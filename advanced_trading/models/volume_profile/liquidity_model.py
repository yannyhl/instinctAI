#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Liquidity Analysis for Financial Markets.

This module provides tools for estimating market liquidity and potential price impact
of orders, which is essential for optimizing trade execution and managing transaction costs.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass
import logging
from scipy.optimize import curve_fit

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class LiquidityMetrics:
    """
    Represents liquidity metrics for a financial instrument.
    
    Attributes
    ----------
    spread : float
        The bid-ask spread.
    depth : float
        The market depth (volume available at best bid/ask).
    slippage_estimate : float
        Estimated slippage for a given order size.
    market_impact : float
        Estimated market impact for a given order size.
    resilience : float
        Market resilience (recovery time after large trades).
    volume_profile_concentration : float
        Concentration of volume across price levels (Gini coefficient).
    amihud_illiquidity : float
        Amihud illiquidity ratio.
    kyle_lambda : float
        Kyle's lambda (price impact per unit of order flow).
    """
    spread: float
    depth: float
    slippage_estimate: float
    market_impact: float
    resilience: float = None
    volume_profile_concentration: float = None
    amihud_illiquidity: float = None
    kyle_lambda: float = None


class LiquidityModel:
    """
    Analyzes market liquidity and estimates potential price impact of orders.
    
    This class provides tools for estimating market liquidity and potential price impact
    of orders, which is essential for optimizing trade execution and managing transaction costs.
    
    Parameters
    ----------
    price_data : pd.DataFrame or pd.Series
        Price data for analysis. If a DataFrame, must contain columns for price.
    volume_data : pd.Series, optional
        Volume data corresponding to price_data. Required if price_data is a Series.
    bid_data : pd.Series, optional
        Bid price data. If provided, used for spread calculation.
    ask_data : pd.Series, optional
        Ask price data. If provided, used for spread calculation.
    bid_volume_data : pd.Series, optional
        Bid volume data. If provided, used for depth calculation.
    ask_volume_data : pd.Series, optional
        Ask volume data. If provided, used for depth calculation.
    time_index : pd.DatetimeIndex, optional
        Time index for the data. If None and price_data has a DatetimeIndex, uses that.
    """
    
    def __init__(
        self,
        price_data: Union[pd.DataFrame, pd.Series],
        volume_data: Optional[pd.Series] = None,
        bid_data: Optional[pd.Series] = None,
        ask_data: Optional[pd.Series] = None,
        bid_volume_data: Optional[pd.Series] = None,
        ask_volume_data: Optional[pd.Series] = None,
        time_index: Optional[pd.DatetimeIndex] = None
    ):
        """Initialize the LiquidityModel with price and volume data."""
        self.time_index = None
        
        # Process input data
        if isinstance(price_data, pd.DataFrame):
            if 'price' in price_data.columns:
                self.price = price_data['price'].values
                if 'volume' in price_data.columns:
                    self.volume = price_data['volume'].values
                elif volume_data is not None:
                    self.volume = volume_data.values
                else:
                    self.volume = None
                
                if time_index is None and isinstance(price_data.index, pd.DatetimeIndex):
                    self.time_index = price_data.index
                else:
                    self.time_index = time_index
            else:
                raise ValueError("DataFrame must contain 'price' column")
        elif isinstance(price_data, pd.Series):
            self.price = price_data.values
            if volume_data is not None:
                self.volume = volume_data.values
            else:
                self.volume = None
            
            if time_index is None and isinstance(price_data.index, pd.DatetimeIndex):
                self.time_index = price_data.index
            else:
                self.time_index = time_index
        else:
            raise ValueError("price_data must be a DataFrame or Series")
        
        # Store bid/ask data if provided
        self.bid = bid_data.values if bid_data is not None else None
        self.ask = ask_data.values if ask_data is not None else None
        self.bid_volume = bid_volume_data.values if bid_volume_data is not None else None
        self.ask_volume = ask_volume_data.values if ask_volume_data is not None else None
        
        # Initialize metrics
        self.metrics = None
        self.market_impact_model = None
        self.market_impact_params = None
        
        logger.info("LiquidityModel initialized")
    
    def calculate_spread(self) -> float:
        """
        Calculate the average bid-ask spread.
        
        Returns
        -------
        float
            Average bid-ask spread.
        """
        if self.bid is None or self.ask is None:
            raise ValueError("Bid and ask data required for spread calculation")
        
        spread = np.mean(self.ask - self.bid)
        return spread
    
    def calculate_depth(self) -> float:
        """
        Calculate the average market depth (volume available at best bid/ask).
        
        Returns
        -------
        float
            Average market depth.
        """
        if self.bid_volume is None or self.ask_volume is None:
            raise ValueError("Bid and ask volume data required for depth calculation")
        
        depth = np.mean(self.bid_volume + self.ask_volume)
        return depth
    
    def calculate_amihud_illiquidity(self, window: int = 20) -> pd.Series:
        """
        Calculate Amihud's illiquidity ratio.
        
        The Amihud illiquidity ratio is defined as the average ratio of absolute returns
        to trading volume over a given time period. Higher values indicate lower liquidity.
        
        Parameters
        ----------
        window : int, default=20
            Rolling window size for calculation.
            
        Returns
        -------
        pd.Series
            Amihud illiquidity ratio over time.
        """
        if self.volume is None:
            raise ValueError("Volume data required for Amihud illiquidity calculation")
        
        # Calculate returns
        returns = np.diff(self.price) / self.price[:-1]
        returns = np.append(0, returns)  # Add 0 for the first element
        
        # Calculate absolute returns / volume
        illiquidity = np.abs(returns) / self.volume
        
        # Replace inf and nan values
        illiquidity = np.nan_to_num(illiquidity, nan=0, posinf=0, neginf=0)
        
        # Create Series with time index
        if self.time_index is not None:
            illiquidity_series = pd.Series(illiquidity, index=self.time_index)
        else:
            illiquidity_series = pd.Series(illiquidity)
        
        # Calculate rolling average
        illiquidity_rolling = illiquidity_series.rolling(window=window).mean()
        
        return illiquidity_rolling
    
    def calculate_kyle_lambda(self, returns: pd.Series, order_flow: pd.Series, window: int = 20) -> pd.Series:
        """
        Calculate Kyle's lambda (price impact per unit of order flow).
        
        Kyle's lambda measures the price impact per unit of order flow, which is a key
        measure of market liquidity. Higher values indicate lower liquidity.
        
        Parameters
        ----------
        returns : pd.Series
            Price returns.
        order_flow : pd.Series
            Order flow (signed volume).
        window : int, default=20
            Rolling window size for calculation.
            
        Returns
        -------
        pd.Series
            Kyle's lambda over time.
        """
        # Ensure returns and order_flow have the same index
        if not returns.index.equals(order_flow.index):
            raise ValueError("Returns and order_flow must have the same index")
        
        # Calculate Kyle's lambda using rolling regression
        lambda_series = pd.Series(index=returns.index)
        
        for i in range(window, len(returns)):
            window_returns = returns.iloc[i-window:i]
            window_order_flow = order_flow.iloc[i-window:i]
            
            # Simple linear regression: returns = lambda * order_flow
            if np.std(window_order_flow) > 0:
                lambda_value = np.cov(window_returns, window_order_flow)[0, 1] / np.var(window_order_flow)
                lambda_series.iloc[i] = lambda_value
        
        return lambda_series
    
    def fit_market_impact_model(
        self,
        order_sizes: np.ndarray,
        price_impacts: np.ndarray,
        model_type: str = 'square_root'
    ) -> Tuple[Callable, np.ndarray]:
        """
        Fit a market impact model to observed data.
        
        Parameters
        ----------
        order_sizes : np.ndarray
            Array of order sizes.
        price_impacts : np.ndarray
            Array of observed price impacts corresponding to order_sizes.
        model_type : str, default='square_root'
            Type of market impact model to fit. Options: 'linear', 'square_root', 'power_law'.
            
        Returns
        -------
        Tuple[Callable, np.ndarray]
            Market impact model function and fitted parameters.
        """
        if model_type == 'linear':
            # Linear model: impact = alpha * order_size
            def model_func(x, alpha):
                return alpha * x
            
            initial_params = [0.1]
        
        elif model_type == 'square_root':
            # Square root model: impact = alpha * sqrt(order_size)
            def model_func(x, alpha):
                return alpha * np.sqrt(x)
            
            initial_params = [0.1]
        
        elif model_type == 'power_law':
            # Power law model: impact = alpha * order_size^beta
            def model_func(x, alpha, beta):
                return alpha * np.power(x, beta)
            
            initial_params = [0.1, 0.5]
        
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        # Fit the model
        params, _ = curve_fit(model_func, order_sizes, price_impacts, p0=initial_params)
        
        # Store the model and parameters
        self.market_impact_model = model_func
        self.market_impact_params = params
        
        return model_func, params
    
    def estimate_market_impact(self, order_size: float) -> float:
        """
        Estimate the market impact of an order.
        
        Parameters
        ----------
        order_size : float
            Size of the order.
            
        Returns
        -------
        float
            Estimated market impact.
        """
        if self.market_impact_model is None or self.market_impact_params is None:
            raise ValueError("Market impact model not fitted. Call fit_market_impact_model first.")
        
        impact = self.market_impact_model(order_size, *self.market_impact_params)
        return impact
    
    def estimate_optimal_execution_size(
        self,
        total_size: float,
        max_impact: float,
        min_chunks: int = 1,
        max_chunks: int = 100
    ) -> Tuple[int, float, float]:
        """
        Estimate the optimal execution size to minimize market impact.
        
        Parameters
        ----------
        total_size : float
            Total size of the order to execute.
        max_impact : float
            Maximum acceptable market impact per chunk.
        min_chunks : int, default=1
            Minimum number of chunks to split the order into.
        max_chunks : int, default=100
            Maximum number of chunks to split the order into.
            
        Returns
        -------
        Tuple[int, float, float]
            Number of chunks, size per chunk, and estimated total impact.
        """
        if self.market_impact_model is None or self.market_impact_params is None:
            raise ValueError("Market impact model not fitted. Call fit_market_impact_model first.")
        
        # Initialize with min_chunks
        best_chunks = min_chunks
        best_impact = float('inf')
        
        # Try different numbers of chunks
        for chunks in range(min_chunks, max_chunks + 1):
            chunk_size = total_size / chunks
            chunk_impact = self.estimate_market_impact(chunk_size)
            
            # If chunk impact is within limit, calculate total impact
            if chunk_impact <= max_impact:
                # Simple model: total impact = sum of individual impacts
                # More sophisticated models could account for market resilience
                total_impact = chunks * chunk_impact
                
                if total_impact < best_impact:
                    best_impact = total_impact
                    best_chunks = chunks
        
        # Calculate optimal chunk size
        optimal_size = total_size / best_chunks
        
        return best_chunks, optimal_size, best_impact
    
    def calculate_market_resilience(
        self,
        price_data: pd.Series,
        event_times: List[pd.Timestamp],
        window_before: int = 10,
        window_after: int = 30
    ) -> float:
        """
        Calculate market resilience (recovery time after large trades).
        
        Parameters
        ----------
        price_data : pd.Series
            Price data with DatetimeIndex.
        event_times : List[pd.Timestamp]
            List of times when large trades occurred.
        window_before : int, default=10
            Number of periods before event to establish baseline.
        window_after : int, default=30
            Number of periods after event to measure recovery.
            
        Returns
        -------
        float
            Average market resilience (recovery time).
        """
        recovery_times = []
        
        for event_time in event_times:
            # Find index of event time
            try:
                event_idx = price_data.index.get_loc(event_time)
            except KeyError:
                # Find closest time if exact match not found
                event_idx = price_data.index.get_indexer([event_time], method='nearest')[0]
            
            # Get data before and after event
            before_data = price_data.iloc[max(0, event_idx - window_before):event_idx]
            after_data = price_data.iloc[event_idx:min(len(price_data), event_idx + window_after)]
            
            if len(before_data) == 0 or len(after_data) == 0:
                continue
            
            # Calculate baseline price (average before event)
            baseline_price = before_data.mean()
            
            # Calculate price deviation at event
            event_price = after_data.iloc[0]
            deviation = abs(event_price - baseline_price)
            
            # If no significant deviation, skip this event
            if deviation < 0.001 * baseline_price:
                continue
            
            # Find recovery time (when price returns to within 10% of baseline)
            recovery_threshold = 0.1 * deviation
            for i, price in enumerate(after_data):
                if abs(price - baseline_price) <= recovery_threshold:
                    recovery_times.append(i)
                    break
        
        # Calculate average recovery time
        if recovery_times:
            avg_recovery_time = np.mean(recovery_times)
            return avg_recovery_time
        else:
            return None
    
    def calculate_volume_profile_concentration(self, n_bins: int = 100) -> float:
        """
        Calculate the concentration of volume across price levels (Gini coefficient).
        
        Parameters
        ----------
        n_bins : int, default=100
            Number of price bins to use.
            
        Returns
        -------
        float
            Volume concentration (Gini coefficient).
        """
        if self.volume is None:
            raise ValueError("Volume data required for volume profile concentration calculation")
        
        # Create price bins
        price_min = np.min(self.price)
        price_max = np.max(self.price)
        bins = np.linspace(price_min, price_max, n_bins + 1)
        
        # Calculate volume histogram
        hist, _ = np.histogram(self.price, bins=bins, weights=self.volume)
        
        # Calculate Gini coefficient
        sorted_hist = np.sort(hist)
        n = len(sorted_hist)
        index = np.arange(1, n + 1)
        gini = 1 - 2 * np.sum((n + 1 - index) * sorted_hist) / (n * np.sum(sorted_hist))
        
        return gini
    
    def calculate_liquidity_metrics(
        self,
        order_size: float = None,
        market_impact_model: str = 'square_root'
    ) -> LiquidityMetrics:
        """
        Calculate comprehensive liquidity metrics.
        
        Parameters
        ----------
        order_size : float, optional
            Size of the order for slippage and market impact estimation.
        market_impact_model : str, default='square_root'
            Type of market impact model to use.
            
        Returns
        -------
        LiquidityMetrics
            Comprehensive liquidity metrics.
        """
        metrics = {}
        
        # Calculate spread if bid/ask data available
        if self.bid is not None and self.ask is not None:
            metrics['spread'] = self.calculate_spread()
        else:
            metrics['spread'] = None
        
        # Calculate depth if bid/ask volume data available
        if self.bid_volume is not None and self.ask_volume is not None:
            metrics['depth'] = self.calculate_depth()
        else:
            metrics['depth'] = None
        
        # Calculate volume profile concentration
        if self.volume is not None:
            metrics['volume_profile_concentration'] = self.calculate_volume_profile_concentration()
        else:
            metrics['volume_profile_concentration'] = None
        
        # Calculate Amihud illiquidity
        if self.volume is not None:
            amihud = self.calculate_amihud_illiquidity()
            metrics['amihud_illiquidity'] = amihud.mean()
        else:
            metrics['amihud_illiquidity'] = None
        
        # Estimate slippage and market impact if order size provided
        if order_size is not None:
            # Simple slippage estimate based on spread and depth
            if metrics['spread'] is not None and metrics['depth'] is not None:
                metrics['slippage_estimate'] = metrics['spread'] * (order_size / metrics['depth'])
            else:
                metrics['slippage_estimate'] = None
            
            # Estimate market impact
            if self.volume is not None:
                # Fit market impact model if not already fitted
                if self.market_impact_model is None:
                    # Use average daily volume for scaling
                    adv = np.mean(self.volume)
                    
                    # Generate synthetic data for fitting
                    order_sizes = np.linspace(0.01 * adv, 0.5 * adv, 10)
                    
                    if market_impact_model == 'linear':
                        price_impacts = 0.1 * order_sizes / adv
                    elif market_impact_model == 'square_root':
                        price_impacts = 0.1 * np.sqrt(order_sizes / adv)
                    else:  # power_law
                        price_impacts = 0.1 * np.power(order_sizes / adv, 0.6)
                    
                    self.fit_market_impact_model(order_sizes, price_impacts, model_type=market_impact_model)
                
                metrics['market_impact'] = self.estimate_market_impact(order_size)
            else:
                metrics['market_impact'] = None
        else:
            metrics['slippage_estimate'] = None
            metrics['market_impact'] = None
        
        # Store metrics
        self.metrics = LiquidityMetrics(**metrics)
        
        return self.metrics
    
    def plot_liquidity_metrics(
        self,
        figsize: Tuple[int, int] = (12, 8),
        title: str = 'Liquidity Metrics',
        save_path: Optional[str] = None
    ):
        """
        Plot liquidity metrics.
        
        Parameters
        ----------
        figsize : Tuple[int, int], default=(12, 8)
            Figure size.
        title : str, default='Liquidity Metrics'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        if self.metrics is None:
            raise ValueError("Liquidity metrics not calculated. Call calculate_liquidity_metrics first.")
        
        # Create figure
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # Plot spread
        if self.metrics.spread is not None:
            axes[0, 0].bar(['Spread'], [self.metrics.spread], color='blue')
            axes[0, 0].set_title('Bid-Ask Spread')
            axes[0, 0].grid(True, alpha=0.3)
        else:
            axes[0, 0].text(0.5, 0.5, 'Spread data not available', ha='center', va='center')
            axes[0, 0].set_title('Bid-Ask Spread')
        
        # Plot depth
        if self.metrics.depth is not None:
            axes[0, 1].bar(['Depth'], [self.metrics.depth], color='green')
            axes[0, 1].set_title('Market Depth')
            axes[0, 1].grid(True, alpha=0.3)
        else:
            axes[0, 1].text(0.5, 0.5, 'Depth data not available', ha='center', va='center')
            axes[0, 1].set_title('Market Depth')
        
        # Plot Amihud illiquidity
        if self.metrics.amihud_illiquidity is not None:
            axes[1, 0].bar(['Amihud Illiquidity'], [self.metrics.amihud_illiquidity], color='red')
            axes[1, 0].set_title('Amihud Illiquidity')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, 'Illiquidity data not available', ha='center', va='center')
            axes[1, 0].set_title('Amihud Illiquidity')
        
        # Plot volume profile concentration
        if self.metrics.volume_profile_concentration is not None:
            axes[1, 1].bar(['Volume Concentration'], [self.metrics.volume_profile_concentration], color='purple')
            axes[1, 1].set_title('Volume Profile Concentration')
            axes[1, 1].grid(True, alpha=0.3)
        else:
            axes[1, 1].text(0.5, 0.5, 'Volume data not available', ha='center', va='center')
            axes[1, 1].set_title('Volume Profile Concentration')
        
        plt.suptitle(title)
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved liquidity metrics plot to {save_path}")
        
        plt.show()
    
    def plot_market_impact_model(
        self,
        max_order_size: float,
        figsize: Tuple[int, int] = (10, 6),
        title: str = 'Market Impact Model',
        save_path: Optional[str] = None
    ):
        """
        Plot the market impact model.
        
        Parameters
        ----------
        max_order_size : float
            Maximum order size to plot.
        figsize : Tuple[int, int], default=(10, 6)
            Figure size.
        title : str, default='Market Impact Model'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        if self.market_impact_model is None or self.market_impact_params is None:
            raise ValueError("Market impact model not fitted. Call fit_market_impact_model first.")
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Generate order sizes
        order_sizes = np.linspace(0, max_order_size, 100)
        
        # Calculate impacts
        impacts = [self.estimate_market_impact(size) for size in order_sizes]
        
        # Plot impact curve
        plt.plot(order_sizes, impacts, 'b-')
        
        plt.xlabel('Order Size')
        plt.ylabel('Market Impact')
        plt.title(title)
        plt.grid(True, alpha=0.3)
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved market impact model plot to {save_path}")
        
        plt.show()
    
    def plot_optimal_execution(
        self,
        total_size: float,
        max_impact: float,
        figsize: Tuple[int, int] = (10, 6),
        title: str = 'Optimal Execution Analysis',
        save_path: Optional[str] = None
    ):
        """
        Plot optimal execution analysis.
        
        Parameters
        ----------
        total_size : float
            Total size of the order to execute.
        max_impact : float
            Maximum acceptable market impact per chunk.
        figsize : Tuple[int, int], default=(10, 6)
            Figure size.
        title : str, default='Optimal Execution Analysis'
            Plot title.
        save_path : str, optional
            Path to save the plot. If None, the plot is not saved.
        """
        if self.market_impact_model is None or self.market_impact_params is None:
            raise ValueError("Market impact model not fitted. Call fit_market_impact_model first.")
        
        # Calculate optimal execution
        chunks, chunk_size, total_impact = self.estimate_optimal_execution_size(
            total_size=total_size,
            max_impact=max_impact
        )
        
        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # Plot number of chunks vs. total impact
        chunk_range = np.arange(1, min(100, total_size) + 1)
        impacts = []
        
        for n_chunks in chunk_range:
            size = total_size / n_chunks
            impact = self.estimate_market_impact(size)
            total_imp = n_chunks * impact
            impacts.append(total_imp)
        
        axes[0].plot(chunk_range, impacts, 'b-')
        axes[0].axvline(x=chunks, color='r', linestyle='--', 
                      label=f'Optimal: {chunks} chunks')
        axes[0].set_xlabel('Number of Chunks')
        axes[0].set_ylabel('Total Market Impact')
        axes[0].set_title('Impact vs. Number of Chunks')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot execution schedule
        times = np.arange(chunks)
        sizes = np.ones(chunks) * chunk_size
        
        axes[1].bar(times, sizes, color='green', alpha=0.7)
        axes[1].set_xlabel('Execution Step')
        axes[1].set_ylabel('Order Size')
        axes[1].set_title(f'Execution Schedule: {chunk_size:.2f} per chunk')
        axes[1].grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        
        # Save plot if path is provided
        if save_path is not None:
            plt.savefig(save_path)
            logger.info(f"Saved optimal execution plot to {save_path}")
        
        plt.show()
    
    def get_liquidity_features(self) -> Dict[str, float]:
        """
        Extract liquidity features for use in machine learning models.
        
        Returns
        -------
        Dict[str, float]
            Dictionary of liquidity features.
        """
        if self.metrics is None:
            raise ValueError("Liquidity metrics not calculated. Call calculate_liquidity_metrics first.")
        
        features = {
            'spread': self.metrics.spread,
            'depth': self.metrics.depth,
            'amihud_illiquidity': self.metrics.amihud_illiquidity,
            'volume_profile_concentration': self.metrics.volume_profile_concentration,
            'market_impact': self.metrics.market_impact,
            'slippage_estimate': self.metrics.slippage_estimate,
            'resilience': self.metrics.resilience,
            'kyle_lambda': self.metrics.kyle_lambda
        }
        
        # Filter out None values
        features = {k: v for k, v in features.items() if v is not None}
        
        return features 