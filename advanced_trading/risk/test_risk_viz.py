"""
Test script for Portfolio Risk Visualization
-------------------------------------------
This script tests the visualization components of the PortfolioRiskController
with sample data to verify their functionality.
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from risk.portfolio_risk import PortfolioRiskController

# Create output directory for plots if it doesn't exist
output_dir = Path(__file__).resolve().parent / "test_output"
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
        trade_type='long',
        category='crypto_majors',
        correlation_group='bitcoin_ecosystem'
    )
    
    controller.register_position(
        symbol='ETH/USD',
        position_size=12,
        entry_price=2500,
        stop_price=2300,
        trade_type='long',
        category='crypto_majors',
        correlation_group='ethereum_ecosystem'
    )
    
    controller.register_position(
        symbol='SOL/USD',
        position_size=100,
        entry_price=100,
        stop_price=85,
        trade_type='long',
        category='crypto_alts',
        correlation_group='ethereum_ecosystem'
    )
    
    controller.register_position(
        symbol='ADA/USD',
        position_size=5000,
        entry_price=0.40,
        stop_price=0.34,
        trade_type='long',
        category='crypto_alts',
        correlation_group='cardano_ecosystem'
    )
    
    # Update positions with current prices (some winning, some losing)
    controller.update_position(symbol='BTC/USD', current_price=42000)
    controller.update_position(symbol='ETH/USD', current_price=2400)  # losing position
    controller.update_position(symbol='SOL/USD', current_price=110)
    controller.update_position(symbol='ADA/USD', current_price=0.41)
    
    # Add sample equity curve data
    days = 30
    base_equity = 100000
    timestamps = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
    
    # Create a somewhat realistic equity curve with some drawdowns
    np.random.seed(42)  # For reproducibility
    daily_returns = np.random.normal(0.002, 0.02, days)  # mean 0.2%, std 2%
    
    # Add a drawdown period
    daily_returns[10:15] = [-0.01, -0.02, -0.015, -0.01, 0.005]
    
    # Calculate cumulative equity
    cumulative_returns = np.cumprod(1 + daily_returns)
    equity_values = base_equity * cumulative_returns
    
    # Create Series
    controller.equity_curve = pd.Series(equity_values, index=timestamps)
    
    # Add VaR and CVaR history
    var_values = np.linspace(0.02, 0.04, days) + np.random.normal(0, 0.005, days)
    cvar_values = var_values * 1.4 + np.random.normal(0, 0.003, days)
    
    controller.var_history = var_values.tolist()
    controller.cvar_history = cvar_values.tolist()
    
    return controller

def test_visualizations():
    """Test all visualization methods and save output to files"""
    controller = create_test_controller()
    
    # Test and save each visualization
    
    # 1. Risk Allocation
    print("Testing plot_risk_allocation...")
    fig = controller.plot_risk_allocation()
    if fig:
        fig.savefig(output_dir / "risk_allocation.png")
        plt.close(fig)
    
    # 2. Equity Curve
    print("Testing plot_equity_curve...")
    fig = controller.plot_equity_curve()
    if fig:
        fig.savefig(output_dir / "equity_curve.png")
        plt.close(fig)
    
    # 3. Correlation Heatmap
    print("Testing plot_correlation_heatmap...")
    fig = controller.plot_correlation_heatmap()
    if fig:
        fig.savefig(output_dir / "correlation_heatmap.png")
        plt.close(fig)
    
    # 4. Risk Metrics
    print("Testing plot_risk_metrics...")
    fig = controller.plot_risk_metrics()
    if fig:
        fig.savefig(output_dir / "risk_metrics.png")
        plt.close(fig)
    
    # 5. Position Performance
    print("Testing plot_position_performance...")
    fig = controller.plot_position_performance()
    if fig:
        fig.savefig(output_dir / "position_performance.png")
        plt.close(fig)
    
    print(f"Visualization tests complete. Output saved to {output_dir}")

if __name__ == "__main__":
    test_visualizations() 