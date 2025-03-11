"""
Correlation Risk Management

This module provides tools for managing risk related to correlation between assets
and strategies. It helps ensure proper diversification and prevents excessive
concentration in correlated positions.

Key features:
1. Strategy correlation analysis
2. Asset correlation monitoring
3. Correlation-aware position sizing
4. Diversification metrics
5. Correlation regime detection
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CorrelationRegime(Enum):
    """Classification of correlation regimes."""
    LOW = "low"                 # Assets generally uncorrelated
    MODERATE = "moderate"       # Some correlation but still diversified
    HIGH = "high"               # Significant correlation, reduced diversification
    CRISIS = "crisis"           # Crisis correlation, diversification breakdown


@dataclass
class CorrelationStats:
    """Statistics about correlation between assets or strategies."""
    average_correlation: float
    max_correlation: float
    min_correlation: float
    effective_n: float  # Effective number of positions accounting for correlation
    regime: CorrelationRegime
    crisis_probability: float
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_matrix: Optional[pd.DataFrame] = None
    eigenvalues: Optional[List[float]] = None
    

class CorrelationRiskManager:
    """
    Manages correlation risk across assets and strategies.
    
    This class provides tools to:
    1. Monitor correlation between assets
    2. Track correlation between strategies
    3. Detect correlation regime changes
    4. Calculate diversification metrics
    5. Recommend position adjustments based on correlation
    """
    
    def __init__(
        self,
        max_correlation_threshold: float = 0.7,
        min_eigenvalue_ratio: float = 0.1,
        lookback_periods: int = 60,
        crisis_detection_threshold: float = 0.8,
        rebalance_threshold: float = 0.1
    ):
        """
        Initialize the correlation risk manager.
        
        Args:
            max_correlation_threshold: Maximum allowed pairwise correlation
            min_eigenvalue_ratio: Minimum ratio of smallest to largest eigenvalue
            lookback_periods: Number of periods for correlation calculation
            crisis_detection_threshold: Threshold for detecting correlation crisis
            rebalance_threshold: Minimum change in correlation to trigger rebalance
        """
        self.max_correlation_threshold = max_correlation_threshold
        self.min_eigenvalue_ratio = min_eigenvalue_ratio
        self.lookback_periods = lookback_periods
        self.crisis_detection_threshold = crisis_detection_threshold
        self.rebalance_threshold = rebalance_threshold
        
        # Internal state
        self.return_history = {}
        self.correlation_history = []
        self.current_correlation_stats = None
        self.current_regime = CorrelationRegime.MODERATE
        self.previous_regime = CorrelationRegime.MODERATE
        self.last_update_time = datetime.now()
        
        logger.info("Correlation risk manager initialized")
    
    def update_returns(self, return_data: Dict[str, float], timestamp: Optional[datetime] = None):
        """
        Update return history with new data.
        
        Args:
            return_data: Dictionary mapping asset/strategy name to return
            timestamp: Optional timestamp for the return data
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Update return history for each asset/strategy
        for name, ret in return_data.items():
            if name not in self.return_history:
                self.return_history[name] = []
                
            self.return_history[name].append((timestamp, ret))
            
            # Keep only lookback_periods history
            if len(self.return_history[name]) > self.lookback_periods:
                self.return_history[name] = self.return_history[name][-self.lookback_periods:]
    
    def calculate_correlation_matrix(self) -> pd.DataFrame:
        """
        Calculate correlation matrix from return history.
        
        Returns:
            DataFrame containing the correlation matrix
        """
        # Extract returns into a DataFrame
        return_data = {}
        
        for name, history in self.return_history.items():
            if len(history) >= self.lookback_periods / 2:  # Require at least half of lookback
                returns = [ret for _, ret in history]
                return_data[name] = returns
        
        if not return_data:
            return pd.DataFrame()
            
        # Create DataFrame with returns
        df = pd.DataFrame(return_data)
        
        # Calculate correlation matrix
        corr_matrix = df.corr()
        
        return corr_matrix
    
    def analyze_correlation(self) -> CorrelationStats:
        """
        Analyze correlation structure and compute metrics.
        
        Returns:
            CorrelationStats with correlation analysis results
        """
        corr_matrix = self.calculate_correlation_matrix()
        
        if corr_matrix.empty:
            # Not enough data for correlation analysis
            return CorrelationStats(
                average_correlation=0.0,
                max_correlation=0.0,
                min_correlation=0.0,
                effective_n=1.0,
                regime=CorrelationRegime.MODERATE,
                crisis_probability=0.0
            )
        
        # Calculate correlation metrics
        # - Remove diagonal (self-correlations)
        mask = np.ones(corr_matrix.shape, dtype=bool)
        np.fill_diagonal(mask, False)
        
        # - Calculate metrics
        correlations = corr_matrix.values[mask]
        avg_corr = correlations.mean()
        max_corr = correlations.max()
        min_corr = correlations.min()
        
        # Calculate eigenvalues for effective N calculation
        eigenvalues = np.linalg.eigvalsh(corr_matrix.values)
        eigenvalues.sort()  # Ascending order
        
        # Effective N (number of uncorrelated assets)
        # - Using participation ratio: N_eff = (sum(λ))² / sum(λ²)
        sum_eig = np.sum(eigenvalues)
        sum_eig_squared = np.sum(eigenvalues ** 2)
        effective_n = (sum_eig ** 2) / sum_eig_squared if sum_eig_squared > 0 else 1.0
        
        # Determine correlation regime
        if max_corr >= self.crisis_detection_threshold:
            regime = CorrelationRegime.CRISIS
            crisis_probability = 0.9
        elif avg_corr >= 0.5:
            regime = CorrelationRegime.HIGH
            crisis_probability = 0.3 + (avg_corr - 0.5) * 2  # 0.3 to 0.7
        elif avg_corr >= 0.2:
            regime = CorrelationRegime.MODERATE
            crisis_probability = 0.1 + (avg_corr - 0.2) * 0.5  # 0.1 to 0.3
        else:
            regime = CorrelationRegime.LOW
            crisis_probability = max(0.0, avg_corr * 0.5)  # 0.0 to 0.1
        
        # Create correlation statistics
        stats = CorrelationStats(
            average_correlation=avg_corr,
            max_correlation=max_corr,
            min_correlation=min_corr,
            effective_n=effective_n,
            regime=regime,
            crisis_probability=crisis_probability,
            correlation_matrix=corr_matrix,
            eigenvalues=eigenvalues.tolist()
        )
        
        # Update internal state
        self.current_correlation_stats = stats
        self.previous_regime = self.current_regime
        self.current_regime = regime
        self.correlation_history.append((datetime.now(), stats))
        self.last_update_time = datetime.now()
        
        # Log regime changes
        if self.previous_regime != self.current_regime:
            logger.warning(f"Correlation regime changed from {self.previous_regime.value} to {self.current_regime.value}")
            logger.warning(f"Average correlation: {avg_corr:.2f}, Max correlation: {max_corr:.2f}")
            logger.warning(f"Effective number of positions: {effective_n:.2f} (vs. actual {len(corr_matrix)})")
        
        return stats
    
    def get_diversification_score(self) -> float:
        """
        Calculate a diversification score from 0.0 (poor) to 1.0 (excellent).
        
        Returns:
            Diversification score
        """
        if self.current_correlation_stats is None:
            return 1.0
            
        # Use effective N relative to actual N as diversification score
        actual_n = len(self.return_history)
        if actual_n <= 1:
            return 1.0
            
        # Score is the ratio of effective positions to actual positions
        eff_n = self.current_correlation_stats.effective_n
        raw_score = eff_n / actual_n
        
        # Normalize score to 0.0-1.0 range with better resolution
        # - 0.0: Complete correlation (eff_n = 1)
        # - 1.0: Complete independence (eff_n = actual_n)
        normalized_score = (raw_score - 1/actual_n) / (1 - 1/actual_n) if actual_n > 1 else raw_score
        
        return max(0.0, min(1.0, normalized_score))
    
    def get_highly_correlated_pairs(self, threshold: Optional[float] = None) -> List[Tuple[str, str, float]]:
        """
        Identify pairs with correlation exceeding the threshold.
        
        Args:
            threshold: Correlation threshold (defaults to max_correlation_threshold)
            
        Returns:
            List of tuples containing (asset1, asset2, correlation)
        """
        if self.current_correlation_stats is None or self.current_correlation_stats.correlation_matrix is None:
            return []
            
        if threshold is None:
            threshold = self.max_correlation_threshold
            
        # Get correlation matrix
        corr_matrix = self.current_correlation_stats.correlation_matrix
        
        # Find pairs with correlation exceeding threshold
        high_corr_pairs = []
        
        for i, name1 in enumerate(corr_matrix.index):
            for j, name2 in enumerate(corr_matrix.columns):
                if i < j:  # Upper triangle only (avoid duplicates and self-correlation)
                    corr = corr_matrix.iloc[i, j]
                    if abs(corr) >= threshold:
                        high_corr_pairs.append((name1, name2, corr))
        
        # Sort by correlation (descending)
        high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        
        return high_corr_pairs
    
    def calculate_optimal_position_sizes(self, base_sizes: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate correlation-adjusted position sizes.
        
        Args:
            base_sizes: Dictionary mapping asset/strategy name to base position size
            
        Returns:
            Dictionary with adjusted position sizes
        """
        if self.current_correlation_stats is None or self.current_correlation_stats.correlation_matrix is None:
            return base_sizes
            
        # Get correlation matrix and corresponding assets
        corr_matrix = self.current_correlation_stats.correlation_matrix
        assets = list(corr_matrix.index)
        
        # Filter to include only assets with base sizes
        relevant_assets = [a for a in assets if a in base_sizes]
        if not relevant_assets:
            return base_sizes
            
        # Extract relevant correlation submatrix
        sub_matrix = corr_matrix.loc[relevant_assets, relevant_assets]
        
        # Calculate effective position sizes using correlation information
        # - In high correlation regime, reduce allocation to highly correlated assets
        # - In low correlation regime, maintain original allocations
        adjusted_sizes = base_sizes.copy()
        
        if self.current_regime in (CorrelationRegime.HIGH, CorrelationRegime.CRISIS):
            # Get highly correlated groups
            high_corr_pairs = self.get_highly_correlated_pairs()
            high_corr_assets = set()
            
            for asset1, asset2, _ in high_corr_pairs:
                high_corr_assets.add(asset1)
                high_corr_assets.add(asset2)
            
            # Apply reduction factor to highly correlated assets
            reduction_factor = 0.5 if self.current_regime == CorrelationRegime.HIGH else 0.25
            for asset in high_corr_assets:
                if asset in adjusted_sizes:
                    adjusted_sizes[asset] *= reduction_factor
        
        # Normalize to maintain the same total allocation
        total_base = sum(base_sizes.values())
        total_adjusted = sum(adjusted_sizes.values())
        
        if total_adjusted > 0:
            for asset in adjusted_sizes:
                adjusted_sizes[asset] *= total_base / total_adjusted
        
        return adjusted_sizes
    
    def should_adjust_allocations(self) -> bool:
        """
        Determine if allocations should be adjusted based on correlation changes.
        
        Returns:
            True if allocations should be adjusted, False otherwise
        """
        # Always adjust if regime changed
        if self.current_regime != self.previous_regime:
            return True
            
        # Calculate change in average correlation
        if len(self.correlation_history) < 2:
            return False
            
        _, prev_stats = self.correlation_history[-2]
        prev_avg_corr = prev_stats.average_correlation
        curr_avg_corr = self.current_correlation_stats.average_correlation
        
        corr_change = abs(curr_avg_corr - prev_avg_corr)
        
        # Adjust if correlation changed significantly
        return corr_change >= self.rebalance_threshold
        
    def get_risk_assessment(self) -> Dict[str, Any]:
        """
        Get a complete correlation risk assessment.
        
        Returns:
            Dictionary containing correlation risk metrics and recommendations
        """
        if self.current_correlation_stats is None:
            return {
                'status': 'insufficient_data',
                'recommendation': 'Continue data collection'
            }
            
        # Correlation metrics
        stats = self.current_correlation_stats
        
        # Diversification score
        div_score = self.get_diversification_score()
        
        # Get highly correlated pairs
        high_corr_pairs = self.get_highly_correlated_pairs()
        
        # Determine risk level
        if self.current_regime == CorrelationRegime.CRISIS:
            risk_level = "critical"
            recommendation = "Significantly reduce position sizes and increase cash allocation"
        elif self.current_regime == CorrelationRegime.HIGH:
            risk_level = "elevated"
            recommendation = "Reduce allocation to highly correlated assets"
        elif self.current_regime == CorrelationRegime.MODERATE:
            risk_level = "moderate"
            recommendation = "Monitor correlation trends" if div_score >= 0.7 else "Consider adding uncorrelated assets"
        else:  # LOW
            risk_level = "low"
            recommendation = "Maintain current allocations"
        
        # Create assessment
        assessment = {
            'status': 'ok',
            'risk_level': risk_level,
            'regime': self.current_regime.value,
            'avg_correlation': stats.average_correlation,
            'max_correlation': stats.max_correlation,
            'effective_positions': stats.effective_n,
            'diversification_score': div_score,
            'crisis_probability': stats.crisis_probability,
            'recommendation': recommendation,
            'high_correlation_pairs': [(a, b, c) for a, b, c in high_corr_pairs],
            'correlation_change_triggered': self.should_adjust_allocations(),
            'last_update': self.last_update_time
        }
        
        return assessment 