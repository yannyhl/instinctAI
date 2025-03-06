#!/usr/bin/env python

"""
Dashboard Launcher
-----------------
Script to launch the Instinct AI trading dashboard
"""

import os
import sys
import logging
import argparse
from pathlib import Path
import subprocess
import webbrowser
import time
import signal
import psutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Launch Instinct AI Trading Dashboard')
    
    parser.add_argument('--port', type=int, default=8050,
                        help='Port to run the dashboard on')
    
    parser.add_argument('--debug', action='store_true',
                        help='Run in debug mode')
    
    parser.add_argument('--no-browser', action='store_true',
                        help='Do not automatically open browser')
    
    return parser.parse_args()

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import dash
        import plotly
        import pandas
        import numpy
        logger.info("All dashboard dependencies are installed")
        return True
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Please install required packages: pip install dash plotly pandas numpy")
        return False

def is_port_in_use(port):
    """Check if the specified port is already in use."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_available_port(start_port):
    """Find an available port starting from the given port."""
    port = start_port
    while is_port_in_use(port):
        logger.warning(f"Port {port} is already in use")
        port += 1
        if port > start_port + 10:  # Limit to checking 10 ports
            logger.error("Unable to find an available port")
            return None
    return port

def start_dashboard(port, debug_mode, open_browser):
    """Start the dashboard server."""
    # Dashboard script path
    dashboard_script = Path(__file__).resolve().parent / "dashboard" / "app.py"
    
    if not dashboard_script.exists():
        logger.error(f"Dashboard script not found: {dashboard_script}")
        return False
    
    # Find available port
    available_port = find_available_port(port)
    if not available_port:
        return False
    
    # Command to run the dashboard
    cmd = [
        sys.executable,
        str(dashboard_script)
    ]
    
    # Environment variables for Dash
    env = os.environ.copy()
    env["DASH_DEBUG"] = "true" if debug_mode else "false"
    env["DASH_APP_PORT"] = str(available_port)
    
    logger.info(f"Starting dashboard on port {available_port}")
    
    # Start the subprocess
    try:
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Wait for the server to start
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is not None:
            # Process has terminated
            stdout, stderr = process.communicate()
            logger.error(f"Dashboard failed to start: {stderr}")
            return False
        
        # Open web browser
        if open_browser:
            url = f"http://localhost:{available_port}"
            logger.info(f"Opening dashboard in browser: {url}")
            webbrowser.open(url)
        
        logger.info("Dashboard is running. Press Ctrl+C to stop.")
        
        # Wait for keyboard interrupt
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break
        
        # Terminate the process
        logger.info("Stopping dashboard...")
        kill_process_tree(process.pid)
        
        return True
    
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}")
        return False

def kill_process_tree(pid):
    """Kill a process and all its children."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # Kill children
        for child in children:
            child.terminate()
        
        # Kill parent
        parent.terminate()
        
        # Wait for processes to terminate
        psutil.wait_procs(children + [parent], timeout=5)
        
        # Check if any processes are still alive and force kill if necessary
        for p in children + [parent]:
            if p.is_running():
                logger.info(f"Force killing process {p.pid}")
                p.kill()
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        logger.error(f"Error killing process tree: {e}")

def main():
    """Main function."""
    # Parse arguments
    args = parse_args()
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Start dashboard
    success = start_dashboard(
        port=args.port,
        debug_mode=args.debug,
        open_browser=not args.no_browser
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 