"""
InstinctAI Configuration Module
-------------------------------
Central configuration for all system components
"""

import os
from dotenv import load_dotenv
import logging
from pathlib import Path

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"

# Create necessary directories
for directory in [DATA_DIR, LOG_DIR, MODEL_DIR]:
    directory.mkdir(exist_ok=True)

# API Keys
HYPERLIQUID_API_KEY = os.getenv("HYPERLIQUID_API_KEY")
HYPERLIQUID_SECRET_KEY = os.getenv("HYPERLIQUID_SECRET_KEY")
HYPERLIQUID_WALLET_ADDRESS = os.getenv("HYPERLIQUID_WALLET_ADDRESS")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
FRED_API_KEY = os.getenv("FRED_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", OPENAI_API_KEY)  # Fallback to OpenAI key if not set
TAAPI_API_KEY = os.getenv("TAAPI_API_KEY")

# Trading Configuration
TRADING_CONFIG = {
    "default_symbol": "BTC",
    "default_timeframe": "1h",
    "initial_capital": 2000.0,
    "max_risk_per_trade": 0.02,  # 2% max risk per trade
    "trading_fee": 0.001,  # 0.1% trading fee
    "live_trading_enabled": False,  # Start in paper trading mode by default
}

# Assistant Configuration
ASSISTANT_CONFIG = {
    "model": "claude-3-5-sonnet-20240620",
    "max_tokens": 4000,
    "conversation_history_length": 10,
    "port": 8000,  # Port for the assistant API
    "host": "0.0.0.0",  # Host for the assistant API
}

# Backtesting Configuration
BACKTEST_CONFIG = {
    "default_start_date": "2023-01-01",
    "default_end_date": "2023-12-31",
    "plot_style": "candlestick",
    "save_plots": True,
}

# Database Configuration
DATABASE_CONFIG = {
    "url": "sqlite:///instinct_ai.db",
    "echo": False,
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": logging.INFO,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_handler": {
        "filename": str(LOG_DIR / "instinct_ai.log"),
        "mode": "a",
    },
}

# GPU Configuration
GPU_CONFIG = {
    "use_gpu": True,
    "gpu_memory_limit": 0.7,  # Use 70% of GPU memory
    "mixed_precision": True,
}

# Strategy Parameters (default values)
STRATEGY_PARAMS = {
    "funding_momentum": {
        "funding_threshold": 0.0001,          # Min funding rate to consider
        "momentum_period": 14,
        "rsi_period": 14,
        "rsi_overbought": 65,                 # RSI overbought threshold
        "rsi_oversold": 45,                   # RSI oversold threshold
        "mean_reversion_period": 50,          # Period for mean reversion calculation
        "risk_pct": 0.01,                     # Base risk per trade
        "max_risk_pct": 0.03,                 # Maximum risk per trade
        "kelly_fraction": 0.5,                # Kelly criterion fraction (conservative)
        "use_kelly": True,                    # Use Kelly criterion for sizing
        "trailing_stop": 0.02,                # Trailing stop (2%)
        "adaptive_trailing": True,            # Use ATR-based trailing stops
        "atr_trailing_multiplier": 2.0,       # ATR multiplier for trailing stop
        "atr_period": 14,                     # ATR period
        "take_profit": 0.05,                  # Take profit level (5%)
        "time_stop": 20,                      # Exit after N bars if neither TP nor SL hit
        "volatility_lookback": 21,            # Period for volatility calculation
    },
    "aggressive_funding": {
        "funding_threshold": 0.00005,         # Much lower funding threshold (50% of original)
        "momentum_period": 8,                 # Shorter momentum calculation period
        "rsi_period": 7,                      # Shorter RSI period for faster signals
        "rsi_overbought": 60,                 # Lower overbought threshold for more signals
        "rsi_oversold": 40,                   # Higher oversold threshold for more signals
        "risk_pct": 0.025,                    # Higher base risk per trade (2.5% vs 1%)
        "max_risk_pct": 0.05,                 # Higher maximum risk (5% vs 3%)
        "kelly_fraction": 0.7,                # Less conservative Kelly fraction
        "trailing_stop": 0.015,               # Tighter trailing stop (1.5% vs 2%)
        "adaptive_trailing": True,            # Use ATR-based trailing stops
        "atr_trailing_multiplier": 1.5,       # Lower multiplier for tighter stops
        "atr_period": 10,                     # Shorter ATR period
        "take_profit": 0.08,                  # Higher take profit target (8% vs 5%)
        "time_stop": 15,                      # Shorter time stop for faster turnover
        "volatility_lookback": 14,            # Shorter volatility lookback period
    },
    "renaissance": {
        # Primary signal parameters
        "funding_threshold": 0.00002,         # Lower threshold to focus on statistical edge
        "funding_z_score_threshold": 2.0,     # Funding rate z-score for outlier detection
        "mean_reversion_period": 20,          # Period for mean reversion signals
        "momentum_period": 12,                # Period for momentum signals
        "volatility_period": 20,              # Period for volatility calculation
        
        # Machine learning model parameters
        "use_ml_regime_detection": True,      # Use ML for regime detection
        "feature_lookback": 100,              # Lookback period for feature engineering
        "regime_lookback": 500,               # Data points for regime detection training
        
        # Signal filtering parameters
        "min_signal_strength": 0.2,           # Minimum combined signal strength (0-1)
        "significance_level": 0.05,           # Statistical significance threshold (p-value)
        "signal_smoothing": 3,                # EMA period for signal smoothing
        
        # Position sizing parameters
        "base_risk_pct": 0.01,                # Base risk percentage per trade (1%)
        "max_risk_pct": 0.05,                 # Maximum risk percentage (5%)
        "kelly_fraction": 0.3,                # Conservative Kelly fraction
        "position_heat": 0.8,                 # Maximum total portfolio heat (% committed)
        
        # Risk management parameters
        "use_dynamic_stops": True,            # Use dynamic stop losses
        "atr_period": 14,                     # ATR period for stops
        "atr_multiplier": 2.5,                # ATR multiplier for stop distance
        "profit_take_atr_mult": 4.0,          # Profit target as ATR multiple
        "time_stop": 24,                      # Exit after N bars if neither TP nor SL hit
        
        # Multi-timeframe parameters
        "use_multi_timeframe": True,          # Use multi-timeframe analysis
        "higher_tf_weight": 0.6,              # Weight given to higher timeframe signals
        "lower_tf_weight": 0.4,               # Weight given to lower timeframe signals
        
        # Dynamic strategy allocation
        "strategy_allocation": True,          # Dynamically allocate to sub-strategies
        "trend_weight": 0.5,                  # Base weight for trend strategies
        "mean_rev_weight": 0.5,               # Base weight for mean reversion strategies
        
        # Execution parameters
        "use_smart_execution": True,          # Use smart execution algorithms
        "min_liquidity_ratio": 10.0,          # Minimum liquidity to position size ratio
    }
}

def get_logging_config():
    """Returns the logging configuration."""
    return LOGGING_CONFIG

def get_strategy_params(strategy_name):
    """Returns parameters for the specified strategy."""
    return STRATEGY_PARAMS.get(strategy_name, {})