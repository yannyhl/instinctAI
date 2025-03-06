"""
Analysis Module

This module provides tools and utilities for analyzing market data, including:
- Technical analysis: Indicators, patterns, and trend analysis
- Fundamental analysis: Financial metrics, economic indicators, and company analysis
- Market microstructure analysis: Order book analysis, liquidity metrics, and market impact

The analysis module is designed to be used by strategies, risk management, and reporting
components of the Instinct AI trading platform.
"""

from typing import Dict, List, Optional, Union, Callable, Any

# Import technical analysis components
# from .technical.indicators import get_indicator, list_available_indicators
# from .technical.patterns import detect_pattern, list_available_patterns
# from .technical.trends import detect_trend, analyze_trend_strength

# Import fundamental analysis components
# from .fundamental.financial_metrics import calculate_metric, list_available_metrics
# from .fundamental.economic_indicators import get_economic_indicator
# from .fundamental.company_analysis import analyze_company

# Import market microstructure analysis components
# from .market_microstructure.order_book import analyze_order_book, calculate_liquidity
# from .market_microstructure.market_impact import estimate_market_impact
# from .market_microstructure.high_frequency import analyze_tick_data

# Public API
__all__ = [
    # Technical analysis
    # 'get_indicator', 'list_available_indicators',
    # 'detect_pattern', 'list_available_patterns',
    # 'detect_trend', 'analyze_trend_strength',
    
    # Fundamental analysis
    # 'calculate_metric', 'list_available_metrics',
    # 'get_economic_indicator', 'analyze_company',
    
    # Market microstructure analysis
    # 'analyze_order_book', 'calculate_liquidity',
    # 'estimate_market_impact', 'analyze_tick_data',
]

# Version information
__version__ = '0.1.0' 