"""
Benchmarking Module

This module provides tools for measuring and tracking the performance of
critical components in the Instinct AI trading platform. It includes:

1. Benchmarking utilities for functions and code blocks
2. Performance tracking over time
3. Comparative benchmarking across implementations
4. Statistical analysis of benchmark results
5. Visualization tools for performance metrics

These tools help identify and document performance improvements and
regressions, ensuring the system maintains optimal performance.
"""

import time
import logging
import statistics
import functools
import gc
import os
import json
import datetime
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union, cast
import uuid
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Type definitions
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')


@dataclass
class BenchmarkResult:
    """
    Container for benchmark results with statistical metrics.
    """
    name: str
    iterations: int
    total_time: float
    mean_time: float
    median_time: float
    min_time: float
    max_time: float
    std_dev: float
    percentile_90: float
    percentile_95: float
    percentile_99: float
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_times: List[float] = field(default_factory=list)
    
    def __str__(self) -> str:
        """String representation of benchmark results."""
        result = f"Benchmark results for {self.name} ({self.iterations} iterations):\n"
        result += f"  Total time: {self.total_time:.6f} seconds\n"
        result += f"  Mean time: {self.mean_time:.6f} seconds\n"
        result += f"  Median time: {self.median_time:.6f} seconds\n"
        result += f"  Min time: {self.min_time:.6f} seconds\n"
        result += f"  Max time: {self.max_time:.6f} seconds\n"
        result += f"  Std dev: {self.std_dev:.6f} seconds\n"
        result += f"  90th percentile: {self.percentile_90:.6f} seconds\n"
        result += f"  95th percentile: {self.percentile_95:.6f} seconds\n"
        result += f"  99th percentile: {self.percentile_99:.6f} seconds\n"
        
        if self.metadata:
            result += "  Metadata:\n"
            for key, value in self.metadata.items():
                result += f"    {key}: {value}\n"
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert benchmark results to a dictionary."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result
    
    def save_to_file(self, directory: str = "benchmarks") -> str:
        """
        Save benchmark results to a JSON file.
        
        Args:
            directory: Directory to save results in
            
        Returns:
            Path to the saved file
        """
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Generate filename based on benchmark name and timestamp
        filename = f"{self.name}_{self.timestamp.strftime('%Y%m%d%H%M%S')}.json"
        filepath = os.path.join(directory, filename)
        
        # Save results to file
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        
        return filepath
    
    def plot(self, show_histogram: bool = True, show_timeseries: bool = True) -> None:
        """
        Plot benchmark results.
        
        Args:
            show_histogram: Whether to show a histogram of execution times
            show_timeseries: Whether to show a time series of execution times
        """
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            if show_histogram and self.raw_times:
                plt.figure(figsize=(10, 6))
                plt.hist(self.raw_times, bins=30, alpha=0.7)
                plt.axvline(self.mean_time, color='r', linestyle='dashed', linewidth=2, label=f'Mean: {self.mean_time:.6f}s')
                plt.axvline(self.median_time, color='g', linestyle='dashed', linewidth=2, label=f'Median: {self.median_time:.6f}s')
                plt.axvline(self.percentile_95, color='b', linestyle='dashed', linewidth=2, label=f'95th: {self.percentile_95:.6f}s')
                plt.xlabel('Execution Time (seconds)')
                plt.ylabel('Frequency')
                plt.title(f'Execution Time Distribution for {self.name}')
                plt.legend()
                plt.tight_layout()
                plt.show()
            
            if show_timeseries and self.raw_times:
                plt.figure(figsize=(10, 6))
                plt.plot(range(len(self.raw_times)), self.raw_times, marker='.', alpha=0.7)
                plt.axhline(self.mean_time, color='r', linestyle='dashed', linewidth=2, label=f'Mean: {self.mean_time:.6f}s')
                plt.axhline(self.median_time, color='g', linestyle='dashed', linewidth=2, label=f'Median: {self.median_time:.6f}s')
                plt.axhline(self.percentile_95, color='b', linestyle='dashed', linewidth=2, label=f'95th: {self.percentile_95:.6f}s')
                plt.xlabel('Iteration')
                plt.ylabel('Execution Time (seconds)')
                plt.title(f'Execution Time Series for {self.name}')
                plt.legend()
                plt.tight_layout()
                plt.show()
        except ImportError:
            logger.warning("Matplotlib not available. Cannot plot benchmark results.")


