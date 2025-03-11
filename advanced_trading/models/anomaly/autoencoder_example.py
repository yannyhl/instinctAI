#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating the use of autoencoder-based anomaly detection for financial time series.

This example shows how to:
1. Load and prepare financial data
2. Create and train different types of autoencoder anomaly detectors
3. Detect anomalies in price and volume data
4. Visualize the results and compare different autoencoder architectures
5. Save and load trained models
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Add parent directory to path to allow imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the AutoencoderDetector
from models.anomaly.autoencoders import AutoencoderDetector

# Import utilities for data generation and preprocessing
from utils.data_utils import load_data, preprocess_data
from utils.visualization import plot_time_series

# Set random seed for reproducibility
np.random.seed(42)

def generate_synthetic_data(n_samples=1000, n_features=5, anomaly_percentage=0.05):
    """
    Generate synthetic financial data with anomalies.
    
    Parameters
    ----------
    n_samples : int, default=1000
        Number of samples to generate.
    n_features : int, default=5
        Number of features to generate.
    anomaly_percentage : float, default=0.05
        Percentage of anomalies to introduce.
        
    Returns
    -------
    pd.DataFrame
        DataFrame with synthetic data.
    np.ndarray
        Array with anomaly labels (1 for normal, -1 for anomaly).
    """
    # Generate dates
    start_date = datetime(2020, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(n_samples)]
    
    # Generate normal data
    data = np.random.randn(n_samples, n_features)
    
    # Add trend and seasonality
    trend = np.linspace(0, 2, n_samples).reshape(-1, 1)
    seasonality = np.sin(np.linspace(0, 10 * np.pi, n_samples)).reshape(-1, 1)
    
    data += trend
    data += seasonality
    
    # Create feature names
    feature_names = [f'Feature_{i}' for i in range(n_features)]
    
    # Create DataFrame
    df = pd.DataFrame(data, index=dates, columns=feature_names)
    
    # Add price and volume-like features
    df['Price'] = 100 + df['Feature_0'].cumsum()
    df['Volume'] = np.abs(10 + 5 * df['Feature_1'] + np.random.randn(n_samples) * 2)
    
    # Introduce anomalies
    n_anomalies = int(n_samples * anomaly_percentage)
    anomaly_indices = np.random.choice(n_samples, n_anomalies, replace=False)
    
    # Create anomaly labels
    labels = np.ones(n_samples)
    labels[anomaly_indices] = -1
    
    # Add point anomalies
    for idx in anomaly_indices[:n_anomalies//3]:
        df.iloc[idx, :] = df.iloc[idx, :] * (np.random.rand() * 5 + 3)
    
    # Add contextual anomalies (break the pattern)
    for idx in anomaly_indices[n_anomalies//3:2*n_anomalies//3]:
        df.iloc[idx, :] = -df.iloc[idx, :] * (np.random.rand() * 2 + 1)
    
    # Add collective anomalies (sequence of unusual values)
    for idx in anomaly_indices[2*n_anomalies//3:]:
        if idx < n_samples - 5:
            df.iloc[idx:idx+5, :] = df.iloc[idx:idx+5, :] * (np.random.rand() * 3 + 2)
            labels[idx:idx+5] = -1
    
    return df, labels

def prepare_sequence_data(data, sequence_length=10):
    """
    Prepare sequence data for LSTM or CNN autoencoders.
    
    Parameters
    ----------
    data : pd.DataFrame
        Input data.
    sequence_length : int, default=10
        Length of sequences to create.
        
    Returns
    -------
    np.ndarray
        Array with sequences.
    """
    n_samples = len(data) - sequence_length + 1
    n_features = data.shape[1]
    
    sequences = np.zeros((n_samples, sequence_length, n_features))
    
    for i in range(n_samples):
        sequences[i] = data.iloc[i:i+sequence_length].values
    
    return sequences

def main():
    print("Autoencoder-based Anomaly Detection Example")
    print("------------------------------------------")
    
    # Generate synthetic data
    print("\n1. Generating synthetic financial data with anomalies...")
    data, labels = generate_synthetic_data(n_samples=1000, n_features=5, anomaly_percentage=0.05)
    
    print(f"Generated data shape: {data.shape}")
    print(f"Number of anomalies: {np.sum(labels == -1)}")
    
    # Plot the data
    plt.figure(figsize=(12, 6))
    plt.plot(data.index, data['Price'], label='Price')
    anomaly_indices = np.where(labels == -1)[0]
    plt.scatter(data.index[anomaly_indices], data.iloc[anomaly_indices]['Price'], 
                color='red', label='Anomalies')
    plt.title('Synthetic Price Data with Anomalies')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    
    # Split data into train and test
    train_size = int(len(data) * 0.7)
    train_data = data.iloc[:train_size]
    test_data = data.iloc[train_size:]
    train_labels = labels[:train_size]
    test_labels = labels[train_size:]
    
    print(f"\nTrain data shape: {train_data.shape}")
    print(f"Test data shape: {test_data.shape}")
    
    # Example 1: Dense Autoencoder for point anomaly detection
    print("\n2. Training Dense Autoencoder for point anomaly detection...")
    
    dense_detector = AutoencoderDetector(
        autoencoder_type='dense',
        hidden_layers=[32, 16],
        latent_dim=8,
        dropout_rate=0.2,
        contamination=0.05,
        normalize=True,
        random_state=42,
        verbose=1
    )
    
    # Fit the detector
    dense_detector.fit(
        train_data,
        epochs=50,
        batch_size=32,
        validation_data=test_data
    )
    
    # Detect anomalies
    print("\nDetecting anomalies with Dense Autoencoder...")
    dense_anomalies = dense_detector.detect_anomalies(test_data)
    
    # Evaluate performance
    from sklearn.metrics import classification_report, confusion_matrix
    
    print("\nDense Autoencoder Performance:")
    print(classification_report(test_labels == -1, dense_anomalies))
    
    # Plot anomalies
    dense_detector.plot_anomalies(
        test_data,
        y=test_labels,
        title='Dense Autoencoder Anomaly Detection',
        time_index=test_data.index
    )
    
    # Plot reconstruction example
    dense_detector.plot_reconstruction(
        test_data,
        sample_idx=10,
        title='Dense Autoencoder Reconstruction Example'
    )
    
    # Example 2: LSTM Autoencoder for sequence anomaly detection
    print("\n3. Training LSTM Autoencoder for sequence anomaly detection...")
    
    # Prepare sequence data
    sequence_length = 10
    train_sequences = prepare_sequence_data(train_data, sequence_length)
    test_sequences = prepare_sequence_data(test_data, sequence_length)
    
    # Adjust labels for sequences
    test_seq_labels = test_labels[sequence_length-1:]
    
    print(f"Train sequences shape: {train_sequences.shape}")
    print(f"Test sequences shape: {test_sequences.shape}")
    
    lstm_detector = AutoencoderDetector(
        autoencoder_type='lstm',
        sequence_length=sequence_length,
        hidden_layers=[64, 32],
        latent_dim=16,
        dropout_rate=0.2,
        contamination=0.05,
        normalize=True,
        random_state=42,
        verbose=1
    )
    
    # Fit the detector
    lstm_detector.fit(
        train_sequences,
        epochs=50,
        batch_size=32,
        validation_data=test_sequences
    )
    
    # Detect anomalies
    print("\nDetecting anomalies with LSTM Autoencoder...")
    lstm_anomalies = lstm_detector.detect_anomalies(test_sequences)
    
    # Evaluate performance
    print("\nLSTM Autoencoder Performance:")
    print(classification_report(test_seq_labels == -1, lstm_anomalies))
    
    # Create a DataFrame for visualization
    test_seq_df = pd.DataFrame(
        test_sequences.reshape(test_sequences.shape[0], -1),
        index=test_data.index[sequence_length-1:]
    )
    
    # Plot anomalies
    lstm_detector.plot_anomalies(
        test_seq_df,
        y=test_seq_labels,
        title='LSTM Autoencoder Anomaly Detection',
        time_index=test_seq_df.index
    )
    
    # Plot reconstruction example
    lstm_detector.plot_reconstruction(
        test_sequences,
        sample_idx=10,
        n_features=3,
        title='LSTM Autoencoder Reconstruction Example'
    )
    
    # Example 3: Convolutional Autoencoder
    print("\n4. Training Convolutional Autoencoder for sequence anomaly detection...")
    
    conv_detector = AutoencoderDetector(
        autoencoder_type='conv',
        sequence_length=sequence_length,
        hidden_layers=[64, 32],
        latent_dim=16,
        dropout_rate=0.2,
        contamination=0.05,
        normalize=True,
        random_state=42,
        verbose=1
    )
    
    # Fit the detector
    conv_detector.fit(
        train_sequences,
        epochs=50,
        batch_size=32,
        validation_data=test_sequences
    )
    
    # Detect anomalies
    print("\nDetecting anomalies with Convolutional Autoencoder...")
    conv_anomalies = conv_detector.detect_anomalies(test_sequences)
    
    # Evaluate performance
    print("\nConvolutional Autoencoder Performance:")
    print(classification_report(test_seq_labels == -1, conv_anomalies))
    
    # Plot anomalies
    conv_detector.plot_anomalies(
        test_seq_df,
        y=test_seq_labels,
        title='Convolutional Autoencoder Anomaly Detection',
        time_index=test_seq_df.index
    )
    
    # Compare results
    print("\n5. Comparing different autoencoder architectures...")
    
    # Create a DataFrame with results
    results = pd.DataFrame({
        'True': test_seq_labels == -1,
        'Dense': np.pad(dense_anomalies, (sequence_length-1, 0), 'constant')[:len(test_seq_labels)],
        'LSTM': lstm_anomalies,
        'Conv': conv_anomalies
    }, index=test_seq_df.index)
    
    # Plot comparison
    plt.figure(figsize=(14, 8))
    
    # Plot price
    plt.subplot(2, 1, 1)
    plt.plot(test_data.index, test_data['Price'], label='Price')
    
    # Plot anomalies
    for col, color in zip(['True', 'Dense', 'LSTM', 'Conv'], ['green', 'red', 'orange', 'purple']):
        anomaly_indices = results.index[results[col]]
        if len(anomaly_indices) > 0:
            plt.scatter(
                anomaly_indices,
                test_data.loc[anomaly_indices, 'Price'],
                color=color,
                marker='o',
                label=f'{col} Anomalies'
            )
    
    plt.title('Comparison of Anomaly Detection Methods')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    
    # Plot anomaly scores
    plt.subplot(2, 1, 2)
    
    # Get scores
    dense_scores = dense_detector.decision_function(test_data)
    lstm_scores = lstm_detector.decision_function(test_sequences)
    conv_scores = conv_detector.decision_function(test_sequences)
    
    # Pad dense scores
    dense_scores_padded = np.pad(dense_scores, (sequence_length-1, 0), 'constant')[:len(lstm_scores)]
    
    # Plot scores
    plt.plot(test_seq_df.index, dense_scores_padded, 'r-', label='Dense Scores')
    plt.plot(test_seq_df.index, lstm_scores, 'g-', label='LSTM Scores')
    plt.plot(test_seq_df.index, conv_scores, 'b-', label='Conv Scores')
    
    # Add threshold lines
    plt.axhline(y=dense_detector.threshold, color='r', linestyle='--', label='Dense Threshold')
    plt.axhline(y=lstm_detector.threshold, color='g', linestyle='--', label='LSTM Threshold')
    plt.axhline(y=conv_detector.threshold, color='b', linestyle='--', label='Conv Threshold')
    
    plt.xlabel('Date')
    plt.ylabel('Anomaly Score')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.show()
    
    # Save models
    print("\n6. Saving models...")
    
    # Create directory if it doesn't exist
    os.makedirs('models/saved_models', exist_ok=True)
    
    dense_detector.save('models/saved_models/dense_autoencoder.h5')
    lstm_detector.save('models/saved_models/lstm_autoencoder.h5')
    conv_detector.save('models/saved_models/conv_autoencoder.h5')
    
    # Load models
    print("\n7. Loading models...")
    
    loaded_dense = AutoencoderDetector.load('models/saved_models/dense_autoencoder.h5')
    loaded_lstm = AutoencoderDetector.load('models/saved_models/lstm_autoencoder.h5')
    
    # Verify loaded models
    print("\nVerifying loaded models...")
    
    loaded_dense_anomalies = loaded_dense.detect_anomalies(test_data)
    loaded_lstm_anomalies = loaded_lstm.detect_anomalies(test_sequences)
    
    print(f"Dense model - Original vs Loaded anomalies match: {np.array_equal(dense_anomalies, loaded_dense_anomalies)}")
    print(f"LSTM model - Original vs Loaded anomalies match: {np.array_equal(lstm_anomalies, loaded_lstm_anomalies)}")
    
    print("\nAutoencoder-based Anomaly Detection Example completed successfully!")

if __name__ == "__main__":
    main() 