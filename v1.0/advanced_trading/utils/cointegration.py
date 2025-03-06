# advanced_trading/utils/cointegration.py

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint, adfuller
from itertools import combinations
from typing import List, Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)

def check_cointegration(series1: pd.Series, series2: pd.Series, 
                       p_value_threshold: float = 0.05) -> Tuple[bool, float, float]:
    """
    Check if two price series are cointegrated.
    
    Args:
        series1: First price series
        series2: Second price series
        p_value_threshold: Maximum p-value to consider cointegrated
        
    Returns:
        Tuple of (is_cointegrated, p_value, hedge_ratio)
    """
    # Ensure both series have the same length
    min_length = min(len(series1), len(series2))
    series1 = series1[-min_length:]
    series2 = series2[-min_length:]
    
    # Check for cointegration
    result = coint(series1, series2)
    p_value = result[1]
    
    # Calculate hedge ratio using OLS
    model = sm.OLS(series1, series2).fit()
    hedge_ratio = model.params[0]
    
    is_cointegrated = p_value < p_value_threshold
    
    return is_cointegrated, p_value, hedge_ratio

def find_cointegrated_pairs(data_dict: Dict[str, pd.DataFrame], 
                          price_col: str = 'close',
                          p_value_threshold: float = 0.05) -> List[Tuple]:
    """
    Find cointegrated pairs among a set of price series.
    
    Args:
        data_dict: Dictionary of DataFrames with price data
        price_col: Column name for price data
        p_value_threshold: Maximum p-value to consider cointegrated
        
    Returns:
        List of (symbol1, symbol2, hedge_ratio, p_value) tuples
    """
    symbols = list(data_dict.keys())
    n = len(symbols)
    
    logger.info(f"Checking cointegration for {n} symbols ({n*(n-1)//2} pairs)")
    
    # Store price series for each symbol
    price_series = {}
    for symbol, df in data_dict.items():
        if price_col in df.columns:
            price_series[symbol] = df[price_col]
    
    # Check all possible pairs
    cointegrated_pairs = []
    
    for i, j in combinations(range(n), 2):
        symbol1 = symbols[i]
        symbol2 = symbols[j]
        
        if symbol1 not in price_series or symbol2 not in price_series:
            continue
        
        series1 = price_series[symbol1]
        series2 = price_series[symbol2]
        
        # Check for cointegration
        is_cointegrated, p_value, hedge_ratio = check_cointegration(
            series1, series2, p_value_threshold
        )
        
        if is_cointegrated:
            pair = (symbol1, symbol2, hedge_ratio, p_value)
            cointegrated_pairs.append(pair)
            
            logger.info(f"Found cointegrated pair: {symbol1} and {symbol2}, "
                      f"p-value: {p_value:.6f}, hedge ratio: {hedge_ratio:.4f}")
    
    # Sort by p-value (strongest cointegration first)
    cointegrated_pairs.sort(key=lambda x: x[3])
    
    logger.info(f"Found {len(cointegrated_pairs)} cointegrated pairs")
    
    return cointegrated_pairs

def calculate_spread(series1: pd.Series, series2: pd.Series, 
                   hedge_ratio: float) -> pd.Series:
    """
    Calculate the spread between two series using a hedge ratio.
    
    Args:
        series1: First price series
        series2: Second price series
        hedge_ratio: Hedge ratio to apply
        
    Returns:
        Spread series
    """
    return series1 - hedge_ratio * series2

def calculate_zscore(spread: pd.Series, window: int = 20) -> pd.Series:
    """
    Calculate z-score of a spread.
    
    Args:
        spread: Spread series
        window: Window for rolling mean and std
        
    Returns:
        Z-score series
    """
    spread_mean = spread.rolling(window=window).mean()
    spread_std = spread.rolling(window=window).std()
    
    return (spread - spread_mean) / spread_std

def is_stationary(series: pd.Series, threshold: float = 0.05) -> bool:
    """
    Test if a series is stationary using Augmented Dickey-Fuller test.
    
    Args:
        series: Series to test
        threshold: P-value threshold
        
    Returns:
        True if series is stationary, False otherwise
    """
    result = adfuller(series.dropna())
    return result[1] < threshold