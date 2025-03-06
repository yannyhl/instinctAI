"""
Backtest Engine Module

This module provides the core functionality for backtesting trading strategies on historical data.
It includes the Backtest class, which orchestrates the backtesting process, and various utility
functions for running backtests and managing backtest results.

The backtesting engine is designed to be flexible, extensible, and highly configurable,
allowing for realistic simulation of trading strategies under various market conditions.
"""

import datetime
import json
import os
import pickle
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable, Type

import numpy as np
import pandas as pd

from advanced_trading.core.observability import get_logger
from advanced_trading.core.common import ComponentRegistry
from advanced_trading.strategies.base import Strategy, StrategyConfig

# Initialize logger
logger = get_logger(__name__)


class BacktestMode(Enum):
    """Backtesting modes supported by the engine."""
    EVENT_DRIVEN = "event_driven"
    VECTORIZED = "vectorized"
    MIXED = "mixed"


@dataclass
class BacktestConfig:
    """
    Configuration for a backtest.
    
    This class defines the configuration parameters for running a backtest,
    including data sources, time periods, and simulation parameters.
    
    Attributes:
        name (str): The name of the backtest.
        strategy_config (StrategyConfig): The configuration for the strategy to test.
        start_date (datetime.datetime): The start date for the backtest.
        end_date (datetime.datetime): The end date for the backtest.
        initial_capital (float): The initial capital for the backtest.
        mode (BacktestMode): The mode to use for backtesting.
        data_frequency (str): The frequency of the data (e.g., "1m", "1h", "1d").
        symbols (List[str]): The trading symbols to include in the backtest.
        commission_model (str): The commission model to use.
        slippage_model (str): The slippage model to use.
        execution_model (str): The execution model to use.
        risk_model (str): The risk model to use.
        benchmark (Optional[str]): The benchmark symbol to compare against.
        additional_params (Dict[str, Any]): Additional parameters for the backtest.
    """
    name: str
    strategy_config: StrategyConfig
    start_date: datetime.datetime
    end_date: datetime.datetime
    initial_capital: float = 100000.0
    mode: BacktestMode = BacktestMode.EVENT_DRIVEN
    data_frequency: str = "1d"
    symbols: List[str] = field(default_factory=list)
    commission_model: str = "percentage"
    slippage_model: str = "fixed"
    execution_model: str = "market"
    risk_model: str = "fixed"
    benchmark: Optional[str] = None
    additional_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """
    Results of a backtest.
    
    This class encapsulates the results of running a backtest, including
    performance metrics, trade history, and equity curve.
    
    Attributes:
        config (BacktestConfig): The configuration used for the backtest.
        equity_curve (pd.DataFrame): The equity curve over time.
        trades (pd.DataFrame): The trade history.
        positions (pd.DataFrame): The position history.
        performance_metrics (Dict[str, float]): Performance metrics for the backtest.
        drawdowns (pd.DataFrame): Drawdown history.
        risk_metrics (Dict[str, float]): Risk metrics for the backtest.
        execution_metrics (Dict[str, float]): Execution metrics for the backtest.
        additional_results (Dict[str, Any]): Additional results from the backtest.
    """
    config: BacktestConfig
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    positions: pd.DataFrame
    performance_metrics: Dict[str, float]
    drawdowns: pd.DataFrame
    risk_metrics: Dict[str, float]
    execution_metrics: Dict[str, float]
    additional_results: Dict[str, Any] = field(default_factory=dict)


