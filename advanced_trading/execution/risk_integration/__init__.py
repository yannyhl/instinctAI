"""
Risk Integration Layer

This module facilitates integration between execution strategies and risk management
components. It enables pre-trade and post-trade risk checks at both position level
and portfolio level, ensuring that execution strategies comply with risk management
rules.

Key components:
- ExecutionRiskManager: Coordinates pre-trade and post-trade risk checks
- PreTradeRiskCheck: Interface for checks performed before order execution
- PostTradeRiskAnalysis: Interface for analysis performed after execution
- PositionRiskValidator: Validates and monitors position-level risk metrics
- PortfolioRiskIntegration: Connects execution with portfolio-level risk constraints

This layer acts as a bridge between the execution strategies framework and the
risk management framework, ensuring that trading decisions adhere to the overall
risk management policies of the system.
"""

# Primary components
from advanced_trading.execution.risk_integration.risk_manager import (
    RiskValidationStatus,
    RiskCheckResult,
    ExecutionRiskConfig,
    ExecutionRiskManager
)

from advanced_trading.execution.risk_integration.checks import (
    PreTradeRiskCheck,
    PostTradeRiskAnalysis,
    # Pre-trade checks
    PositionSizeCheck,
    MaxDrawdownCheck,
    ExposureCheck,
    VolumePercentCheck,
    # Post-trade checks
    SlippageCheck
)

from advanced_trading.execution.risk_integration.position_risk import (
    PositionRiskStatus,
    PositionRiskMetrics,
    PositionRiskValidator
)

from advanced_trading.execution.risk_integration.portfolio_risk import (
    PortfolioRiskLevel,
    PortfolioRiskMetrics,
    PortfolioRiskIntegration
)

# Public API
__all__ = [
    # Core components
    'ExecutionRiskManager',
    'ExecutionRiskConfig',
    'RiskValidationStatus',
    'RiskCheckResult',
    
    # Risk check interfaces
    'PreTradeRiskCheck',
    'PostTradeRiskAnalysis',
    
    # Pre-trade checks
    'PositionSizeCheck',
    'MaxDrawdownCheck',
    'ExposureCheck',
    'VolumePercentCheck',
    
    # Post-trade checks
    'SlippageCheck',
    
    # Position-level risk
    'PositionRiskStatus',
    'PositionRiskMetrics',
    'PositionRiskValidator',
    
    # Portfolio risk integration
    'PortfolioRiskLevel',
    'PortfolioRiskMetrics',
    'PortfolioRiskIntegration'
] 