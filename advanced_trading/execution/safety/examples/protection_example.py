"""
Protection Components Example

This example demonstrates how to use the protection components to handle execution failures
and detect anomalies in trading operations. The example includes:

1. Setting up a TradingProtection instance with various protection actions
2. Configuring failure handling and anomaly detection
3. Integrating with the emergency protocol system
4. Simulating and handling execution failures
5. Monitoring metrics for anomalies

This serves as a practical guide for using the protection components in a trading system.
"""

import logging
import time
from typing import Dict, Any, List

from advanced_trading.execution.safety.emergency import EmergencyHandler, EmergencyLevel, EmergencyProtocol
from advanced_trading.execution.safety.protection import (
    ExecutionFailureType,
    ExecutionAnomalyType,
    TradingProtection,
    PauseExchangeTradingAction,
    RateThrottlingAction,
    OrderSizeReductionAction
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_protection_system() -> TradingProtection:
    """
    Set up a complete protection system with emergency handling and protection actions.
    
    Returns:
        Configured TradingProtection instance
    """
    # Create emergency handler
    emergency_handler = EmergencyHandler()
    
    # Create emergency protocols for different situations
    connection_protocol = EmergencyProtocol(
        name="connection_issues_protocol",
        description="Protocol for handling exchange connection issues"
    )
    emergency_handler.register_protocol(connection_protocol)
    
    order_execution_protocol = EmergencyProtocol(
        name="order_execution_protocol",
        description="Protocol for handling order execution issues"
    )
    emergency_handler.register_protocol(order_execution_protocol)
    
    # Create trading protection system
    protection = TradingProtection(emergency_handler)
    
    # Register protection actions
    pause_action = PauseExchangeTradingAction()
    throttle_action = RateThrottlingAction(throttle_factor=0.3, min_delay_ms=1000)
    size_reduction_action = OrderSizeReductionAction(reduction_factor=0.5, min_orders=3)
    
    protection.register_protection_action(pause_action)
    protection.register_protection_action(throttle_action)
    protection.register_protection_action(size_reduction_action)
    
    # Configure failure protection
    protection.configure_failure_protection(
        ExecutionFailureType.CONNECTION_ERROR, 
        pause_action.name
    )
    protection.configure_failure_protection(
        ExecutionFailureType.TIMEOUT, 
        throttle_action.name
    )
    protection.configure_failure_protection(
        ExecutionFailureType.RATE_LIMIT, 
        throttle_action.name
    )
    protection.configure_failure_protection(
        ExecutionFailureType.PARTIAL_FILL, 
        size_reduction_action.name
    )
    protection.configure_failure_protection(
        ExecutionFailureType.PRICE_SLIPPAGE, 
        size_reduction_action.name
    )
    
    # Configure emergency thresholds for failure types
    protection.failure_handler.set_emergency_threshold(
        ExecutionFailureType.CONNECTION_ERROR,
        count=3,
        level=EmergencyLevel.ALERT
    )
    protection.failure_handler.set_emergency_threshold(
        ExecutionFailureType.RATE_LIMIT,
        count=5,
        level=EmergencyLevel.WARNING
    )
    
    # Configure anomaly protection
    protection.configure_anomaly_protection(
        ExecutionAnomalyType.UNUSUAL_LATENCY,
        throttle_action.name
    )
    protection.configure_anomaly_protection(
        ExecutionAnomalyType.EXCESSIVE_REJECTIONS,
        pause_action.name
    )
    protection.configure_anomaly_protection(
        ExecutionAnomalyType.UNUSUAL_PRICE_IMPACT,
        size_reduction_action.name
    )
    
    # Set anomaly thresholds
    protection.anomaly_monitor.set_threshold(
        ExecutionAnomalyType.UNUSUAL_LATENCY,
        threshold=3.0  # 3x baseline is unusual
    )
    protection.anomaly_monitor.set_threshold(
        ExecutionAnomalyType.UNUSUAL_PRICE_IMPACT,
        threshold=0.05,  # 5% price impact is unusual
        exchange_id="binance"
    )
    
    # Set anomaly emergency thresholds
    protection.anomaly_monitor.set_emergency_threshold(
        ExecutionAnomalyType.UNUSUAL_PRICE_IMPACT,
        severity=0.8,
        level=EmergencyLevel.CRITICAL
    )
    
    # Set up baseline metrics for specific exchanges and symbols
    protection.anomaly_monitor.update_baseline(
        exchange_id="binance",
        symbol="BTC/USDT",
        metric="order_latency_ms",
        value=120.0
    )
    protection.anomaly_monitor.update_baseline(
        exchange_id="coinbase",
        symbol="ETH/USD",
        metric="order_latency_ms",
        value=150.0
    )
    
    logger.info("Protection system configured successfully")
    return protection


def simulate_failures(protection: TradingProtection) -> None:
    """
    Simulate various execution failures and demonstrate how they are handled.
    
    Args:
        protection: The trading protection system to use
    """
    logger.info("Simulating execution failures...")
    
    # Simulate a connection error
    result = protection.report_failure(
        failure_type=ExecutionFailureType.CONNECTION_ERROR,
        exchange_id="binance",
        error_message="Connection timed out",
        details={"attempt": 1, "endpoint": "/api/v3/order"}
    )
    logger.info(f"Connection error handling result: {result}")
    
    # Simulate rate limit exceeded
    for i in range(6):  # Trigger emergency threshold (5)
        result = protection.report_failure(
            failure_type=ExecutionFailureType.RATE_LIMIT,
            exchange_id="binance",
            error_message="Rate limit exceeded",
            symbol="BTC/USDT",
            details={"limit": "10 requests/second", "window": "1 minute"}
        )
        logger.info(f"Rate limit error #{i+1} handling result: {result}")
    
    # Simulate price slippage
    result = protection.report_failure(
        failure_type=ExecutionFailureType.PRICE_SLIPPAGE,
        exchange_id="coinbase",
        error_message="Price slipped beyond acceptable limit",
        order_id="ord123456",
        symbol="ETH/USD",
        details={
            "expected_price": 3500.0,
            "actual_price": 3525.0,
            "slippage_percent": 0.71
        }
    )
    logger.info(f"Price slippage handling result: {result}")
    
    # Resolve one of the failures
    resolved = protection.failure_handler.resolve_failure(
        result["failure_id"],
        details={"resolution": "Manual intervention", "resolved_by": "operator"}
    )
    logger.info(f"Failure resolution result: {resolved}")
    
    # Get active failures
    active_failures = protection.failure_handler.get_active_failures()
    logger.info(f"Active failures count: {len(active_failures)}")
    
    # Get failure statistics
    stats = protection.failure_handler.get_failure_statistics()
    logger.info(f"Failure statistics: {stats}")


def simulate_anomaly_detection(protection: TradingProtection) -> None:
    """
    Simulate anomaly detection by checking various metrics.
    
    Args:
        protection: The trading protection system to use
    """
    logger.info("Simulating anomaly detection...")
    
    # Check normal latency (no anomaly)
    result = protection.check_metric(
        exchange_id="binance",
        symbol="BTC/USDT",
        metric="order_latency_ms",
        value=150.0,  # Within normal range of baseline (120ms)
        anomaly_type=ExecutionAnomalyType.UNUSUAL_LATENCY
    )
    logger.info(f"Normal latency check result: {result}")
    
    # Check unusual latency (anomaly)
    result = protection.check_metric(
        exchange_id="binance",
        symbol="BTC/USDT",
        metric="order_latency_ms",
        value=500.0,  # Well above baseline (120ms)
        anomaly_type=ExecutionAnomalyType.UNUSUAL_LATENCY,
        context={
            "order_id": "ord654321",
            "order_type": "LIMIT",
            "side": "BUY"
        }
    )
    logger.info(f"Unusual latency anomaly detected: {result is not None}")
    if result:
        logger.info(f"Anomaly severity: {result['anomaly'].severity:.2f}")
        logger.info(f"Action results: {result['action_results']}")
    
    # Check price impact (extreme anomaly that triggers emergency)
    result = protection.check_metric(
        exchange_id="binance",
        symbol="BTC/USDT",
        metric="price_impact_percent",
        value=0.15,  # 15% is very high (threshold was 5%)
        anomaly_type=ExecutionAnomalyType.UNUSUAL_PRICE_IMPACT,
        context={
            "order_id": "ord987654",
            "order_type": "MARKET",
            "side": "SELL",
            "size": 5.0,
            "expected_price": 40000.0,
            "executed_price": 34000.0
        }
    )
    logger.info(f"Price impact anomaly detected: {result is not None}")
    if result:
        logger.info(f"Anomaly severity: {result['anomaly'].severity:.2f}")
        logger.info(f"Emergency triggered: {result['emergency_triggered']}")
    
    # Get active anomalies
    active_anomalies = protection.anomaly_monitor.get_active_anomalies(min_severity=0.5)
    logger.info(f"Active high-severity anomalies: {len(active_anomalies)}")


def run_protection_example() -> None:
    """Run the complete protection system example."""
    logger.info("Starting protection system example")
    
    # Set up the protection system
    protection = setup_protection_system()
    
    # Run failure simulation
    simulate_failures(protection)
    
    # Run anomaly detection simulation
    simulate_anomaly_detection(protection)
    
    # Get overall protection system status
    status = protection.get_status()
    logger.info(f"Protection system status: {status}")
    
    logger.info("Protection system example completed")


if __name__ == "__main__":
    run_protection_example() 