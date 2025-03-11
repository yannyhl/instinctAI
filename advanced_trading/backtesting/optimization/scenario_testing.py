"""
Scenario Testing Module
----------------------
This module provides tools for testing trading strategies under various market scenarios.
It enables simulation of different market conditions to assess strategy robustness and
identify potential weaknesses under stress conditions.

Key features:
1. Pre-defined market scenarios (bull, bear, sideways, volatile, etc.)
2. Custom scenario creation with specific market characteristics
3. Monte Carlo simulation for risk assessment
4. Stress testing under extreme market conditions
5. Statistical analysis of scenario test results
6. Visualization of strategy performance across scenarios
"""

import datetime
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple, Callable, Optional, Union, Any, Type, Set

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

# Import our modules
from advanced_trading.core.observability import get_logger
from advanced_trading.strategies.base import Strategy, StrategyConfig
from advanced_trading.backtesting.engine.backtest import Backtest, BacktestConfig, BacktestResult

# Initialize logger
logger = get_logger(__name__)


class ScenarioType(Enum):
    """Types of market scenarios that can be simulated for testing."""
    BULL_MARKET = "bull_market"
    BEAR_MARKET = "bear_market"
    SIDEWAYS_MARKET = "sideways_market"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    MARKET_CRASH = "market_crash"
    MARKET_RALLY = "market_rally"
    REGIME_CHANGE = "regime_change"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    FLASH_CRASH = "flash_crash"
    CUSTOM = "custom"


@dataclass
class ScenarioConfig:
    """
    Configuration for a market scenario test.
    
    Attributes:
        name: Name of the scenario
        scenario_type: Type of scenario (from ScenarioType enum)
        parameters: Specific parameters for the scenario
        description: Description of the scenario
        base_data: Base market data to apply transformations to
        data_transformation: Function to transform market data for this scenario
        duration: Duration of the scenario in days
        probability: Probability of this scenario occurring (for Monte Carlo)
    """
    name: str
    scenario_type: ScenarioType
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    base_data: Optional[Dict[str, pd.DataFrame]] = None
    data_transformation: Optional[Callable[[Dict[str, pd.DataFrame], Dict[str, Any]], Dict[str, pd.DataFrame]]] = None
    duration: int = 252  # Default to ~1 year of trading days
    probability: float = 0.1  # Default probability for Monte Carlo


@dataclass
class ScenarioResult:
    """
    Results of a scenario test.
    
    Attributes:
        scenario_config: Configuration used for the scenario
        backtest_result: Results of the backtest under this scenario
        performance_metrics: Performance metrics under this scenario
        scenario_data: Market data used for this scenario
        drawdowns: Drawdowns during the scenario
        volatility: Volatility during the scenario
        recovery_time: Time to recover from drawdowns
        stress_metrics: Metrics specifically measuring stress resilience
    """
    scenario_config: ScenarioConfig
    backtest_result: BacktestResult
    performance_metrics: Dict[str, float]
    scenario_data: Dict[str, pd.DataFrame]
    drawdowns: List[float] = field(default_factory=list)
    volatility: float = 0.0
    recovery_time: Optional[int] = None
    stress_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ScenarioTestResult:
    """
    Aggregated results of multiple scenario tests.
    
    Attributes:
        scenario_results: Results for each individual scenario
        strategy_name: Name of the strategy tested
        strategy_config: Configuration of the strategy
        overall_metrics: Aggregated metrics across all scenarios
        worst_case: Worst-case scenario and its metrics
        best_case: Best-case scenario and its metrics
        probability_weighted_metrics: Metrics weighted by scenario probabilities
        monte_carlo_metrics: Metrics from Monte Carlo simulation (if performed)
    """
    scenario_results: Dict[str, ScenarioResult]
    strategy_name: str
    strategy_config: StrategyConfig
    overall_metrics: Dict[str, float] = field(default_factory=dict)
    worst_case: Optional[Tuple[str, Dict[str, float]]] = None
    best_case: Optional[Tuple[str, Dict[str, float]]] = None
    probability_weighted_metrics: Dict[str, float] = field(default_factory=dict)
    monte_carlo_metrics: Dict[str, Any] = field(default_factory=dict)


