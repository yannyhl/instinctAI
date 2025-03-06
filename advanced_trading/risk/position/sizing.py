"""
Position Sizing Module

This module provides functions for calculating appropriate position sizes based on various
risk management approaches. Position sizing is a critical aspect of risk management that
determines how much capital to allocate to each trade.

The module implements several common position sizing methods, including:
- Fixed risk: Risk a fixed percentage of capital on each trade
- Volatility-based: Adjust position size based on market volatility
- Optimal f: Use the Kelly criterion for optimal position sizing
- Position scaling: Gradually scale into positions based on confirmation signals
"""

import math
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from advanced_trading.core.observability import get_logger
from advanced_trading.core.common import validate_positive

# Initialize logger
logger = get_logger(__name__)


def calculate_position_size(
    account_size: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss_price: float,
    slippage_factor: float = 0.001,
    commission_per_share: float = 0.0,
    min_position_size: float = 0.0,
    max_position_size: Optional[float] = None
) -> float:
    """Calculate position size based on fixed risk per trade.
    
    This function calculates the appropriate position size based on a fixed percentage
    risk per trade, the entry price, and the stop-loss price.
    
    Args:
        account_size (float): The total account size in currency units.
        risk_per_trade (float): The percentage of account to risk per trade (e.g., 0.01 for 1%).
        entry_price (float): The entry price for the position.
        stop_loss_price (float): The stop-loss price for the position.
        slippage_factor (float, optional): The slippage factor as a percentage. Defaults to 0.001 (0.1%).
        commission_per_share (float, optional): The commission per share. Defaults to 0.0.
        min_position_size (float, optional): The minimum position size. Defaults to 0.0.
        max_position_size (float, optional): The maximum position size. Defaults to None.
        
    Returns:
        float: The calculated position size in units/shares.
        
    Raises:
        ValueError: If any of the input parameters are invalid.
    """
    # Validate inputs
    validate_positive(account_size, "account_size")
    validate_positive(risk_per_trade, "risk_per_trade")
    validate_positive(entry_price, "entry_price")
    validate_positive(stop_loss_price, "stop_loss_price")
    
    if risk_per_trade > 0.5:
        logger.warning(f"Risk per trade is very high: {risk_per_trade:.2%}")
    
    # Calculate the dollar risk amount
    dollar_risk = account_size * risk_per_trade
    
    # Calculate the price risk (difference between entry and stop, adjusted for direction)
    # For long positions, stop is below entry; for short positions, stop is above entry
    is_long = entry_price > stop_loss_price
    price_risk = abs(entry_price - stop_loss_price)
    
    # Add slippage to the price risk
    slippage_amount = entry_price * slippage_factor
    adjusted_price_risk = price_risk + slippage_amount
    
    # Calculate the base position size
    if adjusted_price_risk > 0:
        position_size = dollar_risk / adjusted_price_risk
    else:
        logger.error("Price risk is zero or negative")
        return 0
    
    # Adjust for commission if applicable
    if commission_per_share > 0:
        # Approximate the impact of commission on the position size
        # This is a simplified approach; more complex calculations might be necessary
        position_size = position_size * (1 - (commission_per_share / entry_price))
    
    # Apply minimum position size constraint
    if position_size < min_position_size:
        logger.info(f"Calculated position size {position_size} is below minimum {min_position_size}, using minimum")
        position_size = min_position_size
    
    # Apply maximum position size constraint if specified
    if max_position_size is not None and position_size > max_position_size:
        logger.info(f"Calculated position size {position_size} is above maximum {max_position_size}, using maximum")
        position_size = max_position_size
    
    return position_size


