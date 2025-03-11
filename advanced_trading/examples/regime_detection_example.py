#!/usr/bin/env python
"""
Market Regime Detection Example
----------------------------
Demonstrates Bayesian changepoint detection for identifying market regimes
and adapting trading strategies based on detected regimes.
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging
from pathlib import Path
import yfinance as yf

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import Bayesian changepoint detection
from utils.bayesian_changepoint import (
    BayesianChangepointDetector,
    detect_market_regimes,
    plot_market_regimes,
    classify_regime
)

# Import portfolio allocation for regime-based asset allocation
from utils.portfolio_allocation import (
    PortfolioAllocator,
    allocate_portfolio,
    calculate_portfolio_performance
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_market_data(symbols, start_date, end_date):
    """
    Load market data for the specified symbols using yfinance.
    
    Args:
        symbols: List of ticker symbols
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        
    Returns:
        Dictionary of DataFrames with OHLCV data
    """
    logger.info(f"Loading data for {len(symbols)} symbols from {start_date} to {end_date}")
    
    data_dict = {}
    
    for symbol in symbols:
        try:
            # Download data
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            
            # Verify we have data
            if df.empty:
                logger.warning(f"No data found for {symbol}")
                continue
                
            logger.info(f"Loaded {len(df)} days of data for {symbol}")
            data_dict[symbol] = df
            
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {str(e)}")
    
    return data_dict

def calculate_returns(data_dict):
    """
    Calculate returns for each symbol in the data dictionary.
    
    Args:
        data_dict: Dictionary of DataFrames with OHLCV data
        
    Returns:
        Dictionary of Series with daily returns
    """
    returns_dict = {}
    
    for symbol, df in data_dict.items():
        # Calculate daily returns
        returns = df['Close'].pct_change().dropna()
        returns_dict[symbol] = returns
        
    return returns_dict

def detect_regimes_for_symbols(returns_dict, threshold=0.4):
    """
    Detect market regimes for each symbol.
    
    Args:
        returns_dict: Dictionary of Series with daily returns
        threshold: Probability threshold for changepoint detection
        
    Returns:
        Dictionary with regime information for each symbol
    """
    regimes_dict = {}
    
    for symbol, returns in returns_dict.items():
        logger.info(f"Detecting regimes for {symbol}")
        regimes = detect_market_regimes(returns, threshold)
        regimes_dict[symbol] = regimes
        
        logger.info(f"Detected {regimes['n_segments']} regimes for {symbol}")
        for i, segment in enumerate(regimes['segments']):
            logger.info(f"  Regime {i+1}: {segment['start_date'].strftime('%Y-%m-%d')} to "
                      f"{segment['end_date'].strftime('%Y-%m-%d')} - {segment['regime']}")
    
    return regimes_dict

def visualize_regimes(returns_dict, regimes_dict, output_dir):
    """
    Create visualizations of detected regimes.
    
    Args:
        returns_dict: Dictionary of Series with daily returns
        regimes_dict: Dictionary with regime information for each symbol
        output_dir: Directory to save visualizations
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for symbol, returns in returns_dict.items():
        logger.info(f"Creating visualization for {symbol}")
        
        # Plot market regimes
        fig = plot_market_regimes(returns, threshold=0.4)
        fig.savefig(os.path.join(output_dir, f"{symbol}_regimes.png"))
        plt.close(fig)
        
        # Create a more detailed plot showing regime characteristics
        regimes = regimes_dict[symbol]
        segments = regimes['segments']
        
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 15), sharex=True)
        
        # Calculate cumulative returns
        cum_returns = (1 + returns).cumprod()
        
        # Plot cumulative returns
        ax1.plot(cum_returns, color='gray', alpha=0.7)
        ax1.set_title(f"{symbol} Cumulative Returns with Regime Detection")
        ax1.set_ylabel("Cumulative Return")
        
        # Plot returns volatility by regime
        for i, segment in enumerate(segments):
            start_date = segment['start_date']
            end_date = segment['end_date']
            segment_label = segment['regime']
            
            # Shade region
            ax1.axvspan(start_date, end_date, alpha=0.2, color=f'C{i%10}')
            
            # Add regime label
            y_pos = 0.9 - (i % 3) * 0.05  # Stagger labels to avoid overlap
            ax1.text(start_date + (end_date - start_date)/2, ax1.get_ylim()[1] * y_pos,
                   segment_label, ha='center', fontweight='bold')
        
        # Plot annualized volatility by segment
        for i, segment in enumerate(segments):
            start_date = segment['start_date']
            end_date = segment['end_date']
            volatility = segment['volatility'] * np.sqrt(252)  # Annualize
            
            # Add horizontal line for this segment's volatility
            ax2.axhline(y=volatility, xmin=start_date, xmax=end_date, 
                      color=f'C{i%10}', linewidth=2, label=f"Regime {i+1}")
            
            # Shade region
            ax2.axvspan(start_date, end_date, alpha=0.2, color=f'C{i%10}')
            
            # Add volatility label
            ax2.text(start_date + (end_date - start_date)/2, volatility * 1.05, 
                   f"{volatility:.1%}", ha='center')
        
        # Plot rolling volatility
        rolling_vol = returns.rolling(window=21).std() * np.sqrt(252)  # 21-day rolling window, annualized
        ax2.plot(rolling_vol, color='gray', alpha=0.5)
        ax2.set_ylabel("Annualized Volatility")
        
        # Plot annualized returns by segment
        for i, segment in enumerate(segments):
            start_date = segment['start_date']
            end_date = segment['end_date']
            mean_return = segment['mean'] * 252  # Annualize
            
            # Add horizontal line for this segment's mean return
            ax3.axhline(y=mean_return, xmin=start_date, xmax=end_date, 
                      color=f'C{i%10}', linewidth=2)
            
            # Shade region
            ax3.axvspan(start_date, end_date, alpha=0.2, color=f'C{i%10}')
            
            # Add mean return label
            ax3.text(start_date + (end_date - start_date)/2, mean_return * 1.1, 
                   f"{mean_return:.1%}", ha='center')
        
        # Plot rolling returns
        rolling_mean = returns.rolling(window=63).mean() * 252  # 63-day rolling window, annualized
        ax3.plot(rolling_mean, color='gray', alpha=0.5)
        ax3.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax3.set_ylabel("Annualized Return")
        
        # Plot Sharpe ratio by segment
        for i, segment in enumerate(segments):
            start_date = segment['start_date']
            end_date = segment['end_date']
            sharpe = segment['sharpe']
            
            # Add horizontal line for this segment's Sharpe
            ax4.axhline(y=sharpe, xmin=start_date, xmax=end_date, 
                      color=f'C{i%10}', linewidth=2)
            
            # Shade region
            ax4.axvspan(start_date, end_date, alpha=0.2, color=f'C{i%10}')
            
            # Add Sharpe label
            ax4.text(start_date + (end_date - start_date)/2, sharpe * 1.1, 
                   f"{sharpe:.2f}", ha='center')
        
        # Plot rolling Sharpe
        rolling_sharpe = (rolling_mean / rolling_vol)
        ax4.plot(rolling_sharpe, color='gray', alpha=0.5)
        ax4.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax4.set_ylabel("Sharpe Ratio")
        ax4.set_xlabel("Date")
        
        plt.tight_layout()
        fig.savefig(os.path.join(output_dir, f"{symbol}_regime_analysis.png"))
        plt.close(fig)

