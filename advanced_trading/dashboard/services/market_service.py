"""
Market Service

This module provides backend services for interacting with market data.
"""

import os
import sys
import json
import time
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict, deque

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import core modules
from core import config_manager, metrics, logging as log_manager, tracing

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.market_service"})

# Cache for market data
_market_cache = {}
_last_update = {}
_update_interval = 60  # seconds


def _update_market_data(symbol: str):
    """
    Update cached market data for a symbol.
    
    Args:
        symbol: Market symbol (e.g., "BTC/USD")
    """
    current_time = time.time()
    
    # Only update every _update_interval seconds
    if symbol in _last_update and current_time - _last_update.get(symbol, 0) < _update_interval:
        return
    
    _last_update[symbol] = current_time
    
    # In a real implementation, this would fetch data from a data provider
    # For demonstration, we'll generate some placeholder data
    if symbol not in _market_cache:
        # Initialize cache for this symbol
        _market_cache[symbol] = {
            "ohlcv": deque(maxlen=100),        # OHLCV data
            "orderbook": {},                    # Orderbook
            "trades": deque(maxlen=100),        # Recent trades
            "indicators": {}                    # Technical indicators
        }
    
    # Generate OHLCV data if none exists
    if not _market_cache[symbol]["ohlcv"]:
        # Set base price depending on symbol
        base_price = {
            "BTC/USD": 50000.0,
            "ETH/USD": 3500.0,
            "SOL/USD": 120.0,
            "DOT/USD": 22.0,
            "LTC/USD": 175.0
        }.get(symbol, 100.0)
        
        # Generate 100 candles of historical data
        for i in range(100, 0, -1):
            timestamp = datetime.now() - timedelta(minutes=i)
            
            # Add some randomness to price movement
            price_change = (random.random() - 0.5) * 0.01  # +/- 0.5%
            close_price = base_price * (1 + price_change)
            
            # Generate high, low, open based on close
            high_price = close_price * (1 + random.random() * 0.005)  # Up to 0.5% higher
            low_price = close_price * (1 - random.random() * 0.005)   # Up to 0.5% lower
            open_price = low_price + random.random() * (high_price - low_price)
            
            # Generate volume
            volume = base_price * random.randint(10, 100) / 10.0
            
            # Add to cache
            _market_cache[symbol]["ohlcv"].append({
                "timestamp": timestamp.isoformat(),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume
            })
            
            # Update base price for next candle
            base_price = close_price
    else:
        # Add a new candle
        last_candle = _market_cache[symbol]["ohlcv"][-1]
        timestamp = datetime.now()
        
        # Add some randomness to price movement
        price_change = (random.random() - 0.5) * 0.01  # +/- 0.5%
        close_price = float(last_candle["close"]) * (1 + price_change)
        
        # Generate high, low, open based on close
        high_price = max(close_price * (1 + random.random() * 0.005), close_price)  # Up to 0.5% higher
        low_price = min(close_price * (1 - random.random() * 0.005), close_price)   # Up to 0.5% lower
        open_price = float(last_candle["close"])  # Open at previous close
        
        # Generate volume
        volume = close_price * random.randint(10, 100) / 10.0
        
        # Add to cache
        _market_cache[symbol]["ohlcv"].append({
            "timestamp": timestamp.isoformat(),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume
        })
    
    # Generate orderbook data
    last_price = float(_market_cache[symbol]["ohlcv"][-1]["close"])
    
    _market_cache[symbol]["orderbook"] = {
        "bids": [
            [last_price * (1 - 0.001 * i), random.randint(1, 100) / (i + 1)]
            for i in range(10)
        ],
        "asks": [
            [last_price * (1 + 0.001 * i), random.randint(1, 100) / (i + 1)]
            for i in range(10)
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    # Generate recent trades if none exist
    if not _market_cache[symbol]["trades"]:
        for i in range(20):
            # Random price around last price
            price = last_price * (1 + (random.random() - 0.5) * 0.002)  # +/- 0.1%
            
            # Random quantity
            quantity = random.randint(1, 100) / 10.0
            
            # Random side
            side = "buy" if random.random() > 0.5 else "sell"
            
            # Add to cache
            _market_cache[symbol]["trades"].append({
                "id": f"{symbol.replace('/', '')}-{time.time()}-{i}",
                "timestamp": (datetime.now() - timedelta(seconds=i*30)).isoformat(),
                "price": price,
                "quantity": quantity,
                "side": side
            })
    else:
        # Add a new trade
        # Random price around last price
        price = last_price * (1 + (random.random() - 0.5) * 0.002)  # +/- 0.1%
        
        # Random quantity
        quantity = random.randint(1, 100) / 10.0
        
        # Random side
        side = "buy" if random.random() > 0.5 else "sell"
        
        # Add to cache
        _market_cache[symbol]["trades"].append({
            "id": f"{symbol.replace('/', '')}-{time.time()}",
            "timestamp": datetime.now().isoformat(),
            "price": price,
            "quantity": quantity,
            "side": side
        })
    
    # Calculate some basic indicators
    candles = list(_market_cache[symbol]["ohlcv"])
    if len(candles) >= 20:
        # Calculate SMA 20
        sma20 = sum(float(candle["close"]) for candle in candles[-20:]) / 20
        
        # Calculate EMA 20
        ema20 = float(candles[-20]["close"])
        multiplier = 2 / (20 + 1)
        for candle in candles[-19:]:
            ema20 = (float(candle["close"]) - ema20) * multiplier + ema20
        
        # Calculate RSI
        gains = 0
        losses = 0
        for i in range(-14, 0):
            price_change = float(candles[i]["close"]) - float(candles[i-1]["close"])
            if price_change > 0:
                gains += price_change
            else:
                losses -= price_change
        
        if losses == 0:
            rsi = 100
        else:
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))
        
        # Store indicators
        _market_cache[symbol]["indicators"] = {
            "sma20": sma20,
            "ema20": ema20,
            "rsi": rsi,
            "timestamp": datetime.now().isoformat()
        }


