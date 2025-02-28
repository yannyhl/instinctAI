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
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge, Lasso
from sklearn.svm import SVC, SVR
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier, XGBRegressor
from lightgbm import LGBMClassifier, LGBMRegressor
import logging

# Get the logger
logger = logging.getLogger(__name__)

class ModelFactory:
    """
    Factory for creating and configuring ML models for trading strategies.
    
    This class provides methods to create different types of models with
    appropriate hyperparameters for financial time series prediction.
    
    Models are instantiated with sensible defaults for financial data,
    but can be customized with specific hyperparameters.
    """
    
    @staticmethod
    def create_model(
        model_type: str,
        prediction_type: str = 'classification',
        hyperparams: Optional[Dict[str, Any]] = None,
        use_pipeline: bool = True,
        feature_preprocessing: Optional[str] = 'standard'
    ) -> Any:
        """
        Create a model with specified hyperparameters.
        
        Parameters:
        -----------
        model_type : str
            Type of model to create ('rf', 'gb', 'xgb', 'lgbm', 'linear', 'mlp', 'svm')
        prediction_type : str
            Type of prediction task ('classification' or 'regression')
        hyperparams : Optional[Dict[str, Any]]
            Custom hyperparameters to override defaults
        use_pipeline : bool
            Whether to wrap the model in a scikit-learn pipeline
        feature_preprocessing : Optional[str]
            Type of feature preprocessing ('standard', 'minmax', or None)
            
        Returns:
        --------
        Any
            Instantiated model (or pipeline)
        """
        # Initialize default hyperparams
        if hyperparams is None:
            hyperparams = {}
        
        # Create the model
        model = ModelFactory._create_base_model(model_type, prediction_type, hyperparams)
        
        # Wrap in pipeline if requested
        if use_pipeline and feature_preprocessing is not None:
            return ModelFactory._create_pipeline(model, feature_preprocessing)
        else:
            return model
    
    @staticmethod
    def create_trend_model(
        prediction_type: str = 'classification',
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model optimized for trend prediction.
        
        Parameters:
        -----------
        prediction_type : str
            Type of prediction task ('classification' or 'regression')
        hyperparams : Optional[Dict[str, Any]]
            Custom hyperparameters to override defaults
            
        Returns:
        --------
        Any
            Instantiated model in a pipeline
        """
        # Initialize default hyperparams
        if hyperparams is None:
            hyperparams = {}
        
        # Default hyperparams for trend prediction
        if prediction_type == 'classification':
            default_params = {
                'n_estimators': 200,
                'max_depth': 7,
                'min_samples_leaf': 20,
                'max_features': 'sqrt',
                'class_weight': 'balanced_subsample',
                'random_state': 42
            }
        else:  # regression
            default_params = {
                'n_estimators': 200,
                'max_depth': 9,
                'min_samples_leaf': 15,
                'max_features': 'sqrt',
                'random_state': 42
            }
        
        # Update with custom hyperparams
        for k, v in hyperparams.items():
            default_params[k] = v
        
        # Create gradient boosting model for trend prediction
        return ModelFactory.create_model(
            'gb',
            prediction_type,
            default_params,
            use_pipeline=True,
            feature_preprocessing='standard'
        )
    
    @staticmethod
    def create_mean_reversion_model(
        prediction_type: str = 'classification',
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model optimized for mean-reversion prediction.
        
        Parameters:
        -----------
        prediction_type : str
            Type of prediction task ('classification' or 'regression')
        hyperparams : Optional[Dict[str, Any]]
            Custom hyperparameters to override defaults
            
        Returns:
        --------
        Any
            Instantiated model in a pipeline
        """
        # Initialize default hyperparams
        if hyperparams is None:
            hyperparams = {}
        
        # Default hyperparams for mean-reversion prediction
        if prediction_type == 'classification':
            default_params = {
                'n_estimators': 150,
                'learning_rate': 0.05,
                'max_depth': 5,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'scale_pos_weight': 1.0,
                'random_state': 42
            }
        else:  # regression
            default_params = {
                'n_estimators': 150,
                'learning_rate': 0.03,
                'max_depth': 6,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            }
        
        # Update with custom hyperparams
        for k, v in hyperparams.items():
            default_params[k] = v
        
        # Create XGBoost model for mean-reversion prediction
        return ModelFactory.create_model(
            'xgb',
            prediction_type,
            default_params,
            use_pipeline=True,
            feature_preprocessing='standard'
        )
    
    @staticmethod
    def create_volatility_model(
        prediction_type: str = 'regression',
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model optimized for volatility prediction.
        
        Parameters:
        -----------
        prediction_type : str
            Type of prediction task (usually 'regression' for volatility)
        hyperparams : Optional[Dict[str, Any]]
            Custom hyperparameters to override defaults
            
        Returns:
        --------
        Any
            Instantiated model in a pipeline
        """
        # Initialize default hyperparams
        if hyperparams is None:
            hyperparams = {}
        
        # Default hyperparams for volatility prediction
        default_params = {
            'num_leaves': 31,
            'learning_rate': 0.05,
            'n_estimators': 100,
            'max_depth': -1,
            'min_child_samples': 20,
            'subsample': 0.7,
            'colsample_bytree': 0.7,
            'random_state': 42
        }
        
        # Update with custom hyperparams
        for k, v in hyperparams.items():
            default_params[k] = v
        
        # Create LightGBM model for volatility prediction
        return ModelFactory.create_model(
            'lgbm',
            prediction_type,
            default_params,
            use_pipeline=True,
            feature_preprocessing='standard'
        )
    
    @staticmethod
    def create_regime_detection_model(
        hyperparams: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create a model optimized for market regime detection.
        
        Parameters:
        -----------
        hyperparams : Optional[Dict[str, Any]]
            Custom hyperparameters to override defaults
            
        Returns:
        --------
        Any
            Instantiated model in a pipeline
        """
        # Initialize default hyperparams
        if hyperparams is None:
            hyperparams = {}
        
        # Default hyperparams for regime detection
        default_params = {
            'n_estimators': 200,
            'max_depth': 8,
            'min_samples_split': 20,
            'min_samples_leaf': 10,
            'max_features': 'sqrt',
            'random_state': 42
        }
        
        # Update with custom hyperparams
        for k, v in hyperparams.items():
            default_params[k] = v
        
        # Create Random Forest classifier for regime detection
        return ModelFactory.create_model(
            'rf',
            'classification',
            default_params,
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
        Create a complete set of models for an ensemble.
        
        This method creates a diverse set of models suitable for
        creating a strong ensemble for financial prediction.
        
        Parameters:
        -----------
        prediction_type : str
            Type of prediction task ('classification' or 'regression')
        include_linear : bool
            Whether to include linear models
        include_neural : bool
            Whether to include neural network models
            
        Returns:
        --------
        Dict[str, Any]
            Dictionary of instantiated models with names as keys
        """
        models = {}
        
        # Add tree-based models
        models['random_forest'] = ModelFactory.create_model('rf', prediction_type)
        models['gradient_boost'] = ModelFactory.create_model('gb', prediction_type)
        models['xgboost'] = ModelFactory.create_model('xgb', prediction_type)
        models['lightgbm'] = ModelFactory.create_model('lgbm', prediction_type)
        
        # Add linear models if requested
        if include_linear:
            models['linear'] = ModelFactory.create_model('linear', prediction_type)
        
        # Add neural network if requested
        if include_neural:
            models['neural_net'] = ModelFactory.create_model('mlp', prediction_type)
        
        return models
    
    @staticmethod
    def _create_base_model(
        model_type: str,
        prediction_type: str,
        hyperparams: Dict[str, Any]
    ) -> Any:
        """
        Create a base model of specified type with given hyperparameters.
        
        Parameters:
        -----------
        model_type : str
            Type of model to create
        prediction_type : str
            Type of prediction task
        hyperparams : Dict[str, Any]
            Hyperparameters for the model
            
        Returns:
        --------
        Any
            Instantiated model
        """
        # Combine default hyperparams with custom ones
        model_params = ModelFactory._get_default_params(model_type, prediction_type)
        for k, v in hyperparams.items():
            model_params[k] = v
        
        # Create appropriate model type
        if model_type == 'rf':
            if prediction_type == 'classification':
                return RandomForestClassifier(**model_params)
            else:
                return RandomForestRegressor(**model_params)
        
        elif model_type == 'gb':
            if prediction_type == 'classification':
                return GradientBoostingClassifier(**model_params)
            else:
                return GradientBoostingRegressor(**model_params)
        
        elif model_type == 'xgb':
            if prediction_type == 'classification':
                return XGBClassifier(**model_params)
            else:
                return XGBRegressor(**model_params)
        
        elif model_type == 'lgbm':
            if prediction_type == 'classification':
                return LGBMClassifier(**model_params)
            else:
                return LGBMRegressor(**model_params)
        
        elif model_type == 'linear':
            if prediction_type == 'classification':
                return LogisticRegression(**model_params)
            else:
                # Choose between Ridge and Lasso based on hyperparams
                if model_params.pop('use_lasso', False):
                    return Lasso(**model_params)
                else:
                    return Ridge(**model_params)
        
        elif model_type == 'mlp':
            if prediction_type == 'classification':
                return MLPClassifier(**model_params)
            else:
                return MLPRegressor(**model_params)
        
        elif model_type == 'svm':
            if prediction_type == 'classification':
                return SVC(**model_params)
            else:
                return SVR(**model_params)
        
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    @staticmethod
    def _create_pipeline(
        model: Any,
        preprocessing: str
    ) -> Pipeline:
        """
        Create a scikit-learn pipeline with preprocessing and model.
        
        Parameters:
        -----------
        model : Any
            Model instance
        preprocessing : str
            Type of preprocessing to use
            
        Returns:
        --------
        Pipeline
            Scikit-learn pipeline
        """
        steps = []
        
        # Add preprocessing step
        if preprocessing == 'standard':
            steps.append(('scaler', StandardScaler()))
        elif preprocessing == 'minmax':
            steps.append(('scaler', MinMaxScaler()))
        
        # Add model step
        steps.append(('model', model))
        
        # Return pipeline
        return Pipeline(steps)
    
    @staticmethod
    def _get_default_params(
        model_type: str,
        prediction_type: str
    ) -> Dict[str, Any]:
        """
        Get default hyperparameters for a specific model type.
        
        Parameters:
        -----------
        model_type : str
            Type of model
        prediction_type : str
            Type of prediction task
            
        Returns:
        --------
        Dict[str, Any]
            Default hyperparameters
        """
        # Random Forest defaults
        if model_type == 'rf':
            if prediction_type == 'classification':
                return {
                    'n_estimators': 100,
                    'max_depth': 6,
                    'min_samples_split': 10,
                    'min_samples_leaf': 4,
                    'max_features': 'sqrt',
                    'class_weight': 'balanced',
                    'random_state': 42
                }
            else:
                return {
                    'n_estimators': 100,
                    'max_depth': 8,
                    'min_samples_split': 10,
                    'min_samples_leaf': 4,
                    'max_features': 'sqrt',
                    'random_state': 42
                }
        
        # Gradient Boosting defaults
        elif model_type == 'gb':
            if prediction_type == 'classification':
                return {
                    'n_estimators': 100,
                    'learning_rate': 0.1,
                    'max_depth': 4,
                    'min_samples_split': 10,
                    'min_samples_leaf': 4,
                    'subsample': 0.8,
                    'random_state': 42
                }
            else:
                return {
                    'n_estimators': 100,
                    'learning_rate': 0.1,
                    'max_depth': 4,
                    'min_samples_split': 10,
                    'min_samples_leaf': 4,
                    'subsample': 0.8,
                    'random_state': 42
                }
        
        # XGBoost defaults
        elif model_type == 'xgb':
            if prediction_type == 'classification':
                return {
                    'n_estimators': 100,
                    'learning_rate': 0.1,
                    'max_depth': 4,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'scale_pos_weight': 1.0,
                    'random_state': 42
                }
            else:
                return {
                    'n_estimators': 100,
                    'learning_rate': 0.1,
                    'max_depth': 4,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'random_state': 42
                }
        
        # LightGBM defaults
        elif model_type == 'lgbm':
            if prediction_type == 'classification':
                return {
                    'num_leaves': 31,
                    'learning_rate': 0.1,
                    'n_estimators': 100,
                    'max_depth': -1,
                    'min_child_samples': 20,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'random_state': 42
                }
            else:
                return {
                    'num_leaves': 31,
                    'learning_rate': 0.1,
                    'n_estimators': 100,
                    'max_depth': -1,
                    'min_child_samples': 20,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'random_state': 42
                }
        
        # Linear model defaults
        elif model_type == 'linear':
            if prediction_type == 'classification':
                return {
                    'C': 1.0,
                    'penalty': 'l2',
                    'class_weight': 'balanced',
                    'random_state': 42,
                    'max_iter': 1000
                }
            else:
                return {
                    'alpha': 1.0,
                    'fit_intercept': True,
                    'max_iter': 1000,
                    'tol': 1e-3,
                    'random_state': 42,
                    'use_lasso': False  # Special parameter to choose between Ridge/Lasso
                }
        
        # Neural Network defaults
        elif model_type == 'mlp':
            if prediction_type == 'classification':
                return {
                    'hidden_layer_sizes': (100, 50),
                    'activation': 'relu',
                    'solver': 'adam',
                    'alpha': 0.0001,
                    'batch_size': 'auto',
                    'learning_rate': 'adaptive',
                    'max_iter': 200,
                    'early_stopping': True,
                    'random_state': 42
                }
            else:
                return {
                    'hidden_layer_sizes': (100, 50),
                    'activation': 'relu',
                    'solver': 'adam',
                    'alpha': 0.0001,
                    'batch_size': 'auto',
                    'learning_rate': 'adaptive',
                    'max_iter': 200,
                    'early_stopping': True,
                    'random_state': 42
                }
        
        # SVM defaults
        elif model_type == 'svm':
            if prediction_type == 'classification':
                return {
                    'C': 1.0,
                    'kernel': 'rbf',
                    'gamma': 'scale',
                    'probability': True,
                    'class_weight': 'balanced',
                    'random_state': 42
                }
            else:
                return {
                    'C': 1.0,
                    'kernel': 'rbf',
                    'gamma': 'scale',
                    'epsilon': 0.1
                }
        
        else:
            return {}  # Empty dict for unknown model types 