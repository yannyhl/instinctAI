# Dashboard Views

This directory contains the view components for the Instinct AI Trading Platform dashboard. Each view provides a specific monitoring or analysis capability for the trading system.

## Available Views

- **Performance Dashboard**: Monitors trading performance metrics, returns, and drawdowns
- **Strategy Dashboard**: Monitors strategy performance, signals, and allocations
- **Risk Monitoring Dashboard**: Comprehensive risk analysis and monitoring
- **System Health Dashboard**: Monitors system health, resource usage, and component status

## Risk Monitoring Dashboard

The Risk Monitoring Dashboard (`risk_monitoring_view.py`) provides a comprehensive view of the trading system's risk profile across multiple dimensions. It enables traders and risk managers to monitor portfolio risk, position risk, and market risk in real-time, with interactive visualizations and configurable alerts.

### Features

- **Risk Summary Cards**: At-a-glance view of critical risk metrics
  - Portfolio Value at Risk (VaR)
  - Current Drawdown
  - Risk Concentration
  - Market Regime

- **Risk Alerts**: Real-time alerts for risk threshold violations

- **Portfolio Risk Analysis**:
  - Risk Metrics View: VaR, Expected Shortfall, Beta, etc.
  - Risk Allocation View: Risk contribution by asset/sector
  - Drawdown Analysis: Historical and current drawdowns
  - Correlation Analysis: Asset correlations and network visualization

- **Position Risk Analysis**:
  - Risk Exposure View: Position-level risk metrics
  - Stop Levels View: Stop loss analysis
  - Position Sizing View: Allocation analysis and recommendations

- **Market Risk Analysis**:
  - Volatility Analysis: Historical volatility, current levels, term structure
  - Correlation Analysis: Cross-asset correlations
  - Regime Analysis: Market regime detection and analysis

### Usage

The Risk Monitoring Dashboard is accessible through the main dashboard interface. To use it:

1. Navigate to the dashboard in your browser
2. Select "Risk Monitoring" from the navigation menu
3. Use the date range selector to choose the analysis period
4. Select different views using the view selectors in each section

### Implementation

The dashboard is implemented using:

- **Dash**: For the web application framework
- **Plotly**: For interactive visualizations
- **Bootstrap**: For responsive layout and styling

The main components are:

- `create_risk_monitoring_view()`: Creates the main dashboard layout
- Update callbacks for each section (portfolio risk, position risk, market risk)
- Helper functions for creating specific visualizations

### Extending

To add new risk visualizations:

1. Create a new helper function in `risk_monitoring_view.py`
2. Add the visualization to the appropriate section
3. Update the corresponding callback function

For more detailed documentation, see the [Risk Monitoring Dashboard Documentation](../docs/risk_monitoring_dashboard.md). 