"""
Feature Selection Module
-----------------------
Provides methods for selecting the most relevant features for ML models.
This module implements various feature selection techniques specifically
designed for financial time series data, including:

1. Filter methods (correlation, mutual information)
2. Wrapper methods (recursive feature elimination)
3. Embedded methods (model-based importance)
4. Stability selection across different market regimes
5. Time-series specific feature selection
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import logging
from sklearn.feature_selection import (
    SelectKBest, SelectFromModel, RFE, RFECV, 
    f_classif, f_regression, mutual_info_classif, mutual_info_regression
)
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Lasso, LogisticRegression
import matplotlib.pyplot as plt
from pathlib import Path
import joblib
import warnings

# Get the logger
logger = logging.getLogger(__name__)

class FeatureSelector:
    """
    Feature selection for financial time series data.
    
    This class provides methods for selecting the most relevant features
    for machine learning models in financial applications. It supports
    various feature selection techniques and is designed to work with
    the EnsembleManager class.
    
    Parameters:
    -----------
    selection_method : str
        Method for feature selection ('filter', 'wrapper', 'embedded', 'stability')
    n_features : int or float
        Number of features to select (int) or fraction of features to select (float < 1.0)
    model_type : str
        Type of models ('classification' or 'regression')
    base_estimator : Optional[Any]
        Base estimator for wrapper and embedded methods
    regime_aware : bool
        Whether to perform regime-specific feature selection
    """
    
    def __init__(
        self,
        selection_method: str = 'filter',
        n_features: Union[int, float] = 10,
        model_type: str = 'classification',
        base_estimator: Optional[Any] = None,
        regime_aware: bool = True
    ):
        """Initialize the feature selector."""
        self.selection_method = selection_method.lower()
        self.n_features = n_features
        self.model_type = model_type.lower()
        self.regime_aware = regime_aware
        self.selected_features: Dict[str, List[str]] = {}
        self.feature_importances: Dict[str, pd.DataFrame] = {}
        self.selectors: Dict[str, Any] = {}
        
        # Set up base estimator if not provided
        if base_estimator is None:
            if self.model_type == 'classification':
                self.base_estimator = RandomForestClassifier(n_estimators=100, random_state=42)
            else:
                self.base_estimator = RandomForestRegressor(n_estimators=100, random_state=42)
        else:
            self.base_estimator = base_estimator
    
    def fit(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        regimes: Optional[pd.Series] = None
    ) -> 'FeatureSelector':
        """
        Fit the feature selector to the data.
        
        Parameters:
        -----------
        X : pd.DataFrame
            Feature matrix
        y : pd.Series
            Target variable
        regimes : Optional[pd.Series]
            Market regime labels for regime-specific feature selection
            
        Returns:
        --------
        self : FeatureSelector
            The fitted feature selector
        """
        feature_names = X.columns.tolist()
        
        if self.regime_aware and regimes is not None:
            # Perform regime-specific feature selection
            unique_regimes = regimes.unique()
            
            for regime in unique_regimes:
                regime_mask = (regimes == regime)
                X_regime = X[regime_mask]
                y_regime = y[regime_mask]
                
                if len(X_regime) < 10:  # Skip regimes with too few samples
                    logger.warning(f"Regime {regime} has too few samples for feature selection")
                    continue
                
                selector = self._create_selector()
                
                try:
                    # Fit the selector
                    selector.fit(X_regime, y_regime)
                    
                    # Store the selector
                    self.selectors[str(regime)] = selector
                    
                    # Get selected features
                    selected_features = self._get_selected_features(selector, feature_names)
                    self.selected_features[str(regime)] = selected_features
                    
                    # Get feature importances
                    importances = self._get_feature_importances(selector, feature_names)
                    self.feature_importances[str(regime)] = importances
                    
                    logger.info(f"Selected {len(selected_features)} features for regime {regime}")
                except Exception as e:
                    logger.error(f"Error in feature selection for regime {regime}: {str(e)}")
        else:
            # Perform global feature selection
            selector = self._create_selector()
            
            try:
                # Fit the selector
                selector.fit(X, y)
                
                # Store the selector
                self.selectors['global'] = selector
                
                # Get selected features
                selected_features = self._get_selected_features(selector, feature_names)
                self.selected_features['global'] = selected_features
                
                # Get feature importances
                importances = self._get_feature_importances(selector, feature_names)
                self.feature_importances['global'] = importances
                
                logger.info(f"Selected {len(selected_features)} features globally")
            except Exception as e:
                logger.error(f"Error in global feature selection: {str(e)}")
        
        return self
    
    def transform(
        self, 
        X: pd.DataFrame, 
        current_regime: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Transform the data by selecting features.
        
        Parameters:
        -----------
        X : pd.DataFrame
            Feature matrix
        current_regime : Optional[str]
            Current market regime for regime-specific feature selection
            
        Returns:
        --------
        pd.DataFrame
            Transformed feature matrix with selected features
        """
        if self.regime_aware and current_regime is not None and current_regime in self.selectors:
            # Use regime-specific selector
            selector = self.selectors[current_regime]
            selected_features = self.selected_features[current_regime]
        else:
            # Use global selector
            selector = self.selectors.get('global')
            selected_features = self.selected_features.get('global', [])
            
            if selector is None:
                logger.warning("No selector found, returning original features")
                return X
        
        # Return selected features
        return X[selected_features]
    
    def fit_transform(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        regimes: Optional[pd.Series] = None,
        current_regime: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fit the feature selector and transform the data.
        
        Parameters:
        -----------
        X : pd.DataFrame
            Feature matrix
        y : pd.Series
            Target variable
        regimes : Optional[pd.Series]
            Market regime labels for regime-specific feature selection
        current_regime : Optional[str]
            Current market regime for regime-specific feature selection
            
        Returns:
        --------
        pd.DataFrame
            Transformed feature matrix with selected features
        """
        self.fit(X, y, regimes)
        return self.transform(X, current_regime)
    
    def get_feature_importance(
        self, 
        regime: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get feature importance for a specific regime or globally.
        
        Parameters:
        -----------
        regime : Optional[str]
            Market regime for regime-specific feature importance
            
        Returns:
        --------
        pd.DataFrame
            Feature importance scores
        """
        if self.regime_aware and regime is not None and regime in self.feature_importances:
            return self.feature_importances[regime]
        else:
            return self.feature_importances.get('global', pd.DataFrame())
    
    def get_selected_features(
        self, 
        regime: Optional[str] = None
    ) -> List[str]:
        """
        Get selected features for a specific regime or globally.
        
        Parameters:
        -----------
        regime : Optional[str]
            Market regime for regime-specific selected features
            
        Returns:
        --------
        List[str]
            List of selected feature names
        """
        if self.regime_aware and regime is not None and regime in self.selected_features:
            return self.selected_features[regime]
        else:
            return self.selected_features.get('global', [])
    
    def visualize_feature_importance(
        self, 
        regime: Optional[str] = None, 
        top_n: int = 15,
        figsize: Tuple[int, int] = (10, 8)
    ) -> None:
        """
        Visualize feature importance.
        
        Parameters:
        -----------
        regime : Optional[str]
            Market regime for regime-specific visualization
        top_n : int
            Number of top features to display
        figsize : Tuple[int, int]
            Figure size
        """
        importances = self.get_feature_importance(regime)
        
        if importances.empty:
            logger.warning("No feature importances available for visualization")
            return
        
        # Sort by importance and take top N
        importances = importances.sort_values('importance', ascending=False).head(top_n)
        
        # Create plot
        plt.figure(figsize=figsize)
        plt.barh(importances.index, importances['importance'])
        plt.xlabel('Importance')
        plt.ylabel('Feature')
        plt.title(f'Feature Importance ({regime if regime else "Global"})')
        plt.tight_layout()
        plt.show()
    
    def save(self, filepath: str) -> None:
        """
        Save the feature selector to a file.
        
        Parameters:
        -----------
        filepath : str
            Path to save the feature selector
        """
        # Create directory if it doesn't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Save the feature selector
        joblib.dump(self, filepath)
        logger.info(f"Feature selector saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'FeatureSelector':
        """
        Load a feature selector from a file.
        
        Parameters:
        -----------
        filepath : str
            Path to load the feature selector from
            
        Returns:
        --------
        FeatureSelector
            The loaded feature selector
        """
        # Load the feature selector
        selector = joblib.load(filepath)
        logger.info(f"Feature selector loaded from {filepath}")
        return selector
    
    def _create_selector(self) -> Any:
        """Create a feature selector based on the selection method."""
        if self.selection_method == 'filter':
            return self._create_filter_selector()
        elif self.selection_method == 'wrapper':
            return self._create_wrapper_selector()
        elif self.selection_method == 'embedded':
            return self._create_embedded_selector()
        elif self.selection_method == 'stability':
            return self._create_stability_selector()
        else:
            raise ValueError(f"Unknown selection method: {self.selection_method}")
    
    def _create_filter_selector(self) -> Any:
        """Create a filter-based feature selector."""
        # Determine the scoring function based on the model type
        if self.model_type == 'classification':
            score_func = mutual_info_classif
        else:
            score_func = mutual_info_regression
        
        # Create the selector
        return SelectKBest(score_func=score_func, k=self._get_k())
    
    def _create_wrapper_selector(self) -> Any:
        """Create a wrapper-based feature selector."""
        # Create the selector
        if isinstance(self.n_features, float) and self.n_features < 1.0:
            # Use cross-validation to determine the optimal number of features
            return RFECV(
                estimator=self.base_estimator,
                step=1,
                cv=5,
                scoring='accuracy' if self.model_type == 'classification' else 'neg_mean_squared_error',
                min_features_to_select=max(1, int(self.n_features * 100))  # At least 1 feature
            )
        else:
            # Use a fixed number of features
            return RFE(
                estimator=self.base_estimator,
                n_features_to_select=self._get_k(),
                step=1
            )
    
    def _create_embedded_selector(self) -> Any:
        """Create an embedded feature selector."""
        # Create the selector
        if self.model_type == 'classification':
            estimator = LogisticRegression(C=0.1, penalty='l1', solver='liblinear', random_state=42)
        else:
            estimator = Lasso(alpha=0.1, random_state=42)
        
        # Create the selector
        return SelectFromModel(
            estimator=estimator,
            threshold='median',
            max_features=self._get_k()
        )
    
    def _create_stability_selector(self) -> Any:
        """Create a stability-based feature selector."""
        # For stability selection, we'll use RandomForest which is inherently stable
        if self.model_type == 'classification':
            estimator = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            estimator = RandomForestRegressor(n_estimators=100, random_state=42)
        
        # Create the selector
        return SelectFromModel(
            estimator=estimator,
            threshold='median',
            max_features=self._get_k()
        )
    
    def _get_k(self) -> int:
        """Get the number of features to select."""
        if isinstance(self.n_features, int):
            return self.n_features
        elif isinstance(self.n_features, float) and self.n_features < 1.0:
            # Placeholder - will be determined during fit
            return 10
        else:
            raise ValueError(f"Invalid n_features: {self.n_features}")
    
    def _get_selected_features(self, selector: Any, feature_names: List[str]) -> List[str]:
        """Get the selected features from a fitted selector."""
        if hasattr(selector, 'get_support'):
            # For SelectKBest, RFE, RFECV
            mask = selector.get_support()
            return [feature_names[i] for i in range(len(feature_names)) if mask[i]]
        elif hasattr(selector, 'estimator_') and hasattr(selector.estimator_, 'coef_'):
            # For SelectFromModel with linear models
            coef = selector.estimator_.coef_
            if coef.ndim > 1:
                # For multi-class classification
                coef = np.sum(np.abs(coef), axis=0)
            
            # Get non-zero coefficients
            mask = coef != 0
            return [feature_names[i] for i in range(len(feature_names)) if mask[i]]
        elif hasattr(selector, 'estimator_') and hasattr(selector.estimator_, 'feature_importances_'):
            # For SelectFromModel with tree-based models
            importances = selector.estimator_.feature_importances_
            threshold = selector.threshold_
            
            if isinstance(threshold, str) and threshold == 'median':
                threshold = np.median(importances)
            
            mask = importances > threshold
            return [feature_names[i] for i in range(len(feature_names)) if mask[i]]
        else:
            # Fallback - return all features
            logger.warning("Could not determine selected features, returning all features")
            return feature_names
    
    def _get_feature_importances(self, selector: Any, feature_names: List[str]) -> pd.DataFrame:
        """Get feature importances from a fitted selector."""
        importances = np.zeros(len(feature_names))
        
        if hasattr(selector, 'scores_'):
            # For SelectKBest
            importances = selector.scores_
        elif hasattr(selector, 'estimator_') and hasattr(selector.estimator_, 'coef_'):
            # For SelectFromModel with linear models
            coef = selector.estimator_.coef_
            if coef.ndim > 1:
                # For multi-class classification
                importances = np.sum(np.abs(coef), axis=0)
            else:
                importances = np.abs(coef)
        elif hasattr(selector, 'estimator_') and hasattr(selector.estimator_, 'feature_importances_'):
            # For SelectFromModel with tree-based models
            importances = selector.estimator_.feature_importances_
        
        # Create DataFrame with feature names and importances
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        })
        
        # Set feature as index and sort by importance
        importance_df = importance_df.set_index('feature').sort_values('importance', ascending=False)
        
        return importance_df


