# Instinct AI Trading Dashboard Documentation

## Overview

The Instinct AI Trading Dashboard is a comprehensive monitoring and management tool for cryptocurrency trading strategies. It provides real-time market data visualization, strategy performance tracking, and administrative features with robust security.

## Key Features

- **Real-time Market Monitoring**: Track prices, volumes, and market regimes across multiple cryptocurrencies
- **Strategy Performance Tracking**: Monitor the performance of trading strategies in real-time
- **Secure Authentication**: Role-based access control with user management
- **API Key Management**: Securely store and manage exchange API keys
- **Interactive Visualization**: Advanced charts for technical analysis and market insights
- **Responsive Design**: Optimized for both desktop and mobile devices

## Installation

### Prerequisites

- Python 3.8 or higher
- Required packages:
  - dash
  - plotly
  - pandas
  - numpy
  - flask
  - PyJWT

### Dependency Installation

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies using pip with --force-reinstall flag if needed
pip install dash plotly pandas numpy flask PyJWT --force-reinstall
```

If you encounter issues with package conflicts, try:

```bash
pip install --upgrade pip
pip install dash plotly pandas numpy flask PyJWT --ignore-installed
```

## Running the Dashboard

### Secured Dashboard (Recommended)

The secured dashboard includes authentication and role-based access control:

```bash
python advanced_trading/run_secured_dashboard.py --init-admin
```

This will start the dashboard and create an admin user. The console will display the generated password.

### Options

- `--port=8080`: Run on specific port (default: 8050)
- `--host=localhost`: Set specific host (default: 0.0.0.0)
- `--debug`: Run in debug mode
- `--init-admin`: Initialize admin user (first run)
- `--admin-user=username`: Set specific admin username (default: admin)
- `--admin-pass=password`: Set specific admin password
- `--log-level=INFO`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--no-auth`: Run dashboard without authentication (not recommended)

### Example

```bash
python advanced_trading/run_secured_dashboard.py --port=8080 --host=localhost --debug --log-level=DEBUG --init-admin --admin-user=admin_user
```

## Authentication System

The dashboard uses a comprehensive authentication system with:

- **User Registration**: Admin can create new users
- **Role-Based Access**: Different permissions for admin, analyst, and trader roles
- **Token-based Authentication**: Secure session management
- **API Key Management**: Secure storage for exchange API keys

### Default Credentials

When initializing with `--init-admin`:
- Username: admin
- Password: [Generated and displayed in console]

## Dashboard Structure

### Market Overview
- Real-time price charts with multiple timeframes
- Market summary metrics (price, volume, volatility)
- Volume profile analysis
- Market regime distribution

### Strategy Performance
- Performance metrics table
- Equity curves with benchmark comparison
- Drawdown analysis
- Trade history

### Market Analysis
- Correlation matrix
- Alerts and notifications
- Market event detection

### Administration (Admin only)
- User management
- API key management
- System settings

## Troubleshooting

### Common Issues

1. **Dependency Installation Problems**:
   - Try installing in a clean virtual environment
   - Use `--force-reinstall` or `--ignore-installed` flags
   - For system package conflicts, consider using Docker

2. **Dashboard Not Starting**:
   - Check logs in `advanced_trading/logs/` directory
   - Verify all dependencies are installed correctly
   - Make sure no other service is using the specified port

3. **Authentication Issues**:
   - Reset admin password by deleting the user data file and running with `--init-admin`
   - Check permissions on data storage directories

4. **Data Not Updating**:
   - Verify internet connection for market data retrieval
   - Check API key validity for connected exchanges
   - Use the manual refresh button or adjust update interval in settings

## Advanced Configuration

The dashboard can be configured through:

1. Command-line arguments (as shown above)
2. Configuration files in `advanced_trading/dashboard/config/`
3. Settings panel within the dashboard interface

## Security Considerations

- The dashboard uses secure password hashing
- API keys are stored encrypted
- Session tokens expire automatically
- Sensitive operations require admin privileges

## Development and Customization

To extend or customize the dashboard:

1. Add new components in `advanced_trading/dashboard/components.py`
2. Modify styles in `advanced_trading/dashboard/assets/`
3. Add new data sources in `advanced_trading/dashboard/market_data_handler.py` 