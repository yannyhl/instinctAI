#!/usr/bin/env python3
"""
Instinct AI Trading Dashboard Application
----------------------------------------
Main dashboard application that provides real-time trading insights
and visualization of market data and strategy performance.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
import threading
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table, ctx
import logging

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import project modules
import config
from dashboard.market_data_handler import get_market_data_handler
from dashboard.layout_manager import (
    set_theme, create_main_layout, create_card, create_tab_layout, 
    create_button, create_alert, create_separator, create_input_group
)
from dashboard.components import (
    create_price_chart, create_volume_profile_chart, create_regime_distribution_chart,
    create_correlation_matrix_chart, create_performance_chart, create_market_summary_cards,
    create_alert_cards, create_performance_metrics_table, create_settings_panel
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the data handler
data_handler = get_market_data_handler()

# Initialize the app
app = dash.Dash(
    __name__,
    title="Instinct AI Trading Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True
)

# Define sidebar
sidebar = html.Div([
    # Dashboard settings
    create_settings_panel(),
    
    # Quick access
    create_card(
        title="Quick Access", 
        content=[
            create_button(
                text="Market Overview",
                id="navigate-market-btn",
                type="secondary",
                size="sm",
                style={"margin-bottom": "10px", "width": "100%"}
            ),
            create_button(
                text="Strategy Performance",
                id="navigate-performance-btn",
                type="secondary",
                size="sm",
                style={"margin-bottom": "10px", "width": "100%"}
            ),
            create_button(
                text="Market Analysis",
                id="navigate-analysis-btn",
                type="secondary",
                size="sm",
                style={"margin-bottom": "10px", "width": "100%"}
            ),
            create_button(
                text="Refresh All Data",
                id="refresh-button",
                type="primary",
                size="sm",
                style={"width": "100%"}
            ),
        ]
    ),
    
    # Status section
    html.Div(id="refresh-status"),
])

# Define main content
main_content = [
    # Market Overview Section
    html.Div([
        html.H2("Market Overview"),
        
        # Symbol and timeframe selectors
        html.Div([
            html.Div([
                html.Label("Symbol:", style={"font-weight": "bold"}),
                dcc.Dropdown(
                    id="symbol-selector",
                    options=[
                        {"label": symbol, "value": symbol}
                        for symbol in config.TRADING_CONFIG['symbols']
                    ],
                    value=config.TRADING_CONFIG['symbols'][0] if config.TRADING_CONFIG['symbols'] else "BTC/USDT",
                    clearable=False,
                    style={"width": "200px"}
                ),
            ], style={"margin-right": "20px", "display": "inline-block"}),
            
            html.Div([
                html.Label("Timeframe:", style={"font-weight": "bold"}),
                dcc.Dropdown(
                    id="timeframe-selector",
                    options=[
                        {"label": "1 minute", "value": "1m"},
                        {"label": "5 minutes", "value": "5m"},
                        {"label": "15 minutes", "value": "15m"},
                        {"label": "1 hour", "value": "1h"},
                        {"label": "4 hours", "value": "4h"},
                        {"label": "1 day", "value": "1d"},
                    ],
                    value="1h",
                    clearable=False,
                    style={"width": "200px"}
                ),
            ], style={"display": "inline-block"}),
        ], style={"margin-bottom": "15px"}),
        
        # Market summary cards
        html.Div(id="market-summary-cards", style={"margin-bottom": "20px"}),
        
        # Price chart
        create_card(
            title="Price Chart",
            content=html.Div(id="price-chart-container")
        ),
        
        # Volume Profile and Regime Distribution
        html.Div([
            html.Div([
                create_card(
                    title="Volume Profile",
                    content=html.Div(id="volume-profile-container")
                )
            ], style={"width": "48%", "display": "inline-block"}),
            
            html.Div([
                create_card(
                    title="Market Regime Distribution",
                    content=html.Div(id="regime-distribution-container")
                )
            ], style={"width": "48%", "display": "inline-block", "float": "right"})
        ]),
    ], id="market-section"),
    
    create_separator(),
    
    # Strategy Performance Section
    html.Div([
        html.H2("Strategy Performance"),
        
        # Performance chart
        create_card(
            title="Performance Comparison",
            content=html.Div(id="performance-chart-container")
        ),
        
        # Performance metrics table
        create_card(
            title="Performance Metrics",
            content=html.Div(id="performance-metrics-container")
        ),
    ], id="performance-section"),
    
    create_separator(),
    
    # Market Analysis Section
    html.Div([
        html.H2("Market Analysis"),
        
        # Correlation matrix
        create_card(
            title="Asset Correlation",
            content=html.Div(id="correlation-matrix-container")
        ),
        
        # Alert section
        create_card(
            title="Market Alerts & Events",
            content=html.Div(id="alerts-container")
        ),
    ], id="analysis-section"),
    
    # Auto-update interval
    dcc.Interval(
        id="interval-component",
        interval=60*1000,  # in milliseconds (1 minute)
        n_intervals=0
    ),
    
    # Store for settings
    dcc.Store(id='settings-store', data={
        'theme': 'default',
        'update_interval': 60,
        'favorite_symbols': ['BTC/USDT', 'ETH/USDT']
    })
]

# Define the main layout
app.layout = create_main_layout(
    title="Instinct AI Trading Dashboard",
    subtitle="Real-time market monitor and trading strategy insights",
    content=main_content,
    sidebar=sidebar,
    sidebar_width="250px",
    last_update_id="last-update-time"
)

# Callbacks
@callback(
    Output("price-chart-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("symbol-selector", "value"),
     Input("timeframe-selector", "value"),
     Input("refresh-button", "n_clicks"),
     Input("settings-store", "data")]
)
def update_price_chart(n_intervals, symbol, timeframe, n_clicks, settings):
    """Update the price chart based on the selected symbol and timeframe."""
    # Get chart data
    chart_data = data_handler.get_price_chart_data(
        symbol=symbol,
        timeframe=timeframe,
        n_periods=100
    )
    
    # Create price chart
    return create_price_chart(chart_data)

@callback(
    Output("market-summary-cards", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks"),
     Input("settings-store", "data")]
)
def update_market_summary_cards(n_intervals, n_clicks, settings):
    """Update the market summary cards with latest market data."""
    # Get market overview data
    overview = data_handler.get_market_overview()
    
    # Filter to favorite symbols if set in settings
    if settings and 'favorite_symbols' in settings and settings['favorite_symbols']:
        market_data = [data for data in overview['market_data'] 
                      if data['symbol'] in settings['favorite_symbols']]
    else:
        market_data = overview['market_data']
    
    # Create summary cards
    return create_market_summary_cards(market_data)

@callback(
    Output("volume-profile-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("symbol-selector", "value"),
     Input("timeframe-selector", "value"),
     Input("refresh-button", "n_clicks")]
)
def update_volume_profile_chart(n_intervals, symbol, timeframe, n_clicks):
    """Update the volume profile chart based on the selected symbol and timeframe."""
    # Get volume profile data
    profile_data = data_handler.get_volume_profile(
        symbol=symbol,
        timeframe=timeframe,
        n_periods=100,
        n_bins=20
    )
    
    # Create volume profile chart
    return create_volume_profile_chart(profile_data)

@callback(
    Output("regime-distribution-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("symbol-selector", "value"),
     Input("refresh-button", "n_clicks")]
)
def update_regime_distribution_chart(n_intervals, symbol, n_clicks):
    """Update the regime distribution chart for the selected symbol."""
    # Get regime distribution data
    regime_data = data_handler.get_regime_distribution(symbol)
    
    # Create regime distribution chart
    return create_regime_distribution_chart(regime_data)

@callback(
    Output("correlation-matrix-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_correlation_matrix(n_intervals, n_clicks):
    """Update the correlation matrix heatmap."""
    # Get correlation matrix data
    matrix_data = data_handler.get_correlation_matrix()
    
    # Create correlation matrix chart
    return create_correlation_matrix_chart(matrix_data)

@callback(
    Output("performance-metrics-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_performance_metrics_table(n_intervals, n_clicks):
    """Update the performance metrics table."""
    # Get strategy performance data
    performance_data = data_handler.get_strategy_performance()
    
    # Create performance metrics table
    return create_performance_metrics_table(
        strategy_names=performance_data['strategies'],
        metrics_list=performance_data['metrics']
    )

@callback(
    Output("performance-chart-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_performance_chart(n_intervals, n_clicks):
    """Update the performance comparison chart."""
    # This is a placeholder - in production we would get actual strategy performance data
    # For now, simulate performance data for two strategies
    
    # Create date range
    dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
    
    # Create random cumulative performance for two strategies
    np.random.seed(42)  # For reproducibility
    strat1_returns = np.random.normal(0.001, 0.01, len(dates)).cumsum() + 1
    strat2_returns = np.random.normal(0.0015, 0.015, len(dates)).cumsum() + 1
    benchmark_returns = np.random.normal(0.0005, 0.008, len(dates)).cumsum() + 1
    
    # Create DataFrames
    strat1_df = pd.DataFrame({
        'portfolio_value': strat1_returns
    }, index=dates)
    
    strat2_df = pd.DataFrame({
        'portfolio_value': strat2_returns
    }, index=dates)
    
    benchmark_df = pd.DataFrame({
        'close': benchmark_returns
    }, index=dates)
    
    # Create dictionary of performance data
    performance_data = {
        'LSTM Strategy': strat1_df,
        'Volume Profile Strategy': strat2_df,
        'BTC/USDT': benchmark_df
    }
    
    # Create performance chart
    return create_performance_chart(
        strategies=['LSTM Strategy', 'Volume Profile Strategy'],
        performance_data=performance_data
    )

@callback(
    Output("alerts-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_alerts_section(n_intervals, n_clicks):
    """Update the alerts and events section."""
    # Get alerts
    alerts = data_handler.get_alerts()
    
    # Create alert cards
    return create_alert_cards(alerts)

@callback(
    Output("last-update-time", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_last_update_time(n_intervals, n_clicks):
    """Update the last update time indicator."""
    # Get the market monitor's last update time
    market_monitor = data_handler.market_monitor
    last_update = market_monitor.last_update_time
    
    if last_update:
        return f"Last updated: {last_update.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        return "Data not yet loaded"

@callback(
    Output("refresh-status", "children"),
    [Input("refresh-button", "n_clicks")]
)
def refresh_data(n_clicks):
    """Refresh all data manually."""
    if not n_clicks:
        return ""
    
    try:
        # Trigger a manual data update
        success = data_handler.update_data()
        
        if success:
            return create_alert(
                message="Data refreshed successfully!",
                type="success",
                is_dismissible=True
            )
        else:
            return create_alert(
                message="Error refreshing data",
                type="danger",
                is_dismissible=True
            )
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return create_alert(
            message=f"Error: {str(e)}",
            type="danger",
            is_dismissible=True
        )

@callback(
    Output("settings-store", "data"),
    [Input("apply-settings-button", "n_clicks")],
    [State("theme-selector", "value"),
     State("update-interval-selector", "value"),
     State("favorite-symbols", "value"),
     State("settings-store", "data")]
)
def update_settings(n_clicks, theme, update_interval, favorite_symbols, current_settings):
    """Update dashboard settings when the apply button is clicked."""
    if not n_clicks:
        return current_settings
    
    # Update settings
    new_settings = {
        'theme': theme,
        'update_interval': update_interval,
        'favorite_symbols': favorite_symbols
    }
    
    # Apply theme
    set_theme(theme)
    
    # Update interval component
    # Note: This doesn't actually work directly - we need a separate callback to update the interval
    
    return new_settings

@callback(
    Output("interval-component", "interval"),
    [Input("settings-store", "data")]
)
def update_interval(settings):
    """Update the interval component based on settings."""
    if settings and 'update_interval' in settings:
        # Convert seconds to milliseconds
        return settings['update_interval'] * 1000
    else:
        # Default to 60 seconds
        return 60 * 1000

@callback(
    [Output("market-section", "style"),
     Output("performance-section", "style"),
     Output("analysis-section", "style")],
    [Input("navigate-market-btn", "n_clicks"),
     Input("navigate-performance-btn", "n_clicks"),
     Input("navigate-analysis-btn", "n_clicks")]
)
def navigate_sections(market_clicks, performance_clicks, analysis_clicks):
    """Handle navigation between different dashboard sections."""
    # Default styles - all sections visible
    default_style = {"display": "block"}
    hidden_style = {"display": "none"}
    
    # Determine which button was clicked
    ctx_trigger = ctx.triggered_id if ctx and hasattr(ctx, 'triggered_id') else None
    
    if ctx_trigger == "navigate-market-btn":
        return default_style, hidden_style, hidden_style
    elif ctx_trigger == "navigate-performance-btn":
        return hidden_style, default_style, hidden_style
    elif ctx_trigger == "navigate-analysis-btn":
        return hidden_style, hidden_style, default_style
    else:
        # Default - show all sections
        return default_style, default_style, default_style

# Main entry point
if __name__ == "__main__":
    try:
        # Parse command line arguments for port and debug mode
        import argparse
        parser = argparse.ArgumentParser(description="Run the Instinct AI Trading Dashboard")
        parser.add_argument("--port", type=int, default=8050, help="Port to run the dashboard on")
        parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the dashboard on")
        parser.add_argument("--debug", action="store_true", help="Run in debug mode")
        args = parser.parse_args()
        
        # Start the dashboard
        logger.info(f"Starting dashboard on {args.host}:{args.port} (debug={args.debug})")
        app.run_server(host=args.host, debug=args.debug, port=args.port)
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}")
    finally:
        # Make sure to stop the market monitor when the app exits
        if hasattr(data_handler, 'market_monitor'):
            data_handler.market_monitor.stop()
        logger.info("Dashboard stopped") 