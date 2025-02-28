# Instinct AI API Integration Guide

This document provides comprehensive information on integrating Instinct AI with external systems and cryptocurrency exchanges through API connections.

## Overview

Instinct AI offers multiple integration points for external systems, allowing seamless interaction with market data sources, exchange APIs, and third-party services.

### Integration Categories

1. **Exchange APIs**: Connect to cryptocurrency exchanges for data and trading
2. **API Services**: Expose Instinct AI functionality to external applications
3. **Data Source Integration**: Import data from external providers
4. **Notification Systems**: Send alerts to messaging platforms and services
5. **Custom Integrations**: Framework for building custom connectors

## Exchange Integrations

### Supported Exchanges

The system currently supports the following cryptocurrency exchanges:

| Exchange | API Version | Data Types | Trading | Features |
|----------|-------------|------------|---------|----------|
| Binance | V3 | OHLCV, Orderbook, Trades | ✓ | Spot, Futures, Margin |
| Coinbase | V3 | OHLCV, Orderbook, Trades | ✓ | Spot |
| Kraken | V2 | OHLCV, Orderbook, Trades | ✓ | Spot, Futures |
| FTX | V1 | OHLCV, Orderbook, Trades | ✓ | Spot, Futures, Options |
| Bybit | V2 | OHLCV, Orderbook, Trades | ✓ | Futures |

### Exchange API Configuration

To configure exchange APIs, you need to set up API keys and secrets:

```python
# In config.py or using environment variables
DATA_CONFIG = {
    "api_keys": {
        "binance": os.environ.get("BINANCE_API_KEY", ""),
        "binance_secret": os.environ.get("BINANCE_SECRET_KEY", ""),
        "coinbase": os.environ.get("COINBASE_API_KEY", ""),
        "coinbase_secret": os.environ.get("COINBASE_SECRET_KEY", ""),
        "kraken": os.environ.get("KRAKEN_API_KEY", ""),
        "kraken_secret": os.environ.get("KRAKEN_SECRET_KEY", "")
    }
}
```

### Security Best Practices

When working with exchange API keys:

1. **Set Appropriate Permissions**: Limit API keys to only the required permissions (read-only if not trading)
2. **Use IP Whitelisting**: Restrict API key access to specific IP addresses when possible
3. **Environment Variables**: Store sensitive credentials in environment variables, not in code
4. **Encryption**: Encrypt API secret keys at rest when stored
5. **Key Rotation**: Regularly rotate API keys to mitigate potential exposure risks

### Example: Connecting to Binance

```python
from data.data_loader import DataLoader

# Initialize data loader with Binance as primary source
data_loader = DataLoader(primary_source="binance")

# Load market data
btc_data = data_loader.load_data(
    symbol="BTC/USDT",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-02-01"
)

# Access account information (requires API key with appropriate permissions)
account_info = data_loader.get_account_info(exchange="binance")

# Place order (requires trading permissions)
order = data_loader.place_order(
    exchange="binance",
    symbol="BTC/USDT",
    order_type="limit",
    side="buy",
    amount=0.01,
    price=30000.0
)
```

## Instinct AI API Server

The Instinct AI system can expose its functionality through a RESTful API server, allowing external applications to access trading strategies, market data, and more.

### Setting Up the API Server

```bash
# Start the API server
python advanced_trading/api_server.py --port=5000 --host=0.0.0.0
```

### API Authentication

The API server uses JWT (JSON Web Token) authentication:

```python
# Example authentication request (Python client)
import requests
import json

response = requests.post(
    "http://localhost:5000/api/auth/login",
    json={"username": "admin", "password": "your_password"}
)

# Extract JWT token
token = response.json()["token"]

# Use token in subsequent requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:5000/api/market/data",
    headers=headers
)
```

### Available Endpoints

#### Authentication Endpoints

- `POST /api/auth/login`: Authenticate and receive JWT token
- `POST /api/auth/refresh`: Refresh an existing token
- `POST /api/auth/logout`: Invalidate current token

#### Market Data Endpoints

- `GET /api/market/data`: Get market data for specified symbols and timeframes
- `GET /api/market/summary`: Get market summary with key metrics
- `GET /api/market/regimes`: Get current market regime analysis
- `GET /api/market/correlation`: Get correlation matrix for specified symbols

