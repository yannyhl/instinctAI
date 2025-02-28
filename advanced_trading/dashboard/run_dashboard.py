#!/usr/bin/env python3
"""
Dashboard Runner Script
----------------------
Launches the Instinct AI Trading Dashboard with configurable options.
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the trading dashboard with specified options."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the Instinct AI Trading Dashboard")
    parser.add_argument("--port", type=int, default=8050, help="Port to run the dashboard on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the dashboard on")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--log-level", type=str, default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Logging level")
    parser.add_argument("--update-interval", type=int, default=60,
                       help="Data update interval in seconds")
    args = parser.parse_args()
    
    # Set logging level from arguments
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Initialize market data and app (lazy import to ensure logging is configured first)
    logger.info(f"Starting Instinct AI Trading Dashboard on {args.host}:{args.port}")
    
    # First initialize market monitor with the specified update interval
    from utils.market_monitor import get_market_monitor
    market_monitor = get_market_monitor({
        'update_interval': args.update_interval
    })
    market_monitor.load_state()  # Try to load previous state
    market_monitor.start()
    
    try:
        # Now import and run the dashboard app
        from dashboard.app import app
        
        # Override interval in the app based on command line args
        for component in app.layout.children:
            if hasattr(component, 'id') and component.id == 'interval-component':
                component.interval = args.update_interval * 1000  # Convert to milliseconds
                break
                
        # Run the server
        app.run_server(
            host=args.host,
            port=args.port,
            debug=args.debug
        )
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Error running dashboard: {e}", exc_info=True)
    finally:
        # Make sure to stop the market monitor
        market_monitor.stop()
        logger.info("Market monitor stopped")

if __name__ == "__main__":
    main() 