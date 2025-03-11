"""
Data Preprocessing Utilities for Financial Time Series
-----------------------------------------------------
This module provides a comprehensive set of functions for preprocessing financial time series data,
including cleaning, transformation, feature engineering, dimensionality reduction, and data splitting
utilities specifically designed for financial applications.

Features:
    - Data cleaning (missing values, outliers, duplicates)
    - Data transformation (normalization, standardization, special transformations)
    - Feature engineering (lag features, rolling statistics, date features)
    - Dimensionality reduction (PCA, t-SNE, feature selection)
    - Data splitting (time series-aware train/test split)
    
All functions are designed to work with both pandas DataFrame/Series and numpy arrays where appropriate,
and include robust error handling, parameter validation, and detailed documentation.
"""

import numpy as np
import pandas as pd
import logging
from typing import Union, Dict, List, Tuple, Optional, Callable, Any
from sklearn.preprocessing import (
    MinMaxScaler, StandardScaler, RobustScaler, 
    PowerTransformer, QuantileTransformer
)
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression
import scipy.stats as stats
import warnings
from datetime import datetime, timedelta

# Setup logging
logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
# Data Cleaning Functions
#------------------------------------------------------------------------------

def detect_outliers(data: Union[pd.Series, pd.DataFrame], 
                   method: str = 'zscore', 
                   threshold: float = 3.0,
                   columns: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Detect outliers in the data using various methods.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to check for outliers
    method : str, optional
        Method to use for outlier detection:
        - 'zscore': Use Z-score (number of std devs from the mean)
        - 'iqr': Use Interquartile Range method
        - 'modified_zscore': Use modified Z-score with median absolute deviation
        - 'percentile': Use percentile-based thresholds
    threshold : float, optional
        Threshold for outlier detection (depends on the method)
        - For 'zscore' and 'modified_zscore': number of std devs (default: 3.0)
        - For 'iqr': multiplier for IQR (default: 1.5)
        - For 'percentile': percentile cutoff (0-100, default: 1.0 and 99.0)
    columns : Optional[List[str]], optional
        List of columns to check for outliers, if None, check all numeric columns
        
    Returns
    -------
    pd.DataFrame
        DataFrame with boolean mask where True indicates an outlier
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import detect_outliers
    >>> 
    >>> # Create sample data with outliers
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 100, 6, 7, 8, 9, 10],
    >>>     'B': [10, 20, 30, 40, 50, 60, 70, 80, 90, 1000]
    >>> })
    >>> 
    >>> # Detect outliers using Z-score
    >>> outliers = detect_outliers(data, method='zscore', threshold=3.0)
    >>> print(outliers)
    """
    # Convert Series to DataFrame
    if isinstance(data, pd.Series):
        data = pd.DataFrame(data)
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
    
    # Initialize result DataFrame
    outliers = pd.DataFrame(False, index=data_copy.index, columns=columns)
    
    # Apply the specified method
    if method.lower() == 'zscore':
        for col in columns:
            if col in data_copy.columns:
                mean = data_copy[col].mean()
                std = data_copy[col].std()
                if std != 0:  # Avoid division by zero
                    z_scores = np.abs((data_copy[col] - mean) / std)
                    outliers[col] = z_scores > threshold
                else:
                    logger.warning(f"Standard deviation for column {col} is zero. Skipping Z-score outlier detection.")
    
    elif method.lower() == 'iqr':
        for col in columns:
            if col in data_copy.columns:
                q1 = data_copy[col].quantile(0.25)
                q3 = data_copy[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - threshold * iqr
                upper_bound = q3 + threshold * iqr
                outliers[col] = (data_copy[col] < lower_bound) | (data_copy[col] > upper_bound)
    
    elif method.lower() == 'modified_zscore':
        for col in columns:
            if col in data_copy.columns:
                median = data_copy[col].median()
                mad = np.median(np.abs(data_copy[col] - median))
                if mad != 0:  # Avoid division by zero
                    modified_z_scores = 0.6745 * np.abs(data_copy[col] - median) / mad
                    outliers[col] = modified_z_scores > threshold
                else:
                    logger.warning(f"MAD for column {col} is zero. Skipping modified Z-score outlier detection.")
    
    elif method.lower() == 'percentile':
        lower_percentile = threshold if threshold < 1 else threshold
        upper_percentile = 100 - lower_percentile
        
        for col in columns:
            if col in data_copy.columns:
                lower_bound = data_copy[col].quantile(lower_percentile / 100)
                upper_bound = data_copy[col].quantile(upper_percentile / 100)
                outliers[col] = (data_copy[col] < lower_bound) | (data_copy[col] > upper_bound)
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'zscore', 'iqr', 'modified_zscore', or 'percentile'.")
    
    return outliers

def handle_outliers(data: Union[pd.Series, pd.DataFrame],
                   method: str = 'zscore',
                   threshold: float = 3.0,
                   treatment: str = 'clip',
                   columns: Optional[List[str]] = None,
                   winsorize_limits: Tuple[float, float] = (0.05, 0.05)) -> Union[pd.Series, pd.DataFrame]:
    """
    Detect and handle outliers in the data using various methods.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to check for outliers
    method : str, optional
        Method to use for outlier detection:
        - 'zscore': Use Z-score (number of std devs from the mean)
        - 'iqr': Use Interquartile Range method
        - 'modified_zscore': Use modified Z-score with median absolute deviation
        - 'percentile': Use percentile-based thresholds
    threshold : float, optional
        Threshold for outlier detection (depends on the method)
        - For 'zscore' and 'modified_zscore': number of std devs (default: 3.0)
        - For 'iqr': multiplier for IQR (default: 1.5)
        - For 'percentile': percentile cutoff (0-100, default: 1.0 and 99.0)
    treatment : str, optional
        Method to handle outliers:
        - 'clip': Clip outliers to the threshold values (default)
        - 'remove': Remove outliers (returns a copy with outliers removed)
        - 'nan': Replace outliers with NaN
        - 'mean': Replace outliers with mean
        - 'median': Replace outliers with median
        - 'mode': Replace outliers with mode
        - 'winsorize': Winsorize the data (clip based on percentiles)
    columns : Optional[List[str]], optional
        List of columns to check for outliers, if None, check all numeric columns
    winsorize_limits : Tuple[float, float], optional
        Limits for winsorization (lower, upper) between 0 and 1 (default: (0.05, 0.05))
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Data with outliers handled according to the treatment method
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import handle_outliers
    >>> 
    >>> # Create sample data with outliers
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 100, 6, 7, 8, 9, 10],
    >>>     'B': [10, 20, 30, 40, 50, 60, 70, 80, 90, 1000]
    >>> })
    >>> 
    >>> # Handle outliers by clipping
    >>> cleaned_data = handle_outliers(data, method='zscore', treatment='clip')
    >>> print(cleaned_data)
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        series_name = data.name if data.name is not None else 'value'
        data = pd.DataFrame(data, columns=[series_name])
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # Detect outliers
    outliers = detect_outliers(data_copy, method=method, threshold=threshold, columns=columns)
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = outliers.columns.tolist()
    
    # Apply the specified treatment
    if treatment.lower() == 'clip':
        for col in columns:
            if col in data_copy.columns:
                if method.lower() == 'zscore':
                    mean = data_copy[col].mean()
                    std = data_copy[col].std()
                    lower_bound = mean - threshold * std
                    upper_bound = mean + threshold * std
                elif method.lower() == 'iqr':
                    q1 = data_copy[col].quantile(0.25)
                    q3 = data_copy[col].quantile(0.75)
                    iqr = q3 - q1
                    lower_bound = q1 - threshold * iqr
                    upper_bound = q3 + threshold * iqr
                elif method.lower() == 'modified_zscore':
                    median = data_copy[col].median()
                    mad = np.median(np.abs(data_copy[col] - median))
                    lower_bound = median - threshold * 1.4826 * mad
                    upper_bound = median + threshold * 1.4826 * mad
                elif method.lower() == 'percentile':
                    lower_percentile = threshold if threshold < 1 else threshold
                    upper_percentile = 100 - lower_percentile
                    lower_bound = data_copy[col].quantile(lower_percentile / 100)
                    upper_bound = data_copy[col].quantile(upper_percentile / 100)
                
                # Clip values
                data_copy[col] = data_copy[col].clip(lower=lower_bound, upper=upper_bound)
    
    elif treatment.lower() == 'remove':
        # Get rows that have any outliers
        outlier_rows = outliers.any(axis=1)
        data_copy = data_copy[~outlier_rows]
    
    elif treatment.lower() == 'nan':
        for col in columns:
            if col in data_copy.columns:
                data_copy.loc[outliers[col], col] = np.nan
    
    elif treatment.lower() == 'mean':
        for col in columns:
            if col in data_copy.columns:
                mean_val = data_copy[col].mean()
                data_copy.loc[outliers[col], col] = mean_val
    
    elif treatment.lower() == 'median':
        for col in columns:
            if col in data_copy.columns:
                median_val = data_copy[col].median()
                data_copy.loc[outliers[col], col] = median_val
    
    elif treatment.lower() == 'mode':
        for col in columns:
            if col in data_copy.columns:
                mode_val = data_copy[col].mode()[0]
                data_copy.loc[outliers[col], col] = mode_val
    
    elif treatment.lower() == 'winsorize':
        from scipy.stats.mstats import winsorize as scipy_winsorize
        for col in columns:
            if col in data_copy.columns:
                data_copy[col] = scipy_winsorize(data_copy[col].values, limits=winsorize_limits)
    
    else:
        raise ValueError(f"Unknown treatment: {treatment}. Use 'clip', 'remove', 'nan', 'mean', 'median', 'mode', or 'winsorize'.")
    
    # Return Series if input was Series
    if is_series:
        return data_copy[data_copy.columns[0]]
    
    return data_copy

