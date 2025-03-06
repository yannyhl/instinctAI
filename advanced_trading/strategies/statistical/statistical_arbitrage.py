"""
Statistical Arbitrage Strategy

This strategy exploits mean-reverting relationships between correlated assets.
It identifies pairs of assets with a stable historical relationship and trades
when the relationship deviates from its historical norm, expecting it to revert.

The strategy works by:
1. Analyzing pairs of assets for cointegration and correlation
2. Calculating the spread between normalized prices
3. Trading when the spread exceeds statistical thresholds
4. Unwinding positions when the spread reverts to the mean

Tags: [statistical, pairs_trading, mean_reversion, cointegration]
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint, adfuller
from scipy import stats

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class StatisticalArbitrageStrategy(BaseStrategy):
    """
    Statistical Arbitrage Strategy for exploiting mean-reverting pairs.
    
    This strategy identifies and trades pairs of assets that exhibit a statistically
    significant mean-reverting relationship. It uses cointegration testing to
    find suitable pairs and z-score thresholds to determine entry and exit points.
    
    Args:
        symbols: List of symbols to consider for pair formation
        lookback_period: Period for historical analysis in days
        entry_threshold: Z-score threshold for trade entry
        exit_threshold: Z-score threshold for trade exit
        stop_loss_threshold: Z-score threshold for stop loss
        max_positions: Maximum number of concurrent pair positions
        position_size: Size of position as percentage of available capital
        rebalance_frequency: How often to rebalance positions (in minutes)
        min_half_life: Minimum half-life for mean reversion (in days)
        max_half_life: Maximum half-life for mean reversion (in days)
    """
    
    # Required data for this strategy
    REQUIRED_DATA = ["ohlcv", "orderbook"]
    
    # Default parameters
    DEFAULT_PARAMS = {
        "lookback_period": 60,
        "entry_threshold": 2.0,
        "exit_threshold": 0.5,
        "stop_loss_threshold": 4.0,
        "max_positions": 5,
        "position_size": 0.1,
        "rebalance_frequency": 60,  # minutes
        "min_half_life": 1.0,
        "max_half_life": 30.0
    }
    
    def __init__(
        self,
        symbols: List[str],
        lookback_period: int = DEFAULT_PARAMS["lookback_period"],
        entry_threshold: float = DEFAULT_PARAMS["entry_threshold"],
        exit_threshold: float = DEFAULT_PARAMS["exit_threshold"],
        stop_loss_threshold: float = DEFAULT_PARAMS["stop_loss_threshold"],
        max_positions: int = DEFAULT_PARAMS["max_positions"],
        position_size: float = DEFAULT_PARAMS["position_size"],
        rebalance_frequency: int = DEFAULT_PARAMS["rebalance_frequency"],
        min_half_life: float = DEFAULT_PARAMS["min_half_life"],
        max_half_life: float = DEFAULT_PARAMS["max_half_life"],
        **kwargs
    ):
        """Initialize the strategy with parameters."""
        super().__init__(symbols=symbols, **kwargs)
        
        # Strategy parameters
        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.stop_loss_threshold = stop_loss_threshold
        self.max_positions = max_positions
        self.position_size = position_size
        self.rebalance_frequency = rebalance_frequency
        self.min_half_life = min_half_life
        self.max_half_life = max_half_life
        
        # Internal state
        self.pairs = []  # List of identified pairs
        self.pair_stats = {}  # Statistics for each pair
        self.active_positions = {}  # Currently open positions
        self.historical_spreads = {}  # Historical z-scores for each pair
        
        # Performance tracking
        self.trades = []
        self.last_rebalance_time = datetime.now()
        
        logger.info(f"Initialized StatisticalArbitrageStrategy with {len(symbols)} symbols")
    
    def find_cointegrated_pairs(self, data_dict: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        Find pairs of assets that exhibit cointegration.
        
        Args:
            data_dict: Dictionary of DataFrames with price data for each symbol
        
        Returns:
            List of dictionaries with pair information
        """
        # Need at least two symbols to form pairs
        if len(self.symbols) < 2:
            logger.warning("Need at least two symbols to find pairs")
            return []
        
        # Extract closing prices
        prices = {}
        for symbol in self.symbols:
            if symbol in data_dict and len(data_dict[symbol]) >= self.lookback_period:
                prices[symbol] = data_dict[symbol]['close'].iloc[-self.lookback_period:].values
        
        # Need at least two valid price series
        if len(prices) < 2:
            logger.warning("Not enough price data to find pairs")
            return []
        
        # Test all combinations of symbols for cointegration
        pairs = []
        symbols = list(prices.keys())
        
        for i in range(len(symbols)):
            for j in range(i+1, len(symbols)):
                symbol1 = symbols[i]
                symbol2 = symbols[j]
                
                # Check if we have enough data for both symbols
                if len(prices[symbol1]) < self.lookback_period or len(prices[symbol2]) < self.lookback_period:
                    continue
                
                # Perform cointegration test
                score, pvalue, _ = coint(prices[symbol1], prices[symbol2])
                
                # Check if pair is cointegrated (p-value < 0.05)
                if pvalue < 0.05:
                    # Calculate correlation
                    correlation = np.corrcoef(prices[symbol1], prices[symbol2])[0, 1]
                    
                    # Calculate spread
                    spread = self._calculate_spread(prices[symbol1], prices[symbol2])
                    
                    # Calculate half-life of mean reversion
                    half_life = self._calculate_half_life(spread)
                    
                    # Check half-life constraints
                    if half_life is not None and self.min_half_life <= half_life <= self.max_half_life:
                        # Create pair information
                        pair_info = {
                            'symbol1': symbol1,
                            'symbol2': symbol2,
                            'pvalue': pvalue,
                            'correlation': correlation,
                            'half_life': half_life,
                            'beta': None,  # Will be calculated later
                            'mean': np.mean(spread),
                            'std': np.std(spread)
                        }
                        
                        pairs.append(pair_info)
                        
                        logger.info(f"Found cointegrated pair: {symbol1}-{symbol2}, "
                                  f"p-value: {pvalue:.4f}, half-life: {half_life:.2f} days")
        
        # Sort pairs by half-life (prefer faster mean reversion)
        pairs.sort(key=lambda p: p['half_life'])
        
        return pairs
    
    def _calculate_spread(self, prices1: np.ndarray, prices2: np.ndarray) -> np.ndarray:
        """
        Calculate the spread between two price series.
        
        Args:
            prices1: First price series
            prices2: Second price series
            
        Returns:
            Spread between the two series
        """
        # Calculate hedge ratio (beta) using OLS regression
        X = sm.add_constant(prices1)
        model = sm.OLS(prices2, X).fit()
        beta = model.params[1]
        
        # Calculate spread
        spread = prices2 - beta * prices1
        
        return spread
    
    def _calculate_half_life(self, spread: np.ndarray) -> Optional[float]:
        """
        Calculate the half-life of mean reversion for a spread series.
        
        Args:
            spread: Spread series
            
        Returns:
            Half-life in days or None if not mean-reverting
        """
        # Lag spread by 1 period
        lag_spread = np.roll(spread, 1)
        lag_spread[0] = lag_spread[1]
        
        # Calculate delta (change in spread)
        delta_spread = spread - lag_spread
        
        # Remove first element
        lag_spread = lag_spread[1:]
        delta_spread = delta_spread[1:]
        
        # Regression of change on level to get mean-reversion rate
        X = sm.add_constant(lag_spread)
        model = sm.OLS(delta_spread, X).fit()
        
        # Extract coefficient
        coef = model.params[1]
        
        # Check if mean-reverting (coefficient < 0)
        if coef >= 0:
            return None
            
        # Calculate half-life
        half_life = -np.log(2) / coef
        
        return half_life
    
    def generate_signal(self, data: pd.DataFrame, symbol: str) -> Tuple[int, Dict]:
        """
        Generate trading signals based on pair relationships.
        This method works differently for pairs trading since we need multiple symbols.
        
        Args:
            data: DataFrame with market data for a single symbol
            symbol: Trading symbol
            
        Returns:
            Tuple with signal direction (-1, 0, 1) and signal details
        """
        # Pairs trading requires a different approach, so we always return 0 here
        # The actual signals are generated in the execute_trades method
        return 0, {'reason': 'Pairs signals generated in execute_trades'}
    
    def calculate_pair_signals(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        Calculate trading signals for all identified pairs.
        
        Args:
            data_dict: Dictionary of DataFrames with price data for each symbol
            
        Returns:
            Dictionary of pair signals
        """
        signals = {}
        
        # Check if we need to find/update pairs
        current_time = datetime.now()
        minutes_since_rebalance = (current_time - self.last_rebalance_time).total_seconds() / 60
        
        if not self.pairs or minutes_since_rebalance >= self.rebalance_frequency:
            # Find cointegrated pairs
            self.pairs = self.find_cointegrated_pairs(data_dict)
            self.last_rebalance_time = current_time
        
        # Calculate signals for each pair
        for pair_info in self.pairs:
            symbol1 = pair_info['symbol1']
            symbol2 = pair_info['symbol2']
            
            # Skip if we don't have data for both symbols
            if symbol1 not in data_dict or symbol2 not in data_dict:
                continue
                
            # Get price data
            data1 = data_dict[symbol1]
            data2 = data_dict[symbol2]
            
            # Skip if not enough data
            if len(data1) < 30 or len(data2) < 30:
                continue
                
            # Get latest prices
            prices1 = data1['close'].values
            prices2 = data2['close'].values
            
            # Calculate current spread
            spread = self._calculate_spread(prices1, prices2)
            
            # Calculate z-score
            mean = pair_info['mean']
            std = pair_info['std']
            z_score = (spread[-1] - mean) / std if std > 0 else 0
            
            # Update pair statistics
            pair_id = f"{symbol1}_{symbol2}"
            
            if pair_id not in self.pair_stats:
                self.pair_stats[pair_id] = {
                    'symbol1': symbol1,
                    'symbol2': symbol2,
                    'prices1': [],
                    'prices2': [],
                    'spreads': [],
                    'z_scores': []
                }
                
            # Store latest values
            stats = self.pair_stats[pair_id]
            stats['prices1'].append((current_time, prices1[-1]))
            stats['prices2'].append((current_time, prices2[-1]))
            stats['spreads'].append((current_time, spread[-1]))
            stats['z_scores'].append((current_time, z_score))
            
            # Limit history length
            max_history = 1000
            if len(stats['z_scores']) > max_history:
                stats['prices1'] = stats['prices1'][-max_history:]
                stats['prices2'] = stats['prices2'][-max_history:]
                stats['spreads'] = stats['spreads'][-max_history:]
                stats['z_scores'] = stats['z_scores'][-max_history:]
            
            # Determine signal
            signal = 0
            reason = 'no_signal'
            
            # Check if we have an active position for this pair
            if pair_id in self.active_positions:
                position = self.active_positions[pair_id]
                position_type = position['type']
                entry_z_score = position['entry_z_score']
                
                # Check exit conditions
                if position_type == 'long_spread' and z_score <= self.exit_threshold:
                    # Exit long spread position
                    signal = -1
                    reason = 'exit_long_spread'
                elif position_type == 'short_spread' and z_score >= -self.exit_threshold:
                    # Exit short spread position
                    signal = -1
                    reason = 'exit_short_spread'
                elif position_type == 'long_spread' and z_score >= self.stop_loss_threshold:
                    # Stop loss for long spread
                    signal = -1
                    reason = 'stop_loss_long_spread'
                elif position_type == 'short_spread' and z_score <= -self.stop_loss_threshold:
                    # Stop loss for short spread
                    signal = -1
                    reason = 'stop_loss_short_spread'
            else:
                # Check entry conditions
                if z_score <= -self.entry_threshold:
                    # Enter long spread position
                    signal = 1
                    reason = 'enter_long_spread'
                elif z_score >= self.entry_threshold:
                    # Enter short spread position
                    signal = 1
                    reason = 'enter_short_spread'
            
            # Store signal
            signals[pair_id] = {
                'symbol1': symbol1,
                'symbol2': symbol2,
                'z_score': z_score,
                'signal': signal,
                'reason': reason,
                'type': 'long_spread' if z_score <= -self.entry_threshold else 'short_spread' if z_score >= self.entry_threshold else None,
                'prices': {
                    'symbol1': prices1[-1],
                    'symbol2': prices2[-1]
                },
                'timestamp': current_time
            }
        
        return signals
    
    def execute_trades(self, data_dict: Dict[str, pd.DataFrame], 
                      capital: float) -> List[Dict]:
        """
        Execute trades based on pair signals.
        
        Args:
            data_dict: Dictionary of DataFrames with market data for each symbol
            capital: Available capital
            
        Returns:
            List of executed trade dictionaries
        """
        executed_trades = []
        
        # Calculate signals for all pairs
        pair_signals = self.calculate_pair_signals(data_dict)
        
        # Process signals
        for pair_id, signal_info in pair_signals.items():
            signal = signal_info['signal']
            symbol1 = signal_info['symbol1']
            symbol2 = signal_info['symbol2']
            
            if signal == 1:  # Enter position
                # Check if we have capacity for new positions
                if len(self.active_positions) >= self.max_positions:
                    continue
                    
                # Enter new position
                position_type = signal_info['type']
                
                if position_type is None:
                    continue
                    
                # Calculate position size
                pair_capital = capital * self.position_size
                price1 = signal_info['prices']['symbol1']
                price2 = signal_info['prices']['symbol2']
                
                # Set up quantities based on position type
                if position_type == 'long_spread':
                    # Buy symbol1, sell symbol2
                    qty1 = (pair_capital * 0.5) / price1  # Long position
                    qty2 = (pair_capital * 0.5) / price2  # Short position
                    
                    # Create buy order for symbol1
                    buy_trade = {
                        'symbol': symbol1,
                        'timestamp': signal_info['timestamp'],
                        'action': 'entry',
                        'direction': 'buy',
                        'price': price1,
                        'quantity': qty1,
                        'value': price1 * qty1,
                        'reason': 'pair_trade_long_spread'
                    }
                    
                    # Create sell order for symbol2
                    sell_trade = {
                        'symbol': symbol2,
                        'timestamp': signal_info['timestamp'],
                        'action': 'entry',
                        'direction': 'sell',
                        'price': price2,
                        'quantity': qty2,
                        'value': price2 * qty2,
                        'reason': 'pair_trade_long_spread'
                    }
                    
                    # Add trades to executed trades
                    executed_trades.append(buy_trade)
                    executed_trades.append(sell_trade)
                    
                elif position_type == 'short_spread':
                    # Sell symbol1, buy symbol2
                    qty1 = (pair_capital * 0.5) / price1  # Short position
                    qty2 = (pair_capital * 0.5) / price2  # Long position
                    
                    # Create sell order for symbol1
                    sell_trade = {
                        'symbol': symbol1,
                        'timestamp': signal_info['timestamp'],
                        'action': 'entry',
                        'direction': 'sell',
                        'price': price1,
                        'quantity': qty1,
                        'value': price1 * qty1,
                        'reason': 'pair_trade_short_spread'
                    }
                    
                    # Create buy order for symbol2
                    buy_trade = {
                        'symbol': symbol2,
                        'timestamp': signal_info['timestamp'],
                        'action': 'entry',
                        'direction': 'buy',
                        'price': price2,
                        'quantity': qty2,
                        'value': price2 * qty2,
                        'reason': 'pair_trade_short_spread'
                    }
                    
                    # Add trades to executed trades
                    executed_trades.append(sell_trade)
                    executed_trades.append(buy_trade)
                
                # Record position
                self.active_positions[pair_id] = {
                    'symbol1': symbol1,
                    'symbol2': symbol2,
                    'type': position_type,
                    'entry_time': signal_info['timestamp'],
                    'entry_z_score': signal_info['z_score'],
                    'entry_prices': {
                        'symbol1': price1,
                        'symbol2': price2
                    },
                    'quantities': {
                        'symbol1': qty1,
                        'symbol2': qty2
                    }
                }
                
                logger.info(f"Entered {position_type} position for pair {symbol1}-{symbol2} "
                          f"with z-score {signal_info['z_score']:.2f}")
                
            elif signal == -1:  # Exit position
                # Check if we have an active position for this pair
                if pair_id not in self.active_positions:
                    continue
                    
                # Exit position
                position = self.active_positions[pair_id]
                position_type = position['type']
                
                price1 = signal_info['prices']['symbol1']
                price2 = signal_info['prices']['symbol2']
                qty1 = position['quantities']['symbol1']
                qty2 = position['quantities']['symbol2']
                
                # Set up exit trades based on position type
                if position_type == 'long_spread':
                    # Sell symbol1, buy symbol2
                    sell_trade = {
                        'symbol': symbol1,
                        'timestamp': signal_info['timestamp'],
                        'action': 'exit',
                        'direction': 'sell',
                        'price': price1,
                        'quantity': qty1,
                        'value': price1 * qty1,
                        'reason': signal_info['reason']
                    }
                    
                    buy_trade = {
                        'symbol': symbol2,
                        'timestamp': signal_info['timestamp'],
                        'action': 'exit',
                        'direction': 'buy',
                        'price': price2,
                        'quantity': qty2,
                        'value': price2 * qty2,
                        'reason': signal_info['reason']
                    }
                    
                    # Add trades to executed trades
                    executed_trades.append(sell_trade)
                    executed_trades.append(buy_trade)
                    
                elif position_type == 'short_spread':
                    # Buy symbol1, sell symbol2
                    buy_trade = {
                        'symbol': symbol1,
                        'timestamp': signal_info['timestamp'],
                        'action': 'exit',
                        'direction': 'buy',
                        'price': price1,
                        'quantity': qty1,
                        'value': price1 * qty1,
                        'reason': signal_info['reason']
                    }
                    
                    sell_trade = {
                        'symbol': symbol2,
                        'timestamp': signal_info['timestamp'],
                        'action': 'exit',
                        'direction': 'sell',
                        'price': price2,
                        'quantity': qty2,
                        'value': price2 * qty2,
                        'reason': signal_info['reason']
                    }
                    
                    # Add trades to executed trades
                    executed_trades.append(buy_trade)
                    executed_trades.append(sell_trade)
                
                # Calculate P&L
                entry_price1 = position['entry_prices']['symbol1']
                entry_price2 = position['entry_prices']['symbol2']
                
                if position_type == 'long_spread':
                    # Long symbol1, short symbol2
                    symbol1_pnl = (price1 - entry_price1) / entry_price1
                    symbol2_pnl = (entry_price2 - price2) / entry_price2
                else:
                    # Short symbol1, long symbol2
                    symbol1_pnl = (entry_price1 - price1) / entry_price1
                    symbol2_pnl = (price2 - entry_price2) / entry_price2
                
                # Combined P&L
                combined_pnl = (symbol1_pnl + symbol2_pnl) / 2
                
                # Record trade
                self.trades.append({
                    'pair_id': pair_id,
                    'symbol1': symbol1,
                    'symbol2': symbol2,
                    'type': position_type,
                    'entry_time': position['entry_time'],
                    'exit_time': signal_info['timestamp'],
                    'entry_z_score': position['entry_z_score'],
                    'exit_z_score': signal_info['z_score'],
                    'pnl': combined_pnl,
                    'reason': signal_info['reason']
                })
                
                # Remove from active positions
                del self.active_positions[pair_id]
                
                logger.info(f"Exited {position_type} position for pair {symbol1}-{symbol2} "
                          f"with z-score {signal_info['z_score']:.2f}, PnL: {combined_pnl:.2%}")
        
        return executed_trades
    
    def analyze_performance(self, trades: List[Dict]) -> Dict:
        """
        Analyze performance of executed trades.
        
        Args:
            trades: List of executed trade dictionaries
            
        Returns:
            Dictionary with performance metrics
        """
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'average_profit_pct': 0,
                'max_drawdown_pct': 0
            }
        
        # For pair trading, we need to group trades by reason and timestamp
        # to match the pairs of trades that belong together
        
        # Group trades by reason and timestamp
        trade_groups = {}
        
        for trade in trades:
            key = f"{trade['reason']}_{trade['timestamp']}"
            
            if key not in trade_groups:
                trade_groups[key] = []
                
            trade_groups[key].append(trade)
        
        # Process trade groups
        closed_trades = []
        
        for key, group in trade_groups.items():
            entry_trades = [t for t in group if t['action'] == 'entry']
            exit_trades = [t for t in group if t['action'] == 'exit']
            
            # Skip if we don't have complete pairs
            if not entry_trades or not exit_trades:
                continue
                
            # Calculate combined P&L for the group
            pnl_values = []
            
            for entry in entry_trades:
                matching_exits = [
                    e for e in exit_trades if (
                        e['symbol'] == entry['symbol'] and
                        e['quantity'] == entry['quantity'] and
                        e['timestamp'] > entry['timestamp']
                    )
                ]
                
                if matching_exits:
                    exit_trade = matching_exits[0]
                    
                    # Calculate P&L
                    if entry['direction'] == 'buy':
                        pnl_pct = (exit_trade['price'] - entry['price']) / entry['price'] * 100
                    else:  # sell
                        pnl_pct = (entry['price'] - exit_trade['price']) / entry['price'] * 100
                    
                    pnl_values.append(pnl_pct)
            
            # Average P&L for the group
            if pnl_values:
                avg_pnl = sum(pnl_values) / len(pnl_values)
                
                closed_trades.append({
                    'reason': key.split('_')[0],
                    'timestamp': entry_trades[0]['timestamp'],
                    'exit_timestamp': exit_trades[0]['timestamp'],
                    'pnl_pct': avg_pnl,
                    'trade_count': len(pnl_values)
                })
        
        # Calculate performance metrics
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t['pnl_pct'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl_pct'] <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t['pnl_pct'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl_pct'] for t in losing_trades))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        average_profit_pct = sum(t['pnl_pct'] for t in closed_trades) / total_trades if total_trades > 0 else 0
        
        # Calculate drawdown
        equity_curve = []
        cumulative_pnl = 0
        
        for trade in sorted(closed_trades, key=lambda t: t['exit_timestamp']):
            cumulative_pnl += trade['pnl_pct']
            equity_curve.append(cumulative_pnl)
        
        # Maximum drawdown calculation
        max_drawdown_pct = 0
        peak = 0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            elif peak > 0:
                drawdown = (peak - equity) / peak * 100
                max_drawdown_pct = max(max_drawdown_pct, drawdown)
        
        # Performance by reason
        performance_by_reason = {}
        
        for trade in closed_trades:
            reason = trade['reason']
            
            if reason not in performance_by_reason:
                performance_by_reason[reason] = {
                    'count': 0,
                    'win_count': 0,
                    'total_pnl': 0,
                    'avg_pnl_pct': 0
                }
            
            perf = performance_by_reason[reason]
            perf['count'] += 1
            
            if trade['pnl_pct'] > 0:
                perf['win_count'] += 1
                
            perf['total_pnl'] += trade['pnl_pct']
        
        # Calculate averages
        for reason, perf in performance_by_reason.items():
            if perf['count'] > 0:
                perf['win_rate'] = perf['win_count'] / perf['count']
                perf['avg_pnl_pct'] = perf['total_pnl'] / perf['count']
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'average_profit_pct': average_profit_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'net_profit': gross_profit - gross_loss,
            'performance_by_reason': performance_by_reason,
            'active_pairs': len(self.active_positions),
            'total_pairs_found': len(self.pairs) if self.pairs else 0
        } 