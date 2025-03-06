"""
Strategy Service

This module provides backend services for interacting with trading strategies.
"""

import os
import sys
import json
import time
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import core modules
from core import config_manager, metrics, logging as log_manager, tracing

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.strategy_service"})


def get_strategies() -> List[Dict[str, Any]]:
    """
    Get a list of all available strategies.
    
    Returns:
        List of strategy dictionaries
    """
    # In a real implementation, this would fetch data from the strategy manager
    # For now, return placeholder data
    return [
        {
            "id": "trend_following",
            "name": "Trend Following",
            "description": "Follows medium-term market trends using EMA crossovers",
            "active": True,
            "symbols": ["BTC/USD", "ETH/USD", "SOL/USD"],
            "category": "momentum",
            "parameters": {
                "fast_ema": 12,
                "slow_ema": 26,
                "signal_ema": 9,
                "risk_per_trade": 0.02
            },
            "performance": {
                "win_rate": 62.5,
                "profit_factor": 1.85,
                "sharpe_ratio": 1.62,
                "max_drawdown": 12.4
            },
            "last_signal": "2023-05-01 13:45:00"
        },
        {
            "id": "mean_reversion",
            "name": "Mean Reversion",
            "description": "Identifies overbought/oversold conditions with Bollinger Bands and RSI",
            "active": True,
            "symbols": ["BTC/USD", "ETH/USD", "DOT/USD"],
            "category": "mean_reversion",
            "parameters": {
                "bb_period": 20,
                "bb_std_dev": 2.0,
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "risk_per_trade": 0.015
            },
            "performance": {
                "win_rate": 55.8,
                "profit_factor": 1.62,
                "sharpe_ratio": 1.45,
                "max_drawdown": 8.7
            },
            "last_signal": "2023-05-01 10:30:00"
        },
        {
            "id": "breakout",
            "name": "Breakout Strategy",
            "description": "Identifies and trades breakouts from consolidation patterns",
            "active": False,
            "symbols": ["BTC/USD", "ETH/USD", "SOL/USD", "DOT/USD", "LTC/USD"],
            "category": "momentum",
            "parameters": {
                "lookback_period": 20,
                "volatility_threshold": 0.5,
                "volume_factor": 1.5,
                "risk_per_trade": 0.02
            },
            "performance": {
                "win_rate": 48.2,
                "profit_factor": 1.75,
                "sharpe_ratio": 1.38,
                "max_drawdown": 15.2
            },
            "last_signal": "2023-04-28 16:15:00"
        },
        {
            "id": "grid_trading",
            "name": "Grid Trading",
            "description": "Places buy and sell orders at set intervals in a price range",
            "active": True,
            "symbols": ["BTC/USD"],
            "category": "market_making",
            "parameters": {
                "upper_bound": 55000.0,
                "lower_bound": 45000.0,
                "grid_levels": 10,
                "amount_per_grid": 0.1
            },
            "performance": {
                "win_rate": 92.5,
                "profit_factor": 1.35,
                "sharpe_ratio": 1.22,
                "max_drawdown": 5.8
            },
            "last_signal": "2023-05-01 14:00:00"
        },
        {
            "id": "statistical_arbitrage",
            "name": "Statistical Arbitrage",
            "description": "Exploits price divergences between related assets",
            "active": True,
            "symbols": ["BTC/USD", "ETH/USD"],
            "category": "arbitrage",
            "parameters": {
                "z_score_threshold": 2.0,
                "lookback_period": 60,
                "max_holding_period": 48,
                "risk_per_trade": 0.025
            },
            "performance": {
                "win_rate": 68.5,
                "profit_factor": 1.92,
                "sharpe_ratio": 1.78,
                "max_drawdown": 10.2
            },
            "last_signal": "2023-05-01 12:45:00"
        }
    ]