def handle_missing_values(data: Union[pd.Series, pd.DataFrame],
                         method: str = 'interpolate',
                         columns: Optional[List[str]] = None,
                         max_gap: Optional[int] = None,
                         value: Optional[Any] = None,
                         interpolation_method: str = 'linear',
                         order: Optional[int] = None,
                         limit_direction: str = 'both') -> Union[pd.Series, pd.DataFrame]:
    """
    Handle missing values in the data using various methods.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to handle missing values for
    method : str, optional
        Method to use for handling missing values:
        - 'interpolate': Interpolate missing values (default)
        - 'ffill': Forward fill (carry last observation forward)
        - 'bfill': Backward fill (use next observation)
        - 'mean': Replace with mean
        - 'median': Replace with median
        - 'mode': Replace with mode
        - 'constant': Replace with a constant value
        - 'drop': Remove rows with missing values (returns a copy)
    columns : Optional[List[str]], optional
        List of columns to handle missing values for, if None, handle all columns
    max_gap : Optional[int], optional
        Maximum gap size to fill, if None, fill all gaps
    value : Optional[Any], optional
        Value to use for 'constant' method
    interpolation_method : str, optional
        Method to use for interpolation (default: 'linear')
        See pandas.DataFrame.interpolate for options
    order : Optional[int], optional
        Order of polynomial for polynomial interpolation
    limit_direction : str, optional
        Direction to fill for interpolation (default: 'both')
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Data with missing values handled according to the specified method
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import handle_missing_values
    >>> 
    >>> # Create sample data with missing values
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, np.nan, 4, 5, np.nan, 7],
    >>>     'B': [10, np.nan, 30, np.nan, 50, 60, 70]
    >>> })
    >>> 
    >>> # Handle missing values using linear interpolation
    >>> filled_data = handle_missing_values(data, method='interpolate')
    >>> print(filled_data)
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        series_name = data.name if data.name is not None else 'value'
        data = pd.DataFrame(data, columns=[series_name])
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # If columns is None, use all columns
    if columns is None:
        columns = data_copy.columns.tolist()
    
    # Apply the specified method
    if method.lower() == 'interpolate':
        # Create arguments dictionary
        interp_args = {
            'method': interpolation_method,
            'limit_direction': limit_direction
        }
        
        # Add optional arguments if provided
        if order is not None and interpolation_method == 'polynomial':
            interp_args['order'] = order
        if max_gap is not None:
            interp_args['limit'] = max_gap
        
        # Apply interpolation to specified columns
        for col in columns:
            if col in data_copy.columns:
                data_copy[col] = data_copy[col].interpolate(**interp_args)
    
    elif method.lower() == 'ffill':
        limit = max_gap if max_gap is not None else None
        for col in columns:
            if col in data_copy.columns:
                data_copy[col] = data_copy[col].fillna(method='ffill', limit=limit)
    
    elif method.lower() == 'bfill':
        limit = max_gap if max_gap is not None else None
        for col in columns:
            if col in data_copy.columns:
                data_copy[col] = data_copy[col].fillna(method='bfill', limit=limit)
    
    elif method.lower() == 'mean':
        for col in columns:
            if col in data_copy.columns:
                mean_val = data_copy[col].mean()
                data_copy[col] = data_copy[col].fillna(mean_val)
    
    elif method.lower() == 'median':
        for col in columns:
            if col in data_copy.columns:
                median_val = data_copy[col].median()
                data_copy[col] = data_copy[col].fillna(median_val)
    
    elif method.lower() == 'mode':
        for col in columns:
            if col in data_copy.columns:
                # Get the first mode value
                mode_val = data_copy[col].mode()
                if not mode_val.empty:
                    data_copy[col] = data_copy[col].fillna(mode_val[0])
    
    elif method.lower() == 'constant':
        if value is None:
            raise ValueError("For 'constant' method, a value must be provided.")
        
        for col in columns:
            if col in data_copy.columns:
                data_copy[col] = data_copy[col].fillna(value)
    
    elif method.lower() == 'drop':
        # Drop rows with missing values in specified columns
        data_copy = data_copy.dropna(subset=columns)
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'interpolate', 'ffill', 'bfill', 'mean', 'median', 'mode', 'constant', or 'drop'.")
    
    # Return Series if input was Series
    if is_series:
        return data_copy[data_copy.columns[0]]
    
    return data_copy

def remove_duplicates(data: Union[pd.Series, pd.DataFrame],
                     subset: Optional[List[str]] = None,
                     keep: str = 'first',
                     inplace: bool = False) -> Union[pd.Series, pd.DataFrame]:
    """
    Remove duplicate rows from the data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to remove duplicates from
    subset : Optional[List[str]], optional
        List of columns to consider for identifying duplicates,
        if None, use all columns
    keep : str, optional
        Which duplicates to keep:
        - 'first': Keep first occurrence (default)
        - 'last': Keep last occurrence
        - False: Drop all duplicates
    inplace : bool, optional
        Whether to modify the data in place or return a copy (default: False)
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Data with duplicates removed, or None if inplace=True
    
    Examples
    --------
    >>> import pandas as pd
    >>> from advanced_trading.utils.data_preprocessing import remove_duplicates
    >>> 
    >>> # Create sample data with duplicates
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 1, 3, 2],
    >>>     'B': [10, 20, 10, 30, 20]
    >>> })
    >>> 
    >>> # Remove duplicates
    >>> deduped_data = remove_duplicates(data, subset=['A', 'B'])
    >>> print(deduped_data)
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    
    # Return a copy of the data with duplicates removed
    result = data.drop_duplicates(subset=subset, keep=keep, inplace=inplace)
    
    if inplace:
        return None
    else:
        return result

