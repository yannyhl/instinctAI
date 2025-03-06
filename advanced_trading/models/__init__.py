"""
Advanced Trading Models
----------------------
This package contains various predictive models and frameworks for financial market analysis
and trading. It includes several submodules:

1. ml_ensemble - Framework for ensembles of machine learning models with regime awareness
2. lstm - Long Short-Term Memory neural network models for time series prediction
3. volume_profile - Volume-based market structure analysis models
4. transformer - Transformer-based models for financial time series forecasting
5. statistical - Statistical models for market analysis and prediction

Each module provides specialized models for different aspects of trading and market analysis.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Type

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Check if handler already exists to avoid duplicate logging
if not logger.handlers:
    # Create console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(ch)

# Constants
MODEL_STORAGE_PATH = Path(__file__).parent / "storage"

# Ensure model storage directory exists
MODEL_STORAGE_PATH.mkdir(exist_ok=True, parents=True)

# Import submodules (will be lazy-loaded when requested)
# Each submodule should handle its own exceptions/dependencies

# Package version
__version__ = "1.13.0"

logger.info(f"Advanced Trading Models v{__version__} initialized")

# List of public modules
__all__ = [
    'ml_ensemble',
    'MODEL_STORAGE_PATH',
]

def get_model_path(model_type: str, symbol: str, timeframe: str) -> Path:
    """
    Get the path for storing or loading a model.
    
    Args:
        model_type: Type of model (e.g., 'ml_ensemble', 'lstm')
        symbol: Trading symbol (e.g., 'BTC-USDT')
        timeframe: Timeframe of the model (e.g., '1h', '1d')
        
    Returns:
        Path object for the model file
    """
    # Create subdirectory for model type if it doesn't exist
    model_dir = MODEL_STORAGE_PATH / model_type
    model_dir.mkdir(exist_ok=True)
    
    # Sanitize symbol name for filename
    symbol_safe = symbol.replace('/', '-').replace(' ', '_')
    
    # Return path with standard naming convention
    return model_dir / f"{symbol_safe}_{timeframe}.joblib"

def list_available_models() -> Dict[str, List[str]]:
    """
    List all available trained models in the model storage.
    
    Returns:
        Dictionary mapping model types to lists of available models
    """
    available_models = {}
    
    # Check if storage directory exists
    if not MODEL_STORAGE_PATH.exists():
        logger.warning("Model storage directory does not exist")
        return available_models
    
    # Scan each model type directory
    for model_dir in MODEL_STORAGE_PATH.iterdir():
        if model_dir.is_dir():
            model_type = model_dir.name
            available_models[model_type] = []
            
            # List model files in the directory
            for model_file in model_dir.glob("*.joblib"):
                available_models[model_type].append(model_file.stem)
    
    return available_models

logger.info(f"Models package initialized. Storage path: {MODEL_STORAGE_PATH}") 