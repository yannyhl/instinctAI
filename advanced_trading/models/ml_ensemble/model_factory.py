"""
Model Factory
------------
Factory for creating and configuring different ML models for the ensemble.
This module makes it easy to instantiate various types of models with appropriate
hyperparameters for different market prediction tasks.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Tuple
import logging
import os
import joblib
from pathlib import Path

# Import sklearn components conditionally to handle environments without all dependencies
try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
    from sklearn.linear_model import LogisticRegression, Ridge, Lasso
    from sklearn.svm import SVC, SVR
    from sklearn.neural_network import MLPClassifier, MLPRegressor
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    
# Import XGBoost conditionally
try:
    from xgboost import XGBClassifier, XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    
# Import LightGBM conditionally
try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

# Get the logger
logger = logging.getLogger(__name__)

class ModelFactory:
    """
    Factory for creating and configuring ML models for trading strategies.
    
    This class provides methods to create different types of models with
    appropriate hyperparameters for financial time series prediction.
    
    Models are instantiated with sensible defaults for financial data,
    but can be customized with specific hyperparameters.
    
    The factory supports various model types:
    - 'rf': Random Forest
    - 'gbm': Gradient Boosting Machine
    - 'xgb': XGBoost
    - 'lgbm': LightGBM
    - 'svm': Support Vector Machine
    - 'logistic': Logistic Regression
    - 'ridge': Ridge Regression
    - 'lasso': Lasso Regression
    - 'nn': Neural Network
    
    And specialized models for specific market tasks:
    - Trend prediction models
    - Mean reversion models
    - Volatility prediction models
    - Regime detection models
    """
    
    MODELS_DIR = Path(__file__).parent.parent / "storage" / "ml_ensemble"

    def __init__(self):
        """Initialize the model factory."""
        # Create model storage directory if it doesn't exist
        self.MODELS_DIR.mkdir(exist_ok=True, parents=True)
        
        # Check available ML frameworks
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available. Most models will not work.")
        if not XGBOOST_AVAILABLE:
            logger.warning("XGBoost not available. XGBoost models will not work.")
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available. LightGBM models will not work.")
            
    @staticmethod
    def create_model(
        model_type: str,
        prediction_type: str = 'classification',
        hyperparams: Optional[Dict[str, Any]] = None,
        use_pipeline: bool = True,
        feature_preprocessing: Optional[str] = 'standard'
    ) -> Any:
        """
        Create a model of the specified type with appropriate hyperparameters.
        
        Args:
            model_type: Type of model to create ('rf', 'gbm', 'xgb', 'lgbm', 'svm', etc.)
            prediction_type: 'classification' or 'regression'
            hyperparams: Custom hyperparameters to override defaults
            use_pipeline: Whether to wrap the model in a preprocessing pipeline
            feature_preprocessing: Type of preprocessing ('standard', 'minmax', or None)
            
        Returns:
            Instantiated model (or pipeline)
        
        Raises:
            ValueError: If model_type is invalid or required dependency is missing
        """
        if not SKLEARN_AVAILABLE:
            raise ValueError("scikit-learn is required but not available")
            
        # Validate model type
        valid_types = ['rf', 'gbm', 'xgb', 'lgbm', 'svm', 'logistic', 'ridge', 'lasso', 'nn']
        if model_type not in valid_types:
            raise ValueError(f"Invalid model type: {model_type}. Must be one of {valid_types}")
            
        # Handle optional deps
        if model_type == 'xgb' and not XGBOOST_AVAILABLE:
            raise ValueError("XGBoost models requested but XGBoost is not available")
            
        if model_type == 'lgbm' and not LIGHTGBM_AVAILABLE:
            raise ValueError("LightGBM models requested but LightGBM is not available")
        
        # Get default parameters and override with custom ones
        default_params = ModelFactory._get_default_params(model_type, prediction_type)
        
        if hyperparams:
            default_params.update(hyperparams)
            
        # Create the base model
        model = ModelFactory._create_base_model(model_type, prediction_type, default_params)
        
        # Optionally wrap in a pipeline with preprocessing
        if use_pipeline and feature_preprocessing:
            model = ModelFactory._create_pipeline(model, feature_preprocessing)
            
        return model
        
    @staticmethod
    def create_trend_model(
        prediction_type: str = 'classification',
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model specifically tuned for trend prediction.
        
        Trend models are optimized for detecting directional price movements.
        
        Args:
            prediction_type: 'classification' or 'regression'
            hyperparams: Custom hyperparameters to override defaults
            
        Returns:
            Trend prediction model
        """
        # Default to Gradient Boosting for trend prediction
        base_params = {
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'min_samples_split': 10,
            'min_samples_leaf': 5
        }
        
        if prediction_type == 'classification':
            # Add classification-specific parameters
            base_params.update({
                'class_weight': 'balanced_subsample'
            })
        else:
            # Add regression-specific parameters
            base_params.update({
                'alpha': 0.9  # Focus more on recent performance
            })
            
        # Override with custom hyperparameters if provided
        if hyperparams:
            base_params.update(hyperparams)
            
        # Create the model
        return ModelFactory.create_model(
            model_type='gbm',
            prediction_type=prediction_type,
            hyperparams=base_params,
            use_pipeline=True,
            feature_preprocessing='standard'
        )
    
    @staticmethod
    def create_mean_reversion_model(
        prediction_type: str = 'classification',
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model specifically tuned for mean reversion prediction.
        
        Mean reversion models are optimized for detecting when prices
        are likely to revert to a mean or support/resistance level.
        
        Args:
            prediction_type: 'classification' or 'regression'
            hyperparams: Custom hyperparameters to override defaults
            
        Returns:
            Mean reversion prediction model
        """
        # For mean reversion, use Random Forest with parameters tuned
        # for identifying potential reversal points
        base_params = {
            'n_estimators': 150,
            'max_depth': 8,
            'min_samples_split': 15,
            'min_samples_leaf': 8,
            'bootstrap': True,
            'oob_score': True
        }
        
        if prediction_type == 'classification':
            # Add classification-specific parameters
            base_params.update({
                'class_weight': 'balanced',
                'criterion': 'entropy'  # Focus on information gain
            })
        else:
            # Add regression-specific parameters
            base_params.update({
                'criterion': 'squared_error'
            })
            
        # Override with custom hyperparameters if provided
        if hyperparams:
            base_params.update(hyperparams)
            
        # Create the model
        return ModelFactory.create_model(
            model_type='rf',
            prediction_type=prediction_type,
            hyperparams=base_params,
            use_pipeline=True,
            feature_preprocessing='standard'
        )
    
    @staticmethod
    def create_volatility_model(
        prediction_type: str = 'regression',
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model specifically tuned for volatility prediction.
        
        Volatility models are optimized for forecasting price volatility.
        
        Args:
            prediction_type: 'classification' or 'regression' (usually regression)
            hyperparams: Custom hyperparameters to override defaults
            
        Returns:
            Volatility prediction model
        """
        # For volatility prediction, gradient boosting works well
        base_params = {
            'n_estimators': 200,
            'max_depth': 6,
            'learning_rate': 0.03,
            'subsample': 0.7,
            'min_samples_split': 20,
            'min_samples_leaf': 10,
            'alpha': 0.95  # Quantile regression to capture tail events
        }
            
        # Override with custom hyperparameters if provided
        if hyperparams:
            base_params.update(hyperparams)
            
        # Create the model
        return ModelFactory.create_model(
            model_type='gbm',
            prediction_type=prediction_type,
            hyperparams=base_params,
            use_pipeline=True,
            feature_preprocessing='standard'
        )
    
    @staticmethod
    def create_regime_detection_model(
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model specifically tuned for market regime detection.
        
        Regime detection models are optimized for classifying market conditions.
        
        Args:
            hyperparams: Custom hyperparameters to override defaults
            
        Returns:
            Regime detection model
        """
        # For regime detection, random forest works well
        base_params = {
            'n_estimators': 200,
            'max_depth': 10,
            'min_samples_split': 15,
            'min_samples_leaf': 5,
            'bootstrap': True,
            'oob_score': True,
            'class_weight': 'balanced',
            'criterion': 'entropy'
        }
            
        # Override with custom hyperparameters if provided
        if hyperparams:
            base_params.update(hyperparams)
            
        # Create the model
        return ModelFactory.create_model(
            model_type='rf',
            prediction_type='classification',  # Regime detection is classification
            hyperparams=base_params,
            use_pipeline=True,
            feature_preprocessing='standard'
        )
    
    @staticmethod
    def create_quick_ensemble_set(
        prediction_type: str = 'classification',
        include_linear: bool = True,
        include_neural: bool = False
    ) -> Dict[str, Any]:
        """
        Create a set of models for a quick ensemble.
        
        This is useful for rapidly creating a diverse ensemble
        of models with different learning algorithms.
        
        Args:
            prediction_type: 'classification' or 'regression'
            include_linear: Whether to include linear models
            include_neural: Whether to include neural network models
            
        Returns:
            Dictionary of named models
        """
        models = {}
        
        # Always include tree-based models
        models['rf'] = ModelFactory.create_model('rf', prediction_type)
        models['gbm'] = ModelFactory.create_model('gbm', prediction_type)
        
        # Add XGBoost if available
        if XGBOOST_AVAILABLE:
            models['xgb'] = ModelFactory.create_model('xgb', prediction_type)
            
        # Add LightGBM if available
        if LIGHTGBM_AVAILABLE:
            models['lgbm'] = ModelFactory.create_model('lgbm', prediction_type)
            
        # Optionally add linear models
        if include_linear:
            if prediction_type == 'classification':
                models['logistic'] = ModelFactory.create_model('logistic', prediction_type)
            else:
                models['ridge'] = ModelFactory.create_model('ridge', prediction_type)
                models['lasso'] = ModelFactory.create_model('lasso', prediction_type)
                
        # Optionally add neural network
        if include_neural:
            models['nn'] = ModelFactory.create_model('nn', prediction_type)
            
        return models
    
    def save_model(self, model: Any, model_name: str, symbol: str, timeframe: str) -> str:
        """
        Save a trained model to disk.
        
        Args:
            model: Trained model to save
            model_name: Name to identify the model
            symbol: Trading symbol the model is for
            timeframe: Timeframe the model is trained on
            
        Returns:
            Path where the model was saved
        """
        # Create a safe filename
        symbol_safe = symbol.replace('/', '-').replace(' ', '_')
        filename = f"{model_name}_{symbol_safe}_{timeframe}.joblib"
        filepath = self.MODELS_DIR / filename
        
        # Save the model
        try:
            joblib.dump(model, filepath)
            logger.info(f"Model saved to {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            raise
    
    def load_model(self, model_name: str, symbol: str, timeframe: str) -> Any:
        """
        Load a saved model from disk.
        
        Args:
            model_name: Name to identify the model
            symbol: Trading symbol the model is for
            timeframe: Timeframe the model is trained on
            
        Returns:
            Loaded model
            
        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        # Create the filename to load
        symbol_safe = symbol.replace('/', '-').replace(' ', '_')
        filename = f"{model_name}_{symbol_safe}_{timeframe}.joblib"
        filepath = self.MODELS_DIR / filename
        
        # Check if file exists
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        # Load the model
        try:
            model = joblib.load(filepath)
            logger.info(f"Model loaded from {filepath}")
            return model
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def list_models(self, symbol: Optional[str] = None, timeframe: Optional[str] = None) -> List[str]:
        """
        List available saved models.
        
        Args:
            symbol: Optional symbol to filter by
            timeframe: Optional timeframe to filter by
            
        Returns:
            List of model filenames
        """
        # Create model storage directory if it doesn't exist
        self.MODELS_DIR.mkdir(exist_ok=True, parents=True)
        
        # Get all joblib files
        all_models = list(self.MODELS_DIR.glob("*.joblib"))
        
        # Apply filters if specified
        if symbol or timeframe:
            filtered_models = []
            for model_path in all_models:
                model_name = model_path.stem
                
                # Apply symbol filter
                if symbol and symbol.replace('/', '-').replace(' ', '_') not in model_name:
                    continue
                    
                # Apply timeframe filter
                if timeframe and not model_name.endswith(f"_{timeframe}"):
                    continue
                    
                filtered_models.append(model_path.name)
            
            return filtered_models
        else:
            return [model.name for model in all_models]
            
    @staticmethod
    def _create_base_model(
        model_type: str,
        prediction_type: str,
        hyperparams: Dict[str, Any]
    ) -> Any:
        """
        Create a base model of the specified type.
        
        Args:
            model_type: Type of model to create
            prediction_type: 'classification' or 'regression'
            hyperparams: Model hyperparameters
            
        Returns:
            Instantiated model
            
        Raises:
            ValueError: If model type is invalid
        """
        if prediction_type == 'classification':
            if model_type == 'rf':
                return RandomForestClassifier(**hyperparams)
            elif model_type == 'gbm':
                return GradientBoostingClassifier(**hyperparams)
            elif model_type == 'xgb' and XGBOOST_AVAILABLE:
                return XGBClassifier(**hyperparams)
            elif model_type == 'lgbm' and LIGHTGBM_AVAILABLE:
                return LGBMClassifier(**hyperparams)
            elif model_type == 'svm':
                return SVC(**hyperparams)
            elif model_type == 'logistic':
                return LogisticRegression(**hyperparams)
            elif model_type == 'nn':
                return MLPClassifier(**hyperparams)
        else:  # regression
            if model_type == 'rf':
                return RandomForestRegressor(**hyperparams)
            elif model_type == 'gbm':
                return GradientBoostingRegressor(**hyperparams)
            elif model_type == 'xgb' and XGBOOST_AVAILABLE:
                return XGBRegressor(**hyperparams)
            elif model_type == 'lgbm' and LIGHTGBM_AVAILABLE:
                return LGBMRegressor(**hyperparams)
            elif model_type == 'svm':
                return SVR(**hyperparams)
            elif model_type == 'ridge':
                return Ridge(**hyperparams)
            elif model_type == 'lasso':
                return Lasso(**hyperparams)
            elif model_type == 'nn':
                return MLPRegressor(**hyperparams)
                
        raise ValueError(f"Invalid model configuration: {model_type} - {prediction_type}")
    
    @staticmethod
    def _create_pipeline(
        model: Any,
        preprocessing: str
    ) -> Pipeline:
        """
        Create a pipeline with preprocessing and the model.
        
        Args:
            model: Model to include in the pipeline
            preprocessing: Type of preprocessing ('standard', 'minmax', or None)
            
        Returns:
            scikit-learn Pipeline
        """
        steps = []
        
        # Add preprocessing step
        if preprocessing == 'standard':
            steps.append(('scaler', StandardScaler()))
        elif preprocessing == 'minmax':
            steps.append(('scaler', MinMaxScaler()))
            
        # Add model step
        steps.append(('model', model))
        
        return Pipeline(steps)
    
    @staticmethod
    def _get_default_params(
        model_type: str,
        prediction_type: str
    ) -> Dict[str, Any]:
        """
        Get default hyperparameters for a model type.
        
        Args:
            model_type: Type of model
            prediction_type: 'classification' or 'regression'
            
        Returns:
            Dictionary of default hyperparameters
        """
        # Common parameters for all models
        common_params = {}
        
        # Model-specific parameters
        if model_type == 'rf':
            params = {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 10,
                'min_samples_leaf': 5,
                'bootstrap': True,
                'n_jobs': -1
            }
        elif model_type == 'gbm':
            params = {
                'n_estimators': 100,
                'max_depth': 5,
                'learning_rate': 0.1,
                'subsample': 0.8
            }
        elif model_type == 'xgb':
            params = {
                'n_estimators': 100,
                'max_depth': 5,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'n_jobs': -1
            }
        elif model_type == 'lgbm':
            params = {
                'n_estimators': 100,
                'max_depth': 5,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'n_jobs': -1
            }
        elif model_type == 'svm':
            params = {
                'C': 1.0,
                'gamma': 'scale',
                'probability': True
            }
        elif model_type == 'logistic':
            params = {
                'C': 1.0,
                'max_iter': 1000,
                'solver': 'liblinear',
                'n_jobs': -1
            }
        elif model_type == 'ridge':
            params = {
                'alpha': 1.0
            }
        elif model_type == 'lasso':
            params = {
                'alpha': 0.1,
                'max_iter': 1000
            }
        elif model_type == 'nn':
            params = {
                'hidden_layer_sizes': (100, 50),
                'activation': 'relu',
                'solver': 'adam',
                'alpha': 0.0001,
                'max_iter': 1000
            }
        else:
            params = {}
            
        # Add classification/regression specific parameters
        if prediction_type == 'classification':
            if model_type == 'rf':
                params['class_weight'] = 'balanced'
            elif model_type == 'logistic':
                params['class_weight'] = 'balanced'
                
        # Merge with common parameters
        params.update(common_params)
        
        return params 