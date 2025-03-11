# Unified Dashboard for Instinct AI Trading System

The Unified Dashboard provides a comprehensive, single-operator interface for controlling and monitoring all aspects of the Instinct AI Trading System.

## Overview

This dashboard is designed to be a command center for trading operations, integrating all system components into a cohesive interface that allows a single operator to manage the entire trading pipeline efficiently. It eliminates the need to switch between different interfaces or tools by providing a centralized control point for all trading activities.

## Components

The dashboard consists of the following main components:

### Core Components

- **Configuration (`DashboardConfig`)**: Manages dashboard settings, panel layouts, and user preferences
- **State (`DashboardState`)**: Tracks the runtime state of the dashboard, including active executions, view selections, and notifications
- **Controller (`DashboardController`)**: Coordinates operations between components and handles user interactions

### Panels

The dashboard includes specialized panels for different aspects of the trading system:

- **Strategy Management Panel**: Select, configure, and manage trading strategies
- **Execution Panel**: Monitor and control active strategy executions
- **Backtesting Panel**: Run and analyze strategy backtests
- **Risk Management Panel**: Monitor risk metrics and set limits
- **Performance Analytics Panel**: View performance metrics and analytics
- **System Administration Panel**: Configure and monitor system settings

## Architecture

The Unified Dashboard follows a modular architecture:

```
dashboard/
├── core/               # Core dashboard framework
│   ├── config.py       # Configuration management
│   ├── state.py        # State tracking
│   └── controller.py   # Central controller
├── panels/             # Specialized dashboard panels
├── views/              # Visualization components
├── widgets/            # Reusable UI components
└── examples/           # Example implementations
```

The dashboard uses an event-driven architecture where components communicate through events registered with the central controller. This allows for loose coupling between components and easy extensibility.

## Key Features

- **Single Operator Design**: Optimized for a single user experience with intuitive controls
- **Unified Interface**: Integrates all system components in one place
- **Real-time Monitoring**: Live updates for executions, performance, and risk metrics
- **Centralized Control**: Execute operations across different components from one interface
- **Customizable Layout**: Configurable panel positions and sizes to suit operator preferences
- **Advanced Notifications**: Multi-level notification system for system events

## Usage

### Basic Setup

```python
from advanced_trading.dashboard.core import DashboardConfig, DashboardController

# Create and configure the dashboard
config = DashboardConfig()
config.dashboard_title = "Instinct AI Trading System"

# Initialize the controller
controller = DashboardController(config)

# Register required data providers and services
controller.register_data_provider("strategy", strategy_provider)
controller.register_data_provider("execution", execution_provider)

# Start the dashboard controller
controller.start()
```

### Handling Executions

```python
# Start a new strategy execution
execution_id = controller.add_execution(
    strategy_id="moving_avg_crossover",
    strategy_name="Moving Average Crossover",
    symbol="AAPL",
    timeframe="1h"
)

# Update execution status
controller.update_execution_status(
    execution_id=execution_id,
    status="running",
    progress=0.5
)
```

### Working with Notifications

```python
# Add a notification
controller.add_notification(
    level="warning",
    source="Risk Management",
    message="Position size exceeds daily limit"
)

# Mark notifications as read
controller.mark_all_notifications_read()
```

## Configuration Options

The dashboard can be configured with various options:

- **Themes**: Choose between dark, light, or high-contrast themes
- **Layout Types**: Standard, grid, tabs, or compact layouts available
- **Panel Settings**: Configure position, size, and refresh intervals for each panel
- **Feature Flags**: Enable or disable specific dashboard features

## For Developers

When extending the dashboard:

1. Use the event system to communicate between components
2. Register new data providers with the controller
3. Follow the panel interface for creating new panels
4. Use the widget library for consistent UI elements

## Examples

The `examples` directory contains sample implementations that demonstrate how to use the dashboard:

- `dashboard_example.py`: A complete example of setting up and using the dashboard

## Future Enhancements

- Integration with external notification systems
- Customizable dashboard themes
- Mobile-friendly responsive design
- Advanced data visualization components
- User preference profiles 