#!/usr/bin/env python3
"""
Instinct AI Trading System - Main Entry Point

This script provides the main entry point for launching the Instinct AI trading system.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional, List
import threading
import time

# Add the parent directory to sys.path to enable relative imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import config_manager, metrics, logging as log_manager, tracing


def setup_arg_parser() -> argparse.ArgumentParser:
    """
    Set up command-line argument parser.
    
    Returns:
        Configured argparse.ArgumentParser instance
    """
    parser = argparse.ArgumentParser(description="Instinct AI Trading System")
    
    # General options
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--mode", choices=["development", "production", "simulation"], 
                      default="development", help="Operating mode")
    parser.add_argument("--log-level", type=str, default="info",
                      choices=["debug", "info", "warning", "error", "critical"],
                      help="Logging level")
    parser.add_argument("--log-file", type=str, help="Log file path")
    
    # Component control group
    component_group = parser.add_argument_group("Component Control")
    component_group.add_argument("--enable-all", action="store_true", 
                               help="Enable all components")
    component_group.add_argument("--disable-all", action="store_true", 
                               help="Disable all components")
    component_group.add_argument("--data-only", action="store_true", 
                               help="Only run data manager (disables trading)")
    
    # Dashboard options
    dashboard_group = parser.add_argument_group("Dashboard Options")
    dashboard_group.add_argument("--dashboard", action="store_true", 
                               help="Enable dashboard")
    dashboard_group.add_argument("--no-dashboard", action="store_true", 
                               help="Disable dashboard")
    dashboard_group.add_argument("--dashboard-port", type=int, 
                               help="Dashboard port (default: from config or 8050)")
    dashboard_group.add_argument("--dashboard-theme", choices=["light", "dark"], 
                               help="Dashboard theme (default: from config)")
    
    # Database options
    db_group = parser.add_argument_group("Database Options")
    db_group.add_argument("--db-uri", type=str, help="Database URI")
    db_group.add_argument("--rebuild-db", action="store_true", 
                        help="Rebuild database (warning: destructive)")
    
    # Data options
    data_group = parser.add_argument_group("Data Options")
    data_group.add_argument("--data-dir", type=str, help="Data directory")
    data_group.add_argument("--symbols", type=str, help="Comma-separated list of symbols to trade")
    data_group.add_argument("--timeframes", type=str, 
                          help="Comma-separated list of timeframes to use")
    
    # Strategy options
    strategy_group = parser.add_argument_group("Strategy Options")
    strategy_group.add_argument("--strategies", type=str, 
                             help="Comma-separated list of strategies to use")
    strategy_group.add_argument("--backtest", action="store_true", 
                             help="Run in backtest mode")
    strategy_group.add_argument("--backtest-start", type=str, 
                             help="Backtest start date (YYYY-MM-DD)")
    strategy_group.add_argument("--backtest-end", type=str, 
                             help="Backtest end date (YYYY-MM-DD)")
    
    return parser


def initialize_system(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Initialize the trading system based on command-line arguments.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Dictionary of initialized system components
    """
    # Load and configure the config manager
    if args.config_dir:
        config_manager._config_dir = args.config_dir
        config_manager._load_default_config()
        config_manager._load_env_config()
        config_manager._load_user_config()
    
    # Override config with command-line arguments
    if args.log_level:
        config_manager.set("system.log_level", args.log_level)
    
    # Initialize logging
    log_level = config_manager.get("system.log_level", "INFO")
    log_manager.update_log_level(log_level)
    
    logger = log_manager.get_logger("main", {"component": "main"})
    logger.info(f"Initializing Instinct AI Trading System in {args.mode} mode")
    
    # Set global context for logging
    log_manager.set_global_context(
        system_version=config_manager.get("system.version", "1.0.0"),
        environment=args.mode
    )
    
    # Initialize components based on mode
    components = {
        "config_manager": config_manager,
        "metrics": metrics,
        "logging": log_manager,
        "tracing": tracing,
        "logger": logger
    }
    
    # Parse lists from command-line arguments
    if args.strategies:
        strategies = [s.strip() for s in args.strategies.split(",")]
        logger.info(f"Using explicit strategy list: {strategies}")
        components["strategies"] = strategies
    
    if args.exchanges:
        exchanges = [e.strip() for e in args.exchanges.split(",")]
        logger.info(f"Using explicit exchange list: {exchanges}")
        components["exchanges"] = exchanges
    
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
        logger.info(f"Using explicit symbol list: {symbols}")
        components["symbols"] = symbols
    
    return components


