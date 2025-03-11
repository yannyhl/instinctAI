"""
Time Series Cross-Validation Example
-----------------------------------
This example demonstrates the use of the TimeSeriesCV class for proper time series cross-validation.

The example shows:
1. How to create different types of time series CV splits (sliding, expanding, anchored)
2. How to visualize the splits on a dataset
3. How to use the cross-validation with an ML model
4. How to evaluate results properly respecting time dependencies
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import logging
import yfinance as yf
from datetime import datetime, timedelta

# Import our TimeSeriesCV module
from advanced_trading.utils.cross_validation.time_series_cv import (
    TimeSeriesCV, purged_cross_val_score, plot_purged_cv_results
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_example_data(ticker: str = 'SPY', period: str = '3y') -> pd.DataFrame:
    """
    Download financial data for example using yfinance.
    
    Parameters:
    -----------
    ticker : str
        Ticker symbol to download
    period : str
        Period to download (e.g. '1y', '2y', '5y')
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with OHLCV data
    """
    logger.info(f"Downloading {ticker} data for {period}")
    data = yf.download(ticker, period=period)
    
    # Add some basic features
    data['Returns'] = data['Close'].pct_change()
    data['Target'] = data['Returns'].shift(-1)  # Next day returns as target
    data['MA_5'] = data['Close'].rolling(5).mean()
    data['MA_20'] = data['Close'].rolling(20).mean()
    data['MA_Ratio'] = data['MA_5'] / data['MA_20']
    data['Volatility'] = data['Returns'].rolling(20).std()
    
    # Drop NaN values
    data.dropna(inplace=True)
    
    logger.info(f"Downloaded {len(data)} rows of data")
    return data

def demonstrate_cv_splits():
    """Demonstrate different types of cross-validation splits."""
    # Download example data
    data = download_example_data()
    
    # Create different CV splitters
    cv_types = {
        'Sliding Window': TimeSeriesCV(cv_method='sliding', n_splits=5, 
                                      train_size=60, test_size=20, step_size=20),
        'Expanding Window': TimeSeriesCV(cv_method='expanding', n_splits=5, 
                                        train_size=60, test_size=20, step_size=20),
        'Anchored Window': TimeSeriesCV(cv_method='anchored', n_splits=5, 
                                       train_size=60, test_size=20, step_size=20),
        'Purged Sliding Window': TimeSeriesCV(cv_method='sliding', n_splits=5, 
                                            train_size=60, test_size=20, step_size=20,
                                            purge_size=5, embargo_size=5)
    }
    
    # Plot the splits
    for name, cv in cv_types.items():
        logger.info(f"Demonstrating {name} cross-validation")
        
        # Plot the indices
        fig = cv.plot_cv_indices(data)
        plt.suptitle(f"{name} - Index Plot")
        plt.tight_layout()
        plt.show()
        
        # Plot the dates
        fig = cv.plot_cv_dates(data)
        plt.suptitle(f"{name} - Date Plot")
        plt.tight_layout()
        plt.show()

def evaluate_model_with_cv():
    """Evaluate a simple model using time series cross-validation."""
    # Download example data
    data = download_example_data(period='5y')
    
    # Create features and target
    X = data[['MA_Ratio', 'Volatility']].copy()
    y = data['Target'].copy()
    
    # Create different CV splitters
    cv_types = {
        'Standard CV': TimeSeriesCV(cv_method='sliding', n_splits=5, 
                                   train_size=0.6, test_size=0.2, step_size=0.1),
        'Purged CV': TimeSeriesCV(cv_method='sliding', n_splits=5, 
                                 train_size=0.6, test_size=0.2, step_size=0.1,
                                 purge_size=0.05, embargo_size=0.05)
    }
    
    # Compare model evaluation with different CV methods
    for name, cv in cv_types.items():
        logger.info(f"Evaluating model with {name}")
        
        # Create and evaluate model
        model = LinearRegression()
        scores = purged_cross_val_score(model, X, y, cv=cv, scoring='r2')
        
        logger.info(f"{name} - R² scores: {scores}")
        logger.info(f"{name} - Mean R²: {np.mean(scores):.4f}, Std: {np.std(scores):.4f}")
        
        # Train on the first fold
        first_split = next(cv.split(X, y))
        train_idx, test_idx = first_split
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        
        # Plot predictions
        plt.figure(figsize=(12, 6))
        plt.plot(data.index[test_idx], y_test.values, label='Actual')
        plt.plot(data.index[test_idx], y_pred, label='Predicted')
        plt.title(f"{name} - Test Set Predictions")
        plt.xlabel('Date')
        plt.ylabel('Target (Next Day Returns)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

def parameter_tuning_example():
    """Demonstrate parameter tuning with time series cross-validation."""
    # Download example data
    data = download_example_data()
    
    # Create features and target
    X = data[['MA_Ratio', 'Volatility']].copy()
    y = data['Target'].copy()
    
    # Create CV splitter
    cv = TimeSeriesCV(cv_method='sliding', n_splits=5, 
                      train_size=0.6, test_size=0.2, step_size=0.1,
                      purge_size=0.05, embargo_size=0.05)
    
    # Parameter grid for Ridge regression
    from sklearn.linear_model import Ridge
    alphas = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
    
    # Store results
    cv_results = {}
    
    # Evaluate each parameter
    for alpha in alphas:
        logger.info(f"Evaluating Ridge regression with alpha={alpha}")
        model = Ridge(alpha=alpha)
        scores = purged_cross_val_score(model, X, y, cv=cv, scoring='r2')
        cv_results[f'alpha={alpha}'] = scores
        logger.info(f"Alpha={alpha} - Mean R²: {np.mean(scores):.4f}, Std: {np.std(scores):.4f}")
    
    # Plot results
    fig = plot_purged_cv_results(cv_results)
    plt.title("Ridge Regression Alpha Parameter Tuning")
    plt.tight_layout()
    plt.show()
    
    # Find best parameter
    mean_scores = {param: np.mean(scores) for param, scores in cv_results.items()}
    best_param = max(mean_scores.items(), key=lambda x: x[1])[0]
    logger.info(f"Best parameter: {best_param} with mean R²: {mean_scores[best_param]:.4f}")

def main():
    """Execute the TimeSeriesCV examples."""
    try:
        logger.info("Starting TimeSeriesCV example")
        
        # Demonstrate different CV splits
        demonstrate_cv_splits()
        
        # Evaluate model with CV
        evaluate_model_with_cv()
        
        # Parameter tuning example
        parameter_tuning_example()
        
        logger.info("TimeSeriesCV example completed successfully")
    except Exception as e:
        logger.error(f"Error in TimeSeriesCV example: {e}", exc_info=True)

if __name__ == "__main__":
    main() 