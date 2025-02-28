#!/usr/bin/env python3
# Script to run a backtest with the RenaissanceInspiredStrategy in InstinctAI

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import InstinctAI modules
from trading.main import run_backtest_mode
import config
from backtesting.engine import run_strategy_backtest
from trading.strategies import RenaissanceInspiredStrategy

# Configure more verbose logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(config.LOGGING_CONFIG['file_handler']['filename']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create an args object with default values
class Args:
    def __init__(self):
        self.symbol = 'BTC'
        self.timeframe = '1h'
        self.strategy = 'renaissance'  # This will be mapped to our new strategy
        self.initial_cash = 10000.0    # Higher initial capital for more sophisticated strategy
        self.refresh_data = False      # Don't refresh by default to use existing data
        self.analyze_results = True    # Analyze the results with AI
        self.use_5year_data = True     # Use 5-year data for backtesting

def main():
    """Main function to run the backtest"""
    try:
        # First, check if 5-year data exists
        data_path = Path(config.DATA_DIR) / f"BTC_1h_5years.csv"
        
        if not data_path.exists():
            print("No 5-year historical data found. Running data fetch script first...")
            
            # Import the fetch_historical_data script and run it
            from fetch_historical_data import fetch_data
            fetch_data(['BTC'], ['1h'], force_refresh=True)
            
            # Check if data was successfully fetched
            if not data_path.exists():
                print("Failed to fetch 5-year historical data. Please check your API keys and internet connection.")
                return
        
        print("\n===========================================================")
        print("  Running InstinctAI backtest with RenaissanceInspiredStrategy")
        print("===========================================================\n")
        print("This strategy incorporates cutting-edge quantitative techniques inspired by")
        print("Renaissance Capital's approach including:")
        print("  - Multi-factor signal generation")
        print("  - Advanced statistical arbitrage")
        print("  - Machine learning-based regime detection")
        print("  - Kelly criterion position sizing")
        print("  - Dynamic strategy allocation")
        print("\nStarting backtest - check the log file for detailed progress...\n")
        
        # Add the RenaissanceInspiredStrategy to the strategy map in backtesting.engine
        from backtesting.engine import BacktestEngine
        BacktestEngine.strategy_map = {
            'renaissance': RenaissanceInspiredStrategy
        }
        
        # Extract default parameters from the strategy params class
        strategy_params = {}
        # Configure specific parameters if needed - can be customized here
        # strategy_params = {
        #    'funding_z_score_threshold': 1.8,  # Example override
        #    'kelly_fraction': 0.4             # Example override
        # }
        
        # Standard args for the main function
        args = Args()
        
        # Load data
        from trading.data_manager import DataManager
        data_manager = DataManager()
        data = data_manager.get_data_with_indicators('BTC', '1h', refresh=False, use_5year=True)
        
        if data.empty:
            print("No data available. Please check data files.")
            return
        
        # Run backtest directly with our custom parameters
        try:
            import traceback
            results = run_strategy_backtest(
                data=data,
                strategy_name='renaissance',
                params=strategy_params,
                initial_cash=args.initial_cash,
                plot=True
            )
        except Exception as e:
            print("\n==== DETAILED ERROR INFORMATION ====")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print("\nTraceback (most recent call last):")
            traceback.print_exc()
            print("\nThe error occurred in:")
            tb = traceback.extract_tb(sys.exc_info()[2])
            for frame in tb:
                print(f"  File: {frame.filename}, Line {frame.lineno}, in {frame.name}")
                print(f"    {frame.line}")
            print("\n==== END OF ERROR INFORMATION ====")
            results = {}
        
        # Print summary results
        print("\n===================== Backtest Results =====================")
        print(f"Strategy: RenaissanceInspiredStrategy")
        print(f"Initial Cash: ${args.initial_cash:.2f}")
        print(f"Final Value: ${results.get('final_value', 0):.2f}")
        print(f"Return: {results.get('return_pct', 0):.2f}%")
        print(f"Sharpe Ratio: {results.get('sharpe_ratio', 0):.4f}")
        print(f"Max Drawdown: {results.get('max_drawdown_pct', 0):.2f}%")
        print(f"Win Rate: {results.get('win_rate', 0):.2f}%")
        print(f"Total Trades: {results.get('total_trades', 0)}")
        
        # Compare against simpler strategies for reference
        print("\n=================== Performance Analysis ===================")
        print("The RenaissanceInspiredStrategy implements sophisticated")
        print("statistical techniques and risk management practices that should")
        print("lead to improved risk-adjusted returns over simpler approaches.")
        
        # If time permits, run analysis using Claude
        if args.analyze_results:
            try:
                from assistant.service import AssistantService
                assistant = AssistantService()
                insights = assistant.generate_backtest_insights(results)
                print("\n===================== AI Insights =====================")
                print(insights)
            except Exception as e:
                logger.error(f"Error getting AI insights: {e}")
        
    except Exception as e:
        logger.error(f"Error in backtest: {str(e)}", exc_info=True)
        print(f"An error occurred: {str(e)}")
        print("Check the log file for more details.")

if __name__ == "__main__":
    main() 