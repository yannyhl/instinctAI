"""
Basic Execution Strategy

This module provides a simple execution strategy that executes an order immediately
rather than splitting it over time. It's suitable for small orders with minimal
market impact concerns.
"""

import time
import logging
import uuid
from typing import Dict, List, Optional, Any

from advanced_trading.execution.optimization.strategies.execution_strategy import (
    ExecutionStrategy, ExecutionRequest, ExecutionSchedule, SubOrder
)

from advanced_trading.execution.optimization.routers import (
    OrderRoutingParameters, RoutingPriority
)

from advanced_trading.execution.optimization.order_types import (
    ExecutionPreferences, OrderTypeOptimizationRequest
)

# Initialize logger
logger = logging.getLogger(__name__)

class BasicExecutionStrategy(ExecutionStrategy):
    """
    Basic execution strategy that executes an order immediately.
    
    This strategy is suitable for:
    - Small orders (relative to market liquidity)
    - Situations where immediate execution is preferred over price optimization
    - Markets with good liquidity and low volatility
    
    It uses the Smart Order Router to select the best exchange(s) and the
    Order Type Optimizer to select the best order type and parameters.
    """
    
    def __init__(self, 
                 max_split_exchanges: int = 2,
                 order_router=None,
                 order_optimizer=None,
                 registry=None,
                 profiler=None):
        """
        Initialize the basic execution strategy.
        
        Args:
            max_split_exchanges: Maximum number of exchanges to split an order across
            order_router: SmartOrderRouter instance (or None to use singleton)
            order_optimizer: OrderTypeOptimizer instance (or None to use singleton)
            registry: ExchangeCapabilityRegistry instance (or None to use singleton)
            profiler: ExchangeProfiler instance (or None to use singleton)
        """
        super().__init__(
            name="BasicExecutionStrategy",
            description="Simple immediate execution strategy for small orders",
            order_router=order_router,
            order_optimizer=order_optimizer,
            registry=registry,
            profiler=profiler
        )
        
        self.max_split_exchanges = max_split_exchanges
    
    def create_execution_schedule(self, request: ExecutionRequest) -> ExecutionSchedule:
        """
        Create an execution schedule for the given request.
        
        For BasicExecutionStrategy, this means creating a single action
        to execute the entire order at once.
        
        Args:
            request: Execution request
            
        Returns:
            ExecutionSchedule detailing how the order will be executed
        """
        logger.info(f"Creating execution schedule for order {request.id}")
        
        # Create schedule
        schedule = ExecutionSchedule(
            order_id=request.id,
            total_size=request.size,
            start_time=request.start_time
        )
        
        # Find optimal routing
        routing_decision = self._get_routing_decision(request)
        
        # Create sub-orders based on routing decision
        sub_orders = []
        
        for i, exchange_decision in enumerate(routing_decision.exchange_decisions):
            # Get optimal order type
            order_type_rec = self._get_order_type_recommendation(
                request, exchange_decision.exchange_id, exchange_decision.size
            )
            
            # Create sub-order
            sub_order = SubOrder(
                id=f"{request.id}_{i}",
                parent_id=request.id,
                symbol=request.symbol,
                side=request.side,
                size=exchange_decision.size,
                price=order_type_rec.parameters.price_offset_bps if order_type_rec.order_type == "limit" else None,
                order_type=order_type_rec.order_type,
                exchange_id=exchange_decision.exchange_id,
                time_in_force=order_type_rec.parameters.time_in_force,
                post_only=order_type_rec.parameters.post_only,
                reduce_only=order_type_rec.parameters.reduce_only,
                scheduled_time=request.start_time,
                custom_params={
                    "routing_score": exchange_decision.score,
                    "expected_fee": exchange_decision.expected_fee,
                    "expected_slippage": exchange_decision.expected_slippage,
                    "expected_fill_probability": order_type_rec.expected_fill_probability,
                    "expected_cost_bps": order_type_rec.expected_cost_bps,
                    "expected_market_impact_bps": order_type_rec.expected_market_impact_bps,
                    "expected_time_to_fill_ms": order_type_rec.expected_time_to_fill_ms
                }
            )
            
            sub_orders.append(sub_order)
        
        # Add sub-orders to schedule
        schedule.sub_orders = sub_orders
        
        logger.info(f"Created execution schedule with {len(sub_orders)} sub-orders for order {request.id}")
        
        return schedule
    
    def get_next_actions(self, schedule: ExecutionSchedule) -> List[SubOrder]:
        """
        Get the next actions to take for a schedule.
        
        For BasicExecutionStrategy, all sub-orders are executed immediately.
        
        Args:
            schedule: Execution schedule
            
        Returns:
            List of sub-orders to execute now
        """
        # For basic strategy, return all pending sub-orders
        return [sub for sub in schedule.sub_orders if sub.status == "pending"]
    
    def _get_routing_decision(self, request: ExecutionRequest) -> Any:
        """
        Get routing decision for the request.
        
        Args:
            request: Execution request
            
        Returns:
            RoutingDecision
        """
        # Determine routing priority
        if request.priority == request.priority.MINIMIZE_COST:
            routing_priority = RoutingPriority.LOWEST_FEES
        elif request.priority == request.priority.MINIMIZE_MARKET_IMPACT:
            routing_priority = RoutingPriority.BEST_LIQUIDITY
        elif request.priority == request.priority.MINIMIZE_TIME:
            routing_priority = RoutingPriority.FASTEST_EXECUTION
        elif request.priority == request.priority.MAXIMIZE_CERTAINTY:
            routing_priority = RoutingPriority.HIGHEST_RELIABILITY
        else:
            routing_priority = RoutingPriority.BALANCED
        
        # Create routing parameters
        routing_params = OrderRoutingParameters(
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            size_usd=request.size_usd,
            order_type="market" if not request.limit_price else "limit",
            price=request.limit_price,
            urgency=self._convert_priority_to_urgency(request.priority),
            allow_split=True,
            exclude_exchanges=request.excluded_exchanges,
            only_exchanges=request.preferred_exchanges if request.preferred_exchanges else None,
            priority=routing_priority
        )
        
        # Get routing decision
        return self.order_router.route_order(routing_params)
    
    def _get_order_type_recommendation(self, 
                                      request: ExecutionRequest, 
                                      exchange_id: str,
                                      size: float) -> Any:
        """
        Get order type recommendation for the request.
        
        Args:
            request: Execution request
            exchange_id: Exchange ID
            size: Order size
            
        Returns:
            OrderTypeRecommendation
        """
        # Calculate urgency
        urgency = self._convert_priority_to_urgency(request.priority)
        
        # Create execution preferences
        preferences = ExecutionPreferences(
            urgency=urgency,
            cost_sensitivity=0.5 if request.priority != request.priority.MINIMIZE_COST else 0.9,
            impact_sensitivity=0.5 if request.priority != request.priority.MINIMIZE_MARKET_IMPACT else 0.9,
            completion_priority=0.5 if request.priority != request.priority.MAXIMIZE_CERTAINTY else 0.9,
            minimize_time=request.priority == request.priority.MINIMIZE_TIME,
            maximize_maker_orders=request.priority == request.priority.MINIMIZE_COST
        )
        
        # Calculate size in USD
        size_usd = size * request.size_usd / request.size if request.size > 0 else size * 0
        
        # Create order type request
        order_type_request = OrderTypeOptimizationRequest(
            exchange_id=exchange_id,
            symbol=request.symbol,
            side=request.side,
            size=size,
            size_usd=size_usd,
            reference_price=request.reference_price,
            preferences=preferences
        )
        
        # Get order type recommendation
        return self.order_optimizer.recommend_order_type(order_type_request)
    
    def _convert_priority_to_urgency(self, priority: Any) -> float:
        """
        Convert execution priority to urgency value.
        
        Args:
            priority: ExecutionPriority
            
        Returns:
            Urgency value (0.0-1.0)
        """
        if priority == priority.MINIMIZE_TIME:
            return 0.9  # High urgency for fast execution
        elif priority == priority.MAXIMIZE_CERTAINTY:
            return 0.7  # Medium-high urgency for certainty
        elif priority == priority.MINIMIZE_COST:
            return 0.3  # Low urgency to get better prices
        elif priority == priority.MINIMIZE_MARKET_IMPACT:
            return 0.2  # Very low urgency to minimize impact
        elif priority == priority.STEALTH:
            return 0.4  # Low-medium urgency for stealth
        else:  # BALANCED or CUSTOM
            return 0.5  # Medium urgency for balanced approach 