"""
Example Usage of Enhanced Ensemble Manager
-----------------------------------------
This script demonstrates how to use the enhanced ensemble manager
with regime detection and confidence-based position sizing.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Any
import logging
import os
import time
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the enhanced ensemble manager
from instinct_ai.advanced_trading.models.ml_ensemble.enhanced_ensemble_manager import EnhancedEnsembleManager

# Create a simple mock dataset
def create_mock_data(days: int = 365, n_features: int = 10, n_regimes: int = 3):
    """Create mock market data with different regimes"""
    np.random.seed(42)
    
    # Create date range
    dates = pd.date_range(end=datetime.now(), periods=days)
    
    # Create features
    features = {}
    for i in range(n_features):
        features[f'feature_{i}'] = np.random.randn(days)
    
    # Create target (price direction)
    target = np.random.choice([0, 1], size=days)
    
    # Create regime indicators
    # We'll create periods with different correlations between features and target
    regime_labels = np.zeros(days)
    segment_size = days // n_regimes
    
    for i in range(n_regimes):
        start_idx = i * segment_size
        end_idx = (i+1) * segment_size if i < n_regimes - 1 else days
        regime_labels[start_idx:end_idx] = i
    
    # Create DataFrame
    df = pd.DataFrame(features)
    df['target'] = target
    df['date'] = dates
    df['regime'] = regime_labels
    
    return df

# Create mock model predictions
def generate_mock_predictions(df: pd.DataFrame, n_models: int = 5):
    """Generate mock predictions from multiple models"""
    np.random.seed(42)
    
    days = len(df)
    predictions = {}
    
    # Create different model predictions
    # Some models will be better in certain regimes
    for i in range(n_models):
        # Base accuracy (between 0.5 and 0.7)
        base_accuracy = 0.5 + np.random.rand() * 0.2
        
        # Regime-specific adjustments
        regime_adjustments = np.random.rand(3) * 0.2 - 0.1  # -0.1 to 0.1
        
        # Generate predictions
        model_preds = np.zeros(days)
        
        for regime in range(3):
            regime_mask = df['regime'] == regime
            regime_accuracy = base_accuracy + regime_adjustments[regime]
            
            # Generate predictions with specific accuracy
            correct_mask = np.random.rand(sum(regime_mask)) < regime_accuracy
            wrong_mask = ~correct_mask
            
            model_preds[regime_mask] = df.loc[regime_mask, 'target'].values.copy()
            
            # Flip some predictions to match desired accuracy
            model_preds[regime_mask][wrong_mask] = 1 - model_preds[regime_mask][wrong_mask]
            
        # Convert to probabilities (0.5 to 1.0)
        proba_preds = 0.5 + (model_preds * 0.5)
        
        predictions[f'model_{i}'] = proba_preds
    
    return predictions

# Run a simulation to test the ensemble manager
def run_simulation():
    """Run a simulation of the ensemble manager with mock data"""
    # Create mock data
    print("Creating mock data...")
    mock_data = create_mock_data(days=365, n_features=10, n_regimes=3)
    
    # Define model names
    model_names = [f'model_{i}' for i in range(5)]
    
    # Define regime features
    regime_features = [f'feature_{i}' for i in range(5)]
    
    # Initialize the enhanced ensemble manager
    print("Initializing ensemble manager...")
    ensemble_manager = EnhancedEnsembleManager(
        base_models=model_names,
        n_regimes=3,
        regime_features=regime_features,
        confidence_method='agreement',
        diversity_method='correlation',
        detection_method='kmeans',
        min_confidence_threshold=0.6,
        online_learning_rate=0.05,
        model_save_path='models/ensemble_state'
    )
    
    # Generate mock predictions
    print("Generating mock predictions...")
    mock_predictions = generate_mock_predictions(mock_data, n_models=5)
    
    # Convert to dictionary of model predictions
    predictions_by_day = {}
    for day in range(len(mock_data)):
        predictions_by_day[day] = {
            model: mock_predictions[model][day] for model in model_names
        }
    
    # Run simulation
    print("Running simulation...")
    
    # Track metrics
    position_sizes = []
    confidences = []
    regimes = []
    returns = []
    
    # Process each day
    for day in range(30, len(mock_data)):  # Start after 30 days to have some history
        # Get features for this day
        features = mock_data.iloc[day-30:day][regime_features]
        
        # Detect regime
        regime = ensemble_manager.detect_regime(features)
        regimes.append(regime)
        
        # Select models
        selected_models = ensemble_manager.select_models()
        
        # Get predictions
        day_predictions = predictions_by_day[day]
        
        # Generate ensemble prediction
        prediction, confidence, position_size = ensemble_manager.predict(day_predictions)
        
        # Track metrics
        confidences.append(confidence)
        position_sizes.append(position_size)
        
        # Calculate "return" based on prediction accuracy and position size
        actual = mock_data.iloc[day]['target']
        predicted_class = 1 if prediction > 0.5 else 0
        
        # Simple return calculation: correct = +1%, incorrect = -1%, scaled by position size
        day_return = position_size * (1.0 if predicted_class == actual else -1.0)
        returns.append(day_return)
        
        # Update performance metrics
        # In a real system, this would come from the backtest engine
        metrics = {}
        for model in model_names:
            model_predicted = 1 if day_predictions[model] > 0.5 else 0
            accuracy = 1.0 if model_predicted == actual else 0.0
            
            metrics[model] = {
                'accuracy': accuracy,
                'returns': accuracy * 2 - 1  # Convert to -1 or 1
            }
        
        # Update ensemble manager
        ensemble_manager.update_performance(
            day_predictions,
            prediction,
            np.array([actual]),
            metrics
        )
        
        # Handle regime transitions
        if ensemble_manager.in_transition:
            # In a real system, this would be called with the actual transition progress
            transition_progress = 0.5  # Simplified for this example
            ensemble_manager.handle_regime_transition(transition_progress)
    
    # Calculate cumulative returns
    cumulative_returns = np.cumsum(returns)
    
    # Plot results
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Cumulative Returns
    plt.subplot(3, 1, 1)
    plt.plot(cumulative_returns)
    plt.title('Cumulative Returns')
    plt.grid(alpha=0.3)
    
    # Plot 2: Confidence and Position Sizing
    plt.subplot(3, 1, 2)
    plt.plot(confidences, label='Confidence')
    plt.plot(position_sizes, label='Position Size')
    plt.title('Prediction Confidence and Position Sizing')
    plt.legend()
    plt.grid(alpha=0.3)
    
    # Plot 3: Detected Regimes
    plt.subplot(3, 1, 3)
    regime_ids = [int(r.split('_')[1]) for r in regimes]
    plt.plot(regime_ids)
    plt.title('Detected Market Regimes')
    plt.yticks([0, 1, 2], ['Regime 0', 'Regime 1', 'Regime 2'])
    plt.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('ensemble_simulation_results.png')
    print(f"Results saved to ensemble_simulation_results.png")
    
    # Save the ensemble state
    state_file = ensemble_manager.save_state()
    print(f"Ensemble state saved to {state_file}")
    
    # Get and print summary
    summary = ensemble_manager.get_summary()
    print("\nEnsemble Manager Summary:")
    for key, value in summary.items():
        if key not in ["model_weights", "performance_summary"]:
            print(f"  {key}: {value}")
    
    # Get feature importance
    if hasattr(ensemble_manager.regime_manager, 'get_feature_importance'):
        feature_imp = ensemble_manager.regime_manager.get_feature_importance()
        print("\nFeature Importance for Regime Detection:")
        for feature, importance in feature_imp.items():
            print(f"  {feature}: {importance:.4f}")
    
    return ensemble_manager, mock_data

if __name__ == "__main__":
    print("Starting Enhanced Ensemble Manager Example...")
    manager, data = run_simulation()
    print("Simulation complete.") 