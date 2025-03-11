"""
Order Flow Analyzer Module

This module provides tools for analyzing order flow data, including trade patterns,
transaction size analysis, and trading behavior detection.

The OrderFlowAnalyzer class is the primary component for analyzing order flow data
and extracting trading signals.
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import datetime, timedelta
from collections import deque, defaultdict

from advanced_trading.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)

class OrderFlowAnalyzer:
    """
    Analyzes trade and order data to detect patterns, identify large traders,
    and generate trading signals.
    
    This class provides comprehensive tools for:
    - Trade pattern recognition
    - Transaction size analysis
    - Trade clustering
    - Large trader identification
    - Market buy/sell pressure calculation
    - Volume profile analysis
    """
    
    def __init__(self, 
                history_window: int = 1000,
                time_window_seconds: int = 300,
                large_trade_threshold: float = 0.95,
                sequential_trade_count: int = 10):
        """
        Initialize the OrderFlowAnalyzer.
        
        Args:
            history_window: Number of trades to keep in history
            time_window_seconds: Time window in seconds for analysis
            large_trade_threshold: Percentile threshold for large trade detection (0-1)
            sequential_trade_count: Number of sequential trades to analyze for patterns
        """
        self.history_window = history_window
        self.time_window_seconds = time_window_seconds
        self.large_trade_threshold = large_trade_threshold
        self.sequential_trade_count = sequential_trade_count
        
        # Trade history tracking
        self.trade_history = {}  # {symbol: deque of trades}
        self.metrics = {}        # {symbol: {metric: value}}
        self.patterns = {}       # {symbol: {pattern: data}}
        self.signals = {}        # {symbol: {signal: value}}
        
        # Initialize empty metrics
        self._initialize_metrics()
        
        logger.info(f"OrderFlowAnalyzer initialized with history window {history_window}, "
                  f"time window {time_window_seconds}s, large trade threshold {large_trade_threshold}")
    
    def _initialize_metrics(self):
        """Initialize metrics dictionary with default values."""
        self.default_metrics = {
            # Volume metrics
            'total_volume': 0.0,
            'buy_volume': 0.0,
            'sell_volume': 0.0,
            'volume_imbalance': 0.0,
            
            # Trade count metrics
            'total_trades': 0,
            'buy_trades': 0,
            'sell_trades': 0,
            'trade_imbalance': 0.0,
            
            # Transaction size metrics
            'avg_trade_size': 0.0,
            'large_trade_threshold': 0.0,
            'large_trades_count': 0,
            'large_trades_volume': 0.0,
            'large_trades_pct': 0.0,
            
            # Sequential metrics
            'sequential_buys': 0,
            'sequential_sells': 0,
            'max_sequential_buys': 0,
            'max_sequential_sells': 0,
            
            # Momentum metrics
            'short_term_momentum': 0.0,
            'medium_term_momentum': 0.0,
            'momentum_divergence': 0.0,
            
            # Timestamp
            'last_update_time': 0
        }
    
    def process_trade(self, symbol: str, trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a new trade and update metrics.
        
        Args:
            symbol: Trading symbol
            trade: Trade data with required fields:
                - price: Trade price
                - amount: Trade amount/quantity
                - side: 'buy' or 'sell'
                - timestamp: Trade timestamp in milliseconds
                
        Returns:
            Dict with updated metrics and detected patterns
        """
        # Ensure we have required fields
        required_fields = ['price', 'amount', 'side', 'timestamp']
        for field in required_fields:
            if field not in trade:
                logger.warning(f"Missing required field '{field}' in trade data for {symbol}")
                return {}
        
        # Ensure symbol is initialized in our trackers
        if symbol not in self.trade_history:
            self.trade_history[symbol] = deque(maxlen=self.history_window)
            self.metrics[symbol] = self.default_metrics.copy()
            self.patterns[symbol] = {}
            self.signals[symbol] = {}
        
        # Add trade to history
        self.trade_history[symbol].append(trade)
        
        # Update time window filter - keep trades within time window
        current_time = trade['timestamp']
        time_window_start = current_time - (self.time_window_seconds * 1000)
        
        # Filter recent trades within time window
        recent_trades = [t for t in self.trade_history[symbol] 
                       if t['timestamp'] >= time_window_start]
        
        # Calculate metrics
        self._calculate_volume_metrics(symbol, recent_trades)
        self._calculate_transaction_metrics(symbol, recent_trades)
        self._calculate_sequential_metrics(symbol, recent_trades)
        self._calculate_momentum_metrics(symbol, recent_trades)
        
        # Detect patterns
        patterns = self._detect_patterns(symbol, recent_trades)
        
        # Generate signals
        signals = self._generate_signals(symbol)
        
        # Update timestamp
        self.metrics[symbol]['last_update_time'] = current_time
        
        # Return relevant results
        return {
            'metrics': self.metrics[symbol],
            'patterns': patterns,
            'signals': signals
        }
    
    def _calculate_volume_metrics(self, symbol: str, trades: List[Dict[str, Any]]) -> None:
        """Calculate volume-based metrics from recent trades."""
        metrics = self.metrics[symbol]
        
        # Reset counters
        total_volume = 0.0
        buy_volume = 0.0
        sell_volume = 0.0
        buy_trades = 0
        sell_trades = 0
        
        # Process trades
        for trade in trades:
            amount = trade['amount']
            side = trade['side'].lower()
            
            total_volume += amount
            
            if side == 'buy':
                buy_volume += amount
                buy_trades += 1
            else:
                sell_volume += amount
                sell_trades += 1
        
        # Calculate imbalance
        total_trades = buy_trades + sell_trades
        volume_imbalance = 0.0
        trade_imbalance = 0.0
        
        if total_volume > 0:
            volume_imbalance = (buy_volume - sell_volume) / total_volume
            
        if total_trades > 0:
            trade_imbalance = (buy_trades - sell_trades) / total_trades
        
        # Update metrics
        metrics['total_volume'] = total_volume
        metrics['buy_volume'] = buy_volume
        metrics['sell_volume'] = sell_volume
        metrics['volume_imbalance'] = volume_imbalance
        metrics['total_trades'] = total_trades
        metrics['buy_trades'] = buy_trades
        metrics['sell_trades'] = sell_trades
        metrics['trade_imbalance'] = trade_imbalance
    
    def _calculate_transaction_metrics(self, symbol: str, trades: List[Dict[str, Any]]) -> None:
        """Calculate transaction size metrics from recent trades."""
        metrics = self.metrics[symbol]
        
        if not trades:
            return
        
        # Calculate average trade size
        total_volume = metrics['total_volume']
        total_trades = metrics['total_trades']
        
        avg_trade_size = total_volume / total_trades if total_trades > 0 else 0
        
        # Get trade sizes and calculate percentiles
        trade_sizes = [trade['amount'] for trade in trades]
        
        if trade_sizes:
            large_trade_threshold = np.percentile(trade_sizes, self.large_trade_threshold * 100)
            
            # Count large trades
            large_trades = [size for size in trade_sizes if size >= large_trade_threshold]
            large_trades_count = len(large_trades)
            large_trades_volume = sum(large_trades)
            
            # Calculate percentage of volume from large trades
            large_trades_pct = large_trades_volume / total_volume if total_volume > 0 else 0
        else:
            large_trade_threshold = 0
            large_trades_count = 0
            large_trades_volume = 0
            large_trades_pct = 0
        
        # Update metrics
        metrics['avg_trade_size'] = avg_trade_size
        metrics['large_trade_threshold'] = large_trade_threshold
        metrics['large_trades_count'] = large_trades_count
        metrics['large_trades_volume'] = large_trades_volume
        metrics['large_trades_pct'] = large_trades_pct
    
    def _calculate_sequential_metrics(self, symbol: str, trades: List[Dict[str, Any]]) -> None:
        """Calculate sequential trade metrics."""
        metrics = self.metrics[symbol]
        
        if not trades:
            return
        
        # Sort trades by timestamp to ensure correct order
        sorted_trades = sorted(trades, key=lambda x: x['timestamp'])
        
        # Count sequential buys and sells
        current_sequence = 0
        max_buys = 0
        max_sells = 0
        last_side = None
        
        for trade in sorted_trades:
            side = trade['side'].lower()
            
            if side == last_side:
                current_sequence += 1
            else:
                current_sequence = 1
                last_side = side
            
            if side == 'buy':
                max_buys = max(max_buys, current_sequence)
            else:
                max_sells = max(max_sells, current_sequence)
        
        # Calculate current sequences (for most recent trades)
        recent_count = min(self.sequential_trade_count, len(sorted_trades))
        recent_trades = sorted_trades[-recent_count:]
        
        current_buys = 0
        current_sells = 0
        last_side = None
        
        for trade in reversed(recent_trades):
            side = trade['side'].lower()
            
            if side != last_side and last_side is not None:
                break
                
            if side == 'buy':
                current_buys += 1
            else:
                current_sells += 1
                
            last_side = side
        
        # Update metrics
        metrics['sequential_buys'] = current_buys
        metrics['sequential_sells'] = current_sells
        metrics['max_sequential_buys'] = max_buys
        metrics['max_sequential_sells'] = max_sells
    
    def _calculate_momentum_metrics(self, symbol: str, trades: List[Dict[str, Any]]) -> None:
        """Calculate momentum metrics from price action."""
        metrics = self.metrics[symbol]
        
        if len(trades) < 10:
            return
        
        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda x: x['timestamp'])
        
        # Get prices for different time windows
        prices = [trade['price'] for trade in sorted_trades]
        
        # Calculate price changes for different time periods
        # Short term: last 10% of trades
        # Medium term: last 50% of trades
        short_term_count = max(int(len(prices) * 0.1), 2)
        medium_term_count = max(int(len(prices) * 0.5), 5)
        
        short_term_start = prices[-short_term_count]
        medium_term_start = prices[-medium_term_count]
        current_price = prices[-1]
        
        # Calculate price changes as percentages
        short_term_change = (current_price - short_term_start) / short_term_start if short_term_start > 0 else 0
        medium_term_change = (current_price - medium_term_start) / medium_term_start if medium_term_start > 0 else 0
        
        # Calculate momentum divergence (difference between short and medium term)
        momentum_divergence = short_term_change - medium_term_change
        
        # Update metrics
        metrics['short_term_momentum'] = short_term_change
        metrics['medium_term_momentum'] = medium_term_change
        metrics['momentum_divergence'] = momentum_divergence
    
    def _detect_patterns(self, symbol: str, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect trading patterns in recent trades."""
        metrics = self.metrics[symbol]
        patterns = {}
        
        # Large trade pattern
        if (metrics['large_trades_count'] > 0 and 
            metrics['large_trades_pct'] > 0.3):  # Large trades account for >30% of volume
            
            # Determine direction of large trades
            large_buy_volume = 0.0
            large_sell_volume = 0.0
            
            for trade in trades:
                if trade['amount'] >= metrics['large_trade_threshold']:
                    if trade['side'].lower() == 'buy':
                        large_buy_volume += trade['amount']
                    else:
                        large_sell_volume += trade['amount']
            
            # Calculate large trade imbalance
            large_trade_total = large_buy_volume + large_sell_volume
            if large_trade_total > 0:
                large_trade_imbalance = (large_buy_volume - large_sell_volume) / large_trade_total
                
                if abs(large_trade_imbalance) > 0.7:  # Strong directional bias
                    direction = 'buy' if large_trade_imbalance > 0 else 'sell'
                    
                    patterns['large_trader_activity'] = {
                        'direction': direction,
                        'imbalance': large_trade_imbalance,
                        'volume_pct': metrics['large_trades_pct'],
                        'count': metrics['large_trades_count'],
                        'avg_size': metrics['large_trades_volume'] / metrics['large_trades_count'] 
                                   if metrics['large_trades_count'] > 0 else 0
                    }
        
        # Sequential trades pattern
        if (metrics['max_sequential_buys'] >= 5 or 
            metrics['max_sequential_sells'] >= 5):
            
            patterns['sequential_trades'] = {
                'max_buys': metrics['max_sequential_buys'],
                'max_sells': metrics['max_sequential_sells'],
                'current_buys': metrics['sequential_buys'],
                'current_sells': metrics['sequential_sells'],
                'dominant_side': 'buy' if metrics['max_sequential_buys'] > metrics['max_sequential_sells'] else 'sell'
            }
        
        # Volume burst pattern
        if len(trades) > 20:
            # Split trades into two halves and compare volume
            half_point = len(trades) // 2
            first_half = trades[:half_point]
            second_half = trades[half_point:]
            
            first_volume = sum(t['amount'] for t in first_half)
            second_volume = sum(t['amount'] for t in second_half)
            
            # Calculate volume ratio
            if first_volume > 0:
                volume_ratio = second_volume / first_volume
                
                if volume_ratio > 2.0:  # Volume at least doubled
                    # Determine dominant side in the burst
                    second_buy_vol = sum(t['amount'] for t in second_half if t['side'].lower() == 'buy')
                    second_sell_vol = sum(t['amount'] for t in second_half if t['side'].lower() == 'sell')
                    
                    if second_buy_vol > 0 or second_sell_vol > 0:
                        burst_imbalance = (second_buy_vol - second_sell_vol) / (second_buy_vol + second_sell_vol)
                        
                        patterns['volume_burst'] = {
                            'ratio': volume_ratio,
                            'direction': 'buy' if burst_imbalance > 0 else 'sell',
                            'imbalance': abs(burst_imbalance),
                            'volume': second_volume
                        }
        
        # Momentum divergence pattern
        if abs(metrics['momentum_divergence']) > 0.005:  # 0.5% divergence
            divergence_type = 'bullish' if metrics['momentum_divergence'] > 0 else 'bearish'
            
            patterns['momentum_divergence'] = {
                'type': divergence_type,
                'magnitude': abs(metrics['momentum_divergence']),
                'short_term': metrics['short_term_momentum'],
                'medium_term': metrics['medium_term_momentum']
            }
        
        # Update patterns dictionary for this symbol
        self.patterns[symbol] = patterns
        
        return patterns
    
    def _generate_signals(self, symbol: str) -> Dict[str, Any]:
        """Generate trading signals from metrics and patterns."""
        metrics = self.metrics[symbol]
        patterns = self.patterns.get(symbol, {})
        signals = {}
        
        # Volume imbalance signal
        if abs(metrics['volume_imbalance']) > 0.3:  # Significant imbalance
            signals['volume_imbalance'] = {
                'direction': 'buy' if metrics['volume_imbalance'] > 0 else 'sell',
                'strength': abs(metrics['volume_imbalance']),
                'confidence': min(0.3 + abs(metrics['volume_imbalance']) * 0.7, 1.0)  # Scale 0.3-1.0
            }
        
        # Large trader signal
        if 'large_trader_activity' in patterns:
            large_trader = patterns['large_trader_activity']
            signals['large_trader'] = {
                'direction': large_trader['direction'],
                'strength': abs(large_trader['imbalance']),
                'confidence': min(0.5 + large_trader['volume_pct'] * 0.5, 1.0)  # Scale 0.5-1.0
            }
        
        # Sequential trades signal
        if 'sequential_trades' in patterns:
            seq_trades = patterns['sequential_trades']
            
            # Only generate signal if current sequence is significant
            current_seq = max(seq_trades['current_buys'], seq_trades['current_sells'])
            if current_seq >= 3:
                direction = 'buy' if seq_trades['current_buys'] > seq_trades['current_sells'] else 'sell'
                signals['sequential_trades'] = {
                    'direction': direction,
                    'strength': min(current_seq / 10, 1.0),  # Scale based on sequence length
                    'confidence': 0.4 + min(current_seq / 10, 0.6)  # Scale 0.4-1.0
                }
        
        # Volume burst signal
        if 'volume_burst' in patterns:
            burst = patterns['volume_burst']
            
            # Only strong bursts generate signals
            if burst['ratio'] > 3.0 and burst['imbalance'] > 0.6:
                signals['volume_burst'] = {
                    'direction': burst['direction'],
                    'strength': min(burst['ratio'] / 5, 1.0),  # Scale based on burst size
                    'confidence': min(0.6 + burst['imbalance'] * 0.4, 1.0)  # Scale 0.6-1.0
                }
        
        # Momentum divergence signal
        if 'momentum_divergence' in patterns:
            divergence = patterns['momentum_divergence']
            
            signals['momentum_divergence'] = {
                'direction': 'buy' if divergence['type'] == 'bullish' else 'sell',
                'strength': min(divergence['magnitude'] * 100, 1.0),  # Scale based on magnitude
                'confidence': 0.5 + min(divergence['magnitude'] * 100, 0.5)  # Scale 0.5-1.0
            }
        
        # Combine signals for overall bias
        if signals:
            # Calculate weighted direction
            direction_weight = 0.0
            total_weight = 0.0
            
            for signal_name, signal_data in signals.items():
                # Assign weights based on signal type
                weight = {
                    'volume_imbalance': 0.2,
                    'large_trader': 0.35,
                    'sequential_trades': 0.15,
                    'volume_burst': 0.2,
                    'momentum_divergence': 0.1
                }.get(signal_name, 0.1)
                
                # Adjust by confidence
                weight *= signal_data['confidence']
                
                # Add to direction (positive for buy, negative for sell)
                direction_factor = 1.0 if signal_data['direction'] == 'buy' else -1.0
                direction_weight += weight * direction_factor * signal_data['strength']
                total_weight += weight
            
            if total_weight > 0:
                # Normalize direction weight
                normalized_direction = direction_weight / total_weight
                
                # Convert to buy/sell with confidence
                direction = 'buy' if normalized_direction > 0 else 'sell'
                confidence = min(abs(normalized_direction) * 1.5, 1.0)
                
                signals['overall_bias'] = {
                    'direction': direction,
                    'strength': abs(normalized_direction),
                    'confidence': confidence,
                    'contributing_signals': list(signals.keys())
                }
        
        # Update signals dictionary for this symbol
        self.signals[symbol] = signals
        
        return signals
    
    def get_volume_profile(self, symbol: str, num_bins: int = 10) -> Dict[str, Any]:
        """
        Get volume profile for a symbol.
        
        Args:
            symbol: Trading symbol
            num_bins: Number of price bins for volume profile
            
        Returns:
            Dict with volume profile data
        """
        if symbol not in self.trade_history or not self.trade_history[symbol]:
            return {}
        
        # Get trade data
        trades = list(self.trade_history[symbol])
        
        # Extract prices and volumes
        prices = [trade['price'] for trade in trades]
        volumes = [trade['amount'] for trade in trades]
        sides = [trade['side'].lower() for trade in trades]
        
        # Determine price range
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price == max_price:
            # Handle case where all prices are the same
            bin_edges = [min_price - 0.01, min_price + 0.01]
            num_bins = 1
        else:
            # Create price bins
            bin_edges = np.linspace(min_price, max_price, num_bins + 1)
        
        # Assign trades to bins
        bin_indices = np.digitize(prices, bin_edges) - 1
        
        # Initialize volume arrays
        total_volumes = np.zeros(num_bins)
        buy_volumes = np.zeros(num_bins)
        sell_volumes = np.zeros(num_bins)
        
        # Sum volumes by bin and side
        for i, (bin_idx, volume, side) in enumerate(zip(bin_indices, volumes, sides)):
            if 0 <= bin_idx < num_bins:  # Ensure index is valid
                total_volumes[bin_idx] += volume
                
                if side == 'buy':
                    buy_volumes[bin_idx] += volume
                else:
                    sell_volumes[bin_idx] += volume
        
        # Create profile data
        profile = {
            'price_levels': [],
            'volumes': [],
            'buy_volumes': [],
            'sell_volumes': [],
            'imbalances': []
        }
        
        for i in range(num_bins):
            # Calculate bin midpoint
            if i < len(bin_edges) - 1:
                price_level = (bin_edges[i] + bin_edges[i+1]) / 2
            else:
                price_level = bin_edges[i]
                
            total_vol = total_volumes[i]
            buy_vol = buy_volumes[i]
            sell_vol = sell_volumes[i]
            
            # Calculate imbalance
            imbalance = 0.0
            if total_vol > 0:
                imbalance = (buy_vol - sell_vol) / total_vol
            
            profile['price_levels'].append(price_level)
            profile['volumes'].append(total_vol)
            profile['buy_volumes'].append(buy_vol)
            profile['sell_volumes'].append(sell_vol)
            profile['imbalances'].append(imbalance)
        
        # Add VWAP
        vwap = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes) if volumes else 0
        profile['vwap'] = vwap
        
        # Add POC (Point of Control) - price level with highest volume
        if profile['volumes']:
            poc_idx = np.argmax(profile['volumes'])
            profile['poc'] = profile['price_levels'][poc_idx]
        else:
            profile['poc'] = 0
            
        return profile
    
    def get_trade_size_distribution(self, symbol: str, num_bins: int = 5) -> Dict[str, Any]:
        """
        Get distribution of trade sizes.
        
        Args:
            symbol: Trading symbol
            num_bins: Number of size bins
            
        Returns:
            Dict with trade size distribution data
        """
        if symbol not in self.trade_history or not self.trade_history[symbol]:
            return {}
        
        # Get trade data
        trades = list(self.trade_history[symbol])
        
        # Extract volumes and sides
        volumes = [trade['amount'] for trade in trades]
        sides = [trade['side'].lower() for trade in trades]
        
        if not volumes:
            return {}
        
        # Determine size ranges using percentiles
        percentiles = np.linspace(0, 100, num_bins + 1)
        size_edges = [np.percentile(volumes, p) for p in percentiles]
        
        # Ensure unique bin edges
        size_edges = sorted(set(size_edges))
        num_bins = len(size_edges) - 1
        
        # Assign trades to bins
        bin_indices = np.digitize(volumes, size_edges) - 1
        
        # Initialize count arrays
        total_counts = np.zeros(num_bins)
        buy_counts = np.zeros(num_bins)
        sell_counts = np.zeros(num_bins)
        
        # Count trades by bin and side
        for bin_idx, side in zip(bin_indices, sides):
            if 0 <= bin_idx < num_bins:  # Ensure index is valid
                total_counts[bin_idx] += 1
                
                if side == 'buy':
                    buy_counts[bin_idx] += 1
                else:
                    sell_counts[bin_idx] += 1
        
        # Create distribution data
        distribution = {
            'size_ranges': [],
            'counts': [],
            'buy_counts': [],
            'sell_counts': [],
            'imbalances': []
        }
        
        for i in range(num_bins):
            size_min = size_edges[i]
            size_max = size_edges[i+1]
            
            total_count = total_counts[i]
            buy_count = buy_counts[i]
            sell_count = sell_counts[i]
            
            # Calculate imbalance
            imbalance = 0.0
            if total_count > 0:
                imbalance = (buy_count - sell_count) / total_count
            
            distribution['size_ranges'].append([size_min, size_max])
            distribution['counts'].append(total_count)
            distribution['buy_counts'].append(buy_count)
            distribution['sell_counts'].append(sell_count)
            distribution['imbalances'].append(imbalance)
        
        return distribution
    
    def get_time_of_day_pattern(self, symbol: str, interval_minutes: int = 30) -> Dict[str, Any]:
        """
        Analyze trading patterns by time of day.
        
        Args:
            symbol: Trading symbol
            interval_minutes: Time interval in minutes
            
        Returns:
            Dict with time of day pattern data
        """
        if symbol not in self.trade_history or not self.trade_history[symbol]:
            return {}
        
        # Get trade data
        trades = list(self.trade_history[symbol])
        
        # Number of intervals in a day
        intervals_per_day = 24 * 60 // interval_minutes
        
        # Initialize arrays
        volumes = [0.0] * intervals_per_day
        counts = [0] * intervals_per_day
        buy_volumes = [0.0] * intervals_per_day
        sell_volumes = [0.0] * intervals_per_day
        
        # Process trades
        for trade in trades:
            # Convert timestamp to datetime
            dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
            
            # Calculate interval index
            minutes_since_midnight = dt.hour * 60 + dt.minute
            interval_idx = minutes_since_midnight // interval_minutes
            
            # Ensure valid index
            if 0 <= interval_idx < intervals_per_day:
                amount = trade['amount']
                side = trade['side'].lower()
                
                volumes[interval_idx] += amount
                counts[interval_idx] += 1
                
                if side == 'buy':
                    buy_volumes[interval_idx] += amount
                else:
                    sell_volumes[interval_idx] += amount
        
        # Create pattern data
        pattern = {
            'intervals': [],
            'volumes': [],
            'counts': [],
            'buy_volumes': [],
            'sell_volumes': [],
            'imbalances': []
        }
        
        for i in range(intervals_per_day):
            # Calculate time for this interval
            minutes = i * interval_minutes
            hour = minutes // 60
            minute = minutes % 60
            time_str = f"{hour:02d}:{minute:02d}"
            
            total_vol = volumes[i]
            count = counts[i]
            buy_vol = buy_volumes[i]
            sell_vol = sell_volumes[i]
            
            # Calculate imbalance
            imbalance = 0.0
            if total_vol > 0:
                imbalance = (buy_vol - sell_vol) / total_vol
            
            pattern['intervals'].append(time_str)
            pattern['volumes'].append(total_vol)
            pattern['counts'].append(count)
            pattern['buy_volumes'].append(buy_vol)
            pattern['sell_volumes'].append(sell_vol)
            pattern['imbalances'].append(imbalance)
        
        return pattern
    
    def to_dataframe(self, symbol: str) -> pd.DataFrame:
        """
        Convert trade history to a pandas DataFrame.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            DataFrame with trade data
        """
        if symbol not in self.trade_history:
            return pd.DataFrame()
        
        # Convert deque to list
        trades_list = list(self.trade_history[symbol])
        
        # Convert to DataFrame
        df = pd.DataFrame(trades_list)
        
        # Convert timestamp to datetime
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
        return df 