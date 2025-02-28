# Instinct AI Trading Dashboard

A real-time monitoring dashboard for the Instinct AI trading system. This dashboard provides a comprehensive overview of market conditions, strategy performance, and risk metrics to inform trading decisions.

## Features

- **Market Overview**: Monitor real-time market prices, volume, and volatility
- **Event Detection**: Automatically identify significant market events
- **Strategy Performance**: Track strategy returns, drawdowns, and key metrics
- **Risk Analysis**: Analyze risk metrics, correlations, and value-at-risk (VaR)
- **Multi-asset Support**: Monitor multiple trading pairs simultaneously

## Installation

The dashboard requires additional dependencies on top of the main Instinct AI system:

```
pip install dash plotly pandas numpy
```

For development, you may also want to install:

```
pip install dash-dev-tools
```

## Usage

### Quick Start

The easiest way to run the dashboard is using the launcher script:

```
python run_dashboard.py
```

This will start the dashboard on the default port (8050) and open it in your browser.

### Command-line Options

The dashboard launcher supports several options:

```
python run_dashboard.py --port 8080 --debug --no-browser
```

Options:
- `--port PORT`: Specify the port to run the dashboard on (default: 8050)
- `--debug`: Run in debug mode with hot reloading for development
- `--no-browser`: Don't automatically open the browser

### Running Directly

You can also run the dashboard directly with:

```
python -m advanced_trading.dashboard.app
```

### Stopping the Dashboard

To stop the dashboard, press `Ctrl+C` in the terminal where it's running.

## Dashboard Sections

### Market Overview

This tab provides real-time market data and event detection:

- Current price charts with candlestick visualization
- Volume and volatility analysis
- Detected market events with impact scores
- Technical indicators

### Strategy Performance

This tab shows the performance of your trading strategies:

- Key performance metrics (returns, Sharpe ratio, etc.)
- Equity curve comparison with benchmark
- Drawdown analysis
- Rolling performance metrics

### Risk Analysis

This tab provides risk management information:

- Risk metrics table (volatility, VaR, max drawdown)
- Returns distribution and VaR visualization
- Asset correlation matrix
- Stress test scenarios

## Development

### Dashboard Structure

The dashboard follows this structure:

```
dashboard/
├── app.py            # Main application
├── assets/           # Static assets
│   └── style.css     # CSS styles
└── README.md         # Documentation
```

### Extending the Dashboard

To add new features to the dashboard:

1. Add new components and callbacks in `app.py`
2. Update styles in `assets/style.css`
3. Implement data processing for new metrics

## Troubleshooting

If you encounter issues:

- Check that all dependencies are installed
- Verify that the port is not already in use
- Ensure the data refresher has access to market data
- Check the logs for error messages

For detailed error information, run in debug mode with:

```
python run_dashboard.py --debug
``` 