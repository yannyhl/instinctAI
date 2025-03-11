"""
Utility Functions for Transformer Models

This module provides utility functions for working with transformer models for financial time series,
including time feature generation, data normalization, and specialized masking functions.

Functions:
- create_time_features: Create time-based features from datetime index
- generate_square_subsequent_mask: Generate causal mask for self-attention
- time_series_train_test_split: Split time series data with proper temporal ordering
- normalize_time_series: Normalize time series data with various methods
"""

import torch
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict, Any, Union
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler


def create_time_features(dates: Union[pd.DatetimeIndex, np.ndarray, List]) -> np.ndarray:
    """Create time-based features from datetime index.
    
    This function creates various cyclical time features that capture temporal patterns,
    such as hour of day, day of week, day of month, month of year, etc. The features
    are encoded using sine and cosine transformations to preserve their cyclical nature.
    
    Args:
        dates: DatetimeIndex or array of datetime objects
        
    Returns:
        time_features: Array of time features with shape [len(dates), num_features]
    """
    if not isinstance(dates, pd.DatetimeIndex):
        dates = pd.DatetimeIndex(dates)
    
    # Extract time components
    hour = dates.hour
    day_of_week = dates.dayofweek
    day_of_month = dates.day - 1  # 0-based
    month = dates.month - 1  # 0-based
    
    # Create cyclical features using sine and cosine
    # This captures the cyclical nature of time features
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    
    day_of_week_sin = np.sin(2 * np.pi * day_of_week / 7)
    day_of_week_cos = np.cos(2 * np.pi * day_of_week / 7)
    
    day_of_month_sin = np.sin(2 * np.pi * day_of_month / 30)  # Approximation
    day_of_month_cos = np.cos(2 * np.pi * day_of_month / 30)
    
    month_sin = np.sin(2 * np.pi * month / 12)
    month_cos = np.cos(2 * np.pi * month / 12)
    
    # Combine features
    features = np.column_stack([
        hour_sin, hour_cos,
        day_of_week_sin, day_of_week_cos,
        day_of_month_sin, day_of_month_cos,
        month_sin, month_cos
    ])
    
    return features


def generate_square_subsequent_mask(sz: int, device: torch.device = torch.device('cpu')) -> torch.Tensor:
    """Generate a square causal mask for transformer self-attention.
    
    The mask ensures that predictions for a position can only attend to known elements,
    i.e., the current position and previous positions.
    
    Args:
        sz: Sequence length
        device: Torch device
        
    Returns:
        mask: Causal attention mask [sz, sz]
    """
    mask = (torch.triu(torch.ones(sz, sz, device=device)) == 1).transpose(0, 1)
    mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
    return mask


