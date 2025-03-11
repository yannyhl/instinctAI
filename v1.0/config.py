"""
Advanced Trading System Configuration
------------------------------------
Global configuration settings for the advanced trading system.
"""

import os
from pathlib import Path
import logging
import yaml
import datetime

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
RESULTS_DIR = BASE_DIR / "results"
LOG_DIR = BASE_DIR / "logs"

# Create necessary directories
for directory in [DATA_DIR, MODELS_DIR, RESULTS_DIR, LOG_DIR]:
    os.makedirs(directory, exist_ok=True)

# Configure logging
LOG_FILE = LOG_DIR / f"trading_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

# GPU Configuration
GPU_CONFIG = {
    "use_gpu": True,
    "memory_limit": 0.8,  # Use up to 80% of GPU memory
    "precision": "float32"
}

# Trading parameters
TRADING_CONFIG = {
    "initial_capital": 10000,
    "commission": 0.001,  # 0.1% commission
    "slippage": 0.0005,   # 0.05% slippage
    "symbols": ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD", "XRP/USD"],
    "base_currency": "USD",
    "risk_free_rate": 0.02,  # 2% annual risk-free rate
    "position_sizing": {
        "method": "risk_based",  # Options: equal, risk_based, kelly
        "risk_per_trade": 0.02,  # 2% risk per trade
        "max_position_size": 0.2  # Maximum 20% of portfolio in single position
    }
}

# Backtesting configuration
BACKTEST_CONFIG = {
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "rebalance_frequency": "1d",  # 1 day rebalancing
    "data_frequency": "1h",       # 1 hour data
    "benchmark": "BTC/USD",       # Benchmark asset
    "parallel": True,             # Use parallel processing
    "num_workers": 4,             # Number of parallel workers
    "use_gpu": GPU_CONFIG["use_gpu"]
}

# Strategy configurations
STRATEGY_CONFIGS = {
    "ml_ensemble": {
        "lookback_window": 30,
        "prediction_horizon": 1,
        "training_window": 252 * 2,
        "retraining_frequency": 30,
        "threshold_buy": 0.65,
        "threshold_sell": 0.65,
        "symbols": TRADING_CONFIG["symbols"]
    },
    
    "trend_following": {
        "short_window": 10,
        "medium_window": 20,
        "long_window": 50,
        "volatility_window": 20,
        "trend_threshold": 0.05,
        "symbols": TRADING_CONFIG["symbols"]
    },
    
    "mean_reversion": {
        "lookback_window": 20,
        "entry_zscore": 2.0,
        "exit_zscore": 0.5,
        "max_holding_period": 5,
        "stationarity_pvalue": 0.05,
        "symbols": TRADING_CONFIG["symbols"]
    },
    
    "stat_arb": {
        "pairs": [
            ("BTC/USD", "ETH/USD"),
            ("ETH/USD", "SOL/USD")
        ],
        "lookback_window": 30,
        "entry_zscore": 2.0,
        "exit_zscore": 0.5,
        "max_holding_period": 5,
        "coint_pvalue": 0.05
    }
}

# Data sources configuration
DATA_CONFIG = {
    "sources": ["binance", "coinbase", "kraken"],
    "primary": "binance",  # Primary data source
    "cache_data": True,
    "cache_dir": DATA_DIR / "cache",
    "remote_data": False,  # Whether to use remote data service
    "api_keys": {
        "binance": os.environ.get("BINANCE_API_KEY", ""),
        "binance_secret": os.environ.get("BINANCE_SECRET_KEY", ""),
        "coinbase": os.environ.get("COINBASE_API_KEY", ""),
        "coinbase_secret": os.environ.get("COINBASE_SECRET_KEY", ""),
        "kraken": os.environ.get("KRAKEN_API_KEY", ""),
        "kraken_secret": os.environ.get("KRAKEN_SECRET_KEY", "")
    }
}

