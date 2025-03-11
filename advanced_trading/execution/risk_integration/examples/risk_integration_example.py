"""
Risk Integration Example

This example demonstrates how to use the risk integration components to:
1. Set up an execution risk manager
2. Perform pre-trade risk checks
3. Validate positions
4. Analyze execution results from a risk perspective

The example shows how to integrate these components with execution strategies.
"""

import logging
import time
import json
import random
from decimal import Decimal
from typing import Dict, Any, List

from advanced_trading.execution.risk_integration import (
    # Core components
    ExecutionRiskManager, ExecutionRiskConfig, RiskValidationStatus,
    # Risk checks
    PositionSizeCheck, MaxDrawdownCheck, ExposureCheck, VolumePercentCheck,
    SlippageCheck,
    # Position risk
    PositionRiskValidator, PositionRiskStatus
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_risk_manager() -> ExecutionRiskManager:
    """
    Set up and configure an execution risk manager with custom settings.
    
    Returns:
        Configured execution risk manager
    """
    # Create custom configuration for the risk manager
    config = ExecutionRiskConfig(
        # General settings
        enabled=True,
        enforce_pre_trade_checks=True,
        log_all_checks=True,
        
        # Position-level limits
        max_position_size_usd=10000.0,  # $10K max position
        max_position_size_percent=0.05,  # 5% of portfolio
        max_position_notional={
            "BTC": 5000.0,  # $5K max for BTC
            "ETH": 3000.0   # $3K max for ETH
        },
        
        # Order limits
        max_order_size_usd=5000.0,       # $5K max order
        max_order_size_percent_of_position=0.5,  # 50% of position
        
        # Market impact limits
        max_volume_percent=0.03,  # 3% of volume
        max_slippage_percent=0.005,  # 0.5% max slippage
        
        # Portfolio-level constraints
        max_portfolio_drawdown=0.08,  # 8% max drawdown
        max_daily_loss=0.03,  # 3% max daily loss
        
        # Post-trade analysis
        track_slippage=True,
        track_market_impact=True,
        analyze_execution_quality=True
    )
    
    # Create risk manager with custom configuration
    risk_manager = ExecutionRiskManager(config)
    
    # Register custom checks (in addition to default ones)
    risk_manager.register_pre_trade_check(
        "volatility_check",
        lambda order, portfolio, market: {
            "status": RiskValidationStatus.PASSED 
            if market.get("volatility", 0) < 0.05 
            else RiskValidationStatus.WARNING,
            "message": "Checking market volatility",
            "details": {"volatility": market.get("volatility", 0)}
        }
    )
    
    logger.info("Risk manager set up with custom configuration")
    return risk_manager


def create_sample_order(symbol: str = "BTC", side: str = "buy") -> Dict[str, Any]:
    """
    Create a sample order for demonstration.
    
    Args:
        symbol: Trading symbol
        side: Order side (buy/sell)
        
    Returns:
        Sample order details
    """
    price = 30000.0 if symbol == "BTC" else 2000.0  # Mock prices
    
    return {
        "id": f"order_{int(time.time())}",
        "symbol": symbol,
        "side": side,
        "size": random.uniform(0.05, 0.2),  # 0.05-0.2 BTC/ETH
        "price": price,
        "estimated_notional": price * random.uniform(0.05, 0.2),
        "type": "limit",
        "time_in_force": "GTC",
        "exchange": "binance"
    }


def create_sample_portfolio() -> Dict[str, Any]:
    """
    Create a sample portfolio state for demonstration.
    
    Returns:
        Sample portfolio details
    """
    return {
        "total_value": 100000.0,  # $100K portfolio
        "positions": {
            "BTC": {
                "size": 0.5,
                "entry_price": 29000.0,
                "notional": 14500.0,
                "unrealized_pnl": 500.0,
                "entry_time": time.time() - 86400 * 5  # 5 days old
            },
            "ETH": {
                "size": 3.0,
                "entry_price": 1950.0,
                "notional": 5850.0,
                "unrealized_pnl": 150.0,
                "entry_time": time.time() - 86400 * 10  # 10 days old
            }
        },
        "gross_exposure": 0.2,
        "net_exposure": 0.2,
        "current_drawdown": 0.02,
        "daily_pnl_percent": 0.005,
        "asset_exposures": {
            "BTC": 0.145,  # 14.5% in BTC
            "ETH": 0.0585   # 5.85% in ETH
        }
    }


def create_sample_market_data() -> Dict[str, Dict[str, Any]]:
    """
    Create sample market data for demonstration.
    
    Returns:
        Dictionary of market data by symbol
    """
    return {
        "BTC": {
            "price": 30000.0,
            "bid": 29995.0,
            "ask": 30005.0,
            "daily_volatility": 0.025,  # 2.5% daily volatility
            "volume": 5000.0,
            "average_volume": 4500.0,
            "atr": 750.0,
            "volatility": 0.04
        },
        "ETH": {
            "price": 2000.0,
            "bid": 1998.0,
            "ask": 2002.0,
            "daily_volatility": 0.035,  # 3.5% daily volatility
            "volume": 50000.0,
            "average_volume": 45000.0,
            "atr": 70.0,
            "volatility": 0.06
        }
    }


def example_pre_trade_checks():
    """
    Example of performing pre-trade checks before order execution.
    """
    logger.info("--- PRE-TRADE RISK CHECK EXAMPLE ---")
    
    # Set up the risk manager
    risk_manager = setup_risk_manager()
    
    # Create sample data
    order = create_sample_order("BTC", "buy")
    portfolio = create_sample_portfolio()
    market_data = create_sample_market_data()["BTC"]
    
    # Validate the order
    logger.info(f"Validating order: {order['side']} {order['size']} {order['symbol']} @ {order['price']}")
    
    # Perform validation
    check_results = risk_manager.validate_order(
        order=order,
        portfolio_state=portfolio,
        market_data=market_data
    )
    
    # Determine if order is valid
    is_valid, results = risk_manager.is_order_valid(
        order=order,
        portfolio_state=portfolio,
        market_data=market_data
    )
    
    # Log results
    if is_valid:
        logger.info("Order PASSED all critical risk checks!")
    else:
        logger.warning("Order FAILED one or more critical risk checks!")
    
    # Display check results
    for result in check_results:
        status_icon = "✅" if result.status == RiskValidationStatus.PASSED else (
            "⚠️" if result.status == RiskValidationStatus.WARNING else "❌"
        )
        logger.info(f"{status_icon} {result.check_name}: {result.message}")
    
    # Create a larger order that will fail
    large_order = create_sample_order("BTC", "buy")
    large_order["size"] = 2.0  # Large size that should exceed limits
    large_order["price"] = 30000.0
    large_order["estimated_notional"] = large_order["size"] * large_order["price"]
    
    logger.info(f"\nValidating large order: {large_order['side']} {large_order['size']} "
               f"{large_order['symbol']} @ {large_order['price']}")
    
    # Check if valid
    is_valid, results = risk_manager.is_order_valid(
        order=large_order,
        portfolio_state=portfolio,
        market_data=market_data
    )
    
    if is_valid:
        logger.info("Large order PASSED all critical risk checks!")
    else:
        logger.warning("Large order FAILED one or more critical risk checks!")
        
        # Display failures
        for result in results:
            if result.status != RiskValidationStatus.PASSED:
                logger.warning(f"❌ {result.check_name}: {result.message}")


def example_position_risk_validation():
    """
    Example of validating position risk using the PositionRiskValidator.
    """
    logger.info("\n--- POSITION RISK VALIDATION EXAMPLE ---")
    
    # Create position risk validator
    validator = PositionRiskValidator(
        max_position_size_pct=0.1,        # 10% max position
        max_position_loss_pct=0.05,       # 5% max loss
        max_position_var_pct=0.03,        # 3% max VaR
        max_position_age_days=30.0,       # 30 days max
        risk_reward_min=1.5,              # 1.5 min R:R ratio
        enable_auto_stops=True,
        enable_size_scaling=True
    )
    
    # Create sample data
    portfolio = create_sample_portfolio()
    market_data = create_sample_market_data()
    positions = portfolio["positions"]
    
    # Validate all positions
    logger.info("Validating all positions...")
    violations = validator.validate_all_positions(
        positions=positions,
        market_data=market_data,
        portfolio_data=portfolio
    )
    
    # Log results
    if violations:
        logger.warning(f"Found {sum(len(v) for v in violations.values())} violations across "
                     f"{len(violations)} positions")
        
        for symbol, position_violations in violations.items():
            logger.warning(f"Violations for {symbol}:")
            for violation in position_violations:
                logger.warning(f"  - {violation.check_name}: {violation.message}")
    else:
        logger.info("All positions are within risk parameters")
    
    # Get risk status for each position
    for symbol in positions:
        status = validator.get_position_risk_status(symbol)
        logger.info(f"Risk status for {symbol}: {status.value}")
    
    # Calculate stop levels for a position
    btc_stops = validator.calculate_stop_levels(
        symbol="BTC",
        position_data=positions["BTC"],
        market_data=market_data["BTC"]
    )
    
    logger.info(f"Calculated stop levels for BTC: Stop @ {btc_stops['stop_price']}, "
               f"Target @ {btc_stops['target_price']}, "
               f"R:R = {btc_stops['risk_reward_ratio']:.2f}")
    
    # Adjust position size based on risk
    base_size = 0.2  # 0.2 BTC
    adjusted_size = validator.adjust_position_size(
        symbol="BTC",
        base_position_size=base_size,
        market_data=market_data["BTC"],
        portfolio_data=portfolio
    )
    
    logger.info(f"Position size adjustment: {base_size} BTC → {adjusted_size} BTC")
    
    # Get at-risk positions
    at_risk = validator.get_at_risk_positions()
    if at_risk:
        logger.warning(f"At-risk positions: {', '.join(at_risk)}")
    else:
        logger.info("No positions at risk")


def example_post_trade_analysis():
    """
    Example of post-trade analysis of execution results.
    """
    logger.info("\n--- POST-TRADE ANALYSIS EXAMPLE ---")
    
    # Set up risk manager
    risk_manager = setup_risk_manager()
    
    # Create sample data
    original_order = create_sample_order("ETH", "buy")
    original_order["price"] = 2000.0
    original_order["size"] = 0.5
    
    # Create execution details with some slippage
    execution_details = {
        "order_id": original_order["id"],
        "symbol": original_order["symbol"],
        "executed_price": 2010.0,  # 0.5% slippage
        "executed_size": original_order["size"],
        "executed_notional": 2010.0 * original_order["size"],
        "price_at_order_time": 2000.0,
        "execution_time": time.time(),
        "exchange_fees": 2.01,
        "slippage_percent": 0.005,
        "execution_delay_ms": 120
    }
    
    # Perform post-trade analysis
    logger.info(f"Analyzing execution of {original_order['symbol']} order...")
    
    analysis_results = risk_manager.analyze_execution(
        order=original_order,
        execution_details=execution_details,
        portfolio_state=create_sample_portfolio(),
        market_data=create_sample_market_data()[original_order["symbol"]]
    )
    
    # Log results
    for result in analysis_results:
        status_icon = "✅" if result.status == RiskValidationStatus.PASSED else (
            "⚠️" if result.status == RiskValidationStatus.WARNING else "❌"
        )
        logger.info(f"{status_icon} {result.check_name}: {result.message}")
    
    # Create another example with excessive slippage
    bad_execution = execution_details.copy()
    bad_execution["executed_price"] = 2060.0  # 3% slippage
    bad_execution["slippage_percent"] = 0.03
    bad_execution["executed_notional"] = 2060.0 * original_order["size"]
    
    logger.info(f"\nAnalyzing execution with excessive slippage...")
    
    bad_results = risk_manager.analyze_execution(
        order=original_order,
        execution_details=bad_execution,
        portfolio_state=create_sample_portfolio(),
        market_data=create_sample_market_data()[original_order["symbol"]]
    )
    
    # Log results
    for result in bad_results:
        status_icon = "✅" if result.status == RiskValidationStatus.PASSED else (
            "⚠️" if result.status == RiskValidationStatus.WARNING else "❌"
        )
        logger.info(f"{status_icon} {result.check_name}: {result.message}")


def main():
    """Main function to run all examples."""
    logger.info("RISK INTEGRATION EXAMPLES\n" + "="*30)
    
    # Run examples
    example_pre_trade_checks()
    example_position_risk_validation()
    example_post_trade_analysis()
    
    logger.info("\nAll examples completed!")


if __name__ == "__main__":
    main() 