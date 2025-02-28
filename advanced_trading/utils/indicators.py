"""
Technical Indicators Module
-------------------------
Provides functions for calculating technical indicators for trading data.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Union, Dict


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a comprehensive set of technical indicators to a DataFrame.
    
    Args:
        df: DataFrame with OHLCV data (must have open, high, low, close, volume columns)
        
    Returns:
        DataFrame with added technical indicators
    """
    # Make a copy to avoid modifying the original
    df_with_indicators = df.copy()
    
    # Basic price and volume metrics
    df_with_indicators['returns'] = df_with_indicators['close'].pct_change()
    df_with_indicators['log_returns'] = np.log(df_with_indicators['close'] / df_with_indicators['close'].shift(1))
    df_with_indicators['volume_change'] = df_with_indicators['volume'].pct_change()
    
    # Price momentum over different periods
    for period in [5, 10, 20, 50]:
        df_with_indicators[f'momentum_{period}'] = df_with_indicators['close'].pct_change(periods=period)
    
    # Moving averages
    for period in [10, 20, 50, 100, 200]:
        df_with_indicators[f'sma_{period}'] = df_with_indicators['close'].rolling(window=period).mean()
        df_with_indicators[f'ema_{period}'] = df_with_indicators['close'].ewm(span=period, adjust=False).mean()
    
    # Volatility indicators
    for period in [10, 20, 50]:
        df_with_indicators[f'volatility_{period}'] = df_with_indicators['returns'].rolling(window=period).std() * np.sqrt(252)  # Annualized
    
    # Add Bollinger Bands
    for period in [20]:
        # Calculate the SMA with specified period
        df_with_indicators[f'bb_middle_{period}'] = df_with_indicators['close'].rolling(window=period).mean()
        
        # Calculate the standard deviation with specified period
        std = df_with_indicators['close'].rolling(window=period).std()
        
        # Calculate the upper and lower bands
        df_with_indicators[f'bb_upper_{period}'] = df_with_indicators[f'bb_middle_{period}'] + 2 * std
        df_with_indicators[f'bb_lower_{period}'] = df_with_indicators[f'bb_middle_{period}'] - 2 * std
        
        # Calculate %B (Bollinger Band Position)
        df_with_indicators[f'bb_width_{period}'] = (df_with_indicators[f'bb_upper_{period}'] - df_with_indicators[f'bb_lower_{period}']) / df_with_indicators[f'bb_middle_{period}']
        
        # Calculate %B
        df_with_indicators[f'bb_b_{period}'] = (df_with_indicators['close'] - df_with_indicators[f'bb_lower_{period}']) / (df_with_indicators[f'bb_upper_{period}'] - df_with_indicators[f'bb_lower_{period}'])
    
    # RSI (Relative Strength Index)
    for period in [14]:
        delta = df_with_indicators['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        
        # Calculate RS
        rs = gain / loss
        df_with_indicators[f'rsi_{period}'] = 100 - (100 / (1 + rs))
    
    # MACD (Moving Average Convergence Divergence)
    ema_fast = df_with_indicators['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df_with_indicators['close'].ewm(span=26, adjust=False).mean()
    df_with_indicators['macd'] = ema_fast - ema_slow
    df_with_indicators['macd_signal'] = df_with_indicators['macd'].ewm(span=9, adjust=False).mean()
    df_with_indicators['macd_histogram'] = df_with_indicators['macd'] - df_with_indicators['macd_signal']
    
    # Stochastic Oscillator
    for period in [14]:
        low_min = df_with_indicators['low'].rolling(window=period).min()
        high_max = df_with_indicators['high'].rolling(window=period).max()
        
        # Calculate %K
        df_with_indicators[f'stoch_k_{period}'] = 100 * (df_with_indicators['close'] - low_min) / (high_max - low_min)
        
        # Calculate %D
        df_with_indicators[f'stoch_d_{period}'] = df_with_indicators[f'stoch_k_{period}'].rolling(window=3).mean()
    
    # Average True Range (ATR)
    for period in [14]:
        high_low = df_with_indicators['high'] - df_with_indicators['low']
        high_close = np.abs(df_with_indicators['high'] - df_with_indicators['close'].shift())
        low_close = np.abs(df_with_indicators['low'] - df_with_indicators['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df_with_indicators[f'atr_{period}'] = true_range.rolling(window=period).mean()
    
    # On-Balance Volume (OBV)
    df_with_indicators['obv'] = (np.sign(df_with_indicators['close'].diff()) * df_with_indicators['volume']).fillna(0).cumsum()
    
    # Price and volume ratios
    df_with_indicators['close_to_open'] = df_with_indicators['close'] / df_with_indicators['open']
    df_with_indicators['high_to_low'] = df_with_indicators['high'] / df_with_indicators['low']
    df_with_indicators['volume_to_price'] = df_with_indicators['volume'] / df_with_indicators['close']
    
    # Ichimoku Cloud components
    high_9 = df_with_indicators['high'].rolling(window=9).max()
    low_9 = df_with_indicators['low'].rolling(window=9).min()
    df_with_indicators['ichimoku_tenkan'] = (high_9 + low_9) / 2
    
    high_26 = df_with_indicators['high'].rolling(window=26).max()
    low_26 = df_with_indicators['low'].rolling(window=26).min()
    df_with_indicators['ichimoku_kijun'] = (high_26 + low_26) / 2
    
    df_with_indicators['ichimoku_senkou_a'] = ((df_with_indicators['ichimoku_tenkan'] + df_with_indicators['ichimoku_kijun']) / 2).shift(26)
    
    high_52 = df_with_indicators['high'].rolling(window=52).max()
    low_52 = df_with_indicators['low'].rolling(window=52).min()
    df_with_indicators['ichimoku_senkou_b'] = ((high_52 + low_52) / 2).shift(26)
    
    df_with_indicators['ichimoku_chikou'] = df_with_indicators['close'].shift(-26)
    
    # Calculate day of week
    if isinstance(df_with_indicators.index, pd.DatetimeIndex):
        df_with_indicators['day_of_week'] = df_with_indicators.index.dayofweek
        df_with_indicators['month'] = df_with_indicators.index.month
    
    return df_with_indicators


def add_custom_indicators(df: pd.DataFrame, indicators: List[str]) -> pd.DataFrame:
    """
    Add only the specified indicators to the DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        indicators: List of indicator names to add
        
    Returns:
        DataFrame with added indicators
    """
    # Make a copy to avoid modifying the original
    result_df = df.copy()
    
    # Add all indicators
    all_indicators_df = add_technical_indicators(df)
    
    # Select only the requested indicators
    for indicator in indicators:
        if indicator in all_indicators_df.columns:
            result_df[indicator] = all_indicators_df[indicator]
    
    return result_df 