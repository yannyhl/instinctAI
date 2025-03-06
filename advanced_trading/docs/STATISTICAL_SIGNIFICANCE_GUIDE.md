# Statistical Significance Testing Guide

## Overview

The Statistical Significance Testing module provides robust tools for evaluating the statistical significance of trading strategy performance. This guide explains how to use the module to determine if your strategy's performance is genuinely superior or merely the result of chance.

## Why Statistical Significance Matters

Trading strategies often appear profitable in backtests but fail in live trading. Common reasons include:

1. **Data mining bias**: Testing many strategies until finding one that works by chance
2. **Overfitting**: Creating a strategy that fits historical data too closely
3. **Selection bias**: Focusing only on successful backtest results
4. **Look-ahead bias**: Accidentally using future information
5. **Survivorship bias**: Testing only on securities that survived to the present

The Statistical Significance Testing module helps address these issues by providing rigorous statistical methods to evaluate strategy performance.

## Key Features

The module offers the following key features:

1. **T-tests for returns**: Determine if returns are significantly different from zero or a benchmark
2. **Bootstrap analysis**: Estimate confidence intervals for performance metrics
3. **Multiple hypothesis testing**: Control for data mining bias when testing multiple strategies
4. **Performance metrics with confidence intervals**: Quantify uncertainty in metrics like Sharpe ratio
5. **Regime-specific significance testing**: Evaluate performance across different market conditions
6. **Visualization tools**: Generate plots to interpret test results

## Getting Started

### Installation

The module is included in the Instinct AI Advanced Trading package. No additional installation is required.

### Basic Usage

```python
from instinct_ai.advanced_trading.backtest.walk_forward.significance_testing import PerformanceSignificanceTester

# Initialize the tester
tester = PerformanceSignificanceTester(
    alpha=0.05,               # Significance level
    n_bootstrap=1000,         # Number of bootstrap samples
    multiple_test_correction='fdr_bh',  # Multiple testing correction method
    random_state=42           # Random seed for reproducibility
)

# Run t-test on strategy returns
t_test_results = tester.t_test_returns(strategy_returns)

# Run bootstrap analysis for Sharpe ratio
bootstrap_results = tester.bootstrap_returns(strategy_returns, 'sharpe')

# Calculate performance metrics with confidence intervals
metrics_df = tester.performance_metrics_with_ci(
    strategy_returns, 
    benchmark_returns, 
    risk_free_rate=0.02
)

# Generate visualizations
fig = tester.plot_bootstrap_distribution('sharpe_ratio')
fig.savefig("bootstrap_sharpe.png")
```

## Detailed Usage Guide

### T-Tests for Returns

T-tests help determine if your strategy's returns are statistically different from zero or a benchmark.

```python
# One-sample t-test (test if returns are different from zero)
t_test_one_sample = tester.t_test_returns(strategy_returns)

# Two-sample t-test (test if strategy returns are different from benchmark)
t_test_two_sample = tester.t_test_returns(
    strategy_returns, 
    benchmark_returns, 
    test_type='two-sample'
)

# Paired t-test (test if strategy outperforms benchmark on a paired basis)
t_test_paired = tester.t_test_returns(
    strategy_returns, 
    benchmark_returns, 
    test_type='paired'
)
```

