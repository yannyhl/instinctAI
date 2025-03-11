"""
Circuit Breakers Module
----------------------
This module provides circuit breaker implementations to automatically stop trading
when certain risk thresholds are exceeded. Circuit breakers help protect the system
during extreme market conditions or when the trading system behaves unexpectedly.

Key components:
1. Volatility circuit breakers
2. Drawdown circuit breakers
3. Slippage circuit breakers
4. Volume circuit breakers
5. Trading frequency circuit breakers
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Callable
import logging
from datetime import datetime, timedelta
import time
from enum import Enum

# Configure logger
logger = logging.getLogger(__name__)

class CircuitBreakerStatus(Enum):
    """Enum representing the status of a circuit breaker."""
    NORMAL = "normal"          # Normal operation, no risk threshold breached
    WARNING = "warning"        # Approaching risk threshold, not yet triggered
    TRIGGERED = "triggered"    # Circuit breaker has been triggered
    COOLING = "cooling"        # In cooling period after being triggered
    DISABLED = "disabled"      # Circuit breaker is disabled


class CircuitBreakerBase:
    """
    Base class for all circuit breakers.
    
    Circuit breakers are designed to automatically stop trading when
    certain risk thresholds are exceeded. This base class provides common
    functionality for all circuit breaker implementations.
    
    Parameters:
    -----------
    name : str
        Name of the circuit breaker
    cooling_period : int
        Period (in seconds) before the circuit breaker can be reset after triggering
    auto_reset : bool
        Whether to automatically reset the circuit breaker after the cooling period
    enabled : bool
        Whether the circuit breaker is enabled
    warning_threshold : float
        Threshold at which to issue a warning (as a percentage of the trigger threshold)
    """
    
    def __init__(
        self,
        name: str,
        cooling_period: int = 300,  # 5 minutes by default
        auto_reset: bool = False,
        enabled: bool = True,
        warning_threshold: float = 0.8
    ):
        """Initialize the circuit breaker."""
        self.name = name
        self.cooling_period = cooling_period
        self.auto_reset = auto_reset
        self.enabled = enabled
        self.warning_threshold = warning_threshold
        
        # Internal state
        self.status = CircuitBreakerStatus.NORMAL if enabled else CircuitBreakerStatus.DISABLED
        self.trigger_time = None
        self.trigger_value = None
        self.warning_time = None
        self.warning_value = None
        
        # Notification hooks
        self.on_trigger = None
        self.on_warning = None
        self.on_reset = None
        
    def check(self, value: float, threshold: float) -> CircuitBreakerStatus:
        """
        Check if the circuit breaker should be triggered.
        
        Parameters:
        -----------
        value : float
            Current value to check against the threshold
        threshold : float
            Threshold value for triggering the circuit breaker
            
        Returns:
        --------
        CircuitBreakerStatus
            Current status of the circuit breaker
        """
        # Skip checks if disabled
        if not self.enabled:
            return CircuitBreakerStatus.DISABLED
        
        # Check if we're in a cooling period
        if self.status == CircuitBreakerStatus.TRIGGERED or self.status == CircuitBreakerStatus.COOLING:
            if self.auto_reset and self.trigger_time:
                # Check if cooling period has elapsed
                elapsed_time = time.time() - self.trigger_time
                if elapsed_time >= self.cooling_period:
                    self._reset()
                    logger.info(f"Circuit breaker {self.name} automatically reset after cooling period")
                else:
                    self.status = CircuitBreakerStatus.COOLING
                    return self.status
            else:
                return self.status
        
        # Check if we should trigger
        if value >= threshold:
            self._trigger(value)
            logger.warning(f"Circuit breaker {self.name} TRIGGERED with value {value:.4f} (threshold: {threshold:.4f})")
            return self.status
        
        # Check if we should warn
        if value >= threshold * self.warning_threshold:
            self._warn(value)
            logger.info(f"Circuit breaker {self.name} WARNING with value {value:.4f} (threshold: {threshold:.4f})")
            return self.status
        
        # Normal operation
        self.status = CircuitBreakerStatus.NORMAL
        return self.status
    
    def _trigger(self, value: float):
        """Trigger the circuit breaker."""
        self.status = CircuitBreakerStatus.TRIGGERED
        self.trigger_time = time.time()
        self.trigger_value = value
        
        # Call trigger hook if provided
        if self.on_trigger and callable(self.on_trigger):
            self.on_trigger(self)
    
    def _warn(self, value: float):
        """Issue a warning."""
        self.status = CircuitBreakerStatus.WARNING
        self.warning_time = time.time()
        self.warning_value = value
        
        # Call warning hook if provided
        if self.on_warning and callable(self.on_warning):
            self.on_warning(self)
    
    def _reset(self):
        """Reset the circuit breaker."""
        previous_status = self.status
        self.status = CircuitBreakerStatus.NORMAL if self.enabled else CircuitBreakerStatus.DISABLED
        self.trigger_time = None
        self.trigger_value = None
        
        # Call reset hook if provided
        if previous_status != CircuitBreakerStatus.NORMAL and self.on_reset and callable(self.on_reset):
            self.on_reset(self)
    
    def reset(self):
        """Manually reset the circuit breaker."""
        if self.status == CircuitBreakerStatus.TRIGGERED or self.status == CircuitBreakerStatus.COOLING:
            elapsed_time = time.time() - self.trigger_time if self.trigger_time else float('inf')
            if elapsed_time < self.cooling_period:
                logger.warning(f"Forcing reset of circuit breaker {self.name} before cooling period has elapsed")
        
        self._reset()
        logger.info(f"Circuit breaker {self.name} manually reset")
    
    def disable(self):
        """Disable the circuit breaker."""
        self.enabled = False
        self.status = CircuitBreakerStatus.DISABLED
        logger.info(f"Circuit breaker {self.name} disabled")
    
    def enable(self):
        """Enable the circuit breaker."""
        self.enabled = True
        self.status = CircuitBreakerStatus.NORMAL
        logger.info(f"Circuit breaker {self.name} enabled")
    
    def get_status(self) -> Dict:
        """
        Get the current status of the circuit breaker.
        
        Returns:
        --------
        Dict
            Dictionary with circuit breaker status information
        """
        return {
            'name': self.name,
            'status': self.status.value,
            'enabled': self.enabled,
            'trigger_time': self.trigger_time,
            'trigger_value': self.trigger_value,
            'warning_time': self.warning_time,
            'warning_value': self.warning_value,
            'cooling_period': self.cooling_period,
            'auto_reset': self.auto_reset,
            'warning_threshold': self.warning_threshold
        }
    
    def __str__(self) -> str:
        """Return a string representation of the circuit breaker."""
        return f"CircuitBreaker(name={self.name}, status={self.status.value}, enabled={self.enabled})"


class VolatilityCircuitBreaker(CircuitBreakerBase):
    """
    Circuit breaker that triggers when volatility exceeds a threshold.
    
    Parameters:
    -----------
    volatility_window : int
        Window size for calculating volatility
    volatility_threshold : float
        Volatility threshold for triggering the circuit breaker
    min_periods : int
        Minimum periods for calculating volatility
    **kwargs : 
        Additional parameters for CircuitBreakerBase
    """
    
    def __init__(
        self,
        volatility_window: int = 20,
        volatility_threshold: float = 0.03,  # 3% volatility
        min_periods: int = 5,
        **kwargs
    ):
        """Initialize the volatility circuit breaker."""
        super().__init__(name="volatility_circuit_breaker", **kwargs)
        self.volatility_window = volatility_window
        self.volatility_threshold = volatility_threshold
        self.min_periods = min_periods
        
        # Historical data
        self.returns_history = []
    
    def update(self, returns: float) -> CircuitBreakerStatus:
        """
        Update the circuit breaker with new returns data.
        
        Parameters:
        -----------
        returns : float
            New returns value
            
        Returns:
        --------
        CircuitBreakerStatus
            Current status of the circuit breaker
        """
        # Skip if disabled
        if not self.enabled:
            return CircuitBreakerStatus.DISABLED
        
        # Add to history
        self.returns_history.append(returns)
        
        # Keep only the most recent data
        self.returns_history = self.returns_history[-self.volatility_window*2:]
        
        # Check if we have enough data
        if len(self.returns_history) < self.min_periods:
            return CircuitBreakerStatus.NORMAL
        
        # Calculate volatility
        volatility = np.std(self.returns_history[-self.volatility_window:])
        
        # Check against threshold
        return self.check(volatility, self.volatility_threshold)
    
    def get_status(self) -> Dict:
        """Get the current status of the circuit breaker."""
        status = super().get_status()
        status.update({
            'volatility_window': self.volatility_window,
            'volatility_threshold': self.volatility_threshold,
            'current_volatility': np.std(self.returns_history[-self.volatility_window:]) if len(self.returns_history) >= self.min_periods else None,
            'returns_count': len(self.returns_history)
        })
        return status


class DrawdownCircuitBreaker(CircuitBreakerBase):
    """
    Circuit breaker that triggers when drawdown exceeds a threshold.
    
    Parameters:
    -----------
    drawdown_threshold : float
        Drawdown threshold for triggering the circuit breaker (as a positive value)
    **kwargs : 
        Additional parameters for CircuitBreakerBase
    """
    
    def __init__(
        self,
        drawdown_threshold: float = 0.05,  # 5% drawdown
        **kwargs
    ):
        """Initialize the drawdown circuit breaker."""
        super().__init__(name="drawdown_circuit_breaker", **kwargs)
        self.drawdown_threshold = drawdown_threshold
        
        # Historical data
        self.equity_peak = None
        self.current_equity = None
        self.current_drawdown = 0.0
    
    def update(self, equity: float) -> CircuitBreakerStatus:
        """
        Update the circuit breaker with new equity value.
        
        Parameters:
        -----------
        equity : float
            Current equity value
            
        Returns:
        --------
        CircuitBreakerStatus
            Current status of the circuit breaker
        """
        # Skip if disabled
        if not self.enabled:
            return CircuitBreakerStatus.DISABLED
        
        # Initialize peak if not set
        if self.equity_peak is None:
            self.equity_peak = equity
        
        # Update current equity
        self.current_equity = equity
        
        # Update peak if necessary
        self.equity_peak = max(self.equity_peak, equity)
        
        # Calculate drawdown (as a positive value)
        self.current_drawdown = 1.0 - (equity / self.equity_peak) if self.equity_peak > 0 else 0.0
        
        # Check against threshold
        return self.check(self.current_drawdown, self.drawdown_threshold)
    
    def reset_peak(self, new_peak: Optional[float] = None):
        """
        Reset the equity peak.
        
        Parameters:
        -----------
        new_peak : float, optional
            New peak value (if None, uses current equity)
        """
        self.equity_peak = new_peak if new_peak is not None else self.current_equity
        self.current_drawdown = 0.0 if self.equity_peak is None or self.current_equity is None else 1.0 - (self.current_equity / self.equity_peak)
        logger.info(f"Drawdown circuit breaker peak reset to {self.equity_peak}")
    
    def get_status(self) -> Dict:
        """Get the current status of the circuit breaker."""
        status = super().get_status()
        status.update({
            'drawdown_threshold': self.drawdown_threshold,
            'equity_peak': self.equity_peak,
            'current_equity': self.current_equity,
            'current_drawdown': self.current_drawdown
        })
        return status


class SlippageCircuitBreaker(CircuitBreakerBase):
    """
    Circuit breaker that triggers when slippage exceeds a threshold.
    
    Parameters:
    -----------
    slippage_threshold : float
        Slippage threshold for triggering the circuit breaker (as a percentage)
    slippage_window : int
        Number of trades to consider for average slippage calculation
    **kwargs : 
        Additional parameters for CircuitBreakerBase
    """
    
    def __init__(
        self,
        slippage_threshold: float = 0.003,  # 0.3% slippage
        slippage_window: int = 10,
        **kwargs
    ):
        """Initialize the slippage circuit breaker."""
        super().__init__(name="slippage_circuit_breaker", **kwargs)
        self.slippage_threshold = slippage_threshold
        self.slippage_window = slippage_window
        
        # Historical data
        self.slippage_history = []
        self.total_trades = 0
    
    def update(self, expected_price: float, executed_price: float, side: str) -> CircuitBreakerStatus:
        """
        Update the circuit breaker with new trade information.
        
        Parameters:
        -----------
        expected_price : float
            Expected execution price
        executed_price : float
            Actual execution price
        side : str
            Trade side ('buy' or 'sell')
            
        Returns:
        --------
        CircuitBreakerStatus
            Current status of the circuit breaker
        """
        # Skip if disabled
        if not self.enabled:
            return CircuitBreakerStatus.DISABLED
        
        # Skip if prices are not positive
        if expected_price <= 0 or executed_price <= 0:
            return self.status
        
        # Calculate slippage (as a percentage)
        if side.lower() == 'buy':
            # For buys, slippage is when executed price is higher
            slippage = (executed_price - expected_price) / expected_price
        else:
            # For sells, slippage is when executed price is lower
            slippage = (expected_price - executed_price) / expected_price
        
        # Ensure slippage is positive
        slippage = max(0, slippage)
        
        # Add to history
        self.slippage_history.append(slippage)
        self.total_trades += 1
        
        # Keep only the most recent data
        self.slippage_history = self.slippage_history[-self.slippage_window:]
        
        # Calculate average slippage
        avg_slippage = np.mean(self.slippage_history)
        
        # Check against threshold
        return self.check(avg_slippage, self.slippage_threshold)
    
    def get_status(self) -> Dict:
        """Get the current status of the circuit breaker."""
        status = super().get_status()
        status.update({
            'slippage_threshold': self.slippage_threshold,
            'slippage_window': self.slippage_window,
            'current_avg_slippage': np.mean(self.slippage_history) if self.slippage_history else 0.0,
            'total_trades': self.total_trades,
            'recent_slippage': self.slippage_history
        })
        return status


class VolumeCircuitBreaker(CircuitBreakerBase):
    """
    Circuit breaker that triggers when volume ratio exceeds a threshold.
    
    This circuit breaker monitors the ratio of trading volume to normal volume
    and triggers when the ratio exceeds a threshold. This is useful for detecting
    abnormal market conditions or liquidity issues.
    
    Parameters:
    -----------
    volume_window : int
        Window size for calculating normal volume
    volume_ratio_threshold : float
        Volume ratio threshold for triggering the circuit breaker
    min_periods : int
        Minimum periods for calculating normal volume
    use_relative_ratio : bool
        Whether to use relative ratio (current volume / normal volume) or 
        absolute ratio (current volume / max volume)
    **kwargs : 
        Additional parameters for CircuitBreakerBase
    """
    
    def __init__(
        self,
        volume_window: int = 20,
        volume_ratio_threshold: float = 5.0,  # 5x normal volume
        min_periods: int = 10,
        use_relative_ratio: bool = True,
        **kwargs
    ):
        """Initialize the volume circuit breaker."""
        super().__init__(name="volume_circuit_breaker", **kwargs)
        self.volume_window = volume_window
        self.volume_ratio_threshold = volume_ratio_threshold
        self.min_periods = min_periods
        self.use_relative_ratio = use_relative_ratio
        
        # Historical data
        self.volume_history = []
        self.current_volume = None
        self.current_ratio = None
    
    def update(self, volume: float) -> CircuitBreakerStatus:
        """
        Update the circuit breaker with new volume data.
        
        Parameters:
        -----------
        volume : float
            Current trading volume
            
        Returns:
        --------
        CircuitBreakerStatus
            Current status of the circuit breaker
        """
        # Skip if disabled
        if not self.enabled:
            return CircuitBreakerStatus.DISABLED
        
        # Skip if volume is not positive
        if volume <= 0:
            return self.status
        
        # Add to history
        self.volume_history.append(volume)
        self.current_volume = volume
        
        # Keep only the most recent data
        self.volume_history = self.volume_history[-self.volume_window*2:]
        
        # Check if we have enough data
        if len(self.volume_history) < self.min_periods:
            return CircuitBreakerStatus.NORMAL
        
        # Calculate normal volume and ratio
        normal_volume = np.median(self.volume_history[-self.volume_window:])
        
        if self.use_relative_ratio:
            # Relative ratio: current volume / normal volume
            ratio = volume / normal_volume if normal_volume > 0 else float('inf')
        else:
            # Absolute ratio: current volume / max volume
            max_volume = max(self.volume_history[-self.volume_window:])
            ratio = volume / max_volume if max_volume > 0 else 1.0
        
        self.current_ratio = ratio
        
        # Check against threshold
        return self.check(ratio, self.volume_ratio_threshold)
    
    def get_status(self) -> Dict:
        """Get the current status of the circuit breaker."""
        status = super().get_status()
        
        # Calculate normal volume if we have enough data
        if len(self.volume_history) >= self.min_periods:
            normal_volume = np.median(self.volume_history[-self.volume_window:])
            max_volume = max(self.volume_history[-self.volume_window:])
        else:
            normal_volume = None
            max_volume = None
        
        status.update({
            'volume_window': self.volume_window,
            'volume_ratio_threshold': self.volume_ratio_threshold,
            'current_volume': self.current_volume,
            'normal_volume': normal_volume,
            'max_volume': max_volume,
            'current_ratio': self.current_ratio,
            'use_relative_ratio': self.use_relative_ratio
        })
        return status


class FrequencyCircuitBreaker(CircuitBreakerBase):
    """
    Circuit breaker that triggers when trading frequency exceeds a threshold.
    
    This circuit breaker monitors the frequency of trading activity and
    triggers when the frequency exceeds a threshold. This is useful for
    detecting runaway algorithms or other abnormal trading patterns.
    
    Parameters:
    -----------
    max_trades : int
        Maximum number of trades allowed in the time window
    time_window : int
        Time window in seconds for counting trades
    **kwargs : 
        Additional parameters for CircuitBreakerBase
    """
    
    def __init__(
        self,
        max_trades: int = 10,
        time_window: int = 60,  # 1 minute
        **kwargs
    ):
        """Initialize the frequency circuit breaker."""
        super().__init__(name="frequency_circuit_breaker", **kwargs)
        self.max_trades = max_trades
        self.time_window = time_window
        
        # Historical data
        self.trade_timestamps = []
        self.trade_count = 0
    
    def update(self) -> CircuitBreakerStatus:
        """
        Update the circuit breaker with a new trade.
        
        Returns:
        --------
        CircuitBreakerStatus
            Current status of the circuit breaker
        """
        # Skip if disabled
        if not self.enabled:
            return CircuitBreakerStatus.DISABLED
        
        # Record the trade
        current_time = time.time()
        self.trade_timestamps.append(current_time)
        self.trade_count += 1
        
        # Remove old trades outside the time window
        self.trade_timestamps = [ts for ts in self.trade_timestamps if current_time - ts <= self.time_window]
        
        # Calculate current frequency
        current_trades = len(self.trade_timestamps)
        
        # Check against threshold
        return self.check(current_trades, self.max_trades)
    
    def get_status(self) -> Dict:
        """Get the current status of the circuit breaker."""
        status = super().get_status()
        
        # Calculate current trades in window
        current_time = time.time()
        current_trades = len([ts for ts in self.trade_timestamps if current_time - ts <= self.time_window])
        
        status.update({
            'max_trades': self.max_trades,
            'time_window': self.time_window,
            'current_trades': current_trades,
            'total_trades': self.trade_count
        })
        return status


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers and provides a unified interface.
    
    Parameters:
    -----------
    circuit_breakers : List[CircuitBreakerBase], optional
        List of circuit breakers to manage
    """
    
    def __init__(self, circuit_breakers: Optional[List[CircuitBreakerBase]] = None):
        """Initialize the circuit breaker manager."""
        self.circuit_breakers = circuit_breakers or []
        self.is_triggered = False
        self.triggered_breakers = []
        
        # Register notification hooks
        for cb in self.circuit_breakers:
            cb.on_trigger = self._handle_trigger
            cb.on_reset = self._handle_reset
    
    def add_circuit_breaker(self, circuit_breaker: CircuitBreakerBase):
        """
        Add a circuit breaker to the manager.
        
        Parameters:
        -----------
        circuit_breaker : CircuitBreakerBase
            Circuit breaker to add
        """
        circuit_breaker.on_trigger = self._handle_trigger
        circuit_breaker.on_reset = self._handle_reset
        self.circuit_breakers.append(circuit_breaker)
    
    def remove_circuit_breaker(self, name: str):
        """
        Remove a circuit breaker from the manager.
        
        Parameters:
        -----------
        name : str
            Name of the circuit breaker to remove
        """
        self.circuit_breakers = [cb for cb in self.circuit_breakers if cb.name != name]
        self.triggered_breakers = [cb for cb in self.triggered_breakers if cb.name != name]
        self._update_trigger_status()
    
    def _handle_trigger(self, circuit_breaker: CircuitBreakerBase):
        """Handle a circuit breaker being triggered."""
        if circuit_breaker not in self.triggered_breakers:
            self.triggered_breakers.append(circuit_breaker)
        self._update_trigger_status()
    
    def _handle_reset(self, circuit_breaker: CircuitBreakerBase):
        """Handle a circuit breaker being reset."""
        if circuit_breaker in self.triggered_breakers:
            self.triggered_breakers.remove(circuit_breaker)
        self._update_trigger_status()
    
    def _update_trigger_status(self):
        """Update the overall trigger status."""
        was_triggered = self.is_triggered
        self.is_triggered = len(self.triggered_breakers) > 0
        
        if self.is_triggered and not was_triggered:
            logger.warning(f"Circuit breaker manager TRIGGERED by {len(self.triggered_breakers)} breakers")
        elif not self.is_triggered and was_triggered:
            logger.info("Circuit breaker manager RESET")
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers:
            cb.reset()
        self.triggered_breakers = []
        self.is_triggered = False
    
    def get_status(self) -> Dict:
        """
        Get the current status of all circuit breakers.
        
        Returns:
        --------
        Dict
            Dictionary with status of all circuit breakers
        """
        return {
            'is_triggered': self.is_triggered,
            'triggered_breakers': [cb.name for cb in self.triggered_breakers],
            'circuit_breakers': {cb.name: cb.get_status() for cb in self.circuit_breakers}
        }
    
    def __str__(self) -> str:
        """Return a string representation of the circuit breaker manager."""
        return f"CircuitBreakerManager(triggered={self.is_triggered}, breakers={len(self.circuit_breakers)})" 