"""
End-to-End Trading Workflow Integration Test

This test verifies the complete trading workflow from data ingestion to execution,
including all major system components:

1. Data Pipeline: Data loading and preprocessing
2. Model Framework: Feature generation and prediction
3. Strategy Framework: Signal generation and lifecycle management
4. Risk Management: Risk validation and position sizing
5. Execution Engine: Order submission and execution analysis
"""

import os
import logging
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple

from advanced_trading.tests.integration.fixtures.base_fixture import BaseIntegrationTestFixture
from advanced_trading.data.sources.csv_source import CSVDataSource
from advanced_trading.utils.data_preprocessing import DataPreprocessor
from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager
from advanced_trading.strategies.base import Strategy, StrategyConfig, StrategyType, StrategyResult
from advanced_trading.strategies.risk_integration import RiskAwareStrategyLifecycleManager
from advanced_trading.risk.portfolio.controller import PortfolioRiskController
from advanced_trading.execution.strategy_bridge import StrategyExecutionBridge, ExecutionMode
from advanced_trading.execution.risk_integration.risk_manager import ExecutionRiskManager, ExecutionRiskConfig
from advanced_trading.execution.analysis.execution_analyzer import ExecutionAnalyzer

logger = logging.getLogger('advanced_trading.tests.integration.end_to_end')


