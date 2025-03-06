#!/usr/bin/env python

"""
Statistical Arbitrage Strategy Runner
----------------------------------
Script to run the statistical arbitrage strategy for trading cointegrated pairs.
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
import itertools

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import project modules
import config
from strategies.statistical_arbitrage import StatisticalArbitrageStrategy
from data.data_loader import DataLoader
from utils.performance import calculate_performance_metrics, create_tear_sheet
from utils.cointegration import test_cointegration, find_cointegrated_pairs

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'logs', f'stat_arb_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run Statistical Arbitrage Strategy')
    
    parser.add_argument('--mode', type=str, default='backtest',
                      choices=['backtest', 'live', 'paper', 'scan'],
                      help='Trading mode (scan mode just looks for cointegrated pairs)')
    
    parser.add_argument('--symbols', type=str, nargs='+',
                      default=config.TRADING_CONFIG['symbols'],
                      help='Trading pairs to analyze')
    
    parser.add_argument('--pairs', type=str, nargs='+',
                      help='Specific symbol pairs to trade (format: Symbol1,Symbol2)')
    
    parser.add_argument('--start_date', type=str, default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                      help='Start date for data (YYYY-MM-DD)')
    
    parser.add_argument('--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                      help='End date for data (YYYY-MM-DD)')
    
    parser.add_argument('--capital', type=float, default=10000.0,
                      help='Initial capital')
    
    parser.add_argument('--lookback_period', type=int, default=20,
                      help='Lookback period for z-score calculation')
    
    parser.add_argument('--z_threshold', type=float, default=2.0,
                      help='Z-score threshold for entry signals')
    
    parser.add_argument('--exit_z_threshold', type=float, default=0.5,
                      help='Z-score threshold for exit signals')
    
    parser.add_argument('--timeframe', type=str, default='1d',
                      help='Data timeframe (e.g., 1h, 4h, 1d)')
    
    parser.add_argument('--max_position_size', type=float, default=0.2,
                      help='Maximum position size as fraction of capital')
    
    parser.add_argument('--pvalue_threshold', type=float, default=0.05,
                      help='P-value threshold for cointegration test')
    
    parser.add_argument('--interval', type=int, default=3600,
                      help='Interval for live trading execution in seconds')
    
    parser.add_argument('--output_dir', type=str, default=None,
                      help='Directory to save results')
    
    return parser.parse_args()

def find_pairs(args):
    """Find cointegrated pairs from the list of symbols."""
    logger.info(f"Scanning for cointegrated pairs among {len(args.symbols)} symbols")
    
    # Load market data
    data_loader = DataLoader()
    
    # Load data for each symbol
    data = {}
    for symbol in args.symbols:
        try:
            symbol_data = data_loader.load_data(
                symbol=symbol,
                timeframe=args.timeframe,
                start_date=args.start_date,
                end_date=args.end_date
            )
            
            if symbol_data is not None and not symbol_data.empty:
                data[symbol] = symbol_data['close']
                logger.info(f"Loaded {len(symbol_data)} data points for {symbol}")
            else:
                logger.warning(f"No data loaded for {symbol}")
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {str(e)}")
    
    if len(data) < 2:
        logger.error("Need at least 2 symbols with data for pair analysis. Exiting.")
        return []
    
    # Create DataFrame with all price series
    price_df = pd.DataFrame(data)
    
    # Find cointegrated pairs
    cointegrated_pairs = find_cointegrated_pairs(
        price_df, 
        p_value_threshold=args.pvalue_threshold
    )
    
    logger.info(f"Found {len(cointegrated_pairs)} cointegrated pairs:")
    
    # Format results
    results = []
    for pair in cointegrated_pairs:
        symbol1, symbol2, p_value, hedge_ratio = pair
        logger.info(f"{symbol1} - {symbol2}: p-value={p_value:.4f}, hedge ratio={hedge_ratio:.4f}")
        
        results.append({
            'symbol1': symbol1,
            'symbol2': symbol2,
            'p_value': p_value,
            'hedge_ratio': hedge_ratio
        })
    
    # Save results if output dir specified
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(script_dir) / 'results' / f'pairs_scan_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to CSV
    pairs_df = pd.DataFrame(results)
    pairs_df.to_csv(output_dir / 'cointegrated_pairs.csv', index=False)
    
    logger.info(f"Saved cointegrated pairs list to {output_dir / 'cointegrated_pairs.csv'}")
    
    return results

def parse_pairs(pairs_arg):
    """Parse pairs argument into list of symbol pairs."""
    parsed_pairs = []
    
    if pairs_arg:
        for pair_str in pairs_arg:
            # Handle format like "BTC/USDT,ETH/USDT"
            symbols = pair_str.split(',')
            if len(symbols) == 2:
                parsed_pairs.append((symbols[0].strip(), symbols[1].strip()))
    
    return parsed_pairs

def run_backtest(args):
    """Run backtest for the statistical arbitrage strategy."""
    # Parse pairs if provided
    pairs = parse_pairs(args.pairs)
    
    # If no pairs provided, find them automatically
    if not pairs and args.mode != 'scan':
        logger.info("No specific pairs provided. Finding cointegrated pairs automatically.")
        cointegrated_pairs = find_pairs(args)
        
        if cointegrated_pairs:
            pairs = [(p['symbol1'], p['symbol2']) for p in cointegrated_pairs]
        else:
            logger.warning("No cointegrated pairs found.")
            return
    
    logger.info(f"Running statistical arbitrage backtest with {len(pairs)} pairs")
    
    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(script_dir) / 'results' / f'stat_arb_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load market data for all symbols
    all_symbols = set()
    for pair in pairs:
        all_symbols.add(pair[0])
        all_symbols.add(pair[1])
    
    data_loader = DataLoader()
    
    # Load data for each symbol
    data = {}
    for symbol in all_symbols:
        try:
            symbol_data = data_loader.load_data(
                symbol=symbol,
                timeframe=args.timeframe,
                start_date=args.start_date,
                end_date=args.end_date
            )
            
            if symbol_data is not None and not symbol_data.empty:
                data[symbol] = symbol_data
                logger.info(f"Loaded {len(symbol_data)} data points for {symbol}")
            else:
                logger.warning(f"No data loaded for {symbol}")
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {str(e)}")
    
    if len(data) < 2:
        logger.error("Insufficient data loaded. Exiting.")
        return
    
    # Initialize strategy
    strategy = StatisticalArbitrageStrategy(
        pairs=pairs,
        lookback_period=args.lookback_period,
        z_threshold=args.z_threshold,
        exit_z_threshold=args.exit_z_threshold,
        max_position_size=args.max_position_size
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
        'returns': results['returns']
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
    
    # Save pair analysis
    pair_analysis = []
    for pair in pairs:
        symbol1, symbol2 = pair
        
        # Get price series
        price1 = data[symbol1]['close']
        price2 = data[symbol2]['close']
        
        # Test cointegration
        is_cointegrated, p_value, hedge_ratio = test_cointegration(price1, price2)
        
        # Calculate pair metrics
        pair_metrics = strategy.calculate_pair_metrics(symbol1, symbol2, data)
        
        # Combine results
        pair_info = {
            'symbol1': symbol1,
            'symbol2': symbol2,
            'p_value': p_value,
            'hedge_ratio': hedge_ratio,
            'is_cointegrated': is_cointegrated,
            'metrics': pair_metrics
        }
        
        pair_analysis.append(pair_info)
    
    # Save pair analysis
    with open(output_dir / 'pair_analysis.json', 'w') as f:
        json.dump(pair_analysis, f, indent=2, default=str)
    
    # Create a pair visualization for each pair
    for pair_info in pair_analysis:
        symbol1, symbol2 = pair_info['symbol1'], pair_info['symbol2']
        strategy.visualize_pair(symbol1, symbol2, data, save_path=str(output_dir / f'pair_{symbol1.replace("/", "_")}_{symbol2.replace("/", "_")}.png'))
    
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
    """Run live trading for the statistical arbitrage strategy."""
    # Parse pairs if provided
    pairs = parse_pairs(args.pairs)
    
    # If no pairs provided, find them automatically
    if not pairs:
        logger.info("No specific pairs provided. Finding cointegrated pairs automatically.")
        cointegrated_pairs = find_pairs(args)
        
        if cointegrated_pairs:
            pairs = [(p['symbol1'], p['symbol2']) for p in cointegrated_pairs]
        else:
            logger.warning("No cointegrated pairs found. Exiting.")
            return
    
    logger.info(f"Starting statistical arbitrage live trading with {len(pairs)} pairs")
    logger.info(f"Trading Mode: {'Paper Trading' if args.mode == 'paper' else 'Live Trading'}")
    
    # Validate API keys for exchange access
    if args.mode == 'live':
        if not config.DATA_CONFIG["api_keys"].get("binance"):
            logger.error("No API key found for Binance. Live trading requires API keys.")
            return
    
    # Initialize strategy
    strategy = StatisticalArbitrageStrategy(
        pairs=pairs,
        lookback_period=args.lookback_period,
        z_threshold=args.z_threshold,
        exit_z_threshold=args.exit_z_threshold,
        max_position_size=args.max_position_size
    )
    
    # Initialize data loader for market data updates
    data_loader = DataLoader()
    
    # Main trading loop
    try:
        while True:
            logger.info(f"Trading cycle started at {datetime.now()}")
            
            # Get all symbols from pairs
            symbols = set()
            for pair in pairs:
                symbols.add(pair[0])
                symbols.add(pair[1])
            
            # Load recent market data
            start_date = (datetime.now() - timedelta(days=args.lookback_period * 2)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            market_data = {}
            for symbol in symbols:
                try:
                    symbol_data = data_loader.load_data(
                        symbol=symbol,
                        timeframe=args.timeframe,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if symbol_data is not None and not symbol_data.empty:
                        market_data[symbol] = symbol_data
                        logger.info(f"Loaded {len(symbol_data)} data points for {symbol}")
                    else:
                        logger.warning(f"No data loaded for {symbol}")
                except Exception as e:
                    logger.error(f"Error loading data for {symbol}: {str(e)}")
            
            if len(market_data) < 2:
                logger.error("Insufficient market data. Waiting for next cycle.")
                time.sleep(args.interval)
                continue
            
            # Generate signals
            signals = strategy.generate_live_signals(market_data)
            
            if signals:
                logger.info(f"Generated {len(signals)} trading signals")
                
                # Execute trades
                for signal in signals:
                    logger.info(f"Signal: {signal}")
                    
                    if args.mode == 'live':
                        # Execute actual trades
                        pass
                    else:  # Paper trading
                        logger.info(f"Paper trade: {signal['action']} pair {signal['pair']}, ratio: {signal['hedge_ratio']:.4f}")
            else:
                logger.info("No trading signals generated")
            
            # Wait for next interval
            logger.info(f"Waiting {args.interval} seconds until next cycle")
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info("Trading stopped by user")
    except Exception as e:
        logger.error(f"Error in live trading: {str(e)}")
    
    logger.info("Live trading stopped")

def main():
    """Main entry point for the script."""
    # Parse arguments
    args = parse_args()
    
    # Run in selected mode
    if args.mode == 'scan':
        find_pairs(args)
    elif args.mode == 'backtest':
        run_backtest(args)
    else:  # live or paper
        run_live_trading(args)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
