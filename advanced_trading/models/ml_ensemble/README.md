# ML Ensemble Framework

A comprehensive framework for creating and managing ensembles of machine learning models for financial market prediction.

## Overview

The ML Ensemble framework provides tools for combining multiple models to improve prediction accuracy and robustness in different market conditions. It includes support for:

1. **Model ensemble management** with various combining methods
2. **Regime-specific model selection and weighting**
3. **Feature importance analysis and visualization**
4. **Dynamic weight adjustment** based on recent performance
5. **Feature selection** with regime awareness
6. **Model evaluation** with financial-specific metrics and visualizations
7. **Model calibration** for well-calibrated probability estimates
8. **Meta-labeling** for improved trading signal generation
9. **Model persistence** with versioning and metadata tracking

## Components

### EnsembleManager

The `EnsembleManager` class is the core of the ML Ensemble framework. It manages a collection of base models and provides methods for training, prediction, and performance evaluation.

```python
from advanced_trading.models.ml_ensemble import EnsembleManager

# Create an ensemble manager
ensemble = EnsembleManager(
    base_models=models,
    ensemble_method='weighted_avg',
    model_type='classification',
    regime_aware=True,
    feature_names=feature_names
)

# Train the ensemble
ensemble.fit(X_train, y_train, regimes=regimes_train)

# Make predictions
predictions = ensemble.predict(X_test, current_regime=current_regime)
probabilities = ensemble.predict_proba(X_test, current_regime=current_regime)
```

### ModelFactory

The `ModelFactory` class provides methods for creating various types of models and ensembles.

```python
from advanced_trading.models.ml_ensemble import ModelFactory

# Create a model factory
factory = ModelFactory()

# Create a set of base models for an ensemble
base_models = factory.create_quick_ensemble_set(prediction_type='classification')

# Create a specific model
model = factory.create_model('random_forest', prediction_type='classification')
```

### FeatureSelector

The `FeatureSelector` class provides methods for selecting relevant features for machine learning models.

```python
from advanced_trading.models.ml_ensemble import FeatureSelector

# Create a feature selector
selector = FeatureSelector(
    method='recursive',
    model_type='classification',
    regime_aware=True
)

# Select features
selected_features = selector.select(
    X=X_train,
    y=y_train,
    regimes=regimes_train,
    n_features=10
)

# Get feature importance
importance = selector.get_feature_importance()
```

### ModelEvaluator

The `ModelEvaluator` class provides methods for evaluating machine learning models with financial-specific metrics.

```python
from advanced_trading.models.ml_ensemble import ModelEvaluator

# Create a model evaluator
evaluator = ModelEvaluator(
    model_type='classification',
    regime_aware=True
)

# Evaluate a model
evaluator.evaluate(
    y_true=y_test,
    y_pred=y_pred,
    y_prob=y_prob,
    regimes=regimes_test,
    evaluation_name='model_name'
)

# Compare multiple models
comparison = evaluator.compare_models(
    model_names=['model1', 'model2', 'model3'],
    metric_name='accuracy'
)

# Visualize model performance
evaluator.visualize_confusion_matrix(evaluation_name='model_name')
evaluator.visualize_roc_curve(y_true=y_test, y_prob=y_prob)
evaluator.visualize_precision_recall_curve(y_true=y_test, y_prob=y_prob)
evaluator.visualize_regression_performance(y_true=y_test, y_pred=y_pred)
evaluator.visualize_metric_by_regime(evaluation_name='model_name', metric_name='accuracy')
evaluator.visualize_model_comparison(
    model_names=['model1', 'model2', 'model3'],
    metric_names=['accuracy', 'precision', 'recall', 'f1']
)
```

### ModelCalibrator

The `ModelCalibrator` class provides methods for calibrating machine learning models to ensure their probability estimates are well-calibrated.

```python
from advanced_trading.models.ml_ensemble import ModelCalibrator

# Create a model calibrator
calibrator = ModelCalibrator(
    method='platt',  # Options: 'platt', 'isotonic', 'beta', 'ensemble'
    regime_aware=True
)

# Fit calibrator
calibrator.fit(
    y_true=y_train,
    y_prob=y_prob_train,
    regimes=regimes_train
)

# Calibrate probabilities
calibrated_probs = calibrator.calibrate(
    y_prob=y_prob_test,
    regime='trend'  # Optional: specify regime for regime-specific calibration
)

# Visualize calibration curve
calibrator.visualize_calibration_curve(
    y_true=y_test,
    y_prob=y_prob_test,
    y_prob_calibrated=calibrated_probs,
    title='Calibration Curve'
)

# Visualize reliability diagram
calibrator.visualize_reliability_diagram(
    y_true=y_test,
    y_prob=y_prob_test,
    y_prob_calibrated=calibrated_probs,
    title='Reliability Diagram'
)

# Compare calibration across regimes
calibrator.visualize_calibration_comparison(
    regimes=['trend', 'cycle', 'volatility', 'global'],
    metric='ece'  # Options: 'ece', 'mce', 'brier_score', 'log_loss'
)
```

