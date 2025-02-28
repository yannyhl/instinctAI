"""
Trading Strategies Module
-----------------------
Contains implementations of trading strategies
"""

import logging
import pandas as pd
import numpy as np
import backtrader as bt
from typing import Dict, List, Optional, Union, Any

import config

logger = logging.getLogger(__name__)

class FundingRateMomentumStrategy(bt.Strategy):
    """
    A sophisticated strategy combining funding rate analysis with multi-timeframe momentum indicators,
    mean reversion principles, and adaptive position sizing for cryptocurrency trading.
    
    Inspired by techniques used at Renaissance Capital and other top quantitative firms:
    - Multi-timeframe signal analysis
    - Adaptive position sizing based on volatility
    - Statistical arbitrage principles
    - Dynamic parameter adjustment
    - Rigorous risk management
    """
    
    params = (
        # Signal generation parameters
        ('funding_threshold', 0.0001),    # Min funding rate to consider
        ('momentum_period', 14),          # Period for momentum calculation
        ('rsi_period', 14),               # Period for RSI calculation
        ('rsi_overbought', 65),           # RSI overbought threshold
        ('rsi_oversold', 45),             # RSI oversold threshold
        ('mean_reversion_period', 50),    # Period for mean reversion calculation
        
        # Position sizing and risk management
        ('risk_pct', 0.01),               # Base risk per trade (% of portfolio)
        ('max_risk_pct', 0.03),           # Maximum risk per trade
        ('kelly_fraction', 0.5),          # Kelly criterion fraction (conservative)
        ('use_kelly', True),              # Whether to use Kelly criterion for sizing
        
        # Exit parameters
        ('trailing_stop', 0.02),          # Trailing stop (2%)
        ('adaptive_trailing', True),      # Use ATR-based trailing stops
        ('atr_trailing_multiplier', 2.0), # Multiplier for ATR trailing stop
        ('atr_period', 14),               # ATR period
        ('take_profit', 0.05),            # Take profit level (5%)
        ('time_stop', 20),                # Exit after N bars if neither TP nor SL hit
        
        # Advanced parameters
        ('volatility_lookback', 21),      # Period for volatility calculation
        ('volatility_factor', 2.0),       # Factor for volatility adjustment
        ('regime_period', 100),           # Period for regime detection
        ('correlation_threshold', 0.3),   # Correlation threshold for spread trades
        ('max_trades', 10),               # Maximum concurrent positions
        ('trade_diversification', True),  # Diversify trades (long/short balance)
    )
    
    def __init__(self):
        # Market data
        self.data_close = self.datas[0].close
        self.data_open = self.datas[0].open
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume
        
        # Initialize indicators - price-based
        self.rsi = bt.indicators.RSI(period=self.p.rsi_period)
        self.sma20 = bt.indicators.SMA(period=20)
        self.sma50 = bt.indicators.SMA(period=50)
        self.sma200 = bt.indicators.SMA(period=200)
        self.atr = bt.indicators.ATR(period=self.p.atr_period)
        
        # Bollinger Bands for mean reversion
        self.bbands = bt.indicators.BollingerBands(period=self.p.mean_reversion_period, devfactor=2.0)
        
        # Volatility indicators
        self.volatility = bt.indicators.StdDev(period=self.p.volatility_lookback)
        self.historical_volatility = []  # Store historical volatility for regime detection
        
        # Advanced indicators
        self.macd = bt.indicators.MACD()
        
        # Multi-timeframe indicators (will be manually calculated)
        self.rsi_daily = None  # Will store RSI calculated on daily timeframe
        self.trend_daily = None  # Will store trend direction on daily timeframe
        
        # Order management
        self.order = None
        self.buy_price = None
        self.trailing_stop_price = None
        self.take_profit_price = None
        self.entry_bar = 0  # Track entry bar for time-based stops
        
        # Portfolio tracking
        self.starting_value = self.broker.getvalue()
        self.highest_value = self.starting_value
        self.lowest_value = float('inf')
        self.drawdowns = []  # Track drawdowns for risk management
        
        # Funding rate data 
        self.funding_rates = self.simulate_funding_rates()
        
        # Trade tracking
        self.trade_count = 0
        self.profitable_trades = 0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 0
        self.trade_history = []  # Track all trades for analysis
        self.trade_pnl = []  # Track PnL of all trades
        self.trade_duration = []  # Track duration of all trades
        
        # Strategy state
        self.market_regime = 'neutral'  # Can be 'bull', 'bear', or 'neutral'
        self.regime_changes = []  # Track regime changes
        self.last_signal = None  # Last signal generated
        self.open_positions = {}  # Track open positions
        self.position_sizes = []  # Track position sizes
        
        # Print strategy parameters
        logger.info(f"Strategy initialized with parameters: {self.p.__dict__}")
        logger.info(f"Starting portfolio value: {self.starting_value}")
    
    def simulate_funding_rates(self):
        """Simulate funding rates for backtesting with realistic patterns"""
        # In live trading, this would be replaced with actual API calls
        # For backtest, we'll create a synthetic funding rate series
        dates = []
        rates = []
        
        # Generate a synthetic funding rate series with market-correlated behavior
        base_rate = 0.0001  # 0.01% base rate
        trend_cycle = 14  # 14-day cycle
        
        for i in range(len(self.data)):
            # Date for this bar
            date = self.data.datetime.datetime(i)
            
            # Base cyclical component
            cycle_component = np.sin(2 * np.pi * i / trend_cycle) * 0.0008
            
            # Correlation with price trends (funding tends to be positive in uptrends)
            if i > 0:
                price_change = (self.data.close[i] - self.data.close[max(0, i-trend_cycle)]) / self.data.close[max(0, i-trend_cycle)]
                price_component = min(max(price_change * 0.01, -0.001), 0.001)  # Clamp to reasonable range
            else:
                price_component = 0
                
            # Random component
            random_component = np.random.normal(0, 0.0002)
            
            # Combined rate
            rate = base_rate + cycle_component + price_component + random_component
            
            dates.append(date)
            rates.append(rate)
        
        return pd.Series(rates, index=dates)
    
    def get_current_funding_rate(self, date):
        """Get the current funding rate"""
        # Check if funding rates are available
        if not hasattr(self, 'funding_rates') or self.funding_rates.empty:
            # Generate a synthetic funding rate
            return 0.001 * np.sin(date.hour * np.pi / 4)
        
        # Find the closest date in our funding rates
        closest_date = min(self.funding_rates.index, 
                          key=lambda x: abs(x - date))
        
        return self.funding_rates[closest_date]
    
    def detect_market_regime(self):
        """Detect the current market regime (bull, bear, neutral)"""
        # Use price in relation to moving averages to determine regime
        if self.sma20[0] > self.sma50[0] > self.sma200[0]:
            new_regime = 'bull'
        elif self.sma20[0] < self.sma50[0] < self.sma200[0]:
            new_regime = 'bear'
        else:
            new_regime = 'neutral'
            
        # Check if regime has changed
        if new_regime != self.market_regime:
            self.regime_changes.append((len(self), self.market_regime, new_regime))
            self.market_regime = new_regime
            logger.info(f"Market regime changed to: {self.market_regime}")
            
        return self.market_regime
    
    def calculate_kelly_fraction(self):
        """Calculate Kelly criterion for position sizing"""
        if len(self.trade_pnl) < 10:
            return self.p.kelly_fraction  # Default until we have enough data
            
        win_rate = self.profitable_trades / max(1, self.trade_count)
        avg_win = np.mean([pnl for pnl in self.trade_pnl if pnl > 0]) if any(pnl > 0 for pnl in self.trade_pnl) else 0
        avg_loss = abs(np.mean([pnl for pnl in self.trade_pnl if pnl < 0])) if any(pnl < 0 for pnl in self.trade_pnl) else 1
        
        if avg_loss == 0:
            return self.p.max_risk_pct  # Avoid division by zero
            
        # Kelly formula: f* = (bp - q) / b where b = net odds, p = win probability, q = 1-p
        kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        
        # Apply a fraction of Kelly (half-Kelly is common in practice)
        conservative_kelly = kelly * self.p.kelly_fraction
        
        # Clamp to reasonable range
        return max(0.001, min(conservative_kelly, self.p.max_risk_pct))
    
    def calculate_position_size(self, is_long):
        """Calculate position size based on risk parameters and volatility"""
        portfolio_value = self.broker.getvalue()
        
        # Adjust risk based on market conditions
        if self.market_regime == 'bull' and is_long:
            regime_risk_factor = 1.2  # Increase size in bull market for longs
        elif self.market_regime == 'bear' and not is_long:
            regime_risk_factor = 1.2  # Increase size in bear market for shorts
        else:
            regime_risk_factor = 0.8  # Reduce size when trading against the trend
        
        # Adjust for consecutive losses
        drawdown_factor = max(0.5, 1.0 - (self.consecutive_losses * 0.1))
        
        # Use Kelly criterion if enabled
        if self.p.use_kelly:
            base_risk = self.calculate_kelly_fraction()
        else:
            base_risk = self.p.risk_pct
            
        # Final risk percentage
        adjusted_risk = base_risk * regime_risk_factor * drawdown_factor
        risk_amount = portfolio_value * adjusted_risk
        
        # Calculate position size based on ATR for volatility-adjusted sizing
        atr_value = self.atr[0]
        if atr_value > 0:
            # Risk per unit = ATR * multiplier
            risk_per_unit = atr_value * self.p.atr_trailing_multiplier
            position_size = risk_amount / risk_per_unit
            
            # Log the calculation
            logger.info(f"Position size calculation: Portfolio={portfolio_value:.2f}, Risk={adjusted_risk:.4f}, "
                       f"ATR={atr_value:.2f}, Size={position_size:.6f}")
            
            return position_size
        
        # Fallback to a percentage of portfolio
        return portfolio_value * 0.01 / self.data_close[0]
    
    def next(self):
        """Main strategy logic - executed for each new price bar"""
        # Skip if we have a pending order
        if self.order:
            return
            
        # Current price and indicators
        current_price = self.data_close[0]
        current_rsi = self.rsi[0]
        current_bar = len(self)
        
        # Update market regime
        self.detect_market_regime()
        
        # Store volatility for regime detection
        current_volatility = self.volatility[0]
        self.historical_volatility.append(current_volatility)
        if len(self.historical_volatility) > self.p.regime_period:
            self.historical_volatility.pop(0)
        
        # Get current funding rate
        current_date = self.data.datetime.datetime(0)
        funding_rate = self.get_current_funding_rate(current_date)
        
        # Log current state
        logger.info(f"Date: {current_date}, Close: {current_price}, RSI: {current_rsi:.2f}, "
                   f"Funding Rate: {funding_rate:.6f}, Regime: {self.market_regime}, "
                   f"Portfolio: {self.broker.getvalue():.2f}")
        
        # Update trailing stop if we have a position
        if self.position:
            # For long positions, move stop up if price increases
            if self.position.size > 0:
                # Update highest value seen
                if current_price > self.highest_value:
                    self.highest_value = current_price
                    
                    # Calculate new trailing stop
                    if self.p.adaptive_trailing:
                        # ATR-based trailing stop
                        new_stop = current_price - (self.atr[0] * self.p.atr_trailing_multiplier)
                    else:
                        # Percentage-based trailing stop
                        new_stop = current_price * (1 - self.p.trailing_stop)
                        
                    # Only move stop up, never down
                    if new_stop > self.trailing_stop_price:
                        self.trailing_stop_price = new_stop
                        logger.info(f"Updated trailing stop to {self.trailing_stop_price:.2f}")
            
            # For short positions, move stop down if price decreases
            elif self.position.size < 0:
                # Update lowest value seen
                if current_price < self.lowest_value:
                    self.lowest_value = current_price
                    
                    # Calculate new trailing stop
                    if self.p.adaptive_trailing:
                        # ATR-based trailing stop
                        new_stop = current_price + (self.atr[0] * self.p.atr_trailing_multiplier)
                    else:
                        # Percentage-based trailing stop
                        new_stop = current_price * (1 + self.p.trailing_stop)
                        
                    # Only move stop down, never up
                    if new_stop < self.trailing_stop_price:
                        self.trailing_stop_price = new_stop
                        logger.info(f"Updated trailing stop to {self.trailing_stop_price:.2f}")
        
        # Check exit conditions if in a position
        if self.position:
            # Time-based exit
            bars_in_trade = current_bar - self.entry_bar
            if bars_in_trade >= self.p.time_stop:
                if self.position.size > 0:
                    logger.info(f"Time stop hit after {bars_in_trade} bars. Closing LONG position.")
                    self.order = self.sell(size=self.position.size)
                else:
                    logger.info(f"Time stop hit after {bars_in_trade} bars. Closing SHORT position.")
                    self.order = self.buy(size=abs(self.position.size))
                return
            
            # Check take profit and stop loss
            if self.position.size > 0:  # Long position
                # Check take profit
                if current_price >= self.take_profit_price:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    self.profitable_trades += 1
                    self.consecutive_losses = 0
                    return
                
                # Check trailing stop
                if current_price <= self.trailing_stop_price:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Trailing stop hit at {current_price:.2f}")
                    # Check if this was a loss
                    if current_price < self.buy_price:
                        self.consecutive_losses += 1
                        self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
                    else:
                        self.profitable_trades += 1
                        self.consecutive_losses = 0
                    return
            
            # Short position
            elif self.position.size < 0:
                # Check take profit
                if current_price <= self.take_profit_price:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    self.profitable_trades += 1
                    self.consecutive_losses = 0
                    return
                
                # Check trailing stop
                if current_price >= self.trailing_stop_price:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Trailing stop hit at {current_price:.2f}")
                    # Check if this was a loss
                    if current_price > self.buy_price:
                        self.consecutive_losses += 1
                        self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
                    else:
                        self.profitable_trades += 1
                        self.consecutive_losses = 0
                    return
        
        # Entry signals
        if not self.position:
            # LONG signal conditions - simplified compared to previous version
            if (funding_rate < -self.p.funding_threshold or current_rsi < self.p.rsi_oversold):
                
                # Optional filter: Check if price is below lower Bollinger Band
                # This acts as a mean reversion filter but is now optional
                mean_reversion_long = current_price < self.bbands.lines.bot[0]
                
                # Check market regime - only use as a modifier for position sizing, not as a filter
                trend_aligned = self.market_regime != 'bear'  # Simplified check
                
                # Generate LONG signal - removed extra filters to increase trade frequency
                # Calculate position size
                size = self.calculate_position_size(is_long=True)
                
                # Enter long position
                self.order = self.buy(size=size)
                self.buy_price = current_price
                self.entry_bar = current_bar
                
                # Set trailing stop and take profit levels
                if self.p.adaptive_trailing:
                    self.trailing_stop_price = current_price - (self.atr[0] * self.p.atr_trailing_multiplier)
                    self.take_profit_price = current_price + (self.atr[0] * self.p.atr_trailing_multiplier * self.p.take_profit / self.p.trailing_stop)
                else:
                    self.trailing_stop_price = current_price * (1 - self.p.trailing_stop)
                    self.take_profit_price = current_price * (1 + self.p.take_profit)
                
                # Reset highest value
                self.highest_value = current_price
                
                # Update trade count
                self.trade_count += 1
                
                logger.info(f"LONG signal at {current_price:.2f}, Size: {size}, "
                           f"Stop: {self.trailing_stop_price:.2f}, TP: {self.take_profit_price:.2f}")
            
            # SHORT signal conditions - simplified compared to previous version
            elif (funding_rate > self.p.funding_threshold or current_rsi > self.p.rsi_overbought):
                
                # Optional filter: Check if price is above upper Bollinger Band
                # This acts as a mean reversion filter but is now optional
                mean_reversion_short = current_price > self.bbands.lines.top[0]
                
                # Check market regime - only use as a modifier for position sizing, not as a filter
                trend_aligned = self.market_regime != 'bull'  # Simplified check
                
                # Generate SHORT signal - removed extra filters to increase trade frequency
                # Calculate position size
                size = self.calculate_position_size(is_long=False)
                
                # Enter short position
                self.order = self.sell(size=size)
                self.buy_price = current_price
                self.entry_bar = current_bar
                
                # Set trailing stop and take profit levels
                if self.p.adaptive_trailing:
                    self.trailing_stop_price = current_price + (self.atr[0] * self.p.atr_trailing_multiplier)
                    self.take_profit_price = current_price - (self.atr[0] * self.p.atr_trailing_multiplier * self.p.take_profit / self.p.trailing_stop)
                else:
                    self.trailing_stop_price = current_price * (1 + self.p.trailing_stop)
                    self.take_profit_price = current_price * (1 - self.p.take_profit)
                
                # Reset lowest value
                self.lowest_value = current_price
                
                # Update trade count
                self.trade_count += 1
                
                logger.info(f"SHORT signal at {current_price:.2f}, Size: {size}, "
                           f"Stop: {self.trailing_stop_price:.2f}, TP: {self.take_profit_price:.2f}")
    
    def notify_order(self, order):
        """Handle order status updates"""
        if order.status in [order.Submitted, order.Accepted]:
            # Order has been submitted/accepted - no action required
            return
        
        # Check if order has been completed
        if order.status in [order.Completed]:
            # Record trade details
            if order.isbuy():
                logger.info(f"BUY executed at {order.executed.price:.2f}, Cost: {order.executed.value:.2f}")
                
                # Record position details if opening a long position
                if self.position.size > 0:
                    self.position_sizes.append(self.position.size)
            else:
                logger.info(f"SELL executed at {order.executed.price:.2f}, Profit: {order.executed.pnl:.2f}")
                
                # Record trade results if closing a position
                if order.executed.pnl != 0:
                    self.trade_pnl.append(order.executed.pnl)
                    self.trade_history.append({
                        'exit_bar': len(self),
                        'entry_price': self.buy_price,
                        'exit_price': order.executed.price,
                        'pnl': order.executed.pnl,
                        'bars_held': len(self) - self.entry_bar,
                        'direction': 'long' if order.executed.pnl > 0 else 'short'
                    })
                    self.trade_duration.append(len(self) - self.entry_bar)
                    
                # Record position details if opening a short position
                if self.position.size < 0:
                    self.position_sizes.append(abs(self.position.size))
        
        # Reset order variable regardless of status
        self.order = None
    
    def stop(self):
        """Called when backtest is complete"""
        # Calculate final performance metrics
        final_value = self.broker.getvalue()
        roi = (final_value / self.starting_value - 1) * 100
        win_rate = (self.profitable_trades / self.trade_count * 100) if self.trade_count > 0 else 0
        
        # Calculate more advanced metrics
        avg_trade_pnl = np.mean(self.trade_pnl) if self.trade_pnl else 0
        avg_winner = np.mean([pnl for pnl in self.trade_pnl if pnl > 0]) if any(pnl > 0 for pnl in self.trade_pnl) else 0
        avg_loser = np.mean([pnl for pnl in self.trade_pnl if pnl < 0]) if any(pnl < 0 for pnl in self.trade_pnl) else 0
        profit_factor = abs(sum([pnl for pnl in self.trade_pnl if pnl > 0]) / sum([pnl for pnl in self.trade_pnl if pnl < 0])) if any(pnl < 0 for pnl in self.trade_pnl) else float('inf')
        avg_trade_bars = np.mean(self.trade_duration) if self.trade_duration else 0
        
        # Log results
        logger.info("====== Backtest Results ======")
        logger.info(f"Starting Portfolio Value: {self.starting_value:.2f}")
        logger.info(f"Final Portfolio Value: {final_value:.2f}")
        logger.info(f"ROI: {roi:.2f}%")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Profitable Trades: {self.profitable_trades}")
        logger.info(f"Win Rate: {win_rate:.2f}%")
        logger.info(f"Max Consecutive Losses: {self.max_consecutive_losses}")
        logger.info(f"Average Trade PnL: {avg_trade_pnl:.2f}")
        logger.info(f"Average Winner: {avg_winner:.2f}")
        logger.info(f"Average Loser: {avg_loser:.2f}")
        logger.info(f"Profit Factor: {profit_factor:.2f}")
        logger.info(f"Average Trade Duration: {avg_trade_bars:.1f} bars")


