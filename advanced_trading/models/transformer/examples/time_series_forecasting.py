"""
Time Series Forecasting with Transformers Example

This example demonstrates how to use the transformer models for financial time series forecasting.
It includes data preparation, model configuration, training, evaluation, and visualization.

Usage:
    python -m advanced_trading.models.transformer.examples.time_series_forecasting
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
from torch.utils.data import DataLoader
import yfinance as yf
from sklearn.preprocessing import StandardScaler
import logging
import os
from datetime import datetime, timedelta

from advanced_trading.models.transformer import (
    TimeSeriesTransformer,
    TemporalFusionTransformer,
    TransformerConfig,
    TransformerTrainer,
    TransformerDataset
)

from advanced_trading.models.transformer.utils import (
    create_time_features,
    time_series_train_test_split,
    normalize_time_series
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set random seeds for reproducibility
np.random.seed(42)
torch.manual_seed(42)


def download_data():
    """Download financial data for example."""
    # Download 5 years of SPY data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)
    
    logger.info(f"Downloading SPY data from {start_date.date()} to {end_date.date()}...")
    df = yf.download('SPY', start=start_date, end=end_date, interval='1d')
    
    logger.info(f"Downloaded {len(df)} data points")
    return df


def prepare_data(df):
    """Prepare data for transformer models."""
    # Calculate returns and volatility features
    df['returns'] = df['Close'].pct_change()
    df['log_returns'] = np.log(df['Close']).diff()
    df['volatility'] = df['returns'].rolling(20).std()
    df['volume_ma'] = df['Volume'].rolling(10).mean() / df['Volume'].rolling(50).mean()
    
    # Calculate technical indicators
    df['ma_10'] = df['Close'].rolling(10).mean()
    df['ma_50'] = df['Close'].rolling(50).mean()
    df['rsi'] = calculate_rsi(df['Close'])
    
    # Create price relatives to handle non-stationarity
    df['close_rel'] = df['Close'] / df['Close'].shift(10) - 1
    df['high_rel'] = df['High'] / df['Close'].shift(1) - 1
    df['low_rel'] = df['Low'] / df['Close'].shift(1) - 1
    
    # Create target (future returns at different horizons)
    for horizon in [1, 3, 5, 10]:
        df[f'target_{horizon}d'] = df['returns'].shift(-horizon)
    
    # Create time features
    time_feats = create_time_features(df.index)
    time_df = pd.DataFrame(time_feats, index=df.index)
    
    # Drop NaN values
    df = df.dropna()
    time_df = time_df.loc[df.index]
    
    logger.info(f"Data preparation complete. Shape: {df.shape}")
    return df, time_df


def calculate_rsi(price_series, window=14):
    """Calculate Relative Strength Index."""
    delta = price_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def main():
    """Main function for time series forecasting example."""
    # Download and prepare data
    df = download_data()
    df, time_df = prepare_data(df)
    
    # Define features and targets
    feature_columns = [
        'close_rel', 'high_rel', 'low_rel', 'returns', 'log_returns',
        'volatility', 'volume_ma', 'ma_10', 'ma_50', 'rsi'
    ]
    
    target_column = 'target_5d'  # 5-day future returns
    context_length = 60  # Use 60 days of history
    forecast_horizon = 5  # Predict 5 days ahead
    
    # Split data
    train_ratio, val_ratio, test_ratio = 0.7, 0.15, 0.15
    
    # Prepare feature data
    X = df[feature_columns].values
    y = df[[target_column]].values
    
    # Normalize features
    X_scaled, scaler = normalize_time_series(X, method='standard', return_scaler=True)
    
    # Split data ensuring temporal order
    train_size = int(len(X_scaled) * train_ratio)
    val_size = int(len(X_scaled) * val_ratio)
    
    X_train = X_scaled[:train_size]
    X_val = X_scaled[train_size:train_size+val_size]
    X_test = X_scaled[train_size+val_size:]
    
    y_train = y[:train_size]
    y_val = y[train_size:train_size+val_size]
    y_test = y[train_size+val_size:]
    
    time_train = time_df.values[:train_size]
    time_val = time_df.values[train_size:train_size+val_size]
    time_test = time_df.values[train_size+val_size:]
    
    logger.info(f"Train set: {X_train.shape}, Val set: {X_val.shape}, Test set: {X_test.shape}")
    
    # Set up datasets
    target_idx = 0  # Index of target variable after splitting
    
    train_dataset = TransformerDataset(
        data=np.concatenate([X_train, y_train], axis=1),
        context_length=context_length,
        forecast_horizon=forecast_horizon,
        target_idx=feature_columns.index(target_column),
        time_features=time_train
    )
    
    val_dataset = TransformerDataset(
        data=np.concatenate([X_val, y_val], axis=1),
        context_length=context_length,
        forecast_horizon=forecast_horizon,
        target_idx=feature_columns.index(target_column),
        time_features=time_val
    )
    
    test_dataset = TransformerDataset(
        data=np.concatenate([X_test, y_test], axis=1),
        context_length=context_length,
        forecast_horizon=forecast_horizon,
        target_idx=feature_columns.index(target_column),
        time_features=time_test
    )
    
    # Create data loaders
    batch_size = 32
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)
    test_loader = DataLoader(test_dataset, batch_size=batch_size)
    
    # Configure and initialize transformer model
    model_config = TransformerConfig(
        input_features=len(feature_columns),
        hidden_size=128,
        num_layers=3,
        attention_heads=4,
        dropout=0.1,
        forecast_horizon=forecast_horizon,
        context_length=context_length
    )
    
    # Create model
    model = TimeSeriesTransformer(model_config)
    logger.info(f"Model created with {model.count_parameters():,} parameters")
    
    # Set up trainer
    trainer = TransformerTrainer(
        model=model,
        learning_rate=1e-4,
        weight_decay=1e-6,
        patience=10,
        checkpoint_path="transformer_checkpoint.pt"
    )
    
    # Train model
    logger.info("Starting model training...")
    history = trainer.fit(
        train_loader=train_loader,
        val_loader=val_loader,
        epochs=30,
        verbose=True
    )
    
    # Plot training history
    plt.figure(figsize=(12, 5))
    
    plt.subplot(1, 2, 1)
    plt.plot(history['train_loss'], label='Train Loss')
    plt.plot(history['val_loss'], label='Validation Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Training and Validation Loss')
    plt.legend()
    plt.grid(True)
    
    plt.subplot(1, 2, 2)
    plt.plot(history['learning_rate'])
    plt.xlabel('Epoch')
    plt.ylabel('Learning Rate')
    plt.title('Learning Rate Schedule')
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('transformer_training_history.png')
    logger.info("Training history saved to transformer_training_history.png")
    
    # Evaluate on test set
    logger.info("Evaluating model on test set...")
    test_metrics = trainer.evaluate(test_loader)
    
    for metric_name, metric_value in test_metrics.items():
        logger.info(f"{metric_name}: {metric_value:.4f}")
    
    # Generate predictions
    logger.info("Generating predictions...")
    predictions = trainer.predict(test_loader)
    
    # Plot sample predictions
    plt.figure(figsize=(12, 8))
    
    # Get actual targets for comparison
    all_targets = []
    for batch_data in test_loader:
        future_targets = batch_data['future_data'].numpy()
        all_targets.append(future_targets)
    
    all_targets = np.concatenate(all_targets, axis=0)  # [total_samples, forecast_horizon, num_targets]
    
    # Plot predictions vs actual for random samples
    num_samples = 4
    sample_indices = np.random.choice(len(all_targets), num_samples, replace=False)
    
    for i, idx in enumerate(sample_indices):
        plt.subplot(2, 2, i+1)
        
        # Target and predictions for this sample
        target = all_targets[idx, :, 0]
        pred = predictions[:, idx, 0]
        
        # Create time points
        time_points = np.arange(forecast_horizon)
        
        # Plot
        plt.plot(time_points, target, label='Actual', marker='o')
        plt.plot(time_points, pred, label='Prediction', marker='x')
        
        plt.xlabel('Forecast Horizon (days)')
        plt.ylabel('Returns')
        plt.title(f'Sample {idx}')
        plt.legend()
        plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('transformer_predictions.png')
    logger.info("Predictions visualization saved to transformer_predictions.png")
    
    # TemporalFusionTransformer Example
    logger.info("\nTraining TemporalFusionTransformer for comparison...")
    
    # Configure TFT model with static and known future features
    tft_config = TransformerConfig(
        input_features=len(feature_columns),
        hidden_size=128,
        num_layers=2,
        attention_heads=4,
        dropout=0.1,
        forecast_horizon=forecast_horizon,
        context_length=context_length
    )
    
    # Add TFT-specific attributes (no static or known future features in this example)
    tft_config.static_features = 0
    tft_config.known_future_features = 0
    
    # Create TFT model
    tft_model = TemporalFusionTransformer(tft_config)
    logger.info(f"TFT Model created with {tft_model.count_parameters():,} parameters")
    
    # Set up trainer for TFT
    tft_trainer = TransformerTrainer(
        model=tft_model,
        learning_rate=5e-4,  # Slightly higher learning rate
        weight_decay=1e-6,
        patience=10,
        checkpoint_path="tft_checkpoint.pt"
    )
    
    # Train TFT model
    logger.info("Starting TFT model training...")
    tft_history = tft_trainer.fit(
        train_loader=train_loader,
        val_loader=val_loader,
        epochs=30,
        verbose=True
    )
    
    # Compare models
    logger.info("\nModel Comparison:")
    vanilla_metrics = trainer.evaluate(test_loader)
    tft_metrics = tft_trainer.evaluate(test_loader)
    
    print("TimeSeriesTransformer metrics:")
    for metric_name, metric_value in vanilla_metrics.items():
        if metric_name in ['loss', 'mae', 'rmse', 'r2']:
            print(f"  {metric_name}: {metric_value:.4f}")
    
    print("\nTemporalFusionTransformer metrics:")
    for metric_name, metric_value in tft_metrics.items():
        if metric_name in ['loss', 'mae', 'rmse', 'r2']:
            print(f"  {metric_name}: {metric_value:.4f}")
    
    logger.info("Example completed successfully")


if __name__ == "__main__":
    main() 