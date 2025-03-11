# Instinct AI API

The Instinct AI API provides a comprehensive interface for interacting with the Instinct AI trading platform. It includes both REST and WebSocket endpoints for real-time data streaming, order execution, strategy management, and more.

## Architecture

The API is built using FastAPI and follows a modular architecture:

```
api/
├── auth/                  # Authentication modules
│   ├── api_key.py         # API key authentication
│   ├── dependencies.py    # Authentication dependencies
│   ├── jwt.py             # JWT authentication
│   └── __init__.py
├── rest/                  # REST API components
│   ├── app.py             # FastAPI application factory
│   ├── config.py          # API configuration
│   ├── routers/           # API routers
│   │   ├── auth.py        # Authentication endpoints
│   │   ├── backtest.py    # Backtest management endpoints
│   │   ├── data.py        # Data retrieval endpoints
│   │   ├── execution.py   # Order execution endpoints
│   │   ├── strategies.py  # Strategy management endpoints
│   │   └── __init__.py
│   └── __init__.py
├── websocket/             # WebSocket components
│   ├── handlers.py        # WebSocket connection handlers
│   ├── server.py          # WebSocket server
│   └── __init__.py
├── main.py                # API entry point
├── version.py             # API version information
└── __init__.py
```

## Features

- **Authentication**: Supports both JWT and API key authentication
- **REST API**: Comprehensive REST API for all platform functionality
- **WebSocket API**: Real-time data streaming and notifications
- **OpenAPI Documentation**: Auto-generated API documentation
- **Configuration**: Flexible configuration via environment variables

## REST API Endpoints

The REST API provides the following endpoint groups:

- **Authentication**: User login, registration, token refresh
- **Data**: Market data retrieval, historical data, reference data
- **Execution**: Order placement, order management, execution analysis
- **Strategies**: Strategy management, parameters, performance
- **Backtesting**: Backtest creation, management, and results

## WebSocket API

The WebSocket API provides real-time data streaming for:

- Market data updates
- Order status changes
- Strategy signals
- System notifications

## Authentication

The API supports two authentication methods:

1. **JWT Authentication**: For user sessions and web applications
2. **API Key Authentication**: For programmatic access and integrations

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

Or using the module:

```python
from advanced_trading.api.main import main

if __name__ == "__main__":
    main()
```

## API Documentation

When the API is running, you can access the auto-generated documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Versioning

The API supports versioning to ensure backward compatibility as the API evolves:

- `/api/v1/...` - Version 1 endpoints (stable)
- `/api/...` - Latest version endpoints (may change)

For production use, it's recommended to use the versioned endpoints to ensure stability.

### Example URLs:

- Version 1: `http://localhost:8000/api/v1/strategies`
- Latest version: `http://localhost:8000/api/strategies` 