"""
Performance Profiling Module

This module provides tools for profiling and analyzing the performance of functions and
code blocks in the Instinct AI trading platform. It includes tools for:

1. Function profiling with detailed statistics
2. Memory usage tracking
3. Call graph generation
4. Hotspot identification
5. Performance reporting

These tools are designed to help identify bottlenecks in critical code paths,
particularly in latency-sensitive operations like order book processing,
market data handling, and trade execution.
"""

import cProfile
import pstats
import io
import os
import time
import functools
import logging
import tracemalloc
import gc
import sys
import threading
import inspect
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union, cast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Type definitions
F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class ProfileResult:
    """
    Container for profiling results with detailed performance statistics.
    """
    function_name: str
    execution_time: float
    cpu_time: float
    call_count: int
    timestamp: datetime = field(default_factory=datetime.now)
    stats: Optional[pstats.Stats] = None
    memory_before: Optional[int] = None
    memory_after: Optional[int] = None
    memory_diff: Optional[int] = None
    
    def __str__(self) -> str:
        """String representation of profiling results."""
        result = f"Profile results for {self.function_name}:\n"
        result += f"  Execution time: {self.execution_time:.6f} seconds\n"
        result += f"  CPU time: {self.cpu_time:.6f} seconds\n"
        result += f"  Call count: {self.call_count}\n"
        
        if self.memory_before is not None and self.memory_after is not None:
            result += f"  Memory before: {self.memory_before / (1024 * 1024):.2f} MB\n"
            result += f"  Memory after: {self.memory_after / (1024 * 1024):.2f} MB\n"
            result += f"  Memory diff: {self.memory_diff / (1024 * 1024):.2f} MB\n"
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profiling results to a dictionary."""
        return {
            "function_name": self.function_name,
            "execution_time": self.execution_time,
            "cpu_time": self.cpu_time,
            "call_count": self.call_count,
            "timestamp": self.timestamp.isoformat(),
            "memory_before": self.memory_before,
            "memory_after": self.memory_after,
            "memory_diff": self.memory_diff,
        }
    
    def print_detailed_stats(self, top_n: int = 10) -> None:
        """
        Print detailed profiling statistics including top-N slowest functions.
        
        Args:
            top_n: Number of top functions to show (by cumulative time)
        """
        if self.stats is None:
            logger.warning("No detailed stats available for %s", self.function_name)
            return
        
        # Create a string stream to capture stats output
        stream = io.StringIO()
        stats = self.stats
        
        # Sort stats and print to stream
        stats.sort_stats("cumulative")
        stats.print_stats(top_n)
        
        print(stream.getvalue())


class FunctionProfiler:
    """
    Profile a function or block of code with detailed performance metrics.
    
    Features:
    - CPU profiling (time spent in function and callees)
    - Memory usage tracking
    - Call count tracking
    - Support for profiling specific sections with context manager
    
    Usage as decorator:
        @FunctionProfiler(track_memory=True)
        def my_function():
            # Function implementation
    
    Usage as context manager:
        with FunctionProfiler("critical_section", track_memory=True) as profiler:
            # Critical code section
    """
    
    def __init__(
        self, 
        name: Optional[str] = None, 
        track_memory: bool = False,
        detailed: bool = True,
        show_results: bool = True
    ):
        """
        Initialize the profiler.
        
        Args:
            name: Name of the function or code block (optional, derived from function if used as decorator)
            track_memory: Whether to track memory usage before and after execution
            detailed: Whether to collect detailed profile statistics
            show_results: Whether to print results after profiling
        """
        self.name = name
        self.track_memory = track_memory
        self.detailed = detailed
        self.show_results = show_results
        self.profile = cProfile.Profile()
        self.result: Optional[ProfileResult] = None
        self.memory_before: Optional[int] = None
        self.memory_after: Optional[int] = None
    
    def __call__(self, func: F) -> F:
        """
        Use as a decorator to profile a function.
        
        Args:
            func: The function to profile
            
        Returns:
            Wrapped function that includes profiling
        """
        # Use function name if name not provided
        if self.name is None:
            self.name = func.__name__
            
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
                
        return cast(F, wrapper)
    
    def __enter__(self) -> 'FunctionProfiler':
        """
        Enter the context manager for profiling a code block.
        
        Returns:
            The profiler instance for reference
        """
        if self.track_memory:
            # Run garbage collection to get accurate memory measurements
            gc.collect()
            self.memory_before = self._get_memory_usage()
        
        # Start timing and profiling
        self.start_time = time.time()
        self.profile.enable()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit the context manager and calculate profiling results.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        # Stop profiling
        self.profile.disable()
        
        # Calculate execution time
        execution_time = time.time() - self.start_time
        
        # Get CPU statistics from profile
        s = io.StringIO()
        ps = pstats.Stats(self.profile, stream=s)
        
        if self.track_memory:
            # Measure memory after execution
            gc.collect()
            self.memory_after = self._get_memory_usage()
            memory_diff = self.memory_after - self.memory_before if self.memory_before is not None else None
        else:
            self.memory_before = None
            self.memory_after = None
            memory_diff = None
        
        # Create result object
        self.result = ProfileResult(
            function_name=self.name or "anonymous_function",
            execution_time=execution_time,
            cpu_time=sum(self.profile.getstats()[0][2:4]),  # sum of tottime and cumtime
            call_count=len(self.profile.getstats()),
            stats=ps if self.detailed else None,
            memory_before=self.memory_before,
            memory_after=self.memory_after,
            memory_diff=memory_diff
        )
        
        # Show results if requested
        if self.show_results and self.result:
            print(self.result)
            if self.detailed:
                self.result.print_detailed_stats()
    
    def _get_memory_usage(self) -> int:
        """
        Get current memory usage of the process.
        
        Returns:
            Memory usage in bytes
        """
        # Try to use the most accurate method available for the current system
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except ImportError:
            # Fall back to less accurate method
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def profile_function(
    func: Optional[F] = None, 
    *,
    track_memory: bool = False,
    detailed: bool = True,
    show_results: bool = True
) -> Union[F, Callable[[F], F]]:
    """
    Decorator to profile a function.
    
    Args:
        func: The function to profile
        track_memory: Whether to track memory usage
        detailed: Whether to collect detailed profile statistics
        show_results: Whether to print results after profiling
        
    Returns:
        Decorated function
        
    Usage:
        @profile_function(track_memory=True)
        def my_function():
            # Function implementation
    """
    def decorator(f: F) -> F:
        return FunctionProfiler(
            track_memory=track_memory,
            detailed=detailed,
            show_results=show_results
        )(f)
    
    if func is None:
        return decorator
    
    return decorator(func)


def memory_usage(size_only: bool = False) -> Union[int, Dict[str, Any]]:
    """
    Get memory usage statistics for the current process.
    
    Args:
        size_only: If True, return only the total memory usage in bytes
                  If False, return detailed statistics
                  
    Returns:
        Memory usage information (either an integer or a dictionary)
    """
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        if size_only:
            return memory_info.rss
        
        return {
            "rss": memory_info.rss,  # Resident Set Size
            "vms": memory_info.vms,  # Virtual Memory Size
            "shared": getattr(memory_info, "shared", 0),  # Shared memory
            "text": getattr(memory_info, "text", 0),  # Text segment memory (code)
            "lib": getattr(memory_info, "lib", 0),  # Library memory
            "data": getattr(memory_info, "data", 0),  # Data + stack
            "dirty": getattr(memory_info, "dirty", 0),  # Dirty pages
        }
    except ImportError:
        # Fallback to resource module for basic information
        import resource
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        
        if size_only:
            return mem
        
        return {
            "rss": mem,
            "detailed": "Not available (psutil not installed)"
        }


def trace_memory_allocations(
    func: Optional[F] = None,
    *,
    top_n: int = 10,
    key_type: str = "lineno",
    show_results: bool = True
) -> Union[F, Callable[[F], F]]:
    """
    Decorator to trace memory allocations in a function, showing where memory
    is being allocated.
    
    Args:
        func: Function to trace
        top_n: Number of top allocations to show
        key_type: Type of grouping for allocations ("lineno", "traceback", or "filename")
        show_results: Whether to print results after execution
        
    Returns:
        Decorated function
        
    Usage:
        @trace_memory_allocations(top_n=20)
        def memory_intensive_function():
            # Function implementation
    """
    def decorator(f: F) -> F:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Start tracemalloc
            tracemalloc.start()

            # Run function
            result = f(*args, **kwargs)

            # Get memory snapshot
            snapshot = tracemalloc.take_snapshot()
            tracemalloc.stop()

            if show_results:
                print(f"\nMemory allocation trace for {f.__name__}:")
                if key_type == "lineno":
                    stats = snapshot.statistics("lineno")
                elif key_type == "traceback":
                    stats = snapshot.statistics("traceback")
                elif key_type == "filename":
                    stats = snapshot.statistics("filename")
                else:
                    stats = snapshot.statistics("lineno")
                
                for stat in stats[:top_n]:
                    print(f"{stat.count} allocations: {stat.size / 1024:.1f} KiB")
                    if key_type != "lineno" and hasattr(stat, "traceback"):
                        frames = stat.traceback.format()
                        for frame in frames:
                            print(f"    {frame}")
                    else:
                        print(f"    {stat.traceback.format()[-1] if hasattr(stat, 'traceback') else 'unknown'}")
            
            return result
        
        return cast(F, wrapper)
    
    if func is None:
        return decorator
    
    return decorator(func) 