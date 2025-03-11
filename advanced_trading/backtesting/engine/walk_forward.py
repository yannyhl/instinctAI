"""
Walk-Forward Testing Module
--------------------------
This module provides a framework for walk-forward testing of trading strategies.

Key features:
1. Multiple cross-validation schemes (expanding window, sliding window, anchored window)
2. Parameter optimization for each training period
3. Performance evaluation on out-of-sample data
4. Statistical analysis of results across periods
5. Visualization of strategy performance in different market regimes
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Callable, Optional, Union, Any, Type
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
import os
from tqdm import tqdm

# Import our time series cross-validation
from advanced_trading.utils.cross_validation import TimeSeriesCV

# Configure logger
logger = logging.getLogger(__name__)

class WalkForwardTest:
    """
    Walk-Forward Testing for systematic evaluation of trading strategies.
    
    This class implements walk-forward testing with parameter optimization,
    which mitigates overfitting risk by using proper time series validation.
    
    Parameters:
    -----------
    market_data : pd.DataFrame
        Market data with OHLCV and any additional features
    train_size : Union[int, float]
        Size of training window (int for absolute size, float for fraction of data)
    test_size : Union[int, float]
        Size of test window (int for absolute size, float for fraction of data)
    step_size : Union[int, float]
        Step size between walk-forward periods
    optimization_func : Optional[Callable]
        Function to optimize strategy parameters on training data
    window_type : str
        Type of walk-forward window ('sliding', 'expanding', 'anchored')
    purge_window : Union[int, float, None]
        Size of data to purge between train and test periods
    embargo_window : Union[int, float, None]
        Size of embargo after test period
    initial_capital : float
        Initial capital for backtesting
    commission : float
        Commission rate for trades
    slippage : float
        Slippage rate for trades
    """
    
    def __init__(
        self,
        market_data: pd.DataFrame,
        train_size: Union[int, float] = 0.6,
        test_size: Union[int, float] = 0.2,
        step_size: Union[int, float] = 0.1,
        optimization_func: Optional[Callable] = None,
        window_type: str = 'sliding',
        purge_window: Optional[Union[int, float]] = None,
        embargo_window: Optional[Union[int, float]] = None,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.001
    ):
        """Initialize WalkForwardTest."""
        self._validate_market_data(market_data)
        
        self.market_data = market_data
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
        self.optimization_func = optimization_func
        self.window_type = window_type
        self.purge_window = purge_window
        self.embargo_window = embargo_window
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
        # Initialize with empty results
        self.splits = None
        self.results = None
        self.combined_results = None
        self.optimized_params = None
        
        # Integration with TimeSeriesCV
        self.cv = TimeSeriesCV(
            cv_method=window_type,
            n_splits=None,  # We'll use all available splits
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            purge_size=purge_window,
            embargo_size=embargo_window
        )
        
        logger.info(f"Initialized WalkForwardTest with {window_type} window, "
                   f"train_size={train_size}, test_size={test_size}, step_size={step_size}")
    
    def _validate_market_data(self, market_data: pd.DataFrame):
        """Validate the market data."""
        if not isinstance(market_data, pd.DataFrame):
            raise ValueError("market_data must be a pandas DataFrame")
            
        if 'close' not in market_data.columns.str.lower():
            raise ValueError("market_data must contain a 'close' column")
            
        if not isinstance(market_data.index, pd.DatetimeIndex):
            raise ValueError("market_data must have a DatetimeIndex")
    
    def generate_train_test_splits(self) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Generate train/test splits for walk-forward testing.
        
        Returns:
        --------
        List[Tuple[pd.DataFrame, pd.DataFrame]]
            List of (train_data, test_data) tuples
        """
        # Use TimeSeriesCV to generate the splits
        splits_indices = list(self.cv.split(self.market_data))
        
        # Convert indices to dataframes
        splits = []
        for train_indices, test_indices in splits_indices:
            train_data = self.market_data.iloc[train_indices].copy()
            test_data = self.market_data.iloc[test_indices].copy()
            splits.append((train_data, test_data))
        
        self.splits = splits
        logger.info(f"Generated {len(splits)} train/test splits")
        
        return splits
    
    def run(
        self,
        strategy_class: Type,
        default_params: Dict[str, Any],
        backtest_func: Callable,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Execute walk-forward testing with parameter optimization.
        
        Parameters:
        -----------
        strategy_class : Type
            Class of the trading strategy to test
        default_params : Dict[str, Any]
            Default parameters for the strategy
        backtest_func : Callable
            Function to run backtest on a specific period
        show_progress : bool
            Whether to show progress bar
        
        Returns:
        --------
        Dict[str, Any]
            Dictionary of combined results
        """
        if self.splits is None:
            self.generate_train_test_splits()
            
        # Storage for results
        self.results = []
        self.optimized_params = []
        
        # Iterate through splits
        iterator = tqdm(self.splits, desc="Walk-Forward Testing") if show_progress else self.splits
        
        for i, (train_data, test_data) in enumerate(iterator):
            logger.info(f"Processing walk-forward period {i+1}/{len(self.splits)}")
            
            # Optimize parameters if optimization function is provided
            if self.optimization_func is not None:
                logger.info(f"Optimizing parameters for period {i+1}")
                optimized_params = self.optimization_func(
                    strategy_class=strategy_class,
                    market_data=train_data,
                    default_params=default_params,
                    backtest_func=backtest_func,
                    initial_capital=self.initial_capital,
                    commission=self.commission,
                    slippage=self.slippage
                )
                self.optimized_params.append(optimized_params)
                params = optimized_params
            else:
                params = default_params
                self.optimized_params.append(default_params)
                
            # Run backtest on test data
            logger.info(f"Running backtest on test data for period {i+1}")
            strategy = strategy_class(**params)
            backtest_result = backtest_func(
                strategy=strategy,
                market_data=test_data,
                initial_capital=self.initial_capital,
                commission=self.commission,
                slippage=self.slippage
            )
            
            # Store results
            self.results.append({
                'period': i+1,
                'train_start': train_data.index[0],
                'train_end': train_data.index[-1],
                'test_start': test_data.index[0],
                'test_end': test_data.index[-1],
                'parameters': params,
                'backtest_result': backtest_result
            })
            
        # Combine results
        self.combined_results = self._combine_results()
        
        return self.combined_results
    
    def _combine_results(self) -> Dict[str, Any]:
        """
        Combine results from all walk-forward iterations.
        
        Returns:
        --------
        Dict[str, Any]
            Dictionary of combined results
        """
        if not self.results:
            raise ValueError("No results to combine. Run the walk-forward test first.")
            
        # Extract components
        equity_curves = []
        returns = []
        trades = []
        metrics = []
        
        for result in self.results:
            backtest = result['backtest_result']
            equity_curves.append(backtest['equity_curve'])
            returns.append(backtest['returns'])
            trades.extend(backtest['trades'])
            metrics.append(backtest['metrics'])
            
        # Combine equity curves
        combined_equity = pd.concat(equity_curves)
        combined_equity = combined_equity[~combined_equity.index.duplicated(keep='first')]
        combined_equity.sort_index(inplace=True)
        
        # Combine returns
        combined_returns = pd.concat(returns)
        combined_returns = combined_returns[~combined_returns.index.duplicated(keep='first')]
        combined_returns.sort_index(inplace=True)
        
        # Calculate overall metrics
        total_return = (combined_equity.iloc[-1] / combined_equity.iloc[0]) - 1
        annualized_return = (1 + total_return) ** (252 / len(combined_equity)) - 1
        volatility = combined_returns.std() * np.sqrt(252)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        max_drawdown = (combined_equity / combined_equity.cummax() - 1).min()
        
        # Create a time series of parameter values
        parameter_series = {}
        if self.optimized_params:
            for key in self.optimized_params[0].keys():
                values = []
                dates = []
                for i, params in enumerate(self.optimized_params):
                    values.append(params.get(key))
                    dates.append(self.results[i]['test_start'])
                parameter_series[key] = pd.Series(values, index=dates)
        
        # Combine everything
        combined = {
            'equity_curve': combined_equity,
            'returns': combined_returns,
            'trades': trades,
            'metrics': {
                'total_return': total_return,
                'annualized_return': annualized_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'win_rate': sum(1 for t in trades if t['pnl'] > 0) / len(trades) if trades else 0,
                'profit_factor': sum(t['pnl'] for t in trades if t['pnl'] > 0) / abs(sum(t['pnl'] for t in trades if t['pnl'] < 0)) if sum(t['pnl'] for t in trades if t['pnl'] < 0) != 0 else float('inf')
            },
            'period_metrics': metrics,
            'parameter_series': parameter_series,
            'periods': self.results
        }
        
        logger.info(f"Combined results: Sharpe={combined['metrics']['sharpe_ratio']:.2f}, "
                   f"Return={combined['metrics']['annualized_return']:.2%}, "
                   f"Drawdown={combined['metrics']['max_drawdown']:.2%}")
        
        return combined
    
    def plot_equity_curves(self, figsize: Tuple[int, int] = (12, 6), include_combined: bool = True) -> plt.Figure:
        """
        Plot equity curves for each walk-forward period.
        
        Parameters:
        -----------
        figsize : Tuple[int, int]
            Figure size
        include_combined : bool
            Whether to include the combined equity curve
            
        Returns:
        --------
        plt.Figure
            Figure with equity curves
        """
        if not self.results:
            raise ValueError("No results to plot. Run the walk-forward test first.")
            
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot individual period equity curves
        colors = plt.cm.tab10.colors
        for i, result in enumerate(self.results):
            equity = result['backtest_result']['equity_curve']
            label = f"Period {i+1}: {result['test_start'].strftime('%Y-%m-%d')} to {result['test_end'].strftime('%Y-%m-%d')}"
            ax.plot(equity.index, equity.values, alpha=0.7, color=colors[i % len(colors)], label=label)
            
        # Plot combined equity curve
        if include_combined and self.combined_results:
            combined_equity = self.combined_results['equity_curve']
            ax.plot(combined_equity.index, combined_equity.values, color='black', linewidth=2, label='Combined')
            
        # Format plot
        ax.set_title('Equity Curves by Walk-Forward Period')
        ax.set_xlabel('Date')
        ax.set_ylabel('Equity')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        
        plt.tight_layout()
        return fig
    
    def plot_parameter_stability(self, param_names: Optional[List[str]] = None, figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Plot parameter stability across walk-forward periods.
        
        Parameters:
        -----------
        param_names : Optional[List[str]]
            Names of parameters to plot (if None, plot all)
        figsize : Tuple[int, int]
            Figure size
            
        Returns:
        --------
        plt.Figure
            Figure with parameter values
        """
        if not self.optimized_params:
            raise ValueError("No optimized parameters to plot. Run the walk-forward test with optimization_func.")
            
        # Get all parameter names if not specified
        if param_names is None:
            param_names = list(self.optimized_params[0].keys())
            
        # Number of parameters to plot
        n_params = len(param_names)
        if n_params == 0:
            raise ValueError("No parameters to plot")
            
        # Create subplots
        fig, axes = plt.subplots(n_params, 1, figsize=figsize, sharex=True)
        if n_params == 1:
            axes = [axes]
            
        # Plot each parameter
        for i, param_name in enumerate(param_names):
            ax = axes[i]
            values = []
            dates = []
            
            for j, params in enumerate(self.optimized_params):
                if param_name in params:
                    values.append(params[param_name])
                    dates.append(self.results[j]['test_start'])
                    
            # Plot parameter values
            ax.plot(dates, values, 'o-', markersize=8)
            ax.set_title(f'Parameter: {param_name}')
            ax.grid(True, alpha=0.3)
            
            # Set y-label
            ax.set_ylabel('Value')
            
        # Set x-label on bottom subplot
        axes[-1].set_xlabel('Date')
        
        # Format dates
        fig.autofmt_xdate()
        
        plt.tight_layout()
        return fig
    
    def plot_performance_by_period(self, metric: str = 'sharpe_ratio', figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
        """
        Plot performance metric by walk-forward period.
        
        Parameters:
        -----------
        metric : str
            Performance metric to plot
        figsize : Tuple[int, int]
            Figure size
            
        Returns:
        --------
        plt.Figure
            Figure with performance metrics
        """
        if not self.results:
            raise ValueError("No results to plot. Run the walk-forward test first.")
            
        fig, ax = plt.subplots(figsize=figsize)
        
        # Extract metric values
        values = []
        dates = []
        
        for result in self.results:
            if metric in result['backtest_result']['metrics']:
                values.append(result['backtest_result']['metrics'][metric])
                dates.append(result['test_start'])
                
        # Plot metric values
        ax.bar(range(len(values)), values, alpha=0.7)
        
        # Format plot
        ax.set_title(f'{metric.replace("_", " ").title()} by Walk-Forward Period')
        ax.set_xlabel('Period')
        ax.set_ylabel(metric.replace('_', ' ').title())
        ax.set_xticks(range(len(values)))
        ax.set_xticklabels([f"{i+1}\n{date.strftime('%Y-%m-%d')}" for i, date in enumerate(dates)], rotation=45)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add mean line
        mean_value = np.mean(values)
        ax.axhline(mean_value, color='red', linestyle='--', label=f'Mean: {mean_value:.4f}')
        ax.legend()
        
        plt.tight_layout()
        return fig
    
    def plot_train_test_windows(self, figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
        """
        Visualize training and testing windows on a price chart.
        
        Parameters:
        -----------
        figsize : Tuple[int, int]
            Figure size
            
        Returns:
        --------
        plt.Figure
            Figure with train/test windows
        """
        if not self.splits:
            self.generate_train_test_splits()
            
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot price
        price = self.market_data['close'] if 'close' in self.market_data.columns else self.market_data['Close']
        ax.plot(price.index, price.values, color='gray', alpha=0.5, label='Price')
        
        # Create colormap
        colors = plt.cm.tab10.colors
        
        # Plot training and testing windows
        for i, (train_data, test_data) in enumerate(self.splits):
            # Plot training window
            ax.axvspan(train_data.index[0], train_data.index[-1], alpha=0.2, color=colors[0],
                      label='Training' if i == 0 else None)
            
            # Plot testing window
            ax.axvspan(test_data.index[0], test_data.index[-1], alpha=0.3, color=colors[1],
                      label='Testing' if i == 0 else None)
            
            # Add period number
            mid_point = test_data.index[len(test_data) // 2]
            mid_price = price.loc[mid_point]
            ax.text(mid_point, mid_price, f"P{i+1}", ha='center', va='center',
                   bbox=dict(boxstyle='round', fc='white', ec='black', alpha=0.7))
        
        # Format plot
        ax.set_title('Train/Test Windows on Price Chart')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        
        plt.tight_layout()
        return fig
    
    def analyze_parameter_stability(self) -> Dict[str, Dict[str, float]]:
        """
        Analyze parameter stability across walk-forward periods.
        
        Returns:
        --------
        Dict[str, Dict[str, float]]
            Dictionary mapping parameter names to stability metrics
        """
        if not self.optimized_params:
            raise ValueError("No optimized parameters to analyze. Run the walk-forward test with optimization_func.")
            
        # Get all parameter names
        param_names = list(self.optimized_params[0].keys())
        
        results = {}
        for param_name in param_names:
            # Extract values
            values = []
            for params in self.optimized_params:
                if param_name in params:
                    values.append(params[param_name])
            
            if not values:
                continue
                
            # Calculate metrics
            values = np.array(values)
            mean_value = np.mean(values)
            std_value = np.std(values)
            
            # Calculate coefficient of variation (relative stability)
            cv = std_value / mean_value if mean_value != 0 else float('inf')
            
            # Calculate trend (slope of linear regression)
            x = np.arange(len(values))
            if len(values) > 1:
                slope = np.polyfit(x, values, 1)[0]
            else:
                slope = 0
                
            results[param_name] = {
                'variability': cv,
                'trend': slope,
                'min': np.min(values),
                'max': np.max(values),
                'mean': mean_value,
                'std': std_value
            }
            
        return results
    
    def compute_robustness_metrics(self) -> Dict[str, float]:
        """
        Compute robustness metrics for the walk-forward results.
        
        Returns:
        --------
        Dict[str, float]
            Dictionary of robustness metrics
        """
        if not self.results:
            raise ValueError("No results to analyze. Run the walk-forward test first.")
            
        # Calculate various robustness metrics
        
        # Consistency: Fraction of periods with positive returns
        positive_periods = 0
        for result in self.results:
            if result['backtest_result']['metrics']['total_return'] > 0:
                positive_periods += 1
        consistency = positive_periods / len(self.results)
        
        # Reliability: Fraction of periods with returns above a threshold (e.g., risk-free rate)
        threshold = 0.01  # 1% threshold (simplified)
        reliable_periods = 0
        for result in self.results:
            if result['backtest_result']['metrics']['total_return'] > threshold:
                reliable_periods += 1
        reliability = reliable_periods / len(self.results)
        
        # Drawdown resilience: Average ratio of drawdown to return
        dd_ratios = []
        for result in self.results:
            metrics = result['backtest_result']['metrics']
            total_return = metrics['total_return']
            max_drawdown = metrics['max_drawdown']
            if total_return > 0 and max_drawdown < 0:
                dd_ratios.append(abs(max_drawdown) / total_return)
        dd_resilience = 1 / np.mean(dd_ratios) if dd_ratios else 0
        
        # Volatility ratio: Ratio of upside to downside volatility
        returns = self.combined_results['returns']
        up_returns = returns[returns > 0]
        down_returns = returns[returns < 0]
        up_vol = up_returns.std() if not up_returns.empty else 0
        down_vol = down_returns.std() if not down_returns.empty else float('inf')
        vol_ratio = up_vol / down_vol if down_vol > 0 else float('inf')
        
        # Overall robustness score (simplified)
        robustness = (consistency + reliability + min(dd_resilience, 1) + min(vol_ratio, 2) / 2) / 3.5
        
        return {
            'consistency': consistency,
            'reliability': reliability,
            'drawdown_resilience': dd_resilience,
            'volatility_ratio': vol_ratio,
            'overall_robustness': robustness
        }
    
    def save_results(self, file_path: str):
        """
        Save walk-forward test results to a file.
        
        Parameters:
        -----------
        file_path : str
            Path to save the results
        """
        if not self.combined_results:
            raise ValueError("No results to save. Run the walk-forward test first.")
            
        # Create a serializable version of the results
        serializable = {
            'parameters': {
                'train_size': self.train_size,
                'test_size': self.test_size,
                'step_size': self.step_size,
                'window_type': self.window_type,
                'purge_window': self.purge_window,
                'embargo_window': self.embargo_window,
                'initial_capital': self.initial_capital,
                'commission': self.commission,
                'slippage': self.slippage
            },
            'train_test_indices': [
                {
                    'period': i+1,
                    'train_start': result['train_start'].strftime('%Y-%m-%d'),
                    'train_end': result['train_end'].strftime('%Y-%m-%d'),
                    'test_start': result['test_start'].strftime('%Y-%m-%d'),
                    'test_end': result['test_end'].strftime('%Y-%m-%d')
                }
                for i, result in enumerate(self.results)
            ],
            'optimized_params': self.optimized_params,
            'metrics': self.combined_results['metrics'],
            'period_metrics': [result['backtest_result']['metrics'] for result in self.results],
            'trades_summary': {
                'total_trades': len(self.combined_results['trades']),
                'winning_trades': sum(1 for t in self.combined_results['trades'] if t['pnl'] > 0),
                'losing_trades': sum(1 for t in self.combined_results['trades'] if t['pnl'] <= 0),
                'total_pnl': sum(t['pnl'] for t in self.combined_results['trades'])
            }
        }
        
        # Save as JSON
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(serializable, f, indent=2)
            
        logger.info(f"Saved walk-forward test results to {file_path}")
    
    @classmethod
    def load_results(cls, file_path: str) -> Dict[str, Any]:
        """
        Load walk-forward test results from a file.
        
        Parameters:
        -----------
        file_path : str
            Path to load the results from
            
        Returns:
        --------
        Dict[str, Any]
            Dictionary of loaded results
        """
        with open(file_path, 'r') as f:
            results = json.load(f)
            
        logger.info(f"Loaded walk-forward test results from {file_path}")
        return results 