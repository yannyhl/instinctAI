"""
Adaptive Integration
------------------
Integrates the ML ensemble framework with the AdaptiveMetaStrategy.
This module serves as the bridge between ML predictions and strategy execution.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import logging
import joblib
import os
import time
from datetime import datetime, timedelta

# Import internal modules
from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager
from advanced_trading.models.ml_ensemble.feature_engineering import FeatureEngineer
from advanced_trading.utils.bayesian_changepoint import detect_market_regimes

# Get the logger
logger = logging.getLogger(__name__)

class MLStrategyIntegration:
    """
    Integration between ML ensembles and trading strategies.
    
    This class:
    1. Generates predictions from ML models
    2. Converts predictions into actionable signals
    3. Tracks prediction performance
    4. Dynamically adjusts strategy weights based on ML insights
    5. Provides real-time model updating capabilities
    
    Parameters:
    -----------
    ensemble_path : str
        Path to saved ensemble model
    feature_engineer : Optional[FeatureEngineer]
        Pre-configured feature engineer (or None to create a new one)
    prediction_threshold : float
        Threshold for converting probabilities to signals (-1 to 1)
    confidence_scaling : bool
        Whether to scale signals by prediction confidence
    update_interval : int
        How often to update models (in hours, 0 to disable)
    signal_smoothing : int
        Window for exponential smoothing of signals (0 to disable)
    """
    
    def __init__(
        self,
        ensemble_path: str,
        feature_engineer: Optional[FeatureEngineer] = None,
        prediction_threshold: float = 0.55,
        confidence_scaling: bool = True,
        update_interval: int = 24,
        signal_smoothing: int = 3
    ):
        self.ensemble_path = Path(ensemble_path)
        self.prediction_threshold = prediction_threshold
        self.confidence_scaling = confidence_scaling
        self.update_interval = update_interval
        self.signal_smoothing = signal_smoothing
        
        # Load the ensemble
        if not self.ensemble_path.exists():
            raise FileNotFoundError(f"Ensemble model not found: {self.ensemble_path}")
        
        self.ensemble = EnsembleManager.load(self.ensemble_path)
        logger.info(f"Loaded ensemble model from {self.ensemble_path}")
        
        # Initialize feature engineer if not provided
        if feature_engineer is None:
            self.feature_engineer = FeatureEngineer(
                handle_missing='fill',
                scaling='standard'
            )
        else:
            self.feature_engineer = feature_engineer
        
        # Prediction history
        self.prediction_history = pd.DataFrame()
        
        # Performance tracking
        self.performance_metrics = {}
        
        # Last update time
        self.last_update_time = datetime.now()
    
    def generate_signal(
        self, 
        market_data: Dict[str, pd.DataFrame],
        symbol: str,
        current_regime: Optional[str] = None
    ) -> float:
        """
        Generate trading signal from ML predictions.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
        symbol : str
            Symbol to generate signal for
        current_regime : Optional[str]
            Current market regime
            
        Returns:
        --------
        float
            Trading signal (-1.0 to 1.0)
        """
        if symbol not in market_data:
            logger.error(f"Symbol {symbol} not found in market data")
            return 0.0
        
        try:
            # Convert market data to features
            features = self.feature_engineer.create_features(market_data[symbol])
            
            # Get the most recent data point
            latest_features = features.iloc[-1:].copy()
            
            # Generate prediction
            prediction = self.ensemble.predict(latest_features, current_regime)
            
            # Convert prediction to signal
            signal = self._convert_prediction_to_signal(prediction[0])
            
            # Apply smoothing if enabled
            if self.signal_smoothing > 0 and len(self.prediction_history) > 0:
                prev_signals = self.prediction_history['signal'].values[-self.signal_smoothing:]
                if len(prev_signals) > 0:
                    # Exponential smoothing
                    alpha = 2 / (self.signal_smoothing + 1)
                    smoothed_signal = alpha * signal
                    for i, prev_signal in enumerate(reversed(prev_signals)):
                        smoothed_signal += (1 - alpha) * prev_signal * (1 - alpha) ** i
                    signal = smoothed_signal
            
            # Store prediction in history
            self._update_prediction_history(
                symbol=symbol,
                prediction=prediction[0],
                signal=signal,
                timestamp=market_data[symbol].index[-1],
                regime=current_regime
            )
            
            # Check if models need updating
            self._check_update_models(market_data)
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating ML signal: {str(e)}")
            return 0.0
    
    def update_with_actual_return(
        self, 
        symbol: str, 
        actual_return: float,
        prediction_timestamp: Optional[pd.Timestamp] = None
    ) -> None:
        """
        Update performance tracking with actual return.
        
        Parameters:
        -----------
        symbol : str
            Trading symbol
        actual_return : float
            Actual return for the prediction
        prediction_timestamp : Optional[pd.Timestamp]
            Timestamp of the prediction to update
        """
        if len(self.prediction_history) == 0:
            return
        
        if prediction_timestamp is None:
            # Use the latest prediction
            idx = len(self.prediction_history) - 1
        else:
            # Find the prediction with matching timestamp
            mask = (self.prediction_history['timestamp'] == prediction_timestamp) & \
                   (self.prediction_history['symbol'] == symbol)
            if not mask.any():
                logger.warning(f"No prediction found for {symbol} at {prediction_timestamp}")
                return
            
            idx = mask.idxmax()
        
        # Update the prediction history
        self.prediction_history.loc[idx, 'actual_return'] = actual_return
        
        # Calculate if the prediction was correct
        prediction = self.prediction_history.loc[idx, 'prediction']
        signal = self.prediction_history.loc[idx, 'signal']
        
        # For classification: signal direction matches return direction
        if self.ensemble.model_type == 'classification':
            is_correct = (signal > 0 and actual_return > 0) or (signal < 0 and actual_return < 0)
        else:  # For regression: predicted return is within 50% of actual return
            is_correct = abs(prediction - actual_return) <= abs(actual_return) * 0.5
        
        self.prediction_history.loc[idx, 'is_correct'] = is_correct
        
        # Update performance metrics
        self._update_performance_metrics()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics.
        
        Returns:
        --------
        Dict[str, Any]
            Dictionary of performance metrics
        """
        if not self.performance_metrics:
            self._update_performance_metrics()
        
        return self.performance_metrics
    
    def get_prediction_history(self) -> pd.DataFrame:
        """
        Get prediction history.
        
        Returns:
        --------
        pd.DataFrame
            Prediction history dataframe
        """
        return self.prediction_history.copy()
    
    def update_models(
        self, 
        market_data: Dict[str, pd.DataFrame],
        target_data: Optional[Dict[str, pd.Series]] = None
    ) -> None:
        """
        Update ML models with new data.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
        target_data : Optional[Dict[str, pd.Series]]
            Dictionary of target series by symbol
        """
        if len(market_data) == 0:
            logger.warning("No market data provided for model update")
            return
        
        # Use target data if provided, otherwise generate from market data
        if target_data is None:
            target_data = {}
            for symbol, data in market_data.items():
                target_data[symbol] = self.feature_engineer.create_target_variable(
                    data,
                    method='binary_direction' if self.ensemble.model_type == 'classification' else 'regression_return'
                )
        
        # Update model weights based on recent performance
        for symbol, data in market_data.items():
            if symbol not in target_data:
                logger.warning(f"No target data for symbol {symbol}")
                continue
            
            # Get recent predictions and actual targets
            mask = self.prediction_history['symbol'] == symbol
            if not mask.any():
                logger.warning(f"No prediction history for symbol {symbol}")
                continue
            
            recent_preds = self.prediction_history[mask].copy()
            if 'actual_return' not in recent_preds.columns or recent_preds['actual_return'].isnull().all():
                logger.warning(f"No actual returns recorded for symbol {symbol}")
                continue
            
            # Filter to predictions with actual returns
            recent_preds = recent_preds[recent_preds['actual_return'].notnull()]
            if len(recent_preds) == 0:
                continue
            
            # Get recent model predictions
            try:
                # Extract the predictions per model from the ensemble (more complex in real system)
                dummy_recent_preds = {}
                for model_name in self.ensemble.model_names:
                    # This is a simplification - in reality you'd need to extract actual model predictions
                    dummy_recent_preds[model_name] = np.array([
                        p * (0.9 + 0.2 * np.random.rand()) for p in recent_preds['prediction'].values
                    ])
                
                # Update weights
                self.ensemble.update_weights(
                    recent_predictions=dummy_recent_preds,
                    recent_targets=np.array(recent_preds['actual_return'] > 0).astype(int) \
                        if self.ensemble.model_type == 'classification' else np.array(recent_preds['actual_return']),
                    current_regime=recent_preds['regime'].iloc[-1] if 'regime' in recent_preds.columns else None
                )
                
                logger.info(f"Updated ensemble weights for {symbol}")
            except Exception as e:
                logger.error(f"Error updating ensemble weights: {str(e)}")
        
        # Save updated ensemble
        self.ensemble.save(self.ensemble_path)
        logger.info(f"Saved updated ensemble to {self.ensemble_path}")
        
        # Update last update time
        self.last_update_time = datetime.now()
    
    def detect_current_regime(
        self, 
        price_data: pd.Series, 
        lookback_days: int = 60,
        n_regimes: int = 3
    ) -> str:
        """
        Detect the current market regime.
        
        Parameters:
        -----------
        price_data : pd.Series
            Series of prices
        lookback_days : int
            Number of days to look back for regime detection
        n_regimes : int
            Number of regimes to detect
            
        Returns:
        --------
        str
            Detected regime ID
        """
        # Ensure sufficient data
        if len(price_data) < lookback_days:
            logger.warning("Insufficient data for regime detection")
            return "0"  # default regime
        
        # Get recent data
        recent_prices = price_data[-lookback_days:]
        
        # Detect regimes
        regimes = detect_market_regimes(
            price_series=recent_prices,
            n_regimes=n_regimes
        )
        
        # Return the most recent regime
        return str(regimes.iloc[-1])
    
    def _convert_prediction_to_signal(self, prediction: float) -> float:
        """Convert ML prediction to trading signal"""
        if self.ensemble.model_type == 'classification':
            # For classification, prediction is a probability (0-1)
            if prediction > self.prediction_threshold:
                signal = 1.0
            elif prediction < (1 - self.prediction_threshold):
                signal = -1.0
            else:
                signal = 0.0
            
            # Scale by confidence if enabled
            if self.confidence_scaling:
                confidence = max(prediction, 1 - prediction) * 2 - 1  # Transform to 0-1 scale
                signal *= confidence
        else:
            # For regression, prediction is a return prediction
            # Scale to -1 to 1 range using tanh
            signal = np.tanh(prediction * 3)  # Scale factor of 3 to get reasonable values
        
        return signal
    
    def _update_prediction_history(
        self, 
        symbol: str, 
        prediction: float, 
        signal: float,
        timestamp: pd.Timestamp,
        regime: Optional[str] = None
    ) -> None:
        """Update prediction history"""
        new_row = {
            'symbol': symbol,
            'timestamp': timestamp,
            'prediction': prediction,
            'signal': signal,
            'regime': regime if regime is not None else 'unknown'
        }
        
        # Append to history - using concat instead of append (deprecated)
        new_row_df = pd.DataFrame([new_row])
        if not isinstance(self.prediction_history, pd.DataFrame) or len(self.prediction_history) == 0:
            self.prediction_history = new_row_df
        else:
            self.prediction_history = pd.concat([self.prediction_history, new_row_df], ignore_index=True)
        
        # Trim history to avoid memory growth
        if len(self.prediction_history) > 1000:
            self.prediction_history = self.prediction_history.iloc[-1000:]
    
    def _update_performance_metrics(self) -> None:
        """Update performance metrics based on prediction history"""
        if len(self.prediction_history) == 0:
            return
        
        # Filter to predictions with actual returns
        evaluated_preds = self.prediction_history[self.prediction_history['actual_return'].notnull()].copy()
        if len(evaluated_preds) == 0:
            return
        
        metrics = {}
        
        # Overall accuracy
        metrics['accuracy'] = evaluated_preds['is_correct'].mean()
        
        # Metrics by signal direction
        long_preds = evaluated_preds[evaluated_preds['signal'] > 0]
        short_preds = evaluated_preds[evaluated_preds['signal'] < 0]
        
        metrics['long_accuracy'] = long_preds['is_correct'].mean() if len(long_preds) > 0 else np.nan
        metrics['short_accuracy'] = short_preds['is_correct'].mean() if len(short_preds) > 0 else np.nan
        
        # Average return by signal direction
        metrics['long_avg_return'] = long_preds['actual_return'].mean() if len(long_preds) > 0 else np.nan
        metrics['short_avg_return'] = short_preds['actual_return'].mean() if len(short_preds) > 0 else np.nan
        
        # Metrics by regime
        metrics['regime_metrics'] = {}
        for regime in evaluated_preds['regime'].unique():
            regime_preds = evaluated_preds[evaluated_preds['regime'] == regime]
            metrics['regime_metrics'][regime] = {
                'accuracy': regime_preds['is_correct'].mean(),
                'avg_return': regime_preds['actual_return'].mean(),
                'count': len(regime_preds)
            }
        
        # Store metrics
        self.performance_metrics = metrics
    
    def _check_update_models(self, market_data: Dict[str, pd.DataFrame]) -> None:
        """Check if models need updating and update if necessary"""
        # Skip if update interval is 0 (disabled)
        if self.update_interval == 0:
            return
        
        # Check if it's time to update
        hours_since_update = (datetime.now() - self.last_update_time).total_seconds() / 3600
        if hours_since_update >= self.update_interval:
            logger.info(f"Time to update models (last update: {self.last_update_time})")
            self.update_models(market_data)


