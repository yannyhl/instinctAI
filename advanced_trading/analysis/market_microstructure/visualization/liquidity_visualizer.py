"""
Liquidity Visualizer Module

This module provides tools for visualizing market liquidity data, including:
- Bid-ask spread visualization
- Market depth visualization
- Liquidity metrics visualization
- Liquidity heat maps and profiles
- Visualization of liquidity consumption and resilience
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import matplotlib.cm as cm
from matplotlib.colors import Normalize
import seaborn as sns
from typing import Dict, List, Optional, Union, Tuple, Any, Callable
import logging
from datetime import datetime, timedelta
from IPython.display import HTML, display

# Setup logging
logger = logging.getLogger(__name__)

class LiquidityVisualizer:
    """
    Visualization tools for market liquidity data and metrics.
    
    This class provides various methods to visualize bid-ask spreads, market depth,
    liquidity metrics, and liquidity consumption and resilience over time.
    """
    
    def __init__(self, figsize: Tuple[int, int] = (12, 6), style: str = 'seaborn-darkgrid'):
        """
        Initialize the LiquidityVisualizer.
        
        Args:
            figsize: Default figure size for plots (width, height)
            style: Matplotlib style to use for plots
        """
        self.figsize = figsize
        self.style = style
        self.colors = {
            'spread': 'purple',
            'depth': 'teal',
            'volume': 'blue',
            'volatility': 'orange',
            'liquidity_score': 'green',
            'trading_cost': 'red'
        }
        
        plt.style.use(style)
    
    def plot_spread_analysis(self, data: pd.DataFrame,
                            spread_col: str = 'spread',
                            price_col: Optional[str] = 'mid_price',
                            volume_col: Optional[str] = 'volume',
                            relative_spread: bool = True,
                            moving_average: Optional[int] = None,
                            figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot spread analysis with optional price and volume.
        
        Args:
            data: DataFrame with spread and other market data
            spread_col: Column name for spread values
            price_col: Column name for price (if None, price not plotted)
            volume_col: Column name for volume (if None, volume not plotted)
            relative_spread: If True, show spread as percentage of mid price
            moving_average: If provided, show moving average of spread with this window size
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if spread_col not in data.columns:
                raise ValueError(f"Spread column '{spread_col}' not found in data")
            
            # Prepare data for plotting
            spreads = data[spread_col].copy()
            
            # Calculate relative spread if requested
            if relative_spread and price_col in data.columns:
                spreads = 100 * spreads / data[price_col]  # Convert to percentage
            
            # Calculate moving average if requested
            if moving_average is not None:
                spreads_ma = spreads.rolling(window=moving_average).mean()
            
            # Determine the number of subplots
            show_price = price_col is not None and price_col in data.columns
            show_volume = volume_col is not None and volume_col in data.columns
            n_plots = 1 + show_price + show_volume
            
            # Create figure with appropriate number of subplots
            fig, axes = plt.subplots(n_plots, 1, figsize=figsize or self.figsize, 
                                    sharex=True, gridspec_kw={'height_ratios': [3] + [1] * (n_plots - 1)})
            
            # Convert to list if only one subplot
            if n_plots == 1:
                axes = [axes]
            
            # Plot spread
            ax_spread = axes[0]
            ax_spread.plot(data.index, spreads, label='Spread', color=self.colors['spread'], 
                          linewidth=1, alpha=0.8)
            
            # Plot moving average if requested
            if moving_average is not None:
                ax_spread.plot(data.index, spreads_ma, 
                              label=f'{moving_average}-period MA', 
                              color=self.colors['spread'], linewidth=2)
            
            # Set labels and title
            spread_label = 'Relative Spread (%)' if relative_spread else 'Spread'
            ax_spread.set_ylabel(spread_label)
            ax_spread.set_title('Bid-Ask Spread Analysis')
            ax_spread.legend()
            
            # Add grid and formatting
            ax_spread.grid(True, alpha=0.3)
            
            # Plot price if requested
            plot_idx = 1
            if show_price:
                ax_price = axes[plot_idx]
                ax_price.plot(data.index, data[price_col], color=self.colors['volume'], 
                             linewidth=1, label='Price')
                ax_price.set_ylabel('Price')
                ax_price.legend()
                ax_price.grid(True, alpha=0.3)
                plot_idx += 1
            
            # Plot volume if requested
            if show_volume:
                ax_volume = axes[plot_idx]
                ax_volume.bar(data.index, data[volume_col], color=self.colors['depth'], 
                             alpha=0.7, label='Volume')
                ax_volume.set_ylabel('Volume')
                ax_volume.legend()
                ax_volume.grid(True, alpha=0.3)
            
            # Format x-axis
            if isinstance(data.index, pd.DatetimeIndex):
                plt.gcf().autofmt_xdate()
            
            # Calculate spread statistics
            spread_stats = {
                'mean': spreads.mean(),
                'median': spreads.median(),
                'min': spreads.min(),
                'max': spreads.max(),
                'std_dev': spreads.std()
            }
            
            # Add statistics to the plot
            stats_text = (
                f"Mean: {spread_stats['mean']:.6f}  "
                f"Median: {spread_stats['median']:.6f}  "
                f"Min: {spread_stats['min']:.6f}  "
                f"Max: {spread_stats['max']:.6f}  "
                f"Std Dev: {spread_stats['std_dev']:.6f}"
            )
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, axes
            
        except Exception as e:
            logger.error(f"Error plotting spread analysis: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting spread analysis: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_liquidity_profile(self, data: pd.DataFrame,
                              time_window: Optional[pd.Timedelta] = None,
                              depth_levels: List[float] = [0.1, 0.5, 1.0, 2.0, 5.0],
                              figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot a liquidity profile showing depth at different price levels.
        
        Args:
            data: DataFrame with index as timestamps and columns for each price level
                column names should be the percentage distance from mid price
            time_window: If provided, only plot data from the last time_window
            depth_levels: List of price levels to visualize (percentage from mid)
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Filter data by time window if requested
            if time_window is not None and isinstance(data.index, pd.DatetimeIndex):
                start_time = data.index[-1] - time_window
                data = data[data.index >= start_time]
            
            # Extract columns for the requested depth levels
            depth_columns = []
            for level in depth_levels:
                level_str = f"{level:.1f}%"
                if level_str in data.columns:
                    depth_columns.append(level_str)
                else:
                    logger.warning(f"Depth level {level_str} not found in data")
            
            if not depth_columns:
                raise ValueError("No valid depth levels found in data")
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Plot each depth level
            for col in depth_columns:
                ax.plot(data.index, data[col], label=f"Depth at {col}")
            
            # Set labels and title
            ax.set_xlabel('Time')
            ax.set_ylabel('Liquidity Depth')
            ax.set_title('Market Liquidity Profile Over Time')
            ax.legend()
            
            # Format x-axis
            if isinstance(data.index, pd.DatetimeIndex):
                plt.gcf().autofmt_xdate()
            
            # Add grid
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting liquidity profile: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting liquidity profile: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_liquidity_heatmap(self, data: pd.DataFrame,
                              price_levels: int = 20,
                              normalize: bool = True,
                              cmap: str = 'viridis',
                              figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot a heatmap of liquidity at different price levels over time.
        
        Args:
            data: DataFrame where rows are timestamps and columns are price levels
            price_levels: Number of price levels to show on each side
            normalize: If True, normalize liquidity values for better visualization
            cmap: Colormap to use for the heatmap
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Select the price levels to include
            mid_col = len(data.columns) // 2
            start_col = max(0, mid_col - price_levels // 2)
            end_col = min(len(data.columns), mid_col + price_levels // 2)
            
            plot_data = data.iloc[:, start_col:end_col].copy()
            
            # Normalize data if requested
            if normalize:
                # Normalize each row (timestamp) independently
                plot_data = plot_data.div(plot_data.max(axis=1), axis=0)
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or (12, 8))
            
            # Plot heatmap
            sns.heatmap(plot_data, cmap=cmap, ax=ax, 
                       cbar_kws={'label': 'Normalized Liquidity' if normalize else 'Liquidity'})
            
            # Set labels and title
            ax.set_xlabel('Price Level (Distance from Mid Price)')
            ax.set_ylabel('Time')
            ax.set_title('Liquidity Heatmap')
            
            # Format y-axis for datetime index
            if isinstance(data.index, pd.DatetimeIndex):
                tick_count = min(10, len(data))
                tick_positions = np.linspace(0, len(data) - 1, tick_count).astype(int)
                ax.set_yticks(tick_positions)
                ax.set_yticklabels([data.index[i].strftime('%Y-%m-%d %H:%M:%S') for i in tick_positions])
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting liquidity heatmap: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting liquidity heatmap: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_market_impact(self, sizes: np.ndarray, impacts: np.ndarray,
                          market_name: str = 'Market',
                          side: str = 'buy',
                          fit_curve: bool = True,
                          model_formula: Optional[str] = None,
                          figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot market impact as a function of order size.
        
        Args:
            sizes: Array of order sizes
            impacts: Array of corresponding market impacts
            market_name: Name of the market for the title
            side: Order side ('buy' or 'sell')
            fit_curve: If True, fit a curve to the data
            model_formula: Optional formula to display on plot (e.g., "Impact = 0.1 * sqrt(Size/ADV)")
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Determine color based on side
            color = 'green' if side.lower() == 'buy' else 'red'
            
            # Plot impact curve
            ax.scatter(sizes, impacts, color=color, alpha=0.7, label='Observed Impact')
            
            # Fit curve if requested
            if fit_curve and len(sizes) > 2:
                try:
                    # Try to fit a power law curve: impact = a * size^b
                    from scipy.optimize import curve_fit
                    
                    def power_law(x, a, b):
                        return a * np.power(x, b)
                    
                    popt, _ = curve_fit(power_law, sizes, impacts)
                    a, b = popt
                    
                    # Generate fitted curve
                    x_fit = np.linspace(min(sizes), max(sizes), 100)
                    y_fit = power_law(x_fit, a, b)
                    
                    # Plot fitted curve
                    ax.plot(x_fit, y_fit, color='blue', linewidth=2, 
                           label=f'Fitted: a*size^b (a={a:.5f}, b={b:.5f})')
                    
                    # Update model formula if not provided
                    if model_formula is None:
                        model_formula = f"Impact = {a:.5f} * Size^{b:.5f}"
                except Exception as fit_error:
                    logger.warning(f"Error fitting curve: {str(fit_error)}")
            
            # Set labels and title
            ax.set_xlabel('Order Size')
            ax.set_ylabel('Market Impact')
            ax.set_title(f'Market Impact Curve for {market_name} ({side.capitalize()} Orders)')
            
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
            logger.error(f"Error plotting market impact: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting market impact: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_liquidity_score_breakdown(self, data: pd.DataFrame,
                                     score_col: str = 'liquidity_score',
                                     component_cols: List[str] = None,
                                     figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot a breakdown of liquidity score components over time.
        
        Args:
            data: DataFrame with liquidity score and component data
            score_col: Column name for the overall liquidity score
            component_cols: List of column names for the score components
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if score_col not in data.columns:
                raise ValueError(f"Score column '{score_col}' not found in data")
            
            # Default component columns if not provided
            if component_cols is None:
                # Try to find columns that contain 'component' or end with 'score'
                component_cols = [col for col in data.columns 
                                if 'component' in col.lower() or 
                                (col.lower().endswith('score') and col != score_col)]
                
                if not component_cols:
                    # If no columns found, assume these common components
                    potential_cols = ['spread_score', 'depth_score', 'resilience_score', 
                                    'volume_score', 'volatility_score']
                    component_cols = [col for col in potential_cols if col in data.columns]
            
            # Ensure at least one component column exists
            valid_components = [col for col in component_cols if col in data.columns]
            
            if not valid_components:
                raise ValueError("No valid component columns found in data")
            
            # Create figure with two subplots: overall score and components
            fig, axes = plt.subplots(2, 1, figsize=figsize or (12, 10), sharex=True)
            
            # Plot overall liquidity score
            ax_score = axes[0]
            ax_score.plot(data.index, data[score_col], color=self.colors['liquidity_score'], 
                         linewidth=2, label='Overall Liquidity Score')
            
            # Set labels and title for score plot
            ax_score.set_ylabel('Liquidity Score')
            ax_score.set_title('Liquidity Score Over Time')
            ax_score.legend()
            ax_score.grid(True, alpha=0.3)
            
            # Plot components
            ax_components = axes[1]
            
            for col in valid_components:
                # Create a display name from the column name
                display_name = col.replace('_', ' ').title()
                display_name = display_name.replace('Score', 'Component')
                
                ax_components.plot(data.index, data[col], linewidth=1.5, label=display_name)
            
            # Set labels and title for components plot
            ax_components.set_xlabel('Time')
            ax_components.set_ylabel('Component Scores')
            ax_components.set_title('Liquidity Score Components')
            ax_components.legend()
            ax_components.grid(True, alpha=0.3)
            
            # Format x-axis for datetime index
            if isinstance(data.index, pd.DatetimeIndex):
                plt.gcf().autofmt_xdate()
            
            # Calculate and display correlation between components and overall score
            correlations = {}
            for col in valid_components:
                correlations[col] = data[col].corr(data[score_col])
            
            # Sort by correlation
            sorted_corrs = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
            
            # Format for display
            corr_text = "Correlation with Overall Score: "
            corr_text += ", ".join([f"{col.split('_')[0]}: {corr:.2f}" for col, corr in sorted_corrs])
            
            plt.figtext(0.5, 0.01, corr_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, axes
            
        except Exception as e:
            logger.error(f"Error plotting liquidity score breakdown: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting liquidity breakdown: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_liquidity_resilience(self, data: pd.DataFrame,
                                event_times: List[datetime],
                                metric_col: str = 'depth',
                                window_before: int = 10,
                                window_after: int = 30,
                                aggregate: bool = True,
                                figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot market liquidity resilience around market events.
        
        Args:
            data: DataFrame with liquidity metrics
            event_times: List of event timestamps to analyze resilience around
            metric_col: Column name for the liquidity metric to analyze
            window_before: Number of periods to analyze before each event
            window_after: Number of periods to analyze after each event
            aggregate: If True, aggregate all events; if False, plot each event separately
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if metric_col not in data.columns:
                raise ValueError(f"Metric column '{metric_col}' not found in data")
            
            if not event_times:
                raise ValueError("No event times provided")
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Prepare matrices to store values around events
            event_matrices = []
            
            for event_time in event_times:
                # Find the closest time in the data
                if isinstance(data.index, pd.DatetimeIndex):
                    closest_idx = data.index.get_indexer([event_time], method='nearest')[0]
                else:
                    # If not datetime index, find the nearest index by position
                    closest_idx = min(range(len(data)), key=lambda i: abs(i - event_time))
                
                # Extract data window around the event
                start_idx = max(0, closest_idx - window_before)
                end_idx = min(len(data), closest_idx + window_after + 1)
                
                window_data = data.iloc[start_idx:end_idx][metric_col].values
                
                # Pad if necessary
                if len(window_data) < (window_before + window_after + 1):
                    pad_before = max(0, window_before - (closest_idx - start_idx))
                    pad_after = max(0, window_after - (end_idx - closest_idx - 1))
                    window_data = np.pad(window_data, 
                                        (pad_before, pad_after),
                                        'constant', 
                                        constant_values=np.nan)
                
                # Normalize to pre-event level
                pre_event_value = window_data[window_before - 1]
                if pre_event_value != 0:
                    window_data = window_data / pre_event_value
                
                event_matrices.append(window_data)
            
            # Convert to numpy array
            event_matrix = np.array(event_matrices)
            
            # Create x-axis in relative time to event
            x_values = np.arange(-window_before, window_after + 1)
            
            if aggregate:
                # Aggregate all events (mean and std)
                mean_values = np.nanmean(event_matrix, axis=0)
                std_values = np.nanstd(event_matrix, axis=0)
                
                # Plot mean with shadow for std
                ax.plot(x_values, mean_values, color=self.colors[metric_col] 
                       if metric_col in self.colors else 'blue',
                       linewidth=2, label=f'Mean {metric_col.replace("_", " ").title()}')
                
                ax.fill_between(x_values, 
                               mean_values - std_values, 
                               mean_values + std_values, 
                               alpha=0.2, color=self.colors[metric_col] 
                               if metric_col in self.colors else 'blue',
                               label='±1 Std Dev')
                
                # Mark the event time
                ax.axvline(x=0, color='black', linestyle='--', linewidth=1, label='Event')
                
                # Add pre-event reference line
                ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=1, 
                          label='Pre-event level')
                
            else:
                # Plot each event separately
                for i, event_data in enumerate(event_matrix):
                    event_time_str = event_times[i]
                    if isinstance(event_time_str, datetime):
                        event_time_str = event_time_str.strftime('%Y-%m-%d %H:%M:%S')
                    
                    ax.plot(x_values, event_data, alpha=0.7, 
                           label=f'Event {i+1} - {event_time_str}')
                
                # Mark the event time
                ax.axvline(x=0, color='black', linestyle='--', linewidth=1, label='Event Time')
                
                # Add pre-event reference
                ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=1, 
                          label='Pre-event level')
            
            # Set labels and title
            ax.set_xlabel('Time Relative to Event')
            y_label = f'{metric_col.replace("_", " ").title()} (Normalized to Pre-Event)'
            ax.set_ylabel(y_label)
            ax.set_title(f'Market {metric_col.replace("_", " ").title()} Resilience Around Events')
            
            # Add grid and legend
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Compute and display recovery statistics
            if aggregate:
                # Find first time the mean crosses back to pre-event level
                recovery_time = None
                min_value = np.min(mean_values[window_before:])
                
                for i in range(window_before + 1, len(mean_values)):
                    if mean_values[i] >= 1.0:
                        recovery_time = i - window_before
                        break
                
                recovery_text = (
                    f"Min value: {min_value:.2f} of pre-event level  |  "
                    f"Recovery time: {recovery_time if recovery_time is not None else 'N/A'} periods"
                )
                
                plt.figtext(0.5, 0.01, recovery_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting liquidity resilience: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting liquidity resilience: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax 