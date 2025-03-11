"""
Dashboard Application

This module provides the main application for the trading dashboard.
"""

import os
import sys
import json
import logging
import threading
import time
import atexit
from typing import Dict, Any, List, Optional
from datetime import datetime

import dash
from dash import dcc, html, callback, Output, Input, State
import dash_bootstrap_components as dbc
from flask import Flask

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import core modules
from core import config_manager, metrics, logging as log_manager, tracing

# Import dashboard modules
from dashboard.config import get_dashboard_config, get_view_config

# Import components
from dashboard.components.nav_bar import create_navbar
from dashboard.components.status_card import create_status_card, create_metric_card
from dashboard.components.performance_card import create_performance_card, create_value_card
from dashboard.components.control_panel import create_control_panel

# Import views
from dashboard.views.system_view import create_system_view
from dashboard.views.portfolio_view import create_portfolio_view
from dashboard.views.market_view import create_market_view
from dashboard.views.strategy_view import create_strategy_view
from dashboard.views.strategy_monitoring_view import create_strategy_monitoring_view
from dashboard.views.performance_dashboard_view import create_performance_dashboard_view

# Import views callback registrations
from dashboard.views import system_view, portfolio_view, market_view, strategy_view, strategy_monitoring_view, performance_dashboard_view

# Import services
from dashboard.services import system_service, portfolio_service, market_service, strategy_service

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.app"})

# Global variables for thread management
_app_instance = None
_server_thread = None
_shutdown_event = threading.Event()
_running = False


def create_app():
    """
    Create the Dash application.
    
    Returns:
        Dash application
    """
    global _app_instance
    
    # Return existing instance if already created
    if _app_instance is not None:
        return _app_instance
    
    # Load configuration
    config = get_dashboard_config()
    
    # Set up metrics
    metrics_client = metrics.get_metrics_client()
    dashboard_request_counter = metrics_client.counter(
        name="dashboard_requests_total",
        description="Total number of dashboard requests",
        labels=["view", "method"]
    )
    
    # Set up tracing
    tracer = tracing.get_tracer("dashboard")
    
    # Initialize Flask server
    server = Flask(__name__)
    
    # Initialize Dash app
    external_stylesheets = [
        dbc.themes.BOOTSTRAP if config.get("theme") == "light" else dbc.themes.DARKLY,
        "https://use.fontawesome.com/releases/v5.15.4/css/all.css"
    ]
    
    app = dash.Dash(
        __name__,
        server=server,
        external_stylesheets=external_stylesheets,
        suppress_callback_exceptions=True,
        meta_tags=[
            {"name": "viewport", "content": "width=device-width, initial-scale=1"}
        ],
    )
    
    app.title = "Instinct AI Trading Platform"
    
    # Set interval values from configuration
    refresh_intervals = config.get("refresh_intervals", {})
    fast_interval = refresh_intervals.get("fast", 1000)
    medium_interval = refresh_intervals.get("medium", 5000)
    slow_interval = refresh_intervals.get("slow", 30000)
    
    # Define app layout with navigation and content area
    app.layout = html.Div([
        # Store for current view
        dcc.Store(id="current-view", data="system"),
        
        # Global intervals for data refresh
        dcc.Interval(id="fast-interval", interval=fast_interval, n_intervals=0),
        dcc.Interval(id="medium-interval", interval=medium_interval, n_intervals=0),
        dcc.Interval(id="slow-interval", interval=slow_interval, n_intervals=0),
        
        # Navbar
        create_navbar(theme=config.get("theme", "light")),
        
        # Main content
        dbc.Container(
            fluid=True,
            className="mt-4",
            children=[
                dbc.Row([
                    # Left sidebar with controls
                    dbc.Col(
                        width=3,
                        children=[
                            html.Div(id="control-panel-container"),
                        ]
                    ),
                    
                    # Main content area
                    dbc.Col(
                        width=9,
                        children=[
                            # Content will be populated by the callback based on current view
                            html.Div(id="page-content")
                        ]
                    )
                ])
            ]
        ),
        
        # Footer
        html.Footer(
            className="footer mt-auto py-3 bg-light",
            children=[
                dbc.Container(
                    fluid=True,
                    children=[
                        html.Span(
                            f"Instinct AI Trading Platform © {datetime.now().year}",
                            className="text-muted"
                        ),
                        html.Span(
                            id="server-time",
                            className="text-muted float-right"
                        ),
                        dcc.Interval(
                            id="interval-server-time",
                            interval=1000,  # in milliseconds
                            n_intervals=0
                        )
                    ]
                )
            ]
        )
    ])
    
    # Store configuration in app for access by callbacks
    app.config = config
    
    # Register callbacks
    register_callbacks(app)
    
    # Register view-specific callbacks
    system_view.register_callbacks(app)
    portfolio_view.register_callbacks(app)
    market_view.register_callbacks(app)
    strategy_view.register_callbacks(app)
    strategy_monitoring_view.register_callbacks(app)
    performance_dashboard_view.register_callbacks(app)
    
    # Store the app instance
    _app_instance = app
    
    return app


