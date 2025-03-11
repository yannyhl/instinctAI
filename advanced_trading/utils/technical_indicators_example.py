#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating the use of the technical indicators module.

This example shows how to:
1. Calculate various technical indicators
2. Visualize indicators on price charts
3. Create trading signals based on indicators
4. Combine multiple indicators for more robust signals
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging
import yfinance as yf

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to allow imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import technical indicators
from utils.technical_indicators import (
    sma, ema, macd, bollinger_bands, rsi, stochastic, 
    adx, obv, vwap, supertrend, ichimoku_cloud
)

def fetch_data(symbol='SPY', period='1y'):
    """
    Fetch historical market data using yfinance.
    
    Parameters
    ----------
    symbol : str, default='SPY'
        Ticker symbol to fetch data for.
    period : str, default='1y'
        Period to fetch data for. Options: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'
        
    Returns
    -------
    pd.DataFrame
        DataFrame with OHLCV data.
    """
    logger.info(f"Fetching data for {symbol} over {period}")
    data = yf.download(symbol, period=period)
    return data

def plot_price_with_indicators(data, indicators, figsize=(15, 10), title=None):
    """
    Plot price chart with technical indicators.
    
    Parameters
    ----------
    data : pd.DataFrame
        DataFrame with OHLCV data.
    indicators : dict
        Dictionary of indicators to plot. Keys are indicator names, values are dictionaries with:
        - 'values': indicator values (pd.Series or dict of pd.Series)
        - 'panel': panel to plot on (0 for price panel, 1 for separate panel)
        - 'color': color for the indicator
        - 'alpha': alpha for the indicator
        - 'secondary_y': whether to plot on secondary y-axis
    figsize : tuple, default=(15, 10)
        Figure size.
    title : str, optional
        Plot title.
    """
    # Count number of separate panels needed
    n_panels = 1 + max([ind['panel'] for ind in indicators.values()])
    
    # Create figure and axes
    fig, axes = plt.subplots(n_panels, 1, figsize=figsize, sharex=True, 
                             gridspec_kw={'height_ratios': [3] + [1] * (n_panels - 1)})
    
    if n_panels == 1:
        axes = [axes]
    
    # Plot price
    axes[0].plot(data.index, data['Close'], 'k-', label='Close Price')
    axes[0].set_ylabel('Price')
    axes[0].set_title(title or 'Price Chart with Technical Indicators')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc='upper left')
    
    # Create secondary y-axis for price panel
    ax0_secondary = axes[0].twinx()
    
    # Plot indicators
    for name, ind in indicators.items():
        panel = ind['panel']
        color = ind.get('color', 'blue')
        alpha = ind.get('alpha', 1.0)
        secondary_y = ind.get('secondary_y', False)
        
        # Get the correct axis
        if panel == 0 and secondary_y:
            ax = ax0_secondary
        else:
            ax = axes[panel]
        
        # Plot the indicator
        values = ind['values']
        if isinstance(values, dict):
            # Multiple lines for this indicator
            for subname, subvalues in values.items():
                subcolor = ind.get(f'{subname}_color', color)
                subalpha = ind.get(f'{subname}_alpha', alpha)
                ax.plot(data.index, subvalues, color=subcolor, alpha=subalpha, 
                        label=f'{name} ({subname})')
        else:
            # Single line for this indicator
            ax.plot(data.index, values, color=color, alpha=alpha, label=name)
        
        # Set y-label and legend
        if panel > 0:
            ax.set_ylabel(name)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper left')
    
    # Set x-label on bottom panel
    axes[-1].set_xlabel('Date')
    
    plt.tight_layout()
    plt.show()

def generate_signals(data, indicators):
    """
    Generate trading signals based on technical indicators.
    
    Parameters
    ----------
    data : pd.DataFrame
        DataFrame with OHLCV data.
    indicators : dict
        Dictionary of indicators and their values.
        
    Returns
    -------
    pd.DataFrame
        DataFrame with signals.
    """
    signals = pd.DataFrame(index=data.index)
    signals['price'] = data['Close']
    
    # Generate signals based on SMA crossover
    if 'SMA_50' in indicators and 'SMA_200' in indicators:
        signals['sma_crossover'] = 0
        signals.loc[indicators['SMA_50'] > indicators['SMA_200'], 'sma_crossover'] = 1
        signals.loc[indicators['SMA_50'] < indicators['SMA_200'], 'sma_crossover'] = -1
    
    # Generate signals based on MACD
    if 'MACD' in indicators and 'MACD_signal' in indicators:
        signals['macd_crossover'] = 0
        signals.loc[indicators['MACD'] > indicators['MACD_signal'], 'macd_crossover'] = 1
        signals.loc[indicators['MACD'] < indicators['MACD_signal'], 'macd_crossover'] = -1
    
    # Generate signals based on RSI
    if 'RSI' in indicators:
        signals['rsi_signal'] = 0
        signals.loc[indicators['RSI'] < 30, 'rsi_signal'] = 1  # Oversold
        signals.loc[indicators['RSI'] > 70, 'rsi_signal'] = -1  # Overbought
    
    # Generate signals based on Bollinger Bands
    if all(k in indicators for k in ['BB_upper', 'BB_lower']):
        signals['bb_signal'] = 0
        signals.loc[data['Close'] < indicators['BB_lower'], 'bb_signal'] = 1  # Price below lower band
        signals.loc[data['Close'] > indicators['BB_upper'], 'bb_signal'] = -1  # Price above upper band
    
    # Generate combined signal
    signals['combined_signal'] = (
        signals['sma_crossover'].fillna(0) + 
        signals['macd_crossover'].fillna(0) + 
        signals['rsi_signal'].fillna(0) + 
        signals['bb_signal'].fillna(0)
    )
    
    # Normalize combined signal
    signals['signal'] = 0
    signals.loc[signals['combined_signal'] > 1, 'signal'] = 1
    signals.loc[signals['combined_signal'] < -1, 'signal'] = -1
    
    return signals

