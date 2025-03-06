"""
Control Panel Component

This module provides a control panel component for the dashboard.
"""

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc


def create_control_panel(view_type="system"):
    """
    Create a control panel with actions specific to the view.
    
    Args:
        view_type: Type of view (system, portfolio, market, strategy)
        
    Returns:
        Control panel component
    """
    # Shared actions (refresh, settings)
    shared_actions = [
        dbc.Button([html.I(className="bi bi-arrow-clockwise me-2"), "Refresh"], 
                  color="primary", className="mb-2"),
        dbc.Button([html.I(className="bi bi-gear me-2"), "Settings"], 
                  color="secondary", className="mb-2 ms-2"),
    ]
    
    # View-specific actions
    specific_actions = []
    
    if view_type == "system":
        specific_actions = [
            html.Hr(),
            dbc.Button([html.I(className="bi bi-play-fill me-2"), "Start System"], 
                      id="start-system-button", color="success", className="me-2 mb-2"),
            dbc.Button([html.I(className="bi bi-stop-fill me-2"), "Stop System"], 
                      id="stop-system-button", color="danger", className="mb-2"),
            html.Hr(),
            dbc.Button([html.I(className="bi bi-download me-2"), "Export Logs"], 
                      id="export-logs-button", color="info", className="mb-2"),
        ]
    elif view_type == "portfolio":
        specific_actions = [
            html.Hr(),
            dbc.Button([html.I(className="bi bi-plus-lg me-2"), "Add Position"], 
                      id="add-position-button", color="success", className="me-2 mb-2"),
            dbc.Button([html.I(className="bi bi-dash-lg me-2"), "Close Position"], 
                      id="close-position-button", color="danger", className="mb-2"),
            html.Hr(),
            dbc.Button([html.I(className="bi bi-download me-2"), "Export Report"], 
                      id="export-portfolio-button", color="info", className="mb-2"),
        ]
    elif view_type == "market":
        specific_actions = [
            html.Hr(),
            dbc.Button([html.I(className="bi bi-plus-lg me-2"), "Add Symbol"], 
                      id="add-symbol-button", color="success", className="me-2 mb-2"),
            dbc.Button([html.I(className="bi bi-x-lg me-2"), "Remove Symbol"], 
                      id="remove-symbol-button", color="danger", className="mb-2"),
            html.Hr(),
            dbc.Button([html.I(className="bi bi-download me-2"), "Download Data"], 
                      id="download-data-button", color="info", className="mb-2"),
        ]
    elif view_type == "strategy":
        specific_actions = [
            html.Hr(),
            dbc.Button([html.I(className="bi bi-plus-lg me-2"), "Add Strategy"], 
                      id="add-strategy-button", color="success", className="me-2 mb-2"),
            dbc.Button([html.I(className="bi bi-power me-2"), "Toggle Active"], 
                      id="toggle-strategy-button", color="warning", className="mb-2"),
            html.Hr(),
            dbc.Button([html.I(className="bi bi-graph-up me-2"), "Backtest"], 
                      id="backtest-button", color="info", className="mb-2"),
        ]
    
    # Combine shared and specific actions
    all_actions = shared_actions + specific_actions
    
    # Create the control panel
    return dbc.Card([
        dbc.CardHeader("Controls"),
        dbc.CardBody([
            html.Div(all_actions, className="d-flex flex-wrap")
        ])
    ], className="h-100 shadow-sm") 