def resample_time_series(data: Union[pd.Series, pd.DataFrame],
                        rule: str,
                        agg_func: Union[str, Dict[str, str], Callable] = 'mean',
                        closed: str = 'right',
                        label: str = 'right',
                        offset: Optional[str] = None) -> Union[pd.Series, pd.DataFrame]:
    """
    Resample a time series to a different frequency.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The time series data to resample (must have a DatetimeIndex)
    rule : str
        The offset string representing the target frequency
        (e.g., 'D' for daily, 'W' for weekly, 'M' for monthly)
    agg_func : Union[str, Dict[str, str], Callable], optional
        The aggregation function to use:
        - str: A single function name ('mean', 'sum', 'first', 'last', etc.)
        - Dict: Column-specific functions {'col1': 'mean', 'col2': 'sum'}
        - Callable: A custom aggregation function
    closed : str, optional
        Which side of the interval is closed (default: 'right')
    label : str, optional
        Which side of the interval to use for labeling (default: 'right')
    offset : Optional[str], optional
        An offset to shift the resampling window
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Resampled time series data
    
    Raises
    ------
    TypeError
        If the data doesn't have a DatetimeIndex
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import resample_time_series
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=10, freq='D')
    >>> data = pd.DataFrame({
    >>>     'A': np.random.randn(10),
    >>>     'B': np.random.randn(10)
    >>> }, index=dates)
    >>> 
    >>> # Resample to weekly frequency
    >>> weekly_data = resample_time_series(data, rule='W', agg_func={'A': 'mean', 'B': 'sum'})
    >>> print(weekly_data)
    """
    # Check if index is DatetimeIndex
    if not isinstance(data.index, pd.DatetimeIndex):
        try:
            # Try to convert the index to DatetimeIndex
            data = data.copy()
            data.index = pd.to_datetime(data.index)
        except:
            raise TypeError("Data must have a DatetimeIndex for resampling.")
    
    # Create resampler object
    resampler = data.resample(rule=rule, closed=closed, label=label, offset=offset)
    
    # Apply aggregation function
    if isinstance(agg_func, str):
        # Single function for all columns
        result = getattr(resampler, agg_func)()
    elif isinstance(agg_func, dict):
        # Different functions for different columns
        result = resampler.agg(agg_func)
    else:
        # Custom function
        result = resampler.apply(agg_func)
    
    return result 

#------------------------------------------------------------------------------
# Data Transformation Functions
#------------------------------------------------------------------------------

def normalize_data(data: Union[pd.Series, pd.DataFrame],
                  method: str = 'minmax',
                  feature_range: Tuple[float, float] = (0, 1),
                  columns: Optional[List[str]] = None,
                  return_scaler: bool = False) -> Union[
                      Union[pd.Series, pd.DataFrame],
                      Tuple[Union[pd.Series, pd.DataFrame], Dict[str, Any]]
                  ]:
    """
    Normalize data using various methods.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to normalize
    method : str, optional
        Method to use for normalization:
        - 'minmax': Min-Max scaling to [0, 1] range (default)
        - 'standard': Standardization (zero mean, unit variance)
        - 'robust': Robust scaling using quantiles
        - 'maxabs': Scale by maximum absolute value
        - 'power': Power transformation for Gaussian-like distributions
        - 'quantile': Quantile transformation to uniform or normal distribution
    feature_range : Tuple[float, float], optional
        Range to scale the data to for 'minmax' method (default: (0, 1))
    columns : Optional[List[str]], optional
        List of columns to normalize, if None, normalize all numeric columns
    return_scaler : bool, optional
        Whether to return the scaler object(s) along with the normalized data
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame] or Tuple[Union[pd.Series, pd.DataFrame], Dict[str, Any]]
        Normalized data, optionally with scaler object(s)
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import normalize_data
    >>> 
    >>> # Create sample data
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    >>>     'B': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    >>> })
    >>> 
    >>> # Normalize data using min-max scaling
    >>> normalized_data, scalers = normalize_data(data, method='minmax', return_scaler=True)
    >>> print(normalized_data)
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        series_name = data.name if data.name is not None else 'value'
        data = pd.DataFrame(data, columns=[series_name])
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
    
    # Initialize scaler dictionary
    scalers = {}
    
    # Apply the specified method
    if method.lower() == 'minmax':
        for col in columns:
            if col in data_copy.columns:
                scaler = MinMaxScaler(feature_range=feature_range)
                data_copy[col] = scaler.fit_transform(data_copy[[col]]).flatten()
                scalers[col] = scaler
    
    elif method.lower() == 'standard':
        for col in columns:
            if col in data_copy.columns:
                scaler = StandardScaler()
                data_copy[col] = scaler.fit_transform(data_copy[[col]]).flatten()
                scalers[col] = scaler
    
    elif method.lower() == 'robust':
        for col in columns:
            if col in data_copy.columns:
                scaler = RobustScaler()
                data_copy[col] = scaler.fit_transform(data_copy[[col]]).flatten()
                scalers[col] = scaler
    
    elif method.lower() == 'maxabs':
        for col in columns:
            if col in data_copy.columns:
                # Normalize by maximum absolute value
                max_abs = np.max(np.abs(data_copy[col]))
                if max_abs != 0:  # Avoid division by zero
                    data_copy[col] = data_copy[col] / max_abs
                    # Store the max_abs value for inverse transformation
                    scalers[col] = {'max_abs': max_abs}
    
    elif method.lower() == 'power':
        for col in columns:
            if col in data_copy.columns:
                # For non-positive values, shift data to be positive
                min_val = data_copy[col].min()
                if min_val <= 0:
                    shift = abs(min_val) + 1e-6  # Small epsilon to ensure positive values
                    data_copy[col] = data_copy[col] + shift
                    scalers[col] = {'shift': shift}
                
                # Apply power transformation
                scaler = PowerTransformer(method='yeo-johnson')
                data_copy[col] = scaler.fit_transform(data_copy[[col]]).flatten()
                
                if col in scalers:
                    scalers[col]['scaler'] = scaler
                else:
                    scalers[col] = {'scaler': scaler, 'shift': 0}
    
    elif method.lower() == 'quantile':
        for col in columns:
            if col in data_copy.columns:
                scaler = QuantileTransformer(output_distribution='normal')
                data_copy[col] = scaler.fit_transform(data_copy[[col]]).flatten()
                scalers[col] = scaler
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'minmax', 'standard', 'robust', 'maxabs', 'power', or 'quantile'.")
    
    # Return Series if input was Series
    if is_series:
        result = data_copy[data_copy.columns[0]]
    else:
        result = data_copy
    
    if return_scaler:
        return result, scalers
    else:
        return result

def apply_scaler(data: Union[pd.Series, pd.DataFrame],
                scalers: Dict[str, Any],
                columns: Optional[List[str]] = None,
                inverse: bool = False) -> Union[pd.Series, pd.DataFrame]:
    """
    Apply pre-fitted scalers to data or inverse transform scaled data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to transform or inverse transform
    scalers : Dict[str, Any]
        Dictionary of fitted scaler objects, as returned by normalize_data(return_scaler=True)
    columns : Optional[List[str]], optional
        List of columns to transform, if None, transform all columns with available scalers
    inverse : bool, optional
        Whether to apply inverse transformation (default: False)
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Transformed or inverse-transformed data
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import normalize_data, apply_scaler
    >>> 
    >>> # Create sample data
    >>> train_data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 5],
    >>>     'B': [10, 20, 30, 40, 50]
    >>> })
    >>> test_data = pd.DataFrame({
    >>>     'A': [6, 7, 8, 9, 10],
    >>>     'B': [60, 70, 80, 90, 100]
    >>> })
    >>> 
    >>> # Normalize training data and get scalers
    >>> normalized_train, scalers = normalize_data(train_data, method='minmax', return_scaler=True)
    >>> 
    >>> # Apply same scaling to test data
    >>> normalized_test = apply_scaler(test_data, scalers)
    >>> 
    >>> # Inverse transform
    >>> original_data = apply_scaler(normalized_test, scalers, inverse=True)
    >>> print(original_data)
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        series_name = data.name if data.name is not None else 'value'
        data = pd.DataFrame(data, columns=[series_name])
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # If columns is None, use all columns with available scalers
    if columns is None:
        columns = [col for col in data_copy.columns if col in scalers]
    else:
        # Filter to include only columns that have scalers
        columns = [col for col in columns if col in scalers]
    
    # Apply transformation for each column
    for col in columns:
        if col in data_copy.columns:
            scaler = scalers[col]
            
            # Different handling based on scaler type
            if isinstance(scaler, dict) and 'max_abs' in scaler:
                # MaxAbs scaling
                if inverse:
                    data_copy[col] = data_copy[col] * scaler['max_abs']
                else:
                    data_copy[col] = data_copy[col] / scaler['max_abs']
            
            elif isinstance(scaler, dict) and 'scaler' in scaler:
                # Power transformation with potential shift
                if inverse:
                    # First inverse the transformation
                    data_copy[col] = scaler['scaler'].inverse_transform(data_copy[[col]]).flatten()
                    # Then undo the shift if applied
                    if 'shift' in scaler and scaler['shift'] > 0:
                        data_copy[col] = data_copy[col] - scaler['shift']
                else:
                    # First apply the shift if needed
                    if 'shift' in scaler and scaler['shift'] > 0:
                        data_copy[col] = data_copy[col] + scaler['shift']
                    # Then apply the transformation
                    data_copy[col] = scaler['scaler'].transform(data_copy[[col]]).flatten()
            
            else:
                # Standard sklearn scalers
                if inverse:
                    data_copy[col] = scaler.inverse_transform(data_copy[[col]]).flatten()
                else:
                    data_copy[col] = scaler.transform(data_copy[[col]]).flatten()
    
    # Return Series if input was Series
    if is_series:
        return data_copy[data_copy.columns[0]]
    
    return data_copy

