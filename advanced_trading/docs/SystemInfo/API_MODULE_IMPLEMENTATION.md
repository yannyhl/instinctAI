# API Module Implementation

## Overview

The API module provides a comprehensive interface for interacting with the Instinct AI trading platform. It includes both REST and WebSocket endpoints for real-time data streaming, order execution, strategy management, and more.

## Architecture

The API follows a modular architecture with clear separation of concerns:

- **REST API**: Provides HTTP endpoints for platform functionality
- **WebSocket API**: Enables real-time data streaming and notifications
- **Authentication**: Supports JWT and API key authentication
- **Configuration**: Offers flexible configuration via environment variables

## Components

### 1. Core Components

- **`main.py`**: Entry point for the API server
- **`version.py`**: Version information
- **`README.md`**: Documentation

### 2. REST API

- **`rest/app.py`**: FastAPI application factory
- **`rest/config.py`**: Configuration classes
- **`rest/routes.py`**: API versioning and route definitions

#### Routers

- **`rest/routers/auth.py`**: Authentication endpoints
- **`rest/routers/strategies.py`**: Strategy management
- **`rest/routers/data.py`**: Data retrieval
- **`rest/routers/execution.py`**: Order execution
- **`rest/routers/backtest.py`**: Backtest management

### 3. WebSocket API

- **`websocket/server.py`**: WebSocket server implementation
- **`websocket/handlers.py`**: Connection handlers

### 4. Authentication

- **`auth/jwt.py`**: JWT authentication service
- **`auth/api_key.py`**: API key authentication service
- **`auth/dependencies.py`**: FastAPI dependencies for authentication

## API Endpoints

### REST API

The API is versioned to ensure backward compatibility:

- `/api/v1/...`: Version 1 endpoints (stable)
- `/api/...`: Latest version endpoints

Key endpoints include:

1. **Authentication**
   - `POST /api/auth/login`: Authenticate a user and get a JWT token
   - `POST /api/auth/users`: Create a new user
   - `POST /api/auth/api-keys`: Generate a new API key
   - `DELETE /api/auth/api-keys/{api_key}`: Revoke an API key
   - `GET /api/auth/me`: Get current user information

2. **Strategy Management**
   - `GET /api/strategies/available`: Get available strategy definitions
   - `POST /api/strategies`: Create a new strategy
   - `GET /api/strategies`: List strategies
   - `GET /api/strategies/{strategy_id}`: Get a specific strategy
   - `POST /api/strategies/{strategy_id}/action`: Perform an action on a strategy
   - `DELETE /api/strategies/{strategy_id}`: Delete a strategy

3. **Data Retrieval**
   - `GET /api/data/sources`: Get available data sources
   - `GET /api/data/sources/{source_id}`: Get information about a specific data source
   - `GET /api/data/time-series/{source_id}/{symbol}`: Get time series data

4. **Order Execution**
   - `POST /api/execution/orders`: Create a new order
   - `GET /api/execution/orders`: List orders
   - `GET /api/execution/orders/{order_id}`: Get a specific order
   - `DELETE /api/execution/orders/{order_id}`: Cancel an order
   - `GET /api/execution/orders/{order_id}/fills`: Get fills for a specific order

5. **Backtesting**
   - `POST /api/backtest`: Create a new backtest
   - `GET /api/backtest`: List backtests
   - `GET /api/backtest/{backtest_id}`: Get a specific backtest
   - `DELETE /api/backtest/{backtest_id}`: Cancel a backtest

### WebSocket API

The WebSocket API provides two main endpoints:

1. **`/ws`**: Public WebSocket endpoint for unauthenticated connections
2. **`/ws/auth`**: Authenticated WebSocket endpoint requiring JWT token

WebSocket messages follow a standardized format with topics for subscription:

- `market.data.{symbol}`: Market data updates
- `orders.status`: Order status updates
- `strategy.signals.{strategy_id}`: Strategy signals
- `system.notifications`: System notifications

## Authentication

The API supports two authentication methods:

1. **JWT Authentication**: For user sessions and web applications
   - Tokens are issued via `/api/auth/login`
   - Tokens contain user ID, email, role, and scopes
   - Tokens expire after a configurable period

2. **API Key Authentication**: For programmatic access
   - Keys are issued via `/api/auth/api-keys`
   - Keys can be revoked via `/api/auth/api-keys/{api_key}`
   - Keys are associated with specific users and permissions

## Configuration

The API can be configured using environment variables:

- `API_HOST`: Host to bind the API server (default: 0.0.0.0)
- `API_PORT`: Port to bind the API server (default: 8000)
- `DEBUG`: Enable debug mode (default: false)
- `JWT_SECRET`: Secret key for JWT token signing
- `JWT_ALGORITHM`: Algorithm for JWT token signing (default: HS256)
- `JWT_EXPIRATION`: JWT token expiration in seconds (default: 3600)
- `CORS_ORIGINS`: Comma-separated list of allowed origins for CORS
- `CORS_METHODS`: Comma-separated list of allowed methods for CORS
- `CORS_HEADERS`: Comma-separated list of allowed headers for CORS
- `CORS_CREDENTIALS`: Whether to allow credentials for CORS (default: true)

## Running the API

To run the API:

```bash
# Set environment variables
export JWT_SECRET="your-secret-key"
export DEBUG=true

# Run the API
python -m advanced_trading.api.main
```

## Documentation

When the API is running, auto-generated documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Future Enhancements

Planned future enhancements for the API include:

1. **Rate Limiting**: Implement more sophisticated rate limiting
2. **Caching**: Add response caching for frequently accessed data
3. **Webhooks**: Support for webhook notifications for events
4. **Batch Operations**: Support for batch operations on resources
5. **Advanced Authentication**: OAuth2 support, MFA, and role-based access control
6. **API Metrics**: Detailed metrics on API usage and performance 