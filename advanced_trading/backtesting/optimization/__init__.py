"""
Strategy Optimization Module
---------------------------
This module provides tools for optimizing trading strategies and testing their robustness
under various market conditions. It includes parameter optimization, scenario testing,
Monte Carlo simulation, and performance visualization.

Key components:
1. Strategy Optimizer - Parameter optimization using various methods (grid search, random search, etc.)
2. Scenario Testing - Testing strategies under different market conditions
3. Monte Carlo Simulation - Assessing strategy robustness through randomized scenarios
4. Visualization - Tools for visualizing optimization results and performance across scenarios
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import key components
try:
    # Optimizer components
    from advanced_trading.backtesting.optimization.optimizer import (
        StrategyOptimizer, OptimizerConfig, OptimizationResult,
        OptimizationMetric, OptimizationMethod, OptimizationCallback, ProgressCallback
    )
    
    # Scenario testing components
    from advanced_trading.backtesting.optimization.scenario_testing import (
        ScenarioTester, ScenarioConfig, ScenarioResult, ScenarioTestResult, ScenarioType
    )
    
    __all__ = [
        'StrategyOptimizer',
        'OptimizerConfig',
        'OptimizationResult',
        'OptimizationMetric',
        'OptimizationMethod',
        'OptimizationCallback',
        'ProgressCallback',
        'ScenarioTester',
        'ScenarioConfig',
        'ScenarioResult',
        'ScenarioTestResult',
        'ScenarioType'
    ]
    
    logger.info("Optimization module loaded successfully")
except ImportError as e:
    logger.error(f"Error loading optimization module: {e}")
    
    # Define minimal API to prevent errors
    __all__ = []

# Version information
__version__ = '0.1.0' 