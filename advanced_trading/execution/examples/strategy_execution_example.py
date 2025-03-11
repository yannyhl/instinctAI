"""
Strategy Execution Integration Example

This example demonstrates the complete integration between the Strategy Framework,
Risk Management System, and Execution Engine. It shows how:

1. Strategies generate trading signals
2. Signals are validated against risk parameters
3. Valid signals are converted to orders and executed
4. Execution results are analyzed and fed back to strategies

This serves as a comprehensive demonstration of the entire trading pipeline from
signal generation to execution and analysis.
"""

import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from advanced_trading.strategies.base import Strategy, StrategyConfig, StrategyType, StrategyResult
from advanced_trading.strategies.risk_integration import RiskAwareStrategyLifecycleManager
from advanced_trading.execution.strategy_bridge import (
    StrategyExecutionBridge, ExecutionMode, SignalType
)
from advanced_trading.execution.analysis.execution_analyzer import (
    ExecutionAnalyzer, BenchmarkType, ExecutionMetrics
)
from advanced_trading.execution.risk_integration.risk_manager import (
    ExecutionRiskManager, ExecutionRiskConfig, RiskCheckResult
)
from advanced_trading.risk.portfolio.controller import PortfolioRiskController
from advanced_trading.execution.exchange.order import OrderType, OrderSide, OrderStatus, TimeInForce

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MovingAverageCrossoverStrategy(Strategy):
    """
    A simple moving average crossover strategy for demonstration purposes.
    
    This strategy generates buy signals when the fast moving average crosses above
    the slow moving average, and sell signals when the fast moving average crosses
    below the slow moving average.
    """
    
    # Strategy metadata
    STRATEGY_TYPE = StrategyType.TECHNICAL
    PARAMETERS = {
        "fast_ma_period": {"type": "int", "default": 10, "description": "Fast moving average period"},
        "slow_ma_period": {"type": "int", "default": 30, "description": "Slow moving average period"},
        "position_size": {"type": "float", "default": 0.1, "description": "Position size as fraction of capital"}
    }
    REQUIRED_DATA = ["close"]
    
    def __init__(self, config: StrategyConfig):
        """Initialize the strategy."""
        super().__init__(config)
        self.fast_ma_period = 10
        self.slow_ma_period = 30
        self.position_size = 0.1
        self.version = "1.0.0"
        self.author = "Instinct AI Team"
        self.tags = ["technical", "moving_average", "crossover"]
        
        # Internal state
        self._fast_ma = {}
        self._slow_ma = {}
        self._position = {}
        self._last_signal = {}
    
    def initialize(self, parameters: Optional[Dict[str, Any]] = None, 
                 dependencies: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the strategy."""
        logger.info(f"Initializing {self.name} strategy")
        
        # Set parameters
        if parameters:
            if "fast_ma_period" in parameters:
                self.fast_ma_period = parameters["fast_ma_period"]
            if "slow_ma_period" in parameters:
                self.slow_ma_period = parameters["slow_ma_period"]
            if "position_size" in parameters:
                self.position_size = parameters["position_size"]
        
        # Initialize state
        for symbol in self.config.symbols:
            self._fast_ma[symbol] = None
            self._slow_ma[symbol] = None
            self._position[symbol] = 0.0
            self._last_signal[symbol] = None
        
        logger.info(f"Strategy {self.name} initialized with fast_ma={self.fast_ma_period}, " 
                   f"slow_ma={self.slow_ma_period}, position_size={self.position_size}")
    
    def process_warmup_data(self, data: pd.DataFrame) -> None:
        """Process warm-up data."""
        logger.info(f"Processing warm-up data with {len(data)} rows")
        
        # Convert data to dict format expected by process_data
        symbols = self.config.symbols
        if len(symbols) == 1:
            data_dict = {symbols[0]: data}
        else:
            # Assume data has a 'symbol' column
            data_dict = {}
            for symbol in symbols:
                symbol_data = data[data['symbol'] == symbol] if 'symbol' in data.columns else data
                data_dict[symbol] = symbol_data
        
        # Process data
        self.process_data(data_dict)
        
        logger.info("Warm-up data processed")
    
    def process_data(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Process market data."""
        result = {}
        
        for symbol, df in data.items():
            # Skip if symbol not in config
            if symbol not in self.config.symbols:
                continue
                
            # Calculate moving averages
            if 'close' not in df.columns:
                logger.warning(f"Close price column not found in data for {symbol}")
                continue
                
            processed = df.copy()
            processed['fast_ma'] = processed['close'].rolling(window=self.fast_ma_period).mean()
            processed['slow_ma'] = processed['close'].rolling(window=self.slow_ma_period).mean()
            
            # Calculate crossover signal
            processed['signal'] = 0.0
            # Buy signal when fast MA crosses above slow MA
            buy_signal = (processed['fast_ma'] > processed['slow_ma']) & (processed['fast_ma'].shift(1) <= processed['slow_ma'].shift(1))
            # Sell signal when fast MA crosses below slow MA
            sell_signal = (processed['fast_ma'] < processed['slow_ma']) & (processed['fast_ma'].shift(1) >= processed['slow_ma'].shift(1))
            
            # Set signals with position size
            processed.loc[buy_signal, 'signal'] = self.position_size
            processed.loc[sell_signal, 'signal'] = -self.position_size
            
            # Update internal state
            if not processed.empty:
                self._fast_ma[symbol] = processed['fast_ma'].iloc[-1]
                self._slow_ma[symbol] = processed['slow_ma'].iloc[-1]
                self._last_signal[symbol] = processed['signal'].iloc[-1]
            
            result[symbol] = processed
            
        return result
    
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Generate trading signals."""
        signals = {}
        
        for symbol, df in data.items():
            # Extract rows with signals
            signal_rows = df[df['signal'] != 0].copy()
            
            if not signal_rows.empty:
                # Create signals dataframe
                signals_df = pd.DataFrame()
                signals_df['timestamp'] = signal_rows.index
                signals_df['signal'] = signal_rows['signal']
                signals_df['price'] = signal_rows['close']
                signals_df['type'] = [SignalType.ENTRY.value if s > 0 else SignalType.EXIT.value for s in signal_rows['signal']]
                
                # Add to signals dict
                signals[symbol] = signals_df
                
                # Update state with signals
                for _, row in signals_df.iterrows():
                    self.state.add_signal(symbol, {
                        'timestamp': row['timestamp'],
                        'signal': row['signal'],
                        'price': row['price'],
                        'type': row['type']
                    })
                    
                    # Update position in state
                    current_position = self._position.get(symbol, 0.0)
                    new_position = current_position + row['signal']
                    self._position[symbol] = new_position
                    
                    # Update position in strategy state
                    self.state.update_position(symbol, {
                        'timestamp': row['timestamp'],
                        'position': new_position,
                        'price': row['price']
                    })
        
        return signals
    
    def execute(self, signals: Dict[str, pd.DataFrame]) -> StrategyResult:
        """Execute trading signals (in live mode, this would be handled by the execution bridge)."""
        # In a real implementation, this would delegate to the execution bridge
        # For this example, we'll create a minimal result
        
        # Create result
        result = StrategyResult(
            strategy_name=self.name,
            signals=signals,
            positions=pd.DataFrame([
                {'symbol': s, 'position': p, 'timestamp': datetime.now()}
                for s, p in self._position.items()
            ]) if self._position else None,
            timestamp=datetime.now()
        )
        
        return result


def generate_sample_price_data(symbols, periods=500, frequency='1h'):
    """Generate sample OHLCV data for testing."""
    data = {}
    for symbol in symbols:
        # Start with a random price
        start_price = np.random.uniform(100, 1000)
        
        # Generate price movement with a trend and some volatility
        # Add both trend and mean reversion components
        trend = np.cumsum(np.random.normal(0.0002, 0.001, periods))
        noise = np.random.normal(0, 0.005, periods)
        mean_reversion = np.sin(np.linspace(0, 10, periods)) * 0.02
        
        returns = trend + noise + mean_reversion
        prices = start_price * np.cumprod(1 + returns)
        
        # Create OHLCV dataframe
        df = pd.DataFrame({
            'open': prices * np.random.uniform(0.998, 1.002, periods),
            'high': prices * np.random.uniform(1.001, 1.005, periods),
            'low': prices * np.random.uniform(0.995, 0.999, periods),
            'close': prices,
            'volume': np.random.uniform(1000, 10000, periods)
        })
        
        # Set index to timestamp
        df.index = pd.date_range(start='2023-01-01', periods=periods, freq=frequency)
        
        data[symbol] = df
    
    return data


def main():
    """Run the strategy execution integration example."""
    logger.info("Starting strategy execution integration example")
    
    # Step 1: Create risk configuration
    risk_config = ExecutionRiskConfig(
        enabled=True,
        enforce_pre_trade_checks=True,
        max_position_size_percent=0.2,
        max_order_notional=10000,
        max_position_notional=20000,
        max_order_count_per_minute=10
    )
    
    # Step 2: Create execution risk manager
    execution_risk_manager = ExecutionRiskManager(risk_config)
    
    # Step 3: Create portfolio risk controller
    portfolio_risk_controller = PortfolioRiskController(
        max_portfolio_exposure=1.0,
        max_correlation_exposure=0.5,
        drawdown_control_threshold=0.1,
        target_portfolio_volatility=0.15
    )
    
    # Step 4: Create risk-aware strategy lifecycle manager
    lifecycle_manager = RiskAwareStrategyLifecycleManager(
        risk_config=None,
        portfolio_risk_controller=portfolio_risk_controller,
        enforce_risk_limits=True,
        auto_adjust_position_sizes=True,
        emergency_stop_on_violation=True
    )
    
    # Step 5: Create execution bridge
    execution_bridge = StrategyExecutionBridge(
        execution_mode=ExecutionMode.SIMULATION,  # Use simulation mode for the example
        risk_manager=execution_risk_manager,
        analyze_executions=True
    )
    
    # Step 6: Create strategy configuration
    symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
    strategy_config = StrategyConfig(
        name="MA Crossover Strategy",
        symbols=symbols,
        timeframe="1h",
        parameters={
            "fast_ma_period": 10,
            "slow_ma_period": 30,
            "position_size": 0.1
        },
        risk_limits={
            "max_position": 0.5,
            "max_drawdown": 0.05
        }
    )
    
    # Step 7: Create strategy instance
    strategy = MovingAverageCrossoverStrategy(strategy_config)
    
    # Step 8: Register strategy with lifecycle manager
    strategy_id = lifecycle_manager.register_strategy(
        strategy=strategy,
        strategy_id="ma_crossover_001",
        parameters=strategy_config.parameters,
        dependencies={},
        warmup_bars=50,
        auto_initialize=True,
        risk_limits={
            "position": {
                "max_position_size": 0.2,
                "max_drawdown": 0.05,
                "max_loss_per_trade": 0.02
            },
            "portfolio": {
                "max_exposure": 0.5,
                "max_correlation": 0.7,
                "max_concentration": 0.3
            },
            "market": {
                "max_volatility": 0.03,
                "max_spread": 0.01,
                "max_slippage": 0.005
            }
        }
    )
    
    logger.info(f"Registered strategy with ID: {strategy_id}")
    
    # Step 9: Generate sample data
    logger.info("Generating sample data...")
    sample_data = generate_sample_price_data(symbols, periods=500)
    
    # Step 10: Warm up the strategy
    logger.info("Warming up strategy...")
    for i in range(5):
        # Create a batch of data for warm-up
        warmup_batch = pd.concat([
            sample_data[symbol].iloc[i*10:(i+1)*10] 
            for symbol in symbols
        ], keys=symbols, names=['symbol'])
        
        # Process warm-up batch
        try:
            warm_up_complete = lifecycle_manager.warmup_strategy(strategy_id, warmup_batch)
            
            # Check status
            status = lifecycle_manager.get_strategy_status(strategy_id)
            logger.info(f"Warm-up progress: {status['warmup_progress']}, Status: {status['state']}")
            
            if warm_up_complete:
                logger.info("Strategy warm-up complete!")
                break
        except Exception as e:
            logger.error(f"Error during warm-up: {str(e)}")
            break
    
    # Step 11: Start the strategy
    try:
        lifecycle_manager.start_strategy(strategy_id)
        logger.info(f"Strategy {strategy_id} started")
    except Exception as e:
        logger.error(f"Error starting strategy: {str(e)}")
        return
    
    # Step 12: Process live data
    logger.info("Processing live data and executing signals...")
    execution_results = []
    
    for i in range(5, 50):  # Process 45 more batches of data
        # Create a batch of data
        batch_data = {
            symbol: sample_data[symbol].iloc[i*10:(i+1)*10]
            for symbol in symbols
        }
        
        # Process batch with strategy
        try:
            # Process data through strategy lifecycle manager
            strategy_result = lifecycle_manager.process_data(strategy_id, batch_data)
            
            # Get the strategy result from our strategy instance
            result = strategy.get_state()
            
            # Check if we have signals to execute
            if strategy_result and hasattr(strategy, 'execute'):
                # Get the full strategy result
                full_result = strategy.execute(strategy.generate_signals(strategy.process_data(batch_data)))
                
                # Execute signals through execution bridge
                if full_result and full_result.signals:
                    execution_result = execution_bridge.process_strategy_result(
                        strategy_id=strategy_id,
                        result=full_result
                    )
                    execution_results.append(execution_result)
                    
                    # Log execution result
                    orders_count = len(execution_result.get("orders", []))
                    if orders_count > 0:
                        logger.info(f"Executed {orders_count} orders for batch {i}")
                        
                        # Show order details
                        for order in execution_result.get("orders", []):
                            logger.info(f"  - {order.get('symbol', 'Unknown')}: {order.get('status', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error processing batch {i}: {str(e)}")
            continue
        
        # Check risk metrics periodically
        if i % 10 == 0:
            risk_metrics = lifecycle_manager.get_strategy_risk_metrics(strategy_id)
            logger.info(f"Risk metrics: violations={risk_metrics.get('violations_count', 0)}, warnings={risk_metrics.get('warnings_count', 0)}")
    
    # Step 13: Get execution analytics
    logger.info("Retrieving execution analytics...")
    analytics = execution_bridge.get_execution_analytics(strategy_id=strategy_id)
    
    if analytics:
        logger.info(f"Execution analytics: {analytics}")
    
    # Step 14: Stop the strategy and clean up
    lifecycle_manager.stop_strategy(strategy_id)
    logger.info(f"Strategy {strategy_id} stopped")
    
    # Step 15: Shut down the execution bridge
    execution_bridge.shutdown()
    logger.info("Execution bridge shut down")
    
    logger.info("Strategy execution integration example completed")


if __name__ == "__main__":
    main() 