#!/usr/bin/env python3
# Example script to run a backtest with InstinctAI

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import InstinctAI modules
from trading.main import run_backtest_mode

# Create an args object with default values
class Args:
    def __init__(self):
        self.symbol = 'BTC'
        self.timeframe = '1h'
        self.strategy = 'funding_momentum'
        self.initial_cash = 2000.0
        self.refresh_data = False  # Don't refresh by default to use existing data
        self.analyze_results = True
        self.use_5year_data = True  # Use 5-year data for backtesting

if __name__ == "__main__":
    print("Running InstinctAI backtest example with 5 years of historical data...")
    args = Args()
    run_backtest_mode(args)
