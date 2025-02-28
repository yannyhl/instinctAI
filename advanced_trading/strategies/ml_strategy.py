"""
Machine Learning Strategy
------------------------
Advanced trading strategy using ensemble machine learning models.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any
import logging
from pathlib import Path
import joblib
import time
from datetime import datetime
import os

# Import ML libraries
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# Import custom modules
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils import technical_indicators as ti
from utils import signal_processing as sp
from utils import risk_management as rm
import config

# Setup logging
logger = logging.getLogger(__name__)

# Check for GPU support for ML acceleration
try:
    if config.GPU_CONFIG["use_gpu"]:
        import cuml
        from cuml.ensemble import RandomForestClassifier as cuRF
        from cuml.linear_model import LogisticRegression as cuLR
        import cudf
        logger.info("GPU acceleration enabled for ML models")
        HAS_GPU = True
    else:
        HAS_GPU = False
except ImportError:
    logger.warning("GPU libraries not available for ML. Using CPU implementation.")
    HAS_GPU = False


class MLEnsembleStrategy:
    """
    Advanced ML-based trading strategy using ensemble methods and signal processing.
    """
    
    def __init__(self, 
                config: Dict[str, Any],
                data_handler=None,
                model_dir: str = "models"):
        """
        Initialize the ML Ensemble Strategy.
        
        Args:
            config: Strategy configuration dictionary
            data_handler: Object that provides data (optional)
            model_dir: Directory for saving/loading models
        """
        self.config = config
        self.data_handler = data_handler
        self.model_dir = model_dir
        
        # Create model directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
        
        # Extract configuration parameters
        self.lookback_window = config.get("lookback_window", 30)
        self.prediction_horizon = config.get("prediction_horizon", 1)
        self.training_window = config.get("training_window", 252 * 2)  # 2 years default
        self.retraining_frequency = config.get("retraining_frequency", 30)  # Retrain every 30 days
        self.threshold_buy = config.get("threshold_buy", 0.65)
        self.threshold_sell = config.get("threshold_sell", 0.65)
        self.features = config.get("features", [])
        self.target = config.get("target", "direction")
        self.symbols = config.get("symbols", [])
        
        # Strategy state
        self.models = {}  # Dictionary to store trained models per symbol
        self.last_train_time = {}  # Dictionary to track last training time per symbol
        self.positions = {}  # Dictionary to track current positions
        self.signals = {}  # Dictionary to store current signals
        
        logger.info(f"Initialized ML Ensemble Strategy with {len(self.symbols)} symbols")
    
    def prepare_features(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Prepare features for model training and prediction.
        
        Args:
            data: Price data DataFrame
            symbol: Symbol being processed
            
        Returns:
            DataFrame with prepared features
        """
        df = data.copy()
        
        # Basic price features
        if 'open' in df.columns and 'high' in df.columns and 'low' in df.columns and 'close' in df.columns:
            # Price-based features
            df['returns'] = df['close'].pct_change()
            df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
            
            # Volatility
            df['volatility'] = df['returns'].rolling(window=20).std()
            
            # Price momentum
            for period in [5, 10, 20]:
                df[f'momentum_{period}'] = df['close'].pct_change(periods=period)
            
            # Normalized price (z-score)
            df['price_zscore'] = ti.calculate_zscore(df['close'], window=20)
        
        # Volume features if available
        if 'volume' in df.columns:
            df['volume_change'] = df['volume'].pct_change()
            df['volume_zscore'] = ti.calculate_zscore(df['volume'], window=20)
            
            # Volume momentum
            for period in [5, 10]:
                df[f'volume_momentum_{period}'] = df['volume'].pct_change(periods=period)
            
            # Volume-price relationship
            df['volume_price_ratio'] = df['volume'] / df['close']
        
        # Technical indicators
        df['rsi'] = ti.calculate_rsi(df['close'])
        
        # Updated Bollinger Bands call
        try:
            bb_upper, bb_middle, bb_lower = ti.calculate_bollinger_bands(df['close'])
            df['bb_upper'] = bb_upper
            df['bb_middle'] = bb_middle
            df['bb_lower'] = bb_lower
            df['bb_width'] = (bb_upper - bb_lower) / bb_middle
            df['bb_position'] = (df['close'] - bb_lower) / (bb_upper - bb_lower)
        except Exception as e:
            logger.warning(f"Error calculating Bollinger Bands: {e}")
        
        # Market regime - with updated function call - convert to numeric
        try:
            # Default placeholder
            df['market_regime'] = 0 
            
            if len(df) > 20:
                # Apply regime detection on the entire series - and convert to numeric
                regime = ti.detect_regime(df['returns'])
                # Convert string regime to numeric value
                if regime == "trending":
                    df['market_regime'] = 1
                elif regime == "mean_reverting":
                    df['market_regime'] = -1
                elif regime == "high_volatility":
                    df['market_regime'] = 2
                # default is 0 for unknown
        except Exception as e:
            logger.warning(f"Error detecting market regime: {e}")
        
        # Support/resistance - with updated function call
        try:
            support, resistance = ti.calculate_support_resistance(df[['high', 'low', 'close']])
            df['distance_to_support'] = (df['close'] - support) / df['close']
            df['distance_to_resistance'] = (resistance - df['close']) / df['close']
        except Exception as e:
            logger.warning(f"Error calculating support/resistance: {e}")
            df['distance_to_support'] = 0
            df['distance_to_resistance'] = 0
        
        # Signal processing
        # Apply Kalman filter for smoother price signals
        df['price_kalman'] = sp.apply_kalman_filter(df['close'])
        df['kalman_direction'] = np.sign(df['price_kalman'] - df['price_kalman'].shift(1))
        
        # Crossover signals
        fast_ma = df['close'].rolling(window=10).mean()
        slow_ma = df['close'].rolling(window=30).mean()
        df['ma_crossover'] = sp.calculate_crossovers(fast_ma, slow_ma)
        
        # Adaptive thresholds
        upper_threshold, lower_threshold = sp.calculate_adaptive_thresholds(df['close'])
        df['upper_threshold'] = upper_threshold
        df['lower_threshold'] = lower_threshold
        df['threshold_signal'] = np.where(df['close'] > upper_threshold, 1, 
                                         np.where(df['close'] < lower_threshold, -1, 0))
        
        # Feature engineering: create target variable for training
        # Direction of price movement over prediction horizon
        df['direction'] = np.where(df['close'].shift(-self.prediction_horizon) > df['close'], 1, -1)
        
        # Filter out rows with NaN values
        df = df.dropna()
        
        return df
    
    def create_models(self) -> Dict[str, Any]:
        """
        Create ensemble models for prediction.
        
        Returns:
            Dictionary of model objects
        """
        models = {}
        
        # Create CPU-based models
        if not HAS_GPU:
            # Random Forest Classifier
            models['rf'] = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42
            )
            
            # Gradient Boosting Classifier
            models['gb'] = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            
            # Logistic Regression
            models['lr'] = Pipeline([
                ('scaler', StandardScaler()),
                ('classifier', LogisticRegression(C=0.1, max_iter=1000, random_state=42))
            ])
        else:
            # GPU-accelerated models
            models['rf'] = cuRF(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42
            )
            
            # Logistic Regression on GPU
            models['lr'] = cuLR(
                C=0.1,
                max_iter=1000,
                random_state=42
            )
            
            # For GB, use CPU version as cuML doesn't have GBM yet
            models['gb'] = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
        
        return models
    
    def train_models(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """
        Train models on historical data.
        
        Args:
            data: Prepared feature data
            symbol: Symbol being processed
            
        Returns:
            Dictionary of trained models
        """
        # Record training time
        self.last_train_time[symbol] = datetime.now()
        
        # Create new models
        models = self.create_models()
        
        # Prepare training data
        X = data.drop([self.target, 'open', 'high', 'low', 'close', 'volume'], axis=1, errors='ignore')
        y = data[self.target]
        
        # Log feature importance at the end
        feature_names = X.columns.tolist()
        
        # Create TimeSeriesSplit for cross-validation
        tscv = TimeSeriesSplit(n_splits=5)
        
        # Training stats
        model_metrics = {}
        
        # Train each model
        for model_name, model in models.items():
            start_time = time.time()
            logger.info(f"Training {model_name} model for {symbol}")
            
            # Track metrics across folds
            fold_metrics = {
                'accuracy': [],
                'precision': [],
                'recall': [],
                'f1': []
            }
            
            # Time series cross-validation
            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
                
                # Handle GPU dataframes if needed
                if HAS_GPU and model_name in ['rf', 'lr']:
                    X_train_gpu = cudf.DataFrame.from_pandas(X_train)
                    y_train_gpu = cudf.Series(y_train.values)
                    
                    # Train model
                    model.fit(X_train_gpu, y_train_gpu)
                    
                    # Predict on test set
                    X_test_gpu = cudf.DataFrame.from_pandas(X_test)
                    y_pred = model.predict(X_test_gpu)
                    y_pred = y_pred.to_pandas().values
                else:
                    # Regular training
                    model.fit(X_train, y_train)
                    y_pred = model.predict(X_test)
                
                # Calculate metrics
                fold_metrics['accuracy'].append(accuracy_score(y_test, y_pred))
                fold_metrics['precision'].append(precision_score(y_test, y_pred, average='binary', zero_division=0))
                fold_metrics['recall'].append(recall_score(y_test, y_pred, average='binary', zero_division=0))
                fold_metrics['f1'].append(f1_score(y_test, y_pred, average='binary', zero_division=0))
            
            # Average metrics across folds
            for metric in fold_metrics:
                model_metrics[f"{model_name}_{metric}"] = np.mean(fold_metrics[metric])
            
            # Log training completion
            training_time = time.time() - start_time
            logger.info(f"Completed training {model_name} for {symbol} in {training_time:.2f} seconds")
            logger.info(f"{model_name} Metrics - Accuracy: {model_metrics[f'{model_name}_accuracy']:.4f}, "
                       f"F1: {model_metrics[f'{model_name}_f1']:.4f}")
            
            # Feature importance for supported models
            if model_name == 'rf' and not HAS_GPU:
                importances = model.feature_importances_
                indices = np.argsort(importances)[::-1]
                top_features = [(feature_names[i], importances[i]) for i in indices[:10]]
                logger.info(f"Top features for {symbol} ({model_name}): {top_features}")
        
        # Final training on full dataset
        for model_name, model in models.items():
            if HAS_GPU and model_name in ['rf', 'lr']:
                X_gpu = cudf.DataFrame.from_pandas(X)
                y_gpu = cudf.Series(y.values)
                model.fit(X_gpu, y_gpu)
            else:
                model.fit(X, y)
        
        # Save models - Use a safe filename that replaces / with _
        safe_symbol = symbol.replace('/', '_')
        model_path = os.path.join(self.model_dir, f"{safe_symbol}_models.joblib")
        joblib.dump(models, model_path)
        logger.info(f"Saved models for {symbol} to {model_path}")
        
        # Save metrics
        metrics_path = os.path.join(self.model_dir, f"{safe_symbol}_metrics.joblib")
        joblib.dump(model_metrics, metrics_path)
        
        return models
    
    def load_models(self, symbol: str) -> Dict[str, Any]:
        """
        Load previously trained models for a symbol.
        
        Args:
            symbol: Symbol to load models for
            
        Returns:
            Dictionary of trained models or None if not found
        """
        # Use a safe filename that replaces / with _
        safe_symbol = symbol.replace('/', '_')
        model_path = os.path.join(self.model_dir, f"{safe_symbol}_models.joblib")
        
        if os.path.exists(model_path):
            try:
                models = joblib.load(model_path)
                logger.info(f"Loaded existing models for {symbol}")
                return models
            except Exception as e:
                logger.error(f"Error loading models for {symbol}: {e}")
                return None
        else:
            logger.info(f"No existing models found for {symbol}")
            return None
    
    def needs_retraining(self, symbol: str) -> bool:
        """
        Check if models need retraining based on the configured frequency.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if retraining is needed, False otherwise
        """
        if symbol not in self.last_train_time:
            return True
        
        days_since_training = (datetime.now() - self.last_train_time[symbol]).days
        return days_since_training >= self.retraining_frequency
    
    def generate_predictions(self, data: pd.DataFrame, symbol: str) -> np.ndarray:
        """
        Generate ensemble predictions from all models.
        
        Args:
            data: Prepared feature data
            symbol: Symbol being processed
            
        Returns:
            Array of ensemble predictions
        """
        # Ensure models are loaded
        if symbol not in self.models or self.models[symbol] is None:
            self.models[symbol] = self.load_models(symbol)
            
            if self.models[symbol] is None:
                logger.error(f"No models available for {symbol}. Cannot generate predictions.")
                return np.zeros(len(data))
        
        # Prepare features for prediction
        X = data.drop([self.target, 'open', 'high', 'low', 'close', 'volume'], axis=1, errors='ignore')
        
        # Generate predictions from each model
        model_predictions = {}
        
        for model_name, model in self.models[symbol].items():
            if HAS_GPU and model_name in ['rf', 'lr']:
                X_gpu = cudf.DataFrame.from_pandas(X)
                preds = model.predict_proba(X_gpu)[:, 1].to_pandas().values
            else:
                try:
                    preds = model.predict_proba(X)[:, 1]
                except AttributeError:
                    # For models without predict_proba
                    preds = model.predict(X)
            
            model_predictions[model_name] = preds
        
        # Combine predictions using weighted average
        ensemble_weights = {
            'rf': 0.5,
            'gb': 0.3,
            'lr': 0.2
        }
        
        # Initialize ensemble prediction array
        ensemble_predictions = np.zeros(len(X))
        total_weight = 0
        
        # Weight and combine predictions
        for model_name, predictions in model_predictions.items():
            if model_name in ensemble_weights:
                weight = ensemble_weights[model_name]
                ensemble_predictions += predictions * weight
                total_weight += weight
        
        # Normalize predictions
        if total_weight > 0:
            ensemble_predictions /= total_weight
        
        return ensemble_predictions
    
    def generate_signals(self, predictions: np.ndarray, symbol: str) -> np.ndarray:
        """
        Generate trading signals from ensemble predictions.
        
        Args:
            predictions: Model predictions
            symbol: Symbol being processed
            
        Returns:
            Array of trading signals (1=Buy, -1=Sell, 0=Hold)
        """
        signals = np.zeros(len(predictions))
        
        # Apply hysteresis filtering to reduce noise and false signals
        for i in range(len(predictions)):
            # Buy signal
            if predictions[i] > self.threshold_buy:
                signals[i] = 1
            # Sell signal
            elif predictions[i] < (1 - self.threshold_sell):
                signals[i] = -1
            # Hold (neutral)
            else:
                signals[i] = 0
        
        # Apply hysteresis filter to reduce false signals
        filtered_signals = sp.apply_hysteresis_filter(
            signals, 
            enter_threshold=0.5,  # Requires signal strength of at least 0.5 to enter
            exit_threshold=0.2    # Will exit if signal drops below 0.2
        )
        
        return filtered_signals
    
    def update(self, new_data: Dict[str, pd.DataFrame]) -> Dict[str, np.ndarray]:
        """
        Update the strategy with new data and generate signals.
        
        Args:
            new_data: Dictionary of DataFrames with market data per symbol
            
        Returns:
            Dictionary of signals per symbol
        """
        all_signals = {}
        
        # Process each symbol
        for symbol in self.symbols:
            if symbol not in new_data:
                logger.warning(f"No data provided for symbol {symbol}")
                continue
            
            data = new_data[symbol]
            
            # Prepare features
            prepared_data = self.prepare_features(data, symbol)
            
            # Check if we need to train/retrain models
            if symbol not in self.models or self.models[symbol] is None or self.needs_retraining(symbol):
                logger.info(f"Training models for {symbol}")
                
                # Take training subset of data
                training_data = prepared_data.iloc[-self.training_window:]
                
                # Train models
                self.models[symbol] = self.train_models(training_data, symbol)
            
            # Generate predictions
            predictions = self.generate_predictions(prepared_data, symbol)
            
            # Generate trading signals
            signals = self.generate_signals(predictions, symbol)
            
            # Store the signals
            all_signals[symbol] = signals[-1]  # Return only the most recent signal
            self.signals[symbol] = signals[-1]
        
        return all_signals
    
    def get_position_sizing(self, symbol: str, price: float, capital: float) -> float:
        """
        Calculate position size based on risk management rules.
        
        Args:
            symbol: Symbol to calculate position for
            price: Current price
            capital: Available capital
            
        Returns:
            Position size (quantity to trade)
        """
        # Default risk values
        risk_per_trade = 0.02  # 2% risk per trade
        stop_loss_pct = 0.05   # 5% stop loss
        
        # Calculate position size using risk management function
        position_size = rm.calculate_position_size(
            capital=capital,
            risk_per_trade=risk_per_trade,
            stop_loss_pct=stop_loss_pct,
            entry_price=price,
            volatility_factor=1.0  # Default volatility factor
        )
        
        return position_size
    
    def get_current_positions(self) -> Dict[str, float]:
        """
        Get current positions across all symbols.
        
        Returns:
            Dictionary of positions per symbol
        """
        return self.positions
    
    def get_current_signals(self) -> Dict[str, float]:
        """
        Get current signals across all symbols.
        
        Returns:
            Dictionary of signals per symbol
        """
        return self.signals 