"""
Model Persistence Example
------------------------
This example demonstrates how to use the model persistence functionality
to save, load, and manage machine learning models.

The example covers:
1. Saving and loading individual models
2. Using the model registry to manage multiple models
3. Tracking model performance metrics
4. Working with model versions
5. Using tags to organize models
"""

import os
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification, make_regression
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import accuracy_score, mean_squared_error, f1_score, precision_score, recall_score

# Import model persistence functionality
from advanced_trading.models.ml_ensemble.model_persistence import (
    ModelPersistence,
    ModelRegistry,
    save_model,
    load_model,
    register_model,
    list_models,
    get_model_versions
)

# Set up a temporary directory for models in this example
EXAMPLE_MODEL_DIR = os.path.join(os.getcwd(), 'example_models')
os.makedirs(EXAMPLE_MODEL_DIR, exist_ok=True)

def generate_example_data():
    """Generate example data for classification and regression."""
    # Classification data
    X_cls, y_cls = make_classification(
        n_samples=1000,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        n_classes=2,
        random_state=42
    )
    
    X_cls_train, X_cls_test, y_cls_train, y_cls_test = train_test_split(
        X_cls, y_cls, test_size=0.3, random_state=42
    )
    
    # Regression data
    X_reg, y_reg = make_regression(
        n_samples=1000,
        n_features=20,
        n_informative=10,
        noise=0.1,
        random_state=42
    )
    
    X_reg_train, X_reg_test, y_reg_train, y_reg_test = train_test_split(
        X_reg, y_reg, test_size=0.3, random_state=42
    )
    
    return {
        'classification': {
            'train': (X_cls_train, y_cls_train),
            'test': (X_cls_test, y_cls_test)
        },
        'regression': {
            'train': (X_reg_train, y_reg_train),
            'test': (X_reg_test, y_reg_test)
        }
    }

def example_basic_model_persistence():
    """Example of basic model persistence operations."""
    print("\n=== Basic Model Persistence Example ===")
    
    # Generate data
    data = generate_example_data()
    X_train, y_train = data['classification']['train']
    X_test, y_test = data['classification']['test']
    
    # Train a model
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate the model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model accuracy: {accuracy:.4f}")
    
    # Create a ModelPersistence instance
    persistence = ModelPersistence(base_dir=EXAMPLE_MODEL_DIR)
    
    # Save the model with metadata
    metadata = {
        'description': 'Random Forest classifier for example data',
        'accuracy': accuracy,
        'data_shape': X_train.shape,
        'features': [f'feature_{i}' for i in range(X_train.shape[1])],
        'performance': {
            'accuracy': accuracy,
            'f1': f1_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred)
        }
    }
    
    version_dir = persistence.save_model(
        model=model,
        model_name='example_classifier',
        metadata=metadata
    )
    
    print(f"Model saved to: {version_dir}")
    
    # Load the model
    loaded_model = persistence.load_model(
        model_name='example_classifier',
        version='latest'
    )
    
    # Verify the loaded model
    y_pred_loaded = loaded_model.predict(X_test)
    loaded_accuracy = accuracy_score(y_test, y_pred_loaded)
    print(f"Loaded model accuracy: {loaded_accuracy:.4f}")
    
    # Load the model with metadata
    loaded_model, loaded_metadata = persistence.load_model(
        model_name='example_classifier',
        version='latest',
        with_metadata=True
    )
    
    print(f"Loaded model metadata: {loaded_metadata['description']}")
    print(f"Loaded model performance: {loaded_metadata['performance']}")
    
    # Get model versions
    versions = persistence.get_model_versions('example_classifier')
    print(f"Model versions: {versions}")
    
    # Get model metadata
    metadata = persistence.get_model_metadata('example_classifier')
    print(f"Model created at: {metadata['created_at']}")

