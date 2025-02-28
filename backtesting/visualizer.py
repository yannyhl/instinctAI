import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from typing import Dict, List, Optional, Tuple
import os

class BacktestVisualizer:
    """Generate visualizations from backtest results."""
    
    def __init__(self, equity_curve: pd.Series, trades: List[Dict], 
                 benchmark: Optional[pd.Series] = None, market_data: Optional[pd.DataFrame] = None):
        """
        Initialize with backtest data.
        
        Args:
            equity_curve: Time series of portfolio value
            trades: List of completed trades with entry/exit details
            benchmark: Optional benchmark series for comparison
            market_data: Optional OHLCV market data for price charts
        """
        self.equity_curve = equity_curve
        self.trades = trades
        self.benchmark = benchmark
        self.market_data = market_data
        self.returns = self.equity_curve.pct_change().dropna()
        
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("viridis")
        
    def plot_equity_curve(self, figsize: Tuple[int, int] = (12, 6), 
                          save_path: Optional[str] = None) -> plt.Figure:
        """
        Plot equity curve with optional benchmark comparison.
        
        Args:
            figsize: Figure size as (width, height)
            save_path: Optional path to save the figure
            
        Returns:
            Matplotlib figure object
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot equity curve
        ax.plot(self.equity_curve.index, self.equity_curve, label='Strategy', linewidth=2)
        
        # Plot benchmark if available
        if self.benchmark is not None:
            # Normalize benchmark to same starting value
            benchmark_norm = self.benchmark * (self.equity_curve.iloc[0] / self.benchmark.iloc[0])
            ax.plot(benchmark_norm.index, benchmark_norm, label='Benchmark', linewidth=2, alpha=0.7)
        
        # Plot trade markers
        if self.trades:
            for trade in self.trades:
                if 'entry_time' in trade and 'exit_time' in trade:
                    if trade.get('pnl', 0) > 0:
                        color = 'green'
                    else:
                        color = 'red'
                    
                    # Entry marker
                    entry_value = self.equity_curve.loc[trade['entry_time']] if trade['entry_time'] in self.equity_curve.index else None
                    if entry_value is not None:
                        ax.scatter(trade['entry_time'], entry_value, marker='^', color=color, s=50, alpha=0.7)
                    
                    # Exit marker
                    exit_value = self.equity_curve.loc[trade['exit_time']] if trade['exit_time'] in self.equity_curve.index else None
                    if exit_value is not None:
                        ax.scatter(trade['exit_time'], exit_value, marker='v', color=color, s=50, alpha=0.7)
        
        # Format the plot
        ax.set_title('Equity Curve', fontsize=14)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Portfolio Value', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Format dates on x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.tick_params(labelrotation=45)
        
        fig.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            
        return fig
        
    def plot_drawdown(self, figsize: Tuple[int, int] = (12, 4), 
                      save_path: Optional[str] = None) -> plt.Figure:
        """
        Plot drawdown over time.
        
        Args:
            figsize: Figure size as (width, height)
            save_path: Optional path to save the figure
            
        Returns:
            Matplotlib figure object
        """
        # Calculate drawdown
        running_max = self.equity_curve.cummax()
        drawdown = (self.equity_curve / running_max - 1) * 100
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot drawdown
        ax.fill_between(drawdown.index, drawdown, 0, color='red', alpha=0.3)
        ax.plot(drawdown.index, drawdown, color='red', linewidth=1)
        
        # Format the plot
        ax.set_title('Drawdown Analysis', fontsize=14)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Format dates on x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.tick_params(labelrotation=45)
        
        fig.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            
        return fig
        
    def plot_monthly_returns(self, figsize: Tuple[int, int] = (12, 6), 
                             save_path: Optional[str] = None) -> plt.Figure:
        """
        Plot monthly returns heatmap.
        
        Args:
            figsize: Figure size as (width, height)
            save_path: Optional path to save the figure
            
        Returns:
            Matplotlib figure object
        """
        # Calculate monthly returns
        monthly_returns = self.returns.groupby([
            lambda x: x.year,
            lambda x: x.month
        ]).apply(lambda x: (1 + x).prod() - 1)
        
        # Reshape into a pivot table
        monthly_returns_table = monthly_returns.unstack(level=0)
        
        # Months as rows (more intuitive to read)
        monthly_returns_table.index = pd.date_range(
            start='2000-01-01', periods=12, freq='MS'
        ).strftime('%b')
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # Create the heatmap
        sns.heatmap(
            monthly_returns_table * 100,  # Convert to percentage
            annot=True,
            fmt='.2f',
            cmap='RdYlGn',
            center=0,
            linewidths=1,
            cbar_kws={'label': 'Monthly Return (%)'},
            ax=ax
        )
        
        # Format the plot
        ax.set_title('Monthly Returns (%)', fontsize=14)
        ax.set_ylabel('Month', fontsize=12)
        ax.set_xlabel('Year', fontsize=12)
        
        fig.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            
        return fig
        
    def plot_return_distribution(self, figsize: Tuple[int, int] = (12, 6), 
                                 save_path: Optional[str] = None) -> plt.Figure:
        """
        Plot return distribution with normal curve overlay.
        
        Args:
            figsize: Figure size as (width, height)
            save_path: Optional path to save the figure
            
        Returns:
            Matplotlib figure object
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Daily returns histogram
        returns_pct = self.returns * 100
        sns.histplot(returns_pct, kde=True, stat='density', ax=ax)
        
        # Add normal distribution overlay
        x = np.linspace(returns_pct.min(), returns_pct.max(), 100)
        mu, sigma = returns_pct.mean(), returns_pct.std()
        y = stats.norm.pdf(x, mu, sigma)
        ax.plot(x, y, 'r--', linewidth=2)
        
        # Format the plot
        ax.set_title('Daily Returns Distribution', fontsize=14)
        ax.set_xlabel('Daily Return (%)', fontsize=12)
        ax.set_ylabel('Density', fontsize=12)
        
        # Add mean and std annotations
        ax.axvline(mu, color='black', linestyle='-', alpha=0.7, linewidth=1)
        textstr = f'Mean: {mu:.2f}%\nStd Dev: {sigma:.2f}%'
        ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
        
        fig.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            
        return fig
    
    def plot_trade_analysis(self, figsize: Tuple[int, int] = (12, 10), 
                           save_path: Optional[str] = None) -> plt.Figure:
        """
        Plot trade analysis dashboard.
        
        Args:
            figsize: Figure size as (width, height)
            save_path: Optional path to save the figure
            
        Returns:
            Matplotlib figure object
        """
        if not self.trades:
            return None
            
        # Extract trade data
        pnls = [t.get('pnl', 0) for t in self.trades]
        durations = []
        for trade in self.trades:
            if 'entry_time' in trade and 'exit_time' in trade:
                duration = (trade['exit_time'] - trade['entry_time']).total_seconds() / 3600  # hours
                durations.append(duration)
                
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # 1. Trade P&L distribution
        sns.histplot(pnls, kde=True, ax=axes[0, 0], color='skyblue')
        axes[0, 0].axvline(0, color='red', linestyle='--', alpha=0.7)
        axes[0, 0].set_title('Trade P&L Distribution')
        axes[0, 0].set_xlabel('P&L')
        
        # 2. Trade P&L over time
        trade_dates = [t.get('exit_time') for t in self.trades if 'exit_time' in t]
        if trade_dates:
            axes[0, 1].plot(trade_dates, pnls, marker='o', linestyle='', alpha=0.7)
            axes[0, 1].axhline(0, color='red', linestyle='--', alpha=0.5)
            axes[0, 1].set_title('Trade P&L Over Time')
            axes[0, 1].set_xlabel('Date')
            axes[0, 1].set_ylabel('P&L')
            axes[0, 1].tick_params(axis='x', rotation=45)
        
        # 3. Trade duration vs P&L
        if durations:
            axes[1, 0].scatter(durations, pnls, alpha=0.7)
            axes[1, 0].axhline(0, color='red', linestyle='--', alpha=0.5)
            axes[1, 0].set_title('Trade Duration vs P&L')
            axes[1, 0].set_xlabel('Duration (hours)')
            axes[1, 0].set_ylabel('P&L')
            
        # 4. Cumulative P&L
        cum_pnl = np.cumsum(pnls)
        win_trades = [i for i, pnl in enumerate(pnls) if pnl > 0]
        lose_trades = [i for i, pnl in enumerate(pnls) if pnl <= 0]
        
        axes[1, 1].plot(cum_pnl, label='Cumulative P&L')
        axes[1, 1].scatter(win_trades, cum_pnl[win_trades], color='green', alpha=0.7, label='Win')
        axes[1, 1].scatter(lose_trades, cum_pnl[lose_trades], color='red', alpha=0.7, label='Loss')
        axes[1, 1].set_title('Cumulative P&L')
        axes[1, 1].set_xlabel('Trade #')
        axes[1, 1].set_ylabel('Cumulative P&L')
        axes[1, 1].legend()
        
        fig.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            
        return fig
    
    def create_performance_dashboard(self, output_dir: str = 'results') -> None:
        """
        Create a comprehensive performance dashboard with multiple plots.
        
        Args:
            output_dir: Directory to save the generated plots
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate and save individual plots
        self.plot_equity_curve(save_path=os.path.join(output_dir, 'equity_curve.png'))
        self.plot_drawdown(save_path=os.path.join(output_dir, 'drawdown.png'))
        self.plot_monthly_returns(save_path=os.path.join(output_dir, 'monthly_returns.png'))
        self.plot_return_distribution(save_path=os.path.join(output_dir, 'return_distribution.png'))
        
        if self.trades:
            self.plot_trade_analysis(save_path=os.path.join(output_dir, 'trade_analysis.png'))
        
        # If market data is available, plot price chart with trade markers
        if self.market_data is not None and 'close' in self.market_data.columns:
            self._plot_price_with_trades(save_path=os.path.join(output_dir, 'price_chart.png'))
            
    def _plot_price_with_trades(self, figsize: Tuple[int, int] = (12, 6), 
                               save_path: Optional[str] = None) -> plt.Figure:
        """
        Plot price chart with trade markers.
        
        Args:
            figsize: Figure size as (width, height)
            save_path: Optional path to save the figure
            
        Returns:
            Matplotlib figure object
        """
        if self.market_data is None or 'close' not in self.market_data.columns:
            return None
            
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot price
        ax.plot(self.market_data.index, self.market_data['close'], label='Price')
        
        # Plot trade markers
        for trade in self.trades:
            if 'entry_time' in trade and 'exit_time' in trade and 'direction' in trade:
                color = 'green' if trade['direction'] == 'long' else 'red'
                
                # Entry marker
                if trade['entry_time'] in self.market_data.index:
                    entry_price = self.market_data.loc[trade['entry_time'], 'close']
                    ax.scatter(trade['entry_time'], entry_price, marker='^' if trade['direction'] == 'long' else 'v', 
                               color=color, s=100, alpha=0.7)
                
                # Exit marker
                if trade['exit_time'] in self.market_data.index:
                    exit_price = self.market_data.loc[trade['exit_time'], 'close']
                    ax.scatter(trade['exit_time'], exit_price, marker='v' if trade['direction'] == 'long' else '^', 
                               color='blue', s=100, alpha=0.7)
        
        ax.set_title('Price Chart with Trades', fontsize=14)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Price', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Format dates on x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.tick_params(labelrotation=45)
        
        fig.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            
        return fig