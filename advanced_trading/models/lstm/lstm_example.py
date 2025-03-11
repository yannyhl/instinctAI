"""
LSTM Model Example
----------------
This example demonstrates how to use the LSTM model and sequence generator
for financial time series prediction.

The example covers:
1. Data preparation with SequenceGenerator
2. Building and training LSTM models
3. Making predictions and evaluating performance
4. Visualizing results
5. Saving and loading models
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import LSTM model and sequence generator
from advanced_trading.models.lstm.lstm_model import LSTMModel
from advanced_trading.models.lstm.sequence_generator import SequenceGenerator

def generate_example_data(n_samples=1000, n_features=5, noise_level=0.1, random_state=42):
    """
    Generate synthetic financial time series data for demonstration.
    
    Parameters
    ----------
    n_samples : int, default=1000
        Number of samples to generate
    n_features : int, default=5
        Number of features to generate
    noise_level : float, default=0.1
        Level of noise to add to the data
    random_state : int, default=42
        Random state for reproducibility
        
    Returns
    -------
    pd.DataFrame
        DataFrame containing synthetic financial data
    """
    np.random.seed(random_state)
    
    # Generate time index
    dates = pd.date_range(start='2020-01-01', periods=n_samples, freq='D')
    
    # Generate price series with trend, seasonality, and noise
    t = np.arange(n_samples)
    trend = 0.01 * t
    seasonality = 0.1 * np.sin(2 * np.pi * t / 252)  # Annual seasonality (252 trading days)
    noise = noise_level * np.random.randn(n_samples)
    
    price = 100 * np.exp(trend + seasonality + noise)
    
    # Generate features
    features = {}
    
    # Feature 1: Moving average
    features['ma_10'] = pd.Series(price).rolling(window=10).mean().values
    
    # Feature 2: Volatility
    features['volatility'] = pd.Series(price).rolling(window=20).std().values
    
    # Feature 3: Momentum
    features['momentum'] = pd.Series(price).pct_change(periods=5).values
    
    # Feature 4: RSI-like feature
    diff = pd.Series(price).diff().values
    up = np.maximum(diff, 0)
    down = np.abs(np.minimum(diff, 0))
    avg_up = pd.Series(up).rolling(window=14).mean().values
    avg_down = pd.Series(down).rolling(window=14).mean().values
    rs = np.divide(avg_up, avg_down, out=np.zeros_like(avg_up), where=avg_down != 0)
    features['rsi'] = 100 - (100 / (1 + rs))
    
    # Feature 5: Price
    features['price'] = price
    
    # Target: Next day's price
    features['target'] = np.roll(price, -1)
    
    # Create DataFrame
    df = pd.DataFrame(features, index=dates)
    
    # Drop rows with NaN values
    df = df.dropna()
    
    return df

def example_basic_lstm():
    """
    Example of using a basic LSTM model for financial time series prediction.
    """
    print("\n=== Basic LSTM Example ===")
    
    # Generate example data
    data = generate_example_data(n_samples=1000, n_features=5)
    print(f"Generated data shape: {data.shape}")
    print(data.head())
    
    # Create sequence generator
    seq_gen = SequenceGenerator(
        sequence_length=20,
        forecast_horizon=1,
        step_size=1,
        target_column='target',
        feature_columns=['ma_10', 'volatility', 'momentum', 'rsi', 'price'],
        normalize=True,
        normalization_method='standard',
        include_target_as_feature=False,
        batch_size=32,
        shuffle=True,
        random_state=42
    )
    
    # Split data into train, validation, and test sets
    train_size = int(len(data) * 0.7)
    val_size = int(len(data) * 0.15)
    
    train_data = data.iloc[:train_size]
    val_data = data.iloc[train_size:train_size+val_size]
    test_data = data.iloc[train_size+val_size:]
    
    print(f"Train data shape: {train_data.shape}")
    print(f"Validation data shape: {val_data.shape}")
    print(f"Test data shape: {test_data.shape}")
    
    # Prepare sequences
    X_train, y_train = seq_gen.fit_transform(train_data)
    X_val, y_val = seq_gen.transform(val_data)
    X_test, y_test = seq_gen.transform(test_data)
    
    print(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")
    print(f"X_val shape: {X_val.shape}, y_val shape: {y_val.shape}")
    print(f"X_test shape: {X_test.shape}, y_test shape: {y_test.shape}")
    
    # Create and build LSTM model
    model = LSTMModel(
        sequence_length=20,
        n_features=X_train.shape[2],
        n_outputs=1,
        lstm_units=50,
        dropout_rate=0.2,
        dense_units=[32],
        model_type='regression',
        name='basic_lstm',
        random_state=42
    )
    
    model.build_model()
    model.summary()
    
    # Train model
    history = model.fit(
        X_train=X_train,
        y_train=y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=32,
        verbose=1
    )
    
    # Plot training history
    model.plot_history()
    
    # Evaluate model on test data
    test_loss = model.evaluate(X_test, y_test)
    print(f"Test loss: {test_loss}")
    
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Inverse transform predictions and true values
    y_test_inv = seq_gen.inverse_transform_y(y_test)
    y_pred_inv = seq_gen.inverse_transform_y(y_pred)
    
    # Calculate metrics
    mse = mean_squared_error(y_test_inv, y_pred_inv)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test_inv, y_pred_inv)
    r2 = r2_score(y_test_inv, y_pred_inv)
    
    print(f"MSE: {mse:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE: {mae:.4f}")
    print(f"R²: {r2:.4f}")
    
    # Plot predictions
    model.plot_predictions(X_test, y_test, scaler=seq_gen.target_scaler)
    
    # Save model
    model_dir = os.path.join(os.getcwd(), 'example_models')
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'basic_lstm.h5')
    model.save(model_path)
    print(f"Model saved to {model_path}")
    
    # Load model
    loaded_model = LSTMModel.load(model_path)
    
    # Verify loaded model
    y_loaded_pred = loaded_model.predict(X_test)
    loaded_mse = mean_squared_error(y_test, y_loaded_pred)
    print(f"Loaded model MSE: {loaded_mse:.4f}")
    
    return model, seq_gen, (X_train, y_train, X_val, y_val, X_test, y_test)

def example_stacked_lstm():
    """
    Example of using a stacked LSTM model for financial time series prediction.
    """
    print("\n=== Stacked LSTM Example ===")
    
    # Generate example data
    data = generate_example_data(n_samples=1000, n_features=5)
    
    # Create sequence generator
    seq_gen = SequenceGenerator(
        sequence_length=20,
        forecast_horizon=1,
        step_size=1,
        target_column='target',
        feature_columns=['ma_10', 'volatility', 'momentum', 'rsi', 'price'],
        normalize=True,
        normalization_method='standard',
        include_target_as_feature=False,
        batch_size=32,
        shuffle=True,
        random_state=42
    )
    
    # Split data into train, validation, and test sets
    train_size = int(len(data) * 0.7)
    val_size = int(len(data) * 0.15)
    
    train_data = data.iloc[:train_size]
    val_data = data.iloc[train_size:train_size+val_size]
    test_data = data.iloc[train_size+val_size:]
    
    # Prepare sequences
    X_train, y_train = seq_gen.fit_transform(train_data)
    X_val, y_val = seq_gen.transform(val_data)
    X_test, y_test = seq_gen.transform(test_data)
    
    # Create and build stacked LSTM model
    model = LSTMModel(
        sequence_length=20,
        n_features=X_train.shape[2],
        n_outputs=1,
        lstm_units=[64, 32],  # Stacked LSTM with two layers
        dropout_rate=0.2,
        dense_units=[16],
        model_type='regression',
        name='stacked_lstm',
        random_state=42
    )
    
    model.build_model()
    model.summary()
    
    # Train model
    history = model.fit(
        X_train=X_train,
        y_train=y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=32,
        verbose=1
    )
    
    # Plot training history
    model.plot_history()
    
    # Evaluate model on test data
    test_loss = model.evaluate(X_test, y_test)
    print(f"Test loss: {test_loss}")
    
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Inverse transform predictions and true values
    y_test_inv = seq_gen.inverse_transform_y(y_test)
    y_pred_inv = seq_gen.inverse_transform_y(y_pred)
    
    # Calculate metrics
    mse = mean_squared_error(y_test_inv, y_pred_inv)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test_inv, y_pred_inv)
    r2 = r2_score(y_test_inv, y_pred_inv)
    
    print(f"MSE: {mse:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE: {mae:.4f}")
    print(f"R²: {r2:.4f}")
    
    # Plot predictions
    model.plot_predictions(X_test, y_test, scaler=seq_gen.target_scaler)
    
    return model, seq_gen, (X_train, y_train, X_val, y_val, X_test, y_test)

def example_bidirectional_lstm():
    """
    Example of using a bidirectional LSTM model for financial time series prediction.
    """
    print("\n=== Bidirectional LSTM Example ===")
    
    # Generate example data
    data = generate_example_data(n_samples=1000, n_features=5)
    
    # Create sequence generator
    seq_gen = SequenceGenerator(
        sequence_length=20,
        forecast_horizon=1,
        step_size=1,
        target_column='target',
        feature_columns=['ma_10', 'volatility', 'momentum', 'rsi', 'price'],
        normalize=True,
        normalization_method='standard',
        include_target_as_feature=False,
        batch_size=32,
        shuffle=True,
        random_state=42
    )
    
    # Split data into train, validation, and test sets
    train_size = int(len(data) * 0.7)
    val_size = int(len(data) * 0.15)
    
    train_data = data.iloc[:train_size]
    val_data = data.iloc[train_size:train_size+val_size]
    test_data = data.iloc[train_size+val_size:]
    
    # Prepare sequences
    X_train, y_train = seq_gen.fit_transform(train_data)
    X_val, y_val = seq_gen.transform(val_data)
    X_test, y_test = seq_gen.transform(test_data)
    
    # Create and build bidirectional LSTM model
    model = LSTMModel(
        sequence_length=20,
        n_features=X_train.shape[2],
        n_outputs=1,
        lstm_units=50,
        dropout_rate=0.2,
        dense_units=[32],
        bidirectional=True,  # Use bidirectional LSTM
        model_type='regression',
        name='bidirectional_lstm',
        random_state=42
    )
    
    model.build_model()
    model.summary()
    
    # Train model
    history = model.fit(
        X_train=X_train,
        y_train=y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=32,
        verbose=1
    )
    
    # Plot training history
    model.plot_history()
    
    # Evaluate model on test data
    test_loss = model.evaluate(X_test, y_test)
    print(f"Test loss: {test_loss}")
    
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Inverse transform predictions and true values
    y_test_inv = seq_gen.inverse_transform_y(y_test)
    y_pred_inv = seq_gen.inverse_transform_y(y_pred)
    
    # Calculate metrics
    mse = mean_squared_error(y_test_inv, y_pred_inv)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test_inv, y_pred_inv)
    r2 = r2_score(y_test_inv, y_pred_inv)
    
    print(f"MSE: {mse:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE: {mae:.4f}")
    print(f"R²: {r2:.4f}")
    
    # Plot predictions
    model.plot_predictions(X_test, y_test, scaler=seq_gen.target_scaler)
    
    return model, seq_gen, (X_train, y_train, X_val, y_val, X_test, y_test)

def example_multi_step_forecast():
    """
    Example of using LSTM for multi-step forecasting.
    """
    print("\n=== Multi-Step Forecast Example ===")
    
    # Generate example data
    data = generate_example_data(n_samples=1000, n_features=5)
    
    # Create sequence generator with multi-step forecast
    forecast_horizon = 5  # Forecast 5 steps ahead
    
    seq_gen = SequenceGenerator(
        sequence_length=20,
        forecast_horizon=forecast_horizon,
        step_size=1,
        target_column='target',
        feature_columns=['ma_10', 'volatility', 'momentum', 'rsi', 'price'],
        normalize=True,
        normalization_method='standard',
        include_target_as_feature=False,
        batch_size=32,
        shuffle=True,
        random_state=42
    )
    
    # Split data into train, validation, and test sets
    train_size = int(len(data) * 0.7)
    val_size = int(len(data) * 0.15)
    
    train_data = data.iloc[:train_size]
    val_data = data.iloc[train_size:train_size+val_size]
    test_data = data.iloc[train_size+val_size:]
    
    # Prepare sequences
    X_train, y_train = seq_gen.fit_transform(train_data)
    X_val, y_val = seq_gen.transform(val_data)
    X_test, y_test = seq_gen.transform(test_data)
    
    print(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")
    
    # Create and build LSTM model for multi-step forecasting
    model = LSTMModel(
        sequence_length=20,
        n_features=X_train.shape[2],
        n_outputs=forecast_horizon,  # Output multiple steps
        lstm_units=64,
        dropout_rate=0.2,
        dense_units=[32],
        model_type='regression',
        name='multi_step_lstm',
        random_state=42
    )
    
    model.build_model()
    model.summary()
    
    # Train model
    history = model.fit(
        X_train=X_train,
        y_train=y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=32,
        verbose=1
    )
    
    # Plot training history
    model.plot_history()
    
    # Evaluate model on test data
    test_loss = model.evaluate(X_test, y_test)
    print(f"Test loss: {test_loss}")
    
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Inverse transform predictions and true values
    y_test_inv = seq_gen.inverse_transform_y(y_test)
    y_pred_inv = seq_gen.inverse_transform_y(y_pred)
    
    # Calculate metrics for each forecast step
    for step in range(forecast_horizon):
        mse = mean_squared_error(y_test_inv[:, step], y_pred_inv[:, step])
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test_inv[:, step], y_pred_inv[:, step])
        
        print(f"Step {step+1} - MSE: {mse:.4f}, RMSE: {rmse:.4f}, MAE: {mae:.4f}")
    
    # Plot predictions for a sample
    sample_idx = 0
    plt.figure(figsize=(12, 6))
    plt.plot(range(forecast_horizon), y_test_inv[sample_idx], 'b-', label='True')
    plt.plot(range(forecast_horizon), y_pred_inv[sample_idx], 'r-', label='Predicted')
    plt.title('Multi-Step Forecast Example')
    plt.xlabel('Forecast Step')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True)
    plt.show()
    
    return model, seq_gen, (X_train, y_train, X_val, y_val, X_test, y_test)

def example_classification():
    """
    Example of using LSTM for classification.
    """
    print("\n=== Classification Example ===")
    
    # Generate example data
    data = generate_example_data(n_samples=1000, n_features=5)
    
    # Create binary classification target (price goes up or down)
    data['direction'] = (data['target'] > data['price']).astype(int)
    
    # Create sequence generator
    seq_gen = SequenceGenerator(
        sequence_length=20,
        forecast_horizon=1,
        step_size=1,
        target_column='direction',  # Classification target
        feature_columns=['ma_10', 'volatility', 'momentum', 'rsi', 'price'],
        normalize=True,
        normalization_method='standard',
        include_target_as_feature=False,
        batch_size=32,
        shuffle=True,
        random_state=42
    )
    
    # Split data into train, validation, and test sets
    train_size = int(len(data) * 0.7)
    val_size = int(len(data) * 0.15)
    
    train_data = data.iloc[:train_size]
    val_data = data.iloc[train_size:train_size+val_size]
    test_data = data.iloc[train_size+val_size:]
    
    # Prepare sequences
    X_train, y_train = seq_gen.fit_transform(train_data)
    X_val, y_val = seq_gen.transform(val_data)
    X_test, y_test = seq_gen.transform(test_data)
    
    # Create and build LSTM model for classification
    model = LSTMModel(
        sequence_length=20,
        n_features=X_train.shape[2],
        n_outputs=1,  # Binary classification
        lstm_units=64,
        dropout_rate=0.3,
        dense_units=[32],
        output_activation='sigmoid',  # Sigmoid for binary classification
        model_type='classification',
        loss='binary_crossentropy',
        metrics=['accuracy'],
        name='classification_lstm',
        random_state=42
    )
    
    model.build_model()
    model.summary()
    
    # Train model
    history = model.fit(
        X_train=X_train,
        y_train=y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=32,
        verbose=1
    )
    
    # Plot training history
    model.plot_history()
    
    # Evaluate model on test data
    test_loss, test_acc = model.evaluate(X_test, y_test)
    print(f"Test loss: {test_loss:.4f}, Test accuracy: {test_acc:.4f}")
    
    # Make predictions
    y_pred_proba = model.predict_proba(X_test)
    y_pred = (y_pred_proba > 0.5).astype(int)
    
    # Calculate metrics
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    conf_matrix = confusion_matrix(y_test, y_pred)
    
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    print(f"Confusion Matrix:\n{conf_matrix}")
    
    # Plot ROC curve
    from sklearn.metrics import roc_curve, auc
    
    fpr, tpr, thresholds = roc_curve(y_test, y_pred_proba)
    roc_auc = auc(fpr, tpr)
    
    plt.figure(figsize=(10, 8))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver Operating Characteristic')
    plt.legend(loc="lower right")
    plt.grid(True)
    plt.show()
    
    return model, seq_gen, (X_train, y_train, X_val, y_val, X_test, y_test)

def main():
    """Run all examples."""
    try:
        # Run examples
        example_basic_lstm()
        example_stacked_lstm()
        example_bidirectional_lstm()
        example_multi_step_forecast()
        example_classification()
    except Exception as e:
        logger.exception(f"Error running examples: {e}")

if __name__ == "__main__":
    main() 