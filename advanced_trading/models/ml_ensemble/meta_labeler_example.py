"""
Meta-Labeling Example
-------------------
This example demonstrates how to use the MetaLabeler class to implement
meta-labeling strategies in financial machine learning applications.

The example covers:
1. Basic meta-labeling with a primary model
2. Regime-specific meta-labeling
3. Visualizing meta-labeling performance
4. Optimizing the meta-labeling threshold
5. Using convenience functions for quick meta-labeling
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import logging

# Import the MetaLabeler class and convenience functions
from advanced_trading.models.ml_ensemble.meta_labeler import (
    MetaLabeler,
    apply_meta_labeling,
    evaluate_meta_labeling,
    optimize_meta_labeling_threshold
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

def example_basic_meta_labeling():
    """
    Demonstrate basic meta-labeling with a primary model.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a primary model
    logger.info("Training primary model...")
    primary_model = RandomForestClassifier(n_estimators=100, random_state=42)
    primary_model.fit(X_train, y_train)
    
    # Make predictions with primary model
    primary_pred_train = primary_model.predict(X_train)
    primary_pred_test = primary_model.predict(X_test)
    
    # Create meta-labeler
    logger.info("Creating meta-labeler...")
    meta_labeler = MetaLabeler(
        primary_model=None,  # We'll provide primary predictions directly
        meta_model=GradientBoostingClassifier(random_state=42),
        threshold=0.5,
        regime_aware=False
    )
    
    # Fit meta-labeler
    logger.info("Fitting meta-labeler...")
    meta_labeler.fit(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train
    )
    
    # Generate meta-labeled predictions
    logger.info("Generating meta-labeled predictions...")
    meta_pred_test = meta_labeler.predict(
        X=X_test,
        primary_predictions=primary_pred_test
    )
    
    # Evaluate meta-labeling
    logger.info("Evaluating meta-labeling...")
    metrics = meta_labeler.evaluate(
        X=X_test,
        y=y_test,
        primary_predictions=primary_pred_test
    )
    
    # Print metrics
    print("\nPrimary Model Metrics:")
    print(f"Accuracy: {metrics['primary']['accuracy']:.4f}")
    print(f"Precision: {metrics['primary']['precision']:.4f}")
    print(f"Recall: {metrics['primary']['recall']:.4f}")
    print(f"F1: {metrics['primary']['f1']:.4f}")
    print(f"Trades: {metrics['primary']['trades']} ({metrics['primary']['trades'] / len(y_test):.2%} of samples)")
    
    print("\nMeta-Labeled Model Metrics:")
    print(f"Accuracy: {metrics['meta']['accuracy']:.4f}")
    print(f"Precision: {metrics['meta']['precision']:.4f}")
    print(f"Recall: {metrics['meta']['recall']:.4f}")
    print(f"F1: {metrics['meta']['f1']:.4f}")
    print(f"Trades: {metrics['meta']['trades']} ({metrics['meta']['trades'] / len(y_test):.2%} of samples)")
    
    print("\nImprovements:")
    print(f"Accuracy: {metrics['improvement']['accuracy']:.4f}")
    print(f"Precision: {metrics['improvement']['precision']:.4f}")
    print(f"Recall: {metrics['improvement']['recall']:.4f}")
    print(f"F1: {metrics['improvement']['f1']:.4f}")
    
    # Visualize meta-labeling performance
    logger.info("Visualizing meta-labeling performance...")
    meta_labeler.visualize_meta_model_performance()
    
    # Visualize trade filtering
    logger.info("Visualizing trade filtering...")
    meta_labeler.visualize_trade_filtering(
        X=X_test,
        y=y_test,
        primary_predictions=primary_pred_test
    )
    
    return meta_labeler, primary_model, metrics

