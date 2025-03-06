# Instinct AI Trading Dashboard

A comprehensive trading dashboard for cryptocurrency market analysis, strategy performance tracking, and automated trading.

## Features

- **Real-time Market Monitoring**: Track prices, volumes, and market regimes across multiple cryptocurrencies
- **Strategy Performance Tracking**: Monitor the performance of your trading strategies in real-time
- **User Authentication**: Secure access with role-based permissions
- **API Key Management**: Securely store and manage exchange API keys
- **Technical Analysis**: View price charts with multiple indicators and timeframes
- **Market Insights**: Correlation analysis, volume profiles, and market regime detection
- **Alerts System**: Get notified about significant market events and strategy signals

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

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Initialize the dashboard:
   ```
   python advanced_trading/run_secured_dashboard.py --init-admin
   ```
   This will start the dashboard and create an admin user. The console will display the generated password.

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

#### Available Options

- `--port`: Port to run the dashboard on (default: 8050)
- `--host`: Host to run the dashboard on (default: 0.0.0.0)
- `--debug`: Run in debug mode
- `--init-admin`: Initialize admin user with default credentials
- `--admin-user`: Admin username (when using --init-admin)
- `--admin-pass`: Admin password (when using --init-admin)
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--no-auth`: Run dashboard without authentication (not recommended)

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
├── utils/                  # Utility modules
│   ├── market_monitor.py   # Market monitoring functionality
│   └── ...
├── run_dashboard.py        # Original dashboard runner
├── run_secured_dashboard.py # Secured dashboard runner
├── docs/                   # Documentation
└── README.md               # This file
```

## Authentication System

The dashboard includes a comprehensive authentication system with:

- User registration and login
- Role-based access control (admin, analyst, trader)
- API key management with encryption
- Token-based authentication with expiry
- Password hashing for security

### Default Login

After initializing with `--init-admin`:
- Username: admin
- Password: [Generated and displayed in console]

## Market Monitor

The market monitor component continuously tracks:

- Price and volume data for multiple cryptocurrencies
- Market regimes and significant events
- Trading strategy performance
- Correlations between assets

## Customization

### Adding New Symbols

Edit the configuration or pass symbols when initializing:

```python
from dashboard.data_manager import init_market_monitor

init_market_monitor({
    "symbols": ["BTC/USDT", "ETH/USDT", "ADA/USDT", "DOT/USDT", "SOL/USDT"],
    # other configuration...
})
```

### Adding Trading Strategies

1. Implement your strategy
2. Register it with the market monitor
3. Update the configuration to include your strategy ID

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Dash](https://dash.plotly.com/) - The web framework used
- [Plotly](https://plotly.com/python/) - Interactive visualization library
- [ccxt](https://github.com/ccxt/ccxt) - Cryptocurrency exchange trading library 