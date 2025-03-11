"""
Risk Checks

This module provides interfaces and implementations for pre-trade and post-trade
risk checks. Pre-trade checks validate orders before they are submitted to ensure
they comply with risk parameters. Post-trade checks analyze execution results to
identify issues and provide feedback for future executions.

The module includes common implementations of standard risk checks such as position
size limits, drawdown checks, exposure limits, and volume-based checks.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

from advanced_trading.execution.risk_integration.risk_manager import (
    RiskCheckResult, 
    RiskValidationStatus
)

logger = logging.getLogger(__name__)


class PreTradeRiskCheck(ABC):
    """
    Interface for pre-trade risk checks that validate orders before execution.
    """
    
    def __init__(self, name: str, description: Optional[str] = None, is_critical: bool = True):
        """
        Initialize a pre-trade risk check.
        
        Args:
            name: Unique identifier for this check
            description: Optional human-readable description
            is_critical: Whether this check is critical (failing stops the order)
        """
        self.name = name
        self.description = description or ""
        self.is_critical = is_critical
        self.enabled = True
    
    @abstractmethod
    def check(self, 
             order: Dict[str, Any], 
             portfolio_state: Dict[str, Any],
             market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Validate an order against risk parameters.
        
        Args:
            order: Order details including symbol, size, side, etc.
            portfolio_state: Current state of the portfolio
            market_data: Relevant market data for risk calculations
            
        Returns:
            Result of the risk check
        """
        pass
    
    def __call__(self, 
                order: Dict[str, Any], 
                portfolio_state: Dict[str, Any],
                market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Make the check callable for easier integration with risk manager.
        
        Args:
            order: Order details
            portfolio_state: Portfolio state
            market_data: Market data
            
        Returns:
            Result of the risk check
        """
        if not self.enabled:
            return RiskCheckResult(
                status=RiskValidationStatus.PASSED,
                check_name=self.name,
                message=f"Check '{self.name}' is disabled, skipping validation",
                is_critical=False
            )
        
        try:
            return self.check(order, portfolio_state, market_data)
        except Exception as e:
            logger.error(f"Error in pre-trade check '{self.name}': {e}")
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Error executing check: {str(e)}",
                details={"error": str(e)},
                is_critical=self.is_critical
            )
    
    def enable(self) -> None:
        """Enable this risk check."""
        self.enabled = True
        
    def disable(self) -> None:
        """Disable this risk check."""
        self.enabled = False


class PostTradeRiskAnalysis(ABC):
    """
    Interface for post-trade risk analysis to assess execution quality and compliance.
    """
    
    def __init__(self, name: str, description: Optional[str] = None):
        """
        Initialize a post-trade risk analysis.
        
        Args:
            name: Unique identifier for this analysis
            description: Optional human-readable description
        """
        self.name = name
        self.description = description or ""
        self.enabled = True
    
    @abstractmethod
    def analyze(self, 
               order: Dict[str, Any],
               execution_details: Dict[str, Any],
               portfolio_state: Dict[str, Any],
               market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Analyze execution results against risk parameters.
        
        Args:
            order: Original order details
            execution_details: Details of how the order was executed
            portfolio_state: Current state of the portfolio
            market_data: Relevant market data for risk calculations
            
        Returns:
            Result of the risk analysis
        """
        pass
    
    def __call__(self, 
                order: Dict[str, Any],
                execution_details: Dict[str, Any],
                portfolio_state: Dict[str, Any],
                market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Make the analysis callable for easier integration with risk manager.
        
        Args:
            order: Original order details
            execution_details: Execution details
            portfolio_state: Portfolio state
            market_data: Market data
            
        Returns:
            Result of the risk analysis
        """
        if not self.enabled:
            return RiskCheckResult(
                status=RiskValidationStatus.PASSED,
                check_name=self.name,
                message=f"Analysis '{self.name}' is disabled, skipping",
                is_critical=False
            )
        
        try:
            return self.analyze(order, execution_details, portfolio_state, market_data)
        except Exception as e:
            logger.error(f"Error in post-trade analysis '{self.name}': {e}")
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Error executing analysis: {str(e)}",
                details={"error": str(e)},
                is_critical=False
            )
    
    def enable(self) -> None:
        """Enable this risk analysis."""
        self.enabled = True
        
    def disable(self) -> None:
        """Disable this risk analysis."""
        self.enabled = False


#
# Pre-Trade Risk Check Implementations
#

class PositionSizeCheck(PreTradeRiskCheck):
    """
    Check if an order's size is within allowable limits based on
    absolute size, percentage of portfolio, or notional value.
    """
    
    def __init__(self, 
               name: str = "position_size_check",
               description: Optional[str] = None,
               is_critical: bool = True,
               max_position_size_usd: float = float('inf'),
               max_position_size_percent: float = 0.1,  # 10% of portfolio
               max_position_notional: Dict[str, float] = None):
        """
        Initialize a position size check.
        
        Args:
            name: Unique identifier for this check
            description: Optional human-readable description
            is_critical: Whether this check is critical
            max_position_size_usd: Maximum position size in USD
            max_position_size_percent: Maximum position size as percentage of portfolio
            max_position_notional: Maximum notional value by asset
        """
        super().__init__(name, description, is_critical)
        self.max_position_size_usd = max_position_size_usd
        self.max_position_size_percent = max_position_size_percent
        self.max_position_notional = max_position_notional or {}
    
    def check(self, 
             order: Dict[str, Any], 
             portfolio_state: Dict[str, Any],
             market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Check if the order's size is within the configured limits.
        
        Args:
            order: Order details
            portfolio_state: Portfolio state
            market_data: Market data
            
        Returns:
            Result of the position size check
        """
        symbol = order.get("symbol")
        side = order.get("side", "").lower()
        size = order.get("size", 0.0)
        price = order.get("price")
        
        # If no price in order, try to get from market data
        if price is None and market_data and "price" in market_data:
            price = market_data.get("price", 0.0)
        
        if not price or price <= 0:
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Cannot validate position size: invalid price {price}",
                details={"symbol": symbol, "price": price},
                is_critical=self.is_critical
            )
        
        # Calculate notional value of the order
        notional_value = size * price
        
        # Get portfolio value
        portfolio_value = portfolio_state.get("total_value", 0.0)
        if portfolio_value <= 0:
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Cannot validate position size: invalid portfolio value {portfolio_value}",
                details={"portfolio_value": portfolio_value},
                is_critical=self.is_critical
            )
        
        # Get current position
        positions = portfolio_state.get("positions", {})
        current_position = positions.get(symbol, {"size": 0.0, "notional": 0.0})
        current_size = current_position.get("size", 0.0)
        current_notional = current_position.get("notional", 0.0)
        
        # Calculate new position after order
        if side == "buy":
            new_size = current_size + size
            new_notional = current_notional + notional_value
        elif side == "sell":
            new_size = current_size - size
            new_notional = current_notional - notional_value
        else:
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Cannot validate position size: invalid side {side}",
                details={"side": side},
                is_critical=self.is_critical
            )
        
        # Check against maximum position size in USD
        if abs(new_notional) > self.max_position_size_usd:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Position size exceeds maximum USD limit: "
                        f"{abs(new_notional):.2f} > {self.max_position_size_usd:.2f}"),
                details={
                    "symbol": symbol,
                    "new_notional": new_notional,
                    "max_position_size_usd": self.max_position_size_usd
                },
                is_critical=self.is_critical
            )
        
        # Check against maximum position size as percentage of portfolio
        position_percent = abs(new_notional) / portfolio_value
        if position_percent > self.max_position_size_percent:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Position size exceeds maximum percentage limit: "
                        f"{position_percent:.2%} > {self.max_position_size_percent:.2%}"),
                details={
                    "symbol": symbol,
                    "new_notional": new_notional,
                    "portfolio_value": portfolio_value,
                    "position_percent": position_percent,
                    "max_position_size_percent": self.max_position_size_percent
                },
                is_critical=self.is_critical
            )
        
        # Check against asset-specific notional limits if configured
        if symbol in self.max_position_notional:
            max_notional = self.max_position_notional[symbol]
            if abs(new_notional) > max_notional:
                return RiskCheckResult(
                    status=RiskValidationStatus.FAILED,
                    check_name=self.name,
                    message=(f"Position size exceeds asset-specific limit for {symbol}: "
                            f"{abs(new_notional):.2f} > {max_notional:.2f}"),
                    details={
                        "symbol": symbol,
                        "new_notional": new_notional,
                        "max_notional": max_notional
                    },
                    is_critical=self.is_critical
                )
        
        return RiskCheckResult(
            status=RiskValidationStatus.PASSED,
            check_name=self.name,
            message="Position size within acceptable limits",
            details={
                "symbol": symbol,
                "new_size": new_size,
                "new_notional": new_notional,
                "position_percent": position_percent,
                "max_position_size_percent": self.max_position_size_percent,
                "max_position_size_usd": self.max_position_size_usd
            },
            is_critical=self.is_critical
        )


