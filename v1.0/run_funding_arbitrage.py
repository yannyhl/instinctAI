#!/usr/bin/env python

"""
Funding Rate Arbitrage Strategy Runner
------------------------------------
Script to run the funding rate arbitrage strategy for capturing funding rate differentials
across exchanges.
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

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import project modules
import config
from strategies.funding_arbitrage import FundingRateArbitrage
from data.data_loader import DataLoader
from utils.performance import calculate_performance_metrics, create_tear_sheet

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'logs', f'funding_arb_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run Funding Rate Arbitrage Strategy')
    
    parser.add_argument('--mode', type=str, default='backtest',
                      choices=['backtest', 'live', 'paper'],
                      help='Trading mode')
    
    parser.add_argument('--symbols', type=str, nargs='+',
                      default=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                      help='Trading pairs to analyze')
    
    parser.add_argument('--start_date', type=str, default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                      help='Start date for data (YYYY-MM-DD)')
    
    parser.add_argument('--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                      help='End date for data (YYYY-MM-DD)')
    
    parser.add_argument('--capital', type=float, default=10000.0,
                      help='Initial capital')
    
    parser.add_argument('--min_funding_rate', type=float, default=0.01,
                      help='Minimum funding rate differential to consider (as decimal)')
    
    parser.add_argument('--max_position_size', type=float, default=0.2,
                      help='Maximum position size as fraction of capital')
    
    parser.add_argument('--exchanges', type=str, nargs='+',
                      default=['binance', 'ftx', 'bybit'],
                      help='Exchanges to consider')
    
    parser.add_argument('--interval', type=int, default=3600,
                      help='Interval for live trading execution in seconds')
    
    parser.add_argument('--output_dir', type=str, default=None,
                      help='Directory to save results')
    
    return parser.parse_args()

def run_backtest(args):
    """Run backtest for the funding rate arbitrage strategy."""
    logger.info(f"Starting funding rate arbitrage backtest with symbols: {args.symbols}")
    
    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(script_dir) / 'results' / f'funding_arb_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load market data
    data_loader = DataLoader()
    
    # Load data for each symbol
    data = {}
    for symbol in args.symbols:
        try:
            symbol_data = data_loader.load_data(
                symbol=symbol,
                timeframe='1h',  # Hourly data for funding rate analysis
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
    
    if not data:
        logger.error("No market data loaded. Exiting.")
        return
    
    # Load funding rate data
    funding_data = {}
    for symbol in args.symbols:
        try:
            # Here we'd have a method to load historical funding rates
            # For now, we'll simulate it with random data
            funding_data[symbol] = _simulate_funding_rates(
                data[symbol].index, args.exchanges
            )
            logger.info(f"Loaded funding rate data for {symbol}")
        except Exception as e:
            logger.error(f"Error loading funding rates for {symbol}: {str(e)}")
    
    if not funding_data:
        logger.error("No funding rate data loaded. Exiting.")
        return
    
    # Initialize strategy
    strategy = FundingRateArbitrage(
        symbols=args.symbols,
        min_funding_rate=args.min_funding_rate,
        max_position_size=args.max_position_size,
        exchanges=args.exchanges
    )
    
    # Run backtest
    logger.info("Running backtest...")
    results = strategy.backtest(
        price_data=data,
        funding_data=funding_data,
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
    """Run live trading for the funding rate arbitrage strategy."""
    logger.info(f"Starting funding rate arbitrage live trading with symbols: {args.symbols}")
    logger.info(f"Trading Mode: {'Paper Trading' if args.mode == 'paper' else 'Live Trading'}")
    
    # Validate API keys for exchange access
    if args.mode == 'live':
        for exchange in args.exchanges:
            if not config.DATA_CONFIG["api_keys"].get(exchange):
                logger.error(f"No API key found for {exchange}. Live trading requires API keys.")
                return
    
    # Initialize strategy
    strategy = FundingRateArbitrage(
        symbols=args.symbols,
        min_funding_rate=args.min_funding_rate,
        max_position_size=args.max_position_size,
        exchanges=args.exchanges
    )
    
    # Initialize exchange connections
    # This would be a separate module in a real implementation
    
    # Main trading loop
    try:
        while True:
            logger.info(f"Trading cycle started at {datetime.now()}")
            
            # Fetch current funding rates
            funding_rates = _fetch_current_funding_rates(args.symbols, args.exchanges)
            
            # Generate signals
            signals = strategy.generate_signals(funding_rates)
            
            if signals:
                logger.info(f"Generated {len(signals)} trading signals")
                
                # Execute trades
                for signal in signals:
                    logger.info(f"Signal: {signal}")
                    
                    if args.mode == 'live':
                        # Execute actual trades
                        pass
                    else:  # Paper trading
                        logger.info(f"Paper trade: {signal['action']} {signal['symbol']} on {signal['exchange']}")
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

def _simulate_funding_rates(dates, exchanges):
    """
    Simulate historical funding rates for testing.
    
    Args:
        dates: DatetimeIndex of dates
        exchanges: List of exchange names
        
    Returns:
        DataFrame with simulated funding rates
    """
    np.random.seed(42)  # For reproducibility
    
    # Create a DataFrame with dates as index
    funding_df = pd.DataFrame(index=dates)
    
    # Add funding rates for each exchange
    for exchange in exchanges:
        # Base funding rate between -0.01% and 0.03%
        base_rate = np.random.uniform(-0.0001, 0.0003)
        
        # Add some randomness and trends
        rates = np.random.normal(base_rate, 0.0002, size=len(dates))
        
        # Add trend - higher during bull market (sim)
        trend = np.linspace(0, 0.0002, len(dates))
        rates += trend
        
        # Add to DataFrame
        funding_df[exchange] = rates
    
    return funding_df

def _fetch_current_funding_rates(symbols, exchanges):
    """
    Fetch current funding rates from exchanges.
    
    Args:
        symbols: List of trading pairs
        exchanges: List of exchanges
        
    Returns:
        Dictionary of funding rates by symbol and exchange
    """
    # This would connect to exchange APIs in a real implementation
    # For now, we simulate with random data
    
    funding_rates = {}
    
    for symbol in symbols:
        funding_rates[symbol] = {}
        for exchange in exchanges:
            # Simulate a funding rate between -0.01% and 0.04%
            funding_rates[symbol][exchange] = np.random.uniform(-0.0001, 0.0004)
    
    return funding_rates

def main():
    """Main entry point for the script."""
    # Parse arguments
    args = parse_args()
    
    # Run in selected mode
    if args.mode == 'backtest':
        run_backtest(args)
    else:  # live or paper
        run_live_trading(args)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
