"""
Position Risk Validator

This module provides a position-level risk validation system that monitors and
validates individual trading positions for risk compliance. It includes tools for:

1. Calculating position-level risk metrics
2. Validating positions against defined risk limits
3. Managing stop-loss and take-profit levels
4. Tracking position performance and risk metrics
5. Providing recommendations for position adjustments

The PositionRiskValidator integrates with the ExecutionRiskManager to ensure
trading positions remain within acceptable risk parameters.
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


class PositionRiskStatus(Enum):
    """Status of a position's risk level."""
    SAFE = "safe"            # Position is within all risk parameters
    WARNING = "warning"      # Position is close to risk limits
    AT_RISK = "at_risk"      # Position is at risk of exceeding limits
    VIOLATED = "violated"    # Position has exceeded risk limits
    UNKNOWN = "unknown"      # Risk status could not be determined


@dataclass
class PositionRiskMetrics:
    """Risk metrics for a single position."""
    symbol: str
    current_size: float
    current_notional_value: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    unrealized_pnl_percent: float = 0.0
    position_age_seconds: float = 0.0
    max_drawdown: float = 0.0
    daily_volatility: float = 0.0
    var_95: float = 0.0  # Value at Risk (95% confidence)
    expected_shortfall: float = 0.0  # Expected shortfall
    risk_reward_ratio: float = 0.0
    portfolio_contribution_percent: float = 0.0
    updated_at: float = field(default_factory=time.time)
    risk_status: PositionRiskStatus = PositionRiskStatus.UNKNOWN
    
    @property
    def is_long(self) -> bool:
        """Check if this is a long position."""
        return self.current_size > 0
    
    @property
    def is_short(self) -> bool:
        """Check if this is a short position."""
        return self.current_size < 0
    
    @property
    def is_profitable(self) -> bool:
        """Check if the position is currently profitable."""
        return self.unrealized_pnl > 0


