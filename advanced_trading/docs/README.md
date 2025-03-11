# Instinct AI System Overview

*Note: For detailed dashboard documentation, please see [DASH_READ.md](DASH_READ.md) and [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md).*

A comprehensive trading dashboard and system for cryptocurrency market analysis, strategy performance tracking, and automated trading.

## Features

- **Real-time Market Monitoring**: Track prices, volumes, and market regimes across multiple cryptocurrencies
- **Strategy Performance Tracking**: Monitor the performance of your trading strategies in real-time
- **User Authentication**: Secure access with role-based permissions
- **API Key Management**: Securely store and manage exchange API keys
- **Technical Analysis**: View price charts with multiple indicators and timeframes
- **Market Insights**: Correlation analysis, volume profiles, and market regime detection
- **Alerts System**: Get notified about significant market events and strategy signals
- **Execution Optimization**: Intelligent order routing, order type selection, and execution strategies
- **Market Microstructure Analysis**: Deep analysis of order books, trade flow, and liquidity profiles

## Execution Framework

The Instinct AI System includes a comprehensive execution optimization framework that improves trade execution quality through three key components:

1. **Smart Order Router**: Determines the optimal exchange(s) to route orders based on liquidity, fees, and performance metrics
2. **Order Type Optimizer**: Selects the optimal order type and parameters based on market conditions and execution preferences
3. **Execution Strategies**: Controls when and how to execute orders over time to minimize market impact and optimize execution price

### Available Execution Strategies

- **Basic Execution Strategy**: Immediate execution for small orders with minimal market impact
- **TWAP (Time-Weighted Average Price)**: Splits orders into equal-sized chunks executed at regular time intervals
- **VWAP (Volume-Weighted Average Price)**: Splits orders according to expected volume distribution to match VWAP benchmark
- **Adaptive Strategy**: Dynamically adjusts execution schedule based on real-time market conditions, volatility, and price movements

For examples of how to use these strategies, see `advanced_trading/execution/optimization/examples/execution_strategies_example.py`.

## Execution Safety Framework

The Execution Safety Framework provides comprehensive protection mechanisms for the trading system during execution. It consists of three main components:

### Circuit Breakers

Circuit breakers monitor trading conditions and automatically halt trading when certain thresholds are exceeded. They help prevent catastrophic losses during extreme market conditions.

```python
from advanced_trading.execution.safety import VolatilityCircuitBreaker, DrawdownCircuitBreaker

# Create a volatility circuit breaker
volatility_breaker = VolatilityCircuitBreaker(
    name="btc_volatility_breaker",
    symbol="BTC/USDT",
    lookback_periods=10,
    volatility_threshold=0.05,  # 5% volatility
    cooldown_periods=30
)

# Create a drawdown circuit breaker
drawdown_breaker = DrawdownCircuitBreaker(
    name="portfolio_drawdown_breaker",
    max_drawdown_percent=8.0,  # 8% drawdown
    reference_value="portfolio_equity",
    cooldown_minutes=60
)
```

### Emergency Protocols

Emergency protocols provide a structured way to handle critical situations during trading. They define a hierarchy of emergency levels and associated actions.

```python
from advanced_trading.execution.safety import EmergencyHandler, EmergencyProtocol, EmergencyLevel

# Create an emergency handler
emergency_handler = EmergencyHandler()

# Create and register an emergency protocol
liquidation_protocol = EmergencyProtocol(
    name="liquidation_risk_protocol",
    description="Protocol for handling potential liquidation scenarios"
)
emergency_handler.register_protocol(liquidation_protocol)

# Create an emergency event
event = emergency_handler.create_event(
    level=EmergencyLevel.CRITICAL,
    source="risk_monitor",
    description="Portfolio drawdown exceeding 15%",
    affected_components=["portfolio_manager", "execution_system"],
    requires_acknowledgment=True
)

# Handle the emergency event
results = emergency_handler.handle_event(event)
```

### Protection Components

Protection components monitor execution for failures and anomalies, and take appropriate actions to mitigate issues:

