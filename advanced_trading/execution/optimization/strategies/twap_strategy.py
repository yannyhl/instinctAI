"""
TWAP Execution Strategy

This module provides a Time-Weighted Average Price (TWAP) execution strategy that
splits an order into smaller chunks and executes them evenly over a specified time period.
This helps to minimize market impact and achieve a price close to the time-weighted average.
"""

import time
import logging
import uuid
import math
from typing import Dict, List, Optional, Any
from datetime import datetime

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

class TWAPStrategy(ExecutionStrategy):
    """
    Time-Weighted Average Price (TWAP) execution strategy.
    
    This strategy splits an order into equal-sized chunks and executes them
    at regular intervals over a specified time period. This helps to achieve
    a price close to the time-weighted average price of the asset during the period.
    
    This strategy is suitable for:
    - Medium to large orders that might have market impact
    - Situations where execution urgency is moderate
    - Markets with consistent liquidity
    - When you want to achieve a price close to the market average
    
    The strategy uses the Smart Order Router to select the best exchange(s) for each chunk
    and the Order Type Optimizer to select the best order type and parameters.
    """
    
    def __init__(self,
                 min_chunks: int = 2,
                 max_chunks: int = 24,
                 min_chunk_interval_seconds: int = 60,
                 max_chunk_size_pct: float = 0.1,  # Max size as percentage of total
                 randomize_times: bool = False,
                 randomize_sizes: bool = False,
                 order_router=None,
                 order_optimizer=None,
                 registry=None,
                 profiler=None):
        """
        Initialize the TWAP execution strategy.
        
        Args:
            min_chunks: Minimum number of chunks to split an order into
            max_chunks: Maximum number of chunks to split an order into
            min_chunk_interval_seconds: Minimum time between chunks
            max_chunk_size_pct: Maximum size of a chunk as percentage of total order
            randomize_times: Whether to randomize execution times
            randomize_sizes: Whether to randomize chunk sizes
            order_router: SmartOrderRouter instance (or None to use singleton)
            order_optimizer: OrderTypeOptimizer instance (or None to use singleton)
            registry: ExchangeCapabilityRegistry instance (or None to use singleton)
            profiler: ExchangeProfiler instance (or None to use singleton)
        """
        super().__init__(
            name="TWAPStrategy",
            description="Time-Weighted Average Price execution strategy",
            order_router=order_router,
            order_optimizer=order_optimizer,
            registry=registry,
            profiler=profiler
        )
        
        self.min_chunks = min_chunks
        self.max_chunks = max_chunks
        self.min_chunk_interval_seconds = min_chunk_interval_seconds
        self.max_chunk_size_pct = max_chunk_size_pct
        self.randomize_times = randomize_times
        self.randomize_sizes = randomize_sizes
    
    def create_execution_schedule(self, request: ExecutionRequest) -> ExecutionSchedule:
        """
        Create a TWAP execution schedule for the given request.
        
        This will split the order into chunks and schedule them at regular
        intervals over the specified time period.
        
        Args:
            request: Execution request
            
        Returns:
            ExecutionSchedule detailing how the order will be executed
        """
        logger.info(f"Creating TWAP execution schedule for order {request.id}")
        
        # Create schedule
        schedule = ExecutionSchedule(
            order_id=request.id,
            total_size=request.size,
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        # Validate time period
        if not request.end_time or request.end_time <= request.start_time:
            logger.warning(f"Invalid time period for TWAP order {request.id}")
            request.end_time = request.start_time + 3600  # Default to 1 hour
        
        # Calculate time period
        time_period_seconds = request.end_time - request.start_time
        
        # Determine number of chunks
        num_chunks = self._calculate_num_chunks(request.size, time_period_seconds)
        
        # Calculate chunk interval
        interval_seconds = time_period_seconds / num_chunks
        
        # Split order into chunks
        chunks = self._split_into_chunks(request.size, num_chunks)
        
        # Create sub-orders
        sub_orders = []
        
        for i, chunk_size in enumerate(chunks):
            # Calculate execution time for this chunk
            chunk_time = request.start_time + (i * interval_seconds)
            
            # Create sub-order
            sub_order = SubOrder(
                id=f"{request.id}_{i}",
                parent_id=request.id,
                symbol=request.symbol,
                side=request.side,
                size=chunk_size,
                price=None,  # Will be determined at execution time
                order_type="market",  # Will be determined at execution time
                exchange_id=None,  # Will be determined at execution time
                time_in_force="good_till_cancel",  # Will be determined at execution time
                scheduled_time=chunk_time,
                custom_params={
                    "chunk_number": i + 1,
                    "total_chunks": num_chunks
                }
            )
            
            sub_orders.append(sub_order)
        
        # Add sub-orders to schedule
        schedule.sub_orders = sub_orders
        
        logger.info(f"Created TWAP execution schedule with {len(sub_orders)} chunks for order {request.id}")
        
        return schedule
    
    def get_next_actions(self, schedule: ExecutionSchedule) -> List[SubOrder]:
        """
        Get the next actions to take for a schedule.
        
        For TWAP, this means returning any sub-orders that are due for execution.
        
        Args:
            schedule: Execution schedule
            
        Returns:
            List of sub-orders to execute now
        """
        current_time = time.time()
        
        # Get pending sub-orders that are scheduled for execution now or in the past
        due_orders = [
            sub for sub in schedule.sub_orders
            if sub.status == "pending" and sub.scheduled_time and sub.scheduled_time <= current_time
        ]
        
        # If any orders are due, prepare them for execution
        for sub_order in due_orders:
            # Calculate urgency based on schedule progress
            urgency = self._calculate_urgency(schedule, sub_order)
            
            # Find optimal routing
            routing_decision = self._get_routing_decision(schedule, sub_order, urgency)
            
            # If there's a routing decision with at least one exchange
            if routing_decision and routing_decision.exchange_decisions:
                exchange_decision = routing_decision.exchange_decisions[0]
                
                # Get optimal order type
                order_type_rec = self._get_order_type_recommendation(
                    schedule, sub_order, exchange_decision.exchange_id, urgency
                )
                
                # Update sub-order with routing and order type information
                sub_order.exchange_id = exchange_decision.exchange_id
                sub_order.order_type = order_type_rec.order_type
                sub_order.price = order_type_rec.parameters.price_offset_bps if order_type_rec.order_type == "limit" else None
                sub_order.time_in_force = order_type_rec.parameters.time_in_force
                sub_order.post_only = order_type_rec.parameters.post_only
                sub_order.reduce_only = order_type_rec.parameters.reduce_only
                
                # Update custom params
                sub_order.custom_params.update({
                    "routing_score": exchange_decision.score,
                    "expected_fee": exchange_decision.expected_fee,
                    "expected_slippage": exchange_decision.expected_slippage,
                    "expected_fill_probability": order_type_rec.expected_fill_probability,
                    "expected_cost_bps": order_type_rec.expected_cost_bps,
                    "expected_market_impact_bps": order_type_rec.expected_market_impact_bps,
                    "expected_time_to_fill_ms": order_type_rec.expected_time_to_fill_ms
                })
                
                logger.info(f"Prepared sub-order {sub_order.id} for execution on {sub_order.exchange_id}")
            else:
                # If no routing decision, log an error and mark the sub-order as failed
                logger.error(f"Failed to find routing for sub-order {sub_order.id}")
                sub_order.status = "failed"
                sub_order.custom_params["failure_reason"] = "No routing decision"
        
        # Return due orders that are still pending
        return [sub for sub in due_orders if sub.status == "pending"]
    
    def _calculate_num_chunks(self, size: float, time_period_seconds: float) -> int:
        """
        Calculate the optimal number of chunks based on order size and time period.
        
        Args:
            size: Order size
            time_period_seconds: Execution time period in seconds
            
        Returns:
            Number of chunks
        """
        # Calculate max chunks based on minimum interval
        max_time_chunks = int(time_period_seconds / self.min_chunk_interval_seconds)
        
        # Calculate max chunks based on order size and max chunk size percentage
        max_size_chunks = int(1 / self.max_chunk_size_pct)
        
        # Calculate number of chunks considering constraints
        num_chunks = min(max_time_chunks, max_size_chunks, self.max_chunks)
        num_chunks = max(num_chunks, self.min_chunks)
        
        return num_chunks
    
    def _split_into_chunks(self, size: float, num_chunks: int) -> List[float]:
        """
        Split an order into chunks.
        
        Args:
            size: Order size
            num_chunks: Number of chunks
            
        Returns:
            List of chunk sizes
        """
        if self.randomize_sizes:
            # Randomize chunk sizes while ensuring they sum to the total size
            import random
            
            # Start with all equal chunks
            equal_size = size / num_chunks
            
            # Add random variance
            chunks = []
            remaining_size = size
            
            for i in range(num_chunks - 1):
                # Random variance up to 30% of equal chunk size
                variance = equal_size * 0.3 * (random.random() * 2 - 1)
                
                # Calculate chunk size
                chunk_size = equal_size + variance
                
                # Ensure chunk is positive and not too large
                chunk_size = max(equal_size * 0.5, min(equal_size * 1.5, chunk_size))
                
                # Add to chunks
                chunks.append(chunk_size)
                
                # Update remaining size
                remaining_size -= chunk_size
            
            # Add the last chunk with remaining size
            chunks.append(remaining_size)
            
            return chunks
        else:
            # Equal-sized chunks
            equal_size = size / num_chunks
            return [equal_size] * num_chunks
    
    def _calculate_urgency(self, schedule: ExecutionSchedule, sub_order: SubOrder) -> float:
        """
        Calculate urgency for a sub-order based on schedule progress.
        
        Args:
            schedule: Execution schedule
            sub_order: Sub-order
            
        Returns:
            Urgency value (0.0-1.0)
        """
        current_time = time.time()
        
        # If we're near the end of the schedule, increase urgency
        if schedule.end_time:
            time_remaining = max(0, schedule.end_time - current_time)
            total_time = schedule.end_time - schedule.start_time
            
            # Urgency increases as time remaining decreases
            if total_time > 0:
                urgency = 1.0 - (time_remaining / total_time)
                urgency = min(0.9, max(0.1, urgency))
                return urgency
        
        # Get chunk number from custom params
        chunk_number = sub_order.custom_params.get("chunk_number", 1)
        total_chunks = sub_order.custom_params.get("total_chunks", 1)
        
        # Increase urgency slightly for later chunks
        return 0.5 + (chunk_number / total_chunks) * 0.2
    
    def _get_routing_decision(self, 
                           schedule: ExecutionSchedule, 
                           sub_order: SubOrder,
                           urgency: float) -> Any:
        """
        Get routing decision for a sub-order.
        
        Args:
            schedule: Execution schedule
            sub_order: Sub-order
            urgency: Urgency value
            
        Returns:
            RoutingDecision
        """
        # Get the original request from active orders
        request = None
        for order_id, active_schedule in self.active_orders.items():
            if active_schedule.order_id == schedule.order_id:
                request = ExecutionRequest(
                    id=order_id,
                    symbol=sub_order.symbol,
                    side=sub_order.side,
                    size=sub_order.size,
                    size_usd=sub_order.size * 0  # Will be estimated later
                )
                break
        
        if not request:
            # Create a default request if no active order found
            request = ExecutionRequest(
                id=sub_order.parent_id,
                symbol=sub_order.symbol,
                side=sub_order.side,
                size=sub_order.size,
                size_usd=sub_order.size * 0  # Will be estimated later
            )
        
        # If we have a reference price from a sub-order, use it
        reference_price = None
        for so in schedule.sub_orders:
            if so.filled_price:
                reference_price = so.filled_price
                break
        
        # Use balanced routing for TWAP
        routing_priority = RoutingPriority.BALANCED
        
        # Create routing parameters
        routing_params = OrderRoutingParameters(
            symbol=sub_order.symbol,
            side=sub_order.side,
            size=sub_order.size,
            size_usd=sub_order.size * 0,  # Will be estimated by the router
            order_type="market" if not sub_order.price else "limit",
            price=sub_order.price,
            urgency=urgency,
            allow_split=False,  # Don't split individual chunks
            priority=routing_priority
        )
        
        # Get routing decision
        return self.order_router.route_order(routing_params)
    
    def _get_order_type_recommendation(self,
                                    schedule: ExecutionSchedule,
                                    sub_order: SubOrder,
                                    exchange_id: str,
                                    urgency: float) -> Any:
        """
        Get order type recommendation for a sub-order.
        
        Args:
            schedule: Execution schedule
            sub_order: Sub-order
            exchange_id: Exchange ID
            urgency: Urgency value
            
        Returns:
            OrderTypeRecommendation
        """
        # Create balanced execution preferences for TWAP
        preferences = ExecutionPreferences(
            urgency=urgency,
            cost_sensitivity=0.5,
            impact_sensitivity=0.6,  # Slightly higher impact sensitivity for TWAP
            completion_priority=0.7  # Higher completion priority for TWAP
        )
        
        # Create order type request
        order_type_request = OrderTypeOptimizationRequest(
            exchange_id=exchange_id,
            symbol=sub_order.symbol,
            side=sub_order.side,
            size=sub_order.size,
            size_usd=sub_order.size * 0,  # Will be estimated
            preferences=preferences
        )
        
        # Get order type recommendation
        return self.order_optimizer.recommend_order_type(order_type_request) 