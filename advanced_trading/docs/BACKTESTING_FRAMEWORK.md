# Instinct AI Backtesting Framework

This document provides detailed information about the backtesting capabilities of the Instinct AI system, including methodology, features, and usage guides.

## Overview

The Instinct AI backtesting framework provides a comprehensive environment for testing trading strategies with accurate simulation of market conditions, transaction costs, and risk factors.

### Key Features

- **High-Performance Engine**: Parallel backtesting for multiple strategies, symbols, and timeframes
- **Realistic Simulation**: Accurate modeling of order execution, slippage, and fees
- **Comprehensive Metrics**: Detailed performance analysis and risk metrics
- **Multi-Asset Support**: Test across diverse cryptocurrency markets
- **Walk-Forward Testing**: Prevent overfitting with proper validation methodology
- **Monte Carlo Simulation**: Stress test strategies under varied conditions
- **Visualization**: Rich reporting and interactive charts

## Architecture

The backtesting framework consists of several integrated components:

```
┌───────────────────┐     ┌─────────────────┐     ┌───────────────────┐
│                   │     │                 │     │                   │
│  Data Management  │────▶│  Backtester     │────▶│  Performance      │
│                   │     │                 │     │  Analysis         │
└───────────────────┘     └─────────────────┘     └───────────────────┘
         │                        │                        │
         │                        │                        │
         ▼                        ▼                        ▼
┌───────────────────┐     ┌─────────────────┐     ┌───────────────────┐
│                   │     │                 │     │                   │
│  Strategy Objects │     │  Risk Manager   │     │  Visualization    │
│                   │     │                 │     │                   │
└───────────────────┘     └─────────────────┘     └───────────────────┘
```

## Getting Started

### Basic Backtest Example

```python
from backtest.parallel_backtester import ParallelBacktester
from strategies.ml_strategy import MLEnsembleStrategy

# Initialize backtester
backtester = ParallelBacktester(use_gpu=True, num_workers=4)

# Prepare data
data_bundle = backtester.prepare_data_bundle(
    symbols=["BTC/USDT", "ETH/USDT"],
    timeframes=["1h", "4h"],
    start_date="2022-01-01",
    end_date="2023-01-01"
)

# Configure strategy
strategy_params = {
    "lookback_window": 30,
    "prediction_horizon": 1,
    "threshold_buy": 0.65,
    "threshold_sell": 0.65
}

# Run single backtest
results = backtester.run_single_backtest(
    strategy_class=MLEnsembleStrategy,
    strategy_params=strategy_params,
    data_bundle=data_bundle,
    symbol="BTC/USDT",
    timeframe="4h",
    start_date="2022-01-01",
    end_date="2023-01-01",
    initial_capital=10000.0
)

# Display results
print(f"Total Return: {results['metrics']['total_return']:.2f}%")
print(f"Sharpe Ratio: {results['metrics']['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['metrics']['max_drawdown']:.2f}%")
```

### Running Multiple Backtests

```python
# Define strategies to test
strategies = [
    {
        "name": "ML Ensemble",
        "class": MLEnsembleStrategy,
        "params": {
            "lookback_window": 30,
            "prediction_horizon": 1
        }
    },
    {
        "name": "Stat Arb",
        "class": StatisticalArbitrageStrategy,
        "params": {
            "lookback_period": 20,
            "z_threshold": 2.0
        }
    }
]

# Run parallel backtests
all_results = backtester.run_parallel_backtests(
    strategies=strategies,
    symbols=["BTC/USDT", "ETH/USDT"],
    timeframes=["1h", "4h"],
    start_date="2022-01-01", 
    end_date="2023-01-01",
    initial_capital=10000.0
)

# Compare results
backtester._compare_strategies(all_results)
```

## Realistic Simulation

The backtesting engine simulates real-world trading conditions:

### Transaction Costs

- **Exchange Fees**: Configurable commission rates for each exchange
- **Slippage Model**: Price impact based on order size and market liquidity
- **Spread Costs**: Bid-ask spread simulation for accurate entry/exit prices
- **Gas Fees**: For on-chain transactions (where applicable)

### Market Conditions

- **Liquidity Modeling**: Realistic fill simulations based on volume
- **Gap Handling**: Proper management of price gaps between candles
- **Market Hours**: Respects market availability and trading hours
- **Order Types**: Market, limit, and stop orders with realistic execution

