"""
Order Flow Visualizer Module

This module provides tools for visualizing order flow data, including:
- Trade flow visualization
- Volume profile analysis
- Trade clustering and pattern detection
- Time and sales data visualization
- VPIN (Volume-Synchronized Probability of Informed Trading) visualization
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

class OrderFlowVisualizer:
    """
    Visualization tools for order flow and trade data.
    
    This class provides various methods to visualize trade patterns, volume profiles,
    and other metrics derived from order flow data.
    """
    
    def __init__(self, figsize: Tuple[int, int] = (12, 8), style: str = 'seaborn-darkgrid'):
        """
        Initialize the OrderFlowVisualizer.
        
        Args:
            figsize: Default figure size for plots (width, height)
            style: Matplotlib style to use for plots
        """
        self.figsize = figsize
        self.style = style
        self.colors = {
            'buy': 'green',
            'sell': 'red',
            'volume': 'blue',
            'price': 'purple',
            'vpin': 'orange',
            'poi': 'magenta',  # Point of interest
        }
        plt.style.use(style)
    
    def plot_trade_flow(self, trades: pd.DataFrame,
                       price_col: str = 'price',
                       size_col: str = 'size',
                       side_col: Optional[str] = 'side',
                       time_col: Optional[str] = None,
                       time_window: Optional[pd.Timedelta] = None,
                       show_buys_sells: bool = True,
                       show_sizes: bool = True,
                       figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot trade flow with price, size, and buy/sell indicators.
        
        Args:
            trades: DataFrame with trade data
            price_col: Column name for price
            size_col: Column name for trade size
            side_col: Column name for trade side ('buy' or 'sell')
            time_col: Column name for timestamp (if None, uses index)
            time_window: If provided, show only trades within this time window from the end
            show_buys_sells: If True, differentiate buy and sell trades
            show_sizes: If True, use marker size to indicate trade size
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if price_col not in trades.columns:
                raise ValueError(f"Price column '{price_col}' not found in data")
            if size_col not in trades.columns:
                raise ValueError(f"Size column '{size_col}' not found in data")
            
            # Make a copy of the trade data
            plot_data = trades.copy()
            
            # Ensure we have a datetime index for the trades
            if time_col is not None and time_col in plot_data.columns:
                if not pd.api.types.is_datetime64_any_dtype(plot_data[time_col]):
                    plot_data[time_col] = pd.to_datetime(plot_data[time_col])
                plot_data.set_index(time_col, inplace=True)
            else:
                # Try to use the existing index
                if not isinstance(plot_data.index, pd.DatetimeIndex):
                    # If the index is not a DatetimeIndex, create a simple range index
                    logger.warning("No timestamp column found, using sequential index")
                    plot_data.reset_index(drop=True, inplace=True)
            
            # Filter by time window if provided
            if time_window is not None and isinstance(plot_data.index, pd.DatetimeIndex):
                start_time = plot_data.index[-1] - time_window
                plot_data = plot_data[plot_data.index >= start_time]
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Determine how to plot (with or without buy/sell differentiation)
            if show_buys_sells and side_col in plot_data.columns:
                # Extract buy and sell trades
                buy_trades = plot_data[plot_data[side_col].str.lower() == 'buy']
                sell_trades = plot_data[plot_data[side_col].str.lower() == 'sell']
                
                # Calculate marker sizes
                if show_sizes:
                    # Normalize sizes for visualization
                    max_size = plot_data[size_col].max()
                    buy_sizes = 50 * buy_trades[size_col] / max_size
                    sell_sizes = 50 * sell_trades[size_col] / max_size
                else:
                    buy_sizes = 20  # Default marker size
                    sell_sizes = 20
                
                # Plot buy trades (green circles)
                ax.scatter(buy_trades.index, buy_trades[price_col], 
                          s=buy_sizes, marker='o', color=self.colors['buy'], 
                          alpha=0.7, label='Buy Trades')
                
                # Plot sell trades (red triangles)
                ax.scatter(sell_trades.index, sell_trades[price_col], 
                          s=sell_sizes, marker='v', color=self.colors['sell'], 
                          alpha=0.7, label='Sell Trades')
                
            else:
                # Calculate marker sizes
                if show_sizes:
                    # Normalize sizes for visualization
                    max_size = plot_data[size_col].max()
                    marker_sizes = 50 * plot_data[size_col] / max_size
                else:
                    marker_sizes = 20  # Default marker size
                
                # Plot all trades without differentiating buy/sell
                ax.scatter(plot_data.index, plot_data[price_col], 
                          s=marker_sizes, marker='o', color=self.colors['price'], 
                          alpha=0.7, label='Trades')
            
            # Set labels and title
            ax.set_ylabel('Price')
            ax.set_title('Trade Flow')
            
            # Format x-axis
            if isinstance(plot_data.index, pd.DatetimeIndex):
                plt.gcf().autofmt_xdate()
                ax.set_xlabel('Time')
            else:
                ax.set_xlabel('Trade Sequence')
            
            # Add grid and legend
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Calculate and display trade statistics
            total_volume = plot_data[size_col].sum()
            trade_count = len(plot_data)
            avg_trade_size = total_volume / trade_count if trade_count > 0 else 0
            
            # Add buy/sell ratio if available
            if show_buys_sells and side_col in plot_data.columns:
                buy_volume = buy_trades[size_col].sum()
                sell_volume = sell_trades[size_col].sum()
                buy_ratio = buy_volume / total_volume if total_volume > 0 else 0
                
                stats_text = (
                    f"Total Volume: {total_volume:.2f}  |  "
                    f"Trades: {trade_count}  |  "
                    f"Avg Size: {avg_trade_size:.2f}  |  "
                    f"Buy Ratio: {buy_ratio:.2%}"
                )
            else:
                stats_text = (
                    f"Total Volume: {total_volume:.2f}  |  "
                    f"Trades: {trade_count}  |  "
                    f"Avg Size: {avg_trade_size:.2f}"
                )
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting trade flow: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting trade flow: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_volume_profile(self, price_volume_data: pd.DataFrame,
                          price_col: str = 'price',
                          volume_col: str = 'volume',
                          time_col: Optional[str] = None,
                          time_window: Optional[pd.Timedelta] = None,
                          n_bins: int = 50,
                          horizontal: bool = True,
                          show_vwap: bool = True,
                          figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot volume profile (volume at price levels).
        
        Args:
            price_volume_data: DataFrame with price and volume data
            price_col: Column name for price
            volume_col: Column name for volume
            time_col: Column name for timestamp (if None, uses index)
            time_window: If provided, show only data within this time window from the end
            n_bins: Number of price bins for the profile
            horizontal: If True, plot horizontal bars; if False, plot vertical bars
            show_vwap: If True, show volume-weighted average price line
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if price_col not in price_volume_data.columns:
                raise ValueError(f"Price column '{price_col}' not found in data")
            if volume_col not in price_volume_data.columns:
                raise ValueError(f"Volume column '{volume_col}' not found in data")
            
            # Make a copy of the data
            data = price_volume_data.copy()
            
            # Set index to time column if provided
            if time_col is not None and time_col in data.columns:
                if not pd.api.types.is_datetime64_any_dtype(data[time_col]):
                    data[time_col] = pd.to_datetime(data[time_col])
                data.set_index(time_col, inplace=True)
            
            # Filter by time window if provided
            if time_window is not None and isinstance(data.index, pd.DatetimeIndex):
                start_time = data.index[-1] - time_window
                data = data[data.index >= start_time]
            
            # Create price bins
            min_price = data[price_col].min()
            max_price = data[price_col].max()
            price_range = max_price - min_price
            
            # Ensure we have a reasonable range
            if price_range <= 0:
                price_range = max_price * 0.1  # 10% of the price if range is zero
                min_price = max_price - price_range
            
            # Add a small buffer
            buffer = price_range * 0.05
            min_price -= buffer
            max_price += buffer
            
            # Create bins
            bins = np.linspace(min_price, max_price, n_bins + 1)
            bin_centers = (bins[:-1] + bins[1:]) / 2
            
            # Compute volume profile
            profile, _ = np.histogram(data[price_col], bins=bins, weights=data[volume_col])
            
            # Calculate VWAP if requested
            if show_vwap:
                vwap = np.sum(data[price_col] * data[volume_col]) / np.sum(data[volume_col])
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Plot volume profile
            if horizontal:
                ax.barh(bin_centers, profile, height=(bins[1] - bins[0]), 
                       color=self.colors['volume'], alpha=0.7)
                
                # Add VWAP line if requested
                if show_vwap:
                    ax.axhline(y=vwap, color=self.colors['price'], linestyle='-', 
                              linewidth=1.5, label=f'VWAP: {vwap:.2f}')
                
                # Set labels
                ax.set_xlabel('Volume')
                ax.set_ylabel('Price')
                
            else:
                ax.bar(bin_centers, profile, width=(bins[1] - bins[0]), 
                      color=self.colors['volume'], alpha=0.7)
                
                # Add VWAP line if requested
                if show_vwap:
                    ax.axvline(x=vwap, color=self.colors['price'], linestyle='-', 
                              linewidth=1.5, label=f'VWAP: {vwap:.2f}')
                
                # Set labels
                ax.set_xlabel('Price')
                ax.set_ylabel('Volume')
            
            # Set title
            time_str = ""
            if time_window is not None and isinstance(data.index, pd.DatetimeIndex):
                time_str = f" - Last {time_window}"
            ax.set_title(f'Volume Profile{time_str}')
            
            # Add grid and legend
            ax.grid(True, alpha=0.3)
            if show_vwap:
                ax.legend()
            
            # Calculate and display profile statistics
            max_volume_price = bin_centers[np.argmax(profile)]
            volume_weighted_price = np.sum(bin_centers * profile) / np.sum(profile) if np.sum(profile) > 0 else 0
            
            stats_text = (
                f"Max Volume Price: {max_volume_price:.2f}  |  "
                f"Volume-Weighted Price: {volume_weighted_price:.2f}"
            )
            
            if show_vwap:
                stats_text += f"  |  VWAP: {vwap:.2f}"
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting volume profile: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting volume profile: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_vpin(self, vpin_data: pd.DataFrame,
                 vpin_col: str = 'vpin',
                 volume_col: Optional[str] = 'volume',
                 price_col: Optional[str] = 'price',
                 threshold: Optional[float] = None,
                 time_window: Optional[pd.Timedelta] = None,
                 figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot the Volume-Synchronized Probability of Informed Trading (VPIN).
        
        Args:
            vpin_data: DataFrame with VPIN and optionally volume and price data
            vpin_col: Column name for VPIN values
            volume_col: Column name for volume (if None, volume not plotted)
            price_col: Column name for price (if None, price not plotted)
            threshold: If provided, show threshold line for VPIN
            time_window: If provided, show only data within this time window from the end
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if vpin_col not in vpin_data.columns:
                raise ValueError(f"VPIN column '{vpin_col}' not found in data")
            
            # Make a copy of the data
            data = vpin_data.copy()
            
            # Filter by time window if provided
            if time_window is not None and isinstance(data.index, pd.DatetimeIndex):
                start_time = data.index[-1] - time_window
                data = data[data.index >= start_time]
            
            # Determine the number of subplots
            show_volume = volume_col is not None and volume_col in data.columns
            show_price = price_col is not None and price_col in data.columns
            n_plots = 1 + show_volume + show_price
            
            # Create figure with appropriate number of subplots
            fig, axes = plt.subplots(n_plots, 1, figsize=figsize or self.figsize, 
                                    sharex=True, gridspec_kw={'height_ratios': [3] + [1] * (n_plots - 1)})
            
            # Convert to list if only one subplot
            if n_plots == 1:
                axes = [axes]
            
            # Plot VPIN
            ax_vpin = axes[0]
            ax_vpin.plot(data.index, data[vpin_col], label='VPIN', color=self.colors['vpin'], 
                       linewidth=1.5)
            
            # Add threshold if provided
            if threshold is not None:
                ax_vpin.axhline(y=threshold, color='red', linestyle='--', 
                              label=f'Threshold ({threshold:.2f})')
                
                # Highlight regions above threshold
                above_threshold = data[vpin_col] > threshold
                if above_threshold.any():
                    ax_vpin.fill_between(data.index, data[vpin_col], threshold, 
                                      where=above_threshold, color='red', alpha=0.3)
            
            # Set labels and title
            ax_vpin.set_ylabel('VPIN')
            ax_vpin.set_title('Volume-Synchronized Probability of Informed Trading (VPIN)')
            ax_vpin.legend()
            ax_vpin.grid(True, alpha=0.3)
            
            # Plot price if requested
            plot_idx = 1
            if show_price:
                ax_price = axes[plot_idx]
                ax_price.plot(data.index, data[price_col], color=self.colors['price'], 
                             linewidth=1, label='Price')
                ax_price.set_ylabel('Price')
                ax_price.legend()
                ax_price.grid(True, alpha=0.3)
                plot_idx += 1
            
            # Plot volume if requested
            if show_volume:
                ax_volume = axes[plot_idx]
                ax_volume.bar(data.index, data[volume_col], color=self.colors['volume'], 
                             alpha=0.7, label='Volume')
                ax_volume.set_ylabel('Volume')
                ax_volume.legend()
                ax_volume.grid(True, alpha=0.3)
            
            # Format x-axis for datetime index
            if isinstance(data.index, pd.DatetimeIndex):
                plt.gcf().autofmt_xdate()
                axes[-1].set_xlabel('Time')
            else:
                axes[-1].set_xlabel('Bucket')
            
            # Calculate VPIN statistics
            vpin_mean = data[vpin_col].mean()
            vpin_std = data[vpin_col].std()
            vpin_max = data[vpin_col].max()
            
            # Identify potential toxicity events
            if threshold is not None:
                toxic_periods = data[data[vpin_col] > threshold]
                toxic_count = len(toxic_periods)
                toxic_ratio = toxic_count / len(data) if len(data) > 0 else 0
                
                stats_text = (
                    f"VPIN Mean: {vpin_mean:.4f}  |  "
                    f"VPIN Std: {vpin_std:.4f}  |  "
                    f"VPIN Max: {vpin_max:.4f}  |  "
                    f"Toxic Periods: {toxic_count} ({toxic_ratio:.2%})"
                )
            else:
                stats_text = (
                    f"VPIN Mean: {vpin_mean:.4f}  |  "
                    f"VPIN Std: {vpin_std:.4f}  |  "
                    f"VPIN Max: {vpin_max:.4f}"
                )
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, axes
            
        except Exception as e:
            logger.error(f"Error plotting VPIN: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting VPIN: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_trade_clusters(self, trades: pd.DataFrame,
                          cluster_col: str = 'cluster',
                          price_col: str = 'price',
                          size_col: str = 'size',
                          time_col: Optional[str] = None,
                          highlight_large: bool = True,
                          size_threshold: Optional[float] = None,
                          figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot trade clusters with optional highlighting of large trades.
        
        Args:
            trades: DataFrame with trade data including cluster assignments
            cluster_col: Column name for cluster labels
            price_col: Column name for price
            size_col: Column name for trade size
            time_col: Column name for timestamp (if None, uses index)
            highlight_large: If True, highlight trades above size_threshold
            size_threshold: Size threshold for highlighting large trades (if None, use 95th percentile)
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            required_cols = [cluster_col, price_col, size_col]
            for col in required_cols:
                if col not in trades.columns:
                    raise ValueError(f"Required column '{col}' not found in data")
            
            # Make a copy of the trade data
            plot_data = trades.copy()
            
            # Ensure we have a proper index for the trades
            if time_col is not None and time_col in plot_data.columns:
                if not pd.api.types.is_datetime64_any_dtype(plot_data[time_col]):
                    plot_data[time_col] = pd.to_datetime(plot_data[time_col])
                plot_data.set_index(time_col, inplace=True)
            
            # Get unique clusters
            clusters = plot_data[cluster_col].unique()
            
            # Define a colormap for clusters
            cmap = plt.cm.get_cmap('tab10', len(clusters))
            
            # Determine size threshold for highlighting large trades
            if highlight_large:
                if size_threshold is None:
                    size_threshold = plot_data[size_col].quantile(0.95)
                large_trades = plot_data[plot_data[size_col] >= size_threshold]
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Plot each cluster with a different color
            for i, cluster in enumerate(clusters):
                cluster_data = plot_data[plot_data[cluster_col] == cluster]
                
                # Normalize sizes for visualization
                max_size = plot_data[size_col].max()
                marker_sizes = 30 * cluster_data[size_col] / max_size
                
                ax.scatter(cluster_data.index, cluster_data[price_col], 
                          s=marker_sizes, marker='o', color=cmap(i), 
                          alpha=0.7, label=f'Cluster {cluster}')
            
            # Highlight large trades if requested
            if highlight_large and not large_trades.empty:
                # Normalize sizes for visualization
                highlight_sizes = 100 * large_trades[size_col] / large_trades[size_col].max()
                
                ax.scatter(large_trades.index, large_trades[price_col], 
                          s=highlight_sizes, marker='*', color=self.colors['poi'], 
                          alpha=0.9, edgecolors='black', linewidth=1, 
                          label=f'Large Trades (>{size_threshold:.2f})')
            
            # Set labels and title
            ax.set_ylabel('Price')
            ax.set_title('Trade Clusters Analysis')
            
            # Format x-axis
            if isinstance(plot_data.index, pd.DatetimeIndex):
                plt.gcf().autofmt_xdate()
                ax.set_xlabel('Time')
            else:
                ax.set_xlabel('Trade Sequence')
            
            # Add grid and legend
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Calculate and display cluster statistics
            cluster_sizes = plot_data.groupby(cluster_col).size()
            cluster_volumes = plot_data.groupby(cluster_col)[size_col].sum()
            largest_cluster = cluster_sizes.idxmax()
            highest_volume_cluster = cluster_volumes.idxmax()
            
            stats_text = (
                f"Clusters: {len(clusters)}  |  "
                f"Largest Cluster: {largest_cluster} ({cluster_sizes[largest_cluster]} trades)  |  "
                f"Highest Volume Cluster: {highest_volume_cluster} ({cluster_volumes[highest_volume_cluster]:.2f})"
            )
            
            if highlight_large:
                large_count = len(large_trades)
                large_ratio = large_count / len(plot_data) if len(plot_data) > 0 else 0
                stats_text += f"  |  Large Trades: {large_count} ({large_ratio:.2%})"
            
            plt.figtext(0.5, 0.01, stats_text, ha='center', fontsize=9)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting trade clusters: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting trade clusters: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax 