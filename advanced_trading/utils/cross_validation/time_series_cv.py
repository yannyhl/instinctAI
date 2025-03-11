"""
Time Series Cross-Validation Module
---------------------------------
This module provides advanced time series cross-validation utilities for backtesting.

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
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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
        Minimum training size (only used with expanding window)
    """
    
    def __init__(
        self,
        cv_method: str = 'sliding',
        n_splits: int = 5,
        train_size: Union[int, float] = 0.7,
        test_size: Union[int, float] = 0.3,
        step_size: Union[int, float] = 0.05,
        purge_size: Optional[Union[int, float]] = None,
        embargo_size: Optional[Union[int, float]] = None,
        min_train_size: Optional[int] = None
    ):
        """Initialize TimeSeriesCV."""
        # Validate cv_method
        valid_methods = ['expanding', 'sliding', 'anchored']
        if cv_method not in valid_methods:
            raise ValueError(f"Invalid cv_method: {cv_method}. Must be one of {valid_methods}")
            
        self.cv_method = cv_method
        self.n_splits = n_splits
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
        self.purge_size = purge_size
        self.embargo_size = embargo_size
        self.min_train_size = min_train_size
        
        logger.info(f"Initialized TimeSeriesCV with {cv_method} method, "
                   f"{n_splits} splits")
    
    def split(self, X: Union[pd.DataFrame, np.ndarray], 
             y: Optional[Union[pd.Series, np.ndarray]] = None) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate indices to split data into training and test sets.
        
        Parameters:
        -----------
        X : pd.DataFrame or np.ndarray
            Feature data
        y : pd.Series or np.ndarray, optional
            Target data (not used for splitting, but follows scikit-learn convention)
            
        Yields:
        -------
        train_index, test_index : Tuple[np.ndarray, np.ndarray]
            The training and test indices for each fold
        """
        # Get data length
        n_samples = len(X)
        
        # Convert sizes to absolute values if provided as fractions
        train_size = self._get_absolute_size(self.train_size, n_samples)
        test_size = self._get_absolute_size(self.test_size, n_samples)
        step_size = self._get_absolute_size(self.step_size, n_samples)
        purge_size = self._get_absolute_size(self.purge_size, n_samples) if self.purge_size is not None else 0
        embargo_size = self._get_absolute_size(self.embargo_size, n_samples) if self.embargo_size is not None else 0
        
        # Ensure sizes are valid
        if train_size + purge_size + test_size > n_samples:
            raise ValueError(f"Not enough samples ({n_samples}) for train_size ({train_size}), "
                            f"purge_size ({purge_size}), and test_size ({test_size})")
            
        # Calculate the fold indices based on cv_method
        if self.cv_method == 'sliding':
            splits = self._get_sliding_window_indices(n_samples, train_size, test_size, 
                                                    step_size, purge_size, embargo_size)
        elif self.cv_method == 'expanding':
            min_train_size = self.min_train_size or train_size
            splits = self._get_expanding_window_indices(n_samples, min_train_size, test_size, 
                                                      step_size, purge_size, embargo_size)
        elif self.cv_method == 'anchored':
            splits = self._get_anchored_window_indices(n_samples, train_size, test_size, 
                                                     step_size, purge_size, embargo_size)
        else:
            raise ValueError(f"Invalid cv_method: {self.cv_method}")
            
        # Limit to n_splits if specified
        if self.n_splits and len(splits) > self.n_splits:
            splits = splits[:self.n_splits]
            
        for train_indices, test_indices in splits:
            yield np.array(train_indices), np.array(test_indices)
    
    def _get_absolute_size(self, size: Union[int, float, None], n_samples: int) -> int:
        """Convert fractional sizes to absolute."""
        if size is None:
            return 0
        elif isinstance(size, float) and 0 < size < 1:
            return int(n_samples * size)
        elif isinstance(size, int):
            return size
        else:
            raise ValueError(f"Invalid size: {size}. Must be int or float between 0 and 1")
    
    def _get_sliding_window_indices(self, n_samples: int, train_size: int, test_size: int, 
                                  step_size: int, purge_size: int, embargo_size: int) -> List[Tuple[List[int], List[int]]]:
        """Generate indices for sliding window cross-validation."""
        splits = []
        
        # Calculate the maximum end index
        max_end = n_samples
        
        # Initialize the first test period
        test_end = n_samples
        test_start = test_end - test_size
        
        while test_start >= train_size + purge_size:
            # Calculate train period
            train_end = test_start - purge_size
            train_start = train_end - train_size
            
            # Ensure train period has enough data
            if train_start < 0:
                break
                
            # Calculate train and test indices
            train_indices = list(range(train_start, train_end))
            test_indices = list(range(test_start, test_end))
            
            # Apply embargo (remove indices from previous test set)
            if embargo_size > 0 and len(splits) > 0:
                prev_test_indices = splits[-1][1]
                embargo_indices = list(range(prev_test_indices[-1] + 1, 
                                          min(prev_test_indices[-1] + 1 + embargo_size, n_samples)))
                train_indices = [i for i in train_indices if i not in embargo_indices]
                
            # Append this split
            splits.append((train_indices, test_indices))
            
            # Move to next period
            test_end = test_start
            test_start = test_end - test_size
            
            # Stop if we've generated enough splits
            if self.n_splits and len(splits) >= self.n_splits:
                break
                
        # Reverse the order to have chronologically increasing splits
        return splits[::-1]
    
    def _get_expanding_window_indices(self, n_samples: int, min_train_size: int, test_size: int, 
                                    step_size: int, purge_size: int, embargo_size: int) -> List[Tuple[List[int], List[int]]]:
        """Generate indices for expanding window cross-validation."""
        splits = []
        
        # Calculate the maximum end index
        max_end = n_samples
        
        # Initialize the first test period
        test_start = min_train_size + purge_size
        test_end = test_start + test_size
        
        while test_end <= max_end:
            # Calculate train period (expanding window)
            train_start = 0
            train_end = test_start - purge_size
            
            # Calculate train and test indices
            train_indices = list(range(train_start, train_end))
            test_indices = list(range(test_start, test_end))
            
            # Apply embargo (remove indices from previous test set)
            if embargo_size > 0 and len(splits) > 0:
                prev_test_indices = splits[-1][1]
                embargo_indices = list(range(prev_test_indices[-1] + 1, 
                                          min(prev_test_indices[-1] + 1 + embargo_size, n_samples)))
                train_indices = [i for i in train_indices if i not in embargo_indices]
                
            # Append this split
            splits.append((train_indices, test_indices))
            
            # Move to next period
            test_start += step_size
            test_end = test_start + test_size
            
            # Stop if we've generated enough splits
            if self.n_splits and len(splits) >= self.n_splits:
                break
                
        return splits
    
    def _get_anchored_window_indices(self, n_samples: int, train_size: int, test_size: int, 
                                   step_size: int, purge_size: int, embargo_size: int) -> List[Tuple[List[int], List[int]]]:
        """Generate indices for anchored window cross-validation."""
        splits = []
        
        # Calculate the maximum end index
        max_end = n_samples
        
        # Initialize the first test period
        test_start = train_size + purge_size
        test_end = test_start + test_size
        
        # Fix the anchor point (the start of the first training window)
        anchor_start = 0
        
        while test_end <= max_end:
            # Calculate train period (anchored window)
            train_start = anchor_start
            train_end = test_start - purge_size
            
            # Calculate train and test indices
            train_indices = list(range(train_start, train_end))
            test_indices = list(range(test_start, test_end))
            
            # Apply embargo (remove indices from previous test set)
            if embargo_size > 0 and len(splits) > 0:
                prev_test_indices = splits[-1][1]
                embargo_indices = list(range(prev_test_indices[-1] + 1, 
                                          min(prev_test_indices[-1] + 1 + embargo_size, n_samples)))
                train_indices = [i for i in train_indices if i not in embargo_indices]
                
            # Append this split
            splits.append((train_indices, test_indices))
            
            # Move to next period
            test_start += step_size
            test_end = test_start + test_size
            
            # Stop if we've generated enough splits
            if self.n_splits and len(splits) >= self.n_splits:
                break
                
        return splits
    
    def plot_cv_indices(self, X: Union[pd.DataFrame, np.ndarray], 
                       figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
        """
        Plot the indices of the cross-validation splits.
        
        Parameters:
        -----------
        X : pd.DataFrame or np.ndarray
            Feature data
        figsize : Tuple[int, int]
            Figure size
            
        Returns:
        --------
        matplotlib.pyplot.Figure
            Figure with cross-validation indices visualization
        """
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Generate the splits
        splits = list(self.split(X))
        n_samples = len(X)
        
        # Create a colormap
        colors = plt.cm.tab10.colors
        
        # Plot each split
        for i, (train_indices, test_indices) in enumerate(splits):
            # Plot train indices
            ax.barh(i, len(train_indices), left=min(train_indices), height=0.8, 
                   color=colors[0], alpha=0.6, label='Train' if i == 0 else None)
            
            # Plot test indices
            ax.barh(i, len(test_indices), left=min(test_indices), height=0.8, 
                   color=colors[1], alpha=0.6, label='Test' if i == 0 else None)
            
            # Calculate and plot purge region if any
            if self.purge_size:
                purge_start = max(train_indices) + 1
                purge_end = min(test_indices) - 1
                if purge_end >= purge_start:
                    ax.barh(i, purge_end - purge_start + 1, left=purge_start, height=0.8, 
                           color=colors[2], alpha=0.6, label='Purge' if i == 0 else None)
            
        # Format the plot
        ax.set_xlabel('Sample Index')
        ax.set_ylabel('CV Iteration')
        ax.set_yticks(range(len(splits)))
        ax.set_yticklabels([f'Split {i+1}' for i in range(len(splits))])
        ax.set_title(f'{self.cv_method.title()} Time Series Cross-Validation')
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=3)
        ax.grid(True, alpha=0.3)
        
        # Adjust layout
        plt.tight_layout()
        
        return fig
    
    def plot_cv_dates(self, X: pd.DataFrame, date_column: Optional[str] = None, 
                     figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
        """
        Plot the dates of the cross-validation splits.
        
        Parameters:
        -----------
        X : pd.DataFrame
            Feature data with datetime index or date column
        date_column : str, optional
            Name of the date column (if None, uses the index)
        figsize : Tuple[int, int]
            Figure size
            
        Returns:
        --------
        matplotlib.pyplot.Figure
            Figure with cross-validation dates visualization
        """
        # Extract dates
        if date_column is not None:
            if date_column not in X.columns:
                raise ValueError(f"Date column '{date_column}' not found in X")
            dates = X[date_column].values
        else:
            if not isinstance(X.index, pd.DatetimeIndex):
                raise ValueError("X must have a DatetimeIndex if date_column is not provided")
            dates = X.index.values
            
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Generate the splits
        splits = list(self.split(X))
        
        # Create a colormap
        colors = plt.cm.tab10.colors
        
        # Plot each split
        for i, (train_indices, test_indices) in enumerate(splits):
            # Get the dates for this split
            train_dates = dates[train_indices]
            test_dates = dates[test_indices]
            
            # Plot train dates
            ax.barh(i, (train_dates[-1] - train_dates[0]).astype('timedelta64[D]').astype(int), 
                   left=train_dates[0], height=0.8, color=colors[0], alpha=0.6, 
                   label='Train' if i == 0 else None)
            
            # Plot test dates
            ax.barh(i, (test_dates[-1] - test_dates[0]).astype('timedelta64[D]').astype(int), 
                   left=test_dates[0], height=0.8, color=colors[1], alpha=0.6, 
                   label='Test' if i == 0 else None)
            
            # Calculate and plot purge region if any
            if self.purge_size and train_dates[-1] < test_dates[0]:
                purge_start = train_dates[-1]
                purge_end = test_dates[0]
                ax.barh(i, (purge_end - purge_start).astype('timedelta64[D]').astype(int), 
                       left=purge_start, height=0.8, color=colors[2], alpha=0.6, 
                       label='Purge' if i == 0 else None)
            
        # Format the plot
        ax.set_xlabel('Date')
        ax.set_ylabel('CV Iteration')
        ax.set_yticks(range(len(splits)))
        ax.set_yticklabels([f'Split {i+1}' for i in range(len(splits))])
        ax.set_title(f'{self.cv_method.title()} Time Series Cross-Validation')
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=3)
        ax.grid(True, alpha=0.3)
        
        # Format dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        
        # Adjust layout
        plt.tight_layout()
        
        return fig


def purged_cross_val_score(estimator: Any, X: pd.DataFrame, y: pd.Series, 
                         cv: TimeSeriesCV, scoring: Union[str, Callable],
                         fit_params: Optional[Dict[str, Any]] = None) -> np.ndarray:
    """
    Evaluate a score by cross-validation, respecting time series structure.
    
    Parameters:
    -----------
    estimator : object
        Estimator object implementing 'fit' and 'predict'
    X : pd.DataFrame
        Feature data
    y : pd.Series
        Target data
    cv : TimeSeriesCV
        Cross-validation strategy
    scoring : str or callable
        Scoring function
    fit_params : dict, optional
        Parameters to pass to the fit method
        
    Returns:
    --------
    np.ndarray
        Array of scores for each CV split
    """
    from sklearn.metrics import get_scorer
    
    if fit_params is None:
        fit_params = {}
        
    # Get scorer
    if isinstance(scoring, str):
        scorer = get_scorer(scoring)
    else:
        scorer = scoring
        
    # Generate CV splits
    splits = list(cv.split(X, y))
    
    # Storage for scores
    scores = np.zeros(len(splits))
    
    # Evaluate each split
    for i, (train_indices, test_indices) in enumerate(splits):
        # Extract train and test data
        X_train, X_test = X.iloc[train_indices], X.iloc[test_indices]
        y_train, y_test = y.iloc[train_indices], y.iloc[test_indices]
        
        # Fit the estimator
        estimator.fit(X_train, y_train, **fit_params)
        
        # Score the estimator
        scores[i] = scorer(estimator, X_test, y_test)
        
    return scores


def plot_purged_cv_results(cv_results: Dict[str, List[float]], 
                        figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
    """
    Plot the results of a purged cross-validation.
    
    Parameters:
    -----------
    cv_results : Dict[str, List[float]]
        Dictionary mapping parameter combinations to scores
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    matplotlib.pyplot.Figure
        Figure with cross-validation results visualization
    """
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Get parameter combinations and scores
    param_names = list(cv_results.keys())
    scores = list(cv_results.values())
    
    # Calculate statistics
    mean_scores = [np.mean(s) for s in scores]
    std_scores = [np.std(s) for s in scores]
    
    # Sort by mean score
    sorted_indices = np.argsort(mean_scores)
    param_names = [param_names[i] for i in sorted_indices]
    mean_scores = [mean_scores[i] for i in sorted_indices]
    std_scores = [std_scores[i] for i in sorted_indices]
    
    # Plot scores
    x = np.arange(len(param_names))
    ax.bar(x, mean_scores, yerr=std_scores, alpha=0.8, capsize=5)
    
    # Format plot
    ax.set_xlabel('Parameter Combination')
    ax.set_ylabel('Score')
    ax.set_title('Purged Cross-Validation Results')
    ax.set_xticks(x)
    ax.set_xticklabels(param_names, rotation=45, ha='right')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Adjust layout
    plt.tight_layout()
    
    return fig 