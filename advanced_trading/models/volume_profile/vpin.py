#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Volume-synchronized Probability of Informed Trading (VPIN) Implementation.

This module provides tools for calculating VPIN, a metric for measuring order flow toxicity
and detecting potential informed trading in financial markets. VPIN is particularly useful
for identifying periods of high information asymmetry and potential market stress.

References:
- Easley, D., López de Prado, M. M., & O'Hara, M. (2012). Flow Toxicity and Liquidity in a 
  High-frequency World. The Review of Financial Studies, 25(5), 1457-1493.
- Easley, D., López de Prado, M. M., & O'Hara, M. (2011). The Microstructure of the 'Flash Crash': 
  Flow Toxicity, Liquidity Crashes, and the Probability of Informed Trading. The Journal of 
  Portfolio Management, 37(2), 118-128.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass
import logging
from scipy import stats
import warnings

# Configure logging
logger = logging.getLogger(__name__)

# Suppress specific warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in double_scalars")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="divide by zero encountered in double_scalars")

class VPINCalculator:
    """
    Calculates the Volume-synchronized Probability of Informed Trading (VPIN).
    
    VPIN is a metric for measuring order flow toxicity and detecting potential informed trading
    in financial markets. It is particularly useful for identifying periods of high information
    asymmetry and potential market stress.
    
    The VPIN calculation involves the following steps:
    1. Divide the trading day into equal volume buckets
    2. Classify trades as buys or sells using a bulk volume classification method
    3. Calculate the absolute imbalance between buy and sell volume for each bucket
    4. Compute the VPIN as the average of these imbalances over a rolling window
    
    Parameters
    ----------
    n_buckets : int, default=50
        Number of volume buckets per day.
    window_size : int, default=50
        Rolling window size for VPIN calculation.
    classification_method : str, default='bulk'
        Method for classifying trades as buys or sells.
        Options: 'bulk', 'tick', 'lee_ready'.
    sigma_multiplier : float, default=1.0
        Multiplier for standard deviation in bulk volume classification.
    time_bars : bool, default=False
        Whether to use time bars instead of volume bars.
    bar_size : Optional[str], default=None
        Size of time bars if time_bars=True. E.g., '1min', '5min', '1h'.
    """
    
    def __init__(
        self,
        n_buckets: int = 50,
        window_size: int = 50,
        classification_method: str = 'bulk',
        sigma_multiplier: float = 1.0,
        time_bars: bool = False,
        bar_size: Optional[str] = None
    ):
        """Initialize the VPINCalculator with the specified parameters."""
        self.n_buckets = n_buckets
        self.window_size = window_size
        self.classification_method = classification_method
        self.sigma_multiplier = sigma_multiplier
        self.time_bars = time_bars
        self.bar_size = bar_size
        
        # Validate parameters
        self._validate_parameters()
        
        # Initialize results
        self.bucket_data = None
        self.vpin_series = None
        self.cdf_series = None
        
        logger.info(f"VPINCalculator initialized with {n_buckets} buckets and window size {window_size}")
    
    def _validate_parameters(self):
        """Validate the parameters."""
        if self.n_buckets <= 0:
            raise ValueError("n_buckets must be positive")
        
        if self.window_size <= 0:
            raise ValueError("window_size must be positive")
        
        if self.classification_method not in ['bulk', 'tick', 'lee_ready']:
            raise ValueError("classification_method must be one of 'bulk', 'tick', 'lee_ready'")
        
        if self.sigma_multiplier <= 0:
            raise ValueError("sigma_multiplier must be positive")
        
        if self.time_bars and self.bar_size is None:
            raise ValueError("bar_size must be specified when time_bars=True")
    
    def _classify_trades_bulk(
        self,
        price_changes: np.ndarray,
        volumes: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Classify trades as buys or sells using the bulk volume classification method.
        
        This method uses price changes to estimate the probability of a trade being a buy or sell.
        It assumes that the probability is proportional to the standardized price change.
        
        Parameters
        ----------
        price_changes : np.ndarray
            Array of price changes.
        volumes : np.ndarray
            Array of volumes corresponding to price_changes.
            
        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            Arrays of buy and sell volumes.
        """
        # Calculate standardized price changes
        std_dev = np.std(price_changes) * self.sigma_multiplier
        if std_dev == 0:
            # If standard deviation is zero, classify all trades as neutral
            buy_volume = volumes * 0.5
            sell_volume = volumes * 0.5
        else:
            # Calculate probability of buy using cumulative normal distribution
            z_scores = price_changes / std_dev
            buy_prob = stats.norm.cdf(z_scores)
            
            # Calculate buy and sell volumes
            buy_volume = volumes * buy_prob
            sell_volume = volumes * (1 - buy_prob)
        
        return buy_volume, sell_volume
    
    def _classify_trades_tick(
        self,
        prices: np.ndarray,
        volumes: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Classify trades as buys or sells using the tick test method.
        
        This method classifies a trade as a buy if the price is higher than the previous price,
        and as a sell if the price is lower than the previous price.
        
        Parameters
        ----------
        prices : np.ndarray
            Array of prices.
        volumes : np.ndarray
            Array of volumes corresponding to prices.
            
        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            Arrays of buy and sell volumes.
        """
        # Calculate price changes
        price_changes = np.diff(prices, prepend=prices[0])
        
        # Classify trades
        buy_volume = np.zeros_like(volumes)
        sell_volume = np.zeros_like(volumes)
        
        # Trades with positive price change are buys
        buy_mask = price_changes > 0
        buy_volume[buy_mask] = volumes[buy_mask]
        
        # Trades with negative price change are sells
        sell_mask = price_changes < 0
        sell_volume[sell_mask] = volumes[sell_mask]
        
        # Trades with no price change are classified based on the previous trade
        zero_mask = price_changes == 0
        
        # Find the previous non-zero price change for each zero price change
        for i in np.where(zero_mask)[0]:
            if i == 0:
                # First trade with zero price change is classified as neutral
                buy_volume[i] = volumes[i] * 0.5
                sell_volume[i] = volumes[i] * 0.5
            else:
                # Find the last non-zero price change
                j = i - 1
                while j >= 0 and price_changes[j] == 0:
                    j -= 1
                
                if j < 0:
                    # No previous non-zero price change found, classify as neutral
                    buy_volume[i] = volumes[i] * 0.5
                    sell_volume[i] = volumes[i] * 0.5
                elif price_changes[j] > 0:
                    # Previous price change was positive, classify as buy
                    buy_volume[i] = volumes[i]
                else:
                    # Previous price change was negative, classify as sell
                    sell_volume[i] = volumes[i]
        
        return buy_volume, sell_volume
    
    def _classify_trades_lee_ready(
        self,
        prices: np.ndarray,
        volumes: np.ndarray,
        bid_prices: np.ndarray,
        ask_prices: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Classify trades as buys or sells using the Lee-Ready method.
        
        This method first uses the midpoint test (comparing the trade price to the bid-ask midpoint),
        and then falls back to the tick test for trades at the midpoint.
        
        Parameters
        ----------
        prices : np.ndarray
            Array of prices.
        volumes : np.ndarray
            Array of volumes corresponding to prices.
        bid_prices : np.ndarray
            Array of bid prices.
        ask_prices : np.ndarray
            Array of ask prices.
            
        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            Arrays of buy and sell volumes.
        """
        # Calculate midpoints
        midpoints = (bid_prices + ask_prices) / 2
        
        # Initialize buy and sell volumes
        buy_volume = np.zeros_like(volumes)
        sell_volume = np.zeros_like(volumes)
        
        # Classify trades using midpoint test
        above_midpoint = prices > midpoints
        below_midpoint = prices < midpoints
        at_midpoint = np.isclose(prices, midpoints)
        
        # Trades above midpoint are buys
        buy_volume[above_midpoint] = volumes[above_midpoint]
        
        # Trades below midpoint are sells
        sell_volume[below_midpoint] = volumes[below_midpoint]
        
        # For trades at midpoint, use tick test
        if np.any(at_midpoint):
            # Calculate price changes
            price_changes = np.diff(prices, prepend=prices[0])
            
            # Trades at midpoint with positive price change are buys
            midpoint_buys = at_midpoint & (price_changes > 0)
            buy_volume[midpoint_buys] = volumes[midpoint_buys]
            
            # Trades at midpoint with negative price change are sells
            midpoint_sells = at_midpoint & (price_changes < 0)
            sell_volume[midpoint_sells] = volumes[midpoint_sells]
            
            # Trades at midpoint with no price change are classified as neutral
            midpoint_neutral = at_midpoint & (price_changes == 0)
            buy_volume[midpoint_neutral] = volumes[midpoint_neutral] * 0.5
            sell_volume[midpoint_neutral] = volumes[midpoint_neutral] * 0.5
        
        return buy_volume, sell_volume
    
    def _create_time_bars(
        self,
        data: pd.DataFrame,
        bar_size: str
    ) -> pd.DataFrame:
        """
        Create time bars from tick data.
        
        Parameters
        ----------
        data : pd.DataFrame
            DataFrame with tick data. Must have a DatetimeIndex and 'price' and 'volume' columns.
        bar_size : str
            Size of time bars. E.g., '1min', '5min', '1h'.
            
        Returns
        -------
        pd.DataFrame
            DataFrame with time bars.
        """
        # Ensure data has a DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have a DatetimeIndex")
        
        # Ensure data has 'price' and 'volume' columns
        if 'price' not in data.columns or 'volume' not in data.columns:
            raise ValueError("Data must have 'price' and 'volume' columns")
        
        # Resample data to create time bars
        ohlcv = data.resample(bar_size).agg({
            'price': 'ohlc',
            'volume': 'sum'
        })
        
        # Flatten the MultiIndex columns
        ohlcv.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Use close price as the price for the bar
        ohlcv['price'] = ohlcv['close']
        
        return ohlcv
    
    def _create_volume_buckets(
        self,
        data: pd.DataFrame,
        n_buckets: int
    ) -> pd.DataFrame:
        """
        Create volume buckets from bar data.
        
        Parameters
        ----------
        data : pd.DataFrame
            DataFrame with bar data. Must have 'price' and 'volume' columns.
        n_buckets : int
            Number of volume buckets to create.
            
        Returns
        -------
        pd.DataFrame
            DataFrame with volume buckets.
        """
        # Ensure data has 'price' and 'volume' columns
        if 'price' not in data.columns or 'volume' not in data.columns:
            raise ValueError("Data must have 'price' and 'volume' columns")
        
        # Calculate total volume
        total_volume = data['volume'].sum()
        
        # Calculate target volume per bucket
        target_volume = total_volume / n_buckets
        
        # Initialize buckets
        buckets = []
        current_bucket = {
            'start_time': data.index[0],
            'end_time': None,
            'volume': 0,
            'price': [],
            'bucket_volume': []
        }
        
        # Fill buckets
        for time, row in data.iterrows():
            # If adding this bar would exceed the target volume, finalize the current bucket
            if current_bucket['volume'] + row['volume'] > target_volume and current_bucket['volume'] > 0:
                # Calculate the fraction of this bar's volume to include
                remaining_volume = target_volume - current_bucket['volume']
                fraction = remaining_volume / row['volume']
                
                # Add the fraction to the current bucket
                current_bucket['volume'] += remaining_volume
                current_bucket['price'].append(row['price'])
                current_bucket['bucket_volume'].append(remaining_volume)
                current_bucket['end_time'] = time
                
                # Finalize the current bucket
                buckets.append(current_bucket)
                
                # Start a new bucket with the remaining volume
                current_bucket = {
                    'start_time': time,
                    'end_time': None,
                    'volume': row['volume'] - remaining_volume,
                    'price': [row['price']],
                    'bucket_volume': [row['volume'] - remaining_volume]
                }
            else:
                # Add the entire bar to the current bucket
                current_bucket['volume'] += row['volume']
                current_bucket['price'].append(row['price'])
                current_bucket['bucket_volume'].append(row['volume'])
                current_bucket['end_time'] = time
        
        # Add the last bucket if it has any volume
        if current_bucket['volume'] > 0:
            buckets.append(current_bucket)
        
        # Convert buckets to DataFrame
        bucket_df = pd.DataFrame([
            {
                'start_time': b['start_time'],
                'end_time': b['end_time'],
                'volume': b['volume'],
                'price': np.average(b['price'], weights=b['bucket_volume']),
                'price_change': np.nan  # Will be calculated next
            }
            for b in buckets
        ])
        
        # Calculate price changes
        bucket_df['price_change'] = bucket_df['price'].diff().fillna(0)
        
        # Set index to end_time
        bucket_df.set_index('end_time', inplace=True)
        
        return bucket_df
    
    def calculate_vpin(
        self,
        data: pd.DataFrame,
        bid_data: Optional[pd.DataFrame] = None,
        ask_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Calculate VPIN from market data.
        
        Parameters
        ----------
        data : pd.DataFrame
            DataFrame with market data. Must have 'price' and 'volume' columns.
            If using time bars, must have a DatetimeIndex.
        bid_data : pd.DataFrame, optional
            DataFrame with bid prices. Required if classification_method='lee_ready'.
        ask_data : pd.DataFrame, optional
            DataFrame with ask prices. Required if classification_method='lee_ready'.
            
        Returns
        -------
        pd.DataFrame
            DataFrame with VPIN and related metrics.
        """
        # Validate inputs
        if 'price' not in data.columns or 'volume' not in data.columns:
            raise ValueError("Data must have 'price' and 'volume' columns")
        
        if self.classification_method == 'lee_ready':
            if bid_data is None or ask_data is None:
                raise ValueError("bid_data and ask_data are required for lee_ready classification")
        
        # Create time bars if needed
        if self.time_bars:
            logger.info(f"Creating time bars with bar_size={self.bar_size}")
            bars = self._create_time_bars(data, self.bar_size)
        else:
            bars = data.copy()
        
        # Create volume buckets
        logger.info(f"Creating {self.n_buckets} volume buckets")
        buckets = self._create_volume_buckets(bars, self.n_buckets)
        
        # Classify trades
        logger.info(f"Classifying trades using {self.classification_method} method")
        if self.classification_method == 'bulk':
            buy_volume, sell_volume = self._classify_trades_bulk(
                buckets['price_change'].values,
                buckets['volume'].values
            )
        elif self.classification_method == 'tick':
            buy_volume, sell_volume = self._classify_trades_tick(
                buckets['price'].values,
                buckets['volume'].values
            )
        elif self.classification_method == 'lee_ready':
            # Align bid and ask data with bucket end times
            bid_aligned = bid_data.reindex(buckets.index, method='ffill')
            ask_aligned = ask_data.reindex(buckets.index, method='ffill')
            
            buy_volume, sell_volume = self._classify_trades_lee_ready(
                buckets['price'].values,
                buckets['volume'].values,
                bid_aligned.values,
                ask_aligned.values
            )
        
        # Add buy and sell volumes to buckets
        buckets['buy_volume'] = buy_volume
        buckets['sell_volume'] = sell_volume
        
        # Calculate volume imbalance
        buckets['imbalance'] = np.abs(buy_volume - sell_volume) / buckets['volume']
        
        # Calculate VPIN
        logger.info(f"Calculating VPIN with window_size={self.window_size}")
        vpin = buckets['imbalance'].rolling(window=self.window_size).mean()
        buckets['vpin'] = vpin
        
        # Calculate CDF of VPIN
        logger.info("Calculating CDF of VPIN")
        # Use expanding window to calculate CDF
        vpin_mean = vpin.expanding().mean()
        vpin_std = vpin.expanding().std()
        
        # Handle case where std is 0 (e.g., at the beginning)
        vpin_std = vpin_std.replace(0, np.nan)
        
        # Calculate CDF
        cdf = pd.Series(index=vpin.index)
        mask = ~vpin_std.isna()
        cdf[mask] = stats.norm.cdf((vpin[mask] - vpin_mean[mask]) / vpin_std[mask])
        buckets['vpin_cdf'] = cdf
        
        # Store results
        self.bucket_data = buckets
        self.vpin_series = vpin
        self.cdf_series = cdf
        
        return buckets
    
    def detect_toxic_events(
        self,
        threshold: float = 0.99,
        min_gap: int = 10
    ) -> List[pd.Timestamp]:
        """
        Detect toxic events based on VPIN CDF.
        
        Parameters
        ----------
        threshold : float, default=0.99
            Threshold for VPIN CDF to identify toxic events.
        min_gap : int, default=10
            Minimum number of buckets between toxic events.
            
        Returns
        -------
        List[pd.Timestamp]
            List of timestamps for toxic events.
        """
        if self.cdf_series is None:
            raise ValueError("VPIN not calculated. Call calculate_vpin first.")
        
        # Find buckets where CDF exceeds threshold
        toxic_mask = self.cdf_series > threshold
        
        if not np.any(toxic_mask):
            logger.info(f"No toxic events found with threshold {threshold}")
            return []
        
        # Get indices of toxic buckets
        toxic_indices = np.where(toxic_mask)[0]
        
        # Filter out toxic events that are too close to each other
        filtered_indices = [toxic_indices[0]]
        for idx in toxic_indices[1:]:
            if idx - filtered_indices[-1] >= min_gap:
                filtered_indices.append(idx)
        
        # Convert indices to timestamps
        toxic_events = [self.cdf_series.index[idx] for idx in filtered_indices]
        
        logger.info(f"Detected {len(toxic_events)} toxic events with threshold {threshold}")
        
        return toxic_events
    
    def calculate_vpin_metrics(self) -> Dict[str, float]:
        """
        Calculate various metrics related to VPIN.
        
        Returns
        -------
        Dict[str, float]
            Dictionary of VPIN metrics.
        """
        if self.vpin_series is None:
            raise ValueError("VPIN not calculated. Call calculate_vpin first.")
        
        # Calculate metrics
        metrics = {
            'mean': self.vpin_series.mean(),
            'median': self.vpin_series.median(),
            'std': self.vpin_series.std(),
            'min': self.vpin_series.min(),
            'max': self.vpin_series.max(),
            'q25': self.vpin_series.quantile(0.25),
            'q75': self.vpin_series.quantile(0.75),
            'skew': self.vpin_series.skew(),
            'kurtosis': self.vpin_series.kurtosis(),
            'toxic_periods': (self.cdf_series > 0.99).mean() if self.cdf_series is not None else None
        }
        
        return metrics
    
    def plot_vpin(
        self,
        figsize: Tuple[int, int] = (12, 8),
        title: str = 'VPIN Analysis',
        highlight_toxic: bool = True,
        toxic_threshold: float = 0.99,
        price_data: Optional[pd.Series] = None,
        save_path: Optional[str] = None
    ):
        """
        Plot VPIN and related metrics.
        
        Parameters
        ----------
        figsize : Tuple[int, int], default=(12, 8)
            Figure size.
        title : str, default='VPIN Analysis'
            Plot title.
        highlight_toxic : bool, default=True
            Whether to highlight toxic events.
        toxic_threshold : float, default=0.99
            Threshold for VPIN CDF to identify toxic events.
        price_data : pd.Series, optional
            Price data to plot alongside VPIN.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        if self.vpin_series is None or self.cdf_series is None:
            raise ValueError("VPIN not calculated. Call calculate_vpin first.")
        
        # Create figure
        fig = plt.figure(figsize=figsize)
        
        if price_data is not None:
            # Create 3 subplots
            gs = fig.add_gridspec(3, 1, height_ratios=[2, 1, 1])
            ax1 = fig.add_subplot(gs[0])
            ax2 = fig.add_subplot(gs[1], sharex=ax1)
            ax3 = fig.add_subplot(gs[2], sharex=ax1)
            
            # Plot price
            price_aligned = price_data.reindex(self.bucket_data.index, method='ffill')
            ax1.plot(price_aligned.index, price_aligned.values, 'b-')
            ax1.set_ylabel('Price')
            ax1.set_title('Price')
            ax1.grid(True, alpha=0.3)
            
            # Highlight toxic events on price chart
            if highlight_toxic:
                toxic_events = self.detect_toxic_events(threshold=toxic_threshold)
                for event in toxic_events:
                    ax1.axvline(x=event, color='r', linestyle='--', alpha=0.5)
            
            # Plot VPIN
            ax2.plot(self.vpin_series.index, self.vpin_series.values, 'g-')
            ax2.set_ylabel('VPIN')
            ax2.set_title('Volume-synchronized Probability of Informed Trading (VPIN)')
            ax2.grid(True, alpha=0.3)
            
            # Plot VPIN CDF
            ax3.plot(self.cdf_series.index, self.cdf_series.values, 'r-')
            ax3.set_ylabel('CDF')
            ax3.set_title('VPIN CDF')
            ax3.grid(True, alpha=0.3)
            
            # Add threshold line
            if highlight_toxic:
                ax3.axhline(y=toxic_threshold, color='r', linestyle='--', 
                           label=f'Threshold: {toxic_threshold}')
                ax3.legend()
            
            ax3.set_xlabel('Time')
        else:
            # Create 2 subplots
            gs = fig.add_gridspec(2, 1)
            ax2 = fig.add_subplot(gs[0])
            ax3 = fig.add_subplot(gs[1], sharex=ax2)
            
            # Plot VPIN
            ax2.plot(self.vpin_series.index, self.vpin_series.values, 'g-')
            ax2.set_ylabel('VPIN')
            ax2.set_title('Volume-synchronized Probability of Informed Trading (VPIN)')
            ax2.grid(True, alpha=0.3)
            
            # Plot VPIN CDF
            ax3.plot(self.cdf_series.index, self.cdf_series.values, 'r-')
            ax3.set_ylabel('CDF')
            ax3.set_title('VPIN CDF')
            ax3.grid(True, alpha=0.3)
            
            # Add threshold line
            if highlight_toxic:
                ax3.axhline(y=toxic_threshold, color='r', linestyle='--', 
                           label=f'Threshold: {toxic_threshold}')
                ax3.legend()
            
            ax3.set_xlabel('Time')
        
        plt.suptitle(title)
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved VPIN plot to {save_path}")
        
        plt.show()
    
    def plot_buy_sell_imbalance(
        self,
        figsize: Tuple[int, int] = (12, 6),
        title: str = 'Buy/Sell Volume Imbalance',
        save_path: Optional[str] = None
    ):
        """
        Plot buy/sell volume imbalance.
        
        Parameters
        ----------
        figsize : Tuple[int, int], default=(12, 6)
            Figure size.
        title : str, default='Buy/Sell Volume Imbalance'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        if self.bucket_data is None:
            raise ValueError("VPIN not calculated. Call calculate_vpin first.")
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Plot buy and sell volumes
        plt.bar(self.bucket_data.index, self.bucket_data['buy_volume'], 
               width=0.4, align='edge', color='g', alpha=0.7, label='Buy Volume')
        plt.bar(self.bucket_data.index, -self.bucket_data['sell_volume'], 
               width=0.4, align='edge', color='r', alpha=0.7, label='Sell Volume')
        
        plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        
        plt.xlabel('Time')
        plt.ylabel('Volume')
        plt.title(title)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved buy/sell imbalance plot to {save_path}")
        
        plt.show()
    
    def plot_vpin_distribution(
        self,
        figsize: Tuple[int, int] = (10, 6),
        title: str = 'VPIN Distribution',
        save_path: Optional[str] = None
    ):
        """
        Plot the distribution of VPIN values.
        
        Parameters
        ----------
        figsize : Tuple[int, int], default=(10, 6)
            Figure size.
        title : str, default='VPIN Distribution'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        if self.vpin_series is None:
            raise ValueError("VPIN not calculated. Call calculate_vpin first.")
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Plot histogram
        plt.hist(self.vpin_series.dropna(), bins=50, alpha=0.7, color='g')
        
        # Add vertical lines for key statistics
        plt.axvline(x=self.vpin_series.mean(), color='r', linestyle='--', 
                   label=f'Mean: {self.vpin_series.mean():.4f}')
        plt.axvline(x=self.vpin_series.median(), color='b', linestyle='--', 
                   label=f'Median: {self.vpin_series.median():.4f}')
        
        plt.xlabel('VPIN')
        plt.ylabel('Frequency')
        plt.title(title)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved VPIN distribution plot to {save_path}")
        
        plt.show()
    
    def get_vpin_features(self) -> Dict[str, float]:
        """
        Extract VPIN features for use in machine learning models.
        
        Returns
        -------
        Dict[str, float]
            Dictionary of VPIN features.
        """
        if self.vpin_series is None:
            raise ValueError("VPIN not calculated. Call calculate_vpin first.")
        
        # Calculate features
        features = {
            'vpin_current': self.vpin_series.iloc[-1],
            'vpin_mean': self.vpin_series.mean(),
            'vpin_std': self.vpin_series.std(),
            'vpin_zscore': (self.vpin_series.iloc[-1] - self.vpin_series.mean()) / self.vpin_series.std(),
            'vpin_percentile': stats.percentileofscore(self.vpin_series.dropna(), self.vpin_series.iloc[-1]) / 100,
            'vpin_cdf': self.cdf_series.iloc[-1] if self.cdf_series is not None else None,
            'vpin_is_toxic': self.cdf_series.iloc[-1] > 0.99 if self.cdf_series is not None else None,
            'buy_sell_ratio': (self.bucket_data['buy_volume'].iloc[-1] / 
                              self.bucket_data['sell_volume'].iloc[-1]) if self.bucket_data is not None else None,
            'imbalance': self.bucket_data['imbalance'].iloc[-1] if self.bucket_data is not None else None
        }
        
        return features 

class VPIN:
    """
    Simplified interface for calculating and analyzing VPIN.
    
    This class provides a more user-friendly interface for the VPINCalculator,
    with sensible defaults and simplified methods for common use cases.
    
    Parameters
    ----------
    n_buckets : int, default=50
        Number of volume buckets per day.
    window_size : int, default=50
        Rolling window size for VPIN calculation.
    classification_method : str, default='bulk'
        Method for classifying trades as buys or sells.
        Options: 'bulk', 'tick', 'lee_ready'.
    """
    
    def __init__(
        self,
        n_buckets: int = 50,
        window_size: int = 50,
        classification_method: str = 'bulk'
    ):
        """Initialize the VPIN with the specified parameters."""
        self.calculator = VPINCalculator(
            n_buckets=n_buckets,
            window_size=window_size,
            classification_method=classification_method
        )
    
    def calculate(
        self,
        data: pd.DataFrame,
        bid_data: Optional[pd.DataFrame] = None,
        ask_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Calculate VPIN from market data.
        
        Parameters
        ----------
        data : pd.DataFrame
            DataFrame with market data. Must have 'price' and 'volume' columns.
        bid_data : pd.DataFrame, optional
            DataFrame with bid prices. Required if classification_method='lee_ready'.
        ask_data : pd.DataFrame, optional
            DataFrame with ask prices. Required if classification_method='lee_ready'.
            
        Returns
        -------
        pd.DataFrame
            DataFrame with VPIN and related metrics.
        """
        return self.calculator.calculate_vpin(data, bid_data, ask_data)
    
    def plot(
        self,
        price_data: Optional[pd.Series] = None,
        highlight_toxic: bool = True,
        figsize: Tuple[int, int] = (12, 8)
    ):
        """
        Plot VPIN and related metrics.
        
        Parameters
        ----------
        price_data : pd.Series, optional
            Price data to plot alongside VPIN.
        highlight_toxic : bool, default=True
            Whether to highlight toxic events.
        figsize : Tuple[int, int], default=(12, 8)
            Figure size.
        """
        self.calculator.plot_vpin(
            figsize=figsize,
            highlight_toxic=highlight_toxic,
            price_data=price_data
        )
    
    def detect_toxic_events(
        self,
        threshold: float = 0.99
    ) -> List[pd.Timestamp]:
        """
        Detect toxic events based on VPIN CDF.
        
        Parameters
        ----------
        threshold : float, default=0.99
            Threshold for VPIN CDF to identify toxic events.
            
        Returns
        -------
        List[pd.Timestamp]
            List of timestamps for toxic events.
        """
        return self.calculator.detect_toxic_events(threshold=threshold)
    
    def get_metrics(self) -> Dict[str, float]:
        """
        Calculate various metrics related to VPIN.
        
        Returns
        -------
        Dict[str, float]
            Dictionary of VPIN metrics.
        """
        return self.calculator.calculate_vpin_metrics()
    
    def get_features(self) -> Dict[str, float]:
        """
        Extract VPIN features for use in machine learning models.
        
        Returns
        -------
        Dict[str, float]
            Dictionary of VPIN features.
        """
        return self.calculator.get_vpin_features()
    
    @property
    def vpin(self) -> pd.Series:
        """Get the VPIN series."""
        if self.calculator.vpin_series is None:
            raise ValueError("VPIN not calculated. Call calculate first.")
        return self.calculator.vpin_series
    
    @property
    def cdf(self) -> pd.Series:
        """Get the VPIN CDF series."""
        if self.calculator.cdf_series is None:
            raise ValueError("VPIN not calculated. Call calculate first.")
        return self.calculator.cdf_series
    
    @property
    def buckets(self) -> pd.DataFrame:
        """Get the bucket data."""
        if self.calculator.bucket_data is None:
            raise ValueError("VPIN not calculated. Call calculate first.")
        return self.calculator.bucket_data 