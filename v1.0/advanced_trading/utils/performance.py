"""
Performance Analysis Utilities
---------------------------
Functions for calculating and visualizing performance metrics for trading strategies.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Optional, Union
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

def calculate_performance_metrics(results: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate comprehensive performance metrics from backtest results.
    
    Args:
        results: DataFrame with backtest results
        
    Returns:
        Dictionary of performance metrics
    """
    # Extract key data series
    portfolio_values = results['portfolio_value']
    returns = results['strategy_returns'].dropna()
    market_returns = results['returns'].dropna()
    drawdowns = results['drawdown'].dropna()
    
    # Basic return metrics
    initial_value = portfolio_values.iloc[0]
    final_value = portfolio_values.iloc[-1]
    total_return = (final_value / initial_value - 1) * 100
    
    # Annualized return (geometric mean)
    trading_days = len(returns)
    years = trading_days / 252  # Assuming 252 trading days per year
    annual_return = ((final_value / initial_value) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    # Risk metrics
    volatility = returns.std() * np.sqrt(252)  # Annualized
    market_volatility = market_returns.std() * np.sqrt(252)
    
    # Calculate Sharpe ratio (assuming 0% risk-free rate for simplicity)
    sharpe_ratio = annual_return / 100 / volatility if volatility > 0 else 0
    
    # Maximum drawdown
    max_drawdown = abs(drawdowns.min() * 100) if not drawdowns.empty else 0
    
    # Calmar ratio
    calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0
    
    # Trade metrics
    if 'trade_log' in results.attrs and not results.attrs['trade_log'].empty:
        trade_log = results.attrs['trade_log']
        num_trades = len(trade_log)
        win_rate = (trade_log['profit'] > 0).mean() * 100
        avg_profit = trade_log['profit'].mean()
        avg_profit_pct = trade_log['profit_pct'].mean()
        max_profit = trade_log['profit_pct'].max()
        max_loss = trade_log['profit_pct'].min()
        avg_duration = trade_log['duration'].mean()
        
        # Profit factor (sum of profits / sum of losses)
        profitable_trades = trade_log[trade_log['profit'] > 0]
        losing_trades = trade_log[trade_log['profit'] <= 0]
        profit_factor = 0
        if not losing_trades.empty and losing_trades['profit'].sum() != 0:
            profit_factor = abs(profitable_trades['profit'].sum() / losing_trades['profit'].sum()) if not profitable_trades.empty else 0
    else:
        num_trades = 0
        win_rate = 0
        avg_profit = 0
        avg_profit_pct = 0
        max_profit = 0
        max_loss = 0
        avg_duration = 0
        profit_factor = 0
    
    # Compile metrics
    metrics = {
        'initial_capital': float(initial_value),
        'final_capital': float(final_value),
        'total_return': float(total_return),
        'annual_return': float(annual_return),
        'volatility': float(volatility * 100),  # Convert to percentage
        'market_volatility': float(market_volatility * 100),
        'sharpe_ratio': float(sharpe_ratio),
        'max_drawdown': float(max_drawdown),
        'calmar_ratio': float(calmar_ratio),
        'win_rate': float(win_rate),
        'num_trades': int(num_trades),
        'avg_profit': float(avg_profit),
        'avg_profit_pct': float(avg_profit_pct),
        'max_profit': float(max_profit),
        'max_loss': float(max_loss),
        'avg_duration': float(avg_duration),
        'profit_factor': float(profit_factor)
    }
    
    return metrics

def plot_performance(results: pd.DataFrame) -> plt.Figure:
    """
    Create comprehensive performance visualization.
    
    Args:
        results: DataFrame with backtest results
        
    Returns:
        Matplotlib figure with performance plots
    """
    # Create figure
    fig = plt.figure(figsize=(15, 12))
    
    # Plot equity curve
    ax1 = plt.subplot(3, 2, 1)
    results['portfolio_value'].plot(ax=ax1, label='Strategy')
    ax1.set_title('Portfolio Value')
    ax1.set_ylabel('Value')
    ax1.grid(True)
    
    # Plot drawdown
    ax2 = plt.subplot(3, 2, 2)
    (results['drawdown'] * 100).plot(ax=ax2, color='red', alpha=0.5)
    ax2.set_title('Drawdown %')
    ax2.set_ylabel('Drawdown %')
    ax2.grid(True)
    
    # Plot strategy vs market returns
    ax3 = plt.subplot(3, 2, 3)
    (results['cumulative_strategy_returns'] * 100).plot(ax=ax3, label='Strategy')
    (results['cumulative_market_returns'] * 100).plot(ax=ax3, label='Market')
    ax3.set_title('Strategy vs Market Returns %')
    ax3.set_ylabel('Cumulative Returns %')
    ax3.legend()
    ax3.grid(True)
    
    # Plot monthly returns heatmap if we have enough data
    ax4 = plt.subplot(3, 2, 4)
    if len(results) > 30 and isinstance(results.index, pd.DatetimeIndex):
        # Calculate monthly returns
        monthly_returns = results['strategy_returns'].resample('M').apply(
            lambda x: (1 + x).prod() - 1
        )
        
        # Create a pivot table of monthly returns
        monthly_return_table = pd.DataFrame({
            'Year': monthly_returns.index.year,
            'Month': monthly_returns.index.month,
            'Return': monthly_returns.values
        })
        
        pivot_table = monthly_return_table.pivot_table(
            index='Year', columns='Month', values='Return'
        )
        
        # Plot heatmap
        sns.heatmap(pivot_table * 100, annot=True, fmt='.1f', cmap='RdYlGn', 
                   center=0, ax=ax4, cbar=False)
        ax4.set_title('Monthly Returns %')
    else:
        ax4.text(0.5, 0.5, 'Insufficient data for monthly returns', 
                ha='center', va='center')
    
    # Plot signal distribution
    ax5 = plt.subplot(3, 2, 5)
    results['signal'].value_counts().plot(kind='bar', ax=ax5)
    ax5.set_title('Signal Distribution')
    ax5.set_xlabel('Signal')
    ax5.set_ylabel('Count')
    ax5.set_xticklabels(ax5.get_xticklabels(), rotation=0)
    ax5.grid(True, axis='y')
    
    # Plot key metrics
    ax6 = plt.subplot(3, 2, 6)
    metrics = calculate_performance_metrics(results)
    metrics_text = [
        f"Total Return: {metrics['total_return']:.2f}%",
        f"Annual Return: {metrics['annual_return']:.2f}%",
        f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}",
        f"Max Drawdown: {metrics['max_drawdown']:.2f}%",
        f"Win Rate: {metrics['win_rate']:.2f}%",
        f"Number of Trades: {metrics['num_trades']}",
        f"Profit Factor: {metrics['profit_factor']:.2f}",
        f"Avg Profit/Loss: {metrics['avg_profit_pct']:.2f}%"
    ]
    
    ax6.axis('off')
    ax6.text(0.1, 0.9, 'Key Performance Metrics:', fontsize=12, fontweight='bold')
    
    y_pos = 0.8
    for metric in metrics_text:
        ax6.text(0.1, y_pos, metric, fontsize=10)
        y_pos -= 0.1
    
    plt.tight_layout()
    
    return fig

