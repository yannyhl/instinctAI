"""
Performance Metrics Module
-------------------------
Advanced performance and risk metrics for quantitative trading strategies.
Provides industry-standard metrics for comprehensive strategy evaluation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

# Constants
TRADING_DAYS_PER_YEAR = 252  # Standard for most markets
RISK_FREE_RATE = 0.02  # Default 2% annual


def calculate_returns_metrics(returns: pd.Series, 
                             risk_free_rate: float = RISK_FREE_RATE,
                             benchmark_returns: Optional[pd.Series] = None) -> Dict[str, float]:
    """
    Calculate comprehensive return-based performance metrics.
    
    Args:
        returns: Series of strategy returns (daily)
        risk_free_rate: Annual risk-free rate (decimal)
        benchmark_returns: Series of benchmark returns (daily)
        
    Returns:
        Dictionary of performance metrics
    """
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    # Clean data
    returns = returns.fillna(0)
    
    # Ensure returns are decimal not percentage
    if returns.mean() > 0.5:  # Likely percentage
        returns = returns / 100
        
    # Convert annual risk_free_rate to daily
    daily_risk_free = risk_free_rate / TRADING_DAYS_PER_YEAR
    
    # Calculate excess returns
    excess_returns = returns - daily_risk_free
    
    # Calculate metrics
    total_return = (1 + returns).prod() - 1
    n_years = len(returns) / TRADING_DAYS_PER_YEAR
    
    # Annual return (CAGR)
    annual_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
    
    # Volatility (annualized)
    volatility = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    
    # Downside deviation (annualized)
    downside_returns = returns[returns < 0]
    downside_deviation = np.sqrt(np.mean(downside_returns**2)) * np.sqrt(TRADING_DAYS_PER_YEAR) if len(downside_returns) > 0 else 0
    
    # Sharpe ratio
    sharpe_ratio = (excess_returns.mean() / returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR) if returns.std() > 0 else 0
    
    # Sortino ratio
    sortino_ratio = (excess_returns.mean() / downside_deviation) * np.sqrt(TRADING_DAYS_PER_YEAR) if downside_deviation > 0 else 0
    
    # Calculate drawdown series
    portfolio_value = (1 + returns).cumprod()
    peak = portfolio_value.cummax()
    drawdown = (portfolio_value / peak) - 1
    
    # Maximum drawdown
    max_drawdown = drawdown.min()
    
    # Calmar ratio
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown < 0 else np.inf
    
    # Omega ratio
    threshold = daily_risk_free  # Using risk-free rate as threshold
    omega_ratio = _calculate_omega_ratio(returns, threshold)
    
    # Beta and alpha (if benchmark provided)
    beta = alpha = r_squared = information_ratio = tracking_error = 0
    if benchmark_returns is not None:
        if not isinstance(benchmark_returns, pd.Series):
            benchmark_returns = pd.Series(benchmark_returns)
        
        benchmark_returns = benchmark_returns.fillna(0)
        
        # Ensure alignment of returns
        common_idx = returns.index.intersection(benchmark_returns.index)
        if len(common_idx) > 0:
            returns_aligned = returns.loc[common_idx]
            benchmark_aligned = benchmark_returns.loc[common_idx]
            
            # Beta
            covariance = np.cov(returns_aligned, benchmark_aligned)[0, 1]
            benchmark_variance = np.var(benchmark_aligned)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
            
            # Alpha (Jensen's Alpha)
            alpha = _calculate_alpha(returns_aligned, benchmark_aligned, daily_risk_free, beta)
            
            # R-squared
            r_squared = _calculate_r_squared(returns_aligned, benchmark_aligned)
            
            # Tracking Error and Information Ratio
            excess_return = returns_aligned - benchmark_aligned
            tracking_error = excess_return.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
            information_ratio = (excess_return.mean() * TRADING_DAYS_PER_YEAR) / tracking_error if tracking_error > 0 else 0
    
    # Calculate monthly returns statistics
    if isinstance(returns.index, pd.DatetimeIndex) and len(returns) > 30:
        monthly_returns = ((1 + returns).resample('M').prod() - 1)
        best_month = monthly_returns.max()
        worst_month = monthly_returns.min()
    else:
        best_month = worst_month = np.nan
    
    # Tail risk metrics
    var_95 = _calculate_value_at_risk(returns, 0.95)
    cvar_95 = _calculate_conditional_var(returns, 0.95)
    
    # Return distribution metrics
    skew = returns.skew()
    kurtosis = returns.kurt()
    
    # Win rate and profit metrics (if returns represent trades)
    win_rate = len(returns[returns > 0]) / len(returns) if len(returns) > 0 else 0
    profit_factor = abs(returns[returns > 0].sum() / returns[returns < 0].sum()) if returns[returns < 0].sum() != 0 else np.inf
    
    # Compile all metrics
    metrics = {
        'total_return': total_return * 100,  # Convert to percentage
        'annual_return': annual_return * 100,
        'volatility': volatility * 100,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'max_drawdown': max_drawdown * 100,
        'calmar_ratio': calmar_ratio,
        'omega_ratio': omega_ratio,
        'beta': beta,
        'alpha': alpha * 100,  # Convert to percentage
        'r_squared': r_squared,
        'information_ratio': information_ratio,
        'tracking_error': tracking_error * 100,
        'var_95': var_95 * 100,
        'cvar_95': cvar_95 * 100,
        'skew': skew,
        'kurtosis': kurtosis,
        'win_rate': win_rate * 100,
        'profit_factor': profit_factor,
        'best_month': best_month * 100 if not np.isnan(best_month) else np.nan,
        'worst_month': worst_month * 100 if not np.isnan(worst_month) else np.nan
    }
    
    return metrics


def calculate_drawdown_metrics(returns: pd.Series) -> Dict[str, float]:
    """
    Calculate drawdown-related metrics.
    
    Args:
        returns: Series of strategy returns
        
    Returns:
        Dictionary of drawdown metrics
    """
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    # Calculate equity curve
    equity_curve = (1 + returns).cumprod()
    
    # Calculate running maximum
    running_max = equity_curve.cummax()
    
    # Calculate drawdown
    drawdown = (equity_curve / running_max - 1) * 100  # Convert to percentage
    
    # Calculate drawdown duration
    is_drawdown = drawdown < 0
    
    # Find start of drawdowns
    drawdown_starts = is_drawdown & ~is_drawdown.shift(1, fill_value=False)
    drawdown_starts = drawdown_starts[drawdown_starts].index
    
    # Find end of drawdowns
    drawdown_ends = ~is_drawdown & is_drawdown.shift(1, fill_value=False)
    drawdown_ends = drawdown_ends[drawdown_ends].index
    
    # Create drawdown periods
    drawdown_periods = []
    
    # Add the last drawdown period if still in drawdown
    if is_drawdown.iloc[-1] and len(drawdown_starts) > len(drawdown_ends):
        drawdown_ends = drawdown_ends.append(pd.Index([returns.index[-1]]))
    
    for start, end in zip(drawdown_starts, drawdown_ends):
        period_drawdown = drawdown.loc[start:end]
        max_drawdown = period_drawdown.min()
        drawdown_length = len(period_drawdown)
        recovery_time = drawdown_length - period_drawdown.argmin()
        
        drawdown_periods.append({
            'start': start,
            'end': end,
            'max_drawdown': max_drawdown,
            'length': drawdown_length,
            'recovery_time': recovery_time
        })
    
    # Calculate metrics
    if drawdown_periods:
        max_drawdown = min(period['max_drawdown'] for period in drawdown_periods)
        avg_drawdown = np.mean([period['max_drawdown'] for period in drawdown_periods])
        max_length = max(period['length'] for period in drawdown_periods)
        avg_length = np.mean([period['length'] for period in drawdown_periods])
        max_recovery = max(period['recovery_time'] for period in drawdown_periods)
        avg_recovery = np.mean([period['recovery_time'] for period in drawdown_periods])
        drawdown_frequency = len(drawdown_periods) / (len(returns) / TRADING_DAYS_PER_YEAR)  # Annual frequency
    else:
        max_drawdown = avg_drawdown = 0
        max_length = avg_length = 0
        max_recovery = avg_recovery = 0
        drawdown_frequency = 0
    
    # Recovery factor
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100
    recovery_factor = abs(total_return / max_drawdown) if max_drawdown != 0 else np.inf
    
    # Pain index (average drawdown)
    pain_index = abs(drawdown.mean())
    
    # Pain ratio
    annual_return = total_return / (len(returns) / TRADING_DAYS_PER_YEAR)
    pain_ratio = annual_return / pain_index if pain_index != 0 else np.inf
    
    # Compile metrics
    metrics = {
        'max_drawdown': max_drawdown,
        'avg_drawdown': avg_drawdown,
        'pain_index': pain_index,
        'pain_ratio': pain_ratio,
        'recovery_factor': recovery_factor,
        'drawdown_frequency': drawdown_frequency,
        'max_drawdown_length': max_length,
        'avg_drawdown_length': avg_length,
        'max_recovery_time': max_recovery,
        'avg_recovery_time': avg_recovery,
        'drawdown_periods': drawdown_periods
    }
    
    return metrics


def calculate_trade_metrics(trades: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate trade-based performance metrics.
    
    Args:
        trades: DataFrame of trades with required columns:
               - 'profit': P&L of each trade
               - 'duration': Duration of each trade
               - 'entry_price': Entry price
               - 'exit_price': Exit price
               Optional columns:
               - 'symbol': Trading symbol
               - 'direction': 1 for long, -1 for short
               - 'size': Position size
               - 'entry_time': Entry timestamp
               - 'exit_time': Exit timestamp
               - 'stop_price': Stop price if used
    
    Returns:
        Dictionary of trade metrics
    """
    if trades.empty:
        return {
            'num_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'avg_profit': 0,
            'avg_loss': 0,
            'avg_duration': 0,
            'avg_profit_per_day': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'avg_win_duration': 0,
            'avg_loss_duration': 0
        }
    
    # Basic metrics
    num_trades = len(trades)
    
    # Win/loss metrics
    winning_trades = trades[trades['profit'] > 0]
    losing_trades = trades[trades['profit'] <= 0]
    
    win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0
    
    # Profit metrics
    total_profit = sum(winning_trades['profit']) if not winning_trades.empty else 0
    total_loss = sum(losing_trades['profit']) if not losing_trades.empty else 0
    
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 else np.inf
    
    avg_profit = winning_trades['profit'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['profit'].mean() if not losing_trades.empty else 0
    
    largest_win = winning_trades['profit'].max() if not winning_trades.empty else 0
    largest_loss = losing_trades['profit'].min() if not losing_trades.empty else 0
    
    # Duration metrics
    if 'duration' in trades:
        avg_duration = trades['duration'].mean()
        avg_win_duration = winning_trades['duration'].mean() if not winning_trades.empty else 0
        avg_loss_duration = losing_trades['duration'].mean() if not losing_trades.empty else 0
        avg_profit_per_day = trades['profit'].sum() / trades['duration'].sum() if trades['duration'].sum() > 0 else 0
    else:
        avg_duration = avg_win_duration = avg_loss_duration = avg_profit_per_day = 0
    
    # Consecutive win/loss streaks
    if num_trades > 0:
        is_win = trades['profit'] > 0
        win_streak = _find_max_streak(is_win)
        loss_streak = _find_max_streak(~is_win)
    else:
        win_streak = loss_streak = 0
    
    # Direction analysis if direction column exists
    long_win_rate = short_win_rate = 0
    if 'direction' in trades:
        long_trades = trades[trades['direction'] == 1]
        short_trades = trades[trades['direction'] == -1]
        
        long_win_rate = len(long_trades[long_trades['profit'] > 0]) / len(long_trades) if len(long_trades) > 0 else 0
        short_win_rate = len(short_trades[short_trades['profit'] > 0]) / len(short_trades) if len(short_trades) > 0 else 0
    
    # Risk-adjusted metrics if entry and exit prices are available
    risk_reward_ratio = avg_r_multiple = 0
    if all(col in trades.columns for col in ['entry_price', 'exit_price', 'stop_price']):
        # Calculate risk for each trade
        long_trades = trades[trades['direction'] == 1]
        short_trades = trades[trades['direction'] == -1]
        
        if not long_trades.empty:
            long_risk = abs(long_trades['entry_price'] - long_trades['stop_price'])
            long_reward = abs(long_trades['exit_price'] - long_trades['entry_price'])
            long_trades['risk_reward'] = long_reward / long_risk
            long_trades['r_multiple'] = long_trades['profit'] / long_risk
        
        if not short_trades.empty:
            short_risk = abs(short_trades['entry_price'] - short_trades['stop_price'])
            short_reward = abs(short_trades['exit_price'] - short_trades['entry_price'])
            short_trades['risk_reward'] = short_reward / short_risk
            short_trades['r_multiple'] = short_trades['profit'] / short_risk
        
        # Combine and calculate metrics
        if 'risk_reward' in trades.columns:
            risk_reward_ratio = trades['risk_reward'].mean()
        
        if 'r_multiple' in trades.columns:
            avg_r_multiple = trades['r_multiple'].mean()
    
    # Compile metrics
    metrics = {
        'num_trades': num_trades,
        'win_rate': win_rate * 100,  # Convert to percentage
        'profit_factor': profit_factor,
        'avg_profit': avg_profit,
        'avg_loss': avg_loss,
        'avg_duration': avg_duration,
        'avg_profit_per_day': avg_profit_per_day,
        'largest_win': largest_win,
        'largest_loss': largest_loss,
        'consecutive_wins': win_streak,
        'consecutive_losses': loss_streak,
        'avg_win_duration': avg_win_duration,
        'avg_loss_duration': avg_loss_duration,
        'long_win_rate': long_win_rate * 100 if 'direction' in trades else None,
        'short_win_rate': short_win_rate * 100 if 'direction' in trades else None,
        'risk_reward_ratio': risk_reward_ratio,
        'avg_r_multiple': avg_r_multiple
    }
    
    return metrics


def calculate_regime_performance(returns: pd.Series, 
                                regimes: pd.Series) -> Dict[str, Dict[str, float]]:
    """
    Calculate performance metrics by market regime.
    
    Args:
        returns: Series of strategy returns
        regimes: Series of regime labels with same index as returns
        
    Returns:
        Dictionary of performance metrics by regime
    """
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    if not isinstance(regimes, pd.Series):
        regimes = pd.Series(regimes)
    
    # Ensure alignment
    common_idx = returns.index.intersection(regimes.index)
    returns = returns.loc[common_idx]
    regimes = regimes.loc[common_idx]
    
    # Get unique regimes
    unique_regimes = regimes.unique()
    
    # Calculate metrics for each regime
    regime_metrics = {}
    
    for regime in unique_regimes:
        regime_returns = returns[regimes == regime]
        
        if len(regime_returns) > 5:  # Minimum data for meaningful metrics
            metrics = calculate_returns_metrics(regime_returns)
            regime_metrics[str(regime)] = metrics
    
    return regime_metrics


def calculate_factor_attribution(returns: pd.Series, 
                               factor_returns: Dict[str, pd.Series]) -> Dict[str, float]:
    """
    Perform factor attribution analysis.
    
    Args:
        returns: Series of strategy returns
        factor_returns: Dictionary of factor returns series
        
    Returns:
        Dictionary of factor exposures and metrics
    """
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    # Create DataFrame of factors
    factors_df = pd.DataFrame(factor_returns)
    
    # Ensure alignment with returns
    common_idx = returns.index.intersection(factors_df.index)
    if len(common_idx) == 0:
        raise ValueError("No overlapping dates between returns and factors")
    
    y = returns.loc[common_idx]
    X = factors_df.loc[common_idx]
    
    # Add constant for intercept
    X = sm.add_constant(X)
    
    # Run regression
    model = sm.OLS(y, X).fit()
    
    # Extract factor exposures (betas)
    factor_exposures = model.params.drop('const').to_dict()
    
    # Calculate metrics
    alpha = model.params['const'] * TRADING_DAYS_PER_YEAR  # Annualized alpha
    r_squared = model.rsquared
    
    # Calculate factor contributions
    factor_contributions = {}
    for factor, exposure in factor_exposures.items():
        factor_mean_return = factor_returns[factor].mean() * TRADING_DAYS_PER_YEAR  # Annualized
        factor_contributions[factor] = exposure * factor_mean_return
    
    # Calculate proportion of return explained by each factor
    strategy_return = returns.mean() * TRADING_DAYS_PER_YEAR  # Annualized
    proportion_explained = sum(factor_contributions.values()) / strategy_return if strategy_return != 0 else 0
    
    # Calculate idiosyncratic volatility
    y_pred = model.predict()
    residuals = y - y_pred
    idiosyncratic_vol = residuals.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    
    # Calculate information ratio based on residual returns
    residual_ir = (alpha / idiosyncratic_vol) if idiosyncratic_vol > 0 else 0
    
    # Compile results
    attribution = {
        'alpha': alpha * 100,  # Convert to percentage
        'r_squared': r_squared,
        'idiosyncratic_vol': idiosyncratic_vol * 100,
        'residual_ir': residual_ir,
        'proportion_explained': proportion_explained * 100,
        'factor_exposures': factor_exposures,
        'factor_contributions': {k: v * 100 for k, v in factor_contributions.items()}  # Convert to percentage
    }
    
    return attribution


def _calculate_omega_ratio(returns: pd.Series, threshold: float = 0) -> float:
    """Calculate Omega ratio."""
    returns_less_threshold = returns - threshold
    numer = returns_less_threshold[returns_less_threshold > 0].sum()
    denom = -returns_less_threshold[returns_less_threshold < 0].sum()
    
    return numer / denom if denom > 0 else np.inf


def _calculate_alpha(returns: pd.Series, benchmark_returns: pd.Series, 
                   risk_free_rate: float, beta: float) -> float:
    """Calculate Jensen's Alpha (annualized)."""
    alpha = returns.mean() - risk_free_rate - beta * (benchmark_returns.mean() - risk_free_rate)
    return alpha * TRADING_DAYS_PER_YEAR


def _calculate_r_squared(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """Calculate R-squared."""
    correlation = returns.corr(benchmark_returns)
    return correlation ** 2


def _calculate_value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Calculate Value at Risk using historical method."""
    return -np.percentile(returns, 100 * (1 - confidence))


def _calculate_conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Calculate Conditional Value at Risk / Expected Shortfall."""
    var = _calculate_value_at_risk(returns, confidence)
    return -returns[returns <= -var].mean() if len(returns[returns <= -var]) > 0 else var


def _find_max_streak(series: pd.Series) -> int:
    """Find the maximum streak of True values in a boolean series."""
    if series.empty:
        return 0
    
    # Convert to numpy for faster processing
    vals = series.values
    
    # Find positions where values change
    change_positions = np.where(np.diff(np.concatenate(([False], vals, [False]))))[0]
    
    # Calculate streaks
    streak_lengths = change_positions[1::2] - change_positions[::2]
    
    return max(streak_lengths) if len(streak_lengths) > 0 else 0


def plot_performance_dashboard(returns: pd.Series, 
                              benchmark_returns: Optional[pd.Series] = None,
                              trades: Optional[pd.DataFrame] = None,
                              title: str = "Strategy Performance") -> plt.Figure:
    """
    Create a comprehensive performance dashboard with multiple plots.
    
    Args:
        returns: Series of strategy returns
        benchmark_returns: Series of benchmark returns (optional)
        trades: DataFrame of trades (optional)
        title: Dashboard title
        
    Returns:
        Matplotlib figure with plots
    """
    # Validate inputs
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    if benchmark_returns is not None and not isinstance(benchmark_returns, pd.Series):
        benchmark_returns = pd.Series(benchmark_returns)
    
    # Calculate metrics
    metrics = calculate_returns_metrics(returns, benchmark_returns=benchmark_returns)
    drawdown_metrics = calculate_drawdown_metrics(returns)
    
    # Create figure
    fig = plt.figure(figsize=(15, 12))
    fig.suptitle(title, fontsize=16)
    
    # Grid specification
    gs = fig.add_gridspec(3, 3)
    
    # 1. Cumulative returns plot
    ax1 = fig.add_subplot(gs[0, :2])
    
    # Calculate cumulative returns
    cum_returns = (1 + returns).cumprod() - 1
    
    cum_returns.plot(ax=ax1, label=f'Strategy ({metrics["annual_return"]:.1f}% p.a.)')
    
    if benchmark_returns is not None:
        cum_benchmark = (1 + benchmark_returns).cumprod() - 1
        cum_benchmark.plot(ax=ax1, label='Benchmark', alpha=0.7)
    
    ax1.axhline(y=0, color='black', linestyle='-', alpha=0.2)
    ax1.set_title('Cumulative Returns')
    ax1.set_ylabel('Returns (%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Drawdown plot
    ax2 = fig.add_subplot(gs[1, :2])
    
    equity_curve = (1 + returns).cumprod()
    peak = equity_curve.cummax()
    drawdown = (equity_curve / peak - 1) * 100
    
    ax2.fill_between(drawdown.index, drawdown, 0, color='red', alpha=0.3)
    ax2.plot(drawdown.index, drawdown, color='red', alpha=0.5)
    ax2.set_title(f'Drawdown (Max: {metrics["max_drawdown"]:.1f}%)')
    ax2.set_ylabel('Drawdown (%)')
    ax2.grid(True, alpha=0.3)
    
    # 3. Monthly returns heatmap
    ax3 = fig.add_subplot(gs[0, 2])
    
    if isinstance(returns.index, pd.DatetimeIndex) and len(returns) > 30:
        monthly_returns = (1 + returns).resample('M').prod() - 1
        monthly_returns_table = pd.DataFrame({
            'year': monthly_returns.index.year,
            'month': monthly_returns.index.month,
            'return': monthly_returns.values * 100  # Convert to percentage
        })
        
        # Pivot table
        monthly_pivot = monthly_returns_table.pivot_table(
            index='year', columns='month', values='return'
        )
        
        # Plot heatmap
        sns.heatmap(monthly_pivot, ax=ax3, cmap='RdYlGn', center=0, annot=True, 
                   fmt='.1f', cbar=False, linewidths=.5)
        ax3.set_title('Monthly Returns (%)')
        ax3.set_xlabel('')
        ax3.set_ylabel('')
    else:
        ax3.text(0.5, 0.5, 'Insufficient data\nfor monthly returns', 
                ha='center', va='center')
        ax3.axis('off')
    
    # 4. Return distribution
    ax4 = fig.add_subplot(gs[1, 2])
    
    sns.histplot(returns * 100, kde=True, ax=ax4, color='skyblue')
    ax4.axvline(x=0, color='red', linestyle='--', alpha=0.7)
    ax4.set_title('Return Distribution')
    ax4.set_xlabel('Return (%)')
    ax4.grid(True, alpha=0.3)
    
    # 5. Performance metrics table
    ax5 = fig.add_subplot(gs[2, 0])
    ax5.axis('off')
    
    metrics_text = [
        f"Annual Return: {metrics['annual_return']:.2f}%",
        f"Volatility: {metrics['volatility']:.2f}%",
        f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}",
        f"Sortino Ratio: {metrics['sortino_ratio']:.2f}",
        f"Max Drawdown: {metrics['max_drawdown']:.2f}%",
        f"Calmar Ratio: {metrics['calmar_ratio']:.2f}",
        f"VaR (95%): {metrics['var_95']:.2f}%",
        f"CVaR (95%): {metrics['cvar_95']:.2f}%"
    ]
    
    if benchmark_returns is not None:
        metrics_text.extend([
            f"Beta: {metrics['beta']:.2f}",
            f"Alpha: {metrics['alpha']:.2f}%",
            f"Information Ratio: {metrics['information_ratio']:.2f}"
        ])
    
    metrics_table = ax5.table(
        cellText=[[m] for m in metrics_text],
        cellLoc='left',
        loc='center',
        edges='open'
    )
    metrics_table.auto_set_font_size(False)
    metrics_table.set_fontsize(10)
    metrics_table.scale(1, 1.5)
    
    ax5.set_title('Performance Metrics')
    
    # 6. Drawdown metrics table
    ax6 = fig.add_subplot(gs[2, 1])
    ax6.axis('off')
    
    drawdown_text = [
        f"Recovery Factor: {drawdown_metrics['recovery_factor']:.2f}",
        f"Pain Index: {drawdown_metrics['pain_index']:.2f}%",
        f"Pain Ratio: {drawdown_metrics['pain_ratio']:.2f}",
        f"Avg Drawdown: {drawdown_metrics['avg_drawdown']:.2f}%",
        f"Avg Recovery: {drawdown_metrics['avg_recovery_time']:.1f} days",
        f"Drawdown Frequency: {drawdown_metrics['drawdown_frequency']:.1f}/yr"
    ]
    
    drawdown_table = ax6.table(
        cellText=[[m] for m in drawdown_text],
        cellLoc='left',
        loc='center',
        edges='open'
    )
    drawdown_table.auto_set_font_size(False)
    drawdown_table.set_fontsize(10)
    drawdown_table.scale(1, 1.5)
    
    ax6.set_title('Drawdown Metrics')
    
    # 7. Trade metrics if available
    ax7 = fig.add_subplot(gs[2, 2])
    ax7.axis('off')
    
    if trades is not None and not trades.empty:
        trade_metrics = calculate_trade_metrics(trades)
        
        trade_text = [
            f"Win Rate: {trade_metrics['win_rate']:.1f}%",
            f"Profit Factor: {trade_metrics['profit_factor']:.2f}",
            f"Trades: {trade_metrics['num_trades']}",
            f"Avg Profit: {trade_metrics['avg_profit']:.2f}",
            f"Avg Loss: {trade_metrics['avg_loss']:.2f}",
            f"Max Consecutive Wins: {trade_metrics['consecutive_wins']}"
        ]
        
        trade_table = ax7.table(
            cellText=[[m] for m in trade_text],
            cellLoc='left',
            loc='center',
            edges='open'
        )
        trade_table.auto_set_font_size(False)
        trade_table.set_fontsize(10)
        trade_table.scale(1, 1.5)
        
        ax7.set_title('Trade Metrics')
    else:
        ax7.text(0.5, 0.5, 'No trade data available', ha='center', va='center')
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    
    return fig


def analyze_strategy_performance(returns: pd.Series, 
                               benchmark_returns: Optional[pd.Series] = None,
                               trades: Optional[pd.DataFrame] = None,
                               plot: bool = True,
                               save_path: Optional[str] = None) -> Dict[str, Dict[str, float]]:
    """
    Comprehensive strategy performance analysis, including metrics and visualization.
    
    Args:
        returns: Series of strategy returns
        benchmark_returns: Series of benchmark returns (optional)
        trades: DataFrame of trades (optional)
        plot: Whether to generate and display plots
        save_path: Path to save performance report (optional)
        
    Returns:
        Dictionary of performance metrics categories
    """
    # Calculate all metrics
    return_metrics = calculate_returns_metrics(returns, benchmark_returns=benchmark_returns)
    drawdown_metrics = calculate_drawdown_metrics(returns)
    
    # Trade metrics if available
    trade_metrics = None
    if trades is not None and not trades.empty:
        trade_metrics = calculate_trade_metrics(trades)
    
    # Create performance dashboard
    if plot:
        fig = plot_performance_dashboard(returns, benchmark_returns, trades)
        
        if save_path:
            fig.savefig(save_path, dpi=100, bbox_inches='tight')
            plt.close(fig)
        else:
            plt.show()
    
    # Compile results
    results = {
        'return_metrics': return_metrics,
        'drawdown_metrics': drawdown_metrics
    }
    
    if trade_metrics:
        results['trade_metrics'] = trade_metrics
    
    return results


# Import for factor analysis
try:
    import statsmodels.api as sm
except ImportError:
    pass 