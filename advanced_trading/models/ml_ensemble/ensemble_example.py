"""
Ensemble Manager Example
-----------------------
This example demonstrates how to use the EnsembleManager class to create, train,
and evaluate ensembles of machine learning models for financial predictions.

The example covers:
1. Creating an ensemble of different model types
2. Training the ensemble with regime information
3. Making predictions with regime awareness
4. Updating model weights based on recent performance
5. Visualizing feature importance and model weights
6. Saving and loading ensemble models
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
import logging

# Import the EnsembleManager class
from advanced_trading.models.ml_ensemble.ensemble_manager import EnsembleManager

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
    X = np.random.randn(n_samples, n_features)
    
    # Create target (binary classification for direction prediction)
    y = (np.random.randn(n_samples) > 0).astype(int)
    
    # Create regime labels (3 different regimes)
    regimes = np.random.choice(['bull', 'bear', 'sideways'], size=n_samples, p=[0.4, 0.3, 0.3])
    
    # Create DataFrame with named features
    feature_names = [f'feature_{i}' for i in range(n_features)]
    X_df = pd.DataFrame(X, columns=feature_names)
    
    # Convert to pandas Series
    y_series = pd.Series(y, name='target')
    regimes_series = pd.Series(regimes, name='regime')
    
    # Split into train and test sets (80/20)
    train_size = int(0.8 * n_samples)
    
    X_train = X_df.iloc[:train_size]
    y_train = y_series.iloc[:train_size]
    regimes_train = regimes_series.iloc[:train_size]
    
    X_test = X_df.iloc[train_size:]
    y_test = y_series.iloc[train_size:]
    regimes_test = regimes_series.iloc[train_size:]
    
    return X_train, y_train, X_test, y_test, regimes_train, regimes_test

def create_base_models():
    """
    Create a dictionary of base models for the ensemble.
    
    Returns:
    --------
    dict
        Dictionary of base models with model name as key
    """
    models = {
        'random_forest': RandomForestClassifier(
            n_estimators=100, 
            max_depth=5, 
            random_state=42
        ),
        'gradient_boosting': GradientBoostingClassifier(
            n_estimators=100, 
            learning_rate=0.1, 
            max_depth=3, 
            random_state=42
        ),
        'logistic_regression': LogisticRegression(
            C=1.0, 
            max_iter=1000, 
            random_state=42
        ),
        'svm': SVC(
            C=1.0, 
            kernel='rbf', 
            probability=True, 
            random_state=42
        )
    }
    
    return models

def example_ensemble_training():
    """
    Demonstrate training an ensemble model with regime awareness.
    """
    logger.info("Loading example data...")
    X_train, y_train, X_test, y_test, regimes_train, regimes_test = load_example_data()
    
    logger.info("Creating base models...")
    base_models = create_base_models()
    
    # Create meta-model for stacking
    meta_model = LogisticRegression(C=0.1, max_iter=1000, random_state=42)
    
    logger.info("Creating ensemble manager...")
    ensemble = EnsembleManager(
        base_models=base_models,
        ensemble_method='stacking',  # Try 'voting', 'weighted_avg', or 'stacking'
        model_type='classification',
        regime_aware=True,
        feature_names=list(X_train.columns),
        meta_model=meta_model,
        weight_update_freq=10,
        model_memory=50
    )
    
    logger.info("Training ensemble...")
    # Convert series to numpy array for sample weights
    sample_weights = np.ones(len(y_train))
    # Add more weight to recent samples
    sample_weights[-100:] = 2.0
    
    # Fit the ensemble
    ensemble.fit(X_train, y_train, regimes=regimes_train, sample_weights=sample_weights)
    
    logger.info("Ensemble trained successfully")
    return ensemble, X_test, y_test, regimes_test

def example_ensemble_prediction(ensemble, X_test, y_test, regimes_test):
    """
    Demonstrate making predictions with the ensemble and evaluating performance.
    
    Parameters:
    -----------
    ensemble : EnsembleManager
        Trained ensemble model
    X_test : pd.DataFrame
        Test features
    y_test : pd.Series
        Test target
    regimes_test : pd.Series
        Test regimes
    """
    logger.info("Making predictions with the ensemble...")
    
    # Organize test data by regime
    regime_results = {}
    unique_regimes = regimes_test.unique()
    
    for regime in unique_regimes:
        regime_mask = (regimes_test == regime)
        regime_X = X_test[regime_mask]
        regime_y = y_test[regime_mask]
        
        if len(regime_X) < 5:  # Skip if too few samples
            continue
        
        # Make predictions for this regime
        regime_preds = ensemble.predict(regime_X, current_regime=regime)
        
        # Calculate accuracy
        binary_preds = (regime_preds > 0.5).astype(int)
        accuracy = (binary_preds == regime_y.values).mean()
        
        regime_results[regime] = {
            'accuracy': accuracy,
            'samples': len(regime_X),
            'predictions': regime_preds,
            'actuals': regime_y
        }
        
        logger.info(f"Regime '{regime}' accuracy: {accuracy:.4f} ({len(regime_X)} samples)")
    
    # Overall performance
    all_preds = ensemble.predict(X_test)
    binary_preds = (all_preds > 0.5).astype(int)
    overall_accuracy = (binary_preds == y_test.values).mean()
    
    logger.info(f"Overall accuracy: {overall_accuracy:.4f}")
    
    return regime_results, all_preds

def example_weight_updating(ensemble, X_test, y_test):
    """
    Demonstrate updating model weights based on recent performance.
    
    Parameters:
    -----------
    ensemble : EnsembleManager
        Trained ensemble model
    X_test : pd.DataFrame
        Test features
    y_test : pd.Series
        Test target
    """
    logger.info("Updating model weights based on recent performance...")
    
    # Get predictions from each base model
    base_predictions = ensemble._get_base_predictions(X_test)
    
    # Update weights
    ensemble.update_weights(base_predictions, y_test.values)
    
    logger.info("Updated model weights:")
    for model_name, weight in ensemble.model_weights.items():
        logger.info(f"  {model_name}: {weight:.4f}")

def example_visualization(ensemble):
    """
    Demonstrate visualization capabilities of the ensemble.
    
    Parameters:
    -----------
    ensemble : EnsembleManager
        Trained ensemble model
    """
    logger.info("Visualizing feature importance...")
    ensemble.visualize_feature_importance(top_n=10)
    
    logger.info("Visualizing model weights across regimes...")
    ensemble.visualize_model_weights()
    
    if ensemble.model_metrics and any(ensemble.model_metrics.values()):
        logger.info("Visualizing model performance over time...")
        ensemble.visualize_model_performance()

def example_save_load(ensemble):
    """
    Demonstrate saving and loading the ensemble model.
    
    Parameters:
    -----------
    ensemble : EnsembleManager
        Trained ensemble model
    """
    import tempfile
    from pathlib import Path
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        model_path = Path(temp_dir) / "ensemble_model.joblib"
        
        logger.info(f"Saving ensemble model to {model_path}...")
        ensemble.save(str(model_path))
        
        logger.info(f"Loading ensemble model from {model_path}...")
        loaded_ensemble = EnsembleManager.load(str(model_path))
        
        # Verify loaded model has the same weights
        for model_name, weight in ensemble.model_weights.items():
            loaded_weight = loaded_ensemble.model_weights.get(model_name, 0)
            logger.info(f"Model '{model_name}': original weight={weight:.4f}, loaded weight={loaded_weight:.4f}")

def main():
    """Run all examples"""
    try:
        # Train the ensemble
        ensemble, X_test, y_test, regimes_test = example_ensemble_training()
        
        # Make predictions
        regime_results, all_preds = example_ensemble_prediction(ensemble, X_test, y_test, regimes_test)
        
        # Update weights
        example_weight_updating(ensemble, X_test, y_test)
        
        # Visualize results
        example_visualization(ensemble)
        
        # Save and load the model
        example_save_load(ensemble)
        
        logger.info("All examples completed successfully")
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)

if __name__ == "__main__":
    main() 