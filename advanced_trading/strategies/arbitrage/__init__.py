"""
Arbitrage Strategies

This module contains strategies that exploit price differences between markets,
instruments, or exchanges to generate profit with minimal risk.

Strategies in this module:
- Funding Arbitrage: Exploits funding rate differentials in perpetual futures
- Statistical Arbitrage: Exploits mean-reverting relationships between correlated assets
"""

from typing import Dict, List, Optional, Union, Any

# Import arbitrage strategy implementations
from .statistical_arbitrage import StatisticalArbitrage
from .funding_arbitrage import FundingArbitrage
from .cross_exchange_arbitrage import CrossExchangeArbitrage
from .triangular_arbitrage import TriangularArbitrage
from .index_arbitrage import IndexArbitrage

# Public API
__all__ = [
    'FundingArbitrageStrategy',
    'StatisticalArbitrageStrategy',
] 