def example_regime_specific_meta_labeling():
    """
    Demonstrate regime-specific meta-labeling.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a primary model
    logger.info("Training primary model...")
    primary_model = RandomForestClassifier(n_estimators=100, random_state=42)
    primary_model.fit(X_train, y_train)
    
    # Make predictions with primary model
    primary_pred_train = primary_model.predict(X_train)
    primary_pred_test = primary_model.predict(X_test)
    
    # Create meta-labeler with regime awareness
    logger.info("Creating regime-aware meta-labeler...")
    meta_labeler = MetaLabeler(
        primary_model=None,  # We'll provide primary predictions directly
        meta_model=GradientBoostingClassifier(random_state=42),
        threshold=0.5,
        regime_aware=True
    )
    
    # Fit meta-labeler with regimes
    logger.info("Fitting regime-aware meta-labeler...")
    meta_labeler.fit(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train,
        regimes=regimes_train
    )
    
    # Generate meta-labeled predictions for each regime
    logger.info("Generating regime-specific meta-labeled predictions...")
    unique_regimes = np.unique(regimes_test)
    
    for regime in unique_regimes:
        # Get data for this regime
        regime_mask = (regimes_test == regime)
        regime_X_test = X_test[regime_mask]
        regime_y_test = y_test[regime_mask]
        regime_primary_pred = primary_pred_test[regime_mask]
        
        # Generate meta-labeled predictions for this regime
        regime_meta_pred = meta_labeler.predict(
            X=regime_X_test,
            primary_predictions=regime_primary_pred,
            regime=regime
        )
        
        # Evaluate meta-labeling for this regime
        metrics = meta_labeler.evaluate(
            X=regime_X_test,
            y=regime_y_test,
            primary_predictions=regime_primary_pred
        )
        
        # Print metrics for this regime
        print(f"\nRegime: {regime}")
        print(f"Primary Model - Precision: {metrics['primary']['precision']:.4f}, Recall: {metrics['primary']['recall']:.4f}, Trades: {metrics['primary']['trades']}")
        print(f"Meta-Labeled Model - Precision: {metrics['meta']['precision']:.4f}, Recall: {metrics['meta']['recall']:.4f}, Trades: {metrics['meta']['trades']}")
        print(f"Precision Improvement: {metrics['improvement']['precision']:.4f}")
    
    # Compare regimes
    logger.info("Comparing regimes...")
    meta_labeler.visualize_regime_comparison(
        regimes=list(unique_regimes),
        metric='precision'
    )
    
    meta_labeler.visualize_regime_comparison(
        regimes=list(unique_regimes),
        metric='trade_reduction'
    )
    
    return meta_labeler, primary_model

def example_threshold_optimization():
    """
    Demonstrate meta-labeling threshold optimization.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a primary model
    logger.info("Training primary model...")
    primary_model = RandomForestClassifier(n_estimators=100, random_state=42)
    primary_model.fit(X_train, y_train)
    
    # Make predictions with primary model
    primary_pred_train = primary_model.predict(X_train)
    primary_pred_test = primary_model.predict(X_test)
    
    # Create meta-labeler
    logger.info("Creating meta-labeler...")
    meta_labeler = MetaLabeler(
        primary_model=None,  # We'll provide primary predictions directly
        meta_model=GradientBoostingClassifier(random_state=42),
        threshold=0.5,  # Initial threshold
        regime_aware=False
    )
    
    # Fit meta-labeler
    logger.info("Fitting meta-labeler...")
    meta_labeler.fit(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train
    )
    
    # Visualize threshold impact
    logger.info("Visualizing threshold impact...")
    meta_labeler.visualize_threshold_impact(
        X=X_test,
        y=y_test,
        primary_predictions=primary_pred_test
    )
    
    # Optimize threshold using convenience function
    logger.info("Optimizing threshold...")
    optimal_threshold, metrics = optimize_meta_labeling_threshold(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train,
        meta_model=GradientBoostingClassifier(random_state=42),
        metric='f1'
    )
    
    print(f"\nOptimal Threshold: {optimal_threshold:.4f}")
    print(f"Primary Model - Precision: {metrics['primary']['precision']:.4f}, Recall: {metrics['primary']['recall']:.4f}, F1: {metrics['primary']['f1']:.4f}")
    print(f"Meta-Labeled Model - Precision: {metrics['meta']['precision']:.4f}, Recall: {metrics['meta']['recall']:.4f}, F1: {metrics['meta']['f1']:.4f}")
    print(f"Precision Improvement: {metrics['improvement']['precision']:.4f}")
    print(f"F1 Improvement: {metrics['improvement']['f1']:.4f}")
    
    return optimal_threshold, metrics