### Example Configuration

```python
BACKTEST_CONFIG = {
    "transaction_costs": {
        "commission": 0.001,  # 0.1% exchange fee
        "slippage": 0.0005,   # 0.05% slippage
        "spread_factor": 0.0002  # Average 0.02% spread
    },
    "execution": {
        "allow_partial_fills": True,
        "order_types": ["market", "limit"],
        "price_engine": "vwap",  # Use VWAP for price simulation
        "liquidity_model": "volume_based"
    }
}
```

## Performance Metrics

The framework calculates comprehensive performance metrics:

### Return Metrics

- **Total Return**: Overall percentage gain/loss
- **Annualized Return**: Compound annual growth rate (CAGR)
- **Daily/Monthly/Yearly Returns**: Returns broken down by period
- **Rolling Returns**: Returns over rolling periods

### Risk Metrics

- **Volatility**: Standard deviation of returns (annualized)
- **Sharpe Ratio**: Risk-adjusted return metric
- **Sortino Ratio**: Downside risk-adjusted return
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Drawdown Duration**: Time spent in drawdowns
- **Value at Risk (VaR)**: Statistical measure of potential loss
- **Conditional VaR (CVaR)**: Expected shortfall beyond VaR

### Trade Metrics

- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profits divided by gross losses
- **Average Trade**: Mean P&L per trade
- **Largest Win/Loss**: Magnitude of best and worst trades
- **Average Holding Period**: Mean duration of positions
- **Trading Frequency**: Number of trades per period

### Example Metrics Output

```python
{
    'total_return': 32.5,
    'annual_return': 15.2,
    'volatility': 18.7,
    'sharpe_ratio': 1.45,
    'sortino_ratio': 2.10,
    'max_drawdown': 12.3,
    'win_rate': 54.2,
    'profit_factor': 1.8,
    'avg_trade': 0.75,
    'max_trade': 4.2,
    'min_trade': -2.3,
    'avg_hold_time': 3.5,  # days
    'trade_count': 87
}
```

## Advanced Testing Methodologies

### Walk-Forward Analysis

The backtester supports walk-forward optimization to prevent overfitting:

```python
from utils.walk_forward import run_walk_forward_optimization

# Define parameter grid to test
param_grid = {
    "lookback_window": [20, 30, 40],
    "threshold_buy": [0.6, 0.65, 0.7],
    "threshold_sell": [0.6, 0.65, 0.7]
}

# Run walk-forward optimization
wf_results = run_walk_forward_optimization(
    backtester=backtester,
    strategy_class=MLEnsembleStrategy,
    param_grid=param_grid,
    symbols=["BTC/USDT"],
    timeframes=["4h"],
    start_date="2022-01-01",
    end_date="2023-01-01",
    train_window=60,  # days
    test_window=30,   # days
    step_size=15      # days
)
```

### Monte Carlo Simulation

Test strategy robustness by simulating multiple paths:

```python
from utils.monte_carlo import run_monte_carlo_simulation

mc_results = run_monte_carlo_simulation(
    backtest_results=results,
    num_simulations=1000,
    confidence_level=0.95
)

print(f"95% VaR: {mc_results['var']:.2f}%")
print(f"Expected Final Equity Range: {mc_results['final_equity_range']}")
```

### Stress Testing

Evaluate performance under extreme market conditions:

```python
from utils.risk_stress_testing import perform_stress_testing

stress_results = perform_stress_testing(
    strategy=strategy,
    data_dict=data_bundle,
    scenarios={
        "market_crash": {
            "price_shock": -0.30,
            "volatility_multiplier": 3.0,
            "duration_days": 10
        },
        "liquidity_crisis": {
            "price_shock": -0.10,
            "spread_multiplier": 5.0,
            "volume_multiplier": 0.3
        }
    }
)
```

## Visualization Tools

The framework provides multiple visualization options:

### Performance Charts

```python
from utils.performance import create_tear_sheet

# Generate comprehensive performance tearsheet
create_tear_sheet(results['portfolio'], save_path="results/tearsheet.png")
```

### Drawdown Analysis

```python
from utils.performance import plot_drawdowns

# Visualize drawdown periods
plot_drawdowns(results['portfolio'])
```

### Trade Analysis

