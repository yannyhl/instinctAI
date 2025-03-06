"""
Math Utilities

Common mathematical functions and algorithms.
"""

import math
import numpy as np
from typing import List, Union, Optional, Tuple, Sequence, Dict, Any


def safe_divide(numerator: Union[int, float], denominator: Union[int, float], 
               default: Union[int, float] = 0) -> Union[int, float]:
    """
    Safely divide two numbers, returning a default value if the denominator is zero.
    
    Args:
        numerator: The numerator value
        denominator: The denominator value
        default: The default value to return if denominator is zero
        
    Returns:
        The division result or default value
    """
    if denominator == 0:
        return default
    return numerator / denominator


def simple_moving_average(data: Sequence[Union[int, float]], window: int) -> List[Optional[float]]:
    """
    Calculate the simple moving average for a sequence of data.
    
    Args:
        data: Sequence of numerical values
        window: Window size for the moving average
        
    Returns:
        List of moving averages (None for the first window-1 elements)
    """
    n = len(data)
    result = [None] * (window - 1)
    
    if n < window:
        return result + [sum(data) / n] if n > 0 else result
    
    # Calculate first window
    window_sum = sum(data[:window])
    result.append(window_sum / window)
    
    # Calculate remaining windows using previous sum
    for i in range(window, n):
        window_sum = window_sum - data[i - window] + data[i]
        result.append(window_sum / window)
    
    return result


def exponential_moving_average(data: Sequence[Union[int, float]], span: int) -> List[Optional[float]]:
    """
    Calculate the exponential moving average for a sequence of data.
    
    Args:
        data: Sequence of numerical values
        span: Span parameter for the EMA (similar to window in SMA)
        
    Returns:
        List of exponential moving averages
    """
    n = len(data)
    if n == 0:
        return []
    
    alpha = 2 / (span + 1)
    result = [data[0]]  # Initialize with first value
    
    for i in range(1, n):
        ema = data[i] * alpha + result[i-1] * (1 - alpha)
        result.append(ema)
    
    return result


def zscore(value: Union[int, float], mean: Union[int, float], std: Union[int, float]) -> float:
    """
    Calculate the z-score (standard score) of a value.
    
    Args:
        value: The value to calculate z-score for
        mean: The mean of the distribution
        std: The standard deviation of the distribution
        
    Returns:
        Z-score value
        
    Notes:
        Returns 0 if std is 0 to avoid division by zero
    """
    if std == 0:
        return 0
    return (value - mean) / std


def calculate_sharpe_ratio(returns: Sequence[Union[int, float]], risk_free_rate: float = 0,
                          annualization_factor: float = 252) -> float:
    """
    Calculate the Sharpe ratio for a sequence of returns.
    
    Args:
        returns: Sequence of return values
        risk_free_rate: Risk-free rate (default: 0)
        annualization_factor: Factor to annualize (252 for daily returns)
        
    Returns:
        Sharpe ratio
        
    Notes:
        Returns 0 if there are no returns or if volatility is 0
    """
    if not returns:
        return 0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate
    
    mean_excess_return = np.mean(excess_returns)
    volatility = np.std(excess_returns, ddof=1)
    
    if volatility == 0:
        return 0
    
    sharpe = mean_excess_return / volatility
    return sharpe * math.sqrt(annualization_factor)


def calculate_sortino_ratio(returns: Sequence[Union[int, float]], risk_free_rate: float = 0,
                           annualization_factor: float = 252) -> float:
    """
    Calculate the Sortino ratio for a sequence of returns.
    
    Args:
        returns: Sequence of return values
        risk_free_rate: Risk-free rate (default: 0)
        annualization_factor: Factor to annualize (252 for daily returns)
        
    Returns:
        Sortino ratio
        
    Notes:
        Returns 0 if there are no returns or if downside deviation is 0
    """
    if not returns:
        return 0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate
    
    mean_excess_return = np.mean(excess_returns)
    
    # Calculate downside deviation (standard deviation of negative returns only)
    negative_returns = excess_returns[excess_returns < 0]
    
    if len(negative_returns) == 0:
        downside_deviation = 0
    else:
        downside_deviation = np.std(negative_returns, ddof=1)
    
    if downside_deviation == 0:
        return 0
    
    sortino = mean_excess_return / downside_deviation
    return sortino * math.sqrt(annualization_factor)


def calculate_max_drawdown(values: Sequence[Union[int, float]]) -> float:
    """
    Calculate the maximum drawdown for a sequence of values.
    
    Args:
        values: Sequence of values (typically cumulative returns or equity curve)
        
    Returns:
        Maximum drawdown as a positive percentage (0-1)
        
    Notes:
        Returns 0 if there are not enough values
    """
    if len(values) < 2:
        return 0
    
    # Calculate running maximum and drawdown
    max_value = values[0]
    max_drawdown = 0
    
    for value in values:
        if value > max_value:
            max_value = value
        
        drawdown = 1 - value / max_value if max_value > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
    
    return max_drawdown


def linear_regression(x: Sequence[Union[int, float]], y: Sequence[Union[int, float]]) -> Tuple[float, float]:
    """
    Perform linear regression to find slope and intercept.
    
    Args:
        x: Independent variable values
        y: Dependent variable values
        
    Returns:
        Tuple of (slope, intercept)
        
    Notes:
        Returns (0, 0) if there are not enough data points
    """
    if len(x) != len(y) or len(x) < 2:
        return (0, 0)
    
    x_array = np.array(x)
    y_array = np.array(y)
    
    # Calculate slope and intercept
    n = len(x)
    sum_x = np.sum(x_array)
    sum_y = np.sum(y_array)
    sum_xy = np.sum(x_array * y_array)
    sum_xx = np.sum(x_array * x_array)
    
    # Calculate slope
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
    
    # Calculate intercept
    intercept = (sum_y - slope * sum_x) / n
    
    return (slope, intercept) 