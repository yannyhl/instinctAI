#!/usr/bin/env python3
"""
Command Line Interface for the Trading Assistant

This script launches the interactive trading assistant that provides
guidance and automation for the Advanced Trading System.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import the assistant
from assistant.trading_assistant import TradingAssistant

def main():
    """Launch the trading assistant."""
    print("Initializing Advanced Trading Assistant...")
    
    # Create the assistant instance
    assistant = TradingAssistant()
    
    # Run the assistant
    try:
        assistant.run()
    except KeyboardInterrupt:
        print("\nAssistant terminated by user.")
        return 0
    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 