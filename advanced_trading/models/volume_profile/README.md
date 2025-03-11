# Volume Profile Module

The Volume Profile module provides tools for analyzing the distribution of trading volume across different price levels in financial markets. These tools are essential for understanding market structure, identifying support and resistance levels, and optimizing trade execution.

## Overview

This module implements several volume-based analysis techniques specifically tailored for financial markets:

1. **Volume Profile Analysis**: Analyzes the distribution of trading volume across price levels to identify key areas of interest such as the Point of Control (POC) and Value Area.

2. **Liquidity Analysis** (Coming Soon): Tools for estimating market liquidity and potential price impact of orders.

3. **Volume-synchronized Probability of Informed Trading (VPIN)** (Coming Soon): A metric for measuring order flow toxicity and detecting potential informed trading.

## Features

- **Volume Profile Analysis**: Identify key price levels based on volume distribution.
- **Support and Resistance Detection**: Automatically identify potential support and resistance levels.
- **Volume Delta Analysis**: Compare buy and sell volume across price levels.
- **Feature Extraction**: Extract features from volume profiles for use in machine learning models.
- **Visualization Tools**: Comprehensive visualization capabilities for volume analysis.
- **Integration with ML Ensemble**: Seamless integration with the ML Ensemble framework.

## Components

### VolumeProfile

The `VolumeProfile` class analyzes the distribution of trading volume across price levels. Key features include:

- Calculation of Point of Control (POC) - the price level with the highest volume
- Identification of Value Area - the price range containing 70% of volume
- Detection of high and low volume nodes
- Support and resistance level identification
- Volume delta analysis (buy volume - sell volume)
- Feature extraction for machine learning models
- Comprehensive visualization tools

### LiquidityModel (Coming Soon)

The `LiquidityModel` class will provide tools for estimating market liquidity and potential price impact of orders.

### VPIN (Coming Soon)

The `VPIN` class will implement the Volume-synchronized Probability of Informed Trading metric for measuring order flow toxicity.

## Usage Examples

### Basic Volume Profile Analysis

```python
from models.volume_profile.volume_profile import VolumeProfile

# Create volume profile
profile = VolumeProfile(
    price_data=price_series,
    volume_data=volume_series,
    n_bins=50
)

# Get key price levels
poc = profile.get_point_of_control()
value_area = profile.get_value_area()

# Plot volume profile
profile.plot_profile(
    figsize=(10, 6),
    color='blue',
    show_poc=True,
    show_value_area=True,
    horizontal=True,
    title='Volume Profile'
)
```

### Identifying Support and Resistance Levels

```python
# Identify support and resistance levels
levels = profile.identify_support_resistance(volume_threshold=0.7)

print("Support levels:")
for level in levels['support']:
    print(f"  - {level:.2f}")

print("Resistance levels:")
for level in levels['resistance']:
    print(f"  - {level:.2f}")
```

### Volume Delta Analysis

```python
# Calculate volume delta
delta_profile = profile.calculate_volume_delta(buy_volume, sell_volume)

# Plot volume delta
profile.plot_volume_delta(
    delta_profile=delta_profile,
    figsize=(10, 6),
    title='Volume Delta Profile (Buy - Sell)'
)
```

### Feature Extraction for Machine Learning

```python
# Extract features from volume profile
features = profile.get_volume_profile_features()

# Use features in machine learning models
from models.ml_ensemble.ensemble import MLEnsemble

ensemble = MLEnsemble()
ensemble.add_features(features)
ensemble.train(X_train, y_train)
```

### Integration with Price Charts

```python
# Plot volume profile with price
profile.plot_profile_with_price(
    price_data=price_series,
    figsize=(12, 8),
    profile_width=0.3,
    profile_color='blue',
    price_color='black',
    show_poc=True,
    show_value_area=True,
    title='Price with Volume Profile'
)
```

## Advanced Use Cases

- **Market Structure Analysis**: Understand the distribution of volume across price levels to identify key areas of interest.
- **Support and Resistance Identification**: Automatically identify potential support and resistance levels based on volume distribution.
- **Trade Execution Optimization**: Use volume profile analysis to optimize entry and exit points.
- **Liquidity Analysis**: Estimate market liquidity and potential price impact of orders.
- **Order Flow Analysis**: Detect potential informed trading and order flow toxicity.
- **Feature Engineering**: Extract features from volume profiles for use in machine learning models.

## References

- Steidlmayer, P. J., & Koy, K. (1986). Markets & Market Logic. Porcupine Press.
- Dalton, J., Jones, E. T., & Dalton, R. B. (1993). Mind over Markets: Power Trading with Market Generated Information. Traders Press.
- Easley, D., López de Prado, M. M., & O'Hara, M. (2012). Flow Toxicity and Liquidity in a High-frequency World. The Review of Financial Studies, 25(5), 1457-1493. 