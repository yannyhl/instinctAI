"""
Confidence and Diversity Manager
------------------------------
Extends ensemble learning with sophisticated confidence scoring, 
model diversity tracking, and adaptive position sizing based on prediction confidence.

This module provides:
1. Multiple methods for assessing prediction confidence
2. Model diversity tracking and optimization
3. Online learning capabilities for continuous adaptation
4. Confidence-based position sizing integration
5. Dynamic ensemble pruning for optimal model combination
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mutual_info_score, pairwise_distances
from scipy.stats import entropy, kurtosis, skew
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
import warnings

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Get the logger
logger = logging.getLogger(__name__)

class ConfidenceDiversityManager:
    """
    Manages prediction confidence scoring and model diversity in ensemble learning.
    
    This class provides:
    - Multiple methods for measuring prediction confidence
    - Model diversity tracking and correlation management
    - Online learning and continuous adaptation
    - Adaptive position sizing based on prediction confidence
    - Dynamic model pruning for optimal ensembles
    
    Parameters:
    -----------
    confidence_method : str
        Method for confidence calculation ('entropy', 'agreement', 'calibration')
    diversity_method : str
        Method for diversity tracking ('correlation', 'mutual_info', 'clustering')
    min_confidence_threshold : float
        Minimum confidence required for trading decisions
    online_learning_rate : float
        Rate for online learning updates
    prediction_memory : int
        Number of recent predictions to store for analysis
    """
    
    def __init__(
        self,
        confidence_method: str = 'agreement',
        diversity_method: str = 'correlation',
        min_confidence_threshold: float = 0.65,
        online_learning_rate: float = 0.05,
        prediction_memory: int = 100
    ):
        self.confidence_method = confidence_method
        self.diversity_method = diversity_method
        self.min_confidence_threshold = min_confidence_threshold
        self.online_learning_rate = online_learning_rate
        self.prediction_memory = prediction_memory
        
        # Prediction history for tracking
        self.prediction_history = {}
        self.target_history = []
        self.confidence_history = []
        
        # Diversity metrics
        self.model_diversity_matrix = None
        self.model_clusters = None
        
        # Calibration data
        self.confidence_bins = np.linspace(0, 1, 11)  # 10 bins from 0 to 1
        self.calibration_data = {bin_idx: {'pred': [], 'actual': []} 
                                for bin_idx in range(len(self.confidence_bins)-1)}
        
        # Online learning data
        self.recent_errors = {}
        self.error_trends = {}
        
        # Position sizing recommendations
        self.position_size_multipliers = {}
        
        # Model pruning data
        self.model_redundancy = {}
        self.selected_models = []
    
    def calculate_prediction_confidence(
        self,
        predictions: Dict[str, np.ndarray],
        weights: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """
        Calculate confidence scores for ensemble predictions
        
        Parameters:
        -----------
        predictions : Dict[str, np.ndarray]
            Dictionary of predictions from each model
        weights : Optional[Dict[str, float]]
            Model weights (if None, equal weights are used)
            
        Returns:
        --------
        np.ndarray
            Confidence score for each prediction
        """
        if not predictions:
            logger.warning("No predictions provided to calculate confidence")
            return np.array([])
        
        # Convert predictions to a matrix
        pred_values = np.array(list(predictions.values()))
        
        # Store prediction history
        for model_name, preds in predictions.items():
            if model_name not in self.prediction_history:
                self.prediction_history[model_name] = []
            
            # Store the most recent predictions
            self.prediction_history[model_name].append(preds)
            
            # Keep only recent history
            if len(self.prediction_history[model_name]) > self.prediction_memory:
                self.prediction_history[model_name] = self.prediction_history[model_name][-self.prediction_memory:]
        
        # Calculate confidence based on chosen method
        if self.confidence_method == 'entropy':
            return self._confidence_from_entropy(pred_values)
        elif self.confidence_method == 'agreement':
            return self._confidence_from_agreement(pred_values, weights)
        elif self.confidence_method == 'calibration':
            return self._confidence_from_calibration(pred_values, weights)
        else:
            logger.warning(f"Unknown confidence method: {self.confidence_method}")
            return self._confidence_from_agreement(pred_values, weights)
    
    def _confidence_from_entropy(self, predictions: np.ndarray) -> np.ndarray:
        """
        Calculate confidence based on entropy of predictions
        
        Lower entropy (high agreement) = higher confidence
        
        Parameters:
        -----------
        predictions : np.ndarray
            Array of predictions from multiple models
            
        Returns:
        --------
        np.ndarray
            Confidence scores
        """
        # For classification tasks with probability predictions
        if (predictions >= 0).all() and (predictions <= 1).all():
            # Transpose to get prediction distributions across models for each sample
            pred_dist = predictions.T
            
            # Calculate entropy for each sample's prediction distribution
            entropies = np.array([entropy([p, 1-p]) for p in pred_dist.mean(axis=1)])
            
            # Normalize to 0-1 range (max entropy is 1.0 for a binary variable)
            # Convert entropy to confidence (lower entropy = higher confidence)
            confidence = 1 - entropies
            
            return confidence
        else:
            # For regression tasks, use standard deviation as a proxy for entropy
            # Lower standard deviation = higher confidence
            std_devs = predictions.std(axis=0)
            max_std = max(std_devs.max(), 1e-10)  # Avoid division by zero
            
            # Convert std to confidence score (inverted and normalized)
            confidence = 1 - (std_devs / max_std)
            
            return confidence
    
    def _confidence_from_agreement(
        self, 
        predictions: np.ndarray,
        weights: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """
        Calculate confidence based on model agreement
        
        Higher agreement = higher confidence
        
        Parameters:
        -----------
        predictions : np.ndarray
            Array of predictions from multiple models
        weights : Optional[Dict[str, float]]
            Model weights
            
        Returns:
        --------
        np.ndarray
            Confidence scores
        """
        num_models, num_samples = predictions.shape
        
        # For weighted agreement calculation
        if weights is not None:
            # Ensure weights array matches models
            weight_values = np.array([weights.get(i, 1.0) for i in range(num_models)])
            weight_values = weight_values / weight_values.sum()  # Normalize
        else:
            weight_values = np.ones(num_models) / num_models
        
        confidence_scores = np.zeros(num_samples)
        
        # For classification tasks (predictions are probabilities)
        if (predictions >= 0).all() and (predictions <= 1).all():
            # Calculate weighted mean of probabilities
            weighted_mean = np.sum(predictions * weight_values[:, np.newaxis], axis=0)
            
            # Calculate confidence as distance from 0.5 (uncertain prediction)
            confidence_scores = 2 * np.abs(weighted_mean - 0.5)
        else:
            # For regression tasks, calculate agreement differently
            # Normalize predictions to 0-1 range within each sample
            min_vals = predictions.min(axis=0)
            max_vals = predictions.max(axis=0)
            range_vals = max_vals - min_vals
            range_vals = np.where(range_vals > 0, range_vals, 1.0)  # Avoid division by zero
            
            normalized_preds = (predictions - min_vals) / range_vals
            
            # Calculate mean squared deviation from mean prediction
            mean_preds = np.sum(normalized_preds * weight_values[:, np.newaxis], axis=0)
            squared_devs = (normalized_preds - mean_preds) ** 2
            weighted_mean_squared_dev = np.sum(squared_devs * weight_values[:, np.newaxis], axis=0)
            
            # Convert to confidence score (lower deviation = higher confidence)
            confidence_scores = 1 - np.sqrt(weighted_mean_squared_dev)
        
        return confidence_scores
    
    def _confidence_from_calibration(
        self, 
        predictions: np.ndarray,
        weights: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """
        Calculate confidence based on model calibration data
        
        Uses historical calibration to adjust confidence
        
        Parameters:
        -----------
        predictions : np.ndarray
            Array of predictions from multiple models
        weights : Optional[Dict[str, float]]
            Model weights
            
        Returns:
        --------
        np.ndarray
            Calibrated confidence scores
        """
        # First get base agreement confidence
        base_confidence = self._confidence_from_agreement(predictions, weights)
        
        # If we have enough calibration data, adjust confidence
        if sum(len(data['pred']) for data in self.calibration_data.values()) >= 100:
            calibrated_confidence = np.zeros_like(base_confidence)
            
            # For each prediction, find its confidence bin and calculate calibrated confidence
            for i, conf in enumerate(base_confidence):
                # Find the appropriate confidence bin
                bin_idx = np.digitize(conf, self.confidence_bins) - 1
                bin_idx = min(bin_idx, len(self.confidence_bins) - 2)  # Ensure valid index
                
                bin_data = self.calibration_data[bin_idx]
                
                if bin_data['pred']:
                    # Calculate empirical accuracy for this confidence bin
                    empirical_accuracy = np.mean(bin_data['actual'])
                    
                    # Mix original confidence with empirical accuracy
                    calibrated_confidence[i] = 0.5 * conf + 0.5 * empirical_accuracy
                else:
                    calibrated_confidence[i] = conf
            
            return calibrated_confidence
        else:
            # Not enough calibration data yet, return base confidence
            return base_confidence
    
    def update_calibration(
        self,
        confidence_scores: np.ndarray,
        predictions: np.ndarray,
        actual_values: np.ndarray
    ) -> None:
        """
        Update calibration data with new predictions and actual outcomes
        
        Parameters:
        -----------
        confidence_scores : np.ndarray
            Confidence scores for each prediction
        predictions : np.ndarray
            Final predictions from the ensemble
        actual_values : np.ndarray
            Actual target values
        """
        # For binary classification
        if set(np.unique(actual_values)) <= {0, 1}:
            for i, conf in enumerate(confidence_scores):
                # Find the appropriate confidence bin
                bin_idx = np.digitize(conf, self.confidence_bins) - 1
                bin_idx = min(bin_idx, len(self.confidence_bins) - 2)  # Ensure valid index
                
                # Store prediction and actual outcome
                self.calibration_data[bin_idx]['pred'].append(predictions[i])
                self.calibration_data[bin_idx]['actual'].append(
                    1.0 if (predictions[i] > 0.5 and actual_values[i] == 1) or
                           (predictions[i] <= 0.5 and actual_values[i] == 0) else 0.0
                )
                
                # Keep only recent history
                if len(self.calibration_data[bin_idx]['pred']) > self.prediction_memory:
                    self.calibration_data[bin_idx]['pred'] = self.calibration_data[bin_idx]['pred'][-self.prediction_memory:]
                    self.calibration_data[bin_idx]['actual'] = self.calibration_data[bin_idx]['actual'][-self.prediction_memory:]
        else:
            # For regression, we need a different approach
            # Calculate normalized absolute error
            errors = np.abs(predictions - actual_values)
            max_error = max(errors.max(), 1e-10)  # Avoid division by zero
            normalized_accuracy = 1 - (errors / max_error)
            
            for i, conf in enumerate(confidence_scores):
                # Find the appropriate confidence bin
                bin_idx = np.digitize(conf, self.confidence_bins) - 1
                bin_idx = min(bin_idx, len(self.confidence_bins) - 2)  # Ensure valid index
                
                # Store prediction and normalized accuracy
                self.calibration_data[bin_idx]['pred'].append(predictions[i])
                self.calibration_data[bin_idx]['actual'].append(normalized_accuracy[i])
                
                # Keep only recent history
                if len(self.calibration_data[bin_idx]['pred']) > self.prediction_memory:
                    self.calibration_data[bin_idx]['pred'] = self.calibration_data[bin_idx]['pred'][-self.prediction_memory:]
                    self.calibration_data[bin_idx]['actual'] = self.calibration_data[bin_idx]['actual'][-self.prediction_memory:]
    
    def calculate_model_diversity(
        self,
        predictions: Dict[str, np.ndarray]
    ) -> pd.DataFrame:
        """
        Calculate diversity metrics between models
        
        Parameters:
        -----------
        predictions : Dict[str, np.ndarray]
            Dictionary of predictions from each model
            
        Returns:
        --------
        pd.DataFrame
            Diversity matrix between models
        """
        if not predictions or len(predictions) < 2:
            logger.warning("Need at least 2 models to calculate diversity")
            return pd.DataFrame()
        
        model_names = list(predictions.keys())
        num_models = len(model_names)
        
        # Initialize diversity matrix
        diversity_matrix = np.zeros((num_models, num_models))
        
        # Calculate diversity based on chosen method
        if self.diversity_method == 'correlation':
            pred_matrix = np.array(list(predictions.values()))
            
            # Calculate correlation matrix
            corr_matrix = np.corrcoef(pred_matrix)
            
            # Convert correlation to diversity (1 - |corr|)
            diversity_matrix = 1 - np.abs(corr_matrix)
        
        elif self.diversity_method == 'mutual_info':
            # Calculate mutual information between each pair of models
            for i in range(num_models):
                for j in range(i+1, num_models):
                    mi = mutual_info_score(
                        (predictions[model_names[i]] > 0.5).astype(int),
                        (predictions[model_names[j]] > 0.5).astype(int)
                    )
                    
                    # Normalize and convert to diversity score
                    entropy_i = entropy([(predictions[model_names[i]] > 0.5).mean(), 
                                         (predictions[model_names[i]] <= 0.5).mean()])
                    entropy_j = entropy([(predictions[model_names[j]] > 0.5).mean(), 
                                         (predictions[model_names[j]] <= 0.5).mean()])
                    
                    max_mi = min(entropy_i, entropy_j)
                    normalized_mi = mi / max_mi if max_mi > 0 else 0
                    
                    # Higher mutual information = lower diversity
                    diversity_score = 1 - normalized_mi
                    
                    diversity_matrix[i, j] = diversity_score
                    diversity_matrix[j, i] = diversity_score
            
            # Set diagonal to 0 (no diversity with itself)
            np.fill_diagonal(diversity_matrix, 0)
            
        elif self.diversity_method == 'clustering':
            # Use hierarchical clustering on predictions to determine diversity
            pred_matrix = np.array(list(predictions.values()))
            
            # Calculate distance matrix
            distance_matrix = pairwise_distances(pred_matrix, metric='cosine')
            
            # Convert distance to diversity (higher distance = higher diversity)
            diversity_matrix = distance_matrix
        
        else:
            logger.warning(f"Unknown diversity method: {self.diversity_method}")
            return pd.DataFrame()
        
        # Store the diversity matrix
        self.model_diversity_matrix = pd.DataFrame(
            diversity_matrix,
            index=model_names,
            columns=model_names
        )
        
        return self.model_diversity_matrix
    
    def cluster_models(
        self,
        num_clusters: Optional[int] = None,
        distance_threshold: Optional[float] = 0.3
    ) -> Dict[int, List[str]]:
        """
        Cluster models based on diversity for redundancy detection
        
        Parameters:
        -----------
        num_clusters : Optional[int]
            Number of clusters to create (if None, determined automatically)
        distance_threshold : Optional[float]
            Distance threshold for clustering (lower = more clusters)
            
        Returns:
        --------
        Dict[int, List[str]]
            Clusters of models
        """
        if self.model_diversity_matrix is None or self.model_diversity_matrix.empty:
            logger.warning("Diversity matrix not available for clustering")
            return {}
        
        # Convert diversity to distance (1 - diversity)
        distance_matrix = 1 - self.model_diversity_matrix.values
        
        # Apply hierarchical clustering
        linkage_matrix = linkage(distance_matrix[np.triu_indices(len(distance_matrix), k=1)], 
                                method='average')
        
        # Determine clusters
        if num_clusters is not None:
            labels = fcluster(linkage_matrix, num_clusters, criterion='maxclust')
        else:
            labels = fcluster(linkage_matrix, distance_threshold, criterion='distance')
        
        # Organize models by cluster
        model_names = self.model_diversity_matrix.index
        clusters = {}
        
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(model_names[i])
        
        # Store model clusters
        self.model_clusters = clusters
        
        return clusters
    
    def select_diverse_models(
        self,
        model_performance: Dict[str, float],
        max_models: Optional[int] = None
    ) -> List[str]:
        """
        Select a diverse subset of models for optimal ensemble
        
        Parameters:
        -----------
        model_performance : Dict[str, float]
            Performance metric for each model
        max_models : Optional[int]
            Maximum number of models to select
            
        Returns:
        --------
        List[str]
            Selected model names
        """
        if self.model_clusters is None:
            logger.warning("No model clusters available. Clustering models first.")
            self.cluster_models()
            
            if self.model_clusters is None:
                logger.error("Could not cluster models for selection")
                return list(model_performance.keys())
        
        # Select the best-performing model from each cluster
        selected_models = []
        
        for cluster_id, cluster_models in self.model_clusters.items():
            # Filter performance to only models in this cluster
            cluster_performance = {model: model_performance.get(model, 0) 
                                 for model in cluster_models}
            
            if cluster_performance:
                # Select the best model from this cluster
                best_model = max(cluster_performance.items(), key=lambda x: x[1])[0]
                selected_models.append(best_model)
        
        # If max_models is specified, select only the top performers
        if max_models is not None and len(selected_models) > max_models:
            # Sort by performance
            selected_performance = {model: model_performance.get(model, 0) 
                                  for model in selected_models}
            
            # Select top performers
            selected_models = [model for model, _ in 
                             sorted(selected_performance.items(), 
                                   key=lambda x: x[1], 
                                   reverse=True)[:max_models]]
        
        # Store selected models
        self.selected_models = selected_models
        
        return selected_models
    
    def online_update(
        self,
        model_predictions: Dict[str, np.ndarray],
        ensemble_prediction: np.ndarray,
        actual_values: np.ndarray
    ) -> Dict[str, float]:
        """
        Update model weights and errors based on recent performance
        
        Parameters:
        -----------
        model_predictions : Dict[str, np.ndarray]
            Predictions from each model
        ensemble_prediction : np.ndarray
            Final ensemble prediction
        actual_values : np.ndarray
            Actual target values
            
        Returns:
        --------
        Dict[str, float]
            Learning rate adjustments for each model
        """
        # Calculate errors for each model
        model_errors = {}
        
        for model_name, preds in model_predictions.items():
            if model_name not in self.recent_errors:
                self.recent_errors[model_name] = []
            
            # Calculate error (use appropriate metric based on prediction type)
            if (preds >= 0).all() and (preds <= 1).all() and set(np.unique(actual_values)) <= {0, 1}:
                # Classification error
                errors = (preds > 0.5).astype(int) != actual_values
                error_rate = np.mean(errors)
            else:
                # Regression error (normalized)
                errors = np.abs(preds - actual_values)
                max_error = max(errors.max(), 1e-10)  # Avoid division by zero
                error_rate = np.mean(errors) / max_error
            
            # Store error
            self.recent_errors[model_name].append(error_rate)
            
            # Keep only recent history
            if len(self.recent_errors[model_name]) > self.prediction_memory:
                self.recent_errors[model_name] = self.recent_errors[model_name][-self.prediction_memory:]
            
            # Calculate current error
            model_errors[model_name] = error_rate
        
        # Calculate ensemble error
        if (ensemble_prediction >= 0).all() and (ensemble_prediction <= 1).all() and set(np.unique(actual_values)) <= {0, 1}:
            # Classification error
            ensemble_errors = (ensemble_prediction > 0.5).astype(int) != actual_values
            ensemble_error_rate = np.mean(ensemble_errors)
        else:
            # Regression error (normalized)
            ensemble_errors = np.abs(ensemble_prediction - actual_values)
            max_error = max(ensemble_errors.max(), 1e-10)  # Avoid division by zero
            ensemble_error_rate = np.mean(ensemble_errors) / max_error
        
        # Calculate error trends (improvement or deterioration)
        learning_adjustments = {}
        
        for model_name, errors in self.recent_errors.items():
            if len(errors) >= 10:  # Need enough history to detect trend
                # Recent error trend (first half vs second half)
                half_idx = len(errors) // 2
                recent_trend = np.mean(errors[half_idx:]) - np.mean(errors[:half_idx])
                
                # Store trend
                if model_name not in self.error_trends:
                    self.error_trends[model_name] = []
                
                self.error_trends[model_name].append(recent_trend)
                
                # Keep only recent history
                if len(self.error_trends[model_name]) > 10:
                    self.error_trends[model_name] = self.error_trends[model_name][-10:]
                
                # Adjust learning rate based on trend
                if recent_trend < 0:
                    # Improving - increase learning rate
                    learning_adjustments[model_name] = self.online_learning_rate * 1.2
                elif recent_trend > 0:
                    # Deteriorating - decrease learning rate
                    learning_adjustments[model_name] = self.online_learning_rate * 0.8
                else:
                    # Stable - keep learning rate
                    learning_adjustments[model_name] = self.online_learning_rate
            else:
                # Not enough history - use default learning rate
                learning_adjustments[model_name] = self.online_learning_rate
        
        return learning_adjustments
    
    def get_position_sizing_multiplier(
        self, 
        confidence: float,
        regime: Optional[str] = None
    ) -> float:
        """
        Get position sizing multiplier based on prediction confidence
        
        Parameters:
        -----------
        confidence : float
            Prediction confidence (0-1)
        regime : Optional[str]
            Current market regime
            
        Returns:
        --------
        float
            Position sizing multiplier (0-1)
        """
        # Basic sigmoid function to map confidence to position size
        # Low confidence -> small position, high confidence -> full position
        if confidence < self.min_confidence_threshold:
            # Below minimum threshold - no position
            return 0.0
        
        # Normalize confidence to 0-1 range for the valid region
        normalized_conf = (confidence - self.min_confidence_threshold) / (1 - self.min_confidence_threshold)
        
        # Apply sigmoid function for smooth scaling
        # The constants 5 and 0.5 control the steepness and midpoint
        if regime and regime in self.position_size_multipliers:
            # Use regime-specific settings if available
            steepness, midpoint = self.position_size_multipliers[regime]
        else:
            # Default values
            steepness, midpoint = 5, 0.5
        
        # Calculate multiplier using sigmoid
        multiplier = 1 / (1 + np.exp(-steepness * (normalized_conf - midpoint)))
        
        return multiplier
    
    def set_position_sizing_params(
        self,
        regime: str,
        steepness: float,
        midpoint: float
    ) -> None:
        """
        Set custom position sizing parameters for a specific regime
        
        Parameters:
        -----------
        regime : str
            Market regime
        steepness : float
            Steepness of the sigmoid function
        midpoint : float
            Midpoint of the sigmoid function
        """
        self.position_size_multipliers[regime] = (steepness, midpoint)
    
    def visualize_confidence_distribution(self) -> None:
        """
        Visualize the distribution of confidence scores and their accuracy
        """
        if not self.confidence_history:
            logger.warning("No confidence history to visualize")
            return
        
        # Convert to numpy array
        confidence_values = np.array(self.confidence_history)
        
        # Create figure with 1 subplot
        plt.figure(figsize=(10, 6))
        
        # Plot confidence distribution
        sns.histplot(confidence_values, bins=20, kde=True)
        plt.xlabel('Confidence Score')
        plt.ylabel('Frequency')
        plt.title('Distribution of Prediction Confidence Scores')
        plt.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.show()
    
    def visualize_calibration_curve(self) -> None:
        """
        Visualize the calibration curve (predicted confidence vs. actual accuracy)
        """
        if not any(len(data['pred']) > 0 for data in self.calibration_data.values()):
            logger.warning("No calibration data available to visualize")
            return
        
        # Prepare data for plotting
        bin_centers = []
        mean_predicted_values = []
        mean_actual_values = []
        sample_counts = []
        
        for bin_idx in range(len(self.confidence_bins)-1):
            bin_data = self.calibration_data[bin_idx]
            
            if bin_data['pred']:
                bin_centers.append((self.confidence_bins[bin_idx] + self.confidence_bins[bin_idx+1]) / 2)
                mean_predicted_values.append(np.mean(bin_data['pred']))
                mean_actual_values.append(np.mean(bin_data['actual']))
                sample_counts.append(len(bin_data['pred']))
        
        if not bin_centers:
            logger.warning("Not enough calibration data to create curve")
            return
        
        # Create figure with 1 subplot
        plt.figure(figsize=(10, 6))
        
        # Plot calibration curve
        plt.plot([0, 1], [0, 1], 'k--', label='Perfectly Calibrated')
        
        # Plot calibration points with size proportional to sample count
        max_size = 200
        normalized_counts = np.array(sample_counts) / max(sample_counts)
        sizes = normalized_counts * max_size + 10
        
        plt.scatter(bin_centers, mean_actual_values, s=sizes, alpha=0.7, 
                   c=bin_centers, cmap='viridis', label='Calibration Data')
        
        plt.xlabel('Predicted Confidence')
        plt.ylabel('Actual Accuracy')
        plt.title('Calibration Curve: Predicted vs. Actual')
        plt.grid(alpha=0.3)
        plt.legend()
        
        plt.tight_layout()
        plt.show()
    
    def visualize_model_diversity(self) -> None:
        """
        Visualize model diversity as a heatmap
        """
        if self.model_diversity_matrix is None or self.model_diversity_matrix.empty:
            logger.warning("No diversity matrix available to visualize")
            return
        
        # Create figure
        plt.figure(figsize=(10, 8))
        
        # Plot diversity heatmap
        sns.heatmap(
            self.model_diversity_matrix,
            cmap='viridis',
            vmin=0,
            vmax=1,
            annot=True,
            fmt='.2f',
            cbar_kws={'label': 'Diversity Score'}
        )
        
        plt.title('Model Diversity Matrix')
        plt.tight_layout()
        plt.show()
    
    def visualize_model_clusters(self) -> None:
        """
        Visualize model clusters as a dendrogram
        """
        if self.model_diversity_matrix is None or self.model_diversity_matrix.empty:
            logger.warning("No diversity matrix available to visualize")
            return
        
        # Convert diversity to distance (1 - diversity)
        distance_matrix = 1 - self.model_diversity_matrix.values
        
        # Apply hierarchical clustering
        linkage_matrix = linkage(distance_matrix[np.triu_indices(len(distance_matrix), k=1)], 
                               method='average')
        
        # Create figure
        plt.figure(figsize=(12, 8))
        
        # Plot dendrogram
        dendrogram(
            linkage_matrix,
            labels=self.model_diversity_matrix.index,
            leaf_rotation=90
        )
        
        plt.title('Model Hierarchical Clustering')
        plt.xlabel('Models')
        plt.ylabel('Distance')
        plt.grid(axis='y', alpha=0.3)
        
        # Add horizontal line for suggested clustering threshold
        if self.model_clusters:
            num_clusters = len(self.model_clusters)
            plt.axhline(y=0.3, color='r', linestyle='--', 
                       label=f'Threshold: {0.3:.2f} ({num_clusters} clusters)')
            plt.legend()
        
        plt.tight_layout()
        plt.show()
    
    def visualize_error_trends(self) -> None:
        """
        Visualize error trends for each model
        """
        if not self.error_trends:
            logger.warning("No error trend data available to visualize")
            return
        
        # Convert to DataFrame
        trend_data = {}
        
        for model_name, trends in self.error_trends.items():
            if trends:  # Check if non-empty
                trend_data[model_name] = trends
        
        if not trend_data:
            logger.warning("No trend data available for visualization")
            return
        
        trend_df = pd.DataFrame(trend_data)
        
        # Create figure
        plt.figure(figsize=(12, 6))
        
        # Plot error trends
        trend_df.plot(figsize=(12, 6), marker='o')
        plt.axhline(y=0, color='k', linestyle='--', alpha=0.3)
        plt.xlabel('Update')
        plt.ylabel('Error Trend (negative = improving)')
        plt.title('Model Error Trends')
        plt.grid(alpha=0.3)
        plt.legend(title='Model')
        
        plt.tight_layout()
        plt.show()
    
    def visualize_position_sizing(self) -> None:
        """
        Visualize the position sizing function
        """
        # Create a range of confidence values
        confidence_values = np.linspace(0, 1, 100)
        
        # Calculate position sizing multipliers
        multipliers = np.array([self.get_position_sizing_multiplier(conf) for conf in confidence_values])
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Plot position sizing function
        plt.plot(confidence_values, multipliers, 'b-', linewidth=2)
        plt.axvline(x=self.min_confidence_threshold, color='r', linestyle='--', 
                   label=f'Min Threshold: {self.min_confidence_threshold:.2f}')
        
        # Add regime-specific curves if available
        for regime, (steepness, midpoint) in self.position_size_multipliers.items():
            # Normalize and apply sigmoid
            normalized_conf = (confidence_values - self.min_confidence_threshold) / (1 - self.min_confidence_threshold)
            regime_multipliers = 1 / (1 + np.exp(-steepness * (normalized_conf - midpoint)))
            
            # Set negative values to 0
            regime_multipliers[confidence_values < self.min_confidence_threshold] = 0
            
            plt.plot(confidence_values, regime_multipliers, '--', alpha=0.7, 
                    label=f'Regime: {regime}')
        
        plt.xlabel('Prediction Confidence')
        plt.ylabel('Position Size Multiplier')
        plt.title('Position Sizing Based on Prediction Confidence')
        plt.grid(alpha=0.3)
        plt.legend()
        
        plt.tight_layout()
        plt.show() 