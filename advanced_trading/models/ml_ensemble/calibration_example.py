"""
Model Calibration Example
------------------------
This example demonstrates how to use the ModelCalibrator class to calibrate
machine learning models in financial applications.

The example covers:
1. Calibrating binary classification models
2. Regime-specific calibration
3. Visualizing calibration curves
4. Comparing different calibration methods
5. Using convenience functions for quick calibration
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import logging

# Import the ModelCalibrator class and convenience functions
from advanced_trading.models.ml_ensemble.calibration import (
    ModelCalibrator,
    calibrate_probabilities,
    evaluate_calibration
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_example_data():
    """
    Load sample financial data for demonstration.
    
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

def example_basic_calibration():
    """
    Demonstrate basic model calibration.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a model
    logger.info("Training a model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions
    y_prob_train = model.predict_proba(X_train)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    
    # Create calibrator
    logger.info("Creating calibrator...")
    calibrator = ModelCalibrator(method='platt', regime_aware=False)
    
    # Fit calibrator
    logger.info("Fitting calibrator...")
    calibrator.fit(y_train, y_prob_train)
    
    # Calibrate probabilities
    logger.info("Calibrating probabilities...")
    y_prob_calibrated = calibrator.calibrate(y_prob_test)
    
    # Evaluate calibration
    logger.info("Evaluating calibration...")
    calibrator.visualize_calibration_curve(
        y_true=y_test,
        y_prob=y_prob_test,
        y_prob_calibrated=y_prob_calibrated,
        title='Random Forest Calibration'
    )
    
    # Visualize reliability diagram
    logger.info("Visualizing reliability diagram...")
    calibrator.visualize_reliability_diagram(
        y_true=y_test,
        y_prob=y_prob_test,
        y_prob_calibrated=y_prob_calibrated,
        title='Random Forest Reliability Diagram'
    )
    
    return calibrator, y_prob_test, y_prob_calibrated

def example_regime_specific_calibration():
    """
    Demonstrate regime-specific calibration.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a model
    logger.info("Training a model...")
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions
    y_prob_train = model.predict_proba(X_train)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    
    # Create calibrator with regime awareness
    logger.info("Creating regime-aware calibrator...")
    calibrator = ModelCalibrator(method='isotonic', regime_aware=True)
    
    # Fit calibrator with regimes
    logger.info("Fitting regime-aware calibrator...")
    calibrator.fit(y_train, y_prob_train, regimes=regimes_train)
    
    # Calibrate probabilities for each regime
    logger.info("Calibrating probabilities for each regime...")
    unique_regimes = np.unique(regimes_test)
    
    for regime in unique_regimes:
        # Get data for this regime
        regime_mask = (regimes_test == regime)
        regime_y_test = y_test[regime_mask]
        regime_y_prob = y_prob_test[regime_mask]
        
        # Calibrate probabilities for this regime
        regime_y_prob_calibrated = calibrator.calibrate(regime_y_prob, regime=regime)
        
        # Visualize calibration curve for this regime
        logger.info(f"Visualizing calibration curve for regime '{regime}'...")
        calibrator.visualize_calibration_curve(
            y_true=regime_y_test,
            y_prob=regime_y_prob,
            y_prob_calibrated=regime_y_prob_calibrated,
            title=f'Gradient Boosting Calibration - Regime: {regime}'
        )
    
    # Compare calibration across regimes
    logger.info("Comparing calibration across regimes...")
    calibrator.visualize_calibration_comparison(
        regimes=list(unique_regimes) + ['global'],
        metric='ece'
    )
    
    return calibrator

