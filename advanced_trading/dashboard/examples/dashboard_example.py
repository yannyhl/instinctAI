"""
Unified Dashboard Example

This example demonstrates how to set up and use the unified dashboard
for the Instinct AI Trading System.
"""

import time
import logging
import sys
import threading
import random
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Import dashboard components
from advanced_trading.dashboard.core import (
    DashboardConfig, DashboardController, ViewType, 
    DashboardTheme, LayoutType
)

logger = logging.getLogger(__name__)


class DummyStrategyDataProvider:
    """Simulated data provider for strategies."""
    
    def __init__(self):
        self.strategies = {
            "strat1": {"id": "strat1", "name": "Moving Average Crossover", "type": "trend_following"},
            "strat2": {"id": "strat2", "name": "RSI Mean Reversion", "type": "mean_reversion"},
            "strat3": {"id": "strat3", "name": "MACD Momentum", "type": "momentum"},
            "strat4": {"id": "strat4", "name": "Breakout Detection", "type": "breakout"}
        }
    
    def get_strategies(self):
        """Get list of available strategies."""
        return list(self.strategies.values())
    
    def get_strategy(self, strategy_id):
        """Get details for a specific strategy."""
        return self.strategies.get(strategy_id)


class DummyExecutionDataProvider:
    """Simulated data provider for executions."""
    
    def __init__(self):
        self.executions = {}
    
    def register_execution(self, execution):
        """Register an execution to track."""
        self.executions[execution.id] = {
            "id": execution.id,
            "strategy_id": execution.strategy_id,
            "strategy_name": execution.strategy_name,
            "symbol": execution.symbol,
            "timeframe": execution.timeframe,
            "status": execution.status,
            "progress": execution.progress,
            "start_time": execution.start_time,
            "orders": [],
            "trades": [],
            "metrics": {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0
            }
        }
    
    def get_execution_status(self, execution_id):
        """Get current status of an execution."""
        if execution_id not in self.executions:
            return None
        
        execution = self.executions[execution_id]
        
        # Simulate progress updates
        if execution["status"] == "running":
            execution["progress"] = min(1.0, execution["progress"] + random.uniform(0.01, 0.05))
            
            # Randomly complete or fail execution
            if execution["progress"] >= 1.0:
                execution["status"] = "completed" if random.random() > 0.2 else "failed"
                
                # Generate some random metrics if completed
                if execution["status"] == "completed":
                    execution["metrics"] = {
                        "total_trades": random.randint(10, 100),
                        "win_rate": random.uniform(0.4, 0.7),
                        "profit_factor": random.uniform(1.1, 2.5),
                        "sharpe_ratio": random.uniform(0.8, 2.2),
                        "max_drawdown": random.uniform(0.05, 0.2)
                    }
        
        return {
            "status": execution["status"],
            "progress": execution["progress"],
            "metadata": {"metrics": execution["metrics"]}
        }
    
    def get_execution_details(self, execution_id):
        """Get detailed information about an execution."""
        if execution_id not in self.executions:
            return None
        
        execution = self.executions[execution_id]
        
        # Generate some dummy order and trade data
        if not execution["orders"]:
            num_orders = random.randint(5, 15)
            for i in range(num_orders):
                execution["orders"].append({
                    "id": f"order_{execution_id}_{i}",
                    "symbol": execution["symbol"],
                    "type": random.choice(["market", "limit", "stop"]),
                    "side": random.choice(["buy", "sell"]),
                    "quantity": random.uniform(0.1, 2.0),
                    "price": random.uniform(100, 500),
                    "status": random.choice(["filled", "partial", "cancelled", "rejected", "pending"])
                })
            
            num_trades = random.randint(3, 10)
            for i in range(num_trades):
                execution["trades"].append({
                    "id": f"trade_{execution_id}_{i}",
                    "symbol": execution["symbol"],
                    "entry_time": execution["start_time"] + random.uniform(60, 3600),
                    "exit_time": execution["start_time"] + random.uniform(3600, 7200),
                    "entry_price": random.uniform(100, 500),
                    "exit_price": random.uniform(100, 500),
                    "quantity": random.uniform(0.1, 2.0),
                    "pnl": random.uniform(-500, 1000),
                    "pnl_percent": random.uniform(-5, 10)
                })
        
        return {
            "orders": execution["orders"],
            "trades": execution["trades"],
            "metrics": execution["metrics"]
        }


