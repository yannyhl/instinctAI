"""
Base Test Fixture for Integration Tests

This module provides a base fixture class with common setup and teardown
operations for integration tests.
"""

import os
import logging
import unittest
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple

from advanced_trading.core.observability.logging import setup_logger
from advanced_trading.core.config import ConfigManager

logger = logging.getLogger('advanced_trading.tests.integration')


class BaseIntegrationTestFixture(unittest.TestCase):
    """
    Base class for integration test fixtures.
    
    This class provides common setup and teardown operations for integration tests,
    including configuration management, logging setup, and temporary directory creation.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests in the class."""
        # Create temp directory for test artifacts
        cls.temp_dir = tempfile.TemporaryDirectory()
        
        # Configure logging for tests
        setup_logger(log_level=logging.INFO, 
                    log_file=os.path.join(cls.temp_dir.name, 'integration_test.log'))
        
        # Load test configuration
        cls.config = ConfigManager()
        cls.config.load_default_config()
        
        # Override with test-specific settings
        cls.config.update({
            'testing': {
                'mode': os.environ.get('INTEGRATION_TEST_MODE', 'fast'),
                'timeout': int(os.environ.get('INTEGRATION_TEST_TIMEOUT', '60')),
                'temp_dir': cls.temp_dir.name
            }
        })
        
        logger.info(f"Integration test environment set up in {cls.temp_dir.name}")
        logger.info(f"Test mode: {cls.config.get('testing.mode')}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests in the class have run."""
        # Clean up temp directory
        cls.temp_dir.cleanup()
        logger.info("Integration test environment cleaned up")
    
    def setUp(self):
        """Set up each individual test."""
        self.start_time = datetime.now()
        logger.info(f"Starting test: {self._testMethodName}")
    
    def tearDown(self):
        """Clean up after each individual test."""
        duration = datetime.now() - self.start_time
        logger.info(f"Completed test: {self._testMethodName} in {duration.total_seconds():.2f} seconds")
    
    def create_test_market_data(self, 
                              symbols: List[str], 
                              start_date: datetime,
                              end_date: datetime,
                              frequency: str = '1h') -> Dict[str, pd.DataFrame]:
        """
        Create synthetic market data for testing.
        
        Args:
            symbols: List of symbols to create data for
            start_date: Start date for the data
            end_date: End date for the data
            frequency: Data frequency ('1m', '5m', '1h', '1d', etc.)
            
        Returns:
            Dictionary mapping symbols to DataFrames with OHLCV data
        """
        market_data = {}
        
        for symbol in symbols:
            # Calculate number of periods
            if frequency.endswith('m'):
                minutes = int(frequency[:-1])
                periods = int((end_date - start_date).total_seconds() / 60 / minutes)
            elif frequency.endswith('h'):
                hours = int(frequency[:-1])
                periods = int((end_date - start_date).total_seconds() / 3600 / hours)
            elif frequency.endswith('d'):
                days = int(frequency[:-1])
                periods = int((end_date - start_date).total_seconds() / 86400 / days)
            else:
                periods = 100  # Default
            
            # Start with a random price
            start_price = np.random.uniform(100, 1000)
            
            # Generate price movement with trend and volatility
            trend = np.cumsum(np.random.normal(0.0002, 0.001, periods))
            noise = np.random.normal(0, 0.005, periods)
            mean_reversion = np.sin(np.linspace(0, 10, periods)) * 0.02
            
            returns = trend + noise + mean_reversion
            prices = start_price * np.cumprod(1 + returns)
            
            # Create OHLCV dataframe
            df = pd.DataFrame({
                'open': prices * np.random.uniform(0.998, 1.002, periods),
                'high': prices * np.random.uniform(1.001, 1.005, periods),
                'low': prices * np.random.uniform(0.995, 0.999, periods),
                'close': prices,
                'volume': np.random.uniform(1000, 10000, periods)
            })
            
            # Set index to timestamp
            df.index = pd.date_range(start=start_date, periods=periods, freq=frequency)
            
            market_data[symbol] = df
        
        return market_data
    
    def create_test_order_book_data(self, 
                                  symbol: str, 
                                  timestamp: datetime,
                                  mid_price: float,
                                  depth: int = 10) -> Dict[str, Any]:
        """
        Create synthetic order book data for testing.
        
        Args:
            symbol: Symbol for the order book
            timestamp: Timestamp for the order book snapshot
            mid_price: Mid price around which to generate the book
            depth: Number of price levels to generate
            
        Returns:
            Dictionary with order book data
        """
        # Generate bids (descending from mid_price)
        bids = []
        bid_price = mid_price * 0.9995
        for i in range(depth):
            size = np.random.uniform(0.1, 10.0) * (depth - i) / depth
            bids.append([bid_price, size])
            bid_price *= 0.9995
        
        # Generate asks (ascending from mid_price)
        asks = []
        ask_price = mid_price * 1.0005
        for i in range(depth):
            size = np.random.uniform(0.1, 10.0) * (depth - i) / depth
            asks.append([ask_price, size])
            ask_price *= 1.0005
        
        return {
            'symbol': symbol,
            'timestamp': timestamp,
            'bids': bids,
            'asks': asks,
            'mid_price': mid_price
        }
    
    def assert_dataframes_equal(self, 
                              df1: pd.DataFrame, 
                              df2: pd.DataFrame,
                              check_index: bool = True,
                              check_dtype: bool = False) -> None:
        """
        Assert that two DataFrames are equal, with options for comparison.
        
        Args:
            df1: First DataFrame
            df2: Second DataFrame
            check_index: Whether to check that indices are equal
            check_dtype: Whether to check that dtypes are equal
        """
        # Check shape
        self.assertEqual(df1.shape, df2.shape, "DataFrames have different shapes")
        
        # Check column names
        self.assertListEqual(list(df1.columns), list(df2.columns), 
                           "DataFrames have different column names")
        
        # Check index if required
        if check_index:
            self.assertTrue(df1.index.equals(df2.index), "DataFrames have different indices")
        
        # Check data values
        for col in df1.columns:
            if pd.api.types.is_numeric_dtype(df1[col]) and pd.api.types.is_numeric_dtype(df2[col]):
                # For numeric columns, use almost equal
                np.testing.assert_allclose(df1[col].values, df2[col].values, 
                                        rtol=1e-5, atol=1e-8,
                                        err_msg=f"Values differ in column {col}")
            else:
                # For non-numeric columns, use equals
                self.assertTrue((df1[col] == df2[col]).all(), 
                              f"Values differ in column {col}")
        
        # Check dtypes if required
        if check_dtype:
            for col in df1.columns:
                self.assertEqual(df1[col].dtype, df2[col].dtype,
                               f"Different dtypes in column {col}")
    
    def measure_performance(self, func, *args, **kwargs) -> Tuple[Any, float]:
        """
        Measure the performance of a function call.
        
        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Tuple containing (function_result, execution_time_in_seconds)
        """
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return result, duration 