#!/usr/bin/env python
"""
Simple test script for the advanced_trading backtesting system
"""

import os
import sys
from pathlib import Path
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the current directory to path
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.append(str(script_dir))

# Import from our advanced_trading module
import config
from strategies.ml_strategy import MLEnsembleStrategy
from data.data_loader import DataLoader

def test_data_loader():
    """Test if we can load data correctly"""
    logger.info("Testing DataLoader...")
    
    # Initialize data loader
    data_loader = DataLoader(
        cache_dir=config.DATA_DIR / "cache",
        primary_source="binance"
    )
    
    # Test symbol and timeframe
    symbol = "BTC/USDT"
    timeframe = "1d"
    start_date = "2023-01-01"
    end_date = "2023-04-01"
    
    # Try to load data
    logger.info(f"Loading data for {symbol} from {start_date} to {end_date}")
    data = data_loader.load_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe
    )
    
    if data is not None and not data.empty:
        logger.info(f"Successfully loaded {len(data)} data points")
        logger.info(f"Data columns: {data.columns.tolist()}")
        logger.info(f"Data sample:\n{data.head()}")
        
        # Save a plot of the data
        plt.figure(figsize=(12, 6))
        plt.plot(data.index, data['close'])
        plt.title(f"{symbol} Close Price")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.grid(True)
        
        # Save the plot
        results_dir = config.RESULTS_DIR
        os.makedirs(results_dir, exist_ok=True)
        plt.savefig(results_dir / f"{symbol.replace('/', '_')}_{timeframe}_test.png")
        logger.info(f"Saved price chart to {results_dir}")
        
        return True
    else:
        logger.error("Failed to load data")
        return False

def test_ml_strategy():
    """Test initializing the ML strategy"""
    logger.info("Testing ML strategy...")
    
    # Get strategy config
    strategy_config = config.STRATEGY_CONFIGS["ml_ensemble"]
    
    # Update test symbols 
    strategy_config["symbols"] = ["BTC/USDT", "ETH/USDT"]
    
    try:
        # Create strategy instance
        strategy = MLEnsembleStrategy(
            config=strategy_config,
            model_dir=os.path.join(config.MODELS_DIR, "ml_ensemble")
        )
        
        logger.info("Successfully initialized ML strategy")
        logger.info(f"Strategy configuration: {strategy_config}")
        
        return True
    except Exception as e:
        logger.error(f"Error initializing ML strategy: {e}")
        return False

def main():
    """Main test function"""
    logger.info("Starting backtesting system tests")
    
    # Test data loader
    data_loader_success = test_data_loader()
    
    # Test ML strategy
    ml_strategy_success = test_ml_strategy()
    
    # Overall results
    if data_loader_success and ml_strategy_success:
        logger.info("All tests passed successfully!")
        return 0
    else:
        logger.error("Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 