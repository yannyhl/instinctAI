"""
Autoencoder Anomaly Detector
--------------------------
This module provides an implementation of autoencoder-based anomaly detection
for financial time series data.

Autoencoders are neural networks that learn to reconstruct their input data.
When trained on normal data, they will have difficulty reconstructing anomalous
data, which can be used to detect anomalies.

This implementation includes:
1. Standard autoencoder for point anomalies
2. LSTM autoencoder for temporal anomalies
3. Visualization tools for anomaly analysis
4. Integration with the ML Ensemble framework
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict, Union, Optional, Tuple, Any
import logging
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import datetime
import os
import json

# Configure logging
logger = logging.getLogger(__name__)

# Check if TensorFlow is available, otherwise use Keras
try:
    import tensorflow as tf
    from tensorflow.keras.models import Model, Sequential, load_model
    from tensorflow.keras.layers import (
        Input, Dense, Dropout, LSTM, RepeatVector, TimeDistributed,
        Conv1D, MaxPooling1D, UpSampling1D, Flatten, Reshape
    )
    from tensorflow.keras.callbacks import (
        EarlyStopping, ModelCheckpoint, ReduceLROnPlateau,
        TensorBoard, History
    )
    from tensorflow.keras.optimizers import Adam
    KERAS_BACKEND = 'tensorflow'
    logger.info("Using TensorFlow backend for Keras")
except ImportError:
    try:
        from keras.models import Model, Sequential, load_model
        from keras.layers import (
            Input, Dense, Dropout, LSTM, RepeatVector, TimeDistributed,
            Conv1D, MaxPooling1D, UpSampling1D, Flatten, Reshape
        )
        from keras.callbacks import (
            EarlyStopping, ModelCheckpoint, ReduceLROnPlateau,
            TensorBoard, History
        )
        from keras.optimizers import Adam
        KERAS_BACKEND = 'keras'
        logger.info("Using standalone Keras")
    except ImportError:
        logger.error("Neither TensorFlow nor Keras is available. Please install one of them.")
        raise ImportError("Neither TensorFlow nor Keras is available. Please install one of them.") 

class AutoencoderDetector:
    """
    A class for detecting anomalies in financial time series data using autoencoders.
    
    This class provides methods for:
    - Training an autoencoder model on financial data
    - Detecting anomalies in new data
    - Scoring data points based on their reconstruction error
    - Visualizing anomalies in time series data
    - Analyzing anomaly patterns
    """
    
    def __init__(
        self,
        autoencoder_type: str = 'dense',
        sequence_length: int = 20,
        hidden_layers: List[int] = None,
        latent_dim: int = 10,
        dropout_rate: float = 0.2,
        activation: str = 'relu',
        output_activation: str = 'linear',
        learning_rate: float = 0.001,
        loss: str = 'mse',
        contamination: float = 0.1,
        normalize: bool = True,
        normalization_method: str = 'standard',
        random_state: Optional[int] = None,
        verbose: int = 0
    ):
        """
        Initialize the Autoencoder anomaly detector.
        
        Parameters
        ----------
        autoencoder_type : str, default='dense'
            Type of autoencoder to use. Options: 'dense', 'lstm', 'conv'
        sequence_length : int, default=20
            Length of input sequences for LSTM and Conv autoencoders
        hidden_layers : List[int], optional
            List of hidden layer sizes. If None, uses [64, 32] for dense,
            [64, 32] for LSTM, and [32, 16] for Conv autoencoders
        latent_dim : int, default=10
            Dimension of the latent space (bottleneck layer)
        dropout_rate : float, default=0.2
            Dropout rate for regularization
        activation : str, default='relu'
            Activation function for hidden layers
        output_activation : str, default='linear'
            Activation function for output layer
        learning_rate : float, default=0.001
            Learning rate for the optimizer
        loss : str, default='mse'
            Loss function to use for training
        contamination : float, default=0.1
            Expected proportion of outliers in the data
        normalize : bool, default=True
            Whether to normalize the input data
        normalization_method : str, default='standard'
            Method for normalization: 'standard', 'minmax', or 'robust'
        random_state : int, optional
            Random state for reproducibility
        verbose : int, default=0
            Verbosity level (0, 1, or 2)
        """
        self.autoencoder_type = autoencoder_type
        self.sequence_length = sequence_length
        self.hidden_layers = hidden_layers
        self.latent_dim = latent_dim
        self.dropout_rate = dropout_rate
        self.activation = activation
        self.output_activation = output_activation
        self.learning_rate = learning_rate
        self.loss = loss
        self.contamination = contamination
        self.normalize = normalize
        self.normalization_method = normalization_method
        self.random_state = random_state
        self.verbose = verbose
        
        # Set default hidden layers based on autoencoder type
        if self.hidden_layers is None:
            if self.autoencoder_type == 'dense':
                self.hidden_layers = [64, 32]
            elif self.autoencoder_type == 'lstm':
                self.hidden_layers = [64, 32]
            elif self.autoencoder_type == 'conv':
                self.hidden_layers = [32, 16]
        
        # Initialize models
        self.model = None
        self.encoder = None
        self.decoder = None
        self.threshold = None
        self.scaler = None
        
        # Set random seed if provided
        if random_state is not None:
            if KERAS_BACKEND == 'tensorflow':
                tf.random.set_seed(random_state)
            np.random.seed(random_state)
        
        # Validate parameters
        self._validate_parameters()
        
        # Initialize scaler
        if self.normalize:
            if self.normalization_method == 'standard':
                self.scaler = StandardScaler()
            elif self.normalization_method == 'minmax':
                self.scaler = MinMaxScaler()
            elif self.normalization_method == 'robust':
                from sklearn.preprocessing import RobustScaler
                self.scaler = RobustScaler()
        
        logger.info(f"Initialized AutoencoderDetector with type={autoencoder_type}, "
                   f"latent_dim={latent_dim}")
    
    def _validate_parameters(self):
        """Validate model parameters."""
        if self.autoencoder_type not in ['dense', 'lstm', 'conv']:
            raise ValueError(f"autoencoder_type must be 'dense', 'lstm', or 'conv', got {self.autoencoder_type}")
        
        if self.contamination <= 0 or self.contamination >= 0.5:
            raise ValueError(f"contamination must be in (0, 0.5), got {self.contamination}")
        
        if self.normalization_method not in ['standard', 'minmax', 'robust']:
            raise ValueError(f"normalization_method must be 'standard', 'minmax', or 'robust', got {self.normalization_method}")
        
        if self.autoencoder_type in ['lstm', 'conv'] and self.sequence_length <= 0:
            raise ValueError(f"sequence_length must be positive for {self.autoencoder_type} autoencoder, got {self.sequence_length}")
        
        if not isinstance(self.hidden_layers, list) or len(self.hidden_layers) == 0:
            raise ValueError(f"hidden_layers must be a non-empty list, got {self.hidden_layers}")
        
        if self.latent_dim <= 0:
            raise ValueError(f"latent_dim must be positive, got {self.latent_dim}") 

    def _build_dense_autoencoder(self, input_dim: int):
        """
        Build a dense (fully connected) autoencoder.
        
        Parameters
        ----------
        input_dim : int
            Dimension of the input data
            
        Returns
        -------
        Tuple[Model, Model, Model]
            Tuple of (autoencoder, encoder, decoder) models
        """
        # Define encoder
        encoder_inputs = Input(shape=(input_dim,), name='encoder_input')
        x = encoder_inputs
        
        # Add encoder hidden layers
        for i, units in enumerate(self.hidden_layers):
            x = Dense(units, activation=self.activation, name=f'encoder_dense_{i}')(x)
            if self.dropout_rate > 0:
                x = Dropout(self.dropout_rate, name=f'encoder_dropout_{i}')(x)
        
        # Add bottleneck layer
        latent = Dense(self.latent_dim, activation=self.activation, name='bottleneck')(x)
        
        # Define encoder model
        encoder = Model(encoder_inputs, latent, name='encoder')
        
        # Define decoder
        decoder_inputs = Input(shape=(self.latent_dim,), name='decoder_input')
        x = decoder_inputs
        
        # Add decoder hidden layers (in reverse order)
        for i, units in enumerate(reversed(self.hidden_layers)):
            x = Dense(units, activation=self.activation, name=f'decoder_dense_{i}')(x)
            if self.dropout_rate > 0:
                x = Dropout(self.dropout_rate, name=f'decoder_dropout_{i}')(x)
        
        # Add output layer
        decoder_outputs = Dense(input_dim, activation=self.output_activation, name='decoder_output')(x)
        
        # Define decoder model
        decoder = Model(decoder_inputs, decoder_outputs, name='decoder')
        
        # Define autoencoder model
        autoencoder_outputs = decoder(encoder(encoder_inputs))
        autoencoder = Model(encoder_inputs, autoencoder_outputs, name='autoencoder')
        
        # Compile autoencoder
        autoencoder.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss=self.loss
        )
        
        return autoencoder, encoder, decoder
    
    def _build_lstm_autoencoder(self, n_features: int):
        """
        Build an LSTM autoencoder.
        
        Parameters
        ----------
        n_features : int
            Number of features in the input data
            
        Returns
        -------
        Tuple[Model, Model, Model]
            Tuple of (autoencoder, encoder, decoder) models
        """
        # Define encoder
        encoder_inputs = Input(shape=(self.sequence_length, n_features), name='encoder_input')
        x = encoder_inputs
        
        # Add encoder LSTM layers
        for i, units in enumerate(self.hidden_layers):
            return_sequences = i < len(self.hidden_layers) - 1
            x = LSTM(units, activation=self.activation, return_sequences=return_sequences,
                    name=f'encoder_lstm_{i}')(x)
            if self.dropout_rate > 0:
                x = Dropout(self.dropout_rate, name=f'encoder_dropout_{i}')(x)
        
        # Add bottleneck layer (if needed)
        if self.latent_dim != self.hidden_layers[-1]:
            latent = Dense(self.latent_dim, activation=self.activation, name='bottleneck')(x)
        else:
            latent = x
        
        # Define encoder model
        encoder = Model(encoder_inputs, latent, name='encoder')
        
        # Define decoder
        decoder_inputs = Input(shape=(self.latent_dim,), name='decoder_input')
        x = decoder_inputs
        
        # Repeat the latent vector for sequence generation
        x = RepeatVector(self.sequence_length, name='repeat_vector')(x)
        
        # Add decoder LSTM layers
        for i, units in enumerate(reversed(self.hidden_layers)):
            return_sequences = True  # Always return sequences in decoder
            x = LSTM(units, activation=self.activation, return_sequences=return_sequences,
                    name=f'decoder_lstm_{i}')(x)
            if self.dropout_rate > 0:
                x = Dropout(self.dropout_rate, name=f'decoder_dropout_{i}')(x)
        
        # Add output layer
        decoder_outputs = TimeDistributed(Dense(n_features, activation=self.output_activation),
                                         name='decoder_output')(x)
        
        # Define decoder model
        decoder = Model(decoder_inputs, decoder_outputs, name='decoder')
        
        # Define autoencoder model
        encoded = encoder(encoder_inputs)
        decoded = decoder(encoded)
        autoencoder = Model(encoder_inputs, decoded, name='autoencoder')
        
        # Compile autoencoder
        autoencoder.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss=self.loss
        )
        
        return autoencoder, encoder, decoder
    
    def _build_conv_autoencoder(self, n_features: int):
        """
        Build a convolutional autoencoder.
        
        Parameters
        ----------
        n_features : int
            Number of features in the input data
            
        Returns
        -------
        Tuple[Model, Model, Model]
            Tuple of (autoencoder, encoder, decoder) models
        """
        # Define encoder
        encoder_inputs = Input(shape=(self.sequence_length, n_features), name='encoder_input')
        x = encoder_inputs
        
        # Add encoder convolutional layers
        for i, filters in enumerate(self.hidden_layers):
            x = Conv1D(filters=filters, kernel_size=3, activation=self.activation, padding='same',
                      name=f'encoder_conv_{i}')(x)
            x = MaxPooling1D(pool_size=2, padding='same', name=f'encoder_pool_{i}')(x)
            if self.dropout_rate > 0:
                x = Dropout(self.dropout_rate, name=f'encoder_dropout_{i}')(x)
        
        # Flatten for bottleneck
        x = Flatten(name='flatten')(x)
        
        # Add bottleneck layer
        latent = Dense(self.latent_dim, activation=self.activation, name='bottleneck')(x)
        
        # Define encoder model
        encoder = Model(encoder_inputs, latent, name='encoder')
        
        # Define decoder
        decoder_inputs = Input(shape=(self.latent_dim,), name='decoder_input')
        x = decoder_inputs
        
        # Calculate the shape after flattening
        # This depends on the sequence length and pooling operations
        # For each pooling with pool_size=2, the sequence length is halved
        reduced_length = self.sequence_length
        for _ in range(len(self.hidden_layers)):
            reduced_length = reduced_length // 2
        
        # Dense layer to get back to the right shape for reshaping
        x = Dense(reduced_length * self.hidden_layers[-1], activation=self.activation,
                 name='decoder_dense')(x)
        
        # Reshape to the right shape for Conv1D
        x = Reshape((reduced_length, self.hidden_layers[-1]), name='reshape')(x)
        
        # Add decoder convolutional layers
        for i, filters in enumerate(reversed(self.hidden_layers[:-1])):
            x = Conv1D(filters=filters, kernel_size=3, activation=self.activation, padding='same',
                      name=f'decoder_conv_{i}')(x)
            x = UpSampling1D(size=2, name=f'decoder_upsample_{i}')(x)
            if self.dropout_rate > 0:
                x = Dropout(self.dropout_rate, name=f'decoder_dropout_{i}')(x)
        
        # Final convolutional layer to get back to original number of features
        decoder_outputs = Conv1D(filters=n_features, kernel_size=3, activation=self.output_activation,
                               padding='same', name='decoder_output')(x)
        
        # Define decoder model
        decoder = Model(decoder_inputs, decoder_outputs, name='decoder')
        
        # Define autoencoder model
        encoded = encoder(encoder_inputs)
        decoded = decoder(encoded)
        autoencoder = Model(encoder_inputs, decoded, name='autoencoder')
        
        # Compile autoencoder
        autoencoder.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss=self.loss
        )
        
        return autoencoder, encoder, decoder
    
    def build_model(self, X: Union[pd.DataFrame, np.ndarray]):
        """
        Build the autoencoder model based on the input data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
            
        Returns
        -------
        self : AutoencoderDetector
            The detector with the built model
        """
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Reshape data based on autoencoder type
        if self.autoencoder_type == 'dense':
            # For dense autoencoder, flatten the data if it's multi-dimensional
            if X_data.ndim > 2:
                input_dim = np.prod(X_data.shape[1:])
                X_data = X_data.reshape(X_data.shape[0], input_dim)
            else:
                input_dim = X_data.shape[1]
            
            # Build dense autoencoder
            self.model, self.encoder, self.decoder = self._build_dense_autoencoder(input_dim)
        
        elif self.autoencoder_type == 'lstm':
            # For LSTM autoencoder, ensure data is 3D (samples, sequence_length, features)
            if X_data.ndim == 2:
                # Reshape 2D data to 3D
                if X_data.shape[0] < self.sequence_length:
                    raise ValueError(f"Not enough samples ({X_data.shape[0]}) for sequence_length ({self.sequence_length})")
                
                # Create sequences
                n_samples = X_data.shape[0] - self.sequence_length + 1
                n_features = X_data.shape[1]
                sequences = np.zeros((n_samples, self.sequence_length, n_features))
                
                for i in range(n_samples):
                    sequences[i] = X_data[i:i+self.sequence_length]
                
                X_data = sequences
            
            # Check if data has the right shape
            if X_data.ndim != 3:
                raise ValueError(f"LSTM autoencoder requires 3D data, got {X_data.ndim}D")
            
            n_features = X_data.shape[2]
            
            # Build LSTM autoencoder
            self.model, self.encoder, self.decoder = self._build_lstm_autoencoder(n_features)
        
        elif self.autoencoder_type == 'conv':
            # For Conv autoencoder, ensure data is 3D (samples, sequence_length, features)
            if X_data.ndim == 2:
                # Reshape 2D data to 3D
                if X_data.shape[0] < self.sequence_length:
                    raise ValueError(f"Not enough samples ({X_data.shape[0]}) for sequence_length ({self.sequence_length})")
                
                # Create sequences
                n_samples = X_data.shape[0] - self.sequence_length + 1
                n_features = X_data.shape[1]
                sequences = np.zeros((n_samples, self.sequence_length, n_features))
                
                for i in range(n_samples):
                    sequences[i] = X_data[i:i+self.sequence_length]
                
                X_data = sequences
            
            # Check if data has the right shape
            if X_data.ndim != 3:
                raise ValueError(f"Conv autoencoder requires 3D data, got {X_data.ndim}D")
            
            n_features = X_data.shape[2]
            
            # Build Conv autoencoder
            self.model, self.encoder, self.decoder = self._build_conv_autoencoder(n_features)
        
        logger.info(f"Built {self.autoencoder_type} autoencoder with {self.model.count_params()} parameters")
        
        return self 

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        validation_data: Optional[Union[pd.DataFrame, np.ndarray, Tuple[Union[pd.DataFrame, np.ndarray], Any]]] = None,
        epochs: int = 100,
        batch_size: int = 32,
        callbacks: Optional[List] = None,
        verbose: Optional[int] = None
    ) -> 'AutoencoderDetector':
        """
        Fit the autoencoder model to the data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        validation_data : pd.DataFrame, np.ndarray, or tuple, optional
            Validation data to use during training. If a tuple, should be (X_val, y_val).
        epochs : int, default=100
            Number of epochs to train for.
        batch_size : int, default=32
            Batch size for training.
        callbacks : List, optional
            List of Keras callbacks to use during training.
        verbose : int, optional
            Verbosity level for training. If None, uses self.verbose.
            
        Returns
        -------
        self : AutoencoderDetector
            The fitted detector.
        """
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            # Reshape data for scaler if needed
            original_shape = X_data.shape
            if X_data.ndim > 2:
                X_data_2d = X_data.reshape(X_data.shape[0], -1)
                self.scaler.fit(X_data_2d)
                X_data_2d = self.scaler.transform(X_data_2d)
                X_data = X_data_2d.reshape(original_shape)
            else:
                self.scaler.fit(X_data)
                X_data = self.scaler.transform(X_data)
        
        # Prepare validation data if provided
        if validation_data is not None:
            if isinstance(validation_data, tuple):
                X_val = validation_data[0]
                if isinstance(X_val, pd.DataFrame):
                    X_val = X_val.values
                
                # Normalize validation data if required
                if self.normalize and self.scaler is not None:
                    # Reshape data for scaler if needed
                    original_val_shape = X_val.shape
                    if X_val.ndim > 2:
                        X_val_2d = X_val.reshape(X_val.shape[0], -1)
                        X_val_2d = self.scaler.transform(X_val_2d)
                        X_val = X_val_2d.reshape(original_val_shape)
                    else:
                        X_val = self.scaler.transform(X_val)
                
                validation_data = (X_val, X_val)  # Autoencoder target is the input
            else:
                X_val = validation_data
                if isinstance(X_val, pd.DataFrame):
                    X_val = X_val.values
                
                # Normalize validation data if required
                if self.normalize and self.scaler is not None:
                    # Reshape data for scaler if needed
                    original_val_shape = X_val.shape
                    if X_val.ndim > 2:
                        X_val_2d = X_val.reshape(X_val.shape[0], -1)
                        X_val_2d = self.scaler.transform(X_val_2d)
                        X_val = X_val_2d.reshape(original_val_shape)
                    else:
                        X_val = self.scaler.transform(X_val)
                
                validation_data = (X_val, X_val)  # Autoencoder target is the input
        
        # Build model if not already built
        if self.model is None:
            self.build_model(X_data)
        
        # Set verbosity level
        if verbose is None:
            verbose = self.verbose
        
        # Set up default callbacks if not provided
        if callbacks is None:
            callbacks = []
            
            # Add early stopping
            callbacks.append(EarlyStopping(
                monitor='val_loss' if validation_data is not None else 'loss',
                patience=10,
                restore_best_weights=True
            ))
            
            # Add learning rate reduction
            callbacks.append(ReduceLROnPlateau(
                monitor='val_loss' if validation_data is not None else 'loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6
            ))
        
        # Train model
        history = self.model.fit(
            X_data, X_data,  # Autoencoder target is the input
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=verbose
        )
        
        # Calculate reconstruction error threshold
        self._set_threshold(X_data)
        
        logger.info(f"Trained {self.autoencoder_type} autoencoder for {len(history.epoch)} epochs")
        
        return self
    
    def _set_threshold(self, X: np.ndarray):
        """
        Set the reconstruction error threshold based on the training data.
        
        Parameters
        ----------
        X : np.ndarray
            The training data
        """
        # Get reconstruction errors
        reconstruction_errors = self._get_reconstruction_errors(X)
        
        # Set threshold based on contamination
        threshold_idx = int((1 - self.contamination) * len(reconstruction_errors))
        sorted_errors = np.sort(reconstruction_errors)
        self.threshold = sorted_errors[threshold_idx]
        
        logger.info(f"Set reconstruction error threshold to {self.threshold:.6f}")
    
    def _get_reconstruction_errors(self, X: np.ndarray) -> np.ndarray:
        """
        Calculate reconstruction errors for the data.
        
        Parameters
        ----------
        X : np.ndarray
            The input data
            
        Returns
        -------
        np.ndarray
            Reconstruction errors for each sample
        """
        # Get reconstructions
        X_pred = self.model.predict(X)
        
        # Calculate reconstruction errors
        if X.ndim > 2:
            # For multi-dimensional data, calculate MSE across all dimensions
            reconstruction_errors = np.mean(np.square(X - X_pred), axis=tuple(range(1, X.ndim)))
        else:
            # For 2D data, calculate MSE across features
            reconstruction_errors = np.mean(np.square(X - X_pred), axis=1)
        
        return reconstruction_errors
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Predict if observations are anomalies.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
            
        Returns
        -------
        np.ndarray
            Returns 1 for normal observations and -1 for anomalies.
        """
        # Check if model is fitted
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            # Reshape data for scaler if needed
            original_shape = X_data.shape
            if X_data.ndim > 2:
                X_data_2d = X_data.reshape(X_data.shape[0], -1)
                X_data_2d = self.scaler.transform(X_data_2d)
                X_data = X_data_2d.reshape(original_shape)
            else:
                X_data = self.scaler.transform(X_data)
        
        # Get reconstruction errors
        reconstruction_errors = self._get_reconstruction_errors(X_data)
        
        # Classify as normal or anomaly
        predictions = np.ones(len(reconstruction_errors))
        predictions[reconstruction_errors > self.threshold] = -1
        
        return predictions
    
    def decision_function(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Compute the anomaly score of each sample using the fitted detector.
        
        The anomaly score is the reconstruction error. The higher, the more abnormal.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
            
        Returns
        -------
        np.ndarray
            The anomaly score of each sample. The higher, the more abnormal.
        """
        # Check if model is fitted
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            # Reshape data for scaler if needed
            original_shape = X_data.shape
            if X_data.ndim > 2:
                X_data_2d = X_data.reshape(X_data.shape[0], -1)
                X_data_2d = self.scaler.transform(X_data_2d)
                X_data = X_data_2d.reshape(original_shape)
            else:
                X_data = self.scaler.transform(X_data)
        
        # Get reconstruction errors
        reconstruction_errors = self._get_reconstruction_errors(X_data)
        
        return reconstruction_errors
    
    def detect_anomalies(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        threshold: Optional[float] = None,
        return_scores: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Detect anomalies in the data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        threshold : float, optional
            The threshold for anomaly detection. If None, uses the threshold determined during training.
        return_scores : bool, default=False
            Whether to return anomaly scores along with predictions.
            
        Returns
        -------
        Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]
            Boolean array of anomalies (True for anomalies), or tuple of (anomalies, scores).
        """
        # Get predictions and scores
        if threshold is None:
            predictions = self.predict(X)
        else:
            # Get reconstruction errors
            scores = self.decision_function(X)
            
            # Classify as normal or anomaly using the provided threshold
            predictions = np.ones(len(scores))
            predictions[scores > threshold] = -1
        
        # Convert to boolean array (True for anomalies)
        anomalies = predictions == -1
        
        if return_scores:
            scores = self.decision_function(X)
            return anomalies, scores
        else:
            return anomalies
    
    def plot_anomalies(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
        figsize: Tuple[int, int] = (12, 6),
        title: str = 'Anomaly Detection Results',
        feature_names: Optional[List[str]] = None,
        time_index: Optional[pd.DatetimeIndex] = None,
        save_path: Optional[str] = None
    ):
        """
        Plot the anomalies detected in the data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        y : pd.Series or np.ndarray, optional
            The true anomaly labels, if available.
        figsize : Tuple[int, int], default=(12, 6)
            Figure size.
        title : str, default='Anomaly Detection Results'
            Plot title.
        feature_names : List[str], optional
            Names of the features. If None and X is a DataFrame, uses column names.
        time_index : pd.DatetimeIndex, optional
            Time index for the data. If None and X is a DataFrame, uses the index.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        # Get data
        if isinstance(X, pd.DataFrame):
            data = X.copy()
            if feature_names is None:
                feature_names = data.columns.tolist()
            if time_index is None and isinstance(data.index, pd.DatetimeIndex):
                time_index = data.index
        else:
            data = X.copy()
            if feature_names is None:
                feature_names = [f'Feature {i}' for i in range(data.shape[1])]
        
        # Detect anomalies
        anomalies, scores = self.detect_anomalies(data, return_scores=True)
        
        # Create figure
        fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=True)
        
        # Plot data and anomalies
        x_values = np.arange(len(data)) if time_index is None else time_index
        
        # Plot the first feature or the mean of all features
        if data.shape[1] == 1:
            y_values = data.iloc[:, 0] if isinstance(data, pd.DataFrame) else data[:, 0]
            feature_name = feature_names[0]
        else:
            # Use the mean of all features
            y_values = data.mean(axis=1) if isinstance(data, pd.DataFrame) else data.mean(axis=1)
            feature_name = 'Mean of all features'
        
        # Plot data
        axes[0].plot(x_values, y_values, 'b-', label=feature_name)
        
        # Highlight anomalies
        if np.any(anomalies):
            anomaly_indices = np.where(anomalies)[0]
            axes[0].scatter(
                x_values[anomaly_indices],
                y_values[anomaly_indices],
                color='red',
                marker='o',
                label='Anomalies'
            )
        
        # Plot true anomalies if available
        if y is not None:
            true_anomalies = y == -1 if np.any(y == -1) else y == 1
            if np.any(true_anomalies):
                true_anomaly_indices = np.where(true_anomalies)[0]
                axes[0].scatter(
                    x_values[true_anomaly_indices],
                    y_values[true_anomaly_indices],
                    color='green',
                    marker='x',
                    label='True Anomalies'
                )
        
        axes[0].set_title(title)
        axes[0].set_ylabel(feature_name)
        axes[0].legend()
        axes[0].grid(True)
        
        # Plot reconstruction errors
        axes[1].plot(x_values, scores, 'g-', label='Reconstruction Error')
        
        # Highlight anomalies
        if np.any(anomalies):
            axes[1].scatter(
                x_values[anomaly_indices],
                scores[anomaly_indices],
                color='red',
                marker='o',
                label='Anomalies'
            )
        
        # Add threshold line
        if self.threshold is not None:
            axes[1].axhline(
                y=self.threshold,
                color='r',
                linestyle='--',
                label=f'Threshold: {self.threshold:.3f}'
            )
        
        axes[1].set_xlabel('Time' if time_index is not None else 'Sample')
        axes[1].set_ylabel('Reconstruction Error')
        axes[1].legend()
        axes[1].grid(True)
        
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved anomaly plot to {save_path}")
        
        plt.show()
    
    def plot_reconstruction(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        sample_idx: int = 0,
        n_features: int = None,
        figsize: Tuple[int, int] = (12, 6),
        title: str = 'Reconstruction Example',
        feature_names: Optional[List[str]] = None,
        save_path: Optional[str] = None
    ):
        """
        Plot the original data and its reconstruction for a single sample.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        sample_idx : int, default=0
            Index of the sample to plot.
        n_features : int, optional
            Number of features to plot. If None, plots all features.
        figsize : Tuple[int, int], default=(12, 6)
            Figure size.
        title : str, default='Reconstruction Example'
            Plot title.
        feature_names : List[str], optional
            Names of the features. If None and X is a DataFrame, uses column names.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        # Check if model is fitted
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Get data
        if isinstance(X, pd.DataFrame):
            data = X.values
            if feature_names is None:
                feature_names = X.columns.tolist()
        else:
            data = X
            if feature_names is None:
                feature_names = [f'Feature {i}' for i in range(data.shape[1])]
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            # Reshape data for scaler if needed
            original_shape = data.shape
            if data.ndim > 2:
                data_2d = data.reshape(data.shape[0], -1)
                data_2d = self.scaler.transform(data_2d)
                data = data_2d.reshape(original_shape)
            else:
                data = self.scaler.transform(data)
        
        # Get reconstruction
        reconstruction = self.model.predict(data)
        
        # Get sample
        if sample_idx >= len(data):
            raise ValueError(f"Sample index {sample_idx} out of range for data with {len(data)} samples")
        
        sample = data[sample_idx]
        sample_reconstruction = reconstruction[sample_idx]
        
        # Determine plot type based on data shape
        if self.autoencoder_type == 'dense':
            # For dense autoencoder, plot feature values
            if n_features is None:
                n_features = len(sample)
            else:
                n_features = min(n_features, len(sample))
            
            # Create figure
            plt.figure(figsize=figsize)
            
            # Plot original and reconstruction
            x = np.arange(n_features)
            plt.plot(x, sample[:n_features], 'b-', label='Original')
            plt.plot(x, sample_reconstruction[:n_features], 'r-', label='Reconstruction')
            
            # Add feature names
            plt.xticks(x, feature_names[:n_features], rotation=45)
            
            plt.title(title)
            plt.xlabel('Feature')
            plt.ylabel('Value')
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
        
        elif self.autoencoder_type in ['lstm', 'conv']:
            # For sequence-based autoencoders, plot time series
            if sample.ndim != 2:
                raise ValueError(f"Expected 2D sample for {self.autoencoder_type} autoencoder, got {sample.ndim}D")
            
            sequence_length, n_features_total = sample.shape
            
            if n_features is None:
                n_features = n_features_total
            else:
                n_features = min(n_features, n_features_total)
            
            # Create figure with subplots for each feature
            fig, axes = plt.subplots(n_features, 1, figsize=figsize, sharex=True)
            
            # If only one feature, axes is not a list
            if n_features == 1:
                axes = [axes]
            
            # Plot each feature
            for i in range(n_features):
                axes[i].plot(np.arange(sequence_length), sample[:, i], 'b-', label='Original')
                axes[i].plot(np.arange(sequence_length), sample_reconstruction[:, i], 'r-', label='Reconstruction')
                
                axes[i].set_title(f'Feature: {feature_names[i]}')
                axes[i].set_ylabel('Value')
                axes[i].legend()
                axes[i].grid(True)
            
            # Set common x-axis label
            axes[-1].set_xlabel('Time Step')
            
            plt.suptitle(title)
            plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved reconstruction plot to {save_path}")
        
        plt.show()
    
    def plot_latent_space(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
        figsize: Tuple[int, int] = (10, 8),
        title: str = 'Latent Space Visualization',
        save_path: Optional[str] = None
    ):
        """
        Plot the latent space representation of the data.
        
        This method only works if the latent dimension is 2 or 3.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        y : pd.Series or np.ndarray, optional
            Labels for coloring the points. If None, uses anomaly detection results.
        figsize : Tuple[int, int], default=(10, 8)
            Figure size.
        title : str, default='Latent Space Visualization'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        # Check if model is fitted
        if self.model is None or self.encoder is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Check if latent dimension is 2 or 3
        if self.latent_dim not in [2, 3]:
            raise ValueError(f"Latent space visualization only works for latent_dim=2 or latent_dim=3, got latent_dim={self.latent_dim}")
        
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            # Reshape data for scaler if needed
            original_shape = X_data.shape
            if X_data.ndim > 2:
                X_data_2d = X_data.reshape(X_data.shape[0], -1)
                X_data_2d = self.scaler.transform(X_data_2d)
                X_data = X_data_2d.reshape(original_shape)
            else:
                X_data = self.scaler.transform(X_data)
        
        # Get latent space representation
        latent_representation = self.encoder.predict(X_data)
        
        # Get labels for coloring
        if y is None:
            # Use anomaly detection results
            anomalies = self.detect_anomalies(X)
            labels = np.where(anomalies, 'Anomaly', 'Normal')
            colors = np.where(anomalies, 'red', 'blue')
        else:
            # Use provided labels
            if isinstance(y, pd.Series):
                y = y.values
            
            # Convert to string labels
            labels = y.astype(str)
            
            # Generate colors
            unique_labels = np.unique(labels)
            color_map = plt.cm.get_cmap('tab10', len(unique_labels))
            colors = [color_map(i) for i in range(len(unique_labels))]
            
            # Map labels to colors
            label_to_color = {label: colors[i] for i, label in enumerate(unique_labels)}
            colors = [label_to_color[label] for label in labels]
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Plot latent space
        if self.latent_dim == 2:
            # 2D scatter plot
            scatter = plt.scatter(
                latent_representation[:, 0],
                latent_representation[:, 1],
                c=colors,
                alpha=0.7
            )
            
            plt.xlabel('Latent Dimension 1')
            plt.ylabel('Latent Dimension 2')
        else:  # latent_dim == 3
            # 3D scatter plot
            ax = plt.axes(projection='3d')
            scatter = ax.scatter(
                latent_representation[:, 0],
                latent_representation[:, 1],
                latent_representation[:, 2],
                c=colors,
                alpha=0.7
            )
            
            ax.set_xlabel('Latent Dimension 1')
            ax.set_ylabel('Latent Dimension 2')
            ax.set_zlabel('Latent Dimension 3')
        
        # Add legend
        if y is None:
            # Simple legend for anomaly detection
            plt.legend(['Normal', 'Anomaly'])
        else:
            # Legend for provided labels
            handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=label_to_color[label], markersize=10)
                      for label in unique_labels]
            plt.legend(handles, unique_labels)
        
        plt.title(title)
        plt.grid(True)
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved latent space plot to {save_path}")
        
        plt.show()
    
    def save(self, filepath: str):
        """
        Save the detector to a file.
        
        Parameters
        ----------
        filepath : str
            Path to save the detector.
        """
        # Check if model is fitted
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save model
        model_path = filepath
        self.model.save(model_path)
        
        # Save encoder and decoder
        encoder_path = os.path.splitext(filepath)[0] + '_encoder' + os.path.splitext(filepath)[1]
        decoder_path = os.path.splitext(filepath)[0] + '_decoder' + os.path.splitext(filepath)[1]
        self.encoder.save(encoder_path)
        self.decoder.save(decoder_path)
        
        # Save parameters and threshold
        params_path = os.path.splitext(filepath)[0] + '_params.json'
        params = {
            'autoencoder_type': self.autoencoder_type,
            'sequence_length': self.sequence_length,
            'hidden_layers': self.hidden_layers,
            'latent_dim': self.latent_dim,
            'dropout_rate': self.dropout_rate,
            'activation': self.activation,
            'output_activation': self.output_activation,
            'learning_rate': self.learning_rate,
            'loss': self.loss,
            'contamination': self.contamination,
            'normalize': self.normalize,
            'normalization_method': self.normalization_method,
            'threshold': self.threshold,
            'random_state': self.random_state,
            'verbose': self.verbose
        }
        
        with open(params_path, 'w') as f:
            json.dump(params, f, indent=4)
        
        # Save scaler if available
        if self.scaler is not None:
            import joblib
            scaler_path = os.path.splitext(filepath)[0] + '_scaler.pkl'
            joblib.dump(self.scaler, scaler_path)
        
        logger.info(f"Saved AutoencoderDetector to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'AutoencoderDetector':
        """
        Load a detector from a file.
        
        Parameters
        ----------
        filepath : str
            Path to the saved detector.
            
        Returns
        -------
        AutoencoderDetector
            The loaded detector.
        """
        # Load parameters
        params_path = os.path.splitext(filepath)[0] + '_params.json'
        with open(params_path, 'r') as f:
            params = json.load(f)
        
        # Extract threshold
        threshold = params.pop('threshold', None)
        
        # Create detector instance
        detector = cls(**params)
        detector.threshold = threshold
        
        # Load model
        detector.model = load_model(filepath)
        
        # Load encoder and decoder
        encoder_path = os.path.splitext(filepath)[0] + '_encoder' + os.path.splitext(filepath)[1]
        decoder_path = os.path.splitext(filepath)[0] + '_decoder' + os.path.splitext(filepath)[1]
        detector.encoder = load_model(encoder_path)
        detector.decoder = load_model(decoder_path)
        
        # Load scaler if available
        scaler_path = os.path.splitext(filepath)[0] + '_scaler.pkl'
        if os.path.exists(scaler_path):
            import joblib
            detector.scaler = joblib.load(scaler_path)
        
        logger.info(f"Loaded AutoencoderDetector from {filepath}")
        return detector 