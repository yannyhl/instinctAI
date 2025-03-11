#!/usr/bin/env python
"""
Unit tests for the cross-validation framework.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import tempfile
import shutil
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

from advanced_trading.utils.cross_validation import (
    TimeSeriesCrossValidator,
    cross_validate_strategy,
    evaluate_predictions,
    feature_importance_cv,
    plot_feature_importance,
    plot_cv_predictions
)

class TestTimeSeriesCrossValidator(unittest.TestCase):
    """Test cases for TimeSeriesCrossValidator class."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample data
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        n_samples = len(dates)
        
        # Create features
        X_data = {
            'feature1': np.random.normal(0, 1, n_samples),
            'feature2': np.random.normal(0, 1, n_samples),
            'feature3': np.random.normal(0, 1, n_samples),
            'regime': np.random.choice(['bull', 'bear', 'sideways'], n_samples)
        }
        
        self.X = pd.DataFrame(X_data, index=dates)
        self.y = pd.Series(np.random.randint(0, 2, n_samples), index=dates)
        
        # Create temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_init_with_valid_parameters(self):
        """Test initialization with valid parameters."""
        cv = TimeSeriesCrossValidator(
            cv_method="purged_kfold",
            n_splits=5,
            gap_size=2,
            embargo_size=1
        )
        
        self.assertEqual(cv.cv_method, "purged_kfold")
        self.assertEqual(cv.n_splits, 5)
        self.assertEqual(cv.gap_size, 2)
        self.assertEqual(cv.embargo_size, 1)
    
    def test_init_with_invalid_method(self):
        """Test initialization with invalid cv_method."""
        with self.assertRaises(ValueError):
            TimeSeriesCrossValidator(cv_method="invalid_method")
    
    def test_init_regime_based_without_column(self):
        """Test initialization of regime-based CV without regime column."""
        with self.assertRaises(ValueError):
            TimeSeriesCrossValidator(cv_method="regime_based")
    
    def test_split_with_non_datetime_index(self):
        """Test split with non-datetime index."""
        cv = TimeSeriesCrossValidator()
        X_invalid = self.X.reset_index()
        
        with self.assertRaises(ValueError):
            cv.split(X_invalid)
    
    def test_purged_kfold_split(self):
        """Test purged k-fold split."""
        cv = TimeSeriesCrossValidator(
            cv_method="purged_kfold",
            n_splits=5,
            gap_size=5,
            embargo_size=2,
            random_state=42
        )
        
        splits = cv.split(self.X)
        
        # Check number of splits
        self.assertEqual(len(splits), 5)
        
        # Check that each split has train and test indices
        for train_idx, test_idx in splits:
            self.assertTrue(len(train_idx) > 0)
            self.assertTrue(len(test_idx) > 0)
            
            # Check that train and test indices don't overlap
            self.assertEqual(len(np.intersect1d(train_idx, test_idx)), 0)
            
            # Check that all indices are within range
            self.assertTrue(np.all(train_idx < len(self.X)))
            self.assertTrue(np.all(test_idx < len(self.X)))
    
    def test_walk_forward_split(self):
        """Test walk-forward split."""
        cv = TimeSeriesCrossValidator(
            cv_method="walk_forward",
            n_splits=3,
            min_train_size=100,
            test_size=50,
            gap_size=5
        )
        
        splits = cv.split(self.X)
        
        # Check that we have the expected number of splits
        self.assertLessEqual(len(splits), 3)
        
        # Check that each split follows the walk-forward pattern
        prev_test_end = 0
        for train_idx, test_idx in splits:
            # Check that train indices come before test indices
            self.assertTrue(np.max(train_idx) < np.min(test_idx))
            
            # Check that test indices are sequential
            self.assertTrue(np.all(np.diff(test_idx) == 1))
            
            # Check that test sets don't overlap
            self.assertTrue(np.min(test_idx) >= prev_test_end)
            prev_test_end = np.max(test_idx) + 1
            
            # Check train size
            self.assertGreaterEqual(len(train_idx), 100)
            
            # Check test size
            self.assertLessEqual(len(test_idx), 50)
            
            # Check gap
            if len(train_idx) > 0 and len(test_idx) > 0:
                self.assertGreaterEqual(np.min(test_idx) - np.max(train_idx), 5)
    
    def test_sliding_window_split(self):
        """Test sliding window split."""
        cv = TimeSeriesCrossValidator(
            cv_method="sliding_window",
            n_splits=3,
            min_train_size=100,
            test_size=50,
            gap_size=5
        )
        
        splits = cv.split(self.X)
        
        # Check that we have the expected number of splits
        self.assertLessEqual(len(splits), 3)
        
        # Check that each split follows the sliding window pattern
        for train_idx, test_idx in splits:
            # Check that train indices come before test indices
            self.assertTrue(np.max(train_idx) < np.min(test_idx))
            
            # Check that test indices are sequential
            self.assertTrue(np.all(np.diff(test_idx) == 1))
            
            # Check train size
            self.assertLessEqual(len(train_idx), 100)
            
            # Check test size
            self.assertLessEqual(len(test_idx), 50)
            
            # Check gap
            if len(train_idx) > 0 and len(test_idx) > 0:
                self.assertGreaterEqual(np.min(test_idx) - np.max(train_idx), 5)
    
    def test_regime_based_split(self):
        """Test regime-based split."""
        cv = TimeSeriesCrossValidator(
            cv_method="regime_based",
            n_splits=3,
            regime_column="regime"
        )
        
        splits = cv.split(self.X)
        
        # Check number of splits
        self.assertEqual(len(splits), 3)
        
        # Check that each regime is represented in both train and test sets
        for train_idx, test_idx in splits:
            train_regimes = set(self.X.iloc[train_idx]['regime'])
            test_regimes = set(self.X.iloc[test_idx]['regime'])
            
            # Check that all regimes are in both train and test
            self.assertEqual(train_regimes, test_regimes)
    
    def test_plot_splits(self):
        """Test plot_splits method."""
        cv = TimeSeriesCrossValidator(
            cv_method="purged_kfold",
            n_splits=3,
            random_state=42
        )
        
        # Test that plot_splits returns a figure
        fig = cv.plot_splits(self.X)
        self.assertIsNotNone(fig)
        
        # Save figure to file
        fig_path = os.path.join(self.test_dir, 'test_plot.png')
        fig.savefig(fig_path)
        
        # Check that file exists
        self.assertTrue(os.path.exists(fig_path))


