#!/usr/bin/env python3

"""
Script to modify utils/indicators.py to use pandas-ta instead of TA-Lib
"""

import os
import shutil

# Define the path to the original file
file_path = 'instinct_ai/utils/indicators.py'

# Create a backup of the original file
backup_path = file_path + '.backup'
shutil.copy2(file_path, backup_path)
print(f"Created backup at: {backup_path}")

# New content for the indicators.py file
new_content = """\"\"\"
Technical Indicators Module (pandas-ta version)
--------------------------
Provides functions for calculating technical indicators
\"\"\"

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any
import logging

# Import pandas_ta (alternative to TA-Lib)
import pandas_ta as ta

logger = logging.getLogger(__name__)

def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    \"\"\"Calculate Simple Moving Average\"\"\"
    return data.rolling(window=period).mean()

def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    \"\"\"Calculate Exponential Moving Average\"\"\"
    return data.ewm(span=period, adjust=False).mean()

def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    \"\"\"Calculate Relative Strength Index\"\"\"
    return pd.Series(ta.rsi(data, length=period), index=data.index)

def calculate_macd(data: pd.Series, fast_period: int = 12, 
                  slow_period: int = 26, signal_period: int = 9) -> pd.DataFrame:
    \"\"\"Calculate MACD (Moving Average Convergence Divergence)\"\"\"
    macd = ta.macd(data, fast=fast_period, slow=slow_period, signal=signal_period)
    return pd.DataFrame({
        'macd': macd['MACD_' + str(fast_period) + '_' + str(slow_period) + '_' + str(signal_period)],
        'signal': macd['MACDs_' + str(fast_period) + '_' + str(slow_period) + '_' + str(signal_period)],
        'histogram': macd['MACDh_' + str(fast_period) + '_' + str(slow_period) + '_' + str(signal_period)]
    }, index=data.index)

def calculate_bollinger_bands(data: pd.Series, period: int = 20, 
                             num_std: float = 2.0) -> pd.DataFrame:
    \"\"\"Calculate Bollinger Bands\"\"\"
    bbands = ta.bbands(data, length=period, std=num_std)
    return pd.DataFrame({
        'upper': bbands['BBU_' + str(period) + '_' + str(float(num_std))],
        'middle': bbands['BBM_' + str(period) + '_' + str(float(num_std))],
        'lower': bbands['BBL_' + str(period) + '_' + str(float(num_std))]
    }, index=data.index)

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, 
                period: int = 14) -> pd.Series:
    \"\"\"Calculate Average True Range\"\"\"
    df = pd.DataFrame({'high': high, 'low': low, 'close': close})
    atr = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=period)
    return pd.Series(atr, index=high.index)

def calculate_stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                        k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    \"\"\"Calculate Stochastic Oscillator\"\"\"
    df = pd.DataFrame({'high': high, 'low': low, 'close': close})
    stoch = ta.stoch(high=df['high'], low=df['low'], close=df['close'], k=k_period, d=d_period)
    return pd.DataFrame({
        'k': stoch['STOCHk_' + str(k_period) + '_' + str(d_period) + '_3'],
        'd': stoch['STOCHd_' + str(k_period) + '_' + str(d_period) + '_3']
    }, index=high.index)

def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    \"\"\"Calculate On-Balance Volume\"\"\"
    df = pd.DataFrame({'close': close, 'volume': volume})
    obv = ta.obv(close=df['close'], volume=df['volume'])
    return pd.Series(obv, index=close.index)

def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    \"\"\"Add common technical indicators to a DataFrame of OHLCV data\"\"\"
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
"""

# Write the new content to the file
with open(file_path, 'w') as f:
    f.write(new_content)

print(f"Updated {file_path} to use pandas-ta instead of TA-Lib")
print("To apply the changes, install pandas-ta with: pip install pandas-ta")