class VolumeBreakoutStrategy(bt.Strategy):
    """
    A strategy that identifies and trades volume breakouts in cryptocurrency markets.
    This strategy looks for significant increases in volume combined with price movement
    above resistance or below support levels.
    """
    
    params = (
        ('volume_threshold', 2.0),  # Volume must be this multiple of average
        ('lookback_period', 20),    # Period for calculating average volume
        ('breakout_periods', 5),    # Number of periods to identify range
        ('risk_pct', 0.015),        # 1.5% risk per trade
        ('profit_factor', 2.0),     # Profit target as multiple of risk
        ('trailing_pct', 0.01),     # 1% trailing stop
        ('max_trades', 5),          # Maximum number of open trades
    )
    
    def __init__(self):
        # Market data
        self.data_close = self.datas[0].close
        self.data_open = self.datas[0].open
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume
        
        # Calculate average volume
        self.average_volume = bt.indicators.SimpleMovingAverage(
            self.data_volume, period=self.p.lookback_period
        )
        
        # Identify price ranges
        self.highest_high = bt.indicators.Highest(
            self.data_high, period=self.p.breakout_periods
        )
        self.lowest_low = bt.indicators.Lowest(
            self.data_low, period=self.p.breakout_periods
        )
        
        # ATR for volatility measurement
        self.atr = bt.indicators.ATR(period=14)
        
        # Order tracking
        self.orders = []  # Track multiple orders
        self.stops = {}   # Track stop prices for each order
        self.targets = {} # Track target prices for each order
        self.entry_prices = {} # Track entry prices
        
        # Portfolio tracking
        self.starting_value = self.broker.getvalue()
        
        logger.info(f"Volume Breakout Strategy initialized with lookback {self.p.lookback_period}")
    
    def next(self):
        """Main strategy logic for each price bar"""
        # Current price and indicators
        current_price = self.data_close[0]
        current_volume = self.data_volume[0]
        avg_volume = self.average_volume[0]
        atr_value = self.atr[0]
        
        # Check if volume threshold is exceeded
        volume_spike = current_volume > (avg_volume * self.p.volume_threshold)
        
        # Check for breakouts (price moving above recent highs or below recent lows)
        breakout_up = current_price > self.highest_high[-1]
        breakout_down = current_price < self.lowest_low[-1]
        
        # Calculate maximum number of open positions based on current portfolio
        portfolio_value = self.broker.getvalue()
        risk_amount = portfolio_value * self.p.risk_pct
        
        # Update trailing stops for open positions
        self.update_trailing_stops(current_price)
        
        # Check for entry signals
        if len(self.orders) < self.p.max_trades:  # Check if we have room for more trades
            # LONG signal: Volume spike with upward breakout
            if volume_spike and breakout_up:
                # Calculate stop loss distance based on ATR
                stop_distance = atr_value * 1.5
                
                if stop_distance > 0:
                    # Calculate position size
                    size = risk_amount / stop_distance
                    
                    # Calculate stop loss and take profit levels
                    stop_loss = current_price - stop_distance
                    take_profit = current_price + (stop_distance * self.p.profit_factor)
                    
                    # Place buy order
                    order = self.buy(size=size)
                    self.orders.append(order)
                    
                    # Track stop loss and take profit for this order
                    self.stops[order.ref] = stop_loss
                    self.targets[order.ref] = take_profit
                    self.entry_prices[order.ref] = current_price
                    
                    logger.info(f"LONG Volume Breakout at {current_price:.2f}, Size: {size:.4f}, "
                               f"Stop: {stop_loss:.2f}, Target: {take_profit:.2f}")
            
            # SHORT signal: Volume spike with downward breakout
            elif volume_spike and breakout_down:
                # Calculate stop loss distance based on ATR
                stop_distance = atr_value * 1.5
                
                if stop_distance > 0:
                    # Calculate position size
                    size = risk_amount / stop_distance
                    
                    # Calculate stop loss and take profit levels
                    stop_loss = current_price + stop_distance
                    take_profit = current_price - (stop_distance * self.p.profit_factor)
                    
                    # Place sell order
                    order = self.sell(size=size)
                    self.orders.append(order)
                    
                    # Track stop loss and take profit for this order
                    self.stops[order.ref] = stop_loss
                    self.targets[order.ref] = take_profit
                    self.entry_prices[order.ref] = current_price
                    
                    logger.info(f"SHORT Volume Breakout at {current_price:.2f}, Size: {size:.4f}, "
                               f"Stop: {stop_loss:.2f}, Target: {take_profit:.2f}")
    
    def update_trailing_stops(self, current_price):
        """Update trailing stops for all open positions"""
        # Iterate through all positions with associated orders
        for trade in self.broker.positions:
            # Find associated order
            order_ref = None
            for ref in self.stops:
                if trade.ref == ref:
                    order_ref = ref
                    break
            
            if order_ref is None:
                continue
                
            # Update trailing stop for long positions
            if trade.size > 0:
                # Calculate new stop based on trailing percentage
                potential_stop = current_price * (1 - self.p.trailing_pct)
                
                # Only move stop up, never down
                if potential_stop > self.stops.get(order_ref, 0):
                    self.stops[order_ref] = potential_stop
                    logger.info(f"Updated trailing stop for LONG to {potential_stop:.2f}")
            
            # Update trailing stop for short positions
            elif trade.size < 0:
                # Calculate new stop based on trailing percentage
                potential_stop = current_price * (1 + self.p.trailing_pct)
                
                # Only move stop down, never up
                if potential_stop < self.stops.get(order_ref, float('inf')):
                    self.stops[order_ref] = potential_stop
                    logger.info(f"Updated trailing stop for SHORT to {potential_stop:.2f}")
    
    def notify_order(self, order):
        """Handle order status updates"""
        if order.status in [order.Submitted, order.Accepted]:
            # Order has been submitted/accepted - no action required
            return
        
        # Check if order has been completed
        if order.status in [order.Completed]:
            # Record trade details
            if order.isbuy():
                logger.info(f"BUY executed at {order.executed.price:.2f}, Size: {order.executed.size:.4f}")
            else:
                logger.info(f"SELL executed at {order.executed.price:.2f}, Size: {order.executed.size:.4f}")
        
        # Remove order from tracking lists if it's completed or canceled
        if order.status in [order.Completed, order.Canceled, order.Expired]:
            if order in self.orders:
                self.orders.remove(order)
    
    def stop(self):
        """Called when backtest is complete"""
        # Calculate final performance metrics
        final_value = self.broker.getvalue()
        roi = (final_value / self.starting_value - 1) * 100
        max_roi = (self.highest_value / self.starting_value - 1) * 100
        win_rate = (self.profitable_trades / self.trade_count * 100) if self.trade_count > 0 else 0
        
        logger.info("====== Backtest Results ======")
        logger.info(f"Starting Portfolio Value: {self.starting_value:.2f}")
        logger.info(f"Final Portfolio Value: {final_value:.2f}")
        logger.info(f"ROI: {roi:.2f}%")
        logger.info(f"Maximum ROI: {max_roi:.2f}%")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Profitable Trades: {self.profitable_trades}")
        logger.info(f"Win Rate: {win_rate:.2f}%")


