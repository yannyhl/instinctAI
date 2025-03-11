# Data Preprocessing Module for Financial Time Series

## Overview

The Data Preprocessing Module provides a comprehensive set of functions for handling financial time series data, addressing common challenges in cleaning, transforming, engineering features, reducing dimensionality, and splitting data for training models. This module is designed to support the Instinct AI Trading System by providing robust and flexible preprocessing capabilities.

## Key Components

The module consists of several functional categories:

### 1. Data Cleaning Functions

- **`detect_outliers`**: Identify outliers in time series data using various statistical methods (Z-score, IQR, etc.)
- **`handle_outliers`**: Treat outliers by removing, clipping, or replacing with alternative values
- **`handle_missing_values`**: Fill missing values using interpolation, forward/backward filling, mean/median/mode, or custom values
- **`remove_duplicates`**: Identify and remove duplicate records from datasets
- **`resample_time_series`**: Change the frequency of time series data (e.g., daily to weekly) with customizable aggregation functions

### 2. Feature Transformation Functions

- **`normalize_data`**: Scale data using various methods (min-max, z-score, robust scaling, etc.)
- **`apply_scaler`**: Apply pre-fitted scalers to new data for consistent transformations
- **`apply_log_transform`**: Apply logarithmic transformation to handle skewed distributions
- **`apply_box_cox_transform`**: Apply Box-Cox power transformation for normalizing data
- **`apply_differencing`**: Create stationary time series using differencing of various orders

### 3. Feature Engineering Functions

- **`create_lag_features`**: Generate lagged versions of features for time series modeling
- **`create_rolling_features`**: Calculate rolling window statistics (mean, std, min, max, etc.)
- **`extract_date_features`**: Extract calendar features from datetime indices or columns

### 4. Dimensionality Reduction Functions

- **`apply_pca`**: Perform Principal Component Analysis with configurable parameters
- **`apply_tsne`**: Apply t-SNE for dimensionality reduction and visualization
- **`select_features_by_importance`**: Identify the most important features using statistical methods

### 5. Data Splitting Functions

- **`split_time_series_data`**: Split time series into train/validation/test sets with time-aware logic
- **`time_series_cross_validation`**: Create time series cross-validation folds with expanding or sliding windows
- **`time_series_bootstrap`**: Generate bootstrap samples for time series with block bootstrapping

## Usage Examples

For detailed examples of how to use each function in this module, please refer to the `data_preprocessing_example.py` file, which demonstrates practical applications with synthetic financial data.

Basic usage pattern:

```python
from advanced_trading.utils.data_preprocessing import handle_missing_values, create_lag_features, normalize_data

# Clean data
cleaned_data = handle_missing_values(data, method='interpolate')

# Create features
feature_data = create_lag_features(cleaned_data, lags=[1, 2, 3, 5])

# Normalize data
normalized_data, scalers = normalize_data(feature_data, method='minmax', return_scaler=True)
```

## Integration with Other Components

The Data Preprocessing Module is designed to integrate seamlessly with other components of the Instinct AI Trading System:

- **Models Framework**: Preprocessed data can be directly fed into ML models for training and prediction
- **Feature Engineering**: Works with technical indicators and other feature generators
- **Backtesting**: Provides properly split data for walk-forward testing and other evaluation methods
- **Strategy Framework**: Supports strategy development with clean, properly prepared data

## Implementation Details

- All functions are designed to work with both pandas DataFrame and Series objects
- Comprehensive error handling and validation is implemented throughout
- Detailed documentation and type hints are provided for all functions
- Functions follow a consistent pattern: they don't modify the input data by default (return new objects)

## Contribution Guidelines

When extending or modifying this module:

1. Maintain the same pattern and style as existing functions
2. Include comprehensive docstrings with Parameters and Returns sections
3. Add examples to the docstring
4. Implement proper error handling and input validation
5. Update the example file with demonstrations of new functionality
6. Update this README when adding new categories or significant features 