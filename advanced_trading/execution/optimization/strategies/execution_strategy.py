"""
Execution Strategy Framework

This module provides a framework for execution strategies that determine
when and how to split orders over time and across venues for optimal execution.
"""

import time
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
import uuid
import datetime

from advanced_trading.execution.optimization.profiles import (
    get_exchange_registry, get_exchange_profiler,
    ExchangeCapabilities, ExchangePerformance
)

from advanced_trading.execution.optimization.routers import (
    get_smart_order_router, 
    OrderRoutingParameters, RoutingDecision
)

from advanced_trading.execution.optimization.order_types import (
    get_order_type_optimizer,
    MarketCondition, OrderTypeParameters, ExecutionPreferences,
    OrderTypeOptimizationRequest, OrderTypeRecommendation
)

# Initialize logger
logger = logging.getLogger(__name__)

class ExecutionPriority(Enum):
    """Execution priority levels."""
    MINIMIZE_COST = "minimize_cost"  # Lowest trading costs
    MINIMIZE_MARKET_IMPACT = "minimize_market_impact"  # Lowest market impact
    MINIMIZE_TIME = "minimize_time"  # Fastest execution
    MAXIMIZE_CERTAINTY = "maximize_certainty"  # Highest fill probability
    STEALTH = "stealth"  # Minimize detection by other market participants
    BALANCED = "balanced"  # Balanced approach
    CUSTOM = "custom"  # Custom priorities

class ExecutionAlgorithm(Enum):
    """Available execution algorithms."""
    BASIC = "basic"  # Simple immediate execution
    TWAP = "twap"  # Time-Weighted Average Price
    VWAP = "vwap"  # Volume-Weighted Average Price
    ADAPTIVE = "adaptive"  # Adaptive to market conditions
    ICEBERG = "iceberg"  # Iceberg/hidden orders
    PACED = "paced"  # Paced execution
    LIQUIDITY_SEEKING = "liquidity_seeking"  # Seeks liquidity
    CUSTOM = "custom"  # Custom algorithm

@dataclass
class SubOrder:
    """Represents a part of an order to be executed."""
    id: str
    parent_id: str
    symbol: str
    side: str
    size: float
    price: Optional[float] = None
    order_type: str = "market"
    exchange_id: Optional[str] = None
    time_in_force: str = "good_till_cancel"
    post_only: bool = False
    reduce_only: bool = False
    scheduled_time: Optional[float] = None
    expiration_time: Optional[float] = None
    status: str = "pending"  # pending, sent, filled, partial, cancelled, expired, failed
    filled_size: float = 0.0
    filled_price: Optional[float] = None
    fill_time: Optional[float] = None
    custom_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionRequest:
    """Request for execution of an order."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    side: str = ""  # buy or sell
    size: float = 0.0
    size_usd: float = 0.0
    limit_price: Optional[float] = None
    reference_price: Optional[float] = None
    priority: ExecutionPriority = ExecutionPriority.BALANCED
    algorithm: ExecutionAlgorithm = ExecutionAlgorithm.BASIC
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    max_participation_rate: Optional[float] = None  # 0.0-1.0
    min_size_increment: Optional[float] = None
    preferred_exchanges: List[str] = field(default_factory=list)
    excluded_exchanges: List[str] = field(default_factory=list)
    custom_params: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default values after creation."""
        if not self.start_time:
            self.start_time = time.time()
            
        if not self.end_time:
            # Default to 1 hour for algorithms that need an end time
            self.end_time = self.start_time + 3600
            
        if not self.max_participation_rate:
            # Default to 20% of volume for volume-based algorithms
            self.max_participation_rate = 0.2
            
        if not self.min_size_increment:
            # Default to 1% of total size
            self.min_size_increment = self.size * 0.01

@dataclass
class ExecutionSchedule:
    """Schedule for executing an order over time."""
    order_id: str
    total_size: float
    executed_size: float = 0.0
    remaining_size: float = 0.0
    sub_orders: List[SubOrder] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    is_complete: bool = False
    average_price: Optional[float] = None
    status: str = "active"  # active, completed, cancelled, failed
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize after creation."""
        if self.remaining_size == 0:
            self.remaining_size = self.total_size

@dataclass
class ExecutionResult:
    """Result of an execution strategy."""
    order_id: str
    symbol: str
    side: str
    total_size: float
    executed_size: float
    remaining_size: float
    average_price: Optional[float] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_seconds: float = 0.0
    is_complete: bool = False
    status: str = "unknown"
    sub_orders: List[SubOrder] = field(default_factory=list)
    trading_cost_bps: Optional[float] = None
    market_impact_bps: Optional[float] = None
    slippage_bps: Optional[float] = None
    performance_summary: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields after creation."""
        self.duration_seconds = self.end_time - self.start_time
        
