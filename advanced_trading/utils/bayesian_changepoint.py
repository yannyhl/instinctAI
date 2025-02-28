"""
Bayesian Changepoint Detection
-----------------------------
This module provides utilities for detecting regime changes in financial time series
using Bayesian changepoint detection methods. These algorithms can identify structural 
breaks in the statistical properties of time series data, which can indicate transitions
between different market regimes (trends, mean-reversion, volatility clusters, etc.).
"""

import numpy as np
import pandas as pd
from typing import List, Union, Tuple, Optional
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import logging
import warnings

# For advanced changepoint detection (if installed)
try:
    import pymc3 as pm
    from pymc3.distributions.timeseries import GaussianRandomWalk
    PYMC3_AVAILABLE = True
except ImportError:
    PYMC3_AVAILABLE = False
    warnings.warn("pymc3 not available. Advanced Bayesian changepoint detection will be disabled.")

try:
    import ruptures as rpt
    RUPTURES_AVAILABLE = True
except ImportError:
    RUPTURES_AVAILABLE = False
    warnings.warn("ruptures package not available. Some changepoint detection methods will be disabled.")

# Configure logging
logger = logging.getLogger(__name__)


def detect_market_regimes(
    price_series: Union[pd.Series, np.ndarray],
    n_regimes: int = 3,
    method: str = 'binary_segmentation',
    window_size: int = 20,
    penalty: float = None,
    min_size: int = 30,
    return_probabilities: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, pd.DataFrame]]:
    """
    Detect market regimes in price series data.
    
    Parameters:
    -----------
    price_series : pd.Series or np.ndarray
        Time series of prices
    n_regimes : int, optional
        Number of regimes to identify, default 3
    method : str, optional
        Method to use for changepoint detection, default 'binary_segmentation'
        Options: 'binary_segmentation', 'window', 'bottom_up', 'pelt', 'bayesian', 'hmm'
    window_size : int, optional
        Window size for calculating features, default 20
    penalty : float, optional
        Penalty parameter for changepoint detection, default None (auto-determined)
    min_size : int, optional
        Minimum number of samples between change points, default 30
    return_probabilities : bool, optional
        Whether to return regime probabilities, default False
        
    Returns:
    --------
    np.ndarray or Tuple[np.ndarray, pd.DataFrame]
        Array of regime labels and (optionally) dataframe of regime probabilities
    """
    # Convert to numpy array if pandas Series
    if isinstance(price_series, pd.Series):
        dates = price_series.index
        price_series = price_series.values
    else:
        dates = np.arange(len(price_series))
    
    # Calculate features for regime detection
    features = _extract_regime_features(price_series, window_size)
    
    # Choose detection method
    if method == 'binary_segmentation':
        if not RUPTURES_AVAILABLE:
            logger.warning("ruptures package not available. Falling back to window-based detection.")
            regimes = _detect_regimes_window(features, n_regimes)
        else:
            regimes = _detect_binseg(features, n_regimes, penalty, min_size)
    
    elif method == 'window':
        regimes = _detect_regimes_window(features, n_regimes)
    
    elif method == 'bottom_up':
        if not RUPTURES_AVAILABLE:
            logger.warning("ruptures package not available. Falling back to window-based detection.")
            regimes = _detect_regimes_window(features, n_regimes)
        else:
            regimes = _detect_bottomup(features, n_regimes, penalty, min_size)
    
    elif method == 'pelt':
        if not RUPTURES_AVAILABLE:
            logger.warning("ruptures package not available. Falling back to window-based detection.")
            regimes = _detect_regimes_window(features, n_regimes)
        else:
            regimes = _detect_pelt(features, n_regimes, penalty, min_size)
    
    elif method == 'bayesian':
        if not PYMC3_AVAILABLE:
            logger.warning("pymc3 not available. Falling back to window-based detection.")
            regimes = _detect_regimes_window(features, n_regimes)
        else:
            regimes, probs = _detect_bayesian(features, n_regimes)
            if return_probabilities:
                probs_df = pd.DataFrame(probs, index=dates[-len(probs):])
                return regimes, probs_df
    
    elif method == 'hmm':
        try:
            from hmmlearn import hmm
            regimes, probs = _detect_hmm(features, n_regimes)
            if return_probabilities:
                probs_df = pd.DataFrame(probs, index=dates[-len(probs):])
                return regimes, probs_df
        except ImportError:
            logger.warning("hmmlearn not available. Falling back to window-based detection.")
            regimes = _detect_regimes_window(features, n_regimes)
    
        else:
        raise ValueError(f"Unknown method: {method}")
    
    return regimes