class MaxDrawdownCheck(PreTradeRiskCheck):
    """
    Check if executing the order would potentially exceed maximum allowable drawdown.
    """
    
    def __init__(self, 
               name: str = "max_drawdown_check",
               description: Optional[str] = None,
               is_critical: bool = True,
               max_drawdown_percent: float = 0.1,  # 10% max drawdown
               max_daily_loss_percent: float = 0.05):  # 5% max daily loss
        """
        Initialize a maximum drawdown check.
        
        Args:
            name: Unique identifier for this check
            description: Optional human-readable description
            is_critical: Whether this check is critical
            max_drawdown_percent: Maximum allowable drawdown (0.1 = 10%)
            max_daily_loss_percent: Maximum allowable daily loss (0.05 = 5%)
        """
        super().__init__(name, description, is_critical)
        self.max_drawdown_percent = max_drawdown_percent
        self.max_daily_loss_percent = max_daily_loss_percent
    
    def check(self, 
             order: Dict[str, Any], 
             portfolio_state: Dict[str, Any],
             market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Check if the order might exceed drawdown limits.
        
        Args:
            order: Order details
            portfolio_state: Portfolio state
            market_data: Market data
            
        Returns:
            Result of the drawdown check
        """
        # Get current drawdown information
        current_drawdown = portfolio_state.get("current_drawdown", 0.0)
        daily_pnl_percent = portfolio_state.get("daily_pnl_percent", 0.0)
        
        # If we're already exceeding drawdown limits, fail
        if current_drawdown >= self.max_drawdown_percent:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Maximum drawdown already exceeded: "
                        f"{current_drawdown:.2%} >= {self.max_drawdown_percent:.2%}"),
                details={
                    "current_drawdown": current_drawdown,
                    "max_drawdown_percent": self.max_drawdown_percent
                },
                is_critical=self.is_critical
            )
        
        # If we're already exceeding daily loss limits, fail
        if abs(daily_pnl_percent) >= self.max_daily_loss_percent and daily_pnl_percent < 0:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Maximum daily loss already exceeded: "
                        f"{daily_pnl_percent:.2%} <= -{self.max_daily_loss_percent:.2%}"),
                details={
                    "daily_pnl_percent": daily_pnl_percent,
                    "max_daily_loss_percent": self.max_daily_loss_percent
                },
                is_critical=self.is_critical
            )
        
        # If we have estimated loss information for the order, check against remaining capacity
        estimated_loss_percent = order.get("estimated_loss_percent", 0.0)
        if estimated_loss_percent > 0:
            remaining_drawdown_capacity = self.max_drawdown_percent - current_drawdown
            if estimated_loss_percent > remaining_drawdown_capacity:
                return RiskCheckResult(
                    status=RiskValidationStatus.FAILED,
                    check_name=self.name,
                    message=(f"Estimated loss would exceed remaining drawdown capacity: "
                            f"{estimated_loss_percent:.2%} > {remaining_drawdown_capacity:.2%}"),
                    details={
                        "estimated_loss_percent": estimated_loss_percent,
                        "current_drawdown": current_drawdown,
                        "remaining_drawdown_capacity": remaining_drawdown_capacity
                    },
                    is_critical=self.is_critical
                )
            
            remaining_daily_loss_capacity = self.max_daily_loss_percent - abs(daily_pnl_percent)
            if daily_pnl_percent < 0 and estimated_loss_percent > remaining_daily_loss_capacity:
                return RiskCheckResult(
                    status=RiskValidationStatus.FAILED,
                    check_name=self.name,
                    message=(f"Estimated loss would exceed remaining daily loss capacity: "
                            f"{estimated_loss_percent:.2%} > {remaining_daily_loss_capacity:.2%}"),
                    details={
                        "estimated_loss_percent": estimated_loss_percent,
                        "daily_pnl_percent": daily_pnl_percent,
                        "remaining_daily_loss_capacity": remaining_daily_loss_capacity
                    },
                    is_critical=self.is_critical
                )
        
        return RiskCheckResult(
            status=RiskValidationStatus.PASSED,
            check_name=self.name,
            message="Drawdown limits not exceeded",
            details={
                "current_drawdown": current_drawdown,
                "max_drawdown_percent": self.max_drawdown_percent,
                "daily_pnl_percent": daily_pnl_percent,
                "max_daily_loss_percent": self.max_daily_loss_percent
            },
            is_critical=self.is_critical
        )


class ExposureCheck(PreTradeRiskCheck):
    """
    Check if the order would exceed maximum exposure limits for the portfolio.
    """
    
    def __init__(self, 
               name: str = "exposure_check",
               description: Optional[str] = None,
               is_critical: bool = True,
               max_gross_exposure: float = 2.0,  # 2x gross exposure
               max_net_exposure: float = 1.0,  # 1x net exposure
               max_single_asset_exposure: float = 0.25):  # 25% max single asset
        """
        Initialize an exposure check.
        
        Args:
            name: Unique identifier for this check
            description: Optional human-readable description
            is_critical: Whether this check is critical
            max_gross_exposure: Maximum gross exposure as multiple of portfolio value
            max_net_exposure: Maximum net exposure as multiple of portfolio value
            max_single_asset_exposure: Maximum exposure to a single asset
        """
        super().__init__(name, description, is_critical)
        self.max_gross_exposure = max_gross_exposure
        self.max_net_exposure = max_net_exposure
        self.max_single_asset_exposure = max_single_asset_exposure
    
    def check(self, 
             order: Dict[str, Any], 
             portfolio_state: Dict[str, Any],
             market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Check if the order would exceed exposure limits.
        
        Args:
            order: Order details
            portfolio_state: Portfolio state
            market_data: Market data
            
        Returns:
            Result of the exposure check
        """
        symbol = order.get("symbol")
        side = order.get("side", "").lower()
        size = order.get("size", 0.0)
        price = order.get("price")
        
        # If no price in order, try to get from market data
        if price is None and market_data and "price" in market_data:
            price = market_data.get("price", 0.0)
        
        if not price or price <= 0:
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Cannot validate exposure: invalid price {price}",
                details={"symbol": symbol, "price": price},
                is_critical=self.is_critical
            )
        
        # Calculate notional value of the order
        notional_value = size * price
        
        # Get portfolio value and exposures
        portfolio_value = portfolio_state.get("total_value", 0.0)
        if portfolio_value <= 0:
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Cannot validate exposure: invalid portfolio value {portfolio_value}",
                details={"portfolio_value": portfolio_value},
                is_critical=self.is_critical
            )
        
        current_gross_exposure = portfolio_state.get("gross_exposure", 0.0)
        current_net_exposure = portfolio_state.get("net_exposure", 0.0)
        asset_exposures = portfolio_state.get("asset_exposures", {})
        current_asset_exposure = asset_exposures.get(symbol, 0.0)
        
        # Calculate new exposures after order
        if side == "buy":
            sign = 1
        elif side == "sell":
            sign = -1
        else:
            return RiskCheckResult(
                status=RiskValidationStatus.ERROR,
                check_name=self.name,
                message=f"Cannot validate exposure: invalid side {side}",
                details={"side": side},
                is_critical=self.is_critical
            )
        
        order_exposure = notional_value / portfolio_value
        new_gross_exposure = current_gross_exposure + order_exposure
        new_net_exposure = current_net_exposure + (sign * order_exposure)
        new_asset_exposure = current_asset_exposure + (sign * order_exposure)
        
        # Check against maximum gross exposure
        if new_gross_exposure > self.max_gross_exposure:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Order would exceed maximum gross exposure: "
                        f"{new_gross_exposure:.2f}x > {self.max_gross_exposure:.2f}x"),
                details={
                    "current_gross_exposure": current_gross_exposure,
                    "order_exposure": order_exposure,
                    "new_gross_exposure": new_gross_exposure,
                    "max_gross_exposure": self.max_gross_exposure
                },
                is_critical=self.is_critical
            )
        
        # Check against maximum net exposure
        if abs(new_net_exposure) > self.max_net_exposure:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Order would exceed maximum net exposure: "
                        f"{abs(new_net_exposure):.2f}x > {self.max_net_exposure:.2f}x"),
                details={
                    "current_net_exposure": current_net_exposure,
                    "order_exposure": order_exposure * sign,
                    "new_net_exposure": new_net_exposure,
                    "max_net_exposure": self.max_net_exposure
                },
                is_critical=self.is_critical
            )
        
        # Check against maximum single asset exposure
        if abs(new_asset_exposure) > self.max_single_asset_exposure:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Order would exceed maximum exposure for {symbol}: "
                        f"{abs(new_asset_exposure):.2%} > {self.max_single_asset_exposure:.2%}"),
                details={
                    "symbol": symbol,
                    "current_asset_exposure": current_asset_exposure,
                    "order_exposure": order_exposure * sign,
                    "new_asset_exposure": new_asset_exposure,
                    "max_single_asset_exposure": self.max_single_asset_exposure
                },
                is_critical=self.is_critical
            )
        
        return RiskCheckResult(
            status=RiskValidationStatus.PASSED,
            check_name=self.name,
            message="Exposure limits not exceeded",
            details={
                "new_gross_exposure": new_gross_exposure,
                "max_gross_exposure": self.max_gross_exposure,
                "new_net_exposure": new_net_exposure,
                "max_net_exposure": self.max_net_exposure,
                "new_asset_exposure": new_asset_exposure,
                "max_single_asset_exposure": self.max_single_asset_exposure
            },
            is_critical=self.is_critical
        )


