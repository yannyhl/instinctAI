# Exchange Optimization Examples

This directory contains example scripts demonstrating how to use the Exchange Optimization components of the Instinct AI Trading System.

## Available Examples

### Exchange Profiling Example

The `exchange_profiling_example.py` script demonstrates:

- Setting up the Exchange Capability Registry
- Registering exchanges with their capabilities
- Simulating API calls and order executions
- Recording performance metrics with the Exchange Profiler
- Analyzing exchange performance data
- Ranking exchanges based on different criteria
- Generating optimized execution parameters

### Smart Order Router Example

The `smart_routing_example.py` script demonstrates:

- Setting up test exchanges with different capabilities and performance metrics
- Using the Smart Order Router to determine the optimal exchange for order execution
- Testing different routing priorities (lowest fees, best execution, fastest execution, etc.)
- Comparing routing decisions for different order sizes, including order splitting
- Analyzing how urgency levels affect routing decisions
- Testing routing with different order types and symbols
- Visualizing exchange scores across different routing priorities

### Order Type Optimizer Example

The `order_type_optimization_example.py` script demonstrates:

- Setting up test exchanges with different capabilities and performance metrics
- Using the Order Type Optimizer to select optimal order types and parameters
- Testing how different urgency levels affect order type selection
- Analyzing the impact of various market conditions on execution decisions
- Exploring how order size affects recommended order types and parameters
- Comparing different execution preference profiles
- Visualizing the trade-offs between execution cost, market impact, and fill probability

## Running the Examples

To run an example, navigate to the project root directory and execute:

```bash
python -m advanced_trading.execution.optimization.examples.exchange_profiling_example
```

## Dependencies

The examples require the following dependencies:
- NumPy
- Pandas
- Matplotlib (for visualization)

## Notes

- These examples use simulated data to demonstrate the functionality
- In a production environment, you would connect to real exchanges and collect actual performance data
- The optimization parameters would be tuned based on historical performance data from your specific trading environment 