"""
Strategy Monitoring View

This module provides a comprehensive view for monitoring and controlling trading strategies
in real-time. It includes performance metrics, visualization of strategy performance,
position information, and control capabilities.
"""

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Import core components
from advanced_trading.core.observability import get_logger
from advanced_trading.dashboard.core import DashboardState, DashboardController

# Import components
from advanced_trading.dashboard.components.status_card import create_status_card
from advanced_trading.dashboard.components.performance_card import create_performance_card

# Initialize logger
logger = get_logger(__name__)


def create_strategy_monitoring_view(state: DashboardState, controller: DashboardController) -> html.Div:
    """
    Create the strategy monitoring view.
    
    Args:
        state: Current dashboard state
        controller: Dashboard controller for actions
        
    Returns:
        html.Div: The strategy monitoring view
    """
    view_id = "strategy-monitoring-view"
    
    # Get active strategies from the state
    active_strategies = state.get_active_strategies() or []
    
    # Create the strategy selector
    strategy_selector = dbc.Row([
        dbc.Col([
            html.H5("Select Strategy"),
            dcc.Dropdown(
                id="strategy-selector",
                options=[{"label": s.name, "value": s.id} for s in active_strategies],
                value=active_strategies[0].id if active_strategies else None,
                clearable=False,
                className="mb-3"
            )
        ])
    ])
    
    # Create the strategy summary cards
    strategy_summary = dbc.Row([
        dbc.Col([
            create_status_card(
                id_prefix="strategy-status",
                title="Strategy Status",
                value="Running",
                status="success",
                icon="check-circle"
            )
        ], width=3),
        dbc.Col([
            create_performance_card(
                id_prefix="strategy-return",
                title="Cumulative Return",
                value="12.5%",
                change="+2.3%",
                is_positive=True,
                icon="chart-line"
            )
        ], width=3),
        dbc.Col([
            create_performance_card(
                id_prefix="strategy-sharpe",
                title="Sharpe Ratio",
                value="1.85",
                change="+0.2",
                is_positive=True,
                icon="chart-bar"
            )
        ], width=3),
        dbc.Col([
            create_performance_card(
                id_prefix="strategy-drawdown",
                title="Max Drawdown",
                value="-4.2%",
                change="-0.5%",
                is_positive=True,
                icon="chart-area"
            )
        ], width=3)
    ], className="mb-4")
    
    # Create the performance chart
    performance_chart = dbc.Card([
        dbc.CardHeader(html.H5("Performance")),
        dbc.CardBody([
            dcc.Graph(
                id="strategy-performance-chart",
                config={"displayModeBar": False},
                figure=go.Figure()
            ),
            dbc.ButtonGroup([
                dbc.Button("1D", id="btn-1d", color="secondary", outline=True, size="sm"),
                dbc.Button("1W", id="btn-1w", color="secondary", outline=True, size="sm"),
                dbc.Button("1M", id="btn-1m", color="primary", outline=False, size="sm"),
                dbc.Button("3M", id="btn-3m", color="secondary", outline=True, size="sm"),
                dbc.Button("YTD", id="btn-ytd", color="secondary", outline=True, size="sm"),
                dbc.Button("1Y", id="btn-1y", color="secondary", outline=True, size="sm"),
                dbc.Button("All", id="btn-all", color="secondary", outline=True, size="sm"),
            ], className="mt-3"),
            html.Div(id="performance-time-range", style={"display": "none"}, children="1M")
        ])
    ], className="mb-4")
    
    # Create the metrics cards
    metrics_row = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Key Metrics")),
                dbc.CardBody([
                    html.Div(id="strategy-metrics-table")
                ])
            ])
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Risk Metrics")),
                dbc.CardBody([
                    html.Div(id="strategy-risk-metrics-table")
                ])
            ])
        ], width=6)
    ], className="mb-4")
    
    # Create the positions table
    positions_table = dbc.Card([
        dbc.CardHeader(
            dbc.Row([
                dbc.Col(html.H5("Current Positions")),
                dbc.Col(
                    dbc.Button(
                        "Refresh", 
                        id="refresh-positions", 
                        color="primary", 
                        size="sm", 
                        className="float-end"
                    ),
                    width="auto"
                )
            ])
        ),
        dbc.CardBody([
            html.Div(id="strategy-positions-table")
        ])
    ], className="mb-4")
    
    # Create the trade history section
    trade_history = dbc.Card([
        dbc.CardHeader(
            dbc.Row([
                dbc.Col(html.H5("Trade History")),
                dbc.Col(
                    dbc.Row([
                        dbc.Col(
                            dcc.Dropdown(
                                id="trade-history-filter",
                                options=[
                                    {"label": "All Trades", "value": "all"},
                                    {"label": "Buy Orders", "value": "buy"},
                                    {"label": "Sell Orders", "value": "sell"}
                                ],
                                value="all",
                                clearable=False,
                                style={"width": "140px"}
                            ),
                            width="auto"
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Export", 
                                id="export-trades", 
                                color="secondary", 
                                size="sm"
                            ),
                            width="auto"
                        )
                    ], justify="end"),
                    width="auto"
                )
            ])
        ),
        dbc.CardBody([
            html.Div(id="strategy-trade-history-table")
        ])
    ], className="mb-4")
    
    # Create the control panel
    control_panel = dbc.Card([
        dbc.CardHeader(html.H5("Strategy Controls")),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Button("Start", id="btn-start-strategy", color="success", className="me-2"),
                    dbc.Button("Pause", id="btn-pause-strategy", color="warning", className="me-2"),
                    dbc.Button("Stop", id="btn-stop-strategy", color="danger", className="me-2"),
                    dbc.Button("Reset", id="btn-reset-strategy", color="secondary", className="me-2"),
                ], width="auto"),
                dbc.Col([
                    dbc.InputGroup([
                        dbc.InputGroupText("Risk Level"),
                        dbc.Select(
                            id="risk-level-selector",
                            options=[
                                {"label": "Low", "value": "low"},
                                {"label": "Medium", "value": "medium"},
                                {"label": "High", "value": "high"},
                            ],
                            value="medium"
                        ),
                        dbc.Button("Apply", id="apply-risk-level", color="primary")
                    ], size="sm")
                ], width="auto"),
                dbc.Col([
                    dbc.InputGroup([
                        dbc.InputGroupText("Capital"),
                        dbc.Input(id="strategy-capital", type="number", value=100000),
                        dbc.Button("Apply", id="apply-capital", color="primary")
                    ], size="sm")
                ], width="auto")
            ], className="mb-3"),
            html.Div(id="strategy-control-output")
        ])
    ], className="mb-4")
    
    # Assemble the view
    view = html.Div([
        dcc.Interval(id="strategy-refresh-interval", interval=5000, n_intervals=0),
        html.H3("Strategy Monitoring", className="mb-4"),
        strategy_selector,
        strategy_summary,
        performance_chart,
        metrics_row,
        positions_table,
        trade_history,
        control_panel
    ], id=view_id)
    
    return view


