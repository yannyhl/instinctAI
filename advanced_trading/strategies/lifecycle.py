"""
Strategy Lifecycle Management Module

This module provides components for managing the complete lifecycle of trading strategies, including:
- Strategy initialization and configuration
- Warm-up period management
- Strategy execution and monitoring
- Strategy teardown and resources cleanup
- State persistence and recovery
- Version management and status tracking

The lifecycle manager ensures that strategies operate correctly through their entire lifecycle
from initialization to teardown, with proper resource management and state tracking.
"""

import os
import time
import json
import pickle
import logging
import datetime
from typing import Dict, List, Optional, Union, Any, Callable, Type
from enum import Enum
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

from advanced_trading.strategies.base import Strategy
from advanced_trading.core.config import ConfigManager
from advanced_trading.core.observability import LogManager

# Constants
DEFAULT_WARMUP_BARS = 100
MAX_INITIALIZATION_RETRIES = 3
INITIALIZATION_RETRY_DELAY = 5  # seconds

# Setup logging
logger = logging.getLogger(__name__)


class StrategyState(Enum):
    """Enum representing possible states of a strategy in its lifecycle."""
    
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    WARMING_UP = "warming_up"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    CRASHED = "crashed"


class StrategyError(Exception):
    """Base exception for strategy lifecycle errors."""
    pass


class StrategyInitializationError(StrategyError):
    """Exception raised when strategy initialization fails."""
    pass


class StrategyExecutionError(StrategyError):
    """Exception raised when strategy execution encounters an error."""
    pass


