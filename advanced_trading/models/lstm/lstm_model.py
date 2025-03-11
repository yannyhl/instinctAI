"""
LSTM Model Module
---------------
This module provides a flexible LSTM model implementation for financial time series prediction.
It includes:

1. Various LSTM architectures (vanilla, stacked, bidirectional)
2. Support for regression and classification tasks
3. Customizable hyperparameters
4. Training and prediction methods
5. Model evaluation and visualization
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Union, Optional, Callable, Any
import logging
import os
import json
import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Check if TensorFlow is available, otherwise use Keras
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, Model, load_model
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, BatchNormalization, 
        Input, Bidirectional, TimeDistributed
    )
    from tensorflow.keras.callbacks import (
        EarlyStopping, ModelCheckpoint, ReduceLROnPlateau,
        TensorBoard, History
    )
    from tensorflow.keras.optimizers import Adam, RMSprop
    KERAS_BACKEND = 'tensorflow'
    logger.info("Using TensorFlow backend for Keras")
except ImportError:
    try:
        from keras.models import Sequential, Model, load_model
        from keras.layers import (
            LSTM, Dense, Dropout, BatchNormalization, 
            Input, Bidirectional, TimeDistributed
        )
        from keras.callbacks import (
            EarlyStopping, ModelCheckpoint, ReduceLROnPlateau,
            TensorBoard, History
        )
        from keras.optimizers import Adam, RMSprop
        KERAS_BACKEND = 'keras'
        logger.info("Using standalone Keras")
    except ImportError:
        logger.error("Neither TensorFlow nor Keras is available. Please install one of them.")
        raise ImportError("Neither TensorFlow nor Keras is available. Please install one of them.")

class LSTMModel:
    """
    A flexible LSTM model for financial time series prediction.
    
    This class provides methods for:
    - Building various LSTM architectures
    - Training the model
    - Making predictions
    - Evaluating model performance
    - Saving and loading models
    """
    
    def __init__(
        self,
        sequence_length: int = 20,
        n_features: int = 1,
        n_outputs: int = 1,
        lstm_units: Union[int, List[int]] = 50,
        dropout_rate: float = 0.2,
        recurrent_dropout: float = 0.0,
        dense_units: Optional[List[int]] = None,
        activation: str = 'relu',
        output_activation: Optional[str] = None,
        bidirectional: bool = False,
        stateful: bool = False,
        batch_size: Optional[int] = None,
        optimizer: str = 'adam',
        learning_rate: float = 0.001,
        loss: str = 'mse',
        metrics: Optional[List[str]] = None,
        model_type: str = 'regression',
        return_sequences: bool = False,
        name: Optional[str] = None,
        random_state: Optional[int] = None
    ):
        """
        Initialize the LSTM model.
        
        Parameters
        ----------
        sequence_length : int, default=20
            Length of input sequences
        n_features : int, default=1
            Number of features in the input data
        n_outputs : int, default=1
            Number of output units (1 for regression, >1 for classification)
        lstm_units : Union[int, List[int]], default=50
            Number of LSTM units. If a list, creates a stacked LSTM
        dropout_rate : float, default=0.2
            Dropout rate after LSTM layers
        recurrent_dropout : float, default=0.0
            Dropout rate for recurrent connections
        dense_units : List[int], optional
            Number of units in dense layers after LSTM
        activation : str, default='relu'
            Activation function for dense layers
        output_activation : str, optional
            Activation function for output layer (None for regression, 'softmax' for classification)
        bidirectional : bool, default=False
            Whether to use bidirectional LSTM
        stateful : bool, default=False
            Whether the LSTM should be stateful
        batch_size : int, optional
            Batch size for stateful LSTM. Required if stateful=True
        optimizer : str, default='adam'
            Optimizer to use for training
        learning_rate : float, default=0.001
            Learning rate for the optimizer
        loss : str, default='mse'
            Loss function to use for training
        metrics : List[str], optional
            Metrics to track during training
        model_type : str, default='regression'
            Type of model: 'regression' or 'classification'
        return_sequences : bool, default=False
            Whether to return sequences from the LSTM
        name : str, optional
            Name of the model
        random_state : int, optional
            Random state for reproducibility
        """
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.n_outputs = n_outputs
        self.lstm_units = lstm_units if isinstance(lstm_units, list) else [lstm_units]
        self.dropout_rate = dropout_rate
        self.recurrent_dropout = recurrent_dropout
        self.dense_units = dense_units or []
        self.activation = activation
        self.output_activation = output_activation
        self.bidirectional = bidirectional
        self.stateful = stateful
        self.batch_size = batch_size
        self.optimizer = optimizer
        self.learning_rate = learning_rate
        self.loss = loss
        self.metrics = metrics or ['mae'] if model_type == 'regression' else ['accuracy']
        self.model_type = model_type
        self.return_sequences = return_sequences
        self.name = name or f"lstm_model_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.random_state = random_state
        
        # Set random seed if provided
        if random_state is not None:
            if KERAS_BACKEND == 'tensorflow':
                tf.random.set_seed(random_state)
            else:
                np.random.seed(random_state)
        
        # Validate parameters
        self._validate_parameters()
        
        # Initialize model
        self.model = None
        self.history = None
        
        logger.info(f"Initialized LSTMModel with {len(self.lstm_units)} LSTM layers, "
                   f"bidirectional={bidirectional}, model_type={model_type}")
    
    def _validate_parameters(self):
        """Validate model parameters."""
        if self.model_type not in ['regression', 'classification']:
            raise ValueError(f"model_type must be 'regression' or 'classification', got {self.model_type}")
        
        if self.stateful and self.batch_size is None:
            raise ValueError("batch_size must be specified for stateful LSTM")
        
        if self.model_type == 'classification' and self.output_activation is None:
            self.output_activation = 'softmax'
            logger.info("Setting output_activation to 'softmax' for classification model")
        
        if self.model_type == 'regression' and self.loss == 'categorical_crossentropy':
            logger.warning("Using categorical_crossentropy loss for regression model")
        
        if self.model_type == 'classification' and self.loss == 'mse':
            logger.warning("Using MSE loss for classification model")
    
    def build_model(self):
        """
        Build the LSTM model architecture.
        
        Returns
        -------
        self : LSTMModel
            The model instance
        """
        # Define input shape
        if self.stateful:
            input_shape = (self.sequence_length, self.n_features)
            batch_input_shape = (self.batch_size, self.sequence_length, self.n_features)
        else:
            input_shape = (self.sequence_length, self.n_features)
            batch_input_shape = None
        
        # Create model
        model = Sequential(name=self.name)
        
        # Add LSTM layers
        for i, units in enumerate(self.lstm_units):
            return_sequences = self.return_sequences or i < len(self.lstm_units) - 1
            
            # First layer
            if i == 0:
                if self.bidirectional:
                    if batch_input_shape:
                        model.add(Bidirectional(
                            LSTM(units, 
                                 return_sequences=return_sequences,
                                 stateful=self.stateful,
                                 recurrent_dropout=self.recurrent_dropout),
                            batch_input_shape=batch_input_shape
                        ))
                    else:
                        model.add(Bidirectional(
                            LSTM(units, 
                                 return_sequences=return_sequences,
                                 stateful=self.stateful,
                                 recurrent_dropout=self.recurrent_dropout),
                            input_shape=input_shape
                        ))
                else:
                    if batch_input_shape:
                        model.add(LSTM(units, 
                                      return_sequences=return_sequences,
                                      stateful=self.stateful,
                                      recurrent_dropout=self.recurrent_dropout,
                                      batch_input_shape=batch_input_shape))
                    else:
                        model.add(LSTM(units, 
                                      return_sequences=return_sequences,
                                      stateful=self.stateful,
                                      recurrent_dropout=self.recurrent_dropout,
                                      input_shape=input_shape))
            # Subsequent layers
            else:
                if self.bidirectional:
                    model.add(Bidirectional(LSTM(units, 
                                               return_sequences=return_sequences,
                                               stateful=self.stateful,
                                               recurrent_dropout=self.recurrent_dropout)))
                else:
                    model.add(LSTM(units, 
                                  return_sequences=return_sequences,
                                  stateful=self.stateful,
                                  recurrent_dropout=self.recurrent_dropout))
            
            # Add dropout after each LSTM layer
            if self.dropout_rate > 0:
                model.add(Dropout(self.dropout_rate))
        
        # Add dense layers
        for units in self.dense_units:
            model.add(Dense(units, activation=self.activation))
            if self.dropout_rate > 0:
                model.add(Dropout(self.dropout_rate))
        
        # Add output layer
        if self.return_sequences:
            model.add(TimeDistributed(Dense(self.n_outputs, activation=self.output_activation)))
        else:
            model.add(Dense(self.n_outputs, activation=self.output_activation))
        
        # Configure optimizer
        if self.optimizer.lower() == 'adam':
            optimizer = Adam(learning_rate=self.learning_rate)
        elif self.optimizer.lower() == 'rmsprop':
            optimizer = RMSprop(learning_rate=self.learning_rate)
        else:
            optimizer = self.optimizer
        
        # Compile model
        model.compile(optimizer=optimizer, loss=self.loss, metrics=self.metrics)
        
        self.model = model
        logger.info(f"Built LSTM model with {model.count_params()} parameters")
        
        return self
    
    def summary(self):
        """
        Print a summary of the model architecture.
        
        Returns
        -------
        None
        """
        if self.model is None:
            self.build_model()
        
        self.model.summary()
    
    def get_callbacks(
        self,
        early_stopping: bool = True,
        patience: int = 10,
        checkpoint: bool = True,
        checkpoint_path: Optional[str] = None,
        reduce_lr: bool = True,
        lr_patience: int = 5,
        tensorboard: bool = False,
        log_dir: Optional[str] = None
    ) -> List:
        """
        Get callbacks for model training.
        
        Parameters
        ----------
        early_stopping : bool, default=True
            Whether to use early stopping
        patience : int, default=10
            Patience for early stopping
        checkpoint : bool, default=True
            Whether to save model checkpoints
        checkpoint_path : str, optional
            Path to save model checkpoints
        reduce_lr : bool, default=True
            Whether to reduce learning rate on plateau
        lr_patience : int, default=5
            Patience for learning rate reduction
        tensorboard : bool, default=False
            Whether to use TensorBoard
        log_dir : str, optional
            Directory for TensorBoard logs
            
        Returns
        -------
        List
            List of callbacks
        """
        callbacks = []
        
        if early_stopping:
            callbacks.append(EarlyStopping(
                monitor='val_loss',
                patience=patience,
                restore_best_weights=True,
                verbose=1
            ))
        
        if checkpoint:
            if checkpoint_path is None:
                checkpoint_path = f"./models/{self.name}_best.h5"
            os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
            callbacks.append(ModelCheckpoint(
                filepath=checkpoint_path,
                monitor='val_loss',
                save_best_only=True,
                verbose=1
            ))
        
        if reduce_lr:
            callbacks.append(ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=lr_patience,
                min_lr=1e-6,
                verbose=1
            ))
        
        if tensorboard:
            if log_dir is None:
                log_dir = f"./logs/{self.name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(log_dir, exist_ok=True)
            callbacks.append(TensorBoard(
                log_dir=log_dir,
                histogram_freq=1
            ))
        
        return callbacks 

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        validation_data: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        epochs: int = 100,
        batch_size: Optional[int] = None,
        shuffle: bool = True,
        callbacks: Optional[List] = None,
        verbose: int = 1,
        class_weight: Optional[Dict] = None
    ) -> History:
        """
        Train the LSTM model.
        
        Parameters
        ----------
        X_train : np.ndarray
            Training input sequences with shape (n_samples, sequence_length, n_features)
        y_train : np.ndarray
            Training target values
        validation_data : Tuple[np.ndarray, np.ndarray], optional
            Validation data as (X_val, y_val)
        epochs : int, default=100
            Number of training epochs
        batch_size : int, optional
            Batch size for training. If None, uses self.batch_size for stateful models or 32 otherwise
        shuffle : bool, default=True
            Whether to shuffle the training data
        callbacks : List, optional
            List of callbacks for training
        verbose : int, default=1
            Verbosity mode (0, 1, or 2)
        class_weight : Dict, optional
            Class weights for imbalanced classification
            
        Returns
        -------
        History
            Training history
        """
        # Build model if not already built
        if self.model is None:
            self.build_model()
        
        # Set batch size
        if batch_size is None:
            if self.stateful and self.batch_size is not None:
                batch_size = self.batch_size
            else:
                batch_size = 32
        
        # Get default callbacks if not provided
        if callbacks is None:
            callbacks = self.get_callbacks()
        
        # Train model
        history = self.model.fit(
            X_train, y_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            shuffle=shuffle and not self.stateful,  # Don't shuffle if stateful
            callbacks=callbacks,
            verbose=verbose,
            class_weight=class_weight
        )
        
        self.history = history
        logger.info(f"Trained model for {len(history.epoch)} epochs")
        
        return history
    
    def predict(
        self,
        X: np.ndarray,
        batch_size: Optional[int] = None,
        verbose: int = 0
    ) -> np.ndarray:
        """
        Make predictions with the LSTM model.
        
        Parameters
        ----------
        X : np.ndarray
            Input sequences with shape (n_samples, sequence_length, n_features)
        batch_size : int, optional
            Batch size for prediction
        verbose : int, default=0
            Verbosity mode
            
        Returns
        -------
        np.ndarray
            Predicted values
        """
        if self.model is None:
            raise ValueError("Model has not been built yet. Call build_model() first.")
        
        # Set batch size for stateful models
        if batch_size is None and self.stateful and self.batch_size is not None:
            batch_size = self.batch_size
        
        return self.model.predict(X, batch_size=batch_size, verbose=verbose)
    
    def predict_proba(
        self,
        X: np.ndarray,
        batch_size: Optional[int] = None,
        verbose: int = 0
    ) -> np.ndarray:
        """
        Predict class probabilities for classification models.
        
        Parameters
        ----------
        X : np.ndarray
            Input sequences with shape (n_samples, sequence_length, n_features)
        batch_size : int, optional
            Batch size for prediction
        verbose : int, default=0
            Verbosity mode
            
        Returns
        -------
        np.ndarray
            Predicted probabilities
        """
        if self.model_type != 'classification':
            raise ValueError("predict_proba is only available for classification models")
        
        return self.predict(X, batch_size=batch_size, verbose=verbose)
    
    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        batch_size: Optional[int] = None,
        verbose: int = 1
    ) -> Union[float, List[float]]:
        """
        Evaluate the model on test data.
        
        Parameters
        ----------
        X : np.ndarray
            Input sequences with shape (n_samples, sequence_length, n_features)
        y : np.ndarray
            Target values
        batch_size : int, optional
            Batch size for evaluation
        verbose : int, default=1
            Verbosity mode
            
        Returns
        -------
        Union[float, List[float]]
            Loss value or list of [loss, ...metrics] values
        """
        if self.model is None:
            raise ValueError("Model has not been built yet. Call build_model() first.")
        
        # Set batch size for stateful models
        if batch_size is None and self.stateful and self.batch_size is not None:
            batch_size = self.batch_size
        
        return self.model.evaluate(X, y, batch_size=batch_size, verbose=verbose)
    
    def reset_states(self):
        """
        Reset the states of a stateful LSTM model.
        
        Returns
        -------
        None
        """
        if self.model is not None and self.stateful:
            self.model.reset_states()
            logger.info("Reset states of stateful LSTM model")
    
    def save(self, filepath: str, save_format: str = 'h5'):
        """
        Save the model to a file.
        
        Parameters
        ----------
        filepath : str
            Path to save the model
        save_format : str, default='h5'
            Format to save the model ('h5' or 'tf')
            
        Returns
        -------
        None
        """
        if self.model is None:
            raise ValueError("Model has not been built yet. Call build_model() first.")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save model
        self.model.save(filepath, save_format=save_format)
        logger.info(f"Saved model to {filepath}")
        
        # Save model configuration
        config_path = os.path.splitext(filepath)[0] + '_config.json'
        self.save_config(config_path)
    
    def save_config(self, filepath: str):
        """
        Save the model configuration to a JSON file.
        
        Parameters
        ----------
        filepath : str
            Path to save the configuration
            
        Returns
        -------
        None
        """
        config = {
            'sequence_length': self.sequence_length,
            'n_features': self.n_features,
            'n_outputs': self.n_outputs,
            'lstm_units': self.lstm_units,
            'dropout_rate': self.dropout_rate,
            'recurrent_dropout': self.recurrent_dropout,
            'dense_units': self.dense_units,
            'activation': self.activation,
            'output_activation': self.output_activation,
            'bidirectional': self.bidirectional,
            'stateful': self.stateful,
            'batch_size': self.batch_size,
            'optimizer': self.optimizer,
            'learning_rate': self.learning_rate,
            'loss': self.loss,
            'metrics': self.metrics,
            'model_type': self.model_type,
            'return_sequences': self.return_sequences,
            'name': self.name,
            'random_state': self.random_state
        }
        
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=4)
        
        logger.info(f"Saved model configuration to {filepath}")
    
    @classmethod
    def load(cls, filepath: str, custom_objects: Optional[Dict] = None) -> 'LSTMModel':
        """
        Load a model from a file.
        
        Parameters
        ----------
        filepath : str
            Path to the saved model
        custom_objects : Dict, optional
            Dictionary mapping names to custom classes or functions
            
        Returns
        -------
        LSTMModel
            Loaded model
        """
        # Load model configuration
        config_path = os.path.splitext(filepath)[0] + '_config.json'
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Create model instance with loaded configuration
            model_instance = cls(**config)
        else:
            logger.warning(f"Configuration file {config_path} not found. Creating default model instance.")
            model_instance = cls()
        
        # Load Keras model
        model_instance.model = load_model(filepath, custom_objects=custom_objects)
        logger.info(f"Loaded model from {filepath}")
        
        return model_instance
    
    def plot_history(self, figsize: Tuple[int, int] = (12, 8), save_path: Optional[str] = None):
        """
        Plot the training history.
        
        Parameters
        ----------
        figsize : Tuple[int, int], default=(12, 8)
            Figure size
        save_path : str, optional
            Path to save the plot
            
        Returns
        -------
        None
        """
        if self.history is None:
            raise ValueError("Model has not been trained yet. Call fit() first.")
        
        history = self.history.history
        
        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # Plot loss
        axes[0].plot(history['loss'], label='Training Loss')
        if 'val_loss' in history:
            axes[0].plot(history['val_loss'], label='Validation Loss')
        axes[0].set_title('Loss')
        axes[0].set_xlabel('Epoch')
        axes[0].set_ylabel('Loss')
        axes[0].legend()
        axes[0].grid(True)
        
        # Plot metrics
        for metric in self.metrics:
            if metric in history:
                axes[1].plot(history[metric], label=f'Training {metric}')
                if f'val_{metric}' in history:
                    axes[1].plot(history[f'val_{metric}'], label=f'Validation {metric}')
        axes[1].set_title('Metrics')
        axes[1].set_xlabel('Epoch')
        axes[1].set_ylabel('Value')
        axes[1].legend()
        axes[1].grid(True)
        
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved history plot to {save_path}")
        
        plt.show()
    
    def plot_predictions(
        self,
        X: np.ndarray,
        y_true: np.ndarray,
        scaler=None,
        figsize: Tuple[int, int] = (12, 6),
        save_path: Optional[str] = None,
        n_samples: Optional[int] = None
    ):
        """
        Plot model predictions against true values.
        
        Parameters
        ----------
        X : np.ndarray
            Input sequences
        y_true : np.ndarray
            True target values
        scaler : object, optional
            Scaler used to transform the target values
        figsize : Tuple[int, int], default=(12, 6)
            Figure size
        save_path : str, optional
            Path to save the plot
        n_samples : int, optional
            Number of samples to plot. If None, plots all samples
            
        Returns
        -------
        None
        """
        # Make predictions
        y_pred = self.predict(X)
        
        # Inverse transform if scaler is provided
        if scaler is not None:
            if y_true.ndim == 1:
                y_true_inv = scaler.inverse_transform(y_true.reshape(-1, 1)).flatten()
            else:
                y_true_inv = scaler.inverse_transform(y_true)
            
            if y_pred.ndim == 1:
                y_pred_inv = scaler.inverse_transform(y_pred.reshape(-1, 1)).flatten()
            else:
                y_pred_inv = scaler.inverse_transform(y_pred)
        else:
            y_true_inv = y_true
            y_pred_inv = y_pred
        
        # Limit number of samples if specified
        if n_samples is not None:
            y_true_inv = y_true_inv[:n_samples]
            y_pred_inv = y_pred_inv[:n_samples]
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Plot true values and predictions
        plt.plot(y_true_inv, label='True')
        plt.plot(y_pred_inv, label='Predicted')
        
        plt.title('Model Predictions vs True Values')
        plt.xlabel('Sample')
        plt.ylabel('Value')
        plt.legend()
        plt.grid(True)
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved predictions plot to {save_path}")
        
        plt.show() 