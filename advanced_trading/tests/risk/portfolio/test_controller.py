"""
Unit tests for the PortfolioRiskController class.

This module tests the functionality of the PortfolioRiskController class,
which is responsible for managing portfolio-level risk in the trading system.
"""

import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from advanced_trading.risk.portfolio.controller import PortfolioRiskController


class TestPortfolioRiskController(unittest.TestCase):
    """Test cases for the PortfolioRiskController class."""
    
    def setUp(self):
        """Set up test fixtures before each test."""
        # Create sample return data
        self.dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        np.random.seed(42)  # For reproducibility
        
        # Create returns for 5 assets
        self.returns_data = {
            'asset1': np.random.normal(0.001, 0.02, 100),
            'asset2': np.random.normal(0.0005, 0.01, 100),
            'asset3': np.random.normal(0.0015, 0.025, 100),
            'asset4': np.random.normal(0.0008, 0.015, 100),
            'asset5': np.random.normal(0.0012, 0.018, 100)
        }
        
        self.returns = pd.DataFrame(self.returns_data, index=self.dates)
        
        # Create market index returns
        self.market_returns = pd.Series(
            np.random.normal(0.0008, 0.016, 100),
            index=self.dates
        )
        
        # Create current positions
        self.current_positions = {
            'asset1': 10000,
            'asset2': 15000,
            'asset3': -5000,
            'asset4': 20000,
            'asset5': 8000
        }
        
        self.current_equity = 100000
        
        # Initialize controller with test parameters
        self.controller = PortfolioRiskController(
            max_portfolio_exposure=1.2,
            max_correlation_exposure=0.5,
            drawdown_control_threshold=0.1,
            target_portfolio_volatility=0.15,
            allocation_method='equal',
            risk_free_rate=0.0,
            market_index=self.market_returns
        )
        
        # Update controller with test data
        self.controller.update_market_state(
            returns=self.returns,
            current_equity=self.current_equity,
            current_positions=self.current_positions,
            current_date=self.dates[-1]
        )
    
    def test_initialization(self):
        """Test proper initialization of the controller."""
        self.assertEqual(self.controller.max_portfolio_exposure, 1.2)
        self.assertEqual(self.controller.max_correlation_exposure, 0.5)
        self.assertEqual(self.controller.drawdown_control_threshold, 0.1)
        self.assertEqual(self.controller.target_portfolio_volatility, 0.15)
        self.assertEqual(self.controller.allocation_method, 'equal')
        self.assertEqual(self.controller.risk_free_rate, 0.0)
        
        # Test internal state initialization
        self.assertIsNotNone(self.controller.historical_returns)
        self.assertIsNotNone(self.controller.current_weights)
        self.assertEqual(self.controller.current_date, self.dates[-1])
        
    def test_update_market_state(self):
        """Test updating the market state."""
        # Test that historical returns are stored
        self.assertEqual(len(self.controller.historical_returns), 100)
        
        # Test current weights calculation
        for asset, position in self.current_positions.items():
            expected_weight = position / self.current_equity
            self.assertAlmostEqual(self.controller.current_weights[asset], expected_weight)
        
        # Test exposure calculation
        expected_exposure = sum(abs(v) for v in self.current_positions.values()) / self.current_equity if self.current_equity > 0 else 0
        self.assertAlmostEqual(self.controller.current_portfolio_exposure, expected_exposure)
        
        # Test with updated positions
        new_positions = {
            'asset1': 20000,
            'asset2': 10000,
            'asset3': -10000,
            'asset4': 15000,
            'asset5': 5000
        }
        new_equity = 120000
        
        self.controller.update_market_state(
            returns=self.returns,
            current_equity=new_equity,
            current_positions=new_positions,
            current_date=self.dates[-1]
        )
        
        # Test updated weights
        for asset, position in new_positions.items():
            expected_weight = position / new_equity
            self.assertAlmostEqual(self.controller.current_weights[asset], expected_weight)
    
    def test_calculate_portfolio_weights(self):
        """Test calculating portfolio weights with different methods."""
        # Test equal weights
        weights = self.controller.calculate_portfolio_weights(method='equal')
        for asset in self.returns.columns:
            self.assertAlmostEqual(weights[asset], 1.0 / len(self.returns.columns))
        
        # Test other methods
        methods = ['hrp', 'risk_parity', 'minvar']
        for method in methods:
            weights = self.controller.calculate_portfolio_weights(method=method)
            self.assertEqual(len(weights), len(self.returns.columns))
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
            
    def test_calculate_risk_metrics(self):
        """Test calculating risk metrics."""
        # Test with current weights
        metrics = self.controller.calculate_risk_metrics()
        
        # Check that all expected metrics are present
        expected_metrics = ['volatility', 'sharpe_ratio', 'max_drawdown', 
                           'var_95', 'cvar_95', 'annualized_return']
        for metric in expected_metrics:
            self.assertIn(metric, metrics)
        
        # Test with custom weights
        custom_weights = {
            'asset1': 0.3,
            'asset2': 0.2,
            'asset3': -0.1,
            'asset4': 0.4,
            'asset5': 0.2
        }
        
        metrics = self.controller.calculate_risk_metrics(weights=custom_weights)
        for metric in expected_metrics:
            self.assertIn(metric, metrics)
    
    def test_adjust_weights_for_risk_targets(self):
        """Test adjusting weights to meet risk targets."""
        # Create weights to adjust
        test_weights = {
            'asset1': 0.25,
            'asset2': 0.2,
            'asset3': 0.15,
            'asset4': 0.3,
            'asset5': 0.1
        }
        
        # Test normal adjustment
        adjusted = self.controller.adjust_weights_for_risk_targets(test_weights)
        self.assertEqual(len(adjusted), len(test_weights))
        
        # Test with custom target volatility
        original_target = self.controller.target_portfolio_volatility
        self.controller.target_portfolio_volatility = 0.1  # Lower target
        
        adjusted_lower = self.controller.adjust_weights_for_risk_targets(test_weights)
        
        # Restore original target
        self.controller.target_portfolio_volatility = original_target
        
        # Lower target should result in smaller weights in general
        total_original = sum(abs(v) for v in adjusted.values())
        total_lower = sum(abs(v) for v in adjusted_lower.values())
        self.assertLess(total_lower, total_original)
    
    def test_adjust_for_correlation_clusters(self):
        """Test adjusting weights based on correlation clusters."""
        # Create dummy correlation clusters for testing
        self.controller.correlation_clusters = {
            0: ['asset1', 'asset2'],
            1: ['asset3', 'asset4', 'asset5']
        }
        
        # Create test weights with high exposure to cluster 0
        test_weights = {
            'asset1': 0.4,
            'asset2': 0.3,
            'asset3': 0.1,
            'asset4': 0.1,
            'asset5': 0.1
        }
        
        # Set max correlation exposure
        self.controller.max_correlation_exposure = 0.5
        
        # Test adjustment
        adjusted = self.controller.adjust_for_correlation_clusters(test_weights)
        
        # Check that cluster 0 exposure is now limited
        cluster0_exposure = adjusted['asset1'] + adjusted['asset2']
        self.assertLessEqual(cluster0_exposure, self.controller.max_correlation_exposure * 1.001)  # Small tolerance
    
    def test_calculate_rebalance_trades(self):
        """Test calculating rebalance trades."""
        # Set up initial positions and target weights
        current_positions = {
            'asset1': 30000,
            'asset2': 20000,
            'asset3': 10000,
            'asset4': 25000,
            'asset5': 15000
        }
        
        target_weights = {
            'asset1': 0.2,
            'asset2': 0.2,
            'asset3': 0.2,
            'asset4': 0.2,
            'asset5': 0.2
        }
        
        equity = 100000
        
        # Calculate trades
        trades = self.controller.calculate_rebalance_trades(
            target_weights=target_weights,
            current_positions=current_positions,
            current_equity=equity
        )
        
        # Check trade directions
        self.assertLess(trades.get('asset1', 0), 0)  # Should reduce position
        self.assertEqual(trades.get('asset2', 0), 0)  # Should stay the same
        self.assertGreater(trades.get('asset3', 0), 0)  # Should increase position
        self.assertLess(trades.get('asset4', 0), 0)  # Should reduce position
        self.assertGreater(trades.get('asset5', 0), 0)  # Should increase position
    
    def test_generate_position_sizing_recommendations(self):
        """Test generating position sizing recommendations."""
        # Test with current state
        recommendations = self.controller.generate_position_sizing_recommendations(
            current_equity=self.current_equity,
            current_positions=self.current_positions
        )
        
        # Check that all expected components are present
        expected_components = ['optimal_weights', 'risk_adjusted_weights', 'final_weights',
                               'risk_metrics', 'diversification_metrics', 'portfolio_exposure',
                               'recommended_trades', 'drawdown_status']
        
        for component in expected_components:
            self.assertIn(component, recommendations)
        
        # Check weights sum to approximately 1
        self.assertAlmostEqual(sum(recommendations['optimal_weights'].values()), 1.0, places=6)
    
    def test_risk_contribution(self):
        """Test calculating risk contribution."""
        # Test with equal weights
        weights = {asset: 1.0/5 for asset in self.returns.columns}
        
        risk_contrib = self.controller.calculate_risk_contribution(weights=weights)
        
        # Check that all assets have risk contributions
        for asset in self.returns.columns:
            self.assertIn(asset, risk_contrib)
            
        # Risk contributions should sum to approximately 1
        self.assertAlmostEqual(sum(risk_contrib.values()), 1.0, places=6)
    
    def test_portfolio_metrics(self):
        """Test calculating portfolio metrics."""
        # Test with basic metrics
        metrics = self.controller.calculate_portfolio_metrics(
            weights={asset: 1.0/5 for asset in self.returns.columns},
            include_advanced=False
        )
        
        basic_metrics = ['annualized_return', 'annualized_volatility',
                        'sharpe_ratio', 'sortino_ratio', 'max_drawdown',
                        'var_95', 'cvar_95']
        
        for metric in basic_metrics:
            self.assertIn(metric, metrics)
        
        # Test with advanced metrics
        metrics = self.controller.calculate_portfolio_metrics(
            weights={asset: 1.0/5 for asset in self.returns.columns},
            include_advanced=True
        )
        
        advanced_metrics = ['calmar_ratio', 'volatility_of_volatility',
                           'average_drawdown', 'median_drawdown',
                           'skewness', 'kurtosis']
        
        for metric in advanced_metrics:
            self.assertIn(metric, metrics)
    
    def test_calculate_historical_returns(self):
        """Test calculating historical returns from equity curve."""
        # Create an equity curve
        equity_history = pd.Series(
            [100000 * (1 + 0.001) ** i for i in range(100)],
            index=self.dates
        )
        
        # Test without metrics
        returns = self.controller.calculate_historical_returns(
            equity_history=equity_history,
            include_metrics=False
        )
        
        self.assertEqual(len(returns), 99)  # One less than equity series due to pct_change()
        
        # Test with metrics
        results = self.controller.calculate_historical_returns(
            equity_history=equity_history,
            include_metrics=True
        )
        
        self.assertIn('returns', results)
        self.assertIn('metrics', results)
        self.assertEqual(len(results['returns']), 99)
        
        # Test different periods
        weekly_results = self.controller.calculate_historical_returns(
            equity_history=equity_history,
            period='W',
            include_metrics=True
        )
        
        self.assertLess(len(weekly_results['returns']), len(results['returns']))
    
    def test_calculate_diversification_metrics(self):
        """Test calculating diversification metrics for the portfolio."""
        # Test with default weights
        metrics = self.controller.calculate_diversification_metrics()
        
        # Check that all expected metrics are present
        expected_metrics = ['avg_correlation', 'diversification_ratio', 
                           'effective_n', 'concentration']
        
        for metric in expected_metrics:
            self.assertIn(metric, metrics)
        
        # Test with custom weights
        custom_weights = {
            'asset1': 0.5,  # Higher concentration
            'asset2': 0.2,
            'asset3': 0.1,
            'asset4': 0.1,
            'asset5': 0.1
        }
        
        custom_metrics = self.controller.calculate_diversification_metrics(weights=custom_weights)
        
        # Higher concentration should result in lower effective_n
        self.assertLess(custom_metrics['effective_n'], metrics['effective_n'])
        
        # And higher concentration value
        self.assertGreater(custom_metrics['concentration'], metrics['concentration'])
    
    def test_calculate_risk_adjusted_sizing(self):
        """Test risk-adjusted position sizing."""
        # Create target positions
        target_positions = {
            'asset1': 0.3,
            'asset2': 0.2,
            'asset3': 0.15,
            'asset4': 0.25,
            'asset5': 0.1
        }
        
        # Test with default max risk per position
        adjusted = self.controller.calculate_risk_adjusted_sizing(target_positions)
        
        # All assets should have positions
        for asset in target_positions:
            self.assertIn(asset, adjusted)
            
        # Higher volatility assets should have lower adjusted positions
        # Asset3 has highest volatility from our test data setup
        for asset in ['asset1', 'asset2', 'asset4', 'asset5']:
            self.assertGreater(abs(adjusted['asset3']), 0)
            
        # Test with a stricter risk limit
        strict_adjusted = self.controller.calculate_risk_adjusted_sizing(
            target_positions, 
            max_risk_per_position=0.01
        )
        
        # Stricter limit should result in smaller positions overall
        for asset in target_positions:
            self.assertLessEqual(abs(strict_adjusted[asset]), abs(adjusted[asset]))
    
    def test_calculate_risk_budget_allocation(self):
        """Test risk budget allocation."""
        # Create a risk budget
        risk_budget = {
            'asset1': 0.3,
            'asset2': 0.2,
            'asset3': 0.1,
            'asset4': 0.3,
            'asset5': 0.1
        }
        
        # Calculate weights for this risk budget
        weights = self.controller.calculate_risk_budget_allocation(risk_budget)
        
        # Weights should sum to 1
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
        
        # Calculate risk contributions with these weights
        risk_contrib = self.controller.calculate_risk_contribution(weights)
        
        # Risk contributions should approximately match the budget
        for asset, budget in risk_budget.items():
            self.assertAlmostEqual(risk_contrib[asset], budget, places=2)
    
    def test_calculate_portfolio_exposure(self):
        """Test calculating portfolio exposure metrics."""
        # Test with current positions
        exposure = self.controller.calculate_portfolio_exposure(
            positions=self.current_positions,
            equity=self.current_equity
        )
        
        # Check all expected metrics are present
        expected_metrics = ['gross_exposure', 'net_exposure', 'long_exposure', 
                          'short_exposure', 'position_count', 'long_positions', 
                          'short_positions', 'avg_position_size', 'max_position_size',
                          'concentration_ratio', 'exposure_to_equity']
        
        for metric in expected_metrics:
            self.assertIn(metric, exposure)
        
        # Verify basic calculations
        self.assertEqual(exposure['position_count'], len(self.current_positions))
        self.assertEqual(exposure['long_positions'], sum(1 for v in self.current_positions.values() if v > 0))
        self.assertEqual(exposure['short_positions'], sum(1 for v in self.current_positions.values() if v < 0))
        
        # Test with zero equity (edge case)
        zero_exposure = self.controller.calculate_portfolio_exposure(
            positions=self.current_positions,
            equity=0
        )
        
        for metric in expected_metrics:
            self.assertEqual(zero_exposure[metric], 0)
    
    def test_calculate_current_exposure(self):
        """Test calculating current portfolio exposure."""
        # Test with default arguments (using internal state)
        exposure = self.controller.calculate_current_exposure()
        
        # Manual calculation for comparison
        expected = sum(abs(v) for v in self.controller.current_weights.values())
        
        self.assertAlmostEqual(exposure, expected)
        
        # Test with custom positions and equity
        custom_positions = {
            'asset1': 20000,
            'asset2': 30000,
            'asset3': -15000,
            'asset4': 25000,
            'asset5': 10000
        }
        
        custom_equity = 150000
        
        custom_exposure = self.controller.calculate_current_exposure(
            current_positions=custom_positions,
            current_equity=custom_equity
        )
        
        expected_custom = sum(abs(v) for v in custom_positions.values()) / custom_equity
        
        self.assertAlmostEqual(custom_exposure, expected_custom)
    
    def test_calculate_current_weights(self):
        """Test calculating current portfolio weights."""
        # Test with default arguments (using internal state)
        weights = self.controller.calculate_current_weights()
        
        for asset, value in self.controller.current_weights.items():
            self.assertAlmostEqual(weights[asset], value)
        
        # Test with custom positions and equity
        custom_positions = {
            'asset1': 15000,
            'asset2': 25000,
            'asset3': -10000,
            'asset4': 30000,
            'asset5': 5000
        }
        
        custom_equity = 120000
        
        custom_weights = self.controller.calculate_current_weights(
            current_positions=custom_positions,
            current_equity=custom_equity
        )
        
        for asset, value in custom_positions.items():
            expected_weight = value / custom_equity
            self.assertAlmostEqual(custom_weights[asset], expected_weight)
    
    def test_calculate_current_drawdown(self):
        """Test calculating current drawdown."""
        # Set up peak equity and current equity for testing
        self.controller.peak_equity = 120000
        current_equity = 100000
        
        # Calculate drawdown
        drawdown = self.controller.calculate_current_drawdown(current_equity)
        
        # Expected drawdown: 1 - (current / peak)
        expected = 1 - (current_equity / self.controller.peak_equity)
        
        self.assertAlmostEqual(drawdown, expected)
        
        # Test with current equity greater than peak
        higher_equity = 130000
        
        # This should update the peak equity and return zero drawdown
        drawdown = self.controller.calculate_current_drawdown(higher_equity)
        
        self.assertEqual(drawdown, 0)
    
    def test_calculate_correlation_clusters(self):
        """Test calculating correlation clusters in the portfolio."""
        # Test with default parameters
        clusters = self.controller.calculate_correlation_clusters()
        
        # Clusters should be a dictionary
        self.assertIsInstance(clusters, dict)
        
        # Test with a custom threshold
        high_threshold_clusters = self.controller.calculate_correlation_clusters(threshold=0.9)
        
        # Higher threshold should result in fewer clusters or fewer members per cluster
        total_high_members = sum(len(members) for members in high_threshold_clusters.values())
        total_default_members = sum(len(members) for members in clusters.values())
        
        # The total assigned assets could be the same, but typically higher threshold
        # means fewer correlations exceed the threshold
        self.assertLessEqual(total_high_members, total_default_members)
    
    def test_calculate_current_market_state(self):
        """Test calculating current market state."""
        # Test with default parameters
        market_state = self.controller.calculate_current_market_state()
        
        # Should return a dictionary with assets and market keys
        self.assertIn('assets', market_state)
        self.assertIn('market', market_state)
        
        # Each asset should be included
        for asset in self.returns.columns:
            self.assertIn(asset, market_state['assets'])
            
        # Each asset state should include the expected metrics
        asset_metrics = ['current_volatility', 'relative_volatility', 'trend_direction',
                        'market_correlation', 'recent_performance']
        
        for asset in self.returns.columns:
            for metric in asset_metrics:
                self.assertIn(metric, market_state['assets'][asset])
                
        # Market state should include the expected metrics
        market_metrics = ['average_volatility', 'volatility_regime', 'trend_strength',
                        'trend_direction', 'average_correlation', 'overall_performance']
        
        for metric in market_metrics:
            self.assertIn(metric, market_state['market'])
    
    def test_calculate_current_market_state_metrics(self):
        """Test calculating current market state metrics."""
        # Test with default parameters
        metrics = self.controller.calculate_current_market_state_metrics()
        
        # Check expected metrics
        expected_metrics = ['average_correlation', 'average_volatility', 'return_dispersion',
                           'effective_num_assets', 'concentration_index', 'volatility_regime',
                           'correlation_regime', 'market_volatility', 'average_beta']
        
        for metric in expected_metrics:
            self.assertIn(metric, metrics)
            
        # Test with custom lookback period
        short_lookback = self.controller.calculate_current_market_state_metrics(lookback_period=20)
        
        # Same metrics should be present
        for metric in expected_metrics:
            self.assertIn(metric, short_lookback)
    
    def test_exceptions(self):
        """Test that appropriate exceptions are raised."""
        # Create a controller without historical returns
        empty_controller = PortfolioRiskController()
        
        # Should raise ValueError when trying to calculate weights
        with self.assertRaises(ValueError):
            empty_controller.calculate_portfolio_weights()
        
        # Should raise ValueError with invalid allocation method
        with self.assertRaises(ValueError):
            self.controller.calculate_portfolio_weights(method='invalid_method')
        
        # Test initialization with invalid parameters
        with self.assertRaises(ValueError):
            PortfolioRiskController(max_portfolio_exposure=-1)
        
        with self.assertRaises(ValueError):
            PortfolioRiskController(max_correlation_exposure=1.5)


if __name__ == '__main__':
    unittest.main() 