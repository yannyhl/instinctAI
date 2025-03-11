"""
Smart Order Router

This module provides smart order routing capabilities that select the optimal exchange
and order parameters for executing trades. The router uses exchange capabilities,
performance metrics, and market conditions to make intelligent routing decisions.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import numpy as np

from advanced_trading.execution.optimization.profiles import (
    get_exchange_registry, get_exchange_profiler,
    ExchangeCapabilities, ExchangePerformance
)

# Initialize logger
logger = logging.getLogger(__name__)

class RoutingPriority(Enum):
    """Priority levels for exchange selection."""
    LOWEST_FEES = "lowest_fees"
    BEST_EXECUTION = "best_execution"
    FASTEST_EXECUTION = "fastest_execution"
    HIGHEST_RELIABILITY = "highest_reliability"
    BEST_LIQUIDITY = "best_liquidity"
    BALANCED = "balanced"
    CUSTOM = "custom"

@dataclass
class OrderRoutingParameters:
    """Parameters for routing an order."""
    symbol: str
    side: str  # "buy" or "sell"
    size: float
    size_usd: float
    order_type: str  # "market", "limit", etc.
    price: Optional[float] = None  # Required for limit orders
    urgency: float = 0.5  # 0.0-1.0, higher = more urgent
    max_slippage_bps: float = 10.0  # Maximum acceptable slippage in basis points
    time_in_force: str = "good_till_cancel"  # GTC, IOC, FOK
    post_only: bool = False
    reduce_only: bool = False
    allow_partial: bool = True  # Allow partial fills
    allow_split: bool = True  # Allow splitting across exchanges
    exclude_exchanges: List[str] = None  # Exchanges to exclude
    only_exchanges: List[str] = None  # Only use these exchanges
    priority: RoutingPriority = RoutingPriority.BALANCED
    custom_weights: Dict[str, float] = None  # Custom weighting for CUSTOM priority
    routing_deadline_ms: Optional[int] = None  # Deadline for making routing decision

@dataclass
class ExchangeRoutingDecision:
    """Routing decision for a specific exchange."""
    exchange_id: str
    size: float  # Size in base currency
    price: Optional[float] = None
    order_type: str = "market"
    time_in_force: str = "good_till_cancel"
    post_only: bool = False
    reduce_only: bool = False
    score: float = 0.0  # Routing score (higher is better)
    expected_fee: float = 0.0  # Expected fee in quote currency
    expected_slippage: float = 0.0  # Expected slippage in basis points
    expected_fill_time_ms: float = 0.0  # Expected fill time in milliseconds
    estimated_impact: float = 0.0  # Estimated market impact in basis points

@dataclass
class RoutingDecision:
    """Complete routing decision for an order."""
    order_id: str
    symbol: str
    side: str
    total_size: float
    total_size_usd: float
    exchange_decisions: List[ExchangeRoutingDecision]
    is_split: bool = False
    routing_time_ms: float = 0.0
    timestamp: float = 0.0
    execution_strategy: str = "direct"  # direct, staged, adaptive

class SmartOrderRouter:
    """
    Smart Order Router for determining the optimal exchange and parameters
    for order execution.
    
    The router analyzes exchange capabilities, performance metrics, and current
    market conditions to make intelligent routing decisions.
    """
    
    def __init__(self, 
                 default_priority: RoutingPriority = RoutingPriority.BALANCED,
                 min_data_points: int = 10,
                 reliability_threshold: float = 0.95,
                 max_exchanges_per_order: int = 3,
                 custom_exchange_weights: Dict[str, float] = None,
                 registry = None,
                 profiler = None):
        """
        Initialize the Smart Order Router.
        
        Args:
            default_priority: Default routing priority
            min_data_points: Minimum data points required for reliable metrics
            reliability_threshold: Minimum reliability score to consider an exchange
            max_exchanges_per_order: Maximum number of exchanges to split an order
            custom_exchange_weights: Custom weights for specific exchanges
            registry: ExchangeCapabilityRegistry instance (or None to use singleton)
            profiler: ExchangeProfiler instance (or None to use singleton)
        """
        self.default_priority = default_priority
        self.min_data_points = min_data_points
        self.reliability_threshold = reliability_threshold
        self.max_exchanges_per_order = max_exchanges_per_order
        self.custom_exchange_weights = custom_exchange_weights or {}
        
        # Get registry and profiler instances
        self.registry = registry or get_exchange_registry()
        self.profiler = profiler or get_exchange_profiler()
        
        # Mapping of routing priorities to scoring functions
        self.priority_scoring_functions = {
            RoutingPriority.LOWEST_FEES: self._score_for_lowest_fees,
            RoutingPriority.BEST_EXECUTION: self._score_for_best_execution,
            RoutingPriority.FASTEST_EXECUTION: self._score_for_fastest_execution,
            RoutingPriority.HIGHEST_RELIABILITY: self._score_for_highest_reliability,
            RoutingPriority.BEST_LIQUIDITY: self._score_for_best_liquidity,
            RoutingPriority.BALANCED: self._score_balanced,
            RoutingPriority.CUSTOM: self._score_custom
        }
        
        # Routing decision cache
        self.decision_cache = {}
        self.decision_history = []
        self.max_history_size = 1000
        
        logger.info(f"Smart Order Router initialized with {default_priority} priority")
    
    def route_order(self, params: OrderRoutingParameters) -> RoutingDecision:
        """
        Route an order to the best exchange(s) based on the provided parameters.
        
        Args:
            params: Order routing parameters
            
        Returns:
            RoutingDecision containing the optimal routing strategy
        """
        start_time = time.time()
        order_id = f"order_{int(start_time * 1000)}"
        
        # Validate parameters
        self._validate_parameters(params)
        
        # Get eligible exchanges for this symbol
        eligible_exchanges = self._get_eligible_exchanges(params)
        
        if not eligible_exchanges:
            logger.warning(f"No eligible exchanges found for {params.symbol}")
            return RoutingDecision(
                order_id=order_id,
                symbol=params.symbol,
                side=params.side,
                total_size=params.size,
                total_size_usd=params.size_usd,
                exchange_decisions=[],
                is_split=False,
                routing_time_ms=(time.time() - start_time) * 1000,
                timestamp=time.time(),
                execution_strategy="direct"
            )
        
        # Score each exchange
        exchange_scores = self._score_exchanges(eligible_exchanges, params)
        
        # Select the best exchange(s)
        if params.allow_split and len(exchange_scores) > 1 and params.size_usd > 1000:
            # Consider splitting the order
            exchange_decisions = self._split_order(exchange_scores, params)
            is_split = len(exchange_decisions) > 1
        else:
            # Use single best exchange
            best_exchange = exchange_scores[0][0]
            exchange_decisions = [self._create_exchange_decision(best_exchange, params, exchange_scores[0][1])]
            is_split = False
        
        # Create routing decision
        decision = RoutingDecision(
            order_id=order_id,
            symbol=params.symbol,
            side=params.side,
            total_size=params.size,
            total_size_usd=params.size_usd,
            exchange_decisions=exchange_decisions,
            is_split=is_split,
            routing_time_ms=(time.time() - start_time) * 1000,
            timestamp=time.time(),
            execution_strategy="direct" if not is_split else "split"
        )
        
        # Add to history
        self._add_to_history(decision)
        
        return decision
    
    def _validate_parameters(self, params: OrderRoutingParameters) -> None:
        """Validate routing parameters."""
        if params.size <= 0:
            raise ValueError("Order size must be positive")
        
        if params.order_type == "limit" and params.price is None:
            raise ValueError("Limit orders require a price")
        
        if params.priority == RoutingPriority.CUSTOM and not params.custom_weights:
            raise ValueError("Custom priority requires custom_weights")
    
    def _get_eligible_exchanges(self, params: OrderRoutingParameters) -> List[str]:
        """Get eligible exchanges for this order."""
        # Get exchanges that support this symbol
        exchanges = self.registry.get_exchanges_for_symbol(params.symbol)
        
        # Apply exclusions and inclusions
        if params.exclude_exchanges:
            exchanges = [e for e in exchanges if e not in params.exclude_exchanges]
        
        if params.only_exchanges:
            exchanges = [e for e in exchanges if e in params.only_exchanges]
        
        # Filter by capabilities
        eligible = []
        for exchange_id in exchanges:
            capabilities = self.registry.get_exchange_capabilities(exchange_id)
            if not capabilities:
                continue
            
            # Check order type support
            if params.order_type == "market" and not capabilities.supports_market_orders:
                continue
            if params.order_type == "limit" and not capabilities.supports_limit_orders:
                continue
            
            # Check for post-only and reduce-only support
            if params.post_only and not capabilities.supports_post_only:
                continue
            if params.reduce_only and not capabilities.supports_reduce_only:
                continue
            
            # Check minimum order size
            if params.size < capabilities.min_order_size:
                continue
            
            # Check maximum order size
            if capabilities.max_order_size and params.size > capabilities.max_order_size:
                # Still eligible if splitting is allowed
                if not params.allow_split:
                    continue
            
            # Check time in force compatibility
            if params.time_in_force == "fill_or_kill" and not capabilities.supports_fill_or_kill:
                continue
            if params.time_in_force == "immediate_or_cancel" and not capabilities.supports_immediate_or_cancel:
                continue
            
            # All checks passed
            eligible.append(exchange_id)
        
        return eligible
    
    def _score_exchanges(self, exchanges: List[str], params: OrderRoutingParameters) -> List[Tuple[str, float]]:
        """
        Score eligible exchanges based on priority and parameters.
        
        Returns:
            List of (exchange_id, score) tuples, sorted by descending score
        """
        scores = []
        priority = params.priority if params.priority else self.default_priority
        scoring_function = self.priority_scoring_functions[priority]
        
        for exchange_id in exchanges:
            # Get exchange data
            capabilities = self.registry.get_exchange_capabilities(exchange_id)
            performance = self.registry.get_exchange_performance(exchange_id)
            
            if not capabilities or not performance:
                continue
            
            # Calculate score using the appropriate function
            if priority == RoutingPriority.CUSTOM:
                score = scoring_function(exchange_id, capabilities, performance, params, params.custom_weights)
            else:
                score = scoring_function(exchange_id, capabilities, performance, params)
            
            # Apply custom exchange weight if available
            if exchange_id in self.custom_exchange_weights:
                score *= self.custom_exchange_weights[exchange_id]
            
            scores.append((exchange_id, score))
        
        # Sort by descending score
        return sorted(scores, key=lambda x: x[1], reverse=True)
    
    def _score_for_lowest_fees(self, exchange_id: str, capabilities: ExchangeCapabilities, 
                            performance: ExchangePerformance, params: OrderRoutingParameters) -> float:
        """Score based on lowest fees."""
        # Determine applicable fee
        if params.order_type == "market":
            fee = capabilities.taker_fee
        else:
            fee = capabilities.maker_fee if params.post_only else capabilities.taker_fee
        
        # Calculate score (inverse of fee so lower fees get higher scores)
        base_score = 1.0 / (fee + 0.0001)  # Add small value to prevent division by zero
        
        # Add small weight for reliability
        reliability_score = performance.exchange_reliability_score / 10
        
        return base_score * 0.9 + reliability_score * 0.1
    
    def _score_for_best_execution(self, exchange_id: str, capabilities: ExchangeCapabilities, 
                               performance: ExchangePerformance, params: OrderRoutingParameters) -> float:
        """Score based on best execution quality."""
        if params.order_type == "market":
            # For market orders, focus on slippage
            slippage_score = 1.0 / (performance.market_order_slippage_bps + 1.0)
            fee_score = 1.0 / (capabilities.taker_fee + 0.0001)
            reliability_score = performance.exchange_reliability_score / 10
            
            # Weighted combination
            return slippage_score * 0.6 + fee_score * 0.2 + reliability_score * 0.2
        else:
            # For limit orders, focus on fill rate
            fill_rate_score = performance.limit_order_fill_rate
            fee_score = 1.0 / (capabilities.maker_fee + 0.0001)
            reliability_score = performance.exchange_reliability_score / 10
            
            # Weighted combination
            return fill_rate_score * 0.6 + fee_score * 0.2 + reliability_score * 0.2
    
    def _score_for_fastest_execution(self, exchange_id: str, capabilities: ExchangeCapabilities, 
                                  performance: ExchangePerformance, params: OrderRoutingParameters) -> float:
        """Score based on fastest execution."""
        if params.order_type == "market":
            # For market orders, focus on API latency
            latency_score = 1.0 / (performance.avg_api_latency_ms + 1.0)
            reliability_score = performance.exchange_reliability_score / 10
            
            # Weighted combination
            return latency_score * 0.8 + reliability_score * 0.2
        else:
            # For limit orders, focus on fill time
            fill_time_score = 1.0 / (performance.avg_fill_time_ms + 1.0)
            fill_rate_score = performance.limit_order_fill_rate
            reliability_score = performance.exchange_reliability_score / 10
            
            # Weighted combination
            return fill_time_score * 0.5 + fill_rate_score * 0.3 + reliability_score * 0.2
    
    def _score_for_highest_reliability(self, exchange_id: str, capabilities: ExchangeCapabilities, 
                                     performance: ExchangePerformance, params: OrderRoutingParameters) -> float:
        """Score based on highest reliability."""
        reliability_score = performance.exchange_reliability_score / 10
        api_reliability_score = performance.api_reliability_pct / 100
        
        # Get symbol-specific metrics if available
        symbol_metrics = self.profiler.get_symbol_metrics(exchange_id, params.symbol)
        symbol_liquidity_score = 0.0
        if symbol_metrics and 'avg_liquidity_depth_usd' in symbol_metrics:
            # Normalize liquidity score (0-1)
            liquidity_depth = symbol_metrics['avg_liquidity_depth_usd']
            symbol_liquidity_score = min(1.0, liquidity_depth / 5000000)
        
        # Weighted combination
        return reliability_score * 0.5 + api_reliability_score * 0.3 + symbol_liquidity_score * 0.2
    
    def _score_for_best_liquidity(self, exchange_id: str, capabilities: ExchangeCapabilities, 
                               performance: ExchangePerformance, params: OrderRoutingParameters) -> float:
        """Score based on best liquidity."""
        # Get symbol-specific metrics
        symbol_metrics = self.profiler.get_symbol_metrics(exchange_id, params.symbol)
        
        if not symbol_metrics or 'avg_liquidity_depth_usd' not in symbol_metrics:
            # Fall back to general liquidity metrics
            liquidity_score = performance.avg_liquidity_depth_usd / 1000000  # Normalize to 0-10 range
        else:
            liquidity_score = symbol_metrics['avg_liquidity_depth_usd'] / 1000000
        
        # Cap score at 10
        liquidity_score = min(10.0, liquidity_score)
        
        # Include spread in scoring
        spread_score = 0.0
        if symbol_metrics and 'avg_spread_bps' in symbol_metrics:
            spread_score = 10.0 / (symbol_metrics['avg_spread_bps'] + 1.0)
        else:
            spread_score = 10.0 / (performance.avg_spread_bps + 1.0)
        
        # Weighted combination
        return liquidity_score * 0.7 + spread_score * 0.3
    
    def _score_balanced(self, exchange_id: str, capabilities: ExchangeCapabilities, 
                      performance: ExchangePerformance, params: OrderRoutingParameters) -> float:
        """Score based on balanced consideration of all factors."""
        # Get individual scores
        fee_score = self._score_for_lowest_fees(exchange_id, capabilities, performance, params)
        execution_score = self._score_for_best_execution(exchange_id, capabilities, performance, params)
        speed_score = self._score_for_fastest_execution(exchange_id, capabilities, performance, params)
        reliability_score = self._score_for_highest_reliability(exchange_id, capabilities, performance, params)
        liquidity_score = self._score_for_best_liquidity(exchange_id, capabilities, performance, params)
        
        # Normalize scores
        fee_score /= 10
        execution_score /= 10
        speed_score /= 10
        reliability_score /= 10
        liquidity_score /= 10
        
        # Apply urgency-based weights
        if params.urgency < 0.33:
            # Low urgency: prioritize fees and reliable execution
            weights = {
                'fee': 0.35,
                'execution': 0.25,
                'speed': 0.05,
                'reliability': 0.25,
                'liquidity': 0.10
            }
        elif params.urgency < 0.66:
            # Medium urgency: balanced approach
            weights = {
                'fee': 0.20,
                'execution': 0.25,
                'speed': 0.15,
                'reliability': 0.20,
                'liquidity': 0.20
            }
        else:
            # High urgency: prioritize speed and liquidity
            weights = {
                'fee': 0.10,
                'execution': 0.20,
                'speed': 0.30,
                'reliability': 0.15,
                'liquidity': 0.25
            }
        
        # Calculate weighted score
        weighted_score = (
            fee_score * weights['fee'] +
            execution_score * weights['execution'] +
            speed_score * weights['speed'] +
            reliability_score * weights['reliability'] +
            liquidity_score * weights['liquidity']
        )
        
        return weighted_score * 10  # Scale back to 0-10 range
    
    def _score_custom(self, exchange_id: str, capabilities: ExchangeCapabilities, 
                    performance: ExchangePerformance, params: OrderRoutingParameters, 
                    weights: Dict[str, float]) -> float:
        """Score based on custom weights."""
        scores = {}
        
        # Calculate individual category scores
        if 'fee' in weights:
            scores['fee'] = self._score_for_lowest_fees(exchange_id, capabilities, performance, params) / 10
        
        if 'execution' in weights:
            scores['execution'] = self._score_for_best_execution(exchange_id, capabilities, performance, params) / 10
        
        if 'speed' in weights:
            scores['speed'] = self._score_for_fastest_execution(exchange_id, capabilities, performance, params) / 10
        
        if 'reliability' in weights:
            scores['reliability'] = self._score_for_highest_reliability(exchange_id, capabilities, performance, params) / 10
        
        if 'liquidity' in weights:
            scores['liquidity'] = self._score_for_best_liquidity(exchange_id, capabilities, performance, params) / 10
        
        # Calculate weighted score
        weighted_score = sum(scores.get(category, 0) * weight 
                           for category, weight in weights.items())
        
        # Normalize result to 0-10 range
        total_weight = sum(weights.values())
        if total_weight > 0:
            weighted_score = (weighted_score / total_weight) * 10
        
        return weighted_score
    
    def _split_order(self, exchange_scores: List[Tuple[str, float]], 
                   params: OrderRoutingParameters) -> List[ExchangeRoutingDecision]:
        """
        Split an order across multiple exchanges based on their scores.
        
        Args:
            exchange_scores: List of (exchange_id, score) tuples
            params: Order routing parameters
            
        Returns:
            List of ExchangeRoutingDecision objects
        """
        # Limit to max exchanges
        exchange_scores = exchange_scores[:self.max_exchanges_per_order]
        
        # Calculate allocation percentages based on scores
        total_score = sum(score for _, score in exchange_scores)
        allocations = [(exchange, score / total_score) for exchange, score in exchange_scores]
        
        # Create exchange decisions
        decisions = []
        remaining_size = params.size
        
        for i, (exchange_id, allocation) in enumerate(allocations):
            # For the last exchange, use all remaining size
            if i == len(allocations) - 1:
                exchange_size = remaining_size
            else:
                # Calculate size based on allocation percentage
                exchange_size = params.size * allocation
                # Round to appropriate precision
                capabilities = self.registry.get_exchange_capabilities(exchange_id)
                if capabilities and capabilities.quantity_precision:
                    precision = capabilities.quantity_precision
                    exchange_size = round(exchange_size, precision)
                remaining_size -= exchange_size
            
            # Skip if size is too small
            if exchange_size <= 0:
                continue
            
            # Create decision for this exchange
            decision = self._create_exchange_decision(
                exchange_id, params, exchange_scores[i][1], exchange_size
            )
            decisions.append(decision)
        
        return decisions
    
    def _create_exchange_decision(self, exchange_id: str, params: OrderRoutingParameters, 
                               score: float, size: Optional[float] = None) -> ExchangeRoutingDecision:
        """Create a routing decision for a specific exchange."""
        if size is None:
            size = params.size
        
        # Get exchange data
        capabilities = self.registry.get_exchange_capabilities(exchange_id)
        performance = self.registry.get_exchange_performance(exchange_id)
        
        # Calculate expected fee
        if params.order_type == "market" or not params.post_only:
            fee_rate = capabilities.taker_fee if capabilities else 0.001
        else:
            fee_rate = capabilities.maker_fee if capabilities else 0.0005
        
        expected_fee = params.size_usd * fee_rate
        
        # Get estimated slippage
        if params.order_type == "market":
            expected_slippage = performance.market_order_slippage_bps if performance else 5.0
        else:
            expected_slippage = 0.0  # No slippage for limit orders
        
        # Get expected fill time
        if params.order_type == "market":
            expected_fill_time = performance.avg_api_latency_ms if performance else 100.0
        else:
            # For limit orders, fill time depends on price aggressiveness
            # We use a placeholder here as actual fill time is hard to predict
            expected_fill_time = performance.avg_fill_time_ms if performance else 2000.0
        
        # Get estimated market impact
        symbol_metrics = self.profiler.get_symbol_metrics(exchange_id, params.symbol)
        estimated_impact = 0.0
        if symbol_metrics and 'market_impact_estimate' in symbol_metrics:
            estimated_impact = symbol_metrics['market_impact_estimate']
        
        # Create decision
        return ExchangeRoutingDecision(
            exchange_id=exchange_id,
            size=size,
            price=params.price,
            order_type=params.order_type,
            time_in_force=params.time_in_force,
            post_only=params.post_only,
            reduce_only=params.reduce_only,
            score=score,
            expected_fee=expected_fee,
            expected_slippage=expected_slippage,
            expected_fill_time_ms=expected_fill_time,
            estimated_impact=estimated_impact
        )
    
    def _add_to_history(self, decision: RoutingDecision) -> None:
        """Add a routing decision to the history."""
        self.decision_history.append(decision)
        
        # Limit history size
        if len(self.decision_history) > self.max_history_size:
            self.decision_history.pop(0)
    
    def get_decision_history(self, 
                          symbol: Optional[str] = None, 
                          exchange_id: Optional[str] = None,
                          start_time: Optional[float] = None,
                          end_time: Optional[float] = None) -> List[RoutingDecision]:
        """Get history of routing decisions with optional filtering."""
        filtered = self.decision_history
        
        if symbol:
            filtered = [d for d in filtered if d.symbol == symbol]
        
        if exchange_id:
            filtered = [d for d in filtered if any(ed.exchange_id == exchange_id 
                                                for ed in d.exchange_decisions)]
        
        if start_time:
            filtered = [d for d in filtered if d.timestamp >= start_time]
        
        if end_time:
            filtered = [d for d in filtered if d.timestamp <= end_time]
        
        return filtered
    
    def get_exchange_performance_summary(self, exchange_id: str) -> Dict[str, Any]:
        """Get a summary of exchange performance based on routing history."""
        decisions = [d for d in self.decision_history 
                   if any(ed.exchange_id == exchange_id for ed in d.exchange_decisions)]
        
        if not decisions:
            return {
                "exchange_id": exchange_id,
                "total_orders": 0,
                "total_volume": 0.0,
                "avg_score": 0.0,
                "usage_frequency": 0.0
            }
        
        # Calculate metrics
        total_orders = len(decisions)
        total_volume = sum(d.total_size for d in decisions)
        
        # Extract scores
        scores = []
        for decision in decisions:
            for ed in decision.exchange_decisions:
                if ed.exchange_id == exchange_id:
                    scores.append(ed.score)
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Calculate usage frequency
        usage_frequency = total_orders / len(self.decision_history) if self.decision_history else 0.0
        
        return {
            "exchange_id": exchange_id,
            "total_orders": total_orders,
            "total_volume": total_volume,
            "avg_score": avg_score,
            "usage_frequency": usage_frequency
        }

def get_smart_order_router() -> SmartOrderRouter:
    """Get or create a SmartOrderRouter instance."""
    # This is a simple singleton implementation
    if not hasattr(get_smart_order_router, "instance"):
        get_smart_order_router.instance = SmartOrderRouter()
    
    return get_smart_order_router.instance 