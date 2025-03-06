"""
Data Downloader
-------------
Utility module for downloading historical market data.
This module provides a simple interface for downloading OHLCV data from various sources.
It leverages the more comprehensive data pipeline for seamless integration.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Union, Optional, Any, Tuple

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import from data pipeline
from data.data_manager import DataManager
from data.data_loader import DataLoader

# Set up logging
logger = logging.getLogger(__name__)

def download_historical_data(
    symbol: str,
    timeframe: str = '1h',
    start_date: str = None,
    end_date: str = None,
    source: str = 'binance',
    include_indicators: bool = False
) -> pd.DataFrame:
    """
    Download historical OHLCV data.
    
    This function provides a simple interface for downloading historical data.
    It leverages the more comprehensive data pipeline under the hood.
    
    Parameters:
    -----------
    symbol : str
        Trading symbol (e.g., 'BTC', 'ETH', 'BTC/USDT')
    timeframe : str
        Timeframe for the data (e.g., '1m', '5m', '1h', '1d')
    start_date : str
        Start date for the data (e.g., '2021-01-01')
    end_date : str
        End date for the data (e.g., '2021-12-31')
    source : str
        Data source (e.g., 'binance', 'coinbase')
    include_indicators : bool
        Whether to include technical indicators
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with OHLCV data
    """
    try:
        # Initialize data manager
        data_manager = DataManager(use_gpu=False, use_parallel=True)
        
        # Set default dates if not provided
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            
        # Format symbol if needed (some exchanges require specific format)
        if '/' not in symbol and source.lower() == 'binance':
            if symbol.upper() in ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA']:
                symbol = f"{symbol.upper()}/USDT"
        
        # Fetch data
        logger.info(f"Downloading {symbol} {timeframe} data from {start_date} to {end_date}")
        df = data_manager.fetch_historical_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            source=source
        )
        
        # Add technical indicators if requested
        if include_indicators and not df.empty:
            df = data_manager.add_technical_indicators(df)
        
        # Check if data is empty
        if df.empty:
            logger.warning(f"No data returned for {symbol} {timeframe}")
            return pd.DataFrame()
            
        logger.info(f"Downloaded {len(df)} records for {symbol} {timeframe}")
        return df
        
    except Exception as e:
        logger.error(f"Error downloading historical data: {str(e)}")
        return pd.DataFrame()

def download_multiple_symbols(
    symbols: List[str],
    timeframe: str = '1h',
    start_date: str = None,
    end_date: str = None,
    source: str = 'binance'
) -> Dict[str, pd.DataFrame]:
    """
    Download historical data for multiple symbols.
    
    Parameters:
    -----------
    symbols : List[str]
        List of trading symbols
    timeframe : str
        Timeframe for the data
    start_date : str
        Start date for the data
    end_date : str
        End date for the data
    source : str
        Data source
    
    Returns:
    --------
    Dict[str, pd.DataFrame]
        Dictionary with symbol as key and DataFrame as value
    """
    try:
        # Initialize data manager
        data_manager = DataManager(use_gpu=False, use_parallel=True)
        
        # Set default dates if not provided
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Fetch data for multiple symbols
        logger.info(f"Downloading data for {len(symbols)} symbols from {start_date} to {end_date}")
        
        # Use data manager's multi-timeframe method
        results = data_manager.fetch_multi_timeframe(
            symbols=symbols,
            timeframes=[timeframe],
            start_date=start_date,
            end_date=end_date,
            source=source
        )
        
        # Simplify output structure (just return each symbol's DataFrame for the specified timeframe)
        output = {}
        for symbol in results:
            if timeframe in results[symbol]:
                output[symbol] = results[symbol][timeframe]
        
        return output
        
    except Exception as e:
        logger.error(f"Error downloading data for multiple symbols: {str(e)}")
        return {}

def get_available_symbols(source: str = 'binance', base_currency: str = 'USDT') -> List[str]:
    """
    Get list of available trading symbols.
    
    Parameters:
    -----------
    source : str
        Data source
    base_currency : str
        Base currency to filter symbols (e.g., 'USDT', 'USD', 'BTC')
    
    Returns:
    --------
    List[str]
        List of available symbols
    """
    try:
        # Initialize data loader
        data_loader = DataLoader(primary_source=source)
        
        # Get available symbols
        symbols = data_loader.list_available_symbols(base_currency=base_currency)
        
        return symbols
        
    except Exception as e:
        logger.error(f"Error getting available symbols: {str(e)}")
        return [] 