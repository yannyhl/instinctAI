#!/usr/bin/env python
"""
Historical Data Fetcher
----------------------
Fetches and saves 5 years of historical data for cryptocurrency pairs
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from trading.data_manager import DataManager

# Configure logging
logging.basicConfig(
    level=config.LOGGING_CONFIG['level'],
    format=config.LOGGING_CONFIG['format'],
    handlers=[
        logging.FileHandler(config.LOGGING_CONFIG['file_handler']['filename']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def fetch_data(symbols, timeframes, force_refresh=False):
    """
    Fetch and save historical data for specified symbols and timeframes
    
    Args:
        symbols: List of symbols to fetch data for
        timeframes: List of timeframes to fetch data for
        force_refresh: Whether to force refresh existing data
    """
    data_manager = DataManager()
    
    for symbol in symbols:
        for timeframe in timeframes:
            logger.info(f"Fetching 5 years of historical data for {symbol} {timeframe}")
            
            try:
                # Fetch 5 years of data
                data = data_manager.fetch_5year_data(symbol, timeframe)
                
                if data.empty:
                    logger.error(f"Failed to fetch data for {symbol} {timeframe}")
                    continue
                    
                logger.info(f"Successfully fetched {len(data)} bars for {symbol} {timeframe}")
                logger.info(f"Data range: {data.index[0]} to {data.index[-1]}")
                
                # Add technical indicators
                data_with_indicators = data_manager.get_data_with_indicators(symbol, timeframe, refresh=force_refresh, use_5year=True)
                logger.info(f"Added technical indicators to {symbol} {timeframe} data")
                
            except Exception as e:
                logger.error(f"Error fetching data for {symbol} {timeframe}: {str(e)}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Fetch historical cryptocurrency data')
    
    parser.add_argument('--symbols', nargs='+', default=['BTC', 'ETH'],
                      help='Symbols to fetch data for')
    parser.add_argument('--timeframes', nargs='+', default=['1h', '4h', '1d'],
                      help='Timeframes to fetch data for')
    parser.add_argument('--refresh', action='store_true',
                      help='Force refresh existing data')
    
    args = parser.parse_args()
    
    logger.info(f"Starting historical data fetch for symbols: {args.symbols}, timeframes: {args.timeframes}")
    
    # Check if Binance API keys are set
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        logger.error("Binance API keys not set. Please set BINANCE_API_KEY and BINANCE_API_SECRET in your environment variables.")
        return
    
    # Fetch data
    fetch_data(args.symbols, args.timeframes, args.refresh)
    
    logger.info("Historical data fetch completed")

if __name__ == "__main__":
    main() 