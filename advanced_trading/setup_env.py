#!/usr/bin/env python
"""
Setup environment variables for advanced trading system
"""
import os
import sys
from pathlib import Path
import dotenv
import shutil

# Find and load the .env file from parent directory
parent_dir = Path(__file__).resolve().parent.parent
env_file = parent_dir / ".env"

if env_file.exists():
    print(f"Loading environment variables from {env_file}")
    dotenv.load_dotenv(env_file)
    
    # Copy relevant API keys to config
    api_keys = {
        "binance": os.environ.get("BINANCE_API_KEY", ""),
        "binance_secret": os.environ.get("BINANCE_SECRET_KEY", ""),
        "coinbase": os.environ.get("COINBASE_API_KEY", ""),
        "coinbase_secret": os.environ.get("COINBASE_SECRET_KEY", ""),
        "kraken": os.environ.get("KRAKEN_API_KEY", ""),
        "kraken_secret": os.environ.get("KRAKEN_SECRET_KEY", "")
    }
    
    print("API keys loaded successfully")
    
    # Update the config.py file with these keys
    config_file = Path(__file__).resolve().parent / "config.py"
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            config_content = f.read()
        
        # Find the api_keys section and replace it
        if "api_keys" in config_content:
            print("Updating API keys in config.py")
            # Simple string replacement for demo purposes
            for key, value in api_keys.items():
                if value:
                    replace_str = f'"{key}": os.environ.get("{key.upper()}", "")'
                    new_str = f'"{key}": "{value}"'
                    config_content = config_content.replace(replace_str, new_str)
            
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            print("Config updated successfully")
else:
    print(f"Error: .env file not found at {env_file}")
    sys.exit(1)

print("Environment setup complete")