class Benchmark:
    """
    Benchmark a function or code block with detailed performance metrics.
    
    Features:
    - Statistical analysis of execution times
    - Warm-up iterations
    - Garbage collection control
    - Result persistence
    - Result visualization
    
    Usage as decorator:
        @Benchmark(iterations=100)
        def my_function():
            # Function implementation
    
    Usage as context manager:
        with Benchmark("critical_section", iterations=100) as benchmark:
            # Critical code section
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        iterations: int = 100,
        warmup_iterations: int = 5,
        gc_before: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize benchmark.
        
        Args:
            name: Name of the function or code block
            iterations: Number of iterations to run
            warmup_iterations: Number of warmup iterations to run before timing
            gc_before: Whether to run garbage collection before benchmarking
            metadata: Additional metadata to store with benchmark results
        """
        self.name = name
        self.iterations = iterations
        self.warmup_iterations = warmup_iterations
        self.gc_before = gc_before
        self.metadata = metadata or {}
        self.result: Optional[BenchmarkResult] = None
        self.raw_times: List[float] = []
    
    def __call__(self, func: F) -> F:
        """
        Use as a decorator to benchmark a function.
        
        Args:
            func: Function to benchmark
            
        Returns:
            Benchmarked function
        """
        # Use function name if name not provided
        if self.name is None:
            self.name = func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Run warmup iterations
            for _ in range(self.warmup_iterations):
                func(*args, **kwargs)
            
            # Run garbage collection if requested
            if self.gc_before:
                gc.collect()
            
            # Run benchmarked iterations
            self.raw_times = []
            for _ in range(self.iterations):
                start_time = time.perf_counter()
                result = func(*args, **kwargs)
                end_time = time.perf_counter()
                self.raw_times.append(end_time - start_time)
            
            # Calculate benchmark metrics
            self._calculate_metrics()
            
            # Return original function result
            return result
        
        return cast(F, wrapper)
    
    def __enter__(self) -> 'Benchmark':
        """
        Enter context manager to benchmark a code block.
        
        Returns:
            Benchmark instance
        """
        # Generate a name if not provided
        if self.name is None:
            self.name = f"benchmark_{uuid.uuid4().hex[:8]}"
        
        # Run warmup iterations (empty for context manager)
        for _ in range(self.warmup_iterations):
            pass
        
        # Run garbage collection if requested
        if self.gc_before:
            gc.collect()
        
        # Reset raw times
        self.raw_times = []
        
        # Start timing
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit context manager and calculate benchmark metrics.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        # Only calculate metrics if no exception was raised
        if exc_type is None:
            # Record single execution time for context manager
            execution_time = time.perf_counter() - self.start_time
            self.raw_times = [execution_time]
            
            # Calculate benchmark metrics
            self._calculate_metrics()
            
            # Print results
            if self.result:
                print(self.result)
    
    def _calculate_metrics(self) -> None:
        """Calculate benchmark metrics from raw execution times."""
        if not self.raw_times:
            logger.warning("No execution times recorded for benchmark %s", self.name)
            return
        
        # Calculate metrics
        total_time = sum(self.raw_times)
        mean_time = total_time / len(self.raw_times)
        median_time = statistics.median(self.raw_times)
        min_time = min(self.raw_times)
        max_time = max(self.raw_times)
        
        # Calculate additional statistics
        if len(self.raw_times) > 1:
            std_dev = statistics.stdev(self.raw_times)
        else:
            std_dev = 0.0
        
        # Calculate percentiles
        sorted_times = sorted(self.raw_times)
        percentile_90 = sorted_times[int(0.9 * len(sorted_times))]
        percentile_95 = sorted_times[int(0.95 * len(sorted_times))]
        percentile_99 = sorted_times[int(0.99 * len(sorted_times))]
        
        # Create result object
        self.result = BenchmarkResult(
            name=self.name or "anonymous_benchmark",
            iterations=len(self.raw_times),
            total_time=total_time,
            mean_time=mean_time,
            median_time=median_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            percentile_90=percentile_90,
            percentile_95=percentile_95,
            percentile_99=percentile_99,
            metadata=self.metadata,
            raw_times=self.raw_times
        )


