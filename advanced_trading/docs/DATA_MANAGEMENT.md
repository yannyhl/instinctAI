# Instinct AI Data Management System

This document outlines the data acquisition, processing, storage, and management capabilities of the Instinct AI trading system.

## Overview

The Instinct AI data management system provides a robust foundation for accessing, processing, and storing market data from multiple sources. It is designed to ensure data quality, performance, and reliability for all trading strategies.

```
┌───────────────────┐     ┌────────────────┐     ┌────────────────┐
│                   │     │                │     │                │
│  Data Acquisition │────▶│  Processing    │────▶│  Storage       │
│                   │     │                │     │                │
└───────────────────┘     └────────────────┘     └────────────────┘
         │                        │                      │
         │                        │                      │
         ▼                        ▼                      ▼
┌───────────────────┐     ┌────────────────┐     ┌────────────────┐
│                   │     │                │     │                │
│  Exchange APIs    │     │  Technical     │     │  Caching       │
│                   │     │  Indicators    │     │  System        │
└───────────────────┘     └────────────────┘     └────────────────┘
```

## Key Components

### 1. Data Loader

Responsible for acquiring data from various sources:

- **Exchange Connectors**: Direct API connections to cryptocurrency exchanges
- **Data Providers**: Integration with specialized data providers
- **Local Files**: Loading data from CSV, JSON, or other file formats
- **Distributed Storage**: Accessing data from shared storage systems

**Location**: `advanced_trading/data/data_loader.py`

### 2. Data Manager

Orchestrates the entire data pipeline:

- **Data Synchronization**: Ensures consistent timestamps across data sources
- **Quality Control**: Validates and cleans incoming data
- **Feature Generation**: Calculates technical indicators and derived features
- **Data Format Conversion**: Transforms data between different representations
- **Caching Strategy**: Implements intelligent caching for performance

**Location**: `advanced_trading/data/data_manager.py`

### 3. Technical Indicators

Provides a comprehensive library of technical analysis indicators:

- **Trend Indicators**: Moving averages, MACD, Parabolic SAR
- **Momentum Indicators**: RSI, Stochastic, CCI
- **Volatility Indicators**: Bollinger Bands, ATR, Standard Deviation
- **Volume Indicators**: OBV, Volume Profile, A/D Line
- **Custom Indicators**: Proprietary indicators and combinations

**Location**: `advanced_trading/utils/technical_indicators.py`

### 4. Market Regimes

Detects and classifies market conditions:

- **Regime Classification**: Identify trending, ranging, or volatile markets
- **Anomaly Detection**: Recognize unusual market behavior
- **Correlation Analysis**: Track relationships between assets
- **Volatility Clustering**: Identify periods of high/low volatility

**Location**: `advanced_trading/utils/regime_detection.py`

### 5. Cache System

Optimizes data access with a multi-layered caching approach:

- **Memory Cache**: Fast access to frequently used data
- **Disk Cache**: Persistent storage for larger datasets
- **Distributed Cache**: Optional Redis-based caching for clustered deployments
- **TTL Management**: Time-based cache invalidation strategies

**Location**: *Integrated across multiple components*

## Data Flow

### 1. Acquisition

Market data is acquired through the following process:

```python
# Initialize data loader
data_loader = DataLoader(
    cache_dir="data/cache",
    primary_source="binance"
)

# Load data for a symbol
btc_data = data_loader.load_data(
    symbol="BTC/USDT",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-02-01"
)
```

The system will:
1. Check if data exists in local cache
2. If not cached or expired, fetch from primary source
3. If primary source fails, try secondary sources
4. Validate and standardize the retrieved data
5. Store in cache for future use

### 2. Processing

Raw market data is processed to add features and indicators:

```python
# Initialize data manager
data_manager = DataManager()

# Process raw data
processed_data = data_manager.add_technical_indicators(
    btc_data,
    indicators=["rsi", "macd", "bollinger_bands"]
)
```

The processing pipeline includes:
1. Data cleaning and anomaly detection
2. Missing value handling
3. Calculation of technical indicators
4. Feature normalization
5. Multi-timeframe aggregation

### 3. Advanced Features

Beyond basic processing, the system supports advanced data operations:

```python
# Generate volume profile
volume_profile = data_manager.create_volume_profile(btc_data)

# Detect market regime
regime = RegimeClassifier().fit_predict(btc_data)

# Calculate correlation matrix
correlation = data_manager.calculate_correlation_matrix(
    symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"]
)
```

## Data Sources

### Supported Exchanges

The system integrates with multiple cryptocurrency exchanges:

| Exchange | API Version | Data Types | Rate Limits |
|----------|-------------|------------|------------|
| Binance | V3 | OHLCV, Orderbook, Trades | 1200 req/min |
| Coinbase | V3 | OHLCV, Orderbook, Trades | 300 req/min |
| Kraken | V2 | OHLCV, Orderbook, Trades | 150 req/min |

### Configuration

Exchange connections are configured in `config.py`:

```python
DATA_CONFIG = {
    "sources": ["binance", "coinbase", "kraken"],
    "primary": "binance",
    "cache_data": True,
    "cache_dir": DATA_DIR / "cache",
    "api_keys": {
        "binance": os.environ.get("BINANCE_API_KEY", ""),
        "binance_secret": os.environ.get("BINANCE_SECRET_KEY", ""),
        "coinbase": os.environ.get("COINBASE_API_KEY", ""),
        "coinbase_secret": os.environ.get("COINBASE_SECRET_KEY", ""),
        "kraken": os.environ.get("KRAKEN_API_KEY", ""),
        "kraken_secret": os.environ.get("KRAKEN_SECRET_KEY", "")
    }
}
```

## Performance Optimization

> **Current Development Focus**

The data management system employs several optimization techniques:

### Multi-level Caching

The system implements tiered caching:

```python
# Memory cache for high-frequency access
@memory_cache(ttl=300)  # 5 minutes
def get_recent_data(symbol, timeframe):
    # Implementation
    
# Disk cache for persistence
@disk_cache(ttl=86400)  # 1 day
def get_historical_data(symbol, timeframe, start_date, end_date):
    # Implementation

# Redis cache for distributed setups
@redis_cache(ttl=3600)  # 1 hour
def get_market_overview(symbols):
    # Implementation
```

### Selective Data Loading

Efficient data loading based on actual needs:

```python
# Load only necessary columns
data = data_loader.load_data(
    symbol="BTC/USDT",
    columns=["timestamp", "close", "volume"],
    timeframe="1h"
)

# Load with custom timeframe aggregation
data = data_loader.load_multi_timeframe(
    symbol="BTC/USDT",
    timeframes=["1h", "4h", "1d"]
)
```

### Parallel Processing

Utilizes parallel computation for heavy operations:

```python
# Parallel data loading for multiple symbols
data = data_loader.load_multiple_symbols(
    symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    start_date="2023-01-01",
    end_date="2023-02-01",
    parallel=True,
    num_workers=4
)

# Parallel indicator calculation
data = data_manager.add_technical_indicators(
    data,
    indicators=["rsi", "macd", "bollinger_bands"],
    parallel=True
)
```

### GPU Acceleration

For systems with GPU support:

```python
# Initialize with GPU acceleration
data_manager = DataManager(use_gpu=True)

# GPU-accelerated feature calculation
features = data_manager.compute_features(data, use_gpu=True)
```

## Data Validation and Quality Control

The system implements rigorous data validation:

### Integrity Checks

```python
# Validate OHLCV data integrity
is_valid = data_manager.validate_ohlcv(data)

# Identify and handle anomalies
cleaned_data = data_manager.remove_anomalies(data)

# Handle missing values
complete_data = data_manager.handle_missing_values(data, method="interpolate")
```

### Consistency Verification

```python
# Ensure proper timestamp alignment
aligned_data = data_manager.align_timestamps(data)

# Verify price consistency
is_consistent = data_manager.verify_price_consistency(data)
```

## Technical Indicators

The system provides a comprehensive set of technical indicators:

### Trend Indicators

```python
# Simple Moving Average
data['sma_20'] = calculate_sma(data['close'], window=20)

# Exponential Moving Average
data['ema_20'] = calculate_ema(data['close'], window=20)

# Moving Average Convergence Divergence
data['macd'], data['macd_signal'], data['macd_hist'] = calculate_macd(data['close'])
```

### Volatility Indicators

```python
# Bollinger Bands
data['bb_upper'], data['bb_middle'], data['bb_lower'] = calculate_bollinger_bands(
    data['close'], window=20, num_std=2.0
)

# Average True Range
data['atr'] = calculate_atr(data[['high', 'low', 'close']], period=14)
```

### Momentum Indicators

```python
# Relative Strength Index
data['rsi'] = calculate_rsi(data['close'], period=14)

# Stochastic Oscillator
data['stoch_k'], data['stoch_d'] = calculate_stochastic(
    data[['high', 'low', 'close']], k_period=14, d_period=3
)
```

### Custom Indicators

The system allows creating custom indicators:

```python
def custom_strength_index(data, window1=14, window2=28):
    """Custom strength index combining multiple indicators"""
    rsi1 = calculate_rsi(data['close'], period=window1)
    rsi2 = calculate_rsi(data['close'], period=window2)
    return (rsi1 + rsi2) / 2

# Add to indicators registry
register_indicator('custom_strength_index', custom_strength_index)
```

## Volume Analysis

The system provides specialized volume analysis:

### Volume Profile

```python
from models.volume_profile import VolumeProfile

# Create volume profile analyzer
vp = VolumeProfile(num_bins=50)

# Analyze volume distribution
profile = vp.analyze(data)

# Get key price levels
support_resistance = vp.get_support_resistance_levels(num_levels=3)
```

