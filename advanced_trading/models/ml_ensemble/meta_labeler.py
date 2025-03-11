"""
Meta-Labeling Module
-------------------
This module provides tools for implementing meta-labeling strategies in financial
machine learning applications. Meta-labeling is a technique where a primary model
predicts the direction (or another target variable), and a secondary model predicts
whether the primary model's prediction will be correct.

The module includes:
1. Various meta-labeling strategies
2. Performance evaluation for meta-labeled strategies
3. Regime-specific meta-labeling
4. Visualization tools for meta-labeling analysis
5. Convenience functions for quick implementation

Key classes:
- MetaLabeler: Main class for implementing meta-labeling strategies
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Union, Optional, Tuple, Callable, Any
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_predict
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
import logging

# Configure logging
logger = logging.getLogger(__name__)

class MetaLabeler:
    """
    A class for implementing meta-labeling strategies in financial machine learning.
    
    Meta-labeling is a technique where a primary model predicts the direction
    (or another target variable), and a secondary model (the meta-labeler) predicts
    whether the primary model's prediction will be correct.
    
    This approach can significantly improve trading strategy performance by filtering
    out false positives from the primary model, leading to higher precision.
    
    Parameters
    ----------
    primary_model : BaseEstimator, optional
        The primary model that predicts the direction or target variable.
        If None, the primary predictions must be provided during fitting.
    
    meta_model : BaseEstimator, optional
        The meta-model that predicts whether the primary model's predictions will be correct.
        If None, a default RandomForestClassifier will be used.
    
    threshold : float, default=0.5
        The probability threshold for the meta-model to consider a prediction valid.
    
    regime_aware : bool, default=True
        Whether to use regime-specific meta-labeling.
    
    cv : int, default=5
        Number of cross-validation folds for meta-model training.
    
    Attributes
    ----------
    primary_model : BaseEstimator
        The fitted primary model.
    
    meta_models : dict
        Dictionary of fitted meta-models for each regime.
    
    performance_metrics : dict
        Dictionary of performance metrics for the meta-labeling strategy.
    """
    
    def __init__(
        self,
        primary_model: Optional[BaseEstimator] = None,
        meta_model: Optional[BaseEstimator] = None,
        threshold: float = 0.5,
        regime_aware: bool = True,
        cv: int = 5
    ):
        """
        Initialize the MetaLabeler.
        
        Parameters
        ----------
        primary_model : BaseEstimator, optional
            The primary model that predicts the direction or target variable.
            If None, the primary predictions must be provided during fitting.
        
        meta_model : BaseEstimator, optional
            The meta-model that predicts whether the primary model's predictions will be correct.
            If None, a default RandomForestClassifier will be used.
        
        threshold : float, default=0.5
            The probability threshold for the meta-model to consider a prediction valid.
        
        regime_aware : bool, default=True
            Whether to use regime-specific meta-labeling.
        
        cv : int, default=5
            Number of cross-validation folds for meta-model training.
        """
        self.primary_model = primary_model
        self.meta_model = meta_model if meta_model is not None else RandomForestClassifier(n_estimators=100, random_state=42)
        self.threshold = threshold
        self.regime_aware = regime_aware
        self.cv = cv
        self.meta_models = {}
        self.performance_metrics = {}
        
        logger.info(f"Initialized MetaLabeler with threshold={threshold}, regime_aware={regime_aware}")
    
    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        primary_predictions: Optional[Union[pd.Series, np.ndarray]] = None,
        regimes: Optional[Union[pd.Series, np.ndarray]] = None,
        sample_weights: Optional[Union[pd.Series, np.ndarray]] = None,
        meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None
    ) -> 'MetaLabeler':
        """
        Fit the meta-labeling model.
        
        Parameters
        ----------
        X : array-like
            Features for the primary model (if primary_model is provided) and meta-model.
        
        y : array-like
            Target variable for the primary model.
        
        primary_predictions : array-like, optional
            Predictions from the primary model. If None, the primary_model will be used to generate predictions.
        
        regimes : array-like, optional
            Regime labels for each sample. If provided and regime_aware=True,
            separate meta-models will be fit for each regime.
        
        sample_weights : array-like, optional
            Sample weights for fitting the meta-model.
        
        meta_features : array-like, optional
            Additional features for the meta-model. If provided, these will be combined with X.
        
        Returns
        -------
        self : MetaLabeler
            The fitted meta-labeler.
        """
        # Convert inputs to numpy arrays
        X = self._to_numpy(X)
        y = self._to_numpy(y)
        
        # Fit primary model if provided and generate predictions
        if primary_predictions is None:
            if self.primary_model is None:
                raise ValueError("Either primary_model or primary_predictions must be provided")
            
            logger.info("Fitting primary model...")
            self.primary_model.fit(X, y)
            
            # Generate primary predictions using cross-validation to avoid overfitting
            logger.info("Generating primary predictions using cross-validation...")
            if hasattr(self.primary_model, 'predict_proba'):
                primary_proba = cross_val_predict(self.primary_model, X, y, cv=self.cv, method='predict_proba')
                primary_predictions = (primary_proba[:, 1] > 0.5).astype(int)
            else:
                primary_predictions = cross_val_predict(self.primary_model, X, y, cv=self.cv)
        else:
            primary_predictions = self._to_numpy(primary_predictions)
        
        # Create meta-labels: 1 if primary prediction is correct, 0 otherwise
        meta_labels = (primary_predictions == y).astype(int)
        
        # Prepare meta-features
        if meta_features is not None:
            meta_features = self._to_numpy(meta_features)
            meta_X = np.hstack((X, meta_features))
        else:
            meta_X = X
        
        # Regime-specific meta-labeling
        if self.regime_aware and regimes is not None:
            regimes = self._to_numpy(regimes)
            unique_regimes = np.unique(regimes)
            
            for regime in unique_regimes:
                regime_mask = (regimes == regime)
                regime_meta_X = meta_X[regime_mask]
                regime_meta_labels = meta_labels[regime_mask]
                
                if sample_weights is not None:
                    regime_weights = sample_weights[regime_mask]
                else:
                    regime_weights = None
                
                # Fit meta-model for this regime
                logger.info(f"Fitting meta-model for regime '{regime}'...")
                meta_model = self._clone_meta_model()
                meta_model.fit(regime_meta_X, regime_meta_labels, sample_weight=regime_weights)
                self.meta_models[regime] = meta_model
                
                # Evaluate meta-model for this regime
                self._evaluate_meta_model(
                    meta_X=regime_meta_X,
                    meta_labels=regime_meta_labels,
                    primary_predictions=primary_predictions[regime_mask],
                    y_true=y[regime_mask],
                    regime=regime
                )
            
            logger.info(f"Fitted regime-specific meta-models for {len(unique_regimes)} regimes")
        else:
            # Global meta-labeling
            logger.info("Fitting global meta-model...")
            meta_model = self._clone_meta_model()
            meta_model.fit(meta_X, meta_labels, sample_weight=sample_weights)
            self.meta_models['global'] = meta_model
            
            # Evaluate global meta-model
            self._evaluate_meta_model(
                meta_X=meta_X,
                meta_labels=meta_labels,
                primary_predictions=primary_predictions,
                y_true=y,
                regime='global'
            )
        
        return self
    
    def predict(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        primary_predictions: Optional[Union[pd.Series, np.ndarray]] = None,
        regime: Optional[str] = None,
        meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        return_probabilities: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Generate meta-labeled predictions.
        
        Parameters
        ----------
        X : array-like
            Features for the primary model (if primary_predictions is None) and meta-model.
        
        primary_predictions : array-like, optional
            Predictions from the primary model. If None, the primary_model will be used to generate predictions.
        
        regime : str, optional
            The regime to use for meta-labeling. If None and regime_aware=True,
            the global meta-model will be used.
        
        meta_features : array-like, optional
            Additional features for the meta-model. If provided, these will be combined with X.
        
        return_probabilities : bool, default=False
            Whether to return meta-model probabilities along with the filtered predictions.
        
        Returns
        -------
        filtered_predictions : ndarray
            Primary predictions filtered by the meta-model.
        
        meta_probabilities : ndarray, optional
            Probabilities from the meta-model. Only returned if return_probabilities=True.
        """
        # Convert inputs to numpy arrays
        X = self._to_numpy(X)
        
        # Generate primary predictions if not provided
        if primary_predictions is None:
            if self.primary_model is None:
                raise ValueError("Either primary_model or primary_predictions must be provided")
            
            logger.info("Generating primary predictions...")
            if hasattr(self.primary_model, 'predict_proba'):
                primary_proba = self.primary_model.predict_proba(X)
                primary_predictions = (primary_proba[:, 1] > 0.5).astype(int)
            else:
                primary_predictions = self.primary_model.predict(X)
        else:
            primary_predictions = self._to_numpy(primary_predictions)
        
        # Prepare meta-features
        if meta_features is not None:
            meta_features = self._to_numpy(meta_features)
            meta_X = np.hstack((X, meta_features))
        else:
            meta_X = X
        
        # Determine which meta-model to use
        if regime is not None and regime in self.meta_models:
            meta_model = self.meta_models[regime]
            logger.debug(f"Using regime-specific meta-model for regime '{regime}'")
        elif 'global' in self.meta_models:
            meta_model = self.meta_models['global']
            logger.debug("Using global meta-model")
        else:
            logger.warning("No meta-model found, returning primary predictions")
            if return_probabilities:
                return primary_predictions, np.ones(len(primary_predictions))
            else:
                return primary_predictions
        
        # Generate meta-model probabilities
        if hasattr(meta_model, 'predict_proba'):
            meta_probabilities = meta_model.predict_proba(meta_X)[:, 1]
        else:
            meta_probabilities = meta_model.predict(meta_X).astype(float)
        
        # Filter primary predictions using meta-model
        filtered_predictions = np.zeros_like(primary_predictions)
        mask = (meta_probabilities >= self.threshold)
        filtered_predictions[mask] = primary_predictions[mask]
        
        if return_probabilities:
            return filtered_predictions, meta_probabilities
        else:
            return filtered_predictions
    
    def evaluate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        primary_predictions: Optional[Union[pd.Series, np.ndarray]] = None,
        regimes: Optional[Union[pd.Series, np.ndarray]] = None,
        meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate the meta-labeling strategy.
        
        Parameters
        ----------
        X : array-like
            Features for the primary model (if primary_predictions is None) and meta-model.
        
        y : array-like
            True target values.
        
        primary_predictions : array-like, optional
            Predictions from the primary model. If None, the primary_model will be used to generate predictions.
        
        regimes : array-like, optional
            Regime labels for each sample. If provided, evaluation will be performed for each regime.
        
        meta_features : array-like, optional
            Additional features for the meta-model. If provided, these will be combined with X.
        
        Returns
        -------
        metrics : dict
            Dictionary of evaluation metrics.
        """
        # Convert inputs to numpy arrays
        X = self._to_numpy(X)
        y = self._to_numpy(y)
        
        # Generate primary predictions if not provided
        if primary_predictions is None:
            if self.primary_model is None:
                raise ValueError("Either primary_model or primary_predictions must be provided")
            
            logger.info("Generating primary predictions...")
            if hasattr(self.primary_model, 'predict_proba'):
                primary_proba = self.primary_model.predict_proba(X)
                primary_predictions = (primary_proba[:, 1] > 0.5).astype(int)
            else:
                primary_predictions = self.primary_model.predict(X)
        else:
            primary_predictions = self._to_numpy(primary_predictions)
        
        # Evaluate primary model
        primary_metrics = self._calculate_metrics(y, primary_predictions)
        
        # Generate meta-labeled predictions
        meta_predictions, meta_probabilities = self.predict(
            X=X,
            primary_predictions=primary_predictions,
            meta_features=meta_features,
            return_probabilities=True
        )
        
        # Evaluate meta-labeled predictions
        meta_metrics = self._calculate_metrics(y, meta_predictions)
        
        # Calculate improvement
        improvement = {}
        for metric in primary_metrics:
            if metric in ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']:
                improvement[metric] = meta_metrics[metric] - primary_metrics[metric]
        
        # Combine metrics
        metrics = {
            'primary': primary_metrics,
            'meta': meta_metrics,
            'improvement': improvement
        }
        
        # Regime-specific evaluation
        if regimes is not None:
            regimes = self._to_numpy(regimes)
            unique_regimes = np.unique(regimes)
            
            regime_metrics = {}
            for regime in unique_regimes:
                regime_mask = (regimes == regime)
                
                # Skip if too few samples
                if np.sum(regime_mask) < 10:
                    logger.warning(f"Too few samples for regime '{regime}', skipping evaluation")
                    continue
                
                # Evaluate primary model for this regime
                regime_primary_metrics = self._calculate_metrics(
                    y[regime_mask],
                    primary_predictions[regime_mask]
                )
                
                # Generate meta-labeled predictions for this regime
                regime_meta_predictions, regime_meta_probabilities = self.predict(
                    X=X[regime_mask],
                    primary_predictions=primary_predictions[regime_mask],
                    regime=regime,
                    meta_features=None if meta_features is None else meta_features[regime_mask],
                    return_probabilities=True
                )
                
                # Evaluate meta-labeled predictions for this regime
                regime_meta_metrics = self._calculate_metrics(
                    y[regime_mask],
                    regime_meta_predictions
                )
                
                # Calculate improvement for this regime
                regime_improvement = {}
                for metric in regime_primary_metrics:
                    if metric in ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']:
                        regime_improvement[metric] = regime_meta_metrics[metric] - regime_primary_metrics[metric]
                
                # Combine metrics for this regime
                regime_metrics[regime] = {
                    'primary': regime_primary_metrics,
                    'meta': regime_meta_metrics,
                    'improvement': regime_improvement
                }
            
            metrics['regimes'] = regime_metrics
        
        return metrics
    
    def _evaluate_meta_model(
        self,
        meta_X: np.ndarray,
        meta_labels: np.ndarray,
        primary_predictions: np.ndarray,
        y_true: np.ndarray,
        regime: str = 'global'
    ) -> Dict[str, float]:
        """
        Evaluate the meta-model.
        
        Parameters
        ----------
        meta_X : ndarray
            Features for the meta-model.
        
        meta_labels : ndarray
            Meta-labels (1 if primary prediction is correct, 0 otherwise).
        
        primary_predictions : ndarray
            Predictions from the primary model.
        
        y_true : ndarray
            True target values.
        
        regime : str, default='global'
            The regime for which to evaluate the meta-model.
        
        Returns
        -------
        metrics : dict
            Dictionary of evaluation metrics.
        """
        # Get meta-model for this regime
        meta_model = self.meta_models[regime]
        
        # Generate meta-model predictions using cross-validation
        if hasattr(meta_model, 'predict_proba'):
            meta_proba = cross_val_predict(meta_model, meta_X, meta_labels, cv=self.cv, method='predict_proba')
            meta_predictions = (meta_proba[:, 1] >= self.threshold).astype(int)
        else:
            meta_predictions = cross_val_predict(meta_model, meta_X, meta_labels, cv=self.cv)
        
        # Calculate meta-model metrics
        meta_model_metrics = {
            'accuracy': accuracy_score(meta_labels, meta_predictions),
            'precision': precision_score(meta_labels, meta_predictions, zero_division=0),
            'recall': recall_score(meta_labels, meta_predictions, zero_division=0),
            'f1': f1_score(meta_labels, meta_predictions, zero_division=0)
        }
        
        if hasattr(meta_model, 'predict_proba'):
            meta_model_metrics['roc_auc'] = roc_auc_score(meta_labels, meta_proba[:, 1])
        
        # Filter primary predictions using meta-model
        filtered_predictions = np.zeros_like(primary_predictions)
        mask = (meta_predictions == 1)
        filtered_predictions[mask] = primary_predictions[mask]
        
        # Calculate filtered predictions metrics
        filtered_metrics = self._calculate_metrics(y_true, filtered_predictions)
        
        # Calculate primary predictions metrics
        primary_metrics = self._calculate_metrics(y_true, primary_predictions)
        
        # Calculate improvement
        improvement = {}
        for metric in primary_metrics:
            if metric in ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']:
                improvement[metric] = filtered_metrics[metric] - primary_metrics[metric]
        
        # Combine metrics
        metrics = {
            'meta_model': meta_model_metrics,
            'primary': primary_metrics,
            'filtered': filtered_metrics,
            'improvement': improvement
        }
        
        self.performance_metrics[regime] = metrics
        return metrics
    
    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate evaluation metrics.
        
        Parameters
        ----------
        y_true : ndarray
            True target values.
        
        y_pred : ndarray
            Predicted values.
        
        Returns
        -------
        metrics : dict
            Dictionary of evaluation metrics.
        """
        # Handle case where all predictions are 0 (no trades)
        if np.sum(y_pred) == 0:
            return {
                'accuracy': np.mean(y_true == y_pred),
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
                'support': len(y_true),
                'trades': 0,
                'correct_trades': 0,
                'trade_accuracy': 0.0
            }
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'support': len(y_true),
            'trades': np.sum(y_pred),
            'correct_trades': np.sum((y_pred == 1) & (y_true == 1)),
            'trade_accuracy': np.sum((y_pred == 1) & (y_true == 1)) / np.sum(y_pred)
        }
        
        return metrics
    
    def _clone_meta_model(self) -> BaseEstimator:
        """
        Create a clone of the meta-model.
        
        Returns
        -------
        meta_model : BaseEstimator
            A clone of the meta-model.
        """
        from sklearn.base import clone
        return clone(self.meta_model)
    
    def _to_numpy(self, data: Union[pd.Series, pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Convert data to numpy array.
        
        Parameters
        ----------
        data : array-like
            Data to convert.
        
        Returns
        -------
        data_np : ndarray
            Data as numpy array.
        """
        if isinstance(data, (pd.Series, pd.DataFrame)):
            return data.values
        return np.asarray(data)
    
    def visualize_meta_model_performance(
        self,
        regime: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> None:
        """
        Visualize the meta-model performance.
        
        Parameters
        ----------
        regime : str, optional
            The regime for which to visualize performance. If None, the global meta-model will be used.
        
        figsize : tuple, default=(12, 8)
            Figure size.
        """
        # Determine which regime to use
        if regime is not None and regime in self.performance_metrics:
            metrics = self.performance_metrics[regime]
            title_suffix = f" - Regime: {regime}"
        elif 'global' in self.performance_metrics:
            metrics = self.performance_metrics['global']
            title_suffix = " - Global"
        else:
            logger.warning("No performance metrics found, cannot visualize")
            return
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Plot meta-model metrics (left subplot)
        meta_model_metrics = metrics['meta_model']
        meta_metrics = list(meta_model_metrics.keys())
        meta_values = [meta_model_metrics[m] for m in meta_metrics]
        
        ax1.bar(meta_metrics, meta_values, alpha=0.7)
        ax1.set_title(f"Meta-Model Metrics{title_suffix}")
        ax1.set_ylim(0, 1)
        ax1.grid(True, alpha=0.3)
        
        # Add value labels
        for i, v in enumerate(meta_values):
            ax1.text(i, v + 0.02, f"{v:.3f}", ha='center', va='bottom', fontsize=10)
        
        # Plot improvement metrics (right subplot)
        improvement = metrics['improvement']
        imp_metrics = list(improvement.keys())
        imp_values = [improvement[m] for m in imp_metrics]
        
        colors = ['g' if v >= 0 else 'r' for v in imp_values]
        ax2.bar(imp_metrics, imp_values, alpha=0.7, color=colors)
        ax2.set_title(f"Performance Improvement{title_suffix}")
        ax2.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        ax2.grid(True, alpha=0.3)
        
        # Add value labels
        for i, v in enumerate(imp_values):
            ax2.text(i, v + 0.02 if v >= 0 else v - 0.05, f"{v:.3f}", ha='center', va='bottom' if v >= 0 else 'top', fontsize=10)
        
        plt.tight_layout()
        plt.show()
    
    def visualize_trade_filtering(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        primary_predictions: Optional[Union[pd.Series, np.ndarray]] = None,
        meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        regime: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> None:
        """
        Visualize the trade filtering effect of meta-labeling.
        
        Parameters
        ----------
        X : array-like
            Features for the primary model (if primary_predictions is None) and meta-model.
        
        y : array-like
            True target values.
        
        primary_predictions : array-like, optional
            Predictions from the primary model. If None, the primary_model will be used to generate predictions.
        
        meta_features : array-like, optional
            Additional features for the meta-model. If provided, these will be combined with X.
        
        regime : str, optional
            The regime to use for meta-labeling. If None, the global meta-model will be used.
        
        figsize : tuple, default=(12, 8)
            Figure size.
        """
        # Convert inputs to numpy arrays
        X = self._to_numpy(X)
        y = self._to_numpy(y)
        
        # Generate primary predictions if not provided
        if primary_predictions is None:
            if self.primary_model is None:
                raise ValueError("Either primary_model or primary_predictions must be provided")
            
            logger.info("Generating primary predictions...")
            if hasattr(self.primary_model, 'predict_proba'):
                primary_proba = self.primary_model.predict_proba(X)
                primary_predictions = (primary_proba[:, 1] > 0.5).astype(int)
            else:
                primary_predictions = self.primary_model.predict(X)
        else:
            primary_predictions = self._to_numpy(primary_predictions)
        
        # Generate meta-labeled predictions
        meta_predictions, meta_probabilities = self.predict(
            X=X,
            primary_predictions=primary_predictions,
            regime=regime,
            meta_features=meta_features,
            return_probabilities=True
        )
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Plot confusion matrix for primary model (left subplot)
        cm_primary = confusion_matrix(y, primary_predictions)
        ax1.imshow(cm_primary, interpolation='nearest', cmap=plt.cm.Blues, alpha=0.7)
        ax1.set_title(f"Primary Model Confusion Matrix")
        ax1.set_xlabel("Predicted Label")
        ax1.set_ylabel("True Label")
        ax1.set_xticks([0, 1])
        ax1.set_yticks([0, 1])
        ax1.set_xticklabels(['0', '1'])
        ax1.set_yticklabels(['0', '1'])
        
        # Add text annotations
        thresh = cm_primary.max() / 2.0
        for i in range(cm_primary.shape[0]):
            for j in range(cm_primary.shape[1]):
                ax1.text(j, i, format(cm_primary[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm_primary[i, j] > thresh else "black")
        
        # Plot confusion matrix for meta-labeled model (right subplot)
        cm_meta = confusion_matrix(y, meta_predictions)
        ax2.imshow(cm_meta, interpolation='nearest', cmap=plt.cm.Blues, alpha=0.7)
        ax2.set_title(f"Meta-Labeled Model Confusion Matrix")
        ax2.set_xlabel("Predicted Label")
        ax2.set_ylabel("True Label")
        ax2.set_xticks([0, 1])
        ax2.set_yticks([0, 1])
        ax2.set_xticklabels(['0', '1'])
        ax2.set_yticklabels(['0', '1'])
        
        # Add text annotations
        thresh = cm_meta.max() / 2.0
        for i in range(cm_meta.shape[0]):
            for j in range(cm_meta.shape[1]):
                ax2.text(j, i, format(cm_meta[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm_meta[i, j] > thresh else "black")
        
        plt.tight_layout()
        plt.show()
        
        # Calculate and print metrics
        primary_metrics = self._calculate_metrics(y, primary_predictions)
        meta_metrics = self._calculate_metrics(y, meta_predictions)
        
        print("Primary Model Metrics:")
        print(f"Accuracy: {primary_metrics['accuracy']:.4f}")
        print(f"Precision: {primary_metrics['precision']:.4f}")
        print(f"Recall: {primary_metrics['recall']:.4f}")
        print(f"F1: {primary_metrics['f1']:.4f}")
        print(f"Trades: {primary_metrics['trades']} ({primary_metrics['trades'] / len(y):.2%} of samples)")
        print(f"Correct Trades: {primary_metrics['correct_trades']} ({primary_metrics['correct_trades'] / primary_metrics['trades']:.2%} of trades)")
        
        print("\nMeta-Labeled Model Metrics:")
        print(f"Accuracy: {meta_metrics['accuracy']:.4f}")
        print(f"Precision: {meta_metrics['precision']:.4f}")
        print(f"Recall: {meta_metrics['recall']:.4f}")
        print(f"F1: {meta_metrics['f1']:.4f}")
        print(f"Trades: {meta_metrics['trades']} ({meta_metrics['trades'] / len(y):.2%} of samples)")
        print(f"Correct Trades: {meta_metrics['correct_trades']} ({meta_metrics['correct_trades'] / meta_metrics['trades'] if meta_metrics['trades'] > 0 else 0:.2%} of trades)")
        
        # Calculate improvement
        trades_reduction = primary_metrics['trades'] - meta_metrics['trades']
        trades_reduction_pct = trades_reduction / primary_metrics['trades'] if primary_metrics['trades'] > 0 else 0
        
        precision_improvement = meta_metrics['precision'] - primary_metrics['precision']
        precision_improvement_pct = precision_improvement / primary_metrics['precision'] if primary_metrics['precision'] > 0 else 0
        
        print("\nImprovements:")
        print(f"Trades Reduction: {trades_reduction} ({trades_reduction_pct:.2%})")
        print(f"Precision Improvement: {precision_improvement:.4f} ({precision_improvement_pct:.2%})")
    
    def visualize_threshold_impact(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        primary_predictions: Optional[Union[pd.Series, np.ndarray]] = None,
        meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        regime: Optional[str] = None,
        thresholds: Optional[List[float]] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> None:
        """
        Visualize the impact of different threshold values on meta-labeling performance.
        
        Parameters
        ----------
        X : array-like
            Features for the primary model (if primary_predictions is None) and meta-model.
        
        y : array-like
            True target values.
        
        primary_predictions : array-like, optional
            Predictions from the primary model. If None, the primary_model will be used to generate predictions.
        
        meta_features : array-like, optional
            Additional features for the meta-model. If provided, these will be combined with X.
        
        regime : str, optional
            The regime to use for meta-labeling. If None, the global meta-model will be used.
        
        thresholds : list, optional
            List of threshold values to evaluate. If None, a range of thresholds will be used.
        
        figsize : tuple, default=(12, 8)
            Figure size.
        """
        # Convert inputs to numpy arrays
        X = self._to_numpy(X)
        y = self._to_numpy(y)
        
        # Generate primary predictions if not provided
        if primary_predictions is None:
            if self.primary_model is None:
                raise ValueError("Either primary_model or primary_predictions must be provided")
            
            logger.info("Generating primary predictions...")
            if hasattr(self.primary_model, 'predict_proba'):
                primary_proba = self.primary_model.predict_proba(X)
                primary_predictions = (primary_proba[:, 1] > 0.5).astype(int)
            else:
                primary_predictions = self.primary_model.predict(X)
        else:
            primary_predictions = self._to_numpy(primary_predictions)
        
        # Prepare meta-features
        if meta_features is not None:
            meta_features = self._to_numpy(meta_features)
            meta_X = np.hstack((X, meta_features))
        else:
            meta_X = X
        
        # Determine which meta-model to use
        if regime is not None and regime in self.meta_models:
            meta_model = self.meta_models[regime]
            title_suffix = f" - Regime: {regime}"
        elif 'global' in self.meta_models:
            meta_model = self.meta_models['global']
            title_suffix = " - Global"
        else:
            logger.warning("No meta-model found, cannot visualize")
            return
        
        # Generate meta-model probabilities
        if hasattr(meta_model, 'predict_proba'):
            meta_probabilities = meta_model.predict_proba(meta_X)[:, 1]
        else:
            meta_probabilities = meta_model.predict(meta_X).astype(float)
        
        # Define thresholds if not provided
        if thresholds is None:
            thresholds = np.linspace(0.1, 0.9, 9)
        
        # Calculate metrics for each threshold
        precision_values = []
        recall_values = []
        f1_values = []
        trade_counts = []
        
        for threshold in thresholds:
            # Filter primary predictions using meta-model with this threshold
            filtered_predictions = np.zeros_like(primary_predictions)
            mask = (meta_probabilities >= threshold)
            filtered_predictions[mask] = primary_predictions[mask]
            
            # Calculate metrics
            metrics = self._calculate_metrics(y, filtered_predictions)
            precision_values.append(metrics['precision'])
            recall_values.append(metrics['recall'])
            f1_values.append(metrics['f1'])
            trade_counts.append(metrics['trades'])
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Plot precision, recall, and F1 (left subplot)
        ax1.plot(thresholds, precision_values, 'o-', label='Precision')
        ax1.plot(thresholds, recall_values, 's-', label='Recall')
        ax1.plot(thresholds, f1_values, '^-', label='F1')
        ax1.set_title(f"Metrics vs. Threshold{title_suffix}")
        ax1.set_xlabel("Threshold")
        ax1.set_ylabel("Metric Value")
        ax1.set_ylim(0, 1)
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Plot trade count (right subplot)
        ax2.plot(thresholds, trade_counts, 'o-')
        ax2.set_title(f"Trade Count vs. Threshold{title_suffix}")
        ax2.set_xlabel("Threshold")
        ax2.set_ylabel("Number of Trades")
        ax2.grid(True, alpha=0.3)
        
        # Add current threshold marker
        ax1.axvline(x=self.threshold, color='r', linestyle='--', alpha=0.5, label=f'Current Threshold ({self.threshold})')
        ax2.axvline(x=self.threshold, color='r', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        plt.show()
    
    def visualize_regime_comparison(
        self,
        regimes: List[str],
        metric: str = 'precision',
        figsize: Tuple[int, int] = (12, 6)
    ) -> None:
        """
        Visualize meta-labeling performance across different regimes.
        
        Parameters
        ----------
        regimes : list
            List of regimes to compare.
        
        metric : str, default='precision'
            Metric to visualize. Options include:
            - 'precision': Precision of meta-labeled predictions
            - 'recall': Recall of meta-labeled predictions
            - 'f1': F1 score of meta-labeled predictions
            - 'trades': Number of trades after meta-labeling
            - 'trade_reduction': Percentage of trades filtered out by meta-labeling
            - 'precision_improvement': Improvement in precision due to meta-labeling
        
        figsize : tuple, default=(12, 6)
            Figure size.
        """
        # Validate regimes
        valid_regimes = [r for r in regimes if r in self.performance_metrics]
        if not valid_regimes:
            logger.warning("No valid regimes found for comparison")
            return
        
        # Validate metric
        valid_metrics = ['precision', 'recall', 'f1', 'trades', 'trade_reduction', 'precision_improvement']
        if metric not in valid_metrics:
            logger.warning(f"Invalid metric: {metric}, using 'precision' instead")
            metric = 'precision'
        
        # Extract metric values for each regime
        primary_values = []
        filtered_values = []
        improvement_values = []
        
        for regime in valid_regimes:
            metrics = self.performance_metrics[regime]
            
            if metric in ['precision', 'recall', 'f1']:
                primary_values.append(metrics['primary'][metric])
                filtered_values.append(metrics['filtered'][metric])
                improvement_values.append(metrics['improvement'][metric])
            elif metric == 'trades':
                primary_values.append(metrics['primary']['trades'])
                filtered_values.append(metrics['filtered']['trades'])
                improvement_values.append(metrics['primary']['trades'] - metrics['filtered']['trades'])
            elif metric == 'trade_reduction':
                primary_trades = metrics['primary']['trades']
                filtered_trades = metrics['filtered']['trades']
                reduction = (primary_trades - filtered_trades) / primary_trades if primary_trades > 0 else 0
                primary_values.append(0)  # Not applicable
                filtered_values.append(reduction)
                improvement_values.append(reduction)
            elif metric == 'precision_improvement':
                primary_precision = metrics['primary']['precision']
                filtered_precision = metrics['filtered']['precision']
                improvement = filtered_precision - primary_precision
                primary_values.append(0)  # Not applicable
                filtered_values.append(improvement)
                improvement_values.append(improvement)
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Create bar plot
        x = np.arange(len(valid_regimes))
        width = 0.35
        
        if metric in ['precision', 'recall', 'f1', 'trades']:
            plt.bar(x - width/2, primary_values, width, label='Primary Model', alpha=0.7)
            plt.bar(x + width/2, filtered_values, width, label='Meta-Labeled Model', alpha=0.7)
            
            # Add value labels
            for i, v in enumerate(primary_values):
                plt.text(i - width/2, v + 0.02, f"{v:.2f}" if metric != 'trades' else f"{v}", ha='center', va='bottom', fontsize=10)
            
            for i, v in enumerate(filtered_values):
                plt.text(i + width/2, v + 0.02, f"{v:.2f}" if metric != 'trades' else f"{v}", ha='center', va='bottom', fontsize=10)
        else:
            plt.bar(x, filtered_values, width, alpha=0.7)
            
            # Add value labels
            for i, v in enumerate(filtered_values):
                plt.text(i, v + 0.02 if v >= 0 else v - 0.05, f"{v:.2%}", ha='center', va='bottom' if v >= 0 else 'top', fontsize=10)
        
        # Set plot properties
        plt.xlabel('Regime')
        plt.ylabel(metric.replace('_', ' ').title())
        plt.title(f"{metric.replace('_', ' ').title()} by Regime")
        plt.xticks(x, valid_regimes)
        plt.grid(True, alpha=0.3, axis='y')
        
        if metric in ['precision', 'recall', 'f1', 'trades']:
            plt.legend()
        
        plt.tight_layout()
        plt.show()
    
    def save(self, filepath: str) -> None:
        """
        Save the meta-labeler to a file.
        
        Parameters
        ----------
        filepath : str
            Path to save the meta-labeler.
        """
        import joblib
        joblib.dump(self, filepath)
        logger.info(f"Saved meta-labeler to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'MetaLabeler':
        """
        Load a meta-labeler from a file.
        
        Parameters
        ----------
        filepath : str
            Path to load the meta-labeler from.
        
        Returns
        -------
        meta_labeler : MetaLabeler
            The loaded meta-labeler.
        """
        import joblib
        meta_labeler = joblib.load(filepath)
        logger.info(f"Loaded meta-labeler from {filepath}")
        return meta_labeler


def apply_meta_labeling(
    X: Union[pd.DataFrame, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    primary_predictions: Union[pd.Series, np.ndarray],
    meta_model: Optional[BaseEstimator] = None,
    threshold: float = 0.5,
    regimes: Optional[Union[pd.Series, np.ndarray]] = None,
    meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None,
    return_meta_labeler: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, MetaLabeler]]:
    """
    Convenience function to apply meta-labeling to primary model predictions.
    
    Parameters
    ----------
    X : array-like
        Features for the meta-model.
    
    y : array-like
        True target values.
    
    primary_predictions : array-like
        Predictions from the primary model.
    
    meta_model : BaseEstimator, optional
        The meta-model to use. If None, a default RandomForestClassifier will be used.
    
    threshold : float, default=0.5
        The probability threshold for the meta-model to consider a prediction valid.
    
    regimes : array-like, optional
        Regime labels for each sample. If provided, separate meta-models will be fit for each regime.
    
    meta_features : array-like, optional
        Additional features for the meta-model. If provided, these will be combined with X.
    
    return_meta_labeler : bool, default=False
        Whether to return the fitted meta-labeler along with the filtered predictions.
    
    Returns
    -------
    filtered_predictions : ndarray
        Primary predictions filtered by the meta-model.
    
    meta_labeler : MetaLabeler, optional
        The fitted meta-labeler. Only returned if return_meta_labeler=True.
    """
    # Create and fit meta-labeler
    meta_labeler = MetaLabeler(
        primary_model=None,
        meta_model=meta_model,
        threshold=threshold,
        regime_aware=(regimes is not None)
    )
    
    meta_labeler.fit(
        X=X,
        y=y,
        primary_predictions=primary_predictions,
        regimes=regimes,
        meta_features=meta_features
    )
    
    # Generate meta-labeled predictions
    filtered_predictions = meta_labeler.predict(
        X=X,
        primary_predictions=primary_predictions,
        meta_features=meta_features
    )
    
    if return_meta_labeler:
        return filtered_predictions, meta_labeler
    else:
        return filtered_predictions


def evaluate_meta_labeling(
    X: Union[pd.DataFrame, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    primary_predictions: Union[pd.Series, np.ndarray],
    meta_model: Optional[BaseEstimator] = None,
    threshold: float = 0.5,
    regimes: Optional[Union[pd.Series, np.ndarray]] = None,
    meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None,
    visualize: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to evaluate meta-labeling performance.
    
    Parameters
    ----------
    X : array-like
        Features for the meta-model.
    
    y : array-like
        True target values.
    
    primary_predictions : array-like
        Predictions from the primary model.
    
    meta_model : BaseEstimator, optional
        The meta-model to use. If None, a default RandomForestClassifier will be used.
    
    threshold : float, default=0.5
        The probability threshold for the meta-model to consider a prediction valid.
    
    regimes : array-like, optional
        Regime labels for each sample. If provided, separate meta-models will be fit for each regime.
    
    meta_features : array-like, optional
        Additional features for the meta-model. If provided, these will be combined with X.
    
    visualize : bool, default=True
        Whether to visualize the meta-labeling performance.
    
    Returns
    -------
    metrics : dict
        Dictionary of evaluation metrics.
    """
    # Create and fit meta-labeler
    meta_labeler = MetaLabeler(
        primary_model=None,
        meta_model=meta_model,
        threshold=threshold,
        regime_aware=(regimes is not None)
    )
    
    meta_labeler.fit(
        X=X,
        y=y,
        primary_predictions=primary_predictions,
        regimes=regimes,
        meta_features=meta_features
    )
    
    # Evaluate meta-labeling
    metrics = meta_labeler.evaluate(
        X=X,
        y=y,
        primary_predictions=primary_predictions,
        regimes=regimes,
        meta_features=meta_features
    )
    
    # Visualize if requested
    if visualize:
        meta_labeler.visualize_meta_model_performance()
        meta_labeler.visualize_trade_filtering(
            X=X,
            y=y,
            primary_predictions=primary_predictions,
            meta_features=meta_features
        )
    
    return metrics


def optimize_meta_labeling_threshold(
    X: Union[pd.DataFrame, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    primary_predictions: Union[pd.Series, np.ndarray],
    meta_model: Optional[BaseEstimator] = None,
    regimes: Optional[Union[pd.Series, np.ndarray]] = None,
    meta_features: Optional[Union[pd.DataFrame, np.ndarray]] = None,
    thresholds: Optional[List[float]] = None,
    metric: str = 'f1',
    visualize: bool = True
) -> Tuple[float, Dict[str, Any]]:
    """
    Convenience function to find the optimal threshold for meta-labeling.
    
    Parameters
    ----------
    X : array-like
        Features for the meta-model.
    
    y : array-like
        True target values.
    
    primary_predictions : array-like
        Predictions from the primary model.
    
    meta_model : BaseEstimator, optional
        The meta-model to use. If None, a default RandomForestClassifier will be used.
    
    regimes : array-like, optional
        Regime labels for each sample. If provided, separate meta-models will be fit for each regime.
    
    meta_features : array-like, optional
        Additional features for the meta-model. If provided, these will be combined with X.
    
    thresholds : list, optional
        List of threshold values to evaluate. If None, a range of thresholds will be used.
    
    metric : str, default='f1'
        Metric to optimize. Options include:
        - 'precision': Maximize precision
        - 'recall': Maximize recall
        - 'f1': Maximize F1 score
        - 'accuracy': Maximize accuracy
        - 'trade_reduction': Maximize trade reduction while maintaining precision
    
    visualize : bool, default=True
        Whether to visualize the threshold optimization.
    
    Returns
    -------
    optimal_threshold : float
        The optimal threshold value.
    
    metrics : dict
        Dictionary of evaluation metrics for the optimal threshold.
    """
    # Create meta-labeler with initial threshold
    meta_labeler = MetaLabeler(
        primary_model=None,
        meta_model=meta_model,
        threshold=0.5,  # Initial threshold, will be optimized
        regime_aware=(regimes is not None)
    )
    
    # Fit meta-labeler
    meta_labeler.fit(
        X=X,
        y=y,
        primary_predictions=primary_predictions,
        regimes=regimes,
        meta_features=meta_features
    )
    
    # Define thresholds if not provided
    if thresholds is None:
        thresholds = np.linspace(0.1, 0.9, 17)  # More granular
    
    # Prepare data for meta-model predictions
    X_np = meta_labeler._to_numpy(X)
    primary_predictions_np = meta_labeler._to_numpy(primary_predictions)
    y_np = meta_labeler._to_numpy(y)
    
    if meta_features is not None:
        meta_features_np = meta_labeler._to_numpy(meta_features)
        meta_X = np.hstack((X_np, meta_features_np))
    else:
        meta_X = X_np
    
    # Get meta-model
    if 'global' in meta_labeler.meta_models:
        meta_model = meta_labeler.meta_models['global']
    else:
        # Use the first available meta-model
        meta_model = list(meta_labeler.meta_models.values())[0]
    
    # Generate meta-model probabilities
    if hasattr(meta_model, 'predict_proba'):
        meta_probabilities = meta_model.predict_proba(meta_X)[:, 1]
    else:
        meta_probabilities = meta_model.predict(meta_X).astype(float)
    
    # Evaluate each threshold
    threshold_metrics = {}
    for threshold in thresholds:
        # Filter primary predictions using meta-model with this threshold
        filtered_predictions = np.zeros_like(primary_predictions_np)
        mask = (meta_probabilities >= threshold)
        filtered_predictions[mask] = primary_predictions_np[mask]
        
        # Calculate metrics
        metrics = meta_labeler._calculate_metrics(y_np, filtered_predictions)
        threshold_metrics[threshold] = metrics
    
    # Find optimal threshold based on metric
    if metric == 'precision':
        optimal_threshold = max(threshold_metrics.items(), key=lambda x: x[1]['precision'])[0]
    elif metric == 'recall':
        optimal_threshold = max(threshold_metrics.items(), key=lambda x: x[1]['recall'])[0]
    elif metric == 'f1':
        optimal_threshold = max(threshold_metrics.items(), key=lambda x: x[1]['f1'])[0]
    elif metric == 'accuracy':
        optimal_threshold = max(threshold_metrics.items(), key=lambda x: x[1]['accuracy'])[0]
    elif metric == 'trade_reduction':
        # Find threshold that maximizes trade reduction while maintaining precision
        primary_precision = meta_labeler._calculate_metrics(y_np, primary_predictions_np)['precision']
        
        # Filter thresholds that maintain or improve precision
        valid_thresholds = {t: m for t, m in threshold_metrics.items() 
                           if m['precision'] >= primary_precision}
        
        if not valid_thresholds:
            logger.warning("No threshold maintains or improves precision, using original threshold")
            optimal_threshold = 0.5
        else:
            # Find threshold with maximum trade reduction
            optimal_threshold = min(valid_thresholds.items(), key=lambda x: x[1]['trades'])[0]
    else:
        logger.warning(f"Invalid metric: {metric}, using 'f1' instead")
        optimal_threshold = max(threshold_metrics.items(), key=lambda x: x[1]['f1'])[0]
    
    # Update meta-labeler with optimal threshold
    meta_labeler.threshold = optimal_threshold
    
    # Evaluate with optimal threshold
    filtered_predictions = np.zeros_like(primary_predictions_np)
    mask = (meta_probabilities >= optimal_threshold)
    filtered_predictions[mask] = primary_predictions_np[mask]
    
    optimal_metrics = meta_labeler._calculate_metrics(y_np, filtered_predictions)
    primary_metrics = meta_labeler._calculate_metrics(y_np, primary_predictions_np)
    
    # Calculate improvement
    improvement = {}
    for m in ['accuracy', 'precision', 'recall', 'f1']:
        improvement[m] = optimal_metrics[m] - primary_metrics[m]
    
    # Combine metrics
    metrics = {
        'primary': primary_metrics,
        'meta': optimal_metrics,
        'improvement': improvement,
        'optimal_threshold': optimal_threshold
    }
    
    # Visualize if requested
    if visualize:
        meta_labeler.visualize_threshold_impact(
            X=X,
            y=y,
            primary_predictions=primary_predictions,
            meta_features=meta_features,
            thresholds=thresholds
        )
        
        # Update meta-labeler threshold and visualize trade filtering
        meta_labeler.threshold = optimal_threshold
        meta_labeler.visualize_trade_filtering(
            X=X,
            y=y,
            primary_predictions=primary_predictions,
            meta_features=meta_features
        )
    
    return optimal_threshold, metrics 