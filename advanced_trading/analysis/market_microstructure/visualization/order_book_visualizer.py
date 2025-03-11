"""
Order Book Visualizer Module

This module provides tools for visualizing order book data, including:
- Static order book visualization (bid-ask depth, cumulative depth)
- Dynamic order book visualization over time (heatmaps, animations)
- Order book imbalance visualization
- Custom visualizations for specific analysis needs
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
import io
import base64
from IPython.display import HTML, display

# Setup logging
logger = logging.getLogger(__name__)

class OrderBookVisualizer:
    """
    Visualization tools for order book data and metrics.
    
    This class provides various methods to visualize order book depth, imbalance,
    price levels, and dynamics over time using static plots, heatmaps, and animations.
    """
    
    def __init__(self, figsize: Tuple[int, int] = (10, 6), style: str = 'seaborn-darkgrid'):
        """
        Initialize the OrderBookVisualizer.
        
        Args:
            figsize: Default figure size for plots (width, height)
            style: Matplotlib style to use for plots
        """
        self.figsize = figsize
        self.style = style
        self.cmap_bids = plt.cm.Greens
        self.cmap_asks = plt.cm.Reds
        self.cmap_imbalance = plt.cm.coolwarm
        plt.style.use(style)
    
    def plot_order_book_snapshot(self, order_book: Dict[str, Any], 
                                levels: int = 10,
                                price_precision: int = 2,
                                quantity_precision: int = 4,
                                normalize_prices: bool = False,
                                show_cumulative: bool = True,
                                highlight_touch: bool = True,
                                title: Optional[str] = None,
                                figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot a static snapshot of the order book.
        
        Args:
            order_book: Dictionary containing 'bids' and 'asks' lists of [price, quantity] pairs
            levels: Number of price levels to show on each side
            price_precision: Number of decimal places for price display
            quantity_precision: Number of decimal places for quantity display
            normalize_prices: If True, show prices as percentage from mid price
            show_cumulative: If True, show cumulative quantities
            highlight_touch: If True, highlight best bid/ask
            title: Optional title for the plot
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Extract bids and asks
            bids = np.array(order_book['bids'][:levels]) if 'bids' in order_book else np.array([])
            asks = np.array(order_book['asks'][:levels]) if 'asks' in order_book else np.array([])
            
            if len(bids) == 0 or len(asks) == 0:
                logger.warning("Empty order book or insufficient levels")
                fig, ax = plt.subplots(figsize=figsize or self.figsize)
                ax.text(0.5, 0.5, "Insufficient order book data", 
                        horizontalalignment='center', fontsize=14)
                ax.set_title(title or "Order Book Snapshot")
                return fig, ax
            
            # Calculate mid price
            mid_price = (bids[0][0] + asks[0][0]) / 2
            
            # Normalize prices if requested
            if normalize_prices:
                bids_norm = np.array([[100 * (p / mid_price - 1), q] for p, q in bids])
                asks_norm = np.array([[100 * (p / mid_price - 1), q] for p, q in asks])
                bids = bids_norm
                asks = asks_norm
            
            # Calculate cumulative quantities if requested
            if show_cumulative:
                bids_cumulative = np.array([[p, np.sum(bids[:i+1, 1])] for i, (p, _) in enumerate(bids)])
                asks_cumulative = np.array([[p, np.sum(asks[:i+1, 1])] for i, (p, _) in enumerate(asks)])
                bid_quantities = bids_cumulative[:, 1]
                ask_quantities = asks_cumulative[:, 1]
            else:
                bid_quantities = bids[:, 1]
                ask_quantities = asks[:, 1]
            
            # Extract prices
            bid_prices = bids[:, 0]
            ask_prices = asks[:, 0]
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Plot bids
            ax.bar(bid_prices, bid_quantities, width=(mid_price * 0.0015), 
                   align='center', alpha=0.7, color='green', label='Bids')
            
            # Plot asks
            ax.bar(ask_prices, ask_quantities, width=(mid_price * 0.0015), 
                   align='center', alpha=0.7, color='red', label='Asks')
            
            # Highlight best bid/ask
            if highlight_touch:
                ax.axvline(x=bids[0][0], color='darkgreen', linestyle='--', alpha=0.7)
                ax.axvline(x=asks[0][0], color='darkred', linestyle='--', alpha=0.7)
                
                # Add mid price line
                ax.axvline(x=mid_price, color='gray', linestyle='-', alpha=0.5, label='Mid')
            
            # Set labels
            if normalize_prices:
                ax.set_xlabel("Price (% from mid)")
                # Format tick labels
                def price_formatter(x, pos):
                    return f"{x:+.{price_precision}f}%"
                ax.xaxis.set_major_formatter(plt.FuncFormatter(price_formatter))
            else:
                ax.set_xlabel(f"Price")
                # Format tick labels
                def price_formatter(x, pos):
                    return f"{x:.{price_precision}f}"
                ax.xaxis.set_major_formatter(plt.FuncFormatter(price_formatter))
            
            # Y-axis label
            label = "Cumulative Quantity" if show_cumulative else "Quantity"
            ax.set_ylabel(label)
            
            # Add legend
            ax.legend()
            
            # Title
            default_title = "Order Book Snapshot"
            if title is None:
                title = default_title
                if 'timestamp' in order_book:
                    timestamp = order_book['timestamp']
                    if isinstance(timestamp, (int, float)):
                        # Convert from ms to datetime
                        dt = datetime.fromtimestamp(timestamp / 1000.0)
                        title += f" at {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
            ax.set_title(title)
            
            # Add summary text
            spread = asks[0][0] - bids[0][0]
            spread_pct = 100 * spread / mid_price
            
            summary_text = (
                f"Mid: {mid_price:.{price_precision}f}  "
                f"Spread: {spread:.{price_precision}f} ({spread_pct:.3f}%)  "
                f"Bid Depth: {np.sum(bids[:, 1]):.{quantity_precision}f}  "
                f"Ask Depth: {np.sum(asks[:, 1]):.{quantity_precision}f}"
            )
            
            plt.figtext(0.5, 0.01, summary_text, ha='center', fontsize=10)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting order book snapshot: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting order book: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_order_book_heatmap(self, order_book_history: List[Dict[str, Any]],
                               levels: int = 10,
                               normalize_prices: bool = True,
                               show_imbalance: bool = False,
                               figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot a heatmap of order book depth over time.
        
        Args:
            order_book_history: List of order book snapshots over time
            levels: Number of price levels to show on each side
            normalize_prices: If True, normalize price levels relative to mid price
            show_imbalance: If True, show bid-ask imbalance instead of raw quantities
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if not order_book_history:
                raise ValueError("Empty order book history")
            
            # Calculate price levels and quantities
            timestamps = []
            mid_prices = []
            bid_matrices = []
            ask_matrices = []
            
            for ob in order_book_history:
                bids = np.array(ob['bids'][:levels]) if 'bids' in ob and len(ob['bids']) > 0 else np.zeros((levels, 2))
                asks = np.array(ob['asks'][:levels]) if 'asks' in ob and len(ob['asks']) > 0 else np.zeros((levels, 2))
                
                # Ensure we have enough levels
                if len(bids) < levels:
                    bids = np.vstack([bids, np.zeros((levels - len(bids), 2))])
                if len(asks) < levels:
                    asks = np.vstack([asks, np.zeros((levels - len(asks), 2))])
                
                # Get timestamp
                if 'timestamp' in ob:
                    timestamp = ob['timestamp']
                    if isinstance(timestamp, (int, float)):
                        timestamps.append(datetime.fromtimestamp(timestamp / 1000.0))
                    else:
                        timestamps.append(timestamp)
                else:
                    timestamps.append(len(timestamps))
                
                # Calculate mid price
                if len(bids) > 0 and len(asks) > 0 and bids[0][0] > 0 and asks[0][0] > 0:
                    mid_price = (bids[0][0] + asks[0][0]) / 2
                else:
                    # Use previous mid price if available, otherwise 0
                    mid_price = mid_prices[-1] if mid_prices else 0
                mid_prices.append(mid_price)
                
                # Extract quantities
                bid_quantities = bids[:, 1]
                ask_quantities = asks[:, 1]
                
                # Store in matrices
                bid_matrices.append(bid_quantities)
                ask_matrices.append(ask_quantities)
            
            # Convert to numpy arrays
            bid_matrix = np.array(bid_matrices)
            ask_matrix = np.array(ask_matrices)
            mid_prices = np.array(mid_prices)
            
            # Calculate imbalance if requested
            if show_imbalance:
                # Calculate total bid and ask volume at each time
                bid_totals = np.sum(bid_matrix, axis=1, keepdims=True)
                ask_totals = np.sum(ask_matrix, axis=1, keepdims=True)
                
                # Avoid division by zero
                total_volume = bid_totals + ask_totals
                total_volume[total_volume == 0] = 1
                
                # Calculate imbalance (ranges from -1 to 1)
                imbalance = (bid_totals - ask_totals) / total_volume
                
                # Create a combined matrix for display
                combined_matrix = np.hstack([
                    np.flip(bid_matrix / np.maximum(1, bid_totals), axis=1),
                    imbalance,
                    ask_matrix / np.maximum(1, ask_totals)
                ])
                
                # For labeling x-axis
                level_labels = list(range(-levels, 0)) + ['Imb'] + list(range(1, levels + 1))
                
            else:
                # Create a combined matrix for display
                combined_matrix = np.hstack([np.flip(bid_matrix, axis=1), ask_matrix])
                
                # For labeling x-axis
                level_labels = list(range(-levels, 0)) + list(range(1, levels + 1))
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or (10, 8))
            
            # Plot heatmap
            if show_imbalance:
                # Use a diverging colormap for imbalance
                cmap = 'coolwarm'
                norm = Normalize(vmin=-1, vmax=1)
            else:
                # Use a sequential colormap for quantities
                cmap = 'viridis'
                norm = None
            
            sns.heatmap(combined_matrix, cmap=cmap, norm=norm, ax=ax, 
                       cbar_kws={'label': 'Imbalance' if show_imbalance else 'Quantity'})
            
            # Set labels
            ax.set_xlabel("Price Level (Relative to Mid)")
            
            # Set x-tick labels
            ax.set_xticks(np.arange(len(level_labels)))
            ax.set_xticklabels(level_labels)
            
            # Set title
            ax.set_title("Order Book Depth Heatmap" + 
                         (" (Showing Relative Imbalance)" if show_imbalance else ""))
            
            # Format y-axis (timestamps)
            if isinstance(timestamps[0], datetime):
                # For datetime timestamps
                time_formatter = lambda i: timestamps[int(i)].strftime('%H:%M:%S') if 0 <= int(i) < len(timestamps) else ''
                # Select a reasonable number of ticks based on data size
                tick_count = min(10, len(timestamps))
                tick_positions = np.linspace(0, len(timestamps) - 1, tick_count)
                ax.set_yticks(tick_positions)
                ax.set_yticklabels([time_formatter(i) for i in tick_positions])
            
            # Add mid price evolution as a secondary axis
            ax2 = ax.twinx()
            times = np.arange(len(mid_prices))
            ax2.plot(mid_prices, times, color='white', linewidth=1.5, alpha=0.7)
            ax2.set_ylabel('Mid Price')
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting order book heatmap: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting heatmap: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_order_book_imbalance(self, order_book_metrics: pd.DataFrame,
                                 imbalance_col: str = 'order_book_imbalance',
                                 price_col: Optional[str] = 'mid_price',
                                 returns_col: Optional[str] = 'returns',
                                 figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot order book imbalance over time, optionally with price and returns.
        
        Args:
            order_book_metrics: DataFrame with order book metrics
            imbalance_col: Column name for imbalance values
            price_col: Column name for price (if None, price not plotted)
            returns_col: Column name for returns (if None, returns not plotted)
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            if imbalance_col not in order_book_metrics.columns:
                raise ValueError(f"Imbalance column '{imbalance_col}' not found in data")
            
            # Create figure with appropriate number of subplots
            n_plots = 1 + (price_col is not None) + (returns_col is not None)
            fig, axes = plt.subplots(n_plots, 1, figsize=figsize or (12, 3*n_plots), sharex=True)
            
            # Convert to list if only one subplot
            if n_plots == 1:
                axes = [axes]
            
            # Plot imbalance
            ax_imb = axes[0]
            imbalance = order_book_metrics[imbalance_col]
            ax_imb.plot(imbalance.index, imbalance, color='purple', label='Order Book Imbalance')
            ax_imb.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            ax_imb.set_title("Order Book Imbalance Over Time")
            ax_imb.set_ylabel("Imbalance")
            ax_imb.legend()
            
            # Fill positive/negative regions
            ax_imb.fill_between(imbalance.index, imbalance, 0, 
                              where=(imbalance > 0), color='green', alpha=0.3)
            ax_imb.fill_between(imbalance.index, imbalance, 0, 
                              where=(imbalance < 0), color='red', alpha=0.3)
            
            # Plot price if requested
            plot_idx = 1
            if price_col is not None and price_col in order_book_metrics.columns:
                ax_price = axes[plot_idx]
                ax_price.plot(order_book_metrics.index, order_book_metrics[price_col], 
                             color='blue', label='Price')
                ax_price.set_title("Price Over Time")
                ax_price.set_ylabel("Price")
                ax_price.legend()
                plot_idx += 1
            
            # Plot returns if requested
            if returns_col is not None and returns_col in order_book_metrics.columns:
                ax_ret = axes[plot_idx]
                returns = order_book_metrics[returns_col]
                ax_ret.plot(returns.index, returns, color='orange', label='Returns')
                ax_ret.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
                ax_ret.set_title("Returns Over Time")
                ax_ret.set_ylabel("Returns (%)")
                ax_ret.legend()
                
                # Fill positive/negative returns
                ax_ret.fill_between(returns.index, returns, 0, 
                                  where=(returns > 0), color='green', alpha=0.3)
                ax_ret.fill_between(returns.index, returns, 0, 
                                  where=(returns < 0), color='red', alpha=0.3)
            
            plt.tight_layout()
            return fig, axes
            
        except Exception as e:
            logger.error(f"Error plotting order book imbalance: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting imbalance: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def animate_order_book(self, order_book_history: List[Dict[str, Any]],
                          levels: int = 10,
                          interval: int = 200,
                          title: Optional[str] = None,
                          figsize: Optional[Tuple[int, int]] = None) -> HTML:
        """
        Create an animation of order book changes over time.
        
        Args:
            order_book_history: List of order book snapshots over time
            levels: Number of price levels to show on each side
            interval: Interval between frames in milliseconds
            title: Optional title for the animation
            figsize: Optional custom figure size
            
        Returns:
            HTML object with the animation for display in notebooks
        """
        try:
            if not order_book_history:
                raise ValueError("Empty order book history")
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Function to update the plot for each frame
            def update(frame):
                ax.clear()
                order_book = order_book_history[frame]
                
                # Extract bids and asks
                bids = np.array(order_book['bids'][:levels]) if 'bids' in order_book else np.array([])
                asks = np.array(order_book['asks'][:levels]) if 'asks' in order_book else np.array([])
                
                if len(bids) == 0 or len(asks) == 0:
                    ax.text(0.5, 0.5, "Insufficient order book data", 
                           horizontalalignment='center', fontsize=14)
                    return
                
                # Calculate mid price
                mid_price = (bids[0][0] + asks[0][0]) / 2
                
                # Calculate cumulative quantities
                bids_cumulative = np.array([[p, np.sum(bids[:i+1, 1])] for i, (p, _) in enumerate(bids)])
                asks_cumulative = np.array([[p, np.sum(asks[:i+1, 1])] for i, (p, _) in enumerate(asks)])
                
                # Extract prices and quantities
                bid_prices = bids_cumulative[:, 0]
                bid_quantities = bids_cumulative[:, 1]
                ask_prices = asks_cumulative[:, 0]
                ask_quantities = asks_cumulative[:, 1]
                
                # Plot bids
                ax.bar(bid_prices, bid_quantities, width=(mid_price * 0.0015), 
                      align='center', alpha=0.7, color='green', label='Bids')
                
                # Plot asks
                ax.bar(ask_prices, ask_quantities, width=(mid_price * 0.0015), 
                      align='center', alpha=0.7, color='red', label='Asks')
                
                # Highlight best bid/ask
                ax.axvline(x=bids[0][0], color='darkgreen', linestyle='--', alpha=0.7)
                ax.axvline(x=asks[0][0], color='darkred', linestyle='--', alpha=0.7)
                
                # Add mid price line
                ax.axvline(x=mid_price, color='gray', linestyle='-', alpha=0.5, label='Mid')
                
                # Set labels
                ax.set_xlabel("Price")
                ax.set_ylabel("Cumulative Quantity")
                
                # Add legend
                ax.legend()
                
                # Title
                frame_title = title if title else "Order Book Animation"
                if 'timestamp' in order_book:
                    timestamp = order_book['timestamp']
                    if isinstance(timestamp, (int, float)):
                        # Convert from ms to datetime
                        dt = datetime.fromtimestamp(timestamp / 1000.0)
                        frame_title += f" - {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
                ax.set_title(frame_title)
                
                # Add frame information
                ax.text(0.98, 0.02, f"Frame: {frame+1}/{len(order_book_history)}", 
                       transform=ax.transAxes, ha='right', fontsize=9)
                
                # Calculate and display spread
                spread = asks[0][0] - bids[0][0]
                spread_pct = 100 * spread / mid_price
                ax.text(0.02, 0.02, 
                       f"Mid: {mid_price:.2f}  Spread: {spread:.2f} ({spread_pct:.3f}%)", 
                       transform=ax.transAxes, ha='left', fontsize=9)
            
            # Create animation
            ani = animation.FuncAnimation(
                fig, update, frames=len(order_book_history), 
                interval=interval, blit=False
            )
            
            # Save to HTML
            html_output = HTML(ani.to_jshtml())
            plt.close(fig)  # Close the figure to free memory
            
            return html_output
            
        except Exception as e:
            logger.error(f"Error creating order book animation: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error creating animation: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            plt.close(fig)
            return HTML("<p>Error creating animation</p>")
    
    def plot_price_impact_curve(self, order_book: Dict[str, Any],
                               max_quantity: Optional[float] = None,
                               num_points: int = 20,
                               side: str = 'buy',
                               relative_prices: bool = True,
                               figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot the price impact curve based on order book depth.
        
        Args:
            order_book: Dictionary containing 'bids' and 'asks' lists of [price, quantity] pairs
            max_quantity: Maximum quantity to plot impact for (if None, uses total book depth)
            num_points: Number of points to calculate for the curve
            side: 'buy' or 'sell' side to analyze
            relative_prices: If True, show price impact as percentage from mid
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Extract bids and asks
            bids = np.array(order_book['bids']) if 'bids' in order_book else np.array([])
            asks = np.array(order_book['asks']) if 'asks' in order_book else np.array([])
            
            if len(bids) == 0 or len(asks) == 0:
                raise ValueError("Insufficient order book data")
            
            # Calculate mid price
            mid_price = (bids[0][0] + asks[0][0]) / 2
            
            # Determine max quantity if not provided
            if max_quantity is None:
                max_quantity = np.sum(asks[:, 1]) if side.lower() == 'buy' else np.sum(bids[:, 1])
            
            # Generate quantities to evaluate
            quantities = np.linspace(0, max_quantity, num_points)
            
            # Calculate impact for each quantity
            prices = []
            
            if side.lower() == 'buy':
                # For buy orders, we consume the ask side
                for q in quantities:
                    consumed = 0
                    avg_price = 0
                    total_cost = 0
                    
                    for ask_price, ask_size in asks:
                        # How much we consume from this level
                        consume_size = min(ask_size, q - consumed)
                        if consume_size <= 0:
                            break
                        
                        # Add to total cost
                        total_cost += consume_size * ask_price
                        consumed += consume_size
                        
                        if consumed >= q:
                            break
                    
                    if consumed > 0:
                        avg_price = total_cost / consumed
                        if relative_prices:
                            avg_price = 100 * (avg_price / mid_price - 1)  # As percentage
                        prices.append(avg_price)
                    else:
                        prices.append(np.nan)
            else:
                # For sell orders, we consume the bid side
                for q in quantities:
                    consumed = 0
                    avg_price = 0
                    total_proceeds = 0
                    
                    for bid_price, bid_size in bids:
                        # How much we consume from this level
                        consume_size = min(bid_size, q - consumed)
                        if consume_size <= 0:
                            break
                        
                        # Add to total proceeds
                        total_proceeds += consume_size * bid_price
                        consumed += consume_size
                        
                        if consumed >= q:
                            break
                    
                    if consumed > 0:
                        avg_price = total_proceeds / consumed
                        if relative_prices:
                            avg_price = 100 * (1 - avg_price / mid_price)  # Negative impact for sells
                        prices.append(avg_price)
                    else:
                        prices.append(np.nan)
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Plot impact curve
            ax.plot(quantities, prices, 'o-', linewidth=2, 
                   color='green' if side.lower() == 'buy' else 'red')
            
            # Add reference line at 0 for relative prices
            if relative_prices:
                ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            
            # Format axes
            ax.set_xlabel("Quantity")
            if relative_prices:
                ax.set_ylabel("Price Impact (%)")
            else:
                ax.set_ylabel("Average Execution Price")
            
            # Title
            ax.set_title(f"Price Impact Curve for {side.capitalize()} Orders")
            
            # Add annotations
            plt.figtext(0.5, 0.01, 
                       f"Mid Price: {mid_price:.4f}  |  Book Depth ({side}): {max_quantity:.4f}", 
                       ha='center', fontsize=10)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting price impact curve: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting impact curve: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax
    
    def plot_bid_ask_balance(self, order_book: Dict[str, Any],
                           levels: int = 10,
                           figsize: Optional[Tuple[int, int]] = None) -> Tuple[Figure, Axes]:
        """
        Plot a comparative view of bid and ask side balance.
        
        Args:
            order_book: Dictionary containing 'bids' and 'asks' lists of [price, quantity] pairs
            levels: Number of price levels to show on each side
            figsize: Optional custom figure size
            
        Returns:
            Tuple of (Figure, Axes)
        """
        try:
            # Extract bids and asks
            bids = np.array(order_book['bids'][:levels]) if 'bids' in order_book else np.array([])
            asks = np.array(order_book['asks'][:levels]) if 'asks' in order_book else np.array([])
            
            if len(bids) == 0 or len(asks) == 0:
                raise ValueError("Insufficient order book data")
            
            # Calculate cumulative volumes
            bid_cum_vol = np.cumsum(bids[:, 1])
            ask_cum_vol = np.cumsum(asks[:, 1])
            
            # Calculate mid price and price levels relative to mid
            mid_price = (bids[0][0] + asks[0][0]) / 2
            bid_rel_prices = [(mid_price - p) / mid_price * 100 for p, _ in bids]
            ask_rel_prices = [(p - mid_price) / mid_price * 100 for p, _ in asks]
            
            # Create figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            
            # Plot bid side (negative x axis)
            ax.barh(np.arange(len(bids)), -bid_cum_vol, color='green', alpha=0.7, label='Bids')
            
            # Plot ask side (positive x axis)
            ax.barh(np.arange(len(asks)), ask_cum_vol, color='red', alpha=0.7, label='Asks')
            
            # Add vertical line at 0
            ax.axvline(x=0, color='black', linestyle='-', linewidth=1)
            
            # Set y-ticks to show price levels
            ax.set_yticks(np.arange(max(len(bids), len(asks))))
            
            # Create tick labels showing price distance from mid
            bid_labels = [f"{p:.2f}% ({price:.2f})" for p, (price, _) in zip(bid_rel_prices, bids)]
            ask_labels = [f"{p:.2f}% ({price:.2f})" for p, (price, _) in zip(ask_rel_prices, asks)]
            
            # Combine labels, padding the shorter side with empty strings
            max_levels = max(len(bid_labels), len(ask_labels))
            bid_labels = bid_labels + [''] * (max_levels - len(bid_labels))
            ask_labels = ask_labels + [''] * (max_levels - len(ask_labels))
            
            # Show price distance on both sides (left for bids, right for asks)
            ax.set_yticklabels(bid_labels)
            ax2 = ax.twinx()
            ax2.set_yticks(np.arange(max_levels))
            ax2.set_yticklabels(ask_labels)
            
            # Set grid and axis labels
            ax.grid(True, axis='y', alpha=0.3)
            ax.set_xlabel("Cumulative Volume")
            ax.set_ylabel("Bid Price (% from mid)")
            ax2.set_ylabel("Ask Price (% from mid)")
            
            # Set title
            ax.set_title("Order Book Balance")
            
            # Add legend
            ax.legend(loc='upper left')
            
            # Calculate and show imbalance metrics
            bid_total = np.sum(bids[:, 1])
            ask_total = np.sum(asks[:, 1])
            imbalance = (bid_total - ask_total) / (bid_total + ask_total)
            
            plt.figtext(0.5, 0.01, 
                       f"Bid Total: {bid_total:.2f}  |  Ask Total: {ask_total:.2f}  |  Imbalance: {imbalance:.2%}", 
                       ha='center', fontsize=10)
            
            plt.tight_layout()
            return fig, ax
            
        except Exception as e:
            logger.error(f"Error plotting bid-ask balance: {str(e)}")
            # Return minimal figure
            fig, ax = plt.subplots(figsize=figsize or self.figsize)
            ax.text(0.5, 0.5, f"Error plotting bid-ask balance: {str(e)}", 
                    horizontalalignment='center', fontsize=10)
            return fig, ax 