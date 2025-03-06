"""
Circuit Breaker Module

This module provides circuit breaker functionality for trading system execution.
Circuit breakers automatically pause or stop trading when predefined conditions
are met, protecting the system from extreme market conditions or execution problems.
"""

import time
import logging
import statistics
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

# Initialize logger
logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    """Possible states for a circuit breaker."""
    NORMAL = "normal"  # Circuit breaker is inactive, trading allowed
    WARNING = "warning"  # Approaching threshold, trading still allowed but with caution
    TRIGGERED = "triggered"  # Circuit breaker is triggered, trading paused
    RECOVERY = "recovery"  # Recovering from triggered state, limited trading allowed
    DISABLED = "disabled"  # Circuit breaker is disabled, not monitoring

@dataclass
class CircuitBreakerEvent:
    """Event generated when circuit breaker state changes."""
    breaker_id: str
    timestamp: float
    prev_state: CircuitBreakerState
    new_state: CircuitBreakerState
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    recovery_time: Optional[float] = None

@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""
    warning_threshold: float
    trigger_threshold: float
    recovery_threshold: Optional[float] = None
    min_data_points: int = 10
    cooldown_period_seconds: float = 300.0  # 5 minutes default
    auto_recovery: bool = True
    warning_callback: Optional[Callable[[CircuitBreakerEvent], None]] = None
    trigger_callback: Optional[Callable[[CircuitBreakerEvent], None]] = None
    recovery_callback: Optional[Callable[[CircuitBreakerEvent], None]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    custom_params: Dict[str, Any] = field(default_factory=dict)

class CircuitBreaker(ABC):
    """
    Base class for circuit breakers that can pause trading activity
    when market conditions exceed safety thresholds.
    
    Circuit breakers monitor specific metrics (e.g. volatility, drawdown)
    and automatically change state when thresholds are exceeded.
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize the circuit breaker with configuration parameters.
        
        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self.state = CircuitBreakerState.NORMAL if config.enabled else CircuitBreakerState.DISABLED
        self.id = f"{self.__class__.__name__}_{id(self)}"
        self.name = config.name or self.__class__.__name__
        self.description = config.description or "Generic circuit breaker"
        self.last_triggered_time = None
        self.last_state_change_time = time.time()
        self.event_history: List[CircuitBreakerEvent] = []
        self.value_history: List[float] = []
        self.max_history_length = 1000
        
        # Record initialization
        logger.info(f"Circuit breaker {self.name} ({self.id}) initialized in {self.state.name} state")
    
    @abstractmethod
    def calculate_current_value(self) -> float:
        """
        Calculate the current value of the metric being monitored.
        
        This method must be implemented by subclasses to provide the
        specific calculation for each type of circuit breaker.
        
        Returns:
            Current value of the monitored metric
        """
        pass
    
    def update(self) -> Optional[CircuitBreakerEvent]:
        """
        Update the circuit breaker state based on current conditions.
        
        This method should be called regularly to check if the circuit
        breaker should change state.
        
        Returns:
            CircuitBreakerEvent if state changed, None otherwise
        """
        if self.state == CircuitBreakerState.DISABLED:
            return None
        
        # Get current value of monitored metric
        try:
            current_value = self.calculate_current_value()
        except Exception as e:
            logger.error(f"Error calculating value for circuit breaker {self.name}: {e}")
            return None
        
        # Add to history
        self.value_history.append(current_value)
        if len(self.value_history) > self.max_history_length:
            self.value_history.pop(0)
        
        # Check for state changes
        prev_state = self.state
        event = None
        
        # Handle transitions based on current state
        if self.state == CircuitBreakerState.NORMAL:
            # Check if we should trigger or warn
            if current_value >= self.config.trigger_threshold:
                self.state = CircuitBreakerState.TRIGGERED
                self.last_triggered_time = time.time()
                reason = f"Value {current_value:.6f} exceeded trigger threshold {self.config.trigger_threshold:.6f}"
                event = self._create_state_change_event(prev_state, reason)
                
                # Call the trigger callback if provided
                if self.config.trigger_callback:
                    try:
                        self.config.trigger_callback(event)
                    except Exception as e:
                        logger.error(f"Error in trigger callback for {self.name}: {e}")
            
            elif current_value >= self.config.warning_threshold:
                self.state = CircuitBreakerState.WARNING
                reason = f"Value {current_value:.6f} exceeded warning threshold {self.config.warning_threshold:.6f}"
                event = self._create_state_change_event(prev_state, reason)
                
                # Call the warning callback if provided
                if self.config.warning_callback:
                    try:
                        self.config.warning_callback(event)
                    except Exception as e:
                        logger.error(f"Error in warning callback for {self.name}: {e}")
        
        elif self.state == CircuitBreakerState.WARNING:
            # Check if we should trigger or return to normal
            if current_value >= self.config.trigger_threshold:
                self.state = CircuitBreakerState.TRIGGERED
                self.last_triggered_time = time.time()
                reason = f"Value {current_value:.6f} exceeded trigger threshold {self.config.trigger_threshold:.6f}"
                event = self._create_state_change_event(prev_state, reason)
                
                # Call the trigger callback if provided
                if self.config.trigger_callback:
                    try:
                        self.config.trigger_callback(event)
                    except Exception as e:
                        logger.error(f"Error in trigger callback for {self.name}: {e}")
            
            elif current_value < self.config.warning_threshold:
                self.state = CircuitBreakerState.NORMAL
                reason = f"Value {current_value:.6f} returned below warning threshold {self.config.warning_threshold:.6f}"
                event = self._create_state_change_event(prev_state, reason)
        
        elif self.state == CircuitBreakerState.TRIGGERED:
            # Check if we should enter recovery
            recovery_threshold = self.config.recovery_threshold or self.config.warning_threshold
            
            if current_value < recovery_threshold:
                # Check cooldown period
                elapsed_since_trigger = time.time() - self.last_triggered_time
                if elapsed_since_trigger >= self.config.cooldown_period_seconds:
                    if self.config.auto_recovery:
                        self.state = CircuitBreakerState.RECOVERY
                        reason = f"Value {current_value:.6f} below recovery threshold {recovery_threshold:.6f} and cooldown period elapsed"
                        event = self._create_state_change_event(prev_state, reason)
                        
                        # Call the recovery callback if provided
                        if self.config.recovery_callback:
                            try:
                                self.config.recovery_callback(event)
                            except Exception as e:
                                logger.error(f"Error in recovery callback for {self.name}: {e}")
                    else:
                        logger.info(f"Circuit breaker {self.name} would enter recovery, but auto-recovery is disabled")
        
        elif self.state == CircuitBreakerState.RECOVERY:
            # Check if we should return to normal or re-trigger
            if current_value >= self.config.trigger_threshold:
                self.state = CircuitBreakerState.TRIGGERED
                self.last_triggered_time = time.time()
                reason = f"Value {current_value:.6f} exceeded trigger threshold {self.config.trigger_threshold:.6f} during recovery"
                event = self._create_state_change_event(prev_state, reason)
                
                # Call the trigger callback if provided
                if self.config.trigger_callback:
                    try:
                        self.config.trigger_callback(event)
                    except Exception as e:
                        logger.error(f"Error in trigger callback for {self.name}: {e}")
            
            elif current_value < self.config.warning_threshold:
                self.state = CircuitBreakerState.NORMAL
                reason = f"Value {current_value:.6f} returned below warning threshold {self.config.warning_threshold:.6f}"
                event = self._create_state_change_event(prev_state, reason)
        
        # If state changed, log it and add to history
        if event:
            logger.info(f"Circuit breaker {self.name} state changed: {prev_state.name} -> {self.state.name} ({event.reason})")
            self.last_state_change_time = time.time()
            self.event_history.append(event)
            
            # Trim event history if needed
            if len(self.event_history) > self.max_history_length:
                self.event_history.pop(0)
            
            return event
        
        return None
    
    def _create_state_change_event(self, prev_state: CircuitBreakerState, reason: str) -> CircuitBreakerEvent:
        """Create an event for a state change."""
        metrics = self.get_metrics()
        
        event = CircuitBreakerEvent(
            breaker_id=self.id,
            timestamp=time.time(),
            prev_state=prev_state,
            new_state=self.state,
            reason=reason,
            metrics=metrics
        )
        
        # Set recovery time if transitioning to recovery
        if self.state == CircuitBreakerState.RECOVERY:
            event.recovery_time = time.time() + self.config.cooldown_period_seconds
        
        return event
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for this circuit breaker."""
        metrics = {
            "state": self.state.value,
            "current_value": self.value_history[-1] if self.value_history else None,
            "warning_threshold": self.config.warning_threshold,
            "trigger_threshold": self.config.trigger_threshold,
            "recovery_threshold": self.config.recovery_threshold or self.config.warning_threshold,
            "time_since_last_state_change": time.time() - self.last_state_change_time
        }
        
        # Add history-based metrics if we have enough data
        if len(self.value_history) >= self.config.min_data_points:
            metrics.update({
                "mean_value": statistics.mean(self.value_history),
                "max_value": max(self.value_history),
                "min_value": min(self.value_history),
                "std_dev": statistics.stdev(self.value_history) if len(self.value_history) > 1 else 0.0
            })
        
        return metrics
    
    def reset(self) -> None:
        """
        Reset the circuit breaker to normal state.
        
        This can be used to manually clear a triggered circuit breaker.
        """
        if self.state != CircuitBreakerState.NORMAL:
            prev_state = self.state
            self.state = CircuitBreakerState.NORMAL
            event = self._create_state_change_event(prev_state, "Manual reset")
            self.event_history.append(event)
            logger.info(f"Circuit breaker {self.name} manually reset from {prev_state.name} to NORMAL")
    
    def disable(self) -> None:
        """Disable this circuit breaker."""
        if self.state != CircuitBreakerState.DISABLED:
            prev_state = self.state
            self.state = CircuitBreakerState.DISABLED
            event = self._create_state_change_event(prev_state, "Manually disabled")
            self.event_history.append(event)
            logger.info(f"Circuit breaker {self.name} disabled")
    
    def enable(self) -> None:
        """Enable this circuit breaker."""
        if self.state == CircuitBreakerState.DISABLED:
            self.state = CircuitBreakerState.NORMAL
            event = self._create_state_change_event(CircuitBreakerState.DISABLED, "Manually enabled")
            self.event_history.append(event)
            logger.info(f"Circuit breaker {self.name} enabled")
    
    def is_trading_allowed(self) -> bool:
        """
        Check if trading is allowed under the current circuit breaker state.
        
        Returns:
            True if trading is allowed, False otherwise
        """
        return self.state in (CircuitBreakerState.NORMAL, CircuitBreakerState.WARNING)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get detailed status information about this circuit breaker.
        
        Returns:
            Dict with status information
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "trading_allowed": self.is_trading_allowed(),
            "last_update": time.time(),
            "metrics": self.get_metrics(),
            "config": {
                "warning_threshold": self.config.warning_threshold,
                "trigger_threshold": self.config.trigger_threshold,
                "recovery_threshold": self.config.recovery_threshold,
                "cooldown_period_seconds": self.config.cooldown_period_seconds,
                "auto_recovery": self.config.auto_recovery,
                "enabled": self.config.enabled
            },
            "last_event": self.event_history[-1].__dict__ if self.event_history else None
        }


class VolatilityCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker that triggers when market volatility exceeds thresholds.
    
    This circuit breaker monitors recent price volatility and pauses
    trading when volatility becomes extreme.
    """
    
    def __init__(self, 
                 symbol: str,
                 warning_threshold_pct: float,
                 trigger_threshold_pct: float,
                 window_seconds: float = 300.0,  # 5 minutes
                 recovery_threshold_pct: Optional[float] = None,
                 price_history_provider: Any = None,
                 **kwargs):
        """
        Initialize the volatility circuit breaker.
        
        Args:
            symbol: Trading symbol to monitor
            warning_threshold_pct: Volatility percentage for warning state
            trigger_threshold_pct: Volatility percentage for triggered state
            window_seconds: Window for volatility calculation in seconds
            recovery_threshold_pct: Volatility percentage for recovery (defaults to warning threshold)
            price_history_provider: Object that provides price history for volatility calculation
            **kwargs: Additional arguments for base CircuitBreaker
        """
        # Convert percentage thresholds to decimals
        config = CircuitBreakerConfig(
            warning_threshold=warning_threshold_pct / 100.0,
            trigger_threshold=trigger_threshold_pct / 100.0,
            recovery_threshold=recovery_threshold_pct / 100.0 if recovery_threshold_pct else None,
            name=f"Volatility_{symbol}",
            description=f"Monitors {symbol} price volatility over {window_seconds}s window",
            **kwargs
        )
        
        super().__init__(config)
        
        self.symbol = symbol
        self.window_seconds = window_seconds
        self.price_history_provider = price_history_provider
        self.price_history: List[Dict[str, Any]] = []  # [{timestamp, price}, ...]
    
    def add_price(self, timestamp: float, price: float) -> None:
        """
        Add a price point to the volatility calculation.
        
        Args:
            timestamp: Time of the price observation
            price: Price value
        """
        self.price_history.append({"timestamp": timestamp, "price": price})
        
        # Trim old data outside our window
        cutoff_time = time.time() - self.window_seconds
        self.price_history = [p for p in self.price_history if p["timestamp"] >= cutoff_time]
    
    def calculate_current_value(self) -> float:
        """
        Calculate current volatility over the specified window.
        
        Returns:
            Volatility as a decimal (e.g., 0.05 for 5% volatility)
        """
        # Check if we need to fetch prices
        if self.price_history_provider and not self.price_history:
            try:
                # Get historical prices from provider
                current_time = time.time()
                start_time = current_time - self.window_seconds
                
                prices = self.price_history_provider.get_price_history(
                    symbol=self.symbol,
                    start_time=start_time,
                    end_time=current_time
                )
                
                if prices:
                    self.price_history = [{"timestamp": p["timestamp"], "price": p["price"]} for p in prices]
            except Exception as e:
                logger.error(f"Error fetching price history for {self.symbol}: {e}")
        
        # Check if we have enough data
        if len(self.price_history) < self.config.min_data_points:
            raise ValueError(f"Not enough price data for volatility calculation ({len(self.price_history)} < {self.config.min_data_points})")
        
        # Get prices in chronological order
        sorted_prices = sorted(self.price_history, key=lambda x: x["timestamp"])
        prices = [p["price"] for p in sorted_prices]
        
        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        # Calculate volatility as standard deviation of returns
        if not returns:
            return 0.0
        
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        # Convert to annualized volatility
        # Assuming our window represents a fraction of a year
        # and returns are approximately normally distributed
        seconds_per_year = 365 * 24 * 60 * 60
        annualization_factor = (seconds_per_year / self.window_seconds) ** 0.5
        volatility = std_dev * annualization_factor
        
        return volatility


class DrawdownCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker that triggers when portfolio drawdown exceeds thresholds.
    
    This circuit breaker monitors the current drawdown from peak portfolio value
    and pauses trading when drawdown becomes excessive.
    """
    
    def __init__(self,
                 portfolio_provider: Any,
                 warning_threshold_pct: float,
                 trigger_threshold_pct: float,
                 recovery_threshold_pct: Optional[float] = None,
                 lookback_days: int = 30,
                 **kwargs):
        """
        Initialize the drawdown circuit breaker.
        
        Args:
            portfolio_provider: Object that provides portfolio value information
            warning_threshold_pct: Drawdown percentage for warning state
            trigger_threshold_pct: Drawdown percentage for triggered state
            recovery_threshold_pct: Drawdown percentage for recovery (defaults to warning threshold)
            lookback_days: Days to look back for peak portfolio value
            **kwargs: Additional arguments for base CircuitBreaker
        """
        # Convert percentage thresholds to decimals
        config = CircuitBreakerConfig(
            warning_threshold=warning_threshold_pct / 100.0,
            trigger_threshold=trigger_threshold_pct / 100.0,
            recovery_threshold=recovery_threshold_pct / 100.0 if recovery_threshold_pct else None,
            name="Portfolio_Drawdown",
            description=f"Monitors portfolio drawdown over {lookback_days} days",
            **kwargs
        )
        
        super().__init__(config)
        
        self.portfolio_provider = portfolio_provider
        self.lookback_days = lookback_days
        self.peak_value = 0.0
        self.current_value = 0.0
        self.last_update_time = 0.0
    
    def update_portfolio_value(self, value: float, timestamp: Optional[float] = None) -> None:
        """
        Update the current portfolio value.
        
        Args:
            value: Current portfolio value
            timestamp: Time of the value update (default: current time)
        """
        self.current_value = value
        self.last_update_time = timestamp or time.time()
        
        # Update peak value if needed
        if value > self.peak_value:
            self.peak_value = value
    
    def calculate_current_value(self) -> float:
        """
        Calculate current drawdown from peak.
        
        Returns:
            Drawdown as a decimal (e.g., 0.05 for 5% drawdown)
        """
        # Check if we need to fetch portfolio value
        if self.portfolio_provider and (time.time() - self.last_update_time > 60):  # Refresh if older than 60 seconds
            try:
                value = self.portfolio_provider.get_current_portfolio_value()
                if value:
                    self.update_portfolio_value(value)
            except Exception as e:
                logger.error(f"Error fetching portfolio value: {e}")
        
        # If we have no value data, we can't calculate drawdown
        if self.current_value <= 0 or self.peak_value <= 0:
            raise ValueError("No valid portfolio value data available")
        
        # Calculate drawdown as percentage from peak
        if self.current_value >= self.peak_value:
            return 0.0  # No drawdown
        
        drawdown = (self.peak_value - self.current_value) / self.peak_value
        return drawdown


class SlippageCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker that triggers when execution slippage exceeds thresholds.
    
    This circuit breaker monitors the average slippage of recent trades
    and pauses trading when slippage becomes excessive.
    """
    
    def __init__(self,
                 warning_threshold_bps: float,
                 trigger_threshold_bps: float,
                 recovery_threshold_bps: Optional[float] = None,
                 min_trades: int = 5,
                 window_seconds: float = 1800.0,  # 30 minutes
                 **kwargs):
        """
        Initialize the slippage circuit breaker.
        
        Args:
            warning_threshold_bps: Slippage in basis points for warning state
            trigger_threshold_bps: Slippage in basis points for triggered state
            recovery_threshold_bps: Slippage in basis points for recovery (defaults to warning threshold)
            min_trades: Minimum number of trades needed for calculation
            window_seconds: Time window for slippage calculation
            **kwargs: Additional arguments for base CircuitBreaker
        """
        # Convert basis point thresholds to decimals
        config = CircuitBreakerConfig(
            warning_threshold=warning_threshold_bps / 10000.0,
            trigger_threshold=trigger_threshold_bps / 10000.0,
            recovery_threshold=recovery_threshold_bps / 10000.0 if recovery_threshold_bps else None,
            min_data_points=min_trades,
            name="Execution_Slippage",
            description=f"Monitors trade execution slippage over {window_seconds}s window",
            **kwargs
        )
        
        super().__init__(config)
        
        self.window_seconds = window_seconds
        self.trades: List[Dict[str, Any]] = []  # Trade records with slippage information
        self.min_trades = min_trades
    
    def add_trade(self, 
                  symbol: str, 
                  side: str, 
                  expected_price: float, 
                  actual_price: float, 
                  size: float,
                  timestamp: Optional[float] = None) -> None:
        """
        Add a trade result for slippage monitoring.
        
        Args:
            symbol: Trading symbol
            side: Trade side (buy/sell)
            expected_price: Expected execution price
            actual_price: Actual execution price
            size: Trade size
            timestamp: Time of trade (default: current time)
        """
        # Calculate slippage percentage (positive means unfavorable to trader)
        slippage_pct = 0.0
        if side.lower() == "buy":
            slippage_pct = (actual_price - expected_price) / expected_price
        else:  # sell
            slippage_pct = (expected_price - actual_price) / expected_price
        
        trade = {
            "symbol": symbol,
            "side": side,
            "expected_price": expected_price,
            "actual_price": actual_price,
            "size": size,
            "slippage_pct": slippage_pct,
            "timestamp": timestamp or time.time()
        }
        
        self.trades.append(trade)
        
        # Trim old trades outside our window
        cutoff_time = time.time() - self.window_seconds
        self.trades = [t for t in self.trades if t["timestamp"] >= cutoff_time]
    
    def calculate_current_value(self) -> float:
        """
        Calculate average slippage over the specified window.
        
        Returns:
            Average slippage as a decimal (e.g., 0.0015 for 15 basis points)
        """
        # Check if we have enough trades
        if len(self.trades) < self.min_trades:
            raise ValueError(f"Not enough trades for slippage calculation ({len(self.trades)} < {self.min_trades})")
        
        # Calculate volume-weighted average slippage
        total_weighted_slippage = 0.0
        total_size = 0.0
        
        for trade in self.trades:
            trade_size = trade["size"]
            total_weighted_slippage += trade["slippage_pct"] * trade_size
            total_size += trade_size
        
        if total_size <= 0:
            return 0.0
        
        average_slippage = total_weighted_slippage / total_size
        return average_slippage
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for this circuit breaker."""
        # Get base metrics
        metrics = super().get_metrics()
        
        # Add slippage-specific metrics
        if self.trades:
            slippage_values = [t["slippage_pct"] for t in self.trades]
            
            metrics.update({
                "trade_count": len(self.trades),
                "worst_slippage": max(slippage_values),
                "best_slippage": min(slippage_values),
                "total_volume": sum(t["size"] for t in self.trades),
                "recent_trades": self.trades[-5:]  # Last 5 trades
            })
        
        return metrics 