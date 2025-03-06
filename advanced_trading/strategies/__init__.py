"""
Strategies Module

This module provides trading strategies for the Instinct AI trading platform, including:
- Arbitrage strategies: Statistical arbitrage, funding arbitrage, and cross-exchange arbitrage
- Machine learning strategies: LSTM, reinforcement learning, and other ML-based approaches
- Statistical strategies: Mean reversion, trend following, and other statistical approaches
- Factory: Strategy creation and management utilities

The strategies module is designed to provide a framework for developing, testing, and
deploying trading strategies on the Instinct AI platform.
"""

from typing import Dict, List, Optional, Union, Callable, Any, Type

# Import base strategy components
from .base import Strategy, StrategyConfig, StrategyResult, StrategyState

# Import arbitrage strategies
from .arbitrage import (
    StatisticalArbitrage, FundingArbitrage, CrossExchangeArbitrage,
    TriangularArbitrage, IndexArbitrage
)

# Import machine learning strategies
from .ml import (
    LSTMStrategy, ReinforcementLearningStrategy, EnsembleStrategy,
    GradientBoostingStrategy, DeepLearningStrategy
)

# Import statistical strategies
from .statistical import (
    MeanReversionStrategy, TrendFollowingStrategy, VolatilityStrategy,
    MomentumStrategy, BreakoutStrategy
)

# Import strategy factory
from .factory import (
    create_strategy, register_strategy, get_strategy_class,
    list_available_strategies, strategy_metadata
)

# Public API
__all__ = [
    # Base strategy components
    'Strategy', 'StrategyConfig', 'StrategyResult', 'StrategyState',
    
    # Arbitrage strategies
    'StatisticalArbitrage', 'FundingArbitrage', 'CrossExchangeArbitrage',
    'TriangularArbitrage', 'IndexArbitrage',
    
    # Machine learning strategies
    'LSTMStrategy', 'ReinforcementLearningStrategy', 'EnsembleStrategy',
    'GradientBoostingStrategy', 'DeepLearningStrategy',
    
    # Statistical strategies
    'MeanReversionStrategy', 'TrendFollowingStrategy', 'VolatilityStrategy',
    'MomentumStrategy', 'BreakoutStrategy',
    
    # Strategy factory
    'create_strategy', 'register_strategy', 'get_strategy_class',
    'list_available_strategies', 'strategy_metadata',
]

# Version information
__version__ = '0.1.0' 