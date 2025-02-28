#!/usr/bin/env python
"""
ML Ensemble Example
------------------
Example script demonstrating how to train and use the ML ensemble framework
with the AdaptiveMetaStrategy.

This script:
1. Loads historical data
2. Trains an ML ensemble
3. Evaluates the ensemble
4. Integrates the ensemble with AdaptiveMetaStrategy
5. Runs a backtest
"""

import os
import sys
import logging
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt

# Add parent directory to path to allow importing from project
project_dir = Path(__file__).resolve().parent.parent.parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# Import project modules
from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager
from advanced_trading.models.ml_ensemble.model_factory import ModelFactory
from advanced_trading.models.ml_ensemble.feature_engineering import FeatureEngineer
from advanced_trading.models.ml_ensemble.ensemble_trainer import EnsembleTrainer
from advanced_trading.models.ml_ensemble.adaptive_integration import AdaptiveMLStrategy
from advanced_trading.strategies.adaptive_meta_strategy import AdaptiveMetaStrategy
from advanced_trading.utils.bayesian_changepoint import detect_market_regimes
from advanced_trading.utils.data_downloader import download_historical_data
from advanced_trading.backtest.engine import run_backtest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='ML Ensemble Example')
    
    parser.add_argument('--symbol', type=str, default='BTC',
                        help='Trading symbol (default: BTC)')
    parser.add_argument('--timeframe', type=str, default='1h',
                        help='Trading timeframe (default: 1h)')
    parser.add_argument('--start-date', type=str, default='2023-01-01',
                        help='Start date for data (default: 2023-01-01)')
    parser.add_argument('--end-date', type=str, default=None,
                        help='End date for data (default: today)')
    
    parser.add_argument('--train-only', action='store_true',
                        help='Only train the ML ensemble without running backtest')
    parser.add_argument('--backtest-only', action='store_true',
                        help='Only run backtest with existing ML ensemble')
    
    parser.add_argument('--data-dir', type=str, default='data',
                        help='Directory for data files')
    parser.add_argument('--models-dir', type=str, default='models',
                        help='Directory for model files')
    parser.add_argument('--results-dir', type=str, default='results',
                        help='Directory for results files')
    
    parser.add_argument('--initial-capital', type=float, default=10000,
                        help='Initial capital for backtest')
    parser.add_argument('--commission', type=float, default=0.001,
                        help='Commission rate for backtest')
    
    return parser.parse_args()

def load_data(symbol, timeframe, start_date, end_date, data_dir):
    """
    Load historical data, downloading if necessary.
    
    Parameters:
    -----------
    symbol : str
        Trading symbol
    timeframe : str
        Trading timeframe
    start_date : str
        Start date for data
    end_date : str
        End date for data
    data_dir : str
        Directory for data files
        
    Returns:
    --------
    pd.DataFrame
        Historical OHLCV data
    """
    # Ensure data directory exists
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Define file path
    file_path = data_dir / f"{symbol}_{timeframe}_{start_date}_{end_date or 'latest'}.csv"
    
    # Load data if it exists
    if file_path.exists():
        logger.info(f"Loading data from {file_path}")
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    else:
        logger.info(f"Downloading data for {symbol}_{timeframe} from {start_date} to {end_date or 'latest'}")
        df = download_historical_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        # Save to file
        df.to_csv(file_path)
        logger.info(f"Saved data to {file_path}")
    
    return df

