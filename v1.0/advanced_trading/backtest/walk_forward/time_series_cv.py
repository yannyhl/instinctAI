"""
Time Series Cross-Validation Module
---------------------------------
This module provides advanced time series cross-validation utilities for walk-forward testing.

Key features:
1. Purged cross-validation to prevent data leakage
2. Embargo periods to simulate real-world implementation delays
3. Multiple cross-validation schemes (expanding window, sliding window, anchored window)
4. Proper handling of temporal dependencies in financial data
5. Performance metrics calculation on each fold
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Callable, Optional, Union, Iterator, Any
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from sklearn.base import BaseEstimator
from sklearn.metrics import mean_squared_error, accuracy_score, precision_score, recall_score, f1_score

# Configure logger
logger = logging.getLogger(__name__)

class TimeSeriesCV:
    """
    Time Series Cross-Validation for financial data.
    
    This class implements various time series cross-validation schemes that properly
    respect the temporal order of data and prevent look-ahead bias.
    
    Parameters:
    -----------
    cv_method : str
        Cross-validation method ('expanding', 'sliding', 'anchored')
    n_splits : int
        Number of train/test splits to generate
    train_size : Union[int, float]
        Size of the training window (int for absolute size, float for fraction of data)
    test_size : Union[int, float]
        Size of the test window (int for absolute size, float for fraction of data)
    step_size : Union[int, float]
        Step size between folds (int for absolute size, float for fraction of data)
    purge_size : Union[int, float, None]
        Size of purged data between train and test (to prevent leakage)
    embargo_size : Union[int, float, None]
        Size of embargo after test data (to simulate implementation delays)
    min_train_size : Optional[int]
        Minimum training set size (only for expanding window)
    """
    
    def __init__(
        self,
        cv_method: str = 'expanding',
        n_splits: int = 5,
        train_size: Union[int, float] = 0.6,
        test_size: Union[int, float] = 0.2,
        step_size: Union[int, float] = 0.2,
        purge_size: Optional[Union[int, float]] = None,
        embargo_size: Optional[Union[int, float]] = None,
        min_train_size: Optional[int] = None
    ):
        self.cv_method = cv_method
        self.n_splits = n_splits
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
        self.purge_size = purge_size
        self.embargo_size = embargo_size
        self.min_train_size = min_train_size
        
        # Validate parameters
        self._validate_parameters()
        
        # Track indices for each fold
        self.train_indices = []
        self.test_indices = []
        self.purge_indices = []
        self.embargo_indices = []
    
    def _validate_parameters(self):
        """Validate the parameters provided to the constructor."""
        valid_methods = ['expanding', 'sliding', 'anchored']
        if self.cv_method not in valid_methods:
            raise ValueError(f"cv_method must be one of {valid_methods}")
        
        if not isinstance(self.n_splits, int) or self.n_splits <= 0:
            raise ValueError("n_splits must be a positive integer")
        
        # If expanding window, we need a min_train_size or train_size must be an int
        if self.cv_method == 'expanding' and self.min_train_size is None and isinstance(self.train_size, float):
            logger.warning("For expanding window, setting min_train_size to 252 trading days by default")
            self.min_train_size = 252  # Default to 1 year of trading days
    
    def _get_absolute_size(self, size: Union[int, float], total_size: int) -> int:
        """Convert relative sizes (floats) to absolute sizes (integers)."""
        if isinstance(size, float):
            if size <= 0 or size > 1:
                raise ValueError("Relative size must be in range (0, 1]")
            return int(size * total_size)
        return size
    
    def _generate_expanding_window_indices(self, total_size: int) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Generate indices for expanding window cross-validation."""
        # Get absolute sizes
        test_size = self._get_absolute_size(self.test_size, total_size)
        step_size = self._get_absolute_size(self.step_size, total_size)
        purge_size = self._get_absolute_size(self.purge_size, total_size) if self.purge_size else 0
        embargo_size = self._get_absolute_size(self.embargo_size, total_size) if self.embargo_size else 0
        
        # For expanding window, train_size is the initial size
        if isinstance(self.train_size, int):
            train_size_init = self.train_size
        else:
            train_size_init = self._get_absolute_size(self.train_size, total_size)
        
        # Ensure we have enough data
        if train_size_init + purge_size + test_size + embargo_size > total_size:
            raise ValueError("Not enough data for the specified sizes")
        
        # Generate splits
        train_start = 0
        test_end_max = total_size
        
        train_test_indices = []
        
        for i in range(self.n_splits):
            # Training set grows with each iteration
            train_end = train_size_init + i * step_size
            train_end = min(train_end, total_size - test_size - purge_size)
            
            test_start = train_end + purge_size
            test_end = test_start + test_size
            
            # Ensure we don't exceed data limits
            if test_end > test_end_max:
                break
            
            # Store indices
            train_indices = np.arange(train_start, train_end)
            test_indices = np.arange(test_start, test_end)
            
            # Store purge and embargo indices
            if purge_size > 0:
                self.purge_indices.append(np.arange(train_end, test_start))
            
            if embargo_size > 0 and test_end + embargo_size <= total_size:
                self.embargo_indices.append(np.arange(test_end, test_end + embargo_size))
            
            train_test_indices.append((train_indices, test_indices))
        
        return train_test_indices
    
    def _generate_sliding_window_indices(self, total_size: int) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Generate indices for sliding window cross-validation."""
        # Get absolute sizes
        train_size = self._get_absolute_size(self.train_size, total_size)
        test_size = self._get_absolute_size(self.test_size, total_size)
        step_size = self._get_absolute_size(self.step_size, total_size)
        purge_size = self._get_absolute_size(self.purge_size, total_size) if self.purge_size else 0
        embargo_size = self._get_absolute_size(self.embargo_size, total_size) if self.embargo_size else 0
        
        # Ensure we have enough data
        if train_size + purge_size + test_size + embargo_size > total_size:
            raise ValueError("Not enough data for the specified sizes")
        
        train_test_indices = []
        
        # Calculate the start indices
        max_start = total_size - train_size - purge_size - test_size
        starts = np.arange(0, max_start + 1, step_size)
        
        # Limit the number of splits
        starts = starts[:self.n_splits]
        
        for start in starts:
            train_end = start + train_size
            test_start = train_end + purge_size
            test_end = test_start + test_size
            
            # Store indices
            train_indices = np.arange(start, train_end)
            test_indices = np.arange(test_start, test_end)
            
            # Store purge and embargo indices
            if purge_size > 0:
                self.purge_indices.append(np.arange(train_end, test_start))
            
            if embargo_size > 0 and test_end + embargo_size <= total_size:
                self.embargo_indices.append(np.arange(test_end, test_end + embargo_size))
            
            train_test_indices.append((train_indices, test_indices))
        
        return train_test_indices
    
    def _generate_anchored_window_indices(self, total_size: int) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Generate indices for anchored window cross-validation."""
        # Get absolute sizes
        train_size_init = self._get_absolute_size(self.train_size, total_size)
        test_size = self._get_absolute_size(self.test_size, total_size)
        step_size = self._get_absolute_size(self.step_size, total_size)
        purge_size = self._get_absolute_size(self.purge_size, total_size) if self.purge_size else 0
        embargo_size = self._get_absolute_size(self.embargo_size, total_size) if self.embargo_size else 0
        
        # Ensure we have enough data
        if train_size_init + purge_size + test_size + embargo_size > total_size:
            raise ValueError("Not enough data for the specified sizes")
        
        train_test_indices = []
        
        # Fixed start for anchored window
        train_start = 0
        
        for i in range(self.n_splits):
            train_end = train_size_init + i * step_size
            test_start = train_end + purge_size
            test_end = test_start + test_size
            
            # Ensure we don't exceed data limits
            if test_end > total_size:
                break
            
            # Store indices
            train_indices = np.arange(train_start, train_end)
            test_indices = np.arange(test_start, test_end)
            
            # Store purge and embargo indices
            if purge_size > 0:
                self.purge_indices.append(np.arange(train_end, test_start))
            
            if embargo_size > 0 and test_end + embargo_size <= total_size:
                self.embargo_indices.append(np.arange(test_end, test_end + embargo_size))
            
            train_test_indices.append((train_indices, test_indices))
        
        return train_test_indices
    
    def split(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Union[pd.Series, np.ndarray]] = None) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate indices for time series cross-validation splits.
        
        Parameters:
        -----------
        X : Union[pd.DataFrame, np.ndarray]
            Feature data
        y : Optional[Union[pd.Series, np.ndarray]]
            Target data (not used, included for sklearn compatibility)
            
        Yields:
        -------
        tuple
            (train_indices, test_indices) for each fold
        """
        total_size = len(X)
        
        # Clear previous indices
        self.train_indices = []
        self.test_indices = []
        self.purge_indices = []
        self.embargo_indices = []
        
        # Generate indices based on method
        if self.cv_method == 'expanding':
            train_test_indices = self._generate_expanding_window_indices(total_size)
        elif self.cv_method == 'sliding':
            train_test_indices = self._generate_sliding_window_indices(total_size)
        elif self.cv_method == 'anchored':
            train_test_indices = self._generate_anchored_window_indices(total_size)
        else:
            raise ValueError(f"Unknown cv_method: {self.cv_method}")
        
        # Store indices
        for train_idx, test_idx in train_test_indices:
            self.train_indices.append(train_idx)
            self.test_indices.append(test_idx)
            yield train_idx, test_idx
    
    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        """
        Returns the number of splitting iterations in the cross-validator.
        
        Parameters:
        -----------
        X : Optional
            Not used, present for compatibility
        y : Optional
            Not used, present for compatibility
        groups : Optional
            Not used, present for compatibility
            
        Returns:
        --------
        int
            Number of splitting iterations
        """
        return self.n_splits
    
    def visualize_splits(self, X: Union[pd.DataFrame, np.ndarray], date_index: Optional[pd.DatetimeIndex] = None) -> plt.Figure:
        """
        Visualize the cross-validation splits.
        
        Parameters:
        -----------
        X : Union[pd.DataFrame, np.ndarray]
            Feature data
        date_index : Optional[pd.DatetimeIndex]
            Date index for x-axis (if None, will use integer indices)
            
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        if not self.train_indices or not self.test_indices:
            _ = list(self.split(X))  # Generate indices if not already generated
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Use date index if provided, otherwise use integer indices
        if date_index is not None and len(date_index) == len(X):
            x_values = date_index
            x_label = 'Date'
        else:
            x_values = np.arange(len(X))
            x_label = 'Index'
        
        # Plot each fold
        for i, (train_idx, test_idx) in enumerate(zip(self.train_indices, self.test_indices)):
            # Plot train indices
            train_x = [x_values[idx] for idx in train_idx]
            ax.scatter(train_x, [i] * len(train_idx), marker='|', color='blue', label='Train' if i == 0 else "")
            
            # Plot test indices
            test_x = [x_values[idx] for idx in test_idx]
            ax.scatter(test_x, [i] * len(test_idx), marker='|', color='red', label='Test' if i == 0 else "")
            
            # Plot purge indices if available
            if i < len(self.purge_indices) and len(self.purge_indices[i]) > 0:
                purge_x = [x_values[idx] for idx in self.purge_indices[i]]
                ax.scatter(purge_x, [i] * len(purge_x), marker='|', color='gray', alpha=0.5, label='Purge' if i == 0 else "")
            
            # Plot embargo indices if available
            if i < len(self.embargo_indices) and len(self.embargo_indices[i]) > 0:
                embargo_x = [x_values[idx] for idx in self.embargo_indices[i]]
                ax.scatter(embargo_x, [i] * len(embargo_x), marker='|', color='orange', alpha=0.5, label='Embargo' if i == 0 else "")
        
        # Set labels and title
        ax.set_yticks(range(len(self.train_indices)))
        ax.set_yticklabels([f'Fold {i+1}' for i in range(len(self.train_indices))])
        ax.set_xlabel(x_label)
        ax.set_ylabel('Fold')
        ax.set_title(f"{self.cv_method.capitalize()} Window Time Series Cross-Validation")
        
        # Add legend
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=4)
        
        plt.tight_layout()
        return fig
    
    def cross_val_predict(
        self,
        model: BaseEstimator,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        fit_params: Optional[Dict] = None,
        predict_method: str = 'predict'
    ) -> np.ndarray:
        """
        Generate cross-validated predictions.
        
        Parameters:
        -----------
        model : BaseEstimator
            Machine learning model with fit and predict methods
        X : Union[pd.DataFrame, np.ndarray]
            Feature data
        y : Union[pd.Series, np.ndarray]
            Target data
        fit_params : Optional[Dict]
            Additional parameters to pass to the model's fit method
        predict_method : str
            Method to call for prediction ('predict', 'predict_proba', etc.)
            
        Returns:
        --------
        np.ndarray
            Cross-validated predictions
        """
        fit_params = fit_params or {}
        
        # Convert to numpy arrays for consistent indexing
        X_array = X.values if isinstance(X, (pd.DataFrame, pd.Series)) else X
        y_array = y.values if isinstance(y, (pd.DataFrame, pd.Series)) else y
        
        # Initialize predictions array
        predictions = np.zeros(len(X_array))
        pred_indices = np.zeros(len(X_array), dtype=bool)
        
        # Perform cross-validation
        for train_idx, test_idx in self.split(X):
            # Fit model on training data
            model.fit(X_array[train_idx], y_array[train_idx], **fit_params)
            
            # Generate predictions on test data
            predict_func = getattr(model, predict_method)
            fold_preds = predict_func(X_array[test_idx])
            
            # Store predictions
            predictions[test_idx] = fold_preds
            pred_indices[test_idx] = True
        
        # Return predictions (only for indices that were part of a test set)
        return predictions

    def cross_val_score(
        self,
        model: BaseEstimator,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        scoring: Union[str, Callable] = 'mse',
        fit_params: Optional[Dict] = None,
        predict_method: str = 'predict'
    ) -> Tuple[List[float], np.ndarray]:
        """
        Evaluate model performance using cross-validation.
        
        Parameters:
        -----------
        model : BaseEstimator
            Machine learning model with fit and predict methods
        X : Union[pd.DataFrame, np.ndarray]
            Feature data
        y : Union[pd.Series, np.ndarray]
            Target data
        scoring : Union[str, Callable]
            Scoring metric ('mse', 'rmse', 'accuracy', 'precision', 'recall', 'f1') or callable
        fit_params : Optional[Dict]
            Additional parameters to pass to the model's fit method
        predict_method : str
            Method to call for prediction ('predict', 'predict_proba', etc.)
            
        Returns:
        --------
        Tuple[List[float], np.ndarray]
            (scores for each fold, all predictions)
        """
        fit_params = fit_params or {}
        
        # Convert to numpy arrays for consistent indexing
        X_array = X.values if isinstance(X, (pd.DataFrame, pd.Series)) else X
        y_array = y.values if isinstance(y, (pd.DataFrame, pd.Series)) else y
        
        # Initialize scores and predictions
        scores = []
        predictions = np.zeros(len(X_array))
        pred_indices = np.zeros(len(X_array), dtype=bool)
        
        # Perform cross-validation
        for train_idx, test_idx in self.split(X):
            # Fit model on training data
            model.fit(X_array[train_idx], y_array[train_idx], **fit_params)
            
            # Generate predictions on test data
            predict_func = getattr(model, predict_method)
            fold_preds = predict_func(X_array[test_idx])
            
            # Store predictions
            predictions[test_idx] = fold_preds
            pred_indices[test_idx] = True
            
            # Calculate score
            if callable(scoring):
                # Use custom scoring function
                score = scoring(y_array[test_idx], fold_preds)
            else:
                # Use predefined scoring metrics
                score = self._calculate_score(scoring, y_array[test_idx], fold_preds)
            
            scores.append(score)
        
        return scores, predictions
    
    def _calculate_score(self, scoring: str, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate score based on the specified metric."""
        if scoring == 'mse':
            return mean_squared_error(y_true, y_pred)
        elif scoring == 'rmse':
            return np.sqrt(mean_squared_error(y_true, y_pred))
        elif scoring == 'accuracy':
            return accuracy_score(y_true, y_pred.round())
        elif scoring == 'precision':
            return precision_score(y_true, y_pred.round())
        elif scoring == 'recall':
            return recall_score(y_true, y_pred.round())
        elif scoring == 'f1':
            return f1_score(y_true, y_pred.round())
        else:
            raise ValueError(f"Unknown scoring metric: {scoring}")
    
    def walk_forward_validation(
        self,
        model_factory: Callable[[], BaseEstimator],
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        retrain_freq: int = 1,
        fit_params: Optional[Dict] = None,
        predict_method: str = 'predict',
        return_models: bool = False
    ) -> Dict[str, Any]:
        """
        Perform walk-forward validation with retraining at specified frequency.
        
        Parameters:
        -----------
        model_factory : Callable[[], BaseEstimator]
            Function that returns a new instance of the model
        X : Union[pd.DataFrame, np.ndarray]
            Feature data
        y : Union[pd.Series, np.ndarray]
            Target data
        retrain_freq : int
            How often to retrain the model (1 = every step, 2 = every other step, etc.)
        fit_params : Optional[Dict]
            Additional parameters to pass to the model's fit method
        predict_method : str
            Method to call for prediction ('predict', 'predict_proba', etc.)
        return_models : bool
            Whether to return the trained models
            
        Returns:
        --------
        Dict[str, Any]
            Dictionary with walk-forward validation results
        """
        fit_params = fit_params or {}
        
        # Convert to numpy arrays for consistent indexing
        X_array = X.values if isinstance(X, (pd.DataFrame, pd.Series)) else X
        y_array = y.values if isinstance(y, (pd.DataFrame, pd.Series)) else y
        
        # Generate indices if not already generated
        if not self.train_indices or not self.test_indices:
            _ = list(self.split(X))
        
        # Initialize results
        predictions = np.zeros(len(X_array))
        pred_indices = np.zeros(len(X_array), dtype=bool)
        trained_models = []
        train_times = []
        prediction_times = []
        fold_metrics = []
        
        # Initialize model
        current_model = None
        
        # Perform walk-forward validation
        for i, (train_idx, test_idx) in enumerate(zip(self.train_indices, self.test_indices)):
            # Check if we need to retrain
            if i % retrain_freq == 0 or current_model is None:
                # Create new model instance
                current_model = model_factory()
                
                # Measure training time
                train_start = datetime.now()
                
                # Fit model on training data
                current_model.fit(X_array[train_idx], y_array[train_idx], **fit_params)
                
                # Record training time
                train_end = datetime.now()
                train_times.append((train_end - train_start).total_seconds())
                
                # Store trained model if requested
                if return_models:
                    trained_models.append(current_model)
            
            # Measure prediction time
            pred_start = datetime.now()
            
            # Generate predictions on test data
            predict_func = getattr(current_model, predict_method)
            fold_preds = predict_func(X_array[test_idx])
            
            # Record prediction time
            pred_end = datetime.now()
            prediction_times.append((pred_end - pred_start).total_seconds())
            
            # Store predictions
            predictions[test_idx] = fold_preds
            pred_indices[test_idx] = True
            
            # Calculate metrics for this fold
            fold_metrics.append({
                'fold': i + 1,
                'train_size': len(train_idx),
                'test_size': len(test_idx),
                'mse': mean_squared_error(y_array[test_idx], fold_preds),
                'accuracy': accuracy_score(y_array[test_idx], np.round(fold_preds)) if np.all((fold_preds >= 0) & (fold_preds <= 1)) else None
            })
        
        # Compile results
        results = {
            'predictions': predictions,
            'prediction_indices': pred_indices,
            'train_times': train_times,
            'prediction_times': prediction_times,
            'fold_metrics': fold_metrics,
            'mean_train_time': np.mean(train_times) if train_times else None,
            'mean_prediction_time': np.mean(prediction_times) if prediction_times else None,
            'total_train_time': sum(train_times) if train_times else None,
        }
        
        if return_models:
            results['models'] = trained_models
        
        return results
    
    def get_fold_dates(self, date_index: pd.DatetimeIndex) -> List[Dict[str, Any]]:
        """
        Get date ranges for each fold.
        
        Parameters:
        -----------
        date_index : pd.DatetimeIndex
            DatetimeIndex corresponding to the data
            
        Returns:
        --------
        List[Dict[str, Any]]
            List of dictionaries with date ranges for each fold
        """
        if not self.train_indices or not self.test_indices:
            raise ValueError("No folds generated yet. Call split() first.")
        
        if len(date_index) != len(self.train_indices[0]) + len(self.test_indices[0]) + \
            (len(self.purge_indices[0]) if self.purge_indices else 0) + \
            (len(self.embargo_indices[0]) if self.embargo_indices else 0):
            raise ValueError("Date index length does not match data length")
        
        fold_dates = []
        
        for i, (train_idx, test_idx) in enumerate(zip(self.train_indices, self.test_indices)):
            fold_info = {
                'fold': i + 1,
                'train_start': date_index[train_idx[0]],
                'train_end': date_index[train_idx[-1]],
                'test_start': date_index[test_idx[0]],
                'test_end': date_index[test_idx[-1]],
            }
            
            # Add purge dates if available
            if self.purge_indices and i < len(self.purge_indices) and len(self.purge_indices[i]) > 0:
                fold_info['purge_start'] = date_index[self.purge_indices[i][0]]
                fold_info['purge_end'] = date_index[self.purge_indices[i][-1]]
            
            # Add embargo dates if available
            if self.embargo_indices and i < len(self.embargo_indices) and len(self.embargo_indices[i]) > 0:
                fold_info['embargo_start'] = date_index[self.embargo_indices[i][0]]
                fold_info['embargo_end'] = date_index[self.embargo_indices[i][-1]]
            
            fold_dates.append(fold_info)
        
        return fold_dates 