"""
Model Calibration Module
------------------------
This module provides tools for calibrating machine learning models to ensure
their probability estimates are well-calibrated. Calibration is particularly
important in financial applications where decision-making relies on accurate
probability estimates.

The module includes:
1. Various calibration methods (Platt scaling, isotonic regression, etc.)
2. Calibration visualization tools
3. Regime-specific calibration
4. Evaluation metrics for calibration quality
5. Convenience functions for quick calibration

Key classes:
- ModelCalibrator: Main class for calibrating models
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Union, Optional, Tuple, Callable, Any
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.base import BaseEstimator, ClassifierMixin
import logging
from scipy import stats

# Configure logging
logger = logging.getLogger(__name__)

class ModelCalibrator:
    """
    A class for calibrating machine learning models to ensure their probability
    estimates are well-calibrated.
    
    Calibration is the process of adjusting probability estimates to match
    observed frequencies. This is particularly important in financial applications
    where decision-making relies on accurate probability estimates.
    
    The class supports multiple calibration methods and regime-specific calibration.
    
    Parameters
    ----------
    method : str, default='platt'
        The calibration method to use. Options include:
        - 'platt': Platt scaling (logistic regression)
        - 'isotonic': Isotonic regression
        - 'beta': Beta calibration
        - 'ensemble': Ensemble of calibration methods
    
    regime_aware : bool, default=True
        Whether to perform regime-specific calibration.
    
    cv : int, default=5
        Number of cross-validation folds for calibration.
    
    Attributes
    ----------
    calibrators : dict
        Dictionary of calibration models for each regime.
    
    calibration_scores : dict
        Dictionary of calibration quality metrics.
    """
    
    def __init__(
        self,
        method: str = 'platt',
        regime_aware: bool = True,
        cv: int = 5
    ):
        """
        Initialize the ModelCalibrator.
        
        Parameters
        ----------
        method : str, default='platt'
            The calibration method to use.
        
        regime_aware : bool, default=True
            Whether to perform regime-specific calibration.
        
        cv : int, default=5
            Number of cross-validation folds for calibration.
        """
        self.method = method
        self.regime_aware = regime_aware
        self.cv = cv
        self.calibrators = {}
        self.calibration_scores = {}
        
        # Validate method
        valid_methods = ['platt', 'isotonic', 'beta', 'ensemble']
        if method not in valid_methods:
            raise ValueError(f"Method must be one of {valid_methods}, got {method}")
        
        logger.info(f"Initialized ModelCalibrator with method={method}, regime_aware={regime_aware}")
    
    def fit(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray, pd.DataFrame],
        regimes: Optional[Union[pd.Series, np.ndarray]] = None,
        sample_weights: Optional[Union[pd.Series, np.ndarray]] = None
    ) -> 'ModelCalibrator':
        """
        Fit calibration models to the data.
        
        Parameters
        ----------
        y_true : array-like
            True binary labels.
        
        y_prob : array-like
            Probability estimates from the uncalibrated model.
            For binary classification, this should be a 1D array of probabilities.
            For multiclass, this should be a 2D array with shape (n_samples, n_classes).
        
        regimes : array-like, optional
            Regime labels for each sample. If provided and regime_aware=True,
            separate calibration models will be fit for each regime.
        
        sample_weights : array-like, optional
            Sample weights for fitting the calibration models.
        
        Returns
        -------
        self : ModelCalibrator
            The fitted calibrator.
        """
        # Convert inputs to numpy arrays
        y_true = self._to_numpy(y_true)
        y_prob = self._to_numpy(y_prob)
        
        # Handle multiclass case
        if len(y_prob.shape) > 1 and y_prob.shape[1] > 1:
            # For multiclass, we need to calibrate each class separately
            # This is a simplification - more sophisticated approaches exist
            logger.info("Multiclass calibration detected, calibrating each class separately")
            self.is_multiclass = True
            self.n_classes = y_prob.shape[1]
        else:
            # For binary classification, ensure y_prob is 1D
            if len(y_prob.shape) > 1:
                y_prob = y_prob[:, 1]  # Take the probability of the positive class
            self.is_multiclass = False
            self.n_classes = 2
        
        # Regime-specific calibration
        if self.regime_aware and regimes is not None:
            regimes = self._to_numpy(regimes)
            unique_regimes = np.unique(regimes)
            
            for regime in unique_regimes:
                regime_mask = (regimes == regime)
                regime_y_true = y_true[regime_mask]
                regime_y_prob = y_prob[regime_mask] if not self.is_multiclass else y_prob[regime_mask, :]
                
                if sample_weights is not None:
                    regime_weights = sample_weights[regime_mask]
                else:
                    regime_weights = None
                
                # Fit calibration model for this regime
                self._fit_calibrator(regime_y_true, regime_y_prob, regime_weights, regime=regime)
                
                # Evaluate calibration quality
                self._evaluate_calibration(regime_y_true, regime_y_prob, regime=regime)
                
            logger.info(f"Fitted regime-specific calibration models for {len(unique_regimes)} regimes")
        else:
            # Global calibration
            self._fit_calibrator(y_true, y_prob, sample_weights, regime='global')
            self._evaluate_calibration(y_true, y_prob, regime='global')
            
            logger.info("Fitted global calibration model")
        
        return self
    
    def calibrate(
        self,
        y_prob: Union[pd.Series, np.ndarray, pd.DataFrame],
        regime: Optional[str] = None
    ) -> np.ndarray:
        """
        Calibrate probability estimates using the fitted calibration models.
        
        Parameters
        ----------
        y_prob : array-like
            Probability estimates from the uncalibrated model.
        
        regime : str, optional
            The regime to use for calibration. If None and regime_aware=True,
            the global calibration model will be used.
        
        Returns
        -------
        calibrated_probs : ndarray
            Calibrated probability estimates.
        """
        y_prob = self._to_numpy(y_prob)
        
        # Determine which calibrator to use
        if regime is not None and regime in self.calibrators:
            calibrator = self.calibrators[regime]
            logger.debug(f"Using regime-specific calibrator for regime '{regime}'")
        elif 'global' in self.calibrators:
            calibrator = self.calibrators['global']
            logger.debug("Using global calibrator")
        else:
            logger.warning("No calibrator found, returning uncalibrated probabilities")
            return y_prob
        
        # Apply calibration
        if self.is_multiclass:
            # For multiclass, calibrate each class separately
            calibrated_probs = np.zeros_like(y_prob)
            for i in range(self.n_classes):
                if isinstance(calibrator, dict) and i in calibrator:
                    calibrated_probs[:, i] = self._apply_calibrator(y_prob[:, i], calibrator[i])
                else:
                    calibrated_probs[:, i] = y_prob[:, i]
            
            # Normalize to ensure probabilities sum to 1
            row_sums = calibrated_probs.sum(axis=1)
            calibrated_probs = calibrated_probs / row_sums[:, np.newaxis]
        else:
            # For binary classification
            calibrated_probs = self._apply_calibrator(y_prob, calibrator)
        
        return calibrated_probs
    
    def _fit_calibrator(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        regime: str = 'global'
    ) -> None:
        """
        Fit a calibration model for a specific regime.
        
        Parameters
        ----------
        y_true : ndarray
            True binary labels.
        
        y_prob : ndarray
            Probability estimates from the uncalibrated model.
        
        sample_weights : ndarray, optional
            Sample weights for fitting the calibration model.
        
        regime : str, default='global'
            The regime for which to fit the calibration model.
        """
        if self.is_multiclass:
            # For multiclass, fit a calibrator for each class
            calibrators = {}
            for i in range(self.n_classes):
                # Convert to binary problem (one-vs-rest)
                binary_y_true = (y_true == i).astype(int)
                binary_y_prob = y_prob[:, i]
                
                calibrators[i] = self._fit_binary_calibrator(
                    binary_y_true, binary_y_prob, sample_weights
                )
            
            self.calibrators[regime] = calibrators
        else:
            # For binary classification
            self.calibrators[regime] = self._fit_binary_calibrator(
                y_true, y_prob, sample_weights
            )
    
    def _fit_binary_calibrator(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        sample_weights: Optional[np.ndarray] = None
    ) -> BaseEstimator:
        """
        Fit a calibration model for binary classification.
        
        Parameters
        ----------
        y_true : ndarray
            True binary labels.
        
        y_prob : ndarray
            Probability estimates from the uncalibrated model.
        
        sample_weights : ndarray, optional
            Sample weights for fitting the calibration model.
        
        Returns
        -------
        calibrator : BaseEstimator
            The fitted calibration model.
        """
        # Reshape y_prob for sklearn
        y_prob_reshaped = y_prob.reshape(-1, 1)
        
        if self.method == 'platt':
            # Platt scaling (logistic regression)
            calibrator = LogisticRegression(C=1.0, solver='lbfgs')
            calibrator.fit(y_prob_reshaped, y_true, sample_weight=sample_weights)
            
        elif self.method == 'isotonic':
            # Isotonic regression
            calibrator = IsotonicRegression(out_of_bounds='clip')
            calibrator.fit(y_prob, y_true, sample_weight=sample_weights)
            
        elif self.method == 'beta':
            # Beta calibration
            # This is a simplified implementation
            # For a more robust implementation, consider using betacal package
            calibrator = self._fit_beta_calibration(y_prob, y_true, sample_weights)
            
        elif self.method == 'ensemble':
            # Ensemble of calibration methods
            calibrators = {
                'platt': LogisticRegression(C=1.0, solver='lbfgs'),
                'isotonic': IsotonicRegression(out_of_bounds='clip')
            }
            
            # Fit each calibrator
            for name, cal in calibrators.items():
                if name == 'isotonic':
                    cal.fit(y_prob, y_true, sample_weight=sample_weights)
                else:
                    cal.fit(y_prob_reshaped, y_true, sample_weight=sample_weights)
            
            calibrator = calibrators
        
        return calibrator
    
    def _apply_calibrator(
        self,
        y_prob: np.ndarray,
        calibrator: Union[BaseEstimator, Dict[str, BaseEstimator]]
    ) -> np.ndarray:
        """
        Apply a calibration model to probability estimates.
        
        Parameters
        ----------
        y_prob : ndarray
            Probability estimates from the uncalibrated model.
        
        calibrator : BaseEstimator or dict
            The calibration model to apply.
        
        Returns
        -------
        calibrated_probs : ndarray
            Calibrated probability estimates.
        """
        # Reshape y_prob for sklearn
        y_prob_reshaped = y_prob.reshape(-1, 1)
        
        if isinstance(calibrator, dict):
            # Ensemble of calibrators
            calibrated_probs = np.zeros_like(y_prob)
            weights = {'platt': 0.5, 'isotonic': 0.5}  # Equal weights by default
            
            for name, cal in calibrator.items():
                if name == 'isotonic':
                    cal_prob = cal.predict(y_prob)
                else:
                    cal_prob = cal.predict_proba(y_prob_reshaped)[:, 1]
                
                calibrated_probs += weights[name] * cal_prob
            
            return calibrated_probs
        
        elif self.method == 'platt':
            # Platt scaling
            return calibrator.predict_proba(y_prob_reshaped)[:, 1]
        
        elif self.method == 'isotonic':
            # Isotonic regression
            return calibrator.predict(y_prob)
        
        elif self.method == 'beta':
            # Beta calibration
            return self._apply_beta_calibration(y_prob, calibrator)
        
        else:
            # Fallback
            logger.warning(f"Unknown calibration method: {self.method}, returning uncalibrated probabilities")
            return y_prob
    
    def _evaluate_calibration(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        regime: str = 'global'
    ) -> Dict[str, float]:
        """
        Evaluate the calibration quality.
        
        Parameters
        ----------
        y_true : ndarray
            True binary labels.
        
        y_prob : ndarray
            Probability estimates from the uncalibrated model.
        
        regime : str, default='global'
            The regime for which to evaluate calibration.
        
        Returns
        -------
        metrics : dict
            Dictionary of calibration quality metrics.
        """
        if self.is_multiclass:
            # For multiclass, evaluate calibration for each class
            metrics = {}
            for i in range(self.n_classes):
                # Convert to binary problem (one-vs-rest)
                binary_y_true = (y_true == i).astype(int)
                binary_y_prob = y_prob[:, i]
                
                class_metrics = self._evaluate_binary_calibration(binary_y_true, binary_y_prob)
                metrics[f'class_{i}'] = class_metrics
            
            # Average metrics across classes
            avg_metrics = {}
            for metric in class_metrics.keys():
                avg_metrics[metric] = np.mean([metrics[f'class_{i}'][metric] for i in range(self.n_classes)])
            
            metrics['average'] = avg_metrics
        else:
            # For binary classification
            metrics = self._evaluate_binary_calibration(y_true, y_prob)
        
        self.calibration_scores[regime] = metrics
        return metrics
    
    def _evaluate_binary_calibration(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray
    ) -> Dict[str, float]:
        """
        Evaluate the calibration quality for binary classification.
        
        Parameters
        ----------
        y_true : ndarray
            True binary labels.
        
        y_prob : ndarray
            Probability estimates from the uncalibrated model.
        
        Returns
        -------
        metrics : dict
            Dictionary of calibration quality metrics.
        """
        # Calculate calibration curve
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10)
        
        # Calculate metrics
        metrics = {}
        
        # Expected Calibration Error (ECE)
        # This is a simplified implementation
        ece = np.sum(np.abs(prob_true - prob_pred)) / len(prob_true)
        metrics['ece'] = ece
        
        # Maximum Calibration Error (MCE)
        mce = np.max(np.abs(prob_true - prob_pred))
        metrics['mce'] = mce
        
        # Brier Score
        brier_score = np.mean((y_prob - y_true) ** 2)
        metrics['brier_score'] = brier_score
        
        # Log Loss
        eps = 1e-15  # Small constant to avoid log(0)
        y_prob_clipped = np.clip(y_prob, eps, 1 - eps)
        log_loss = -np.mean(y_true * np.log(y_prob_clipped) + (1 - y_true) * np.log(1 - y_prob_clipped))
        metrics['log_loss'] = log_loss
        
        return metrics
    
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
    
    def _fit_beta_calibration(
        self,
        y_prob: np.ndarray,
        y_true: np.ndarray,
        sample_weights: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Fit a beta calibration model.
        
        Parameters
        ----------
        y_prob : ndarray
            Probability estimates from the uncalibrated model.
        
        y_true : ndarray
            True binary labels.
        
        sample_weights : ndarray, optional
            Sample weights for fitting the calibration model.
        
        Returns
        -------
        calibrator : dict
            Dictionary with beta calibration parameters.
        """
        # Avoid numerical issues
        eps = 1e-15
        y_prob = np.clip(y_prob, eps, 1 - eps)
        
        # Transform to logit space
        logit_y_prob = np.log(y_prob / (1 - y_prob))
        
        # Fit logistic regression in logit space
        lr = LogisticRegression(C=1.0, solver='lbfgs')
        lr.fit(logit_y_prob.reshape(-1, 1), y_true, sample_weight=sample_weights)
        
        # Extract parameters
        a = lr.coef_[0][0]
        b = lr.intercept_[0]
        
        return {'a': a, 'b': b}
    
    def _apply_beta_calibration(
        self,
        y_prob: np.ndarray,
        calibrator: Dict[str, Any]
    ) -> np.ndarray:
        """
        Apply beta calibration to probability estimates.
        
        Parameters
        ----------
        y_prob : ndarray
            Probability estimates from the uncalibrated model.
        
        calibrator : dict
            Dictionary with beta calibration parameters.
        
        Returns
        -------
        calibrated_probs : ndarray
            Calibrated probability estimates.
        """
        # Avoid numerical issues
        eps = 1e-15
        y_prob = np.clip(y_prob, eps, 1 - eps)
        
        # Extract parameters
        a = calibrator['a']
        b = calibrator['b']
        
        # Transform to logit space
        logit_y_prob = np.log(y_prob / (1 - y_prob))
        
        # Apply calibration in logit space
        logit_calibrated = a * logit_y_prob + b
        
        # Transform back to probability space
        calibrated_probs = 1 / (1 + np.exp(-logit_calibrated))
        
        return calibrated_probs
    
    def visualize_calibration_curve(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        y_prob_calibrated: Optional[Union[pd.Series, np.ndarray]] = None,
        n_bins: int = 10,
        figsize: Tuple[int, int] = (10, 8),
        title: str = 'Calibration Curve',
        regime: Optional[str] = None
    ) -> None:
        """
        Visualize the calibration curve.
        
        Parameters
        ----------
        y_true : array-like
            True binary labels.
        
        y_prob : array-like
            Probability estimates from the uncalibrated model.
        
        y_prob_calibrated : array-like, optional
            Probability estimates from the calibrated model.
            If provided, both uncalibrated and calibrated curves will be shown.
        
        n_bins : int, default=10
            Number of bins for the calibration curve.
        
        figsize : tuple, default=(10, 8)
            Figure size.
        
        title : str, default='Calibration Curve'
            Plot title.
        
        regime : str, optional
            Regime for which to visualize the calibration curve.
            If provided, the title will include the regime.
        """
        # Convert inputs to numpy arrays
        y_true = self._to_numpy(y_true)
        y_prob = self._to_numpy(y_prob)
        
        if y_prob_calibrated is not None:
            y_prob_calibrated = self._to_numpy(y_prob_calibrated)
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Plot diagonal (perfect calibration)
        plt.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')
        
        # Plot uncalibrated curve
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)
        plt.plot(prob_pred, prob_true, 'o-', label='Uncalibrated')
        
        # Plot calibrated curve if provided
        if y_prob_calibrated is not None:
            prob_true_cal, prob_pred_cal = calibration_curve(y_true, y_prob_calibrated, n_bins=n_bins)
            plt.plot(prob_pred_cal, prob_true_cal, 's-', label='Calibrated')
        
        # Calculate metrics
        if regime is not None and regime in self.calibration_scores:
            metrics = self.calibration_scores[regime]
            metrics_text = f"ECE: {metrics['ece']:.4f}, MCE: {metrics['mce']:.4f}, Brier: {metrics['brier_score']:.4f}"
            plt.text(0.05, 0.95, metrics_text, transform=plt.gca().transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
        
        # Set plot properties
        plt.xlabel('Mean predicted probability')
        plt.ylabel('Fraction of positives')
        
        if regime is not None:
            title = f"{title} - Regime: {regime}"
        
        plt.title(title)
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        
        # Show plot
        plt.tight_layout()
        plt.show()
    
    def visualize_calibration_comparison(
        self,
        regimes: List[str],
        metric: str = 'ece',
        figsize: Tuple[int, int] = (12, 6),
        title: str = 'Calibration Comparison Across Regimes'
    ) -> None:
        """
        Visualize calibration metrics across different regimes.
        
        Parameters
        ----------
        regimes : list
            List of regimes to compare.
        
        metric : str, default='ece'
            Calibration metric to visualize. Options include:
            - 'ece': Expected Calibration Error
            - 'mce': Maximum Calibration Error
            - 'brier_score': Brier Score
            - 'log_loss': Log Loss
        
        figsize : tuple, default=(12, 6)
            Figure size.
        
        title : str, default='Calibration Comparison Across Regimes'
            Plot title.
        """
        # Validate regimes
        valid_regimes = [r for r in regimes if r in self.calibration_scores]
        if not valid_regimes:
            logger.warning("No valid regimes found for calibration comparison")
            return
        
        # Validate metric
        valid_metrics = ['ece', 'mce', 'brier_score', 'log_loss']
        if metric not in valid_metrics:
            logger.warning(f"Invalid metric: {metric}, using 'ece' instead")
            metric = 'ece'
        
        # Extract metric values for each regime
        metric_values = []
        for regime in valid_regimes:
            if self.is_multiclass:
                # For multiclass, use average metrics
                if 'average' in self.calibration_scores[regime]:
                    metric_values.append(self.calibration_scores[regime]['average'][metric])
                else:
                    # Skip if average metrics not available
                    continue
            else:
                # For binary classification
                metric_values.append(self.calibration_scores[regime][metric])
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Create bar plot
        bars = plt.bar(valid_regimes, metric_values, alpha=0.7)
        
        # Add value labels on top of bars
        for bar, value in zip(bars, metric_values):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                    f'{value:.4f}', ha='center', va='bottom', fontsize=10)
        
        # Set plot properties
        plt.xlabel('Regime')
        plt.ylabel(metric.replace('_', ' ').title())
        plt.title(f"{title} - Metric: {metric.replace('_', ' ').title()}")
        plt.grid(True, alpha=0.3, axis='y')
        
        # Show plot
        plt.tight_layout()
        plt.show()
    
    def visualize_reliability_diagram(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        y_prob_calibrated: Optional[Union[pd.Series, np.ndarray]] = None,
        n_bins: int = 10,
        figsize: Tuple[int, int] = (12, 10),
        title: str = 'Reliability Diagram',
        regime: Optional[str] = None
    ) -> None:
        """
        Visualize the reliability diagram, which includes the calibration curve
        and the histogram of predicted probabilities.
        
        Parameters
        ----------
        y_true : array-like
            True binary labels.
        
        y_prob : array-like
            Probability estimates from the uncalibrated model.
        
        y_prob_calibrated : array-like, optional
            Probability estimates from the calibrated model.
            If provided, both uncalibrated and calibrated curves will be shown.
        
        n_bins : int, default=10
            Number of bins for the calibration curve and histogram.
        
        figsize : tuple, default=(12, 10)
            Figure size.
        
        title : str, default='Reliability Diagram'
            Plot title.
        
        regime : str, optional
            Regime for which to visualize the reliability diagram.
            If provided, the title will include the regime.
        """
        # Convert inputs to numpy arrays
        y_true = self._to_numpy(y_true)
        y_prob = self._to_numpy(y_prob)
        
        if y_prob_calibrated is not None:
            y_prob_calibrated = self._to_numpy(y_prob_calibrated)
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot calibration curve (top subplot)
        ax1.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')
        
        # Plot uncalibrated curve
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)
        ax1.plot(prob_pred, prob_true, 'o-', label='Uncalibrated')
        
        # Plot calibrated curve if provided
        if y_prob_calibrated is not None:
            prob_true_cal, prob_pred_cal = calibration_curve(y_true, y_prob_calibrated, n_bins=n_bins)
            ax1.plot(prob_pred_cal, prob_true_cal, 's-', label='Calibrated')
        
        # Calculate metrics
        if regime is not None and regime in self.calibration_scores:
            metrics = self.calibration_scores[regime]
            metrics_text = f"ECE: {metrics['ece']:.4f}, MCE: {metrics['mce']:.4f}, Brier: {metrics['brier_score']:.4f}"
            ax1.text(0.05, 0.95, metrics_text, transform=ax1.transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
        
        # Set top subplot properties
        ax1.set_xlabel('Mean predicted probability')
        ax1.set_ylabel('Fraction of positives')
        ax1.set_title(title + (f" - Regime: {regime}" if regime is not None else ""))
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        
        # Plot histogram of predicted probabilities (bottom subplot)
        bin_edges = np.linspace(0, 1, n_bins + 1)
        
        # Plot uncalibrated histogram
        ax2.hist(y_prob, bins=bin_edges, alpha=0.5, label='Uncalibrated', density=True)
        
        # Plot calibrated histogram if provided
        if y_prob_calibrated is not None:
            ax2.hist(y_prob_calibrated, bins=bin_edges, alpha=0.5, label='Calibrated', density=True)
        
        # Set bottom subplot properties
        ax2.set_xlabel('Predicted probability')
        ax2.set_ylabel('Density')
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        
        # Show plot
        plt.tight_layout()
        plt.show()
    
    def save(self, filepath: str) -> None:
        """
        Save the calibrator to a file.
        
        Parameters
        ----------
        filepath : str
            Path to save the calibrator.
        """
        import joblib
        joblib.dump(self, filepath)
        logger.info(f"Saved calibrator to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'ModelCalibrator':
        """
        Load a calibrator from a file.
        
        Parameters
        ----------
        filepath : str
            Path to load the calibrator from.
        
        Returns
        -------
        calibrator : ModelCalibrator
            The loaded calibrator.
        """
        import joblib
        calibrator = joblib.load(filepath)
        logger.info(f"Loaded calibrator from {filepath}")
        return calibrator

def calibrate_probabilities(
    y_true: Union[pd.Series, np.ndarray],
    y_prob: Union[pd.Series, np.ndarray, pd.DataFrame],
    method: str = 'platt',
    regimes: Optional[Union[pd.Series, np.ndarray]] = None,
    test_y_prob: Optional[Union[pd.Series, np.ndarray, pd.DataFrame]] = None,
    test_regime: Optional[str] = None
) -> Union[np.ndarray, Tuple[np.ndarray, ModelCalibrator]]:
    """
    Convenience function to calibrate probability estimates.
    
    Parameters
    ----------
    y_true : array-like
        True binary labels for training the calibration model.
    
    y_prob : array-like
        Probability estimates from the uncalibrated model for training.
    
    method : str, default='platt'
        The calibration method to use. Options include:
        - 'platt': Platt scaling (logistic regression)
        - 'isotonic': Isotonic regression
        - 'beta': Beta calibration
        - 'ensemble': Ensemble of calibration methods
    
    regimes : array-like, optional
        Regime labels for each training sample. If provided,
        separate calibration models will be fit for each regime.
    
    test_y_prob : array-like, optional
        Probability estimates to calibrate. If not provided,
        the training probabilities will be calibrated.
    
    test_regime : str, optional
        The regime to use for calibrating test_y_prob.
        Only used if regimes is provided and test_y_prob is provided.
    
    Returns
    -------
    calibrated_probs : ndarray
        Calibrated probability estimates.
    
    calibrator : ModelCalibrator, optional
        The fitted calibrator. Only returned if return_calibrator=True.
    """
    # Create and fit calibrator
    calibrator = ModelCalibrator(method=method, regime_aware=(regimes is not None))
    calibrator.fit(y_true, y_prob, regimes=regimes)
    
    # Calibrate probabilities
    if test_y_prob is not None:
        calibrated_probs = calibrator.calibrate(test_y_prob, regime=test_regime)
    else:
        calibrated_probs = calibrator.calibrate(y_prob, regime=None)
    
    return calibrated_probs, calibrator

def evaluate_calibration(
    y_true: Union[pd.Series, np.ndarray],
    y_prob: Union[pd.Series, np.ndarray],
    y_prob_calibrated: Optional[Union[pd.Series, np.ndarray]] = None,
    visualize: bool = True,
    n_bins: int = 10
) -> Dict[str, float]:
    """
    Convenience function to evaluate calibration quality.
    
    Parameters
    ----------
    y_true : array-like
        True binary labels.
    
    y_prob : array-like
        Probability estimates from the uncalibrated model.
    
    y_prob_calibrated : array-like, optional
        Probability estimates from the calibrated model.
        If provided, both uncalibrated and calibrated metrics will be returned.
    
    visualize : bool, default=True
        Whether to visualize the calibration curve.
    
    n_bins : int, default=10
        Number of bins for the calibration curve.
    
    Returns
    -------
    metrics : dict
        Dictionary of calibration quality metrics.
    """
    # Convert inputs to numpy arrays
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    
    if y_prob_calibrated is not None:
        y_prob_calibrated = np.asarray(y_prob_calibrated)
    
    # Calculate calibration curve
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)
    
    # Calculate metrics for uncalibrated probabilities
    metrics = {}
    
    # Expected Calibration Error (ECE)
    ece = np.sum(np.abs(prob_true - prob_pred)) / len(prob_true)
    metrics['uncalibrated_ece'] = ece
    
    # Maximum Calibration Error (MCE)
    mce = np.max(np.abs(prob_true - prob_pred))
    metrics['uncalibrated_mce'] = mce
    
    # Brier Score
    brier_score = np.mean((y_prob - y_true) ** 2)
    metrics['uncalibrated_brier_score'] = brier_score
    
    # Log Loss
    eps = 1e-15  # Small constant to avoid log(0)
    y_prob_clipped = np.clip(y_prob, eps, 1 - eps)
    log_loss = -np.mean(y_true * np.log(y_prob_clipped) + (1 - y_true) * np.log(1 - y_prob_clipped))
    metrics['uncalibrated_log_loss'] = log_loss
    
    # Calculate metrics for calibrated probabilities if provided
    if y_prob_calibrated is not None:
        # Calculate calibration curve
        prob_true_cal, prob_pred_cal = calibration_curve(y_true, y_prob_calibrated, n_bins=n_bins)
        
        # Expected Calibration Error (ECE)
        ece_cal = np.sum(np.abs(prob_true_cal - prob_pred_cal)) / len(prob_true_cal)
        metrics['calibrated_ece'] = ece_cal
        
        # Maximum Calibration Error (MCE)
        mce_cal = np.max(np.abs(prob_true_cal - prob_pred_cal))
        metrics['calibrated_mce'] = mce_cal
        
        # Brier Score
        brier_score_cal = np.mean((y_prob_calibrated - y_true) ** 2)
        metrics['calibrated_brier_score'] = brier_score_cal
        
        # Log Loss
        y_prob_cal_clipped = np.clip(y_prob_calibrated, eps, 1 - eps)
        log_loss_cal = -np.mean(y_true * np.log(y_prob_cal_clipped) + (1 - y_true) * np.log(1 - y_prob_cal_clipped))
        metrics['calibrated_log_loss'] = log_loss_cal
    
    # Visualize calibration curve if requested
    if visualize:
        plt.figure(figsize=(10, 8))
        
        # Plot diagonal (perfect calibration)
        plt.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')
        
        # Plot uncalibrated curve
        plt.plot(prob_pred, prob_true, 'o-', label='Uncalibrated')
        
        # Plot calibrated curve if provided
        if y_prob_calibrated is not None:
            plt.plot(prob_pred_cal, prob_true_cal, 's-', label='Calibrated')
        
        # Add metrics to plot
        metrics_text = f"Uncalibrated - ECE: {metrics['uncalibrated_ece']:.4f}, Brier: {metrics['uncalibrated_brier_score']:.4f}"
        if y_prob_calibrated is not None:
            metrics_text += f"\nCalibrated - ECE: {metrics['calibrated_ece']:.4f}, Brier: {metrics['calibrated_brier_score']:.4f}"
        
        plt.text(0.05, 0.95, metrics_text, transform=plt.gca().transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
        
        # Set plot properties
        plt.xlabel('Mean predicted probability')
        plt.ylabel('Fraction of positives')
        plt.title('Calibration Curve')
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        
        # Show plot
        plt.tight_layout()
        plt.show()
    
    return metrics 