def example_model_registry():
    """Example of using the model registry."""
    print("\n=== Model Registry Example ===")
    
    # Generate data
    data = generate_example_data()
    
    # Classification data
    X_cls_train, y_cls_train = data['classification']['train']
    X_cls_test, y_cls_test = data['classification']['test']
    
    # Regression data
    X_reg_train, y_reg_train = data['regression']['train']
    X_reg_test, y_reg_test = data['regression']['test']
    
    # Create a ModelRegistry instance
    registry = ModelRegistry(base_dir=EXAMPLE_MODEL_DIR)
    
    # Train and register a classification model
    rf_cls = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_cls.fit(X_cls_train, y_cls_train)
    
    # Evaluate the model
    y_cls_pred = rf_cls.predict(X_cls_test)
    cls_accuracy = accuracy_score(y_cls_test, y_cls_pred)
    
    # Register the model with metadata and tags
    rf_version = registry.register_model(
        model=rf_cls,
        model_name='random_forest_classifier',
        metadata={
            'description': 'Random Forest classifier for financial data',
            'performance': {
                'accuracy': cls_accuracy,
                'f1': f1_score(y_cls_test, y_cls_pred),
                'precision': precision_score(y_cls_test, y_cls_pred),
                'recall': recall_score(y_cls_test, y_cls_pred)
            }
        },
        tags=['classification', 'random_forest', 'financial']
    )
    
    print(f"Registered classification model with version: {rf_version}")
    
    # Train and register a regression model
    rf_reg = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_reg.fit(X_reg_train, y_reg_train)
    
    # Evaluate the model
    y_reg_pred = rf_reg.predict(X_reg_test)
    reg_mse = mean_squared_error(y_reg_test, y_reg_pred)
    
    # Register the model with metadata and tags
    reg_version = registry.register_model(
        model=rf_reg,
        model_name='random_forest_regressor',
        metadata={
            'description': 'Random Forest regressor for financial data',
            'performance': {
                'mse': reg_mse,
                'rmse': np.sqrt(reg_mse),
                'mae': np.mean(np.abs(y_reg_test - y_reg_pred))
            }
        },
        tags=['regression', 'random_forest', 'financial']
    )
    
    print(f"Registered regression model with version: {reg_version}")
    
    # Train and register another version of the classification model
    lr_cls = LogisticRegression(random_state=42)
    lr_cls.fit(X_cls_train, y_cls_train)
    
    # Evaluate the model
    y_lr_pred = lr_cls.predict(X_cls_test)
    lr_accuracy = accuracy_score(y_cls_test, y_lr_pred)
    
    # Register the model with metadata and tags
    lr_version = registry.register_model(
        model=lr_cls,
        model_name='logistic_regression',
        metadata={
            'description': 'Logistic Regression classifier for financial data',
            'performance': {
                'accuracy': lr_accuracy,
                'f1': f1_score(y_cls_test, y_lr_pred),
                'precision': precision_score(y_cls_test, y_lr_pred),
                'recall': recall_score(y_cls_test, y_lr_pred)
            }
        },
        tags=['classification', 'linear', 'financial']
    )
    
    print(f"Registered logistic regression model with version: {lr_version}")
    
    # List all models in the registry
    models_df = registry.list_models()
    print("\nAll models in registry:")
    print(models_df)
    
    # List models filtered by tags
    rf_models = registry.list_models(tags=['random_forest'])
    print("\nRandom Forest models:")
    print(rf_models)
    
    # Get model versions
    cls_versions = registry.get_model_versions('random_forest_classifier')
    print("\nRandom Forest classifier versions:")
    print(cls_versions)
    
    # Load a model from the registry
    loaded_model = registry.get_model(
        model_name='random_forest_classifier',
        version='latest'
    )
    
    # Verify the loaded model
    y_loaded_pred = loaded_model.predict(X_cls_test)
    loaded_accuracy = accuracy_score(y_cls_test, y_loaded_pred)
    print(f"\nLoaded model accuracy: {loaded_accuracy:.4f}")
    
    # Update model performance
    new_performance = {
        'accuracy': loaded_accuracy,
        'custom_metric': 0.95
    }
    
    registry.update_model_performance(
        model_name='random_forest_classifier',
        version=rf_version,
        performance=new_performance
    )
    
    # Get updated model versions
    updated_versions = registry.get_model_versions('random_forest_classifier')
    print("\nUpdated Random Forest classifier versions:")
    print(updated_versions)