#### Strategy Endpoints

- `GET /api/strategies`: List available strategies
- `GET /api/strategies/{strategy_id}`: Get strategy details and performance
- `POST /api/strategies/{strategy_id}/backtest`: Run strategy backtest
- `POST /api/strategies/{strategy_id}/enable`: Enable strategy for live trading
- `POST /api/strategies/{strategy_id}/disable`: Disable strategy

#### Trading Endpoints

- `GET /api/trading/positions`: Get current positions
- `GET /api/trading/orders`: Get active orders
- `POST /api/trading/orders`: Place new order
- `DELETE /api/trading/orders/{order_id}`: Cancel order

### API Rate Limiting

The API server implements rate limiting to prevent abuse:

- **Authenticated users**: 60 requests per minute
- **Anonymous users**: 10 requests per minute

Rate limit headers are included in API responses:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
X-RateLimit-Reset: 1635528000
```

### API Documentation

Full OpenAPI/Swagger documentation is available at the `/api/docs` endpoint when the server is running. This provides interactive documentation for all endpoints.

## WebSocket API

For real-time data and updates, Instinct AI provides a WebSocket API:

### Connecting to WebSocket

```javascript
// JavaScript client example
const socket = new WebSocket('ws://localhost:5001/ws');

socket.onopen = () => {
  // Subscribe to market data updates
  socket.send(JSON.stringify({
    action: 'subscribe',
    channel: 'market_data',
    symbols: ['BTC/USDT', 'ETH/USDT'],
    timeframe: '1m'
  }));
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received update:', data);
};
```

### Available WebSocket Channels

- `market_data`: Real-time market data updates
- `strategy_updates`: Strategy performance and signal updates
- `order_updates`: Order status changes
- `position_updates`: Position changes
- `alerts`: System alerts and notifications

## Notification Integrations

Instinct AI can send notifications to various platforms:

### Email Notifications

```python
# Configure email integration in config.py
NOTIFICATION_CONFIG = {
    "email": {
        "enabled": True,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "your_email@gmail.com",
        "sender_password": os.environ.get("EMAIL_PASSWORD")
    }
}

# Send notification from code
from utils.notification import send_notification

send_notification(
    channel="email",
    recipient="user@example.com",
    subject="Strategy Alert",
    message="BTC price dropped below support level",
    priority="high"
)
```

### Telegram Integration

```python
# Configure Telegram integration in config.py
NOTIFICATION_CONFIG = {
    "telegram": {
        "enabled": True,
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN"),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID")
    }
}

# Send notification from code
send_notification(
    channel="telegram",
    message="⚠️ Alert: BTC entered bearish regime",
    include_chart=True,
    chart_data={
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "periods": 24
    }
)
```

### Slack Integration

```python
# Configure Slack integration in config.py
NOTIFICATION_CONFIG = {
    "slack": {
        "enabled": True,
        "webhook_url": os.environ.get("SLACK_WEBHOOK_URL"),
        "channel": "#trading-alerts"
    }
}

# Send notification from code
send_notification(
    channel="slack",
    message="Strategy performance update",
    attachments=[
        {
            "title": "Weekly Performance",
            "text": "ML Ensemble: +2.3%\nStat Arb: +1.5%",
            "color": "#36a64f"
        }
    ]
)
```

## Custom Data Source Integration

You can integrate custom data sources with Instinct AI by implementing a data provider interface:

### Creating a Custom Data Provider

```python
from data.data_provider import BaseDataProvider

class CustomDataProvider(BaseDataProvider):
    """Custom data provider implementation."""
    
    def __init__(self, api_key=None, **kwargs):
        super().__init__(name="custom_provider", **kwargs)
        self.api_key = api_key
    
    def fetch_historical_data(self, symbol, timeframe, start_date, end_date):
        """Fetch historical data from custom source."""
        # Implementation to fetch data from your custom source
        # and return as pandas DataFrame with columns:
        # [timestamp, open, high, low, close, volume]
        
        return fetched_data_dataframe
    
    def fetch_orderbook(self, symbol, depth=10):
        """Fetch order book data from custom source."""
        # Implementation
        
    def fetch_trades(self, symbol, limit=100):
        """Fetch recent trades from custom source."""
        # Implementation

