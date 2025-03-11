"""
One-Class SVM Anomaly Detector
----------------------------
This module provides an implementation of the One-Class SVM algorithm for
anomaly detection in financial time series data.

One-Class SVM is an unsupervised algorithm that learns a decision boundary
that encompasses the normal data points. Points that fall outside this boundary
are classified as anomalies.

This implementation includes:
1. Standard One-Class SVM for point anomalies
2. Time-aware One-Class SVM for temporal anomalies
3. Visualization tools for anomaly analysis
4. Integration with the ML Ensemble framework
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict, Union, Optional, Tuple, Any
import logging
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
import datetime

# Configure logging
logger = logging.getLogger(__name__)

class OneClassSVMDetector:
    """
    A class for detecting anomalies in financial time series data using the One-Class SVM algorithm.
    
    This class provides methods for:
    - Training a One-Class SVM model on financial data
    - Detecting anomalies in new data
    - Scoring data points based on their anomaly likelihood
    - Visualizing anomalies in time series data
    - Analyzing anomaly patterns
    """
    
    def __init__(
        self,
        kernel: str = 'rbf',
        nu: float = 0.1,
        gamma: Union[str, float] = 'scale',
        degree: int = 3,
        coef0: float = 0.0,
        tol: float = 1e-3,
        shrinking: bool = True,
        cache_size: float = 200,
        max_iter: int = -1,
        normalize: bool = True,
        time_aware: bool = False,
        time_window: Optional[int] = None,
        verbose: bool = False
    ):
        """
        Initialize the One-Class SVM anomaly detector.
        
        Parameters
        ----------
        kernel : str, default='rbf'
            Specifies the kernel type to be used in the algorithm.
            Options: 'linear', 'poly', 'rbf', 'sigmoid', 'precomputed'
        nu : float, default=0.1
            An upper bound on the fraction of training errors and a lower bound of the
            fraction of support vectors. Should be in the interval (0, 1].
        gamma : {'scale', 'auto'} or float, default='scale'
            Kernel coefficient for 'rbf', 'poly' and 'sigmoid'.
        degree : int, default=3
            Degree of the polynomial kernel function ('poly').
        coef0 : float, default=0.0
            Independent term in kernel function. It is only significant in 'poly' and 'sigmoid'.
        tol : float, default=1e-3
            Tolerance for stopping criterion.
        shrinking : bool, default=True
            Whether to use the shrinking heuristic.
        cache_size : float, default=200
            Specify the size of the kernel cache (in MB).
        max_iter : int, default=-1
            Hard limit on iterations within solver, or -1 for no limit.
        normalize : bool, default=True
            Whether to normalize the input data.
        time_aware : bool, default=False
            Whether to use time-aware anomaly detection.
        time_window : int, optional
            The size of the time window for time-aware anomaly detection.
            Required if time_aware=True.
        verbose : bool, default=False
            Enable verbose output.
        """
        self.kernel = kernel
        self.nu = nu
        self.gamma = gamma
        self.degree = degree
        self.coef0 = coef0
        self.tol = tol
        self.shrinking = shrinking
        self.cache_size = cache_size
        self.max_iter = max_iter
        self.normalize = normalize
        self.time_aware = time_aware
        self.time_window = time_window
        self.verbose = verbose
        
        # Initialize model
        self.model = None
        self.scaler = StandardScaler() if normalize else None
        
        # Validate parameters
        self._validate_parameters()
        
        logger.info(f"Initialized OneClassSVMDetector with kernel={kernel}, nu={nu}, "
                   f"time_aware={time_aware}")
    
    def _validate_parameters(self):
        """Validate model parameters."""
        if self.time_aware and self.time_window is None:
            raise ValueError("time_window must be specified when time_aware=True")
        
        if self.nu <= 0 or self.nu > 1:
            raise ValueError("nu must be in (0, 1]")
    
    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Union[pd.Series, np.ndarray]] = None) -> 'OneClassSVMDetector':
        """
        Fit the One-Class SVM model to the data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        y : pd.Series or np.ndarray, optional
            Not used, present for API consistency.
            
        Returns
        -------
        self : OneClassSVMDetector
            The fitted detector.
        """
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            X_data = self.scaler.fit_transform(X_data)
        
        # Create and fit model
        if self.time_aware:
            # Time-aware anomaly detection
            self._fit_time_aware(X_data)
        else:
            # Standard One-Class SVM
            self.model = OneClassSVM(
                kernel=self.kernel,
                nu=self.nu,
                gamma=self.gamma,
                degree=self.degree,
                coef0=self.coef0,
                tol=self.tol,
                shrinking=self.shrinking,
                cache_size=self.cache_size,
                max_iter=self.max_iter,
                verbose=self.verbose
            )
            self.model.fit(X_data)
        
        logger.info(f"Fitted OneClassSVMDetector to data with shape {X_data.shape}")
        return self
    
    def _fit_time_aware(self, X: np.ndarray):
        """
        Fit a time-aware One-Class SVM model.
        
        This method creates a model that is aware of the temporal structure of the data
        by using a sliding window approach.
        
        Parameters
        ----------
        X : np.ndarray
            The input data.
        """
        if self.time_window is None or self.time_window <= 0:
            raise ValueError("time_window must be a positive integer")
        
        # Create a list to store models for each time window
        self.time_models = []
        
        # Fit a model for each time window
        for i in range(0, len(X) - self.time_window + 1):
            window_data = X[i:i+self.time_window]
            model = OneClassSVM(
                kernel=self.kernel,
                nu=self.nu,
                gamma=self.gamma,
                degree=self.degree,
                coef0=self.coef0,
                tol=self.tol,
                shrinking=self.shrinking,
                cache_size=self.cache_size,
                max_iter=self.max_iter,
                verbose=self.verbose
            )
            model.fit(window_data)
            self.time_models.append(model)
        
        logger.info(f"Fitted {len(self.time_models)} time-aware One-Class SVM models")
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Predict if observations are anomalies.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
            
        Returns
        -------
        np.ndarray
            Returns 1 for normal observations and -1 for anomalies.
        """
        # Check if model is fitted
        if self.model is None and not self.time_aware:
            raise ValueError("Model not fitted. Call fit() first.")
        if self.time_aware and not hasattr(self, 'time_models'):
            raise ValueError("Time-aware model not fitted. Call fit() first.")
        
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            X_data = self.scaler.transform(X_data)
        
        # Make predictions
        if self.time_aware:
            return self._predict_time_aware(X_data)
        else:
            return self.model.predict(X_data)
    
    def _predict_time_aware(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using the time-aware One-Class SVM model.
        
        Parameters
        ----------
        X : np.ndarray
            The input data.
            
        Returns
        -------
        np.ndarray
            Returns 1 for normal observations and -1 for anomalies.
        """
        if len(X) < self.time_window:
            raise ValueError(f"Input data must have at least {self.time_window} observations for time-aware prediction")
        
        # Initialize predictions
        predictions = np.ones(len(X))
        
        # Make predictions for each time window
        for i in range(len(self.time_models)):
            if i + self.time_window <= len(X):
                window_data = X[i:i+self.time_window]
                window_pred = self.time_models[i].predict(window_data)
                
                # Update predictions
                predictions[i:i+self.time_window] = np.minimum(predictions[i:i+self.time_window], window_pred)
        
        return predictions
    
    def decision_function(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Compute the anomaly score of each sample using the fitted detector.
        
        The anomaly score of a sample is the signed distance to the separating hyperplane.
        The lower, the more abnormal.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
            
        Returns
        -------
        np.ndarray
            The anomaly score of each sample. The lower, the more abnormal.
        """
        # Check if model is fitted
        if self.model is None and not self.time_aware:
            raise ValueError("Model not fitted. Call fit() first.")
        if self.time_aware and not hasattr(self, 'time_models'):
            raise ValueError("Time-aware model not fitted. Call fit() first.")
        
        # Convert to numpy array if DataFrame
        X_data = X.values if isinstance(X, pd.DataFrame) else X
        
        # Normalize data if required
        if self.normalize and self.scaler is not None:
            X_data = self.scaler.transform(X_data)
        
        # Compute anomaly scores
        if self.time_aware:
            return self._decision_function_time_aware(X_data)
        else:
            return self.model.decision_function(X_data)
    
    def _decision_function_time_aware(self, X: np.ndarray) -> np.ndarray:
        """
        Compute anomaly scores using the time-aware One-Class SVM model.
        
        Parameters
        ----------
        X : np.ndarray
            The input data.
            
        Returns
        -------
        np.ndarray
            The anomaly score of each sample. The lower, the more abnormal.
        """
        if len(X) < self.time_window:
            raise ValueError(f"Input data must have at least {self.time_window} observations for time-aware prediction")
        
        # Initialize scores
        scores = np.zeros(len(X))
        counts = np.zeros(len(X))
        
        # Compute scores for each time window
        for i in range(len(self.time_models)):
            if i + self.time_window <= len(X):
                window_data = X[i:i+self.time_window]
                window_scores = self.time_models[i].decision_function(window_data)
                
                # Update scores
                scores[i:i+self.time_window] += window_scores
                counts[i:i+self.time_window] += 1
        
        # Average scores
        scores = np.divide(scores, counts, out=np.zeros_like(scores), where=counts != 0)
        
        return scores
    
    def detect_anomalies(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        threshold: Optional[float] = None,
        return_scores: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Detect anomalies in the data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        threshold : float, optional
            The threshold for anomaly detection. If None, uses the model's threshold.
        return_scores : bool, default=False
            Whether to return anomaly scores along with predictions.
            
        Returns
        -------
        Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]
            Boolean array of anomalies (True for anomalies), or tuple of (anomalies, scores).
        """
        # Get predictions and scores
        predictions = self.predict(X)
        
        # Convert to boolean array (True for anomalies)
        anomalies = predictions == -1
        
        if return_scores:
            scores = self.decision_function(X)
            return anomalies, scores
        else:
            return anomalies
    
    def plot_anomalies(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
        figsize: Tuple[int, int] = (12, 6),
        title: str = 'Anomaly Detection Results',
        feature_names: Optional[List[str]] = None,
        time_index: Optional[pd.DatetimeIndex] = None,
        save_path: Optional[str] = None
    ):
        """
        Plot the anomalies detected in the data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        y : pd.Series or np.ndarray, optional
            The true anomaly labels, if available.
        figsize : Tuple[int, int], default=(12, 6)
            Figure size.
        title : str, default='Anomaly Detection Results'
            Plot title.
        feature_names : List[str], optional
            Names of the features. If None and X is a DataFrame, uses column names.
        time_index : pd.DatetimeIndex, optional
            Time index for the data. If None and X is a DataFrame, uses the index.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        # Get data
        if isinstance(X, pd.DataFrame):
            data = X.copy()
            if feature_names is None:
                feature_names = data.columns.tolist()
            if time_index is None and isinstance(data.index, pd.DatetimeIndex):
                time_index = data.index
        else:
            data = X.copy()
            if feature_names is None:
                feature_names = [f'Feature {i}' for i in range(data.shape[1])]
        
        # Detect anomalies
        anomalies, scores = self.detect_anomalies(data, return_scores=True)
        
        # Create figure
        fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=True)
        
        # Plot data and anomalies
        x_values = np.arange(len(data)) if time_index is None else time_index
        
        # Plot the first feature or the mean of all features
        if data.shape[1] == 1:
            y_values = data.iloc[:, 0] if isinstance(data, pd.DataFrame) else data[:, 0]
            feature_name = feature_names[0]
        else:
            # Use the mean of all features
            y_values = data.mean(axis=1) if isinstance(data, pd.DataFrame) else data.mean(axis=1)
            feature_name = 'Mean of all features'
        
        # Plot data
        axes[0].plot(x_values, y_values, 'b-', label=feature_name)
        
        # Highlight anomalies
        if np.any(anomalies):
            anomaly_indices = np.where(anomalies)[0]
            axes[0].scatter(
                x_values[anomaly_indices],
                y_values[anomaly_indices],
                color='red',
                marker='o',
                label='Anomalies'
            )
        
        # Plot true anomalies if available
        if y is not None:
            true_anomalies = y == -1 if np.any(y == -1) else y == 1
            if np.any(true_anomalies):
                true_anomaly_indices = np.where(true_anomalies)[0]
                axes[0].scatter(
                    x_values[true_anomaly_indices],
                    y_values[true_anomaly_indices],
                    color='green',
                    marker='x',
                    label='True Anomalies'
                )
        
        axes[0].set_title(title)
        axes[0].set_ylabel(feature_name)
        axes[0].legend()
        axes[0].grid(True)
        
        # Plot anomaly scores
        axes[1].plot(x_values, scores, 'g-', label='Anomaly Score')
        
        # Highlight anomalies
        if np.any(anomalies):
            axes[1].scatter(
                x_values[anomaly_indices],
                scores[anomaly_indices],
                color='red',
                marker='o',
                label='Anomalies'
            )
        
        # Add threshold line if available
        if hasattr(self.model, 'offset_') and not self.time_aware:
            threshold = -self.model.offset_
            axes[1].axhline(
                y=threshold,
                color='r',
                linestyle='--',
                label=f'Threshold: {threshold:.3f}'
            )
        
        axes[1].set_xlabel('Time' if time_index is not None else 'Sample')
        axes[1].set_ylabel('Anomaly Score')
        axes[1].legend()
        axes[1].grid(True)
        
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved anomaly plot to {save_path}")
        
        plt.show()
    
    def save(self, filepath: str):
        """
        Save the detector to a file.
        
        Parameters
        ----------
        filepath : str
            Path to save the detector.
        """
        import joblib
        
        # Create a dictionary with all the necessary components
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'params': {
                'kernel': self.kernel,
                'nu': self.nu,
                'gamma': self.gamma,
                'degree': self.degree,
                'coef0': self.coef0,
                'tol': self.tol,
                'shrinking': self.shrinking,
                'cache_size': self.cache_size,
                'max_iter': self.max_iter,
                'normalize': self.normalize,
                'time_aware': self.time_aware,
                'time_window': self.time_window,
                'verbose': self.verbose
            }
        }
        
        # Add time models if time-aware
        if self.time_aware and hasattr(self, 'time_models'):
            model_data['time_models'] = self.time_models
        
        # Save to file
        joblib.dump(model_data, filepath)
        logger.info(f"Saved OneClassSVMDetector to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'OneClassSVMDetector':
        """
        Load a detector from a file.
        
        Parameters
        ----------
        filepath : str
            Path to the saved detector.
            
        Returns
        -------
        OneClassSVMDetector
            The loaded detector.
        """
        import joblib
        
        # Load from file
        model_data = joblib.load(filepath)
        
        # Create a new instance with the saved parameters
        detector = cls(**model_data['params'])
        
        # Restore model components
        detector.model = model_data['model']
        detector.scaler = model_data['scaler']
        
        # Restore time models if time-aware
        if detector.time_aware and 'time_models' in model_data:
            detector.time_models = model_data['time_models']
        
        logger.info(f"Loaded OneClassSVMDetector from {filepath}")
        return detector


# Convenience functions

def detect_anomalies(
    X: Union[pd.DataFrame, np.ndarray],
    nu: float = 0.1,
    kernel: str = 'rbf',
    gamma: Union[str, float] = 'scale',
    normalize: bool = True,
    time_aware: bool = False,
    time_window: Optional[int] = None,
    return_detector: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, 'OneClassSVMDetector']]:
    """
    Detect anomalies in the data using One-Class SVM.
    
    Parameters
    ----------
    X : pd.DataFrame or np.ndarray
        The input data. If a DataFrame, the index is assumed to be the time index.
    nu : float, default=0.1
        An upper bound on the fraction of training errors and a lower bound of the
        fraction of support vectors. Should be in the interval (0, 1].
    kernel : str, default='rbf'
        Specifies the kernel type to be used in the algorithm.
        Options: 'linear', 'poly', 'rbf', 'sigmoid', 'precomputed'
    gamma : {'scale', 'auto'} or float, default='scale'
        Kernel coefficient for 'rbf', 'poly' and 'sigmoid'.
    normalize : bool, default=True
        Whether to normalize the input data.
    time_aware : bool, default=False
        Whether to use time-aware anomaly detection.
    time_window : int, optional
        The size of the time window for time-aware anomaly detection.
    return_detector : bool, default=False
        Whether to return the detector along with the anomalies.
        
    Returns
    -------
    Union[np.ndarray, Tuple[np.ndarray, OneClassSVMDetector]]
        Boolean array of anomalies (True for anomalies), or tuple of (anomalies, detector).
    """
    # Create and fit detector
    detector = OneClassSVMDetector(
        nu=nu,
        kernel=kernel,
        gamma=gamma,
        normalize=normalize,
        time_aware=time_aware,
        time_window=time_window
    )
    
    detector.fit(X)
    
    # Detect anomalies
    anomalies = detector.detect_anomalies(X)
    
    if return_detector:
        return anomalies, detector
    else:
        return anomalies 