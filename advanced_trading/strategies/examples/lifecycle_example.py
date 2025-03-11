"""
Strategy Lifecycle Management Example

This example demonstrates how to use the strategy lifecycle management system to:
1. Register strategies with the registry
2. Discover strategies in the codebase
3. Initialize strategies with parameters
4. Manage the lifecycle of strategies (warm-up, start, pause, stop)
5. Process data through strategies
6. Save and load strategy state

This serves as a comprehensive example of how to use the strategy lifecycle management
system in the Instinct AI trading platform.
"""

import os
import time
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union

from advanced_trading.strategies.base import Strategy, StrategyConfig, StrategyType, StrategyResult
from advanced_trading.strategies.lifecycle import StrategyLifecycleManager
from advanced_trading.strategies.factory.strategy_registry import strategy_registry, StrategyMetadata

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ExampleStrategy(Strategy):
    """
    A simple example strategy for demonstration purposes.
    
    This strategy calculates a simple moving average crossover and generates
    buy signals when the fast MA crosses above the slow MA, and sell signals
    when the fast MA crosses below the slow MA.
    """
    
    # Strategy metadata
    STRATEGY_TYPE = StrategyType.TECHNICAL
    PARAMETERS = {
        "fast_ma_period": {"type": "int", "default": 10, "description": "Fast moving average period"},
        "slow_ma_period": {"type": "int", "default": 30, "description": "Slow moving average period"},
        "signal_threshold": {"type": "float", "default": 0.0, "description": "Signal threshold"}
    }
    REQUIRED_DATA = ["close"]
    
    def __init__(self, config: StrategyConfig):
        """Initialize the strategy."""
        super().__init__(config)
        self.fast_ma_period = 10
        self.slow_ma_period = 30
        self.signal_threshold = 0.0
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
            if "signal_threshold" in parameters:
                self.signal_threshold = parameters["signal_threshold"]
        
        # Initialize state
        for symbol in self.config.symbols:
            self._fast_ma[symbol] = None
            self._slow_ma[symbol] = None
            self._position[symbol] = 0.0
            self._last_signal[symbol] = None
        
        logger.info(f"Strategy {self.name} initialized with fast_ma={self.fast_ma_period}, " 
                   f"slow_ma={self.slow_ma_period}, threshold={self.signal_threshold}")
    
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
                
            # Calculate fast and slow moving averages
            if 'close' not in df.columns:
                logger.warning(f"Close price column not found in data for {symbol}")
                continue
                
            processed = df.copy()
            processed['fast_ma'] = processed['close'].rolling(window=self.fast_ma_period).mean()
            processed['slow_ma'] = processed['close'].rolling(window=self.slow_ma_period).mean()
            
            # Calculate signal
            processed['signal'] = np.where(
                processed['fast_ma'] > processed['slow_ma'] + self.signal_threshold, 1,
                np.where(processed['fast_ma'] < processed['slow_ma'] - self.signal_threshold, -1, 0)
            )
            
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
            signals_df = pd.DataFrame()
            signals_df['timestamp'] = df.index
            signals_df['signal'] = df['signal']
            signals_df['price'] = df['close']
            
            # Only include rows with non-zero signals
            signals_df = signals_df[signals_df['signal'] != 0]
            
            signals[symbol] = signals_df
            
            # Update state with signals
            for _, row in signals_df.iterrows():
                self.state.add_signal(symbol, {
                    'timestamp': row['timestamp'],
                    'signal': row['signal'],
                    'price': row['price']
                })
        
        return signals
    
    def execute(self, signals: Dict[str, pd.DataFrame]) -> StrategyResult:
        """Execute trading signals."""
        pnl = 0.0
        positions = {}
        trades = []
        
        for symbol, df in signals.items():
            if df.empty:
                continue
                
            for _, row in df.iterrows():
                old_position = self._position.get(symbol, 0.0)
                
                # Update position based on signal
                if row['signal'] > 0:  # Buy signal
                    new_position = 1.0
                elif row['signal'] < 0:  # Sell signal
                    new_position = -1.0
                else:
                    new_position = old_position
                
                # Record position change if any
                if new_position != old_position:
                    trades.append({
                        'timestamp': row['timestamp'],
                        'symbol': symbol,
                        'action': 'buy' if new_position > old_position else 'sell',
                        'price': row['price'],
                        'quantity': abs(new_position - old_position),
                        'position': new_position
                    })
                    
                    # Update position
                    self._position[symbol] = new_position
                    
                    # Update state with position
                    self.state.update_position(symbol, {
                        'timestamp': row['timestamp'],
                        'position': new_position,
                        'price': row['price']
                    })
            
            positions[symbol] = self._position[symbol]
        
        # Create result
        result = StrategyResult(
            strategy_name=self.name,
            signals={s: df for s, df in signals.items() if not df.empty},
            positions=pd.DataFrame([
                {'symbol': s, 'position': p, 'timestamp': pd.Timestamp.now()}
                for s, p in positions.items()
            ]) if positions else None,
            pnl=pnl,
            trades=pd.DataFrame(trades) if trades else None,
            timestamp=pd.Timestamp.now()
        )
        
        return result


