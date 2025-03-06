"""
Strategy View

This module provides the strategy monitoring and management view for the dashboard.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Import Dash libraries
import dash
from dash import html, dcc, callback, Output, Input, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import core modules
from core import config_manager, metrics, logging as log_manager

# Import services
from dashboard.services import strategy_service

# Import components
from dashboard.components.status_card import create_status_card, create_metric_card
from dashboard.components.performance_card import create_performance_card

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.views.strategy_view"})


def create_strategy_view():
    """
    Create the strategy view.
    
    Returns:
        Strategy view layout
    """
    # Get available strategies
    strategies = strategy_service.get_strategies()
    strategy_options = [{"label": s["name"], "value": s["id"]} for s in strategies]
    default_strategy = strategies[0]["id"] if strategies else None
    
    # Create layout
    layout = html.Div([
        # Title and description
        html.H2("Strategy Management"),
        html.P("Monitor, configure, and backtest trading strategies."),
        
        # Strategy selection and overview
        dbc.Row([
            # Strategy selector
            dbc.Col([
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Select Strategy"),
                        dcc.Dropdown(
                            id="strategy-selector",
                            options=strategy_options,
                            value=default_strategy,
                            clearable=False
                        ),
                        html.Div(id="strategy-description", className="mt-3"),
                        html.Hr(),
                        html.Div([
                            html.H6("Strategy Status"),
                            dbc.FormGroup([
                                dbc.Checklist(
                                    options=[{"label": "Active", "value": 1}],
                                    value=[1] if strategies and strategies[0]["active"] else [],
                                    id="strategy-active-toggle",
                                    switch=True
                                )
                            ])
                        ]),
                        html.Div(id="strategy-action-output")
                    ]),
                    className="shadow-sm h-100"
                )
            ], width=3),
            
            # Strategy overview
            dbc.Col([
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Performance Overview"),
                        dbc.Row([
                            dbc.Col(html.Div(id="strategy-win-rate"), width=4),
                            dbc.Col(html.Div(id="strategy-profit-factor"), width=4),
                            dbc.Col(html.Div(id="strategy-sharpe-ratio"), width=4)
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col(html.Div(id="strategy-max-drawdown"), width=4),
                            dbc.Col(html.Div(id="strategy-last-signal"), width=4),
                            dbc.Col(html.Div(id="strategy-symbol-count"), width=4)
                        ])
                    ]),
                    className="shadow-sm h-100"
                )
            ], width=9)
        ], className="mb-4"),
        
        # Tabs for different strategy sections
        dbc.Tabs([
            # Performance tab
            dbc.Tab(
                html.Div([
                    dbc.Row([
                        dbc.Col([
                            html.H5("Equity Curve", className="mt-3"),
                            dcc.Graph(
                                id="strategy-equity-curve",
                                style={"height": "400px"},
                                figure={"layout": {"title": "Loading..."}}
                            )
                        ], width=8),
                        dbc.Col([
                            html.H5("Performance Metrics", className="mt-3"),
                            html.Div(id="strategy-performance-metrics")
                        ], width=4)
                    ], className="mb-4"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.H5("Trade History"),
                            html.Div(id="strategy-trade-history")
                        ], width=12)
                    ])
                ]),
                label="Performance"
            ),
            
            # Configuration tab
            dbc.Tab(
                html.Div([
                    dbc.Row([
                        dbc.Col([
                            html.H5("Strategy Parameters", className="mt-3"),
                            html.Div(id="strategy-parameters-form")
                        ], width=6),
                        dbc.Col([
                            html.H5("Symbols", className="mt-3"),
                            html.Div(id="strategy-symbols"),
                            html.Hr(),
                            html.H5("Category"),
                            html.Div(id="strategy-category")
                        ], width=6)
                    ])
                ]),
                label="Configuration"
            ),
            
            # Signals tab
            dbc.Tab(
                html.Div([
                    html.H5("Recent Signals", className="mt-3"),
                    html.Div(id="strategy-signals")
                ]),
                label="Signals"
            ),
            
            # Backtest tab
            dbc.Tab(
                html.Div([
                    dbc.Row([
                        # Backtest form
                        dbc.Col([
                            html.H5("Backtest Parameters", className="mt-3"),
                            dbc.Form([
                                dbc.FormGroup([
                                    dbc.Label("Start Date"),
                                    dcc.DatePickerSingle(
                                        id="backtest-start-date",
                                        date=datetime.now() - timedelta(days=365),
                                        display_format="YYYY-MM-DD"
                                    )
                                ]),
                                dbc.FormGroup([
                                    dbc.Label("End Date"),
                                    dcc.DatePickerSingle(
                                        id="backtest-end-date",
                                        date=datetime.now(),
                                        display_format="YYYY-MM-DD"
                                    )
                                ]),
                                dbc.FormGroup([
                                    dbc.Label("Symbols"),
                                    dcc.Dropdown(
                                        id="backtest-symbols",
                                        options=[],
                                        multi=True
                                    )
                                ]),
                                dbc.Button("Run Backtest", id="btn-run-backtest", color="primary")
                            ])
                        ], width=4),
                        
                        # Backtest results
                        dbc.Col([
                            html.H5("Backtest Results", className="mt-3"),
                            html.Div(id="backtest-results", className="d-none"),
                            html.Div(id="backtest-placeholder", children=[
                                html.P("Run a backtest to see results", className="text-muted")
                            ])
                        ], width=8)
                    ])
                ]),
                label="Backtest"
            )
        ], id="strategy-tabs"),
        
        # Refresh interval
        dcc.Interval(
            id="strategy-refresh-interval",
            interval=5000,  # 5 seconds
            n_intervals=0
        )
    ])
    
    return layout


def create_equity_curve(performance_history):
    """Create equity curve chart from performance history"""
    if not performance_history:
        return go.Figure().update_layout(title="No performance data available")
    
    # Create DataFrame
    df = pd.DataFrame(performance_history)
    df["date"] = pd.to_datetime(df["date"])
    
    # Create figure
    fig = go.Figure()
    
    # Add equity curve
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["portfolio_value"],
        mode="lines",
        name="Portfolio Value",
        line=dict(color="rgb(41, 128, 185)")
    ))
    
    # Customize layout
    fig.update_layout(
        title="Strategy Equity Curve",
        xaxis_title="Date",
        yaxis_title="Value ($)",
        height=400,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig


def register_callbacks(app):
    """
    Register callbacks for the strategy view.
    
    Args:
        app: Dash application
    """
    # Callback to update strategy description
    @app.callback(
        Output("strategy-description", "children"),
        Input("strategy-selector", "value")
    )
    def update_strategy_description(strategy_id):
        """Update strategy description based on selected strategy"""
        if not strategy_id:
            return "No strategy selected"
        
        # Get strategy details
        strategy = strategy_service.get_strategy(strategy_id)
        
        if "error" in strategy:
            return strategy["error"]
        
        return [
            html.P(strategy["description"]),
            html.Small(f"Category: {strategy['category'].capitalize()}")
        ]
    
    # Callback to update strategy overview metrics
    @app.callback(
        [
            Output("strategy-win-rate", "children"),
            Output("strategy-profit-factor", "children"),
            Output("strategy-sharpe-ratio", "children"),
            Output("strategy-max-drawdown", "children"),
            Output("strategy-last-signal", "children"),
            Output("strategy-symbol-count", "children")
        ],
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_strategy_overview(strategy_id, n_intervals):
        """Update strategy overview metrics"""
        if not strategy_id:
            empty_metric = create_metric_card("N/A", "0", "N/A")
            return empty_metric, empty_metric, empty_metric, empty_metric, empty_metric, empty_metric
        
        # Get strategy details
        strategy = strategy_service.get_strategy(strategy_id)
        
        if "error" in strategy:
            empty_metric = create_metric_card("Error", "N/A", "Strategy not found")
            return empty_metric, empty_metric, empty_metric, empty_metric, empty_metric, empty_metric
        
        # Format metrics
        win_rate = create_metric_card(
            "Win Rate", 
            f"{strategy['performance']['win_rate']}%", 
            "% of profitable trades"
        )
        
        profit_factor = create_metric_card(
            "Profit Factor", 
            f"{strategy['performance']['profit_factor']:.2f}", 
            "Gross profit / gross loss"
        )
        
        sharpe_ratio = create_metric_card(
            "Sharpe Ratio", 
            f"{strategy['performance']['sharpe_ratio']:.2f}", 
            "Risk-adjusted return"
        )
        
        max_drawdown = create_metric_card(
            "Max Drawdown", 
            f"{strategy['performance']['max_drawdown']:.1f}%", 
            "Largest peak-to-trough decline"
        )
        
        last_signal = create_metric_card(
            "Last Signal", 
            strategy['last_signal'].split()[1] if ' ' in strategy['last_signal'] else strategy['last_signal'],
            strategy['last_signal'].split()[0] if ' ' in strategy['last_signal'] else "Date"
        )
        
        symbol_count = create_metric_card(
            "Symbols", 
            f"{len(strategy['symbols'])}", 
            "Active trading pairs"
        )
        
        return win_rate, profit_factor, sharpe_ratio, max_drawdown, last_signal, symbol_count
    
    # Callback to update equity curve
    @app.callback(
        Output("strategy-equity-curve", "figure"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_equity_curve(strategy_id, n_intervals):
        """Update equity curve chart"""
        if not strategy_id:
            return go.Figure().update_layout(title="No strategy selected")
        
        # Get strategy details
        strategy = strategy_service.get_strategy(strategy_id)
        
        if "error" in strategy:
            return go.Figure().update_layout(title=strategy["error"])
        
        # Create equity curve
        return create_equity_curve(strategy["performance_history"])
    
    # Callback to update performance metrics
    @app.callback(
        Output("strategy-performance-metrics", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_performance_metrics(strategy_id, n_intervals):
        """Update performance metrics"""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Get performance metrics for different timeframes
        metrics = {}
        for timeframe in ["1d", "1w", "1m", "3m", "1y"]:
            metrics[timeframe] = strategy_service.get_performance_metrics(timeframe)
        
        # Create metrics table
        table = dbc.Table(
            [
                html.Thead(
                    html.Tr([
                        html.Th("Metric"),
                        html.Th("1d"),
                        html.Th("1w"),
                        html.Th("1m"),
                        html.Th("3m"),
                        html.Th("1y")
                    ])
                ),
                html.Tbody([
                    html.Tr([
                        html.Td("Return"),
                        html.Td(f"{metrics['1d']['return']:+.2f}%", className="text-success" if metrics['1d']['return'] >= 0 else "text-danger"),
                        html.Td(f"{metrics['1w']['return']:+.2f}%", className="text-success" if metrics['1w']['return'] >= 0 else "text-danger"),
                        html.Td(f"{metrics['1m']['return']:+.2f}%", className="text-success" if metrics['1m']['return'] >= 0 else "text-danger"),
                        html.Td(f"{metrics['3m']['return']:+.2f}%", className="text-success" if metrics['3m']['return'] >= 0 else "text-danger"),
                        html.Td(f"{metrics['1y']['return']:+.2f}%", className="text-success" if metrics['1y']['return'] >= 0 else "text-danger")
                    ]),
                    html.Tr([
                        html.Td("Drawdown"),
                        html.Td(f"{metrics['1d']['drawdown']:.2f}%"),
                        html.Td(f"{metrics['1w']['drawdown']:.2f}%"),
                        html.Td(f"{metrics['1m']['drawdown']:.2f}%"),
                        html.Td(f"{metrics['3m']['drawdown']:.2f}%"),
                        html.Td(f"{metrics['1y']['drawdown']:.2f}%")
                    ]),
                    html.Tr([
                        html.Td("Sharpe"),
                        html.Td(f"{metrics['1d']['sharpe']:.2f}"),
                        html.Td(f"{metrics['1w']['sharpe']:.2f}"),
                        html.Td(f"{metrics['1m']['sharpe']:.2f}"),
                        html.Td(f"{metrics['3m']['sharpe']:.2f}"),
                        html.Td(f"{metrics['1y']['sharpe']:.2f}")
                    ]),
                    html.Tr([
                        html.Td("Win Rate"),
                        html.Td(f"{metrics['1d']['win_rate']:.1f}%"),
                        html.Td(f"{metrics['1w']['win_rate']:.1f}%"),
                        html.Td(f"{metrics['1m']['win_rate']:.1f}%"),
                        html.Td(f"{metrics['3m']['win_rate']:.1f}%"),
                        html.Td(f"{metrics['1y']['win_rate']:.1f}%")
                    ])
                ])
            ],
            bordered=False,
            hover=True,
            responsive=True,
            size="sm"
        )
        
        return table
    
    # Callback to update trade history
    @app.callback(
        Output("strategy-trade-history", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_trade_history(strategy_id, n_intervals):
        """Update trade history table"""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Get trades for the strategy
        trades = strategy_service.get_strategy_trades(strategy_id)
        
        if not trades:
            return html.Div("No trades available")
        
        # Create trades table
        trade_rows = []
        for trade in trades:
            # Format P&L with color
            if trade["profit_loss"] >= 0:
                pnl_cell = html.Td([
                    f"${trade['profit_loss']:.2f}",
                    html.Br(),
                    f"({trade['profit_loss_percent']:+.2f}%)"
                ], className="text-success")
            else:
                pnl_cell = html.Td([
                    f"${trade['profit_loss']:.2f}",
                    html.Br(),
                    f"({trade['profit_loss_percent']:+.2f}%)"
                ], className="text-danger")
            
            trade_rows.append(
                html.Tr([
                    html.Td(trade["timestamp"]),
                    html.Td(trade["symbol"]),
                    html.Td(trade["side"].capitalize()),
                    html.Td(f"${trade['price']:.2f}"),
                    html.Td(f"{trade['quantity']:.6f}"),
                    pnl_cell
                ])
            )
        
        table = dbc.Table(
            [
                html.Thead(
                    html.Tr([
                        html.Th("Timestamp"),
                        html.Th("Symbol"),
                        html.Th("Side"),
                        html.Th("Price"),
                        html.Th("Quantity"),
                        html.Th("P&L")
                    ])
                ),
                html.Tbody(trade_rows)
            ],
            bordered=True,
            hover=True,
            responsive=True,
            size="sm"
        )
        
        return table
    
    # Callback to update strategy parameters form
    @app.callback(
        Output("strategy-parameters-form", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_strategy_parameters_form(strategy_id, n_intervals):
        """Update strategy parameters form"""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Get strategy details
        strategy = strategy_service.get_strategy(strategy_id)
        
        if "error" in strategy:
            return html.Div(strategy["error"])
        
        # Create form
        parameters = strategy["parameters"]
        form_groups = []
        
        for param_name, param_value in parameters.items():
            # Format the parameter name for display
            display_name = param_name.replace('_', ' ').title()
            
            # Create appropriate input based on parameter type
            if isinstance(param_value, bool):
                # Boolean parameter - use a toggle switch
                form_groups.append(
                    dbc.FormGroup([
                        dbc.Label(display_name),
                        dbc.Checklist(
                            options=[{"label": "", "value": 1}],
                            value=[1] if param_value else [],
                            id={"type": "strategy-param", "param": param_name},
                            switch=True
                        )
                    ])
                )
            elif isinstance(param_value, (int, float)):
                # Numeric parameter - use a number input
                form_groups.append(
                    dbc.FormGroup([
                        dbc.Label(display_name),
                        dbc.Input(
                            type="number",
                            value=param_value,
                            id={"type": "strategy-param", "param": param_name},
                            step="any" if isinstance(param_value, float) else 1
                        )
                    ])
                )
            else:
                # String or other parameter - use a text input
                form_groups.append(
                    dbc.FormGroup([
                        dbc.Label(display_name),
                        dbc.Input(
                            type="text",
                            value=str(param_value),
                            id={"type": "strategy-param", "param": param_name}
                        )
                    ])
                )
        
        # Add submit button
        form_groups.append(
            dbc.Button("Update Parameters", id="btn-update-parameters", color="primary")
        )
        
        return dbc.Form(form_groups)
    
    # Callback to update strategy symbols
    @app.callback(
        Output("strategy-symbols", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_strategy_symbols(strategy_id, n_intervals):
        """Update strategy symbols display"""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Get strategy details
        strategy = strategy_service.get_strategy(strategy_id)
        
        if "error" in strategy:
            return html.Div(strategy["error"])
        
        # Create badges for symbols
        symbol_badges = []
        for symbol in strategy["symbols"]:
            symbol_badges.append(
                dbc.Badge(symbol, color="primary", className="mr-2 mb-2", pill=True)
            )
        
        return html.Div(symbol_badges)
    
    # Callback to update strategy category
    @app.callback(
        Output("strategy-category", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_strategy_category(strategy_id, n_intervals):
        """Update strategy category display"""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Get strategy details
        strategy = strategy_service.get_strategy(strategy_id)
        
        if "error" in strategy:
            return html.Div(strategy["error"])
        
        # Determine badge color based on category
        if strategy["category"] == "momentum":
            color = "success"
        elif strategy["category"] == "mean_reversion":
            color = "info"
        elif strategy["category"] == "arbitrage":
            color = "warning"
        elif strategy["category"] == "market_making":
            color = "primary"
        else:
            color = "secondary"
        
        return dbc.Badge(strategy["category"].replace("_", " ").title(), color=color, className="p-2")
    
    # Callback to update strategy signals
    @app.callback(
        Output("strategy-signals", "children"),
        [
            Input("strategy-selector", "value"),
            Input("strategy-refresh-interval", "n_intervals")
        ]
    )
    def update_strategy_signals(strategy_id, n_intervals):
        """Update strategy signals"""
        if not strategy_id:
            return html.Div("No strategy selected")
        
        # Get signals for the strategy
        signals = strategy_service.get_strategy_signals(strategy_id)
        
        if not signals:
            return html.Div("No signals available")
        
        # Create signal cards
        signal_cards = []
        for signal in signals:
            # Determine card color based on signal type
            if signal["type"] == "buy":
                header_color = "success"
                icon = "fas fa-arrow-up"
            else:
                header_color = "danger"
                icon = "fas fa-arrow-down"
            
            # Create card
            card = dbc.Card(
                [
                    dbc.CardHeader([
                        html.I(className=f"{icon} mr-2"),
                        f"{signal['type'].upper()} {signal['symbol']} (Strength: {signal['strength']}/10)"
                    ], className=f"bg-{header_color} text-white"),
                    dbc.CardBody([
                        html.P(signal["reason"]),
                        html.Footer(
                            dbc.Badge(
                                "Executed" if signal["executed"] else "Pending", 
                                color="success" if signal["executed"] else "warning"
                            ),
                            className="text-muted text-right"
                        )
                    ])
                ],
                className="mb-3"
            )
            
            signal_cards.append(card)
        
        return html.Div(signal_cards)
    
    # Callback to update backtest symbols dropdown
    @app.callback(
        Output("backtest-symbols", "options"),
        Input("strategy-selector", "value")
    )
    def update_backtest_symbols(strategy_id):
        """Update backtest symbols dropdown options"""
        if not strategy_id:
            return []
        
        # Get strategy details
        strategy = strategy_service.get_strategy(strategy_id)
        
        if "error" in strategy:
            return []
        
        # Create options from strategy symbols
        options = [{"label": s, "value": s} for s in strategy["symbols"]]
        
        return options
    
    # Callback to update backtest symbols value
    @app.callback(
        Output("backtest-symbols", "value"),
        Input("backtest-symbols", "options")
    )
    def update_backtest_symbols_value(options):
        """Update backtest symbols dropdown value"""
        if not options:
            return []
        
        # Default to all symbols
        return [option["value"] for option in options]
    
    # Callback to run backtest and show results
    @app.callback(
        [
            Output("backtest-results", "children"),
            Output("backtest-results", "className"),
            Output("backtest-placeholder", "className")
        ],
        Input("btn-run-backtest", "n_clicks"),
        [
            State("strategy-selector", "value"),
            State("backtest-start-date", "date"),
            State("backtest-end-date", "date"),
            State("backtest-symbols", "value")
        ]
    )
    def run_backtest(n_clicks, strategy_id, start_date, end_date, symbols):
        """Run backtest and show results"""
        if not n_clicks or not strategy_id:
            return html.Div(), "d-none", ""
        
        # Run backtest
        results = strategy_service.run_backtest(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols
        )
        
        if not results["success"]:
            return html.Div(f"Error: {results.get('message', 'Unknown error')}"), "", "d-none"
        
        # Create results display
        backtest_results = html.Div([
            # Summary statistics
            dbc.Row([
                dbc.Col([
                    html.H6("Summary Statistics"),
                    dbc.Table(
                        [
                            html.Tbody([
                                html.Tr([
                                    html.Td("Total Return"),
                                    html.Td(f"{results['results']['total_return']:+.2f}%", 
                                          className="text-success" if results['results']['total_return'] >= 0 else "text-danger")
                                ]),
                                html.Tr([
                                    html.Td("Annualized Return"),
                                    html.Td(f"{results['results']['annualized_return']:+.2f}%",
                                          className="text-success" if results['results']['annualized_return'] >= 0 else "text-danger")
                                ]),
                                html.Tr([
                                    html.Td("Max Drawdown"),
                                    html.Td(f"{results['results']['max_drawdown']:.2f}%")
                                ]),
                                html.Tr([
                                    html.Td("Sharpe Ratio"),
                                    html.Td(f"{results['results']['sharpe_ratio']:.2f}")
                                ]),
                                html.Tr([
                                    html.Td("Win Rate"),
                                    html.Td(f"{results['results']['win_rate']:.2f}%")
                                ]),
                                html.Tr([
                                    html.Td("Profit Factor"),
                                    html.Td(f"{results['results']['profit_factor']:.2f}")
                                ]),
                                html.Tr([
                                    html.Td("Total Trades"),
                                    html.Td(f"{results['results']['trades']}")
                                ])
                            ])
                        ],
                        bordered=False,
                        size="sm"
                    )
                ], width=4),
                
                # Equity curve
                dbc.Col([
                    html.H6("Equity Curve"),
                    dcc.Graph(
                        figure=create_backtest_equity_curve(results['results']['equity_curve']),
                        style={"height": "300px"}
                    )
                ], width=8)
            ])
        ])
        
        return backtest_results, "", "d-none"
    
    # Callback to toggle strategy active state
    @app.callback(
        [
            Output("strategy-action-output", "children"),
            Output("strategy-active-toggle", "value")
        ],
        [
            Input("strategy-active-toggle", "value"),
            Input("strategy-selector", "value")
        ]
    )
    def toggle_strategy_active(active_value, strategy_id):
        """Toggle strategy active state"""
        ctx = dash.callback_context
        
        if not ctx.triggered or not strategy_id:
            # Initial load - get current status
            strategy = strategy_service.get_strategy(strategy_id)
            if "error" in strategy:
                return html.Div(), []
            return html.Div(), [1] if strategy["active"] else []
        
        # Toggle was clicked
        is_active = bool(active_value and 1 in active_value)
        result = strategy_service.toggle_strategy(strategy_id, is_active)
        
        if result["success"]:
            return dbc.Alert(result["message"], color="success", dismissable=True), active_value
        else:
            return dbc.Alert(result["message"], color="danger", dismissable=True), [] if is_active else [1]
    
    # Callback to update parameters
    @app.callback(
        Output("strategy-parameters-form", "className"),
        Input("btn-update-parameters", "n_clicks"),
        [
            State("strategy-selector", "value"),
            State({"type": "strategy-param", "param": dash.ALL}, "value"),
            State({"type": "strategy-param", "param": dash.ALL}, "id")
        ]
    )
    def update_parameters(n_clicks, strategy_id, param_values, param_ids):
        """Update strategy parameters"""
        if not n_clicks or not strategy_id:
            return ""
        
        # Build parameters dictionary
        parameters = {}
        for i, param_id in enumerate(param_ids):
            param_name = param_id["param"]
            param_value = param_values[i]
            
            # Handle toggle switches
            if isinstance(param_value, list):
                param_value = bool(param_value and 1 in param_value)
            
            parameters[param_name] = param_value
        
        # Update parameters
        result = strategy_service.update_strategy_parameters(strategy_id, parameters)
        
        # We're not showing a notification, just returning an empty class name
        return ""


def create_backtest_equity_curve(equity_curve_data):
    """Create equity curve chart for backtest results"""
    # Create DataFrame
    df = pd.DataFrame(equity_curve_data)
    df["date"] = pd.to_datetime(df["date"])
    
    # Create figure
    fig = go.Figure()
    
    # Add equity curve
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["equity"],
        mode="lines",
        name="Equity",
        line=dict(color="rgb(41, 128, 185)")
    ))
    
    # Customize layout
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=20),
        height=300,
        yaxis_title="Equity ($)",
        xaxis_title=None,
        showlegend=False
    )
    
    return fig 