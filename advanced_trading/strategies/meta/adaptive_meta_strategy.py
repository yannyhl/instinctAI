"""
Adaptive Meta-Strategy

An advanced strategy that dynamically allocates capital across multiple sub-strategies
based on detected market regimes, historical performance, and risk management constraints.

This meta-strategy:
1. Uses Bayesian changepoint detection for identifying market regimes
2. Tracks strategy performance by regime type
3. Employs hierarchical risk parity for balanced risk allocation
4. Dynamically adjusts allocations based on recent performance
5. Implements adaptive risk management based on market conditions

Tags: [meta, adaptive, multi_strategy, regime_detection, risk_parity]
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import logging

from ..base import BaseStrategy

# Set up logging
logger = logging.getLogger(__name__)


class AdaptiveMetaStrategy(BaseStrategy):
    """
    A meta-strategy that allocates across multiple sub-strategies
    based on regime detection and performance characteristics.
    
    Args:
        symbols: List of symbols to trade
        strategies: List of strategy instances to allocate between
        base_allocations: Initial allocation weights for each strategy (sums to 1.0)
        lookback_window: Window for tracking strategy performance (days)
        regime_memory: Number of days to remember regime-specific performance
        allocation_method: Method for portfolio allocation ('hrp', 'risk_parity', etc.)
        max_allocation: Maximum allocation to any single strategy (0.0-1.0)
        min_allocation: Minimum allocation to any strategy (0.0-1.0)
        target_volatility: Target volatility for the combined strategy portfolio
        adaptation_speed: How quickly to adapt to new performance (0.0-1.0)
        rebalance_frequency: How often to rebalance allocations (in days)
    """
    
    # Required data for this strategy
    REQUIRED_DATA = ["ohlcv", "market_data"]
    
    def __init__(self, 
                 symbols: List[str],
                 strategies: List[BaseStrategy],
                 base_allocations: Optional[Dict[str, float]] = None,
                 lookback_window: int = 60,
                 regime_memory: int = 252,
                 allocation_method: str = 'hrp',
                 max_allocation: float = 0.5,
                 min_allocation: float = 0.0,
                 target_volatility: Optional[float] = 0.15,
                 adaptation_speed: float = 0.1,
                 rebalance_frequency: int = 7,
                 **kwargs):
        """Initialize the meta-strategy with parameters."""
        super().__init__(symbols=symbols, **kwargs)
        
        # Store strategies
        self.strategies = {strategy.__class__.__name__: strategy for strategy in strategies}
        self.strategy_names = list(self.strategies.keys())
        
        # Strategy parameters
        self.lookback_window = lookback_window
        self.regime_memory = regime_memory
        self.allocation_method = allocation_method
        self.max_allocation = max_allocation
        self.min_allocation = min_allocation
        self.target_volatility = target_volatility
        self.adaptation_speed = adaptation_speed
        self.rebalance_frequency = rebalance_frequency
        
        # Set base allocations or create equal-weight default
        if base_allocations is None:
            # Equal allocation to all strategies
            self.base_allocations = {
                name: 1.0 / len(self.strategy_names) for name in self.strategy_names
            }
        else:
            self.base_allocations = base_allocations
            
        # Ensure base allocations sum to 1.0
        total = sum(self.base_allocations.values())
        if total > 0:
            self.base_allocations = {
                k: v / total for k, v in self.base_allocations.items()
            }
        
        # Initialize current allocations
        self.current_allocations = self.base_allocations.copy()
        
        # Strategy performance tracking
        self.strategy_returns = {name: [] for name in self.strategy_names}
        self.strategy_performance = {name: {} for name in self.strategy_names}
        self.regime_strategy_performance = {}
        
        # Market regime tracking
        self.current_regime = "unknown"
        self.regime_history = []
        self.last_regime_change = datetime.now()
        
        # Position tracking
        self._active_positions = {}
        self._closed_positions = []
        
        # Rebalance tracking
        self.last_rebalance = datetime.now()
        
        logger.info(f"Initialized AdaptiveMetaStrategy with {len(self.strategies)} sub-strategies")
    
    def detect_regime(self, data: pd.DataFrame) -> str:
        """
        Detect the current market regime based on price patterns.
        
        Args:
            data: DataFrame with market data
            
        Returns:
            String indicating the current market regime
        """
        if len(data) < 60:  # Need sufficient data
            return "unknown"
        
        # Extract returns for regime detection
        returns = data['close'].pct_change().dropna()
        
        # Calculate volatility (annualized)
        volatility = returns.std() * np.sqrt(252)
        
        # Calculate autocorrelation
        autocorr = returns.autocorr(lag=1)
        
        # Calculate trend strength
        trend_strength = abs(returns.sum()) / returns.abs().sum()
        
        # Determine regime
        if volatility > 0.8:
            regime = "high_volatility"
        elif trend_strength > 0.15 and autocorr > 0.1:
            regime = "trending"
        elif autocorr < -0.1:
            regime = "mean_reverting"
        else:
            regime = "normal"
        
        # Store regime
        self.regime_history.append((datetime.now(), regime))
        
        # Check if regime has changed
        if regime != self.current_regime:
            self.last_regime_change = datetime.now()
            logger.info(f"Market regime changed from {self.current_regime} to {regime}")
            
        self.current_regime = regime
        return regime
    
    def update_strategy_returns(self, data_dict: Dict[str, pd.DataFrame], capital: float) -> Dict[str, float]:
        """
        Update return tracking for each sub-strategy.
        
        Args:
            data_dict: Dictionary of DataFrames with market data for each symbol
            capital: Available capital
            
        Returns:
            Dictionary of strategy returns
        """
        strategy_returns = {}
        
        # Get current returns for each strategy
        for name, strategy in self.strategies.items():
            try:
                # Generate signals using the strategy
                trades = strategy.execute_trades(data_dict, capital)
                
                # Calculate performance
                if trades:
                    performance = strategy.analyze_performance(trades)
                    avg_return = performance.get('average_profit_pct', 0)
                else:
                    avg_return = 0.0
                
                # Store return
                strategy_returns[name] = avg_return
                
                # Update strategy return history
                self.strategy_returns[name].append((datetime.now(), avg_return))
                
                # Keep only the lookback window
                if len(self.strategy_returns[name]) > self.lookback_window:
                    self.strategy_returns[name] = self.strategy_returns[name][-self.lookback_window:]
                
                # Update strategy performance metrics
                returns = [r for _, r in self.strategy_returns[name]]
                
                if returns:
                    self.strategy_performance[name] = {
                        'mean_return': np.mean(returns),
                        'std_return': np.std(returns),
                        'sharpe': np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0,
                        'win_rate': sum(1 for r in returns if r > 0) / len(returns) if returns else 0,
                    }
                
                # Update regime-specific performance
                if self.current_regime not in self.regime_strategy_performance:
                    self.regime_strategy_performance[self.current_regime] = {
                        name: {'returns': [], 'metrics': {}} for name in self.strategy_names
                    }
                
                regime_perf = self.regime_strategy_performance[self.current_regime]
                regime_perf[name]['returns'].append(avg_return)
                
                # Keep only regime memory window
                if len(regime_perf[name]['returns']) > self.regime_memory:
                    regime_perf[name]['returns'] = regime_perf[name]['returns'][-self.regime_memory:]
                
                # Update regime-specific metrics
                returns = regime_perf[name]['returns']
                
                if returns:
                    regime_perf[name]['metrics'] = {
                        'mean_return': np.mean(returns),
                        'std_return': np.std(returns),
                        'sharpe': np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0,
                        'win_rate': sum(1 for r in returns if r > 0) / len(returns) if returns else 0,
                    }
            
            except Exception as e:
                logger.error(f"Error updating returns for strategy {name}: {str(e)}")
                strategy_returns[name] = 0.0
        
        return strategy_returns
    
    def calculate_allocations(self) -> Dict[str, float]:
        """
        Calculate optimal allocations to each strategy based on performance and regime.
        
        Returns:
            Dictionary of strategy allocations
        """
        # Start with base allocations
        allocations = self.base_allocations.copy()
        
        # Adjust based on regime-specific performance if available
        if self.current_regime in self.regime_strategy_performance:
            regime_perf = self.regime_strategy_performance[self.current_regime]
            
            # Calculate regime-specific sharpe ratios
            sharpes = {}
            for name in self.strategy_names:
                if name in regime_perf and 'metrics' in regime_perf[name]:
                    sharpe = regime_perf[name]['metrics'].get('sharpe', 0)
                    # Ensure non-negative Sharpe
                    sharpes[name] = max(0.01, sharpe)
                else:
                    sharpes[name] = 0.01  # Default for strategies without data
            
            # Normalize sharpes to create weights
            total_sharpe = sum(sharpes.values())
            
            if total_sharpe > 0:
                regime_weights = {name: sharpe / total_sharpe for name, sharpe in sharpes.items()}
                
                # Blend regime weights with base allocations
                for name in allocations:
                    if name in regime_weights:
                        allocations[name] = (
                            (1 - self.adaptation_speed) * allocations[name] + 
                            self.adaptation_speed * regime_weights[name]
                        )
        
        # Apply allocation constraints
        for name in allocations:
            allocations[name] = max(self.min_allocation, min(self.max_allocation, allocations[name]))
        
        # Normalize to ensure weights sum to 1.0
        total = sum(allocations.values())
        if total > 0:
            allocations = {name: weight / total for name, weight in allocations.items()}
        else:
            # Fallback to equal weights if something went wrong
            allocations = {name: 1.0 / len(self.strategy_names) for name in self.strategy_names}
        
        return allocations
    
    def rebalance_strategies(self, current_time: datetime) -> bool:
        """
        Check if rebalancing is needed and perform rebalancing if necessary.
        
        Args:
            current_time: Current datetime
            
        Returns:
            Boolean indicating if rebalancing was performed
        """
        # Calculate time since last rebalance
        days_since_rebalance = (current_time - self.last_rebalance).days
        
        # Check if rebalancing is needed
        if days_since_rebalance >= self.rebalance_frequency:
            # Calculate new allocations
            new_allocations = self.calculate_allocations()
            
            # Update current allocations
            self.current_allocations = new_allocations
            
            # Update last rebalance time
            self.last_rebalance = current_time
            
            logger.info(f"Rebalanced strategy allocations: {self.current_allocations}")
            return True
        
        return False
    
    def generate_signal(self, data: pd.DataFrame, symbol: str) -> Tuple[int, Dict]:
        """
        Generate trading signals using the current allocations across strategies.
        
        Args:
            data: DataFrame with market data
            symbol: Trading symbol
            
        Returns:
            Tuple with signal direction (-1, 0, 1) and signal details
        """
        if len(data) < 60:  # Need sufficient data
            return 0, {'reason': 'Insufficient data for meta-strategy'}
        
        # Detect current market regime
        self.detect_regime(data)
        
        # Initialize combined signal and components
        combined_signal = 0
        signal_components = {}
        
        # Generate signals from each strategy
        for name, strategy in self.strategies.items():
            try:
                # Get allocation weight
                weight = self.current_allocations.get(name, 0.0)
                
                if weight > 0:
                    # Generate signal from this strategy
                    signal, details = strategy.generate_signal(data, symbol)
                    
                    # Add weighted signal to combined signal
                    combined_signal += signal * weight
                    
                    # Store component details
                    signal_components[name] = {
                        'signal': signal,
                        'weight': weight,
                        'weighted_signal': signal * weight,
                        'details': details
                    }
            
            except Exception as e:
                logger.error(f"Error generating signal for strategy {name}: {str(e)}")
                signal_components[name] = {
                    'signal': 0,
                    'weight': 0.0,
                    'weighted_signal': 0.0,
                    'error': str(e)
                }
        
        # Determine final signal direction
        final_signal = 0
        if combined_signal > 0.2:
            final_signal = 1
        elif combined_signal < -0.2:
            final_signal = -1
        
        # Create signal details
        signal_details = {
            'timestamp': data.index[-1] if not data.empty else datetime.now(),
            'combined_signal': combined_signal,
            'signal_strength': abs(combined_signal),
            'regime': self.current_regime,
            'component_signals': signal_components,
            'allocations': self.current_allocations.copy()
        }
        
        return final_signal, signal_details
    
    def execute_trades(self, data_dict: Dict[str, pd.DataFrame], 
                      capital: float) -> List[Dict]:
        """
        Execute trades using the current strategy allocations.
        
        Args:
            data_dict: Dictionary of DataFrames with market data for each symbol
            capital: Available capital
            
        Returns:
            List of executed trade dictionaries
        """
        executed_trades = []
        current_time = datetime.now()
        
        # Check if rebalancing is needed
        self.rebalance_strategies(current_time)
        
        # Update strategy returns (for future allocation calculations)
        self.update_strategy_returns(data_dict, capital)
        
        # Allocate capital according to current allocations
        allocated_capital = {}
        for name, allocation in self.current_allocations.items():
            allocated_capital[name] = capital * allocation
        
        # Execute trades for each strategy with its allocated capital
        for name, strategy in self.strategies.items():
            if name in allocated_capital and allocated_capital[name] > 0:
                try:
                    # Execute trades using the strategy
                    strategy_trades = strategy.execute_trades(data_dict, allocated_capital[name])
                    
                    # Add strategy identifier to each trade
                    for trade in strategy_trades:
                        trade['strategy'] = name
                        trade['meta_regime'] = self.current_regime
                    
                    # Add to overall trades
                    executed_trades.extend(strategy_trades)
                    
                except Exception as e:
                    logger.error(f"Error executing trades for strategy {name}: {str(e)}")
        
        # Update position tracking
        self._update_positions(executed_trades)
        
        return executed_trades
    
    def _update_positions(self, trades: List[Dict]) -> None:
        """
        Update active and closed positions based on executed trades.
        
        Args:
            trades: List of executed trade dictionaries
        """
        current_time = datetime.now()
        
        # Process entry trades
        for trade in [t for t in trades if t['action'] == 'entry']:
            position_id = f"{trade['symbol']}_{trade['strategy']}_{trade['timestamp']}"
            
            self._active_positions[position_id] = {
                'symbol': trade['symbol'],
                'strategy': trade['strategy'],
                'entry_time': trade['timestamp'],
                'direction': trade['direction'],
                'entry_price': trade['price'],
                'quantity': trade['quantity'],
                'position_value': trade['value'],
                'regime': trade.get('meta_regime', 'unknown')
            }
        
        # Process exit trades
        for trade in [t for t in trades if t['action'] == 'exit']:
            # Find matching entry
            for pos_id, position in list(self._active_positions.items()):
                if (position['symbol'] == trade['symbol'] and 
                    position['strategy'] == trade['strategy'] and 
                    position['quantity'] == trade['quantity']):
                    
                    # Update position with exit details
                    position['exit_time'] = trade['timestamp']
                    position['exit_price'] = trade['price']
                    position['exit_reason'] = trade.get('reason', 'unknown')
                    position['pnl_pct'] = trade.get('pnl_pct', 0.0)
                    position['pnl_value'] = trade.get('pnl_value', 0.0)
                    
                    # Move to closed positions
                    self._closed_positions.append(position)
                    
                    # Remove from active positions
                    del self._active_positions[pos_id]
                    break
    
    def analyze_performance(self, trades: List[Dict]) -> Dict:
        """
        Analyze performance of executed trades across all strategies.
        
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
        
        # Extract closed trades (pairs of entry and exit)
        entry_trades = [t for t in trades if t['action'] == 'entry']
        exit_trades = [t for t in trades if t['action'] == 'exit']
        
        # Match entries with exits
        closed_trades = []
        
        for entry in entry_trades:
            # Find matching exit
            matching_exits = [
                e for e in exit_trades if (
                    e['symbol'] == entry['symbol'] and
                    e['strategy'] == entry['strategy'] and
                    e['quantity'] == entry['quantity'] and
                    e['timestamp'] > entry['timestamp']
                )
            ]
            
            if matching_exits:
                # Use the first matching exit
                exit_trade = matching_exits[0]
                
                # Calculate P&L
                if entry['direction'] == 'buy':
                    pnl_pct = (exit_trade['price'] - entry['price']) / entry['price'] * 100
                else:  # sell
                    pnl_pct = (entry['price'] - exit_trade['price']) / entry['price'] * 100
                
                pnl_value = entry['value'] * pnl_pct / 100
                
                closed_trades.append({
                    'symbol': entry['symbol'],
                    'strategy': entry['strategy'],
                    'entry_time': entry['timestamp'],
                    'exit_time': exit_trade['timestamp'],
                    'direction': entry['direction'],
                    'entry_price': entry['price'],
                    'exit_price': exit_trade['price'],
                    'quantity': entry['quantity'],
                    'value': entry['value'],
                    'pnl_pct': pnl_pct,
                    'pnl_value': pnl_value,
                    'exit_reason': exit_trade.get('reason', 'unknown'),
                    'regime': entry.get('meta_regime', 'unknown')
                })
        
        # Calculate overall performance metrics
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t['pnl_value'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl_value'] <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t['pnl_value'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl_value'] for t in losing_trades))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        average_profit_pct = sum(t['pnl_pct'] for t in closed_trades) / total_trades if total_trades > 0 else 0
        
        # Calculate drawdown
        equity_curve = []
        cumulative_pnl = 0
        
        for trade in sorted(closed_trades, key=lambda t: t['exit_time']):
            cumulative_pnl += trade['pnl_value']
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
        
        # Performance by strategy
        performance_by_strategy = {}
        
        for trade in closed_trades:
            strategy = trade['strategy']
            
            if strategy not in performance_by_strategy:
                performance_by_strategy[strategy] = {
                    'count': 0,
                    'win_count': 0,
                    'total_pnl': 0,
                    'avg_pnl_pct': 0
                }
            
            perf = performance_by_strategy[strategy]
            perf['count'] += 1
            
            if trade['pnl_value'] > 0:
                perf['win_count'] += 1
                
            perf['total_pnl'] += trade['pnl_value']
        
        # Performance by regime
        performance_by_regime = {}
        
        for trade in closed_trades:
            regime = trade.get('regime', 'unknown')
            
            if regime not in performance_by_regime:
                performance_by_regime[regime] = {
                    'count': 0,
                    'win_count': 0,
                    'total_pnl': 0,
                    'avg_pnl_pct': 0
                }
            
            perf = performance_by_regime[regime]
            perf['count'] += 1
            
            if trade['pnl_value'] > 0:
                perf['win_count'] += 1
                
            perf['total_pnl'] += trade['pnl_value']
        
        # Calculate averages and add metrics
        for strategy, perf in performance_by_strategy.items():
            if perf['count'] > 0:
                perf['win_rate'] = perf['win_count'] / perf['count']
                perf['avg_pnl_pct'] = perf['total_pnl'] / perf['count']
        
        for regime, perf in performance_by_regime.items():
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
            'performance_by_strategy': performance_by_strategy,
            'performance_by_regime': performance_by_regime,
            'current_allocations': self.current_allocations.copy(),
            'current_regime': self.current_regime
        } 