"""
Order Book Predictor Module

This module provides models for predicting order book dynamics and future states.
These predictive models can be used for:
- Forecasting price movements based on order book patterns
- Predicting order flow and liquidity changes
- Anticipating market regime changes through order book dynamics
- Optimizing execution by predicting future order book states

The module includes:
- Base OrderBookPredictor class defining the interface
- VAR_OrderBookPredictor using Vector Autoregression for linear prediction
- LSTM_OrderBookPredictor using LSTM networks for nonlinear prediction
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Tuple, Any
from abc import ABC, abstractmethod
import logging
import os
import joblib
from datetime import datetime
from statsmodels.tsa.api import VAR
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
import warnings

# Try to import TensorFlow, but handle the case where it's not installed
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model, save_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    warnings.warn("TensorFlow not available. LSTM_OrderBookPredictor will be disabled.")

# Setup logging
logger = logging.getLogger(__name__)

class OrderBookPredictor(ABC):
    """
    Abstract base class for order book prediction models.
    
    This class defines the interface for models that predict future order book states
    or metrics derived from order book data.
    """
    
    def __init__(self, name: str, prediction_horizon: int = 1):
        """
        Initialize the order book predictor.
        
        Args:
            name: Name of the predictor model
            prediction_horizon: Number of steps ahead to predict
        """
        self.name = name
        self.prediction_horizon = prediction_horizon
        self.is_trained = False
        self.metadata = {}
        self.feature_names = []
        self.target_names = []
    
    @abstractmethod
    def predict(self, current_state: pd.DataFrame) -> pd.DataFrame:
        """
        Predict future order book state or metrics.
        
        Args:
            current_state: DataFrame containing current and historical order book metrics
            
        Returns:
            DataFrame with predictions for future states
        """
        pass
    
    @abstractmethod
    def train(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Train the prediction model using historical order book data.
        
        Args:
            data: DataFrame containing time series of order book metrics
            
        Returns:
            Dictionary with training results and metrics
        """
        pass
    
    def save(self, filepath: str) -> None:
        """
        Save the model to disk.
        
        Args:
            filepath: Path where to save the model
        """
        try:
            # Create any needed directories
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Basic info for all models
            model_info = {
                "name": self.name,
                "prediction_horizon": self.prediction_horizon,
                "is_trained": self.is_trained,
                "metadata": self.metadata,
                "feature_names": self.feature_names,
                "target_names": self.target_names,
                "model_type": self.__class__.__name__
            }
            
            # Get model-specific parameters
            model_params = self._get_model_params()
            
            # Save the model info separately
            joblib.dump(model_info, f"{filepath}_info.joblib")
            
            # For simple models, save everything together
            if hasattr(self, "_save_model_separately") and self._save_model_separately():
                self._save_model(filepath)
            else:
                # Include model parameters in the info file
                model_info["model_params"] = model_params
                joblib.dump(model_info, f"{filepath}_info.joblib")
            
            logger.info(f"Order book predictor saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save model: {str(e)}")
            raise
    
    def load(self, filepath: str) -> None:
        """
        Load the model from disk.
        
        Args:
            filepath: Path from where to load the model
        """
        try:
            # Load model info
            model_info = joblib.load(f"{filepath}_info.joblib")
            
            # Load basic info
            self.name = model_info["name"]
            self.prediction_horizon = model_info["prediction_horizon"]
            self.is_trained = model_info["is_trained"]
            self.metadata = model_info["metadata"]
            self.feature_names = model_info["feature_names"]
            self.target_names = model_info["target_names"]
            
            # Load model-specific parameters
            if hasattr(self, "_save_model_separately") and self._save_model_separately():
                self._load_model(filepath)
            else:
                # Load model parameters from the info file
                self._set_model_params(model_info.get("model_params", {}))
            
            logger.info(f"Order book predictor loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise
    
    @abstractmethod
    def _get_model_params(self) -> Dict[str, Any]:
        """Get model parameters for serialization"""
        pass
    
    @abstractmethod
    def _set_model_params(self, params: Dict[str, Any]) -> None:
        """Set model parameters after deserialization"""
        pass
    
    def _save_model_separately(self) -> bool:
        """
        Indicates whether the model should be saved separately from the metadata.
        Override in subclasses if needed.
        """
        return False
    
    def _save_model(self, filepath: str) -> None:
        """
        Save the model separately from metadata.
        Override in subclasses if needed.
        """
        pass
    
    def _load_model(self, filepath: str) -> None:
        """
        Load the model separately from metadata.
        Override in subclasses if needed.
        """
        pass


class VAR_OrderBookPredictor(OrderBookPredictor):
    """
    Order book predictor using Vector Autoregression (VAR).
    
    This model uses a VAR model to capture the linear relationships between
    different order book metrics and predict their future values.
    """
    
    def __init__(self, name: str = "VAR Order Book Predictor", 
                prediction_horizon: int = 1,
                lag_order: int = 5):
        """
        Initialize the VAR-based order book predictor.
        
        Args:
            name: Name of the predictor model
            prediction_horizon: Number of steps ahead to predict
            lag_order: Number of lags to include in the VAR model
        """
        super().__init__(name, prediction_horizon)
        self.lag_order = lag_order
        self.model = None
        self.scaler = StandardScaler()
        self.use_scaling = True
    
    def predict(self, current_state: pd.DataFrame) -> pd.DataFrame:
        """
        Predict future order book metrics using the VAR model.
        
        Args:
            current_state: DataFrame with historical order book metrics
                Must contain at least lag_order rows and all required features
                
        Returns:
            DataFrame with predictions for the next 'prediction_horizon' steps
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model has not been trained yet")
        
        try:
            # Ensure we have the required features
            for feature in self.feature_names:
                if feature not in current_state.columns:
                    raise ValueError(f"Required feature '{feature}' not found in input data")
            
            # Select only the features we need
            data = current_state[self.feature_names].copy()
            
            # Ensure we have enough historical data
            if len(data) < self.lag_order:
                raise ValueError(f"Need at least {self.lag_order} data points, but got {len(data)}")
            
            # Scale the data if needed
            if self.use_scaling:
                data_scaled = self.scaler.transform(data)
                data_scaled_df = pd.DataFrame(data_scaled, index=data.index, columns=data.columns)
            else:
                data_scaled_df = data
            
            # Predict future values
            forecast = self.model.forecast(data_scaled_df.values, steps=self.prediction_horizon)
            
            # Convert to DataFrame
            forecast_df = pd.DataFrame(forecast, columns=self.feature_names)
            
            # Invert scaling if needed
            if self.use_scaling:
                forecast = self.scaler.inverse_transform(forecast)
                forecast_df = pd.DataFrame(forecast, columns=self.feature_names)
            
            # Add timestamps if the input has a datetime index
            if isinstance(current_state.index, pd.DatetimeIndex):
                last_time = current_state.index[-1]
                # Create future timestamps based on the average time delta in the input
                time_deltas = pd.Series(current_state.index).diff().dropna()
                if not time_deltas.empty:
                    avg_delta = time_deltas.mean()
                    future_times = [last_time + (i+1)*avg_delta for i in range(self.prediction_horizon)]
                    forecast_df.index = future_times
            
            return forecast_df
            
        except Exception as e:
            logger.error(f"Error predicting with VAR model: {str(e)}")
            raise
    
    def train(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Train the VAR model using historical order book data.
        
        Args:
            data: DataFrame containing time series of order book metrics
                Each column is a different metric, and each row is a time point
                
        Returns:
            Dictionary with training results and metrics
        """
        try:
            # Store feature names
            self.feature_names = data.columns.tolist()
            self.target_names = data.columns.tolist()
            
            # Scale the data if needed
            if self.use_scaling:
                data_scaled = self.scaler.fit_transform(data)
                data_scaled_df = pd.DataFrame(data_scaled, index=data.index, columns=data.columns)
            else:
                data_scaled_df = data
            
            # Create and fit the VAR model
            model = VAR(data_scaled_df)
            
            # Select lag order if not specified
            if self.lag_order is None:
                # Use AIC to select optimal lag order
                lag_order_results = model.select_order(maxlags=10)
                self.lag_order = lag_order_results.aic
                logger.info(f"Selected lag order: {self.lag_order} based on AIC")
            
            # Fit the model
            self.model = model.fit(maxlags=self.lag_order)
            self.is_trained = True
            
            # Calculate in-sample predictions for evaluation
            in_sample_preds = self.model.fittedvalues
            
            # Calculate metrics (skipping the first lag_order rows that don't have predictions)
            start_idx = self.lag_order
            actual = data_scaled_df.iloc[start_idx:].values
            predicted = in_sample_preds
            
            # If using scaling, convert predictions back to original scale for metrics
            if self.use_scaling:
                predicted = self.scaler.inverse_transform(predicted)
                actual = data.iloc[start_idx:].values
            
            # Calculate metrics for each variable
            mse_values = [mean_squared_error(actual[:, i], predicted[:, i]) for i in range(actual.shape[1])]
            rmse_values = [np.sqrt(mse) for mse in mse_values]
            r2_values = [r2_score(actual[:, i], predicted[:, i]) for i in range(actual.shape[1])]
            
            # Overall metrics
            overall_mse = np.mean(mse_values)
            overall_rmse = np.sqrt(overall_mse)
            overall_r2 = np.mean(r2_values)
            
            # Extract coefficients for interpretability
            try:
                coefficients = {
                    f"equation_{i}": {
                        f"lag_{lag}_{col}": coef 
                        for lag in range(1, self.lag_order + 1)
                        for col, coef in zip(self.feature_names, self.model.coefs[lag-1][i])
                    }
                    for i, equation in enumerate(self.feature_names)
                }
            except Exception as e:
                logger.warning(f"Could not extract coefficients: {str(e)}")
                coefficients = {}
            
            # Store results in metadata
            results = {
                "lag_order": self.lag_order,
                "mse_by_variable": {col: mse for col, mse in zip(self.feature_names, mse_values)},
                "rmse_by_variable": {col: rmse for col, rmse in zip(self.feature_names, rmse_values)},
                "r2_by_variable": {col: r2 for col, r2 in zip(self.feature_names, r2_values)},
                "overall_mse": overall_mse,
                "overall_rmse": overall_rmse,
                "overall_r2": overall_r2,
                "coefficients": coefficients,
                "aic": self.model.aic,
                "bic": self.model.bic,
                "training_data_size": len(data)
            }
            
            self.metadata = {
                "training_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "training_data_shape": data.shape,
                "metrics": results
            }
            
            logger.info(f"VAR model trained with overall R²={overall_r2:.4f}, RMSE={overall_rmse:.6f}")
            return results
            
        except Exception as e:
            logger.error(f"Error training VAR model: {str(e)}")
            raise
    
    def _get_model_params(self) -> Dict[str, Any]:
        """Get model parameters for serialization"""
        return {
            "lag_order": self.lag_order,
            "model": self.model,
            "scaler": self.scaler,
            "use_scaling": self.use_scaling
        }
    
    def _set_model_params(self, params: Dict[str, Any]) -> None:
        """Set model parameters after deserialization"""
        self.lag_order = params.get("lag_order", 5)
        self.model = params.get("model", None)
        self.scaler = params.get("scaler", StandardScaler())
        self.use_scaling = params.get("use_scaling", True)


class LSTM_OrderBookPredictor(OrderBookPredictor):
    """
    Order book predictor using Long Short-Term Memory (LSTM) networks.
    
    This model uses LSTM networks to capture nonlinear temporal patterns in
    order book dynamics for prediction.
    """
    
    def __init__(self, name: str = "LSTM Order Book Predictor", 
                prediction_horizon: int = 1,
                lookback_window: int = 10,
                lstm_units: List[int] = [64, 32],
                dropout_rate: float = 0.2):
        """
        Initialize the LSTM-based order book predictor.
        
        Args:
            name: Name of the predictor model
            prediction_horizon: Number of steps ahead to predict
            lookback_window: Number of past time steps to use for prediction
            lstm_units: List of units in each LSTM layer
            dropout_rate: Dropout rate for regularization
        """
        super().__init__(name, prediction_horizon)
        
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM_OrderBookPredictor but is not installed")
        
        self.lookback_window = lookback_window
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.model = None
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
    
    def predict(self, current_state: pd.DataFrame) -> pd.DataFrame:
        """
        Predict future order book metrics using the LSTM model.
        
        Args:
            current_state: DataFrame with historical order book metrics
                Must contain at least lookback_window rows and all required features
                
        Returns:
            DataFrame with predictions for the next 'prediction_horizon' steps
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model has not been trained yet")
        
        try:
            # Ensure we have the required features
            for feature in self.feature_names:
                if feature not in current_state.columns:
                    raise ValueError(f"Required feature '{feature}' not found in input data")
            
            # Select only the features we need
            data = current_state[self.feature_names].copy()
            
            # Ensure we have enough historical data
            if len(data) < self.lookback_window:
                raise ValueError(f"Need at least {self.lookback_window} data points, but got {len(data)}")
            
            # Scale the data
            data_scaled = self.scaler_X.transform(data)
            
            # Take the last lookback_window points
            input_sequence = data_scaled[-self.lookback_window:].reshape(1, self.lookback_window, len(self.feature_names))
            
            # Predict future values
            predictions_scaled = []
            current_sequence = input_sequence.copy()
            
            for _ in range(self.prediction_horizon):
                # Predict the next step
                next_step = self.model.predict(current_sequence, verbose=0)
                predictions_scaled.append(next_step[0])
                
                # Update the sequence for next prediction (if predicting multiple steps)
                if self.prediction_horizon > 1:
                    # Remove the first time step and append the prediction
                    current_sequence = np.roll(current_sequence, -1, axis=1)
                    current_sequence[0, -1, :] = next_step[0]
            
            # Combine predictions and inverse scale
            predictions_scaled = np.array(predictions_scaled)
            predictions = self.scaler_y.inverse_transform(predictions_scaled)
            
            # Convert to DataFrame
            predictions_df = pd.DataFrame(predictions, columns=self.target_names)
            
            # Add timestamps if the input has a datetime index
            if isinstance(current_state.index, pd.DatetimeIndex):
                last_time = current_state.index[-1]
                # Create future timestamps based on the average time delta in the input
                time_deltas = pd.Series(current_state.index).diff().dropna()
                if not time_deltas.empty:
                    avg_delta = time_deltas.mean()
                    future_times = [last_time + (i+1)*avg_delta for i in range(self.prediction_horizon)]
                    predictions_df.index = future_times
            
            return predictions_df
            
        except Exception as e:
            logger.error(f"Error predicting with LSTM model: {str(e)}")
            raise
    
    def train(self, data: pd.DataFrame, target_columns: Optional[List[str]] = None,
             epochs: int = 50, batch_size: int = 32, validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train the LSTM model using historical order book data.
        
        Args:
            data: DataFrame containing time series of order book metrics
            target_columns: List of column names to predict. If None, predicts all columns.
            epochs: Number of training epochs
            batch_size: Batch size for training
            validation_split: Fraction of data to use for validation
                
        Returns:
            Dictionary with training results and metrics
        """
        try:
            # Store feature names
            self.feature_names = data.columns.tolist()
            
            # Determine target columns
            if target_columns is None:
                target_columns = data.columns.tolist()
            self.target_names = target_columns
            
            # Prepare data
            X, y = self._prepare_sequences(data, target_columns)
            
            # Scale data
            X_scaled = X.reshape(-1, X.shape[2])
            y_scaled = y.reshape(-1, y.shape[1])
            X_scaled = self.scaler_X.fit_transform(X_scaled).reshape(X.shape)
            y_scaled = self.scaler_y.fit_transform(y_scaled).reshape(y.shape)
            
            # Build model
            self._build_model(X_scaled.shape[2], y_scaled.shape[1])
            
            # Use early stopping
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            )
            
            # Train model
            history = self.model.fit(
                X_scaled, y_scaled,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=validation_split,
                callbacks=[early_stopping],
                verbose=0
            )
            
            self.is_trained = True
            
            # Calculate predictions on training data
            y_pred_scaled = self.model.predict(X_scaled, verbose=0)
            
            # Inverse transform for metrics calculation
            y_pred = self.scaler_y.inverse_transform(y_pred_scaled)
            y_true = self.scaler_y.inverse_transform(y_scaled)
            
            # Calculate metrics
            mse_values = [mean_squared_error(y_true[:, i], y_pred[:, i]) for i in range(y_true.shape[1])]
            rmse_values = [np.sqrt(mse) for mse in mse_values]
            r2_values = [r2_score(y_true[:, i], y_pred[:, i]) for i in range(y_true.shape[1])]
            
            # Overall metrics
            overall_mse = np.mean(mse_values)
            overall_rmse = np.sqrt(overall_mse)
            overall_r2 = np.mean(r2_values)
            
            # Extract training history
            train_history = {
                "loss": history.history['loss'],
                "val_loss": history.history['val_loss']
            }
            
            # Store results in metadata
            results = {
                "lookback_window": self.lookback_window,
                "lstm_units": self.lstm_units,
                "dropout_rate": self.dropout_rate,
                "epochs": len(history.history['loss']),
                "batch_size": batch_size,
                "validation_split": validation_split,
                "mse_by_variable": {col: mse for col, mse in zip(self.target_names, mse_values)},
                "rmse_by_variable": {col: rmse for col, rmse in zip(self.target_names, rmse_values)},
                "r2_by_variable": {col: r2 for col, r2 in zip(self.target_names, r2_values)},
                "overall_mse": overall_mse,
                "overall_rmse": overall_rmse,
                "overall_r2": overall_r2,
                "final_loss": history.history['loss'][-1],
                "final_val_loss": history.history['val_loss'][-1],
                "training_history": train_history,
                "training_data_size": len(data)
            }
            
            self.metadata = {
                "training_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "training_data_shape": data.shape,
                "metrics": results
            }
            
            logger.info(f"LSTM model trained with overall R²={overall_r2:.4f}, RMSE={overall_rmse:.6f}")
            return results
            
        except Exception as e:
            logger.error(f"Error training LSTM model: {str(e)}")
            raise
    
    def _prepare_sequences(self, data: pd.DataFrame, target_columns: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare input sequences and target values for LSTM training.
        
        Args:
            data: DataFrame with time series data
            target_columns: Columns to predict
            
        Returns:
            Tuple of (X, y) arrays for training
        """
        # Extract values
        values = data.values
        
        # Create sequences
        X, y = [], []
        for i in range(len(values) - self.lookback_window - self.prediction_horizon + 1):
            X.append(values[i:(i + self.lookback_window)])
            
            # Extract target values
            target_idx = i + self.lookback_window + self.prediction_horizon - 1
            if target_idx < len(values):
                target_values = values[target_idx]
                # Select only target columns
                target_indices = [data.columns.get_loc(col) for col in target_columns]
                y.append(target_values[target_indices])
        
        return np.array(X), np.array(y)
    
    def _build_model(self, n_features: int, n_outputs: int) -> None:
        """
        Build the LSTM model architecture.
        
        Args:
            n_features: Number of input features
            n_outputs: Number of output features to predict
        """
        # Create sequential model
        model = Sequential()
        
        # Add LSTM layers
        for i, units in enumerate(self.lstm_units):
            return_sequences = i < len(self.lstm_units) - 1
            if i == 0:
                model.add(LSTM(
                    units, 
                    activation='tanh',
                    return_sequences=return_sequences,
                    input_shape=(self.lookback_window, n_features)
                ))
            else:
                model.add(LSTM(
                    units,
                    activation='tanh',
                    return_sequences=return_sequences
                ))
            
            # Add dropout for regularization
            model.add(Dropout(self.dropout_rate))
        
        # Add output layer
        model.add(Dense(n_outputs))
        
        # Compile model
        model.compile(optimizer='adam', loss='mse')
        
        self.model = model
    
    def _get_model_params(self) -> Dict[str, Any]:
        """Get model parameters for serialization"""
        return {
            "lookback_window": self.lookback_window,
            "lstm_units": self.lstm_units,
            "dropout_rate": self.dropout_rate,
            "scaler_X": self.scaler_X,
            "scaler_y": self.scaler_y
        }
    
    def _set_model_params(self, params: Dict[str, Any]) -> None:
        """Set model parameters after deserialization"""
        self.lookback_window = params.get("lookback_window", 10)
        self.lstm_units = params.get("lstm_units", [64, 32])
        self.dropout_rate = params.get("dropout_rate", 0.2)
        self.scaler_X = params.get("scaler_X", StandardScaler())
        self.scaler_y = params.get("scaler_y", StandardScaler())
    
    def _save_model_separately(self) -> bool:
        """LSTM models should be saved separately using TensorFlow's save_model"""
        return True
    
    def _save_model(self, filepath: str) -> None:
        """Save the LSTM model separately using TensorFlow's save_model"""
        if self.model is not None:
            model_path = f"{filepath}_keras_model"
            save_model(self.model, model_path)
            
            # Save scalers and other parameters
            params = self._get_model_params()
            joblib.dump(params, f"{filepath}_params.joblib")
    
    def _load_model(self, filepath: str) -> None:
        """Load the LSTM model separately using TensorFlow's load_model"""
        model_path = f"{filepath}_keras_model"
        if os.path.exists(model_path):
            self.model = load_model(model_path)
            
            # Load parameters
            params = joblib.load(f"{filepath}_params.joblib")
            self._set_model_params(params) 