def get_market_summary() -> Dict[str, Any]:
    """
    Get a summary of current market conditions.
    
    Returns:
        Dictionary with market summary information
    """
    symbols = ["BTC/USD", "ETH/USD", "SOL/USD", "DOT/USD", "LTC/USD"]
    
    # Make sure we have data for all symbols
    for symbol in symbols:
        _update_market_data(symbol)
    
    # Create summary
    return {
        "timestamp": datetime.now().isoformat(),
        "symbols": {
            symbol: {
                "price": float(_market_cache[symbol]["ohlcv"][-1]["close"]),
                "change_24h": round((float(_market_cache[symbol]["ohlcv"][-1]["close"]) / 
                                  float(_market_cache[symbol]["ohlcv"][0]["close"]) - 1) * 100, 2),
                "high_24h": max(float(candle["high"]) for candle in _market_cache[symbol]["ohlcv"]),
                "low_24h": min(float(candle["low"]) for candle in _market_cache[symbol]["ohlcv"]),
                "volume_24h": sum(float(candle["volume"]) for candle in _market_cache[symbol]["ohlcv"])
            } for symbol in symbols
        },
        "market_cap": {
            "BTC": 950000000000,
            "ETH": 420000000000,
            "SOL": 48000000000,
            "DOT": 22000000000,
            "LTC": 12500000000
        },
        "global": {
            "total_market_cap": 2400000000000,
            "total_volume_24h": 85000000000,
            "btc_dominance": 39.58,
            "defi_tvl": 78000000000
        }
    }