def max_position_size(
    account_size: float,
    max_exposure_pct: float,
    entry_price: float,
    leverage: float = 1.0
) -> float:
    """Calculate the maximum position size based on the maximum exposure percentage.
    
    This function determines the maximum position size based on account size,
    maximum exposure percentage, and current market price.
    
    Args:
        account_size (float): The total account size in currency units.
        max_exposure_pct (float): The maximum percentage of account to expose to a single position.
        entry_price (float): The entry price for the position.
        leverage (float, optional): The leverage multiplier. Defaults to 1.0 (no leverage).
        
    Returns:
        float: The maximum position size in units/shares.
        
    Raises:
        ValueError: If any of the input parameters are invalid.
    """
    # Validate inputs
    validate_positive(account_size, "account_size")
    validate_positive(max_exposure_pct, "max_exposure_pct")
    validate_positive(entry_price, "entry_price")
    validate_positive(leverage, "leverage")
    
    if max_exposure_pct > 1.0:
        logger.warning(f"Maximum exposure percentage exceeds 100%: {max_exposure_pct:.2%}")
    
    if leverage > 1.0:
        logger.info(f"Using leverage: {leverage}x")
    
    # Calculate the maximum dollar amount to allocate to the position
    max_dollar_amount = account_size * max_exposure_pct * leverage
    
    # Calculate the maximum position size
    max_size = max_dollar_amount / entry_price
    
    return max_size


def optimal_position_size(
    account_size: float,
    win_rate: float,
    risk_reward_ratio: float,
    max_exposure_pct: float = 0.25,
    kelly_fraction: float = 0.5
) -> float:
    """Calculate the optimal position size using the Kelly criterion.
    
    The Kelly criterion provides a mathematically optimal bet size based on the
    probability of winning and the risk/reward ratio. This function calculates
    the optimal position size as a percentage of the account.
    
    Args:
        account_size (float): The total account size in currency units.
        win_rate (float): The probability of winning (between 0 and 1).
        risk_reward_ratio (float): The ratio of average win to average loss.
        max_exposure_pct (float, optional): Maximum exposure percentage. Defaults to 0.25 (25%).
        kelly_fraction (float, optional): Fraction of the Kelly criterion to use. Defaults to 0.5 (half-Kelly).
        
    Returns:
        float: The optimal position size as a dollar amount.
        
    Raises:
        ValueError: If any of the input parameters are invalid.
    """
    # Validate inputs
    validate_positive(account_size, "account_size")
    
    if not 0 < win_rate < 1:
        raise ValueError(f"Win rate must be between 0 and 1, got {win_rate}")
    
    validate_positive(risk_reward_ratio, "risk_reward_ratio")
    validate_positive(max_exposure_pct, "max_exposure_pct")
    validate_positive(kelly_fraction, "kelly_fraction")
    
    # Calculate the Kelly percentage
    # Kelly % = W - [(1 - W) / R]
    # Where: W = Win Rate, R = Risk/Reward Ratio
    kelly_pct = win_rate - ((1 - win_rate) / risk_reward_ratio)
    
    # Apply Kelly fraction to reduce risk
    adjusted_kelly_pct = kelly_pct * kelly_fraction
    
    # Cap at maximum exposure percentage
    final_pct = min(adjusted_kelly_pct, max_exposure_pct)
    
    if final_pct <= 0:
        logger.warning(f"Calculated Kelly percentage is negative: {kelly_pct:.2%}")
        logger.warning(f"This indicates a negative expectancy system. Using minimum position size.")
        return 0
    
    if adjusted_kelly_pct > max_exposure_pct:
        logger.info(f"Kelly position size {adjusted_kelly_pct:.2%} exceeds maximum exposure {max_exposure_pct:.2%}, using maximum")
    
    # Calculate dollar amount
    position_dollar_amount = account_size * final_pct
    
    return position_dollar_amount


