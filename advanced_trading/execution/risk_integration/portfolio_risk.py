"""
Portfolio Risk Integration

This module connects execution strategies with portfolio-level risk management.
It provides tools for:

1. Integrating with the PortfolioRiskController to enforce portfolio constraints
2. Validating orders against portfolio-level risk limits
3. Tracking portfolio risk metrics during execution
4. Managing cross-asset risk factors like correlation and concentration

The portfolio integration ensures execution strategies maintain portfolio-level
risk constraints while making trading decisions.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from enum import Enum

from advanced_trading.execution.risk_integration.risk_manager import (
    RiskCheckResult,
    RiskValidationStatus
)

logger = logging.getLogger(__name__)


class PortfolioRiskLevel(Enum):
    """Risk level for the overall portfolio."""
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PortfolioRiskMetrics:
    """Risk metrics for the overall portfolio."""
    total_value: float
    cash_balance: float
    gross_exposure: float
    net_exposure: float
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    daily_pnl: float = 0.0
    daily_pnl_percent: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0
    expected_shortfall: float = 0.0
    sharpe_ratio: float = 0.0
    beta: float = 0.0
    portfolio_risk_level: PortfolioRiskLevel = PortfolioRiskLevel.MODERATE
    updated_at: float = field(default_factory=time.time)


class PortfolioRiskIntegration:
    """
    Integrates execution strategies with portfolio-level risk management.
    
    This class serves as a bridge between the execution system and the
    portfolio risk controller, ensuring that execution decisions comply
    with portfolio-level risk constraints.
    """
    
    def __init__(self,
               risk_controller_path: str = "advanced_trading.risk.controllers.portfolio",
               max_gross_exposure: float = 1.5,
               max_net_exposure: float = 1.0,
               max_drawdown: float = 0.15,
               max_daily_loss: float = 0.05,
               max_concentration: float = 0.25,
               max_correlation: float = 0.7,
               volatility_target: float = 0.1):
        """
        Initialize portfolio risk integration.
        
        Args:
            risk_controller_path: Import path for the portfolio risk controller
            max_gross_exposure: Maximum gross exposure (1.5 = 150% of portfolio value)
            max_net_exposure: Maximum net exposure (1.0 = 100% of portfolio value)
            max_drawdown: Maximum allowed drawdown (0.15 = 15%)
            max_daily_loss: Maximum allowed daily loss (0.05 = 5%)
            max_concentration: Maximum concentration in a single asset/sector
            max_correlation: Maximum allowed correlation between positions
            volatility_target: Target annualized volatility for the portfolio
        """
        self.max_gross_exposure = max_gross_exposure
        self.max_net_exposure = max_net_exposure
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        self.max_concentration = max_concentration
        self.max_correlation = max_correlation
        self.volatility_target = volatility_target
        
        self.risk_controller_path = risk_controller_path
        self.risk_controller = None
        self.portfolio_metrics = None
        self._last_update = time.time()
        
        # Try to import the portfolio risk controller
        try:
            self._load_risk_controller()
        except ImportError:
            logger.warning(f"Could not import portfolio risk controller from {risk_controller_path}")
    
    def _load_risk_controller(self) -> None:
        """
        Dynamically load the portfolio risk controller.
        This allows for flexible configuration without direct dependencies.
        """
        try:
            module_path = self.risk_controller_path.rsplit('.', 1)
            if len(module_path) == 2:
                module_name, class_name = module_path
                module = __import__(module_name, fromlist=[class_name])
                controller_class = getattr(module, class_name)
                self.risk_controller = controller_class()
                logger.info(f"Successfully loaded portfolio risk controller: {class_name}")
            else:
                logger.error(f"Invalid module path format: {self.risk_controller_path}")
        except (ImportError, AttributeError) as e:
            logger.error(f"Error loading portfolio risk controller: {str(e)}")
            self.risk_controller = None
    
    def validate_portfolio_with_order(self, 
                                 order: Dict[str, Any],
                                 current_portfolio: Dict[str, Any]) -> List[RiskCheckResult]:
        """
        Validate how an order would affect portfolio risk.
        
        Args:
            order: Order details
            current_portfolio: Current portfolio state
            
        Returns:
            List of risk check results
        """
        results = []
        symbol = order.get("symbol", "")
        side = order.get("side", "").lower()
        size = order.get("size", 0.0)
        price = order.get("price", 0.0)
        notional = size * price
        
        # Get portfolio exposure data
        gross_exposure = current_portfolio.get("gross_exposure", 0.0)
        net_exposure = current_portfolio.get("net_exposure", 0.0)
        asset_exposures = current_portfolio.get("asset_exposures", {})
        total_value = current_portfolio.get("total_value", 0.0)
        
        if not total_value:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name="portfolio_value",
                message="Invalid portfolio value: cannot calculate exposure impacts",
                details={"total_value": total_value},
                is_critical=True
            ))
            return results
        
        # Calculate exposure impact
        exposure_delta = notional / total_value
        new_gross_exposure = gross_exposure + exposure_delta
        
        # For net exposure, consider the direction
        direction = 1 if side == "buy" else -1
        new_net_exposure = net_exposure + (direction * exposure_delta)
        
        # Check against maximum gross exposure
        if new_gross_exposure > self.max_gross_exposure:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name="portfolio_gross_exposure",
                message=(f"Order would exceed max gross exposure: "
                        f"{new_gross_exposure:.2f}x > {self.max_gross_exposure:.2f}x"),
                details={
                    "current_gross_exposure": gross_exposure,
                    "order_exposure": exposure_delta,
                    "new_gross_exposure": new_gross_exposure,
                    "max_gross_exposure": self.max_gross_exposure
                },
                is_critical=True
            ))
        
        # Check against maximum net exposure
        if abs(new_net_exposure) > self.max_net_exposure:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name="portfolio_net_exposure",
                message=(f"Order would exceed max net exposure: "
                        f"{abs(new_net_exposure):.2f}x > {self.max_net_exposure:.2f}x"),
                details={
                    "current_net_exposure": net_exposure,
                    "order_exposure": direction * exposure_delta,
                    "new_net_exposure": new_net_exposure,
                    "max_net_exposure": self.max_net_exposure
                },
                is_critical=True
            ))
        
        # Check concentration in a single asset
        current_exposure = asset_exposures.get(symbol, 0.0)
        new_exposure = current_exposure + (direction * exposure_delta)
        
        if abs(new_exposure) > self.max_concentration:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name="portfolio_concentration",
                message=(f"Order would create excessive concentration in {symbol}: "
                        f"{abs(new_exposure):.2%} > {self.max_concentration:.2%}"),
                details={
                    "symbol": symbol,
                    "current_exposure": current_exposure,
                    "new_exposure": new_exposure,
                    "max_concentration": self.max_concentration
                },
                is_critical=False  # Warning, not critical
            ))
        
        # If using the risk controller, perform additional checks
        if self.risk_controller:
            # Create a simulated portfolio with the order applied
            simulated_portfolio = self._simulate_portfolio_with_order(
                order, current_portfolio
            )
            
            try:
                # Use the risk controller to validate the simulated portfolio
                controller_results = self.risk_controller.validate_portfolio(simulated_portfolio)
                
                # Convert controller results to RiskCheckResult
                for check_name, check_result in controller_results.items():
                    if not check_result.get("passed", True):
                        results.append(RiskCheckResult(
                            status=RiskValidationStatus.FAILED,
                            check_name=f"portfolio_controller_{check_name}",
                            message=check_result.get("message", f"Portfolio risk check failed: {check_name}"),
                            details=check_result.get("details", {}),
                            is_critical=check_result.get("is_critical", False)
                        ))
            except Exception as e:
                logger.error(f"Error validating with portfolio risk controller: {str(e)}")
                results.append(RiskCheckResult(
                    status=RiskValidationStatus.ERROR,
                    check_name="portfolio_controller",
                    message=f"Error validating with portfolio risk controller: {str(e)}",
                    details={"error": str(e)},
                    is_critical=False
                ))
        
        return results
    
    def _simulate_portfolio_with_order(self, 
                                  order: Dict[str, Any],
                                  current_portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a simulated portfolio with the order applied.
        
        Args:
            order: Order details
            current_portfolio: Current portfolio state
            
        Returns:
            Simulated portfolio state after the order
        """
        # Create a deep copy of the portfolio to avoid modifying the original
        simulated = {k: v.copy() if isinstance(v, dict) else v 
                   for k, v in current_portfolio.items()}
        
        # Deep copy the positions
        if "positions" in simulated:
            simulated["positions"] = {k: v.copy() 
                                     for k, v in simulated["positions"].items()}
        
        # Get order details
        symbol = order.get("symbol", "")
        side = order.get("side", "").lower()
        size = order.get("size", 0.0)
        price = order.get("price", 0.0)
        notional = size * price
        
        # Update the position
        if "positions" not in simulated:
            simulated["positions"] = {}
            
        if symbol not in simulated["positions"]:
            simulated["positions"][symbol] = {
                "size": 0.0,
                "notional": 0.0,
                "unrealized_pnl": 0.0
            }
        
        # Apply the order to the position
        position = simulated["positions"][symbol]
        if side == "buy":
            position["size"] += size
            position["notional"] += notional
        else:  # sell
            position["size"] -= size
            position["notional"] -= notional
        
        # Update exposures
        total_value = simulated.get("total_value", 0.0)
        
        if "asset_exposures" not in simulated:
            simulated["asset_exposures"] = {}
            
        if total_value > 0:
            # Calculate new exposure
            direction = 1 if side == "buy" else -1
            exposure_delta = notional / total_value
            
            # Update asset exposure
            current_exposure = simulated["asset_exposures"].get(symbol, 0.0)
            simulated["asset_exposures"][symbol] = current_exposure + (direction * exposure_delta)
            
            # Update gross and net exposure
            simulated["gross_exposure"] = simulated.get("gross_exposure", 0.0) + exposure_delta
            simulated["net_exposure"] = simulated.get("net_exposure", 0.0) + (direction * exposure_delta)
        
        return simulated
    
    def update_portfolio_metrics(self, portfolio_data: Dict[str, Any]) -> PortfolioRiskMetrics:
        """
        Update portfolio risk metrics from portfolio data.
        
        Args:
            portfolio_data: Current portfolio data
            
        Returns:
            Updated portfolio risk metrics
        """
        # Extract portfolio values
        total_value = portfolio_data.get("total_value", 0.0)
        cash_balance = portfolio_data.get("cash_balance", 0.0)
        gross_exposure = portfolio_data.get("gross_exposure", 0.0)
        net_exposure = portfolio_data.get("net_exposure", 0.0)
        current_drawdown = portfolio_data.get("current_drawdown", 0.0)
        max_drawdown = portfolio_data.get("max_drawdown", 0.0)
        daily_pnl = portfolio_data.get("daily_pnl", 0.0)
        daily_pnl_percent = portfolio_data.get("daily_pnl_percent", 0.0)
        volatility = portfolio_data.get("volatility", 0.0)
        var_95 = portfolio_data.get("var_95", 0.0)
        expected_shortfall = portfolio_data.get("expected_shortfall", 0.0)
        sharpe_ratio = portfolio_data.get("sharpe_ratio", 0.0)
        beta = portfolio_data.get("beta", 0.0)
        
        # Determine risk level
        risk_level = self._determine_portfolio_risk_level(
            gross_exposure=gross_exposure,
            current_drawdown=current_drawdown,
            daily_pnl_percent=daily_pnl_percent,
            volatility=volatility
        )
        
        # Create and store metrics
        self.portfolio_metrics = PortfolioRiskMetrics(
            total_value=total_value,
            cash_balance=cash_balance,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            current_drawdown=current_drawdown,
            max_drawdown=max_drawdown,
            daily_pnl=daily_pnl,
            daily_pnl_percent=daily_pnl_percent,
            volatility=volatility,
            var_95=var_95,
            expected_shortfall=expected_shortfall,
            sharpe_ratio=sharpe_ratio,
            beta=beta,
            portfolio_risk_level=risk_level,
            updated_at=time.time()
        )
        
        # Check if using portfolio risk controller
        if self.risk_controller:
            try:
                # Update the risk controller with latest portfolio data
                if hasattr(self.risk_controller, 'update_portfolio'):
                    self.risk_controller.update_portfolio(portfolio_data)
            except Exception as e:
                logger.error(f"Error updating portfolio risk controller: {str(e)}")
        
        return self.portfolio_metrics
    
    def _determine_portfolio_risk_level(self,
                                   gross_exposure: float,
                                   current_drawdown: float,
                                   daily_pnl_percent: float,
                                   volatility: float) -> PortfolioRiskLevel:
        """
        Determine the overall portfolio risk level.
        
        Args:
            gross_exposure: Current gross exposure
            current_drawdown: Current drawdown
            daily_pnl_percent: Daily P&L as a percentage
            volatility: Portfolio volatility
            
        Returns:
            Portfolio risk level
        """
        # Start with assumption of moderate risk
        risk_points = 0
        
        # Score each risk factor
        # Exposure risk
        if gross_exposure > self.max_gross_exposure * 0.9:
            risk_points += 3  # Near max exposure
        elif gross_exposure > self.max_gross_exposure * 0.75:
            risk_points += 2  # High exposure
        elif gross_exposure > self.max_gross_exposure * 0.5:
            risk_points += 1  # Moderate exposure
            
        # Drawdown risk
        if current_drawdown > self.max_drawdown * 0.8:
            risk_points += 3  # Near max drawdown
        elif current_drawdown > self.max_drawdown * 0.6:
            risk_points += 2  # Significant drawdown
        elif current_drawdown > self.max_drawdown * 0.4:
            risk_points += 1  # Moderate drawdown
            
        # Daily loss risk
        if daily_pnl_percent < -self.max_daily_loss * 0.8:
            risk_points += 3  # Near max daily loss
        elif daily_pnl_percent < -self.max_daily_loss * 0.6:
            risk_points += 2  # Significant daily loss
        elif daily_pnl_percent < -self.max_daily_loss * 0.3:
            risk_points += 1  # Moderate daily loss
        
        # Volatility risk
        if volatility > self.volatility_target * 1.5:
            risk_points += 2  # Much higher volatility than target
        elif volatility > self.volatility_target * 1.2:
            risk_points += 1  # Higher volatility than target
        
        # Determine risk level based on points
        if risk_points >= 8:
            return PortfolioRiskLevel.CRITICAL
        elif risk_points >= 5:
            return PortfolioRiskLevel.HIGH
        elif risk_points >= 3:
            return PortfolioRiskLevel.ELEVATED
        elif risk_points >= 1:
            return PortfolioRiskLevel.MODERATE
        else:
            return PortfolioRiskLevel.LOW
    
    def get_risk_allocation(self, 
                         symbol: str,
                         portfolio_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Get risk allocation for a symbol based on portfolio risk factors.
        
        Args:
            symbol: Asset symbol
            portfolio_data: Current portfolio data
            
        Returns:
            Dictionary with allocation details
        """
        # Update portfolio metrics if needed
        if self.portfolio_metrics is None:
            self.update_portfolio_metrics(portfolio_data)
        
        # Get portfolio risk level
        risk_level = self.portfolio_metrics.portfolio_risk_level
        
        # Get asset information
        asset_volatility = 0.0
        asset_correlation = 0.0
        asset_beta = 0.0
        
        # Try to get asset-specific risk metrics
        assets_data = portfolio_data.get("assets_data", {})
        if symbol in assets_data:
            asset_data = assets_data[symbol]
            asset_volatility = asset_data.get("volatility", 0.0)
            asset_correlation = asset_data.get("correlation", 0.0)
            asset_beta = asset_data.get("beta", 0.0)
        
        # Base allocation starts from maximum concentration
        base_allocation = self.max_concentration
        
        # Adjust for portfolio risk level
        if risk_level == PortfolioRiskLevel.CRITICAL:
            risk_factor = 0.25  # Reduce to 25% of base allocation
        elif risk_level == PortfolioRiskLevel.HIGH:
            risk_factor = 0.5   # Reduce to 50% of base allocation
        elif risk_level == PortfolioRiskLevel.ELEVATED:
            risk_factor = 0.75  # Reduce to 75% of base allocation
        elif risk_level == PortfolioRiskLevel.MODERATE:
            risk_factor = 0.9   # Reduce to 90% of base allocation
        else:  # LOW
            risk_factor = 1.0   # Use full base allocation
            
        # Adjust for asset-specific risk
        asset_factor = 1.0
        
        # Adjust for volatility (inverse relationship)
        if asset_volatility > 0:
            vol_factor = min(1.0, 0.2 / asset_volatility)  # Normalize to moderate volatility
            asset_factor *= max(0.25, vol_factor)
        
        # Adjust for correlation (lower is better)
        if asset_correlation > self.max_correlation:
            corr_factor = max(0.5, 1.0 - (asset_correlation - self.max_correlation))
            asset_factor *= corr_factor
        
        # Calculate final allocation
        allocation = base_allocation * risk_factor * asset_factor
        
        # Ensure allocation is within bounds
        allocation = max(0.01, min(allocation, self.max_concentration))
        
        return {
            "allocation_percent": allocation,
            "max_allocation_percent": self.max_concentration,
            "portfolio_risk_level": risk_level.value,
            "risk_factor": risk_factor,
            "asset_factor": asset_factor,
            "base_allocation": base_allocation
        }
    
    def should_reduce_exposure(self, portfolio_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Determine if portfolio exposure should be reduced based on risk metrics.
        
        Args:
            portfolio_data: Current portfolio data
            
        Returns:
            Tuple with boolean indicating if reduction is needed and details
        """
        # Update portfolio metrics if needed
        if self.portfolio_metrics is None:
            self.update_portfolio_metrics(portfolio_data)
        
        # Get risk factors
        risk_level = self.portfolio_metrics.portfolio_risk_level
        gross_exposure = self.portfolio_metrics.gross_exposure
        current_drawdown = self.portfolio_metrics.current_drawdown
        daily_loss = -self.portfolio_metrics.daily_pnl_percent if self.portfolio_metrics.daily_pnl_percent < 0 else 0
        
        # Check various risk triggers
        reduce_exposure = False
        reasons = []
        reduction_percent = 0.0
        
        # Check exposure
        if gross_exposure > self.max_gross_exposure * 0.95:
            reduce_exposure = True
            reasons.append("Approaching maximum gross exposure")
            exposure_reduction = (gross_exposure - (self.max_gross_exposure * 0.8)) / gross_exposure
            reduction_percent = max(reduction_percent, exposure_reduction)
        
        # Check drawdown
        if current_drawdown > self.max_drawdown * 0.8:
            reduce_exposure = True
            reasons.append("Significant portfolio drawdown")
            drawdown_reduction = (current_drawdown - (self.max_drawdown * 0.5)) / self.max_drawdown
            reduction_percent = max(reduction_percent, drawdown_reduction)
        
        # Check daily loss
        if daily_loss > self.max_daily_loss * 0.8:
            reduce_exposure = True
            reasons.append("Approaching maximum daily loss")
            loss_reduction = (daily_loss - (self.max_daily_loss * 0.5)) / self.max_daily_loss
            reduction_percent = max(reduction_percent, loss_reduction)
        
        # Check overall risk level
        if risk_level in (PortfolioRiskLevel.HIGH, PortfolioRiskLevel.CRITICAL):
            reduce_exposure = True
            reasons.append(f"Portfolio risk level is {risk_level.value}")
            level_reduction = 0.3 if risk_level == PortfolioRiskLevel.CRITICAL else 0.2
            reduction_percent = max(reduction_percent, level_reduction)
        
        # Ensure reduction is reasonable
        reduction_percent = min(0.75, max(0.1, reduction_percent))
        
        reduction_details = {
            "should_reduce": reduce_exposure,
            "reduction_percent": reduction_percent,
            "reasons": reasons,
            "current_exposure": gross_exposure,
            "target_exposure": gross_exposure * (1 - reduction_percent) if reduce_exposure else gross_exposure,
            "risk_level": risk_level.value
        }
        
        return reduce_exposure, reduction_details


# Public API
__all__ = [
    'PortfolioRiskLevel',
    'PortfolioRiskMetrics',
    'PortfolioRiskIntegration'
] 