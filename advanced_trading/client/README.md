# Instinct AI Client SDK

This package provides a Python client SDK for interacting with the Instinct AI trading platform API.

## Installation

```bash
# Assuming you have the Instinct AI trading platform installed
pip install -e .
```

## Quick Start

```python
from advanced_trading.client import ApiClient

# Create API client
client = ApiClient(
    base_url="http://localhost:8000",
    api_version="v1"
)

# Initialize client components
client._initialize_clients()

# Authenticate
login_response = client.auth.login(
    username="your_username",
    password="your_password"
)

# Access the API token
token = login_response["access_token"]
print(f"Token: {token}")

# Get available strategies
strategies = client.strategies.get_available_strategies()
print(f"Available strategies: {len(strategies)}")
for strategy in strategies:
    print(f"- {strategy['name']}: {strategy['description']}")
```

## Authentication

The client supports both JWT and API key authentication:

```python
# With JWT token
client = ApiClient(
    base_url="http://localhost:8000",
    token="your_jwt_token"
)

# With API key
client = ApiClient(
    base_url="http://localhost:8000",
    api_key="your_api_key"
)
```

You can also authenticate after creating the client:

```python
client = ApiClient(base_url="http://localhost:8000")
client._initialize_clients()

# Login and get token
login_response = client.auth.login(
    username="your_username",
    password="your_password"
)
```

## Components

The client SDK provides specialized clients for different API components:

- `client.auth`: Authentication and user management
- `client.strategies`: Strategy management
- `client.data`: Data retrieval
- `client.execution`: Order execution
- `client.backtest`: Backtest management

### Authentication Client

```python
# Login
login_response = client.auth.login(
    username="your_username",
    password="your_password"
)

# Get current user
user = client.auth.get_current_user()

# Create API key
api_key_response = client.auth.create_api_key(user["id"])

# Revoke API key
client.auth.revoke_api_key(api_key_response["api_key"])
```

### Strategies Client

```python
# Get available strategies
strategies = client.strategies.get_available_strategies()

# Create a strategy
strategy = client.strategies.create_strategy(
    name="My Strategy",
    type="trend_following",
    symbols=["BTC/USD"],
    timeframe="1h",
    parameters={
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9
    }
)

# Get strategy details
strategy_details = client.strategies.get_strategy(strategy["id"])

# Start strategy
client.strategies.start_strategy(strategy["id"])

# Stop strategy
client.strategies.stop_strategy(strategy["id"])

# Delete strategy
client.strategies.delete_strategy(strategy["id"])
```

### Data Client

```python
# Get data sources
sources = client.data.get_data_sources()

# Get data source details
source = client.data.get_data_source(sources[0]["id"])

# Get time series data
from datetime import datetime, timedelta

end_time = datetime.now()
start_time = end_time - timedelta(days=1)

data = client.data.get_time_series_data(
    source_id=source["id"],
    symbol=source["symbols"][0],
    start_time=start_time,
    end_time=end_time,
    frequency="1h"
)
```

### Execution Client

```python
# Create a market buy order
order = client.execution.market_buy(
    symbol="BTC/USD",
    quantity=0.1
)

# Create a limit sell order
order = client.execution.limit_sell(
    symbol="BTC/USD",
    quantity=0.1,
    price=50000.0
)

# Get order details
order_details = client.execution.get_order(order["id"])

# Cancel order
client.execution.cancel_order(order["id"])

# Get order fills
fills = client.execution.get_order_fills(order["id"])
```

### Backtest Client

```python
# Create a backtest
backtest = client.backtest.create_backtest(
    strategy_id=strategy["id"],
    start_date=datetime(2022, 1, 1),
    end_date=datetime(2022, 12, 31),
    symbols=["BTC/USD"],
    initial_capital=100000.0,
    parameters={
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9
    }
)

# Get backtest details
backtest_details = client.backtest.get_backtest(backtest["id"])

# Cancel backtest
client.backtest.cancel_backtest(backtest["id"])
```

## WebSocket Support

The client SDK also supports WebSocket connections for real-time data:

```python
# Create WebSocket connection
ws = client.create_websocket_connection(authenticated=True)

# Define custom message handler
def on_message(ws, message):
    print(f"Received: {message}")

# Override message handler
ws.on_message = on_message

# Start connection in a separate thread
import threading
ws_thread = threading.Thread(target=ws.run_forever)
ws_thread.daemon = True
ws_thread.start()

# Send a subscription message
ws.send('{"action": "subscribe", "topics": ["market.data.BTC/USD"]}')

# Later, close the connection
ws.close()
```

## Error Handling

The client SDK raises standard Python exceptions for errors:

```python
from requests.exceptions import RequestException

try:
    client.strategies.get_strategy("non-existent-id")
except RequestException as e:
    print(f"Request error: {e}")
```

## Configuration

The client SDK can be configured with various options:

```python
client = ApiClient(
    base_url="http://localhost:8000",
    api_version="v1",
    token=None,
    api_key=None,
    timeout=30,
    verify_ssl=True,
    proxies=None
)
```

## Complete Example

See the `advanced_trading/examples/api_client_example.py` file for a complete example of using the client SDK. 