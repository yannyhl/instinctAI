"""
Portfolio Risk Visualization (Part 2)
----------------------------------
Additional reporting and optimization visualization components for portfolio risk management.

This module provides additional reporting tools for the PortfolioRiskController.
It includes methods for generating detailed risk reports, stress testing outputs,
and optimization visualizations.

This is a companion module to portfolio_risk.py and portfolio_risk_viz.py, and will 
be merged into the main PortfolioRiskController class.
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
import json

# Configure logging
logger = logging.getLogger(__name__)

class PortfolioRiskVizAdditional:
    """
    Additional visualization and reporting functions for portfolio risk management.
    
    This class contains advanced methods for portfolio risk visualization and reporting
    that will be integrated into the PortfolioRiskController class.
    """

    @staticmethod
    def generate_risk_report(
        portfolio_state: Dict[str, Any],
        include_history: bool = True,
        include_correlation: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive risk report for the portfolio.
        
        Args:
            portfolio_state: Dictionary with portfolio state
            include_history: Whether to include historical data
            include_correlation: Whether to include correlation analysis
            
        Returns:
            Dictionary with detailed risk metrics
        """
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
    
    @staticmethod
    def plot_optimization_comparison(
        current_allocation: Dict[str, float],
        optimal_allocation: Dict[str, float]
    ) -> plt.Figure:
        """
        Plot comparison between current and optimal allocations.
        
        Args:
            current_allocation: Dictionary with current allocations by symbol
            optimal_allocation: Dictionary with optimal allocations by symbol
            
        Returns:
            Matplotlib figure object
        """
        if not current_allocation or not optimal_allocation:
            logger.warning("Empty allocation data, cannot plot")
            return None
        
        # Get unique symbols across both allocations
        all_symbols = sorted(set(list(current_allocation.keys()) + list(optimal_allocation.keys())))
        
        # Create data for plotting
        current_values = [current_allocation.get(symbol, 0) * 100 for symbol in all_symbols]
        optimal_values = [optimal_allocation.get(symbol, 0) * 100 for symbol in all_symbols]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, max(6, len(all_symbols) * 0.4)))
        
        # Set position and width for bars
        pos = np.arange(len(all_symbols))
        width = 0.35
        
        # Create bars
        current_bars = ax.barh(pos - width/2, current_values, width, label='Current', color='skyblue', alpha=0.8)
        optimal_bars = ax.barh(pos + width/2, optimal_values, width, label='Optimal', color='coral', alpha=0.8)
        
        # Add values on bars
        for bars, values in zip([current_bars, optimal_bars], [current_values, optimal_values]):
            for i, bar in enumerate(bars):
                if values[i] > 1:  # Only show if allocation > 1%
                    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                           f'{values[i]:.1f}%', va='center')
        
        # Customize plot
        ax.set_yticks(pos)
        ax.set_yticklabels(all_symbols)
        ax.set_xlabel('Allocation (%)')
        ax.set_title('Current vs Optimal Portfolio Allocation')
        ax.xaxis.set_major_formatter(PercentFormatter())
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_rebalance_trades(
        rebalance_trades: Dict[str, Dict[str, float]]
    ) -> plt.Figure:
        """
        Plot rebalance trades as a bar chart.
        
        Args:
            rebalance_trades: Dictionary with rebalance trade details
            
        Returns:
            Matplotlib figure object
        """
        if not rebalance_trades:
            logger.warning("No rebalance trades to plot")
            return None
        
        # Extract trade data
        symbols = []
        value_changes = []
        colors = []
        
        for symbol, trade in rebalance_trades.items():
            symbols.append(symbol)
            value_changes.append(trade['value_change'])
            # Set color based on trade direction
            colors.append('green' if trade['value_change'] > 0 else 'red')
        
        # Sort by value change
        sort_idx = np.argsort(value_changes)
        symbols = [symbols[i] for i in sort_idx]
        value_changes = [value_changes[i] for i in sort_idx]
        colors = [colors[i] for i in sort_idx]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, max(6, len(symbols) * 0.4)))
        
        # Plot value changes
        bars = ax.barh(symbols, value_changes, color=colors, alpha=0.7)
        
        # Add values on bars
        for i, bar in enumerate(bars):
            ax.text(bar.get_width() + np.sign(bar.get_width()) * 0.5, bar.get_y() + bar.get_height()/2, 
                   f'${value_changes[i]:.2f}', va='center', ha='left' if value_changes[i] > 0 else 'right')
        
        ax.set_title('Rebalance Trades')
        ax.set_xlabel('Value Change ($)')
        ax.grid(True, alpha=0.3)
        ax.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def run_stress_test(
        positions: Dict[str, Dict[str, Any]],
        current_equity: float,
        scenarios: Dict[str, Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Run stress tests on the portfolio.
        
        Args:
            positions: Dictionary of positions
            current_equity: Current portfolio equity
            scenarios: Dictionary of stress scenarios
            
        Returns:
            Dictionary with stress test results
        """
        if not positions:
            logger.warning("No positions for stress testing")
            return {'error': 'No positions for stress testing'}
        
        # Default scenarios if none provided
        if scenarios is None:
            scenarios = {
                'market_crash': {'description': 'Market crash (-20%)', 'factor': -0.20},
                'correction': {'description': 'Market correction (-10%)', 'factor': -0.10},
                'volatility_spike': {'description': 'Volatility spike (+50%)', 'factor': -0.15},
                'bullish': {'description': 'Bullish scenario (+10%)', 'factor': 0.10},
                'category_crash': {'factor_by_category': {'crypto_major': -0.30, 'crypto_alt': -0.40}}
            }
        
        results = {}
        
        # Process each scenario
        for scenario_name, scenario_data in scenarios.items():
            # Portfolio impact
            total_pnl = 0
            position_impacts = {}
            
            if 'factor' in scenario_data:
                # Apply uniform factor to all positions
                factor = scenario_data['factor']
                
                for symbol, position in positions.items():
                    # Calculate impact based on position type
                    if position['trade_type'] == 'long':
                        impact = position['value'] * factor
                    else:
                        impact = position['value'] * -factor
                    
                    total_pnl += impact
                    position_impacts[symbol] = {
                        'current_value': position['value'],
                        'impact': impact,
                        'impact_pct': impact / position['value'] * 100 if position['value'] > 0 else 0
                    }
            
            elif 'factor_by_category' in scenario_data:
                # Apply different factors by category
                factors = scenario_data['factor_by_category']
                
                for symbol, position in positions.items():
                    # Get factor for this category
                    category = position['category']
                    factor = factors.get(category, 0)
                    
                    # Calculate impact based on position type
                    if position['trade_type'] == 'long':
                        impact = position['value'] * factor
                    else:
                        impact = position['value'] * -factor
                    
                    total_pnl += impact
                    position_impacts[symbol] = {
                        'current_value': position['value'],
                        'impact': impact,
                        'impact_pct': impact / position['value'] * 100 if position['value'] > 0 else 0
                    }
            
            # Calculate overall portfolio impact
            new_equity = current_equity + total_pnl
            impact_pct = total_pnl / current_equity * 100 if current_equity > 0 else 0
            
            # Store results
            results[scenario_name] = {
                'description': scenario_data.get('description', scenario_name),
                'total_pnl': total_pnl,
                'impact_pct': impact_pct,
                'new_equity': new_equity,
                'position_impacts': position_impacts
            }
        
        return results
    
    @staticmethod
    def plot_stress_test_results(
        stress_results: Dict[str, Dict[str, Any]]
    ) -> plt.Figure:
        """
        Plot stress test results as a horizontal bar chart.
        
        Args:
            stress_results: Dictionary with stress test results
            
        Returns:
            Matplotlib figure object
        """
        if not stress_results:
            logger.warning("No stress test results to plot")
            return None
        
        # Extract scenario names and impacts
        scenarios = []
        impacts = []
        colors = []
        
        for scenario, result in stress_results.items():
            if 'description' in result:
                scenarios.append(result['description'])
            else:
                scenarios.append(scenario)
            
            impacts.append(result['impact_pct'])
            colors.append('green' if result['impact_pct'] >= 0 else 'red')
        
        # Sort by impact
        sort_idx = np.argsort(impacts)
        scenarios = [scenarios[i] for i in sort_idx]
        impacts = [impacts[i] for i in sort_idx]
        colors = [colors[i] for i in sort_idx]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, max(6, len(scenarios) * 0.4)))
        
        # Plot impacts
        bars = ax.barh(scenarios, impacts, color=colors, alpha=0.7)
        
        # Add values on bars
        for i, bar in enumerate(bars):
            ax.text(bar.get_width() + np.sign(bar.get_width()) * 0.5, bar.get_y() + bar.get_height()/2, 
                   f'{impacts[i]:.2f}%', va='center', ha='left' if impacts[i] > 0 else 'right')
        
        ax.set_title('Stress Test Results - Portfolio Impact')
        ax.set_xlabel('Impact (%)')
        ax.xaxis.set_major_formatter(PercentFormatter())
        ax.grid(True, alpha=0.3)
        ax.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_risk_contribution(
        positions: Dict[str, Dict[str, Any]],
        current_equity: float
    ) -> plt.Figure:
        """
        Plot risk contribution of each position.
        
        Args:
            positions: Dictionary of positions
            current_equity: Current portfolio equity
            
        Returns:
            Matplotlib figure object
        """
        if not positions:
            logger.warning("No positions to plot risk contribution")
            return None
        
        # Calculate risk contribution
        risk_contributions = {}
        total_risk = sum(p['risk_amount'] for p in positions.values())
        
        for symbol, position in positions.items():
            risk_contributions[symbol] = position['risk_amount'] / total_risk if total_risk > 0 else 0
        
        # Sort by risk contribution
        sorted_symbols = sorted(risk_contributions.keys(), key=lambda x: risk_contributions[x], reverse=True)
        values = [risk_contributions[s] * 100 for s in sorted_symbols]  # Convert to percentage
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Pie chart for risk contribution
        ax.pie(values, labels=sorted_symbols, autopct='%1.1f%%', startangle=90)
        ax.set_title('Risk Contribution by Position')
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def export_risk_report(
        report: Dict[str, Any],
        file_format: str = 'json',
        file_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Export risk report to file.
        
        Args:
            report: Risk report dictionary
            file_format: Output format ('json' or 'csv')
            file_path: Path to save the report (optional)
            
        Returns:
            File path if saved, None otherwise
        """
        if not report:
            logger.warning("Empty report, nothing to export")
            return None
        
        # Generate default filename if not provided
        if file_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = f"risk_report_{timestamp}.{file_format}"
        
        try:
            if file_format == 'json':
                # Handle datetime objects for JSON serialization
                def json_serial(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    raise TypeError(f"Type {type(obj)} not serializable")
                
                with open(file_path, 'w') as f:
                    json.dump(report, f, default=json_serial, indent=4)
                
                logger.info(f"Risk report exported to {file_path}")
                return file_path
            
            elif file_format == 'csv':
                # For CSV, we need to flatten the report
                flat_data = []
                
                # Add summary data
                summary = report.get('summary', {})
                flat_data.append({
                    'section': 'summary',
                    'metric': 'account_equity',
                    'value': summary.get('account_equity', 0)
                })
                flat_data.append({
                    'section': 'summary',
                    'metric': 'total_exposure',
                    'value': summary.get('total_exposure', 0)
                })
                # ... add more summary metrics
                
                # Add position data
                for position in report.get('positions', []):
                    for key, value in position.items():
                        flat_data.append({
                            'section': 'position',
                            'metric': f"{position['symbol']}_{key}",
                            'value': value
                        })
                
                # Convert to DataFrame and save
                df = pd.DataFrame(flat_data)
                df.to_csv(file_path, index=False)
                
                logger.info(f"Risk report exported to {file_path}")
                return file_path
            
            else:
                logger.error(f"Unsupported file format: {file_format}")
                return None
                
        except Exception as e:
            logger.error(f"Error exporting risk report: {str(e)}")
            return None 