# Advanced Trading Test Suite

This directory contains unit tests and integration tests for the components of the advanced_trading system.

## Test Organization

Tests are organized according to the same structure as the main package:

```
tests/
├── core/          # Tests for core functionality
├── data/          # Tests for data handling components
├── execution/     # Tests for execution components
├── risk/          # Tests for risk management components
│   ├── position/  # Tests for position-level risk management
│   └── portfolio/ # Tests for portfolio-level risk management
└── strategy/      # Tests for trading strategies
```

## Running Tests

### Running All Tests

```bash
python -m unittest discover -s advanced_trading/tests
```

### Running Specific Test Modules

```bash
# Run all tests in a specific package
python -m unittest discover -s advanced_trading/tests/risk

# Run a specific test file
python -m unittest advanced_trading.tests.risk.portfolio.test_controller
```

## Recent Test Coverage Enhancements

### Portfolio Risk Controller (Current Update)

The `PortfolioRiskController` test suite has been enhanced with additional tests covering:

- Diversification metrics calculation
- Risk-adjusted position sizing 
- Risk budget allocation
- Portfolio exposure metrics
- Current weight and exposure calculation
- Drawdown calculation
- Correlation cluster identification
- Market state analysis
- Market regime detection

See `advanced_trading/tests/risk/portfolio/README.md` for detailed information about the portfolio risk test coverage.

## Test Coverage Report

To generate a test coverage report:

```bash
# Install coverage tool if not already installed
pip install coverage

# Run tests with coverage
coverage run -m unittest discover -s advanced_trading/tests

# Generate coverage report
coverage report -m
``` 