def apply_log_transform(data: Union[pd.Series, pd.DataFrame], 
                       columns: Optional[List[str]] = None,
                       epsilon: float = 1e-6,
                       inverse: bool = False) -> Union[pd.Series, pd.DataFrame]:
    """
    Apply logarithmic transformation to the data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to transform
    columns : Optional[List[str]], optional
        List of columns to transform, if None, transform all numeric columns
    epsilon : float, optional
        Small constant to add to avoid log(0) (default: 1e-6)
    inverse : bool, optional
        Whether to apply inverse transformation (exponential) (default: False)
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Transformed data
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import apply_log_transform
    >>> 
    >>> # Create sample data
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 5],
    >>>     'B': [10, 20, 30, 40, 50]
    >>> })
    >>> 
    >>> # Apply log transformation
    >>> log_data = apply_log_transform(data)
    >>> print(log_data)
    >>> 
    >>> # Inverse transform to get original data
    >>> original_data = apply_log_transform(log_data, inverse=True)
    >>> print(original_data)
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        series_name = data.name if data.name is not None else 'value'
        data = pd.DataFrame(data, columns=[series_name])
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
    
    # Apply log transform or inverse
    for col in columns:
        if col in data_copy.columns:
            if inverse:
                # Apply exponential function
                data_copy[col] = np.exp(data_copy[col])
            else:
                # Check for non-positive values
                min_val = data_copy[col].min()
                
                if min_val <= 0:
                    # Add epsilon to avoid log(0)
                    data_copy[col] = np.log(data_copy[col] + abs(min_val) + epsilon)
                else:
                    # Apply natural log
                    data_copy[col] = np.log(data_copy[col])
    
    # Return Series if input was Series
    if is_series:
        return data_copy[data_copy.columns[0]]
    
    return data_copy

def apply_box_cox_transform(data: Union[pd.Series, pd.DataFrame],
                           columns: Optional[List[str]] = None,
                           lmbda: Optional[Union[float, Dict[str, float]]] = None,
                           epsilon: float = 1e-6,
                           inverse: bool = False,
                           return_lambda: bool = False) -> Union[
                               Union[pd.Series, pd.DataFrame],
                               Tuple[Union[pd.Series, pd.DataFrame], Dict[str, float]]
                           ]:
    """
    Apply Box-Cox transformation to the data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The data to transform (must be strictly positive for Box-Cox)
    columns : Optional[List[str]], optional
        List of columns to transform, if None, transform all numeric columns
    lmbda : Optional[Union[float, Dict[str, float]]], optional
        Lambda parameter(s) for the Box-Cox transformation:
        - None: Find optimal lambda for each column (default)
        - float: Use the same lambda for all columns
        - Dict: Use specific lambda for each column {'col1': lambda1, 'col2': lambda2}
    epsilon : float, optional
        Small constant to add to ensure positive values (default: 1e-6)
    inverse : bool, optional
        Whether to apply inverse transformation (default: False)
    return_lambda : bool, optional
        Whether to return the lambda parameter(s) along with the transformed data
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame] or Tuple[Union[pd.Series, pd.DataFrame], Dict[str, float]]
        Transformed data, optionally with lambda parameter(s)
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import apply_box_cox_transform
    >>> 
    >>> # Create sample data
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 5],
    >>>     'B': [10, 20, 30, 40, 50]
    >>> })
    >>> 
    >>> # Apply Box-Cox transformation with optimal lambda
    >>> transformed_data, lambdas = apply_box_cox_transform(data, return_lambda=True)
    >>> print(transformed_data)
    >>> print(f"Optimal lambdas: {lambdas}")
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        series_name = data.name if data.name is not None else 'value'
        data = pd.DataFrame(data, columns=[series_name])
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
    
    # Initialize lambda dictionary
    lambda_dict = {}
    
    # Prepare lambda values
    if lmbda is None:
        # Will be calculated for each column
        pass
    elif isinstance(lmbda, (int, float)):
        # Use the same lambda for all columns
        lambda_dict = {col: lmbda for col in columns}
    elif isinstance(lmbda, dict):
        # Use provided lambdas for specific columns
        lambda_dict = lmbda
    else:
        raise ValueError("lmbda must be None, a number, or a dictionary of column-specific lambda values.")
    
    # Apply Box-Cox transform or inverse
    for col in columns:
        if col in data_copy.columns:
            # Ensure values are positive
            min_val = data_copy[col].min()
            if min_val <= 0:
                shift = abs(min_val) + epsilon
                data_copy[col] = data_copy[col] + shift
            else:
                shift = 0
            
            if inverse:
                # Apply inverse Box-Cox transformation
                if col not in lambda_dict:
                    raise ValueError(f"Lambda value for column '{col}' not provided for inverse transformation.")
                
                lmbda_val = lambda_dict[col]
                
                if abs(lmbda_val) < 1e-10:  # Close to zero
                    # For lambda close to 0, inverse of log is exp
                    data_copy[col] = np.exp(data_copy[col])
                else:
                    # General inverse Box-Cox formula
                    data_copy[col] = np.power(lmbda_val * data_copy[col] + 1, 1/lmbda_val)
                
                # Undo shift if applied
                if shift > 0:
                    data_copy[col] = data_copy[col] - shift
            
            else:
                # Apply Box-Cox transformation
                if col in lambda_dict:
                    # Use provided lambda
                    lmbda_val = lambda_dict[col]
                    if abs(lmbda_val) < 1e-10:  # Close to zero
                        # For lambda close to 0, use log
                        transformed = np.log(data_copy[col])
                    else:
                        # General Box-Cox formula
                        transformed = (np.power(data_copy[col], lmbda_val) - 1) / lmbda_val
                    
                    data_copy[col] = transformed
                    lambda_dict[col] = lmbda_val
                else:
                    # Find optimal lambda
                    transformed, lmbda_val = stats.boxcox(data_copy[col].values)
                    data_copy[col] = transformed
                    lambda_dict[col] = lmbda_val
    
    # Return Series if input was Series
    if is_series:
        result = data_copy[data_copy.columns[0]]
    else:
        result = data_copy
    
    if return_lambda:
        return result, lambda_dict
    else:
        return result