def time_series_train_test_split(
    data: Union[np.ndarray, pd.DataFrame],
    test_size: float = 0.2,
    val_size: Optional[float] = None,
    shuffle: bool = False,
    seed: Optional[int] = None
) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Split time series data into train and test sets with proper temporal ordering.
    
    Time series data requires special handling for train-test splits to preserve the
    temporal ordering. This function provides a convenient way to split time series
    data with optional validation set.
    
    Args:
        data: Time series data as array or DataFrame
        test_size: Proportion of data to use for testing
        val_size: Optional proportion of data to use for validation
        shuffle: Whether to shuffle the data (not recommended for time series)
        seed: Random seed for reproducibility
        
    Returns:
        train_data: Training data
        test_data: Test data
        val_data: Optional validation data
    """
    if isinstance(data, pd.DataFrame):
        data = data.values
    
    n = len(data)
    
    if shuffle:
        if seed is not None:
            np.random.seed(seed)
        idx = np.random.permutation(n)
        data = data[idx]
    
    if val_size is not None:
        # Calculate split indices
        test_idx = int(n * (1 - test_size))
        val_idx = int(n * (1 - test_size - val_size))
        
        # Split data
        train_data = data[:val_idx]
        val_data = data[val_idx:test_idx]
        test_data = data[test_idx:]
        
        return train_data, val_data, test_data
    else:
        # Calculate split index
        test_idx = int(n * (1 - test_size))
        
        # Split data
        train_data = data[:test_idx]
        test_data = data[test_idx:]
        
        return train_data, test_data


def normalize_time_series(
    data: Union[np.ndarray, pd.DataFrame],
    method: str = 'standard',
    fit_on: Optional[Union[np.ndarray, pd.DataFrame]] = None,
    return_scaler: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, Union[StandardScaler, MinMaxScaler, RobustScaler]]]:
    """Normalize time series data using various methods.
    
    This function provides several normalization methods for time series data,
    with the option to fit the scaler on a specific subset of the data (e.g., training set).
    
    Args:
        data: Time series data to normalize
        method: Normalization method ('standard', 'minmax', 'robust')
        fit_on: Optional data to fit the scaler on (e.g., training set)
        return_scaler: Whether to return the fitted scaler
        
    Returns:
        normalized_data: Normalized time series data
        scaler: Fitted scaler if return_scaler is True
    """
    # Convert DataFrame to numpy array
    if isinstance(data, pd.DataFrame):
        data = data.values
    
    if fit_on is not None and isinstance(fit_on, pd.DataFrame):
        fit_on = fit_on.values
    
    # Select scaler based on method
    if method == 'standard':
        scaler = StandardScaler()
    elif method == 'minmax':
        scaler = MinMaxScaler()
    elif method == 'robust':
        scaler = RobustScaler()
    else:
        raise ValueError(f"Unknown normalization method: {method}")
    
    # Ensure data is 2D
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    
    # Fit scaler on specified data or on input data
    if fit_on is not None:
        if fit_on.ndim == 1:
            fit_on = fit_on.reshape(-1, 1)
        scaler.fit(fit_on)
    else:
        scaler.fit(data)
    
    # Transform data
    normalized_data = scaler.transform(data)
    
    if return_scaler:
        return normalized_data, scaler
    else:
        return normalized_data


def inverse_normalize(
    data: np.ndarray,
    scaler: Union[StandardScaler, MinMaxScaler, RobustScaler]
) -> np.ndarray:
    """Inverse the normalization applied to time series data.
    
    Args:
        data: Normalized time series data
        scaler: Fitted scaler used for normalization
        
    Returns:
        original_data: Data in original scale
    """
    # Ensure data is 2D
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    
    # Inverse transform
    original_data = scaler.inverse_transform(data)
    
    return original_data


def sliding_window_samples(
    data: np.ndarray,
    window_size: int,
    forecast_horizon: int,
    target_idx: Union[int, List[int]],
    stride: int = 1
) -> Tuple[np.ndarray, np.ndarray]:
    """Create sliding window samples from time series data.
    
    This function creates input-output pairs for supervised learning using a sliding window.
    
    Args:
        data: Time series data with shape [sequence_length, features]
        window_size: Size of the input window
        forecast_horizon: Number of future steps to predict
        target_idx: Index or indices of target variable(s)
        stride: Stride for sliding window
        
    Returns:
        X: Input windows with shape [num_windows, window_size, features]
        y: Target outputs with shape [num_windows, forecast_horizon, num_targets]
    """
    if isinstance(target_idx, int):
        target_idx = [target_idx]
    
    n_samples = data.shape[0] - window_size - forecast_horizon + 1
    n_features = data.shape[1]
    n_targets = len(target_idx)
    
    # Calculare number of windows based on stride
    n_windows = (n_samples + stride - 1) // stride
    
    # Create arrays for inputs and outputs
    X = np.zeros((n_windows, window_size, n_features))
    y = np.zeros((n_windows, forecast_horizon, n_targets))
    
    # Create sliding windows
    for i in range(0, n_samples, stride):
        if i // stride >= n_windows:
            break
            
        # Input window
        X[i // stride] = data[i:i+window_size]
        
        # Output window (targets only)
        y[i // stride] = data[i+window_size:i+window_size+forecast_horizon, target_idx]
    
    return X, y


def create_multi_horizon_target(
    data: np.ndarray,
    target_idx: int,
    horizon: int
) -> np.ndarray:
    """Create multi-horizon target for time series forecasting.
    
    This function creates a multi-horizon target by shifting the target variable
    for each forecast horizon.
    
    Args:
        data: Time series data with shape [sequence_length, features]
        target_idx: Index of target variable
        horizon: Maximum forecast horizon
        
    Returns:
        multi_horizon_target: Target with shape [sequence_length, horizon]
    """
    sequence_length = len(data)
    multi_horizon_target = np.zeros((sequence_length, horizon))
    
    # Fill target for each horizon
    for h in range(1, horizon + 1):
        # Shift target by horizon steps
        multi_horizon_target[:-h, h-1] = data[h:, target_idx]
    
    return multi_horizon_target 