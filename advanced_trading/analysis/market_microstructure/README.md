# Market Microstructure Analysis

This module provides advanced market microstructure analysis tools for the Instinct AI trading system. Market microstructure analysis examines the details of trading processes, focusing on how order flow, liquidity provision, and market mechanics affect price formation and execution quality.

## Overview

Market microstructure analysis is essential for:
- Optimizing order execution
- Detecting market conditions
- Predicting short-term price movements
- Estimating transaction costs
- Identifying trading opportunities
- Understanding market liquidity

## Components

### OrderBookAnalyzer

The `OrderBookAnalyzer` provides real-time analysis of order book data, focusing on:

- **Order Book Imbalance**: Analyzes the imbalance between buy and sell sides at different price levels
- **Depth Analysis**: Measures liquidity availability at various price distances
- **Buy/Sell Pressure**: Detects order flow pressure from market participants
- **Pattern Recognition**: Identifies common order book patterns that precede price movements
- **Price Movement Prediction**: Generates short-term price movement predictions
- **Market Impact Estimation**: Estimates the market impact of orders of different sizes

```python
from advanced_trading.analysis.market_microstructure import OrderBookAnalyzer

# Initialize analyzer
analyzer = OrderBookAnalyzer(
    update_frequency_ms=100,  # Update frequency in milliseconds
    max_book_depth=10,        # Maximum depth to analyze
    history_window=100        # Number of historical snapshots to keep
)

# Process order book update
results = analyzer.process_order_book(
    symbol='BTC/USD',
    order_book={
        'bids': [[price, quantity], ...],  # Bids as [price, quantity] pairs
        'asks': [[price, quantity], ...],  # Asks as [price, quantity] pairs
        'timestamp': 1638360000000         # Timestamp in milliseconds
    }
)

# Get optimal order parameters
order_params = analyzer.get_optimal_order_params(
    symbol='BTC/USD',
    side='buy',
    size=1.0,
    urgency=0.7  # Higher values = more aggressive execution
)
```

### OrderFlowAnalyzer

The `OrderFlowAnalyzer` examines trade data to identify patterns and generate signals:

- **Trade Pattern Recognition**: Identifies sequences and clusters in trade data
- **Volume Analysis**: Analyzes trading volume patterns and imbalances
- **Large Trader Detection**: Identifies the presence of large market participants
- **Signal Generation**: Creates trading signals based on order flow patterns
- **Transaction Size Analysis**: Examines the distribution of transaction sizes
- **Time-of-Day Patterns**: Identifies recurring patterns based on time

```python
from advanced_trading.analysis.market_microstructure import OrderFlowAnalyzer

# Initialize analyzer
analyzer = OrderFlowAnalyzer(
    history_window=1000,         # Number of trades to keep in history
    time_window_seconds=300,     # Analysis time window in seconds
    large_trade_threshold=0.95   # Percentile threshold for large trades
)

# Process trade
results = analyzer.process_trade(
    symbol='BTC/USD',
    trade={
        'price': 50000.0,        # Trade price
        'amount': 1.5,           # Trade amount/quantity
        'side': 'buy',           # Trade side ('buy' or 'sell')
        'timestamp': 1638360000000  # Timestamp in milliseconds
    }
)

# Get volume profile
profile = analyzer.get_volume_profile(
    symbol='BTC/USD',
    num_bins=10                  # Number of price bins
)
```

### LiquidityProfiler

The `LiquidityProfiler` focuses on market liquidity analysis:

- **Spread Analysis**: Examines bid-ask spreads and their dynamics
- **Depth Profiling**: Analyzes available liquidity at different price levels
- **Market Impact Estimation**: Predicts price impact for different order sizes
- **Liquidity Scoring**: Provides composite scores for market liquidity
- **Resilience Measurement**: Evaluates how quickly markets recover from shocks
- **Liquidity Trend Tracking**: Monitors changes in liquidity conditions over time

```python
from advanced_trading.analysis.market_microstructure import LiquidityProfiler

# Initialize profiler
profiler = LiquidityProfiler(
    history_window=1000,           # Number of snapshots to keep
    depth_levels=10,               # Number of price levels to analyze
    impact_size_tiers=[0.001, 0.005, 0.01, 0.05, 0.1]  # Order sizes for impact calculation
)

# Process order book
profile = profiler.process_order_book(
    symbol='BTC/USD',
    order_book={
        'bids': [[price, quantity], ...],  # Bids as [price, quantity] pairs
        'asks': [[price, quantity], ...],  # Asks as [price, quantity] pairs
        'timestamp': 1638360000000         # Timestamp in milliseconds
    }
)

# Process trade
profiler.process_trade(
    symbol='BTC/USD',
    trade={
        'price': 50000.0,          # Trade price
        'amount': 1.5,             # Trade amount/quantity
        'side': 'buy',             # Trade side
        'timestamp': 1638360000000 # Timestamp in milliseconds
    }
)

# Get liquidity score components
components = profiler.get_liquidity_score_components('BTC/USD')
```

