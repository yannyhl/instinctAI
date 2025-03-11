"""
Performance Dashboard View

This module provides a comprehensive view for monitoring and analyzing portfolio and 
strategy performance metrics, including returns, drawdowns, risk-adjusted metrics,
and benchmark comparisons.

The dashboard includes interactive charts, performance tables, and customizable
date ranges to analyze performance across different time periods.
"""

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Union

# Import core components
from advanced_trading.core.observability import get_logger
from advanced_trading.dashboard.core import DashboardState, DashboardController

# Initialize logger
logger = get_logger(__name__)


def create_performance_dashboard_view(state: DashboardState, controller: DashboardController) -> html.Div:
    """
    Create the performance dashboard view.
    
    Args:
        state: Current dashboard state
        controller: Dashboard controller for actions
        
    Returns:
        html.Div: The performance dashboard view
    """
    view_id = "performance-dashboard-view"
    
    # Header with date range selection
    header = dbc.Row([
        dbc.Col([
            html.H3("Performance Dashboard", className="mb-3")
        ], width=6),
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    html.Label("Date Range"),
                    dcc.DatePickerRange(
                        id="performance-date-range",
                        start_date=datetime.now() - timedelta(days=90),
                        end_date=datetime.now(),
                        display_format="YYYY-MM-DD",
                        className="w-100"
                    )
                ], width=8),
                dbc.Col([
                    html.Label("Presets"),
                    dbc.Select(
                        id="date-range-preset",
                        options=[
                            {"label": "Last 30 Days", "value": "30d"},
                            {"label": "Last 90 Days", "value": "90d"},
                            {"label": "Year to Date", "value": "ytd"},
                            {"label": "Last 1 Year", "value": "1y"},
                            {"label": "Last 3 Years", "value": "3y"},
                            {"label": "Max", "value": "max"}
                        ],
                        value="90d",
                        className="mt-1"
                    )
                ], width=4)
            ])
        ], width=6)
    ], className="mb-4")
    
    # Performance summary cards
    summary_cards = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Total Return", className="card-title text-center mb-1"),
                    html.H3(
                        id="total-return-value",
                        className="text-center",
                        children="23.5%"
                    ),
                    html.P(
                        id="total-return-vs-benchmark",
                        className="text-center text-success mb-0",
                        children="+8.2% vs. S&P 500"
                    )
                ])
            ], className="h-100")
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Annualized Return", className="card-title text-center mb-1"),
                    html.H3(
                        id="annualized-return-value",
                        className="text-center",
                        children="18.7%"
                    ),
                    html.P(
                        id="annualized-vs-benchmark",
                        className="text-center text-success mb-0",
                        children="+6.5% vs. S&P 500"
                    )
                ])
            ], className="h-100")
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Sharpe Ratio", className="card-title text-center mb-1"),
                    html.H3(
                        id="sharpe-ratio-value",
                        className="text-center",
                        children="1.85"
                    ),
                    html.P(
                        id="sharpe-ratio-interpretation",
                        className="text-center text-info mb-0",
                        children="Good Risk-Adjusted Return"
                    )
                ])
            ], className="h-100")
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Max Drawdown", className="card-title text-center mb-1"),
                    html.H3(
                        id="max-drawdown-value",
                        className="text-center text-danger",
                        children="-12.3%"
                    ),
                    html.P(
                        id="drawdown-recovery-time",
                        className="text-center mb-0",
                        children="45 days to recover"
                    )
                ])
            ], className="h-100")
        ], width=3)
    ], className="mb-4")
    
    # Main equity curve chart
    equity_chart = dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H5("Portfolio Performance"), width=8),
                dbc.Col([
                    dbc.ButtonGroup([
                        dbc.Button(
                            "Linear",
                            id="btn-linear-scale",
                            color="primary",
                            outline=False,
                            size="sm"
                        ),
                        dbc.Button(
                            "Log",
                            id="btn-log-scale",
                            color="secondary",
                            outline=True,
                            size="sm"
                        )
                    ], size="sm")
                ], width=4, className="text-end")
            ])
        ]),
        dbc.CardBody([
            dcc.Graph(
                id="equity-curve-chart",
                config={"displayModeBar": True, "scrollZoom": True},
                figure=go.Figure(),
                style={"height": "400px"}
            ),
            html.Div(id="chart-scale-type", style={"display": "none"}, children="linear")
        ])
    ], className="mb-4")
    
    # Dashboard content
    dashboard_content = html.Div([
        summary_cards,
        equity_chart,
        
        # Detailed metrics section
        dbc.Row([
            # Risk and Return Metrics
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Risk & Return Metrics")),
                    dbc.CardBody([
                        dbc.Tabs([
                            dbc.Tab([
                                html.Div(id="return-metrics-table", className="mt-3")
                            ], label="Return Metrics"),
                            dbc.Tab([
                                html.Div(id="risk-metrics-table", className="mt-3")
                            ], label="Risk Metrics"),
                            dbc.Tab([
                                html.Div(id="risk-adjusted-metrics-table", className="mt-3")
                            ], label="Risk-Adjusted")
                        ])
                    ])
                ], className="h-100")
            ], width=6),
            
            # Drawdown Analysis
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Drawdown Analysis")),
                    dbc.CardBody([
                        dcc.Graph(
                            id="drawdown-chart",
                            config={"displayModeBar": False},
                            figure=go.Figure(),
                            style={"height": "220px"}
                        ),
                        html.Div(id="top-drawdowns-table", className="mt-3")
                    ])
                ], className="h-100")
            ], width=6)
        ], className="mb-4"),
        
        # Monthly and Yearly Returns
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Monthly Returns (%)")),
                    dbc.CardBody([
                        html.Div(id="monthly-returns-table")
                    ])
                ])
            ], width=12)
        ], className="mb-4"),
        
        # Return Distribution
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Return Distribution")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dcc.Graph(
                                    id="return-histogram",
                                    config={"displayModeBar": False},
                                    figure=go.Figure(),
                                    style={"height": "300px"}
                                )
                            ], width=6),
                            dbc.Col([
                                dcc.Graph(
                                    id="return-qq-plot",
                                    config={"displayModeBar": False},
                                    figure=go.Figure(),
                                    style={"height": "300px"}
                                )
                            ], width=6)
                        ])
                    ])
                ])
            ], width=12)
        ])
    ], id="performance-dashboard-content")
    
    # Assemble the view
    view = html.Div([
        dcc.Interval(id="performance-refresh-interval", interval=60000, n_intervals=0),  # refresh every minute
        dcc.Store(id="performance-data-store"),
        header,
        dashboard_content
    ], id=view_id)
    
    return view 