# Register the custom provider
from data.data_loader import register_data_provider
register_data_provider(CustomDataProvider)

# Use the custom provider
data_loader = DataLoader(primary_source="custom_provider", 
                         api_key="your_api_key")
```

## Database Integration

Instinct AI can integrate with various databases for data storage and retrieval:

### Supported Databases

- **SQLite**: Built-in support for lightweight, file-based SQL database
- **PostgreSQL**: Support for high-performance, scalable SQL database
- **MongoDB**: Support for flexible, document-based NoSQL database
- **InfluxDB**: Support for time-series optimized database

### Configuring Database Connection

```python
# Configure in config.py
DB_CONFIG = {
    "type": "postgresql",  # Options: sqlite, postgresql, mongodb, influxdb
    "connection": {
        "host": "localhost",
        "port": 5432,
        "database": "instinct_ai",
        "user": os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASSWORD")
    }
}
```

### Using Database Integration

```python
from utils.database import DatabaseManager

# Initialize database connection
db_manager = DatabaseManager()

# Store data
db_manager.store_market_data(
    symbol="BTC/USDT",
    timeframe="1h",
    data=btc_data
)

# Query data
query_result = db_manager.query(
    "SELECT * FROM strategy_performance WHERE strategy_id = ? AND date > ?",
    ["ml_ensemble", "2023-01-01"]
)

# Store and retrieve objects
db_manager.store_object("strategy_config", strategy_config)
retrieved_config = db_manager.get_object("strategy_config")
```

## Cloud Service Integration

Instinct AI supports integration with major cloud services:

### AWS Integration

```python
# Configure AWS integration
CLOUD_CONFIG = {
    "aws": {
        "enabled": True,
        "region": "us-east-1",
        "s3_bucket": "instinct-ai-data",
        "access_key": os.environ.get("AWS_ACCESS_KEY"),
        "secret_key": os.environ.get("AWS_SECRET_KEY")
    }
}

# Use S3 for data storage
from utils.cloud import CloudStorage

cloud_storage = CloudStorage(provider="aws")

# Store data in S3
cloud_storage.store_file(
    local_path="results/backtest_btc_20230101.json",
    remote_path="backtests/btc/20230101.json"
)

# Retrieve data from S3
cloud_storage.retrieve_file(
    remote_path="backtests/btc/20230101.json",
    local_path="downloaded_results.json"
)
```

### Google Cloud Integration

```python
# Configure Google Cloud integration
CLOUD_CONFIG = {
    "gcp": {
        "enabled": True,
        "project_id": "instinct-ai-project",
        "storage_bucket": "instinct-ai-data",
        "credentials_file": "path/to/credentials.json"
    }
}

# Use Cloud Storage
cloud_storage = CloudStorage(provider="gcp")

# Additional GCP services
from utils.cloud.gcp import BigQueryClient

bq_client = BigQueryClient()
query_result = bq_client.execute_query(
    "SELECT * FROM `project.dataset.market_data` WHERE symbol = 'BTC/USDT'"
)
```

## Webhook Integration

Instinct AI can both send and receive webhooks:

### Configuring Webhook Endpoints

```python
# Configure webhook receivers
WEBHOOK_CONFIG = {
    "receivers": [
        {
            "name": "strategy_signals",
            "endpoint": "/webhook/strategy_signals",
            "secret": os.environ.get("WEBHOOK_SECRET_1"),
            "handler": "utils.webhooks.handle_strategy_signal"
        }
    ],
    "senders": [
        {
            "name": "trading_events",
            "target_url": "https://example.com/receive-events",
            "secret": os.environ.get("WEBHOOK_SECRET_2"),
            "events": ["order_executed", "position_closed"]
        }
    ]
}
```

### Receiving Webhooks

```python
# Define webhook handler
def handle_strategy_signal(payload, request):
    """Handle incoming strategy signal webhook."""
    if "signal" in payload and "symbol" in payload:
        symbol = payload["symbol"]
        signal = payload["signal"]
        
        # Process signal
        logger.info(f"Received signal {signal} for {symbol}")
        
        # Trigger strategy or update
        if signal == "buy":
            # Execute buy logic
            pass
        
        return {"status": "success", "message": "Signal processed"}
    else:
        return {"status": "error", "message": "Invalid payload"}, 400
