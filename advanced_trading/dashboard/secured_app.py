#!/usr/bin/env python3
"""
Instinct AI Secured Trading Dashboard
----------------------------------
Authenticated and optimized dashboard for monitoring market data and trading strategies.
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
import flask

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
from dashboard.auth_middleware import protect_dash_views, require_roles, get_current_username, is_admin

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the data handler
data_handler = get_market_data_handler()

# Initialize the app with cache control
server = flask.Flask(__name__)
app = dash.Dash(
    __name__,
    server=server,
    title="Instinct AI Trading Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True,
    update_title=None
)

# Configure server-side cache control
@server.after_request
def add_cache_control_headers(response):
    # Set cache control headers to avoid browser caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Create user profile component
def create_user_profile():
    username = get_current_username()
    admin_label = " (Admin)" if is_admin() else ""
    
    return html.Div([
        html.Div([
            html.Div(f"{username}{admin_label}", style={"font-weight": "bold"}),
            html.A("Logout", href="/logout", className="logout-link")
        ], className="user-profile-details"),
    ], className="user-profile")

# Define sidebar
def create_sidebar():
    return html.Div([
        # User profile
        create_user_profile(),
        
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
        
        # Admin panel (only visible to admins)
        html.Div([
            create_card(
                title="Admin Panel", 
                content=[
                    create_button(
                        text="User Management",
                        id="navigate-users-btn",
                        type="warning",
                        size="sm",
                        style={"margin-bottom": "10px", "width": "100%"}
                    ),
                    create_button(
                        text="API Key Management",
                        id="navigate-apikeys-btn",
                        type="warning",
                        size="sm",
                        style={"margin-bottom": "10px", "width": "100%"}
                    ),
                ]
            )
        ], id="admin-panel", style={"display": "none" if not is_admin() else "block"}),
        
        # Status section
        html.Div(id="refresh-status"),
    ])

# Define main content
def create_main_content():
    return [
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
        
        # User Management Section (admin only)
        html.Div([
            html.H2("User Management"),
            
            # User list
            create_card(
                title="User Accounts",
                content=html.Div(id="user-management-container")
            ),
            
            # Add user form
            create_card(
                title="Add New User",
                content=html.Div([
                    create_input_group(
                        label="Username",
                        input_component=dcc.Input(
                            id="new-username-input",
                            type="text",
                            placeholder="Enter username",
                            className="form-input"
                        ),
                        required=True
                    ),
                    create_input_group(
                        label="Password",
                        input_component=dcc.Input(
                            id="new-password-input",
                            type="password",
                            placeholder="Enter password",
                            className="form-input"
                        ),
                        required=True
                    ),
                    create_input_group(
                        label="Email",
                        input_component=dcc.Input(
                            id="new-email-input",
                            type="email",
                            placeholder="Enter email",
                            className="form-input"
                        )
                    ),
                    create_input_group(
                        label="Role",
                        input_component=dcc.Dropdown(
                            id="new-role-dropdown",
                            options=[
                                {"label": "User", "value": "user"},
                                {"label": "Admin", "value": "admin"}
                            ],
                            value="user",
                            clearable=False
                        )
                    ),
                    html.Div([
                        create_button(
                            text="Add User",
                            id="add-user-button",
                            type="primary",
                            style={"margin-top": "10px"}
                        ),
                        html.Div(id="add-user-result")
                    ], style={"margin-top": "20px"})
                ])
            )
        ], id="user-management-section", style={"display": "none"}),
        
        # API Key Management Section (admin only)
        html.Div([
            html.H2("API Key Management"),
            
            # API key list
            create_card(
                title="Exchange API Keys",
                content=html.Div(id="apikey-management-container")
            ),
            
            # Add API key form
            create_card(
                title="Add API Key",
                content=html.Div([
                    create_input_group(
                        label="Exchange",
                        input_component=dcc.Input(
                            id="new-exchange-input",
                            type="text",
                            placeholder="Enter exchange name (e.g., binance)",
                            className="form-input"
                        ),
                        required=True
                    ),
                    create_input_group(
                        label="API Key",
                        input_component=dcc.Input(
                            id="new-apikey-input",
                            type="text",
                            placeholder="Enter API key",
                            className="form-input"
                        ),
                        required=True
                    ),
                    create_input_group(
                        label="API Secret",
                        input_component=dcc.Input(
                            id="new-apisecret-input",
                            type="password",
                            placeholder="Enter API secret",
                            className="form-input"
                        ),
                        required=True
                    ),
                    create_input_group(
                        label="Description",
                        input_component=dcc.Input(
                            id="new-apidesc-input",
                            type="text",
                            placeholder="Enter description",
                            className="form-input"
                        )
                    ),
                    html.Div([
                        create_button(
                            text="Add API Key",
                            id="add-apikey-button",
                            type="primary",
                            style={"margin-top": "10px"}
                        ),
                        html.Div(id="add-apikey-result")
                    ], style={"margin-top": "20px"})
                ])
            )
        ], id="apikey-management-section", style={"display": "none"}),
        
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
        }),
        
        # Store for lazy loading status
        dcc.Store(id='loaded-sections', data={
            'market': False,
            'performance': False,
            'analysis': False,
            'user-management': False,
            'apikey-management': False
        })
    ]

# Define the main layout function
def serve_layout():
    return create_main_layout(
        title="Instinct AI Trading Dashboard",
        subtitle="Real-time market monitor and trading strategy insights",
        content=create_main_content(),
        sidebar=create_sidebar(),
        sidebar_width="250px",
        last_update_id="last-update-time"
    )

# Set the app layout
app.layout = serve_layout

# Apply authentication middleware
protect_dash_views(app)

# Define callbacks
@callback(
    Output("price-chart-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("symbol-selector", "value"),
     Input("timeframe-selector", "value"),
     Input("refresh-button", "n_clicks"),
     Input("settings-store", "data"),
     Input("loaded-sections", "data")]
)
def update_price_chart(n_intervals, symbol, timeframe, n_clicks, settings, loaded_sections):
    """Update the price chart based on the selected symbol and timeframe."""
    # Skip update if the market section is not visible
    if not loaded_sections.get('market', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
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
     Input("settings-store", "data"),
     Input("loaded-sections", "data")]
)
def update_market_summary_cards(n_intervals, n_clicks, settings, loaded_sections):
    """Update the market summary cards with latest market data."""
    # Skip update if the market section is not visible
    if not loaded_sections.get('market', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
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
     Input("refresh-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
def update_volume_profile_chart(n_intervals, symbol, timeframe, n_clicks, loaded_sections):
    """Update the volume profile chart based on the selected symbol and timeframe."""
    # Skip update if the market section is not visible
    if not loaded_sections.get('market', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
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
     Input("refresh-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
def update_regime_distribution_chart(n_intervals, symbol, n_clicks, loaded_sections):
    """Update the regime distribution chart for the selected symbol."""
    # Skip update if the market section is not visible
    if not loaded_sections.get('market', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
    # Get regime distribution data
    regime_data = data_handler.get_regime_distribution(symbol)
    
    # Create regime distribution chart
    return create_regime_distribution_chart(regime_data)

@callback(
    Output("correlation-matrix-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
def update_correlation_matrix(n_intervals, n_clicks, loaded_sections):
    """Update the correlation matrix heatmap."""
    # Skip update if the analysis section is not visible
    if not loaded_sections.get('analysis', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
    # Get correlation matrix data
    matrix_data = data_handler.get_correlation_matrix()
    
    # Create correlation matrix chart
    return create_correlation_matrix_chart(matrix_data)

@callback(
    Output("performance-metrics-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
def update_performance_metrics_table(n_intervals, n_clicks, loaded_sections):
    """Update the performance metrics table."""
    # Skip update if the performance section is not visible
    if not loaded_sections.get('performance', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
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
     Input("refresh-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
def update_performance_chart(n_intervals, n_clicks, loaded_sections):
    """Update the performance comparison chart."""
    # Skip update if the performance section is not visible
    if not loaded_sections.get('performance', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
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
     Input("refresh-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
def update_alerts_section(n_intervals, n_clicks, loaded_sections):
    """Update the alerts and events section."""
    # Skip update if the analysis section is not visible
    if not loaded_sections.get('analysis', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
    # Get alerts
    alerts = data_handler.get_alerts()
    
    # Create alert cards
    return create_alert_cards(alerts)

@callback(
    Output("user-management-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("add-user-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
@require_roles(['admin'])
def update_user_management(n_intervals, add_clicks, loaded_sections):
    """Update the user management table."""
    # Skip update if the user management section is not visible
    if not loaded_sections.get('user-management', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
    # Get auth manager
    from dashboard.auth import get_auth_manager
    auth_manager = get_auth_manager()
    
    # Get users
    users = auth_manager.list_users()
    
    # Create table
    table = dash_table.DataTable(
        id='users-table',
        columns=[
            {'name': 'Username', 'id': 'username'},
            {'name': 'Role', 'id': 'role'},
            {'name': 'Email', 'id': 'email'},
            {'name': 'Created', 'id': 'created_at'},
            {'name': 'Last Login', 'id': 'last_login'},
            {'name': 'Actions', 'id': 'actions', 'presentation': 'markdown'}
        ],
        data=[
            {
                'username': user['username'],
                'role': user['role'],
                'email': user.get('email', 'N/A'),
                'created_at': datetime.fromisoformat(user['created_at']).strftime('%Y-%m-%d %H:%M') if user.get('created_at') else 'N/A',
                'last_login': datetime.fromisoformat(user['last_login']).strftime('%Y-%m-%d %H:%M') if user.get('last_login') else 'Never',
                'actions': f"[Delete](delete:{user['username']})" if user['username'] != get_current_username() else "Cannot delete yourself"
            }
            for user in users
        ],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f1f1f1'},
        style_data_conditional=[
            {
                'if': {'column_id': 'actions'},
                'textAlign': 'center'
            },
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)'
            }
        ],
        markdown_options={'link_target': '_blank'}
    )
    
    return table

@callback(
    Output("apikey-management-container", "children"),
    [Input("interval-component", "n_intervals"),
     Input("add-apikey-button", "n_clicks"),
     Input("loaded-sections", "data")]
)
@require_roles(['admin'])
def update_apikey_management(n_intervals, add_clicks, loaded_sections):
    """Update the API key management table."""
    # Skip update if the API key management section is not visible
    if not loaded_sections.get('apikey-management', False) and ctx.triggered_id != 'loaded-sections':
        raise dash.exceptions.PreventUpdate
    
    # Get auth manager
    from dashboard.auth import get_auth_manager
    auth_manager = get_auth_manager()
    
    # Get API keys
    api_keys = auth_manager.list_api_keys()
    
    # Create table
    table = dash_table.DataTable(
        id='apikeys-table',
        columns=[
            {'name': 'Exchange', 'id': 'exchange'},
            {'name': 'API Key', 'id': 'api_key'},
            {'name': 'Description', 'id': 'description'},
            {'name': 'Added', 'id': 'added_at'},
            {'name': 'Last Used', 'id': 'last_used'},
            {'name': 'Actions', 'id': 'actions', 'presentation': 'markdown'}
        ],
        data=[
            {
                'exchange': exchange,
                'api_key': info['api_key'][:8] + '...',
                'description': info.get('description', 'N/A'),
                'added_at': datetime.fromisoformat(info['added_at']).strftime('%Y-%m-%d %H:%M') if info.get('added_at') else 'N/A',
                'last_used': datetime.fromisoformat(info['last_used']).strftime('%Y-%m-%d %H:%M') if info.get('last_used') else 'Never',
                'actions': f"[Delete](delete:{exchange})"
            }
            for exchange, info in api_keys.items()
        ],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f1f1f1'},
        style_data_conditional=[
            {
                'if': {'column_id': 'actions'},
                'textAlign': 'center'
            },
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)'
            }
        ],
        markdown_options={'link_target': '_blank'}
    )
    
    return table

@callback(
    Output("add-user-result", "children"),
    [Input("add-user-button", "n_clicks")],
    [State("new-username-input", "value"),
     State("new-password-input", "value"),
     State("new-email-input", "value"),
     State("new-role-dropdown", "value")]
)
@require_roles(['admin'])
def add_user(n_clicks, username, password, email, role):
    """Add a new user."""
    if n_clicks is None or n_clicks == 0:
        raise dash.exceptions.PreventUpdate
    
    if not username or not password:
        return create_alert("Username and password are required", type="danger")
    
    # Get auth manager
    from dashboard.auth import get_auth_manager
    auth_manager = get_auth_manager()
    
    # Add user
    success = auth_manager.add_user(
        username=username,
        password=password,
        role=role,
        email=email
    )
    
    if success:
        return create_alert(f"User '{username}' added successfully", type="success")
    else:
        return create_alert(f"Failed to add user '{username}'", type="danger")

@callback(
    Output("add-apikey-result", "children"),
    [Input("add-apikey-button", "n_clicks")],
    [State("new-exchange-input", "value"),
     State("new-apikey-input", "value"),
     State("new-apisecret-input", "value"),
     State("new-apidesc-input", "value")]
)
@require_roles(['admin'])
def add_apikey(n_clicks, exchange, api_key, api_secret, description):
    """Add a new API key."""
    if n_clicks is None or n_clicks == 0:
        raise dash.exceptions.PreventUpdate
    
    if not exchange or not api_key or not api_secret:
        return create_alert("Exchange, API key, and API secret are required", type="danger")
    
    # Get auth manager
    from dashboard.auth import get_auth_manager
    auth_manager = get_auth_manager()
    
    # Add API key
    success = auth_manager.add_api_key(
        exchange=exchange,
        api_key=api_key,
        api_secret=api_secret,
        description=description
    )
    
    if success:
        return create_alert(f"API key for '{exchange}' added successfully", type="success")
    else:
        return create_alert(f"Failed to add API key for '{exchange}'", type="danger")

@callback(
    Output("last-update-time", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_last_update_time(n_intervals, n_clicks):
    """Update the last update time indicator."""
    # Get the market monitor's last update time
    market_monitor = data_handler.market_monitor
    last_update = getattr(market_monitor, 'last_update_time', None)
    
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
     Output("analysis-section", "style"),
     Output("user-management-section", "style"),
     Output("apikey-management-section", "style"),
     Output("loaded-sections", "data")],
    [Input("navigate-market-btn", "n_clicks"),
     Input("navigate-performance-btn", "n_clicks"),
     Input("navigate-analysis-btn", "n_clicks"),
     Input("navigate-users-btn", "n_clicks"),
     Input("navigate-apikeys-btn", "n_clicks")],
    [State("loaded-sections", "data")]
)
def navigate_sections(market_clicks, performance_clicks, analysis_clicks, 
                     users_clicks, apikeys_clicks, loaded_sections):
    """Handle navigation between different dashboard sections."""
    # Default styles - all sections hidden
    default_style = {"display": "block"}
    hidden_style = {"display": "none"}
    
    # Default - all sections hidden
    styles = [hidden_style] * 5
    
    # Determine which button was clicked
    ctx_trigger = ctx.triggered_id if ctx and hasattr(ctx, 'triggered_id') else None
    
    # Update loaded status
    if ctx_trigger:
        if ctx_trigger == "navigate-market-btn":
            styles[0] = default_style
            loaded_sections['market'] = True
        elif ctx_trigger == "navigate-performance-btn":
            styles[1] = default_style
            loaded_sections['performance'] = True
        elif ctx_trigger == "navigate-analysis-btn":
            styles[2] = default_style
            loaded_sections['analysis'] = True
        elif ctx_trigger == "navigate-users-btn":
            styles[3] = default_style
            loaded_sections['user-management'] = True
        elif ctx_trigger == "navigate-apikeys-btn":
            styles[4] = default_style
            loaded_sections['apikey-management'] = True
    else:
        # Initial load - show market section
        styles[0] = default_style
        loaded_sections['market'] = True
    
    return styles[0], styles[1], styles[2], styles[3], styles[4], loaded_sections

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