def _extract_regime_features(price_series: np.ndarray, window_size: int = 20) -> np.ndarray:
        """
    Extract features for regime detection.
    
    Parameters:
    -----------
    price_series : np.ndarray
        Price time series
    window_size : int, optional
        Window size for calculations, default 20
            
        Returns:
    --------
    np.ndarray
        Array of features for regime detection
    """
    n = len(price_series)
    
    # Calculate returns
    returns = np.diff(np.log(price_series))
    returns = np.append(0, returns)  # Add a 0 at the beginning to maintain length
    
    # Initialize feature array
    features = np.zeros((n - window_size + 1, 4))
    
    for i in range(window_size - 1, n):
        window = slice(i - window_size + 1, i + 1)
        
        # Calculate features in the window
        price_window = price_series[window]
        return_window = returns[window]
        
        # Trend feature: normalized slope
        x = np.arange(window_size)
        slope = np.polyfit(x, price_window, 1)[0]
        features[i - window_size + 1, 0] = slope / np.mean(price_window) * 100
        
        # Volatility feature: rolling standard deviation of returns
        features[i - window_size + 1, 1] = np.std(return_window) * np.sqrt(252)
        
        # Momentum feature: return over window
        features[i - window_size + 1, 2] = (price_window[-1] / price_window[0] - 1) * 100
        
        # Mean reversion feature: z-score of price
        mean_price = np.mean(price_window)
        std_price = np.std(price_window)
        if std_price > 0:
            features[i - window_size + 1, 3] = (price_window[-1] - mean_price) / std_price
        else:
            features[i - window_size + 1, 3] = 0
    
    # Normalize features
    for j in range(features.shape[1]):
        if np.std(features[:, j]) > 0:
            features[:, j] = (features[:, j] - np.mean(features[:, j])) / np.std(features[:, j])
    
    return features


def _detect_regimes_window(features: np.ndarray, n_regimes: int) -> np.ndarray:
        """
    Detect market regimes using window-based clustering.
    
    Parameters:
    -----------
    features : np.ndarray
        Array of features for regime detection
    n_regimes : int
        Number of regimes to identify
            
        Returns:
    --------
    np.ndarray
        Array of regime labels
    """
    from sklearn.cluster import KMeans
    
    # Fit K-means
    kmeans = KMeans(n_clusters=n_regimes, random_state=42, n_init=10)
    regimes = kmeans.fit_predict(features)
    
    # Pad with initial regime to match original length
    initial_regime = regimes[0]
    padding = np.full(len(features) - len(regimes), initial_regime)
    regimes = np.concatenate([padding, regimes])
    
    return regimes


def _detect_binseg(
    features: np.ndarray, 
    n_regimes: int, 
    penalty: float = None, 
    min_size: int = 30
) -> np.ndarray:
    """
    Detect market regimes using binary segmentation.
    
    Parameters:
    -----------
    features : np.ndarray
        Array of features for regime detection
    n_regimes : int
        Number of regimes to identify
    penalty : float, optional
        Penalty parameter for changepoint detection, default None (auto-determined)
    min_size : int, optional
        Minimum number of samples between change points, default 30
        
    Returns:
    --------
    np.ndarray
        Array of regime labels
    """
    # Initialize ruptures algorithm
    algo = rpt.Binseg(model="rbf", min_size=min_size).fit(features)
    
    # Determine penalty if not provided
    if penalty is None:
        penalty = rpt.Binseg.penalty.value
    
    # Find optimal number of changepoints
    n_bkps = n_regimes - 1  # Number of breakpoints = number of regimes - 1
    bkps = algo.predict(n_bkps=n_bkps)
    
    # Convert breakpoints to regime labels
    regimes = np.zeros(len(features), dtype=int)
    for i, (start, end) in enumerate(zip([0] + bkps[:-1], bkps)):
        regimes[start:end] = i
    
    return regimes