def apply_differencing(data: Union[pd.Series, pd.DataFrame],
                      periods: int = 1,
                      order: int = 1,
                      seasonal: bool = False,
                      seasonal_periods: int = None,
                      columns: Optional[List[str]] = None) -> Union[pd.Series, pd.DataFrame]:
    """
    Apply differencing to time series data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        The time series data to difference
    periods : int, optional
        Periods to shift for calculating difference (default: 1)
    order : int, optional
        Number of times to difference (default: 1)
    seasonal : bool, optional
        Whether to apply seasonal differencing (default: False)
    seasonal_periods : int, optional
        Seasonal periods for seasonal differencing (required if seasonal=True)
    columns : Optional[List[str]], optional
        List of columns to difference, if None, difference all numeric columns
        
    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Differenced data
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import apply_differencing
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=10, freq='D')
    >>> data = pd.DataFrame({
    >>>     'A': [10, 11, 13, 16, 20, 25, 31, 38, 46, 55],
    >>>     'B': [100, 105, 110, 115, 120, 125, 130, 135, 140, 145]
    >>> }, index=dates)
    >>> 
    >>> # Apply first-order differencing
    >>> diff_data = apply_differencing(data, periods=1, order=1)
    >>> print(diff_data)
    """
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        series_name = data.name if data.name is not None else 'value'
        data = pd.DataFrame(data, columns=[series_name])
    
    # Make a copy to avoid modifying the original
    data_copy = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
    
    # Check if seasonal differencing is requested but seasonal_periods is not provided
    if seasonal and seasonal_periods is None:
        raise ValueError("seasonal_periods must be provided for seasonal differencing.")
    
    # Apply differencing
    for col in columns:
        if col in data_copy.columns:
            # Apply regular differencing
            for _ in range(order):
                data_copy[col] = data_copy[col].diff(periods=periods)
            
            # Apply seasonal differencing if requested
            if seasonal:
                data_copy[col] = data_copy[col].diff(periods=seasonal_periods)
    
    # Return Series if input was Series
    if is_series:
        return data_copy[data_copy.columns[0]]
    
    return data_copy 

#------------------------------------------------------------------------------
# Feature Engineering Functions
#------------------------------------------------------------------------------

def create_lag_features(data: Union[pd.Series, pd.DataFrame],
                       lags: List[int],
                       columns: Optional[List[str]] = None,
                       drop_na: bool = True) -> pd.DataFrame:
    """
    Create lag features from time series data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Time series data to create lag features from
    lags : List[int]
        List of lag periods to create
    columns : Optional[List[str]], optional
        List of columns to create lags for, if None, use all numeric columns
    drop_na : bool, optional
        Whether to drop rows with NaN values after creating lags (default: True)
        
    Returns
    -------
    pd.DataFrame
        DataFrame with original and lag features
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import create_lag_features
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=10, freq='D')
    >>> data = pd.DataFrame({
    >>>     'price': [100, 102, 104, 103, 105, 107, 108, 106, 104, 105]
    >>> }, index=dates)
    >>> 
    >>> # Create lag features with lags 1, 2, and 3
    >>> lagged_data = create_lag_features(data, lags=[1, 2, 3])
    >>> print(lagged_data)
    """
    logger.info(f"Creating lag features with lags: {lags}")
    
    # Convert to DataFrame if Series
    if isinstance(data, pd.Series):
        data = pd.DataFrame(data)
    
    # Make a copy
    result = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = result.select_dtypes(include=np.number).columns.tolist()
    
    # Create lag features
    for col in columns:
        if col in result.columns:
            for lag in lags:
                if lag <= 0:
                    logger.warning(f"Lag must be positive, skipping lag {lag}")
                    continue
                    
                lag_name = f"{col}_lag_{lag}"
                result[lag_name] = result[col].shift(lag)
    
    # Drop rows with NaN values if requested
    if drop_na:
        result = result.dropna()
    
    return result

def create_rolling_features(data: Union[pd.Series, pd.DataFrame],
                           windows: List[int],
                           functions: Dict[str, Callable] = None,
                           columns: Optional[List[str]] = None,
                           min_periods: Optional[int] = None,
                           center: bool = False,
                           win_type: Optional[str] = None,
                           drop_na: bool = True) -> pd.DataFrame:
    """
    Create rolling window features from time series data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Time series data to create rolling features from
    windows : List[int]
        List of window sizes to use
    functions : Dict[str, Callable], optional
        Dictionary of function names and functions to apply to rolling windows
        e.g. {'mean': np.mean, 'std': np.std}
        If None, uses {'mean': np.mean, 'std': np.std, 'min': np.min, 'max': np.max}
    columns : Optional[List[str]], optional
        List of columns to create rolling features for, if None, use all numeric columns
    min_periods : Optional[int], optional
        Minimum number of observations required in window
    center : bool, optional
        Set the labels at the center of the window (default: False)
    win_type : Optional[str], optional
        Window type (see pandas.DataFrame.rolling for options)
    drop_na : bool, optional
        Whether to drop rows with NaN values after creating features (default: True)
        
    Returns
    -------
    pd.DataFrame
        DataFrame with original and rolling features
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import create_rolling_features
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=10, freq='D')
    >>> data = pd.DataFrame({
    >>>     'price': [100, 102, 104, 103, 105, 107, 108, 106, 104, 105]
    >>> }, index=dates)
    >>> 
    >>> # Create rolling features with window sizes 3 and 5
    >>> rolling_data = create_rolling_features(data, windows=[3, 5])
    >>> print(rolling_data)
    """
    logger.info(f"Creating rolling features with windows: {windows}")
    
    # Convert to DataFrame if Series
    if isinstance(data, pd.Series):
        data = pd.DataFrame(data)
    
    # Make a copy
    result = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = result.select_dtypes(include=np.number).columns.tolist()
    
    # If functions is None, use default functions
    if functions is None:
        functions = {
            'mean': np.mean,
            'std': np.std,
            'min': np.min,
            'max': np.max
        }
    
    # Create rolling features
    for col in columns:
        if col in result.columns:
            for window in windows:
                if window <= 0:
                    logger.warning(f"Window size must be positive, skipping window {window}")
                    continue
                
                # Create rolling object
                rolling = result[col].rolling(
                    window=window,
                    min_periods=min_periods,
                    center=center,
                    win_type=win_type
                )
                
                # Apply functions
                for func_name, func in functions.items():
                    feature_name = f"{col}_rolling_{window}_{func_name}"
                    result[feature_name] = rolling.apply(func, raw=True)
    
    # Drop rows with NaN values if requested
    if drop_na:
        result = result.dropna()
    
    return result

