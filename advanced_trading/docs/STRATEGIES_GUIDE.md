# Instinct AI Trading Strategies Guide

This document provides detailed information about each trading strategy implemented within the Instinct AI system, including configurations, performance characteristics, and usage guidelines.

## Strategy Overview

The Instinct AI system supports multiple strategy types, each designed for specific market conditions and objectives:

| Strategy | Type | Market Conditions | Risk Profile | Timeframes |
|----------|------|-------------------|--------------|------------|
| ML Ensemble | Machine Learning | All | Medium | 1h, 4h, 1d |
| Advanced Crypto | Multi-factor | All | Adaptive | 5m, 15m, 1h, 4h |
| Statistical Arbitrage | Mean Reversion | Range-bound | Low | 5m, 15m, 1h |
| Funding Rate Arbitrage | Arbitrage | All | Very Low | 1h, 4h |
| LSTM Strategy | Deep Learning | Trending | Medium-High | 1h, 4h, 1d |

## 1. ML Ensemble Strategy

The ML Ensemble strategy combines multiple machine learning models to predict price movements with robust filtering and risk management.

### Architecture

```
           ┌─────────────┐
           │ Input Data  │
           └──────┬──────┘
                  │
        ┌─────────▼────────┐
        │ Feature Engineer │
        └─────────┬────────┘
                  │
     ┌────────────┼────────────┐
     │            │            │
┌────▼───┐   ┌────▼───┐   ┌────▼───┐
│Random  │   │Gradient│   │Logistic│
│Forest  │   │Boost   │   │Regress │
└────┬───┘   └────┬───┘   └────┬───┘
     │            │            │
     └────────────┼────────────┘
                  │
          ┌───────▼───────┐
          │  Ensemble     │
          │  Predictions  │
          └───────┬───────┘
                  │
          ┌───────▼───────┐
          │Signal Filtering│
          └───────┬───────┘
                  │
          ┌───────▼───────┐
          │Position Sizing │
          └───────────────┘
```

### Features

- **Model Ensemble**: Combines Random Forest, Gradient Boosting, and Logistic Regression
- **Feature Engineering**: 30+ technical features including price patterns, volatility metrics, and volume indicators
- **Adaptive Position Sizing**: Adjusts position size based on prediction confidence and market volatility
- **Time-Series Validation**: Uses walk-forward optimization to prevent overfitting
- **Signal Filtering**: Reduces noise through consensus and persistence filters

### Configuration Parameters

```python
STRATEGY_CONFIGS = {
    "ml_ensemble": {
        "lookback_window": 30,
        "prediction_horizon": 1,
        "training_window": 252 * 2,
        "retraining_frequency": 30,
        "threshold_buy": 0.65,
        "threshold_sell": 0.65,
        "symbols": TRADING_CONFIG["symbols"]
    }
}
```

### Performance Characteristics

- **Win Rate**: 53-58%
- **Average Profit/Loss Ratio**: 1.2-1.5
- **Typical Drawdown**: 10-15%
- **Best Market Regime**: Moderately trending with clear patterns
- **Worst Market Regime**: Choppy, low-volume environments

### Usage Guidelines

```python
from strategies.ml_strategy import MLEnsembleStrategy

# Initialize
strategy = MLEnsembleStrategy(
    config=STRATEGY_CONFIGS["ml_ensemble"],
    model_dir="models/ml_ensemble"
)

# Update with new data
signals = strategy.update(market_data)

# Get positions
current_positions = strategy.get_current_positions()
```

## 2. Advanced Crypto Strategy

This strategy integrates multiple factors including momentum, trend analysis, volatility, and on-chain metrics to create a comprehensive market approach.

### Strategy Components

- **Trend Detection**: Multiple timeframe trend analysis
- **Momentum Factors**: RSI, MACD, and custom momentum indicators
- **Volatility Adjustment**: Adapts to changing volatility regimes
- **Volume Analysis**: OBV, volume profile, and liquidity measures
- **Market Regimes**: Dynamically adjusts parameters based on detected market regime

### Configuration Parameters

```python
STRATEGY_CONFIGS = {
    "trend_following": {
        "short_window": 10,
        "medium_window": 20,
        "long_window": 50,
        "volatility_window": 20,
        "trend_threshold": 0.05,
        "symbols": TRADING_CONFIG["symbols"]
    }
}
```

