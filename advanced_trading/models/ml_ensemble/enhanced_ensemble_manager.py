"""
Enhanced Ensemble Manager
------------------------
This module integrates the regime detection capabilities and confidence-based diversity
management into a unified ensemble learning framework for trading.

The EnhancedEnsembleManager provides a comprehensive solution for:
1. Automatic regime detection and regime-specific model selection
2. Confidence scoring and calibration of predictions
3. Model diversity optimization and redundancy elimination
4. Adaptive position sizing based on prediction confidence
5. Continuous learning and adaptation to market conditions
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
import logging
import os
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Import the component managers
from instinct_ai.advanced_trading.models.ml_ensemble.regime_enhanced_manager import RegimeEnhancedManager
from instinct_ai.advanced_trading.models.ml_ensemble.confidence_diversity_manager import ConfidenceDiversityManager

# Get the logger
logger = logging.getLogger(__name__)

class EnhancedEnsembleManager:
    """
    Advanced ensemble manager that integrates regime detection with confidence scoring
    and model diversity optimization.
    
    This manager provides a comprehensive framework for adaptive trading strategies
    that can detect market regimes, optimize model selection, score prediction confidence,
    and dynamically adjust position sizing.
    
    Parameters:
    -----------
    base_models : List[str]
        List of base model names to be used in the ensemble
    n_regimes : int
        Number of market regimes to detect
    regime_features : List[str]
        Features to use for regime detection
    confidence_method : str
        Method for confidence calculation ('entropy', 'agreement', 'calibration')
    diversity_method : str
        Method for diversity tracking ('correlation', 'mutual_info', 'clustering')
    detection_method : str
        Method for regime detection ('kmeans', 'gmm', 'threshold')
    min_confidence_threshold : float
        Minimum confidence required for trading decisions
    online_learning_rate : float
        Learning rate for online updates
    model_save_path : str
        Path to save model states
    """
    
    def __init__(
        self,
        base_models: List[str],
        n_regimes: int = 3,
        regime_features: Optional[List[str]] = None,
        confidence_method: str = 'agreement',
        diversity_method: str = 'correlation',
        detection_method: str = 'kmeans',
        min_confidence_threshold: float = 0.65,
        online_learning_rate: float = 0.05,
        model_save_path: str = 'models/ensemble_state'
    ):
        self.base_models = base_models
        self.n_regimes = n_regimes
        self.model_save_path = model_save_path
        
        # Initialize regime manager
        self.regime_manager = RegimeEnhancedManager(
            n_regimes=n_regimes,
            regime_features=regime_features,
            detection_method=detection_method,
            transition_window=5,
            min_regime_duration=10,
            regime_memory=100
        )
        
        # Initialize confidence and diversity manager
        self.confidence_manager = ConfidenceDiversityManager(
            confidence_method=confidence_method,
            diversity_method=diversity_method,
            min_confidence_threshold=min_confidence_threshold,
            online_learning_rate=online_learning_rate,
            prediction_memory=100
        )
        
        # Track current state
        self.current_regime = None
        self.current_models = base_models
        self.model_weights = {model: 1.0/len(base_models) for model in base_models}
        self.in_transition = False
        self.transition_weights = None
        
        # Performance tracking
        self.regime_performance = {f"regime_{i}": {} for i in range(n_regimes)}
        self.overall_performance = {}
        self.model_metrics = {model: {"accuracy": [], "sharpe": [], "returns": []} for model in base_models}
        
        # Prediction storage
        self.last_predictions = None
        self.last_confidence = None
        self.last_position_size = None
        
        # Create save directory if it doesn't exist
        os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
    
    def detect_regime(self, X: pd.DataFrame) -> str:
        """
        Detect the current market regime based on features
        
        Parameters:
        -----------
        X : pd.DataFrame
            Feature data for regime detection
            
        Returns:
        --------
        str
            Detected regime name
        """
        # Use regime manager to detect regime
        regime_id = self.regime_manager.detect_regime(X)
        self.current_regime = f"regime_{regime_id}"
        
        # Check if we're in a transition
        self.in_transition = self.regime_manager.is_transition()
        
        # Log regime detection
        if self.in_transition:
            current_to_next = self.regime_manager.predict_next_regime()
            logger.info(f"In transition from {self.current_regime} to predicted {current_to_next}")
        else:
            logger.info(f"Current regime: {self.current_regime}")
        
        return self.current_regime
    
    def select_models(
        self,
        model_performance: Optional[Dict[str, float]] = None
    ) -> List[str]:
        """
        Select appropriate models based on the current regime and diversity
        
        Parameters:
        -----------
        model_performance : Optional[Dict[str, float]]
            Performance metric for each model
            
        Returns:
        --------
        List[str]
            Selected model names
        """
        if model_performance is None:
            if self.current_regime and self.current_regime in self.regime_performance:
                # Use regime-specific performance if available
                model_performance = self.regime_performance[self.current_regime]
            else:
                # Fall back to overall performance
                model_performance = self.overall_performance
            
            # If still no performance data, use equal weights
            if not model_performance:
                model_performance = {model: 1.0 for model in self.base_models}
        
        if self.in_transition:
            # Get models for current and predicted next regime
            current_models = self.regime_manager.get_regime_models(self.current_regime, model_performance)
            next_regime = self.regime_manager.predict_next_regime()
            next_models = self.regime_manager.get_regime_models(next_regime, model_performance)
            
            # Combine and remove duplicates
            selected_models = list(set(current_models + next_models))
        else:
            # Get models for current regime
            regime_models = self.regime_manager.get_regime_models(self.current_regime, model_performance)
            
            # Apply diversity-based selection
            if len(regime_models) > 3 and self.last_predictions is not None:
                # Filter predictions to only include regime models
                regime_predictions = {model: preds for model, preds in self.last_predictions.items() 
                                     if model in regime_models}
                
                # Calculate diversity and select diverse subset
                self.confidence_manager.calculate_model_diversity(regime_predictions)
                selected_models = self.confidence_manager.select_diverse_models(
                    model_performance, max_models=min(5, len(regime_models))
                )
            else:
                selected_models = regime_models
        
        if not selected_models:
            # Fallback to base models if no models selected
            logger.warning("No models selected, falling back to base models")
            selected_models = self.base_models
        
        # Update current models
        self.current_models = selected_models
        
        return selected_models
    
    def get_model_weights(self) -> Dict[str, float]:
        """
        Get weights for the selected models
        
        Returns:
        --------
        Dict[str, float]
            Model weights
        """
        if self.in_transition and self.transition_weights is not None:
            # Use transition weights
            return self.transition_weights
        
        if self.current_regime and self.current_regime in self.regime_performance:
            # Get regime-specific weights
            weights = self.regime_manager.get_regime_model_weights(
                self.current_regime,
                self.current_models,
                self.regime_performance[self.current_regime]
            )
        else:
            # Equal weights if no regime-specific performance
            weights = {model: 1.0/len(self.current_models) for model in self.current_models}
        
        # Store current weights
        self.model_weights = weights
        
        return weights
    
    def predict(
        self,
        model_predictions: Dict[str, np.ndarray],
        X: Optional[pd.DataFrame] = None
    ) -> Tuple[np.ndarray, float, float]:
        """
        Generate final prediction with confidence score and position sizing
        
        Parameters:
        -----------
        model_predictions : Dict[str, np.ndarray]
            Predictions from each model
        X : Optional[pd.DataFrame]
            Feature data for confidence calculation
            
        Returns:
        --------
        Tuple[np.ndarray, float, float]
            (final_prediction, confidence_score, position_size)
        """
        # Store predictions
        self.last_predictions = model_predictions
        
        # Filter to only use selected models
        selected_predictions = {model: preds for model, preds in model_predictions.items() 
                              if model in self.current_models}
        
        if not selected_predictions:
            logger.error("No predictions available for selected models")
            # Fallback to all available predictions
            selected_predictions = model_predictions
        
        # Get model weights
        weights = self.get_model_weights()
        
        # Calculate weighted prediction
        weighted_preds = np.zeros_like(next(iter(selected_predictions.values())))
        weight_sum = 0
        
        for model, preds in selected_predictions.items():
            if model in weights:
                model_weight = weights[model]
                weighted_preds += preds * model_weight
                weight_sum += model_weight
        
        # Normalize if weights don't sum to 1
        if weight_sum > 0 and weight_sum != 1.0:
            weighted_preds /= weight_sum
        
        # Calculate confidence score
        confidence = self.confidence_manager.calculate_prediction_confidence(
            selected_predictions, weights
        )
        
        # Calculate mean confidence
        mean_confidence = float(np.mean(confidence))
        self.last_confidence = mean_confidence
        
        # Get position sizing multiplier
        position_size = self.confidence_manager.get_position_sizing_multiplier(
            mean_confidence, self.current_regime
        )
        self.last_position_size = position_size
        
        # Log prediction info
        logger.info(f"Prediction confidence: {mean_confidence:.4f}, Position size: {position_size:.4f}")
        
        return weighted_preds, mean_confidence, position_size
    
    def update_performance(
        self,
        model_predictions: Dict[str, np.ndarray],
        ensemble_prediction: np.ndarray,
        actual_values: np.ndarray,
        metrics: Dict[str, Dict[str, float]]
    ) -> None:
        """
        Update performance metrics for models and regimes
        
        Parameters:
        -----------
        model_predictions : Dict[str, np.ndarray]
            Predictions from each model
        ensemble_prediction : np.ndarray
            Final ensemble prediction
        actual_values : np.ndarray
            Actual target values
        metrics : Dict[str, Dict[str, float]]
            Performance metrics for each model
        """
        # Update calibration data
        if self.last_confidence is not None:
            self.confidence_manager.update_calibration(
                np.array([self.last_confidence]), 
                ensemble_prediction, 
                actual_values
            )
        
        # Update overall performance
        for model, model_metrics in metrics.items():
            if model not in self.overall_performance:
                self.overall_performance[model] = {}
            
            # Update overall metrics
            for metric_name, metric_value in model_metrics.items():
                if metric_name not in self.overall_performance[model]:
                    self.overall_performance[model][metric_name] = []
                
                self.overall_performance[model][metric_name].append(metric_value)
                
                # Keep only recent history (last 100)
                if len(self.overall_performance[model][metric_name]) > 100:
                    self.overall_performance[model][metric_name] = self.overall_performance[model][metric_name][-100:]
        
        # Update regime-specific performance if a regime is detected
        if self.current_regime:
            if self.current_regime not in self.regime_performance:
                self.regime_performance[self.current_regime] = {}
            
            # Update regime-specific metrics
            for model, model_metrics in metrics.items():
                if model not in self.regime_performance[self.current_regime]:
                    self.regime_performance[self.current_regime][model] = {}
                
                for metric_name, metric_value in model_metrics.items():
                    if metric_name not in self.regime_performance[self.current_regime][model]:
                        self.regime_performance[self.current_regime][model][metric_name] = []
                    
                    self.regime_performance[self.current_regime][model][metric_name].append(metric_value)
                    
                    # Keep only recent history (last 50)
                    if len(self.regime_performance[self.current_regime][model][metric_name]) > 50:
                        self.regime_performance[self.current_regime][model][metric_name] = \
                            self.regime_performance[self.current_regime][model][metric_name][-50:]
        
        # Update regime manager with performance
        if self.current_regime:
            # Calculate mean performance for each model (using Sharpe ratio if available)
            mean_performance = {}
            for model, model_metrics in metrics.items():
                if 'sharpe' in model_metrics:
                    mean_performance[model] = model_metrics['sharpe']
                elif 'returns' in model_metrics:
                    mean_performance[model] = model_metrics['returns']
                elif 'accuracy' in model_metrics:
                    mean_performance[model] = model_metrics['accuracy']
                else:
                    # Use first available metric
                    first_metric = next(iter(model_metrics.values()))
                    mean_performance[model] = first_metric
            
            # Update regime model weights
            self.regime_manager.update_regime_model_weights(
                self.current_regime, mean_performance
            )
        
        # Apply online learning updates
        learning_adjustments = self.confidence_manager.online_update(
            model_predictions, ensemble_prediction, actual_values
        )
        
        # Log performance update
        logger.info(f"Updated performance for {len(metrics)} models")
    
    def handle_regime_transition(self, transition_progress: float) -> None:
        """
        Handle smooth transition between regimes
        
        Parameters:
        -----------
        transition_progress : float
            Progress of transition (0-1)
        """
        if not self.in_transition:
            logger.warning("handle_regime_transition called but not in transition state")
            return
        
        # Get current and next regime
        current_regime = self.current_regime
        next_regime = self.regime_manager.predict_next_regime()
        
        # Get weights for both regimes
        current_weights = self.regime_manager.get_regime_model_weights(
            current_regime, self.current_models,
            self.regime_performance.get(current_regime, {})
        )
        
        next_weights = self.regime_manager.get_regime_model_weights(
            next_regime, self.current_models,
            self.regime_performance.get(next_regime, {})
        )
        
        # Initialize transition weights
        self.transition_weights = {}
        
        # Interpolate weights
        all_models = set(list(current_weights.keys()) + list(next_weights.keys()))
        
        for model in all_models:
            current_w = current_weights.get(model, 0.0)
            next_w = next_weights.get(model, 0.0)
            
            # Linear interpolation
            self.transition_weights[model] = current_w * (1 - transition_progress) + next_w * transition_progress
        
        # Normalize weights
        weight_sum = sum(self.transition_weights.values())
        if weight_sum > 0:
            self.transition_weights = {model: w/weight_sum for model, w in self.transition_weights.items()}
        
        logger.info(f"Transition progress: {transition_progress:.2f} from {current_regime} to {next_regime}")
    
    def save_state(self, filename: Optional[str] = None) -> str:
        """
        Save the current state of the ensemble manager
        
        Parameters:
        -----------
        filename : Optional[str]
            Custom filename to save state
            
        Returns:
        --------
        str
            Path to the saved state file
        """
        if filename is None:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.model_save_path}_{timestamp}.pkl"
        else:
            # Use provided filename
            filename = f"{self.model_save_path}_{filename}.pkl"
        
        # Prepare state dictionary
        state = {
            'current_regime': self.current_regime,
            'current_models': self.current_models,
            'model_weights': self.model_weights,
            'regime_performance': self.regime_performance,
            'overall_performance': self.overall_performance,
            'regime_manager_state': self.regime_manager.get_state(),
            'confidence_manager_state': {
                'confidence_method': self.confidence_manager.confidence_method,
                'diversity_method': self.confidence_manager.diversity_method,
                'min_confidence_threshold': self.confidence_manager.min_confidence_threshold,
                'calibration_data': self.confidence_manager.calibration_data,
                'model_diversity_matrix': self.confidence_manager.model_diversity_matrix,
                'model_clusters': self.confidence_manager.model_clusters,
                'position_size_multipliers': self.confidence_manager.position_size_multipliers
            }
        }
        
        # Save state
        with open(filename, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"Ensemble state saved to {filename}")
        return filename
    
    def load_state(self, filename: str) -> bool:
        """
        Load a saved state
        
        Parameters:
        -----------
        filename : str
            Path to the saved state file
            
        Returns:
        --------
        bool
            Success or failure
        """
        try:
            with open(filename, 'rb') as f:
                state = pickle.load(f)
            
            # Restore state
            self.current_regime = state['current_regime']
            self.current_models = state['current_models']
            self.model_weights = state['model_weights']
            self.regime_performance = state['regime_performance']
            self.overall_performance = state['overall_performance']
            
            # Restore regime manager state
            if 'regime_manager_state' in state:
                self.regime_manager.set_state(state['regime_manager_state'])
            
            # Restore confidence manager state
            if 'confidence_manager_state' in state:
                conf_state = state['confidence_manager_state']
                self.confidence_manager.confidence_method = conf_state['confidence_method']
                self.confidence_manager.diversity_method = conf_state['diversity_method']
                self.confidence_manager.min_confidence_threshold = conf_state['min_confidence_threshold']
                self.confidence_manager.calibration_data = conf_state['calibration_data']
                self.confidence_manager.model_diversity_matrix = conf_state['model_diversity_matrix']
                self.confidence_manager.model_clusters = conf_state['model_clusters']
                self.confidence_manager.position_size_multipliers = conf_state['position_size_multipliers']
            
            logger.info(f"Ensemble state loaded from {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to load ensemble state: {str(e)}")
            return False
    
    def visualize_regime_history(self) -> None:
        """
        Visualize the history of detected regimes
        """
        # Use regime manager to visualize regime history
        self.regime_manager.visualize_regimes()
    
    def visualize_model_performance(self, regime: Optional[str] = None) -> None:
        """
        Visualize model performance, overall or by regime
        
        Parameters:
        -----------
        regime : Optional[str]
            Specific regime to visualize (None for overall)
        """
        if regime is not None and regime in self.regime_performance:
            performance_data = self.regime_performance[regime]
            title = f"Model Performance for {regime}"
        else:
            performance_data = self.overall_performance
            title = "Overall Model Performance"
        
        if not performance_data:
            logger.warning(f"No performance data available for {title}")
            return
        
        # Extract metrics for visualization
        metrics = set()
        for model_metrics in performance_data.values():
            metrics.update(model_metrics.keys())
        
        # Set up plot grid
        n_metrics = len(metrics)
        if n_metrics == 0:
            return
        
        n_cols = min(2, n_metrics)
        n_rows = (n_metrics + 1) // 2
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 4 * n_rows))
        if n_metrics == 1:
            axes = np.array([axes])
        
        # Plot each metric
        for i, metric in enumerate(sorted(metrics)):
            row = i // n_cols
            col = i % n_cols
            ax = axes[row, col] if n_rows > 1 else axes[col]
            
            # Gather data for this metric
            metric_data = {}
            for model, model_metrics in performance_data.items():
                if metric in model_metrics and model_metrics[metric]:
                    metric_data[model] = model_metrics[metric]
            
            if metric_data:
                # Create DataFrame
                df = pd.DataFrame(metric_data)
                
                # Plot
                df.plot(ax=ax)
                ax.set_title(f"{metric.capitalize()} over time")
                ax.set_xlabel("Update")
                ax.set_ylabel(metric.capitalize())
                ax.legend(title="Model")
                ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.suptitle(title, fontsize=16)
        plt.subplots_adjust(top=0.9)
        plt.show()
    
    def visualize_confidence_metrics(self) -> None:
        """
        Visualize confidence-related metrics
        """
        # Visualize confidence distribution
        self.confidence_manager.visualize_confidence_distribution()
        
        # Visualize calibration curve
        self.confidence_manager.visualize_calibration_curve()
        
        # Visualize position sizing function
        self.confidence_manager.visualize_position_sizing()
    
    def visualize_model_diversity(self) -> None:
        """
        Visualize model diversity
        """
        # Visualize diversity matrix
        self.confidence_manager.visualize_model_diversity()
        
        # Visualize model clusters
        self.confidence_manager.visualize_model_clusters()
        
        # Visualize error trends
        self.confidence_manager.visualize_error_trends()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current ensemble state
        
        Returns:
        --------
        Dict[str, Any]
            Summary information
        """
        summary = {
            "current_regime": self.current_regime,
            "in_transition": self.in_transition,
            "selected_models": self.current_models,
            "model_weights": self.model_weights,
            "last_confidence": self.last_confidence,
            "last_position_size": self.last_position_size,
        }
        
        # Add regime information
        if hasattr(self.regime_manager, 'regime_history') and self.regime_manager.regime_history:
            regime_counts = {}
            for regime in self.regime_manager.regime_history:
                if regime not in regime_counts:
                    regime_counts[regime] = 0
                regime_counts[regime] += 1
            
            summary["regime_distribution"] = regime_counts
        
        # Add performance summary
        if self.overall_performance:
            # Calculate average performance for each model and metric
            performance_summary = {}
            for model, metrics in self.overall_performance.items():
                performance_summary[model] = {}
                for metric_name, values in metrics.items():
                    if values:
                        performance_summary[model][metric_name] = np.mean(values)
            
            summary["performance_summary"] = performance_summary
        
        return summary 