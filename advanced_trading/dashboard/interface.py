"""
Dashboard Interface

This module provides a clean interface for interacting with the dashboard.
"""

import os
import sys
import logging
import threading
from typing import Dict, Any, Optional, List, Callable

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import dashboard modules
from dashboard.app import create_app, run_server, run_in_thread, shutdown
from dashboard.config import get_dashboard_config, save_dashboard_config

# Configure logging
logger = logging.getLogger(__name__)


class DashboardManager:
    """
    Provides a clean interface for managing the dashboard.
    """
    
    def __init__(self):
        """Initialize dashboard manager."""
        self._dashboard_thread = None
        self._is_running = False
        self._config = get_dashboard_config()
    
    @property
    def is_running(self) -> bool:
        """Check if dashboard is running."""
        return self._is_running and (
            self._dashboard_thread is not None and 
            self._dashboard_thread.is_alive()
        )
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get dashboard configuration."""
        return self._config
    
    def start(self, host: str = None, port: int = None, debug: bool = None) -> bool:
        """
        Start the dashboard server.
        
        Args:
            host: Host address to bind to (uses config if None)
            port: Port to listen on (uses config if None)
            debug: Whether to run in debug mode (uses config if None)
            
        Returns:
            True if successfully started or already running, False otherwise
        """
        if self.is_running:
            logger.info("Dashboard is already running")
            return True
        
        # Start dashboard in a thread
        try:
            self._dashboard_thread = run_in_thread(host, port, debug)
            self._is_running = True
            
            # Wait a moment to see if thread starts properly
            self._dashboard_thread.join(0.5)
            
            if not self._dashboard_thread.is_alive():
                logger.error("Dashboard thread failed to start")
                self._is_running = False
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error starting dashboard: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the dashboard server.
        
        Returns:
            True if successfully stopped or not running, False otherwise
        """
        if not self.is_running:
            logger.info("Dashboard is not running")
            return True
        
        try:
            # Call shutdown
            shutdown()
            
            # Reset state
            self._is_running = False
            
            return True
        except Exception as e:
            logger.error(f"Error stopping dashboard: {str(e)}")
            return False
    
    def restart(self) -> bool:
        """
        Restart the dashboard server.
        
        Returns:
            True if successfully restarted, False otherwise
        """
        if self.is_running:
            # Get current host and port
            host = self._config.get("host", "0.0.0.0") 
            port = self._config.get("port", 8050)
            debug = self._config.get("debug", False)
            
            # Stop dashboard
            if not self.stop():
                return False
            
            # Wait a moment for complete shutdown
            import time
            time.sleep(1)
            
            # Start dashboard
            return self.start(host, port, debug)
        else:
            # Just start if not running
            return self.start()
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """
        Update dashboard configuration.
        
        Args:
            config: New configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Save configuration
            if save_dashboard_config(config):
                self._config = config
                
                # Restart if running
                if self.is_running:
                    return self.restart()
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating dashboard configuration: {str(e)}")
            return False
    
    def add_view_data_handler(self, view_name: str, handler: Callable) -> bool:
        """
        Add a data handler for a specific view.
        
        Args:
            view_name: Name of the view
            handler: Handler function for data updates
            
        Returns:
            True if successful, False otherwise
        """
        # This is a stub for future implementation
        # It could register handlers to be called when the view data needs to be updated
        logger.info(f"Adding view data handler for {view_name}")
        return True
    
    def remove_view_data_handler(self, view_name: str, handler: Callable) -> bool:
        """
        Remove a data handler for a specific view.
        
        Args:
            view_name: Name of the view
            handler: Handler function to remove
            
        Returns:
            True if successful, False otherwise
        """
        # This is a stub for future implementation
        logger.info(f"Removing view data handler for {view_name}")
        return True


# Singleton instance
_dashboard_manager = None


def get_dashboard_manager() -> DashboardManager:
    """
    Get the singleton dashboard manager instance.
    
    Returns:
        Dashboard manager instance
    """
    global _dashboard_manager
    
    if _dashboard_manager is None:
        _dashboard_manager = DashboardManager()
    
    return _dashboard_manager


def start_dashboard(host: str = None, port: int = None, debug: bool = None) -> bool:
    """
    Start the dashboard server.
    
    Args:
        host: Host address to bind to (uses config if None)
        port: Port to listen on (uses config if None)
        debug: Whether to run in debug mode (uses config if None)
        
    Returns:
        True if successful, False otherwise
    """
    return get_dashboard_manager().start(host, port, debug)


def stop_dashboard() -> bool:
    """
    Stop the dashboard server.
    
    Returns:
        True if successful, False otherwise
    """
    return get_dashboard_manager().stop()


def is_dashboard_running() -> bool:
    """
    Check if dashboard is running.
    
    Returns:
        True if running, False otherwise
    """
    return get_dashboard_manager().is_running


def update_dashboard_config(config: Dict[str, Any]) -> bool:
    """
    Update dashboard configuration.
    
    Args:
        config: New configuration
        
    Returns:
        True if successful, False otherwise
    """
    return get_dashboard_manager().update_config(config) 