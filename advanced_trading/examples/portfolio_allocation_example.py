#!/usr/bin/env python
"""
Portfolio Allocation Example
--------------------------
Demonstrates the usage of the Hierarchical Risk Parity and other portfolio
allocation methods implemented in the portfolio_allocation module.
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import logging
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import portfolio allocation module
from utils.portfolio_allocation import (
    PortfolioAllocator,
    allocate_portfolio,
    calculate_portfolio_performance,
    compare_allocation_methods,
    plot_allocation_comparison
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_strategy_returns():
    """
    Load or generate strategy returns for demonstration.
    
    In a real-world scenario, you would load actual strategy returns
    from your backtest results or performance database.
    
    Returns:
        DataFrame with strategy returns
    """
    # For demonstration, we'll generate synthetic return data
    # with different characteristics for each strategy
    
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Create date range for the past 2 years of daily data
    dates = pd.date_range(end=datetime.now(), periods=252*2, freq='B')
    
    # Create empty DataFrame
    returns = pd.DataFrame(index=dates)
    
    # Add strategy returns with different characteristics
    
    # Trend Following - Higher volatility, higher returns
    trend_returns = np.random.normal(0.0005, 0.012, len(dates))  # Positive mean, higher vol
    
    # Mean Reversion - Lower volatility, moderate returns
    mean_rev_returns = np.random.normal(0.0003, 0.008, len(dates))  # Positive mean, lower vol
    
    # ML Strategy - Moderate volatility, higher returns
    ml_returns = np.random.normal(0.0006, 0.010, len(dates))  # Higher mean, moderate vol
    
    # Statistical Arbitrage - Very low volatility, low returns
    stat_arb_returns = np.random.normal(0.0002, 0.005, len(dates))  # Lower mean, very low vol
    
    # Funding Rate Strategy - Moderate returns, spiky
    funding_returns = np.random.normal(0.0004, 0.007, len(dates))
    # Add occasional spikes to simulate funding events
    spike_indices = np.random.choice(len(dates), size=10, replace=False)
    funding_returns[spike_indices] *= 3
    
    # Add some correlation between strategies
    # Trend and ML are more correlated, Mean Rev and Stat Arb less correlated
    rho = 0.5
    trend_returns = trend_returns + rho * np.random.normal(0, 0.005, len(dates))
    ml_returns = ml_returns + rho * trend_returns
    
    rho_low = 0.2
    stat_arb_returns = stat_arb_returns + rho_low * mean_rev_returns
    
    # Add returns to DataFrame
    returns['Trend_Following'] = trend_returns
    returns['Mean_Reversion'] = mean_rev_returns
    returns['ML_Strategy'] = ml_returns
    returns['Stat_Arb'] = stat_arb_returns
    returns['Funding_Rate'] = funding_returns
    
    # Add some NaN values to test robustness
    for col in returns.columns:
        returns.loc[np.random.choice(returns.index, 5), col] = np.nan
    
    logger.info(f"Generated returns for {len(returns.columns)} strategies over {len(returns)} days")
    
    return returns

def analyze_allocations(returns):
    """
    Analyze and visualize different portfolio allocation methods.
    
    Args:
        returns: DataFrame with strategy returns
    """
    # Create output directory for charts
    output_dir = os.path.join(script_dir, 'results', 'portfolio_allocation')
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize a portfolio allocator with Hierarchical Risk Parity
    allocator = PortfolioAllocator(method='hrp')
    
    # Calculate allocations
    hrp_weights = allocator.allocate(returns)
    
    logger.info("Hierarchical Risk Parity Weights:")
    for strategy, weight in hrp_weights.items():
        logger.info(f"  {strategy}: {weight:.2%}")
    
    # Plot the hierarchical clustering of strategies
    cluster_fig = allocator.plot_hierarchical_clusters(returns)
    cluster_fig.savefig(os.path.join(output_dir, 'strategy_clusters.png'))
    
    # Plot the allocations
    alloc_fig = allocator.plot_allocations(hrp_weights)
    alloc_fig.savefig(os.path.join(output_dir, 'hrp_allocation.png'))
    
    # Calculate performance metrics
    performance = calculate_portfolio_performance(hrp_weights, returns)
    
    logger.info("\nHRP Portfolio Performance:")
    logger.info(f"  Annual Return: {performance['annualized_return']:.2%}")
    logger.info(f"  Annual Volatility: {performance['annualized_volatility']:.2%}")
    logger.info(f"  Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
    logger.info(f"  Max Drawdown: {performance['max_drawdown']:.2%}")
    logger.info(f"  Sortino Ratio: {performance['sortino_ratio']:.2f}")
    
    # Calculate risk contribution
    risk_contrib = allocator.calculate_allocation_risk_contribution(hrp_weights, returns)
    
    logger.info("\nRisk Contribution:")
    for strategy, contrib in risk_contrib.items():
        logger.info(f"  {strategy}: {contrib:.2%}")
    
    # Plot risk contribution
    risk_fig = allocator.plot_risk_contribution(hrp_weights, returns)
    risk_fig.savefig(os.path.join(output_dir, 'risk_contribution.png'))
    
    # Compare all allocation methods
    methods = ['hrp', 'risk_parity', 'min_variance', 'equal', 'sharpe_maximizing']
    comparison = compare_allocation_methods(returns, methods=methods)
    
    logger.info("\nAllocation Method Comparison:")
    for method, results in comparison.items():
        perf = results['performance']
        logger.info(f"\n{method.upper()} Method:")
        logger.info(f"  Sharpe Ratio: {perf['sharpe_ratio']:.2f}")
        logger.info(f"  Annual Return: {perf['annualized_return']:.2%}")
        logger.info(f"  Annual Volatility: {perf['annualized_volatility']:.2%}")
        logger.info(f"  Max Drawdown: {perf['max_drawdown']:.2%}")
    
    # Plot method comparison
    comparison_fig = plot_allocation_comparison(comparison)
    comparison_fig.savefig(os.path.join(output_dir, 'method_comparison.png'))
    
    logger.info(f"\nResults saved to {output_dir}")
    
    return comparison

def visualize_portfolio_performance(returns, allocations):
    """
    Visualize the performance of portfolios with different allocations.
    
    Args:
        returns: DataFrame with strategy returns
        allocations: Dictionary with allocation methods and their weights
    """
    # Create output directory
    output_dir = os.path.join(script_dir, 'results', 'portfolio_allocation')
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate portfolio returns for each allocation method
    portfolio_returns = pd.DataFrame(index=returns.index)
    
    for method, results in allocations.items():
        weights = results['weights']
        # Convert weights to array
        weight_array = np.array([weights.get(col, 0) for col in returns.columns])
        # Calculate portfolio returns
        portfolio_returns[method] = returns.fillna(0).dot(weight_array)
    
    # Calculate cumulative returns
    cumulative_returns = (1 + portfolio_returns).cumprod()
    
    # Plot cumulative returns
    plt.figure(figsize=(12, 8))
    for method in allocations.keys():
        plt.plot(cumulative_returns.index, cumulative_returns[method], label=method.upper())
    
    plt.title('Cumulative Returns by Allocation Method')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    
    # Save figure
    plt.savefig(os.path.join(output_dir, 'cumulative_returns.png'))
    
    # Calculate rolling metrics
    
    # Rolling Sharpe (annualized, 3-month window)
    window = 63  # ~3 months of trading days
    rolling_returns = portfolio_returns.rolling(window=window)
    
    # Calculate rolling volatility
    rolling_vol = rolling_returns.std() * np.sqrt(252)
    
    # Calculate rolling Sharpe ratio (assuming 0 risk-free rate for simplicity)
    rolling_sharpe = (portfolio_returns.rolling(window=window).mean() * 252) / rolling_vol
    
    # Plot rolling volatility
    plt.figure(figsize=(12, 8))
    for method in allocations.keys():
        plt.plot(rolling_vol.index, rolling_vol[method], label=method.upper())
    
    plt.title('Rolling Annualized Volatility (3-month window)')
    plt.xlabel('Date')
    plt.ylabel('Volatility')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    
    # Save figure
    plt.savefig(os.path.join(output_dir, 'rolling_volatility.png'))
    
    # Plot rolling Sharpe ratio
    plt.figure(figsize=(12, 8))
    for method in allocations.keys():
        plt.plot(rolling_sharpe.index, rolling_sharpe[method], label=method.upper())
    
    plt.title('Rolling Sharpe Ratio (3-month window)')
    plt.xlabel('Date')
    plt.ylabel('Sharpe Ratio')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    
    # Save figure
    plt.savefig(os.path.join(output_dir, 'rolling_sharpe.png'))
    
    # Calculate drawdowns
    drawdowns = {}
    for method in allocations.keys():
        # Calculate drawdown
        cum_returns = cumulative_returns[method]
        peak = cum_returns.cummax()
        drawdown = (cum_returns - peak) / peak
        drawdowns[method] = drawdown
    
    # Plot drawdowns
    plt.figure(figsize=(12, 8))
    for method, drawdown in drawdowns.items():
        plt.plot(drawdown.index, drawdown, label=method.upper())
    
    plt.title('Portfolio Drawdowns by Allocation Method')
    plt.xlabel('Date')
    plt.ylabel('Drawdown')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    
    # Save figure
    plt.savefig(os.path.join(output_dir, 'drawdowns.png'))
    
    logger.info("Portfolio performance visualization completed")

def apply_target_volatility(returns, target_vol=0.10):
    """
    Create portfolio allocations with target volatility.
    
    Args:
        returns: DataFrame with strategy returns
        target_vol: Target annualized volatility
        
    Returns:
        Dictionary with allocation results
    """
    logger.info(f"Creating portfolio with target volatility of {target_vol:.1%}")
    
    # Compare methods with target volatility
    methods = ['hrp', 'risk_parity', 'equal']
    comparison = compare_allocation_methods(
        returns, 
        methods=methods, 
        target_volatility=target_vol
    )
    
    # Create output directory
    output_dir = os.path.join(script_dir, 'results', 'portfolio_allocation')
    os.makedirs(output_dir, exist_ok=True)
    
    # Plot comparison
    comparison_fig = plot_allocation_comparison(comparison)
    comparison_fig.savefig(os.path.join(output_dir, 'target_vol_comparison.png'))
    
    # Log results
    logger.info("\nTarget Volatility Portfolio Results:")
    for method, results in comparison.items():
        perf = results['performance']
        logger.info(f"\n{method.upper()} Method with {target_vol:.1%} target volatility:")
        logger.info(f"  Sharpe Ratio: {perf['sharpe_ratio']:.2f}")
        logger.info(f"  Annual Return: {perf['annualized_return']:.2%}")
        logger.info(f"  Annual Volatility: {perf['annualized_volatility']:.2%}")
        logger.info(f"  Max Drawdown: {perf['max_drawdown']:.2%}")
    
    return comparison

def main():
    """Main function to run the portfolio allocation example."""
    logger.info("Starting Portfolio Allocation Example")
    
    # Load or generate strategy returns
    strategy_returns = load_strategy_returns()
    
    # Analyze different allocation methods
    allocations = analyze_allocations(strategy_returns)
    
    # Visualize portfolio performance
    visualize_portfolio_performance(strategy_returns, allocations)
    
    # Apply target volatility
    target_vol_allocations = apply_target_volatility(strategy_returns, target_vol=0.10)
    
    logger.info("Portfolio Allocation Example completed successfully")

if __name__ == "__main__":
    main() 