def extract_date_features(data: Union[pd.Series, pd.DataFrame],
                         features: List[str] = None,
                         date_column: Optional[str] = None) -> pd.DataFrame:
    """
    Extract date/time features from time series data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Time series data to extract date features from
    features : List[str], optional
        List of date features to extract. Default includes:
        ['year', 'month', 'day', 'dayofweek', 'dayofyear', 'quarter', 'hour', 'minute', 'is_month_end', 'is_month_start']
    date_column : Optional[str], optional
        Column name containing datetime information. If None, uses the DataFrame index
        
    Returns
    -------
    pd.DataFrame
        DataFrame with original and date features
    
    Examples
    --------
    >>> import pandas as pd
    >>> from advanced_trading.utils.data_preprocessing import extract_date_features
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=10, freq='D')
    >>> data = pd.DataFrame({
    >>>     'price': [100, 102, 104, 103, 105, 107, 108, 106, 104, 105]
    >>> }, index=dates)
    >>> 
    >>> # Extract date features
    >>> date_features = extract_date_features(data)
    >>> print(date_features)
    """
    logger.info("Extracting date features")
    
    # Convert to DataFrame if Series
    if isinstance(data, pd.Series):
        data = pd.DataFrame(data)
    
    # Make a copy
    result = data.copy()
    
    # Default features
    if features is None:
        features = [
            'year', 'month', 'day', 'dayofweek', 'dayofyear', 'quarter',
            'hour', 'minute', 'is_month_end', 'is_month_start'
        ]
    
    # Get datetime series
    if date_column is None:
        if not isinstance(result.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index is not a DatetimeIndex and no date_column provided")
        dates = result.index
    else:
        if date_column not in result.columns:
            raise ValueError(f"Column {date_column} not found in DataFrame")
        dates = pd.to_datetime(result[date_column])
    
    # Extract features
    for feature in features:
        if feature == 'year':
            result['year'] = dates.year
        elif feature == 'month':
            result['month'] = dates.month
        elif feature == 'day':
            result['day'] = dates.day
        elif feature == 'dayofweek':
            result['dayofweek'] = dates.dayofweek
        elif feature == 'dayofyear':
            result['dayofyear'] = dates.dayofyear
        elif feature == 'quarter':
            result['quarter'] = dates.quarter
        elif feature == 'hour':
            result['hour'] = dates.hour
        elif feature == 'minute':
            result['minute'] = dates.minute
        elif feature == 'second':
            result['second'] = dates.second
        elif feature == 'is_month_end':
            result['is_month_end'] = dates.is_month_end.astype(int)
        elif feature == 'is_month_start':
            result['is_month_start'] = dates.is_month_start.astype(int)
        elif feature == 'is_quarter_end':
            result['is_quarter_end'] = dates.is_quarter_end.astype(int)
        elif feature == 'is_quarter_start':
            result['is_quarter_start'] = dates.is_quarter_start.astype(int)
        elif feature == 'is_year_end':
            result['is_year_end'] = dates.is_year_end.astype(int)
        elif feature == 'is_year_start':
            result['is_year_start'] = dates.is_year_start.astype(int)
        elif feature == 'weekday_name':
            # Get weekday name
            weekday_map = {
                0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
                4: 'Friday', 5: 'Saturday', 6: 'Sunday'
            }
            result['weekday_name'] = dates.dayofweek.map(weekday_map)
        elif feature == 'month_name':
            # Get month name
            month_map = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }
            result['month_name'] = dates.month.map(month_map)
        else:
            logger.warning(f"Unknown date feature: {feature}, skipping")
    
    return result 

#------------------------------------------------------------------------------
# Dimensionality Reduction Functions
#------------------------------------------------------------------------------

def apply_pca(data: Union[pd.Series, pd.DataFrame],
             n_components: Optional[Union[int, float]] = None,
             columns: Optional[List[str]] = None,
             standardize: bool = True,
             return_components: bool = False,
             return_explained_variance: bool = False) -> Union[
                 pd.DataFrame,
                 Tuple[pd.DataFrame, PCA, Optional[pd.DataFrame]]
             ]:
    """
    Apply Principal Component Analysis (PCA) to the data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Data to apply PCA to
    n_components : Optional[Union[int, float]], optional
        Number of components to keep:
        - If int, the exact number of components
        - If float between 0 and 1, the number of components such that the amount
          of variance explained is greater than the percentage specified
        - If None, all components are kept
    columns : Optional[List[str]], optional
        List of columns to apply PCA to, if None, use all numeric columns
    standardize : bool, optional
        Whether to standardize the data before applying PCA (default: True)
    return_components : bool, optional
        Whether to return the PCA components (default: False)
    return_explained_variance : bool, optional
        Whether to return the explained variance ratio (default: False)
        
    Returns
    -------
    pd.DataFrame or Tuple
        DataFrame with PCA components, optionally with PCA object and components DataFrame
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import apply_pca
    >>> 
    >>> # Create sample data
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    >>>     'B': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    >>>     'C': [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    >>> })
    >>> 
    >>> # Apply PCA with 2 components
    >>> pca_data, pca_obj, components = apply_pca(data, n_components=2, 
    >>>                                         return_components=True,
    >>>                                         return_explained_variance=True)
    >>> print(pca_data)
    >>> print("Explained variance:", pca_obj.explained_variance_ratio_)
    >>> print("Components:\n", components)
    """
    logger.info(f"Applying PCA with n_components={n_components}")
    
    # Convert to DataFrame if Series
    if isinstance(data, pd.Series):
        data = pd.DataFrame(data)
    
    # Make a copy
    data_copy = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
    
    # Check we have enough columns for PCA
    if len(columns) < 2:
        raise ValueError("PCA requires at least 2 columns")
    
    # Get original index
    original_index = data_copy.index
    
    # Extract features for PCA
    features = data_copy[columns].copy()
    
    # Handle missing values
    if features.isnull().any().any():
        raise ValueError("Data contains missing values. Handle missing values before applying PCA.")
    
    # Standardize the data if requested
    if standardize:
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
    else:
        features_scaled = features.values
    
    # Apply PCA
    pca = PCA(n_components=n_components)
    principal_components = pca.fit_transform(features_scaled)
    
    # Create DataFrame with principal components
    column_names = [f"PC{i+1}" for i in range(principal_components.shape[1])]
    pc_df = pd.DataFrame(data=principal_components, columns=column_names, index=original_index)
    
    # Create components DataFrame if requested
    if return_components:
        components_df = pd.DataFrame(
            data=pca.components_,
            columns=columns,
            index=column_names
        )
    else:
        components_df = None
    
    # Determine return value
    if return_components or return_explained_variance:
        return pc_df, pca, components_df
    else:
        return pc_df

def apply_tsne(data: Union[pd.Series, pd.DataFrame],
              n_components: int = 2,
              columns: Optional[List[str]] = None,
              perplexity: float = 30.0,
              learning_rate: float = 200.0,
              n_iter: int = 1000,
              standardize: bool = True,
              random_state: Optional[int] = None) -> pd.DataFrame:
    """
    Apply t-Distributed Stochastic Neighbor Embedding (t-SNE) to the data.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Data to apply t-SNE to
    n_components : int, optional
        Number of components for the embedded space (default: 2)
    columns : Optional[List[str]], optional
        List of columns to apply t-SNE to, if None, use all numeric columns
    perplexity : float, optional
        Related to the number of nearest neighbors (default: 30.0)
    learning_rate : float, optional
        Learning rate for optimization (default: 200.0)
    n_iter : int, optional
        Number of iterations for optimization (default: 1000)
    standardize : bool, optional
        Whether to standardize the data before applying t-SNE (default: True)
    random_state : Optional[int], optional
        Random state for reproducibility
        
    Returns
    -------
    pd.DataFrame
        DataFrame with t-SNE components
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import apply_tsne
    >>> 
    >>> # Create sample data
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    >>>     'B': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    >>>     'C': [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    >>> })
    >>> 
    >>> # Apply t-SNE with 2 components
    >>> tsne_data = apply_tsne(data, n_components=2, random_state=42)
    >>> print(tsne_data)
    """
    logger.info(f"Applying t-SNE with n_components={n_components}, perplexity={perplexity}")
    
    # Convert to DataFrame if Series
    if isinstance(data, pd.Series):
        data = pd.DataFrame(data)
    
    # Make a copy
    data_copy = data.copy()
    
    # If columns is None, use all numeric columns
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
    
    # Get original index
    original_index = data_copy.index
    
    # Extract features for t-SNE
    features = data_copy[columns].copy()
    
    # Handle missing values
    if features.isnull().any().any():
        raise ValueError("Data contains missing values. Handle missing values before applying t-SNE.")
    
    # Standardize the data if requested
    if standardize:
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
    else:
        features_scaled = features.values
    
    # Apply t-SNE
    tsne = TSNE(
        n_components=n_components,
        perplexity=perplexity,
        learning_rate=learning_rate,
        n_iter=n_iter,
        random_state=random_state
    )
    tsne_results = tsne.fit_transform(features_scaled)
    
    # Create DataFrame with t-SNE results
    column_names = [f"TSNE{i+1}" for i in range(n_components)]
    tsne_df = pd.DataFrame(data=tsne_results, columns=column_names, index=original_index)
    
    return tsne_df

