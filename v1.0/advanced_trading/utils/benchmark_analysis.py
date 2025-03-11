# advanced_trading/utils/benchmark_analysis.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

def calculate_relative_metrics(strategy_returns: pd.Series, 
                             benchmark_returns: pd.Series) -> Dict[str, float]:
    """
    Calculate performance metrics relative to a benchmark.
    
    Args:
        strategy_returns: Series of strategy returns
        benchmark_returns: Series of benchmark returns
        
    Returns:
        Dictionary of relative performance metrics
    """
    # Align the series to ensure they have the same index
    strategy_returns, benchmark_returns = strategy_returns.align(benchmark_returns, join='inner')
    
    if len(strategy_returns) == 0:
        logger.warning("No matching data points between strategy and benchmark")
        return {}
    
    # Calculate excess returns
    excess_returns = strategy_returns - benchmark_returns
    
    # Calculate information ratio
    information_ratio = excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0
    
    # Calculate beta
    covariance = strategy_returns.cov(benchmark_returns)
    benchmark_variance = benchmark_returns.var()
    beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
    
    # Calculate alpha (annualized)
    annual_factor = 252  # Assuming daily returns
    strategy_mean = strategy_returns.mean() * annual_factor
    benchmark_mean = benchmark_returns.mean() * annual_factor
    alpha = strategy_mean - (beta * benchmark_mean)
    
    # Calculate up/down capture
    up_markets = benchmark_returns > 0
    down_markets = benchmark_returns < 0
    
    up_capture = (strategy_returns[up_markets].mean() / benchmark_returns[up_markets].mean()) if up_markets.any() and benchmark_returns[up_markets].mean() != 0 else 0
    down_capture = (strategy_returns[down_markets].mean() / benchmark_returns[down_markets].mean()) if down_markets.any() and benchmark_returns[down_markets].mean() != 0 else 0
    
    # Calculate tracking error
    tracking_error = excess_returns.std() * np.sqrt(annual_factor)
    
    # Calculate batting average (% of periods outperforming)
    batting_average = (strategy_returns > benchmark_returns).mean()
    
    return {
        'alpha': alpha,
        'beta': beta,
        'information_ratio': information_ratio,
        'tracking_error': tracking_error,
        'up_capture': up_capture,
        'down_capture': down_capture,
        'batting_average': batting_average
    }

def compare_to_benchmarks(strategy_data: pd.DataFrame, 
                        benchmarks: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Compare strategy performance to multiple benchmarks.
    
    Args:
        strategy_data: DataFrame with strategy returns
        benchmarks: Dictionary of benchmark DataFrames
        
    Returns:
        Dictionary of comparison results
    """
    results = {}
    
    # Extract strategy returns
    if 'strategy_returns' in strategy_data.columns:
        strategy_returns = strategy_data['strategy_returns']
    elif 'returns' in strategy_data.columns:
        strategy_returns = strategy_data['returns']
    else:
        strategy_returns = strategy_data['close'].pct_change()
    
    # Remove NaN values
    strategy_returns = strategy_returns.dropna()
    
    for benchmark_name, benchmark_data in benchmarks.items():
        logger.info(f"Comparing to benchmark: {benchmark_name}")
        
        # Extract benchmark returns
        if 'returns' in benchmark_data.columns:
            benchmark_returns = benchmark_data['returns']
        else:
            benchmark_returns = benchmark_data['close'].pct_change()
        
        # Remove NaN values
        benchmark_returns = benchmark_returns.dropna()
        
        # Calculate relative metrics
        metrics = calculate_relative_metrics(strategy_returns, benchmark_returns)
        
        # Calculate cumulative returns
        strategy_cum_returns = (1 + strategy_returns).cumprod() - 1
        benchmark_cum_returns = (1 + benchmark_returns).cumprod() - 1
        
        # Calculate drawdowns
        strategy_drawdown = calculate_drawdown(strategy_returns)
        benchmark_drawdown = calculate_drawdown(benchmark_returns)
        
        # Store results
        results[benchmark_name] = {
            'metrics': metrics,
            'strategy_cum_returns': strategy_cum_returns,
            'benchmark_cum_returns': benchmark_cum_returns,
            'strategy_drawdown': strategy_drawdown,
            'benchmark_drawdown': benchmark_drawdown
        }
    
    return results

def calculate_drawdown(returns: pd.Series) -> pd.Series:
    """
    Calculate drawdown series from returns.
    
    Args:
        returns: Series of returns
        
    Returns:
        Series of drawdowns
    """
    cumulative_returns = (1 + returns).cumprod()
    peak = cumulative_returns.cummax()
    drawdown = (cumulative_returns / peak) - 1
    return drawdown

def plot_benchmark_comparison(comparison_results: Dict[str, Any],
                           save_path: Optional[str] = None) -> plt.Figure:
    """
    Plot comparison of strategy versus benchmarks.
    
    Args:
        comparison_results: Results from compare_to_benchmarks
        save_path: Path to save the visualization
        
    Returns:
        Matplotlib figure
    """
    num_benchmarks = len(comparison_results)
    
    # Create figure
    fig = plt.figure(figsize=(15, 5 * num_benchmarks))
    
    # Plot each benchmark comparison
    for i, (benchmark_name, results) in enumerate(comparison_results.items()):
        # Plot cumulative returns
        ax1 = plt.subplot(num_benchmarks, 2, i*2 + 1)
        results['strategy_cum_returns'].plot(ax=ax1, label='Strategy', color='blue')
        results['benchmark_cum_returns'].plot(ax=ax1, label=benchmark_name, color='red')
        ax1.set_title(f'Cumulative Returns: Strategy vs {benchmark_name}')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Cumulative Return')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot drawdowns
        ax2 = plt.subplot(num_benchmarks, 2, i*2 + 2)
        results['strategy_drawdown'].plot(ax=ax2, label='Strategy', color='blue')
        results['benchmark_drawdown'].plot(ax=ax2, label=benchmark_name, color='red')
        ax2.set_title(f'Drawdowns: Strategy vs {benchmark_name}')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Drawdown')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Benchmark comparison saved to {save_path}")
    
    return fig

def create_benchmark_table(comparison_results: Dict[str, Any]) -> pd.DataFrame:
    """
    Create a table summarizing benchmark comparisons.
    
    Args:
        comparison_results: Results from compare_to_benchmarks
        
    Returns:
        DataFrame with comparison metrics
    """
    data = []
    
    for benchmark_name, results in comparison_results.items():
        metrics = results['metrics']
        
        row = {
            'Benchmark': benchmark_name,
            'Alpha': metrics.get('alpha', 0),
            'Beta': metrics.get('beta', 0),
            'Information Ratio': metrics.get('information_ratio', 0),
            'Tracking Error': metrics.get('tracking_error', 0),
            'Up Capture': metrics.get('up_capture', 0),
            'Down Capture': metrics.get('down_capture', 0),
            'Batting Average': metrics.get('batting_average', 0)
        }
        
        data.append(row)
    
    return pd.DataFrame(data)