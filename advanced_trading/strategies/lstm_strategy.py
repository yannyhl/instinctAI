"""
LSTM Strategy Module
-------------------
Implements a trading strategy based on LSTM (Long Short-Term Memory) neural networks
for time series forecasting and trading signal generation.
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional
from pathlib import Path
import joblib
import json
import matplotlib.pyplot as plt
from datetime import datetime

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
import sys
sys.path.append(str(script_dir))

import config
from models.lstm_model import LSTMModel
from models.volume_profile import VolumeProfile
from utils.indicators import add_technical_indicators

# Set up logging
logger = logging.getLogger(__name__)

class LSTMStrategy:
    """
    LSTM-based trading strategy that uses deep learning to predict price movements
    and generate trading signals.
    
    Features:
    - Price prediction using LSTM neural networks
    - Integration with volume profile analysis
    - Configurable prediction thresholds and signal generation
    - Model training, evaluation, and persistence
    """
    
    def __init__(self, 
                symbol: str,
                config_params: Dict = None,
                sequence_length: int = 60,
                prediction_horizon: int = 5,
                threshold_pct: float = 1.0,
                use_volume_profile: bool = True):
        """
        Initialize the LSTM strategy.
        
        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            config_params: Configuration parameters for the LSTM model
            sequence_length: Number of past time steps to use as input
            prediction_horizon: Number of future time steps to predict
            threshold_pct: Percentage threshold for signal generation
            use_volume_profile: Whether to incorporate volume profile analysis
        """
        self.symbol = symbol
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.threshold_pct = threshold_pct
        self.use_volume_profile = use_volume_profile
        
        # Clean symbol for filenames
        self.clean_symbol = symbol.replace('/', '_')
        
        # Initialize models
        self.lstm_model = LSTMModel(
            config=config_params,
            sequence_length=sequence_length,
            prediction_horizon=prediction_horizon
        )
        
        if use_volume_profile:
            self.volume_profile = VolumeProfile(
                num_bins=50,
                high_vol_percentile=80,
                value_area_percentage=70
            )
        else:
            self.volume_profile = None
        
        # Strategy state
        self.is_trained = False
        self.last_signal = 0
        self.last_prediction = None
        self.last_confidence = 0.0
        
        logger.info(f"Initialized LSTM strategy for {symbol} with sequence length {sequence_length}")
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data for the LSTM model by adding technical indicators.
        
        Args:
            data: Raw OHLCV data
            
        Returns:
            Processed DataFrame with technical indicators
        """
        # Verify data contains required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in data.columns:
                logger.error(f"Required column '{col}' not found in data")
                return pd.DataFrame()  # Return empty dataframe instead of None
        
        # Add technical indicators
        processed_data = add_technical_indicators(data.copy())
        
        # For LSTM, we need at least sequence_length points of data
        if len(processed_data) < self.sequence_length:
            logger.warning(f"Not enough data for LSTM. Have {len(processed_data)} points, need {self.sequence_length}.")
            return pd.DataFrame()  # Return empty dataframe instead of None
        
        # Drop NaN values
        processed_data.dropna(inplace=True)
        
        logger.info(f"Prepared data with {len(processed_data)} rows and {len(processed_data.columns)} features")
        return processed_data
    
    def train(self, data: pd.DataFrame, validation_split: float = 0.2) -> Dict:
        """
        Train the LSTM model on historical data.
        
        Args:
            data: OHLCV data with technical indicators
            validation_split: Portion of data to use for validation
            
        Returns:
            Training metrics
        """
        # Prepare data if needed
        if len(data.columns) <= 5:  # Only OHLCV columns
            data = self.prepare_data(data)
        
        if len(data) < self.sequence_length + self.prediction_horizon:
            logger.error(f"Not enough data to train model. Need at least {self.sequence_length + self.prediction_horizon} points.")
            return None
        
        # Train LSTM model
        logger.info(f"Training LSTM model for {self.symbol} on {len(data)} data points")
        history = self.lstm_model.train(data, validation_split=validation_split)
        
        # Analyze volume profile if enabled
        if self.use_volume_profile:
            self.volume_profile.analyze(data)
        
        self.is_trained = True
        
        # Return training metrics
        metrics = {
            'loss': history['loss'][-1] if history else None,
            'val_loss': history['val_loss'][-1] if history else None,
            'mae': history['mae'][-1] if history else None,
            'val_mae': history['val_mae'][-1] if history else None
        }
        
        logger.info(f"LSTM model training completed with validation loss: {metrics['val_loss']:.4f}")
        return metrics
    
    def predict(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate price prediction using the trained LSTM model.
        
        Args:
            data: Recent OHLCV data with technical indicators
            
        Returns:
            Tuple of (predicted_price, confidence)
        """
        if not self.is_trained:
            logger.error("Model not trained. Call train() first.")
            return None, 0.0
        
        # Prepare data if needed
        processed_data = data
        if len(data.columns) <= 5:  # Only OHLCV columns
            processed_data = self.prepare_data(data)
        
        if processed_data.empty or len(processed_data) < self.sequence_length:
            logger.error(f"Not enough data for prediction. Need at least {self.sequence_length} points.")
            return None, 0.0
        
        # Make prediction
        prediction = self.lstm_model.predict(processed_data)
        
        if prediction is None or len(prediction) == 0:
            logger.error("Failed to generate prediction")
            return None, 0.0
        
        # Extract predicted price (first value if multi-step)
        predicted_price = prediction[0][0]
        
        # Calculate confidence based on model history
        # Simple approach: use inverse of validation loss as confidence
        if self.lstm_model.history is not None:
            val_loss = self.lstm_model.history.history['val_loss'][-1]
            confidence = 1.0 / (1.0 + val_loss)  # Normalize to 0-1 range
        else:
            confidence = 0.5  # Default confidence
        
        self.last_prediction = predicted_price
        self.last_confidence = confidence
        
        logger.info(f"Generated prediction for {self.symbol}: {predicted_price:.2f} with confidence {confidence:.2f}")
        return predicted_price, confidence
    
    def generate_signal(self, data: pd.DataFrame) -> float:
        """
        Generate trading signal based on LSTM prediction and volume profile.
        
        Args:
            data: Recent OHLCV data
            
        Returns:
            Signal value: 1.0 (buy), -1.0 (sell), or 0.0 (hold)
        """
        if not self.is_trained:
            logger.warning("Model not trained yet. No signal generated.")
            return 0.0
            
        # Get current price
        if data.empty:
            logger.warning("Empty data provided to generate_signal")
            return self.last_signal
            
        # Ensure we have enough data
        if len(data) < self.sequence_length:
            logger.warning(f"Not enough data for prediction. Need at least {self.sequence_length} points.")
            return 0.0
            
        # Process data
        processed_data = data
        if len(data.columns) <= 5:  # Only OHLCV columns
            # Try to process the data
            processed_data = self.prepare_data(data)
            if processed_data.empty:
                logger.warning("Failed to process data for signal generation")
                return self.last_signal
                
        current_price = data['close'].iloc[-1]
        
        # Generate prediction
        predicted_price, confidence = self.predict(processed_data)
        
        if predicted_price is None:
            logger.warning("No prediction available, maintaining previous signal")
            return self.last_signal
        
        # Calculate predicted return
        predicted_return_pct = 100 * (predicted_price - current_price) / current_price
        
        # Initialize signal
        signal = 0.0
        
        # Generate signal based on prediction threshold
        if predicted_return_pct > self.threshold_pct:
            signal = 1.0  # Buy signal
        elif predicted_return_pct < -self.threshold_pct:
            signal = -1.0  # Sell signal
        
        # Incorporate volume profile if enabled
        if self.use_volume_profile and self.volume_profile.bins is not None:
            # Update volume profile
            self.volume_profile.analyze(data)
            
            # Check if price is at key level
            level_info = self.volume_profile.is_price_at_key_level(current_price)
            
            # Adjust signal based on volume profile
            if level_info:
                # Strengthen signal if at support/resistance
                if signal > 0 and level_info['at_high_volume_node']:
                    signal = 1.0  # Strong buy at support
                elif signal < 0 and level_info['at_high_volume_node']:
                    signal = -1.0  # Strong sell at resistance
                
                # Reduce signal if in value area (mean reversion)
                if level_info['in_value_area'] and not level_info['at_value_area_edge']:
                    signal *= 0.5  # Reduce signal strength
        
        # Apply confidence weighting
        signal *= confidence
        
        # Discretize final signal
        if signal > 0.5:
            final_signal = 1.0
        elif signal < -0.5:
            final_signal = -1.0
        else:
            final_signal = 0.0
        
        self.last_signal = final_signal
        
        logger.info(f"Generated signal for {self.symbol}: {final_signal} (predicted return: {predicted_return_pct:.2f}%)")
        return final_signal
    
    def save(self, base_path: str = None) -> str:
        """
        Save the strategy models and configuration.
        
        Args:
            base_path: Base directory to save models
            
        Returns:
            Path where models were saved
        """
        if not self.is_trained:
            logger.error("Model not trained. Call train() first.")
            return None
        
        # Use default path if not provided
        if base_path is None:
            base_path = os.path.join(script_dir, 'models', 'lstm')
        
        # Create model directory
        model_dir = os.path.join(base_path, f"{self.clean_symbol}_lstm")
        os.makedirs(model_dir, exist_ok=True)
        
        # Save LSTM model
        self.lstm_model.save(model_dir)
        
        # Save strategy configuration
        config_path = os.path.join(model_dir, 'strategy_config.json')
        with open(config_path, 'w') as f:
            json.dump({
                'symbol': self.symbol,
                'sequence_length': self.sequence_length,
                'prediction_horizon': self.prediction_horizon,
                'threshold_pct': self.threshold_pct,
                'use_volume_profile': self.use_volume_profile,
                'last_updated': datetime.now().isoformat()
            }, f, indent=4)
        
        logger.info(f"Strategy saved to {model_dir}")
        return model_dir
    
    def load(self, base_path: str = None) -> bool:
        """
        Load the strategy models and configuration.
        
        Args:
            base_path: Base directory to load models from
            
        Returns:
            True if successful, False otherwise
        """
        # Use default path if not provided
        if base_path is None:
            base_path = os.path.join(script_dir, 'models', 'lstm')
        
        # Model directory
        model_dir = os.path.join(base_path, f"{self.clean_symbol}_lstm")
        
        try:
            # Load LSTM model
            if not self.lstm_model.load(model_dir):
                logger.error(f"Failed to load LSTM model from {model_dir}")
                return False
            
            # Load strategy configuration
            config_path = os.path.join(model_dir, 'strategy_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.symbol = config['symbol']
                self.sequence_length = config['sequence_length']
                self.prediction_horizon = config['prediction_horizon']
                self.threshold_pct = config['threshold_pct']
                self.use_volume_profile = config['use_volume_profile']
            
            self.is_trained = True
            logger.info(f"Strategy loaded from {model_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading strategy: {str(e)}")
            return False
    
    def evaluate(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        Evaluate strategy performance on test data.
        
        Args:
            data: Test data
            
        Returns:
            Dictionary of evaluation metrics
        """
        if not self.is_trained:
            logger.error("Model not trained. Call train() first.")
            return None
        
        # Prepare data if needed
        if len(data.columns) <= 5:  # Only OHLCV columns
            data = self.prepare_data(data)
        
        # Evaluate LSTM model
        model_metrics = self.lstm_model.evaluate(data)
        
        # Generate signals for each point
        signals = []
        for i in range(self.sequence_length, len(data)):
            window = data.iloc[i-self.sequence_length:i]
            signal = self.generate_signal(window)
            signals.append(signal)
        
        # Calculate strategy returns
        price_changes = data['close'].pct_change().iloc[self.sequence_length:].values
        strategy_returns = price_changes * signals
        
        # Calculate metrics
        total_return = np.sum(strategy_returns)
        win_rate = np.mean(strategy_returns > 0)
        sharpe = np.mean(strategy_returns) / np.std(strategy_returns) if np.std(strategy_returns) > 0 else 0
        
        metrics = {
            **model_metrics,
            'total_return': float(total_return),
            'win_rate': float(win_rate),
            'sharpe_ratio': float(sharpe)
        }
        
        logger.info(f"Strategy evaluation: Return={total_return:.4f}, Win Rate={win_rate:.4f}, Sharpe={sharpe:.4f}")
        return metrics
    
    def plot_predictions(self, data: pd.DataFrame, lookback_periods: int = 30) -> plt.Figure:
        """
        Plot recent price data with predictions.
        
        Args:
            data: Recent OHLCV data
            lookback_periods: Number of periods to plot
            
        Returns:
            Matplotlib figure
        """
        if not self.is_trained:
            logger.error("Model not trained. Call train() first.")
            return None
        
        # Prepare data if needed
        if len(data.columns) <= 5:  # Only OHLCV columns
            data = self.prepare_data(data)
        
        # Get recent data
        recent_data = data.iloc[-lookback_periods:]
        
        # Generate predictions for each point
        predictions = []
        for i in range(self.sequence_length, len(recent_data)):
            window = recent_data.iloc[i-self.sequence_length:i]
            pred, _ = self.predict(window)
            predictions.append(pred)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot actual prices
        ax.plot(recent_data.index[-len(predictions):], recent_data['close'].iloc[-len(predictions):], 
                label='Actual Price', color='blue')
        
        # Plot predictions
        ax.plot(recent_data.index[-len(predictions):], predictions, 
                label='LSTM Prediction', color='red', linestyle='--')
        
        # Add volume profile if available
        if self.use_volume_profile and self.volume_profile.bins is not None:
            # Create twin axes for volume profile
            ax2 = ax.twinx()
            self.volume_profile.plot_profile(ax=ax2)
            ax2.set_ylabel('Volume')
        
        ax.set_title(f'LSTM Price Predictions for {self.symbol}')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig 