#!/bin/bash
# Dashboard Dependencies Installation Script
# This script helps install the necessary dependencies for the Instinct AI Trading Dashboard

set -e # Exit on error

echo "================================================"
echo "Instinct AI Dashboard Dependencies Installer"
echo "================================================"

# Create necessary directories
mkdir -p logs data/cache

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python version
echo "Checking Python version..."
if ! command_exists python3; then
    echo "Error: Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

# Parse Python version
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "Error: Python 3.8 or higher is required. Found Python $PYTHON_VERSION"
    exit 1
fi

# Set up virtual environment
echo "Setting up virtual environment..."
if ! command_exists virtualenv; then
    echo "Installing virtualenv..."
    pip3 install virtualenv
fi

if [ -d "venv" ]; then
    echo "Virtual environment already exists. Do you want to recreate it? (y/n)"
    read -r RECREATE
    if [ "$RECREATE" = "y" ]; then
        echo "Removing existing virtual environment..."
        rm -rf venv
        virtualenv venv
    fi
else
    echo "Creating virtual environment..."
    virtualenv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dashboard dependencies
echo "Installing dashboard dependencies..."
echo "This may take a few minutes..."

# Try different installation methods based on platform
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Try Method 1: Direct install
    echo "Trying direct installation method..."
    if ! pip install dash plotly pandas numpy flask PyJWT; then
        echo "Direct installation failed, trying alternative method..."
        
        # Try Method 2: Install with --ignore-installed
        if ! pip install dash plotly pandas numpy flask PyJWT --ignore-installed; then
            echo "Alternative method failed, trying with --no-deps for problematic packages..."
            
            # Try Method 3: Install problematic packages with --no-deps
            pip install --no-deps blinker
            pip install dash plotly pandas numpy flask PyJWT
        fi
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS installation method
    echo "Installing dependencies for macOS..."
    pip install dash plotly pandas numpy flask PyJWT
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows installation method
    echo "Installing dependencies for Windows..."
    pip install dash plotly pandas numpy flask PyJWT
else
    # Generic installation method
    echo "Installing dependencies for your platform..."
    pip install dash plotly pandas numpy flask PyJWT --ignore-installed
fi

# Verify installation
echo "Verifying installation..."
python -c "import dash; import plotly; import pandas; import numpy; import flask; import jwt; print('All dependencies installed successfully!')" || {
    echo "Error: Failed to import required packages. Please check the logs and try again."
    echo "You may need to install packages manually:"
    echo "pip install dash plotly pandas numpy flask PyJWT"
    exit 1
}

# Install additional trading dependencies
echo "Would you like to install additional trading dependencies? (y/n)"
read -r INSTALL_EXTRAS
if [ "$INSTALL_EXTRAS" = "y" ]; then
    echo "Installing additional dependencies..."
    pip install ccxt python-binance yfinance scikit-learn scipy statsmodels
fi

echo "================================================"
echo "Installation completed successfully!"
echo "================================================"
echo ""
echo "To activate the virtual environment, run:"
echo "source venv/bin/activate"
echo ""
echo "To start the secured dashboard, run:"
echo "python advanced_trading/run_secured_dashboard.py --init-admin"
echo ""
echo "If you encounter any issues, please check the documentation in:"
echo "advanced_trading/docs/INSTALLATION_GUIDE.md"
echo "================================================" 