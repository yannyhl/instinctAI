# Enhanced Portfolio Allocation and Regime Detection

This document provides an overview of the advanced portfolio allocation and regime detection capabilities added to the Instinct AI trading system.

## 1. Hierarchical Risk Parity (HRP)

### Overview

Hierarchical Risk Parity is a modern portfolio optimization technique developed by Marcos Lopez de Prado that addresses key limitations of traditional approaches like Mean-Variance Optimization (MVO). It uses graph theory and machine learning concepts to create well-diversified portfolios without the need for inverting potentially ill-conditioned covariance matrices.

### Key Advantages

- **Robustness to Estimation Errors**: HRP is less sensitive to errors in expected returns and covariance matrices.
- **No Matrix Inversion**: Avoids numerical instability issues common in traditional optimization methods.
- **Hierarchical Clustering**: Accounts for the nested correlation structure of assets.
- **Performance**: Empirically shown to outperform traditional methods in out-of-sample tests.
- **No Assumptions**: Does not assume any particular distribution of returns.

### Implementation Details

Our implementation in `utils/portfolio_allocation.py` follows these steps:

1. **Distance Calculation**: Convert correlation matrix to a distance matrix
2. **Hierarchical Clustering**: Apply hierarchical clustering to group similar assets
3. **Quasi-Diagonalization**: Rearrange assets based on clustering
4. **Recursive Bisection**: Allocate weights by recursively dividing clusters
5. **Risk Balancing**: Balance risk contribution between clusters

### Usage Example

```python
from utils.portfolio_allocation import PortfolioAllocator

# Initialize with HRP method
allocator = PortfolioAllocator(method='hrp')

# Calculate allocations
weights = allocator.allocate(returns_df)

# Visualize the hierarchical clustering
fig = allocator.plot_hierarchical_clusters(returns_df)

# Visualize the allocations
fig = allocator.plot_allocations(weights)

# Calculate risk contribution of each asset
risk_contrib = allocator.calculate_allocation_risk_contribution(weights, returns_df)
```

## 2. Alternative Allocation Methods

In addition to HRP, we've implemented several other scientifically-proven allocation methods:

### Risk Parity

Allocates capital to equalize risk contribution from each asset, rather than capital allocation. This is particularly effective in creating diversified portfolios where no single asset dominates the risk profile.

```python
allocator = PortfolioAllocator(method='risk_parity')
weights = allocator.allocate(returns_df)
```

### Minimum Variance

Creates the portfolio with the lowest possible volatility, regardless of returns. This method is useful for conservative allocations or in high-volatility regimes.

```python
allocator = PortfolioAllocator(method='min_variance')
weights = allocator.allocate(returns_df)
```

### Sharpe Ratio Maximization

Optimizes the portfolio to achieve the highest possible Sharpe ratio, balancing returns and risk.

```python
allocator = PortfolioAllocator(method='sharpe_maximizing', risk_free_rate=0.02)
weights = allocator.allocate(returns_df)
```

### Target Volatility Scaling

Any allocation method can be scaled to target a specific volatility level, which is essential for risk management:

```python
allocator = PortfolioAllocator(method='hrp', target_volatility=0.10)
weights = allocator.allocate(returns_df)  # Will scale to 10% target volatility
```

## 3. Bayesian Changepoint Detection for Market Regimes

### Overview

We've implemented Bayesian Online Changepoint Detection (BOCD) based on the research by Adams & MacKay (2007) to identify shifts in market regimes. This allows strategies to adapt to changing market conditions, which is crucial for long-term performance.

### Scientific Foundation

The algorithm uses Bayesian inference to detect changes in the underlying probability distribution of financial time series. Unlike traditional methods that use fixed-size windows or arbitrary thresholds, this approach:

- Probabilistically identifies structural breaks in the data
- Adapts to different data distributions
- Provides uncertainty quantification
- Operates in an online fashion, making it suitable for real-time applications

### Implemented Models

Our implementation supports multiple statistical models:

- **Normal-Gamma**: For unknown mean and variance (default, best for financial returns)
- **Normal with Known Variance**: For situations where variance is known or estimated separately
- **Poisson**: For count data (e.g., number of trades)
- **Bernoulli**: For binary outcomes (e.g., up/down days)

### Regime Classification

We automatically classify detected regimes based on their statistical properties:

- **Mean Return**: Categorized as Bull, Choppy, or Bear
- **Volatility**: Categorized as Stable or Volatile
- **Higher Moments**: Additional labels for Skewed and Fat-Tailed regimes

This results in labels like "Bull-Stable", "Choppy-Bearish", "Bear-Volatile-Fat-Tailed", etc.

### Usage Example

```python
from utils.bayesian_changepoint import detect_market_regimes, plot_market_regimes

# Detect regimes in returns series
regimes = detect_market_regimes(returns_series, threshold=0.5)

# Visualize the regimes
fig = plot_market_regimes(returns_series)

# Access regime information
for segment in regimes['segments']:
    print(f"Regime: {segment['regime']}")
    print(f"  From: {segment['start_date']} to {segment['end_date']}")
    print(f"  Mean: {segment['mean']:.4f}, Volatility: {segment['volatility']:.4f}")
    print(f"  Sharpe: {segment['sharpe']:.2f}")
```

## 4. Regime-Based Strategy Adaptation

### Strategy Framework

We've developed a framework that allows strategies to adapt to detected market regimes. This can be done in several ways:

1. **Allocation Adjustment**: Modify asset allocations based on current regimes
2. **Parameter Adaptation**: Adjust strategy parameters based on regime characteristics
3. **Model Selection**: Use different models or sub-strategies for different regimes
4. **Risk Management**: Apply different risk controls in each regime

