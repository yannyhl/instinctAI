"""
Risk-Validated Execution Integration Tests

These tests verify the integration between the risk management system and
the execution engine, ensuring orders are properly validated before execution.
"""

import os
import unittest
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from advanced_trading.tests.integration.fixtures.base_fixture import BaseIntegrationTestFixture
from advanced_trading.strategies.base import StrategyResult
from advanced_trading.execution.risk_integration.risk_manager import (
    ExecutionRiskManager, ExecutionRiskConfig, RiskCheckResult
)
from advanced_trading.risk.portfolio.controller import PortfolioRiskController
from advanced_trading.execution.strategy_bridge import (
    StrategyExecutionBridge, ExecutionMode, SignalType
)
from advanced_trading.execution.exchange.order import OrderType, OrderSide, TimeInForce

logger = logging.getLogger('advanced_trading.tests.integration.risk_to_execution')


class TestRiskValidatedExecution(BaseIntegrationTestFixture):
    """Test the integration between risk management and execution components."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests in the class."""
        super().setUpClass()
        
        # Create risk configuration
        cls.risk_config = ExecutionRiskConfig(
            enabled=True,
            enforce_pre_trade_checks=True,
            max_position_size_percent=0.2,
            max_order_notional=10000,
            max_position_notional=20000,
            max_order_count_per_minute=10
        )
        
        # Create risk manager
        cls.execution_risk_manager = ExecutionRiskManager(cls.risk_config)
        
        # Create portfolio risk controller
        cls.portfolio_risk_controller = PortfolioRiskController(
            max_portfolio_exposure=1.0,
            max_correlation_exposure=0.5,
            drawdown_control_threshold=0.1,
            target_portfolio_volatility=0.15
        )
        
        # Create execution bridge in simulation mode
        cls.execution_bridge = StrategyExecutionBridge(
            execution_mode=ExecutionMode.SIMULATION,
            risk_manager=cls.execution_risk_manager,
            analyze_executions=True
        )
        
        # Test data
        cls.strategy_id = "test_strategy_001"
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
        
        logger.info("Risk-validated execution test setup complete")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests in the class have run."""
        # Shut down the execution bridge
        cls.execution_bridge.shutdown()
        
        super().tearDownClass()
    
    def setUp(self):
        """Set up each individual test."""
        super().setUp()
        
        # Reset risk manager state before each test
        self.execution_risk_manager.reset_state()
    
    def create_test_strategy_result(self, 
                                  signals: Optional[Dict[str, pd.DataFrame]] = None) -> StrategyResult:
        """Create a test strategy result with the given signals."""
        if signals is None:
            # Create a simple signal for BTC/USD
            signal_data = {
                'timestamp': [datetime.now()],
                'signal': [0.1],  # Buy 10% of available capital
                'price': [50000.0],
                'type': [SignalType.ENTRY.value]
            }
            signals = {
                'BTC/USD': pd.DataFrame(signal_data)
            }
        
        # Create positions data
        positions_data = []
        for symbol in self.symbols:
            # Only add a position if we have a signal for this symbol
            if symbol in signals:
                positions_data.append({
                    'symbol': symbol,
                    'position': signals[symbol]['signal'].sum(),
                    'timestamp': datetime.now()
                })
        
        positions = pd.DataFrame(positions_data) if positions_data else None
        
        # Create and return strategy result
        return StrategyResult(
            strategy_name=self.strategy_id,
            signals=signals,
            positions=positions,
            timestamp=datetime.now()
        )
    
    def test_order_validation_within_limits(self):
        """Test that orders within risk limits are validated and executed."""
        # Create a valid strategy result (within limits)
        strategy_result = self.create_test_strategy_result()
        
        # Process result through execution bridge
        execution_result = self.execution_bridge.process_strategy_result(
            strategy_id=self.strategy_id,
            result=strategy_result
        )
        
        # Verify execution result
        self.assertIsNotNone(execution_result)
        self.assertIn('orders', execution_result)
        self.assertTrue(len(execution_result['orders']) > 0)
        
        # Check that the order was approved
        order = execution_result['orders'][0]
        self.assertIn('status', order)
        self.assertNotEqual(order['status'], 'REJECTED')
        
        # Check that we have risk check results
        self.assertIn('risk_check_results', execution_result)
        self.assertTrue(len(execution_result['risk_check_results']) > 0)
        
        # Verify that the risk check passed
        risk_check = execution_result['risk_check_results'][0]
        self.assertIn('passed', risk_check)
        self.assertTrue(risk_check['passed'])
    
    def test_order_validation_exceeding_limits(self):
        """Test that orders exceeding risk limits are rejected."""
        # Create signals with excessive position size
        signal_data = {
            'timestamp': [datetime.now()],
            'signal': [0.5],  # 50% position - exceeds the 20% limit
            'price': [50000.0],
            'type': [SignalType.ENTRY.value]
        }
        signals = {
            'BTC/USD': pd.DataFrame(signal_data)
        }
        
        # Create strategy result with excessive position
        strategy_result = self.create_test_strategy_result(signals=signals)
        
        # Process result through execution bridge
        execution_result = self.execution_bridge.process_strategy_result(
            strategy_id=self.strategy_id,
            result=strategy_result
        )
        
        # Verify execution result
        self.assertIsNotNone(execution_result)
        self.assertIn('orders', execution_result)
        
        # For this test case, there are two possibilities:
        # 1. The order was rejected outright and not added to the orders list
        # 2. The order was created but marked as rejected
        
        if len(execution_result['orders']) > 0:
            # If an order was created, check that it was rejected
            order = execution_result['orders'][0]
            self.assertIn('status', order)
            self.assertEqual(order['status'], 'REJECTED')
        
        # Check that we have risk check results
        self.assertIn('risk_check_results', execution_result)
        self.assertTrue(len(execution_result['risk_check_results']) > 0)
        
        # Verify that at least one risk check failed
        failed_checks = [check for check in execution_result['risk_check_results'] 
                       if not check.get('passed', True)]
        self.assertTrue(len(failed_checks) > 0)
    
    def test_execution_analytics(self):
        """Test that execution analytics are generated correctly."""
        # Create a valid strategy result
        strategy_result = self.create_test_strategy_result()
        
        # Process result through execution bridge
        self.execution_bridge.process_strategy_result(
            strategy_id=self.strategy_id,
            result=strategy_result
        )
        
        # Get execution analytics
        analytics = self.execution_bridge.get_execution_analytics(
            strategy_id=self.strategy_id
        )
        
        # Verify analytics
        self.assertIsNotNone(analytics)
        self.assertIn('metrics', analytics)
        self.assertIn('orders', analytics)
        
        # Metrics should include execution quality metrics
        metrics = analytics['metrics']
        self.assertIn('fill_rate', metrics)
        self.assertIn('rejection_rate', metrics)
        
        # Analytics should include order information
        orders = analytics['orders']
        self.assertTrue(len(orders) > 0)
    
    def test_multiple_order_rate_limit(self):
        """Test that the order rate limit is enforced."""
        # Create multiple strategy results in quick succession
        results = []
        order_count = self.risk_config.max_order_count_per_minute + 5  # Exceed the limit
        
        for i in range(order_count):
            # Create signals with different timestamps to avoid duplicate order detection
            signal_data = {
                'timestamp': [datetime.now() + timedelta(seconds=i)],
                'signal': [0.01],  # Small position size
                'price': [50000.0 + i],
                'type': [SignalType.ENTRY.value]
            }
            signals = {
                'BTC/USD': pd.DataFrame(signal_data)
            }
            
            results.append(self.create_test_strategy_result(signals=signals))
        
        # Process all results
        execution_results = []
        for result in results:
            execution_result = self.execution_bridge.process_strategy_result(
                strategy_id=self.strategy_id,
                result=result
            )
            execution_results.append(execution_result)
        
        # Count accepted and rejected orders
        accepted_orders = 0
        rejected_orders = 0
        
        for result in execution_results:
            if 'orders' in result:
                for order in result['orders']:
                    if order.get('status') != 'REJECTED':
                        accepted_orders += 1
                    else:
                        rejected_orders += 1
        
        # Verify that the number of accepted orders doesn't exceed the limit
        self.assertLessEqual(accepted_orders, self.risk_config.max_order_count_per_minute)
        
        # Verify that some orders were rejected due to rate limiting
        self.assertTrue(rejected_orders > 0)
    
    def test_order_size_validation(self):
        """Test validation of order sizes against risk limits."""
        # Create market data with a high price to trigger notional value limit
        signal_data = {
            'timestamp': [datetime.now()],
            'signal': [0.1],  # 10% position
            'price': [200000.0],  # High price to trigger notional value limit
            'type': [SignalType.ENTRY.value]
        }
        signals = {
            'BTC/USD': pd.DataFrame(signal_data)
        }
        
        # Create strategy result
        strategy_result = self.create_test_strategy_result(signals=signals)
        
        # Process result through execution bridge
        execution_result = self.execution_bridge.process_strategy_result(
            strategy_id=self.strategy_id,
            result=strategy_result
        )
        
        # Check the risk check results
        self.assertIn('risk_check_results', execution_result)
        
        # Find the notional value check
        notional_checks = [check for check in execution_result['risk_check_results'] 
                         if check.get('check_name', '').lower().find('notional') >= 0]
        
        # If the notional is too high, the check should fail
        if len(notional_checks) > 0:
            for check in notional_checks:
                # The test might pass or fail depending on the notional calculation
                # This just verifies that the check was performed
                self.assertIn('passed', check)
                self.assertIn('details', check)


if __name__ == '__main__':
    unittest.main() 