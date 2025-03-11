# Instinct AI Installation Guide

This guide provides detailed instructions for installing and setting up the Instinct AI Trading System, with special focus on resolving common dependency issues.

## System Requirements

- **Operating System**: Linux, macOS, or Windows
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum (8GB+ recommended)
- **Disk Space**: 2GB minimum for code and data
- **Internet Connection**: Required for market data retrieval

## Installation Options

### Option 1: Quick Install (Recommended for most users)

```bash
# Clone the repository
git clone https://github.com/yourusername/instinct_ai.git
cd instinct_ai

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r advanced_trading/requirements.txt
```

### Option 2: Manual Install (For troubleshooting)

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies one by one
pip install numpy pandas matplotlib seaborn
pip install scikit-learn scipy statsmodels
pip install dash plotly flask

# Install additional dependencies
pip install PyJWT ccxt python-binance requests
```

## Troubleshooting Common Issues

### Dependency Installation Problems

#### Issue: "Cannot uninstall 'blinker'. It is a distutils installed project..."

This occurs when trying to install a package that conflicts with a system-installed version. Try these solutions:

1. **Use `--ignore-installed` flag**:
   ```bash
   pip install dash flask --ignore-installed blinker
   ```

2. **Bypass the problematic dependency**:
   ```bash
   pip install --no-deps blinker
   pip install dash flask
   ```

3. **Create a clean virtual environment**:
   ```bash
   python -m venv fresh_venv
   source fresh_venv/bin/activate
   python -m pip install --upgrade pip
   pip install dash flask PyJWT plotly pandas numpy
   ```

#### Issue: "ModuleNotFoundError: No module named 'dash'"

If you've installed the packages but still get import errors:

1. **Verify installation**:
   ```bash
   pip list | grep dash
   pip list | grep flask
   ```

2. **Check Python environment**:
   ```bash
   which python  # On Unix/Linux
   where python  # On Windows
   ```
   Make sure you're using the Python from your virtual environment.

3. **Try force reinstalling**:
   ```bash
   pip install dash --force-reinstall
   ```

### Docker Installation (Alternative)

If you continue to have dependency issues, using Docker can bypass most environment problems:

```bash
# Build the Docker image
docker build -t instinct_ai .

# Run the container
docker run -p 8050:8050 instinct_ai
```

## Verifying Installation

After installation, verify that everything is working correctly:

```bash
# Run the test script
python advanced_trading/test_backtest.py

# Check if the dashboard runs
python advanced_trading/run_dashboard.py --no-auth
```

If the dashboard starts successfully, you should be able to access it at `http://localhost:8050` in your web browser.

## Setting Up the Secured Dashboard

Once basic installation is verified, set up the secured dashboard:

```bash
# Initialize the dashboard with admin user
python advanced_trading/run_secured_dashboard.py --init-admin
```

Note the generated admin password displayed in the console.

## Environment Variables

You may need to set these environment variables for certain features:

```bash
# For authentication security
export DASH_SECRET_KEY="your_strong_secret_key_here"

# For API connections (if needed)
export BINANCE_API_KEY="your_api_key"
export BINANCE_SECRET_KEY="your_api_secret"
```

On Windows, use `set` instead of `export`.

## Logging and Debugging

If you encounter issues:

1. **Enable debug mode**:
   ```bash
   python advanced_trading/run_secured_dashboard.py --debug --log-level=DEBUG
   ```

2. **Check log files** in the `advanced_trading/logs/` directory.

3. **Test components individually**:
   ```bash
   # Test market monitor
   python -c "from advanced_trading.utils.market_monitor import get_market_monitor; m = get_market_monitor(); print(m.symbols)"
   
   # Test authentication
   python -c "from advanced_trading.dashboard.auth import get_auth_manager; a = get_auth_manager(); print(a.list_users())"
   ```

## Common Configuration Issues

### Permission Errors

If you encounter permission errors:

```bash
# Ensure directories are writable
mkdir -p advanced_trading/data/cache
chmod -R 755 advanced_trading/data
chmod -R 755 advanced_trading/logs
```

### Port Already in Use

If port 8050 is already in use:

```bash
# Find process using the port
lsof -i :8050  # On Linux/Mac
netstat -ano | findstr :8050  # On Windows

# Run on a different port
python advanced_trading/run_secured_dashboard.py --port=8051
```

## Getting Help

If you continue to experience issues:

1. Check the logs in `advanced_trading/logs/`
2. Consult the troubleshooting section in `advanced_trading/docs/DASH_READ.md`
3. Try running with `--debug` flag for more detailed error messages 