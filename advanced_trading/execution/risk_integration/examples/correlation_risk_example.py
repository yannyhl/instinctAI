"""
Correlation Risk Management Example

This example demonstrates how to use the CorrelationRiskManager to monitor and manage
correlation risk between assets and strategies, calculate diversification metrics,
and adjust position sizes based on correlation.

Key features demonstrated:
1. Tracking correlations between assets
2. Detecting correlation regime changes
3. Calculating diversification scores
4. Identifying highly correlated pairs
5. Adjusting position sizes based on correlation
"""

import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from advanced_trading.execution.risk_integration.correlation_risk import (
    CorrelationRiskManager,
    CorrelationRegime,
    CorrelationStats
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("correlation_risk_example")


def generate_correlated_returns(
    num_assets: int = 5,
    num_periods: int = 120,
    base_correlation: float = 0.3,
    volatility_range: Tuple[float, float] = (0.01, 0.03),
    correlation_regime_change: bool = True
) -> pd.DataFrame:
    """
    Generate synthetic correlated returns for testing.
    
    Args:
        num_assets: Number of assets to generate
        num_periods: Number of time periods
        base_correlation: Base correlation between assets
        volatility_range: Range of volatilities for assets
        correlation_regime_change: Whether to simulate regime changes
        
    Returns:
        DataFrame with correlated returns
    """
    # Generate random volatilities for each asset
    volatilities = np.random.uniform(
        volatility_range[0],
        volatility_range[1],
        num_assets
    )
    
    # Create correlation matrix
    if correlation_regime_change:
        # Create three regimes: low, moderate, and high correlation
        regime_lengths = [num_periods // 3] * 3
        regime_lengths[-1] += num_periods - sum(regime_lengths)  # Adjust for rounding
        
        correlation_values = [0.1, 0.4, 0.8]  # Low, moderate, high
        
        # Generate correlation matrices for each regime
        correlation_matrices = []
        for corr_value in correlation_values:
            # Base correlation matrix with specified correlation
            corr_matrix = np.ones((num_assets, num_assets)) * corr_value
            # Set diagonal to 1.0 (assets perfectly correlated with themselves)
            np.fill_diagonal(corr_matrix, 1.0)
            correlation_matrices.append(corr_matrix)
        
        # Generate returns for each regime
        all_returns = []
        for i, (corr_matrix, length) in enumerate(zip(correlation_matrices, regime_lengths)):
            # Generate correlated random returns using Cholesky decomposition
            L = np.linalg.cholesky(corr_matrix)
            uncorrelated_returns = np.random.normal(0, 1, (length, num_assets))
            correlated_returns = uncorrelated_returns @ L.T
            
            # Scale by volatilities
            scaled_returns = correlated_returns * volatilities
            
            all_returns.append(scaled_returns)
        
        # Combine all regimes
        returns = np.vstack(all_returns)
    else:
        # Create a single correlation matrix
        corr_matrix = np.ones((num_assets, num_assets)) * base_correlation
        np.fill_diagonal(corr_matrix, 1.0)
        
        # Generate correlated random returns
        L = np.linalg.cholesky(corr_matrix)
        uncorrelated_returns = np.random.normal(0, 1, (num_periods, num_assets))
        correlated_returns = uncorrelated_returns @ L.T
        
        # Scale by volatilities
        returns = correlated_returns * volatilities
    
    # Create DataFrame
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=num_periods),
        periods=num_periods,
        freq='D'
    )
    columns = [f"Asset_{i+1}" for i in range(num_assets)]
    
    return pd.DataFrame(returns, index=dates, columns=columns)


