# Risk Integration Layer

## Overview

The Risk Integration Layer connects execution strategies with risk management components in the Instinct AI Trading System. This layer ensures that all trading decisions adhere to the system's risk management rules by implementing pre-trade and post-trade risk checks at both position and portfolio levels.

## Purpose

This module serves as a critical safety layer that:

1. Validates orders before execution against risk parameters
2. Monitors position-level risk metrics in real-time
3. Analyzes execution results from a risk perspective
4. Prevents actions that could violate risk management rules
5. Provides integration with the portfolio risk management system

## Key Components

### Core Components

- **ExecutionRiskManager**: Central component that coordinates pre-trade and post-trade risk checks
- **RiskCheckResult**: Data structure representing the result of a risk check
- **RiskValidationStatus**: Status of risk validation (PASSED, WARNING, FAILED, ERROR)

### Strategy Integration (New)

- **StrategyRiskAdapter**: Adapter that connects trading strategies with risk management
- **Strategy Lifecycle Risk Management**: Risk validation throughout strategy lifecycle
- **Risk-Adjusted Position Sizing**: Dynamic sizing based on risk parameters

### Risk Check Interfaces

- **PreTradeRiskCheck**: Abstract base class for pre-trade risk checks
- **PostTradeRiskAnalysis**: Abstract base class for post-trade risk analysis

### Pre-Trade Check Implementations

- **PositionSizeCheck**: Validates order size against absolute and relative limits
- **MaxDrawdownCheck**: Ensures orders won't exceed maximum drawdown limits
- **ExposureCheck**: Validates portfolio exposure constraints
- **VolumePercentCheck**: Ensures order size is reasonable compared to market volume

### Post-Trade Check Implementations

- **SlippageCheck**: Analyzes execution slippage to identify issues

### Position Risk Management

- **PositionRiskValidator**: Comprehensive position-level risk monitoring
- **PositionRiskMetrics**: Data structure for tracking position risk metrics
- **PositionRiskStatus**: Risk status indicator for positions (SAFE, WARNING, AT_RISK, VIOLATED)

## Strategy Integration

### Strategy Risk Adapter

The StrategyRiskAdapter wraps around strategies to ensure they adhere to risk rules:

1. **Signal Validation**: Validates trading signals against risk parameters
2. **Position Monitoring**: Tracks strategy positions for risk compliance
3. **Adaptive Sizing**: Adjusts position sizes based on risk metrics
4. **Portfolio Constraints**: Enforces portfolio-level risk limits
5. **Risk-Reducing Actions**: Implements defensive trades when risk levels are high

### Usage Examples

#### Wrapping a Strategy with Risk Adapter

```python
from advanced_trading.strategies.statistical.statistical_arbitrage import StatisticalArbitrageStrategy
from advanced_trading.execution.risk_integration.strategy_risk_adapter import StrategyRiskAdapter
from advanced_trading.execution.risk_integration.risk_manager import ExecutionRiskConfig

# Create the strategy
strategy = StatisticalArbitrageStrategy(
    symbols=['BTC', 'ETH', 'SOL'],
    lookback_period=30,
    entry_threshold=2.0,
    exit_threshold=0.5
)

# Create risk configuration
risk_config = ExecutionRiskConfig(
    max_position_size_percent=0.05,  # 5% max position size
    max_daily_loss=0.02,             # 2% max daily loss
    max_portfolio_drawdown=0.10      # 10% max drawdown
)

# Create risk-adapted strategy
risk_adapted_strategy = StrategyRiskAdapter(
    strategy=strategy,
    risk_config=risk_config,
    enable_position_validation=True,
    enable_portfolio_validation=True,
    enable_adaptive_sizing=True
)

# Execute trades with risk management
trades = risk_adapted_strategy.execute_trades(data_dict, capital)

# Analyze performance with risk insights
performance = risk_adapted_strategy.analyze_performance(trades)
```

#### Working with Meta-Strategies

