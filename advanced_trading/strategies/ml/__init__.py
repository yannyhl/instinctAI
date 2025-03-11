"""
Machine Learning Strategies

This module contains trading strategies that utilize machine learning techniques,
including deep learning, reinforcement learning, and other ML approaches.

Strategies in this module:
- LSTM Strategy: Uses Long Short-Term Memory networks for price prediction
- ML Strategy: Generic machine learning-based strategy with customizable models
"""

from typing import Dict, List, Optional, Union, Any

# Import machine learning strategy implementations
from .lstm_strategy import LSTMStrategy
from .reinforcement_learning_strategy import ReinforcementLearningStrategy
from .ensemble_strategy import EnsembleStrategy
from .gradient_boosting_strategy import GradientBoostingStrategy
from .deep_learning_strategy import DeepLearningStrategy

# Public API
__all__ = [
    'LSTMStrategy',
    'MLStrategy',
] 