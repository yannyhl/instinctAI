"""
Portfolio Risk Controller Module

This module implements the PortfolioRiskController class, which provides advanced portfolio-level 
risk management functionality for trading strategies. It integrates position sizing, exposure 
monitoring, drawdown controls, volatility targeting, and other risk management techniques.

Key features:
- Correlation-aware position sizing
- Portfolio exposure monitoring and limits
- Drawdown-based risk controls (reducing exposure during drawdowns)
- Volatility-targeted portfolio construction
- Risk budget allocation across strategies/assets
- Risk-adjusted sizing based on asset volatility
- Dynamic portfolio rebalancing

This controller serves as the central risk management component for portfolio-level decisions.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Import components from the risk package
from advanced_trading.risk.portfolio.allocation import (
    calculate_portfolio_weights,
    rebalance_portfolio,
    calculate_portfolio_metrics,
    calculate_risk_contribution,
    calculate_risk_parity_weights,
    calculate_hrp_weights,
    calculate_minvar_weights,
    calculate_equal_weights
)
from advanced_trading.risk.portfolio.correlation import (
    calculate_correlation_matrix,
    detect_correlation_changes,
    identify_correlation_clusters,
    calculate_beta,
    calculate_portfolio_diversification
)
from advanced_trading.risk.portfolio.metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_value_at_risk,
    calculate_conditional_value_at_risk
)

# Set up logging
logger = logging.getLogger(__name__)

class PortfolioRiskController:
    """
    Portfolio Risk Controller - Manages risk at the portfolio level.
    
    This class implements various risk management techniques to control portfolio risk,
    including exposure limits, drawdown controls, volatility targeting, and correlation-aware
    position sizing.
    
    Attributes:
        max_portfolio_exposure (float): Maximum allowed portfolio exposure (1.0 = 100%)
        max_correlation_exposure (float): Maximum exposure to highly correlated assets
        drawdown_control_threshold (float): Drawdown threshold to begin reducing exposure
        target_portfolio_volatility (float): Target annualized volatility for the portfolio
        rebalance_threshold (float): Threshold for portfolio rebalancing
        allocation_method (str): Portfolio allocation method ('hrp', 'risk_parity', etc.)
        risk_free_rate (float): Risk-free rate used in calculations
        market_index (pd.Series, optional): Market index returns for beta calculations
    """
    
    def __init__(
        self,
        max_portfolio_exposure: float = 1.0,
        max_correlation_exposure: float = 0.4,
        drawdown_control_threshold: float = 0.1,
        target_portfolio_volatility: float = 0.15,
        rebalance_threshold: float = 0.05,
        allocation_method: str = 'hrp',
        risk_free_rate: float = 0.0,
        market_index: Optional[pd.Series] = None
    ):
        """
        Initialize the Portfolio Risk Controller.
        
        Args:
            max_portfolio_exposure: Maximum allowed portfolio exposure (1.0 = 100%)
            max_correlation_exposure: Maximum exposure to highly correlated assets
            drawdown_control_threshold: Drawdown threshold to begin reducing exposure
            target_portfolio_volatility: Target annualized volatility for the portfolio
            rebalance_threshold: Threshold for portfolio rebalancing
            allocation_method: Portfolio allocation method ('hrp', 'risk_parity', etc.)
            risk_free_rate: Risk-free rate used in calculations
            market_index: Market index returns for beta calculations
        """
        # Validate inputs
        if max_portfolio_exposure <= 0 or max_portfolio_exposure > 2:
            raise ValueError("max_portfolio_exposure must be between 0 and 2")
        if max_correlation_exposure <= 0 or max_correlation_exposure > 1:
            raise ValueError("max_correlation_exposure must be between 0 and 1")
        if drawdown_control_threshold <= 0 or drawdown_control_threshold > 0.5:
            raise ValueError("drawdown_control_threshold must be between 0 and 0.5")
        if target_portfolio_volatility <= 0:
            raise ValueError("target_portfolio_volatility must be positive")
        if rebalance_threshold <= 0 or rebalance_threshold > 0.5:
            raise ValueError("rebalance_threshold must be between 0 and 0.5")
            
        # Store parameters
        self.max_portfolio_exposure = max_portfolio_exposure
        self.max_correlation_exposure = max_correlation_exposure
        self.drawdown_control_threshold = drawdown_control_threshold
        self.target_portfolio_volatility = target_portfolio_volatility
        self.rebalance_threshold = rebalance_threshold
        self.allocation_method = allocation_method
        self.risk_free_rate = risk_free_rate
        self.market_index = market_index
        
        # Internal state
        self.current_portfolio_exposure = 0.0
        self.current_drawdown = 0.0
        self.peak_equity = 0.0
        self.current_weights = {}
        self.correlation_clusters = {}
        self.historical_returns = None
        self.last_rebalance_date = None
        
        logger.info(f"PortfolioRiskController initialized with: "
                   f"max_exposure={max_portfolio_exposure}, "
                   f"target_vol={target_portfolio_volatility}, "
                   f"method={allocation_method}")
    
    def update_market_state(
        self,
        returns: pd.DataFrame,
        current_equity: float,
        current_positions: Dict[str, float],
        current_date: Optional[datetime] = None
    ) -> None:
        """
        Update the internal state with current market data and portfolio information.
        
        Args:
            returns: Historical returns for assets/strategies
            current_equity: Current portfolio equity value
            current_positions: Current positions as {asset: value}
            current_date: Current date for time-based operations
        """
        # Update historical returns with new data
        if self.historical_returns is None:
            self.historical_returns = returns.copy()
        else:
            # Update existing returns with new data
            self.historical_returns = pd.concat([
                self.historical_returns,
                returns.loc[~returns.index.isin(self.historical_returns.index)]
            ]).sort_index()
            
        # Update drawdown tracking
        if self.peak_equity < current_equity:
            self.peak_equity = current_equity
        
        if self.peak_equity > 0:
            self.current_drawdown = 1 - (current_equity / self.peak_equity)
        
        # Calculate current exposure
        self.current_portfolio_exposure = sum(abs(val) for val in current_positions.values()) / current_equity if current_equity > 0 else 0
        
        # Calculate current weights
        if current_equity > 0:
            self.current_weights = {k: v / current_equity for k, v in current_positions.items()}
        else:
            self.current_weights = {k: 0 for k in current_positions}
            
        # Update current date
        self.current_date = current_date or datetime.now()
        
        # Update correlation clusters
        correlation_matrix = calculate_correlation_matrix(
            self.historical_returns.iloc[-min(len(self.historical_returns), 252):],
            method='pearson'
        )
        self.correlation_clusters = identify_correlation_clusters(
            correlation_matrix, threshold=0.7
        )
        
        logger.debug(f"Updated market state: equity={current_equity}, "
                    f"drawdown={self.current_drawdown:.2%}, "
                    f"exposure={self.current_portfolio_exposure:.2%}")

    def calculate_portfolio_weights(
        self, 
        returns: Optional[pd.DataFrame] = None,
        method: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Calculate optimal portfolio weights based on the specified allocation method.
        
        Args:
            returns: Historical returns to use for weight calculation (defaults to internal state)
            method: Allocation method override (defaults to self.allocation_method)
            
        Returns:
            Dictionary of assets to weights
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
        
        method = method or self.allocation_method
        
        if method == 'equal':
            weights = calculate_equal_weights(returns)
        elif method == 'risk_parity':
            weights = calculate_risk_parity_weights(returns)
        elif method == 'hrp':
            weights = calculate_hrp_weights(returns)
        elif method == 'minvar':
            weights = calculate_minvar_weights(returns)
        else:
            raise ValueError(f"Unknown allocation method: {method}")
        
        return weights
    
    def calculate_risk_metrics(
        self, 
        returns: Optional[pd.DataFrame] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Calculate risk metrics for the current or specified portfolio.
        
        Args:
            returns: Historical returns to use (defaults to internal state)
            weights: Portfolio weights to use (defaults to current weights)
            
        Returns:
            Dictionary of risk metrics
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
            
        weights = weights or self.current_weights
        
        # Convert weights dictionary to pandas Series
        weights_series = pd.Series(weights)
        
        # Ensure weights sum to 1.0
        if abs(weights_series.sum() - 1.0) > 1e-5:
            weights_series = weights_series / weights_series.sum()
        
        # Calculate portfolio returns
        returns_assets = returns[weights_series.index]
        portfolio_returns = returns_assets.dot(weights_series)
        
        # Calculate metrics
        volatility = portfolio_returns.std() * np.sqrt(252)  # Annualized
        sharpe = (portfolio_returns.mean() * 252 - self.risk_free_rate) / volatility
        
        # Calculate max drawdown
        cumulative_returns = (1 + portfolio_returns).cumprod()
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns / running_max) - 1
        max_drawdown = drawdown.min()
        
        # Calculate VaR and CVaR
        var_95 = portfolio_returns.quantile(0.05)
        cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()
        
        return {
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'annualized_return': portfolio_returns.mean() * 252
        }
    
    def calculate_diversification_metrics(
        self, 
        returns: Optional[pd.DataFrame] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Calculate diversification metrics for the portfolio.
        
        Args:
            returns: Historical returns to use (defaults to internal state)
            weights: Portfolio weights to use (defaults to current weights)
            
        Returns:
            Dictionary of diversification metrics
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
            
        weights = weights or self.current_weights
        
        # Convert weights dictionary to pandas Series
        weights_series = pd.Series(weights)
        weights_series = weights_series[weights_series > 0]  # Focus on positive weights
        
        # Calculate correlation matrix
        correlation_matrix = calculate_correlation_matrix(returns[weights_series.index])
        
        # Average correlation
        avg_correlation = correlation_matrix.values.mean()
        
        # Calculate diversification ratio
        vol_weighted = np.dot(weights_series, returns[weights_series.index].std())
        portfolio_vol = np.sqrt(weights_series.dot(correlation_matrix).dot(weights_series))
        div_ratio = vol_weighted / portfolio_vol if portfolio_vol > 0 else np.nan
        
        # Number of effective assets
        concentration = (weights_series**2).sum()
        effective_n = 1 / concentration if concentration > 0 else np.nan
        
        return {
            'avg_correlation': avg_correlation,
            'diversification_ratio': div_ratio,
            'effective_n': effective_n,
            'concentration': concentration
        }
    
    def adjust_weights_for_risk_targets(
        self, 
        weights: Dict[str, float],
        returns: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Adjust portfolio weights to meet risk targets.
        
        Args:
            weights: Initial portfolio weights
            returns: Historical returns to use (defaults to internal state)
            
        Returns:
            Risk-adjusted portfolio weights
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
        
        # Convert weights dictionary to pandas Series
        weights_series = pd.Series(weights)
        
        # Calculate current portfolio volatility
        returns_subset = returns[weights_series.index]
        cov_matrix = returns_subset.cov() * 252  # Annualized
        portfolio_variance = weights_series.dot(cov_matrix).dot(weights_series)
        current_volatility = np.sqrt(portfolio_variance)
        
        # Scale weights to meet volatility target
        if current_volatility > 0:
            volatility_scalar = self.target_portfolio_volatility / current_volatility
            adjusted_weights = weights_series * volatility_scalar
        else:
            adjusted_weights = weights_series
            
        # Apply drawdown-based scaling if in drawdown
        if self.current_drawdown > self.drawdown_control_threshold:
            drawdown_factor = 1.0 - ((self.current_drawdown - self.drawdown_control_threshold) / 
                                    (1.0 - self.drawdown_control_threshold))
            drawdown_factor = max(0.1, min(1.0, drawdown_factor))
            adjusted_weights = adjusted_weights * drawdown_factor
            
        return adjusted_weights.to_dict()
    
    def adjust_for_correlation_clusters(
        self, 
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Adjust weights to avoid excess exposure to correlated asset clusters.
        
        Args:
            weights: Portfolio weights to adjust
            
        Returns:
            Correlation-adjusted portfolio weights
        """
        if not self.correlation_clusters:
            return weights
            
        # Convert weights dictionary to pandas Series
        weights_series = pd.Series(weights)
        
        # Calculate exposure per cluster
        cluster_exposure = {}
        for cluster_id, members in self.correlation_clusters.items():
            cluster_members = [m for m in members if m in weights_series.index]
            cluster_exposure[cluster_id] = weights_series[cluster_members].sum()
            
        # Identify clusters exceeding maximum exposure
        excess_clusters = {
            cluster_id: exposure
            for cluster_id, exposure in cluster_exposure.items()
            if exposure > self.max_correlation_exposure and len(self.correlation_clusters[cluster_id]) > 1
        }
        
        # Adjust weights for excess clusters
        adjusted_weights = weights_series.copy()
        for cluster_id, exposure in excess_clusters.items():
            cluster_members = [m for m in self.correlation_clusters[cluster_id] if m in weights_series.index]
            if not cluster_members:
                continue
                
            # Scale down proportionally
            scale_factor = self.max_correlation_exposure / exposure
            for member in cluster_members:
                adjusted_weights[member] *= scale_factor
                
        return adjusted_weights.to_dict()
    
    def calculate_rebalance_trades(
        self, 
        target_weights: Dict[str, float],
        current_positions: Dict[str, float],
        current_equity: float
    ) -> Dict[str, float]:
        """
        Calculate trades needed to rebalance portfolio to target weights.
        
        Args:
            target_weights: Target portfolio weights
            current_positions: Current positions as {asset: value}
            current_equity: Current portfolio equity value
            
        Returns:
            Dictionary of assets to trade amounts (positive = buy, negative = sell)
        """
        if current_equity <= 0:
            return {}
            
        # Calculate current weights
        current_weights = {
            asset: value / current_equity
            for asset, value in current_positions.items()
        }
        
        # Calculate trades needed
        trades = {}
        
        # Process assets in both target and current
        for asset in set(target_weights).union(current_weights):
            target = target_weights.get(asset, 0.0)
            current = current_weights.get(asset, 0.0)
            
            # Only trade if difference exceeds threshold
            if abs(target - current) > self.rebalance_threshold / len(target_weights):
                trades[asset] = (target - current) * current_equity
                
        return trades
        
    def generate_position_sizing_recommendations(
        self, 
        current_equity: float,
        current_positions: Optional[Dict[str, float]] = None
    ) -> Dict[str, Dict]:
        """
        Generate comprehensive position sizing recommendations.
        
        Args:
            current_equity: Current portfolio equity value
            current_positions: Current positions as {asset: value} (defaults to empty)
            
        Returns:
            Dictionary of position sizing recommendations
        """
        current_positions = current_positions or {}
        
        # Calculate optimal weights
        optimal_weights = self.calculate_portfolio_weights()
        
        # Adjust for risk targets and correlation
        risk_adjusted = self.adjust_weights_for_risk_targets(optimal_weights)
        correlation_adjusted = self.adjust_for_correlation_clusters(risk_adjusted)
        
        # Calculate trades needed
        trades = self.calculate_rebalance_trades(
            correlation_adjusted, current_positions, current_equity
        )
        
        # Calculate risk metrics for the portfolio
        risk_metrics = self.calculate_risk_metrics(weights=correlation_adjusted)
        diversification = self.calculate_diversification_metrics(weights=correlation_adjusted)
        
        return {
            'optimal_weights': optimal_weights,
            'risk_adjusted_weights': risk_adjusted,
            'final_weights': correlation_adjusted,
            'recommended_trades': trades,
            'risk_metrics': risk_metrics,
            'diversification_metrics': diversification,
            'portfolio_exposure': sum(abs(w) for w in correlation_adjusted.values()),
            'drawdown_status': {
                'current_drawdown': self.current_drawdown,
                'threshold': self.drawdown_control_threshold,
                'risk_reduction': (self.current_drawdown > self.drawdown_control_threshold)
            }
        }

    def calculate_risk_contribution(self,
        weights: Optional[Dict[str, float]] = None,
        returns: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Calculate the risk contribution of each asset to the portfolio.
        
        This method calculates how much each position contributes to the overall portfolio
        variance, allowing for risk budgeting and risk parity analysis.
        
        Args:
            weights: Portfolio weights (defaults to current weights)
            returns: Historical returns (defaults to internal state)
            
        Returns:
            Dictionary of assets to risk contribution percentages
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
        
        weights = weights or self.current_weights
        weights_series = pd.Series(weights)
        
        # Calculate covariance matrix
        cov_matrix = returns[weights_series.index].cov() * 252  # Annualized
        
        # Calculate portfolio variance
        portfolio_variance = weights_series.dot(cov_matrix).dot(weights_series)
        
        # Calculate marginal contributions
        marginal_contributions = cov_matrix.dot(weights_series)
        
        # Calculate component contributions
        component_contributions = {}
        for asset in weights_series.index:
            component_contributions[asset] = weights_series[asset] * marginal_contributions[asset] / portfolio_variance
        
        return component_contributions

    def calculate_portfolio_metrics(
        self,
        weights: Optional[Dict[str, float]] = None,
        returns: Optional[pd.DataFrame] = None,
        include_advanced: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive portfolio metrics including performance and risk statistics.
        
        Args:
            weights: Portfolio weights (defaults to current weights)
            returns: Historical returns (defaults to internal state)
            include_advanced: Whether to include advanced metrics (more computation)
            
        Returns:
            Dictionary of portfolio metrics
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
        
        weights = weights or self.current_weights
        weights_series = pd.Series(weights)
        
        # Calculate portfolio returns
        portfolio_returns = returns[weights_series.index].dot(weights_series)
        
        # Basic metrics
        metrics = {
            # Performance metrics
            'annualized_return': portfolio_returns.mean() * 252,
            'annualized_volatility': portfolio_returns.std() * np.sqrt(252),
            'sharpe_ratio': calculate_sharpe_ratio(portfolio_returns, risk_free_rate=self.risk_free_rate),
            'sortino_ratio': calculate_sortino_ratio(portfolio_returns, risk_free_rate=self.risk_free_rate),
            
            # Risk metrics
            'max_drawdown': calculate_max_drawdown(portfolio_returns),
            'var_95': calculate_value_at_risk(portfolio_returns, confidence=0.95),
            'cvar_95': calculate_conditional_value_at_risk(portfolio_returns, confidence=0.95),
            
            # Exposure metrics
            'gross_exposure': sum(abs(w) for w in weights_series),
            'net_exposure': sum(weights_series),
            'long_exposure': sum(w for w in weights_series if w > 0),
            'short_exposure': sum(abs(w) for w in weights_series if w < 0),
        }
        
        if include_advanced:
            # Advanced metrics (more computational)
            rolling_vol = portfolio_returns.rolling(window=21).std() * np.sqrt(252)
            
            # Calculate beta if market index is available
            if self.market_index is not None:
                aligned_market = self.market_index[self.market_index.index.isin(portfolio_returns.index)]
                if len(aligned_market) > 20:  # Minimum data points for regression
                    beta = calculate_beta(portfolio_returns, aligned_market)
                    metrics['beta'] = beta
            
            # Calculate drawdown series
            cum_returns = (1 + portfolio_returns).cumprod()
            peak = cum_returns.cummax()
            drawdown = (cum_returns / peak) - 1
            
            metrics.update({
                'calmar_ratio': metrics['annualized_return'] / abs(metrics['max_drawdown']) if metrics['max_drawdown'] != 0 else np.inf,
                'volatility_of_volatility': rolling_vol.std() / rolling_vol.mean() if rolling_vol.mean() != 0 else np.nan,
                'average_drawdown': drawdown.mean(),
                'median_drawdown': drawdown.median(),
                'skewness': portfolio_returns.skew(),
                'kurtosis': portfolio_returns.kurtosis(),
            })
        
        return metrics

    def calculate_risk_adjusted_sizing(
        self,
        target_positions: Dict[str, float],
        max_risk_per_position: float = 0.02,
        returns: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Adjust position sizes based on individual asset volatility to achieve balanced risk allocation.
        
        Args:
            target_positions: Target position sizes before risk adjustment
            max_risk_per_position: Maximum risk contribution from any single position (0.02 = 2%)
            returns: Historical returns (defaults to internal state)
            
        Returns:
            Dictionary of risk-adjusted position sizes
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
        
        # Calculate asset volatilities
        volatilities = {}
        for asset in target_positions:
            if asset in returns.columns:
                volatilities[asset] = returns[asset].std() * np.sqrt(252)  # Annualized
            else:
                volatilities[asset] = 0.15  # Default assumed volatility
        
        # Calculate target risk budget per position
        portfolio_value = 1.0  # Normalized to 1.0
        risk_budget = max_risk_per_position * portfolio_value
        
        # Calculate position sizes to achieve risk budget
        risk_adjusted_positions = {}
        for asset, target_size in target_positions.items():
            if volatilities[asset] > 0:
                # Position size = risk budget / volatility
                risk_adjusted_size = risk_budget / volatilities[asset]
                
                # Cap position size to target size
                risk_adjusted_positions[asset] = min(abs(target_size), risk_adjusted_size) * (1 if target_size >= 0 else -1)
            else:
                risk_adjusted_positions[asset] = 0  # Zero volatility means no position
        
        return risk_adjusted_positions

    def calculate_risk_budget_allocation(
        self,
        target_risk_budget: Dict[str, float],
        returns: Optional[pd.DataFrame] = None,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> Dict[str, float]:
        """
        Calculate weights that achieve the specified risk budget allocation.
        
        This implements an iterative risk parity algorithm to allocate portfolio weights
        according to a specified risk budget for each asset.
        
        Args:
            target_risk_budget: Target risk budget allocation as {asset: risk_proportion}
            returns: Historical returns (defaults to internal state)
            max_iterations: Maximum iterations for the optimizer
            tolerance: Convergence tolerance
            
        Returns:
            Dictionary of weights that achieve the target risk budget
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
        
        # Normalize risk budget to sum to 1
        total_budget = sum(target_risk_budget.values())
        normalized_budget = {k: v / total_budget for k, v in target_risk_budget.items()}
        
        # Filter returns to include only assets in the risk budget
        returns_subset = returns[normalized_budget.keys()]
        
        # Calculate covariance matrix
        cov_matrix = returns_subset.cov() * 252  # Annualized
        
        # Initialize weights equally
        n_assets = len(normalized_budget)
        weights = np.ones(n_assets) / n_assets
        
        # Iterative optimization to achieve risk budget
        for i in range(max_iterations):
            # Calculate portfolio variance with current weights
            portfolio_variance = weights.dot(cov_matrix).dot(weights)
            
            # Calculate risk contribution of each asset
            marginal_contrib = cov_matrix.dot(weights)
            risk_contrib = weights * marginal_contrib / portfolio_variance
            
            # Calculate desired change in weights
            assets = list(normalized_budget.keys())
            target_risk_contrib = np.array([normalized_budget[asset] for asset in assets])
            adjustment = target_risk_contrib / risk_contrib
            
            # Update weights
            new_weights = weights * adjustment
            new_weights = new_weights / new_weights.sum()  # Normalize
            
            # Check convergence
            if np.max(np.abs(new_weights - weights)) < tolerance:
                weights = new_weights
                break
                
            weights = new_weights
        
        # Convert back to dictionary
        return {asset: weight for asset, weight in zip(normalized_budget.keys(), weights)}

    def calculate_portfolio_exposure(
        self,
        positions: Optional[Dict[str, float]] = None,
        equity: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate total portfolio exposure across all assets and exposure categories.
        
        Args:
            positions: Portfolio positions as {asset: value} (defaults to internal state)
            equity: Portfolio equity value (defaults to using position values)
            
        Returns:
            Dictionary of various exposure metrics
        """
        # Use provided positions or current positions from state
        if positions is None:
            positions = {k: v for k, v in self.current_weights.items()}
        
        # Calculate total position value
        total_value = sum(abs(v) for v in positions.values())
        
        # Use provided equity or infer from positions
        if equity is None:
            equity = total_value
        
        # Calculate different types of exposure if equity is positive
        if equity > 0:
            # Calculate long and short exposure
            long_exposure = sum(v for v in positions.values() if v > 0) / equity
            short_exposure = sum(abs(v) for v in positions.values() if v < 0) / equity
            
            # Calculate gross and net exposure
            gross_exposure = long_exposure + short_exposure
            net_exposure = long_exposure - short_exposure
            
            # Calculate exposure by position count
            position_count = len(positions)
            long_positions = sum(1 for v in positions.values() if v > 0)
            short_positions = sum(1 for v in positions.values() if v < 0)
            
            # Calculate concentration metrics
            if position_count > 0:
                avg_position_size = gross_exposure / position_count
                max_position_size = max(abs(v) for v in positions.values()) / equity if positions else 0
                concentration_ratio = max_position_size / avg_position_size if avg_position_size > 0 else 0
            else:
                avg_position_size = 0
                max_position_size = 0
                concentration_ratio = 0
        else:
            # Default values if equity is zero or negative
            long_exposure = 0
            short_exposure = 0
            gross_exposure = 0
            net_exposure = 0
            position_count = 0
            long_positions = 0
            short_positions = 0
            avg_position_size = 0
            max_position_size = 0
            concentration_ratio = 0
        
        return {
            'gross_exposure': gross_exposure,
            'net_exposure': net_exposure,
            'long_exposure': long_exposure,
            'short_exposure': short_exposure,
            'position_count': position_count,
            'long_positions': long_positions,
            'short_positions': short_positions,
            'avg_position_size': avg_position_size,
            'max_position_size': max_position_size,
            'concentration_ratio': concentration_ratio,
            'exposure_to_equity': gross_exposure
        }

    def calculate_current_exposure(
        self,
        current_positions: Optional[Dict[str, float]] = None,
        current_equity: Optional[float] = None
    ) -> float:
        """
        Calculate current portfolio exposure based on position values and equity.
        
        Args:
            current_positions: Current positions as {asset: value} (defaults to internal state)
            current_equity: Current portfolio equity value (defaults to sum of position values)
            
        Returns:
            Current portfolio exposure as a ratio (1.0 = 100% exposure)
        """
        # Use provided positions or current positions from state
        positions = current_positions or self.current_weights
        
        # Calculate absolute position values
        abs_position_sum = sum(abs(v) for v in positions.values())
        
        # Use provided equity or infer from positions
        equity = current_equity or abs_position_sum
        
        # Calculate exposure as ratio of positions to equity
        if equity > 0:
            return abs_position_sum / equity
        else:
            return 0.0  # No exposure if equity is zero or negative

    def calculate_current_weights(
        self,
        current_positions: Optional[Dict[str, float]] = None,
        current_equity: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate current portfolio weights based on position values and equity.
        
        Args:
            current_positions: Current positions as {asset: value} (defaults to internal state)
            current_equity: Current portfolio equity value (defaults to sum of position values)
            
        Returns:
            Dictionary of current weights as {asset: weight}
        """
        # Use provided positions or current positions from state
        positions = current_positions or self.current_weights
        
        # Use provided equity or calculate from positions
        if current_equity is None:
            equity = sum(abs(v) for v in positions.values())
        else:
            equity = current_equity
        
        # Calculate weights as position value / equity
        if equity > 0:
            return {k: v / equity for k, v in positions.items()}
        else:
            return {k: 0.0 for k in positions}  # Zero weights if equity is zero or negative

    def calculate_current_drawdown(
        self,
        current_equity: Optional[float] = None,
        peak_equity: Optional[float] = None
    ) -> float:
        """
        Calculate current portfolio drawdown from peak equity.
        
        Args:
            current_equity: Current portfolio equity value (defaults to internal state)
            peak_equity: Peak equity value (defaults to internal state)
            
        Returns:
            Current drawdown as a decimal (0.1 = 10% drawdown)
        """
        # Use provided values or internal state
        current = current_equity if current_equity is not None else self.current_weights.values()
        peak = peak_equity if peak_equity is not None else self.peak_equity
        
        # If current is a dictionary of positions, sum the values
        if isinstance(current, dict):
            current = sum(current.values())
        
        # Calculate drawdown
        if peak > 0 and current >= 0:
            return max(0, 1 - (current / peak))
        else:
            return 0.0  # No drawdown if peak or current equity is invalid

    def calculate_peak_equity(
        self,
        equity_history: Optional[pd.Series] = None
    ) -> float:
        """
        Calculate peak equity achieved by the portfolio.
        
        Args:
            equity_history: Historical equity values (defaults to using peak from internal state)
            
        Returns:
            Peak equity value
        """
        # If equity history is provided, calculate peak from the series
        if equity_history is not None:
            if len(equity_history) > 0:
                return equity_history.max()
            else:
                return 0.0  # No peak if history is empty
        
        # Otherwise return peak from internal state
        return self.peak_equity

    def calculate_historical_returns(
        self,
        equity_history: pd.Series,
        period: str = 'D',
        include_metrics: bool = False
    ) -> Union[pd.Series, Dict[str, Union[pd.Series, float]]]:
        """
        Calculate historical returns for the portfolio from equity curve.
        
        Args:
            equity_history: Historical equity values as a time series
            period: Return calculation period ('D' for daily, 'W' for weekly, etc.)
            include_metrics: Whether to include return metrics in the output
            
        Returns:
            If include_metrics=False: Series of historical returns
            If include_metrics=True: Dict with returns series and metrics
        """
        if len(equity_history) < 2:
            if include_metrics:
                return {
                    'returns': pd.Series(dtype=float),
                    'metrics': {}
                }
            return pd.Series(dtype=float)
        
        # Resample to the specified period if necessary
        if period != 'D':
            equity_resampled = equity_history.resample(period).last()
        else:
            equity_resampled = equity_history
        
        # Calculate returns
        returns = equity_resampled.pct_change().dropna()
        
        if not include_metrics:
            return returns
        
        # Calculate return metrics
        annualization_factor = {
            'D': 252,
            'W': 52,
            'M': 12,
            'Q': 4,
            'Y': 1
        }.get(period, 252)
        
        # Basic metrics
        mean_return = returns.mean()
        std_return = returns.std()
        annualized_return = (1 + mean_return) ** annualization_factor - 1
        annualized_volatility = std_return * np.sqrt(annualization_factor)
        sharpe_ratio = annualized_return / annualized_volatility if annualized_volatility > 0 else 0
        
        # Calculate drawdowns
        cum_returns = (1 + returns).cumprod()
        peak = cum_returns.cummax()
        drawdown = (cum_returns / peak) - 1
        max_drawdown = drawdown.min()
        
        metrics = {
            'mean_return': mean_return,
            'std_return': std_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'skewness': returns.skew(),
            'kurtosis': returns.kurtosis(),
            'positive_periods': (returns > 0).sum() / len(returns),
            'negative_periods': (returns < 0).sum() / len(returns)
        }
        
        return {
            'returns': returns,
            'metrics': metrics
        }

    def calculate_last_rebalance_date(
        self,
        trade_history: Optional[pd.DataFrame] = None
    ) -> Optional[datetime]:
        """
        Calculate the date of the last portfolio rebalance.
        
        Args:
            trade_history: Historical trades with datetime index (defaults to internal state)
            
        Returns:
            Datetime of the last rebalance or None if no rebalance history
        """
        # If trade history is provided, find the last trade date
        if trade_history is not None and not trade_history.empty:
            return trade_history.index[-1]
        
        # Otherwise return the last rebalance date from internal state
        return self.last_rebalance_date

    def calculate_correlation_clusters(
        self,
        returns: Optional[pd.DataFrame] = None,
        threshold: float = 0.7,
        method: str = 'pearson'
    ) -> Dict[int, List[str]]:
        """
        Calculate correlation clusters in the portfolio.
        
        Args:
            returns: Historical returns (defaults to internal state)
            threshold: Correlation threshold for clustering (0.7 = 70% correlation)
            method: Correlation method ('pearson', 'spearman', 'kendall')
            
        Returns:
            Dictionary of cluster IDs to lists of assets in each cluster
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns.iloc[-min(len(self.historical_returns), 252):]
        
        # Calculate correlation matrix
        correlation_matrix = calculate_correlation_matrix(returns, method=method)
        
        # Identify correlation clusters
        clusters = identify_correlation_clusters(correlation_matrix, threshold=threshold)
        
        # Update internal state
        self.correlation_clusters = clusters
        
        return clusters

    def calculate_current_date(
        self,
        reference_data: Optional[pd.DataFrame] = None
    ) -> datetime:
        """
        Get the current date for time-based operations.
        
        Args:
            reference_data: Data with datetime index to extract latest date from
            
        Returns:
            Current date (from reference data, internal state, or system time)
        """
        # If reference data is provided, get the latest date from it
        if reference_data is not None and hasattr(reference_data, 'index') and len(reference_data.index) > 0:
            if isinstance(reference_data.index, pd.DatetimeIndex):
                return reference_data.index[-1]
        
        # If internal current_date is set, use that
        if hasattr(self, 'current_date') and self.current_date is not None:
            return self.current_date
        
        # Otherwise use the current system time
        return datetime.now()

    def calculate_current_market_state(
        self,
        returns: Optional[pd.DataFrame] = None,
        lookback_period: int = 20,
        volatility_window: int = 20,
        trend_window: int = 50
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate current market state based on various indicators.
        
        Args:
            returns: Historical returns (defaults to internal state)
            lookback_period: Number of periods to consider as "current"
            volatility_window: Window for volatility calculation
            trend_window: Window for trend calculation
            
        Returns:
            Dictionary of market state indicators for assets and overall market
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns
        
        # Ensure sufficient data
        min_required = max(lookback_period, volatility_window, trend_window)
        if len(returns) < min_required:
            raise ValueError(f"Insufficient data for market state calculation. Need at least {min_required} periods.")
        
        recent_returns = returns.iloc[-lookback_period:]
        
        # Calculate volatility for each asset
        rolling_vol = returns.rolling(window=volatility_window).std().iloc[-lookback_period:]
        current_vol = rolling_vol.iloc[-1]
        avg_vol = rolling_vol.mean()
        rel_vol = current_vol / avg_vol
        
        # Calculate trend indicators
        rolling_mean = returns.rolling(window=trend_window).mean().iloc[-lookback_period:]
        current_trend = rolling_mean.iloc[-1]
        
        # Determine if each asset is in an uptrend or downtrend
        trend_direction = {col: 1 if current_trend[col] > 0 else -1 for col in returns.columns}
        
        # Calculate correlation to "market" (using average of all assets as proxy)
        market_returns = returns.mean(axis=1)
        correlations = {}
        for col in returns.columns:
            correlations[col] = returns[col].iloc[-lookback_period:].corr(market_returns.iloc[-lookback_period:])
        
        # Calculate recent performance
        recent_performance = recent_returns.sum()
        
        # Compile market state for each asset
        asset_states = {}
        for asset in returns.columns:
            asset_states[asset] = {
                'current_volatility': current_vol[asset],
                'relative_volatility': rel_vol[asset],
                'trend_direction': trend_direction[asset],
                'market_correlation': correlations[asset],
                'recent_performance': recent_performance[asset]
            }
        
        # Calculate overall market state
        overall_market = {
            'average_volatility': current_vol.mean(),
            'volatility_regime': 'high' if current_vol.mean() > avg_vol.mean() * 1.2 else 'normal',
            'trend_strength': abs(current_trend.mean()),
            'trend_direction': 1 if current_trend.mean() > 0 else -1,
            'average_correlation': sum(correlations.values()) / len(correlations),
            'overall_performance': recent_performance.mean()
        }
        
        return {
            'assets': asset_states,
            'market': overall_market
        }

    def calculate_current_market_state_metrics(
        self,
        returns: Optional[pd.DataFrame] = None,
        market_returns: Optional[pd.Series] = None,
        lookback_period: int = 60
    ) -> Dict[str, float]:
        """
        Calculate metrics related to the current market state.
        
        Args:
            returns: Historical returns for assets (defaults to internal state)
            market_returns: Market index returns (defaults to market_index in internal state)
            lookback_period: Number of periods to consider as "current"
            
        Returns:
            Dictionary of market state metrics
        """
        if returns is None:
            if self.historical_returns is None:
                raise ValueError("No returns data available")
            returns = self.historical_returns
        
        # Use provided market returns or internal state
        if market_returns is None:
            market_returns = self.market_index
        
        # Ensure sufficient data
        if len(returns) < lookback_period:
            raise ValueError(f"Insufficient data for market metrics calculation. Need at least {lookback_period} periods.")
        
        # Recent returns for calculation
        recent_returns = returns.iloc[-lookback_period:]
        
        # Calculate cross-asset correlation
        correlation_matrix = recent_returns.corr()
        avg_correlation = correlation_matrix.values.mean()
        
        # Calculate volatility regime
        volatility = recent_returns.std() * np.sqrt(252)  # Annualized
        avg_volatility = volatility.mean()
        
        # Calculate dispersion (variation in returns across assets)
        dispersion = recent_returns.std(axis=1).mean()
        
        # Calculate asset diversification metrics
        num_assets = len(returns.columns)
        hhi_concentration = sum((recent_returns.std() / recent_returns.std().sum()) ** 2)
        effective_num_assets = 1 / hhi_concentration if hhi_concentration > 0 else 0
        
        # Calculate market metrics if market index is available
        market_metrics = {}
        if market_returns is not None:
            recent_market = market_returns.iloc[-lookback_period:] if len(market_returns) >= lookback_period else market_returns
            market_volatility = recent_market.std() * np.sqrt(252)
            
            # Calculate average beta to market
            betas = {}
            for col in recent_returns.columns:
                if len(recent_market) > 10:  # Minimum for regression
                    beta = calculate_beta(recent_returns[col], recent_market)
                    betas[col] = beta
            
            if betas:
                avg_beta = sum(betas.values()) / len(betas)
                market_metrics = {
                    'market_volatility': market_volatility,
                    'average_beta': avg_beta,
                    'beta_dispersion': np.std(list(betas.values())) if len(betas) > 1 else 0
                }
        
        # Combine all metrics
        metrics = {
            'average_correlation': avg_correlation,
            'average_volatility': avg_volatility,
            'return_dispersion': dispersion,
            'effective_num_assets': effective_num_assets,
            'concentration_index': hhi_concentration,
            'volatility_regime': 'high' if avg_volatility > 0.2 else ('medium' if avg_volatility > 0.1 else 'low'),
            'correlation_regime': 'high' if avg_correlation > 0.6 else ('medium' if avg_correlation > 0.3 else 'low')
        }
        
        # Add market metrics if available
        if market_metrics:
            metrics.update(market_metrics)
        
        return metrics
