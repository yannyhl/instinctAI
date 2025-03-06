"""
Execution Metrics

This module defines the data structures for execution metrics that are displayed
in the dashboard. These metrics track execution performance, quality, and status.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time
from datetime import datetime


class ExecutionStatus(Enum):
    """Status of an execution."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELED = "canceled"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ExecutionQuality(Enum):
    """Quality rating of an execution."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    VERY_POOR = "very_poor"
    UNKNOWN = "unknown"


@dataclass
class OrderMetrics:
    """Metrics for a single order."""
    order_id: str
    symbol: str
    side: str
    order_type: str
    size: float
    price: Optional[float] = None
    executed_price: Optional[float] = None
    executed_size: Optional[float] = None
    remaining_size: Optional[float] = None
    status: str = "pending"
    exchange: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    execution_time_ms: Optional[int] = None
    slippage_bps: Optional[float] = None
    fees: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPerformanceMetrics:
    """Performance metrics for an execution."""
    execution_id: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    average_price: Optional[float] = None
    expected_price: Optional[float] = None
    price_improvement_bps: Optional[float] = None
    slippage_bps: Optional[float] = None
    market_impact_bps: Optional[float] = None
    total_fees: Optional[float] = None
    effective_spread_bps: Optional[float] = None
    participation_rate: Optional[float] = None  # % of market volume
    timing_score: Optional[float] = None  # 0.0-1.0
    urgency_score: Optional[float] = None  # 0.0-1.0
    quality_rating: ExecutionQuality = ExecutionQuality.UNKNOWN
    comparison_benchmark: Optional[str] = None  # VWAP, TWAP, etc.
    benchmark_performance_bps: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskMetrics:
    """Risk metrics for an execution."""
    execution_id: str
    position_exposure_percent: Optional[float] = None  # % of portfolio
    drawdown_contribution: Optional[float] = None
    var_contribution: Optional[float] = None
    expected_shortfall_contribution: Optional[float] = None
    correlation_with_portfolio: Optional[float] = None
    risk_checks_passed: int = 0
    risk_checks_warnings: int = 0
    risk_checks_failed: int = 0
    risk_status: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyMetrics:
    """Strategy metrics related to an execution."""
    execution_id: str
    strategy_id: str
    strategy_name: str
    strategy_type: str
    strategy_performance: Optional[float] = None  # Strategy-specific performance
    signal_strength: Optional[float] = None  # 0.0-1.0
    signal_conviction: Optional[float] = None  # 0.0-1.0
    expected_holding_period: Optional[str] = None
    expected_return_bps: Optional[float] = None
    expected_risk_bps: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionMetrics:
    """
    Comprehensive metrics for an execution.
    
    This class combines order metrics, performance metrics, risk metrics,
    and strategy metrics for a complete view of an execution.
    """
    execution_id: str
    symbol: str
    strategy_id: str
    account_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # Nested metrics
    orders: List[OrderMetrics] = field(default_factory=list)
    performance: Optional[ExecutionPerformanceMetrics] = None
    risk: Optional[RiskMetrics] = None
    strategy: Optional[StrategyMetrics] = None
    
    # Summary data
    total_size: float = 0.0
    executed_size: float = 0.0
    remaining_size: float = 0.0
    average_price: Optional[float] = None
    completion_percent: float = 0.0
    execution_time_ms: Optional[int] = None
    
    # Additional fields
    custom_metrics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def update_summary(self) -> None:
        """Update summary metrics based on component metrics."""
        # Update status
        if not self.orders:
            self.status = ExecutionStatus.PENDING
        else:
            statuses = [order.status for order in self.orders]
            if all(status == "completed" for status in statuses):
                self.status = ExecutionStatus.COMPLETED
            elif all(status in ["canceled", "failed"] for status in statuses):
                self.status = ExecutionStatus.FAILED
            elif any(status == "active" for status in statuses):
                self.status = ExecutionStatus.ACTIVE
            elif any(status == "completed" for status in statuses):
                self.status = ExecutionStatus.PARTIAL
            else:
                self.status = ExecutionStatus.PENDING
        
        # Update size metrics
        self.total_size = sum(order.size for order in self.orders)
        self.executed_size = sum(order.executed_size or 0 for order in self.orders)
        self.remaining_size = self.total_size - self.executed_size
        
        # Update completion percentage
        if self.total_size > 0:
            self.completion_percent = (self.executed_size / self.total_size) * 100
        else:
            self.completion_percent = 0.0
        
        # Update average price
        if self.executed_size > 0:
            weighted_prices = sum((order.executed_price or 0) * (order.executed_size or 0) 
                                for order in self.orders)
            self.average_price = weighted_prices / self.executed_size
        
        # Update timestamp
        self.updated_at = time.time()
        
        # Update execution time if completed
        if self.status == ExecutionStatus.COMPLETED and not self.execution_time_ms:
            start_time = min(order.created_at for order in self.orders)
            end_time = max(order.updated_at for order in self.orders)
            self.execution_time_ms = int((end_time - start_time) * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a dictionary for serialization."""
        result = {
            "execution_id": self.execution_id,
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value,
            "total_size": self.total_size,
            "executed_size": self.executed_size,
            "remaining_size": self.remaining_size,
            "average_price": self.average_price,
            "completion_percent": self.completion_percent,
            "execution_time_ms": self.execution_time_ms,
            "orders": [vars(order) for order in self.orders],
            "custom_metrics": self.custom_metrics,
            "tags": self.tags
        }
        
        # Add nested metrics if they exist
        if self.performance:
            result["performance"] = vars(self.performance)
            result["performance"]["quality_rating"] = self.performance.quality_rating.value
        
        if self.risk:
            result["risk"] = vars(self.risk)
        
        if self.strategy:
            result["strategy"] = vars(self.strategy)
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionMetrics':
        """Create metrics from a dictionary."""
        # Create base metrics
        metrics = cls(
            execution_id=data["execution_id"],
            symbol=data["symbol"],
            strategy_id=data["strategy_id"],
            account_id=data["account_id"],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            status=ExecutionStatus(data.get("status", "pending")),
            total_size=data.get("total_size", 0.0),
            executed_size=data.get("executed_size", 0.0),
            remaining_size=data.get("remaining_size", 0.0),
            average_price=data.get("average_price"),
            completion_percent=data.get("completion_percent", 0.0),
            execution_time_ms=data.get("execution_time_ms"),
            custom_metrics=data.get("custom_metrics", {}),
            tags=data.get("tags", [])
        )
        
        # Add orders
        if "orders" in data:
            metrics.orders = [OrderMetrics(**order_data) for order_data in data["orders"]]
        
        # Add performance metrics
        if "performance" in data:
            perf_data = data["performance"].copy()
            if "quality_rating" in perf_data:
                perf_data["quality_rating"] = ExecutionQuality(perf_data["quality_rating"])
            metrics.performance = ExecutionPerformanceMetrics(**perf_data)
        
        # Add risk metrics
        if "risk" in data:
            metrics.risk = RiskMetrics(**data["risk"])
        
        # Add strategy metrics
        if "strategy" in data:
            metrics.strategy = StrategyMetrics(**data["strategy"])
        
        return metrics


# Public API
__all__ = [
    'ExecutionStatus',
    'ExecutionQuality',
    'OrderMetrics',
    'ExecutionPerformanceMetrics',
    'RiskMetrics',
    'StrategyMetrics',
    'ExecutionMetrics'
] 