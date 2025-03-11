#!/usr/bin/env python

"""
Volume Profile Strategy Runner
--------------------------
Script to run the volume profile based trading strategy, which uses volume-at-price 
distribution to identify key support and resistance levels.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import time
import matplotlib.pyplot as plt

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import project modules
import config
from strategies.volume_profile_strategy import VolumeProfileStrategy
from data.data_loader import DataLoader
from utils.performance import calculate_performance_metrics, create_tear_sheet
from models.volume_profile import VolumeProfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'logs', f'volume_profile_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run Volume Profile Trading Strategy')
    
    parser.add_argument('--mode', type=str, default='backtest',
                      choices=['backtest', 'live', 'paper', 'analyze'],
                      help='Trading mode (analyze mode just analyzes volume profiles)')
    
    parser.add_argument('--symbol', type=str, default='BTC/USDT',
                      help='Trading symbol')
    
    parser.add_argument('--start_date', type=str, default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                      help='Start date for data (YYYY-MM-DD)')
    
    parser.add_argument('--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                      help='End date for data (YYYY-MM-DD)')
    
    parser.add_argument('--capital', type=float, default=10000.0,
                      help='Initial capital')
    
    parser.add_argument('--timeframe', type=str, default='1d',
                      help='Data timeframe (e.g., 1h, 4h, 1d)')
    
    parser.add_argument('--num_bins', type=int, default=50,
                      help='Number of price bins for volume profile')
    
    parser.add_argument('--lookback_period', type=int, default=60,
                      help='Lookback period for volume profile calculation')
    
    parser.add_argument('--value_area_pct', type=float, default=70.0,
                      help='Value area percentage (0-100)')
    
    parser.add_argument('--max_position_size', type=float, default=0.2,
                      help='Maximum position size as fraction of capital')
    
    parser.add_argument('--confidence_threshold', type=float, default=0.7,
                      help='Confidence threshold for trade signals (0-1)')
    
    parser.add_argument('--interval', type=int, default=3600,
                      help='Interval for live trading execution in seconds')
    
    parser.add_argument('--output_dir', type=str, default=None,
                      help='Directory to save results')
    
    parser.add_argument('--rolling_profiles', action='store_true',
                      help='Use rolling volume profiles instead of periodic recalculations')
    
    return parser.parse_args()

def analyze_volume_profile(args):
    """Analyze volume profile for a symbol without trading."""
    logger.info(f"Analyzing volume profile for {args.symbol}")
    
    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(script_dir) / 'results' / f'vol_profile_analysis_{args.symbol.replace("/", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load market data
    data_loader = DataLoader()
    
    try:
        data = data_loader.load_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        if data is None or data.empty:
            logger.error(f"No data loaded for {args.symbol}")
            return
        
        logger.info(f"Loaded {len(data)} data points for {args.symbol}")
        
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        return
    
    # Initialize volume profile
    volume_profile = VolumeProfile(
        num_bins=args.num_bins,
        high_vol_percentile=80,
        value_area_percentage=args.value_area_pct
    )
    
    # Analyze full period volume profile
    full_profile_results = volume_profile.analyze(data)
    
    if full_profile_results is None:
        logger.error("Failed to analyze volume profile")
        return
    
    # Get support and resistance levels
    levels = volume_profile.get_support_resistance_levels(num_levels=5)
    poc = volume_profile.get_poc_level()
    value_area = volume_profile.value_area
    
    # Log results
    logger.info(f"Point of Control (POC): {poc:.2f}")
    logger.info(f"Value Area: {value_area[0]:.2f} - {value_area[1]:.2f}")
    logger.info("Support Levels: " + ", ".join([f"{level:.2f}" for level in levels['support']]))
    logger.info("Resistance Levels: " + ", ".join([f"{level:.2f}" for level in levels['resistance']]))
    
    # Create visualizations
    # Full period volume profile
    fig, ax = plt.subplots(figsize=(12, 6))
    volume_profile.plot_profile(ax=ax)
    ax.set_title(f"Volume Profile for {args.symbol} - {args.start_date} to {args.end_date}")
    plt.savefig(output_dir / 'full_period_volume_profile.png', dpi=300)
    plt.close(fig)
    
    # Price with key levels
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(data.index, data['close'], label='Price')
    
    # Add POC line
    ax.axhline(poc, color='red', linestyle='-', label='POC')
    
    # Add value area
    ax.axhspan(value_area[0], value_area[1], alpha=0.2, color='green', label='Value Area')
    
    # Add support/resistance levels
    for level in levels['support']:
        ax.axhline(level, color='green', linestyle='--', alpha=0.6)
    
    for level in levels['resistance']:
        ax.axhline(level, color='red', linestyle='--', alpha=0.6)
    
    ax.set_title(f"{args.symbol} Price with Volume Profile Levels")
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.legend()
    plt.savefig(output_dir / 'price_with_levels.png', dpi=300)
    plt.close(fig)
    
    # Create multiple volume profiles for different periods
    if len(data) > 100:
        # Split data into multiple periods
        period_length = len(data) // 3
        
        for i in range(3):
            start_idx = i * period_length
            end_idx = min((i + 1) * period_length, len(data))
            
            period_data = data.iloc[start_idx:end_idx]
            
            if len(period_data) < 20:
                continue
                
            period_start = period_data.index[0].strftime('%Y-%m-%d')
            period_end = period_data.index[-1].strftime('%Y-%m-%d')
            
            # Analyze this period
            volume_profile.analyze(period_data)
            
            # Create visualization
            fig, ax = plt.subplots(figsize=(12, 6))
            volume_profile.plot_profile(ax=ax)
            ax.set_title(f"Volume Profile for {args.symbol} - {period_start} to {period_end}")
            plt.savefig(output_dir / f'period_{i+1}_volume_profile.png', dpi=300)
            plt.close(fig)
    
    # Save analysis results
    analysis_results = {
        'symbol': args.symbol,
        'timeframe': args.timeframe,
        'start_date': args.start_date,
        'end_date': args.end_date,
        'poc': float(poc),
        'value_area': [float(value_area[0]), float(value_area[1])],
        'support_levels': [float(level) for level in levels['support']],
        'resistance_levels': [float(level) for level in levels['resistance']],
        'total_volume': float(data['volume'].sum()),
        'avg_daily_volume': float(data['volume'].mean()),
        'current_price': float(data['close'].iloc[-1]),
        'position_relative_to_va': 'In Value Area' if value_area[0] <= data['close'].iloc[-1] <= value_area[1] else 'Outside Value Area',
    }
    
    with open(output_dir / 'volume_profile_analysis.json', 'w') as f:
        json.dump(analysis_results, f, indent=4)
    
    logger.info(f"Analysis completed and saved to {output_dir}")
    return output_dir, analysis_results

def run_backtest(args):
    """Run backtest for the volume profile strategy."""
    logger.info(f"Running volume profile strategy backtest for {args.symbol}")
    
    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(script_dir) / 'results' / f'vol_profile_backtest_{args.symbol.replace("/", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load market data
    data_loader = DataLoader()
    
    try:
        data = data_loader.load_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        if data is None or data.empty:
            logger.error(f"No data loaded for {args.symbol}")
            return
        
        logger.info(f"Loaded {len(data)} data points for {args.symbol}")
        
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        return
    
    # Initialize strategy
    strategy = VolumeProfileStrategy(
        symbol=args.symbol,
        num_bins=args.num_bins,
        lookback_period=args.lookback_period,
        value_area_pct=args.value_area_pct,
        confidence_threshold=args.confidence_threshold,
        max_position_size=args.max_position_size,
        rolling_profiles=args.rolling_profiles
    )
    
    # Run backtest
    logger.info("Running backtest...")
    results = strategy.backtest(
        data=data,
        initial_capital=args.capital
    )
    
    # Save results
    results_df = pd.DataFrame({
        'portfolio_value': results['portfolio_value'],
        'returns': results['returns'],
        'position': results['positions'],
        'signal': results['signals']
    }, index=results['dates'])
    
    results_df.to_csv(output_dir / 'backtest_results.csv')
    
    # Save trades
    trades_df = pd.DataFrame(results['trades'])
    if not trades_df.empty:
        trades_df.to_csv(output_dir / 'trades.csv', index=False)
    
    # Calculate and save metrics
    metrics = calculate_performance_metrics(results_df)
    with open(output_dir / 'performance_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=4)
    
    # Create performance visualization
    create_tear_sheet(results_df, save_path=str(output_dir / 'performance_tearsheet.png'))
    
    # Create strategy-specific visualizations
    strategy.visualize_trades(data, results, save_path=str(output_dir / 'trades_visualization.png'))
    
    # Print summary
    logger.info("Backtest Results:")
    logger.info(f"Total Return: {metrics['total_return']:.2f}%")
    logger.info(f"Annual Return: {metrics['annual_return']:.2f}%")
    logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
    logger.info(f"Number of Trades: {metrics['num_trades']}")
    logger.info(f"Results saved to {output_dir}")
    
    return output_dir, results, metrics

def run_live_trading(args):
    """Run live trading for the volume profile strategy."""
    logger.info(f"Starting volume profile live trading for {args.symbol}")
    logger.info(f"Trading Mode: {'Paper Trading' if args.mode == 'paper' else 'Live Trading'}")
    
    # Validate API keys for exchange access
    if args.mode == 'live':
        if not config.DATA_CONFIG["api_keys"].get("binance"):
            logger.error("No API key found for Binance. Live trading requires API keys.")
            return
    
    # Initialize strategy
    strategy = VolumeProfileStrategy(
        symbol=args.symbol,
        num_bins=args.num_bins,
        lookback_period=args.lookback_period,
        value_area_pct=args.value_area_pct,
        confidence_threshold=args.confidence_threshold,
        max_position_size=args.max_position_size,
        rolling_profiles=args.rolling_profiles
    )
    
    # Initialize data loader for market data updates
    data_loader = DataLoader()
    
    # Initial portfolio state
    portfolio = {
        'cash': args.capital,
        'position': 0,
        'position_value': 0
    }
    
    # Trading history
    trades = []
    
    # Main trading loop
    try:
        while True:
            logger.info(f"Trading cycle started at {datetime.now()}")
            
            # Load recent market data
            start_date = (datetime.now() - timedelta(days=args.lookback_period * 2)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            try:
                market_data = data_loader.load_data(
                    symbol=args.symbol,
                    timeframe=args.timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if market_data is None or market_data.empty:
                    logger.warning(f"No data loaded for {args.symbol}")
                    time.sleep(args.interval)
                    continue
                
                logger.info(f"Loaded {len(market_data)} data points for {args.symbol}")
                
            except Exception as e:
                logger.error(f"Error loading data: {str(e)}")
                time.sleep(args.interval)
                continue
            
            # Current price
            current_price = market_data['close'].iloc[-1]
            
            # Generate signal
            signal = strategy.generate_signal(market_data)
            
            logger.info(f"Current price: {current_price:.2f}, Signal: {signal:.2f}")
            
            if abs(signal) >= args.confidence_threshold:
                # Generate trade
                if signal > 0 and portfolio['position'] <= 0:
                    # Buy signal
                    action = "BUY"
                    size = strategy.get_position_size(portfolio['cash'], current_price)
                    cost = size * current_price
                    
                    if portfolio['position'] < 0:
                        # Close short position first
                        trade = {
                            'timestamp': datetime.now(),
                            'symbol': args.symbol,
                            'action': 'CLOSE_SHORT',
                            'price': current_price,
                            'size': abs(portfolio['position']),
                            'value': abs(portfolio['position']) * current_price,
                            'profit': portfolio['position_value'] - (abs(portfolio['position']) * current_price)
                        }
                        trades.append(trade)
                        
                        # Update portfolio
                        portfolio['cash'] += abs(portfolio['position']) * current_price
                        portfolio['position'] = 0
                        portfolio['position_value'] = 0
                    
                    # Open long position
                    if portfolio['cash'] >= cost:
                        trade = {
                            'timestamp': datetime.now(),
                            'symbol': args.symbol,
                            'action': action,
                            'price': current_price,
                            'size': size,
                            'value': cost
                        }
                        trades.append(trade)
                        
                        # Update portfolio
                        portfolio['cash'] -= cost
                        portfolio['position'] = size
                        portfolio['position_value'] = cost
                        
                        logger.info(f"SIGNAL: {action} {size} {args.symbol} at {current_price:.2f}")
                    else:
                        logger.warning(f"Insufficient funds to execute {action}")
                
                elif signal < 0 and portfolio['position'] >= 0:
                    # Sell signal
                    action = "SELL"
                    
                    if portfolio['position'] > 0:
                        # Close long position first
                        trade = {
                            'timestamp': datetime.now(),
                            'symbol': args.symbol,
                            'action': 'CLOSE_LONG',
                            'price': current_price,
                            'size': portfolio['position'],
                            'value': portfolio['position'] * current_price,
                            'profit': (portfolio['position'] * current_price) - portfolio['position_value']
                        }
                        trades.append(trade)
                        
                        # Update portfolio
                        portfolio['cash'] += portfolio['position'] * current_price
                        portfolio['position'] = 0
                        portfolio['position_value'] = 0
                    
                    # Open short position if supported
                    if args.mode == 'live':
                        # Check if exchange supports shorting
                        # For now, we'll just simulate it
                        size = strategy.get_position_size(portfolio['cash'], current_price)
                        
                        trade = {
                            'timestamp': datetime.now(),
                            'symbol': args.symbol,
                            'action': action,
                            'price': current_price,
                            'size': size,
                            'value': size * current_price
                        }
                        trades.append(trade)
                        
                        # Update portfolio (simulate shorting)
                        portfolio['position'] = -size
                        portfolio['position_value'] = size * current_price
                        
                        logger.info(f"SIGNAL: {action} {size} {args.symbol} at {current_price:.2f}")
            
            # Execute trades in live mode
            if args.mode == 'live' and trades and trades[-1]['timestamp'] == datetime.now():
                # This would connect to exchange API to execute the trade
                logger.info(f"Executing trade: {trades[-1]}")
                # TODO: Implement actual trade execution
            
            # Update portfolio value
            if portfolio['position'] != 0:
                if portfolio['position'] > 0:
                    # Long position
                    portfolio['position_value'] = portfolio['position'] * current_price
                else:
                    # Short position
                    # For short position, value increases as price decreases
                    entry_price = portfolio['position_value'] / abs(portfolio['position'])
                    pnl = entry_price - current_price
                    portfolio['position_value'] = abs(portfolio['position']) * entry_price + abs(portfolio['position']) * pnl
            
            total_value = portfolio['cash'] + portfolio['position_value']
            logger.info(f"Portfolio: Cash={portfolio['cash']:.2f}, Position={portfolio['position']}, Position Value={portfolio['position_value']:.2f}, Total={total_value:.2f}")
            
            # Save trading status
            status = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': args.symbol,
                'price': current_price,
                'signal': signal,
                'position': portfolio['position'],
                'cash': portfolio['cash'],
                'position_value': portfolio['position_value'],
                'total_value': total_value
            }
            
            # Here we would save the status to a file or database
            
            # Wait for next interval
            logger.info(f"Waiting {args.interval} seconds until next cycle")
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info("Trading stopped by user")
    except Exception as e:
        logger.error(f"Error in live trading: {str(e)}")
    
    # Final portfolio summary
    logger.info("Final Portfolio Summary:")
    logger.info(f"Cash: ${portfolio['cash']:.2f}")
    logger.info(f"Position: {portfolio['position']} {args.symbol}")
    logger.info(f"Position Value: ${portfolio['position_value']:.2f}")
    logger.info(f"Total Value: ${portfolio['cash'] + portfolio['position_value']:.2f}")
    logger.info(f"Total Trades: {len(trades)}")
    
    logger.info("Live trading stopped")

def main():
    """Main entry point for the script."""
    # Parse arguments
    args = parse_args()
    
    # Run in selected mode
    if args.mode == 'analyze':
        analyze_volume_profile(args)
    elif args.mode == 'backtest':
        run_backtest(args)
    else:  # live or paper
        run_live_trading(args)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
