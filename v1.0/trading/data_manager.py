"""
Data Manager Module
------------------
Handles data collection, processing, and storage.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
import json

import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from pathlib import Path

import config
from trading.exchange import HyperliquidExchange, BinanceExchange
from utils.indicators import add_technical_indicators

logger = logging.getLogger(__name__)

class DataManager:
    """Manage data collection, processing, and storage"""
    
    def __init__(self):
        """Initialize data manager"""
        self.hyperliquid = HyperliquidExchange()
        self.binance = BinanceExchange()
        self.data_dir = config.DATA_DIR
        
        # Ensure data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def fetch_and_save_data(self, symbol: str = 'BTC', timeframe: str = '1h', 
                            limit: int = 500, use_binance: bool = True) -> pd.DataFrame:
        """Fetch historical data and save to CSV"""
        try:
            # Fetch data from exchange
            if use_binance:
                logger.info(f"Fetching data from Binance for {symbol} {timeframe}")
                data = self.binance.get_historical_klines(symbol, timeframe, 
                                                         start_time=datetime.now() - timedelta(hours=limit))
            else:
                logger.info(f"Fetching data from Hyperliquid for {symbol} {timeframe}")
                data = self.hyperliquid.get_historical_data(symbol, timeframe, limit)
            
            if data.empty:
                logger.error(f"No data returned for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Save to CSV
            filename = self.data_dir / f"{symbol}_{timeframe}.csv"
            data.to_csv(filename)
            logger.info(f"Saved {len(data)} records to {filename}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error in fetch_and_save_data: {str(e)}")
            return pd.DataFrame()
    
    def fetch_5year_data(self, symbol: str = 'BTC', timeframe: str = '1h') -> pd.DataFrame:
        """Fetch 5 years of historical data from Binance"""
        try:
            logger.info(f"Fetching 5 years of data from Binance for {symbol} {timeframe}")
            
            # Use the dedicated 5-year data fetching method
            data = self.binance.get_5year_historical_data(symbol, timeframe)
            
            if data.empty:
                logger.error(f"No 5-year data returned for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # The data is already saved by the get_5year_historical_data method
            logger.info(f"Successfully retrieved 5 years of data for {symbol} {timeframe} ({len(data)} records)")
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching 5-year data: {str(e)}")
            return pd.DataFrame()
    
    def load_data(self, symbol: str = 'BTC', timeframe: str = '1h', 
                  refresh: bool = False, use_5year: bool = False) -> pd.DataFrame:
        """Load data from CSV or fetch if needed"""
        try:
            # Determine the filename based on whether we want 5-year data
            if use_5year:
                filename = self.data_dir / f"{symbol}_{timeframe}_5years.csv"
                fetch_method = self.fetch_5year_data
            else:
                filename = self.data_dir / f"{symbol}_{timeframe}.csv"
                fetch_method = lambda s, t: self.fetch_and_save_data(s, t, use_binance=True)
            
            # Check if file exists and doesn't need refreshing
            if filename.exists() and not refresh:
                try:
                    data = pd.read_csv(filename)
                    
                    # Handle different column names for timestamp
                    if 'time' in data.columns:
                        data['time'] = pd.to_datetime(data['time'])
                        data.set_index('time', inplace=True)
                    elif 'timestamp' in data.columns:
                        data['timestamp'] = pd.to_datetime(data['timestamp'])
                        data.set_index('timestamp', inplace=True)
                    
                    logger.info(f"Loaded {len(data)} records from {filename}")
                    return data
                except Exception as e:
                    logger.error(f"Error loading data from file: {str(e)}")
                    # If error, fall back to fetching new data
            
            # Fetch new data
            return fetch_method(symbol, timeframe)
            
        except Exception as e:
            logger.error(f"Error in load_data: {str(e)}")
            return pd.DataFrame()
    
    def prepare_data_for_backtest(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for backtesting with indicators"""
        # Create a copy to avoid modifying original
        bt_data = data.copy()
        
        # Make sure columns are named according to backtrader expectations
        if 'open' in bt_data.columns:
            bt_data.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }, inplace=True)
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in bt_data.columns:
                bt_data[col] = pd.to_numeric(bt_data[col])
        
        return bt_data
    
    def get_data_with_indicators(self, symbol: str = 'BTC', timeframe: str = '1h', 
                                refresh: bool = False, use_5year: bool = True) -> pd.DataFrame:
        """Get data with technical indicators added"""
        # Load raw data
        data = self.load_data(symbol, timeframe, refresh, use_5year)
        
        if data.empty:
            return data
            
        # Add technical indicators
        return add_technical_indicators(data)
    
    def get_historical_funding_rates(self, symbol: str = 'BTC', 
                                    days: int = 30) -> pd.DataFrame:
        """
        Get historical funding rates
        
        Note: Hyperliquid API might not provide historical funding rates directly.
        This function may need to be adapted based on available endpoints.
        """
        try:
            # In a production system, this would fetch from exchange or database
            # For now, we'll create simulated funding rate data
            
            # Get price data to align timestamps
            price_data = self.load_data(symbol, '8h', use_5year=True)
            timestamps = price_data.index
            
            # Generate synthetic funding rates based on price action
            # (this is a simplified model - real implementation would use actual funding data)
            returns = price_data['close'].pct_change().fillna(0)
            vol = returns.rolling(30).std().fillna(0)
            
            # Generate funding rates with some relation to price movements
            # Funding rates tend to be positive when prices rise rapidly (longs pay shorts)
            # and negative when prices fall rapidly (shorts pay longs)
            funding_rates = returns * 0.1 + np.random.normal(0, 0.001, len(returns))
            
            # Clip to realistic funding rate range
            funding_rates = np.clip(funding_rates, -0.01, 0.01)
            
            # Create DataFrame
            funding_df = pd.DataFrame({
                'symbol': symbol,
                'funding_rate': funding_rates
            }, index=timestamps)
            
            return funding_df
            
        except Exception as e:
            logger.error(f"Error getting historical funding rates: {str(e)}")
            return pd.DataFrame()
    
    def get_market_liquidity(self, symbol: str = 'BTC', depth: int = 20) -> Dict:
        """Get market liquidity analysis from orderbook"""
        try:
            # Get orderbook
            orderbook = self.hyperliquid.get_orderbook(symbol, depth)
            
            if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
                logger.warning(f"Invalid orderbook data for {symbol}")
                return {}
                
            # Convert to arrays for analysis
            bids = np.array(orderbook['bids'])
            asks = np.array(orderbook['asks'])
            
            if len(bids) == 0 or len(asks) == 0:
                return {}
                
            # Calculate spread
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread = best_ask - best_bid
            spread_pct = spread / best_bid * 100
            
            # Calculate total liquidity on each side
            bid_liquidity = sum(float(bid[1]) for bid in bids)
            ask_liquidity = sum(float(ask[1]) for ask in asks)
            
            # Calculate imbalance
            imbalance = (bid_liquidity - ask_liquidity) / (bid_liquidity + ask_liquidity)
            
            # Find liquidity clusters (peaks in volume)
            # For bids
            bid_prices = np.array([float(b[0]) for b in bids])
            bid_volumes = np.array([float(b[1]) for b in bids])
            bid_peaks, _ = find_peaks(bid_volumes, height=np.mean(bid_volumes) * 1.5)
            
            # For asks
            ask_prices = np.array([float(a[0]) for a in asks])
            ask_volumes = np.array([float(a[1]) for a in asks])
            ask_peaks, _ = find_peaks(ask_volumes, height=np.mean(ask_volumes) * 1.5)
            
            # Collect key liquidity levels
            liquidity_levels = []
            for i in bid_peaks:
                liquidity_levels.append({
                    'price': bid_prices[i],
                    'volume': bid_volumes[i],
                    'type': 'bid'
                })
                
            for i in ask_peaks:
                liquidity_levels.append({
                    'price': ask_prices[i],
                    'volume': ask_volumes[i],
                    'type': 'ask'
                })
            
            # Sort by volume
            liquidity_levels.sort(key=lambda x: x['volume'], reverse=True)
            
            return {
                'spread': spread,
                'spread_pct': spread_pct,
                'bid_liquidity': bid_liquidity,
                'ask_liquidity': ask_liquidity,
                'imbalance': imbalance,
                'key_levels': liquidity_levels[:5]  # Top 5 liquidity levels
            }
                
        except Exception as e:
            logger.error(f"Error analyzing market liquidity: {str(e)}")
            return {}
    
    def calculate_volume_profile(self, data: pd.DataFrame, 
                                num_bins: int = 100) -> Dict:
        """Calculate volume profile and find key levels"""
        try:
            if data.empty:
                return {}
                
            # Extract price and volume data
            prices = data['close'].values
            volumes = data['volume'].values
            
            # Calculate price range
            min_price = min(prices)
            max_price = max(prices)
            price_range = max_price - min_price
            
            # Create bins
            bins = np.linspace(min_price, max_price, num_bins + 1)
            
            # Calculate histogram
            hist, bin_edges = np.histogram(prices, bins=bins, weights=volumes)
            
            # Calculate bin centers
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            # Find Point of Control (POC) - price level with highest volume
            poc_idx = np.argmax(hist)
            poc = bin_centers[poc_idx]
            
            # Calculate Value Area (70% of volume)
            total_volume = np.sum(hist)
            target_volume = total_volume * 0.7
            
            # Sort indices by volume (highest to lowest)
            sorted_indices = np.argsort(-hist)
            
            # Take indices until reaching 70% of volume
            cumulative_volume = 0
            value_area_indices = []
            
            for idx in sorted_indices:
                value_area_indices.append(idx)
                cumulative_volume += hist[idx]
                if cumulative_volume >= target_volume:
                    break
            
            # Find Value Area High and Value Area Low
            vah = bin_centers[max(value_area_indices)]
            val = bin_centers[min(value_area_indices)]
            
            # Create profile data for visualization
            profile_data = [
                {'price': float(price), 'volume': float(volume)}
                for price, volume in zip(bin_centers, hist)
            ]
            
            return {
                'poc': float(poc),
                'vah': float(vah),
                'val': float(val),
                'profile': profile_data
            }
            
        except Exception as e:
            logger.error(f"Error calculating volume profile: {str(e)}")
            return {}
    
    def save_analysis_results(self, analysis: Dict, symbol: str, 
                             analysis_type: str) -> bool:
        """Save analysis results to JSON file"""
        try:
            if not analysis:
                return False
                
            # Create directory for analysis results
            analysis_dir = self.data_dir / 'analysis'
            if not os.path.exists(analysis_dir):
                os.makedirs(analysis_dir)
                
            # Create filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = analysis_dir / f"{symbol}_{analysis_type}_{timestamp}.json"
            
            # Save to JSON
            with open(filename, 'w') as f:
                json.dump(analysis, f, indent=2)
                
            logger.info(f"Saved {analysis_type} analysis for {symbol} to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving analysis results: {str(e)}")
            return False
    
    def load_latest_analysis(self, symbol: str, analysis_type: str) -> Dict:
        """Load the most recent analysis of the specified type"""
        try:
            analysis_dir = self.data_dir / 'analysis'
            if not os.path.exists(analysis_dir):
                return {}
                
            # List all matching files
            files = list(analysis_dir.glob(f"{symbol}_{analysis_type}_*.json"))
            
            if not files:
                return {}
                
            # Sort by modification time (newest first)
            latest_file = max(files, key=os.path.getmtime)
            
            # Load JSON
            with open(latest_file, 'r') as f:
                analysis = json.load(f)
                
            logger.info(f"Loaded latest {analysis_type} analysis for {symbol} from {latest_file}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error loading latest analysis: {str(e)}")
            return {}
            
    def fetch_macroeconomic_data(self) -> pd.DataFrame:
        """
        Fetch macroeconomic data from FRED API
        
        Returns:
            DataFrame with macroeconomic indicators
        """
        try:
            # This is a placeholder for actual implementation
            # In a real system, we would use the FRED API to fetch data
            logger.info("Fetching macroeconomic data is not yet implemented")
            
            # Create a synthetic dataset for now
            today = datetime.now()
            dates = pd.date_range(end=today, periods=60, freq='M')  # Monthly data for 5 years
            
            # Create synthetic data
            data = pd.DataFrame(index=dates)
            
            # M2 Money Supply (trillions USD)
            base_m2 = 15.0  # Starting value
            growth_rate = 0.005  # Monthly growth rate
            noise = np.random.normal(0, 0.02, len(dates))
            m2_trend = np.array([base_m2 * (1 + growth_rate) ** i for i in range(len(dates))])
            data['m2_money_supply'] = m2_trend * (1 + noise)
            
            # Inflation Rate (CPI YoY %)
            base_inflation = 0.02  # 2%
            inflation_cycle = 0.01 * np.sin(np.linspace(0, 4*np.pi, len(dates)))
            inflation_noise = np.random.normal(0, 0.005, len(dates))
            data['inflation_rate'] = base_inflation + inflation_cycle + inflation_noise
            
            # S&P 500 Index
            base_sp500 = 3000
            sp500_growth = 0.007  # Monthly growth
            sp500_noise = np.random.normal(0, 0.03, len(dates))
            sp500_trend = np.array([base_sp500 * (1 + sp500_growth) ** i for i in range(len(dates))])
            data['sp500_index'] = sp500_trend * (1 + sp500_noise)
            
            # GDP Growth Rate (Quarterly, annualized)
            base_gdp_growth = 0.025  # 2.5%
            gdp_cycle = 0.015 * np.sin(np.linspace(0, 2*np.pi, len(dates)))
            gdp_noise = np.random.normal(0, 0.01, len(dates))
            data['gdp_growth'] = base_gdp_growth + gdp_cycle + gdp_noise
            
            # Unemployment Rate
            base_unemployment = 0.05  # 5%
            unemployment_cycle = 0.02 * np.sin(np.linspace(0, 3*np.pi, len(dates)))
            unemployment_noise = np.random.normal(0, 0.005, len(dates))
            data['unemployment_rate'] = base_unemployment + unemployment_cycle + unemployment_noise
            data['unemployment_rate'] = np.clip(data['unemployment_rate'], 0.03, 0.12)  # Realistic bounds
            
            # Save to CSV
            filename = self.data_dir / "macroeconomic_data.csv"
            data.to_csv(filename)
            logger.info(f"Saved synthetic macroeconomic data to {filename}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching macroeconomic data: {str(e)}")
            return pd.DataFrame()