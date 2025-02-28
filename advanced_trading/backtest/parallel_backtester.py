"""
Parallel Backtesting Engine
--------------------------
High-performance backtesting engine that leverages multiprocessing and GPU acceleration
to run multiple strategies in parallel.
"""

import os
import logging
import multiprocessing
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union, Callable
import json
import matplotlib.pyplot as plt
import seaborn as sns
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial

# Zipline imports
import zipline
from zipline.api import symbol
from zipline.data import bundles
from zipline.data.data_portal import DataPortal
from zipline.finance import trading_calendar
from zipline.utils.run_algo import run_algorithm
from zipline.utils.calendar_utils import get_calendar
from zipline.utils.cli import Date, Timestamp

# Import custom modules
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from data.data_manager import DataManager

# Set up logging
logger = logging.getLogger(__name__)

class ParallelBacktester:
    """
    High-performance parallel backtesting engine for cryptocurrency strategies.
    """
    
    def __init__(self, use_gpu: bool = True, num_workers: int = None):
        """
        Initialize the parallel backtester.
        
        Args:
            use_gpu: Whether to use GPU acceleration
            num_workers: Number of worker processes to use (defaults to CPU count - 1)
        """
        self.use_gpu = use_gpu and config.GPU_CONFIG["use_gpu"]
        self.num_workers = num_workers or config.PARALLEL_CONFIG["num_workers"]
        self.data_manager = DataManager(use_gpu=use_gpu)
        self.results_dir = config.RESULTS_DIR
        
        # Create results directory if it doesn't exist
        if not self.results_dir.exists():
            self.results_dir.mkdir(parents=True)
        
        logger.info(f"Parallel backtester initialized with {self.num_workers} workers and GPU={self.use_gpu}")
    
    def prepare_data_bundle(self, symbols: List[str], timeframes: List[str], 
                           start_date: str, end_date: str, refresh: bool = False) -> Dict:
        """
        Prepare data bundle for backtesting.
        
        Args:
            symbols: List of symbols to prepare data for
            timeframes: List of timeframes to prepare data for
            start_date: Start date for backtest
            end_date: End date for backtest
            refresh: Whether to force refresh data
            
        Returns:
            Dictionary of prepared data
        """
        logger.info(f"Preparing data bundle for {len(symbols)} symbols and {len(timeframes)} timeframes")
        
        # For each symbol and timeframe, load data
        data_bundle = {}
        
        for symbol in symbols:
            data_bundle[symbol] = {}
            
            for timeframe in timeframes:
                logger.info(f"Loading data for {symbol} {timeframe}")
                
                # Load data with indicators
                df = self.data_manager.load_and_prepare_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    refresh=refresh
                )
                
                if df.empty:
                    logger.warning(f"No data available for {symbol} {timeframe}")
                    continue
                
                # Convert to Zipline format
                zipline_data = self.data_manager.prepare_zipline_data(df)
                
                if zipline_data.empty:
                    logger.warning(f"Failed to convert data to Zipline format for {symbol} {timeframe}")
                    continue
                
                data_bundle[symbol][timeframe] = zipline_data
                logger.info(f"Prepared {len(zipline_data)} bars for {symbol} {timeframe}")
        
        return data_bundle
    
    def run_single_backtest(self, strategy_class: type, strategy_params: Dict, 
                           data_bundle: Dict, symbol: str, timeframe: str,
                           start_date: str, end_date: str, initial_capital: float = 10000.0) -> Dict:
        """
        Run a single backtest for a strategy.
        
        Args:
            strategy_class: Strategy class to backtest
            strategy_params: Parameters for the strategy
            data_bundle: Data bundle for backtesting
            symbol: Symbol to backtest
            timeframe: Timeframe to backtest
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Initial capital for backtest
            
        Returns:
            Dictionary of backtest results
        """
        start_time = time.time()
        logger.info(f"Starting backtest for {strategy_class.__name__} on {symbol} {timeframe}")
        
        try:
            # Prepare data for this specific backtest
            if symbol not in data_bundle or timeframe not in data_bundle[symbol]:
                logger.error(f"No data available for {symbol} {timeframe}")
                return {"error": f"No data available for {symbol} {timeframe}"}
            
            zipline_data = data_bundle[symbol][timeframe]
            
            # Create a unique identifier for this backtest
            backtest_id = f"{strategy_class.__name__}_{symbol}_{timeframe}_{int(time.time())}"
            
            # Prepare the start and end dates
            start = pd.Timestamp(start_date, tz='UTC')
            end = pd.Timestamp(end_date, tz='UTC')
            
            # Initialize the strategy instance
            strategy_instance = strategy_class(strategy_params)
            
            # Run the backtest
            results = run_algorithm(
                start=start,
                end=end,
                initialize=strategy_instance.initialize,
                capital_base=initial_capital,
                handle_data=None,  # We'll use scheduled functions instead
                before_trading_start=strategy_instance.before_trading_start,
                data_frequency='daily',  # Use 'minute' for minute data
                data=zipline_data,
                trading_calendar=get_calendar('NYSE'),  # Use 24/7 for crypto in production
                bundle=None
            )
            
            # Calculate performance metrics
            metrics = self._calculate_performance_metrics(results, strategy_instance)
            
            # Save results and generate plots
            self._save_backtest_results(backtest_id, results, metrics, strategy_params)
            
            elapsed = time.time() - start_time
            logger.info(f"Completed backtest for {strategy_class.__name__} on {symbol} {timeframe} in {elapsed:.2f}s")
            
            return {
                "backtest_id": backtest_id,
                "strategy": strategy_class.__name__,
                "symbol": symbol,
                "timeframe": timeframe,
                "params": strategy_params,
                "metrics": metrics,
                "elapsed_time": elapsed
            }
            
        except Exception as e:
            logger.error(f"Error running backtest for {strategy_class.__name__} on {symbol} {timeframe}: {str(e)}")
            return {
                "error": str(e),
                "strategy": strategy_class.__name__,
                "symbol": symbol,
                "timeframe": timeframe
            }
    
    def run_parallel_backtests(self, strategies: List[Dict], symbols: List[str], 
                              timeframes: List[str], start_date: str, end_date: str,
                              initial_capital: float = 10000.0, refresh_data: bool = False) -> Dict:
        """
        Run multiple backtests in parallel.
        
        Args:
            strategies: List of strategy configurations (class and params)
            symbols: List of symbols to backtest
            timeframes: List of timeframes to backtest
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Initial capital for backtest
            refresh_data: Whether to force refresh data
            
        Returns:
            Dictionary of backtest results by strategy
        """
        start_time = time.time()
        logger.info(f"Starting parallel backtests for {len(strategies)} strategies, "
                   f"{len(symbols)} symbols, {len(timeframes)} timeframes")
        
        # Prepare data bundle for all symbols and timeframes
        data_bundle = self.prepare_data_bundle(
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            refresh=refresh_data
        )
        
        # Create backtest tasks
        tasks = []
        for strategy in strategies:
            strategy_class = strategy["class"]
            strategy_params = strategy.get("params", {})
            
            for symbol in symbols:
                for timeframe in timeframes:
                    tasks.append({
                        "strategy_class": strategy_class,
                        "strategy_params": strategy_params,
                        "symbol": symbol,
                        "timeframe": timeframe
                    })
        
        logger.info(f"Created {len(tasks)} backtest tasks")
        
        # Run tasks in parallel
        results = []
        
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            # Create partial function with fixed parameters
            run_func = partial(
                self._run_backtest_task,
                data_bundle=data_bundle,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital
            )
            
            # Execute tasks in parallel
            for result in executor.map(run_func, tasks):
                results.append(result)
        
        # Organize results by strategy
        organized_results = {}
        for result in results:
            if "error" in result:
                logger.warning(f"Backtest error: {result['error']}")
                continue
                
            strategy_name = result["strategy"]
            if strategy_name not in organized_results:
                organized_results[strategy_name] = []
            
            organized_results[strategy_name].append(result)
        
        # Compare strategies
        if len(organized_results) > 1:
            self._compare_strategies(organized_results)
        
        elapsed = time.time() - start_time
        logger.info(f"Completed all backtests in {elapsed:.2f}s")
        
        return organized_results
    
    def _run_backtest_task(self, task: Dict, data_bundle: Dict, 
                          start_date: str, end_date: str, initial_capital: float) -> Dict:
        """Helper function to run a single backtest task"""
        return self.run_single_backtest(
            strategy_class=task["strategy_class"],
            strategy_params=task["strategy_params"],
            data_bundle=data_bundle,
            symbol=task["symbol"],
            timeframe=task["timeframe"],
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
    
    def _calculate_performance_metrics(self, results: pd.DataFrame, strategy_instance: Any) -> Dict:
        """
        Calculate performance metrics from backtest results.
        
        Args:
            results: Backtest results DataFrame
            strategy_instance: Strategy instance used for backtest
            
        Returns:
            Dictionary of performance metrics
        """
        # Extract portfolio values
        portfolio_value = results['portfolio_value']
        benchmark = results['benchmark']
        
        # Calculate returns
        returns = portfolio_value.pct_change().dropna()
        benchmark_returns = benchmark.pct_change().dropna()
        
        # Annualize return and volatility (assuming 252 trading days per year)
        trading_days = len(returns)
        years = trading_days / 252
        
        total_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0]) - 1
        annualized_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1
        
        volatility = returns.std() * np.sqrt(252)
        benchmark_volatility = benchmark_returns.std() * np.sqrt(252)
        
        # Sharpe ratio (assuming risk-free rate of 0)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = annualized_return / downside_deviation if downside_deviation > 0 else 0
        
        # Maximum drawdown
        rolling_max = portfolio_value.cummax()
        drawdowns = portfolio_value / rolling_max - 1
        max_drawdown = drawdowns.min()
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown < 0 else 0
        
        # Information ratio (vs benchmark)
        active_returns = returns - benchmark_returns
        information_ratio = active_returns.mean() / active_returns.std() * np.sqrt(252) if len(active_returns) > 0 else 0
        
        # Alpha and beta
        covariance = returns.cov(benchmark_returns)
        benchmark_variance = benchmark_returns.var()
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
        alpha = annualized_return - beta * (benchmark_returns.mean() * 252)
        
        # Trade statistics
        if hasattr(strategy_instance, 'trades') and len(strategy_instance.trades) > 0:
            num_trades = len(strategy_instance.trades)
            # We could extract more trade details here if available
        else:
            num_trades = 0
        
        metrics = {
            'total_return': total_return,
            'annual_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'information_ratio': information_ratio,
            'alpha': alpha,
            'beta': beta,
            'num_trades': num_trades,
            'trading_days': trading_days
        }
        
        return metrics
    
    def _save_backtest_results(self, backtest_id: str, results: pd.DataFrame, 
                              metrics: Dict, params: Dict) -> None:
        """
        Save backtest results and generate plots.
        
        Args:
            backtest_id: Unique identifier for the backtest
            results: Backtest results DataFrame
            metrics: Performance metrics
            params: Strategy parameters
        """
        # Create directory for this backtest
        backtest_dir = self.results_dir / backtest_id
        backtest_dir.mkdir(parents=True, exist_ok=True)
        
        # Save results as CSV
        results.to_csv(backtest_dir / 'results.csv')
        
        # Save metrics and params as JSON
        with open(backtest_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=4)
        
        with open(backtest_dir / 'params.json', 'w') as f:
            json.dump(params, f, indent=4, default=str)  # Use default=str to handle non-serializable types
        
        # Generate performance chart
        self._generate_performance_chart(results, metrics, backtest_dir)
        
        logger.info(f"Saved backtest results to {backtest_dir}")
    
    def _generate_performance_chart(self, results: pd.DataFrame, metrics: Dict, 
                                  output_dir: Path) -> None:
        """
        Generate performance charts.
        
        Args:
            results: Backtest results DataFrame
            metrics: Performance metrics
            output_dir: Output directory for plots
        """
        try:
            sns.set(style="darkgrid")
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 18), sharex=True)
            
            # Plot portfolio value and benchmark
            results[['portfolio_value', 'benchmark']].plot(ax=ax1)
            ax1.set_ylabel('Value')
            ax1.set_title(f"Portfolio Performance (Return: {metrics['total_return']:.2%}, Sharpe: {metrics['sharpe_ratio']:.2f})")
            
            # Plot returns
            returns = results['portfolio_value'].pct_change()
            benchmark_returns = results['benchmark'].pct_change()
            pd.DataFrame({
                'Strategy Returns': returns,
                'Benchmark Returns': benchmark_returns
            }).plot(ax=ax2)
            ax2.set_ylabel('Daily Return')
            ax2.set_title(f"Daily Returns (Volatility: {metrics['volatility']:.2%})")
            
            # Plot drawdowns
            rolling_max = results['portfolio_value'].cummax()
            drawdowns = results['portfolio_value'] / rolling_max - 1
            drawdowns.plot(ax=ax3)
            ax3.set_ylabel('Drawdown')
            ax3.set_title(f"Drawdowns (Max Drawdown: {metrics['max_drawdown']:.2%})")
            
            plt.tight_layout()
            plt.savefig(output_dir / 'performance.png')
            plt.close()
            
            # Generate supplementary plots
            self._generate_supplementary_plots(results, metrics, output_dir)
            
        except Exception as e:
            logger.error(f"Error generating performance chart: {str(e)}")
    
    def _generate_supplementary_plots(self, results: pd.DataFrame, metrics: Dict, 
                                    output_dir: Path) -> None:
        """Generate additional analysis plots"""
        try:
            # Monthly returns heatmap
            returns = results['portfolio_value'].pct_change()
            monthly_returns = returns.groupby([
                lambda x: x.year,
                lambda x: x.month
            ]).apply(lambda x: (1 + x).prod() - 1)
            
            monthly_returns = monthly_returns.unstack()
            plt.figure(figsize=(12, 8))
            sns.heatmap(monthly_returns, annot=True, fmt=".2%", cmap="RdYlGn")
            plt.title("Monthly Returns")
            plt.savefig(output_dir / 'monthly_returns.png')
            plt.close()
            
            # Rolling metrics
            rolling_window = min(252, len(returns) // 4)  # Use 252 days or 1/4 of data length
            
            # Calculate rolling Sharpe ratio
            rolling_return = returns.rolling(rolling_window).mean() * 252
            rolling_vol = returns.rolling(rolling_window).std() * np.sqrt(252)
            rolling_sharpe = rolling_return / rolling_vol
            
            plt.figure(figsize=(12, 6))
            rolling_sharpe.plot()
            plt.title(f"Rolling {rolling_window}-day Sharpe Ratio")
            plt.axhline(y=1.0, color='r', linestyle='-', alpha=0.3)
            plt.axhline(y=2.0, color='g', linestyle='-', alpha=0.3)
            plt.savefig(output_dir / 'rolling_sharpe.png')
            plt.close()
            
            # Rolling volatility
            plt.figure(figsize=(12, 6))
            rolling_vol.plot()
            plt.title(f"Rolling {rolling_window}-day Volatility")
            plt.savefig(output_dir / 'rolling_volatility.png')
            plt.close()
            
        except Exception as e:
            logger.error(f"Error generating supplementary plots: {str(e)}")
    
    def _compare_strategies(self, results_by_strategy: Dict) -> None:
        """
        Compare multiple strategies.
        
        Args:
            results_by_strategy: Dictionary of results by strategy
        """
        try:
            # Create comparison directory
            comparison_dir = self.results_dir / f"comparison_{int(time.time())}"
            comparison_dir.mkdir(parents=True, exist_ok=True)
            
            # Collect metrics for each strategy
            metrics_by_strategy = {}
            for strategy_name, results in results_by_strategy.items():
                # Average metrics across all symbols and timeframes
                metrics_list = [r["metrics"] for r in results if "metrics" in r]
                if not metrics_list:
                    continue
                
                avg_metrics = {}
                for key in metrics_list[0].keys():
                    avg_metrics[key] = sum(m[key] for m in metrics_list) / len(metrics_list)
                
                metrics_by_strategy[strategy_name] = avg_metrics
            
            # Create comparison table
            comparison_df = pd.DataFrame(metrics_by_strategy).T
            comparison_df.to_csv(comparison_dir / 'strategy_comparison.csv')
            
            # Plot key metrics
            plt.figure(figsize=(12, 8))
            comparison_df[['annual_return', 'sharpe_ratio', 'sortino_ratio', 'max_drawdown']].plot(kind='bar')
            plt.title("Strategy Comparison")
            plt.tight_layout()
            plt.savefig(comparison_dir / 'strategy_comparison.png')
            plt.close()
            
            logger.info(f"Saved strategy comparison to {comparison_dir}")
            
        except Exception as e:
            logger.error(f"Error comparing strategies: {str(e)}")


# Helper function for walk-forward optimization
def run_walk_forward_optimization(backtester: ParallelBacktester, strategy_class: type,
                                 param_grid: Dict[str, List], symbols: List[str],
                                 timeframes: List[str], start_date: str, end_date: str,
                                 train_window: int = 365, test_window: int = 90,
                                 step_size: int = 30, initial_capital: float = 10000.0) -> Dict:
    """
    Run walk-forward optimization for a strategy.
    
    Args:
        backtester: ParallelBacktester instance
        strategy_class: Strategy class to optimize
        param_grid: Grid of parameters to test
        symbols: List of symbols to test
        timeframes: List of timeframes to test
        start_date: Start date for optimization
        end_date: End date for optimization
        train_window: Training window in days
        test_window: Testing window in days
        step_size: Step size in days
        initial_capital: Initial capital for backtest
        
    Returns:
        Dictionary of optimization results
    """
    logger.info(f"Starting walk-forward optimization for {strategy_class.__name__}")
    
    # Convert dates to datetime
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)
    
    # Generate all parameter combinations
    import itertools
    param_keys = list(param_grid.keys())
    param_values = list(param_grid.values())
    param_combinations = list(itertools.product(*param_values))
    
    logger.info(f"Testing {len(param_combinations)} parameter combinations")
    
    # Generate time windows for walk-forward testing
    windows = []
    current_start = start_dt
    
    while current_start + timedelta(days=train_window + test_window) <= end_dt:
        train_end = current_start + timedelta(days=train_window)
        test_end = train_end + timedelta(days=test_window)
        
        windows.append({
            'train_start': current_start.strftime('%Y-%m-%d'),
            'train_end': train_end.strftime('%Y-%m-%d'),
            'test_start': train_end.strftime('%Y-%m-%d'),
            'test_end': test_end.strftime('%Y-%m-%d')
        })
        
        current_start += timedelta(days=step_size)
    
    logger.info(f"Created {len(windows)} time windows for walk-forward testing")
    
    # Results storage
    wfo_results = {
        'windows': windows,
        'param_grid': param_grid,
        'best_params_by_window': [],
        'out_of_sample_results': [],
        'best_overall_params': {},
        'overall_performance': {}
    }
    
    # For each window
    for i, window in enumerate(windows):
        logger.info(f"Processing window {i+1}/{len(windows)}: "
                  f"{window['train_start']} to {window['test_end']}")
        
        # In-sample optimization
        train_strategies = []
        for j, param_combo in enumerate(param_combinations):
            params = {param_keys[k]: param_combo[k] for k in range(len(param_keys))}
            train_strategies.append({
                "class": strategy_class,
                "params": params
            })
        
        # Run in parallel for training window
        train_results = backtester.run_parallel_backtests(
            strategies=train_strategies,
            symbols=symbols,
            timeframes=timeframes,
            start_date=window['train_start'],
            end_date=window['train_end'],
            initial_capital=initial_capital
        )
        
        # Find best parameters
        best_score = -float('inf')
        best_params = None
        
        for strategy_name, results in train_results.items():
            for result in results:
                if 'metrics' in result:
                    # Use Sharpe ratio as optimization metric
                    sharpe = result['metrics']['sharpe_ratio']
                    if sharpe > best_score:
                        best_score = sharpe
                        best_params = result['params']
        
        if best_params is None:
            logger.warning(f"No valid results found for window {i+1}")
            continue
        
        logger.info(f"Best parameters for window {i+1}: {best_params} (Sharpe: {best_score:.2f})")
        
        # Save best parameters for this window
        wfo_results['best_params_by_window'].append({
            'window': i,
            'params': best_params,
            'train_sharpe': best_score
        })
        
        # Out-of-sample testing with best parameters
        test_strategies = [{
            "class": strategy_class,
            "params": best_params
        }]
        
        test_results = backtester.run_parallel_backtests(
            strategies=test_strategies,
            symbols=symbols,
            timeframes=timeframes,
            start_date=window['test_start'],
            end_date=window['test_end'],
            initial_capital=initial_capital
        )
        
        # Extract out-of-sample performance
        if strategy_class.__name__ in test_results:
            for result in test_results[strategy_class.__name__]:
                if 'metrics' in result:
                    wfo_results['out_of_sample_results'].append({
                        'window': i,
                        'params': best_params,
                        'metrics': result['metrics']
                    })
                    logger.info(f"Out-of-sample performance for window {i+1}: "
                              f"Return: {result['metrics']['total_return']:.2%}, "
                              f"Sharpe: {result['metrics']['sharpe_ratio']:.2f}")
    
    # Determine overall best parameters
    # We'll use average out-of-sample Sharpe ratio as the criterion
    param_performance = {}
    
    for result in wfo_results['out_of_sample_results']:
        param_str = str(result['params'])
        if param_str not in param_performance:
            param_performance[param_str] = {
                'params': result['params'],
                'sharpe_values': [],
                'return_values': []
            }
        
        param_performance[param_str]['sharpe_values'].append(result['metrics']['sharpe_ratio'])
        param_performance[param_str]['return_values'].append(result['metrics']['total_return'])
    
    best_avg_sharpe = -float('inf')
    best_overall_params = None
    
    for param_str, perf in param_performance.items():
        avg_sharpe = sum(perf['sharpe_values']) / len(perf['sharpe_values'])
        avg_return = sum(perf['return_values']) / len(perf['return_values'])
        
        perf['avg_sharpe'] = avg_sharpe
        perf['avg_return'] = avg_return
        
        if avg_sharpe > best_avg_sharpe:
            best_avg_sharpe = avg_sharpe
            best_overall_params = perf['params']
    
    wfo_results['best_overall_params'] = best_overall_params
    wfo_results['overall_performance'] = {
        'avg_sharpe': best_avg_sharpe,
        'param_performance': param_performance
    }
    
    logger.info(f"Walk-forward optimization complete. Best overall parameters: {best_overall_params}")
    
    # Save results
    results_path = backtester.results_dir / f"wfo_{strategy_class.__name__}_{int(time.time())}.json"
    with open(results_path, 'w') as f:
        json.dump(wfo_results, f, indent=4, default=str)
    
    return wfo_results 