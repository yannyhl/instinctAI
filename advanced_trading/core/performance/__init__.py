"""
Performance Optimization Framework

This module provides tools and utilities for optimizing the performance of critical
system components in the Instinct AI trading platform. It includes:

1. Profiling tools for identifying performance bottlenecks
2. Memory optimization utilities for efficient resource usage
3. Critical path optimization for latency-sensitive operations
4. Concurrency utilities for parallelizing operations
5. Benchmarking tools for measuring performance improvements

Usage:
    from advanced_trading.core.performance import profile_function
    
    @profile_function
    def my_critical_function():
        # Function implementation
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union, cast
import time
import functools
import cProfile
import pstats
import io
import os
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Configure logging
logger = logging.getLogger(__name__)

# Type definitions
F = TypeVar('F', bound=Callable[..., Any])

# Import submodules
from .profiling import (
    profile_function, 
    ProfileResult, 
    FunctionProfiler,
    memory_usage,
    trace_memory_allocations
)

from .optimization import (
    optimize_numpy_operations,
    use_numba_jit,
    parallelize_operations,
    batch_process,
    use_shared_memory
)

from .concurrency import (
    ProcessPool,
    ThreadPool,
    ConcurrentTaskManager,
    SharedMemoryManager,
    LockFreeQueue,
    AsyncExecutor
)

from .benchmarking import (
    Benchmark,
    benchmark_function,
    BenchmarkSuite,
    BenchmarkResult,
    compare_benchmarks
)

__all__ = [
    # Profiling tools
    'profile_function',
    'ProfileResult',
    'FunctionProfiler',
    'memory_usage',
    'trace_memory_allocations',
    
    # Optimization utilities
    'optimize_numpy_operations',
    'use_numba_jit',
    'parallelize_operations',
    'batch_process',
    'use_shared_memory',
    
    # Concurrency utilities
    'ProcessPool',
    'ThreadPool',
    'ConcurrentTaskManager',
    'SharedMemoryManager',
    'LockFreeQueue',
    'AsyncExecutor',
    
    # Benchmarking tools
    'Benchmark',
    'benchmark_function',
    'BenchmarkSuite',
    'BenchmarkResult',
    'compare_benchmarks',
] 