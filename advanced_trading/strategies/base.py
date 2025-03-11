"""
Base Strategy Module

This module provides the base classes and interfaces for all trading strategies in the
Instinct AI trading platform. It defines the core abstractions that all strategies must
implement, including:

- Strategy: The base class for all trading strategies
- StrategyConfig: Configuration parameters for strategies
- StrategyResult: Results and metrics from strategy execution
- StrategyState: State management for strategies

These abstractions ensure that all strategies have a consistent interface and can be
used interchangeably within the platform.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Tuple, Set, Callable

import numpy as np
import pandas as pd

from advanced_trading.core.common import ComponentRegistry


class StrategyType(Enum):
    """Enumeration of strategy types."""
    ARBITRAGE = "arbitrage"
    MACHINE_LEARNING = "machine_learning"
    STATISTICAL = "statistical"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    HYBRID = "hybrid"
    CUSTOM = "custom"


@dataclass
class StrategyConfig:
    """Configuration parameters for a trading strategy.
    
    This class defines the configuration parameters that can be used to customize
    the behavior of a trading strategy.
    
    Attributes:
        name (str): The name of the strategy.
        symbols (List[str]): The trading symbols to use.
        timeframe (str): The timeframe for data (e.g., "1m", "5m", "1h", "1d").
        parameters (Dict[str, Any]): Strategy-specific parameters.
        risk_limits (Dict[str, float]): Risk management limits.
        enabled (bool): Whether the strategy is enabled.
    """
    name: str
    symbols: List[str]
    timeframe: str = "1h"
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk_limits: Dict[str, float] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class StrategyResult:
    """Results and metrics from strategy execution.
    
    This class encapsulates the results and performance metrics from executing
    a trading strategy.
    
    Attributes:
        strategy_name (str): The name of the strategy.
        signals (pd.DataFrame): The trading signals generated.
        positions (pd.DataFrame): The positions taken.
        pnl (float): The profit and loss.
        metrics (Dict[str, float]): Performance metrics.
        trades (pd.DataFrame): The trades executed.
        timestamp (pd.Timestamp): The timestamp of the result.
    """
    strategy_name: str
    signals: Optional[pd.DataFrame] = None
    positions: Optional[pd.DataFrame] = None
    pnl: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    trades: Optional[pd.DataFrame] = None
    timestamp: Optional[pd.Timestamp] = None


class StrategyState:
    """State management for strategies.
    
    This class manages the state of a strategy, including positions, signals,
    metrics, and parameters.
    
    Attributes:
        strategy_name (str): The name of the strategy.
        positions (Dict[str, Dict[str, Any]]): The current positions by symbol.
        signals (Dict[str, List[Dict[str, Any]]]): The recent signals by symbol.
        metrics (Dict[str, float]): The current performance metrics.
        parameters (Dict[str, Any]): The current strategy parameters.
    """
    
    def __init__(self, strategy_name: str):
        """Initialize the strategy state.
        
        Args:
            strategy_name (str): The name of the strategy.
        """
        self.strategy_name = strategy_name
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.signals: Dict[str, List[Dict[str, Any]]] = {}
        self.metrics: Dict[str, float] = {}
        self.parameters: Dict[str, Any] = {}
    
    def update_position(self, symbol: str, position: Dict[str, Any]) -> None:
        """Update the position for a symbol.
        
        Args:
            symbol (str): The symbol.
            position (Dict[str, Any]): The position data.
        """
        self.positions[symbol] = position
    
    def add_signal(self, symbol: str, signal: Dict[str, Any]) -> None:
        """Add a signal for a symbol.
        
        Args:
            symbol (str): The symbol.
            signal (Dict[str, Any]): The signal data.
        """
        if symbol not in self.signals:
            self.signals[symbol] = []
        self.signals[symbol].append(signal)
    
    def update_metrics(self, metrics: Dict[str, float]) -> None:
        """Update the performance metrics.
        
        Args:
            metrics (Dict[str, float]): The performance metrics.
        """
        self.metrics.update(metrics)
    
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update the strategy parameters.
        
        Args:
            parameters (Dict[str, Any]): The strategy parameters.
        """
        self.parameters.update(parameters)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary.
        
        Returns:
            Dict[str, Any]: The state as a dictionary.
        """
        return {
            "strategy_name": self.strategy_name,
            "positions": self.positions,
            "signals": self.signals,
            "metrics": self.metrics,
            "parameters": self.parameters
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyState':
        """Create a state from a dictionary.
        
        Args:
            data (Dict[str, Any]): The state data.
        
        Returns:
            StrategyState: The state.
        """
        state = cls(data["strategy_name"])
        state.positions = data.get("positions", {})
        state.signals = data.get("signals", {})
        state.metrics = data.get("metrics", {})
        state.parameters = data.get("parameters", {})
        return state


class Strategy(ABC):
    """Base class for all trading strategies.
    
    This abstract class defines the interface that all trading strategies must implement.
    It provides methods for initialization, data processing, signal generation, and
    execution.
    
    Attributes:
        name (str): The name of the strategy.
        config (StrategyConfig): The strategy configuration.
        state (StrategyState): The strategy state.
        version (str): The strategy version.
        is_running (bool): Whether the strategy is currently running.
    """
    
    def __init__(self, config: StrategyConfig):
        """Initialize the strategy.
        
        Args:
            config (StrategyConfig): The strategy configuration.
        """
        self.name = config.name
        self.config = config
        self.state = StrategyState(config.name)
        self.version = "1.0.0"  # Default version
        self.is_running = False
        self._is_paused = False
        self._warmup_data = []
    
    @abstractmethod
    def initialize(self, parameters: Optional[Dict[str, Any]] = None, 
                  dependencies: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the strategy.
        
        This method is called once when the strategy is created. It should
        perform any one-time initialization tasks.
        
        Args:
            parameters: Optional parameters to override the default configuration
            dependencies: Optional dependencies like data sources, models, etc.
        """
        pass
    
    def process_warmup_data(self, data: pd.DataFrame) -> None:
        """Process warm-up data before the strategy is fully active.
        
        This method is called during the strategy warm-up phase to provide historical
        data that the strategy can use to initialize its internal state, indicators,
        or models.
        
        Args:
            data (pd.DataFrame): Historical data for warm-up.
        """
        # Default implementation stores the data
        self._warmup_data.append(data)
        
        # Subclasses should override this method to properly process warm-up data
        pass
    
    def start(self) -> None:
        """Start the strategy execution.
        
        This method is called when the strategy should begin active trading.
        """
        self.is_running = True
        self._is_paused = False
    
    def pause(self) -> None:
        """Pause the strategy execution.
        
        This method is called when the strategy should temporarily pause trading.
        """
        self._is_paused = True
    
    def stop(self) -> None:
        """Stop the strategy execution.
        
        This method is called when the strategy should stop trading and clean up resources.
        """
        self.is_running = False
        self._is_paused = False
        
        # Perform any necessary cleanup
        self._cleanup()
    
    def _cleanup(self) -> None:
        """Clean up resources used by the strategy.
        
        This method should be overridden by subclasses to perform strategy-specific cleanup.
        """
        # Default implementation does nothing
        pass
    
    @abstractmethod
    def process_data(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Process market data.
        
        This method processes raw market data and prepares it for signal generation.
        
        Args:
            data (Dict[str, pd.DataFrame]): Raw market data by symbol.
        
        Returns:
            Dict[str, pd.DataFrame]: Processed data by symbol.
        """
        pass
    
    @abstractmethod
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Generate trading signals.
        
        This method generates trading signals based on processed market data.
        
        Args:
            data (Dict[str, pd.DataFrame]): Processed market data by symbol.
        
        Returns:
            Dict[str, pd.DataFrame]: Trading signals by symbol.
        """
        pass
    
    @abstractmethod
    def execute(self, signals: Dict[str, pd.DataFrame]) -> StrategyResult:
        """Execute trading signals.
        
        This method executes trading signals and returns the results.
        
        Args:
            signals (Dict[str, pd.DataFrame]): Trading signals by symbol.
        
        Returns:
            StrategyResult: The results of executing the signals.
        """
        pass
    
    def update(self, data: Dict[str, pd.DataFrame]) -> StrategyResult:
        """Update the strategy with new data.
        
        This method updates the strategy with new market data, generates signals,
        and executes them.
        
        Args:
            data (Dict[str, pd.DataFrame]): Raw market data by symbol.
        
        Returns:
            StrategyResult: The results of the update.
        """
        # Skip processing if strategy is not running or is paused
        if not self.is_running or self._is_paused:
            return StrategyResult(strategy_name=self.name)
            
        processed_data = self.process_data(data)
        signals = self.generate_signals(processed_data)
        result = self.execute(signals)
        return result
    
    def get_config(self) -> StrategyConfig:
        """Get the strategy configuration.
        
        Returns:
            StrategyConfig: The strategy configuration.
        """
        return self.config
    
    def set_config(self, config: StrategyConfig) -> None:
        """Set the strategy configuration.
        
        Args:
            config (StrategyConfig): The strategy configuration.
        """
        self.config = config
    
    def get_state(self) -> StrategyState:
        """Get the strategy state.
        
        Returns:
            StrategyState: The strategy state.
        """
        return self.state
    
    def set_state(self, state: StrategyState) -> None:
        """Set the strategy state.
        
        Args:
            state (StrategyState): The strategy state.
        """
        self.state = state
    
    def save(self) -> Dict[str, Any]:
        """Save the strategy.
        
        Returns:
            Dict[str, Any]: The saved strategy data.
        """
        return {
            "name": self.name,
            "config": self.config.__dict__,
            "state": self.state.to_dict(),
            "version": self.version
        }
    
    @classmethod
    def load(cls, data: Dict[str, Any]) -> 'Strategy':
        """Load a strategy.
        
        Args:
            data (Dict[str, Any]): The strategy data.
        
        Returns:
            Strategy: The loaded strategy.
        """
        config = StrategyConfig(**data["config"])
        strategy = cls(config)
        strategy.state = StrategyState.from_dict(data["state"])
        if "version" in data:
            strategy.version = data["version"]
        return strategy


# Register the Strategy class with the component registry
ComponentRegistry.register_component("strategy", Strategy) 