# Adaptive Meta-Strategy Framework

## Overview

The Adaptive Meta-Strategy is a sophisticated trading framework that combines multiple strategies with dynamic allocation based on detected market regimes. This meta-strategy adapts to changing market conditions by leveraging Bayesian changepoint detection and hierarchical risk parity allocation to create a robust, adaptive portfolio of strategies.

## Key Features

- **Regime-Adaptive Allocation**: Automatically adjusts strategy weights based on market regimes
- **Dynamic Risk Management**: Adapts risk exposure based on market conditions and strategy performance
- **Portfolio of Strategies**: Combines multiple strategies with optimal risk-balanced allocation
- **Performance Tracking**: Monitors strategy performance across different market regimes
- **Robust Visualization**: Comprehensive visualization of allocations, performance, and regimes

## Scientific Foundation

The Adaptive Meta-Strategy combines several scientific approaches:

### 1. Bayesian Changepoint Detection

Market regimes are detected using Bayesian Online Changepoint Detection (BOCD) based on the seminal work of Adams & MacKay (2007). This algorithm provides:

- Probabilistic detection of structural breaks in time series data
- Dynamic adaptation to changing market conditions
- Robust handling of financial market non-stationarity
- Online learning capability for real-time applications

### 2. Hierarchical Risk Parity (HRP)

Strategy allocation uses Hierarchical Risk Parity, developed by Marcos Lopez de Prado, which offers:

- Robustness to estimation errors common in traditional portfolio optimization
- Superior diversification through hierarchical clustering of strategy correlation
- No matrix inversion, avoiding numerical instabilities
- Better out-of-sample performance compared to traditional allocation methods

### 3. Adaptive Risk Management

Risk is dynamically adjusted based on:

- Current market regime (reducing exposure in bear markets)
- Kelly Criterion for optimal position sizing
- Drawdown control to preserve capital
- Volatility targeting for consistent risk exposure

## Components and Architecture

The Adaptive Meta-Strategy consists of several integrated components:

```
┌─────────────────────┐
│                     │
│  Market Data Feed   │
│                     │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────┐     ┌────────────────────┐
│                      │     │                    │
│  Bayesian Regime     │────▶│  Regime History    │
│  Detection           │     │  & Classification  │
│                      │     │                    │
└──────────┬───────────┘     └────────────────────┘
           │
           ▼
┌──────────────────────┐     ┌────────────────────┐
│                      │     │                    │
│  Strategy Signal     │────▶│  Performance       │
│  Generation          │     │  Tracking          │
│                      │     │                    │
└──────────┬───────────┘     └────────┬───────────┘
           │                          │
           ▼                          ▼
┌──────────────────────┐     ┌────────────────────┐
│                      │     │                    │
│  Regime-Based        │◀────┤  Regime-Specific   │
│  Allocation          │     │  Performance Data  │
│                      │     │                    │
└──────────┬───────────┘     └────────────────────┘
           │
           ▼
┌──────────────────────┐
│                      │
│  Risk-Adjusted       │
│  Position Sizing     │
│                      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│                      │
│  Final Portfolio     │
│  Positions           │
│                      │
└──────────────────────┘
```

## Usage

### Initialization

```python
from strategies.adaptive_meta_strategy import create_adaptive_meta_strategy

# Initialize with existing strategies
strategies = {
    "trend_following": trend_strategy,
    "mean_reversion": reversion_strategy,
    "ml_ensemble": ml_strategy
}

# Create the meta-strategy
meta_strategy = create_adaptive_meta_strategy(
    strategies=strategies,
    base_allocations={"trend_following": 0.4, "mean_reversion": 0.3, "ml_ensemble": 0.3},
    target_volatility=0.15,
    allocation_method='hrp',
    max_allocation=0.5,
    save_dir='results/adaptive_strategy'
)
```

### Updating with Market Data

```python
# Get the latest market data
market_data = data_loader.load_latest_data(symbols, timeframe)

# Update the meta-strategy and get positions
positions = meta_strategy.update(market_data)

# positions is a dictionary of {symbol: position_size} that can be used for trading
```

### Visualization

