#!/usr/bin/env python3
"""
Test suite for the Adaptive Meta-Strategy.
"""

import os
import sys
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path to allow imports
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(script_dir))

# Use patch to mock the module
with patch('advanced_trading.utils.bayesian_changepoint.BayesianChangepointDetector'), \
     patch('advanced_trading.utils.bayesian_changepoint.detect_market_regimes'):
    
    # Import the strategy after patching
    from advanced_trading.strategies.adaptive_meta_strategy import AdaptiveMetaStrategy, create_adaptive_meta_strategy
    from advanced_trading.utils.bayesian_changepoint import BayesianChangepointDetector
    from advanced_trading.utils.portfolio_allocation import PortfolioAllocator

class MockStrategy:
    """Mock strategy class for testing."""
    
    def __init__(self, name, signal_value=0.5):
        self.name = name
        self.signal_value = signal_value
        self.positions = {}
    
    def generate_signal(self, market_data):
        """Return a fixed signal value."""
        return self.signal_value
    
    def get_positions(self, market_data):
        """Return positions based on the signal value."""
        return {symbol: self.signal_value for symbol in market_data}

class TestAdaptiveMetaStrategy(unittest.TestCase):
    """Test the AdaptiveMetaStrategy class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test strategies
        self.strategies = {
            "trend_following": MockStrategy("trend_following", 0.8),
            "mean_reversion": MockStrategy("mean_reversion", -0.5),
            "ml_ensemble": MockStrategy("ml_ensemble", 0.3)
        }
        
        # Create test market data
        self.market_data = self._create_test_market_data()
        
        # Create mock for BayesianChangepointDetector and detect_market_regimes
        self.mock_detector = MagicMock()
        self.mock_detector.update.return_value = None
        
        # Create strategy instance
        self.meta_strategy = AdaptiveMetaStrategy(
            strategies=self.strategies,
            regime_detector=self.mock_detector,
            lookback_window=30,
            regime_memory=60,
            allocation_method='hrp',
            max_allocation=0.5,
            min_allocation=0.0,
            target_volatility=0.15,
            adaptation_speed=0.2
        )
        
        # Mock _update_regime_detection method to prevent issues
        self.original_update_regime = self.meta_strategy._update_regime_detection
        self.meta_strategy._update_regime_detection = MagicMock()
        self.meta_strategy._update_regime_detection.return_value = None
        self.meta_strategy.current_regime = "Bull-Stable"  # Default regime
    
    def tearDown(self):
        """Clean up after tests."""
        # Restore original method
        if hasattr(self, 'original_update_regime'):
            self.meta_strategy._update_regime_detection = self.original_update_regime
    
    def _create_test_market_data(self):
        """Create test market data with price and returns."""
        # Create date range
        today = datetime.now().date()
        dates = [today - timedelta(days=i) for i in range(100)]
        dates.reverse()  # Oldest to newest
        
        # Create test data for BTC and ETH
        btc_data = pd.DataFrame({
            'open': np.linspace(40000, 50000, len(dates)) + np.random.normal(0, 1000, len(dates)),
            'high': np.linspace(40000, 50000, len(dates)) + np.random.normal(0, 1500, len(dates)),
            'low': np.linspace(40000, 50000, len(dates)) + np.random.normal(0, 900, len(dates)),
            'close': np.linspace(40000, 50000, len(dates)) + np.random.normal(0, 1200, len(dates)),
            'volume': np.random.uniform(1000, 5000, len(dates))
        }, index=dates)
        
        eth_data = pd.DataFrame({
            'open': np.linspace(2800, 3500, len(dates)) + np.random.normal(0, 100, len(dates)),
            'high': np.linspace(2800, 3500, len(dates)) + np.random.normal(0, 150, len(dates)),
            'low': np.linspace(2800, 3500, len(dates)) + np.random.normal(0, 90, len(dates)),
            'close': np.linspace(2800, 3500, len(dates)) + np.random.normal(0, 120, len(dates)),
            'volume': np.random.uniform(10000, 50000, len(dates))
        }, index=dates)
        
        # Add returns
        btc_data['returns'] = btc_data['close'].pct_change()
        eth_data['returns'] = eth_data['close'].pct_change()
        
        # Create market data dictionary
        market_data = {
            'BTC/USDT': btc_data,
            'ETH/USDT': eth_data
        }
        
        return market_data
    
    def test_initialization(self):
        """Test strategy initialization."""
        # Check strategies are stored
        self.assertEqual(len(self.meta_strategy.strategies), 3)
        self.assertIn("trend_following", self.meta_strategy.strategies)
        self.assertIn("mean_reversion", self.meta_strategy.strategies)
        self.assertIn("ml_ensemble", self.meta_strategy.strategies)
        
        # Check default allocations
        self.assertEqual(len(self.meta_strategy.current_allocations), 3)
        for name, alloc in self.meta_strategy.current_allocations.items():
            self.assertAlmostEqual(alloc, 1/3, places=5)
    
    def test_update_with_market_data(self):
        """Test updating the strategy with market data."""
        # Get a subset of market data
        test_data = {symbol: df.iloc[:50] for symbol, df in self.market_data.items()}
        
        # Update the strategy
        positions = self.meta_strategy.update(test_data)
        
        # Check positions were returned
        self.assertIsInstance(positions, dict)
        self.assertEqual(len(positions), 2)  # Two symbols
        self.assertIn('BTC/USDT', positions)
        self.assertIn('ETH/USDT', positions)
        
        # Check performance tracking was initialized
        self.assertTrue(self.meta_strategy.is_initialized)
        
        # Update again to collect performance data
        test_data2 = {symbol: df.iloc[:60] for symbol, df in self.market_data.items()}
        positions2 = self.meta_strategy.update(test_data2)
        
        # Check performance history is being built
        self.assertGreater(len(self.meta_strategy.performance_history), 0)
    
    def test_regime_detection(self):
        """Test regime detection."""
        # Restore original method for this test
        self.meta_strategy._update_regime_detection = self.original_update_regime
        
        # Mock the detect_market_regimes function
        with patch('advanced_trading.strategies.adaptive_meta_strategy.detect_market_regimes') as mock_detect:
            # Set up mock return value
            mock_detect.return_value = {
                'segments': [
                    {'regime': 'Bull-Stable', 'start_idx': 0, 'end_idx': 30}
                ]
            }
            
            # Get a subset of market data
            test_data = {symbol: df.iloc[:50] for symbol, df in self.market_data.items()}
            
            # Force recalculation of regimes
            self.meta_strategy.regime_history = [{'date': datetime.now(), 'regime': 'Unknown'}] * 20
            
            # Manually call just the regime detection method
            self.meta_strategy._update_regime_detection(test_data)
            
            # Check if the regime was updated
            self.assertEqual(self.meta_strategy.current_regime, 'Bull-Stable')
    
    def test_strategy_allocations(self):
        """Test strategy allocation updates."""
        # Initialize with specific base allocations
        base_allocations = {
            "trend_following": 0.4,
            "mean_reversion": 0.3,
            "ml_ensemble": 0.3
        }
        
        meta_strategy = AdaptiveMetaStrategy(
            strategies=self.strategies,
            base_allocations=base_allocations,
            adaptation_speed=0.5  # Fast adaptation for testing
        )
        
        # Replace the regime detection method to avoid issues
        meta_strategy._update_regime_detection = MagicMock()
        meta_strategy._update_regime_detection.return_value = None
        
        # Check initial allocations
        for name, expected in base_allocations.items():
            self.assertAlmostEqual(meta_strategy.current_allocations[name], expected, places=5)
        
        # Set up performance data for each strategy
        # Create mock performance data by regime
        meta_strategy.performance_by_regime = {
            'Bull-Stable': {
                'trend_following': {'sharpe_ratio': 2.0},
                'mean_reversion': {'sharpe_ratio': 0.5},
                'ml_ensemble': {'sharpe_ratio': 1.5}
            }
        }
        
        # Set current regime
        meta_strategy.current_regime = 'Bull-Stable'
        
        # Update allocations
        meta_strategy._update_strategy_allocations()
        
        # Check allocations were updated
        # Trend following should have higher allocation now due to higher Sharpe
        self.assertGreater(meta_strategy.current_allocations['trend_following'], 
                          meta_strategy.current_allocations['mean_reversion'])
        
        # Sum of allocations should be 1.0
        total_allocation = sum(meta_strategy.current_allocations.values())
        self.assertAlmostEqual(total_allocation, 1.0, places=5)
    
    def test_risk_adjustment(self):
        """Test position risk adjustment."""
        # Create mock positions
        positions = {
            'BTC/USDT': 0.8,
            'ETH/USDT': 0.6
        }
        
        # Set bear market regime to test risk reduction
        self.meta_strategy.current_regime = 'Bear-Volatile'
        
        # Adjust positions
        adjusted = self.meta_strategy._adjust_positions_for_risk(positions, self.market_data)
        
        # Check that positions were reduced (Bear-Volatile should reduce exposure)
        for symbol, pos in positions.items():
            self.assertLess(adjusted[symbol], pos)
    
    def test_portfolio_volatility_estimation(self):
        """Test portfolio volatility estimation."""
        # Create test positions
        positions = {
            'BTC/USDT': 0.7,
            'ETH/USDT': 0.3
        }
        
        # Estimate volatility
        volatility = self.meta_strategy._estimate_portfolio_volatility(positions, self.market_data)
        
        # Volatility should be a positive number
        self.assertGreater(volatility, 0)
    
    def test_save_and_load(self):
        """Test saving and loading strategy state."""
        # Create a temporary directory for the test
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            # Update the strategy with some data
            test_data = {symbol: df.iloc[:50] for symbol, df in self.market_data.items()}
            self.meta_strategy.update(test_data)
            
            # Save state
            save_path = os.path.join(temp_dir, "test_state.json")
            success = self.meta_strategy.save(save_path)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(save_path))
            
            # Create a new strategy instance
            new_strategy = AdaptiveMetaStrategy(
                strategies=self.strategies
            )
            
            # Replace regime detection in the new strategy
            new_strategy._update_regime_detection = MagicMock()
            
            # Load state
            success = new_strategy.load(save_path)
            self.assertTrue(success)
            
            # Check that state was loaded correctly
            self.assertEqual(self.meta_strategy.current_regime, new_strategy.current_regime)
            self.assertEqual(len(self.meta_strategy.regime_history), len(new_strategy.regime_history))
            
            # Compare allocations
            for name, alloc in self.meta_strategy.current_allocations.items():
                self.assertAlmostEqual(alloc, new_strategy.current_allocations[name], places=5)
    
    def test_utility_create_function(self):
        """Test the utility function to create a meta-strategy."""
        # Mock the class to avoid issues
        with patch('advanced_trading.strategies.adaptive_meta_strategy.AdaptiveMetaStrategy') as MockAdaptiveMetaStrategy:
            # Set up base allocations
            base_allocations = {
                "trend_following": 0.4,
                "mean_reversion": 0.3,
                "ml_ensemble": 0.3
            }
            
            # Setup mock instance
            mock_instance = MagicMock()
            MockAdaptiveMetaStrategy.return_value = mock_instance
            
            # Create meta-strategy using utility function
            create_adaptive_meta_strategy(
                strategies=self.strategies,
                base_allocations=base_allocations,
                target_volatility=0.12,
                allocation_method='risk_parity',
                max_allocation=0.4
            )
            
            # Check that the constructor was called with correct parameters
            MockAdaptiveMetaStrategy.assert_called_once()
            args, kwargs = MockAdaptiveMetaStrategy.call_args
            
            # Check parameters
            self.assertEqual(kwargs['strategies'], self.strategies)
            self.assertEqual(kwargs['base_allocations'], base_allocations)
            self.assertEqual(kwargs['target_volatility'], 0.12)
            self.assertEqual(kwargs['allocation_method'], 'risk_parity')
            self.assertEqual(kwargs['max_allocation'], 0.4)
    
    def test_performance_summary(self):
        """Test getting performance summary."""
        # Update the strategy with some data
        test_data = {symbol: df.iloc[:50] for symbol, df in self.market_data.items()}
        self.meta_strategy.update(test_data)
        
        # We need a second update to generate performance data
        test_data2 = {symbol: df.iloc[:60] for symbol, df in self.market_data.items()}
        self.meta_strategy.update(test_data2)
        
        # Mock some performance metrics
        self.meta_strategy.performance_by_regime = {
            'Bull-Stable': {
                'Meta-Strategy': {
                    'sharpe_ratio': 1.5,
                    'annual_return': 0.2,
                    'max_drawdown': -0.1,
                    'win_rate': 0.6
                }
            }
        }
        
        # Get performance summary
        summary = self.meta_strategy.get_performance_summary()
        
        # Should be an error message if not enough data
        if len(self.meta_strategy.performance_history) < 5:
            self.assertIn('error', summary)
        else:
            # Check current allocations
            self.assertIn('current_allocations', summary)
            self.assertEqual(len(summary['current_allocations']), 3)
            
            # Check current regime
            self.assertIn('current_regime', summary)

if __name__ == '__main__':
    unittest.main() 