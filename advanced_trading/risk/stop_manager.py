"""
Stop Loss Management
------------------
Advanced stop loss management for trading strategies.

This module provides a comprehensive system for setting, monitoring, and
adjusting stop losses for trading positions. It includes:
1. Volatility-based stops (ATR, standard deviation)
2. Chart-based stops (support/resistance, swing points)
3. Time-based stops
4. Trailing stops with multiple algorithms
5. Profit targets and take-profit management
6. Dynamic risk management during trade lifecycle

The stop manager can be used standalone or integrated with the position sizing engine.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union, Callable
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import existing risk management utilities
from utils.risk_management import calculate_adaptive_stop_loss

# Configure logging
logger = logging.getLogger(__name__)

class StopManager:
    """
    Advanced stop loss management for trading strategies.
    
    This class implements multiple methods for setting, monitoring, and
    adjusting stop losses and take-profit levels during a trade lifecycle.
    """
    
    def __init__(
        self,
        default_method: str = 'volatility',
        trailing_activation: float = 0.5,  # Activate trailing stop at 0.5R profit
        time_stop_days: int = 10,         # Exit after 10 days if specified
        atr_multiplier: float = 2.0,
        volatility_window: int = 20,
        min_stop_pct: float = 0.005,      # 0.5% minimum stop
        max_stop_pct: float = 0.1,        # 10% maximum stop
        profit_targets: List[Tuple[float, float]] = None,  # [(target_r, exit_pct), ...]
        enable_breakeven: bool = True,    # Move to breakeven 
        breakeven_threshold_r: float = 1.0  # Move to breakeven at 1R profit
    ):
        """
        Initialize the stop manager.
        
        Args:
            default_method: Default stop loss method 
               ('volatility', 'fixed', 'chart', 'chandelier', 'time')
            trailing_activation: Profit (in R multiples) to activate trailing stop
            time_stop_days: Days until time-based exit (if enabled)
            atr_multiplier: Multiplier for ATR-based stops
            volatility_window: Lookback window for volatility calculations
            min_stop_pct: Minimum stop loss percentage
            max_stop_pct: Maximum stop loss percentage
            profit_targets: List of (target_r, exit_percentage) tuples
                e.g. [(1.0, 0.3), (2.0, 0.5), (3.0, 1.0)] means:
                - Exit 30% of position at 1R profit
                - Exit 50% of remaining at 2R profit
                - Exit remaining at 3R profit
            enable_breakeven: Whether to move stop to breakeven at certain profit
            breakeven_threshold_r: Profit (in R) to move stop to breakeven
        """
        self.default_method = default_method
        self.trailing_activation = trailing_activation
        self.time_stop_days = time_stop_days
        self.atr_multiplier = atr_multiplier
        self.volatility_window = volatility_window
        self.min_stop_pct = min_stop_pct
        self.max_stop_pct = max_stop_pct
        self.enable_breakeven = enable_breakeven
        self.breakeven_threshold_r = breakeven_threshold_r
        
        # Set default profit targets if none provided
        if profit_targets is None:
            self.profit_targets = [(1.5, 0.3), (2.5, 0.5), (4.0, 1.0)]
        else:
            self.profit_targets = sorted(profit_targets, key=lambda x: x[0])
            
        # Dictionary to store active stops
        self.active_stops = {}
        
        # Validate parameters
        self._validate_parameters()
        
        logger.info(f"Initialized StopManager with {default_method} method")
    
    def _validate_parameters(self):
        """Validate the initialization parameters."""
        valid_methods = ['volatility', 'fixed', 'chart', 'chandelier', 'time']
        if self.default_method not in valid_methods:
            raise ValueError(f"default_method must be one of {valid_methods}")
        
        if not (0 < self.min_stop_pct < self.max_stop_pct):
            raise ValueError("Invalid stop percentages (min must be less than max)")
        
        if self.atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be positive")
        
        if self.volatility_window <= 0:
            raise ValueError("volatility_window must be positive")
        
        # Ensure profit targets are properly ordered
        if len(self.profit_targets) > 0:
            for i, (target_r, exit_pct) in enumerate(self.profit_targets):
                if not (0 < exit_pct <= 1):
                    raise ValueError(f"Invalid exit percentage in profit target {i}: {exit_pct}")
                if target_r <= 0:
                    raise ValueError(f"Invalid target R multiple in profit target {i}: {target_r}")
    
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
        Initialize stop management for a new position.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            trade_type: 'long' or 'short'
            initial_stop_price: Initial stop price (optional)
            atr: Average True Range value (optional)
            risk_amount: Risk amount for R-multiple calculations
            position_size: Position size in base units
            chart_levels: Key price levels for chart-based stops
            stop_method: Stop method override
            entry_time: Entry timestamp
            
        Returns:
            Dictionary with stop management details
        """
        # Use default method if none specified
        method = stop_method if stop_method else self.default_method
        
        # Calculate initial stop price if not provided
        if initial_stop_price is None:
            initial_stop_price = self._calculate_initial_stop(
                entry_price, 
                trade_type, 
                method,
                atr, 
                chart_levels
            )
        
        # Calculate stop distance as percentage
        if trade_type == 'long':
            stop_pct = (entry_price - initial_stop_price) / entry_price
        else:
            stop_pct = (initial_stop_price - entry_price) / entry_price
        
        # Ensure stop is within bounds
        stop_pct = max(self.min_stop_pct, min(stop_pct, self.max_stop_pct))
        
        # Recalculate stop price based on bounded percentage
        if trade_type == 'long':
            adjusted_stop = entry_price * (1 - stop_pct)
        else:
            adjusted_stop = entry_price * (1 + stop_pct)
        
        # Create stop management object
        stop_data = {
            'symbol': symbol,
            'entry_price': entry_price,
            'current_stop': adjusted_stop,
            'initial_stop': adjusted_stop,
            'initial_stop_pct': stop_pct,
            'trade_type': trade_type,
            'stop_method': method,
            'atr': atr,
            'risk_amount': risk_amount,
            'position_size': position_size,
            'r_multiple_current': 0.0,  # Current profit/loss in R multiples
            'entry_time': entry_time if entry_time else datetime.now(),
            'last_update_time': datetime.now(),
            'trailing_activated': False,
            'breakeven_activated': False,
            'profit_targets': self._calculate_profit_targets(entry_price, adjusted_stop, trade_type),
            'exits_triggered': [],  # Track which profit targets have been hit
            'current_price': entry_price,
            'chart_levels': chart_levels if chart_levels else []
        }
        
        # Register in active stops
        self.active_stops[symbol] = stop_data
        
        logger.info(
            f"Initialized stop for {symbol} at {adjusted_stop:.4f} "
            f"({stop_pct*100:.2f}% from entry)"
        )
        
        return stop_data.copy()
    
    def update_stop(
        self, 
        symbol: str, 
        current_price: float,
        current_time: Optional[datetime] = None,
        atr: Optional[float] = None,
        new_chart_levels: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Update stop loss based on current price and conditions.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            current_time: Current timestamp
            atr: Updated ATR value (optional)
            new_chart_levels: Updated chart levels (optional)
            
        Returns:
            Updated stop management details with action recommendations
        """
        if symbol not in self.active_stops:
            logger.warning(f"No active stop found for {symbol}")
            return {}
        
        # Get stop data
        stop_data = self.active_stops[symbol].copy()
        
        # Update current values
        stop_data['current_price'] = current_price
        if current_time:
            stop_data['last_update_time'] = current_time
        else:
            current_time = datetime.now()
            stop_data['last_update_time'] = current_time
            
        if atr is not None:
            stop_data['atr'] = atr
            
        if new_chart_levels:
            stop_data['chart_levels'] = new_chart_levels
        
        # Calculate current R multiple
        if stop_data['risk_amount'] > 0:
            if stop_data['trade_type'] == 'long':
                profit_amount = (current_price - stop_data['entry_price']) * stop_data['position_size']
            else:
                profit_amount = (stop_data['entry_price'] - current_price) * stop_data['position_size']
                
            stop_data['r_multiple_current'] = profit_amount / stop_data['risk_amount']
        else:
            # Fallback calculation if risk amount not provided
            if stop_data['trade_type'] == 'long':
                r_distance = (stop_data['entry_price'] - stop_data['initial_stop'])
                if r_distance > 0:
                    stop_data['r_multiple_current'] = (current_price - stop_data['entry_price']) / r_distance
            else:
                r_distance = (stop_data['initial_stop'] - stop_data['entry_price'])
                if r_distance > 0:
                    stop_data['r_multiple_current'] = (stop_data['entry_price'] - current_price) / r_distance
        
        # Initialize action response
        action = {
            'stop_triggered': False,
            'take_profit_triggered': False,
            'time_stop_triggered': False,
            'profit_exit_pct': 0.0,  # Percentage of position to exit
            'new_stop': stop_data['current_stop'],
            'trailing_activated': stop_data['trailing_activated'],
            'breakeven_activated': stop_data['breakeven_activated'],
            'stop_moved': False
        }
        
        # Check for stop loss hit
        if self._is_stop_triggered(stop_data, current_price):
            action['stop_triggered'] = True
            action['exit_reason'] = 'stop_loss'
            logger.info(f"Stop loss triggered for {symbol} at {current_price:.4f}")
            return {**stop_data, **action}
        
        # Check for time-based exit
        if stop_data['stop_method'] == 'time':
            time_diff = current_time - stop_data['entry_time']
            if time_diff.total_seconds() > self.time_stop_days * 24 * 3600:
                action['time_stop_triggered'] = True
                action['exit_reason'] = 'time_stop'
                logger.info(f"Time stop triggered for {symbol} after {self.time_stop_days} days")
                return {**stop_data, **action}
        
        # Check for take-profit levels
        exit_pct = self._check_profit_targets(stop_data, current_price)
        if exit_pct > 0:
            action['take_profit_triggered'] = True
            action['profit_exit_pct'] = exit_pct
            action['exit_reason'] = 'take_profit'
            logger.info(f"Take profit triggered for {symbol} at {current_price:.4f} (exit {exit_pct*100:.0f}%)")
            
            # If not exiting full position, update stop and continue
            if exit_pct < 1.0:
                # After partial exit, may want to adjust stops
                new_stop = self._adjust_stop_after_partial_exit(stop_data, current_price, exit_pct)
                if new_stop != stop_data['current_stop']:
                    stop_data['current_stop'] = new_stop
                    action['new_stop'] = new_stop
                    action['stop_moved'] = True
                    logger.info(f"Adjusted stop after partial exit to {new_stop:.4f}")
            
            return {**stop_data, **action}
        
        # Check for breakeven stop
        if (self.enable_breakeven and 
            not stop_data['breakeven_activated'] and 
            stop_data['r_multiple_current'] >= self.breakeven_threshold_r):
            
            # Move stop to breakeven (or slightly better)
            new_stop = self._get_breakeven_stop(stop_data)
            stop_data['current_stop'] = new_stop
            stop_data['breakeven_activated'] = True
            action['new_stop'] = new_stop
            action['breakeven_activated'] = True
            action['stop_moved'] = True
            logger.info(f"Moved stop to breakeven for {symbol} at {new_stop:.4f}")
        
        # Check for trailing stop activation
        if (not stop_data['trailing_activated'] and 
            stop_data['r_multiple_current'] >= self.trailing_activation):
            
            stop_data['trailing_activated'] = True
            action['trailing_activated'] = True
            logger.info(f"Activated trailing stop for {symbol} at {self.trailing_activation}R profit")
        
        # Update trailing stop if activated
        if stop_data['trailing_activated']:
            new_stop = self._update_trailing_stop(stop_data, current_price)
            if new_stop != stop_data['current_stop']:
                stop_data['current_stop'] = new_stop
                action['new_stop'] = new_stop
                action['stop_moved'] = True
                logger.info(f"Updated trailing stop for {symbol} to {new_stop:.4f}")
        
        # Update active stops dictionary
        self.active_stops[symbol] = stop_data
        
        return {**stop_data, **action}
    
    def remove_stop(self, symbol: str) -> bool:
        """
        Remove stop management for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if successfully removed, False otherwise
        """
        if symbol in self.active_stops:
            del self.active_stops[symbol]
            logger.info(f"Removed stop management for {symbol}")
            return True
        else:
            logger.warning(f"Cannot remove stop for {symbol} - not found")
            return False
    
    def get_stop_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get current stop management data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Stop management data or empty dict if not found
        """
        return self.active_stops.get(symbol, {}).copy()
    
    def _calculate_initial_stop(
        self,
        entry_price: float,
        trade_type: str,
        method: str,
        atr: Optional[float] = None,
        chart_levels: Optional[List[float]] = None
    ) -> float:
        """
        Calculate initial stop price based on specified method.
        
        Args:
            entry_price: Entry price
            trade_type: 'long' or 'short'
            method: Stop method
            atr: ATR value (for volatility-based stops)
            chart_levels: Price levels (for chart-based stops)
            
        Returns:
            Initial stop price
        """
        if method == 'volatility':
            # ATR-based volatility stop
            if atr is None or atr <= 0:
                # Fallback to percentage
                logger.warning("No valid ATR provided for volatility stop, using fixed percentage")
                stop_pct = self.min_stop_pct
            else:
                # Calculate stop percentage based on ATR
                stop_pct = calculate_adaptive_stop_loss(
                    price=entry_price,
                    atr=atr,
                    multiplier=self.atr_multiplier,
                    min_pct=self.min_stop_pct,
                    max_pct=self.max_stop_pct
                )
            
            # Calculate stop price
            if trade_type == 'long':
                stop_price = entry_price * (1 - stop_pct)
            else:
                stop_price = entry_price * (1 + stop_pct)
                
        elif method == 'fixed':
            # Simple fixed percentage
            if trade_type == 'long':
                stop_price = entry_price * (1 - self.min_stop_pct)
            else:
                stop_price = entry_price * (1 + self.min_stop_pct)
                
        elif method == 'chart':
            # Chart-based stop using nearest level
            if not chart_levels or len(chart_levels) == 0:
                logger.warning("No chart levels provided for chart-based stop, using fixed percentage")
                if trade_type == 'long':
                    stop_price = entry_price * (1 - self.min_stop_pct)
                else:
                    stop_price = entry_price * (1 + self.min_stop_pct)
            else:
                # For long trades, find nearest level below entry
                if trade_type == 'long':
                    levels_below = [l for l in chart_levels if l < entry_price]
                    if levels_below:
                        stop_price = max(levels_below)  # Highest level below entry
                    else:
                        stop_price = entry_price * (1 - self.min_stop_pct)
                        
                # For short trades, find nearest level above entry
                else:
                    levels_above = [l for l in chart_levels if l > entry_price]
                    if levels_above:
                        stop_price = min(levels_above)  # Lowest level above entry
                    else:
                        stop_price = entry_price * (1 + self.min_stop_pct)
                        
                # Ensure stop is not too far from entry
                stop_pct = abs(stop_price - entry_price) / entry_price
                if stop_pct > self.max_stop_pct:
                    logger.warning(f"Chart-based stop too far from entry ({stop_pct:.2%}), limiting to {self.max_stop_pct:.2%}")
                    if trade_type == 'long':
                        stop_price = entry_price * (1 - self.max_stop_pct)
                    else:
                        stop_price = entry_price * (1 + self.max_stop_pct)
                        
        elif method == 'chandelier':
            # Chandelier exit (similar to volatility but using different calculation)
            if atr is None or atr <= 0:
                logger.warning("No valid ATR provided for chandelier stop, using fixed percentage")
                if trade_type == 'long':
                    stop_price = entry_price * (1 - self.min_stop_pct)
                else:
                    stop_price = entry_price * (1 + self.min_stop_pct)
            else:
                # For longs: Entry - (ATR * multiplier)
                # For shorts: Entry + (ATR * multiplier)
                if trade_type == 'long':
                    stop_price = entry_price - (atr * self.atr_multiplier)
                else:
                    stop_price = entry_price + (atr * self.atr_multiplier)
                    
                # Ensure stop is within bounds
                stop_pct = abs(stop_price - entry_price) / entry_price
                if stop_pct < self.min_stop_pct:
                    if trade_type == 'long':
                        stop_price = entry_price * (1 - self.min_stop_pct)
                    else:
                        stop_price = entry_price * (1 + self.min_stop_pct)
                elif stop_pct > self.max_stop_pct:
                    if trade_type == 'long':
                        stop_price = entry_price * (1 - self.max_stop_pct)
                    else:
                        stop_price = entry_price * (1 + self.max_stop_pct)
                        
        elif method == 'time':
            # For time-based exits, still need an initial stop price
            # Use volatility-based if ATR available, otherwise fixed
            if atr is not None and atr > 0:
                stop_pct = calculate_adaptive_stop_loss(
                    price=entry_price,
                    atr=atr,
                    multiplier=self.atr_multiplier,
                    min_pct=self.min_stop_pct,
                    max_pct=self.max_stop_pct
                )
            else:
                stop_pct = self.min_stop_pct
                
            if trade_type == 'long':
                stop_price = entry_price * (1 - stop_pct)
            else:
                stop_price = entry_price * (1 + stop_pct)
        
        else:
            # Fallback to fixed percentage
            logger.warning(f"Unknown stop method '{method}', using fixed percentage")
            if trade_type == 'long':
                stop_price = entry_price * (1 - self.min_stop_pct)
            else:
                stop_price = entry_price * (1 + self.min_stop_pct)
        
        return stop_price

    def _calculate_profit_targets(self, entry_price: float, stop_price: float, trade_type: str) -> List[Tuple[float, float]]:
        """
        Calculate profit targets based on entry price and stop price.
        
        Args:
            entry_price: Entry price
            stop_price: Stop price
            trade_type: 'long' or 'short'
            
        Returns:
            List of (target_r, exit_percentage) tuples
        """
        profit_targets = []
        for target_r, exit_pct in self.profit_targets:
            if trade_type == 'long':
                target_price = entry_price * target_r
            else:
                target_price = entry_price / target_r
            
            if trade_type == 'long':
                exit_pct = (target_price - stop_price) / target_price
            else:
                exit_pct = (stop_price - target_price) / stop_price
            
            # Ensure exit percentage is within bounds
            exit_pct = max(0, min(exit_pct, 1))
            
            profit_targets.append((target_r, exit_pct))
        
        return profit_targets

    def _is_stop_triggered(self, stop_data: Dict[str, Any], current_price: float) -> bool:
        """
        Check if the stop loss is triggered based on current price.
        
        Args:
            stop_data: Stop management data
            current_price: Current market price
            
        Returns:
            True if stop loss is triggered, False otherwise
        """
        if stop_data['trade_type'] == 'long':
            return current_price <= stop_data['current_stop']
        else:
            return current_price >= stop_data['current_stop']

    def _check_profit_targets(self, stop_data: Dict[str, Any], current_price: float) -> float:
        """
        Check if any profit target is triggered based on current price.
        
        Args:
            stop_data: Stop management data
            current_price: Current market price
            
        Returns:
            Exit percentage if any profit target is triggered, 0.0 if none are triggered
        """
        for target_r, exit_pct in self.profit_targets:
            if stop_data['trade_type'] == 'long':
                target_price = stop_data['entry_price'] * target_r
            else:
                target_price = stop_data['entry_price'] / target_r
            
            if stop_data['trade_type'] == 'long':
                if current_price >= target_price:
                    return exit_pct
            else:
                if current_price <= target_price:
                    return exit_pct
        
        return 0.0

    def _adjust_stop_after_partial_exit(self, stop_data: Dict[str, Any], current_price: float, exit_pct: float) -> float:
        """
        Adjust stop loss after a partial exit.
        
        Args:
            stop_data: Stop management data
            current_price: Current market price
            exit_pct: Exit percentage
            
        Returns:
            Adjusted stop price
        """
        if stop_data['trade_type'] == 'long':
            new_stop = stop_data['entry_price'] * (1 - exit_pct)
        else:
            new_stop = stop_data['entry_price'] * (1 + exit_pct)
        
        # Ensure new stop is within bounds
        new_stop = max(self.min_stop_pct, min(new_stop, self.max_stop_pct))
        
        return new_stop

    def _get_breakeven_stop(self, stop_data: Dict[str, Any]) -> float:
        """
        Get breakeven stop price.
        
        Args:
            stop_data: Stop management data
            
        Returns:
            Breakeven stop price
        """
        if stop_data['trade_type'] == 'long':
            return stop_data['entry_price'] * (1 - self.min_stop_pct)
        else:
            return stop_data['entry_price'] * (1 + self.min_stop_pct)

    def _update_trailing_stop(self, stop_data: Dict[str, Any], current_price: float) -> float:
        """
        Update trailing stop price based on current price.
        
        Args:
            stop_data: Stop management data
            current_price: Current market price
            
        Returns:
            Updated trailing stop price
        """
        if stop_data['trade_type'] == 'long':
            new_stop = current_price - (current_price - stop_data['initial_stop']) * self.trailing_activation
        else:
            new_stop = current_price + (stop_data['initial_stop'] - current_price) * self.trailing_activation
        
        # Ensure new stop is within bounds
        new_stop = max(self.min_stop_pct, min(new_stop, self.max_stop_pct))
        
        return new_stop 