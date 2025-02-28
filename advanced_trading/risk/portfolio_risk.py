"""
Portfolio Risk Controller
---------------------
Advanced portfolio-level risk management for trading strategies.

This module provides a comprehensive system for managing risk at the portfolio level,
including:
1. Correlation-aware position sizing and risk allocation
2. Exposure monitoring and management by asset class/category
3. Drawdown-based risk controls
4. Volatility-targeted portfolio construction
5. Hierarchical risk parity for optimal risk allocation

The portfolio risk controller can be used standalone or integrated with position sizing
and stop management components.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union, Callable, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
import seaborn as sns
import json
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import existing risk management and portfolio allocation utilities
from utils.risk_management import calculate_var, calculate_cvar, calculate_max_drawdown
from utils.portfolio_allocation import PortfolioAllocator

# Configure logging
logger = logging.getLogger(__name__)

class PortfolioRiskController:
    """
    Advanced portfolio-level risk management for trading strategies.
    
    This class implements multiple methods for managing risk at the portfolio level,
    including exposure limits, correlation management, and drawdown controls.
    """
    
    def __init__(
        self,
        account_size: float,
        max_portfolio_risk: float = 0.05,     # 5% max total portfolio risk
        max_correlation_risk: float = 0.1,    # 10% max risk for correlated assets
        max_category_allocation: float = 0.4, # 40% max allocation to any category
        drawdown_control: bool = True,        # Enable drawdown-based risk control
        drawdown_control_threshold: float = 0.05,  # 5% drawdown activates controls
        drawdown_risk_reduction: float = 0.5, # 50% risk reduction during drawdowns
        volatility_targeting: bool = True,    # Enable volatility targeting
        target_volatility: float = 0.15,      # 15% annualized target volatility
        risk_parity: bool = True,             # Enable risk parity allocation
        rebalance_threshold: float = 0.1,     # 10% deviation to trigger rebalance
        leverage_control: bool = True,        # Enable leverage control
        max_leverage: float = 1.5             # Maximum allowed leverage
    ):
        """
        Initialize the portfolio risk controller.
        
        Args:
            account_size: Total account capital
            max_portfolio_risk: Maximum total portfolio risk as fraction of account
            max_correlation_risk: Maximum risk for correlated assets/strategies
            max_category_allocation: Maximum allocation to any single category
            drawdown_control: Whether to enable drawdown-based risk control
            drawdown_control_threshold: Drawdown threshold to activate controls
            drawdown_risk_reduction: Risk reduction factor during drawdowns
            volatility_targeting: Whether to target specific portfolio volatility
            target_volatility: Target annualized portfolio volatility
            risk_parity: Whether to use risk parity for allocation
            rebalance_threshold: Threshold deviation to trigger rebalance
            leverage_control: Whether to enable leverage control
            max_leverage: Maximum allowed leverage
        """
        self.account_size = account_size
        self.max_portfolio_risk = max_portfolio_risk
        self.max_correlation_risk = max_correlation_risk
        self.max_category_allocation = max_category_allocation
        self.drawdown_control = drawdown_control
        self.drawdown_control_threshold = drawdown_control_threshold
        self.drawdown_risk_reduction = drawdown_risk_reduction
        self.volatility_targeting = volatility_targeting
        self.target_volatility = target_volatility
        self.risk_parity = risk_parity
        self.rebalance_threshold = rebalance_threshold
        self.leverage_control = leverage_control
        self.max_leverage = max_leverage
        
        # Current portfolio state
        self.positions = {}
        self.category_allocations = {}
        self.correlation_groups = {}
        self.current_drawdown = 0.0
        self.peak_equity = account_size
        self.current_equity = account_size
        self.in_drawdown_control = False
        
        # Historical performance tracking
        self.equity_curve = pd.Series([account_size], index=[datetime.now()])
        self.drawdown_history = pd.Series([0.0], index=[datetime.now()])
        self.risk_allocation_history = []
        self.var_history = []
        self.cvar_history = []
        
        # Correlation matrix and volatilities
        self.correlation_matrix = pd.DataFrame()
        self.volatilities = {}
        self.returns_data = {}
        
        # Portfolio allocator for risk parity
        self.allocator = PortfolioAllocator(
            method='hrp' if risk_parity else 'equal',
            target_volatility=target_volatility if volatility_targeting else None
        )
        
        # Tracking risk-adjusted returns
        self.sharpe_ratio = 0.0
        self.sortino_ratio = 0.0
        self.calmar_ratio = 0.0
        
        # Log initialization
        logger.info(f"Initialized PortfolioRiskController with max risk {max_portfolio_risk*100:.1f}%")
    
    def register_position(
        self,
        symbol: str,
        position_size: float,
        entry_price: float,
        stop_price: float,
        trade_type: str = 'long',
        category: str = 'default',
        correlation_group: Optional[str] = None,
        expected_volatility: Optional[float] = None,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new position with the risk controller.
        
        Args:
            symbol: Trading symbol
            position_size: Position size in base units
            entry_price: Entry price
            stop_price: Stop-loss price
            trade_type: 'long' or 'short'
            category: Asset category (e.g., 'crypto_major', 'crypto_alt', 'stock_tech')
            correlation_group: Group of correlated assets/strategies
            expected_volatility: Expected annualized volatility
            strategy_id: ID of the strategy that created this position
            
        Returns:
            Dictionary with position details including risk metrics
        """
        # Calculate position value
        position_value = position_size * entry_price
        
        # Calculate stop distance as percentage
        if trade_type == 'long':
            stop_pct = (entry_price - stop_price) / entry_price
        else:
            stop_pct = (stop_price - entry_price) / entry_price
        
        # Calculate risk amount
        risk_amount = position_value * stop_pct
        
        # Calculate risk as percentage of account
        risk_pct = risk_amount / self.account_size
        
        # Create position object
        position = {
            'symbol': symbol,
            'position_size': position_size,
            'entry_price': entry_price,
            'current_price': entry_price,
            'stop_price': stop_price,
            'stop_pct': stop_pct,
            'trade_type': trade_type,
            'category': category,
            'correlation_group': correlation_group,
            'strategy_id': strategy_id,
            'value': position_value,
            'risk_amount': risk_amount,
            'risk_pct': risk_pct,
            'entry_time': datetime.now(),
            'last_update_time': datetime.now(),
            'expected_volatility': expected_volatility,
            'pnl_amount': 0.0,
            'pnl_pct': 0.0
        }
        
        # Register position
        self.positions[symbol] = position
        
        # Update category allocations
        if category not in self.category_allocations:
            self.category_allocations[category] = 0.0
        self.category_allocations[category] += position_value
        
        # Update correlation groups
        if correlation_group:
            if correlation_group not in self.correlation_groups:
                self.correlation_groups[correlation_group] = 0.0
            self.correlation_groups[correlation_group] += risk_amount
        
        # Log new position
        logger.info(
            f"Registered {trade_type} position: {symbol}, "
            f"size={position_size:.4f}, value=${position_value:.2f}, "
            f"risk=${risk_amount:.2f} ({risk_pct*100:.2f}%)"
        )
        
        # Check if this position violates any risk limits
        self._check_risk_limits(position)
        
        return position.copy()
    
    def update_position(
        self,
        symbol: str,
        current_price: float,
        stop_price: Optional[float] = None,
        position_size: Optional[float] = None,
        update_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Update an existing position with current price and optional changes.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            stop_price: Updated stop-loss price (optional)
            position_size: Updated position size (optional)
            update_time: Current timestamp (optional)
            
        Returns:
            Updated position details
        """
        if symbol not in self.positions:
            logger.warning(f"Cannot update {symbol} - position does not exist")
            return {}
        
        position = self.positions[symbol].copy()
        old_value = position['value']
        old_risk = position['risk_amount']
        
        # Update price and recalculate value
        position['current_price'] = current_price
        
        # If position size changed, update it
        if position_size is not None and position_size != position['position_size']:
            position['position_size'] = position_size
        
        # Recalculate position value
        position['value'] = position['position_size'] * current_price
        
        # Update stop price if provided
        if stop_price is not None:
            position['stop_price'] = stop_price
            
            # Recalculate stop percentage
            if position['trade_type'] == 'long':
                position['stop_pct'] = (current_price - stop_price) / current_price
            else:
                position['stop_pct'] = (stop_price - current_price) / current_price
        
        # Recalculate risk amount
        position['risk_amount'] = position['value'] * position['stop_pct']
        position['risk_pct'] = position['risk_amount'] / self.account_size
        
        # Calculate P&L
        if position['trade_type'] == 'long':
            position['pnl_amount'] = (current_price - position['entry_price']) * position['position_size']
            position['pnl_pct'] = (current_price / position['entry_price']) - 1
        else:
            position['pnl_amount'] = (position['entry_price'] - current_price) * position['position_size']
            position['pnl_pct'] = 1 - (current_price / position['entry_price'])
        
        # Update timestamp
        if update_time:
            position['last_update_time'] = update_time
        else:
            position['last_update_time'] = datetime.now()
        
        # Update category allocations
        category = position['category']
        self.category_allocations[category] = self.category_allocations.get(category, 0) - old_value + position['value']
        
        # Update correlation groups
        if position['correlation_group']:
            corr_group = position['correlation_group']
            self.correlation_groups[corr_group] = self.correlation_groups.get(corr_group, 0) - old_risk + position['risk_amount']
        
        # Store updated position
        self.positions[symbol] = position
        
        return position.copy()
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        exit_reason: str = 'manual'
    ) -> Dict[str, Any]:
        """
        Close a position and update portfolio state.
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
            exit_time: Exit timestamp (optional)
            exit_reason: Reason for exit
            
        Returns:
            Dictionary with closed position details
        """
        if symbol not in self.positions:
            logger.warning(f"Cannot close {symbol} - position does not exist")
            return {}
        
        position = self.positions[symbol].copy()
        
        # Calculate final P&L
        if position['trade_type'] == 'long':
            position['pnl_amount'] = (exit_price - position['entry_price']) * position['position_size']
            position['pnl_pct'] = (exit_price / position['entry_price']) - 1
        else:
            position['pnl_amount'] = (position['entry_price'] - exit_price) * position['position_size']
            position['pnl_pct'] = 1 - (exit_price / position['entry_price'])
        
        # Set exit details
        position['exit_price'] = exit_price
        position['exit_time'] = exit_time if exit_time else datetime.now()
        position['exit_reason'] = exit_reason
        
        # Update account equity
        self.current_equity += position['pnl_amount']
        self._update_equity_curve()
        
        # Update category allocations
        category = position['category']
        self.category_allocations[category] = max(0, self.category_allocations.get(category, 0) - position['value'])
        
        # Update correlation groups
        if position['correlation_group']:
            corr_group = position['correlation_group']
            self.correlation_groups[corr_group] = max(0, self.correlation_groups.get(corr_group, 0) - position['risk_amount'])
        
        # Remove position
        del self.positions[symbol]
        
        # Log closed position
        logger.info(
            f"Closed {position['trade_type']} position: {symbol}, "
            f"P&L=${position['pnl_amount']:.2f} ({position['pnl_pct']*100:.2f}%), "
            f"reason: {exit_reason}"
        )
        
        # If this was the last position in a category, clean up
        if self.category_allocations[category] == 0:
            del self.category_allocations[category]
        
        # If this was the last position in a correlation group, clean up
        if position['correlation_group'] and self.correlation_groups.get(position['correlation_group'], 0) == 0:
            if position['correlation_group'] in self.correlation_groups:
                del self.correlation_groups[position['correlation_group']]
        
        # Update risk measures
        self._update_risk_metrics()
        
        return position
    
    def update_account_equity(
        self,
        new_equity: float,
        update_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Update the account equity value and recalculate risk metrics.
        
        Args:
            new_equity: New account equity value
            update_time: Update timestamp (optional)
            
        Returns:
            Dictionary with updated account metrics
        """
        old_equity = self.current_equity
        self.current_equity = new_equity
        
        # Update peak equity if new high
        if new_equity > self.peak_equity:
            self.peak_equity = new_equity
        
        # Calculate current drawdown
        self.current_drawdown = (self.peak_equity - new_equity) / self.peak_equity
        
        # Update equity curve
        self._update_equity_curve(update_time)
        
        # Check if we need to activate drawdown controls
        if self.drawdown_control and self.current_drawdown >= self.drawdown_control_threshold:
            if not self.in_drawdown_control:
                logger.warning(
                    f"Activating drawdown control: current drawdown {self.current_drawdown*100:.2f}% "
                    f"exceeds threshold {self.drawdown_control_threshold*100:.2f}%"
                )
                self.in_drawdown_control = True
                self._apply_drawdown_controls()
        elif self.in_drawdown_control and self.current_drawdown < self.drawdown_control_threshold / 2:
            # Deactivate drawdown controls when drawdown is half the threshold
            logger.info(
                f"Deactivating drawdown control: current drawdown {self.current_drawdown*100:.2f}% "
                f"below half of threshold {self.drawdown_control_threshold*100/2:.2f}%"
            )
            self.in_drawdown_control = False
        
        # Update risk measures
        self._update_risk_metrics()
        
        # Return updated metrics
        return {
            'account_size': self.account_size,
            'current_equity': self.current_equity,
            'peak_equity': self.peak_equity,
            'current_drawdown': self.current_drawdown,
            'in_drawdown_control': self.in_drawdown_control,
            'total_exposure': self.get_total_exposure(),
            'total_risk': self.get_total_risk()
        }
    
    def get_portfolio_state(self) -> Dict[str, Any]:
        """
        Get current portfolio state including positions, allocations, and risk metrics.
        
        Returns:
            Dictionary with comprehensive portfolio state
        """
        # Calculate total exposure and risk
        total_exposure = sum(p['value'] for p in self.positions.values())
        total_risk = sum(p['risk_amount'] for p in self.positions.values())
        
        # Calculate leverage
        leverage = total_exposure / self.current_equity if self.current_equity > 0 else 0
        
        # Calculate exposure and risk by category
        exposure_by_category = {}
        risk_by_category = {}
        
        for symbol, position in self.positions.items():
            category = position['category']
            if category not in exposure_by_category:
                exposure_by_category[category] = 0
                risk_by_category[category] = 0
            
            exposure_by_category[category] += position['value']
            risk_by_category[category] += position['risk_amount']
        
        # Calculate exposure and risk percentages
        exposure_pct_by_category = {k: v / self.current_equity for k, v in exposure_by_category.items()}
        risk_pct_by_category = {k: v / self.current_equity for k, v in risk_by_category.items()}
        
        # Get latest risk metrics
        var_95 = self.var_history[-1] if self.var_history else 0
        cvar_95 = self.cvar_history[-1] if self.cvar_history else 0
        
        # Create portfolio state dictionary
        portfolio_state = {
            'timestamp': datetime.now(),
            'account_size': self.account_size,
            'current_equity': self.current_equity,
            'peak_equity': self.peak_equity,
            'current_drawdown': self.current_drawdown,
            'positions': {symbol: pos.copy() for symbol, pos in self.positions.items()},
            'total_positions': len(self.positions),
            'total_exposure': total_exposure,
            'total_exposure_pct': total_exposure / self.current_equity if self.current_equity > 0 else 0,
            'total_risk': total_risk,
            'total_risk_pct': total_risk / self.current_equity if self.current_equity > 0 else 0,
            'leverage': leverage,
            'category_allocations': self.category_allocations.copy(),
            'category_allocations_pct': exposure_pct_by_category,
            'risk_by_category': risk_by_category,
            'risk_pct_by_category': risk_pct_by_category,
            'correlation_groups': self.correlation_groups.copy(),
            'in_drawdown_control': self.in_drawdown_control,
            'var_95_pct': var_95,
            'cvar_95_pct': cvar_95,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio
        }
        
        return portfolio_state
    
    def get_total_exposure(self) -> float:
        """
        Get total portfolio exposure.
        
        Returns:
            Total exposure in base currency
        """
        return sum(p['value'] for p in self.positions.values())
    
    def get_total_risk(self) -> float:
        """
        Get total portfolio risk.
        
        Returns:
            Total risk in base currency
        """
        return sum(p['risk_amount'] for p in self.positions.values())
    
    def _check_risk_limits(self, position: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check if a position violates any risk limits.
        
        Args:
            position: Position data dictionary
            
        Returns:
            Dictionary with risk limit violations
        """
        violations = {
            'total_risk': False,
            'category_risk': False,
            'correlation_risk': False,
            'leverage': False
        }
        
        # Check total portfolio risk
        total_risk = self.get_total_risk()
        total_risk_pct = total_risk / self.account_size
        if total_risk_pct > self.max_portfolio_risk:
            violations['total_risk'] = True
            logger.warning(
                f"Position {position['symbol']} causes total risk to exceed limit: "
                f"{total_risk_pct*100:.2f}% > {self.max_portfolio_risk*100:.2f}%"
            )
        
        # Check category allocation
        category = position['category']
        category_allocation = self.category_allocations.get(category, 0)
        category_allocation_pct = category_allocation / self.account_size
        
        if category_allocation_pct > self.max_category_allocation:
            violations['category_risk'] = True
            logger.warning(
                f"Position {position['symbol']} causes category {category} to exceed limit: "
                f"{category_allocation_pct*100:.2f}% > {self.max_category_allocation*100:.2f}%"
            )
        
        # Check correlation group risk
        if position['correlation_group']:
            corr_group = position['correlation_group']
            corr_group_risk = self.correlation_groups.get(corr_group, 0)
            corr_group_risk_pct = corr_group_risk / self.account_size
            
            if corr_group_risk_pct > self.max_correlation_risk:
                violations['correlation_risk'] = True
                logger.warning(
                    f"Position {position['symbol']} causes correlation group {corr_group} to exceed limit: "
                    f"{corr_group_risk_pct*100:.2f}% > {self.max_correlation_risk*100:.2f}%"
                )
        
        # Check leverage
        total_exposure = self.get_total_exposure()
        leverage = total_exposure / self.current_equity if self.current_equity > 0 else 0
        
        if self.leverage_control and leverage > self.max_leverage:
            violations['leverage'] = True
            logger.warning(
                f"Position {position['symbol']} causes leverage to exceed limit: "
                f"{leverage:.2f}x > {self.max_leverage:.2f}x"
            )
        
        return violations
    
    def _update_equity_curve(self, timestamp: Optional[datetime] = None) -> None:
        """
        Update the equity curve with current equity value.
        
        Args:
            timestamp: Timestamp for the equity update (optional)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Add to equity curve series
        self.equity_curve[timestamp] = self.current_equity
        
        # Calculate current drawdown
        self.current_drawdown = (self.peak_equity - self.current_equity) / self.peak_equity if self.peak_equity > 0 else 0
        
        # Add to drawdown history
        self.drawdown_history[timestamp] = self.current_drawdown
    
    def _update_risk_metrics(self) -> None:
        """
        Update portfolio risk metrics including VaR, CVaR, and ratios.
        """
        # Only update if we have enough history (at least 10 points)
        if len(self.equity_curve) >= 10:
            # Calculate returns
            returns = self.equity_curve.pct_change().dropna()
            
            # Store returns for correlation analysis
            time_index = returns.index[-1]
            if time_index not in self.returns_data:
                self.returns_data[time_index] = returns.iloc[-1]
            
            # Calculate VaR and CVaR (95%)
            var_95 = calculate_var(returns, confidence_level=0.95)
            cvar_95 = calculate_cvar(returns, confidence_level=0.95)
            
            self.var_history.append(var_95)
            self.cvar_history.append(cvar_95)
            
            # Calculate annualized metrics (assuming daily data)
            if len(returns) >= 30:  # Need reasonable amount of data
                # Annualized return
                ann_return = returns.mean() * 252
                
                # Annualized volatility
                ann_vol = returns.std() * np.sqrt(252)
                
                # Downside deviation (only negative returns)
                downside_returns = returns[returns < 0]
                downside_dev = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 1e-6
                
                # Maximum drawdown
                max_dd = calculate_max_drawdown(self.equity_curve)
                
                # Calculate ratios
                if ann_vol > 0:
                    self.sharpe_ratio = ann_return / ann_vol
                
                if downside_dev > 0:
                    self.sortino_ratio = ann_return / downside_dev
                
                if max_dd > 0:
                    self.calmar_ratio = ann_return / max_dd
        
        # Store risk allocation snapshot
        risk_allocation = {
            'timestamp': datetime.now(),
            'total_risk': self.get_total_risk(),
            'risk_by_category': {cat: sum(p['risk_amount'] for p in self.positions.values() 
                                          if p['category'] == cat) 
                               for cat in self.category_allocations},
            'risk_by_corr_group': self.correlation_groups.copy()
        }
        
        self.risk_allocation_history.append(risk_allocation)
    
    def _apply_drawdown_controls(self) -> None:
        """
        Apply risk controls during drawdown periods.
        
        This reduces position sizes and risk limits when in drawdown.
        """
        if not self.drawdown_control or not self.in_drawdown_control:
            return
        
        # Calculate risk reduction factor
        reduction_factor = self.drawdown_risk_reduction
        
        logger.info(
            f"Applying drawdown risk controls - reducing risk by factor {reduction_factor:.2f} "
            f"due to drawdown of {self.current_drawdown*100:.2f}%"
        )
        
        # Identify positions to reduce
        for symbol, position in self.positions.items():
            # Determine how much to reduce each position
            current_size = position['position_size']
            new_size = current_size * (1 - reduction_factor)
            
            logger.info(
                f"Reducing position {symbol} from {current_size:.4f} to {new_size:.4f} "
                f"units due to drawdown controls"
            )
            
            # Update position with reduced size
            self.update_position(
                symbol=symbol,
                current_price=position['current_price'],
                position_size=new_size
            )
    
    def get_optimal_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_price: float,
        trade_type: str = 'long',
        category: str = 'default',
        correlation_group: Optional[str] = None,
        expected_volatility: Optional[float] = None,
        max_allowed_risk: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate optimal position size considering portfolio constraints.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_price: Stop-loss price
            trade_type: 'long' or 'short'
            category: Asset category
            correlation_group: Correlation group
            expected_volatility: Expected volatility
            max_allowed_risk: Maximum allowed risk for this trade
            
        Returns:
            Dictionary with position sizing recommendations
        """
        # Calculate stop distance as percentage
        if trade_type == 'long':
            stop_pct = (entry_price - stop_price) / entry_price
        else:
            stop_pct = (stop_price - entry_price) / entry_price
        
        # Ensure stop percentage is within bounds
        stop_pct = max(0.005, min(stop_pct, 0.2))
        
        # Calculate available risk based on portfolio state
        if max_allowed_risk is None:
            # Start with maximum portfolio risk
            available_risk_pct = self.max_portfolio_risk
            
            # Subtract existing risk
            existing_risk_pct = self.get_total_risk() / self.account_size
            available_risk_pct = max(0, available_risk_pct - existing_risk_pct)
            
            # Apply drawdown control if active
            if self.in_drawdown_control:
                available_risk_pct *= (1 - self.drawdown_risk_reduction)
            
            # Check category constraints
            if category in self.category_allocations:
                category_risk = sum(p['risk_amount'] for p in self.positions.values() 
                                   if p['category'] == category)
                category_risk_pct = category_risk / self.account_size
                
                category_available = max(0, self.max_category_allocation - category_risk_pct)
                available_risk_pct = min(available_risk_pct, category_available)
            
            # Check correlation group constraints
            if correlation_group and correlation_group in self.correlation_groups:
                corr_group_risk = self.correlation_groups[correlation_group]
                corr_risk_pct = corr_group_risk / self.account_size
                
                corr_available = max(0, self.max_correlation_risk - corr_risk_pct)
                available_risk_pct = min(available_risk_pct, corr_available)
            
            # Convert percentage to amount
            max_allowed_risk = available_risk_pct * self.account_size
        
        # Calculate position size based on risk
        position_value = max_allowed_risk / stop_pct
        position_size = position_value / entry_price
        
        # Check leverage constraints
        total_exposure = self.get_total_exposure() + position_value
        future_leverage = total_exposure / self.current_equity
        
        if self.leverage_control and future_leverage > self.max_leverage:
            # Scale down to meet leverage constraint
            excess_leverage = future_leverage - self.max_leverage
            leverage_reduction = excess_leverage / future_leverage
            
            position_value *= (1 - leverage_reduction)
            position_size *= (1 - leverage_reduction)
        
        # Calculate risk amount
        risk_amount = position_value * stop_pct
        
        # Return sizing recommendation
        return {
            'position_size': position_size,
            'position_value': position_value,
            'risk_amount': risk_amount,
            'risk_pct': risk_amount / self.account_size,
            'stop_pct': stop_pct,
            'available_risk': max_allowed_risk
        }
    
    def update_correlation_matrix(self, returns_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Update the correlation matrix between assets/strategies.
        
        Args:
            returns_data: Historical returns data (optional)
            
        Returns:
            Updated correlation matrix
        """
        # If returns data provided, use it
        if returns_data is not None and isinstance(returns_data, pd.DataFrame):
            self.correlation_matrix = returns_data.corr()
            return self.correlation_matrix
        
        # Otherwise, use stored returns data if available
        if len(self.returns_data) >= 10:  # Need reasonable amount of data
            returns_df = pd.DataFrame(self.returns_data).T
            self.correlation_matrix = returns_df.corr()
            
            # Update correlation groups based on matrix
            self._update_correlation_groups()
            
            return self.correlation_matrix
        
        # Not enough data
        logger.warning("Not enough return data to update correlation matrix")
        return pd.DataFrame()
    
    def _update_correlation_groups(self, correlation_threshold: float = 0.7) -> None:
        """
        Update correlation groups based on correlation matrix.
        
        Args:
            correlation_threshold: Threshold for high correlation
        """
        if self.correlation_matrix.empty:
            return
        
        # Get assets/strategies currently in positions
        active_symbols = list(self.positions.keys())
        
        # Filter correlation matrix to active symbols
        active_matrix = self.correlation_matrix.loc[
            self.correlation_matrix.index.isin(active_symbols),
            self.correlation_matrix.columns.isin(active_symbols)
        ]
        
        if active_matrix.empty:
            return
        
        # Identify highly correlated pairs
        for i in range(len(active_matrix.index)):
            symbol_i = active_matrix.index[i]
            if symbol_i not in self.positions:
                continue
            
            for j in range(i+1, len(active_matrix.columns)):
                symbol_j = active_matrix.columns[j]
                if symbol_j not in self.positions:
                    continue
                
                correlation = active_matrix.iloc[i, j]
                
                if abs(correlation) >= correlation_threshold:
                    # Create correlation group name if needed
                    group_name = f"corr_group_{i}_{j}"
                    
                    # Assign both positions to same group
                    if 'correlation_group' not in self.positions[symbol_i] or not self.positions[symbol_i]['correlation_group']:
                        self.positions[symbol_i]['correlation_group'] = group_name
                    
                    if 'correlation_group' not in self.positions[symbol_j] or not self.positions[symbol_j]['correlation_group']:
                        self.positions[symbol_j]['correlation_group'] = group_name
                    
                    # Update correlation groups
                    if group_name not in self.correlation_groups:
                        self.correlation_groups[group_name] = (
                            self.positions[symbol_i]['risk_amount'] + 
                            self.positions[symbol_j]['risk_amount']
                        )
    
    def optimize_portfolio_allocation(self) -> Dict[str, float]:
        """
        Optimize portfolio allocation using risk parity or other methods.
        
        Returns:
            Dictionary with optimal allocations by symbol
        """
        if not self.positions:
            return {}
        
        # Extract position data
        symbols = list(self.positions.keys())
        current_allocations = {s: self.positions[s]['value'] / self.current_equity 
                              for s in symbols}
        
        # Extract or estimate volatilities
        vols = {}
        for symbol, position in self.positions.items():
            if position['expected_volatility'] is not None:
                vols[symbol] = position['expected_volatility']
            else:
                # Use stop percentage as proxy for volatility
                vols[symbol] = position['stop_pct'] * np.sqrt(252)
        
        # Use correlation matrix if available, otherwise assume identity matrix
        if not self.correlation_matrix.empty:
            corr_matrix = self.correlation_matrix.loc[
                self.correlation_matrix.index.isin(symbols),
                self.correlation_matrix.columns.isin(symbols)
            ]
            
            # Ensure all symbols are in the matrix
            if not all(s in corr_matrix.index for s in symbols):
                # Default to identity matrix
                corr_matrix = pd.DataFrame(
                    np.eye(len(symbols)),
                    index=symbols,
                    columns=symbols
                )
        else:
            # Default to identity matrix
            corr_matrix = pd.DataFrame(
                np.eye(len(symbols)),
                index=symbols,
                columns=symbols
            )
        
        # Convert volatilities to series
        vol_series = pd.Series(vols)
        
        # Compute optimal allocation
        try:
            if self.risk_parity:
                # Set up allocator method
                self.allocator.set_method('hrp')
                
                # Compute risk parity allocation
                optimal_allocation = self.allocator.allocate(
                    corr_matrix=corr_matrix,
                    volatilities=vol_series,
                    target_volatility=self.target_volatility if self.volatility_targeting else None
                )
            else:
                # Equal risk allocation
                self.allocator.set_method('equal_risk')
                
                # Compute equal risk allocation
                optimal_allocation = self.allocator.allocate(
                    volatilities=vol_series,
                    target_volatility=self.target_volatility if self.volatility_targeting else None
                )
            
            return optimal_allocation
            
        except Exception as e:
            logger.error(f"Error in portfolio optimization: {str(e)}")
            # Fallback to current allocations
            return current_allocations
    
    def check_rebalance_needed(self) -> bool:
        """
        Check if portfolio rebalancing is needed based on deviation from target.
        
        Returns:
            True if rebalancing is needed, False otherwise
        """
        if not self.positions:
            return False
        
        # Get optimal allocation
        optimal_allocation = self.optimize_portfolio_allocation()
        
        # Get current allocation
        current_allocation = {
            symbol: position['value'] / self.current_equity
            for symbol, position in self.positions.items()
        }
        
        # Check for symbols that are in one but not the other
        all_symbols = set(list(optimal_allocation.keys()) + list(current_allocation.keys()))
        
        # Calculate maximum deviation
        max_deviation = 0
        for symbol in all_symbols:
            optimal = optimal_allocation.get(symbol, 0)
            current = current_allocation.get(symbol, 0)
            deviation = abs(optimal - current)
            max_deviation = max(max_deviation, deviation)
        
        # Need rebalance if maximum deviation exceeds threshold
        return max_deviation > self.rebalance_threshold
    
    def get_rebalance_trades(self) -> Dict[str, Dict[str, float]]:
        """
        Get recommended trades to rebalance the portfolio.
        
        Returns:
            Dictionary with symbols as keys and trade details as values
        """
        if not self.positions:
            return {}
        
        # Get optimal allocation
        optimal_allocation = self.optimize_portfolio_allocation()
        
        # Calculate target position values
        target_values = {
            symbol: self.current_equity * alloc
            for symbol, alloc in optimal_allocation.items()
        }
        
        # Calculate trades needed
        rebalance_trades = {}
        for symbol in set(list(self.positions.keys()) + list(target_values.keys())):
            current_value = self.positions[symbol]['value'] if symbol in self.positions else 0
            current_size = self.positions[symbol]['position_size'] if symbol in self.positions else 0
            target_value = target_values.get(symbol, 0)
            
            # Calculate trade size
            value_change = target_value - current_value
            
            # Only include if significant change
            if abs(value_change) / self.current_equity >= 0.005:  # 0.5% minimum change
                if symbol in self.positions:
                    price = self.positions[symbol]['current_price']
                    size_change = value_change / price
                    
                    rebalance_trades[symbol] = {
                        'current_value': current_value,
                        'current_size': current_size,
                        'target_value': target_value,
                        'target_size': current_size + size_change,
                        'value_change': value_change,
                        'size_change': size_change,
                        'price': price
                    }
                else:
                    # New position, need price input
                    rebalance_trades[symbol] = {
                        'current_value': 0,
                        'current_size': 0,
                        'target_value': target_value,
                        'target_size': None,  # Need price
                        'value_change': target_value,
                        'size_change': None,  # Need price
                        'price': None  # Need price input
                    }
        
        return rebalance_trades
    
    def generate_risk_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive risk report for the portfolio.
        
        Returns:
            Dictionary with detailed risk metrics
        """
        # Get basic portfolio state
        report = self.get_portfolio_state()
        
        # Add historical metrics
        report['historical'] = {
            'equity_curve': self.equity_curve.copy(),
            'drawdown_history': self.drawdown_history.copy(),
            'var_history': self.var_history.copy() if self.var_history else [],
            'cvar_history': self.cvar_history.copy() if self.cvar_history else []
        }
        
        # Add position metrics
        winning_positions = [p for p in self.positions.values() if p['pnl_amount'] > 0]
        losing_positions = [p for p in self.positions.values() if p['pnl_amount'] <= 0]
        
        report['position_analysis'] = {
            'total_positions': len(self.positions),
            'winning_positions': len(winning_positions),
            'losing_positions': len(losing_positions),
            'avg_win_pnl': np.mean([p['pnl_amount'] for p in winning_positions]) if winning_positions else 0,
            'avg_loss_pnl': np.mean([p['pnl_amount'] for p in losing_positions]) if losing_positions else 0,
            'largest_winner': max([p['pnl_amount'] for p in winning_positions]) if winning_positions else 0,
            'largest_loser': min([p['pnl_amount'] for p in losing_positions]) if losing_positions else 0
        }
        
        # Add correlation analysis
        if not self.correlation_matrix.empty:
            # Find highest correlations
            corr_matrix = self.correlation_matrix.copy()
            np.fill_diagonal(corr_matrix.values, 0)  # Remove self-correlations
            
            # Get highest absolute correlations
            high_corrs = []
            for i in range(len(corr_matrix.index)):
                for j in range(i+1, len(corr_matrix.columns)):
                    corr = corr_matrix.iloc[i, j]
                    if abs(corr) >= 0.5:  # Threshold for high correlation
                        high_corrs.append({
                            'symbol1': corr_matrix.index[i],
                            'symbol2': corr_matrix.columns[j],
                            'correlation': corr
                        })
            
            # Sort by absolute correlation
            high_corrs.sort(key=lambda x: abs(x['correlation']), reverse=True)
            
            report['correlation_analysis'] = {
                'high_correlations': high_corrs[:10],  # Top 10 highest correlations
                'correlation_matrix': self.correlation_matrix.to_dict()
            }
        
        # Add optimization results
        report['optimization'] = {
            'optimal_allocation': self.optimize_portfolio_allocation(),
            'rebalance_needed': self.check_rebalance_needed(),
            'rebalance_trades': self.get_rebalance_trades() if self.check_rebalance_needed() else {}
        }
        
        return report
    
    def plot_risk_allocation(self) -> plt.Figure:
        """
        Plot current risk allocation by category and correlation group.
        
        Returns:
            Matplotlib figure object
        """
        if not self.positions:
            logger.warning("No positions to plot risk allocation")
            return None
        
        # Calculate risk by category
        risk_by_category = {}
        for symbol, position in self.positions.items():
            category = position['category']
            if category not in risk_by_category:
                risk_by_category[category] = 0
            risk_by_category[category] += position['risk_amount']
        
        # Calculate risk by correlation group
        risk_by_group = {}
        for symbol, position in self.positions.items():
            group = position.get('correlation_group', 'Uncorrelated')
            if group not in risk_by_group:
                risk_by_group[group] = 0
            risk_by_group[group] += position['risk_amount']
        
        # Create figure with 2 rows, 2 columns
        fig, axs = plt.subplots(2, 2, figsize=(14, 12))
        
        # Plot risk by category - pie chart
        categories = list(risk_by_category.keys())
        values = [risk_by_category[cat] for cat in categories]
        
        axs[0, 0].pie(values, labels=categories, autopct='%1.1f%%', startangle=90)
        axs[0, 0].set_title('Risk Allocation by Category')
        
        # Plot risk by correlation group - pie chart
        groups = list(risk_by_group.keys())
        group_values = [risk_by_group[group] for group in groups]
        
        axs[0, 1].pie(group_values, labels=groups, autopct='%1.1f%%', startangle=90)
        axs[0, 1].set_title('Risk Allocation by Correlation Group')
        
        # Plot risk vs allocation by position - scatter plot
        symbols = list(self.positions.keys())
        allocations = [self.positions[s]['value'] / self.current_equity * 100 for s in symbols]
        risks = [self.positions[s]['risk_amount'] / self.current_equity * 100 for s in symbols]
        
        # Create category-based colors
        categories = [self.positions[s]['category'] for s in symbols]
        unique_categories = list(set(categories))
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_categories)))
        color_map = {cat: colors[i] for i, cat in enumerate(unique_categories)}
        point_colors = [color_map[cat] for cat in categories]
        
        scatter = axs[1, 0].scatter(allocations, risks, s=100, alpha=0.7, c=point_colors)
        
        # Add labels
        for i, symbol in enumerate(symbols):
            axs[1, 0].annotate(symbol, (allocations[i], risks[i]), 
                        xytext=(5, 5), textcoords='offset points')
        
        axs[1, 0].set_xlabel('Allocation (% of Portfolio)')
        axs[1, 0].set_ylabel('Risk (% of Portfolio)')
        axs[1, 0].set_title('Position Risk vs Allocation')
        axs[1, 0].grid(True, alpha=0.3)
        
        # Add legend
        legend_elements = [plt.Line2D([0], [0], marker='o', color='w', 
                                     label=cat, markerfacecolor=color_map[cat], 
                                     markersize=10) 
                          for cat in unique_categories]
        axs[1, 0].legend(handles=legend_elements, title="Categories")
        
        # Plot risk contribution vs expected return - scatter
        if any('expected_return' in position for position in self.positions.values()):
            returns = []
            for symbol in symbols:
                if 'expected_return' in self.positions[symbol]:
                    returns.append(self.positions[symbol]['expected_return'] * 100)  # Convert to percentage
                else:
                    returns.append(0)  # Default to zero if not available
                
            risk_contribution = [r / sum(risks) * 100 if sum(risks) > 0 else 0 for r in risks]
            
            axs[1, 1].scatter(risk_contribution, returns, s=100, alpha=0.7, c=point_colors)
            
            # Add labels
            for i, symbol in enumerate(symbols):
                axs[1, 1].annotate(symbol, (risk_contribution[i], returns[i]), 
                                 xytext=(5, 5), textcoords='offset points')
            
            axs[1, 1].set_xlabel('Risk Contribution (%)')
            axs[1, 1].set_ylabel('Expected Return (%)')
            axs[1, 1].set_title('Risk Contribution vs Expected Return')
            axs[1, 1].grid(True, alpha=0.3)
        else:
            axs[1, 1].text(0.5, 0.5, 'Expected return data not available', 
                         horizontalalignment='center', verticalalignment='center',
                         transform=axs[1, 1].transAxes)
        
        plt.tight_layout()
        return fig
        
    def plot_equity_curve(self, highlight_drawdowns: bool = True, drawdown_threshold: float = 0.05) -> plt.Figure:
        """
        Plot the equity curve with optional drawdown highlighting.
        
        Args:
            highlight_drawdowns: Whether to highlight drawdown periods
            drawdown_threshold: Minimum drawdown percentage to highlight
            
        Returns:
            Matplotlib figure object
        """
        if self.equity_curve is None or len(self.equity_curve) < 2:
            logger.warning("Insufficient equity data to plot equity curve")
            return None
        
        # Convert to DataFrame if it's a list
        if isinstance(self.equity_curve, list):
            equity_df = pd.DataFrame({
                'equity': [e['equity'] for e in self.equity_curve],
                'timestamp': [e['timestamp'] for e in self.equity_curve]
            })
            equity_df.set_index('timestamp', inplace=True)
            equity_series = equity_df['equity']
        else:
            equity_series = self.equity_curve
            
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot equity curve
        ax.plot(equity_series.index, equity_series.values, label='Portfolio Equity', linewidth=2)
        
        # Calculate and plot running maximum (high watermark)
        running_max = equity_series.cummax()
        ax.plot(running_max.index, running_max.values, 'k--', alpha=0.5, label='High Watermark')
        
        # Calculate drawdowns
        drawdowns = (equity_series / running_max - 1) * 100  # Convert to percentage
        
        # Highlight drawdown periods
        if highlight_drawdowns:
            # Find periods where drawdown exceeds threshold
            exceeded = drawdowns < -drawdown_threshold * 100  # Convert to percentage
            
            # Find start and end of each drawdown period
            in_drawdown = False
            drawdown_periods = []
            current_period = {'start': None, 'end': None}
            
            for i, (date, is_exceeded) in enumerate(exceeded.items()):
                if is_exceeded and not in_drawdown:
                    # Start of a drawdown period
                    in_drawdown = True
                    current_period['start'] = date
                elif not is_exceeded and in_drawdown:
                    # End of a drawdown period
                    in_drawdown = False
                    current_period['end'] = date
                    drawdown_periods.append(current_period)
                    current_period = {'start': None, 'end': None}
            
            # Handle case where we're still in a drawdown at the end
            if in_drawdown:
                current_period['end'] = exceeded.index[-1]
                drawdown_periods.append(current_period)
            
            # Highlight each drawdown period
            for period in drawdown_periods:
                start_idx = equity_series.index.get_loc(period['start'])
                end_idx = equity_series.index.get_loc(period['end'])
                
                # Get the equity values for this period
                x_range = equity_series.index[start_idx:end_idx+1]
                y_values = equity_series.iloc[start_idx:end_idx+1].values
                
                # Calculate drawdown depth
                period_min = equity_series.iloc[start_idx:end_idx+1].min()
                min_idx = equity_series.iloc[start_idx:end_idx+1].idxmin()
                min_loc = equity_series.index.get_loc(min_idx)
                hwm_at_min = running_max.iloc[min_loc]
                drawdown_pct = (period_min / hwm_at_min - 1) * 100
                
                # Highlight the drawdown period
                ax.fill_between(x_range, y_values, running_max.iloc[start_idx:end_idx+1].values,
                                alpha=0.3, color='red', 
                                label=f'Drawdown: {drawdown_pct:.1f}%' if period == drawdown_periods[0] else None)
        
        # Add second axis for drawdown percentage
        ax2 = ax.twinx()
        ax2.fill_between(drawdowns.index, 0, drawdowns.values, alpha=0.2, color='gray')
        ax2.set_ylabel('Drawdown %')
        ax2.set_ylim(min(drawdowns.min() * 1.5, -10), 5)  # Set y-limit with some margin
        
        # Format the plot
        ax.set_title('Portfolio Equity Curve with Drawdowns')
        ax.set_xlabel('Date')
        ax.set_ylabel('Portfolio Value')
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        # Add legend
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, loc='upper left')
        
        plt.tight_layout()
        return fig
        
    def plot_correlation_heatmap(self) -> plt.Figure:
        """
        Plot a heatmap of the correlation matrix for the current positions.
        
        Returns:
            Matplotlib figure object
        """
        if self.correlation_matrix is None or self.correlation_matrix.empty:
            logger.warning("Correlation matrix is empty, cannot plot heatmap")
            return None
            
        # Filter correlation matrix to include only current positions
        current_symbols = list(self.positions.keys())
        
        if not current_symbols:
            logger.warning("No active positions to plot correlation heatmap")
            return None
            
        # Check if all symbols are in the correlation matrix
        available_symbols = [s for s in current_symbols if s in self.correlation_matrix.index]
        
        if not available_symbols:
            logger.warning("None of the current positions are in the correlation matrix")
            return None
            
        # Extract the relevant subset of the correlation matrix
        corr_subset = self.correlation_matrix.loc[available_symbols, available_symbols]
        
        # Create the plot
        plt.figure(figsize=(10, 8))
        
        # Generate mask for the upper triangle
        mask = np.triu(np.ones_like(corr_subset, dtype=bool))
        
        # Set up the matplotlib figure
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Generate a custom diverging colormap
        cmap = sns.diverging_palette(230, 20, as_cmap=True)
        
        # Draw the heatmap with the mask and correct aspect ratio
        sns.heatmap(
            corr_subset, 
            mask=mask,
            cmap=cmap, 
            vmax=1.0, 
            vmin=-1.0,
            center=0,
            square=True, 
            linewidths=.5, 
            cbar_kws={"shrink": .8},
            annot=True,
            fmt=".2f"
        )
        
        plt.title('Correlation Heatmap of Portfolio Assets')
        plt.tight_layout()
        
        return fig
        
    def plot_risk_metrics(self) -> plt.Figure:
        """
        Plot the historical risk metrics (VaR and CVaR) over time.
        
        Returns:
            Matplotlib figure object
        """
        if not hasattr(self, 'var_history') or not self.var_history:
            logger.warning("No VaR history available to plot risk metrics")
            return None
            
        # Prepare the data
        if isinstance(self.var_history[0], dict):
            # Convert from dict format to lists
            var_values = [entry['value'] for entry in self.var_history]
            cvar_values = [entry['value'] for entry in self.cvar_history] if hasattr(self, 'cvar_history') else None
            dates = [entry['timestamp'] for entry in self.var_history]
        else:
            # Already in list format
            var_values = self.var_history
            cvar_values = self.cvar_history if hasattr(self, 'cvar_history') else None
            dates = None  # Use indices if dates are not available
            
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot VaR
        if dates:
            ax.plot(dates, var_values, 'b-', label='Value at Risk (VaR)', linewidth=2)
            if cvar_values:
                ax.plot(dates, cvar_values, 'r-', label='Conditional VaR (CVaR)', linewidth=2)
        else:
            ax.plot(var_values, 'b-', label='Value at Risk (VaR)', linewidth=2)
            if cvar_values:
                ax.plot(cvar_values, 'r-', label='Conditional VaR (CVaR)', linewidth=2)
                
        # Format the plot
        ax.set_title('Portfolio Risk Metrics Over Time')
        if dates:
            ax.set_xlabel('Date')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
        else:
            ax.set_xlabel('Trading Day')
            
        ax.set_ylabel('Risk (% of Portfolio)')
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.grid(True, alpha=0.3)
        
        # Set y-limits to focus on the relevant range
        max_risk = max(max(var_values), max(cvar_values) if cvar_values else 0)
        ax.set_ylim(0, min(max_risk * 1.2, 0.5))  # Cap at 50% for readability
        
        ax.legend()
        plt.tight_layout()
        
        return fig
        
    def plot_position_performance(self) -> plt.Figure:
        """
        Plot the performance of current positions.
        
        Returns:
            Matplotlib figure object
        """
        if not self.positions:
            logger.warning("No positions to plot performance")
            return None
            
        # Prepare data
        symbols = list(self.positions.keys())
        pnl_pcts = []
        risk_amounts = []
        holding_days = []
        categories = []
        trade_types = []
        
        current_time = datetime.now()
        
        for symbol in symbols:
            position = self.positions[symbol]
            
            # Calculate PnL percentage
            if position['trade_type'] == 'long':
                pnl_pct = (position['current_price'] / position['entry_price']) - 1
            else:
                pnl_pct = 1 - (position['current_price'] / position['entry_price'])
                
            pnl_pcts.append(pnl_pct * 100)  # Convert to percentage
            
            # Get risk amount as percentage of account
            risk_amounts.append(position['risk_amount'] / self.current_equity * 100)
            
            # Calculate holding period in days
            entry_time = position.get('entry_time', current_time)
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            holding_days.append((current_time - entry_time).days + 1)  # +1 to avoid 0 days
            
            # Store category and trade type
            categories.append(position['category'])
            trade_types.append(position['trade_type'])
            
        # Create category and trade type color mappings
        unique_categories = list(set(categories))
        category_colors = plt.cm.tab10(np.linspace(0, 1, len(unique_categories)))
        category_color_map = {cat: category_colors[i] for i, cat in enumerate(unique_categories)}
        
        trade_type_markers = {'long': 'o', 'short': 's'}
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create scatter plot with size proportional to risk and color by category
        for i, symbol in enumerate(symbols):
            marker = trade_type_markers.get(trade_types[i], 'o')
            ax.scatter(
                holding_days[i], 
                pnl_pcts[i], 
                s=risk_amounts[i] * 20,  # Size proportional to risk
                color=category_color_map[categories[i]],
                marker=marker,
                alpha=0.7,
                label=f"{symbol} ({categories[i]}, {trade_types[i]})"
            )
            
            # Add labels
            ax.annotate(
                symbol, 
                (holding_days[i], pnl_pcts[i]),
                xytext=(5, 5), 
                textcoords='offset points'
            )
            
        # Add horizontal line at y=0
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        # Format the plot
        ax.set_title('Position Performance')
        ax.set_xlabel('Holding Period (Days)')
        ax.set_ylabel('Profit/Loss (%)')
        ax.grid(True, alpha=0.3)
        
        # Create a custom legend
        category_legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color, markersize=10, label=cat)
            for cat, color in category_color_map.items()
        ]
        
        trade_type_legend_elements = [
            plt.Line2D([0], [0], marker=marker, color='black', markersize=10, label=trade_type)
            for trade_type, marker in trade_type_markers.items()
        ]
        
        # Add two legends
        ax.legend(handles=category_legend_elements, title='Categories', loc='upper left')
        ax.legend(handles=trade_type_legend_elements, title='Trade Types', loc='upper right')
        
        plt.tight_layout()
        return fig
        
    def plot_optimization_comparison(self, optimal_allocation: Dict[str, float] = None) -> plt.Figure:
        """
        Plot comparison between current allocation and optimal allocation.
        
        Args:
            optimal_allocation: Dictionary of optimal allocations {symbol: allocation}
                If None, will use the result of optimize_portfolio_allocation()
                
        Returns:
            Matplotlib figure object
        """
        if not self.positions:
            logger.warning("No positions to plot allocation comparison")
            return None
            
        # Get current allocation
        current_allocation = {
            symbol: position['value'] / self.current_equity
            for symbol, position in self.positions.items()
        }
        
        # Get optimal allocation if not provided
        if optimal_allocation is None:
            try:
                optimal_allocation = self.optimize_portfolio_allocation()
            except Exception as e:
                logger.warning(f"Failed to get optimal allocation: {str(e)}")
                return None
                
        # Ensure we're comparing the same assets
        symbols = sorted(set(current_allocation.keys()) & set(optimal_allocation.keys()))
        
        if not symbols:
            logger.warning("No overlapping symbols between current and optimal allocations")
            return None
            
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
        
        # Plot current allocation
        current_values = [current_allocation.get(symbol, 0) * 100 for symbol in symbols]
        ax1.bar(symbols, current_values)
        ax1.set_title('Current Allocation')
        ax1.set_ylabel('Allocation (%)')
        ax1.set_ylim(0, max(current_values) * 1.2)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # Plot optimal allocation
        optimal_values = [optimal_allocation.get(symbol, 0) * 100 for symbol in symbols]
        ax2.bar(symbols, optimal_values)
        ax2.set_title('Optimal Allocation')
        ax2.set_ylabel('Allocation (%)')
        ax2.set_ylim(0, max(optimal_values) * 1.2)
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        return fig 