```python
from advanced_trading.strategies.meta.adaptive_meta_strategy import AdaptiveMetaStrategy
from advanced_trading.execution.risk_integration.strategy_risk_adapter import StrategyRiskAdapter

# Create component strategies
strategy1 = StatisticalArbitrageStrategy(symbols=symbols)
strategy2 = AdvancedCryptoStrategy(symbols=symbols)

# Create meta-strategy
meta_strategy = AdaptiveMetaStrategy(
    symbols=symbols,
    strategies=[strategy1, strategy2]
)

# Apply risk adapter to meta-strategy
risk_adapted_meta = StrategyRiskAdapter(
    strategy=meta_strategy,
    enable_position_validation=True,
    enable_portfolio_validation=True,
    max_position_size_pct=0.04,
    correlations_limit=0.6
)
```

## Setting Up the Risk Manager

```python
from advanced_trading.execution.risk_integration import ExecutionRiskManager, ExecutionRiskConfig

# Create custom configuration
config = ExecutionRiskConfig(
    max_position_size_percent=0.05,  # 5% of portfolio
    max_daily_loss=0.03,  # 3% max daily loss
    max_slippage_percent=0.005  # 0.5% max slippage
)

# Initialize risk manager
risk_manager = ExecutionRiskManager(config)
```

## Validating Orders

```python
# Perform pre-trade validation
is_valid, results = risk_manager.is_order_valid(
    order=order,
    portfolio_state=portfolio_state,
    market_data=market_data
)

if is_valid:
    # Proceed with order execution
    execute_order(order)
else:
    # Handle validation failure
    for result in results:
        if result.status != RiskValidationStatus.PASSED:
            log_error(f"{result.check_name}: {result.message}")
```

## Position Risk Validation

```python
from advanced_trading.execution.risk_integration import PositionRiskValidator

# Create position risk validator
validator = PositionRiskValidator(
    max_position_size_pct=0.1,
    max_position_loss_pct=0.05,
    enable_auto_stops=True
)

# Validate positions
violations = validator.validate_all_positions(
    positions=positions,
    market_data=market_data,
    portfolio_data=portfolio
)

# Get at-risk positions
at_risk = validator.get_at_risk_positions()
```

## Post-Trade Analysis

```python
# Analyze execution results
analysis_results = risk_manager.analyze_execution(
    order=original_order,
    execution_details=execution_details,
    portfolio_state=portfolio_state,
    market_data=market_data
)

# Process analysis results
for result in analysis_results:
    if result.status == RiskValidationStatus.FAILED:
        log_warning(f"Execution issue: {result.message}")
```

## Integration Points

The Risk Integration Layer connects with:

1. **Execution Strategies**: By validating orders before execution
2. **Portfolio Risk Management**: Through portfolio-level constraint checks
3. **Circuit Breakers**: To trigger emergency actions when risk limits are exceeded
4. **Execution Dashboard**: By providing risk metrics and status indicators
5. **Strategy Layer**: Through StrategyRiskAdapter for strategy-level risk management

## Configuration

The Risk Integration Layer is highly configurable through the `ExecutionRiskConfig` class. Key configuration parameters include:

- Position size limits (absolute, percentage, by asset)
- Order size limits (for individual orders)
- Market impact constraints (volume percentage, slippage limits)
- Portfolio-level constraints (drawdown, daily loss)
- Analysis settings (enable/disable specific checks)

## Best Practices

1. **Always validate before execution**: Integrate pre-trade checks into your execution workflow
2. **Monitor position risk continuously**: Validate positions after market changes
3. **Use position size scaling**: Adjust position sizes based on volatility and risk
4. **Configure context-appropriate limits**: Set different limits for different markets and strategies
5. **Analyze execution quality**: Use post-trade analysis to improve execution strategies
6. **Wrap strategies with adapters**: Use StrategyRiskAdapter to integrate risk management with all strategies

## Further Examples

See the `examples` directory for complete implementation examples:
- `strategy_integration_example.py`: Demonstrates integrating strategies with risk management
- `risk_integration_example.py`: Demonstrates the full risk integration workflow 