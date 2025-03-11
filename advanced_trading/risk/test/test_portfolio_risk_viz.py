"""
Test Portfolio Risk Visualization

This module tests the visualization components of the portfolio risk management system
with sample data to verify their functionality.
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from pathlib import Path

# Import the portfolio risk module
from advanced_trading.risk.portfolio import PortfolioRiskController

# Create output directory for plots if it doesn't exist
output_dir = Path(__file__).resolve().parent / "output"
output_dir.mkdir(exist_ok=True)

# Create a risk controller with sample data
def create_test_controller():
    """Create a PortfolioRiskController with sample test data"""
    controller = PortfolioRiskController(account_size=100000)
    
    # Add sample correlation matrix
    symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'ADA/USD', 'DOT/USD']
    correlation_data = np.array([
        [1.0, 0.8, 0.7, 0.6, 0.5],
        [0.8, 1.0, 0.6, 0.5, 0.4],
        [0.7, 0.6, 1.0, 0.7, 0.3],
        [0.6, 0.5, 0.7, 1.0, 0.6],
        [0.5, 0.4, 0.3, 0.6, 1.0]
    ])
    controller.correlation_matrix = pd.DataFrame(
        correlation_data, 
        index=symbols, 
        columns=symbols
    )
    
    # Add sample positions
    controller.register_position(
        symbol='BTC/USD',
        position_size=1.5,
        entry_price=40000,
        stop_price=38000,
        risk_amount=3000,
        trade_type='long',
        category='crypto',
        correlation_group='major'
    )
    
    controller.register_position(
        symbol='ETH/USD',
        position_size=10,
        entry_price=2800,
        stop_price=2600,
        risk_amount=2000,
        trade_type='long',
        category='crypto',
        correlation_group='major'
    )
    
    controller.register_position(
        symbol='SOL/USD',
        position_size=50,
        entry_price=100,
        stop_price=90,
        risk_amount=500,
        trade_type='long',
        category='crypto',
        correlation_group='altcoin'
    )
    
    controller.register_position(
        symbol='ADA/USD',
        position_size=2000,
        entry_price=1.20,
        stop_price=1.10,
        risk_amount=200,
        trade_type='long',
        category='crypto',
        correlation_group='altcoin'
    )
    
    # Add sample returns data
    days = 100
    dates = [datetime.now() - timedelta(days=i) for i in range(days)]
    
    returns_data = {
        'BTC/USD': np.random.normal(0.001, 0.03, days),
        'ETH/USD': np.random.normal(0.002, 0.04, days),
        'SOL/USD': np.random.normal(0.003, 0.05, days),
        'ADA/USD': np.random.normal(0.001, 0.04, days),
        'DOT/USD': np.random.normal(0.002, 0.045, days)
    }
    
    returns_df = pd.DataFrame(returns_data, index=dates)
    controller.returns_data = returns_df
    
    # Add sample portfolio returns
    weights = {
        'BTC/USD': 0.4,
        'ETH/USD': 0.3,
        'SOL/USD': 0.1,
        'ADA/USD': 0.1,
        'DOT/USD': 0.1
    }
    
    portfolio_returns = pd.Series(
        np.zeros(days),
        index=dates
    )
    
    for symbol, weight in weights.items():
        portfolio_returns += returns_data[symbol] * weight
    
    controller.portfolio_returns = portfolio_returns
    
    return controller

def test_visualizations():
    """Test all visualization components"""
    controller = create_test_controller()
    
    # Test correlation heatmap
    fig1 = controller.plot_correlation_heatmap()
    fig1.savefig(output_dir / "correlation_heatmap.png")
    
    # Test risk allocation chart
    fig2 = controller.plot_risk_allocation()
    fig2.savefig(output_dir / "risk_allocation.png")
    
    # Test drawdown chart
    fig3 = controller.plot_drawdown()
    fig3.savefig(output_dir / "drawdown.png")
    
    # Test returns distribution
    fig4 = controller.plot_returns_distribution()
    fig4.savefig(output_dir / "returns_distribution.png")
    
    # Test risk metrics table
    fig5 = controller.plot_risk_metrics_table()
    fig5.savefig(output_dir / "risk_metrics_table.png")
    
    print("All visualization tests completed. See output directory for results.")

if __name__ == "__main__":
    test_visualizations() 