"""
Market Regime Detection Module
----------------------------
Functionality for identifying market regimes to adapt trading strategies.

This module provides tools for detecting market regimes (bull/bear/sideways markets,
high/low volatility regimes, etc.) using various machine learning techniques.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from enum import Enum
from datetime import datetime

# Import machine learning dependencies conditionally
try:
    from sklearn.cluster import KMeans
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classification."""
    BEAR = 0
    SIDEWAYS = 1
    BULL = 2
    HIGH_VOLATILITY = 3
    LOW_VOLATILITY = 4
    TREND_FOLLOWING = 5
    MEAN_REVERTING = 6
    RISK_ON = 7
    RISK_OFF = 8

class RegimeClassifier:
    """
    Market regime classifier that can identify different market regimes.
    
    Supported methods:
    - KMeans clustering
    - Gaussian Mixture Models (GMM)
    - Hidden Markov Models (HMM)
    - Threshold-based classification
    """
    
    def __init__(self, method: str = 'hmm', n_regimes: int = 3, lookback_window: int = 60):
        """
        Initialize the regime classifier.
        
        Args:
            method: Classification method ('kmeans', 'gmm', 'hmm', or 'threshold')
            n_regimes: Number of regimes to identify
            lookback_window: Window size for feature calculation
        """
        self._check_dependencies(method)
            
        self.method = method.lower()
        self.n_regimes = n_regimes
        self.lookback_window = lookback_window
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.feature_names = None
        self.is_fitted = False
        
        # Default regime labels (can be customized)
        self.regime_labels = {
            0: "Bear Market",
            1: "Sideways/Neutral",
            2: "Bull Market"
        }
        
        if n_regimes > 3:
            for i in range(3, n_regimes):
                self.regime_labels[i] = f"Regime {i+1}"
    
    def _check_dependencies(self, method: str):
        """Check if required dependencies are available for the chosen method."""
        if method in ['kmeans', 'gmm'] and not SKLEARN_AVAILABLE:
            raise ImportError(f"Method '{method}' requires scikit-learn, which is not available")
            
        if method == 'hmm' and not HMM_AVAILABLE:
            raise ImportError("Method 'hmm' requires hmmlearn, which is not available")
    
    def fit(self, price_data: pd.DataFrame) -> 'RegimeClassifier':
        """
        Fit the regime classifier to historical price data.
        
        Args:
            price_data: DataFrame with price data (must include 'close', 'high', 'low', and 'volume')
                        or at minimum just 'close' prices
                        
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If price_data doesn't contain required columns
        """
        # Extract features for regime detection
        features = self._extract_features(price_data)
        
        # Store feature names
        self.feature_names = features.columns.tolist()
        
        # Scale features
        if SKLEARN_AVAILABLE:
            scaled_features = self.scaler.fit_transform(features)
        else:
            # Simple z-score scaling if sklearn not available
            scaled_features = (features - features.mean()) / features.std()
        
        # Fit the appropriate model
        if self.method == 'kmeans':
            self.model = KMeans(n_clusters=self.n_regimes, random_state=42)
            self.model.fit(scaled_features)
            
        elif self.method == 'gmm':
            self.model = GaussianMixture(n_components=self.n_regimes, random_state=42)
            self.model.fit(scaled_features)
            
        elif self.method == 'hmm':
            # HMM requires special handling for time series
            self.model = hmm.GaussianHMM(n_components=self.n_regimes, random_state=42)
            self.model.fit(scaled_features)
            
        elif self.method == 'threshold':
            # Threshold-based methods don't need fitting
            self.model = "threshold"
            
        else:
            raise ValueError(f"Unknown method: {self.method}")
        
        self.is_fitted = True
        logger.info(f"Fitted {self.method} regime classifier with {self.n_regimes} regimes")
        
        return self
    
    def predict(self, price_data: pd.DataFrame) -> np.ndarray:
        """
        Predict regimes for the given price data.
        
        Args:
            price_data: DataFrame with price data
            
        Returns:
            Array of regime labels
            
        Raises:
            ValueError: If model is not fitted
        """
        if not self.is_fitted:
            raise ValueError("Model is not fitted. Call fit() first.")
            
        # Extract features
        features = self._extract_features(price_data)
        
        # Scale features
        if SKLEARN_AVAILABLE:
            scaled_features = self.scaler.transform(features)
        else:
            # Simple z-score scaling if sklearn not available
            scaled_features = (features - features.mean()) / features.std()
        
        # Predict regimes based on method
        if self.method == 'kmeans':
            regimes = self.model.predict(scaled_features)
            
        elif self.method == 'gmm':
            regimes = self.model.predict(scaled_features)
            
        elif self.method == 'hmm':
            regimes = self.model.predict(scaled_features)
            
        elif self.method == 'threshold':
            regimes = self._threshold_based_classification(features)
            
        else:
            raise ValueError(f"Unknown method: {self.method}")
            
        return regimes
    
    def fit_predict(self, price_data: pd.DataFrame) -> np.ndarray:
        """
        Fit the classifier and predict regimes in one step.
        
        Args:
            price_data: DataFrame with price data
            
        Returns:
            Array of regime labels
        """
        self.fit(price_data)
        return self.predict(price_data)
    
    def get_regime_probabilities(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Get the probability of each regime for the given price data.
        Only available for GMM and HMM methods.
        
        Args:
            price_data: DataFrame with price data
            
        Returns:
            DataFrame with probabilities for each regime
            
        Raises:
            ValueError: If method doesn't support probabilities
        """
        if not self.is_fitted:
            raise ValueError("Model is not fitted. Call fit() first.")
            
        if self.method not in ['gmm', 'hmm']:
            raise ValueError(f"Regime probabilities not available for method '{self.method}'")
            
        # Extract features
        features = self._extract_features(price_data)
        
        # Scale features
        if SKLEARN_AVAILABLE:
            scaled_features = self.scaler.transform(features)
        else:
            # Simple z-score scaling if sklearn not available
            scaled_features = (features - features.mean()) / features.std()
        
        # Get probabilities
        if self.method == 'gmm':
            probs = self.model.predict_proba(scaled_features)
        else:  # hmm
            probs = np.exp(self.model.score_samples(scaled_features)[1])
            
        # Create DataFrame with probabilities
        regime_names = [self.regime_labels.get(i, f"Regime {i+1}") for i in range(self.n_regimes)]
        return pd.DataFrame(probs, index=price_data.index, columns=regime_names)
    
    def get_regime_features(self) -> Dict[int, Dict[str, float]]:
        """
        Get the feature importance or characteristics of each regime.
        
        Returns:
            Dictionary mapping regime indices to feature importance dictionaries
            
        Raises:
            ValueError: If method doesn't support feature importance
        """
        if not self.is_fitted:
            raise ValueError("Model is not fitted. Call fit() first.")
            
        result = {}
        
        if self.method == 'kmeans':
            # For KMeans, we can use the cluster centers
            for i in range(self.n_regimes):
                center = self.model.cluster_centers_[i]
                result[i] = dict(zip(self.feature_names, center))
                
        elif self.method == 'gmm':
            # For GMM, we can use the means
            for i in range(self.n_regimes):
                mean = self.model.means_[i]
                result[i] = dict(zip(self.feature_names, mean))
                
        elif self.method == 'hmm':
            # For HMM, we can use the means of the emission distributions
            for i in range(self.n_regimes):
                mean = self.model.means_[i]
                result[i] = dict(zip(self.feature_names, mean))
                
        else:
            raise ValueError(f"Feature importance not available for method '{self.method}'")
            
        return result
    
    def plot_regimes(self, price_data: pd.DataFrame, regimes: Optional[np.ndarray] = None, 
                    ax: Optional[plt.Axes] = None, figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
        """
        Plot price data with regime classifications.
        
        Args:
            price_data: DataFrame with price data
            regimes: Optional pre-computed regimes (will predict if None)
            ax: Optional matplotlib axis to plot on
            figsize: Figure size if creating a new figure
            
        Returns:
            Matplotlib figure
        """
        if regimes is None:
            regimes = self.predict(price_data)
            
        # Create figure if needed
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.get_figure()
            
        # Plot price
        price_data['close'].plot(ax=ax, color='black', alpha=0.5, label='Price')
        
        # Color background based on regimes
        for regime in range(self.n_regimes):
            mask = regimes == regime
            if not any(mask):
                continue
                
            # Get regime spans
            spans = self._get_regime_spans(mask, price_data.index)
            
            # Color the background for this regime
            for start, end in spans:
                ax.axvspan(start, end, alpha=0.3, color=f'C{regime}', 
                          label=self.regime_labels.get(regime, f"Regime {regime+1}") if start == spans[0][0] else "")
                
        # Clean up the plot
        ax.set_title(f'Price with {self.method.upper()} Regime Classification')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.grid(True, alpha=0.3)
        
        # Only show unique labels in the legend
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='best')
        
        return fig
    
    def _extract_features(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Extract features from price data for regime detection.
        
        Args:
            price_data: DataFrame with price data
            
        Returns:
            DataFrame with extracted features
        """
        # Ensure we have at least close prices
        if 'close' not in price_data.columns:
            raise ValueError("Price data must contain at least 'close' column")
            
        # Create a copy to avoid modifying the original
        df = price_data.copy()
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        
        # Start with basic features
        features = pd.DataFrame(index=df.index)
        
        # Rolling features with the lookback window
        window = self.lookback_window
        
        # Trend features
        features['trend'] = df['close'].pct_change(window)
        features['trend_strength'] = self._calculate_trend_strength(df['close'], window)
        
        # Volatility features
        features['volatility'] = df['returns'].rolling(window).std() * np.sqrt(252)
        
        # Volume features (if available)
        if 'volume' in df.columns:
            features['volume_trend'] = df['volume'].pct_change(window)
            features['volume_intensity'] = df['volume'] / df['volume'].rolling(window).mean()
        
        # Range features (if available)
        if 'high' in df.columns and 'low' in df.columns:
            df['range'] = (df['high'] - df['low']) / df['close']
            features['range_expansion'] = df['range'].rolling(window).mean()
        
        # Clean up NaN values from rolling calculations
        features = features.dropna()
        
        return features
    
    def _calculate_trend_strength(self, prices: pd.Series, window: int) -> pd.Series:
        """
        Calculate the strength of a trend using R-squared of linear fit.
        
        Args:
            prices: Series of prices
            window: Window size for calculation
            
        Returns:
            Series of trend strength values
        """
        trend_strength = pd.Series(index=prices.index, dtype=float)
        
        for i in range(window, len(prices)):
            # Get the price window
            window_prices = prices.iloc[i-window:i]
            
            # Create X array (time points)
            x = np.arange(window)
            
            # Calculate linear regression
            slope, intercept = np.polyfit(x, window_prices, 1)
            
            # Calculate R-squared
            y_pred = intercept + slope * x
            ss_total = np.sum((window_prices - window_prices.mean()) ** 2)
            ss_residual = np.sum((window_prices - y_pred) ** 2)
            r_squared = 1 - (ss_residual / ss_total)
            
            # Store the result
            trend_strength.iloc[i] = r_squared * np.sign(slope)
            
        return trend_strength
    
    def _threshold_based_classification(self, features: pd.DataFrame) -> np.ndarray:
        """
        Classify regimes using threshold-based rules.
        
        Args:
            features: DataFrame with extracted features
            
        Returns:
            Array of regime labels
        """
        regimes = np.zeros(len(features), dtype=int)
        
        # Simple classification based on trend and volatility
        trend = features['trend'].values
        volatility = features['volatility'].values
        
        # Regime 0: Bear Market (negative trend)
        regimes[trend < -0.05] = 0
        
        # Regime 1: Sideways Market (low absolute trend)
        regimes[np.abs(trend) <= 0.05] = 1
        
        # Regime 2: Bull Market (positive trend)
        regimes[trend > 0.05] = 2
        
        # Could add more regimes based on volatility, etc.
        if self.n_regimes > 3:
            # Regime 3: High Volatility
            high_vol_threshold = np.percentile(volatility, 80)
            regimes[volatility > high_vol_threshold] = 3
        
        return regimes
    
    def _get_regime_spans(self, mask: np.ndarray, index: pd.DatetimeIndex) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
        """
        Get spans (start, end) for each continuous regime period.
        
        Args:
            mask: Boolean mask for a specific regime
            index: DatetimeIndex of the data
            
        Returns:
            List of (start, end) tuples for each span
        """
        if not any(mask):
            return []
            
        # Convert mask to numerical
        mask_int = mask.astype(int)
        
        # Find transitions
        transitions = np.diff(mask_int)
        transition_indices = np.where(transitions != 0)[0]
        
        # Add start and end if needed
        if mask[0]:
            transition_indices = np.r_[-1, transition_indices]
        if mask[-1]:
            transition_indices = np.r_[transition_indices, len(mask) - 1]
            
        # Create spans
        spans = []
        for i in range(0, len(transition_indices), 2):
            if i + 1 >= len(transition_indices):
                break
                
            start_idx = transition_indices[i] + 1
            end_idx = transition_indices[i + 1]
            
            if start_idx < 0:
                start_idx = 0
                
            if start_idx < len(index) and end_idx < len(index):
                spans.append((index[start_idx], index[end_idx]))
                
        return spans


def detect_regime(price_data: pd.DataFrame, method: str = 'hmm', n_regimes: int = 3, 
                lookback_window: int = 60) -> np.ndarray:
    """
    Detect market regimes using the specified method.
    
    This is a convenience function that creates a RegimeClassifier,
    fits it to the data, and returns the regime classifications.
    
    Args:
        price_data: DataFrame with price data
        method: Classification method ('kmeans', 'gmm', 'hmm', or 'threshold')
        n_regimes: Number of regimes to identify
        lookback_window: Window size for feature calculation
        
    Returns:
        Array of regime labels
    """
    classifier = RegimeClassifier(method=method, n_regimes=n_regimes, lookback_window=lookback_window)
    return classifier.fit_predict(price_data) 