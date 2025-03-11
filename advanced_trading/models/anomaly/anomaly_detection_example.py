"""
Anomaly Detection Example
-----------------------
This example demonstrates how to use the anomaly detection modules for
detecting anomalies in financial time series data.

The example covers:
1. Using Isolation Forest for anomaly detection
2. Using One-Class SVM for anomaly detection
3. Comparing different anomaly detection methods
4. Visualizing anomalies in financial data
5. Time-aware anomaly detection
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict, Union, Optional, Tuple, Any
import logging
import datetime
import yfinance as yf
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import anomaly detection modules
from advanced_trading.models.anomaly.isolation_forest import IsolationForestDetector, detect_anomalies as if_detect_anomalies
from advanced_trading.models.anomaly.one_class_svm import OneClassSVMDetector, detect_anomalies as svm_detect_anomalies

def generate_synthetic_data(n_samples=1000, anomaly_ratio=0.05, random_state=42):
    """
    Generate synthetic financial time series data with anomalies.
    
    Parameters
    ----------
    n_samples : int, default=1000
        Number of samples to generate
    anomaly_ratio : float, default=0.05
        Ratio of anomalies to generate
    random_state : int, default=42
        Random state for reproducibility
        
    Returns
    -------
    pd.DataFrame
        DataFrame containing synthetic financial data with anomalies
    np.ndarray
        Boolean array indicating anomalies (True for anomalies)
    """
    np.random.seed(random_state)
    
    # Generate time index
    dates = pd.date_range(start='2020-01-01', periods=n_samples, freq='D')
    
    # Generate price series with trend, seasonality, and noise
    t = np.arange(n_samples)
    trend = 0.01 * t
    seasonality = 0.1 * np.sin(2 * np.pi * t / 252)  # Annual seasonality (252 trading days)
    noise = 0.05 * np.random.randn(n_samples)
    
    price = 100 * np.exp(trend + seasonality + noise)
    
    # Generate features
    features = {}
    
    # Feature 1: Price
    features['price'] = price
    
    # Feature 2: Returns
    returns = np.zeros_like(price)
    returns[1:] = np.diff(price) / price[:-1]
    features['returns'] = returns
    
    # Feature 3: Volatility (rolling standard deviation of returns)
    volatility = pd.Series(returns).rolling(window=20).std().values
    features['volatility'] = volatility
    
    # Feature 4: Volume
    volume = 1000000 + 500000 * np.random.randn(n_samples)
    volume = np.abs(volume)
    features['volume'] = volume
    
    # Create DataFrame
    df = pd.DataFrame(features, index=dates)
    
    # Generate anomalies
    n_anomalies = int(n_samples * anomaly_ratio)
    anomaly_indices = np.random.choice(np.arange(n_samples), size=n_anomalies, replace=False)
    
    # Create anomalies in the data
    for idx in anomaly_indices:
        # Randomly choose anomaly type
        anomaly_type = np.random.choice(['price_spike', 'volume_spike', 'volatility_spike'])
        
        if anomaly_type == 'price_spike':
            # Price spike (up or down)
            direction = np.random.choice([-1, 1])
            df.iloc[idx, df.columns.get_loc('price')] *= (1 + direction * np.random.uniform(0.1, 0.3))
            
            # Update returns
            if idx > 0:
                df.iloc[idx, df.columns.get_loc('returns')] = (df.iloc[idx, df.columns.get_loc('price')] - 
                                                              df.iloc[idx-1, df.columns.get_loc('price')]) / df.iloc[idx-1, df.columns.get_loc('price')]
            if idx < n_samples - 1:
                df.iloc[idx+1, df.columns.get_loc('returns')] = (df.iloc[idx+1, df.columns.get_loc('price')] - 
                                                                df.iloc[idx, df.columns.get_loc('price')]) / df.iloc[idx, df.columns.get_loc('price')]
        
        elif anomaly_type == 'volume_spike':
            # Volume spike
            df.iloc[idx, df.columns.get_loc('volume')] *= np.random.uniform(3, 10)
        
        elif anomaly_type == 'volatility_spike':
            # Volatility spike
            df.iloc[idx, df.columns.get_loc('volatility')] *= np.random.uniform(3, 10)
    
    # Create anomaly labels
    anomalies = np.zeros(n_samples, dtype=bool)
    anomalies[anomaly_indices] = True
    
    # Drop NaN values
    df = df.dropna()
    anomalies = anomalies[:len(df)]
    
    return df, anomalies

def load_real_data(ticker='SPY', start_date='2018-01-01', end_date='2023-01-01'):
    """
    Load real financial data from Yahoo Finance.
    
    Parameters
    ----------
    ticker : str, default='SPY'
        Ticker symbol
    start_date : str, default='2018-01-01'
        Start date for data retrieval
    end_date : str, default='2023-01-01'
        End date for data retrieval
        
    Returns
    -------
    pd.DataFrame
        DataFrame containing financial data
    """
    # Download data
    data = yf.download(ticker, start=start_date, end=end_date)
    
    # Calculate returns
    data['Returns'] = data['Adj Close'].pct_change()
    
    # Calculate volatility (20-day rolling standard deviation of returns)
    data['Volatility'] = data['Returns'].rolling(window=20).std()
    
    # Calculate volume change
    data['Volume_Change'] = data['Volume'].pct_change()
    
    # Drop NaN values
    data = data.dropna()
    
    return data

def example_isolation_forest_synthetic():
    """
    Example of using Isolation Forest for anomaly detection on synthetic data.
    """
    print("\n=== Isolation Forest on Synthetic Data ===")
    
    # Generate synthetic data
    data, true_anomalies = generate_synthetic_data(n_samples=1000, anomaly_ratio=0.05)
    print(f"Generated data shape: {data.shape}")
    print(f"Number of true anomalies: {np.sum(true_anomalies)}")
    
    # Create detector
    detector = IsolationForestDetector(
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        normalize=True
    )
    
    # Fit detector
    detector.fit(data)
    
    # Detect anomalies
    anomalies = detector.detect_anomalies(data)
    
    # Calculate detection metrics
    true_positives = np.sum(anomalies & true_anomalies)
    false_positives = np.sum(anomalies & ~true_anomalies)
    false_negatives = np.sum(~anomalies & true_anomalies)
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"Number of detected anomalies: {np.sum(anomalies)}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    
    # Plot anomalies
    detector.plot_anomalies(
        X=data,
        y=true_anomalies,
        title='Isolation Forest Anomaly Detection (Synthetic Data)',
        time_index=data.index
    )
    
    return detector, data, true_anomalies, anomalies

def example_one_class_svm_synthetic():
    """
    Example of using One-Class SVM for anomaly detection on synthetic data.
    """
    print("\n=== One-Class SVM on Synthetic Data ===")
    
    # Generate synthetic data
    data, true_anomalies = generate_synthetic_data(n_samples=1000, anomaly_ratio=0.05)
    
    # Create detector
    detector = OneClassSVMDetector(
        nu=0.05,
        kernel='rbf',
        gamma='scale',
        normalize=True
    )
    
    # Fit detector
    detector.fit(data)
    
    # Detect anomalies
    anomalies = detector.detect_anomalies(data)
    
    # Calculate detection metrics
    true_positives = np.sum(anomalies & true_anomalies)
    false_positives = np.sum(anomalies & ~true_anomalies)
    false_negatives = np.sum(~anomalies & true_anomalies)
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"Number of detected anomalies: {np.sum(anomalies)}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    
    # Plot anomalies
    detector.plot_anomalies(
        X=data,
        y=true_anomalies,
        title='One-Class SVM Anomaly Detection (Synthetic Data)',
        time_index=data.index
    )
    
    return detector, data, true_anomalies, anomalies

def example_comparison_synthetic():
    """
    Example of comparing different anomaly detection methods on synthetic data.
    """
    print("\n=== Comparing Anomaly Detection Methods on Synthetic Data ===")
    
    # Generate synthetic data
    data, true_anomalies = generate_synthetic_data(n_samples=1000, anomaly_ratio=0.05)
    
    # Create detectors
    if_detector = IsolationForestDetector(
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        normalize=True
    )
    
    svm_detector = OneClassSVMDetector(
        nu=0.05,
        kernel='rbf',
        gamma='scale',
        normalize=True
    )
    
    # Fit detectors
    if_detector.fit(data)
    svm_detector.fit(data)
    
    # Detect anomalies
    if_anomalies = if_detector.detect_anomalies(data)
    svm_anomalies = svm_detector.detect_anomalies(data)
    
    # Calculate detection metrics
    methods = ['Isolation Forest', 'One-Class SVM']
    anomalies = [if_anomalies, svm_anomalies]
    metrics = []
    
    for method, method_anomalies in zip(methods, anomalies):
        true_positives = np.sum(method_anomalies & true_anomalies)
        false_positives = np.sum(method_anomalies & ~true_anomalies)
        false_negatives = np.sum(~method_anomalies & true_anomalies)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        metrics.append({
            'Method': method,
            'Detected Anomalies': np.sum(method_anomalies),
            'Precision': precision,
            'Recall': recall,
            'F1 Score': f1
        })
    
    # Print metrics
    print("\nComparison of Anomaly Detection Methods:")
    metrics_df = pd.DataFrame(metrics)
    print(metrics_df)
    
    # Plot comparison
    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    
    # Plot data
    axes[0].plot(data.index, data['price'], 'b-', label='Price')
    axes[0].set_title('Synthetic Financial Data')
    axes[0].set_ylabel('Price')
    axes[0].legend()
    axes[0].grid(True)
    
    # Plot true anomalies
    anomaly_indices = np.where(true_anomalies)[0]
    axes[0].scatter(
        data.index[anomaly_indices],
        data['price'].iloc[anomaly_indices],
        color='green',
        marker='x',
        label='True Anomalies'
    )
    
    # Plot Isolation Forest anomalies
    if_indices = np.where(if_anomalies)[0]
    axes[1].plot(data.index, data['price'], 'b-', label='Price')
    axes[1].scatter(
        data.index[if_indices],
        data['price'].iloc[if_indices],
        color='red',
        marker='o',
        label='Isolation Forest Anomalies'
    )
    axes[1].set_title('Isolation Forest Anomaly Detection')
    axes[1].set_ylabel('Price')
    axes[1].legend()
    axes[1].grid(True)
    
    # Plot One-Class SVM anomalies
    svm_indices = np.where(svm_anomalies)[0]
    axes[2].plot(data.index, data['price'], 'b-', label='Price')
    axes[2].scatter(
        data.index[svm_indices],
        data['price'].iloc[svm_indices],
        color='purple',
        marker='o',
        label='One-Class SVM Anomalies'
    )
    axes[2].set_title('One-Class SVM Anomaly Detection')
    axes[2].set_xlabel('Date')
    axes[2].set_ylabel('Price')
    axes[2].legend()
    axes[2].grid(True)
    
    plt.tight_layout()
    plt.show()
    
    return if_detector, svm_detector, data, true_anomalies

def example_real_data():
    """
    Example of using anomaly detection on real financial data.
    """
    print("\n=== Anomaly Detection on Real Financial Data ===")
    
    try:
        # Load real data
        data = load_real_data(ticker='SPY', start_date='2018-01-01', end_date='2023-01-01')
        print(f"Loaded data shape: {data.shape}")
        print(data.head())
        
        # Select features for anomaly detection
        features = data[['Adj Close', 'Returns', 'Volatility', 'Volume_Change']].copy()
        
        # Create detector
        detector = IsolationForestDetector(
            n_estimators=100,
            contamination=0.01,  # Detect 1% of points as anomalies
            random_state=42,
            normalize=True
        )
        
        # Fit detector
        detector.fit(features)
        
        # Detect anomalies
        anomalies = detector.detect_anomalies(features)
        
        print(f"Number of detected anomalies: {np.sum(anomalies)}")
        
        # Plot anomalies
        detector.plot_anomalies(
            X=features,
            title='Anomaly Detection on SPY Data',
            time_index=features.index
        )
        
        # Plot price with anomalies
        plt.figure(figsize=(12, 6))
        plt.plot(data.index, data['Adj Close'], 'b-', label='SPY Price')
        
        # Highlight anomalies
        anomaly_indices = np.where(anomalies)[0]
        plt.scatter(
            data.index[anomaly_indices],
            data['Adj Close'].iloc[anomaly_indices],
            color='red',
            marker='o',
            label='Anomalies'
        )
        
        plt.title('SPY Price with Detected Anomalies')
        plt.xlabel('Date')
        plt.ylabel('Price')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        
        return detector, data, anomalies
    
    except Exception as e:
        logger.error(f"Error loading real data: {e}")
        print(f"Error loading real data: {e}")
        print("Skipping real data example.")
        return None, None, None

def example_time_aware_anomaly_detection():
    """
    Example of using time-aware anomaly detection.
    """
    print("\n=== Time-Aware Anomaly Detection ===")
    
    # Generate synthetic data
    data, true_anomalies = generate_synthetic_data(n_samples=1000, anomaly_ratio=0.05)
    
    # Create standard detector
    standard_detector = IsolationForestDetector(
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        normalize=True,
        time_aware=False
    )
    
    # Create time-aware detector
    time_aware_detector = IsolationForestDetector(
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        normalize=True,
        time_aware=True,
        time_window=30  # 30-day window
    )
    
    # Fit detectors
    standard_detector.fit(data)
    time_aware_detector.fit(data)
    
    # Detect anomalies
    standard_anomalies = standard_detector.detect_anomalies(data)
    time_aware_anomalies = time_aware_detector.detect_anomalies(data)
    
    # Calculate detection metrics
    methods = ['Standard Isolation Forest', 'Time-Aware Isolation Forest']
    anomalies = [standard_anomalies, time_aware_anomalies]
    metrics = []
    
    for method, method_anomalies in zip(methods, anomalies):
        true_positives = np.sum(method_anomalies & true_anomalies)
        false_positives = np.sum(method_anomalies & ~true_anomalies)
        false_negatives = np.sum(~method_anomalies & true_anomalies)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        metrics.append({
            'Method': method,
            'Detected Anomalies': np.sum(method_anomalies),
            'Precision': precision,
            'Recall': recall,
            'F1 Score': f1
        })
    
    # Print metrics
    print("\nComparison of Standard vs. Time-Aware Anomaly Detection:")
    metrics_df = pd.DataFrame(metrics)
    print(metrics_df)
    
    # Plot comparison
    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    
    # Plot data
    axes[0].plot(data.index, data['price'], 'b-', label='Price')
    axes[0].set_title('Synthetic Financial Data')
    axes[0].set_ylabel('Price')
    axes[0].legend()
    axes[0].grid(True)
    
    # Plot true anomalies
    anomaly_indices = np.where(true_anomalies)[0]
    axes[0].scatter(
        data.index[anomaly_indices],
        data['price'].iloc[anomaly_indices],
        color='green',
        marker='x',
        label='True Anomalies'
    )
    
    # Plot Standard Isolation Forest anomalies
    std_indices = np.where(standard_anomalies)[0]
    axes[1].plot(data.index, data['price'], 'b-', label='Price')
    axes[1].scatter(
        data.index[std_indices],
        data['price'].iloc[std_indices],
        color='red',
        marker='o',
        label='Standard Isolation Forest Anomalies'
    )
    axes[1].set_title('Standard Isolation Forest Anomaly Detection')
    axes[1].set_ylabel('Price')
    axes[1].legend()
    axes[1].grid(True)
    
    # Plot Time-Aware Isolation Forest anomalies
    time_indices = np.where(time_aware_anomalies)[0]
    axes[2].plot(data.index, data['price'], 'b-', label='Price')
    axes[2].scatter(
        data.index[time_indices],
        data['price'].iloc[time_indices],
        color='purple',
        marker='o',
        label='Time-Aware Isolation Forest Anomalies'
    )
    axes[2].set_title('Time-Aware Isolation Forest Anomaly Detection')
    axes[2].set_xlabel('Date')
    axes[2].set_ylabel('Price')
    axes[2].legend()
    axes[2].grid(True)
    
    plt.tight_layout()
    plt.show()
    
    return standard_detector, time_aware_detector, data, true_anomalies

def example_convenience_functions():
    """
    Example of using convenience functions for anomaly detection.
    """
    print("\n=== Using Convenience Functions for Anomaly Detection ===")
    
    # Generate synthetic data
    data, true_anomalies = generate_synthetic_data(n_samples=1000, anomaly_ratio=0.05)
    
    # Detect anomalies using Isolation Forest convenience function
    if_anomalies, if_detector = if_detect_anomalies(
        X=data,
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        normalize=True,
        return_detector=True
    )
    
    # Detect anomalies using One-Class SVM convenience function
    svm_anomalies, svm_detector = svm_detect_anomalies(
        X=data,
        nu=0.05,
        kernel='rbf',
        gamma='scale',
        normalize=True,
        return_detector=True
    )
    
    # Calculate detection metrics
    methods = ['Isolation Forest', 'One-Class SVM']
    anomalies = [if_anomalies, svm_anomalies]
    metrics = []
    
    for method, method_anomalies in zip(methods, anomalies):
        true_positives = np.sum(method_anomalies & true_anomalies)
        false_positives = np.sum(method_anomalies & ~true_anomalies)
        false_negatives = np.sum(~method_anomalies & true_anomalies)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        metrics.append({
            'Method': method,
            'Detected Anomalies': np.sum(method_anomalies),
            'Precision': precision,
            'Recall': recall,
            'F1 Score': f1
        })
    
    # Print metrics
    print("\nComparison of Anomaly Detection Methods (Convenience Functions):")
    metrics_df = pd.DataFrame(metrics)
    print(metrics_df)
    
    # Plot anomalies using convenience function
    from advanced_trading.models.anomaly.isolation_forest import plot_anomalies
    
    plot_anomalies(
        X=data,
        anomalies=if_anomalies,
        title='Anomaly Detection using Convenience Functions',
        time_index=data.index
    )
    
    return if_detector, svm_detector, data, true_anomalies

def main():
    """Run all examples."""
    try:
        # Run examples
        example_isolation_forest_synthetic()
        example_one_class_svm_synthetic()
        example_comparison_synthetic()
        example_real_data()
        example_time_aware_anomaly_detection()
        example_convenience_functions()
    except Exception as e:
        logger.exception(f"Error running examples: {e}")

if __name__ == "__main__":
    main() 