### Regime Adaptations

| Market Regime | Strategy Adjustment |
|---------------|---------------------|
| Strong Trend | Increases trend following weight |
| Range-Bound | Increases mean reversion weight |
| High Volatility | Reduces position sizes |
| Low Volatility | Increases position sizes |
| Extreme Volatility | Activates defensive positioning |

### Risk Parameters

- **Dynamic Stop-Loss**: 3 * ATR (Average True Range)
- **Take-Profit**: Based on volatility and target R multiple
- **Max Drawdown Threshold**: 25%
- **Position Size**: 2% risk per trade, adjusted by volatility

### Usage Guidelines

```python
from strategies.advanced_crypto_strategy import AdvancedCryptoStrategy

# Initialize
strategy = AdvancedCryptoStrategy(context)

# Set up and initialize
strategy.initialize(context)

# Execute strategy
strategy.rebalance(context, data)
```

## 3. Statistical Arbitrage Strategy

This strategy identifies and trades cointegrated pairs of assets, exploiting temporary pricing inefficiencies while maintaining market neutrality.

### Strategy Logic

1. **Pair Selection**: Identifies cointegrated pairs with statistical tests
2. **Spread Calculation**: Calculates the spread using optimal hedge ratios
3. **Statistical Modeling**: Normalizes the spread and calculates z-scores
4. **Signal Generation**: Enters positions when z-score exceeds thresholds
5. **Risk Management**: Implements time-based and deviation-based stop losses

### Configuration Parameters

```python
STRATEGY_CONFIGS = {
    "stat_arb": {
        "pairs": [
            ("BTC/USD", "ETH/USD"),
            ("ETH/USD", "SOL/USD")
        ],
        "lookback_window": 30,
        "entry_zscore": 2.0,
        "exit_zscore": 0.5,
        "max_holding_period": 5,
        "coint_pvalue": 0.05
    }
}
```

### Performance Characteristics

- **Win Rate**: 65-75%
- **Average Profit/Loss Ratio**: 0.8-1.0
- **Typical Drawdown**: 5-10%
- **Best Market Regime**: Range-bound with high correlation
- **Worst Market Regime**: Trending markets with correlation breakdowns

### Usage Example

```python
from strategies.statistical_arbitrage import StatisticalArbitrageStrategy

# Initialize
strategy = StatisticalArbitrageStrategy(
    pairs=[("BTC/USDT", "ETH/USDT")],
    lookback_period=20,
    z_threshold=2.0,
    exit_z_threshold=0.5
)

# Run backtest
results = strategy.backtest(data, initial_capital=10000)
```

## 4. Funding Rate Arbitrage Strategy

This strategy exploits the funding rate differentials across exchanges for perpetual contracts, generating consistent low-risk returns.

### Strategy Logic

1. **Market Scanning**: Monitors funding rates across exchanges
2. **Opportunity Detection**: Identifies significant funding rate differentials
3. **Position Execution**: Enters opposing positions on different exchanges
4. **Fee Management**: Accounts for transaction costs and funding payments
5. **Exit Timing**: Closes positions based on funding payment schedule

### Configuration Parameters

```python
STRATEGY_CONFIGS = {
    "funding_arbitrage": {
        "min_funding_rate": 0.01,
        "max_position_size": 0.2,
        "exchanges": ["binance", "ftx", "bybit"],
        "symbols": ["BTC/USDT", "ETH/USDT"]
    }
}
```

### Performance Characteristics

- **Win Rate**: 80-90%
- **Average Profit/Loss Ratio**: 0.5-0.7
- **Typical Drawdown**: 2-5%
- **Best Market Regime**: Volatile markets with high funding rates
- **Worst Market Regime**: Low volatility with minimal funding rate differentials

### Usage Example

```python
from strategies.funding_arbitrage import FundingRateArbitrage

# Initialize
strategy = FundingRateArbitrage(
    symbols=["BTC/USDT", "ETH/USDT"],
    min_funding_rate=0.01,
    max_position_size=0.2,
    exchanges=["binance", "ftx", "bybit"]
)

# Generate signals
signals = strategy.generate_signals(funding_rates)
```

## 5. LSTM Strategy

This deep learning strategy uses Long Short-Term Memory networks to capture complex patterns and long-term dependencies in price data.

### Architecture