def example_convenience_functions():
    """Example of using convenience functions for model persistence."""
    print("\n=== Convenience Functions Example ===")
    
    # Generate data
    data = generate_example_data()
    X_train, y_train = data['regression']['train']
    X_test, y_test = data['regression']['test']
    
    # Train a model
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Evaluate the model
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    
    # Save the model using convenience function
    save_model(
        model=model,
        model_name='linear_regression',
        metadata={
            'description': 'Linear regression model for example data',
            'performance': {
                'mse': mse,
                'rmse': np.sqrt(mse)
            }
        },
        base_dir=EXAMPLE_MODEL_DIR
    )
    
    print(f"Model saved with convenience function")
    
    # Load the model using convenience function
    loaded_model = load_model(
        model_name='linear_regression',
        base_dir=EXAMPLE_MODEL_DIR
    )
    
    # Verify the loaded model
    y_loaded_pred = loaded_model.predict(X_test)
    loaded_mse = mean_squared_error(y_test, y_loaded_pred)
    print(f"Loaded model MSE: {loaded_mse:.4f}")
    
    # Register the model using convenience function
    register_model(
        model=model,
        model_name='linear_regression_registered',
        metadata={
            'description': 'Registered linear regression model',
            'performance': {
                'mse': mse,
                'rmse': np.sqrt(mse)
            }
        },
        tags=['regression', 'linear'],
        base_dir=EXAMPLE_MODEL_DIR
    )
    
    print(f"Model registered with convenience function")
    
    # List models using convenience function
    models_df = list_models(base_dir=EXAMPLE_MODEL_DIR)
    print("\nAll models:")
    print(models_df)
    
    # Get model versions using convenience function
    versions_df = get_model_versions(
        model_name='linear_regression_registered',
        base_dir=EXAMPLE_MODEL_DIR
    )
    print("\nModel versions:")
    print(versions_df)

def example_model_versioning():
    """Example of model versioning."""
    print("\n=== Model Versioning Example ===")
    
    # Generate data
    data = generate_example_data()
    X_train, y_train = data['classification']['train']
    X_test, y_test = data['classification']['test']
    
    # Create a ModelRegistry instance
    registry = ModelRegistry(base_dir=EXAMPLE_MODEL_DIR)
    
    # Train and register multiple versions of a model
    for n_estimators in [10, 50, 100, 200]:
        # Train model with different hyperparameters
        model = RandomForestClassifier(n_estimators=n_estimators, random_state=42)
        model.fit(X_train, y_train)
        
        # Evaluate the model
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Register the model with version based on hyperparameters
        version = f"n_est_{n_estimators}"
        
        registry.register_model(
            model=model,
            model_name='rf_hyperparameter_tuning',
            metadata={
                'description': f'Random Forest with {n_estimators} estimators',
                'hyperparameters': {
                    'n_estimators': n_estimators,
                    'random_state': 42
                },
                'performance': {
                    'accuracy': accuracy,
                    'f1': f1_score(y_test, y_pred)
                }
            },
            version=version,
            tags=['classification', 'random_forest', 'hyperparameter_tuning']
        )
        
        print(f"Registered model version {version} with accuracy: {accuracy:.4f}")
    
    # Get all versions of the model
    versions_df = registry.get_model_versions('rf_hyperparameter_tuning')
    print("\nAll model versions:")
    print(versions_df)
    
    # Find the best performing version
    best_version = versions_df.loc[versions_df['performance_accuracy'].idxmax()]['version']
    print(f"\nBest performing version: {best_version}")
    
    # Load the best performing model
    best_model = registry.get_model(
        model_name='rf_hyperparameter_tuning',
        version=best_version
    )
    
    # Verify the best model
    y_best_pred = best_model.predict(X_test)
    best_accuracy = accuracy_score(y_test, y_best_pred)
    print(f"Best model accuracy: {best_accuracy:.4f}")

def cleanup():
    """Clean up example models directory."""
    import shutil
    if os.path.exists(EXAMPLE_MODEL_DIR):
        shutil.rmtree(EXAMPLE_MODEL_DIR)
        print(f"\nCleaned up example models directory: {EXAMPLE_MODEL_DIR}")

def main():
    """Run all examples."""
    try:
        # Run examples
        example_basic_model_persistence()
        example_model_registry()
        example_convenience_functions()
        example_model_versioning()
    finally:
        # Clean up
        cleanup()

if __name__ == "__main__":
    main() 