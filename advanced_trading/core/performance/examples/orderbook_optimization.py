"""
Order Book Optimization Example

This example demonstrates how to use the performance optimization framework
to optimize order book processing in the Instinct AI trading platform.

The example compares three implementations of order book processing:
1. Baseline implementation using standard Python data structures
2. Optimized implementation using numpy arrays and vectorized operations
3. High-performance implementation using Numba JIT compilation

The results show significant performance improvements with the optimized implementations.
"""

import numpy as np
import pandas as pd
import time
import random
from typing import Dict, List, Tuple, Any

# Import performance optimization framework
import sys
import os
import pathlib

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent.absolute()
parent_dir = current_dir.parent.parent.parent
sys.path.append(str(parent_dir))

from core.performance.profiling import profile_function, FunctionProfiler
from core.performance.optimization import optimize_numpy_operations, use_numba_jit, parallelize_operations
from core.performance.benchmarking import Benchmark, benchmark_function, BenchmarkSuite


# ---- Sample Data Generation ----

def generate_order_book_data(
    num_levels: int = 10,
    num_updates: int = 1000,
    bid_ask_spread: float = 0.01,
    mid_price: float = 100.0,
    volatility: float = 0.001
) -> List[Dict[str, Any]]:
    """
    Generate synthetic order book data for testing.
    
    Args:
        num_levels: Number of price levels in the order book
        num_updates: Number of order book updates to generate
        bid_ask_spread: Initial spread between bid and ask prices
        mid_price: Initial mid price
        volatility: Volatility of price changes
        
    Returns:
        List of order book snapshots
    """
    order_books = []
    current_mid = mid_price
    
    for i in range(num_updates):
        # Randomly move the mid price
        current_mid += random.normalvariate(0, volatility) * current_mid
        
        # Calculate bid and ask prices
        best_bid = current_mid - bid_ask_spread / 2
        best_ask = current_mid + bid_ask_spread / 2
        
        # Generate bid side
        bids = []
        for level in range(num_levels):
            price = best_bid - level * 0.01 * (1 + random.random() * 0.1)
            size = random.randint(1, 100) * 10
            bids.append({"price": price, "size": size})
        
        # Generate ask side
        asks = []
        for level in range(num_levels):
            price = best_ask + level * 0.01 * (1 + random.random() * 0.1)
            size = random.randint(1, 100) * 10
            asks.append({"price": price, "size": size})
        
        # Create order book snapshot
        order_book = {
            "timestamp": time.time() + i * 0.1,
            "bids": bids,
            "asks": asks,
            "mid_price": current_mid,
            "spread": bid_ask_spread
        }
        
        order_books.append(order_book)
    
    return order_books


# ---- Baseline Implementation ----

def calculate_book_imbalance_baseline(order_book: Dict[str, Any]) -> float:
    """
    Calculate order book imbalance using the baseline implementation.
    
    Imbalance = (total_bid_value - total_ask_value) / (total_bid_value + total_ask_value)
    
    Args:
        order_book: Order book snapshot
        
    Returns:
        Order book imbalance value between -1 and 1
    """
    bids = order_book["bids"]
    asks = order_book["asks"]
    
    total_bid_value = sum(bid["price"] * bid["size"] for bid in bids)
    total_ask_value = sum(ask["price"] * ask["size"] for ask in asks)
    
    # Avoid division by zero
    if total_bid_value + total_ask_value == 0:
        return 0.0
    
    imbalance = (total_bid_value - total_ask_value) / (total_bid_value + total_ask_value)
    return imbalance


def calculate_vwap_baseline(order_book: Dict[str, Any], side: str = "bids") -> float:
    """
    Calculate Volume-Weighted Average Price (VWAP) for a side of the order book.
    
    Args:
        order_book: Order book snapshot
        side: Which side to calculate VWAP for ("bids" or "asks")
        
    Returns:
        VWAP value
    """
    orders = order_book[side]
    
    total_value = sum(order["price"] * order["size"] for order in orders)
    total_volume = sum(order["size"] for order in orders)
    
    # Avoid division by zero
    if total_volume == 0:
        return 0.0
    
    vwap = total_value / total_volume
    return vwap


def calculate_weighted_mid_price_baseline(order_book: Dict[str, Any]) -> float:
    """
    Calculate weighted mid price based on top level volumes.
    
    Args:
        order_book: Order book snapshot
        
    Returns:
        Weighted mid price
    """
    if not order_book["bids"] or not order_book["asks"]:
        return order_book["mid_price"]
    
    best_bid = order_book["bids"][0]
    best_ask = order_book["asks"][0]
    
    bid_volume = best_bid["size"]
    ask_volume = best_ask["size"]
    total_volume = bid_volume + ask_volume
    
    # Avoid division by zero
    if total_volume == 0:
        return (best_bid["price"] + best_ask["price"]) / 2
    
    weighted_mid = (best_bid["price"] * ask_volume + best_ask["price"] * bid_volume) / total_volume
    return weighted_mid


