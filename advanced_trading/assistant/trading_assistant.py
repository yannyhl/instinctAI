"""
Trading Assistant
----------------
Interactive assistant for the Advanced Trading System that provides
guidance, explanations, and automations for common tasks.
"""

import os
import sys
import logging
import importlib
import inspect
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Union, Any, Optional

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import project modules
import config
from data.data_loader import DataLoader
from strategies.ml_strategy import MLEnsembleStrategy

# Set up logging
logger = logging.getLogger(__name__)

class TradingAssistant:
    """
    Interactive assistant that helps users with the trading system.
    """
    
    def __init__(self):
        """Initialize the trading assistant."""
        self.base_dir = Path(__file__).resolve().parent.parent
        self.data_loader = None
        self.active_strategy = None
        self.available_commands = self._get_available_commands()
        
        # Initialize logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Welcome message
        print("\n" + "="*80)
        print("Welcome to the Advanced Trading Assistant (v1.1)")
        print("Type 'help' for a list of commands or 'exit' to quit.")
        print("="*80 + "\n")
    
    def _get_available_commands(self) -> Dict[str, Any]:
        """Get all available commands from the assistant."""
        commands = {}
        
        # Get all methods that don't start with underscore
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if not name.startswith('_') and name != 'run':
                commands[name] = method
        
        return commands
    
    def run(self):
        """Run the assistant in interactive mode."""
        while True:
            try:
                command = input("\n> ").strip().lower()
                
                if command == 'exit':
                    print("Goodbye!")
                    break
                
                if command == '':
                    continue
                
                # Parse command and arguments
                parts = command.split()
                cmd = parts[0]
                args = parts[1:]
                
                if cmd in self.available_commands:
                    # Call the command
                    self.available_commands[cmd](*args)
                else:
                    print(f"Unknown command: {cmd}. Type 'help' for available commands.")
            
            except KeyboardInterrupt:
                print("\nOperation cancelled. Type 'exit' to quit.")
            except Exception as e:
                print(f"Error: {str(e)}")
    
    def help(self, *args):
        """Display help information about available commands."""
        if not args:
            print("\nAvailable commands:")
            print("-"*80)
            
            for cmd, method in sorted(self.available_commands.items()):
                # Get the first line of the docstring
                doc = method.__doc__.split('\n')[0] if method.__doc__ else "No description"
                print(f"  {cmd:<15} - {doc}")
            
            print("\nFor more details on a specific command, type: help <command>")
        else:
            cmd = args[0]
            if cmd in self.available_commands:
                method = self.available_commands[cmd]
                # Get the full docstring
                doc = inspect.getdoc(method)
                print(f"\nHelp for command '{cmd}':")
                print("-"*80)
                print(doc)
                print("\nUsage:", end=" ")
                
                # Get the function signature
                sig = inspect.signature(method)
                params = []
                for name, param in sig.parameters.items():
                    if name != 'self' and name != 'args':
                        if param.default != inspect.Parameter.empty:
                            params.append(f"[{name}={param.default}]")
                        else:
                            params.append(f"<{name}>")
                
                print(f"{cmd} {' '.join(params)}")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
    
    def list_symbols(self, exchange="binance"):
        """
        List available trading symbols from the specified exchange.
        
        Args:
            exchange: Exchange to get symbols from (default: binance)
        """
        print(f"Getting available symbols from {exchange}...")
        
        if self.data_loader is None:
            self.data_loader = DataLoader(
                cache_dir=config.DATA_DIR / "cache",
                primary_source=exchange
            )
        
        try:
            # Get base currencies from config
            base_currencies = [config.TRADING_CONFIG.get("base_currency", "USD")]
            
            # List symbols for each base currency
            for base in base_currencies:
                symbols = self.data_loader.list_available_symbols(base_currency=base)
                
                if symbols:
                    print(f"\nAvailable {base} pairs ({len(symbols)}):")
                    # Print in columns
                    symbols.sort()
                    columns = 4
                    for i in range(0, len(symbols), columns):
                        row = symbols[i:i+columns]
                        print("  ".join(f"{s:<12}" for s in row))
                else:
                    print(f"No symbols found for {base}")
        
        except Exception as e:
            print(f"Error listing symbols: {e}")
    
    def backtest(self, symbol=None, start_date=None, end_date=None, timeframe="1d", capital="10000"):
        """
        Run a backtest with the specified parameters.
        
        Args:
            symbol: Trading symbol (e.g., BTC/USDT)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: Data timeframe (default: 1d)
            capital: Initial capital (default: 10000)
        """
        if symbol is None:
            print("Error: Symbol is required. Example: backtest BTC/USDT")
            return
        
        # Set default dates if not provided
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            print(f"Using default start date: {start_date}")
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            print(f"Using default end date: {end_date}")
        
        try:
            # Import the backtest module
            from run_simple_backtest import run_backtest
            
            print(f"Running backtest for {symbol} from {start_date} to {end_date}...")
            print(f"Timeframe: {timeframe}, Initial Capital: {capital}")
            print("\nThis might take a few minutes. Please wait...\n")
            
            # Run the backtest
            results = run_backtest(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                initial_capital=float(capital)
            )
            
            if results:
                metrics = results['metrics']
                print("\nBacktest Results:")
                print("-"*80)
                print(f"Total Return: {metrics['total_return']:.2f}%")
                print(f"Annual Return: {metrics['annual_return']:.2f}%")
                print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
                print(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
                print(f"Number of Trades: {metrics['num_trades']}")
                print(f"Final Capital: ${metrics['final_capital']:.2f}")
                print("\nResults saved to:", results['results_dir'])
            else:
                print("Backtest failed. Check the logs for details.")
        
        except Exception as e:
            print(f"Error running backtest: {e}")
    
    def analyze(self, results_path=None):
        """
        Analyze backtest results.
        
        Args:
            results_path: Path to backtest results directory
        """
        if results_path is None:
            # Try to find the most recent results directory
            results_dir = self.base_dir / "results"
            if not results_dir.exists():
                print("Error: No results directory found.")
                return
            
            # Get all backtest directories
            backtest_dirs = [d for d in results_dir.glob("backtest_*") if d.is_dir()]
            if not backtest_dirs:
                print("Error: No backtest results found.")
                return
            
            # Sort by modification time (most recent first)
            backtest_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            results_path = backtest_dirs[0]
            print(f"Using most recent results: {results_path}")
        
        try:
            # Load metrics and portfolio data
            metrics_file = Path(results_path) / "metrics.json"
            portfolio_file = Path(results_path) / "portfolio.csv"
            
            if not metrics_file.exists() or not portfolio_file.exists():
                print(f"Error: Required files not found in {results_path}")
                return
            
            import json
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)
            
            portfolio = pd.read_csv(portfolio_file)
            
            # Basic analysis
            print("\nPerformance Analysis:")
            print("-"*80)
            print(f"Symbol: {metrics['symbol']}")
            print(f"Period: {metrics['start_date']} to {metrics['end_date']}")
            print(f"Total Return: {metrics['total_return']:.2f}%")
            print(f"Annual Return: {metrics['annual_return']:.2f}%")
            print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            print(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
            print(f"Number of Trades: {metrics['num_trades']}")
            
            # Analyze drawdown periods
            if 'drawdown' in portfolio.columns:
                drawdowns = portfolio[portfolio['drawdown'] < -0.01].copy()  # Only consider >1% drawdowns
                if not drawdowns.empty:
                    print("\nSignificant Drawdown Periods:")
                    current_start = None
                    current_end = None
                    current_max = 0
                    drawdown_periods = []
                    
                    # Identify contiguous drawdown periods
                    for i, row in drawdowns.iterrows():
                        if current_start is None:
                            current_start = i
                            current_max = row['drawdown']
                        elif i > current_end + 1 if current_end is not None else True:
                            # End of period, record it
                            if current_start is not None and current_end is not None:
                                drawdown_periods.append((current_start, current_end, current_max))
                            current_start = i
                            current_max = row['drawdown']
                        else:
                            if row['drawdown'] < current_max:
                                current_max = row['drawdown']
                        current_end = i
                    
                    # Record the last period
                    if current_start is not None and current_end is not None:
                        drawdown_periods.append((current_start, current_end, current_max))
                    
                    # Display drawdown periods
                    for start, end, max_dd in drawdown_periods:
                        try:
                            start_date = portfolio.iloc[start]['timestamp']
                            end_date = portfolio.iloc[end]['timestamp']
                            duration = pd.to_datetime(end_date) - pd.to_datetime(start_date)
                            print(f"  {start_date} to {end_date} ({duration.days} days): {max_dd*100:.2f}%")
                        except (KeyError, IndexError):
                            pass
            
            # Profitable vs. losing trades
            if 'signal' in portfolio.columns:
                signal_changes = portfolio['signal'] != portfolio['signal'].shift(1)
                trade_entries = portfolio[signal_changes].copy()
                
                if not trade_entries.empty:
                    # Analyze position sizes
                    if 'position_size' in trade_entries.columns:
                        avg_pos_size = trade_entries['position_size'].abs().mean()
                        max_pos_size = trade_entries['position_size'].abs().max()
                        print(f"\nAverage Position Size: {avg_pos_size:.2%}")
                        print(f"Maximum Position Size: {max_pos_size:.2%}")
            
            # Performance visualization suggestion
            print(f"\nFor visual performance analysis, check the chart at: {results_path / 'performance.png'}")
        
        except Exception as e:
            print(f"Error analyzing results: {e}")
    
    def optimize(self, symbol=None, param=None, start_val=None, end_val=None, steps=None):
        """
        Optimize a strategy parameter through backtesting.
        
        Args:
            symbol: Trading symbol to optimize for
            param: Parameter to optimize
            start_val: Starting parameter value
            end_val: Ending parameter value
            steps: Number of steps between start and end values
        """
        if symbol is None or param is None or start_val is None or end_val is None:
            print("Error: Required parameters missing.")
            print("Usage: optimize <symbol> <param> <start_val> <end_val> [steps]")
            return
        
        if steps is None:
            steps = "5"  # Default
        
        try:
            # Convert values to appropriate types
            start_val = float(start_val)
            end_val = float(end_val)
            steps = int(steps)
            
            # Generate parameter values
            param_values = np.linspace(start_val, end_val, steps)
            
            print(f"Optimizing {param} for {symbol} with {steps} steps:")
            for val in param_values:
                print(f"  {val:.4f}")
            
            print("\nThis optimization will run multiple backtests and may take a while.")
            print("Feature not fully implemented yet - this will be available in a future version.")
            
            # TODO: Implement parameter optimization
            # For now, we'll just provide guidance
            print("\nTo manually test different parameters:")
            for val in param_values:
                print(f"1. Edit config.py to set {param} = {val:.4f}")
                print(f"2. Run: backtest {symbol}")
                print(f"3. Record the results")
            
            print("\nIn future versions, this will be automated with results comparison.")
        
        except Exception as e:
            print(f"Error in optimization: {e}")
    
    def show_features(self, symbol=None):
        """
        Show feature importance for a symbol's ML model.
        
        Args:
            symbol: Trading symbol to analyze
        """
        if symbol is None:
            print("Error: Symbol is required.")
            print("Usage: show_features <symbol>")
            return
        
        try:
            # Try to load saved models
            import joblib
            from pathlib import Path
            
            # Clean symbol for filename
            symbol_safe = symbol.replace('/', '_')
            model_path = self.base_dir / "models" / "ml_ensemble" / f"{symbol_safe}_models.joblib"
            
            if not model_path.exists():
                print(f"No models found for {symbol}.")
                print(f"Try running a backtest first: backtest {symbol}")
                return
            
            # Load the models
            models = joblib.load(model_path)
            
            print(f"\nFeature Importance for {symbol}:")
            print("-"*80)
            
            # Extract feature importance from Random Forest model
            if 'rf' in models:
                rf_model = models['rf']
                if hasattr(rf_model, 'feature_importances_'):
                    # Try to get feature names if available
                    feature_names = getattr(rf_model, 'feature_names_in_', None)
                    importances = rf_model.feature_importances_
                    
                    if feature_names is not None:
                        # Sort features by importance
                        indices = np.argsort(importances)[::-1]
                        print("Random Forest Feature Importance:")
                        for i, idx in enumerate(indices):
                            if i < 15:  # Show top 15 features
                                print(f"  {feature_names[idx]:<25}: {importances[idx]:.4f}")
                            else:
                                break
                    else:
                        print("Feature names not available in the model.")
                else:
                    print("Feature importance not available for this model.")
            else:
                print("Random Forest model not found.")
            
            # Gradient Boosting feature importance
            if 'gb' in models:
                gb_model = models['gb']
                if hasattr(gb_model, 'feature_importances_'):
                    print("\nGradient Boosting Feature Importance:")
                    importances = gb_model.feature_importances_
                    feature_names = getattr(gb_model, 'feature_names_in_', None)
                    
                    if feature_names is not None:
                        indices = np.argsort(importances)[::-1]
                        for i, idx in enumerate(indices):
                            if i < 10:  # Show top 10 features
                                print(f"  {feature_names[idx]:<25}: {importances[idx]:.4f}")
                            else:
                                break
                    else:
                        print("Feature names not available in the model.")
                else:
                    print("Feature importance not available for this model.")
            
            # Logistic Regression coefficients
            if 'lr' in models:
                lr_model = models['lr']
                # Check if it's a pipeline with classifier
                if hasattr(lr_model, 'named_steps') and 'classifier' in lr_model.named_steps:
                    classifier = lr_model.named_steps['classifier']
                    if hasattr(classifier, 'coef_'):
                        print("\nLogistic Regression Coefficients:")
                        coefs = classifier.coef_[0]
                        feature_names = getattr(lr_model, 'feature_names_in_', None)
                        
                        if feature_names is not None:
                            # Sort by absolute coefficient value
                            indices = np.argsort(np.abs(coefs))[::-1]
                            for i, idx in enumerate(indices):
                                if i < 10:  # Show top 10 features
                                    print(f"  {feature_names[idx]:<25}: {coefs[idx]:.4f}")
                                else:
                                    break
                        else:
                            print("Feature names not available in the model.")
                elif hasattr(lr_model, 'coef_'):
                    print("\nLogistic Regression Coefficients:")
                    coefs = lr_model.coef_[0]
                    feature_names = getattr(lr_model, 'feature_names_in_', None)
                    
                    if feature_names is not None:
                        indices = np.argsort(np.abs(coefs))[::-1]
                        for i, idx in enumerate(indices):
                            if i < 10:
                                print(f"  {feature_names[idx]:<25}: {coefs[idx]:.4f}")
                            else:
                                break
                    else:
                        print("Feature names not available in the model.")
                else:
                    print("Coefficients not available for this model.")
            
            print("\nThis information can help you understand which features are most important")
            print("for predicting price movements and can guide your feature engineering efforts.")
            
        except Exception as e:
            print(f"Error analyzing feature importance: {e}")
    
    def version(self):
        """Show the current version of the trading system."""
        import importlib.metadata as metadata
        
        print("\nInstinct Algo Trading System")
        print("-"*80)
        print("Version: 1.1 (February 2024)")
        print("Status: Development/Testing")
        
        print("\nKey Components:")
        try:
            print(f"Python: {sys.version.split()[0]}")
            
            packages = [
                "numpy", "pandas", "matplotlib", "scikit-learn",
                "tensorflow", "ccxt", "joblib"
            ]
            
            for package in packages:
                try:
                    version = metadata.version(package)
                    print(f"{package}: {version}")
                except metadata.PackageNotFoundError:
                    print(f"{package}: Not installed")
        except Exception as e:
            print(f"Error getting versions: {e}")
            
        # Show configuration information
        print("\nConfiguration:")
        print(f"Data directory: {config.DATA_DIR}")
        print(f"Models directory: {config.MODELS_DIR}")
        print(f"Results directory: {config.RESULTS_DIR}")
        print(f"GPU enabled: {config.GPU_CONFIG['use_gpu']}")
        
        # Show documentation
        print("\nDocumentation:")
        docs_dir = self.base_dir / "DOCS"
        if docs_dir.exists():
            docs = list(docs_dir.glob("*.md"))
            for doc in docs:
                print(f"- {doc.name}")
            
            print("\nView documentation files in the DOCS directory.")
        else:
            print("Documentation directory not found.")
            
        print("\nFor more information, see the README.md file.")
    
    def explain(self, topic=None):
        """
        Explain a topic or concept from the trading system.
        
        Args:
            topic: Topic to explain
        """
        topics = {
            "backtest": """
Backtesting is a method to test a trading strategy on historical data before risking real money.

In our system, backtesting includes:
1. Loading historical market data for a symbol
2. Training ML models on this data
3. Generating trading signals
4. Simulating trades with realistic costs and constraints
5. Calculating performance metrics

Critically, our backtesting implementation includes:
- Commission costs (0.1% per trade)
- Slippage (0.05% per trade)
- Adaptive position sizing based on volatility
- Maximum drawdown protection
- Realistic entry and exit logic

You can run a backtest using the 'backtest' command.
            """,
            
            "ml_strategy": """
Our ML Ensemble strategy combines multiple machine learning models to predict price movements:

1. Random Forest Classifier:
   - Ensemble of decision trees
   - Good at capturing non-linear relationships
   - Handles missing values well
   - Provides feature importance

2. Gradient Boosting Classifier:
   - Sequential ensemble that improves on previous models' errors
   - Often captures subtle patterns
   - More prone to overfitting than Random Forest

3. Logistic Regression:
   - Linear model that serves as a baseline
   - More interpretable, less complex
   - Helps balance the ensemble

These models are trained on historical data with features including:
- Price momentum
- Volatility
- Technical indicators
- Volume patterns
- Market regime indicators

The ensemble signal is formed by combining predictions from all models.
Signals are then filtered and smoothed to reduce noise and false positives.
            """,
            
            "risk_management": """
Risk management is critical for trading success and incorporated throughout our system:

1. Position Sizing:
   - Adaptive sizing based on asset volatility
   - Higher volatility = smaller positions
   - Maximum position cap of 95% of capital
   - Based on percent risk principles

2. Stop Losses:
   - Portfolio-level drawdown protection (15% max drawdown)
   - Position-specific stop losses
   - Trading halts when drawdown exceeds threshold
   - Trading resumes after recovery

3. Transaction Costs:
   - Commission fees (0.1% per trade)
   - Slippage (0.05% per trade)
   - Tracked separately to analyze impact

4. Signal Filtering:
   - Requires consecutive signals to change positions
   - Smoothing to avoid excessive trading
   - Minimum signal strength thresholds
   - Hysteresis to prevent repeated entries/exits

These measures work together to provide realistic protection against losses
and avoid common pitfalls in algorithmic trading.
            """,
            
            "feature_engineering": """
Feature engineering is the process of creating predictive inputs for our ML models:

Our system uses the following feature categories:

1. Price-based features:
   - Returns (percent change in price)
   - Log returns (natural logarithm of price ratio)
   - Price momentum (returns over various timeframes)
   - Z-scores (normalized deviation from mean)

2. Volatility indicators:
   - Standard deviation of returns
   - Average True Range (ATR)
   - Bollinger Band width

3. Technical indicators:
   - Bollinger Bands (mean + standard deviation channels)
   - Relative Strength Index (RSI)
   - Moving averages and crossovers

4. Volume-related features:
   - Volume changes
   - Volume-price relationships
   - Abnormal volume detection

5. Market regime indicators:
   - Hurst exponent for trend/mean-reversion
   - Volatility regimes (high/low)
   - Support/resistance levels

These features help the models identify patterns that may predict future price movements.
You can see which features are most important with the 'show_features' command.
            """,
            
            "performance_metrics": """
Performance metrics help evaluate trading strategy effectiveness:

1. Return Metrics:
   - Total Return: Overall percentage gain/loss
   - Annual Return (CAGR): Annualized compound growth rate
   - Risk-adjusted Return: Returns normalized by risk taken

2. Risk Metrics:
   - Maximum Drawdown: Largest peak-to-trough decline
   - Volatility: Standard deviation of returns
   - Downside Deviation: Standard deviation of negative returns only

3. Ratios:
   - Sharpe Ratio: Returns in excess of risk-free rate divided by volatility
   - Sortino Ratio: Similar to Sharpe but only considers downside volatility
   - Calmar Ratio: Annual return divided by maximum drawdown
   - Profit Factor: Gross profits divided by gross losses

4. Trade Statistics:
   - Win Rate: Percentage of profitable trades
   - Average Profit/Loss: Mean return per trade
   - Maximum Consecutive Losses: Longest string of losing trades
   - Transaction Costs: Total fees and slippage

5. Other Metrics:
   - Beta: Correlation with the market
   - Alpha: Excess return compared to benchmark
   - Information Ratio: Excess return divided by tracking error

Our system calculates these metrics after each backtest to provide a comprehensive 
performance assessment.
            """,
            
            "gpu_acceleration": """
GPU acceleration can significantly speed up computation-intensive tasks in our system:

1. Supported operations:
   - Machine learning model training
   - Feature calculation
   - Technical indicator computation
   - Signal processing

2. Requirements:
   - CUDA-compatible NVIDIA GPU
   - cuPy and cuML Python libraries
   - Appropriate CUDA version for your hardware

3. Implementation details:
   - Code detects GPU availability automatically
   - Falls back to CPU if GPU not available or libraries missing
   - For ML, uses GPU-accelerated implementations when available
   - For data processing, uses cuDF/cuPy when available

4. Performance improvement:
   - Model training: 5-20x speedup
   - Technical indicators: 3-10x speedup
   - Large dataset processing: 10-50x speedup

5. Current limitations:
   - Not all operations are GPU-accelerated
   - Some algorithms lack GPU implementations
   - Memory limitations for very large datasets

The system will automatically use GPU acceleration if available hardware and 
software are detected. You can check GPU status with the 'version' command.
            """
        }
        
        if topic is None or topic not in topics:
            print("\nAvailable topics to explain:")
            print("-"*80)
            for t in sorted(topics.keys()):
                print(f"- {t}")
            print("\nUsage: explain <topic>")
            return
        
        # Show the explanation for the requested topic
        print(f"\nExplanation of {topic}:")
        print("-"*80)
        print(topics[topic])
    
    def show_symbols(self, top_n=None):
        """
        Show list of popular trading symbols.
        
        Args:
            top_n: Number of symbols to show (default: 20)
        """
        if top_n is None:
            top_n = "20"
        
        try:
            top_n = int(top_n)
            
            # List of popular cryptocurrencies with USDT pairs
            popular_symbols = [
                "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
                "ADA/USDT", "AVAX/USDT", "DOT/USDT", "MATIC/USDT", "LINK/USDT",
                "LTC/USDT", "DOGE/USDT", "UNI/USDT", "ATOM/USDT", "AAVE/USDT",
                "ETC/USDT", "XLM/USDT", "FIL/USDT", "ALGO/USDT", "NEAR/USDT",
                "CRO/USDT", "ICP/USDT", "VET/USDT", "EOS/USDT", "SAND/USDT",
                "MANA/USDT", "AXS/USDT", "THETA/USDT", "FTM/USDT", "NEO/USDT"
            ]
            
            # Display top_n symbols
            print(f"\nTop {min(top_n, len(popular_symbols))} Popular Cryptocurrency Pairs:")
            print("-"*80)
            
            for i, symbol in enumerate(popular_symbols[:top_n], 1):
                print(f"{i:2}. {symbol}")
            
            print("\nYou can use these symbols with commands like:")
            print(f"  backtest {popular_symbols[0]}")
            print(f"  show_features {popular_symbols[1]}")
            
        except Exception as e:
            print(f"Error showing symbols: {e}")
    
    def clean(self, target=None):
        """
        Clean cached data or temporary files.
        
        Args:
            target: What to clean (cache, logs, results, all)
        """
        if target is None:
            print("Please specify what to clean: cache, logs, results, or all")
            print("Usage: clean <target>")
            return
        
        target = target.lower()
        valid_targets = ["cache", "logs", "results", "all"]
        
        if target not in valid_targets:
            print(f"Invalid target: {target}")
            print(f"Valid options: {', '.join(valid_targets)}")
            return
        
        try:
            paths_to_clean = []
            
            if target in ["cache", "all"]:
                paths_to_clean.append(self.base_dir / "data" / "cache")
            
            if target in ["logs", "all"]:
                paths_to_clean.append(self.base_dir / "logs")
            
            if target in ["results", "all"]:
                paths_to_clean.append(self.base_dir / "results")
            
            # Clean each path
            for path in paths_to_clean:
                if not path.exists():
                    print(f"Path does not exist: {path}")
                    continue
                
                print(f"Cleaning {path}...")
                
                # Keep directories, remove files
                for item in path.glob("*"):
                    if item.is_file():
                        if item.name != ".gitkeep":
                            item.unlink()
                            print(f"  Removed: {item.name}")
                    elif item.is_dir() and target in ["results", "all"]:
                        # For results, also remove subdirectories
                        import shutil
                        shutil.rmtree(item)
                        print(f"  Removed directory: {item.name}")
            
            print(f"Finished cleaning {target}.")
            
        except Exception as e:
            print(f"Error cleaning {target}: {e}")


if __name__ == "__main__":
    # Run the assistant
    assistant = TradingAssistant()
    assistant.run() 