def train_ml_ensemble(data, symbol, timeframe, models_dir, results_dir):
    """
    Train ML ensemble model.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Historical OHLCV data
    symbol : str
        Trading symbol
    timeframe : str
        Trading timeframe
    models_dir : str
        Directory for model files
    results_dir : str
        Directory for results files
        
    Returns:
    --------
    EnsembleManager
        Trained ensemble model
    """
    # Ensure directories exist
    models_dir = Path(models_dir)
    results_dir = Path(results_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Create ensemble trainer
    trainer = EnsembleTrainer(
        data_dir=str(Path(data.name).parent) if hasattr(data, 'name') else ".",
        output_dir=str(models_dir),
        prediction_type='classification',
        target_horizon=5,  # 5 periods ahead
        cv_folds=5,
        ensemble_method='weighted_avg',
        regime_aware=True
    )
    
    # Prepare feature engineering
    feature_engineer = FeatureEngineer(
        handle_missing='fill',
        scaling='standard',
        feature_selection='mutual_info',
        n_features=50
    )
    
    # Create features and target
    features = feature_engineer.create_features(data)
    target = feature_engineer.create_target_variable(
        data,
        method='binary_direction',
        horizon=trainer.target_horizon,
        threshold=0.0  # Any movement
    )
    
    # Detect market regimes
    regimes = detect_market_regimes(data['close'], n_regimes=3)
    
    # Train ensemble
    logger.info("Training ML ensemble...")
    ensemble = trainer.train_ensemble(
        features=features,
        target=target,
        regimes=regimes,
        use_predefined_models=True,
        include_neural=False  # Add neural nets if you have GPU
    )
    
    # Evaluate ensemble
    logger.info("Evaluating ML ensemble...")
    eval_metrics = trainer.evaluate_ensemble(
        features=features,
        target=target,
        regimes=regimes,
        evaluation_type='time_series_cv'
    )
    
    # Log performance
    logger.info(f"Ensemble performance: {eval_metrics['overall']}")
    
    # Visualize performance
    trainer.visualize_performance()
    
    # Save ensemble
    model_name = f"{symbol}_{timeframe}_ensemble.joblib"
    trainer.save_ensemble(model_name)
    logger.info(f"Saved ensemble to {models_dir / model_name}")
    
    return ensemble

def run_adaptive_backtest(data, symbol, ensemble_path, initial_capital, commission, results_dir):
    """
    Run backtest with AdaptiveMetaStrategy and ML ensemble.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Historical OHLCV data
    symbol : str
        Trading symbol
    ensemble_path : str
        Path to trained ensemble model
    initial_capital : float
        Initial capital for backtest
    commission : float
        Commission rate for backtest
    results_dir : str
        Directory for results files
        
    Returns:
    --------
    dict
        Backtest results
    """
    # Ensure results directory exists
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Create ML strategy
    ml_strategy = AdaptiveMLStrategy(
        ensemble_path=ensemble_path,
        symbol=symbol
    )
    
    # Create other strategies for the meta-strategy
    strategies = {
        'ml_ensemble': ml_strategy,
        # Add other strategies here if needed
    }
    
    # Create AdaptiveMetaStrategy
    meta_strategy = AdaptiveMetaStrategy(
        strategies=strategies,
        base_allocations={'ml_ensemble': 1.0},  # Start with 100% to ML
        lookback_window=60,
        regime_memory=252,
        allocation_method='hrp',
        max_allocation=1.0,
        min_allocation=0.0
    )
    
    # Prepare market data for backtest (converting single df to dict)
    market_data = {symbol: data}
    
    # Run backtest
    logger.info("Running backtest with AdaptiveMetaStrategy and ML ensemble...")
    results = run_backtest(
        strategy=meta_strategy,
        market_data=market_data,
        initial_capital=initial_capital,
        commission=commission,
        slippage=0.0005,
        leverage=1.0
    )
    
    # Save results
    results_filename = f"{symbol}_adaptive_ml_backtest_{datetime.now().strftime('%Y%m%d')}.json"
    results_path = results_dir / results_filename
    
    with open(results_path, 'w') as f:
        import json
        json.dump(results, f, indent=4)
    
    logger.info(f"Saved backtest results to {results_path}")
    
    # Plot equity curve
    plt.figure(figsize=(12, 6))
    plt.plot(results['equity_curve'])
    plt.title(f"Equity Curve - {symbol} - AdaptiveMetaStrategy with ML")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.grid(True)
    
    # Save plot
    plot_filename = f"{symbol}_adaptive_ml_equity_{datetime.now().strftime('%Y%m%d')}.png"
    plot_path = results_dir / plot_filename
    plt.savefig(plot_path)
    plt.close()
    
    logger.info(f"Saved equity curve plot to {plot_path}")
    
    return results

def main():
    """Main function"""
    args = parse_args()
    
    # Set end date to today if not specified
    if args.end_date is None:
        args.end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Load data
    data = load_data(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=args.start_date,
        end_date=args.end_date,
        data_dir=args.data_dir
    )
    
    # Ensure all required columns are present
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in data.columns:
            logger.error(f"Required column {col} not found in data")
            return
    
    # Define ensemble model path
    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    model_name = f"{args.symbol}_{args.timeframe}_ensemble.joblib"
    ensemble_path = models_dir / model_name
    
    # Train ML ensemble if needed
    if not args.backtest_only and (not ensemble_path.exists() or not args.train_only):
        train_ml_ensemble(
            data=data,
            symbol=args.symbol,
            timeframe=args.timeframe,
            models_dir=args.models_dir,
            results_dir=args.results_dir
        )
    
    # Run backtest
    if not args.train_only:
        if not ensemble_path.exists():
            logger.error(f"Ensemble model not found at {ensemble_path}")
            return
        
        run_adaptive_backtest(
            data=data,
            symbol=args.symbol,
            ensemble_path=str(ensemble_path),
            initial_capital=args.initial_capital,
            commission=args.commission,
            results_dir=args.results_dir
        )

if __name__ == "__main__":
    main() 