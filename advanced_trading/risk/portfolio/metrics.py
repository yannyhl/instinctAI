"""
Portfolio Risk Metrics Module

This module provides functions for calculating various risk metrics at the portfolio level.
These metrics help quantify the risk and risk-adjusted performance of a portfolio, enabling
better risk management and portfolio optimization.

The module implements several common portfolio risk metrics, including:
- Sharpe Ratio: Risk-adjusted return relative to the risk-free rate
- Sortino Ratio: Risk-adjusted return focusing on downside risk
- Maximum Drawdown: The largest peak-to-trough decline
- Value at Risk (VaR): The expected worst-case loss at a given confidence level
- Conditional Value at Risk (CVaR): The expected loss beyond VaR
"""

import math
from typing import Dict, List, Optional, Union, Any, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from advanced_trading.core.observability import get_logger
from advanced_trading.core.common import validate_positive

# Initialize logger
logger = get_logger(__name__)


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    annualization_factor: float = 252
) -> float:
    """Calculate the Sharpe ratio for a series of returns.
    
    The Sharpe ratio is a measure of risk-adjusted return, calculated as the difference
    between the portfolio return and the risk-free rate, divided by the standard deviation
    of the portfolio returns.
    
    Args:
        returns (np.ndarray): Array of returns (percentage or decimal).
        risk_free_rate (float, optional): The risk-free rate. Defaults to 0.0.
        annualization_factor (float, optional): The annualization factor. Defaults to 252 (trading days).
    
    Returns:
        float: The Sharpe ratio.
    """
    # Calculate mean return and standard deviation
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)  # Use sample standard deviation
    
    # Check if std_return is close to zero
    if std_return < 1e-10:
        logger.warning("Standard deviation of returns is close to zero, Sharpe ratio may be unreliable")
        std_return = 1e-10  # Use a small value to avoid division by zero
    
    # Calculate the Sharpe ratio
    sharpe = (mean_return - risk_free_rate) / std_return
    
    # Annualize the Sharpe ratio
    sharpe_annualized = sharpe * math.sqrt(annualization_factor)
    
    return sharpe_annualized


def calculate_sortino_ratio(
    returns: np.ndarray,
    target_return: float = 0.0,
    annualization_factor: float = 252
) -> float:
    """Calculate the Sortino ratio for a series of returns.
    
    The Sortino ratio is a variation of the Sharpe ratio that uses only downside deviation
    instead of standard deviation, focusing on "bad" volatility rather than all volatility.
    
    Args:
        returns (np.ndarray): Array of returns (percentage or decimal).
        target_return (float, optional): The target return or minimum acceptable return. Defaults to 0.0.
        annualization_factor (float, optional): The annualization factor. Defaults to 252 (trading days).
    
    Returns:
        float: The Sortino ratio.
    """
    # Calculate mean return
    mean_return = np.mean(returns)
    
    # Calculate downside returns (returns below the target)
    downside_returns = returns[returns < target_return]
    
    # Calculate downside deviation (standard deviation of downside returns)
    if len(downside_returns) > 0:
        downside_deviation = np.std(downside_returns, ddof=1)
    else:
        logger.info("No downside returns found, using a small value for downside deviation")
        downside_deviation = 1e-10  # Use a small value if there are no downside returns
    
    # Check if downside_deviation is close to zero
    if downside_deviation < 1e-10:
        logger.warning("Downside deviation is close to zero, Sortino ratio may be unreliable")
        downside_deviation = 1e-10  # Use a small value to avoid division by zero
    
    # Calculate the Sortino ratio
    sortino = (mean_return - target_return) / downside_deviation
    
    # Annualize the Sortino ratio
    sortino_annualized = sortino * math.sqrt(annualization_factor)
    
    return sortino_annualized


def calculate_max_drawdown(
    returns: np.ndarray,
    as_percentage: bool = True
) -> float:
    """Calculate the maximum drawdown for a series of returns.
    
    Maximum drawdown is the maximum observed loss from a peak to a trough of a portfolio,
    before a new peak is attained.
    
    Args:
        returns (np.ndarray): Array of returns (percentage or decimal).
        as_percentage (bool, optional): Whether to return the result as a percentage. Defaults to True.
    
    Returns:
        float: The maximum drawdown.
    """
    # Convert returns to cumulative returns
    cumulative_returns = (1 + returns).cumprod()
    
    # Calculate the running maximum
    running_max = np.maximum.accumulate(cumulative_returns)
    
    # Calculate drawdowns
    drawdowns = (cumulative_returns / running_max) - 1
    
    # Find the maximum drawdown
    max_drawdown = np.min(drawdowns)
    
    # Convert to percentage if requested
    if as_percentage and not np.isnan(max_drawdown):
        max_drawdown *= 100
    
    return max_drawdown


