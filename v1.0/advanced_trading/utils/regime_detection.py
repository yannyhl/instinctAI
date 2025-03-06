"""
Market Regime Detection Module
----------------------------
Functionality for identifying market regimes to adapt trading strategies.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any
import logging
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
from hmmlearn import hmm
import matplotlib.dates as mdates

# Set up logging
logger = logging.getLogger(__name__)

class RegimeClassifier:
    """
    Market regime classifier that can identify different market regimes.
    
    Supported methods:
    - KMeans clustering
    - Gaussian Mixture Models (GMM)
    - Hidden Markov Models (HMM)
    """
    
    def __init__(self, method: str = 'hmm', n_regimes: int = 3, lookback_window: int = 60):
        """
        Initialize the regime classifier.
        
        Args:
            method: Classification method ('kmeans', 'gmm', or 'hmm')
            n_regimes: Number of regimes to identify
            lookback_window: Window size for feature calculation
        """
        self.method = method.lower()
        self.n_regimes = n_regimes
        self.lookback_window = lookback_window
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = None
        self.regime_labels = {
            0: "Bear Market",
            1: "Sideways/Neutral",
            2: "Bull Market"
        }
        
        # Customize regime labels for more than 3 regimes
        if n_regimes > 3:
            self.regime_labels = {i: f"Regime {i+1}" for i in range(n_regimes)}
        
        logger.info(f"Initialized {method} regime classifier with {n_regimes} regimes")
    
    def calculate_features(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate features for regime classification from price data.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with extracted features
        """
        # Ensure we have enough data
        if len(price_data) < self.lookback_window:
            logger.warning(f"Not enough data for feature calculation. Need at least {self.lookback_window} points.")
            return pd.DataFrame()
        
        # Calculate returns and volatility features
        returns = price_data['close'].pct_change().fillna(0)
        
        features = pd.DataFrame(index=price_data.index)
        
        # Return over different timeframes
        for window in [5, 10, 20, 40]:
            if len(price_data) > window:
                # Cumulative return over window
                features[f'return_{window}d'] = returns.rolling(window=window).apply(
                    lambda x: (1 + x).prod() - 1, raw=True
                )
        
        # Volatility over different timeframes
        for window in [10, 20, 40]:
            if len(price_data) > window:
                features[f'volatility_{window}d'] = returns.rolling(window=window).std() * np.sqrt(252)
        
        # Trend indicators
        if len(price_data) > 50:
            # Calculate moving averages
            ma_20 = price_data['close'].rolling(window=20).mean()
            ma_50 = price_data['close'].rolling(window=50).mean()
            
            # MA crossover indicator
            features['ma_diff'] = (ma_20 / ma_50) - 1
        
        # Volume features
        if 'volume' in price_data.columns:
            volume = price_data['volume']
            # Normalized volume
            features['vol_change'] = volume.pct_change().rolling(window=10).mean()
            
            # Volume trend
            features['vol_trend'] = (volume.rolling(window=10).mean() / 
                                   volume.rolling(window=30).mean() - 1)
        
        # RSI indicator
        delta = price_data['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        features['rsi'] = 100 - (100 / (1 + rs))
        
        # Momentum
        features['momentum'] = price_data['close'] / price_data['close'].shift(20) - 1
        
        # Drop rows with NaN due to lookback periods
        features = features.dropna()
        
        # Store feature names
        self.feature_names = features.columns.tolist()
        
        return features
    
    def fit(self, price_data: pd.DataFrame) -> 'RegimeClassifier':
        """
        Fit the regime classification model.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Self for method chaining
        """
        # Calculate features
        features_df = self.calculate_features(price_data)
        
        if features_df.empty:
            logger.error("No features calculated. Cannot fit model.")
            return self
        
        # Scale features
        X = features_df.values
        X_scaled = self.scaler.fit_transform(X)
        
        # Fit the appropriate model
        if self.method == 'kmeans':
            self.model = KMeans(n_clusters=self.n_regimes, random_state=42)
            self.model.fit(X_scaled)
            logger.info(f"Fitted KMeans model with {self.n_regimes} clusters")
            
        elif self.method == 'gmm':
            self.model = GaussianMixture(n_components=self.n_regimes, random_state=42)
            self.model.fit(X_scaled)
            logger.info(f"Fitted GMM model with {self.n_regimes} components")
            
        elif self.method == 'hmm':
            # HMM requires a different approach
            # Use returns as the observed variable
            returns = price_data['close'].pct_change().fillna(0).values.reshape(-1, 1)
            
            # Scale returns
            returns_scaled = self.scaler.fit_transform(returns)
            
            # Initialize and fit HMM
            self.model = hmm.GaussianHMM(
                n_components=self.n_regimes,
                covariance_type="full",
                n_iter=1000,
                random_state=42
            )
            
            self.model.fit(returns_scaled)
            logger.info(f"Fitted HMM model with {self.n_regimes} hidden states")
            
        else:
            logger.error(f"Unknown method: {self.method}")
        
        return self
    
    def predict(self, price_data: pd.DataFrame) -> pd.Series:
        """
        Predict regimes for the given price data.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Series with regime predictions
        """
        if self.model is None:
            logger.error("Model not fitted. Call fit() first.")
            return pd.Series()
        
        # Calculate features
        features_df = self.calculate_features(price_data)
        
        if features_df.empty:
            logger.error("No features calculated. Cannot predict regimes.")
            return pd.Series()
        
        # Make predictions based on the method
        if self.method in ['kmeans', 'gmm']:
            # Scale features
            X = features_df.values
            X_scaled = self.scaler.transform(X)
            
            if self.method == 'kmeans':
                regimes = self.model.predict(X_scaled)
            else:  # gmm
                regimes = self.model.predict(X_scaled)
                
        elif self.method == 'hmm':
            # Use returns as the observed variable
            returns = price_data['close'].pct_change().fillna(0).values.reshape(-1, 1)
            
            # Scale returns
            returns_scaled = self.scaler.transform(returns)
            
            # Predict hidden states
            regimes = self.model.predict(returns_scaled)
        
        # Create Series with predictions
        regime_series = pd.Series(regimes, index=features_df.index)
        
        return regime_series
    
    def classify_regime(self, regime_idx: int) -> str:
        """
        Get the label for a regime.
        
        Args:
            regime_idx: Regime index (0 to n_regimes-1)
            
        Returns:
            String label for the regime
        """
        if regime_idx in self.regime_labels:
            return self.regime_labels[regime_idx]
        else:
            return f"Regime {regime_idx+1}"
    
    def analyze_regimes(self, price_data: pd.DataFrame, regimes: pd.Series) -> Dict[int, Dict[str, float]]:
        """
        Analyze the properties of each detected regime.
        
        Args:
            price_data: DataFrame with OHLCV data
            regimes: Series with regime predictions
            
        Returns:
            Dictionary of regime stats by regime index
        """
        # Calculate returns
        returns = price_data['close'].pct_change().dropna()
        
        # Align returns with regimes
        aligned_data = pd.DataFrame({
            'returns': returns,
            'regime': regimes
        }).dropna()
        
        regime_stats = {}
        
        # Calculate statistics for each regime
        for regime_idx in range(self.n_regimes):
            regime_returns = aligned_data[aligned_data['regime'] == regime_idx]['returns']
            
            if len(regime_returns) == 0:
                continue
                
            # Calculate key statistics
            stats = {
                'count': len(regime_returns),
                'mean_return': regime_returns.mean() * 100,  # as percentage
                'volatility': regime_returns.std() * np.sqrt(252) * 100,  # annualized
                'sharpe': (regime_returns.mean() / regime_returns.std()) * np.sqrt(252) if regime_returns.std() > 0 else 0,
                'max_return': regime_returns.max() * 100,
                'min_return': regime_returns.min() * 100,
                'pct_positive': (regime_returns > 0).mean() * 100
            }
            
            regime_stats[regime_idx] = stats
        
        return regime_stats
    
    def plot_regimes(self, price_data: pd.DataFrame, regimes: pd.Series) -> plt.Figure:
        """
        Plot price chart with colored regime backgrounds.
        
        Args:
            price_data: DataFrame with OHLCV data
            regimes: Series with regime predictions
            
        Returns:
            Matplotlib figure
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot price
        ax.plot(price_data.index, price_data['close'], color='black', label='Price')
        
        # Color the background based on regimes
        regime_colors = ['#ffcccc', '#ccffcc', '#ccccff', '#ffffcc', '#ffccff']
        
        # Get unique regimes in order
        changes = np.diff(np.array(regimes), prepend=0)
        regime_changes = np.where(changes != 0)[0]
        
        # Add the last point
        if len(regime_changes) > 0:
            if regime_changes[-1] != len(regimes) - 1:
                regime_changes = np.append(regime_changes, len(regimes) - 1)
        
        # Fill regimes with colors
        for i in range(len(regime_changes) - 1):
            start_idx = regime_changes[i]
            end_idx = regime_changes[i + 1]
            
            regime = regimes.iloc[start_idx]
            color = regime_colors[regime % len(regime_colors)]
            
            ax.axvspan(regimes.index[start_idx], regimes.index[end_idx],
                      alpha=0.3, color=color, 
                      label=f'Regime {regime}' if i == 0 or regimes.iloc[start_idx] != regimes.iloc[regime_changes[i-1]] else "")
        
        # Add regime labels
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys())
        
        # Format the x-axis to show dates nicely
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.xticks(rotation=45)
        
        # Add title and labels
        ax.set_title(f'Price Chart with {self.method.upper()} Detected Regimes')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        
        plt.tight_layout()
        
        return fig
    
    def get_transition_matrix(self) -> np.ndarray:
        """
        Get the regime transition probability matrix.
        
        Returns:
            Transition probability matrix
        """
        if self.model is None:
            logger.error("Model not fitted. Call fit() first.")
            return np.array([])
        
        if self.method == 'hmm':
            # HMM already has a transition matrix
            return self.model.transmat_
        else:
            logger.warning(f"Transition matrix not directly available for {self.method}. Need to compute from data.")
            return np.array([])
    
    def predict_next_regime(self, current_regime: int) -> Tuple[int, float]:
        """
        Predict the most likely next regime from the current regime.
        
        Args:
            current_regime: Current regime index
            
        Returns:
            Tuple of (most_likely_next_regime, probability)
        """
        if self.model is None or self.method != 'hmm':
            logger.error("Next regime prediction only available for HMM.")
            return (-1, 0.0)
        
        # Get transition probabilities for current state
        trans_probs = self.model.transmat_[current_regime]
        
        # Find most likely next regime
        next_regime = np.argmax(trans_probs)
        probability = trans_probs[next_regime]
        
        return next_regime, probability
    
    def plot_regime_distributions(self, price_data: pd.DataFrame, regimes: pd.Series) -> plt.Figure:
        """
        Plot return distributions for each regime.
        
        Args:
            price_data: DataFrame with OHLCV data
            regimes: Series with regime predictions
            
        Returns:
            Matplotlib figure
        """
        # Calculate returns
        returns = price_data['close'].pct_change().dropna() * 100  # Convert to percentage
        
        # Align returns with regimes
        aligned_data = pd.DataFrame({
            'returns': returns,
            'regime': regimes
        }).dropna()
        
        # Create figure
        fig, axes = plt.subplots(1, self.n_regimes, figsize=(15, 5))
        
        # Plot histogram for each regime
        for i in range(self.n_regimes):
            ax = axes[i] if self.n_regimes > 1 else axes
            
            regime_returns = aligned_data[aligned_data['regime'] == i]['returns']
            
            if len(regime_returns) > 0:
                ax.hist(regime_returns, bins=20, alpha=0.7)
                ax.axvline(0, color='r', linestyle='--')
                ax.axvline(regime_returns.mean(), color='g', linestyle='-')
                
                ax.set_title(f'Regime {i}: {self.classify_regime(i)}')
                ax.set_xlabel('Daily Return (%)')
                ax.text(0.05, 0.95, f"Mean: {regime_returns.mean():.2f}%\nStd: {regime_returns.std():.2f}%",
                       transform=ax.transAxes, verticalalignment='top')
            else:
                ax.text(0.5, 0.5, f'No data for Regime {i}', 
                      ha='center', va='center', transform=ax.transAxes)
        
        plt.tight_layout()
        
        return fig


def detect_regime(returns: pd.Series, method: str = 'hmm', n_regimes: int = 3) -> int:
    """
    Simple function to detect the current market regime from a series of returns.
    
    Args:
        returns: Series of asset returns
        method: Detection method ('hmm', 'kmeans', 'volatility')
        n_regimes: Number of regimes to identify
        
    Returns:
        Integer representing the current regime
    """
    # Require at least 60 data points
    if len(returns) < 60:
        logger.warning("Not enough data for regime detection")
        return -1
    
    if method == 'volatility':
        # Simple volatility-based regime detection
        recent_vol = returns[-30:].std() * np.sqrt(252)
        
        if recent_vol > 0.4:  # Over 40% annualized vol
            return 0  # High volatility regime
        elif recent_vol > 0.2:  # 20-40% annualized vol
            return 1  # Medium volatility regime
        else:
            return 2  # Low volatility regime
            
    else:
        # Use the full classifier
        classifier = RegimeClassifier(method=method, n_regimes=n_regimes)
        
        # Create a dummy price series from returns
        price = (1 + returns).cumprod() * 100
        ohlc = pd.DataFrame({
            'open': price,
            'high': price,
            'low': price,
            'close': price
        }, index=returns.index)
        
        # Fit and predict
        classifier.fit(ohlc)
        regimes = classifier.predict(ohlc)
        
        if len(regimes) > 0:
            return regimes.iloc[-1]
        else:
            return -1


def analyze_regime_transitions(regimes: pd.Series) -> pd.DataFrame:
    """
    Analyze transitions between regimes to identify stable and unstable periods.
    
    Args:
        regimes: Series with regime predictions
        
    Returns:
        DataFrame with regime transition statistics
    """
    # Create shift to identify transitions
    transitions = pd.DataFrame({
        'regime': regimes,
        'next_regime': regimes.shift(-1)
    }).dropna()
    
    # Count transitions
    transition_counts = pd.crosstab(
        transitions['regime'], 
        transitions['next_regime'], 
        rownames=['From'], 
        colnames=['To']
    )
    
    # Convert to probabilities
    transition_probs = transition_counts.div(transition_counts.sum(axis=1), axis=0)
    
    return transition_probs


def identify_regime_change_points(regimes: pd.Series) -> pd.DatetimeIndex:
    """
    Identify points where the market regime changes.
    
    Args:
        regimes: Series with regime predictions
        
    Returns:
        DatetimeIndex with regime change points
    """
    # Find where regime changes
    regime_changes = regimes.diff().fillna(0) != 0
    
    # Get indices where changes occur
    change_points = regimes.index[regime_changes]
    
    return change_points


def get_regime_duration_stats(regimes: pd.Series) -> pd.DataFrame:
    """
    Calculate statistics about how long each regime typically lasts.
    
    Args:
        regimes: Series with regime predictions
        
    Returns:
        DataFrame with duration statistics for each regime
    """
    # Find regime change points
    change_points = identify_regime_change_points(regimes)
    
    # Add the end of the series as a final change point
    all_points = change_points.tolist() + [regimes.index[-1]]
    
    # Calculate duration of each regime segment
    durations = []
    regimes_list = []
    
    for i in range(len(all_points) - 1):
        start_date = all_points[i]
        end_date = all_points[i + 1]
        
        # Get the regime for this segment
        if i == 0 and len(change_points) > 0:
            # For first segment, get regime at the start
            regime = regimes.loc[:change_points[0]].iloc[0]
        else:
            # For other segments, get regime after the change
            regime = regimes.loc[start_date]
        
        # Calculate duration in days
        duration = (end_date - start_date).days
        
        durations.append(duration)
        regimes_list.append(regime)
    
    # Create DataFrame
    duration_df = pd.DataFrame({
        'regime': regimes_list,
        'duration': durations
    })
    
    # Group by regime and calculate statistics
    stats = duration_df.groupby('regime')['duration'].agg(
        ['count', 'mean', 'min', 'max', 'std']
    ).rename(columns={
        'count': 'num_occurrences',
        'mean': 'avg_duration_days',
        'min': 'min_duration_days',
        'max': 'max_duration_days',
        'std': 'std_duration_days'
    })
    
    return stats 