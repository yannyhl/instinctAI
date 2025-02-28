"""
Bayesian Changepoint Detection Module
-----------------------------------
Implementation of Bayesian methods for detecting changes in
statistical properties of financial time series data.

Based on academic research by Adams & MacKay (2007) and Fearnhead (2006).
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Union, Optional
from scipy import stats
from datetime import datetime, timedelta
import logging

# Configure logging
logger = logging.getLogger(__name__)

class BayesianChangepointDetector:
    """
    Bayesian Online Changepoint Detection (BOCD) implementation.
    
    This class implements the algorithm described in the paper:
    "Bayesian Online Changepoint Detection" by Adams & MacKay (2007)
    
    The algorithm detects changes in the underlying probability distribution
    of a time series in an online fashion, which makes it well-suited for
    financial time series where regimes can change unexpectedly.
    """
    
    def __init__(self, 
                hazard_function: Union[float, callable] = 0.01,
                model: str = 'normal_gamma',
                prior_params: Optional[Dict] = None):
        """
        Initialize the Bayesian Changepoint Detector.
        
        Args:
            hazard_function: Constant hazard or callable returning hazard at each time step
            model: Statistical model to use ('normal_gamma', 'normal_known_var', 'poisson', 'bernoulli')
            prior_params: Parameters for the prior distribution
        """
        self.hazard = hazard_function
        self.model_name = model
        
        # Set default prior parameters if not provided
        if prior_params is None:
            if model == 'normal_gamma':
                # For Normal-Gamma model (unknown mean and variance)
                self.prior_params = {
                    'alpha': 0.1,     # Shape parameter
                    'beta': 0.1,      # Scale parameter
                    'kappa': 0.1,     # Prior sample size for mean
                    'mu': 0.0         # Prior mean
                }
            elif model == 'normal_known_var':
                # For Normal model with known variance
                self.prior_params = {
                    'mu_0': 0.0,      # Prior mean
                    'sigma_0': 1.0,   # Prior standard deviation
                    'sigma_x': 1.0    # Known data standard deviation
                }
            elif model == 'poisson':
                # For Poisson model
                self.prior_params = {
                    'alpha': 1.0,     # Shape of Gamma prior
                    'beta': 1.0       # Rate of Gamma prior
                }
            elif model == 'bernoulli':
                # For Bernoulli model
                self.prior_params = {
                    'alpha': 1.0,     # Beta prior parameter
                    'beta': 1.0       # Beta prior parameter
                }
            else:
                raise ValueError(f"Unknown model: {model}")
        else:
            self.prior_params = prior_params
        
        # Select model for predictive probability
        if model == 'normal_gamma':
            self.model = self._predictive_normal_gamma
        elif model == 'normal_known_var':
            self.model = self._predictive_normal_known_var
        elif model == 'poisson':
            self.model = self._predictive_poisson
        elif model == 'bernoulli':
            self.model = self._predictive_bernoulli
        else:
            raise ValueError(f"Unknown model: {model}")
        
        # Initialize variables
        self.run_length_dist = None   # Current run length distribution
        self.joint_log_prob = None    # Joint log probability for each run length
        self.max_run_length = 0       # Maximum observed run length
        self.t = 0                    # Current time step
        self.sufficient_stats = []    # Sufficient statistics for each run length
    
    def _hazard_function(self, r: int) -> float:
        """
        Calculate the hazard function for run length r.
        
        The hazard function determines the probability of a changepoint
        given the current run length.
        
        Args:
            r: Current run length
            
        Returns:
            Hazard probability
        """
        if callable(self.hazard):
            return self.hazard(r)
        else:
            # Constant hazard function
            return self.hazard
    
    def _predictive_normal_gamma(self, 
                             data_point: float,
                             suff_stats: Dict) -> Tuple[float, Dict]:
        """
        Predictive distribution and updated sufficient statistics for Normal-Gamma model.
        
        Args:
            data_point: New data point
            suff_stats: Current sufficient statistics
            
        Returns:
            Tuple of (predictive probability, updated sufficient statistics)
        """
        if not suff_stats:
            # Initialize sufficient statistics using prior
            suff_stats = {
                'alpha': self.prior_params['alpha'],
                'beta': self.prior_params['beta'],
                'kappa': self.prior_params['kappa'],
                'mu': self.prior_params['mu'],
                'n': 0,
                'sum_x': 0,
                'sum_x2': 0
            }
        
        # Extract parameters
        alpha = suff_stats['alpha']
        beta = suff_stats['beta']
        kappa = suff_stats['kappa']
        mu = suff_stats['mu']
        n = suff_stats['n']
        
        # Calculate Student-t parameters
        nu = 2 * alpha
        
        # If we have more than 1 observation
        if n > 0:
            # Calculate updated variance term
            sigma2 = beta * (1 + 1 / kappa) / alpha
        else:
            # Use prior
            sigma2 = beta / alpha
        
        # Calculate predictive probability (Student's t distribution)
        pred_prob = stats.t.pdf(data_point, nu, loc=mu, scale=np.sqrt(sigma2))
        
        # Update sufficient statistics for next step
        n += 1
        kappa_new = kappa + 1
        mu_new = (kappa * mu + data_point) / kappa_new
        
        # Update sum of observations and sum of squares
        sum_x = suff_stats.get('sum_x', 0) + data_point
        sum_x2 = suff_stats.get('sum_x2', 0) + data_point**2
        
        # Update beta
        if n > 1:
            # Use incremental formula to avoid numerical issues
            beta_new = beta + 0.5 * kappa / kappa_new * (data_point - mu)**2
        else:
            beta_new = beta
        
        # Update alpha
        alpha_new = alpha + 0.5
        
        # Create new sufficient statistics dictionary
        new_suff_stats = {
            'alpha': alpha_new,
            'beta': beta_new,
            'kappa': kappa_new,
            'mu': mu_new,
            'n': n,
            'sum_x': sum_x,
            'sum_x2': sum_x2
        }
        
        return pred_prob, new_suff_stats
    
    def _predictive_normal_known_var(self, 
                                  data_point: float,
                                  suff_stats: Dict) -> Tuple[float, Dict]:
        """
        Predictive distribution and updated sufficient statistics for Normal with known variance.
        
        Args:
            data_point: New data point
            suff_stats: Current sufficient statistics
            
        Returns:
            Tuple of (predictive probability, updated sufficient statistics)
        """
        if not suff_stats:
            # Initialize sufficient statistics using prior
            suff_stats = {
                'mu': self.prior_params['mu_0'],
                'sigma': self.prior_params['sigma_0'],
                'n': 0,
                'sum_x': 0
            }
        
        # Extract parameters
        mu = suff_stats['mu']
        sigma = suff_stats['sigma']
        n = suff_stats['n']
        sigma_x = self.prior_params['sigma_x']
        
        # Calculate predictive probability (Normal distribution)
        pred_sigma2 = sigma**2 + sigma_x**2
        pred_prob = stats.norm.pdf(data_point, loc=mu, scale=np.sqrt(pred_sigma2))
        
        # Update sufficient statistics for next step
        n += 1
        sum_x = suff_stats.get('sum_x', 0) + data_point
        
        # Update posterior
        k = sigma_x**2 / (sigma**2 + sigma_x**2)
        mu_new = mu + k * (data_point - mu)
        sigma_new = np.sqrt((1 - k) * sigma**2)
        
        # Create new sufficient statistics dictionary
        new_suff_stats = {
            'mu': mu_new,
            'sigma': sigma_new,
            'n': n,
            'sum_x': sum_x
        }
        
        return pred_prob, new_suff_stats
    
    def _predictive_poisson(self, 
                        data_point: int,
                        suff_stats: Dict) -> Tuple[float, Dict]:
        """
        Predictive distribution and updated sufficient statistics for Poisson model.
        
        Args:
            data_point: New data point (count)
            suff_stats: Current sufficient statistics
            
        Returns:
            Tuple of (predictive probability, updated sufficient statistics)
        """
        if not suff_stats:
            # Initialize sufficient statistics using prior
            suff_stats = {
                'alpha': self.prior_params['alpha'],
                'beta': self.prior_params['beta'],
                'n': 0,
                'sum_x': 0
            }
        
        # Extract parameters
        alpha = suff_stats['alpha']
        beta = suff_stats['beta']
        n = suff_stats['n']
        
        # Calculate predictive probability (Negative Binomial)
        r = alpha
        p = beta / (beta + 1)
        pred_prob = stats.nbinom.pmf(data_point, r, p)
        
        # Update sufficient statistics for next step
        n += 1
        sum_x = suff_stats.get('sum_x', 0) + data_point
        alpha_new = alpha + data_point
        beta_new = beta + 1
        
        # Create new sufficient statistics dictionary
        new_suff_stats = {
            'alpha': alpha_new,
            'beta': beta_new,
            'n': n,
            'sum_x': sum_x
        }
        
        return pred_prob, new_suff_stats
    
    def _predictive_bernoulli(self, 
                          data_point: int,
                          suff_stats: Dict) -> Tuple[float, Dict]:
        """
        Predictive distribution and updated sufficient statistics for Bernoulli model.
        
        Args:
            data_point: New data point (0 or 1)
            suff_stats: Current sufficient statistics
            
        Returns:
            Tuple of (predictive probability, updated sufficient statistics)
        """
        if not suff_stats:
            # Initialize sufficient statistics using prior
            suff_stats = {
                'alpha': self.prior_params['alpha'],
                'beta': self.prior_params['beta'],
                'n': 0,
                'n_success': 0
            }
        
        # Extract parameters
        alpha = suff_stats['alpha']
        beta = suff_stats['beta']
        n = suff_stats['n']
        
        # Calculate predictive probability (Beta-Bernoulli)
        pred_prob = alpha / (alpha + beta) if data_point == 1 else beta / (alpha + beta)
        
        # Update sufficient statistics for next step
        n += 1
        n_success = suff_stats.get('n_success', 0) + (1 if data_point == 1 else 0)
        alpha_new = alpha + (1 if data_point == 1 else 0)
        beta_new = beta + (1 if data_point == 0 else 0)
        
        # Create new sufficient statistics dictionary
        new_suff_stats = {
            'alpha': alpha_new,
            'beta': beta_new,
            'n': n,
            'n_success': n_success
        }
        
        return pred_prob, new_suff_stats
    
    def update(self, data_point: float) -> None:
        """
        Update the run length distribution with a new data point.
        
        This implements the core algorithm from Adams & MacKay (2007).
        
        Args:
            data_point: New data point
        """
        # Initialize for first point
        if self.t == 0:
            # Initialize run length distribution with probability 1 at r=0
            self.run_length_dist = np.array([1.0])
            self.joint_log_prob = np.array([0.0])  # log(1) = 0
            self.sufficient_stats = [None]  # No observations yet for r=0
            self.t = 1
            
            # Process the first data point
            pred_prob, new_stats = self.model(data_point, {})
            self.sufficient_stats = [new_stats]
            return
        
        # Extend the sufficient statistics and growth distributions to include the new possible run length
        self.sufficient_stats.append(None)
        self.max_run_length += 1
        joint_log_prob = np.full(self.max_run_length + 1, -np.inf)  # log(0) = -inf
        
        # Calculate predictive probabilities for each run length
        pred_probs = np.zeros(self.max_run_length)
        new_stats = []
        
        # Process each previous run length
        for r in range(self.max_run_length):
            if self.run_length_dist[r] > 0:  # Only process if there's probability mass
                # Calculate predictive probability and updated statistics
                pred_prob, updated_stats = self.model(data_point, self.sufficient_stats[r])
                pred_probs[r] = pred_prob
                new_stats.append(updated_stats)
            else:
                # If run length has 0 probability, use placeholder
                new_stats.append(None)
                pred_probs[r] = 1.0  # Doesn't matter, will be multiplied by 0
        
        # Calculate hazard function for each run length
        hazard_vals = np.array([self._hazard_function(r) for r in range(self.max_run_length)])
        
        # Calculate growth probabilities
        growth_probs = pred_probs * (1 - hazard_vals)
        
        # Calculate changepoint probabilities
        cp_prob = np.sum(pred_probs * hazard_vals * self.run_length_dist[:-1])
        
        # Update joint log probabilities
        # For r > 0, we grow a run
        joint_log_prob[1:] = self.joint_log_prob[:-1] + np.log(growth_probs)
        
        # For r = 0, we start a new run with cp_prob
        joint_log_prob[0] = np.log(cp_prob) if cp_prob > 0 else -np.inf
        
        # Normalize
        max_log_prob = np.max(joint_log_prob)
        if not np.isfinite(max_log_prob):
            # All probabilities are 0, which shouldn't happen
            # Reset to a reasonable state (all weight on r=0)
            joint_log_prob = np.full_like(joint_log_prob, -np.inf)
            joint_log_prob[0] = 0.0
        else:
            joint_log_prob -= max_log_prob
        
        # Convert log probs back to probs
        run_length_dist = np.exp(joint_log_prob)
        
        # Normalize
        run_length_dist /= np.sum(run_length_dist)
        
        # Update the last sufficient statistics (for r=0)
        pred_prob, updated_stats = self.model(data_point, {})
        new_stats.append(updated_stats)
        
        # Update class variables
        self.run_length_dist = run_length_dist
        self.joint_log_prob = joint_log_prob
        self.sufficient_stats = new_stats
        self.t += 1
    
    def detect_changepoints(self, data: Union[List[float], np.ndarray, pd.Series],
                         threshold: float = 0.5) -> List[int]:
        """
        Detect changepoints in a data series.
        
        Args:
            data: Time series data
            threshold: Probability threshold for changepoint detection
            
        Returns:
            List of changepoint indices
        """
        # Reset detector
        self.run_length_dist = None
        self.joint_log_prob = None
        self.max_run_length = 0
        self.t = 0
        self.sufficient_stats = []
        
        # Convert data to numpy array
        if isinstance(data, pd.Series):
            data_array = data.values
        else:
            data_array = np.asarray(data)
        
        # Process each data point
        run_length_log_probs = []
        
        for x in data_array:
            self.update(x)
            # Store the run length distribution at each time step
            run_length_log_probs.append(self.joint_log_prob.copy())
        
        # Convert log probabilities to probabilities
        run_length_probs = []
        for log_probs in run_length_log_probs:
            probs = np.exp(log_probs - np.max(log_probs))
            probs /= np.sum(probs)
            run_length_probs.append(probs)
        
        # Detect changepoints
        changepoints = []
        
        for t in range(1, len(data_array)):
            # Probability of a changepoint at this time step
            cp_prob = run_length_probs[t][0]
            
            if cp_prob > threshold:
                changepoints.append(t)
        
        return changepoints
    
    def get_segments(self, data: Union[List[float], np.ndarray, pd.Series],
                  threshold: float = 0.5) -> Dict:
        """
        Get data segments based on detected changepoints.
        
        Args:
            data: Time series data
            threshold: Probability threshold for changepoint detection
            
        Returns:
            Dictionary with segment information
        """
        # Detect changepoints
        changepoints = self.detect_changepoints(data, threshold)
        
        # Convert data to numpy array for consistent indexing
        if isinstance(data, pd.Series):
            data_array = data.values
            dates = data.index
        else:
            data_array = np.asarray(data)
            dates = np.arange(len(data_array))
        
        # Create segments
        segments = []
        start_idx = 0
        
        for cp in changepoints:
            # Add segment
            if isinstance(dates[start_idx], datetime) and isinstance(dates[cp-1], datetime):
                segment = {
                    'start_date': dates[start_idx],
                    'end_date': dates[cp-1],
                    'start_idx': int(start_idx),
                    'end_idx': int(cp-1),
                    'mean': float(np.mean(data_array[start_idx:cp])),
                    'volatility': float(np.std(data_array[start_idx:cp])),
                    'length': int(cp - start_idx)
                }
            else:
                segment = {
                    'start_idx': int(start_idx),
                    'end_idx': int(cp-1),
                    'mean': float(np.mean(data_array[start_idx:cp])),
                    'volatility': float(np.std(data_array[start_idx:cp])),
                    'length': int(cp - start_idx)
                }
            
            segments.append(segment)
            start_idx = cp
        
        # Add final segment
        if start_idx < len(data_array):
            if isinstance(dates[start_idx], datetime) and isinstance(dates[-1], datetime):
                segment = {
                    'start_date': dates[start_idx],
                    'end_date': dates[-1],
                    'start_idx': int(start_idx),
                    'end_idx': int(len(data_array)-1),
                    'mean': float(np.mean(data_array[start_idx:])),
                    'volatility': float(np.std(data_array[start_idx:])),
                    'length': int(len(data_array) - start_idx)
                }
            else:
                segment = {
                    'start_idx': int(start_idx),
                    'end_idx': int(len(data_array)-1),
                    'mean': float(np.mean(data_array[start_idx:])),
                    'volatility': float(np.std(data_array[start_idx:])),
                    'length': int(len(data_array) - start_idx)
                }
            
            segments.append(segment)
        
        return {
            'changepoints': changepoints,
            'segments': segments,
            'n_segments': len(segments)
        }
    
    def plot_changepoints(self, data: Union[List[float], np.ndarray, pd.Series],
                       threshold: float = 0.5,
                       figsize: Tuple[int, int] = (12, 10)) -> plt.Figure:
        """
        Plot data with detected changepoints.
        
        Args:
            data: Time series data
            threshold: Probability threshold for changepoint detection
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        # Detect changepoints and segments
        result = self.get_segments(data, threshold)
        changepoints = result['changepoints']
        segments = result['segments']
        
        # Convert data to Series for consistent plotting
        if isinstance(data, pd.Series):
            series = data
        else:
            data_array = np.asarray(data)
            series = pd.Series(data_array)
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot data and changepoints
        ax1.plot(series.index, series.values, color='blue', alpha=0.6)
        
        # Plot segments with different colors
        colors = plt.cm.tab10(np.linspace(0, 1, len(segments)))
        
        for i, segment in enumerate(segments):
            start_idx = segment['start_idx']
            end_idx = segment['end_idx']
            
            # Plot segment
            ax1.plot(series.index[start_idx:end_idx+1], series.values[start_idx:end_idx+1], 
                    color=colors[i], linewidth=2)
            
            # Add mean line
            ax1.axhline(y=segment['mean'], color=colors[i], linestyle='--', 
                       alpha=0.7, linewidth=1)
            
            # Label segment
            if isinstance(series.index[start_idx], datetime):
                label = f"{series.index[start_idx].strftime('%Y-%m-%d')} to {series.index[end_idx].strftime('%Y-%m-%d')}"
            else:
                label = f"Segment {i+1}: {start_idx} to {end_idx}"
                
            ax1.text(series.index[start_idx + (end_idx - start_idx)//2], 
                    segment['mean'], 
                    f"μ={segment['mean']:.4f}, σ={segment['volatility']:.4f}",
                    verticalalignment='bottom', 
                    horizontalalignment='center',
                    color=colors[i])
        
        # Add changepoint markers
        for cp in changepoints:
            ax1.axvline(x=series.index[cp], color='red', linestyle='-', alpha=0.7)
            
            # Add label
            if isinstance(series.index[cp], datetime):
                ax1.text(series.index[cp], ax1.get_ylim()[1], 
                        series.index[cp].strftime('%Y-%m-%d'), 
                        rotation=90, verticalalignment='top')
            else:
                ax1.text(series.index[cp], ax1.get_ylim()[1], 
                        f"CP at {cp}", 
                        rotation=90, verticalalignment='top')
        
        ax1.set_title(f"Detected Changepoints (threshold={threshold})")
        ax1.set_ylabel("Value")
        ax1.grid(True, alpha=0.3)
        
        # Plot run length distribution heat map
        # We only have this if we've already processed the data
        if hasattr(self, 'run_length_log_probs') and self.run_length_log_probs is not None:
            run_length_probs = []
            for log_probs in self.run_length_log_probs:
                probs = np.exp(log_probs - np.max(log_probs))
                probs /= np.sum(probs)
                run_length_probs.append(probs)
            
            # Pad each array to the maximum length
            max_len = max(len(probs) for probs in run_length_probs)
            padded_probs = []
            
            for probs in run_length_probs:
                padded = np.zeros(max_len)
                padded[:len(probs)] = probs
                padded_probs.append(padded)
            
            # Create matrix of run length probabilities
            probs_matrix = np.array(padded_probs)
            
            # Plot heatmap
            im = ax2.imshow(probs_matrix.T, aspect='auto', origin='lower', 
                          interpolation='nearest', cmap='viridis')
            
            # Add colorbar
            cbar = plt.colorbar(im, ax=ax2)
            cbar.set_label('Probability')
            
            # Add changepoint markers
            for cp in changepoints:
                ax2.axvline(x=cp, color='red', linestyle='-', alpha=0.7)
            
            ax2.set_xlabel("Time")
            ax2.set_ylabel("Run Length")
            ax2.set_title("Run Length Distribution")
        else:
            ax2.text(0.5, 0.5, "Run length distribution not available.\nCall detect_changepoints() first.", 
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax2.transAxes)
        
        plt.tight_layout()
        
        return fig


def offline_bayesian_changepoint_detection(data: Union[List[float], np.ndarray, pd.Series], 
                                         threshold: float = 0.5,
                                         model: str = 'normal_gamma',
                                         hazard: float = 0.01) -> Dict:
    """
    Convenience function to run Bayesian changepoint detection on a dataset.
    
    Args:
        data: Time series data
        threshold: Probability threshold for changepoint detection
        model: Statistical model to use
        hazard: Hazard function parameter
        
    Returns:
        Dictionary with changepoints and segments
    """
    detector = BayesianChangepointDetector(hazard_function=hazard, model=model)
    return detector.get_segments(data, threshold)


def detect_market_regimes(returns: pd.Series, threshold: float = 0.5) -> Dict:
    """
    Detect market regimes in financial returns series.
    
    Args:
        returns: Financial returns series
        threshold: Probability threshold for changepoint detection
        
    Returns:
        Dictionary with regime information
    """
    # Initialize detector for volatility
    # First, calculate absolute returns as a proxy for volatility
    abs_returns = returns.abs()
    
    # For volatility, a normal-gamma model is appropriate
    vol_detector = BayesianChangepointDetector(
        hazard_function=0.01,  # Typical: 1 change per 100 days
        model='normal_gamma'
    )
    
    # Detect volatility regimes
    vol_result = vol_detector.get_segments(abs_returns, threshold)
    
    # Initialize detector for mean returns
    # For mean returns, a normal-gamma model is also appropriate
    mean_detector = BayesianChangepointDetector(
        hazard_function=0.01,
        model='normal_gamma'
    )
    
    # Detect mean regimes
    mean_result = mean_detector.get_segments(returns, threshold)
    
    # Combine changepoints
    all_cps = sorted(set(vol_result['changepoints'] + mean_result['changepoints']))
    
    # Create unified segments
    segments = []
    start_idx = 0
    
    for cp in all_cps:
        if cp > start_idx:
            segment_data = returns.iloc[start_idx:cp]
            
            segment = {
                'start_date': returns.index[start_idx],
                'end_date': returns.index[cp-1],
                'start_idx': start_idx,
                'end_idx': cp-1,
                'mean': float(segment_data.mean()),
                'volatility': float(segment_data.std()),
                'skew': float(stats.skew(segment_data.dropna())),
                'kurtosis': float(stats.kurtosis(segment_data.dropna())),
                'sharpe': float(segment_data.mean() / segment_data.std() * np.sqrt(252)) \
                          if segment_data.std() > 0 else 0,
                'length': cp - start_idx,
                'regime': classify_regime(segment_data)
            }
            
            segments.append(segment)
            start_idx = cp
    
    # Add final segment
    if start_idx < len(returns):
        segment_data = returns.iloc[start_idx:]
        
        segment = {
            'start_date': returns.index[start_idx],
            'end_date': returns.index[-1],
            'start_idx': start_idx,
            'end_idx': len(returns)-1,
            'mean': float(segment_data.mean()),
            'volatility': float(segment_data.std()),
            'skew': float(stats.skew(segment_data.dropna())),
            'kurtosis': float(stats.kurtosis(segment_data.dropna())),
            'sharpe': float(segment_data.mean() / segment_data.std() * np.sqrt(252)) \
                      if segment_data.std() > 0 else 0,
            'length': len(returns) - start_idx,
            'regime': classify_regime(segment_data)
        }
        
        segments.append(segment)
    
    return {
        'changepoints': all_cps,
        'segments': segments,
        'n_segments': len(segments),
        'vol_changepoints': vol_result['changepoints'],
        'mean_changepoints': mean_result['changepoints']
    }


def classify_regime(returns: pd.Series) -> str:
    """
    Classify a market regime based on statistical properties.
    
    Args:
        returns: Financial returns series
        
    Returns:
        Regime classification
    """
    # Calculate key statistics
    mean_return = returns.mean()
    volatility = returns.std()
    skew = stats.skew(returns.dropna())
    kurtosis = stats.kurtosis(returns.dropna())
    
    # Annualize mean and volatility
    mean_annual = mean_return * 252
    vol_annual = volatility * np.sqrt(252)
    
    # Classify based on mean and volatility
    if mean_annual > 0.15:  # High returns
        if vol_annual > 0.25:  # High volatility
            regime = "Bull-Volatile"
        else:  # Low volatility
            regime = "Bull-Stable"
    elif mean_annual > 0:  # Moderate positive returns
        if vol_annual > 0.25:  # High volatility
            regime = "Choppy-Bullish"
        else:  # Low volatility
            regime = "Slow-Bullish"
    elif mean_annual > -0.15:  # Moderate negative returns
        if vol_annual > 0.25:  # High volatility
            regime = "Choppy-Bearish"
        else:  # Low volatility
            regime = "Slow-Bearish"
    else:  # High negative returns
        if vol_annual > 0.25:  # High volatility
            regime = "Bear-Volatile"
        else:  # Low volatility
            regime = "Bear-Stable"
    
    # Refine based on higher moments
    if abs(skew) > 1:
        regime += "-Skewed"
    
    if kurtosis > 3:
        regime += "-Fat-Tailed"
    
    return regime


def plot_market_regimes(returns: pd.Series, 
                     threshold: float = 0.5,
                     figsize: Tuple[int, int] = (15, 10)) -> plt.Figure:
    """
    Plot market regimes detected in returns series.
    
    Args:
        returns: Financial returns series
        threshold: Probability threshold for changepoint detection
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    # Detect regimes
    result = detect_market_regimes(returns, threshold)
    segments = result['segments']
    changepoints = result['changepoints']
    
    # Calculate cumulative returns
    cum_returns = (1 + returns).cumprod()
    
    # Create figure
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=figsize, 
                                      gridspec_kw={'height_ratios': [3, 1, 1]})
    
    # Plot cumulative returns
    ax1.plot(cum_returns.index, cum_returns.values, color='gray', alpha=0.6, linewidth=1)
    
    # Plot segments with different colors
    colors = plt.cm.tab10(np.linspace(0, 1, len(segments)))
    
    for i, segment in enumerate(segments):
        start_idx = segment['start_idx']
        end_idx = segment['end_idx']
        regime = segment['regime']
        
        # Plot segment
        ax1.plot(cum_returns.index[start_idx:end_idx+1], 
                cum_returns.values[start_idx:end_idx+1], 
                color=colors[i], linewidth=2)
        
        # Add regime label
        ax1.text(cum_returns.index[start_idx + (end_idx - start_idx)//2], 
                cum_returns.values[start_idx + (end_idx - start_idx)//2],
                regime,
                verticalalignment='bottom', 
                horizontalalignment='center',
                color=colors[i], fontweight='bold')
    
    # Add changepoint markers
    for cp in changepoints:
        ax1.axvline(x=cum_returns.index[cp], color='red', linestyle='--', alpha=0.7)
    
    ax1.set_title(f"Market Regimes (threshold={threshold})")
    ax1.set_ylabel("Cumulative Return")
    ax1.grid(True, alpha=0.3)
    
    # Plot returns
    ax2.plot(returns.index, returns.values, color='gray', alpha=0.7)
    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.2)
    
    # Shade segments with different colors
    for i, segment in enumerate(segments):
        start_idx = segment['start_idx']
        end_idx = segment['end_idx']
        
        # Calculate shading y limits
        y_min, y_max = ax2.get_ylim()
        
        # Shade segment
        ax2.fill_between(returns.index[start_idx:end_idx+1], y_min, y_max,
                       color=colors[i], alpha=0.2)
    
    # Add changepoint markers
    for cp in changepoints:
        ax2.axvline(x=returns.index[cp], color='red', linestyle='--', alpha=0.7)
    
    ax2.set_ylabel("Returns")
    ax2.grid(True, alpha=0.3)
    
    # Plot volatility (rolling standard deviation)
    window = 21  # 21-day rolling window
    rolling_vol = returns.rolling(window=window).std() * np.sqrt(252)  # Annualized
    
    ax3.plot(rolling_vol.index, rolling_vol.values, color='gray', alpha=0.7)
    
    # Shade segments with different colors
    for i, segment in enumerate(segments):
        start_idx = segment['start_idx']
        end_idx = segment['end_idx']
        
        # Calculate shading y limits
        y_min, y_max = ax3.get_ylim()
        
        # Shade segment
        ax3.fill_between(rolling_vol.index[start_idx:end_idx+1], y_min, y_max,
                       color=colors[i], alpha=0.2)
    
    # Add changepoint markers
    for cp in changepoints:
        ax3.axvline(x=rolling_vol.index[cp], color='red', linestyle='--', alpha=0.7)
    
    ax3.set_xlabel("Date")
    ax3.set_ylabel("Volatility")
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    return fig 