"""
Helpers Module
------------
Provides utility functions for InstinctAI
"""

import json
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import numpy as np
import pandas as pd

import config

def timestamp_to_datetime(timestamp):
    """Convert Unix timestamp to datetime"""
    return datetime.fromtimestamp(timestamp)

def datetime_to_timestamp(dt):
    """Convert datetime to Unix timestamp"""
    return int(dt.timestamp())

def round_price(price, tick_size=0.01):
    """Round price to nearest tick size"""
    return round(price / tick_size) * tick_size

def calculate_position_size(account_size, risk_percent, stop_distance):
    """
    Calculate position size based on risk parameters
    
    Args:
        account_size: Total account size
        risk_percent: Percentage of account to risk (e.g., 0.02 for 2%)
        stop_distance: Distance to stop loss in price units
        
    Returns:
        Position size
    """
    if stop_distance <= 0:
        return 0
    
    risk_amount = account_size * risk_percent
    position_size = risk_amount / stop_distance
    
    return position_size

def load_json(filepath):
    """Load data from JSON file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON file {filepath}: {e}")
        return None

def save_json(data, filepath):
    """Save data to JSON file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=json_serial)
        return True
    except Exception as e:
        print(f"Error saving JSON file {filepath}: {e}")
        return False

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, np.datetime64)):
        return obj.isoformat()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"