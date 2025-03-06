"""
Funding Arbitrage Strategy

This strategy exploits funding rate differentials in perpetual futures markets.
It takes advantage of the funding rate mechanism in perpetual futures contracts
to generate returns with minimal directional risk.

The strategy works by:
1. Identifying perpetual futures contracts with significant funding rate differentials
2. Taking opposing positions across exchanges or contracts
3. Collecting funding payments while maintaining delta-neutral exposure
4. Unwinding positions when funding rate differentials normalize

Tags: [arbitrage, funding, perpetual_futures, low_risk]
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class FundingArbitrageStrategy(BaseStrategy):
    """
    Funding Arbitrage Strategy for exploiting funding rate differentials.
    
    This strategy identifies and exploits funding rate differentials between
    perpetual futures contracts, either on the same exchange or across multiple
    exchanges.
    
    Args:
        symbols: List of symbols to trade
        funding_threshold: Minimum funding rate differential to enter a position
        position_size: Size of position as percentage of available capital
        max_positions: Maximum number of concurrent arbitrage positions
        min_half_life: Minimum expected half-life of funding rate differential
        unwinding_threshold: Threshold to unwind positions when differential normalizes
        rebalance_frequency: How often to rebalance positions (in minutes)
        exchanges: Optional list of exchanges to use (default: all available)
    """
    
    # Required data for this strategy
    REQUIRED_DATA = ["funding_rates", "orderbook", "trade_history"]
    
    # Default parameters
    DEFAULT_PARAMS = {
        "funding_threshold": 0.0005,  # 0.05% minimum funding differential
        "position_size": 0.1,         # 10% of available capital per arbitrage
        "max_positions": 5,           # Maximum 5 concurrent arbitrage positions
        "min_half_life": 6,           # Minimum half-life of 6 hours
        "unwinding_threshold": 0.0002,  # Unwind when differential < 0.02%
        "rebalance_frequency": 60,    # Rebalance every 60 minutes
    }
    
    def __init__(
        self,
        symbols: List[str],
        funding_threshold: float = DEFAULT_PARAMS["funding_threshold"],
        position_size: float = DEFAULT_PARAMS["position_size"],
        max_positions: int = DEFAULT_PARAMS["max_positions"],
        min_half_life: float = DEFAULT_PARAMS["min_half_life"],
        unwinding_threshold: float = DEFAULT_PARAMS["unwinding_threshold"],
        rebalance_frequency: int = DEFAULT_PARAMS["rebalance_frequency"],
        exchanges: Optional[List[str]] = None
    ):
        """Initialize the funding arbitrage strategy."""
        super().__init__(name="FundingArbitrage")
        
        # Store parameters
        self.symbols = symbols
        self.funding_threshold = funding_threshold
        self.position_size = position_size
        self.max_positions = max_positions
        self.min_half_life = min_half_life
        self.unwinding_threshold = unwinding_threshold
        self.rebalance_frequency = rebalance_frequency
        self.exchanges = exchanges
        
        # State variables
        self.active_arbitrages = {}
        self.last_rebalance_time = None
        self.current_funding_rates = {}
        self.funding_rate_history = {}
        self.half_life_estimates = {}
        
        logger.info(f"Initialized FundingArbitrageStrategy with {len(symbols)} symbols")
        logger.info(f"Using funding threshold of {funding_threshold}, position size {position_size}")
    
    def initialize(self, data_provider, execution_handler, risk_manager=None):
        """
        Initialize the strategy with required components.
        
        Args:
            data_provider: Provider for market data
            execution_handler: Handler for executing orders
            risk_manager: Optional risk management component
        """
        super().initialize(data_provider, execution_handler, risk_manager)
        
        # Initialize funding rate history for each symbol
        for symbol in self.symbols:
            # Get historical funding rates if available
            try:
                history = self.data_provider.get_funding_rate_history(symbol)
                self.funding_rate_history[symbol] = history
                
                # Estimate half-life of funding rate differential
                if len(history) > 10:
                    self.half_life_estimates[symbol] = self._estimate_half_life(history)
                
                logger.info(f"Loaded funding rate history for {symbol}: {len(history)} records")
            except Exception as e:
                logger.warning(f"Could not load funding rate history for {symbol}: {e}")
                self.funding_rate_history[symbol] = pd.DataFrame()
        
        self.last_rebalance_time = datetime.now()
        logger.info("FundingArbitrageStrategy initialized")
    
    def on_data(self, data):
        """
        Process new market data.
        
        Args:
            data: Latest market data
        """
        # Update current funding rates
        if "funding_rates" in data:
            funding_rates = data["funding_rates"]
            for symbol, rate in funding_rates.items():
                if symbol in self.symbols:
                    self.current_funding_rates[symbol] = rate
                    
                    # Update history
                    if symbol in self.funding_rate_history:
                        self.funding_rate_history[symbol] = self.funding_rate_history[symbol].append(
                            pd.DataFrame([{
                                "timestamp": datetime.now(),
                                "rate": rate
                            }])
                        )
        
        # Check if rebalance is needed
        now = datetime.now()
        if (self.last_rebalance_time is None or
            (now - self.last_rebalance_time).total_seconds() / 60 >= self.rebalance_frequency):
            self._rebalance()
            self.last_rebalance_time = now
    
    def _rebalance(self):
        """Rebalance the portfolio based on current funding rates."""
        logger.info("Rebalancing funding arbitrage portfolio")
        
        # Get current positions
        positions = self.execution_handler.get_positions()
        
        # Check existing arbitrages for unwinding
        for arb_id, arbitrage in list(self.active_arbitrages.items()):
            long_symbol = arbitrage["long_symbol"]
            short_symbol = arbitrage["short_symbol"]
            
            # Calculate current differential
            if long_symbol in self.current_funding_rates and short_symbol in self.current_funding_rates:
                long_rate = self.current_funding_rates[long_symbol]
                short_rate = self.current_funding_rates[short_symbol]
                current_diff = long_rate - short_rate
                
                # Check if differential has narrowed enough to unwind
                if abs(current_diff) < self.unwinding_threshold:
                    logger.info(f"Unwinding arbitrage {arb_id}: differential narrowed to {current_diff}")
                    self._unwind_arbitrage(arb_id, arbitrage)
                else:
                    logger.info(f"Maintaining arbitrage {arb_id}: current differential {current_diff}")
        
        # Look for new arbitrage opportunities if we have capacity
        if len(self.active_arbitrages) < self.max_positions:
            opportunities = self._find_opportunities()
            
            for opp in opportunities:
                if len(self.active_arbitrages) >= self.max_positions:
                    break
                
                # Create new arbitrage position
                arb_id = f"arb_{len(self.active_arbitrages) + 1}"
                success = self._establish_arbitrage(arb_id, opp)
                
                if success:
                    logger.info(f"Established new arbitrage {arb_id}: {opp['long_symbol']} vs {opp['short_symbol']}")
                    self.active_arbitrages[arb_id] = opp
                else:
                    logger.warning(f"Failed to establish arbitrage {arb_id}")
    
    def _find_opportunities(self) -> List[Dict]:
        """
        Find funding arbitrage opportunities.
        
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        # Compare all pairs of symbols
        for i, symbol1 in enumerate(self.symbols):
            if symbol1 not in self.current_funding_rates:
                continue
                
            rate1 = self.current_funding_rates[symbol1]
            
            for symbol2 in self.symbols[i+1:]:
                if symbol2 not in self.current_funding_rates:
                    continue
                    
                rate2 = self.current_funding_rates[symbol2]
                diff = rate1 - rate2
                
                # Check if differential exceeds threshold
                if abs(diff) > self.funding_threshold:
                    # Determine which is long and which is short
                    if diff > 0:
                        long_symbol, short_symbol = symbol1, symbol2
                        diff_rate = diff
                    else:
                        long_symbol, short_symbol = symbol2, symbol1
                        diff_rate = abs(diff)
                    
                    # Check estimated half-life if available
                    half_life = self._estimate_pair_half_life(long_symbol, short_symbol)
                    
                    if half_life is None or half_life >= self.min_half_life:
                        opportunity = {
                            "long_symbol": long_symbol,
                            "short_symbol": short_symbol,
                            "diff_rate": diff_rate,
                            "estimated_half_life": half_life,
                            "entry_time": datetime.now()
                        }
                        
                        opportunities.append(opportunity)
                        logger.info(f"Found opportunity: {long_symbol} vs {short_symbol}, diff: {diff_rate:.6f}")
        
        # Sort by descending differential
        opportunities.sort(key=lambda x: x["diff_rate"], reverse=True)
        return opportunities
    
    def _establish_arbitrage(self, arb_id: str, opportunity: Dict) -> bool:
        """
        Establish a new arbitrage position.
        
        Args:
            arb_id: Identifier for the arbitrage
            opportunity: Arbitrage opportunity details
            
        Returns:
            True if successful, False otherwise
        """
        long_symbol = opportunity["long_symbol"]
        short_symbol = opportunity["short_symbol"]
        
        # Calculate position sizes
        total_capital = self.execution_handler.get_account_balance()
        position_value = total_capital * self.position_size
        
        try:
            # Get current prices
            long_price = self.data_provider.get_last_price(long_symbol)
            short_price = self.data_provider.get_last_price(short_symbol)
            
            # Calculate quantities
            long_qty = position_value / long_price
            short_qty = position_value / short_price
            
            # Execute trades
            long_order = self.execution_handler.place_market_order(
                symbol=long_symbol,
                side="buy",
                quantity=long_qty,
                tags={"strategy": self.name, "arbitrage_id": arb_id}
            )
            
            short_order = self.execution_handler.place_market_order(
                symbol=short_symbol,
                side="sell",
                quantity=short_qty,
                tags={"strategy": self.name, "arbitrage_id": arb_id}
            )
            
            # Store order IDs in opportunity
            opportunity["long_order_id"] = long_order.id if long_order else None
            opportunity["short_order_id"] = short_order.id if short_order else None
            
            # Update opportunity with quantities and prices
            opportunity["long_qty"] = long_qty
            opportunity["short_qty"] = short_qty
            opportunity["long_price"] = long_price
            opportunity["short_price"] = short_price
            
            return long_order is not None and short_order is not None
            
        except Exception as e:
            logger.error(f"Error establishing arbitrage: {e}")
            return False
    
    def _unwind_arbitrage(self, arb_id: str, arbitrage: Dict) -> bool:
        """
        Unwind an existing arbitrage position.
        
        Args:
            arb_id: Identifier for the arbitrage
            arbitrage: Arbitrage details
            
        Returns:
            True if successful, False otherwise
        """
        long_symbol = arbitrage["long_symbol"]
        short_symbol = arbitrage["short_symbol"]
        long_qty = arbitrage["long_qty"]
        short_qty = arbitrage["short_qty"]
        
        try:
            # Close positions
            close_long = self.execution_handler.place_market_order(
                symbol=long_symbol,
                side="sell",
                quantity=long_qty,
                tags={"strategy": self.name, "arbitrage_id": arb_id, "action": "unwind"}
            )
            
            close_short = self.execution_handler.place_market_order(
                symbol=short_symbol,
                side="buy",
                quantity=short_qty,
                tags={"strategy": self.name, "arbitrage_id": arb_id, "action": "unwind"}
            )
            
            # Remove from active arbitrages
            if arb_id in self.active_arbitrages:
                del self.active_arbitrages[arb_id]
            
            return close_long is not None and close_short is not None
            
        except Exception as e:
            logger.error(f"Error unwinding arbitrage: {e}")
            return False
    
    def _estimate_half_life(self, history: pd.DataFrame) -> Optional[float]:
        """
        Estimate the half-life of mean reversion for a time series.
        
        Args:
            history: DataFrame with funding rate history
            
        Returns:
            Estimated half-life in hours, or None if estimation fails
        """
        if len(history) < 10:
            return None
            
        try:
            # Use lagged regression method to estimate mean reversion
            rates = history["rate"].values
            rates_lag = rates[:-1]
            rates_diff = np.diff(rates)
            
            # Calculate beta (slope) of diff ~ lag relationship
            X = rates_lag.reshape(-1, 1)
            Y = rates_diff.reshape(-1, 1)
            beta = np.linalg.lstsq(X, Y, rcond=None)[0][0][0]
            
            # Convert to half-life
            half_life = -np.log(2) / beta if beta < 0 else None
            
            # Convert to hours (assuming 8-hour funding intervals)
            if half_life is not None:
                half_life_hours = half_life * 8
                logger.info(f"Estimated half-life: {half_life_hours:.2f} hours")
                return half_life_hours
            
            return None
            
        except Exception as e:
            logger.warning(f"Error estimating half-life: {e}")
            return None
    
    def _estimate_pair_half_life(self, symbol1: str, symbol2: str) -> Optional[float]:
        """
        Estimate the half-life of the funding rate differential between two symbols.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            
        Returns:
            Estimated half-life in hours, or None if estimation fails
        """
        if (symbol1 not in self.funding_rate_history or 
            symbol2 not in self.funding_rate_history):
            return None
            
        history1 = self.funding_rate_history[symbol1]
        history2 = self.funding_rate_history[symbol2]
        
        if len(history1) < 10 or len(history2) < 10:
            return None
            
        try:
            # Merge histories by timestamp
            merged = pd.merge(
                history1, history2, 
                on="timestamp", 
                suffixes=("_1", "_2")
            )
            
            if len(merged) < 10:
                return None
                
            # Calculate differentials
            merged["diff"] = merged["rate_1"] - merged["rate_2"]
            
            # Create Series for estimating half-life
            diff_series = pd.Series(merged["diff"].values)
            
            # Use lagged regression method
            lag_1 = diff_series.shift(1).iloc[1:].values
            diff = diff_series.diff().iloc[1:].values
            
            # Calculate beta (slope) of diff ~ lag relationship
            X = lag_1.reshape(-1, 1)
            Y = diff.reshape(-1, 1)
            beta = np.linalg.lstsq(X, Y, rcond=None)[0][0]
            
            # Convert to half-life
            half_life = -np.log(2) / beta if beta < 0 else None
            
            # Convert to hours (assuming 8-hour funding intervals)
            if half_life is not None:
                half_life_hours = half_life * 8
                logger.info(f"Estimated pair half-life ({symbol1}/{symbol2}): {half_life_hours:.2f} hours")
                return half_life_hours
            
            return None
            
        except Exception as e:
            logger.warning(f"Error estimating pair half-life: {e}")
            return None
    
    def on_trade(self, trade):
        """
        Process trade notifications.
        
        Args:
            trade: Trade information
        """
        # Update position tracking
        pass
    
    def on_orderbook(self, orderbook):
        """
        Process orderbook updates.
        
        Args:
            orderbook: Orderbook information
        """
        # Not used for this strategy
        pass
    
    def on_error(self, error):
        """
        Handle errors.
        
        Args:
            error: Error information
        """
        logger.error(f"Strategy error: {error}")
    
    def teardown(self):
        """Clean up resources and close positions."""
        logger.info("Tearing down FundingArbitrageStrategy")
        
        # Close all active arbitrages
        for arb_id, arbitrage in list(self.active_arbitrages.items()):
            self._unwind_arbitrage(arb_id, arbitrage)
        
        logger.info("Finished teardown of FundingArbitrageStrategy") 