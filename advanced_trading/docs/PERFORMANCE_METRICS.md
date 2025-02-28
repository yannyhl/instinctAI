# Instinct AI Performance Metrics Guide

This document provides a comprehensive overview of the performance metrics used to evaluate trading strategies within the Instinct AI system. These metrics help traders assess profitability, risk, and overall effectiveness of their strategies.

## Overview

Performance measurement in Instinct AI follows a multi-dimensional approach, evaluating strategies across several key categories:

1. **Return Metrics**: Measure profitability
2. **Risk Metrics**: Evaluate downside exposure
3. **Risk-Adjusted Metrics**: Balance return against risk
4. **Trade Metrics**: Analyze individual trade performance
5. **Statistical Metrics**: Assess statistical properties of returns
6. **Market-Relative Metrics**: Compare to benchmarks

## Return Metrics

### Total Return

The overall percentage gain or loss from a strategy over the entire backtest period.

```python
def calculate_total_return(portfolio_values):
    """Calculate total return from portfolio values."""
    initial_value = portfolio_values.iloc[0]
    final_value = portfolio_values.iloc[-1]
    total_return = (final_value / initial_value - 1) * 100
    return total_return
```

**Interpretation**: Higher is better. A total return of 20% means the strategy grew the initial capital by 20%.

### Annualized Return (CAGR)

The Compound Annual Growth Rate, representing the annual rate of return achieved over the test period.

```python
def calculate_annualized_return(portfolio_values):
    """Calculate annualized return (CAGR)."""
    initial_value = portfolio_values.iloc[0]
    final_value = portfolio_values.iloc[-1]
    n_years = len(portfolio_values) / 252  # Trading days per year
    
    annualized_return = (final_value / initial_value) ** (1 / n_years) - 1
    return annualized_return * 100  # Convert to percentage
```

**Interpretation**: Higher is better. Enables comparison between strategies with different durations.

### Periodic Returns

Returns broken down by time periods, such as daily, monthly, and yearly.

```python
def calculate_periodic_returns(portfolio_values):
    """Calculate daily, monthly, and yearly returns."""
    daily_returns = portfolio_values.pct_change().dropna()
    
    # Resample to monthly and yearly
    monthly_returns = (daily_returns + 1).resample('M').prod() - 1
    yearly_returns = (daily_returns + 1).resample('Y').prod() - 1
    
    return {
        'daily': daily_returns,
        'monthly': monthly_returns,
        'yearly': yearly_returns
    }
```

**Interpretation**: Helps identify performance consistency and seasonality patterns.

## Risk Metrics

### Volatility (Standard Deviation)

Measures the dispersion of returns, indicating the strategy's stability.

```python
def calculate_volatility(returns, annualized=True):
    """Calculate return volatility."""
    volatility = returns.std()
    
    if annualized:
        volatility *= np.sqrt(252)  # Annualized (252 trading days)
    
    return volatility * 100  # Convert to percentage
```

**Interpretation**: Lower is generally better. High volatility indicates large swings in portfolio value.

### Maximum Drawdown

The maximum peak-to-trough decline in portfolio value, representing the worst-case historical loss.

```python
def calculate_max_drawdown(portfolio_values):
    """Calculate maximum drawdown."""
    peak = portfolio_values.expanding().max()
    drawdown = ((portfolio_values / peak) - 1) * 100
    max_drawdown = drawdown.min()
    return abs(max_drawdown)  # Return as positive value
```

**Interpretation**: Lower is better. A max drawdown of 20% means the strategy experienced a 20% decline from its peak at some point.

### Drawdown Duration

The length of time the strategy spends in drawdowns.

```python
def calculate_drawdown_duration(portfolio_values):
    """Calculate drawdown durations."""
    peak = portfolio_values.expanding().max()
    drawdown = (portfolio_values / peak) - 1
    
    # Find drawdown periods
    in_drawdown = drawdown < 0
    
    # Calculate durations
    drawdown_durations = []
    current_duration = 0
    
    for is_drawdown in in_drawdown:
        if is_drawdown:
            current_duration += 1
        elif current_duration > 0:
            drawdown_durations.append(current_duration)
            current_duration = 0
    
    # Add final duration if in drawdown at end
    if current_duration > 0:
        drawdown_durations.append(current_duration)
    
    return {
        'max_duration': max(drawdown_durations) if drawdown_durations else 0,
        'avg_duration': np.mean(drawdown_durations) if drawdown_durations else 0,
        'all_durations': drawdown_durations
    }
```

