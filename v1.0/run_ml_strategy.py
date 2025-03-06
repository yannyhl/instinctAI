#!/usr/bin/env python
"""
ML Strategy Runner
----------------
Script to run and backtest the advanced ML ensemble strategy.
"""

import os
import sys
from pathlib import Path
import argparse
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import time
import json

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import project modules
import config
from strategies.ml_strategy import MLEnsembleStrategy
from utils import risk_management as rm
from backtest.parallel_backtester import ParallelBacktester
from data.data_loader import DataLoader

# Set up logging
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run ML Ensemble Strategy')
    
    parser.add_argument('--mode', type=str, default='backtest',
                        choices=['backtest', 'optimize', 'live'],
                        help='Mode of operation')
    
    parser.add_argument('--start_date', type=str, default=config.BACKTEST_CONFIG['start_date'],
                        help='Start date for backtesting (YYYY-MM-DD)')
    
    parser.add_argument('--end_date', type=str, default=config.BACKTEST_CONFIG['end_date'],
                        help='End date for backtesting (YYYY-MM-DD)')
    
    parser.add_argument('--symbols', type=str, nargs='+',
                        default=config.TRADING_CONFIG['symbols'],
                        help='Symbols to trade')
    
    parser.add_argument('--capital', type=float, 
                        default=config.TRADING_CONFIG['initial_capital'],
                        help='Initial capital')
    
    parser.add_argument('--data_freq', type=str, 
                        default=config.BACKTEST_CONFIG['data_frequency'],
                        help='Data frequency')
    
    parser.add_argument('--parallel', action='store_true',
                        default=config.BACKTEST_CONFIG['parallel'],
                        help='Use parallel processing')
    
    parser.add_argument('--gpu', action='store_true',
                        default=config.GPU_CONFIG['use_gpu'],
                        help='Use GPU acceleration')
    
    parser.add_argument('--output_dir', type=str,
                        default=str(config.RESULTS_DIR),
                        help='Directory for saving results')
    
    args = parser.parse_args()
    return args


def load_market_data(symbols, start_date, end_date, data_freq):
    """
    Load market data for the specified symbols.
    
    Args:
        symbols: List of symbols to load
        start_date: Start date
        end_date: End date
        data_freq: Data frequency
        
    Returns:
        Dictionary of DataFrames with market data per symbol
    """
    logger.info(f"Loading market data for {len(symbols)} symbols")
    
    # Initialize data loader
    data_loader = DataLoader(
        cache_dir=config.DATA_CONFIG['cache_dir'],
        primary_source=config.DATA_CONFIG['primary'],
        api_keys=config.DATA_CONFIG['api_keys']
    )
    
    # Load data for each symbol
    data = {}
    for symbol in symbols:
        logger.info(f"Loading data for {symbol}")
        try:
            symbol_data = data_loader.load_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=data_freq
            )
            
            if symbol_data is not None and not symbol_data.empty:
                logger.info(f"Loaded {len(symbol_data)} data points for {symbol}")
                data[symbol] = symbol_data
            else:
                logger.warning(f"No data loaded for {symbol}")
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
    
    return data


def run_backtest(strategy, data, args):
    """
    Run backtest using the ParallelBacktester.
    
    Args:
        strategy: Strategy instance
        data: Dictionary of market data per symbol
        args: Command line arguments
        
    Returns:
        Backtest results
    """
    logger.info("Initializing backtester")
    
    backtester = ParallelBacktester(
        strategy=strategy,
        data=data,
        initial_capital=args.capital,
        commission=config.TRADING_CONFIG['commission'],
        slippage=config.TRADING_CONFIG['slippage'],
        start_date=args.start_date,
        end_date=args.end_date,
        use_parallel=args.parallel,
        use_gpu=args.gpu
    )
    
    logger.info("Starting backtest")
    start_time = time.time()
    
    # Run backtest
    results = backtester.run()
    
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"Backtest completed in {duration:.2f} seconds")
    
    return results


def analyze_results(results, args):
    """
    Analyze backtest results and generate reports.
    
    Args:
        results: Backtest results
        args: Command line arguments
    """
    logger.info("Analyzing backtest results")
    
    # Extract portfolio values and trade history
    portfolio_history = results['portfolio_history']
    trades = results['trades']
    
    # Calculate performance metrics
    metrics = calculate_performance_metrics(portfolio_history, trades)
    
    # Log performance summary
    logger.info(f"Performance Summary:")
    logger.info(f"Total Return: {metrics['total_return']:.2%}")
    logger.info(f"Annualized Return: {metrics['cagr']:.2%}")
    logger.info(f"Sharpe Ratio: {metrics['sharpe']:.2f}")
    logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
    logger.info(f"Win Rate: {metrics['win_rate']:.2%}")
    
    # Generate reports
    generate_reports(portfolio_history, trades, metrics, args)
    
    return metrics