def register_callbacks(app):
    """
    Register callbacks for the application.
    
    Args:
        app: Dash application
    """
    # Callback to update the content based on the current view
    @app.callback(
        Output("page-content", "children"),
        Input("current-view", "data")
    )
    def render_page_content(view):
        """Render the appropriate view based on the current view selection."""
        if view == "system":
            return create_system_view()
        elif view == "portfolio":
            return create_portfolio_view()
        elif view == "market":
            return create_market_view()
        elif view == "strategy":
            return create_strategy_view()
        elif view == "strategy-monitoring":
            # Create a dummy DashboardState and DashboardController for now
            # In a real implementation, these would be properly initialized
            class DummyState:
                def get_active_strategies(self):
                    return [type('obj', (object,), {'id': 'strategy1', 'name': 'MA Crossover Strategy'})]
            
            class DummyController:
                pass
            
            return create_strategy_monitoring_view(DummyState(), DummyController())
        elif view == "performance-dashboard":
            # Create a dummy DashboardState and DashboardController for now
            class DummyState:
                pass
            
            class DummyController:
                pass
            
            return create_performance_dashboard_view(DummyState(), DummyController())
        else:
            return html.Div(
                dbc.Alert(
                    f"View '{view}' not found",
                    color="danger"
                )
            )
    
    # Callback to update the control panel based on the current view
    @app.callback(
        Output("control-panel-container", "children"),
        Input("current-view", "data")
    )
    def render_control_panel(view):
        """Render the control panel for the current view"""
        return create_control_panel(view)
    
    # Callback to update the current view based on navbar clicks
    @app.callback(
        Output("current-view", "data"),
        [
            Input("nav-system", "n_clicks"),
            Input("nav-portfolio", "n_clicks"),
            Input("nav-market", "n_clicks"),
            Input("nav-strategy", "n_clicks"),
            Input("nav-strategy-monitoring", "n_clicks"),
            Input("nav-performance-dashboard", "n_clicks")
        ],
        State("current-view", "data")
    )
    def update_current_view(n_system, n_portfolio, n_market, n_strategy, n_strategy_monitoring, 
                          n_performance_dashboard, current):
        """Update the current view based on navigation clicks."""
        ctx = dash.callback_context
        
        if not ctx.triggered:
            # No clicks yet, return the current view
            return current
        
        # Get the ID of the element that triggered the callback
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if triggered_id == "nav-system":
            return "system"
        elif triggered_id == "nav-portfolio":
            return "portfolio"
        elif triggered_id == "nav-market":
            return "market"
        elif triggered_id == "nav-strategy":
            return "strategy"
        elif triggered_id == "nav-strategy-monitoring":
            return "strategy-monitoring"
        elif triggered_id == "nav-performance-dashboard":
            return "performance-dashboard"
        
        # Default case, return the current view
        return current
    
    # Callback to update server time
    @app.callback(
        Output("server-time", "children"),
        Input("interval-server-time", "n_intervals")
    )
    def update_server_time(n):
        """Update the server time display"""
        return f"Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # System view callbacks
    
    # Callback to update system state
    @app.callback(
        [
            Output("system-status", "children"),
            Output("cpu-usage", "children"),
            Output("memory-usage", "children"),
            Output("disk-usage", "children")
        ],
        Input("system-refresh-interval", "n_intervals")
    )
    def update_system_state(n):
        """Update the system state information"""
        # Get system state
        state = system_service.get_system_state()
        
        # Create status indicators
        component_statuses = []
        for name, status in state["components"].items():
            color = "success" if status == "online" else "warning" if status == "degraded" else "danger"
            component_statuses.append(
                dbc.Badge(f"{name}: {status}", color=color, className="mr-2 mb-2")
            )
        
        # Create system status indicators
        status_indicators = html.Div([
            html.H5("Component Status"),
            html.Div(component_statuses)
        ])
        
        # Create usage indicators
        cpu_usage = f"{state['cpu']['percent']:.1f}%"
        memory_usage = f"{state['memory']['percent']:.1f}% ({state['memory']['used'] / 1024 / 1024 / 1024:.1f} GB / {state['memory']['total'] / 1024 / 1024 / 1024:.1f} GB)"
        disk_usage = f"{state['disk']['percent']:.1f}% ({state['disk']['used'] / 1024 / 1024 / 1024:.1f} GB / {state['disk']['total'] / 1024 / 1024 / 1024:.1f} GB)"
        
        return status_indicators, cpu_usage, memory_usage, disk_usage
    
    # Callback to update recent logs
    @app.callback(
        Output("recent-logs", "children"),
        Input("logs-refresh-interval", "n_intervals")
    )
    def update_recent_logs(n):
        """Update the recent logs display"""
        # Get recent logs
        logs = system_service.get_recent_logs(limit=10)
        
        # Create log table
        log_rows = []
        for log in logs:
            level_color = {
                "DEBUG": "secondary",
                "INFO": "info",
                "WARNING": "warning",
                "ERROR": "danger",
                "CRITICAL": "danger"
            }.get(log["level"], "secondary")
            
            log_rows.append(
                html.Tr([
                    html.Td(log["timestamp"]),
                    html.Td(html.Span(log["level"], className=f"badge badge-{level_color}")),
                    html.Td(log["component"]),
                    html.Td(log["message"])
                ])
            )
        
        log_table = dbc.Table(
            [
                html.Thead(
                    html.Tr([
                        html.Th("Timestamp"),
                        html.Th("Level"),
                        html.Th("Component"),
                        html.Th("Message")
                    ])
                ),
                html.Tbody(log_rows)
            ],
            bordered=True,
            hover=True,
            responsive=True,
            size="sm"
        )
        
        return log_table
    
    # Callback to handle start/stop system buttons
    @app.callback(
        Output("system-action-output", "children"),
        [
            Input("btn-start-system", "n_clicks"),
            Input("btn-stop-system", "n_clicks"),
            Input("btn-export-logs", "n_clicks")
        ]
    )
    def handle_system_actions(n_start, n_stop, n_export):
        """Handle system control actions"""
        ctx = dash.callback_context
        
        if not ctx.triggered:
            return ""
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if button_id == "btn-start-system":
            result = system_service.start_system()
            return dbc.Alert(result["message"], color="success")
        elif button_id == "btn-stop-system":
            result = system_service.stop_system()
            return dbc.Alert(result["message"], color="warning")
        elif button_id == "btn-export-logs":
            return dbc.Alert("Logs exported successfully", color="info")
        
        return ""
    
    # Portfolio view callbacks
    
    # Callback to update portfolio summary
    @app.callback(
        [
            Output("portfolio-summary", "children"),
            Output("portfolio-value", "children"),
            Output("daily-pnl", "children"),
            Output("weekly-pnl", "children"),
            Output("monthly-pnl", "children")
        ],
        Input("portfolio-refresh-interval", "n_intervals")
    )
    def update_portfolio_summary(n):
        """Update the portfolio summary information"""
        # Get portfolio summary
        summary = portfolio_service.get_portfolio_summary()
        
        # Create asset allocation pie chart
        asset_allocation = dcc.Graph(
            figure={
                "data": [
                    {
                        "labels": list(summary["asset_allocation"].keys()),
                        "values": list(summary["asset_allocation"].values()),
                        "type": "pie",
                        "hole": 0.4,
                        "marker": {
                            "colors": [
                                "#FF9500", "#28A745", "#007BFF", "#6F42C1", "#FD7E14"
                            ]
                        }
                    }
                ],
                "layout": {
                    "title": "Asset Allocation",
                    "height": 300,
                    "margin": {"l": 10, "r": 10, "t": 40, "b": 10}
                }
            }
        )
        
        # Create risk metrics
        risk_metrics = html.Div([
            html.H5("Risk Metrics"),
            dbc.Row([
                dbc.Col(dbc.Card(html.Div([
                    html.H6("Value at Risk (95%)", className="card-subtitle"),
                    html.P(f"${summary['risk_metrics']['var_95']:,.2f}", className="lead")
                ]), body=True)),
                dbc.Col(dbc.Card(html.Div([
                    html.H6("Sharpe Ratio", className="card-subtitle"),
                    html.P(f"{summary['risk_metrics']['sharpe_ratio']:.2f}", className="lead")
                ]), body=True)),
                dbc.Col(dbc.Card(html.Div([
                    html.H6("Max Drawdown", className="card-subtitle"),
                    html.P(f"{summary['risk_metrics']['max_drawdown'] * 100:.1f}%", className="lead")
                ]), body=True)),
                dbc.Col(dbc.Card(html.Div([
                    html.H6("Volatility", className="card-subtitle"),
                    html.P(f"{summary['risk_metrics']['volatility'] * 100:.1f}%", className="lead")
                ]), body=True))
            ])
        ])
        
        # Combine into summary card
        portfolio_summary = html.Div([
            asset_allocation,
            html.Hr(),
            risk_metrics
        ])
        
        # Create value indicators
        portfolio_value = f"${summary['total_value_usd']:,.2f}"
        
        daily_pnl = [
            f"${summary['daily_pnl']:,.2f}",
            html.Span(f" ({summary['daily_pnl_percent']:+.2f}%)", 
                     className="text-success" if summary['daily_pnl_percent'] >= 0 else "text-danger")
        ]
        
        weekly_pnl = [
            f"${summary['weekly_pnl']:,.2f}",
            html.Span(f" ({summary['weekly_pnl_percent']:+.2f}%)", 
                     className="text-success" if summary['weekly_pnl_percent'] >= 0 else "text-danger")
        ]
        
        monthly_pnl = [
            f"${summary['monthly_pnl']:,.2f}",
            html.Span(f" ({summary['monthly_pnl_percent']:+.2f}%)", 
                     className="text-success" if summary['monthly_pnl_percent'] >= 0 else "text-danger")
        ]
        
        return portfolio_summary, portfolio_value, daily_pnl, weekly_pnl, monthly_pnl
    
    # Callback to update positions table
    @app.callback(
        Output("positions-table", "children"),
        Input("positions-refresh-interval", "n_intervals")
    )
    def update_positions_table(n):
        """Update the positions table"""
        # Get positions
        positions = portfolio_service.get_positions()
        
        # Create positions table
        position_rows = []
        for position in positions:
            pnl_color = "success" if position["pnl"] >= 0 else "danger"
            
            position_rows.append(
                html.Tr([
                    html.Td(position["symbol"]),
                    html.Td(f"{position['type']} ({position['side']})"),
                    html.Td(f"${position['entry_price']:,.2f}"),
                    html.Td(f"${position['current_price']:,.2f}"),
                    html.Td(f"{position['quantity']}"),
                    html.Td(f"${position['value_usd']:,.2f}"),
                    html.Td(html.Span([
                        f"${position['pnl']:,.2f}",
                        html.Br(),
                        f"({position['pnl_percent']:+.2f}%)"
                    ], className=f"text-{pnl_color}")),
                    html.Td(position["exchange"]),
                    html.Td(
                        dbc.Button("Close", color="danger", size="sm", id={"type": "close-position", "index": position["symbol"]})
                    )
                ])
            )
        
        positions_table = dbc.Table(
            [
                html.Thead(
                    html.Tr([
                        html.Th("Symbol"),
                        html.Th("Type"),
                        html.Th("Entry Price"),
                        html.Th("Current Price"),
                        html.Th("Quantity"),
                        html.Th("Value"),
                        html.Th("P&L"),
                        html.Th("Exchange"),
                        html.Th("Actions")
                    ])
                ),
                html.Tbody(position_rows)
            ],
            bordered=True,
            hover=True,
            responsive=True,
            size="sm"
        )
        
        return positions_table


