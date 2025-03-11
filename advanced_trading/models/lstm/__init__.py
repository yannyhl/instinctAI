"""
LSTM Models Framework
-------------------
A framework for creating and using LSTM (Long Short-Term Memory) models
for financial time series prediction, with support for:

1. Sequence generation and preprocessing for time series data
2. Various LSTM architectures (vanilla, stacked, bidirectional, attention)
3. Ensemble methods for combining multiple LSTM models
4. Hyperparameter optimization for LSTM models
5. Integration with the ML Ensemble framework

This module provides tools for building and using LSTM models for financial
time series prediction tasks.
"""

import logging

# Configure logging
logger = logging.getLogger(__name__)

# Version of the LSTM models framework
__version__ = "1.0.0"

# Import main components when they are implemented
from .lstm_model import LSTMModel
from .sequence_generator import SequenceGenerator

__all__ = [
    'LSTMModel',
    'SequenceGenerator',
] 