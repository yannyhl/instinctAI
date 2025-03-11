"""
Risk-Aware Strategy Lifecycle Management

This module extends the Strategy Lifecycle Management system to integrate with
the Risk Management system. It provides risk-aware strategy execution by:

1. Validating strategy actions against risk limits
2. Adjusting position sizes based on risk parameters
3. Enforcing portfolio-level risk constraints
4. Monitoring risk metrics during strategy execution
5. Implementing emergency protocol for risk violations

The risk-aware lifecycle manager ensures that all strategies operate within
the defined risk parameters, protecting the trading system from excessive risk.
"""

import os
import time
import logging
import datetime
from typing import Dict, List, Optional, Union, Any, Tuple, Set, Type
import pandas as pd

from advanced_trading.strategies.lifecycle import (
    StrategyLifecycleManager, 
    StrategyState,
    StrategyError,
    DEFAULT_WARMUP_BARS
)
from advanced_trading.strategies.base import Strategy
from advanced_trading.core.config import ConfigManager
from advanced_trading.core.observability import LogManager

from advanced_trading.execution.risk_integration.risk_manager import (
    ExecutionRiskManager,
    ExecutionRiskConfig,
    RiskCheckResult,
    RiskValidationStatus
)
from advanced_trading.execution.risk_integration.position_risk import (
    PositionRiskValidator,
    PositionRiskMetrics
)
from advanced_trading.execution.risk_integration.portfolio_risk import (
    PortfolioRiskIntegration,
    PortfolioRiskMetrics
)
from advanced_trading.risk.portfolio.controller import PortfolioRiskController

# Setup logging
logger = logging.getLogger(__name__)


class RiskViolationError(StrategyError):
    """Exception raised when a risk violation is detected."""
    pass