```

### Sending Webhooks

```python
from utils.webhooks import send_webhook

# Send webhook notification
send_webhook(
    webhook_name="trading_events",
    event="order_executed",
    payload={
        "order_id": "123456",
        "symbol": "BTC/USDT",
        "side": "buy",
        "price": 30000.0,
        "quantity": 0.1,
        "timestamp": "2023-06-15T12:34:56Z"
    }
)
```

## Integration with Machine Learning Frameworks

Instinct AI integrates with popular machine learning frameworks:

### TensorFlow Integration

```python
from strategies.ml.tensorflow_model import TensorFlowModel

# Create TensorFlow model
model = TensorFlowModel(
    input_shape=(30, 10),  # 30 time steps, 10 features
    lstm_units=64,
    dropout=0.2
)

# Train model
model.train(
    features_train=x_train,
    targets_train=y_train,
    validation_split=0.2,
    epochs=100,
    batch_size=32
)

# Generate predictions
predictions = model.predict(features_test)
```

### PyTorch Integration

```python
from strategies.ml.pytorch_model import PyTorchModel

# Create PyTorch model
model = PyTorchModel(
    input_size=10,
    hidden_size=64,
    output_size=1
)

# Train model
model.train(
    features_train=x_train,
    targets_train=y_train,
    validation_data=(x_val, y_val),
    epochs=100,
    batch_size=32
)

# Generate predictions
predictions = model.predict(features_test)
```

## API Security

Instinct AI implements several security measures for API integrations:

### API Key Security

- **Encryption**: All API keys are stored in encrypted format
- **Access Control**: Granular permissions for API key access
- **Audit Logging**: All API key usage is logged
- **Automatic Rotation**: Optional automatic API key rotation

### Secure Communication

- **HTTPS**: All API communication is encrypted with TLS
- **JWT Authentication**: Secure token-based authentication
- **IP Restrictions**: Optional IP-based access restrictions
- **Rate Limiting**: Protection against brute force attacks

### Implementing Secure API Requests

```python
import requests
import hmac
import hashlib
import time
import base64

def create_signature(secret_key, message):
    """Create HMAC signature for API request authentication."""
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def send_secure_api_request(url, method, api_key, secret_key, params=None):
    """Send a secure API request with authentication."""
    timestamp = str(int(time.time() * 1000))
    
    # Create message to sign
    message = timestamp + method + url.split('.com')[-1]
    if params:
        message += str(params)
    
    # Create signature
    signature = create_signature(secret_key, message)
    
    # Set headers
    headers = {
        'API-Key': api_key,
        'API-Timestamp': timestamp,
        'API-Signature': signature,
        'Content-Type': 'application/json'
    }
    
    # Send request
    if method == 'GET':
        response = requests.get(url, headers=headers, params=params)
    elif method == 'POST':
        response = requests.post(url, headers=headers, json=params)
    
    return response
```

## Troubleshooting Integration Issues

### Common API Issues

1. **Authentication Errors**
   - Problem: API key or signature invalid
   - Solution: Verify API key, secret, and signature generation

2. **Rate Limiting**
   - Problem: Too many requests to exchange API
   - Solution: Implement rate limiting and backoff strategies

3. **Data Consistency**
   - Problem: Inconsistent data across different sources
   - Solution: Use standardization and validation functions

4. **Connection Timeouts**
   - Problem: API requests timing out
   - Solution: Implement retry logic with exponential backoff

### Debugging Integration Code

```python
# Enable debug logging for API calls
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3').setLevel(logging.DEBUG)

# Trace API requests
from utils.api_monitoring import trace_api_calls

@trace_api_calls
def fetch_data_from_api():
    # Implementation
    
# Execute with tracing
result = fetch_data_from_api()

# Check response data
print(f"Status: {result.status_code}")
print(f"Headers: {result.headers}")
print(f"Content: {result.content[:100]}...")
```

## Conclusion

The Instinct AI system provides robust API integration capabilities, allowing seamless connection to exchanges, external data sources, and services. By following the guidelines in this document, you can securely and efficiently integrate the system with various external platforms to extend its functionality. 