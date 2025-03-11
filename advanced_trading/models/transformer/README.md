# Transformer Models for Financial Time Series

This module implements transformer-based deep learning models for financial time series prediction. These models leverage the self-attention mechanism to capture long-range dependencies in time series data, which is particularly valuable for financial market prediction where patterns can span across multiple timeframes.

## Overview

The transformer models module provides:

1. **Specialized Architectures**:
   - `TimeSeriesTransformer`: Vanilla transformer adapted for time series with causal masking
   - `TemporalFusionTransformer`: Specialized model for multivariate time series with mixed variables
   - `Informer` (planned): Efficient transformer variant with reduced complexity for long sequences
   - `Autoformer` (planned): Self-attention based decomposition architecture for time series

2. **Training Utilities**:
   - `TransformerDataset`: Dataset class for time series data with sliding windows
   - `TimeSeriesBatch`: Container for batched time series data
   - `TransformerTrainer`: Trainer class with training loop and early stopping

3. **Helper Functions**:
   - Time feature generation
   - Specialized masking functions
   - Data normalization
   - Time series train-test splitting

## Key Features

- **Causal Masking**: Prevents lookahead bias in time series forecasting
- **Time-specific Positional Encoding**: Captures temporal patterns in financial data
- **Variable Selection Networks**: Identifies important features for prediction
- **Interpretable Attention Weights**: Provides insights into model decision-making
- **Flexible Forecast Generation**: Supports multi-horizon forecasting

## Usage Example

```python
from advanced_trading.models.transformer import (
    TimeSeriesTransformer,
    TransformerConfig,
    TransformerTrainer,
    TransformerDataset
)

# Configure model
config = TransformerConfig(
    input_features=10,
    hidden_size=128,
    num_layers=3,
    attention_heads=4,
    dropout=0.1,
    forecast_horizon=5,
    context_length=60
)

# Create model
model = TimeSeriesTransformer(config)

# Create dataset
dataset = TransformerDataset(
    data=data,
    context_length=60,
    forecast_horizon=5,
    target_idx=0
)

# Create data loader
train_loader = DataLoader(dataset, batch_size=32, shuffle=True)

# Train model
trainer = TransformerTrainer(model, learning_rate=1e-4)
history = trainer.fit(train_loader, epochs=100)

# Generate predictions
predictions = model.predict(new_data)
```

## Model Architecture

### TimeSeriesTransformer

The `TimeSeriesTransformer` is a vanilla transformer architecture adapted for time series forecasting. It includes:

1. Input embedding layer
2. Positional encoding with time features
3. Multiple transformer blocks with self-attention
4. Output projection layer

### TemporalFusionTransformer

The `TemporalFusionTransformer` is a specialized architecture for multivariate time series with mixed variables. It includes:

1. Variable selection networks for feature importance
2. Separate processing for static, past, and future inputs
3. LSTM-based temporal processing
4. Self-attention for temporal fusion
5. Gated residual networks for skip connections

## Performance Considerations

- **Memory Usage**: Transformer models can be memory-intensive for long sequences. Consider using smaller batch sizes or sequence lengths for large datasets.
- **Training Time**: Transformer models typically require more training time than traditional models. Use the early stopping feature in `TransformerTrainer` to avoid overfitting.
- **Hyperparameter Tuning**: Model performance is sensitive to hyperparameters such as learning rate, number of layers, and attention heads. Use the `TransformerConfig` class to experiment with different configurations.

## References

1. Vaswani, A., et al. (2017). "Attention is All You Need." NeurIPS.
2. Lim, B., et al. (2021). "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting." International Journal of Forecasting.
3. Zhou, H., et al. (2021). "Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting." AAAI.
4. Wu, H., et al. (2021). "Autoformer: Decomposition Transformers with Auto-Correlation for Long-Term Series Forecasting." NeurIPS. 