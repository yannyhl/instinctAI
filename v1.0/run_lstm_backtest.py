#!/usr/bin/env python3
"""
LSTM Backtest Runner
-------------------
Script to run backtests using the LSTM strategy with volume profile analysis.
"""

import os
import sys
import logging
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

import config
from data.data_loader import DataLoader
from strategies.lstm_strategy import LSTMStrategy
from utils.backtest import Backtest
from utils.performance import calculate_performance_metrics, plot_performance

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'logs', f'lstm_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run LSTM strategy backtest')
    
    parser.add_argument('symbol', type=str, help='Trading symbol (e.g., BTC/USDT)')
    parser.add_argument('start_date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('end_date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('timeframe', type=str, help='Timeframe (e.g., 1h, 4h, 1d)')
    parser.add_argument('initial_capital', type=float, help='Initial capital')
    
    parser.add_argument('--sequence_length', type=int, default=60, 
                        help='Sequence length for LSTM model')
    parser.add_argument('--prediction_horizon', type=int, default=5, 
                        help='Prediction horizon for LSTM model')
    parser.add_argument('--threshold_pct', type=float, default=1.0, 
                        help='Threshold percentage for signal generation')
    parser.add_argument('--no_volume_profile', action='store_true', 
                        help='Disable volume profile analysis')
    parser.add_argument('--train_split', type=float, default=0.7, 
                        help='Portion of data to use for training')
    parser.add_argument('--load_model', action='store_true', 
                        help='Load pre-trained model instead of training')
    parser.add_argument('--save_model', action='store_true', 
                        help='Save trained model after backtest')
    
    return parser.parse_args()

def main():
    """Main function to run LSTM backtest."""
    # Parse arguments
    args = parse_args()
    
    logger.info(f"Starting LSTM backtest for {args.symbol} from {args.start_date} to {args.end_date}")
    logger.info(f"Parameters: timeframe={args.timeframe}, initial_capital={args.initial_capital}")
    logger.info(f"LSTM parameters: sequence_length={args.sequence_length}, prediction_horizon={args.prediction_horizon}")
    
    try:
        # Calculate an earlier start date to ensure enough historical data
        # Convert start_date to datetime
        start_date_dt = datetime.strptime(args.start_date, '%Y-%m-%d')
        
        # For daily data, go back at least sequence_length+100 days to ensure enough data
        if args.timeframe == '1d':
            data_start_date = (start_date_dt - timedelta(days=args.sequence_length+100)).strftime('%Y-%m-%d')
        elif args.timeframe == '1h':
            # For hourly data, go back at least sequence_length+100 hours
            data_start_date = (start_date_dt - timedelta(hours=args.sequence_length+100)).strftime('%Y-%m-%d')
        else:
            # Default: go back 3x the sequence length
            data_start_date = (start_date_dt - timedelta(days=args.sequence_length*3)).strftime('%Y-%m-%d')
        
        logger.info(f"Loading data from {data_start_date} to ensure sufficient history for LSTM model")
        
        # Load data with earlier start date
        data_loader = DataLoader()
        data = data_loader.load_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=data_start_date,  # Use earlier date for loading
            end_date=args.end_date
        )
        
        if data is None or len(data) == 0:
            logger.error(f"No data available for {args.symbol} in the specified date range")
            return
        
        logger.info(f"Loaded {len(data)} data points for {args.symbol}")
        
        # Filter for actual backtest period
        backtest_data = data[data.index >= pd.Timestamp(args.start_date)]
        logger.info(f"Using {len(backtest_data)} data points for backtesting")
        
        # Split data into train and test sets (using full dataset)
        train_size = int(len(data) * args.train_split)
        train_data = data.iloc[:train_size]
        
        # Make sure we have enough history for test data
        # Test data should include history needed for the first prediction
        test_start_idx = max(0, train_size - args.sequence_length)
        test_data = data.iloc[test_start_idx:]
        
        logger.info(f"Using {len(train_data)} points for training and {len(test_data)} points for testing")
        logger.info(f"Test data includes {train_size - test_start_idx} points of history for initial predictions")
        
        # Initialize LSTM strategy
        strategy = LSTMStrategy(
            symbol=args.symbol,
            sequence_length=args.sequence_length,
            prediction_horizon=args.prediction_horizon,
            threshold_pct=args.threshold_pct,
            use_volume_profile=not args.no_volume_profile
        )
        
        # Load or train model
        if args.load_model:
            logger.info("Loading pre-trained LSTM model")
            if not strategy.load():
                logger.error("Failed to load pre-trained model. Training new model instead.")
                strategy.train(train_data)
        else:
            logger.info("Training LSTM model")
            strategy.train(train_data)
        
        # Run backtest on test data
        backtest = Backtest(
            strategy=strategy,
            data=test_data,
            initial_capital=args.initial_capital,
            commission=0.001  # 0.1% commission
        )
        
        results = backtest.run()
        
        # Calculate and display performance metrics
        metrics = calculate_performance_metrics(results)
        
        logger.info("Backtest Results:")
        logger.info(f"Total Return: {metrics['total_return']:.2f}%")
        logger.info(f"Annual Return: {metrics['annual_return']:.2f}%")
        logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
        logger.info(f"Win Rate: {metrics['win_rate']:.2f}%")
        
        # Plot performance
        fig = plot_performance(results)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = os.path.join(script_dir, 'results', f'lstm_backtest_{args.symbol.replace("/", "_")}_{timestamp}')
        os.makedirs(results_dir, exist_ok=True)
        
        # Save performance plot
        fig.savefig(os.path.join(results_dir, 'performance.png'))
        
        # Save results to CSV
        results.to_csv(os.path.join(results_dir, 'backtest_results.csv'))
        
        # Save metrics to text file
        with open(os.path.join(results_dir, 'metrics.txt'), 'w') as f:
            for key, value in metrics.items():
                f.write(f"{key}: {value}\n")
        
        # Save model if requested
        if args.save_model:
            logger.info("Saving LSTM model")
            strategy.save()
        
        logger.info(f"Results saved to {results_dir}")
        
        # Plot predictions
        if len(test_data) > args.sequence_length + 30:
            pred_fig = strategy.plot_predictions(test_data, lookback_periods=30)
            pred_fig.savefig(os.path.join(results_dir, 'predictions.png'))
        
        logger.info("LSTM backtest completed successfully")
        
    except Exception as e:
        logger.exception(f"Error during backtest: {str(e)}")
        return

if __name__ == "__main__":
    main() 