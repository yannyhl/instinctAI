"""
Cross-validation utilities for machine learning trading strategies.

This module provides specialized cross-validation techniques for time series data
in trading applications, addressing the unique challenges of financial time series
such as non-stationarity, temporal dependence, and regime changes.
"""

import numpy as np
import pandas as pd
import logging
from typing import Callable, Dict, List, Tuple, Union, Optional
from sklearn.model_selection import KFold, TimeSeriesSplit
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import joblib
import os

# Configure logging
logger = logging.getLogger(__name__)

class TimeSeriesCrossValidator:
    """
    Time series cross-validation for financial market data.
    
    This class implements various cross-validation strategies specifically designed
    for financial time series data, addressing issues like temporal dependence,
    non-stationarity, and regime changes.
    """
    
    def __init__(
        self,
        cv_method: str = "purged_kfold",
        n_splits: int = 5,
        gap_size: int = 0,
        embargo_size: int = 0,
        min_train_size: Optional[int] = None,
        max_train_size: Optional[int] = None,
        test_size: Optional[int] = None,
        random_state: Optional[int] = None,
        regime_column: Optional[str] = None
    ):
        """
        Initialize the time series cross-validator.
        
        Args:
            cv_method: Cross-validation method to use. Options:
                - "purged_kfold": K-fold with purging and embargo
                - "walk_forward": Expanding window validation
                - "sliding_window": Fixed-size sliding window
                - "regime_based": Split based on market regimes
            n_splits: Number of splits for cross-validation
            gap_size: Number of samples to exclude between train and test sets (purging)
            embargo_size: Number of samples to exclude after test set (embargo)
            min_train_size: Minimum size of the training set
            max_train_size: Maximum size of the training set
            test_size: Size of the test set
            random_state: Random seed for reproducibility
            regime_column: Column name containing regime labels (for regime_based CV)
        """
        self.cv_method = cv_method
        self.n_splits = n_splits
        self.gap_size = gap_size
        self.embargo_size = embargo_size
        self.min_train_size = min_train_size
        self.max_train_size = max_train_size
        self.test_size = test_size
        self.random_state = random_state
        self.regime_column = regime_column
        
        # Validate parameters
        self._validate_parameters()
    
    def _validate_parameters(self):
        """Validate the input parameters."""
        valid_methods = ["purged_kfold", "walk_forward", "sliding_window", "regime_based"]
        if self.cv_method not in valid_methods:
            raise ValueError(f"cv_method must be one of {valid_methods}")
        
        if self.cv_method == "regime_based" and self.regime_column is None:
            raise ValueError("regime_column must be specified for regime_based cross-validation")
    
    def split(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate train/test indices to split data in train/test sets.
        
        Args:
            X: Features dataframe with DatetimeIndex
            y: Target variable (optional)
            
        Returns:
            List of tuples (train_idx, test_idx) for each fold
        """
        if not isinstance(X.index, pd.DatetimeIndex):
            raise ValueError("X must have a DatetimeIndex for time series cross-validation")
        
        if self.cv_method == "purged_kfold":
            return self._purged_kfold_split(X, y)
        elif self.cv_method == "walk_forward":
            return self._walk_forward_split(X)
        elif self.cv_method == "sliding_window":
            return self._sliding_window_split(X)
        elif self.cv_method == "regime_based":
            return self._regime_based_split(X)
    
    def _purged_kfold_split(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Implement purged K-fold cross-validation with embargo.
        
        Purging removes overlapping samples between train and test sets.
        Embargo removes samples from the training set that are close to the test set.
        
        Args:
            X: Features dataframe with DatetimeIndex
            y: Target variable (optional)
            
        Returns:
            List of tuples (train_idx, test_idx) for each fold
        """
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        # Basic K-fold split
        kf = KFold(n_splits=self.n_splits, shuffle=True, random_state=self.random_state)
        basic_splits = list(kf.split(X))
        
        # Apply purging and embargo
        purged_splits = []
        for train_idx, test_idx in basic_splits:
            # Get the time indices
            test_times = X.index[test_idx]
            test_start, test_end = test_times.min(), test_times.max()
            
            # Purging: remove samples from train that are within gap_size of test
            if self.gap_size > 0:
                gap_start = test_start - pd.Timedelta(days=self.gap_size)
                gap_end = test_end + pd.Timedelta(days=self.gap_size)
                
                # Keep only train samples outside the gap
                train_idx = np.array([
                    i for i in train_idx 
                    if X.index[i] < gap_start or X.index[i] > gap_end
                ])
            
            # Embargo: remove samples from train that are within embargo_size after test
            if self.embargo_size > 0:
                embargo_end = test_end + pd.Timedelta(days=self.embargo_size)
                
                # Remove samples in the embargo period
                train_idx = np.array([
                    i for i in train_idx 
                    if X.index[i] <= test_end or X.index[i] > embargo_end
                ])
            
            purged_splits.append((train_idx, test_idx))
        
        return purged_splits
    
    def _walk_forward_split(self, X: pd.DataFrame) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Implement walk-forward validation (expanding window).
        
        Args:
            X: Features dataframe with DatetimeIndex
            
        Returns:
            List of tuples (train_idx, test_idx) for each fold
        """
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        # Determine test size if not specified
        test_size = self.test_size or max(1, n_samples // (self.n_splits + 1))
        
        # Determine initial train size
        if self.min_train_size is None:
            initial_train_size = max(1, n_samples // (self.n_splits + 1))
        else:
            initial_train_size = self.min_train_size
        
        splits = []
        for i in range(self.n_splits):
            # Calculate split points
            train_end = initial_train_size + i * test_size
            test_start = train_end + self.gap_size
            test_end = min(test_start + test_size, n_samples)
            
            # Check if we have enough data for another split
            if test_end >= n_samples:
                break
                
            # Create train/test indices
            train_indices = indices[:train_end]
            test_indices = indices[test_start:test_end]
            
            # Apply max_train_size if specified
            if self.max_train_size is not None and len(train_indices) > self.max_train_size:
                train_indices = train_indices[-self.max_train_size:]
                
            splits.append((train_indices, test_indices))
            
        return splits
    
    def _sliding_window_split(self, X: pd.DataFrame) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Implement sliding window validation (fixed-size window).
        
        Args:
            X: Features dataframe with DatetimeIndex
            
        Returns:
            List of tuples (train_idx, test_idx) for each fold
        """
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        # Determine test size if not specified
        test_size = self.test_size or max(1, n_samples // (self.n_splits + 1))
        
        # Determine train size
        if self.min_train_size is None:
            train_size = max(1, n_samples // (self.n_splits + 1))
        else:
            train_size = self.min_train_size
            
        # Use max_train_size if specified
        if self.max_train_size is not None:
            train_size = min(train_size, self.max_train_size)
        
        # Calculate step size
        step_size = (n_samples - train_size - test_size) // self.n_splits
        if step_size <= 0:
            step_size = test_size
        
        splits = []
        for i in range(self.n_splits):
            # Calculate split points
            train_start = i * step_size
            train_end = train_start + train_size
            test_start = train_end + self.gap_size
            test_end = test_start + test_size
            
            # Check if we have enough data for another split
            if test_end > n_samples:
                break
                
            # Create train/test indices
            train_indices = indices[train_start:train_end]
            test_indices = indices[test_start:test_end]
                
            splits.append((train_indices, test_indices))
            
        return splits
    
    def _regime_based_split(self, X: pd.DataFrame) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Implement regime-based cross-validation.
        
        This method splits the data based on market regimes, ensuring that
        each regime is represented in both training and testing sets.
        
        Args:
            X: Features dataframe with DatetimeIndex and regime_column
            
        Returns:
            List of tuples (train_idx, test_idx) for each fold
        """
        if self.regime_column not in X.columns:
            raise ValueError(f"Regime column '{self.regime_column}' not found in X")
        
        # Get unique regimes
        regimes = X[self.regime_column].unique()
        n_regimes = len(regimes)
        
        if n_regimes < 2:
            raise ValueError("At least 2 different regimes are required for regime-based CV")
        
        # Create indices for each regime
        regime_indices = {regime: np.where(X[self.regime_column] == regime)[0] for regime in regimes}
        
        # Create stratified folds ensuring each regime is represented
        splits = []
        for i in range(self.n_splits):
            train_indices = []
            test_indices = []
            
            for regime, indices in regime_indices.items():
                # Shuffle indices for this regime
                np.random.seed(self.random_state + i if self.random_state else None)
                shuffled_indices = indices.copy()
                np.random.shuffle(shuffled_indices)
                
                # Split into train/test
                n_test = max(1, len(shuffled_indices) // self.n_splits)
                test_start = i * n_test
                test_end = min((i + 1) * n_test, len(shuffled_indices))
                
                regime_test = shuffled_indices[test_start:test_end]
                regime_train = np.setdiff1d(shuffled_indices, regime_test)
                
                train_indices.extend(regime_train)
                test_indices.extend(regime_test)
            
            splits.append((np.array(train_indices), np.array(test_indices)))
        
        return splits
    
    def plot_splits(self, X: pd.DataFrame, y: Optional[pd.Series] = None, figsize: Tuple[int, int] = (15, 10)):
        """
        Visualize the cross-validation splits.
        
        Args:
            X: Features dataframe with DatetimeIndex
            y: Target variable (optional, for coloring)
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        splits = self.split(X, y)
        n_splits = len(splits)
        
        fig, ax = plt.subplots(n_splits, 1, figsize=figsize, sharex=True)
        if n_splits == 1:
            ax = [ax]
            
        for i, (train_idx, test_idx) in enumerate(splits):
            train_dates = X.index[train_idx]
            test_dates = X.index[test_idx]
            
            # Plot train and test periods
            ax[i].scatter(train_dates, [i + 0.1] * len(train_dates), 
                         c='blue', marker='|', s=100, label='Train')
            ax[i].scatter(test_dates, [i + 0.2] * len(test_dates), 
                         c='red', marker='|', s=100, label='Test')
            
            # Add regime information if available
            if self.cv_method == "regime_based" and self.regime_column in X.columns:
                for regime in X[self.regime_column].unique():
                    regime_dates = X[X[self.regime_column] == regime].index
                    ax[i].scatter(regime_dates, [i + 0.3] * len(regime_dates),
                                 alpha=0.3, marker='o', s=20, label=f'Regime {regime}')
            
            ax[i].set_ylabel(f'Fold {i+1}')
            
            if i == 0:
                ax[i].legend(loc='upper right')
                
        ax[-1].set_xlabel('Date')
        plt.tight_layout()
        
        return fig

def cross_validate_strategy(
    strategy_fn: Callable,
    X: pd.DataFrame,
    y: Optional[pd.Series] = None,
    cv: Union[TimeSeriesCrossValidator, int] = 5,
    strategy_params: Dict = None,
    scoring_fn: Callable = None,
    return_models: bool = False,
    return_predictions: bool = False,
    verbose: bool = False,
    save_dir: Optional[str] = None
) -> Dict:
    """
    Cross-validate a trading strategy using time series cross-validation.
    
    Args:
        strategy_fn: Function that takes (X_train, y_train, params) and returns a fitted model
        X: Features dataframe with DatetimeIndex
        y: Target variable
        cv: TimeSeriesCrossValidator instance or number of folds
        strategy_params: Parameters to pass to the strategy function
        scoring_fn: Function to score predictions, takes (y_true, y_pred) and returns a score
        return_models: Whether to return the fitted models
        return_predictions: Whether to return the predictions
        verbose: Whether to print progress
        save_dir: Directory to save models and results
        
    Returns:
        Dictionary with cross-validation results
    """
    # Initialize parameters
    strategy_params = strategy_params or {}
    
    # Create cross-validator if integer is provided
    if isinstance(cv, int):
        cv = TimeSeriesCrossValidator(n_splits=cv)
    
    # Get splits
    splits = cv.split(X, y)
    n_splits = len(splits)
    
    # Initialize results
    scores = []
    models = []
    all_predictions = pd.Series(index=X.index)
    fold_indices = {}
    
    # Cross-validate
    for i, (train_idx, test_idx) in enumerate(splits):
        if verbose:
            logger.info(f"Fold {i+1}/{n_splits}")
            logger.info(f"Train size: {len(train_idx)}, Test size: {len(test_idx)}")
        
        # Split data
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        
        if y is not None:
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        else:
            y_train, y_test = None, None
        
        # Fit model
        model = strategy_fn(X_train, y_train, **strategy_params)
        
        # Make predictions
        if hasattr(model, 'predict'):
            y_pred = model.predict(X_test)
        elif hasattr(model, 'predict_proba'):
            y_pred = model.predict_proba(X_test)[:, 1]
        elif callable(model):
            # If model is a function, call it directly
            y_pred = model(X_test)
        else:
            raise ValueError("Model must have predict or predict_proba method, or be callable")
        
        # Store predictions
        all_predictions.iloc[test_idx] = y_pred
        fold_indices[f"fold_{i+1}"] = {"train": train_idx, "test": test_idx}
        
        # Score predictions
        if scoring_fn is not None and y_test is not None:
            score = scoring_fn(y_test, y_pred)
            scores.append(score)
            
            if verbose:
                logger.info(f"Fold {i+1} score: {score:.4f}")
        
        # Store model
        if return_models:
            models.append(model)
            
        # Save model if directory is provided
        if save_dir is not None:
            os.makedirs(save_dir, exist_ok=True)
            model_path = os.path.join(save_dir, f"model_fold_{i+1}.joblib")
            joblib.dump(model, model_path)
            
            if verbose:
                logger.info(f"Saved model to {model_path}")
    
    # Prepare results
    results = {
        "cv_method": cv.cv_method,
        "n_splits": n_splits,
        "fold_indices": fold_indices
    }
    
    if scores:
        results["scores"] = scores
        results["mean_score"] = np.mean(scores)
        results["std_score"] = np.std(scores)
        
    if return_predictions:
        results["predictions"] = all_predictions
        
    if return_models:
        results["models"] = models
    
    # Save results if directory is provided
    if save_dir is not None:
        os.makedirs(save_dir, exist_ok=True)
        results_path = os.path.join(save_dir, "cv_results.joblib")
        joblib.dump(results, results_path)
        
        if verbose:
            logger.info(f"Saved results to {results_path}")
    
    return results

def evaluate_predictions(
    y_true: pd.Series,
    y_pred: pd.Series,
    metrics: List[Callable] = None,
    threshold: float = 0.5
) -> Dict:
    """
    Evaluate predictions using multiple metrics.
    
    Args:
        y_true: True values
        y_pred: Predicted values
        metrics: List of metric functions
        threshold: Threshold for binary classification
        
    Returns:
        Dictionary with evaluation results
    """
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, mean_squared_error, mean_absolute_error, r2_score
    )
    
    # Default metrics
    if metrics is None:
        # Check if binary classification or regression
        if set(np.unique(y_true)) == {0, 1}:
            # Binary classification
            metrics = [
                ('accuracy', lambda y_t, y_p: accuracy_score(y_t, y_p > threshold)),
                ('precision', lambda y_t, y_p: precision_score(y_t, y_p > threshold)),
                ('recall', lambda y_t, y_p: recall_score(y_t, y_p > threshold)),
                ('f1', lambda y_t, y_p: f1_score(y_t, y_p > threshold)),
                ('roc_auc', roc_auc_score)
            ]
        else:
            # Regression
            metrics = [
                ('mse', mean_squared_error),
                ('rmse', lambda y_t, y_p: np.sqrt(mean_squared_error(y_t, y_p))),
                ('mae', mean_absolute_error),
                ('r2', r2_score)
            ]
    
    # Calculate metrics
    results = {}
    for name, metric_fn in metrics:
        try:
            results[name] = metric_fn(y_true, y_pred)
        except Exception as e:
            logger.warning(f"Error calculating {name}: {e}")
            results[name] = None
    
    return results

def feature_importance_cv(
    strategy_fn: Callable,
    X: pd.DataFrame,
    y: pd.Series,
    cv: Union[TimeSeriesCrossValidator, int] = 5,
    strategy_params: Dict = None,
    importance_method: str = "permutation",
    n_repeats: int = 10,
    random_state: Optional[int] = None,
    n_jobs: int = -1
) -> pd.DataFrame:
    """
    Calculate feature importance across cross-validation folds.
    
    Args:
        strategy_fn: Function that takes (X_train, y_train, params) and returns a fitted model
        X: Features dataframe with DatetimeIndex
        y: Target variable
        cv: TimeSeriesCrossValidator instance or number of folds
        strategy_params: Parameters to pass to the strategy function
        importance_method: Method to calculate feature importance:
            - "permutation": Permutation importance
            - "shap": SHAP values
            - "built_in": Use model's feature_importances_ or coef_ attribute
        n_repeats: Number of repeats for permutation importance
        random_state: Random seed for reproducibility
        n_jobs: Number of jobs for parallel processing
        
    Returns:
        DataFrame with feature importances
    """
    from sklearn.inspection import permutation_importance
    
    # Initialize parameters
    strategy_params = strategy_params or {}
    
    # Create cross-validator if integer is provided
    if isinstance(cv, int):
        cv = TimeSeriesCrossValidator(n_splits=cv)
    
    # Get splits
    splits = cv.split(X, y)
    
    # Initialize results
    importances = []
    
    # Cross-validate
    for i, (train_idx, test_idx) in enumerate(splits):
        # Split data
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        # Fit model
        model = strategy_fn(X_train, y_train, **strategy_params)
        
        # Calculate feature importance
        if importance_method == "permutation":
            # Permutation importance
            perm_importance = permutation_importance(
                model, X_test, y_test, 
                n_repeats=n_repeats, 
                random_state=random_state,
                n_jobs=n_jobs
            )
            fold_importance = pd.Series(
                perm_importance.importances_mean,
                index=X.columns
            )
            
        elif importance_method == "shap":
            # SHAP values
            try:
                import shap
                explainer = shap.Explainer(model, X_train)
                shap_values = explainer(X_test)
                fold_importance = pd.Series(
                    np.abs(shap_values.values).mean(axis=0),
                    index=X.columns
                )
            except ImportError:
                logger.warning("SHAP not installed. Using permutation importance instead.")
                perm_importance = permutation_importance(
                    model, X_test, y_test, 
                    n_repeats=n_repeats, 
                    random_state=random_state,
                    n_jobs=n_jobs
                )
                fold_importance = pd.Series(
                    perm_importance.importances_mean,
                    index=X.columns
                )
                
        elif importance_method == "built_in":
            # Built-in feature importance
            if hasattr(model, "feature_importances_"):
                fold_importance = pd.Series(
                    model.feature_importances_,
                    index=X.columns
                )
            elif hasattr(model, "coef_"):
                fold_importance = pd.Series(
                    np.abs(model.coef_),
                    index=X.columns
                )
            else:
                logger.warning("Model has no built-in feature importance. Using permutation importance instead.")
                perm_importance = permutation_importance(
                    model, X_test, y_test, 
                    n_repeats=n_repeats, 
                    random_state=random_state,
                    n_jobs=n_jobs
                )
                fold_importance = pd.Series(
                    perm_importance.importances_mean,
                    index=X.columns
                )
        else:
            raise ValueError(f"Unknown importance method: {importance_method}")
        
        # Store importance
        importances.append(fold_importance)
    
    # Combine importances
    importance_df = pd.concat(importances, axis=1)
    importance_df.columns = [f"fold_{i+1}" for i in range(len(importances))]
    
    # Calculate mean and std
    importance_df["mean"] = importance_df.mean(axis=1)
    importance_df["std"] = importance_df.std(axis=1)
    
    # Sort by mean importance
    importance_df = importance_df.sort_values("mean", ascending=False)
    
    return importance_df

def plot_feature_importance(
    importance_df: pd.DataFrame,
    top_n: int = 20,
    figsize: Tuple[int, int] = (12, 10)
) -> plt.Figure:
    """
    Plot feature importance.
    
    Args:
        importance_df: DataFrame with feature importances
        top_n: Number of top features to plot
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    # Get top features
    top_features = importance_df.head(top_n)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot feature importance
    top_features["mean"].sort_values().plot(
        kind="barh", 
        xerr=top_features["std"],
        ax=ax
    )
    
    ax.set_title("Feature Importance")
    ax.set_xlabel("Importance")
    ax.set_ylabel("Feature")
    
    plt.tight_layout()
    
    return fig

def plot_cv_predictions(
    y_true: pd.Series,
    y_pred: pd.Series,
    figsize: Tuple[int, int] = (15, 10)
) -> plt.Figure:
    """
    Plot cross-validation predictions.
    
    Args:
        y_true: True values
        y_pred: Predicted values
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot true values
    ax.plot(y_true.index, y_true, label="True", color="blue", alpha=0.7)
    
    # Plot predictions
    ax.scatter(y_pred.index, y_pred, label="Predicted", color="red", alpha=0.5, s=20)
    
    # Add regression line
    if len(y_true) > 1 and len(y_pred) > 1:
        from sklearn.linear_model import LinearRegression
        
        # Filter out NaN values
        valid_mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        if valid_mask.sum() > 1:
            X_reg = y_true[valid_mask].values.reshape(-1, 1)
            y_reg = y_pred[valid_mask].values
            
            reg = LinearRegression().fit(X_reg, y_reg)
            
            # Plot regression line
            x_range = np.linspace(y_true.min(), y_true.max(), 100)
            y_range = reg.predict(x_range.reshape(-1, 1))
            
            ax.plot(x_range, y_range, "--", color="green", 
                   label=f"Fit: y={reg.coef_[0]:.2f}x+{reg.intercept_:.2f}")
    
    ax.set_title("Cross-Validation Predictions")
    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    ax.legend()
    
    plt.tight_layout()
    
    return fig 