class ScenarioTester:
    """
    Scenario tester for evaluating strategy performance under different market conditions.
    
    This class provides methods for generating market scenarios, running backtests under
    these scenarios, and analyzing the results to assess strategy robustness.
    
    Attributes:
        strategy_class: Strategy class to test
        strategy_config: Configuration for the strategy
        base_market_data: Base market data to apply scenario transformations to
        scenarios: Dictionary of scenario configurations by name
    """
    
    def __init__(self,
                strategy_class: Type[Strategy],
                strategy_config: StrategyConfig,
                base_market_data: Dict[str, pd.DataFrame],
                scenarios: Optional[Dict[str, ScenarioConfig]] = None):
        """
        Initialize the scenario tester.
        
        Args:
            strategy_class: Strategy class to test
            strategy_config: Configuration for the strategy
            base_market_data: Base market data to apply scenario transformations to
            scenarios: Optional dictionary of scenario configurations by name
        """
        self.strategy_class = strategy_class
        self.strategy_config = strategy_config
        self.base_market_data = base_market_data
        self.scenarios = scenarios or {}
        
        # Add default scenarios if none provided
        if not self.scenarios:
            self._add_default_scenarios()
    
    def _add_default_scenarios(self) -> None:
        """Add default market scenarios to the tester."""
        # Bull market scenario
        self.add_scenario(
            name="bull_market",
            scenario_type=ScenarioType.BULL_MARKET,
            parameters={"trend_strength": 0.5, "volatility": 0.15},
            description="Strong upward trend with moderate volatility",
            probability=0.3
        )
        
        # Bear market scenario
        self.add_scenario(
            name="bear_market",
            scenario_type=ScenarioType.BEAR_MARKET,
            parameters={"trend_strength": -0.4, "volatility": 0.25},
            description="Downward trend with increased volatility",
            probability=0.2
        )
        
        # Sideways market scenario
        self.add_scenario(
            name="sideways_market",
            scenario_type=ScenarioType.SIDEWAYS_MARKET,
            parameters={"trend_strength": 0.0, "volatility": 0.1, "range_width": 0.05},
            description="Low trend with confined price range",
            probability=0.3
        )
        
        # High volatility scenario
        self.add_scenario(
            name="high_volatility",
            scenario_type=ScenarioType.HIGH_VOLATILITY,
            parameters={"volatility_factor": 2.5, "trend_strength": 0.1},
            description="Extremely volatile market with weak trend",
            probability=0.1
        )
        
        # Market crash scenario
        self.add_scenario(
            name="market_crash",
            scenario_type=ScenarioType.MARKET_CRASH,
            parameters={"crash_size": -0.3, "crash_duration": 20, "recovery_speed": 0.5},
            description="Sudden market crash followed by gradual recovery",
            probability=0.05
        )
        
        # Flash crash scenario
        self.add_scenario(
            name="flash_crash",
            scenario_type=ScenarioType.FLASH_CRASH,
            parameters={"crash_size": -0.15, "crash_duration": 3, "recovery_speed": 0.9},
            description="Very rapid crash with quick recovery",
            probability=0.05
        )
    
    def add_scenario(self,
                    name: str,
                    scenario_type: ScenarioType,
                    parameters: Dict[str, Any] = None,
                    description: str = "",
                    data_transformation: Optional[Callable] = None,
                    duration: int = 252,
                    probability: float = 0.1) -> None:
        """
        Add a scenario to the tester.
        
        Args:
            name: Name of the scenario
            scenario_type: Type of scenario (from ScenarioType enum)
            parameters: Specific parameters for the scenario
            description: Description of the scenario
            data_transformation: Custom function to transform market data for this scenario
            duration: Duration of the scenario in days
            probability: Probability of this scenario occurring (for Monte Carlo)
        """
        # Create transformation function if not provided
        if data_transformation is None:
            data_transformation = self._get_default_transformation(scenario_type)
        
        # Create scenario config
        scenario_config = ScenarioConfig(
            name=name,
            scenario_type=scenario_type,
            parameters=parameters or {},
            description=description,
            base_data=self.base_market_data,
            data_transformation=data_transformation,
            duration=duration,
            probability=probability
        )
        
        # Add to scenarios
        self.scenarios[name] = scenario_config
        logger.info(f"Added scenario: {name} ({scenario_type.value})")
    
    def _get_default_transformation(self, scenario_type: ScenarioType) -> Callable:
        """Get the default transformation function for a scenario type."""
        # Define transformation functions for each scenario type
        transformations = {
            ScenarioType.BULL_MARKET: self._transform_bull_market,
            ScenarioType.BEAR_MARKET: self._transform_bear_market,
            ScenarioType.SIDEWAYS_MARKET: self._transform_sideways_market,
            ScenarioType.HIGH_VOLATILITY: self._transform_high_volatility,
            ScenarioType.LOW_VOLATILITY: self._transform_low_volatility,
            ScenarioType.MARKET_CRASH: self._transform_market_crash,
            ScenarioType.MARKET_RALLY: self._transform_market_rally,
            ScenarioType.REGIME_CHANGE: self._transform_regime_change,
            ScenarioType.LIQUIDITY_CRISIS: self._transform_liquidity_crisis,
            ScenarioType.FLASH_CRASH: self._transform_flash_crash,
        }
        
        return transformations.get(scenario_type, self._transform_custom)
    
    def _transform_bull_market(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a bull market."""
        trend_strength = params.get("trend_strength", 0.5)
        volatility = params.get("volatility", 0.15)
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Add upward trend
            n_periods = len(transformed_df)
            trend = np.linspace(0, trend_strength, n_periods)
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Normalize to starting price
                    start_price = transformed_df[col].iloc[0]
                    normalized = transformed_df[col] / start_price
                    
                    # Add trend and adjust volatility
                    adjusted_returns = normalized.pct_change().fillna(0) * volatility / df[col].pct_change().std()
                    cumulative_returns = (1 + adjusted_returns).cumprod()
                    
                    # Apply trend on top of returns
                    transformed_df[col] = start_price * cumulative_returns * (1 + trend)
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_bear_market(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a bear market."""
        trend_strength = params.get("trend_strength", -0.4)  # Negative for downtrend
        volatility = params.get("volatility", 0.25)
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Add downward trend
            n_periods = len(transformed_df)
            trend = np.linspace(0, trend_strength, n_periods)
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Normalize to starting price
                    start_price = transformed_df[col].iloc[0]
                    normalized = transformed_df[col] / start_price
                    
                    # Add trend and adjust volatility
                    adjusted_returns = normalized.pct_change().fillna(0) * volatility / df[col].pct_change().std()
                    cumulative_returns = (1 + adjusted_returns).cumprod()
                    
                    # Apply trend on top of returns
                    transformed_df[col] = start_price * cumulative_returns * (1 + trend)
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_sideways_market(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a sideways market."""
        trend_strength = params.get("trend_strength", 0.0)
        volatility = params.get("volatility", 0.1)
        range_width = params.get("range_width", 0.05)
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Generate a slight range-bound pattern
            n_periods = len(transformed_df)
            
            # Create oscillating pattern within a range
            t = np.linspace(0, 4 * np.pi, n_periods)  # Multiple cycles
            range_pattern = np.sin(t) * range_width
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Normalize to starting price
                    start_price = transformed_df[col].iloc[0]
                    normalized = transformed_df[col] / start_price
                    
                    # Reduce trend and adjust volatility
                    adjusted_returns = normalized.pct_change().fillna(0) * volatility / df[col].pct_change().std()
                    
                    # Filter out large moves to create more range-bound behavior
                    adjusted_returns = adjusted_returns.clip(-0.02, 0.02)
                    
                    cumulative_returns = (1 + adjusted_returns).cumprod()
                    
                    # Apply range pattern and minimal trend
                    transformed_df[col] = start_price * cumulative_returns * (1 + trend_strength * np.linspace(0, 1, n_periods) + range_pattern)
            
            result[symbol] = transformed_df
        
        return result
    
    def _transform_high_volatility(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a high volatility market."""
        volatility_factor = params.get("volatility_factor", 2.5)
        trend_strength = params.get("trend_strength", 0.1)
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Add mild trend
            n_periods = len(transformed_df)
            trend = np.linspace(0, trend_strength, n_periods)
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Normalize to starting price
                    start_price = transformed_df[col].iloc[0]
                    normalized = transformed_df[col] / start_price
                    
                    # Increase volatility
                    returns = normalized.pct_change().fillna(0)
                    high_vol_returns = returns * volatility_factor
                    
                    # Generate more extreme moves occasionally
                    spikes = np.random.choice([0, 1], size=len(high_vol_returns), p=[0.95, 0.05])
                    high_vol_returns = high_vol_returns + spikes * returns * 5
                    
                    cumulative_returns = (1 + high_vol_returns).cumprod()
                    
                    # Apply trend on top of returns
                    transformed_df[col] = start_price * cumulative_returns * (1 + trend)
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_low_volatility(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a low volatility market."""
        volatility_factor = params.get("volatility_factor", 0.4)
        trend_strength = params.get("trend_strength", 0.05)
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Add mild trend
            n_periods = len(transformed_df)
            trend = np.linspace(0, trend_strength, n_periods)
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Normalize to starting price
                    start_price = transformed_df[col].iloc[0]
                    normalized = transformed_df[col] / start_price
                    
                    # Decrease volatility
                    returns = normalized.pct_change().fillna(0)
                    low_vol_returns = returns * volatility_factor
                    
                    # Smooth out returns
                    low_vol_returns = pd.Series(low_vol_returns).rolling(window=3).mean().fillna(0)
                    
                    cumulative_returns = (1 + low_vol_returns).cumprod()
                    
                    # Apply trend on top of returns
                    transformed_df[col] = start_price * cumulative_returns * (1 + trend)
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_market_crash(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a market crash."""
        crash_size = params.get("crash_size", -0.3)  # e.g., -0.3 for 30% crash
        crash_duration = params.get("crash_duration", 20)  # trading days
        recovery_speed = params.get("recovery_speed", 0.5)  # 1.0 = full recovery in remaining period
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Define crash and recovery pattern
            n_periods = len(transformed_df)
            crash_start = n_periods // 4  # Start crash at 25% of the way through
            crash_end = crash_start + crash_duration
            
            # Create crash pattern
            pattern = np.ones(n_periods)
            
            # Pre-crash period
            pattern[:crash_start] = np.linspace(1.0, 1.05, crash_start)  # Slight buildup
            
            # Crash period
            crash_pattern = np.linspace(1.0, 1.0 + crash_size, crash_duration)
            pattern[crash_start:crash_end] = crash_pattern
            
            # Recovery period
            recovery_periods = n_periods - crash_end
            recovery_amount = -crash_size * recovery_speed
            recovery_pattern = np.linspace(1.0 + crash_size, 1.0 + crash_size + recovery_amount, recovery_periods)
            pattern[crash_end:] = recovery_pattern
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Apply crash pattern
                    transformed_df[col] = df[col] * pattern
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_market_rally(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a market rally."""
        rally_size = params.get("rally_size", 0.4)  # e.g., 0.4 for 40% rally
        rally_duration = params.get("rally_duration", 30)  # trading days
        plateau_factor = params.get("plateau_factor", 0.7)  # 1.0 = maintain full rally, 0 = return to start
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Define rally pattern
            n_periods = len(transformed_df)
            rally_start = n_periods // 4  # Start rally at 25% of the way through
            rally_end = rally_start + rally_duration
            
            # Create rally pattern
            pattern = np.ones(n_periods)
            
            # Pre-rally period
            pattern[:rally_start] = np.linspace(1.0, 0.98, rally_start)  # Slight dip before rally
            
            # Rally period
            rally_pattern = np.linspace(1.0, 1.0 + rally_size, rally_duration)
            pattern[rally_start:rally_end] = rally_pattern
            
            # Post-rally period
            post_periods = n_periods - rally_end
            plateau_level = 1.0 + rally_size * plateau_factor
            pattern[rally_end:] = np.linspace(1.0 + rally_size, plateau_level, post_periods)
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Apply rally pattern
                    transformed_df[col] = df[col] * pattern
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_regime_change(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a market regime change."""
        initial_trend = params.get("initial_trend", 0.2)
        final_trend = params.get("final_trend", -0.3)
        volatility_change = params.get("volatility_change", 1.5)  # Volatility factor after change
        change_point = params.get("change_point", 0.6)  # Position of regime change (0-1)
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Define regime change pattern
            n_periods = len(transformed_df)
            change_idx = int(n_periods * change_point)
            
            # Create trend pattern
            trend1 = np.linspace(0, initial_trend, change_idx)
            trend2 = np.linspace(0, final_trend, n_periods - change_idx)
            trend = np.concatenate([trend1, trend2])
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Normalize to starting price
                    start_price = transformed_df[col].iloc[0]
                    normalized = transformed_df[col] / start_price
                    
                    # Generate returns with regime change
                    returns = normalized.pct_change().fillna(0)
                    
                    # Create volatility pattern
                    vol_pattern = np.ones(n_periods)
                    vol_pattern[change_idx:] = volatility_change
                    
                    # Apply volatility pattern
                    adjusted_returns = returns * vol_pattern
                    
                    # Create cumulative returns
                    cumulative_returns = (1 + adjusted_returns).cumprod()
                    
                    # Apply trend on top of returns
                    transformed_df[col] = start_price * cumulative_returns * (1 + trend)
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_liquidity_crisis(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a liquidity crisis."""
        crisis_magnitude = params.get("crisis_magnitude", -0.25)
        volatility_factor = params.get("volatility_factor", 3.0)
        spread_widening = params.get("spread_widening", 5.0)  # Factor to widen spreads
        crisis_duration = params.get("crisis_duration", 15)  # trading days
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Define crisis pattern
            n_periods = len(transformed_df)
            crisis_start = n_periods // 3  # Start crisis at 33% of the way through
            crisis_end = crisis_start + crisis_duration
            
            # Create pattern for price impact
            pattern = np.ones(n_periods)
            
            # Crisis period
            crisis_pattern = np.linspace(1.0, 1.0 + crisis_magnitude, crisis_duration // 2)
            recovery_pattern = np.linspace(1.0 + crisis_magnitude, 1.0 + crisis_magnitude * 0.3, crisis_duration // 2)
            pattern[crisis_start:crisis_start + crisis_duration // 2] = crisis_pattern
            pattern[crisis_start + crisis_duration // 2:crisis_end] = recovery_pattern
            
            # Post-crisis period (partial recovery)
            recovery_amount = -crisis_magnitude * 0.7
            pattern[crisis_end:] = np.linspace(1.0 + crisis_magnitude * 0.3, 1.0 + crisis_magnitude * 0.3 + recovery_amount, n_periods - crisis_end)
            
            # Create pattern for volatility
            vol_pattern = np.ones(n_periods)
            vol_pattern[crisis_start:crisis_end] = volatility_factor
            vol_pattern[crisis_end:] = np.linspace(volatility_factor, 1.5, n_periods - crisis_end)
            
            # Create pattern for spreads
            spread_pattern = np.ones(n_periods)
            spread_pattern[crisis_start:crisis_end] = spread_widening
            spread_pattern[crisis_end:] = np.linspace(spread_widening, 1.5, n_periods - crisis_end)
            
            # Apply to price data
            for col in ['close']:
                if col in transformed_df:
                    transformed_df[col] = df[col] * pattern
            
            # Apply to high/low to represent wider spreads
            if 'high' in transformed_df and 'low' in transformed_df:
                mid_price = df['close']
                spread = (df['high'] - df['low'])
                
                transformed_df['high'] = mid_price * pattern + (spread * spread_pattern) / 2
                transformed_df['low'] = mid_price * pattern - (spread * spread_pattern) / 2
            
            # Apply to open
            if 'open' in transformed_df:
                transformed_df['open'] = df['open'] * pattern
            
            # Adjust volume to reflect liquidity crisis
            if 'volume' in transformed_df:
                volume_pattern = np.ones(n_periods)
                volume_pattern[crisis_start:crisis_end] = 0.3  # 70% volume reduction during crisis
                volume_pattern[crisis_end:] = np.linspace(0.3, 0.8, n_periods - crisis_end)
                transformed_df['volume'] = df['volume'] * volume_pattern
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_flash_crash(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Transform market data to simulate a flash crash."""
        crash_size = params.get("crash_size", -0.15)  # e.g., -0.15 for 15% crash
        crash_duration = params.get("crash_duration", 3)  # trading days for crash
        recovery_speed = params.get("recovery_speed", 0.9)  # 1.0 = full recovery
        
        result = {}
        for symbol, df in data.items():
            # Create a copy to avoid modifying the original
            transformed_df = df.copy()
            
            # Define flash crash pattern
            n_periods = len(transformed_df)
            crash_start = n_periods // 2  # Start crash in the middle
            crash_end = crash_start + crash_duration
            recovery_end = crash_end + crash_duration * 2  # Recovery takes a bit longer
            recovery_end = min(recovery_end, n_periods)
            
            # Create crash and recovery pattern
            pattern = np.ones(n_periods)
            
            # Crash period
            crash_pattern = np.linspace(1.0, 1.0 + crash_size, crash_duration)
            pattern[crash_start:crash_end] = crash_pattern
            
            # Recovery period
            recovery_periods = recovery_end - crash_end
            recovery_amount = -crash_size * recovery_speed
            if recovery_periods > 0:
                recovery_pattern = np.linspace(1.0 + crash_size, 1.0 + crash_size + recovery_amount, recovery_periods)
                pattern[crash_end:recovery_end] = recovery_pattern
            
            # Post-recovery period
            if recovery_end < n_periods:
                pattern[recovery_end:] = pattern[recovery_end-1]
            
            # Apply to price data
            for col in ['open', 'high', 'low', 'close']:
                if col in transformed_df:
                    # Apply flash crash pattern
                    transformed_df[col] = df[col] * pattern
            
            # Simulate extreme volume during crash
            if 'volume' in transformed_df:
                volume_pattern = np.ones(n_periods)
                volume_pattern[crash_start:crash_end] = 3.0  # 3x volume during crash
                volume_pattern[crash_end:recovery_end] = 2.0  # 2x volume during recovery
                transformed_df['volume'] = df['volume'] * volume_pattern
            
            result[symbol] = transformed_df
            
        return result
    
    def _transform_custom(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Custom transformation based on parameters."""
        # This is a placeholder for custom scenarios
        # Users should define their own transformation function and pass it when creating a custom scenario
        return data.copy()
    
    def generate_scenario_data(self, scenario_name: str) -> Dict[str, pd.DataFrame]:
        """
        Generate market data for a specific scenario.
        
        Args:
            scenario_name: Name of the scenario to generate data for
            
        Returns:
            Dict[str, pd.DataFrame]: Transformed market data for the scenario
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        scenario = self.scenarios[scenario_name]
        
        # Use the scenario's data transformation function
        if scenario.data_transformation:
            transformed_data = scenario.data_transformation(self.base_market_data, scenario.parameters)
        else:
            transformed_data = self.base_market_data.copy()
        
        return transformed_data
        
    def test_scenario(self, scenario_name: str) -> ScenarioResult:
        """
        Test a strategy under a specific market scenario.
        
        Args:
            scenario_name: Name of the scenario to test
            
        Returns:
            ScenarioResult: Results of the scenario test
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        scenario = self.scenarios[scenario_name]
        logger.info(f"Testing scenario: {scenario_name} ({scenario.scenario_type.value})")
        
        # Generate scenario data
        scenario_data = self.generate_scenario_data(scenario_name)
        
        # Create backtest config
        first_symbol = next(iter(scenario_data.keys()))
        start_date = scenario_data[first_symbol].index[0]
        end_date = scenario_data[first_symbol].index[-1]
        
        backtest_config = BacktestConfig(
            name=f"scenario_test_{scenario_name}",
            strategy_config=self.strategy_config,
            start_date=start_date,
            end_date=end_date,
            symbols=list(scenario_data.keys()),
            initial_capital=100000,
            data_frequency="1d"  # This should be dynamic based on data
        )
        
        # Run backtest
        backtest = Backtest(backtest_config)
        backtest.setup(data_override=scenario_data)
        backtest_result = backtest.run()
        
        # Calculate additional metrics
        performance_metrics = backtest_result.performance_metrics.copy()
        
        # Calculate drawdowns
        equity_curve = backtest_result.equity_curve
        drawdowns = []
        if not equity_curve.empty:
            peak = equity_curve.iloc[0]
            for value in equity_curve:
                if value > peak:
                    peak = value
                drawdown = (value - peak) / peak
                drawdowns.append(drawdown)
        
        # Calculate volatility
        returns = backtest_result.returns
        volatility = returns.std() * np.sqrt(252) if not returns.empty else 0.0
        
        # Calculate recovery time (days to recover from max drawdown)
        recovery_time = None
        if drawdowns and min(drawdowns) < -0.01:  # Only calculate if there was a meaningful drawdown
            max_dd_idx = drawdowns.index(min(drawdowns))
            peak_idx = max(0, max_dd_idx - 1)
            while peak_idx > 0 and equity_curve.iloc[peak_idx - 1] >= equity_curve.iloc[peak_idx]:
                peak_idx -= 1
            
            # Find recovery point
            recovery_idx = max_dd_idx
            while recovery_idx < len(equity_curve) - 1 and equity_curve.iloc[recovery_idx] < equity_curve.iloc[peak_idx]:
                recovery_idx += 1
            
            if recovery_idx < len(equity_curve) - 1:
                recovery_time = recovery_idx - max_dd_idx
        
        # Calculate stress metrics (measures specific to stress scenarios)
        stress_metrics = {}
        
        # Metric: Maximum consecutive losses
        if not returns.empty:
            losses = returns < 0
            streaks = losses.astype(int).groupby(losses.astype(int).diff().ne(0).cumsum()).sum()
            max_consecutive_losses = streaks.max() if not streaks.empty else 0
            stress_metrics["max_consecutive_losses"] = max_consecutive_losses
        
        # Metric: Time under water (percentage of time spent in drawdown)
        if drawdowns:
            time_underwater = len([d for d in drawdowns if d < 0]) / len(drawdowns)
            stress_metrics["time_underwater"] = time_underwater
        
        # Metric: Worst day return
        if not returns.empty:
            worst_day = returns.min()
            stress_metrics["worst_day_return"] = worst_day
        
        # Metric: Tail risk (expected shortfall)
        if not returns.empty:
            tail_threshold = np.percentile(returns, 5)
            tail_returns = returns[returns <= tail_threshold]
            expected_shortfall = tail_returns.mean() if not tail_returns.empty else returns.min()
            stress_metrics["expected_shortfall"] = expected_shortfall
        
        # Create and return scenario result
        result = ScenarioResult(
            scenario_config=scenario,
            backtest_result=backtest_result,
            performance_metrics=performance_metrics,
            scenario_data=scenario_data,
            drawdowns=drawdowns,
            volatility=volatility,
            recovery_time=recovery_time,
            stress_metrics=stress_metrics
        )
        
        logger.info(f"Scenario test complete: {scenario_name}")
        return result
        
    def run_all_tests(self) -> ScenarioTestResult:
        """
        Run tests for all scenarios and aggregate results.
        
        Returns:
            ScenarioTestResult: Aggregated results for all scenario tests
        """
        logger.info(f"Running tests for {len(self.scenarios)} scenarios")
        
        # Run each scenario
        scenario_results = {}
        for scenario_name in tqdm(self.scenarios.keys(), desc="Testing scenarios"):
            try:
                result = self.test_scenario(scenario_name)
                scenario_results[scenario_name] = result
            except Exception as e:
                logger.error(f"Error testing scenario {scenario_name}: {str(e)}")
        
        if not scenario_results:
            raise ValueError("No scenarios were successfully tested")
        
        # Calculate aggregate metrics
        strategy_name = self.strategy_config.name
        overall_metrics = self._calculate_overall_metrics(scenario_results)
        probability_weighted_metrics = self._calculate_weighted_metrics(scenario_results)
        worst_case = self._find_worst_case(scenario_results)
        best_case = self._find_best_case(scenario_results)
        
        # Create aggregated result
        result = ScenarioTestResult(
            scenario_results=scenario_results,
            strategy_name=strategy_name,
            strategy_config=self.strategy_config,
            overall_metrics=overall_metrics,
            worst_case=worst_case,
            best_case=best_case,
            probability_weighted_metrics=probability_weighted_metrics
        )
        
        logger.info(f"Completed all scenario tests for strategy: {strategy_name}")
        return result
    
    def _calculate_overall_metrics(self, scenario_results: Dict[str, ScenarioResult]) -> Dict[str, float]:
        """Calculate overall metrics across all scenarios."""
        metrics = {}
        
        # Get all metric keys from the first result
        first_result = next(iter(scenario_results.values()))
        metric_keys = list(first_result.performance_metrics.keys())
        
        # Calculate mean, min, max for each metric
        for key in metric_keys:
            values = [result.performance_metrics.get(key, 0.0) for result in scenario_results.values()]
            if values:
                metrics[f"{key}_mean"] = np.mean(values)
                metrics[f"{key}_min"] = np.min(values)
                metrics[f"{key}_max"] = np.max(values)
                metrics[f"{key}_std"] = np.std(values)
        
        # Add stress metrics
        stress_keys = list(first_result.stress_metrics.keys())
        for key in stress_keys:
            values = [result.stress_metrics.get(key, 0.0) for result in scenario_results.values()]
            if values:
                metrics[f"{key}_mean"] = np.mean(values)
                metrics[f"{key}_worst"] = np.min(values) if "return" in key else np.max(values)
        
        return metrics
    
    def _calculate_weighted_metrics(self, scenario_results: Dict[str, ScenarioResult]) -> Dict[str, float]:
        """Calculate probability-weighted metrics across scenarios."""
        metrics = {}
        
        # Normalize probabilities
        total_prob = sum(result.scenario_config.probability for result in scenario_results.values())
        
        if total_prob == 0:
            return metrics
        
        # Get all metric keys from the first result
        first_result = next(iter(scenario_results.values()))
        metric_keys = list(first_result.performance_metrics.keys())
        
        # Calculate weighted metrics
        for key in metric_keys:
            weighted_sum = sum(
                result.performance_metrics.get(key, 0.0) * result.scenario_config.probability / total_prob
                for result in scenario_results.values()
            )
            metrics[key] = weighted_sum
        
        return metrics
    
    def _find_worst_case(self, scenario_results: Dict[str, ScenarioResult]) -> Tuple[str, Dict[str, float]]:
        """Find the worst-case scenario based on Sharpe ratio."""
        worst_scenario = None
        worst_metrics = None
        worst_sharpe = float('inf')
        
        for name, result in scenario_results.items():
            sharpe = result.performance_metrics.get("sharpe_ratio", 0.0)
            if sharpe < worst_sharpe:
                worst_sharpe = sharpe
                worst_scenario = name
                worst_metrics = result.performance_metrics
        
        return (worst_scenario, worst_metrics) if worst_scenario else (None, None)
    
    def _find_best_case(self, scenario_results: Dict[str, ScenarioResult]) -> Tuple[str, Dict[str, float]]:
        """Find the best-case scenario based on Sharpe ratio."""
        best_scenario = None
        best_metrics = None
        best_sharpe = float('-inf')
        
        for name, result in scenario_results.items():
            sharpe = result.performance_metrics.get("sharpe_ratio", 0.0)
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_scenario = name
                best_metrics = result.performance_metrics
        
        return (best_scenario, best_metrics) if best_scenario else (None, None)
        
    def run_monte_carlo(self, num_simulations: int = 1000) -> ScenarioTestResult:
        """
        Run Monte Carlo simulation by sampling from scenario distributions.
        
        This method runs simulations by randomly selecting scenarios according to their
        probabilities, creating sequences of different market conditions.
        
        Args:
            num_simulations: Number of Monte Carlo simulations to run
            
        Returns:
            ScenarioTestResult: Aggregated results with Monte Carlo metrics
        """
        logger.info(f"Running {num_simulations} Monte Carlo simulations")
        
        # First, run all individual scenarios if not already done
        scenario_results = {}
        for scenario_name in self.scenarios.keys():
            try:
                result = self.test_scenario(scenario_name)
                scenario_results[scenario_name] = result
            except Exception as e:
                logger.error(f"Error testing scenario {scenario_name}: {str(e)}")
        
        if not scenario_results:
            raise ValueError("No scenarios were successfully tested")
        
        # Calculate scenario probabilities and normalize
        scenario_names = list(scenario_results.keys())
        probabilities = [self.scenarios[name].probability for name in scenario_names]
        total_prob = sum(probabilities)
        if total_prob == 0:
            # If no probabilities set, use uniform distribution
            probabilities = [1.0 / len(scenario_names) for _ in scenario_names]
        else:
            # Normalize probabilities
            probabilities = [p / total_prob for p in probabilities]
        
        # Run Monte Carlo simulations
        mc_metrics = self._run_monte_carlo_simulations(scenario_results, scenario_names, 
                                                    probabilities, num_simulations)
        
        # Calculate regular metrics
        strategy_name = self.strategy_config.name
        overall_metrics = self._calculate_overall_metrics(scenario_results)
        probability_weighted_metrics = self._calculate_weighted_metrics(scenario_results)
        worst_case = self._find_worst_case(scenario_results)
        best_case = self._find_best_case(scenario_results)
        
        # Create aggregated result
        result = ScenarioTestResult(
            scenario_results=scenario_results,
            strategy_name=strategy_name,
            strategy_config=self.strategy_config,
            overall_metrics=overall_metrics,
            worst_case=worst_case,
            best_case=best_case,
            probability_weighted_metrics=probability_weighted_metrics,
            monte_carlo_metrics=mc_metrics
        )
        
        logger.info(f"Completed Monte Carlo simulations for strategy: {strategy_name}")
        return result
    
    def _run_monte_carlo_simulations(self, scenario_results: Dict[str, ScenarioResult],
                                   scenario_names: List[str], probabilities: List[float],
                                   num_simulations: int) -> Dict[str, Any]:
        """Run Monte Carlo simulations and aggregate results."""
        # Get key metrics to track
        key_metrics = ["sharpe_ratio", "sortino_ratio", "max_drawdown", "annual_return", 
                      "profit_factor", "win_rate"]
        
        # Initialize metric collectors
        mc_results = {metric: [] for metric in key_metrics}
        mc_paths = []
        mc_scenarios = []
        
        # Run simulations
        for i in tqdm(range(num_simulations), desc="Monte Carlo simulations"):
            # Sample series of scenarios based on probabilities
            sampled_scenarios = np.random.choice(scenario_names, size=10, p=probabilities)
            mc_scenarios.append(sampled_scenarios.tolist())
            
            # Aggregate returns from sampled scenarios to create a path
            path_returns = []
            for scenario_name in sampled_scenarios:
                if scenario_name in scenario_results:
                    # Get returns from scenario result
                    scenario_returns = scenario_results[scenario_name].backtest_result.returns
                    if not scenario_returns.empty:
                        path_returns.extend(scenario_returns.tolist())
            
            if path_returns:
                mc_paths.append(path_returns)
                
                # Calculate metrics for this path
                series_returns = pd.Series(path_returns)
                
                # Calculate key metrics
                sharpe = series_returns.mean() / series_returns.std() * np.sqrt(252) if series_returns.std() > 0 else 0.0
                mc_results["sharpe_ratio"].append(sharpe)
                
                negative_returns = series_returns[series_returns < 0]
                sortino = series_returns.mean() / negative_returns.std() * np.sqrt(252) if not negative_returns.empty and negative_returns.std() > 0 else 0.0
                mc_results["sortino_ratio"].append(sortino)
                
                # Calculate drawdown
                cumulative_returns = (1 + series_returns).cumprod()
                running_max = cumulative_returns.cummax()
                drawdown = (cumulative_returns - running_max) / running_max
                max_drawdown = drawdown.min()
                mc_results["max_drawdown"].append(max_drawdown)
                
                # Calculate annual return
                annual_return = (1 + series_returns.mean()) ** 252 - 1
                mc_results["annual_return"].append(annual_return)
                
                # Calculate profit factor and win rate
                wins = series_returns[series_returns > 0].sum()
                losses = series_returns[series_returns < 0].sum()
                profit_factor = abs(wins / losses) if losses < 0 else float('inf')
                win_rate = len(series_returns[series_returns > 0]) / len(series_returns)
                
                mc_results["profit_factor"].append(profit_factor)
                mc_results["win_rate"].append(win_rate)
        
        # Calculate aggregated metrics
        mc_metrics = {}
        for metric, values in mc_results.items():
            if values:
                mc_metrics[f"{metric}_mean"] = np.mean(values)
                mc_metrics[f"{metric}_median"] = np.median(values)
                mc_metrics[f"{metric}_std"] = np.std(values)
                mc_metrics[f"{metric}_min"] = np.min(values)
                mc_metrics[f"{metric}_max"] = np.max(values)
                
                # Calculate percentiles
                percentiles = [5, 25, 50, 75, 95]
                for p in percentiles:
                    mc_metrics[f"{metric}_p{p}"] = np.percentile(values, p)
        
        # Add paths and scenario sequences for later analysis
        mc_metrics["paths"] = mc_paths
        mc_metrics["scenarios"] = mc_scenarios
        
        return mc_metrics
    
    def plot_scenario_comparison(self, results: ScenarioTestResult = None, 
                               metrics: List[str] = None, figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Plot scenario comparison showing key metrics across different scenarios.
        
        Args:
            results: ScenarioTestResult to plot (if None, run all tests)
            metrics: List of metrics to plot (if None, use default key metrics)
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        if results is None:
            results = self.run_all_tests()
        
        if metrics is None:
            metrics = ["sharpe_ratio", "sortino_ratio", "max_drawdown", "annual_return"]
        
        fig, axes = plt.subplots(len(metrics), 1, figsize=figsize)
        if len(metrics) == 1:
            axes = [axes]
        
        # Get scenario data
        scenario_names = list(results.scenario_results.keys())
        
        # Plot each metric
        for i, metric in enumerate(metrics):
            metric_values = []
            for name in scenario_names:
                if name in results.scenario_results:
                    val = results.scenario_results[name].performance_metrics.get(metric, 0.0)
                    metric_values.append(val)
                else:
                    metric_values.append(0.0)
            
            # Plot bar chart
            ax = axes[i]
            bars = ax.bar(scenario_names, metric_values)
            
            # Add value labels
            for bar, val in zip(bars, metric_values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{val:.2f}', ha='center', va='bottom')
            
            # Add weighted average line
            if metric in results.probability_weighted_metrics:
                weighted_avg = results.probability_weighted_metrics[metric]
                ax.axhline(weighted_avg, color='r', linestyle='--', alpha=0.7)
                ax.text(0, weighted_avg, f'Weighted Avg: {weighted_avg:.2f}', 
                      color='r', ha='left', va='bottom')
            
            ax.set_title(f'{metric.replace("_", " ").title()}')
            ax.set_ylabel('Value')
            ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.9)
        plt.suptitle(f'Scenario Comparison - {results.strategy_name}', fontsize=16)
        
        return fig
    
    def plot_monte_carlo_results(self, results: ScenarioTestResult = None,
                               figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Plot Monte Carlo simulation results.
        
        Args:
            results: ScenarioTestResult with Monte Carlo metrics
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        if results is None or not results.monte_carlo_metrics:
            logger.warning("No Monte Carlo results available. Run monte_carlo first.")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # Get key metrics for plotting
        metrics = ["sharpe_ratio", "annual_return", "max_drawdown", "sortino_ratio"]
        
        # Plot histograms for each metric
        for i, metric in enumerate(metrics):
            ax = axes[i // 2, i % 2]
            values = []
            for p in range(5, 100, 5):
                key = f"{metric}_p{p}"
                if key in results.monte_carlo_metrics:
                    values.append(results.monte_carlo_metrics[key])
            
            if not values:
                continue
            
            # Plot histogram
            ax.hist(values, bins=20, alpha=0.7)
            
            # Add mean line
            mean_key = f"{metric}_mean"
            if mean_key in results.monte_carlo_metrics:
                mean_val = results.monte_carlo_metrics[mean_key]
                ax.axvline(mean_val, color='r', linestyle='--', alpha=0.7)
                ax.text(mean_val, 0, f'Mean: {mean_val:.2f}', color='r', ha='left', va='bottom')
            
            # Add percentile lines
            percentiles = [5, 95]
            colors = ['b', 'g']
            for p, color in zip(percentiles, colors):
                key = f"{metric}_p{p}"
                if key in results.monte_carlo_metrics:
                    val = results.monte_carlo_metrics[key]
                    ax.axvline(val, color=color, linestyle=':', alpha=0.7)
                    ax.text(val, 0, f'P{p}: {val:.2f}', color=color, ha='left', va='top')
            
            ax.set_title(f'{metric.replace("_", " ").title()} Distribution')
            ax.set_xlabel('Value')
            ax.set_ylabel('Frequency')
            ax.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.9)
        plt.suptitle(f'Monte Carlo Results - {results.strategy_name}', fontsize=16)
        
        return fig 