```
                 ┌──────────────┐
                 │  OHLCV Data  │
                 └───────┬──────┘
                         │
               ┌─────────▼──────────┐
               │  Feature Engineer  │
               └─────────┬──────────┘
                         │
               ┌─────────▼──────────┐
               │  Sequence Creator  │
               └─────────┬──────────┘
                         │
                 ┌───────▼───────┐
                 │  LSTM Model   │
                 └───────┬───────┘
                         │
                 ┌───────▼───────┐
                 │  Predictions  │
                 └───────┬───────┘
                         │
                 ┌───────▼───────┐
                 │Signal Generator│
                 └───────┬───────┘
                         │
                 ┌───────▼───────┐
                 │Position Sizing │
                 └───────────────┘
```

### Features

- **Deep Learning Model**: LSTM neural network for sequence modeling
- **Sequence Processing**: Converts price data into overlapping sequences
- **Multi-Step Prediction**: Forecasts multiple steps into the future
- **Volume Profile Integration**: Incorporates volume profile analysis
- **Confidence Scoring**: Adjusts position sizing based on prediction confidence

### Configuration Parameters

```python
LSTM_CONFIG = {
    "sequence_length": 60,
    "prediction_horizon": 5,
    "threshold_pct": 1.0,
    "use_volume_profile": True,
    "hidden_layers": 2,
    "neurons_per_layer": 64,
    "dropout_rate": 0.2
}
```

### Performance Characteristics

- **Win Rate**: 48-55%
- **Average Profit/Loss Ratio**: 1.5-2.0
- **Typical Drawdown**: 15-25%
- **Best Market Regime**: Strong trending markets
- **Worst Market Regime**: Choppy, sideways markets

### Usage Example

```python
from strategies.lstm_strategy import LSTMStrategy

# Initialize
strategy = LSTMStrategy(
    symbol="BTC/USDT",
    sequence_length=60,
    prediction_horizon=5
)

# Train the model
strategy.train(historical_data)

# Generate signals
signal = strategy.generate_signal(market_data)
```

## Strategy Comparison

| Strategy | Win Rate | Profit Factor | Max Drawdown | Trades/Month | Sharpe |
|----------|----------|--------------|--------------|--------------|--------|
| ML Ensemble | 55% | 1.3 | 15% | 15-25 | 1.2 |
| Advanced Crypto | 50% | 1.5 | 18% | 20-40 | 1.4 |
| Statistical Arbitrage | 70% | 1.1 | 8% | 40-60 | 1.8 |
| Funding Rate Arbitrage | 85% | 1.2 | 5% | 5-15 | 2.5 |
| LSTM Strategy | 52% | 1.7 | 22% | 8-12 | 1.1 |

## Multi-Strategy Approach

The Instinct AI system allows for combining multiple strategies to create a robust portfolio:

### Combining Strategies

1. **Diversification**: Uncorrelated return streams reduce overall portfolio risk
2. **Strategy Allocation**: Adjustable capital allocation between strategies
3. **Risk Parity**: Equal risk contribution across strategies
4. **Adaptive Allocation**: Dynamic adjustment based on recent performance

### Example Multi-Strategy Configuration

```python
MULTI_STRATEGY_CONFIG = {
    "strategies": [
        {"name": "ml_ensemble", "allocation": 0.3, "max_drawdown": 0.15},
        {"name": "stat_arb", "allocation": 0.3, "max_drawdown": 0.1},
        {"name": "funding_arbitrage", "allocation": 0.2, "max_drawdown": 0.05},
        {"name": "lstm", "allocation": 0.2, "max_drawdown": 0.15}
    ],
    "rebalance_frequency": "weekly",
    "adaptive_allocation": True,
    "performance_lookback": 30
}
```

## Strategy Development Guidelines

### Adding New Strategies

1. Create a new strategy class in `advanced_trading/strategies/`
2. Implement required interface methods:
   - `__init__`: Initialize strategy parameters
   - `update`: Process new data and generate signals
   - `get_current_positions`: Report current positions
3. Register the strategy in the Strategy Manager

### Best Practices

- **Separation of Concerns**: Keep signal generation separate from execution
- **Parameterization**: Make all thresholds and constants configurable
- **Documentation**: Include docstrings and performance characteristics
- **Testing**: Create unit tests and backtest comprehensively
- **Risk Management**: Include strategy-specific risk controls 