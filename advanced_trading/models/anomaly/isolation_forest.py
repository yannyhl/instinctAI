"""
Isolation Forest Anomaly Detector
-------------------------------
This module provides an implementation of the Isolation Forest algorithm for
anomaly detection in financial time series data.

The Isolation Forest algorithm isolates observations by randomly selecting a feature
and then randomly selecting a split value between the maximum and minimum values
of the selected feature. This process is repeated recursively until all observations
are isolated. Anomalies are observations that require fewer splits to isolate.

This implementation includes:
1. Standard Isolation Forest for point anomalies
2. Time-aware Isolation Forest for temporal anomalies
3. Visualization tools for anomaly analysis
4. Integration with the ML Ensemble framework
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict, Union, Optional, Tuple, Any
import logging
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import datetime

# Configure logging
logger = logging.getLogger(__name__)

class IsolationForestDetector:
    """
    A class for detecting anomalies in financial time series data using the Isolation Forest algorithm.
    
    This class provides methods for:
    - Training an Isolation Forest model on financial data
    - Detecting anomalies in new data
    - Scoring data points based on their anomaly likelihood
    - Visualizing anomalies in time series data
    - Analyzing anomaly patterns
    """
    
    def __init__(
        self,
        n_estimators: int = 100,
        max_samples: Union[int, str] = 'auto',
        contamination: Union[float, str] = 'auto',
        max_features: Union[int, float] = 1.0,
        bootstrap: bool = False,
        n_jobs: Optional[int] = None,
        random_state: Optional[int] = None,
        normalize: bool = True,
        time_aware: bool = False,
        time_window: Optional[int] = None,
        verbose: int = 0
    ):
        """
        Initialize the Isolation Forest anomaly detector.
        
        Parameters
        ----------
        n_estimators : int, default=100
            The number of base estimators in the ensemble.
        max_samples : int or str, default='auto'
            The number of samples to draw from X to train each base estimator.
            If 'auto', max_samples=min(256, n_samples).
        contamination : float or str, default='auto'
            The proportion of outliers in the data set. Used to define the threshold.
            If 'auto', the threshold is determined automatically.
        max_features : int or float, default=1.0
            The number of features to draw from X to train each base estimator.
        bootstrap : bool, default=False
            Whether samples are drawn with replacement.
        n_jobs : int, optional
            The number of jobs to run in parallel. None means 1.
        random_state : int, optional
            Random state for reproducibility.
        normalize : bool, default=True
            Whether to normalize the input data.
        time_aware : bool, default=False
            Whether to use time-aware anomaly detection.
        time_window : int, optional
            The size of the time window for time-aware anomaly detection.
            Required if time_aware=True.
        verbose : int, default=0
            Controls the verbosity of the tree building process.
        """
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self.max_features = max_features
        self.bootstrap = bootstrap
        self.n_jobs = n_jobs
        self.random_state = random_state
        self.normalize = normalize
        self.time_aware = time_aware
        self.time_window = time_window
        self.verbose = verbose
        
        # Initialize model
        self.model = None
        self.scaler = StandardScaler() if normalize else None
        
        # Validate parameters
        self._validate_parameters()
        
        logger.info(f"Initialized IsolationForestDetector with n_estimators={n_estimators}, "
                   f"time_aware={time_aware}")
    
    def _validate_parameters(self):
        """Validate model parameters."""
        if self.time_aware and self.time_window is None:
            raise ValueError("time_window must be specified when time_aware=True")
        
        if self.contamination != 'auto' and (self.contamination <= 0 or self.contamination >= 0.5):
            raise ValueError("contamination must be in (0, 0.5)")
    
    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Union[pd.Series, np.ndarray]] = None) -> 'IsolationForestDetector':
        """
        Fit the Isolation Forest model to the data.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
        y : pd.Series or np.ndarray, optional
            Not used, present for API consistency.
            
        Returns
        -------
        self : IsolationForestDetector
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
            # Standard Isolation Forest
            self.model = IsolationForest(
                n_estimators=self.n_estimators,
                max_samples=self.max_samples,
                contamination=self.contamination,
                max_features=self.max_features,
                bootstrap=self.bootstrap,
                n_jobs=self.n_jobs,
                random_state=self.random_state,
                verbose=self.verbose
            )
            self.model.fit(X_data)
        
        logger.info(f"Fitted IsolationForestDetector to data with shape {X_data.shape}")
        return self
    
    def _fit_time_aware(self, X: np.ndarray):
        """
        Fit a time-aware Isolation Forest model.
        
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
            model = IsolationForest(
                n_estimators=self.n_estimators,
                max_samples=self.max_samples,
                contamination=self.contamination,
                max_features=self.max_features,
                bootstrap=self.bootstrap,
                n_jobs=self.n_jobs,
                random_state=self.random_state,
                verbose=self.verbose
            )
            model.fit(window_data)
            self.time_models.append(model)
        
        logger.info(f"Fitted {len(self.time_models)} time-aware Isolation Forest models")
    
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
        Make predictions using the time-aware Isolation Forest model.
        
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
        
        The anomaly score of a sample is the average path length to isolate the sample
        over the trees in the forest. The lower, the more abnormal.
        
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
        Compute anomaly scores using the time-aware Isolation Forest model.
        
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
    
    def score_samples(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Compute the anomaly score of each sample using the fitted detector.
        
        The anomaly score of a sample is the average path length to isolate the sample
        over the trees in the forest. The higher, the more normal.
        
        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            The input data. If a DataFrame, the index is assumed to be the time index.
            
        Returns
        -------
        np.ndarray
            The anomaly score of each sample. The higher, the more normal.
        """
        # The score_samples method returns the opposite of decision_function
        return -self.decision_function(X)
    
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
        if hasattr(self.model, 'threshold_') and not self.time_aware:
            axes[1].axhline(
                y=self.model.threshold_,
                color='r',
                linestyle='--',
                label=f'Threshold: {self.model.threshold_:.3f}'
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
                'n_estimators': self.n_estimators,
                'max_samples': self.max_samples,
                'contamination': self.contamination,
                'max_features': self.max_features,
                'bootstrap': self.bootstrap,
                'n_jobs': self.n_jobs,
                'random_state': self.random_state,
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
        logger.info(f"Saved IsolationForestDetector to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'IsolationForestDetector':
        """
        Load a detector from a file.
        
        Parameters
        ----------
        filepath : str
            Path to the saved detector.
            
        Returns
        -------
        IsolationForestDetector
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
        
        logger.info(f"Loaded IsolationForestDetector from {filepath}")
        return detector


# Convenience functions

def detect_anomalies(
    X: Union[pd.DataFrame, np.ndarray],
    n_estimators: int = 100,
    contamination: Union[float, str] = 'auto',
    random_state: Optional[int] = None,
    normalize: bool = True,
    time_aware: bool = False,
    time_window: Optional[int] = None,
    return_detector: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, 'IsolationForestDetector']]:
    """
    Detect anomalies in the data using Isolation Forest.
    
    Parameters
    ----------
    X : pd.DataFrame or np.ndarray
        The input data. If a DataFrame, the index is assumed to be the time index.
    n_estimators : int, default=100
        The number of base estimators in the ensemble.
    contamination : float or str, default='auto'
        The proportion of outliers in the data set. Used to define the threshold.
    random_state : int, optional
        Random state for reproducibility.
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
    Union[np.ndarray, Tuple[np.ndarray, IsolationForestDetector]]
        Boolean array of anomalies (True for anomalies), or tuple of (anomalies, detector).
    """
    # Create and fit detector
    detector = IsolationForestDetector(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
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


def plot_anomalies(
    X: Union[pd.DataFrame, np.ndarray],
    anomalies: Optional[np.ndarray] = None,
    detector: Optional[IsolationForestDetector] = None,
    figsize: Tuple[int, int] = (12, 6),
    title: str = 'Anomaly Detection Results',
    feature_names: Optional[List[str]] = None,
    time_index: Optional[pd.DatetimeIndex] = None,
    save_path: Optional[str] = None
):
    """
    Plot anomalies in the data.
    
    Parameters
    ----------
    X : pd.DataFrame or np.ndarray
        The input data. If a DataFrame, the index is assumed to be the time index.
    anomalies : np.ndarray, optional
        Boolean array of anomalies (True for anomalies). If None, detector must be provided.
    detector : IsolationForestDetector, optional
        Fitted detector to use for detecting anomalies. If None, anomalies must be provided.
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
    if anomalies is None and detector is None:
        raise ValueError("Either anomalies or detector must be provided")
    
    if detector is not None:
        detector.plot_anomalies(
            X=X,
            figsize=figsize,
            title=title,
            feature_names=feature_names,
            time_index=time_index,
            save_path=save_path
        )
    else:
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
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
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
        ax.plot(x_values, y_values, 'b-', label=feature_name)
        
        # Highlight anomalies
        if np.any(anomalies):
            anomaly_indices = np.where(anomalies)[0]
            ax.scatter(
                x_values[anomaly_indices],
                y_values[anomaly_indices],
                color='red',
                marker='o',
                label='Anomalies'
            )
        
        ax.set_title(title)
        ax.set_xlabel('Time' if time_index is not None else 'Sample')
        ax.set_ylabel(feature_name)
        ax.legend()
        ax.grid(True)
        
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved anomaly plot to {save_path}")
        
        plt.show() 