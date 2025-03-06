# ML Ensemble Framework

The ML Ensemble framework is a sophisticated system for combining multiple machine learning models to improve prediction accuracy and robustness in financial markets. This framework is specifically designed to handle the challenges of financial time series prediction, including regime shifts, varying feature importance, and the need for adaptive model weights.

## Key Features

- **Multiple Model Types**: Support for heterogeneous model types including tree-based models, neural networks, and statistical models
- **Various Ensemble Methods**: Implementation of different ensemble techniques including voting, weighted averaging, and stacking
- **Regime-Specific Model Selection**: Dynamic model selection and weighting based on detected market regimes
- **Feature Importance Analysis**: Tracking and visualization of feature importance across different market conditions
- **Dynamic Weight Adjustment**: Adaptive adjustment of model weights based on recent performance
- **Visualization Tools**: Comprehensive visualization of model performance, weights, and feature importance

## Core Components

### EnsembleManager

The primary class that manages a collection of machine learning models and implements ensemble methods for prediction. It provides:

- Training models with regime awareness
- Making predictions with different ensemble techniques
- Updating model weights based on recent performance
- Analyzing feature importance
- Visualizing model performance and weights

## Usage Examples

### Basic Usage

```python
from advanced_trading.models.ml_ensemble import EnsembleManager

# Create base models (any scikit-learn compatible models)
base_models = {
    'random_forest': RandomForestClassifier(n_estimators=100),
    'gradient_boosting': GradientBoostingClassifier(),
    'logistic_regression': LogisticRegression()
}

# Create ensemble manager
ensemble = EnsembleManager(
    base_models=base_models,
    ensemble_method='weighted_avg',
    model_type='classification',
    regime_aware=True
)

# Train the ensemble
ensemble.fit(X_train, y_train, regimes=regime_labels)

# Make predictions
predictions = ensemble.predict(X_test, current_regime='bull')

# Update weights based on recent performance
ensemble.update_weights(recent_predictions, recent_targets, current_regime='bull')

# Visualize feature importance
ensemble.visualize_feature_importance(regime='bull')
```

### Advanced Usage: Regime-Specific Training and Prediction

```python
# Train with regime information
ensemble.fit(X_train, y_train, regimes=market_regimes)

# Predict with different regimes
bull_predictions = ensemble.predict(X_bull, current_regime='bull')
bear_predictions = ensemble.predict(X_bear, current_regime='bear')
sideways_predictions = ensemble.predict(X_sideways, current_regime='sideways')

# Analyze feature importance by regime
bull_features = ensemble.get_feature_importance(regime='bull')
bear_features = ensemble.get_feature_importance(regime='bear')
```

### Visualization

```python
# Visualize feature importance
ensemble.visualize_feature_importance(regime='bull', top_n=10)

# Visualize model weights across regimes
ensemble.visualize_model_weights()

# Visualize model performance over time
ensemble.visualize_model_performance()
```

### Saving and Loading Models

```python
# Save the ensemble model
ensemble.save('models/ensemble_model.joblib')

# Load the ensemble model
loaded_ensemble = EnsembleManager.load('models/ensemble_model.joblib')
```

## Integration with Other Components

The ML Ensemble framework is designed to integrate with other components of the Instinct AI system:

- **Regime Detection**: Can use market regimes detected by the RegimeClassifier
- **Signal Processing**: Predictions can be processed using the signal processing utilities
- **Backtesting Engine**: Models can be evaluated using the walk-forward testing framework

## Performance Considerations

- **Training Time**: Training multiple models with regime awareness can be computationally intensive
- **Prediction Speed**: Prediction requires running multiple models, which can be slower than a single model
- **Memory Usage**: Storing multiple models and their weights requires more memory

## Best Practices

1. **Model Selection**: Include diverse models that perform well in different market regimes
2. **Feature Engineering**: Create features that are relevant across different market conditions
3. **Regime Definition**: Define regimes that are meaningful for your trading strategy
4. **Weight Update Frequency**: Update weights frequently enough to adapt to changing markets, but not so frequently that you overfit to noise
5. **Validation**: Use proper time-series cross-validation to evaluate ensemble performance

## Contributing

When extending or modifying the ML Ensemble framework, please follow these guidelines:

1. Ensure backward compatibility when adding new features
2. Add comprehensive unit tests for new functionality
3. Update documentation to reflect changes
4. Follow the existing code style and naming conventions

## Future Enhancements

- Support for more ensemble methods (boosting, bagging)
- Integration with deep learning models
- Online learning capabilities
- Explainability tools for model decisions
- Multi-asset correlation awareness 