def benchmark_function(
    func: Callable[..., T],
    args: Tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
    iterations: int = 100,
    warmup_iterations: int = 5,
    gc_before: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> BenchmarkResult:
    """
    Benchmark a function with specified arguments.
    
    Args:
        func: Function to benchmark
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        iterations: Number of iterations to run
        warmup_iterations: Number of warmup iterations
        gc_before: Whether to run garbage collection before benchmarking
        metadata: Additional metadata to store with results
        
    Returns:
        Benchmark result
        
    Usage:
        result = benchmark_function(calculate_indicators, args=(data,), iterations=1000)
        print(result)
    """
    kwargs = kwargs or {}
    metadata = metadata or {}
    
    # Set function name in metadata
    if "function_name" not in metadata:
        metadata["function_name"] = func.__name__
    
    # Run warmup iterations
    for _ in range(warmup_iterations):
        func(*args, **kwargs)
    
    # Run garbage collection if requested
    if gc_before:
        gc.collect()
    
    # Run benchmarked iterations
    raw_times = []
    for _ in range(iterations):
        start_time = time.perf_counter()
        func(*args, **kwargs)
        end_time = time.perf_counter()
        raw_times.append(end_time - start_time)
    
    # Calculate benchmark metrics
    total_time = sum(raw_times)
    mean_time = total_time / len(raw_times)
    median_time = statistics.median(raw_times)
    min_time = min(raw_times)
    max_time = max(raw_times)
    
    # Calculate additional statistics
    std_dev = statistics.stdev(raw_times) if len(raw_times) > 1 else 0.0
    
    # Calculate percentiles
    sorted_times = sorted(raw_times)
    percentile_90 = sorted_times[int(0.9 * len(sorted_times))]
    percentile_95 = sorted_times[int(0.95 * len(sorted_times))]
    percentile_99 = sorted_times[int(0.99 * len(sorted_times))]
    
    # Create result object
    result = BenchmarkResult(
        name=func.__name__,
        iterations=iterations,
        total_time=total_time,
        mean_time=mean_time,
        median_time=median_time,
        min_time=min_time,
        max_time=max_time,
        std_dev=std_dev,
        percentile_90=percentile_90,
        percentile_95=percentile_95,
        percentile_99=percentile_99,
        metadata=metadata,
        raw_times=raw_times
    )
    
    return result


class BenchmarkSuite:
    """
    Run and compare multiple benchmarks.
    
    Features:
    - Consistent environment across benchmarks
    - Statistical comparison of implementations
    - Result persistence and tracking
    - Visualization of comparative performance
    
    Usage:
        suite = BenchmarkSuite("Algorithm Comparison")
        suite.add_benchmark("baseline", baseline_algo, args=(data,))
        suite.add_benchmark("optimized", optimized_algo, args=(data,))
        results = suite.run_all()
        suite.compare_results()
    """
    
    def __init__(self, name: str, save_results: bool = True, save_directory: str = "benchmarks"):
        """
        Initialize benchmark suite.
        
        Args:
            name: Name of the benchmark suite
            save_results: Whether to save results to files
            save_directory: Directory to save results in
        """
        self.name = name
        self.save_results = save_results
        self.save_directory = save_directory
        self.benchmarks: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, BenchmarkResult] = {}
    
    def add_benchmark(
        self,
        name: str,
        func: Callable[..., Any],
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        iterations: int = 100,
        warmup_iterations: int = 5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a benchmark to the suite.
        
        Args:
            name: Name of the benchmark
            func: Function to benchmark
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            iterations: Number of iterations to run
            warmup_iterations: Number of warmup iterations
            metadata: Additional metadata to store with results
        """
        self.benchmarks[name] = {
            "function": func,
            "args": args,
            "kwargs": kwargs or {},
            "iterations": iterations,
            "warmup_iterations": warmup_iterations,
            "metadata": metadata or {}
        }
    
    def run_benchmark(self, name: str) -> BenchmarkResult:
        """
        Run a specific benchmark.
        
        Args:
            name: Name of the benchmark to run
            
        Returns:
            Benchmark result
        """
        if name not in self.benchmarks:
            raise ValueError(f"Benchmark '{name}' not found in suite")
        
        benchmark = self.benchmarks[name]
        
        # Add suite name to metadata
        metadata = benchmark["metadata"].copy()
        metadata["suite_name"] = self.name
        
        # Run benchmark
        result = benchmark_function(
            func=benchmark["function"],
            args=benchmark["args"],
            kwargs=benchmark["kwargs"],
            iterations=benchmark["iterations"],
            warmup_iterations=benchmark["warmup_iterations"],
            metadata=metadata
        )
        
        # Store result
        self.results[name] = result
        
        # Save result if requested
        if self.save_results:
            result.save_to_file(self.save_directory)
        
        return result
    
    def run_all(self) -> Dict[str, BenchmarkResult]:
        """
        Run all benchmarks in the suite.
        
        Returns:
            Dictionary of benchmark results indexed by name
        """
        for name in self.benchmarks:
            self.run_benchmark(name)
        
        return self.results
    
    def compare_results(self, baseline: Optional[str] = None) -> None:
        """
        Compare benchmark results.
        
        Args:
            baseline: Name of the benchmark to use as baseline (default is first added)
        """
        if not self.results:
            logger.warning("No benchmark results to compare")
            return
        
        # Use first benchmark as baseline if not specified
        if baseline is None:
            baseline = next(iter(self.results.keys()))
        elif baseline not in self.results:
            raise ValueError(f"Baseline benchmark '{baseline}' not found in results")
        
        baseline_result = self.results[baseline]
        baseline_mean = baseline_result.mean_time
        
        # Print comparison
        print(f"Benchmark comparison for suite '{self.name}':")
        print(f"  Baseline: {baseline} - {baseline_mean:.6f} seconds")
        
        for name, result in self.results.items():
            if name == baseline:
                continue
            
            mean_time = result.mean_time
            relative = mean_time / baseline_mean
            diff_percent = (relative - 1.0) * 100
            
            if diff_percent > 0:
                diff_str = f"{diff_percent:.2f}% slower"
            else:
                diff_str = f"{-diff_percent:.2f}% faster"
            
            print(f"  {name}: {mean_time:.6f} seconds ({diff_str} than baseline)")
    
    def plot_comparison(self, metric: str = "mean_time", baseline: Optional[str] = None) -> None:
        """
        Plot comparison of benchmark results.
        
        Args:
            metric: Metric to compare ("mean_time", "median_time", etc.)
            baseline: Name of the benchmark to use as baseline
        """
        if not self.results:
            logger.warning("No benchmark results to plot")
            return
        
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            # Get metric values for each benchmark
            names = []
            values = []
            
            for name, result in self.results.items():
                if not hasattr(result, metric):
                    logger.warning(f"Metric '{metric}' not found in benchmark result '{name}'")
                    continue
                
                names.append(name)
                values.append(getattr(result, metric))
            
            # Plot comparison
            plt.figure(figsize=(10, 6))
            bars = plt.bar(names, values, alpha=0.7)
            
            # Highlight baseline if specified
            if baseline and baseline in self.results and baseline in names:
                idx = names.index(baseline)
                bars[idx].set_color('r')
            
            plt.xlabel('Benchmark')
            plt.ylabel(f'{metric.replace("_", " ").title()} (seconds)')
            plt.title(f'Comparison of {metric.replace("_", " ").title()} - {self.name}')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            plt.show()
        except ImportError:
            logger.warning("Matplotlib not available. Cannot plot comparison.")


def compare_benchmarks(
    benchmarks: Dict[str, BenchmarkResult],
    baseline: Optional[str] = None,
    metrics: Optional[List[str]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Compare multiple benchmark results.
    
    Args:
        benchmarks: Dictionary of benchmark results indexed by name
        baseline: Name of the benchmark to use as baseline
        metrics: List of metrics to compare
        
    Returns:
        Dictionary of comparison results
        
    Usage:
        comparison = compare_benchmarks(
            {"baseline": baseline_result, "optimized": optimized_result}
        )
        print(comparison)
    """
    if not benchmarks:
        return {}
    
    # Use first benchmark as baseline if not specified
    if baseline is None:
        baseline = next(iter(benchmarks.keys()))
    elif baseline not in benchmarks:
        raise ValueError(f"Baseline benchmark '{baseline}' not found in benchmarks")
    
    # Default metrics to compare
    if metrics is None:
        metrics = ["mean_time", "median_time", "percentile_95"]
    
    baseline_result = benchmarks[baseline]
    comparison = {}
    
    for name, result in benchmarks.items():
        if name == baseline:
            continue
        
        comparison[name] = {}
        
        for metric in metrics:
            if not hasattr(baseline_result, metric) or not hasattr(result, metric):
                logger.warning(f"Metric '{metric}' not found in benchmark results")
                continue
            
            baseline_value = getattr(baseline_result, metric)
            current_value = getattr(result, metric)
            
            # Avoid division by zero
            if baseline_value == 0:
                relative = float('inf') if current_value > 0 else 1.0
            else:
                relative = current_value / baseline_value
            
            diff_percent = (relative - 1.0) * 100
            
            comparison[name][metric] = current_value
            comparison[name][f"{metric}_relative"] = relative
            comparison[name][f"{metric}_diff_percent"] = diff_percent
    
    return comparison 