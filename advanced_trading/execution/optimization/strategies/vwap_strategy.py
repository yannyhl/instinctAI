"""
VWAP Execution Strategy

This module provides a Volume-Weighted Average Price (VWAP) execution strategy that
splits an order into chunks weighted by expected market volume at each time interval.
This aims to match the volume profile of the market and achieve a price close to VWAP.
"""

import time
import logging
import uuid
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

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

class VolumeProfile:
    """
    Represents a volume profile for a trading day.
    
    This class holds information about expected trading volume
    distribution throughout a trading day, used for VWAP execution.
    """
    
    def __init__(self, 
                 buckets: int = 24,  # Default to hourly buckets for a 24-hour market
                 profile: Optional[List[float]] = None):
        """
        Initialize a volume profile.
        
        Args:
            buckets: Number of time buckets in the profile
            profile: Volume distribution as percentage for each bucket (must sum to 1.0)
        """
        self.buckets = buckets
        
        if profile:
            # Validate profile
            if len(profile) != buckets:
                raise ValueError(f"Profile must have {buckets} buckets")
            
            if abs(sum(profile) - 1.0) > 0.001:
                raise ValueError("Profile must sum to 1.0")
            
            self.profile = profile
        else:
            # Use default profile for 24-hour crypto markets
            # This approximates higher volume during US and Asian trading hours
            self.profile = self._default_crypto_profile(buckets)
    
    def _default_crypto_profile(self, buckets: int) -> List[float]:
        """
        Create a default volume profile for 24-hour crypto markets.
        
        Args:
            buckets: Number of buckets
            
        Returns:
            List of volume percentages for each bucket
        """
        if buckets == 24:  # Hourly buckets
            # Higher volume during US trading hours (13-21 UTC)
            # and Asian trading hours (0-8 UTC)
            us_peak = [0.055, 0.058, 0.062, 0.065, 0.063, 0.058, 0.055, 0.052, 0.048]
            asia_peak = [0.045, 0.048, 0.052, 0.055, 0.058, 0.055, 0.052, 0.048, 0.045]
            low_volume = [0.035, 0.033, 0.031, 0.030, 0.030, 0.032]
            
            # Combine into 24-hour profile
            profile = us_peak + low_volume + asia_peak
            
            # Normalize
            total = sum(profile)
            return [v / total for v in profile]
        else:
            # For non-standard bucket counts, use a simplified approach
            return [1.0 / buckets] * buckets
    
    def get_bucket_for_time(self, timestamp: float) -> int:
        """
        Get the bucket index for a given timestamp.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            Bucket index (0 to buckets-1)
        """
        # Convert to datetime for easier manipulation
        dt = datetime.fromtimestamp(timestamp)
        
        # Get hour of day (0-23)
        hour = dt.hour
        
        if self.buckets == 24:
            # If we have 24 buckets, map directly to hours
            return hour
        else:
            # For other bucket counts, map proportionally
            return int((hour / 24.0) * self.buckets)
    
    def get_volume_percent_for_period(self, 
                                     start_time: float, 
                                     end_time: float) -> List[Tuple[int, float]]:
        """
        Get volume percentages for a specific time period.
        
        Args:
            start_time: Start time as Unix timestamp
            end_time: End time as Unix timestamp
            
        Returns:
            List of (bucket_index, volume_percentage) tuples for the period
        """
        # Convert to datetime for easier manipulation
        start_dt = datetime.fromtimestamp(start_time)
        end_dt = datetime.fromtimestamp(end_time)
        
        # Handle case where period crosses day boundary
        if end_dt.date() > start_dt.date():
            # If period spans multiple days, we need a more complex approach
            # For now, we'll use a simplified model that assumes
            # the volume profile is repeated each day
            
            # Calculate duration in days
            duration_days = (end_dt - start_dt).total_seconds() / 86400.0
            
            # If duration is very long, just return full profile
            if duration_days > 3:
                return [(i, p) for i, p in enumerate(self.profile)]
            
            # Otherwise, calculate partial day volumes
            result = []
            
            # Get start day partial volume
            start_bucket = self.get_bucket_for_time(start_time)
            day_end = datetime.combine(start_dt.date(), datetime.max.time()).timestamp()
            
            for i in range(start_bucket, self.buckets):
                result.append((i, self.profile[i]))
            
            # Get any full days in between
            full_days = int(duration_days)
            if full_days > 0:
                for _ in range(full_days - 1):  # -1 because we handle first and last separately
                    for i in range(self.buckets):
                        result.append((i, self.profile[i]))
            
            # Get end day partial volume
            end_bucket = self.get_bucket_for_time(end_time)
            for i in range(end_bucket + 1):
                result.append((i, self.profile[i]))
            
            return result
        else:
            # Period within same day
            start_bucket = self.get_bucket_for_time(start_time)
            end_bucket = self.get_bucket_for_time(end_time)
            
            # If in same bucket
            if start_bucket == end_bucket:
                # Calculate fraction of bucket covered
                bucket_start = datetime(start_dt.year, start_dt.month, start_dt.day, 
                                       int(start_bucket * 24 / self.buckets))
                bucket_end = bucket_start + timedelta(hours=24/self.buckets)
                
                total_bucket_seconds = (bucket_end - bucket_start).total_seconds()
                period_seconds = (end_dt - start_dt).total_seconds()
                
                fraction = period_seconds / total_bucket_seconds
                
                return [(start_bucket, self.profile[start_bucket] * fraction)]
            
            # Handle case crossing bucket boundaries
            result = []
            
            # First partial bucket
            bucket_end = datetime(start_dt.year, start_dt.month, start_dt.day, 
                                 int((start_bucket + 1) * 24 / self.buckets) % 24)
            
            # Handle midnight crossing
            if bucket_end.hour < start_dt.hour:
                bucket_end = bucket_end.replace(day=bucket_end.day + 1)
            
            bucket_seconds = (bucket_end - start_dt).total_seconds()
            bucket_fraction = bucket_seconds / (24 * 3600 / self.buckets)
            
            result.append((start_bucket, self.profile[start_bucket] * bucket_fraction))
            
            # Full intermediate buckets
            for i in range(start_bucket + 1, end_bucket):
                result.append((i, self.profile[i]))
            
            # Last partial bucket
            if start_bucket != end_bucket:
                bucket_start = datetime(end_dt.year, end_dt.month, end_dt.day, 
                                      int(end_bucket * 24 / self.buckets))
                
                # Handle midnight crossing
                if bucket_start.hour > end_dt.hour:
                    bucket_start = bucket_start.replace(day=bucket_start.day - 1)
                
                bucket_seconds = (end_dt - bucket_start).total_seconds()
                bucket_fraction = bucket_seconds / (24 * 3600 / self.buckets)
                
                result.append((end_bucket, self.profile[end_bucket] * bucket_fraction))
            
            return result