class ExecutionStrategy(ABC):
    """
    Base class for all execution strategies.
    
    An execution strategy defines how an order should be split and executed
    over time and across venues for optimal results.
    """
    
    def __init__(self,
                 name: str,
                 description: str,
                 order_router=None,
                 order_optimizer=None,
                 registry=None,
                 profiler=None):
        """
        Initialize the execution strategy.
        
        Args:
            name: Strategy name
            description: Strategy description
            order_router: SmartOrderRouter instance (or None to use singleton)
            order_optimizer: OrderTypeOptimizer instance (or None to use singleton)
            registry: ExchangeCapabilityRegistry instance (or None to use singleton)
            profiler: ExchangeProfiler instance (or None to use singleton)
        """
        self.name = name
        self.description = description
        
        # Get dependencies
        self.order_router = order_router or get_smart_order_router()
        self.order_optimizer = order_optimizer or get_order_type_optimizer()
        self.registry = registry or get_exchange_registry()
        self.profiler = profiler or get_exchange_profiler()
        
        # Active orders
        self.active_orders: Dict[str, ExecutionSchedule] = {}
        
        # Market condition cache
        self.market_conditions: Dict[str, MarketCondition] = {}
        
        # Performance tracking
        self.completed_orders: List[ExecutionResult] = []
        self.max_history_size = 100
        
        logger.info(f"Initialized execution strategy: {name}")
    
    @abstractmethod
    def create_execution_schedule(self, request: ExecutionRequest) -> ExecutionSchedule:
        """
        Create an execution schedule for the given request.
        
        Args:
            request: Execution request
            
        Returns:
            ExecutionSchedule detailing how the order will be executed
        """
        pass
    
    @abstractmethod
    def get_next_actions(self, schedule: ExecutionSchedule) -> List[SubOrder]:
        """
        Get the next actions to take for a schedule.
        
        Args:
            schedule: Execution schedule
            
        Returns:
            List of sub-orders to execute now
        """
        pass
    
    def execute_order(self, request: ExecutionRequest) -> str:
        """
        Begin execution of an order.
        
        Args:
            request: Execution request
            
        Returns:
            Order ID that can be used to track execution
        """
        # Create execution schedule
        schedule = self.create_execution_schedule(request)
        
        # Store in active orders
        self.active_orders[request.id] = schedule
        
        # Start execution process
        self._process_schedule(schedule)
        
        return request.id
    
    def _process_schedule(self, schedule: ExecutionSchedule) -> None:
        """
        Process an execution schedule.
        
        Args:
            schedule: Execution schedule to process
        """
        # Get next actions
        actions = self.get_next_actions(schedule)
        
        # Process actions
        for action in actions:
            self._execute_sub_order(action)
            
        # Update schedule
        self._update_schedule(schedule)
    
    def _execute_sub_order(self, sub_order: SubOrder) -> None:
        """
        Execute a sub-order.
        
        Args:
            sub_order: Sub-order to execute
        """
        # In a real implementation, this would send the order to the exchange
        # For this example, we'll just simulate execution
        
        # Update sub-order status
        sub_order.status = "sent"
        
        # Log the action
        logger.info(f"Executing sub-order {sub_order.id}: {sub_order.size} {sub_order.symbol} on {sub_order.exchange_id}")
    
    def _update_schedule(self, schedule: ExecutionSchedule) -> None:
        """
        Update a schedule with execution results.
        
        Args:
            schedule: Execution schedule to update
        """
        # Update execution status
        total_executed = sum(sub.filled_size for sub in schedule.sub_orders if sub.status in ["filled", "partial"])
        schedule.executed_size = total_executed
        schedule.remaining_size = schedule.total_size - total_executed
        
        # Calculate average price
        filled_sub_orders = [sub for sub in schedule.sub_orders if sub.status in ["filled", "partial"] and sub.filled_price is not None]
        if filled_sub_orders:
            weighted_price_sum = sum(sub.filled_size * sub.filled_price for sub in filled_sub_orders)
            total_filled_size = sum(sub.filled_size for sub in filled_sub_orders)
            schedule.average_price = weighted_price_sum / total_filled_size
        
        # Check if complete
        if schedule.remaining_size <= 0 or all(sub.status in ["filled", "cancelled", "expired", "failed"] for sub in schedule.sub_orders):
            schedule.is_complete = True
            schedule.status = "completed"
            self._finalize_order(schedule)
    
    def _finalize_order(self, schedule: ExecutionSchedule) -> None:
        """
        Finalize a completed order.
        
        Args:
            schedule: Execution schedule to finalize
        """
        # Create execution result
        result = ExecutionResult(
            order_id=schedule.order_id,
            symbol=schedule.sub_orders[0].symbol if schedule.sub_orders else "",
            side=schedule.sub_orders[0].side if schedule.sub_orders else "",
            total_size=schedule.total_size,
            executed_size=schedule.executed_size,
            remaining_size=schedule.remaining_size,
            average_price=schedule.average_price,
            start_time=schedule.start_time,
            end_time=time.time(),
            is_complete=schedule.is_complete,
            status=schedule.status,
            sub_orders=schedule.sub_orders
        )
        
        # Calculate performance metrics
        self._calculate_performance_metrics(result)
        
        # Add to completed orders
        self.completed_orders.append(result)
        
        # Limit history size
        if len(self.completed_orders) > self.max_history_size:
            self.completed_orders.pop(0)
        
        # Remove from active orders
        if schedule.order_id in self.active_orders:
            del self.active_orders[schedule.order_id]
    
    def _calculate_performance_metrics(self, result: ExecutionResult) -> None:
        """
        Calculate performance metrics for an execution result.
        
        Args:
            result: Execution result to calculate metrics for
        """
        # In a real implementation, this would calculate performance metrics
        # like slippage, market impact, trading costs, etc.
        # For this example, we'll just set placeholder values
        
        result.trading_cost_bps = 10.0  # 10 basis points
        result.market_impact_bps = 5.0  # 5 basis points
        result.slippage_bps = 2.0  # 2 basis points
        
        result.performance_summary = {
            "trading_cost_bps": result.trading_cost_bps,
            "market_impact_bps": result.market_impact_bps,
            "slippage_bps": result.slippage_bps,
            "total_cost_bps": result.trading_cost_bps + result.market_impact_bps + result.slippage_bps,
            "execution_duration_seconds": result.duration_seconds,
            "exchanges_used": len(set(sub.exchange_id for sub in result.sub_orders if sub.exchange_id)),
            "order_types_used": len(set(sub.order_type for sub in result.sub_orders))
        }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get the status of an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Dict with order status information
        """
        # Check active orders
        if order_id in self.active_orders:
            schedule = self.active_orders[order_id]
            
            return {
                "order_id": order_id,
                "status": schedule.status,
                "total_size": schedule.total_size,
                "executed_size": schedule.executed_size,
                "remaining_size": schedule.remaining_size,
                "is_complete": schedule.is_complete,
                "average_price": schedule.average_price,
                "sub_orders": len(schedule.sub_orders),
                "active_sub_orders": sum(1 for sub in schedule.sub_orders if sub.status in ["pending", "sent"]),
                "start_time": schedule.start_time,
                "elapsed_seconds": time.time() - schedule.start_time
            }
        
        # Check completed orders
        for result in self.completed_orders:
            if result.order_id == order_id:
                return {
                    "order_id": order_id,
                    "status": result.status,
                    "total_size": result.total_size,
                    "executed_size": result.executed_size,
                    "remaining_size": result.remaining_size,
                    "is_complete": result.is_complete,
                    "average_price": result.average_price,
                    "sub_orders": len(result.sub_orders),
                    "start_time": result.start_time,
                    "end_time": result.end_time,
                    "duration_seconds": result.duration_seconds,
                    "trading_cost_bps": result.trading_cost_bps,
                    "market_impact_bps": result.market_impact_bps,
                    "slippage_bps": result.slippage_bps
                }
        
        # Not found
        return {
            "order_id": order_id,
            "status": "not_found",
            "error": "Order not found"
        }
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if the order was cancelled, False otherwise
        """
        if order_id not in self.active_orders:
            return False
        
        schedule = self.active_orders[order_id]
        
        # Cancel pending sub-orders
        for sub in schedule.sub_orders:
            if sub.status in ["pending", "sent"]:
                sub.status = "cancelled"
        
        # Update schedule
        schedule.status = "cancelled"
        
        # Finalize order
        self._finalize_order(schedule)
        
        return True
    
    def update_market_condition(self, symbol: str, condition: MarketCondition) -> None:
        """
        Update market condition for a symbol.
        
        Args:
            symbol: Symbol
            condition: Market condition
        """
        self.market_conditions[symbol] = condition
    
    def get_market_condition(self, symbol: str) -> Optional[MarketCondition]:
        """
        Get market condition for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            Market condition or None if not available
        """
        if symbol in self.market_conditions:
            return self.market_conditions[symbol]
        
        # Try to get from order optimizer
        condition = self.order_optimizer._get_market_condition(None, symbol)
        if condition:
            self.market_conditions[symbol] = condition
            return condition
        
        return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary for all completed orders.
        
        Returns:
            Dict with performance summary
        """
        if not self.completed_orders:
            return {"error": "No completed orders"}
        
        # Calculate average metrics
        avg_trading_cost = sum(r.trading_cost_bps for r in self.completed_orders if r.trading_cost_bps is not None) / len(self.completed_orders)
        avg_market_impact = sum(r.market_impact_bps for r in self.completed_orders if r.market_impact_bps is not None) / len(self.completed_orders)
        avg_slippage = sum(r.slippage_bps for r in self.completed_orders if r.slippage_bps is not None) / len(self.completed_orders)
        
        return {
            "completed_orders": len(self.completed_orders),
            "avg_trading_cost_bps": avg_trading_cost,
            "avg_market_impact_bps": avg_market_impact,
            "avg_slippage_bps": avg_slippage,
            "avg_total_cost_bps": avg_trading_cost + avg_market_impact + avg_slippage,
            "success_rate": sum(1 for r in self.completed_orders if r.is_complete) / len(self.completed_orders),
            "avg_duration_seconds": sum(r.duration_seconds for r in self.completed_orders) / len(self.completed_orders)
        } 