def calculate_var(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    method: str = "historical",
    portfolio_value: Optional[float] = None
) -> float:
    """Calculate Value at Risk (VaR) for a series of returns.
    
    Value at Risk (VaR) is a measure of the potential loss in value of a risky asset or portfolio
    over a defined period for a given confidence interval.
    
    Args:
        returns (np.ndarray): Array of returns (percentage or decimal).
        confidence_level (float, optional): The confidence level (e.g., 0.95 for 95%). Defaults to 0.95.
        method (str, optional): The method to use for calculating VaR.
            Options are "historical", "parametric", or "monte_carlo". Defaults to "historical".
        portfolio_value (Optional[float], optional): The current portfolio value.
            If provided, VaR will be returned in currency units. Defaults to None.
    
    Returns:
        float: The Value at Risk (VaR) as a positive number.
    
    Raises:
        ValueError: If the method is not recognized or if confidence_level is not valid.
    """
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")
    
    # Calculate VaR based on the specified method
    if method == "historical":
        # Historical VaR: percentile of the historical returns
        var = -np.percentile(returns, 100 * (1 - confidence_level))
    
    elif method == "parametric":
        # Parametric VaR: assuming normally distributed returns
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        var = -mean - std * stats.norm.ppf(confidence_level)
    
    elif method == "monte_carlo":
        # Monte Carlo VaR: simulate returns based on historical distribution
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        simulated_returns = np.random.normal(mean, std, size=10000)
        var = -np.percentile(simulated_returns, 100 * (1 - confidence_level))
    
    else:
        raise ValueError(f"Unknown method: {method}. Choose from 'historical', 'parametric', or 'monte_carlo'")
    
    # Convert to currency units if portfolio_value is provided
    if portfolio_value is not None:
        var = portfolio_value * var
    
    # Ensure VaR is positive
    var = abs(var)
    
    return var


def calculate_cvar(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    method: str = "historical",
    portfolio_value: Optional[float] = None
) -> float:
    """Calculate Conditional Value at Risk (CVaR) for a series of returns.
    
    Conditional Value at Risk (CVaR), also known as Expected Shortfall (ES), is the expected
    loss given that the loss exceeds the Value at Risk (VaR).
    
    Args:
        returns (np.ndarray): Array of returns (percentage or decimal).
        confidence_level (float, optional): The confidence level (e.g., 0.95 for 95%). Defaults to 0.95.
        method (str, optional): The method to use for calculating CVaR.
            Options are "historical", "parametric", or "monte_carlo". Defaults to "historical".
        portfolio_value (Optional[float], optional): The current portfolio value.
            If provided, CVaR will be returned in currency units. Defaults to None.
    
    Returns:
        float: The Conditional Value at Risk (CVaR) as a positive number.
    
    Raises:
        ValueError: If the method is not recognized or if confidence_level is not valid.
    """
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")
    
    # Calculate CVaR based on the specified method
    if method == "historical":
        # Historical CVaR: mean of returns beyond VaR
        var_threshold = np.percentile(returns, 100 * (1 - confidence_level))
        cvar = -np.mean(returns[returns <= var_threshold])
    
    elif method == "parametric":
        # Parametric CVaR: assuming normally distributed returns
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        var_threshold = mean + std * stats.norm.ppf(1 - confidence_level)
        cvar = -mean - std * stats.norm.pdf(stats.norm.ppf(1 - confidence_level)) / (1 - confidence_level)
    
    elif method == "monte_carlo":
        # Monte Carlo CVaR: simulate returns based on historical distribution
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        simulated_returns = np.random.normal(mean, std, size=10000)
        var_threshold = np.percentile(simulated_returns, 100 * (1 - confidence_level))
        cvar = -np.mean(simulated_returns[simulated_returns <= var_threshold])
    
    else:
        raise ValueError(f"Unknown method: {method}. Choose from 'historical', 'parametric', or 'monte_carlo'")
    
    # Convert to currency units if portfolio_value is provided
    if portfolio_value is not None:
        cvar = portfolio_value * cvar
    
    # Ensure CVaR is positive
    cvar = abs(cvar)
    
    return cvar 