def simulate_dashboard_activity(controller, data_provider):
    """
    Simulate dashboard activity for demonstration purposes.
    
    Args:
        controller: Dashboard controller instance.
        data_provider: Execution data provider.
    """
    # Register some simulated executions
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
    strategies = list(data_provider.strategies.keys())
    
    # Add a few executions
    for i in range(3):
        strategy_id = random.choice(strategies)
        strategy_info = data_provider.get_strategy(strategy_id)
        
        execution_id = controller.add_execution(
            strategy_id=strategy_id,
            strategy_name=strategy_info["name"],
            symbol=random.choice(symbols),
            timeframe=random.choice(timeframes),
            strategy_type=strategy_info["type"]
        )
        
        # Register with data provider
        execution = controller.state.active_executions[execution_id]
        data_provider.register_execution(execution)
    
    # Simulate view changes
    time.sleep(2)
    controller.change_view(ViewType.EXECUTION)
    
    # Add some notifications
    time.sleep(1)
    controller.add_notification(
        level="info",
        source="System",
        message="Dashboard demonstration initialized"
    )
    
    time.sleep(1)
    controller.add_notification(
        level="warning",
        source="Risk Management",
        message="Daily risk limit approaching 80% utilization"
    )
    
    # Select a random execution
    if controller.state.active_executions:
        random_exec_id = random.choice(list(controller.state.active_executions.keys()))
        controller.select_execution(random_exec_id)
    
    # Add error notification
    time.sleep(2)
    controller.add_notification(
        level="error",
        source="Data Service",
        message="Connection to market data provider interrupted"
    )
    
    # Update filters
    controller.update_filters(
        symbol="AAPL",
        timeframe="1h"
    )
    
    # Let the simulation run for a while
    time.sleep(5)


def run_dashboard_example():
    """Run the dashboard example."""
    # Create dashboard configuration with custom settings
    config = DashboardConfig()
    config.dashboard_title = "Instinct AI Trading System - Demo"
    config.theme = DashboardTheme.DARK
    config.layout_type = LayoutType.STANDARD
    
    # Initialize controller
    controller = DashboardController(config)
    
    # Create data providers
    strategy_provider = DummyStrategyDataProvider()
    execution_provider = DummyExecutionDataProvider()
    
    # Register data providers with controller
    controller.register_data_provider("strategy", strategy_provider)
    controller.register_data_provider("execution", execution_provider)
    
    # Start controller
    controller.start()
    
    try:
        # Print dashboard status
        logger.info(f"Dashboard initialized: {config.dashboard_title}")
        logger.info(f"Theme: {config.theme.value}, Layout: {config.layout_type.value}")
        
        # Run simulation
        logger.info("Starting dashboard simulation...")
        simulate_dashboard_activity(controller, strategy_provider)
        
        # Run for a while to let things happen
        for i in range(30):
            num_active = controller.state.get_active_execution_count()
            num_notifications = len(controller.state.notifications)
            unread = controller.state.unread_notification_count
            
            logger.info(f"Status: {num_active} active executions, "
                       f"{num_notifications} notifications ({unread} unread)")
            
            # Every 5 seconds, add a new notification
            if i % 5 == 0:
                level = random.choice(["info", "warning", "error"])
                source = random.choice(["System", "Execution", "Strategy", "Risk", "Data"])
                controller.add_notification(
                    level=level,
                    source=source,
                    message=f"Random {level} message from {source} at {datetime.now().strftime('%H:%M:%S')}"
                )
            
            # Every 10 seconds, add a new execution
            if i % 10 == 0 and i > 0:
                strategy_id = random.choice(list(strategy_provider.strategies.keys()))
                strategy_info = strategy_provider.get_strategy(strategy_id)
                
                execution_id = controller.add_execution(
                    strategy_id=strategy_id,
                    strategy_name=strategy_info["name"],
                    symbol=random.choice(["BTC", "ETH", "SOL", "DOT", "ADA"]),
                    timeframe=random.choice(["1m", "5m", "15m", "1h"]),
                    strategy_type=strategy_info["type"]
                )
                
                execution = controller.state.active_executions[execution_id]
                execution_provider.register_execution(execution)
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Example interrupted by user.")
    finally:
        # Stop controller
        controller.stop()
        logger.info("Dashboard example completed.")


if __name__ == "__main__":
    run_dashboard_example() 