def get_ohlcv(symbol: str, timeframe: str = "1m", limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get OHLCV (candlestick) data for a symbol.
    
    Args:
        symbol: Market symbol (e.g., "BTC/USD")
        timeframe: Candle timeframe (e.g., "1m", "5m", "1h", "1d")
        limit: Maximum number of candles to return
        
    Returns:
        List of OHLCV dictionaries
    """
    # Make sure we have data for this symbol
    _update_market_data(symbol)
    
    # Return the OHLCV data
    candles = list(_market_cache[symbol]["ohlcv"])
    
    # Convert timeframe if needed (in a real implementation)
    # For now, just return what we have
    
    return candles[-limit:]


def get_orderbook(symbol: str, depth: int = 10) -> Dict[str, Any]:
    """
    Get market order book for a symbol.
    
    Args:
        symbol: Market symbol (e.g., "BTC/USD")
        depth: Depth of order book to return
        
    Returns:
        Order book dictionary
    """
    # Make sure we have data for this symbol
    _update_market_data(symbol)
    
    # Return the orderbook
    orderbook = _market_cache[symbol]["orderbook"]
    
    # Limit depth if needed
    limited_orderbook = {
        "bids": orderbook["bids"][:depth],
        "asks": orderbook["asks"][:depth],
        "timestamp": orderbook["timestamp"]
    }
    
    return limited_orderbook


def get_recent_trades(symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent trades for a symbol.
    
    Args:
        symbol: Market symbol (e.g., "BTC/USD")
        limit: Maximum number of trades to return
        
    Returns:
        List of trade dictionaries
    """
    # Make sure we have data for this symbol
    _update_market_data(symbol)
    
    # Return the trades
    trades = list(_market_cache[symbol]["trades"])
    
    return trades[-limit:]


def get_indicators(symbol: str) -> Dict[str, Any]:
    """
    Get technical indicators for a symbol.
    
    Args:
        symbol: Market symbol (e.g., "BTC/USD")
        
    Returns:
        Dictionary of indicators
    """
    # Make sure we have data for this symbol
    _update_market_data(symbol)
    
    # Return the indicators
    return _market_cache[symbol]["indicators"]


def get_market_sentiment() -> Dict[str, Any]:
    """
    Get overall market sentiment data.
    
    Returns:
        Dictionary with sentiment information
    """
    # In a real implementation, this would fetch data from various sources
    # For now, return placeholder data
    return {
        "timestamp": datetime.now().isoformat(),
        "fear_greed_index": 65,  # 0-100, where 0 is extreme fear and 100 is extreme greed
        "fear_greed_value": "Greed",
        "social_sentiment": {
            "BTC": 0.72,  # -1 to 1, where -1 is very negative and 1 is very positive
            "ETH": 0.65,
            "SOL": 0.81,
            "DOT": 0.58,
            "LTC": 0.42
        },
        "market_trend": "bullish",  # bullish, bearish, or neutral
        "market_volatility": "medium"  # low, medium, or high
    }


def get_supported_symbols() -> List[str]:
    """
    Get a list of supported market symbols.
    
    Returns:
        List of symbol strings
    """
    # In a real implementation, this would fetch data from a data provider
    # For now, return placeholder data
    return ["BTC/USD", "ETH/USD", "SOL/USD", "DOT/USD", "LTC/USD", "XRP/USD", "ADA/USD", "AVAX/USD"]


def add_symbol(symbol: str) -> Dict[str, Any]:
    """
    Add a new market symbol to watch.
    
    Args:
        symbol: Market symbol to add
        
    Returns:
        Success status and message
    """
    logger.info(f"Adding symbol: {symbol}")
    
    # Initialize data for this symbol
    _update_market_data(symbol)
    
    return {"success": True, "message": f"Symbol {symbol} added successfully"}


def remove_symbol(symbol: str) -> Dict[str, Any]:
    """
    Remove a market symbol from watching.
    
    Args:
        symbol: Market symbol to remove
        
    Returns:
        Success status and message
    """
    logger.info(f"Removing symbol: {symbol}")
    
    # Remove data for this symbol
    if symbol in _market_cache:
        del _market_cache[symbol]
    
    if symbol in _last_update:
        del _last_update[symbol]
    
    return {"success": True, "message": f"Symbol {symbol} removed successfully"}


def download_market_data(symbol: str, timeframe: str = "1d", start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    Download historical market data for offline analysis.
    
    Args:
        symbol: Market symbol
        timeframe: Data timeframe
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        
    Returns:
        Success status and message
    """
    logger.info(f"Downloading market data: {symbol} {timeframe} {start_date} to {end_date}")
    
    # In a real implementation, this would download data to a file
    # For now, return success message
    return {
        "success": True, 
        "message": f"Market data for {symbol} ({timeframe}) downloaded successfully",
        "path": f"/tmp/{symbol.replace('/', '_')}_{timeframe}_{start_date}_{end_date}.csv"
    } 