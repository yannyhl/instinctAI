"""
Order Type Optimizer

This module provides functionality to select the optimal order type and parameters
based on market conditions, exchange capabilities, and execution objectives.
It works alongside the Smart Order Router to optimize execution quality.
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union

from advanced_trading.execution.optimization.profiles import (
    get_exchange_registry, get_exchange_profiler,
    ExchangeCapabilities, ExchangePerformance, ExchangeOptimizationParams
)

# Initialize logger
logger = logging.getLogger(__name__)

class OrderTypeCategory(Enum):
    """Categories of order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    
class TimeInForceType(Enum):
    """Time-in-force options."""
    GOOD_TILL_CANCEL = "good_till_cancel"
    IMMEDIATE_OR_CANCEL = "immediate_or_cancel"
    FILL_OR_KILL = "fill_or_kill"
    DAY = "day"

@dataclass
class MarketCondition:
    """Current market condition metrics."""
    volatility: float = 0.0
    spread_bps: float = 0.0
    liquidity_depth_usd: float = 0.0
    price_trend: float = 0.0  # -1.0 to 1.0, negative means downtrend
    volume_profile: float = 0.0  # 0.0 to 1.0, higher means higher volume
    is_high_volatility: bool = False
    is_tight_spread: bool = False
    is_deep_liquidity: bool = False

@dataclass
class OrderTypeParameters:
    """Parameters for a specific order type."""
    order_type: str
    
    # Common parameters
    time_in_force: str = "good_till_cancel"
    post_only: bool = False
    reduce_only: bool = False
    
    # Limit order parameters
    price_offset_bps: float = 0.0  # Basis points from reference price
    trigger_price_offset_bps: float = 0.0  # For stop orders
    
    # Advanced parameters
    retry_attempts: int = 0
    retry_delay_ms: float = 1000.0
    expiry_seconds: Optional[int] = None
    iceberg_size: Optional[float] = None
    
    # Custom parameters
    custom_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionPreferences:
    """User preferences for execution."""
    urgency: float = 0.5  # 0.0 to 1.0
    cost_sensitivity: float = 0.5  # 0.0 to 1.0
    impact_sensitivity: float = 0.5  # 0.0 to 1.0
    completion_priority: float = 0.5  # 0.0 to 1.0
    minimize_time: bool = False
    aggressive_in_favorable_trend: bool = True
    maximize_maker_orders: bool = False
    acceptable_partial_fill_pct: float = 0.0  # Percentage of order that must be filled
    
@dataclass
class OrderTypeOptimizationRequest:
    """Request for order type optimization."""
    exchange_id: str
    symbol: str
    side: str  # "buy" or "sell"
    size: float
    size_usd: float
    reference_price: Optional[float] = None
    market_condition: Optional[MarketCondition] = None
    preferences: ExecutionPreferences = field(default_factory=ExecutionPreferences)
    available_order_types: List[str] = field(default_factory=list)
    custom_constraints: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OrderTypeRecommendation:
    """Recommendation for order type and parameters."""
    order_type: str
    parameters: OrderTypeParameters
    expected_fill_probability: float
    expected_cost_bps: float
    expected_market_impact_bps: float
    expected_time_to_fill_ms: float
    expected_implementation_shortfall_bps: float
    confidence: float  # 0.0 to 1.0
    reasoning: str
    alternatives: List[Tuple[str, OrderTypeParameters, float]] = field(default_factory=list)

