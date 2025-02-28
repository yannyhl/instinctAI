#!/usr/bin/env python3
"""
Secured Dashboard Runner
---------------------
Script to launch the secured Instinct AI trading dashboard with authentication.
"""

import os
import sys
import argparse
import logging
import subprocess
import time
from pathlib import Path
import importlib.util
import traceback

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'logs', f'dashboard_{time.strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

# Required dependencies
REQUIRED_PACKAGES = [
    ('dash', 'Dash'),
    ('plotly', 'Plotly'),
    ('pandas', 'Pandas'),
    ('numpy', 'NumPy'),
    ('flask', 'Flask'),
    ('jwt', 'PyJWT')
]

def check_dependencies():
    """Check if all required dependencies are installed."""
    missing_packages = []
    
    for package, display_name in REQUIRED_PACKAGES:
        if importlib.util.find_spec(package) is None:
            missing_packages.append(display_name)
    
    if missing_packages:
        logger.error(f"Missing required dependencies: {', '.join(missing_packages)}")
        logger.error("Please install missing packages with: pip install dash plotly pandas numpy flask PyJWT")
        
        # Suggest workaround for common blinker issue
        logger.error("\nIf you're having issues with blinker dependency, try one of these solutions:")
        logger.error("1. pip install dash plotly pandas numpy flask PyJWT --ignore-installed")
        logger.error("2. Run the install_dashboard.sh script: bash advanced_trading/install_dashboard.sh")
        logger.error("3. See advanced_trading/docs/INSTALLATION_GUIDE.md for more solutions")
        
        return False
    
    # Check if we can actually import the packages (sometimes they're installed but broken)
    try:
        # Add manual import checks for critical packages
        import dash
        import flask
        logger.info("Dash and Flask packages successfully imported")
    except ImportError as e:
        logger.error(f"Error importing packages: {e}")
        logger.error("Please try reinstalling with: pip install dash flask --force-reinstall")
        logger.error("Or use the installation script: bash advanced_trading/install_dashboard.sh")
        return False
    
    logger.info("All required dependencies are installed")
    return True

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Secured Instinct AI Trading Dashboard")
    
    parser.add_argument("--port", type=int, default=8050,
                      help="Port to run the dashboard on")
    
    parser.add_argument("--host", type=str, default="0.0.0.0",
                      help="Host to run the dashboard on")
    
    parser.add_argument("--debug", action="store_true",
                      help="Run in debug mode")
    
    parser.add_argument("--init-admin", action="store_true",
                      help="Initialize admin user with default credentials")
    
    parser.add_argument("--admin-user", type=str, default="admin",
                      help="Admin username (when using --init-admin)")
    
    parser.add_argument("--admin-pass", type=str, default=None,
                      help="Admin password (when using --init-admin)")
    
    parser.add_argument("--log-level", type=str, default="INFO",
                      choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                      help="Set the logging level")
    
    parser.add_argument("--no-auth", action="store_true",
                      help="Run dashboard without authentication (not recommended)")
    
    parser.add_argument("--skip-dependency-check", action="store_true", 
                      help="Skip the dependency check (use if facing import issues)")
    
    return parser.parse_args()

def init_admin_user(username, password):
    """Initialize admin user with specified credentials."""
    try:
        from dashboard.auth import get_auth_manager
        auth_manager = get_auth_manager()
        
        # Check if user already exists
        user_info = auth_manager.get_user_info(username)
        if user_info:
            logger.info(f"Admin user '{username}' already exists")
            return True
        
        # Create admin user
        if password is None:
            # Generate random password if not specified
            import secrets
            import string
            password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            logger.info(f"Generated random password for admin user: {password}")
        
        success = auth_manager.add_user(
            username=username,
            password=password,
            role="admin",
            email=f"{username}@example.com"
        )
        
        if success:
            logger.info(f"Admin user '{username}' created successfully")
            return True
        else:
            logger.error(f"Failed to create admin user '{username}'")
            return False
    except Exception as e:
        logger.error(f"Error initializing admin user: {str(e)}")
        return False

def run_dashboard(args):
    """Run the trading dashboard."""
    try:
        if args.no_auth:
            # Run unsecured dashboard
            logger.warning("Running dashboard without authentication (not recommended)")
            dashboard_script = os.path.join(script_dir, "dashboard", "updated_app.py")
        else:
            # Run secured dashboard
            dashboard_script = os.path.join(script_dir, "dashboard", "secured_app.py")
        
        # Check if dashboard script exists
        if not os.path.exists(dashboard_script):
            logger.error(f"Dashboard script not found: {dashboard_script}")
            return False
        
        # Set logging level
        level = getattr(logging, args.log_level)
        logger.setLevel(level)
        
        # Run dashboard as a module (to ensure imports work correctly)
        cmd = [
            sys.executable,
            dashboard_script,
            f"--port={args.port}",
            f"--host={args.host}"
        ]
        
        if args.debug:
            cmd.append("--debug")
        
        logger.info(f"Starting dashboard with command: {' '.join(cmd)}")
        
        # Run dashboard in the same process for better error handling
        try:
            if args.no_auth:
                # Import and run unsecured dashboard
                from dashboard.updated_app import app
                app.run_server(host=args.host, port=args.port, debug=args.debug)
            else:
                # Import and run secured dashboard
                from dashboard.secured_app import app
                app.run_server(host=args.host, port=args.port, debug=args.debug)
        except ModuleNotFoundError as e:
            logger.error(f"Error importing dashboard: {str(e)}")
            logger.error("This is likely due to missing dependencies. Please run:")
            logger.error("bash advanced_trading/install_dashboard.sh")
            return False
        
        return True
    except ImportError as e:
        logger.error(f"Error importing dashboard: {str(e)}")
        logger.error("Make sure all required packages are installed")
        logger.error(traceback.format_exc())
        return False
    except Exception as e:
        logger.error(f"Error running dashboard: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point for the script."""
    # Parse arguments
    args = parse_args()
    
    # Set log level
    log_level = getattr(logging, args.log_level)
    logger.setLevel(log_level)
    
    logger.info(f"Starting Secured Dashboard Runner (log level: {args.log_level})")
    
    # Create necessary directories
    os.makedirs(os.path.join(script_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(script_dir, "data", "cache"), exist_ok=True)
    
    # Check dependencies unless explicitly skipped
    if not args.skip_dependency_check:
        if not check_dependencies():
            logger.error("Dependency check failed. Use --skip-dependency-check to bypass this check.")
            return 1
    else:
        logger.warning("Dependency check skipped. Continuing anyway...")
    
    # Initialize admin user if requested
    if args.init_admin:
        if not init_admin_user(args.admin_user, args.admin_pass):
            logger.warning("Failed to initialize admin user, continuing anyway")
    
    # Run dashboard
    try:
        success = run_dashboard(args)
        if not success:
            logger.error("Failed to run dashboard")
            return 1
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Error running dashboard: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    
    logger.info("Dashboard runner exiting")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 