class StrategyLifecycleManager:
    """
    Manages the complete lifecycle of trading strategies.
    
    The lifecycle manager is responsible for:
    1. Initializing strategies with proper parameters and dependencies
    2. Managing warm-up periods to ensure strategies have sufficient data
    3. Starting, pausing, and stopping strategy execution
    4. Monitoring strategy health and performance
    5. Handling failures and recovery
    6. Cleaning up resources when strategies are stopped
    7. Persisting and recovering strategy state
    
    This class serves as the central coordinator for strategy operation,
    ensuring that strategies go through proper state transitions and
    maintain their operational integrity.
    """
    
    def __init__(self, 
                 config_manager: Optional[ConfigManager] = None,
                 log_manager: Optional[LogManager] = None,
                 state_dir: Optional[str] = None):
        """
        Initialize the strategy lifecycle manager.
        
        Args:
            config_manager: Configuration manager instance
            log_manager: Log manager instance
            state_dir: Directory to store strategy state files
        """
        self.config_manager = config_manager or ConfigManager()
        self.log_manager = log_manager or LogManager(__name__)
        self.state_dir = state_dir or os.path.join(os.getcwd(), "strategy_state")
        
        # Create state directory if it doesn't exist
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
        
        # Dictionary to track managed strategies
        self.strategies: Dict[str, Dict[str, Any]] = {}
        
        self.logger = self.log_manager.get_logger()
        self.logger.info("Strategy lifecycle manager initialized")
    
    def register_strategy(self, 
                         strategy: Strategy, 
                         strategy_id: Optional[str] = None,
                         parameters: Optional[Dict[str, Any]] = None,
                         dependencies: Optional[Dict[str, Any]] = None,
                         warmup_bars: int = DEFAULT_WARMUP_BARS,
                         auto_initialize: bool = False) -> str:
        """
        Register a strategy to be managed by the lifecycle manager.
        
        Args:
            strategy: The strategy instance to manage
            strategy_id: Optional unique identifier for the strategy
            parameters: Strategy parameters
            dependencies: Strategy dependencies (data sources, models, etc.)
            warmup_bars: Number of bars needed for warm-up
            auto_initialize: Whether to automatically initialize the strategy
            
        Returns:
            The strategy ID
            
        Raises:
            ValueError: If the strategy is already registered
        """
        # Generate strategy ID if not provided
        if strategy_id is None:
            strategy_id = f"{strategy.__class__.__name__}_{int(time.time())}"
            
        # Check if strategy is already registered
        if strategy_id in self.strategies:
            raise ValueError(f"Strategy with ID {strategy_id} is already registered")
        
        # Initialize strategy entry
        self.strategies[strategy_id] = {
            "instance": strategy,
            "parameters": parameters or {},
            "dependencies": dependencies or {},
            "state": StrategyState.UNINITIALIZED,
            "warmup_bars": warmup_bars,
            "warmup_progress": 0,
            "start_time": None,
            "last_update_time": None,
            "error": None,
            "metrics": {},
            "version": strategy.version if hasattr(strategy, "version") else "1.0.0"
        }
        
        self.logger.info(f"Strategy {strategy_id} registered with lifecycle manager")
        
        # Initialize if requested
        if auto_initialize:
            self.initialize_strategy(strategy_id)
            
        return strategy_id
    
    def initialize_strategy(self, strategy_id: str) -> bool:
        """
        Initialize a registered strategy.
        
        This method:
        1. Sets up strategy parameters and dependencies
        2. Calls the strategy's initialize method
        3. Updates the strategy state
        
        Args:
            strategy_id: ID of the strategy to initialize
            
        Returns:
            True if initialization was successful, False otherwise
            
        Raises:
            ValueError: If strategy is not registered
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        if strategy_info["state"] != StrategyState.UNINITIALIZED:
            self.logger.warning(f"Strategy {strategy_id} is already initialized (state: {strategy_info['state']})")
            return True
        
        # Update state
        strategy_info["state"] = StrategyState.INITIALIZING
        
        # Get strategy instance and parameters
        strategy = strategy_info["instance"]
        parameters = strategy_info["parameters"]
        dependencies = strategy_info["dependencies"]
        
        self.logger.info(f"Initializing strategy {strategy_id}")
        
        # Attempt initialization with retry logic
        for attempt in range(1, MAX_INITIALIZATION_RETRIES + 1):
            try:
                # Call strategy's initialize method
                strategy.initialize(parameters=parameters, dependencies=dependencies)
                
                # Update state on success
                strategy_info["state"] = StrategyState.WARMING_UP
                strategy_info["warmup_progress"] = 0
                strategy_info["last_update_time"] = datetime.datetime.now()
                
                self.logger.info(f"Strategy {strategy_id} initialized successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Strategy {strategy_id} initialization failed (attempt {attempt}/{MAX_INITIALIZATION_RETRIES}): {str(e)}")
                if attempt < MAX_INITIALIZATION_RETRIES:
                    self.logger.info(f"Retrying in {INITIALIZATION_RETRY_DELAY} seconds...")
                    time.sleep(INITIALIZATION_RETRY_DELAY)
                else:
                    strategy_info["state"] = StrategyState.FAILED
                    strategy_info["error"] = str(e)
                    self.logger.error(f"Strategy {strategy_id} initialization failed after {MAX_INITIALIZATION_RETRIES} attempts")
                    raise StrategyInitializationError(f"Strategy {strategy_id} initialization failed: {str(e)}")
        
        return False
    
    def warmup_strategy(self, strategy_id: str, data: pd.DataFrame) -> bool:
        """
        Warm up a strategy by feeding it historical data.
        
        Args:
            strategy_id: ID of the strategy to warm up
            data: Historical data for warm-up
            
        Returns:
            True if warm-up is complete, False if more data is needed
            
        Raises:
            ValueError: If strategy is not registered or not in correct state
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        # Check current state
        if strategy_info["state"] == StrategyState.READY:
            self.logger.info(f"Strategy {strategy_id} is already warmed up")
            return True
            
        if strategy_info["state"] != StrategyState.WARMING_UP:
            raise ValueError(f"Strategy {strategy_id} is not in warming up state (current state: {strategy_info['state']})")
        
        # Get strategy instance
        strategy = strategy_info["instance"]
        
        try:
            # Process warm-up data
            strategy.process_warmup_data(data)
            
            # Update warm-up progress
            strategy_info["warmup_progress"] += len(data)
            strategy_info["last_update_time"] = datetime.datetime.now()
            
            self.logger.info(f"Strategy {strategy_id} warmed up with {len(data)} bars, progress: {strategy_info['warmup_progress']}/{strategy_info['warmup_bars']}")
            
            # Check if warm-up is complete
            if strategy_info["warmup_progress"] >= strategy_info["warmup_bars"]:
                strategy_info["state"] = StrategyState.READY
                self.logger.info(f"Strategy {strategy_id} warm-up complete")
                return True
                
            return False
            
        except Exception as e:
            strategy_info["state"] = StrategyState.FAILED
            strategy_info["error"] = str(e)
            self.logger.error(f"Strategy {strategy_id} warm-up failed: {str(e)}")
            raise StrategyError(f"Strategy {strategy_id} warm-up failed: {str(e)}")
    
    def start_strategy(self, strategy_id: str) -> bool:
        """
        Start a strategy's execution.
        
        Args:
            strategy_id: ID of the strategy to start
            
        Returns:
            True if strategy was started successfully
            
        Raises:
            ValueError: If strategy is not registered or not ready
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        # Check current state
        if strategy_info["state"] == StrategyState.RUNNING:
            self.logger.warning(f"Strategy {strategy_id} is already running")
            return True
            
        if strategy_info["state"] not in [StrategyState.READY, StrategyState.PAUSED]:
            raise ValueError(f"Strategy {strategy_id} is not ready to start (current state: {strategy_info['state']})")
        
        # Get strategy instance
        strategy = strategy_info["instance"]
        
        try:
            # Call strategy's start method
            strategy.start()
            
            # Update state
            strategy_info["state"] = StrategyState.RUNNING
            strategy_info["start_time"] = datetime.datetime.now() if strategy_info["start_time"] is None else strategy_info["start_time"]
            strategy_info["last_update_time"] = datetime.datetime.now()
            
            self.logger.info(f"Strategy {strategy_id} started successfully")
            return True
            
        except Exception as e:
            strategy_info["state"] = StrategyState.FAILED
            strategy_info["error"] = str(e)
            self.logger.error(f"Strategy {strategy_id} start failed: {str(e)}")
            raise StrategyError(f"Strategy {strategy_id} start failed: {str(e)}")
    
    def pause_strategy(self, strategy_id: str) -> bool:
        """
        Pause a running strategy.
        
        Args:
            strategy_id: ID of the strategy to pause
            
        Returns:
            True if strategy was paused successfully
            
        Raises:
            ValueError: If strategy is not registered or not running
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        # Check current state
        if strategy_info["state"] == StrategyState.PAUSED:
            self.logger.warning(f"Strategy {strategy_id} is already paused")
            return True
            
        if strategy_info["state"] != StrategyState.RUNNING:
            raise ValueError(f"Strategy {strategy_id} is not running (current state: {strategy_info['state']})")
        
        # Get strategy instance
        strategy = strategy_info["instance"]
        
        try:
            # Call strategy's pause method
            strategy.pause()
            
            # Update state
            strategy_info["state"] = StrategyState.PAUSED
            strategy_info["last_update_time"] = datetime.datetime.now()
            
            self.logger.info(f"Strategy {strategy_id} paused successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Strategy {strategy_id} pause failed: {str(e)}")
            raise StrategyError(f"Strategy {strategy_id} pause failed: {str(e)}")
    
    def stop_strategy(self, strategy_id: str, force: bool = False) -> bool:
        """
        Stop a strategy and clean up its resources.
        
        Args:
            strategy_id: ID of the strategy to stop
            force: If True, force stop even if strategy is in an unexpected state
            
        Returns:
            True if strategy was stopped successfully
            
        Raises:
            ValueError: If strategy is not registered
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        # Check current state
        if strategy_info["state"] == StrategyState.STOPPED:
            self.logger.warning(f"Strategy {strategy_id} is already stopped")
            return True
            
        if not force and strategy_info["state"] not in [StrategyState.RUNNING, StrategyState.PAUSED, StrategyState.READY]:
            self.logger.warning(f"Strategy {strategy_id} is in state {strategy_info['state']}, not typically stoppable")
            if not force:
                raise ValueError(f"Strategy {strategy_id} cannot be stopped in state {strategy_info['state']}")
        
        # Get strategy instance
        strategy = strategy_info["instance"]
        
        # Update state to stopping
        strategy_info["state"] = StrategyState.STOPPING
        
        try:
            # Call strategy's stop method
            strategy.stop()
            
            # Update state
            strategy_info["state"] = StrategyState.STOPPED
            strategy_info["last_update_time"] = datetime.datetime.now()
            
            self.logger.info(f"Strategy {strategy_id} stopped successfully")
            return True
            
        except Exception as e:
            strategy_info["state"] = StrategyState.CRASHED
            strategy_info["error"] = str(e)
            self.logger.error(f"Strategy {strategy_id} stop failed: {str(e)}")
            if force:
                self.logger.warning(f"Force stop enabled, marking strategy {strategy_id} as stopped despite error")
                strategy_info["state"] = StrategyState.STOPPED
                return True
            else:
                raise StrategyError(f"Strategy {strategy_id} stop failed: {str(e)}")
    
    def process_data(self, strategy_id: str, data: Union[pd.DataFrame, Dict]) -> Dict[str, Any]:
        """
        Process new data with a strategy.
        
        Args:
            strategy_id: ID of the strategy to process data with
            data: New data to process
            
        Returns:
            Dictionary with processing results
            
        Raises:
            ValueError: If strategy is not registered or not running
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        # Check current state
        if strategy_info["state"] != StrategyState.RUNNING:
            raise ValueError(f"Strategy {strategy_id} is not running (current state: {strategy_info['state']})")
        
        # Get strategy instance
        strategy = strategy_info["instance"]
        
        try:
            # Process data with strategy
            results = strategy.process_data(data)
            
            # Update last update time
            strategy_info["last_update_time"] = datetime.datetime.now()
            
            return results
            
        except Exception as e:
            self.logger.error(f"Strategy {strategy_id} data processing failed: {str(e)}")
            raise StrategyExecutionError(f"Strategy {strategy_id} data processing failed: {str(e)}")
    
    def save_strategy_state(self, strategy_id: str, include_instance: bool = False) -> str:
        """
        Save the current state of a strategy to disk.
        
        Args:
            strategy_id: ID of the strategy to save
            include_instance: Whether to save the strategy instance (may be large)
            
        Returns:
            Path to the saved state file
            
        Raises:
            ValueError: If strategy is not registered
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        # Create a copy of strategy info for saving
        state_to_save = strategy_info.copy()
        
        # Don't save the instance unless specifically requested
        if not include_instance:
            state_to_save.pop("instance", None)
        
        # Convert datetime objects to strings
        if state_to_save.get("start_time"):
            state_to_save["start_time"] = state_to_save["start_time"].isoformat()
        if state_to_save.get("last_update_time"):
            state_to_save["last_update_time"] = state_to_save["last_update_time"].isoformat()
        
        # Convert enum to string
        state_to_save["state"] = state_to_save["state"].value
        
        # Create filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{strategy_id}_{timestamp}.json"
        filepath = os.path.join(self.state_dir, filename)
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(state_to_save, f, indent=2)
        
        self.logger.info(f"Strategy {strategy_id} state saved to {filepath}")
        return filepath
    
    def load_strategy_state(self, filepath: str) -> str:
        """
        Load a strategy state from a file.
        
        Args:
            filepath: Path to the state file
            
        Returns:
            ID of the loaded strategy
            
        Raises:
            FileNotFoundError: If the state file doesn't exist
            ValueError: If the state file is invalid
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Strategy state file {filepath} not found")
        
        # Load state from file
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Validate state
        required_fields = ["parameters", "state", "warmup_bars"]
        for field in required_fields:
            if field not in state:
                raise ValueError(f"Invalid strategy state file: missing field '{field}'")
        
        # Get strategy ID
        strategy_id = state.get("id")
        if not strategy_id:
            # Extract ID from filename
            strategy_id = os.path.basename(filepath).split('_')[0]
        
        # Check if strategy with this ID is already registered
        if strategy_id in self.strategies:
            self.logger.warning(f"Strategy {strategy_id} is already registered, will be overwritten")
            
        # Convert string state to enum
        state["state"] = StrategyState(state["state"])
        
        # Convert string timestamps to datetime objects
        if state.get("start_time"):
            state["start_time"] = datetime.datetime.fromisoformat(state["start_time"])
        if state.get("last_update_time"):
            state["last_update_time"] = datetime.datetime.fromisoformat(state["last_update_time"])
        
        # Store in strategies dictionary
        self.strategies[strategy_id] = state
        
        self.logger.info(f"Strategy {strategy_id} state loaded from {filepath}")
        return strategy_id
    
    def get_strategy_status(self, strategy_id: str) -> Dict[str, Any]:
        """
        Get the current status of a strategy.
        
        Args:
            strategy_id: ID of the strategy
            
        Returns:
            Dictionary with strategy status information
            
        Raises:
            ValueError: If strategy is not registered
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
            
        strategy_info = self.strategies[strategy_id]
        
        # Create status dictionary
        status = {
            "id": strategy_id,
            "name": strategy_info["instance"].__class__.__name__,
            "state": strategy_info["state"].value,
            "version": strategy_info.get("version", "unknown"),
            "warmup_progress": f"{strategy_info['warmup_progress']}/{strategy_info['warmup_bars']}",
            "start_time": strategy_info.get("start_time"),
            "last_update_time": strategy_info.get("last_update_time"),
            "runtime": None,
            "error": strategy_info.get("error"),
            "parameters_count": len(strategy_info.get("parameters", {})),
            "dependencies_count": len(strategy_info.get("dependencies", {}))
        }
        
        # Calculate runtime if started
        if status["start_time"] and status["last_update_time"]:
            status["runtime"] = str(status["last_update_time"] - status["start_time"])
            
        return status
    
    def get_all_strategies_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the current status of all registered strategies.
        
        Returns:
            Dictionary mapping strategy IDs to their status information
        """
        return {
            strategy_id: self.get_strategy_status(strategy_id)
            for strategy_id in self.strategies
        }
    
    def cleanup(self):
        """Clean up resources used by the lifecycle manager."""
        # Stop all running strategies
        for strategy_id in list(self.strategies.keys()):
            try:
                strategy_info = self.strategies[strategy_id]
                if strategy_info["state"] in [StrategyState.RUNNING, StrategyState.PAUSED]:
                    self.logger.info(f"Stopping strategy {strategy_id} during cleanup")
                    self.stop_strategy(strategy_id, force=True)
            except Exception as e:
                self.logger.error(f"Error stopping strategy {strategy_id} during cleanup: {str(e)}")
        
        self.logger.info("Strategy lifecycle manager cleaned up") 