def example_meta_features():
    """
    Demonstrate meta-labeling with additional meta-features.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a primary model
    logger.info("Training primary model...")
    primary_model = RandomForestClassifier(n_estimators=100, random_state=42)
    primary_model.fit(X_train, y_train)
    
    # Make predictions with primary model
    primary_pred_train = primary_model.predict(X_train)
    primary_pred_test = primary_model.predict(X_test)
    
    # Create additional meta-features
    logger.info("Creating meta-features...")
    
    # Example meta-features: prediction confidence, volatility, and trend strength
    if hasattr(primary_model, 'predict_proba'):
        # Prediction confidence (distance from 0.5)
        confidence_train = np.abs(primary_model.predict_proba(X_train)[:, 1] - 0.5) * 2
        confidence_test = np.abs(primary_model.predict_proba(X_test)[:, 1] - 0.5) * 2
    else:
        # Dummy confidence if predict_proba not available
        confidence_train = np.ones(len(y_train)) * 0.8
        confidence_test = np.ones(len(y_test)) * 0.8
    
    # Volatility (standard deviation of features)
    volatility_train = X_train.std(axis=1)
    volatility_test = X_test.std(axis=1)
    
    # Trend strength (absolute value of trend feature)
    trend_train = np.abs(X_train['feature_trend'])
    trend_test = np.abs(X_test['feature_trend'])
    
    # Combine meta-features
    meta_features_train = pd.DataFrame({
        'confidence': confidence_train,
        'volatility': volatility_train,
        'trend_strength': trend_train
    })
    
    meta_features_test = pd.DataFrame({
        'confidence': confidence_test,
        'volatility': volatility_test,
        'trend_strength': trend_test
    })
    
    # Create meta-labeler
    logger.info("Creating meta-labeler with meta-features...")
    meta_labeler = MetaLabeler(
        primary_model=None,  # We'll provide primary predictions directly
        meta_model=GradientBoostingClassifier(random_state=42),
        threshold=0.5,
        regime_aware=False
    )
    
    # Fit meta-labeler with meta-features
    logger.info("Fitting meta-labeler with meta-features...")
    meta_labeler.fit(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train,
        meta_features=meta_features_train
    )
    
    # Generate meta-labeled predictions with meta-features
    logger.info("Generating meta-labeled predictions with meta-features...")
    meta_pred_test = meta_labeler.predict(
        X=X_test,
        primary_predictions=primary_pred_test,
        meta_features=meta_features_test
    )
    
    # Evaluate meta-labeling with meta-features
    logger.info("Evaluating meta-labeling with meta-features...")
    metrics_with_meta = meta_labeler.evaluate(
        X=X_test,
        y=y_test,
        primary_predictions=primary_pred_test,
        meta_features=meta_features_test
    )
    
    # For comparison, fit meta-labeler without meta-features
    logger.info("Fitting meta-labeler without meta-features...")
    meta_labeler_no_meta = MetaLabeler(
        primary_model=None,
        meta_model=GradientBoostingClassifier(random_state=42),
        threshold=0.5,
        regime_aware=False
    )
    
    meta_labeler_no_meta.fit(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train
    )
    
    # Evaluate meta-labeling without meta-features
    logger.info("Evaluating meta-labeling without meta-features...")
    metrics_no_meta = meta_labeler_no_meta.evaluate(
        X=X_test,
        y=y_test,
        primary_predictions=primary_pred_test
    )
    
    # Print comparison
    print("\nMeta-Labeling Without Meta-Features:")
    print(f"Precision: {metrics_no_meta['meta']['precision']:.4f}")
    print(f"Recall: {metrics_no_meta['meta']['recall']:.4f}")
    print(f"F1: {metrics_no_meta['meta']['f1']:.4f}")
    print(f"Trades: {metrics_no_meta['meta']['trades']} ({metrics_no_meta['meta']['trades'] / len(y_test):.2%} of samples)")
    
    print("\nMeta-Labeling With Meta-Features:")
    print(f"Precision: {metrics_with_meta['meta']['precision']:.4f}")
    print(f"Recall: {metrics_with_meta['meta']['recall']:.4f}")
    print(f"F1: {metrics_with_meta['meta']['f1']:.4f}")
    print(f"Trades: {metrics_with_meta['meta']['trades']} ({metrics_with_meta['meta']['trades'] / len(y_test):.2%} of samples)")
    
    print("\nImprovement from Meta-Features:")
    print(f"Precision: {metrics_with_meta['meta']['precision'] - metrics_no_meta['meta']['precision']:.4f}")
    print(f"Recall: {metrics_with_meta['meta']['recall'] - metrics_no_meta['meta']['recall']:.4f}")
    print(f"F1: {metrics_with_meta['meta']['f1'] - metrics_no_meta['meta']['f1']:.4f}")
    
    return meta_labeler, meta_features_test, metrics_with_meta, metrics_no_meta

def example_convenience_functions():
    """
    Demonstrate convenience functions for quick meta-labeling.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Train a primary model
    logger.info("Training primary model...")
    primary_model = RandomForestClassifier(n_estimators=100, random_state=42)
    primary_model.fit(X_train, y_train)
    
    # Make predictions with primary model
    primary_pred_train = primary_model.predict(X_train)
    primary_pred_test = primary_model.predict(X_test)
    
    # Use apply_meta_labeling convenience function
    logger.info("Using apply_meta_labeling convenience function...")
    meta_pred_test, meta_labeler = apply_meta_labeling(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train,
        meta_model=GradientBoostingClassifier(random_state=42),
        threshold=0.5,
        regimes=regimes_train,
        return_meta_labeler=True
    )
    
    # Use evaluate_meta_labeling convenience function
    logger.info("Using evaluate_meta_labeling convenience function...")
    metrics = evaluate_meta_labeling(
        X=X_test,
        y=y_test,
        primary_predictions=primary_pred_test,
        meta_model=GradientBoostingClassifier(random_state=42),
        threshold=0.5,
        regimes=regimes_test,
        visualize=True
    )
    
    # Use optimize_meta_labeling_threshold convenience function
    logger.info("Using optimize_meta_labeling_threshold convenience function...")
    optimal_threshold, opt_metrics = optimize_meta_labeling_threshold(
        X=X_train,
        y=y_train,
        primary_predictions=primary_pred_train,
        meta_model=GradientBoostingClassifier(random_state=42),
        regimes=regimes_train,
        metric='precision',
        visualize=True
    )
    
    print(f"\nOptimal Threshold: {optimal_threshold:.4f}")
    print(f"Primary Model - Precision: {opt_metrics['primary']['precision']:.4f}, Recall: {opt_metrics['primary']['recall']:.4f}")
    print(f"Meta-Labeled Model - Precision: {opt_metrics['meta']['precision']:.4f}, Recall: {opt_metrics['meta']['recall']:.4f}")
    print(f"Precision Improvement: {opt_metrics['improvement']['precision']:.4f}")
    
    return meta_labeler, metrics, optimal_threshold, opt_metrics

def main():
    """
    Run the meta-labeling examples.
    """
    logger.info("Starting meta-labeling examples...")
    
    # Example 1: Basic Meta-Labeling
    logger.info("\n\n=== Example 1: Basic Meta-Labeling ===")
    meta_labeler, primary_model, metrics = example_basic_meta_labeling()
    
    # Example 2: Regime-Specific Meta-Labeling
    logger.info("\n\n=== Example 2: Regime-Specific Meta-Labeling ===")
    regime_meta_labeler, regime_primary_model = example_regime_specific_meta_labeling()
    
    # Example 3: Threshold Optimization
    logger.info("\n\n=== Example 3: Threshold Optimization ===")
    optimal_threshold, opt_metrics = example_threshold_optimization()
    
    # Example 4: Meta-Features
    logger.info("\n\n=== Example 4: Meta-Features ===")
    meta_features_labeler, meta_features, metrics_with_meta, metrics_no_meta = example_meta_features()
    
    # Example 5: Convenience Functions
    logger.info("\n\n=== Example 5: Convenience Functions ===")
    conv_meta_labeler, conv_metrics, conv_threshold, conv_opt_metrics = example_convenience_functions()
    
    logger.info("Meta-labeling examples completed")

if __name__ == "__main__":
    main() 