class Backtest:
    """
    Core backtesting engine.
    
    This class orchestrates the backtesting process, including loading data,
    simulating strategy execution, and calculating performance metrics.
    
    Attributes:
        config (BacktestConfig): The configuration for the backtest.
        strategy (Strategy): The strategy being tested.
        data_handler: The data handler for loading and processing data.
        portfolio_manager: The portfolio manager for tracking positions and equity.
        simulator: The simulator for executing trades.
        results (Optional[BacktestResult]): The results of the backtest, if available.
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize the backtest.
        
        Args:
            config (BacktestConfig): The configuration for the backtest.
        """
        self.config = config
        self.strategy = None
        self.data_handler = None
        self.portfolio_manager = None
        self.simulator = None
        self.results = None
        
        logger.info(f"Initialized backtest '{config.name}' from {config.start_date} to {config.end_date}")
    
    def setup(self) -> None:
        """
        Set up the backtest.
        
        This method initializes the data handler, portfolio manager, simulator,
        and strategy for the backtest.
        """
        # Import here to avoid circular imports
        from advanced_trading.backtesting.engine.data_handler import get_data_handler
        from advanced_trading.backtesting.engine.portfolio import create_portfolio
        from advanced_trading.backtesting.engine.simulation import get_simulator
        from advanced_trading.strategies.factory import create_strategy
        
        # Create data handler
        self.data_handler = get_data_handler(
            symbols=self.config.symbols,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            frequency=self.config.data_frequency
        )
        
        # Create portfolio manager
        self.portfolio_manager = create_portfolio(
            initial_capital=self.config.initial_capital,
            symbols=self.config.symbols
        )
        
        # Create simulator
        self.simulator = get_simulator(
            commission_model=self.config.commission_model,
            slippage_model=self.config.slippage_model,
            execution_model=self.config.execution_model
        )
        
        # Create strategy
        self.strategy = create_strategy(self.config.strategy_config)
        
        logger.info(f"Setup complete for backtest '{self.config.name}'")
    
    def run(self) -> BacktestResult:
        """
        Run the backtest.
        
        This method runs the backtest, simulating the execution of the strategy
        on historical data and tracking the results.
        
        Returns:
            BacktestResult: The results of the backtest.
        """
        if self.strategy is None:
            self.setup()
        
        logger.info(f"Running backtest '{self.config.name}'")
        
        # Event-driven backtest
        if self.config.mode == BacktestMode.EVENT_DRIVEN:
            self._run_event_driven()
        
        # Vectorized backtest
        elif self.config.mode == BacktestMode.VECTORIZED:
            self._run_vectorized()
        
        # Mixed backtest
        elif self.config.mode == BacktestMode.MIXED:
            self._run_mixed()
        
        # Calculate performance metrics
        self._calculate_performance_metrics()
        
        logger.info(f"Backtest '{self.config.name}' completed")
        
        return self.results
    
    def _run_event_driven(self) -> None:
        """
        Run an event-driven backtest.
        
        In an event-driven backtest, the engine processes data events one at a time,
        simulating the strategy's response to each event and tracking the results.
        """
        # Initialize result containers
        equity_curve = []
        trades = []
        positions = []
        
        # Get data events
        data_events = self.data_handler.get_data_events()
        
        # Process each event
        for event in data_events:
            # Update portfolio with current prices
            self.portfolio_manager.update_prices(event['prices'])
            
            # Process data with strategy
            signals = self.strategy.process_data(event['data'])
            
            # Execute signals
            if signals:
                executed_trades = self.simulator.execute_signals(
                    signals=signals,
                    portfolio=self.portfolio_manager,
                    prices=event['prices'],
                    timestamp=event['timestamp']
                )
                
                # Record trades
                trades.extend(executed_trades)
            
            # Record portfolio state
            portfolio_state = self.portfolio_manager.get_state()
            equity_curve.append({
                'timestamp': event['timestamp'],
                'equity': portfolio_state.equity,
                'cash': portfolio_state.cash,
                'positions_value': portfolio_state.positions_value
            })
            
            # Record positions
            for symbol, position in portfolio_state.positions.items():
                positions.append({
                    'timestamp': event['timestamp'],
                    'symbol': symbol,
                    'quantity': position.quantity,
                    'price': position.price,
                    'value': position.value
                })
        
        # Convert to DataFrames
        equity_df = pd.DataFrame(equity_curve)
        equity_df.set_index('timestamp', inplace=True)
        
        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            trades_df.set_index('timestamp', inplace=True)
        
        positions_df = pd.DataFrame(positions)
        if not positions_df.empty:
            positions_df.set_index(['timestamp', 'symbol'], inplace=True)
        
        # Calculate drawdowns
        drawdowns_df = self._calculate_drawdowns(equity_df)
        
        # Create results
        self.results = BacktestResult(
            config=self.config,
            equity_curve=equity_df,
            trades=trades_df,
            positions=positions_df,
            performance_metrics={},
            drawdowns=drawdowns_df,
            risk_metrics={},
            execution_metrics={}
        )
    
    def _run_vectorized(self) -> None:
        """
        Run a vectorized backtest.
        
        In a vectorized backtest, the engine processes all data at once using
        vectorized operations, which can be much faster for certain strategies.
        """
        # Get all data at once
        data = self.data_handler.get_all_data()
        
        # Process data with strategy
        signals = self.strategy.generate_signals(data)
        
        # Simulate portfolio performance
        # This would typically use vectorized operations to calculate equity, trades, etc.
        # For now, we'll just create empty result containers
        equity_curve = pd.DataFrame()
        trades = pd.DataFrame()
        positions = pd.DataFrame()
        drawdowns = pd.DataFrame()
        
        # Create results
        self.results = BacktestResult(
            config=self.config,
            equity_curve=equity_curve,
            trades=trades,
            positions=positions,
            performance_metrics={},
            drawdowns=drawdowns,
            risk_metrics={},
            execution_metrics={}
        )
    
    def _run_mixed(self) -> None:
        """
        Run a mixed backtest.
        
        A mixed backtest combines elements of both event-driven and vectorized
        approaches, using vectorized operations where possible but processing
        some events individually.
        """
        # This would typically implement a hybrid approach
        # For now, we'll just use the event-driven approach
        self._run_event_driven()
    
    def _calculate_drawdowns(self, equity_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate drawdowns from an equity curve.
        
        Args:
            equity_df (pd.DataFrame): The equity curve.
        
        Returns:
            pd.DataFrame: The drawdowns.
        """
        # Calculate running maximum
        running_max = equity_df['equity'].cummax()
        
        # Calculate drawdowns
        drawdowns = (equity_df['equity'] / running_max) - 1
        
        # Calculate drawdown duration
        in_drawdown = drawdowns < 0
        drawdown_start = in_drawdown.ne(in_drawdown.shift()).cumsum()
        drawdown_duration = in_drawdown.groupby(drawdown_start).cumsum()
        
        # Create drawdowns DataFrame
        drawdowns_df = pd.DataFrame({
            'equity': equity_df['equity'],
            'running_max': running_max,
            'drawdown': drawdowns,
            'duration': drawdown_duration
        })
        
        return drawdowns_df
    
    def _calculate_performance_metrics(self) -> None:
        """
        Calculate performance metrics from backtest results.
        """
        if self.results is None:
            return
        
        # Get equity curve
        equity = self.results.equity_curve['equity']
        
        # Calculate returns
        returns = equity.pct_change().dropna()
        
        # Calculate basic metrics
        total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
        annualized_return = (1 + total_return) ** (252 / len(returns)) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # Calculate max drawdown
        max_drawdown = self.results.drawdowns['drawdown'].min()
        
        # Store metrics
        performance_metrics = {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown
        }
        
        # Calculate risk metrics
        risk_metrics = {
            'var_95': np.percentile(returns, 5),
            'var_99': np.percentile(returns, 1),
            'worst_day': returns.min(),
            'best_day': returns.max(),
            'avg_drawdown': self.results.drawdowns['drawdown'][self.results.drawdowns['drawdown'] < 0].mean(),
            'avg_drawdown_duration': self.results.drawdowns['duration'][self.results.drawdowns['drawdown'] < 0].mean()
        }
        
        # Calculate execution metrics
        if not self.results.trades.empty:
            execution_metrics = {
                'total_trades': len(self.results.trades),
                'win_rate': (self.results.trades['pnl'] > 0).mean(),
                'avg_trade_pnl': self.results.trades['pnl'].mean(),
                'avg_win': self.results.trades[self.results.trades['pnl'] > 0]['pnl'].mean(),
                'avg_loss': self.results.trades[self.results.trades['pnl'] < 0]['pnl'].mean(),
                'profit_factor': abs(self.results.trades[self.results.trades['pnl'] > 0]['pnl'].sum() / self.results.trades[self.results.trades['pnl'] < 0]['pnl'].sum()),
                'avg_trade_duration': (self.results.trades['exit_time'] - self.results.trades['entry_time']).mean()
            }
        else:
            execution_metrics = {}
        
        # Update results
        self.results.performance_metrics = performance_metrics
        self.results.risk_metrics = risk_metrics
        self.results.execution_metrics = execution_metrics


def run_backtest(config: BacktestConfig) -> BacktestResult:
    """
    Run a backtest with the specified configuration.
    
    Args:
        config (BacktestConfig): The configuration for the backtest.
    
    Returns:
        BacktestResult: The results of the backtest.
    """
    backtest = Backtest(config)
    return backtest.run()


def save_backtest_results(results: BacktestResult, path: str) -> None:
    """
    Save backtest results to a file.
    
    Args:
        results (BacktestResult): The results to save.
        path (str): The path to save to.
    """
    with open(path, 'wb') as f:
        pickle.dump(results, f)
    
    logger.info(f"Saved backtest results to {path}")


def load_backtest_results(path: str) -> BacktestResult:
    """
    Load backtest results from a file.
    
    Args:
        path (str): The path to load from.
    
    Returns:
        BacktestResult: The loaded results.
    
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid backtest results file.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    
    with open(path, 'rb') as f:
        results = pickle.load(f)
    
    if not isinstance(results, BacktestResult):
        raise ValueError(f"File does not contain backtest results: {path}")
    
    logger.info(f"Loaded backtest results from {path}")
    
    return results


def get_backtest_config(name: str, strategy_name: str, **kwargs) -> BacktestConfig:
    """
    Create a backtest configuration.
    
    Args:
        name (str): The name of the backtest.
        strategy_name (str): The name of the strategy to test.
        **kwargs: Additional parameters for the configuration.
    
    Returns:
        BacktestConfig: The created configuration.
    """
    from advanced_trading.strategies.factory import strategy_metadata
    
    # Get strategy metadata
    metadata = strategy_metadata(strategy_name)
    
    # Create strategy configuration
    strategy_config = StrategyConfig(
        name=strategy_name,
        symbols=kwargs.get('symbols', []),
        timeframe=kwargs.get('data_frequency', '1d'),
        parameters=kwargs.get('strategy_parameters', {})
    )
    
    # Create backtest configuration
    config = BacktestConfig(
        name=name,
        strategy_config=strategy_config,
        start_date=kwargs.get('start_date', datetime.datetime.now() - datetime.timedelta(days=365)),
        end_date=kwargs.get('end_date', datetime.datetime.now()),
        initial_capital=kwargs.get('initial_capital', 100000.0),
        mode=kwargs.get('mode', BacktestMode.EVENT_DRIVEN),
        data_frequency=kwargs.get('data_frequency', '1d'),
        symbols=kwargs.get('symbols', []),
        commission_model=kwargs.get('commission_model', 'percentage'),
        slippage_model=kwargs.get('slippage_model', 'fixed'),
        execution_model=kwargs.get('execution_model', 'market'),
        risk_model=kwargs.get('risk_model', 'fixed'),
        benchmark=kwargs.get('benchmark', None),
        additional_params=kwargs.get('additional_params', {})
    )
    
    return config


def set_backtest_config(config: BacktestConfig, **kwargs) -> BacktestConfig:
    """
    Update a backtest configuration.
    
    Args:
        config (BacktestConfig): The configuration to update.
        **kwargs: The parameters to update.
    
    Returns:
        BacktestConfig: The updated configuration.
    """
    # Create a new configuration with updated parameters
    new_config = BacktestConfig(
        name=kwargs.get('name', config.name),
        strategy_config=kwargs.get('strategy_config', config.strategy_config),
        start_date=kwargs.get('start_date', config.start_date),
        end_date=kwargs.get('end_date', config.end_date),
        initial_capital=kwargs.get('initial_capital', config.initial_capital),
        mode=kwargs.get('mode', config.mode),
        data_frequency=kwargs.get('data_frequency', config.data_frequency),
        symbols=kwargs.get('symbols', config.symbols),
        commission_model=kwargs.get('commission_model', config.commission_model),
        slippage_model=kwargs.get('slippage_model', config.slippage_model),
        execution_model=kwargs.get('execution_model', config.execution_model),
        risk_model=kwargs.get('risk_model', config.risk_model),
        benchmark=kwargs.get('benchmark', config.benchmark),
        additional_params=kwargs.get('additional_params', config.additional_params)
    )
    
    return new_config


# Register components with the component registry
ComponentRegistry.register_component("backtest", Backtest)
ComponentRegistry.register_component("backtest_config", BacktestConfig)
ComponentRegistry.register_component("backtest_result", BacktestResult) 