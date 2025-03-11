"""
Risk Stress Testing Module
-----------------------
Implements stress testing scenarios for trading strategies to evaluate performance
under extreme market conditions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json
import matplotlib.pyplot as plt
import os

# Set up logging
logger = logging.getLogger(__name__)

def default_stress_scenarios() -> Dict[str, Dict[str, Union[str, float]]]:
    """
    Define default stress testing scenarios.
    
    Returns:
        Dictionary of named scenarios with their parameters
    """
    scenarios = {
        "market_crash": {
            "description": "Sudden market crash (2008 style)",
            "price_shock": -0.30,  # 30% drop
            "volatility_multiplier": 3.0,
            "correlation_adjustment": 0.8,  # Higher correlation in crash
            "volume_multiplier": 2.5,
            "duration_days": 10
        },
        "flash_crash": {
            "description": "Flash crash with quick recovery",
            "price_shock": -0.15,  # 15% drop
            "volatility_multiplier": 5.0,
            "correlation_adjustment": 0.9,
            "volume_multiplier": 4.0,
            "duration_days": 2
        },
        "liquidity_crisis": {
            "description": "Market-wide liquidity crisis",
            "price_shock": -0.10,
            "volatility_multiplier": 2.0,
            "spread_multiplier": 5.0,  # Wider spreads
            "volume_multiplier": 0.3,  # Low volume
            "duration_days": 15
        },
        "sustained_bear": {
            "description": "Sustained bear market",
            "price_shock": -0.05,  # Initial 5% drop
            "trend_per_day": -0.01,  # Continued 1% daily drop
            "volatility_multiplier": 1.8,
            "volume_multiplier": 0.7,
            "duration_days": 60
        },
        "volatility_explosion": {
            "description": "Extreme volatility with no clear direction",
            "price_shock": 0.0,
            "volatility_multiplier": 4.0,
            "daily_noise": 0.08,  # 8% daily movement in random direction
            "volume_multiplier": 2.0,
            "duration_days": 20
        },
        "correlation_breakdown": {
            "description": "Typical correlations break down",
            "correlation_randomizer": True,
            "volatility_multiplier": 2.5,
            "volume_multiplier": 1.5,
            "duration_days": 15
        },
        "crypto_winter": {
            "description": "Extended crypto bear market",
            "price_shock": -0.20,
            "trend_per_day": -0.005,  # 0.5% daily drop
            "volatility_multiplier": 1.2,
            "volume_multiplier": 0.4,
            "duration_days": 90
        },
        "regulatory_shock": {
            "description": "Sudden regulatory crackdown",
            "price_shock": -0.25,
            "volatility_multiplier": 2.5,
            "volume_multiplier": 3.0,
            "duration_days": 5,
            "followed_by": {
                "trend_per_day": -0.003,
                "duration_days": 30
            }
        }
    }
    
    return scenarios

def generate_stress_scenario(
    data: pd.DataFrame,
    scenario: Dict[str, Any]
) -> pd.DataFrame:
    """
    Generate a stress scenario based on original market data.
    
    Args:
        data: Original market data DataFrame with OHLCV data
        scenario: Scenario parameters
        
    Returns:
        DataFrame with modified data representing the stress scenario
    """
    # Create a copy to avoid modifying the original data
    stressed_data = data.copy()
    
    # Apply initial price shock if specified
    if "price_shock" in scenario and scenario["price_shock"] != 0:
        shock_factor = 1.0 + scenario["price_shock"]
        stressed_data["open"] *= shock_factor
        stressed_data["high"] *= shock_factor
        stressed_data["low"] *= shock_factor
        stressed_data["close"] *= shock_factor
    
    # Apply volatility adjustment if specified
    if "volatility_multiplier" in scenario and scenario["volatility_multiplier"] != 1.0:
        volatility_factor = scenario["volatility_multiplier"]
        
        # Calculate price ranges and adjust
        original_range = data["high"] - data["low"]
        new_range = original_range * volatility_factor
        
        # Expand ranges around the close price
        mid_prices = stressed_data["close"]
        half_range = new_range / 2
        
        stressed_data["high"] = mid_prices + half_range
        stressed_data["low"] = mid_prices - half_range
        
        # Ensure open is within the new range
        stressed_data["open"] = np.clip(
            stressed_data["open"], 
            stressed_data["low"], 
            stressed_data["high"]
        )
    
    # Apply volume adjustments
    if "volume_multiplier" in scenario:
        stressed_data["volume"] *= scenario["volume_multiplier"]
    
    # Apply trend if specified
    if "trend_per_day" in scenario:
        days = np.arange(len(stressed_data))
        trend_factors = 1.0 + (days * scenario["trend_per_day"])
        
        stressed_data["open"] *= trend_factors
        stressed_data["high"] *= trend_factors
        stressed_data["low"] *= trend_factors
        stressed_data["close"] *= trend_factors
    
    # Apply random noise for high volatility scenarios
    if "daily_noise" in scenario:
        noise_magnitude = scenario["daily_noise"]
        random_factors = 1.0 + np.random.uniform(-noise_magnitude, noise_magnitude, len(stressed_data))
        
        stressed_data["open"] *= random_factors
        stressed_data["high"] *= random_factors
        stressed_data["low"] *= random_factors
        stressed_data["close"] *= random_factors
    
    # Ensure data consistency (high >= open, close, low and low <= open, close, high)
    for i in range(len(stressed_data)):
        highest = max(stressed_data.loc[stressed_data.index[i], "open"], 
                      stressed_data.loc[stressed_data.index[i], "close"])
        lowest = min(stressed_data.loc[stressed_data.index[i], "open"], 
                     stressed_data.loc[stressed_data.index[i], "close"])
        
        stressed_data.loc[stressed_data.index[i], "high"] = max(highest, stressed_data.loc[stressed_data.index[i], "high"])
        stressed_data.loc[stressed_data.index[i], "low"] = min(lowest, stressed_data.loc[stressed_data.index[i], "low"])
    
    # Calculate returns for reference
    stressed_data["returns"] = stressed_data["close"].pct_change()
    
    logger.info(f"Generated stress scenario: {scenario.get('description', 'Custom scenario')}")
    return stressed_data

def perform_stress_testing(
    strategy: Any,
    data_dict: Dict[str, pd.DataFrame],
    scenarios: Dict[str, Dict] = None,
    duration_days: int = None
) -> Dict[str, Dict]:
    """
    Perform stress testing on a strategy using various scenarios.
    
    Args:
        strategy: Strategy instance to test
        data_dict: Dictionary of data frames by symbol
        scenarios: Dictionary of stress scenarios (uses defaults if None)
        duration_days: Override scenario duration (if specified)
        
    Returns:
        Dictionary of test results by scenario
    """
    if scenarios is None:
        scenarios = default_stress_scenarios()
    
    results = {}
    
    # Test each scenario
    for scenario_name, scenario_params in scenarios.items():
        logger.info(f"Testing scenario: {scenario_name}")
        
        # Override duration if specified
        if duration_days is not None:
            scenario_params = scenario_params.copy()
            scenario_params["duration_days"] = duration_days
        
        # Create stressed data for each symbol
        stressed_data = {}
        
        for symbol, original_data in data_dict.items():
            # Use duration_days to limit the test data size
            test_duration = scenario_params.get("duration_days", 30)
            test_data = original_data.iloc[-test_duration:].copy() if len(original_data) > test_duration else original_data.copy()
            
            # Generate stressed data
            stressed_data[symbol] = generate_stress_scenario(test_data, scenario_params)
        
        # Run backtest on stressed data
        try:
            if hasattr(strategy, 'backtest'):
                # If strategy has a backtest method, use it directly
                scenario_results = strategy.backtest(stressed_data)
            else:
                # Otherwise try to create a basic backtest
                from utils.backtest import Backtest
                backtest = Backtest(strategy=strategy, data=next(iter(stressed_data.values())))
                scenario_results = backtest.run()
            
            # Calculate performance metrics
            if isinstance(scenario_results, pd.DataFrame):
                performance = calculate_stress_performance(scenario_results)
            elif isinstance(scenario_results, dict) and 'portfolio_value' in scenario_results:
                performance = calculate_stress_performance(scenario_results['portfolio_value'])
            else:
                performance = {"error": "Invalid backtest results format"}
                
            results[scenario_name] = {
                "description": scenario_params.get("description", ""),
                "performance": performance,
                "data_summary": {
                    "start_date": min(data.index[0] for data in stressed_data.values()),
                    "end_date": max(data.index[-1] for data in stressed_data.values()),
                    "symbols": list(stressed_data.keys())
                }
            }
            
        except Exception as e:
            logger.error(f"Error in stress test for scenario {scenario_name}: {str(e)}")
            results[scenario_name] = {
                "description": scenario_params.get("description", ""),
                "error": str(e)
            }
    
    return results

def calculate_stress_performance(results: Union[pd.DataFrame, pd.Series]) -> Dict[str, float]:
    """
    Calculate performance metrics from stress test results.
    
    Args:
        results: DataFrame with portfolio values or Series of portfolio values
        
    Returns:
        Dictionary of performance metrics
    """
    # Handle different input formats
    if isinstance(results, pd.DataFrame):
        if 'portfolio_value' in results.columns:
            portfolio_values = results['portfolio_value']
        elif 'close' in results.columns:
            portfolio_values = results['close']
        else:
            portfolio_values = results.iloc[:, 0]  # Use first column
    else:
        portfolio_values = results
    
    # Calculate basic metrics
    initial_value = portfolio_values.iloc[0]
    final_value = portfolio_values.iloc[-1]
    total_return = (final_value / initial_value - 1) * 100
    
    # Calculate returns
    returns = portfolio_values.pct_change().dropna()
    
    # Annualized metrics (scaled based on length of test)
    trading_days = len(returns)
    annual_factor = 252 / trading_days if trading_days > 0 else 1
    
    volatility = returns.std() * np.sqrt(252) * 100  # Annualized, in percent
    
    # Calculate drawdown
    peak = portfolio_values.expanding().max()
    drawdown = ((portfolio_values / peak) - 1) * 100
    max_drawdown = drawdown.min()
    
    # Calculate Sharpe ratio (assuming 0% risk-free rate for simplicity)
    mean_return = returns.mean()
    sharpe_ratio = (mean_return / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    
    # Recovery analysis
    if max_drawdown < 0:
        # Find the peak before the max drawdown
        max_dd_idx = drawdown.idxmin()
        peak_idx = peak.loc[:max_dd_idx].idxmax()
        
        # Check if recovery happened
        post_dd_values = portfolio_values.loc[max_dd_idx:]
        if any(value >= portfolio_values.loc[peak_idx] for value in post_dd_values):
            # Find recovery point
            recovery_idx = post_dd_values[post_dd_values >= portfolio_values.loc[peak_idx]].index[0]
            recovery_days = (recovery_idx - max_dd_idx).days
        else:
            recovery_days = -1  # No recovery
    else:
        recovery_days = 0  # No drawdown
    
    # Compile results
    metrics = {
        "total_return": float(total_return),
        "annualized_return": float(total_return * annual_factor),
        "volatility": float(volatility),
        "max_drawdown": float(max_drawdown),
        "sharpe_ratio": float(sharpe_ratio),
        "recovery_days": int(recovery_days) if isinstance(recovery_days, (int, float)) else recovery_days,
        "worst_daily_loss": float(returns.min() * 100),
        "best_daily_gain": float(returns.max() * 100)
    }
    
    return metrics

def visualize_stress_test_results(
    results: Dict[str, Dict],
    output_dir: Optional[Path] = None
) -> plt.Figure:
    """
    Visualize stress test results.
    
    Args:
        results: Dictionary of stress test results
        output_dir: Output directory for saving visualization
        
    Returns:
        Matplotlib figure
    """
    # Create figure
    fig = plt.figure(figsize=(12, 10))
    
    # Extract performance metrics for each scenario
    scenarios = []
    returns = []
    drawdowns = []
    volatilities = []
    
    for scenario_name, scenario_results in results.items():
        if "performance" in scenario_results and not isinstance(scenario_results["performance"], str):
            perf = scenario_results["performance"]
            
            scenarios.append(scenario_name)
            returns.append(perf.get("total_return", 0))
            drawdowns.append(abs(perf.get("max_drawdown", 0)))  # Make positive for visualization
            volatilities.append(perf.get("volatility", 0))
    
    # Create bar chart of returns
    ax1 = plt.subplot(3, 1, 1)
    ax1.bar(scenarios, returns, color=['green' if r > 0 else 'red' for r in returns])
    ax1.set_title('Total Returns by Scenario')
    ax1.set_ylabel('Return (%)')
    ax1.set_xticklabels([])  # Hide x labels for top plot
    ax1.grid(axis='y', alpha=0.3)
    
    # Add return values as text
    for i, r in enumerate(returns):
        ax1.text(i, r + (5 if r >= 0 else -5), f"{r:.1f}%", ha='center', va='center' if r >= 0 else 'top')
    
    # Create bar chart of drawdowns
    ax2 = plt.subplot(3, 1, 2)
    ax2.bar(scenarios, drawdowns, color='red', alpha=0.7)
    ax2.set_title('Maximum Drawdowns by Scenario')
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xticklabels([])  # Hide x labels for middle plot
    ax2.grid(axis='y', alpha=0.3)
    
    # Add drawdown values as text
    for i, d in enumerate(drawdowns):
        ax2.text(i, d + 1, f"{d:.1f}%", ha='center', va='bottom')
    
    # Create bar chart of volatilities
    ax3 = plt.subplot(3, 1, 3)
    ax3.bar(scenarios, volatilities, color='blue', alpha=0.7)
    ax3.set_title('Volatility by Scenario')
    ax3.set_ylabel('Volatility (%)')
    ax3.set_xticklabels(scenarios, rotation=45, ha='right')
    ax3.grid(axis='y', alpha=0.3)
    
    # Add volatility values as text
    for i, v in enumerate(volatilities):
        ax3.text(i, v + 1, f"{v:.1f}%", ha='center', va='bottom')
    
    plt.tight_layout()
    
    # Save figure if output directory is provided
    if output_dir is not None:
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(output_dir / 'stress_test_results.png', dpi=300, bbox_inches='tight')
    
    return fig 