def adjust_position_size(
    base_position_size: float,
    volatility_factor: Optional[float] = None,
    trend_strength: Optional[float] = None,
    confidence_factor: Optional[float] = None,
    market_condition_factor: Optional[float] = None
) -> float:
    """Adjust the position size based on market conditions and strategy confidence.
    
    This function applies various adjustment factors to the base position size to
    account for current market conditions, strategy confidence, and other factors.
    
    Args:
        base_position_size (float): The base position size to adjust.
        volatility_factor (float, optional): Adjustment factor based on current market volatility.
        trend_strength (float, optional): Adjustment factor based on the strength of the current trend.
        confidence_factor (float, optional): Adjustment factor based on strategy confidence.
        market_condition_factor (float, optional): Adjustment factor based on overall market conditions.
        
    Returns:
        float: The adjusted position size.
    """
    # Validate inputs
    validate_positive(base_position_size, "base_position_size")
    
    # Start with the base position size
    adjusted_size = base_position_size
    
    # Apply volatility adjustment if provided
    if volatility_factor is not None:
        if volatility_factor <= 0:
            logger.warning(f"Invalid volatility factor: {volatility_factor}, must be positive")
        else:
            # Inverse relationship: higher volatility = smaller position
            adjusted_size = adjusted_size * (1 / volatility_factor)
            logger.debug(f"Applied volatility adjustment: {volatility_factor}, new size: {adjusted_size}")
    
    # Apply trend strength adjustment if provided
    if trend_strength is not None:
        if trend_strength < 0 or trend_strength > 1:
            logger.warning(f"Invalid trend strength: {trend_strength}, should be between 0 and 1")
        else:
            # Direct relationship: stronger trend = larger position
            trend_adjustment = 0.5 + (trend_strength * 0.5)  # Scale from 0.5 to 1.0
            adjusted_size = adjusted_size * trend_adjustment
            logger.debug(f"Applied trend adjustment: {trend_adjustment}, new size: {adjusted_size}")
    
    # Apply confidence adjustment if provided
    if confidence_factor is not None:
        if confidence_factor < 0 or confidence_factor > 1:
            logger.warning(f"Invalid confidence factor: {confidence_factor}, should be between 0 and 1")
        else:
            # Direct relationship: higher confidence = larger position
            adjusted_size = adjusted_size * confidence_factor
            logger.debug(f"Applied confidence adjustment: {confidence_factor}, new size: {adjusted_size}")
    
    # Apply market condition adjustment if provided
    if market_condition_factor is not None:
        if market_condition_factor <= 0:
            logger.warning(f"Invalid market condition factor: {market_condition_factor}, must be positive")
        else:
            # Market condition factor could be > 1 (favorable) or < 1 (unfavorable)
            adjusted_size = adjusted_size * market_condition_factor
            logger.debug(f"Applied market condition adjustment: {market_condition_factor}, new size: {adjusted_size}")
    
    return adjusted_size


