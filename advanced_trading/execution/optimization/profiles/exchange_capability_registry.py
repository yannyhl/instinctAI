"""
Exchange Capability Registry Module

This module provides a centralized registry for exchange capabilities, performance
metrics, and optimization parameters. It's used to make intelligent decisions
about order routing, parameter selection, and execution strategies.
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field, asdict
from threading import RLock

from advanced_trading.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)

@dataclass
class ExchangeCapabilities:
    """Data class for exchange capabilities."""
    # Fee structure
    maker_fee: float = 0.001
    taker_fee: float = 0.002
    fee_tier_volume: Dict[str, float] = field(default_factory=dict)
    tiered_fees: bool = False
    
    # Order size limits
    min_order_size: float = 0.001
    max_order_size: Optional[float] = None
    size_increment: Optional[float] = None
    
    # Price precision
    price_precision: int = 8
    price_increment: Optional[float] = None
    quantity_precision: int = 8
    
    # Supported order types
    supports_market_orders: bool = True
    supports_limit_orders: bool = True
    supports_stop_orders: bool = False
    supports_stop_limit_orders: bool = False
    supports_trailing_stop: bool = False
    supports_post_only: bool = False
    supports_fill_or_kill: bool = False
    supports_immediate_or_cancel: bool = False
    supports_reduce_only: bool = False
    supports_good_till_date: bool = False
    supports_iceberg: bool = False
    
    # Leverage features
    supports_margin: bool = False
    supports_futures: bool = False
    max_leverage: float = 1.0
    
    # API rate limits
    base_api_limit: int = 60  # requests per minute
    weight_system: bool = False
    enhanced_rate_limit: bool = False
    
    # Other features
    native_websocket: bool = True
    supports_batch_orders: bool = False
    has_testnet: bool = False
    requires_api_key: bool = True
    

@dataclass
class ExchangePerformance:
    """Data class for exchange performance metrics."""
    # API performance
    avg_api_latency_ms: float = 100.0
    api_error_rate: float = 0.01
    api_timeout_rate: float = 0.005
    
    # Order execution performance
    avg_fill_time_ms: float = 500.0
    market_order_slippage_bps: float = 5.0
    limit_order_fill_rate: float = 0.9
    cancellation_success_rate: float = 0.99
    
    # Market quality
    avg_spread_bps: float = 10.0
    avg_liquidity_depth_usd: float = 1000000.0
    price_volatility: float = 0.02
    
    # Reliability
    uptime_pct: float = 99.9
    api_reliability_pct: float = 99.8
    exchange_reliability_score: float = 9.5  # 1-10 scale
    
    # Last updated
    last_updated: float = field(default_factory=time.time)


@dataclass
class ExchangeOptimizationParams:
    """Data class for exchange-specific optimization parameters."""
    # Order placement
    price_improvement_threshold_bps: float = 0.5
    max_slippage_tolerance_bps: float = 10.0
    optimal_order_refresh_ms: float = 5000.0
    
    # Order type selection thresholds
    use_market_threshold_urgency: float = 0.8
    use_post_only_threshold_urgency: float = 0.3
    
    # Execution parameters
    default_market_order_urgency: float = 0.7
    default_limit_order_distance_bps: float = 0.5
    
    # Retry parameters
    max_retry_attempts: int = 3
    retry_delay_ms: float = 1000.0
    
    # Parallel orders
    max_parallel_orders: int = 5
    max_in_flight_orders: int = 10
    
    # Optimization status
    auto_optimized: bool = False
    optimization_version: int = 1
    last_optimized: float = field(default_factory=time.time)


class ExchangeCapabilityRegistry:
    """
    Centralized registry of exchange capabilities, performance metrics, and optimization parameters.
    Used to make intelligent decisions about order routing and execution style.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the exchange capability registry.
        
        Args:
            config_path: Path to configuration file (if None, use defaults)
        """
        self._lock = RLock()
        
        # Core data structures
        self.exchanges: Dict[str, ExchangeCapabilities] = {}
        self.performance_metrics: Dict[str, ExchangePerformance] = {}
        self.optimization_params: Dict[str, ExchangeOptimizationParams] = {}
        
        # Symbol availability
        self.symbols_by_exchange: Dict[str, Set[str]] = {}
        self.exchanges_by_symbol: Dict[str, Set[str]] = {}
        
        # Real-time metrics
        self.realtime_metrics: Dict[str, Dict[str, Dict[str, float]]] = {
            'order_fill_rates': {},
            'execution_latency': {},
            'api_errors': {},
            'price_impact': {}
        }
        
        # Load configuration
        if config_path and os.path.exists(config_path):
            self._load_from_config(config_path)
        else:
            self._load_defaults()
        
        logger.info(f"Exchange capability registry initialized with {len(self.exchanges)} exchanges")
    
    def _load_from_config(self, config_path: str):
        """Load exchange capabilities from configuration file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Load exchanges
            for exchange_id, data in config.get('exchanges', {}).items():
                capabilities = ExchangeCapabilities(**data.get('capabilities', {}))
                self.exchanges[exchange_id] = capabilities
                
                # Load performance metrics if available
                if 'performance' in data:
                    self.performance_metrics[exchange_id] = ExchangePerformance(**data['performance'])
                
                # Load optimization parameters if available
                if 'optimization' in data:
                    self.optimization_params[exchange_id] = ExchangeOptimizationParams(**data['optimization'])
                
                # Load symbols if available
                if 'symbols' in data:
                    self.symbols_by_exchange[exchange_id] = set(data['symbols'])
                    for symbol in data['symbols']:
                        if symbol not in self.exchanges_by_symbol:
                            self.exchanges_by_symbol[symbol] = set()
                        self.exchanges_by_symbol[symbol].add(exchange_id)
            
            logger.info(f"Loaded exchange capabilities from {config_path}")
        except Exception as e:
            logger.error(f"Error loading exchange capabilities from {config_path}: {e}")
            # Fall back to defaults
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default exchange capabilities."""
        # Default exchange map with basic capabilities
        default_exchanges = {
            'exchange_a': {
                'maker_fee': 0.0010,
                'taker_fee': 0.0020,
                'min_order_size': 0.001,
                'price_precision': 5,
                'quantity_precision': 8,
                'supports_market_orders': True,
                'supports_limit_orders': True,
                'supports_stop_orders': True,
                'supports_post_only': True,
                'supports_fill_or_kill': True,
                'supports_reduce_only': True,
                'supports_iceberg': False,
                'max_leverage': 10.0,
                'base_api_limit': 300,  # requests per minute
                'weight_system': True,  # whether API has weighted rate limits
                'native_websocket': True
            },
            'exchange_b': {
                'maker_fee': 0.0004,
                'taker_fee': 0.0015,
                'min_order_size': 0.0005,
                'price_precision': 6,
                'quantity_precision': 6,
                'supports_market_orders': True,
                'supports_limit_orders': True,
                'supports_stop_orders': False,
                'supports_post_only': True,
                'supports_fill_or_kill': False,
                'supports_reduce_only': True,
                'supports_iceberg': True,
                'max_leverage': 20.0,
                'base_api_limit': 200,
                'weight_system': False,
                'native_websocket': True
            }
        }
        
        # Default performance metrics
        default_performance = {
            'exchange_a': {
                'avg_fill_time_ms': 120,
                'market_order_slippage_bps': 8.5,
                'limit_order_fill_rate': 0.92,
                'api_reliability_pct': 99.7,
                'avg_liquidity_depth_usd': 2500000
            },
            'exchange_b': {
                'avg_fill_time_ms': 85,
                'market_order_slippage_bps': 7.2,
                'limit_order_fill_rate': 0.88,
                'api_reliability_pct': 99.5,
                'avg_liquidity_depth_usd': 3200000
            }
        }
        
        # Add defaults to registry
        for exchange_id, capabilities_dict in default_exchanges.items():
            self.exchanges[exchange_id] = ExchangeCapabilities(**capabilities_dict)
            
            if exchange_id in default_performance:
                self.performance_metrics[exchange_id] = ExchangePerformance(**default_performance[exchange_id])
            else:
                self.performance_metrics[exchange_id] = ExchangePerformance()
                
            self.optimization_params[exchange_id] = ExchangeOptimizationParams()
            
            # Initialize default symbols
            self.symbols_by_exchange[exchange_id] = set(['BTC/USD', 'ETH/USD', 'BTC/USDT', 'ETH/USDT'])
            
        # Setup exchanges by symbol
        for exchange_id, symbols in self.symbols_by_exchange.items():
            for symbol in symbols:
                if symbol not in self.exchanges_by_symbol:
                    self.exchanges_by_symbol[symbol] = set()
                self.exchanges_by_symbol[symbol].add(exchange_id)
                
        logger.info("Loaded default exchange capabilities")
    
    def register_exchange(self, 
                        exchange_id: str, 
                        capabilities: Dict[str, Any], 
                        performance_data: Optional[Dict[str, Any]] = None,
                        optimization_params: Optional[Dict[str, Any]] = None,
                        symbols: Optional[List[str]] = None) -> bool:
        """
        Register a new exchange with its specific capabilities.
        
        Args:
            exchange_id: Unique identifier for the exchange
            capabilities: Dict of exchange capabilities
            performance_data: Optional performance metrics
            optimization_params: Optional optimization parameters
            symbols: List of supported symbols
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                # Register capabilities
                self.exchanges[exchange_id] = ExchangeCapabilities(**capabilities)
                
                # Register performance metrics if provided
                if performance_data:
                    self.performance_metrics[exchange_id] = ExchangePerformance(**performance_data)
                elif exchange_id not in self.performance_metrics:
                    self.performance_metrics[exchange_id] = ExchangePerformance()
                
                # Register optimization parameters if provided
                if optimization_params:
                    self.optimization_params[exchange_id] = ExchangeOptimizationParams(**optimization_params)
                elif exchange_id not in self.optimization_params:
                    self.optimization_params[exchange_id] = ExchangeOptimizationParams()
                
                # Register symbols if provided
                if symbols:
                    self.symbols_by_exchange[exchange_id] = set(symbols)
                    for symbol in symbols:
                        if symbol not in self.exchanges_by_symbol:
                            self.exchanges_by_symbol[symbol] = set()
                        self.exchanges_by_symbol[symbol].add(exchange_id)
                        
                # Initialize real-time metrics for this exchange
                for metric_type in self.realtime_metrics:
                    if exchange_id not in self.realtime_metrics[metric_type]:
                        self.realtime_metrics[metric_type][exchange_id] = {}
                
                logger.info(f"Registered exchange {exchange_id}")
                return True
            except Exception as e:
                logger.error(f"Error registering exchange {exchange_id}: {e}")
                return False
    
    def update_exchange_metrics(self, exchange_id: str, metrics_update: Dict[str, Any]) -> bool:
        """
        Update performance metrics for an exchange.
        
        Args:
            exchange_id: Exchange identifier
            metrics_update: Dict of metrics to update
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if exchange_id not in self.performance_metrics:
                self.performance_metrics[exchange_id] = ExchangePerformance()
                
            try:
                # Update existing metrics object with new values
                for key, value in metrics_update.items():
                    if hasattr(self.performance_metrics[exchange_id], key):
                        setattr(self.performance_metrics[exchange_id], key, value)
                
                # Update timestamp
                self.performance_metrics[exchange_id].last_updated = time.time()
                
                # Recalculate optimization parameters if needed
                if self.optimization_params.get(exchange_id, ExchangeOptimizationParams()).auto_optimized:
                    self._recalculate_optimization_params(exchange_id)
                
                return True
            except Exception as e:
                logger.error(f"Error updating metrics for exchange {exchange_id}: {e}")
                return False
    
    def update_realtime_metric(self, 
                             exchange_id: str, 
                             metric_type: str, 
                             symbol: str, 
                             value: float) -> bool:
        """
        Update a real-time metric for a specific exchange and symbol.
        
        Args:
            exchange_id: Exchange identifier
            metric_type: Type of metric (order_fill_rates, execution_latency, etc.)
            symbol: Trading symbol
            value: Metric value
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                if metric_type not in self.realtime_metrics:
                    logger.warning(f"Unknown metric type: {metric_type}")
                    return False
                
                if exchange_id not in self.realtime_metrics[metric_type]:
                    self.realtime_metrics[metric_type][exchange_id] = {}
                
                self.realtime_metrics[metric_type][exchange_id][symbol] = value
                return True
            except Exception as e:
                logger.error(f"Error updating real-time metric: {e}")
                return False
    
    def get_realtime_metrics(self, 
                           exchange_id: str, 
                           metric_type: str) -> Dict[str, float]:
        """
        Get real-time metrics for a specific exchange and metric type.
        
        Args:
            exchange_id: Exchange identifier
            metric_type: Type of metric
            
        Returns:
            Dict of metrics by symbol
        """
        with self._lock:
            if (metric_type not in self.realtime_metrics or
                exchange_id not in self.realtime_metrics[metric_type]):
                return {}
            
            return self.realtime_metrics[metric_type][exchange_id].copy()
    
    def get_exchange_capabilities(self, exchange_id: str) -> Optional[ExchangeCapabilities]:
        """
        Get capabilities for a specific exchange.
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            Exchange capabilities or None if not found
        """
        with self._lock:
            if exchange_id not in self.exchanges:
                return None
            
            return self.exchanges[exchange_id]
    
    def get_exchange_performance(self, exchange_id: str) -> Optional[ExchangePerformance]:
        """
        Get performance metrics for a specific exchange.
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            Exchange performance metrics or None if not found
        """
        with self._lock:
            if exchange_id not in self.performance_metrics:
                return None
            
            return self.performance_metrics[exchange_id]
    
    def get_optimization_params(self, exchange_id: str) -> Optional[ExchangeOptimizationParams]:
        """
        Get optimization parameters for a specific exchange.
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            Exchange optimization parameters or None if not found
        """
        with self._lock:
            if exchange_id not in self.optimization_params:
                return None
            
            return self.optimization_params[exchange_id]
    
    def get_exchanges_for_symbol(self, symbol: str) -> List[str]:
        """
        Get all exchanges that support a specific symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of exchange identifiers
        """
        with self._lock:
            if symbol not in self.exchanges_by_symbol:
                return []
            
            return list(self.exchanges_by_symbol[symbol])
    
    def get_symbols_for_exchange(self, exchange_id: str) -> List[str]:
        """
        Get all symbols supported by a specific exchange.
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            List of symbols
        """
        with self._lock:
            if exchange_id not in self.symbols_by_exchange:
                return []
            
            return list(self.symbols_by_exchange[exchange_id])
    
    def get_execution_parameters(self, 
                               exchange_id: str, 
                               order_type: str, 
                               symbol: str, 
                               size_usd: float) -> Dict[str, Any]:
        """
        Get optimized execution parameters for a specific exchange, order type and size.
        
        Args:
            exchange_id: Exchange identifier
            order_type: Type of order (market, limit, etc.)
            symbol: Trading symbol
            size_usd: Size of order in USD
            
        Returns:
            Dict of optimized parameters
        """
        with self._lock:
            if exchange_id not in self.exchanges:
                raise ValueError(f"Exchange {exchange_id} not registered")
                
            # Get base capability and performance data
            capabilities = self.exchanges[exchange_id]
            performance = self.performance_metrics.get(exchange_id, ExchangePerformance())
            optimization = self.optimization_params.get(exchange_id, ExchangeOptimizationParams())
            
            # Start with default parameters
            params = {
                'price_precision': capabilities.price_precision,
                'quantity_precision': capabilities.quantity_precision,
                'price_improvement_bps': optimization.price_improvement_threshold_bps,
                'slippage_tolerance_bps': optimization.max_slippage_tolerance_bps,
                'refresh_interval_ms': optimization.optimal_order_refresh_ms
            }
            
            # Adjust based on order type
            if order_type.lower() == 'market':
                # For market orders, focus on slippage control
                params['urgency'] = optimization.default_market_order_urgency
                
                # Adjust slippage tolerance based on order size and typical slippage
                size_factor = min(1.0, size_usd / 10000)  # Scale by size up to $10k
                params['slippage_tolerance_bps'] *= (1.0 + size_factor)
                
                # Add expected slippage based on historical performance
                params['expected_slippage_bps'] = performance.market_order_slippage_bps
                
            elif order_type.lower() == 'limit':
                # For limit orders, focus on fill probability
                base_limit_distance = optimization.default_limit_order_distance_bps
                
                # Adjust distance based on market volatility
                vol_factor = performance.price_volatility / 0.02  # Normalize to 2% vol
                params['limit_distance_bps'] = base_limit_distance * vol_factor
                
                # Adjust based on typical fill rates
                fill_factor = 1.0 - performance.limit_order_fill_rate  # Lower fill rate = more aggressive
                params['limit_distance_bps'] *= (1.0 - fill_factor * 0.5)
                
                # Check if exchange supports post-only
                if capabilities.supports_post_only:
                    params['post_only'] = True
            
            # Time in force parameter
            if order_type.lower() == 'limit':
                if capabilities.supports_good_till_date:
                    params['time_in_force'] = 'good_till_date'
                    params['expiry_seconds'] = 86400  # 24 hours
                else:
                    params['time_in_force'] = 'good_till_cancel'
                
                # Use fill-or-kill for small orders if supported
                if capabilities.supports_fill_or_kill and size_usd < 10000:
                    params['time_in_force'] = 'fill_or_kill'
                    
                # Use immediate-or-cancel for high urgency orders if supported
                if capabilities.supports_immediate_or_cancel and params.get('urgency', 0) > 0.7:
                    params['time_in_force'] = 'immediate_or_cancel'
            
            # Add fee information
            params['maker_fee'] = capabilities.maker_fee
            params['taker_fee'] = capabilities.taker_fee
            
            return params
    
    def rank_exchanges(self, 
                      symbol: str, 
                      criteria: Dict[str, float]) -> List[Tuple[str, float]]:
        """
        Rank exchanges based on specified criteria for a symbol.
        
        Args:
            symbol: Trading symbol
            criteria: Dict of criterion names and weights (e.g., {'latency': 0.3, 'fees': 0.4, 'reliability': 0.3})
            
        Returns:
            List of (exchange_id, score) tuples, sorted by score (higher is better)
        """
        with self._lock:
            if symbol not in self.exchanges_by_symbol:
                return []
            
            exchanges = self.exchanges_by_symbol[symbol]
            if not exchanges:
                return []
            
            # Calculate scores for each exchange
            scores = []
            for exchange_id in exchanges:
                if (exchange_id not in self.exchanges or 
                    exchange_id not in self.performance_metrics):
                    continue
                
                capabilities = self.exchanges[exchange_id]
                performance = self.performance_metrics[exchange_id]
                
                # Initialize score components
                score_components = {}
                
                # Score for latency (lower is better)
                if 'latency' in criteria:
                    latency_score = 1.0 - min(1.0, performance.avg_fill_time_ms / 500)
                    score_components['latency'] = latency_score
                
                # Score for fees (lower is better)
                if 'fees' in criteria:
                    fee_score = 1.0 - min(1.0, capabilities.taker_fee / 0.003)
                    score_components['fees'] = fee_score
                
                # Score for reliability (higher is better)
                if 'reliability' in criteria:
                    reliability_score = min(1.0, performance.api_reliability_pct / 100)
                    score_components['reliability'] = reliability_score
                
                # Score for liquidity (higher is better)
                if 'liquidity' in criteria:
                    liquidity_score = min(1.0, performance.avg_liquidity_depth_usd / 5000000)
                    score_components['liquidity'] = liquidity_score
                
                # Score for slippage (lower is better)
                if 'slippage' in criteria:
                    slippage_score = 1.0 - min(1.0, performance.market_order_slippage_bps / 20)
                    score_components['slippage'] = slippage_score
                
                # Calculate weighted score
                total_score = 0.0
                total_weight = 0.0
                
                for criterion, weight in criteria.items():
                    if criterion in score_components:
                        total_score += score_components[criterion] * weight
                        total_weight += weight
                
                if total_weight > 0:
                    final_score = total_score / total_weight
                else:
                    final_score = 0.0
                
                scores.append((exchange_id, final_score))
            
            # Sort by score (descending)
            return sorted(scores, key=lambda x: x[1], reverse=True)
    
    def save_to_config(self, config_path: str) -> bool:
        """
        Save current registry state to a configuration file.
        
        Args:
            config_path: Path to save the configuration
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                config = {'exchanges': {}}
                
                for exchange_id, capabilities in self.exchanges.items():
                    config['exchanges'][exchange_id] = {
                        'capabilities': asdict(capabilities)
                    }
                    
                    if exchange_id in self.performance_metrics:
                        config['exchanges'][exchange_id]['performance'] = asdict(self.performance_metrics[exchange_id])
                    
                    if exchange_id in self.optimization_params:
                        config['exchanges'][exchange_id]['optimization'] = asdict(self.optimization_params[exchange_id])
                    
                    if exchange_id in self.symbols_by_exchange:
                        config['exchanges'][exchange_id]['symbols'] = list(self.symbols_by_exchange[exchange_id])
                
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                
                logger.info(f"Saved exchange configuration to {config_path}")
                return True
            except Exception as e:
                logger.error(f"Error saving exchange configuration to {config_path}: {e}")
                return False
    
    def _recalculate_optimization_params(self, exchange_id: str) -> None:
        """
        Recalculate optimization parameters based on performance metrics.
        
        Args:
            exchange_id: Exchange identifier
        """
        if (exchange_id not in self.performance_metrics or
            exchange_id not in self.optimization_params):
            return
        
        try:
            performance = self.performance_metrics[exchange_id]
            optimization = self.optimization_params[exchange_id]
            
            # Adjust slippage tolerance based on typical slippage
            optimization.max_slippage_tolerance_bps = max(5.0, performance.market_order_slippage_bps * 1.5)
            
            # Adjust limit order distance based on volatility
            optimization.default_limit_order_distance_bps = max(0.5, performance.price_volatility * 25)
            
            # Adjust order refresh rate based on fill times
            optimization.optimal_order_refresh_ms = max(1000, min(60000, performance.avg_fill_time_ms * 10))
            
            # Adjust urgency thresholds based on fill rates
            if performance.limit_order_fill_rate < 0.7:
                # Low fill rates require more aggressive orders
                optimization.use_market_threshold_urgency = 0.7
            elif performance.limit_order_fill_rate > 0.9:
                # High fill rates allow more passive orders
                optimization.use_market_threshold_urgency = 0.85
            
            # Update optimization timestamp
            optimization.last_optimized = time.time()
            optimization.optimization_version += 1
            
            logger.debug(f"Recalculated optimization parameters for {exchange_id}")
        except Exception as e:
            logger.error(f"Error recalculating optimization parameters for {exchange_id}: {e}")


# Singleton instance
_registry_instance = None

def get_exchange_registry(config_path: Optional[str] = None) -> ExchangeCapabilityRegistry:
    """
    Get the global exchange capability registry instance.
    
    Args:
        config_path: Path to configuration file (only used on first call)
        
    Returns:
        ExchangeCapabilityRegistry instance
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ExchangeCapabilityRegistry(config_path)
    return _registry_instance 