class TestCrossValidateStrategy(unittest.TestCase):
    """Test cases for cross_validate_strategy function."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample data
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        n_samples = len(dates)
        
        # Create features
        X_data = {
            'feature1': np.random.normal(0, 1, n_samples),
            'feature2': np.random.normal(0, 1, n_samples),
            'feature3': np.random.normal(0, 1, n_samples)
        }
        
        self.X = pd.DataFrame(X_data, index=dates)
        self.y = pd.Series(np.random.randint(0, 2, n_samples), index=dates)
        
        # Create temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_cross_validate_strategy(self):
        """Test cross_validate_strategy function."""
        # Define a simple strategy function
        def simple_strategy(X_train, y_train, **params):
            model = RandomForestClassifier(
                n_estimators=params.get('n_estimators', 10),
                random_state=42
            )
            model.fit(X_train, y_train)
            return model
        
        # Define a simple scoring function
        def simple_scoring(y_true, y_pred):
            return accuracy_score(y_true, y_pred > 0.5)
        
        # Create cross-validator
        cv = TimeSeriesCrossValidator(
            cv_method="purged_kfold",
            n_splits=3,
            random_state=42
        )
        
        # Cross-validate strategy
        results = cross_validate_strategy(
            strategy_fn=simple_strategy,
            X=self.X,
            y=self.y,
            cv=cv,
            strategy_params={'n_estimators': 10},
            scoring_fn=simple_scoring,
            return_models=True,
            return_predictions=True,
            verbose=True,
            save_dir=self.test_dir
        )
        
        # Check results
        self.assertIn('mean_score', results)
        self.assertIn('std_score', results)
        self.assertIn('scores', results)
        self.assertIn('models', results)
        self.assertIn('predictions', results)
        self.assertIn('cv_method', results)
        self.assertIn('n_splits', results)
        self.assertIn('fold_indices', results)
        
        # Check that we have the expected number of scores and models
        self.assertEqual(len(results['scores']), 3)
        self.assertEqual(len(results['models']), 3)
        
        # Check that predictions have the same index as X
        self.assertEqual(len(results['predictions']), len(self.X))
        self.assertTrue(results['predictions'].index.equals(self.X.index))
        
        # Check that files were saved
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'model_fold_1.joblib')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'cv_results.joblib')))
    
    def test_cross_validate_with_integer_cv(self):
        """Test cross_validate_strategy with integer cv parameter."""
        # Define a simple strategy function
        def simple_strategy(X_train, y_train, **params):
            model = RandomForestClassifier(random_state=42)
            model.fit(X_train, y_train)
            return model
        
        # Cross-validate strategy with integer cv
        results = cross_validate_strategy(
            strategy_fn=simple_strategy,
            X=self.X,
            y=self.y,
            cv=3  # Integer instead of TimeSeriesCrossValidator
        )
        
        # Check results
        self.assertIn('cv_method', results)
        self.assertIn('n_splits', results)
        self.assertEqual(results['n_splits'], 3)


class TestEvaluatePredictions(unittest.TestCase):
    """Test cases for evaluate_predictions function."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        n_samples = 100
        
        # Binary classification
        self.y_true_binary = np.random.randint(0, 2, n_samples)
        self.y_pred_binary = np.random.random(n_samples)
        
        # Regression
        self.y_true_reg = np.random.normal(0, 1, n_samples)
        self.y_pred_reg = self.y_true_reg + np.random.normal(0, 0.5, n_samples)
    
    def test_evaluate_binary_classification(self):
        """Test evaluate_predictions for binary classification."""
        results = evaluate_predictions(
            y_true=self.y_true_binary,
            y_pred=self.y_pred_binary,
            threshold=0.5
        )
        
        # Check that we have the expected metrics
        self.assertIn('accuracy', results)
        self.assertIn('precision', results)
        self.assertIn('recall', results)
        self.assertIn('f1', results)
        self.assertIn('roc_auc', results)
    
    def test_evaluate_regression(self):
        """Test evaluate_predictions for regression."""
        results = evaluate_predictions(
            y_true=self.y_true_reg,
            y_pred=self.y_pred_reg
        )
        
        # Check that we have the expected metrics
        self.assertIn('mse', results)
        self.assertIn('rmse', results)
        self.assertIn('mae', results)
        self.assertIn('r2', results)
    
    def test_evaluate_with_custom_metrics(self):
        """Test evaluate_predictions with custom metrics."""
        # Define custom metrics
        custom_metrics = [
            ('custom_metric1', lambda y_t, y_p: np.mean(np.abs(y_t - y_p))),
            ('custom_metric2', lambda y_t, y_p: np.mean((y_t - y_p) ** 2))
        ]
        
        results = evaluate_predictions(
            y_true=self.y_true_reg,
            y_pred=self.y_pred_reg,
            metrics=custom_metrics
        )
        
        # Check that we have the custom metrics
        self.assertIn('custom_metric1', results)
        self.assertIn('custom_metric2', results)