def plot_signals(data, signals, figsize=(15, 10), title=None):
    """
    Plot price chart with trading signals.
    
    Parameters
    ----------
    data : pd.DataFrame
        DataFrame with OHLCV data.
    signals : pd.DataFrame
        DataFrame with signals.
    figsize : tuple, default=(15, 10)
        Figure size.
    title : str, optional
        Plot title.
    """
    fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot price
    axes[0].plot(data.index, data['Close'], 'k-', label='Close Price')
    
    # Plot buy signals
    buy_signals = signals[signals['signal'] == 1]
    if not buy_signals.empty:
        axes[0].scatter(buy_signals.index, buy_signals['price'], marker='^', color='green', 
                        s=100, label='Buy Signal')
    
    # Plot sell signals
    sell_signals = signals[signals['signal'] == -1]
    if not sell_signals.empty:
        axes[0].scatter(sell_signals.index, sell_signals['price'], marker='v', color='red', 
                        s=100, label='Sell Signal')
    
    axes[0].set_ylabel('Price')
    axes[0].set_title(title or 'Price Chart with Trading Signals')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc='upper left')
    
    # Plot combined signal
    axes[1].plot(signals.index, signals['combined_signal'], 'b-', label='Combined Signal')
    axes[1].axhline(y=1, color='g', linestyle='--', alpha=0.3)
    axes[1].axhline(y=-1, color='r', linestyle='--', alpha=0.3)
    axes[1].axhline(y=0, color='k', linestyle='-', alpha=0.2)
    axes[1].set_ylabel('Signal Strength')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc='upper left')
    
    # Set x-label on bottom panel
    axes[1].set_xlabel('Date')
    
    plt.tight_layout()
    plt.show()