class VWAPStrategy(ExecutionStrategy):
    """
    Volume-Weighted Average Price (VWAP) execution strategy.
    
    This strategy splits an order into chunks weighted by expected market volume
    at each time interval. This aims to minimize market impact by following the
    typical volume pattern of the market throughout the day.
    
    This strategy is suitable for:
    - Medium to large orders that might have market impact
    - When you want to achieve a price close to the VWAP benchmark
    - When executing over a longer period (several hours)
    - Markets with predictable volume patterns
    
    The strategy uses the Smart Order Router to select the best exchange(s) for each chunk
    and the Order Type Optimizer to select the best order type and parameters.
    """
    
    def __init__(self,
                 min_chunks: int = 5,
                 max_chunks: int = 48,
                 min_chunk_interval_seconds: int = 300,  # 5 minutes
                 max_chunk_size_pct: float = 0.1,  # Max size as percentage of total
                 volume_profile: Optional[VolumeProfile] = None,
                 randomize_times: bool = True,
                 randomize_sizes: bool = False,
                 order_router=None,
                 order_optimizer=None,
                 registry=None,
                 profiler=None):
        """
        Initialize the VWAP execution strategy.
        
        Args:
            min_chunks: Minimum number of chunks to split an order into
            max_chunks: Maximum number of chunks to split an order into
            min_chunk_interval_seconds: Minimum time between chunks
            max_chunk_size_pct: Maximum size of a chunk as percentage of total order
            volume_profile: Volume profile to use (default creates standard profile)
            randomize_times: Whether to add random jitter to execution times
            randomize_sizes: Whether to randomize chunk sizes around target
            order_router: SmartOrderRouter instance (or None to use singleton)
            order_optimizer: OrderTypeOptimizer instance (or None to use singleton)
            registry: ExchangeCapabilityRegistry instance (or None to use singleton)
            profiler: ExchangeProfiler instance (or None to use singleton)
        """
        super().__init__(
            name="VWAPStrategy",
            description="Volume-Weighted Average Price execution strategy",
            order_router=order_router,
            order_optimizer=order_optimizer,
            registry=registry,
            profiler=profiler
        )
        
        self.min_chunks = min_chunks
        self.max_chunks = max_chunks
        self.min_chunk_interval_seconds = min_chunk_interval_seconds
        self.max_chunk_size_pct = max_chunk_size_pct
        self.volume_profile = volume_profile or VolumeProfile()
        self.randomize_times = randomize_times
        self.randomize_sizes = randomize_sizes
    
    def create_execution_schedule(self, request: ExecutionRequest) -> ExecutionSchedule:
        """
        Create a VWAP execution schedule for the given request.
        
        This will split the order into chunks weighted by expected market volume
        at each time interval over the specified time period.
        
        Args:
            request: Execution request
            
        Returns:
            ExecutionSchedule detailing how the order will be executed
        """
        logger.info(f"Creating VWAP execution schedule for order {request.id}")
        
        # Create schedule
        schedule = ExecutionSchedule(
            order_id=request.id,
            total_size=request.size,
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        # Validate time period
        if not request.end_time or request.end_time <= request.start_time:
            logger.warning(f"Invalid time period for VWAP order {request.id}")
            request.end_time = request.start_time + 14400  # Default to 4 hours
        
        # Get volume profile for the period
        volume_buckets = self.volume_profile.get_volume_percent_for_period(
            request.start_time, request.end_time
        )
        
        # Calculate total volume percentage for normalization
        total_volume_pct = sum(pct for _, pct in volume_buckets)
        
        # Calculate time period
        time_period_seconds = request.end_time - request.start_time
        
        # Calculate number of chunks
        num_chunks = self._calculate_num_chunks(
            request.size, time_period_seconds, len(volume_buckets)
        )
        
        # Generate chunk times and sizes
        chunk_times, chunk_sizes = self._generate_chunks(
            request.start_time, request.end_time, 
            request.size, num_chunks, volume_buckets, total_volume_pct
        )
        
        # Create sub-orders
        sub_orders = []
        
        for i, (chunk_time, chunk_size) in enumerate(zip(chunk_times, chunk_sizes)):
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
        
        logger.info(f"Created VWAP execution schedule with {len(sub_orders)} chunks for order {request.id}")
        
        return schedule
    
    def get_next_actions(self, schedule: ExecutionSchedule) -> List[SubOrder]:
        """
        Get the next actions to take for a schedule.
        
        For VWAP, this means returning any sub-orders that are due for execution.
        
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
    
    def _calculate_num_chunks(self, 
                             size: float, 
                             time_period_seconds: float,
                             num_volume_buckets: int) -> int:
        """
        Calculate the optimal number of chunks based on order size, time period, and volume buckets.
        
        Args:
            size: Order size
            time_period_seconds: Execution time period in seconds
            num_volume_buckets: Number of volume buckets in the period
            
        Returns:
            Number of chunks
        """
        # Calculate max chunks based on minimum interval
        max_time_chunks = int(time_period_seconds / self.min_chunk_interval_seconds)
        
        # Calculate max chunks based on order size and max chunk size percentage
        max_size_chunks = int(1 / self.max_chunk_size_pct)
        
        # Consider volume buckets
        max_volume_chunks = num_volume_buckets * 2  # Allow up to 2 chunks per volume bucket
        
        # Calculate number of chunks considering constraints
        num_chunks = min(max_time_chunks, max_size_chunks, max_volume_chunks, self.max_chunks)
        num_chunks = max(num_chunks, self.min_chunks)
        
        return num_chunks
    
    def _generate_chunks(self,
                        start_time: float,
                        end_time: float,
                        total_size: float,
                        num_chunks: int,
                        volume_buckets: List[Tuple[int, float]],
                        total_volume_pct: float) -> Tuple[List[float], List[float]]:
        """
        Generate chunk times and sizes based on volume profile.
        
        Args:
            start_time: Start time
            end_time: End time
            total_size: Total order size
            num_chunks: Number of chunks
            volume_buckets: List of (bucket_index, volume_percentage) tuples
            total_volume_pct: Total volume percentage in the period
            
        Returns:
            Tuple of (chunk_times, chunk_sizes)
        """
        import random
        
        # Initialize result lists
        chunk_times = []
        chunk_sizes = []
        
        # Sort volume buckets by bucket index to ensure correct ordering
        sorted_buckets = sorted(volume_buckets, key=lambda x: x[0])
        
        # Normalize volume percentages
        normalized_buckets = [(idx, pct / total_volume_pct) for idx, pct in sorted_buckets]
        
        # Calculate total time period
        time_period = end_time - start_time
        
        # First, allocate chunks to buckets
        # We'll allocate chunks proportionally to the volume in each bucket
        bucket_chunks = {}
        
        chunks_allocated = 0
        for idx, vol_pct in normalized_buckets:
            # Calculate number of chunks for this bucket
            bucket_chunk_count = max(1, round(num_chunks * vol_pct))
            
            # Ensure we don't exceed total number of chunks
            if chunks_allocated + bucket_chunk_count > num_chunks:
                bucket_chunk_count = num_chunks - chunks_allocated
            
            # Allocate chunks
            bucket_chunks[idx] = bucket_chunk_count
            chunks_allocated += bucket_chunk_count
            
            # If we've allocated all chunks, break
            if chunks_allocated >= num_chunks:
                break
        
        # If we haven't allocated all chunks, add them to buckets with highest volume
        if chunks_allocated < num_chunks:
            # Sort buckets by volume percentage (descending)
            sorted_by_volume = sorted(normalized_buckets, key=lambda x: x[1], reverse=True)
            
            # Allocate remaining chunks
            for idx, _ in sorted_by_volume:
                if chunks_allocated >= num_chunks:
                    break
                
                bucket_chunks[idx] = bucket_chunks.get(idx, 0) + 1
                chunks_allocated += 1
        
        # For each bucket, calculate chunk times and sizes
        bucket_start_times = {}
        bucket_durations = {}
        
        # Calculate bucket start times and durations
        bucket_size = time_period / len(set(idx for idx, _ in volume_buckets))
        for idx, _ in volume_buckets:
            bucket_start_times[idx] = start_time + (idx * bucket_size)
            bucket_durations[idx] = bucket_size
        
        # Generate chunk times for each bucket
        for idx, num_bucket_chunks in bucket_chunks.items():
            # Skip if no chunks allocated
            if num_bucket_chunks <= 0:
                continue
            
            bucket_start = bucket_start_times[idx]
            bucket_duration = bucket_durations[idx]
            
            # Calculate intervals within the bucket
            interval = bucket_duration / num_bucket_chunks
            
            for i in range(num_bucket_chunks):
                # Calculate base time
                base_time = bucket_start + (i * interval)
                
                # Add random jitter if requested
                if self.randomize_times:
                    # Add up to ±25% of interval as jitter
                    jitter = interval * 0.25 * (2 * random.random() - 1)
                    
                    # Ensure time is within bucket
                    time_with_jitter = base_time + jitter
                    time_with_jitter = max(bucket_start, min(bucket_start + bucket_duration, time_with_jitter))
                    
                    chunk_times.append(time_with_jitter)
                else:
                    # No jitter, just add midpoint of interval
                    chunk_times.append(base_time + (interval / 2))
        
        # Sort chunk times
        chunk_times.sort()
        
        # Ensure we have the right number of chunk times
        if len(chunk_times) > num_chunks:
            # If too many, remove excess
            chunk_times = chunk_times[:num_chunks]
        elif len(chunk_times) < num_chunks:
            # If too few, duplicate last time (shouldn't happen with proper allocation)
            while len(chunk_times) < num_chunks:
                chunk_times.append(end_time)
        
        # Calculate chunk sizes based on volume profile
        remaining_size = total_size
        
        for i, chunk_time in enumerate(chunk_times[:-1]):  # Process all but the last chunk
            # Find which bucket this chunk time falls into
            bucket_idx = None
            for idx in bucket_chunks.keys():
                if (bucket_start_times[idx] <= chunk_time < 
                    bucket_start_times[idx] + bucket_durations[idx]):
                    bucket_idx = idx
                    break
            
            # If no bucket found, use first bucket (shouldn't happen)
            if bucket_idx is None:
                bucket_idx = next(iter(bucket_chunks.keys()))
            
            # Get volume percentage for this bucket
            vol_pct = next((pct for idx, pct in normalized_buckets if idx == bucket_idx), 0)
            
            # Calculate base chunk size
            chunk_bucket_chunks = bucket_chunks.get(bucket_idx, 1)
            base_chunk_size = (total_size * vol_pct) / chunk_bucket_chunks
            
            # Add random variation if requested
            if self.randomize_sizes:
                # Add up to ±15% random variation
                variation = base_chunk_size * 0.15 * (2 * random.random() - 1)
                chunk_size = base_chunk_size + variation
                
                # Ensure chunk size is positive and not too large
                chunk_size = max(base_chunk_size * 0.5, min(base_chunk_size * 1.5, chunk_size))
            else:
                chunk_size = base_chunk_size
            
            # Ensure we don't exceed remaining size
            chunk_size = min(chunk_size, remaining_size * 0.9)  # Leave at least 10% for later chunks
            
            # Add to result
            chunk_sizes.append(chunk_size)
            
            # Update remaining size
            remaining_size -= chunk_size
        
        # Add last chunk with remaining size
        chunk_sizes.append(remaining_size)
        
        return chunk_times, chunk_sizes
    
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
                
                # Scale urgency: start moderate, increase more rapidly at the end
                if urgency < 0.7:
                    # Early in the schedule, moderate urgency
                    urgency = 0.3 + (urgency * 0.4)
                else:
                    # Late in the schedule, higher urgency
                    urgency = 0.58 + ((urgency - 0.7) * 1.4)
                
                # Ensure urgency is in valid range
                urgency = min(0.9, max(0.3, urgency))
                return urgency
        
        # Get chunk number from custom params
        chunk_number = sub_order.custom_params.get("chunk_number", 1)
        total_chunks = sub_order.custom_params.get("total_chunks", 1)
        
        # Increase urgency slightly for later chunks
        return 0.4 + (chunk_number / total_chunks) * 0.3
    
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
        
        # Use liquidity-focused routing for VWAP
        routing_priority = RoutingPriority.LIQUIDITY
        
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
        # Create balanced execution preferences for VWAP
        preferences = ExecutionPreferences(
            urgency=urgency,
            cost_sensitivity=0.5,
            impact_sensitivity=0.7,  # Higher impact sensitivity for VWAP
            completion_priority=0.7  # Higher completion priority for VWAP
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