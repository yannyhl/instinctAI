"""
ML Ensemble Framework
--------------------
A framework for creating and managing ensembles of machine learning models
for financial market prediction, with support for:

1. Model ensemble management with various combining methods
2. Regime-specific model selection and weighting
3. Feature importance analysis and visualization
4. Dynamic weight adjustment based on recent performance
5. Feature selection with regime awareness
6. Model evaluation with financial-specific metrics and visualizations
7. Model calibration for well-calibrated probability estimates
8. Meta-labeling for improved trading signal generation
9. Model persistence with versioning and metadata tracking

This module provides tools for combining multiple models to improve prediction
accuracy and robustness in different market conditions.
"""

import logging

from .ensemble_manager import EnsembleManager
from .model_factory import ModelFactory
from .feature_selection import (
    FeatureSelector, 
    select_features, 
    get_feature_importance
)
from .model_evaluation import (
    ModelEvaluator,
    evaluate_classification_model,
    evaluate_regression_model
)
from .calibration import (
    ModelCalibrator,
    calibrate_probabilities,
    evaluate_calibration
)
from .meta_labeler import (
    MetaLabeler,
    apply_meta_labeling,
    evaluate_meta_labeling,
    optimize_meta_labeling_threshold
)
from .model_persistence import (
    ModelPersistence,
    ModelRegistry,
    save_model,
    load_model,
    register_model,
    list_models,
    get_model_versions
)

# Configure logging
logger = logging.getLogger(__name__)

# Version of the ML ensemble framework
__version__ = "1.0.0"

__all__ = [
    'EnsembleManager',
    'ModelFactory',
    'FeatureSelector',
    'select_features',
    'get_feature_importance',
    'ModelEvaluator',
    'evaluate_classification_model',
    'evaluate_regression_model',
    'ModelCalibrator',
    'calibrate_probabilities',
    'evaluate_calibration',
    'MetaLabeler',
    'apply_meta_labeling',
    'evaluate_meta_labeling',
    'optimize_meta_labeling_threshold',
    'ModelPersistence',
    'ModelRegistry',
    'save_model',
    'load_model',
    'register_model',
    'list_models',
    'get_model_versions',
] 