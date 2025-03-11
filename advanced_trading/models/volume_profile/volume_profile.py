#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Volume Profile Analysis for Financial Markets.

This module provides tools for analyzing the distribution of trading volume
across different price levels, which is essential for understanding market
structure, identifying support/resistance levels, and optimizing trade execution.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import logging

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class PriceLevel:
    """
    Represents a price level in a volume profile.
    
    Attributes
    ----------
    price : float
        The price level.
    volume : float
        The volume traded at this price level.
    buy_volume : float
        The buy volume at this price level.
    sell_volume : float
        The sell volume at this price level.
    trades : int
        The number of trades at this price level.
    """
    price: float
    volume: float
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    trades: int = 0
    
    @property
    def buy_sell_ratio(self) -> float:
        """Calculate the buy/sell ratio at this price level."""
        if self.sell_volume == 0:
            return float('inf')
        return self.buy_volume / self.sell_volume
    
    @property
    def average_trade_size(self) -> float:
        """Calculate the average trade size at this price level."""
        if self.trades == 0:
            return 0.0
        return self.volume / self.trades


class VolumeProfile:
    """
    Analyzes the distribution of trading volume across price levels.
    
    This class provides tools for constructing and analyzing volume profiles,
    which show how trading volume is distributed across different price levels.
    Volume profiles can be used to identify support and resistance levels,
    understand market structure, and optimize trade execution.
    
    Parameters
    ----------
    price_data : pd.DataFrame or pd.Series
        Price data for analysis. If a DataFrame, must contain columns for price and volume.
        If a Series, represents price data and volume_data must be provided.
    volume_data : pd.Series, optional
        Volume data corresponding to price_data. Required if price_data is a Series.
    n_bins : int, optional
        Number of price bins to use for the volume profile. Default is 100.
    price_range : Tuple[float, float], optional
        Price range to consider for the volume profile. If None, uses the min and max prices.
    time_index : pd.DatetimeIndex, optional
        Time index for the data. If None and price_data has a DatetimeIndex, uses that.
    """
    
    def __init__(
        self,
        price_data: Union[pd.DataFrame, pd.Series],
        volume_data: Optional[pd.Series] = None,
        n_bins: int = 100,
        price_range: Optional[Tuple[float, float]] = None,
        time_index: Optional[pd.DatetimeIndex] = None
    ):
        """Initialize the VolumeProfile with price and volume data."""
        self.n_bins = n_bins
        self.time_index = None
        
        # Process input data
        if isinstance(price_data, pd.DataFrame):
            if 'price' in price_data.columns and 'volume' in price_data.columns:
                self.price = price_data['price'].values
                self.volume = price_data['volume'].values
                if time_index is None and isinstance(price_data.index, pd.DatetimeIndex):
                    self.time_index = price_data.index
                else:
                    self.time_index = time_index
            else:
                raise ValueError("DataFrame must contain 'price' and 'volume' columns")
        elif isinstance(price_data, pd.Series):
            if volume_data is None:
                raise ValueError("volume_data must be provided when price_data is a Series")
            self.price = price_data.values
            self.volume = volume_data.values
            if time_index is None and isinstance(price_data.index, pd.DatetimeIndex):
                self.time_index = price_data.index
            else:
                self.time_index = time_index
        else:
            raise ValueError("price_data must be a DataFrame or Series")
        
        # Set price range
        if price_range is None:
            self.price_min = np.min(self.price)
            self.price_max = np.max(self.price)
        else:
            self.price_min, self.price_max = price_range
        
        # Initialize profile data
        self.bins = np.linspace(self.price_min, self.price_max, n_bins + 1)
        self.bin_centers = (self.bins[:-1] + self.bins[1:]) / 2
        self.profile = None
        self.value_area = None
        self.point_of_control = None
        
        # Calculate the volume profile
        self._calculate_profile()
    
    def _calculate_profile(self):
        """Calculate the volume profile."""
        # Calculate histogram
        hist, _ = np.histogram(self.price, bins=self.bins, weights=self.volume)
        
        # Create profile data
        self.profile = pd.DataFrame({
            'price': self.bin_centers,
            'volume': hist
        })
        
        # Find point of control (price level with highest volume)
        poc_idx = np.argmax(hist)
        self.point_of_control = self.bin_centers[poc_idx]
        
        # Calculate value area (70% of volume)
        total_volume = np.sum(hist)
        value_area_volume = 0.7 * total_volume
        
        # Sort bins by volume (descending)
        sorted_idx = np.argsort(hist)[::-1]
        cumulative_volume = 0
        value_area_idx = []
        
        for idx in sorted_idx:
            value_area_idx.append(idx)
            cumulative_volume += hist[idx]
            if cumulative_volume >= value_area_volume:
                break
        
        # Get min and max price in value area
        min_idx = np.min(value_area_idx)
        max_idx = np.max(value_area_idx)
        self.value_area = (self.bin_centers[min_idx], self.bin_centers[max_idx])
        
        logger.info(f"Volume profile calculated with {self.n_bins} bins")
        logger.info(f"Point of control: {self.point_of_control}")
        logger.info(f"Value area: {self.value_area}")
    
    def get_profile(self) -> pd.DataFrame:
        """
        Get the volume profile as a DataFrame.
        
        Returns
        -------
        pd.DataFrame
            DataFrame with price and volume columns.
        """
        return self.profile.copy()
    
    def get_point_of_control(self) -> float:
        """
        Get the point of control (price level with highest volume).
        
        Returns
        -------
        float
            Price level with the highest volume.
        """
        return self.point_of_control
    
    def get_value_area(self) -> Tuple[float, float]:
        """
        Get the value area (price range containing 70% of volume).
        
        Returns
        -------
        Tuple[float, float]
            Minimum and maximum price of the value area.
        """
        return self.value_area
    
    def get_volume_at_price(self, price: float) -> float:
        """
        Get the volume at a specific price level.
        
        Parameters
        ----------
        price : float
            Price level to query.
            
        Returns
        -------
        float
            Volume at the specified price level.
        """
        if price < self.price_min or price > self.price_max:
            return 0.0
        
        # Find the closest bin
        bin_idx = np.argmin(np.abs(self.bin_centers - price))
        return self.profile.iloc[bin_idx]['volume']
    
    def get_high_volume_nodes(self, threshold: float = 0.8) -> List[float]:
        """
        Get high volume nodes (price levels with volume above threshold * max volume).
        
        Parameters
        ----------
        threshold : float, default=0.8
            Threshold as a fraction of the maximum volume.
            
        Returns
        -------
        List[float]
            List of price levels with high volume.
        """
        max_volume = self.profile['volume'].max()
        threshold_volume = threshold * max_volume
        high_volume = self.profile[self.profile['volume'] >= threshold_volume]
        return high_volume['price'].tolist()
    
    def get_low_volume_nodes(self, threshold: float = 0.2) -> List[float]:
        """
        Get low volume nodes (price levels with volume below threshold * max volume).
        
        Parameters
        ----------
        threshold : float, default=0.2
            Threshold as a fraction of the maximum volume.
            
        Returns
        -------
        List[float]
            List of price levels with low volume.
        """
        max_volume = self.profile['volume'].max()
        threshold_volume = threshold * max_volume
        low_volume = self.profile[self.profile['volume'] <= threshold_volume]
        return low_volume['price'].tolist()
    
    def plot_profile(
        self,
        figsize: Tuple[int, int] = (10, 6),
        color: str = 'blue',
        alpha: float = 0.7,
        show_poc: bool = True,
        show_value_area: bool = True,
        horizontal: bool = True,
        title: str = 'Volume Profile',
        save_path: Optional[str] = None
    ):
        """
        Plot the volume profile.
        
        Parameters
        ----------
        figsize : Tuple[int, int], default=(10, 6)
            Figure size.
        color : str, default='blue'
            Color for the volume bars.
        alpha : float, default=0.7
            Transparency for the volume bars.
        show_poc : bool, default=True
            Whether to highlight the point of control.
        show_value_area : bool, default=True
            Whether to highlight the value area.
        horizontal : bool, default=True
            Whether to plot the profile horizontally (price on y-axis).
        title : str, default='Volume Profile'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        plt.figure(figsize=figsize)
        
        if horizontal:
            # Horizontal profile (price on y-axis)
            plt.barh(self.profile['price'], self.profile['volume'], 
                    height=(self.price_max - self.price_min) / self.n_bins,
                    color=color, alpha=alpha)
            
            if show_poc:
                plt.axhline(y=self.point_of_control, color='red', linestyle='--', 
                           label=f'POC: {self.point_of_control:.2f}')
            
            if show_value_area:
                plt.axhspan(self.value_area[0], self.value_area[1], color='green', alpha=0.2,
                           label=f'Value Area: {self.value_area[0]:.2f} - {self.value_area[1]:.2f}')
            
            plt.ylabel('Price')
            plt.xlabel('Volume')
        else:
            # Vertical profile (price on x-axis)
            plt.bar(self.profile['price'], self.profile['volume'], 
                   width=(self.price_max - self.price_min) / self.n_bins,
                   color=color, alpha=alpha)
            
            if show_poc:
                plt.axvline(x=self.point_of_control, color='red', linestyle='--', 
                           label=f'POC: {self.point_of_control:.2f}')
            
            if show_value_area:
                plt.axvspan(self.value_area[0], self.value_area[1], color='green', alpha=0.2,
                           label=f'Value Area: {self.value_area[0]:.2f} - {self.value_area[1]:.2f}')
            
            plt.xlabel('Price')
            plt.ylabel('Volume')
        
        plt.title(title)
        plt.grid(True, alpha=0.3)
        
        if show_poc or show_value_area:
            plt.legend()
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved volume profile plot to {save_path}")
        
        plt.show()
    
    def plot_profile_with_price(
        self,
        price_data: pd.Series,
        figsize: Tuple[int, int] = (12, 8),
        profile_width: float = 0.3,
        profile_color: str = 'blue',
        price_color: str = 'black',
        show_poc: bool = True,
        show_value_area: bool = True,
        title: str = 'Price with Volume Profile',
        save_path: Optional[str] = None
    ):
        """
        Plot the price chart with volume profile on the right.
        
        Parameters
        ----------
        price_data : pd.Series
            Price data to plot.
        figsize : Tuple[int, int], default=(12, 8)
            Figure size.
        profile_width : float, default=0.3
            Width of the volume profile as a fraction of the plot.
        profile_color : str, default='blue'
            Color for the volume profile.
        price_color : str, default='black'
            Color for the price line.
        show_poc : bool, default=True
            Whether to highlight the point of control.
        show_value_area : bool, default=True
            Whether to highlight the value area.
        title : str, default='Price with Volume Profile'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        fig, ax1 = plt.subplots(figsize=figsize)
        
        # Plot price
        ax1.plot(price_data.index, price_data.values, color=price_color, linewidth=1)
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Price', color=price_color)
        ax1.tick_params(axis='y', labelcolor=price_color)
        
        # Create a second y-axis for the volume profile
        ax2 = ax1.twinx()
        
        # Calculate max volume for scaling
        max_volume = self.profile['volume'].max()
        
        # Plot volume profile horizontally
        ax2.barh(self.profile['price'], self.profile['volume'] / max_volume * profile_width,
                height=(self.price_max - self.price_min) / self.n_bins,
                color=profile_color, alpha=0.7)
        
        # Hide the y-axis labels for the volume profile
        ax2.set_yticks([])
        ax2.set_yticklabels([])
        
        # Set the x-axis limits to make the profile a specific width
        x_min, x_max = ax1.get_xlim()
        ax2.set_xlim(0, profile_width)
        
        # Add POC and Value Area
        if show_poc:
            ax1.axhline(y=self.point_of_control, color='red', linestyle='--', 
                       label=f'POC: {self.point_of_control:.2f}')
        
        if show_value_area:
            ax1.axhspan(self.value_area[0], self.value_area[1], color='green', alpha=0.1,
                       label=f'Value Area: {self.value_area[0]:.2f} - {self.value_area[1]:.2f}')
        
        plt.title(title)
        
        if show_poc or show_value_area:
            ax1.legend(loc='upper left')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved price with volume profile plot to {save_path}")
        
        plt.show()
    
    def identify_support_resistance(
        self, 
        volume_threshold: float = 0.7,
        cluster_distance: float = None
    ) -> Dict[str, List[float]]:
        """
        Identify support and resistance levels based on volume profile.
        
        Parameters
        ----------
        volume_threshold : float, default=0.7
            Threshold as a fraction of the maximum volume to identify high volume nodes.
        cluster_distance : float, optional
            Distance to cluster nearby levels. If None, uses (price_max - price_min) / (n_bins * 2).
            
        Returns
        -------
        Dict[str, List[float]]
            Dictionary with 'support' and 'resistance' levels.
        """
        if cluster_distance is None:
            cluster_distance = (self.price_max - self.price_min) / (self.n_bins * 2)
        
        # Get high volume nodes
        high_volume_levels = self.get_high_volume_nodes(threshold=volume_threshold)
        
        # Cluster nearby levels
        clustered_levels = []
        current_cluster = [high_volume_levels[0]]
        
        for level in high_volume_levels[1:]:
            if level - current_cluster[-1] <= cluster_distance:
                current_cluster.append(level)
            else:
                # Add the average of the current cluster
                clustered_levels.append(np.mean(current_cluster))
                current_cluster = [level]
        
        # Add the last cluster
        if current_cluster:
            clustered_levels.append(np.mean(current_cluster))
        
        # Separate into support and resistance
        mid_price = (self.price_min + self.price_max) / 2
        support = [level for level in clustered_levels if level < mid_price]
        resistance = [level for level in clustered_levels if level >= mid_price]
        
        return {
            'support': support,
            'resistance': resistance
        }
    
    def calculate_volume_delta(
        self,
        buy_volume: pd.Series,
        sell_volume: pd.Series
    ) -> pd.DataFrame:
        """
        Calculate volume delta (buy volume - sell volume) across price levels.
        
        Parameters
        ----------
        buy_volume : pd.Series
            Buy volume data corresponding to self.price.
        sell_volume : pd.Series
            Sell volume data corresponding to self.price.
            
        Returns
        -------
        pd.DataFrame
            DataFrame with price, buy_volume, sell_volume, and delta columns.
        """
        if len(buy_volume) != len(self.price) or len(sell_volume) != len(self.price):
            raise ValueError("buy_volume and sell_volume must have the same length as price data")
        
        # Calculate histograms
        buy_hist, _ = np.histogram(self.price, bins=self.bins, weights=buy_volume.values)
        sell_hist, _ = np.histogram(self.price, bins=self.bins, weights=sell_volume.values)
        
        # Create delta profile
        delta_profile = pd.DataFrame({
            'price': self.bin_centers,
            'buy_volume': buy_hist,
            'sell_volume': sell_hist,
            'delta': buy_hist - sell_hist
        })
        
        return delta_profile
    
    def plot_volume_delta(
        self,
        delta_profile: pd.DataFrame,
        figsize: Tuple[int, int] = (10, 6),
        title: str = 'Volume Delta Profile',
        save_path: Optional[str] = None
    ):
        """
        Plot the volume delta profile.
        
        Parameters
        ----------
        delta_profile : pd.DataFrame
            DataFrame with price and delta columns, as returned by calculate_volume_delta.
        figsize : Tuple[int, int], default=(10, 6)
            Figure size.
        title : str, default='Volume Delta Profile'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        plt.figure(figsize=figsize)
        
        # Plot delta
        plt.bar(delta_profile['price'], delta_profile['delta'], 
               width=(self.price_max - self.price_min) / self.n_bins,
               color=np.where(delta_profile['delta'] >= 0, 'green', 'red'),
               alpha=0.7)
        
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        plt.xlabel('Price')
        plt.ylabel('Volume Delta (Buy - Sell)')
        plt.title(title)
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved volume delta plot to {save_path}")
        
        plt.show()
    
    def get_volume_profile_features(self) -> Dict[str, float]:
        """
        Extract features from the volume profile for use in machine learning models.
        
        Returns
        -------
        Dict[str, float]
            Dictionary of features extracted from the volume profile.
        """
        # Calculate various metrics
        total_volume = self.profile['volume'].sum()
        max_volume = self.profile['volume'].max()
        volume_std = self.profile['volume'].std()
        
        # Calculate volume concentration (Gini coefficient)
        sorted_volume = np.sort(self.profile['volume'].values)
        n = len(sorted_volume)
        index = np.arange(1, n + 1)
        gini = 1 - 2 * np.sum((n + 1 - index) * sorted_volume) / (n * np.sum(sorted_volume))
        
        # Calculate distance from current price to POC
        if self.time_index is not None:
            current_price = self.price[-1]
            distance_to_poc = abs(current_price - self.point_of_control) / current_price
        else:
            distance_to_poc = None
        
        # Calculate volume in value area
        value_area_mask = (self.profile['price'] >= self.value_area[0]) & (self.profile['price'] <= self.value_area[1])
        value_area_volume = self.profile.loc[value_area_mask, 'volume'].sum()
        value_area_concentration = value_area_volume / total_volume
        
        # Calculate volume above/below POC
        above_poc_mask = self.profile['price'] > self.point_of_control
        below_poc_mask = self.profile['price'] < self.point_of_control
        
        above_poc_volume = self.profile.loc[above_poc_mask, 'volume'].sum()
        below_poc_volume = self.profile.loc[below_poc_mask, 'volume'].sum()
        
        volume_skew = (above_poc_volume - below_poc_volume) / total_volume
        
        features = {
            'point_of_control': self.point_of_control,
            'value_area_low': self.value_area[0],
            'value_area_high': self.value_area[1],
            'value_area_width': self.value_area[1] - self.value_area[0],
            'total_volume': total_volume,
            'max_volume': max_volume,
            'volume_std': volume_std,
            'volume_concentration': gini,
            'value_area_concentration': value_area_concentration,
            'volume_skew': volume_skew,
        }
        
        if distance_to_poc is not None:
            features['distance_to_poc'] = distance_to_poc
        
        return features 