# Walk-forward optimization settings
OPTIMIZATION_CONFIG = {
    "enabled": True,
    "train_size": 252 * 2,  # 2 years of training data
    "test_size": 90,        # 3 months of test data
    "optimization_method": "bayesian",  # Options: grid, random, bayesian
    "n_iterations": 50,     # Number of iterations for optimization
    "parallel": True,       # Use parallel processing
    "n_jobs": 4             # Number of jobs for parallelization
}

# Risk management settings
RISK_CONFIG = {
    "stop_loss": {
        "enabled": True,
        "type": "adaptive",  # Options: fixed, trailing, adaptive
        "percentage": 0.05,  # 5% stop loss for fixed type
        "atr_multiplier": 3  # For adaptive stop loss based on ATR
    },
    "take_profit": {
        "enabled": True,
        "type": "risk_reward",  # Options: fixed, risk_reward
        "percentage": 0.1,      # 10% take profit for fixed type
        "risk_reward_ratio": 2  # For risk-reward based take profit
    },
    "max_drawdown": 0.25,  # Maximum allowed drawdown (25%)
    "max_risk_per_trade": 0.02,  # Maximum risk per trade (2%)
    "max_correlated_trades": 3,  # Maximum number of correlated trades
    "target_volatility": 0.15    # Target annualized volatility
}

# Live trading settings
LIVE_CONFIG = {
    "enabled": False,  # Whether live trading is enabled
    "exchange": "binance",
    "paper_trading": True,  # Use paper trading mode
    "order_types": ["market", "limit"],
    "default_order_type": "limit",
    "limit_order_expiration": 300,  # 5 minutes
    "retry_failed_orders": True,
    "max_retries": 3,
    "position_update_interval": 60,  # Update positions every 60 seconds
    "heartbeat_interval": 300       # Heartbeat check every 5 minutes
}

# Notifications configuration
NOTIFICATION_CONFIG = {
    "enabled": True,
    "methods": ["email", "telegram"],
    "email": {
        "smtp_server": os.environ.get("SMTP_SERVER", ""),
        "smtp_port": int(os.environ.get("SMTP_PORT", 587)),
        "sender_email": os.environ.get("SENDER_EMAIL", ""),
        "sender_password": os.environ.get("SENDER_PASSWORD", ""),
        "recipient_email": os.environ.get("RECIPIENT_EMAIL", "")
    },
    "telegram": {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "")
    },
    "notify_on": {
        "trade": True,
        "error": True,
        "warning": True,
        "daily_summary": True
    }
}

# Load environment-specific config if exists
env = os.environ.get("TRADING_ENV", "development")
env_config_path = BASE_DIR / f"config_{env}.yaml"

if os.path.exists(env_config_path):
    with open(env_config_path, 'r') as file:
        env_config = yaml.safe_load(file)
        
        # Update configs with environment-specific values
        for config_name, config_values in env_config.items():
            if config_name in globals() and isinstance(globals()[config_name], dict):
                globals()[config_name].update(config_values)

# Initialize logging
def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    
    # Reduce verbosity of external libraries
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: {LOG_FILE}")
    
    return logger

# Create logger
logger = setup_logging()
logger.info(f"Configuration loaded in {env} environment")

# Log system information
try:
    import platform
    import psutil
    
    system_info = {
        "os": platform.system(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_available": f"{psutil.virtual_memory().available / (1024**3):.2f} GB"
    }
    
    logger.info(f"System information: {system_info}")
    
    if GPU_CONFIG["use_gpu"]:
        try:
            import torch
            gpu_available = torch.cuda.is_available()
            gpu_count = torch.cuda.device_count() if gpu_available else 0
            gpu_info = {
                "gpu_available": gpu_available,
                "gpu_count": gpu_count
            }
            if gpu_available:
                gpu_info["gpu_name"] = torch.cuda.get_device_name(0)
                gpu_info["gpu_memory"] = f"{torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB"
            
            logger.info(f"GPU information: {gpu_info}")
        except ImportError:
            logger.warning("PyTorch not available for GPU detection")
except ImportError:
    logger.warning("psutil not available for system information") 