def calculate_performance_metrics(portfolio_history, trades):
    """
    Calculate performance metrics from backtest results.
    
    Args:
        portfolio_history: DataFrame with portfolio history
        trades: DataFrame with trade history
        
    Returns:
        Dictionary of performance metrics
    """
    # Calculate returns
    portfolio_history['daily_return'] = portfolio_history['portfolio_value'].pct_change()
    
    # Basic metrics
    start_value = portfolio_history['portfolio_value'].iloc[0]
    end_value = portfolio_history['portfolio_value'].iloc[-1]
    total_return = (end_value / start_value) - 1
    
    # Calculate trading days and annualized return
    trading_days = (portfolio_history.index[-1] - portfolio_history.index[0]).days
    years = trading_days / 365
    cagr = (end_value / start_value) ** (1 / years) - 1 if years > 0 else 0
    
    # Risk metrics
    daily_returns = portfolio_history['daily_return'].dropna()
    annualized_volatility = daily_returns.std() * np.sqrt(252)
    sharpe = (cagr - config.TRADING_CONFIG['risk_free_rate']) / annualized_volatility if annualized_volatility > 0 else 0
    
    # Calculate downside deviation for Sortino ratio
    downside_returns = daily_returns[daily_returns < 0]
    downside_deviation = downside_returns.std() * np.sqrt(252)
    sortino = (cagr - config.TRADING_CONFIG['risk_free_rate']) / downside_deviation if downside_deviation > 0 else 0
    
    # Maximum drawdown
    portfolio_history['peak'] = portfolio_history['portfolio_value'].cummax()
    portfolio_history['drawdown'] = (portfolio_history['portfolio_value'] / portfolio_history['peak']) - 1
    max_drawdown = portfolio_history['drawdown'].min()
    
    # Calmar ratio
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else 0
    
    # Trade statistics
    if not trades.empty:
        profitable_trades = trades[trades['profit_pct'] > 0]
        win_rate = len(profitable_trades) / len(trades) if len(trades) > 0 else 0
        avg_profit = trades['profit_pct'].mean() if len(trades) > 0 else 0
        avg_win = profitable_trades['profit_pct'].mean() if len(profitable_trades) > 0 else 0
        losing_trades = trades[trades['profit_pct'] <= 0]
        avg_loss = losing_trades['profit_pct'].mean() if len(losing_trades) > 0 else 0
        profit_factor = abs(profitable_trades['profit_pct'].sum() / losing_trades['profit_pct'].sum()) if len(losing_trades) > 0 and losing_trades['profit_pct'].sum() < 0 else 0
    else:
        win_rate = 0
        avg_profit = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
    
    metrics = {
        'total_return': total_return,
        'cagr': cagr,
        'annualized_volatility': annualized_volatility,
        'sharpe': sharpe,
        'sortino': sortino,
        'max_drawdown': max_drawdown,
        'calmar': calmar,
        'win_rate': win_rate,
        'avg_profit': avg_profit,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'num_trades': len(trades)
    }
    
    return metrics


