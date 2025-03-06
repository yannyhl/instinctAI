"""
Exchange Profiler Module

This module provides capability to profile and track exchange behavior, 
performance metrics, and reliability. It monitors and analyzes exchange
performance in real-time to optimize execution decisions.
"""

import time
import numpy as np
from typing import Dict, Any, List, Optional, Set, Tuple, Union, Callable
from datetime import datetime, timedelta
from collections import deque, defaultdict
import threading
import pandas as pd

from advanced_trading.core.observability import get_logger
from .exchange_capability_registry import get_exchange_registry, ExchangePerformance

# Initialize logger
logger = get_logger(__name__)

# Default values for metrics windows
DEFAULT_LATENCY_WINDOW = 100  # Number of API calls to track for latency
DEFAULT_SUCCESS_WINDOW = 200  # Number of API calls to track for success rates
DEFAULT_SLIPPAGE_WINDOW = 50  # Number of orders to track for slippage
DEFAULT_FILL_RATE_WINDOW = 50  # Number of limit orders to track for fill rates
DEFAULT_REFRESH_SECONDS = 300  # Seconds between profiler refreshes


class ExchangeProfiler:
    """
    Profiles and tracks exchange behavior, performance metrics, and reliability
    to optimize execution decisions.
    
    This class continuously monitors exchange performance and updates the 
    exchange registry with current metrics.
    """
    
    def __init__(self, 
                refresh_interval_seconds: int = DEFAULT_REFRESH_SECONDS,
                latency_window: int = DEFAULT_LATENCY_WINDOW,
                success_window: int = DEFAULT_SUCCESS_WINDOW,
                slippage_window: int = DEFAULT_SLIPPAGE_WINDOW,
                fill_rate_window: int = DEFAULT_FILL_RATE_WINDOW,
                auto_optimize: bool = True):
        """
        Initialize the exchange profiler.
        
        Args:
            refresh_interval_seconds: Seconds between registry updates
            latency_window: Number of API calls to track for latency
            success_window: Number of API calls to track for success rates
            slippage_window: Number of orders to track for slippage
            fill_rate_window: Number of limit orders to track for fill rates
            auto_optimize: Whether to automatically optimize parameters
        """
        self.refresh_interval = refresh_interval_seconds
        self.latency_window = latency_window
        self.success_window = success_window
        self.slippage_window = slippage_window
        self.fill_rate_window = fill_rate_window
        self.auto_optimize = auto_optimize
        
        # Get exchange registry
        self.registry = get_exchange_registry()
        
        # Tracking metrics
        self._api_latencies = defaultdict(lambda: deque(maxlen=latency_window))
        self._api_successes = defaultdict(lambda: deque(maxlen=success_window))
        self._api_errors = defaultdict(lambda: deque(maxlen=success_window))
        self._market_order_slippages = defaultdict(lambda: deque(maxlen=slippage_window))
        self._limit_order_fills = defaultdict(lambda: deque(maxlen=fill_rate_window))
        self._order_cancellations = defaultdict(lambda: deque(maxlen=success_window))
        
        # Additional per-symbol metrics
        self._symbol_metrics = defaultdict(lambda: defaultdict(dict))
        
        # Background thread for periodic updates
        self._stop_event = threading.Event()
        self._update_thread = None
        
        # Status
        self._is_running = False
        self._last_update_time = 0
        
        logger.info("Exchange profiler initialized")
    
    def start(self):
        """Start the background profiler thread."""
        if self._is_running:
            logger.warning("Exchange profiler is already running")
            return
        
        self._stop_event.clear()
        self._update_thread = threading.Thread(
            target=self._update_loop,
            name="ExchangeProfilerThread",
            daemon=True
        )
        self._update_thread.start()
        self._is_running = True
        
        logger.info("Exchange profiler started")
    
    def stop(self):
        """Stop the background profiler thread."""
        if not self._is_running:
            logger.warning("Exchange profiler is not running")
            return
        
        self._stop_event.set()
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=2.0)
        
        self._is_running = False
        logger.info("Exchange profiler stopped")
    
    def _update_loop(self):
        """Background thread that periodically updates the registry."""
        try:
            while not self._stop_event.is_set():
                try:
                    # Check if it's time for an update
                    current_time = time.time()
                    if current_time - self._last_update_time >= self.refresh_interval:
                        self._update_registry()
                        self._last_update_time = current_time
                except Exception as e:
                    logger.error(f"Error in exchange profiler update loop: {e}")
                
                # Sleep for a short time before checking again
                self._stop_event.wait(10)  # Check every 10 seconds
        except Exception as e:
            logger.error(f"Exchange profiler thread error: {e}")
    
    def _update_registry(self):
        """Update the exchange registry with current metrics."""
        # Get all exchanges with metrics
        exchanges = set()
        for collection in [
            self._api_latencies, self._api_successes, self._market_order_slippages,
            self._limit_order_fills, self._order_cancellations
        ]:
            exchanges.update(collection.keys())
        
        # Update metrics for each exchange
        update_count = 0
        for exchange_id in exchanges:
            # Skip if no data for this exchange
            if not self._has_metrics_for_exchange(exchange_id):
                continue
            
            # Calculate current metrics
            metrics = self._calculate_metrics_for_exchange(exchange_id)
            
            # Update registry
            if metrics and self.registry.update_exchange_metrics(exchange_id, metrics):
                update_count += 1
                
                # Optimize parameters if enabled
                if self.auto_optimize:
                    self._optimize_parameters(exchange_id, metrics)
        
        logger.info(f"Updated metrics for {update_count} exchanges")
    
    def _has_metrics_for_exchange(self, exchange_id: str) -> bool:
        """Check if we have any metrics for an exchange."""
        # Check if we have any metrics for this exchange
        has_api_metrics = (exchange_id in self._api_latencies and len(self._api_latencies[exchange_id]) > 0) or \
                         (exchange_id in self._api_successes and len(self._api_successes[exchange_id]) > 0)
        
        has_order_metrics = (exchange_id in self._market_order_slippages and len(self._market_order_slippages[exchange_id]) > 0) or \
                           (exchange_id in self._limit_order_fills and len(self._limit_order_fills[exchange_id]) > 0)
        
        return has_api_metrics or has_order_metrics
    
    def _calculate_metrics_for_exchange(self, exchange_id: str) -> Dict[str, Any]:
        """Calculate current metrics for an exchange."""
        metrics = {}
        
        # API latency
        if exchange_id in self._api_latencies and self._api_latencies[exchange_id]:
            metrics['avg_api_latency_ms'] = np.mean(self._api_latencies[exchange_id])
        
        # API error rate
        if exchange_id in self._api_successes and self._api_successes[exchange_id]:
            success_count = sum(1 for success in self._api_successes[exchange_id] if success)
            total_count = len(self._api_successes[exchange_id])
            
            if total_count > 0:
                success_rate = success_count / total_count
                metrics['api_error_rate'] = 1.0 - success_rate
                metrics['api_reliability_pct'] = success_rate * 100
        
        # API timeout rate
        if exchange_id in self._api_errors and self._api_errors[exchange_id]:
            timeout_count = sum(1 for err in self._api_errors[exchange_id] if err == 'timeout')
            total_count = len(self._api_errors[exchange_id])
            
            if total_count > 0:
                metrics['api_timeout_rate'] = timeout_count / total_count
        
        # Market order slippage
        if exchange_id in self._market_order_slippages and self._market_order_slippages[exchange_id]:
            metrics['market_order_slippage_bps'] = np.mean(self._market_order_slippages[exchange_id])
        
        # Limit order fill rate
        if exchange_id in self._limit_order_fills and self._limit_order_fills[exchange_id]:
            fill_count = sum(1 for fill in self._limit_order_fills[exchange_id] if fill)
            total_count = len(self._limit_order_fills[exchange_id])
            
            if total_count > 0:
                metrics['limit_order_fill_rate'] = fill_count / total_count
        
        # Order cancellation success rate
        if exchange_id in self._order_cancellations and self._order_cancellations[exchange_id]:
            success_count = sum(1 for success in self._order_cancellations[exchange_id] if success)
            total_count = len(self._order_cancellations[exchange_id])
            
            if total_count > 0:
                metrics['cancellation_success_rate'] = success_count / total_count
        
        # Calculate exchange reliability score (1-10 scale)
        if 'api_reliability_pct' in metrics and 'limit_order_fill_rate' in metrics:
            # 70% API reliability, 30% order execution reliability
            api_score = min(10.0, metrics['api_reliability_pct'] / 10.0)
            execution_score = min(10.0, metrics['limit_order_fill_rate'] * 10.0)
            
            reliability_score = (api_score * 0.7) + (execution_score * 0.3)
            metrics['exchange_reliability_score'] = reliability_score
        
        return metrics
    
    def _optimize_parameters(self, exchange_id: str, metrics: Dict[str, Any]) -> None:
        """Optimize execution parameters based on metrics."""
        # Get current optimization parameters
        params = self.registry.get_optimization_params(exchange_id)
        if not params:
            logger.warning(f"No optimization parameters found for {exchange_id}")
            return
        
        # Create updated parameters (registry handles the actual update)
        update = {}
        
        # Adjust slippage tolerance based on observed slippage
        if 'market_order_slippage_bps' in metrics:
            slippage = metrics['market_order_slippage_bps']
            update['max_slippage_tolerance_bps'] = max(5.0, slippage * 1.5)
        
        # Adjust limit order parameters based on fill rates
        if 'limit_order_fill_rate' in metrics:
            fill_rate = metrics['limit_order_fill_rate']
            
            # Low fill rates require more aggressive limit prices
            if fill_rate < 0.7:
                update['default_limit_order_distance_bps'] = max(0.5, params.default_limit_order_distance_bps * 0.8)
                update['use_market_threshold_urgency'] = 0.7  # Lower threshold for using market orders
            # High fill rates allow more passive limit prices
            elif fill_rate > 0.9:
                update['default_limit_order_distance_bps'] = min(3.0, params.default_limit_order_distance_bps * 1.2)
                update['use_market_threshold_urgency'] = 0.85  # Higher threshold for using market orders
        
        # Update
        if update:
            update['auto_optimized'] = True
            update['last_optimized'] = time.time()
            self.registry.update_exchange_metrics(exchange_id, update)
    
    def record_api_call(self, 
                       exchange_id: str, 
                       latency_ms: float, 
                       success: bool, 
                       error_type: Optional[str] = None) -> None:
        """
        Record metrics for an API call.
        
        Args:
            exchange_id: Exchange identifier
            latency_ms: API call latency in milliseconds
            success: Whether the call was successful
            error_type: Type of error if the call failed
        """
        # Record latency if call was successful
        if success:
            self._api_latencies[exchange_id].append(latency_ms)
        
        # Record success/failure
        self._api_successes[exchange_id].append(success)
        
        # Record error type if provided
        if error_type:
            self._api_errors[exchange_id].append(error_type)
    
    def record_market_order(self, 
                          exchange_id: str, 
                          symbol: str, 
                          expected_price: float, 
                          executed_price: float, 
                          side: str) -> None:
        """
        Record metrics for a market order execution.
        
        Args:
            exchange_id: Exchange identifier
            symbol: Trading symbol
            expected_price: Expected execution price
            executed_price: Actual execution price
            side: 'buy' or 'sell'
        """
        # Calculate slippage in basis points
        if expected_price <= 0:
            logger.warning(f"Invalid expected price: {expected_price}")
            return
        
        # Slippage direction depends on side
        if side.lower() == 'buy':
            # For buys, executed > expected is bad (positive slippage)
            price_diff = executed_price - expected_price
        else:
            # For sells, executed < expected is bad (positive slippage)
            price_diff = expected_price - executed_price
        
        # Convert to basis points
        slippage_bps = (price_diff / expected_price) * 10000
        
        # Record slippage
        self._market_order_slippages[exchange_id].append(slippage_bps)
        
        # Also record per-symbol metrics
        if symbol not in self._symbol_metrics[exchange_id]:
            self._symbol_metrics[exchange_id][symbol] = {
                'market_slippage': deque(maxlen=self.slippage_window)
            }
        
        self._symbol_metrics[exchange_id][symbol]['market_slippage'].append(slippage_bps)
        
        # Update real-time metrics in registry
        if symbol and self._symbol_metrics[exchange_id][symbol]['market_slippage']:
            avg_slippage = np.mean(self._symbol_metrics[exchange_id][symbol]['market_slippage'])
            self.registry.update_realtime_metric(
                exchange_id=exchange_id,
                metric_type='price_impact',
                symbol=symbol,
                value=avg_slippage
            )
    
    def record_limit_order(self, 
                         exchange_id: str, 
                         symbol: str, 
                         filled: bool, 
                         time_to_fill_ms: Optional[float] = None) -> None:
        """
        Record metrics for a limit order.
        
        Args:
            exchange_id: Exchange identifier
            symbol: Trading symbol
            filled: Whether the order was filled
            time_to_fill_ms: Time to fill in milliseconds (if filled)
        """
        # Record fill status
        self._limit_order_fills[exchange_id].append(filled)
        
        # Also record per-symbol metrics
        if symbol not in self._symbol_metrics[exchange_id]:
            self._symbol_metrics[exchange_id][symbol] = {
                'limit_fills': deque(maxlen=self.fill_rate_window),
                'fill_times': deque(maxlen=self.fill_rate_window),
            }
        
        self._symbol_metrics[exchange_id][symbol]['limit_fills'].append(filled)
        
        # Record fill time if provided
        if filled and time_to_fill_ms is not None:
            # Record in exchange metrics
            if 'avg_fill_time_ms' not in self._symbol_metrics[exchange_id][symbol]:
                self._symbol_metrics[exchange_id][symbol]['fill_times'] = deque(maxlen=self.fill_rate_window)
            
            self._symbol_metrics[exchange_id][symbol]['fill_times'].append(time_to_fill_ms)
        
        # Update real-time metrics in registry
        if symbol and self._symbol_metrics[exchange_id][symbol]['limit_fills']:
            fill_count = sum(1 for fill in self._symbol_metrics[exchange_id][symbol]['limit_fills'] if fill)
            total_count = len(self._symbol_metrics[exchange_id][symbol]['limit_fills'])
            
            if total_count > 0:
                fill_rate = fill_count / total_count
                self.registry.update_realtime_metric(
                    exchange_id=exchange_id,
                    metric_type='order_fill_rates',
                    symbol=symbol,
                    value=fill_rate
                )
    
    def record_order_cancellation(self, 
                                exchange_id: str, 
                                success: bool) -> None:
        """
        Record metrics for an order cancellation.
        
        Args:
            exchange_id: Exchange identifier
            success: Whether the cancellation was successful
        """
        self._order_cancellations[exchange_id].append(success)
    
    def get_exchange_metrics(self, exchange_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current metrics for an exchange.
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            Dict of metrics or None if no metrics are available
        """
        if not self._has_metrics_for_exchange(exchange_id):
            return None
        
        return self._calculate_metrics_for_exchange(exchange_id)
    
    def get_symbol_metrics(self, 
                         exchange_id: str, 
                         symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current metrics for a symbol on an exchange.
        
        Args:
            exchange_id: Exchange identifier
            symbol: Trading symbol
            
        Returns:
            Dict of metrics or None if no metrics are available
        """
        if (exchange_id not in self._symbol_metrics or
            symbol not in self._symbol_metrics[exchange_id]):
            return None
        
        metrics = {}
        symbol_data = self._symbol_metrics[exchange_id][symbol]
        
        # Market order slippage
        if 'market_slippage' in symbol_data and symbol_data['market_slippage']:
            metrics['market_slippage_bps'] = np.mean(symbol_data['market_slippage'])
        
        # Limit order fill rate
        if 'limit_fills' in symbol_data and symbol_data['limit_fills']:
            fill_count = sum(1 for fill in symbol_data['limit_fills'] if fill)
            total_count = len(symbol_data['limit_fills'])
            
            if total_count > 0:
                metrics['limit_fill_rate'] = fill_count / total_count
        
        # Fill time
        if 'fill_times' in symbol_data and symbol_data['fill_times']:
            metrics['avg_fill_time_ms'] = np.mean(symbol_data['fill_times'])
        
        return metrics
    
    def record_spread_data(self, 
                         exchange_id: str, 
                         symbol: str, 
                         spread_bps: float, 
                         liquidity_depth_usd: float) -> None:
        """
        Record spread and liquidity data for a symbol.
        
        Args:
            exchange_id: Exchange identifier
            symbol: Trading symbol
            spread_bps: Bid-ask spread in basis points
            liquidity_depth_usd: Liquidity depth in USD
        """
        # Initialize symbol metrics if needed
        if symbol not in self._symbol_metrics[exchange_id]:
            self._symbol_metrics[exchange_id][symbol] = {}
        
        # Initialize spread and depth tracking if needed
        if 'spreads' not in self._symbol_metrics[exchange_id][symbol]:
            self._symbol_metrics[exchange_id][symbol]['spreads'] = deque(maxlen=100)
        
        if 'depths' not in self._symbol_metrics[exchange_id][symbol]:
            self._symbol_metrics[exchange_id][symbol]['depths'] = deque(maxlen=100)
        
        # Record data
        self._symbol_metrics[exchange_id][symbol]['spreads'].append(spread_bps)
        self._symbol_metrics[exchange_id][symbol]['depths'].append(liquidity_depth_usd)
        
        # Calculate averages for the exchange
        all_spreads = []
        all_depths = []
        
        for sym, data in self._symbol_metrics[exchange_id].items():
            if 'spreads' in data and data['spreads']:
                all_spreads.extend(data['spreads'])
            
            if 'depths' in data and data['depths']:
                all_depths.extend(data['depths'])
        
        # Update exchange metrics
        update = {}
        
        if all_spreads:
            update['avg_spread_bps'] = np.mean(all_spreads)
        
        if all_depths:
            update['avg_liquidity_depth_usd'] = np.mean(all_depths)
        
        if update:
            self.registry.update_exchange_metrics(exchange_id, update)
    
    def to_dataframe(self, exchange_id: Optional[str] = None) -> pd.DataFrame:
        """
        Convert exchange metrics to a pandas DataFrame.
        
        Args:
            exchange_id: Optional exchange to filter by
            
        Returns:
            DataFrame with exchange metrics
        """
        # Get all exchanges
        exchanges = set()
        if exchange_id:
            exchanges.add(exchange_id)
        else:
            for collection in [
                self._api_latencies, self._api_successes, self._market_order_slippages,
                self._limit_order_fills, self._order_cancellations
            ]:
                exchanges.update(collection.keys())
        
        # Build dataframe
        rows = []
        for ex_id in exchanges:
            # Skip if no data
            if not self._has_metrics_for_exchange(ex_id):
                continue
            
            # Get metrics
            metrics = self._calculate_metrics_for_exchange(ex_id)
            if not metrics:
                continue
            
            # Add exchange ID
            metrics['exchange_id'] = ex_id
            rows.append(metrics)
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows)


# Singleton instance
_profiler_instance = None

def get_exchange_profiler() -> ExchangeProfiler:
    """
    Get the global exchange profiler instance.
    
    Returns:
        ExchangeProfiler instance
    """
    global _profiler_instance
    if _profiler_instance is None:
        _profiler_instance = ExchangeProfiler()
        _profiler_instance.start()
    return _profiler_instance 