def get_strategy(strategy_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific strategy.
    
    Args:
        strategy_id: ID of the strategy
        
    Returns:
        Strategy dictionary
    """
    # Get all strategies
    strategies = get_strategies()
    
    # Find the requested strategy
    for strategy in strategies:
        if strategy["id"] == strategy_id:
            # Add more detailed information for the specific request
            strategy["trades"] = get_strategy_trades(strategy_id, limit=10)
            strategy["signals"] = get_strategy_signals(strategy_id, limit=10)
            strategy["performance_history"] = get_strategy_performance_history(strategy_id)
            return strategy
    
    # Strategy not found
    return {"error": f"Strategy with ID '{strategy_id}' not found"}


def get_strategy_trades(strategy_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent trades executed by a strategy.
    
    Args:
        strategy_id: ID of the strategy
        limit: Maximum number of trades to return
        
    Returns:
        List of trade dictionaries
    """
    # In a real implementation, this would fetch data from the strategy manager
    # For now, generate placeholder data
    trades = []
    
    # Different trade patterns based on strategy type
    if strategy_id == "trend_following":
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        avg_win_rate = 0.625
        win_loss_pattern = [1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0]
    elif strategy_id == "mean_reversion":
        symbols = ["BTC/USD", "ETH/USD", "DOT/USD"]
        avg_win_rate = 0.558
        win_loss_pattern = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0]
    elif strategy_id == "breakout":
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD", "DOT/USD", "LTC/USD"]
        avg_win_rate = 0.482
        win_loss_pattern = [0, 1, 0, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0, 1]
    elif strategy_id == "grid_trading":
        symbols = ["BTC/USD"]
        avg_win_rate = 0.925
        win_loss_pattern = [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1]
    elif strategy_id == "statistical_arbitrage":
        symbols = ["BTC/USD", "ETH/USD"]
        avg_win_rate = 0.685
        win_loss_pattern = [1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1]
    else:
        symbols = ["BTC/USD"]
        avg_win_rate = 0.6
        win_loss_pattern = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1]
    
    # Generate trades
    for i in range(limit):
        timestamp = datetime.now() - timedelta(hours=i*4)
        symbol_idx = i % len(symbols)
        
        # Determine win/loss for this trade
        pattern_idx = i % len(win_loss_pattern)
        is_win = win_loss_pattern[pattern_idx] == 1
        
        # Base values
        if symbols[symbol_idx] == "BTC/USD":
            price = 50000.0 * (1 + (random.random() - 0.5) * 0.1)  # +/- 5%
            quantity = 0.5 * (1 + (random.random() - 0.5) * 0.2)  # +/- 10%
        elif symbols[symbol_idx] == "ETH/USD":
            price = 3500.0 * (1 + (random.random() - 0.5) * 0.1)  # +/- 5%
            quantity = 3.0 * (1 + (random.random() - 0.5) * 0.2)  # +/- 10%
        elif symbols[symbol_idx] == "SOL/USD":
            price = 120.0 * (1 + (random.random() - 0.5) * 0.1)  # +/- 5%
            quantity = 40.0 * (1 + (random.random() - 0.5) * 0.2)  # +/- 10%
        elif symbols[symbol_idx] == "DOT/USD":
            price = 22.0 * (1 + (random.random() - 0.5) * 0.1)  # +/- 5%
            quantity = 250.0 * (1 + (random.random() - 0.5) * 0.2)  # +/- 10%
        else:  # LTC/USD
            price = 175.0 * (1 + (random.random() - 0.5) * 0.1)  # +/- 5%
            quantity = 20.0 * (1 + (random.random() - 0.5) * 0.2)  # +/- 10%
        
        # Calculate trade value
        value = price * quantity
        
        # Determine profit/loss
        if is_win:
            profit_percent = random.uniform(0.5, 5.0)
            profit = value * profit_percent / 100
        else:
            profit_percent = -random.uniform(0.5, 3.0)  # Losses tend to be smaller than wins
            profit = value * profit_percent / 100
        
        # Add trade to list
        trades.append({
            "id": f"{strategy_id}-trade-{i+1}",
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbols[symbol_idx],
            "side": "buy" if i % 2 == 0 else "sell",
            "price": price,
            "quantity": quantity,
            "value": value,
            "profit_loss": profit,
            "profit_loss_percent": profit_percent,
            "status": "closed"
        })
    
    # Sort by timestamp (newest first)
    trades.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return trades