def example_correlation_monitoring():
    """Demonstrate basic correlation monitoring capabilities."""
    logger.info("=== Correlation Monitoring Example ===")
    
    # Create correlation risk manager
    manager = CorrelationRiskManager(
        max_correlation_threshold=0.7,
        lookback_periods=30,
        crisis_detection_threshold=0.8
    )
    
    # Generate sample return data
    returns_df = generate_correlated_returns(
        num_assets=5,
        num_periods=90,
        correlation_regime_change=True
    )
    
    # Process returns sequentially to simulate real-time updates
    for i in range(0, len(returns_df), 5):  # Process in batches of 5 days
        batch = returns_df.iloc[i:i+5]
        
        for date, row in batch.iterrows():
            # Extract returns for this day
            return_data = {col: row[col] for col in returns_df.columns}
            
            # Update returns in the manager
            manager.update_returns(return_data, timestamp=date)
        
        # Analyze correlation
        stats = manager.analyze_correlation()
        
        # Calculate diversification score
        div_score = manager.get_diversification_score()
        
        # Log results
        logger.info(f"Date: {batch.index[-1].strftime('%Y-%m-%d')}")
        logger.info(f"Correlation Regime: {stats.regime.value}")
        logger.info(f"Average Correlation: {stats.average_correlation:.3f}")
        logger.info(f"Max Correlation: {stats.max_correlation:.3f}")
        logger.info(f"Effective Positions: {stats.effective_n:.2f} (out of 5)")
        logger.info(f"Diversification Score: {div_score:.3f}")
        logger.info(f"Crisis Probability: {stats.crisis_probability:.3f}")
        logger.info("-" * 40)
    
    # Check for highly correlated pairs
    high_corr_pairs = manager.get_highly_correlated_pairs(threshold=0.6)
    if high_corr_pairs:
        logger.info("Highly correlated pairs:")
        for asset1, asset2, corr in high_corr_pairs:
            logger.info(f"  {asset1} / {asset2}: {corr:.3f}")


def example_position_adjustment():
    """Demonstrate position size adjustment based on correlation."""
    logger.info("=== Position Size Adjustment Example ===")
    
    # Create correlation risk manager
    manager = CorrelationRiskManager(
        max_correlation_threshold=0.7,
        lookback_periods=30,
        crisis_detection_threshold=0.8
    )
    
    # Generate sample return data with increasing correlation
    returns_df = generate_correlated_returns(
        num_assets=6,
        num_periods=100,
        correlation_regime_change=True
    )
    
    # Define initial position sizes
    base_position_sizes = {
        "Asset_1": 0.20,  # 20% allocation
        "Asset_2": 0.15,  # 15% allocation
        "Asset_3": 0.25,  # 25% allocation
        "Asset_4": 0.15,  # 15% allocation
        "Asset_5": 0.10,  # 10% allocation
        "Asset_6": 0.15   # 15% allocation
    }
    
    # Initialize tracking data
    dates = []
    regimes = []
    avg_correlations = []
    original_allocations = []
    adjusted_allocations = []
    
    # Process returns in batches
    for i in range(0, len(returns_df), 10):  # Process in larger batches
        batch = returns_df.iloc[i:i+10]
        
        for date, row in batch.iterrows():
            # Extract returns for this day
            return_data = {col: row[col] for col in returns_df.columns}
            
            # Update returns in the manager
            manager.update_returns(return_data, timestamp=date)
        
        # Skip if batch is empty
        if batch.empty:
            continue
            
        # Analyze correlation
        stats = manager.analyze_correlation()
        
        # Calculate adjusted position sizes
        adjusted_sizes = manager.calculate_optimal_position_sizes(base_position_sizes)
        
        # Get risk assessment
        assessment = manager.get_risk_assessment()
        
        # Print results
        logger.info(f"Date: {batch.index[-1].strftime('%Y-%m-%d')}")
        logger.info(f"Correlation Regime: {stats.regime.value}")
        logger.info(f"Average Correlation: {stats.average_correlation:.3f}")
        logger.info(f"Risk Assessment: {assessment['risk_level']}")
        logger.info(f"Recommendation: {assessment['recommendation']}")
        
        logger.info("Position Size Adjustments:")
        total_original = sum(base_position_sizes.values())
        total_adjusted = sum(adjusted_sizes.values())
        original_allocation = {}
        adjusted_allocation = {}
        
        for asset in base_position_sizes:
            orig = base_position_sizes[asset]
            adj = adjusted_sizes[asset]
            change_pct = (adj - orig) / orig * 100 if orig > 0 else 0
            
            logger.info(f"  {asset}: {orig:.3f} → {adj:.3f} ({change_pct:+.1f}%)")
            
            # Store for visualization
            original_allocation[asset] = orig / total_original
            adjusted_allocation[asset] = adj / total_adjusted
        
        # Store data for visualization
        dates.append(batch.index[-1])
        regimes.append(stats.regime.value)
        avg_correlations.append(stats.average_correlation)
        original_allocations.append(original_allocation)
        adjusted_allocations.append(adjusted_allocation)
        
        logger.info("-" * 40)
    
    # Visualize results
    try:
        plt.figure(figsize=(12, 8))
        
        # Plot 1: Average correlation and regimes
        plt.subplot(2, 1, 1)
        plt.plot(dates, avg_correlations, 'b-', label='Average Correlation')
        plt.scatter(dates, avg_correlations, c=[{'low': 'green', 'moderate': 'blue', 'high': 'orange', 'crisis': 'red'}[r] for r in regimes])
        
        regime_changes = [i for i in range(1, len(regimes)) if regimes[i] != regimes[i-1]]
        for i in regime_changes:
            plt.axvline(x=dates[i], color='gray', linestyle='--', alpha=0.7)
        
        plt.title('Average Correlation and Regime Changes')
        plt.ylabel('Correlation')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Plot 2: Position size adjustments for a few assets
        plt.subplot(2, 1, 2)
        
        # Selected assets to show
        selected_assets = list(base_position_sizes.keys())[:3]
        
        for asset in selected_assets:
            original = [alloc[asset] for alloc in original_allocations]
            adjusted = [alloc[asset] for alloc in adjusted_allocations]
            
            plt.plot(dates, original, '--', label=f'{asset} Original')
            plt.plot(dates, adjusted, '-', label=f'{asset} Adjusted')
        
        plt.title('Position Size Adjustments (Selected Assets)')
        plt.ylabel('Allocation')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('correlation_adjustments.png')
        logger.info("Saved visualization to correlation_adjustments.png")
    except Exception as e:
        logger.error(f"Error creating visualization: {str(e)}")