def run_server(host: str = None, port: int = None, debug: bool = None) -> None:
    """
    Run the dashboard server.
    
    Args:
        host: Host address to bind to (uses config if None)
        port: Port to listen on (uses config if None)
        debug: Whether to run in debug mode (uses config if None)
    """
    global _running
    
    try:
        # Get configuration
        config = get_dashboard_config()
        
        # Use provided parameters or fall back to configuration
        host = host or config.get("host", "0.0.0.0")
        port = port or config.get("port", 8050)
        debug = debug if debug is not None else config.get("debug", False)
        
        logger.info(f"Starting dashboard server on {host}:{port}")
        app = create_app()
        _running = True
        app.run_server(host=host, port=port, debug=debug)
    except Exception as e:
        logger.error(f"Error running dashboard server: {str(e)}")
        logger.debug("Dashboard server error details", exc_info=True)
    finally:
        _running = False
        logger.info("Dashboard server stopped")


def run_in_thread(host: str = None, port: int = None, debug: bool = None) -> threading.Thread:
    """
    Run the dashboard server in a separate thread.
    
    Args:
        host: Host address to bind to (uses config if None)
        port: Port to listen on (uses config if None)
        debug: Whether to run in debug mode (uses config if None)
        
    Returns:
        Thread object running the server
    """
    global _server_thread, _shutdown_event
    
    # Reset shutdown event
    _shutdown_event.clear()
    
    # Create server thread
    _server_thread = threading.Thread(
        target=lambda: run_server(host, port, debug),
        daemon=True
    )
    
    # Start thread
    _server_thread.start()
    
    # Register shutdown handler
    atexit.register(shutdown)
    
    return _server_thread


def shutdown() -> None:
    """
    Shutdown the dashboard server gracefully.
    """
    global _running, _server_thread, _shutdown_event
    
    if not _running or _server_thread is None:
        logger.info("Dashboard is not running")
        return
    
    logger.info("Shutting down dashboard server...")
    
    # Signal shutdown
    _shutdown_event.set()
    _running = False
    
    # Wait for thread to exit (with timeout)
    if _server_thread is not None:
        _server_thread.join(timeout=5.0)
    
    logger.info("Dashboard server shutdown complete")


def main():
    """
    Main function to run the dashboard application.
    """
    # Create the app
    app = create_app()
    
    # Get configuration
    config = get_dashboard_config()
    host = config.get("host", "0.0.0.0")
    port = config.get("port", 8050)
    debug = config.get("debug", False)
    
    # Check if dashboard is enabled
    if not config.get("enabled", True):
        logger.info("Dashboard is disabled in configuration")
        return
    
    # Run the app
    logger.info(f"Starting dashboard on {host}:{port}")
    app.run_server(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main() 