### Liquidity Analysis

```python
# Analyze market liquidity
liquidity = data_manager.analyze_liquidity(
    symbol="BTC/USDT",
    timeframe="1h",
    window=24  # hours
)

# Get order book imbalance
imbalance = data_loader.get_orderbook_imbalance("BTC/USDT")
```

## Market Regime Detection

The system can identify different market conditions:

```python
from utils.regime_detection import RegimeClassifier

# Initialize regime classifier
classifier = RegimeClassifier(method='hmm', n_regimes=3)

# Fit and predict regimes
regimes = classifier.fit_predict(data)

# Get regime characteristics
regime_stats = classifier.analyze_regimes(data, regimes)

# Plot regimes
classifier.plot_regimes(data, regimes)
```

Detected regimes include:
- **Trending Up**: Strong buying pressure and momentum
- **Trending Down**: Strong selling pressure and downward momentum
- **Range-Bound**: Sideways movement with defined support/resistance
- **High Volatility**: Large price swings with high volume
- **Low Volatility**: Tight consolidation with declining volume

## Data Storage

### Cache Structure

The data caching system follows a structured approach:

```
data/cache/
├── binance/
│   ├── BTC_USDT/
│   │   ├── 1h_20230101_20230201.parquet
│   │   ├── 4h_20230101_20230201.parquet
│   │   └── 1d_20230101_20230201.parquet
│   └── ETH_USDT/
│       └── ...
├── coinbase/
│   └── ...
└── metadata/
    └── last_update.json
```

### Storage Formats

The system supports multiple storage formats:

- **Parquet**: Default format for OHLCV data (efficient columnar storage)
- **CSV**: Alternative format for simpler data exchange
- **JSON**: Used for configuration and metadata
- **SQLite**: Used for relational data and query support
- **Redis**: Used for distributed caching (optional)

### Data Retention

By default, the system implements the following retention policies:

- **High-frequency data** (1m, 5m): 30 days
- **Intraday data** (1h, 4h): 90 days
- **Daily data** (1d): 5 years
- **Metadata and derived features**: Variable based on usage

These policies can be configured in `config.py`.

## Using the Data System

### Basic Usage

```python
from data.data_manager import DataManager

# Initialize
data_manager = DataManager()

# Load and prepare data
data = data_manager.load_and_prepare_data(
    symbol="BTC/USDT",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-02-01"
)

# Access specific data
recent_data = data_manager.get_most_recent_data("BTC/USDT", n_periods=20)
```

### Advanced Usage

```python
# Multi-timeframe analysis
data_dict = data_manager.fetch_multi_timeframe(
    symbols=["BTC/USDT", "ETH/USDT"],
    timeframes=["1h", "4h", "1d"],
    start_date="2023-01-01",
    end_date="2023-02-01"
)

# Custom indicator pipeline
data = data_manager.load_data("BTC/USDT", "1h")
data = data_manager.add_technical_indicators(data, [
    {"name": "sma", "params": {"window": 20}},
    {"name": "rsi", "params": {"period": 14}},
    {"name": "bollinger_bands", "params": {"window": 20, "num_std": 2.0}}
])

# Feature engineering
features = data_manager.engineer_features(data, feature_set="ml_strategy")
```

## Performance Considerations

To optimize data management performance:

1. **Use Appropriate Timeframes**
   - Match data granularity to your strategy needs
   - Avoid loading 1-minute data for daily strategies

2. **Leverage Caching**
   - Minimize redundant API calls
   - Pre-compute common indicators

3. **Batch Operations**
   - Load multiple symbols together
   - Calculate multiple indicators in one pass

4. **Use Efficient Formats**
   - Parquet for disk storage
   - NumPy arrays for in-memory processing

5. **Apply Filtering Early**
   - Filter by date range at the data source
   - Select only needed columns

## Troubleshooting

### Common Issues

1. **API Rate Limiting**
   - Problem: Exceeding exchange API rate limits
   - Solution: Enable `respect_rate_limits=True` in the DataLoader

2. **Missing Data**
   - Problem: Gaps in historical data
   - Solution: Use `handle_missing_values()` with appropriate method

3. **Memory Usage**
   - Problem: High memory consumption with large datasets
   - Solution: Enable chunked processing with `use_chunks=True`

4. **Data Synchronization**
   - Problem: Timestamp misalignment between exchanges
   - Solution: Use `synchronize_data()` for consistent timestamps

## Future Enhancements

Planned improvements to the data management system:

1. **Real-time Streaming**
   - WebSocket connections for live data
   - Event-driven architecture for updates

2. **Enhanced Caching**
   - Redis integration for distributed caching
   - Smarter cache invalidation strategies

3. **Data Compression**
   - Optimized storage formats
   - Smart downsampling for historical data

4. **Additional Data Sources**
   - On-chain data integration
   - Sentiment analysis from news and social media

5. **Feature Store**
   - Centralized repository for computed features
   - Version control for feature sets 