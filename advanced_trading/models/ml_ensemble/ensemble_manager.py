"""
Ensemble Manager
---------------
Manages a collection of ML models and implements ensemble methods for prediction.
This module serves as the core of the ML ensemble framework, providing:
1. Support for heterogeneous model types (tree-based, neural, statistical)
2. Various ensemble methods (stacking, bagging, boosting)
3. Regime-specific model selection and weighting
4. Feature importance analysis across different market conditions
5. Integration with adaptive strategy frameworks
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
import joblib
import logging
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

# Get the logger
logger = logging.getLogger(__name__)

class EnsembleManager:
    """
    Manages a collection of ML models and implements ensemble methods for prediction.
    
    This class supports:
    - Multiple model types (classification, regression)
    - Various ensemble techniques (voting, stacking, weighted average)
    - Regime-specific model selection
    - Feature importance tracking across regimes
    - Dynamic model weighting based on recent performance
    
    Parameters:
    -----------
    base_models : Dict[str, Any]
        Dictionary of base models with model name as key
    ensemble_method : str
        Method for ensembling ('voting', 'stacking', 'weighted_avg')
    model_type : str
        Type of models ('classification' or 'regression')
    regime_aware : bool
        Whether to use regime-specific model selection and weighting
    feature_names : List[str]
        Names of features used by the models
    meta_model : Optional[Any]
        Model to use for stacking (if ensemble_method='stacking')
    weight_update_freq : int
        Frequency (in days) to update model weights
    model_memory : int
        Number of days to remember model performance
    """
    
    def __init__(
        self,
        base_models: Dict[str, Any],
        ensemble_method: str = 'weighted_avg',
        model_type: str = 'classification',
        regime_aware: bool = True,
        feature_names: Optional[List[str]] = None,
        meta_model: Optional[Any] = None,
        weight_update_freq: int = 5,
        model_memory: int = 60
    ):
        self.base_models = base_models
        self.model_names = list(base_models.keys())
        self.ensemble_method = ensemble_method
        self.model_type = model_type
        self.regime_aware = regime_aware
        self.feature_names = feature_names
        self.meta_model = meta_model
        self.weight_update_freq = weight_update_freq
        self.model_memory = model_memory
        
        # Initialize model weights equally
        self.model_weights = {model_name: 1.0 / len(base_models) for model_name in self.model_names}
        
        # Track performance by regime
        self.regime_performance = {}
        
        # Track feature importance by regime
        self.feature_importance_by_regime = {}
        
        # Track predictions for post-analysis
        self.prediction_history = pd.DataFrame()
        
        # Track metrics by model
        self.model_metrics = {model_name: [] for model_name in self.model_names}
        
        # Days since last weight update
        self.days_since_update = 0
    
    def fit(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        regimes: Optional[pd.Series] = None,
        sample_weights: Optional[np.ndarray] = None
    ) -> None:
        """
        Fit all base models and the meta model (if using stacking)
        
        Parameters:
        -----------
        X : pd.DataFrame
            Features for training
        y : pd.Series
            Target variable
        regimes : Optional[pd.Series]
            Series of regime labels corresponding to each sample
        sample_weights : Optional[np.ndarray]
            Sample weights for training
        """
        # Store feature names if not already set
        if self.feature_names is None:
            self.feature_names = list(X.columns)
        
        # If regime-aware, fit models separately for each regime
        if self.regime_aware and regimes is not None:
            unique_regimes = regimes.unique()
            
            for regime in unique_regimes:
                regime_mask = (regimes == regime)
                regime_X = X[regime_mask]
                regime_y = y[regime_mask]
                
                if sample_weights is not None:
                    regime_weights = sample_weights[regime_mask]
                else:
                    regime_weights = None
                
                # Skip if not enough data for this regime
                if len(regime_X) < 30:  # Minimal data required
                    logger.warning(f"Not enough data for regime {regime}. Skipping.")
                    continue
                
                # Fit each base model on this regime
                for model_name, model in self.base_models.items():
                    if sample_weights is not None:
                        if hasattr(model, 'fit') and 'sample_weight' in model.fit.__code__.co_varnames:
                            model.fit(regime_X, regime_y, sample_weight=regime_weights)
                        else:
                            model.fit(regime_X, regime_y)
                    
                    # Extract and store feature importance if available
                    self._extract_feature_importance(model, regime)
                
                # Store model for this regime
                self._save_regime_models(regime)
        
        # Also fit models on entire dataset
        for model_name, model in self.base_models.items():
            if sample_weights is not None and hasattr(model, 'fit') and 'sample_weight' in model.fit.__code__.co_varnames:
                model.fit(X, y, sample_weight=sample_weights)
            else:
                model.fit(X, y)
            
            # Extract and store feature importance for overall model
            self._extract_feature_importance(model, 'overall')
        
        # Fit meta model if using stacking
        if self.ensemble_method == 'stacking' and self.meta_model is not None:
            self._fit_meta_model(X, y, sample_weights)
    
    def predict(
        self, 
        X: pd.DataFrame, 
        current_regime: Optional[str] = None
    ) -> np.ndarray:
        """
        Generate predictions using the ensemble
        
        Parameters:
        -----------
        X : pd.DataFrame
            Features for prediction
        current_regime : Optional[str]
            Current market regime (if regime_aware is True)
            
        Returns:
        --------
        np.ndarray
            Predictions from the ensemble
        """
        # Get predictions from each base model
        base_predictions = self._get_base_predictions(X)
        
        # Use regime-specific weights if applicable
        if self.regime_aware and current_regime is not None:
            weights = self._get_regime_weights(current_regime)
        else:
            weights = self.model_weights
        
        # Ensemble predictions based on method
        if self.ensemble_method == 'voting':
            return self._voting_ensemble(base_predictions)
        elif self.ensemble_method == 'stacking' and self.meta_model is not None:
            return self._stacking_ensemble(base_predictions)
        else:  # Default to weighted average
            return self._weighted_average_ensemble(base_predictions, weights)
    
    def update_weights(
        self, 
        recent_predictions: Dict[str, np.ndarray], 
        recent_targets: np.ndarray,
        current_regime: Optional[str] = None
    ) -> None:
        """
        Update model weights based on recent performance
        
        Parameters:
        -----------
        recent_predictions : Dict[str, np.ndarray]
            Recent predictions from each model
        recent_targets : np.ndarray
            Actual target values for comparison
        current_regime : Optional[str]
            Current market regime
        """
        # Update only at specified frequency
        self.days_since_update += 1
        if self.days_since_update < self.weight_update_freq:
            return
        
        self.days_since_update = 0
        
        # Calculate performance metrics for each model
        performance_metrics = {}
        
        for model_name, preds in recent_predictions.items():
            if self.model_type == 'classification':
                # Classification metrics
                accuracy = accuracy_score(recent_targets, (preds > 0.5).astype(int))
                precision = precision_score(recent_targets, (preds > 0.5).astype(int), zero_division=0)
                recall = recall_score(recent_targets, (preds > 0.5).astype(int), zero_division=0)
                f1 = f1_score(recent_targets, (preds > 0.5).astype(int), zero_division=0)
                
                # Composite score
                performance_metrics[model_name] = (2 * f1 + accuracy) / 3
            else:
                # Regression metrics (lower is better, so invert)
                mse = mean_squared_error(recent_targets, preds)
                performance_metrics[model_name] = 1 / (1 + mse)  # Transform to 0-1 scale
            
            # Store metrics for this model
            self.model_metrics[model_name].append(performance_metrics[model_name])
            
            # Trim history if too long
            if len(self.model_metrics[model_name]) > self.model_memory:
                self.model_metrics[model_name] = self.model_metrics[model_name][-self.model_memory:]
        
        # Convert metrics to weights (softmax)
        performance_values = np.array(list(performance_metrics.values()))
        exp_values = np.exp(performance_values - np.max(performance_values))  # Numerical stability
        softmax_weights = exp_values / exp_values.sum()
        
        # Update weights
        for i, model_name in enumerate(performance_metrics.keys()):
            # Weighted average of old and new weights for smooth transitions
            self.model_weights[model_name] = 0.7 * self.model_weights[model_name] + 0.3 * softmax_weights[i]
        
        # Normalize weights to sum to 1
        weight_sum = sum(self.model_weights.values())
        self.model_weights = {k: v / weight_sum for k, v in self.model_weights.items()}
        
        # Store regime-specific weights if applicable
        if self.regime_aware and current_regime is not None:
            if current_regime not in self.regime_performance:
                self.regime_performance[current_regime] = {}
            
            self.regime_performance[current_regime] = self.model_weights.copy()
    
    def get_feature_importance(self, regime: Optional[str] = None) -> pd.DataFrame:
        """
        Get feature importance across models
        
        Parameters:
        -----------
        regime : Optional[str]
            Specific regime to get feature importance for
            
        Returns:
        --------
        pd.DataFrame
            Feature importance scores
        """
        if regime is not None and regime in self.feature_importance_by_regime:
            return self.feature_importance_by_regime[regime]
        elif 'overall' in self.feature_importance_by_regime:
            return self.feature_importance_by_regime['overall']
        else:
            logger.warning("No feature importance data available")
            return pd.DataFrame()
    
    def _extract_feature_importance(self, model: Any, regime: str) -> None:
        """Extract feature importance from model if available"""
        importance_dict = {}
        
        # Try different attribute names for feature importance
        if hasattr(model, 'feature_importances_'):
            importance = model.feature_importances_
            for i, feat_name in enumerate(self.feature_names):
                importance_dict[feat_name] = importance[i]
        elif hasattr(model, 'coef_'):
            importance = np.abs(model.coef_)
            if importance.ndim > 1:
                importance = importance.mean(axis=0)
            for i, feat_name in enumerate(self.feature_names):
                importance_dict[feat_name] = importance[i]
        else:
            return  # No feature importance available
        
        # Store in a DataFrame
        importance_df = pd.DataFrame.from_dict(importance_dict, orient='index', columns=['importance'])
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        # Store by regime
        self.feature_importance_by_regime[regime] = importance_df
    
    def _save_regime_models(self, regime: str) -> None:
        """Save models specific to a regime"""
        # In a production system, we would save these models to disk
        # For now, just store them in memory
        if regime not in self.regime_performance:
            self.regime_performance[regime] = self.model_weights.copy()
    
    def _get_regime_weights(self, regime: str) -> Dict[str, float]:
        """Get model weights for a specific regime"""
        if regime in self.regime_performance:
            return self.regime_performance[regime]
        else:
            logger.warning(f"No weights for regime {regime}. Using default weights.")
            return self.model_weights
    
    def _get_base_predictions(self, X: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Get predictions from all base models"""
        predictions = {}
        
        for model_name, model in self.base_models.items():
            try:
                if self.model_type == 'classification' and hasattr(model, 'predict_proba'):
                    # Get probability of positive class
                    pred = model.predict_proba(X)[:, 1]
                else:
                    pred = model.predict(X)
                
                predictions[model_name] = pred
            except Exception as e:
                logger.error(f"Error getting predictions from model {model_name}: {e}")
                # Fill with zeros as fallback
                predictions[model_name] = np.zeros(len(X))
        
        return predictions
    
    def _voting_ensemble(self, predictions: Dict[str, np.ndarray]) -> np.ndarray:
        """Implement voting ensemble"""
        all_preds = np.array(list(predictions.values()))
        
        if self.model_type == 'classification':
            # Majority vote for classification
            votes = (all_preds > 0.5).astype(int)
            return np.mean(votes, axis=0)
        else:
            # Mean for regression
            return np.mean(all_preds, axis=0)
    
    def _weighted_average_ensemble(
        self, 
        predictions: Dict[str, np.ndarray], 
        weights: Dict[str, float]
    ) -> np.ndarray:
        """Implement weighted average ensemble"""
        weighted_preds = np.zeros(len(list(predictions.values())[0]))
        
        for model_name, preds in predictions.items():
            weighted_preds += preds * weights[model_name]
        
        return weighted_preds
    
    def _stacking_ensemble(self, predictions: Dict[str, np.ndarray]) -> np.ndarray:
        """Implement stacking ensemble"""
        # Convert predictions to a matrix for the meta-model
        X_meta = np.column_stack(list(predictions.values()))
        
        # Use meta-model to make final predictions
        return self.meta_model.predict(X_meta)
    
    def _fit_meta_model(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        sample_weights: Optional[np.ndarray] = None
    ) -> None:
        """Fit the meta-model for stacking"""
        # Use k-fold cross-validation to generate out-of-fold predictions
        tscv = TimeSeriesSplit(n_splits=5)
        meta_features = np.zeros((len(X), len(self.base_models)))
        
        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            if sample_weights is not None:
                train_weights = sample_weights[train_idx]
            else:
                train_weights = None
            
            # Train each model on the training fold
            for i, (model_name, model) in enumerate(self.base_models.items()):
                if train_weights is not None and hasattr(model, 'fit') and 'sample_weight' in model.fit.__code__.co_varnames:
                    model.fit(X_train, y_train, sample_weight=train_weights)
                else:
                    model.fit(X_train, y_train)
                
                # Generate predictions for the test fold
                if self.model_type == 'classification' and hasattr(model, 'predict_proba'):
                    meta_features[test_idx, i] = model.predict_proba(X_test)[:, 1]
                else:
                    meta_features[test_idx, i] = model.predict(X_test)
        
        # Train the meta-model on the predictions
        if sample_weights is not None and hasattr(self.meta_model, 'fit') and 'sample_weight' in self.meta_model.fit.__code__.co_varnames:
            self.meta_model.fit(meta_features, y, sample_weight=sample_weights)
        else:
            self.meta_model.fit(meta_features, y)

    def save(self, filepath: str) -> None:
        """
        Save the ensemble model to disk
        
        Parameters:
        -----------
        filepath : str
            Path to save the model to
        """
        save_path = Path(filepath)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'base_models': self.base_models,
            'meta_model': self.meta_model,
            'model_weights': self.model_weights,
            'regime_performance': self.regime_performance,
            'feature_importance_by_regime': self.feature_importance_by_regime,
            'model_metrics': self.model_metrics,
            'feature_names': self.feature_names,
            'ensemble_method': self.ensemble_method,
            'model_type': self.model_type,
            'regime_aware': self.regime_aware
        }
        
        joblib.dump(data, save_path)
        logger.info(f"Ensemble model saved to {save_path}")

    @classmethod
    def load(cls, filepath: str) -> 'EnsembleManager':
        """
        Load the ensemble model from disk
        
        Parameters:
        -----------
        filepath : str
            Path to load the model from
            
        Returns:
        --------
        EnsembleManager
            Loaded ensemble model
        """
        data = joblib.load(filepath)
        
        # Create instance with base initialization
        ensemble = cls(
            base_models=data['base_models'],
            ensemble_method=data['ensemble_method'],
            model_type=data['model_type'],
            regime_aware=data['regime_aware'],
            feature_names=data['feature_names'],
            meta_model=data['meta_model']
        )
        
        # Restore state
        ensemble.model_weights = data['model_weights']
        ensemble.regime_performance = data['regime_performance']
        ensemble.feature_importance_by_regime = data['feature_importance_by_regime']
        ensemble.model_metrics = data['model_metrics']
        
        return ensemble

    def visualize_feature_importance(
        self, 
        regime: Optional[str] = None, 
        top_n: int = 15
    ) -> None:
        """
        Visualize feature importance
        
        Parameters:
        -----------
        regime : Optional[str]
            Specific regime to visualize feature importance for
        top_n : int
            Number of top features to show
        """
        importance_df = self.get_feature_importance(regime)
        
        if importance_df.empty:
            logger.warning("No feature importance data available for visualization")
            return
        
        # Get top N features
        top_features = importance_df.head(top_n)
        
        # Plot
        plt.figure(figsize=(10, 8))
        plt.barh(
            top_features.index[::-1], 
            top_features['importance'][::-1],
            color='skyblue'
        )
        plt.xlabel('Importance')
        plt.ylabel('Feature')
        plt.title(f'Top {top_n} Features by Importance' + 
                 (f' (Regime: {regime})' if regime else ''))
        plt.tight_layout()
        
        # Show plot
        plt.show()

    def visualize_model_weights(self, regimes: Optional[List[str]] = None) -> None:
        """
        Visualize model weights across regimes
        
        Parameters:
        -----------
        regimes : Optional[List[str]]
            Specific regimes to visualize weights for
        """
        if regimes is None:
            regimes = list(self.regime_performance.keys())
            if 'overall' not in regimes:
                regimes.append('overall')
        
        # Create DataFrame of weights
        weights_data = {}
        
        for regime in regimes:
            if regime == 'overall':
                weights_data[regime] = self.model_weights
            elif regime in self.regime_performance:
                weights_data[regime] = self.regime_performance[regime]
        
        if not weights_data:
            logger.warning("No model weight data available for visualization")
            return
        
        # Convert to DataFrame
        weights_df = pd.DataFrame(weights_data)
        
        # Plot
        plt.figure(figsize=(12, 6))
        weights_df.plot(kind='bar', figsize=(12, 6))
        plt.xlabel('Model')
        plt.ylabel('Weight')
        plt.title('Model Weights Across Regimes')
        plt.legend(title='Regime')
        plt.tight_layout()
        
        # Show plot
        plt.show()

    def visualize_model_performance(self) -> None:
        """Visualize model performance over time"""
        # Convert metrics to DataFrame
        perf_data = {}
        
        for model_name, metrics in self.model_metrics.items():
            if metrics:  # Check if non-empty
                perf_data[model_name] = metrics
        
        if not perf_data:
            logger.warning("No model performance data available for visualization")
            return
        
        perf_df = pd.DataFrame(perf_data)
        
        # Plot
        plt.figure(figsize=(12, 6))
        perf_df.plot(figsize=(12, 6))
        plt.xlabel('Time')
        plt.ylabel('Performance Metric')
        plt.title('Model Performance Over Time')
        plt.legend(title='Model')
        plt.tight_layout()
        
        # Show plot
        plt.show() 