### Impact Models

The module provides several market impact models to estimate the price effect of executing orders:

- **Linear Impact Model**: Implements the classic square-root law for market impact.
- **Nonlinear Impact Model**: Separates impact into permanent and temporary components.
- **ML-based Impact Model**: Uses machine learning to predict impact based on market conditions.

```python
from advanced_trading.analysis.market_microstructure.models import (
    LinearImpactModel, NonlinearImpactModel, MLImpactModel
)

# Create linear impact model
linear_model = LinearImpactModel(name="Square-Root Impact Model", alpha=0.5)

# Create market state for prediction
market_state = {
    'volatility': 0.02,  # 2% daily volatility
    'adv': 1000,         # Average daily volume
    'spread': 0.001,     # Bid-ask spread (10 bps)
    'depth': 50          # Market depth
}

# Predict impact for different order sizes
sizes = [0.01, 0.05, 0.1]  # Order sizes as fraction of ADV
for size in sizes:
    impact = linear_model.predict_impact(size, market_state, 'buy')
    print(f"Size: {size:.2f}, Impact: {impact:.6f}")

# Train model with historical data
training_result = linear_model.train(trade_data, market_data)
```

### Order Book Predictors

The module includes time series prediction models for order book dynamics:

- **VAR Order Book Predictor**: Uses Vector Autoregression for linear prediction of order book metrics.
- **LSTM Order Book Predictor**: Uses LSTM networks for nonlinear prediction of order book metrics.

```python
from advanced_trading.analysis.market_microstructure.models import (
    VAR_OrderBookPredictor, LSTM_OrderBookPredictor
)

# Create VAR predictor
var_model = VAR_OrderBookPredictor(
    name="VAR Order Book Predictor",
    prediction_horizon=5,  # Predict 5 steps ahead
    lag_order=3            # Use 3 lags
)

# Train the model with historical data
var_model.train(order_book_metrics)

# Make predictions using recent data
predictions = var_model.predict(recent_data)
```

### Visualization Tools

The module provides visualization tools for market microstructure analysis:

- **OrderBookVisualizer**: Visualizes order book depth, imbalance, and dynamics.
- **LiquidityVisualizer**: Visualizes bid-ask spread, market depth, and liquidity metrics.
- **OrderFlowVisualizer**: Visualizes trade flow, volume profile, and trade clustering.
- **ImpactVisualizer**: Visualizes market impact curves, components, and model comparisons.

```python
from advanced_trading.analysis.market_microstructure.visualization import (
    OrderBookVisualizer, LiquidityVisualizer, 
    OrderFlowVisualizer, ImpactVisualizer
)

# Create order book visualizer
ob_viz = OrderBookVisualizer()

# Plot order book snapshot
fig, ax = ob_viz.plot_order_book_snapshot(
    order_book=order_book,
    levels=10,
    show_cumulative=True
)

# Create impact visualizer
impact_viz = ImpactVisualizer()

# Plot impact curve
fig, ax = impact_viz.plot_impact_curve(
    sizes=sizes,
    impacts=impacts,
    model_name="Square-Root Impact Model",
    fit_curve=True
)
```

## Examples

The `examples` directory contains sample code demonstrating the use of these components:

- `basic_usage.py`: Simple example of how to use all three analyzers
- `models/example.py`: Example of impact models and order book prediction
- `visualization_example.py`: Example of visualizing market microstructure data
- `strategy_integration.py`: Example of integrating microstructure analysis into a trading strategy

## Integration Points

The market microstructure analysis components are designed to integrate with:

- **Execution System**: To optimize order execution parameters
- **Trading Strategies**: To generate entry/exit signals based on microstructure
- **Risk Management**: To assess execution risk and market conditions
- **Backtesting**: To simulate market microstructure conditions
- **Dashboard**: To visualize real-time market microstructure metrics

## Performance Considerations

These components are designed for high-performance applications:

- The `OrderBookAnalyzer` can process thousands of order book updates per second
- Memory usage is optimized through circular buffers for historical data
- Computation-intensive operations use NumPy for vectorized calculations
- Components can be scaled horizontally across multiple instruments

## Future Enhancements

Planned enhancements include:

- Additional machine learning models for order book prediction
- Enhanced visualization tools for market microstructure
- Integration with reinforcement learning for adaptive execution
- Cross-exchange microstructure analysis
- Market regime detection based on microstructure features 