def generate_reports(portfolio_history, trades, metrics, args):
    """
    Generate performance reports and charts.
    
    Args:
        portfolio_history: DataFrame with portfolio history
        trades: DataFrame with trade history
        metrics: Dictionary of performance metrics
        args: Command line arguments
    """
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir) / f"ml_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save portfolio history and trades to CSV
    portfolio_history.to_csv(output_dir / 'portfolio_history.csv')
    trades.to_csv(output_dir / 'trades.csv')
    
    # Save metrics to JSON
    with open(output_dir / 'metrics.json', 'w') as f:
        json.dump({k: float(v) for k, v in metrics.items()}, f, indent=4)
    
    # Generate performance charts
    plt.figure(figsize=(16, 12))
    
    # Plot 1: Portfolio Value
    plt.subplot(3, 2, 1)
    portfolio_history['portfolio_value'].plot()
    plt.title('Portfolio Value')
    plt.grid(True)
    
    # Plot 2: Drawdown
    plt.subplot(3, 2, 2)
    portfolio_history['drawdown'].plot(color='red')
    plt.title('Drawdown')
    plt.grid(True)
    
    # Plot 3: Daily Returns
    plt.subplot(3, 2, 3)
    portfolio_history['daily_return'].plot(kind='hist', bins=50)
    plt.title('Distribution of Daily Returns')
    plt.grid(True)
    
    # Plot 4: Monthly Returns Heatmap
    plt.subplot(3, 2, 4)
    if not portfolio_history.empty and len(portfolio_history) > 30:
        # Calculate monthly returns
        monthly_returns = portfolio_history['daily_return'].resample('M').apply(
            lambda x: (1 + x).prod() - 1
        )
        monthly_returns = monthly_returns.to_frame()
        monthly_returns['year'] = monthly_returns.index.year
        monthly_returns['month'] = monthly_returns.index.month
        
        # Create pivot table
        heatmap_data = monthly_returns.pivot_table(
            index='year', 
            columns='month', 
            values='daily_return'
        )
        
        # Plot heatmap
        sns.heatmap(heatmap_data, annot=True, fmt='.2%', cmap='RdYlGn')
        plt.title('Monthly Returns')
    else:
        plt.text(0.5, 0.5, 'Insufficient data for monthly heatmap', 
                 horizontalalignment='center', verticalalignment='center')
    
    # Plot 5: Trade Profitability
    plt.subplot(3, 2, 5)
    if not trades.empty:
        trades['profit_pct'].plot(kind='bar', color=trades['profit_pct'].apply(
            lambda x: 'green' if x > 0 else 'red'))
        plt.title('Trade Profitability')
        plt.grid(True)
    else:
        plt.text(0.5, 0.5, 'No trades to display', 
                 horizontalalignment='center', verticalalignment='center')
    
    # Plot 6: Performance Metrics
    plt.subplot(3, 2, 6)
    metrics_to_plot = {
        'Total Return': f"{metrics['total_return']:.2%}",
        'CAGR': f"{metrics['cagr']:.2%}",
        'Sharpe': f"{metrics['sharpe']:.2f}",
        'Sortino': f"{metrics['sortino']:.2f}",
        'Max Drawdown': f"{metrics['max_drawdown']:.2%}",
        'Win Rate': f"{metrics['win_rate']:.2%}",
        'Profit Factor': f"{metrics['profit_factor']:.2f}",
        'Num Trades': f"{metrics['num_trades']}"
    }
    plt.axis('off')
    y_pos = 0.9
    for metric, value in metrics_to_plot.items():
        plt.text(0.1, y_pos, f"{metric}: {value}", fontsize=12)
        y_pos -= 0.1
    
    plt.tight_layout()
    plt.savefig(output_dir / 'performance_summary.png', dpi=300)
    plt.close()
    
    logger.info(f"Reports saved to {output_dir}")


def optimize_strategy(strategy, data, args):
    """
    Optimize strategy parameters using Bayesian optimization.
    
    Args:
        strategy: Strategy instance
        data: Dictionary of market data per symbol
        args: Command line arguments
        
    Returns:
        Optimized strategy parameters
    """
    logger.info("Strategy optimization not implemented yet")
    # Implementation would use Bayesian optimization from skopt
    # to find optimal strategy parameters
    return {}


def setup_ml_strategy(args):
    """
    Set up ML ensemble strategy with configuration.
    
    Args:
        args: Command line arguments
        
    Returns:
        Configured ML strategy instance
    """
    # Update GPU config based on args
    config.GPU_CONFIG["use_gpu"] = args.gpu
    
    # Get strategy config
    strategy_config = config.STRATEGY_CONFIGS["ml_ensemble"]
    
    # Update symbols from args
    strategy_config["symbols"] = args.symbols
    
    # Create strategy instance
    strategy = MLEnsembleStrategy(
        config=strategy_config,
        model_dir=os.path.join(config.MODELS_DIR, "ml_ensemble")
    )
    
    return strategy


def main():
    """Main entry point for the script."""
    args = parse_arguments()
    
    logger.info(f"Starting ML Strategy Runner in {args.mode} mode")
    logger.info(f"Parameters: {vars(args)}")
    
    # Set up strategy
    strategy = setup_ml_strategy(args)
    
    # Load market data
    data = load_market_data(
        symbols=args.symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        data_freq=args.data_freq
    )
    
    if not data:
        logger.error("No market data loaded. Exiting.")
        return 1
    
    # Execute based on mode
    if args.mode == 'backtest':
        results = run_backtest(strategy, data, args)
        metrics = analyze_results(results, args)
        
        # Return non-zero exit code if performance is poor
        if metrics['total_return'] < 0:
            logger.warning("Backtest resulted in negative returns")
            return 1
        
    elif args.mode == 'optimize':
        optimal_params = optimize_strategy(strategy, data, args)
        logger.info(f"Optimal parameters: {optimal_params}")
        
    elif args.mode == 'live':
        logger.info("Live trading mode is not implemented yet")
        return 1
    
    logger.info("ML Strategy Runner completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 