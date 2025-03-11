"""
Dashboard Example

This example demonstrates how to use the execution dashboard components
to create a simple dashboard application. It shows how to:

1. Set up the dashboard components
2. Create and control executions
3. Display execution metrics
4. Handle dashboard interactions
"""

import logging
import time
import random
import uuid
from datetime import datetime, timedelta
import threading
import json
import os
from typing import Dict, List, Any, Optional

from advanced_trading.execution.dashboard.models.metrics import (
    ExecutionMetrics, OrderMetrics, ExecutionStatus, ExecutionQuality,
    ExecutionPerformanceMetrics, RiskMetrics, StrategyMetrics
)
from advanced_trading.execution.dashboard.models.state import DashboardState, DashboardView
from advanced_trading.execution.dashboard.services.metrics_collector import MetricsCollector
from advanced_trading.execution.dashboard.services.dashboard_data import DashboardDataService
from advanced_trading.execution.dashboard.services.execution_controller import (
    ExecutionController, ControlAction
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_mock_order(symbol: str, side: str) -> OrderMetrics:
    """Generate a mock order for demonstration."""
    order_id = f"order_{uuid.uuid4().hex[:8]}"
    price = 30000.0 if symbol == "BTC" else 2000.0
    size = random.uniform(0.05, 0.2)
    
    return OrderMetrics(
        order_id=order_id,
        symbol=symbol,
        side=side,
        order_type="limit" if random.random() > 0.3 else "market",
        size=size,
        price=price,
        executed_price=price * (1 + random.uniform(-0.001, 0.001)),
        executed_size=size if random.random() > 0.2 else size * random.uniform(0.5, 0.95),
        status="completed" if random.random() > 0.3 else "active",
        exchange="binance" if random.random() > 0.5 else "kraken",
        slippage_bps=random.uniform(0, 5)
    )


def generate_mock_executions(count: int) -> List[ExecutionMetrics]:
    """Generate mock executions for demonstration."""
    symbols = ["BTC", "ETH", "SOL", "ADA", "DOT"]
    strategies = ["momentum", "mean_reversion", "trend_following", "arbitrage"]
    accounts = ["main", "test"]
    
    executions = []
    for _ in range(count):
        symbol = random.choice(symbols)
        strategy_id = random.choice(strategies)
        account_id = random.choice(accounts)
        
        # Create base metrics
        execution_id = str(uuid.uuid4())
        metrics = ExecutionMetrics(
            execution_id=execution_id,
            symbol=symbol,
            strategy_id=strategy_id,
            account_id=account_id,
            created_at=time.time() - random.uniform(0, 86400),
            tags=[strategy_id, symbol, account_id]
        )
        
        # Add orders
        order_count = random.randint(1, 5)
        for _ in range(order_count):
            side = "buy" if random.random() > 0.5 else "sell"
            metrics.orders.append(generate_mock_order(symbol, side))
        
        # Update summary metrics
        metrics.update_summary()
        
        # Add performance metrics
        duration_ms = random.randint(100, 10000)
        slippage_bps = random.uniform(0, 10)
        quality_rating = random.choice(list(ExecutionQuality))
        
        metrics.performance = ExecutionPerformanceMetrics(
            execution_id=execution_id,
            start_time=metrics.created_at,
            end_time=metrics.created_at + (duration_ms / 1000),
            duration_ms=duration_ms,
            average_price=metrics.average_price,
            slippage_bps=slippage_bps,
            quality_rating=quality_rating,
            market_impact_bps=slippage_bps * 0.7,
            participation_rate=random.uniform(0.01, 0.1),
            timing_score=random.uniform(0, 1.0),
            urgency_score=random.uniform(0, 1.0)
        )
        
        # Add risk metrics
        metrics.risk = RiskMetrics(
            execution_id=execution_id,
            position_exposure_percent=random.uniform(0.01, 0.1),
            drawdown_contribution=random.uniform(0, 0.02),
            var_contribution=random.uniform(0, 0.05),
            risk_checks_passed=random.randint(3, 10),
            risk_checks_warnings=random.randint(0, 2),
            risk_checks_failed=random.randint(0, 1)
        )
        
        # Add strategy metrics
        metrics.strategy = StrategyMetrics(
            execution_id=execution_id,
            strategy_id=strategy_id,
            strategy_name=strategy_id.replace("_", " ").title(),
            strategy_type=strategy_id,
            signal_strength=random.uniform(0.5, 1.0),
            signal_conviction=random.uniform(0.5, 1.0),
            expected_return_bps=random.uniform(5, 50),
            expected_risk_bps=random.uniform(2, 30)
        )
        
        executions.append(metrics)
    
    return executions


def simulate_execution_updates(controller: ExecutionController, metrics_collector: MetricsCollector) -> None:
    """Simulate execution updates for demonstration."""
    # Get active executions
    active_executions = metrics_collector.get_active_executions()
    
    for metrics in active_executions:
        # Random chance to update
        if random.random() > 0.7:
            continue
        
        # Create a new order
        side = "buy" if random.random() > 0.5 else "sell"
        order = generate_mock_order(metrics.symbol, side)
        
        # Add the order
        controller.add_order(metrics.execution_id, order)
        
        # Random chance to complete
        if random.random() > 0.9:
            # Update all orders to completed
            for existing_order in metrics.orders:
                if existing_order.status != "completed":
                    controller.update_order(
                        metrics.execution_id,
                        existing_order.order_id,
                        {"status": "completed", "executed_size": existing_order.size}
                    )
            
            # Update execution status
            metrics_collector.update_execution(
                metrics.execution_id,
                {"status": ExecutionStatus.COMPLETED}
            )


def run_simulation(controller: ExecutionController, metrics_collector: MetricsCollector) -> None:
    """Run a simulation of execution updates."""
    # Loop until stopped
    while True:
        try:
            # Simulate execution updates
            simulate_execution_updates(controller, metrics_collector)
            
            # Random chance to create a new execution
            if random.random() > 0.8:
                symbol = random.choice(["BTC", "ETH", "SOL", "ADA", "DOT"])
                strategy_id = random.choice(["momentum", "mean_reversion", "trend_following", "arbitrage"])
                
                # Create execution
                execution_id = controller.create_execution(
                    symbol=symbol,
                    strategy_id=strategy_id,
                    account_id="main",
                    params={"tags": [strategy_id, symbol, "main"]}
                )
                
                # Start execution
                controller.control_execution(
                    execution_id,
                    ControlAction.START
                )
                
                logger.info(f"Created new execution {execution_id} for {symbol}")
            
            # Sleep for a bit
            time.sleep(1.0)
        except Exception as e:
            logger.error(f"Error in simulation: {str(e)}")
            time.sleep(1.0)


def print_dashboard_stats(data_service: DashboardDataService) -> None:
    """Print dashboard statistics."""
    # Get active executions
    active_executions = data_service.get_active_executions()
    
    # Get recent executions
    recent_executions = data_service.get_recent_executions()
    
    # Get statistics
    stats = data_service.get_execution_statistics()
    
    # Print statistics
    print("\n" + "=" * 50)
    print("EXECUTION DASHBOARD")
    print("=" * 50)
    
    print(f"\nActive Executions: {stats['active_executions']}")
    print(f"Completed Executions: {stats['completed_executions']}")
    print(f"Failed Executions: {stats['failed_executions']}")
    print(f"Total Orders: {stats['total_orders']}")
    print(f"Average Slippage: {stats['average_slippage_bps']:.2f} bps")
    print(f"Average Execution Time: {stats['average_execution_time_ms']:.2f} ms")
    print(f"Total Notional: ${stats['total_executed_notional']:.2f}")
    
    # Print active executions
    if active_executions:
        print("\nACTIVE EXECUTIONS:")
        for i, execution in enumerate(active_executions[:5]):
            print(f"{i+1}. {execution['symbol']} - {execution['strategy_id']} - "
                 f"{execution['completion_percent']:.1f}% complete")
    
    # Print dashboard state
    state = data_service.get_dashboard_state()
    print(f"\nCurrent View: {state['current_view']}")
    if state['selected_execution_id']:
        print(f"Selected Execution: {state['selected_execution_id']}")
    if state['selected_symbol']:
        print(f"Selected Symbol: {state['selected_symbol']}")
    
    print("=" * 50 + "\n")


def handle_user_input(
    controller: ExecutionController, 
    data_service: DashboardDataService
) -> None:
    """Handle user input for controlling the dashboard."""
    while True:
        try:
            print("\nDASHBOARD CONTROLS:")
            print("1. Select Execution")
            print("2. Control Execution (start/pause/resume/cancel)")
            print("3. Change View")
            print("4. Apply Filter")
            print("5. Clear Filters")
            print("6. Emergency Stop All")
            print("7. Toggle Auto-Refresh")
            print("8. Exit")
            
            choice = input("Enter choice (1-8): ")
            
            if choice == "1":
                # Get recent executions
                recent_executions = data_service.get_recent_executions()
                
                # Show list of executions
                print("\nRECENT EXECUTIONS:")
                for i, execution in enumerate(recent_executions[:10]):
                    print(f"{i+1}. {execution['symbol']} - {execution['strategy_id']} - "
                         f"{execution['status']} - {execution['completion_percent']:.1f}% complete")
                
                # Get selection
                selection = input("Enter execution number to select (or 0 to cancel): ")
                try:
                    selection_idx = int(selection) - 1
                    if selection_idx >= 0 and selection_idx < len(recent_executions):
                        execution_id = recent_executions[selection_idx]['execution_id']
                        data_service.select_execution(execution_id)
                        print(f"Selected execution {execution_id}")
                except ValueError:
                    print("Invalid selection")
            
            elif choice == "2":
                # Get execution to control
                execution_id = data_service.dashboard_state.selected_execution_id
                if not execution_id:
                    print("No execution selected")
                    continue
                
                # Get action
                print("\nCONTROL ACTIONS:")
                print("1. Start")
                print("2. Pause")
                print("3. Resume")
                print("4. Cancel")
                
                action_choice = input("Enter action (1-4): ")
                
                # Map to action
                action_map = {
                    "1": ControlAction.START,
                    "2": ControlAction.PAUSE,
                    "3": ControlAction.RESUME,
                    "4": ControlAction.CANCEL
                }
                
                if action_choice in action_map:
                    action = action_map[action_choice]
                    success = controller.control_execution(execution_id, action)
                    if success:
                        print(f"Successfully executed {action.value} on {execution_id}")
                    else:
                        print(f"Failed to execute {action.value} on {execution_id}")
                else:
                    print("Invalid action")
            
            elif choice == "3":
                # Change view
                print("\nVIEWS:")
                print("1. Overview")
                print("2. Execution")
                print("3. History")
                print("4. Settings")
                
                view_choice = input("Enter view (1-4): ")
                
                # Map to view
                view_map = {
                    "1": "overview",
                    "2": "execution",
                    "3": "history",
                    "4": "settings"
                }
                
                if view_choice in view_map:
                    view_name = view_map[view_choice]
                    data_service.change_view(view_name)
                    print(f"Changed to {view_name} view")
                else:
                    print("Invalid view")
            
            elif choice == "4":
                # Apply filter
                print("\nFILTER TYPES:")
                print("1. Symbol")
                print("2. Strategy")
                print("3. Status")
                print("4. Time Range")
                
                filter_choice = input("Enter filter type (1-4): ")
                
                if filter_choice == "1":
                    symbols = data_service.get_available_symbols()
                    print(f"Available symbols: {', '.join(symbols)}")
                    symbol = input("Enter symbol to filter by: ")
                    if symbol in symbols:
                        data_service.select_symbol(symbol)
                        print(f"Filtered by symbol {symbol}")
                    else:
                        print("Invalid symbol")
                
                elif filter_choice == "2":
                    strategies = data_service.get_available_strategies()
                    print(f"Available strategies: {', '.join(strategies)}")
                    strategy = input("Enter strategy to filter by: ")
                    if strategy in strategies:
                        data_service.apply_filter("strategies", {strategy})
                        print(f"Filtered by strategy {strategy}")
                    else:
                        print("Invalid strategy")
                
                elif filter_choice == "3":
                    statuses = ["pending", "active", "completed", "failed", "canceled"]
                    print(f"Available statuses: {', '.join(statuses)}")
                    status = input("Enter status to filter by: ")
                    if status in statuses:
                        data_service.apply_filter("statuses", {status})
                        print(f"Filtered by status {status}")
                    else:
                        print("Invalid status")
                
                elif filter_choice == "4":
                    hours = input("Enter time range in hours: ")
                    try:
                        hours_int = int(hours)
                        if hours_int > 0:
                            data_service.set_time_range(hours_int)
                            print(f"Set time range to {hours_int} hours")
                        else:
                            print("Invalid time range")
                    except ValueError:
                        print("Invalid time range")
                
                else:
                    print("Invalid filter type")
            
            elif choice == "5":
                # Clear filters
                data_service.clear_filters()
                print("Cleared all filters")
            
            elif choice == "6":
                # Emergency stop all
                confirm = input("Are you sure you want to stop all executions? (y/n): ")
                if confirm.lower() == "y":
                    results = controller.emergency_stop_all()
                    print(f"Stopped {sum(1 for v in results.values() if v)} executions")
                else:
                    print("Emergency stop canceled")
            
            elif choice == "7":
                # Toggle auto-refresh
                auto_refresh = data_service.toggle_auto_refresh()
                print(f"Auto-refresh is now {'on' if auto_refresh else 'off'}")
            
            elif choice == "8":
                # Exit
                print("Exiting dashboard...")
                return
            
            else:
                print("Invalid choice")
            
            # Print updated stats
            print_dashboard_stats(data_service)
        
        except Exception as e:
            logger.error(f"Error handling input: {str(e)}")


def main():
    """Main function for the dashboard example."""
    logger.info("Starting dashboard example")
    
    # Create metrics collector
    metrics_collector = MetricsCollector()
    
    # Generate some mock executions
    mock_executions = generate_mock_executions(20)
    for metrics in mock_executions:
        metrics_collector.add_execution(metrics)
    
    # Create dashboard data service
    data_service = DashboardDataService(metrics_collector)
    
    # Create execution controller
    controller = ExecutionController(metrics_collector)
    
    # Start data collection
    data_service.start_data_collection()
    
    try:
        # Start simulation in a separate thread
        simulation_thread = threading.Thread(
            target=run_simulation,
            args=(controller, metrics_collector),
            daemon=True
        )
        simulation_thread.start()
        
        # Print initial stats
        print_dashboard_stats(data_service)
        
        # Handle user input
        handle_user_input(controller, data_service)
    
    finally:
        # Stop data collection
        data_service.stop_data_collection()
        
        # Save metrics
        metrics_collector.save_metrics("execution_metrics.json")
        
        logger.info("Dashboard example completed")


if __name__ == "__main__":
    main() 