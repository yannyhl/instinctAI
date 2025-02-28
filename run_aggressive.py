#!/usr/bin/env python3
# Script to run a backtest with the AggressiveFundingStrategy in InstinctAI

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import InstinctAI modules
from trading.main import run_backtest_mode
import config

# Configure more verbose logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOGGING_CONFIG['file_handler']['filename']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create an args object with default values
class Args:
    def __init__(self):
        self.symbol = 'BTC'
        self.timeframe = '1h'
        self.strategy = 'aggressive_funding'  # Use our aggressive strategy
        self.initial_cash = 5000.0  # Higher initial capital
        self.refresh_data = False  # Don't refresh by default to use existing data
        self.analyze_results = True  # Analyze the results with AI
        self.use_5year_data = True  # Use 5-year data for backtesting

def main():
    """Main function to run the backtest"""
    try:
        # First, check if 5-year data exists
        data_path = Path(config.DATA_DIR) / f"BTC_1h_5years.csv"
        
        if not data_path.exists():
            print("No 5-year historical data found. Running data fetch script first...")
            
            # Import the fetch_historical_data script and run it
            from fetch_historical_data import fetch_data
            fetch_data(['BTC'], ['1h'], force_refresh=True)
            
            # Check if data was successfully fetched
            if not data_path.exists():
                print("Failed to fetch 5-year historical data. Please check your API keys and internet connection.")
                return
        
        print("Running InstinctAI backtest with AggressiveFundingStrategy and 5 years of historical data...")
        print("This strategy uses more aggressive parameters and simplified entry conditions to generate more frequent trades.")
        print("Key changes: Lower thresholds, higher position sizes, tighter trailing stops, higher profit targets.")
        
        args = Args()
        
        # Run the backtest
        print("Starting backtest - check the log file for detailed progress...")
        run_backtest_mode(args)
        print("Backtest completed.")
        
    except Exception as e:
        logger.error(f"Error in backtest: {str(e)}", exc_info=True)
        print(f"An error occurred: {str(e)}")
        print("Check the log file for more details.")

if __name__ == "__main__":
    main() 