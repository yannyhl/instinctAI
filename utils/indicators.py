"""
Technical Indicators Module
--------------------------
Provides functions for calculating technical indicators
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any
import logging

logger = logging.getLogger(__name__)

# Try to import TA-Lib, fallback to pandas-based implementations if not available
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    logger.warning("TA-Lib not available, using pandas-based implementations instead")
    TALIB_AVAILABLE = False

def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return data.rolling(window=period).mean()

def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return data.ewm(span=period, adjust=False).mean()

def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index"""
    if TALIB_AVAILABLE:
        return pd.Series(talib.RSI(data.values, timeperiod=period), index=data.index)
    
    # Pandas implementation
    delta = data.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data: pd.Series, fast_period: int = 12, 
                  slow_period: int = 26, signal_period: int = 9) -> pd.DataFrame:
    """Calculate MACD (Moving Average Convergence Divergence)"""
    if TALIB_AVAILABLE:
        macd, signal, hist = talib.MACD(
            data.values, 
            fastperiod=fast_period, 
            slowperiod=slow_period, 
            signalperiod=signal_period
        )
        return pd.DataFrame({
            'macd': macd,
            'signal': signal,
            'histogram': hist
        }, index=data.index)
    
    # Pandas implementation
    ema_fast = calculate_ema(data, fast_period)
    ema_slow = calculate_ema(data, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return pd.DataFrame({
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }, index=data.index)

def calculate_bollinger_bands(data: pd.Series, period: int = 20, 
                             num_std: float = 2.0) -> pd.DataFrame:
    """Calculate Bollinger Bands"""
    if TALIB_AVAILABLE:
        upper, middle, lower = talib.BBANDS(
            data.values, 
            timeperiod=period, 
            nbdevup=num_std, 
            nbdevdn=num_std
        )
        return pd.DataFrame({
            'upper': upper,
            'middle': middle,
            'lower': lower
        }, index=data.index)
    
    # Pandas implementation
    middle = calculate_sma(data, period)
    std = data.rolling(window=period).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    
    return pd.DataFrame({
        'upper': upper,
        'middle': middle,
        'lower': lower
    }, index=data.index)

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, 
                period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    if TALIB_AVAILABLE:
        return pd.Series(
            talib.ATR(high.values, low.values, close.values, timeperiod=period),
            index=high.index
        )
    
    # Pandas implementation
    high_low = high - low
    high_close_prev = abs(high - close.shift(1))
    low_close_prev = abs(low - close.shift(1))
    
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                        k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Calculate Stochastic Oscillator"""
    if TALIB_AVAILABLE:
        k, d = talib.STOCH(
            high.values, 
            low.values, 
            close.values, 
            fastk_period=k_period, 
            slowk_period=3, 
            slowk_matype=0, 
            slowd_period=d_period, 
            slowd_matype=0
        )
        return pd.DataFrame({
            'k': k,
            'd': d
        }, index=high.index)
    
    # Pandas implementation
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    # %K calculation
    k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    
    # %D calculation (3-period SMA of %K)
    d = k.rolling(window=d_period).mean()
    
    return pd.DataFrame({
        'k': k,
        'd': d
    }, index=high.index)

def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume"""
    if TALIB_AVAILABLE:
        return pd.Series(talib.OBV(close.values, volume.values), index=close.index)
    
    # Pandas implementation
    obv = pd.Series(0, index=close.index)
    
    # Calculate daily price changes
    price_changes = close.diff()
    
    # Update OBV based on price changes
    for i in range(1, len(close)):
        if price_changes.iloc[i] > 0:
            obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
        elif price_changes.iloc[i] < 0:
            obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    
    return obv

def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Add common technical indicators to a DataFrame of OHLCV data"""
    try:
        # Create a copy to avoid modifying the original
        df = data.copy()
        
        # Ensure required columns exist
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            return df
        
        # Add moving averages
        df['sma20'] = calculate_sma(df['close'], 20)
        df['sma50'] = calculate_sma(df['close'], 50)
        df['sma200'] = calculate_sma(df['close'], 200)
        df['ema20'] = calculate_ema(df['close'], 20)
        df['ema50'] = calculate_ema(df['close'], 50)
        
        # Add RSI
        df['rsi'] = calculate_rsi(df['close'])
        
        # Add MACD
        macd_df = calculate_macd(df['close'])
        df['macd'] = macd_df['macd']
        df['macd_signal'] = macd_df['signal']
        df['macd_hist'] = macd_df['histogram']
        
        # Add Bollinger Bands
        bb_df = calculate_bollinger_bands(df['close'])
        df['bb_upper'] = bb_df['upper']
        df['bb_middle'] = bb_df['middle']
        df['bb_lower'] = bb_df['lower']
        
        # Add ATR
        df['atr'] = calculate_atr(df['high'], df['low'], df['close'])
        
        # Add Stochastic Oscillator
        stoch_df = calculate_stochastic(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch_df['k']
        df['stoch_d'] = stoch_df['d']
        
        # Add OBV
        df['obv'] = calculate_obv(df['close'], df['volume'])
        
        # Calculate price changes
        df['daily_return'] = df['close'].pct_change()
        df['volatility'] = df['daily_return'].rolling(window=20).std() * np.sqrt(20)
        
        # Remove NaN values that may be created by indicators
        df.dropna(inplace=True)
        
        return df
    
    except Exception as e:
        logger.error(f"Error adding technical indicators: {str(e)}")
        return data