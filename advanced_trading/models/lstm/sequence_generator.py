"""
Sequence Generator Module
-----------------------
This module provides functionality for generating sequences from time series data
for LSTM models. It includes:

1. Time series to sequence conversion
2. Various sequence generation strategies (sliding window, expanding window, etc.)
3. Feature normalization and standardization
4. Sequence padding and masking
5. Batch generation for training
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Union, Optional, Callable, Any
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import logging

# Configure logging
logger = logging.getLogger(__name__)

class SequenceGenerator:
    """
    Class for generating sequences from time series data for LSTM models.
    
    This class provides methods for:
    - Converting time series data to sequences
    - Normalizing/standardizing features
    - Generating batches for training
    - Creating train/test splits with proper time ordering
    """
    
    def __init__(
        self,
        sequence_length: int = 20,
        forecast_horizon: int = 1,
        step_size: int = 1,
        target_column: Optional[str] = None,
        feature_columns: Optional[List[str]] = None,
        normalize: bool = True,
        normalization_method: str = 'standard',
        include_target_as_feature: bool = False,
        batch_size: int = 32,
        shuffle: bool = False,
        random_state: Optional[int] = None
    ):
        """
        Initialize the SequenceGenerator.
        
        Parameters
        ----------
        sequence_length : int, default=20
            Length of the input sequences (lookback period)
        forecast_horizon : int, default=1
            Number of steps to forecast into the future
        step_size : int, default=1
            Step size between consecutive sequences
        target_column : str, optional
            Name of the target column. If None, the last column is used as target
        feature_columns : List[str], optional
            List of feature column names. If None, all columns except target are used
        normalize : bool, default=True
            Whether to normalize/standardize the features
        normalization_method : str, default='standard'
            Method for normalization: 'standard', 'minmax', or 'robust'
        include_target_as_feature : bool, default=False
            Whether to include the target column as a feature
        batch_size : int, default=32
            Batch size for training
        shuffle : bool, default=False
            Whether to shuffle the sequences (only for training)
        random_state : int, optional
            Random state for reproducibility
        """
        self.sequence_length = sequence_length
        self.forecast_horizon = forecast_horizon
        self.step_size = step_size
        self.target_column = target_column
        self.feature_columns = feature_columns
        self.normalize = normalize
        self.normalization_method = normalization_method
        self.include_target_as_feature = include_target_as_feature
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.random_state = random_state
        
        # Initialize scalers
        self.feature_scaler = None
        self.target_scaler = None
        
        # Initialize random number generator
        self.rng = np.random.RandomState(random_state) if random_state is not None else np.random
        
        logger.info(f"Initialized SequenceGenerator with sequence_length={sequence_length}, "
                   f"forecast_horizon={forecast_horizon}, step_size={step_size}")
    
    def fit(self, data: pd.DataFrame) -> 'SequenceGenerator':
        """
        Fit the sequence generator to the data.
        
        This method prepares the feature and target columns and fits the scalers
        if normalization is enabled.
        
        Parameters
        ----------
        data : pd.DataFrame
            The time series data
            
        Returns
        -------
        self : SequenceGenerator
            The fitted sequence generator
        """
        # Validate data
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Data must be a pandas DataFrame")
        
        if len(data) <= self.sequence_length + self.forecast_horizon:
            raise ValueError(f"Data length ({len(data)}) must be greater than "
                           f"sequence_length ({self.sequence_length}) + "
                           f"forecast_horizon ({self.forecast_horizon})")
        
        # Determine target column
        if self.target_column is None:
            self.target_column = data.columns[-1]
            logger.info(f"No target column specified, using last column: {self.target_column}")
        elif self.target_column not in data.columns:
            raise ValueError(f"Target column '{self.target_column}' not found in data")
        
        # Determine feature columns
        if self.feature_columns is None:
            if self.include_target_as_feature:
                self.feature_columns = list(data.columns)
            else:
                self.feature_columns = [col for col in data.columns if col != self.target_column]
            logger.info(f"No feature columns specified, using: {self.feature_columns}")
        else:
            # Validate feature columns
            missing_cols = [col for col in self.feature_columns if col not in data.columns]
            if missing_cols:
                raise ValueError(f"Feature columns {missing_cols} not found in data")
        
        # Fit scalers if normalization is enabled
        if self.normalize:
            if self.normalization_method == 'standard':
                self.feature_scaler = StandardScaler()
                self.target_scaler = StandardScaler()
            elif self.normalization_method == 'minmax':
                self.feature_scaler = MinMaxScaler()
                self.target_scaler = MinMaxScaler()
            elif self.normalization_method == 'robust':
                from sklearn.preprocessing import RobustScaler
                self.feature_scaler = RobustScaler()
                self.target_scaler = RobustScaler()
            else:
                raise ValueError(f"Unknown normalization method: {self.normalization_method}")
            
            # Fit feature scaler
            self.feature_scaler.fit(data[self.feature_columns])
            
            # Fit target scaler (reshape for 1D case)
            self.target_scaler.fit(data[[self.target_column]])
            
            logger.info(f"Fitted scalers using {self.normalization_method} normalization")
        
        return self
    
    def transform(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Transform the data into sequences for LSTM models.
        
        Parameters
        ----------
        data : pd.DataFrame
            The time series data
            
        Returns
        -------
        X : np.ndarray
            The input sequences with shape (n_samples, sequence_length, n_features)
        y : np.ndarray
            The target values with shape (n_samples, forecast_horizon) or (n_samples,)
        """
        # Validate data
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Data must be a pandas DataFrame")
        
        if len(data) <= self.sequence_length + self.forecast_horizon:
            raise ValueError(f"Data length ({len(data)}) must be greater than "
                           f"sequence_length ({self.sequence_length}) + "
                           f"forecast_horizon ({self.forecast_horizon})")
        
        # Extract features and target
        features = data[self.feature_columns].values
        target = data[self.target_column].values
        
        # Normalize if enabled
        if self.normalize and self.feature_scaler is not None and self.target_scaler is not None:
            features = self.feature_scaler.transform(features)
            target = self.target_scaler.transform(data[[self.target_column]]).flatten()
        
        # Generate sequences
        X, y = self._generate_sequences(features, target)
        
        return X, y
    
    def fit_transform(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fit the sequence generator to the data and transform it.
        
        Parameters
        ----------
        data : pd.DataFrame
            The time series data
            
        Returns
        -------
        X : np.ndarray
            The input sequences with shape (n_samples, sequence_length, n_features)
        y : np.ndarray
            The target values with shape (n_samples, forecast_horizon) or (n_samples,)
        """
        return self.fit(data).transform(data)
    
    def inverse_transform_y(self, y: np.ndarray) -> np.ndarray:
        """
        Inverse transform the target values.
        
        Parameters
        ----------
        y : np.ndarray
            The normalized target values
            
        Returns
        -------
        np.ndarray
            The original scale target values
        """
        if not self.normalize or self.target_scaler is None:
            return y
        
        # Reshape for inverse transform if needed
        if y.ndim == 1:
            y_reshaped = y.reshape(-1, 1)
        else:
            y_reshaped = y
        
        return self.target_scaler.inverse_transform(y_reshaped)
    
    def inverse_transform_X(self, X: np.ndarray) -> np.ndarray:
        """
        Inverse transform the feature values.
        
        Parameters
        ----------
        X : np.ndarray
            The normalized feature values with shape (n_samples, sequence_length, n_features)
            
        Returns
        -------
        np.ndarray
            The original scale feature values
        """
        if not self.normalize or self.feature_scaler is None:
            return X
        
        # Get original shape
        n_samples, seq_len, n_features = X.shape
        
        # Reshape to 2D for inverse transform
        X_reshaped = X.reshape(-1, n_features)
        
        # Inverse transform
        X_inv = self.feature_scaler.inverse_transform(X_reshaped)
        
        # Reshape back to original shape
        return X_inv.reshape(n_samples, seq_len, n_features)
    
    def _generate_sequences(self, features: np.ndarray, target: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate sequences from the features and target arrays.
        
        Parameters
        ----------
        features : np.ndarray
            The feature values with shape (n_samples, n_features)
        target : np.ndarray
            The target values with shape (n_samples,)
            
        Returns
        -------
        X : np.ndarray
            The input sequences with shape (n_sequences, sequence_length, n_features)
        y : np.ndarray
            The target values with shape (n_sequences, forecast_horizon) or (n_sequences,)
        """
        n_samples, n_features = features.shape
        
        # Calculate number of sequences
        n_sequences = (n_samples - self.sequence_length - self.forecast_horizon + 1) // self.step_size
        
        # Initialize arrays
        X = np.zeros((n_sequences, self.sequence_length, n_features))
        
        if self.forecast_horizon == 1:
            y = np.zeros(n_sequences)
        else:
            y = np.zeros((n_sequences, self.forecast_horizon))
        
        # Generate sequences
        for i in range(n_sequences):
            start_idx = i * self.step_size
            end_idx = start_idx + self.sequence_length
            
            # Input sequence
            X[i] = features[start_idx:end_idx]
            
            # Target value(s)
            if self.forecast_horizon == 1:
                y[i] = target[end_idx]
            else:
                y[i] = target[end_idx:end_idx + self.forecast_horizon]
        
        return X, y
    
    def train_test_split(
        self,
        data: pd.DataFrame,
        test_size: float = 0.2,
        validation_size: Optional[float] = None
    ) -> Union[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
               Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        """
        Split the data into train and test sets, optionally including a validation set.
        
        This method ensures that the time ordering is preserved, with the test set
        containing the most recent data.
        
        Parameters
        ----------
        data : pd.DataFrame
            The time series data
        test_size : float, default=0.2
            Proportion of the data to include in the test set
        validation_size : float, optional
            Proportion of the data to include in the validation set
            
        Returns
        -------
        Union[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
               Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]
            X_train, y_train, X_test, y_test or
            X_train, y_train, X_val, y_val, X_test, y_test
        """
        # Fit the sequence generator if not already fitted
        if self.feature_scaler is None and self.normalize:
            self.fit(data)
        
        # Calculate split indices
        n_samples = len(data)
        test_idx = int(n_samples * (1 - test_size))
        
        if validation_size is not None:
            val_idx = int(n_samples * (1 - test_size - validation_size))
            
            # Split data
            train_data = data.iloc[:val_idx]
            val_data = data.iloc[val_idx:test_idx]
            test_data = data.iloc[test_idx:]
            
            # Transform each split
            X_train, y_train = self.transform(train_data)
            X_val, y_val = self.transform(val_data)
            X_test, y_test = self.transform(test_data)
            
            return X_train, y_train, X_val, y_val, X_test, y_test
        else:
            # Split data
            train_data = data.iloc[:test_idx]
            test_data = data.iloc[test_idx:]
            
            # Transform each split
            X_train, y_train = self.transform(train_data)
            X_test, y_test = self.transform(test_data)
            
            return X_train, y_train, X_test, y_test
    
    def batch_generator(
        self,
        X: np.ndarray,
        y: np.ndarray,
        batch_size: Optional[int] = None,
        shuffle: Optional[bool] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate batches for training.
        
        Parameters
        ----------
        X : np.ndarray
            The input sequences
        y : np.ndarray
            The target values
        batch_size : int, optional
            Batch size. If None, uses the value specified in the constructor
        shuffle : bool, optional
            Whether to shuffle the sequences. If None, uses the value specified in the constructor
            
        Yields
        ------
        Tuple[np.ndarray, np.ndarray]
            Batch of input sequences and target values
        """
        # Use instance values if not specified
        batch_size = batch_size or self.batch_size
        shuffle = self.shuffle if shuffle is None else shuffle
        
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        if shuffle:
            self.rng.shuffle(indices)
        
        # Generate batches
        for start_idx in range(0, n_samples, batch_size):
            end_idx = min(start_idx + batch_size, n_samples)
            batch_indices = indices[start_idx:end_idx]
            
            yield X[batch_indices], y[batch_indices]
    
    def create_stateful_dataset(
        self,
        data: pd.DataFrame,
        batch_size: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create a dataset for stateful LSTM models.
        
        For stateful LSTMs, the batch size must be fixed and the number of samples
        must be divisible by the batch size.
        
        Parameters
        ----------
        data : pd.DataFrame
            The time series data
        batch_size : int
            Batch size for the stateful LSTM
            
        Returns
        -------
        X : np.ndarray
            The input sequences with shape (n_samples, sequence_length, n_features)
        y : np.ndarray
            The target values with shape (n_samples, forecast_horizon) or (n_samples,)
        """
        # Fit the sequence generator if not already fitted
        if self.feature_scaler is None and self.normalize:
            self.fit(data)
        
        # Transform data
        X, y = self.transform(data)
        
        # Adjust number of samples to be divisible by batch_size
        n_samples = (len(X) // batch_size) * batch_size
        X = X[:n_samples]
        y = y[:n_samples]
        
        return X, y
    
    def create_multi_step_forecast_dataset(
        self,
        data: pd.DataFrame,
        forecast_steps: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create a dataset for multi-step forecasting.
        
        Parameters
        ----------
        data : pd.DataFrame
            The time series data
        forecast_steps : int
            Number of steps to forecast
            
        Returns
        -------
        X : np.ndarray
            The input sequences with shape (n_samples, sequence_length, n_features)
        y : np.ndarray
            The target values with shape (n_samples, forecast_steps)
        """
        # Save original forecast horizon
        original_horizon = self.forecast_horizon
        
        # Set forecast horizon to the desired number of steps
        self.forecast_horizon = forecast_steps
        
        # Fit and transform data
        X, y = self.fit_transform(data)
        
        # Restore original forecast horizon
        self.forecast_horizon = original_horizon
        
        return X, y 