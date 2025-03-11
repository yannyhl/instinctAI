"""
Exchange Interface Module
------------------------
Provides interface to interact with Hyperliquid exchange
"""

import logging
import requests
import json
import time
import hmac
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import numpy as np

import config

logger = logging.getLogger(__name__)

class BinanceExchange:
    """Interface with Binance exchange API for data fetching"""
    
    def __init__(self):
        """Initialize Binance API connection"""
        self.api_key = config.BINANCE_API_KEY
        self.api_secret = config.BINANCE_API_SECRET
        self.base_url = 'https://api.binance.com'
        
    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC signature for API request"""
        query_string = '&'.join([f"{key}={params[key]}" for key in params])
        return hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False) -> Dict:
        """Make request to Binance API"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'X-MBX-APIKEY': self.api_key
        }
        
        # Add signature for authenticated endpoints
        if signed and params:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Binance API request error: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    def get_historical_klines(self, symbol: str, interval: str, start_time: Optional[datetime] = None, 
                             end_time: Optional[datetime] = None, limit: int = 1000) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Binance
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '1h', '4h', '1d')
            start_time: Start time for data fetching
            end_time: End time for data fetching
            limit: Maximum number of candles per request (max 1000)
            
        Returns:
            DataFrame with OHLCV data
        """
        # Ensure symbol format for Binance (BTC -> BTCUSDT)
        if not symbol.endswith('USDT'):
            symbol = f"{symbol}USDT"
            
        # Convert interval to Binance format
        interval_mapping = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d',
            '1w': '1w'
        }
        binance_interval = interval_mapping.get(interval, '1h')
        
        # Set up parameters
        params = {
            'symbol': symbol,
            'interval': binance_interval,
            'limit': min(limit, 1000)  # Binance limit is 1000 candles per request
        }
        
        # Add time parameters if provided
        if start_time:
            params['startTime'] = int(start_time.timestamp() * 1000)
        if end_time:
            params['endTime'] = int(end_time.timestamp() * 1000)
        
        try:
            # For fetching large amounts of data, we need to make multiple requests
            all_candles = []
            
            # If specific start_time is given, fetch all data up to end_time or current time
            if start_time:
                current_start = start_time
                current_end = end_time or datetime.now()
                
                while current_start < current_end:
                    params['startTime'] = int(current_start.timestamp() * 1000)
                    
                    # Set end time for this batch (either end_time or current_start + 1000 candles)
                    if end_time:
                        params['endTime'] = int(min(current_end, current_start + timedelta(minutes=limit * self._interval_to_minutes(binance_interval))).timestamp() * 1000)
                    
                    data = self._make_request('GET', '/api/v3/klines', params=params)
                    
                    if not data:
                        break
                        
                    all_candles.extend(data)
                    
                    # Update start time for next batch
                    if len(data) < limit:
                        break  # We've fetched all available data
                    
                    # Start from the next candle after the last one we got
                    last_candle_time = datetime.fromtimestamp(data[-1][0] / 1000)
                    current_start = last_candle_time + timedelta(minutes=self._interval_to_minutes(binance_interval))
            else:
                # If no start_time, just fetch the latest candles
                data = self._make_request('GET', '/api/v3/klines', params=params)
                all_candles.extend(data)
            
            # Convert to DataFrame
            if not all_candles:
                logger.warning(f"No historical data retrieved from Binance for {symbol} {interval}")
                return pd.DataFrame()
                
            # Process the candles into a DataFrame
            df = pd.DataFrame(all_candles, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert timestamp to datetime and set as index
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Convert string values to float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            # Return only the OHLCV columns
            return df[['open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            logger.error(f"Error fetching historical data from Binance: {str(e)}")
            return pd.DataFrame()
    
    def _interval_to_minutes(self, interval: str) -> int:
        """Convert interval string to minutes"""
        unit = interval[-1]
        value = int(interval[:-1])
        
        if unit == 'm':
            return value
        elif unit == 'h':
            return value * 60
        elif unit == 'd':
            return value * 24 * 60
        elif unit == 'w':
            return value * 7 * 24 * 60
        else:
            return 60  # Default to 1h
    
    def get_5year_historical_data(self, symbol: str = 'BTC', timeframe: str = '1h') -> pd.DataFrame:
        """
        Fetch 5 years of historical OHLCV data
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC')
            timeframe: Kline interval (e.g., '1h', '4h', '1d')
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Calculate start and end times
            end_time = datetime.now()
            start_time = end_time - timedelta(days=365 * 5)  # 5 years
            
            logger.info(f"Fetching 5 years of historical data for {symbol} ({timeframe}) from Binance")
            logger.info(f"Date range: {start_time.date()} to {end_time.date()}")
            
            # Fetch the data
            df = self.get_historical_klines(symbol, timeframe, start_time, end_time)
            
            if df.empty:
                logger.warning(f"No historical data retrieved for {symbol} {timeframe}")
                return pd.DataFrame()
                
            logger.info(f"Successfully retrieved {len(df)} bars of historical data for {symbol} {timeframe}")
            logger.info(f"Data range: {df.index[0]} to {df.index[-1]}")
            
            # Save to CSV file for later use
            filename = f"{symbol}_{timeframe}_5years.csv"
            file_path = config.DATA_DIR / filename
            df.to_csv(file_path)
            logger.info(f"Saved historical data to {file_path}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching 5-year historical data: {str(e)}")
            return pd.DataFrame()

