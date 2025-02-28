"""
Backtesting Engine Module
-----------------------
Provides functionality for backtesting trading strategies
"""

import os
import logging
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, List, Union, Any, Optional, Tuple, Type

import pandas as pd
import matplotlib.pyplot as plt
import backtrader as bt
import numpy as np
import traceback
import sys

import config
from trading.strategies import FundingRateMomentumStrategy, LiquidityAwareScalpingStrategy, VolumeBreakoutStrategy, MacroFundingStrategy, AggressiveFundingStrategy, RenaissanceInspiredStrategy

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    Backtesting engine for evaluating trading strategies
    """
    
    def __init__(self, initial_cash: float = 2000.0, commission: float = 0.001):
        """
        Initialize backtesting engine
        
        Args:
            initial_cash: Initial capital for backtesting
            commission: Trading commission (e.g., 0.001 for 0.1%)
        """
        self.initial_cash = initial_cash
        self.commission = commission
        self.cerebro = bt.Cerebro()
        self.results = None
        self.strategy_params = {}
        
        # Configure cerebro
        self.cerebro.broker.setcash(initial_cash)
        self.cerebro.broker.setcommission(commission=commission)
        
        # Configure default plotting style
        plt.rcParams['figure.figsize'] = [15, 10]
        plt.rcParams['figure.dpi'] = 100
        
        # Create results directory
        self.results_dir = config.BASE_DIR / 'results'
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def add_data(self, data: pd.DataFrame, name: str = 'primary') -> None:
        """
        Add data feed to the backtesting engine
        
        Args:
            data: DataFrame with OHLCV data
            name: Name for the data feed
        """
        try:
            # Create a copy to avoid modifying the original
            df = data.copy()
            
            # Check if data has required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                return
            
            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'time' in df.columns:
                    df.set_index('time', inplace=True)
                    logger.info("Set DataFrame index to 'time' column")
                else:
                    logger.error("DataFrame index is not DatetimeIndex and has no 'time' column")
                    return
            
            # Create data feed
            data_feed = bt.feeds.PandasData(
                dataname=df,
                name=name,
                timeframe=bt.TimeFrame.Minutes if 'min' in str(df.index.freq) else bt.TimeFrame.Days
            )
            
            # Add to cerebro
            self.cerebro.adddata(data_feed, name=name)
            logger.info(f"Added data feed with {len(df)} bars")
            
        except Exception as e:
            logger.error(f"Error adding data feed: {str(e)}")
    
    def add_strategy(self, strategy_class: Type[bt.Strategy], params: Dict = None) -> None:
        """
        Add a trading strategy to the backtesting engine
        
        Args:
            strategy_class: Strategy class to test
            params: Parameters to pass to the strategy
        """
        try:
            # Store strategy parameters for later reference
            strategy_name = strategy_class.__name__
            self.strategy_params[strategy_name] = params or {}
            
            # Add strategy to cerebro
            self.cerebro.addstrategy(strategy_class, **self.strategy_params[strategy_name])
            logger.info(f"Added strategy {strategy_name} with parameters: {self.strategy_params[strategy_name]}")
            
        except Exception as e:
            logger.error(f"Error adding strategy: {str(e)}")
    
    def add_analyzers(self) -> None:
        """Add standard analyzers to the backtesting engine"""
        try:
            # Sharpe Ratio
            self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
            
            # Drawdown
            self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            
            # Returns
            self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
            
            # Trade analysis
            self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
            
            # Annual returns
            self.cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')
            
            # Monthly returns
            self.cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='monthly', timeframe=bt.TimeFrame.Months)
            
            # Calmar ratio - Removed as it's not available in standard backtrader
            # self.cerebro.addanalyzer(bt.analyzers.CalmarRatio, _name='calmar')
            
            logger.info("Added standard analyzers")
            
        except Exception as e:
            logger.error(f"Error adding analyzers: {str(e)}")
    
    def run(self) -> Dict:
        """
        Run the backtest and return results
        
        Returns:
            Dictionary with backtest results
        """
        try:
            # Add analyzers if not already added
            if not any(isinstance(a, bt.analyzers.SharpeRatio) for a in self.cerebro.analyzers):
                self.add_analyzers()
            
            # Run the backtest
            logger.info(f"Starting backtest with initial cash: {self.initial_cash}")
            self.results = self.cerebro.run()
            
            # Extract and organize results
            if not self.results:
                logger.error("No backtest results returned")
                return {
                    'initial_value': self.initial_cash,
                    'final_value': self.initial_cash,
                    'return_pct': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown_pct': 0,
                    'max_drawdown_length': 0,
                    'total_trades': 0,
                    'win_rate': 0,
                    'net_pnl': 0,
                    'avg_trade_pnl': 0
                }
                
            strat = self.results[0]
            
            # Extract metrics from analyzers
            metrics = {
                'initial_value': self.initial_cash,
                'final_value': self.cerebro.broker.getvalue(),
                'return_pct': (self.cerebro.broker.getvalue() / self.initial_cash - 1) * 100,
            }
            
            # Sharpe ratio
            sharpe = strat.analyzers.sharpe.get_analysis()
            metrics['sharpe_ratio'] = sharpe.get('sharperatio', 0)
            
            # Drawdown
            drawdown = strat.analyzers.drawdown.get_analysis()
            metrics['max_drawdown_pct'] = drawdown.get('max', {}).get('drawdown', 0)
            metrics['max_drawdown_length'] = drawdown.get('max', {}).get('len', 0)
            
            # Calculate trade statistics
            trades = getattr(strat, 'trades', None)
            
            if trades is not None:
                # Extract trade metrics
                pnl_list = trades.pnl if hasattr(trades, 'pnl') else []
                won_list = trades.won if hasattr(trades, 'won') else []
                
                # Convert to Python types to ensure safe comparisons
                total_trades = int(trades.total) if hasattr(trades, 'total') else 0
                won_trades = sum(won_list) if isinstance(won_list, (list, tuple)) else int(won_list) if won_list else 0
                
                metrics['total_trades'] = total_trades
                
                if total_trades > 0 and won_trades > 0:
                    metrics['win_rate'] = (won_trades / total_trades) * 100
                else:
                    metrics['win_rate'] = 0
                
                # PnL - Handle AutoOrderedDict issue
                try:
                    if isinstance(trades.get('pnl', {}), dict):
                        metrics['net_pnl'] = trades.get('pnl', {}).get('net', 0)
                    else:
                        # If trades.pnl is an AutoOrderedDict, we need to handle it differently
                        pnl_dict = trades.get('pnl', {})
                        metrics['net_pnl'] = getattr(pnl_dict, 'net', 0)
                except Exception as e:
                    logger.warning(f"Error extracting PnL data: {str(e)}")
                    metrics['net_pnl'] = 0
                
                # Average trade metrics
                if total_trades > 0:
                    try:
                        metrics['avg_trade_pnl'] = metrics['net_pnl'] / total_trades
                    except Exception as e:
                        logger.warning(f"Error calculating average trade PnL: {str(e)}")
                        metrics['avg_trade_pnl'] = 0
                    
                    # Average trade length - Handle potential AutoOrderedDict
                    try:
                        if isinstance(trades.get('len', {}), dict):
                            metrics['avg_trade_bars'] = trades.get('len', {}).get('average', 0)
                        else:
                            len_dict = trades.get('len', {})
                            metrics['avg_trade_bars'] = getattr(len_dict, 'average', 0)
                    except Exception as e:
                        logger.warning(f"Error extracting trade length data: {str(e)}")
                        metrics['avg_trade_bars'] = 0
                
                # Annual returns
                try:
                    annual = strat.analyzers.annual.get_analysis()
                    
                    # Enhanced error handling for AutoOrderedDict
                    metrics['annual_returns'] = {}
                    
                    # Safely extract data from annual returns
                    if annual:
                        for year in annual:
                            try:
                                year_str = str(year)
                                return_val = float(annual[year])
                                metrics['annual_returns'][year_str] = return_val
                            except Exception as inner_e:
                                logger.warning(f"Error extracting return for year {year}: {str(inner_e)}")
                                continue
                except Exception as e:
                    logger.warning(f"Error extracting annual returns: {str(e)}")
                    metrics['annual_returns'] = {}
            
            # Save results
            self.save_results(metrics)
            
            logger.info(f"Backtest completed. Final value: {metrics['final_value']:.2f}, Return: {metrics['return_pct']:.2f}%")
            return metrics
            
        except Exception as e:
            logger.error(f"Error running backtest: {str(e)}")
            logger.error("Detailed error information:")
            tb = traceback.format_exc()
            logger.error(tb)
            
            # Check if this is a dict append error and print more details
            if "'dict' object has no attribute 'append'" in str(e):
                logger.error("Dictionary append error detected. Examining call stack:")
                frames = traceback.extract_tb(sys.exc_info()[2])
                for i, frame in enumerate(frames):
                    logger.error(f"Frame {i}: {frame.filename}:{frame.lineno} in {frame.name}")
                    logger.error(f"   Code: {frame.line}")
                    
                    if "append" in frame.line:
                        # Found the problematic append - try to get the variable name
                        line = frame.line.strip()
                        var_name = line.split(".append")[0].strip()
                        logger.error(f"Problematic append operation on variable: {var_name}")
            
            return {
                'initial_value': self.initial_cash,
                'final_value': self.initial_cash,
                'return_pct': 0,
                'sharpe_ratio': 0,
                'max_drawdown_pct': 0,
                'max_drawdown_length': 0,
                'total_trades': 0,
                'win_rate': 0,
                'net_pnl': 0,
                'avg_trade_pnl': 0,
                'error': str(e)
            }
    
    def plot(self, filename: str = None, show_plot: bool = False) -> bool:
        """
        Generate and save plots of the backtest results
        
        Args:
            filename: Name of the file to save the plot (without extension)
            show_plot: Whether to display the plot (in Jupyter notebooks)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.results is None:
                logger.error("No backtest results to plot")
                return False
            
            # Generate default filename if not provided
            if filename is None:
                strategy_name = list(self.strategy_params.keys())[0] if self.strategy_params else "backtest"
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{strategy_name}_{timestamp}"
            
            # Ensure filename has no extension
            filename = os.path.splitext(filename)[0]
            
            # Full path to save the file
            filepath = self.results_dir / f"{filename}.png"
            
            # Generate plot
            plt.figure(figsize=(15, 10))
            plot = self.cerebro.plot(style=config.BACKTEST_CONFIG['plot_style'], barup='green', bardown='red')
            
            # Save plot
            plt.savefig(filepath)
            logger.info(f"Plot saved as {filepath}")
            
            # Show plot if requested
            if show_plot:
                plt.show()
            else:
                plt.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error plotting backtest results: {str(e)}")
            return False
    
    def save_results(self, metrics: Dict) -> bool:
        """
        Save backtest results to a JSON file
        
        Args:
            metrics: Dictionary of backtest metrics
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate filename
            strategy_name = list(self.strategy_params.keys())[0] if self.strategy_params else "backtest"
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{strategy_name}_{timestamp}.json"
            
            # Full path to save the file
            filepath = self.results_dir / filename
            
            # Add strategy parameters to metrics
            metrics['strategy_params'] = self.strategy_params
            
            # Add timestamp
            metrics['timestamp'] = timestamp
            metrics['date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Helper function to safely convert AutoOrderedDict and other non-serializable types
            def safe_serialize(obj):
                if isinstance(obj, (int, float, str, bool, list, dict)) or obj is None:
                    return obj
                elif isinstance(obj, np.float64):
                    return float(obj)
                elif isinstance(obj, np.int64):
                    return int(obj)
                elif hasattr(obj, '__dict__'):
                    # Handle objects with __dict__ attribute (including AutoOrderedDict)
                    result = {}
                    for key in dir(obj):
                        # Skip private attributes and methods
                        if not key.startswith('_') and not callable(getattr(obj, key)):
                            try:
                                value = getattr(obj, key)
                                result[key] = safe_serialize(value)
                            except:
                                # Skip attributes that can't be serialized
                                pass
                    return result
                else:
                    # Fallback to string representation
                    return str(obj)
            
            # Process all metrics for JSON serialization
            metrics_json = {}
            for key, value in metrics.items():
                metrics_json[key] = safe_serialize(value)
            
            # Save to JSON file
            with open(filepath, 'w') as f:
                json.dump(metrics_json, f, indent=4)
                
            logger.info(f"Results saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving backtest results: {str(e)}")
            return False

def run_strategy_backtest(data: pd.DataFrame, strategy_name: str, 
                         params: Dict = None, initial_cash: float = 2000.0,
                         plot: bool = True) -> Dict:
    """
    Run a backtest for a specific strategy
    
    Args:
        data: DataFrame with OHLCV data
        strategy_name: Name of the strategy to test
        params: Parameters for the strategy
        initial_cash: Initial capital for the backtest
        plot: Whether to generate and save a plot
        
    Returns:
        Dictionary with backtest results
    """
    try:
        # Create backtest engine
        engine = BacktestEngine(initial_cash=initial_cash)
        
        # Add data
        engine.add_data(data)
        
        # Map strategy name to class
        strategy_map = {
            'funding_momentum': FundingRateMomentumStrategy,
            'liquidity_scalping': LiquidityAwareScalpingStrategy,
            'volume_breakout': VolumeBreakoutStrategy,
            'macro_funding': MacroFundingStrategy,
            'aggressive_funding': AggressiveFundingStrategy,
            'renaissance': RenaissanceInspiredStrategy
        }
        
        # Get strategy class
        if strategy_name not in strategy_map:
            logger.error(f"Unknown strategy: {strategy_name}")
            return {}
        
        strategy_class = strategy_map[strategy_name]
        
        # Get default parameters
        default_params = config.STRATEGY_PARAMS.get(strategy_name, {})
        
        # Merge with provided parameters
        final_params = default_params.copy()
        if params:
            final_params.update(params)
        
        # Add strategy
        engine.add_strategy(strategy_class, final_params)
        
        # Run backtest
        results = engine.run()
        
        # Generate plot if requested
        if plot:
            engine.plot()
        
        return results
        
    except Exception as e:
        logger.error(f"Error running strategy backtest: {str(e)}")
        return {}

def compare_strategies(data: pd.DataFrame, strategy_configs: List[Dict], 
                     initial_cash: float = 2000.0) -> Dict:
    """
    Compare multiple strategies or parameter sets
    
    Args:
        data: DataFrame with OHLCV data
        strategy_configs: List of strategy configurations
            [{'name': 'strategy_name', 'params': {param_dict}}]
        initial_cash: Initial capital for each backtest
        
    Returns:
        Dictionary with comparison results
    """
    try:
        results = []
        
        # Run backtest for each strategy configuration
        for config in strategy_configs:
            strategy_name = config.get('name')
            params = config.get('params', {})
            
            logger.info(f"Running backtest for {strategy_name} with parameters: {params}")
            
            # Run backtest
            result = run_strategy_backtest(
                data=data,
                strategy_name=strategy_name,
                params=params,
                initial_cash=initial_cash,
                plot=True
            )
            
            # Add strategy info to results
            result['strategy_name'] = strategy_name
            result['strategy_params'] = params
            
            results.append(result)
        
        # Create comparison summary
        comparison = {
            'strategies': len(results),
            'best_return': max(r['return_pct'] for r in results) if results else 0,
            'worst_return': min(r['return_pct'] for r in results) if results else 0,
            'best_sharpe': max(r['sharpe_ratio'] for r in results) if results else 0,
            'results': results
        }
        
        # Identify best strategy
        if results:
            # Sort by return (could use other metrics)
            sorted_results = sorted(results, key=lambda x: x['return_pct'], reverse=True)
            best_result = sorted_results[0]
            
            comparison['best_strategy'] = {
                'name': best_result['strategy_name'],
                'params': best_result['strategy_params'],
                'return_pct': best_result['return_pct'],
                'sharpe_ratio': best_result['sharpe_ratio']
            }
        
        # Save comparison results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"strategy_comparison_{timestamp}.json"
        filepath = config.BASE_DIR / 'results' / filename
        
        with open(filepath, 'w') as f:
            json.dump(comparison, f, indent=4)
        
        logger.info(f"Strategy comparison saved to {filepath}")
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing strategies: {str(e)}")
        return {}