### MetaLabeler

The `MetaLabeler` class provides methods for implementing meta-labeling strategies to improve trading signal generation.

```python
from advanced_trading.models.ml_ensemble import MetaLabeler

# Create a meta-labeler
meta_labeler = MetaLabeler(
    primary_model=primary_model,  # Optional: primary model for direction prediction
    meta_model=meta_model,  # Optional: meta-model for filtering predictions
    threshold=0.5,  # Probability threshold for meta-model
    regime_aware=True  # Whether to use regime-specific meta-labeling
)

# Fit meta-labeler
meta_labeler.fit(
    X=X_train,
    y=y_train,
    primary_predictions=primary_pred_train,  # Optional: if primary_model is not provided
    regimes=regimes_train,  # Optional: for regime-specific meta-labeling
    meta_features=meta_features_train  # Optional: additional features for meta-model
)

# Generate meta-labeled predictions
meta_predictions = meta_labeler.predict(
    X=X_test,
    primary_predictions=primary_pred_test,  # Optional: if primary_model is not provided
    regime='trend',  # Optional: specify regime for regime-specific meta-labeling
    meta_features=meta_features_test  # Optional: additional features for meta-model
)

# Evaluate meta-labeling
metrics = meta_labeler.evaluate(
    X=X_test,
    y=y_test,
    primary_predictions=primary_pred_test,
    regimes=regimes_test,
    meta_features=meta_features_test
)

# Visualize meta-labeling performance
meta_labeler.visualize_meta_model_performance()
meta_labeler.visualize_trade_filtering(
    X=X_test,
    y=y_test,
    primary_predictions=primary_pred_test,
    meta_features=meta_features_test
)

# Visualize threshold impact
meta_labeler.visualize_threshold_impact(
    X=X_test,
    y=y_test,
    primary_predictions=primary_pred_test,
    meta_features=meta_features_test,
    thresholds=[0.1, 0.3, 0.5, 0.7, 0.9]
)

# Compare regimes
meta_labeler.visualize_regime_comparison(
    regimes=['trend', 'cycle', 'volatility', 'global'],
    metric='precision'  # Options: 'precision', 'recall', 'f1', 'trades', 'trade_reduction', 'precision_improvement'
)
```

### ModelPersistence

The `ModelPersistence` class provides methods for saving and loading trained models with metadata.

```python
from advanced_trading.models.ml_ensemble import ModelPersistence

# Create a model persistence instance
persistence = ModelPersistence(base_dir='./models')

# Save a model with metadata
version_dir = persistence.save_model(
    model=trained_model,
    model_name='my_classifier',
    metadata={
        'description': 'Random Forest classifier for market prediction',
        'performance': {
            'accuracy': 0.85,
            'f1': 0.83,
            'precision': 0.82,
            'recall': 0.84
        },
        'features': feature_names
    }
)

# Load a model
loaded_model = persistence.load_model(
    model_name='my_classifier',
    version='latest'  # or specific version
)

# Load a model with metadata
loaded_model, metadata = persistence.load_model(
    model_name='my_classifier',
    version='latest',
    with_metadata=True
)

# Get all versions of a model
versions = persistence.get_model_versions('my_classifier')

# Get metadata for a model version
metadata = persistence.get_model_metadata(
    model_name='my_classifier',
    version='latest'
)

# Delete a model or specific version
persistence.delete_model(
    model_name='my_classifier',
    version=None  # None deletes all versions
)
```

### ModelRegistry

The `ModelRegistry` class provides methods for managing a collection of models, including registration, retrieval, and tracking model performance.

```python
from advanced_trading.models.ml_ensemble import ModelRegistry

# Create a model registry instance
registry = ModelRegistry(base_dir='./models')

# Register a model with metadata and tags
version = registry.register_model(
    model=trained_model,
    model_name='market_predictor',
    metadata={
        'description': 'Model for predicting market direction',
        'performance': {
            'accuracy': 0.85,
            'f1': 0.83
        }
    },
    tags=['classification', 'market_direction', 'daily']
)

# Get a model from the registry
model = registry.get_model(
    model_name='market_predictor',
    version='latest'  # or specific version
)

# List all models in the registry
models_df = registry.list_models()

# List models with specific tags
tagged_models = registry.list_models(tags=['classification', 'daily'])

# Get all versions of a model
versions_df = registry.get_model_versions('market_predictor')

# Update performance metrics for a model version
registry.update_model_performance(
    model_name='market_predictor',
    version=version,
    performance={
        'accuracy': 0.86,
        'custom_metric': 0.95
    }
)

# Delete a model or specific version
registry.delete_model(
    model_name='market_predictor',
    version=None  # None deletes all versions
)
```