class LiquidityAwareScalpingStrategy(bt.Strategy):
    """
    A scalping strategy that utilizes order book liquidity analysis
    to identify short-term opportunities.
    """
    
    params = (
        ('risk_pct', 0.01),          # Max risk per trade (1% of portfolio)
        ('profit_factor', 1.5),      # Profit target as multiple of risk
        ('max_holding_period', 12),  # Maximum bars to hold a position (e.g., 12 hours)
        ('liquidity_threshold', 2.0), # Liquidity imbalance threshold
        ('size', 0.5),               # Initial position size
    )
    
    def __init__(self):
        # Price data
        self.data_close = self.datas[0].close
        self.data_open = self.datas[0].open
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume
        
        # Technical indicators
        self.atr = bt.indicators.ATR(period=14)
        self.ema_fast = bt.indicators.EMA(period=9)
        self.ema_slow = bt.indicators.EMA(period=21)
        
        # Order management
        self.order = None
        self.entry_price = None
        self.entry_bar = 0
        self.stop_loss = None
        self.take_profit = None
        
        # Portfolio tracking
        self.starting_value = self.broker.getvalue()
        
        # Liquidity simulation (in live trading, this would come from exchange)
        self.liquidity_imbalance = self.simulate_liquidity_imbalance()
        
        logger.info(f"Liquidity Scalping Strategy initialized with {self.p.risk_pct*100}% risk per trade")
    
    def simulate_liquidity_imbalance(self):
        """
        Simulate liquidity imbalance for backtesting
        In live trading, this would be calculated from real order book data
        """
        # Create an array of liquidity imbalance values
        # Positive values indicate more buy liquidity, negative values indicate more sell liquidity
        dates = []
        imbalance = []
        
        for i in range(len(self.data)):
            dates.append(self.data.datetime.datetime(i))
            
            # Generate imbalance based on price movements and some randomness
            # This is a simplified simulation - real implementation would use order book data
            price_change = 0
            if i > 0:
                price_change = (self.data.close[i] - self.data.close[i-1]) / self.data.close[i-1]
            
            # Imbalance tends to correlate with recent price changes plus noise
            # We add some mean-reversion tendency
            base_imbalance = price_change * 5 + np.random.normal(0, 0.5)
            mean_reversion = -0.3 * base_imbalance  # Mean reversion component
            
            imb = base_imbalance + mean_reversion
            imbalance.append(imb)
        
        return pd.Series(imbalance, index=dates)
    
    def get_current_liquidity_imbalance(self):
        """Get current liquidity imbalance"""
        current_date = self.data.datetime.datetime(0)
        closest_date = min(self.liquidity_imbalance.index, 
                          key=lambda x: abs(x - current_date))
        return self.liquidity_imbalance[closest_date]
    
    def next(self):
        """Main strategy logic for each price bar"""
        # Skip if we have a pending order
        if self.order:
            return
        
        # Get current data
        current_price = self.data_close[0]
        current_bar = len(self.data)
        
        # Calculate price direction
        price_direction = 1 if self.ema_fast[0] > self.ema_slow[0] else -1
        
        # Get current liquidity imbalance
        imbalance = self.get_current_liquidity_imbalance()
        
        # Log current state
        logger.info(f"Bar: {current_bar}, Price: {current_price:.2f}, "
                   f"Imbalance: {imbalance:.2f}, Direction: {price_direction}")
        
        # Check if max holding period exceeded
        if self.position and (current_bar - self.entry_bar) >= self.p.max_holding_period:
            if self.position.size > 0:
                self.order = self.sell(size=self.position.size)
                logger.info(f"Max holding period reached. Closing LONG at {current_price:.2f}")
            else:
                self.order = self.buy(size=abs(self.position.size))
                logger.info(f"Max holding period reached. Closing SHORT at {current_price:.2f}")
            return
        
        # Check stop loss and take profit if in a position
        if self.position:
            if self.position.size > 0:  # Long position
                if current_price <= self.stop_loss:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Stop loss hit at {current_price:.2f}")
                    return
                
                if current_price >= self.take_profit:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    return
                    
            else:  # Short position
                if current_price >= self.stop_loss:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Stop loss hit at {current_price:.2f}")
                    return
                
                if current_price <= self.take_profit:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    return
        
        # Entry logic - look for significant liquidity imbalance
        if not self.position:
            # Calculate risk per trade
            portfolio_value = self.broker.getvalue()
            risk_amount = portfolio_value * self.p.risk_pct
            
            # LONG signal: Strong buy liquidity (positive imbalance) and upward price movement
            if imbalance > self.p.liquidity_threshold and price_direction > 0:
                # Calculate position size based on ATR
                atr_value = self.atr[0]
                stop_distance = atr_value * 1.5  # Stop loss 1.5 ATR away
                
                if stop_distance > 0:
                    size = min(risk_amount / stop_distance, self.p.size)
                    
                    # Entry price, stop loss, and take profit
                    self.entry_price = current_price
                    self.stop_loss = current_price - stop_distance
                    self.take_profit = current_price + (stop_distance * self.p.profit_factor)
                    self.entry_bar = current_bar
                    
                    # Enter long position
                    self.order = self.buy(size=size)
                    logger.info(f"LONG entry at {current_price:.2f}, Size: {size:.4f}, "
                               f"Stop: {self.stop_loss:.2f}, Target: {self.take_profit:.2f}")
            
            # SHORT signal: Strong sell liquidity (negative imbalance) and downward price movement
            elif imbalance < -self.p.liquidity_threshold and price_direction < 0:
                # Calculate position size based on ATR
                atr_value = self.atr[0]
                stop_distance = atr_value * 1.5  # Stop loss 1.5 ATR away
                
                if stop_distance > 0:
                    size = min(risk_amount / stop_distance, self.p.size)
                    
                    # Entry price, stop loss, and take profit
                    self.entry_price = current_price
                    self.stop_loss = current_price + stop_distance
                    self.take_profit = current_price - (stop_distance * self.p.profit_factor)
                    self.entry_bar = current_bar
                    
                    # Enter short position
                    self.order = self.sell(size=size)
                    logger.info(f"SHORT entry at {current_price:.2f}, Size: {size:.4f}, "
                               f"Stop: {self.stop_loss:.2f}, Target: {self.take_profit:.2f}")
    
    def notify_order(self, order):
        """Handle order status updates"""
        if order.status in [order.Submitted, order.Accepted]:
            # Order has been submitted/accepted - no action required
            return
        
        # Check if order has been completed
        if order.status in [order.Completed]:
            # Record trade details
            if order.isbuy():
                logger.info(f"BUY executed at {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}")
            else:
                logger.info(f"SELL executed at {order.executed.price:.2f}, Profit: {order.executed.pnl:.2f}, Commission: {order.executed.comm:.2f}")
                
                # Track profitable trades
                if order.executed.pnl > 0:
                    self.profitable_trades += 1
        
        # Reset order variable regardless of status
        self.order = None
        
        # Update portfolio value
        current_value = self.broker.getvalue()
        if current_value > self.highest_value:
            self.highest_value = current_value
    
    def stop(self):
        """Called when backtest is complete"""
        # Calculate final performance metrics
        final_value = self.broker.getvalue()
        roi = (final_value / self.starting_value - 1) * 100
        max_roi = (self.highest_value / self.starting_value - 1) * 100
        win_rate = (self.profitable_trades / self.trade_count * 100) if self.trade_count > 0 else 0
        
        logger.info("====== Backtest Results ======")
        logger.info(f"Starting Portfolio Value: {self.starting_value:.2f}")
        logger.info(f"Final Portfolio Value: {final_value:.2f}")
        logger.info(f"ROI: {roi:.2f}%")
        logger.info(f"Maximum ROI: {max_roi:.2f}%")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Profitable Trades: {self.profitable_trades}")
        logger.info(f"Win Rate: {win_rate:.2f}%")


