"""
Stop Loss Management Module

This module provides functions and classes for managing stop losses and take profits
for trading positions. Proper stop loss management is essential for controlling risk
and protecting capital.

The module implements several types of stop loss strategies:
- Fixed percentage stops: Set stops at a fixed percentage from entry
- Volatility-based stops: Set stops based on market volatility (e.g., ATR)
- Chart-based stops: Set stops based on support/resistance levels
- Time-based stops: Exit positions after a specific time period
- Trailing stops: Dynamically adjust stops to lock in profits
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
from datetime import datetime, timedelta
import logging

from advanced_trading.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)


def calculate_stop_loss(
    entry_price: float,
    risk_percent: float,
    trade_type: str = "long"
) -> float:
    """Calculate a stop loss price based on a fixed percentage risk.
    
    Args:
        entry_price (float): The entry price of the position.
        risk_percent (float): The percentage risk (e.g., 0.02 for 2%).
        trade_type (str, optional): The type of trade ('long' or 'short'). Defaults to "long".
        
    Returns:
        float: The calculated stop loss price.
        
    Raises:
        ValueError: If the inputs are invalid.
    """
    if entry_price <= 0:
        raise ValueError(f"Entry price must be positive, got {entry_price}")
    
    if risk_percent <= 0:
        raise ValueError(f"Risk percent must be positive, got {risk_percent}")
    
    if trade_type.lower() not in ["long", "short"]:
        raise ValueError(f"Trade type must be 'long' or 'short', got {trade_type}")
    
    if trade_type.lower() == "long":
        stop_price = entry_price * (1 - risk_percent)
    else:  # short
        stop_price = entry_price * (1 + risk_percent)
    
    return stop_price


def volatility_based_stop(
    entry_price: float,
    atr: float,
    multiplier: float = 2.0,
    trade_type: str = "long",
    min_stop_percent: Optional[float] = None,
    max_stop_percent: Optional[float] = None
) -> float:
    """Calculate a stop loss based on market volatility (ATR).
    
    Args:
        entry_price (float): The entry price of the position.
        atr (float): The Average True Range value.
        multiplier (float, optional): The ATR multiplier. Defaults to 2.0.
        trade_type (str, optional): The type of trade ('long' or 'short'). Defaults to "long".
        min_stop_percent (float, optional): Minimum stop distance as percentage. Defaults to None.
        max_stop_percent (float, optional): Maximum stop distance as percentage. Defaults to None.
        
    Returns:
        float: The calculated stop loss price.
        
    Raises:
        ValueError: If the inputs are invalid.
    """
    if entry_price <= 0:
        raise ValueError(f"Entry price must be positive, got {entry_price}")
    
    if atr <= 0:
        raise ValueError(f"ATR must be positive, got {atr}")
    
    if multiplier <= 0:
        raise ValueError(f"Multiplier must be positive, got {multiplier}")
    
    if trade_type.lower() not in ["long", "short"]:
        raise ValueError(f"Trade type must be 'long' or 'short', got {trade_type}")
    
    # Calculate the stop distance
    stop_distance = atr * multiplier
    
    # Calculate the raw stop price
    if trade_type.lower() == "long":
        stop_price = entry_price - stop_distance
    else:  # short
        stop_price = entry_price + stop_distance
    
    # Calculate the stop as a percentage of entry price
    stop_percent = abs(stop_price - entry_price) / entry_price
    
    # Apply minimum stop percentage if provided
    if min_stop_percent is not None and stop_percent < min_stop_percent:
        logger.info(f"Stop percent {stop_percent:.2%} is below minimum {min_stop_percent:.2%}, adjusting")
        if trade_type.lower() == "long":
            stop_price = entry_price * (1 - min_stop_percent)
        else:  # short
            stop_price = entry_price * (1 + min_stop_percent)
    
    # Apply maximum stop percentage if provided
    if max_stop_percent is not None and stop_percent > max_stop_percent:
        logger.info(f"Stop percent {stop_percent:.2%} is above maximum {max_stop_percent:.2%}, adjusting")
        if trade_type.lower() == "long":
            stop_price = entry_price * (1 - max_stop_percent)
        else:  # short
            stop_price = entry_price * (1 + max_stop_percent)
    
    return stop_price


def trailing_stop(
    entry_price: float,
    current_price: float,
    initial_stop_price: float,
    highest_price: float,
    lowest_price: float,
    trade_type: str = "long",
    trail_percent: float = 0.02,
    activation_percent: float = 0.01
) -> float:
    """Calculate a trailing stop loss price.
    
    Args:
        entry_price (float): The entry price of the position.
        current_price (float): The current market price.
        initial_stop_price (float): The initial stop loss price.
        highest_price (float): The highest price since trade entry (for longs).
        lowest_price (float): The lowest price since trade entry (for shorts).
        trade_type (str, optional): The type of trade ('long' or 'short'). Defaults to "long".
        trail_percent (float, optional): The trailing percentage. Defaults to 0.02 (2%).
        activation_percent (float, optional): Profit percent needed to activate. Defaults to 0.01 (1%).
        
    Returns:
        float: The updated trailing stop price.
        
    Raises:
        ValueError: If the inputs are invalid.
    """
    if entry_price <= 0 or current_price <= 0 or initial_stop_price <= 0:
        raise ValueError("Prices must be positive")
    
    if trail_percent <= 0 or activation_percent < 0:
        raise ValueError("Percentage values must be positive")
    
    if trade_type.lower() not in ["long", "short"]:
        raise ValueError(f"Trade type must be 'long' or 'short', got {trade_type}")
    
    # Calculate current profit percentage
    if trade_type.lower() == "long":
        profit_percent = (current_price - entry_price) / entry_price
        reference_price = highest_price
    else:  # short
        profit_percent = (entry_price - current_price) / entry_price
        reference_price = lowest_price
    
    # Check if trailing stop should be activated
    if profit_percent < activation_percent:
        logger.debug(f"Profit {profit_percent:.2%} below activation threshold {activation_percent:.2%}, using initial stop")
        return initial_stop_price
    
    # Calculate trailing stop based on highest/lowest price
    if trade_type.lower() == "long":
        trailing_stop_price = reference_price * (1 - trail_percent)
        # Only move the stop up, never down
        return max(trailing_stop_price, initial_stop_price)
    else:  # short
        trailing_stop_price = reference_price * (1 + trail_percent)
        # Only move the stop down, never up
        return min(trailing_stop_price, initial_stop_price)


def time_based_stop(
    entry_time: datetime,
    current_time: datetime,
    max_days: int = 10,
    max_bars: Optional[int] = None,
    calendar_days: bool = True
) -> bool:
    """Determine if a position should be exited based on time.
    
    Args:
        entry_time (datetime): The entry time of the position.
        current_time (datetime): The current time.
        max_days (int, optional): Maximum holding period in days. Defaults to 10.
        max_bars (int, optional): Maximum holding period in bars. Defaults to None.
        calendar_days (bool, optional): Whether to use calendar days. Defaults to True.
        
    Returns:
        bool: True if the time stop is triggered, False otherwise.
        
    Raises:
        ValueError: If the inputs are invalid.
    """
    if not isinstance(entry_time, datetime) or not isinstance(current_time, datetime):
        raise ValueError("Times must be datetime objects")
    
    if current_time < entry_time:
        raise ValueError("Current time cannot be before entry time")
    
    if max_days <= 0 and (max_bars is None or max_bars <= 0):
        raise ValueError("Either max_days or max_bars must be positive")
    
    # Check if max_days is specified
    if max_days > 0:
        # Calculate time difference in days
        if calendar_days:
            days_held = (current_time - entry_time).days
        else:
            # Only count trading days (Monday to Friday)
            days_held = sum(1 for d in range((current_time - entry_time).days + 1)
                          if (entry_time + timedelta(days=d)).weekday() < 5)
        
        if days_held >= max_days:
            logger.info(f"Time stop triggered: Position held for {days_held} days (max: {max_days})")
            return True
    
    # Check if max_bars is specified
    if max_bars is not None and max_bars > 0:
        # This would require bar count data, which we don't have here
        # In a real implementation, you would need to track the number of bars
        # since entry and compare to max_bars
        pass
    
    return False


class StopManager:
    """
    Advanced stop loss management for trading positions.
    
    This class implements multiple methods for setting, monitoring, and
    adjusting stop losses and take-profit levels during a trade lifecycle.
    
    Attributes:
        default_method (str): Default stop loss method
        trailing_activation (float): Profit needed to activate trailing stops (as R-multiple)
        time_stop_days (int): Number of days before time stop triggers
        atr_multiplier (float): Multiplier for ATR-based stops
        volatility_window (int): Window for volatility calculations
        min_stop_pct (float): Minimum stop distance as percentage
        max_stop_pct (float): Maximum stop distance as percentage
        profit_targets (List[Tuple[float, float]]): List of profit targets as (target_r, exit_pct)
        enable_breakeven (bool): Whether to enable breakeven stops
        breakeven_threshold_r (float): Profit needed to move to breakeven (as R-multiple)
    """
    
    def __init__(
        self,
        default_method: str = 'volatility',
        trailing_activation: float = 0.5,
        time_stop_days: int = 10,
        atr_multiplier: float = 2.0,
        volatility_window: int = 20,
        min_stop_pct: float = 0.005,
        max_stop_pct: float = 0.1,
        profit_targets: Optional[List[Tuple[float, float]]] = None,
        enable_breakeven: bool = True,
        breakeven_threshold_r: float = 1.0
    ):
        """
        Initialize the stop manager.
        
        Args:
            default_method: Default stop loss method
            trailing_activation: Profit needed to activate trailing stops (as R-multiple)
            time_stop_days: Number of days before time stop triggers
            atr_multiplier: Multiplier for ATR-based stops
            volatility_window: Window for volatility calculations
            min_stop_pct: Minimum stop distance as percentage
            max_stop_pct: Maximum stop distance as percentage
            profit_targets: List of profit targets as (target_r, exit_pct)
            enable_breakeven: Whether to enable breakeven stops
            breakeven_threshold_r: Profit needed to move to breakeven (as R-multiple)
        """
        # Initialize parameters
        self.default_method = default_method
        self.trailing_activation = trailing_activation
        self.time_stop_days = time_stop_days
        self.atr_multiplier = atr_multiplier
        self.volatility_window = volatility_window
        self.min_stop_pct = min_stop_pct
        self.max_stop_pct = max_stop_pct
        self.profit_targets = profit_targets if profit_targets else []
        self.enable_breakeven = enable_breakeven
        self.breakeven_threshold_r = breakeven_threshold_r
        
        # Initialize storage for stop data
        self.stops = {}
        
        # Validate parameters
        self._validate_parameters()
        
        logger.info(f"Initialized StopManager with default method: {default_method}")
    
    def _validate_parameters(self):
        """Validate the stop manager parameters."""
        valid_methods = ['fixed', 'volatility', 'chart', 'trailing', 'time']
        if self.default_method not in valid_methods:
            raise ValueError(f"Invalid default method: {self.default_method}")
        
        if self.trailing_activation < 0:
            raise ValueError(f"Trailing activation must be non-negative, got {self.trailing_activation}")
        
        if self.time_stop_days <= 0:
            raise ValueError(f"Time stop days must be positive, got {self.time_stop_days}")
        
        if self.atr_multiplier <= 0:
            raise ValueError(f"ATR multiplier must be positive, got {self.atr_multiplier}")
        
        if self.volatility_window <= 0:
            raise ValueError(f"Volatility window must be positive, got {self.volatility_window}")
        
        if not 0 < self.min_stop_pct < self.max_stop_pct:
            raise ValueError(f"Min stop percent must be positive and less than max stop percent")
        
        if self.max_stop_pct > 0.5:
            logger.warning(f"Max stop percent is very high: {self.max_stop_pct:.2%}")
        
        if self.breakeven_threshold_r < 0:
            raise ValueError(f"Breakeven threshold must be non-negative, got {self.breakeven_threshold_r}")
    
    def initialize_stop(
        self,
        symbol: str,
        entry_price: float,
        trade_type: str,
        initial_stop_price: Optional[float] = None,
        atr: Optional[float] = None,
        risk_amount: float = 0.0,
        position_size: float = 0.0,
        chart_levels: Optional[List[float]] = None,
        stop_method: Optional[str] = None,
        entry_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Initialize a stop loss for a new position.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price of the position
            trade_type: Type of trade ('long' or 'short')
            initial_stop_price: Optional initial stop price (overrides calculation)
            atr: Average True Range for volatility-based stops
            risk_amount: Risk amount in currency
            position_size: Position size in units/shares
            chart_levels: Price levels from chart analysis
            stop_method: Stop loss method (defaults to self.default_method)
            entry_time: Entry time of the position
            
        Returns:
            Dictionary with stop loss details
        """
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        
        if trade_type.lower() not in ["long", "short"]:
            raise ValueError(f"Trade type must be 'long' or 'short', got {trade_type}")
        
        method = stop_method if stop_method else self.default_method
        
        # Calculate initial stop price if not provided
        if initial_stop_price is None:
            initial_stop_price = self._calculate_initial_stop(
                entry_price=entry_price,
                trade_type=trade_type,
                method=method,
                atr=atr,
                chart_levels=chart_levels
            )
        
        # Validate the stop price
        if trade_type.lower() == "long" and initial_stop_price >= entry_price:
            raise ValueError(f"Long stop price ({initial_stop_price}) must be below entry price ({entry_price})")
        
        if trade_type.lower() == "short" and initial_stop_price <= entry_price:
            raise ValueError(f"Short stop price ({initial_stop_price}) must be above entry price ({entry_price})")
        
        # Calculate stop distance in currency and percentage
        stop_distance = abs(entry_price - initial_stop_price)
        stop_percent = stop_distance / entry_price
        
        # Calculate R-value (risk multiple)
        r_value = 1.0 if risk_amount <= 0 else entry_price * position_size / risk_amount
        
        # Calculate profit targets if any
        profit_targets = self._calculate_profit_targets(entry_price, initial_stop_price, trade_type)
        
        # Store stop data
        stop_data = {
            'symbol': symbol,
            'entry_price': entry_price,
            'current_stop': initial_stop_price,
            'initial_stop': initial_stop_price,
            'trade_type': trade_type,
            'method': method,
            'risk_amount': risk_amount,
            'position_size': position_size,
            'stop_distance': stop_distance,
            'stop_percent': stop_percent,
            'r_value': r_value,
            'profit_targets': profit_targets,
            'highest_price': entry_price,
            'lowest_price': entry_price,
            'entry_time': entry_time if entry_time else datetime.now(),
            'breakeven_activated': False,
            'trailing_activated': False,
            'partial_exits': []
        }
        
        self.stops[symbol] = stop_data
        
        logger.info(f"Initialized {method} stop for {symbol} at {initial_stop_price:.6f} "
                   f"({stop_percent:.2%} from entry)")
        
        return stop_data 