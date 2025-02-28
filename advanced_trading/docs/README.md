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