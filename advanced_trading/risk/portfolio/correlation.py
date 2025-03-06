"""
Portfolio Correlation Module

This module provides functions for analyzing and managing correlations between assets
in a portfolio. Correlation analysis is essential for portfolio diversification and 
risk management.

The module includes functions for:
- Calculating correlation matrices
- Identifying correlation clusters
- Detecting correlation changes over time
- Visualizing correlation structures
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform

from advanced_trading.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)


def calculate_correlation_matrix(
    returns: pd.DataFrame,
    method: str = 'pearson',
    min_periods: Optional[int] = None
) -> pd.DataFrame:
    """
    Calculate the correlation matrix between assets.
    
    Args:
        returns: DataFrame of asset returns (columns=assets, index=time)
        method: Correlation method ('pearson', 'spearman', or 'kendall')
        min_periods: Minimum number of observations required to calculate correlation
        
    Returns:
        DataFrame containing the correlation matrix
    """
    # Validate inputs
    if returns.empty:
        logger.warning("Empty returns data provided")
        return pd.DataFrame()
    
    if method not in ['pearson', 'spearman', 'kendall']:
        logger.warning(f"Invalid correlation method: {method}, using pearson")
        method = 'pearson'
    
    # Calculate correlation matrix
    corr_matrix = returns.corr(method=method, min_periods=min_periods)
    
    return corr_matrix


def detect_correlation_changes(
    returns: pd.DataFrame,
    window_size: int = 63,  # ~3 months of trading days
    overlap: int = 21,  # ~1 month overlap
    threshold: float = 0.3  # Significant correlation change threshold
) -> Dict[str, Any]:
    """
    Detect significant changes in correlations over time.
    
    Args:
        returns: DataFrame of asset returns (columns=assets, index=time)
        window_size: Size of rolling window (in time periods)
        overlap: Number of periods to overlap between windows
        threshold: Threshold for significant correlation change
        
    Returns:
        Dictionary containing changes in correlations and their significance
    """
    # Validate inputs
    if returns.shape[0] < window_size:
        logger.warning(f"Returns data has fewer periods ({returns.shape[0]}) than window size ({window_size})")
        window_size = min(30, returns.shape[0])
    
    # Get time windows with specified overlap
    periods = returns.shape[0]
    windows = []
    
    for i in range(0, periods - window_size + 1, max(1, window_size - overlap)):
        end_idx = min(i + window_size, periods)
        windows.append((i, end_idx))
    
    # Calculate correlation matrix for each window
    window_correlations = []
    window_dates = []
    
    for start_idx, end_idx in windows:
        window_returns = returns.iloc[start_idx:end_idx]
        window_corr = window_returns.corr()
        window_correlations.append(window_corr)
        window_dates.append(returns.index[end_idx - 1])  # Use end date of window
    
    # Find pairs with significant correlation changes
    significant_changes = {}
    
    if len(window_correlations) >= 2:
        first_corr = window_correlations[0]
        last_corr = window_correlations[-1]
        
        for asset1 in returns.columns:
            for asset2 in returns.columns:
                if asset1 >= asset2:  # Only look at upper triangle
                    continue
                
                start_correlation = first_corr.loc[asset1, asset2]
                end_correlation = last_corr.loc[asset1, asset2]
                correlation_change = end_correlation - start_correlation
                
                if abs(correlation_change) >= threshold:
                    significant_changes[(asset1, asset2)] = {
                        'start_correlation': start_correlation,
                        'end_correlation': end_correlation,
                        'change': correlation_change,
                        'start_date': returns.index[0],
                        'end_date': returns.index[-1]
                    }
    
    # Organize results
    result = {
        'window_correlations': window_correlations,
        'window_dates': window_dates,
        'significant_changes': significant_changes
    }
    
    return result


def identify_correlation_clusters(
    correlation_matrix: pd.DataFrame,
    threshold: float = 0.7
) -> Dict[str, List[str]]:
    """
    Identify clusters of highly correlated assets.
    
    Args:
        correlation_matrix: Correlation matrix between assets
        threshold: Correlation threshold for cluster identification
        
    Returns:
        Dictionary mapping cluster IDs to lists of assets in each cluster
    """
    # Validate inputs
    if correlation_matrix.empty:
        logger.warning("Empty correlation matrix provided")
        return {}
    
    # Convert correlation matrix to distance matrix
    # Distance = 1 - |correlation|
    distance_matrix = 1 - np.abs(correlation_matrix)
    
    # Perform hierarchical clustering
    try:
        # Calculate linkage matrix
        link = linkage(squareform(distance_matrix), method='average')
        
        # Cut the tree at the specified threshold
        clusters = {}
        n = len(correlation_matrix.columns)
        
        # Process linkage matrix to find clusters
        cluster_id = 0
        asset_to_cluster = {asset: None for asset in correlation_matrix.columns}
        
        # Start with each asset in its own cluster
        for i, asset in enumerate(correlation_matrix.columns):
            asset_to_cluster[asset] = i
        
        # Merge clusters based on linkage matrix
        for i in range(len(link)):
            cluster1 = int(link[i, 0])
            cluster2 = int(link[i, 1])
            distance = link[i, 2]
            
            # If the distance is less than our threshold, merge the clusters
            if distance < (1 - threshold):
                # Find all assets in cluster1 and cluster2
                assets_in_cluster1 = [a for a, c in asset_to_cluster.items() if c == cluster1]
                assets_in_cluster2 = [a for a, c in asset_to_cluster.items() if c == cluster2]
                
                # Create a new merged cluster
                new_cluster_id = n + i
                
                # Update cluster assignments
                for asset in assets_in_cluster1 + assets_in_cluster2:
                    asset_to_cluster[asset] = new_cluster_id
        
        # Group assets by cluster
        cluster_to_assets = {}
        for asset, cluster in asset_to_cluster.items():
            if cluster not in cluster_to_assets:
                cluster_to_assets[cluster] = []
            cluster_to_assets[cluster].append(asset)
        
        # Only return clusters with at least 2 assets
        result = {f"cluster_{i}": assets for i, (_, assets) in 
                 enumerate(cluster_to_assets.items()) if len(assets) >= 2}
        
        return result
    
    except Exception as e:
        logger.error(f"Error in cluster identification: {str(e)}")
        return {}


def calculate_beta(
    returns: pd.DataFrame,
    market_returns: pd.Series,
    rolling_window: Optional[int] = None
) -> Union[pd.DataFrame, pd.Series]:
    """
    Calculate beta (market sensitivity) for each asset.
    
    Args:
        returns: DataFrame of asset returns (columns=assets, index=time)
        market_returns: Series of market/benchmark returns
        rolling_window: Optional window size for rolling beta calculation
        
    Returns:
        Series or DataFrame of beta values for each asset
    """
    # Validate inputs
    if returns.empty or market_returns.empty:
        logger.warning("Empty returns data provided")
        return pd.Series()
    
    # Align the indices of returns and market_returns
    aligned_data = pd.concat([returns, market_returns.rename('market')], axis=1).dropna()
    
    if aligned_data.empty:
        logger.warning("No overlapping data between returns and market_returns")
        return pd.Series()
    
    # Extract aligned data
    aligned_returns = aligned_data[returns.columns]
    aligned_market = aligned_data['market']
    
    # Calculate market variance
    market_var = aligned_market.var()
    
    if market_var == 0:
        logger.warning("Market variance is zero, cannot calculate beta")
        return pd.Series(0, index=returns.columns)
    
    if rolling_window is None:
        # Calculate beta for the entire period
        betas = {}
        
        for asset in returns.columns:
            # Calculate covariance with market
            cov_with_market = aligned_returns[asset].cov(aligned_market)
            # Calculate beta
            beta = cov_with_market / market_var
            betas[asset] = beta
        
        return pd.Series(betas)
    else:
        # Calculate rolling beta
        rolling_betas = pd.DataFrame(index=aligned_returns.index)
        
        for asset in returns.columns:
            # Calculate rolling covariance
            rolling_cov = aligned_returns[asset].rolling(window=rolling_window).cov(aligned_market)
            # Calculate rolling market variance
            rolling_market_var = aligned_market.rolling(window=rolling_window).var()
            # Calculate rolling beta
            rolling_beta = rolling_cov / rolling_market_var
            rolling_betas[asset] = rolling_beta
        
        return rolling_betas


def calculate_portfolio_diversification(
    weights: Dict[str, float],
    correlation_matrix: pd.DataFrame
) -> float:
    """
    Calculate a diversification score for a portfolio.
    
    Args:
        weights: Dictionary of portfolio weights
        correlation_matrix: Correlation matrix between assets
        
    Returns:
        Diversification score (0-1, higher is more diversified)
    """
    # Validate inputs
    if not weights or correlation_matrix.empty:
        logger.warning("Empty weights or correlation matrix provided")
        return 0.0
    
    # Get common assets between weights and correlation matrix
    common_assets = [a for a in weights.keys() if a in correlation_matrix.columns]
    
    if not common_assets:
        logger.warning("No common assets between weights and correlation matrix")
        return 0.0
    
    # Extract relevant weights and normalize them
    filtered_weights = np.array([weights[a] for a in common_assets])
    normalized_weights = filtered_weights / np.sum(filtered_weights)
    
    # Extract relevant correlation matrix
    filtered_corr = correlation_matrix.loc[common_assets, common_assets].to_numpy()
    
    # Calculate weighted average correlation
    weighted_corr = 0.0
    total_weight = 0.0
    
    for i in range(len(common_assets)):
        for j in range(i+1, len(common_assets)):
            pair_weight = normalized_weights[i] * normalized_weights[j]
            weighted_corr += filtered_corr[i, j] * pair_weight
            total_weight += pair_weight
    
    if total_weight > 0:
        avg_corr = weighted_corr / total_weight
    else:
        avg_corr = 0.0
    
    # Convert to diversification score (1 - avg_corr)
    # Higher correlations mean less diversification
    diversification = 1.0 - abs(avg_corr)
    
    return diversification


def plot_correlation_heatmap(
    correlation_matrix: pd.DataFrame,
    figsize: Tuple[int, int] = (10, 8),
    cmap: str = 'coolwarm',
    show_values: bool = False
) -> plt.Figure:
    """
    Plot a heatmap of the correlation matrix.
    
    Args:
        correlation_matrix: Correlation matrix between assets
        figsize: Figure size (width, height)
        cmap: Colormap for the heatmap
        show_values: Whether to show correlation values in the heatmap
        
    Returns:
        Matplotlib figure object
    """
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot heatmap
    mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
    
    if show_values:
        sns.heatmap(
            correlation_matrix,
            annot=True,
            mask=mask,
            cmap=cmap,
            vmin=-1,
            vmax=1,
            center=0,
            fmt='.2f',
            ax=ax
        )
    else:
        sns.heatmap(
            correlation_matrix,
            annot=False,
            mask=mask,
            cmap=cmap,
            vmin=-1,
            vmax=1,
            center=0,
            ax=ax
        )
    
    plt.title('Asset Correlation Matrix')
    plt.tight_layout()
    
    return fig


def plot_correlation_network(
    correlation_matrix: pd.DataFrame,
    threshold: float = 0.5,
    figsize: Tuple[int, int] = (12, 10)
) -> Optional[plt.Figure]:
    """
    Plot a network graph of correlations between assets.
    
    Args:
        correlation_matrix: Correlation matrix between assets
        threshold: Minimum absolute correlation to display an edge
        figsize: Figure size (width, height)
        
    Returns:
        Matplotlib figure object or None if networkx is not available
    """
    try:
        import networkx as nx
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Create graph
        G = nx.Graph()
        
        # Add nodes
        for asset in correlation_matrix.columns:
            G.add_node(asset)
        
        # Add edges for correlations above threshold
        for i, asset1 in enumerate(correlation_matrix.columns):
            for j, asset2 in enumerate(correlation_matrix.columns):
                if i < j:  # Only process upper triangle
                    corr = correlation_matrix.loc[asset1, asset2]
                    if abs(corr) >= threshold:
                        G.add_edge(asset1, asset2, weight=abs(corr), color='r' if corr < 0 else 'b')
        
        # Set layout
        pos = nx.spring_layout(G, seed=42)
        
        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_size=700, node_color='lightblue', ax=ax)
        
        # Draw edges with colors and widths based on correlation
        for (u, v, d) in G.edges(data=True):
            nx.draw_networkx_edges(
                G, pos, 
                edgelist=[(u, v)],
                width=d['weight'] * 3,
                edge_color=d['color'],
                alpha=0.7,
                ax=ax
            )
        
        # Draw labels
        nx.draw_networkx_labels(G, pos, font_size=10, ax=ax)
        
        plt.title('Asset Correlation Network')
        plt.axis('off')
        plt.tight_layout()
        
        return fig
    
    except ImportError:
        logger.warning("Networkx library not available, cannot plot correlation network")
        return None 