"""
Statistical Strategies

This module contains trading strategies based on statistical methods and analysis,
including mean reversion, momentum, and pattern recognition approaches.

Strategies in this module:
- Volume Profile Strategy: Analyzes volume distribution for price levels of interest
- Advanced Crypto Strategy: Combines multiple statistical indicators for crypto trading
"""

from typing import Dict, List, Optional, Union, Any

# Import statistical strategy implementations
from .mean_reversion_strategy import MeanReversionStrategy
from .trend_following_strategy import TrendFollowingStrategy
from .volatility_strategy import VolatilityStrategy
from .momentum_strategy import MomentumStrategy
from .breakout_strategy import BreakoutStrategy

# Public API
__all__ = [
    'VolumeProfileStrategy',
    'AdvancedCryptoStrategy',
] 