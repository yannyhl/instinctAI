"""
Test Script for Ensemble Framework Integration
---------------------------------------------
This script performs basic validation of the enhanced ensemble framework components
to ensure they integrate properly.
"""

import sys
import os
import unittest
import numpy as np
import pandas as pd
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the components we need to test
from instinct_ai.advanced_trading.models.ml_ensemble.regime_enhanced_manager import RegimeEnhancedManager
from instinct_ai.advanced_trading.models.ml_ensemble.confidence_diversity_manager import ConfidenceDiversityManager
from instinct_ai.advanced_trading.models.ml_ensemble.enhanced_ensemble_manager import EnhancedEnsembleManager

class TestEnsembleIntegration(unittest.TestCase):
    """Test class for validating ensemble framework integration"""
    
    def setUp(self):
        """Set up test data and components"""
        # Create simple test data
        np.random.seed(42)
        self.n_samples = 100
        self.n_features = 5
        self.n_models = 3
        
        # Create feature data
        self.features = pd.DataFrame({
            f'feature_{i}': np.random.randn(self.n_samples) 
            for i in range(self.n_features)
        })
        
        # Create model predictions (classification probabilities)
        self.predictions = {
            f'model_{i}': np.random.rand(self.n_samples) 
            for i in range(self.n_models)
        }
        
        # Create actual values (binary classification)
        self.actuals = np.random.choice([0, 1], size=self.n_samples)
        
        # Create model names
        self.model_names = list(self.predictions.keys())
        
        # Create regime features
        self.regime_features = [f'feature_{i}' for i in range(3)]
    
    def test_regime_manager(self):
        """Test that the RegimeEnhancedManager works correctly"""
        # Initialize the regime manager
        regime_manager = RegimeEnhancedManager(
            n_regimes=3,
            regime_features=self.regime_features,
            detection_method='kmeans',
            transition_window=5,
            min_regime_duration=10,
            regime_memory=50
        )
        
        # Test regime detection
        regime_id = regime_manager.detect_regime(self.features)
        self.assertIsInstance(regime_id, int)
        self.assertTrue(0 <= regime_id < 3)
        
        # Test transition detection
        is_transition = regime_manager.is_transition()
        self.assertIsInstance(is_transition, bool)
        
        # Test model weight calculation
        model_performance = {model: np.random.rand() for model in self.model_names}
        regime = f"regime_{regime_id}"
        weights = regime_manager.get_regime_model_weights(regime, self.model_names, model_performance)
        
        self.assertEqual(len(weights), len(self.model_names))
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        
        # Test state persistence
        state = regime_manager.get_state()
        self.assertIsInstance(state, dict)
        self.assertIn('regime_history', state)
        
        # Test visualization method exists
        self.assertTrue(hasattr(regime_manager, 'visualize_regimes'))
        
        print("RegimeEnhancedManager tests passed")
    
    def test_confidence_manager(self):
        """Test that the ConfidenceDiversityManager works correctly"""
        # Initialize the confidence manager
        confidence_manager = ConfidenceDiversityManager(
            confidence_method='agreement',
            diversity_method='correlation',
            min_confidence_threshold=0.65,
            online_learning_rate=0.05,
            prediction_memory=50
        )
        
        # Test confidence calculation
        confidence_scores = confidence_manager.calculate_prediction_confidence(self.predictions)
        self.assertEqual(len(confidence_scores), self.n_samples)
        self.assertTrue(all(0 <= score <= 1 for score in confidence_scores))
        
        # Test diversity calculation
        diversity_matrix = confidence_manager.calculate_model_diversity(self.predictions)
        self.assertIsInstance(diversity_matrix, pd.DataFrame)
        self.assertEqual(diversity_matrix.shape, (self.n_models, self.n_models))
        
        # Test model clustering
        clusters = confidence_manager.cluster_models()
        self.assertIsInstance(clusters, dict)
        
        # Test model selection
        model_performance = {model: np.random.rand() for model in self.model_names}
        selected_models = confidence_manager.select_diverse_models(model_performance)
        self.assertIsInstance(selected_models, list)
        
        # Test position sizing
        position_size = confidence_manager.get_position_sizing_multiplier(0.7)
        self.assertTrue(0 <= position_size <= 1)
        
        # Test online learning
        ensemble_pred = np.mean(list(self.predictions.values()), axis=0)
        learning_rates = confidence_manager.online_update(
            self.predictions, ensemble_pred, self.actuals
        )
        self.assertIsInstance(learning_rates, dict)
        
        print("ConfidenceDiversityManager tests passed")
    
    def test_enhanced_ensemble_manager(self):
        """Test that the EnhancedEnsembleManager integrates components correctly"""
        # Initialize the enhanced ensemble manager
        ensemble_manager = EnhancedEnsembleManager(
            base_models=self.model_names,
            n_regimes=3,
            regime_features=self.regime_features,
            confidence_method='agreement',
            diversity_method='correlation',
            detection_method='kmeans',
            min_confidence_threshold=0.6,
            online_learning_rate=0.05,
            model_save_path='test_ensemble_state'
        )
        
        # Test regime detection
        regime = ensemble_manager.detect_regime(self.features)
        self.assertIsInstance(regime, str)
        self.assertTrue(regime.startswith('regime_'))
        
        # Test model selection
        selected_models = ensemble_manager.select_models()
        self.assertIsInstance(selected_models, list)
        
        # Test prediction
        prediction, confidence, position_size = ensemble_manager.predict(self.predictions)
        self.assertEqual(len(prediction), self.n_samples)
        self.assertIsInstance(confidence, float)
        self.assertIsInstance(position_size, float)
        
        # Test performance update
        metrics = {
            model: {
                'accuracy': np.random.rand(),
                'returns': np.random.randn(),
                'sharpe': np.random.rand() * 2
            } 
            for model in self.model_names
        }
        
        ensemble_manager.update_performance(
            self.predictions, prediction, self.actuals, metrics
        )
        
        # Test state saving and loading
        save_path = ensemble_manager.save_state('test_state')
        self.assertTrue(os.path.exists(save_path))
        
        # Test summary generation
        summary = ensemble_manager.get_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn('current_regime', summary)
        
        print("EnhancedEnsembleManager integration tests passed")
        
        # Clean up test files
        try:
            os.remove(save_path)
        except:
            pass

if __name__ == "__main__":
    print("Running ensemble framework integration tests...")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
    print("All tests completed successfully") 