def example_crisis_scenario():
    """Demonstrate correlation behavior during a crisis scenario."""
    logger.info("=== Crisis Scenario Example ===")
    
    # Create correlation risk manager
    manager = CorrelationRiskManager(
        max_correlation_threshold=0.7,
        lookback_periods=30,
        crisis_detection_threshold=0.8
    )
    
    # Normal returns: First 60 days
    normal_returns = generate_correlated_returns(
        num_assets=8,
        num_periods=60,
        base_correlation=0.3,
        correlation_regime_change=False
    )
    
    # Crisis returns: Next 20 days with high correlation
    crisis_returns = generate_correlated_returns(
        num_assets=8,
        num_periods=20,
        base_correlation=0.8,  # High correlation during crisis
        volatility_range=(0.03, 0.06),  # Higher volatility
        correlation_regime_change=False
    )
    
    # Recovery returns: Final 20 days
    recovery_returns = generate_correlated_returns(
        num_assets=8,
        num_periods=20,
        base_correlation=0.5,  # Moderate correlation during recovery
        volatility_range=(0.02, 0.04),
        correlation_regime_change=False
    )
    
    # Combine returns
    all_dates = pd.concat([normal_returns, crisis_returns, recovery_returns]).index
    all_returns = pd.concat([normal_returns, crisis_returns, recovery_returns])
    
    # Process all returns
    for date, row in all_returns.iterrows():
        # Extract returns for this day
        return_data = {col: row[col] for col in all_returns.columns}
        
        # Update returns in the manager
        manager.update_returns(return_data, timestamp=date)
        
        # Analyze correlation every 5 days
        if date.day % 5 == 0 or date in crisis_returns.index[:5]:
            stats = manager.analyze_correlation()
            assessment = manager.get_risk_assessment()
            
            phase = "Normal"
            if date in crisis_returns.index:
                phase = "Crisis"
            elif date in recovery_returns.index:
                phase = "Recovery"
            
            logger.info(f"Date: {date.strftime('%Y-%m-%d')} (Phase: {phase})")
            logger.info(f"Correlation Regime: {stats.regime.value}")
            logger.info(f"Average Correlation: {stats.average_correlation:.3f}")
            logger.info(f"Effective Positions: {stats.effective_n:.2f} (out of 8)")
            logger.info(f"Diversification Score: {manager.get_diversification_score():.3f}")
            logger.info(f"Risk Level: {assessment['risk_level']}")
            logger.info(f"Recommendation: {assessment['recommendation']}")
            logger.info("-" * 40)


if __name__ == "__main__":
    try:
        logger.info("Starting correlation risk management examples")
        
        # Run examples
        example_correlation_monitoring()
        example_position_adjustment()
        example_crisis_scenario()
        
        logger.info("All examples completed successfully")
    except Exception as e:
        logger.error(f"Error in examples: {str(e)}", exc_info=True) 