def register_callbacks(app):
    """Register callbacks for the strategy monitoring view."""
    
    @app.callback(
        Output("strategy-performance-chart", "figure"),
        [
            Input("strategy-selector", "value"),
            Input("performance-time-range", "children"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_performance_chart(strategy_id, time_range, n_intervals):
        """Update the performance chart based on the selected strategy and time range."""
        if not strategy_id:
            return go.Figure()
        
        # This would normally fetch real data from the strategy service
        # For now, we'll generate sample data
        end_date = datetime.now()
        
        if time_range == "1D":
            start_date = end_date - timedelta(days=1)
            date_range = pd.date_range(start=start_date, end=end_date, freq="15min")
        elif time_range == "1W":
            start_date = end_date - timedelta(weeks=1)
            date_range = pd.date_range(start=start_date, end=end_date, freq="1h")
        elif time_range == "1M":
            start_date = end_date - timedelta(days=30)
            date_range = pd.date_range(start=start_date, end=end_date, freq="1d")
        elif time_range == "3M":
            start_date = end_date - timedelta(days=90)
            date_range = pd.date_range(start=start_date, end=end_date, freq="1d")
        elif time_range == "YTD":
            start_date = datetime(end_date.year, 1, 1)
            date_range = pd.date_range(start=start_date, end=end_date, freq="1d")
        elif time_range == "1Y":
            start_date = end_date - timedelta(days=365)
            date_range = pd.date_range(start=start_date, end=end_date, freq="1d")
        else:  # "All"
            start_date = end_date - timedelta(days=365 * 2)
            date_range = pd.date_range(start=start_date, end=end_date, freq="1d")
        
        # Generate sample performance data
        np.random.seed(42)  # For reproducibility
        cumulative_returns = 100 * (1 + np.random.normal(0.0005, 0.01, len(date_range))).cumprod()
        benchmark_returns = 100 * (1 + np.random.normal(0.0003, 0.008, len(date_range))).cumprod()
        
        # Create the figure
        fig = go.Figure()
        
        # Add strategy line
        fig.add_trace(go.Scatter(
            x=date_range,
            y=cumulative_returns,
            mode="lines",
            name="Strategy",
            line=dict(color="#1f77b4", width=2)
        ))
        
        # Add benchmark line
        fig.add_trace(go.Scatter(
            x=date_range,
            y=benchmark_returns,
            mode="lines",
            name="Benchmark (S&P 500)",
            line=dict(color="#ff7f0e", width=1, dash="dash")
        ))
        
        # Update layout
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title="Date", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="Value ($)", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            hovermode="x unified"
        )
        
        return fig
    
    @app.callback(
        Output("performance-time-range", "children"),
        [
            Input("btn-1d", "n_clicks"),
            Input("btn-1w", "n_clicks"),
            Input("btn-1m", "n_clicks"),
            Input("btn-3m", "n_clicks"),
            Input("btn-ytd", "n_clicks"),
            Input("btn-1y", "n_clicks"),
            Input("btn-all", "n_clicks")
        ],
        [State("performance-time-range", "children")]
    )
    def update_time_range(n1d, n1w, n1m, n3m, nytd, n1y, nall, current_range):
        """Update the selected time range based on button clicks."""
        ctx = dash.callback_context
        if not ctx.triggered:
            return current_range
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id == "btn-1d":
            return "1D"
        elif button_id == "btn-1w":
            return "1W"
        elif button_id == "btn-1m":
            return "1M"
        elif button_id == "btn-3m":
            return "3M"
        elif button_id == "btn-ytd":
            return "YTD"
        elif button_id == "btn-1y":
            return "1Y"
        elif button_id == "btn-all":
            return "All"
        return current_range
    
    @app.callback(
        [
            Output("btn-1d", "color"),
            Output("btn-1d", "outline"),
            Output("btn-1w", "color"),
            Output("btn-1w", "outline"),
            Output("btn-1m", "color"),
            Output("btn-1m", "outline"),
            Output("btn-3m", "color"),
            Output("btn-3m", "outline"),
            Output("btn-ytd", "color"),
            Output("btn-ytd", "outline"),
            Output("btn-1y", "color"),
            Output("btn-1y", "outline"),
            Output("btn-all", "color"),
            Output("btn-all", "outline")
        ],
        [Input("performance-time-range", "children")]
    )
    def update_time_buttons(selected_range):
        """Update the time range button styles based on the selected range."""
        button_styles = {
            "1D": ("primary", False),
            "1W": ("primary", False),
            "1M": ("primary", False),
            "3M": ("primary", False),
            "YTD": ("primary", False),
            "1Y": ("primary", False),
            "All": ("primary", False)
        }
        
        # Set default styles
        styles = {k: ("secondary", True) for k in button_styles.keys()}
        
        # Update selected button style
        if selected_range in styles:
            styles[selected_range] = button_styles[selected_range]
        
        return (
            styles["1D"][0], styles["1D"][1],
            styles["1W"][0], styles["1W"][1],
            styles["1M"][0], styles["1M"][1],
            styles["3M"][0], styles["3M"][1],
            styles["YTD"][0], styles["YTD"][1],
            styles["1Y"][0], styles["1Y"][1],
            styles["All"][0], styles["All"][1]
        )
    
    @app.callback(
        Output("strategy-metrics-table", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_metrics_table(strategy_id, n_intervals):
        """Update the strategy metrics table."""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Generate sample metrics
        metrics = {
            "Cumulative Return": "12.5%",
            "Annualized Return": "15.2%",
            "Sharpe Ratio": "1.85",
            "Sortino Ratio": "2.12",
            "Win Rate": "62.3%",
            "Profit Factor": "1.73",
            "Expectancy": "$0.82"
        }
        
        # Create table
        table = dbc.Table(
            [
                html.Tbody([
                    html.Tr([html.Td(k), html.Td(v, style={"text-align": "right"})]) 
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
    
    @app.callback(
        Output("strategy-risk-metrics-table", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_risk_metrics_table(strategy_id, n_intervals):
        """Update the strategy risk metrics table."""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Generate sample risk metrics
        metrics = {
            "Maximum Drawdown": "-4.2%",
            "Average Drawdown": "-2.1%",
            "Drawdown Duration": "12 days",
            "Daily Value at Risk (95%)": "-1.8%",
            "Beta": "0.62",
            "Alpha": "0.08",
            "Correlation to Market": "0.48"
        }
        
        # Create table
        table = dbc.Table(
            [
                html.Tbody([
                    html.Tr([html.Td(k), html.Td(v, style={"text-align": "right"})]) 
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
    
    @app.callback(
        Output("strategy-positions-table", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals"),
            Input("refresh-positions", "n_clicks")
        ]
    )
    def update_positions_table(strategy_id, n_intervals, n_clicks):
        """Update the positions table."""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Generate sample positions data
        positions = [
            {"symbol": "AAPL", "quantity": 100, "entry_price": 172.50, "current_price": 178.25, "pnl": 575.00, "pnl_pct": 3.3},
            {"symbol": "MSFT", "quantity": 75, "entry_price": 325.10, "current_price": 337.80, "pnl": 952.50, "pnl_pct": 3.9},
            {"symbol": "GOOGL", "quantity": 50, "entry_price": 135.75, "current_price": 131.20, "pnl": -227.50, "pnl_pct": -3.4},
            {"symbol": "AMZN", "quantity": 30, "entry_price": 142.80, "current_price": 148.15, "pnl": 160.50, "pnl_pct": 3.7}
        ]
        
        # Create the table
        table = dbc.Table(
            [
                html.Thead(
                    html.Tr([
                        html.Th("Symbol"),
                        html.Th("Quantity"),
                        html.Th("Entry Price"),
                        html.Th("Current Price"),
                        html.Th("P&L ($)"),
                        html.Th("P&L (%)"),
                        html.Th("Actions")
                    ])
                ),
                html.Tbody([
                    html.Tr([
                        html.Td(pos["symbol"]),
                        html.Td(f"{pos['quantity']:,}"),
                        html.Td(f"${pos['entry_price']:.2f}"),
                        html.Td(f"${pos['current_price']:.2f}"),
                        html.Td(
                            f"${pos['pnl']:.2f}", 
                            style={"color": "green" if pos['pnl'] >= 0 else "red"}
                        ),
                        html.Td(
                            f"{pos['pnl_pct']:.1f}%", 
                            style={"color": "green" if pos['pnl_pct'] >= 0 else "red"}
                        ),
                        html.Td(
                            dbc.ButtonGroup([
                                dbc.Button("Close", color="danger", size="sm", outline=True),
                                dbc.Button("Add", color="success", size="sm", outline=True)
                            ], size="sm")
                        )
                    ]) for pos in positions
                ])
            ],
            bordered=True,
            hover=True,
            responsive=True,
            striped=True
        )
        
        return table
    
    @app.callback(
        Output("strategy-trade-history-table", "children"),
        [
            Input("strategy-selector", "value"),
            Input("trade-history-filter", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_trade_history_table(strategy_id, filter_value, n_intervals):
        """Update the trade history table."""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Generate sample trade history
        trades = [
            {"id": "T123", "date": "2023-09-12 10:15:30", "symbol": "AAPL", "type": "buy", "quantity": 100, "price": 172.50, "value": 17250.00},
            {"id": "T124", "date": "2023-09-12 10:15:35", "symbol": "MSFT", "type": "buy", "quantity": 75, "price": 325.10, "value": 24382.50},
            {"id": "T125", "date": "2023-09-12 10:16:02", "symbol": "GOOGL", "type": "buy", "quantity": 50, "price": 135.75, "value": 6787.50},
            {"id": "T126", "date": "2023-09-12 11:05:17", "symbol": "AMZN", "type": "buy", "quantity": 30, "price": 142.80, "value": 4284.00},
            {"id": "T127", "date": "2023-09-13 09:32:45", "symbol": "NFLX", "type": "buy", "quantity": 20, "price": 450.20, "value": 9004.00},
            {"id": "T128", "date": "2023-09-13 14:23:11", "symbol": "NFLX", "type": "sell", "quantity": 20, "price": 445.85, "value": 8917.00}
        ]
        
        # Apply filter
        if filter_value != "all":
            trades = [t for t in trades if t["type"] == filter_value]
        
        # Create the table
        table = dbc.Table(
            [
                html.Thead(
                    html.Tr([
                        html.Th("ID"),
                        html.Th("Date & Time"),
                        html.Th("Symbol"),
                        html.Th("Type"),
                        html.Th("Quantity"),
                        html.Th("Price"),
                        html.Th("Value"),
                        html.Th("Details")
                    ])
                ),
                html.Tbody([
                    html.Tr([
                        html.Td(trade["id"]),
                        html.Td(trade["date"]),
                        html.Td(trade["symbol"]),
                        html.Td(
                            html.Span(
                                trade["type"].capitalize(),
                                style={
                                    "color": "green" if trade["type"] == "buy" else "red",
                                    "font-weight": "bold"
                                }
                            )
                        ),
                        html.Td(f"{trade['quantity']:,}"),
                        html.Td(f"${trade['price']:.2f}"),
                        html.Td(f"${trade['value']:.2f}"),
                        html.Td(
                            dbc.Button(
                                "View",
                                id=f"btn-view-trade-{trade['id']}",
                                color="link",
                                size="sm"
                            )
                        )
                    ]) for trade in trades
                ])
            ],
            bordered=True,
            hover=True,
            responsive=True,
            striped=True
        )
        
        return table
    
    @app.callback(
        Output("strategy-control-output", "children"),
        [
            Input("btn-start-strategy", "n_clicks"),
            Input("btn-pause-strategy", "n_clicks"),
            Input("btn-stop-strategy", "n_clicks"),
            Input("btn-reset-strategy", "n_clicks"),
            Input("apply-risk-level", "n_clicks"),
            Input("apply-capital", "n_clicks")
        ],
        [
            State("strategy-selector", "value"),
            State("risk-level-selector", "value"),
            State("strategy-capital", "value")
        ]
    )
    def handle_control_actions(n_start, n_pause, n_stop, n_reset, n_risk, n_capital, 
                             strategy_id, risk_level, capital):
        """Handle strategy control actions."""
        if not strategy_id:
            return dbc.Alert("No strategy selected", color="warning", dismissable=True)
        
        # Check which button was clicked
        ctx = dash.callback_context
        if not ctx.triggered:
            return None
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if button_id == "btn-start-strategy":
            return dbc.Alert("Strategy started successfully", color="success", dismissable=True)
        elif button_id == "btn-pause-strategy":
            return dbc.Alert("Strategy paused", color="warning", dismissable=True)
        elif button_id == "btn-stop-strategy":
            return dbc.Alert("Strategy stopped", color="danger", dismissable=True)
        elif button_id == "btn-reset-strategy":
            return dbc.Alert("Strategy reset to initial state", color="info", dismissable=True)
        elif button_id == "apply-risk-level":
            return dbc.Alert(f"Risk level updated to {risk_level}", color="success", dismissable=True)
        elif button_id == "apply-capital":
            return dbc.Alert(f"Capital updated to ${capital:,}", color="success", dismissable=True)
        
        return None 