**Interpretation**: Shorter durations are better. Long recovery periods may indicate poor risk management.

### Value at Risk (VaR)

The maximum expected loss within a specific confidence level over a defined period.

```python
def calculate_value_at_risk(returns, confidence=0.95):
    """Calculate Value at Risk."""
    return -np.percentile(returns, 100 * (1 - confidence)) * 100
```

**Interpretation**: Lower is better. A 95% VaR of 2% means there's a 95% probability that the strategy won't lose more than 2% in a single day.

### Conditional Value at Risk (CVaR)

Also known as Expected Shortfall, measures the expected loss in the worst scenarios beyond the VaR threshold.

```python
def calculate_conditional_var(returns, confidence=0.95):
    """Calculate Conditional Value at Risk (Expected Shortfall)."""
    var_cutoff = np.percentile(returns, 100 * (1 - confidence))
    cvar = -returns[returns <= var_cutoff].mean() * 100
    return cvar
```

**Interpretation**: Lower is better. CVaR is always higher than VaR and provides a better estimate of tail risks.

## Risk-Adjusted Metrics

### Sharpe Ratio

Measures excess return per unit of risk, using standard deviation as the risk measure.

```python
def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """Calculate Sharpe Ratio."""
    excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
    sharpe = excess_returns.mean() / excess_returns.std()
    
    # Annualize
    sharpe *= np.sqrt(252)
    
    return sharpe
```

**Interpretation**: Higher is better. A Sharpe ratio above 1.0 is considered acceptable, above 2.0 is very good, and above 3.0 is excellent.

### Sortino Ratio

Similar to Sharpe ratio but uses only downside deviation, focusing on harmful volatility.

```python
def calculate_sortino_ratio(returns, risk_free_rate=0.0, target_return=0.0):
    """Calculate Sortino Ratio."""
    excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
    
    # Calculate downside deviation
    negative_returns = returns[returns < target_return]
    downside_deviation = np.sqrt(np.mean(negative_returns**2))
    
    sortino = 0 if downside_deviation == 0 else excess_returns.mean() / downside_deviation
    
    # Annualize
    sortino *= np.sqrt(252)
    
    return sortino
```

**Interpretation**: Higher is better. The Sortino ratio improves upon the Sharpe ratio by focusing only on harmful volatility.

### Calmar Ratio

Measures return relative to maximum drawdown, providing insight into recovery capability.

```python
def calculate_calmar_ratio(portfolio_values, annualized_return):
    """Calculate Calmar Ratio."""
    max_drawdown = calculate_max_drawdown(portfolio_values) / 100  # Convert to decimal
    calmar = 0 if max_drawdown == 0 else annualized_return / 100 / max_drawdown
    return calmar
```

**Interpretation**: Higher is better. A Calmar ratio above 3.0 is generally considered excellent.

### Omega Ratio

Probability-weighted ratio of gains versus losses for a given threshold.

```python
def calculate_omega_ratio(returns, threshold=0.0):
    """Calculate Omega Ratio."""
    gains = returns[returns >= threshold] - threshold
    losses = threshold - returns[returns < threshold]
    
    omega = 0 if losses.sum() == 0 else gains.sum() / losses.sum()
    return omega
```

**Interpretation**: Higher is better. An Omega ratio greater than 1.0 indicates more gains than losses relative to the threshold.

## Trade Metrics

### Win Rate

The percentage of trades that result in a profit.

```python
def calculate_win_rate(trades):
    """Calculate win rate."""
    if not trades or len(trades) == 0:
        return 0
    
    winning_trades = sum(1 for trade in trades if trade['profit'] > 0)
    return (winning_trades / len(trades)) * 100
```

**Interpretation**: Higher is better, but must be considered alongside average profit/loss per trade.

### Profit Factor

The ratio of gross profits to gross losses.