def main():
    print("Technical Indicators Example")
    print("---------------------------")
    
    # Fetch data
    print("\n1. Fetching market data...")
    data = fetch_data(symbol='AAPL', period='1y')
    
    print(f"Data shape: {data.shape}")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")
    
    # Calculate indicators
    print("\n2. Calculating technical indicators...")
    
    # Moving averages
    sma_50 = sma(data['Close'], window=50)
    sma_200 = sma(data['Close'], window=200)
    ema_20 = ema(data['Close'], window=20)
    
    # MACD
    macd_result = macd(data['Close'])
    
    # Bollinger Bands
    bb_result = bollinger_bands(data['Close'])
    
    # RSI
    rsi_values = rsi(data['Close'])
    
    # Stochastic Oscillator
    stoch_result = stochastic(data['High'], data['Low'], data['Close'])
    
    # ADX
    adx_result = adx(data['High'], data['Low'], data['Close'])
    
    # OBV
    obv_values = obv(data['Close'], data['Volume'])
    
    # SuperTrend
    supertrend_result = supertrend(data['High'], data['Low'], data['Close'])
    
    # Ichimoku Cloud
    ichimoku_result = ichimoku_cloud(data['High'], data['Low'], data['Close'])
    
    # VWAP (requires DatetimeIndex)
    vwap_values = vwap(data['High'], data['Low'], data['Close'], data['Volume'], reset_period='day')
    
    # Store indicators in a dictionary
    indicators = {
        'SMA_50': sma_50,
        'SMA_200': sma_200,
        'EMA_20': ema_20,
        'MACD': macd_result['macd'],
        'MACD_signal': macd_result['signal'],
        'MACD_histogram': macd_result['histogram'],
        'BB_upper': bb_result['upper'],
        'BB_middle': bb_result['middle'],
        'BB_lower': bb_result['lower'],
        'RSI': rsi_values,
        'Stoch_K': stoch_result['k'],
        'Stoch_D': stoch_result['d'],
        'ADX': adx_result['adx'],
        'DI_plus': adx_result['di_plus'],
        'DI_minus': adx_result['di_minus'],
        'OBV': obv_values,
        'SuperTrend': supertrend_result['supertrend'],
        'SuperTrend_direction': supertrend_result['direction'],
        'Tenkan_sen': ichimoku_result['tenkan_sen'],
        'Kijun_sen': ichimoku_result['kijun_sen'],
        'Senkou_span_a': ichimoku_result['senkou_span_a'],
        'Senkou_span_b': ichimoku_result['senkou_span_b'],
        'Chikou_span': ichimoku_result['chikou_span'],
        'VWAP': vwap_values
    }
    
    # Plot price with moving averages
    print("\n3. Plotting price with moving averages...")
    plot_price_with_indicators(
        data,
        {
            'SMA_50': {'values': sma_50, 'panel': 0, 'color': 'blue'},
            'SMA_200': {'values': sma_200, 'panel': 0, 'color': 'red'},
            'EMA_20': {'values': ema_20, 'panel': 0, 'color': 'green'}
        },
        title='Price with Moving Averages'
    )
    
    # Plot price with Bollinger Bands
    print("\n4. Plotting price with Bollinger Bands...")
    plot_price_with_indicators(
        data,
        {
            'Bollinger Bands': {
                'values': {
                    'upper': bb_result['upper'],
                    'middle': bb_result['middle'],
                    'lower': bb_result['lower']
                },
                'panel': 0,
                'color': 'blue',
                'upper_color': 'red',
                'middle_color': 'blue',
                'lower_color': 'green',
                'alpha': 0.3
            }
        },
        title='Price with Bollinger Bands'
    )
    
    # Plot price with MACD
    print("\n5. Plotting price with MACD...")
    plot_price_with_indicators(
        data,
        {
            'MACD': {
                'values': {
                    'macd': macd_result['macd'],
                    'signal': macd_result['signal']
                },
                'panel': 1,
                'color': 'blue',
                'signal_color': 'red'
            },
            'Histogram': {
                'values': macd_result['histogram'],
                'panel': 1,
                'color': 'green',
                'alpha': 0.5
            }
        },
        title='Price with MACD'
    )
    
    # Plot price with RSI
    print("\n6. Plotting price with RSI...")
    plot_price_with_indicators(
        data,
        {
            'RSI': {'values': rsi_values, 'panel': 1, 'color': 'purple'}
        },
        title='Price with RSI'
    )
    
    # Plot price with Stochastic Oscillator
    print("\n7. Plotting price with Stochastic Oscillator...")
    plot_price_with_indicators(
        data,
        {
            'Stochastic': {
                'values': {
                    'K': stoch_result['k'],
                    'D': stoch_result['d']
                },
                'panel': 1,
                'color': 'blue',
                'D_color': 'red'
            }
        },
        title='Price with Stochastic Oscillator'
    )
    
    # Plot price with ADX
    print("\n8. Plotting price with ADX...")
    plot_price_with_indicators(
        data,
        {
            'ADX': {'values': adx_result['adx'], 'panel': 1, 'color': 'black'},
            'DI+': {'values': adx_result['di_plus'], 'panel': 1, 'color': 'green'},
            'DI-': {'values': adx_result['di_minus'], 'panel': 1, 'color': 'red'}
        },
        title='Price with ADX'
    )
    
    # Plot price with OBV
    print("\n9. Plotting price with OBV...")
    plot_price_with_indicators(
        data,
        {
            'OBV': {'values': obv_values, 'panel': 1, 'color': 'orange'}
        },
        title='Price with On-Balance Volume'
    )
    
    # Plot price with SuperTrend
    print("\n10. Plotting price with SuperTrend...")
    plot_price_with_indicators(
        data,
        {
            'SuperTrend': {'values': supertrend_result['supertrend'], 'panel': 0, 'color': 'purple'}
        },
        title='Price with SuperTrend'
    )
    
    # Plot price with Ichimoku Cloud
    print("\n11. Plotting price with Ichimoku Cloud...")
    plot_price_with_indicators(
        data,
        {
            'Tenkan-sen': {'values': ichimoku_result['tenkan_sen'], 'panel': 0, 'color': 'red'},
            'Kijun-sen': {'values': ichimoku_result['kijun_sen'], 'panel': 0, 'color': 'blue'},
            'Senkou Span A': {'values': ichimoku_result['senkou_span_a'], 'panel': 0, 'color': 'green', 'alpha': 0.5},
            'Senkou Span B': {'values': ichimoku_result['senkou_span_b'], 'panel': 0, 'color': 'red', 'alpha': 0.5},
            'Chikou Span': {'values': ichimoku_result['chikou_span'], 'panel': 0, 'color': 'purple'}
        },
        title='Price with Ichimoku Cloud'
    )
    
    # Plot price with VWAP
    print("\n12. Plotting price with VWAP...")
    plot_price_with_indicators(
        data,
        {
            'VWAP': {'values': vwap_values, 'panel': 0, 'color': 'orange'}
        },
        title='Price with VWAP'
    )
    
    # Generate trading signals
    print("\n13. Generating trading signals...")
    signals = generate_signals(data, indicators)
    
    # Plot signals
    print("\n14. Plotting trading signals...")
    plot_signals(data, signals, title='Trading Signals')
    
    print("\nTechnical Indicators Example completed successfully!")

if __name__ == "__main__":
    main() 