class RiskMetrics:
    """Container for risk metrics tracked during strategy execution."""
    
    def __init__(self):
        """Initialize risk metrics."""
        self.position_metrics: Dict[str, Dict[str, Any]] = {}
        self.portfolio_metrics: Dict[str, Any] = {}
        self.drawdown: float = 0.0
        self.exposure: float = 0.0
        self.volatility: float = 0.0
        self.value_at_risk: float = 0.0
        self.correlation_matrix: Optional[pd.DataFrame] = None
        self.violations: List[RiskCheckResult] = []
        self.warnings: List[RiskCheckResult] = []
        self.last_updated: Optional[datetime.datetime] = None
    
    def update(self, metrics: Dict[str, Any]) -> None:
        """Update risk metrics.
        
        Args:
            metrics: Dictionary of risk metrics to update.
        """
        if 'position_metrics' in metrics:
            self.position_metrics.update(metrics['position_metrics'])
        
        if 'portfolio_metrics' in metrics:
            self.portfolio_metrics.update(metrics['portfolio_metrics'])
        
        for key in ['drawdown', 'exposure', 'volatility', 'value_at_risk']:
            if key in metrics:
                setattr(self, key, metrics[key])
        
        if 'correlation_matrix' in metrics:
            self.correlation_matrix = metrics['correlation_matrix']
        
        if 'violations' in metrics:
            self.violations.extend(metrics['violations'])
        
        if 'warnings' in metrics:
            self.warnings.extend(metrics['warnings'])
        
        self.last_updated = datetime.datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert risk metrics to a dictionary.
        
        Returns:
            Dictionary representation of risk metrics.
        """
        return {
            'position_metrics': self.position_metrics,
            'portfolio_metrics': self.portfolio_metrics,
            'drawdown': self.drawdown,
            'exposure': self.exposure,
            'volatility': self.volatility,
            'value_at_risk': self.value_at_risk,
            'correlation_matrix': self.correlation_matrix.to_dict() if self.correlation_matrix is not None else None,
            'violations_count': len(self.violations),
            'warnings_count': len(self.warnings),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }


class RiskAwareStrategyLifecycleManager(StrategyLifecycleManager):
    """
    Risk-aware extension of the Strategy Lifecycle Manager.
    
    This class extends the standard Strategy Lifecycle Manager to integrate with
    the risk management system, ensuring that all strategies operate within
    defined risk parameters.
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        log_manager: Optional[LogManager] = None,
        state_dir: Optional[str] = None,
        risk_config: Optional[ExecutionRiskConfig] = None,
        portfolio_risk_controller: Optional[PortfolioRiskController] = None,
        enforce_risk_limits: bool = True,
        auto_adjust_position_sizes: bool = True,
        emergency_stop_on_violation: bool = True
    ):
        """
        Initialize the risk-aware strategy lifecycle manager.
        
        Args:
            config_manager: Configuration manager instance.
            log_manager: Log manager instance.
            state_dir: Directory to store strategy state files.
            risk_config: Risk configuration.
            portfolio_risk_controller: Portfolio risk controller instance.
            enforce_risk_limits: Whether to enforce risk limits.
            auto_adjust_position_sizes: Whether to automatically adjust position sizes.
            emergency_stop_on_violation: Whether to emergency stop strategies on risk violation.
        """
        super().__init__(config_manager, log_manager, state_dir)
        
        # Initialize risk management components
        self.risk_config = risk_config or ExecutionRiskConfig()
        self.risk_manager = ExecutionRiskManager(self.risk_config)
        self.portfolio_risk_controller = portfolio_risk_controller or PortfolioRiskController()
        self.position_risk_validator = PositionRiskValidator()
        self.portfolio_risk_integration = PortfolioRiskIntegration()
        
        # Risk tracking and configuration
        self.enforce_risk_limits = enforce_risk_limits
        self.auto_adjust_position_sizes = auto_adjust_position_sizes
        self.emergency_stop_on_violation = emergency_stop_on_violation
        self.risk_metrics: Dict[str, RiskMetrics] = {}
        
        # Additional state tracking
        self.violations: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        
        self.logger.info("Risk-aware strategy lifecycle manager initialized")
    
    def register_strategy(
        self,
        strategy: Strategy,
        strategy_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
        warmup_bars: int = DEFAULT_WARMUP_BARS,
        auto_initialize: bool = False,
        risk_limits: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a strategy with additional risk limits.
        
        Args:
            strategy: The strategy instance to manage.
            strategy_id: Optional unique identifier for the strategy.
            parameters: Strategy parameters.
            dependencies: Strategy dependencies (data sources, models, etc.).
            warmup_bars: Number of bars needed for warm-up.
            auto_initialize: Whether to automatically initialize the strategy.
            risk_limits: Strategy-specific risk limits.
            
        Returns:
            The strategy ID.
        """
        # Register strategy with parent class
        strategy_id = super().register_strategy(
            strategy=strategy,
            strategy_id=strategy_id,
            parameters=parameters,
            dependencies=dependencies,
            warmup_bars=warmup_bars,
            auto_initialize=False  # We'll handle initialization ourselves
        )
        
        # Initialize risk metrics
        self.risk_metrics[strategy_id] = RiskMetrics()
        
        # Add risk limits to strategy info
        strategy_info = self.strategies[strategy_id]
        strategy_info["risk_limits"] = risk_limits or {}
        
        # Initialize if requested
        if auto_initialize:
            self.initialize_strategy(strategy_id)
        
        return strategy_id
    
    def initialize_strategy(self, strategy_id: str) -> bool:
        """
        Initialize a registered strategy with risk validation.
        
        Args:
            strategy_id: ID of the strategy to initialize.
            
        Returns:
            True if initialization was successful, False otherwise.
            
        Raises:
            ValueError: If strategy is not registered.
            RiskViolationError: If initialization would violate risk limits.
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
        
        # Check if adding this strategy would violate portfolio risk limits
        if self.enforce_risk_limits:
            strategy_info = self.strategies[strategy_id]
            portfolio_state = self._build_portfolio_state()
            
            # Add this strategy to the portfolio state for validation
            portfolio_state["strategies"][strategy_id] = {
                "name": strategy_info["instance"].__class__.__name__,
                "type": strategy_info["instance"].__class__.__name__,
                "symbols": strategy_info["instance"].config.symbols,
                "risk_limits": strategy_info["risk_limits"]
            }
            
            # Validate portfolio risk
            validation_results = self.portfolio_risk_integration.validate_portfolio(portfolio_state)
            
            # Check for violations
            violations = [r for r in validation_results if r.status == RiskValidationStatus.FAILED]
            if violations and self.enforce_risk_limits:
                error_message = f"Strategy {strategy_id} initialization would violate risk limits: " + \
                               ", ".join([v.message for v in violations])
                self.logger.error(error_message)
                
                # Track violations
                for violation in violations:
                    self.violations.append({
                        "timestamp": datetime.datetime.now(),
                        "strategy_id": strategy_id,
                        "message": violation.message,
                        "details": violation.details,
                        "check_name": violation.check_name
                    })
                
                # Update risk metrics
                self.risk_metrics[strategy_id].update({
                    "violations": violations
                })
                
                if self.enforce_risk_limits:
                    raise RiskViolationError(error_message)
        
        # Call parent class implementation
        return super().initialize_strategy(strategy_id)
    
    def start_strategy(self, strategy_id: str) -> bool:
        """
        Start a strategy with risk validation.
        
        Args:
            strategy_id: ID of the strategy to start.
            
        Returns:
            True if strategy was started successfully.
            
        Raises:
            ValueError: If strategy is not registered or not ready.
            RiskViolationError: If starting would violate risk limits.
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
        
        # Check current risk status before starting
        if self.enforce_risk_limits:
            strategy_info = self.strategies[strategy_id]
            portfolio_state = self._build_portfolio_state()
            
            # Validate portfolio risk
            validation_results = self.portfolio_risk_integration.validate_portfolio(portfolio_state)
            
            # Check for violations
            violations = [r for r in validation_results if r.status == RiskValidationStatus.FAILED]
            if violations:
                error_message = f"Cannot start strategy {strategy_id} due to risk violations: " + \
                              ", ".join([v.message for v in violations])
                self.logger.error(error_message)
                
                # Track violations
                for violation in violations:
                    self.violations.append({
                        "timestamp": datetime.datetime.now(),
                        "strategy_id": strategy_id,
                        "message": violation.message,
                        "details": violation.details,
                        "check_name": violation.check_name
                    })
                
                # Update risk metrics
                self.risk_metrics[strategy_id].update({
                    "violations": violations
                })
                
                if self.enforce_risk_limits:
                    raise RiskViolationError(error_message)
        
        # Call parent class implementation
        return super().start_strategy(strategy_id)
    
    def process_data(
        self, 
        strategy_id: str, 
        data: Union[pd.DataFrame, Dict]
    ) -> Dict[str, Any]:
        """
        Process data with risk validation and adjustment.
        
        Args:
            strategy_id: ID of the strategy to process data with.
            data: New data to process.
            
        Returns:
            Dictionary with processing results.
            
        Raises:
            ValueError: If strategy is not registered or not running.
            RiskViolationError: If processing would violate risk limits.
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
        
        strategy_info = self.strategies[strategy_id]
        
        # Skip if not running
        if strategy_info["state"] != StrategyState.RUNNING:
            return {"status": "skipped", "reason": f"Strategy is not running (state: {strategy_info['state'].value})"}
        
        # Get strategy instance
        strategy = strategy_info["instance"]
        
        try:
            # Process data with strategy
            results = strategy.process_data(data)
            
            # Check for risk violations in the results
            if self.enforce_risk_limits and results:
                # Extract portfolio state after this data processing
                portfolio_state = self._build_portfolio_state()
                
                # Update with latest results
                if strategy_id not in portfolio_state["strategies"]:
                    portfolio_state["strategies"][strategy_id] = {}
                
                if hasattr(results, "to_dict"):
                    # If results is a DataFrame or has to_dict method
                    portfolio_state["strategies"][strategy_id]["results"] = results.to_dict()
                else:
                    # Otherwise, assume it's already a dict
                    portfolio_state["strategies"][strategy_id]["results"] = results
                
                # Validate portfolio risk
                validation_results = self.portfolio_risk_integration.validate_portfolio(portfolio_state)
                
                # Check for violations and warnings
                violations = [r for r in validation_results if r.status == RiskValidationStatus.FAILED]
                warnings = [r for r in validation_results if r.status == RiskValidationStatus.WARNING]
                
                # Update risk metrics
                self.risk_metrics[strategy_id].update({
                    "violations": violations,
                    "warnings": warnings
                })
                
                # Track violations
                for violation in violations:
                    self.violations.append({
                        "timestamp": datetime.datetime.now(),
                        "strategy_id": strategy_id,
                        "message": violation.message,
                        "details": violation.details,
                        "check_name": violation.check_name
                    })
                
                # Track warnings
                for warning in warnings:
                    self.warnings.append({
                        "timestamp": datetime.datetime.now(),
                        "strategy_id": strategy_id,
                        "message": warning.message,
                        "details": warning.details,
                        "check_name": warning.check_name
                    })
                
                # Handle violations if present
                if violations:
                    error_message = f"Risk violations detected for strategy {strategy_id}: " + \
                                  ", ".join([v.message for v in violations])
                    self.logger.error(error_message)
                    
                    # Emergency stop if configured
                    if self.emergency_stop_on_violation:
                        self.logger.warning(f"Emergency stopping strategy {strategy_id} due to risk violations")
                        self.stop_strategy(strategy_id, force=True)
                        raise RiskViolationError(error_message)
            
            # Update last update time
            strategy_info["last_update_time"] = datetime.datetime.now()
            
            return results
            
        except Exception as e:
            self.logger.error(f"Strategy {strategy_id} data processing failed: {str(e)}")
            if isinstance(e, RiskViolationError):
                # Re-raise risk violations
                raise
            else:
                # Wrap other errors
                raise StrategyError(f"Strategy {strategy_id} data processing failed: {str(e)}")
    
    def get_strategy_risk_metrics(self, strategy_id: str) -> Dict[str, Any]:
        """
        Get risk metrics for a strategy.
        
        Args:
            strategy_id: ID of the strategy.
            
        Returns:
            Dictionary with risk metrics.
            
        Raises:
            ValueError: If strategy is not registered.
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
        
        if strategy_id not in self.risk_metrics:
            self.risk_metrics[strategy_id] = RiskMetrics()
        
        return self.risk_metrics[strategy_id].to_dict()
    
    def get_portfolio_risk_metrics(self) -> Dict[str, Any]:
        """
        Get risk metrics for the entire portfolio.
        
        Returns:
            Dictionary with portfolio risk metrics.
        """
        portfolio_state = self._build_portfolio_state()
        
        # Calculate portfolio metrics
        try:
            metrics = self.portfolio_risk_controller.calculate_portfolio_metrics(
                weights=portfolio_state.get("weights", {}),
                returns=portfolio_state.get("returns", None),
                include_advanced=True
            )
        except Exception as e:
            self.logger.error(f"Error calculating portfolio metrics: {str(e)}")
            metrics = {}
        
        # Add additional info
        metrics["strategy_count"] = len(self.strategies)
        metrics["active_strategy_count"] = len([
            s for s in self.strategies.values() 
            if s["state"] == StrategyState.RUNNING
        ])
        metrics["violation_count"] = len(self.violations)
        metrics["warning_count"] = len(self.warnings)
        
        return metrics
    
    def check_risk_limits(self, strategy_id: Optional[str] = None) -> List[RiskCheckResult]:
        """
        Check risk limits for a strategy or all strategies.
        
        Args:
            strategy_id: Optional ID of the strategy to check. If None, check all strategies.
            
        Returns:
            List of risk check results.
        """
        if strategy_id and strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} is not registered")
        
        portfolio_state = self._build_portfolio_state()
        
        # Check specific strategy if requested
        if strategy_id:
            strategy_info = self.strategies[strategy_id]
            
            # Extract strategy-specific state
            strategy_state = {
                "name": strategy_info["instance"].__class__.__name__,
                "type": strategy_info["instance"].__class__.__name__,
                "symbols": strategy_info["instance"].config.symbols,
                "risk_limits": strategy_info.get("risk_limits", {})
            }
            
            # Check position risk
            try:
                position_results = self.position_risk_validator.validate_positions(
                    strategy_state, portfolio_state
                )
            except Exception as e:
                self.logger.error(f"Error checking position risk for strategy {strategy_id}: {str(e)}")
                position_results = []
            
            return position_results
        
        # Otherwise check entire portfolio
        try:
            portfolio_results = self.portfolio_risk_integration.validate_portfolio(portfolio_state)
        except Exception as e:
            self.logger.error(f"Error checking portfolio risk: {str(e)}")
            portfolio_results = []
        
        return portfolio_results
    
    def get_risk_violations(self, 
                          strategy_id: Optional[str] = None, 
                          limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent risk violations.
        
        Args:
            strategy_id: Optional ID of the strategy to get violations for.
            limit: Maximum number of violations to return.
            
        Returns:
            List of risk violations.
        """
        if strategy_id:
            if strategy_id not in self.strategies:
                raise ValueError(f"Strategy {strategy_id} is not registered")
            
            # Filter violations by strategy ID
            strategy_violations = [
                v for v in self.violations if v["strategy_id"] == strategy_id
            ]
            
            # Sort by timestamp (newest first) and limit
            return sorted(
                strategy_violations,
                key=lambda v: v["timestamp"],
                reverse=True
            )[:limit]
        
        # Return all violations, sorted by timestamp (newest first) and limited
        return sorted(
            self.violations,
            key=lambda v: v["timestamp"],
            reverse=True
        )[:limit]
    
    def _build_portfolio_state(self) -> Dict[str, Any]:
        """
        Build the current portfolio state.
        
        Returns:
            Dictionary with portfolio state.
        """
        portfolio_state = {
            "strategies": {},
            "positions": {},
            "metrics": {},
            "weights": {},
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add strategies
        for strategy_id, strategy_info in self.strategies.items():
            if strategy_info["state"] in [StrategyState.RUNNING, StrategyState.PAUSED, StrategyState.READY]:
                strategy = strategy_info["instance"]
                
                portfolio_state["strategies"][strategy_id] = {
                    "name": strategy.__class__.__name__,
                    "type": strategy.__class__.__name__,
                    "symbols": strategy.config.symbols,
                    "risk_limits": strategy_info.get("risk_limits", {}),
                    "state": strategy_info["state"].value
                }
                
                # Add positions from strategy state
                strategy_state = strategy.get_state()
                portfolio_state["positions"][strategy_id] = strategy_state.positions
        
        return portfolio_state 