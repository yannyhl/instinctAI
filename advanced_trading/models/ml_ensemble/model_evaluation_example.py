"""
Model Evaluation Example
-----------------------
This example demonstrates how to use the ModelEvaluator class to evaluate
machine learning models in financial applications.

The example covers:
1. Evaluating classification models with regime awareness
2. Evaluating regression models with regime awareness
3. Visualizing model performance
4. Comparing multiple models
5. Integrating with the EnsembleManager
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import train_test_split
import logging

# Import the ModelEvaluator and EnsembleManager classes
from advanced_trading.models.ml_ensemble.model_evaluation import (
    ModelEvaluator, 
    evaluate_classification_model, 
    evaluate_regression_model
)
from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager
from advanced_trading.models.ml_ensemble.model_factory import ModelFactory

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_example_classification_data():
    """
    Load sample financial classification data for demonstration.
    
    This is a placeholder - in a real scenario, you would load actual market data.
    
    Returns:
    --------
    tuple
        X_train, y_train, X_test, y_test, regimes_train, regimes_test
    """
    # Create synthetic data
    np.random.seed(42)
    n_samples = 1000
    n_features = 20
    
    # Generate features
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f'feature_{i}' for i in range(n_features)]
    )
    
    # Add some informative features
    X['feature_trend'] = np.linspace(-3, 3, n_samples) + np.random.randn(n_samples) * 0.5
    X['feature_cycle'] = np.sin(np.linspace(0, 6*np.pi, n_samples)) + np.random.randn(n_samples) * 0.5
    X['feature_vol'] = np.abs(np.random.randn(n_samples))
    
    # Generate target (binary classification)
    y_trend = (X['feature_trend'] > 0.5).astype(int)
    y_cycle = (X['feature_cycle'] > 0.5).astype(int)
    y_vol = (X['feature_vol'] > 1.0).astype(int)
    
    # Different regimes have different important features
    regimes = pd.Series(np.random.choice(['trend', 'cycle', 'volatility'], size=n_samples, p=[0.4, 0.4, 0.2]))
    
    # Target depends on regime
    y = pd.Series(np.zeros(n_samples))
    y[regimes == 'trend'] = y_trend[regimes == 'trend']
    y[regimes == 'cycle'] = y_cycle[regimes == 'cycle']
    y[regimes == 'volatility'] = y_vol[regimes == 'volatility']
    
    # Split data
    X_train, X_test, y_train, y_test, regimes_train, regimes_test = train_test_split(
        X, y, regimes, test_size=0.3, random_state=42
    )
    
    return X_train, y_train, X_test, y_test, regimes_train, regimes_test

def load_example_regression_data():
    """
    Load sample financial regression data for demonstration.
    
    This is a placeholder - in a real scenario, you would load actual market data.
    
    Returns:
    --------
    tuple
        X_train, y_train, X_test, y_test, regimes_train, regimes_test
    """
    # Create synthetic data
    np.random.seed(42)
    n_samples = 1000
    n_features = 20
    
    # Generate features
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f'feature_{i}' for i in range(n_features)]
    )
    
    # Add some informative features
    X['feature_trend'] = np.linspace(-3, 3, n_samples) + np.random.randn(n_samples) * 0.5
    X['feature_cycle'] = np.sin(np.linspace(0, 6*np.pi, n_samples)) + np.random.randn(n_samples) * 0.5
    X['feature_vol'] = np.abs(np.random.randn(n_samples))
    
    # Generate target (continuous)
    y_trend = X['feature_trend'] * 2 + np.random.randn(n_samples) * 0.5
    y_cycle = X['feature_cycle'] * 3 + np.random.randn(n_samples) * 0.5
    y_vol = X['feature_vol'] * 1.5 + np.random.randn(n_samples) * 0.5
    
    # Different regimes have different important features
    regimes = pd.Series(np.random.choice(['trend', 'cycle', 'volatility'], size=n_samples, p=[0.4, 0.4, 0.2]))
    
    # Target depends on regime
    y = pd.Series(np.zeros(n_samples))
    y[regimes == 'trend'] = y_trend[regimes == 'trend']
    y[regimes == 'cycle'] = y_cycle[regimes == 'cycle']
    y[regimes == 'volatility'] = y_vol[regimes == 'volatility']
    
    # Split data
    X_train, X_test, y_train, y_test, regimes_train, regimes_test = train_test_split(
        X, y, regimes, test_size=0.3, random_state=42
    )
    
    return X_train, y_train, X_test, y_test, regimes_train, regimes_test

def example_classification_evaluation():
    """
    Demonstrate evaluation of classification models.
    """
    logger.info("Loading example classification data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_classification_data()
    
    # Train multiple models
    logger.info("Training classification models...")
    models = {
        'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
        'gradient_boosting': GradientBoostingClassifier(random_state=42),
        'logistic_regression': LogisticRegression(random_state=42)
    }
    
    for name, model in models.items():
        model.fit(X_train, y_train)
    
    # Create model evaluator
    logger.info("Creating model evaluator...")
    evaluator = ModelEvaluator(model_type='classification', regime_aware=True)
    
    # Evaluate each model
    for name, model in models.items():
        logger.info(f"Evaluating {name}...")
        
        # Make predictions
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)
        
        # Evaluate model
        evaluator.evaluate(
            y_true=y_test,
            y_pred=y_pred,
            y_prob=y_prob,
            regimes=regimes_test,
            evaluation_name=name
        )
    
    # Compare models
    logger.info("Comparing models...")
    comparison = evaluator.compare_models(
        model_names=list(models.keys()),
        metric_name='accuracy'
    )
    print("Model Accuracy Comparison:")
    print(comparison)
    
    # Visualize confusion matrix
    logger.info("Visualizing confusion matrix...")
    evaluator.visualize_confusion_matrix(
        evaluation_name='random_forest',
        regime=None  # Global evaluation
    )
    
    # Visualize ROC curve
    logger.info("Visualizing ROC curve...")
    evaluator.visualize_roc_curve(
        y_true=y_test,
        y_prob=models['random_forest'].predict_proba(X_test)
    )
    
    # Visualize precision-recall curve
    logger.info("Visualizing precision-recall curve...")
    evaluator.visualize_precision_recall_curve(
        y_true=y_test,
        y_prob=models['random_forest'].predict_proba(X_test)
    )
    
    # Visualize metric by regime
    logger.info("Visualizing metric by regime...")
    evaluator.visualize_metric_by_regime(
        evaluation_name='random_forest',
        metric_name='accuracy'
    )
    
    # Visualize model comparison
    logger.info("Visualizing model comparison...")
    evaluator.visualize_model_comparison(
        model_names=list(models.keys()),
        metric_names=['accuracy', 'precision', 'recall', 'f1']
    )
    
    return evaluator, models

def example_regression_evaluation():
    """
    Demonstrate evaluation of regression models.
    """
    logger.info("Loading example regression data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_regression_data()
    
    # Train multiple models
    logger.info("Training regression models...")
    models = {
        'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
        'ridge': Ridge(alpha=1.0, random_state=42)
    }
    
    for name, model in models.items():
        model.fit(X_train, y_train)
    
    # Create model evaluator
    logger.info("Creating model evaluator...")
    evaluator = ModelEvaluator(model_type='regression', regime_aware=True)
    
    # Evaluate each model
    for name, model in models.items():
        logger.info(f"Evaluating {name}...")
        
        # Make predictions
        y_pred = model.predict(X_test)
        
        # Evaluate model
        evaluator.evaluate(
            y_true=y_test,
            y_pred=y_pred,
            regimes=regimes_test,
            evaluation_name=name
        )
    
    # Compare models
    logger.info("Comparing models...")
    comparison = evaluator.compare_models(
        model_names=list(models.keys()),
        metric_name='rmse'
    )
    print("Model RMSE Comparison:")
    print(comparison)
    
    # Visualize regression performance
    logger.info("Visualizing regression performance...")
    evaluator.visualize_regression_performance(
        y_true=y_test,
        y_pred=models['random_forest'].predict(X_test)
    )
    
    # Visualize metric by regime
    logger.info("Visualizing metric by regime...")
    evaluator.visualize_metric_by_regime(
        evaluation_name='random_forest',
        metric_name='rmse'
    )
    
    # Visualize model comparison
    logger.info("Visualizing model comparison...")
    evaluator.visualize_model_comparison(
        model_names=list(models.keys()),
        metric_names=['rmse', 'mae', 'r2']
    )
    
    return evaluator, models

def example_ensemble_evaluation():
    """
    Demonstrate evaluation of ensemble models.
    """
    logger.info("Loading example classification data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_classification_data()
    
    # Create base models using ModelFactory
    logger.info("Creating base models...")
    model_factory = ModelFactory()
    base_models = model_factory.create_quick_ensemble_set(prediction_type='classification')
    
    # Create ensemble manager
    logger.info("Creating ensemble manager...")
    ensemble = EnsembleManager(
        base_models=base_models,
        ensemble_method='weighted_avg',
        model_type='classification',
        regime_aware=True,
        feature_names=X_train.columns.tolist()
    )
    
    # Train ensemble
    logger.info("Training ensemble...")
    ensemble.fit(X_train, y_train, regimes=regimes_train)
    
    # Make predictions
    logger.info("Making predictions...")
    y_pred = ensemble.predict(X_test, current_regime=None)  # Global prediction
    y_prob = ensemble.predict_proba(X_test, current_regime=None)
    
    # Evaluate ensemble
    logger.info("Evaluating ensemble...")
    evaluator = ModelEvaluator(model_type='classification', regime_aware=True)
    
    evaluator.evaluate(
        y_true=y_test,
        y_pred=y_pred,
        y_prob=y_prob,
        regimes=regimes_test,
        evaluation_name='ensemble'
    )
    
    # Make regime-specific predictions
    logger.info("Making regime-specific predictions...")
    regime_predictions = {}
    
    for regime in regimes_test.unique():
        # Get data for this regime
        regime_mask = (regimes_test == regime)
        X_regime = X_test[regime_mask]
        y_regime = y_test[regime_mask]
        
        # Make predictions
        y_pred_regime = ensemble.predict(X_regime, current_regime=regime)
        y_prob_regime = ensemble.predict_proba(X_regime, current_regime=regime)
        
        # Evaluate
        evaluator.evaluate(
            y_true=y_regime,
            y_pred=y_pred_regime,
            y_prob=y_prob_regime,
            evaluation_name=f'ensemble_{regime}'
        )
        
        regime_predictions[regime] = (y_pred_regime, y_prob_regime)
    
    # Compare regime-specific performance
    logger.info("Comparing regime-specific performance...")
    regime_models = [f'ensemble_{regime}' for regime in regimes_test.unique()]
    
    comparison = evaluator.compare_models(
        model_names=['ensemble'] + regime_models,
        metric_name='accuracy'
    )
    print("Ensemble Accuracy Comparison:")
    print(comparison)
    
    # Visualize model comparison
    logger.info("Visualizing model comparison...")
    evaluator.visualize_model_comparison(
        model_names=['ensemble'] + regime_models,
        metric_names=['accuracy', 'precision', 'recall', 'f1']
    )
    
    return evaluator, ensemble, regime_predictions

def example_convenience_functions():
    """
    Demonstrate convenience functions.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_classification_data()
    
    # Train a model
    logger.info("Training a model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)
    
    # Use convenience function for classification
    logger.info("Using evaluate_classification_model convenience function...")
    classification_results = evaluate_classification_model(
        y_true=y_test,
        y_pred=y_pred,
        y_prob=y_prob,
        regimes=regimes_test
    )
    
    print("Classification Results:")
    print(f"Accuracy: {classification_results['metrics']['global']['accuracy']:.4f}")
    print(f"Precision: {classification_results['metrics']['global']['precision']:.4f}")
    print(f"Recall: {classification_results['metrics']['global']['recall']:.4f}")
    print(f"F1: {classification_results['metrics']['global']['f1']:.4f}")
    
    # Load regression data
    X_train_reg, y_train_reg, X_test_reg, y_test_reg, regimes_train_reg, regimes_test_reg = load_example_regression_data()
    
    # Train a regression model
    logger.info("Training a regression model...")
    reg_model = Ridge(alpha=1.0, random_state=42)
    reg_model.fit(X_train_reg, y_train_reg)
    
    # Make predictions
    y_pred_reg = reg_model.predict(X_test_reg)
    
    # Use convenience function for regression
    logger.info("Using evaluate_regression_model convenience function...")
    regression_results = evaluate_regression_model(
        y_true=y_test_reg,
        y_pred=y_pred_reg,
        regimes=regimes_test_reg
    )
    
    print("Regression Results:")
    print(f"RMSE: {regression_results['metrics']['global']['rmse']:.4f}")
    print(f"MAE: {regression_results['metrics']['global']['mae']:.4f}")
    print(f"R²: {regression_results['metrics']['global']['r2']:.4f}")
    print(f"Direction Accuracy: {regression_results['metrics']['global']['direction_accuracy']:.4f}")
    
    return classification_results, regression_results

def main():
    """
    Run the model evaluation examples.
    """
    logger.info("Starting model evaluation examples...")
    
    # Example 1: Classification Evaluation
    logger.info("\n\n=== Example 1: Classification Evaluation ===")
    classification_evaluator, classification_models = example_classification_evaluation()
    
    # Example 2: Regression Evaluation
    logger.info("\n\n=== Example 2: Regression Evaluation ===")
    regression_evaluator, regression_models = example_regression_evaluation()
    
    # Example 3: Ensemble Evaluation
    logger.info("\n\n=== Example 3: Ensemble Evaluation ===")
    ensemble_evaluator, ensemble, regime_predictions = example_ensemble_evaluation()
    
    # Example 4: Convenience Functions
    logger.info("\n\n=== Example 4: Convenience Functions ===")
    classification_results, regression_results = example_convenience_functions()
    
    logger.info("Model evaluation examples completed")

if __name__ == "__main__":
    main() 