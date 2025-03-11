"""
Volume Profile Strategy

This strategy utilizes volume profile analysis to identify key price levels and 
react to price movements around these levels. It's particularly effective at
identifying potential reversal points and areas of value during market volatility
and liquidation cascades.

The strategy:
1. Builds volume profiles over configurable time periods
2. Identifies key levels (POC, value areas, liquidity zones)
3. Detects potential liquidation cascades 
4. Takes contrarian positions at key levels during high volatility
5. Uses adaptive position sizing based on volume profile strength

Tags: [statistical, volume, liquidity, mean_reversion, volatility]
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union, Any
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from pathlib import Path
import os

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class VolumeProfileStrategy(BaseStrategy):
    """
    Strategy utilizing volume profile analysis to identify key levels and react
    to price movements around these levels, particularly during liquidation cascades.
    
    Args:
        symbols: List of symbols to trade
        lookback_periods: Number of periods to use for building volume profile
        num_volume_bins: Number of price bins for volume profile
        value_area_pct: Percentage of volume to include in value area
        poc_threshold_pct: Threshold for POC significance
        key_level_threshold_pct: Threshold for key level significance
        liquidation_threshold: Volatility threshold for liquidation detection
        position_size_pct: Base position size as percentage of capital
        profit_target_pct: Profit target as percentage
        stop_loss_pct: Stop loss as percentage
        max_holding_periods: Maximum number of periods to hold a position
    """
    
    # Required data for this strategy
    REQUIRED_DATA = ["ohlcv", "trades", "liquidations"]
    
    def __init__(self, 
                 symbols: List[str],
                 lookback_periods: int = 30,
                 num_volume_bins: int = 60,
                 value_area_pct: float = 70.0,
                 poc_threshold_pct: float = 0.5,
                 key_level_threshold_pct: float = 0.2,
                 liquidation_threshold: float = 2.0,
                 position_size_pct: float = 0.2,
                 profit_target_pct: float = 2.0,
                 stop_loss_pct: float = 1.0,
                 max_holding_periods: int = 48,
                 **kwargs):
        """Initialize the strategy with parameters."""
        super().__init__(symbols=symbols, **kwargs)
        
        # Strategy parameters
        self.lookback_periods = lookback_periods
        self.num_volume_bins = num_volume_bins
        self.value_area_pct = value_area_pct
        self.poc_threshold_pct = poc_threshold_pct
        self.key_level_threshold_pct = key_level_threshold_pct
        self.liquidation_threshold = liquidation_threshold
        self.position_size_pct = position_size_pct
        self.profit_target_pct = profit_target_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_holding_periods = max_holding_periods
        
        # Internal state
        self._volume_profiles = {}
        self._active_positions = {}
        self._closed_positions = []
        self._last_update = {}
    
    def detect_liquidation(self, data: pd.DataFrame, periods: int = 5) -> bool:
        """
        Detect potential liquidation cascades based on price and volume behavior.
        
        Args:
            data: DataFrame with OHLCV and trade data
            periods: Number of recent periods to analyze
            
        Returns:
            bool: True if liquidation cascade is detected
        """
        if len(data) < periods + 1:
            return False
            
        recent_data = data.iloc[-periods:]
        
        # Calculate price volatility
        price_change = recent_data['close'].pct_change().abs()
        volume_change = recent_data['volume'].pct_change()
        
        # Conditions for liquidation cascade:
        # 1. High price volatility
        # 2. Increasing volume
        # 3. Directional consistency (continuous up or down moves)
        
        avg_price_change = price_change.mean() * 100  # as percentage
        price_direction_consistency = abs(recent_data['close'].pct_change().sum() / 
                                      price_change.sum() if price_change.sum() > 0 else 0)
        increasing_volume = (volume_change > 0).sum() / periods
        
        # Liquidation detected if:
        # - Price volatility exceeds threshold
        # - Price moves are directionally consistent
        # - Volume is generally increasing
        return (avg_price_change > self.liquidation_threshold and
                price_direction_consistency > 0.7 and
                increasing_volume > 0.6)
    
    def update_volume_profile(self, data: pd.DataFrame) -> Dict:
        """
        Update the volume profile based on recent data.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            Dict with volume profile information
        """
        if len(data) < self.lookback_periods:
            return {}
            
        # Use most recent data for volume profile
        profile_data = data.iloc[-self.lookback_periods:]
        
        # Calculate price range
        price_min = profile_data['low'].min()
        price_max = profile_data['high'].max()
        price_range = price_max - price_min
        
        if price_range <= 0:
            return {}
            
        # Create price bins
        bin_size = price_range / self.num_volume_bins
        price_bins = np.linspace(price_min, price_max, self.num_volume_bins + 1)
        
        # Initialize volume profile
        volume_profile = np.zeros(self.num_volume_bins)
        
        # Distribute volume across price bins
        for _, row in profile_data.iterrows():
            # Calculate approximation of volume distribution across the price range of the candle
            candle_min = max(row['low'], price_min)
            candle_max = min(row['high'], price_max)
            candle_range = candle_max - candle_min
            
            if candle_range <= 0:
                continue
                
            # Find bins that overlap with this candle
            low_bin = max(0, int((candle_min - price_min) / bin_size))
            high_bin = min(self.num_volume_bins - 1, int((candle_max - price_min) / bin_size))
            
            # Distribute volume across bins
            for bin_idx in range(low_bin, high_bin + 1):
                bin_low = price_min + bin_idx * bin_size
                bin_high = price_min + (bin_idx + 1) * bin_size
                
                # Calculate overlap between bin and candle
                overlap_low = max(bin_low, candle_min)
                overlap_high = min(bin_high, candle_max)
                overlap_pct = (overlap_high - overlap_low) / candle_range
                
                # Allocate volume to this bin
                volume_profile[bin_idx] += row['volume'] * overlap_pct
        
        # Find point of control (price level with highest volume)
        poc_idx = np.argmax(volume_profile)
        poc_price = price_min + (poc_idx + 0.5) * bin_size
        
        # Calculate value area (price range containing specified % of volume)
        total_volume = volume_profile.sum()
        value_area_volume = total_volume * (self.value_area_pct / 100.0)
        
        # Sort bins by volume in descending order
        sorted_bins = np.argsort(volume_profile)[::-1]
        
        value_area_bins = set()
        cumulative_volume = 0
        
        for bin_idx in sorted_bins:
            value_area_bins.add(bin_idx)
            cumulative_volume += volume_profile[bin_idx]
            
            if cumulative_volume >= value_area_volume:
                break
        
        # Find continuous ranges in value area
        value_area_ranges = []
        in_range = False
        start_bin = 0
        
        for bin_idx in range(self.num_volume_bins):
            if bin_idx in value_area_bins and not in_range:
                # Start of a new range
                in_range = True
                start_bin = bin_idx
            elif bin_idx not in value_area_bins and in_range:
                # End of a range
                in_range = False
                end_bin = bin_idx - 1
                
                value_area_ranges.append({
                    'low': price_min + start_bin * bin_size,
                    'high': price_min + (end_bin + 1) * bin_size,
                    'volume': sum(volume_profile[start_bin:end_bin+1])
                })
        
        # Add final range if still in range at the end
        if in_range:
            value_area_ranges.append({
                'low': price_min + start_bin * bin_size,
                'high': price_min + self.num_volume_bins * bin_size,
                'volume': sum(volume_profile[start_bin:])
            })
        
        # Identify key levels (local maxima in volume profile)
        key_levels = []
        threshold = volume_profile.max() * self.key_level_threshold_pct
        
        for i in range(1, self.num_volume_bins - 1):
            if (volume_profile[i] > volume_profile[i-1] and 
                volume_profile[i] > volume_profile[i+1] and
                volume_profile[i] > threshold):
                
                key_levels.append({
                    'price': price_min + (i + 0.5) * bin_size,
                    'volume': volume_profile[i],
                    'strength': volume_profile[i] / volume_profile.max()
                })
        
        # Return volume profile analysis
        return {
            'price_range': {'min': price_min, 'max': price_max},
            'bin_size': bin_size,
            'poc': {'price': poc_price, 'volume': volume_profile[poc_idx]},
            'value_area': value_area_ranges,
            'key_levels': key_levels,
            'profile': volume_profile.tolist(),
            'price_bins': price_bins.tolist()
        }
    
    def generate_signal(self, data: pd.DataFrame, symbol: str) -> Tuple[int, Dict]:
        """
        Generate trading signals based on volume profile analysis.
        
        Args:
            data: DataFrame with market data
            symbol: Trading symbol
            
        Returns:
            Tuple with signal direction (-1, 0, 1) and signal details
        """
        if len(data) < self.lookback_periods + 10:
            return 0, {'reason': 'Insufficient data'}
            
        # Update the volume profile
        volume_profile = self.update_volume_profile(data.iloc[:-1])
        
        if not volume_profile:
            return 0, {'reason': 'Failed to create volume profile'}
            
        # Store updated profile
        self._volume_profiles[symbol] = volume_profile
        
        # Current price
        current_price = data.iloc[-1]['close']
        
        # Detect potential liquidation cascade
        is_liquidation = self.detect_liquidation(data)
        
        # Default signal
        signal = 0
        signal_details = {}
        
        # Check relative position to POC and value area
        poc_price = volume_profile['poc']['price']
        distance_to_poc_pct = (current_price - poc_price) / poc_price * 100
        
        # Determine if price is within value area
        in_value_area = False
        for va_range in volume_profile['value_area']:
            if va_range['low'] <= current_price <= va_range['high']:
                in_value_area = True
                break
        
        # Find nearest key level
        nearest_key_level = None
        min_distance = float('inf')
        
        for level in volume_profile['key_levels']:
            distance = abs(current_price - level['price'])
            if distance < min_distance:
                min_distance = distance
                nearest_key_level = level
        
        # Calculate relative distance to nearest key level
        if nearest_key_level:
            distance_to_key_level_pct = (
                abs(current_price - nearest_key_level['price']) / nearest_key_level['price'] * 100
            )
            key_level_strength = nearest_key_level['strength']
        else:
            distance_to_key_level_pct = 100.0
            key_level_strength = 0.0
        
        # Current price momentum
        recent_momentum = data.iloc[-5:]['close'].pct_change().sum() * 100
        
        # Signal logic based on volume profile and current conditions
        if is_liquidation:
            # Contrarian signal during liquidation cascades
            if recent_momentum < -2.0 and (
                (abs(distance_to_poc_pct) < 1.0) or 
                (distance_to_key_level_pct < 0.5 and key_level_strength > 0.7)
            ):
                # Strong buy signal at support during downward liquidation
                signal = 1
                signal_details = {
                    'signal_type': 'liquidation_reversal',
                    'direction': 'buy',
                    'strength': min(1.0, key_level_strength + 0.3),
                    'target_price': poc_price,
                    'stop_price': current_price * (1 - self.stop_loss_pct/100)
                }
            elif recent_momentum > 2.0 and (
                (abs(distance_to_poc_pct) < 1.0) or 
                (distance_to_key_level_pct < 0.5 and key_level_strength > 0.7)
            ):
                # Strong sell signal at resistance during upward liquidation
                signal = -1
                signal_details = {
                    'signal_type': 'liquidation_reversal',
                    'direction': 'sell',
                    'strength': min(1.0, key_level_strength + 0.3),
                    'target_price': poc_price,
                    'stop_price': current_price * (1 + self.stop_loss_pct/100)
                }
        else:
            # Normal market conditions signals
            
            # Value area breakout/breakdown
            for va_range in volume_profile['value_area']:
                # Breakout above value area high
                if (current_price > va_range['high'] and 
                    data.iloc[-2]['close'] <= va_range['high'] and
                    recent_momentum > 0):
                    signal = 1
                    signal_details = {
                        'signal_type': 'value_area_breakout',
                        'direction': 'buy',
                        'strength': 0.7,
                        'target_price': va_range['high'] * (1 + self.profit_target_pct/100),
                        'stop_price': va_range['high'] * 0.99
                    }
                    break
                    
                # Breakdown below value area low
                if (current_price < va_range['low'] and 
                    data.iloc[-2]['close'] >= va_range['low'] and
                    recent_momentum < 0):
                    signal = -1
                    signal_details = {
                        'signal_type': 'value_area_breakdown',
                        'direction': 'sell',
                        'strength': 0.7,
                        'target_price': va_range['low'] * (1 - self.profit_target_pct/100),
                        'stop_price': va_range['low'] * 1.01
                    }
                    break
            
            # Mean reversion at extreme moves away from POC
            if not signal and abs(distance_to_poc_pct) > 3.0:
                if distance_to_poc_pct > 0 and recent_momentum < 0:
                    # Price is above POC and momentum turning down
                    signal = -1
                    signal_details = {
                        'signal_type': 'mean_reversion',
                        'direction': 'sell',
                        'strength': min(0.8, abs(distance_to_poc_pct) / 10),
                        'target_price': poc_price,
                        'stop_price': current_price * (1 + self.stop_loss_pct/100)
                    }
                elif distance_to_poc_pct < 0 and recent_momentum > 0:
                    # Price is below POC and momentum turning up
                    signal = 1
                    signal_details = {
                        'signal_type': 'mean_reversion',
                        'direction': 'buy',
                        'strength': min(0.8, abs(distance_to_poc_pct) / 10),
                        'target_price': poc_price,
                        'stop_price': current_price * (1 - self.stop_loss_pct/100)
                    }
        
        if signal:
            # Add common signal information
            signal_details.update({
                'timestamp': data.index[-1],
                'price': current_price,
                'volume_profile': {
                    'poc': poc_price,
                    'in_value_area': in_value_area,
                    'distance_to_poc_pct': distance_to_poc_pct
                },
                'is_liquidation': is_liquidation
            })
        
        return signal, signal_details
    
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
        
        # Calculate per-symbol capital allocation
        symbol_count = len(self.symbols)
        capital_per_symbol = capital / symbol_count if symbol_count > 0 else 0
        
        # Process each symbol
        for symbol in self.symbols:
            if symbol not in data_dict:
                continue
                
            data = data_dict[symbol]
            
            if len(data) < self.lookback_periods + 10:
                continue
                
            # Get current timestamp
            current_time = data.index[-1]
            
            # Update existing positions
            if symbol in self._active_positions:
                position = self._active_positions[symbol]
                current_price = data.iloc[-1]['close']
                
                # Calculate P&L
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
                
                # Max holding period
                if position['holding_periods'] >= self.max_holding_periods:
                    exit_reason = 'max_holding_period'
                
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
            
            # Generate new signals if no active position
            if symbol not in self._active_positions:
                signal, signal_details = self.generate_signal(data, symbol)
                
                if signal != 0 and signal_details:
                    # Calculate position size
                    base_position_value = capital_per_symbol * self.position_size_pct
                    
                    # Adjust position size based on signal strength
                    signal_strength = signal_details.get('strength', 0.5)
                    position_value = base_position_value * signal_strength
                    
                    # Entry price
                    entry_price = data.iloc[-1]['close']
                    
                    # Calculate quantity
                    quantity = position_value / entry_price
                    
                    # Create new position
                    position = {
                        'symbol': symbol,
                        'entry_time': current_time,
                        'direction': 'buy' if signal > 0 else 'sell',
                        'entry_price': entry_price,
                        'quantity': quantity,
                        'position_value': position_value,
                        'target_price': signal_details.get('target_price'),
                        'stop_price': signal_details.get('stop_price'),
                        'signal_type': signal_details.get('signal_type'),
                        'current_price': entry_price,
                        'current_pnl_pct': 0.0,
                        'holding_periods': 0,
                        'is_liquidation_trade': signal_details.get('is_liquidation', False)
                    }
                    
                    # Add to active positions
                    self._active_positions[symbol] = position
                    
                    # Record the executed entry trade
                    executed_trades.append({
                        'symbol': symbol,
                        'timestamp': current_time,
                        'action': 'entry',
                        'direction': position['direction'],
                        'price': entry_price,
                        'quantity': quantity,
                        'value': position_value,
                        'reason': position['signal_type'],
                        'target_price': position['target_price'],
                        'stop_price': position['stop_price']
                    })
        
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
                    'trade_type': entry['reason']
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
        
        # Performance by trade type
        performance_by_type = {}
        
        for trade in closed_trades:
            trade_type = trade['trade_type']
            
            if trade_type not in performance_by_type:
                performance_by_type[trade_type] = {
                    'count': 0,
                    'win_count': 0,
                    'total_pnl': 0,
                    'avg_pnl_pct': 0
                }
            
            perf = performance_by_type[trade_type]
            perf['count'] += 1
            
            if trade['pnl_value'] > 0:
                perf['win_count'] += 1
                
            perf['total_pnl'] += trade['pnl_value']
            
        # Calculate averages
        for trade_type, perf in performance_by_type.items():
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
            'performance_by_type': performance_by_type
        } 