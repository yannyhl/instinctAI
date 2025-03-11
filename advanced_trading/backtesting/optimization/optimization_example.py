"""
Strategy Optimization Example
---------------------------
This example demonstrates how to use the optimization framework to tune strategy parameters
and test strategy robustness under different market scenarios.

The example includes:
1. Parameter optimization using various methods
2. Scenario testing to evaluate strategy robustness
3. Monte Carlo simulation for risk assessment
4. Visualization of optimization results
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from advanced_trading.strategies.base import Strategy, StrategyConfig
from advanced_trading.backtesting.engine.backtest import Backtest, BacktestConfig
from advanced_trading.backtesting.optimization import (
    StrategyOptimizer, OptimizerConfig, OptimizationResult,
    OptimizationMetric, OptimizationMethod,
    ScenarioTester, ScenarioConfig, ScenarioType
)


# Sample strategy for demonstration
class MovingAverageCrossStrategy(Strategy):
    """Simple moving average crossover strategy."""
    
    def __init__(self, config):
        super().__init__(config)
        self.fast_window = config.parameters.get("fast_window", 10)
        self.slow_window = config.parameters.get("slow_window", 30)
        self.current_position = 0
    
    def initialize(self, parameters=None, dependencies=None):
        """Initialize the strategy."""
        if parameters:
            self.fast_window = parameters.get("fast_window", self.fast_window)
            self.slow_window = parameters.get("slow_window", self.slow_window)
    
    def process_data(self, data):
        """Process market data."""
        processed_data = {}
        for symbol, df in data.items():
            processed_df = df.copy()
            processed_df['fast_ma'] = df['close'].rolling(self.fast_window).mean()
            processed_df['slow_ma'] = df['close'].rolling(self.slow_window).mean()
            processed_data[symbol] = processed_df
        return processed_data
    
    def generate_signals(self, data):
        """Generate trading signals."""
        signals = {}
        for symbol, df in data.items():
            signals_df = pd.DataFrame(index=df.index)
            signals_df['signal'] = 0.0
            
            # Generate signals
            signals_df['signal'] = np.where(
                df['fast_ma'] > df['slow_ma'], 1.0, 0.0
            )
            
            # Generate positions (avoid excessive trading)
            signals_df['position'] = signals_df['signal'].diff().fillna(0)
            
            signals[symbol] = signals_df
        return signals
    
    def execute(self, signals):
        """Execute trading signals."""
        result = self.create_result()
        
        for symbol, df in signals.items():
            # Extract buy/sell signals
            buys = df[df['position'] == 1].index
            sells = df[df['position'] == -1].index
            
            for buy_date in buys:
                result.add_trade(
                    symbol=symbol,
                    direction="buy",
                    quantity=1.0,
                    price=self.get_price(symbol, buy_date, "close"),
                    timestamp=buy_date
                )
            
            for sell_date in sells:
                result.add_trade(
                    symbol=symbol,
                    direction="sell",
                    quantity=1.0,
                    price=self.get_price(symbol, sell_date, "close"),
                    timestamp=sell_date
                )
        
        return result
    
    def get_price(self, symbol, date, price_type="close"):
        """Get price for a symbol at a specific date."""
        # In a real implementation, this would look up the price from market data
        return 100.0  # Placeholder


def generate_sample_data(symbols=None, start_date=None, end_date=None):
    """Generate sample price data for testing."""
    if symbols is None:
        symbols = ["AAPL", "MSFT", "GOOG"]
    
    if start_date is None:
        start_date = datetime.now() - timedelta(days=365)
    
    if end_date is None:
        end_date = datetime.now()
    
    # Create date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Generate data for each symbol
    data = {}
    for symbol in symbols:
        # Generate random walk
        np.random.seed(hash(symbol) % 2**32)
        returns = np.random.normal(0.0005, 0.015, len(date_range))
        prices = 100 * (1 + returns).cumprod()
        
        # Create DataFrame
        df = pd.DataFrame({
            'open': prices * (1 - np.random.uniform(0, 0.01, len(prices))),
            'high': prices * (1 + np.random.uniform(0, 0.01, len(prices))),
            'low': prices * (1 - np.random.uniform(0, 0.01, len(prices))),
            'close': prices,
            'volume': np.random.lognormal(12, 1, len(prices))
        }, index=date_range)
        
        data[symbol] = df
    
    return data


def parameter_optimization_example():
    """Example of parameter optimization."""
    print("\n=== Parameter Optimization Example ===")
    
    # Generate sample data
    market_data = generate_sample_data()
    
    # Create strategy configuration
    strategy_config = StrategyConfig(
        name="MA_Cross_Strategy",
        parameters={"fast_window": 10, "slow_window": 30}
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
        n_jobs=1
    )
    
    # Create optimizer
    optimizer = StrategyOptimizer(
        config=optimizer_config,
        strategy_class=MovingAverageCrossStrategy,
        base_config=strategy_config,
        market_data=market_data
    )
    
    # Run optimization
    print("Running parameter optimization...")
    result = optimizer.optimize()
    
    # Display results
    print(f"\nOptimization completed in {result.optimization_time:.2f} seconds")
    print(f"Best parameters: {result.best_parameters}")
    print(f"Best Sharpe ratio: {result.best_score:.4f}")
    
    # Plot optimization results
    fig = optimizer.plot_optimization_results(result)
    plt.savefig("optimization_results.png")
    print("Saved optimization results plot to 'optimization_results.png'")
    
    return result


def scenario_testing_example():
    """Example of scenario testing."""
    print("\n=== Scenario Testing Example ===")
    
    # Generate sample data
    market_data = generate_sample_data()
    
    # Create strategy configuration with best parameters from optimization
    strategy_config = StrategyConfig(
        name="MA_Cross_Strategy",
        parameters={"fast_window": 15, "slow_window": 50}  # Example best parameters
    )
    
    # Create scenario tester
    tester = ScenarioTester(
        strategy_class=MovingAverageCrossStrategy,
        strategy_config=strategy_config,
        base_market_data=market_data
    )
    
    # Run all scenario tests
    print("Running scenario tests...")
    results = tester.run_all_tests()
    
    # Display results
    print("\nScenario testing completed")
    print(f"Best case scenario: {results.best_case[0]}")
    print(f"Worst case scenario: {results.worst_case[0]}")
    
    # Display weighted metrics
    print("\nProbability-weighted metrics:")
    for metric, value in results.probability_weighted_metrics.items():
        print(f"  {metric}: {value:.4f}")
    
    # Plot scenario comparison
    fig = tester.plot_scenario_comparison(results)
    plt.savefig("scenario_comparison.png")
    print("Saved scenario comparison plot to 'scenario_comparison.png'")
    
    return results


def monte_carlo_example(scenario_results=None):
    """Example of Monte Carlo simulation."""
    print("\n=== Monte Carlo Simulation Example ===")
    
    if scenario_results is None:
        # Generate sample data
        market_data = generate_sample_data()
        
        # Create strategy configuration
        strategy_config = StrategyConfig(
            name="MA_Cross_Strategy",
            parameters={"fast_window": 15, "slow_window": 50}  # Example best parameters
        )
        
        # Create scenario tester
        tester = ScenarioTester(
            strategy_class=MovingAverageCrossStrategy,
            strategy_config=strategy_config,
            base_market_data=market_data
        )
    else:
        # Use existing tester from previous results
        tester = scenario_results._tester
    
    # Run Monte Carlo simulation
    print("Running Monte Carlo simulation...")
    results = tester.run_monte_carlo(num_simulations=100)  # Reduced for example
    
    # Display results
    print("\nMonte Carlo simulation completed")
    
    # Display selected percentile metrics
    metrics = ["sharpe_ratio", "annual_return", "max_drawdown"]
    percentiles = [5, 50, 95]
    
    print("\nMonte Carlo metrics:")
    for metric in metrics:
        print(f"\n{metric.replace('_', ' ').title()}:")
        for p in percentiles:
            key = f"{metric}_p{p}"
            if key in results.monte_carlo_metrics:
                print(f"  {p}th percentile: {results.monte_carlo_metrics[key]:.4f}")
    
    # Plot Monte Carlo results
    fig = tester.plot_monte_carlo_results(results)
    plt.savefig("monte_carlo_results.png")
    print("Saved Monte Carlo results plot to 'monte_carlo_results.png'")
    
    return results


if __name__ == "__main__":
    # Run the examples
    optimization_result = parameter_optimization_example()
    scenario_result = scenario_testing_example()
    monte_carlo_result = monte_carlo_example(scenario_result)
    
    print("\nAll examples completed successfully!") 