```python
from advanced_trading.execution.safety import (
    TradingProtection, ExecutionFailureType, ExecutionAnomalyType,
    PauseExchangeTradingAction, RateThrottlingAction
)

# Create a trading protection system
protection = TradingProtection()

# Register protection actions
pause_action = PauseExchangeTradingAction()
throttle_action = RateThrottlingAction(throttle_factor=0.5)
protection.register_protection_action(pause_action)
protection.register_protection_action(throttle_action)

# Configure failure protection
protection.configure_failure_protection(
    ExecutionFailureType.CONNECTION_ERROR, 
    pause_action.name
)
protection.configure_failure_protection(
    ExecutionFailureType.RATE_LIMIT, 
    throttle_action.name
)

# Report and handle a failure
result = protection.report_failure(
    failure_type=ExecutionFailureType.RATE_LIMIT,
    exchange_id="binance",
    error_message="Rate limit exceeded",
    symbol="BTC/USDT"
)

# Monitor for anomalies
anomaly_result = protection.check_metric(
    exchange_id="binance",
    symbol="BTC/USDT",
    metric="order_latency_ms",
    value=500.0,
    anomaly_type=ExecutionAnomalyType.UNUSUAL_LATENCY
)
```

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Required packages:
  - dash
  - plotly
  - pandas
  - numpy
  - flask
  - PyJWT

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/instinct_ai.git
   cd instinct_ai
   ```

2. Install dependencies using the installation script:
   ```
   bash advanced_trading/install_dashboard.sh
   ```

3. For detailed installation instructions, see [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)

### Usage

#### Running the Dashboard

Basic usage:
```
python advanced_trading/run_secured_dashboard.py
```

With custom options:
```
python advanced_trading/run_secured_dashboard.py --port=8080 --host=localhost --debug --log-level=DEBUG
```

#### Using Execution Strategies

```python
from advanced_trading.execution.optimization import (
    ExecutionRequest, TWAPStrategy, VWAPStrategy, AdaptiveStrategy
)

# Create an execution request
request = ExecutionRequest(
    id="order_1",
    symbol="BTC/USD",
    side="buy",
    size=1.0,
    start_time=time.time(),
    end_time=time.time() + 3600  # Execute over 1 hour
)

# Create a TWAP strategy
twap = TWAPStrategy(min_chunks=10, max_chunks=20)

# Create an execution schedule
schedule = twap.create_execution_schedule(request)

# Get next actions to take (sub-orders to execute)
next_actions = twap.get_next_actions(schedule)

# Update order status when filled
twap.update_order_status(sub_order_id="order_1_0", status="filled", filled_price=10000.0)
```

## Project Structure

```
advanced_trading/
├── dashboard/              # Dashboard components
│   ├── app.py              # Original dashboard
│   ├── secured_app.py      # Secured dashboard with authentication
│   ├── auth.py             # Authentication management
│   ├── auth_middleware.py  # Authentication middleware for Dash
│   ├── components.py       # UI components
│   ├── data_manager.py     # Data management and caching
│   ├── layout_manager.py   # Layout components and theming
│   ├── market_data_handler.py # Market data handling
│   └── assets/             # CSS and other static assets
├── execution/              # Execution framework components
│   ├── optimization/       # Execution optimization
│   │   ├── profiles/       # Exchange profiling and capabilities
│   │   ├── routers/        # Smart order routing
│   │   ├── order_types/    # Order type optimization
│   │   ├── strategies/     # Execution strategies
│   │   └── examples/       # Usage examples
├── microstructure/         # Market microstructure analysis
│   ├── order_book/         # Order book analysis
│   ├── order_flow/         # Order flow analysis
│   └── liquidity/          # Liquidity analysis
├── utils/                  # Utility modules
│   ├── market_monitor.py   # Market monitoring functionality
│   └── ...
├── docs/                   # Documentation
│   ├── DASH_READ.md        # Dashboard documentation
│   ├── INSTALLATION_GUIDE.md # Installation troubleshooting
│   └── DASHBOARD_PLAN.md   # Development roadmap
├── run_dashboard.py        # Original dashboard runner
├── run_secured_dashboard.py # Secured dashboard runner
└── install_dashboard.sh    # Installation script
```

## Development Plan

For details on the current implementation status and future plans, see [DASHBOARD_PLAN.md](DASHBOARD_PLAN.md).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Dash](https://dash.plotly.com/) - The web framework used
- [Plotly](https://plotly.com/python/) - Interactive visualization library
- [ccxt](https://github.com/ccxt/ccxt) - Cryptocurrency exchange trading library 