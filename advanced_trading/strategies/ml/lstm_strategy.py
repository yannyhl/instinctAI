"""
LSTM Trading Strategy

This strategy uses Long Short-Term Memory (LSTM) neural networks for price prediction
and trading signal generation. It leverages deep learning techniques to capture
complex patterns in time series data.

The strategy works by:
1. Processing historical data through feature engineering
2. Feeding processed data into an LSTM model
3. Generating price predictions for different horizons
4. Converting predictions into trading signals
5. Managing positions based on signal strength and risk parameters

Tags: [machine_learning, deep_learning, lstm, neural_network, predictive]
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta
import os
import json
import pickle
from sklearn.preprocessing import StandardScaler

# Import TensorFlow with error handling
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logging.warning("TensorFlow not available, LSTM strategy will use pre-trained models only")

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class LSTMStrategy(BaseStrategy):
    """
    LSTM-based Trading Strategy.
    
    This strategy uses LSTM neural networks to predict price movements and
    generate trading signals. It can use pre-trained models or train new ones
    on historical data.
    
    Args:
        symbols: List of symbols to trade
        prediction_horizon: Time horizon for predictions in minutes
        lookback_window: Number of periods to look back for prediction
        model_path: Path to pre-trained model or directory to save new models
        train_model: Whether to train a new model on startup
        features: List of features to use in the model
        signal_threshold: Threshold for converting predictions to signals
        stop_loss_pct: Stop loss percentage
        take_profit_pct: Take profit percentage
        position_size: Size of position as percentage of available capital
        max_positions: Maximum number of concurrent positions
    """
    
    # Required data for this strategy
    REQUIRED_DATA = ["ohlcv", "indicator"]
    
    # Default parameters
    DEFAULT_PARAMS = {
        "prediction_horizon": 60,     # 60-minute prediction horizon
        "lookback_window": 48,        # 48 periods of lookback
        "model_path": "models/lstm",  # Path for models
        "train_model": False,         # Don't train by default
        "features": [                 # Default features
            "close", "volume", "rsi", "macd", "bollinger_b"
        ],
        "signal_threshold": 0.005,    # 0.5% price movement threshold
        "stop_loss_pct": 0.02,        # 2% stop loss
        "take_profit_pct": 0.04,      # 4% take profit
        "position_size": 0.1,         # 10% of capital per position
        "max_positions": 3,           # Maximum 3 concurrent positions
    }
    
    def __init__(
        self,
        symbols: List[str],
        prediction_horizon: int = DEFAULT_PARAMS["prediction_horizon"],
        lookback_window: int = DEFAULT_PARAMS["lookback_window"],
        model_path: str = DEFAULT_PARAMS["model_path"],
        train_model: bool = DEFAULT_PARAMS["train_model"],
        features: List[str] = None,
        signal_threshold: float = DEFAULT_PARAMS["signal_threshold"],
        stop_loss_pct: float = DEFAULT_PARAMS["stop_loss_pct"],
        take_profit_pct: float = DEFAULT_PARAMS["take_profit_pct"],
        position_size: float = DEFAULT_PARAMS["position_size"],
        max_positions: int = DEFAULT_PARAMS["max_positions"]
    ):
        """Initialize the LSTM strategy."""
        super().__init__(name="LSTMStrategy")
        
        # Check TensorFlow availability
        if train_model and not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for training models")
        
        # Store parameters
        self.symbols = symbols
        self.prediction_horizon = prediction_horizon
        self.lookback_window = lookback_window
        self.model_path = model_path
        self.train_model = train_model
        self.features = features or self.DEFAULT_PARAMS["features"]
        self.signal_threshold = signal_threshold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.position_size = position_size
        self.max_positions = max_positions
        
        # State variables
        self.models = {}
        self.scalers = {}
        self.data_buffer = {symbol: [] for symbol in symbols}
        self.active_positions = {}
        self.predictions = {}
        
        logger.info(f"Initialized LSTMStrategy with {len(symbols)} symbols")
    
    def initialize(self, data_provider, execution_handler, risk_manager=None):
        """
        Initialize the strategy with required components.
        
        Args:
            data_provider: Provider for market data
            execution_handler: Handler for executing orders
            risk_manager: Optional risk management component
        """
        super().initialize(data_provider, execution_handler, risk_manager)
        
        # Create model directory if it doesn't exist
        os.makedirs(self.model_path, exist_ok=True)
        
        # Initialize models for each symbol
        for symbol in self.symbols:
            # Load or train model
            try:
                if self.train_model:
                    self._train_model(symbol)
                else:
                    self._load_model(symbol)
            except Exception as e:
                logger.error(f"Error initializing model for {symbol}: {e}")
        
        # Load historical data to initialize buffer
        self._initialize_data_buffer()
        
        logger.info("LSTMStrategy initialized")
    
    def _initialize_data_buffer(self):
        """Initialize data buffer with historical data."""
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=self.lookback_window * self.prediction_horizon)
        
        for symbol in self.symbols:
            try:
                # Get historical data
                data = self.data_provider.get_historical_data(
                    symbol, 
                    start_date=start_time,
                    end_date=end_time,
                    interval=f"{self.prediction_horizon}m"
                )
                
                if data is not None and len(data) > 0:
                    # Process data and add to buffer
                    processed_data = self._process_data(symbol, data)
                    self.data_buffer[symbol] = processed_data
                    logger.info(f"Initialized data buffer for {symbol} with {len(processed_data)} records")
                else:
                    logger.warning(f"No historical data available for {symbol}")
            except Exception as e:
                logger.error(f"Error initializing data buffer for {symbol}: {e}")
    
    def _load_model(self, symbol: str):
        """
        Load pre-trained model for a symbol.
        
        Args:
            symbol: Symbol to load model for
        """
        model_file = os.path.join(self.model_path, f"{symbol}_lstm_model.h5")
        scaler_file = os.path.join(self.model_path, f"{symbol}_scaler.pkl")
        
        if not os.path.exists(model_file) or not os.path.exists(scaler_file):
            logger.warning(f"Pre-trained model not found for {symbol}, will use default model")
            return
        
        try:
            # Load the model
            self.models[symbol] = load_model(model_file)
            
            # Load the scaler
            with open(scaler_file, 'rb') as f:
                self.scalers[symbol] = pickle.load(f)
            
            logger.info(f"Loaded pre-trained model for {symbol}")
        except Exception as e:
            logger.error(f"Error loading model for {symbol}: {e}")
    
    def _train_model(self, symbol: str):
        """
        Train a new LSTM model for a symbol.
        
        Args:
            symbol: Symbol to train model for
        """
        if not TENSORFLOW_AVAILABLE:
            logger.error("TensorFlow not available, cannot train model")
            return
        
        logger.info(f"Training LSTM model for {symbol}")
        
        try:
            # Get historical data for training
            end_time = datetime.now()
            # Get at least 60 days of data for training
            start_time = end_time - timedelta(days=60)
            
            data = self.data_provider.get_historical_data(
                symbol, 
                start_date=start_time,
                end_date=end_time,
                interval=f"{self.prediction_horizon}m"
            )
            
            if data is None or len(data) < 100:
                logger.warning(f"Insufficient data for {symbol}, need at least 100 samples")
                return
            
            # Process data for training
            X, y, scaler = self._prepare_training_data(data)
            
            if X is None or y is None or X.shape[0] < 100:
                logger.warning(f"Insufficient processed data for {symbol}")
                return
            
            # Split data into training and validation sets
            split_idx = int(X.shape[0] * 0.8)
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            
            # Build and train model
            model = self._build_model(X_train.shape[1:])
            
            # Define callbacks
            callbacks = [
                EarlyStopping(patience=10, restore_best_weights=True),
                ModelCheckpoint(
                    os.path.join(self.model_path, f"{symbol}_lstm_model.h5"),
                    save_best_only=True
                )
            ]
            
            # Train model
            model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=50,
                batch_size=32,
                callbacks=callbacks,
                verbose=0
            )
            
            # Save model and scaler
            model.save(os.path.join(self.model_path, f"{symbol}_lstm_model.h5"))
            with open(os.path.join(self.model_path, f"{symbol}_scaler.pkl"), 'wb') as f:
                pickle.dump(scaler, f)
            
            # Store model and scaler in memory
            self.models[symbol] = model
            self.scalers[symbol] = scaler
            
            logger.info(f"Trained and saved LSTM model for {symbol}")
            
        except Exception as e:
            logger.error(f"Error training model for {symbol}: {e}")
    
    def _build_model(self, input_shape: Tuple[int, int]) -> Sequential:
        """
        Build LSTM model architecture.
        
        Args:
            input_shape: Shape of input data
            
        Returns:
            Compiled Keras LSTM model
        """
        model = Sequential([
            LSTM(100, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),
            LSTM(50),
            Dropout(0.2),
            Dense(1)
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='mse'
        )
        
        return model
    
    def _prepare_training_data(self, data: pd.DataFrame) -> Tuple:
        """
        Prepare data for LSTM model training.
        
        Args:
            data: Historical data
            
        Returns:
            Tuple of (X, y, scaler)
        """
        try:
            # Extract features
            df = self._extract_features(data)
            if df is None or len(df) < self.lookback_window + 1:
                return None, None, None
            
            # Create scaler
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(df)
            
            # Create sequences
            X, y = [], []
            for i in range(len(scaled_data) - self.lookback_window):
                X.append(scaled_data[i:i+self.lookback_window])
                # Target is the close price change
                next_close = data.iloc[i+self.lookback_window]['close']
                current_close = data.iloc[i+self.lookback_window-1]['close']
                price_change = (next_close - current_close) / current_close
                y.append(price_change)
            
            return np.array(X), np.array(y), scaler
            
        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return None, None, None
    
    def _extract_features(self, data: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Extract features from raw data.
        
        Args:
            data: Raw OHLCV data
            
        Returns:
            DataFrame with extracted features
        """
        try:
            df = pd.DataFrame()
            
            # Basic price and volume features
            if 'close' in self.features:
                df['close'] = data['close'].pct_change().fillna(0)
            if 'open' in self.features:
                df['open'] = data['open'].pct_change().fillna(0)
            if 'high' in self.features:
                df['high'] = data['high'].pct_change().fillna(0)
            if 'low' in self.features:
                df['low'] = data['low'].pct_change().fillna(0)
            if 'volume' in self.features:
                df['volume'] = data['volume'].pct_change().fillna(0)
            
            # Technical indicators
            if 'rsi' in self.features:
                df['rsi'] = self._calculate_rsi(data['close'])
            if 'macd' in self.features:
                df['macd'] = self._calculate_macd(data['close'])
            if 'bollinger_b' in self.features:
                df['bollinger_b'] = self._calculate_bollinger_bands(data['close'])
            
            # Drop NaN values
            df.dropna(inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: Price series
            period: RSI period
            
        Returns:
            RSI values
        """
        delta = prices.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Normalize to [0, 1]
        return rsi / 100
    
    def _calculate_macd(self, prices: pd.Series) -> pd.Series:
        """
        Calculate MACD.
        
        Args:
            prices: Price series
            
        Returns:
            MACD values
        """
        short_ema = prices.ewm(span=12, adjust=False).mean()
        long_ema = prices.ewm(span=26, adjust=False).mean()
        
        macd = short_ema - long_ema
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # Normalize by standard deviation
        macd_normalized = (macd - signal) / prices.rolling(window=20).std()
        
        # Clip to handle extreme values
        return macd_normalized.clip(-3, 3) / 6 + 0.5  # Scale to [0, 1]
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> pd.Series:
        """
        Calculate Bollinger Bands %B indicator.
        
        Args:
            prices: Price series
            period: Bollinger Band period
            std_dev: Number of standard deviations
            
        Returns:
            %B values
        """
        rolling_mean = prices.rolling(window=period).mean()
        rolling_std = prices.rolling(window=period).std()
        
        upper_band = rolling_mean + (rolling_std * std_dev)
        lower_band = rolling_mean - (rolling_std * std_dev)
        
        # Calculate %B
        b_pct = (prices - lower_band) / (upper_band - lower_band)
        
        return b_pct
    
    def _process_data(self, symbol: str, data: pd.DataFrame) -> List:
        """
        Process raw data for prediction.
        
        Args:
            symbol: Symbol to process data for
            data: Raw data
            
        Returns:
            Processed data list
        """
        try:
            # Extract features
            df = self._extract_features(data)
            if df is None or len(df) == 0:
                return []
            
            return df.values.tolist()
            
        except Exception as e:
            logger.error(f"Error processing data for {symbol}: {e}")
            return []
    
    def on_data(self, data):
        """
        Process new market data.
        
        Args:
            data: Latest market data
        """
        # Process OHLCV data
        if "ohlcv" in data:
            ohlcv = data["ohlcv"]
            
            for symbol, candle in ohlcv.items():
                if symbol in self.symbols:
                    # Add new data to buffer
                    processed_candle = self._process_candle(symbol, candle)
                    if processed_candle:
                        self.data_buffer[symbol].append(processed_candle)
                        
                        # Keep buffer size limited to lookback window
                        if len(self.data_buffer[symbol]) > self.lookback_window:
                            self.data_buffer[symbol] = self.data_buffer[symbol][-self.lookback_window:]
                        
                        # Generate prediction if we have enough data
                        if len(self.data_buffer[symbol]) == self.lookback_window:
                            self._generate_prediction(symbol, candle["close"])
        
        # Check active positions for stop loss / take profit
        self._check_positions()
    
    def _process_candle(self, symbol: str, candle: Dict) -> Optional[List]:
        """
        Process a single candle for prediction.
        
        Args:
            symbol: Symbol to process candle for
            candle: Candle data
            
        Returns:
            Processed candle features
        """
        try:
            # Create a temporary DataFrame to leverage existing feature extraction
            df = pd.DataFrame([candle])
            
            # Extract features
            processed = self._extract_features(df)
            if processed is None or len(processed) == 0:
                return None
            
            return processed.iloc[0].values.tolist()
            
        except Exception as e:
            logger.error(f"Error processing candle for {symbol}: {e}")
            return None
    
    def _generate_prediction(self, symbol: str, current_price: float):
        """
        Generate price prediction for a symbol.
        
        Args:
            symbol: Symbol to generate prediction for
            current_price: Current price
        """
        if symbol not in self.models or symbol not in self.scalers:
            logger.warning(f"Model or scaler not available for {symbol}")
            return
        
        try:
            # Prepare input data
            input_data = np.array(self.data_buffer[symbol])
            
            # Scale data
            input_data = self.scalers[symbol].transform(input_data)
            
            # Reshape for LSTM [samples, time steps, features]
            input_data = input_data.reshape(1, self.lookback_window, input_data.shape[1])
            
            # Generate prediction
            prediction = self.models[symbol].predict(input_data, verbose=0)[0][0]
            
            # Convert to price change
            self.predictions[symbol] = {
                "price_change": prediction,
                "predicted_price": current_price * (1 + prediction),
                "signal": self._generate_signal(prediction),
                "timestamp": datetime.now()
            }
            
            logger.info(f"Generated prediction for {symbol}: {prediction:.6f} " +
                      f"({self.predictions[symbol]['signal']})")
            
            # Check if we should take action
            self._check_trading_signal(symbol, current_price)
            
        except Exception as e:
            logger.error(f"Error generating prediction for {symbol}: {e}")
    
    def _generate_signal(self, prediction: float) -> str:
        """
        Generate trading signal from prediction.
        
        Args:
            prediction: Price change prediction
            
        Returns:
            Signal string: 'buy', 'sell', or 'hold'
        """
        if prediction > self.signal_threshold:
            return "buy"
        elif prediction < -self.signal_threshold:
            return "sell"
        else:
            return "hold"
    
    def _check_trading_signal(self, symbol: str, current_price: float):
        """
        Check if we should act on a trading signal.
        
        Args:
            symbol: Symbol to check
            current_price: Current price
        """
        # Skip if symbol not in predictions
        if symbol not in self.predictions:
            return
        
        # Get prediction and signal
        prediction = self.predictions[symbol]
        signal = prediction["signal"]
        
        # Check if we already have a position for this symbol
        has_position = any(pos["symbol"] == symbol for pos in self.active_positions.values())
        
        # Check if we have capacity for new positions
        has_capacity = len(self.active_positions) < self.max_positions
        
        if signal == "buy" and not has_position and has_capacity:
            # Open long position
            self._open_position(symbol, "long", current_price)
            
        elif signal == "sell" and not has_position and has_capacity:
            # Open short position
            self._open_position(symbol, "short", current_price)
    
    def _open_position(self, symbol: str, direction: str, entry_price: float):
        """
        Open a new position.
        
        Args:
            symbol: Symbol to trade
            direction: 'long' or 'short'
            entry_price: Entry price
        """
        # Calculate position size
        account_balance = self.execution_handler.get_account_balance()
        position_value = account_balance * self.position_size
        quantity = position_value / entry_price
        
        # Calculate stop loss and take profit levels
        if direction == "long":
            stop_loss = entry_price * (1 - self.stop_loss_pct)
            take_profit = entry_price * (1 + self.take_profit_pct)
            order_side = "buy"
        else:  # short
            stop_loss = entry_price * (1 + self.stop_loss_pct)
            take_profit = entry_price * (1 - self.take_profit_pct)
            order_side = "sell"
        
        try:
            # Execute the order
            order = self.execution_handler.place_market_order(
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                tags={"strategy": self.name}
            )
            
            if order:
                # Store position information
                position_id = f"pos_{len(self.active_positions) + 1}"
                self.active_positions[position_id] = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "entry_time": datetime.now(),
                    "order_id": order.id
                }
                
                logger.info(f"Opened {direction} position for {symbol} at {entry_price}: "
                          f"stop_loss={stop_loss}, take_profit={take_profit}")
                
                # Update with risk manager if available
                if self.risk_manager:
                    self.risk_manager.register_position(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        quantity=quantity,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
        
        except Exception as e:
            logger.error(f"Error opening position for {symbol}: {e}")
    
    def _check_positions(self):
        """Check active positions for exit conditions."""
        for position_id, position in list(self.active_positions.items()):
            symbol = position["symbol"]
            
            try:
                # Get current price
                current_price = self.data_provider.get_last_price(symbol)
                
                if current_price is None:
                    logger.warning(f"Could not get current price for {symbol}")
                    continue
                
                # Check exit conditions
                exit_signal = False
                exit_reason = ""
                
                # Check stop loss
                if (position["direction"] == "long" and current_price <= position["stop_loss"]) or \
                   (position["direction"] == "short" and current_price >= position["stop_loss"]):
                    exit_signal = True
                    exit_reason = "stop_loss"
                
                # Check take profit
                elif (position["direction"] == "long" and current_price >= position["take_profit"]) or \
                     (position["direction"] == "short" and current_price <= position["take_profit"]):
                    exit_signal = True
                    exit_reason = "take_profit"
                
                # Check signal reversal
                elif symbol in self.predictions:
                    prediction = self.predictions[symbol]
                    signal = prediction["signal"]
                    
                    if (position["direction"] == "long" and signal == "sell") or \
                       (position["direction"] == "short" and signal == "buy"):
                        exit_signal = True
                        exit_reason = "signal_reversal"
                
                # Close position if exit signal
                if exit_signal:
                    self._close_position(position_id, position, current_price, exit_reason)
            
            except Exception as e:
                logger.error(f"Error checking position {position_id}: {e}")
    
    def _close_position(self, position_id: str, position: Dict, current_price: float, reason: str):
        """
        Close an active position.
        
        Args:
            position_id: Position ID
            position: Position details
            current_price: Current price
            reason: Reason for closing position
        """
        symbol = position["symbol"]
        quantity = position["quantity"]
        
        # Determine order side for closing
        order_side = "sell" if position["direction"] == "long" else "buy"
        
        try:
            # Execute the order
            order = self.execution_handler.place_market_order(
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                tags={"strategy": self.name, "action": "close", "reason": reason}
            )
            
            if order:
                # Calculate P&L
                if position["direction"] == "long":
                    pnl = (current_price - position["entry_price"]) * quantity
                else:  # short
                    pnl = (position["entry_price"] - current_price) * quantity
                
                pnl_pct = abs(current_price - position["entry_price"]) / position["entry_price"]
                pnl_pct = pnl_pct if pnl >= 0 else -pnl_pct
                
                logger.info(f"Closed {position['direction']} position for {symbol} at {current_price}: "
                          f"P&L=${pnl:.2f} ({pnl_pct:.2%}), reason={reason}")
                
                # Remove from active positions
                del self.active_positions[position_id]
                
                # Update with risk manager if available
                if self.risk_manager:
                    self.risk_manager.close_position(
                        symbol=symbol,
                        direction=position["direction"],
                        exit_price=current_price,
                        quantity=quantity,
                        pnl=pnl
                    )
        
        except Exception as e:
            logger.error(f"Error closing position {position_id}: {e}")
    
    def on_trade(self, trade):
        """
        Process trade notifications.
        
        Args:
            trade: Trade information
        """
        # Update position tracking
        pass
    
    def on_error(self, error):
        """
        Handle errors.
        
        Args:
            error: Error information
        """
        logger.error(f"Strategy error: {error}")
    
    def teardown(self):
        """Clean up resources and close positions."""
        logger.info("Tearing down LSTMStrategy")
        
        # Close all active positions
        for position_id, position in list(self.active_positions.items()):
            try:
                current_price = self.data_provider.get_last_price(position["symbol"])
                if current_price:
                    self._close_position(position_id, position, current_price, "strategy_teardown")
            except Exception as e:
                logger.error(f"Error closing position during teardown: {e}")
        
        logger.info("Finished teardown of LSTMStrategy") 