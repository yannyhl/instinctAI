"""
Volume Profile Module for Instinct AI Trading Platform.

This module provides tools for analyzing volume profiles, liquidity, and order flow
in financial markets. These components are essential for understanding market microstructure
and can be used for trading signal generation, execution optimization, and risk management.

Components:
- VolumeProfile: Tools for analyzing volume distribution across price levels
- LiquidityModel: Models for estimating market liquidity and impact
- VPIN: Volume-synchronized Probability of Informed Trading implementation
"""

from .volume_profile import VolumeProfile
from .liquidity_model import LiquidityModel, LiquidityMetrics
from .vpin import VPIN, VPINCalculator

__all__ = [
    'VolumeProfile',
    'LiquidityModel',
    'LiquidityMetrics',
    'VPIN',
    'VPINCalculator',
] 