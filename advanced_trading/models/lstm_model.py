"""
LSTM Model Module
-----------------
Advanced LSTM model implementation for time series forecasting with cryptocurrency data.
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any, Union, Optional
from pathlib import Path
import json
import joblib
import matplotlib.pyplot as plt

# TensorFlow imports
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model, save_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization, Bidirectional
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from tensorflow.keras.optimizers import Adam
from sklearn.preprocessing import MinMaxScaler, StandardScaler

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

import config

# Set up logging
logger = logging.getLogger(__name__)

class LSTMModel:
    """
    Advanced LSTM model for time series forecasting of cryptocurrency prices.
    
    Features:
    - Configurable architecture (layers, units, dropout)
    - Multiple prediction modes (next-point, sequence)
    - Feature normalization and preprocessing
    - Model saving/loading
    - Performance evaluation
    """
    
    def __init__(self, 
                config: Dict[str, Any] = None,
                sequence_length: int = 60,
                prediction_horizon: int = 1,
                features: List[str] = None,
                target: str = 'close'):
        """
        Initialize the LSTM model with configuration.
        
        Args:
            config: Model configuration
            sequence_length: Number of past time steps to use as input
            prediction_horizon: Number of future time steps to predict
            features: List of feature columns to use
            target: Target column to predict
        """
        # Set default configuration
        self.default_config = {
            'layers': 2,                # Number of LSTM layers
            'units': [128, 64],         # Units in each layer
            'dropout': 0.2,             # Dropout rate
            'batch_size': 32,           # Batch size for training
            'epochs': 100,              # Maximum epochs
            'patience': 10,             # Early stopping patience
            'learning_rate': 0.001,     # Learning rate
            'bidirectional': False,     # Whether to use bidirectional LSTM
            'batch_norm': True,         # Whether to use batch normalization
            'loss': 'mean_squared_error', # Loss function
            'optimizer': 'adam'         # Optimizer
        }
        
        # Update with provided config
        self.config = self.default_config.copy()
        if config is not None:
            self.config.update(config)
        
        # Model parameters
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.features = features if features is not None else ['close', 'volume', 'open', 'high', 'low']
        self.target = target
        
        # Initialize model artifacts
        self.model = None
        self.feature_scaler = None
        self.target_scaler = None
        self.history = None
        
        logger.info(f"Initialized LSTM model with {self.config['layers']} layers, "
                  f"sequence length {self.sequence_length}, "
                  f"prediction horizon {self.prediction_horizon}")
    
    def _build_model(self, input_shape: Tuple) -> Sequential:
        """
        Build the LSTM model architecture.
        
        Args:
            input_shape: Shape of input data
            
        Returns:
            Compiled Keras model
        """
        model = Sequential()
        
        # Configure LSTM layers
        for i in range(self.config['layers']):
            # First layer
            if i == 0:
                if self.config['bidirectional']:
                    model.add(Bidirectional(
                        LSTM(self.config['units'][i], return_sequences=(i < self.config['layers'] - 1)),
                        input_shape=input_shape
                    ))
                else:
                    model.add(LSTM(
                        self.config['units'][i], 
                        return_sequences=(i < self.config['layers'] - 1),
                        input_shape=input_shape
                    ))
            # Middle and last layers
            else:
                if self.config['bidirectional']:
                    model.add(Bidirectional(
                        LSTM(self.config['units'][i], return_sequences=(i < self.config['layers'] - 1))
                    ))
                else:
                    model.add(LSTM(
                        self.config['units'][i], 
                        return_sequences=(i < self.config['layers'] - 1)
                    ))
            
            # Add batch normalization if configured
            if self.config['batch_norm']:
                model.add(BatchNormalization())
            
            # Add dropout after each LSTM layer
            model.add(Dropout(self.config['dropout']))
        
        # Output layer
        model.add(Dense(self.prediction_horizon))
        
        # Compile the model
        model.compile(
            optimizer=Adam(learning_rate=self.config['learning_rate']),
            loss=self.config['loss'],
            metrics=['mae']
        )
        
        return model
    
    def _prepare_data(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare data for LSTM model.
        
        Args:
            data: DataFrame with features and target
            
        Returns:
            Tuple of (X, y) for model training/prediction
        """
        # Create feature set
        feature_data = data[self.features].values
        target_data = data[[self.target]].values
        
        # Initialize scalers if not already
        if self.feature_scaler is None:
            self.feature_scaler = MinMaxScaler(feature_range=(0, 1))
            self.feature_scaler.fit(feature_data)
        
        if self.target_scaler is None:
            self.target_scaler = MinMaxScaler(feature_range=(0, 1))
            self.target_scaler.fit(target_data)
        
        # Scale data
        scaled_features = self.feature_scaler.transform(feature_data)
        scaled_target = self.target_scaler.transform(target_data)
        
        # Create sequences
        X, y = [], []
        for i in range(len(scaled_features) - self.sequence_length - self.prediction_horizon + 1):
            # Feature sequence
            X.append(scaled_features[i:(i + self.sequence_length)])
            
            # Target value(s)
            if self.prediction_horizon == 1:
                y.append(scaled_target[i + self.sequence_length])
            else:
                y.append(scaled_target[i + self.sequence_length:i + self.sequence_length + self.prediction_horizon])
        
        return np.array(X), np.array(y)
    
    def train(self, data: pd.DataFrame, validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train the LSTM model.
        
        Args:
            data: DataFrame with features and target
            validation_split: Portion of data to use for validation
            
        Returns:
            Training history
        """
        logger.info(f"Training LSTM model on {len(data)} data points with {len(self.features)} features")
        
        # Prepare data
        X, y = self._prepare_data(data)
        
        if len(X) == 0 or len(y) == 0:
            logger.error("Not enough data to train model after sequence preparation")
            return None
        
        logger.info(f"Prepared {len(X)} sequences for training")
        
        # Build model if not already built
        if self.model is None:
            input_shape = (X.shape[1], X.shape[2])
            self.model = self._build_model(input_shape)
        
        # Define callbacks
        callbacks = [
            EarlyStopping(
                monitor='val_loss',
                patience=self.config['patience'],
                restore_best_weights=True
            ),
            ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6
            )
        ]
        
        # Train model
        self.history = self.model.fit(
            X, y,
            epochs=self.config['epochs'],
            batch_size=self.config['batch_size'],
            validation_split=validation_split,
            callbacks=callbacks,
            verbose=1
        )
        
        logger.info(f"Model training completed. Final loss: {self.history.history['loss'][-1]:.4f}, "
                  f"Val loss: {self.history.history['val_loss'][-1]:.4f}")
        
        return self.history.history
    
    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """
        Generate predictions using the trained model.
        
        Args:
            data: DataFrame with features
            
        Returns:
            Array of predictions
        """
        if self.model is None:
            logger.error("Model not trained. Call train() first.")
            return None
        
        # Prepare input data
        if len(data) < self.sequence_length:
            logger.error(f"Not enough data for prediction. Need at least {self.sequence_length} points.")
            return None
        
        # Get the most recent sequence
        feature_data = data[self.features].values
        scaled_features = self.feature_scaler.transform(feature_data)
        
        # Create sequence
        X = np.array([scaled_features[-self.sequence_length:]])
        
        # Make prediction
        scaled_prediction = self.model.predict(X)
        
        # Inverse transform
        prediction = self.target_scaler.inverse_transform(scaled_prediction)
        
        return prediction
    
    def evaluate(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        Evaluate model performance on test data.
        
        Args:
            data: Test data DataFrame
            
        Returns:
            Dictionary of evaluation metrics
        """
        if self.model is None:
            logger.error("Model not trained. Call train() first.")
            return None
        
        # Prepare test data
        X, y_true = self._prepare_data(data)
        
        # Make predictions
        y_pred = self.model.predict(X)
        
        # Calculate metrics
        mse = np.mean((y_pred - y_true) ** 2)
        mae = np.mean(np.abs(y_pred - y_true))
        
        # Inverse transform for RMSE in original scale
        y_true_inv = self.target_scaler.inverse_transform(y_true)
        y_pred_inv = self.target_scaler.inverse_transform(y_pred)
        
        rmse = np.sqrt(np.mean((y_pred_inv - y_true_inv) ** 2))
        
        # Calculate directional accuracy
        direction_true = np.sign(y_true[1:] - y_true[:-1])
        direction_pred = np.sign(y_pred[1:] - y_pred[:-1])
        directional_accuracy = np.mean(direction_true == direction_pred)
        
        metrics = {
            'mse': float(mse),
            'mae': float(mae),
            'rmse': float(rmse),
            'directional_accuracy': float(directional_accuracy)
        }
        
        logger.info(f"Model evaluation: RMSE={rmse:.4f}, Direction Accuracy={directional_accuracy:.4f}")
        
        return metrics
    
    def save(self, path: str) -> None:
        """
        Save the model and scalers.
        
        Args:
            path: Directory path to save model
        """
        if self.model is None:
            logger.error("No model to save. Train model first.")
            return
        
        # Create directory if it doesn't exist
        os.makedirs(path, exist_ok=True)
        
        # Save model
        model_path = os.path.join(path, 'lstm_model.h5')
        self.model.save(model_path)
        
        # Save scalers
        scalers = {
            'feature_scaler': self.feature_scaler,
            'target_scaler': self.target_scaler
        }
        scaler_path = os.path.join(path, 'scalers.joblib')
        joblib.dump(scalers, scaler_path)
        
        # Save configuration
        config_path = os.path.join(path, 'config.json')
        with open(config_path, 'w') as f:
            json.dump({
                'config': self.config,
                'sequence_length': self.sequence_length,
                'prediction_horizon': self.prediction_horizon,
                'features': self.features,
                'target': self.target
            }, f, indent=4)
        
        logger.info(f"Model and configuration saved to {path}")
    
    def load(self, path: str) -> bool:
        """
        Load the model and scalers.
        
        Args:
            path: Directory path to load model from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load model
            model_path = os.path.join(path, 'lstm_model.h5')
            self.model = load_model(model_path)
            
            # Load scalers
            scaler_path = os.path.join(path, 'scalers.joblib')
            scalers = joblib.load(scaler_path)
            self.feature_scaler = scalers['feature_scaler']
            self.target_scaler = scalers['target_scaler']
            
            # Load configuration
            config_path = os.path.join(path, 'config.json')
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                self.config = loaded_config['config']
                self.sequence_length = loaded_config['sequence_length']
                self.prediction_horizon = loaded_config['prediction_horizon']
                self.features = loaded_config['features']
                self.target = loaded_config['target']
            
            logger.info(f"Model loaded from {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False
    
    def plot_training_history(self) -> None:
        """Plot training history."""
        if self.history is None:
            logger.error("No training history available.")
            return
        
        # Create figure
        plt.figure(figsize=(12, 5))
        
        # Plot training & validation loss
        plt.subplot(1, 2, 1)
        plt.plot(self.history.history['loss'], label='Train')
        plt.plot(self.history.history['val_loss'], label='Validation')
        plt.title('Model Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.legend()
        
        # Plot training & validation MAE
        plt.subplot(1, 2, 2)
        plt.plot(self.history.history['mae'], label='Train')
        plt.plot(self.history.history['val_mae'], label='Validation')
        plt.title('Model MAE')
        plt.xlabel('Epoch')
        plt.ylabel('MAE')
        plt.legend()
        
        plt.tight_layout()
        plt.show()
    
    def forecast(self, data: pd.DataFrame, steps: int) -> pd.DataFrame:
        """
        Generate multi-step forecast.
        
        Args:
            data: Input data
            steps: Number of steps to forecast
            
        Returns:
            DataFrame with forecasted values
        """
        if self.model is None:
            logger.error("Model not trained. Call train() first.")
            return None
        
        # Get last sequence from data
        if len(data) < self.sequence_length:
            logger.error(f"Not enough data for forecasting. Need at least {self.sequence_length} points.")
            return None
        
        # Initialize with latest data
        forecast_data = data.copy().tail(self.sequence_length)
        last_sequence = data[self.features].values[-self.sequence_length:]
        last_sequence_scaled = self.feature_scaler.transform(last_sequence)
        
        # Iteratively predict next steps
        forecasts = []
        current_sequence = last_sequence_scaled.copy()
        
        for _ in range(steps):
            # Reshape for model input
            X = np.array([current_sequence])
            
            # Predict next value
            next_scaled = self.model.predict(X)[0]
            
            # Store the predicted value
            next_value = self.target_scaler.inverse_transform(next_scaled.reshape(1, -1))[0]
            forecasts.append(next_value[0])
            
            # Update sequence for next prediction by removing oldest and adding newest prediction
            # For simplicity, we assume the predicted value is for the target column only
            # In a real system, you'd need to estimate the other features too
            
            # Create a new row with the latest known values
            last_known_row = current_sequence[-1].copy()
            
            # Update the target column value with our prediction
            target_idx = self.features.index(self.target)
            last_known_row[target_idx] = next_scaled[0]
            
            # Add to sequence and drop the oldest entry
            current_sequence = np.vstack([current_sequence[1:], last_known_row])
        
        # Create forecast DataFrame
        dates = pd.date_range(
            start=data.index[-1] + pd.Timedelta('1d'),
            periods=steps,
            freq='D'
        )
        
        forecast_df = pd.DataFrame({
            self.target: forecasts
        }, index=dates)
        
        return forecast_df 