class TestFeatureImportance(unittest.TestCase):
    """Test cases for feature importance functions."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample data
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        n_samples = len(dates)
        
        # Create features
        X_data = {
            'feature1': np.random.normal(0, 1, n_samples),
            'feature2': np.random.normal(0, 1, n_samples),
            'feature3': np.random.normal(0, 1, n_samples),
            'feature4': np.random.normal(0, 1, n_samples),
            'feature5': np.random.normal(0, 1, n_samples)
        }
        
        self.X = pd.DataFrame(X_data, index=dates)
        self.y = pd.Series(np.random.randint(0, 2, n_samples), index=dates)
        
        # Create temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_feature_importance_cv(self):
        """Test feature_importance_cv function."""
        # Define a simple strategy function
        def simple_strategy(X_train, y_train, **params):
            model = RandomForestClassifier(random_state=42)
            model.fit(X_train, y_train)
            return model
        
        # Create cross-validator
        cv = TimeSeriesCrossValidator(
            cv_method="purged_kfold",
            n_splits=2,
            random_state=42
        )
        
        # Calculate feature importance
        importance_df = feature_importance_cv(
            strategy_fn=simple_strategy,
            X=self.X,
            y=self.y,
            cv=cv,
            importance_method="permutation",
            n_repeats=2,
            random_state=42,
            n_jobs=1
        )
        
        # Check results
        self.assertEqual(len(importance_df), len(self.X.columns))
        self.assertIn('mean', importance_df.columns)
        self.assertIn('std', importance_df.columns)
        self.assertEqual(len(importance_df.columns), 4)  # fold_1, fold_2, mean, std
    
    def test_plot_feature_importance(self):
        """Test plot_feature_importance function."""
        # Create sample importance DataFrame
        importance_data = {
            'fold_1': [0.1, 0.2, 0.3, 0.4, 0.5],
            'fold_2': [0.15, 0.25, 0.35, 0.45, 0.55],
            'mean': [0.125, 0.225, 0.325, 0.425, 0.525],
            'std': [0.025, 0.025, 0.025, 0.025, 0.025]
        }
        importance_df = pd.DataFrame(
            importance_data,
            index=['feature1', 'feature2', 'feature3', 'feature4', 'feature5']
        )
        
        # Plot feature importance
        fig = plot_feature_importance(importance_df, top_n=3)
        
        # Check that we got a figure
        self.assertIsNotNone(fig)
        
        # Save figure to file
        fig_path = os.path.join(self.test_dir, 'feature_importance.png')
        fig.savefig(fig_path)
        
        # Check that file exists
        self.assertTrue(os.path.exists(fig_path))


class TestPlotCVPredictions(unittest.TestCase):
    """Test cases for plot_cv_predictions function."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample data
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        n_samples = len(dates)
        
        # Create true values and predictions
        self.y_true = pd.Series(np.random.normal(0, 1, n_samples), index=dates)
        self.y_pred = self.y_true + np.random.normal(0, 0.5, n_samples)
        self.y_pred = pd.Series(self.y_pred, index=dates)
        
        # Create temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_plot_cv_predictions(self):
        """Test plot_cv_predictions function."""
        # Plot CV predictions
        fig = plot_cv_predictions(self.y_true, self.y_pred)
        
        # Check that we got a figure
        self.assertIsNotNone(fig)
        
        # Save figure to file
        fig_path = os.path.join(self.test_dir, 'cv_predictions.png')
        fig.savefig(fig_path)
        
        # Check that file exists
        self.assertTrue(os.path.exists(fig_path))


if __name__ == '__main__':
    unittest.main() 