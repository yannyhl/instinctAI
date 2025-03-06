# Portfolio Risk Controller Tests

This directory contains unit tests for the `PortfolioRiskController` class, which is responsible for managing portfolio-level risk in the advanced trading system.

## Test Coverage

The test suite in `test_controller.py` covers the following functionality:

### Core Functionality
- Initialization and parameter validation
- Market state updates
- Portfolio weight calculation
- Risk metrics calculation

### Position Sizing and Allocation
- Position sizing recommendations generation
- Risk-adjusted position sizing
- Risk budget allocation
- Correlation-based adjustments

### Risk Metrics
- Basic and advanced portfolio metrics
- Risk contribution calculation
- Diversification metrics
- Portfolio exposure metrics

### Market Analysis
- Historical returns calculation
- Correlation cluster identification
- Current market state analysis
- Market volatility and trend metrics

### Portfolio Management
- Current position weight calculation
- Portfolio exposure calculation
- Drawdown calculation and management
- Rebalance trade generation

## Running Tests

To run the portfolio risk controller tests:

```bash
# From the project root directory
python -m unittest advanced_trading.tests.risk.portfolio.test_controller
```

## Test Enhancement History

- **Initial Implementation**: Basic test coverage for core functionality
- **2023-09-15**: Added tests for position sizing and risk contribution
- **2023-12-10**: Added tests for portfolio metrics and historical returns
- **Current Update**: Enhanced coverage for market state analysis, diversification metrics, and correlation-based adjustments 