def select_features_by_importance(data: pd.DataFrame,
                                 target_column: str,
                                 method: str = 'f_regression',
                                 k: Optional[int] = None,
                                 percentile: Optional[int] = None,
                                 columns: Optional[List[str]] = None,
                                 return_scores: bool = False) -> Union[
                                     List[str],
                                     Tuple[List[str], pd.DataFrame]
                                 ]:
    """
    Select features based on importance metrics.
    
    Parameters
    ----------
    data : pd.DataFrame
        Data containing features and target
    target_column : str
        Name of the target column
    method : str, optional
        Feature selection method:
        - 'f_regression': F-statistic for regression (default)
        - 'mutual_info': Mutual information for regression
    k : Optional[int], optional
        Number of top features to select
    percentile : Optional[int], optional
        Percent of top features to select (0-100)
    columns : Optional[List[str]], optional
        List of columns to consider for feature selection, if None, use all numeric columns
        except target_column
    return_scores : bool, optional
        Whether to return feature importance scores (default: False)
        
    Returns
    -------
    List[str] or Tuple[List[str], pd.DataFrame]
        List of selected feature names, optionally with scores DataFrame
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import select_features_by_importance
    >>> 
    >>> # Create sample data
    >>> data = pd.DataFrame({
    >>>     'A': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    >>>     'B': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    >>>     'C': [5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
    >>>     'target': [10, 22, 33, 43, 55, 67, 76, 89, 99, 110]
    >>> })
    >>> 
    >>> # Select top 2 features
    >>> selected_features, scores = select_features_by_importance(
    >>>     data, 'target', k=2, return_scores=True
    >>> )
    >>> print("Selected features:", selected_features)
    >>> print("Feature scores:\n", scores)
    """
    logger.info(f"Selecting features using {method} method")
    
    # Validate parameters
    if k is None and percentile is None:
        raise ValueError("Either k or percentile must be provided")
    if k is not None and percentile is not None:
        raise ValueError("Only one of k or percentile should be provided")
    
    # Make a copy
    data_copy = data.copy()
    
    # Ensure target_column exists
    if target_column not in data_copy.columns:
        raise ValueError(f"Target column '{target_column}' not found in data")
    
    # If columns is None, use all numeric columns except target
    if columns is None:
        columns = data_copy.select_dtypes(include=np.number).columns.tolist()
        if target_column in columns:
            columns.remove(target_column)
    
    # Check if we have features to select from
    if len(columns) == 0:
        raise ValueError("No features available for selection")
    
    # Get feature matrix and target vector
    X = data_copy[columns]
    y = data_copy[target_column]
    
    # Handle missing values
    if X.isnull().any().any() or y.isnull().any():
        raise ValueError("Data contains missing values. Handle missing values before feature selection.")
    
    # Define the selection method
    if method.lower() == 'f_regression':
        score_func = f_regression
    elif method.lower() == 'mutual_info':
        score_func = mutual_info_regression
    else:
        raise ValueError(f"Unknown method: {method}. Use 'f_regression' or 'mutual_info'.")
    
    # Create the selector based on k or percentile
    if k is not None:
        if k > len(columns):
            logger.warning(f"k ({k}) is greater than the number of features ({len(columns)}). Using all features.")
            k = len(columns)
        selector = SelectKBest(score_func=score_func, k=k)
    else:
        selector = SelectKBest(score_func=score_func, k=int(len(columns) * percentile / 100))
    
    # Fit the selector
    selector.fit(X, y)
    
    # Get selected feature indices and names
    selected_indices = selector.get_support(indices=True)
    selected_features = [columns[i] for i in selected_indices]
    
    # If return_scores, create a DataFrame with scores
    if return_scores:
        scores = pd.DataFrame(
            data={'score': selector.scores_},
            index=columns
        )
        scores = scores.sort_values('score', ascending=False)
        return selected_features, scores
    else:
        return selected_features

#------------------------------------------------------------------------------
# Data Splitting Functions
#------------------------------------------------------------------------------

def split_time_series_data(data: Union[pd.Series, pd.DataFrame],
                          train_size: Optional[Union[int, float]] = None,
                          test_size: Optional[Union[int, float]] = None,
                          val_size: Optional[Union[int, float]] = None,
                          gap: int = 0,
                          shuffle: bool = False,
                          random_state: Optional[int] = None) -> Dict[str, Union[pd.Series, pd.DataFrame]]:
    """
    Split time series data into train, validation, and test sets.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Time series data to split
    train_size : Optional[Union[int, float]], optional
        Size of training set:
        - If int, number of samples
        - If float between 0 and 1, percentage of samples
        - If None, determined from test_size and val_size
    test_size : Optional[Union[int, float]], optional
        Size of test set:
        - If int, number of samples
        - If float between 0 and 1, percentage of samples
        - If None, 0.2 (20%) is used
    val_size : Optional[Union[int, float]], optional
        Size of validation set:
        - If int, number of samples
        - If float between 0 and 1, percentage of samples
        - If None, no validation set is created
    gap : int, optional
        Number of samples to skip between train/val and val/test sets (default: 0)
    shuffle : bool, optional
        Whether to shuffle the data (default: False, recommended False for time series)
    random_state : Optional[int], optional
        Random state for shuffling
        
    Returns
    -------
    Dict[str, Union[pd.Series, pd.DataFrame]]
        Dictionary with 'train', 'val' (if val_size is not None), and 'test' keys
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import split_time_series_data
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=100, freq='D')
    >>> data = pd.DataFrame({
    >>>     'price': np.random.normal(100, 10, 100)
    >>> }, index=dates)
    >>> 
    >>> # Split into train (70%), validation (15%), and test (15%) sets
    >>> splits = split_time_series_data(data, train_size=0.7, val_size=0.15, test_size=0.15)
    >>> print("Train shape:", splits['train'].shape)
    >>> print("Validation shape:", splits['val'].shape)
    >>> print("Test shape:", splits['test'].shape)
    """
    logger.info("Splitting time series data")
    
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        data = pd.DataFrame(data)
    
    # Make a copy
    data_copy = data.copy()
    
    # Determine number of samples
    n_samples = len(data_copy)
    
    # Validate parameters
    if test_size is None and train_size is None:
        test_size = 0.2  # Default test size of 20%
    
    # Calculate absolute sizes
    if test_size is not None:
        if isinstance(test_size, float):
            test_size = int(n_samples * test_size)
    else:
        test_size = 0
    
    if val_size is not None:
        if isinstance(val_size, float):
            val_size = int(n_samples * val_size)
    else:
        val_size = 0
    
    if train_size is not None:
        if isinstance(train_size, float):
            train_size = int(n_samples * train_size)
    else:
        train_size = n_samples - test_size - val_size - gap * (1 if val_size > 0 else 0) - gap
    
    # Check for valid sizes
    total_size = train_size + val_size + test_size + gap * (1 if val_size > 0 else 0) + gap
    if total_size > n_samples:
        raise ValueError(f"Total size ({total_size}) is greater than the number of samples ({n_samples})")
    
    # Shuffle if requested
    if shuffle:
        if random_state is not None:
            np.random.seed(random_state)
        data_copy = data_copy.sample(frac=1).reset_index(drop=True)
    
    # Determine the split indices
    train_end = train_size
    val_start = train_end + gap
    val_end = val_start + val_size if val_size > 0 else val_start
    test_start = val_end + gap
    test_end = test_start + test_size
    
    # Create the splits
    result = {}
    result['train'] = data_copy.iloc[:train_end]
    
    if val_size > 0:
        result['val'] = data_copy.iloc[val_start:val_end]
    
    if test_size > 0:
        result['test'] = data_copy.iloc[test_start:test_end]
    
    # Convert back to Series if input was Series
    if is_series:
        for key in result.keys():
            result[key] = result[key].iloc[:, 0]
    
    return result

