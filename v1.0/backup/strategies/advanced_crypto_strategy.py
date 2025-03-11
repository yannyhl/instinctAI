"""
Advanced Crypto Trading Strategy
-------------------------------
A sophisticated multi-signal strategy for cryptocurrency trading with adaptive parameters,
advanced risk management, and profit optimization techniques.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import logging
from pathlib import Path
import time
from datetime import datetime, timedelta

# Zipline imports
from zipline.api import (
    order, order_target_percent, record, symbol, get_datetime,
    schedule_function, date_rules, time_rules, get_open_orders,
    cancel_order, set_slippage, set_commission, slippage, commission,
    set_benchmark, get_order, get_positions
)
from zipline.finance import commission, slippage
from zipline.utils.events import date_rules, time_rules
from zipline.errors import SymbolNotFound

# Import custom modules
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from utils.risk_management import calculate_position_size, calculate_kelly_fraction
from utils.technical_indicators import calculate_zscore, detect_regime, calculate_market_fear
from utils.signal_processing import generate_ensemble_signal, normalize_signals

# Set up logging
logger = logging.getLogger(__name__)

class AdvancedCryptoStrategy:
    """
    Advanced cryptocurrency trading strategy combining:
    1. Multiple technical indicators
    2. Mean reversion signals
    3. Trend following signals
    4. Volatility-based position sizing
    5. Dynamic stop losses and take profits
    6. Regime detection for strategy adaptation
    """
    
    def __init__(self, context):
        """
        Initialize the strategy
        
        Args:
            context: Zipline context object
        """
        self.context = context
        self.initialized = False
        self.symbols = ["BTC"]  # Default to BTC
        
        # Configure from settings
        self._load_config()
        
        # Performance tracking
        self.portfolio_values = []
        self.positions = {}
        self.trades = []
        
        # Signal values
        self.signal_values = {sym: {} for sym in self.symbols}
        self.indicators = {sym: {} for sym in self.symbols}
        self.regime_state = {sym: "unknown" for sym in self.symbols}
        
        # Risk management
        self.current_risk_per_trade = self.base_risk_per_trade
        self.current_volatility = {}
        self.stop_losses = {}
        self.take_profits = {}
        
        logger.info("Advanced Crypto Strategy initialized")
    
    def _load_config(self):
        """Load strategy configuration from config file"""
        # Portfolio allocation parameters
        portfolio_config = config.STRATEGY_CONFIG["portfolio_allocation"]
        self.max_position_size = portfolio_config["max_position_size"]
        self.min_position_size = portfolio_config["min_position_size"]
        self.diversification_target = portfolio_config["diversification_target"]
        
        # Risk management parameters
        risk_config = config.STRATEGY_CONFIG["risk_management"]
        self.max_drawdown_limit = risk_config["max_drawdown_limit"]
        self.base_risk_per_trade = risk_config["position_risk_limit"]
        self.volatility_target = risk_config["portfolio_volatility_target"]
        self.kelly_fraction = risk_config["kelly_fraction"]
        self.base_stop_loss = risk_config["stop_loss"]
        self.dynamic_stop_loss = risk_config["dynamic_stop_loss"]
        self.atr_stop_multiplier = risk_config["atr_stop_multiplier"]
        
        # Signal generation parameters
        self.trend_config = config.STRATEGY_CONFIG["signals"]["trend"]
        self.mean_reversion_config = config.STRATEGY_CONFIG["signals"]["mean_reversion"]
        self.volatility_config = config.STRATEGY_CONFIG["signals"]["volatility"]
        self.on_chain_config = config.STRATEGY_CONFIG["signals"]["on_chain"]
        
        # Machine learning parameters
        self.ml_config = config.STRATEGY_CONFIG["ml_models"]
    
    def initialize(self, context):
        """
        Initialize the strategy in the Zipline context
        
        Args:
            context: Zipline context object
        """
        # Set benchmark to BTC
        set_benchmark(symbol('BTC'))
        
        # Set commission and slippage models
        set_commission(commission.PerShare(cost=0.001, min_trade_cost=0.001))
        set_slippage(slippage.VolumeShareSlippage(volume_limit=0.025, price_impact=0.1))
        
        # Initialize parameters
        context.symbols = [symbol(sym) for sym in self.symbols]
        context.base_pct_per_position = 1.0 / self.diversification_target
        
        # Set lookback windows for different indicators
        context.short_window = self.trend_config["short_window"]
        context.long_window = self.trend_config["long_window"]
        context.mr_window = self.mean_reversion_config["lookback_period"]
        context.volatility_window = self.volatility_config["atr_period"]
        
        # Schedule rebalance functions
        # Main strategy execution
        schedule_function(
            self.rebalance,
            date_rules.every_day(),
            time_rules.market_open(hours=1)  # 1 hour after market open
        )
        
        # End of day position check/adjustments
        schedule_function(
            self.check_positions,
            date_rules.every_day(),
            time_rules.market_close(minutes=30)  # 30 minutes before close
        )
        
        # Daily risk adjustment based on performance
        schedule_function(
            self.adjust_risk_parameters,
            date_rules.every_day(),
            time_rules.market_open(minutes=15)  # 15 minutes after open
        )
        
        # Weekly strategy performance evaluation and adaptation
        schedule_function(
            self.adapt_strategy,
            date_rules.week_start(),
            time_rules.market_open(hours=1)  # 1 hour after Monday open
        )
        
        # Flag as initialized
        self.initialized = True
        logger.info("Strategy initialization in Zipline complete")
    
    def before_trading_start(self, context, data):
        """
        Called before the start of each trading day.
        Updates indicators and signals.
        
        Args:
            context: Zipline context
            data: Zipline data object
        """
        if not self.initialized:
            return
        
        try:
            # Update portfolio values for tracking
            current_value = context.portfolio.portfolio_value
            self.portfolio_values.append((get_datetime(), current_value))
            
            # Calculate indicators for each trading symbol
            for sym in context.symbols:
                # Get historical price data
                hist = data.history(
                    sym, 
                    fields=['price', 'open', 'high', 'low', 'close', 'volume'],
                    bar_count=max(context.long_window, context.mr_window) + 50,  # Extra buffer
                    frequency='1d'
                )
                
                if len(hist) < max(context.long_window, context.mr_window):
                    logger.warning(f"Not enough data for {sym} - got {len(hist)} bars")
                    continue
                
                # Store raw price data
                self.indicators[sym.symbol]['price'] = hist['price']
                self.indicators[sym.symbol]['close'] = hist['close']
                self.indicators[sym.symbol]['open'] = hist['open']
                self.indicators[sym.symbol]['high'] = hist['high']
                self.indicators[sym.symbol]['low'] = hist['low']
                self.indicators[sym.symbol]['volume'] = hist['volume']
                
                # Calculate returns
                self.indicators[sym.symbol]['returns'] = hist['close'].pct_change()
                
                # Calculate trend indicators
                self.indicators[sym.symbol]['sma_short'] = hist['close'].rolling(
                    window=context.short_window).mean()
                self.indicators[sym.symbol]['sma_long'] = hist['close'].rolling(
                    window=context.long_window).mean()
                
                # Calculate mean reversion indicators
                rolling_mean = hist['close'].rolling(window=context.mr_window).mean()
                rolling_std = hist['close'].rolling(window=context.mr_window).std()
                self.indicators[sym.symbol]['z_score'] = (hist['close'] - rolling_mean) / rolling_std
                
                # Calculate volatility indicators
                high_low = hist['high'] - hist['low']
                high_close = np.abs(hist['high'] - hist['close'].shift())
                low_close = np.abs(hist['low'] - hist['close'].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = np.max(ranges, axis=1)
                self.indicators[sym.symbol]['atr'] = true_range.rolling(
                    window=context.volatility_window).mean()
                
                # Calculate Bollinger Bands
                self.indicators[sym.symbol]['bb_mid'] = rolling_mean
                self.indicators[sym.symbol]['bb_upper'] = rolling_mean + 2 * rolling_std
                self.indicators[sym.symbol]['bb_lower'] = rolling_mean - 2 * rolling_std
                
                # Calculate volatility
                self.current_volatility[sym.symbol] = self.indicators[sym.symbol]['returns'].rolling(
                    window=21).std() * np.sqrt(252)  # Annualized
                
                # Detect market regime
                returns = self.indicators[sym.symbol]['returns'].dropna()
                self.regime_state[sym.symbol] = detect_regime(returns.values)
                
                # Generate trading signals
                self._generate_signals(sym)
                
                logger.info(f"Updated indicators and signals for {sym.symbol}")
        
        except Exception as e:
            logger.error(f"Error in before_trading_start: {str(e)}")
    
    def _generate_signals(self, sym):
        """
        Generate trading signals for a symbol
        
        Args:
            sym: Trading symbol
        """
        symbol_str = sym.symbol
        indicators = self.indicators[symbol_str]
        
        # Skip if missing data
        required_fields = ['close', 'sma_short', 'sma_long', 'z_score', 'atr']
        if any(field not in indicators or indicators[field].empty for field in required_fields):
            logger.warning(f"Missing required indicator data for {symbol_str}")
            return
        
        current_price = indicators['close'].iloc[-1]
        
        # 1. Trend following signal (-1 to 1)
        if indicators['sma_short'].iloc[-1] > indicators['sma_long'].iloc[-1]:
            # Uptrend strength based on distance between MAs
            trend_signal = min(1.0, (indicators['sma_short'].iloc[-1] / indicators['sma_long'].iloc[-1] - 1) * 10)
        else:
            # Downtrend strength
            trend_signal = max(-1.0, (indicators['sma_short'].iloc[-1] / indicators['sma_long'].iloc[-1] - 1) * 10)
        
        # 2. Mean reversion signal (-1 to 1)
        z_score = indicators['z_score'].iloc[-1]
        if np.isnan(z_score):
            mean_rev_signal = 0
        else:
            # More extreme z-scores give stronger signals in the opposite direction
            mean_rev_signal = -np.clip(z_score / self.mean_reversion_config["z_score_threshold"], -1.0, 1.0)
        
        # 3. Volatility signal (0 to 1)
        # Higher ATR relative to price = higher volatility = lower position size
        if current_price > 0 and not np.isnan(indicators['atr'].iloc[-1]):
            volatility_ratio = indicators['atr'].iloc[-1] / current_price
            volatility_signal = 1.0 - np.clip(volatility_ratio * 100, 0, 1)
        else:
            volatility_signal = 0.5  # Neutral
        
        # 4. Momentum signal (-1 to 1)
        returns = indicators['returns'].dropna()
        if len(returns) > 14:
            momentum_signal = np.tanh(returns[-14:].mean() * 100)  # Scale and bound to [-1, 1]
        else:
            momentum_signal = 0  # Neutral
        
        # 5. Bollinger Band signal (-1 to 1)
        if current_price <= indicators['bb_lower'].iloc[-1]:
            bb_signal = 1.0  # Oversold - buy signal
        elif current_price >= indicators['bb_upper'].iloc[-1]:
            bb_signal = -1.0  # Overbought - sell signal
        else:
            # Proportional distance between bands
            bb_range = indicators['bb_upper'].iloc[-1] - indicators['bb_lower'].iloc[-1]
            if bb_range > 0:
                bb_position = (current_price - indicators['bb_lower'].iloc[-1]) / bb_range
                bb_signal = 1.0 - 2.0 * bb_position  # Map from 0-1 to 1 to -1
            else:
                bb_signal = 0
        
        # Store all raw signals
        self.signal_values[symbol_str] = {
            'trend': trend_signal,
            'mean_reversion': mean_rev_signal,
            'volatility': volatility_signal,
            'momentum': momentum_signal,
            'bollinger': bb_signal,
        }
        
        # Combine signals based on regime
        regime = self.regime_state[symbol_str]
        
        if regime == "trending":
            # In trending regime, prefer trend and momentum signals
            weights = {
                'trend': 0.40,
                'momentum': 0.30,
                'mean_reversion': 0.0,
                'bollinger': 0.15,
                'volatility': 0.15
            }
        elif regime == "mean_reverting":
            # In mean-reverting regime, prefer mean reversion signals
            weights = {
                'trend': 0.0,
                'momentum': 0.10,
                'mean_reversion': 0.50,
                'bollinger': 0.30,
                'volatility': 0.10
            }
        elif regime == "high_volatility":
            # In high volatility, be more conservative
            weights = {
                'trend': 0.15,
                'momentum': 0.15,
                'mean_reversion': 0.15,
                'bollinger': 0.15,
                'volatility': 0.40  # Higher weight to volatility
            }
        else:
            # Balanced/unknown regime
            weights = {
                'trend': 0.25,
                'momentum': 0.25,
                'mean_reversion': 0.25,
                'bollinger': 0.15,
                'volatility': 0.10
            }
        
        # Calculate ensemble signal
        signals = self.signal_values[symbol_str]
        ensemble_value = sum(signals[k] * weights[k] for k in weights)
        
        # Store the final signal (-1 to 1 range)
        self.signal_values[symbol_str]['ensemble'] = np.clip(ensemble_value, -1.0, 1.0)
        
        # Calculate implied position size
        # Map signal from [-1, 1] to [-max_position_size, max_position_size]
        self.signal_values[symbol_str]['position_pct'] = self.signal_values[symbol_str]['ensemble'] * self.max_position_size
    
    def rebalance(self, context, data):
        """
        Main rebalancing logic to execute trades based on signals
        
        Args:
            context: Zipline context
            data: Zipline data object
        """
        if not self.initialized:
            return
        
        try:
            # Check if we're in a drawdown exceeding our limit
            if self._check_excessive_drawdown(context):
                logger.warning("Excessive drawdown detected - reducing risk")
                self._reduce_risk(context, data)
                return
            
            for sym in context.symbols:
                symbol_str = sym.symbol
                
                # Skip if we don't have signals
                if symbol_str not in self.signal_values or 'position_pct' not in self.signal_values[symbol_str]:
                    logger.warning(f"No signal available for {symbol_str}")
                    continue
                
                # Get target position size
                target_pct = self.signal_values[symbol_str]['position_pct']
                
                # Current position
                current_position = self._get_position_size(context, sym)
                
                # Only trade if signal is strong enough or we're exiting
                signal_strength = abs(self.signal_values[symbol_str]['ensemble'])
                min_signal_strength = 0.2  # Minimum signal strength to enter
                
                # Calculate dynamic position size based on volatility and Kelly criterion
                if target_pct != 0:
                    # Kelly-adjusted position size
                    if self.signal_values[symbol_str]['ensemble'] > 0:
                        win_rate = 0.55  # Estimated from backtest
                        win_loss_ratio = 1.5  # Avg win / avg loss
                    else:
                        win_rate = 0.55  # For shorts
                        win_loss_ratio = 1.5
                    
                    kelly_pct = calculate_kelly_fraction(win_rate, win_loss_ratio) * self.kelly_fraction
                    volatility_factor = 0.15 / max(0.05, self.current_volatility.get(symbol_str, 0.15))
                    
                    # Final dynamic position size
                    adjusted_target = target_pct * min(1.0, kelly_pct * volatility_factor)
                    
                    # Ensure within limits
                    if abs(adjusted_target) < self.min_position_size:
                        # Not worth trading
                        if current_position == 0:
                            adjusted_target = 0
                        else:
                            # Exit existing position
                            adjusted_target = 0
                    
                    # Cap at maximum
                    adjusted_target = np.clip(adjusted_target, -self.max_position_size, self.max_position_size)
                else:
                    adjusted_target = 0
                
                # Log the decision
                logger.info(f"Symbol: {symbol_str}, Signal: {self.signal_values[symbol_str]['ensemble']:.2f}, "
                          f"Target: {adjusted_target:.2f}, Current: {current_position:.2f}")
                
                # Set stop loss and take profit levels if entering a new position
                current_price = data.current(sym, 'price')
                
                if (current_position == 0 and adjusted_target != 0) or (
                    current_position > 0 and adjusted_target <= 0) or (
                    current_position < 0 and adjusted_target >= 0):
                    
                    # Calculate dynamic stop loss
                    atr = self.indicators[symbol_str]['atr'].iloc[-1] if symbol_str in self.indicators else current_price * 0.02
                    
                    if self.dynamic_stop_loss:
                        stop_pct = self.atr_stop_multiplier * atr / current_price
                    else:
                        stop_pct = self.base_stop_loss
                    
                    # Take profit at 2x the stop loss by default
                    take_profit_pct = stop_pct * 2
                    
                    # Record for later use
                    if adjusted_target > 0:
                        # Long position
                        self.stop_losses[symbol_str] = current_price * (1 - stop_pct)
                        self.take_profits[symbol_str] = current_price * (1 + take_profit_pct)
                    elif adjusted_target < 0:
                        # Short position
                        self.stop_losses[symbol_str] = current_price * (1 + stop_pct)
                        self.take_profits[symbol_str] = current_price * (1 - take_profit_pct)
                
                # Execute the trade
                if current_position != adjusted_target:
                    if signal_strength >= min_signal_strength or adjusted_target == 0:
                        order_target_percent(sym, adjusted_target)
                        logger.info(f"Order placed for {symbol_str}: target {adjusted_target:.2f}")
                    else:
                        logger.info(f"Signal too weak for {symbol_str}: {signal_strength:.2f} < {min_signal_strength}")
        
        except Exception as e:
            logger.error(f"Error in rebalance: {str(e)}")
    
    def check_positions(self, context, data):
        """
        Check existing positions for stop loss/take profit triggers
        
        Args:
            context: Zipline context
            data: Zipline data object
        """
        if not self.initialized:
            return
        
        try:
            for sym in context.symbols:
                symbol_str = sym.symbol
                current_price = data.current(sym, 'price')
                position = self._get_position_size(context, sym)
                
                # Skip if no position
                if position == 0:
                    continue
                
                # Check if stop loss or take profit has been hit
                if symbol_str in self.stop_losses and symbol_str in self.take_profits:
                    # Long position
                    if position > 0:
                        # Check stop loss
                        if current_price <= self.stop_losses[symbol_str]:
                            logger.info(f"Stop loss triggered for {symbol_str} at {current_price}")
                            order_target_percent(sym, 0)  # Close position
                            self._record_trade(symbol_str, "stop_loss", position, 0)
                        
                        # Check take profit
                        elif current_price >= self.take_profits[symbol_str]:
                            logger.info(f"Take profit triggered for {symbol_str} at {current_price}")
                            order_target_percent(sym, 0)  # Close position
                            self._record_trade(symbol_str, "take_profit", position, 0)
                    
                    # Short position
                    elif position < 0:
                        # Check stop loss (price rise for shorts)
                        if current_price >= self.stop_losses[symbol_str]:
                            logger.info(f"Stop loss triggered for short {symbol_str} at {current_price}")
                            order_target_percent(sym, 0)  # Close position
                            self._record_trade(symbol_str, "stop_loss", position, 0)
                        
                        # Check take profit (price fall for shorts)
                        elif current_price <= self.take_profits[symbol_str]:
                            logger.info(f"Take profit triggered for short {symbol_str} at {current_price}")
                            order_target_percent(sym, 0)  # Close position
                            self._record_trade(symbol_str, "take_profit", position, 0)
        
        except Exception as e:
            logger.error(f"Error in check_positions: {str(e)}")
    
    def adjust_risk_parameters(self, context, data):
        """
        Dynamically adjust risk parameters based on performance
        
        Args:
            context: Zipline context
            data: Zipline data object
        """
        if not self.initialized or len(self.portfolio_values) < 10:
            return
        
        try:
            # Calculate recent performance
            recent_values = [v[1] for v in self.portfolio_values[-10:]]
            recent_returns = np.diff(recent_values) / recent_values[:-1]
            
            recent_std = np.std(recent_returns) * np.sqrt(252)  # Annualized
            
            # If volatility is high, reduce risk
            if recent_std > self.volatility_target * 1.5:
                self.current_risk_per_trade = max(self.base_risk_per_trade * 0.5, 0.005)
                logger.info(f"Reducing risk due to high volatility: {recent_std:.2f}")
            
            # If volatility is low, increase risk (up to base level)
            elif recent_std < self.volatility_target * 0.5:
                self.current_risk_per_trade = min(self.current_risk_per_trade * 1.2, self.base_risk_per_trade)
                logger.info(f"Increasing risk due to low volatility: {recent_std:.2f}")
        
        except Exception as e:
            logger.error(f"Error in adjust_risk_parameters: {str(e)}")
    
    def adapt_strategy(self, context, data):
        """
        Weekly adaptation of strategy parameters based on performance
        
        Args:
            context: Zipline context
            data: Zipline data object
        """
        if not self.initialized or len(self.portfolio_values) < 20:
            return
        
        try:
            # Calculate overall performance statistics
            values = np.array([v[1] for v in self.portfolio_values])
            returns = np.diff(values) / values[:-1]
            
            # Performance metrics
            total_return = (values[-1] / values[0]) - 1
            volatility = np.std(returns) * np.sqrt(252)
            sharpe = (np.mean(returns) * 252) / volatility if volatility > 0 else 0
            
            # Monitor drawdowns
            running_max = np.maximum.accumulate(values)
            drawdowns = values / running_max - 1
            max_drawdown = np.min(drawdowns)
            
            logger.info(f"Strategy performance: Return: {total_return:.2f}, "
                      f"Sharpe: {sharpe:.2f}, Max Drawdown: {max_drawdown:.2f}")
            
            # Strategy adaptation based on performance
            # 1. Adjust trend/mean-reversion balance based on what's working
            trend_returns = []
            mr_returns = []
            
            # TODO: Implement more sophisticated performance attribution
            # For now, use a simple heuristic
            
            # 2. Adjust risk parameters based on Sharpe ratio
            if sharpe > 1.5:
                # Strategy is performing well, can increase risk slightly
                self.kelly_fraction = min(self.kelly_fraction * 1.05, 0.7)  # Cap at 0.7
                logger.info(f"Increasing Kelly fraction to {self.kelly_fraction:.2f}")
            elif sharpe < 0.5:
                # Strategy is underperforming, reduce risk
                self.kelly_fraction = max(self.kelly_fraction * 0.9, 0.3)  # Floor at 0.3
                logger.info(f"Decreasing Kelly fraction to {self.kelly_fraction:.2f}")
            
            # 3. Adjust stop loss parameters based on drawdowns
            if max_drawdown < -0.1:
                # Tighten stops if experiencing significant drawdowns
                self.atr_stop_multiplier = max(self.atr_stop_multiplier * 0.9, 1.0)  # Tighter stops
                logger.info(f"Tightening stops to {self.atr_stop_multiplier:.2f} x ATR")
            else:
                # Can use wider stops if drawdowns are controlled
                self.atr_stop_multiplier = min(self.atr_stop_multiplier * 1.05, 3.0)  # Wider stops
                logger.info(f"Widening stops to {self.atr_stop_multiplier:.2f} x ATR")
        
        except Exception as e:
            logger.error(f"Error in adapt_strategy: {str(e)}")
    
    def _get_position_size(self, context, sym):
        """Get current position size as a percentage of portfolio"""
        port_value = context.portfolio.portfolio_value
        if port_value <= 0:
            return 0
        
        positions = context.portfolio.positions
        if sym in positions:
            pos = positions[sym]
            return (pos.amount * pos.last_sale_price) / port_value
        
        return 0
    
    def _check_excessive_drawdown(self, context):
        """Check if we're in an excessive drawdown that requires risk reduction"""
        if len(self.portfolio_values) < 2:
            return False
        
        # Calculate current drawdown
        values = np.array([v[1] for v in self.portfolio_values])
        peak = np.max(values)
        current = values[-1]
        drawdown = (current / peak) - 1
        
        # Check against our limit
        return drawdown < -self.max_drawdown_limit
    
    def _reduce_risk(self, context, data):
        """Reduce risk when in excessive drawdown"""
        # Cut position sizes in half
        for sym in context.symbols:
            current_pct = self._get_position_size(context, sym)
            if abs(current_pct) > 0:
                new_pct = current_pct * 0.5
                order_target_percent(sym, new_pct)
                logger.info(f"Reducing position in {sym.symbol} from {current_pct:.2f} to {new_pct:.2f}")
        
        # Reduce future risk parameters
        self.current_risk_per_trade = self.base_risk_per_trade * 0.5
        self.kelly_fraction = self.kelly_fraction * 0.5
    
    def _record_trade(self, symbol, exit_reason, old_position, new_position):
        """Record trade details for analysis"""
        trade = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'exit_reason': exit_reason,
            'old_position': old_position,
            'new_position': new_position
        }
        self.trades.append(trade) 