# Convenience functions

def select_features(
    X: pd.DataFrame,
    y: pd.Series,
    method: str = 'filter',
    n_features: Union[int, float] = 10,
    model_type: str = 'classification',
    regimes: Optional[pd.Series] = None,
    current_regime: Optional[str] = None
) -> pd.DataFrame:
    """
    Select features from a dataset.
    
    Parameters:
    -----------
    X : pd.DataFrame
        Feature matrix
    y : pd.Series
        Target variable
    method : str
        Method for feature selection ('filter', 'wrapper', 'embedded', 'stability')
    n_features : int or float
        Number of features to select (int) or fraction of features to select (float < 1.0)
    model_type : str
        Type of models ('classification' or 'regression')
    regimes : Optional[pd.Series]
        Market regime labels for regime-specific feature selection
    current_regime : Optional[str]
        Current market regime for regime-specific feature selection
        
    Returns:
    --------
    pd.DataFrame
        Transformed feature matrix with selected features
    """
    selector = FeatureSelector(
        selection_method=method,
        n_features=n_features,
        model_type=model_type,
        regime_aware=(regimes is not None)
    )
    
    return selector.fit_transform(X, y, regimes, current_regime)


def get_feature_importance(
    X: pd.DataFrame,
    y: pd.Series,
    method: str = 'embedded',
    model_type: str = 'classification',
    regimes: Optional[pd.Series] = None,
    regime: Optional[str] = None
) -> pd.DataFrame:
    """
    Get feature importance scores.
    
    Parameters:
    -----------
    X : pd.DataFrame
        Feature matrix
    y : pd.Series
        Target variable
    method : str
        Method for feature selection ('filter', 'wrapper', 'embedded', 'stability')
    model_type : str
        Type of models ('classification' or 'regression')
    regimes : Optional[pd.Series]
        Market regime labels for regime-specific feature selection
    regime : Optional[str]
        Market regime for regime-specific feature importance
        
    Returns:
    --------
    pd.DataFrame
        Feature importance scores
    """
    selector = FeatureSelector(
        selection_method=method,
        n_features=X.shape[1],  # Use all features
        model_type=model_type,
        regime_aware=(regimes is not None)
    )
    
    selector.fit(X, y, regimes)
    return selector.get_feature_importance(regime) 