```python
# Visualize strategy allocations over time
fig = meta_strategy.visualize_allocations()
fig.savefig('allocations.png')

# Visualize performance by regime
fig = meta_strategy.visualize_regime_performance()
fig.savefig('regime_performance.png')

# Get performance summary
summary = meta_strategy.get_performance_summary()
print(f"Current Regime: {summary['current_regime']}")
print(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
```

### Saving and Loading State

```python
# Save strategy state
meta_strategy.save('models/meta_strategy_state.json')

# Load state later
meta_strategy.load('models/meta_strategy_state.json')
```

## Configuration Parameters

### Main Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `strategies` | Dictionary of strategy instances | Required |
| `base_allocations` | Initial allocation weights | Equal weight |
| `lookback_window` | Window for performance tracking | 60 days |
| `regime_memory` | Days to remember regime-specific performance | 252 days |
| `allocation_method` | Method for portfolio allocation | 'hrp' |
| `max_allocation` | Maximum allocation to any strategy | 0.5 (50%) |
| `min_allocation` | Minimum allocation to any strategy | 0.0 (0%) |
| `target_volatility` | Target annualized volatility | 0.15 (15%) |
| `adaptation_speed` | How quickly to adapt allocations | 0.1 (10%) |

### Risk Management Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max_drawdown` | Maximum allowed drawdown before reducing exposure | 0.25 (25%) |
| `risk_scaling` | Whether to scale by risk | True |
| `use_kelly` | Whether to use Kelly criterion | True |
| `kelly_fraction` | Conservative Kelly fraction | 0.5 (Half-Kelly) |

## Market Regime Classification

The strategy automatically classifies market regimes based on return, volatility, and other statistical properties:

| Regime Type | Description | Allocation Tendency |
|-------------|-------------|---------------------|
| Bull-Stable | Strong uptrend with low volatility | Higher allocations, especially to trend strategies |
| Bull-Volatile | Strong uptrend with high volatility | Moderate allocations, balanced approach |
| Bear-Stable | Downtrend with low volatility | Reduced allocations, favor mean-reversion |
| Bear-Volatile | Downtrend with high volatility | Minimal allocations, maximum risk reduction |
| Choppy | Sideways market with noise | Reduced allocations, favor mean-reversion |
| Neutral | No clear regime identified | Default allocations |

## Performance Tracking

The strategy tracks performance at multiple levels:

1. **Strategy-Level Performance**: Individual strategy returns and metrics
2. **Regime-Specific Performance**: How each strategy performs in different regimes
3. **Meta-Strategy Performance**: Overall combined strategy performance
4. **Allocation Evolution**: How allocations change over time

## Example Results

### Performance by Market Regime

Here's an example of how performance might differ across market regimes:

| Strategy | Bull-Stable | Bull-Volatile | Bear-Stable | Bear-Volatile |
|----------|-------------|---------------|-------------|---------------|
| Trend Following | ++++ | ++ | -- | ---- |
| Mean Reversion | + | ++ | +++ | - |
| ML Ensemble | +++ | ++ | + | -- |
| Adaptive Meta | ++++ | +++ | ++ | - |

### Allocation Evolution

As market regimes change, allocations adapt automatically:

- **Bull Markets**: Higher allocation to trend-following and momentum strategies
- **Bear Markets**: Shift toward mean-reversion and defensive strategies
- **Volatile Periods**: Overall risk reduction and increased diversification
- **Stable Periods**: Concentration in highest-performing strategies

## Implementation Notes

### Dependencies

- NumPy, Pandas: Data manipulation and processing
- Matplotlib: Visualization
- SciPy: Scientific calculations

### Performance Considerations

- Regime detection runs every 20 days or when significant changes are detected
- Strategy allocations smooth changes via adaptation_speed parameter
- State can be saved and loaded for persistence across sessions

## Conclusion

The Adaptive Meta-Strategy provides a scientific, robust framework for combining multiple trading strategies with regime awareness. By dynamically adjusting allocations based on market conditions and strategy performance, it achieves superior risk-adjusted returns compared to static allocation approaches.

This framework represents the cutting edge of quantitative finance, leveraging advanced mathematical techniques in Bayesian inference, hierarchical clustering, and adaptive risk management. 