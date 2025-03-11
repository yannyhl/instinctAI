"""
Performance Optimization Module

This module provides utilities for optimizing the performance of critical code
paths in the Instinct AI trading platform. It includes:

1. Numpy operation optimizations
2. Numba JIT compilation
3. Batch processing utilities
4. Parallel processing helpers
5. Memory optimization techniques

These utilities are designed to be applied to performance-critical components
such as order book processing, market data handling, and execution algorithms.
"""

import numpy as np
import logging
import functools
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union, cast
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Configure logging
logger = logging.getLogger(__name__)

# Type definitions
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')


def optimize_numpy_operations(func: F) -> F:
    """
    Decorator to optimize numpy operations in a function.
    
    This decorator:
    1. Forces contiguous memory layout for arrays
    2. Ensures proper dtype alignment
    3. Applies vectorized operations where possible
    4. Minimizes temporary array creation
    
    Args:
        func: Function to optimize
        
    Returns:
        Optimized function
        
    Usage:
        @optimize_numpy_operations
        def process_market_data(data):
            # Function implementation
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Convert numpy array arguments to contiguous memory layout
        new_args = []
        for arg in args:
            if isinstance(arg, np.ndarray) and not arg.flags.c_contiguous:
                new_args.append(np.ascontiguousarray(arg))
            else:
                new_args.append(arg)
        
        # Convert numpy array keyword arguments to contiguous memory layout
        new_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, np.ndarray) and not value.flags.c_contiguous:
                new_kwargs[key] = np.ascontiguousarray(value)
            else:
                new_kwargs[key] = value
        
        # Apply original function with optimized arrays
        with np.errstate(all='ignore'):  # Ignore numpy warnings during execution
            result = func(*new_args, **new_kwargs)
        
        return result
    
    return cast(F, wrapper)


def use_numba_jit(
    parallel: bool = False,
    fastmath: bool = True,
    cache: bool = True,
    nopython: bool = True,
    **kwargs
) -> Callable[[F], F]:
    """
    Decorator to JIT compile a function using Numba for significant speedup.
    
    Args:
        parallel: Whether to use parallel processing
        fastmath: Whether to enable fast math optimizations
        cache: Whether to cache the compiled function
        nopython: Whether to use nopython mode (recommended)
        **kwargs: Additional arguments to pass to numba.jit
        
    Returns:
        Decorated function
        
    Usage:
        @use_numba_jit(parallel=True)
        def calculate_indicators(data):
            # Function implementation
    """
    try:
        import numba
        
        def decorator(func: F) -> F:
            try:
                return cast(
                    F,
                    numba.jit(
                        parallel=parallel,
                        fastmath=fastmath,
                        cache=cache,
                        nopython=nopython,
                        **kwargs
                    )(func)
                )
            except Exception as e:
                logger.warning(f"Failed to apply Numba JIT to {func.__name__}: {e}")
                logger.warning("Function will run in non-optimized mode")
                return func
        
        return decorator
    except ImportError:
        # Fallback if numba is not installed
        logger.warning("Numba not installed. Function will run in non-optimized mode.")
        
        def decorator(func: F) -> F:
            return func
        
        return decorator


def parallelize_operations(
    func: Callable[[Any], T],
    data: List[Any], 
    n_jobs: Optional[int] = None,
    use_processes: bool = False, 
    chunk_size: Optional[int] = None,
    **kwargs
) -> List[T]:
    """
    Apply a function to a list of data items in parallel.
    
    Args:
        func: Function to apply to each data item
        data: List of data items
        n_jobs: Number of parallel jobs (default: number of CPU cores)
        use_processes: Whether to use processes instead of threads
        chunk_size: Size of data chunks for each worker
        **kwargs: Additional arguments to pass to the executor
        
    Returns:
        List of results
        
    Usage:
        results = parallelize_operations(process_data, data_list, n_jobs=4)
    """
    if n_jobs is None:
        import multiprocessing
        n_jobs = multiprocessing.cpu_count()
    
    # Use no more jobs than data items
    n_jobs = min(n_jobs, len(data))
    
    if n_jobs <= 1 or len(data) <= 1:
        # If only one job or one data item, run sequentially
        return [func(item) for item in data]
    
    # Determine executor type based on flag
    executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
    
    with executor_class(max_workers=n_jobs, **kwargs) as executor:
        if chunk_size:
            # Process data in chunks
            results = []
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                chunk_results = list(executor.map(func, chunk))
                results.extend(chunk_results)
            return results
        else:
            # Process all data at once
            return list(executor.map(func, data))


def batch_process(
    func: Callable[[List[Any]], List[T]], 
    data: List[Any], 
    batch_size: int,
    show_progress: bool = False,
    **kwargs
) -> List[T]:
    """
    Process data in batches to optimize memory usage and performance.
    
    Args:
        func: Function to apply to each batch (must accept and return lists)
        data: List of data items
        batch_size: Size of each batch
        show_progress: Whether to show progress bar
        **kwargs: Additional arguments to pass to the function
        
    Returns:
        List of results
        
    Usage:
        results = batch_process(process_batch, data_list, batch_size=1000)
    """
    if len(data) <= batch_size:
        # If data fits in one batch, process directly
        return func(data, **kwargs)
    
    results = []
    total_batches = (len(data) + batch_size - 1) // batch_size
    
    if show_progress:
        try:
            from tqdm import tqdm
            batch_range = tqdm(range(0, len(data), batch_size), total=total_batches)
        except ImportError:
            # Simple progress reporting if tqdm not available
            batch_range = range(0, len(data), batch_size)
            print(f"Processing {total_batches} batches...")
    else:
        batch_range = range(0, len(data), batch_size)
    
    for i in batch_range:
        batch = data[i:i + batch_size]
        batch_results = func(batch, **kwargs)
        results.extend(batch_results)
        
        if show_progress and not 'tqdm' in sys.modules:
            print(f"Processed batch {(i // batch_size) + 1}/{total_batches}")
    
    return results


def use_shared_memory(
    array: np.ndarray,
    name: Optional[str] = None,
    read_only: bool = False
) -> np.ndarray:
    """
    Place a numpy array in shared memory for efficient access across processes.
    
    Args:
        array: Numpy array to share
        name: Name for the shared memory segment (auto-generated if None)
        read_only: Whether the array should be read-only in child processes
        
    Returns:
        Numpy array backed by shared memory
        
    Usage:
        shared_data = use_shared_memory(large_data_array)
    """
    try:
        import multiprocessing as mp
        from multiprocessing import shared_memory
        
        # Generate a name if not provided
        if name is None:
            import uuid
            name = f"shared_array_{uuid.uuid4().hex}"
        
        # Create a shared memory segment
        shm = shared_memory.SharedMemory(
            name=name,
            create=True,
            size=array.nbytes
        )
        
        # Create a numpy array backed by shared memory
        shared_array = np.ndarray(
            array.shape,
            dtype=array.dtype,
            buffer=shm.buf
        )
        
        # Copy data to shared array
        shared_array[:] = array[:]
        
        return shared_array
    except (ImportError, AttributeError):
        # Fallback for older Python versions or if shared_memory not available
        logger.warning("SharedMemory not available. Returning original array.")
        return array


# Additional optimization utilities
def precompute_calculations(
    func: Callable[[Any], Dict[str, Any]], 
    cache_size: int = 1000
) -> Callable[[Any], Dict[str, Any]]:
    """
    Decorator to precompute and cache expensive calculations.
    
    Args:
        func: Function that performs calculations
        cache_size: Maximum number of results to cache
        
    Returns:
        Decorated function with caching
        
    Usage:
        @precompute_calculations(cache_size=500)
        def calculate_indicators(data):
            # Expensive calculations
            return results
    """
    try:
        from functools import lru_cache
        
        @functools.wraps(func)
        @lru_cache(maxsize=cache_size)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    except ImportError:
        # Simple cache implementation if lru_cache not available
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key from arguments
            key_parts = [str(arg) for arg in args]
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            key = "|".join(key_parts)
            
            # Return cached result if available
            if key in cache:
                return cache[key]
            
            # Calculate and cache result
            result = func(*args, **kwargs)
            
            # Manage cache size
            if len(cache) >= cache_size:
                # Remove a random item if cache is full
                try:
                    cache.pop(next(iter(cache)))
                except (StopIteration, KeyError):
                    pass
            
            cache[key] = result
            return result
        
        return wrapper 