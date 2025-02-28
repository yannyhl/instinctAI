"""
Market Data Handler
-----------------
Provides data access and processing for the trading dashboard.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
import pandas as pd
import numpy as np
import traceback
from pathlib import Path
import sys

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import custom modules
from utils.market_monitor import get_market_monitor
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarketDataHandler:
    """
    Market Data Handler
    
    Provides data access, processing, and caching for the dashboard.
    Acts as an interface between the dashboard and the market data sources.
    """
    
    def __init__(self):
        """Initialize the market data handler."""
        logger.info("Initializing Market Data Handler")
        
        # Get market monitor instance
        self.market_monitor = get_market_monitor()
        
        # Last update times for different data types
        self.last_updates = {
            'market_overview': datetime.now() - timedelta(minutes=5),
            'price_data': {},
            'volume_profile': {},
            'correlation': datetime.now() - timedelta(minutes=5),
            'performance': datetime.now() - timedelta(minutes=5),
            'regimes': {},
            'alerts': datetime.now() - timedelta(minutes=5)
        }
        
        # Data cache
        self.cache = {
            'market_overview': None,
            'price_data': {},
            'volume_profile': {},
            'correlation': None,
            'performance': None,
            'regimes': {},
            'alerts': None
        }
        
        # Cache TTL in seconds
        self.cache_ttl = {
            'market_overview': 60,  # 1 minute
            'price_data': 60,
            'volume_profile': 300,  # 5 minutes
            'correlation': 300,
            'performance': 300,
            'regimes': 3600,  # 1 hour
            'alerts': 60
        }
        
        # Error state tracking
        self.errors = {
            'market_overview': None,
            'price_data': {},
            'volume_profile': {},
            'correlation': None,
            'performance': None,
            'regimes': {},
            'alerts': None
        }
        
        # Last successful update times
        self.last_successful_updates = {
            'market_overview': None,
            'price_data': {},
            'volume_profile': {},
            'correlation': None,
            'performance': None,
            'regimes': {},
            'alerts': None
        }
        
        logger.info("Market Data Handler initialized")
    
    def get_market_overview(self) -> Dict[str, Any]:
        """
        Get market overview data.
        
        Returns:
            Dictionary with market overview data
        """
        cache_key = 'market_overview'
        
        # Check if cache is valid
        if self._is_cache_valid(cache_key):
            logger.debug("Using cached market overview data")
            return self.cache[cache_key]
        
        try:
            # Get data from market monitor
            logger.info("Fetching market overview data")
            overview = self.market_monitor.get_market_summary()
            
            # Validate data
            if not self._validate_market_overview(overview):
                # If validation fails but we have cache, return cache with warning
                if self.cache[cache_key]:
                    logger.warning("Invalid market overview data received, using cached data")
                    return self.cache[cache_key]
                else:
                    # No valid cache, return fallback data
                    logger.error("Invalid market overview data and no valid cache")
                    return self._get_fallback_market_overview()
            
            # Update cache
            self.cache[cache_key] = overview
            self.last_updates[cache_key] = datetime.now()
            self.last_successful_updates[cache_key] = datetime.now()
            self.errors[cache_key] = None
            
            return overview
            
        except Exception as e:
            logger.error(f"Error getting market overview: {str(e)}")
            self.errors[cache_key] = {
                'time': datetime.now(),
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Return cached data if available
            if self.cache[cache_key]:
                logger.warning("Error fetching market overview, using cached data")
                return self.cache[cache_key]
            else:
                # No cache, return fallback data
                return self._get_fallback_market_overview()
    
    def get_price_chart_data(self, symbol: str, timeframe: str = '1h', 
                           n_periods: int = 100) -> Dict[str, Any]:
        """
        Get price chart data for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            n_periods: Number of periods to return
            
        Returns:
            Dictionary with price chart data
        """
        cache_key = 'price_data'
        cache_subkey = f"{symbol}_{timeframe}_{n_periods}"
        
        # Check if cache is valid
        if self._is_cache_valid(cache_key, cache_subkey):
            logger.debug(f"Using cached price data for {symbol}")
            return self.cache[cache_key][cache_subkey]
        
        try:
            # Get data from market monitor
            logger.info(f"Fetching price data for {symbol} ({timeframe})")
            price_data = self.market_monitor.get_price_data(symbol, timeframe, n_periods)
            
            # Validate data
            if not self._validate_price_data(price_data, symbol, timeframe):
                # If validation fails but we have cache, return cache with warning
                if cache_subkey in self.cache[cache_key]:
                    logger.warning(f"Invalid price data received for {symbol}, using cached data")
                    return self.cache[cache_key][cache_subkey]
                else:
                    # No valid cache, return fallback data
                    logger.error(f"Invalid price data for {symbol} and no valid cache")
                    return self._get_fallback_price_data(symbol, timeframe)
            
            # Calculate additional data
            result = {
                'symbol': symbol,
                'timeframe': timeframe,
                'data': {
                    'timestamps': price_data.index.tolist(),
                    'open': price_data['open'].tolist(),
                    'high': price_data['high'].tolist(),
                    'low': price_data['low'].tolist(),
                    'close': price_data['close'].tolist(),
                    'volume': price_data['volume'].tolist() if 'volume' in price_data.columns else []
                }
            }
            
            # Add technical indicators
            result['indicators'] = self._calculate_indicators(price_data)
            
            # Get current market regime
            try:
                regimes = self.market_monitor.detect_market_regimes()
                if symbol in regimes:
                    result['regime'] = regimes[symbol]['current_regime']
            except Exception as e:
                logger.warning(f"Error getting regime for {symbol}: {str(e)}")
            
            # Update cache
            if cache_key not in self.cache:
                self.cache[cache_key] = {}
            self.cache[cache_key][cache_subkey] = result
            
            if cache_key not in self.last_updates:
                self.last_updates[cache_key] = {}
            self.last_updates[cache_key][cache_subkey] = datetime.now()
            
            if cache_key not in self.last_successful_updates:
                self.last_successful_updates[cache_key] = {}
            self.last_successful_updates[cache_key][cache_subkey] = datetime.now()
            
            if cache_key not in self.errors:
                self.errors[cache_key] = {}
            self.errors[cache_key][cache_subkey] = None
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting price data for {symbol}: {str(e)}")
            
            if cache_key not in self.errors:
                self.errors[cache_key] = {}
            self.errors[cache_key][cache_subkey] = {
                'time': datetime.now(),
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Return cached data if available
            if cache_key in self.cache and cache_subkey in self.cache[cache_key]:
                logger.warning(f"Error fetching price data for {symbol}, using cached data")
                return self.cache[cache_key][cache_subkey]
            else:
                # No cache, return fallback data
                return self._get_fallback_price_data(symbol, timeframe)
    
    def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, List[float]]:
        """
        Calculate technical indicators from price data.
        
        Args:
            data: Price data DataFrame
            
        Returns:
            Dictionary of indicator values
        """
        if data is None or data.empty:
            return {}
        
        indicators = {}
        
        try:
            # Simple moving averages
            indicators['sma20'] = data['close'].rolling(window=20).mean().fillna(0).tolist()
            indicators['sma50'] = data['close'].rolling(window=50).mean().fillna(0).tolist()
            
            # Bollinger Bands (20, 2)
            sma = data['close'].rolling(window=20).mean()
            std = data['close'].rolling(window=20).std()
            indicators['bb_upper'] = (sma + (std * 2)).fillna(0).tolist()
            indicators['bb_middle'] = sma.fillna(0).tolist()
            indicators['bb_lower'] = (sma - (std * 2)).fillna(0).tolist()
            
            # Relative Strength Index (14)
            delta = data['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            indicators['rsi'] = (100 - (100 / (1 + rs))).fillna(0).tolist()
            
            # MACD (12, 26, 9)
            ema12 = data['close'].ewm(span=12, adjust=False).mean()
            ema26 = data['close'].ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            indicators['macd'] = macd.fillna(0).tolist()
            indicators['macd_signal'] = signal.fillna(0).tolist()
            indicators['macd_histogram'] = (macd - signal).fillna(0).tolist()
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
        
        return indicators
    
    def get_volume_profile(self, symbol: str, timeframe: str = '1h', 
                          n_periods: int = 100, n_bins: int = 20) -> Dict[str, Any]:
        """
        Get volume profile data for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            n_periods: Number of periods to analyze
            n_bins: Number of price bins
            
        Returns:
            Dictionary with volume profile data
        """
        cache_key = 'volume_profile'
        cache_subkey = f"{symbol}_{timeframe}_{n_periods}_{n_bins}"
        
        # Check if cache is valid
        if self._is_cache_valid(cache_key, cache_subkey):
            logger.debug(f"Using cached volume profile for {symbol}")
            return self.cache[cache_key][cache_subkey]
        
        try:
            # Get price data
            price_data = self.market_monitor.get_price_data(symbol, timeframe, n_periods)
            
            # Validate data
            if not self._validate_price_data(price_data, symbol, timeframe):
                # If validation fails but we have cache, return cache with warning
                if cache_key in self.cache and cache_subkey in self.cache[cache_key]:
                    logger.warning(f"Invalid price data for volume profile ({symbol}), using cached data")
                    return self.cache[cache_key][cache_subkey]
                else:
                    # No valid cache, return fallback data
                    logger.error(f"Invalid price data for volume profile ({symbol}) and no valid cache")
                    return self._get_fallback_volume_profile(symbol, timeframe)
            
            # Generate volume profile
            vp_result = self._generate_volume_profile(price_data, n_bins)
            
            # Create result
            result = {
                'symbol': symbol,
                'timeframe': timeframe,
                'price_levels': vp_result['price_levels'],
                'volumes': vp_result['volumes'],
                'poc': vp_result['poc'],
                'value_area': vp_result['value_area']
            }
            
            # Update cache
            if cache_key not in self.cache:
                self.cache[cache_key] = {}
            self.cache[cache_key][cache_subkey] = result
            
            if cache_key not in self.last_updates:
                self.last_updates[cache_key] = {}
            self.last_updates[cache_key][cache_subkey] = datetime.now()
            
            if cache_key not in self.last_successful_updates:
                self.last_successful_updates[cache_key] = {}
            self.last_successful_updates[cache_key][cache_subkey] = datetime.now()
            
            if cache_key not in self.errors:
                self.errors[cache_key] = {}
            self.errors[cache_key][cache_subkey] = None
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating volume profile for {symbol}: {str(e)}")
            
            if cache_key not in self.errors:
                self.errors[cache_key] = {}
            self.errors[cache_key][cache_subkey] = {
                'time': datetime.now(),
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Return cached data if available
            if cache_key in self.cache and cache_subkey in self.cache[cache_key]:
                logger.warning(f"Error calculating volume profile for {symbol}, using cached data")
                return self.cache[cache_key][cache_subkey]
            else:
                # No cache, return fallback data
                return self._get_fallback_volume_profile(symbol, timeframe)
    
    def _generate_volume_profile(self, price_data: pd.DataFrame, n_bins: int) -> Dict[str, Any]:
        """
        Generate volume profile from price data.
        
        Args:
            price_data: Price data DataFrame
            n_bins: Number of price bins
            
        Returns:
            Dictionary with volume profile data
        """
        try:
            # Extract price and volume
            if 'hlc3' in price_data.columns:
                price = price_data['hlc3']
            else:
                price = (price_data['high'] + price_data['low'] + price_data['close']) / 3
            
            volume = price_data['volume']
            
            # Calculate price range
            min_price = price.min()
            max_price = price.max()
            
            # Create bins
            bin_edges = np.linspace(min_price, max_price, n_bins + 1)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            # Calculate volume per bin
            volumes, _ = np.histogram(price, bins=bin_edges, weights=volume)
            
            # Find Point of Control (POC)
            poc_idx = np.argmax(volumes)
            poc = bin_centers[poc_idx]
            
            # Calculate Value Area (70% of volume)
            sorted_indices = np.argsort(-volumes)
            sorted_volumes = volumes[sorted_indices]
            
            cumulative_volume = np.cumsum(sorted_volumes)
            total_volume = cumulative_volume[-1]
            
            # Find indices for 70% of volume
            value_area_indices = np.where(cumulative_volume <= 0.7 * total_volume)[0]
            
            # Get corresponding price levels
            value_area_levels = bin_centers[sorted_indices[value_area_indices]]
            
            # Get value area range
            value_area = [value_area_levels.min(), value_area_levels.max()]
            
            return {
                'price_levels': bin_centers.tolist(),
                'volumes': volumes.tolist(),
                'poc': float(poc),
                'value_area': [float(x) for x in value_area]
            }
            
        except Exception as e:
            logger.error(f"Error generating volume profile: {str(e)}")
            return {
                'price_levels': [],
                'volumes': [],
                'poc': None,
                'value_area': []
            }
    
    def get_regime_distribution(self, symbol: str) -> Dict[str, Any]:
        """
        Get market regime distribution for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with regime distribution data
        """
        cache_key = 'regimes'
        cache_subkey = symbol
        
        # Check if cache is valid
        if self._is_cache_valid(cache_key, cache_subkey):
            logger.debug(f"Using cached regime distribution for {symbol}")
            return self.cache[cache_key][cache_subkey]
        
        try:
            # Get regime data from market monitor
            logger.info(f"Fetching regime data for {symbol}")
            regimes = self.market_monitor.detect_market_regimes()
            
            if symbol not in regimes:
                # If symbol not found but we have cache, return cache with warning
                if cache_key in self.cache and cache_subkey in self.cache[cache_key]:
                    logger.warning(f"No regime data for {symbol}, using cached data")
                    return self.cache[cache_key][cache_subkey]
                else:
                    # No cache, return fallback data
                    logger.error(f"No regime data for {symbol} and no valid cache")
                    return self._get_fallback_regime_distribution(symbol)
            
            # Extract regime data
            regime_data = regimes[symbol]
            
            # Validate data
            if not self._validate_regime_data(regime_data):
                # If validation fails but we have cache, return cache with warning
                if cache_key in self.cache and cache_subkey in self.cache[cache_key]:
                    logger.warning(f"Invalid regime data for {symbol}, using cached data")
                    return self.cache[cache_key][cache_subkey]
                else:
                    # No cache, return fallback data
                    logger.error(f"Invalid regime data for {symbol} and no valid cache")
                    return self._get_fallback_regime_distribution(symbol)
            
            # Create result
            result = {
                'symbol': symbol,
                'current_regime': regime_data.get('current_regime', 'unknown'),
                'regimes': regime_data.get('regimes', []),
                'counts': regime_data.get('counts', []),
                'transitions': regime_data.get('transitions', [])
            }
            
            # Update cache
            if cache_key not in self.cache:
                self.cache[cache_key] = {}
            self.cache[cache_key][cache_subkey] = result
            
            if cache_key not in self.last_updates:
                self.last_updates[cache_key] = {}
            self.last_updates[cache_key][cache_subkey] = datetime.now()
            
            if cache_key not in self.last_successful_updates:
                self.last_successful_updates[cache_key] = {}
            self.last_successful_updates[cache_key][cache_subkey] = datetime.now()
            
            if cache_key not in self.errors:
                self.errors[cache_key] = {}
            self.errors[cache_key][cache_subkey] = None
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting regime distribution for {symbol}: {str(e)}")
            
            if cache_key not in self.errors:
                self.errors[cache_key] = {}
            self.errors[cache_key][cache_subkey] = {
                'time': datetime.now(),
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Return cached data if available
            if cache_key in self.cache and cache_subkey in self.cache[cache_key]:
                logger.warning(f"Error fetching regime data for {symbol}, using cached data")
                return self.cache[cache_key][cache_subkey]
            else:
                # No cache, return fallback data
                return self._get_fallback_regime_distribution(symbol)
    
    def get_correlation_matrix(self) -> Dict[str, Any]:
        """
        Get correlation matrix for all monitored symbols.
        
        Returns:
            Dictionary with correlation matrix data
        """
        cache_key = 'correlation'
        
        # Check if cache is valid
        if self._is_cache_valid(cache_key):
            logger.debug("Using cached correlation matrix")
            return self.cache[cache_key]
        
        try:
            # Get correlation data from market monitor
            market_monitor = get_market_monitor()
            
            # Get list of symbols
            symbols = config.TRADING_CONFIG.get('symbols')
            if not symbols:
                symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
            
            # Get price data for each symbol
            price_data = {}
            for symbol in symbols:
                try:
                    df = market_monitor.get_price_data(symbol, '1d', 30)
                    price_data[symbol] = df['close']
                except Exception as e:
                    logger.warning(f"Error getting price data for {symbol}: {str(e)}")
            
            # If no data, return fallback
            if not price_data:
                logger.error("No price data available for correlation matrix")
                if self.cache[cache_key]:
                    return self.cache[cache_key]
                else:
                    return self._get_fallback_correlation_matrix()
            
            # Create DataFrame
            price_df = pd.DataFrame(price_data)
            
            # Calculate correlation matrix
            correlation = price_df.corr().fillna(0)
            
            # Create result
            result = {
                'symbols': correlation.index.tolist(),
                'matrix': correlation.values.tolist()
            }
            
            # Update cache
            self.cache[cache_key] = result
            self.last_updates[cache_key] = datetime.now()
            self.last_successful_updates[cache_key] = datetime.now()
            self.errors[cache_key] = None
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting correlation matrix: {str(e)}")
            self.errors[cache_key] = {
                'time': datetime.now(),
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Return cached data if available
            if self.cache[cache_key]:
                logger.warning("Error fetching correlation matrix, using cached data")
                return self.cache[cache_key]
            else:
                # No cache, return fallback data
                return self._get_fallback_correlation_matrix()
    
    def get_strategy_performance(self) -> Dict[str, Any]:
        """
        Get performance data for all strategies.
        
        Returns:
            Dictionary with strategy performance data
        """
        cache_key = 'performance'
        
        # Check if cache is valid
        if self._is_cache_valid(cache_key):
            logger.debug("Using cached strategy performance data")
            return self.cache[cache_key]
        
        # This function would typically get real strategy performance data
        # For now, we'll simulate it
        
        # List of strategies
        strategies = ['LSTM Strategy', 'Volume Profile Strategy', 'Funding Rate Arbitrage']
        
        # Generate metrics for each strategy
        metrics = []
        for strategy in strategies:
            metrics.append({
                'total_return': np.random.uniform(10, 50),
                'annual_return': np.random.uniform(5, 30),
                'sharpe_ratio': np.random.uniform(0.5, 3.0),
                'max_drawdown': np.random.uniform(5, 25),
                'win_rate': np.random.uniform(40, 70),
                'profit_factor': np.random.uniform(1.0, 2.5),
                'num_trades': int(np.random.uniform(50, 300))
            })
        
        # Create result
        result = {
            'strategies': strategies,
            'metrics': metrics,
            'last_updated': datetime.now().isoformat()
        }
        
        # Update cache
        self.cache[cache_key] = result
        self.last_updates[cache_key] = datetime.now()
        self.last_successful_updates[cache_key] = datetime.now()
        
        return result
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Get active alerts from the market monitor.
        
        Returns:
            List of alert dictionaries
        """
        try:
            # Get alerts from market monitor
            alerts = self.market_monitor.generate_alerts()
            
            # Sort by timestamp (newest first)
            alerts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            return []
    
    def update_data(self) -> bool:
        """
        Manually update all data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Manually updating all data")
            
            # Update market monitor
            self.market_monitor.update_market_data()
            
            # Clear caches to force refresh
            self.cache = {
                'market_overview': None,
                'price_data': {},
                'volume_profile': {},
                'correlation': None,
                'performance': None,
                'regimes': {},
                'alerts': None
            }
            
            # Reset last update times
            now = datetime.now() - timedelta(minutes=10)  # Set to past to force immediate refresh
            self.last_updates = {
                'market_overview': now,
                'price_data': {},
                'volume_profile': {},
                'correlation': now,
                'performance': now,
                'regimes': {},
                'alerts': now
            }
            
            logger.info("Data update completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating data: {str(e)}")
            return False
    
    def _is_cache_valid(self, cache_key: str, cache_subkey: str = None) -> bool:
        """
        Check if cache is valid for a given key.
        
        Args:
            cache_key: Primary cache key
            cache_subkey: Secondary cache key (for nested caches)
            
        Returns:
            True if cache is valid, False otherwise
        """
        now = datetime.now()
        
        # Handle nested cache
        if cache_subkey is not None:
            # Check if cache exists
            if (cache_key not in self.cache or 
                cache_key not in self.last_updates or 
                cache_subkey not in self.cache[cache_key] or 
                cache_subkey not in self.last_updates[cache_key]):
                return False
            
            # Check if cache is valid
            last_update = self.last_updates[cache_key][cache_subkey]
            cache_data = self.cache[cache_key][cache_subkey]
            ttl = self.cache_ttl[cache_key]
            
            if cache_data is None:
                return False
                
            return (now - last_update).total_seconds() < ttl
        
        # Handle simple cache
        else:
            # Check if cache exists
            if cache_key not in self.cache or cache_key not in self.last_updates:
                return False
            
            # Check if cache is valid
            last_update = self.last_updates[cache_key]
            cache_data = self.cache[cache_key]
            ttl = self.cache_ttl[cache_key]
            
            if cache_data is None:
                return False
                
            return (now - last_update).total_seconds() < ttl
    
    def _validate_market_overview(self, data: Dict[str, Any]) -> bool:
        """
        Validate market overview data.
        
        Args:
            data: Market overview data
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            return False
        
        if 'market_data' not in data:
            return False
        
        if not isinstance(data['market_data'], list):
            return False
        
        return True
    
    def _validate_price_data(self, data: pd.DataFrame, symbol: str, timeframe: str) -> bool:
        """
        Validate price data.
        
        Args:
            data: Price data
            symbol: Symbol
            timeframe: Timeframe
            
        Returns:
            True if valid, False otherwise
        """
        if data is None or not isinstance(data, pd.DataFrame):
            return False
        
        if data.empty:
            return False
        
        required_columns = ['open', 'high', 'low', 'close']
        if not all(col in data.columns for col in required_columns):
            return False
        
        return True
    
    def _validate_regime_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate regime data.
        
        Args:
            data: Regime data
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            return False
        
        if 'current_regime' not in data:
            return False
        
        if 'regimes' not in data or 'counts' not in data:
            return False
        
        if len(data['regimes']) != len(data['counts']):
            return False
        
        return True
    
    def _get_fallback_market_overview(self) -> Dict[str, Any]:
        """
        Get fallback market overview data.
        
        Returns:
            Fallback market overview data
        """
        return {
            'market_data': [
                {
                    'symbol': 'BTC/USDT',
                    'price': 30000.0,
                    'daily_change': 0.0,
                    'volume': 1000000.0,
                    'regime': 'unknown'
                },
                {
                    'symbol': 'ETH/USDT',
                    'price': 2000.0,
                    'daily_change': 0.0,
                    'volume': 500000.0,
                    'regime': 'unknown'
                }
            ],
            'timestamp': datetime.now().isoformat(),
            '_fallback': True
        }
    
    def _get_fallback_price_data(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Get fallback price data.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            
        Returns:
            Fallback price data
        """
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'data': {
                'timestamps': [datetime.now().isoformat()],
                'open': [0.0],
                'high': [0.0],
                'low': [0.0],
                'close': [0.0],
                'volume': [0.0]
            },
            'indicators': {},
            '_fallback': True
        }
    
    def _get_fallback_volume_profile(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Get fallback volume profile data.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            
        Returns:
            Fallback volume profile data
        """
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'price_levels': [],
            'volumes': [],
            'poc': None,
            'value_area': [],
            '_fallback': True
        }
    
    def _get_fallback_regime_distribution(self, symbol: str) -> Dict[str, Any]:
        """
        Get fallback regime distribution data.
        
        Args:
            symbol: Symbol
            
        Returns:
            Fallback regime distribution data
        """
        return {
            'symbol': symbol,
            'current_regime': 'unknown',
            'regimes': ['Bull', 'Bear', 'Sideways'],
            'counts': [0, 0, 0],
            'transitions': [],
            '_fallback': True
        }
    
    def _get_fallback_correlation_matrix(self) -> Dict[str, Any]:
        """
        Get fallback correlation matrix data.
        
        Returns:
            Fallback correlation matrix data
        """
        symbols = ['BTC/USDT', 'ETH/USDT']
        matrix = [
            [1.0, 0.7],
            [0.7, 1.0]
        ]
        
        return {
            'symbols': symbols,
            'matrix': matrix,
            '_fallback': True
        }
    
    def get_error_status(self) -> Dict[str, Any]:
        """
        Get error status for all data sources.
        
        Returns:
            Dictionary with error status
        """
        status = {}
        
        for key, value in self.errors.items():
            if isinstance(value, dict):
                status[key] = {}
                for subkey, error in value.items():
                    if error:
                        status[key][subkey] = {
                            'has_error': True,
                            'time': error['time'].isoformat(),
                            'error': error['error']
                        }
                    else:
                        status[key][subkey] = {
                            'has_error': False
                        }
            else:
                if value:
                    status[key] = {
                        'has_error': True,
                        'time': value['time'].isoformat(),
                        'error': value['error']
                    }
                else:
                    status[key] = {
                        'has_error': False
                    }
        
        return status

# Singleton instance
_market_data_handler = None

def get_market_data_handler() -> MarketDataHandler:
    """
    Get the market data handler instance.
    
    Returns:
        Market data handler instance
    """
    global _market_data_handler
    
    if _market_data_handler is None:
        _market_data_handler = MarketDataHandler()
    
    return _market_data_handler 