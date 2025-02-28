"""
Main Trading Module
----------------
Entry point for the InstinctAI trading system
"""

import os
import sys
import logging
import argparse
import threading
import time
from datetime import datetime
import signal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from trading.data_manager import DataManager
from trading.exchange import HyperliquidExchange
from trading.strategies import FundingRateMomentumStrategy
from assistant.service import AssistantService
from assistant.api import start_assistant_api
from backtesting.engine import run_strategy_backtest

# Configure logging
logging.basicConfig(
    level=config.LOGGING_CONFIG['level'],
    format=config.LOGGING_CONFIG['format'],
    handlers=[
        logging.FileHandler(config.LOGGING_CONFIG['file_handler']['filename']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global flags
running = True

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    global running
    logger.info("Shutting down InstinctAI...")
    running = False

def start_assistant_service():
    """Start the assistant service in a separate thread"""
    try:
        logger.info("Starting InstinctAI Assistant API...")
        start_assistant_api()
    except Exception as e:
        logger.error(f"Error starting assistant service: {str(e)}")

def run_backtest_mode(args):
    """Run in backtest mode"""
    try:
        logger.info("Starting InstinctAI in backtest mode...")
        
        # Initialize data manager
        data_manager = DataManager()
        
        # Get data
        symbol = args.symbol or config.TRADING_CONFIG['default_symbol']
        timeframe = args.timeframe or config.TRADING_CONFIG['default_timeframe']
        
        # Check if we should use 5-year data
        use_5year = getattr(args, 'use_5year_data', False)
        if use_5year:
            logger.info(f"Loading 5 years of market data for {symbol} {timeframe}...")
        else:
            logger.info(f"Loading market data for {symbol} {timeframe}...")
        
        data = data_manager.get_data_with_indicators(symbol, timeframe, refresh=args.refresh_data, use_5year=use_5year)
        
        if data.empty:
            logger.error(f"No data available for {symbol} {timeframe}")
            return
        
        # Get strategy name and parameters
        strategy_name = args.strategy or 'funding_momentum'
        
        # Run backtest
        logger.info(f"Running backtest for {strategy_name} strategy...")
        
        results = run_strategy_backtest(
            data=data,
            strategy_name=strategy_name,
            initial_cash=args.initial_cash,
            plot=True
        )
        
        # Print summary
        print("\n== Backtest Results ==")
        print(f"Strategy: {strategy_name}")
        print(f"Symbol: {symbol} ({timeframe})")
        print(f"Initial Cash: ${args.initial_cash:.2f}")
        print(f"Final Value: ${results.get('final_value', 0):.2f}")
        print(f"Return: {results.get('return_pct', 0):.2f}%")
        print(f"Sharpe Ratio: {results.get('sharpe_ratio', 0):.4f}")
        print(f"Max Drawdown: {results.get('max_drawdown_pct', 0):.2f}%")
        print(f"Win Rate: {results.get('win_rate', 0):.2f}%")
        print(f"Total Trades: {results.get('total_trades', 0)}")
        
        # Get AI insights if requested
        if args.analyze_results:
            print("\nGetting AI insights...")
            try:
                assistant = AssistantService()
                insights = assistant.generate_backtest_insights(results)
                print("\n== AI Insights ==")
                print(insights)
                
                suggestions = assistant.suggest_strategy_improvements(strategy_name, results)
                print("\n== Strategy Improvement Suggestions ==")
                print(suggestions)
            except Exception as e:
                logger.error(f"Error getting AI insights: {str(e)}")
                print("Error getting AI insights. Check logs for details.")
        
    except Exception as e:
        logger.error(f"Error in backtest mode: {str(e)}")

def run_paper_trading_mode(args):
    """Run in paper trading mode"""
    try:
        logger.info("Starting InstinctAI in paper trading mode...")
        
        # Initialize components
        exchange = HyperliquidExchange()
        data_manager = DataManager()
        
        # Get initial data
        symbol = args.symbol or config.TRADING_CONFIG['default_symbol']
        timeframe = args.timeframe or config.TRADING_CONFIG['default_timeframe']
        
        logger.info(f"Loading initial market data for {symbol} {timeframe}...")
        data = data_manager.get_data_with_indicators(symbol, timeframe, refresh=True)
        
        if data.empty:
            logger.error(f"No data available for {symbol} {timeframe}")
            return
        
        # Trading state
        position = None
        orders = []
        last_analysis_time = None
        analysis_interval = args.analysis_interval  # in seconds
        
        # Start main trading loop
        while running:
            current_time = datetime.now()
            
            # Refresh market data periodically
            if last_analysis_time is None or (current_time - last_analysis_time).total_seconds() >= analysis_interval:
                logger.info(f"Refreshing market data for {symbol}...")
                data = data_manager.get_data_with_indicators(symbol, timeframe, refresh=True)
                
                # Get current market conditions
                market_data = {
                    'symbol': symbol,
                    'current_price': data['close'].iloc[-1],
                    'rsi': data['rsi'].iloc[-1] if 'rsi' in data.columns else None,
                    'funding_rate': exchange.get_funding_rates(symbol),
                    'timestamp': current_time.isoformat()
                }
                
                # Get liquidity analysis
                liquidity = data_manager.get_market_liquidity(symbol)
                market_data.update({
                    'bid_liquidity': liquidity.get('bid_liquidity', 0),
                    'ask_liquidity': liquidity.get('ask_liquidity', 0),
                    'imbalance': liquidity.get('imbalance', 0)
                })
                
                # Log market conditions
                logger.info(f"Market conditions for {symbol}: Price: {market_data['current_price']}, "
                          f"RSI: {market_data['rsi']}, Funding Rate: {market_data['funding_rate']}")
                
                # Update timestamp
                last_analysis_time = current_time
                
                # TODO: Implement trading logic based on strategy
                # For now, just log the current state
                
                # Get AI analysis if requested
                if args.use_assistant:
                    try:
                        assistant = AssistantService()
                        analysis = assistant.analyze_market_conditions(data.tail(24))
                        logger.info(f"AI Market Analysis:\n{analysis}")
                    except Exception as e:
                        logger.error(f"Error getting AI analysis: {str(e)}")
            
            # Sleep to avoid excessive API calls
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in paper trading mode: {str(e)}")

def run_live_trading_mode(args):
    """Run in live trading mode (with real funds)"""
    try:
        logger.warning("Starting InstinctAI in LIVE TRADING mode with REAL FUNDS...")
        
        # Confirmation prompt
        confirm = input("WARNING: You are about to start trading with REAL FUNDS. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Live trading canceled by user")
            return
        
        # Set live trading flag to true
        config.TRADING_CONFIG['live_trading_enabled'] = True
        
        # Run the same logic as paper trading
        run_paper_trading_mode(args)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in live trading mode: {str(e)}")

def run_assistant_mode(args):
    """Run only the assistant service"""
    try:
        logger.info("Starting InstinctAI Assistant service...")
        
        # Start assistant service
        assistant_thread = threading.Thread(target=start_assistant_service)
        assistant_thread.daemon = True
        assistant_thread.start()
        
        logger.info("Assistant service started. Press Ctrl+C to exit.")
        
        # Keep main thread alive
        while running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in assistant mode: {str(e)}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='InstinctAI Quantitative Trading System')
    
    # Global arguments
    parser.add_argument('--mode', choices=['backtest', 'paper', 'live', 'assistant'], 
                      default='backtest', help='Operation mode')
    parser.add_argument('--symbol', type=str, help='Trading symbol (e.g., BTC)')
    parser.add_argument('--timeframe', type=str, help='Data timeframe (e.g., 1h, 4h, 1d)')
    
    # Backtest mode arguments
    parser.add_argument('--strategy', type=str, help='Strategy to use')
    parser.add_argument('--initial-cash', type=float, default=2000.0, 
                      help='Initial cash for backtesting')
    parser.add_argument('--refresh-data', action='store_true', 
                      help='Force refresh of market data')
    parser.add_argument('--analyze-results', action='store_true', 
                      help='Get AI analysis of backtest results')
    
    # Trading mode arguments
    parser.add_argument('--use-assistant', action='store_true', 
                      help='Use AI assistant for market analysis')
    parser.add_argument('--analysis-interval', type=int, default=300, 
                      help='Interval between market analyses (seconds)')
    
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run in the specified mode
        if args.mode == 'backtest':
            run_backtest_mode(args)
        elif args.mode == 'paper':
            run_paper_trading_mode(args)
        elif args.mode == 'live':
            run_live_trading_mode(args)
        elif args.mode == 'assistant':
            run_assistant_mode(args)
        else:
            logger.error(f"Unknown mode: {args.mode}")
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    main()