def get_strategy_signals(strategy_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent signals generated by a strategy.
    
    Args:
        strategy_id: ID of the strategy
        limit: Maximum number of signals to return
        
    Returns:
        List of signal dictionaries
    """
    # In a real implementation, this would fetch data from the strategy manager
    # For now, generate placeholder data
    signals = []
    
    # Different signal patterns based on strategy type
    if strategy_id == "trend_following":
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        signal_types = ["buy", "sell"]
        reason_templates = [
            "Fast EMA crossed above slow EMA",
            "Fast EMA crossed below slow EMA",
            "Price broke above resistance at {price}",
            "Price broke below support at {price}",
            "MACD histogram turned positive",
            "MACD histogram turned negative"
        ]
    elif strategy_id == "mean_reversion":
        symbols = ["BTC/USD", "ETH/USD", "DOT/USD"]
        signal_types = ["buy", "sell"]
        reason_templates = [
            "RSI below oversold threshold (30)",
            "RSI above overbought threshold (70)",
            "Price touched lower Bollinger Band",
            "Price touched upper Bollinger Band",
            "RSI divergence detected",
            "Price deviated {percent}% from 20-period MA"
        ]
    elif strategy_id == "breakout":
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD", "DOT/USD", "LTC/USD"]
        signal_types = ["buy", "sell"]
        reason_templates = [
            "Breakout from {period}-day consolidation",
            "Volume spike of {percent}% above average",
            "ATR increased by {percent}%",
            "Failed breakout, reverting to range",
            "Price closed outside of Bollinger Bands",
            "New {timeframe} high/low formed"
        ]
    elif strategy_id == "grid_trading":
        symbols = ["BTC/USD"]
        signal_types = ["buy", "sell"]
        reason_templates = [
            "Price hit grid level at {price}",
            "Grid rebalance triggered",
            "Upper grid boundary adjusted to {price}",
            "Lower grid boundary adjusted to {price}",
            "Grid density increased at {price} zone",
            "Grid level triggered by volatility spike"
        ]
    elif strategy_id == "statistical_arbitrage":
        symbols = ["BTC/USD", "ETH/USD"]
        signal_types = ["buy", "sell"]
        reason_templates = [
            "Z-score exceeded threshold (2.0)",
            "Pair correlation deviated from norm",
            "Mean reversion opportunity detected",
            "Spread widened to {percent}%",
            "Spread narrowed to {percent}%",
            "Cointegration test passed with p-value {value}"
        ]
    else:
        symbols = ["BTC/USD"]
        signal_types = ["buy", "sell"]
        reason_templates = [
            "Strategy condition met",
            "Technical indicator triggered",
            "Price movement detected",
            "Algorithm generated signal",
            "Pattern recognized",
            "Threshold crossed"
        ]
    
    # Generate signals
    for i in range(limit):
        timestamp = datetime.now() - timedelta(minutes=i*45)
        symbol_idx = i % len(symbols)
        signal_type_idx = i % len(signal_types)
        reason_template_idx = i % len(reason_templates)
        
        # Generate reason with placeholders filled
        reason = reason_templates[reason_template_idx]
        if "{price}" in reason:
            if symbols[symbol_idx] == "BTC/USD":
                price = round(random.uniform(48000, 52000), 2)
            elif symbols[symbol_idx] == "ETH/USD":
                price = round(random.uniform(3300, 3700), 2)
            elif symbols[symbol_idx] == "SOL/USD":
                price = round(random.uniform(110, 130), 2)
            elif symbols[symbol_idx] == "DOT/USD":
                price = round(random.uniform(20, 24), 2)
            else:  # LTC/USD
                price = round(random.uniform(165, 185), 2)
            reason = reason.replace("{price}", str(price))
        
        if "{percent}" in reason:
            percent = round(random.uniform(5, 25), 1)
            reason = reason.replace("{percent}", str(percent))
        
        if "{period}" in reason:
            period = random.choice([5, 10, 14, 20, 30])
            reason = reason.replace("{period}", str(period))
        
        if "{timeframe}" in reason:
            timeframe = random.choice(["hourly", "4-hour", "daily", "weekly"])
            reason = reason.replace("{timeframe}", timeframe)
        
        if "{value}" in reason:
            value = round(random.uniform(0.01, 0.05), 3)
            reason = reason.replace("{value}", str(value))
        
        # Add signal to list
        signals.append({
            "id": f"{strategy_id}-signal-{i+1}",
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbols[symbol_idx],
            "type": signal_types[signal_type_idx],
            "strength": random.randint(1, 10),  # Signal strength on a scale of 1-10
            "reason": reason,
            "executed": i < limit // 2  # First half of signals were executed
        })
    
    # Sort by timestamp (newest first)
    signals.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return signals


def get_strategy_performance_history(strategy_id: str, days: int = 90) -> List[Dict[str, Any]]:
    """
    Get historical performance data for a strategy.
    
    Args:
        strategy_id: ID of the strategy
        days: Number of days of history to return
        
    Returns:
        List of performance data points
    """
    # In a real implementation, this would fetch data from the strategy manager
    # For now, generate placeholder data
    history = []
    
    # Different performance patterns based on strategy type
    if strategy_id == "trend_following":
        base_return = 0.08  # 8% monthly return
        volatility = 0.2  # Medium volatility
    elif strategy_id == "mean_reversion":
        base_return = 0.06  # 6% monthly return
        volatility = 0.15  # Lower volatility
    elif strategy_id == "breakout":
        base_return = 0.1  # 10% monthly return
        volatility = 0.25  # Higher volatility
    elif strategy_id == "grid_trading":
        base_return = 0.05  # 5% monthly return
        volatility = 0.1  # Very low volatility
    elif strategy_id == "statistical_arbitrage":
        base_return = 0.07  # 7% monthly return
        volatility = 0.12  # Low volatility
    else:
        base_return = 0.06  # 6% monthly return
        volatility = 0.18  # Medium volatility
    
    # Generate daily performance data
    start_date = datetime.now() - timedelta(days=days)
    
    # Start with $10,000 portfolio value
    portfolio_value = 10000.0
    daily_return_rate = (1 + base_return) ** (1/30) - 1  # Convert monthly to daily return
    
    for day in range(days):
        date = start_date + timedelta(days=day)
        
        # Apply some randomness to daily return
        daily_return = daily_return_rate + (random.random() - 0.5) * volatility / 20
        
        # Update portfolio value
        portfolio_value *= (1 + daily_return)
        
        # Calculate metrics
        day_of_month = date.day
        if day > 29:  # For 30-day rolling metrics
            start_idx = max(0, day - 30)
            rolling_return = portfolio_value / 10000.0 * (1 + daily_return_rate) ** start_idx - 1
            sharpe = rolling_return / (volatility * (30/365) ** 0.5)
        else:
            rolling_return = daily_return * day
            sharpe = 0
        
        # Add to history
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "portfolio_value": round(portfolio_value, 2),
            "daily_return": round(daily_return * 100, 2),
            "rolling_return_30d": round(rolling_return * 100, 2) if day >= 29 else None,
            "sharpe_ratio": round(sharpe, 2) if day >= 29 else None,
            "trades": random.randint(0, 5)  # 0-5 trades per day
        })
    
    return history


def get_strategy_parameters(strategy_id: str) -> Dict[str, Any]:
    """
    Get the parameters for a specific strategy.
    
    Args:
        strategy_id: ID of the strategy
        
    Returns:
        Dictionary of strategy parameters
    """
    # Get the strategy
    strategy = get_strategy(strategy_id)
    
    # Return the parameters
    return strategy.get("parameters", {})


def update_strategy_parameters(strategy_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update the parameters for a specific strategy.
    
    Args:
        strategy_id: ID of the strategy
        parameters: New parameter values
        
    Returns:
        Success status and message
    """
    logger.info(f"Updating parameters for strategy {strategy_id}: {parameters}")
    
    # In a real implementation, this would update the strategy parameters
    # For now, return success message
    return {
        "success": True, 
        "message": f"Parameters for strategy '{strategy_id}' updated successfully",
        "strategy_id": strategy_id,
        "parameters": parameters
    }


def toggle_strategy(strategy_id: str, active: bool) -> Dict[str, Any]:
    """
    Toggle a strategy active/inactive.
    
    Args:
        strategy_id: ID of the strategy
        active: Whether the strategy should be active
        
    Returns:
        Success status and message
    """
    status = "activated" if active else "deactivated"
    logger.info(f"{status} strategy {strategy_id}")
    
    # In a real implementation, this would update the strategy status
    # For now, return success message
    return {
        "success": True, 
        "message": f"Strategy '{strategy_id}' {status} successfully",
        "strategy_id": strategy_id,
        "active": active
    }


def add_strategy(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new strategy.
    
    Args:
        data: Strategy data
        
    Returns:
        Success status and message
    """
    logger.info(f"Adding new strategy: {data}")
    
    # In a real implementation, this would add a new strategy
    # For now, return success message with generated ID
    strategy_id = f"strategy_{int(time.time())}"
    
    return {
        "success": True, 
        "message": f"Strategy '{data.get('name', 'New Strategy')}' added successfully",
        "strategy_id": strategy_id
    }


def delete_strategy(strategy_id: str) -> Dict[str, Any]:
    """
    Delete a strategy.
    
    Args:
        strategy_id: ID of the strategy
        
    Returns:
        Success status and message
    """
    logger.info(f"Deleting strategy {strategy_id}")
    
    # In a real implementation, this would delete the strategy
    # For now, return success message
    return {
        "success": True, 
        "message": f"Strategy '{strategy_id}' deleted successfully",
        "strategy_id": strategy_id
    }


def run_backtest(strategy_id: str, parameters: Optional[Dict[str, Any]] = None, 
                start_date: Optional[str] = None, end_date: Optional[str] = None,
                symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Run a backtest for a strategy.
    
    Args:
        strategy_id: ID of the strategy
        parameters: Optional parameters to override strategy parameters
        start_date: Start date for backtest (ISO format)
        end_date: End date for backtest (ISO format)
        symbols: Optional list of symbols to backtest on
        
    Returns:
        Backtest results
    """
    logger.info(f"Running backtest for strategy {strategy_id}")
    
    # In a real implementation, this would run a backtest
    # For now, return placeholder results
    
    # Generate random backtest results
    if strategy_id == "trend_following":
        total_return = random.uniform(8, 15)
        max_drawdown = random.uniform(5, 15)
        win_rate = random.uniform(55, 65)
    elif strategy_id == "mean_reversion":
        total_return = random.uniform(5, 12)
        max_drawdown = random.uniform(3, 10)
        win_rate = random.uniform(50, 60)
    elif strategy_id == "breakout":
        total_return = random.uniform(10, 20)
        max_drawdown = random.uniform(8, 18)
        win_rate = random.uniform(45, 55)
    elif strategy_id == "grid_trading":
        total_return = random.uniform(4, 8)
        max_drawdown = random.uniform(2, 6)
        win_rate = random.uniform(85, 95)
    elif strategy_id == "statistical_arbitrage":
        total_return = random.uniform(6, 14)
        max_drawdown = random.uniform(4, 12)
        win_rate = random.uniform(60, 70)
    else:
        total_return = random.uniform(6, 12)
        max_drawdown = random.uniform(5, 15)
        win_rate = random.uniform(50, 65)
    
    # Calculate additional metrics
    profit_factor = 1 + total_return / 100
    sharpe_ratio = total_return / (max_drawdown * 0.5)
    
    # Default timeframe if not provided
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Generate daily equity curve
    start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
    end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end_datetime - start_datetime).days
    
    equity_curve = []
    start_equity = 10000.0
    current_equity = start_equity
    
    # Generate equity curve with a drawdown period
    drawdown_start = days // 3
    drawdown_end = drawdown_start + days // 6
    
    for day in range(days):
        date = start_datetime + timedelta(days=day)
        
        # Apply different return patterns for different phases
        if day < drawdown_start:
            # Growth phase
            daily_return = (1 + total_return/100) ** (1/days) - 1 + (random.random() - 0.3) * 0.005
        elif day < drawdown_end:
            # Drawdown phase
            daily_return = -max_drawdown/100/drawdown_end + (random.random() - 0.7) * 0.01
        else:
            # Recovery phase
            daily_return = (1 + total_return/100) ** (1/days) - 1 + (random.random() - 0.4) * 0.006
        
        # Update equity
        current_equity *= (1 + daily_return)
        
        equity_curve.append({
            "date": date.strftime("%Y-%m-%d"),
            "equity": round(current_equity, 2)
        })
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "start_date": start_date,
        "end_date": end_date,
        "parameters": parameters or get_strategy_parameters(strategy_id),
        "symbols": symbols or get_strategy(strategy_id).get("symbols", []),
        "results": {
            "total_return": round(total_return, 2),
            "annualized_return": round(total_return * 365 / days, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "trades": random.randint(50, 500),
            "equity_curve": equity_curve
        }
    } 