def example_calibration_methods_comparison():
    """
    Demonstrate comparison of different calibration methods.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a model
    logger.info("Training a model...")
    model = LogisticRegression(random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions
    y_prob_train = model.predict_proba(X_train)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    
    # Create calibrators with different methods
    logger.info("Creating calibrators with different methods...")
    methods = ['platt', 'isotonic', 'beta', 'ensemble']
    calibrators = {}
    calibrated_probs = {}
    
    for method in methods:
        logger.info(f"Fitting calibrator with method '{method}'...")
        calibrator = ModelCalibrator(method=method, regime_aware=False)
        calibrator.fit(y_train, y_prob_train)
        
        # Calibrate probabilities
        calibrated_probs[method] = calibrator.calibrate(y_prob_test)
        calibrators[method] = calibrator
    
    # Compare calibration methods
    logger.info("Comparing calibration methods...")
    plt.figure(figsize=(12, 8))
    
    # Plot diagonal (perfect calibration)
    plt.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')
    
    # Plot uncalibrated curve
    prob_true, prob_pred = calibration_curve(y_test, y_prob_test, n_bins=10)
    plt.plot(prob_pred, prob_true, 'o-', label='Uncalibrated')
    
    # Plot calibrated curves
    for method in methods:
        prob_true_cal, prob_pred_cal = calibration_curve(y_test, calibrated_probs[method], n_bins=10)
        plt.plot(prob_pred_cal, prob_true_cal, 's-', label=f'{method.title()} Calibration')
    
    # Set plot properties
    plt.xlabel('Mean predicted probability')
    plt.ylabel('Fraction of positives')
    plt.title('Comparison of Calibration Methods')
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    
    # Show plot
    plt.tight_layout()
    plt.show()
    
    # Compare calibration metrics
    logger.info("Comparing calibration metrics...")
    metrics = pd.DataFrame(index=methods + ['uncalibrated'], columns=['ECE', 'MCE', 'Brier Score', 'Log Loss'])
    
    # Calculate metrics for uncalibrated probabilities
    uncal_metrics = evaluate_calibration(y_test, y_prob_test, visualize=False)
    metrics.loc['uncalibrated', 'ECE'] = uncal_metrics['uncalibrated_ece']
    metrics.loc['uncalibrated', 'MCE'] = uncal_metrics['uncalibrated_mce']
    metrics.loc['uncalibrated', 'Brier Score'] = uncal_metrics['uncalibrated_brier_score']
    metrics.loc['uncalibrated', 'Log Loss'] = uncal_metrics['uncalibrated_log_loss']
    
    # Calculate metrics for each calibration method
    for method in methods:
        cal_metrics = evaluate_calibration(y_test, y_prob_test, calibrated_probs[method], visualize=False)
        metrics.loc[method, 'ECE'] = cal_metrics['calibrated_ece']
        metrics.loc[method, 'MCE'] = cal_metrics['calibrated_mce']
        metrics.loc[method, 'Brier Score'] = cal_metrics['calibrated_brier_score']
        metrics.loc[method, 'Log Loss'] = cal_metrics['calibrated_log_loss']
    
    print("Calibration Metrics Comparison:")
    print(metrics)
    
    return calibrators, calibrated_probs, metrics

def example_convenience_functions():
    """
    Demonstrate convenience functions for quick calibration.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a model
    logger.info("Training a model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions
    y_prob_train = model.predict_proba(X_train)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    
    # Use convenience function for calibration
    logger.info("Using calibrate_probabilities convenience function...")
    y_prob_calibrated, calibrator = calibrate_probabilities(
        y_true=y_train,
        y_prob=y_prob_train,
        method='platt',
        test_y_prob=y_prob_test
    )
    
    # Use convenience function for evaluation
    logger.info("Using evaluate_calibration convenience function...")
    metrics = evaluate_calibration(
        y_true=y_test,
        y_prob=y_prob_test,
        y_prob_calibrated=y_prob_calibrated,
        visualize=True
    )
    
    print("Calibration Metrics:")
    print(f"Uncalibrated ECE: {metrics['uncalibrated_ece']:.4f}")
    print(f"Calibrated ECE: {metrics['calibrated_ece']:.4f}")
    print(f"Improvement: {(1 - metrics['calibrated_ece'] / metrics['uncalibrated_ece']) * 100:.2f}%")
    
    return y_prob_calibrated, calibrator, metrics

def example_integration_with_ensemble():
    """
    Demonstrate integration with the EnsembleManager.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Import EnsembleManager and ModelFactory
    from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager
    from advanced_trading.models.ml_ensemble.model_factory import ModelFactory
    
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
    y_prob_train = ensemble.predict_proba(X_train)
    y_prob_test = ensemble.predict_proba(X_test)
    
    # Create calibrator
    logger.info("Creating calibrator...")
    calibrator = ModelCalibrator(method='platt', regime_aware=True)
    
    # Fit calibrator
    logger.info("Fitting calibrator...")
    calibrator.fit(y_train, y_prob_train, regimes=regimes_train)
    
    # Calibrate probabilities
    logger.info("Calibrating probabilities...")
    y_prob_calibrated = calibrator.calibrate(y_prob_test)
    
    # Evaluate calibration
    logger.info("Evaluating calibration...")
    calibrator.visualize_calibration_curve(
        y_true=y_test,
        y_prob=y_prob_test,
        y_prob_calibrated=y_prob_calibrated,
        title='Ensemble Calibration'
    )
    
    return ensemble, calibrator, y_prob_test, y_prob_calibrated

def main():
    """
    Run the model calibration examples.
    """
    logger.info("Starting model calibration examples...")
    
    # Example 1: Basic Calibration
    logger.info("\n\n=== Example 1: Basic Calibration ===")
    calibrator, y_prob_test, y_prob_calibrated = example_basic_calibration()
    
    # Example 2: Regime-Specific Calibration
    logger.info("\n\n=== Example 2: Regime-Specific Calibration ===")
    regime_calibrator = example_regime_specific_calibration()
    
    # Example 3: Calibration Methods Comparison
    logger.info("\n\n=== Example 3: Calibration Methods Comparison ===")
    calibrators, calibrated_probs, metrics = example_calibration_methods_comparison()
    
    # Example 4: Convenience Functions
    logger.info("\n\n=== Example 4: Convenience Functions ===")
    y_prob_calibrated, quick_calibrator, quick_metrics = example_convenience_functions()
    
    # Example 5: Integration with Ensemble
    logger.info("\n\n=== Example 5: Integration with Ensemble ===")
    ensemble, ensemble_calibrator, ensemble_y_prob, ensemble_y_prob_calibrated = example_integration_with_ensemble()
    
    logger.info("Model calibration examples completed")

if __name__ == "__main__":
    main() 