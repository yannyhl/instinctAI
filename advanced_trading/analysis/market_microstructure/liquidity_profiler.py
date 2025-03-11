"""
Liquidity Profiler Module

This module provides tools for analyzing market liquidity, including
bid-ask spread analysis, depth profiling, and impact cost estimation.

The LiquidityProfiler class is the primary component for analyzing and
tracking market liquidity over time.
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

class LiquidityProfiler:
    """
    Analyzes market liquidity conditions including bid-ask spreads, depth,
    and transaction costs.
    
    This class provides comprehensive tools for:
    - Bid-ask spread analysis
    - Market depth profiling
    - Liquidity cost estimation
    - Resiliency measurement
    - Liquidity trend tracking
    - Market impact prediction
    """
    
    def __init__(self, 
                 history_window: int = 1000,
                 depth_levels: int = 10,
                 impact_size_tiers: List[float] = None,
                 impact_confidence_interval: float = 0.95,
                 time_window_seconds: int = 3600):
        """
        Initialize the LiquidityProfiler.
        
        Args:
            history_window: Number of snapshots to keep in history
            depth_levels: Number of price levels to analyze in order book
            impact_size_tiers: List of order sizes for impact calculation (% of daily volume)
            impact_confidence_interval: Confidence interval for impact estimates
            time_window_seconds: Time window in seconds for liquidity analysis
        """
        self.history_window = history_window
        self.depth_levels = depth_levels
        self.impact_size_tiers = impact_size_tiers or [0.001, 0.005, 0.01, 0.05, 0.1]  # 0.1% to 10%
        self.impact_confidence_interval = impact_confidence_interval
        self.time_window_seconds = time_window_seconds
        
        # Liquidity tracking
        self.snapshots = {}             # {symbol: deque of {timestamp, metrics}}
        self.current_profiles = {}      # {symbol: current liquidity profile}
        self.daily_stats = {}           # {symbol: {volume, count, etc.}}
        self.resilience_metrics = {}    # {symbol: {recovery time, etc.}}
        
        # Initialize empty metrics
        self._initialize_metrics()
        
        logger.info(f"LiquidityProfiler initialized with history window {history_window}, "
                  f"depth levels {depth_levels}, time window {time_window_seconds}s")
    
    def _initialize_metrics(self):
        """Initialize metrics dictionary with default values."""
        self.default_profile = {
            # Spread metrics
            'bid_ask_spread': 0.0,      # Absolute spread
            'relative_spread': 0.0,     # Spread as percentage of mid price
            'effective_spread': 0.0,    # Volume-weighted effective spread
            'time_weighted_spread': 0.0, # Time-weighted average spread
            'spread_volatility': 0.0,   # Standard deviation of spread
            
            # Depth metrics
            'depth_at_best': {
                'bid_volume': 0.0,
                'ask_volume': 0.0,
                'total': 0.0,
                'imbalance': 0.0
            },
            'depth_by_level': [],       # List of depth at each level
            'total_depth': {
                'bid_volume': 0.0,
                'ask_volume': 0.0,
                'total': 0.0,
                'imbalance': 0.0
            },
            'depth_distribution': [],   # Distribution of liquidity by price level
            
            # Volume metrics
            'recent_volume': 0.0,       # Volume in recent time window
            'volume_profile': {},       # Volume by price level
            'turnover_ratio': 0.0,      # Volume / available liquidity
            
            # Liquidity cost metrics
            'impact_estimates': {},     # Estimated impact by order size
            'liquidity_score': 0.0,     # Composite liquidity score
            'transacted_costs': {},     # Actual costs from transactions
            
            # Other metrics
            'mid_price': 0.0,           # Mid price
            'quote_quality': 0.0,       # Measure of quote stability
            'timestamp': 0              # Unix timestamp in ms
        }
        
        self.default_daily_stats = {
            'open_time': 0,             # Start time of the daily window
            'close_time': 0,            # End time of the daily window
            'total_volume': 0.0,        # Total traded volume
            'trade_count': 0,           # Number of trades
            'avg_trade_size': 0.0,      # Average trade size
            'avg_spread': 0.0,          # Average spread
            'min_spread': float('inf'), # Minimum spread
            'max_spread': 0.0,          # Maximum spread
            'avg_depth': 0.0,           # Average depth
            'min_depth': float('inf'),  # Minimum depth
            'max_depth': 0.0,           # Maximum depth
            'spread_series': [],        # Time series of spreads
            'depth_series': [],         # Time series of depths
            'volume_by_hour': {}        # Volume distributed by hour
        }
        
        self.default_resilience = {
            'shock_events': [],         # List of liquidity shock events
            'avg_recovery_time': 0.0,   # Average time to recover from shocks
            'avg_shock_magnitude': 0.0, # Average magnitude of shocks
            'shock_frequency': 0.0      # Shocks per day
        }
    
    def process_order_book(self, symbol: str, order_book: Dict[str, Any],
                         timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Process a new order book snapshot and update liquidity metrics.
        
        Args:
            symbol: Trading symbol
            order_book: Order book data with 'bids' and 'asks' lists of [price, quantity] pairs
            timestamp_ms: Timestamp in milliseconds (if None, current time is used)
            
        Returns:
            Dict with updated liquidity profile
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
            
        # Ensure symbol is initialized in our trackers
        if symbol not in self.snapshots:
            self.snapshots[symbol] = deque(maxlen=self.history_window)
            self.current_profiles[symbol] = self.default_profile.copy()
            self.daily_stats[symbol] = self.default_daily_stats.copy()
            self.resilience_metrics[symbol] = self.default_resilience.copy()
        
        # Calculate liquidity metrics
        profile = self._calculate_liquidity_metrics(symbol, order_book, timestamp_ms)
        
        # Store the snapshot
        self.snapshots[symbol].append({
            'timestamp': timestamp_ms,
            'profile': profile,
            'bids': order_book.get('bids', [])[:self.depth_levels],
            'asks': order_book.get('asks', [])[:self.depth_levels]
        })
        
        # Update current profile
        self.current_profiles[symbol] = profile
        
        # Update daily stats if needed
        self._update_daily_stats(symbol, profile)
        
        # Detect liquidity shocks if we have enough history
        if len(self.snapshots[symbol]) > 10:
            self._detect_liquidity_shocks(symbol)
        
        return profile
    
    def process_trade(self, symbol: str, trade: Dict[str, Any]) -> None:
        """
        Process a new trade for liquidity impact analysis.
        
        Args:
            symbol: Trading symbol
            trade: Trade data with required fields:
                - price: Trade price
                - amount: Trade amount/quantity
                - side: 'buy' or 'sell'
                - timestamp: Trade timestamp in milliseconds
        """
        # Ensure symbol is initialized
        if symbol not in self.daily_stats:
            self.daily_stats[symbol] = self.default_daily_stats.copy()
        
        # Update daily stats
        stats = self.daily_stats[symbol]
        stats['total_volume'] += trade['amount']
        stats['trade_count'] += 1
        
        # Calculate average trade size
        if stats['trade_count'] > 0:
            stats['avg_trade_size'] = stats['total_volume'] / stats['trade_count']
        
        # Update volume by hour
        hour = datetime.fromtimestamp(trade['timestamp'] / 1000).hour
        if hour not in stats['volume_by_hour']:
            stats['volume_by_hour'][hour] = 0.0
        stats['volume_by_hour'][hour] += trade['amount']
        
        # TODO: Calculate actual market impact from trades
        # This would require comparing the trade with the order book before the trade
    
    def _calculate_liquidity_metrics(self, symbol: str, order_book: Dict[str, Any],
                                  timestamp_ms: int) -> Dict[str, Any]:
        """Calculate liquidity metrics from order book snapshot."""
        profile = self.default_profile.copy()
        profile['timestamp'] = timestamp_ms
        
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        if not bids or not asks:
            logger.warning(f"Empty order book for {symbol}")
            return profile
        
        # Sort bids and asks (descending for bids, ascending for asks)
        bids = sorted(bids, key=lambda x: x[0], reverse=True)
        asks = sorted(asks, key=lambda x: x[0])
        
        # Calculate basic spread metrics
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2
        
        spread = best_ask - best_bid
        relative_spread = spread / mid_price if mid_price > 0 else 0
        
        profile['bid_ask_spread'] = spread
        profile['relative_spread'] = relative_spread
        profile['mid_price'] = mid_price
        
        # Calculate depth at best
        best_bid_volume = bids[0][1]
        best_ask_volume = asks[0][1]
        best_total = best_bid_volume + best_ask_volume
        
        profile['depth_at_best'] = {
            'bid_volume': best_bid_volume,
            'ask_volume': best_ask_volume,
            'total': best_total,
            'imbalance': (best_bid_volume - best_ask_volume) / best_total if best_total > 0 else 0
        }
        
        # Calculate depth by level (up to depth_levels)
        depth_by_level = []
        bid_volume_sum = 0.0
        ask_volume_sum = 0.0
        
        for i in range(min(self.depth_levels, max(len(bids), len(asks)))):
            bid_price = bids[i][0] if i < len(bids) else 0
            ask_price = asks[i][0] if i < len(asks) else 0
            bid_volume = bids[i][1] if i < len(bids) else 0
            ask_volume = asks[i][1] if i < len(asks) else 0
            
            bid_volume_sum += bid_volume
            ask_volume_sum += ask_volume
            
            level_total = bid_volume + ask_volume
            level_imbalance = (bid_volume - ask_volume) / level_total if level_total > 0 else 0
            
            depth_by_level.append({
                'level': i + 1,
                'bid_price': bid_price,
                'ask_price': ask_price,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'total': level_total,
                'imbalance': level_imbalance
            })
        
        profile['depth_by_level'] = depth_by_level
        
        # Calculate total depth
        total_bid_volume = sum(bid[1] for bid in bids)
        total_ask_volume = sum(ask[1] for ask in asks)
        total_depth = total_bid_volume + total_ask_volume
        
        profile['total_depth'] = {
            'bid_volume': total_bid_volume,
            'ask_volume': total_ask_volume,
            'total': total_depth,
            'imbalance': (total_bid_volume - total_ask_volume) / total_depth if total_depth > 0 else 0
        }
        
        # Calculate depth distribution (percentage of liquidity at each level)
        if total_depth > 0:
            distribution = []
            for i, level in enumerate(depth_by_level):
                level_pct = (level['bid_volume'] + level['ask_volume']) / total_depth
                distribution.append(level_pct)
            profile['depth_distribution'] = distribution
        
        # Calculate effective spread (weighted by volume)
        volume_weighted_midpoint = 0.0
        total_weight = 0.0
        
        for i, level in enumerate(depth_by_level):
            bid_midpoint = (level['bid_price'] + mid_price) / 2
            ask_midpoint = (level['ask_price'] + mid_price) / 2
            
            # Weight by volume
            bid_weight = level['bid_volume']
            ask_weight = level['ask_volume']
            
            volume_weighted_midpoint += bid_midpoint * bid_weight + ask_midpoint * ask_weight
            total_weight += bid_weight + ask_weight
        
        if total_weight > 0:
            volume_weighted_midpoint /= total_weight
            
            # Calculate effective spread
            effective_spread = abs(best_ask - volume_weighted_midpoint) + abs(best_bid - volume_weighted_midpoint)
            profile['effective_spread'] = effective_spread
        
        # Estimate market impact for different order sizes
        impact_estimates = {}
        for size_pct in self.impact_size_tiers:
            # Convert percentage to absolute size (estimate)
            estimated_volume = 0.0
            if symbol in self.daily_stats:
                estimated_volume = self.daily_stats[symbol]['total_volume']
            
            size = max(estimated_volume * size_pct, 1.0)  # Ensure minimum size
            
            # Calculate impact for buys and sells
            buy_impact = self._estimate_market_impact(bids, size, 'buy')
            sell_impact = self._estimate_market_impact(asks, size, 'sell')
            
            impact_estimates[str(size_pct)] = {
                'size_pct': size_pct,
                'size': size,
                'buy_impact_bps': buy_impact,
                'sell_impact_bps': sell_impact,
                'avg_impact_bps': (buy_impact + sell_impact) / 2
            }
        
        profile['impact_estimates'] = impact_estimates
        
        # Calculate liquidity score (1-10 scale, higher is more liquid)
        # Based on spread, depth, and impact metrics
        
        # Normalize spread (lower is better)
        norm_spread = min(1.0, relative_spread * 100)  # Cap at 1% = 100 bps
        spread_score = max(0, 10 - norm_spread * 10)
        
        # Normalize depth (higher is better)
        # We'll use depth relative to average trade size
        avg_trade_size = 1.0
        if symbol in self.daily_stats and self.daily_stats[symbol]['avg_trade_size'] > 0:
            avg_trade_size = self.daily_stats[symbol]['avg_trade_size']
        
        depth_ratio = min(100, total_depth / avg_trade_size)  # Cap at 100x avg trade size
        depth_score = min(10, depth_ratio / 10)
        
        # Impact score (lower impact is better)
        impact_score = 0.0
        if impact_estimates:
            # Use middle tier impact (e.g., 1% of daily volume)
            middle_tier = self.impact_size_tiers[len(self.impact_size_tiers) // 2]
            avg_impact = impact_estimates[str(middle_tier)]['avg_impact_bps']
            impact_score = max(0, 10 - avg_impact / 10)  # 100 bps impact = 0 score
        
        # Combine scores with weights
        liquidity_score = 0.4 * spread_score + 0.3 * depth_score + 0.3 * impact_score
        profile['liquidity_score'] = liquidity_score
        
        # Additional metrics when we have history
        if len(self.snapshots[symbol]) > 1:
            # Calculate spread volatility
            recent_snapshots = list(self.snapshots[symbol])[-min(20, len(self.snapshots[symbol])):]
            spreads = [s['profile']['bid_ask_spread'] for s in recent_snapshots]
            
            if spreads:
                profile['spread_volatility'] = np.std(spreads)
                
                # Calculate time weighted spread (newer snapshots have more weight)
                weights = np.linspace(0.5, 1.0, len(spreads))
                weights /= np.sum(weights)  # Normalize
                
                profile['time_weighted_spread'] = np.sum(np.array(spreads) * weights)
        
        return profile
    
    def _estimate_market_impact(self, orders: List[List[float]], size: float, side: str) -> float:
        """
        Estimate market impact for a given order size in basis points.
        
        Args:
            orders: List of [price, quantity] pairs (bids for selling, asks for buying)
            size: Order size
            side: 'buy' or 'sell'
            
        Returns:
            Estimated impact in basis points
        """
        if not orders:
            return 100.0  # Default high impact if no orders
            
        remaining_size = size
        weighted_avg_price = 0.0
        total_cost = 0.0
        
        # For selling, use the bids (highest first)
        # For buying, use the asks (lowest first)
        # orders should already be properly sorted
        
        for order in orders:
            price = order[0]
            quantity = order[1]
            
            # If this level can fill the remaining size
            if quantity >= remaining_size:
                total_cost += remaining_size * price
                weighted_avg_price = total_cost / size
                remaining_size = 0
                break
            
            # Otherwise, take the entire level and continue
            total_cost += quantity * price
            remaining_size -= quantity
        
        # If we still have remaining size, use the last price (with a penalty)
        if remaining_size > 0:
            last_price = orders[-1][0]
            
            # Apply a penalty based on remaining size (10% additional impact per unfilled size)
            penalty_factor = 1.0 + 0.1 * (remaining_size / size)
            total_cost += remaining_size * (last_price * penalty_factor if side == 'buy' else last_price / penalty_factor)
            
            weighted_avg_price = total_cost / size
        
        # Calculate the impact relative to the best available price
        best_price = orders[0][0]
        
        # Impact is different for buy vs sell
        if side == 'buy':
            impact_pct = (weighted_avg_price - best_price) / best_price
        else:
            impact_pct = (best_price - weighted_avg_price) / best_price
        
        # Convert to basis points
        impact_bps = impact_pct * 10000
        
        return impact_bps
    
    def _update_daily_stats(self, symbol: str, profile: Dict[str, Any]) -> None:
        """Update daily statistics with new profile data."""
        stats = self.daily_stats[symbol]
        current_time = profile['timestamp']
        
        # Initialize day boundaries if needed
        if stats['open_time'] == 0:
            # Set to start of day
            dt = datetime.fromtimestamp(current_time / 1000)
            day_start = datetime(dt.year, dt.month, dt.day, 0, 0, 0).timestamp() * 1000
            
            stats['open_time'] = day_start
            stats['close_time'] = day_start + 24 * 60 * 60 * 1000  # 24 hours later
        
        # Check if we need to reset for a new day
        if current_time > stats['close_time']:
            # Reset stats for new day
            old_volume = stats['total_volume']  # Keep for reference
            
            stats['open_time'] = stats['close_time']
            stats['close_time'] = stats['open_time'] + 24 * 60 * 60 * 1000
            stats['total_volume'] = 0.0
            stats['trade_count'] = 0
            stats['avg_trade_size'] = 0.0
            stats['avg_spread'] = 0.0
            stats['min_spread'] = float('inf')
            stats['max_spread'] = 0.0
            stats['avg_depth'] = 0.0
            stats['min_depth'] = float('inf')
            stats['max_depth'] = 0.0
            stats['spread_series'] = []
            stats['depth_series'] = []
            stats['volume_by_hour'] = {}
            
            logger.info(f"Reset daily stats for {symbol}. Previous day volume: {old_volume}")
        
        # Update running stats
        spread = profile['bid_ask_spread']
        depth = profile['total_depth']['total']
        
        # Update spreads
        stats['min_spread'] = min(stats['min_spread'], spread)
        stats['max_spread'] = max(stats['max_spread'], spread)
        stats['spread_series'].append(spread)
        
        # Limit series length
        if len(stats['spread_series']) > 1000:
            stats['spread_series'] = stats['spread_series'][-1000:]
        
        # Update depths
        stats['min_depth'] = min(stats['min_depth'], depth)
        stats['max_depth'] = max(stats['max_depth'], depth)
        stats['depth_series'].append(depth)
        
        # Limit series length
        if len(stats['depth_series']) > 1000:
            stats['depth_series'] = stats['depth_series'][-1000:]
        
        # Calculate averages
        if stats['spread_series']:
            stats['avg_spread'] = sum(stats['spread_series']) / len(stats['spread_series'])
        
        if stats['depth_series']:
            stats['avg_depth'] = sum(stats['depth_series']) / len(stats['depth_series'])
    
    def _detect_liquidity_shocks(self, symbol: str) -> None:
        """Detect and record significant liquidity shocks."""
        recent_snapshots = list(self.snapshots[symbol])
        if len(recent_snapshots) < 10:
            return
        
        # We'll define a shock as a sudden drop in liquidity (depth) or spike in spread
        metrics = self.resilience_metrics[symbol]
        
        # Get recent profiles
        recent_profiles = [s['profile'] for s in recent_snapshots[-10:]]
        
        # Calculate baseline and current values
        baseline_depths = [p['total_depth']['total'] for p in recent_profiles[:-1]]
        baseline_spreads = [p['bid_ask_spread'] for p in recent_profiles[:-1]]
        
        if not baseline_depths or not baseline_spreads:
            return
            
        baseline_depth = np.mean(baseline_depths)
        baseline_spread = np.mean(baseline_spreads)
        
        current_depth = recent_profiles[-1]['total_depth']['total']
        current_spread = recent_profiles[-1]['bid_ask_spread']
        
        # Calculate standard deviations
        depth_std = np.std(baseline_depths) if len(baseline_depths) > 1 else baseline_depth * 0.1
        spread_std = np.std(baseline_spreads) if len(baseline_spreads) > 1 else baseline_spread * 0.1
        
        # Detect shocks
        depth_shock = False
        spread_shock = False
        
        # Depth drop of more than 3 standard deviations
        if depth_std > 0 and baseline_depth > 0:
            depth_z_score = (baseline_depth - current_depth) / depth_std
            if depth_z_score > 3 and (baseline_depth - current_depth) / baseline_depth > 0.3:
                depth_shock = True
        
        # Spread spike of more than 3 standard deviations
        if spread_std > 0 and baseline_spread > 0:
            spread_z_score = (current_spread - baseline_spread) / spread_std
            if spread_z_score > 3 and (current_spread - baseline_spread) / baseline_spread > 0.5:
                spread_shock = True
        
        # Record shock if detected
        if depth_shock or spread_shock:
            shock_event = {
                'timestamp': recent_profiles[-1]['timestamp'],
                'type': 'depth_shock' if depth_shock else 'spread_shock',
                'magnitude_depth': (baseline_depth - current_depth) / baseline_depth if depth_shock else 0,
                'magnitude_spread': (current_spread - baseline_spread) / baseline_spread if spread_shock else 0,
                'baseline_depth': baseline_depth,
                'current_depth': current_depth,
                'baseline_spread': baseline_spread,
                'current_spread': current_spread,
                'recovery_time': None  # Will be filled when/if recovery happens
            }
            
            metrics['shock_events'].append(shock_event)
            
            # Limit number of tracked shock events
            if len(metrics['shock_events']) > 100:
                metrics['shock_events'] = metrics['shock_events'][-100:]
            
            logger.info(f"Liquidity shock detected for {symbol}: "
                       f"{'Depth drop' if depth_shock else 'Spread spike'} "
                       f"at {datetime.fromtimestamp(shock_event['timestamp']/1000)}")
        
        # Check for recovery from previous shocks
        self._check_shock_recovery(symbol)
    
    def _check_shock_recovery(self, symbol: str) -> None:
        """Check if liquidity has recovered from previous shocks."""
        metrics = self.resilience_metrics[symbol]
        
        # Get unresolved shock events
        unresolved_shocks = [e for e in metrics['shock_events'] if e['recovery_time'] is None]
        
        if not unresolved_shocks:
            return
            
        # Get current profile
        current_profile = self.current_profiles[symbol]
        
        # Check each unresolved shock
        for shock in unresolved_shocks:
            recovery = False
            
            if shock['type'] == 'depth_shock':
                # Recovery if depth returns to at least 90% of baseline
                if current_profile['total_depth']['total'] >= 0.9 * shock['baseline_depth']:
                    recovery = True
            else:  # spread_shock
                # Recovery if spread returns to within 110% of baseline
                if current_profile['bid_ask_spread'] <= 1.1 * shock['baseline_spread']:
                    recovery = True
            
            if recovery:
                # Calculate recovery time
                recovery_time_ms = current_profile['timestamp'] - shock['timestamp']
                shock['recovery_time'] = recovery_time_ms
                
                logger.info(f"Liquidity recovery for {symbol} after "
                           f"{recovery_time_ms/1000:.1f} seconds")
        
        # Update aggregate metrics
        resolved_shocks = [e for e in metrics['shock_events'] if e['recovery_time'] is not None]
        
        if resolved_shocks:
            # Average recovery time
            metrics['avg_recovery_time'] = np.mean([e['recovery_time'] for e in resolved_shocks])
            
            # Average shock magnitude
            depth_shocks = [e for e in resolved_shocks if e['type'] == 'depth_shock']
            spread_shocks = [e for e in resolved_shocks if e['type'] == 'spread_shock']
            
            if depth_shocks:
                depth_magnitudes = [e['magnitude_depth'] for e in depth_shocks]
                metrics['avg_depth_shock_magnitude'] = np.mean(depth_magnitudes)
            
            if spread_shocks:
                spread_magnitudes = [e['magnitude_spread'] for e in spread_shocks]
                metrics['avg_spread_shock_magnitude'] = np.mean(spread_magnitudes)
            
            # Overall average magnitude
            all_magnitudes = ([e['magnitude_depth'] for e in depth_shocks] +
                             [e['magnitude_spread'] for e in spread_shocks])
            if all_magnitudes:
                metrics['avg_shock_magnitude'] = np.mean(all_magnitudes)
            
            # Shock frequency (shocks per day)
            earliest_shock = min(e['timestamp'] for e in metrics['shock_events'])
            latest_shock = max(e['timestamp'] for e in metrics['shock_events'])
            
            time_span_days = (latest_shock - earliest_shock) / (24 * 60 * 60 * 1000)
            
            if time_span_days > 0:
                metrics['shock_frequency'] = len(metrics['shock_events']) / time_span_days
    
    def get_current_profile(self, symbol: str) -> Dict[str, Any]:
        """Get the current liquidity profile for a symbol."""
        if symbol not in self.current_profiles:
            return None
        
        return self.current_profiles[symbol]
    
    def get_historical_spreads(self, symbol: str, lookback_count: int = 100) -> List[float]:
        """Get historical bid-ask spreads."""
        if symbol not in self.snapshots:
            return []
        
        snapshots = list(self.snapshots[symbol])[-min(lookback_count, len(self.snapshots[symbol])):]
        return [s['profile']['bid_ask_spread'] for s in snapshots]
    
    def get_historical_depths(self, symbol: str, lookback_count: int = 100) -> List[float]:
        """Get historical total depth values."""
        if symbol not in self.snapshots:
            return []
        
        snapshots = list(self.snapshots[symbol])[-min(lookback_count, len(self.snapshots[symbol])):]
        return [s['profile']['total_depth']['total'] for s in snapshots]
    
    def get_daily_stats(self, symbol: str) -> Dict[str, Any]:
        """Get daily liquidity statistics for a symbol."""
        if symbol not in self.daily_stats:
            return None
        
        return self.daily_stats[symbol]
    
    def get_resilience_metrics(self, symbol: str) -> Dict[str, Any]:
        """Get liquidity resilience metrics for a symbol."""
        if symbol not in self.resilience_metrics:
            return None
        
        return self.resilience_metrics[symbol]
    
    def get_liquidity_score_components(self, symbol: str) -> Dict[str, Any]:
        """Get detailed breakdown of liquidity score components."""
        if symbol not in self.current_profiles:
            return None
        
        profile = self.current_profiles[symbol]
        
        # Calculate components that make up the liquidity score
        # See _calculate_liquidity_metrics for the original calculation
        
        # Normalize spread (lower is better)
        norm_spread = min(1.0, profile['relative_spread'] * 100)  # Cap at 1% = 100 bps
        spread_score = max(0, 10 - norm_spread * 10)
        
        # Normalize depth (higher is better)
        avg_trade_size = 1.0
        if symbol in self.daily_stats and self.daily_stats[symbol]['avg_trade_size'] > 0:
            avg_trade_size = self.daily_stats[symbol]['avg_trade_size']
        
        depth = profile['total_depth']['total']
        depth_ratio = min(100, depth / avg_trade_size)  # Cap at 100x avg trade size
        depth_score = min(10, depth_ratio / 10)
        
        # Impact score (lower impact is better)
        impact_score = 0.0
        impact_estimates = profile.get('impact_estimates', {})
        
        if impact_estimates:
            # Use middle tier impact (e.g., 1% of daily volume)
            middle_tier = self.impact_size_tiers[len(self.impact_size_tiers) // 2]
            avg_impact = impact_estimates[str(middle_tier)]['avg_impact_bps']
            impact_score = max(0, 10 - avg_impact / 10)  # 100 bps impact = 0 score
        
        # Combine components with weights
        components = {
            'spread_score': {
                'value': spread_score,
                'weight': 0.4,
                'description': 'Based on relative spread of {:.0f} bps'.format(norm_spread * 100)
            },
            'depth_score': {
                'value': depth_score,
                'weight': 0.3,
                'description': 'Based on total depth of {:.1f}x avg trade size'.format(depth_ratio)
            },
            'impact_score': {
                'value': impact_score,
                'weight': 0.3,
                'description': 'Based on estimated impact of {:.1f} bps for medium orders'.format(
                    avg_impact if 'avg_impact' in locals() else 0
                )
            },
            'total_score': {
                'value': profile['liquidity_score'],
                'description': 'Overall liquidity score (0-10 scale)'
            }
        }
        
        return components
    
    def to_dataframe(self, symbol: str) -> pd.DataFrame:
        """
        Convert liquidity history to a pandas DataFrame.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            DataFrame with liquidity metrics
        """
        if symbol not in self.snapshots:
            return pd.DataFrame()
        
        # Extract data from snapshots
        snapshots = list(self.snapshots[symbol])
        data = []
        
        for snapshot in snapshots:
            profile = snapshot['profile']
            row = {
                'timestamp': profile['timestamp'],
                'datetime': datetime.fromtimestamp(profile['timestamp'] / 1000),
                'mid_price': profile['mid_price'],
                'bid_ask_spread': profile['bid_ask_spread'],
                'relative_spread': profile['relative_spread'],
                'total_depth': profile['total_depth']['total'],
                'depth_imbalance': profile['total_depth']['imbalance'],
                'liquidity_score': profile['liquidity_score']
            }
            data.append(row)
        
        return pd.DataFrame(data) 