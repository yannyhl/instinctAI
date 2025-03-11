"""
Execution Risk Manager

This module provides the central risk management component for execution strategies.
It coordinates pre-trade and post-trade risk checks, manages risk limits, and
integrates with both position-level and portfolio-level risk management systems.

The ExecutionRiskManager serves as the primary interface for execution strategies
to validate orders against risk parameters and analyze execution results from a
risk perspective.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

logger = logging.getLogger(__name__)


class RiskValidationStatus(Enum):
    """Status of a risk validation check."""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    ERROR = "error"  # For when the check itself encounters an error


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    status: RiskValidationStatus
    check_name: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    is_critical: bool = False
    mitigation_actions: List[str] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        """Check if the risk validation passed (potentially with warnings)."""
        return self.status in (RiskValidationStatus.PASSED, RiskValidationStatus.WARNING)
    
    @property
    def failed(self) -> bool:
        """Check if the risk validation failed."""
        return self.status in (RiskValidationStatus.FAILED, RiskValidationStatus.ERROR)


@dataclass
class ExecutionRiskConfig:
    """Configuration for the execution risk manager."""
    # General settings
    enabled: bool = True
    enforce_pre_trade_checks: bool = True
    log_all_checks: bool = True
    
    # Position-level limits
    max_position_size_usd: float = float('inf')
    max_position_size_percent: float = 0.1  # 10% of portfolio
    max_position_notional: Dict[str, float] = field(default_factory=dict)  # By asset
    
    # Order limits
    max_order_size_usd: float = float('inf')
    max_order_size_percent_of_position: float = 1.0  # 100% of position
    max_order_notional: Dict[str, float] = field(default_factory=dict)  # By asset
    
    # Market impact limits
    max_volume_percent: float = 0.1  # 10% of market volume
    max_slippage_percent: float = 0.01  # 1% max slippage
    
    # Portfolio-level constraints
    max_portfolio_drawdown: float = 0.1  # 10% max drawdown
    max_daily_loss: float = 0.05  # 5% max daily loss
    max_correlation_allowed: float = 0.7  # Max correlation between positions
    
    # Post-trade analysis
    track_slippage: bool = True
    track_market_impact: bool = True
    analyze_execution_quality: bool = True
    
    # Custom checks
    custom_pre_trade_checks: List[str] = field(default_factory=list)
    custom_post_trade_checks: List[str] = field(default_factory=list)


class ExecutionRiskManager:
    """
    Central component for managing risk during order execution.
    
    The ExecutionRiskManager provides methods for validating orders against
    risk parameters before execution (pre-trade checks) and analyzing execution
    results after trades are completed (post-trade analysis).
    
    It integrates with both position-level and portfolio-level risk management
    systems to ensure a comprehensive risk management approach.
    """
    
    def __init__(self, config: Optional[ExecutionRiskConfig] = None):
        """
        Initialize the execution risk manager.
        
        Args:
            config: Risk management configuration
        """
        self.config = config or ExecutionRiskConfig()
        self.pre_trade_checks: Dict[str, Callable] = {}
        self.post_trade_checks: Dict[str, Callable] = {}
        self.check_history: List[RiskCheckResult] = []
        self.recent_violations: List[RiskCheckResult] = []
        self.enabled = self.config.enabled
        
        # Initialize with default checks
        self._register_default_checks()
        
    def _register_default_checks(self) -> None:
        """Register the default pre-trade and post-trade checks."""
        # This will be populated when we implement the specific check classes
        pass
    
    def register_pre_trade_check(self, name: str, check_function: Callable) -> None:
        """
        Register a pre-trade risk check.
        
        Args:
            name: Unique name for the check
            check_function: Function that performs the check and returns a RiskCheckResult
        """
        if name in self.pre_trade_checks:
            logger.warning(f"Overwriting existing pre-trade check: {name}")
        
        self.pre_trade_checks[name] = check_function
        logger.info(f"Registered pre-trade check: {name}")
    
    def register_post_trade_check(self, name: str, check_function: Callable) -> None:
        """
        Register a post-trade risk check or analysis.
        
        Args:
            name: Unique name for the check/analysis
            check_function: Function that performs the check and returns a RiskCheckResult
        """
        if name in self.post_trade_checks:
            logger.warning(f"Overwriting existing post-trade check: {name}")
        
        self.post_trade_checks[name] = check_function
        logger.info(f"Registered post-trade check: {name}")
    
    def validate_order(self, 
                     order: Dict[str, Any], 
                     portfolio_state: Dict[str, Any],
                     market_data: Dict[str, Any]) -> List[RiskCheckResult]:
        """
        Validate an order against all pre-trade risk checks.
        
        Args:
            order: Order details including symbol, size, side, etc.
            portfolio_state: Current state of the portfolio
            market_data: Relevant market data for risk calculations
            
        Returns:
            List of risk check results for all pre-trade checks
        """
        if not self.enabled:
            logger.warning("Risk manager is disabled. Skipping order validation.")
            return []
        
        results = []
        for name, check_func in self.pre_trade_checks.items():
            try:
                result = check_func(order, portfolio_state, market_data)
                results.append(result)
                
                if self.config.log_all_checks or result.status != RiskValidationStatus.PASSED:
                    level = logging.INFO if result.passed else logging.WARNING
                    logger.log(level, f"Risk check '{name}': {result.status.value} - {result.message}")
                
                if result.failed and result.is_critical:
                    logger.error(f"Critical risk check failed: {name} - {result.message}")
                    
            except Exception as e:
                error_result = RiskCheckResult(
                    status=RiskValidationStatus.ERROR,
                    check_name=name,
                    message=f"Error executing risk check: {str(e)}",
                    details={"error": str(e), "traceback": logging.traceback.format_exc()},
                    is_critical=True
                )
                results.append(error_result)
                logger.error(f"Error in risk check '{name}': {e}")
        
        # Store check history
        self.check_history.extend(results)
        
        # Store violations for later analysis
        violations = [r for r in results if r.failed]
        if violations:
            self.recent_violations.extend(violations)
            if len(self.recent_violations) > 100:  # Limit the size
                self.recent_violations = self.recent_violations[-100:]
        
        return results
    
    def is_order_valid(self, 
                     order: Dict[str, Any], 
                     portfolio_state: Dict[str, Any],
                     market_data: Dict[str, Any]) -> Tuple[bool, List[RiskCheckResult]]:
        """
        Check if an order passes all critical pre-trade risk checks.
        
        Args:
            order: Order details including symbol, size, side, etc.
            portfolio_state: Current state of the portfolio
            market_data: Relevant market data for risk calculations
            
        Returns:
            Tuple containing:
            - Boolean indicating if the order is valid
            - List of risk check results
        """
        results = self.validate_order(order, portfolio_state, market_data)
        
        # Order is invalid if any critical check failed
        critical_failures = [r for r in results if r.failed and r.is_critical]
        is_valid = len(critical_failures) == 0
        
        return is_valid, results
    
    def analyze_execution(self, 
                        order: Dict[str, Any],
                        execution_details: Dict[str, Any],
                        portfolio_state: Dict[str, Any],
                        market_data: Dict[str, Any]) -> List[RiskCheckResult]:
        """
        Perform post-trade risk analysis on an executed order.
        
        Args:
            order: Original order details
            execution_details: Details of how the order was executed
            portfolio_state: Current state of the portfolio
            market_data: Relevant market data for risk calculations
            
        Returns:
            List of risk check results for all post-trade analyses
        """
        if not self.enabled:
            logger.warning("Risk manager is disabled. Skipping execution analysis.")
            return []
        
        results = []
        for name, check_func in self.post_trade_checks.items():
            try:
                result = check_func(order, execution_details, portfolio_state, market_data)
                results.append(result)
                
                if self.config.log_all_checks or result.status != RiskValidationStatus.PASSED:
                    level = logging.INFO if result.passed else logging.WARNING
                    logger.log(level, f"Post-trade analysis '{name}': {result.status.value} - {result.message}")
                
            except Exception as e:
                error_result = RiskCheckResult(
                    status=RiskValidationStatus.ERROR,
                    check_name=name,
                    message=f"Error executing post-trade analysis: {str(e)}",
                    details={"error": str(e), "traceback": logging.traceback.format_exc()}
                )
                results.append(error_result)
                logger.error(f"Error in post-trade analysis '{name}': {e}")
        
        # Store check history
        self.check_history.extend(results)
        
        return results
    
    def get_recent_violations(self, 
                            count: int = 10, 
                            check_name: Optional[str] = None) -> List[RiskCheckResult]:
        """
        Get recent risk check violations.
        
        Args:
            count: Maximum number of violations to return
            check_name: Optional filter for specific check
            
        Returns:
            List of recent risk check violations
        """
        violations = self.recent_violations
        
        if check_name:
            violations = [v for v in violations if v.check_name == check_name]
            
        return violations[-count:]
    
    def get_risk_status(self) -> Dict[str, Any]:
        """
        Get the current status of the risk management system.
        
        Returns:
            Dictionary with current risk management status
        """
        total_checks = len(self.check_history)
        violations = [c for c in self.check_history if c.failed]
        critical_violations = [v for v in violations if v.is_critical]
        
        recent_checks = self.check_history[-100:] if self.check_history else []
        recent_violations = [c for c in recent_checks if c.failed]
        
        by_check = {}
        for check_name in set(c.check_name for c in self.check_history):
            check_results = [c for c in self.check_history if c.check_name == check_name]
            check_violations = [c for c in check_results if c.failed]
            by_check[check_name] = {
                "total": len(check_results),
                "violations": len(check_violations),
                "violation_rate": len(check_violations) / len(check_results) if check_results else 0
            }
        
        return {
            "enabled": self.enabled,
            "total_checks": total_checks,
            "total_violations": len(violations),
            "critical_violations": len(critical_violations),
            "recent_checks": len(recent_checks),
            "recent_violations": len(recent_violations),
            "by_check": by_check
        }
    
    def enable(self) -> None:
        """Enable the risk management system."""
        self.enabled = True
        logger.info("Risk management system enabled")
    
    def disable(self) -> None:
        """Disable the risk management system."""
        self.enabled = False
        logger.warning("Risk management system disabled")


# Public API
__all__ = [
    'RiskValidationStatus',
    'RiskCheckResult',
    'ExecutionRiskConfig',
    'ExecutionRiskManager'
] 