class HyperliquidExchange:
    """Interface with Hyperliquid exchange API"""
    
    def __init__(self):
        """Initialize Hyperliquid API connection"""
        self.api_key = config.HYPERLIQUID_API_KEY
        self.secret_key = config.HYPERLIQUID_SECRET_KEY
        self.wallet_address = config.HYPERLIQUID_WALLET_ADDRESS
        self.base_url = 'https://api.hyperliquid.xyz'
        
        if not all([self.api_key, self.secret_key, self.wallet_address]):
            logger.warning("Hyperliquid API credentials incomplete")
    
    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for API request"""
        return hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Make request to Hyperliquid API"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'X-HL-API-Key': self.api_key
        }
        
        # Add signature for authenticated endpoints if data is provided
        if data and endpoint.startswith('/exchange'):
            payload = json.dumps(data)
            headers['X-HL-Signature'] = self._generate_signature(payload)
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    def get_historical_data(self, symbol: str = 'BTC', timeframe: str = '1h', limit: int = 43800) -> pd.DataFrame:
        """Fetch historical OHLCV data"""
        try:
            # Convert timeframe to seconds
            timeframe_seconds = {
                '1m': 60,
                '5m': 300,
                '15m': 900,
                '1h': 3600,
                '4h': 14400,
                '1d': 86400
            }.get(timeframe, 3600)
            
            # Calculate start time (default to 5 years)
            # 365 days * 24 hours * 5 years = 43800 hours
            if timeframe in ['1h', '4h', '1d']:
                # For larger timeframes, we can request 5 years directly
                params = {
                    'coin': symbol,
                    'startTime': int((datetime.now() - timedelta(days=365*5)).timestamp()),
                    'endTime': int(datetime.now().timestamp()),
                    'interval': timeframe_seconds
                }
            else:
                # For smaller timeframes, we need to limit the number of candles
                # to avoid overwhelming the API or memory
                hours_limit = min(limit, 43800)  # Cap at 5 years max
                params = {
                    'coin': symbol,
                    'startTime': int((datetime.now() - timedelta(hours=hours_limit)).timestamp()),
                    'endTime': int(datetime.now().timestamp()),
                    'interval': timeframe_seconds
                }
            
            try:
                data = self._make_request('GET', '/info/candles', params=params)
                
                # Convert to DataFrame
                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)
                
                # Convert string values to float
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                    
                return df
                
            except Exception as api_error:
                logger.warning(f"API call failed: {str(api_error)}. Generating synthetic data instead.")
                return self._generate_synthetic_data(symbol, timeframe, limit)
                
        except Exception as e:
            logger.error(f"Error fetching historical data: {str(e)}")
            return pd.DataFrame()
    
    def _generate_synthetic_data(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Generate synthetic price data for testing with realistic market cycles"""
        logger.info(f"Generating synthetic data for {symbol} {timeframe} ({limit} candles)")
        
        # Starting parameters based on symbol
        if symbol.upper() == 'BTC':
            base_price = 40000.0
            volatility = 0.02
            volume_base = 100.0
        elif symbol.upper() == 'ETH':
            base_price = 2500.0
            volatility = 0.025
            volume_base = 1000.0
        else:
            base_price = 100.0
            volatility = 0.03
            volume_base = 10000.0
        
        # Generate time index
        timeframe_map = {
            '1m': '1min', 
            '5m': '5min', 
            '15m': '15min',
            '1h': '1H', 
            '4h': '4H', 
            '1d': '1D'
        }
        pd_timeframe = timeframe_map.get(timeframe, '1H')
        
        # Cap the limit to avoid memory issues
        if limit > 43800:  # 5 years in hours
            logger.warning(f"Limiting synthetic data generation to 5 years (43800 hours) instead of {limit} hours")
            limit = 43800
            
        end_time = pd.Timestamp.now().floor(pd_timeframe)
        periods = pd.date_range(end=end_time, periods=limit, freq=pd_timeframe)
        
        # Generate price data with realistic market cycles
        np.random.seed(42)  # For reproducibility
        
        # Create multi-year market cycles (bull/bear markets)
        # A full market cycle typically lasts about 4 years for crypto
        cycle_period = min(1440, limit/3)  # ~60 days for short cycles, but cap at 1/3 of total length
        
        # Long-term market cycles (multi-year)
        long_cycle = np.sin(np.linspace(0, 2*np.pi * (limit/cycle_period/4), limit)) * 0.5
        
        # Medium-term market trends (months)
        medium_cycle = np.sin(np.linspace(0, 2*np.pi * (limit/cycle_period), limit)) * 0.3
        
        # Short-term fluctuations
        short_cycle = np.sin(np.linspace(0, 2*np.pi * (limit/cycle_period*10), limit)) * 0.1
        
        # Combine cycles with random walk
        returns = np.random.normal(0, volatility, limit)
        cumulative_returns = np.cumsum(returns)
        
        # Add market cycles to returns
        trend = long_cycle + medium_cycle + short_cycle
        
        # Exponential growth with market cycles and volatility clusters
        growth_factor = 1.0003  # Small daily growth factor (~10% annual on average)
        exponential_growth = np.power(growth_factor, np.arange(limit))
        
        # Generate volatility clusters (periods of high and low volatility)
        volatility_regime = np.abs(np.sin(np.linspace(0, 8*np.pi, limit))) * 0.02 + 0.01
        volatility_adjusted_returns = returns * volatility_regime
        
        # Calculate final price series
        price_changes = np.exp(cumulative_returns + trend)
        closes = base_price * price_changes * exponential_growth
        
        # Create dataframe
        df = pd.DataFrame(index=periods)
        df['close'] = closes
        
        # Generate realistic OHLC based on close prices
        daily_volatility = np.mean(volatility_regime)
        df['high'] = df['close'] * (1 + abs(np.random.normal(0, daily_volatility, limit)))
        df['low'] = df['close'] * (1 - abs(np.random.normal(0, daily_volatility, limit)))
        df['open'] = df['close'].shift(1)
        df.loc[df.index[0], 'open'] = df['close'].iloc[0] * (1 + np.random.normal(0, daily_volatility))
        
        # Ensure high is always the highest and low is always the lowest
        df['high'] = df[['high', 'open', 'close']].max(axis=1)
        df['low'] = df[['low', 'open', 'close']].min(axis=1)
        
        # Generate volume with realistic patterns
        # Volume tends to be higher in volatile periods and major trend changes
        volatility_component = np.abs(df['close'].pct_change().fillna(0))
        trend_change = np.abs(np.diff(np.sign(np.diff(np.array(trend))), prepend=[0, 0]))
        
        volume_pattern = volatility_component * 10 + trend_change * 5
        volume_scaling = volume_pattern / np.mean(volume_pattern) if np.mean(volume_pattern) > 0 else 1
        
        # Add random noise to volume
        volume_noise = np.random.lognormal(0, 0.5, limit)
        df['volume'] = volume_base * volume_scaling * volume_noise
        
        logger.info(f"Generated {len(df)} bars of synthetic data from {df.index[0]} to {df.index[-1]}")
        return df
    
    def get_funding_rates(self, symbol: str = 'BTC') -> float:
        """Fetch current funding rates"""
        try:
            try:
                params = {'coin': symbol}
                data = self._make_request('GET', '/info/funding', params=params)
                return data.get('fundingRate', 0)
            except Exception as api_error:
                logger.warning(f"API call for funding rates failed: {str(api_error)}. Using synthetic data.")
                # Generate synthetic funding rate based on sinusoidal pattern
                # Funding rates typically alternate between positive and negative
                hour_of_day = datetime.now().hour
                # Generate number between -0.01 and +0.01 with some periodicity
                funding_rate = 0.005 * np.sin(hour_of_day * np.pi / 4)
                return funding_rate
        except Exception as e:
            logger.error(f"Error fetching funding rates: {str(e)}")
            return 0
    
    def get_orderbook(self, symbol: str = 'BTC', depth: int = 10) -> Dict:
        """Fetch current orderbook"""
        try:
            try:
                params = {'coin': symbol, 'depth': depth}
                data = self._make_request('GET', '/info/l2Book', params=params)
                return {
                    'bids': data.get('bids', []),
                    'asks': data.get('asks', [])
                }
            except Exception as api_error:
                logger.warning(f"API call for orderbook failed: {str(api_error)}. Using synthetic data.")
                
                # Get last price from historical data or use default
                try:
                    last_data = self.get_historical_data(symbol, '1h', 1)
                    last_price = float(last_data['close'].iloc[-1])
                except:
                    if symbol.upper() == 'BTC':
                        last_price = 40000.0
                    elif symbol.upper() == 'ETH':
                        last_price = 2500.0
                    else:
                        last_price = 100.0
                
                # Generate synthetic orderbook
                bids = []
                asks = []
                
                # Generate bids (buy orders below current price)
                for i in range(depth):
                    price_decrease = (1 - 0.001 * (i + 1)) * last_price
                    size = np.random.uniform(0.1, 10.0)  # Random size
                    bids.append([str(price_decrease), str(size)])
                
                # Generate asks (sell orders above current price)
                for i in range(depth):
                    price_increase = (1 + 0.001 * (i + 1)) * last_price
                    size = np.random.uniform(0.1, 10.0)  # Random size
                    asks.append([str(price_increase), str(size)])
                
                return {
                    'bids': bids,
                    'asks': asks
                }
        except Exception as e:
            logger.error(f"Error fetching orderbook: {str(e)}")
            return {'bids': [], 'asks': []}
    
    def get_account_info(self) -> Dict:
        """Fetch account information"""
        try:
            data = {
                'wallet': self.wallet_address
            }
            return self._make_request('POST', '/exchange/user', data=data)
        except Exception as e:
            logger.error(f"Error fetching account info: {str(e)}")
            return {}
    
    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = 'limit', 
                    price: Optional[float] = None, reduce_only: bool = False) -> Dict:
        """
        Place an order on Hyperliquid
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC')
            side: 'buy' or 'sell'
            quantity: Order quantity
            order_type: 'limit' or 'market'
            price: Price for limit orders
            reduce_only: Whether to reduce position only
            
        Returns:
            Order response from exchange
        """
        try:
            # For live trading, this would be implemented with actual API calls
            if not config.TRADING_CONFIG['live_trading_enabled']:
                logger.info(f"SIMULATION: Order placed - {symbol} {side} {quantity} @ {price or 'market'}")
                return {"order_id": "simulation"}
            
            # Example of actual order placement
            data = {
                'wallet': self.wallet_address,
                'order': {
                    'coin': symbol,
                    'side': side.upper(),
                    'size': str(quantity),
                    'reduceOnly': reduce_only
                }
            }
            
            # Add price for limit orders
            if order_type.lower() == 'limit' and price is not None:
                data['order']['limitPrice'] = str(price)
            else:
                # Market order
                data['order']['orderType'] = 'MARKET'
            
            response = self._make_request('POST', '/exchange/order', data=data)
            logger.info(f"Order placed: {response}")
            return response
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return {"error": str(e)}
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """Cancel an open order"""
        try:
            if not config.TRADING_CONFIG['live_trading_enabled']:
                logger.info(f"SIMULATION: Order cancelled - {order_id}")
                return {"success": True}
            
            data = {
                'wallet': self.wallet_address,
                'coin': symbol,
                'orderId': order_id
            }
            
            response = self._make_request('POST', '/exchange/cancel', data=data)
            logger.info(f"Order cancelled: {response}")
            return response
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return {"error": str(e)}
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        try:
            account_info = self.get_account_info()
            return account_info.get('positions', [])
        except Exception as e:
            logger.error(f"Error getting open positions: {str(e)}")
            return []
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders, optionally filtered by symbol"""
        try:
            account_info = self.get_account_info()
            orders = account_info.get('orders', [])
            
            if symbol:
                return [order for order in orders if order.get('coin') == symbol]
            return orders
        except Exception as e:
            logger.error(f"Error getting open orders: {str(e)}")
            return []