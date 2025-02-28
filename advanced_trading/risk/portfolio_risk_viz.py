"""
Portfolio Risk Visualization
--------------------------
Visualization and reporting components for portfolio risk management.

This module provides visualization and reporting tools for the PortfolioRiskController.
It includes methods for plotting risk allocation, exposure, drawdowns, and generating
comprehensive risk reports.

This is a companion module to portfolio_risk.py and will be merged into
the main PortfolioRiskController class.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Callable, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
import seaborn as sns
from datetime import datetime, timedelta
import logging

# Configure logging
logger = logging.getLogger(__name__)

class PortfolioRiskViz:
    """
    Visualization and reporting functions for portfolio risk management.
    
    This class contains methods for portfolio risk visualization and reporting
    that will be integrated into the PortfolioRiskController class.
    """

    @staticmethod
    def plot_risk_allocation(
        positions: Dict[str, Dict[str, Any]],
        current_equity: float
    ) -> plt.Figure:
        """
        Plot current risk allocation by category and correlation group.
        
        Args:
            positions: Dictionary of positions
            current_equity: Current portfolio equity
            
        Returns:
            Matplotlib figure object
        """
        if not positions:
            logger.warning("No positions to plot risk allocation")
            return None
        
        # Calculate risk by category
        risk_by_category = {}
        for symbol, position in positions.items():
            category = position['category']
            if category not in risk_by_category:
                risk_by_category[category] = 0
            risk_by_category[category] += position['risk_amount']
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Plot risk by category
        categories = list(risk_by_category.keys())
        values = [risk_by_category[cat] for cat in categories]
        
        ax1.pie(values, labels=categories, autopct='%1.1f%%', startangle=90)
        ax1.set_title('Risk Allocation by Category')
        
        # Plot risk vs allocation by position
        symbols = list(positions.keys())
        allocations = [positions[s]['value'] / current_equity for s in symbols]
        risks = [positions[s]['risk_amount'] / current_equity for s in symbols]
        
        ax2.scatter(allocations, risks, s=80, alpha=0.7)
        
        # Add labels
        for i, symbol in enumerate(symbols):
            ax2.annotate(symbol, (allocations[i], risks[i]), 
                        xytext=(5, 5), textcoords='offset points')
        
        ax2.set_xlabel('Allocation (% of Portfolio)')
        ax2.set_ylabel('Risk (% of Portfolio)')
        ax2.set_title('Position Risk vs Allocation')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_equity_curve(
        equity_curve: pd.Series,
        drawdown_history: pd.Series = None,
        highlight_drawdowns: bool = True,
        drawdown_threshold: float = 0.05
    ) -> plt.Figure:
        """
        Plot equity curve with optional drawdown highlighting.
        
        Args:
            equity_curve: Series of portfolio equity values
            drawdown_history: Series of drawdowns
            highlight_drawdowns: Whether to highlight drawdown periods
            drawdown_threshold: Threshold for highlighting drawdowns
            
        Returns:
            Matplotlib figure object
        """
        if equity_curve.empty:
            logger.warning("Empty equity curve, cannot plot")
            return None
        
        # Create figure
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot equity curve
        ax1 = axes[0]
        ax1.plot(equity_curve.index, equity_curve.values, 'b-', linewidth=2)
        ax1.set_title('Portfolio Equity Curve')
        ax1.set_ylabel('Equity')
        ax1.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # Highlight drawdown periods if requested
        if highlight_drawdowns and drawdown_history is not None and not drawdown_history.empty:
            # Find periods where drawdown exceeds threshold
            drawdown_periods = []
            in_drawdown = False
            start_idx = None
            
            for i, (date, dd) in enumerate(drawdown_history.items()):
                if not in_drawdown and dd >= drawdown_threshold:
                    # Start of drawdown period
                    in_drawdown = True
                    start_idx = i
                elif in_drawdown and dd < drawdown_threshold:
                    # End of drawdown period
                    in_drawdown = False
                    drawdown_periods.append((
                        drawdown_history.index[start_idx],
                        drawdown_history.index[i]
                    ))
            
            # Add last period if still in drawdown
            if in_drawdown:
                drawdown_periods.append((
                    drawdown_history.index[start_idx],
                    drawdown_history.index[-1]
                ))
            
            # Highlight drawdown periods
            for start, end in drawdown_periods:
                ax1.axvspan(start, end, alpha=0.2, color='red')
        
        # Plot drawdown
        ax2 = axes[1]
        if drawdown_history is not None and not drawdown_history.empty:
            ax2.fill_between(
                drawdown_history.index,
                0,
                drawdown_history.values * 100,  # Convert to percentage
                color='red',
                alpha=0.3
            )
            ax2.plot(drawdown_history.index, drawdown_history.values * 100, 'r-', linewidth=1)
            
            # Add drawdown threshold line
            if highlight_drawdowns:
                ax2.axhline(y=drawdown_threshold * 100, color='r', linestyle='--', alpha=0.5)
        
        ax2.set_title('Drawdown (%)')
        ax2.set_ylabel('Drawdown %')
        ax2.yaxis.set_major_formatter(PercentFormatter())
        ax2.grid(True, alpha=0.3)
        ax2.invert_yaxis()
        
        # Format x-axis dates
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_risk_metrics(
        var_history: List[float],
        cvar_history: List[float],
        dates: Optional[List[datetime]] = None
    ) -> plt.Figure:
        """
        Plot risk metrics history (VaR, CVaR).
        
        Args:
            var_history: List of VaR values (95%)
            cvar_history: List of CVaR values (95%)
            dates: List of dates for the x-axis
            
        Returns:
            Matplotlib figure object
        """
        if not var_history or not cvar_history:
            logger.warning("Empty risk metrics history, cannot plot")
            return None
        
        # Create default dates if not provided
        if dates is None:
            end_date = datetime.now()
            dates = [end_date - timedelta(days=i) for i in range(len(var_history))]
            dates.reverse()
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot VaR and CVaR
        ax.plot(dates, [v * 100 for v in var_history], 'b-', linewidth=2, label='VaR (95%)')
        ax.plot(dates, [v * 100 for v in cvar_history], 'r-', linewidth=2, label='CVaR (95%)')
        
        ax.set_title('Risk Metrics History')
        ax.set_ylabel('Value at Risk (%)')
        ax.yaxis.set_major_formatter(PercentFormatter())
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Format x-axis dates
        if isinstance(dates[0], datetime):
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        return fig

    @staticmethod
    def plot_correlation_heatmap(
        correlation_matrix: pd.DataFrame
    ) -> plt.Figure:
        """
        Plot correlation heatmap between assets/strategies.
        
        Args:
            correlation_matrix: Correlation matrix DataFrame
            
        Returns:
            Matplotlib figure object
        """
        if correlation_matrix.empty:
            logger.warning("Empty correlation matrix, cannot plot")
            return None
        
        # Create figure
        plt.figure(figsize=(10, 8))
        
        # Create heatmap
        mask = np.zeros_like(correlation_matrix, dtype=bool)
        mask[np.triu_indices_from(mask)] = True
        
        # Set up the matplotlib figure
        f, ax = plt.subplots(figsize=(11, 9))
        
        # Draw the heatmap with the mask and correct aspect ratio
        sns.heatmap(
            correlation_matrix,
            mask=mask,
            cmap='coolwarm',
            vmax=1,
            vmin=-1,
            center=0,
            square=True,
            linewidths=.5,
            cbar_kws={"shrink": .5},
            annot=True,
            fmt=".2f"
        )
        
        plt.title('Asset Correlation Heatmap')
        plt.tight_layout()
        
        return f
    
    @staticmethod
    def plot_position_performance(
        positions: Dict[str, Dict[str, Any]]
    ) -> plt.Figure:
        """
        Plot position performance as a horizontal bar chart.
        
        Args:
            positions: Dictionary of positions
            
        Returns:
            Matplotlib figure object
        """
        if not positions:
            logger.warning("No positions to plot performance")
            return None
        
        # Extract position data
        symbols = []
        pnl_pcts = []
        pnl_amts = []
        colors = []
        
        for symbol, position in positions.items():
            symbols.append(symbol)
            pnl_pcts.append(position['pnl_pct'] * 100)  # Convert to percentage
            pnl_amts.append(position['pnl_amount'])
            # Set color based on P&L
            colors.append('green' if position['pnl_amount'] > 0 else 'red')
        
        # Sort by P&L amount
        sort_idx = np.argsort(pnl_amts)
        symbols = [symbols[i] for i in sort_idx]
        pnl_pcts = [pnl_pcts[i] for i in sort_idx]
        pnl_amts = [pnl_amts[i] for i in sort_idx]
        colors = [colors[i] for i in sort_idx]
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, max(6, len(symbols) * 0.4)))
        
        # Plot P&L percentage
        ax1.barh(symbols, pnl_pcts, color=colors)
        ax1.set_title('Position P&L (%)')
        ax1.set_xlabel('P&L %')
        ax1.xaxis.set_major_formatter(PercentFormatter())
        ax1.grid(True, alpha=0.3)
        
        # Add values on bars
        for i, pnl in enumerate(pnl_pcts):
            ax1.text(pnl + np.sign(pnl) * 0.5, i, f'{pnl:.2f}%', 
                    va='center', ha='left' if pnl > 0 else 'right')
        
        # Plot P&L amount
        ax2.barh(symbols, pnl_amts, color=colors)
        ax2.set_title('Position P&L (Amount)')
        ax2.set_xlabel('P&L Amount')
        ax2.grid(True, alpha=0.3)
        
        # Add values on bars
        for i, pnl in enumerate(pnl_amts):
            ax2.text(pnl + np.sign(pnl) * 0.5, i, f'${pnl:.2f}', 
                    va='center', ha='left' if pnl > 0 else 'right')
        
        plt.tight_layout()
        return fig 