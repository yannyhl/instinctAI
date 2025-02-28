"""
Market Monitor Module
------------------
Utility for monitoring cryptocurrency markets, including prices, volumes, and market events.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Union
from datetime import datetime, timedelta
import time
import json
import threading
from pathlib import Path
import requests

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import project modules
import config
from data.data_loader import DataLoader
from utils.event_detection import MarketEventDetector
from utils.regime_detection import RegimeClassifier, detect_regime

# Set up logging
logger = logging.getLogger(__name__)

class MarketMonitor:
    """
    Real-time market monitor for cryptocurrency data.
    
    Features:
    - Real-time price and volume tracking
    - Market regime detection
    - Market event detection
    - Performance tracking for active strategies
    - Alert generation for significant market moves
    """
    
    def __init__(self, 
               symbols: List[str] = None, 
               timeframes: List[str] = None,
               update_interval: int = 60,
               cache_dir: Optional[str] = None):
        """
        Initialize the market monitor.
        
        Args:
            symbols: List of symbols to monitor
            timeframes: List of timeframes to track
            update_interval: Update interval in seconds
            cache_dir: Directory to cache market data
        """
        self.symbols = symbols or config.TRADING_CONFIG['symbols']
        self.timeframes = timeframes or ['1m', '5m', '15m', '1h', '4h', '1d']
        self.update_interval = update_interval
        
        # Set up cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = config.DATA_DIR / "market_monitor"
        
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize data structures
        self.market_data = {}  # Dict of {symbol: {timeframe: DataFrame}}
        self.latest_prices = {}  # Dict of {symbol: price}
        self.daily_changes = {}  # Dict of {symbol: percent_change}
        self.market_regimes = {}  # Dict of {symbol: regime}
        self.recent_events = []  # List of recent market events
        self.strategy_performance = {}  # Dict of {strategy: performance_metrics}
        
        # Initialize helpers
        self.data_loader = DataLoader()
        self.event_detector = MarketEventDetector()
        self.regime_classifier = RegimeClassifier()
        
        # Threading
        self.running = False
        self.update_thread = None
        self.last_update_time = None
        
        logger.info(f"Initialized market monitor for {len(self.symbols)} symbols")
    
    def start(self):
        """Start the market monitor update thread."""
        if self.running:
            logger.warning("Market monitor already running")
            return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        logger.info(f"Started market monitor update thread with {self.update_interval}s interval")
    
    def stop(self):
        """Stop the market monitor update thread."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=2.0)
        logger.info("Stopped market monitor update thread")
    
    def _update_loop(self):
        """Main update loop for the market monitor."""
        while self.running:
            try:
                self.update_market_data()
                self.detect_market_regimes()
                self.detect_market_events()
                
                # Save state
                self._save_state()
                
                # Update last update time
                self.last_update_time = datetime.now()
                
                # Sleep until next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in market monitor update loop: {e}")
                time.sleep(10)  # Sleep on error
    
    def update_market_data(self):
        """Update market data for all symbols and timeframes."""
        logger.info(f"Updating market data for {len(self.symbols)} symbols")
        
        for symbol in self.symbols:
            self.market_data[symbol] = {}
            
            # For each timeframe, load recent data
            for timeframe in self.timeframes:
                try:
                    # Calculate start date based on timeframe
                    start_date = self._calculate_start_date(timeframe)
                    
                    # Load data
                    data = self.data_loader.load_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=datetime.now().strftime('%Y-%m-%d')
                    )
                    
                    if data is not None and not data.empty:
                        self.market_data[symbol][timeframe] = data
                        logger.debug(f"Loaded {len(data)} {timeframe} data points for {symbol}")
                    else:
                        logger.warning(f"No {timeframe} data loaded for {symbol}")
                
                except Exception as e:
                    logger.error(f"Error loading {timeframe} data for {symbol}: {e}")
            
            # Update latest price and daily change
            if '1h' in self.market_data[symbol] and not self.market_data[symbol]['1h'].empty:
                hourly_data = self.market_data[symbol]['1h']
                self.latest_prices[symbol] = hourly_data['close'].iloc[-1]
                
                # Calculate 24h change
                if len(hourly_data) >= 24:
                    price_24h_ago = hourly_data['close'].iloc[-25]
                    self.daily_changes[symbol] = (self.latest_prices[symbol] / price_24h_ago - 1) * 100
                else:
                    self.daily_changes[symbol] = 0.0
        
        logger.info(f"Market data updated at {datetime.now()}")
    
    def _calculate_start_date(self, timeframe: str) -> str:
        """Calculate appropriate start date based on timeframe."""
        now = datetime.now()
        
        if timeframe == '1m':
            # For 1-minute data, get the last 4 hours
            start_date = (now - timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S')
        elif timeframe == '5m':
            # For 5-minute data, get the last 24 hours
            start_date = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        elif timeframe == '15m':
            # For 15-minute data, get the last 3 days
            start_date = (now - timedelta(days=3)).strftime('%Y-%m-%d')
        elif timeframe == '1h':
            # For hourly data, get the last 7 days
            start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        elif timeframe == '4h':
            # For 4-hour data, get the last 30 days
            start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        elif timeframe == '1d':
            # For daily data, get the last 90 days
            start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
        else:
            # Default to 30 days
            start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        
        return start_date
    
    def detect_market_regimes(self):
        """Detect current market regimes for all symbols."""
        logger.info("Detecting market regimes")
        
        for symbol in self.symbols:
            try:
                # Use daily data for regime detection
                if '1d' in self.market_data[symbol] and not self.market_data[symbol]['1d'].empty:
                    daily_data = self.market_data[symbol]['1d']
                    
                    # Calculate returns
                    returns = daily_data['close'].pct_change().dropna()
                    
                    if len(returns) >= 60:  # Need at least 60 data points
                        # Use simple regime detection
                        regime = detect_regime(returns, method='volatility')
                        self.market_regimes[symbol] = regime
                        
                        logger.info(f"Detected regime {regime} for {symbol}")
            
            except Exception as e:
                logger.error(f"Error detecting regime for {symbol}: {e}")
    
    def detect_market_events(self):
        """Detect significant market events."""
        logger.info("Detecting market events")
        
        # Get latest events for each symbol
        new_events = []
        
        for symbol in self.symbols:
            try:
                # Use daily data for event detection
                if '1d' in self.market_data[symbol] and not self.market_data[symbol]['1d'].empty:
                    daily_data = self.market_data[symbol]['1d']
                    
                    # Get symbol base (e.g., BTC from BTC/USDT)
                    symbol_base = symbol.split('/')[0]
                    
                    # Detect events
                    events = self.event_detector.detect_events(
                        market_data=daily_data,
                        start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                        end_date=datetime.now().strftime('%Y-%m-%d'),
                        symbols=[symbol_base]
                    )
                    
                    # Add symbol to events and append to new events
                    for event in events:
                        event['symbol'] = symbol
                        new_events.append(event)
            
            except Exception as e:
                logger.error(f"Error detecting events for {symbol}: {e}")
        
        # Sort events by date (most recent first)
        new_events.sort(key=lambda e: e['date'] if isinstance(e['date'], datetime) else datetime.now(), reverse=True)
        
        # Keep only the 50 most recent events
        self.recent_events = new_events[:50]
        
        logger.info(f"Detected {len(new_events)} market events")
    
    def update_strategy_performance(self, strategy_name: str, performance_metrics: Dict[str, float]):
        """Update performance metrics for a strategy."""
        self.strategy_performance[strategy_name] = performance_metrics
        logger.info(f"Updated performance metrics for {strategy_name}")
    
    def get_market_summary(self) -> Dict[str, Any]:
        """Get a summary of current market conditions."""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'prices': self.latest_prices,
            'daily_changes': self.daily_changes,
            'regimes': self.market_regimes,
            'recent_events': [
                {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in event.items()}
                for event in self.recent_events[:5]  # Include only most recent 5 events
            ],
            'strategy_performance': self.strategy_performance
        }
        
        return summary
    
    def get_price_data(self, symbol: str, timeframe: str = '1h', 
                     limit: int = 100) -> pd.DataFrame:
        """Get price data for a specific symbol and timeframe."""
        if symbol in self.market_data and timeframe in self.market_data[symbol]:
            data = self.market_data[symbol][timeframe]
            
            # Return last 'limit' rows
            if len(data) > limit:
                return data.iloc[-limit:]
            else:
                return data
        else:
            logger.warning(f"No data available for {symbol} on {timeframe} timeframe")
            return pd.DataFrame()
    
    def get_correlated_symbols(self, symbol: str, min_correlation: float = 0.7) -> List[Tuple[str, float]]:
        """
        Find correlated symbols based on price correlation.
        
        Args:
            symbol: Base symbol to find correlations for
            min_correlation: Minimum correlation threshold
            
        Returns:
            List of (symbol, correlation) tuples
        """
        correlations = []
        
        # Use daily data for correlation calculation
        if symbol not in self.market_data or '1d' not in self.market_data[symbol]:
            return correlations
        
        base_returns = self.market_data[symbol]['1d']['close'].pct_change().dropna()
        
        for other_symbol in self.symbols:
            if other_symbol == symbol:
                continue
                
            if other_symbol in self.market_data and '1d' in self.market_data[other_symbol]:
                other_returns = self.market_data[other_symbol]['1d']['close'].pct_change().dropna()
                
                # Calculate correlation
                if len(base_returns) > 20 and len(other_returns) > 20:
                    # Align series
                    common_idx = base_returns.index.intersection(other_returns.index)
                    if len(common_idx) > 20:
                        aligned_base = base_returns.loc[common_idx]
                        aligned_other = other_returns.loc[common_idx]
                        
                        corr = aligned_base.corr(aligned_other)
                        
                        if abs(corr) >= min_correlation:
                            correlations.append((other_symbol, corr))
        
        # Sort by absolute correlation (descending)
        correlations.sort(key=lambda x: abs(x[1]), reverse=True)
        
        return correlations
    
    def generate_alerts(self) -> List[Dict[str, Any]]:
        """
        Generate alerts for significant market conditions.
        
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        # Price change alerts
        for symbol, change in self.daily_changes.items():
            if abs(change) >= 10.0:  # 10% daily change
                alerts.append({
                    'type': 'price_change',
                    'symbol': symbol,
                    'value': change,
                    'message': f"{symbol} moved {change:.2f}% in the last 24 hours",
                    'timestamp': datetime.now().isoformat(),
                    'severity': 'high' if abs(change) >= 20.0 else 'medium'
                })
        
        # Regime change alerts
        for symbol, regime in self.market_regimes.items():
            # Check if we have a previous regime saved
            prev_regime_file = self.cache_dir / f"{symbol.replace('/', '_')}_regime.json"
            
            if prev_regime_file.exists():
                try:
                    with open(prev_regime_file, 'r') as f:
                        prev_data = json.load(f)
                        prev_regime = prev_data.get('regime')
                        
                        if prev_regime is not None and prev_regime != regime:
                            alerts.append({
                                'type': 'regime_change',
                                'symbol': symbol,
                                'from_regime': prev_regime,
                                'to_regime': regime,
                                'message': f"{symbol} regime changed from {prev_regime} to {regime}",
                                'timestamp': datetime.now().isoformat(),
                                'severity': 'high'
                            })
                except Exception as e:
                    logger.error(f"Error reading previous regime data: {e}")
            
            # Save current regime
            with open(prev_regime_file, 'w') as f:
                json.dump({'regime': regime, 'timestamp': datetime.now().isoformat()}, f)
        
        # Event alerts
        for event in self.recent_events[:3]:  # Consider only the most recent 3 events
            # Skip events older than 24 hours
            event_date = event.get('date')
            if event_date is None:
                continue
                
            if isinstance(event_date, str):
                try:
                    event_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                except:
                    continue
            
            if datetime.now() - event_date > timedelta(hours=24):
                continue
                
            alerts.append({
                'type': 'market_event',
                'symbol': event.get('symbol', 'Unknown'),
                'event_type': event.get('type', 'Unknown'),
                'message': event.get('description', 'Market event detected'),
                'timestamp': datetime.now().isoformat(),
                'severity': 'high' if event.get('impact_score', 0) > 7 else 'medium'
            })
        
        return alerts
    
    def _save_state(self):
        """Save the current state of the market monitor."""
        state = {
            'timestamp': datetime.now().isoformat(),
            'latest_prices': self.latest_prices,
            'daily_changes': self.daily_changes,
            'market_regimes': self.market_regimes,
            'recent_events': [
                {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in event.items()}
                for event in self.recent_events
            ],
            'strategy_performance': self.strategy_performance
        }
        
        # Save to file
        state_file = self.cache_dir / 'market_monitor_state.json'
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def load_state(self) -> bool:
        """
        Load the previous state of the market monitor.
        
        Returns:
            True if state was loaded successfully, False otherwise
        """
        state_file = self.cache_dir / 'market_monitor_state.json'
        
        if not state_file.exists():
            logger.warning("No saved state found")
            return False
        
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            self.latest_prices = state.get('latest_prices', {})
            self.daily_changes = state.get('daily_changes', {})
            self.market_regimes = state.get('market_regimes', {})
            
            # Parse datetime objects in events
            self.recent_events = state.get('recent_events', [])
            for event in self.recent_events:
                if 'date' in event and isinstance(event['date'], str):
                    try:
                        event['date'] = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                    except:
                        pass
            
            self.strategy_performance = state.get('strategy_performance', {})
            
            self.last_update_time = datetime.fromisoformat(state.get('timestamp', datetime.now().isoformat()))
            
            logger.info(f"Loaded market monitor state from {state_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading market monitor state: {e}")
            return False


# Singleton instance for global access
_market_monitor = None

def get_market_monitor(init_params: Dict = None) -> MarketMonitor:
    """Get the global market monitor instance."""
    global _market_monitor
    
    if _market_monitor is None:
        if init_params:
            _market_monitor = MarketMonitor(**init_params)
        else:
            _market_monitor = MarketMonitor()
    
    return _market_monitor 