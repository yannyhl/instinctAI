"""
Circuit Breakers Example
-----------------------
This example demonstrates how to use the circuit breakers module to automatically
stop trading when certain risk thresholds are exceeded.
"""

import time
import random
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Import our circuit breakers
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def demonstrate_volatility_circuit_breaker():
    """Demonstrate the volatility circuit breaker."""
    logger.info("Demonstrating volatility circuit breaker")
    
    # Create a volatility circuit breaker
    cb = VolatilityCircuitBreaker(
        volatility_window=10,
        volatility_threshold=0.02,  # 2% volatility
        min_periods=5,
        warning_threshold=0.8,
        cooling_period=3  # 3 seconds for demonstration
    )
    
    # Generate some random returns data
    returns = []
    statuses = []
    
    for i in range(50):
        # Normal returns with occasional spike
        if i >= 20 and i < 25:
            # Period of high volatility
            returns.append(random.uniform(-0.05, 0.05))
        else:
            # Normal volatility
            returns.append(random.uniform(-0.01, 0.01))
        
        # Update the circuit breaker
        status = cb.update(returns[-1])
        statuses.append(status.value)
        
        logger.info(f"Step {i+1}: Return={returns[-1]:.4f}, Status={status.value}")
        
        # If triggered, wait for cooling period
        if status == CircuitBreakerStatus.TRIGGERED or status == CircuitBreakerStatus.COOLING:
            logger.warning(f"Circuit breaker triggered at step {i+1}, waiting for cooling period")
            time.sleep(1)
            
            # Manually reset after a few steps
            if i == 27:
                cb.reset()
                logger.info("Manually reset circuit breaker")
    
    # Plot results
    plt.figure(figsize=(12, 8))
    
    # Plot returns
    plt.subplot(2, 1, 1)
    plt.plot(returns, 'b-', label='Returns')
    plt.title('Returns Data')
    plt.ylabel('Return')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Calculate and plot volatility
    volatility = []
    for i in range(len(returns)):
        if i < cb.volatility_window:
            volatility.append(np.nan)
        else:
            volatility.append(np.std(returns[i-cb.volatility_window:i]))
    
    plt.subplot(2, 1, 2)
    plt.plot(volatility, 'g-', label='Volatility')
    plt.axhline(y=cb.volatility_threshold, color='r', linestyle='--', label='Threshold')
    plt.axhline(y=cb.volatility_threshold * cb.warning_threshold, color='y', linestyle='--', label='Warning')
    
    # Plot status
    for i, status in enumerate(statuses):
        if status == 'triggered':
            plt.axvline(x=i, color='r', alpha=0.3)
        elif status == 'warning':
            plt.axvline(x=i, color='y', alpha=0.3)
        elif status == 'cooling':
            plt.axvline(x=i, color='m', alpha=0.3)
    
    plt.title('Volatility and Circuit Breaker Status')
    plt.ylabel('Volatility')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    return cb

def demonstrate_drawdown_circuit_breaker():
    """Demonstrate the drawdown circuit breaker."""
    logger.info("Demonstrating drawdown circuit breaker")
    
    # Create a drawdown circuit breaker
    cb = DrawdownCircuitBreaker(
        drawdown_threshold=0.1,  # 10% drawdown
        warning_threshold=0.7,
        cooling_period=3  # 3 seconds for demonstration
    )
    
    # Generate equity curve with drawdown
    equity = [100000.0]  # Starting equity
    statuses = []
    
    for i in range(100):
        # Simulate equity changes
        if i < 30:
            # Growth phase
            change = random.uniform(0.001, 0.015)
        elif i < 60:
            # Drawdown phase
            change = random.uniform(-0.02, 0.005)
        else:
            # Recovery phase
            change = random.uniform(-0.005, 0.015)
        
        equity.append(equity[-1] * (1 + change))
        
        # Update the circuit breaker
        status = cb.update(equity[-1])
        statuses.append(status.value)
        
        logger.info(f"Step {i+1}: Equity={equity[-1]:.2f}, Drawdown={cb.current_drawdown:.4f}, Status={status.value}")
        
        # If triggered, wait for cooling period
        if status == CircuitBreakerStatus.TRIGGERED or status == CircuitBreakerStatus.COOLING:
            logger.warning(f"Circuit breaker triggered at step {i+1} with drawdown {cb.current_drawdown:.4f}")
            time.sleep(1)
            
            # Manually reset after a few steps
            if i == 65:
                cb.reset_peak()
                logger.info(f"Manually reset drawdown peak to {cb.equity_peak}")
    
    # Plot results
    plt.figure(figsize=(12, 8))
    
    # Plot equity curve
    plt.subplot(2, 1, 1)
    plt.plot(equity, 'b-', label='Equity')
    plt.title('Equity Curve')
    plt.ylabel('Equity')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Calculate and plot drawdown
    drawdown = []
    peak = equity[0]
    for e in equity:
        peak = max(peak, e)
        drawdown.append(1.0 - (e / peak))
    
    plt.subplot(2, 1, 2)
    plt.plot(drawdown, 'r-', label='Drawdown')
    plt.axhline(y=cb.drawdown_threshold, color='r', linestyle='--', label='Threshold')
    plt.axhline(y=cb.drawdown_threshold * cb.warning_threshold, color='y', linestyle='--', label='Warning')
    
    # Plot status
    for i, status in enumerate(statuses):
        if status == 'triggered':
            plt.axvline(x=i, color='r', alpha=0.3)
        elif status == 'warning':
            plt.axvline(x=i, color='y', alpha=0.3)
        elif status == 'cooling':
            plt.axvline(x=i, color='m', alpha=0.3)
    
    plt.title('Drawdown and Circuit Breaker Status')
    plt.ylabel('Drawdown')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    return cb

