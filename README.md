# Instinct AI Trading System

A comprehensive AI-powered trading system for cryptocurrencies with machine learning, advanced risk management, and adaptive strategies.

## System Architecture

The Instinct AI trading system consists of several integrated components:

### Core Components

1. **ML Ensemble Framework**
   - Ensemble machine learning models for market prediction
   - Dynamic model weighting based on regime performance
   - Feature importance tracking and optimization
   - Cross-validation and proper model evaluation

2. **Unified Data Pipeline**
   - Consistent API for multiple data sources (OHLCV, on-chain, sentiment)
   - Extensible provider architecture for easy integration of new data sources
   - Caching and data validation for reliable operation
   - Support for GPU acceleration and parallel processing

3. **AdaptiveMetaStrategy**
   - Combines multiple trading strategies with dynamic allocation
   - Adapts to changing market conditions through regime detection
   - Risk-weighted portfolio optimization
   - Performance monitoring and strategy rotation

4. **Walk-Forward Testing Framework**
   - Systematic out-of-sample testing to prevent overfitting
   - Regime-aware model evaluation
   - Feature importance analysis across market conditions
   - Parameter optimization and sensitivity analysis

5. **Risk Management**
   - Position sizing based on volatility and predicted edge
   - Dynamic stop-loss and take-profit management
   - Portfolio-level risk controls
   - Monte Carlo simulation for strategy robustness

## Key Features

- **Regime Awareness**: All components adapt to changing market regimes
- **Ensemble Learning**: Combines diverse models to improve robustness
- **Modular Design**: Easily extendable with new data sources or strategies
- **Proper Validation**: Walk-forward testing prevents overfitting
- **Performance Metrics**: Comprehensive analysis beyond simple returns
- **Alternative Data**: Ready for integration with on-chain and sentiment data

## Usage

### Running the ML Ensemble Example

```bash
python -m advanced_trading.examples.run_ml_ensemble --symbol BTC --timeframe 1h --start-date 2023-01-01
```

### Accessing Data Through the Unified Pipeline

```python
from advanced_trading.data.data_interface import get_data_interface

# Get the data interface
data = get_data_interface()

# Get OHLCV data
btc_data = data.get_ohlcv_data(
    symbol='BTC/USDT',
    timeframe='1h',
    start_date='2023-01-01',
    end_date='2023-03-01'
)

# Get combined data with on-chain metrics
combined_data = data.get_combined_data(
    symbol='BTC',
    timeframe='1d',
    include_onchain=True,
    start_date='2023-01-01',
    end_date='2023-03-01'
)
```

### Running Walk-Forward Analysis

```python
from advanced_trading.backtest.walk_forward import MLWalkForwardAnalysis
from advanced_trading.utils.bayesian_changepoint import detect_market_regimes

# Create walk-forward tester
wf = MLWalkForwardAnalysis(
    market_data=data,
    train_size=3000,  # 3000 periods (hours)
    test_size=720,    # 720 periods (1 month)
    step_size=720,    # Step 1 month at a time
    optimization_func=optimizer,
    feature_engineer=FeatureEngineer(),
    regime_detection_func=lambda x: detect_market_regimes(x, n_regimes=3),
    initial_capital=10000,
    commission=0.001
)

# Run walk-forward test
results = wf.run(
    strategy_factory=lambda **kwargs: AdaptiveMetaStrategy(**kwargs),
    verbose=True
)

# Plot results
wf.plot_results(title='Adaptive ML Strategy Walk-Forward Test')
```

## Directory Structure

```
instinct_ai/
├── advanced_trading/          # Advanced trading components
│   ├── backtest/              # Backtesting and walk-forward testing framework
│   ├── data/                  # Unified data pipeline
│   │   ├── providers/         # Data provider implementations
│   │   ├── cache/             # Data cache
│   │   └── market_monitor/    # Real-time market monitoring
│   ├── models/                # Machine learning models
│   │   └── ml_ensemble/       # ML ensemble framework
│   ├── strategies/            # Trading strategies
│   │   └── adaptive_meta_strategy.py  # Meta-strategy implementation
│   ├── utils/                 # Utility functions and helpers
│   │   ├── bayesian_changepoint.py    # Regime detection
│   │   └── data_downloader.py  # Simplified data access
│   ├── examples/              # Example scripts
│   └── tests/                 # Test scripts
├── trading/                   # Core trading components
│   ├── exchange.py            # Exchange connectivity
│   ├── portfolio.py           # Portfolio management
│   ├── risk_management.py     # Risk management
│   └── signal_processor.py    # Signal processing
└── dashboard/                 # UI components and visualization
```

## Development Status

The system is actively being developed with the following components ready:

- ✅ ML Ensemble Framework - Core implementation complete
- ✅ Unified Data Pipeline - Ready for OHLCV and prepared for on-chain data
- ✅ AdaptiveMetaStrategy - Core implementation complete
- ✅ Walk-Forward Testing - Framework implemented
- ⚠️ On-Chain Data - Framework ready, awaiting API keys
- ⚠️ Sentiment Analysis - Framework ready, awaiting implementation

## Roadmap

1. **Phase 1: Core Infrastructure (Completed)**
   - ML Ensemble Framework
   - Unified Data Pipeline
   - Walk-Forward Testing

2. **Phase 2: On-Chain Integration (In Progress)**
   - Integrate Glassnode, The TIE, and other on-chain data sources
   - Develop specialized on-chain features
   - Create on-chain specific models

3. **Phase 3: Advanced ML Models**
   - Add neural network models (LSTM, Transformer)
   - Implement reinforcement learning components
   - Develop hierarchical ensemble methods

4. **Phase 4: Production Deployment**
   - Exchange integration for live trading
   - Monitoring and alerting systems
   - Performance dashboard

## Dependencies

- Python 3.7+
- pandas, numpy, scikit-learn
- xgboost, lightgbm
- ccxt (for exchange connectivity)
- matplotlib, seaborn (for visualization)
- pyarrow (for data storage)
- talib (for technical indicators)
- Optional:
  - cudf/cupy (for GPU acceleration)
  - dask (for distributed computing)

## Contributing

To contribute to Instinct AI:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

This software is proprietary and confidential to Instinct AI. 