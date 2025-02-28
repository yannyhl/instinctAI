#!/usr/bin/env python3
# Script to run a backtest with MacroFundingStrategy in InstinctAI

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import InstinctAI modules
from trading.main import run_backtest_mode
import config

# Create an args object with default values
class Args:
    def __init__(self):
        self.symbol = 'BTC'
        self.timeframe = '1h'
        self.strategy = 'macro_funding'
        self.initial_cash = 5000.0  # Increased initial capital
        self.refresh_data = False  # Don't refresh by default to use existing data
        self.analyze_results = True
        self.use_5year_data = True  # Use 5-year data for backtesting

def main():
    """Main function to run the backtest"""
    # First, check if 5-year data exists
    data_path = Path(config.DATA_DIR) / f"BTC_1h_5years.csv"
    
    if not data_path.exists():
        print("No 5-year historical data found. Running data fetch script first...")
        
        # Import the fetch_historical_data script and run it
        from fetch_historical_data import fetch_data
        fetch_data(['BTC'], ['1h'], force_refresh=False)
        
        # Check if data was successfully fetched
        if not data_path.exists():
            print("Failed to fetch 5-year historical data. Please check your API keys and internet connection.")
            return
    
    print("Running InstinctAI backtest with MacroFundingStrategy and 5 years of historical data...")
    print("This strategy incorporates macroeconomic factors like inflation, interest rates, and GDP growth")
    print("to make more informed trading decisions based on the broader economic environment.")
    
    args = Args()
    run_backtest_mode(args)

if __name__ == "__main__":
    main() 