def _detect_bottomup(
    features: np.ndarray, 
    n_regimes: int, 
    penalty: float = None, 
    min_size: int = 30
) -> np.ndarray:
    """
    Detect market regimes using bottom-up segmentation.
    
    Parameters:
    -----------
    features : np.ndarray
        Array of features for regime detection
    n_regimes : int
        Number of regimes to identify
    penalty : float, optional
        Penalty parameter for changepoint detection, default None (auto-determined)
    min_size : int, optional
        Minimum number of samples between change points, default 30
        
    Returns:
    --------
    np.ndarray
        Array of regime labels
    """
    # Initialize ruptures algorithm
    algo = rpt.BottomUp(model="rbf", min_size=min_size).fit(features)
        
    # Determine penalty if not provided
    if penalty is None:
        penalty = rpt.BottomUp.penalty.value
    
    # Find optimal number of changepoints
    n_bkps = n_regimes - 1  # Number of breakpoints = number of regimes - 1
    bkps = algo.predict(n_bkps=n_bkps)
    
    # Convert breakpoints to regime labels
    regimes = np.zeros(len(features), dtype=int)
    for i, (start, end) in enumerate(zip([0] + bkps[:-1], bkps)):
        regimes[start:end] = i
    
    return regimes


def _detect_pelt(
    features: np.ndarray, 
    n_regimes: int, 
    penalty: float = None, 
    min_size: int = 30
) -> np.ndarray:
        """
    Detect market regimes using PELT algorithm.
    
    Parameters:
    -----------
    features : np.ndarray
        Array of features for regime detection
    n_regimes : int
        Number of regimes to identify
    penalty : float, optional
        Penalty parameter for changepoint detection, default None (auto-determined)
    min_size : int, optional
        Minimum number of samples between change points, default 30
            
        Returns:
    --------
    np.ndarray
        Array of regime labels
        """
    # Initialize ruptures algorithm with a appropriate penalty
    if penalty is None:
        penalty = 3 * np.log(len(features))  # BIC penalty
    
    algo = rpt.Pelt(model="rbf", min_size=min_size, jump=1).fit(features)
    
    # Find optimal number of changepoints
    bkps = algo.predict(pen=penalty)
        
    # If we get too many breakpoints, adjust penalty and rerun
    while len(bkps) - 1 > n_regimes and penalty < 1000:
        penalty *= 1.5
        bkps = algo.predict(pen=penalty)
        
    # If we get too few breakpoints, adjust penalty and rerun
    while len(bkps) - 1 < n_regimes and penalty > 0.1:
        penalty /= 1.5
        bkps = algo.predict(pen=penalty)
    
    # Convert breakpoints to regime labels
    regimes = np.zeros(len(features), dtype=int)
    for i, (start, end) in enumerate(zip([0] + bkps[:-1], bkps)):
        regimes[start:end] = i
    
    # If we have more regimes than requested, merge similar ones
    if len(np.unique(regimes)) > n_regimes:
        from sklearn.cluster import AgglomerativeClustering
        
        # Calculate mean feature values for each preliminary regime
        regime_features = []
        for r in np.unique(regimes):
            mask = regimes == r
            regime_features.append(np.mean(features[mask], axis=0))
        
        # Cluster the regimes
        regime_features = np.array(regime_features)
        clustering = AgglomerativeClustering(n_clusters=n_regimes).fit(regime_features)
        
        # Map original regimes to clustered regimes
        regime_map = {r: clustering.labels_[i] for i, r in enumerate(np.unique(regimes))}
        regimes = np.array([regime_map[r] for r in regimes])
    
    return regimes


