# Statistical Significance Testing Module
"""
Statistical Significance Testing Module
-------------------------------------
This module provides tools for evaluating the statistical significance of
trading strategy performance in walk-forward testing.

Key features:
1. Multiple hypothesis testing with appropriate corrections
2. Reality check and SPA tests for data snooping bias
3. Performance metrics with confidence intervals
4. Bootstrapping and Monte Carlo methods for robust evaluation
5. Regime-specific significance testing
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any, Callable, Iterator
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import logging
from datetime import datetime
import warnings
from statsmodels.stats.multitest import multipletests
from sklearn.utils import resample

# Configure logger
logger = logging.getLogger(__name__)

class PerformanceSignificanceTester:
    """
    Evaluate the statistical significance of trading strategy performance.
    
    This class implements various statistical tests to determine if a strategy's
    performance is statistically significant or likely due to chance. It provides
    methods for hypothesis testing, bootstrapping, and confidence interval estimation.
    
    Parameters:
    -----------
    alpha : float
        Significance level for hypothesis tests (default: 0.05)
    n_bootstrap : int
        Number of bootstrap samples for CI estimation (default: 1000)
    multiple_test_correction : str
        Method for multiple testing correction ('bonferroni', 'fdr_bh', etc.)
    random_state : Optional[int]
        Random seed for reproducibility
    """
    
    def __init__(
        self,
        alpha: float = 0.05,
        n_bootstrap: int = 1000,
        multiple_test_correction: str = 'fdr_bh',
        random_state: Optional[int] = None
    ):
        self.alpha = alpha
        self.n_bootstrap = n_bootstrap
        self.multiple_test_correction = multiple_test_correction
        self.random_state = random_state
        
        # Validate parameters
        self._validate_parameters()
        
        # Set random state
        if self.random_state is not None:
            np.random.seed(self.random_state)
        
        # Storage for test results
        self.test_results = {}
        self.bootstrap_distributions = {}
        self.confidence_intervals = {}
    
    def _validate_parameters(self) -> None:
        """Validate constructor parameters."""
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        
        if self.n_bootstrap <= 0:
            raise ValueError("n_bootstrap must be positive")
        
        valid_corrections = [
            'bonferroni', 'sidak', 'holm-sidak', 'holm', 
            'simes-hochberg', 'hommel', 'fdr_bh', 'fdr_by', 'fdr_tsbh', 'fdr_tsbky'
        ]
        
        if self.multiple_test_correction not in valid_corrections:
            raise ValueError(f"multiple_test_correction must be one of {valid_corrections}")
            
    def t_test_returns(
        self, 
        returns: Union[pd.Series, np.ndarray],
        benchmark_returns: Optional[Union[pd.Series, np.ndarray]] = None,
        test_type: str = 'one-sample'
    ) -> Dict[str, Any]:
        """
        Perform t-test on strategy returns.
        
        Parameters:
        -----------
        returns : Union[pd.Series, np.ndarray]
            Strategy returns
        benchmark_returns : Optional[Union[pd.Series, np.ndarray]]
            Benchmark returns (for two-sample tests)
        test_type : str
            Type of t-test ('one-sample', 'two-sample', 'paired')
            
        Returns:
        --------
        Dict[str, Any]
            Dictionary with test results
        """
        # Convert inputs to numpy arrays
        returns_array = np.asarray(returns)
        
        if benchmark_returns is not None:
            benchmark_array = np.asarray(benchmark_returns)
            
            # Ensure lengths match for paired test
            if test_type == 'paired' and len(returns_array) != len(benchmark_array):
                raise ValueError("Returns and benchmark must have same length for paired test")
            
        # Perform appropriate t-test
        if test_type == 'one-sample':
            # Test if mean returns are significantly different from zero
            t_stat, p_value = stats.ttest_1samp(returns_array, 0)
            dof = len(returns_array) - 1
            alternative = 'two-sided'
            
            # Calculate additional metrics
            effect_size = np.mean(returns_array) / np.std(returns_array, ddof=1)  # Cohen's d
            
        elif test_type == 'two-sample':
            if benchmark_returns is None:
                raise ValueError("benchmark_returns required for two-sample test")
                
            # Test if strategy returns are significantly different from benchmark
            t_stat, p_value = stats.ttest_ind(returns_array, benchmark_array, equal_var=False)
            dof = len(returns_array) + len(benchmark_array) - 2
            alternative = 'two-sided'
            
            # Calculate additional metrics
            pooled_std = np.sqrt(
                ((len(returns_array) - 1) * np.var(returns_array, ddof=1) + 
                 (len(benchmark_array) - 1) * np.var(benchmark_array, ddof=1)) / 
                (len(returns_array) + len(benchmark_array) - 2)
            effect_size = (np.mean(returns_array) - np.mean(benchmark_array)) / pooled_std  # Cohen's d
            
        elif test_type == 'paired':
            if benchmark_returns is None:
                raise ValueError("benchmark_returns required for paired test")
                
            # Test if strategy outperforms benchmark on a paired basis
            t_stat, p_value = stats.ttest_rel(returns_array, benchmark_array)
            dof = len(returns_array) - 1
            alternative = 'two-sided'
            
            # Calculate additional metrics
            diff = returns_array - benchmark_array
            effect_size = np.mean(diff) / np.std(diff, ddof=1)  # Cohen's d for paired test
            
        else:
            raise ValueError(f"Unknown test_type: {test_type}")
        
        # Calculate confidence interval for mean return
        ci_low, ci_high = stats.t.interval(
            1 - self.alpha, 
            dof, 
            loc=np.mean(returns_array), 
            scale=stats.sem(returns_array)
        )
        
        # Determine whether to reject the null hypothesis
        reject_null = p_value < self.alpha
        
        # Store and return results
        results = {
            'test_type': test_type,
            't_statistic': t_stat,
            'p_value': p_value,
            'degrees_of_freedom': dof,
            'alpha': self.alpha,
            'reject_null': reject_null,
            'alternative': alternative,
            'effect_size': effect_size,
            'mean_return': np.mean(returns_array),
            'annualized_return': np.mean(returns_array) * 252,  # Assuming daily returns
            'std_return': np.std(returns_array, ddof=1),
            'annualized_volatility': np.std(returns_array, ddof=1) * np.sqrt(252),  # Assuming daily returns
            'sharpe_ratio': np.mean(returns_array) / np.std(returns_array, ddof=1) * np.sqrt(252),  # Assuming daily returns
            'confidence_interval': (ci_low, ci_high),
            'sample_size': len(returns_array)
        }
        
        if benchmark_returns is not None:
            results['benchmark_mean_return'] = np.mean(benchmark_array)
            results['benchmark_std_return'] = np.std(benchmark_array, ddof=1)
            
            if test_type == 'paired':
                results['mean_difference'] = np.mean(returns_array - benchmark_array)
        
        # Save to instance
        self.test_results['t_test_returns'] = results
        
        return results
        
    def bootstrap_returns(
        self, 
        returns: Union[pd.Series, np.ndarray],
        statistic: Union[str, Callable] = 'mean',
        benchmark_returns: Optional[Union[pd.Series, np.ndarray]] = None,
        block_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform bootstrap analysis of returns to estimate confidence intervals.
        
        Parameters:
        -----------
        returns : Union[pd.Series, np.ndarray]
            Strategy returns
        statistic : Union[str, Callable]
            Statistic to bootstrap ('mean', 'sharpe', etc. or callable)
        benchmark_returns : Optional[Union[pd.Series, np.ndarray]]
            Benchmark returns for relative metrics
        block_size : Optional[int]
            Size of blocks for block bootstrap (for time series with autocorrelation)
            
        Returns:
        --------
        Dict[str, Any]
            Dictionary with bootstrap results
        """
        # Convert inputs to numpy arrays
        returns_array = np.asarray(returns)
        
        if benchmark_returns is not None:
            benchmark_array = np.asarray(benchmark_returns)
            
            # Ensure lengths match
            if len(returns_array) != len(benchmark_array):
                raise ValueError("Returns and benchmark must have same length")
        
        # Define statistic to bootstrap
        if callable(statistic):
            stat_func = statistic
            stat_name = statistic.__name__
        elif statistic == 'mean':
            stat_func = np.mean
            stat_name = 'mean'
        elif statistic == 'sharpe':
            stat_func = lambda x: np.mean(x) / np.std(x, ddof=1) * np.sqrt(252)  # Annualized Sharpe
            stat_name = 'sharpe_ratio'
        elif statistic == 'sortino':
            def sortino_ratio(x):
                downside_returns = x[x < 0]
                if len(downside_returns) == 0:
                    return np.inf
                return np.mean(x) / np.std(downside_returns, ddof=1) * np.sqrt(252)
            stat_func = sortino_ratio
            stat_name = 'sortino_ratio'
        elif statistic == 'excess_return':
            if benchmark_returns is None:
                raise ValueError("benchmark_returns required for 'excess_return'")
            stat_func = lambda x: np.mean(x - benchmark_array)
            stat_name = 'excess_return'
        elif statistic == 'information_ratio':
            if benchmark_returns is None:
                raise ValueError("benchmark_returns required for 'information_ratio'")
            stat_func = lambda x: np.mean(x - benchmark_array) / np.std(x - benchmark_array, ddof=1) * np.sqrt(252)
            stat_name = 'information_ratio'
        else:
            raise ValueError(f"Unknown statistic: {statistic}")
        
        # Calculate original statistic
        original_stat = stat_func(returns_array)
        
        # Perform bootstrap
        bootstrap_samples = []
        
        if block_size is not None:
            # Block bootstrap for time series
            bootstrap_samples = self._block_bootstrap(
                returns_array, stat_func, block_size
            )
        else:
            # Simple IID bootstrap
            rng = np.random.RandomState(self.random_state)
            
            for _ in range(self.n_bootstrap):
                # Generate bootstrap sample
                boot_idx = rng.randint(0, len(returns_array), size=len(returns_array))
                boot_sample = returns_array[boot_idx]
                
                # If we have benchmark returns, need to maintain alignment
                if benchmark_returns is not None and 'benchmark' in stat_name:
                    boot_benchmark = benchmark_array[boot_idx]
                    # Create a temporary bootstrap sample for the statistic function
                    # This assumes the statistic function uses the globally defined benchmark_array
                    temp_benchmark_array = benchmark_array
                    benchmark_array = boot_benchmark
                    boot_stat = stat_func(boot_sample)
                    # Restore the original benchmark array
                    benchmark_array = temp_benchmark_array
                else:
                    boot_stat = stat_func(boot_sample)
                
                bootstrap_samples.append(boot_stat)
        
        # Convert to numpy array
        bootstrap_samples = np.array(bootstrap_samples)
        
        # Calculate percentile confidence intervals
        ci_low = np.percentile(bootstrap_samples, self.alpha/2 * 100)
        ci_high = np.percentile(bootstrap_samples, (1 - self.alpha/2) * 100)
        
        # Calculate p-value (proportion of bootstrap samples where statistic <= 0)
        # For metrics where higher is better
        if stat_name in ['mean', 'sharpe_ratio', 'sortino_ratio', 'excess_return', 'information_ratio']:
            p_value = np.mean(bootstrap_samples <= 0)
        else:
            # For metrics where lower is better (like drawdown)
            p_value = np.mean(bootstrap_samples >= 0)
        
        # Store and return results
        results = {
            'statistic_name': stat_name,
            'original_statistic': original_stat,
            'bootstrap_mean': np.mean(bootstrap_samples),
            'bootstrap_std': np.std(bootstrap_samples, ddof=1),
            'bootstrap_quantiles': {
                '1%': np.percentile(bootstrap_samples, 1),
                '5%': np.percentile(bootstrap_samples, 5),
                '25%': np.percentile(bootstrap_samples, 25),
                '50%': np.percentile(bootstrap_samples, 50),
                '75%': np.percentile(bootstrap_samples, 75),
                '95%': np.percentile(bootstrap_samples, 95),
                '99%': np.percentile(bootstrap_samples, 99)
            },
            'confidence_interval': (ci_low, ci_high),
            'p_value': p_value,
            'reject_null': p_value < self.alpha,
            'alpha': self.alpha,
            'n_bootstrap': self.n_bootstrap,
            'bootstrap_method': 'block' if block_size else 'iid',
            'block_size': block_size
        }
        
        # Save distribution for plotting
        self.bootstrap_distributions[stat_name] = bootstrap_samples
        self.confidence_intervals[stat_name] = (ci_low, ci_high)
        
        # Save to instance
        self.test_results[f'bootstrap_{stat_name}'] = results
        
        return results
    
    def _block_bootstrap(
        self, 
        data: np.ndarray, 
        statistic: Callable, 
        block_size: int
    ) -> List[float]:
        """
        Perform block bootstrap for time series data with autocorrelation.
        
        Parameters:
        -----------
        data : np.ndarray
            Time series data
        statistic : Callable
            Statistic function to apply to each bootstrap sample
        block_size : int
            Size of blocks to resample
            
        Returns:
        --------
        List[float]
            Bootstrap sample statistics
        """
        n = len(data)
        rng = np.random.RandomState(self.random_state)
        bootstrap_samples = []
        
        for _ in range(self.n_bootstrap):
            # Create bootstrap sample
            sample = np.zeros(n)
            
            # Determine how many blocks we need
            n_blocks = int(np.ceil(n / block_size))
            
            # Sample blocks with replacement
            block_starts = rng.randint(0, n - block_size + 1, size=n_blocks)
            
            # Fill sample with blocks
            pos = 0
            for start in block_starts:
                end = min(pos + block_size, n)
                sample_end = min(start + end - pos, len(data))
                sample[pos:end] = data[start:sample_end]
                pos = end
                
                if pos >= n:
                    break
            
            # Calculate statistic
            stat = statistic(sample)
            bootstrap_samples.append(stat)
        
        return bootstrap_samples
        
    def multiple_hypothesis_test(
        self, 
        pvalues: Union[List[float], np.ndarray],
        hypotheses: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Perform multiple hypothesis testing with appropriate corrections.
        
        Parameters:
        -----------
        pvalues : Union[List[float], np.ndarray]
            P-values from individual hypothesis tests
        hypotheses : Optional[List[str]]
            Descriptions of the hypotheses being tested
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with test results, corrected p-values, and decisions
        """
        pvalues = np.asarray(pvalues)
        
        # Perform multiple test correction
        reject, pvals_corrected, _, _ = multipletests(
            pvalues, 
            alpha=self.alpha, 
            method=self.multiple_test_correction
        )
        
        # Create results DataFrame
        results = pd.DataFrame({
            'original_pvalue': pvalues,
            'corrected_pvalue': pvals_corrected,
            'reject_null': reject
        })
        
        # Add hypothesis descriptions if provided
        if hypotheses is not None:
            if len(hypotheses) != len(pvalues):
                logger.warning(
                    f"Length of hypotheses ({len(hypotheses)}) does not match "
                    f"length of pvalues ({len(pvalues)})"
                )
                hypotheses = hypotheses[:len(pvalues)]
            
            results['hypothesis'] = hypotheses
        
        # Add significant column for easier filtering
        results['significant'] = results['reject_null']
        
        # Store results
        self.test_results['multiple_hypothesis_test'] = results
        
        return results
    
    def performance_metrics_with_ci(
        self, 
        returns: Union[pd.Series, np.ndarray],
        benchmark_returns: Optional[Union[pd.Series, np.ndarray]] = None,
        risk_free_rate: float = 0.0,
        periodicity: str = 'daily'
    ) -> pd.DataFrame:
        """
        Calculate performance metrics with bootstrap confidence intervals.
        
        Parameters:
        -----------
        returns : Union[pd.Series, np.ndarray]
            Strategy returns
        benchmark_returns : Optional[Union[pd.Series, np.ndarray]]
            Benchmark returns for relative metrics
        risk_free_rate : float
            Risk-free rate (annualized)
        periodicity : str
            Data frequency ('daily', 'weekly', 'monthly')
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with performance metrics and confidence intervals
        """
        # Convert inputs to numpy arrays
        returns_array = np.asarray(returns)
        
        # Set annualization factor based on periodicity
        if periodicity == 'daily':
            ann_factor = 252
        elif periodicity == 'weekly':
            ann_factor = 52
        elif periodicity == 'monthly':
            ann_factor = 12
        else:
            raise ValueError(f"Unknown periodicity: {periodicity}")
        
        # Adjust risk-free rate to match periodicity
        periodic_rf = risk_free_rate / ann_factor
        
        # Calculate excess returns
        excess_returns = returns_array - periodic_rf
        
        # Initialize results dictionary
        metrics_with_ci = {}
        
        # Define metrics to calculate with their descriptions
        metrics = {
            'mean': 'Mean Return',
            'annualized_return': 'Annualized Return',
            'volatility': 'Volatility',
            'sharpe': 'Sharpe Ratio',
            'sortino': 'Sortino Ratio',
            'max_drawdown': 'Maximum Drawdown',
            'skewness': 'Return Skewness',
            'kurtosis': 'Return Kurtosis'
        }
        
        # Add benchmark-relative metrics if benchmark provided
        if benchmark_returns is not None:
            metrics.update({
                'excess_return': 'Excess Return over Benchmark',
                'tracking_error': 'Tracking Error',
                'information_ratio': 'Information Ratio',
                'beta': 'Beta',
                'alpha': 'Alpha (annualized)'
            })
        
        # Calculate each metric with bootstrap CI
        # Mean return
        mean_result = self.bootstrap_returns(excess_returns, 'mean')
        metrics_with_ci['mean'] = {
            'value': mean_result['original_statistic'],
            'ci_lower': mean_result['confidence_interval'][0],
            'ci_upper': mean_result['confidence_interval'][1],
            'p_value': mean_result['p_value'],
            'significant': mean_result['reject_null']
        }
        
        # Annualized return
        metrics_with_ci['annualized_return'] = {
            'value': mean_result['original_statistic'] * ann_factor,
            'ci_lower': mean_result['confidence_interval'][0] * ann_factor,
            'ci_upper': mean_result['confidence_interval'][1] * ann_factor,
            'p_value': mean_result['p_value'],
            'significant': mean_result['reject_null']
        }
        
        # Volatility
        vol_func = lambda x: np.std(x, ddof=1)
        vol_result = self.bootstrap_returns(returns_array, vol_func)
        metrics_with_ci['volatility'] = {
            'value': vol_result['original_statistic'],
            'ci_lower': vol_result['confidence_interval'][0],
            'ci_upper': vol_result['confidence_interval'][1],
            'p_value': None,  # Not applicable
            'significant': None
        }
        
        # Sharpe ratio
        sharpe_result = self.bootstrap_returns(excess_returns, 'sharpe')
        metrics_with_ci['sharpe'] = {
            'value': sharpe_result['original_statistic'],
            'ci_lower': sharpe_result['confidence_interval'][0],
            'ci_upper': sharpe_result['confidence_interval'][1],
            'p_value': sharpe_result['p_value'],
            'significant': sharpe_result['reject_null']
        }
        
        # Sortino ratio
        sortino_result = self.bootstrap_returns(excess_returns, 'sortino')
        metrics_with_ci['sortino'] = {
            'value': sortino_result['original_statistic'],
            'ci_lower': sortino_result['confidence_interval'][0],
            'ci_upper': sortino_result['confidence_interval'][1],
            'p_value': sortino_result['p_value'],
            'significant': sortino_result['reject_null']
        }
        
        # Maximum drawdown
        def max_drawdown(returns):
            # Calculate cumulative returns
            cum_returns = np.cumprod(1 + returns)
            # Calculate running maximum
            running_max = np.maximum.accumulate(cum_returns)
            # Calculate drawdowns
            drawdowns = cum_returns / running_max - 1
            # Return maximum drawdown (minimum value)
            return np.min(drawdowns)
        
        drawdown_result = self.bootstrap_returns(returns_array, max_drawdown)
        metrics_with_ci['max_drawdown'] = {
            'value': drawdown_result['original_statistic'],
            'ci_lower': drawdown_result['confidence_interval'][0],
            'ci_upper': drawdown_result['confidence_interval'][1],
            'p_value': None,  # Not applicable
            'significant': None
        }
        
        # Skewness
        skew_func = lambda x: stats.skew(x)
        skew_result = self.bootstrap_returns(returns_array, skew_func)
        metrics_with_ci['skewness'] = {
            'value': skew_result['original_statistic'],
            'ci_lower': skew_result['confidence_interval'][0],
            'ci_upper': skew_result['confidence_interval'][1],
            'p_value': None,  # Not directly applicable
            'significant': None
        }
        
        # Kurtosis
        kurt_func = lambda x: stats.kurtosis(x)
        kurt_result = self.bootstrap_returns(returns_array, kurt_func)
        metrics_with_ci['kurtosis'] = {
            'value': kurt_result['original_statistic'],
            'ci_lower': kurt_result['confidence_interval'][0],
            'ci_upper': kurt_result['confidence_interval'][1],
            'p_value': None,  # Not directly applicable
            'significant': None
        }
        
        # Calculate benchmark-relative metrics if benchmark provided
        if benchmark_returns is not None:
            benchmark_array = np.asarray(benchmark_returns)
            
            # Excess return over benchmark
            excess_result = self.bootstrap_returns(returns_array, 'excess_return', benchmark_array)
            metrics_with_ci['excess_return'] = {
                'value': excess_result['original_statistic'],
                'ci_lower': excess_result['confidence_interval'][0],
                'ci_upper': excess_result['confidence_interval'][1],
                'p_value': excess_result['p_value'],
                'significant': excess_result['reject_null']
            }
            
            # Tracking error
            def tracking_error(returns):
                return np.std(returns - benchmark_array, ddof=1) * np.sqrt(ann_factor)
            
            te_result = self.bootstrap_returns(returns_array, tracking_error)
            metrics_with_ci['tracking_error'] = {
                'value': te_result['original_statistic'],
                'ci_lower': te_result['confidence_interval'][0],
                'ci_upper': te_result['confidence_interval'][1],
                'p_value': None,  # Not directly applicable
                'significant': None
            }
            
            # Information ratio
            ir_result = self.bootstrap_returns(returns_array, 'information_ratio', benchmark_array)
            metrics_with_ci['information_ratio'] = {
                'value': ir_result['original_statistic'],
                'ci_lower': ir_result['confidence_interval'][0],
                'ci_upper': ir_result['confidence_interval'][1],
                'p_value': ir_result['p_value'],
                'significant': ir_result['reject_null']
            }
            
            # Beta
            def beta(returns):
                cov = np.cov(returns, benchmark_array)[0, 1]
                benchmark_var = np.var(benchmark_array, ddof=1)
                return cov / benchmark_var if benchmark_var > 0 else 0
            
            beta_result = self.bootstrap_returns(returns_array, beta)
            metrics_with_ci['beta'] = {
                'value': beta_result['original_statistic'],
                'ci_lower': beta_result['confidence_interval'][0],
                'ci_upper': beta_result['confidence_interval'][1],
                'p_value': None,  # Not directly applicable
                'significant': None
            }
            
            # Alpha (CAPM)
            def alpha(returns):
                b = beta(returns)
                alpha = np.mean(returns) - b * np.mean(benchmark_array)
                return alpha * ann_factor  # Annualize
            
            alpha_result = self.bootstrap_returns(returns_array, alpha)
            metrics_with_ci['alpha'] = {
                'value': alpha_result['original_statistic'],
                'ci_lower': alpha_result['confidence_interval'][0],
                'ci_upper': alpha_result['confidence_interval'][1],
                'p_value': alpha_result['p_value'],
                'significant': alpha_result['reject_null']
            }
        
        # Convert to DataFrame for easier handling
        metrics_df = pd.DataFrame(metrics_with_ci).T
        
        # Add metric names for readability
        metrics_df['metric_name'] = metrics_df.index.map(lambda x: metrics.get(x, x))
        
        # Reorder columns
        column_order = ['metric_name', 'value', 'ci_lower', 'ci_upper', 'p_value', 'significant']
        metrics_df = metrics_df[column_order]
        
        # Store results
        self.test_results['performance_metrics'] = metrics_df
        
        return metrics_df
        
    def plot_bootstrap_distribution(
        self, 
        statistic_name: str,
        figsize: Tuple[int, int] = (10, 6),
        bins: int = 50,
        show_ci: bool = True,
        show_original: bool = True
    ) -> plt.Figure:
        """
        Plot the bootstrap distribution for a specific statistic.
        
        Parameters:
        -----------
        statistic_name : str
            Name of the statistic to plot
        figsize : Tuple[int, int]
            Figure size
        bins : int
            Number of histogram bins
        show_ci : bool
            Whether to show confidence interval
        show_original : bool
            Whether to show original statistic value
            
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        if statistic_name not in self.bootstrap_distributions:
            logger.warning(f"No bootstrap distribution found for {statistic_name}")
            return None
        
        # Get bootstrap distribution
        bootstrap_samples = self.bootstrap_distributions[statistic_name]
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot histogram
        sns.histplot(bootstrap_samples, bins=bins, kde=True, ax=ax)
        
        # Add confidence interval
        if show_ci and statistic_name in self.confidence_intervals:
            ci_low, ci_high = self.confidence_intervals[statistic_name]
            ax.axvline(x=ci_low, color='r', linestyle='--', 
                      label=f'{(1-self.alpha)*100:.1f}% CI Lower: {ci_low:.4f}')
            ax.axvline(x=ci_high, color='r', linestyle='--',
                      label=f'{(1-self.alpha)*100:.1f}% CI Upper: {ci_high:.4f}')
            
            # Shade the confidence interval
            ax.axvspan(ci_low, ci_high, alpha=0.2, color='red')
        
        # Add original statistic value
        if show_original and statistic_name in self.test_results:
            result_key = f'bootstrap_{statistic_name}'
            if result_key in self.test_results:
                original_stat = self.test_results[result_key]['original_statistic']
                ax.axvline(x=original_stat, color='g', linestyle='-',
                          label=f'Original: {original_stat:.4f}')
        
        # Add zero line for reference
        ax.axvline(x=0, color='k', linestyle='-', alpha=0.3)
        
        # Set labels and title
        ax.set_xlabel(f'{statistic_name.replace("_", " ").title()}')
        ax.set_ylabel('Frequency')
        ax.set_title(f'Bootstrap Distribution of {statistic_name.replace("_", " ").title()}')
        
        # Add legend
        ax.legend()
        
        plt.tight_layout()
        return fig
    
    def plot_performance_metrics(
        self,
        figsize: Tuple[int, int] = (12, 8),
        metrics_to_plot: Optional[List[str]] = None,
        sort_by: str = 'value'
    ) -> plt.Figure:
        """
        Plot performance metrics with confidence intervals.
        
        Parameters:
        -----------
        figsize : Tuple[int, int]
            Figure size
        metrics_to_plot : Optional[List[str]]
            List of metrics to plot (if None, plot all)
        sort_by : str
            How to sort metrics ('value', 'name', 'significance')
            
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        if 'performance_metrics' not in self.test_results:
            logger.warning("No performance metrics to plot")
            return None
        
        # Get metrics DataFrame
        metrics_df = self.test_results['performance_metrics'].copy()
        
        # Filter metrics if specified
        if metrics_to_plot is not None:
            metrics_df = metrics_df.loc[metrics_to_plot]
        
        # Sort metrics
        if sort_by == 'value':
            metrics_df = metrics_df.sort_values('value', ascending=False)
        elif sort_by == 'name':
            metrics_df = metrics_df.sort_index()
        elif sort_by == 'significance':
            # Sort by significance, then by value
            metrics_df['is_significant'] = metrics_df['significant'].fillna(False)
            metrics_df = metrics_df.sort_values(['is_significant', 'value'], ascending=[False, False])
            metrics_df = metrics_df.drop('is_significant', axis=1)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Prepare data for plotting
        metrics = metrics_df.index
        values = metrics_df['value']
        ci_lower = metrics_df['ci_lower']
        ci_upper = metrics_df['ci_upper']
        
        # Calculate error bars
        yerr = np.zeros((2, len(values)))
        yerr[0, :] = values - ci_lower
        yerr[1, :] = ci_upper - values
        
        # Plot metrics with error bars
        ax.errorbar(
            range(len(metrics)), 
            values, 
            yerr=yerr, 
            fmt='o', 
            capsize=5, 
            ecolor='k', 
            markersize=8,
            markerfacecolor='blue'
        )
        
        # Highlight significant metrics
        for i, (idx, row) in enumerate(metrics_df.iterrows()):
            if row['significant'] == True:
                ax.plot(i, row['value'], 'o', markersize=12, markerfacecolor='none', 
                       markeredgecolor='green', markeredgewidth=2)
        
        # Add zero line for reference
        ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        
        # Set labels and title
        ax.set_xticks(range(len(metrics)))
        ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics], rotation=45, ha='right')
        ax.set_ylabel('Value')
        ax.set_title('Performance Metrics with Confidence Intervals')
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def plot_hypothesis_test_results(
        self,
        figsize: Tuple[int, int] = (12, 6)
    ) -> plt.Figure:
        """
        Plot the results of multiple hypothesis tests.
        
        Parameters:
        -----------
        figsize : Tuple[int, int]
            Figure size
            
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        if 'multiple_hypothesis_test' not in self.test_results:
            logger.warning("No multiple hypothesis test results to plot")
            return None
        
        # Get results DataFrame
        results_df = self.test_results['multiple_hypothesis_test'].copy()
        
        # Sort by original p-value
        results_df = results_df.sort_values('original_pvalue')
        
        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Plot 1: Original vs Corrected p-values
        ax1.scatter(results_df['original_pvalue'], results_df['corrected_pvalue'], 
                   c=results_df['reject_null'].map({True: 'green', False: 'red'}),
                   alpha=0.7)
        
        # Add reference line (y=x)
        max_p = max(results_df['original_pvalue'].max(), results_df['corrected_pvalue'].max())
        ax1.plot([0, max_p], [0, max_p], 'k--', alpha=0.5)
        
        # Add significance threshold lines
        ax1.axhline(y=self.alpha, color='r', linestyle='--', alpha=0.5)
        ax1.axvline(x=self.alpha, color='r', linestyle='--', alpha=0.5)
        
        # Set labels and title
        ax1.set_xlabel('Original p-value')
        ax1.set_ylabel('Corrected p-value')
        ax1.set_title('Original vs. Corrected p-values')
        
        # Add grid
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: P-value distribution
        sns.histplot(results_df['original_pvalue'], bins=20, kde=True, ax=ax2, color='blue', 
                    label='Original')
        sns.histplot(results_df['corrected_pvalue'], bins=20, kde=True, ax=ax2, color='green', 
                    label='Corrected')
        
        # Add significance threshold line
        ax2.axvline(x=self.alpha, color='r', linestyle='--', 
                   label=f'Alpha = {self.alpha}')
        
        # Set labels and title
        ax2.set_xlabel('p-value')
        ax2.set_ylabel('Frequency')
        ax2.set_title('P-value Distribution')
        
        # Add legend
        ax2.legend()
        
        # Add grid
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def plot_regime_performance(
        self,
        returns: Union[pd.Series, np.ndarray],
        regimes: Union[pd.Series, np.ndarray],
        benchmark_returns: Optional[Union[pd.Series, np.ndarray]] = None,
        figsize: Tuple[int, int] = (15, 10)
    ) -> plt.Figure:
        """
        Plot performance metrics by market regime.
        
        Parameters:
        -----------
        returns : Union[pd.Series, np.ndarray]
            Strategy returns
        regimes : Union[pd.Series, np.ndarray]
            Regime labels for each return observation
        benchmark_returns : Optional[Union[pd.Series, np.ndarray]]
            Benchmark returns for relative metrics
        figsize : Tuple[int, int]
            Figure size
            
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        # Convert inputs to numpy arrays
        returns_array = np.asarray(returns)
        regimes_array = np.asarray(regimes)
        
        if benchmark_returns is not None:
            benchmark_array = np.asarray(benchmark_returns)
            
            # Ensure lengths match
            if len(returns_array) != len(benchmark_array):
                raise ValueError("Returns and benchmark must have same length")
        
        # Ensure returns and regimes have the same length
        if len(returns_array) != len(regimes_array):
            raise ValueError("Returns and regimes must have same length")
        
        # Get unique regimes
        unique_regimes = np.unique(regimes_array)
        n_regimes = len(unique_regimes)
        
        # Define metrics to calculate
        metrics = ['mean', 'sharpe', 'sortino', 'max_drawdown']
        if benchmark_returns is not None:
            metrics.extend(['excess_return', 'information_ratio', 'beta', 'alpha'])
        
        # Calculate metrics for each regime
        regime_metrics = {}
        
        for regime in unique_regimes:
            # Get returns for this regime
            regime_mask = (regimes_array == regime)
            regime_returns = returns_array[regime_mask]
            
            if benchmark_returns is not None:
                regime_benchmark = benchmark_array[regime_mask]
            else:
                regime_benchmark = None
            
            # Calculate metrics
            metrics_df = self.performance_metrics_with_ci(
                regime_returns, 
                regime_benchmark,
                periodicity='daily'  # Assuming daily returns
            )
            
            # Store metrics
            regime_metrics[regime] = metrics_df
        
        # Create figure with subplots for each metric
        n_metrics = len(metrics)
        n_cols = min(3, n_metrics)
        n_rows = (n_metrics + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        
        # Flatten axes if needed
        if n_rows == 1 and n_cols == 1:
            axes = np.array([axes])
        elif n_rows == 1 or n_cols == 1:
            axes = axes.flatten()
        
        # Plot each metric
        for i, metric in enumerate(metrics):
            if i < len(axes):
                ax = axes[i]
                
                # Prepare data for this metric
                regime_values = []
                regime_ci_lower = []
                regime_ci_upper = []
                regime_labels = []
                
                for regime in unique_regimes:
                    if metric in regime_metrics[regime].index:
                        regime_values.append(regime_metrics[regime].loc[metric, 'value'])
                        regime_ci_lower.append(regime_metrics[regime].loc[metric, 'ci_lower'])
                        regime_ci_upper.append(regime_metrics[regime].loc[metric, 'ci_upper'])
                        regime_labels.append(str(regime))
                
                # Calculate error bars
                yerr = np.zeros((2, len(regime_values)))
                yerr[0, :] = np.array(regime_values) - np.array(regime_ci_lower)
                yerr[1, :] = np.array(regime_ci_upper) - np.array(regime_values)
                
                # Plot metric by regime
                ax.bar(regime_labels, regime_values, yerr=yerr, capsize=5, alpha=0.7)
                
                # Add zero line for reference
                ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
                
                # Set labels and title
                ax.set_xlabel('Regime')
                ax.set_ylabel(metric.replace('_', ' ').title())
                ax.set_title(f'{metric.replace("_", " ").title()} by Regime')
                
                # Add grid
                ax.grid(True, alpha=0.3)
        
        # Hide any unused axes
        for j in range(i + 1, len(axes)):
            axes[j].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive summary report of all test results.
        
        Returns:
        --------
        Dict[str, Any]
            Dictionary with summary information
        """
        summary = {
            'test_count': len(self.test_results),
            'alpha': self.alpha,
            'n_bootstrap': self.n_bootstrap,
            'multiple_test_correction': self.multiple_test_correction
        }
        
        # Summarize t-test results
        if 't_test_returns' in self.test_results:
            t_test = self.test_results['t_test_returns']
            summary['t_test'] = {
                'test_type': t_test['test_type'],
                'reject_null': t_test['reject_null'],
                'p_value': t_test['p_value'],
                't_statistic': t_test['t_statistic'],
                'effect_size': t_test['effect_size'],
                'mean_return': t_test['mean_return'],
                'annualized_return': t_test['annualized_return'],
                'sharpe_ratio': t_test['sharpe_ratio']
            }
        
        # Summarize bootstrap results
        bootstrap_results = {}
        for key, value in self.test_results.items():
            if key.startswith('bootstrap_'):
                stat_name = key.replace('bootstrap_', '')
                bootstrap_results[stat_name] = {
                    'original_statistic': value['original_statistic'],
                    'bootstrap_mean': value['bootstrap_mean'],
                    'p_value': value['p_value'],
                    'reject_null': value['reject_null'],
                    'confidence_interval': value['confidence_interval']
                }
        
        if bootstrap_results:
            summary['bootstrap_results'] = bootstrap_results
        
        # Summarize performance metrics
        if 'performance_metrics' in self.test_results:
            metrics_df = self.test_results['performance_metrics']
            
            # Count significant metrics
            significant_count = metrics_df['significant'].sum()
            total_testable = metrics_df['significant'].count()
            
            summary['performance_metrics'] = {
                'significant_count': significant_count,
                'total_testable': total_testable,
                'significant_percentage': significant_count / total_testable if total_testable > 0 else 0,
                'metrics': metrics_df.to_dict(orient='index')
            }
        
        # Summarize multiple hypothesis test
        if 'multiple_hypothesis_test' in self.test_results:
            mht_df = self.test_results['multiple_hypothesis_test']
            
            # Count significant hypotheses
            significant_count = mht_df['significant'].sum()
            total_tests = len(mht_df)
            
            summary['multiple_hypothesis_test'] = {
                'significant_count': significant_count,
                'total_tests': total_tests,
                'significant_percentage': significant_count / total_tests if total_tests > 0 else 0,
                'correction_method': self.multiple_test_correction
            }
        
        return summary