```python
def calculate_profit_factor(trades):
    """Calculate profit factor."""
    if not trades or len(trades) == 0:
        return 0
    
    gross_profit = sum(trade['profit'] for trade in trades if trade['profit'] > 0)
    gross_loss = abs(sum(trade['profit'] for trade in trades if trade['profit'] < 0))
    
    return gross_profit / gross_loss if gross_loss > 0 else float('inf')
```

**Interpretation**: Higher is better. A profit factor above 1.5 is generally considered good, and above 2.0 is excellent.

### Average Trade

The average profit or loss per trade.

```python
def calculate_average_trade(trades):
    """Calculate average profit/loss per trade."""
    if not trades or len(trades) == 0:
        return 0
    
    total_profit = sum(trade['profit'] for trade in trades)
    return total_profit / len(trades)
```

**Interpretation**: Higher is better. A positive average indicates profitability over many trades.

### Largest Win and Loss

The magnitude of the most significant individual winning and losing trades.

```python
def calculate_largest_trades(trades):
    """Calculate largest win and loss."""
    if not trades or len(trades) == 0:
        return {'largest_win': 0, 'largest_loss': 0}
    
    winning_trades = [trade['profit'] for trade in trades if trade['profit'] > 0]
    losing_trades = [trade['profit'] for trade in trades if trade['profit'] < 0]
    
    largest_win = max(winning_trades) if winning_trades else 0
    largest_loss = min(losing_trades) if losing_trades else 0
    
    return {'largest_win': largest_win, 'largest_loss': largest_loss}
```

**Interpretation**: A large difference between the largest win and loss may indicate poor risk management.

### Average Holding Period

The average duration of positions.

```python
def calculate_average_holding(trades):
    """Calculate average holding period in days."""
    if not trades or len(trades) == 0:
        return 0
    
    holding_periods = [(trade['exit_date'] - trade['entry_date']).days for trade in trades]
    return np.mean(holding_periods)
```

**Interpretation**: Varies by strategy type. Shorter isn't always better - depends on the strategy's design.

## Statistical Metrics

### Return Distribution Statistics

Statistical properties of the return distribution, helping assess normality and behavior.

```python
def calculate_return_statistics(returns):
    """Calculate return distribution statistics."""
    stats = {
        'mean': returns.mean() * 100,
        'median': returns.median() * 100,
        'std_dev': returns.std() * 100,
        'skewness': returns.skew(),
        'kurtosis': returns.kurt(),
        'min': returns.min() * 100,
        'max': returns.max() * 100
    }
    return stats
```

**Interpretation**: Positive skew and moderate kurtosis are generally preferable for trading strategies.

### Autocorrelation

Measures the correlation between returns and their lagged values, indicating return predictability.

```python
def calculate_autocorrelation(returns, lag=1):
    """Calculate autocorrelation of returns."""
    return returns.autocorr(lag=lag)
```

**Interpretation**: Values significantly different from zero may indicate serial dependence in returns.

### Hurst Exponent

Measures the long-term memory of a time series, indicating whether returns are trending, mean-reverting, or random.

```python
def calculate_hurst_exponent(returns):
    """Calculate Hurst exponent of returns."""
    lags = range(2, 100)
    tau = [np.sqrt(np.std(np.subtract(returns.values[lag:], returns.values[:-lag]))) for lag in lags]
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0] / 2.0
```

**Interpretation**:
- H < 0.5: Mean-reverting series
- H = 0.5: Random walk (Brownian motion)
- H > 0.5: Trending series

## Market-Relative Metrics

### Beta

Measures the strategy's systematic risk relative to a benchmark.

```python
def calculate_beta(returns, benchmark_returns):
    """Calculate beta against benchmark."""
    cov = np.cov(returns, benchmark_returns)[0, 1]
    var = np.var(benchmark_returns)
    return cov / var if var != 0 else 0
```

**Interpretation**: A beta of 1.0 indicates the strategy moves with the market. Less than 1.0 suggests lower volatility than the market, while greater than 1.0 suggests higher volatility.

### Alpha (Jensen's Alpha)

Measures the excess return over what would be predicted by the capital asset pricing model (CAPM).