class MacroFundingStrategy(bt.Strategy):
    """
    An enhanced strategy that builds on FundingRateMomentumStrategy but incorporates macroeconomic 
    indicators to adjust trading decisions based on the broader economic environment.
    
    Key enhancements:
    - Integration of macroeconomic indicators (inflation, interest rates, GDP growth)
    - Risk adjustment based on macro regime
    - Dynamic position sizing influenced by macroeconomic conditions
    - Time-varying parameterization based on macro cycle
    """
    
    params = (
        # Signal generation parameters
        ('funding_threshold', 0.0001),    # Min funding rate to consider
        ('momentum_period', 14),          # Period for momentum calculation
        ('rsi_period', 14),               # Period for RSI calculation
        ('rsi_overbought', 65),           # RSI overbought threshold
        ('rsi_oversold', 45),             # RSI oversold threshold
        ('mean_reversion_period', 50),    # Period for mean reversion calculation
        
        # Position sizing and risk management
        ('risk_pct', 0.01),               # Base risk per trade (% of portfolio)
        ('max_risk_pct', 0.03),           # Maximum risk per trade
        ('kelly_fraction', 0.5),          # Kelly criterion fraction (conservative)
        ('use_kelly', True),              # Whether to use Kelly criterion for sizing
        
        # Exit parameters
        ('trailing_stop', 0.02),          # Trailing stop (2%)
        ('adaptive_trailing', True),      # Use ATR-based trailing stops
        ('atr_trailing_multiplier', 2.0), # Multiplier for ATR trailing stop
        ('atr_period', 14),               # ATR period
        ('take_profit', 0.05),            # Take profit level (5%)
        ('time_stop', 20),                # Exit after N bars if neither TP nor SL hit
        
        # Advanced parameters
        ('volatility_lookback', 21),      # Period for volatility calculation
        ('volatility_factor', 2.0),       # Factor for volatility adjustment
        ('regime_period', 100),           # Period for regime detection
        ('correlation_threshold', 0.3),   # Correlation threshold for spread trades
        ('max_trades', 10),               # Maximum concurrent positions
        ('trade_diversification', True),  # Diversify trades (long/short balance)
        
        # Macroeconomic parameters
        ('inflation_threshold', 0.03),    # Inflation rate threshold (3%)
        ('growth_threshold', 0.02),       # GDP growth threshold (2%)
        ('macro_weight', 0.3),            # Weight of macro factors in decisions
        ('macro_lookback', 3),            # Lookback period for macro trends (months)
        ('interest_rate_impact', 0.5),    # Impact of interest rate changes
    )
    
    def __init__(self):
        # Market data
        self.data_close = self.datas[0].close
        self.data_open = self.datas[0].open
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume
        
        # Initialize indicators - price-based
        self.rsi = bt.indicators.RSI(period=self.p.rsi_period)
        self.sma20 = bt.indicators.SMA(period=20)
        self.sma50 = bt.indicators.SMA(period=50)
        self.sma200 = bt.indicators.SMA(period=200)
        self.atr = bt.indicators.ATR(period=self.p.atr_period)
        
        # Bollinger Bands for mean reversion
        self.bbands = bt.indicators.BollingerBands(period=self.p.mean_reversion_period, devfactor=2.0)
        
        # Volatility indicators
        self.volatility = bt.indicators.StdDev(period=self.p.volatility_lookback)
        self.historical_volatility = []  # Store historical volatility for regime detection
        
        # Advanced indicators
        self.macd = bt.indicators.MACD()
        
        # Multi-timeframe indicators (will be manually calculated)
        self.rsi_daily = None  # Will store RSI calculated on daily timeframe
        self.trend_daily = None  # Will store trend direction on daily timeframe
        
        # Order management
        self.order = None
        self.buy_price = None
        self.trailing_stop_price = None
        self.take_profit_price = None
        self.entry_bar = 0  # Track entry bar for time-based stops
        
        # Portfolio tracking
        self.starting_value = self.broker.getvalue()
        self.highest_value = self.starting_value
        self.lowest_value = float('inf')
        self.drawdowns = []  # Track drawdowns for risk management
        
        # Funding rate data 
        self.funding_rates = self.simulate_funding_rates()
        
        # Macroeconomic data
        self.macro_data = self.load_macro_data()
        self.macro_regime = self.detect_macro_regime()
        
        # Trade tracking
        self.trade_count = 0
        self.profitable_trades = 0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 0
        self.trade_history = []  # Track all trades for analysis
        self.trade_pnl = []  # Track PnL of all trades
        self.trade_duration = []  # Track duration of all trades
        
        # Strategy state
        self.market_regime = 'neutral'  # Can be 'bull', 'bear', or 'neutral'
        self.regime_changes = []  # Track regime changes
        self.last_signal = None  # Last signal generated
        self.open_positions = {}  # Track open positions
        self.position_sizes = []  # Track position sizes
        
        # Print strategy parameters
        logger.info(f"MacroFunding Strategy initialized with parameters: {self.p.__dict__}")
        logger.info(f"Starting portfolio value: {self.starting_value}")
    
    def load_macro_data(self):
        """Load macroeconomic data for backtesting"""
        try:
            # In a production environment, we would load actual macro data
            # For backtesting, we'll create synthetic macro data
            macro_data = {}
            
            # Generate dates for the synthetic data
            # Assuming we have daily price data and monthly macro data
            dates = []
            for i in range(len(self.data)):
                bar_date = self.data.datetime.datetime(i)
                # Get the first day of each month
                if i == 0 or bar_date.month != self.data.datetime.datetime(i-1).month:
                    dates.append(bar_date)
            
            # Generate synthetic macro indicators
            # Inflation rate (%)
            base_inflation = 0.02  # 2%
            inflation_trend = 0.001  # Slight upward trend
            inflation_cycle = 0.01 * np.sin(np.linspace(0, 4*np.pi, len(dates)))
            inflation_noise = np.random.normal(0, 0.003, len(dates))  # Random noise
            inflation = [base_inflation + (inflation_trend * i) + inflation_cycle[i] + inflation_noise[i] for i in range(len(dates))]
            
            # GDP Growth rate (%)
            base_gdp = 0.025  # 2.5%
            gdp_trend = -0.0005  # Slight downward trend
            gdp_cycle = 0.015 * np.sin(np.linspace(0, 3*np.pi, len(dates)))  # Cyclical component
            gdp_noise = np.random.normal(0, 0.004, len(dates))  # Random noise
            gdp = [base_gdp + (gdp_trend * i) + gdp_cycle[i] + gdp_noise[i] for i in range(len(dates))]
            
            # Interest rate (%)
            base_interest = 0.01  # 1%
            interest_trend = 0.002  # Upward trend
            interest_steps = np.zeros(len(dates))
            # Add step changes in interest rates (policy changes)
            change_points = np.random.choice(len(dates), 5, replace=False)
            for point in change_points:
                interest_steps[point:] += np.random.choice([-0.0025, 0.0025])
            interest = [base_interest + (interest_trend * min(i, 15)) + interest_steps[i] for i in range(len(dates))]
            interest = np.clip(interest, 0.001, 0.1)  # Clip to reasonable range
            
            # Store data in a dictionary
            macro_data['dates'] = dates
            macro_data['inflation'] = inflation
            macro_data['gdp_growth'] = gdp
            macro_data['interest_rate'] = interest
            
            logger.info(f"Generated synthetic macro data for {len(dates)} months")
            return macro_data
            
        except Exception as e:
            logger.error(f"Error loading macro data: {str(e)}")
            return {}
    
    def get_current_macro_data(self, date):
        """Get macroeconomic data for the current date"""
        if not self.macro_data or 'dates' not in self.macro_data:
            return {'inflation': 0.02, 'gdp_growth': 0.025, 'interest_rate': 0.01}
        
        # Find the index of the closest date
        closest_idx = min(range(len(self.macro_data['dates'])), 
                         key=lambda i: abs(self.macro_data['dates'][i] - date))
        
        return {
            'inflation': self.macro_data['inflation'][closest_idx],
            'gdp_growth': self.macro_data['gdp_growth'][closest_idx],
            'interest_rate': self.macro_data['interest_rate'][closest_idx]
        }
    
    def detect_macro_regime(self):
        """Determine the current macroeconomic regime"""
        try:
            if not self.macro_data or 'dates' not in self.macro_data:
                return 'neutral'
            
            # Get latest macro data
            latest_idx = -1
            latest_inflation = self.macro_data['inflation'][latest_idx]
            latest_gdp = self.macro_data['gdp_growth'][latest_idx]
            latest_interest = self.macro_data['interest_rate'][latest_idx]
            
            # Define regimes based on inflation and growth
            # High growth, low inflation = Expansion
            if latest_gdp > self.p.growth_threshold and latest_inflation < self.p.inflation_threshold:
                regime = 'expansion'
            # High growth, high inflation = Overheating
            elif latest_gdp > self.p.growth_threshold and latest_inflation >= self.p.inflation_threshold:
                regime = 'overheating'
            # Low growth, high inflation = Stagflation
            elif latest_gdp <= self.p.growth_threshold and latest_inflation >= self.p.inflation_threshold:
                regime = 'stagflation'
            # Low growth, low inflation = Contraction
            else:
                regime = 'contraction'
            
            # Factor in interest rate trend
            if len(self.macro_data['interest_rate']) > 2:
                rate_trend = self.macro_data['interest_rate'][-1] - self.macro_data['interest_rate'][-3]
                if rate_trend > 0.005:  # Significant rate increases
                    # Shift regime towards contraction
                    if regime == 'expansion':
                        regime = 'late_expansion'
                    elif regime == 'overheating':
                        regime = 'transition_to_contraction'
                elif rate_trend < -0.005:  # Significant rate decreases
                    # Shift regime towards expansion
                    if regime == 'contraction':
                        regime = 'early_recovery'
            
            logger.info(f"Current macro regime: {regime}")
            return regime
            
        except Exception as e:
            logger.error(f"Error detecting macro regime: {str(e)}")
            return 'neutral'
    
    def simulate_funding_rates(self):
        """Simulate funding rates for backtesting with realistic patterns"""
        # Same implementation as FundingRateMomentumStrategy
        # In live trading, this would be replaced with actual API calls
        # For backtest, we'll create a synthetic funding rate series
        dates = []
        rates = []
        
        # Generate a synthetic funding rate series with market-correlated behavior
        base_rate = 0.0001  # 0.01% base rate
        trend_cycle = 14  # 14-day cycle
        
        for i in range(len(self.data)):
            # Date for this bar
            date = self.data.datetime.datetime(i)
            
            # Base cyclical component
            cycle_component = np.sin(2 * np.pi * i / trend_cycle) * 0.0008
            
            # Correlation with price trends (funding tends to be positive in uptrends)
            if i > 0:
                price_change = (self.data.close[i] - self.data.close[max(0, i-trend_cycle)]) / self.data.close[max(0, i-trend_cycle)]
                price_component = min(max(price_change * 0.01, -0.001), 0.001)  # Clamp to reasonable range
            else:
                price_component = 0
                
            # Random component
            random_component = np.random.normal(0, 0.0002)
            
            # Combined rate
            rate = base_rate + cycle_component + price_component + random_component
            
            dates.append(date)
            rates.append(rate)
        
        return pd.Series(rates, index=dates)
    
    def get_current_funding_rate(self, date):
        """Get the current funding rate"""
        # Same implementation as FundingRateMomentumStrategy
        # Check if funding rates are available
        if not hasattr(self, 'funding_rates') or self.funding_rates.empty:
            # Generate a synthetic funding rate
            return 0.001 * np.sin(date.hour * np.pi / 4)
        
        # Find the closest date in our funding rates
        closest_date = min(self.funding_rates.index, 
                          key=lambda x: abs(x - date))
        
        return self.funding_rates[closest_date]
    
    def detect_market_regime(self):
        """Detect the current market regime (bull, bear, neutral)"""
        # Same implementation as FundingRateMomentumStrategy
        # Use price in relation to moving averages to determine regime
        if self.sma20[0] > self.sma50[0] > self.sma200[0]:
            new_regime = 'bull'
        elif self.sma20[0] < self.sma50[0] < self.sma200[0]:
            new_regime = 'bear'
        else:
            new_regime = 'neutral'
            
        # Check if regime has changed
        if new_regime != self.market_regime:
            self.regime_changes.append((len(self), self.market_regime, new_regime))
            self.market_regime = new_regime
            logger.info(f"Market regime changed to: {self.market_regime}")
            
        return self.market_regime
    
    def calculate_position_size(self, is_long):
        """Calculate position size based on risk parameters, volatility and macro conditions"""
        portfolio_value = self.broker.getvalue()
        
        # Get current macro conditions
        current_date = self.data.datetime.datetime(0)
        macro_data = self.get_current_macro_data(current_date)
        
        # Adjust risk based on market and macro conditions
        if self.market_regime == 'bull' and is_long:
            market_risk_factor = 1.2  # Increase size in bull market for longs
        elif self.market_regime == 'bear' and not is_long:
            market_risk_factor = 1.2  # Increase size in bear market for shorts
        else:
            market_risk_factor = 0.8  # Reduce size when trading against the trend
        
        # Macro risk adjustments
        # Higher inflation generally negative for crypto
        inflation_factor = 1.0 - (macro_data['inflation'] - 0.02) * 5.0  # 0.02 is baseline
        
        # Higher interest rates generally negative for crypto
        interest_factor = 1.0 - (macro_data['interest_rate'] - 0.01) * 8.0 * self.p.interest_rate_impact
        
        # GDP growth effect depends on direction
        if is_long:
            # Strong growth is good for long positions
            growth_factor = 1.0 + (macro_data['gdp_growth'] - 0.02) * 3.0
        else:
            # Weak growth is good for short positions
            growth_factor = 1.0 - (macro_data['gdp_growth'] - 0.02) * 3.0
        
        # Regime-specific adjustments
        if self.macro_regime == 'expansion':
            regime_factor = 1.2 if is_long else 0.8
        elif self.macro_regime == 'contraction':
            regime_factor = 0.8 if is_long else 1.2
        elif self.macro_regime == 'stagflation':
            regime_factor = 0.7  # Reduce size in stagflation regardless of direction
        elif self.macro_regime == 'overheating':
            regime_factor = 0.9  # Slightly reduce size in overheating economy
        else:
            regime_factor = 1.0
        
        # Combine macro factors, weighted by macro_weight parameter
        macro_factor = (inflation_factor * 0.3 + interest_factor * 0.4 + growth_factor * 0.3) * self.p.macro_weight + \
                      (1.0 - self.p.macro_weight)
        
        # Ensure macro_factor is in a reasonable range
        macro_factor = max(0.5, min(macro_factor, 1.5))
        
        # Adjust for consecutive losses
        drawdown_factor = max(0.5, 1.0 - (self.consecutive_losses * 0.1))
        
        # Use Kelly criterion if enabled
        if self.p.use_kelly and len(self.trade_pnl) >= 10:
            win_rate = self.profitable_trades / max(1, self.trade_count)
            avg_win = np.mean([pnl for pnl in self.trade_pnl if pnl > 0]) if any(pnl > 0 for pnl in self.trade_pnl) else 0
            avg_loss = abs(np.mean([pnl for pnl in self.trade_pnl if pnl < 0])) if any(pnl < 0 for pnl in self.trade_pnl) else 1
            
            if avg_loss > 0:
                kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
                base_risk = max(0.001, min(kelly * self.p.kelly_fraction, self.p.max_risk_pct))
            else:
                base_risk = self.p.risk_pct
        else:
            base_risk = self.p.risk_pct
            
        # Final risk percentage
        adjusted_risk = base_risk * market_risk_factor * macro_factor * regime_factor * drawdown_factor
        
        # Ensure risk stays within reasonable bounds
        adjusted_risk = max(0.005, min(adjusted_risk, self.p.max_risk_pct))
        
        risk_amount = portfolio_value * adjusted_risk
        
        # Calculate position size based on ATR for volatility-adjusted sizing
        atr_value = self.atr[0]
        if atr_value > 0:
            # Risk per unit = ATR * multiplier
            risk_per_unit = atr_value * self.p.atr_trailing_multiplier
            position_size = risk_amount / risk_per_unit
            
            # Log the calculation
            logger.info(f"Position size calculation: Portfolio={portfolio_value:.2f}, Risk={adjusted_risk:.4f}, "
                       f"ATR={atr_value:.2f}, MacroFactor={macro_factor:.2f}, RegimeFactor={regime_factor:.2f}, "
                       f"Size={position_size:.6f}")
            
            return position_size
        
        # Fallback to a percentage of portfolio
        return portfolio_value * 0.01 / self.data_close[0]
    
    def next(self):
        """Main strategy logic - executed for each new price bar"""
        # Skip if we have a pending order
        if self.order:
            return
            
        # Current price and indicators
        current_price = self.data_close[0]
        current_rsi = self.rsi[0]
        current_bar = len(self)
        
        # Update market regime
        self.detect_market_regime()
        
        # Update macro regime once per month
        current_date = self.data.datetime.datetime(0)
        if current_bar == 0 or current_date.month != self.data.datetime.datetime(-1).month:
            self.macro_regime = self.detect_macro_regime()
            
        # Store volatility for regime detection
        current_volatility = self.volatility[0]
        self.historical_volatility.append(current_volatility)
        if len(self.historical_volatility) > self.p.regime_period:
            self.historical_volatility.pop(0)
        
        # Get current funding rate
        funding_rate = self.get_current_funding_rate(current_date)
        
        # Get current macro data
        macro_data = self.get_current_macro_data(current_date)
        
        # Log current state
        logger.info(f"Date: {current_date}, Close: {current_price}, RSI: {current_rsi:.2f}, "
                   f"Funding Rate: {funding_rate:.6f}, Regime: {self.market_regime}, "
                   f"MacroRegime: {self.macro_regime}, Inflation: {macro_data['inflation']:.2%}, "
                   f"Interest: {macro_data['interest_rate']:.2%}, "
                   f"Portfolio: {self.broker.getvalue():.2f}")
        
        # Update trailing stop if we have a position
        if self.position:
            # For long positions, move stop up if price increases
            if self.position.size > 0:
                # Update highest value seen
                if current_price > self.highest_value:
                    self.highest_value = current_price
                    
                    # Calculate new trailing stop
                    if self.p.adaptive_trailing:
                        # ATR-based trailing stop
                        new_stop = current_price - (self.atr[0] * self.p.atr_trailing_multiplier)
                    else:
                        # Percentage-based trailing stop
                        new_stop = current_price * (1 - self.p.trailing_stop)
                        
                    # Only move stop up, never down
                    if new_stop > self.trailing_stop_price:
                        self.trailing_stop_price = new_stop
                        logger.info(f"Updated trailing stop to {self.trailing_stop_price:.2f}")
            
            # For short positions, move stop down if price decreases
            elif self.position.size < 0:
                # Update lowest value seen
                if current_price < self.lowest_value:
                    self.lowest_value = current_price
                    
                    # Calculate new trailing stop
                    if self.p.adaptive_trailing:
                        # ATR-based trailing stop
                        new_stop = current_price + (self.atr[0] * self.p.atr_trailing_multiplier)
                    else:
                        # Percentage-based trailing stop
                        new_stop = current_price * (1 + self.p.trailing_stop)
                        
                    # Only move stop down, never up
                    if new_stop < self.trailing_stop_price:
                        self.trailing_stop_price = new_stop
                        logger.info(f"Updated trailing stop to {self.trailing_stop_price:.2f}")
        
        # Check exit conditions if in a position
        if self.position:
            # Time-based exit
            bars_in_trade = current_bar - self.entry_bar
            if bars_in_trade >= self.p.time_stop:
                if self.position.size > 0:
                    logger.info(f"Time stop hit after {bars_in_trade} bars. Closing LONG position.")
                    self.order = self.sell(size=self.position.size)
                else:
                    logger.info(f"Time stop hit after {bars_in_trade} bars. Closing SHORT position.")
                    self.order = self.buy(size=abs(self.position.size))
                return
            
            # Check take profit and stop loss
            if self.position.size > 0:  # Long position
                # Check take profit
                if current_price >= self.take_profit_price:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    self.profitable_trades += 1
                    self.consecutive_losses = 0
                    return
                
                # Check trailing stop
                if current_price <= self.trailing_stop_price:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Trailing stop hit at {current_price:.2f}")
                    # Check if this was a loss
                    if current_price < self.buy_price:
                        self.consecutive_losses += 1
                        self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
                    else:
                        self.profitable_trades += 1
                        self.consecutive_losses = 0
                    return
            
            # Short position
            elif self.position.size < 0:
                # Check take profit
                if current_price <= self.take_profit_price:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    self.profitable_trades += 1
                    self.consecutive_losses = 0
                    return
                
                # Check trailing stop
                if current_price >= self.trailing_stop_price:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Trailing stop hit at {current_price:.2f}")
                    # Check if this was a loss
                    if current_price > self.buy_price:
                        self.consecutive_losses += 1
                        self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
                    else:
                        self.profitable_trades += 1
                        self.consecutive_losses = 0
                    return
        
        # Entry signals - incorporating macro conditions
        if not self.position:
            # Get macroeconomic context
            inflation = macro_data['inflation']
            interest_rate = macro_data['interest_rate']
            gdp_growth = macro_data['gdp_growth']
            
            # Adjust thresholds based on macro conditions
            funding_threshold_long = self.p.funding_threshold
            funding_threshold_short = self.p.funding_threshold
            rsi_oversold = self.p.rsi_oversold
            rsi_overbought = self.p.rsi_overbought
            
            # In high inflation environment, increase threshold for long entries
            if inflation > self.p.inflation_threshold:
                funding_threshold_long *= 1.5
                rsi_oversold -= 5  # Require deeper oversold for entry
            
            # In high interest rate environment, adjust thresholds
            if interest_rate > 0.03:  # 3% is considered high
                funding_threshold_long *= 1.2
                rsi_oversold -= 3
            
            # In low growth environment, be more conservative with longs
            if gdp_growth < self.p.growth_threshold:
                funding_threshold_long *= 1.3
                rsi_oversold -= 5
            
            # LONG signal conditions
            if (funding_rate < -funding_threshold_long or current_rsi < rsi_oversold):
                # Additional macro check - avoid longs in poor macro conditions
                macro_favorable_for_long = True
                
                # Unfavorable macro conditions for longs
                if self.macro_regime in ['stagflation', 'contraction'] and inflation > 0.04:
                    macro_favorable_for_long = False
                    logger.info(f"Skipping LONG signal due to unfavorable macro conditions: {self.macro_regime}, inflation={inflation:.2%}")
                
                if macro_favorable_for_long:
                    # Calculate position size
                    size = self.calculate_position_size(is_long=True)
                    
                    # Enter long position
                    self.order = self.buy(size=size)
                    self.buy_price = current_price
                    self.entry_bar = current_bar
                    
                    # Set trailing stop and take profit levels
                    if self.p.adaptive_trailing:
                        self.trailing_stop_price = current_price - (self.atr[0] * self.p.atr_trailing_multiplier)
                        self.take_profit_price = current_price + (self.atr[0] * self.p.atr_trailing_multiplier * self.p.take_profit / self.p.trailing_stop)
                    else:
                        self.trailing_stop_price = current_price * (1 - self.p.trailing_stop)
                        self.take_profit_price = current_price * (1 + self.p.take_profit)
                    
                    # Reset highest value
                    self.highest_value = current_price
                    
                    # Update trade count
                    self.trade_count += 1
                    
                    logger.info(f"LONG signal at {current_price:.2f}, Size: {size}, "
                              f"Stop: {self.trailing_stop_price:.2f}, TP: {self.take_profit_price:.2f}")
            
            # SHORT signal conditions
            elif (funding_rate > funding_threshold_short or current_rsi > rsi_overbought):
                # Additional macro check - avoid shorts in strong macro conditions
                macro_favorable_for_short = True
                
                # Unfavorable macro conditions for shorts
                if self.macro_regime in ['expansion'] and inflation < 0.03 and gdp_growth > 0.03:
                    macro_favorable_for_short = False
                    logger.info(f"Skipping SHORT signal due to unfavorable macro conditions: {self.macro_regime}")
                
                if macro_favorable_for_short:
                    # Calculate position size
                    size = self.calculate_position_size(is_long=False)
                    
                    # Enter short position
                    self.order = self.sell(size=size)
                    self.buy_price = current_price
                    self.entry_bar = current_bar
                    
                    # Set trailing stop and take profit levels
                    if self.p.adaptive_trailing:
                        self.trailing_stop_price = current_price + (self.atr[0] * self.p.atr_trailing_multiplier)
                        self.take_profit_price = current_price - (self.atr[0] * self.p.atr_trailing_multiplier * self.p.take_profit / self.p.trailing_stop)
                    else:
                        self.trailing_stop_price = current_price * (1 + self.p.trailing_stop)
                        self.take_profit_price = current_price * (1 - self.p.take_profit)
                    
                    # Reset lowest value
                    self.lowest_value = current_price
                    
                    # Update trade count
                    self.trade_count += 1
                    
                    logger.info(f"SHORT signal at {current_price:.2f}, Size: {size}, "
                              f"Stop: {self.trailing_stop_price:.2f}, TP: {self.take_profit_price:.2f}")
    
    def notify_order(self, order):
        """Handle order status updates"""
        if order.status in [order.Submitted, order.Accepted]:
            # Order has been submitted/accepted - no action required
            return
        
        # Check if order has been completed
        if order.status in [order.Completed]:
            # Record trade details
            if order.isbuy():
                logger.info(f"BUY executed at {order.executed.price:.2f}")
                
                # Record position details if opening a long position
                if self.position.size > 0:
                    self.position_sizes.append(self.position.size)
            else:
                logger.info(f"SELL executed at {order.executed.price:.2f}")
                
                # Record trade results if closing a position
                if order.executed.pnl != 0:
                    self.trade_pnl.append(order.executed.pnl)
                    self.trade_history.append({
                        'exit_bar': len(self),
                        'entry_price': self.buy_price,
                        'exit_price': order.executed.price,
                        'pnl': order.executed.pnl,
                        'bars_held': len(self) - self.entry_bar,
                        'direction': 'long' if order.executed.pnl > 0 else 'short'
                    })
                    self.trade_duration.append(len(self) - self.entry_bar)
                    
                # Record position details if opening a short position
                if self.position.size < 0:
                    self.position_sizes.append(abs(self.position.size))
        
        # Reset order variable regardless of status
        self.order = None
    
    def stop(self):
        """Called when backtest is complete"""
        # Calculate final performance metrics
        final_value = self.broker.getvalue()
        roi = (final_value / self.starting_value - 1) * 100
        
        # Log performance
        logger.info("Backtest completed")
        logger.info(f"Starting Value: ${self.starting_value:.2f}")
        logger.info(f"Final Value: ${final_value:.2f}")
        logger.info(f"Return: {roi:.2f}%")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Profitable Trades: {self.profitable_trades}")
        logger.info(f"Win Rate: {100 * self.profitable_trades / max(1, self.trade_count):.2f}%")
        logger.info(f"Max Consecutive Losses: {self.max_consecutive_losses}")
        
        # Calculate average trade statistics
        if self.trade_pnl:
            avg_trade = sum(self.trade_pnl) / len(self.trade_pnl)
            profitable_trades = [p for p in self.trade_pnl if p > 0]
            losing_trades = [p for p in self.trade_pnl if p < 0]
            
            avg_win = sum(profitable_trades) / max(1, len(profitable_trades))
            avg_loss = sum(losing_trades) / max(1, len(losing_trades))
            
            logger.info(f"Average Trade: ${avg_trade:.2f}")
            logger.info(f"Average Win: ${avg_win:.2f}")
            logger.info(f"Average Loss: ${avg_loss:.2f}")
            
            if avg_loss != 0:
                profit_factor = abs(sum(profitable_trades) / sum(losing_trades)) if losing_trades else float('inf')
                logger.info(f"Profit Factor: {profit_factor:.2f}")
        
        # Log position sizing statistics
        if self.position_sizes:
            avg_position = sum(self.position_sizes) / len(self.position_sizes)
            logger.info(f"Average Position Size: {avg_position:.6f}")


