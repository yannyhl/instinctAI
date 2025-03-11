"""
Model Evaluation Module
----------------------
Provides tools for evaluating machine learning models in financial time series prediction.
This module implements various evaluation metrics and visualization tools specifically
designed for assessing model performance in financial applications.

Key features:
1. Classification and regression metrics tailored for financial data
2. Time series specific evaluation techniques
3. Regime-aware performance assessment
4. Visualization tools for model performance analysis
5. Statistical significance testing
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    roc_auc_score, confusion_matrix, classification_report,
    mean_squared_error, mean_absolute_error, r2_score, 
    mean_absolute_percentage_error
)
from pathlib import Path
import joblib
from datetime import datetime

# Get the logger
logger = logging.getLogger(__name__)

class ModelEvaluator:
    """
    Evaluator for machine learning models in financial applications.
    
    This class provides methods for evaluating model performance using various
    metrics and visualization tools. It supports both classification and regression
    models, and can perform regime-specific evaluation.
    
    Parameters:
    -----------
    model_type : str
        Type of model ('classification' or 'regression')
    regime_aware : bool
        Whether to perform regime-specific evaluation
    custom_metrics : Optional[Dict[str, Callable]]
        Custom evaluation metrics as {name: function} pairs
    """
    
    def __init__(
        self,
        model_type: str = 'classification',
        regime_aware: bool = True,
        custom_metrics: Optional[Dict[str, Callable]] = None
    ):
        """Initialize the model evaluator."""
        self.model_type = model_type.lower()
        self.regime_aware = regime_aware
        self.custom_metrics = custom_metrics or {}
        self.evaluation_results: Dict[str, Any] = {}
        
        # Validate model type
        if self.model_type not in ['classification', 'regression']:
            raise ValueError(f"Invalid model type: {model_type}. Must be 'classification' or 'regression'.")
    
    def evaluate(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_pred: Union[pd.Series, np.ndarray],
        y_prob: Optional[Union[pd.Series, np.ndarray, pd.DataFrame]] = None,
        regimes: Optional[Union[pd.Series, np.ndarray]] = None,
        sample_weights: Optional[Union[pd.Series, np.ndarray]] = None,
        evaluation_name: str = 'default'
    ) -> Dict[str, Any]:
        """
        Evaluate model performance.
        
        Parameters:
        -----------
        y_true : Union[pd.Series, np.ndarray]
            True target values
        y_pred : Union[pd.Series, np.ndarray]
            Predicted target values
        y_prob : Optional[Union[pd.Series, np.ndarray, pd.DataFrame]]
            Predicted probabilities (for classification)
        regimes : Optional[Union[pd.Series, np.ndarray]]
            Market regime labels for regime-specific evaluation
        sample_weights : Optional[Union[pd.Series, np.ndarray]]
            Sample weights for weighted evaluation
        evaluation_name : str
            Name for this evaluation
            
        Returns:
        --------
        Dict[str, Any]
            Evaluation results
        """
        # Convert inputs to numpy arrays
        y_true = self._to_numpy(y_true)
        y_pred = self._to_numpy(y_pred)
        
        if y_prob is not None:
            y_prob = self._to_numpy(y_prob)
        
        if regimes is not None:
            regimes = self._to_numpy(regimes)
        
        if sample_weights is not None:
            sample_weights = self._to_numpy(sample_weights)
        
        # Initialize results dictionary
        results = {
            'model_type': self.model_type,
            'evaluation_time': datetime.now(),
            'sample_count': len(y_true),
            'metrics': {}
        }
        
        # Perform global evaluation
        if self.model_type == 'classification':
            results['metrics']['global'] = self._evaluate_classification(
                y_true, y_pred, y_prob, sample_weights
            )
        else:
            results['metrics']['global'] = self._evaluate_regression(
                y_true, y_pred, sample_weights
            )
        
        # Perform regime-specific evaluation if requested
        if self.regime_aware and regimes is not None:
            results['metrics']['regimes'] = {}
            
            # Get unique regimes
            unique_regimes = np.unique(regimes)
            
            for regime in unique_regimes:
                # Get data for this regime
                regime_mask = (regimes == regime)
                
                if np.sum(regime_mask) < 10:  # Skip regimes with too few samples
                    logger.warning(f"Regime {regime} has too few samples for evaluation")
                    continue
                
                y_true_regime = y_true[regime_mask]
                y_pred_regime = y_pred[regime_mask]
                
                y_prob_regime = None
                if y_prob is not None:
                    if y_prob.ndim == 1:
                        y_prob_regime = y_prob[regime_mask]
                    else:
                        y_prob_regime = y_prob[regime_mask, :]
                
                sample_weights_regime = None
                if sample_weights is not None:
                    sample_weights_regime = sample_weights[regime_mask]
                
                # Evaluate for this regime
                if self.model_type == 'classification':
                    results['metrics']['regimes'][str(regime)] = self._evaluate_classification(
                        y_true_regime, y_pred_regime, y_prob_regime, sample_weights_regime
                    )
                else:
                    results['metrics']['regimes'][str(regime)] = self._evaluate_regression(
                        y_true_regime, y_pred_regime, sample_weights_regime
                    )
        
        # Apply custom metrics
        if self.custom_metrics:
            custom_results = {}
            
            for metric_name, metric_func in self.custom_metrics.items():
                try:
                    if y_prob is not None:
                        custom_results[metric_name] = metric_func(y_true, y_pred, y_prob)
                    else:
                        custom_results[metric_name] = metric_func(y_true, y_pred)
                except Exception as e:
                    logger.error(f"Error calculating custom metric '{metric_name}': {str(e)}")
            
            results['metrics']['custom'] = custom_results
        
        # Store results
        self.evaluation_results[evaluation_name] = results
        
        return results
    
    def _evaluate_classification(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: Optional[np.ndarray] = None,
        sample_weights: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """
        Evaluate classification model performance.
        
        Parameters:
        -----------
        y_true : np.ndarray
            True target values
        y_pred : np.ndarray
            Predicted target values
        y_prob : Optional[np.ndarray]
            Predicted probabilities
        sample_weights : Optional[np.ndarray]
            Sample weights for weighted evaluation
            
        Returns:
        --------
        Dict[str, float]
            Classification metrics
        """
        metrics = {}
        
        # Basic metrics
        metrics['accuracy'] = accuracy_score(y_true, y_pred, sample_weight=sample_weights)
        
        # Handle binary and multiclass cases
        unique_classes = np.unique(np.concatenate([y_true, y_pred]))
        is_binary = len(unique_classes) <= 2
        
        if is_binary:
            # Binary classification metrics
            metrics['precision'] = precision_score(y_true, y_pred, sample_weight=sample_weights, zero_division=0)
            metrics['recall'] = recall_score(y_true, y_pred, sample_weight=sample_weights, zero_division=0)
            metrics['f1'] = f1_score(y_true, y_pred, sample_weight=sample_weights, zero_division=0)
            
            # ROC AUC if probabilities are provided
            if y_prob is not None:
                if y_prob.ndim > 1 and y_prob.shape[1] >= 2:
                    # Use second column for positive class probability
                    metrics['roc_auc'] = roc_auc_score(y_true, y_prob[:, 1], sample_weight=sample_weights)
                else:
                    metrics['roc_auc'] = roc_auc_score(y_true, y_prob, sample_weight=sample_weights)
        else:
            # Multiclass classification metrics
            metrics['precision_macro'] = precision_score(y_true, y_pred, average='macro', sample_weight=sample_weights, zero_division=0)
            metrics['recall_macro'] = recall_score(y_true, y_pred, average='macro', sample_weight=sample_weights, zero_division=0)
            metrics['f1_macro'] = f1_score(y_true, y_pred, average='macro', sample_weight=sample_weights, zero_division=0)
            
            metrics['precision_weighted'] = precision_score(y_true, y_pred, average='weighted', sample_weight=sample_weights, zero_division=0)
            metrics['recall_weighted'] = recall_score(y_true, y_pred, average='weighted', sample_weight=sample_weights, zero_division=0)
            metrics['f1_weighted'] = f1_score(y_true, y_pred, average='weighted', sample_weight=sample_weights, zero_division=0)
            
            # ROC AUC if probabilities are provided
            if y_prob is not None and y_prob.ndim > 1:
                try:
                    metrics['roc_auc_ovr'] = roc_auc_score(y_true, y_prob, multi_class='ovr', sample_weight=sample_weights)
                except Exception as e:
                    logger.warning(f"Could not calculate ROC AUC: {str(e)}")
        
        # Confusion matrix
        metrics['confusion_matrix'] = confusion_matrix(y_true, y_pred, sample_weight=sample_weights).tolist()
        
        # Classification report
        report = classification_report(y_true, y_pred, output_dict=True, sample_weight=sample_weights, zero_division=0)
        metrics['classification_report'] = report
        
        return metrics
    
    def _evaluate_regression(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        sample_weights: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """
        Evaluate regression model performance.
        
        Parameters:
        -----------
        y_true : np.ndarray
            True target values
        y_pred : np.ndarray
            Predicted target values
        sample_weights : Optional[np.ndarray]
            Sample weights for weighted evaluation
            
        Returns:
        --------
        Dict[str, float]
            Regression metrics
        """
        metrics = {}
        
        # Basic metrics
        metrics['mse'] = mean_squared_error(y_true, y_pred, sample_weight=sample_weights)
        metrics['rmse'] = np.sqrt(metrics['mse'])
        metrics['mae'] = mean_absolute_error(y_true, y_pred, sample_weight=sample_weights)
        metrics['r2'] = r2_score(y_true, y_pred, sample_weight=sample_weights)
        
        # Mean absolute percentage error (handle zero values)
        with np.errstate(divide='ignore', invalid='ignore'):
            if np.any(y_true == 0):
                # Avoid division by zero
                non_zero_mask = y_true != 0
                if np.sum(non_zero_mask) > 0:
                    mape = np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])
                    metrics['mape'] = np.mean(mape) * 100
                else:
                    metrics['mape'] = np.nan
            else:
                metrics['mape'] = mean_absolute_percentage_error(y_true, y_pred) * 100
        
        # Direction accuracy (for financial time series)
        if len(y_true) > 1:
            true_direction = np.sign(np.diff(y_true))
            pred_direction = np.sign(np.diff(y_pred))
            metrics['direction_accuracy'] = np.mean(true_direction == pred_direction)
        else:
            metrics['direction_accuracy'] = np.nan
        
        return metrics
    
    def get_results(
        self,
        evaluation_name: str = 'default',
        regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get evaluation results.
        
        Parameters:
        -----------
        evaluation_name : str
            Name of the evaluation to retrieve
        regime : Optional[str]
            Regime to get results for (if regime-specific evaluation was performed)
            
        Returns:
        --------
        Dict[str, Any]
            Evaluation results
        """
        if evaluation_name not in self.evaluation_results:
            raise ValueError(f"No evaluation results found for '{evaluation_name}'")
        
        results = self.evaluation_results[evaluation_name]
        
        if regime is not None:
            if 'regimes' not in results['metrics'] or regime not in results['metrics']['regimes']:
                raise ValueError(f"No results found for regime '{regime}'")
            
            return results['metrics']['regimes'][regime]
        
        return results['metrics']['global']
    
    def compare_models(
        self,
        model_names: List[str],
        metric_name: str = 'accuracy',
        regime: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Compare multiple models based on a specific metric.
        
        Parameters:
        -----------
        model_names : List[str]
            Names of the evaluations to compare
        metric_name : str
            Name of the metric to compare
        regime : Optional[str]
            Regime to compare models for
            
        Returns:
        --------
        pd.DataFrame
            Comparison of models
        """
        comparison = {}
        
        for model_name in model_names:
            try:
                results = self.get_results(model_name, regime)
                
                # Handle nested metrics in classification report
                if '.' in metric_name:
                    parts = metric_name.split('.')
                    value = results
                    for part in parts:
                        value = value[part]
                    comparison[model_name] = value
                else:
                    comparison[model_name] = results[metric_name]
            except (KeyError, ValueError) as e:
                logger.warning(f"Could not get metric '{metric_name}' for model '{model_name}': {str(e)}")
                comparison[model_name] = np.nan
        
        return pd.DataFrame(comparison, index=[metric_name]).T
    
    def _to_numpy(self, data: Union[pd.Series, pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Convert data to numpy array."""
        if isinstance(data, (pd.Series, pd.DataFrame)):
            return data.values
        return np.asarray(data)
    
    def visualize_confusion_matrix(
        self,
        evaluation_name: str = 'default',
        regime: Optional[str] = None,
        figsize: Tuple[int, int] = (8, 6),
        cmap: str = 'Blues',
        normalize: bool = False
    ) -> None:
        """
        Visualize confusion matrix.
        
        Parameters:
        -----------
        evaluation_name : str
            Name of the evaluation to visualize
        regime : Optional[str]
            Regime to visualize (if regime-specific evaluation was performed)
        figsize : Tuple[int, int]
            Figure size
        cmap : str
            Colormap for the confusion matrix
        normalize : bool
            Whether to normalize the confusion matrix
        """
        if self.model_type != 'classification':
            logger.warning("Confusion matrix is only available for classification models")
            return
        
        try:
            results = self.get_results(evaluation_name, regime)
            cm = np.array(results['confusion_matrix'])
            
            # Get class labels from classification report
            class_labels = list(results['classification_report'].keys())
            class_labels = [label for label in class_labels if label not in ['accuracy', 'macro avg', 'weighted avg']]
            
            # Normalize if requested
            if normalize:
                cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
                title = 'Normalized Confusion Matrix'
                fmt = '.2f'
            else:
                title = 'Confusion Matrix'
                fmt = 'd'
            
            # Create plot
            plt.figure(figsize=figsize)
            sns.heatmap(cm, annot=True, fmt=fmt, cmap=cmap, 
                        xticklabels=class_labels, yticklabels=class_labels)
            plt.ylabel('True Label')
            plt.xlabel('Predicted Label')
            
            # Add regime to title if specified
            if regime is not None:
                title += f" (Regime: {regime})"
            
            plt.title(title)
            plt.tight_layout()
            plt.show()
        except Exception as e:
            logger.error(f"Error visualizing confusion matrix: {str(e)}")
    
    def visualize_roc_curve(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray, pd.DataFrame],
        figsize: Tuple[int, int] = (8, 6)
    ) -> None:
        """
        Visualize ROC curve.
        
        Parameters:
        -----------
        y_true : Union[pd.Series, np.ndarray]
            True target values
        y_prob : Union[pd.Series, np.ndarray, pd.DataFrame]
            Predicted probabilities
        figsize : Tuple[int, int]
            Figure size
        """
        if self.model_type != 'classification':
            logger.warning("ROC curve is only available for classification models")
            return
        
        try:
            from sklearn.metrics import roc_curve, auc
            
            # Convert inputs to numpy arrays
            y_true = self._to_numpy(y_true)
            y_prob = self._to_numpy(y_prob)
            
            # Handle binary and multiclass cases
            unique_classes = np.unique(y_true)
            is_binary = len(unique_classes) <= 2
            
            plt.figure(figsize=figsize)
            
            if is_binary:
                # Binary classification
                if y_prob.ndim > 1 and y_prob.shape[1] >= 2:
                    # Use second column for positive class probability
                    y_prob_binary = y_prob[:, 1]
                else:
                    y_prob_binary = y_prob
                
                fpr, tpr, _ = roc_curve(y_true, y_prob_binary)
                roc_auc = auc(fpr, tpr)
                
                plt.plot(fpr, tpr, lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
                plt.plot([0, 1], [0, 1], 'k--', lw=2)
                plt.xlim([0.0, 1.0])
                plt.ylim([0.0, 1.05])
                plt.xlabel('False Positive Rate')
                plt.ylabel('True Positive Rate')
                plt.title('Receiver Operating Characteristic')
                plt.legend(loc="lower right")
            else:
                # Multiclass classification
                from sklearn.preprocessing import label_binarize
                
                # Binarize the output
                y_true_bin = label_binarize(y_true, classes=unique_classes)
                n_classes = y_true_bin.shape[1]
                
                # Compute ROC curve and ROC area for each class
                fpr = {}
                tpr = {}
                roc_auc = {}
                
                for i, class_label in enumerate(unique_classes):
                    fpr[i], tpr[i], _ = roc_curve(y_true_bin[:, i], y_prob[:, i])
                    roc_auc[i] = auc(fpr[i], tpr[i])
                    
                    plt.plot(fpr[i], tpr[i], lw=2,
                             label=f'ROC curve of class {class_label} (AUC = {roc_auc[i]:.2f})')
                
                plt.plot([0, 1], [0, 1], 'k--', lw=2)
                plt.xlim([0.0, 1.0])
                plt.ylim([0.0, 1.05])
                plt.xlabel('False Positive Rate')
                plt.ylabel('True Positive Rate')
                plt.title('Receiver Operating Characteristic for Multi-class')
                plt.legend(loc="lower right")
            
            plt.tight_layout()
            plt.show()
        except Exception as e:
            logger.error(f"Error visualizing ROC curve: {str(e)}")
    
    def visualize_precision_recall_curve(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray, pd.DataFrame],
        figsize: Tuple[int, int] = (8, 6)
    ) -> None:
        """
        Visualize precision-recall curve.
        
        Parameters:
        -----------
        y_true : Union[pd.Series, np.ndarray]
            True target values
        y_prob : Union[pd.Series, np.ndarray, pd.DataFrame]
            Predicted probabilities
        figsize : Tuple[int, int]
            Figure size
        """
        if self.model_type != 'classification':
            logger.warning("Precision-recall curve is only available for classification models")
            return
        
        try:
            from sklearn.metrics import precision_recall_curve, average_precision_score
            
            # Convert inputs to numpy arrays
            y_true = self._to_numpy(y_true)
            y_prob = self._to_numpy(y_prob)
            
            # Handle binary and multiclass cases
            unique_classes = np.unique(y_true)
            is_binary = len(unique_classes) <= 2
            
            plt.figure(figsize=figsize)
            
            if is_binary:
                # Binary classification
                if y_prob.ndim > 1 and y_prob.shape[1] >= 2:
                    # Use second column for positive class probability
                    y_prob_binary = y_prob[:, 1]
                else:
                    y_prob_binary = y_prob
                
                precision, recall, _ = precision_recall_curve(y_true, y_prob_binary)
                ap = average_precision_score(y_true, y_prob_binary)
                
                plt.plot(recall, precision, lw=2, label=f'Precision-Recall curve (AP = {ap:.2f})')
                plt.xlabel('Recall')
                plt.ylabel('Precision')
                plt.title('Precision-Recall Curve')
                plt.legend(loc="lower left")
            else:
                # Multiclass classification
                from sklearn.preprocessing import label_binarize
                
                # Binarize the output
                y_true_bin = label_binarize(y_true, classes=unique_classes)
                n_classes = y_true_bin.shape[1]
                
                # Compute precision-recall curve and average precision for each class
                precision = {}
                recall = {}
                ap = {}
                
                for i, class_label in enumerate(unique_classes):
                    precision[i], recall[i], _ = precision_recall_curve(y_true_bin[:, i], y_prob[:, i])
                    ap[i] = average_precision_score(y_true_bin[:, i], y_prob[:, i])
                    
                    plt.plot(recall[i], precision[i], lw=2,
                             label=f'PR curve of class {class_label} (AP = {ap[i]:.2f})')
                
                plt.xlabel('Recall')
                plt.ylabel('Precision')
                plt.title('Precision-Recall Curve for Multi-class')
                plt.legend(loc="lower left")
            
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.tight_layout()
            plt.show()
        except Exception as e:
            logger.error(f"Error visualizing precision-recall curve: {str(e)}")
    
    def visualize_regression_performance(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_pred: Union[pd.Series, np.ndarray],
        figsize: Tuple[int, int] = (12, 10)
    ) -> None:
        """
        Visualize regression model performance.
        
        Parameters:
        -----------
        y_true : Union[pd.Series, np.ndarray]
            True target values
        y_pred : Union[pd.Series, np.ndarray]
            Predicted target values
        figsize : Tuple[int, int]
            Figure size
        """
        if self.model_type != 'regression':
            logger.warning("Regression performance visualization is only available for regression models")
            return
        
        try:
            # Convert inputs to numpy arrays
            y_true = self._to_numpy(y_true)
            y_pred = self._to_numpy(y_pred)
            
            # Calculate metrics
            mse = mean_squared_error(y_true, y_pred)
            rmse = np.sqrt(mse)
            mae = mean_absolute_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred)
            
            # Calculate residuals
            residuals = y_true - y_pred
            
            # Create figure with subplots
            fig, axes = plt.subplots(2, 2, figsize=figsize)
            
            # Scatter plot of true vs predicted values
            axes[0, 0].scatter(y_true, y_pred, alpha=0.5)
            axes[0, 0].plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'k--', lw=2)
            axes[0, 0].set_xlabel('True Values')
            axes[0, 0].set_ylabel('Predicted Values')
            axes[0, 0].set_title(f'True vs Predicted Values (R² = {r2:.2f})')
            
            # Histogram of residuals
            axes[0, 1].hist(residuals, bins=30, alpha=0.7)
            axes[0, 1].axvline(x=0, color='k', linestyle='--', lw=2)
            axes[0, 1].set_xlabel('Residuals')
            axes[0, 1].set_ylabel('Frequency')
            axes[0, 1].set_title(f'Residuals (RMSE = {rmse:.2f}, MAE = {mae:.2f})')
            
            # Residuals vs predicted values
            axes[1, 0].scatter(y_pred, residuals, alpha=0.5)
            axes[1, 0].axhline(y=0, color='k', linestyle='--', lw=2)
            axes[1, 0].set_xlabel('Predicted Values')
            axes[1, 0].set_ylabel('Residuals')
            axes[1, 0].set_title('Residuals vs Predicted Values')
            
            # Q-Q plot of residuals
            from scipy import stats
            
            # Calculate quantiles
            sorted_residuals = np.sort(residuals)
            n = len(sorted_residuals)
            quantiles = np.arange(1, n + 1) / (n + 1)
            theoretical_quantiles = stats.norm.ppf(quantiles, loc=np.mean(residuals), scale=np.std(residuals))
            
            axes[1, 1].scatter(theoretical_quantiles, sorted_residuals, alpha=0.5)
            axes[1, 1].plot([theoretical_quantiles.min(), theoretical_quantiles.max()],
                           [sorted_residuals.min(), sorted_residuals.max()], 'k--', lw=2)
            axes[1, 1].set_xlabel('Theoretical Quantiles')
            axes[1, 1].set_ylabel('Sample Quantiles')
            axes[1, 1].set_title('Q-Q Plot of Residuals')
            
            plt.tight_layout()
            plt.show()
        except Exception as e:
            logger.error(f"Error visualizing regression performance: {str(e)}")
    
    def visualize_feature_importance(
        self,
        feature_importance: Dict[str, float],
        figsize: Tuple[int, int] = (10, 8),
        top_n: int = 20
    ) -> None:
        """
        Visualize feature importance.
        
        Parameters:
        -----------
        feature_importance : Dict[str, float]
            Dictionary mapping feature names to importance scores
        figsize : Tuple[int, int]
            Figure size
        top_n : int
            Number of top features to display
        """
        try:
            # Convert to DataFrame and sort
            importance_df = pd.DataFrame({
                'feature': list(feature_importance.keys()),
                'importance': list(feature_importance.values())
            })
            importance_df = importance_df.sort_values('importance', ascending=False).head(top_n)
            
            # Create plot
            plt.figure(figsize=figsize)
            sns.barplot(x='importance', y='feature', data=importance_df)
            plt.title(f'Top {top_n} Feature Importance')
            plt.tight_layout()
            plt.show()
        except Exception as e:
            logger.error(f"Error visualizing feature importance: {str(e)}")
    
    def visualize_metric_by_regime(
        self,
        evaluation_name: str = 'default',
        metric_name: str = 'accuracy',
        figsize: Tuple[int, int] = (10, 6)
    ) -> None:
        """
        Visualize a metric across different regimes.
        
        Parameters:
        -----------
        evaluation_name : str
            Name of the evaluation to visualize
        metric_name : str
            Name of the metric to visualize
        figsize : Tuple[int, int]
            Figure size
        """
        if evaluation_name not in self.evaluation_results:
            raise ValueError(f"No evaluation results found for '{evaluation_name}'")
        
        results = self.evaluation_results[evaluation_name]
        
        if 'regimes' not in results['metrics']:
            logger.warning("No regime-specific results found")
            return
        
        try:
            # Extract metric values for each regime
            regimes = []
            metric_values = []
            
            for regime, regime_results in results['metrics']['regimes'].items():
                # Handle nested metrics in classification report
                if '.' in metric_name:
                    parts = metric_name.split('.')
                    value = regime_results
                    for part in parts:
                        value = value[part]
                    metric_values.append(value)
                else:
                    metric_values.append(regime_results[metric_name])
                
                regimes.append(regime)
            
            # Create DataFrame
            data = pd.DataFrame({
                'regime': regimes,
                metric_name: metric_values
            })
            
            # Create plot
            plt.figure(figsize=figsize)
            sns.barplot(x='regime', y=metric_name, data=data)
            plt.title(f'{metric_name.capitalize()} by Regime')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.show()
        except Exception as e:
            logger.error(f"Error visualizing metric by regime: {str(e)}")
    
    def visualize_model_comparison(
        self,
        model_names: List[str],
        metric_names: List[str],
        regime: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> None:
        """
        Visualize comparison of multiple models across multiple metrics.
        
        Parameters:
        -----------
        model_names : List[str]
            Names of the evaluations to compare
        metric_names : List[str]
            Names of the metrics to compare
        regime : Optional[str]
            Regime to compare models for
        figsize : Tuple[int, int]
            Figure size
        """
        try:
            # Create DataFrame for comparison
            comparison_data = []
            
            for model_name in model_names:
                try:
                    results = self.get_results(model_name, regime)
                    
                    for metric_name in metric_names:
                        # Handle nested metrics in classification report
                        if '.' in metric_name:
                            parts = metric_name.split('.')
                            value = results
                            for part in parts:
                                value = value[part]
                        else:
                            value = results[metric_name]
                        
                        comparison_data.append({
                            'model': model_name,
                            'metric': metric_name,
                            'value': value
                        })
                except (KeyError, ValueError) as e:
                    logger.warning(f"Could not get metrics for model '{model_name}': {str(e)}")
            
            # Convert to DataFrame
            comparison_df = pd.DataFrame(comparison_data)
            
            # Create plot
            plt.figure(figsize=figsize)
            sns.barplot(x='model', y='value', hue='metric', data=comparison_df)
            plt.title('Model Comparison' + (f' (Regime: {regime})' if regime else ''))
            plt.xticks(rotation=45)
            plt.legend(title='Metric')
            plt.tight_layout()
            plt.show()
        except Exception as e:
            logger.error(f"Error visualizing model comparison: {str(e)}")
    
    def save(self, filepath: str) -> None:
        """
        Save the model evaluator to a file.
        
        Parameters:
        -----------
        filepath : str
            Path to save the model evaluator
        """
        # Create directory if it doesn't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Save the model evaluator
        joblib.dump(self, filepath)
        logger.info(f"Model evaluator saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'ModelEvaluator':
        """
        Load a model evaluator from a file.
        
        Parameters:
        -----------
        filepath : str
            Path to load the model evaluator from
            
        Returns:
        --------
        ModelEvaluator
            The loaded model evaluator
        """
        # Load the model evaluator
        evaluator = joblib.load(filepath)
        logger.info(f"Model evaluator loaded from {filepath}")
        return evaluator


# Convenience functions

def evaluate_classification_model(
    y_true: Union[pd.Series, np.ndarray],
    y_pred: Union[pd.Series, np.ndarray],
    y_prob: Optional[Union[pd.Series, np.ndarray, pd.DataFrame]] = None,
    regimes: Optional[Union[pd.Series, np.ndarray]] = None
) -> Dict[str, Any]:
    """
    Evaluate a classification model.
    
    Parameters:
    -----------
    y_true : Union[pd.Series, np.ndarray]
        True target values
    y_pred : Union[pd.Series, np.ndarray]
        Predicted target values
    y_prob : Optional[Union[pd.Series, np.ndarray, pd.DataFrame]]
        Predicted probabilities
    regimes : Optional[Union[pd.Series, np.ndarray]]
        Market regime labels for regime-specific evaluation
        
    Returns:
    --------
    Dict[str, Any]
        Evaluation results
    """
    evaluator = ModelEvaluator(model_type='classification', regime_aware=(regimes is not None))
    return evaluator.evaluate(y_true, y_pred, y_prob, regimes)

def evaluate_regression_model(
    y_true: Union[pd.Series, np.ndarray],
    y_pred: Union[pd.Series, np.ndarray],
    regimes: Optional[Union[pd.Series, np.ndarray]] = None
) -> Dict[str, Any]:
    """
    Evaluate a regression model.
    
    Parameters:
    -----------
    y_true : Union[pd.Series, np.ndarray]
        True target values
    y_pred : Union[pd.Series, np.ndarray]
        Predicted target values
    regimes : Optional[Union[pd.Series, np.ndarray]]
        Market regime labels for regime-specific evaluation
        
    Returns:
    --------
    Dict[str, Any]
        Evaluation results
    """
    evaluator = ModelEvaluator(model_type='regression', regime_aware=(regimes is not None))
    return evaluator.evaluate(y_true, y_pred, regimes=regimes) 