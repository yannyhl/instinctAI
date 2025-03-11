"""
Portfolio Risk Integration Guide
------------------------------
This file provides guidance on how to integrate the visualization and reporting 
components from portfolio_risk_viz.py and portfolio_risk_viz_part2.py into the main
portfolio_risk.py file.

The integration steps below show how to properly merge the code.
"""

# Integration Steps:

"""
STEP 1: Update Imports
---------------------
Add these imports to the top of portfolio_risk.py if they're not already there:

```python
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
import seaborn as sns
import json
```
"""

"""
STEP 2: Add Visualization Methods to PortfolioRiskController
---------------------------------------------------------
Add these methods to the PortfolioRiskController class in portfolio_risk.py:

1. First, replace the existing plot_risk_allocation method with the enhanced version:

```python
def plot_risk_allocation(self) -> plt.Figure:
    \"\"\"
    Plot current risk allocation by category and correlation group.
    
    Returns:
        Matplotlib figure object
    \"\"\"
    if not self.positions:
        logger.warning("No positions to plot risk allocation")
        return None
    
    # Calculate risk by category
    risk_by_category = {}
    for symbol, position in self.positions.items():
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
    symbols = list(self.positions.keys())
    allocations = [self.positions[s]['value'] / self.current_equity for s in symbols]
    risks = [self.positions[s]['risk_amount'] / self.current_equity for s in symbols]
    
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
```

2. Add the plot_equity_curve method:

```python
def plot_equity_curve(
    self,
    highlight_drawdowns: bool = True,
    drawdown_threshold: float = 0.05
) -> plt.Figure:
    \"\"\"
    Plot equity curve with optional drawdown highlighting.
    
    Args:
        highlight_drawdowns: Whether to highlight drawdown periods
        drawdown_threshold: Threshold for highlighting drawdowns
        
    Returns:
        Matplotlib figure object
    \"\"\"
    if self.equity_curve.empty:
        logger.warning("Empty equity curve, cannot plot")
        return None
    
    # Create figure
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot equity curve
    ax1 = axes[0]
    ax1.plot(self.equity_curve.index, self.equity_curve.values, 'b-', linewidth=2)
    ax1.set_title('Portfolio Equity Curve')
    ax1.set_ylabel('Equity')
    ax1.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # Highlight drawdown periods if requested
    if highlight_drawdowns and not self.drawdown_history.empty:
        # Find periods where drawdown exceeds threshold
        drawdown_periods = []
        in_drawdown = False
        start_idx = None
        
        for i, (date, dd) in enumerate(self.drawdown_history.items()):
            if not in_drawdown and dd >= drawdown_threshold:
                # Start of drawdown period
                in_drawdown = True
                start_idx = i
            elif in_drawdown and dd < drawdown_threshold:
                # End of drawdown period
                in_drawdown = False
                drawdown_periods.append((
                    self.drawdown_history.index[start_idx],
                    self.drawdown_history.index[i]
                ))
        
        # Add last period if still in drawdown
        if in_drawdown:
            drawdown_periods.append((
                self.drawdown_history.index[start_idx],
                self.drawdown_history.index[-1]
            ))
        
        # Highlight drawdown periods
        for start, end in drawdown_periods:
            ax1.axvspan(start, end, alpha=0.2, color='red')
    
    # Plot drawdown
    ax2 = axes[1]
    if not self.drawdown_history.empty:
        ax2.fill_between(
            self.drawdown_history.index,
            0,
            self.drawdown_history.values * 100,  # Convert to percentage
            color='red',
            alpha=0.3
        )
        ax2.plot(self.drawdown_history.index, self.drawdown_history.values * 100, 'r-', linewidth=1)
        
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
```

3. Add other visualization methods from portfolio_risk_viz.py:

```python
def plot_risk_metrics(self) -> plt.Figure:
    \"\"\"
    Plot risk metrics history (VaR, CVaR).
    
    Returns:
        Matplotlib figure object
    \"\"\"
    if not self.var_history or not self.cvar_history:
        logger.warning("Empty risk metrics history, cannot plot")
        return None
    
    # Extract dates from equity curve if available
    if not self.equity_curve.empty and len(self.equity_curve) >= len(self.var_history):
        # Use the most recent dates from equity curve
        dates = self.equity_curve.index[-len(self.var_history):]
    else:
        # Create default dates
        end_date = datetime.now()
        dates = [end_date - timedelta(days=i) for i in range(len(self.var_history))]
        dates.reverse()
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot VaR and CVaR
    ax.plot(dates, [v * 100 for v in self.var_history], 'b-', linewidth=2, label='VaR (95%)')
    ax.plot(dates, [v * 100 for v in self.cvar_history], 'r-', linewidth=2, label='CVaR (95%)')
    
    ax.set_title('Risk Metrics History')
    ax.set_ylabel('Value at Risk (%)')
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Format x-axis dates
    if isinstance(dates[0], datetime):
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    return fig

def plot_correlation_heatmap(self) -> plt.Figure:
    \"\"\"
    Plot correlation heatmap between assets/strategies.
    
    Returns:
        Matplotlib figure object
    \"\"\"
    if self.correlation_matrix.empty:
        logger.warning("Empty correlation matrix, cannot plot")
        return None
    
    # Create figure
    plt.figure(figsize=(10, 8))
    
    # Create heatmap
    mask = np.zeros_like(self.correlation_matrix, dtype=bool)
    mask[np.triu_indices_from(mask)] = True
    
    # Set up the matplotlib figure
    f, ax = plt.subplots(figsize=(11, 9))
    
    # Draw the heatmap with the mask and correct aspect ratio
    sns.heatmap(
        self.correlation_matrix,
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

def plot_position_performance(self) -> plt.Figure:
    \"\"\"
    Plot position performance as a horizontal bar chart.
    
    Returns:
        Matplotlib figure object
    \"\"\"
    if not self.positions:
        logger.warning("No positions to plot performance")
        return None
    
    # Extract position data
    symbols = []
    pnl_pcts = []
    pnl_amts = []
    colors = []
    
    for symbol, position in self.positions.items():
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
```

4. Add the additional methods from portfolio_risk_viz_part2.py:

```python
def generate_risk_report(self, include_history: bool = True, include_correlation: bool = True) -> Dict[str, Any]:
    \"\"\"
    Generate a comprehensive risk report for the portfolio.
    
    Args:
        include_history: Whether to include historical data
        include_correlation: Whether to include correlation analysis
        
    Returns:
        Dictionary with detailed risk metrics
    \"\"\"
    # Get portfolio state
    portfolio_state = self.get_portfolio_state()
    
    # Start with basic portfolio state
    report = {
        'timestamp': datetime.now(),
        'summary': {
            'account_equity': portfolio_state.get('current_equity', 0),
            'total_positions': len(portfolio_state.get('positions', {})),
            'total_exposure': portfolio_state.get('total_exposure', 0),
            'total_exposure_pct': portfolio_state.get('total_exposure_pct', 0) * 100,
            'total_risk': portfolio_state.get('total_risk', 0),
            'total_risk_pct': portfolio_state.get('total_risk_pct', 0) * 100,
            'leverage': portfolio_state.get('leverage', 0),
            'current_drawdown': portfolio_state.get('current_drawdown', 0) * 100,
            'sharpe_ratio': portfolio_state.get('sharpe_ratio', 0),
            'sortino_ratio': portfolio_state.get('sortino_ratio', 0),
            'calmar_ratio': portfolio_state.get('calmar_ratio', 0),
            'in_drawdown_control': portfolio_state.get('in_drawdown_control', False)
        }
    }
    
    # Add category allocations
    report['allocations'] = {
        'by_category': {
            k: v for k, v in portfolio_state.get('category_allocations_pct', {}).items()
        },
        'risk_by_category': {
            k: v for k, v in portfolio_state.get('risk_pct_by_category', {}).items()
        }
    }
    
    # Add position details
    positions = portfolio_state.get('positions', {})
    position_details = []
    
    for symbol, pos in positions.items():
        position_details.append({
            'symbol': symbol,
            'type': pos.get('trade_type', 'unknown'),
            'category': pos.get('category', 'default'),
            'size': pos.get('position_size', 0),
            'value': pos.get('value', 0),
            'allocation_pct': (pos.get('value', 0) / portfolio_state.get('current_equity', 1)) * 100,
            'entry_price': pos.get('entry_price', 0),
            'current_price': pos.get('current_price', 0),
            'stop_price': pos.get('stop_price', 0),
            'risk_amount': pos.get('risk_amount', 0),
            'risk_pct': pos.get('risk_pct', 0) * 100,
            'pnl_amount': pos.get('pnl_amount', 0),
            'pnl_pct': pos.get('pnl_pct', 0) * 100,
            'entry_time': pos.get('entry_time', datetime.now()).isoformat(),
            'days_held': (datetime.now() - pos.get('entry_time', datetime.now())).days
        })
    
    report['positions'] = position_details
    
    # Add historical data if requested
    if include_history and 'historical' in portfolio_state:
        history = portfolio_state['historical']
        
        # Convert time series data to list of dicts for JSON compatibility
        if 'equity_curve' in history and not history['equity_curve'].empty:
            report['history'] = {
                'equity_curve': [
                    {'date': date.isoformat(), 'equity': value}
                    for date, value in history['equity_curve'].items()
                ],
                'drawdown_history': [
                    {'date': date.isoformat(), 'drawdown': value * 100}
                    for date, value in history.get('drawdown_history', pd.Series()).items()
                ],
                'var_history': [v * 100 for v in history.get('var_history', [])],
                'cvar_history': [v * 100 for v in history.get('cvar_history', [])]
            }
        else:
            report['history'] = {
                'equity_curve': [],
                'drawdown_history': [],
                'var_history': [],
                'cvar_history': []
            }
    
    # Add correlation analysis if requested
    if include_correlation and 'correlation_analysis' in portfolio_state:
        corr_analysis = portfolio_state['correlation_analysis']
        report['correlation'] = {
            'high_correlations': corr_analysis.get('high_correlations', []),
            # Simplified correlation matrix representation
            'matrix_summary': {
                'size': corr_analysis.get('correlation_matrix', {}).get('shape', (0, 0)),
                'avg_correlation': np.mean(np.abs(np.array(
                    list(corr_analysis.get('correlation_matrix', {}).values())
                ))) if corr_analysis.get('correlation_matrix') else 0
            }
        }
    
    # Add optimization results if available
    if 'optimization' in portfolio_state:
        opt = portfolio_state['optimization']
        report['optimization'] = {
            'rebalance_needed': opt.get('rebalance_needed', False),
            'optimal_allocation': {
                k: v * 100 for k, v in opt.get('optimal_allocation', {}).items()
            },
            'rebalance_trade_count': len(opt.get('rebalance_trades', {}))
        }
    
    return report
```

5. Then add the remaining advanced methods from portfolio_risk_viz_part2.py:

- plot_optimization_comparison
- plot_rebalance_trades
- run_stress_test
- plot_stress_test_results
- plot_risk_contribution
- export_risk_report

These methods should be copied in full from portfolio_risk_viz_part2.py, but adjusted
to use the class's data members rather than taking parameters.
"""

