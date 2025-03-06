"""
System Service

This module provides backend services for interacting with system components.
"""

import os
import sys
import logging
import time
import json
import threading
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict, deque

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import core modules
from core import config_manager, metrics, logging as log_manager, tracing

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.system_service"})

# Cache for system metrics
_cpu_history = deque(maxlen=100)  # Store 100 data points
_memory_history = deque(maxlen=100)  # Store 100 data points
_last_update = 0
_update_interval = 5  # seconds


def _update_metrics():
    """Update system metrics cache"""
    global _last_update
    
    # Only update every _update_interval seconds
    current_time = time.time()
    if current_time - _last_update < _update_interval:
        return
    
    _last_update = current_time
    timestamp = datetime.now()
    
    # Update CPU usage
    cpu_percent = psutil.cpu_percent()
    _cpu_history.append({
        "timestamp": timestamp,
        "usage": cpu_percent
    })
    
    # Update memory usage
    memory = psutil.virtual_memory()
    _memory_history.append({
        "timestamp": timestamp,
        "usage": memory.percent,
        "used": memory.used,
        "total": memory.total
    })


def get_system_state() -> Dict[str, Any]:
    """
    Get the current system state.
    
    Returns:
        Dictionary with system state information
    """
    # Update metrics
    _update_metrics()
    
    # Get system information
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Get component status
    components = get_component_status()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu_percent
        },
        "memory": {
            "percent": memory.percent,
            "used": memory.used,
            "total": memory.total
        },
        "disk": {
            "percent": disk.percent,
            "used": disk.used,
            "total": disk.total
        },
        "components": {comp["name"]: comp["status"] for comp in components}
    }


def get_component_status() -> List[Dict[str, Any]]:
    """
    Get the status of all system components.
    
    Returns:
        List of component status dictionaries
    """
    # In a real implementation, this would query all system components
    # For now, return placeholder data
    return [
        {
            "name": "Data Manager",
            "status": "online",
            "last_update": "2023-05-01 14:30:00",
            "details": "Processing 5 symbols"
        },
        {
            "name": "Strategy Manager",
            "status": "online",
            "last_update": "2023-05-01 14:30:00",
            "details": "3 active strategies"
        },
        {
            "name": "Exchange Connector (Binance)",
            "status": "online",
            "last_update": "2023-05-01 14:30:00",
            "details": "Connected"
        },
        {
            "name": "Exchange Connector (Coinbase)",
            "status": "degraded",
            "last_update": "2023-05-01 14:25:00",
            "details": "Rate limit reached (450/600)"
        },
        {
            "name": "Risk Manager",
            "status": "online",
            "last_update": "2023-05-01 14:30:00",
            "details": "No issues detected"
        }
    ]


def get_recent_logs(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent log entries.
    
    Args:
        limit: Maximum number of log entries to return
        
    Returns:
        List of log entry dictionaries
    """
    # In a real implementation, this would query the logging system
    # For now, return placeholder data
    logs = [
        {
            "timestamp": "2023-05-01 14:30:00",
            "level": "INFO",
            "component": "DataManager",
            "message": "Successfully updated market data for BTC/USD"
        },
        {
            "timestamp": "2023-05-01 14:29:45",
            "level": "INFO",
            "component": "StrategyManager",
            "message": "Strategy 'statistical_arbitrage' generated 2 signals"
        },
        {
            "timestamp": "2023-05-01 14:29:30",
            "level": "WARNING",
            "component": "ExchangeConnector",
            "message": "Coinbase API rate limit at 75% (450/600)"
        },
        {
            "timestamp": "2023-05-01 14:29:15",
            "level": "INFO",
            "component": "OrderManager",
            "message": "Order executed: BUY 0.5 BTC at $50,000"
        },
        {
            "timestamp": "2023-05-01 14:28:45",
            "level": "INFO",
            "component": "RiskManager",
            "message": "Position added: 0.5 BTC (2.5% of portfolio)"
        }
    ]
    
    # Generate additional placeholder logs
    components = ["DataManager", "StrategyManager", "ExchangeConnector", "OrderManager", "RiskManager"]
    levels = ["INFO", "INFO", "INFO", "WARNING", "ERROR"]  # Distribution of log levels
    
    for i in range(limit - len(logs)):
        timestamp = datetime.now() - timedelta(seconds=i*15)
        component_idx = (i * 7) % len(components)  # Pseudo-random selection
        level_idx = (i * 13) % len(levels)  # Pseudo-random selection
        
        logs.append({
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "level": levels[level_idx],
            "component": components[component_idx],
            "message": f"Placeholder log message {i+1}"
        })
    
    # Sort by timestamp (newest first)
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return logs[:limit]


def get_cpu_history() -> List[Dict[str, Any]]:
    """
    Get CPU usage history.
    
    Returns:
        List of CPU usage data points
    """
    # Update metrics
    _update_metrics()
    
    # Return the history
    return list(_cpu_history)


def get_memory_history() -> List[Dict[str, Any]]:
    """
    Get memory usage history.
    
    Returns:
        List of memory usage data points
    """
    # Update metrics
    _update_metrics()
    
    # Return the history
    return list(_memory_history)


def get_processes(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get a list of running processes.
    
    Args:
        limit: Maximum number of processes to return
        
    Returns:
        List of process dictionaries
    """
    processes = []
    
    # Get process information
    for proc in psutil.process_iter(['pid', 'name', 'status', 'create_time', 'cpu_percent', 'memory_percent']):
        try:
            # Get process info
            proc_info = proc.info
            
            # Add process to list
            processes.append({
                'pid': proc_info['pid'],
                'name': proc_info['name'],
                'status': proc_info['status'],
                'cpu_percent': proc_info['cpu_percent'],
                'memory_percent': proc_info['memory_percent'],
                'created': datetime.fromtimestamp(proc_info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Sort by CPU usage (highest first)
    processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
    
    return processes[:limit]


def start_system():
    """Start the trading system"""
    logger.info("Starting trading system")
    # In a real implementation, this would start the trading system
    return {"success": True, "message": "System started successfully"}


def stop_system(mode: str = "graceful"):
    """
    Stop the trading system.
    
    Args:
        mode: Shutdown mode (graceful or emergency)
        
    Returns:
        Success status and message
    """
    logger.info(f"Stopping trading system (mode: {mode})")
    # In a real implementation, this would stop the trading system
    return {"success": True, "message": f"System stopped successfully ({mode} shutdown)"}


def restart_component(component_name: str):
    """
    Restart a specific system component.
    
    Args:
        component_name: Name of the component to restart
        
    Returns:
        Success status and message
    """
    logger.info(f"Restarting component: {component_name}")
    # In a real implementation, this would restart the specified component
    return {"success": True, "message": f"Component '{component_name}' restarted successfully"} 