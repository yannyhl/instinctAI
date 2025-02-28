"""
Volume Profile Module
--------------------
Provides functionality for volume profile analysis, identifying key price levels
based on trading volume distribution.
"""

import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from typing import List, Dict, Tuple, Union, Optional
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
import sys
sys.path.append(str(script_dir))

import config

# Set up logging
logger = logging.getLogger(__name__)

class VolumeProfile:
    """
    Volume Profile Analysis
    
    Analyzes volume distribution across price levels to identify
    value areas, volume nodes, and support/resistance zones.
    """
    
    def __init__(self, 
                num_bins: int = 50, 
                high_vol_percentile: float = 80,
                value_area_percentage: float = 70,
                smooth_kernel_size: int = 3):
        """
        Initialize Volume Profile analyzer.
        
        Args:
            num_bins: Number of price bins to divide the range into
            high_vol_percentile: Percentile to identify high volume nodes (0-100)
            value_area_percentage: Percentage of volume within value area (0-100)
            smooth_kernel_size: Size of smoothing kernel for volume profile
        """
        self.num_bins = num_bins
        self.high_vol_percentile = high_vol_percentile
        self.value_area_percentage = value_area_percentage
        self.smooth_kernel_size = smooth_kernel_size
        
        # Results storage
        self.bins = None
        self.volumes = None
        self.bin_edges = None
        self.value_area = None
        self.high_volume_nodes = None
        self.low_volume_nodes = None
        self.peak_levels = None
        self.valley_levels = None
        
        logger.info(f"Initialized Volume Profile analyzer with {num_bins} bins")
    
    def analyze(self, data: pd.DataFrame, use_hlc: bool = True) -> Dict[str, np.ndarray]:
        """
        Analyze volume profile from OHLCV data.
        
        Args:
            data: DataFrame with OHLC(V) data
            use_hlc: Whether to use the high-low-close average price instead of just close
            
        Returns:
            Dictionary of analysis results
        """
        # Verify data contains required columns
        required_cols = ['volume']
        if use_hlc:
            required_cols.extend(['high', 'low', 'close'])
        else:
            required_cols.append('close')
        
        for col in required_cols:
            if col not in data.columns:
                logger.error(f"Required column '{col}' not found in data")
                return None
        
        # Calculate the price to use (HLC/3 or close)
        if use_hlc:
            price = (data['high'] + data['low'] + data['close']) / 3
        else:
            price = data['close']
            
        # Create histogram
        hist_range = (price.min(), price.max())
        hist_volumes, bin_edges = np.histogram(
            price, 
            bins=self.num_bins, 
            range=hist_range, 
            weights=data['volume']
        )
        
        # Calculate bin centers
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        # Smooth the volume profile
        if self.smooth_kernel_size > 1:
            kernel = np.ones(self.smooth_kernel_size) / self.smooth_kernel_size
            hist_volumes = np.convolve(hist_volumes, kernel, mode='same')
        
        # Store results
        self.bins = bin_centers
        self.volumes = hist_volumes
        self.bin_edges = bin_edges
        
        # Identify high volume nodes
        high_vol_threshold = np.percentile(hist_volumes, self.high_vol_percentile)
        self.high_volume_nodes = bin_centers[hist_volumes >= high_vol_threshold]
        
        # Identify low volume nodes
        low_vol_threshold = np.percentile(hist_volumes, 100 - self.high_vol_percentile)
        self.low_volume_nodes = bin_centers[hist_volumes <= low_vol_threshold]
        
        # Find peaks (high volume nodes) and valleys (low volume nodes)
        peaks, _ = find_peaks(hist_volumes)
        valleys, _ = find_peaks(-hist_volumes)
        
        self.peak_levels = bin_centers[peaks]
        self.valley_levels = bin_centers[valleys]
        
        # Calculate value area
        self.calculate_value_area()
        
        logger.info(f"Volume profile analysis complete: {len(self.peak_levels)} peaks identified")
        
        return {
            'bins': self.bins,
            'volumes': self.volumes,
            'high_volume_nodes': self.high_volume_nodes,
            'low_volume_nodes': self.low_volume_nodes,
            'peak_levels': self.peak_levels,
            'valley_levels': self.valley_levels,
            'value_area': self.value_area
        }
    
    def calculate_value_area(self) -> Tuple[float, float]:
        """
        Calculate the value area (price range containing X% of volume).
        
        Returns:
            Tuple of (lower_bound, upper_bound) of value area
        """
        if self.volumes is None or self.bins is None:
            logger.error("No volume profile data available")
            return None
        
        # Sort bins by volume (descending)
        sorted_indices = np.argsort(-self.volumes)
        sorted_volumes = self.volumes[sorted_indices]
        sorted_bins = self.bins[sorted_indices]
        
        # Calculate cumulative percentage
        cumulative_vol = np.cumsum(sorted_volumes)
        cumulative_pct = 100 * cumulative_vol / cumulative_vol[-1]
        
        # Find bins within value area percentage
        value_area_indices = np.where(cumulative_pct <= self.value_area_percentage)[0]
        value_area_bins = sorted_bins[value_area_indices]
        
        # Determine bounds
        lower_bound = np.min(value_area_bins)
        upper_bound = np.max(value_area_bins)
        
        self.value_area = (lower_bound, upper_bound)
        
        logger.info(f"Value area calculated: {lower_bound:.2f} - {upper_bound:.2f}")
        return self.value_area
    
    def plot_profile(self, ax=None, show_value_area=True, show_nodes=True) -> plt.Axes:
        """
        Plot the volume profile.
        
        Args:
            ax: Matplotlib axes to plot on
            show_value_area: Whether to highlight the value area
            show_nodes: Whether to highlight high/low volume nodes
            
        Returns:
            Matplotlib axes object
        """
        if self.volumes is None or self.bins is None:
            logger.error("No volume profile data available")
            return None
        
        # Create axes if not provided
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot horizontal volume bars
        ax.barh(self.bins, self.volumes, height=(self.bin_edges[1] - self.bin_edges[0]), 
                alpha=0.7, color='blue')
        
        # Highlight value area
        if show_value_area and self.value_area is not None:
            lower, upper = self.value_area
            ax.axhspan(lower, upper, alpha=0.2, color='green', label='Value Area')
        
        # Mark nodes
        if show_nodes:
            if self.peak_levels is not None and len(self.peak_levels) > 0:
                for level in self.peak_levels:
                    ax.axhline(level, alpha=0.5, linestyle='--', linewidth=1, color='green')
            
            if self.valley_levels is not None and len(self.valley_levels) > 0:
                for level in self.valley_levels:
                    ax.axhline(level, alpha=0.5, linestyle='--', linewidth=1, color='red')
        
        ax.set_title('Volume Profile')
        ax.set_xlabel('Volume')
        ax.set_ylabel('Price')
        ax.grid(True, alpha=0.3)
        
        if show_value_area or show_nodes:
            ax.legend()
        
        return ax
    
    def get_support_resistance_levels(self, num_levels: int = 3) -> Dict[str, List[float]]:
        """
        Get potential support and resistance levels from volume profile.
        
        Args:
            num_levels: Number of levels to return
            
        Returns:
            Dictionary with 'support' and 'resistance' levels
        """
        if self.peak_levels is None or len(self.peak_levels) == 0:
            logger.error("No peak levels identified")
            return {'support': [], 'resistance': []}
        
        # Sort peak levels by price
        sorted_peaks = np.sort(self.peak_levels)
        
        # Get current price (assume last bin is close to current price)
        current_price = self.bins[-1]
        
        # Identify levels below current price (support) and above (resistance)
        support_levels = sorted_peaks[sorted_peaks < current_price]
        resistance_levels = sorted_peaks[sorted_peaks > current_price]
        
        # Return the top levels
        return {
            'support': support_levels[-min(num_levels, len(support_levels)):].tolist(),
            'resistance': resistance_levels[:min(num_levels, len(resistance_levels))].tolist()
        }
    
    def is_price_at_key_level(self, price: float, tolerance_pct: float = 0.5) -> Dict[str, bool]:
        """
        Check if a price is at a key volume level.
        
        Args:
            price: Price to check
            tolerance_pct: Percentage tolerance around level
            
        Returns:
            Dictionary indicating if price is at different key levels
        """
        if self.peak_levels is None or self.value_area is None:
            logger.error("No volume profile data available")
            return None
        
        # Calculate tolerance in absolute price
        tolerance = price * (tolerance_pct / 100)
        
        # Check if price is at a high volume node
        at_high_vol = any(abs(price - level) <= tolerance for level in self.high_volume_nodes)
        
        # Check if price is at a low volume node
        at_low_vol = any(abs(price - level) <= tolerance for level in self.low_volume_nodes)
        
        # Check if price is at edge of value area
        lower, upper = self.value_area
        at_value_area_edge = (abs(price - lower) <= tolerance or abs(price - upper) <= tolerance)
        
        # Check if price is within value area
        in_value_area = (lower - tolerance <= price <= upper + tolerance)
        
        return {
            'at_high_volume_node': at_high_vol,
            'at_low_volume_node': at_low_vol,
            'at_value_area_edge': at_value_area_edge,
            'in_value_area': in_value_area
        }
    
    def get_volume_by_price(self, price: float) -> float:
        """
        Get the volume at a specific price level.
        
        Args:
            price: Price to check
            
        Returns:
            Volume at the price level
        """
        if self.volumes is None or self.bins is None:
            logger.error("No volume profile data available")
            return 0.0
        
        # Find closest bin
        bin_idx = np.abs(self.bins - price).argmin()
        return float(self.volumes[bin_idx])
    
    def find_fair_value_gap(self) -> List[Tuple[float, float]]:
        """
        Find fair value gaps (low volume areas between high volume nodes).
        
        Returns:
            List of tuples (lower_bound, upper_bound) of fair value gaps
        """
        if self.volumes is None or self.bins is None:
            logger.error("No volume profile data available")
            return []
        
        gaps = []
        # Sort valley levels by price
        if self.valley_levels is not None and len(self.valley_levels) > 0:
            sorted_valleys = np.sort(self.valley_levels)
            
            # Check each valley to see if it's a significant low volume area
            for valley in sorted_valleys:
                valley_idx = np.abs(self.bins - valley).argmin()
                valley_vol = self.volumes[valley_idx]
                
                # Look for flanking high volume areas
                lower_high = None
                upper_high = None
                
                for i in range(valley_idx - 1, -1, -1):
                    if self.volumes[i] > valley_vol * 2:  # Significant volume increase
                        lower_high = self.bins[i]
                        break
                
                for i in range(valley_idx + 1, len(self.bins)):
                    if self.volumes[i] > valley_vol * 2:  # Significant volume increase
                        upper_high = self.bins[i]
                        break
                
                if lower_high is not None and upper_high is not None:
                    gaps.append((lower_high, upper_high))
        
        return gaps
    
    def get_poc_level(self) -> float:
        """
        Get the Point of Control (POC) - the price level with highest volume.
        
        Returns:
            Price level of the POC
        """
        if self.volumes is None or self.bins is None:
            logger.error("No volume profile data available")
            return None
        
        poc_idx = np.argmax(self.volumes)
        return float(self.bins[poc_idx])
    
    def as_features(self) -> Dict[str, float]:
        """
        Convert volume profile analysis into features for ML models.
        
        Returns:
            Dictionary of features
        """
        if self.volumes is None or self.bins is None:
            logger.error("No volume profile data available")
            return {}
        
        # Get POC and value area
        poc = self.get_poc_level()
        
        # For simplicity, assume last bin price is close to current price
        current_price = self.bins[-1]
        
        # Calculate distance from current price to key levels
        features = {}
        
        if poc is not None:
            features['dist_to_poc_pct'] = 100 * (current_price - poc) / current_price
        
        if self.value_area is not None:
            lower, upper = self.value_area
            features['dist_to_va_lower_pct'] = 100 * (current_price - lower) / current_price
            features['dist_to_va_upper_pct'] = 100 * (current_price - upper) / current_price
            features['price_in_value_area'] = 1.0 if lower <= current_price <= upper else 0.0
        
        # Get closest support and resistance
        levels = self.get_support_resistance_levels(num_levels=1)
        
        if levels['support'] and len(levels['support']) > 0:
            closest_support = levels['support'][0]
            features['dist_to_support_pct'] = 100 * (current_price - closest_support) / current_price
        
        if levels['resistance'] and len(levels['resistance']) > 0:
            closest_resistance = levels['resistance'][0]
            features['dist_to_resistance_pct'] = 100 * (closest_resistance - current_price) / current_price
        
        # Calculate volume concentration metrics
        if len(self.high_volume_nodes) > 0:
            features['high_volume_node_count'] = len(self.high_volume_nodes)
        
        return features 