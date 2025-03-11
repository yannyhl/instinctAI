# Backtesting Optimization Framework

This module provides a comprehensive framework for optimizing trading strategies and evaluating their robustness through scenario testing and Monte Carlo simulation.

## Key Components

### 1. Strategy Optimizer

The `StrategyOptimizer` class provides tools for optimizing strategy parameters using various methods:

- **Grid Search**: Exhaustive search over a specified parameter grid
- **Random Search**: Random sampling of parameters from the parameter space
- **Bayesian Optimization**: Efficient optimization using Gaussian Process models
- **Genetic Algorithms**: Evolution-inspired optimization for complex parameter spaces

The optimizer incorporates proper time series cross-validation to prevent overfitting and ensure robust results.

### 2. Scenario Testing

The `ScenarioTester` class enables testing strategies under different market conditions:

- **Predefined Scenarios**: Bull market, bear market, sideways market, high volatility, market crash, etc.
- **Custom Scenarios**: Create your own market scenarios with specific characteristics
- **Scenario Transformation**: Apply transformations to historical data to simulate specific market conditions
- **Probability Weighting**: Assign probabilities to different scenarios to calculate weighted performance metrics

### 3. Monte Carlo Simulation

The framework includes Monte Carlo simulation capabilities to assess strategy robustness:

- **Scenario Sampling**: Sample from different market scenarios according to their probabilities
- **Risk Assessment**: Analyze the distribution of key performance metrics
- **Tail Risk**: Evaluate performance in extreme market conditions
- **Confidence Intervals**: Calculate percentiles for various performance metrics

### 4. Visualization Tools

The framework provides various visualization tools to analyze optimization results:

- **Parameter Importance**: Visualize the importance of different parameters
- **Parameter Surface**: Plot 3D surfaces showing the relationship between parameters and performance
- **Scenario Comparison**: Compare strategy performance across different market scenarios
- **Monte Carlo Results**: Visualize the distribution of performance metrics from Monte Carlo simulations

## Usage Examples

### Strategy Optimization

```python
from advanced_trading.backtesting.optimization import (
    StrategyOptimizer, OptimizerConfig, OptimizationMetric, OptimizationMethod
)

# Define parameter space
parameter_space = {
    "fast_window": [5, 10, 15, 20, 25],
    "slow_window": [30, 40, 50, 60, 70]
}

# Create optimizer configuration
optimizer_config = OptimizerConfig(
    parameter_space=parameter_space,
    optimization_metric=OptimizationMetric.SHARPE_RATIO,
    optimization_method=OptimizationMethod.GRID_SEARCH,
    maximize=True,
    n_jobs=4  # Use 4 parallel processes
)

# Create optimizer
optimizer = StrategyOptimizer(
    config=optimizer_config,
    strategy_class=MyStrategy,
    base_config=strategy_config,
    market_data=market_data
)

# Run optimization
result = optimizer.optimize()

# Display results
print(f"Best parameters: {result.best_parameters}")
print(f"Best score: {result.best_score}")

# Plot results
optimizer.plot_optimization_results(result)
```

### Scenario Testing

```python
from advanced_trading.backtesting.optimization import (
    ScenarioTester, ScenarioType
)

# Create scenario tester
tester = ScenarioTester(
    strategy_class=MyStrategy,
    strategy_config=strategy_config,
    base_market_data=market_data
)

# Add custom scenario
tester.add_scenario(
    name="market_crash_2008",
    scenario_type=ScenarioType.MARKET_CRASH,
    parameters={
        "crash_size": -0.5,
        "crash_duration": 30,
        "recovery_speed": 0.2
    },
    description="Simulates a 2008-style market crash",
    probability=0.05
)

# Run all scenario tests
results = tester.run_all_tests()

# Display results
print(f"Best case scenario: {results.best_case[0]}")
print(f"Worst case scenario: {results.worst_case[0]}")

# Plot scenario comparison
tester.plot_scenario_comparison(results)
```

### Monte Carlo Simulation

```python
from advanced_trading.backtesting.optimization import (
    ScenarioTester
)

# Create scenario tester
tester = ScenarioTester(
    strategy_class=MyStrategy,
    strategy_config=strategy_config,
    base_market_data=market_data
)

# Run Monte Carlo simulation
results = tester.run_monte_carlo(num_simulations=1000)

# Display results
for metric in ["sharpe_ratio", "annual_return", "max_drawdown"]:
    print(f"{metric}:")
    print(f"  5th percentile: {results.monte_carlo_metrics[f'{metric}_p5']:.4f}")
    print(f"  50th percentile: {results.monte_carlo_metrics[f'{metric}_p50']:.4f}")
    print(f"  95th percentile: {results.monte_carlo_metrics[f'{metric}_p95']:.4f}")

# Plot Monte Carlo results
tester.plot_monte_carlo_results(results)
```

## Advanced Features

### Parameter Constraints

You can define constraints on parameter combinations:

```python
def parameter_constraint(params):
    """Ensure fast_window is less than slow_window."""
    return params["fast_window"] < params["slow_window"]

optimizer_config = OptimizerConfig(
    parameter_space=parameter_space,
    optimization_metric=OptimizationMetric.SHARPE_RATIO,
    optimization_method=OptimizationMethod.GRID_SEARCH,
    maximize=True,
    additional_constraints=parameter_constraint
)
```

### Custom Scenario Transformations

You can define custom transformations for market scenarios:

```python
def my_custom_scenario(data, params):
    """Custom market scenario transformation."""
    result = {}
    for symbol, df in data.items():
        transformed_df = df.copy()
        # Apply your custom transformations
        # ...
        result[symbol] = transformed_df
    return result

tester.add_scenario(
    name="my_custom_scenario",
    scenario_type=ScenarioType.CUSTOM,
    parameters={"param1": 0.5, "param2": 0.3},
    data_transformation=my_custom_scenario
)
```

### Optimization Callbacks

You can define callbacks to track optimization progress:

```python
class MyCallback(OptimizationCallback):
    def on_optimization_start(self, config):
        print("Starting optimization...")
    
    def on_iteration_complete(self, iteration, parameters, score, best_score):
        print(f"Iteration {iteration}: score={score}, best={best_score}")
    
    def on_optimization_end(self, result):
        print(f"Optimization complete: best score={result.best_score}")

# Use your callback with the optimizer
optimizer = StrategyOptimizer(
    config=optimizer_config,
    strategy_class=MyStrategy,
    base_config=strategy_config,
    market_data=market_data,
    callbacks=[MyCallback()]
)
```

## Installation Requirements

The optimization framework depends on the following packages:

- NumPy, Pandas: Data manipulation
- Matplotlib: Visualization
- Scikit-learn, Scikit-optimize: For Bayesian optimization
- Joblib: For parallel processing
- DEAP: For genetic algorithms (optional)

## API Reference

For detailed API documentation, please see the API Reference section or the docstrings in the source code. 