def start_dashboard(components: Dict[str, Any], args: argparse.Namespace) -> None:
    """
    Start the dashboard server if enabled in configuration.
    
    Args:
        components: Dictionary of system components
        args: Command-line arguments
    """
    try:
        # Import dashboard modules
        from dashboard.interface import start_dashboard as start_dash, get_dashboard_manager
        
        # Check if dashboard is enabled via args or config
        if not args.dashboard and not config_manager.get("dashboard.enabled", True):
            logger.info("Dashboard is disabled, not starting")
            return
        
        # Get dashboard configuration
        host = config_manager.get("dashboard.host", "0.0.0.0")
        port = args.dashboard_port or config_manager.get("dashboard.port", 8050)
        debug = config_manager.get("dashboard.debug", False)
        
        # Get dashboard manager
        dashboard_manager = get_dashboard_manager()
        
        # Make components available to the dashboard
        dashboard_manager._components = components
        
        # Start the dashboard
        if start_dash(host=host, port=port, debug=debug):
            logger.info(f"Dashboard started on http://{host}:{port}")
            
            # Store dashboard manager in components for later access
            components["dashboard_manager"] = dashboard_manager
        else:
            logger.error("Failed to start dashboard")
    except ImportError as e:
        logger.warning(f"Dashboard could not be started: {str(e)}")
        logger.warning("Make sure dashboard dependencies are installed")
    except Exception as e:
        logger.error(f"Error starting dashboard: {str(e)}")
        logger.debug("Dashboard start error details", exc_info=True)


def shutdown_system(components: Dict[str, Any], mode: str = "graceful") -> None:
    """
    Shutdown the system gracefully.
    
    Args:
        components: Dictionary of system components
        mode: Shutdown mode ('graceful' or 'emergency')
    """
    logger = components.get("logger", logging.getLogger())
    logger.info(f"Shutting down system ({mode} mode)")
    
    # Shutdown dashboard
    if "dashboard_manager" in components:
        logger.info("Shutting down dashboard")
        try:
            components["dashboard_manager"].stop()
        except Exception as e:
            logger.error(f"Error shutting down dashboard: {str(e)}")
    
    # Shutdown other components
    # ... [implementation of other component shutdown]
    
    logger.info("System shutdown complete")


def setup_signal_handlers(components: Dict[str, Any]) -> None:
    """
    Set up signal handlers for graceful shutdown.
    
    Args:
        components: Dictionary of system components
    """
    import signal
    
    def signal_handler(sig, frame):
        logger = components.get("logger", logging.getLogger())
        
        if sig == signal.SIGINT:
            logger.info("Received SIGINT (Ctrl+C)")
            shutdown_system(components)
            sys.exit(0)
        elif sig == signal.SIGTERM:
            logger.info("Received SIGTERM")
            shutdown_system(components)
            sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main() -> int:
    """
    Main entry point for the application.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Parse command-line arguments
        parser = setup_arg_parser()
        args = parser.parse_args()
        
        # Initialize system components
        components = initialize_system(args)
        
        # Set up signal handlers for graceful shutdown
        setup_signal_handlers(components)
        
        # Start dashboard if requested
        if args.dashboard or config_manager.get("dashboard.enabled", True):
            start_dashboard(components, args)
        
        # Start system (blocking call)
        logger.info("System started successfully")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
        
        return 0
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
        if 'components' in locals():
            shutdown_system(components)
        return 0
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        logger.debug("Error details", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 