The results include:
- t-statistic
- p-value
- Effect size (Cohen's d)
- Confidence intervals
- Decision to reject or fail to reject the null hypothesis

### Bootstrap Analysis

Bootstrap analysis provides robust confidence intervals for performance metrics by resampling the returns data.

```python
# Bootstrap Sharpe ratio
bootstrap_sharpe = tester.bootstrap_returns(strategy_returns, 'sharpe')

# Bootstrap with block bootstrap for time series with autocorrelation
bootstrap_sortino = tester.bootstrap_returns(
    strategy_returns, 
    'sortino', 
    block_size=20  # Block size for block bootstrap
)

# Bootstrap custom statistic
def max_drawdown(returns):
    # Calculate maximum drawdown
    cum_returns = (1 + returns).cumprod()
    running_max = np.maximum.accumulate(cum_returns)
    drawdowns = cum_returns / running_max - 1
    return np.min(drawdowns)

bootstrap_drawdown = tester.bootstrap_returns(strategy_returns, max_drawdown)
```

The results include:
- Original statistic value
- Bootstrap mean and standard deviation
- Confidence intervals
- p-value
- Bootstrap distribution for visualization

### Multiple Hypothesis Testing

When testing multiple strategies or parameters, multiple hypothesis testing helps control the false discovery rate.

```python
# Generate p-values from multiple strategy tests
pvalues = [0.01, 0.03, 0.04, 0.06, 0.08]
hypotheses = ["Strategy 1", "Strategy 2", "Strategy 3", "Strategy 4", "Strategy 5"]

# Apply multiple testing correction
mht_results = tester.multiple_hypothesis_test(pvalues, hypotheses)
```

The results include:
- Original p-values
- Corrected p-values
- Decisions after correction
- Visualization of p-value distribution

### Performance Metrics with Confidence Intervals

Calculate comprehensive performance metrics with bootstrap confidence intervals.

```python
metrics_df = tester.performance_metrics_with_ci(
    strategy_returns, 
    benchmark_returns, 
    risk_free_rate=0.02,
    periodicity='daily'  # 'daily', 'weekly', or 'monthly'
)
```

Metrics include:
- Mean return
- Annualized return
- Volatility
- Sharpe ratio
- Sortino ratio
- Maximum drawdown
- Skewness and kurtosis
- Benchmark-relative metrics (if benchmark provided):
  - Excess return
  - Tracking error
  - Information ratio
  - Beta
  - Alpha

### Regime-Specific Analysis

Evaluate strategy performance across different market regimes.

```python
# Assuming you have regime labels for each return observation
fig_regime = tester.plot_regime_performance(
    strategy_returns, 
    regimes,  # Array of regime labels
    benchmark_returns
)
```

This analysis helps determine if your strategy performs consistently across different market conditions or if it's only effective in specific regimes.

### Visualization Tools

The module provides several visualization tools:

```python
# Plot bootstrap distribution
fig_bootstrap = tester.plot_bootstrap_distribution('sharpe_ratio')

# Plot performance metrics with confidence intervals
fig_metrics = tester.plot_performance_metrics()

# Plot multiple hypothesis test results
fig_mht = tester.plot_hypothesis_test_results()

# Plot regime-specific performance
fig_regime = tester.plot_regime_performance(
    strategy_returns, regimes, benchmark_returns
)
```

### Summary Report

Generate a comprehensive summary of all test results.

```python
summary = tester.generate_summary_report()
```

## Best Practices

1. **Always test against a relevant benchmark**: Comparing to a benchmark helps determine if your strategy adds value beyond passive investing.

2. **Use block bootstrap for time series data**: Financial returns often exhibit autocorrelation, making standard bootstrap methods inappropriate. Use block bootstrap instead.

3. **Control for multiple testing**: When testing multiple strategies or parameters, always apply multiple testing corrections to avoid false discoveries.

4. **Test across different market regimes**: A strategy that performs well in all market conditions is more robust than one that only works in specific regimes.

5. **Consider economic significance, not just statistical significance**: A statistically significant result might not be economically meaningful if transaction costs or other practical considerations are taken into account.

6. **Use out-of-sample testing**: The most reliable test is performance on data not used in strategy development.

## Example Workflow

Here's a complete workflow for evaluating a trading strategy:

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from instinct_ai.advanced_trading.backtest.walk_forward.significance_testing import PerformanceSignificanceTester

# Load strategy returns and benchmark returns
strategy_returns = pd.read_csv('strategy_returns.csv')['returns']
benchmark_returns = pd.read_csv('benchmark_returns.csv')['returns']

# Initialize tester
tester = PerformanceSignificanceTester(
    alpha=0.05,
    n_bootstrap=1000,
    multiple_test_correction='fdr_bh',
    random_state=42
)

# 1. Run t-tests
t_test_results = tester.t_test_returns(
    strategy_returns, 
    benchmark_returns, 
    test_type='paired'
)
print(f"T-test p-value: {t_test_results['p_value']:.4f}")
print(f"Reject null hypothesis: {t_test_results['reject_null']}")

# 2. Calculate performance metrics with confidence intervals
metrics_df = tester.performance_metrics_with_ci(
    strategy_returns, 
    benchmark_returns, 
    risk_free_rate=0.02
)
print(metrics_df)

# 3. Plot performance metrics
fig_metrics = tester.plot_performance_metrics()
fig_metrics.savefig("performance_metrics.png")

# 4. Generate summary report
summary = tester.generate_summary_report()

# 5. Save summary to file
with open("significance_test_summary.txt", "w") as f:
    f.write(str(summary))

print("Analysis complete!")
```

## Conclusion

The Statistical Significance Testing module provides a comprehensive toolkit for evaluating trading strategy performance. By applying these methods, you can gain confidence in your strategy's robustness and avoid common pitfalls in strategy development.

For more information, refer to the API documentation or the example scripts in the package.

## References

1. Harvey, C. R., & Liu, Y. (2015). Backtesting. The Journal of Portfolio Management, 42(1), 13-28.
2. Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2016). The probability of backtest overfitting. Journal of Computational Finance, 20(4), 39-69.
3. López de Prado, M. (2018). Advances in financial machine learning. John Wiley & Sons.
4. Efron, B., & Tibshirani, R. J. (1994). An introduction to the bootstrap. CRC press.
5. White, H. (2000). A reality check for data snooping. Econometrica, 68(5), 1097-1126. 