# Integration Testing Framework

This directory contains integration tests for the Instinct AI trading system. Integration tests verify that different components of the system work together correctly, focusing on the interactions between modules rather than individual functions or classes.

## Test Organization

Integration tests are organized by system workflow:

```
integration/
├── data_to_model/          # Tests for data pipeline to model workflow
├── model_to_strategy/      # Tests for model to strategy workflow
├── strategy_to_risk/       # Tests for strategy to risk management workflow
├── risk_to_execution/      # Tests for risk to execution workflow
├── end_to_end/             # Complete end-to-end system tests
└── fixtures/               # Test fixtures and data
```

## Key Integration Test Areas

### 1. Data Pipeline to Model Integration
- Test data loading, preprocessing, and feeding into models
- Verify feature engineering pipeline
- Test model training and inference with live data

### 2. Model to Strategy Integration
- Test model predictions integrated with strategy logic
- Verify strategy behavior with different model outputs
- Test strategy lifecycle with dynamic model updates

### 3. Strategy to Risk Management Integration
- Test risk limit enforcement on strategy operations
- Verify position sizing with risk constraints
- Test emergency protocols for risk violations

### 4. Risk to Execution Integration
- Test pre-trade risk checks during order submission
- Verify circuit breaker activation with execution
- Test execution behavior under different risk scenarios

### 5. End-to-End System Tests
- Test complete trading workflows from data to execution
- Verify system behavior under various market conditions
- Test failure recovery and resiliency

## Running Integration Tests

### Running All Integration Tests

```bash
python -m unittest discover -s advanced_trading/tests/integration
```

### Running Specific Integration Test Modules

```bash
# Run all tests in a specific integration area
python -m unittest discover -s advanced_trading/tests/integration/risk_to_execution

# Run a specific integration test file
python -m unittest advanced_trading.tests.integration.end_to_end.test_trading_workflow
```

## Testing Best Practices

1. **Use Realistic Test Data**: Prefer using realistic market data over simple synthetic data
2. **Test Edge Cases**: Include tests for boundary conditions and error scenarios
3. **Minimize Dependencies**: Use mocks where appropriate to isolate the integration points being tested
4. **Standardize Setup/Teardown**: Use consistent environment setup and cleanup
5. **Measure Performance**: Include performance metrics in integration tests

## Test Configuration

Integration tests can be configured using environment variables:

- `INTEGRATION_TEST_MODE`: Set to `fast`, `thorough`, or `stress` to control test depth
- `INTEGRATION_TEST_DATA_PATH`: Path to test data fixtures
- `INTEGRATION_TEST_TIMEOUT`: Maximum time (in seconds) allowed for integration tests 