"""
STEP 3: Update get_portfolio_state Method
--------------------------------------
Update the get_portfolio_state method to include all necessary data for visualization:

```python
def get_portfolio_state(self) -> Dict[str, Any]:
    \"\"\"
    Get current portfolio state including positions, allocations, and risk metrics.
    
    Returns:
        Dictionary with comprehensive portfolio state
    \"\"\"
    # Calculate total exposure and risk
    total_exposure = sum(p['value'] for p in self.positions.values())
    total_risk = sum(p['risk_amount'] for p in self.positions.values())
    
    # Calculate leverage
    leverage = total_exposure / self.current_equity if self.current_equity > 0 else 0
    
    # Calculate exposure and risk by category
    exposure_by_category = {}
    risk_by_category = {}
    
    for symbol, position in self.positions.items():
        category = position['category']
        if category not in exposure_by_category:
            exposure_by_category[category] = 0
            risk_by_category[category] = 0
        
        exposure_by_category[category] += position['value']
        risk_by_category[category] += position['risk_amount']
    
    # Calculate exposure and risk percentages
    exposure_pct_by_category = {k: v / self.current_equity for k, v in exposure_by_category.items()}
    risk_pct_by_category = {k: v / self.current_equity for k, v in risk_by_category.items()}
    
    # Get latest risk metrics
    var_95 = self.var_history[-1] if self.var_history else 0
    cvar_95 = self.cvar_history[-1] if self.cvar_history else 0
    
    # Prepare correlation analysis
    correlation_analysis = {}
    if not self.correlation_matrix.empty:
        # Find highest correlations
        corr_matrix = self.correlation_matrix.copy()
        np.fill_diagonal(corr_matrix.values, 0)  # Remove self-correlations
        
        # Get highest absolute correlations
        high_corrs = []
        for i in range(len(corr_matrix.index)):
            for j in range(i+1, len(corr_matrix.columns)):
                corr = corr_matrix.iloc[i, j]
                if abs(corr) >= 0.5:  # Threshold for high correlation
                    high_corrs.append({
                        'symbol1': corr_matrix.index[i],
                        'symbol2': corr_matrix.columns[j],
                        'correlation': corr
                    })
        
        # Sort by absolute correlation
        high_corrs.sort(key=lambda x: abs(x['correlation']), reverse=True)
        
        correlation_analysis = {
            'high_correlations': high_corrs[:10],  # Top 10 highest correlations
            'correlation_matrix': self.correlation_matrix.to_dict()
        }
    
    # Create portfolio state dictionary
    portfolio_state = {
        'timestamp': datetime.now(),
        'account_size': self.account_size,
        'current_equity': self.current_equity,
        'peak_equity': self.peak_equity,
        'current_drawdown': self.current_drawdown,
        'positions': {symbol: pos.copy() for symbol, pos in self.positions.items()},
        'total_positions': len(self.positions),
        'total_exposure': total_exposure,
        'total_exposure_pct': total_exposure / self.current_equity if self.current_equity > 0 else 0,
        'total_risk': total_risk,
        'total_risk_pct': total_risk / self.current_equity if self.current_equity > 0 else 0,
        'leverage': leverage,
        'category_allocations': self.category_allocations.copy(),
        'category_allocations_pct': exposure_pct_by_category,
        'risk_by_category': risk_by_category,
        'risk_pct_by_category': risk_pct_by_category,
        'correlation_groups': self.correlation_groups.copy(),
        'in_drawdown_control': self.in_drawdown_control,
        'var_95_pct': var_95,
        'cvar_95_pct': cvar_95,
        'sharpe_ratio': self.sharpe_ratio,
        'sortino_ratio': self.sortino_ratio,
        'calmar_ratio': self.calmar_ratio,
        'correlation_analysis': correlation_analysis,
        'historical': {
            'equity_curve': self.equity_curve.copy(),
            'drawdown_history': self.drawdown_history.copy(),
            'var_history': self.var_history.copy() if self.var_history else [],
            'cvar_history': self.cvar_history.copy() if self.cvar_history else []
        },
        'optimization': {
            'optimal_allocation': self.optimize_portfolio_allocation(),
            'rebalance_needed': self.check_rebalance_needed(),
            'rebalance_trades': self.get_rebalance_trades() if self.check_rebalance_needed() else {}
        }
    }
    
    return portfolio_state
```
"""

"""
FINAL STEPS:
-----------
1. Remove any duplicate or redundant methods
2. Ensure all visualization methods are correctly using class data members
3. Update method docstrings as needed
4. Test each visualization method individually
""" 