def _detect_bayesian(features: np.ndarray, n_regimes: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect market regimes using Bayesian changepoint detection.
    
    Parameters:
    -----------
    features : np.ndarray
        Array of features for regime detection
    n_regimes : int
        Number of regimes to identify
            
        Returns:
    --------
    Tuple[np.ndarray, np.ndarray]
        Array of regime labels and array of regime probabilities
    """
    if not PYMC3_AVAILABLE:
        raise ImportError("pymc3 not available. Cannot use Bayesian changepoint detection.")
    
    # Use only the first feature for simplicity
    data = features[:, 0]
    
    with pm.Model() as model:
        # Define transition probability
        alpha = 1 / len(data)  # Expected changepoint every 1/alpha observations
        
        # Define changepoint prior
        changepoint_prior = pm.Beta('changepoint_prior', alpha=1, beta=alpha)
        
        # Define regime indicators (1 = changepoint, 0 = no changepoint)
        regime_indicators = pm.Bernoulli('regime_indicators', p=changepoint_prior, shape=len(data)-1)
            
        # Define regime states
        regimes = pm.math.concatenate([[0], pm.math.cumsum(regime_indicators)])
        
        # Define parameters for each regime
        means = pm.Normal('means', mu=0, sigma=1, shape=n_regimes)
        sigmas = pm.HalfNormal('sigmas', sigma=1, shape=n_regimes)
            
        # Define likelihood
        regime_idx = pm.math.clip(regimes, 0, n_regimes-1)
        mu = means[regime_idx]
        sigma = sigmas[regime_idx]
        
        # Define likelihood
        obs = pm.Normal('obs', mu=mu, sigma=sigma, observed=data)
            
        # Sample from posterior
        trace = pm.sample(1000, tune=1000, cores=1)
            
    # Extract regime indicators and compute regime probabilities
    regime_indicators_samples = trace['regime_indicators']
    regime_probs = regime_indicators_samples.mean(axis=0)
            
    # Identify changepoints
    changepoints = np.where(regime_probs > 0.5)[0] + 1
    
    # Convert changepoints to regime labels
    regimes = np.zeros(len(data), dtype=int)
    for i, cp in enumerate(changepoints):
        if i < n_regimes - 1:  # Ensure we don't exceed n_regimes
            regimes[cp:] = i + 1
    
    return regimes, regime_probs


def _detect_hmm(features: np.ndarray, n_regimes: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect market regimes using Hidden Markov Model.
    
    Parameters:
    -----------
    features : np.ndarray
        Array of features for regime detection
    n_regimes : int
        Number of regimes to identify
        
    Returns:
    --------
    Tuple[np.ndarray, np.ndarray]
        Array of regime labels and array of regime probabilities
    """
    from hmmlearn import hmm
    
    # Initialize and fit HMM
    model = hmm.GaussianHMM(
        n_components=n_regimes, 
        covariance_type="full", 
        n_iter=1000,
        random_state=42
    )
    model.fit(features)
    
    # Predict hidden states
    hidden_states = model.predict(features)
    
    # Get state probabilities
    state_probs = model.predict_proba(features)
    
    return hidden_states, state_probs


def visualize_regimes(
    price_series: Union[pd.Series, np.ndarray],
    regimes: np.ndarray,
    title: str = 'Market Regimes',
    save_path: Optional[str] = None
) -> None:
    """
    Visualize detected market regimes.
    
    Parameters:
    -----------
    price_series : pd.Series or np.ndarray
        Time series of prices
    regimes : np.ndarray
        Array of regime labels
    title : str, optional
        Plot title, default 'Market Regimes'
    save_path : str, optional
        Path to save the plot, if None then plot is displayed, default None
    """
    # Convert to pandas Series if numpy array
    if isinstance(price_series, np.ndarray):
        price_series = pd.Series(price_series)
    
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, 
                                  gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot price series
    price_series.plot(ax=ax1)
    ax1.set_ylabel('Price')
    ax1.set_title(title)
    ax1.grid(True)
    
    # Plot regimes
    unique_regimes = np.unique(regimes)
    colors = plt.cm.tab10(np.linspace(0, 1, len(unique_regimes)))
    
    # Add colored background for each regime
    for i, regime in enumerate(unique_regimes):
        mask = regimes == regime
        indices = np.where(mask)[0]
        
        if len(indices) > 0:
            start_idx = indices[0]
            if isinstance(price_series.index, pd.DatetimeIndex):
                start = price_series.index[start_idx]
            else:
                start = start_idx
            
            for j in range(len(indices) - 1):
                if indices[j + 1] != indices[j] + 1:
                    # End of continuous segment
                    end_idx = indices[j]
                    if isinstance(price_series.index, pd.DatetimeIndex):
                        end = price_series.index[end_idx]
                    else:
                        end = end_idx
                    
                    # Add colored background
                    ax1.axvspan(start, end, alpha=0.2, color=colors[i])
                    
                    # Update start for next segment
                    start_idx = indices[j + 1]
                    if isinstance(price_series.index, pd.DatetimeIndex):
                        start = price_series.index[start_idx]
                    else:
                        start = start_idx
            
            # Add last segment
            end_idx = indices[-1]
            if isinstance(price_series.index, pd.DatetimeIndex):
                end = price_series.index[end_idx]
            else:
                end = end_idx
            
            ax1.axvspan(start, end, alpha=0.2, color=colors[i])
    
    # Plot regime labels
    regime_series = pd.Series(regimes, index=price_series.index[:len(regimes)])
    regime_series.plot(ax=ax2, drawstyle='steps-post')
    ax2.set_yticks(unique_regimes)
    ax2.set_ylabel('Regime')
    ax2.grid(True)
    
    # Create legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=colors[i], alpha=0.2, label=f'Regime {regime}')
                       for i, regime in enumerate(unique_regimes)]
    ax1.legend(handles=legend_elements, loc='upper left')
    
    plt.tight_layout()
    
    # Save or display plot
    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()