def register_callbacks(app):
    """Register callbacks for the performance dashboard view."""
    
    # Callback to update date range based on preset selection
    @app.callback(
        Output("performance-date-range", "start_date"),
        Output("performance-date-range", "end_date"),
        Input("date-range-preset", "value")
    )
    def update_date_range(preset):
        """Update date range based on preset selection."""
        end_date = datetime.now()
        
        if preset == "30d":
            start_date = end_date - timedelta(days=30)
        elif preset == "90d":
            start_date = end_date - timedelta(days=90)
        elif preset == "ytd":
            start_date = datetime(end_date.year, 1, 1)
        elif preset == "1y":
            start_date = end_date - timedelta(days=365)
        elif preset == "3y":
            start_date = end_date - timedelta(days=365 * 3)
        elif preset == "max":
            start_date = datetime(2015, 1, 1)  # Just an example start date
        else:
            start_date = end_date - timedelta(days=90)
        
        return start_date, end_date
    
    # Callback to update performance data based on date range
    @app.callback(
        Output("performance-data-store", "data"),
        Input("performance-date-range", "start_date"),
        Input("performance-date-range", "end_date"),
        Input("performance-refresh-interval", "n_intervals")
    )
    def update_performance_data(start_date, end_date, n_intervals):
        """
        Fetch performance data based on the selected date range.
        
        In a real implementation, this would call portfolio service
        to get actual performance data.
        """
        # For now, generate sample data
        if start_date is None or end_date is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
        
        # Ensure timestamps are in datetime format
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Generate date range
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        
        # Generate sample performance data (cumulative returns)
        np.random.seed(42)  # For reproducibility
        daily_returns = np.random.normal(0.0007, 0.01, len(date_range))
        portfolio_cumulative = 100 * (1 + daily_returns).cumprod()
        
        # Generate benchmark data (slightly worse performance)
        benchmark_returns = np.random.normal(0.0005, 0.009, len(date_range))
        benchmark_cumulative = 100 * (1 + benchmark_returns).cumprod()
        
        # Create DataFrame with all data
        df = pd.DataFrame({
            'date': date_range,
            'portfolio_value': portfolio_cumulative,
            'benchmark_value': benchmark_cumulative,
            'portfolio_return': daily_returns,
            'benchmark_return': benchmark_returns
        })
        
        # Calculate drawdowns
        df['portfolio_peak'] = df['portfolio_value'].cummax()
        df['drawdown'] = (df['portfolio_value'] - df['portfolio_peak']) / df['portfolio_peak']
        
        # Add some monthly and yearly data
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        
        # Convert to dict for storage in dcc.Store
        return {
            'equity_curve': df.to_dict('records'),
            'summary': {
                'total_return': (portfolio_cumulative[-1] / portfolio_cumulative[0] - 1) * 100,
                'benchmark_return': (benchmark_cumulative[-1] / benchmark_cumulative[0] - 1) * 100,
                'annualized_return': ((1 + daily_returns.mean()) ** 252 - 1) * 100,
                'benchmark_annualized': ((1 + benchmark_returns.mean()) ** 252 - 1) * 100,
                'volatility': daily_returns.std() * np.sqrt(252) * 100,
                'sharpe_ratio': daily_returns.mean() / daily_returns.std() * np.sqrt(252),
                'max_drawdown': df['drawdown'].min() * 100,
                'recovery_days': 45  # Placeholder
            }
        }
    
    # Callback to update summary metrics
    @app.callback(
        Output("total-return-value", "children"),
        Output("total-return-vs-benchmark", "children"),
        Output("total-return-vs-benchmark", "className"),
        Output("annualized-return-value", "children"),
        Output("annualized-vs-benchmark", "children"),
        Output("annualized-vs-benchmark", "className"),
        Output("sharpe-ratio-value", "children"),
        Output("sharpe-ratio-interpretation", "children"),
        Output("sharpe-ratio-interpretation", "className"),
        Output("max-drawdown-value", "children"),
        Output("drawdown-recovery-time", "children"),
        Input("performance-data-store", "data")
    )
    def update_summary_metrics(data):
        """Update the summary metrics based on performance data."""
        if not data:
            # Return placeholder values if no data
            return (
                "0.0%", "+0.0% vs. S&P 500", "text-center text-muted mb-0",
                "0.0%", "+0.0% vs. S&P 500", "text-center text-muted mb-0",
                "0.0", "No Data", "text-center text-muted mb-0",
                "0.0%", "N/A days to recover", 
            )
        
        summary = data.get('summary', {})
        
        # Total return
        total_return = f"{summary.get('total_return', 0):.2f}%"
        
        # Relative to benchmark
        benchmark_outperformance = summary.get('total_return', 0) - summary.get('benchmark_return', 0)
        benchmark_text = f"{'+' if benchmark_outperformance > 0 else ''}{benchmark_outperformance:.2f}% vs. S&P 500"
        benchmark_class = "text-center text-success mb-0" if benchmark_outperformance > 0 else "text-center text-danger mb-0"
        
        # Annualized return
        annualized = f"{summary.get('annualized_return', 0):.2f}%"
        
        # Annualized vs benchmark
        ann_outperformance = summary.get('annualized_return', 0) - summary.get('benchmark_annualized', 0)
        ann_text = f"{'+' if ann_outperformance > 0 else ''}{ann_outperformance:.2f}% vs. S&P 500"
        ann_class = "text-center text-success mb-0" if ann_outperformance > 0 else "text-center text-danger mb-0"
        
        # Sharpe ratio
        sharpe = f"{summary.get('sharpe_ratio', 0):.2f}"
        
        # Interpret sharpe ratio
        if summary.get('sharpe_ratio', 0) > 1.5:
            sharpe_text = "Excellent Risk-Adjusted Return"
            sharpe_class = "text-center text-success mb-0"
        elif summary.get('sharpe_ratio', 0) > 1.0:
            sharpe_text = "Good Risk-Adjusted Return"
            sharpe_class = "text-center text-info mb-0"
        elif summary.get('sharpe_ratio', 0) > 0.5:
            sharpe_text = "Average Risk-Adjusted Return"
            sharpe_class = "text-center text-warning mb-0"
        else:
            sharpe_text = "Poor Risk-Adjusted Return"
            sharpe_class = "text-center text-danger mb-0"
        
        # Max drawdown
        max_dd = f"{summary.get('max_drawdown', 0):.2f}%"
        
        # Recovery time
        recovery = f"{summary.get('recovery_days', 'N/A')} days to recover"
        
        return (
            total_return, benchmark_text, benchmark_class,
            annualized, ann_text, ann_class,
            sharpe, sharpe_text, sharpe_class,
            max_dd, recovery
        )
    
    # Callback to update the main equity curve chart
    @app.callback(
        Output("equity-curve-chart", "figure"),
        Input("performance-data-store", "data"),
        Input("chart-scale-type", "children")
    )
    def update_equity_curve(data, scale_type):
        """Update the equity curve chart based on performance data."""
        if not data:
            return go.Figure()
        
        # Convert data to DataFrame
        equity_data = pd.DataFrame(data.get('equity_curve', []))
        
        if equity_data.empty:
            return go.Figure()
        
        # Create figure
        fig = go.Figure()
        
        # Add portfolio line
        fig.add_trace(go.Scatter(
            x=equity_data['date'],
            y=equity_data['portfolio_value'],
            mode='lines',
            name='Portfolio',
            line=dict(color='#1f77b4', width=2)
        ))
        
        # Add benchmark line
        fig.add_trace(go.Scatter(
            x=equity_data['date'],
            y=equity_data['benchmark_value'],
            mode='lines',
            name='S&P 500',
            line=dict(color='#ff7f0e', width=1, dash='dash')
        ))
        
        # Update layout
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                title="",
                showgrid=True,
                gridcolor="lightgray"
            ),
            yaxis=dict(
                title="Portfolio Value ($)",
                showgrid=True,
                gridcolor="lightgray",
                type="log" if scale_type == "log" else "linear"
            ),
            plot_bgcolor="white",
            hovermode="x unified"
        )
        
        return fig
    
    # Callback to update the chart scale type (linear/log)
    @app.callback(
        Output("chart-scale-type", "children"),
        Output("btn-linear-scale", "color"),
        Output("btn-linear-scale", "outline"),
        Output("btn-log-scale", "color"),
        Output("btn-log-scale", "outline"),
        Input("btn-linear-scale", "n_clicks"),
        Input("btn-log-scale", "n_clicks"),
        State("chart-scale-type", "children")
    )
    def update_chart_scale(n_linear, n_log, current_scale):
        """Update the chart scale type between linear and logarithmic."""
        ctx = dash.callback_context
        if not ctx.triggered:
            return current_scale, "primary", False, "secondary", True
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if button_id == "btn-linear-scale":
            return "linear", "primary", False, "secondary", True
        elif button_id == "btn-log-scale":
            return "log", "secondary", True, "primary", False
        
        return current_scale, "primary", False, "secondary", True
    
    # Callback to update drawdown chart
    @app.callback(
        Output("drawdown-chart", "figure"),
        Input("performance-data-store", "data")
    )
    def update_drawdown_chart(data):
        """Update the drawdown chart based on performance data."""
        if not data:
            return go.Figure()
        
        # Convert data to DataFrame
        equity_data = pd.DataFrame(data.get('equity_curve', []))
        
        if equity_data.empty:
            return go.Figure()
        
        # Create figure
        fig = go.Figure()
        
        # Add drawdown area
        fig.add_trace(go.Scatter(
            x=equity_data['date'],
            y=equity_data['drawdown'] * 100,
            mode='lines',
            name='Drawdown',
            line=dict(color='#d62728', width=1),
            fill='tozeroy'
        ))
        
        # Update layout
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                title="",
                showgrid=True,
                gridcolor="lightgray"
            ),
            yaxis=dict(
                title="Drawdown (%)",
                showgrid=True,
                gridcolor="lightgray",
                range=[min(equity_data['drawdown'] * 100) * 1.1, 5]
            ),
            plot_bgcolor="white",
            hovermode="x unified"
        )
        
        return fig
    
    # Callback to update return metrics table
    @app.callback(
        Output("return-metrics-table", "children"),
        Input("performance-data-store", "data")
    )
    def update_return_metrics_table(data):
        """Update the return metrics table based on performance data."""
        if not data:
            return html.Div("No data available")
        
        summary = data.get('summary', {})
        
        # Create metrics dictionary
        metrics = {
            "Total Return": f"{summary.get('total_return', 0):.2f}%",
            "Annualized Return": f"{summary.get('annualized_return', 0):.2f}%",
            "Monthly Return (Avg)": f"{summary.get('annualized_return', 0) / 12:.2f}%",
            "Best Month": f"+{np.random.uniform(3, 8):.2f}%",
            "Worst Month": f"-{np.random.uniform(2, 6):.2f}%",
            "Positive Months": f"{np.random.randint(55, 70)}%",
            "Outperformance vs S&P 500": f"{summary.get('total_return', 0) - summary.get('benchmark_return', 0):.2f}%"
        }
        
        # Create table
        table = dbc.Table(
            [
                html.Tbody([
                    html.Tr([html.Td(k), html.Td(v, style={"text-align": "right", "font-weight": "bold"})]) 
                    for k, v in metrics.items()
                ])
            ],
            bordered=False,
            hover=True,
            responsive=True,
            size="sm",
            striped=True
        )
        
        return table
    
    # Callback to update risk metrics table
    @app.callback(
        Output("risk-metrics-table", "children"),
        Input("performance-data-store", "data")
    )
    def update_risk_metrics_table(data):
        """Update the risk metrics table based on performance data."""
        if not data:
            return html.Div("No data available")
        
        summary = data.get('summary', {})
        
        # Create metrics dictionary
        metrics = {
            "Volatility (Annualized)": f"{summary.get('volatility', 0):.2f}%",
            "Maximum Drawdown": f"{summary.get('max_drawdown', 0):.2f}%",
            "Average Drawdown": f"{summary.get('max_drawdown', 0) * 0.4:.2f}%",
            "Maximum Drawdown Duration": f"{summary.get('recovery_days', 45)} days",
            "VaR (95%)": f"-{summary.get('volatility', 0) * 1.65 / np.sqrt(252):.2f}%",
            "Expected Shortfall (95%)": f"-{summary.get('volatility', 0) * 2.06 / np.sqrt(252):.2f}%",
            "Beta to S&P 500": f"{np.random.uniform(0.6, 1.1):.2f}"
        }
        
        # Create table
        table = dbc.Table(
            [
                html.Tbody([
                    html.Tr([html.Td(k), html.Td(v, style={"text-align": "right", "font-weight": "bold"})]) 
                    for k, v in metrics.items()
                ])
            ],
            bordered=False,
            hover=True,
            responsive=True,
            size="sm",
            striped=True
        )
        
        return table
    
    # Callback to update risk-adjusted metrics table
    @app.callback(
        Output("risk-adjusted-metrics-table", "children"),
        Input("performance-data-store", "data")
    )
    def update_risk_adjusted_metrics_table(data):
        """Update the risk-adjusted metrics table based on performance data."""
        if not data:
            return html.Div("No data available")
        
        summary = data.get('summary', {})
        
        # Create metrics dictionary
        metrics = {
            "Sharpe Ratio": f"{summary.get('sharpe_ratio', 0):.2f}",
            "Sortino Ratio": f"{summary.get('sharpe_ratio', 0) * 1.3:.2f}",
            "Calmar Ratio": f"{summary.get('annualized_return', 0) / abs(summary.get('max_drawdown', 1)):.2f}",
            "Omega Ratio": f"{np.random.uniform(1.2, 1.8):.2f}",
            "Information Ratio": f"{np.random.uniform(0.3, 0.9):.2f}",
            "Alpha (Annualized)": f"{(summary.get('annualized_return', 0) - summary.get('benchmark_annualized', 0)) * 0.7:.2f}%",
            "Treynor Ratio": f"{np.random.uniform(0.1, 0.3):.2f}"
        }
        
        # Create table
        table = dbc.Table(
            [
                html.Tbody([
                    html.Tr([html.Td(k), html.Td(v, style={"text-align": "right", "font-weight": "bold"})]) 
                    for k, v in metrics.items()
                ])
            ],
            bordered=False,
            hover=True,
            responsive=True,
            size="sm",
            striped=True
        )
        
        return table
    
    # Callback to update top drawdowns table
    @app.callback(
        Output("top-drawdowns-table", "children"),
        Input("performance-data-store", "data")
    )
    def update_top_drawdowns_table(data):
        """Update the top drawdowns table based on performance data."""
        if not data:
            return html.Div("No data available")
        
        # Generate sample drawdown data
        drawdowns = [
            {"start": "2023-01-15", "end": "2023-03-01", "recovery": "2023-04-15", "depth": -12.3, "duration": 45},
            {"start": "2022-08-20", "end": "2022-09-25", "recovery": "2022-11-10", "depth": -8.7, "duration": 36},
            {"start": "2022-04-05", "end": "2022-04-28", "recovery": "2022-05-20", "depth": -5.4, "duration": 23},
            {"start": "2021-11-15", "end": "2021-12-05", "recovery": "2022-01-10", "depth": -6.2, "duration": 25}
        ]
        
        # Create table
        table = dbc.Table(
            [
                html.Thead(
                    html.Tr([
                        html.Th("Start"),
                        html.Th("End"),
                        html.Th("Recovery"),
                        html.Th("Depth"),
                        html.Th("Duration")
                    ])
                ),
                html.Tbody([
                    html.Tr([
                        html.Td(dd["start"]),
                        html.Td(dd["end"]),
                        html.Td(dd["recovery"]),
                        html.Td(f"{dd['depth']:.1f}%", style={"color": "red"}),
                        html.Td(f"{dd['duration']} days")
                    ]) for dd in drawdowns
                ])
            ],
            bordered=False,
            hover=True,
            responsive=True,
            size="sm",
            striped=True
        )
        
        return table
    
    # Callback to update monthly returns table
    @app.callback(
        Output("monthly-returns-table", "children"),
        Input("performance-data-store", "data")
    )
    def update_monthly_returns_table(data):
        """Update the monthly returns table based on performance data."""
        if not data:
            return html.Div("No data available")
        
        # Generate sample monthly returns
        np.random.seed(42)
        years = range(2021, 2024)
        months = range(1, 13)
        monthly_returns = {}
        
        for year in years:
            monthly_returns[year] = {}
            for month in months:
                if year == 2023 and month > datetime.now().month:
                    monthly_returns[year][month] = None
                else:
                    # Generate random returns, slightly biased positive
                    monthly_returns[year][month] = np.random.normal(0.8, 3.0)
        
        # Create header row with month names
        header_row = [html.Th("Year")] + [html.Th(datetime(2000, m, 1).strftime("%b")) for m in months] + [html.Th("YTD")]
        
        # Create data rows
        data_rows = []
        for year in years:
            row = [html.Td(year, style={"font-weight": "bold"})]
            year_returns = []
            
            for month in months:
                value = monthly_returns[year].get(month)
                if value is None:
                    row.append(html.Td("-"))
                else:
                    year_returns.append(value)
                    style = {"color": "green" if value >= 0 else "red", "text-align": "right"}
                    row.append(html.Td(f"{value:.1f}%", style=style))
            
            # Add year-to-date return
            if year_returns:
                ytd_return = sum(year_returns)
                style = {"color": "green" if ytd_return >= 0 else "red", "text-align": "right", "font-weight": "bold"}
                row.append(html.Td(f"{ytd_return:.1f}%", style=style))
            else:
                row.append(html.Td("-"))
            
            data_rows.append(html.Tr(row))
        
        # Create table
        table = dbc.Table(
            [
                html.Thead(html.Tr(header_row)),
                html.Tbody(data_rows)
            ],
            bordered=True,
            hover=True,
            responsive=True,
            size="sm",
            striped=True
        )
        
        return table
    
    # Callback to update return histogram
    @app.callback(
        Output("return-histogram", "figure"),
        Input("performance-data-store", "data")
    )
    def update_return_histogram(data):
        """Update the return distribution histogram based on performance data."""
        if not data:
            return go.Figure()
        
        # Convert data to DataFrame
        equity_data = pd.DataFrame(data.get('equity_curve', []))
        
        if equity_data.empty:
            return go.Figure()
        
        returns = equity_data.get('portfolio_return', pd.Series())
        
        # Create figure
        fig = go.Figure()
        
        # Add histogram
        fig.add_trace(go.Histogram(
            x=returns * 100,  # Convert to percentage
            opacity=0.75,
            name="Daily Returns",
            marker_color="#1f77b4",
            nbinsx=30
        ))
        
        # Add normal distribution curve
        x = np.linspace(min(returns) * 100, max(returns) * 100, 100)
        y = np.exp(-(x - returns.mean() * 100) ** 2 / (2 * (returns.std() * 100) ** 2)) / (returns.std() * 100 * np.sqrt(2 * np.pi))
        y = y / max(y) * max(np.histogram(returns * 100, bins=30)[0])  # Scale to match histogram height
        
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name="Normal Distribution",
            line=dict(color="red", width=2)
        ))
        
        # Update layout
        fig.update_layout(
            title="Return Distribution",
            xaxis_title="Daily Return (%)",
            yaxis_title="Frequency",
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="white",
            bargap=0.05
        )
        
        return fig
    
    # Callback to update Q-Q plot
    @app.callback(
        Output("return-qq-plot", "figure"),
        Input("performance-data-store", "data")
    )
    def update_qq_plot(data):
        """Update the Q-Q plot based on performance data."""
        if not data:
            return go.Figure()
        
        # Convert data to DataFrame
        equity_data = pd.DataFrame(data.get('equity_curve', []))
        
        if equity_data.empty:
            return go.Figure()
        
        returns = equity_data.get('portfolio_return', pd.Series())
        
        # Calculate theoretical quantiles
        from scipy import stats
        standardized_returns = (returns - returns.mean()) / returns.std()
        theoretical_quantiles = np.sort(stats.norm.ppf(np.linspace(0.01, 0.99, len(returns))))
        observed_quantiles = np.sort(standardized_returns)
        
        # Create figure
        fig = go.Figure()
        
        # Add Q-Q plot
        fig.add_trace(go.Scatter(
            x=theoretical_quantiles,
            y=observed_quantiles,
            mode="markers",
            name="Q-Q Plot",
            marker=dict(color="#1f77b4", size=6)
        ))
        
        # Add diagonal line (normal distribution reference)
        min_val = min(min(theoretical_quantiles), min(observed_quantiles))
        max_val = max(max(theoretical_quantiles), max(observed_quantiles))
        fig.add_trace(go.Scatter(
            x=[min_val, max_val],
            y=[min_val, max_val],
            mode="lines",
            name="Normal Reference",
            line=dict(color="red", width=2)
        ))
        
        # Update layout
        fig.update_layout(
            title="Q-Q Plot (Normal Distribution)",
            xaxis_title="Theoretical Quantiles",
            yaxis_title="Sample Quantiles",
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="white"
        )
        
        return fig 