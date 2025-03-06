#!/usr/bin/env python
"""
Quick test script for advanced_trading ML strategy
"""

import os
import sys
from pathlib import Path
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the current directory to path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import our modules
import config
from strategies.ml_strategy import MLEnsembleStrategy
from data.data_loader import DataLoader

def main():
    """Main function to run a quick test"""
    # Configuration
    symbol = "BTC/USDT"
    start_date = "2023-01-01"
    end_date = "2023-03-01"  # Just 2 months
    timeframe = "1d"
    
    logger.info(f"Running quick test for {symbol} from {start_date} to {end_date}")
    
    # Load data
    data_loader = DataLoader(
        cache_dir=config.DATA_DIR / "cache",
        primary_source="binance"
    )
    
    data = data_loader.load_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe
    )
    
    if data is None or data.empty:
        logger.error(f"Failed to load data for {symbol}")
        return 1
    
    logger.info(f"Loaded {len(data)} data points")
    
    # Initialize strategy with reduced parameters for quick testing
    strategy_config = config.STRATEGY_CONFIGS["ml_ensemble"].copy()
    strategy_config["symbols"] = [symbol]
    strategy_config["lookback_window"] = 10  # Reduce lookback window
    strategy_config["training_window"] = 30  # Use just 30 days of data for training
    
    logger.info("Initializing ML strategy with reduced parameters...")
    strategy = MLEnsembleStrategy(
        config=strategy_config,
        model_dir=str(config.MODELS_DIR / "ml_ensemble")
    )
    
    # Prepare data for the strategy
    logger.info("Preparing data...")
    prepared_data = strategy.prepare_features(data, symbol)
    
    # Reduce the feature set for faster testing
    feature_cols = [col for col in prepared_data.columns if col not in ['open', 'high', 'low', 'close', 'volume', 'direction']]
    
    # Just keep a subset of features for quick testing
    if len(feature_cols) > 10:
        keep_features = feature_cols[:10] + ['direction']
        prepared_data = prepared_data[['open', 'high', 'low', 'close', 'volume'] + keep_features]
    
    logger.info(f"Using {len(feature_cols)} features for analysis")
    
    # Train a model
    logger.info("Training models...")
    try:
        strategy.models[symbol] = strategy.train_models(prepared_data, symbol)
        logger.info("Models trained successfully")
    except Exception as e:
        logger.error(f"Error training models: {e}")
        return 1
    
    # Generate predictions
    logger.info("Generating predictions...")
    predictions = strategy.generate_predictions(prepared_data, symbol)
    
    # Generate signals
    signals = strategy.generate_signals(predictions, symbol)
    
    # Create a simple results DataFrame
    results = pd.DataFrame(index=prepared_data.index)
    results['close'] = prepared_data['close'] if 'close' in prepared_data.columns else data['close']
    results['prediction'] = predictions
    results['signal'] = signals
    
    # Calculate some basic metrics
    buy_signals = results[results['signal'] > 0]
    sell_signals = results[results['signal'] < 0]
    
    logger.info(f"Generated {len(buy_signals)} buy signals and {len(sell_signals)} sell signals")
    
    # Plot the results
    plt.figure(figsize=(12, 6))
    plt.plot(results.index, results['close'], label='Price')
    
    # Plot buy signals
    plt.scatter(buy_signals.index, buy_signals['close'], marker='^', color='green', label='Buy')
    
    # Plot sell signals
    plt.scatter(sell_signals.index, sell_signals['close'], marker='v', color='red', label='Sell')
    
    plt.title(f"{symbol} Price and Signals")
    plt.legend()
    plt.grid(True)
    
    # Save the plot
    results_dir = config.RESULTS_DIR
    os.makedirs(results_dir, exist_ok=True)
    plt.savefig(results_dir / f"quick_test_{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    
    logger.info(f"Quick test completed and results saved to {results_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 