### Implementation Example

The example in `examples/regime_detection_example.py` demonstrates a regime-based allocation strategy:

```python
# Define allocation strategy for each regime type
regime_allocations = {
    # Bullish regimes: favor higher allocations
    "Bull-Volatile": 0.8,
    "Bull-Stable": 1.0,
    "Choppy-Bullish": 0.6,
    "Slow-Bullish": 0.8,
    
    # Bearish regimes: reduced allocations
    "Bear-Volatile": 0.0,    # Avoid volatile bear markets
    "Bear-Stable": 0.1,      # Small allocation in stable bear markets
    "Choppy-Bearish": 0.2,   # Small allocation in choppy bear markets
    "Slow-Bearish": 0.3,     # Moderate allocation in slow bear markets
    
    # Default for any other regime type
    "default": 0.5
}
```

### Performance Benefits

Empirical research shows that regime-adaptive strategies typically outperform static strategies by:

1. **Reducing Drawdowns**: By reducing exposure in high-risk regimes
2. **Improving Returns**: By increasing exposure in favorable regimes
3. **Enhancing Risk-Adjusted Metrics**: Leading to better Sharpe and Sortino ratios
4. **Increasing Robustness**: Making the strategy work across different market conditions

## 5. Integration with Existing System

The new portfolio allocation and regime detection capabilities are designed to integrate seamlessly with the existing Instinct AI system:

### Integration Points

1. **Strategy Manager**: The Strategy Manager can use regime information to adjust its allocation across strategies
2. **Risk Manager**: The Risk Management module can adapt position sizing based on detected regimes
3. **Portfolio Construction**: The system now supports multiple allocation methods for portfolio construction
4. **Dashboard**: Visualizations for regime detection and allocation can be integrated into the dashboard

### Configuration

In the system configuration (`config.py`), you can now specify:

```python
# Portfolio allocation configuration
ALLOCATION_CONFIG = {
    "method": "hrp",                # Allocation method
    "target_volatility": 0.15,      # Target annualized volatility
    "risk_free_rate": 0.02,         # Risk-free rate for optimization
    "rebalance_frequency": "1W"     # Rebalancing frequency
}

# Regime detection configuration
REGIME_CONFIG = {
    "enabled": True,
    "detection_method": "bayesian",
    "threshold": 0.5,
    "hazard_function": 0.01,        # Expected frequency of regime changes
    "adapt_allocation": True,       # Whether to adapt allocations based on regimes
    "adapt_parameters": True        # Whether to adapt strategy parameters based on regimes
}
```

## 6. Advanced Applications

### Ensemble Allocation

Combine multiple allocation methods for even greater robustness:

```python
methods = ['hrp', 'risk_parity', 'min_variance']
weights_dict = {}

for method in methods:
    allocator = PortfolioAllocator(method=method)
    weights_dict[method] = allocator.allocate(returns_df)

# Combine weights (equal-weighted ensemble)
ensemble_weights = {asset: sum(weights_dict[method][asset] for method in methods) / len(methods) 
                   for asset in weights_dict[methods[0]].keys()}
```

### Regime-Specific Models

Train different ML models for different market regimes:

```python
# Detect regimes
regimes = detect_market_regimes(returns)

# Train regime-specific models
regime_models = {}
for i, segment in enumerate(regimes['segments']):
    regime_type = segment['regime']
    start_idx, end_idx = segment['start_idx'], segment['end_idx']
    
    # Extract data for this regime
    regime_data = data.iloc[start_idx:end_idx+1]
    
    # Train model for this regime
    if regime_type not in regime_models:
        model = train_model_for_regime(regime_data, regime_type)
        regime_models[regime_type] = model
```

### Dynamic Risk Management

Adjust risk parameters based on detected regimes:

```python
def get_risk_parameters(current_regime):
    if "Bull" in current_regime:
        return {
            "stop_loss_pct": 0.05,
            "max_position_size": 0.2,
            "leverage": 1.0
        }
    elif "Bear" in current_regime:
        return {
            "stop_loss_pct": 0.03,
            "max_position_size": 0.1,
            "leverage": 0.5
        }
    else:  # Choppy or default
        return {
            "stop_loss_pct": 0.04,
            "max_position_size": 0.15,
            "leverage": 0.8
        }
```

## 7. Performance and Scaling

Both the HRP allocation and Bayesian changepoint detection algorithms are designed for efficiency:

- **HRP**: O(n² log n) complexity, much faster than traditional optimization for large portfolios
- **BOCD**: O(n) complexity for online processing, with constant memory requirements

For large portfolios or high-frequency applications, we've implemented optimizations:

1. **Parallel Processing**: For multiple assets or time series
2. **Caching**: For frequently accessed metrics and intermediate results
3. **Dimensionality Reduction**: For very large asset universes
4. **GPU Acceleration**: For matrix operations when available

## Conclusion

The addition of Hierarchical Risk Parity portfolio allocation and Bayesian changepoint detection for market regimes significantly enhances the capabilities of the Instinct AI trading system. These scientifically-proven methods address key challenges in quantitative trading:

1. **Robust Allocation**: HRP provides better diversification and performance than traditional methods
2. **Regime Adaptation**: BOCD allows strategies to adapt to changing market conditions
3. **Risk Management**: Both components contribute to better risk-adjusted performance

By combining these advanced techniques, the Instinct AI system can now deliver more stable performance across different market environments while maintaining the flexibility to adapt to changing conditions. 