## Convenience Functions

The ML Ensemble framework also provides convenience functions for common tasks:

### Feature Selection

```python
from advanced_trading.models.ml_ensemble import select_features, get_feature_importance

# Select features
selected_features = select_features(
    X=X_train,
    y=y_train,
    method='recursive',
    model_type='classification',
    n_features=10
)

# Get feature importance
importance = get_feature_importance(
    X=X_train,
    y=y_train,
    method='permutation',
    model_type='classification'
)
```

### Model Evaluation

```python
from advanced_trading.models.ml_ensemble import evaluate_classification_model, evaluate_regression_model

# Evaluate a classification model
classification_results = evaluate_classification_model(
    y_true=y_test,
    y_pred=y_pred,
    y_prob=y_prob,
    regimes=regimes_test
)

# Evaluate a regression model
regression_results = evaluate_regression_model(
    y_true=y_test,
    y_pred=y_pred,
    regimes=regimes_test
)
```

### Model Calibration

```python
from advanced_trading.models.ml_ensemble import calibrate_probabilities, evaluate_calibration

# Calibrate probabilities
calibrated_probs, calibrator = calibrate_probabilities(
    y_true=y_train,
    y_prob=y_prob_train,
    method='platt',
    regimes=regimes_train,
    test_y_prob=y_prob_test,
    test_regime='trend'
)

# Evaluate calibration
metrics = evaluate_calibration(
    y_true=y_test,
    y_prob=y_prob_test,
    y_prob_calibrated=calibrated_probs,
    visualize=True
)
```

### Meta-Labeling

```python
from advanced_trading.models.ml_ensemble import apply_meta_labeling, evaluate_meta_labeling, optimize_meta_labeling_threshold

# Apply meta-labeling
meta_predictions, meta_labeler = apply_meta_labeling(
    X=X_train,
    y=y_train,
    primary_predictions=primary_pred_train,
    meta_model=meta_model,
    threshold=0.5,
    regimes=regimes_train,
    meta_features=meta_features_train,
    return_meta_labeler=True
)

# Evaluate meta-labeling
metrics = evaluate_meta_labeling(
    X=X_test,
    y=y_test,
    primary_predictions=primary_pred_test,
    meta_model=meta_model,
    threshold=0.5,
    regimes=regimes_test,
    meta_features=meta_features_test,
    visualize=True
)

# Optimize meta-labeling threshold
optimal_threshold, opt_metrics = optimize_meta_labeling_threshold(
    X=X_train,
    y=y_train,
    primary_predictions=primary_pred_train,
    meta_model=meta_model,
    regimes=regimes_train,
    meta_features=meta_features_train,
    metric='precision',  # Options: 'precision', 'recall', 'f1', 'accuracy', 'trade_reduction'
    visualize=True
)
```

### Model Persistence

```python
from advanced_trading.models.ml_ensemble import save_model, load_model, register_model, list_models, get_model_versions

# Save a model
save_model(
    model=trained_model,
    model_name='quick_save_model',
    metadata={'description': 'Quickly saved model'},
    base_dir='./models'
)

# Load a model
loaded_model = load_model(
    model_name='quick_save_model',
    version='latest',
    base_dir='./models'
)

# Register a model
register_model(
    model=trained_model,
    model_name='quick_register_model',
    metadata={'description': 'Quickly registered model'},
    tags=['quick', 'example'],
    base_dir='./models'
)

# List all models
models_df = list_models(base_dir='./models')

# Get model versions
versions_df = get_model_versions(
    model_name='quick_register_model',
    base_dir='./models'
)
```

## Example Files

The ML Ensemble framework includes example files that demonstrate how to use the various components:

- `feature_selection_example.py`: Demonstrates how to use the feature selection functionality
- `model_evaluation_example.py`: Demonstrates how to use the model evaluation functionality
- `calibration_example.py`: Demonstrates how to use the model calibration functionality
- `meta_labeler_example.py`: Demonstrates how to use the meta-labeling functionality
- `model_persistence_example.py`: Demonstrates how to use the model persistence functionality

## Integration with Other Components

The ML Ensemble framework integrates with other components of the Instinct AI system:

- **Regime Detection**: The ensemble can use regime information to select and weight models
- **Feature Engineering**: The feature selection functionality can be used to select relevant features
- **Strategy Framework**: The ensemble predictions can be used to drive trading decisions
- **Risk Management**: The ensemble confidence can be used to adjust position sizing
- **Backtesting**: The ensemble models can be evaluated in the backtesting engine 