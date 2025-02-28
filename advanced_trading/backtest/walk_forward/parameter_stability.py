"""
Parameter Stability Analysis Module
---------------------------------
This module provides tools for analyzing the stability of model parameters
across different folds in walk-forward testing.

Key features:
1. Parameter tracking across walk-forward iterations
2. Statistical analysis of parameter stability
3. Visualization of parameter evolution over time
4. Stability metrics for parameter sensitivity analysis
5. Recommendations for parameter smoothing or constraints
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any, Callable
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.base import BaseEstimator
import logging
from datetime import datetime
import warnings

# Configure logger
logger = logging.getLogger(__name__)

class ParameterTracker:
    """
    Track and analyze model parameters across walk-forward iterations.
    
    This class helps detect parameter instability which can lead to poor 
    out-of-sample performance. It tracks parameters across folds, calculates
    stability metrics, and provides visualizations.
    
    Parameters:
    -----------
    param_extract_func : Optional[Callable]
        Function to extract parameters from model (if None, will try model.get_params())
    stability_threshold : float
        Threshold for coefficient of variation to be considered stable
    track_performance : bool
        Whether to track performance metrics alongside parameters
    param_names : Optional[List[str]]
        Specific parameter names to track (if None, track all)
    """
    
    def __init__(
        self,
        param_extract_func: Optional[Callable] = None,
        stability_threshold: float = 0.25,
        track_performance: bool = True,
        param_names: Optional[List[str]] = None
    ):
        self.param_extract_func = param_extract_func
        self.stability_threshold = stability_threshold
        self.track_performance = track_performance
        self.param_names = param_names
        
        # Storage for parameters and metrics
        self.parameter_history = {}
        self.performance_history = []
        self.fold_info = []
        self.parameters_df = None
        self.stability_metrics = None
    
    def extract_parameters(self, model: BaseEstimator) -> Dict[str, float]:
        """
        Extract parameters from a fitted model.
        
        Parameters:
        -----------
        model : BaseEstimator
            Fitted model object
            
        Returns:
        --------
        Dict[str, float]
            Dictionary of parameter names and values
        """
        if self.param_extract_func is not None:
            # Use custom function
            params = self.param_extract_func(model)
        elif hasattr(model, 'get_params'):
            # Use scikit-learn's get_params
            params = self._flatten_params(model.get_params())
        elif hasattr(model, 'coef_'):
            # Linear model coefficients
            if hasattr(model, 'feature_names_in_'):
                feature_names = model.feature_names_in_
            else:
                feature_names = [f'feature_{i}' for i in range(len(model.coef_))]
            
            # Handle multi-output models
            if model.coef_.ndim > 1:
                params = {}
                for i, coef_array in enumerate(model.coef_):
                    for j, coef in enumerate(coef_array):
                        params[f'coef_{i}_{feature_names[j]}'] = coef
                
                if hasattr(model, 'intercept_'):
                    if isinstance(model.intercept_, np.ndarray) and len(model.intercept_) > 1:
                        for i, intercept in enumerate(model.intercept_):
                            params[f'intercept_{i}'] = intercept
                    else:
                        params['intercept'] = model.intercept_
            else:
                params = {f'coef_{feature_names[i]}': coef for i, coef in enumerate(model.coef_)}
                if hasattr(model, 'intercept_'):
                    params['intercept'] = model.intercept_
        else:
            # Try some common parameter attributes
            params = {}
            for attr in dir(model):
                if attr.startswith('_'):
                    continue
                    
                value = getattr(model, attr)
                if isinstance(value, (int, float, bool)) and not callable(value):
                    params[attr] = value
        
        # Filter to specific parameters if requested
        if self.param_names is not None:
            params = {k: v for k, v in params.items() if k in self.param_names}
        
        return params
    
    def _flatten_params(self, params: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """
        Flatten nested parameter dictionaries.
        
        Parameters:
        -----------
        params : Dict[str, Any]
            Nested parameter dictionary
        prefix : str
            Prefix for flattened parameter names
            
        Returns:
        --------
        Dict[str, Any]
            Flattened parameter dictionary
        """
        flattened = {}
        
        for key, value in params.items():
            new_key = f"{prefix}{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                flattened.update(self._flatten_params(value, f"{new_key}__"))
            elif isinstance(value, (int, float, bool)) and not callable(value):
                # Only keep numeric parameters
                flattened[new_key] = value
        
        return flattened
    
    def add_fold(
        self, 
        model: BaseEstimator, 
        fold_id: int, 
        fold_date: Optional[datetime] = None, 
        performance_metrics: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Add parameters from one walk-forward fold.
        
        Parameters:
        -----------
        model : BaseEstimator
            Fitted model from this fold
        fold_id : int
            Fold identifier (increasing with time)
        fold_date : Optional[datetime]
            Date corresponding to this fold
        performance_metrics : Optional[Dict[str, float]]
            Performance metrics for this fold
        """
        # Extract parameters
        try:
            params = self.extract_parameters(model)
        except Exception as e:
            logger.warning(f"Error extracting parameters from model: {str(e)}")
            params = {}
        
        # Update parameter history
        for param_name, param_value in params.items():
            if param_name not in self.parameter_history:
                self.parameter_history[param_name] = []
            
            self.parameter_history[param_name].append(param_value)
        
        # Store fold info
        self.fold_info.append({
            'fold_id': fold_id,
            'fold_date': fold_date or datetime.now(),
            'n_params': len(params)
        })
        
        # Store performance metrics
        if self.track_performance and performance_metrics:
            metrics_with_fold = performance_metrics.copy()
            metrics_with_fold['fold_id'] = fold_id
            metrics_with_fold['fold_date'] = fold_date or datetime.now()
            self.performance_history.append(metrics_with_fold)
    
    def add_models(
        self, 
        models: List[BaseEstimator], 
        fold_dates: Optional[List[datetime]] = None,
        performance_metrics: Optional[List[Dict[str, float]]] = None
    ) -> None:
        """
        Add parameters from multiple models from walk-forward folds.
        
        Parameters:
        -----------
        models : List[BaseEstimator]
            List of fitted models, one per fold
        fold_dates : Optional[List[datetime]]
            Dates corresponding to each fold
        performance_metrics : Optional[List[Dict[str, float]]]
            Performance metrics for each fold
        """
        # Validate inputs
        n_models = len(models)
        if fold_dates is not None and len(fold_dates) != n_models:
            raise ValueError("Length of fold_dates must match length of models")
        
        if performance_metrics is not None and len(performance_metrics) != n_models:
            raise ValueError("Length of performance_metrics must match length of models")
        
        # Add each model
        for i, model in enumerate(models):
            fold_date = fold_dates[i] if fold_dates is not None else None
            metrics = performance_metrics[i] if performance_metrics is not None else None
            self.add_fold(model, i+1, fold_date, metrics)
    
    def compute_stability_metrics(self) -> pd.DataFrame:
        """
        Compute stability metrics for all tracked parameters.
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with stability metrics for each parameter
        """
        if not self.parameter_history:
            logger.warning("No parameters tracked yet")
            return pd.DataFrame()
        
        # Initialize metrics
        metrics = []
        
        for param_name, param_values in self.parameter_history.items():
            if len(param_values) <= 1:
                continue
                
            # Convert to numpy array for calculations
            values = np.array(param_values)
            
            # Calculate basic statistics
            mean = np.mean(values)
            median = np.median(values)
            std = np.std(values)
            min_val = np.min(values)
            max_val = np.max(values)
            range_val = max_val - min_val
            
            # Calculate coefficient of variation (cv)
            # For stability - lower is better
            if mean != 0:
                cv = std / abs(mean)
            else:
                cv = np.nan
            
            # Calculate trend using regression slope
            fold_ids = np.arange(1, len(values) + 1)
            if len(values) > 2:
                slope, intercept, r_value, p_value, std_err = stats.linregress(fold_ids, values)
                trend_significance = p_value
            else:
                slope = intercept = r_value = p_value = std_err = np.nan
                trend_significance = np.nan
            
            # Stability classification
            if np.isnan(cv):
                stability = "Unknown"
            elif cv <= self.stability_threshold / 2:
                stability = "Very Stable"
            elif cv <= self.stability_threshold:
                stability = "Stable"
            elif cv <= self.stability_threshold * 2:
                stability = "Moderately Unstable"
            else:
                stability = "Unstable"
            
            # Store metrics
            metrics.append({
                'parameter': param_name,
                'mean': mean,
                'median': median,
                'std': std,
                'min': min_val,
                'max': max_val,
                'range': range_val,
                'cv': cv,
                'trend_slope': slope,
                'trend_r2': r_value**2,
                'trend_p_value': p_value,
                'stability': stability,
                'n_folds': len(values)
            })
        
        # Convert to DataFrame and sort
        metrics_df = pd.DataFrame(metrics)
        if not metrics_df.empty:
            metrics_df = metrics_df.sort_values('cv', ascending=True)
        
        # Store for later use
        self.stability_metrics = metrics_df
        
        return metrics_df
    
    def create_parameters_dataframe(self) -> pd.DataFrame:
        """
        Create a DataFrame with all parameters across folds.
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with parameters by fold
        """
        if not self.parameter_history:
            logger.warning("No parameters tracked yet")
            return pd.DataFrame()
            
        # Create fold identifiers
        fold_ids = [info['fold_id'] for info in self.fold_info]
        fold_dates = [info['fold_date'] for info in self.fold_info]
        
        # Initialize with fold information
        data = {
            'fold_id': fold_ids,
            'fold_date': fold_dates
        }
        
        # Add parameters
        for param_name, param_values in self.parameter_history.items():
            # Pad with NaN if needed (some parameters might be missing in early folds)
            if len(param_values) < len(fold_ids):
                param_values = param_values + [np.nan] * (len(fold_ids) - len(param_values))
            
            data[param_name] = param_values
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Add performance metrics if available
        if self.performance_history:
            perf_df = pd.DataFrame(self.performance_history)
            
            # Merge on fold_id
            merged = pd.merge(df, perf_df, on='fold_id', how='left', suffixes=('', '_perf'))
            
            # Handle duplicate columns
            for col in merged.columns:
                if col.endswith('_perf'):
                    orig_col = col[:-5]
                    if orig_col != 'fold_date':  # Skip fold_date
                        if orig_col in merged.columns:
                            merged = merged.drop(orig_col, axis=1)
                        merged = merged.rename(columns={col: orig_col})
            
            df = merged
        
        # Store for later use
        self.parameters_df = df
        
        return df
    
    def get_unstable_parameters(self, threshold: Optional[float] = None) -> pd.DataFrame:
        """
        Get parameters that are considered unstable.
        
        Parameters:
        -----------
        threshold : Optional[float]
            Coefficient of variation threshold (if None, use self.stability_threshold)
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with unstable parameters and their metrics
        """
        if self.stability_metrics is None:
            self.compute_stability_metrics()
        
        if self.stability_metrics is None or self.stability_metrics.empty:
            return pd.DataFrame()
        
        threshold = threshold or self.stability_threshold
        
        # Filter to unstable parameters
        unstable = self.stability_metrics[self.stability_metrics['cv'] > threshold]
        
        return unstable.sort_values('cv', ascending=False)
    
    def plot_parameter_evolution(
        self, 
        parameters: Optional[List[str]] = None,
        figsize: Tuple[int, int] = (12, 8),
        n_cols: int = 2, 
        y_as_pct_change: bool = False,
        plot_performance: bool = True,
        normalize_params: bool = False,
    ) -> plt.Figure:
        """
        Plot parameter evolution across folds.
        
        Parameters:
        -----------
        parameters : Optional[List[str]]
            List of parameters to plot (if None, plot all or top unstable)
        figsize : Tuple[int, int]
            Figure size
        n_cols : int
            Number of columns in the plot grid
        y_as_pct_change : bool
            Whether to plot percent change rather than absolute values
        plot_performance : bool
            Whether to include performance metrics in the plots
        normalize_params : bool
            Whether to normalize parameters to a 0-1 range
            
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        if self.parameters_df is None:
            self.create_parameters_dataframe()
        
        if self.parameters_df is None or self.parameters_df.empty:
            logger.warning("No parameter data to plot")
            return None
        
        # If no parameters specified, use all or top unstable
        if parameters is None:
            if self.stability_metrics is not None and not self.stability_metrics.empty:
                # Use the most unstable parameters
                unstable = self.get_unstable_parameters()
                if not unstable.empty:
                    parameters = unstable['parameter'].tolist()[:10]  # Top 10 unstable
                else:
                    # Use the top 10 parameters by coefficient of variation
                    parameters = self.stability_metrics.sort_values('cv', ascending=False)['parameter'].tolist()[:10]
            else:
                # Use all parameters except fold_id and fold_date
                parameters = [col for col in self.parameters_df.columns 
                             if col not in ['fold_id', 'fold_date']]
                
                # Exclude performance metrics
                if self.performance_history:
                    perf_metrics = set(self.performance_history[0].keys()) - {'fold_id', 'fold_date'}
                    parameters = [p for p in parameters if p not in perf_metrics]
        
        if not parameters:
            logger.warning("No parameters to plot")
            return None
        
        # Determine performance metric to plot (if any)
        performance_metric = None
        if plot_performance and self.performance_history:
            # Find a good performance metric (prefer these in order)
            preferred_metrics = ['sharpe', 'r2', 'accuracy', 'f1', 'precision', 'recall', 'mse', 'rmse']
            available_metrics = set(self.performance_history[0].keys()) - {'fold_id', 'fold_date'}
            
            for metric in preferred_metrics:
                if metric in available_metrics:
                    performance_metric = metric
                    break
            
            if performance_metric is None and available_metrics:
                # Just use the first available metric
                performance_metric = list(available_metrics)[0]
        
        # Calculate number of rows needed
        n_params = len(parameters)
        if performance_metric is not None:
            n_params += 1  # Add one for performance plot
        
        n_rows = (n_params + n_cols - 1) // n_cols
        
        # Create figure and axes
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        
        # Flatten axes if needed
        if n_rows == 1 and n_cols == 1:
            axes = np.array([axes])
        elif n_rows == 1 or n_cols == 1:
            axes = axes.flatten()
        
        # Plot each parameter
        for i, param_name in enumerate(parameters):
            if i >= len(axes.flat):
                break
                
            ax = axes.flat[i]
            
            if param_name in self.parameters_df.columns:
                df = self.parameters_df.copy()
                
                # Prepare data
                if y_as_pct_change:
                    # Calculate percent change
                    values = df[param_name].pct_change() * 100
                    ylabel = f"{param_name} (% change)"
                elif normalize_params:
                    # Normalize to 0-1 range
                    values = df[param_name]
                    min_val = values.min()
                    max_val = values.max()
                    if min_val != max_val:
                        values = (values - min_val) / (max_val - min_val)
                    ylabel = f"{param_name} (normalized)"
                else:
                    values = df[param_name]
                    ylabel = param_name
                
                # Use dates for x-axis if available, otherwise fold_id
                if 'fold_date' in df.columns:
                    x_values = df['fold_date']
                    xlabel = 'Date'
                else:
                    x_values = df['fold_id']
                    xlabel = 'Fold'
                
                # Plot parameter evolution
                ax.plot(x_values, values, marker='o', linestyle='-')
                
                # Add stability info if available
                if self.stability_metrics is not None and not self.stability_metrics.empty:
                    param_metrics = self.stability_metrics[self.stability_metrics['parameter'] == param_name]
                    if not param_metrics.empty:
                        stability = param_metrics.iloc[0]['stability']
                        cv = param_metrics.iloc[0]['cv']
                        title = f"{param_name} (CV: {cv:.3f}, {stability})"
                    else:
                        title = param_name
                else:
                    title = param_name
                
                ax.set_title(title)
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.grid(True, alpha=0.3)
                
                # Rotate x-axis labels if they're dates
                if 'fold_date' in df.columns:
                    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
            else:
                ax.text(0.5, 0.5, f"{param_name} not found", 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes)
        
        # Plot performance metric if requested
        if performance_metric is not None and performance_metric in self.parameters_df.columns:
            if i + 1 < len(axes.flat):
                ax = axes.flat[i + 1]
                
                # Use dates for x-axis if available, otherwise fold_id
                if 'fold_date' in self.parameters_df.columns:
                    x_values = self.parameters_df['fold_date']
                    xlabel = 'Date'
                else:
                    x_values = self.parameters_df['fold_id']
                    xlabel = 'Fold'
                
                # Plot performance
                ax.plot(x_values, self.parameters_df[performance_metric], 
                       marker='o', linestyle='-', color='green')
                
                ax.set_title(f"{performance_metric.capitalize()}")
                ax.set_xlabel(xlabel)
                ax.set_ylabel(performance_metric)
                ax.grid(True, alpha=0.3)
                
                # Rotate x-axis labels if they're dates
                if 'fold_date' in self.parameters_df.columns:
                    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        
        # Hide any unused axes
        for j in range(i + 1 + (1 if performance_metric is not None else 0), len(axes.flat)):
            axes.flat[j].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def plot_stability_metrics(self) -> plt.Figure:
        """
        Plot stability metrics for all parameters.
        
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        if self.stability_metrics is None:
            self.compute_stability_metrics()
        
        if self.stability_metrics is None or self.stability_metrics.empty:
            logger.warning("No stability metrics to plot")
            return None
            
        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot 1: Parameter Stability (CV)
        stability_df = self.stability_metrics.sort_values('cv', ascending=False).head(15)
        ax1.barh(stability_df['parameter'], stability_df['cv'])
        
        # Add reference line at threshold
        ax1.axvline(x=self.stability_threshold, color='r', linestyle='--', 
                   label=f'Threshold ({self.stability_threshold})')
        
        ax1.set_title('Parameter Stability (Coefficient of Variation)')
        ax1.set_xlabel('Coefficient of Variation (lower is better)')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Plot 2: Parameter Trend Significance
        if 'trend_p_value' in self.stability_metrics.columns:
            # Use -log10(p-value) for better visualization (higher = more significant)
            trend_df = self.stability_metrics.copy()
            trend_df['neg_log_p'] = -np.log10(trend_df['trend_p_value'].replace(0, 1e-10))
            trend_df = trend_df.sort_values('neg_log_p', ascending=False).head(15)
            
            ax2.barh(trend_df['parameter'], trend_df['neg_log_p'])
            
            # Add reference line at p=0.05 significance
            ax2.axvline(x=-np.log10(0.05), color='r', linestyle='--', 
                       label='p=0.05 significance')
            
            ax2.set_title('Parameter Trend Significance')
            ax2.set_xlabel('-log10(p-value) (higher = more significant trend)')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
        else:
            ax2.text(0.5, 0.5, 'Trend significance not available', 
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax2.transAxes)
        
        plt.tight_layout()
        return fig
    
    def plot_parameter_correlations(self, include_performance: bool = True) -> plt.Figure:
        """
        Plot correlations between parameters and with performance.
        
        Parameters:
        -----------
        include_performance : bool
            Whether to include performance metrics in the correlation matrix
            
        Returns:
        --------
        plt.Figure
            Matplotlib figure object
        """
        if self.parameters_df is None:
            self.create_parameters_dataframe()
        
        if self.parameters_df is None or self.parameters_df.empty:
            logger.warning("No parameter data to plot correlations")
            return None
            
        # Prepare data
        df = self.parameters_df.copy()
        
        # Exclude non-numeric columns
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
        df = df[numeric_cols]
        
        # Exclude fold_id by default
        if 'fold_id' in df.columns:
            df = df.drop('fold_id', axis=1)
        
        # Exclude performance metrics if requested
        if not include_performance and self.performance_history:
            perf_metrics = set(k for perf in self.performance_history for k in perf.keys()) - {'fold_id', 'fold_date'}
            perf_metrics = [m for m in perf_metrics if m in df.columns]
            if perf_metrics:
                df = df.drop(perf_metrics, axis=1)
        
        # Calculate correlation matrix
        corr_matrix = df.corr()
        
        # Create figure
        plt.figure(figsize=(12, 10))
        
        # Generate mask for the upper triangle
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
        
        # Generate custom diverging colormap
        cmap = sns.diverging_palette(230, 20, as_cmap=True)
        
        # Draw the heatmap
        sns.heatmap(
            corr_matrix, 
            mask=mask,
            annot=True, 
            fmt=".2f",
            cmap=cmap,
            vmax=1.0,
            vmin=-1.0,
            center=0,
            square=True, 
            linewidths=.5, 
            cbar_kws={"shrink": .5}
        )
        
        plt.title('Parameter Correlations')
        plt.tight_layout()
        
        return plt.gcf()
    
    def generate_stability_report(self) -> pd.DataFrame:
        """
        Generate a comprehensive stability report with recommendations.
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with parameters, stability metrics, and recommendations
        """
        if self.stability_metrics is None:
            self.compute_stability_metrics()
        
        if self.stability_metrics is None or self.stability_metrics.empty:
            logger.warning("No stability metrics for report")
            return pd.DataFrame()
        
        # Start with stability metrics
        report_df = self.stability_metrics.copy()
        
        # Add recommendations based on stability
        def get_recommendation(row):
            if row['stability'] == 'Very Stable':
                return "Parameter is very stable. No action needed."
            elif row['stability'] == 'Stable':
                return "Parameter is sufficiently stable. Monitor for changes."
            elif row['stability'] == 'Moderately Unstable':
                # Check if there's a significant trend
                if row['trend_p_value'] < 0.05:
                    if row['trend_slope'] > 0:
                        return "Parameter is increasing significantly. Consider increasing constraints or smoothing."
                    else:
                        return "Parameter is decreasing significantly. Consider increasing constraints or smoothing."
                else:
                    return "Parameter shows moderate instability without clear trend. Consider regularization or constraints."
            else:  # Unstable
                if row['trend_p_value'] < 0.05:
                    if row['trend_slope'] > 0:
                        return "Parameter is highly unstable with significant upward trend. Strongly recommend fixing or constraining."
                    else:
                        return "Parameter is highly unstable with significant downward trend. Strongly recommend fixing or constraining."
                else:
                    return "Parameter is highly unstable without clear trend. Strongly recommend fixing, constraining, or removing."
        
        report_df['recommendation'] = report_df.apply(get_recommendation, axis=1)
        
        # Add priority field based on stability and significance of trend
        def get_priority(row):
            if row['stability'] == 'Very Stable':
                return 'Low'
            elif row['stability'] == 'Stable':
                return 'Low'
            elif row['stability'] == 'Moderately Unstable':
                if row['trend_p_value'] < 0.05:
                    return 'Medium'
                else:
                    return 'Medium-Low'
            else:  # Unstable
                if row['trend_p_value'] < 0.05:
                    return 'High'
                else:
                    return 'Medium-High'
        
        report_df['priority'] = report_df.apply(get_priority, axis=1)
        
        # Order by priority and coefficient of variation
        priority_order = {'High': 0, 'Medium-High': 1, 'Medium': 2, 'Medium-Low': 3, 'Low': 4}
        report_df['priority_order'] = report_df['priority'].map(priority_order)
        
        report_df = report_df.sort_values(['priority_order', 'cv'], ascending=[True, False])
        report_df = report_df.drop('priority_order', axis=1)
        
        return report_df
    
    def recommend_parameter_constraints(self) -> Dict[str, Dict[str, float]]:
        """
        Recommend constraints for unstable parameters.
        
        Returns:
        --------
        Dict[str, Dict[str, float]]
            Dictionary with recommended constraints for each unstable parameter
        """
        if self.stability_metrics is None:
            self.compute_stability_metrics()
        
        if self.stability_metrics is None or self.stability_metrics.empty:
            logger.warning("No stability metrics for recommendations")
            return {}
        
        # Get unstable parameters
        unstable = self.get_unstable_parameters()
        
        if unstable.empty:
            return {}
        
        recommendations = {}
        
        for _, row in unstable.iterrows():
            param_name = row['parameter']
            
            # Get parameter values
            if param_name in self.parameter_history:
                values = self.parameter_history[param_name]
                
                # Calculate recommendation based on parameter distribution
                median = np.median(values)
                p25 = np.percentile(values, 25)
                p75 = np.percentile(values, 75)
                iqr = p75 - p25
                
                # Recommend constraints based on interquartile range
                recommendations[param_name] = {
                    'suggested_min': max(median - 1.5 * iqr, min(values)),
                    'suggested_max': min(median + 1.5 * iqr, max(values)),
                    'mean': np.mean(values),
                    'median': median,
                    'stability': row['stability'],
                    'cv': row['cv']
                } 