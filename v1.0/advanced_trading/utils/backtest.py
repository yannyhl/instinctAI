"""
Backtesting Utility
-----------------
Provides the backtest class to run strategy simulations.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class Backtest:
    """
    Backtesting engine for evaluating trading strategies.
    
    Features:
    - Realistic simulation with transaction costs
    - Position tracking and portfolio valuation
    - Performance metrics calculation
    """
    
    def __init__(self, strategy, data: pd.DataFrame, initial_capital: float = 10000.0, 
               commission: float = 0.001, slippage: float = 0.0005):
        """
        Initialize the backtest.
        
        Args:
            strategy: Strategy instance with generate_signal method
            data: DataFrame with market data
            initial_capital: Initial capital
            commission: Commission rate (as a decimal)
            slippage: Slippage rate (as a decimal)
        """
        self.strategy = strategy
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
        # Initialize backtest state
        self.portfolio_value = initial_capital
        self.position_size = 0
        self.position_value = 0
        self.cash = initial_capital
        
        logger.info(f"Initialized backtest with {len(data)} data points and {initial_capital} initial capital")
    
    def run(self) -> pd.DataFrame:
        """
        Run the backtest simulation.
        
        Returns:
            DataFrame with backtest results
        """
        # Initialize results dataframe
        results = pd.DataFrame(index=self.data.index)
        results['close'] = self.data['close']
        results['returns'] = self.data['close'].pct_change()
        
        # Initialize portfolio tracking
        results['signal'] = 0
        results['position'] = 0
        results['portfolio_value'] = self.initial_capital
        results['cash'] = self.initial_capital
        results['position_value'] = 0
        results['trade_count'] = 0
        results['commission_paid'] = 0
        results['slippage_paid'] = 0
        results['trade_profit'] = 0
        
        # Track trades
        trades = []
        
        # Run simulation
        current_position = 0
        entry_price = 0
        entry_date = None
        
        logger.info("Starting backtest simulation")
        
        # Process each data point
        for i in range(len(self.data)):
            # Get all data up to the current point (including history)
            data_window = self.data.iloc[:i+1]
            
            # Skip if we don't have enough data for the strategy yet
            if i < self.strategy.sequence_length:
                results.iloc[i, results.columns.get_loc('portfolio_value')] = self.initial_capital
                continue
            
            # Generate signal
            signal = self.strategy.generate_signal(data_window)
            results.iloc[i, results.columns.get_loc('signal')] = signal
            
            # Current price
            current_price = self.data['close'].iloc[i]
            
            # Determine if we need to trade
            if (signal > 0 and current_position <= 0) or (signal < 0 and current_position >= 0):
                # Close existing position if any
                if current_position != 0:
                    # Calculate exit price with slippage
                    exit_price = current_price * (1 - self.slippage) if current_position > 0 else current_price * (1 + self.slippage)
                    
                    # Calculate position value
                    position_value = abs(current_position) * exit_price
                    
                    # Calculate commission
                    commission_amount = position_value * self.commission
                    
                    # Update cash (add position value, subtract commission)
                    self.cash += position_value - commission_amount
                    
                    # Record trade profit
                    if current_position > 0:
                        profit = (exit_price - entry_price) * current_position - commission_amount
                    else:  # Short position
                        profit = (entry_price - exit_price) * abs(current_position) - commission_amount
                    
                    results.iloc[i, results.columns.get_loc('trade_profit')] = profit
                    
                    # Add to trade history
                    trade = {
                        'entry_date': entry_date,
                        'exit_date': self.data.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'position': current_position,
                        'profit': profit,
                        'profit_pct': profit / (abs(current_position) * entry_price) * 100,
                        'duration': (self.data.index[i] - entry_date).days
                    }
                    trades.append(trade)
                    
                    # Reset position
                    current_position = 0
                    self.position_value = 0
                    
                    # Update commission paid
                    results.iloc[i, results.columns.get_loc('commission_paid')] = commission_amount
                    results.iloc[i, results.columns.get_loc('slippage_paid')] = position_value * self.slippage
                    results.iloc[i, results.columns.get_loc('trade_count')] += 1
                
                # Open new position if signal is not neutral
                if signal != 0:
                    # Calculate entry price with slippage
                    entry_price = current_price * (1 + self.slippage) if signal > 0 else current_price * (1 - self.slippage)
                    
                    # Calculate position size (use 95% of cash to leave room for fees)
                    available_cash = self.cash * 0.95
                    position_size = available_cash / entry_price
                    
                    # Set position direction
                    current_position = position_size if signal > 0 else -position_size
                    
                    # Calculate position value
                    position_value = abs(current_position) * entry_price
                    
                    # Calculate commission
                    commission_amount = position_value * self.commission
                    
                    # Update cash (subtract position value and commission)
                    self.cash -= (position_value + commission_amount)
                    self.position_value = position_value
                    
                    # Record entry
                    entry_date = self.data.index[i]
                    
                    # Update commission paid
                    results.iloc[i, results.columns.get_loc('commission_paid')] += commission_amount
                    results.iloc[i, results.columns.get_loc('slippage_paid')] += position_value * self.slippage
                    results.iloc[i, results.columns.get_loc('trade_count')] += 1
            
            # Update position value based on current price
            if current_position != 0:
                self.position_value = abs(current_position) * current_price
                
                # For short positions, calculate P&L differently
                if current_position < 0:
                    # Short profit = price decrease
                    position_pl = (entry_price - current_price) * abs(current_position)
                    self.position_value = abs(current_position) * entry_price + position_pl
            
            # Update portfolio value
            self.portfolio_value = self.cash + self.position_value
            
            # Record state
            results.iloc[i, results.columns.get_loc('position')] = current_position
            results.iloc[i, results.columns.get_loc('cash')] = self.cash
            results.iloc[i, results.columns.get_loc('position_value')] = self.position_value
            results.iloc[i, results.columns.get_loc('portfolio_value')] = self.portfolio_value
        
        # Close any open position at the end
        if current_position != 0:
            # Final price
            final_price = self.data['close'].iloc[-1]
            
            # Calculate exit price with slippage
            exit_price = final_price * (1 - self.slippage) if current_position > 0 else final_price * (1 + self.slippage)
            
            # Calculate position value
            position_value = abs(current_position) * exit_price
            
            # Calculate commission
            commission_amount = position_value * self.commission
            
            # Add to trade history
            if current_position > 0:
                profit = (exit_price - entry_price) * current_position - commission_amount
            else:  # Short position
                profit = (entry_price - exit_price) * abs(current_position) - commission_amount
                
            trade = {
                'entry_date': entry_date,
                'exit_date': self.data.index[-1],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position': current_position,
                'profit': profit,
                'profit_pct': profit / (abs(current_position) * entry_price) * 100,
                'duration': (self.data.index[-1] - entry_date).days
            }
            trades.append(trade)
        
        # Calculate strategy returns
        results['strategy_returns'] = results['portfolio_value'].pct_change()
        
        # Calculate cumulative returns
        results['cumulative_market_returns'] = (1 + results['returns']).cumprod() - 1
        results['cumulative_strategy_returns'] = (1 + results['strategy_returns']).cumprod() - 1
        
        # Calculate drawdowns
        results['peak'] = results['portfolio_value'].cummax()
        results['drawdown'] = (results['portfolio_value'] - results['peak']) / results['peak']
        
        # Create trade log DataFrame
        trade_log = pd.DataFrame(trades)
        
        # Add trade log to the results object
        results.attrs['trade_log'] = trade_log
        
        logger.info(f"Backtest completed with final portfolio value: {self.portfolio_value:.2f}")
        
        return results 