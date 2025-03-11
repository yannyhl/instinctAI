import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
from scipy import stats


class PerformanceMetrics:
    """Calculate and report trading strategy performance metrics."""
    
    def __init__(self, equity_curve: pd.Series, trades: List[Dict], benchmark: Optional[pd.Series] = None):
        """
        Initialize with backtest results.
        
        Args:
            equity_curve: Time series of portfolio value
            trades: List of completed trades with entry/exit details
            benchmark: Optional benchmark series for comparison
        """
        self.equity_curve = equity_curve
        self.trades = trades
        self.benchmark = benchmark
        self.returns = self.equity_curve.pct_change().dropna()
        self.metrics = {}
        
    def calculate_all_metrics(self) -> Dict:
        """Calculate all performance metrics and return as dictionary."""
        self.calculate_basic_metrics()
        self.calculate_risk_metrics()
        self.calculate_drawdown_metrics()
        self.calculate_trade_metrics()
        
        if self.benchmark is not None:
            self.calculate_relative_metrics()
            
        return self.metrics
    
    def calculate_basic_metrics(self) -> None:
        """Calculate basic performance metrics."""
        # Total return
        self.metrics['total_return'] = (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0]) - 1
        
        # Annualized return
        days = (self.equity_curve.index[-1] - self.equity_curve.index[0]).days
        self.metrics['annual_return'] = (1 + self.metrics['total_return']) ** (365 / max(days, 1)) - 1
        
        # Winning percentage
        if len(self.trades) > 0:
            winning_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
            self.metrics['win_rate'] = len(winning_trades) / len(self.trades)
        else:
            self.metrics['win_rate'] = 0
            
    def calculate_risk_metrics(self) -> None:
        """Calculate risk-adjusted return metrics."""
        # Volatility (annualized)
        self.metrics['volatility'] = self.returns.std() * np.sqrt(252)
        
        # Sharpe ratio (assuming 0% risk-free rate)
        if self.metrics['volatility'] != 0:
            self.metrics['sharpe_ratio'] = self.metrics['annual_return'] / self.metrics['volatility']
        else:
            self.metrics['sharpe_ratio'] = 0
            
        # Sortino ratio (downside deviation)
        negative_returns = self.returns[self.returns < 0]
        if len(negative_returns) > 0:
            downside_deviation = negative_returns.std() * np.sqrt(252)
            if downside_deviation != 0:
                self.metrics['sortino_ratio'] = self.metrics['annual_return'] / downside_deviation
            else:
                self.metrics['sortino_ratio'] = 0
        else:
            self.metrics['sortino_ratio'] = np.inf if self.metrics['annual_return'] > 0 else 0
    
    def calculate_drawdown_metrics(self) -> None:
        """Calculate drawdown-related metrics."""
        # Running maximum
        running_max = self.equity_curve.cummax()
        
        # Drawdown percentage
        drawdown = (self.equity_curve / running_max - 1)
        
        # Maximum drawdown
        self.metrics['max_drawdown'] = drawdown.min()
        
        # Average drawdown
        self.metrics['avg_drawdown'] = drawdown[drawdown < 0].mean() if len(drawdown[drawdown < 0]) > 0 else 0
        
        # Calmar ratio
        if self.metrics['max_drawdown'] != 0:
            self.metrics['calmar_ratio'] = self.metrics['annual_return'] / abs(self.metrics['max_drawdown'])
        else:
            self.metrics['calmar_ratio'] = np.inf if self.metrics['annual_return'] > 0 else 0
    
    def calculate_trade_metrics(self) -> None:
        """Calculate trade-specific metrics."""
        if not self.trades:
            self.metrics['avg_trade_return'] = 0
            self.metrics['avg_winner_return'] = 0
            self.metrics['avg_loser_return'] = 0
            self.metrics['profit_factor'] = 0
            self.metrics['expectancy'] = 0
            return
            
        # Average trade return
        pnls = [t.get('pnl', 0) for t in self.trades]
        self.metrics['avg_trade_return'] = np.mean(pnls) if pnls else 0
        
        # Average winner/loser
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        
        self.metrics['avg_winner_return'] = np.mean(winners) if winners else 0
        self.metrics['avg_loser_return'] = np.mean(losers) if losers else 0
        
        # Profit factor
        total_profit = sum(winners) if winners else 0
        total_loss = abs(sum(losers)) if losers else 0
        
        self.metrics['profit_factor'] = total_profit / total_loss if total_loss != 0 else np.inf
        
        # Expectancy
        win_rate = len(winners) / len(pnls) if pnls else 0
        avg_win = np.mean(winners) if winners else 0
        avg_loss = abs(np.mean(losers)) if losers else 0
        
        self.metrics['expectancy'] = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    def calculate_relative_metrics(self) -> None:
        """Calculate metrics relative to benchmark."""
        if self.benchmark is None:
            return
            
        # Align benchmark with equity curve
        benchmark = self.benchmark.reindex(self.equity_curve.index, method='ffill')
        benchmark_returns = benchmark.pct_change().dropna()
        
        # Beta
        cov = np.cov(self.returns, benchmark_returns)[0, 1]
        benchmark_var = benchmark_returns.var()
        self.metrics['beta'] = cov / benchmark_var if benchmark_var != 0 else 0
        
        # Alpha (annualized)
        risk_free_rate = 0  # Assuming 0% risk-free rate
        benchmark_annual_return = (1 + benchmark_returns.mean()) ** 252 - 1
        self.metrics['alpha'] = self.metrics['annual_return'] - (
            risk_free_rate + self.metrics['beta'] * (benchmark_annual_return - risk_free_rate)
        )
        
        # Information ratio
        tracking_error = (self.returns - benchmark_returns).std() * np.sqrt(252)
        if tracking_error != 0:
            self.metrics['information_ratio'] = (self.metrics['annual_return'] - benchmark_annual_return) / tracking_error
        else:
            self.metrics['information_ratio'] = 0
    
    def generate_report(self) -> pd.DataFrame:
        """Generate a DataFrame with all performance metrics."""
        if not self.metrics:
            self.calculate_all_metrics()
            
        # Format metrics for display
        formatted_metrics = {}
        for key, value in self.metrics.items():
            if isinstance(value, float):
                # Format percentages
                if 'return' in key or 'rate' in key or 'drawdown' in key:
                    formatted_metrics[key] = f"{value:.2%}"
                else:
                    formatted_metrics[key] = f"{value:.4f}"
            else:
                formatted_metrics[key] = value
                
        return pd.DataFrame(formatted_metrics.items(), columns=['Metric', 'Value'])