def generate_sample_data(symbols, periods=100):
    """Generate sample OHLCV data for testing."""
    data = {}
    for symbol in symbols:
        # Start with a random price
        start_price = np.random.uniform(100, 1000)
        
        # Generate random price movement
        returns = np.random.normal(0, 0.01, periods)
        # Add a trend
        returns += np.linspace(0, 0.001, periods)
        
        # Calculate prices
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
        df.index = pd.date_range(start='2023-01-01', periods=periods, freq='H')
        
        data[symbol] = df
    
    return data


def main():
    """Run the lifecycle management example."""
    # Create strategy lifecycle manager
    lifecycle_manager = StrategyLifecycleManager()
    
    # Register example strategy with the registry
    strategy_registry.register_strategy(
        ExampleStrategy,
        StrategyMetadata(
            name="ExampleStrategy",
            description="A simple moving average crossover strategy",
            strategy_type=StrategyType.TECHNICAL,
            parameters=ExampleStrategy.PARAMETERS,
            required_data=ExampleStrategy.REQUIRED_DATA,
            version="1.0.0",
            author="Instinct AI Team",
            tags=["technical", "moving_average", "example"]
        )
    )
    
    # List available strategies
    available_strategies = strategy_registry.list_strategies()
    logger.info(f"Available strategies: {available_strategies}")
    
    # Create strategy configuration
    symbols = ["BTC/USD", "ETH/USD"]
    config = StrategyConfig(
        name="MA Crossover Example",
        symbols=symbols,
        timeframe="1h",
        parameters={
            "fast_ma_period": 5,
            "slow_ma_period": 20,
            "signal_threshold": 0.001
        },
        risk_limits={
            "max_position": 1.0,
            "max_drawdown": 0.05
        }
    )
    
    # Create strategy instance
    strategy = strategy_registry.create_strategy("ExampleStrategy", config)
    
    # Register strategy with lifecycle manager
    strategy_id = lifecycle_manager.register_strategy(
        strategy=strategy,
        strategy_id="example_strategy_001",
        parameters=config.parameters,
        dependencies={},
        warmup_bars=50,
        auto_initialize=True
    )
    
    logger.info(f"Registered strategy with ID: {strategy_id}")
    
    # Generate sample data
    sample_data = generate_sample_data(symbols, periods=150)
    
    # Get strategy status
    status = lifecycle_manager.get_strategy_status(strategy_id)
    logger.info(f"Strategy status: {status}")
    
    # Warm up the strategy
    logger.info("Warming up strategy...")
    for i in range(5):
        # Create a batch of 10 bars
        batch_data = pd.concat([
            sample_data[symbol].iloc[i*10:(i+1)*10] 
            for symbol in symbols
        ], keys=symbols, names=['symbol'])
        
        # Process batch
        warm_up_complete = lifecycle_manager.warmup_strategy(strategy_id, batch_data)
        
        # Check status
        status = lifecycle_manager.get_strategy_status(strategy_id)
        logger.info(f"Warm-up progress: {status['warmup_progress']}, Status: {status['state']}")
        
        if warm_up_complete:
            logger.info("Warm-up complete!")
            break
    
    # Start the strategy
    logger.info("Starting strategy...")
    lifecycle_manager.start_strategy(strategy_id)
    
    # Process live data
    logger.info("Processing live data...")
    for i in range(5, 10):
        # Create a batch of data
        batch_data = {
            symbol: sample_data[symbol].iloc[i*10:(i+1)*10]
            for symbol in symbols
        }
        
        # Process data
        results = lifecycle_manager.process_data(strategy_id, batch_data)
        
        if i == 7:
            # Pause the strategy
            logger.info("Pausing strategy...")
            lifecycle_manager.pause_strategy(strategy_id)
            
            # Wait a moment
            time.sleep(1)
            
            # Resume the strategy
            logger.info("Resuming strategy...")
            lifecycle_manager.start_strategy(strategy_id)
    
    # Save strategy state
    state_file = lifecycle_manager.save_strategy_state(strategy_id)
    logger.info(f"Strategy state saved to: {state_file}")
    
    # Stop the strategy
    logger.info("Stopping strategy...")
    lifecycle_manager.stop_strategy(strategy_id)
    
    # Get final status
    all_statuses = lifecycle_manager.get_all_strategies_status()
    logger.info(f"All strategy statuses: {all_statuses}")
    
    logger.info("Example completed successfully!")


if __name__ == "__main__":
    main() 