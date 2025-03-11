"""
Advanced Crypto Trading Strategy

A sophisticated multi-signal strategy for cryptocurrency trading that combines
multiple techniques including technical analysis, mean reversion, trend following,
and market regime detection. Features adaptive parameters, advanced risk management,
and profit optimization techniques.

The strategy:
1. Combines multiple technical indicators to create a composite signal
2. Adapts to different market regimes (trending, mean-reverting, high volatility)
3. Uses dynamic position sizing based on volatility and Kelly criterion
4. Implements adaptive stop losses and take profits
5. Periodically re-evaluates and adjusts its parameters based on performance

Tags: [hybrid, adaptive, multi_signal, multi_timeframe, technical]
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional, Union
import logging
from datetime import datetime, timedelta

from ..base import BaseStrategy

# Set up logging
logger = logging.getLogger(__name__)


class AdvancedCryptoStrategy(BaseStrategy):
    """
    Advanced cryptocurrency trading strategy combining multiple approaches.
    
    Args:
        symbols: List of symbols to trade
        max_position_size: Maximum position size as percentage of portfolio
        min_position_size: Minimum position size as percentage of portfolio
        diversification_target: Target number of positions for diversification
        max_drawdown_limit: Maximum portfolio drawdown before reducing risk
        base_risk_per_trade: Base risk per trade as percentage of portfolio
        volatility_target: Target portfolio volatility
        kelly_fraction: Fraction of Kelly criterion to use (0.0-1.0)
        base_stop_loss: Base stop loss percentage
        dynamic_stop_loss: Whether to use dynamic/adaptive stop losses
        atr_stop_multiplier: ATR multiplier for stop loss calculation
        short_window: Short-term moving average window
        long_window: Long-term moving average window
        mr_window: Mean reversion lookback window
        volatility_window: ATR calculation window
    """
    
    # Required data for this strategy
    REQUIRED_DATA = ["ohlcv", "exchange_info"]
    
    def __init__(self, 
                 symbols: List[str],
                 max_position_size: float = 0.25,
                 min_position_size: float = 0.02,
                 diversification_target: int = 4,
                 max_drawdown_limit: float = 0.15,
                 base_risk_per_trade: float = 0.02,
                 volatility_target: float = 0.20,
                 kelly_fraction: float = 0.5,
                 base_stop_loss: float = 0.05,
                 dynamic_stop_loss: bool = True,
                 atr_stop_multiplier: float = 2.0,
                 short_window: int = 20,
                 long_window: int = 50,
                 mr_window: int = 30,
                 volatility_window: int = 14,
                 **kwargs):
        """Initialize the strategy with parameters."""
        super().__init__(symbols=symbols, **kwargs)
        
        # Portfolio allocation parameters
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size
        self.diversification_target = diversification_target
        
        # Risk management parameters
        self.max_drawdown_limit = max_drawdown_limit
        self.base_risk_per_trade = base_risk_per_trade
        self.current_risk_per_trade = base_risk_per_trade
        self.volatility_target = volatility_target
        self.kelly_fraction = kelly_fraction
        self.base_stop_loss = base_stop_loss
        self.dynamic_stop_loss = dynamic_stop_loss
        self.atr_stop_multiplier = atr_stop_multiplier
        
        # Signal generation parameters
        self.short_window = short_window
        self.long_window = long_window
        self.mr_window = mr_window
        self.volatility_window = volatility_window
        
        # Performance tracking
        self.portfolio_values = []
        self.highest_value = 0.0
        
        # Signal and indicator storage
        self.signal_values = {sym: {} for sym in symbols}
        self.indicators = {sym: {} for sym in symbols}
        self.regime_state = {sym: "unknown" for sym in symbols}
        
        # Position management
        self.current_volatility = {}
        self.stop_losses = {}
        self.take_profits = {}
        self._active_positions = {}
        self._closed_positions = []
        
        logger.info("Advanced Crypto Strategy initialized")
    
    def calculate_indicators(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """
        Calculate technical indicators for a symbol.
        
        Args:
            data: DataFrame with OHLCV data
            symbol: Trading symbol
            
        Returns:
            Dictionary of calculated indicators
        """
        if len(data) < max(self.long_window, self.mr_window) + 10:
            return {}
            
        indicators = {}
        
        # Extract price data
        indicators['price'] = data['close'].copy()
        indicators['open'] = data['open'].copy()
        indicators['high'] = data['high'].copy()
        indicators['low'] = data['low'].copy()
        indicators['close'] = data['close'].copy()
        indicators['volume'] = data['volume'].copy()
        
        # Calculate returns
        indicators['returns'] = data['close'].pct_change()
        
        # Calculate trend indicators
        indicators['sma_short'] = data['close'].rolling(window=self.short_window).mean()
        indicators['sma_long'] = data['close'].rolling(window=self.long_window).mean()
        indicators['ema_short'] = data['close'].ewm(span=self.short_window, adjust=False).mean()
        indicators['ema_long'] = data['close'].ewm(span=self.long_window, adjust=False).mean()
        
        # Calculate mean reversion indicators
        rolling_mean = data['close'].rolling(window=self.mr_window).mean()
        rolling_std = data['close'].rolling(window=self.mr_window).std()
        indicators['z_score'] = (data['close'] - rolling_mean) / rolling_std
        
        # Calculate Bollinger Bands
        indicators['bb_mid'] = rolling_mean
        indicators['bb_upper'] = rolling_mean + 2 * rolling_std
        indicators['bb_lower'] = rolling_mean - 2 * rolling_std
        
        # Calculate volatility indicators (ATR)
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        indicators['atr'] = true_range.rolling(window=self.volatility_window).mean()
        
        # Calculate RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs))
        
        # Calculate MACD
        ema12 = data['close'].ewm(span=12, adjust=False).mean()
        ema26 = data['close'].ewm(span=26, adjust=False).mean()
        indicators['macd'] = ema12 - ema26
        indicators['macd_signal'] = indicators['macd'].ewm(span=9, adjust=False).mean()
        indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
        
        # Calculate current volatility
        self.current_volatility[symbol] = indicators['returns'].rolling(window=21).std() * np.sqrt(252)  # Annualized
        
        # Detect market regime
        returns = indicators['returns'].dropna().iloc[-50:]
        indicators['regime'] = self._detect_regime(returns)
        self.regime_state[symbol] = indicators['regime']
        
        # Store indicators
        self.indicators[symbol] = indicators
        
        return indicators
    
    def _detect_regime(self, returns: pd.Series) -> str:
        """
        Detect the current market regime based on return patterns.
        
        Args:
            returns: Series of price returns
            
        Returns:
            String indicating the market regime
        """
        if len(returns) < 20:
            return "unknown"
            
        # Calculate autocorrelation
        autocorr = returns.autocorr(lag=1)
        
        # Calculate volatility
        volatility = returns.std() * np.sqrt(252)  # Annualized
        
        # Calculate directional strength
        cumulative_return = (1 + returns).prod() - 1
        abs_returns = returns.abs().sum()
        directional_strength = abs(cumulative_return) / abs_returns if abs_returns > 0 else 0
        
        # Determine regime
        if volatility > 0.8:  # High volatility regime
            return "volatile"
        elif autocorr < -0.1:  # Mean reverting regime
            return "mean_reverting"
        elif autocorr > 0.1 and directional_strength > 0.1:  # Trending regime
            return "trending"
        else:
            return "ranging"  # Default/ranging regime
    
    def generate_signal(self, data: pd.DataFrame, symbol: str) -> Tuple[int, Dict]:
        """
        Generate trading signals based on indicators and market regime.
        
        Args:
            data: DataFrame with market data
            symbol: Trading symbol
            
        Returns:
            Tuple with signal direction (-1, 0, 1) and signal details
        """
        if len(data) < max(self.long_window, self.mr_window) + 10:
            return 0, {'reason': 'Insufficient data'}
            
        # Calculate indicators
        indicators = self.calculate_indicators(data, symbol)
        
        if not indicators:
            return 0, {'reason': 'Failed to calculate indicators'}
        
        # Current price and regime
        current_price = data.iloc[-1]['close']
        regime = self.regime_state[symbol]
        
        # Initialize signals dictionary for component signals
        signals = {}
        
        # Trend signals
        signals['trend'] = 0
        if indicators['sma_short'].iloc[-1] > indicators['sma_long'].iloc[-1]:
            # Uptrend
            if indicators['close'].iloc[-1] > indicators['sma_short'].iloc[-1]:
                signals['trend'] = 1  # Strong uptrend
            else:
                signals['trend'] = 0.5  # Moderate uptrend
        elif indicators['sma_short'].iloc[-1] < indicators['sma_long'].iloc[-1]:
            # Downtrend
            if indicators['close'].iloc[-1] < indicators['sma_short'].iloc[-1]:
                signals['trend'] = -1  # Strong downtrend
            else:
                signals['trend'] = -0.5  # Moderate downtrend
        
        # Mean reversion signals
        signals['mean_reversion'] = 0
        z_score = indicators['z_score'].iloc[-1]
        if z_score < -2.0:
            signals['mean_reversion'] = 1  # Oversold
        elif z_score > 2.0:
            signals['mean_reversion'] = -1  # Overbought
        
        # Bollinger Band signals
        signals['bbands'] = 0
        if current_price < indicators['bb_lower'].iloc[-1]:
            signals['bbands'] = 1  # Below lower band
        elif current_price > indicators['bb_upper'].iloc[-1]:
            signals['bbands'] = -1  # Above upper band
        
        # RSI signals
        signals['rsi'] = 0
        rsi = indicators['rsi'].iloc[-1]
        if not np.isnan(rsi):
            if rsi < 30:
                signals['rsi'] = 1  # Oversold
            elif rsi > 70:
                signals['rsi'] = -1  # Overbought
        
        # MACD signals
        signals['macd'] = 0
        if not np.isnan(indicators['macd'].iloc[-1]) and not np.isnan(indicators['macd_signal'].iloc[-1]):
            if (indicators['macd'].iloc[-2] < indicators['macd_signal'].iloc[-2] and 
                indicators['macd'].iloc[-1] > indicators['macd_signal'].iloc[-1]):
                signals['macd'] = 1  # Bullish crossover
            elif (indicators['macd'].iloc[-2] > indicators['macd_signal'].iloc[-2] and 
                  indicators['macd'].iloc[-1] < indicators['macd_signal'].iloc[-1]):
                signals['macd'] = -1  # Bearish crossover
        
        # Combine signals based on current regime
        composite_signal = 0
        
        if regime == "trending":
            # In trending markets, emphasize trend signals and MACD
            weights = {
                'trend': 0.5,
                'mean_reversion': 0.1,
                'bbands': 0.1,
                'rsi': 0.1,
                'macd': 0.2
            }
        elif regime == "mean_reverting":
            # In mean-reverting markets, emphasize mean reversion signals
            weights = {
                'trend': 0.1,
                'mean_reversion': 0.4,
                'bbands': 0.3,
                'rsi': 0.15,
                'macd': 0.05
            }
        elif regime == "volatile":
            # In volatile markets, be more conservative
            weights = {
                'trend': 0.2,
                'mean_reversion': 0.2,
                'bbands': 0.3,
                'rsi': 0.2,
                'macd': 0.1
            }
        else:  # ranging or unknown
            # Balanced approach
            weights = {
                'trend': 0.25,
                'mean_reversion': 0.25,
                'bbands': 0.2,
                'rsi': 0.15,
                'macd': 0.15
            }
        
        # Calculate weighted signal
        for signal_type, value in signals.items():
            if signal_type in weights:
                composite_signal += value * weights[signal_type]
        
        # Determine final signal
        final_signal = 0
        signal_strength = abs(composite_signal)
        
        if composite_signal > 0.3:
            final_signal = 1
        elif composite_signal < -0.3:
            final_signal = -1
        
        # Signal details
        signal_details = {
            'timestamp': data.index[-1],
            'price': current_price,
            'regime': regime,
            'composite_signal': composite_signal,
            'signal_strength': signal_strength,
            'component_signals': signals,
            'indicators': {
                'sma_short': indicators['sma_short'].iloc[-1],
                'sma_long': indicators['sma_long'].iloc[-1],
                'z_score': indicators['z_score'].iloc[-1],
                'atr': indicators['atr'].iloc[-1],
                'rsi': indicators['rsi'].iloc[-1],
                'macd': indicators['macd'].iloc[-1],
                'volatility': self.current_volatility.get(symbol, 0)
            }
        }
        
        # Calculate stop loss and take profit levels
        if final_signal != 0:
            atr = indicators['atr'].iloc[-1]
            
            if self.dynamic_stop_loss and not np.isnan(atr):
                stop_distance = self.atr_stop_multiplier * atr
                stop_pct = stop_distance / current_price
            else:
                stop_pct = self.base_stop_loss
            
            # Different position sizing based on regime
            if regime == "volatile":
                # More conservative in volatile markets
                take_profit_pct = stop_pct * 1.5
            elif regime == "trending":
                # More generous in trending markets
                take_profit_pct = stop_pct * 2.5
            else:
                # Default
                take_profit_pct = stop_pct * 2.0
            
            if final_signal > 0:
                signal_details['stop_price'] = current_price * (1 - stop_pct)
                signal_details['target_price'] = current_price * (1 + take_profit_pct)
            else:
                signal_details['stop_price'] = current_price * (1 + stop_pct)
                signal_details['target_price'] = current_price * (1 - take_profit_pct)
        
        # Store signal values
        self.signal_values[symbol] = signal_details
        
        return final_signal, signal_details
    
    def calculate_position_size(self, signal_details: Dict[str, Any], 
                               capital: float, symbol: str) -> float:
        """
        Calculate optimal position size based on signal strength, volatility, and risk parameters.
        
        Args:
            signal_details: Dictionary with signal details
            capital: Available capital
            symbol: Trading symbol
            
        Returns:
            Position size as a fraction of capital
        """
        # Base position size based on diversification target
        base_position_size = 1.0 / self.diversification_target
        
        # Get volatility and signal strength
        volatility = self.current_volatility.get(symbol, 0.5)
        signal_strength = signal_details.get('signal_strength', 0.5)
        regime = signal_details.get('regime', 'unknown')
        
        # Calculate Kelly fraction
        # f* = (bp - q) / b
        # where:
        # b = profit on winning trades (ratio)
        # p = win probability
        # q = 1-p (loss probability)
        
        # Estimate win probability based on signal strength
        win_prob = 0.5 + (0.2 * signal_strength)
        
        # Estimate profit ratio based on target and stop
        if 'target_price' in signal_details and 'stop_price' in signal_details and 'price' in signal_details:
            price = signal_details['price']
            direction = 1 if signal_details.get('composite_signal', 0) > 0 else -1
            
            if direction > 0:
                profit_ratio = (signal_details['target_price'] - price) / (price - signal_details['stop_price'])
            else:
                profit_ratio = (price - signal_details['target_price']) / (signal_details['stop_price'] - price)
                
            # Safety check
            profit_ratio = max(0.5, min(profit_ratio, 5.0))
        else:
            profit_ratio = 2.0  # Default
        
        # Kelly calculation
        loss_prob = 1 - win_prob
        kelly = (win_prob * profit_ratio - loss_prob) / profit_ratio
        
        # Apply kelly fraction for safety
        kelly = max(0, kelly) * self.kelly_fraction
        
        # Adjust for volatility
        vol_adjustment = self.volatility_target / max(volatility, 0.1)
        vol_adjustment = max(0.5, min(vol_adjustment, 2.0))  # Limit adjustment range
        
        # Regime-based adjustments
        regime_factor = 1.0
        if regime == "volatile":
            regime_factor = 0.7  # Reduce size in volatile regimes
        elif regime == "trending" and signal_strength > 0.6:
            regime_factor = 1.2  # Increase size in strong trending regimes
            
        # Final position size
        position_size = base_position_size * kelly * vol_adjustment * regime_factor
        
        # Apply position limits
        position_size = max(self.min_position_size, min(position_size, self.max_position_size))
        
        return position_size
    
    def execute_trades(self, data_dict: Dict[str, pd.DataFrame], 
                      capital: float) -> List[Dict]:
        """
        Execute trades based on signals across all symbols.
        
        Args:
            data_dict: Dictionary of DataFrames with market data for each symbol
            capital: Available capital
            
        Returns:
            List of executed trade dictionaries
        """
        executed_trades = []
        current_time = datetime.now()
        
        # Update active positions
        for symbol, position in list(self._active_positions.items()):
            if symbol not in data_dict:
                continue
                
            data = data_dict[symbol]
            if len(data) == 0:
                continue
                
            current_price = data.iloc[-1]['close']
            
            # Update position status
            if position['direction'] == 'buy':
                pnl_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            else:  # sell
                pnl_pct = (position['entry_price'] - current_price) / position['entry_price'] * 100
                
            position['current_price'] = current_price
            position['current_pnl_pct'] = pnl_pct
            position['holding_periods'] += 1
            
            # Check for exit conditions
            exit_reason = None
            
            # Take profit
            if position['direction'] == 'buy' and current_price >= position['target_price']:
                exit_reason = 'take_profit'
            elif position['direction'] == 'sell' and current_price <= position['target_price']:
                exit_reason = 'take_profit'
                
            # Stop loss
            if position['direction'] == 'buy' and current_price <= position['stop_price']:
                exit_reason = 'stop_loss'
            elif position['direction'] == 'sell' and current_price >= position['stop_price']:
                exit_reason = 'stop_loss'
                
            # Dynamic exit based on regime change
            if 'regime' in position and position['regime'] != self.regime_state.get(symbol, 'unknown'):
                if (position['direction'] == 'buy' and self.regime_state.get(symbol) == 'volatile' and pnl_pct > 0) or \
                   (position['direction'] == 'sell' and self.regime_state.get(symbol) == 'volatile' and pnl_pct > 0):
                    exit_reason = 'regime_change'
            
            # Exit position if conditions met
            if exit_reason:
                position['exit_price'] = current_price
                position['exit_time'] = current_time
                position['exit_reason'] = exit_reason
                position['final_pnl_pct'] = pnl_pct
                position['final_pnl_value'] = position['position_value'] * pnl_pct / 100
                
                # Add to closed positions
                self._closed_positions.append(position)
                
                # Remove from active positions
                del self._active_positions[symbol]
                
                # Record the executed exit trade
                executed_trades.append({
                    'symbol': symbol,
                    'timestamp': current_time,
                    'action': 'exit',
                    'direction': 'sell' if position['direction'] == 'buy' else 'buy',
                    'price': current_price,
                    'quantity': position['quantity'],
                    'value': position['position_value'],
                    'reason': exit_reason,
                    'pnl_pct': pnl_pct,
                    'pnl_value': position['position_value'] * pnl_pct / 100
                })
                
                logger.info(f"Exited {position['direction']} position in {symbol} for {exit_reason} with PnL: {pnl_pct:.2f}%")
        
        # Generate new signals
        for symbol in self.symbols:
            if symbol not in data_dict:
                continue
                
            data = data_dict[symbol]
            if len(data) < max(self.long_window, self.mr_window) + 10:
                continue
                
            # Skip if already in position
            if symbol in self._active_positions:
                continue
                
            # Generate signal
            signal, signal_details = self.generate_signal(data, symbol)
            
            if signal != 0:
                # Calculate position size
                position_size_pct = self.calculate_position_size(signal_details, capital, symbol)
                position_value = capital * position_size_pct
                
                # Get current price
                current_price = data.iloc[-1]['close']
                
                # Calculate quantity
                quantity = position_value / current_price
                
                # Create new position
                direction = 'buy' if signal > 0 else 'sell'
                position = {
                    'symbol': symbol,
                    'entry_time': current_time,
                    'direction': direction,
                    'entry_price': current_price,
                    'quantity': quantity,
                    'position_value': position_value,
                    'target_price': signal_details.get('target_price'),
                    'stop_price': signal_details.get('stop_price'),
                    'regime': self.regime_state.get(symbol, 'unknown'),
                    'signal_strength': signal_details.get('signal_strength', 0.5),
                    'current_price': current_price,
                    'current_pnl_pct': 0.0,
                    'holding_periods': 0
                }
                
                # Add to active positions
                self._active_positions[symbol] = position
                
                # Record the executed entry trade
                executed_trades.append({
                    'symbol': symbol,
                    'timestamp': current_time,
                    'action': 'entry',
                    'direction': direction,
                    'price': current_price,
                    'quantity': quantity,
                    'value': position_value,
                    'reason': f"signal_{direction}",
                    'signal_strength': signal_details.get('signal_strength', 0.5),
                    'regime': self.regime_state.get(symbol, 'unknown'),
                    'target_price': signal_details.get('target_price'),
                    'stop_price': signal_details.get('stop_price')
                })
                
                logger.info(f"Entered {direction} position in {symbol} at {current_price} with "
                           f"size: {position_size_pct:.2%} of portfolio")
        
        # Track portfolio value for drawdown calculations
        portfolio_value = capital
        for position in self._active_positions.values():
            portfolio_value += position.get('position_value', 0) * position.get('current_pnl_pct', 0) / 100
            
        self.portfolio_values.append((current_time, portfolio_value))
        self.highest_value = max(self.highest_value, portfolio_value)
        
        # Check for excessive drawdown
        if self.highest_value > 0:
            current_drawdown = (self.highest_value - portfolio_value) / self.highest_value
            
            if current_drawdown > self.max_drawdown_limit:
                logger.warning(f"Excessive drawdown detected: {current_drawdown:.2%}. "
                              f"Reducing risk per trade from {self.current_risk_per_trade:.2%} "
                              f"to {self.current_risk_per_trade * 0.75:.2%}")
                self.current_risk_per_trade *= 0.75
        
        return executed_trades
    
    def analyze_performance(self, trades: List[Dict]) -> Dict:
        """
        Analyze performance of executed trades.
        
        Args:
            trades: List of executed trade dictionaries
            
        Returns:
            Dictionary with performance metrics
        """
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'average_profit_pct': 0,
                'max_drawdown_pct': 0
            }
        
        # Extract closed trades (pairs of entry and exit)
        entry_trades = [t for t in trades if t['action'] == 'entry']
        exit_trades = [t for t in trades if t['action'] == 'exit']
        
        # Match entries with exits
        closed_trades = []
        
        for entry in entry_trades:
            # Find matching exit
            matching_exits = [
                e for e in exit_trades if (
                    e['symbol'] == entry['symbol'] and
                    e['quantity'] == entry['quantity'] and
                    e['timestamp'] > entry['timestamp']
                )
            ]
            
            if matching_exits:
                # Use the first matching exit
                exit_trade = matching_exits[0]
                
                # Calculate P&L
                if entry['direction'] == 'buy':
                    pnl_pct = (exit_trade['price'] - entry['price']) / entry['price'] * 100
                else:  # sell
                    pnl_pct = (entry['price'] - exit_trade['price']) / entry['price'] * 100
                
                pnl_value = entry['value'] * pnl_pct / 100
                
                closed_trades.append({
                    'symbol': entry['symbol'],
                    'entry_time': entry['timestamp'],
                    'exit_time': exit_trade['timestamp'],
                    'direction': entry['direction'],
                    'entry_price': entry['price'],
                    'exit_price': exit_trade['price'],
                    'quantity': entry['quantity'],
                    'value': entry['value'],
                    'pnl_pct': pnl_pct,
                    'pnl_value': pnl_value,
                    'exit_reason': exit_trade['reason'],
                    'regime': entry.get('regime', 'unknown')
                })
        
        # Calculate performance metrics
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t['pnl_value'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl_value'] <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t['pnl_value'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl_value'] for t in losing_trades))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        average_profit_pct = sum(t['pnl_pct'] for t in closed_trades) / total_trades if total_trades > 0 else 0
        
        # Calculate drawdown
        equity_curve = []
        cumulative_pnl = 0
        
        for trade in sorted(closed_trades, key=lambda t: t['exit_time']):
            cumulative_pnl += trade['pnl_value']
            equity_curve.append(cumulative_pnl)
        
        # Maximum drawdown calculation
        max_drawdown_pct = 0
        peak = 0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            elif peak > 0:
                drawdown = (peak - equity) / peak * 100
                max_drawdown_pct = max(max_drawdown_pct, drawdown)
        
        # Performance by market regime
        performance_by_regime = {}
        
        for trade in closed_trades:
            regime = trade.get('regime', 'unknown')
            
            if regime not in performance_by_regime:
                performance_by_regime[regime] = {
                    'count': 0,
                    'win_count': 0,
                    'total_pnl': 0,
                    'avg_pnl_pct': 0
                }
            
            perf = performance_by_regime[regime]
            perf['count'] += 1
            
            if trade['pnl_value'] > 0:
                perf['win_count'] += 1
                
            perf['total_pnl'] += trade['pnl_value']
            
        # Calculate averages
        for regime, perf in performance_by_regime.items():
            if perf['count'] > 0:
                perf['win_rate'] = perf['win_count'] / perf['count']
                perf['avg_pnl_pct'] = perf['total_pnl'] / perf['count']
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'average_profit_pct': average_profit_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'net_profit': gross_profit - gross_loss,
            'performance_by_regime': performance_by_regime
        } 