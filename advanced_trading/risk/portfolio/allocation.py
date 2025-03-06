"""
Portfolio Allocation Module

This module provides functions and classes for portfolio construction and allocation.
It implements various allocation methods to optimize portfolio weights based on risk,
return, and correlation characteristics.

The module includes:
- Hierarchical Risk Parity (HRP): A tree-based portfolio allocation method
- Risk Parity: Allocates capital to equalize risk contribution
- Minimum Variance: Minimizes portfolio volatility
- Maximum Sharpe: Maximizes risk-adjusted returns
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Callable, Any
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform
from scipy.optimize import minimize
import logging

from advanced_trading.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)


def calculate_portfolio_weights(
    returns: pd.DataFrame,
    method: str = 'hrp',
    risk_free_rate: float = 0.0,
    target_volatility: Optional[float] = None
) -> Dict[str, float]:
    """
    Calculate optimal portfolio weights based on historical returns.
    
    Args:
        returns: DataFrame of asset/strategy returns (columns=assets, index=time)
        method: Allocation method ('hrp', 'risk_parity', 'min_variance', 'max_sharpe', 'equal')
        risk_free_rate: Annual risk-free rate (decimal)
        target_volatility: Target portfolio volatility (annualized, decimal)
        
    Returns:
        Dictionary of optimal weights for each asset/strategy
    """
    allocator = PortfolioAllocator(
        method=method,
        risk_free_rate=risk_free_rate,
        target_volatility=target_volatility
    )
    
    return allocator.allocate(returns)


def rebalance_portfolio(
    current_weights: Dict[str, float],
    target_weights: Dict[str, float],
    threshold: float = 0.05
) -> Dict[str, float]:
    """
    Determine trades needed to rebalance a portfolio to target weights.
    
    Args:
        current_weights: Current portfolio weights
        target_weights: Target portfolio weights
        threshold: Minimum deviation threshold to trigger rebalance
        
    Returns:
        Dictionary of weight adjustments needed (positive = buy, negative = sell)
    """
    # Ensure all assets are in both current and target weights
    all_assets = set(list(current_weights.keys()) + list(target_weights.keys()))
    
    # Fill in missing weights with zeros
    current = {asset: current_weights.get(asset, 0.0) for asset in all_assets}
    target = {asset: target_weights.get(asset, 0.0) for asset in all_assets}
    
    # Calculate deviations
    deviations = {}
    for asset in all_assets:
        deviation = target[asset] - current[asset]
        # Only include if deviation exceeds threshold
        if abs(deviation) >= threshold:
            deviations[asset] = deviation
    
    return deviations


def calculate_portfolio_metrics(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    risk_free_rate: float = 0.0
) -> Dict[str, float]:
    """
    Calculate performance metrics for a portfolio with given weights.
    
    Args:
        weights: Dictionary of portfolio weights
        returns: DataFrame of asset returns
        risk_free_rate: Annual risk-free rate (decimal)
        
    Returns:
        Dictionary of portfolio metrics including return, volatility, and Sharpe ratio
    """
    # Convert weights to pandas series aligned with returns
    weight_series = pd.Series(0, index=returns.columns)
    for asset, weight in weights.items():
        if asset in weight_series.index:
            weight_series[asset] = weight
    
    # Ensure weights sum to 1
    if weight_series.sum() != 0:
        weight_series = weight_series / weight_series.sum()
    
    # Calculate portfolio returns
    portfolio_returns = returns.dot(weight_series)
    
    # Calculate metrics
    annual_factor = 252  # Assuming daily returns
    mean_return = portfolio_returns.mean() * annual_factor
    volatility = portfolio_returns.std() * np.sqrt(annual_factor)
    sharpe_ratio = (mean_return - risk_free_rate) / volatility if volatility > 0 else 0
    
    # Calculate max drawdown
    cumulative = (1 + portfolio_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative / running_max - 1)
    max_drawdown = drawdown.min()
    
    return {
        'return': mean_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'annual_return': mean_return,
        'annual_volatility': volatility
    }


def calculate_risk_contribution(
    weights: Dict[str, float],
    returns: pd.DataFrame
) -> Dict[str, float]:
    """
    Calculate the risk contribution of each asset in a portfolio.
    
    Args:
        weights: Dictionary of portfolio weights
        returns: DataFrame of asset returns
        
    Returns:
        Dictionary of risk contribution percentages for each asset
    """
    # Convert weights to array
    assets = list(weights.keys())
    w_array = np.array([weights[asset] for asset in assets])
    
    # Extract return data for the assets we have weights for
    filtered_returns = returns[[col for col in returns.columns if col in assets]]
    
    # Calculate covariance matrix
    cov = filtered_returns.cov().to_numpy()
    
    # Portfolio volatility
    port_vol = np.sqrt(w_array.T @ cov @ w_array)
    
    # Marginal contribution to risk
    mcr = cov @ w_array
    
    # Risk contribution
    rc = np.multiply(mcr, w_array) / port_vol
    
    # Convert to percentage
    risk_contrib = {assets[i]: rc[i] / np.sum(rc) for i in range(len(assets))}
    
    return risk_contrib


class PortfolioAllocator:
    """
    Portfolio allocation class implementing various advanced allocation methods
    including Hierarchical Risk Parity, Risk Parity, and Minimum Variance.
    
    Attributes:
        method (str): Allocation method
        risk_free_rate (float): Annual risk-free rate
        target_volatility (float): Target portfolio volatility
    """
    
    def __init__(
        self,
        method: str = 'hrp',
        risk_free_rate: float = 0.0,
        target_volatility: Optional[float] = None
    ):
        """
        Initialize the portfolio allocator.
        
        Args:
            method: Allocation method ('hrp', 'risk_parity', 'min_variance', 'max_sharpe', 'equal')
            risk_free_rate: Annual risk-free rate (decimal)
            target_volatility: Target portfolio volatility (annualized, decimal)
        """
        self.method = method.lower()
        self.risk_free_rate = risk_free_rate
        self.target_volatility = target_volatility
        
        # Validate method
        valid_methods = ['hrp', 'risk_parity', 'min_variance', 'max_sharpe', 'equal']
        if self.method not in valid_methods:
            raise ValueError(f"Method must be one of {valid_methods}")
    
    def allocate(self, returns: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate optimal portfolio weights based on historical returns.
        
        Args:
            returns: DataFrame of asset returns (columns=assets, index=time)
            
        Returns:
            Dictionary of optimal weights for each asset
        """
        # Remove columns with all NaN values
        returns = returns.dropna(axis=1, how='all')
        
        # Check if we have enough data
        if returns.empty:
            logger.error("Empty returns data provided")
            return {}
        
        if len(returns.columns) < 2:
            logger.warning("Only one asset provided, allocating 100% to it")
            return {returns.columns[0]: 1.0}
        
        # Select allocation method
        if self.method == 'hrp':
            weights = self._hierarchical_risk_parity(returns)
        elif self.method == 'risk_parity':
            weights = self._risk_parity(returns)
        elif self.method == 'min_variance':
            weights = self._minimum_variance(returns)
        elif self.method == 'max_sharpe':
            weights = self._max_sharpe(returns)
        else:  # 'equal'
            weights = self._equal_weights(returns)
        
        # Scale to target volatility if specified
        if self.target_volatility is not None:
            weights = self._scale_to_target_volatility(weights, returns)
        
        # Convert to dictionary
        weight_dict = {returns.columns[i]: weights[i] for i in range(len(weights))}
        
        return weight_dict
    
    def _hierarchical_risk_parity(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Implement the Hierarchical Risk Parity algorithm.
        
        Args:
            returns: DataFrame of asset returns
            
        Returns:
            Array of optimal weights
        """
        # Calculate covariance matrix
        cov = returns.cov().to_numpy()
        
        # Calculate distance matrix based on correlation
        corr = returns.corr().to_numpy()
        distance = np.sqrt(0.5 * (1 - corr))
        
        # Clustering
        link = linkage(squareform(distance), method='single')
        
        # Sort assets hierarchically
        sorted_idx = self._get_quasi_diag(link)
        
        # Recursive bisection
        weights = np.ones(len(returns.columns)) / len(returns.columns)  # Start with equal weights
        sorted_cov = pd.DataFrame(
            cov, 
            index=returns.columns, 
            columns=returns.columns
        ).iloc[sorted_idx, sorted_idx]
        
        # Apply recursive bisection to get weights
        self._recursive_bisection(sorted_cov, weights, list(range(len(sorted_idx))))
        
        return weights
    
    def _get_quasi_diag(self, link: np.ndarray) -> List[int]:
        """
        Sort assets based on hierarchical clustering.
        
        Args:
            link: Linkage matrix from hierarchical clustering
            
        Returns:
            Sorted list of asset indices
        """
        # Initialize sorted indices
        link_copy = link.copy()
        n = link_copy.shape[0] + 1  # Number of assets
        sorted_idx = [None] * n
        curr_idx = np.arange(n)
        
        # For each cluster, retrieve the original assets
        for i in range(link_copy.shape[0]):
            cluster1, cluster2 = int(link_copy[i, 0]), int(link_copy[i, 1])
            
            # Original format uses 0-indexed clusters; linkage in scipy uses the convention 
            # that original data points have indices [0, n-1], clusters have indices [n, 2n-2]
            if cluster1 >= n:
                cluster1 -= n
            if cluster2 >= n:
                cluster2 -= n
            
            # Sort assets
            sorted_idx[curr_idx[0]:curr_idx[0] + len(curr_idx[curr_idx == cluster1])] = curr_idx[curr_idx == cluster1]
            sorted_idx[curr_idx[0] + len(curr_idx[curr_idx == cluster1]):curr_idx[0] + len(curr_idx[curr_idx == cluster1]) + len(curr_idx[curr_idx == cluster2])] = curr_idx[curr_idx == cluster2]
            
            # Update current index
            cluster1_len = len(curr_idx[curr_idx == cluster1])
            cluster2_len = len(curr_idx[curr_idx == cluster2])
            
            curr_idx = np.delete(curr_idx, np.where(curr_idx == cluster1)[0])
            curr_idx = np.delete(curr_idx, np.where(curr_idx == cluster2)[0])
            
            # Add the new cluster
            curr_idx = np.append(curr_idx, n + i)
        
        return sorted_idx
    
    def _recursive_bisection(
        self,
        cov: pd.DataFrame,
        weights: np.ndarray,
        indices: List[int]
    ) -> None:
        """
        Recursively bisect the portfolio to allocate weights.
        
        Args:
            cov: Covariance matrix
            weights: Current weights array (modified in-place)
            indices: List of asset indices to process
        """
        # Stop recursion if we've reached a single asset
        if len(indices) <= 1:
            return
        
        # Split the cluster into two
        mid = len(indices) // 2
        left_indices = indices[:mid]
        right_indices = indices[mid:]
        
        # Calculate cluster variances
        left_var = self._get_cluster_variance(cov, left_indices)
        right_var = self._get_cluster_variance(cov, right_indices)
        
        # Adjust weights by cluster variance
        alpha = 1 - left_var / (left_var + right_var)
        
        # Update weights
        weights[left_indices] *= alpha
        weights[right_indices] *= (1 - alpha)
        
        # Recurse
        self._recursive_bisection(cov, weights, left_indices)
        self._recursive_bisection(cov, weights, right_indices)
    
    def _get_cluster_variance(self, cov: pd.DataFrame, indices: List[int]) -> float:
        """
        Calculate the variance of a cluster.
        
        Args:
            cov: Covariance matrix
            indices: List of asset indices in the cluster
            
        Returns:
            Variance of the cluster
        """
        # Extract cluster covariance matrix
        cluster_cov = cov.iloc[indices, indices].to_numpy()
        
        # Equal weights within the cluster
        w = np.ones(len(indices)) / len(indices)
        
        # Calculate cluster variance
        variance = w.T @ cluster_cov @ w
        
        return variance
    
    def _risk_parity(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Implement the Risk Parity algorithm.
        
        Args:
            returns: DataFrame of asset returns
            
        Returns:
            Array of optimal weights
        """
        # Calculate covariance matrix
        cov = returns.cov().to_numpy()
        n = len(returns.columns)
        
        # Initial weights (equal)
        x0 = np.ones(n) / n
        
        # Bounds (0 to 1)
        bounds = [(0, 1) for _ in range(n)]
        
        # Constraint: weights sum to 1
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        # Objective function: minimize the variance of risk contributions
        def objective(w):
            # Portfolio volatility
            portfolio_vol = np.sqrt(w.T @ cov @ w)
            
            # Marginal contribution to risk
            mcr = cov @ w
            
            # Risk contribution
            rc = np.multiply(mcr, w) / portfolio_vol
            
            # Variance of risk contributions
            return np.sum((rc - rc.mean())**2)
        
        # Optimize
        result = minimize(
            objective, 
            x0, 
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-9, 'disp': False}
        )
        
        # Return optimized weights
        return result.x
    
    def _minimum_variance(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Implement the Minimum Variance Portfolio algorithm.
        
        Args:
            returns: DataFrame of asset returns
            
        Returns:
            Array of optimal weights
        """
        # Calculate covariance matrix
        cov = returns.cov().to_numpy()
        n = len(returns.columns)
        
        # Initial weights (equal)
        x0 = np.ones(n) / n
        
        # Bounds (0 to 1)
        bounds = [(0, 1) for _ in range(n)]
        
        # Constraint: weights sum to 1
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        # Objective function: minimize portfolio variance
        def objective(w):
            return w.T @ cov @ w
        
        # Optimize
        result = minimize(
            objective, 
            x0, 
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-9, 'disp': False}
        )
        
        # Return optimized weights
        return result.x
    
    def _max_sharpe(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Implement the Maximum Sharpe Ratio Portfolio algorithm.
        
        Args:
            returns: DataFrame of asset returns
            
        Returns:
            Array of optimal weights
        """
        # Calculate mean returns and covariance matrix
        mean_returns = returns.mean().to_numpy() * 252  # Annualize
        cov = returns.cov().to_numpy() * 252  # Annualize
        n = len(returns.columns)
        
        # Initial weights (equal)
        x0 = np.ones(n) / n
        
        # Bounds (0 to 1)
        bounds = [(0, 1) for _ in range(n)]
        
        # Constraint: weights sum to 1
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        # Objective function: maximize Sharpe ratio (minimize negative Sharpe)
        def objective(w):
            portfolio_return = np.sum(mean_returns * w)
            portfolio_volatility = np.sqrt(w.T @ cov @ w)
            
            if portfolio_volatility == 0:
                return 0
            
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_volatility
            return -sharpe  # Minimize negative Sharpe ratio
        
        # Optimize
        result = minimize(
            objective, 
            x0, 
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-9, 'disp': False}
        )
        
        # Return optimized weights
        return result.x
    
    def _equal_weights(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Implement the Equal Weights Portfolio algorithm.
        
        Args:
            returns: DataFrame of asset returns
            
        Returns:
            Array of equal weights
        """
        n = len(returns.columns)
        return np.ones(n) / n
    
    def _scale_to_target_volatility(
        self,
        weights: np.ndarray,
        returns: pd.DataFrame
    ) -> np.ndarray:
        """
        Scale portfolio weights to achieve a target volatility.
        
        Args:
            weights: Array of portfolio weights
            returns: DataFrame of asset returns
            
        Returns:
            Array of scaled weights
        """
        # Calculate covariance matrix
        cov = returns.cov().to_numpy()
        
        # Calculate current portfolio volatility (annualized)
        current_vol = np.sqrt(weights.T @ cov @ weights) * np.sqrt(252)
        
        # Scale weights
        scale_factor = self.target_volatility / current_vol
        
        # If scaling up, check if it exceeds reasonable leverage
        if scale_factor > 3:
            logger.warning(f"Scaling factor {scale_factor:.2f} exceeds reasonable leverage. Capping at 3.")
            scale_factor = 3
        
        return weights * scale_factor
    
    def plot_hierarchical_clusters(
        self,
        returns: pd.DataFrame,
        figsize: Tuple[int, int] = (12, 8)
    ) -> plt.Figure:
        """
        Plot hierarchical clusters of assets.
        
        Args:
            returns: DataFrame of asset returns
            figsize: Figure size (width, height)
            
        Returns:
            Matplotlib figure object
        """
        # Calculate correlation matrix
        corr = returns.corr()
        
        # Calculate distance matrix
        distance = np.sqrt(0.5 * (1 - corr))
        
        # Clustering
        link = linkage(squareform(distance), method='single')
        
        # Create plot
        fig, ax = plt.subplots(figsize=figsize)
        dendrogram(link, labels=returns.columns, ax=ax)
        
        plt.title('Hierarchical Clustering of Assets')
        plt.xlabel('Assets')
        plt.ylabel('Distance')
        plt.xticks(rotation=90)
        plt.tight_layout()
        
        return fig
    
    def plot_allocations(
        self,
        weights: Dict[str, float],
        figsize: Tuple[int, int] = (10, 6)
    ) -> plt.Figure:
        """
        Plot portfolio allocations as a pie chart.
        
        Args:
            weights: Dictionary of portfolio weights
            figsize: Figure size (width, height)
            
        Returns:
            Matplotlib figure object
        """
        # Sort weights by value
        sorted_weights = {k: v for k, v in sorted(weights.items(), key=lambda item: item[1], reverse=True)}
        
        # Create plot
        fig, ax = plt.subplots(figsize=figsize)
        ax.pie(sorted_weights.values(), labels=sorted_weights.keys(), autopct='%1.1f%%')
        ax.set_title(f'Portfolio Allocation ({self.method.upper()})')
        
        return fig 