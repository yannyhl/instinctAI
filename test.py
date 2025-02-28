#!/usr/bin/env python3
"""
InstinctAI Test Script
---------------------
Tests basic functionality of the InstinctAI system
"""

import os
import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from utils.logger import get_logger
from trading.exchange import HyperliquidExchange
from trading.data_manager import DataManager
from utils.indicators import add_technical_indicators

logger = get_logger("test_script")

def test_data_fetch():
    """Test data fetching functionality"""
    logger.info("Testing data fetch...")
    
    exchange = HyperliquidExchange()
    data_manager = DataManager()
    
    # Test data fetch
    symbol = "BTC"
    timeframe = "1h"
    
    logger.info(f"Fetching data for {symbol} {timeframe}...")
    data = data_manager.fetch_and_save_data(symbol, timeframe, limit=100)
    
    if data is not None and not data.empty:
        logger.info(f"Successfully fetched {len(data)} records")
        logger.info(f"Sample data: {data.head()}")
        
        # Test adding indicators
        logger.info("Adding technical indicators...")
        data_with_indicators = add_technical_indicators(data)
        logger.info(f"Added indicators. New columns: {data_with_indicators.columns.tolist()}")
        
        return True
    else:
        logger.error("Failed to fetch data")
        return False

def main():
    """Main test function"""
    logger.info("Starting InstinctAI system test")
    
    # Test data fetch
    if test_data_fetch():
        logger.info("Data fetch test passed")
    else:
        logger.error("Data fetch test failed")
    
    logger.info("System test complete")

if __name__ == "__main__":
    main()