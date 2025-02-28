"""
LSTM Model Module
-----------------
Provides LSTM model implementation for time series forecasting
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any, Union
from pathlib import Path

import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model, save_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.preprocessing import MinMaxScaler

import config

logger = logging.getLogger(__name__)

class LSTMModel:
    """LSTM model for price prediction with multiple features"""
    
    def __init__(self, sequence_length: int = 60, prediction_horizon: int = 1):
        """
        Initialize the LSTM model
        
        Args:
            sequence_length: Number of time steps to use for each prediction
            prediction_horizon: Number of time steps to predict into the future
        """
        self.model = None
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.price_scaler = MinMaxScaler(feature_range=(0, 1))
        self.feature_scaler = MinMaxScaler(feature_range=(0, 1))
        
        # Set GPU memory limit if available
        if config.GPU_CONFIG['use_gpu']:
            try:
                gpus = tf.config.list_physical_devices('GPU')
                if gpus:
                    # Limit GPU memory usage
                    for gpu in gpus:
                        tf.config.experimental.set_memory_growth(gpu, True)
                    logger.info(f"GPU available: {len(gpus)}")
                else:
                    logger.warning("No GPU found, using CPU")
            except Exception as e:
                logger.error(f"Error configuring GPU: {str(e)}")
    
    def preprocess_data(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess data for LSTM model
        
        Args:
            data: DataFrame with time series data
        
        Returns:
            Tuple of (X, y) arrays for training
        """
        if len(data) <= self.sequence_length:
            logger.error(f"Not enough data points. Need more than {self.sequence_length}")
            return np.array([]), np.array([])
        
        # Extract price data (target variable)
        if 'close' in data.columns:
            price_data = data['close'].values.reshape(-1, 1)
            price_scaled = self.price_scaler.fit_transform(price_data)
        else:
            logger.error("No 'close' column found in data")
            return np.array([]), np.array([])
        
        # Extract features (if any)
        feature_columns = [col for col in data.columns 
                          if col not in ['close', 'open', 'high', 'low', 'volume']]
        
        features = None
        if feature_columns:
            features = data[feature_columns].values
            features_scaled = self.feature_scaler.fit_transform(features)
        
        # Create sequences
        X, y = [], []
        for i in range(self.sequence_length, len(price_scaled) - self.prediction_horizon + 1):
            # Price sequence
            price_seq = price_scaled[i-self.sequence_length:i, 0]
            
            # Feature sequence if available
            if features is not None:
                feature_seq = features_scaled[i-self.sequence_length:i, :]
                # Combine price with features
                seq = np.column_stack((price_seq.reshape(-1, 1), feature_seq))
            else:
                seq = price_seq.reshape(-1, 1)
            
            # Target is the price 'prediction_horizon' steps ahead
            target = price_scaled[i + self.prediction_horizon - 1, 0]
            
            X.append(seq)
            y.append(target)
        
        return np.array(X), np.array(y)
    
    def build_model(self, input_shape: Tuple[int, ...]) -> Sequential:
        """
        Build LSTM model architecture
        
        Args:
            input_shape: Shape of input data (sequence_length, features)
        
        Returns:
            Compiled Keras model
        """
        model = Sequential()
        
        # First LSTM layer with return sequences for stacking
        model.add(LSTM(units=100, return_sequences=True, input_shape=input_shape))
        model.add(Dropout(0.2))
        
        # Second LSTM layer
        model.add(LSTM(units=50))
        model.add(Dropout(0.2))
        
        # Output layer
        model.add(Dense(units=1))
        
        # Compile model
        model.compile(optimizer='adam', loss='mean_squared_error')
        
        return model
    
    def train(self, data: pd.DataFrame, validation_split: float = 0.2, 
              epochs: int = 50, batch_size: int = 32) -> Dict[str, Any]:
        """
        Train the LSTM model
        
        Args:
            data: DataFrame with time series data
            validation_split: Fraction of data to use for validation
            epochs: Number of training epochs
            batch_size: Batch size for training
        
        Returns:
            Training history
        """
        try:
            # Preprocess data
            X, y = self.preprocess_data(data)
            
            if len(X) == 0 or len(y) == 0:
                logger.error("Failed to preprocess data")
                return {"success": False, "error": "Failed to preprocess data"}
            
            # Build model
            self.model = self.build_model(X.shape[1:])
            
            # Early stopping to prevent overfitting
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            )
            
            # Train model
            history = self.model.fit(
                X, y,
                validation_split=validation_split,
                epochs=epochs,
                batch_size=batch_size,
                callbacks=[early_stopping],
                verbose=1
            )
            
            logger.info(f"Model trained. Final loss: {history.history['loss'][-1]}, "
                        f"Validation loss: {history.history['val_loss'][-1]}")
            
            return {
                "success": True,
                "loss": history.history['loss'],
                "val_loss": history.history['val_loss'],
                "epochs_completed": len(history.history['loss'])
            }
            
        except Exception as e:
            logger.error(f"Error training LSTM model: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def predict(self, data: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Generate price predictions using the trained model
        
        Args:
            data: DataFrame or array with recent price data
        
        Returns:
            Array of predicted prices for the next 'prediction_horizon' time steps
        """
        try:
            if self.model is None:
                logger.error("Model not trained")
                return np.array([])
            
            # Prepare input data
            if isinstance(data, pd.DataFrame):
                # Extract required columns
                if 'close' in data.columns:
                    price_data = data['close'].values.reshape(-1, 1)
                    price_scaled = self.price_scaler.transform(price_data)
                    
                    # Extract features if available
                    feature_columns = [col for col in data.columns 
                                     if col not in ['close', 'open', 'high', 'low', 'volume']]
                    
                    features_scaled = None
                    if feature_columns:
                        features = data[feature_columns].values
                        features_scaled = self.feature_scaler.transform(features)
                    
                    # Get the last sequence
                    price_seq = price_scaled[-self.sequence_length:, 0]
                    
                    if features_scaled is not None:
                        feature_seq = features_scaled[-self.sequence_length:, :]
                        # Combine price with features
                        input_seq = np.column_stack((price_seq.reshape(-1, 1), feature_seq))
                    else:
                        input_seq = price_seq.reshape(-1, 1)
                    
                    # Reshape for LSTM (samples, time steps, features)
                    input_seq = input_seq.reshape(1, input_seq.shape[0], input_seq.shape[1])
                    
                    # Make prediction
                    prediction_scaled = self.model.predict(input_seq)
                    prediction = self.price_scaler.inverse_transform(prediction_scaled)
                    
                    return prediction.flatten()
                else:
                    logger.error("No 'close' column found in data")
                    return np.array([])
            else:
                # Assume numpy array is already preprocessed and shaped correctly
                prediction_scaled = self.model.predict(data)
                prediction = self.price_scaler.inverse_transform(prediction_scaled)
                return prediction.flatten()
                
        except Exception as e:
            logger.error(f"Error making prediction: {str(e)}")
            return np.array([])
    
    def save(self, path: str = None) -> bool:
        """
        Save the model to disk
        
        Args:
            path: Path to save the model
            
        Returns:
            True if successful, False otherwise
        """
        if self.model is None:
            logger.error("No model to save")
            return False
        
        if path is None:
            path = os.path.join(config.MODEL_DIR, "lstm_model.h5")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Save model
            self.model.save(path)
            
            # Save scalers
            scaler_dir = os.path.dirname(path)
            np.save(os.path.join(scaler_dir, "price_scaler.npy"), 
                   self.price_scaler.scale_)
            np.save(os.path.join(scaler_dir, "price_min.npy"),
                   self.price_scaler.min_)
            
            if hasattr(self.feature_scaler, 'scale_'):
                np.save(os.path.join(scaler_dir, "feature_scaler.npy"),
                       self.feature_scaler.scale_)
                np.save(os.path.join(scaler_dir, "feature_min.npy"),
                       self.feature_scaler.min_)
            
            logger.info(f"Model saved to {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            return False
    
    def load(self, path: str = None) -> bool:
        """
        Load the model from disk
        
        Args:
            path: Path to load the model from
            
        Returns:
            True if successful, False otherwise
        """
        if path is None:
            path = os.path.join(config.MODEL_DIR, "lstm_model.h5")
        
        try:
            # Load model
            self.model = load_model(path)
            
            # Load scalers
            scaler_dir = os.path.dirname(path)
            
            # Load price scaler
            price_scale = np.load(os.path.join(scaler_dir, "price_scaler.npy"))
            price_min = np.load(os.path.join(scaler_dir, "price_min.npy"))
            self.price_scaler.scale_ = price_scale
            self.price_scaler.min_ = price_min
            self.price_scaler.data_min_ = price_min
            self.price_scaler.data_max_ = price_min + price_scale
            
            # Load feature scaler if available
            feature_scale_path = os.path.join(scaler_dir, "feature_scaler.npy")
            if os.path.exists(feature_scale_path):
                feature_scale = np.load(feature_scale_path)
                feature_min = np.load(os.path.join(scaler_dir, "feature_min.npy"))
                self.feature_scaler.scale_ = feature_scale
                self.feature_scaler.min_ = feature_min
                self.feature_scaler.data_min_ = feature_min
                self.feature_scaler.data_max_ = feature_min + feature_scale
            
            logger.info(f"Model loaded from {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False