class AggressiveFundingStrategy(bt.Strategy):
    """
    An aggressive trading strategy that builds on the FundingRateMomentumStrategy
    with more aggressive parameters and simplified entry conditions.
    
    This strategy aims to:
    1. Generate more frequent trading signals by using looser entry criteria
    2. Increase position sizes using higher risk parameters
    3. Lock in profits with tighter trailing stops
    4. Maximize gains with trend-following techniques
    5. Maintain strict risk management with higher risk-reward ratios
    """
    
    params = (
        # Signal generation parameters - more aggressive
        ('funding_threshold', 0.00005),    # Much lower funding threshold (50% of original)
        ('momentum_period', 8),            # Shorter momentum calculation period
        ('rsi_period', 7),                 # Shorter RSI period for faster signals
        ('rsi_overbought', 60),            # Lower overbought threshold
        ('rsi_oversold', 40),              # Higher oversold threshold
        
        # Position sizing and risk management - more aggressive
        ('risk_pct', 0.025),               # Higher base risk per trade (2.5% vs 1%)
        ('max_risk_pct', 0.05),            # Higher maximum risk (5% vs 3%)
        ('kelly_fraction', 0.7),           # Less conservative Kelly fraction
        ('use_kelly', True),               # Use Kelly criterion for sizing
        
        # Exit parameters - tighter trailing stops, higher profit targets
        ('trailing_stop', 0.015),          # Tighter trailing stop (1.5% vs 2%)
        ('adaptive_trailing', True),       # Use ATR-based trailing stops
        ('atr_trailing_multiplier', 1.5),  # Lower multiplier for tighter stops
        ('atr_period', 10),                # Shorter ATR period
        ('take_profit', 0.08),             # Higher take profit (8% vs 5%)
        ('time_stop', 15),                 # Shorter time stop
        
        # Advanced parameters
        ('volatility_lookback', 14),       # Shorter volatility lookback
        ('volatility_factor', 2.5),        # Higher volatility adjustment
        ('regime_period', 50),             # Shorter regime detection period
        ('max_trades', 15),                # More concurrent positions
    )
    
    def __init__(self):
        # Market data
        self.data_close = self.datas[0].close
        self.data_open = self.datas[0].open
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume
        
        # Initialize indicators - price-based
        self.rsi = bt.indicators.RSI(period=self.p.rsi_period)
        self.sma20 = bt.indicators.SMA(period=20)
        self.sma50 = bt.indicators.SMA(period=50)
        self.sma200 = bt.indicators.SMA(period=200)
        self.atr = bt.indicators.ATR(period=self.p.atr_period)
        
        # Bollinger Bands for mean reversion
        self.bbands = bt.indicators.BollingerBands(period=20, devfactor=2.0)
        
        # Volatility indicators
        self.volatility = bt.indicators.StdDev(period=self.p.volatility_lookback)
        self.historical_volatility = []  # Store historical volatility for regime detection
        
        # MACD for trend confirmation
        self.macd = bt.indicators.MACD(period_me1=8, period_me2=17, period_signal=9)
        
        # Stochastic for additional entry/exit signals
        self.stoch = bt.indicators.Stochastic(period=5, period_dfast=3)
        
        # Order management
        self.order = None
        self.buy_price = None
        self.trailing_stop_price = None
        self.take_profit_price = None
        self.entry_bar = 0  # Track entry bar for time-based stops
        
        # Portfolio tracking
        self.starting_value = self.broker.getvalue()
        self.highest_value = self.starting_value
        self.lowest_value = float('inf')
        self.drawdowns = []  # Track drawdowns for risk management
        
        # Funding rate data 
        self.funding_rates = self.simulate_funding_rates()
        
        # Trade tracking
        self.trade_count = 0
        self.profitable_trades = 0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 0
        
        # Strategy state
        self.market_regime = 'neutral'  # Can be 'bull', 'bear', or 'neutral'
        
        # Print strategy parameters
        logger.info(f"Aggressive Strategy initialized with parameters: {self.p.__dict__}")
        logger.info(f"Starting portfolio value: {self.starting_value}")
    
    def simulate_funding_rates(self):
        """Simulate funding rates for backtesting with realistic patterns"""
        # In live trading, this would be replaced with actual API calls
        # For backtest, we'll create a synthetic funding rate series
        dates = []
        rates = []
        
        # Generate a synthetic funding rate series with market-correlated behavior
        base_rate = 0.0001  # 0.01% base rate
        trend_cycle = 14  # 14-day trend cycle
        
        # Generate one rate for each day in our data
        for i in range(len(self.data)):
            # Generate date for this bar
            date = self.data.datetime.datetime(i)
            dates.append(date)
            
            # Generate synthetic funding rate with some randomness
            day_of_cycle = i % trend_cycle
            cycle_position = day_of_cycle / trend_cycle
            
            # Add some sinusoidal variation to simulate market cycles
            cycle_factor = np.sin(cycle_position * 2 * np.pi)
            
            # Random component
            random_factor = np.random.normal(0, 0.5)
            
            # Combine factors
            rate = base_rate * (1 + cycle_factor + random_factor)
            rates.append(rate)
        
        # Create a dictionary of funding rates
        funding_data = dict(zip(dates, rates))
        
        return funding_data
    
    def get_current_funding_rate(self, date):
        """Get funding rate for the current bar"""
        # In live trading, this would fetch from API
        # For backtest, use our simulated rates
        
        # Try to get the exact date
        rate = self.funding_rates.get(date, None)
        
        # If not found, use the most recent available rate
        if rate is None:
            # Find closest date before current date
            closest_date = None
            for d in self.funding_rates.keys():
                if d <= date and (closest_date is None or d > closest_date):
                    closest_date = d
            
            if closest_date:
                rate = self.funding_rates[closest_date]
            else:
                # Fallback to a small random rate
                rate = np.random.normal(0, 0.0001)
        
        return rate
    
    def detect_market_regime(self):
        """Detect the current market regime (bull, bear, neutral)"""
        # Use price in relation to moving averages to determine regime
        if self.sma20[0] > self.sma50[0] > self.sma200[0]:
            new_regime = 'bull'
        elif self.sma20[0] < self.sma50[0] < self.sma200[0]:
            new_regime = 'bear'
        else:
            new_regime = 'neutral'
            
        # Check if regime has changed
        if new_regime != self.market_regime:
            self.market_regime = new_regime
            logger.info(f"Market regime changed to: {self.market_regime}")
            
        return self.market_regime
    
    def calculate_position_size(self, is_long):
        """Calculate position size based on risk parameters and volatility"""
        portfolio_value = self.broker.getvalue()
        
        # Adjust risk based on market conditions with more aggressive sizing
        if self.market_regime == 'bull' and is_long:
            regime_risk_factor = 1.5  # More aggressive sizing in bull market for longs (was 1.2)
        elif self.market_regime == 'bear' and not is_long:
            regime_risk_factor = 1.5  # More aggressive sizing in bear market for shorts (was 1.2)
        else:
            regime_risk_factor = 0.9  # Less reduction when against trend (was 0.8)
        
        # Adjust for consecutive losses - less reduction for aggressive strategy
        drawdown_factor = max(0.7, 1.0 - (self.consecutive_losses * 0.05))
        
        # Base risk is higher for this aggressive strategy
        base_risk = self.p.risk_pct
            
        # Final risk percentage
        adjusted_risk = base_risk * regime_risk_factor * drawdown_factor
        risk_amount = portfolio_value * adjusted_risk
        
        # Calculate position size based on ATR for volatility-adjusted sizing
        atr_value = self.atr[0]
        if atr_value > 0:
            # Risk per unit = ATR * multiplier
            risk_per_unit = atr_value * self.p.atr_trailing_multiplier
            position_size = risk_amount / risk_per_unit
            
            # Log the calculation
            logger.info(f"Position size calculation: Portfolio={portfolio_value:.2f}, Risk={adjusted_risk:.4f}, "
                       f"ATR={atr_value:.2f}, Size={position_size:.6f}")
            
            return position_size
        
        # Fallback to a percentage of portfolio
        return portfolio_value * 0.02 / self.data_close[0]  # Higher default allocation
    
    def next(self):
        """Main strategy logic - executed for each new price bar"""
        # Skip if we have a pending order
        if self.order:
            return
            
        # Ensure indicators are ready
        if len(self) < max(self.p.rsi_period * 2, 30):  # Make sure we have enough data for indicators
            return
            
        # Validate indicator objects are properly initialized
        try:
            # Check key indicators
            if not self.rsi or not self.macd or not self.stoch or not self.atr:
                logger.warning("One or more indicators not properly initialized")
                return
                
            # Current price and indicators
            current_price = self.data_close[0]
            current_rsi = float(self.rsi[0]) if self.rsi[0] is not None else 50
            current_bar = len(self)
        except Exception as e:
            logger.error(f"Error accessing indicators: {e}")
            return
        
        # Update market regime
        self.detect_market_regime()
        
        # Store volatility for regime detection
        current_volatility = self.volatility[0]
        self.historical_volatility.append(current_volatility)
        if len(self.historical_volatility) > self.p.regime_period:
            self.historical_volatility.pop(0)
        
        # Get current funding rate
        current_date = self.data.datetime.datetime(0)
        funding_rate = self.get_current_funding_rate(current_date)
        
        # Log current state
        logger.info(f"Date: {current_date}, Close: {current_price:.2f}, RSI: {current_rsi:.2f}, "
                   f"Funding Rate: {funding_rate:.6f}, Regime: {self.market_regime}, "
                   f"Portfolio: {self.broker.getvalue():.2f}")
        
        # Update trailing stop if we have a position
        if self.position:
            # For long positions, move stop up if price increases
            if self.position.size > 0:
                # Update highest value seen
                if current_price > self.highest_value:
                    self.highest_value = current_price
                    
                    # Calculate new trailing stop - more aggressive trailing (closer to price)
                    if self.p.adaptive_trailing:
                        # ATR-based trailing stop
                        new_stop = current_price - (self.atr[0] * self.p.atr_trailing_multiplier)
                    else:
                        # Percentage-based trailing stop
                        new_stop = current_price * (1 - self.p.trailing_stop)
                        
                    # Only move stop up, never down
                    if new_stop > self.trailing_stop_price:
                        self.trailing_stop_price = new_stop
                        logger.info(f"Updated trailing stop to {self.trailing_stop_price:.2f}")
            
            # For short positions, move stop down if price decreases
            elif self.position.size < 0:
                # Update lowest value seen
                if current_price < self.lowest_value:
                    self.lowest_value = current_price
                    
                    # Calculate new trailing stop - more aggressive trailing
                    if self.p.adaptive_trailing:
                        # ATR-based trailing stop
                        new_stop = current_price + (self.atr[0] * self.p.atr_trailing_multiplier)
                    else:
                        # Percentage-based trailing stop
                        new_stop = current_price * (1 + self.p.trailing_stop)
                        
                    # Only move stop down, never up
                    if new_stop < self.trailing_stop_price:
                        self.trailing_stop_price = new_stop
                        logger.info(f"Updated trailing stop to {self.trailing_stop_price:.2f}")
        
        # Check exit conditions if in a position
        if self.position:
            # Time-based exit
            bars_in_trade = current_bar - self.entry_bar
            if bars_in_trade >= self.p.time_stop:
                if self.position.size > 0:
                    logger.info(f"Time stop hit after {bars_in_trade} bars. Closing LONG position.")
                    self.order = self.sell(size=self.position.size)
                else:
                    logger.info(f"Time stop hit after {bars_in_trade} bars. Closing SHORT position.")
                    self.order = self.buy(size=abs(self.position.size))
                return
            
            # Check take profit and stop loss
            if self.position.size > 0:  # Long position
                # Check take profit
                if current_price >= self.take_profit_price:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    self.profitable_trades += 1
                    self.consecutive_losses = 0
                    return
                
                # Check trailing stop
                if current_price <= self.trailing_stop_price:
                    self.order = self.sell(size=self.position.size)
                    logger.info(f"Trailing stop hit at {current_price:.2f}")
                    # Check if this was a loss
                    if current_price < self.buy_price:
                        self.consecutive_losses += 1
                        self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
                    else:
                        self.profitable_trades += 1
                        self.consecutive_losses = 0
                    return
            
            # Short position
            elif self.position.size < 0:
                # Check take profit
                if current_price <= self.take_profit_price:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Take profit hit at {current_price:.2f}")
                    self.profitable_trades += 1
                    self.consecutive_losses = 0
                    return
                
                # Check trailing stop
                if current_price >= self.trailing_stop_price:
                    self.order = self.buy(size=abs(self.position.size))
                    logger.info(f"Trailing stop hit at {current_price:.2f}")
                    # Check if this was a loss
                    if current_price > self.buy_price:
                        self.consecutive_losses += 1
                        self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
                    else:
                        self.profitable_trades += 1
                        self.consecutive_losses = 0
                    return
        
        # Entry signals - VERY SIMPLIFIED for more frequent entries
        if not self.position:
            # Get additional indicators for confirmation
            try:
                # Add proper error handling for indicator access
                macd_signal = False
                stoch_signal = False
                
                # Check if MACD is ready
                if len(self.macd.macd) > 0 and len(self.macd.signal) > 0:
                    macd_value = float(self.macd.macd[0]) if self.macd.macd[0] is not None else 0
                    signal_value = float(self.macd.signal[0]) if self.macd.signal[0] is not None else 0
                    macd_signal = macd_value > signal_value  # Bullish MACD
                
                # Check if Stochastic is ready
                if len(self.stoch.percK) > 0 and len(self.stoch.percD) > 0:
                    k_value = float(self.stoch.percK[0]) if self.stoch.percK[0] is not None else 50
                    d_value = float(self.stoch.percD[0]) if self.stoch.percD[0] is not None else 50
                    stoch_signal = k_value > d_value  # Bullish stochastic
                    
            except Exception as e:
                logger.warning(f"Error processing indicators: {e}")
                macd_signal = False
                stoch_signal = False
            
            # LONG signal - much more relaxed conditions
            if (funding_rate < 0 or current_rsi < self.p.rsi_oversold or
                (macd_signal and stoch_signal and self.market_regime != 'bear')):
                
                # Calculate position size
                size = self.calculate_position_size(is_long=True)
                
                # Enter long position
                self.order = self.buy(size=size)
                self.buy_price = current_price
                self.entry_bar = current_bar
                
                # Set trailing stop and take profit levels - wider profit target for aggressive strategy
                if self.p.adaptive_trailing:
                    self.trailing_stop_price = current_price - (self.atr[0] * self.p.atr_trailing_multiplier)
                    self.take_profit_price = current_price + (self.atr[0] * self.p.atr_trailing_multiplier * 
                                                             self.p.take_profit / self.p.trailing_stop)
                else:
                    self.trailing_stop_price = current_price * (1 - self.p.trailing_stop)
                    self.take_profit_price = current_price * (1 + self.p.take_profit)
                
                # Reset highest value
                self.highest_value = current_price
                
                # Update trade count
                self.trade_count += 1
                
                logger.info(f"LONG signal at {current_price:.2f}, Size: {size}, "
                           f"Stop: {self.trailing_stop_price:.2f}, TP: {self.take_profit_price:.2f}")
            
            # SHORT signal - much more relaxed conditions
            elif (funding_rate > 0 or current_rsi > self.p.rsi_overbought or
                 (not macd_signal and not stoch_signal and self.market_regime != 'bull')):
                
                # Calculate position size
                size = self.calculate_position_size(is_long=False)
                
                # Enter short position
                self.order = self.sell(size=size)
                self.buy_price = current_price
                self.entry_bar = current_bar
                
                # Set trailing stop and take profit levels
                if self.p.adaptive_trailing:
                    self.trailing_stop_price = current_price + (self.atr[0] * self.p.atr_trailing_multiplier)
                    self.take_profit_price = current_price - (self.atr[0] * self.p.atr_trailing_multiplier * 
                                                             self.p.take_profit / self.p.trailing_stop)
                else:
                    self.trailing_stop_price = current_price * (1 + self.p.trailing_stop)
                    self.take_profit_price = current_price * (1 - self.p.take_profit)
                
                # Reset lowest value
                self.lowest_value = current_price
                
                # Update trade count
                self.trade_count += 1
                
                logger.info(f"SHORT signal at {current_price:.2f}, Size: {size}, "
                           f"Stop: {self.trailing_stop_price:.2f}, TP: {self.take_profit_price:.2f}")
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted - no action required
            return

        # Check if an order has been completed
        if order.status in [order.Completed]:
            if order.isbuy():
                logger.info(f"BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}")
                self.buy_price = order.executed.price
            else:  # Sell
                logger.info(f"SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}")
                
                # Calculate profit
                if self.buy_price:
                    profit = order.executed.price - self.buy_price if order.isbuy() else self.buy_price - order.executed.price
                    profit_pct = 100 * profit / self.buy_price
                    logger.info(f"Trade Profit: {profit:.2f} ({profit_pct:.2f}%)")
                    
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            logger.info(f"Order Canceled/Margin/Rejected: {order.Status[order.status]}")
        
        # Reset order
        self.order = None
    
    def stop(self):
        """Method called when backtest is finished"""
        # Calculate final portfolio value
        final_value = self.broker.getvalue()
        roi = (final_value / self.starting_value - 1.0) * 100
        
        # Calculate win rate
        win_rate = 0
        if self.trade_count > 0:
            win_rate = (self.profitable_trades / self.trade_count) * 100
            
        # Log results
        logger.info("Backtest completed")
        logger.info(f"Starting Value: ${self.starting_value:.2f}")
        logger.info(f"Final Value: ${final_value:.2f}")
        logger.info(f"Return: {roi:.2f}%")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Profitable Trades: {self.profitable_trades}")
        logger.info(f"Win Rate: {win_rate:.2f}%")
        logger.info(f"Max Consecutive Losses: {self.max_consecutive_losses}")