def time_series_cross_validation(data: Union[pd.Series, pd.DataFrame],
                                n_splits: int = 5,
                                train_size: Optional[Union[int, float]] = None,
                                test_size: Union[int, float] = 1,
                                gap: int = 0,
                                expanding_window: bool = True) -> List[Dict[str, Union[pd.Series, pd.DataFrame]]]:
    """
    Create time series cross-validation splits for model evaluation.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Time series data to split
    n_splits : int, optional
        Number of cross-validation splits (default: 5)
    train_size : Optional[Union[int, float]], optional
        Size of initial training window:
        - If int, number of samples
        - If float between 0 and 1, percentage of samples
        - If None, determined by n_splits and test_size
    test_size : Union[int, float], optional
        Size of test window for each split:
        - If int, number of samples
        - If float between 0 and 1, percentage of samples
    gap : int, optional
        Number of samples to skip between train and test sets (default: 0)
    expanding_window : bool, optional
        If True, use expanding window approach, otherwise use sliding window (default: True)
        
    Returns
    -------
    List[Dict[str, Union[pd.Series, pd.DataFrame]]]
        List of dictionaries, each with 'train' and 'test' keys
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import time_series_cross_validation
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=100, freq='D')
    >>> data = pd.DataFrame({
    >>>     'price': np.random.normal(100, 10, 100)
    >>> }, index=dates)
    >>> 
    >>> # Create 5-fold time series cross-validation splits
    >>> cv_splits = time_series_cross_validation(data, n_splits=5, test_size=10)
    >>> for i, split in enumerate(cv_splits):
    >>>     print(f"Split {i+1}:")
    >>>     print(f"  Train: {split['train'].index[0]} to {split['train'].index[-1]}, shape: {split['train'].shape}")
    >>>     print(f"  Test: {split['test'].index[0]} to {split['test'].index[-1]}, shape: {split['test'].shape}")
    """
    logger.info(f"Creating time series cross-validation with {n_splits} splits")
    
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        data = pd.DataFrame(data)
    
    # Make a copy
    data_copy = data.copy()
    
    # Determine number of samples
    n_samples = len(data_copy)
    
    # Calculate absolute sizes
    if isinstance(test_size, float):
        test_size = int(n_samples * test_size)
    
    # Calculate absolute train size if provided
    if train_size is not None:
        if isinstance(train_size, float):
            train_size = int(n_samples * train_size)
    else:
        # Estimate a reasonable train size
        min_train_size = int((n_samples - (n_splits * test_size) - (n_splits * gap)) / n_splits)
        train_size = max(min_train_size, 1)
    
    # Check for valid sizes
    max_samples_needed = train_size + (n_splits * test_size) + (n_splits * gap)
    if max_samples_needed > n_samples:
        raise ValueError(
            f"Not enough samples ({n_samples}) for {n_splits} splits with "
            f"train_size={train_size}, test_size={test_size}, and gap={gap}. "
            f"Need at least {max_samples_needed} samples."
        )
    
    # Create the splits
    splits = []
    
    for i in range(n_splits):
        # Determine split indices
        if expanding_window:
            # Expanding window: Keep all prior data for training
            test_start = train_size + i * (test_size + gap)
        else:
            # Sliding window: Move the training window forward
            test_start = train_size + i * (test_size + gap)
            
        test_end = test_start + test_size
        
        if test_end > n_samples:
            logger.warning(f"Split {i+1} would exceed data length. Stopping at {i} splits.")
            break
        
        # Create the split
        if expanding_window:
            train_data = data_copy.iloc[:test_start-gap]
        else:
            train_start = max(0, test_start - gap - train_size)
            train_data = data_copy.iloc[train_start:test_start-gap]
            
        test_data = data_copy.iloc[test_start:test_end]
        
        split = {
            'train': train_data,
            'test': test_data
        }
        
        # Convert back to Series if input was Series
        if is_series:
            for key in split.keys():
                split[key] = split[key].iloc[:, 0]
        
        splits.append(split)
    
    return splits

def time_series_bootstrap(data: Union[pd.Series, pd.DataFrame],
                         block_size: int,
                         n_bootstraps: int = 100,
                         sample_size: Optional[float] = None,
                         random_state: Optional[int] = None) -> List[Union[pd.Series, pd.DataFrame]]:
    """
    Create bootstrapped samples from time series data using block bootstrap.
    
    Parameters
    ----------
    data : Union[pd.Series, pd.DataFrame]
        Time series data to bootstrap
    block_size : int
        Size of contiguous blocks to sample
    n_bootstraps : int, optional
        Number of bootstrap samples to create (default: 100)
    sample_size : Optional[float], optional
        Size of each bootstrap sample as a fraction of original data size (default: None, same as original)
    random_state : Optional[int], optional
        Random state for reproducibility
        
    Returns
    -------
    List[Union[pd.Series, pd.DataFrame]]
        List of bootstrapped samples
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.data_preprocessing import time_series_bootstrap
    >>> 
    >>> # Create sample time series data
    >>> dates = pd.date_range('2023-01-01', periods=100, freq='D')
    >>> data = pd.DataFrame({
    >>>     'price': np.random.normal(100, 10, 100)
    >>> }, index=dates)
    >>> 
    >>> # Create 10 bootstrap samples with block size 5
    >>> bootstrap_samples = time_series_bootstrap(data, block_size=5, n_bootstraps=10)
    >>> for i, sample in enumerate(bootstrap_samples):
    >>>     print(f"Bootstrap sample {i+1} shape: {sample.shape}")
    """
    logger.info(f"Creating {n_bootstraps} bootstrap samples with block size {block_size}")
    
    # Convert to DataFrame if Series
    is_series = isinstance(data, pd.Series)
    if is_series:
        data = pd.DataFrame(data)
    
    # Make a copy
    data_copy = data.copy()
    
    # Set random state
    if random_state is not None:
        np.random.seed(random_state)
    
    # Determine number of samples
    n_samples = len(data_copy)
    
    # Check block size
    if block_size < 1:
        raise ValueError("block_size must be at least 1")
    if block_size > n_samples:
        raise ValueError(f"block_size ({block_size}) is greater than data length ({n_samples})")
    
    # Determine sample size
    if sample_size is None:
        sample_size = 1.0
    
    # Calculate number of blocks to sample for each bootstrap
    target_size = int(n_samples * sample_size)
    n_blocks = int(np.ceil(target_size / block_size))
    
    # Calculate number of possible starting positions for blocks
    max_start = n_samples - block_size + 1
    
    # Create bootstrap samples
    bootstrap_samples = []
    
    for _ in range(n_bootstraps):
        # Sample block starting positions
        block_starts = np.random.randint(0, max_start, n_blocks)
        
        # Create empty sample
        sample_indices = []
        
        # Fill with blocks
        for start in block_starts:
            sample_indices.extend(range(start, start + block_size))
        
        # Trim to target size if needed
        if len(sample_indices) > target_size:
            sample_indices = sample_indices[:target_size]
        
        # Create the bootstrap sample
        bootstrap_sample = data_copy.iloc[sample_indices].copy()
        
        # Convert back to Series if input was Series
        if is_series:
            bootstrap_sample = bootstrap_sample.iloc[:, 0]
        
        bootstrap_samples.append(bootstrap_sample)
    
    return bootstrap_samples