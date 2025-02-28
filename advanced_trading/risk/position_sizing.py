"""
Position Sizing Engine
--------------------
Advanced position sizing system for trading strategies.

This module provides a comprehensive position sizing engine that determines
optimal position sizes based on multiple factors:
1. Account risk limits
2. Volatility-adjusted sizing
3. Kelly criterion optimization
4. Expected value calculations
5. Risk-of-ruin protections
6. Dynamic adjustment based on strategy performance
7. Portfolio-level considerations

The position sizing engine can be used standalone or integrated with the 
broader risk management system.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union, Callable
import matplotlib.pyplot as plt
from datetime import datetime
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import existing risk management utilities
from utils.risk_management import (
    calculate_kelly_fraction,
    calculate_position_size,
    calculate_adaptive_stop_loss,
    calculate_var,
    calculate_cvar,
    dynamic_risk_adjustment
)

# Configure logging
logger = logging.getLogger(__name__)

class PositionSizingEngine:
    """
    Advanced position sizing engine for trading strategies.
    
    This class determines optimal position sizes based on multiple factors
    and risk management techniques.
    """
    
    def __init__(
        self,
        account_size: float,
        max_risk_per_trade: float = 0.01,
        max_account_risk: float = 0.05,
        max_correlated_risk: float = 0.1,
        position_sizing_method: str = 'risk_based',
        kelly_fraction: float = 0.3,
        volatility_lookback: int = 20,
        performance_adjustment: bool = True,
        risk_of_ruin_protection: bool = True,
        max_open_trades: int = 10
    ):
        """
        Initialize the position sizing engine.
        
        Args:
            account_size: Total account capital
            max_risk_per_trade: Maximum risk per trade as a fraction of account
            max_account_risk: Maximum total account risk at any time
            max_correlated_risk: Maximum risk for correlated assets/strategies
            position_sizing_method: Method for position sizing
                ('risk_based', 'kelly', 'fixed', 'volatility_adjusted', 'optimal')
            kelly_fraction: Fraction of full Kelly to use (0-1)
            volatility_lookback: Lookback period for volatility calculations
            performance_adjustment: Whether to adjust sizing based on recent performance
            risk_of_ruin_protection: Whether to use risk-of-ruin protection
            max_open_trades: Maximum number of simultaneous open trades
        """
        self.account_size = account_size
        self.max_risk_per_trade = max_risk_per_trade
        self.max_account_risk = max_account_risk
        self.max_correlated_risk = max_correlated_risk
        self.position_sizing_method = position_sizing_method
        self.kelly_fraction = kelly_fraction
        self.volatility_lookback = volatility_lookback
        self.performance_adjustment = performance_adjustment
        self.risk_of_ruin_protection = risk_of_ruin_protection
        self.max_open_trades = max_open_trades
        
        # Track current positions and exposure
        self.current_positions = {}
        self.current_exposure = {
            'total_long': 0.0,
            'total_short': 0.0,
            'net': 0.0,
            'gross': 0.0,
            'categories': {}
        }
        
        # Performance metrics for adjustment
        self.performance_metrics = {
            'win_rate': 0.5,
            'win_loss_ratio': 1.0,
            'sharpe_ratio': 0.0,
            'recent_profit_factor': 1.0,
            'drawdown': 0.0
        }
        
        # Historical trade results for analysis
        self.trade_history = []
        
        # Risk-of-ruin parameters
        self.max_consecutive_losses = 5
        self.consecutive_loss_count = 0
        self.drawdown_scaling = True
        
        # Volatility normalization
        self.volatility_scaling = True
        self.target_volatility = 0.01  # 1% daily volatility
        self.volatility_cap = 3.0      # Don't let volatility adjustment exceed 3x
        
        # Validate parameters
        self._validate_parameters()
        
        logger.info(f"Initialized PositionSizingEngine with {position_sizing_method} method")
    
    def _validate_parameters(self):
        """Validate the initialization parameters."""
        if self.account_size <= 0:
            raise ValueError("Account size must be positive")
        
        if not (0 < self.max_risk_per_trade <= 0.5):
            raise ValueError("max_risk_per_trade must be between 0 and 0.5")
            
        if not (0 < self.max_account_risk <= 0.5):
            raise ValueError("max_account_risk must be between 0 and 0.5")
            
        if not (0 <= self.kelly_fraction <= 1):
            raise ValueError("kelly_fraction must be between 0 and 1")
            
        valid_methods = ['risk_based', 'kelly', 'fixed', 'volatility_adjusted', 'optimal']
        if self.position_sizing_method not in valid_methods:
            raise ValueError(f"position_sizing_method must be one of {valid_methods}")
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_price: Optional[float] = None,
        atr: Optional[float] = None,
        volatility: Optional[float] = None,
        win_rate: Optional[float] = None,
        win_loss_ratio: Optional[float] = None,
        trade_type: str = 'long',
        strategy_id: Optional[str] = None,
        category: str = 'default',
        correlation_group: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Calculate position size for a new trade.
        
        Args:
            symbol: Trading symbol
            entry_price: Planned entry price
            stop_price: Stop loss price (optional if using ATR)
            atr: Average True Range value (optional if using stop_price)
            volatility: Volatility measure (optional)
            win_rate: Expected win rate for this setup (optional)
            win_loss_ratio: Expected win/loss ratio for this setup (optional)
            trade_type: Type of trade ('long' or 'short')
            strategy_id: ID of the strategy (for tracking)
            category: Category of the asset (for risk grouping)
            correlation_group: Group of correlated assets/strategies
            
        Returns:
            Dictionary with position sizing details
        """
        # Determine stop loss percentage
        stop_loss_pct = self._calculate_stop_loss_pct(entry_price, stop_price, atr)
        
        if stop_loss_pct <= 0:
            logger.warning(f"Invalid stop loss for {symbol} (entry: {entry_price}, stop: {stop_price})")
            return {'size': 0, 'value': 0, 'risk_amount': 0}
        
        # Adjust risk based on portfolio risk constraints
        adjusted_risk_pct = self._get_adjusted_risk_pct(
            symbol, 
            category,
            correlation_group,
            trade_type
        )
        
        # Calculate base position size using selected method
        if self.position_sizing_method == 'fixed':
            # Fixed fraction of account
            position_pct = adjusted_risk_pct
        
        elif self.position_sizing_method == 'risk_based':
            # Risk-based sizing
            position_pct = adjusted_risk_pct / stop_loss_pct
        
        elif self.position_sizing_method == 'kelly':
            # Kelly Criterion sizing
            win_rate_to_use = win_rate if win_rate is not None else self.performance_metrics['win_rate']
            win_loss_ratio_to_use = win_loss_ratio if win_loss_ratio is not None else self.performance_metrics['win_loss_ratio']
            
            kelly_size = calculate_kelly_fraction(
                win_rate_to_use,
                win_loss_ratio_to_use,
                self.kelly_fraction
            )
            
            # Limit by max risk per trade
            position_pct = min(kelly_size, adjusted_risk_pct / stop_loss_pct)
        
        elif self.position_sizing_method == 'volatility_adjusted':
            # Volatility-adjusted sizing
            vol_to_use = volatility if volatility is not None else self._get_normalized_volatility(symbol, atr)
            
            # Adjust position size inversely to volatility
            vol_factor = self.target_volatility / vol_to_use if vol_to_use > 0 else 1.0
            vol_factor = min(vol_factor, self.volatility_cap)  # Cap the adjustment
            
            position_pct = adjusted_risk_pct / stop_loss_pct * vol_factor
        
        elif self.position_sizing_method == 'optimal':
            # Combined optimal approach using all factors
            
            # 1. Kelly sizing
            win_rate_to_use = win_rate if win_rate is not None else self.performance_metrics['win_rate']
            win_loss_ratio_to_use = win_loss_ratio if win_loss_ratio is not None else self.performance_metrics['win_loss_ratio']
            
            kelly_size = calculate_kelly_fraction(
                win_rate_to_use,
                win_loss_ratio_to_use,
                self.kelly_fraction
            )
            
            # 2. Volatility adjustment
            vol_to_use = volatility if volatility is not None else self._get_normalized_volatility(symbol, atr)
            vol_factor = self.target_volatility / vol_to_use if vol_to_use > 0 else 1.0
            vol_factor = min(vol_factor, self.volatility_cap)
            
            # 3. Risk of ruin adjustment
            ruin_factor = self._calculate_risk_of_ruin_factor()
            
            # 4. Drawdown adjustment
            drawdown_factor = 1.0
            if self.drawdown_scaling and self.performance_metrics['drawdown'] < 0:
                # Scale down as drawdown increases
                drawdown_factor = max(0.25, 1.0 + 2.0 * self.performance_metrics['drawdown'])
            
            # Combine all factors
            position_pct = (
                min(kelly_size, adjusted_risk_pct / stop_loss_pct) * 
                vol_factor * 
                ruin_factor * 
                drawdown_factor
            )
        
        # Calculate final position size
        position_value = self.account_size * position_pct
        
        # Calculate actual risk amount
        risk_amount = position_value * stop_loss_pct
        
        # Cap position size based on max open trades
        if len(self.current_positions) >= self.max_open_trades:
            logger.warning(f"Maximum open trades reached ({self.max_open_trades}), reducing position size")
            position_pct *= 0.5
            position_value *= 0.5
            risk_amount *= 0.5
        
        # Return position details
        position_data = {
            'symbol': symbol,
            'strategy_id': strategy_id,
            'trade_type': trade_type,
            'entry_price': entry_price,
            'stop_price': stop_price if stop_price else entry_price * (1 - stop_loss_pct if trade_type == 'long' else 1 + stop_loss_pct),
            'stop_loss_pct': stop_loss_pct,
            'position_pct': position_pct,
            'size': position_value / entry_price,  # Units
            'value': position_value,               # Base currency
            'risk_amount': risk_amount,            # Actual risk in base currency
            'category': category,
            'correlation_group': correlation_group
        }
        
        logger.info(
            f"Position sizing for {symbol}: " +
            f"size={position_data['size']:.4f}, " +
            f"value=${position_data['value']:.2f}, " +
            f"risk=${position_data['risk_amount']:.2f}"
        )
        
        return position_data
    
    def update_position(
        self,
        symbol: str,
        current_price: float,
        new_stop_price: Optional[float] = None,
        partial_exit: float = 0.0,
        update_exposure: bool = True
    ) -> Dict[str, float]:
        """
        Update an existing position with new stop or partial exit.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            new_stop_price: New stop loss price (if None, keep existing)
            partial_exit: Fraction of position to exit (0-1)
            update_exposure: Whether to update the exposure tracking
            
        Returns:
            Updated position details
        """
        if symbol not in self.current_positions:
            logger.warning(f"Cannot update {symbol} - position does not exist")
            return {}
        
        position = self.current_positions[symbol].copy()
        
        # Update stop loss if provided
        if new_stop_price is not None:
            old_stop = position['stop_price']
            position['stop_price'] = new_stop_price
            
            # Recalculate stop loss percentage
            if position['trade_type'] == 'long':
                position['stop_loss_pct'] = (current_price - new_stop_price) / current_price
            else:
                position['stop_loss_pct'] = (new_stop_price - current_price) / current_price
            
            logger.info(f"Updated stop for {symbol} from {old_stop:.2f} to {new_stop_price:.2f}")
        
        # Handle partial exit
        if 0 < partial_exit <= 1:
            original_size = position['size']
            position['size'] *= (1 - partial_exit)
            position['value'] = position['size'] * current_price
            
            # Recalculate risk amount
            position['risk_amount'] = position['value'] * position['stop_loss_pct']
            
            logger.info(f"Partial exit for {symbol}: {partial_exit*100:.1f}% of position")
        
        # Update current positions
        self.current_positions[symbol] = position
        
        # Update exposure tracking
        if update_exposure:
            self._update_exposure()
        
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        exit_reason: str = 'manual'
    ) -> Dict[str, float]:
        """
        Close a position and update performance metrics.
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
            exit_time: Exit timestamp
            exit_reason: Reason for exit
            
        Returns:
            Dictionary with trade results
        """
        if symbol not in self.current_positions:
            logger.warning(f"Cannot close {symbol} - position does not exist")
            return {}
        
        position = self.current_positions[symbol]
        
        # Calculate trade result
        if position['trade_type'] == 'long':
            pnl_pct = (exit_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - exit_price) / position['entry_price']
        
        pnl_amount = position['value'] * pnl_pct
        
        # Create trade record
        trade_result = {
            'symbol': symbol,
            'strategy_id': position['strategy_id'],
            'trade_type': position['trade_type'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'size': position['size'],
            'value': position['value'],
            'pnl_pct': pnl_pct,
            'pnl_amount': pnl_amount,
            'risk_amount': position['risk_amount'],
            'risk_reward_realized': pnl_amount / position['risk_amount'] if position['risk_amount'] > 0 else 0,
            'exit_reason': exit_reason,
            'entry_time': position.get('entry_time', None),
            'exit_time': exit_time if exit_time else datetime.now(),
            'category': position.get('category', 'default'),
            'correlation_group': position.get('correlation_group', None)
        }
        
        # Update trade history
        self.trade_history.append(trade_result)
        
        # Update performance metrics
        self._update_performance_metrics(trade_result)
        
        # Remove from current positions
        del self.current_positions[symbol]
        
        # Update exposure tracking
        self._update_exposure()
        
        logger.info(
            f"Closed {symbol} position: " +
            f"P&L=${pnl_amount:.2f} ({pnl_pct*100:.2f}%), " +
            f"R/R={trade_result['risk_reward_realized']:.2f}"
        )
        
        return trade_result
    
    def update_account_size(self, new_account_size: float) -> None:
        """
        Update the account size.
        
        Args:
            new_account_size: New account size
        """
        if new_account_size <= 0:
            logger.error(f"Invalid account size: {new_account_size}")
            return
        
        self.account_size = new_account_size
        logger.info(f"Updated account size to {new_account_size}")
    
    def get_current_exposure(self) -> Dict[str, float]:
        """
        Get current exposure metrics.
        
        Returns:
            Dictionary with exposure metrics
        """
        # Ensure exposure is up to date
        self._update_exposure()
        
        # Add exposure as percentage of account
        exposure_pct = {
            'total_long_pct': self.current_exposure['total_long'] / self.account_size,
            'total_short_pct': self.current_exposure['total_short'] / self.account_size,
            'net_pct': self.current_exposure['net'] / self.account_size,
            'gross_pct': self.current_exposure['gross'] / self.account_size,
        }
        
        # Add to exposure data
        exposure_data = {**self.current_exposure, **exposure_pct}
        
        return exposure_data
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Get current performance metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        return self.performance_metrics.copy()
    
    def analyze_trade_history(self, lookback: int = None) -> Dict[str, Any]:
        """
        Analyze trade history to get performance metrics.
        
        Args:
            lookback: Number of recent trades to include (None for all)
            
        Returns:
            Dictionary with trade analysis
        """
        if not self.trade_history:
            return {'total_trades': 0}
        
        # Filter by lookback if specified
        trades = self.trade_history
        if lookback and lookback < len(trades):
            trades = trades[-lookback:]
        
        # Calculate metrics
        wins = [t for t in trades if t['pnl_amount'] > 0]
        losses = [t for t in trades if t['pnl_amount'] <= 0]
        
        win_rate = len(wins) / len(trades) if trades else 0
        
        avg_win = np.mean([t['pnl_amount'] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t['pnl_amount']) for t in losses]) if losses else 0
        
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        total_profit = sum(t['pnl_amount'] for t in wins)
        total_loss = sum(abs(t['pnl_amount']) for t in losses)
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Calculate expectancy
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        expectancy_per_dollar = expectancy / np.mean([t['risk_amount'] for t in trades]) if trades else 0
        
        # By category
        by_category = {}
        categories = set(t['category'] for t in trades)
        
        for category in categories:
            cat_trades = [t for t in trades if t['category'] == category]
            cat_wins = [t for t in cat_trades if t['pnl_amount'] > 0]
            
            by_category[category] = {
                'count': len(cat_trades),
                'win_rate': len(cat_wins) / len(cat_trades) if cat_trades else 0,
                'avg_pnl': np.mean([t['pnl_amount'] for t in cat_trades]) if cat_trades else 0,
                'profit_factor': (
                    sum(t['pnl_amount'] for t in cat_trades if t['pnl_amount'] > 0) / 
                    abs(sum(t['pnl_amount'] for t in cat_trades if t['pnl_amount'] <= 0))
                ) if sum(t['pnl_amount'] for t in cat_trades if t['pnl_amount'] <= 0) != 0 else float('inf')
            }
        
        # Create analysis dictionary
        analysis = {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'win_loss_ratio': win_loss_ratio,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'expectancy_per_dollar_risked': expectancy_per_dollar,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'net_profit': total_profit - total_loss,
            'by_category': by_category
        }
        
        return analysis
    
    def plot_risk_allocation(self, figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Plot current risk allocation.
        
        Args:
            figsize: Figure size
            
        Returns:
            Matplotlib figure with risk allocation visualization
        """
        # Ensure exposure is up to date
        self._update_exposure()
        
        # Calculate risk allocation
        risk_by_position = {}
        
        for symbol, position in self.current_positions.items():
            risk_by_position[symbol] = position['risk_amount']
        
        if not risk_by_position:
            # No open positions
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, 'No open positions', ha='center', va='center', fontsize=14)
            ax.set_title('Current Risk Allocation')
            ax.axis('off')
            return fig
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Plot risk by position
        ax1.bar(risk_by_position.keys(), risk_by_position.values(), color='skyblue')
        ax1.set_title('Risk Allocation by Position')
        ax1.set_ylabel('Risk Amount')
        ax1.tick_params(axis='x', rotation=45)
        
        # Plot risk by category
        risk_by_category = {}
        for position in self.current_positions.values():
            category = position.get('category', 'default')
            if category not in risk_by_category:
                risk_by_category[category] = 0
            risk_by_category[category] += position['risk_amount']
        
        ax2.pie(
            risk_by_category.values(),
            labels=risk_by_category.keys(),
            autopct='%1.1f%%',
            startangle=90
        )
        ax2.set_title('Risk Allocation by Category')
        
        plt.tight_layout()
        
        return fig
    
    def _calculate_stop_loss_pct(
        self, 
        entry_price: float, 
        stop_price: Optional[float], 
        atr: Optional[float]
    ) -> float:
        """
        Calculate stop loss percentage based on provided inputs.
        
        Args:
            entry_price: Entry price
            stop_price: Stop loss price (optional)
            atr: ATR value (optional)
            
        Returns:
            Stop loss percentage (0-1)
        """
        if stop_price is not None and stop_price > 0:
            # Calculate directly from stop price
            stop_loss_pct = abs(entry_price - stop_price) / entry_price
        elif atr is not None and atr > 0:
            # Calculate from ATR
            stop_loss_pct = calculate_adaptive_stop_loss(
                price=entry_price,
                atr=atr,
                multiplier=2.0,
                min_pct=0.005,
                max_pct=0.1
            )
        else:
            # Default fallback
            logger.warning(f"No valid stop loss or ATR provided, using default 2% stop")
            stop_loss_pct = 0.02
        
        return stop_loss_pct
    
    def _get_adjusted_risk_pct(
        self,
        symbol: str,
        category: str,
        correlation_group: Optional[str],
        trade_type: str
    ) -> float:
        """
        Get risk percentage adjusted for portfolio constraints.
        
        Args:
            symbol: Symbol
            category: Asset category
            correlation_group: Correlation group
            trade_type: Trade type
            
        Returns:
            Adjusted risk percentage
        """
        # Start with base risk per trade
        adjusted_risk = self.max_risk_per_trade
        
        # Get current exposure
        exposure = self.get_current_exposure()
        
        # Adjust for total account risk
        current_total_risk = sum(p['risk_amount'] for p in self.current_positions.values())
        current_risk_pct = current_total_risk / self.account_size
        
        if current_risk_pct >= self.max_account_risk:
            logger.warning(f"Maximum account risk reached ({current_risk_pct:.1%}), reducing position size")
            adjusted_risk *= 0.5
        
        # Adjust for category exposure
        if category in exposure['categories']:
            category_exposure = exposure['categories'][category]
            category_pct = category_exposure / self.account_size
            
            # Reduce risk if category exposure is high
            if category_pct > 0.25:  # If more than 25% in one category
                category_factor = max(0.25, 1 - (category_pct - 0.25))
                adjusted_risk *= category_factor
                logger.info(f"High exposure to category {category}, reducing risk by factor {category_factor:.2f}")
        
        # Adjust for correlation group
        if correlation_group:
            # Calculate current risk in this correlation group
            correlated_risk = sum(
                p['risk_amount'] for p in self.current_positions.values() 
                if p.get('correlation_group') == correlation_group
            )
            
            correlated_risk_pct = correlated_risk / self.account_size
            
            if correlated_risk_pct >= self.max_correlated_risk:
                logger.warning(f"High correlated risk in group {correlation_group}, reducing position size")
                adjusted_risk *= 0.5
        
        # Adjust for directional exposure
        if trade_type == 'long' and exposure.get('total_long_pct', 0) > 0.5:
            long_factor = max(0.5, 1 - (exposure['total_long_pct'] - 0.5))
            adjusted_risk *= long_factor
            logger.info(f"High long exposure ({exposure['total_long_pct']:.1%}), reducing risk")
            
        elif trade_type == 'short' and exposure.get('total_short_pct', 0) > 0.5:
            short_factor = max(0.5, 1 - (exposure['total_short_pct'] - 0.5))
            adjusted_risk *= short_factor
            logger.info(f"High short exposure ({exposure['total_short_pct']:.1%}), reducing risk")
        
        # Apply performance-based adjustment if enabled
        if self.performance_adjustment:
            performance_factor = self._get_performance_adjustment_factor()
            adjusted_risk *= performance_factor
        
        return adjusted_risk
    
    def _get_normalized_volatility(self, symbol: str, atr: Optional[float]) -> float:
        """
        Get normalized volatility for position sizing.
        
        Args:
            symbol: Symbol
            atr: ATR value
            
        Returns:
            Normalized volatility
        """
        # If ATR provided, use it
        if atr is not None and atr > 0:
            # Convert ATR to percentage
            return atr
        
        # Otherwise use a default volatility
        return 0.02  # Default 2% daily volatility
    
    def _calculate_risk_of_ruin_factor(self) -> float:
        """
        Calculate risk of ruin adjustment factor.
        
        Returns:
            Risk of ruin adjustment factor (0-1)
        """
        if not self.risk_of_ruin_protection:
            return 1.0
        
        # Factor based on consecutive losses
        consecutive_loss_factor = max(0.25, 1.0 - (self.consecutive_loss_count / self.max_consecutive_losses))
        
        return consecutive_loss_factor
    
    def _get_performance_adjustment_factor(self) -> float:
        """
        Get adjustment factor based on recent performance.
        
        Returns:
            Performance adjustment factor (0-2)
        """
        # Start with neutral factor
        factor = 1.0
        
        # Adjust based on profit factor
        profit_factor = self.performance_metrics.get('profit_factor', 1.0)
        if profit_factor > 1.5:
            # Increase size for strong performance
            factor *= min(1.5, profit_factor / 1.5)
        elif profit_factor < 1.0:
            # Decrease size for weak performance
            factor *= max(0.5, profit_factor)
        
        # Adjust based on drawdown
        drawdown = self.performance_metrics.get('drawdown', 0.0)
        if drawdown < 0:
            # Decrease size during drawdowns
            factor *= max(0.5, 1.0 + drawdown)
        
        # Limit the range
        return max(0.5, min(factor, 1.5))
    
    def _update_exposure(self) -> None:
        """Update current exposure tracking."""
        exposure = {
            'total_long': 0.0,
            'total_short': 0.0,
            'net': 0.0,
            'gross': 0.0,
            'categories': {}
        }
        
        for symbol, position in self.current_positions.items():
            category = position.get('category', 'default')
            
            # Update long/short exposure
            if position['trade_type'] == 'long':
                exposure['total_long'] += position['value']
            else:
                exposure['total_short'] += position['value']
            
            # Update category exposure
            if category not in exposure['categories']:
                exposure['categories'][category] = 0.0
            
            exposure['categories'][category] += position['value']
        
        # Calculate net and gross exposure
        exposure['net'] = exposure['total_long'] - exposure['total_short']
        exposure['gross'] = exposure['total_long'] + exposure['total_short']
        
        self.current_exposure = exposure
    
    def _update_performance_metrics(self, trade_result: Dict[str, Any]) -> None:
        """
        Update performance metrics based on a completed trade.
        
        Args:
            trade_result: Dictionary with trade result
        """
        # Update consecutive loss counter
        if trade_result['pnl_amount'] > 0:
            self.consecutive_loss_count = 0
        else:
            self.consecutive_loss_count += 1
        
        # Calculate metrics based on recent trade history
        analysis = self.analyze_trade_history(lookback=50)  # Last 50 trades
        
        # Update performance metrics
        self.performance_metrics.update({
            'win_rate': analysis['win_rate'],
            'win_loss_ratio': analysis['win_loss_ratio'],
            'profit_factor': analysis['profit_factor'],
            'expectancy': analysis['expectancy_per_dollar_risked'],
        })
        
        # Calculate drawdown (simplified)
        if len(self.trade_history) >= 10:
            # Get cumulative P&L of last 10 trades
            recent_pnl = [t['pnl_amount'] for t in self.trade_history[-10:]]
            cumulative = np.cumsum(recent_pnl)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - peak) / self.account_size
            self.performance_metrics['drawdown'] = drawdown[-1] if len(drawdown) > 0 else 0
        
        logger.debug(f"Updated performance metrics: {self.performance_metrics}") 