class AdaptiveMLStrategy:
    """
    Adapter class for using ML ensembles in AdaptiveMetaStrategy.
    
    This class follows the strategy interface expected by AdaptiveMetaStrategy
    and internally uses the ML ensemble for signal generation.
    
    Parameters:
    -----------
    ensemble_path : str
        Path to saved ensemble model
    symbol : str
        Trading symbol
    timeframe : str
        Trading timeframe
    param_dict : Dict[str, Any]
        Additional parameters
    """
    
    def __init__(
        self,
        ensemble_path: str,
        symbol: str = 'BTC',
        timeframe: str = '1h',
        param_dict: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        
        # Default parameters
        default_params = {
            'prediction_threshold': 0.55,
            'confidence_scaling': True,
            'signal_smoothing': 3
        }
        
        # Update with provided parameters
        self.params = default_params
        if param_dict is not None:
            self.params.update(param_dict)
        
        # Initialize ML integration
        self.ml_integration = MLStrategyIntegration(
            ensemble_path=ensemble_path,
            prediction_threshold=self.params['prediction_threshold'],
            confidence_scaling=self.params['confidence_scaling'],
            signal_smoothing=self.params['signal_smoothing']
        )
        
        # Trading state
        self.current_position = 0
        self.last_signal = 0
        self.market_regimes = {}
    
    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> float:
        """
        Generate trading signals using ML predictions.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
            
        Returns:
        --------
        float
            Trading signal (-1.0 to 1.0)
        """
        if self.symbol not in market_data:
            logger.error(f"Symbol {self.symbol} not found in market data")
            return 0.0
        
        # Detect market regime
        if len(market_data[self.symbol]) > 60:
            current_regime = self.ml_integration.detect_current_regime(
                market_data[self.symbol]['close']
            )
            self.market_regimes[self.symbol] = current_regime
        else:
            current_regime = self.market_regimes.get(self.symbol, "0")
        
        # Generate signal
        signal = self.ml_integration.generate_signal(
            market_data=market_data,
            symbol=self.symbol,
            current_regime=current_regime
        )
        
        # Store last signal
        self.last_signal = signal
        
        return signal
    
    def update_state(
        self, 
        current_position: float, 
        market_data: Dict[str, pd.DataFrame]
    ) -> None:
        """
        Update strategy state with current position.
        
        Parameters:
        -----------
        current_position : float
            Current position size (-1.0 to 1.0)
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
        """
        # Store position
        self.current_position = current_position
        
        # Calculate returns if position changed
        if current_position != 0 and len(market_data[self.symbol]) >= 2:
            # Calculate return from the last two bars
            last_close = market_data[self.symbol]['close'].iloc[-1]
            prev_close = market_data[self.symbol]['close'].iloc[-2]
            actual_return = (last_close / prev_close - 1) * 100  # percentage
            
            # If short position, reverse return
            if current_position < 0:
                actual_return = -actual_return
            
            # Update ML performance tracking
            timestamp = market_data[self.symbol].index[-2]  # Previous bar's timestamp
            self.ml_integration.update_with_actual_return(
                symbol=self.symbol,
                actual_return=actual_return,
                prediction_timestamp=timestamp
            )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get ML performance metrics.
        
        Returns:
        --------
        Dict[str, Any]
            Dictionary of performance metrics
        """
        return self.ml_integration.get_performance_metrics()
    
    def get_current_regime(self) -> str:
        """
        Get current market regime.
        
        Returns:
        --------
        str
            Current market regime
        """
        return self.market_regimes.get(self.symbol, "unknown")
    
    def get_params(self) -> Dict[str, Any]:
        """
        Get strategy parameters.
        
        Returns:
        --------
        Dict[str, Any]
            Strategy parameters
        """
        return self.params.copy() 