def create_regime_based_strategy(returns_dict, regimes_dict):
    """
    Create a regime-based strategy that adapts allocation based on detected regimes.
    
    Args:
        returns_dict: Dictionary of Series with daily returns
        regimes_dict: Dictionary with regime information for each symbol
        
    Returns:
        DataFrame with strategy performance
    """
    # Get list of symbols
    symbols = list(returns_dict.keys())
    
    # First, create a DataFrame with all returns aligned by date
    all_returns = pd.DataFrame({symbol: returns for symbol, returns in returns_dict.items()})
    
    # Initialize strategy returns series
    strategy_returns = pd.Series(index=all_returns.index, dtype=float)
    
    # Initialize portfolio allocation for each date
    allocations = pd.DataFrame(index=all_returns.index, columns=symbols)
    
    # Set initial equal allocation
    initial_allocation = {symbol: 1.0 / len(symbols) for symbol in symbols}
    
    # Fill initial allocations
    for symbol in symbols:
        allocations[symbol] = initial_allocation[symbol]
    
    # Define allocation strategy for each regime type
    regime_allocations = {
        # Bullish regimes: favor higher allocations
        "Bull-Volatile": 0.8,
        "Bull-Stable": 1.0,
        "Choppy-Bullish": 0.6,
        "Slow-Bullish": 0.8,
        
        # Bearish regimes: reduced allocations
        "Bear-Volatile": 0.0,    # Avoid volatile bear markets
        "Bear-Stable": 0.1,      # Small allocation in stable bear markets
        "Choppy-Bearish": 0.2,   # Small allocation in choppy bear markets
        "Slow-Bearish": 0.3,     # Moderate allocation in slow bear markets
        
        # Default for any other regime type
        "default": 0.5
    }
    
    # For each date, determine the current regime for each symbol and adjust allocation
    for date in all_returns.index:
        # Find current regime for each symbol
        current_regimes = {}
        
        for symbol, regimes in regimes_dict.items():
            current_regime = None
            
            for segment in regimes['segments']:
                if segment['start_date'] <= date <= segment['end_date']:
                    current_regime = segment['regime']
                    break
            
            # Store the base regime class (remove refinements)
            if current_regime:
                base_regime = current_regime.split('-')[0] + '-' + current_regime.split('-')[1]
                current_regimes[symbol] = base_regime
        
        # Adjust allocations based on regimes
        total_allocation = 0
        
        for symbol in symbols:
            if symbol in current_regimes:
                regime = current_regimes[symbol]
                # Get allocation for this regime
                regime_alloc = regime_allocations.get(regime, regime_allocations['default'])
                allocations.loc[date, symbol] = regime_alloc
                total_allocation += regime_alloc
        
        # Normalize allocations to sum to 1
        if total_allocation > 0:
            for symbol in symbols:
                allocations.loc[date, symbol] = allocations.loc[date, symbol] / total_allocation
    
    # Initialize portfolio value at 1.0
    portfolio_value = 1.0
    portfolio_values = [portfolio_value]
    
    # Calculate strategy returns
    prev_date = None
    
    for date in all_returns.index[1:]:  # Skip first date as we don't have returns
        # Get previous date for allocations
        if prev_date is None:
            prev_date = all_returns.index[0]
        
        # Get returns for current date
        date_returns = all_returns.loc[date]
        
        # Get allocations from previous date
        date_allocations = allocations.loc[prev_date]
        
        # Calculate weighted return
        strategy_return = 0
        for symbol in symbols:
            if not np.isnan(date_returns[symbol]) and not np.isnan(date_allocations[symbol]):
                strategy_return += date_returns[symbol] * date_allocations[symbol]
        
        # Store strategy return
        strategy_returns.loc[date] = strategy_return
        
        # Update portfolio value
        portfolio_value *= (1 + strategy_return)
        portfolio_values.append(portfolio_value)
        
        # Update previous date
        prev_date = date
    
    # Create strategy performance DataFrame
    strategy_performance = pd.DataFrame({
        'returns': strategy_returns,
        'cumulative_returns': pd.Series(portfolio_values, index=all_returns.index) - 1,
        'portfolio_value': pd.Series(portfolio_values, index=all_returns.index)
    })
    
    # Calculate benchmark (equal weighted)
    benchmark_returns = all_returns.mean(axis=1)
    benchmark_values = (1 + benchmark_returns).cumprod()
    
    strategy_performance['benchmark_returns'] = benchmark_returns
    strategy_performance['benchmark_value'] = benchmark_values
    
    return strategy_performance, allocations

def evaluate_regime_strategy(strategy_performance, allocations, output_dir):
    """
    Evaluate and visualize the regime-based strategy performance.
    
    Args:
        strategy_performance: DataFrame with strategy performance
        allocations: DataFrame with allocations over time
        output_dir: Directory to save visualizations
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate performance metrics
    strategy_returns = strategy_performance['returns'].dropna()
    benchmark_returns = strategy_performance['benchmark_returns'].dropna()
    
    # Calculate annualized return
    strategy_annual_return = strategy_returns.mean() * 252
    benchmark_annual_return = benchmark_returns.mean() * 252
    
    # Calculate volatility
    strategy_volatility = strategy_returns.std() * np.sqrt(252)
    benchmark_volatility = benchmark_returns.std() * np.sqrt(252)
    
    # Calculate Sharpe ratio (assuming 0% risk-free rate for simplicity)
    strategy_sharpe = strategy_annual_return / strategy_volatility
    benchmark_sharpe = benchmark_annual_return / benchmark_volatility
    
    # Calculate maximum drawdown
    strategy_cum_returns = strategy_performance['cumulative_returns']
    strategy_peak = strategy_cum_returns.cummax()
    strategy_drawdown = (strategy_cum_returns - strategy_peak) / strategy_peak
    max_drawdown = strategy_drawdown.min()
    
    # Calculate benchmark drawdown
    benchmark_cum_returns = strategy_performance['benchmark_value'] - 1
    benchmark_peak = benchmark_cum_returns.cummax()
    benchmark_drawdown = (benchmark_cum_returns - benchmark_peak) / benchmark_peak
    benchmark_max_drawdown = benchmark_drawdown.min()
    
    # Log performance metrics
    logger.info("Regime-Based Strategy Performance:")
    logger.info(f"  Annual Return: {strategy_annual_return:.2%} (Benchmark: {benchmark_annual_return:.2%})")
    logger.info(f"  Volatility: {strategy_volatility:.2%} (Benchmark: {benchmark_volatility:.2%})")
    logger.info(f"  Sharpe Ratio: {strategy_sharpe:.2f} (Benchmark: {benchmark_sharpe:.2f})")
    logger.info(f"  Max Drawdown: {max_drawdown:.2%} (Benchmark: {benchmark_max_drawdown:.2%})")
    
    # Create performance visualization
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 15), gridspec_kw={'height_ratios': [3, 1, 1]})
    
    # Plot portfolio value vs benchmark
    ax1.plot(strategy_performance.index, strategy_performance['portfolio_value'], 
           label='Regime-Based Strategy', linewidth=2)
    ax1.plot(strategy_performance.index, strategy_performance['benchmark_value'], 
           label='Equal-Weight Benchmark', linewidth=2, alpha=0.7)
    
    ax1.set_title('Regime-Based Strategy Performance')
    ax1.set_ylabel('Portfolio Value')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot drawdowns
    ax2.fill_between(strategy_performance.index, 0, strategy_drawdown * 100, 
                    color='red', alpha=0.3, label='Strategy Drawdown')
    ax2.fill_between(strategy_performance.index, 0, benchmark_drawdown * 100, 
                    color='blue', alpha=0.3, label='Benchmark Drawdown')
    
    ax2.set_ylabel('Drawdown (%)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot allocation over time
    ax3.stackplot(allocations.index, allocations.T.values, 
                 labels=allocations.columns, alpha=0.7)
    
    ax3.set_ylabel('Allocation')
    ax3.set_xlabel('Date')
    ax3.legend(loc='upper left', fontsize='small')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, 'regime_strategy_performance.png'))
    plt.close(fig)
    
    # Save performance data
    strategy_performance.to_csv(os.path.join(output_dir, 'regime_strategy_performance.csv'))
    
    # Create a performance summary table
    performance_summary = pd.DataFrame({
        'Metric': ['Annual Return', 'Volatility', 'Sharpe Ratio', 'Max Drawdown'],
        'Strategy': [f"{strategy_annual_return:.2%}", f"{strategy_volatility:.2%}", 
                    f"{strategy_sharpe:.2f}", f"{max_drawdown:.2%}"],
        'Benchmark': [f"{benchmark_annual_return:.2%}", f"{benchmark_volatility:.2%}", 
                     f"{benchmark_sharpe:.2f}", f"{benchmark_max_drawdown:.2%}"]
    })
    
    performance_summary.to_csv(os.path.join(output_dir, 'performance_summary.csv'), index=False)
    
    return {
        'annual_return': float(strategy_annual_return),
        'volatility': float(strategy_volatility),
        'sharpe_ratio': float(strategy_sharpe),
        'max_drawdown': float(max_drawdown),
        'benchmark_annual_return': float(benchmark_annual_return),
        'benchmark_volatility': float(benchmark_volatility),
        'benchmark_sharpe': float(benchmark_sharpe),
        'benchmark_max_drawdown': float(benchmark_max_drawdown)
    }

def main():
    """Main function to run the market regime detection example."""
    logger.info("Starting Market Regime Detection Example")
    
    # Create output directory
    output_dir = os.path.join(script_dir, 'results', 'regime_detection')
    os.makedirs(output_dir, exist_ok=True)
    
    # Define symbols to analyze (major US indices and Bitcoin)
    symbols = ['SPY', 'QQQ', 'IWM', 'GLD', 'TLT', 'BTC-USD']
    
    # Set date range (5 years)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
    
    # Load market data
    data_dict = load_market_data(symbols, start_date, end_date)
    
    # Calculate returns
    returns_dict = calculate_returns(data_dict)
    
    # Detect regimes
    regimes_dict = detect_regimes_for_symbols(returns_dict)
    
    # Visualize regimes
    visualize_regimes(returns_dict, regimes_dict, output_dir)
    
    # Create and evaluate regime-based strategy
    strategy_performance, allocations = create_regime_based_strategy(returns_dict, regimes_dict)
    
    performance_metrics = evaluate_regime_strategy(
        strategy_performance, allocations, output_dir)
    
    logger.info("Market Regime Detection Example completed successfully.")
    logger.info(f"Results saved to {output_dir}")

if __name__ == "__main__":
    main() 