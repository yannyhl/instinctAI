"""
Portfolio View

This module provides the portfolio view for the dashboard.
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

# Import dashboard modules
from ..components import performance_card, control_panel
from ..services import portfolio_service

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.portfolio_view"})


def layout():
    """
    Create the portfolio view layout.
    
    Returns:
        Dash layout
    """
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.H1("Portfolio Overview"),
                html.P("Monitor portfolio performance, positions, and allocation."),
            ], width=8),
            dbc.Col([
                control_panel.create_control_panel("portfolio")
            ], width=4),
        ], className="mb-4"),
        
        dbc.Row([
            # Portfolio summary cards
            dbc.Col([
                performance_card.create_performance_card(
                    "Total Value", 
                    id="total-value-card",
                    icon="wallet"
                ),
            ], width=3),
            dbc.Col([
                performance_card.create_performance_card(
                    "Daily P&L", 
                    id="daily-pnl-card",
                    icon="graph-up"
                ),
            ], width=3),
            dbc.Col([
                performance_card.create_performance_card(
                    "Open Positions", 
                    id="open-positions-card",
                    icon="layers"
                ),
            ], width=3),
            dbc.Col([
                performance_card.create_performance_card(
                    "Drawdown", 
                    id="drawdown-card",
                    icon="arrow-down"
                ),
            ], width=3),
        ], className="mb-4"),
        
        dbc.Row([
            # Equity curve
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Equity Curve"),
                    dbc.CardBody([
                        dcc.Graph(id="equity-curve-graph")
                    ])
                ])
            ], width=8),
            
            # Asset allocation
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Asset Allocation"),
                    dbc.CardBody([
                        dcc.Graph(id="asset-allocation-graph")
                    ])
                ])
            ], width=4),
        ], className="mb-4"),
        
        dbc.Row([
            # Open positions
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Open Positions"),
                    dbc.CardBody([
                        html.Div(id="open-positions-content")
                    ])
                ])
            ], width=6),
            
            # Recent trades
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent Trades"),
                    dbc.CardBody([
                        html.Div(id="recent-trades-content")
                    ])
                ])
            ], width=6),
        ], className="mb-4"),
        
        dbc.Row([
            # Strategy allocation
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Strategy Allocation"),
                    dbc.CardBody([
                        dcc.Graph(id="strategy-allocation-graph")
                    ])
                ])
            ], width=6),
            
            # Risk metrics
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Risk Metrics"),
                    dbc.CardBody([
                        html.Div(id="risk-metrics-content")
                    ])
                ])
            ], width=6),
        ])
    ])


def register_callbacks(app):
    """
    Register callbacks for the portfolio view.
    
    Args:
        app: Dash application
    """
    # These are placeholder callbacks that will be implemented properly later
    
    # Total value card update
    @app.callback(
        Output("total-value-card", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_total_value_card(n_intervals):
        """Update the total value card with placeholder data"""
        return [
            html.H3("$100,000", className="card-title"),
            html.P("Total portfolio value", className="card-text"),
            html.Span("↑ $1,200 (1.2%)", className="text-success")
        ]
    
    # Daily P&L card update
    @app.callback(
        Output("daily-pnl-card", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_daily_pnl_card(n_intervals):
        """Update the daily P&L card with placeholder data"""
        return [
            html.H3("$2,450", className="card-title"),
            html.P("Today's profit/loss", className="card-text"),
            html.Span("↑ 2.45%", className="text-success")
        ]
    
    # Open positions card update
    @app.callback(
        Output("open-positions-card", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_open_positions_card(n_intervals):
        """Update the open positions card with placeholder data"""
        return [
            html.H3("12", className="card-title"),
            html.P("Active positions", className="card-text"),
            html.Span("6 long / 6 short", className="text-primary")
        ]
    
    # Drawdown card update
    @app.callback(
        Output("drawdown-card", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_drawdown_card(n_intervals):
        """Update the drawdown card with placeholder data"""
        return [
            html.H3("3.2%", className="card-title"),
            html.P("Current drawdown", className="card-text"),
            html.Span("Peak: $103,200", className="text-muted")
        ]
    
    # Equity curve graph update
    @app.callback(
        Output("equity-curve-graph", "figure"),
        Input("slow-interval", "n_intervals"),
    )
    def update_equity_curve(n_intervals):
        """Update the equity curve graph with placeholder data"""
        # Create placeholder data
        dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
        equity = [100000]
        
        # Generate a simple upward trend with some noise
        for i in range(1, len(dates)):
            prev = equity[i-1]
            change = prev * (0.005 + (datetime.now().microsecond / 10000000 - 0.5) * 0.01)
            equity.append(prev + change)
        
        df = pd.DataFrame({
            'date': dates,
            'equity': equity
        })
        
        # Create the plot
        fig = px.line(df, x='date', y='equity', title='Portfolio Equity Curve')
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Value ($)",
            template="plotly_dark" if config_manager.get("dashboard.theme", "dark") == "dark" else "plotly"
        )
        
        return fig
    
    # Asset allocation graph update
    @app.callback(
        Output("asset-allocation-graph", "figure"),
        Input("slow-interval", "n_intervals"),
    )
    def update_asset_allocation(n_intervals):
        """Update the asset allocation graph with placeholder data"""
        # Create placeholder data
        assets = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT']
        values = [30000, 25000, 15000, 10000, 5000]
        
        # Create the plot
        fig = px.pie(
            values=values,
            names=assets,
            title='Asset Allocation'
        )
        fig.update_layout(
            template="plotly_dark" if config_manager.get("dashboard.theme", "dark") == "dark" else "plotly"
        )
        
        return fig
    
    # Strategy allocation graph update
    @app.callback(
        Output("strategy-allocation-graph", "figure"),
        Input("slow-interval", "n_intervals"),
    )
    def update_strategy_allocation(n_intervals):
        """Update the strategy allocation graph with placeholder data"""
        # Create placeholder data
        strategies = ['Statistical Arbitrage', 'Funding Rate', 'Market Microstructure', 'ML Strategy', 'Trend Following']
        values = [25000, 20000, 20000, 15000, 20000]
        
        # Create the plot
        fig = px.pie(
            values=values,
            names=strategies,
            title='Strategy Allocation'
        )
        fig.update_layout(
            template="plotly_dark" if config_manager.get("dashboard.theme", "dark") == "dark" else "plotly"
        )
        
        return fig
    
    # Open positions table update
    @app.callback(
        Output("open-positions-content", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_open_positions(n_intervals):
        """Update the open positions table with placeholder data"""
        # Create placeholder data
        positions = [
            {"symbol": "BTC/USD", "type": "long", "entry": 50000, "current": 52000, "size": 0.5, "pnl": "+4.0%"},
            {"symbol": "ETH/USD", "type": "long", "entry": 2000, "current": 2100, "size": 10, "pnl": "+5.0%"},
            {"symbol": "SOL/USD", "type": "short", "entry": 100, "current": 95, "size": 100, "pnl": "+5.0%"},
            {"symbol": "ADA/USD", "type": "long", "entry": 0.5, "current": 0.48, "size": 10000, "pnl": "-4.0%"},
            {"symbol": "DOT/USD", "type": "short", "entry": 10, "current": 10.5, "size": 500, "pnl": "-5.0%"},
        ]
        
        # Create table
        return html.Table([
            html.Thead(
                html.Tr([
                    html.Th("Symbol"),
                    html.Th("Direction"),
                    html.Th("Entry Price"),
                    html.Th("Current Price"),
                    html.Th("Size"),
                    html.Th("P&L")
                ])
            ),
            html.Tbody([
                html.Tr([
                    html.Td(position["symbol"]),
                    html.Td(html.Span(position["type"].capitalize(), className=f"badge bg-{'success' if position['type'] == 'long' else 'danger'}")),
                    html.Td(f"${position['entry']}"),
                    html.Td(f"${position['current']}"),
                    html.Td(position["size"]),
                    html.Td(html.Span(position["pnl"], className=f"text-{'success' if '+' in position['pnl'] else 'danger'}"))
                ]) for position in positions
            ])
        ], className="table table-striped table-sm")
    
    # Recent trades table update
    @app.callback(
        Output("recent-trades-content", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_recent_trades(n_intervals):
        """Update the recent trades table with placeholder data"""
        # Create placeholder data
        trades = [
            {"date": "2023-05-01 14:30", "symbol": "BTC/USD", "type": "buy", "price": 49800, "size": 0.5, "fee": "$24.90"},
            {"date": "2023-05-01 13:15", "symbol": "ETH/USD", "type": "buy", "price": 1980, "size": 10, "fee": "$19.80"},
            {"date": "2023-05-01 12:45", "symbol": "SOL/USD", "type": "sell", "price": 100, "size": 100, "fee": "$10.00"},
            {"date": "2023-05-01 10:30", "symbol": "ADA/USD", "type": "buy", "price": 0.5, "size": 10000, "fee": "$5.00"},
            {"date": "2023-05-01 09:15", "symbol": "DOT/USD", "type": "sell", "price": 10, "size": 500, "fee": "$5.00"},
        ]
        
        # Create table
        return html.Table([
            html.Thead(
                html.Tr([
                    html.Th("Date/Time"),
                    html.Th("Symbol"),
                    html.Th("Type"),
                    html.Th("Price"),
                    html.Th("Size"),
                    html.Th("Fee")
                ])
            ),
            html.Tbody([
                html.Tr([
                    html.Td(trade["date"]),
                    html.Td(trade["symbol"]),
                    html.Td(html.Span(trade["type"].capitalize(), className=f"badge bg-{'success' if trade['type'] == 'buy' else 'danger'}")),
                    html.Td(f"${trade['price']}"),
                    html.Td(trade["size"]),
                    html.Td(trade["fee"])
                ]) for trade in trades
            ])
        ], className="table table-striped table-sm")
    
    # Risk metrics update
    @app.callback(
        Output("risk-metrics-content", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_risk_metrics(n_intervals):
        """Update the risk metrics with placeholder data"""
        # Create placeholder data
        metrics = [
            {"name": "Sharpe Ratio", "value": "1.8", "description": "Risk-adjusted return"},
            {"name": "Sortino Ratio", "value": "2.5", "description": "Downside risk-adjusted return"},
            {"name": "Maximum Drawdown", "value": "8.5%", "description": "Largest peak-to-trough decline"},
            {"name": "Value at Risk (95%)", "value": "$2,500", "description": "Potential daily loss at 95% confidence"},
            {"name": "Beta to BTC", "value": "0.35", "description": "Portfolio sensitivity to BTC movements"},
            {"name": "Win Rate", "value": "62%", "description": "Percentage of winning trades"}
        ]
        
        # Create metrics display
        return html.Div([
            html.Div([
                html.Div([
                    html.H5(metric["name"], className="mb-0"),
                    html.P(metric["value"], className="h3 mb-0"),
                    html.Small(metric["description"], className="text-muted")
                ], className="p-3 border rounded") 
            ], className="col-md-6 mb-3") for metric in metrics
        ], className="row") 