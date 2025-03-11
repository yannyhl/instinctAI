# Anomaly Detection Module

The Anomaly Detection module provides a collection of algorithms for detecting anomalies in financial time series data. These algorithms can be used to identify unusual patterns, outliers, and anomalous behavior in market data, which can be valuable for risk management, trading signal generation, and market surveillance.

## Overview

This module implements several anomaly detection techniques specifically tailored for financial time series data:

1. **Isolation Forest**: An ensemble-based method that isolates observations by randomly selecting a feature and then randomly selecting a split value between the maximum and minimum values of the selected feature.

2. **One-Class SVM**: A support vector machine-based method that learns a decision boundary that encompasses the normal data points, treating outliers as lying outside the boundary.

3. **Autoencoder-based Detection**: Neural network-based approach that learns to compress and reconstruct normal data, identifying anomalies based on reconstruction error.

## Features

- **Multiple Detection Algorithms**: Choose from different anomaly detection techniques based on your specific use case.
- **Time-Aware Detection**: Special handling for time series data, including sequence-based detection.
- **Visualization Tools**: Comprehensive visualization capabilities for anomaly analysis.
- **Model Persistence**: Save and load trained models for later use.
- **Integration with ML Ensemble**: Seamless integration with the ML Ensemble framework.

## Components

### Isolation Forest Detector

The `IsolationForestDetector` class implements anomaly detection using the Isolation Forest algorithm. Key features include:

- Standard and time-aware anomaly detection modes
- Configurable contamination parameter
- Visualization tools for anomaly analysis
- Model persistence

### One-Class SVM Detector

The `OneClassSVMDetector` class implements anomaly detection using the One-Class SVM algorithm. Key features include:

- Configurable kernel and nu parameters
- Visualization tools for anomaly analysis
- Model persistence

### Autoencoder Detector

The `AutoencoderDetector` class implements anomaly detection using autoencoder neural networks. Key features include:

- Multiple autoencoder architectures:
  - Dense (fully connected) autoencoders for point anomaly detection
  - LSTM autoencoders for sequence anomaly detection
  - Convolutional autoencoders for pattern-based anomaly detection
- Configurable network architecture
- Data normalization options
- Visualization tools:
  - Anomaly plots with reconstruction error
  - Reconstruction visualization
  - Latent space visualization (for 2D/3D latent spaces)
- Model persistence

## Usage Examples

### Isolation Forest Example

```python
from models.anomaly.isolation_forest import IsolationForestDetector

# Create detector
detector = IsolationForestDetector(
    n_estimators=100,
    contamination=0.05,
    random_state=42
)

# Fit and detect anomalies
detector.fit(data)
anomalies = detector.detect_anomalies(data)

# Visualize results
detector.plot_anomalies(data, time_index=data.index)
```

### One-Class SVM Example

```python
from models.anomaly.one_class_svm import OneClassSVMDetector

# Create detector
detector = OneClassSVMDetector(
    kernel='rbf',
    nu=0.05,
    gamma='scale'
)

# Fit and detect anomalies
detector.fit(data)
anomalies = detector.detect_anomalies(data)

# Visualize results
detector.plot_anomalies(data, time_index=data.index)
```

### Autoencoder Example

```python
from models.anomaly.autoencoders import AutoencoderDetector

# Create detector (Dense Autoencoder)
detector = AutoencoderDetector(
    autoencoder_type='dense',
    hidden_layers=[32, 16],
    latent_dim=8,
    dropout_rate=0.2,
    contamination=0.05,
    normalize=True
)

# Fit and detect anomalies
detector.fit(data, epochs=50, batch_size=32)
anomalies = detector.detect_anomalies(data)

# Visualize results
detector.plot_anomalies(data, time_index=data.index)
detector.plot_reconstruction(data, sample_idx=0)

# For sequence data (LSTM Autoencoder)
lstm_detector = AutoencoderDetector(
    autoencoder_type='lstm',
    sequence_length=10,
    hidden_layers=[64, 32],
    latent_dim=16,
    dropout_rate=0.2,
    contamination=0.05
)

# Prepare sequence data
sequences = prepare_sequence_data(data, sequence_length=10)

# Fit and detect anomalies
lstm_detector.fit(sequences, epochs=50, batch_size=32)
anomalies = lstm_detector.detect_anomalies(sequences)
```

## Integration with ML Ensemble

The anomaly detection algorithms can be integrated with the ML Ensemble framework to create more robust trading signals:

```python
from models.ml_ensemble.ensemble import MLEnsemble
from models.anomaly.isolation_forest import IsolationForestDetector

# Create ensemble
ensemble = MLEnsemble()

# Add anomaly detector as a feature generator
ensemble.add_feature_generator(
    "anomaly_score",
    lambda data: IsolationForestDetector().fit(data).decision_function(data)
)

# Use in model training
ensemble.train(data)
```

## Advanced Use Cases

- **Market Regime Detection**: Identify unusual market conditions that may require different trading strategies.
- **Flash Crash Detection**: Detect sudden, extreme market movements in real-time.
- **Data Quality Monitoring**: Identify data quality issues and outliers in market data feeds.
- **Risk Management**: Monitor portfolio behavior for unusual patterns that may indicate increased risk.
- **Trading Signal Enhancement**: Use anomaly scores as additional features for trading models.

## References

- Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation forest. In 2008 Eighth IEEE International Conference on Data Mining (pp. 413-422). IEEE.
- Schölkopf, B., Platt, J. C., Shawe-Taylor, J., Smola, A. J., & Williamson, R. C. (2001). Estimating the support of a high-dimensional distribution. Neural computation, 13(7), 1443-1471.
- Sakurada, M., & Yairi, T. (2014). Anomaly detection using autoencoders with nonlinear dimensionality reduction. In Proceedings of the MLSDA 2014 2nd Workshop on Machine Learning for Sensory Data Analysis (pp. 4-11). 