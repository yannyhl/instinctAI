"""
ML Ensemble Framework
--------------------
A framework for creating and managing ensembles of machine learning models
for financial market prediction, with support for:

1. Model ensemble management with various combining methods
2. Regime-specific model selection and weighting
3. Feature importance analysis and visualization
4. Dynamic weight adjustment based on recent performance

This module provides tools for combining multiple models to improve prediction
accuracy and robustness in different market conditions.
"""

import logging

from .ensemble_manager import EnsembleManager

# Configure logging
logger = logging.getLogger(__name__)

# Version of the ML ensemble framework
__version__ = "1.0.0"

__all__ = [
    'EnsembleManager',
] 