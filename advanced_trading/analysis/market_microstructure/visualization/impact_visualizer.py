"""
Impact Visualizer Module

This module provides tools for visualizing market impact models and data, including:
- Market impact curves
- Implementation shortfall analysis
- Price impact visualization
- Cost curves for various execution strategies
- Model comparison and evaluation
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import seaborn as sns
from typing import Dict, List, Optional, Union, Tuple, Any, Callable
import logging
from datetime import datetime, timedelta

# Setup logging
logger = logging.getLogger(__name__)

class ImpactVisualizer:
    """
    Visualization tools for market impact models and transaction cost analysis.
    
    This class provides various methods to visualize market impact curves,
    implementation shortfall, and execution costs.
    """
    
    def __init__(self, figsize: Tuple[int, int] = (12, 8), style: str = 'seaborn-darkgrid'):
        """
        Initialize the ImpactVisualizer.
        
        Args:
            figsize: Default figure size for plots (width, height)
            style: Matplotlib style to use for plots
        """
        self.figsize = figsize
        self.style = style
        self.colors = {
            'permanent': 'darkblue',
            'temporary': 'lightblue',
            'total': 'purple',
            'actual': 'green',
            'predicted': 'red',
            'theoretical': 'orange',
            'baseline': 'grey',
        }
        plt.style.use(style)
    
    def plot_impact_curve(self, sizes: np.ndarray, impacts: np.ndarray,
                        model_name: str = 'Impact Model',
                        fit_curve: bool = True,
                        model_formula: Optional[str] = None,
                        theoretical_curve: Optional[Callable[[np.ndarray], np.ndarray]] = None,
                        figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot market impact as a function of order size with optional model fitting.
        
        Args:
            sizes: Array of order sizes
            impacts: Array of corresponding market impacts
            model_name: Name of the impact model for the title
            fit_curve: If True, fit a curve to the data
            model_formula: Optional formula to display on plot (e.g., "Impact = 0.1 * sqrt(Size/ADV)")
            theoretical_curve: Optional function to plot a theoretical impact curve
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Plot observed impact
            ax.scatter(sizes, impacts, color=self.colors['actual'], alpha=0.7, 
                      label='Observed Impact')
            
            # Fit curve if requested
            if fit_curve and len(sizes) > 2:
                try:
                    # Try to fit a power law curve: impact = a * size^b
                    from scipy.optimize import curve_fit
                    
                    def power_law(x, a, b):
                        return a * np.power(x, b)
                    
                    popt, pcov = curve_fit(power_law, sizes, impacts)
                    a, b = popt
                    
                    # Generate fitted curve
                    x_fit = np.linspace(min(sizes), max(sizes), 100)
                    y_fit = power_law(x_fit, a, b)
                    
                    # Plot fitted curve
                    ax.plot(x_fit, y_fit, color=self.colors['predicted'], linewidth=2, 
                           label=f'Fitted: a*size^b (a={a:.4f}, b={b:.4f})')
                    
                    # Update model formula if not provided
                    if model_formula is None:
                        model_formula = f"Impact = {a:.4f} * Size^{b:.4f}"
                except Exception as fit_error:
                    logger.warning(f"Error fitting curve: {str(fit_error)}")
            
            # Plot theoretical curve if provided
            if theoretical_curve is not None:
                x_theory = np.linspace(min(sizes), max(sizes), 100)
                try:
                    y_theory = theoretical_curve(x_theory)
                    ax.plot(x_theory, y_theory, color=self.colors['theoretical'], 
                           linestyle='--', linewidth=2, label='Theoretical Model')
                except Exception as theory_error:
                    logger.warning(f"Error plotting theoretical curve: {str(theory_error)}")
            
            # Set labels and title
            ax.set_xlabel('Order Size')
            ax.set_ylabel('Price Impact')
            ax.set_title(f'Market Impact Curve - {model_name}')
            
            # Add grid and legend
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Add model formula if provided
            if model_formula:
                ax.text(0.05, 0.95, model_formula, transform=ax.transAxes, 
                       fontsize=10, va='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting impact curve: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting impact curve: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_permanent_temporary_impact(self, sizes: np.ndarray, 
                                      permanent_impacts: np.ndarray,
                                      temporary_impacts: np.ndarray,
                                      model_name: str = 'Impact Model',
                                      figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot permanent and temporary impact components.
        
        Args:
            sizes: Array of order sizes
            permanent_impacts: Array of permanent market impacts
            temporary_impacts: Array of temporary market impacts
            model_name: Name of the impact model for the title
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Calculate total impact
            total_impacts = permanent_impacts + temporary_impacts
            
            # Plot impacts
            ax.plot(sizes, permanent_impacts, color=self.colors['permanent'], 
                   linewidth=2, label='Permanent Impact')
            ax.plot(sizes, temporary_impacts, color=self.colors['temporary'], 
                   linewidth=2, label='Temporary Impact')
            ax.plot(sizes, total_impacts, color=self.colors['total'], 
                   linewidth=2, label='Total Impact')
            
            # Add shadow to show the temporary component clearly
            ax.fill_between(sizes, permanent_impacts, total_impacts, 
                          color=self.colors['temporary'], alpha=0.3)
            
            # Set labels and title
            ax.set_xlabel('Order Size')
            ax.set_ylabel('Price Impact')
            ax.set_title(f'Permanent vs. Temporary Impact - {model_name}')
            
            # Add grid and legend
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Calculate and display component statistics
            perm_ratio = np.mean(permanent_impacts / total_impacts) if np.sum(total_impacts) > 0 else 0
            temp_ratio = 1 - perm_ratio
            
            stats_text = (
                f"Permanent Impact Ratio: {perm_ratio:.2%}  |  "
                f"Temporary Impact Ratio: {temp_ratio:.2%}"
            )
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting permanent/temporary impact: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting impact components: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_implementation_shortfall(self, execution_data: pd.DataFrame,
                                    time_col: str = 'time',
                                    price_col: str = 'price',
                                    benchmark_price_col: str = 'benchmark_price',
                                    size_col: str = 'size',
                                    side_col: Optional[str] = 'side',
                                    figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot implementation shortfall analysis (difference between execution price and benchmark).
        
        Args:
            execution_data: DataFrame with execution data
            time_col: Column name for execution time
            price_col: Column name for execution price
            benchmark_price_col: Column name for benchmark price
            size_col: Column name for execution size
            side_col: Column name for execution side ('buy' or 'sell')
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            required_cols = [time_col, price_col, benchmark_price_col, size_col]
            for col in required_cols:
                if col not in execution_data.columns:
                    raise ValueError(f"Required column '{col}' not found in data")
            
            # Make a copy of the data
            data = execution_data.copy()
            
            # Ensure time column is datetime
            if not pd.api.types.is_datetime64_any_dtype(data[time_col]):
                data[time_col] = pd.to_datetime(data[time_col])
            
            # Sort by time
            data = data.sort_values(by=time_col)
            
            # Calculate shortfall for each execution
            if side_col in data.columns:
                # Adjust formula based on side (buy: price - benchmark, sell: benchmark - price)
                data['shortfall'] = np.where(
                    data[side_col].str.lower() == 'buy',
                    data[price_col] - data[benchmark_price_col],
                    data[benchmark_price_col] - data[price_col]
                )
            else:
                # Default to treating all as buys
                data['shortfall'] = data[price_col] - data[benchmark_price_col]
            
            # Calculate shortfall in basis points
            data['shortfall_bps'] = 10000 * data['shortfall'] / data[benchmark_price_col]
            
            # Calculate cumulative statistics
            data['size_pct'] = data[size_col] / data[size_col].sum()
            data['weighted_shortfall'] = data['shortfall'] * data['size_pct']
            data['cumulative_size'] = data[size_col].cumsum() / data[size_col].sum()
            data['cumulative_shortfall'] = (data['weighted_shortfall'].cumsum() / 
                                          data['size_pct'].cumsum())
            
            # Create figure with two subplots
            fig, axes = plt.subplots(2, 1, figsize=figsize or (12, 10), sharex=True)
            
            # Plot price and benchmark
            ax_price = axes[0]
            ax_price.plot(data[time_col], data[price_col], color=self.colors['actual'], 
                         marker='o', linestyle='-', label='Execution Price')
            ax_price.plot(data[time_col], data[benchmark_price_col], color=self.colors['baseline'], 
                         linestyle='--', label='Benchmark Price')
            
            # Highlight the shortfall (use different color based on sign)
            for i, row in data.iterrows():
                color = 'red' if row['shortfall'] > 0 else 'green'
                ax_price.plot([row[time_col], row[time_col]], 
                             [row[benchmark_price_col], row[price_col]],
                             color=color, alpha=0.5, linewidth=1.5)
            
            # Set labels and title for price plot
            ax_price.set_ylabel('Price')
            ax_price.set_title('Implementation Shortfall Analysis')
            ax_price.legend()
            ax_price.grid(True, alpha=0.3)
            
            # Plot shortfall in basis points
            ax_shortfall = axes[1]
            
            # Bar plot for individual shortfalls
            bar_colors = ['red' if x > 0 else 'green' for x in data['shortfall_bps']]
            ax_shortfall.bar(data[time_col], data['shortfall_bps'], color=bar_colors, 
                           alpha=0.7, label='Shortfall (bps)')
            
            # Set labels for shortfall plot
            ax_shortfall.set_xlabel('Time')
            ax_shortfall.set_ylabel('Shortfall (basis points)')
            ax_shortfall.axhline(y=0, color='gray', linestyle='-', linewidth=1)
            ax_shortfall.grid(True, alpha=0.3)
            
            # Add cumulative shortfall line on secondary y-axis
            ax2 = ax_shortfall.twinx()
            ax2.plot(data[time_col], data['cumulative_shortfall'] * 10000, 
                    color=self.colors['total'], linewidth=2, label='Cumulative Shortfall (bps)')
            ax2.set_ylabel('Cumulative Shortfall (basis points)')
            
            # Add second legend for cumulative line
            lines, labels = ax_shortfall.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax2.legend(lines + lines2, labels + labels2, loc='best')
            
            # Format x-axis
            plt.gcf().autofmt_xdate()
            
            # Calculate and display shortfall statistics
            total_shortfall = data['weighted_shortfall'].sum()
            total_shortfall_bps = 10000 * total_shortfall / data[benchmark_price_col].mean()
            shortfall_std = data['shortfall_bps'].std()
            max_shortfall = data['shortfall_bps'].max()
            min_shortfall = data['shortfall_bps'].min()
            
            stats_text = (
                f"Total Shortfall: {total_shortfall_bps:.2f} bps  |  "
                f"Std Dev: {shortfall_std:.2f} bps  |  "
                f"Max: {max_shortfall:.2f} bps  |  "
                f"Min: {min_shortfall:.2f} bps"
            )
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, axes
            
        except Exception as e:
            logger.error(f"Error plotting implementation shortfall: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting implementation shortfall: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_model_comparison(self, sizes: np.ndarray, 
                            model_results: Dict[str, np.ndarray],
                            actual_impacts: Optional[np.ndarray] = None,
                            reference_model: Optional[str] = None,
                            figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Compare multiple impact models against each other and optionally against actual impact.
        
        Args:
            sizes: Array of order sizes
            model_results: Dictionary mapping model names to their impact predictions
            actual_impacts: Optional array of actual observed impacts
            reference_model: Optional name of a reference model to use for comparison
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if not model_results:
                raise ValueError("No models provided for comparison")
            
            # Create figure with two subplots (absolute and relative comparison)
            fig, axes = plt.subplots(2, 1, figsize=figsize or (12, 10), sharex=True)
            
            # Plot absolute comparison
            ax_abs = axes[0]
            
            # Generate color cycle
            color_cycle = plt.cm.tab10(np.linspace(0, 1, len(model_results)))
            
            # Plot each model
            for i, (model_name, impacts) in enumerate(model_results.items()):
                ax_abs.plot(sizes, impacts, color=color_cycle[i], linewidth=2, label=model_name)
            
            # Plot actual impacts if provided
            if actual_impacts is not None:
                ax_abs.scatter(sizes, actual_impacts, color='black', alpha=0.7, 
                              label='Actual Impact')
            
            # Set labels and title for absolute comparison
            ax_abs.set_ylabel('Price Impact')
            ax_abs.set_title('Impact Model Comparison (Absolute)')
            ax_abs.legend()
            ax_abs.grid(True, alpha=0.3)
            
            # Plot relative comparison
            ax_rel = axes[1]
            
            # Determine reference for relative comparison
            if reference_model is not None and reference_model in model_results:
                reference_impacts = model_results[reference_model]
                reference_label = reference_model
            elif actual_impacts is not None:
                reference_impacts = actual_impacts
                reference_label = 'Actual Impact'
            else:
                # Use the first model as reference
                reference_model = list(model_results.keys())[0]
                reference_impacts = model_results[reference_model]
                reference_label = reference_model
            
            # Plot relative differences
            for i, (model_name, impacts) in enumerate(model_results.items()):
                if model_name != reference_model:
                    # Calculate relative difference in percentage
                    rel_diff = 100 * (impacts - reference_impacts) / np.maximum(1e-10, reference_impacts)
                    ax_rel.plot(sizes, rel_diff, color=color_cycle[i], linewidth=2, 
                               label=f'{model_name} vs {reference_label}')
            
            # Add zero line
            ax_rel.axhline(y=0, color='gray', linestyle='-', linewidth=1)
            
            # Set labels for relative comparison
            ax_rel.set_xlabel('Order Size')
            ax_rel.set_ylabel('Relative Difference (%)')
            ax_rel.set_title('Impact Model Comparison (Relative to Reference)')
            ax_rel.legend()
            ax_rel.grid(True, alpha=0.3)
            
            # Calculate and display model statistics
            if len(model_results) > 1:
                # Calculate mean absolute differences between models
                model_names = list(model_results.keys())
                diff_text = "Mean Absolute Differences: "
                
                for i in range(len(model_names)):
                    for j in range(i+1, len(model_names)):
                        model1 = model_names[i]
                        model2 = model_names[j]
                        diff = np.mean(np.abs(model_results[model1] - model_results[model2]))
                        diff_text += f"{model1} vs {model2}: {diff:.4f}  "
                
                plt.figtext(0.5, 0.01, diff_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, axes
            
        except Exception as e:
            logger.error(f"Error plotting model comparison: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting model comparison: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_execution_cost_profile(self, times: np.ndarray,
                                  immediacy_costs: np.ndarray,
                                  timing_risks: np.ndarray,
                                  opportunity_costs: Optional[np.ndarray] = None,
                                  strategy_name: str = 'Execution Strategy',
                                  figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot execution cost profile showing trade-offs between immediacy costs and timing risk.
        
        Args:
            times: Array of execution times (e.g., seconds, minutes, hours)
            immediacy_costs: Array of immediacy costs at each time point
            timing_risks: Array of timing risks at each time point
            opportunity_costs: Optional array of opportunity costs at each time point
            strategy_name: Name of the execution strategy for the title
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Calculate total costs (if opportunity costs provided)
            if opportunity_costs is not None:
                total_costs = immediacy_costs + timing_risks + opportunity_costs
            else:
                total_costs = immediacy_costs + timing_risks
            
            # Plot costs
            ax.plot(times, immediacy_costs, color='blue', linewidth=2, label='Immediacy Cost')
            ax.plot(times, timing_risks, color='red', linewidth=2, label='Timing Risk')
            
            if opportunity_costs is not None:
                ax.plot(times, opportunity_costs, color='green', linewidth=2, 
                       label='Opportunity Cost')
            
            ax.plot(times, total_costs, color='purple', linewidth=3, label='Total Cost')
            
            # Find the optimal execution time (minimum total cost)
            optimal_idx = np.argmin(total_costs)
            optimal_time = times[optimal_idx]
            optimal_cost = total_costs[optimal_idx]
            
            # Mark the optimal point
            ax.scatter([optimal_time], [optimal_cost], color='black', s=100, 
                      marker='*', label=f'Optimal ({optimal_time:.2f})')
            
            # Set labels and title
            ax.set_xlabel('Execution Time')
            ax.set_ylabel('Execution Cost')
            ax.set_title(f'Execution Cost Profile - {strategy_name}')
            
            # Add grid and legend
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Calculate and display cost statistics
            min_immediacy = np.min(immediacy_costs)
            min_timing = np.min(timing_risks)
            
            stats_text = (
                f"Optimal Execution Time: {optimal_time:.2f}  |  "
                f"Minimum Immediacy Cost: {min_immediacy:.4f}  |  "
                f"Minimum Timing Risk: {min_timing:.4f}"
            )
            
            if opportunity_costs is not None:
                min_opportunity = np.min(opportunity_costs)
                stats_text += f"  |  Minimum Opportunity Cost: {min_opportunity:.4f}"
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting execution cost profile: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting execution cost profile: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax 