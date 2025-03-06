"""
Volume Profile Analysis Module
----------------------------
Provides functionality for volume profile analysis
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

import config

logger = logging.getLogger(__name__)

class VolumeProfile:
    """Class for analyzing volume profiles and identifying key levels"""
    
    def __init__(self, price_data: np.ndarray = None, volume_data: np.ndarray = None, 
                num_bins: int = 100):
        """
        Initialize the volume profile analyzer
        
        Args:
            price_data: Array of price data
            volume_data: Array of volume data
            num_bins: Number of bins for volume profile
        """
        self.price_data = price_data
        self.volume_data = volume_data
        self.num_bins = num_bins
        self.histogram = None
        self.bin_centers = None
        self.poc = None
        self.vah = None
        self.val = None
    
    def set_data(self, price_data: np.ndarray, volume_data: np.ndarray) -> None:
        """
        Set price and volume data
        
        Args:
            price_data: Array of price data
            volume_data: Array of volume data
        """
        self.price_data = price_data
        self.volume_data = volume_data
    
    def calculate_profile(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate volume profile histogram
        
        Returns:
            Tuple of (histogram, bin_centers)
        """
        if self.price_data is None or self.volume_data is None:
            logger.error("Price or volume data not set")
            return np.array([]), np.array([])
        
        try:
            # Calculate price range
            min_price = np.min(self.price_data)
            max_price = np.max(self.price_data)
            
            # Create bins
            bins = np.linspace(min_price, max_price, self.num_bins + 1)
            
            # Calculate histogram with volume weights
            hist, bin_edges = np.histogram(self.price_data, bins=bins, weights=self.volume_data)
            
            # Calculate bin centers for easier reference
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            # Store results
            self.histogram = hist
            self.bin_centers = bin_centers
            
            return hist, bin_centers
            
        except Exception as e:
            logger.error(f"Error calculating volume profile: {str(e)}")
            return np.array([]), np.array([])
    
    def find_key_levels(self) -> Dict[str, Any]:
        """
        Find key volume profile levels (POC, VAH, VAL)
        
        Returns:
            Dictionary with key levels
        """
        if self.histogram is None or self.bin_centers is None:
            hist, bin_centers = self.calculate_profile()
            if len(hist) == 0 or len(bin_centers) == 0:
                logger.error("Failed to calculate volume profile")
                return {}
        else:
            hist, bin_centers = self.histogram, self.bin_centers
        
        try:
            # Point of Control (POC) - price level with highest volume
            poc_idx = np.argmax(hist)
            poc = bin_centers[poc_idx]
            
            # Calculate Value Area (70% of volume)
            total_volume = np.sum(hist)
            target_volume = total_volume * 0.7
            
            # Sort indices by volume (highest to lowest)
            sorted_indices = np.argsort(-hist)
            
            # Take indices until we reach 70% of volume
            cumulative_volume = 0
            value_area_indices = []
            
            for idx in sorted_indices:
                value_area_indices.append(idx)
                cumulative_volume += hist[idx]
                if cumulative_volume >= target_volume:
                    break
            
            # Find Value Area High and Value Area Low
            vah = bin_centers[max(value_area_indices)]
            val = bin_centers[min(value_area_indices)]
            
            # Store results
            self.poc = poc
            self.vah = vah
            self.val = val
            
            # Find significant volume clusters
            peak_indices, _ = find_peaks(hist, height=np.mean(hist) * 1.5)
            volume_clusters = [(bin_centers[i], hist[i]) for i in peak_indices]
            
            return {
                'POC': float(poc),
                'VAH': float(vah),
                'VAL': float(val),
                'volume_clusters': volume_clusters,
                'histogram': hist.tolist(),
                'bin_centers': bin_centers.tolist()
            }
            
        except Exception as e:
            logger.error(f"Error finding key levels: {str(e)}")
            return {}
    
    def plot_profile(self, ax=None, title: str = "Volume Profile") -> Optional[plt.Axes]:
        """
        Plot volume profile
        
        Args:
            ax: Matplotlib axes to plot on (optional)
            title: Plot title
            
        Returns:
            Matplotlib axes with plot
        """
        if self.histogram is None or self.bin_centers is None:
            self.calculate_profile()
            if self.histogram is None or self.bin_centers is None:
                logger.error("Failed to calculate profile for plotting")
                return None
        
        if self.poc is None or self.vah is None or self.val is None:
            self.find_key_levels()
        
        try:
            # Create plot if not provided
            if ax is None:
                fig, ax = plt.subplots(figsize=(10, 6))
            
            # Plot horizontal volume bars
            ax.barh(self.bin_centers, self.histogram, height=self.bin_centers[1] - self.bin_centers[0])
            
            # Plot key levels
            if self.poc is not None:
                ax.axhline(y=self.poc, color='r', linestyle='-', label='POC')
            if self.vah is not None:
                ax.axhline(y=self.vah, color='g', linestyle='--', label='VAH')
            if self.val is not None:
                ax.axhline(y=self.val, color='g', linestyle='--', label='VAL')
            
            # Add labels and legend
            ax.set_title(title)
            ax.set_xlabel('Volume')
            ax.set_ylabel('Price')
            ax.legend()
            
            return ax
            
        except Exception as e:
            logger.error(f"Error plotting volume profile: {str(e)}")
            return None
    
    def analyze_from_dataframe(self, df: pd.DataFrame, price_col: str = 'close', 
                             volume_col: str = 'volume') -> Dict[str, Any]:
        """
        Calculate volume profile from DataFrame
        
        Args:
            df: DataFrame with price and volume data
            price_col: Column name for price data
            volume_col: Column name for volume data
            
        Returns:
            Dictionary with volume profile analysis
        """
        if price_col not in df.columns or volume_col not in df.columns:
            logger.error(f"Required columns not found in DataFrame: {price_col}, {volume_col}")
            return {}
        
        # Set data
        self.set_data(df[price_col].values, df[volume_col].values)
        
        # Calculate profile and find key levels
        return self.find_key_levels()