class OrderTypeOptimizer:
    """
    Optimizer that selects the best order type and parameters based on
    market conditions, exchange capabilities, and execution objectives.
    """
    
    def __init__(self, 
                 default_urgency: float = 0.5,
                 default_cost_sensitivity: float = 0.5,
                 max_alternatives: int = 3,
                 registry = None,
                 profiler = None):
        """
        Initialize the Order Type Optimizer.
        
        Args:
            default_urgency: Default urgency level (0.0 to 1.0)
            default_cost_sensitivity: Default cost sensitivity (0.0 to 1.0)
            max_alternatives: Maximum number of alternative recommendations
            registry: ExchangeCapabilityRegistry instance (or None to use singleton)
            profiler: ExchangeProfiler instance (or None to use singleton)
        """
        self.default_urgency = default_urgency
        self.default_cost_sensitivity = default_cost_sensitivity
        self.max_alternatives = max_alternatives
        
        # Get registry and profiler instances
        self.registry = registry or get_exchange_registry()
        self.profiler = profiler or get_exchange_profiler()
        
        # History of recommendations
        self.recommendation_history = []
        self.max_history_size = 1000
        
        # Market condition thresholds
        self.market_condition_thresholds = {
            'high_volatility_threshold': 0.02,  # 2% price variation
            'tight_spread_threshold_bps': 5.0,  # 5 basis points
            'deep_liquidity_threshold_usd': 1000000.0  # $1M of liquidity
        }
        
        logger.info(f"Order Type Optimizer initialized with default urgency {default_urgency}")
    
    def recommend_order_type(self, request: OrderTypeOptimizationRequest) -> OrderTypeRecommendation:
        """
        Recommend the optimal order type and parameters.
        
        Args:
            request: Order type optimization request
            
        Returns:
            OrderTypeRecommendation with optimal order type and parameters
        """
        start_time = time.time()
        
        # Get exchange capabilities
        capabilities = self.registry.get_exchange_capabilities(request.exchange_id)
        if not capabilities:
            logger.warning(f"No capabilities found for exchange {request.exchange_id}")
            return self._create_default_recommendation(request)
        
        # Get exchange performance metrics
        performance = self.registry.get_exchange_performance(request.exchange_id)
        if not performance:
            logger.warning(f"No performance metrics found for exchange {request.exchange_id}")
            return self._create_default_recommendation(request)
        
        # Get optimization parameters
        optimization_params = self.registry.get_optimization_params(request.exchange_id)
        if not optimization_params:
            logger.warning(f"No optimization parameters found for exchange {request.exchange_id}")
            return self._create_default_recommendation(request)
        
        # Get or update market condition
        market_condition = request.market_condition
        if not market_condition:
            market_condition = self._get_market_condition(request.exchange_id, request.symbol)
        
        # Filter available order types based on exchange capabilities
        available_types = self._filter_available_order_types(
            request.available_order_types if request.available_order_types else ["market", "limit"],
            capabilities
        )
        
        if not available_types:
            logger.warning(f"No available order types for {request.exchange_id}")
            return self._create_default_recommendation(request)
        
        # Score each order type
        type_scores = self._score_order_types(
            available_types, 
            request, 
            capabilities, 
            performance, 
            optimization_params, 
            market_condition
        )
        
        # Select best order type and generate parameters
        best_type, best_score = type_scores[0]
        parameters = self._generate_parameters(
            best_type, 
            request, 
            capabilities, 
            performance, 
            optimization_params, 
            market_condition
        )
        
        # Create recommendation
        recommendation = self._create_recommendation(
            best_type,
            parameters,
            request,
            capabilities,
            performance,
            market_condition,
            best_score
        )
        
        # Generate alternatives
        alternatives = []
        for order_type, score in type_scores[1:self.max_alternatives+1]:
            alt_parameters = self._generate_parameters(
                order_type, 
                request, 
                capabilities, 
                performance, 
                optimization_params, 
                market_condition
            )
            alternatives.append((order_type, alt_parameters, score))
        
        recommendation.alternatives = alternatives
        
        # Add to history
        self._add_to_history(recommendation)
        
        return recommendation
    
    def _create_default_recommendation(self, request: OrderTypeOptimizationRequest) -> OrderTypeRecommendation:
        """Create a default recommendation when optimization isn't possible."""
        order_type = "market"
        parameters = OrderTypeParameters(
            order_type=order_type,
            time_in_force="good_till_cancel"
        )
        
        return OrderTypeRecommendation(
            order_type=order_type,
            parameters=parameters,
            expected_fill_probability=1.0,
            expected_cost_bps=20.0,  # Assuming 20bps cost for market orders
            expected_market_impact_bps=10.0,
            expected_time_to_fill_ms=500.0,
            expected_implementation_shortfall_bps=30.0,
            confidence=0.5,
            reasoning="Default recommendation due to insufficient data"
        )
    
    def _filter_available_order_types(self, 
                                    requested_types: List[str], 
                                    capabilities: ExchangeCapabilities) -> List[str]:
        """Filter order types based on exchange capabilities."""
        available = []
        
        for order_type in requested_types:
            if order_type == "market" and capabilities.supports_market_orders:
                available.append(order_type)
            elif order_type == "limit" and capabilities.supports_limit_orders:
                available.append(order_type)
            elif order_type in ["stop", "stop_market"] and capabilities.supports_stop_orders:
                available.append(order_type)
            elif order_type == "stop_limit" and capabilities.supports_stop_limit_orders:
                available.append(order_type)
            elif order_type == "trailing_stop" and capabilities.supports_trailing_stop:
                available.append(order_type)
        
        # Always include market if available and list would be empty
        if not available and capabilities.supports_market_orders:
            available.append("market")
        
        return available
    
    def _get_market_condition(self, exchange_id: str, symbol: str) -> MarketCondition:
        """Get current market condition metrics."""
        # Get symbol-specific metrics from profiler
        symbol_metrics = self.profiler.get_symbol_metrics(exchange_id, symbol)
        
        # Default condition
        condition = MarketCondition()
        
        if symbol_metrics:
            # Extract metrics if available
            if 'avg_spread_bps' in symbol_metrics:
                condition.spread_bps = symbol_metrics['avg_spread_bps']
                
            if 'avg_liquidity_depth_usd' in symbol_metrics:
                condition.liquidity_depth_usd = symbol_metrics['avg_liquidity_depth_usd']
                
            if 'price_volatility' in symbol_metrics:
                condition.volatility = symbol_metrics['price_volatility']
                
            if 'price_trend' in symbol_metrics:
                condition.price_trend = symbol_metrics['price_trend']
                
            if 'volume_profile' in symbol_metrics:
                condition.volume_profile = symbol_metrics['volume_profile']
        
        # Set boolean flags based on thresholds
        condition.is_high_volatility = condition.volatility >= self.market_condition_thresholds['high_volatility_threshold']
        condition.is_tight_spread = condition.spread_bps <= self.market_condition_thresholds['tight_spread_threshold_bps']
        condition.is_deep_liquidity = condition.liquidity_depth_usd >= self.market_condition_thresholds['deep_liquidity_threshold_usd']
        
        return condition
    
    def _score_order_types(self,
                         order_types: List[str],
                         request: OrderTypeOptimizationRequest,
                         capabilities: ExchangeCapabilities,
                         performance: ExchangePerformance,
                         optimization_params: ExchangeOptimizationParams,
                         market_condition: MarketCondition) -> List[Tuple[str, float]]:
        """
        Score order types based on request parameters and market conditions.
        
        Returns:
            List of (order_type, score) tuples, sorted by descending score
        """
        scores = []
        preferences = request.preferences
        
        for order_type in order_types:
            # Calculate base scores for different metrics
            fill_probability_score = self._calculate_fill_probability_score(order_type, request, market_condition)
            cost_score = self._calculate_cost_score(order_type, request, capabilities, performance)
            speed_score = self._calculate_speed_score(order_type, request, performance, market_condition)
            impact_score = self._calculate_impact_score(order_type, request, market_condition)
            
            # Apply preference weightings
            urgency = preferences.urgency
            cost_sensitivity = preferences.cost_sensitivity
            impact_sensitivity = preferences.impact_sensitivity
            completion_priority = preferences.completion_priority
            
            # Higher urgency prioritizes speed and fill probability over cost
            if urgency > 0.7:
                fill_weight = 0.4
                cost_weight = 0.1
                speed_weight = 0.4
                impact_weight = 0.1
            elif urgency > 0.3:
                fill_weight = 0.3
                cost_weight = 0.3
                speed_weight = 0.3
                impact_weight = 0.1
            else:
                fill_weight = 0.2
                cost_weight = 0.5
                speed_weight = 0.1
                impact_weight = 0.2
                
            # Apply cost sensitivity
            cost_weight *= (1.0 + cost_sensitivity)
            
            # Apply impact sensitivity
            impact_weight *= (1.0 + impact_sensitivity)
            
            # Apply completion priority
            fill_weight *= (1.0 + completion_priority)
            
            # Normalize weights
            total_weight = fill_weight + cost_weight + speed_weight + impact_weight
            fill_weight /= total_weight
            cost_weight /= total_weight
            speed_weight /= total_weight
            impact_weight /= total_weight
            
            # Calculate weighted score
            weighted_score = (
                fill_probability_score * fill_weight +
                cost_score * cost_weight +
                speed_score * speed_weight +
                impact_score * impact_weight
            )
            
            # Apply additional adjustments based on preferences
            if preferences.minimize_time and order_type == "market":
                weighted_score *= 1.2
                
            if preferences.maximize_maker_orders and order_type == "limit":
                if request.side == "buy":
                    # For buys, post-only limits are beneficial in downtrends
                    if market_condition.price_trend < -0.3:
                        weighted_score *= 1.3
                else:
                    # For sells, post-only limits are beneficial in uptrends
                    if market_condition.price_trend > 0.3:
                        weighted_score *= 1.3
                        
            if preferences.aggressive_in_favorable_trend:
                if (request.side == "buy" and market_condition.price_trend > 0.5) or \
                   (request.side == "sell" and market_condition.price_trend < -0.5):
                    # Market is moving favorably, prioritize market orders
                    if order_type == "market":
                        weighted_score *= 1.2
            
            scores.append((order_type, weighted_score))
        
        # Sort by descending score
        return sorted(scores, key=lambda x: x[1], reverse=True)
    
    def _calculate_fill_probability_score(self, 
                                       order_type: str, 
                                       request: OrderTypeOptimizationRequest, 
                                       market_condition: MarketCondition) -> float:
        """Calculate score based on fill probability."""
        # Market orders always fill (barring extreme conditions)
        if order_type == "market":
            return 1.0
            
        # For limit orders, consider market conditions
        if order_type == "limit":
            # Base fill probability
            base_prob = 0.7
            
            # Adjust for volatility
            if market_condition.is_high_volatility:
                base_prob += 0.1
                
            # Adjust for spread
            if market_condition.is_tight_spread:
                base_prob += 0.1
            else:
                base_prob -= 0.1
                
            # Adjust for liquidity
            if market_condition.is_deep_liquidity:
                base_prob += 0.1
            else:
                base_prob -= 0.1
                
            # Adjust for order size relative to liquidity
            size_to_liquidity_ratio = min(1.0, request.size_usd / max(1.0, market_condition.liquidity_depth_usd))
            size_adjustment = -0.3 * size_to_liquidity_ratio
            base_prob += size_adjustment
            
            return max(0.3, min(0.95, base_prob))
        
        # Stop orders and other conditional orders
        if order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            # Very dependent on market conditions and parameters
            base_prob = 0.6
            
            # Higher probability in volatile markets
            if market_condition.is_high_volatility:
                base_prob += 0.1
            
            return base_prob
            
        # Default for other order types
        return 0.5
    
    def _calculate_cost_score(self, 
                           order_type: str, 
                           request: OrderTypeOptimizationRequest, 
                           capabilities: ExchangeCapabilities, 
                           performance: ExchangePerformance) -> float:
        """Calculate score based on execution cost."""
        # For market orders, we expect to pay taker fees and potentially experience slippage
        if order_type == "market":
            # Base cost is taker fee plus expected slippage
            base_cost = capabilities.taker_fee + (performance.market_order_slippage_bps / 10000)
            
            # Normalize to 0-1 score (lower cost = higher score)
            # Assuming maximum reasonable cost is 50 bps
            cost_score = 1.0 - min(1.0, base_cost * 20000)
            
            return cost_score
            
        # For limit orders, we may pay maker fees (better) or taker fees
        if order_type == "limit":
            # If post-only, we only pay maker fees
            if request.preferences.maximize_maker_orders:
                base_cost = capabilities.maker_fee
            else:
                # Estimate a mix of maker and taker fees based on fill rate
                maker_probability = 0.7  # 70% chance of getting maker fees
                base_cost = (maker_probability * capabilities.maker_fee + 
                          (1 - maker_probability) * capabilities.taker_fee)
            
            # Normalize to 0-1 score
            cost_score = 1.0 - min(1.0, base_cost * 20000)
            
            return cost_score
            
        # For stop orders, assume taker fees
        if order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            base_cost = capabilities.taker_fee
            
            # Normalize to 0-1 score
            cost_score = 1.0 - min(1.0, base_cost * 20000)
            
            return cost_score
            
        # Default for other order types
        return 0.5
    
    def _calculate_speed_score(self, 
                            order_type: str, 
                            request: OrderTypeOptimizationRequest, 
                            performance: ExchangePerformance, 
                            market_condition: MarketCondition) -> float:
        """Calculate score based on execution speed."""
        # Market orders execute almost immediately
        if order_type == "market":
            return 0.95
            
        # Limit orders depend on market conditions
        if order_type == "limit":
            # Base score depends on whether parameters will be aggressive
            if request.preferences.urgency > 0.7:
                # Aggressive limit order (likely to execute quickly)
                base_score = 0.8
            else:
                # Passive limit order (may wait for price to come to it)
                base_score = 0.4
                
            # Adjust for market conditions
            if market_condition.is_high_volatility:
                base_score += 0.1  # More likely to get filled quickly
            
            if market_condition.is_tight_spread:
                base_score += 0.1  # Less price distance to cross
            
            return min(0.9, base_score)
            
        # Stop orders execute quickly once triggered
        if order_type in ["stop", "stop_market"]:
            return 0.8
            
        # Stop limit orders might not execute even when triggered
        if order_type == "stop_limit":
            return 0.7
            
        # Default for other order types
        return 0.5
    
    def _calculate_impact_score(self, 
                             order_type: str, 
                             request: OrderTypeOptimizationRequest, 
                             market_condition: MarketCondition) -> float:
        """Calculate score based on market impact (higher = less impact)."""
        # Calculate size relative to liquidity
        size_to_liquidity_ratio = min(1.0, request.size_usd / max(1.0, market_condition.liquidity_depth_usd))
        
        # Market orders have immediate impact proportional to size
        if order_type == "market":
            impact_score = 1.0 - size_to_liquidity_ratio
            return max(0.2, impact_score)
            
        # Limit orders have less impact
        if order_type == "limit":
            # Post-only limit orders have minimal impact
            if request.preferences.maximize_maker_orders:
                impact_score = 0.9 - (0.3 * size_to_liquidity_ratio)
            else:
                impact_score = 0.8 - (0.4 * size_to_liquidity_ratio)
                
            return max(0.4, impact_score)
            
        # Stop orders can have significant impact when triggered
        if order_type in ["stop", "stop_market"]:
            impact_score = 0.7 - (0.5 * size_to_liquidity_ratio)
            return max(0.3, impact_score)
            
        # Stop limit orders have moderate impact
        if order_type == "stop_limit":
            impact_score = 0.8 - (0.4 * size_to_liquidity_ratio)
            return max(0.4, impact_score)
            
        # Default for other order types
        return 0.5
    
    def _generate_parameters(self,
                          order_type: str,
                          request: OrderTypeOptimizationRequest,
                          capabilities: ExchangeCapabilities,
                          performance: ExchangePerformance,
                          optimization_params: ExchangeOptimizationParams,
                          market_condition: MarketCondition) -> OrderTypeParameters:
        """Generate optimal parameters for the selected order type."""
        urgency = request.preferences.urgency
        
        # Initialize with defaults
        parameters = OrderTypeParameters(order_type=order_type)
        
        # Set time in force based on order type and preferences
        parameters.time_in_force = self._select_time_in_force(
            order_type, 
            request, 
            capabilities, 
            urgency
        )
        
        # For limit orders, calculate optimal price
        if order_type == "limit":
            parameters.post_only = request.preferences.maximize_maker_orders
            parameters.price_offset_bps = self._calculate_limit_price_offset(
                request, 
                market_condition, 
                urgency,
                parameters.post_only
            )
            
        # For stop orders, calculate trigger price
        if order_type in ["stop", "stop_market", "stop_limit"]:
            parameters.trigger_price_offset_bps = self._calculate_stop_price_offset(
                request, 
                market_condition, 
                urgency
            )
            
            # For stop limit, also need limit price offset from trigger
            if order_type == "stop_limit":
                parameters.price_offset_bps = self._calculate_stop_limit_price_offset(
                    request, 
                    market_condition, 
                    urgency
                )
                
        # Set retry parameters
        parameters.retry_attempts = optimization_params.max_retry_attempts
        parameters.retry_delay_ms = optimization_params.retry_delay_ms
        
        # Set reduce only if requested
        parameters.reduce_only = request.custom_constraints.get('reduce_only', False)
        
        # Set iceberg order size if appropriate
        if (hasattr(capabilities, 'supports_iceberg') and 
            capabilities.supports_iceberg and 
            request.size_usd > 50000):  # Only for larger orders
            
            iceberg_threshold_usd = market_condition.liquidity_depth_usd * 0.1
            if request.size_usd > iceberg_threshold_usd:
                # Set iceberg size to 5-10% of liquidity depth
                visible_pct = max(0.05, min(0.3, iceberg_threshold_usd / request.size_usd))
                parameters.iceberg_size = request.size * visible_pct
                
        return parameters
    
    def _select_time_in_force(self,
                           order_type: str,
                           request: OrderTypeOptimizationRequest,
                           capabilities: ExchangeCapabilities,
                           urgency: float) -> str:
        """Select appropriate time in force parameter."""
        # For market orders, default is IOC
        if order_type == "market":
            return "immediate_or_cancel" if capabilities.supports_immediate_or_cancel else "good_till_cancel"
            
        # For limit orders, depend on urgency
        if order_type == "limit":
            if urgency > 0.8 and capabilities.supports_fill_or_kill:
                return "fill_or_kill"
            elif urgency > 0.5 and capabilities.supports_immediate_or_cancel:
                return "immediate_or_cancel"
            else:
                return "good_till_cancel"
                
        # For stop orders, usually GTC
        if order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            return "good_till_cancel"
            
        # Default for other order types
        return "good_till_cancel"
    
    def _calculate_limit_price_offset(self,
                                  request: OrderTypeOptimizationRequest,
                                  market_condition: MarketCondition,
                                  urgency: float,
                                  post_only: bool) -> float:
        """Calculate optimal limit price offset in basis points."""
        # Base offset depends on side and post_only flag
        if request.side == "buy":
            # For buys, negative offset means below mid price (less aggressive)
            if post_only:
                # Post-only buy should be below best ask
                base_offset = -market_condition.spread_bps / 2
            else:
                # Regular buy can cross the spread
                base_offset = 0.0
        else:  # sell
            # For sells, positive offset means above mid price (less aggressive)
            if post_only:
                # Post-only sell should be above best bid
                base_offset = market_condition.spread_bps / 2
            else:
                # Regular sell can cross the spread
                base_offset = 0.0
                
        # Adjust based on urgency - higher urgency means more aggressive pricing
        urgency_adjustment = market_condition.spread_bps * (urgency - 0.5)
        
        # Adjust based on volatility - in volatile markets, need to be more aggressive
        volatility_adjustment = 0.0
        if market_condition.is_high_volatility:
            volatility_adjustment = market_condition.spread_bps * 0.1
            
        # Calculate final offset
        final_offset = base_offset + urgency_adjustment + volatility_adjustment
        
        # For post-only orders, ensure we don't cross the spread
        if post_only:
            if request.side == "buy" and final_offset > -0.1:
                final_offset = -0.1  # Ensure buy price is below best ask
            elif request.side == "sell" and final_offset < 0.1:
                final_offset = 0.1  # Ensure sell price is above best bid
                
        return final_offset
    
    def _calculate_stop_price_offset(self,
                                  request: OrderTypeOptimizationRequest,
                                  market_condition: MarketCondition,
                                  urgency: float) -> float:
        """Calculate optimal stop trigger price offset in basis points."""
        # For stop orders, the offset direction depends on the side
        if request.side == "buy":
            # Buy-stop is placed above current price
            base_offset = market_condition.spread_bps
        else:  # sell
            # Sell-stop is placed below current price
            base_offset = -market_condition.spread_bps
            
        # Adjust based on volatility - in volatile markets, need wider stops
        volatility_adjustment = 0.0
        if market_condition.is_high_volatility:
            # More breathing room in volatile markets
            volatility_adjustment = market_condition.volatility * 10000  # Convert to bps
            if request.side == "sell":
                volatility_adjustment = -volatility_adjustment  # Negative for sells
                
        # Calculate final offset
        final_offset = base_offset + volatility_adjustment
        
        return final_offset
    
    def _calculate_stop_limit_price_offset(self,
                                       request: OrderTypeOptimizationRequest,
                                       market_condition: MarketCondition,
                                       urgency: float) -> float:
        """Calculate optimal limit price offset from stop trigger in basis points."""
        # For stop-limit orders, we need additional offset for the limit price
        if request.side == "buy":
            # For buy-stop-limit, limit price is usually at or above trigger
            base_offset = market_condition.spread_bps * 0.5
        else:  # sell
            # For sell-stop-limit, limit price is usually at or below trigger
            base_offset = -market_condition.spread_bps * 0.5
            
        # Adjust based on urgency - higher urgency means smaller offset (tighter to trigger)
        urgency_adjustment = base_offset * (1.0 - urgency)
        
        # Calculate final offset
        final_offset = base_offset + urgency_adjustment
        
        return final_offset
    
    def _create_recommendation(self,
                            order_type: str,
                            parameters: OrderTypeParameters,
                            request: OrderTypeOptimizationRequest,
                            capabilities: ExchangeCapabilities,
                            performance: ExchangePerformance,
                            market_condition: MarketCondition,
                            score: float) -> OrderTypeRecommendation:
        """Create recommendation with expected metrics."""
        # Calculate expected metrics for the chosen order type and parameters
        fill_probability = self._estimate_fill_probability(
            order_type, 
            parameters, 
            request, 
            market_condition
        )
        
        cost_bps = self._estimate_cost(
            order_type, 
            parameters, 
            request, 
            capabilities, 
            performance
        )
        
        market_impact_bps = self._estimate_market_impact(
            order_type, 
            parameters, 
            request, 
            market_condition
        )
        
        time_to_fill_ms = self._estimate_time_to_fill(
            order_type, 
            parameters, 
            request, 
            performance, 
            market_condition
        )
        
        # Implementation shortfall includes cost and market impact
        implementation_shortfall_bps = cost_bps + market_impact_bps
        
        # Calculate confidence based on score and data quality
        confidence = min(0.95, score * 0.8)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            order_type, 
            parameters, 
            request, 
            market_condition, 
            fill_probability, 
            cost_bps, 
            market_impact_bps, 
            time_to_fill_ms
        )
        
        # Create recommendation
        return OrderTypeRecommendation(
            order_type=order_type,
            parameters=parameters,
            expected_fill_probability=fill_probability,
            expected_cost_bps=cost_bps,
            expected_market_impact_bps=market_impact_bps,
            expected_time_to_fill_ms=time_to_fill_ms,
            expected_implementation_shortfall_bps=implementation_shortfall_bps,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def _estimate_fill_probability(self,
                                order_type: str,
                                parameters: OrderTypeParameters,
                                request: OrderTypeOptimizationRequest,
                                market_condition: MarketCondition) -> float:
        """Estimate the probability of fill for given order type and parameters."""
        # Market orders almost always fill
        if order_type == "market":
            return 0.999
        
        # For limit orders, depends on aggressiveness
        if order_type == "limit":
            # Base probability
            base_prob = 0.85
            
            # Adjust for post-only flag
            if parameters.post_only:
                base_prob *= 0.85
                
            # Adjust for price offset
            offset = parameters.price_offset_bps
            spread = market_condition.spread_bps
            
            # For buys, negative offset means less aggressive
            if request.side == "buy":
                if offset >= 0:  # Crossing spread
                    offset_factor = 1.1
                else:
                    # Normalize to spread
                    norm_offset = abs(offset) / max(0.1, spread)
                    offset_factor = max(0.5, 1.0 - norm_offset * 0.5)
            else:  # sell
                if offset <= 0:  # Crossing spread
                    offset_factor = 1.1
                else:
                    # Normalize to spread
                    norm_offset = abs(offset) / max(0.1, spread)
                    offset_factor = max(0.5, 1.0 - norm_offset * 0.5)
                    
            base_prob *= offset_factor
            
            # Adjust for time in force
            if parameters.time_in_force == "fill_or_kill":
                base_prob *= 0.9  # Harder to fill all or nothing
            elif parameters.time_in_force == "immediate_or_cancel":
                base_prob *= 0.95  # Needs to fill immediately
                
            # Clamp result
            return max(0.1, min(0.999, base_prob))
            
        # For stop orders, probability depends on market conditions
        if order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            # Hard to estimate without knowing current price and trigger price
            # This is a placeholder - real implementation would be more sophisticated
            return 0.7
            
        # Default for unknown order types
        return 0.5
    
    def _estimate_cost(self,
                    order_type: str,
                    parameters: OrderTypeParameters,
                    request: OrderTypeOptimizationRequest,
                    capabilities: ExchangeCapabilities,
                    performance: ExchangePerformance) -> float:
        """Estimate the cost in basis points for given order type and parameters."""
        # Base cost from fees
        if order_type == "market" or parameters.time_in_force in ["immediate_or_cancel", "fill_or_kill"]:
            base_fee_bps = capabilities.taker_fee * 10000  # Convert to bps
        else:
            # For maker orders
            base_fee_bps = capabilities.maker_fee * 10000  # Convert to bps
            
        # For market orders, add expected slippage
        if order_type == "market":
            # Scale slippage with size relative to typical size
            size_factor = min(5.0, max(0.5, request.size_usd / 10000))  # Normalize around $10K
            expected_slippage = performance.market_order_slippage_bps * size_factor
            return base_fee_bps + expected_slippage
            
        # For limit orders, estimate based on parameters
        if order_type == "limit":
            if parameters.post_only:
                # Post-only ensures maker fee
                return base_fee_bps
            else:
                # Might get maker or taker fee
                # Estimate based on price aggressiveness
                offset = parameters.price_offset_bps
                
                if (request.side == "buy" and offset >= 0) or (request.side == "sell" and offset <= 0):
                    # Likely to be taker (crossing spread)
                    taker_fee_bps = capabilities.taker_fee * 10000
                    return taker_fee_bps
                else:
                    # Likely to be maker
                    return base_fee_bps
                    
        # For stop orders, assume taker fee
        if order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            taker_fee_bps = capabilities.taker_fee * 10000
            
            # For stop-limit, might sometimes get maker fee
            if order_type == "stop_limit":
                # Weight between maker and taker based on parameter aggressiveness
                maker_fee_bps = capabilities.maker_fee * 10000
                weighted_fee = taker_fee_bps * 0.7 + maker_fee_bps * 0.3
                return weighted_fee
                
            return taker_fee_bps
            
        # Default
        return base_fee_bps
    
    def _estimate_market_impact(self,
                             order_type: str,
                             parameters: OrderTypeParameters,
                             request: OrderTypeOptimizationRequest,
                             market_condition: MarketCondition) -> float:
        """Estimate market impact in basis points for given order type and parameters."""
        # Calculate size relative to liquidity
        size_to_liquidity_ratio = min(1.0, request.size_usd / max(1.0, market_condition.liquidity_depth_usd))
        
        # Base impact factor
        base_impact_factor = 10.0  # 10 bps for 100% of liquidity
        
        # For market orders, full impact is immediate
        if order_type == "market":
            impact = base_impact_factor * size_to_liquidity_ratio
            
            # Adjust for market conditions
            if market_condition.is_high_volatility:
                impact *= 1.5
                
            return impact
            
        # For limit orders, impact depends on how aggressive they are
        if order_type == "limit":
            if parameters.post_only:
                # Post-only orders have minimal impact
                impact = base_impact_factor * size_to_liquidity_ratio * 0.2
            else:
                # Regular limit orders - impact depends on offset
                offset = parameters.price_offset_bps
                
                if (request.side == "buy" and offset >= 0) or (request.side == "sell" and offset <= 0):
                    # Crossing spread - similar to market order
                    impact = base_impact_factor * size_to_liquidity_ratio * 0.8
                else:
                    # Passive order - minimal impact
                    impact = base_impact_factor * size_to_liquidity_ratio * 0.3
                    
            return impact
            
        # For stop orders, impact occurs when triggered
        if order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            # Similar to market orders when triggered
            impact = base_impact_factor * size_to_liquidity_ratio * 0.9
            
            # Stop-limit might have less impact if limit price is passive
            if order_type == "stop_limit":
                impact *= 0.8
                
            return impact
            
        # Default
        return base_impact_factor * size_to_liquidity_ratio * 0.5
    
    def _estimate_time_to_fill(self,
                            order_type: str,
                            parameters: OrderTypeParameters,
                            request: OrderTypeOptimizationRequest,
                            performance: ExchangePerformance,
                            market_condition: MarketCondition) -> float:
        """Estimate time to fill in milliseconds for given order type and parameters."""
        # Market orders execute quickly - just API latency
        if order_type == "market":
            return performance.avg_api_latency_ms * 1.2  # Add 20% buffer
            
        # For limit orders, depends on aggressiveness
        if order_type == "limit":
            # Base time from exchange average
            base_time = performance.avg_fill_time_ms
            
            # Adjust for parameters
            if parameters.post_only:
                # Post-only can take longer
                base_time *= 2.0
                
            # Adjust for offset
            offset = parameters.price_offset_bps
            
            if (request.side == "buy" and offset >= 0) or (request.side == "sell" and offset <= 0):
                # Crossing spread - quick fill like market order
                return performance.avg_api_latency_ms * 1.5
            else:
                # Passive order - scales with how far from market
                spread = market_condition.spread_bps
                norm_offset = abs(offset) / max(0.1, spread)
                
                # More passive = exponentially longer wait
                time_factor = 1.0 + (norm_offset * norm_offset * 10.0)
                
                return base_time * time_factor
                
        # For stop orders, need to wait for trigger, then execution time
        if order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            # Hard to estimate without knowing current price and trigger price
            # This is a placeholder - real implementation would be more sophisticated
            return 60000  # 1 minute as a default guess
            
        # Default
        return 10000  # 10 seconds default
    
    def _generate_reasoning(self,
                         order_type: str,
                         parameters: OrderTypeParameters,
                         request: OrderTypeOptimizationRequest,
                         market_condition: MarketCondition,
                         fill_probability: float,
                         cost_bps: float,
                         market_impact_bps: float,
                         time_to_fill_ms: float) -> str:
        """Generate human-readable reasoning for the recommendation."""
        urgency = request.preferences.urgency
        
        # Start with order type explanation
        if order_type == "market":
            reasoning = f"Recommended a market order because "
            
            if urgency > 0.7:
                reasoning += "execution urgency is high. "
            elif market_condition.is_high_volatility:
                reasoning += "market is volatile and immediate execution is preferred. "
            else:
                reasoning += "it provides guaranteed execution with acceptable costs. "
                
        elif order_type == "limit":
            reasoning = f"Recommended a limit order "
            
            if parameters.post_only:
                reasoning += "with post-only flag because fee optimization is important "
                
                if request.preferences.maximize_maker_orders:
                    reasoning += "and maker-only execution was requested. "
                else:
                    reasoning += "in the current market conditions. "
            else:
                if urgency > 0.5:
                    reasoning += "that crosses the spread for quick execution with better price control. "
                else:
                    reasoning += "with passive pricing to minimize costs while maintaining reasonable fill probability. "
                    
        elif order_type in ["stop", "stop_market", "stop_limit", "trailing_stop"]:
            reasoning = f"Recommended a {order_type} order because conditional execution is needed. "
        
        # Add market condition context
        reasoning += "Current market conditions: "
        
        if market_condition.is_high_volatility:
            reasoning += "high volatility, "
        else:
            reasoning += "normal volatility, "
            
        if market_condition.is_tight_spread:
            reasoning += "tight spread, "
        else:
            reasoning += "wide spread, "
            
        if market_condition.is_deep_liquidity:
            reasoning += "deep liquidity. "
        else:
            reasoning += "limited liquidity. "
            
        # Add expected performance
        reasoning += f"Expected performance: {fill_probability:.0%} fill probability, "
        reasoning += f"{cost_bps:.1f} bps cost, "
        reasoning += f"{market_impact_bps:.1f} bps market impact, "
        
        if time_to_fill_ms < 1000:
            reasoning += f"estimated fill time of {time_to_fill_ms:.0f}ms."
        elif time_to_fill_ms < 60000:
            reasoning += f"estimated fill time of {time_to_fill_ms/1000:.1f}s."
        else:
            reasoning += f"estimated fill time of {time_to_fill_ms/60000:.1f}m."
            
        return reasoning
    
    def _add_to_history(self, recommendation: OrderTypeRecommendation) -> None:
        """Add a recommendation to the history."""
        self.recommendation_history.append(recommendation)
        
        # Limit history size
        if len(self.recommendation_history) > self.max_history_size:
            self.recommendation_history.pop(0)
    
    def get_recommendation_history(self, 
                               exchange_id: Optional[str] = None, 
                               symbol: Optional[str] = None,
                               start_time: Optional[float] = None,
                               end_time: Optional[float] = None) -> List[OrderTypeRecommendation]:
        """Get history of recommendations with optional filtering."""
        # Not implemented yet - would need to add timestamp and metadata to recommendations
        return []
    
    def update_market_condition_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update the thresholds used for market condition classification."""
        for key, value in thresholds.items():
            if key in self.market_condition_thresholds:
                self.market_condition_thresholds[key] = value
    
    def optimize_for_cost(self) -> None:
        """Configure optimizer to prioritize cost efficiency."""
        # Adjust default parameters to prioritize cost over speed
        self.default_urgency = 0.3
        
    def optimize_for_speed(self) -> None:
        """Configure optimizer to prioritize execution speed."""
        # Adjust default parameters to prioritize speed over cost
        self.default_urgency = 0.8
        
    def optimize_for_reliability(self) -> None:
        """Configure optimizer to prioritize reliable execution."""
        # Adjust default parameters to prioritize reliability
        self.default_urgency = 0.5
        # Would adjust other parameters in a full implementation

def get_order_type_optimizer() -> OrderTypeOptimizer:
    """Get or create an OrderTypeOptimizer instance."""
    # This is a simple singleton implementation
    if not hasattr(get_order_type_optimizer, "instance"):
        get_order_type_optimizer.instance = OrderTypeOptimizer()
    
    return get_order_type_optimizer.instance 