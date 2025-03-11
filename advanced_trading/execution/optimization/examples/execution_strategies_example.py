"""
Execution Strategies Example

This example demonstrates how to use the various execution strategies
available in the execution optimization module.
"""

import time
import logging
import random
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from advanced_trading.execution.optimization import (
    # Execution strategies
    ExecutionStrategy, ExecutionRequest, 
    BasicExecutionStrategy, TWAPStrategy, VWAPStrategy, AdaptiveStrategy,
    VolumeProfile, MarketCondition,
    
    # Supporting components
    get_smart_order_router, get_order_type_optimizer,
    get_exchange_registry, get_exchange_profiler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock Market Data Provider for the Adaptive Strategy
class MockMarketDataProvider:
    """
    Mock market data provider for demonstration purposes.
    
    This provides simulated market data for the adaptive strategy to respond to.
    In a real implementation, this would connect to a real market data source.
    """
    
    def __init__(self, base_volatility=0.3, base_liquidity=0.7, base_price=10000.0):
        self.base_volatility = base_volatility
        self.base_liquidity = base_liquidity
        self.base_price = base_price
        self.current_time = time.time()
        
        # Initialize price series
        self.prices = {}
        self.volatilities = {}
        self.liquidities = {}
        
        # Generate some random market data
        self._generate_market_data("BTC/USD")
        self._generate_market_data("ETH/USD")
    
    def _generate_market_data(self, symbol):
        # Generate 24 hours of 5-minute price data
        periods = 24 * 12  # 5-minute periods in 24 hours
        
        # Create a random walk for price
        prices = [self.base_price]
        for _ in range(periods):
            # Random price change with some mean reversion
            change = random.normalvariate(0, 1) * self.base_price * 0.005
            # Mean reversion
            change -= (prices[-1] - self.base_price) * 0.01
            prices.append(prices[-1] + change)
        
        # Create a random walk for volatility
        volatilities = [self.base_volatility]
        for _ in range(periods):
            # Random volatility change with mean reversion
            change = random.normalvariate(0, 1) * 0.02
            # Mean reversion
            change -= (volatilities[-1] - self.base_volatility) * 0.1
            volatilities.append(max(0.1, min(0.9, volatilities[-1] + change)))
        
        # Create a random walk for liquidity
        liquidities = [self.base_liquidity]
        for _ in range(periods):
            # Random liquidity change with mean reversion
            change = random.normalvariate(0, 1) * 0.02
            # Mean reversion
            change -= (liquidities[-1] - self.base_liquidity) * 0.1
            liquidities.append(max(0.1, min(0.9, liquidities[-1] + change)))
        
        # Store the data
        self.prices[symbol] = prices
        self.volatilities[symbol] = volatilities
        self.liquidities[symbol] = liquidities
    
    def get_current_price(self, symbol):
        """Get the current price for a symbol."""
        if symbol not in self.prices:
            return None
        
        # Return the latest price
        return self.prices[symbol][-1]
    
    def get_recent_volatility(self, symbol):
        """Get the recent volatility for a symbol."""
        if symbol not in self.volatilities:
            return None
        
        # Return the latest volatility
        return self.volatilities[symbol][-1]
    
    def get_current_spread(self, symbol):
        """Get the current spread for a symbol."""
        if symbol not in self.prices:
            return None
        
        # Simulate a spread based on volatility
        volatility = self.volatilities[symbol][-1]
        price = self.prices[symbol][-1]
        
        # Higher volatility means wider spreads
        return price * 0.0001 * (1 + volatility * 5)
    
    def get_current_liquidity(self, symbol):
        """Get the current liquidity for a symbol."""
        if symbol not in self.liquidities:
            return None
        
        # Return the latest liquidity
        return self.liquidities[symbol][-1]
    
    def update(self):
        """Update market data with new values."""
        for symbol in self.prices:
            # Update price with random walk
            price = self.prices[symbol][-1]
            change = random.normalvariate(0, 1) * price * 0.002
            change -= (price - self.base_price) * 0.005  # Mean reversion
            new_price = price + change
            self.prices[symbol].append(new_price)
            
            # Update volatility with random walk
            volatility = self.volatilities[symbol][-1]
            change = random.normalvariate(0, 1) * 0.01
            change -= (volatility - self.base_volatility) * 0.05  # Mean reversion
            new_volatility = max(0.1, min(0.9, volatility + change))
            self.volatilities[symbol].append(new_volatility)
            
            # Update liquidity with random walk
            liquidity = self.liquidities[symbol][-1]
            change = random.normalvariate(0, 1) * 0.01
            change -= (liquidity - self.base_liquidity) * 0.05  # Mean reversion
            new_liquidity = max(0.1, min(0.9, liquidity + change))
            self.liquidities[symbol].append(new_liquidity)

# Mock Execution Engine to simulate order execution
class MockExecutionEngine:
    """
    Mock execution engine for demonstration purposes.
    
    This simulates executing orders and returning filled prices.
    In a real implementation, this would connect to exchange APIs.
    """
    
    def __init__(self, market_data_provider):
        self.market_data_provider = market_data_provider
        self.executed_orders = []
    
    def execute_order(self, sub_order):
        """Simulate executing an order and returning a fill price."""
        symbol = sub_order.symbol
        side = sub_order.side
        size = sub_order.size
        
        # Get current price
        price = self.market_data_provider.get_current_price(symbol)
        if price is None:
            return None
        
        # Simulate slippage based on order size, liquidity, and volatility
        liquidity = self.market_data_provider.get_current_liquidity(symbol)
        volatility = self.market_data_provider.get_recent_volatility(symbol)
        
        # Calculate slippage (larger for larger orders, lower liquidity, higher volatility)
        slippage_factor = 0.0001 * (1 + size * 0.1) * (1 + (1 - liquidity) * 2) * (1 + volatility * 2)
        
        # Apply slippage based on side
        if side == "buy":
            fill_price = price * (1 + slippage_factor)
        else:
            fill_price = price * (1 - slippage_factor)
        
        # Record the execution
        self.executed_orders.append({
            "id": sub_order.id,
            "symbol": symbol,
            "side": side,
            "size": size,
            "price": fill_price,
            "time": time.time()
        })
        
        return fill_price

# Demo function to compare execution strategies
def compare_execution_strategies():
    """
    Compare different execution strategies on a simulated order.
    """
    # Create a mock market data provider
    market_data = MockMarketDataProvider()
    
    # Create a mock execution engine
    execution_engine = MockExecutionEngine(market_data)
    
    # Get components needed for strategies
    router = get_smart_order_router()
    optimizer = get_order_type_optimizer()
    registry = get_exchange_registry()
    profiler = get_exchange_profiler()
    
    # Create execution strategies
    basic_strategy = BasicExecutionStrategy(
        order_router=router,
        order_optimizer=optimizer,
        registry=registry,
        profiler=profiler
    )
    
    twap_strategy = TWAPStrategy(
        min_chunks=8,
        max_chunks=12,
        min_chunk_interval_seconds=30,  # 30 seconds for demo purposes
        order_router=router,
        order_optimizer=optimizer,
        registry=registry,
        profiler=profiler
    )
    
    vwap_strategy = VWAPStrategy(
        min_chunks=8,
        max_chunks=12,
        min_chunk_interval_seconds=30,  # 30 seconds for demo purposes
        volume_profile=VolumeProfile(),  # Use default profile
        order_router=router,
        order_optimizer=optimizer,
        registry=registry,
        profiler=profiler
    )
    
    adaptive_strategy = AdaptiveStrategy(
        initial_chunks=8,
        min_chunk_interval_seconds=30,  # 30 seconds for demo purposes
        volatility_sensitivity=0.7,
        price_sensitivity=0.7,
        liquidity_sensitivity=0.7,
        market_data_provider=market_data,
        order_router=router,
        order_optimizer=optimizer,
        registry=registry,
        profiler=profiler
    )
    
    # Create a sample execution request
    start_time = time.time()
    end_time = start_time + 300  # 5 minutes for demo
    
    execution_request = ExecutionRequest(
        id="demo_order_1",
        symbol="BTC/USD",
        side="buy",
        size=1.0,
        size_usd=10000.0,
        start_time=start_time,
        end_time=end_time,
        priority="balanced"
    )
    
    # Create execution schedules for each strategy
    basic_schedule = basic_strategy.create_execution_schedule(execution_request)
    twap_schedule = twap_strategy.create_execution_schedule(execution_request)
    vwap_schedule = vwap_strategy.create_execution_schedule(execution_request)
    adaptive_schedule = adaptive_strategy.create_execution_schedule(execution_request)
    
    # Store strategies and schedules
    strategies = {
        "Basic": (basic_strategy, basic_schedule),
        "TWAP": (twap_strategy, twap_schedule),
        "VWAP": (vwap_strategy, vwap_schedule),
        "Adaptive": (adaptive_strategy, adaptive_schedule)
    }
    
    # Track performance
    strategy_results = {
        "Basic": {"times": [], "prices": [], "sizes": []},
        "TWAP": {"times": [], "prices": [], "sizes": []},
        "VWAP": {"times": [], "prices": [], "sizes": []},
        "Adaptive": {"times": [], "prices": [], "sizes": []}
    }
    
    # Simulate market and execution for demo
    print("Simulating execution with multiple strategies...")
    
    simulation_end = start_time + 600  # 10 minutes
    current_time = start_time
    
    while current_time < simulation_end:
        # Update market data
        market_data.update()
        
        # Process each strategy
        for name, (strategy, schedule) in strategies.items():
            # Get next actions
            next_actions = strategy.get_next_actions(schedule)
            
            # Execute due orders
            for sub_order in next_actions:
                fill_price = execution_engine.execute_order(sub_order)
                
                if fill_price:
                    # Update order status
                    strategy.update_order_status(sub_order.id, "filled", fill_price)
                    
                    # Track results
                    strategy_results[name]["times"].append(current_time)
                    strategy_results[name]["prices"].append(fill_price)
                    strategy_results[name]["sizes"].append(sub_order.size)
                    
                    print(f"Strategy: {name}, Executed order: {sub_order.id}, Size: {sub_order.size:.4f}, Price: {fill_price:.2f}")
        
        # Advance time
        current_time += 10  # 10 seconds per step
        time.sleep(0.01)  # Small sleep to avoid CPU spinning
    
    # Calculate performance metrics
    print("\nExecution Results:")
    print("-----------------")
    
    for name, results in strategy_results.items():
        if not results["prices"]:
            print(f"{name}: No orders executed")
            continue
        
        # Calculate VWAP achieved by the strategy
        vwap_price = sum(p * s for p, s in zip(results["prices"], results["sizes"])) / sum(results["sizes"])
        
        # Calculate total executed size
        total_size = sum(results["sizes"])
        
        # Calculate average execution time
        avg_time = sum(t - start_time for t in results["times"]) / len(results["times"])
        
        print(f"{name}:")
        print(f"  Total Executed: {total_size:.6f} BTC")
        print(f"  VWAP Price: ${vwap_price:.2f}")
        print(f"  Avg. Execution Time: {avg_time:.1f} seconds\n")
    
    # Plot results
    plt.figure(figsize=(12, 8))
    
    # 1. Price vs. Time plot
    plt.subplot(211)
    for name, results in strategy_results.items():
        if results["times"]:
            # Convert to relative time for easier reading
            rel_times = [(t - start_time) for t in results["times"]]
            plt.scatter(rel_times, results["prices"], label=f"{name} Executions", alpha=0.7)
    
    plt.title("Execution Prices vs. Time")
    plt.xlabel("Time (seconds since start)")
    plt.ylabel("Price ($)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 2. Cumulative Execution plot
    plt.subplot(212)
    for name, results in strategy_results.items():
        if results["times"]:
            # Convert to relative time for easier reading
            rel_times = [(t - start_time) for t in results["times"]]
            # Calculate cumulative execution
            cum_sizes = []
            size_so_far = 0
            for s in results["sizes"]:
                size_so_far += s
                cum_sizes.append(size_so_far)
            
            plt.step(rel_times, cum_sizes, label=f"{name} Cumulative", where='post')
    
    plt.title("Cumulative Execution vs. Time")
    plt.xlabel("Time (seconds since start)")
    plt.ylabel("Cumulative Size (BTC)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("execution_strategy_comparison.png")
    print("Saved plot to execution_strategy_comparison.png")
    plt.close()

if __name__ == "__main__":
    compare_execution_strategies() 