#!/usr/bin/env python3
"""
Debug script to pinpoint the error in RenaissanceInspiredStrategy initialization
"""

import os
import sys
import logging
import traceback
import pandas as pd
from pathlib import Path
import pdb
import inspect

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

# Custom exception hook to get detailed information
def custom_except_hook(exc_type, exc_value, exc_traceback):
    if exc_type.__name__ == 'AttributeError' and "object has no attribute 'append'" in str(exc_value):
        print("\n\n======================= DETAILED APPEND ERROR ANALYSIS =======================")
        print(f"Error found: {exc_value}")
        
        # Walk through the frames
        frames = inspect.trace()
        print(f"\nFrame analysis - {len(frames)} frames in the stack:")
        
        for i, frame_info in enumerate(frames):
            frame = frame_info[0]
            filename = frame_info[1]
            lineno = frame_info[2]
            function = frame_info[3]
            context_lines = frame_info[4]
            index = frame_info[5]
            
            print(f"\nFrame {i} - {filename}:{lineno} in {function}")
            
            # Print local variables that might be dictionaries
            local_vars = frame.f_locals
            for var_name, var_value in local_vars.items():
                if isinstance(var_value, dict):
                    print(f"  Dict '{var_name}': {type(var_value)} with {len(var_value)} items")
                elif var_name.endswith('s') and not isinstance(var_value, (str, int, float, bool)):
                    print(f"  Collection '{var_name}': {type(var_value)} with {getattr(var_value, '__len__', lambda: 'unknown')()}")
            
            # Print the problematic line and context
            if context_lines:
                print("\n  Code context:")
                for j, line in enumerate(context_lines):
                    prefix = ">>>" if j == index else "   "
                    print(f"  {prefix} {line.strip()}")
    
    # Call the default exception hook
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Install our custom exception hook
sys.excepthook = custom_except_hook

try:
    # Import our strategy and engine
    from trading.strategies import RenaissanceInspiredStrategy
    from backtesting.engine import BacktestEngine
    import config
    
    # Load the data
    print("Loading data...")
    data_path = Path('data/BTC_1h_5years.csv')
    if not data_path.exists():
        print(f"Error: Data file not found at {data_path}")
        sys.exit(1)
        
    data = pd.read_csv(data_path)
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data.set_index('timestamp', inplace=True)
    data.columns = data.columns.str.lower()  # Ensure lowercase column names
    
    print(f"Data loaded: {len(data)} rows")
    print(f"Columns: {data.columns.tolist()}")
    print(f"First few rows:\n{data.head()}")
    
    # Create backtest engine
    print("\nInitializing backtest engine...")
    engine = BacktestEngine(initial_cash=10000.0)
    
    # Add data
    print("Adding data feed...")
    engine.add_data(data)
    
    # Add strategy with debugging
    print("Adding strategy...")
    strategy_params = config.STRATEGY_PARAMS.get('renaissance', {})
    print(f"Strategy parameters: {strategy_params}")
    
    print("Adding RenaissanceInspiredStrategy...")
    engine.add_strategy(RenaissanceInspiredStrategy, strategy_params)
    
    # Run the strategy initialization (will raise the error)
    print("\nRunning backtest...")
    results = engine.run()
    print("Backtest completed successfully!")
    print(f"Results: {results}")
    
except Exception as e:
    print(f"\n======== ERROR DETECTED ========")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {str(e)}")
    print("\nDetailed Traceback:")
    traceback.print_exc()
    
    print("\nCall Stack:")
    tb = traceback.extract_tb(sys.exc_info()[2])
    for i, frame in enumerate(tb):
        print(f"{i+1}. File '{frame.filename}', line {frame.lineno}, in {frame.name}")
        print(f"   Code: {frame.line}")
    
    print("\n======== END OF ERROR INFORMATION ========")
    
    # For AppendError, check if we can find the specific line where append is called
    if "has no attribute 'append'" in str(e):
        print("\nSearching for append calls in the error path...")
        for i, frame in enumerate(tb):
            if "append" in frame.line:
                print(f"Found append call at {frame.filename}:{frame.lineno}")
                print(f"Code: {frame.line}")
                
                # Try to get more context
                try:
                    with open(frame.filename, 'r') as f:
                        lines = f.readlines()
                        start_line = max(0, frame.lineno - 5)
                        end_line = min(len(lines), frame.lineno + 5)
                        print("\nContext:")
                        for i, line in enumerate(lines[start_line:end_line], start=start_line + 1):
                            prefix = ">>> " if i == frame.lineno else "   "
                            print(f"  {prefix}{i}: {line.rstrip()}")
                except Exception as context_err:
                    print(f"Error getting context: {context_err}") 