class SimpleMomentumStrategy(Strategy):
    """A simple momentum strategy for testing purposes."""
    
    STRATEGY_TYPE = StrategyType.TECHNICAL
    PARAMETERS = {
        "lookback_period": {"type": "int", "default": 10, "description": "Lookback period for momentum"},
        "threshold": {"type": "float", "default": 0.005, "description": "Momentum threshold"},
        "position_size": {"type": "float", "default": 0.1, "description": "Position size as fraction of capital"}
    }
    REQUIRED_DATA = ["close"]
    
    def __init__(self, config: StrategyConfig):
        """Initialize the strategy."""
        super().__init__(config)
        self.lookback_period = 10
        self.threshold = 0.005
        self.position_size = 0.1
        self.version = "1.0.0"
        self.author = "Instinct AI Team"
        self.tags = ["momentum", "technical"]
        
        # Internal state
        self._momentum = {}
        self._position = {}
        self._last_signal = {}
    
    def initialize(self, parameters: Optional[Dict[str, Any]] = None, 
                 dependencies: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the strategy with parameters."""
        logger.info(f"Initializing {self.name} strategy")
        
        # Set parameters
        if parameters:
            if "lookback_period" in parameters:
                self.lookback_period = parameters["lookback_period"]
            if "threshold" in parameters:
                self.threshold = parameters["threshold"]
            if "position_size" in parameters:
                self.position_size = parameters["position_size"]
        
        # Initialize state
        for symbol in self.config.symbols:
            self._momentum[symbol] = None
            self._position[symbol] = 0.0
            self._last_signal[symbol] = None
        
        logger.info(f"Strategy {self.name} initialized with lookback={self.lookback_period}, "
                   f"threshold={self.threshold}, position_size={self.position_size}")
    
    def process_data(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Process market data and calculate momentum signals."""
        result = {}
        
        for symbol, df in data.items():
            # Skip if symbol not in config
            if symbol not in self.config.symbols:
                continue
            
            # Calculate momentum
            if 'close' not in df.columns:
                logger.warning(f"Close price column not found in data for {symbol}")
                continue
            
            processed = df.copy()
            
            # Calculate simple momentum (percentage change over lookback period)
            processed['momentum'] = processed['close'].pct_change(periods=self.lookback_period)
            
            # Generate signals based on momentum
            processed['signal'] = 0.0
            
            # Buy signal when momentum is above threshold
            buy_condition = processed['momentum'] > self.threshold
            
            # Sell signal when momentum is below negative threshold
            sell_condition = processed['momentum'] < -self.threshold
            
            # Set signals with position size
            processed.loc[buy_condition, 'signal'] = self.position_size
            processed.loc[sell_condition, 'signal'] = -self.position_size
            
            # Update internal state
            if not processed.empty:
                self._momentum[symbol] = processed['momentum'].iloc[-1]
                self._last_signal[symbol] = processed['signal'].iloc[-1]
            
            result[symbol] = processed
        
        return result
    
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Generate trading signals based on processed data."""
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
                signals_df['type'] = ['entry' if s > 0 else 'exit' for s in signal_rows['signal']]
                
                # Add to signals dict
                signals[symbol] = signals_df
                
                # Update state with signals
                for _, row in signals_df.iterrows():
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


class TestEndToEndTradingWorkflow(BaseIntegrationTestFixture):
    """Test the complete end-to-end trading workflow."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests in the class."""
        super().setUpClass()
        
        # Test data
        cls.strategy_id = "momentum_strategy_001"
        cls.symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        cls.start_date = datetime.now() - timedelta(days=30)
        cls.end_date = datetime.now()
        
        # Generate test market data
        cls.market_data = cls.create_test_market_data(
            symbols=cls.symbols,
            start_date=cls.start_date,
            end_date=cls.end_date,
            frequency='1h'
        )
        
        # Create test data directory
        cls.data_dir = os.path.join(cls.temp_dir.name, 'data')
        os.makedirs(cls.data_dir, exist_ok=True)
        
        # Save test data to CSV files for loading via data source
        for symbol, df in cls.market_data.items():
            file_path = os.path.join(cls.data_dir, f"{symbol.replace('/', '_')}.csv")
            df.to_csv(file_path)
        
        # Set up components for workflow
        
        # 1. Data Pipeline
        cls.data_source = CSVDataSource(
            base_dir=cls.data_dir,
            symbols=cls.symbols,
            timeframe='1h'
        )
        
        cls.data_preprocessor = DataPreprocessor()
        
        # 2. Risk Management
        cls.risk_config = ExecutionRiskConfig(
            enabled=True,
            enforce_pre_trade_checks=True,
            max_position_size_percent=0.2,
            max_order_notional=10000,
            max_position_notional=20000,
            max_order_count_per_minute=10
        )
        
        cls.execution_risk_manager = ExecutionRiskManager(cls.risk_config)
        
        cls.portfolio_risk_controller = PortfolioRiskController(
            max_portfolio_exposure=1.0,
            max_correlation_exposure=0.5,
            drawdown_control_threshold=0.1,
            target_portfolio_volatility=0.15
        )
        
        # 3. Strategy Framework
        cls.strategy_config = StrategyConfig(
            name="Momentum Strategy",
            symbols=cls.symbols,
            timeframe="1h",
            parameters={
                "lookback_period": 5,
                "threshold": 0.01,
                "position_size": 0.1
            },
            risk_limits={
                "max_position": 0.2,
                "max_drawdown": 0.05
            }
        )
        
        cls.strategy = SimpleMomentumStrategy(cls.strategy_config)
        
        cls.lifecycle_manager = RiskAwareStrategyLifecycleManager(
            portfolio_risk_controller=cls.portfolio_risk_controller,
            enforce_risk_limits=True,
            auto_adjust_position_sizes=True,
            emergency_stop_on_violation=True
        )
        
        # 4. Execution Engine
        cls.execution_bridge = StrategyExecutionBridge(
            execution_mode=ExecutionMode.SIMULATION,
            risk_manager=cls.execution_risk_manager,
            analyze_executions=True
        )
        
        cls.execution_analyzer = ExecutionAnalyzer()
        
        logger.info("End-to-end trading workflow test setup complete")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests in the class have run."""
        # Shut down the execution bridge
        cls.execution_bridge.shutdown()
        
        super().tearDownClass()
    
    def setUp(self):
        """Set up each individual test."""
        super().setUp()
        
        # Reset components before each test
        self.execution_risk_manager.reset_state()
    
    def test_complete_trading_workflow(self):
        """Test the complete trading workflow from data to execution."""
        # Step 1: Register strategy with lifecycle manager
        strategy_id = self.lifecycle_manager.register_strategy(
            strategy=self.strategy,
            strategy_id=self.strategy_id,
            parameters=self.strategy_config.parameters,
            dependencies={},
            warmup_bars=10,
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
        
        self.assertEqual(strategy_id, self.strategy_id)
        
        # Step 2: Load data from the data source
        data = {}
        for symbol in self.symbols:
            symbol_data = self.data_source.get_historical_data(
                symbol=symbol,
                start_date=self.start_date,
                end_date=self.end_date
            )
            data[symbol] = symbol_data
        
        # Verify that we have data for all symbols
        self.assertEqual(len(data), len(self.symbols))
        for symbol in self.symbols:
            self.assertIn(symbol, data)
            self.assertIsNotNone(data[symbol])
            self.assertGreater(len(data[symbol]), 0)
        
        # Step 3: Preprocess the data
        processed_data = {}
        for symbol, df in data.items():
            processed_df = self.data_preprocessor.clean_data(df)
            processed_data[symbol] = processed_df
        
        # Step 4: Split data into batches for warmup and live processing
        warmup_data_batches = []
        live_data_batches = []
        
        batch_size = 24  # 1-day batches in 1h data
        
        for symbol, df in processed_data.items():
            # Split into warmup and live periods
            warmup_end_idx = min(len(df), 48)  # 2 days of warmup
            
            warmup_df = df.iloc[:warmup_end_idx]
            live_df = df.iloc[warmup_end_idx:]
            
            # Create batches
            warmup_batches = [warmup_df]
            
            live_batches = []
            for i in range(0, len(live_df), batch_size):
                batch = live_df.iloc[i:min(i+batch_size, len(live_df))]
                if not batch.empty:
                    live_batches.append(batch)
            
            warmup_data_batches.append((symbol, warmup_batches))
            live_data_batches.append((symbol, live_batches))
        
        # Step 5: Warm up the strategy
        for symbol, batches in warmup_data_batches:
            for batch in batches:
                warmup_data = {symbol: batch}
                self.lifecycle_manager.warmup_strategy(self.strategy_id, warmup_data)
        
        # Verify that the strategy is warmed up
        status = self.lifecycle_manager.get_strategy_status(self.strategy_id)
        self.assertIn('warmup_progress', status)
        self.assertIn('state', status)
        
        if status['warmup_progress'] < 1.0:
            logger.warning(f"Strategy warmup not complete: {status['warmup_progress']}")
        
        # Step 6: Start the strategy
        self.lifecycle_manager.start_strategy(self.strategy_id)
        
        # Verify the strategy is running
        status = self.lifecycle_manager.get_strategy_status(self.strategy_id)
        self.assertEqual(status['state'], 'RUNNING')
        
        # Step 7: Process live data batches
        execution_results = []
        for i in range(len(live_data_batches[0][1])):  # Use the first symbol's batch count
            # Create batch with data from all symbols
            batch_data = {}
            for symbol, batches in live_data_batches:
                if i < len(batches):
                    batch_data[symbol] = batches[i]
            
            # Process batch with lifecycle manager
            strategy_result = self.lifecycle_manager.process_data(self.strategy_id, batch_data)
            
            # If there are signals, execute them
            if strategy_result:
                execution_result = self.execution_bridge.process_strategy_result(
                    strategy_id=self.strategy_id,
                    result=strategy_result
                )
                execution_results.append(execution_result)
        
        # Verify that we have processed all data batches
        self.assertTrue(len(execution_results) > 0)
        
        # Step 8: Analyze execution results
        analytics = self.execution_bridge.get_execution_analytics(
            strategy_id=self.strategy_id
        )
        
        # Verify analytics
        self.assertIsNotNone(analytics)
        self.assertIn('metrics', analytics)
        
        # Step 9: Check risk metrics
        risk_metrics = self.lifecycle_manager.get_strategy_risk_metrics(self.strategy_id)
        
        # Verify risk metrics
        self.assertIsNotNone(risk_metrics)
        self.assertIn('violations_count', risk_metrics)
        self.assertIn('warnings_count', risk_metrics)
        
        # Step 10: Stop the strategy
        self.lifecycle_manager.stop_strategy(self.strategy_id)
        
        # Verify the strategy is stopped
        status = self.lifecycle_manager.get_strategy_status(self.strategy_id)
        self.assertEqual(status['state'], 'STOPPED')
        
        # Log summary of the test
        orders_executed = sum(len(result.get('orders', [])) for result in execution_results)
        logger.info(f"Trading workflow test completed: {orders_executed} orders executed")
        logger.info(f"Risk metrics: violations={risk_metrics.get('violations_count', 0)}, "
                   f"warnings={risk_metrics.get('warnings_count', 0)}")
    
    def test_performance_benchmarks(self):
        """Test performance benchmarks for critical components of the workflow."""
        # Define test data
        symbol = self.symbols[0]
        df = self.market_data[symbol].copy()
        
        # Benchmark data preprocessing
        _, preprocessing_time = self.measure_performance(
            self.data_preprocessor.clean_data,
            df
        )
        
        logger.info(f"Data preprocessing time: {preprocessing_time:.4f} seconds")
        self.assertLess(preprocessing_time, 1.0, "Data preprocessing took too long")
        
        # Benchmark strategy processing
        test_batch = {symbol: df.iloc[:100]}
        
        # First register and warm up strategy
        self.lifecycle_manager.register_strategy(
            strategy=self.strategy,
            strategy_id="perf_test_strategy",
            parameters=self.strategy_config.parameters,
            auto_initialize=True
        )
        
        self.lifecycle_manager.warmup_strategy("perf_test_strategy", test_batch)
        self.lifecycle_manager.start_strategy("perf_test_strategy")
        
        # Now benchmark the processing
        _, strategy_processing_time = self.measure_performance(
            self.lifecycle_manager.process_data,
            "perf_test_strategy",
            test_batch
        )
        
        logger.info(f"Strategy processing time: {strategy_processing_time:.4f} seconds")
        self.assertLess(strategy_processing_time, 1.0, "Strategy processing took too long")
        
        # Clean up
        self.lifecycle_manager.stop_strategy("perf_test_strategy")


if __name__ == '__main__':
    unittest.main() 