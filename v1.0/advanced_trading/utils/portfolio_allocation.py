"""
Portfolio Allocation Module
--------------------------
Advanced portfolio construction and allocation techniques for multi-strategy systems.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Callable
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform
import logging

# Configure logging
logger = logging.getLogger(__name__)

class PortfolioAllocator:
    """
    Portfolio allocation class implementing various advanced allocation methods
    including Hierarchical Risk Parity, Risk Parity, and Minimum Variance.
    """
    
    def __init__(self, method: str = 'hrp', 
                risk_free_rate: float = 0.02,
                target_volatility: Optional[float] = None):
        """
        Initialize the portfolio allocator.
        
        Args:
            method: Allocation method ('hrp', 'risk_parity', 'min_variance', 'equal')
            risk_free_rate: Annual risk-free rate as decimal
            target_volatility: Target portfolio volatility (optional)
        """
        self.method = method.lower()
        self.risk_free_rate = risk_free_rate
        self.target_volatility = target_volatility
        
        # Validate method
        valid_methods = ['hrp', 'risk_parity', 'min_variance', 'equal', 'sharpe_maximizing']
        if self.method not in valid_methods:
            raise ValueError(f"Method must be one of {valid_methods}")
    
    def allocate(self, returns: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate optimal portfolio weights based on historical returns.
        
        Args:
            returns: DataFrame of strategy/asset returns (columns=strategies, index=time)
            
        Returns:
            Dictionary mapping strategy names to allocation weights
        """
        # Handle empty or NaN returns
        if returns.empty or returns.isna().all().all():
            logger.warning("Empty or all-NaN returns provided, defaulting to equal weights")
            return {col: 1.0/len(returns.columns) for col in returns.columns}
        
        # Fill NaN values with 0 to avoid calculation errors
        returns_filled = returns.fillna(0)
        
        # Apply selected allocation method
        if self.method == 'hrp':
            weights = self._hierarchical_risk_parity(returns_filled)
        elif self.method == 'risk_parity':
            weights = self._risk_parity(returns_filled)
        elif self.method == 'min_variance':
            weights = self._minimum_variance(returns_filled)
        elif self.method == 'sharpe_maximizing':
            weights = self._sharpe_maximizing(returns_filled)
        else:  # equal weights
            weights = self._equal_weights(returns_filled)
        
        # Scale to target volatility if specified
        if self.target_volatility is not None:
            weights = self._scale_to_target_volatility(weights, returns_filled)
        
        # Create dictionary of allocations
        return {col: float(weights[i]) for i, col in enumerate(returns.columns)}
    
    def _hierarchical_risk_parity(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Implement Hierarchical Risk Parity (Lopez de Prado) for portfolio allocation.
        
        Args:
            returns: DataFrame of strategy/asset returns
            
        Returns:
            Array of portfolio weights
        """
        # Calculate covariance matrix
        cov = returns.cov()
        
        # Calculate correlation matrix
        corr = returns.corr()
        
        # Convert correlation to distance matrix
        dist = np.sqrt(0.5 * (1 - corr))
        
        # Perform hierarchical clustering
        link = linkage(squareform(dist), 'single')
        
        # Get quasi-diagonalization order
        sortIx = self._get_quasi_diag(link)
        sortIx = sortIx.astype(int)
        
        # Recover original indices
        sortIx = {int(sortIx[i]): i for i in range(len(sortIx))}
        
        # Sort covariance matrix
        sorted_cov = cov.iloc[list(sortIx.keys())].iloc[:, list(sortIx.keys())]
        
        # Calculate HRP weights
        weights = self._get_recursive_bisection(sorted_cov)
        
        # Reorder weights to match original order
        weights = np.array([weights[sortIx[i]] for i in range(len(weights))])
        
        return weights
    
    def _get_quasi_diag(self, link: np.ndarray) -> np.ndarray:
        """
        Sort clustered items by distance.
        
        Args:
            link: Linkage matrix from hierarchical clustering
            
        Returns:
            Sorted index array
        """
        link = link.astype(int)
        # Number of original items
        n = link[-1, 3]
        
        # Initialize with direct (non-clustered) items
        ret = np.arange(n)
        
        # Add clustered items
        for i in range(len(link)):
            c1, c2 = link[i, 0], link[i, 1]
            if c1 >= n:  # c1 is a cluster
                c1 -= n
                ret = np.append(ret, ret[c1])
                ret = np.delete(ret, c1)
            if c2 >= n:  # c2 is a cluster
                c2 -= n
                ret = np.append(ret, ret[c2])
                ret = np.delete(ret, c2)
        
        return ret
    
    def _get_recursive_bisection(self, cov: pd.DataFrame) -> np.ndarray:
        """
        Compute HRP weights using recursive bisection algorithm.
        
        Args:
            cov: Covariance matrix (sorted)
            
        Returns:
            HRP weights
        """
        # Initialize weights
        w = np.ones(cov.shape[0])
        
        # Start recursive bisection
        self._recursive_bisection(cov, w)
        
        return w
    
    def _recursive_bisection(self, cov: pd.DataFrame, w: np.ndarray, 
                           indices: Optional[List[int]] = None) -> None:
        """
        Perform recursive bisection for HRP.
        
        Args:
            cov: Covariance matrix
            w: Weight vector to be updated in-place
            indices: Subset of indices to process (for recursion)
        """
        if indices is None:
            indices = list(range(cov.shape[0]))
        
        # If only one asset, return
        if len(indices) <= 1:
            return
        
        # Split into two clusters
        mid = len(indices) // 2
        left_indices = indices[:mid]
        right_indices = indices[mid:]
        
        # Calculate variance of clusters
        var_left = self._get_cluster_variance(cov, left_indices)
        var_right = self._get_cluster_variance(cov, right_indices)
        
        # Calculate alpha (relative size)
        alpha = 1 - var_left / (var_left + var_right)
        
        # Update weights
        w[left_indices] *= alpha
        w[right_indices] *= (1 - alpha)
        
        # Recurse
        self._recursive_bisection(cov, w, left_indices)
        self._recursive_bisection(cov, w, right_indices)
    
    def _get_cluster_variance(self, cov: pd.DataFrame, indices: List[int]) -> float:
        """
        Calculate variance of a cluster.
        
        Args:
            cov: Covariance matrix
            indices: Indices of the cluster
            
        Returns:
            Cluster variance
        """
        if len(indices) == 0:
            return 0
        
        # Extract subcovariance matrix
        sub_cov = cov.iloc[indices, indices]
        
        # Calculate equal-weight variance
        n = len(indices)
        w = np.ones(n) / n
        variance = np.dot(w, np.dot(sub_cov, w))
        
        return variance
    
    def _risk_parity(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Calculate Risk Parity weights (equal risk contribution).
        
        Args:
            returns: DataFrame of strategy/asset returns
            
        Returns:
            Array of portfolio weights
        """
        cov = returns.cov().values
        n = len(returns.columns)
        
        # Initial weights
        weights = np.ones(n) / n
        
        # Risk Parity optimization 
        # Using simple iterative approach for risk parity
        max_iter = 1000
        tol = 1e-8
        
        for _ in range(max_iter):
            # Calculate portfolio risk
            portfolio_risk = np.sqrt(np.dot(weights, np.dot(cov, weights)))
            
            # Calculate risk contribution of each asset
            marginal_risk = np.dot(cov, weights) / portfolio_risk
            risk_contribution = weights * marginal_risk
            
            # Calculate risk contribution target (equal for all assets)
            target_risk = portfolio_risk / n
            
            # Calculate weight adjustments
            adjustment = target_risk / risk_contribution
            
            # Apply adjustments
            new_weights = weights * adjustment
            
            # Normalize
            new_weights = new_weights / np.sum(new_weights)
            
            # Check convergence
            if np.max(np.abs(new_weights - weights)) < tol:
                break
                
            weights = new_weights
        
        return weights
    
    def _minimum_variance(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Calculate Minimum Variance portfolio weights.
        
        Args:
            returns: DataFrame of strategy/asset returns
            
        Returns:
            Array of portfolio weights
        """
        cov = returns.cov().values
        n = len(returns.columns)
        
        # Solve minimum variance optimization problem
        try:
            # Invert covariance matrix
            inv_cov = np.linalg.inv(cov)
            
            # Calculate weights
            ones = np.ones(n)
            weights = np.dot(inv_cov, ones) / np.dot(ones, np.dot(inv_cov, ones))
            
            # Handle negative weights (optional - can be removed for short positions)
            if np.any(weights < 0):
                logger.warning("Negative weights in minimum variance solution. Applying constraints.")
                weights = self._constrained_minimum_variance(cov)
                
        except np.linalg.LinAlgError:
            logger.warning("Singular covariance matrix. Using diagonal approximation.")
            # Use diagonal approximation
            diag_cov = np.diag(np.diag(cov))
            inv_diag = np.linalg.inv(diag_cov)
            weights = np.dot(inv_diag, np.ones(n))
            weights = weights / np.sum(weights)
        
        return weights
    
    def _constrained_minimum_variance(self, cov: np.ndarray) -> np.ndarray:
        """
        Calculate minimum variance weights with non-negative constraint.
        
        Args:
            cov: Covariance matrix
            
        Returns:
            Array of portfolio weights
        """
        from scipy.optimize import minimize
        
        n = cov.shape[0]
        
        # Define objective function
        def objective(weights):
            return np.dot(weights, np.dot(cov, weights))
        
        # Define constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Sum of weights = 1
        ]
        
        # Define bounds (non-negative weights)
        bounds = [(0, 1) for _ in range(n)]
        
        # Initial guess (equal weights)
        initial_weights = np.ones(n) / n
        
        # Solve optimization problem
        result = minimize(objective, initial_weights, method='SLSQP', 
                         bounds=bounds, constraints=constraints)
        
        if result.success:
            return result.x
        else:
            logger.warning(f"Optimization failed: {result.message}. Using equal weights.")
            return np.ones(n) / n
    
    def _sharpe_maximizing(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Calculate weights that maximize the Sharpe ratio.
        
        Args:
            returns: DataFrame of strategy/asset returns
            
        Returns:
            Array of portfolio weights
        """
        from scipy.optimize import minimize
        
        n = len(returns.columns)
        
        # Calculate mean returns and covariance
        mean_returns = returns.mean().values * 252  # Annualized returns
        cov_matrix = returns.cov().values * 252  # Annualized covariance
        
        # Define objective function to minimize (negative Sharpe ratio)
        def objective(weights):
            portfolio_return = np.sum(mean_returns * weights)
            portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility
            return -sharpe_ratio
        
        # Define constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Sum of weights = 1
        ]
        
        # Define bounds (non-negative weights)
        bounds = [(0, 1) for _ in range(n)]
        
        # Initial guess (equal weights)
        initial_weights = np.ones(n) / n
        
        # Solve optimization problem
        result = minimize(objective, initial_weights, method='SLSQP', 
                         bounds=bounds, constraints=constraints)
        
        if result.success:
            return result.x
        else:
            logger.warning(f"Sharpe maximization failed: {result.message}. Using equal weights.")
            return np.ones(n) / n
    
    def _equal_weights(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Calculate equal weights (1/N portfolio).
        
        Args:
            returns: DataFrame of strategy/asset returns
            
        Returns:
            Array of equal portfolio weights
        """
        n = len(returns.columns)
        return np.ones(n) / n
    
    def _scale_to_target_volatility(self, weights: np.ndarray, 
                                  returns: pd.DataFrame) -> np.ndarray:
        """
        Scale weights to match target portfolio volatility.
        
        Args:
            weights: Portfolio weights
            returns: DataFrame of strategy/asset returns
            
        Returns:
            Scaled portfolio weights
        """
        cov = returns.cov().values
        portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov, weights))) * np.sqrt(252)
        
        if portfolio_vol > 0:
            # Calculate the scaling factor
            scaling = self.target_volatility / portfolio_vol
            
            # Scale the weights
            scaled_weights = weights * scaling
            
            # If scaling > 1, it implies leverage
            if scaling > 1:
                logger.info(f"Applying leverage of {scaling:.2f}x to reach target volatility")
            
            return scaled_weights
        else:
            return weights
    
    def plot_hierarchical_clusters(self, returns: pd.DataFrame, 
                                figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Plot hierarchical clustering dendrogram for portfolio assets.
        
        Args:
            returns: DataFrame of strategy/asset returns
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        # Calculate correlation matrix
        corr = returns.corr()
        
        # Calculate distance matrix
        dist = np.sqrt(0.5 * (1 - corr))
        
        # Perform hierarchical clustering
        link = linkage(squareform(dist), 'single')
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot dendrogram
        dendrogram(link, labels=returns.columns, ax=ax, leaf_rotation=90)
        
        ax.set_title('Hierarchical Clustering of Assets')
        ax.set_xlabel('Assets')
        ax.set_ylabel('Distance')
        
        plt.tight_layout()
        
        return fig
    
    def plot_allocations(self, allocations: Dict[str, float], 
                       figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Plot portfolio allocations as a pie chart and bar chart.
        
        Args:
            allocations: Dictionary of strategy/asset allocations
            figsize: Figure size
            
        Returns:
            Matplotlib figure with pie and bar charts
        """
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Sort allocations by value
        sorted_alloc = {k: v for k, v in sorted(allocations.items(), 
                                             key=lambda item: item[1], reverse=True)}
        
        # Create pie chart
        labels = list(sorted_alloc.keys())
        sizes = list(sorted_alloc.values())
        
        ax1.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
        ax1.set_title('Portfolio Allocation (Pie Chart)')
        
        # Create bar chart
        ax2.barh(labels, sizes)
        ax2.set_title('Portfolio Allocation (Bar Chart)')
        ax2.set_xlabel('Weight')
        
        plt.tight_layout()
        
        return fig
    
    def calculate_allocation_risk_contribution(self, allocations: Dict[str, float], 
                                            returns: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate risk contribution of each asset in the portfolio.
        
        Args:
            allocations: Dictionary of strategy/asset allocations
            returns: DataFrame of strategy/asset returns
            
        Returns:
            Dictionary of risk contributions
        """
        # Convert allocations to array
        weights = np.array([allocations[col] for col in returns.columns])
        
        # Calculate covariance matrix
        cov = returns.cov().values
        
        # Calculate portfolio risk
        portfolio_risk = np.sqrt(np.dot(weights, np.dot(cov, weights)))
        
        # Calculate risk contribution
        marginal_risk = np.dot(cov, weights)
        risk_contribution = weights * marginal_risk / portfolio_risk
        
        # Calculate percentage risk contribution
        percent_risk_contribution = risk_contribution / np.sum(risk_contribution)
        
        # Create dictionary of risk contributions
        return {col: float(percent_risk_contribution[i]) for i, col in enumerate(returns.columns)}
    
    def plot_risk_contribution(self, allocations: Dict[str, float], 
                             returns: pd.DataFrame,
                             figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Plot risk contribution of each asset.
        
        Args:
            allocations: Dictionary of strategy/asset allocations
            returns: DataFrame of strategy/asset returns
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        # Calculate risk contributions
        risk_contrib = self.calculate_allocation_risk_contribution(allocations, returns)
        
        # Sort by risk contribution
        sorted_risk = {k: v for k, v in sorted(risk_contrib.items(), 
                                           key=lambda item: item[1], reverse=True)}
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Create bar chart
        labels = list(sorted_risk.keys())
        sizes = list(sorted_risk.values())
        
        ax.barh(labels, sizes)
        ax.set_title('Risk Contribution by Asset')
        ax.set_xlabel('Percent of Total Risk')
        
        # Add percent labels
        for i, v in enumerate(sizes):
            ax.text(v + 0.01, i, f"{v:.1%}", va='center')
        
        plt.tight_layout()
        
        return fig


def allocate_portfolio(returns: pd.DataFrame, method: str = 'hrp', 
                    target_volatility: Optional[float] = None) -> Dict[str, float]:
    """
    Convenience function to allocate portfolio using specified method.
    
    Args:
        returns: DataFrame of strategy/asset returns
        method: Allocation method ('hrp', 'risk_parity', 'min_variance', 'equal')
        target_volatility: Target annualized volatility (optional)
        
    Returns:
        Dictionary of allocations by strategy/asset
    """
    allocator = PortfolioAllocator(method=method, target_volatility=target_volatility)
    return allocator.allocate(returns)


def calculate_portfolio_performance(weights: Dict[str, float], 
                                 returns: pd.DataFrame,
                                 risk_free_rate: float = 0.02) -> Dict[str, float]:
    """
    Calculate portfolio performance metrics.
    
    Args:
        weights: Dictionary of strategy/asset allocations
        returns: DataFrame of strategy/asset returns
        risk_free_rate: Annual risk-free rate as decimal
        
    Returns:
        Dictionary of performance metrics
    """
    # Convert weights to array in same order as returns columns
    weight_array = np.array([weights.get(col, 0) for col in returns.columns])
    
    # Calculate portfolio returns
    portfolio_returns = returns.dot(weight_array)
    
    # Calculate performance metrics
    ann_return = portfolio_returns.mean() * 252
    ann_volatility = portfolio_returns.std() * np.sqrt(252)
    sharpe_ratio = (ann_return - risk_free_rate) / ann_volatility if ann_volatility > 0 else 0
    
    # Calculate drawdown
    cumulative_returns = (1 + portfolio_returns).cumprod()
    peak = cumulative_returns.cummax()
    drawdown = (cumulative_returns - peak) / peak
    max_drawdown = drawdown.min()
    
    # Calculate Calmar ratio
    calmar_ratio = abs(ann_return / max_drawdown) if max_drawdown < 0 else np.inf
    
    # Calculate Sortino ratio (downside risk)
    negative_returns = portfolio_returns[portfolio_returns < 0]
    downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
    sortino_ratio = (ann_return - risk_free_rate) / downside_deviation if downside_deviation > 0 else np.inf
    
    return {
        'annualized_return': float(ann_return),
        'annualized_volatility': float(ann_volatility),
        'sharpe_ratio': float(sharpe_ratio),
        'max_drawdown': float(max_drawdown),
        'calmar_ratio': float(calmar_ratio),
        'sortino_ratio': float(sortino_ratio)
    }


def compare_allocation_methods(returns: pd.DataFrame, 
                            methods: List[str] = ['hrp', 'risk_parity', 'min_variance', 'equal'],
                            target_volatility: Optional[float] = None,
                            risk_free_rate: float = 0.02) -> Dict[str, Dict]:
    """
    Compare different portfolio allocation methods.
    
    Args:
        returns: DataFrame of strategy/asset returns
        methods: List of allocation methods to compare
        target_volatility: Target annualized volatility (optional)
        risk_free_rate: Annual risk-free rate as decimal
        
    Returns:
        Dictionary with allocation weights and performance for each method
    """
    results = {}
    
    for method in methods:
        # Allocate portfolio
        allocator = PortfolioAllocator(method=method, 
                                     risk_free_rate=risk_free_rate,
                                     target_volatility=target_volatility)
        weights = allocator.allocate(returns)
        
        # Calculate performance
        performance = calculate_portfolio_performance(weights, returns, risk_free_rate)
        
        # Calculate risk contribution
        risk_contrib = allocator.calculate_allocation_risk_contribution(weights, returns)
        
        # Store results
        results[method] = {
            'weights': weights,
            'performance': performance,
            'risk_contribution': risk_contrib
        }
    
    return results


def plot_allocation_comparison(comparison_results: Dict[str, Dict],
                            figsize: Tuple[int, int] = (15, 10)) -> plt.Figure:
    """
    Plot comparison of different allocation methods.
    
    Args:
        comparison_results: Results from compare_allocation_methods
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    methods = list(comparison_results.keys())
    metrics = ['sharpe_ratio', 'annualized_return', 'annualized_volatility', 'max_drawdown']
    
    # Create figure
    fig, axs = plt.subplots(2, 2, figsize=figsize)
    axs = axs.flatten()
    
    # Plot metrics
    for i, metric in enumerate(metrics):
        values = [comparison_results[method]['performance'][metric] for method in methods]
        
        # Handle negative values for drawdown
        if metric == 'max_drawdown':
            values = [-v for v in values]  # Make positive for better visualization
        
        axs[i].bar(methods, values)
        axs[i].set_title(f'{metric.replace("_", " ").title()}')
        axs[i].set_xticklabels(methods, rotation=45)
        
        # Add value labels
        for j, v in enumerate(values):
            if metric == 'max_drawdown':
                axs[i].text(j, v/2, f"{-values[j]:.2%}", ha='center')
            elif metric in ['annualized_return', 'annualized_volatility']:
                axs[i].text(j, v/2, f"{values[j]:.2%}", ha='center')
            else:
                axs[i].text(j, v/2, f"{values[j]:.2f}", ha='center')
    
    plt.tight_layout()
    
    return fig 