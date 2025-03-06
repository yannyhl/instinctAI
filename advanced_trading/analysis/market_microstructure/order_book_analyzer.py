"""
Order Book Analyzer Module

This module provides tools for analyzing order book data in real-time, 
including order book imbalance, depth analysis, and price pressure metrics.

The OrderBookAnalyzer class is the primary component for analyzing order book data
and providing insights for trading decisions.
"""

import time
import numpy as np
from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import datetime, timedelta
from collections import deque
import pandas as pd

from advanced_trading.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)

class OrderBookAnalyzer:
    """
    Analyzes order book data in real-time to detect patterns, predict market impact,
    and optimize order placement.
    
    This class provides comprehensive tools for:
    - Order book imbalance calculation
    - Depth analysis at different price levels
    - Buy/sell pressure detection
    - Order flow analysis
    - Liquidity profiling
    - Anomaly detection
    """
    
    def __init__(self, update_frequency_ms: int = 100, 
                 max_book_depth: int = 10,
                 history_window: int = 100,
                 anomaly_threshold: float = 2.5):
        """
        Initialize the OrderBookAnalyzer.
        
        Args:
            update_frequency_ms: Frequency of updates in milliseconds
            max_book_depth: Maximum depth of the order book to analyze
            history_window: Number of historical snapshots to keep
            anomaly_threshold: Z-score threshold for anomaly detection
        """
        self.update_frequency_ms = update_frequency_ms
        self.max_book_depth = max_book_depth
        self.history_window = history_window
        self.anomaly_threshold = anomaly_threshold
        
        # Order book state tracking
        self.book_snapshots = {}  # {symbol: deque of snapshots}
        self.current_books = {}   # {symbol: current book state}
        self.book_metrics = {}    # {symbol: {metric: value}}
        self.anomalies = {}       # {symbol: list of detected anomalies}
        self.predictions = {}     # {symbol: predicted price movements}
        
        # Initialize empty metrics
        self._initialize_metrics()
        
        logger.info(f"OrderBookAnalyzer initialized with update frequency {update_frequency_ms}ms, " 
                   f"max depth {max_book_depth}, history window {history_window}")
    
    def _initialize_metrics(self):
        """Initialize metrics dictionary with default values."""
        self.default_metrics = {
            # Imbalance metrics
            'bid_ask_imbalance': 0.0,
            'weighted_imbalance': 0.0,
            'volume_imbalance': 0.0,
            
            # Spread metrics
            'spread_absolute': 0.0,
            'spread_bps': 0.0,
            'spread_volatility': 0.0,
            
            # Depth metrics
            'bid_depth_usd': {},  # {level: depth}
            'ask_depth_usd': {},  # {level: depth}
            'depth_imbalance': {},  # {level: imbalance}
            'total_depth_usd': 0.0,
            
            # Order flow metrics
            'order_flow_imbalance': 0.0,
            'cancellation_rate': 0.0,
            'new_order_rate': 0.0,
            
            # Book pressure metrics
            'price_pressure': 0.0,
            'buying_pressure': 0.0,
            'selling_pressure': 0.0,
            
            # Liquidity metrics
            'liquidity_score': 0.0,
            'market_impact_estimate': 0.0,
            'liquidity_concentration': 0.0,
            
            # Timestamp
            'timestamp': 0
        }
    
    def process_order_book(self, symbol: str, order_book: Dict[str, Any], 
                         timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Process a new order book snapshot and update metrics.
        
        Args:
            symbol: Trading symbol
            order_book: Order book data with 'bids' and 'asks' lists of [price, quantity] pairs
            timestamp_ms: Timestamp in milliseconds (if None, current time is used)
        
        Returns:
            Dict with updated metrics and analysis results
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        
        # Ensure symbol is initialized in our trackers
        if symbol not in self.book_snapshots:
            self.book_snapshots[symbol] = deque(maxlen=self.history_window)
            self.current_books[symbol] = None
            self.book_metrics[symbol] = self.default_metrics.copy()
            self.anomalies[symbol] = []
            self.predictions[symbol] = {}
        
        # Store previous book for comparison
        previous_book = self.current_books[symbol]
        
        # Update current book state
        self.current_books[symbol] = {
            'bids': order_book.get('bids', [])[:self.max_book_depth],
            'asks': order_book.get('asks', [])[:self.max_book_depth],
            'timestamp': timestamp_ms
        }
        
        # Add to history
        self.book_snapshots[symbol].append(self.current_books[symbol])
        
        # Calculate metrics
        self._calculate_basic_metrics(symbol)
        self._calculate_imbalance_metrics(symbol)
        self._calculate_depth_metrics(symbol)
        
        # Only calculate these if we have a previous book to compare
        if previous_book:
            self._calculate_flow_metrics(symbol, previous_book)
            self._calculate_pressure_metrics(symbol, previous_book)
        
        # Anomaly detection
        anomalies = self._detect_anomalies(symbol)
        if anomalies:
            self.anomalies[symbol].extend(anomalies)
            # Trim anomalies list if too long
            if len(self.anomalies[symbol]) > 100:
                self.anomalies[symbol] = self.anomalies[symbol][-100:]
        
        # Price movement prediction
        self.predictions[symbol] = self._predict_price_movement(symbol)
        
        # Return relevant results
        return {
            'metrics': self.book_metrics[symbol],
            'anomalies': anomalies,
            'predictions': self.predictions[symbol]
        }
    
    def _calculate_basic_metrics(self, symbol: str) -> None:
        """Calculate basic metrics from the current order book."""
        book = self.current_books[symbol]
        bids = book['bids']
        asks = book['asks']
        
        if not bids or not asks:
            logger.warning(f"Empty order book for {symbol}")
            return
        
        # Best bid and ask prices
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        
        # Calculate spread
        spread_absolute = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        spread_bps = (spread_absolute / mid_price) * 10000  # Convert to basis points
        
        # Update metrics
        metrics = self.book_metrics[symbol]
        metrics['spread_absolute'] = spread_absolute
        metrics['spread_bps'] = spread_bps
        metrics['mid_price'] = mid_price
        metrics['best_bid'] = best_bid
        metrics['best_ask'] = best_ask
        metrics['timestamp'] = book['timestamp']
        
        # Calculate spread volatility if we have enough history
        if len(self.book_snapshots[symbol]) > 10:
            recent_spreads = [
                (s['asks'][0][0] - s['bids'][0][0]) / ((s['asks'][0][0] + s['bids'][0][0]) / 2) * 10000
                for s in list(self.book_snapshots[symbol])[-10:]
                if s['bids'] and s['asks']
            ]
            if recent_spreads:
                metrics['spread_volatility'] = np.std(recent_spreads)
    
    def _calculate_imbalance_metrics(self, symbol: str) -> None:
        """Calculate order book imbalance metrics."""
        book = self.current_books[symbol]
        bids = book['bids']
        asks = book['asks']
        metrics = self.book_metrics[symbol]
        
        if not bids or not asks:
            return
        
        # Calculate volume at best bid/ask
        bid_volume = sum(bid[1] for bid in bids)
        ask_volume = sum(ask[1] for ask in asks)
        total_volume = bid_volume + ask_volume
        
        # Simple imbalance ratio
        if total_volume > 0:
            bid_ratio = bid_volume / total_volume
            ask_ratio = ask_volume / total_volume
            imbalance = bid_ratio - ask_ratio  # Range: -1 to 1
        else:
            bid_ratio = ask_ratio = 0.5
            imbalance = 0
        
        # Weighted imbalance (giving more weight to prices closer to mid)
        mid_price = metrics['mid_price']
        
        weighted_bid_volume = 0
        for bid in bids:
            # Price distance from mid as a percentage
            price_distance = (mid_price - bid[0]) / mid_price
            # Weight decreases as we get further from mid
            weight = max(0, 1 - (price_distance * 5))  # 5x multiplier for steeper decay
            weighted_bid_volume += bid[1] * weight
        
        weighted_ask_volume = 0
        for ask in asks:
            price_distance = (ask[0] - mid_price) / mid_price
            weight = max(0, 1 - (price_distance * 5))
            weighted_ask_volume += ask[1] * weight
        
        weighted_total = weighted_bid_volume + weighted_ask_volume
        if weighted_total > 0:
            weighted_imbalance = (weighted_bid_volume - weighted_ask_volume) / weighted_total
        else:
            weighted_imbalance = 0
        
        # Update metrics
        metrics['bid_volume'] = bid_volume
        metrics['ask_volume'] = ask_volume
        metrics['total_volume'] = total_volume
        metrics['bid_ask_imbalance'] = imbalance
        metrics['weighted_imbalance'] = weighted_imbalance
        metrics['bid_ratio'] = bid_ratio
        metrics['ask_ratio'] = ask_ratio
    
    def _calculate_depth_metrics(self, symbol: str) -> None:
        """Calculate order book depth metrics at different price levels."""
        book = self.current_books[symbol]
        bids = book['bids']
        asks = book['asks']
        metrics = self.book_metrics[symbol]
        
        if not bids or not asks:
            return
        
        mid_price = metrics['mid_price']
        
        # Define price levels (percentage from mid price)
        price_levels = [0.1, 0.2, 0.5, 1.0, 2.0]  # percent
        bid_depth = {level: 0 for level in price_levels}
        ask_depth = {level: 0 for level in price_levels}
        
        # Calculate depth at each level
        for bid in bids:
            price_distance_pct = (mid_price - bid[0]) / mid_price * 100
            for level in price_levels:
                if price_distance_pct <= level:
                    bid_depth[level] += bid[1] * bid[0]  # Convert to USD value
        
        for ask in asks:
            price_distance_pct = (ask[0] - mid_price) / mid_price * 100
            for level in price_levels:
                if price_distance_pct <= level:
                    ask_depth[level] += ask[1] * ask[0]  # Convert to USD value
        
        # Calculate depth imbalance at each level
        depth_imbalance = {}
        for level in price_levels:
            total_depth = bid_depth[level] + ask_depth[level]
            if total_depth > 0:
                depth_imbalance[level] = (bid_depth[level] - ask_depth[level]) / total_depth
            else:
                depth_imbalance[level] = 0
        
        # Total depth in USD
        total_depth_usd = sum(bid[0] * bid[1] for bid in bids) + sum(ask[0] * ask[1] for ask in asks)
        
        # Update metrics
        metrics['bid_depth_usd'] = bid_depth
        metrics['ask_depth_usd'] = ask_depth
        metrics['depth_imbalance'] = depth_imbalance
        metrics['total_depth_usd'] = total_depth_usd
    
    def _calculate_flow_metrics(self, symbol: str, previous_book: Dict[str, Any]) -> None:
        """Calculate order flow metrics by comparing with previous book."""
        current_book = self.current_books[symbol]
        current_bids = current_book['bids']
        current_asks = current_book['asks']
        previous_bids = previous_book['bids']
        previous_asks = previous_book['asks']
        metrics = self.book_metrics[symbol]
        
        if not current_bids or not current_asks or not previous_bids or not previous_asks:
            return
        
        # Create price-indexed dictionaries for easier comparison
        prev_bid_dict = {bid[0]: bid[1] for bid in previous_bids}
        prev_ask_dict = {ask[0]: ask[1] for ask in previous_asks}
        curr_bid_dict = {bid[0]: bid[1] for bid in current_bids}
        curr_ask_dict = {ask[0]: ask[1] for ask in current_asks}
        
        # Track changes
        new_bid_volume = 0
        cancelled_bid_volume = 0
        new_ask_volume = 0
        cancelled_ask_volume = 0
        
        # Detect new bids and cancelled bids
        for price, volume in curr_bid_dict.items():
            if price not in prev_bid_dict:
                new_bid_volume += volume
            elif volume > prev_bid_dict[price]:
                new_bid_volume += (volume - prev_bid_dict[price])
        
        for price, volume in prev_bid_dict.items():
            if price not in curr_bid_dict:
                cancelled_bid_volume += volume
            elif volume > curr_bid_dict[price]:
                cancelled_bid_volume += (volume - curr_bid_dict[price])
        
        # Detect new asks and cancelled asks
        for price, volume in curr_ask_dict.items():
            if price not in prev_ask_dict:
                new_ask_volume += volume
            elif volume > prev_ask_dict[price]:
                new_ask_volume += (volume - prev_ask_dict[price])
        
        for price, volume in prev_ask_dict.items():
            if price not in curr_ask_dict:
                cancelled_ask_volume += volume
            elif volume > curr_ask_dict[price]:
                cancelled_ask_volume += (volume - curr_ask_dict[price])
        
        # Calculate metrics
        total_new_volume = new_bid_volume + new_ask_volume
        total_cancelled_volume = cancelled_bid_volume + cancelled_ask_volume
        
        if total_new_volume > 0:
            order_flow_imbalance = (new_bid_volume - new_ask_volume) / total_new_volume
        else:
            order_flow_imbalance = 0
        
        total_volume = metrics['total_volume']
        if total_volume > 0:
            new_order_rate = total_new_volume / total_volume
            cancellation_rate = total_cancelled_volume / total_volume
        else:
            new_order_rate = 0
            cancellation_rate = 0
        
        # Update metrics
        metrics['order_flow_imbalance'] = order_flow_imbalance
        metrics['new_order_rate'] = new_order_rate
        metrics['cancellation_rate'] = cancellation_rate
        metrics['new_bid_volume'] = new_bid_volume
        metrics['new_ask_volume'] = new_ask_volume
        metrics['cancelled_bid_volume'] = cancelled_bid_volume
        metrics['cancelled_ask_volume'] = cancelled_ask_volume
    
    def _calculate_pressure_metrics(self, symbol: str, previous_book: Dict[str, Any]) -> None:
        """Calculate price pressure metrics based on order book changes."""
        current_book = self.current_books[symbol]
        metrics = self.book_metrics[symbol]
        
        # Calculate pressure based on recent price moves and book imbalance
        if len(self.book_snapshots[symbol]) >= 5:
            recent_books = list(self.book_snapshots[symbol])[-5:]
            
            # Track mid price changes
            mid_prices = []
            for book in recent_books:
                if book['bids'] and book['asks']:
                    mid = (book['bids'][0][0] + book['asks'][0][0]) / 2
                    mid_prices.append(mid)
            
            # Calculate metrics if we have enough data
            if len(mid_prices) >= 3:
                # Price trend
                price_changes = [mid_prices[i] - mid_prices[i-1] for i in range(1, len(mid_prices))]
                avg_price_change = sum(price_changes) / len(price_changes)
                
                # Normalize by volatility
                if metrics['spread_volatility'] > 0:
                    normalized_change = avg_price_change / metrics['spread_volatility']
                else:
                    normalized_change = avg_price_change
                
                # Combine with imbalance for pressure metric
                imbalance = metrics['weighted_imbalance']
                price_pressure = (normalized_change * 0.7) + (imbalance * 0.3)
                
                # Buying and selling pressure
                buying_pressure = max(0, price_pressure)
                selling_pressure = max(0, -price_pressure)
                
                # Update metrics
                metrics['price_pressure'] = price_pressure
                metrics['buying_pressure'] = buying_pressure
                metrics['selling_pressure'] = selling_pressure
    
    def _detect_anomalies(self, symbol: str) -> List[Dict[str, Any]]:
        """Detect anomalies in the order book."""
        metrics = self.book_metrics[symbol]
        anomalies = []
        
        # Need sufficient history
        if len(self.book_snapshots[symbol]) < 10:
            return anomalies
        
        # Get recent metrics for comparison
        recent_books = list(self.book_snapshots[symbol])[-10:]
        
        # Check for spread anomalies
        recent_spreads = [
            (s['asks'][0][0] - s['bids'][0][0]) / ((s['asks'][0][0] + s['bids'][0][0]) / 2) * 10000
            for s in recent_books if s['bids'] and s['asks']
        ]
        
        if recent_spreads:
            avg_spread = sum(recent_spreads) / len(recent_spreads)
            std_spread = np.std(recent_spreads) if len(recent_spreads) > 1 else 1.0
            
            if std_spread > 0:
                spread_z_score = (metrics['spread_bps'] - avg_spread) / std_spread
                
                # Detect anomalous spread
                if abs(spread_z_score) > self.anomaly_threshold:
                    anomalies.append({
                        'type': 'spread_anomaly',
                        'value': metrics['spread_bps'],
                        'avg_value': avg_spread,
                        'z_score': spread_z_score,
                        'direction': 'widening' if spread_z_score > 0 else 'narrowing',
                        'timestamp': metrics['timestamp']
                    })
        
        # Check for imbalance anomalies
        recent_imbalances = []
        for s in recent_books:
            if s['bids'] and s['asks']:
                bid_vol = sum(bid[1] for bid in s['bids'])
                ask_vol = sum(ask[1] for ask in s['asks'])
                total = bid_vol + ask_vol
                if total > 0:
                    imb = (bid_vol - ask_vol) / total
                    recent_imbalances.append(imb)
        
        if recent_imbalances:
            avg_imbalance = sum(recent_imbalances) / len(recent_imbalances)
            std_imbalance = np.std(recent_imbalances) if len(recent_imbalances) > 1 else 0.1
            
            if std_imbalance > 0:
                imbalance_z_score = (metrics['bid_ask_imbalance'] - avg_imbalance) / std_imbalance
                
                # Detect anomalous imbalance
                if abs(imbalance_z_score) > self.anomaly_threshold:
                    anomalies.append({
                        'type': 'imbalance_anomaly',
                        'value': metrics['bid_ask_imbalance'],
                        'avg_value': avg_imbalance,
                        'z_score': imbalance_z_score,
                        'direction': 'buy_pressure' if imbalance_z_score > 0 else 'sell_pressure',
                        'timestamp': metrics['timestamp']
                    })
        
        # Check for depth anomalies
        recent_depths = [
            sum(sum(bid[0] * bid[1] for bid in s['bids']) + sum(ask[0] * ask[1] for ask in s['asks']))
            for s in recent_books if s['bids'] and s['asks']
        ]
        
        if recent_depths:
            avg_depth = sum(recent_depths) / len(recent_depths)
            std_depth = np.std(recent_depths) if len(recent_depths) > 1 else avg_depth * 0.1
            
            if std_depth > 0 and avg_depth > 0:
                depth_z_score = (metrics['total_depth_usd'] - avg_depth) / std_depth
                
                # Detect anomalous depth
                if abs(depth_z_score) > self.anomaly_threshold:
                    anomalies.append({
                        'type': 'depth_anomaly',
                        'value': metrics['total_depth_usd'],
                        'avg_value': avg_depth,
                        'z_score': depth_z_score,
                        'direction': 'increasing' if depth_z_score > 0 else 'decreasing',
                        'timestamp': metrics['timestamp']
                    })
        
        return anomalies
    
    def _predict_price_movement(self, symbol: str) -> Dict[str, Any]:
        """Predict short-term price movement based on order book metrics."""
        metrics = self.book_metrics[symbol]
        
        # Need metrics to proceed
        if not metrics or 'weighted_imbalance' not in metrics:
            return {
                'direction': 'neutral',
                'confidence': 0.0,
                'horizon_ms': 1000,
                'timestamp': int(time.time() * 1000)
            }
        
        # Combine signals for prediction
        signals = []
        weights = []
        
        # Imbalance signal
        if 'weighted_imbalance' in metrics:
            signals.append(metrics['weighted_imbalance'])
            weights.append(0.4)  # 40% weight
        
        # Price pressure
        if 'price_pressure' in metrics:
            signals.append(metrics['price_pressure'])
            weights.append(0.3)  # 30% weight
        
        # Order flow imbalance
        if 'order_flow_imbalance' in metrics:
            signals.append(metrics['order_flow_imbalance'])
            weights.append(0.2)  # 20% weight
        
        # Depth imbalance at closest level
        if 'depth_imbalance' in metrics and 0.1 in metrics['depth_imbalance']:
            signals.append(metrics['depth_imbalance'][0.1])
            weights.append(0.1)  # 10% weight
        
        # Calculate combined signal
        if signals and weights:
            # Normalize weights
            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w / total_weight for w in weights]
            
            # Weighted average
            combined_signal = sum(s * w for s, w in zip(signals, weights))
            
            # Convert to direction and confidence
            confidence = min(abs(combined_signal) * 2, 1.0)  # Scale to 0-1
            
            if combined_signal > 0.05:
                direction = "up"
            elif combined_signal < -0.05:
                direction = "down"
            else:
                direction = "neutral"
                confidence = min(confidence, 0.3)  # Cap confidence for neutral signals
            
            # Adjust prediction horizon based on confidence
            horizon_ms = int(1000 * (1.0 - confidence * 0.7))  # 300ms to 1000ms
            
            return {
                'direction': direction,
                'confidence': confidence,
                'signal_strength': combined_signal,
                'horizon_ms': horizon_ms,
                'timestamp': metrics['timestamp']
            }
        
        # Default prediction if we don't have enough data
        return {
            'direction': 'neutral',
            'confidence': 0.0,
            'horizon_ms': 1000,
            'timestamp': metrics['timestamp']
        }
    
    def get_optimal_order_params(self, symbol: str, side: str, size: float, 
                               urgency: float = 0.5) -> Dict[str, Any]:
        """
        Determine optimal order parameters based on current order book state.
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            size: Order size
            urgency: Execution urgency (0.0-1.0)
            
        Returns:
            Dict with optimal order parameters
        """
        if symbol not in self.book_metrics:
            logger.warning(f"No order book metrics available for {symbol}")
            return None
        
        metrics = self.book_metrics[symbol]
        
        # Need basic metrics
        if 'best_bid' not in metrics or 'best_ask' not in metrics:
            return None
        
        # Get current book state
        best_bid = metrics['best_bid']
        best_ask = metrics['best_ask']
        spread = metrics['spread_absolute']
        mid_price = metrics['mid_price']
        
        # Estimate market impact based on order size and book depth
        market_impact = self._estimate_market_impact(symbol, side, size)
        
        # Determine base price based on side
        if side.lower() == 'buy':
            base_price = best_ask
            direction = 1
        else:
            base_price = best_bid
            direction = -1
        
        # Adjust price based on urgency
        # High urgency = willing to cross spread, low urgency = passive order
        price_adjustment = spread * (urgency - 0.5) * 1.5
        
        # Further adjust based on imbalance (if favorable)
        imbalance_adjustment = 0
        if 'weighted_imbalance' in metrics:
            imb = metrics['weighted_imbalance']
            if (side.lower() == 'buy' and imb < 0) or (side.lower() == 'sell' and imb > 0):
                # Favorable imbalance, can be more passive
                imbalance_adjustment = -spread * abs(imb) * 0.5
            else:
                # Unfavorable imbalance, need to be more aggressive
                imbalance_adjustment = spread * abs(imb) * 0.3
        
        # Calculate optimal price
        optimal_price = base_price + direction * (price_adjustment + imbalance_adjustment)
        
        # Determine order type based on urgency
        if urgency > 0.8:
            order_type = 'market'
        elif urgency > 0.5:
            order_type = 'limit'
        else:
            order_type = 'post_only'
        
        # Check for price improvement opportunities
        price_improvement = False
        if 'weighted_imbalance' in metrics and abs(metrics['weighted_imbalance']) > 0.6:
            price_improvement = True
        
        # Return optimal parameters
        return {
            'symbol': symbol,
            'side': side,
            'size': size,
            'optimal_price': optimal_price,
            'order_type': order_type,
            'estimated_impact': market_impact,
            'price_improvement_opportunity': price_improvement,
            'urgency_signal': urgency + (imbalance_adjustment / spread if spread > 0 else 0),
            'timestamp': metrics['timestamp']
        }
    
    def _estimate_market_impact(self, symbol: str, side: str, size: float) -> float:
        """
        Estimate market impact for a given order size.
        
        Returns:
            Estimated price impact in basis points
        """
        if symbol not in self.book_metrics:
            return 10.0  # Default impact estimate (10 bps)
        
        metrics = self.book_metrics[symbol]
        
        # Get relevant depth based on side
        depth_key = 'bid_depth_usd' if side.lower() == 'sell' else 'ask_depth_usd'
        if depth_key not in metrics:
            return 10.0
        
        depth = metrics[depth_key]
        
        # Convert size to approximate USD
        if 'mid_price' in metrics:
            size_usd = size * metrics['mid_price']
        else:
            return 10.0
        
        # Basic impact estimation based on available liquidity
        impact_bps = 0
        remaining_size = size_usd
        
        # Check each depth level
        for level in sorted(depth.keys()):
            level_depth = depth[level]
            
            if level_depth >= remaining_size:
                # This level has enough liquidity
                impact_bps += (level / 0.1) * (remaining_size / level_depth) * 5
                remaining_size = 0
                break
            else:
                # Use all liquidity at this level and move to next
                impact_bps += (level / 0.1) * 5
                remaining_size -= level_depth
        
        # If we still have remaining size, add additional impact
        if remaining_size > 0:
            # If we couldn't satisfy the order with visible liquidity, higher impact
            impact_bps += 20  # Base penalty for exceeding visible liquidity
            
            # Scale based on how much exceeds visible liquidity
            total_visible = sum(depth.values())
            if total_visible > 0:
                excess_ratio = remaining_size / total_visible
                impact_bps += excess_ratio * 50  # 50 bps for each multiple of visible liquidity
        
        return impact_bps
    
    def get_historical_metrics(self, symbol: str, metric_name: str, lookback: int = 100) -> List[float]:
        """Get historical values for a specific metric."""
        if symbol not in self.book_snapshots:
            return []
        
        history = list(self.book_snapshots[symbol])[-lookback:]
        values = []
        
        for idx, snapshot in enumerate(history):
            # For basic metrics available in the snapshot
            if metric_name in ['spread', 'mid_price']:
                if not snapshot['bids'] or not snapshot['asks']:
                    continue
                
                if metric_name == 'spread':
                    values.append(snapshot['asks'][0][0] - snapshot['bids'][0][0])
                elif metric_name == 'mid_price':
                    values.append((snapshot['asks'][0][0] + snapshot['bids'][0][0]) / 2)
            
            # For complex metrics we need to reconstruct from snapshots
            # This would require re-calculating metrics for each historical snapshot
            # For simplicity, we'll just return empty list for now
            # A more complete implementation would cache metrics with each snapshot
        
        return values
    
    def get_liquidity_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Get a comprehensive liquidity profile for a symbol.
        
        Returns:
            Dict with liquidity metrics
        """
        if symbol not in self.book_metrics:
            return {}
        
        metrics = self.book_metrics[symbol]
        
        # Extract relevant liquidity metrics
        profile = {
            'spreads': {
                'absolute': metrics.get('spread_absolute', 0),
                'bps': metrics.get('spread_bps', 0),
                'volatility': metrics.get('spread_volatility', 0)
            },
            'depth': {
                'total_usd': metrics.get('total_depth_usd', 0),
                'bid_depth': metrics.get('bid_depth_usd', {}),
                'ask_depth': metrics.get('ask_depth_usd', {}),
                'imbalance': metrics.get('depth_imbalance', {})
            },
            'order_flow': {
                'imbalance': metrics.get('order_flow_imbalance', 0),
                'new_order_rate': metrics.get('new_order_rate', 0),
                'cancellation_rate': metrics.get('cancellation_rate', 0)
            }
        }
        
        # Add market impact estimates for standard sizes
        typical_sizes = [0.1, 0.5, 1.0, 5.0, 10.0]  # in BTC or ETH equivalent
        impact_buy = {}
        impact_sell = {}
        
        for size in typical_sizes:
            impact_buy[str(size)] = self._estimate_market_impact(symbol, 'buy', size)
            impact_sell[str(size)] = self._estimate_market_impact(symbol, 'sell', size)
        
        profile['impact_estimates'] = {
            'buy': impact_buy,
            'sell': impact_sell
        }
        
        # Add timestamp
        profile['timestamp'] = metrics.get('timestamp', int(time.time() * 1000))
        
        return profile
    
    def to_dataframe(self, symbol: str, lookback: int = 100) -> pd.DataFrame:
        """
        Convert order book metrics history to a pandas DataFrame.
        
        Args:
            symbol: Trading symbol
            lookback: Number of historical snapshots to include
            
        Returns:
            DataFrame with order book metrics
        """
        if symbol not in self.book_snapshots:
            return pd.DataFrame()
        
        # This would require storing metrics with each snapshot
        # For now, return an empty DataFrame
        # A more complete implementation would track metrics history
        
        return pd.DataFrame() 