def demonstrate_circuit_breaker_manager():
    """Demonstrate the circuit breaker manager."""
    logger.info("Demonstrating circuit breaker manager")
    
    # Create multiple circuit breakers
    volatility_cb = VolatilityCircuitBreaker(
        volatility_window=10,
        volatility_threshold=0.02,
        warning_threshold=0.7
    )
    
    drawdown_cb = DrawdownCircuitBreaker(
        drawdown_threshold=0.1,
        warning_threshold=0.7
    )
    
    frequency_cb = FrequencyCircuitBreaker(
        max_trades=5,
        time_window=10  # 10 seconds
    )
    
    # Create a circuit breaker manager
    manager = CircuitBreakerManager([
        volatility_cb,
        drawdown_cb,
        frequency_cb
    ])
    
    # Simulate market and trading conditions
    equity = 100000.0
    returns = []
    trades = 0
    system_halted = False
    manager_status_history = []
    
    for i in range(100):
        # Skip trading if system is halted
        if system_halted:
            logger.warning(f"Step {i+1}: System halted, skipping trading")
            manager_status_history.append(manager.is_triggered)
            
            # Reset after 10 steps
            if i % 10 == 0:
                logger.info("Attempting to reset circuit breakers")
                manager.reset_all()
                system_halted = manager.is_triggered
                
            continue
        
        # Simulate returns (with a volatility spike in the middle)
        if 40 <= i < 50:
            # High volatility period
            returns.append(random.uniform(-0.05, 0.05))
        else:
            # Normal volatility
            returns.append(random.uniform(-0.01, 0.01))
        
        # Update equity
        equity *= (1 + returns[-1])
        
        # Simulate trading activity
        if i % 3 == 0 and not system_halted:
            # Execute a trade
            trades += 1
            frequency_cb.update()
            
            # Check if we've exceeded trading frequency
            if frequency_cb.status == CircuitBreakerStatus.TRIGGERED:
                logger.warning(f"Step {i+1}: Trading frequency circuit breaker triggered")
        
        # Update other circuit breakers
        if len(returns) > 1:
            volatility_cb.update(returns[-1])
        drawdown_cb.update(equity)
        
        # Check if any circuit breaker is triggered
        if manager.is_triggered and not system_halted:
            logger.warning(f"Step {i+1}: Circuit breaker manager TRIGGERED. Halting trading.")
            logger.warning(f"Triggered breakers: {manager.triggered_breakers}")
            system_halted = True
        
        # Record manager status
        manager_status_history.append(manager.is_triggered)
        
        # Log status
        logger.info(f"Step {i+1}: Equity={equity:.2f}, Return={returns[-1] if returns else 0:.4f}, "
                   f"Trades={trades}, System Halted={system_halted}")
    
    # Get final status
    final_status = manager.get_status()
    logger.info(f"Final status: {final_status}")
    
    # Plot results
    plt.figure(figsize=(12, 10))
    
    # Plot equity
    plt.subplot(3, 1, 1)
    equity_series = [100000]
    for r in returns:
        equity_series.append(equity_series[-1] * (1 + r))
    plt.plot(equity_series, 'b-', label='Equity')
    
    # Highlight system halted periods
    for i, triggered in enumerate(manager_status_history):
        if triggered:
            plt.axvspan(i, i+1, color='r', alpha=0.3)
    
    plt.title('Equity and System Status')
    plt.ylabel('Equity')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot returns and volatility
    plt.subplot(3, 1, 2)
    plt.plot(returns, 'g-', label='Returns')
    
    # Calculate and plot volatility
    volatility = []
    for i in range(len(returns)):
        if i < volatility_cb.volatility_window:
            volatility.append(np.nan)
        else:
            volatility.append(np.std(returns[i-volatility_cb.volatility_window:i]))
    
    plt.plot(volatility, 'm-', label='Volatility')
    plt.axhline(y=volatility_cb.volatility_threshold, color='r', linestyle='--', label='Volatility Threshold')
    
    # Highlight system halted periods
    for i, triggered in enumerate(manager_status_history):
        if triggered:
            plt.axvspan(i, i+1, color='r', alpha=0.3)
    
    plt.title('Returns and Volatility')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot trading frequency
    plt.subplot(3, 1, 3)
    trade_times = [i for i in range(100) if i % 3 == 0 and i < len(manager_status_history) and not manager_status_history[i]]
    plt.stem(trade_times, [1] * len(trade_times), linefmt='b-', markerfmt='bo', label='Trades')
    
    # Highlight system halted periods
    for i, triggered in enumerate(manager_status_history):
        if triggered:
            plt.axvspan(i, i+1, color='r', alpha=0.3)
    
    plt.title('Trading Activity')
    plt.ylabel('Trade')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    return manager

def main():
    """Run the circuit breaker examples."""
    try:
        logger.info("Starting circuit breaker examples")
        
        # Demonstrate volatility circuit breaker
        volatility_cb = demonstrate_volatility_circuit_breaker()
        
        # Demonstrate drawdown circuit breaker
        drawdown_cb = demonstrate_drawdown_circuit_breaker()
        
        # Demonstrate circuit breaker manager
        manager = demonstrate_circuit_breaker_manager()
        
        logger.info("Circuit breaker examples completed")
        
    except Exception as e:
        logger.error(f"Error in circuit breaker examples: {e}", exc_info=True)

if __name__ == "__main__":
    main() 