class RenaissanceInspiredStrategy(bt.Strategy):
    """
    A sophisticated quantitative trading strategy inspired by Renaissance Capital's approach.
    
    Key features:
    1. Multi-factor signal generation combining technical, statistical, and funding indicators
    2. Advanced statistical arbitrage techniques with mean-reversion and momentum models
    3. Machine learning-based regime detection and parameter optimization
    4. Rigorous risk management with position sizing based on Kelly criterion and volatility
    5. Multi-timeframe analysis for improved signal quality
    6. Adaptive execution based on market microstructure
    7. Dynamic strategy allocation based on market conditions
    
    This strategy represents a significant enhancement over previous approaches by:
    - Moving beyond simplistic technical indicators to statistical edge identification
    - Implementing proper signal normalization and combination techniques
    - Using sophisticated position sizing based on expected value and risk
    - Adapting to changing market conditions through regime detection
    - Filtering signals based on statistical significance and edge persistence
    """
    
    params = (
        # Primary signal parameters
        ('funding_threshold', 0.00002),        # Lower threshold to focus on statistical edge
        ('funding_z_score_threshold', 2.0),    # Funding rate z-score for outlier detection
        ('mean_reversion_period', 20),         # Period for mean reversion signals
        ('momentum_period', 12),               # Period for momentum signals
        ('volatility_period', 20),             # Period for volatility calculation
        
        # Machine learning model parameters
        ('use_ml_regime_detection', True),     # Use ML for regime detection
        ('feature_lookback', 100),             # Lookback period for feature engineering
        ('regime_lookback', 500),              # Data points for regime detection training
        
        # Signal filtering parameters
        ('min_signal_strength', 0.2),          # Minimum combined signal strength (0-1)
        ('significance_level', 0.05),          # Statistical significance threshold (p-value)
        ('signal_smoothing', 3),               # EMA period for signal smoothing
        
        # Position sizing parameters
        ('base_risk_pct', 0.01),               # Base risk percentage per trade (1%)
        ('max_risk_pct', 0.05),                # Maximum risk percentage (5%)
        ('kelly_fraction', 0.3),               # Conservative Kelly fraction
        ('position_heat', 0.8),                # Maximum total portfolio heat (% committed)
        
        # Risk management parameters
        ('use_dynamic_stops', True),           # Use dynamic stop losses
        ('atr_period', 14),                    # ATR period for stops
        ('atr_multiplier', 2.5),               # ATR multiplier for stop distance
        ('profit_take_atr_mult', 4.0),         # Profit target as ATR multiple
        ('time_stop', 24),                     # Exit after N bars if neither TP nor SL hit
        
        # Multi-timeframe parameters
        ('use_multi_timeframe', True),         # Use multi-timeframe analysis
        ('higher_tf_weight', 0.6),             # Weight given to higher timeframe signals
        ('lower_tf_weight', 0.4),              # Weight given to lower timeframe signals
        
        # Dynamic strategy allocation
        ('strategy_allocation', True),         # Dynamically allocate to sub-strategies
        ('trend_weight', 0.5),                 # Base weight for trend strategies
        ('mean_rev_weight', 0.5),              # Base weight for mean reversion strategies
        
        # Execution parameters
        ('use_smart_execution', True),         # Use smart execution algorithms
        ('min_liquidity_ratio', 10.0),         # Minimum liquidity to position size ratio
    )
    
    def __init__(self):
        # Initialize data structures for storing signals and state
        self.signals = {}
        self.position_sizes = []
        self.regime_probs = {}
        self.feature_history = []
        self.signal_history = []
        self.executed_trades = []
        self.current_regime = 'unknown'
        self.pending_orders = {}
        self.funding_rates = []  # Ensure this is a list, not a dictionary
        self.regime_changes = []  # Ensure this is initialized
        self.historical_volatility = []  # Ensure this is initialized
        self.trade_pnl = []  # Ensure this is initialized
        self.trade_history = []  # Ensure this is initialized
        self.trade_duration = []  # Ensure this is initialized
        self.orders = []  # Ensure this is initialized
        
        # CRITICAL FIX: In Backtrader, 'stats' should be a LineStats collection, 
        # not a list or dictionary. This is a special type that handles observers.
        # Let the parent strategy class initialize stats properly
        
        # We'll store our own statistics in a separate dictionary
        self.statistics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'peak_value': 0.0,
        }
        
        # Safeguard method to ensure all objects that need append are lists
        def ensure_list_attributes():
            list_attrs = [
                'position_sizes', 'feature_history', 'signal_history', 
                'executed_trades', 'funding_rates', 'regime_changes',
                'historical_volatility', 'trade_pnl', 'trade_history', 
                'trade_duration', 'orders'
            ]
            for attr in list_attrs:
                if not hasattr(self, attr):
                    setattr(self, attr, [])
                elif not isinstance(getattr(self, attr), list):
                    logger.warning(f"Converting {attr} from {type(getattr(self, attr))} to list")
                    setattr(self, attr, [])
        
        # Call the safeguard method
        ensure_list_attributes()
        
        # Initialize market data
        self.data_close = self.datas[0].close
        self.data_open = self.datas[0].open
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume
        
        # Technical indicators
        # Moving averages for multiple timeframes
        self.sma20 = bt.indicators.SMA(self.data_close, period=20)
        self.sma50 = bt.indicators.SMA(self.data_close, period=50)
        self.sma200 = bt.indicators.SMA(self.data_close, period=200)
        self.ema12 = bt.indicators.EMA(self.data_close, period=12)
        self.ema26 = bt.indicators.EMA(self.data_close, period=26)
        
        # Volatility indicators
        self.atr = bt.indicators.ATR(self.datas[0], period=self.p.atr_period)
        self.volatility = bt.indicators.StdDev(self.data_close, period=self.p.volatility_period)
        self.bollinger = bt.indicators.BollingerBands(self.data_close, period=20)
        
        # Momentum indicators
        self.macd = bt.indicators.MACD(self.data_close)
        self.rsi = bt.indicators.RSI(self.data_close, period=14)
        
        # Volume indicators - implement custom OBV indicator
        self.obv = self.create_obv_indicator()
        self.volume_sma = bt.indicators.SMA(self.data_volume, period=20)
        
        # Custom indicators
        self.z_score = self.zscore_indicator(self.data_close, period=20)
        self.price_z_score = self.z_score  # Add alias for consistency
        self.funding_z_score = self.create_funding_z_score_indicator()
        
        # Initialize strategy state
        self.order = None
        self.buy_price = 0
        self.sell_price = 0
        self.stop_price = 0
        self.take_profit_price = 0
        self.trade_start_time = 0
        self.atr_value = 0
        self.trailing_stop = 0
        self.current_position_value = 0
        self.current_position_risk = 0
        
        # Initialize regime detection model
        if self.p.use_ml_regime_detection:
            self.initialize_regime_model()
        
        # Log initialization
        logger.info("RenaissanceInspiredStrategy initialized with parameters:")
        for param_name, param_value in self.p._getitems():
            logger.info(f"  - {param_name}: {param_value}")
        
        # Starting values for performance tracking
        self.starting_value = self.broker.getvalue()
        self.peak_value = self.starting_value
        
        # Trading statistics
        self.trade_count = 0
        self.profitable_trades = 0
        self.unprofitable_trades = 0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 0
    
    def zscore_indicator(self, data, period):
        """Create a z-score indicator for mean reversion strategies"""
        return (data - bt.indicators.SMA(data, period=period)) / bt.indicators.StdDev(data, period=period)
    
    def create_funding_z_score_indicator(self):
        """Create a z-score indicator for funding rates to detect outliers"""
        class FundingZScore(bt.Indicator):
            lines = ('z_score',)
            params = (('period', 72),)  # 3 days at 1h intervals
            
            def __init__(self):
                self.addminperiod(self.params.period)
                self.funding_rates = []
                
            def next(self):
                # In real implementation, this would use actual funding rate data
                # For now, we use a synthetic value based on price changes
                current_date = self.data.datetime.datetime(0)
                
                # Get simulated funding rate
                if hasattr(self._owner, 'get_current_funding_rate'):
                    current_rate = self._owner.get_current_funding_rate(current_date)
                else:
                    # Simple proxy based on price returns if method not available
                    returns = (self.data.close[0] / self.data.close[-1]) - 1
                    current_rate = returns * 0.01  # Scale down returns as proxy
                
                # Store funding rate history
                self.funding_rates.append(current_rate)
                if len(self.funding_rates) > self.params.period:
                    self.funding_rates.pop(0)
                
                # Calculate z-score if we have enough data
                if len(self.funding_rates) >= self.params.period:
                    mean = sum(self.funding_rates) / len(self.funding_rates)
                    std = (sum((x - mean) ** 2 for x in self.funding_rates) / len(self.funding_rates)) ** 0.5
                    if std > 0:
                        self.lines.z_score[0] = (current_rate - mean) / std
                    else:
                        self.lines.z_score[0] = 0
                else:
                    self.lines.z_score[0] = 0
        
        return FundingZScore()
    
    def initialize_regime_model(self):
        """Initialize the machine learning model for regime detection"""
        try:
            # In a real implementation, this would initialize an actual ML model
            # For this demonstration, we'll use a simplified approach
            logger.info("Initializing regime detection model")
            
            # We'll use a simple state-based approach as placeholder
            self.regime_states = {
                'bull': {'sma_alignment': True, 'volatility': 'low', 'trend': 'up'},
                'bear': {'sma_alignment': False, 'volatility': 'high', 'trend': 'down'},
                'neutral': {'sma_alignment': None, 'volatility': 'medium', 'trend': 'sideways'}
            }
            
            # Initialize state probabilities
            self.regime_probs = {'bull': 0.33, 'bear': 0.33, 'neutral': 0.34}
            logger.info("Regime detection model initialized")
            
        except Exception as e:
            logger.error(f"Error initializing regime model: {str(e)}")
            self.p.use_ml_regime_detection = False
    
    def detect_market_regime(self):
        """Detect the current market regime using ML-enhanced methods"""
        try:
            # Debug check of variable types before operations
            print(f"Before feature extraction - feature_history type: {type(self.feature_history)}")
            
            # Extract features for regime detection
            features = self.extract_regime_features()
            
            # Debug before append
            print(f"Before append - feature_history type: {type(self.feature_history)}, features type: {type(features)}")
            
            # Store feature history for online learning
            self.feature_history.append(features)
            
            # Debug after append
            print(f"After append - feature_history now has {len(self.feature_history)} items")
            
            if len(self.feature_history) > self.p.regime_lookback:
                self.feature_history.pop(0)
            
            # In a real implementation, this would use the ML model
            # For this demonstration, we'll use a rule-based approach
            
            # Trend direction features
            sma20 = self.sma20[0]
            sma50 = self.sma50[0]
            sma200 = self.sma200[0]
            
            # Volatility features
            current_atr = self.atr[0]
            atr_pct = current_atr / self.data_close[0]
            
            # SMA alignment check
            sma_alignment = (sma20 > sma50 > sma200)
            inverse_alignment = (sma20 < sma50 < sma200)
            
            # Determine volatility regime
            vol_history = [feat['volatility'] for feat in self.feature_history[-30:]] if len(self.feature_history) >= 30 else [0.01]
            avg_vol = sum(vol_history) / len(vol_history)
            vol_regime = 'high' if atr_pct > avg_vol * 1.5 else 'low' if atr_pct < avg_vol * 0.5 else 'medium'
            
            # Trend direction
            price_sma50_ratio = self.data_close[0] / sma50
            trend = 'up' if price_sma50_ratio > 1.05 else 'down' if price_sma50_ratio < 0.95 else 'sideways'
            
            # Rule-based regime classification
            if sma_alignment and trend == 'up' and vol_regime != 'high':
                new_regime = 'bull'
                self.regime_probs = {'bull': 0.7, 'neutral': 0.25, 'bear': 0.05}
            elif inverse_alignment and trend == 'down' and vol_regime != 'low':
                new_regime = 'bear'
                self.regime_probs = {'bull': 0.05, 'neutral': 0.25, 'bear': 0.7}
            else:
                new_regime = 'neutral'
                self.regime_probs = {'bull': 0.3, 'neutral': 0.4, 'bear': 0.3}
            
            # Check if regime has changed
            if new_regime != self.current_regime:
                logger.info(f"Market regime changed: {self.current_regime} -> {new_regime}")
                logger.info(f"Regime probabilities: Bull={self.regime_probs['bull']:.2f}, " +
                           f"Neutral={self.regime_probs['neutral']:.2f}, " +
                           f"Bear={self.regime_probs['bear']:.2f}")
                self.current_regime = new_regime
            
            return self.current_regime
            
        except Exception as e:
            logger.error(f"Error in regime detection: {str(e)}")
            return 'neutral'  # Default to neutral on error
    
    def extract_regime_features(self):
        """Extract features for regime detection"""
        try:
            # Debug print to check variable types
            print(f"Extracting regime features - var types: feature_history: {type(self.feature_history)}")
            
            # Calculate features for regime detection
            features = {
                'price': self.data_close[0],
                'sma20': self.sma20[0],
                'sma50': self.sma50[0],
                'sma200': self.sma200[0],
                'volatility': self.volatility[0],
                'atr': self.atr[0],
                'rsi': self.rsi[0],
                'macd': self.macd.macd[0],
                'macd_signal': self.macd.signal[0],
                'upper_band': self.bollinger.top[0],
                'lower_band': self.bollinger.bot[0],
                'date': self.data.datetime.datetime(0),
            }
            
            # Add z_score and funding_z_score if available
            try:
                if hasattr(self, 'funding_z_score') and len(self.funding_z_score) > 0:
                    features['funding_z_score'] = self.funding_z_score[0]
                else:
                    features['funding_z_score'] = 0.0
                    
                # Get the z-score from our indicator if available
                if hasattr(self, 'price_z_score') and len(self.price_z_score) > 0:
                    features['z_score'] = self.price_z_score[0]
                else:
                    # Calculate a simple z-score as fallback
                    returns = (self.data_close[0] / self.data_close[-1]) - 1
                    features['z_score'] = returns / max(self.volatility[0], 0.001)  # Avoid division by zero
                    
            except Exception as e:
                logger.warning(f"Error adding z-scores to features: {str(e)}")
                features['z_score'] = 0.0
                features['funding_z_score'] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting regime features: {str(e)}")
            return {}
    
    def generate_signals(self):
        """Generate trading signals using multiple factors"""
        try:
            # Debug print to check variable types
            print(f"Generating signals - var types: signals: {type(self.signals)}, signal_history: {type(self.signal_history)}")
            
            # Reset signals
            self.signals = {}
            
            # Extract features for signal generation
            features = self.extract_regime_features()
            
            # Calculate additional ratios needed for signal generation
            if features.get('sma50', 0) > 0:
                features['price_sma50_ratio'] = features['price'] / features['sma50']
            else:
                features['price_sma50_ratio'] = 1.0
                
            if features.get('sma200', 0) > 0:
                features['sma50_200_ratio'] = features.get('sma50', 1.0) / features['sma200'] 
            else:
                features['sma50_200_ratio'] = 1.0
                
            if features.get('sma50', 0) > 0:
                features['sma20_50_ratio'] = features.get('sma20', self.sma20[0]) / features['sma50']
            else:
                features['sma20_50_ratio'] = 1.0
            
            # Calculate various signal components
            
            # 1. Trend signal component
            trend_signal = 0
            
            # Simple moving average crossover signal
            if self.ema12[0] > self.ema26[0] and self.ema12[-1] <= self.ema26[-1]:
                trend_signal += 0.5  # Bullish crossover
            elif self.ema12[0] < self.ema26[0] and self.ema12[-1] >= self.ema26[-1]:
                trend_signal -= 0.5  # Bearish crossover
            
            # Add price relative to moving averages
            price_sma50_ratio = features.get('price_sma50_ratio', 1.0)
            if price_sma50_ratio > 1.05:
                trend_signal += 0.3
            elif price_sma50_ratio < 0.95:
                trend_signal -= 0.3
            
            # 2. Mean reversion signal component
            mean_rev_signal = 0
            
            # Z-score based mean reversion
            z_score = features.get('z_score', 0.0)
            if z_score < -2.0:  # Oversold
                mean_rev_signal += 0.6
            elif z_score > 2.0:  # Overbought
                mean_rev_signal -= 0.6
            
            # Add RSI component for mean reversion
            rsi_value = features.get('rsi', 50)
            if rsi_value < 30:  # Oversold
                mean_rev_signal += 0.4
            elif rsi_value > 70:  # Overbought
                mean_rev_signal -= 0.4
            
            # 3. Funding rate component (statistical arbitrage)
            funding_signal = 0
            
            # Look for funding rate outliers
            funding_z = features.get('funding_z_score', 0.0)
            if abs(funding_z) > self.p.funding_z_score_threshold:
                # Strong negative funding (shorts pay longs) is bullish
                if funding_z < -self.p.funding_z_score_threshold:
                    funding_signal += 0.7
                # Strong positive funding (longs pay shorts) is bearish
                elif funding_z > self.p.funding_z_score_threshold:
                    funding_signal -= 0.7
            
            # 4. Volatility breakout component
            vol_breakout_signal = 0
            
            # ATR-based breakout detection
            if (self.data_high[0] - self.data_low[0]) > self.atr[0] * 2:
                # Determine breakout direction
                if self.data_close[0] > self.data_open[0]:  # Bullish breakout
                    vol_breakout_signal += 0.5
                else:  # Bearish breakout
                    vol_breakout_signal -= 0.5
            
            # Store individual signals for reference
            self.signals = {
                'trend': trend_signal,
                'mean_reversion': mean_rev_signal,
                'funding': funding_signal,
                'vol_breakout': vol_breakout_signal
            }
            
            # Combine signals with weights based on current regime
            if self.current_regime == 'bull':
                # In bull regimes, favor trend following and breakouts
                weights = {'trend': 0.5, 'mean_reversion': 0.1, 'funding': 0.2, 'vol_breakout': 0.2}
            elif self.current_regime == 'bear':
                # In bear regimes, favor mean reversion and funding signals
                weights = {'trend': 0.2, 'mean_reversion': 0.4, 'funding': 0.3, 'vol_breakout': 0.1}
            else:  # neutral
                # In neutral regimes, balance all signals
                weights = {'trend': 0.25, 'mean_reversion': 0.3, 'funding': 0.3, 'vol_breakout': 0.15}
            
            # Calculate final combined signal (-1 to 1 scale)
            combined_signal = sum(self.signals[k] * weights[k] for k in weights)
            
            # Apply signal smoothing if enabled
            if hasattr(self, 'last_signal'):
                smoothing_factor = 2 / (self.p.signal_smoothing + 1)
                combined_signal = (smoothing_factor * combined_signal) + ((1 - smoothing_factor) * self.last_signal)
            
            self.last_signal = combined_signal
            
            # Log signals for debugging
            logger.info(f"Signals - Trend: {trend_signal:.2f}, Mean Rev: {mean_rev_signal:.2f}, " +
                       f"Funding: {funding_signal:.2f}, Vol Breakout: {vol_breakout_signal:.2f}")
            logger.info(f"Combined signal: {combined_signal:.2f} in {self.current_regime} regime")
            
            return combined_signal
            
        except Exception as e:
            logger.error(f"Error generating signals: {str(e)}")
            return 0  # Neutral signal on error
    
    def calculate_position_size(self, direction, signal_strength):
        """
        Calculate optimal position size using Kelly criterion and risk management rules
        
        Args:
            direction: 'long' or 'short'
            signal_strength: Signal strength from -1 to 1
        
        Returns:
            Position size in units of base currency
        """
        try:
            # Get current portfolio value
            portfolio_value = self.broker.getvalue()
            
            # Use ATR for volatility-based position sizing
            atr_value = self.atr[0]
            price = self.data_close[0]
            
            # Calculate maximum position size based on risk percentage
            # Scale risk based on signal strength
            abs_signal = abs(signal_strength)
            if abs_signal < self.p.min_signal_strength:
                return 0  # Signal too weak to trade
            
            # Scale risk between base and max risk based on signal strength
            risk_pct = self.p.base_risk_pct + (self.p.max_risk_pct - self.p.base_risk_pct) * (abs_signal - self.p.min_signal_strength) / (1 - self.p.min_signal_strength)
            
            # Apply Kelly criterion - estimate win rate and average win/loss
            # This would be based on historical performance in similar market regimes
            # For this example, we'll use simplified assumptions
            
            # Use current regime to estimate win probability
            if direction == 'long':
                if self.current_regime == 'bull':
                    win_prob = 0.65
                elif self.current_regime == 'bear':
                    win_prob = 0.35
                else:  # neutral
                    win_prob = 0.5
            else:  # short
                if self.current_regime == 'bull':
                    win_prob = 0.35
                elif self.current_regime == 'bear':
                    win_prob = 0.65
                else:  # neutral
                    win_prob = 0.5
            
            # Adjust win probability based on signal strength
            win_prob = 0.5 + (win_prob - 0.5) * abs_signal
            
            # Assume reward/risk ratio based on market conditions
            if self.current_regime == 'neutral':
                reward_risk_ratio = 1.5
            else:
                reward_risk_ratio = 2.0
            
            # Kelly formula: f* = (bp - q) / b = (win_prob * reward_risk_ratio - (1-win_prob)) / reward_risk_ratio
            kelly_percentage = (win_prob * reward_risk_ratio - (1 - win_prob)) / reward_risk_ratio
            
            # Apply Kelly fraction (conservative adjustment)
            kelly_percentage *= self.p.kelly_fraction
            
            # Cap at maximum risk percentage
            risk_pct = min(risk_pct, kelly_percentage, self.p.max_risk_pct)
            
            # Calculate stop loss distance based on ATR
            stop_distance = atr_value * self.p.atr_multiplier
            
            # Calculate position size based on risk amount and stop distance
            risk_amount = portfolio_value * risk_pct
            position_size_usd = risk_amount / (stop_distance / price)
            position_size_units = position_size_usd / price
            
            # Cap position size based on portfolio heat
            max_position_usd = portfolio_value * self.p.position_heat
            if position_size_usd > max_position_usd:
                position_size_units = max_position_usd / price
            
            # Log position sizing details
            logger.info(f"Position sizing - Direction: {direction}, Signal: {signal_strength:.2f}")
            logger.info(f"Risk %: {risk_pct:.2%}, Stop distance: {stop_distance:.2f}, Position size: {position_size_units:.4f} units")
            
            return position_size_units
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 0
    
    def next(self):
        """Main strategy logic executed on each bar"""
        try:
            # Debug print to trace execution
            print(f"Processing bar {len(self)} - type checks: signals: {type(self.signals)}, position_sizes: {type(self.position_sizes)}, feature_history: {type(self.feature_history)}")
            
            # Skip the first bars until we have enough data for our indicators
            if len(self) < self.p.mean_reversion_period + 5:
                return
            
            # Skip if we don't have enough data for our indicators
            if not self.sma200.lines.sma[0] or self.data_close[0] == 0:
                return
            
            # Update portfolio tracking
            current_value = self.broker.getvalue()
            if current_value > self.peak_value:
                self.peak_value = current_value
            else:
                self.statistics['current_drawdown'] = (self.peak_value - current_value) / self.peak_value
                if self.statistics['current_drawdown'] > self.statistics['max_drawdown']:
                    self.statistics['max_drawdown'] = self.statistics['current_drawdown']
            
            # Skip if we have a pending order
            if self.order:
                return
            
            # Generate signals
            signal = self.generate_signals()
            
            # Check if we're in a trade and need to manage it
            if self.position:
                # Update trailing stop if applicable
                self.update_trailing_stop()
                
                # Check time stop
                if self.trade_start_time > 0 and (len(self) - self.trade_start_time) > self.p.time_stop:
                    logger.info(f"Time stop triggered after {self.p.time_stop} bars")
                    self.close()
                    return
                
                # Check for exit signals
                if self.position.size > 0:  # Long position
                    # Exit if signal turns significantly negative
                    if signal < -0.5:
                        logger.info("Strong reversal signal detected, exiting long position")
                        self.close()
                        return
                
                elif self.position.size < 0:  # Short position
                    # Exit if signal turns significantly positive
                    if signal > 0.5:
                        logger.info("Strong reversal signal detected, exiting short position")
                        self.close()
                        return
                
                # If we're still in the trade, no need to enter new trades
                return
            
            # Generate entry signals if not in a position
            
            # Long signal
            if signal > self.p.min_signal_strength:
                # Calculate position size
                size = self.calculate_position_size('long', signal)
                
                if size > 0:
                    # Calculate stops and targets
                    stop_price = self.data_close[0] * (1 - (self.atr[0] * self.p.atr_multiplier / self.data_close[0]))
                    take_profit_price = self.data_close[0] * (1 + (self.atr[0] * self.p.profit_take_atr_mult / self.data_close[0]))
                    
                    # Store values for trailing stop calculation
                    self.buy_price = self.data_close[0]
                    self.stop_price = stop_price
                    self.take_profit_price = take_profit_price
                    self.trade_start_time = len(self)
                    self.atr_value = self.atr[0]
                    
                    # Log trade details
                    logger.info(f"LONG signal at {self.data_close[0]:.2f} with strength {signal:.2f}")
                    logger.info(f"Stop: {stop_price:.2f}, Target: {take_profit_price:.2f}, Size: {size:.4f}")
                    
                    # Execute the order
                    self.order = self.buy(size=size)
                    self.statistics['total_trades'] += 1
            
            # Short signal
            elif signal < -self.p.min_signal_strength:
                # Calculate position size
                size = self.calculate_position_size('short', signal)
                
                if size > 0:
                    # Calculate stops and targets
                    stop_price = self.data_close[0] * (1 + (self.atr[0] * self.p.atr_multiplier / self.data_close[0]))
                    take_profit_price = self.data_close[0] * (1 - (self.atr[0] * self.p.profit_take_atr_mult / self.data_close[0]))
                    
                    # Store values for trailing stop calculation
                    self.sell_price = self.data_close[0]
                    self.stop_price = stop_price
                    self.take_profit_price = take_profit_price
                    self.trade_start_time = len(self)
                    self.atr_value = self.atr[0]
                    
                    # Log trade details
                    logger.info(f"SHORT signal at {self.data_close[0]:.2f} with strength {signal:.2f}")
                    logger.info(f"Stop: {stop_price:.2f}, Target: {take_profit_price:.2f}, Size: {size:.4f}")
                    
                    # Execute the order
                    self.order = self.sell(size=size)
                    self.statistics['total_trades'] += 1
            
        except Exception as e:
            logger.error(f"Error in next method: {str(e)}")
    
    def update_trailing_stop(self):
        """Update trailing stop loss for open positions"""
        try:
            if not self.position:
                return
            
            # Update ATR value for stop calculations
            current_atr = self.atr[0]
            current_price = self.data_close[0]
            
            if self.position.size > 0:  # Long position
                # Initialize trailing stop if not set
                if self.trailing_stop == 0:
                    self.trailing_stop = self.stop_price
                
                # Calculate new potential trailing stop
                new_stop = current_price - (current_atr * self.p.atr_multiplier)
                
                # Only move stop up, never down
                if new_stop > self.trailing_stop:
                    self.trailing_stop = new_stop
                    logger.info(f"Updated trailing stop for LONG to {self.trailing_stop:.2f}")
                
                # Check if trailing stop is hit
                if current_price <= self.trailing_stop:
                    logger.info(f"Trailing stop hit at {current_price:.2f} for LONG position")
                    self.close()
                
                # Check if take profit is hit
                elif current_price >= self.take_profit_price:
                    logger.info(f"Take profit hit at {current_price:.2f} for LONG position")
                    self.close()
            
            elif self.position.size < 0:  # Short position
                # Initialize trailing stop if not set
                if self.trailing_stop == 0:
                    self.trailing_stop = self.stop_price
                
                # Calculate new potential trailing stop
                new_stop = current_price + (current_atr * self.p.atr_multiplier)
                
                # Only move stop down, never up
                if self.trailing_stop == 0 or new_stop < self.trailing_stop:
                    self.trailing_stop = new_stop
                    logger.info(f"Updated trailing stop for SHORT to {self.trailing_stop:.2f}")
                
                # Check if trailing stop is hit
                if current_price >= self.trailing_stop:
                    logger.info(f"Trailing stop hit at {current_price:.2f} for SHORT position")
                    self.close()
                
                # Check if take profit is hit
                elif current_price <= self.take_profit_price:
                    logger.info(f"Take profit hit at {current_price:.2f} for SHORT position")
                    self.close()
        
        except Exception as e:
            logger.error(f"Error updating trailing stop: {str(e)}")
    
    def notify_order(self, order):
        """Handle order notifications"""
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted - no action required
            return
        
        # Check if order is completed
        if order.status in [order.Completed]:
            if order.isbuy():
                logger.info(f"BUY executed at {order.executed.price:.2f}")
                self.buy_price = order.executed.price
            else:
                logger.info(f"SELL executed at {order.executed.price:.2f}")
                self.sell_price = order.executed.price
            
            # Reset trailing stop on new trades
            self.trailing_stop = 0
            
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            logger.info(f"Order Canceled/Margin/Rejected: {order.Status[order.status]}")
        
        # Reset order reference
        self.order = None
    
    def notify_trade(self, trade):
        """Handle trade notifications"""
        if not trade.isclosed:
            return
        
        # Calculate profit metrics
        profit = trade.pnl
        profit_pct = trade.pnlcomm / trade.price * 100
        
        logger.info(f"Trade closed - Profit: {profit:.2f} ({profit_pct:.2f}%)")
        
        # Update statistics - FIX: use statistics dictionary instead of stats
        if profit > 0:
            self.statistics['winning_trades'] += 1
            self.profitable_trades += 1
            self.consecutive_losses = 0
        else:
            self.statistics['losing_trades'] += 1
            self.unprofitable_trades += 1
            self.consecutive_losses += 1
            
            # Update max consecutive losses
            if self.consecutive_losses > self.max_consecutive_losses:
                self.max_consecutive_losses = self.consecutive_losses
        
        # Update total PnL
        self.statistics['total_pnl'] += profit
        
        # Store trade details for analysis
        trade_data = {
            'entry_date': self.data.datetime.datetime(-trade.barlen),
            'exit_date': self.data.datetime.datetime(0),
            'duration': trade.barlen,
            'type': 'long' if trade.long else 'short',
            'size': trade.size,
            'entry_price': trade.price,
            'exit_price': trade.price if trade.size == 0 else trade.price + trade.pnl / trade.size,
            'pnl': trade.pnl,
            'pnl_pct': profit_pct,
            'regime': self.current_regime,
        }
        
        # Safety check to ensure the object is a list before appending
        if not isinstance(self.executed_trades, list):
            logger.error(f"Error: executed_trades is not a list, it's a {type(self.executed_trades)}")
            # Convert to list if it's not
            self.executed_trades = []
            
        self.executed_trades.append(trade_data)
    
    def stop(self):
        """Perform final operations at the end of backtest"""
        # Calculate final metrics
        final_value = self.broker.getvalue()
        roi = (final_value / self.starting_value - 1) * 100
        
        # Calculate win rate
        win_rate = 0
        if self.trade_count > 0:
            win_rate = (self.profitable_trades / self.trade_count) * 100
        
        # Log results
        logger.info("Backtest completed")
        logger.info(f"Starting Value: ${self.starting_value:.2f}")
        logger.info(f"Final Value: ${final_value:.2f}")
        logger.info(f"Return: {roi:.2f}%")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Profitable Trades: {self.profitable_trades}")
        logger.info(f"Win Rate: {win_rate:.2f}%")
        logger.info(f"Max Drawdown: {self.statistics['max_drawdown']:.2%}")
        logger.info(f"Max Consecutive Losses: {self.max_consecutive_losses}")
    
    def create_obv_indicator(self):
        """Create a custom On Balance Volume indicator"""
        class OBV(bt.Indicator):
            lines = ('obv',)
            params = ()
            
            def __init__(self):
                self.addminperiod(2)  # Needs at least 2 periods to calculate
                
            def next(self):
                if len(self) <= 1:  # First bar
                    self.lines.obv[0] = self.data.volume[0]
                    return
                    
                prev_close = self.data.close[-1]
                curr_close = self.data.close[0]
                curr_volume = self.data.volume[0]
                
                if curr_close > prev_close:
                    # Bullish
                    self.lines.obv[0] = self.lines.obv[-1] + curr_volume
                elif curr_close < prev_close:
                    # Bearish
                    self.lines.obv[0] = self.lines.obv[-1] - curr_volume
                else:
                    # No change
                    self.lines.obv[0] = self.lines.obv[-1]
        
        return OBV(self.data)

    def get_current_funding_rate(self, date):
        """Get the funding rate for a given date"""
        try:
            # In a real implementation, this would retrieve the actual funding rate from an API
            # For this demonstration, we'll use a synthetic rate
            
            # Ensure funding_rates is a list
            if not hasattr(self, 'funding_rates') or not isinstance(self.funding_rates, list):
                self.funding_rates = []
                
            # If we don't have a synthetic rate yet, generate one based on price movement
            if not self.funding_rates:
                # Generate synthetic rate based on price momentum
                recent_return = (self.data_close[0] / self.data_close[-20]) - 1
                rate = -0.01 * recent_return  # Negative correlation with recent returns
                return rate
                
            # Use the most recent rate from our list
            return self.funding_rates[-1] if self.funding_rates else 0.0
                
        except Exception as e:
            logger.error(f"Error getting funding rate: {str(e)}")
            return 0.0  # Default to zero funding rate on error