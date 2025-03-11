"""
Time Series Transformer Models Package

This package implements transformer-based deep learning models for financial time series prediction.
These models leverage the self-attention mechanism to capture long-range dependencies in time series data,
which is particularly valuable for financial market prediction where patterns can span across
multiple timeframes.

The implementation includes specialized architectures adapted for time series data, such as:
1. Temporal Fusion Transformers (TFT) - For multivariate time series with mixed variables
2. Time Series Transformers (TST) - Specialized for univariate and multivariate time series
3. Informer - Efficient transformer variant with reduced complexity for long sequences
4. Autoformer - Self-attention based decomposition architecture for time series

Key components:
- Base transformer architecture with self-attention mechanisms
- Time-specific positional encodings for financial time series
- Input/output adaptations for different prediction tasks
- Training utilities with early stopping and learning rate scheduling
- Specialized prediction heads for different trading tasks

Usage:
    from advanced_trading.models.transformer import (
        TimeSeriesTransformer,
        TemporalFusionTransformer,
        Informer,
        Autoformer,
        TransformerConfig,
        TransformerTrainer
    )
    
    # Create and train a model
    config = TransformerConfig(
        input_features=10,
        forecast_horizon=5,
        attention_heads=4,
        hidden_size=128
    )
    model = TimeSeriesTransformer(config)
    trainer = TransformerTrainer(model, learning_rate=1e-4)
    trainer.fit(X_train, y_train, validation_data=(X_val, y_val))
    
    # Make predictions
    predictions = model.predict(X_test)
"""

from advanced_trading.models.transformer.base import (
    TransformerBlock,
    MultiHeadAttention,
    PositionalEncoding,
    TransformerConfig,
    TransformerBase
)

from advanced_trading.models.transformer.models import (
    TimeSeriesTransformer,
    TemporalFusionTransformer,
    Informer,
    Autoformer
)

from advanced_trading.models.transformer.training import (
    TransformerTrainer,
    TransformerDataset,
    TimeSeriesBatch
)

from advanced_trading.models.transformer.utils import (
    create_time_features,
    generate_square_subsequent_mask,
    time_series_train_test_split,
    normalize_time_series
)

__all__ = [
    # Base components
    'TransformerBlock',
    'MultiHeadAttention',
    'PositionalEncoding',
    'TransformerConfig',
    'TransformerBase',
    
    # Models
    'TimeSeriesTransformer',
    'TemporalFusionTransformer',
    'Informer',
    'Autoformer',
    
    # Training
    'TransformerTrainer',
    'TransformerDataset',
    'TimeSeriesBatch',
    
    # Utilities
    'create_time_features',
    'generate_square_subsequent_mask',
    'time_series_train_test_split',
    'normalize_time_series'
] 