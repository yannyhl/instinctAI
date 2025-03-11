#!/usr/bin/env python
"""
Test script for the Statistical Significance Testing module.

This script demonstrates how to use the PerformanceSignificanceTester class
with synthetic data to evaluate trading strategy performance.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to path to import the module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backtest.walk_forward.significance_testing import PerformanceSignificanceTester

# Set random seed for reproducibility
np.random.seed(42)

def generate_synthetic_returns(n_days=252, mean_return=0.0005, volatility=0.01, 
                              autocorr=0.1, regime_shifts=True):
    """
    Generate synthetic daily returns with realistic properties.
    
    Parameters:
    -----------
    n_days : int
        Number of trading days
    mean_return : float
        Mean daily return
    volatility : float
        Daily volatility
    autocorr : float
        Return autocorrelation
    regime_shifts : bool
        Whether to include regime shifts
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with synthetic returns and regimes
    """
    # Generate dates
    start_date = datetime(2020, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]
    
    # Generate white noise
    noise = np.random.normal(0, 1, n_days)
    
    # Add autocorrelation
    returns = np.zeros(n_days)
    returns[0] = noise[0]
    for i in range(1, n_days):
        returns[i] = autocorr * returns[i-1] + np.sqrt(1 - autocorr**2) * noise[i]
    
    # Scale to desired volatility and add mean
    returns = returns * volatility + mean_return
    
    # Create regimes
    if regime_shifts:
        # Define 3 regimes: bull, bear, sideways
        regimes = np.ones(n_days)
        
        # Bull market (first third)
        regimes[:n_days//3] = 0
        returns[:n_days//3] += 0.001  # Higher returns in bull market
        
        # Bear market (middle third)
        regimes[n_days//3:2*n_days//3] = 1
        returns[n_days//3:2*n_days//3] -= 0.001  # Lower returns in bear market
        
        # Sideways market (last third)
        regimes[2*n_days//3:] = 2
        returns[2*n_days//3:] *= 0.5  # Lower volatility in sideways market
    else:
        regimes = np.zeros(n_days)
    
    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'returns': returns,
        'regime': regimes.astype(int)
    })
    
    df.set_index('date', inplace=True)
    
    return df

def generate_benchmark_returns(strategy_returns, beta=0.8, alpha=0.0001, 
                              idiosyncratic_vol=0.005):
    """
    Generate benchmark returns with a specified relationship to strategy returns.
    
    Parameters:
    -----------
    strategy_returns : pd.Series
        Strategy returns
    beta : float
        Beta of strategy to benchmark
    alpha : float
        Alpha (excess return) of strategy over benchmark
    idiosyncratic_vol : float
        Idiosyncratic volatility
        
    Returns:
    --------
    pd.Series
        Benchmark returns
    """
    n_days = len(strategy_returns)
    
    # Generate idiosyncratic returns
    idiosyncratic = np.random.normal(0, idiosyncratic_vol, n_days)
    
    # Calculate benchmark returns: r_strategy = alpha + beta * r_benchmark + idiosyncratic
    # Solving for r_benchmark: r_benchmark = (r_strategy - alpha - idiosyncratic) / beta
    benchmark_returns = (strategy_returns - alpha - idiosyncratic) / beta
    
    return benchmark_returns

def main():
    """Run tests with synthetic data."""
    print("Generating synthetic data...")
    
    # Generate strategy returns
    df = generate_synthetic_returns(n_days=756, mean_return=0.0008, volatility=0.015)
    strategy_returns = df['returns']
    regimes = df['regime']
    
    # Generate benchmark returns
    benchmark_returns = generate_benchmark_returns(strategy_returns, beta=0.85, alpha=0.0002)
    
    # Create output directory for plots
    output_dir = "significance_test_results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize tester
    print("Initializing PerformanceSignificanceTester...")
    tester = PerformanceSignificanceTester(
        alpha=0.05,
        n_bootstrap=1000,
        multiple_test_correction='fdr_bh',
        random_state=42
    )
    
    # Run t-tests
    print("Running t-tests...")
    t_test_one_sample = tester.t_test_returns(strategy_returns)
    print(f"One-sample t-test p-value: {t_test_one_sample['p_value']:.4f}")
    print(f"Reject null hypothesis: {t_test_one_sample['reject_null']}")
    
    t_test_two_sample = tester.t_test_returns(
        strategy_returns, benchmark_returns, test_type='two-sample'
    )
    print(f"Two-sample t-test p-value: {t_test_two_sample['p_value']:.4f}")
    print(f"Reject null hypothesis: {t_test_two_sample['reject_null']}")
    
    # Run bootstrap analysis
    print("\nRunning bootstrap analysis...")
    bootstrap_sharpe = tester.bootstrap_returns(strategy_returns, 'sharpe')
    print(f"Sharpe ratio: {bootstrap_sharpe['original_statistic']:.4f}")
    print(f"95% CI: ({bootstrap_sharpe['confidence_interval'][0]:.4f}, "
          f"{bootstrap_sharpe['confidence_interval'][1]:.4f})")
    print(f"Bootstrap p-value: {bootstrap_sharpe['p_value']:.4f}")
    
    # Plot bootstrap distribution
    print("Plotting bootstrap distribution...")
    fig_bootstrap = tester.plot_bootstrap_distribution('sharpe_ratio')
    fig_bootstrap.savefig(os.path.join(output_dir, "bootstrap_sharpe.png"))
    
    # Calculate performance metrics
    print("\nCalculating performance metrics...")
    metrics_df = tester.performance_metrics_with_ci(
        strategy_returns, benchmark_returns, risk_free_rate=0.02
    )
    print(metrics_df)
    
    # Plot performance metrics
    print("Plotting performance metrics...")
    fig_metrics = tester.plot_performance_metrics()
    fig_metrics.savefig(os.path.join(output_dir, "performance_metrics.png"))
    
    # Run multiple hypothesis tests
    print("\nRunning multiple hypothesis tests...")
    # Generate multiple p-values (simulating multiple strategy variations)
    n_tests = 20
    pvalues = np.random.uniform(0, 0.1, n_tests)  # Some will be significant by chance
    hypotheses = [f"Strategy Variation {i+1}" for i in range(n_tests)]
    
    mht_results = tester.multiple_hypothesis_test(pvalues, hypotheses)
    print(f"Original significant tests: {sum(pvalues < 0.05)}")
    print(f"After correction: {sum(mht_results['reject_null'])}")
    
    # Plot hypothesis test results
    print("Plotting hypothesis test results...")
    fig_mht = tester.plot_hypothesis_test_results()
    fig_mht.savefig(os.path.join(output_dir, "multiple_hypothesis_tests.png"))
    
    # Analyze performance by regime
    print("\nAnalyzing performance by regime...")
    fig_regime = tester.plot_regime_performance(
        strategy_returns, regimes, benchmark_returns
    )
    fig_regime.savefig(os.path.join(output_dir, "regime_performance.png"))
    
    # Generate summary report
    print("\nGenerating summary report...")
    summary = tester.generate_summary_report()
    
    # Save summary to file
    with open(os.path.join(output_dir, "summary_report.txt"), "w") as f:
        f.write("PERFORMANCE SIGNIFICANCE TESTING SUMMARY\n")
        f.write("=======================================\n\n")
        
        f.write(f"Test count: {summary['test_count']}\n")
        f.write(f"Significance level (alpha): {summary['alpha']}\n")
        f.write(f"Bootstrap samples: {summary['n_bootstrap']}\n")
        f.write(f"Multiple test correction: {summary['multiple_test_correction']}\n\n")
        
        if 't_test' in summary:
            f.write("T-TEST RESULTS\n")
            f.write("--------------\n")
            t_test = summary['t_test']
            f.write(f"Test type: {t_test['test_type']}\n")
            f.write(f"t-statistic: {t_test['t_statistic']:.4f}\n")
            f.write(f"p-value: {t_test['p_value']:.4f}\n")
            f.write(f"Reject null: {t_test['reject_null']}\n")
            f.write(f"Effect size: {t_test['effect_size']:.4f}\n")
            f.write(f"Mean return: {t_test['mean_return']:.6f}\n")
            f.write(f"Annualized return: {t_test['annualized_return']:.4f}\n")
            f.write(f"Sharpe ratio: {t_test['sharpe_ratio']:.4f}\n\n")
        
        if 'performance_metrics' in summary:
            f.write("PERFORMANCE METRICS\n")
            f.write("-------------------\n")
            perf = summary['performance_metrics']
            f.write(f"Significant metrics: {perf['significant_count']} out of {perf['total_testable']}\n")
            f.write(f"Significant percentage: {perf['significant_percentage']*100:.1f}%\n\n")
            
            f.write("Key metrics:\n")
            metrics = perf['metrics']
            for metric in ['sharpe', 'sortino', 'information_ratio', 'alpha']:
                if metric in metrics:
                    m = metrics[metric]
                    f.write(f"  {metric}: {m['value']:.4f} (95% CI: {m['ci_lower']:.4f} to {m['ci_upper']:.4f})")
                    if m['p_value'] is not None:
                        f.write(f", p-value: {m['p_value']:.4f}")
                    f.write("\n")
            f.write("\n")
        
        if 'multiple_hypothesis_test' in summary:
            f.write("MULTIPLE HYPOTHESIS TESTING\n")
            f.write("--------------------------\n")
            mht = summary['multiple_hypothesis_test']
            f.write(f"Correction method: {mht['correction_method']}\n")
            f.write(f"Significant tests: {mht['significant_count']} out of {mht['total_tests']}\n")
            f.write(f"Significant percentage: {mht['significant_percentage']*100:.1f}%\n\n")
    
    print(f"\nResults saved to {output_dir}/")
    print("Done!")

if __name__ == "__main__":
    main() 