"""
Risk Management Utilities
------------------------
Advanced risk management functions for trading strategies.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, List, Optional, Union


def calculate_kelly_fraction(win_rate: float, win_loss_ratio: float, 
                           fraction: float = 0.5) -> float:
    """
    Calculate the optimal position size using the Kelly Criterion.
    
    Args:
        win_rate: Probability of winning (0-1)
        win_loss_ratio: Ratio of average win to average loss
        fraction: Conservative adjustment to Kelly (0-1)
        
    Returns:
        Kelly position size as a fraction of capital
    """
    # Full Kelly formula: K = W - (1-W)/R
    # Where: W = win rate, R = win/loss ratio
    if win_loss_ratio <= 0 or win_rate <= 0:
        return 0
    
    kelly = win_rate - (1 - win_rate) / win_loss_ratio
    
    # Apply the fraction (half-Kelly is common)
    kelly *= fraction
    
    # Limit to reasonable bounds (0-100%)
    kelly = max(0, min(kelly, 1.0))
    
    return kelly


def calculate_position_size(
    capital: float, 
    risk_per_trade: float, 
    stop_loss_pct: float, 
    volatility_adjustment: float = 1.0,
    min_size: float = 0.0,
    max_size: float = 1.0
) -> float:
    """
    Calculate position size based on fixed percentage risk.
    
    Args:
        capital: Available capital
        risk_per_trade: Risk per trade as a percentage of capital (0-1)
        stop_loss_pct: Stop loss percentage (0-1)
        volatility_adjustment: Adjustment factor based on current market volatility
        min_size: Minimum position size as percentage of capital
        max_size: Maximum position size as percentage of capital
        
    Returns:
        Position size in base currency
    """
    if stop_loss_pct <= 0:
        return 0
    
    # Maximum amount to risk
    risk_amount = capital * risk_per_trade
    
    # Position size based on stop loss
    position_size = risk_amount / stop_loss_pct
    
    # Adjust for volatility
    position_size *= volatility_adjustment
    
    # Convert to percentage of capital
    position_pct = position_size / capital
    
    # Apply bounds
    position_pct = max(min_size, min(position_pct, max_size))
    
    return position_pct


def calculate_adaptive_stop_loss(
    price: float, 
    atr: float, 
    multiplier: float = 2.0, 
    min_pct: float = 0.005, 
    max_pct: float = 0.1
) -> float:
    """
    Calculate adaptive stop loss based on Average True Range.
    
    Args:
        price: Current price
        atr: Average True Range value
        multiplier: Multiplier for ATR
        min_pct: Minimum stop loss percentage
        max_pct: Maximum stop loss percentage
        
    Returns:
        Stop loss price
    """
    # Calculate stop loss distance
    stop_distance = atr * multiplier
    
    # Calculate as percentage of price
    stop_pct = stop_distance / price
    
    # Apply bounds
    stop_pct = max(min_pct, min(stop_pct, max_pct))
    
    return stop_pct


def calculate_position_exposure(positions: Dict[str, Dict]) -> Dict[str, float]:
    """
    Calculate total exposure by asset class, sector, etc.
    
    Args:
        positions: Dictionary of current positions
        
    Returns:
        Dictionary of exposure by category
    """
    exposure = {
        'total_long': 0.0,
        'total_short': 0.0,
        'net': 0.0,
        'gross': 0.0,
        'categories': {}
    }
    
    for symbol, pos in positions.items():
        size = pos.get('size', 0)
        value = pos.get('value', 0)
        category = pos.get('category', 'unknown')
        
        # Update total exposures
        if size > 0:
            exposure['total_long'] += value
        else:
            exposure['total_short'] += abs(value)
        
        # Update category exposures
        if category not in exposure['categories']:
            exposure['categories'][category] = 0
        
        exposure['categories'][category] += value
    
    # Calculate net and gross exposure
    exposure['net'] = exposure['total_long'] - exposure['total_short']
    exposure['gross'] = exposure['total_long'] + exposure['total_short']
    
    return exposure


def calculate_max_drawdown(equity_curve: pd.Series) -> Tuple[float, int, int]:
    """
    Calculate maximum drawdown and its duration.
    
    Args:
        equity_curve: Series of portfolio values
        
    Returns:
        Tuple of (max_drawdown, start_index, end_index)
    """
    # Calculate running maximum
    running_max = equity_curve.cummax()
    
    # Calculate drawdown
    drawdown = equity_curve / running_max - 1
    
    # Find worst drawdown
    max_drawdown = drawdown.min()
    max_dd_idx = drawdown.idxmin()
    
    # Find when the drawdown started (last peak)
    temp = equity_curve[:max_dd_idx]
    peak_idx = temp.idxmax()
    
    return max_drawdown, peak_idx, max_dd_idx


def calculate_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Calculate Value at Risk (VaR) using historical method.
    
    Args:
        returns: Series of returns
        confidence: Confidence level (0-1)
        
    Returns:
        VaR at the given confidence level
    """
    # Sort returns
    sorted_returns = sorted(returns)
    
    # Find the index at the confidence level
    index = int((1 - confidence) * len(sorted_returns))
    
    # Return VaR (negative because it's a loss)
    return -sorted_returns[index]


def calculate_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Calculate Conditional Value at Risk (CVaR)/Expected Shortfall.
    
    Args:
        returns: Series of returns
        confidence: Confidence level (0-1)
        
    Returns:
        CVaR at the given confidence level
    """
    # Calculate VaR
    var = calculate_var(returns, confidence)
    
    # Filter returns worse than VaR
    tail_returns = returns[returns <= -var]
    
    # Calculate average of worst returns (if any)
    if len(tail_returns) > 0:
        return -tail_returns.mean()
    else:
        return var  # Fallback to VaR if no tail returns


def dynamic_risk_adjustment(
    strategy_performance: Dict[str, float],
    base_risk: float,
    min_risk: float = 0.005,
    max_risk: float = 0.03
) -> float:
    """
    Dynamically adjust risk based on recent strategy performance.
    
    Args:
        strategy_performance: Dictionary of performance metrics
        base_risk: Base risk percentage
        min_risk: Minimum risk percentage
        max_risk: Maximum risk percentage
        
    Returns:
        Adjusted risk percentage
    """
    # Extract key metrics
    sharpe = strategy_performance.get('sharpe_ratio', 0)
    recent_return = strategy_performance.get('recent_return', 0)
    
    # Adjust based on Sharpe ratio
    if sharpe > 2.0:
        # Excellent performance - increase risk
        risk_adj = base_risk * 1.2
    elif sharpe > 1.0:
        # Good performance - slight increase
        risk_adj = base_risk * 1.1
    elif sharpe < 0:
        # Poor performance - reduce risk
        risk_adj = base_risk * 0.7
    elif sharpe < 0.5:
        # Mediocre performance - slight reduction
        risk_adj = base_risk * 0.9
    else:
        # Moderate performance - keep base risk
        risk_adj = base_risk
    
    # Further adjust based on recent return
    if recent_return < -0.05:  # 5% down recently
        risk_adj *= 0.8  # Additional 20% reduction
    
    # Apply bounds
    return max(min_risk, min(risk_adj, max_risk)) 