# advanced_trading/strategies/funding_arbitrage.py

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

from ..data.exchange_api import ExchangeAPI
from ..utils.risk_management import calculate_position_size

logger = logging.getLogger(__name__)

class FundingRateArbitrage:
    """
    Strategy to exploit funding rate imbalances between exchanges
    or between perpetual contracts and spot.
    """
    
    def __init__(self, 
                min_rate_threshold: float = 0.1/100,  # 0.1% per 8h
                max_position_per_pair: float = 0.2,   # Maximum 20% allocation per pair
                lookback_periods: int = 10,           # For calculating historical variance
                exchanges: List[str] = None):
        """
        Initialize the funding rate arbitrage strategy.
        
        Args:
            min_rate_threshold: Minimum funding rate differential to trigger a trade
            max_position_per_pair: Maximum position size as fraction of portfolio
            lookback_periods: Number of funding periods to look back
            exchanges: List of exchanges to monitor (default: all available)
        """
        self.min_rate_threshold = min_rate_threshold
        self.max_position_per_pair = max_position_per_pair
        self.lookback_periods = lookback_periods
        
        # Initialize exchange connections
        self.exchanges = exchanges or ["binance", "bybit", "hyperliquid"]
        self.apis = {}
        for exchange in self.exchanges:
            self.apis[exchange] = ExchangeAPI(exchange)
        
        # Track active arbitrage positions
        self.active_positions = {}
        
        logger.info(f"Initialized Funding Rate Arbitrage strategy with {len(self.exchanges)} exchanges")
    
    def get_funding_rates(self) -> pd.DataFrame:
        """
        Retrieve current funding rates from all exchanges.
        
        Returns:
            DataFrame with funding rates for all symbols across exchanges
        """
        all_rates = []
        
        for exchange, api in self.apis.items():
            try:
                rates = api.get_funding_rates()
                
                # Add exchange column
                rates['exchange'] = exchange
                
                all_rates.append(rates)
            except Exception as e:
                logger.error(f"Error fetching funding rates from {exchange}: {e}")
        
        if not all_rates:
            logger.warning("Failed to retrieve funding rates from any exchange")
            return pd.DataFrame()
        
        # Combine all rates
        combined_rates = pd.concat(all_rates, ignore_index=True)
        
        # Calculate annualized rates (assuming 8h funding intervals)
        combined_rates['annualized_rate'] = combined_rates['rate'] * 3 * 365
        
        return combined_rates
    
    def find_opportunities(self) -> List[Dict]:
        """
        Find funding rate arbitrage opportunities.
        
        Returns:
            List of opportunity dictionaries
        """
        # Get current funding rates
        current_rates = self.get_funding_rates()
        
        if current_rates.empty:
            return []
        
        opportunities = []
        
        # Group by symbol to find rate differences
        for symbol, group in current_rates.groupby('symbol'):
            if len(group) < 2:
                continue  # Need at least 2 exchanges for arbitrage
            
            # Find highest and lowest rates
            highest = group.loc[group['rate'].idxmax()]
            lowest = group.loc[group['rate'].idxmin()]
            
            # Calculate rate differential
            rate_diff = highest['rate'] - lowest['rate']
            
            # Check if differential exceeds threshold
            if abs(rate_diff) > self.min_rate_threshold:
                # This is an opportunity
                opportunity = {
                    'symbol': symbol,
                    'long_exchange': lowest['exchange'],
                    'short_exchange': highest['exchange'],
                    'rate_diff': rate_diff,
                    'annualized_diff': rate_diff * 3 * 365,  # 8h funding * 3 per day * 365 days
                    'timestamp': datetime.now()
                }
                
                opportunities.append(opportunity)
                
                logger.info(f"Found funding arbitrage opportunity: {symbol}, "
                          f"Long on {lowest['exchange']} at {lowest['rate']:.4%}, "
                          f"Short on {highest['exchange']} at {highest['rate']:.4%}, "
                          f"Diff: {rate_diff:.4%}, Annualized: {opportunity['annualized_diff']:.2%}")
        
        # Sort by rate differential (best opportunities first)
        opportunities.sort(key=lambda x: abs(x['rate_diff']), reverse=True)
        
        return opportunities
    
    def execute_arbitrage(self, capital: float, max_pairs: int = 5) -> List[Dict]:
        """
        Execute funding rate arbitrage trades.
        
        Args:
            capital: Available capital
            max_pairs: Maximum number of pairs to trade
            
        Returns:
            List of executed trades
        """
        # Find opportunities
        opportunities = self.find_opportunities()
        
        if not opportunities:
            logger.info("No funding arbitrage opportunities found")
            return []
        
        # Limit to top opportunities
        top_opportunities = opportunities[:max_pairs]
        
        # Calculate position sizes
        capital_per_pair = capital * self.max_position_per_pair
        
        executed_trades = []
        
        # Execute trades for each opportunity
        for opp in top_opportunities:
            symbol = opp['symbol']
            long_exchange = opp['long_exchange']
            short_exchange = opp['short_exchange']
            
            try:
                # Calculate position size based on risk management
                position_size = min(
                    capital_per_pair,
                    capital * self.max_position_per_pair
                )
                
                # Execute long position
                long_api = self.apis[long_exchange]
                long_order = long_api.create_order(
                    symbol=symbol,
                    side='buy',
                    quantity=position_size
                )
                
                # Execute short position
                short_api = self.apis[short_exchange]
                short_order = short_api.create_order(
                    symbol=symbol,
                    side='sell',
                    quantity=position_size
                )
                
                # Record the arbitrage position
                position = {
                    'symbol': symbol,
                    'long_exchange': long_exchange,
                    'short_exchange': short_exchange,
                    'position_size': position_size,
                    'entry_rate_diff': opp['rate_diff'],
                    'entry_time': datetime.now(),
                    'long_order_id': long_order['id'],
                    'short_order_id': short_order['id']
                }
                
                self.active_positions[symbol] = position
                executed_trades.append(position)
                
                logger.info(f"Executed funding arbitrage: {symbol}, Size: {position_size}")
                
            except Exception as e:
                logger.error(f"Error executing funding arbitrage for {symbol}: {e}")
        
        return executed_trades
    
    def monitor_positions(self) -> List[Dict]:
        """
        Monitor active arbitrage positions and close if necessary.
        
        Returns:
            List of closed positions
        """
        if not self.active_positions:
            return []
        
        # Get current funding rates
        current_rates = self.get_funding_rates()
        closed_positions = []
        
        # Check each active position
        for symbol, position in list(self.active_positions.items()):
            # Find current rate differential
            symbol_rates = current_rates[current_rates['symbol'] == symbol]
            
            if symbol_rates.empty:
                logger.warning(f"Could not find current rates for {symbol}")
                continue
            
            try:
                long_rate = symbol_rates[symbol_rates['exchange'] == position['long_exchange']]['rate'].iloc[0]
                short_rate = symbol_rates[symbol_rates['exchange'] == position['short_exchange']]['rate'].iloc[0]
                
                current_diff = short_rate - long_rate
                
                # Check if differential has shrunk significantly or reversed
                if current_diff < position['entry_rate_diff'] * 0.3 or current_diff < 0:
                    # Close the position
                    long_api = self.apis[position['long_exchange']]
                    short_api = self.apis[position['short_exchange']]
                    
                    # Close long position
                    long_close = long_api.create_order(
                        symbol=symbol,
                        side='sell',
                        quantity=position['position_size']
                    )
                    
                    # Close short position
                    short_close = short_api.create_order(
                        symbol=symbol,
                        side='buy',
                        quantity=position['position_size']
                    )
                    
                    # Calculate profit/loss
                    # Note: In a real system, you'd calculate actual P&L from order executions
                    funding_earned = position['entry_rate_diff'] * position['position_size']
                    
                    # Record closed position
                    position['exit_time'] = datetime.now()
                    position['exit_rate_diff'] = current_diff
                    position['funding_earned'] = funding_earned
                    position['duration'] = (position['exit_time'] - position['entry_time']).total_seconds() / 3600
                    
                    closed_positions.append(position)
                    
                    # Remove from active positions
                    del self.active_positions[symbol]
                    
                    logger.info(f"Closed funding arbitrage: {symbol}, Duration: {position['duration']:.1f}h, "
                              f"Funding earned: {funding_earned}")
                    
            except Exception as e:
                logger.error(f"Error monitoring position for {symbol}: {e}")
        
        return closed_positions