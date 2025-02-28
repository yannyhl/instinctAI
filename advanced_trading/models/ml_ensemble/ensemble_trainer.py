"""
Ensemble Trainer
---------------
Main entry point for training and evaluating machine learning ensembles.
This module handles dataset preparation, cross-validation, and model evaluation
for the ML ensemble framework.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import joblib
import logging
import os
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    mean_squared_error, mean_absolute_error, r2_score
)

# Import internal modules
from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager
from advanced_trading.models.ml_ensemble.model_factory import ModelFactory
from advanced_trading.models.ml_ensemble.feature_engineering import FeatureEngineer
from advanced_trading.utils.bayesian_changepoint import detect_market_regimes

# Get the logger
logger = logging.getLogger(__name__)

class EnsembleTrainer:
    """
    Main class for training and evaluating ML ensembles.
    
    This class handles:
    - Dataset preparation and splitting
    - Feature engineering
    - Model training and evaluation
    - Ensemble creation and optimization
    - Performance evaluation and visualization
    - Model persistence
    
    Parameters:
    -----------
    data_dir : str
        Directory containing market data
    output_dir : str
        Directory for saving models and results
    prediction_type : str
        Type of prediction task ('classification' or 'regression')
    target_horizon : int
        Forecast horizon (in periods)
    cv_folds : int
        Number of folds for time series cross-validation
    feature_engineer : Optional[FeatureEngineer]
        Pre-configured feature engineer (or None to create a new one)
    ensemble_method : str
        Method for ensembling ('voting', 'stacking', 'weighted_avg')
    regime_aware : bool
        Whether to train regime-specific models
    random_state : int
        Random state for reproducibility
    """
    
    def __init__(
        self,
        data_dir: str,
        output_dir: str,
        prediction_type: str = 'classification',
        target_horizon: int = 5,
        cv_folds: int = 5,
        feature_engineer: Optional[FeatureEngineer] = None,
        ensemble_method: str = 'weighted_avg',
        regime_aware: bool = True,
        random_state: int = 42
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.prediction_type = prediction_type
        self.target_horizon = target_horizon
        self.cv_folds = cv_folds
        self.ensemble_method = ensemble_method
        self.regime_aware = regime_aware
        self.random_state = random_state
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize feature engineer if not provided
        if feature_engineer is None:
            self.feature_engineer = FeatureEngineer(
                handle_missing='fill',
                scaling='standard',
                feature_selection=None,
                random_state=random_state
            )
        else:
            self.feature_engineer = feature_engineer
        
        # Placeholder for trained ensemble
        self.ensemble = None
        
        # Performance metrics
        self.performance_metrics = {}
        
        # Cross-validation splits
        self.cv_splits = []
    
    def prepare_data(
        self, 
        data_file: Union[str, Path], 
        symbol: str = 'BTC',
        timeframe: str = '1d',
        target_method: str = 'binary_direction',
        threshold: float = 0.0,
        drop_na: bool = True
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Load and prepare data for training.
        
        Parameters:
        -----------
        data_file : Union[str, Path]
            Path to data file
        symbol : str
            Trading symbol
        timeframe : str
            Data timeframe
        target_method : str
            Method to create target ('binary_direction', 'multi_direction', 'regression_return')
        threshold : float
            Threshold for significant movement (used in 'binary_direction')
        drop_na : bool
            Whether to drop rows with NaN values
            
        Returns:
        --------
        Tuple[pd.DataFrame, pd.Series]
            Features and target variable
        """
        # Determine file path
        if not isinstance(data_file, (str, Path)):
            raise ValueError("data_file must be a string or Path object")
        
        if isinstance(data_file, str):
            if os.path.isabs(data_file):
                file_path = Path(data_file)
            else:
                file_path = self.data_dir / data_file
        else:
            file_path = data_file
        
        # Load data
        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")
        
        # Determine file type and load accordingly
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        elif file_path.suffix.lower() in ['.parquet', '.pq']:
            df = pd.read_parquet(file_path)
        elif file_path.suffix.lower() in ['.pickle', '.pkl']:
            df = pd.read_pickle(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Ensure OHLCV columns exist (standardize column names if needed)
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        column_mapping = {}
        
        for col in required_cols:
            # Try different common naming conventions
            candidates = [
                col,
                col.upper(),
                col.capitalize(),
                f"{symbol}_{col}",
                f"{symbol}_{col.upper()}",
                f"{symbol.lower()}_{col}"
            ]
            
            found = False
            for candidate in candidates:
                if candidate in df.columns:
                    column_mapping[candidate] = col
                    found = True
                    break
            
            if not found:
                raise ValueError(f"Could not find {col} column in data")
        
        # Rename columns if needed
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Create target variable
        target = self.feature_engineer.create_target_variable(
            df,
            method=target_method,
            horizon=self.target_horizon,
            threshold=threshold
        )
        
        # Create features
        features = self.feature_engineer.create_features(df)
        
        # Drop rows with NaN if requested
        if drop_na:
            # Combine features and target to align indices
            combined = pd.concat([features, target], axis=1)
            combined = combined.dropna()
            
            # Split back into features and target
            features = combined.iloc[:, :-1]
            target = combined.iloc[:, -1]
        
        return features, target
    
    def detect_regimes(
        self, 
        prices: pd.Series, 
        n_regimes: int = 3,
        change_prob_threshold: float = 0.3
    ) -> pd.Series:
        """
        Detect market regimes in the data.
        
        Parameters:
        -----------
        prices : pd.Series
            Price series
        n_regimes : int
            Number of regimes to detect
        change_prob_threshold : float
            Probability threshold for regime change detection
            
        Returns:
        --------
        pd.Series
            Series with regime labels
        """
        # Use the util function to detect regimes
        regimes = detect_market_regimes(
            prices, 
            n_regimes=n_regimes,
            threshold=change_prob_threshold
        )
        
        return regimes
    
    def train_ensemble(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        regimes: Optional[pd.Series] = None,
        model_types: Optional[List[str]] = None,
        include_linear: bool = True,
        include_neural: bool = False,
        meta_model_type: Optional[str] = None,
        use_predefined_models: bool = True
    ) -> EnsembleManager:
        """
        Train an ensemble of models.
        
        Parameters:
        -----------
        features : pd.DataFrame
            Feature dataframe
        target : pd.Series
            Target variable
        regimes : Optional[pd.Series]
            Market regime labels (used if regime_aware=True)
        model_types : Optional[List[str]]
            List of model types to include (e.g., ['rf', 'gb', 'xgb'])
        include_linear : bool
            Whether to include linear models
        include_neural : bool
            Whether to include neural network models
        meta_model_type : Optional[str]
            Type of meta model for stacking (None for default)
        use_predefined_models : bool
            Whether to use predefined models for specific market patterns
            
        Returns:
        --------
        EnsembleManager
            Trained ensemble manager
        """
        # Create base models
        if use_predefined_models:
            base_models = self._create_predefined_models()
        else:
            if model_types is None:
                model_types = ['rf', 'gb', 'xgb', 'lgbm']
            
            base_models = {}
            for model_type in model_types:
                model = ModelFactory.create_model(
                    model_type,
                    prediction_type=self.prediction_type
                )
                base_models[f"{model_type}_model"] = model
            
            # Add linear models if requested
            if include_linear:
                linear_model = ModelFactory.create_model(
                    'linear',
                    prediction_type=self.prediction_type
                )
                base_models['linear_model'] = linear_model
            
            # Add neural network if requested
            if include_neural:
                nn_model = ModelFactory.create_model(
                    'mlp',
                    prediction_type=self.prediction_type
                )
                base_models['neural_net'] = nn_model
        
        # Create meta model for stacking if needed
        meta_model = None
        if self.ensemble_method == 'stacking':
            if meta_model_type is None:
                meta_model_type = 'lgbm'
            
            meta_model = ModelFactory.create_model(
                meta_model_type,
                prediction_type=self.prediction_type
            )
        
        # Create and train the ensemble
        self.ensemble = EnsembleManager(
            base_models=base_models,
            ensemble_method=self.ensemble_method,
            model_type=self.prediction_type,
            regime_aware=self.regime_aware,
            feature_names=list(features.columns),
            meta_model=meta_model
        )
        
        # Fit the ensemble
        self.ensemble.fit(features, target, regimes)
        
        return self.ensemble
    
    def evaluate_ensemble(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        regimes: Optional[pd.Series] = None,
        evaluation_type: str = 'time_series_cv',
        test_size: float = 0.3
    ) -> Dict[str, Any]:
        """
        Evaluate the trained ensemble.
        
        Parameters:
        -----------
        features : pd.DataFrame
            Feature dataframe
        target : pd.Series
            Target variable
        regimes : Optional[pd.Series]
            Market regime labels
        evaluation_type : str
            Type of evaluation ('time_series_cv', 'train_test_split', 'full')
        test_size : float
            Size of test set for train_test_split
            
        Returns:
        --------
        Dict[str, Any]
            Evaluation metrics
        """
        if self.ensemble is None:
            raise ValueError("No trained ensemble found. Call train_ensemble first.")
        
        # Perform evaluation based on specified method
        if evaluation_type == 'time_series_cv':
            return self._evaluate_with_timeseries_cv(features, target, regimes)
        elif evaluation_type == 'train_test_split':
            return self._evaluate_with_train_test_split(features, target, regimes, test_size)
        elif evaluation_type == 'full':
            return self._evaluate_on_full_dataset(features, target, regimes)
        else:
            raise ValueError(f"Unknown evaluation type: {evaluation_type}")
    
    def save_ensemble(self, filename: str) -> None:
        """
        Save the trained ensemble to disk.
        
        Parameters:
        -----------
        filename : str
            Filename to save the ensemble to
        """
        if self.ensemble is None:
            raise ValueError("No trained ensemble to save. Call train_ensemble first.")
        
        # Save to the output directory
        file_path = self.output_dir / filename
        self.ensemble.save(file_path)
        
        # Save performance metrics if available
        if self.performance_metrics:
            metrics_path = self.output_dir / f"{Path(filename).stem}_metrics.joblib"
            joblib.dump(self.performance_metrics, metrics_path)
            logger.info(f"Performance metrics saved to {metrics_path}")
        
        logger.info(f"Ensemble saved to {file_path}")
    
    def load_ensemble(self, filename: str) -> EnsembleManager:
        """
        Load a trained ensemble from disk.
        
        Parameters:
        -----------
        filename : str
            Filename to load the ensemble from
            
        Returns:
        --------
        EnsembleManager
            Loaded ensemble manager
        """
        # Load from the output directory
        file_path = self.output_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Ensemble file not found: {file_path}")
        
        self.ensemble = EnsembleManager.load(file_path)
        
        # Try to load performance metrics if available
        metrics_path = self.output_dir / f"{Path(filename).stem}_metrics.joblib"
        if metrics_path.exists():
            self.performance_metrics = joblib.load(metrics_path)
            logger.info(f"Performance metrics loaded from {metrics_path}")
        
        logger.info(f"Ensemble loaded from {file_path}")
        return self.ensemble
    
    def visualize_performance(
        self,
        by_regime: bool = True,
        show_feature_importance: bool = True,
        top_n_features: int = 20
    ) -> None:
        """
        Visualize ensemble performance.
        
        Parameters:
        -----------
        by_regime : bool
            Whether to show performance by regime
        show_feature_importance : bool
            Whether to show feature importance
        top_n_features : int
            Number of top features to show
        """
        if not self.performance_metrics:
            raise ValueError("No performance metrics available. Evaluate the ensemble first.")
        
        if self.ensemble is None:
            raise ValueError("No trained ensemble available.")
        
        # Create a figure with multiple subplots
        fig = plt.figure(figsize=(15, 12))
        
        # 1. Overall performance metrics
        plt.subplot(2, 2, 1)
        self._plot_overall_metrics()
        
        # 2. Model weights
        plt.subplot(2, 2, 2)
        self.ensemble.visualize_model_weights()
        
        # 3. Feature importance
        if show_feature_importance:
            plt.subplot(2, 2, 3)
            self.ensemble.visualize_feature_importance(top_n=top_n_features)
        
        # 4. Performance by regime
        if by_regime and 'regime_performance' in self.performance_metrics:
            plt.subplot(2, 2, 4)
            self._plot_regime_performance()
        
        plt.tight_layout()
        plt.show()
    
    def _create_predefined_models(self) -> Dict[str, Any]:
        """Create predefined models for different market patterns"""
        models = {}
        
        # Trend model
        models['trend_model'] = ModelFactory.create_trend_model(
            prediction_type=self.prediction_type
        )
        
        # Mean reversion model
        models['mean_reversion_model'] = ModelFactory.create_mean_reversion_model(
            prediction_type=self.prediction_type
        )
        
        # Volatility model (for regression)
        if self.prediction_type == 'regression':
            models['volatility_model'] = ModelFactory.create_volatility_model()
        
        # Regime detection model (for classification)
        if self.prediction_type == 'classification':
            models['regime_model'] = ModelFactory.create_regime_detection_model()
        
        # Generic high-quality models
        models['xgboost_model'] = ModelFactory.create_model(
            'xgb',
            prediction_type=self.prediction_type,
            hyperparams={'n_estimators': 200}
        )
        
        models['random_forest_model'] = ModelFactory.create_model(
            'rf',
            prediction_type=self.prediction_type,
            hyperparams={'n_estimators': 200}
        )
        
        return models
    
    def _evaluate_with_timeseries_cv(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        regimes: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """Evaluate with time series cross-validation"""
        # Create TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=self.cv_folds)
        
        # Metrics for each fold
        fold_metrics = []
        
        # Store CV splits for later use
        self.cv_splits = []
        
        # For tracking predictions
        all_predictions = []
        all_targets = []
        all_regimes = []
        
        for i, (train_idx, test_idx) in enumerate(tscv.split(features)):
            # Get train/test data
            X_train, X_test = features.iloc[train_idx], features.iloc[test_idx]
            y_train, y_test = target.iloc[train_idx], target.iloc[test_idx]
            
            # Get regimes for this split if available
            train_regimes = None
            test_regimes = None
            if regimes is not None:
                train_regimes = regimes.iloc[train_idx]
                test_regimes = regimes.iloc[test_idx]
                all_regimes.extend(test_regimes.tolist())
            
            # Store split for later use
            self.cv_splits.append((train_idx, test_idx))
            
            # Train on this fold
            if i == 0:  # Only fit the ensemble on the first fold
                self.ensemble.fit(X_train, y_train, train_regimes)
            
            # Predict on test set
            pred = self.ensemble.predict(X_test, test_regimes.iloc[-1] if test_regimes is not None else None)
            
            # Store predictions and targets
            all_predictions.extend(pred.tolist())
            all_targets.extend(y_test.tolist())
            
            # Calculate metrics for this fold
            fold_metric = self._calculate_metrics(y_test, pred)
            fold_metric['fold'] = i
            fold_metrics.append(fold_metric)
        
        # Calculate overall metrics
        all_predictions = np.array(all_predictions)
        all_targets = np.array(all_targets)
        
        overall_metrics = self._calculate_metrics(all_targets, all_predictions)
        
        # Calculate metrics by regime if regimes are provided
        regime_metrics = {}
        if regimes is not None:
            all_regimes = np.array(all_regimes)
            unique_regimes = np.unique(all_regimes)
            
            for regime in unique_regimes:
                regime_mask = (all_regimes == regime)
                if np.sum(regime_mask) > 0:
                    regime_pred = all_predictions[regime_mask]
                    regime_true = all_targets[regime_mask]
                    regime_metrics[str(regime)] = self._calculate_metrics(regime_true, regime_pred)
        
        # Store and return results
        self.performance_metrics = {
            'overall': overall_metrics,
            'fold_metrics': fold_metrics,
            'regime_performance': regime_metrics
        }
        
        return self.performance_metrics
    
    def _evaluate_with_train_test_split(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        regimes: Optional[pd.Series] = None,
        test_size: float = 0.3
    ) -> Dict[str, Any]:
        """Evaluate with train/test split"""
        # Calculate split point
        split_idx = int(len(features) * (1 - test_size))
        
        # Split data
        X_train, X_test = features.iloc[:split_idx], features.iloc[split_idx:]
        y_train, y_test = target.iloc[:split_idx], target.iloc[split_idx:]
        
        # Split regimes if available
        train_regimes = None
        test_regimes = None
        if regimes is not None:
            train_regimes = regimes.iloc[:split_idx]
            test_regimes = regimes.iloc[split_idx:]
        
        # Store split for later use
        self.cv_splits = [(np.arange(split_idx), np.arange(split_idx, len(features)))]
        
        # Train on training set
        self.ensemble.fit(X_train, y_train, train_regimes)
        
        # Predict on test set
        test_pred = self.ensemble.predict(X_test, test_regimes.iloc[-1] if test_regimes is not None else None)
        
        # Calculate metrics
        test_metrics = self._calculate_metrics(y_test, test_pred)
        
        # Calculate metrics by regime if regimes are provided
        regime_metrics = {}
        if regimes is not None:
            unique_regimes = np.unique(test_regimes)
            
            for regime in unique_regimes:
                regime_mask = (test_regimes == regime)
                if np.sum(regime_mask) > 0:
                    regime_pred = test_pred[regime_mask]
                    regime_true = y_test.iloc[regime_mask]
                    regime_metrics[str(regime)] = self._calculate_metrics(regime_true, regime_pred)
        
        # Store and return results
        self.performance_metrics = {
            'overall': test_metrics,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'regime_performance': regime_metrics
        }
        
        return self.performance_metrics
    
    def _evaluate_on_full_dataset(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        regimes: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """Evaluate on full dataset (generally not recommended due to overfitting risk)"""
        # We already fitted the model in train_ensemble, so just predict
        predictions = self.ensemble.predict(features)
        
        # Calculate metrics
        metrics = self._calculate_metrics(target, predictions)
        
        # Calculate metrics by regime if regimes are provided
        regime_metrics = {}
        if regimes is not None:
            unique_regimes = np.unique(regimes)
            
            for regime in unique_regimes:
                regime_mask = (regimes == regime)
                if np.sum(regime_mask) > 0:
                    regime_pred = predictions[regime_mask]
                    regime_true = target.iloc[regime_mask]
                    regime_metrics[str(regime)] = self._calculate_metrics(regime_true, regime_pred)
        
        # Store and return results
        self.performance_metrics = {
            'overall': metrics,
            'in_sample': True,  # Flag this as in-sample evaluation
            'regime_performance': regime_metrics
        }
        
        return self.performance_metrics
    
    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, float]:
        """Calculate performance metrics based on prediction type"""
        metrics = {}
        
        if self.prediction_type == 'classification':
            # Convert probabilities to class labels for metrics
            if len(np.unique(y_true)) <= 2:  # Binary classification
                y_pred_class = (y_pred > 0.5).astype(int)
                
                metrics['accuracy'] = accuracy_score(y_true, y_pred_class)
                metrics['precision'] = precision_score(y_true, y_pred_class, zero_division=0)
                metrics['recall'] = recall_score(y_true, y_pred_class, zero_division=0)
                metrics['f1'] = f1_score(y_true, y_pred_class, zero_division=0)
            else:  # Multi-class classification
                y_pred_class = np.argmax(y_pred, axis=1) if y_pred.ndim > 1 else y_pred.astype(int)
                
                metrics['accuracy'] = accuracy_score(y_true, y_pred_class)
                metrics['precision'] = precision_score(y_true, y_pred_class, average='weighted', zero_division=0)
                metrics['recall'] = recall_score(y_true, y_pred_class, average='weighted', zero_division=0)
                metrics['f1'] = f1_score(y_true, y_pred_class, average='weighted', zero_division=0)
        else:  # Regression
            metrics['mse'] = mean_squared_error(y_true, y_pred)
            metrics['rmse'] = np.sqrt(metrics['mse'])
            metrics['mae'] = mean_absolute_error(y_true, y_pred)
            metrics['r2'] = r2_score(y_true, y_pred)
        
        return metrics
    
    def _plot_overall_metrics(self) -> None:
        """Plot overall performance metrics"""
        if 'overall' not in self.performance_metrics:
            logger.warning("No overall metrics available")
            return
        
        metrics = self.performance_metrics['overall']
        
        # Bar plot of metrics
        plt.bar(range(len(metrics)), list(metrics.values()), align='center')
        plt.xticks(range(len(metrics)), list(metrics.keys()), rotation=45)
        plt.ylim(0, 1)
        plt.title('Overall Performance Metrics')
        plt.tight_layout()
    
    def _plot_regime_performance(self) -> None:
        """Plot performance by regime"""
        if 'regime_performance' not in self.performance_metrics:
            logger.warning("No regime-specific metrics available")
            return
        
        regime_metrics = self.performance_metrics['regime_performance']
        if not regime_metrics:
            logger.warning("No regime-specific metrics available")
            return
        
        # Create a DataFrame for easier plotting
        metrics_df = pd.DataFrame(regime_metrics).T
        
        # Bar plot for key metrics by regime
        if self.prediction_type == 'classification':
            key_metrics = ['accuracy', 'precision', 'recall', 'f1']
        else:  # Regression
            key_metrics = ['rmse', 'mae', 'r2']
        
        # Filter to metrics that exist in the data
        plot_metrics = [m for m in key_metrics if m in metrics_df.columns]
        
        if not plot_metrics:
            logger.warning("No matching metrics for plotting")
            return
        
        metrics_df[plot_metrics].plot(kind='bar', figsize=(10, 6))
        plt.title('Performance by Market Regime')
        plt.xlabel('Regime')
        plt.ylabel('Metric Value')
        plt.legend(title='Metric')
        plt.tight_layout() 