"""
Feature Selection Example
------------------------
This example demonstrates how to use the FeatureSelector class to select
the most relevant features for machine learning models in financial applications.

The example covers:
1. Creating a feature selector with different methods
2. Selecting features with regime awareness
3. Visualizing feature importance
4. Integrating feature selection with the EnsembleManager
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import logging

# Import the FeatureSelector and EnsembleManager classes
from advanced_trading.models.ml_ensemble.feature_selection import FeatureSelector, select_features, get_feature_importance
from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager
from advanced_trading.models.ml_ensemble.model_factory import ModelFactory

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
    n_features = 50
    
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

def example_feature_selection():
    """
    Demonstrate basic feature selection.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    logger.info(f"Original feature set: {X_train.shape[1]} features")
    
    # Create a feature selector
    logger.info("Creating feature selector...")
    selector = FeatureSelector(
        selection_method='filter',
        n_features=10,
        model_type='classification',
        regime_aware=True
    )
    
    # Fit the selector
    logger.info("Fitting feature selector...")
    selector.fit(X_train, y_train, regimes_train)
    
    # Get selected features for each regime
    for regime in regimes_train.unique():
        selected_features = selector.get_selected_features(regime)
        logger.info(f"Selected features for regime '{regime}': {selected_features}")
    
    # Transform the data
    X_train_selected = selector.transform(X_train, current_regime='trend')
    X_test_selected = selector.transform(X_test, current_regime='trend')
    
    logger.info(f"Selected feature set: {X_train_selected.shape[1]} features")
    
    # Visualize feature importance
    logger.info("Visualizing feature importance...")
    selector.visualize_feature_importance(regime='trend', top_n=10)
    
    return selector, X_train_selected, y_train, X_test_selected, y_test

def example_feature_selection_methods():
    """
    Demonstrate different feature selection methods.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Try different feature selection methods
    methods = ['filter', 'wrapper', 'embedded', 'stability']
    
    for method in methods:
        logger.info(f"Testing feature selection method: {method}")
        
        # Create a feature selector
        selector = FeatureSelector(
            selection_method=method,
            n_features=10,
            model_type='classification',
            regime_aware=False
        )
        
        # Fit and transform
        X_train_selected = selector.fit_transform(X_train, y_train)
        
        # Get selected features
        selected_features = selector.get_selected_features()
        logger.info(f"Selected features using {method}: {selected_features}")
        
        # Visualize feature importance
        selector.visualize_feature_importance(top_n=10)

def example_integration_with_ensemble():
    """
    Demonstrate integration with EnsembleManager.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Step 1: Feature selection
    logger.info("Performing feature selection...")
    selector = FeatureSelector(
        selection_method='embedded',
        n_features=15,
        model_type='classification',
        regime_aware=True
    )
    
    # Fit the selector
    selector.fit(X_train, y_train, regimes_train)
    
    # Step 2: Create base models using ModelFactory
    logger.info("Creating base models...")
    model_factory = ModelFactory()
    base_models = model_factory.create_quick_ensemble_set(prediction_type='classification')
    
    # Step 3: Create ensemble manager
    logger.info("Creating ensemble manager...")
    ensemble = EnsembleManager(
        base_models=base_models,
        ensemble_method='weighted_avg',
        model_type='classification',
        regime_aware=True,
        feature_names=X_train.columns.tolist()
    )
    
    # Step 4: Train the ensemble with selected features for each regime
    logger.info("Training ensemble with selected features...")
    
    # For each regime, select features and train models
    for regime in regimes_train.unique():
        # Get data for this regime
        regime_mask = (regimes_train == regime)
        X_regime = X_train[regime_mask]
        y_regime = y_train[regime_mask]
        
        # Select features for this regime
        selected_features = selector.get_selected_features(regime)
        X_regime_selected = X_regime[selected_features]
        
        # Train models for this regime
        for model_name, model in base_models.items():
            try:
                model.fit(X_regime_selected, y_regime)
                logger.info(f"Trained model '{model_name}' for regime '{regime}' with {len(selected_features)} features")
            except Exception as e:
                logger.error(f"Error training model '{model_name}' for regime '{regime}': {str(e)}")
    
    # Step 5: Make predictions
    logger.info("Making predictions...")
    
    # For each regime in test set, select features and predict
    predictions = []
    
    for regime in regimes_test.unique():
        # Get data for this regime
        regime_mask = (regimes_test == regime)
        X_regime = X_test[regime_mask]
        
        # Select features for this regime
        selected_features = selector.get_selected_features(regime)
        X_regime_selected = X_regime[selected_features]
        
        # Make predictions
        for model_name, model in base_models.items():
            try:
                preds = model.predict(X_regime_selected)
                logger.info(f"Made predictions with model '{model_name}' for regime '{regime}'")
                predictions.append((regime, model_name, preds))
            except Exception as e:
                logger.error(f"Error predicting with model '{model_name}' for regime '{regime}': {str(e)}")
    
    logger.info("Feature selection and ensemble integration complete")
    
    return selector, ensemble, predictions

def example_convenience_functions():
    """
    Demonstrate convenience functions.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    # Use select_features convenience function
    logger.info("Using select_features convenience function...")
    X_train_selected = select_features(
        X_train, 
        y_train, 
        method='filter', 
        n_features=10, 
        model_type='classification',
        regimes=regimes_train,
        current_regime='trend'
    )
    
    logger.info(f"Selected {X_train_selected.shape[1]} features")
    
    # Use get_feature_importance convenience function
    logger.info("Using get_feature_importance convenience function...")
    importances = get_feature_importance(
        X_train,
        y_train,
        method='embedded',
        model_type='classification',
        regimes=regimes_train,
        regime='trend'
    )
    
    logger.info(f"Top 5 important features:\n{importances.head(5)}")
    
    # Plot feature importance
    plt.figure(figsize=(10, 6))
    plt.barh(importances.index[:10], importances['importance'][:10])
    plt.xlabel('Importance')
    plt.ylabel('Feature')
    plt.title('Feature Importance (Trend Regime)')
    plt.tight_layout()
    plt.show()

def main():
    """
    Run the feature selection examples.
    """
    logger.info("Starting feature selection examples...")
    
    # Example 1: Basic feature selection
    logger.info("\n\n=== Example 1: Basic Feature Selection ===")
    selector, X_train_selected, y_train, X_test_selected, y_test = example_feature_selection()
    
    # Example 2: Different feature selection methods
    logger.info("\n\n=== Example 2: Feature Selection Methods ===")
    example_feature_selection_methods()
    
    # Example 3: Integration with ensemble
    logger.info("\n\n=== Example 3: Integration with Ensemble ===")
    selector, ensemble, predictions = example_integration_with_ensemble()
    
    # Example 4: Convenience functions
    logger.info("\n\n=== Example 4: Convenience Functions ===")
    example_convenience_functions()
    
    logger.info("Feature selection examples completed")

if __name__ == "__main__":
    main() 