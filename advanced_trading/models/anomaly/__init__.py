"""
Anomaly Detection Framework
-------------------------
A framework for detecting anomalies in financial time series data, with support for:

1. Multiple anomaly detection algorithms (Isolation Forest, One-Class SVM, Autoencoders)
2. Unsupervised and semi-supervised approaches
3. Time series specific anomaly detection
4. Ensemble methods for anomaly detection
5. Visualization tools for anomaly analysis
6. Integration with the ML Ensemble framework

This module provides tools for identifying unusual patterns, outliers, and anomalies
in financial market data that may indicate trading opportunities or risks.
"""

import logging

# Configure logging
logger = logging.getLogger(__name__)

# Version of the anomaly detection framework
__version__ = "1.0.0"

# Import main components when they are implemented
from .isolation_forest import IsolationForestDetector
from .one_class_svm import OneClassSVMDetector
from .autoencoders import AutoencoderDetector

__all__ = [
    'IsolationForestDetector',
    'OneClassSVMDetector',
    'AutoencoderDetector',
] 