class PositionSizingEngine:
    """
    Advanced position sizing engine for trading strategies.
    
    This class determines optimal position sizes based on multiple factors
    including account risk limits, volatility, portfolio exposure, and
    strategy-specific performance metrics.
    
    Attributes:
        account_size (float): Current account size in currency units
        max_risk_per_trade (float): Maximum risk per trade as a percentage
        max_account_risk (float): Maximum account-wide risk as a percentage
        max_correlated_risk (float): Maximum correlated risk as a percentage
        position_sizing_method (str): Method used for position sizing
        kelly_fraction (float): Fraction of Kelly criterion to use
        volatility_lookback (int): Lookback period for volatility calculation
        performance_adjustment (bool): Whether to adjust based on performance
        risk_of_ruin_protection (bool): Whether to use risk of ruin protection
        max_open_trades (int): Maximum number of open trades allowed
    """
    
    def __init__(
        self,
        account_size: float,
        max_risk_per_trade: float = 0.01,
        max_account_risk: float = 0.05,
        max_correlated_risk: float = 0.1,
        position_sizing_method: str = 'risk_based',
        kelly_fraction: float = 0.3,
        volatility_lookback: int = 20,
        performance_adjustment: bool = True,
        risk_of_ruin_protection: bool = True,
        max_open_trades: int = 10
    ):
        """
        Initialize the position sizing engine.
        
        Args:
            account_size: Current account size in currency units
            max_risk_per_trade: Maximum risk per trade as a percentage
            max_account_risk: Maximum account-wide risk as a percentage
            max_correlated_risk: Maximum correlated risk as a percentage
            position_sizing_method: Method used for position sizing
            kelly_fraction: Fraction of Kelly criterion to use
            volatility_lookback: Lookback period for volatility calculation
            performance_adjustment: Whether to adjust based on performance
            risk_of_ruin_protection: Whether to use risk of ruin protection
            max_open_trades: Maximum number of open trades allowed
        """
        # Initialize the engine with provided parameters
        self.account_size = account_size
        self.max_risk_per_trade = max_risk_per_trade
        self.max_account_risk = max_account_risk
        self.max_correlated_risk = max_correlated_risk
        self.position_sizing_method = position_sizing_method
        self.kelly_fraction = kelly_fraction
        self.volatility_lookback = volatility_lookback
        self.performance_adjustment = performance_adjustment
        self.risk_of_ruin_protection = risk_of_ruin_protection
        self.max_open_trades = max_open_trades
        
        # Initialize tracking variables
        self.positions = {}
        self.exposure = {
            'total': 0.0,
            'long': 0.0,
            'short': 0.0,
            'categories': {},
            'correlation_groups': {}
        }
        
        # Initialize performance metrics
        self.performance = {
            'win_rate': 0.5,
            'win_loss_ratio': 1.0,
            'expected_value': 0.0,
            'sharpe_ratio': 0.0,
            'drawdown': 0.0,
            'trades': []
        }
        
        # Validate the parameters
        self._validate_parameters()
        
        logger.info(f"Initialized PositionSizingEngine with account size: {account_size}")
    
    def _validate_parameters(self):
        """Validate the engine parameters."""
        if self.account_size <= 0:
            raise ValueError(f"Account size must be positive, got {self.account_size}")
        
        if not 0 < self.max_risk_per_trade < 0.5:
            raise ValueError(f"Max risk per trade should be between 0 and 0.5, got {self.max_risk_per_trade}")
        
        if not 0 < self.max_account_risk < 1:
            raise ValueError(f"Max account risk should be between 0 and 1, got {self.max_account_risk}")
        
        if not 0 < self.max_correlated_risk < 1:
            raise ValueError(f"Max correlated risk should be between 0 and 1, got {self.max_correlated_risk}")
        
        valid_methods = ['risk_based', 'kelly', 'volatility_based', 'fixed_size']
        if self.position_sizing_method not in valid_methods:
            raise ValueError(f"Invalid position sizing method: {self.position_sizing_method}")
        
        if not 0 < self.kelly_fraction <= 1:
            raise ValueError(f"Kelly fraction should be between 0 and 1, got {self.kelly_fraction}")
        
        if self.volatility_lookback < 5:
            raise ValueError(f"Volatility lookback should be at least 5, got {self.volatility_lookback}")
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_price: Optional[float] = None,
        atr: Optional[float] = None,
        volatility: Optional[float] = None,
        win_rate: Optional[float] = None,
        win_loss_ratio: Optional[float] = None,
        trade_type: str = 'long',
        strategy_id: Optional[str] = None,
        category: str = 'default',
        correlation_group: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Calculate the optimal position size for a trade.
        
        Args:
            symbol: The trading symbol
            entry_price: The intended entry price
            stop_price: The initial stop loss price
            atr: Average True Range, used for volatility-based sizing
            volatility: Market volatility, alternative to ATR
            win_rate: Expected win rate for this trade
            win_loss_ratio: Expected win/loss ratio for this trade
            trade_type: Type of trade ('long' or 'short')
            strategy_id: Identifier of the strategy generating this signal
            category: Category of the trade (e.g., 'trend', 'breakout')
            correlation_group: Group of correlated trades
            
        Returns:
            Dictionary containing position size and related metrics
        """
        # Validate inputs
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        
        if stop_price is not None and stop_price <= 0:
            raise ValueError(f"Stop price must be positive, got {stop_price}")
        
        if trade_type not in ['long', 'short']:
            raise ValueError(f"Trade type must be 'long' or 'short', got {trade_type}")
        
        # Get the stop loss percentage
        stop_loss_pct = self._calculate_stop_loss_pct(entry_price, stop_price, atr)
        
        # Get the adjusted risk percentage based on current exposure
        risk_pct = self._get_adjusted_risk_pct(symbol, category, correlation_group, trade_type)
        
        # Calculate position size based on the selected method
        if self.position_sizing_method == 'risk_based':
            # Risk-based position sizing
            dollar_risk = self.account_size * risk_pct
            position_size = dollar_risk / (entry_price * stop_loss_pct)
            
        elif self.position_sizing_method == 'kelly':
            # Kelly criterion position sizing
            if win_rate is None:
                win_rate = self.performance['win_rate']
            
            if win_loss_ratio is None:
                win_loss_ratio = self.performance['win_loss_ratio']
            
            # Calculate Kelly position size
            kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)
            adjusted_kelly = kelly_pct * self.kelly_fraction
            
            # Apply risk limits
            kelly_pct = min(adjusted_kelly, risk_pct)
            
            if kelly_pct <= 0:
                logger.warning(f"Kelly criterion suggests no position for {symbol}")
                return {
                    'symbol': symbol,
                    'position_size': 0,
                    'dollar_amount': 0,
                    'risk_amount': 0,
                    'stop_price': stop_price,
                    'entry_price': entry_price
                }
            
            dollar_amount = self.account_size * kelly_pct
            position_size = dollar_amount / entry_price
            
        elif self.position_sizing_method == 'volatility_based':
            # Volatility-based position sizing
            if atr is None and volatility is None:
                raise ValueError("Either ATR or volatility must be provided for volatility-based sizing")
            
            # Normalize volatility
            norm_vol = self._get_normalized_volatility(symbol, atr if atr else volatility)
            
            # Adjust risk based on volatility
            adjusted_risk = risk_pct / norm_vol
            
            dollar_risk = self.account_size * adjusted_risk
            position_size = dollar_risk / (entry_price * stop_loss_pct)
            
        else:  # fixed_size
            # Fixed size position sizing
            position_size = (self.account_size * risk_pct) / entry_price
        
        # Apply risk-of-ruin protection if enabled
        if self.risk_of_ruin_protection:
            ror_factor = self._calculate_risk_of_ruin_factor()
            position_size *= ror_factor
        
        # Apply performance adjustment if enabled
        if self.performance_adjustment:
            perf_factor = self._get_performance_adjustment_factor()
            position_size *= perf_factor
        
        # Calculate dollar amount and risk amount
        dollar_amount = position_size * entry_price
        risk_amount = dollar_amount * stop_loss_pct
        
        # Check if adding this position would exceed the max account risk
        total_risk = self.exposure['total'] + (risk_amount / self.account_size)
        if total_risk > self.max_account_risk:
            logger.warning(f"Adding position would exceed max account risk. Adjusting size.")
            risk_reduction = self.max_account_risk / total_risk
            position_size *= risk_reduction
            dollar_amount = position_size * entry_price
            risk_amount = dollar_amount * stop_loss_pct
        
        # Check if we're exceeding the maximum number of open trades
        if len(self.positions) >= self.max_open_trades:
            logger.warning(f"Maximum number of open trades reached ({self.max_open_trades})")
            return {
                'symbol': symbol,
                'position_size': 0,
                'dollar_amount': 0,
                'risk_amount': 0,
                'stop_price': stop_price,
                'entry_price': entry_price
            }
        
        # Store the position details
        self.positions[symbol] = {
            'size': position_size,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'type': trade_type,
            'category': category,
            'correlation_group': correlation_group,
            'dollar_amount': dollar_amount,
            'risk_amount': risk_amount,
            'strategy_id': strategy_id,
            'entry_time': datetime.now(),
            'update_time': datetime.now()
        }
        
        # Update exposure tracking
        self._update_exposure()
        
        logger.info(f"Calculated position size for {symbol}: {position_size:.6f} units, "
                   f"${dollar_amount:.2f}, risk: ${risk_amount:.2f}")
        
        return {
            'symbol': symbol,
            'position_size': position_size,
            'dollar_amount': dollar_amount,
            'risk_amount': risk_amount,
            'stop_price': stop_price,
            'entry_price': entry_price
        } 