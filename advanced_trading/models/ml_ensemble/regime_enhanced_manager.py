"""
Regime-Enhanced Ensemble Manager
-------------------------------
Extends the basic ensemble manager with advanced regime detection, 
transition handling, and regime-specific model optimization.

This module provides:
1. Automatic regime detection using unsupervised methods
2. Smooth transition between regimes for stable predictions
3. Regime-specific model selection and weighting
4. Regime transition forecasting
5. Adaptation strategies for regime changes
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
import logging
import joblib
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
from scipy.stats import entropy
import warnings

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

# Get the logger
logger = logging.getLogger(__name__)

class RegimeEnhancedManager:
    """
    Extends ensemble management with sophisticated regime handling capabilities.
    
    This class enhances the basic EnsembleManager with:
    - Automatic regime detection using clustering and statistical methods
    - Smooth transition between regimes to prevent prediction jumps
    - Tracking of regime-specific model performance
    - Forecasting of upcoming regime changes
    - Adaptive strategies during regime transitions
    
    Parameters:
    -----------
    n_regimes : int
        Target number of market regimes to detect
    regime_features : List[str]
        Features to use for regime detection
    detection_method : str
        Method for regime detection ('kmeans', 'gmm', 'hmm', 'thresholds')
    transition_window : int
        Number of periods for smooth transition between regimes
    min_regime_duration : int
        Minimum number of periods a regime must persist
    regime_memory : int
        Number of past periods to consider for regime detection
    """
    
    def __init__(
        self,
        n_regimes: int = 3,
        regime_features: Optional[List[str]] = None,
        detection_method: str = 'kmeans',
        transition_window: int = 5,
        min_regime_duration: int = 10,
        regime_memory: int = 120
    ):
        self.n_regimes = n_regimes
        self.regime_features = regime_features
        self.detection_method = detection_method
        self.transition_window = transition_window
        self.min_regime_duration = min_regime_duration
        self.regime_memory = regime_memory
        
        # Regime detection models
        self.regime_model = None
        self.pca = None
        
        # Regime state tracking
        self.current_regime = None
        self.regime_history = []
        self.regime_transitions = []
        self.regime_durations = {}
        self.regime_probabilities = None
        
        # Regime-specific model weights and performance
        self.regime_model_weights = {}
        self.regime_model_performance = {}
        
        # Feature stability tracking by regime
        self.feature_stability = {}
        
        # Model performance in regime transitions
        self.transition_performance = {}
        
        # Regime profiles (statistical characteristics)
        self.regime_profiles = {}
    
    def detect_regimes(
        self, 
        X: pd.DataFrame,
        custom_regime_labels: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        Detect market regimes from features
        
        Parameters:
        -----------
        X : pd.DataFrame
            Feature data for regime detection
        custom_regime_labels : Optional[pd.Series]
            Custom regime labels to use instead of detection (for manual regime assignment)
            
        Returns:
        --------
        pd.Series
            Detected regime labels for each data point
        """
        if custom_regime_labels is not None:
            logger.info("Using custom regime labels instead of detection")
            self.regime_history = custom_regime_labels.copy()
            return custom_regime_labels
        
        # Use only specified regime features if provided
        if self.regime_features is not None:
            available_features = [f for f in self.regime_features if f in X.columns]
            if not available_features:
                logger.warning("None of the specified regime features are available")
                features_df = X.copy()
            else:
                features_df = X[available_features].copy()
        else:
            features_df = X.copy()
        
        # Apply PCA if we have many features
        if features_df.shape[1] > 10:
            if self.pca is None:
                self.pca = PCA(n_components=min(10, features_df.shape[1], features_df.shape[0]))
                pca_features = self.pca.fit_transform(features_df)
            else:
                pca_features = self.pca.transform(features_df)
            
            # Convert back to DataFrame for consistency
            features_df = pd.DataFrame(
                pca_features,
                index=features_df.index,
                columns=[f'pca_{i}' for i in range(pca_features.shape[1])]
            )
        
        # Detect regimes using the specified method
        if self.detection_method == 'kmeans':
            regimes = self._detect_regimes_kmeans(features_df)
        elif self.detection_method == 'gmm':
            regimes = self._detect_regimes_gmm(features_df)
        elif self.detection_method == 'thresholds':
            regimes = self._detect_regimes_thresholds(features_df)
        else:
            logger.warning(f"Unknown regime detection method: {self.detection_method}")
            regimes = pd.Series(['unknown'] * len(features_df), index=features_df.index)
        
        # Enforce minimum regime duration to prevent rapid switching
        regimes = self._enforce_min_duration(regimes)
        
        # Update regime history
        self.regime_history = regimes.copy()
        
        # Update current regime
        if not regimes.empty:
            self.current_regime = regimes.iloc[-1]
        
        # Detect and record regime transitions
        self._detect_transitions(regimes)
        
        return regimes
    
    def _detect_regimes_kmeans(self, features_df: pd.DataFrame) -> pd.Series:
        """Detect regimes using K-means clustering"""
        # Initialize or reuse the model
        if self.regime_model is None or not isinstance(self.regime_model, KMeans):
            self.regime_model = KMeans(
                n_clusters=self.n_regimes, 
                n_init=10,
                random_state=42
            )
            self.regime_model.fit(features_df)
        
        # Get cluster assignments
        labels = self.regime_model.predict(features_df)
        
        # Convert to regime names
        regime_labels = pd.Series(
            [f'regime_{label}' for label in labels],
            index=features_df.index
        )
        
        return regime_labels
    
    def _detect_regimes_gmm(self, features_df: pd.DataFrame) -> pd.Series:
        """Detect regimes using Gaussian Mixture Model"""
        # Initialize or reuse the model
        if self.regime_model is None or not isinstance(self.regime_model, GaussianMixture):
            self.regime_model = GaussianMixture(
                n_components=self.n_regimes,
                covariance_type='full',
                random_state=42
            )
            self.regime_model.fit(features_df)
        
        # Get cluster assignments and probabilities
        labels = self.regime_model.predict(features_df)
        self.regime_probabilities = self.regime_model.predict_proba(features_df)
        
        # Convert to regime names
        regime_labels = pd.Series(
            [f'regime_{label}' for label in labels],
            index=features_df.index
        )
        
        return regime_labels
    
    def _detect_regimes_thresholds(self, features_df: pd.DataFrame) -> pd.Series:
        """
        Detect regimes using predefined thresholds on specific features
        
        For example, for a volatility + trend framework:
        - High vol, up trend -> regime_0
        - High vol, down trend -> regime_1
        - Low vol, up trend -> regime_2
        - Low vol, down trend -> regime_3
        """
        # This is an example implementation that would be customized
        # based on domain knowledge and specific features
        
        # Assume we have volatility and trend features
        if 'volatility' in features_df.columns and 'trend' in features_df.columns:
            # Define thresholds
            vol_threshold = features_df['volatility'].median()
            trend_threshold = 0  # Assuming trend > 0 means uptrend
            
            # Create regime labels
            regime_labels = pd.Series(index=features_df.index, dtype='object')
            
            # Assign regimes based on thresholds
            regime_labels[(features_df['volatility'] > vol_threshold) & 
                          (features_df['trend'] > trend_threshold)] = 'regime_0'  # High vol, up trend
            
            regime_labels[(features_df['volatility'] > vol_threshold) & 
                          (features_df['trend'] <= trend_threshold)] = 'regime_1'  # High vol, down trend
            
            regime_labels[(features_df['volatility'] <= vol_threshold) & 
                          (features_df['trend'] > trend_threshold)] = 'regime_2'  # Low vol, up trend
            
            regime_labels[(features_df['volatility'] <= vol_threshold) & 
                          (features_df['trend'] <= trend_threshold)] = 'regime_3'  # Low vol, down trend
            
            return regime_labels
        else:
            logger.warning("Required features for threshold-based regime detection not available")
            # Fallback to a simple clustering approach
            return self._detect_regimes_kmeans(features_df)
    
    def _enforce_min_duration(self, regimes: pd.Series) -> pd.Series:
        """
        Enforce minimum regime duration to prevent oscillation
        by smoothing over short-lived regime changes
        """
        # Copy input to avoid modifying the original
        smoothed_regimes = regimes.copy()
        
        if len(regimes) <= 1:
            return smoothed_regimes
        
        # Track current regime and its duration
        current_regime = regimes.iloc[0]
        duration = 1
        
        # Iterate through the regime series
        for i in range(1, len(regimes)):
            new_regime = regimes.iloc[i]
            
            if new_regime == current_regime:
                # Same regime, increase duration
                duration += 1
            else:
                # Different regime, check if we should switch
                if duration < self.min_regime_duration:
                    # Current regime too short, keep original regime for these points
                    prev_idx = max(0, i-duration)
                    smoothed_regimes.iloc[prev_idx:i] = current_regime
                
                # Reset with new regime
                current_regime = new_regime
                duration = 1
        
        # Check the final regime duration
        if duration < self.min_regime_duration:
            smoothed_regimes.iloc[-duration:] = smoothed_regimes.iloc[-(duration+1)] if len(regimes) > duration else smoothed_regimes.iloc[0]
        
        return smoothed_regimes
    
    def _detect_transitions(self, regimes: pd.Series) -> None:
        """
        Detect and record regime transitions for transition analysis
        
        A transition occurs when the regime changes from one to another.
        This method tracks these transitions and their timing.
        """
        if len(regimes) <= 1:
            return
        
        transitions = []
        prev_regime = regimes.iloc[0]
        
        # Find points where regime changes
        for i in range(1, len(regimes)):
            curr_regime = regimes.iloc[i]
            if curr_regime != prev_regime:
                # Record transition
                transitions.append({
                    'timestamp': regimes.index[i],
                    'from_regime': prev_regime,
                    'to_regime': curr_regime
                })
                
                # Update regime durations
                if prev_regime not in self.regime_durations:
                    self.regime_durations[prev_regime] = []
                
                # Calculate duration from start to this transition
                duration = i - sum(len(self.regime_durations.get(regime, [])) 
                                   for regime in self.regime_durations 
                                   if regime != prev_regime)
                
                self.regime_durations[prev_regime].append(duration)
                
                # Update previous regime
                prev_regime = curr_regime
        
        # Store transitions
        self.regime_transitions.extend(transitions)
    
    def get_model_weights_for_regime(
        self, 
        current_regime: str,
        default_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Get appropriate model weights for the current regime
        
        Parameters:
        -----------
        current_regime : str
            Current market regime
        default_weights : Dict[str, float]
            Default model weights to use if no regime-specific weights are available
            
        Returns:
        --------
        Dict[str, float]
            Model weights appropriate for the current regime
        """
        # Check if we have weights for this regime
        if current_regime in self.regime_model_weights:
            return self.regime_model_weights[current_regime]
        
        logger.info(f"No specific weights for regime {current_regime}, using defaults")
        return default_weights
    
    def update_regime_model_weights(
        self,
        regime: str,
        model_performance: Dict[str, float]
    ) -> None:
        """
        Update model weights for a specific regime based on performance
        
        Parameters:
        -----------
        regime : str
            Market regime to update weights for
        model_performance : Dict[str, float]
            Performance metric for each model in this regime
        """
        if not model_performance:
            return
        
        # Store performance by regime
        if regime not in self.regime_model_performance:
            self.regime_model_performance[regime] = {}
        
        for model, perf in model_performance.items():
            if model not in self.regime_model_performance[regime]:
                self.regime_model_performance[regime][model] = []
            
            self.regime_model_performance[regime][model].append(perf)
        
        # Calculate weights based on performance (softmax)
        performance_values = np.array(list(model_performance.values()))
        
        # Handle negative values by shifting all values to be positive
        if np.any(performance_values < 0):
            performance_values = performance_values - np.min(performance_values) + 1e-6
        
        # Apply softmax to get weights
        exp_values = np.exp(performance_values / 0.1)  # Temperature parameter for softmax
        softmax_weights = exp_values / exp_values.sum()
        
        # Update regime-specific weights
        if regime not in self.regime_model_weights:
            self.regime_model_weights[regime] = {}
        
        for i, model in enumerate(model_performance.keys()):
            if model in self.regime_model_weights[regime]:
                # Smooth update of weights
                self.regime_model_weights[regime][model] = (
                    0.8 * self.regime_model_weights[regime][model] +
                    0.2 * softmax_weights[i]
                )
            else:
                self.regime_model_weights[regime][model] = softmax_weights[i]
        
        # Normalize weights to sum to 1
        total_weight = sum(self.regime_model_weights[regime].values())
        self.regime_model_weights[regime] = {
            model: weight / total_weight 
            for model, weight in self.regime_model_weights[regime].items()
        }
    
    def handle_regime_transition(
        self,
        from_regime: str,
        to_regime: str,
        model_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Handle smooth transition between regimes by blending model weights
        
        Parameters:
        -----------
        from_regime : str
            Previous regime
        to_regime : str
            New regime
        model_weights : Dict[str, float]
            Current model weights
            
        Returns:
        --------
        Dict[str, float]
            Blended model weights for smooth transition
        """
        # If we don't have weights for either regime, return current weights
        if from_regime not in self.regime_model_weights or to_regime not in self.regime_model_weights:
            return model_weights
        
        # Calculate transition progress (0 to 1) based on transition window
        transition_progress = min(1.0, self.transition_window / self.min_regime_duration)
        
        # Blend weights between the two regimes
        from_weights = self.regime_model_weights[from_regime]
        to_weights = self.regime_model_weights[to_regime]
        
        # Ensure both weight dicts have the same models
        all_models = set(list(from_weights.keys()) + list(to_weights.keys()))
        
        # Create blended weights
        blended_weights = {}
        
        for model in all_models:
            from_weight = from_weights.get(model, 0.0)
            to_weight = to_weights.get(model, 0.0)
            
            # Linear interpolation between weights
            blended_weights[model] = (
                (1 - transition_progress) * from_weight +
                transition_progress * to_weight
            )
        
        # Normalize weights to sum to 1
        total_weight = sum(blended_weights.values())
        blended_weights = {
            model: weight / total_weight 
            for model, weight in blended_weights.items()
        }
        
        return blended_weights
    
    def predict_next_regime(
        self,
        current_features: pd.DataFrame
    ) -> Tuple[str, float]:
        """
        Predict the next likely regime based on current market features
        
        Parameters:
        -----------
        current_features : pd.DataFrame
            Current market features
            
        Returns:
        --------
        Tuple[str, float]
            Most likely next regime and confidence level
        """
        # This is a simplified implementation that could be enhanced with
        # a dedicated regime transition prediction model
        
        if self.detection_method == 'gmm' and self.regime_probabilities is not None:
            # Use regime probabilities from GMM
            latest_probs = self.regime_probabilities[-1]
            
            # Get the most likely regime
            most_likely_idx = np.argmax(latest_probs)
            confidence = latest_probs[most_likely_idx]
            
            next_regime = f'regime_{most_likely_idx}'
            
            return next_regime, confidence
        
        # Fallback to current regime with low confidence
        if self.current_regime is not None:
            return self.current_regime, 0.6
        
        # If all else fails
        return 'unknown', 0.5
    
    def update_feature_stability(
        self,
        regime: str,
        feature_importances: Dict[str, float]
    ) -> None:
        """
        Update feature stability metrics for a specific regime
        
        Parameters:
        -----------
        regime : str
            Market regime
        feature_importances : Dict[str, float]
            Importance scores for each feature
        """
        if not feature_importances:
            return
        
        # Initialize regime data if needed
        if regime not in self.feature_stability:
            self.feature_stability[regime] = {}
        
        # For each feature, track its importance history
        for feature, importance in feature_importances.items():
            if feature not in self.feature_stability[regime]:
                self.feature_stability[regime][feature] = []
            
            self.feature_stability[regime][feature].append(importance)
            
            # Keep only recent history
            if len(self.feature_stability[regime][feature]) > self.regime_memory:
                self.feature_stability[regime][feature] = self.feature_stability[regime][feature][-self.regime_memory:]
    
    def get_regime_duration_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics about regime durations
        
        Returns:
        --------
        Dict[str, Dict[str, float]]
            Statistics on regime durations
        """
        stats = {}
        
        for regime, durations in self.regime_durations.items():
            if durations:
                stats[regime] = {
                    'count': len(durations),
                    'mean': np.mean(durations),
                    'median': np.median(durations),
                    'min': np.min(durations),
                    'max': np.max(durations),
                    'std': np.std(durations)
                }
        
        return stats
    
    def visualize_regimes(self, X: Optional[pd.DataFrame] = None) -> None:
        """
        Visualize detected regimes
        
        Parameters:
        -----------
        X : Optional[pd.DataFrame]
            Feature data for visualization
        """
        if not self.regime_history:
            logger.warning("No regime history to visualize")
            return
        
        # Convert regime history to DataFrame if it's a Series
        if isinstance(self.regime_history, pd.Series):
            regime_df = pd.DataFrame({'regime': self.regime_history})
        else:
            # Assume it's already a list of regime labels
            regime_df = pd.DataFrame({
                'regime': self.regime_history,
                'timestamp': range(len(self.regime_history))
            })
            regime_df.set_index('timestamp', inplace=True)
        
        # Create figure with 2 subplots if we have features, otherwise 1
        if X is not None:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [1, 2]})
        else:
            fig, ax1 = plt.subplots(figsize=(12, 5))
        
        # Plot regime changes over time
        regime_df['regime_num'] = regime_df['regime'].astype('category').cat.codes
        unique_regimes = regime_df['regime'].unique()
        
        # Create a colormap
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_regimes)))
        
        # Plot regimes as colored background
        for i, regime in enumerate(unique_regimes):
            mask = regime_df['regime'] == regime
            if mask.any():
                regime_periods = regime_df.index[mask]
                for start_idx in regime_periods[regime_df.index.get_indexer(regime_periods[1:]) 
                                              - regime_df.index.get_indexer(regime_periods[:-1]) > 1]:
                    # Find end of this continuous period
                    end_mask = regime_df.index > start_idx
                    if end_mask.any() and any(regime_df.loc[end_mask, 'regime'] != regime):
                        end_idx = regime_df.index[end_mask][regime_df.loc[end_mask, 'regime'] != regime][0]
                    else:
                        end_idx = regime_df.index[-1]
                    
                    ax1.axvspan(start_idx, end_idx, alpha=0.3, color=colors[i], label=regime if start_idx == regime_periods[0] else "")
        
        # Plot regime labels as a line
        ax1.plot(regime_df.index, regime_df['regime_num'], 'k-', linewidth=1)
        ax1.set_ylabel('Regime')
        ax1.set_title('Market Regime Detection')
        
        # Set y-tick labels to regime names
        ax1.set_yticks(range(len(unique_regimes)))
        ax1.set_yticklabels(unique_regimes)
        
        # Add legend
        handles, labels = ax1.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax1.legend(by_label.values(), by_label.keys(), loc='upper right')
        
        # If we have features, visualize in 2D using PCA or t-SNE
        if X is not None and len(X) > 0:
            # Use only the first 2 PCs if we have PCA fitted
            if self.pca is not None:
                pca_features = self.pca.transform(X)
                X_2d = pca_features[:, :2]
                method = 'PCA'
            elif len(X.columns) > 2:
                # Use t-SNE for dimensionality reduction
                tsne = TSNE(n_components=2, random_state=42)
                X_2d = tsne.fit_transform(X)
                method = 't-SNE'
            else:
                # Use first 2 features directly
                X_2d = X.iloc[:, :2].values
                method = 'Features'
            
            # Create 2D scatter plot colored by regime
            for i, regime in enumerate(unique_regimes):
                mask = regime_df['regime'] == regime
                if mask.any() and i < len(colors):
                    ax2.scatter(
                        X_2d[mask.values, 0],
                        X_2d[mask.values, 1],
                        c=[colors[i]],
                        label=regime,
                        alpha=0.7,
                        edgecolors='none',
                        s=50
                    )
            
            ax2.set_title(f'Regime Visualization ({method})')
            ax2.set_xlabel(f'{method} Dimension 1')
            ax2.set_ylabel(f'{method} Dimension 2')
            ax2.legend()
            ax2.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.show()
    
    def visualize_regime_performance(self) -> None:
        """
        Visualize model performance across different regimes
        """
        if not self.regime_model_performance:
            logger.warning("No regime-specific performance data to visualize")
            return
        
        # Create a DataFrame for visualization
        data = []
        
        for regime, model_perf in self.regime_model_performance.items():
            for model, perf_list in model_perf.items():
                for perf in perf_list:
                    data.append({
                        'Regime': regime,
                        'Model': model,
                        'Performance': perf
                    })
        
        if not data:
            logger.warning("No performance data points to visualize")
            return
        
        # Convert to DataFrame
        perf_df = pd.DataFrame(data)
        
        # Create a box plot
        plt.figure(figsize=(12, 6))
        sns.boxplot(x='Regime', y='Performance', hue='Model', data=perf_df)
        plt.title('Model Performance by Regime')
        plt.legend(title='Model')
        plt.tight_layout()
        plt.show()
    
    def save(self, filepath: str) -> None:
        """
        Save the regime manager to disk
        
        Parameters:
        -----------
        filepath : str
            Path to save the model
        """
        save_path = Path(filepath)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data for saving
        data = {
            'n_regimes': self.n_regimes,
            'regime_features': self.regime_features,
            'detection_method': self.detection_method,
            'transition_window': self.transition_window,
            'min_regime_duration': self.min_regime_duration,
            'regime_memory': self.regime_memory,
            'regime_model': self.regime_model,
            'pca': self.pca,
            'current_regime': self.current_regime,
            'regime_transitions': self.regime_transitions,
            'regime_durations': self.regime_durations,
            'regime_model_weights': self.regime_model_weights,
            'regime_model_performance': self.regime_model_performance,
            'feature_stability': self.feature_stability,
            'transition_performance': self.transition_performance,
            'regime_profiles': self.regime_profiles
        }
        
        # Save to disk
        joblib.dump(data, save_path)
        logger.info(f"Regime manager saved to {save_path}")
    
    @classmethod
    def load(cls, filepath: str) -> 'RegimeEnhancedManager':
        """
        Load a saved regime manager from disk
        
        Parameters:
        -----------
        filepath : str
            Path to the saved model
            
        Returns:
        --------
        RegimeEnhancedManager
            Loaded regime manager
        """
        data = joblib.load(filepath)
        
        # Create instance
        manager = cls(
            n_regimes=data['n_regimes'],
            regime_features=data['regime_features'],
            detection_method=data['detection_method'],
            transition_window=data['transition_window'],
            min_regime_duration=data['min_regime_duration'],
            regime_memory=data['regime_memory']
        )
        
        # Restore state
        manager.regime_model = data['regime_model']
        manager.pca = data['pca']
        manager.current_regime = data['current_regime']
        manager.regime_transitions = data['regime_transitions']
        manager.regime_durations = data['regime_durations']
        manager.regime_model_weights = data['regime_model_weights']
        manager.regime_model_performance = data['regime_model_performance']
        manager.feature_stability = data['feature_stability']
        manager.transition_performance = data['transition_performance']
        manager.regime_profiles = data['regime_profiles']
        
        return manager 