```python
from utils.performance import plot_trade_analysis

# Analyze individual trades
plot_trade_analysis(results)
```

## Comparative Backtesting

Compare multiple strategies, parameters, or time periods:

```python
# Define test matrix
test_matrix = [
    {"strategy": "ml_ensemble", "symbol": "BTC/USDT", "timeframe": "4h"},
    {"strategy": "ml_ensemble", "symbol": "ETH/USDT", "timeframe": "4h"},
    {"strategy": "stat_arb", "symbol": "BTC/USDT,ETH/USDT", "timeframe": "1h"}
]

# Run comparative backtest
comparison = backtester.run_comparison(test_matrix)

# Visualize comparison
from utils.visualization import plot_strategy_comparison
plot_strategy_comparison(comparison)
```

## Regime Analysis

Analyze performance across different market regimes:

```python
from utils.regime_detection import RegimeClassifier
from utils.performance import analyze_performance_by_regime

# Detect market regimes
regime_classifier = RegimeClassifier()
regimes = regime_classifier.fit_predict(data_bundle["BTC/USDT"]["4h"])

# Analyze performance by regime
regime_performance = analyze_performance_by_regime(
    results['portfolio'],
    regimes
)

print("Performance by Market Regime:")
for regime, metrics in regime_performance.items():
    print(f"{regime}: Return: {metrics['return']:.2f}%, Sharpe: {metrics['sharpe']:.2f}")
```

## Backtesting Best Practices

For best results when using the backtesting framework:

1. **Prevent Lookahead Bias**
   - Ensure strategies only use data available at the time of decision
   - Properly align signals and execution timestamps

2. **Address Survivorship Bias**
   - Include delisted assets in historical data
   - Consider the universe of assets available at each point in time

3. **Realistic Position Sizing**
   - Account for available capital and leverage
   - Consider portfolio constraints and correlations

4. **Consistent Validation**
   - Always test on out-of-sample data
   - Use walk-forward testing for parameter optimization

5. **Transaction Cost Modeling**
   - Include all relevant costs (fees, slippage, spread)
   - Model liquidity limitations realistically

6. **Multiple Time Period Testing**
   - Test across bull markets, bear markets, and sideways periods
   - Verify performance in different volatility regimes

## Advanced Configuration

### Parallel Processing

```python
BACKTEST_CONFIG = {
    "parallel": True,
    "num_workers": 8,
    "use_gpu": True,
    "memory_limit": 0.8,  # Use 80% of available memory
    "precision": "float32"
}
```

### Custom Event Handling

```python
def custom_event_handler(event_type, event_data, context):
    """Custom event handler for backtest events"""
    if event_type == "stop_loss_triggered":
        # Custom logic for stop loss events
        context.risk_factor *= 0.9
        context.log_event("Reducing risk after stop loss")

# Add to backtest config
BACKTEST_CONFIG["event_handler"] = custom_event_handler
```

### Custom Metrics

```python
def custom_metrics(results):
    """Calculate custom performance metrics"""
    returns = results['portfolio']['returns']
    
    # Calculate custom metrics
    gain_to_pain = returns[returns > 0].sum() / abs(returns[returns < 0].sum())
    
    return {
        'gain_to_pain_ratio': gain_to_pain
    }

# Add to backtest config
BACKTEST_CONFIG["custom_metrics"] = custom_metrics
```

## Troubleshooting

### Common Issues

1. **Data Synchronization**
   - Problem: Misaligned timestamps between different data sources
   - Solution: Use `data_manager.synchronize_data()` to align data properly

2. **Memory Limitations**
   - Problem: Out of memory errors when backtesting large datasets
   - Solution: Enable chunking with `BACKTEST_CONFIG["chunked_processing"] = True`

3. **Unrealistic Performance**
   - Problem: Suspiciously high returns that don't match reality
   - Solutions: 
     - Check for lookahead bias
     - Verify transaction cost modeling
     - Ensure proper handling of trading limitations

4. **Slow Execution**
   - Problem: Backtests running too slowly
   - Solutions:
     - Enable parallel processing
     - Use GPU acceleration where available
     - Consider downsampling data for initial tests

## Conclusion

The Instinct AI backtesting framework provides a comprehensive, realistic, and high-performance environment for developing and validating trading strategies. By combining accurate market simulation with advanced analysis tools, it enables traders to confidently develop strategies with strong real-world performance. 