```python
def calculate_alpha(returns, benchmark_returns, risk_free_rate=0.0):
    """Calculate Jensen's Alpha."""
    # Convert annual risk-free rate to daily
    daily_rf = risk_free_rate / 252
    
    # Calculate beta
    beta = calculate_beta(returns, benchmark_returns)
    
    # Calculate alpha (annualized)
    alpha = returns.mean() - daily_rf - beta * (benchmark_returns.mean() - daily_rf)
    alpha = alpha * 252 * 100  # Annualize and convert to percentage
    
    return alpha
```

**Interpretation**: Higher is better. A positive alpha indicates the strategy outperformed the benchmark on a risk-adjusted basis.

### Information Ratio

Measures the risk-adjusted excess return relative to a benchmark.

```python
def calculate_information_ratio(returns, benchmark_returns):
    """Calculate Information Ratio."""
    active_returns = returns - benchmark_returns
    tracking_error = active_returns.std() * np.sqrt(252)  # Annualized
    
    information_ratio = (active_returns.mean() * 252) / tracking_error if tracking_error != 0 else 0
    return information_ratio
```

**Interpretation**: Higher is better. An information ratio above 1.0 is generally considered good, and above 1.5 is excellent.

### Capture Ratios

Upside and downside capture ratios measure how the strategy performs in up and down markets, respectively.

```python
def calculate_capture_ratios(returns, benchmark_returns):
    """Calculate upside and downside capture ratios."""
    # Identify up and down market days
    up_market = benchmark_returns > 0
    down_market = benchmark_returns < 0
    
    # Calculate capture ratios
    upside_capture = (returns[up_market].mean() / benchmark_returns[up_market].mean()) * 100
    downside_capture = (returns[down_market].mean() / benchmark_returns[down_market].mean()) * 100
    
    return {'upside_capture': upside_capture, 'downside_capture': downside_capture}
```

**Interpretation**: 
- **Upside Capture**: Higher is better. A ratio above 100% means the strategy outperformed the benchmark in up markets.
- **Downside Capture**: Lower is better. A ratio below 100% means the strategy outperformed the benchmark in down markets (lost less).

## Strategy-Specific Metrics

### Strategy Exposure

The percentage of time the strategy is exposed to the market.

```python
def calculate_exposure(positions):
    """Calculate market exposure."""
    total_days = len(positions)
    days_exposed = sum(1 for pos in positions if pos != 0)
    return (days_exposed / total_days) * 100
```

**Interpretation**: Depends on strategy type. Lower exposure might indicate more selectivity but also potentially missed opportunities.

### Profit per Unit of Risk

The amount of profit generated per unit of risk taken.

```python
def calculate_profit_per_risk(trades):
    """Calculate profit per unit of risk."""
    if not trades or len(trades) == 0:
        return 0
    
    total_profit = sum(trade['profit'] for trade in trades)
    total_risk = sum(trade['risk'] for trade in trades)
    
    return total_profit / total_risk if total_risk > 0 else 0
```

**Interpretation**: Higher is better. Indicates how efficiently the strategy converts risk into profit.

### Recovery Factor

The ratio of total return to maximum drawdown, indicating recovery capability.

```python
def calculate_recovery_factor(portfolio_values):
    """Calculate recovery factor."""
    total_return = calculate_total_return(portfolio_values) / 100  # Convert to decimal
    max_drawdown = calculate_max_drawdown(portfolio_values) / 100  # Convert to decimal
    
    return total_return / max_drawdown if max_drawdown > 0 else float('inf')
```

**Interpretation**: Higher is better. A recovery factor above 2.0 is generally considered good.

## Performance Visualization

Instinct AI provides comprehensive visualization tools for analyzing strategy performance:

### Equity Curve

```python
def plot_equity_curve(portfolio_values, benchmark_values=None):
    """Plot equity curve with optional benchmark."""
    plt.figure(figsize=(12, 6))
    plt.plot(portfolio_values, label='Strategy')
    
    if benchmark_values is not None:
        plt.plot(benchmark_values, label='Benchmark', alpha=0.7)
    
    plt.title('Equity Curve')
    plt.xlabel('Date')
    plt.ylabel('Portfolio Value')
    plt.legend()
    plt.grid(True, alpha=0.3)
    return plt.gcf()
```