class PositionRiskValidator:
    """
    Validates and monitors position-level risk metrics to ensure positions
    comply with risk management rules.
    """
    
    def __init__(self, 
               max_position_size_pct: float = 0.1,
               max_position_loss_pct: float = 0.05,
               max_position_var_pct: float = 0.03,
               max_position_age_days: float = 30.0,
               risk_reward_min: float = 1.5,
               enable_auto_stops: bool = True,
               enable_size_scaling: bool = True,
               correlation_limit: float = 0.7):
        """
        Initialize a position risk validator.
        
        Args:
            max_position_size_pct: Maximum position size as percentage of portfolio
            max_position_loss_pct: Maximum allowed loss for a position
            max_position_var_pct: Maximum Value at Risk as percent of portfolio
            max_position_age_days: Maximum age of a position in days
            risk_reward_min: Minimum risk-reward ratio required
            enable_auto_stops: Whether to automatically calculate stop levels
            enable_size_scaling: Whether to scale position size by volatility
            correlation_limit: Maximum allowed correlation with portfolio
        """
        self.max_position_size_pct = max_position_size_pct
        self.max_position_loss_pct = max_position_loss_pct
        self.max_position_var_pct = max_position_var_pct
        self.max_position_age_seconds = max_position_age_days * 24 * 60 * 60
        self.risk_reward_min = risk_reward_min
        self.enable_auto_stops = enable_auto_stops
        self.enable_size_scaling = enable_size_scaling
        self.correlation_limit = correlation_limit
        
        # Position tracking
        self.position_metrics: Dict[str, PositionRiskMetrics] = {}
        self.violations: Dict[str, List[RiskCheckResult]] = {}
        self.stop_levels: Dict[str, Dict[str, float]] = {}
        self._last_update = time.time()
    
    def calculate_position_metrics(self, 
                                 symbol: str, 
                                 position_data: Dict[str, Any],
                                 market_data: Dict[str, Any],
                                 portfolio_data: Dict[str, Any]) -> PositionRiskMetrics:
        """
        Calculate risk metrics for a single position.
        
        Args:
            symbol: Symbol of the position
            position_data: Data about the position
            market_data: Market data for the symbol
            portfolio_data: Overall portfolio data
            
        Returns:
            Updated position risk metrics
        """
        current_time = time.time()
        
        # Extract position information
        current_size = position_data.get("size", 0.0)
        entry_price = position_data.get("entry_price", 0.0)
        entry_time = position_data.get("entry_time", current_time)
        position_age_seconds = current_time - entry_time
        
        # Extract market data
        current_price = market_data.get("price", 0.0)
        daily_volatility = market_data.get("daily_volatility", 0.0)
        
        # Extract portfolio data
        portfolio_value = portfolio_data.get("total_value", 0.0)
        
        # Calculate basic metrics
        current_notional_value = abs(current_size * current_price)
        portfolio_contribution_percent = (
            current_notional_value / portfolio_value if portfolio_value > 0 else 0.0
        )
        
        # Calculate P&L
        if current_size > 0:  # Long position
            unrealized_pnl = current_size * (current_price - entry_price)
        else:  # Short position
            unrealized_pnl = current_size * (entry_price - current_price)
        
        unrealized_pnl_percent = (
            unrealized_pnl / (current_size * entry_price) if current_size * entry_price != 0 else 0.0
        )
        
        # Calculate risk metrics
        max_drawdown = position_data.get("max_drawdown", 0.0)
        
        # Simple VaR calculation (can be replaced with more sophisticated methods)
        var_95 = current_notional_value * daily_volatility * 1.65
        var_pct = var_95 / portfolio_value if portfolio_value > 0 else 0.0
        
        # Simple Expected Shortfall calculation
        expected_shortfall = var_95 * 1.2
        
        # Calculate risk-reward ratio if stop and target are available
        risk_reward_ratio = 1.0
        if "stop_price" in position_data and "target_price" in position_data:
            stop_price = position_data["stop_price"]
            target_price = position_data["target_price"]
            if current_size > 0:  # Long
                risk = entry_price - stop_price
                reward = target_price - entry_price
            else:  # Short
                risk = stop_price - entry_price
                reward = entry_price - target_price
                
            if risk > 0:
                risk_reward_ratio = reward / risk
        
        # Determine risk status
        risk_status = self._determine_risk_status(
            position_age_seconds=position_age_seconds,
            portfolio_contribution_percent=portfolio_contribution_percent,
            unrealized_pnl_percent=unrealized_pnl_percent,
            var_pct=var_pct,
            risk_reward_ratio=risk_reward_ratio
        )
        
        # Create and return metrics
        metrics = PositionRiskMetrics(
            symbol=symbol,
            current_size=current_size,
            current_notional_value=current_notional_value,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=unrealized_pnl_percent,
            position_age_seconds=position_age_seconds,
            max_drawdown=max_drawdown,
            daily_volatility=daily_volatility,
            var_95=var_95,
            expected_shortfall=expected_shortfall,
            risk_reward_ratio=risk_reward_ratio,
            portfolio_contribution_percent=portfolio_contribution_percent,
            risk_status=risk_status,
            updated_at=current_time
        )
        
        # Update stored metrics
        self.position_metrics[symbol] = metrics
        return metrics
    
    def _determine_risk_status(self,
                            position_age_seconds: float,
                            portfolio_contribution_percent: float,
                            unrealized_pnl_percent: float,
                            var_pct: float,
                            risk_reward_ratio: float) -> PositionRiskStatus:
        """
        Determine the risk status of a position based on its metrics.
        
        Args:
            position_age_seconds: Age of the position in seconds
            portfolio_contribution_percent: Position's percentage of portfolio
            unrealized_pnl_percent: Unrealized P&L as a percentage
            var_pct: Value at Risk as percentage of portfolio
            risk_reward_ratio: Current risk-reward ratio
            
        Returns:
            Risk status of the position
        """
        # Check for violations
        if (portfolio_contribution_percent > self.max_position_size_pct or
            unrealized_pnl_percent < -self.max_position_loss_pct or
            var_pct > self.max_position_var_pct or
            position_age_seconds > self.max_position_age_seconds):
            return PositionRiskStatus.VIOLATED
        
        # Check for at-risk positions (80% of limits)
        if (portfolio_contribution_percent > self.max_position_size_pct * 0.8 or
            unrealized_pnl_percent < -self.max_position_loss_pct * 0.8 or
            var_pct > self.max_position_var_pct * 0.8 or
            position_age_seconds > self.max_position_age_seconds * 0.8 or
            risk_reward_ratio < self.risk_reward_min * 0.8):
            return PositionRiskStatus.AT_RISK
        
        # Check for warning positions (60% of limits)
        if (portfolio_contribution_percent > self.max_position_size_pct * 0.6 or
            unrealized_pnl_percent < -self.max_position_loss_pct * 0.6 or
            var_pct > self.max_position_var_pct * 0.6 or
            position_age_seconds > self.max_position_age_seconds * 0.6 or
            risk_reward_ratio < self.risk_reward_min * 0.9):
            return PositionRiskStatus.WARNING
        
        # Position is safe
        return PositionRiskStatus.SAFE
    
    def validate_position(self, 
                       symbol: str,
                       position_data: Dict[str, Any],
                       market_data: Dict[str, Any],
                       portfolio_data: Dict[str, Any]) -> List[RiskCheckResult]:
        """
        Validate a position against risk parameters and return check results.
        
        Args:
            symbol: Symbol of the position
            position_data: Data about the position
            market_data: Market data for the symbol
            portfolio_data: Overall portfolio data
            
        Returns:
            List of risk check results
        """
        # Calculate or get current metrics
        metrics = self.calculate_position_metrics(
            symbol, position_data, market_data, portfolio_data
        )
        
        results = []
        
        # Check position size
        if metrics.portfolio_contribution_percent > self.max_position_size_pct:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name="position_size_limit",
                message=(f"Position size exceeds maximum: {metrics.portfolio_contribution_percent:.2%} > "
                        f"{self.max_position_size_pct:.2%}"),
                details={
                    "symbol": symbol,
                    "current_contribution": metrics.portfolio_contribution_percent,
                    "max_allowed": self.max_position_size_pct,
                    "notional_value": metrics.current_notional_value
                },
                is_critical=True
            ))
        
        # Check position loss
        if metrics.unrealized_pnl_percent < -self.max_position_loss_pct:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name="position_loss_limit",
                message=(f"Position loss exceeds maximum: {metrics.unrealized_pnl_percent:.2%} < "
                        f"-{self.max_position_loss_pct:.2%}"),
                details={
                    "symbol": symbol,
                    "unrealized_pnl": metrics.unrealized_pnl,
                    "unrealized_pnl_percent": metrics.unrealized_pnl_percent,
                    "max_allowed_loss": self.max_position_loss_pct
                },
                is_critical=True
            ))
        
        # Check position VAR
        position_var_pct = metrics.var_95 / portfolio_data.get("total_value", 1.0)
        if position_var_pct > self.max_position_var_pct:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name="position_var_limit",
                message=(f"Position VaR exceeds maximum: {position_var_pct:.2%} > "
                        f"{self.max_position_var_pct:.2%}"),
                details={
                    "symbol": symbol,
                    "var_95": metrics.var_95,
                    "position_var_pct": position_var_pct,
                    "max_allowed_var": self.max_position_var_pct
                },
                is_critical=False
            ))
        
        # Check position age
        if metrics.position_age_seconds > self.max_position_age_seconds:
            age_days = metrics.position_age_seconds / (24 * 60 * 60)
            max_age_days = self.max_position_age_seconds / (24 * 60 * 60)
            results.append(RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name="position_age_limit",
                message=(f"Position age exceeds maximum: {age_days:.1f} days > "
                        f"{max_age_days:.1f} days"),
                details={
                    "symbol": symbol,
                    "position_age_seconds": metrics.position_age_seconds,
                    "position_age_days": age_days,
                    "max_allowed_age_days": max_age_days
                },
                is_critical=False
            ))
        
        # Check risk-reward ratio
        if metrics.risk_reward_ratio < self.risk_reward_min:
            results.append(RiskCheckResult(
                status=RiskValidationStatus.WARNING,
                check_name="risk_reward_ratio",
                message=(f"Risk-reward ratio below minimum: {metrics.risk_reward_ratio:.2f} < "
                        f"{self.risk_reward_min:.2f}"),
                details={
                    "symbol": symbol,
                    "risk_reward_ratio": metrics.risk_reward_ratio,
                    "min_risk_reward": self.risk_reward_min
                },
                is_critical=False
            ))
        
        # Store violations
        if results:
            self.violations[symbol] = results
        elif symbol in self.violations:
            del self.violations[symbol]
            
        return results
    
    def validate_all_positions(self, 
                            positions: Dict[str, Dict[str, Any]],
                            market_data: Dict[str, Dict[str, Any]],
                            portfolio_data: Dict[str, Any]) -> Dict[str, List[RiskCheckResult]]:
        """
        Validate all positions and return violations grouped by symbol.
        
        Args:
            positions: Dictionary of positions by symbol
            market_data: Market data by symbol
            portfolio_data: Overall portfolio data
            
        Returns:
            Dictionary of risk check results by symbol
        """
        results = {}
        self._last_update = time.time()
        
        for symbol, position_data in positions.items():
            symbol_market_data = market_data.get(symbol, {})
            position_results = self.validate_position(
                symbol, position_data, symbol_market_data, portfolio_data
            )
            if position_results:
                results[symbol] = position_results
        
        return results
    
    def calculate_stop_levels(self,
                           symbol: str,
                           position_data: Dict[str, Any],
                           market_data: Dict[str, Any],
                           risk_percent: float = 0.01) -> Dict[str, float]:
        """
        Calculate recommended stop and target levels for a position.
        
        Args:
            symbol: Symbol of the position
            position_data: Data about the position
            market_data: Market data for the symbol
            risk_percent: Percentage of portfolio to risk (0.01 = 1%)
            
        Returns:
            Dictionary with stop and target prices
        """
        if not self.enable_auto_stops:
            return {}
        
        current_size = position_data.get("size", 0.0)
        entry_price = position_data.get("entry_price", 0.0)
        current_price = market_data.get("price", 0.0)
        
        # If we don't have necessary data, return empty dict
        if not current_size or not entry_price or not current_price:
            return {}
        
        # Calculate ATR if available for better stop placement
        atr = market_data.get("atr", 0.0)
        if not atr:
            # Estimate ATR as a percentage of price if not provided
            daily_volatility = market_data.get("daily_volatility", 0.02)
            atr = current_price * daily_volatility
        
        # Calculate stop distance based on risk tolerance
        is_long = current_size > 0
        
        # Default stop and target distances
        stop_distance = atr * 2
        target_distance = atr * 4  # 2:1 reward-to-risk ratio
        
        # Calculate actual stop and target prices
        if is_long:
            stop_price = max(entry_price - stop_distance, current_price - stop_distance)
            target_price = entry_price + target_distance
        else:
            stop_price = min(entry_price + stop_distance, current_price + stop_distance)
            target_price = entry_price - target_distance
        
        # Store and return results
        result = {
            "stop_price": stop_price,
            "target_price": target_price,
            "risk_reward_ratio": target_distance / stop_distance if stop_distance > 0 else 0.0,
            "stop_distance_pct": stop_distance / current_price,
            "target_distance_pct": target_distance / current_price
        }
        
        self.stop_levels[symbol] = result
        return result
    
    def adjust_position_size(self,
                          symbol: str,
                          base_position_size: float,
                          market_data: Dict[str, Any],
                          portfolio_data: Dict[str, Any]) -> float:
        """
        Adjust a position's size based on volatility and risk factors.
        
        Args:
            symbol: Symbol for the position
            base_position_size: Initial requested position size
            market_data: Market data for the symbol
            portfolio_data: Overall portfolio data
            
        Returns:
            Adjusted position size
        """
        if not self.enable_size_scaling:
            return base_position_size
        
        # Get market volatility
        volatility = market_data.get("daily_volatility", 0.0)
        if not volatility:
            return base_position_size
        
        # Base volatility for reference (consider this "normal" volatility)
        base_volatility = 0.02  # 2% daily volatility
        
        # Volatility scaling factor (inverse relationship to volatility)
        vol_factor = base_volatility / max(volatility, 0.005)
        
        # Apply minimum and maximum scaling
        vol_factor = max(0.25, min(vol_factor, 2.0))
        
        # Get portfolio concentration for this symbol
        portfolio_value = portfolio_data.get("total_value", 0.0)
        if not portfolio_value:
            return base_position_size
            
        # Check existing risk for this symbol
        metrics = self.position_metrics.get(symbol)
        if metrics and metrics.risk_status in (PositionRiskStatus.AT_RISK, PositionRiskStatus.VIOLATED):
            # Reduce size for risky positions
            risk_factor = 0.5
        elif metrics and metrics.risk_status == PositionRiskStatus.WARNING:
            risk_factor = 0.75
        else:
            risk_factor = 1.0
        
        # Apply scaling factors
        adjusted_size = base_position_size * vol_factor * risk_factor
        
        logger.info(f"Adjusted position size for {symbol}: {base_position_size} → {adjusted_size} "
                   f"(vol_factor={vol_factor:.2f}, risk_factor={risk_factor:.2f})")
        
        return adjusted_size
    
    def get_position_risk_status(self, symbol: str) -> PositionRiskStatus:
        """
        Get the current risk status for a position.
        
        Args:
            symbol: Symbol of the position
            
        Returns:
            Risk status of the position
        """
        metrics = self.position_metrics.get(symbol)
        if not metrics:
            return PositionRiskStatus.UNKNOWN
        return metrics.risk_status
    
    def get_at_risk_positions(self) -> Set[str]:
        """
        Get the set of positions that are at risk or violated.
        
        Returns:
            Set of symbols for at-risk positions
        """
        at_risk = set()
        for symbol, metrics in self.position_metrics.items():
            if metrics.risk_status in (PositionRiskStatus.AT_RISK, PositionRiskStatus.VIOLATED):
                at_risk.add(symbol)
        return at_risk
    
    def get_safe_allocation(self, 
                         symbol: str, 
                         portfolio_data: Dict[str, Any]) -> float:
        """
        Get the safe allocation percentage for a symbol based on current risk factors.
        
        Args:
            symbol: Symbol to check
            portfolio_data: Portfolio data
            
        Returns:
            Safe allocation as a percentage of portfolio (0.0-1.0)
        """
        # Start with the max position size
        safe_allocation = self.max_position_size_pct
        
        # Adjust based on current metrics if available
        metrics = self.position_metrics.get(symbol)
        if metrics:
            # Reduce for high volatility
            if metrics.daily_volatility > 0.03:  # 3% daily volatility
                vol_factor = 0.03 / metrics.daily_volatility
                safe_allocation *= max(0.25, min(vol_factor, 1.0))
            
            # Reduce for poor risk-reward
            if metrics.risk_reward_ratio < self.risk_reward_min:
                rr_factor = metrics.risk_reward_ratio / self.risk_reward_min
                safe_allocation *= max(0.25, min(rr_factor, 1.0))
        
        return safe_allocation


# Public API
__all__ = [
    'PositionRiskStatus',
    'PositionRiskMetrics',
    'PositionRiskValidator'
] 