"""
Adaptive Execution Strategy

This module provides an adaptive execution strategy that dynamically adjusts execution
parameters based on real-time market conditions. It combines elements of TWAP and VWAP
but can adapt to changing volatility, spread, and liquidity conditions.
"""

import time
import logging
import uuid
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum

from advanced_trading.execution.optimization.strategies.execution_strategy import (
    ExecutionStrategy, ExecutionRequest, ExecutionSchedule, SubOrder, ExecutionPriority
)

from advanced_trading.execution.optimization.routers import (
    OrderRoutingParameters, RoutingPriority
)

from advanced_trading.execution.optimization.order_types import (
    ExecutionPreferences, OrderTypeOptimizationRequest
)

# Initialize logger
logger = logging.getLogger(__name__)

class MarketCondition(Enum):
    """
    Enum representing market conditions.
    """
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    LOW_LIQUIDITY = "low_liquidity"
    FAVORABLE = "favorable"
    UNFAVORABLE = "unfavorable"


class AdaptiveStrategy(ExecutionStrategy):
    """
    Adaptive execution strategy that dynamically adjusts to market conditions.
    
    This strategy combines elements of TWAP and VWAP but includes real-time
    adaptations based on market conditions. It can:
    - Accelerate or slow down execution based on volatility
    - Adjust order types based on spread conditions
    - Modify routing priorities based on observed fills
    - Dynamically alter chunk sizes based on price movements
    
    This strategy is suitable for:
    - Medium to large orders in volatile markets
    - When performance relative to a benchmark is critical
    - When market conditions are expected to change during execution
    - When optimizing for opportunity cost as well as execution cost
    
    The strategy requires access to market data to make real-time decisions.
    """
    
    def __init__(self,
                 initial_chunks: int = 12,
                 min_chunk_interval_seconds: int = 60,
                 max_chunk_size_pct: float = 0.15,  # Max size as percentage of total
                 volatility_sensitivity: float = 0.5,  # 0.0 to 1.0
                 price_sensitivity: float = 0.5,  # 0.0 to 1.0
                 liquidity_sensitivity: float = 0.5,  # 0.0 to 1.0
                 opportunistic: bool = True,  # Whether to be opportunistic on favorable moves
                 defensive: bool = True,  # Whether to be defensive on unfavorable moves
                 market_data_provider=None,  # Market data provider for real-time adaptation
                 order_router=None,
                 order_optimizer=None,
                 registry=None,
                 profiler=None):
        """
        Initialize the adaptive execution strategy.
        
        Args:
            initial_chunks: Initial number of chunks to split an order into
            min_chunk_interval_seconds: Minimum time between chunks
            max_chunk_size_pct: Maximum size of a chunk as percentage of total order
            volatility_sensitivity: How sensitive to volatility (0.0 to 1.0)
            price_sensitivity: How sensitive to price moves (0.0 to 1.0)
            liquidity_sensitivity: How sensitive to liquidity changes (0.0 to 1.0)
            opportunistic: Whether to accelerate on favorable price moves
            defensive: Whether to slow down on unfavorable price moves
            market_data_provider: Object providing real-time market data
            order_router: SmartOrderRouter instance (or None to use singleton)
            order_optimizer: OrderTypeOptimizer instance (or None to use singleton)
            registry: ExchangeCapabilityRegistry instance (or None to use singleton)
            profiler: ExchangeProfiler instance (or None to use singleton)
        """
        super().__init__(
            name="AdaptiveStrategy",
            description="Adaptive execution strategy that adjusts to market conditions",
            order_router=order_router,
            order_optimizer=order_optimizer,
            registry=registry,
            profiler=profiler
        )
        
        self.initial_chunks = initial_chunks
        self.min_chunk_interval_seconds = min_chunk_interval_seconds
        self.max_chunk_size_pct = max_chunk_size_pct
        
        # Strategy sensitivities
        self.volatility_sensitivity = max(0.0, min(1.0, volatility_sensitivity))
        self.price_sensitivity = max(0.0, min(1.0, price_sensitivity))
        self.liquidity_sensitivity = max(0.0, min(1.0, liquidity_sensitivity))
        
        # Strategy behaviors
        self.opportunistic = opportunistic
        self.defensive = defensive
        
        # Market data provider for real-time data
        self.market_data_provider = market_data_provider
        
        # Track market conditions per order
        self.market_conditions = {}  # order_id -> MarketCondition
        
        # Track initial prices for relative price movement calculations
        self.initial_prices = {}  # order_id -> price
        
        # Track performance metrics
        self.performance_metrics = {}  # order_id -> metrics dict
    
    def create_execution_schedule(self, request: ExecutionRequest) -> ExecutionSchedule:
        """
        Create an adaptive execution schedule for the given request.
        
        This creates an initial schedule, but the distinctive feature of the
        adaptive strategy is that the schedule will be dynamically adjusted
        as execution progresses.
        
        Args:
            request: Execution request
            
        Returns:
            ExecutionSchedule detailing how the order will be executed initially
        """
        logger.info(f"Creating adaptive execution schedule for order {request.id}")
        
        # Create schedule
        schedule = ExecutionSchedule(
            order_id=request.id,
            total_size=request.size,
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        # Validate time period
        if not request.end_time or request.end_time <= request.start_time:
            logger.warning(f"Invalid time period for adaptive order {request.id}")
            # Default to 2 hours for adaptive strategy
            request.end_time = request.start_time + 7200
        
        # Calculate time period
        time_period_seconds = request.end_time - request.start_time
        
        # Initial number of chunks
        num_chunks = self.initial_chunks
        
        # Calculate chunk interval
        interval_seconds = time_period_seconds / num_chunks
        
        # Ensure chunks aren't too frequent
        if interval_seconds < self.min_chunk_interval_seconds:
            interval_seconds = self.min_chunk_interval_seconds
            num_chunks = int(time_period_seconds / interval_seconds)
        
        # Calculate initial chunk size (equal sized for now)
        chunk_size = request.size / num_chunks
        
        # Create sub-orders for initial schedule
        sub_orders = []
        
        for i in range(num_chunks):
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
                    "total_chunks": num_chunks,
                    "original_time": chunk_time,  # Store original time for reference
                    "adaptation_count": 0,  # Track how many times we've adapted this order
                    "current_condition": MarketCondition.NORMAL.value  # Start with normal condition
                }
            )
            
            sub_orders.append(sub_order)
        
        # Add sub-orders to schedule
        schedule.sub_orders = sub_orders
        
        # Initialize market condition for this order
        self.market_conditions[request.id] = MarketCondition.NORMAL
        
        # Try to get initial price from market data provider
        try:
            if self.market_data_provider:
                price = self.market_data_provider.get_current_price(request.symbol)
                if price:
                    self.initial_prices[request.id] = price
        except Exception as e:
            logger.warning(f"Failed to get initial price for {request.symbol}: {e}")
        
        # Initialize performance metrics
        self.performance_metrics[request.id] = {
            "initial_midpoint": self.initial_prices.get(request.id),
            "filled_count": 0,
            "total_fill_price": 0.0,
            "best_fill_price": None,
            "worst_fill_price": None,
            "avg_fill_price": None,
            "last_adaptation_time": None,
            "adaptation_count": 0
        }
        
        logger.info(f"Created adaptive execution schedule with {len(sub_orders)} chunks for order {request.id}")
        
        return schedule
    
    def get_next_actions(self, schedule: ExecutionSchedule) -> List[SubOrder]:
        """
        Get the next actions to take for a schedule.
        
        For adaptive strategy, this includes:
        1. Checking for any due orders
        2. Analyzing market conditions and adapting the schedule if needed
        3. Preparing due orders for execution
        
        Args:
            schedule: Execution schedule
            
        Returns:
            List of sub-orders to execute now
        """
        current_time = time.time()
        order_id = schedule.order_id
        
        # First, assess market conditions and potentially adapt the schedule
        self._adapt_schedule(schedule, current_time)
        
        # Get pending sub-orders that are scheduled for execution now or in the past
        due_orders = [
            sub for sub in schedule.sub_orders
            if sub.status == "pending" and sub.scheduled_time and sub.scheduled_time <= current_time
        ]
        
        # If any orders are due, prepare them for execution
        for sub_order in due_orders:
            # Get current market condition
            market_condition = self.market_conditions.get(order_id, MarketCondition.NORMAL)
            
            # Calculate urgency based on market condition and schedule progress
            urgency = self._calculate_urgency(schedule, sub_order, market_condition)
            
            # Find optimal routing based on market condition
            routing_decision = self._get_routing_decision(schedule, sub_order, urgency, market_condition)
            
            # If there's a routing decision with at least one exchange
            if routing_decision and routing_decision.exchange_decisions:
                exchange_decision = routing_decision.exchange_decisions[0]
                
                # Get optimal order type based on market condition
                order_type_rec = self._get_order_type_recommendation(
                    schedule, sub_order, exchange_decision.exchange_id, urgency, market_condition
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
                    "expected_time_to_fill_ms": order_type_rec.expected_time_to_fill_ms,
                    "market_condition": market_condition.value
                })
                
                logger.info(f"Prepared adaptive sub-order {sub_order.id} for execution on {sub_order.exchange_id}")
            else:
                # If no routing decision, log an error and mark the sub-order as failed
                logger.error(f"Failed to find routing for sub-order {sub_order.id}")
                sub_order.status = "failed"
                sub_order.custom_params["failure_reason"] = "No routing decision"
        
        # Return due orders that are still pending
        return [sub for sub in due_orders if sub.status == "pending"]
    
    def update_order_status(self, sub_order_id: str, status: str, filled_price: Optional[float] = None) -> None:
        """
        Update the status of a sub-order and track metrics.
        
        Args:
            sub_order_id: ID of the sub-order
            status: New status
            filled_price: Price at which the order was filled (if applicable)
        """
        # Call parent implementation first
        super().update_order_status(sub_order_id, status, filled_price)
        
        # If order was filled, update performance metrics
        if status == "filled" and filled_price is not None:
            # Find parent order ID
            parent_id = None
            sub_order = None
            
            for order_id, schedule in self.active_orders.items():
                for sub in schedule.sub_orders:
                    if sub.id == sub_order_id:
                        parent_id = order_id
                        sub_order = sub
                        break
                if parent_id:
                    break
            
            if parent_id and sub_order and parent_id in self.performance_metrics:
                metrics = self.performance_metrics[parent_id]
                
                # Update metrics
                metrics["filled_count"] += 1
                metrics["total_fill_price"] += filled_price * sub_order.size
                
                # Update best/worst prices
                if metrics["best_fill_price"] is None or filled_price > metrics["best_fill_price"]:
                    metrics["best_fill_price"] = filled_price
                
                if metrics["worst_fill_price"] is None or filled_price < metrics["worst_fill_price"]:
                    metrics["worst_fill_price"] = filled_price
                
                # Update average fill price
                total_filled_size = 0
                for sub in self.active_orders[parent_id].sub_orders:
                    if sub.status == "filled" and sub.filled_price:
                        total_filled_size += sub.size
                
                if total_filled_size > 0:
                    metrics["avg_fill_price"] = metrics["total_fill_price"] / total_filled_size
    
    def _adapt_schedule(self, schedule: ExecutionSchedule, current_time: float) -> None:
        """
        Adapt the execution schedule based on current market conditions.
        
        Args:
            schedule: Execution schedule to adapt
            current_time: Current time
        """
        order_id = schedule.order_id
        
        # Skip if we recently adapted (avoid too frequent adaptations)
        last_adaptation = self.performance_metrics.get(order_id, {}).get("last_adaptation_time")
        if last_adaptation and current_time - last_adaptation < 60:  # Minimum 60 seconds between adaptations
            return
        
        # Assess current market conditions
        market_condition = self._assess_market_condition(schedule)
        
        # Update tracked condition
        self.market_conditions[order_id] = market_condition
        
        # Get pending sub-orders
        pending_orders = [
            sub for sub in schedule.sub_orders 
            if sub.status == "pending"
        ]
        
        # Skip if no pending orders
        if not pending_orders:
            return
        
        # Early exit if market condition is normal
        if market_condition == MarketCondition.NORMAL:
            return
        
        # Adapt based on market condition
        if market_condition == MarketCondition.HIGH_VOLATILITY:
            self._adapt_to_high_volatility(schedule, pending_orders)
        elif market_condition == MarketCondition.LOW_LIQUIDITY:
            self._adapt_to_low_liquidity(schedule, pending_orders)
        elif market_condition == MarketCondition.FAVORABLE:
            self._adapt_to_favorable_conditions(schedule, pending_orders)
        elif market_condition == MarketCondition.UNFAVORABLE:
            self._adapt_to_unfavorable_conditions(schedule, pending_orders)
        
        # Update adaptation metrics
        self.performance_metrics[order_id]["last_adaptation_time"] = current_time
        self.performance_metrics[order_id]["adaptation_count"] += 1
        
        logger.info(f"Adapted schedule for order {order_id} based on {market_condition.value} market conditions")
    
    def _assess_market_condition(self, schedule: ExecutionSchedule) -> MarketCondition:
        """
        Assess current market conditions based on available data.
        
        Args:
            schedule: Execution schedule
            
        Returns:
            MarketCondition representing current conditions
        """
        # Default to normal if we can't assess
        if not self.market_data_provider:
            return MarketCondition.NORMAL
        
        order_id = schedule.order_id
        
        # Get a representative symbol from the schedule
        symbol = None
        for sub in schedule.sub_orders:
            if sub.symbol:
                symbol = sub.symbol
                break
        
        if not symbol:
            return MarketCondition.NORMAL
        
        try:
            # Get current volatility (normalized)
            volatility = self.market_data_provider.get_recent_volatility(symbol)
            
            # Get current spread
            spread = self.market_data_provider.get_current_spread(symbol)
            
            # Get current liquidity
            liquidity = self.market_data_provider.get_current_liquidity(symbol)
            
            # Get current price
            current_price = self.market_data_provider.get_current_price(symbol)
            
            # Get initial price
            initial_price = self.initial_prices.get(order_id)
            
            # If we're missing data, return normal
            if None in (volatility, spread, liquidity, current_price, initial_price):
                return MarketCondition.NORMAL
            
            # Calculate price movement (negative for downward move, positive for upward)
            price_move_pct = (current_price - initial_price) / initial_price
            
            # Analyze for an active buy order
            is_buy = False
            for sub in schedule.sub_orders:
                if sub.side == "buy":
                    is_buy = True
                    break
            
            # Determine if price movement is favorable (depends on side)
            favorable_price = (is_buy and price_move_pct < 0) or (not is_buy and price_move_pct > 0)
            unfavorable_price = (is_buy and price_move_pct > 0) or (not is_buy and price_move_pct < 0)
            
            # Check for high volatility
            if volatility > 0.7:  # Assuming normalized volatility metric (0-1)
                return MarketCondition.HIGH_VOLATILITY
            
            # Check for low liquidity
            if liquidity < 0.3:  # Assuming normalized liquidity metric (0-1)
                return MarketCondition.LOW_LIQUIDITY
            
            # Check for price opportunities
            if abs(price_move_pct) > 0.01:  # 1% move
                if favorable_price and self.opportunistic:
                    return MarketCondition.FAVORABLE
                elif unfavorable_price and self.defensive:
                    return MarketCondition.UNFAVORABLE
            
            return MarketCondition.NORMAL
            
        except Exception as e:
            logger.warning(f"Error assessing market condition: {e}")
            return MarketCondition.NORMAL
    
    def _adapt_to_high_volatility(self, schedule: ExecutionSchedule, pending_orders: List[SubOrder]) -> None:
        """
        Adapt to high volatility conditions by spreading out orders more.
        
        Args:
            schedule: Execution schedule
            pending_orders: List of pending sub-orders
        """
        # Sort by scheduled time
        pending_orders.sort(key=lambda x: x.scheduled_time)
        
        # Spread out the orders more (increase intervals)
        spread_factor = 1.0 + (0.5 * self.volatility_sensitivity)
        
        # Calculate new end time if needed
        if pending_orders:
            current_end = max(sub.scheduled_time for sub in pending_orders)
            new_end = schedule.start_time + (current_end - schedule.start_time) * spread_factor
            
            # Get the time range
            time_range = new_end - schedule.start_time
            
            # Reschedule pending orders
            for i, sub_order in enumerate(pending_orders):
                # Calculate position in sequence (0 to 1)
                position = i / (len(pending_orders) - 1) if len(pending_orders) > 1 else 0
                
                # Calculate new time
                new_time = schedule.start_time + (position * time_range)
                
                # Update the scheduled time
                sub_order.scheduled_time = new_time
                
                # Update custom params
                sub_order.custom_params["adaptation_count"] = sub_order.custom_params.get("adaptation_count", 0) + 1
                sub_order.custom_params["current_condition"] = MarketCondition.HIGH_VOLATILITY.value
    
    def _adapt_to_low_liquidity(self, schedule: ExecutionSchedule, pending_orders: List[SubOrder]) -> None:
        """
        Adapt to low liquidity conditions by reducing chunk sizes.
        
        Args:
            schedule: Execution schedule
            pending_orders: List of pending sub-orders
        """
        # Calculate total remaining size
        total_remaining = sum(sub.size for sub in pending_orders)
        
        # Create more, smaller chunks
        if len(pending_orders) < 3:
            return  # Not enough pending orders to adapt
        
        # Double the number of chunks
        num_new_chunks = len(pending_orders) * 2
        
        # Calculate new chunk size
        new_chunk_size = total_remaining / num_new_chunks
        
        # Calculate time range
        if pending_orders:
            start_time = min(sub.scheduled_time for sub in pending_orders)
            end_time = max(sub.scheduled_time for sub in pending_orders)
            time_range = end_time - start_time
            
            # Remove existing pending orders
            to_remove = []
            for sub in pending_orders:
                to_remove.append(sub)
            
            for sub in to_remove:
                schedule.sub_orders.remove(sub)
            
            # Create new, smaller chunks
            for i in range(num_new_chunks):
                # Calculate position in time range
                position = i / (num_new_chunks - 1) if num_new_chunks > 1 else 0
                
                # Calculate time
                chunk_time = start_time + (position * time_range)
                
                # Create new sub-order
                new_sub = SubOrder(
                    id=f"{schedule.order_id}_adaptive_{i}",
                    parent_id=schedule.order_id,
                    symbol=pending_orders[0].symbol,  # Use symbol from first order
                    side=pending_orders[0].side,  # Use side from first order
                    size=new_chunk_size,
                    price=None,
                    order_type="market",
                    exchange_id=None,
                    time_in_force="good_till_cancel",
                    scheduled_time=chunk_time,
                    custom_params={
                        "chunk_number": i + 1,
                        "total_chunks": num_new_chunks,
                        "adaptation_count": 1,
                        "current_condition": MarketCondition.LOW_LIQUIDITY.value
                    }
                )
                
                schedule.sub_orders.append(new_sub)
    
    def _adapt_to_favorable_conditions(self, schedule: ExecutionSchedule, pending_orders: List[SubOrder]) -> None:
        """
        Adapt to favorable price conditions by accelerating execution.
        
        Args:
            schedule: Execution schedule
            pending_orders: List of pending sub-orders
        """
        # If not opportunistic, don't adapt
        if not self.opportunistic:
            return
        
        # Sort by scheduled time
        pending_orders.sort(key=lambda x: x.scheduled_time)
        
        # Calculate the acceleration factor based on price sensitivity
        acceleration_factor = 0.5 * self.price_sensitivity
        
        # Early orders get moved earlier, with a larger acceleration for later orders
        current_time = time.time()
        
        for i, sub_order in enumerate(pending_orders):
            # Calculate position in sequence (0 to 1)
            position = i / (len(pending_orders) - 1) if len(pending_orders) > 1 else 0
            
            # Calculate time shift (later orders get shifted more)
            time_shift = (sub_order.scheduled_time - current_time) * acceleration_factor * (1 + position)
            
            # Calculate new time (ensure it's not in the past)
            new_time = max(current_time, sub_order.scheduled_time - time_shift)
            
            # Update the scheduled time
            sub_order.scheduled_time = new_time
            
            # Update custom params
            sub_order.custom_params["adaptation_count"] = sub_order.custom_params.get("adaptation_count", 0) + 1
            sub_order.custom_params["current_condition"] = MarketCondition.FAVORABLE.value
    
    def _adapt_to_unfavorable_conditions(self, schedule: ExecutionSchedule, pending_orders: List[SubOrder]) -> None:
        """
        Adapt to unfavorable price conditions by slowing down execution.
        
        Args:
            schedule: Execution schedule
            pending_orders: List of pending sub-orders
        """
        # If not defensive, don't adapt
        if not self.defensive:
            return
        
        # Sort by scheduled time
        pending_orders.sort(key=lambda x: x.scheduled_time)
        
        # Calculate delay factor based on price sensitivity
        delay_factor = 0.5 * self.price_sensitivity
        
        # Calculate the current time range
        if pending_orders:
            start_time = min(sub.scheduled_time for sub in pending_orders)
            end_time = max(sub.scheduled_time for sub in pending_orders)
            time_range = end_time - start_time
            
            # Calculate new time range
            new_time_range = time_range * (1 + delay_factor)
            
            # Reschedule pending orders to spread them out
            for i, sub_order in enumerate(pending_orders):
                # Calculate position in sequence (0 to 1)
                position = i / (len(pending_orders) - 1) if len(pending_orders) > 1 else 0
                
                # Calculate new time
                new_time = start_time + (position * new_time_range)
                
                # Update the scheduled time
                sub_order.scheduled_time = new_time
                
                # Update custom params
                sub_order.custom_params["adaptation_count"] = sub_order.custom_params.get("adaptation_count", 0) + 1
                sub_order.custom_params["current_condition"] = MarketCondition.UNFAVORABLE.value
    
    def _calculate_urgency(self, 
                         schedule: ExecutionSchedule, 
                         sub_order: SubOrder, 
                         market_condition: MarketCondition) -> float:
        """
        Calculate urgency based on schedule progress and market condition.
        
        Args:
            schedule: Execution schedule
            sub_order: Sub-order
            market_condition: Current market condition
            
        Returns:
            Urgency value (0.0-1.0)
        """
        current_time = time.time()
        
        # Base urgency calculation
        if schedule.end_time:
            time_remaining = max(0, schedule.end_time - current_time)
            total_time = schedule.end_time - schedule.start_time
            
            if total_time > 0:
                base_urgency = 1.0 - (time_remaining / total_time)
                base_urgency = min(0.9, max(0.1, base_urgency))
            else:
                base_urgency = 0.5
        else:
            base_urgency = 0.5
        
        # Adjust based on market condition
        if market_condition == MarketCondition.HIGH_VOLATILITY:
            # In high volatility, urgency depends on volatility sensitivity
            # More sensitive = more urgent (to get fills while we can)
            urgency = base_urgency * (1 + 0.3 * self.volatility_sensitivity)
        elif market_condition == MarketCondition.LOW_LIQUIDITY:
            # In low liquidity, we need to be more patient
            urgency = base_urgency * (1 - 0.3 * self.liquidity_sensitivity)
        elif market_condition == MarketCondition.FAVORABLE:
            # In favorable conditions, we want to be more aggressive
            urgency = base_urgency * (1 + 0.5 * self.price_sensitivity)
        elif market_condition == MarketCondition.UNFAVORABLE:
            # In unfavorable conditions, we want to be less aggressive
            urgency = base_urgency * (1 - 0.5 * self.price_sensitivity)
        else:
            # Normal conditions
            urgency = base_urgency
        
        # Ensure urgency is in valid range
        return min(0.95, max(0.05, urgency))
    
    def _get_routing_decision(self, 
                           schedule: ExecutionSchedule, 
                           sub_order: SubOrder,
                           urgency: float,
                           market_condition: MarketCondition) -> Any:
        """
        Get routing decision for a sub-order, adapted to market conditions.
        
        Args:
            schedule: Execution schedule
            sub_order: Sub-order
            urgency: Urgency value
            market_condition: Current market condition
            
        Returns:
            RoutingDecision
        """
        # Create default request
        request = ExecutionRequest(
            id=sub_order.parent_id,
            symbol=sub_order.symbol,
            side=sub_order.side,
            size=sub_order.size,
            size_usd=sub_order.size * 0  # Will be estimated later
        )
        
        # Choose routing priority based on market condition
        if market_condition == MarketCondition.HIGH_VOLATILITY:
            # In high volatility, prioritize certainty of execution
            routing_priority = RoutingPriority.CERTAINTY
        elif market_condition == MarketCondition.LOW_LIQUIDITY:
            # In low liquidity, look for best liquidity
            routing_priority = RoutingPriority.LIQUIDITY
        elif market_condition == MarketCondition.FAVORABLE:
            # In favorable conditions, we can be more cost-sensitive
            routing_priority = RoutingPriority.COST
        elif market_condition == MarketCondition.UNFAVORABLE:
            # In unfavorable conditions, focus on balanced execution
            routing_priority = RoutingPriority.BALANCED
        else:
            # Normal conditions, use balanced approach
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
                                    urgency: float,
                                    market_condition: MarketCondition) -> Any:
        """
        Get order type recommendation for a sub-order, adapted to market conditions.
        
        Args:
            schedule: Execution schedule
            sub_order: Sub-order
            exchange_id: Exchange ID
            urgency: Urgency value
            market_condition: Current market condition
            
        Returns:
            OrderTypeRecommendation
        """
        # Adjust execution preferences based on market condition
        if market_condition == MarketCondition.HIGH_VOLATILITY:
            # In high volatility, high completion priority, lower cost sensitivity
            preferences = ExecutionPreferences(
                urgency=urgency,
                cost_sensitivity=0.3,
                impact_sensitivity=0.5,
                completion_priority=0.9
            )
        elif market_condition == MarketCondition.LOW_LIQUIDITY:
            # In low liquidity, be patient, lower impact sensitivity
            preferences = ExecutionPreferences(
                urgency=urgency,
                cost_sensitivity=0.5,
                impact_sensitivity=0.8,  # Higher impact sensitivity due to thin markets
                completion_priority=0.6
            )
        elif market_condition == MarketCondition.FAVORABLE:
            # In favorable conditions, prioritize completion over cost
            preferences = ExecutionPreferences(
                urgency=urgency,
                cost_sensitivity=0.3,
                impact_sensitivity=0.5,
                completion_priority=0.8
            )
        elif market_condition == MarketCondition.UNFAVORABLE:
            # In unfavorable conditions, higher cost sensitivity
            preferences = ExecutionPreferences(
                urgency=urgency,
                cost_sensitivity=0.7,
                impact_sensitivity=0.6,
                completion_priority=0.5
            )
        else:
            # Normal conditions, balanced preferences
            preferences = ExecutionPreferences(
                urgency=urgency,
                cost_sensitivity=0.5,
                impact_sensitivity=0.5,
                completion_priority=0.6
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