### Drawdown Chart

```python
def plot_drawdowns(portfolio_values):
    """Plot drawdown chart."""
    peak = portfolio_values.expanding().max()
    drawdown = ((portfolio_values / peak) - 1) * 100
    
    plt.figure(figsize=(12, 6))
    plt.fill_between(drawdown.index, drawdown, 0, color='red', alpha=0.3)
    plt.plot(drawdown, color='red', alpha=0.7)
    plt.title('Drawdown (%)')
    plt.xlabel('Date')
    plt.ylabel('Drawdown %')
    plt.grid(True, alpha=0.3)
    return plt.gcf()
```

### Return Distribution

```python
def plot_return_distribution(returns):
    """Plot return distribution with normal curve for comparison."""
    plt.figure(figsize=(12, 6))
    
    # Plot histogram
    sns.histplot(returns * 100, kde=True, stat='density', label='Returns')
    
    # Plot normal distribution for comparison
    x = np.linspace(min(returns * 100), max(returns * 100), 100)
    mean = returns.mean() * 100
    std = returns.std() * 100
    pdf = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-(x - mean)**2 / (2 * std**2))
    plt.plot(x, pdf, 'r--', label='Normal Distribution')
    
    plt.title('Return Distribution')
    plt.xlabel('Return (%)')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid(True, alpha=0.3)
    return plt.gcf()
```

### Performance Tear Sheet

Instinct AI can generate comprehensive performance tear sheets that combine multiple metrics and visualizations into a single report:

```python
def create_tear_sheet(portfolio_values, returns, trades=None, benchmark_values=None):
    """Generate comprehensive performance tear sheet."""
    # Implementation in utils/performance.py
```

## Using Performance Metrics in the System

### Accessing Metrics

```python
from utils.performance import calculate_performance_metrics

# Get performance metrics for backtest results
metrics = calculate_performance_metrics(results['portfolio'])

# Access specific metrics
print(f"Total Return: {metrics['total_return']:.2f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Maximum Drawdown: {metrics['max_drawdown']:.2f}%")
```

### Custom Metrics

You can define and use custom performance metrics:

```python
def custom_gain_to_pain_ratio(returns):
    """Calculate gain-to-pain ratio: sum of returns / sum of absolute losses."""
    gains = sum(ret for ret in returns if ret > 0)
    pains = sum(abs(ret) for ret in returns if ret < 0)
    return gains / pains if pains > 0 else float('inf')

# Add to performance metrics
def calculate_extended_metrics(returns):
    standard_metrics = calculate_performance_metrics(returns)
    standard_metrics['gain_to_pain'] = custom_gain_to_pain_ratio(returns)
    return standard_metrics
```

### Strategy Comparison

Instinct AI includes tools for comparing multiple strategies:

```python
from utils.performance import compare_strategies

# Compare strategies
comparison = compare_strategies([
    {'name': 'ML Ensemble', 'results': ml_results},
    {'name': 'Statistical Arbitrage', 'results': stat_arb_results},
    {'name': 'LSTM Strategy', 'results': lstm_results}
])

# Visualize comparison
from utils.visualization import plot_strategy_comparison
plot_strategy_comparison(comparison)
```

## Best Practices for Performance Evaluation

1. **Use Multiple Metrics**: Don't rely on a single metric for strategy evaluation.
2. **Consider Risk**: Always balance return metrics with risk metrics.
3. **Compare to Benchmarks**: Evaluate strategy performance relative to appropriate benchmarks.
4. **Test Across Regimes**: Analyze performance across different market regimes.
5. **Consider Implementation Costs**: Account for transaction costs, slippage, and market impact.
6. **Out-of-Sample Testing**: Validate strategy performance on out-of-sample data.
7. **Statistical Significance**: Assess whether performance is statistically significant or due to chance.

## Conclusion

Comprehensive performance evaluation is essential for developing robust trading strategies. Instinct AI provides a wide range of metrics and visualization tools to help traders understand the strengths and weaknesses of their strategies across different market conditions. 