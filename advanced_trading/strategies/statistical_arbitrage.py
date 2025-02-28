# advanced_trading/strategies/statistical_arbitrage.py

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

from ..utils.cointegration import (
    find_cointegrated_pairs, 
    calculate_spread, 
    calculate_zscore,
    is_stationary
)

logger = logging.getLogger(__name__)

class StatisticalArbitrageStrategy:
    """
    Statistical arbitrage strategy using cointegration for pairs trading.
    """
    
    def __init__(self, 
                entry_threshold: float = 2.0,
                exit_threshold: float = 0.5,
                max_holding_period: int = 10,
                max_position_per_pair: float = 0.2,
                recalibration_interval: int = 20,
                lookback_window: int = 60,
                max_active_pairs: int = 5):
        """
        Initialize the statistical arbitrage strategy.
        
        Args:
            entry_threshold: Z-score threshold to enter a position
            exit_threshold: Z-score threshold to exit a position
            max_holding_period: Maximum holding period in days
            max_position_per_pair: Maximum position size as fraction of portfolio
            recalibration_interval: Interval to recalibrate hedge ratios (in days)
            lookback_window: Window for z-score calculation
            max_active_pairs: Maximum number of pairs to trade simultaneously
        """
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_holding_period = max_holding_period
        self.max_position_per_pair = max_position_per_pair
        self.recalibration_interval = recalibration_interval
        self.lookback_window = lookback_window
        self.max_active_pairs = max_active_pairs
        
        # Strategy state
        self.pairs = []
        self.hedge_ratios = {}
        self.last_recalibration = None
        self.active_positions = {}
        self.spreads = {}
        self.zscores = {}
        
        logger.info(f"Initialized Statistical Arbitrage strategy with "
                  f"entry threshold {entry_threshold}, exit threshold {exit_threshold}")
    
    def find_pairs(self, data_dict: Dict[str, pd.DataFrame], 
                 p_value_threshold: float = 0.05) -> List[Tuple]:
        """
        Find cointegrated pairs from price data.
        
        Args:
            data_dict: Dictionary of DataFrames with price data
            p_value_threshold: Maximum p-value to consider cointegrated
            
        Returns:
            List of cointegrated pairs
        """
        logger.info("Finding cointegrated pairs")
        
        # Find pairs
        pairs = find_cointegrated_pairs(data_dict, p_value_threshold=p_value_threshold)
        
        # Update strategy state
        self.pairs = pairs
        
        # Update hedge ratios
        for pair in pairs:
            symbol1, symbol2, hedge_ratio, _ = pair
            self.hedge_ratios[(symbol1, symbol2)] = hedge_ratio
        
        # Update last recalibration time
        self.last_recalibration = datetime.now()
        
        return pairs
    
    def calculate_pair_metrics(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        """
        Calculate spread and z-score for all pairs.
        
        Args:
            data_dict: Dictionary of DataFrames with price data
            
        Returns:
            Dictionary of metrics for each pair
        """
        metrics = {}
        
        for pair in self.pairs:
            symbol1, symbol2, _, _ = pair
            
            if symbol1 not in data_dict or symbol2 not in data_dict:
                continue
            
            # Get price series
            series1 = data_dict[symbol1]['close']
            series2 = data_dict[symbol2]['close']
            
            # advanced_trading/strategies/statistical_arbitrage.py (continued)

            # Get hedge ratio
            hedge_ratio = self.hedge_ratios.get((symbol1, symbol2))
            
            if hedge_ratio is None:
                continue
            
            # Calculate spread
            spread = calculate_spread(series1, series2, hedge_ratio)
            
            # Calculate z-score
            zscore = calculate_zscore(spread, window=self.lookback_window)
            
            # Store results
            self.spreads[(symbol1, symbol2)] = spread
            self.zscores[(symbol1, symbol2)] = zscore
            
            # Create metrics entry
            metrics[(symbol1, symbol2)] = {
                'spread': spread.iloc[-1] if not spread.empty else None,
                'zscore': zscore.iloc[-1] if not zscore.empty else None,
                'hedge_ratio': hedge_ratio,
                'is_stationary': is_stationary(spread),
                'current_position': self.active_positions.get((symbol1, symbol2), 0)
            }
        
        return metrics
    
    def should_recalibrate(self) -> bool:
        """Check if pairs should be recalibrated."""
        if self.last_recalibration is None:
            return True
            
        days_since_recalibration = (datetime.now() - self.last_recalibration).days
        return days_since_recalibration >= self.recalibration_interval
    
    def generate_signals(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        """
        Generate trading signals for all pairs.
        
        Args:
            data_dict: Dictionary of DataFrames with price data
            
        Returns:
            Dictionary of signals for each pair
        """
        # Recalibrate if needed
        if self.should_recalibrate():
            self.find_pairs(data_dict)
        
        # Calculate metrics
        metrics = self.calculate_pair_metrics(data_dict)
        
        # Generate signals
        signals = {}
        
        for pair, pair_metrics in metrics.items():
            symbol1, symbol2 = pair
            zscore = pair_metrics['zscore']
            current_position = pair_metrics['current_position']
            
            # Default to no action
            signal = 0
            
            if zscore is None:
                continue
            
            # Check if we have an active position
            if current_position == 0:
                # No position, check entry conditions
                if zscore > self.entry_threshold:
                    # Spread is high, go short the spread
                    # Short symbol1, long symbol2
                    signal = -1
                elif zscore < -self.entry_threshold:
                    # Spread is low, go long the spread
                    # Long symbol1, short symbol2
                    signal = 1
            else:
                # We have an active position, check exit conditions
                if (current_position > 0 and zscore > -self.exit_threshold) or \
                   (current_position < 0 and zscore < self.exit_threshold):
                    # Exit condition met
                    signal = 0
                else:
                    # Maintain current position
                    signal = current_position
            
            signals[pair] = signal
        
        return signals
    
    def execute_trades(self, signals: Dict, data_dict: Dict[str, pd.DataFrame], 
                      capital: float) -> List[Dict]:
        """
        Execute trades based on signals.
        
        Args:
            signals: Dictionary of signals for each pair
            data_dict: Dictionary of DataFrames with price data
            capital: Available capital
            
        Returns:
            List of executed trades
        """
        executed_trades = []
        active_pairs_count = sum(1 for pos in self.active_positions.values() if pos != 0)
        available_slots = self.max_active_pairs - active_pairs_count
        
        # Sort pairs by signal strength (absolute z-score)
        pairs_with_signals = []
        for pair, signal in signals.items():
            if signal != 0 and pair in self.zscores:
                zscore = self.zscores[pair].iloc[-1] if not self.zscores[pair].empty else 0
                pairs_with_signals.append((pair, signal, abs(zscore)))
        
        # Sort by z-score strength
        pairs_with_signals.sort(key=lambda x: x[2], reverse=True)
        
        # Execute trades
        for pair, signal, _ in pairs_with_signals:
            symbol1, symbol2 = pair
            current_position = self.active_positions.get(pair, 0)
            
            # Skip if no position change
            if signal == current_position:
                continue
            
            # Skip if we're at capacity and this is a new entry
            if current_position == 0 and signal != 0 and available_slots <= 0:
                continue
            
            # Get prices
            price1 = data_dict[symbol1]['close'].iloc[-1]
            price2 = data_dict[symbol2]['close'].iloc[-1]
            
            # Get hedge ratio
            hedge_ratio = self.hedge_ratios[pair]
            
            try:
                # Calculate position sizes
                if signal == 0:
                    # Exit position
                    position_size1 = 0
                    position_size2 = 0
                    
                    # Record trade exit
                    entry_time = self.active_positions.get(f"{pair}_entry_time")
                    holding_period = (datetime.now() - entry_time).days if entry_time else 0
                    
                    trade = {
                        'pair': pair,
                        'action': 'exit',
                        'exit_time': datetime.now(),
                        'holding_period': holding_period,
                        'exit_zscore': self.zscores[pair].iloc[-1] if not self.zscores[pair].empty else None
                    }
                    
                    executed_trades.append(trade)
                    
                    logger.info(f"Exiting position for {symbol1}/{symbol2}, holding period: {holding_period} days")
                    
                else:
                    # Enter or flip position
                    capital_per_pair = capital * self.max_position_per_pair
                    
                    # Calculate notional values maintaining the hedge ratio
                    total_notional = capital_per_pair
                    
                    # Calculate position sizes
                    if signal > 0:
                        # Long spread: Long symbol1, Short symbol2
                        notional1 = total_notional / (1 + hedge_ratio * price2 / price1)
                        position_size1 = notional1 / price1
                        position_size2 = -hedge_ratio * position_size1
                        
                        action = 'entry_long' if current_position == 0 else 'flip_to_long'
                    else:
                        # Short spread: Short symbol1, Long symbol2
                        notional1 = total_notional / (1 + hedge_ratio * price2 / price1)
                        position_size1 = -notional1 / price1
                        position_size2 = hedge_ratio * abs(position_size1)
                        
                        action = 'entry_short' if current_position == 0 else 'flip_to_short'
                    
                    # Record trade entry
                    trade = {
                        'pair': pair,
                        'action': action,
                        'entry_time': datetime.now(),
                        'entry_zscore': self.zscores[pair].iloc[-1] if not self.zscores[pair].empty else None,
                        'position_size1': position_size1,
                        'position_size2': position_size2,
                        'notional1': position_size1 * price1,
                        'notional2': position_size2 * price2
                    }
                    
                    executed_trades.append(trade)
                    
                    # If this is a new pair, decrement available slots
                    if current_position == 0 and signal != 0:
                        available_slots -= 1
                    
                    logger.info(f"Executing {action} for {symbol1}/{symbol2}, "
                              f"z-score: {trade['entry_zscore']:.2f}, "
                              f"position sizes: {position_size1:.4f}/{position_size2:.4f}")
                
                # Update active positions
                self.active_positions[pair] = signal
                
                if signal != 0:
                    self.active_positions[f"{pair}_entry_time"] = datetime.now()
                else:
                    # Remove entry time when exiting
                    if f"{pair}_entry_time" in self.active_positions:
                        del self.active_positions[f"{pair}_entry_time"]
                
            except Exception as e:
                logger.error(f"Error executing trade for {symbol1}/{symbol2}: {e}")
        
        return executed_trades
    
    def check_timeout_positions(self) -> List[Dict]:
        """
        Check for positions that have exceeded the maximum holding period.
        
        Returns:
            List of timed-out positions
        """
        timed_out = []
        
        for pair, position in list(self.active_positions.items()):
            # Skip metadata entries
            if isinstance(pair, str) and "_entry_time" in pair:
                continue
                
            if position == 0:
                continue
                
            entry_time = self.active_positions.get(f"{pair}_entry_time")
            
            if entry_time is None:
                continue
                
            holding_period = (datetime.now() - entry_time).days
            
            if holding_period >= self.max_holding_period:
                symbol1, symbol2 = pair
                
                logger.info(f"Position timeout for {symbol1}/{symbol2}, "
                          f"holding period: {holding_period} days")
                
                # Record timeout
                timeout = {
                    'pair': pair,
                    'action': 'timeout',
                    'exit_time': datetime.now(),
                    'holding_period': holding_period,
                    'exit_zscore': self.zscores[pair].iloc[-1] if pair in self.zscores and not self.zscores[pair].empty else None
                }
                
                timed_out.append(timeout)
                
                # Reset position
                self.active_positions[pair] = 0
                
                # Remove entry time
                if f"{pair}_entry_time" in self.active_positions:
                    del self.active_positions[f"{pair}_entry_time"]
        
        return timed_out
    
    def visualize_pair(self, pair: Tuple[str, str], data_dict: Dict[str, pd.DataFrame], 
                     save_path: Optional[str] = None) -> plt.Figure:
        """
        Visualize a trading pair with spread, z-score, and signals.
        
        Args:
            pair: Tuple of (symbol1, symbol2)
            data_dict: Dictionary of DataFrames with price data
            save_path: Path to save the plot
            
        Returns:
            Matplotlib figure
        """
        symbol1, symbol2 = pair
        
        if pair not in self.spreads or pair not in self.zscores:
            logger.warning(f"No data available for pair {symbol1}/{symbol2}")
            return None
        
        spread = self.spreads[pair]
        zscore = self.zscores[pair]
        
        # Create figure
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        
        # Plot prices
        ax1.plot(data_dict[symbol1]['close'], label=symbol1)
        ax1.plot(data_dict[symbol2]['close'], label=symbol2)
        ax1.set_title(f"Price Series: {symbol1} and {symbol2}")
        ax1.legend()
        ax1.grid(True)
        
        # Plot spread
        ax2.plot(spread, label='Spread')
        ax2.set_title(f"Spread (Hedge Ratio: {self.hedge_ratios[pair]:.4f})")
        ax2.legend()
        ax2.grid(True)
        
        # Plot z-score
        ax3.plot(zscore, label='Z-Score')
        ax3.axhline(y=self.entry_threshold, color='r', linestyle='--', label=f'Entry (+{self.entry_threshold})')
        ax3.axhline(y=-self.entry_threshold, color='r', linestyle='--', label=f'Entry (-{self.entry_threshold})')
        ax3.axhline(y=self.exit_threshold, color='g', linestyle='--', label=f'Exit (+{self.exit_threshold})')
        ax3.axhline(y=-self.exit_threshold, color='g', linestyle='--', label=f'Exit (-{self.exit_threshold})')
        ax3.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        ax3.set_title("Z-Score with Entry/Exit Thresholds")
        ax3.legend()
        ax3.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved pair visualization to {save_path}")
        
        return fig