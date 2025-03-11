"""
Execution Safety Module
---------------------
This module provides safety mechanisms to protect trading systems during 
extreme market conditions or when the system behaves unexpectedly.

Components:
1. Circuit Breakers - Automatically stop trading when risk thresholds are exceeded
2. Emergency Protocols - Procedures for handling exceptional situations
3. Kill Switches - Mechanisms to immediately stop all trading activity
4. Position Unwinder - Systematically unwind positions to reduce risk
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import circuit breakers
try:
    from advanced_trading.execution.safety.circuit_breakers import (
        CircuitBreakerBase,
        CircuitBreakerStatus,
        VolatilityCircuitBreaker,
        DrawdownCircuitBreaker,
        SlippageCircuitBreaker,
        VolumeCircuitBreaker,
        FrequencyCircuitBreaker,
        CircuitBreakerManager
    )
    
    # Define public API
    __all__ = [
        'CircuitBreakerBase',
        'CircuitBreakerStatus',
        'VolatilityCircuitBreaker',
        'DrawdownCircuitBreaker',
        'SlippageCircuitBreaker',
        'VolumeCircuitBreaker',
        'FrequencyCircuitBreaker',
        'CircuitBreakerManager'
    ]
    
    logger.info("Execution safety module loaded successfully - Circuit breakers available")
except ImportError as e:
    logger.error(f"Error loading circuit breakers: {e}")
    __all__ = []

# Emergency protocol components
from advanced_trading.execution.safety.emergency import (
    EmergencyLevel,
    EmergencyEvent,
    EmergencyAction,
    EmergencyProtocol,
    EmergencyHandler
)

# Protection components
from advanced_trading.execution.safety.protection import (
    ExecutionFailureType,
    ExecutionAnomalyType,
    ExecutionFailure,
    ExecutionAnomaly,
    ProtectionAction,
    ExecutionFailureHandler,
    ExecutionAnomalyMonitor,
    TradingProtection,
    PauseExchangeTradingAction,
    RateThrottlingAction,
    OrderSizeReductionAction
)

# Public API
__all__ += [
    # Emergency protocols
    'EmergencyLevel',
    'EmergencyEvent',
    'EmergencyAction',
    'EmergencyProtocol',
    'EmergencyHandler',
    
    # Protection components
    'ExecutionFailureType',
    'ExecutionAnomalyType',
    'ExecutionFailure',
    'ExecutionAnomaly',
    'ProtectionAction',
    'ExecutionFailureHandler',
    'ExecutionAnomalyMonitor',
    'TradingProtection',
    'PauseExchangeTradingAction',
    'RateThrottlingAction',
    'OrderSizeReductionAction'
] 