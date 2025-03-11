# Enhanced Ensemble Machine Learning Framework

This module provides an advanced ensemble learning framework designed specifically for trading applications. It combines regime detection, prediction confidence scoring, model diversity optimization, and adaptive position sizing to create a comprehensive solution for market adaptation.

## Key Components

### 1. RegimeEnhancedManager

The `RegimeEnhancedManager` class provides automatic market regime detection and handling capabilities:

- Automatic regime detection using multiple methods (K-means, GMM, thresholds)
- Regime-specific model selection and weighting
- Smooth transition handling between regimes
- Regime history tracking and visualization
- Regime forecasting to anticipate upcoming shifts

### 2. ConfidenceDiversityManager

The `ConfidenceDiversityManager` class focuses on prediction confidence scoring and model diversity:

- Multiple methods for confidence calculation (entropy, agreement, calibration)
- Model diversity tracking and correlation analysis
- Model clustering to detect and handle redundancy
- Calibration curve tracking and correction
- Position sizing based on prediction confidence

### 3. EnhancedEnsembleManager

The `EnhancedEnsembleManager` integrates both components into a unified framework:

- Regime-aware model selection
- Confidence-based position sizing
- Diversity-optimized ensemble combinations
- Continuous learning and adaptation
- Comprehensive performance tracking
- State persistence for production deployment

## Usage

### Basic Example

```python
from instinct_ai.advanced_trading.models.ml_ensemble.enhanced_ensemble_manager import EnhancedEnsembleManager

# Initialize with model names and parameters
ensemble_manager = EnhancedEnsembleManager(
    base_models=['model_1', 'model_2', 'model_3', 'model_4', 'model_5'],
    n_regimes=3,
    regime_features=['volatility', 'volume', 'trend_strength', 'correlation', 'momentum'],
    confidence_method='agreement',
    diversity_method='correlation',
    detection_method='kmeans'
)

# For each trading decision:
# 1. Detect current regime
regime = ensemble_manager.detect_regime(market_features)

# 2. Select appropriate models
selected_models = ensemble_manager.select_models()

# 3. Get prediction with confidence and position sizing
prediction, confidence, position_size = ensemble_manager.predict(model_predictions)

# 4. After results are known, update performance
ensemble_manager.update_performance(
    model_predictions,
    ensemble_prediction,
    actual_values,
    performance_metrics
)
```

### Full Documentation

For a complete example, see `example_usage.py` which demonstrates all major features.

## Advanced Features

### Regime Detection

The system supports multiple regime detection methods:

- **K-means clustering**: Unsupervised detection of market states
- **Gaussian Mixture Models**: Probability-based regime assignment
- **Threshold-based**: Rule-based detection using domain knowledge

### Confidence Scoring

Three confidence calculation methods are available:

- **Entropy-based**: Measures uncertainty in probability distributions
- **Agreement-based**: Assesses consensus among models
- **Calibration-based**: Adjusts confidence based on historical accuracy

### Position Sizing

Position size is adjusted dynamically based on:

- Prediction confidence
- Current market regime
- Regime transition state
- Historical performance in similar conditions

### Model Diversity

Diversity optimization ensures the ensemble includes complementary models:

- Correlation analysis between model predictions
- Hierarchical clustering to identify redundant models
- Selection of diverse, high-performing models 

## Performance Visualization

The framework includes comprehensive visualization tools:

- Regime detection history
- Model performance by regime
- Confidence calibration curves
- Model diversity matrices and dendrograms
- Position sizing functions

## Installation

This module is part of the Instinct AI Trading System. No separate installation is required beyond the base system.

## Requirements

- NumPy
- Pandas
- Scikit-learn
- Matplotlib
- Seaborn
- SciPy

## Testing

Run the integration tests to verify correct operation:

```
python test_integration.py
```

For a full simulation with mock data:

```
python example_usage.py 