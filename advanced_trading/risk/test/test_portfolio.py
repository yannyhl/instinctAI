"""
Tests for the Portfolio Risk Controller
# advanced_trading/risk/test/test_portfolio.py 
This module contains unit tests for the PortfolioRiskController class
and related portfolio risk management functionality.
"""

import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from advanced_trading.risk.portfolio import (
    PortfolioRiskController,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_correlation_matrix
)

class TestPortfolioRiskController(unittest.TestCase):
    """Test cases for the PortfolioRiskController class."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample returns data
        np.random.seed(42)  # For reproducibility
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        assets = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META']
        
        # Generate correlated returns
        cov_matrix = np.array([
            [0.0004, 0.0002, 0.0001, 0.0001, 0.0002],
            [0.0002, 0.0005, 0.0001, 0.0002, 0.0001],
            [0.0001, 0.0001, 0.0006, 0.0002, 0.0001],
            [0.0001, 0.0002, 0.0002, 0.0005, 0.0002],
            [0.0002, 0.0001, 0.0001, 0.0002, 0.0007]
        ])
        
        # Generate random returns with the given covariance structure
        daily_returns = np.random.multivariate_normal(
            mean=[0.0005, 0.0004, 0.0006, 0.0003, 0.0004],
            cov=cov_matrix,
            size=len(dates)
        )
        
        # Create DataFrame with returns
        self.returns_df = pd.DataFrame(
            daily_returns,
            index=dates,
            columns=assets
        )
        
        # Current portfolio state
        self.current_equity = 100000.0
        self.current_positions = {
            'AAPL': 20000.0,
            'MSFT': 30000.0,
            'AMZN': 15000.0,
            'GOOGL': 25000.0,
            'META': 10000.0
        }
        
        # Create the controller
        self.controller = PortfolioRiskController(
            max_portfolio_exposure=1.5,
            max_correlation_exposure=0.5,
            drawdown_control_threshold=0.05,
            target_portfolio_volatility=0.12,
            allocation_method='equal'
        )
        
        # Update controller with market data
        self.controller.update_market_state(
            returns=self.returns_df,
            current_equity=self.current_equity,
            current_positions=self.current_positions,
            current_date=datetime.now()
        )
    
    def test_initialization(self):
        """Test controller initialization."""
        self.assertEqual(self.controller.max_portfolio_exposure, 1.5)
        self.assertEqual(self.controller.max_correlation_exposure, 0.5)
        self.assertEqual(self.controller.drawdown_control_threshold, 0.05)
        self.assertEqual(self.controller.target_portfolio_volatility, 0.12)
        self.assertEqual(self.controller.allocation_method, 'equal')
    
    def test_calculate_portfolio_weights(self):
        """Test portfolio weight calculation."""
        weights = self.controller.calculate_portfolio_weights()
        
        # Check that weights sum to 1.0
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
        
        # Check that all assets are included
        self.assertEqual(set(weights.keys()), set(self.returns_df.columns))
        
        # Check equal weights
        for weight in weights.values():
            self.assertAlmostEqual(weight, 1.0 / len(self.returns_df.columns), places=6)
    
    def test_calculate_risk_metrics(self):
        """Test risk metrics calculation."""
        weights = self.controller.calculate_portfolio_weights()
        metrics = self.controller.calculate_risk_metrics(weights=weights)
        
        # Check that all expected metrics are present
        expected_metrics = ['volatility', 'sharpe_ratio', 'max_drawdown', 'var_95', 'cvar_95', 'annualized_return']
        for metric in expected_metrics:
            self.assertIn(metric, metrics)
            
        # Check that volatility is positive
        self.assertGreater(metrics['volatility'], 0)
        
        # Check that max drawdown is negative or zero
        self.assertLessEqual(metrics['max_drawdown'], 0)
    
    def test_adjust_weights_for_risk_targets(self):
        """Test weight adjustment for risk targets."""
        weights = self.controller.calculate_portfolio_weights()
        adjusted_weights = self.controller.adjust_weights_for_risk_targets(weights)
        
        # Check that weights are adjusted
        self.assertNotEqual(weights, adjusted_weights)
        
        # Check that the sum of absolute weights is consistent with target volatility
        portfolio_exposure = sum(abs(w) for w in adjusted_weights.values())
        self.assertTrue(0 < portfolio_exposure < 2.0)
    
    def test_correlation_clusters(self):
        """Test correlation cluster identification."""
        # Ensure correlation clusters were created
        self.assertIsNotNone(self.controller.correlation_clusters)
        
    def test_generate_position_sizing_recommendations(self):
        """Test position sizing recommendations."""
        recommendations = self.controller.generate_position_sizing_recommendations(
            current_equity=self.current_equity,
            current_positions=self.current_positions
        )
        
        # Check that all expected sections are present
        expected_sections = [
            'optimal_weights', 'risk_adjusted_weights', 'final_weights',
            'recommended_trades', 'risk_metrics', 'diversification_metrics',
            'portfolio_exposure', 'drawdown_status'
        ]
        for section in expected_sections:
            self.assertIn(section, recommendations)
        
        # Check that trades are reasonable
        for asset, trade in recommendations['recommended_trades'].items():
            self.assertLessEqual(abs(trade), self.current_equity * 0.5)

if __name__ == '__main__':
    unittest.main()