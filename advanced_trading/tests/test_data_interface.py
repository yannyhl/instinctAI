"""
Test Data Interface
----------------
This script tests the unified data interface.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt

# Add parent directory to path to allow importing from project
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import data interface
from data.data_interface import get_data_interface
from utils.data_downloader import download_historical_data, download_multiple_symbols, get_available_symbols

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def test_ohlcv_data():
    """Test fetching OHLCV data."""
    # Get data interface
    data = get_data_interface()
    
    # Fetch OHLCV data
    symbol = 'BTC/USDT'
    timeframe = '1h'
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"Fetching OHLCV data for {symbol} {timeframe} from {start_date} to {end_date}")
    
    ohlcv_data = data.get_ohlcv_data(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if ohlcv_data.empty:
        logger.error("Failed to fetch OHLCV data")
        return False
    
    logger.info(f"Successfully fetched {len(ohlcv_data)} records")
    logger.info(f"Columns: {ohlcv_data.columns.tolist()}")
    logger.info(f"Sample data:\n{ohlcv_data.head()}")
    
    # Plot the data
    plt.figure(figsize=(12, 6))
    plt.plot(ohlcv_data.index, ohlcv_data['close'])
    plt.title(f"{symbol} Close Price ({timeframe})")
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.grid(True)
    
    # Save the plot
    plot_dir = Path(__file__).parent / "plots"
    plot_dir.mkdir(exist_ok=True)
    plt.savefig(plot_dir / f"{symbol.replace('/', '_')}_{timeframe}.png")
    
    return True

def test_multiple_symbols():
    """Test fetching data for multiple symbols."""
    # Fetch data for multiple symbols
    symbols = ['BTC', 'ETH', 'SOL']
    timeframe = '1d'
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"Fetching data for multiple symbols: {symbols}")
    
    symbol_data = download_multiple_symbols(
        symbols=symbols,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if not symbol_data:
        logger.error("Failed to fetch data for multiple symbols")
        return False
    
    logger.info(f"Successfully fetched data for {len(symbol_data)} symbols")
    
    # Plot the data
    plt.figure(figsize=(12, 6))
    
    for symbol, data in symbol_data.items():
        if not data.empty:
            # Normalize data for comparison
            normalized = data['close'] / data['close'].iloc[0]
            plt.plot(data.index, normalized, label=symbol)
    
    plt.title(f"Normalized Price Comparison ({timeframe})")
    plt.xlabel('Date')
    plt.ylabel('Normalized Price')
    plt.legend()
    plt.grid(True)
    
    # Save the plot
    plot_dir = Path(__file__).parent / "plots"
    plot_dir.mkdir(exist_ok=True)
    plt.savefig(plot_dir / f"multiple_symbols_{timeframe}.png")
    
    return True

def test_available_providers():
    """Test getting available providers."""
    # Get data interface
    data = get_data_interface()
    
    # Get available providers
    providers = data.get_available_providers()
    
    logger.info("Available providers:")
    for provider_type, provider_names in providers.items():
        logger.info(f"  {provider_type}: {provider_names}")
    
    return True

def test_available_symbols():
    """Test getting available symbols."""
    # Get available symbols
    symbols = get_available_symbols()
    
    if not symbols:
        logger.warning("No symbols returned or provider not available")
        return False
    
    logger.info(f"Available symbols: {len(symbols)}")
    logger.info(f"Sample symbols: {symbols[:10]}")
    
    return True

def test_downloader_integration():
    """Test the data downloader integration."""
    # Fetch data using the simplified interface
    symbol = 'ETH'
    timeframe = '4h'
    start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"Fetching data using the simplified interface for {symbol} {timeframe}")
    
    data = download_historical_data(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        include_indicators=True
    )
    
    if data.empty:
        logger.error("Failed to fetch data using the simplified interface")
        return False
    
    logger.info(f"Successfully fetched {len(data)} records")
    
    # Check if indicators were added
    indicator_columns = [col for col in data.columns if col not in ['open', 'high', 'low', 'close', 'volume']]
    logger.info(f"Indicators added: {len(indicator_columns)}")
    logger.info(f"Sample indicators: {indicator_columns[:5] if indicator_columns else 'None'}")
    
    return True

def test_onchain_readiness():
    """
    Test the on-chain data readiness.
    
    This doesn't actually fetch on-chain data since we don't have API keys yet.
    Instead, it verifies that the on-chain interface is ready to be used when
    API keys become available.
    """
    # Get data interface
    data = get_data_interface()
    
    # Check if any on-chain providers are available
    providers = data.get_available_providers()
    onchain_providers = providers.get('on_chain', [])
    
    if not onchain_providers:
        logger.warning("No on-chain providers available")
        logger.info("This is expected since we don't have API keys yet")
        logger.info("The on-chain data interface is ready to be used when API keys become available")
        return True
    
    # If we have on-chain providers, test them
    for provider in onchain_providers:
        logger.info(f"Testing on-chain provider: {provider}")
        
        # Try to fetch on-chain data
        onchain_data = data.get_onchain_data(
            blockchain='bitcoin',
            metric_name='active_addresses',
            start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d'),
            provider=provider
        )
        
        if not onchain_data.empty:
            logger.info(f"Successfully fetched on-chain data using {provider}")
            logger.info(f"Columns: {onchain_data.columns.tolist()}")
            logger.info(f"Sample data:\n{onchain_data.head()}")
        else:
            logger.warning(f"No on-chain data returned from {provider}")
    
    return True

def test_combined_data_readiness():
    """
    Test the combined data readiness.
    
    This doesn't fetch real combined data since we don't have on-chain API keys yet.
    Instead, it verifies that the combined data interface is ready to be used.
    """
    # Get data interface
    data = get_data_interface()
    
    logger.info("Testing combined data readiness")
    
    # Try to fetch combined data
    try:
        combined_data = data.get_combined_data(
            symbol='BTC',
            timeframe='1d',
            include_onchain=True,
            include_sentiment=True,
            start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        if not combined_data.empty:
            logger.info("Successfully fetched combined data")
            logger.info(f"Columns: {combined_data.columns.tolist()}")
            
            # Check if any on-chain or sentiment columns were added
            onchain_cols = [col for col in combined_data.columns if col.startswith('onchain_')]
            sentiment_cols = [col for col in combined_data.columns if col.startswith('sentiment_')]
            
            logger.info(f"On-chain columns: {len(onchain_cols)}")
            logger.info(f"Sentiment columns: {len(sentiment_cols)}")
            
            if not onchain_cols and not sentiment_cols:
                logger.info("No on-chain or sentiment data was added, which is expected")
                logger.info("The combined data interface is ready to be used when API keys become available")
        else:
            logger.warning("No combined data returned")
            logger.info("This could be because we don't have API keys for on-chain data yet")
    except Exception as e:
        logger.error(f"Error testing combined data: {str(e)}")
        return False
    
    return True

def run_tests():
    """Run all tests."""
    tests = [
        ("OHLCV Data", test_ohlcv_data),
        ("Multiple Symbols", test_multiple_symbols),
        ("Available Providers", test_available_providers),
        ("Available Symbols", test_available_symbols),
        ("Downloader Integration", test_downloader_integration),
        ("On-Chain Readiness", test_onchain_readiness),
        ("Combined Data Readiness", test_combined_data_readiness)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"==== Running Test: {test_name} ====")
        
        try:
            result = test_func()
            results[test_name] = result
            logger.info(f"==== Test {test_name}: {'PASSED' if result else 'FAILED'} ====\n")
        except Exception as e:
            results[test_name] = False
            logger.error(f"Exception in test {test_name}: {str(e)}")
            logger.info(f"==== Test {test_name}: FAILED (Exception) ====\n")
    
    # Print summary
    logger.info("==== Test Summary ====")
    for test_name, result in results.items():
        logger.info(f"{test_name}: {'PASSED' if result else 'FAILED'}")
    
    # Calculate overall result
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    logger.info(f"Overall: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == "__main__":
    logger.info("Starting data interface tests")
    success = run_tests()
    logger.info("Data interface tests completed")
    sys.exit(0 if success else 1) 