def analyze_regime_transitions(
    regimes: np.ndarray, 
    returns: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, Optional[pd.DataFrame]]:
    """
    Analyze regime transitions and their impact on returns.
    
    Parameters:
    -----------
    regimes : np.ndarray
        Array of regime labels
    returns : np.ndarray, optional
        Array of returns corresponding to regime labels, default None
        
    Returns:
    --------
    Tuple[np.ndarray, Optional[pd.DataFrame]]
        Transition matrix and (if returns provided) return characteristics by regime
    """
    unique_regimes = np.unique(regimes)
    n_regimes = len(unique_regimes)
    
    # Initialize transition count matrix
    transitions = np.zeros((n_regimes, n_regimes))
    
    # Count transitions
    for i in range(len(regimes) - 1):
        curr_regime = regimes[i]
        next_regime = regimes[i + 1]
        
        curr_idx = np.where(unique_regimes == curr_regime)[0][0]
        next_idx = np.where(unique_regimes == next_regime)[0][0]
        
        transitions[curr_idx, next_idx] += 1
    
    # Convert counts to probabilities
    transition_matrix = transitions / transitions.sum(axis=1, keepdims=True)
    
    # If returns are provided, analyze returns by regime
    if returns is not None:
        regime_stats = {}
        
        for regime in unique_regimes:
            mask = regimes == regime
            regime_returns = returns[mask]
            
            stats = {
                'mean': np.mean(regime_returns),
                'std': np.std(regime_returns),
                'sharpe': np.mean(regime_returns) / np.std(regime_returns) if np.std(regime_returns) > 0 else 0,
                'count': len(regime_returns),
                'positive_pct': np.mean(regime_returns > 0),
                'negative_pct': np.mean(regime_returns < 0),
                'max': np.max(regime_returns),
                'min': np.min(regime_returns)
            }
            
            regime_stats[regime] = stats
        
        return transition_matrix, pd.DataFrame(regime_stats).T
    
    return transition_matrix, None


if __name__ == "__main__":
    # Example usage
    import yfinance as yf
    
    # Download some data
    data = yf.download('BTC-USD', start='2020-01-01', end='2023-01-01')
    price = data['Close']
    
    # Detect regimes
    regimes = detect_market_regimes(price, n_regimes=3, method='binary_segmentation')
    
    # Visualize regimes
    visualize_regimes(price, regimes, title='BTC-USD Market Regimes')
        
    # Analyze regime transitions
    returns = price.pct_change().dropna().values
    transition_matrix, regime_stats = analyze_regime_transitions(regimes[:len(returns)], returns)
    
    print("Regime Transition Matrix:")
    print(transition_matrix)
    
    print("\nRegime Statistics:")
    print(regime_stats) 