def plot_trade_analysis(results: pd.DataFrame) -> plt.Figure:
    """
    Create trade analysis visualization.
    
    Args:
        results: DataFrame with backtest results
        
    Returns:
        Matplotlib figure with trade analysis plots
    """
    if 'trade_log' not in results.attrs or results.attrs['trade_log'].empty:
        # Create a figure with a message
        fig = plt.figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No trade data available', ha='center', va='center', fontsize=14)
        ax.axis('off')
        return fig
    
    trade_log = results.attrs['trade_log']
    
    # Create figure
    fig = plt.figure(figsize=(15, 12))
    
    # Plot trade P&L
    ax1 = plt.subplot(2, 2, 1)
    trade_log['profit_pct'].plot(kind='bar', ax=ax1, color=trade_log['profit_pct'].apply(
        lambda x: 'green' if x > 0 else 'red'
    ))
    ax1.set_title('Trade P&L %')
    ax1.set_xlabel('Trade #')
    ax1.set_ylabel('Profit/Loss %')
    ax1.grid(True, axis='y')
    
    # Plot trade P&L distribution
    ax2 = plt.subplot(2, 2, 2)
    trade_log['profit_pct'].plot(kind='hist', bins=20, ax=ax2, alpha=0.5)
    ax2.axvline(0, color='r', linestyle='--')
    ax2.set_title('P&L Distribution')
    ax2.set_xlabel('Profit/Loss %')
    ax2.grid(True)
    
    # Plot cumulative P&L
    ax3 = plt.subplot(2, 2, 3)
    trade_log['profit'].cumsum().plot(ax=ax3)
    ax3.set_title('Cumulative P&L')
    ax3.set_xlabel('Trade #')
    ax3.set_ylabel('Cumulative Profit/Loss')
    ax3.grid(True)
    
    # Plot trade duration
    ax4 = plt.subplot(2, 2, 4)
    trade_log.plot.scatter(x='duration', y='profit_pct', ax=ax4, alpha=0.5)
    ax4.axhline(0, color='r', linestyle='--')
    ax4.set_title('Trade Duration vs P&L')
    ax4.set_xlabel('Duration (Days)')
    ax4.set_ylabel('Profit/Loss %')
    ax4.grid(True)
    
    plt.tight_layout()
    
    return fig

def compute_monthly_returns(results: pd.DataFrame) -> pd.DataFrame:
    """
    Compute monthly returns from backtest results.
    
    Args:
        results: DataFrame with backtest results
        
    Returns:
        DataFrame with monthly returns
    """
    if not isinstance(results.index, pd.DatetimeIndex):
        logger.warning("Results index is not a DatetimeIndex, cannot compute monthly returns")
        return pd.DataFrame()
    
    # Calculate monthly returns
    monthly_returns = results['strategy_returns'].resample('M').apply(
        lambda x: (1 + x).prod() - 1
    ).to_frame('strategy')
    
    # Add market returns
    monthly_market_returns = results['returns'].resample('M').apply(
        lambda x: (1 + x).prod() - 1
    )
    monthly_returns['market'] = monthly_market_returns
    
    # Add year and month columns
    monthly_returns['year'] = monthly_returns.index.year
    monthly_returns['month'] = monthly_returns.index.month
    
    return monthly_returns

def create_tear_sheet(results: pd.DataFrame, save_path: Optional[str] = None) -> None:
    """
    Create and save a comprehensive performance tear sheet.
    
    Args:
        results: DataFrame with backtest results
        save_path: Path to save the tear sheet (if None, will display instead)
    """
    # Create figure
    fig = plt.figure(figsize=(15, 20))
    
    # Plot performance overview
    plot_performance(results)
    
    # Add trade analysis
    plot_trade_analysis(results)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Tear sheet saved to {save_path}")
    else:
        plt.show() 