class VolumePercentCheck(PreTradeRiskCheck):
    """
    Check if the order size is within acceptable limits as a percentage of market volume.
    """
    
    def __init__(self, 
               name: str = "volume_percent_check",
               description: Optional[str] = None,
               is_critical: bool = True,
               max_volume_percent: float = 0.1,  # 10% of market volume
               lookback_periods: int = 24,  # Number of periods to look back for volume
               volume_period: str = "1h"):  # Period for volume calculation
        """
        Initialize a volume percent check.
        
        Args:
            name: Unique identifier for this check
            description: Optional human-readable description
            is_critical: Whether this check is critical
            max_volume_percent: Maximum order size as percentage of market volume
            lookback_periods: Number of periods to look back for volume
            volume_period: Period for volume calculation (e.g., "1h", "15m")
        """
        super().__init__(name, description, is_critical)
        self.max_volume_percent = max_volume_percent
        self.lookback_periods = lookback_periods
        self.volume_period = volume_period
    
    def check(self, 
             order: Dict[str, Any], 
             portfolio_state: Dict[str, Any],
             market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Check if the order size is within acceptable limits as a percentage of market volume.
        
        Args:
            order: Order details
            portfolio_state: Portfolio state
            market_data: Market data
            
        Returns:
            Result of the volume percent check
        """
        symbol = order.get("symbol")
        size = order.get("size", 0.0)
        
        # Get average volume from market data
        avg_volume = None
        if market_data:
            # Try different ways market data might provide volume information
            if "average_volume" in market_data:
                avg_volume = market_data.get("average_volume")
            elif "volume" in market_data:
                avg_volume = market_data.get("volume")
            elif f"average_{self.volume_period}_volume" in market_data:
                avg_volume = market_data.get(f"average_{self.volume_period}_volume")
            elif f"{self.volume_period}_volume" in market_data:
                avg_volume = market_data.get(f"{self.volume_period}_volume")
        
        if avg_volume is None or avg_volume <= 0:
            return RiskCheckResult(
                status=RiskValidationStatus.WARNING,
                check_name=self.name,
                message=f"Cannot validate volume percent: no volume data available",
                details={"symbol": symbol, "size": size},
                is_critical=False  # Downgrade to warning since we can't validate
            )
        
        # Calculate percentage of average volume
        volume_percent = size / avg_volume
        
        # Check against maximum volume percentage
        if volume_percent > self.max_volume_percent:
            return RiskCheckResult(
                status=RiskValidationStatus.FAILED,
                check_name=self.name,
                message=(f"Order size exceeds maximum percentage of market volume: "
                        f"{volume_percent:.2%} > {self.max_volume_percent:.2%}"),
                details={
                    "symbol": symbol,
                    "size": size,
                    "avg_volume": avg_volume,
                    "volume_percent": volume_percent,
                    "max_volume_percent": self.max_volume_percent,
                    "volume_period": self.volume_period
                },
                is_critical=self.is_critical
            )
        
        return RiskCheckResult(
            status=RiskValidationStatus.PASSED,
            check_name=self.name,
            message="Order size within acceptable percentage of market volume",
            details={
                "symbol": symbol,
                "size": size,
                "avg_volume": avg_volume,
                "volume_percent": volume_percent,
                "max_volume_percent": self.max_volume_percent,
                "volume_period": self.volume_period
            },
            is_critical=self.is_critical
        )


#
# Post-Trade Risk Analysis Implementations
#

class SlippageCheck(PostTradeRiskAnalysis):
    """
    Analyze execution slippage to identify excessive price impact.
    """
    
    def __init__(self, 
               name: str = "slippage_check",
               description: Optional[str] = None,
               warning_threshold: float = 0.005,  # 0.5% warning
               critical_threshold: float = 0.02):  # 2% critical
        """
        Initialize a slippage check.
        
        Args:
            name: Unique identifier for this analysis
            description: Optional human-readable description
            warning_threshold: Slippage percentage for warning level
            critical_threshold: Slippage percentage for critical level
        """
        super().__init__(name, description)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
    
    def analyze(self, 
               order: Dict[str, Any],
               execution_details: Dict[str, Any],
               portfolio_state: Dict[str, Any],
               market_data: Dict[str, Any]) -> RiskCheckResult:
        """
        Analyze execution slippage.
        
        Args:
            order: Original order details
            execution_details: Details of how the order was executed
            portfolio_state: Current state of the portfolio
            market_data: Relevant market data for risk calculations
            
        Returns:
            Result of the slippage analysis
        """
        symbol = order.get("symbol")
        side = order.get("side", "").lower()
        intended_price = order.get("price")
        
        # If no intended price, try to use price at time of order
        if intended_price is None and "price_at_order_time" in execution_details:
            intended_price = execution_details.get("price_at_order_time")
        
        # If still no price, can't calculate slippage
        if intended_price is None or intended_price <= 0:
            return RiskCheckResult(
                status=RiskValidationStatus.WARNING,
                check_name=self.name,
                message=f"Cannot calculate slippage: no intended price available",
                details={"symbol": symbol, "side": side},
                is_critical=False
            )
        
        # Get executed price
        executed_price = execution_details.get("executed_price")
        if executed_price is None or executed_price <= 0:
            return RiskCheckResult(
                status=RiskValidationStatus.WARNING,
                check_name=self.name,
                message=f"Cannot calculate slippage: no executed price available",
                details={"symbol": symbol, "side": side},
                is_critical=False
            )
        
        # Calculate slippage (adjusted for side)
        if side == "buy":
            slippage_percent = (executed_price - intended_price) / intended_price
        elif side == "sell":
            slippage_percent = (intended_price - executed_price) / intended_price
        else:
            return RiskCheckResult(
                status=RiskValidationStatus.WARNING,
                check_name=self.name,
                message=f"Cannot calculate slippage: invalid side {side}",
                details={"side": side},
                is_critical=False
            )
        
        # Analyze slippage level
        if slippage_percent > self.critical_threshold:
            status = RiskValidationStatus.FAILED
            message = (f"Critical slippage detected: {slippage_percent:.2%} > "
                      f"{self.critical_threshold:.2%}")
        elif slippage_percent > self.warning_threshold:
            status = RiskValidationStatus.WARNING
            message = (f"Warning: slippage exceeds threshold: {slippage_percent:.2%} > "
                      f"{self.warning_threshold:.2%}")
        else:
            status = RiskValidationStatus.PASSED
            message = f"Slippage within acceptable limits: {slippage_percent:.2%}"
        
        return RiskCheckResult(
            status=status,
            check_name=self.name,
            message=message,
            details={
                "symbol": symbol,
                "side": side,
                "intended_price": intended_price,
                "executed_price": executed_price,
                "slippage_percent": slippage_percent,
                "warning_threshold": self.warning_threshold,
                "critical_threshold": self.critical_threshold
            },
            is_critical=False
        )


# Public API
__all__ = [
    'PreTradeRiskCheck',
    'PostTradeRiskAnalysis',
    'PositionSizeCheck',
    'MaxDrawdownCheck',
    'ExposureCheck',
    'VolumePercentCheck',
    'SlippageCheck'
] 