def process_order_book_baseline(order_book: Dict[str, Any]) -> Dict[str, float]:
    """
    Process an order book snapshot to calculate various metrics.
    
    Args:
        order_book: Order book snapshot
        
    Returns:
        Dictionary of calculated metrics
    """
    results = {}
    
    # Basic metrics
    results["mid_price"] = order_book["mid_price"]
    results["spread"] = order_book["spread"]
    
    # Calculate imbalance
    results["imbalance"] = calculate_book_imbalance_baseline(order_book)
    
    # Calculate VWAPs
    results["bid_vwap"] = calculate_vwap_baseline(order_book, "bids")
    results["ask_vwap"] = calculate_vwap_baseline(order_book, "asks")
    
    # Calculate weighted mid price
    results["weighted_mid"] = calculate_weighted_mid_price_baseline(order_book)
    
    # Calculate total volumes
    results["total_bid_volume"] = sum(bid["size"] for bid in order_book["bids"])
    results["total_ask_volume"] = sum(ask["size"] for ask in order_book["asks"])
    
    return results


def analyze_order_book_flow_baseline(order_books: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """
    Analyze a sequence of order book snapshots.
    
    Args:
        order_books: List of order book snapshots
        
    Returns:
        List of processed results for each snapshot
    """
    results = []
    
    for order_book in order_books:
        # Process the current order book
        metrics = process_order_book_baseline(order_book)
        
        # Add timestamp
        metrics["timestamp"] = order_book["timestamp"]
        
        results.append(metrics)
    
    return results


# ---- Optimized Implementation ----

@optimize_numpy_operations
def calculate_book_imbalance_optimized(
    bid_prices: np.ndarray,
    bid_sizes: np.ndarray,
    ask_prices: np.ndarray,
    ask_sizes: np.ndarray
) -> float:
    """
    Calculate order book imbalance using numpy operations.
    
    Args:
        bid_prices: Array of bid prices
        bid_sizes: Array of bid sizes
        ask_prices: Array of ask prices
        ask_sizes: Array of ask sizes
        
    Returns:
        Order book imbalance value
    """
    total_bid_value = np.sum(bid_prices * bid_sizes)
    total_ask_value = np.sum(ask_prices * ask_sizes)
    
    # Avoid division by zero
    denominator = total_bid_value + total_ask_value
    if denominator == 0:
        return 0.0
    
    imbalance = (total_bid_value - total_ask_value) / denominator
    return imbalance


@optimize_numpy_operations
def calculate_vwap_optimized(prices: np.ndarray, sizes: np.ndarray) -> float:
    """
    Calculate VWAP using numpy operations.
    
    Args:
        prices: Array of prices
        sizes: Array of sizes
        
    Returns:
        VWAP value
    """
    total_value = np.sum(prices * sizes)
    total_volume = np.sum(sizes)
    
    # Avoid division by zero
    if total_volume == 0:
        return 0.0
    
    vwap = total_value / total_volume
    return vwap


@optimize_numpy_operations
def calculate_weighted_mid_price_optimized(
    bid_price: float,
    bid_size: float,
    ask_price: float,
    ask_size: float
) -> float:
    """
    Calculate weighted mid price based on top level volumes.
    
    Args:
        bid_price: Best bid price
        bid_size: Best bid size
        ask_price: Best ask price
        ask_size: Best ask size
        
    Returns:
        Weighted mid price
    """
    total_volume = bid_size + ask_size
    
    # Avoid division by zero
    if total_volume == 0:
        return (bid_price + ask_price) / 2
    
    weighted_mid = (bid_price * ask_size + ask_price * bid_size) / total_volume
    return weighted_mid


def process_order_book_optimized(order_book: Dict[str, Any]) -> Dict[str, float]:
    """
    Process an order book snapshot using optimized numpy operations.
    
    Args:
        order_book: Order book snapshot
        
    Returns:
        Dictionary of calculated metrics
    """
    results = {}
    
    # Basic metrics
    results["mid_price"] = order_book["mid_price"]
    results["spread"] = order_book["spread"]
    
    # Convert to numpy arrays
    bid_prices = np.array([bid["price"] for bid in order_book["bids"]])
    bid_sizes = np.array([bid["size"] for bid in order_book["bids"]])
    ask_prices = np.array([ask["price"] for ask in order_book["asks"]])
    ask_sizes = np.array([ask["size"] for ask in order_book["asks"]])
    
    # Calculate imbalance
    results["imbalance"] = calculate_book_imbalance_optimized(
        bid_prices, bid_sizes, ask_prices, ask_sizes
    )
    
    # Calculate VWAPs
    results["bid_vwap"] = calculate_vwap_optimized(bid_prices, bid_sizes)
    results["ask_vwap"] = calculate_vwap_optimized(ask_prices, ask_sizes)
    
    # Calculate weighted mid price
    if len(bid_prices) > 0 and len(ask_prices) > 0:
        results["weighted_mid"] = calculate_weighted_mid_price_optimized(
            bid_prices[0], bid_sizes[0],
            ask_prices[0], ask_sizes[0]
        )
    else:
        results["weighted_mid"] = order_book["mid_price"]
    
    # Calculate total volumes
    results["total_bid_volume"] = np.sum(bid_sizes)
    results["total_ask_volume"] = np.sum(ask_sizes)
    
    return results


def analyze_order_book_flow_optimized(order_books: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """
    Analyze a sequence of order book snapshots using optimized operations.
    
    Args:
        order_books: List of order book snapshots
        
    Returns:
        List of processed results for each snapshot
    """
    results = []
    
    for order_book in order_books:
        # Process the current order book
        metrics = process_order_book_optimized(order_book)
        
        # Add timestamp
        metrics["timestamp"] = order_book["timestamp"]
        
        results.append(metrics)
    
    return results


# ---- High-Performance Implementation with Numba ----

try:
    import numba
    from numba import jit, float64, int64
    
    # Define Numba-optimized functions
    @use_numba_jit(nopython=True, fastmath=True)
    def calculate_book_imbalance_numba(
        bid_prices: np.ndarray,
        bid_sizes: np.ndarray,
        ask_prices: np.ndarray,
        ask_sizes: np.ndarray
    ) -> float:
        """Calculate order book imbalance using Numba."""
        total_bid_value = 0.0
        total_ask_value = 0.0
        
        # Calculate total values
        for i in range(len(bid_prices)):
            total_bid_value += bid_prices[i] * bid_sizes[i]
        
        for i in range(len(ask_prices)):
            total_ask_value += ask_prices[i] * ask_sizes[i]
        
        # Avoid division by zero
        denominator = total_bid_value + total_ask_value
        if denominator == 0:
            return 0.0
        
        imbalance = (total_bid_value - total_ask_value) / denominator
        return imbalance
    
    @use_numba_jit(nopython=True, fastmath=True)
    def calculate_vwap_numba(prices: np.ndarray, sizes: np.ndarray) -> float:
        """Calculate VWAP using Numba."""
        total_value = 0.0
        total_volume = 0.0
        
        for i in range(len(prices)):
            total_value += prices[i] * sizes[i]
            total_volume += sizes[i]
        
        # Avoid division by zero
        if total_volume == 0:
            return 0.0
        
        vwap = total_value / total_volume
        return vwap
    
    def process_order_book_numba(order_book: Dict[str, Any]) -> Dict[str, float]:
        """Process an order book snapshot using Numba-optimized functions."""
        results = {}
        
        # Basic metrics
        results["mid_price"] = order_book["mid_price"]
        results["spread"] = order_book["spread"]
        
        # Convert to numpy arrays (required for Numba)
        bid_prices = np.array([bid["price"] for bid in order_book["bids"]], dtype=np.float64)
        bid_sizes = np.array([bid["size"] for bid in order_book["bids"]], dtype=np.float64)
        ask_prices = np.array([ask["price"] for ask in order_book["asks"]], dtype=np.float64)
        ask_sizes = np.array([ask["size"] for ask in order_book["asks"]], dtype=np.float64)
        
        # Calculate imbalance
        results["imbalance"] = calculate_book_imbalance_numba(
            bid_prices, bid_sizes, ask_prices, ask_sizes
        )
        
        # Calculate VWAPs
        results["bid_vwap"] = calculate_vwap_numba(bid_prices, bid_sizes)
        results["ask_vwap"] = calculate_vwap_numba(ask_prices, ask_sizes)
        
        # Calculate weighted mid price (using numpy for simplicity)
        if len(bid_prices) > 0 and len(ask_prices) > 0:
            total_volume = bid_sizes[0] + ask_sizes[0]
            if total_volume > 0:
                weighted_mid = (bid_prices[0] * ask_sizes[0] + ask_prices[0] * bid_sizes[0]) / total_volume
                results["weighted_mid"] = weighted_mid
            else:
                results["weighted_mid"] = (bid_prices[0] + ask_prices[0]) / 2
        else:
            results["weighted_mid"] = order_book["mid_price"]
        
        # Calculate total volumes
        results["total_bid_volume"] = np.sum(bid_sizes)
        results["total_ask_volume"] = np.sum(ask_sizes)
        
        return results
    
    def analyze_order_book_flow_numba(order_books: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        """Analyze a sequence of order book snapshots using Numba-optimized functions."""
        results = []
        
        for order_book in order_books:
            # Process the current order book
            metrics = process_order_book_numba(order_book)
            
            # Add timestamp
            metrics["timestamp"] = order_book["timestamp"]
            
            results.append(metrics)
        
        return results

except ImportError:
    # Numba not available, provide fallback
    def analyze_order_book_flow_numba(order_books: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        """Fallback implementation when Numba is not available."""
        print("Numba not available, using optimized implementation instead.")
        return analyze_order_book_flow_optimized(order_books)


# ---- Parallel Implementation ----

def process_order_book_batch(order_books: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """Process a batch of order book snapshots."""
    return [process_order_book_optimized(order_book) for order_book in order_books]


def analyze_order_book_flow_parallel(
    order_books: List[Dict[str, Any]],
    batch_size: int = 100,
    n_jobs: int = 4
) -> List[Dict[str, float]]:
    """
    Analyze order book flow using parallel processing.
    
    Args:
        order_books: List of order book snapshots
        batch_size: Size of batches to process
        n_jobs: Number of parallel jobs
        
    Returns:
        List of processed results
    """
    # Split data into batches
    batches = [
        order_books[i:i + batch_size]
        for i in range(0, len(order_books), batch_size)
    ]
    
    # Process batches in parallel
    batch_results = parallelize_operations(
        process_order_book_batch,
        batches,
        n_jobs=n_jobs
    )
    
    # Flatten results
    results = []
    for batch in batch_results:
        # Add timestamps
        for i, metrics in enumerate(batch):
            if "timestamp" not in metrics:
                batch_index = batch_results.index(batch)
                original_index = batch_index * batch_size + i
                if original_index < len(order_books):
                    metrics["timestamp"] = order_books[original_index]["timestamp"]
        
        results.extend(batch)
    
    return results


# ---- Benchmark and Compare ----

def main():
    """Run benchmarks and compare implementations."""
    print("Generating sample order book data...")
    order_books = generate_order_book_data(
        num_levels=20,
        num_updates=1000,
        bid_ask_spread=0.05,
        mid_price=100.0,
        volatility=0.001
    )
    
    print(f"Generated {len(order_books)} order book snapshots.")
    
    # Create benchmark suite
    suite = BenchmarkSuite(
        "Order Book Processing Comparison",
        save_results=True,
        save_directory="benchmarks/order_book"
    )
    
    # Add benchmarks
    suite.add_benchmark(
        "baseline",
        analyze_order_book_flow_baseline,
        args=(order_books,),
        iterations=10,
        warmup_iterations=2,
        metadata={"description": "Standard Python implementation"}
    )
    
    suite.add_benchmark(
        "optimized",
        analyze_order_book_flow_optimized,
        args=(order_books,),
        iterations=10,
        warmup_iterations=2,
        metadata={"description": "Numpy-optimized implementation"}
    )
    
    suite.add_benchmark(
        "numba",
        analyze_order_book_flow_numba,
        args=(order_books,),
        iterations=10,
        warmup_iterations=2,
        metadata={"description": "Numba JIT-compiled implementation"}
    )
    
    suite.add_benchmark(
        "parallel",
        analyze_order_book_flow_parallel,
        args=(order_books, 100, 4),
        iterations=10,
        warmup_iterations=2,
        metadata={"description": "Parallel processing implementation with 4 workers"}
    )
    
    # Run benchmarks
    print("Running benchmarks...")
    results = suite.run_all()
    
    # Compare results
    print("\nBenchmark Results:")
    suite.compare_results(baseline="baseline")
    
    # Plot comparison
    suite.plot_comparison(metric="mean_time", baseline="baseline")
    
    # Verify implementations produce the same results
    print("\nVerifying result consistency...")
    baseline_results = analyze_order_book_flow_baseline(order_books[:10])
    optimized_results = analyze_order_book_flow_optimized(order_books[:10])
    numba_results = analyze_order_book_flow_numba(order_books[:10])
    
    # Compare a few key metrics for the first snapshot
    print("First snapshot metrics comparison:")
    for impl, res in [
        ("Baseline", baseline_results[0]),
        ("Optimized", optimized_results[0]),
        ("Numba", numba_results[0])
    ]:
        print(f"  {impl}: imbalance={res['imbalance']:.6f}, "
              f"bid_vwap={res['bid_vwap']:.6f}, "
              f"ask_vwap={res['ask_vwap']:.6f}")


if __name__ == "__main__":
    main() 