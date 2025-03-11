"""
Status Card Component

This module provides a card component for displaying system status.
"""

import dash
from dash import html
import dash_bootstrap_components as dbc


def create_status_card(title, id=None, icon=None):
    """
    Create a status card.
    
    Args:
        title: Card title
        id: Component ID
        icon: Optional Bootstrap icon name
        
    Returns:
        Card component
    """
    # Get icon element if provided
    icon_element = html.I(className=f"bi bi-{icon} me-2") if icon else None
    
    header = [icon_element, title] if icon_element else title
    
    return dbc.Card([
        dbc.CardHeader(header),
        dbc.CardBody(id=id, children=[
            # Default content (will be replaced by callback)
            html.H3("Loading...", className="card-title"),
            html.P("Fetching data...", className="card-text"),
        ])
    ], className="h-100 shadow-sm")


def create_metric_card(title, value, subtitle=None, trend=None, id=None, icon=None):
    """
    Create a card with a metric and optional trend indicator.
    
    Args:
        title: Card title
        value: Main value to display
        subtitle: Optional subtitle
        trend: Optional trend indicator (positive or negative)
        id: Component ID
        icon: Optional Bootstrap icon name
        
    Returns:
        Card component
    """
    # Get icon element if provided
    icon_element = html.I(className=f"bi bi-{icon} me-2") if icon else None
    
    # Create trend element if provided
    trend_element = None
    if trend is not None:
        if trend > 0:
            trend_element = html.Span(f"↑ {trend:.1f}%", className="text-success")
        elif trend < 0:
            trend_element = html.Span(f"↓ {abs(trend):.1f}%", className="text-danger")
        else:
            trend_element = html.Span("No change", className="text-muted")
    
    header = [icon_element, title] if icon_element else title
    
    return dbc.Card([
        dbc.CardHeader(header),
        dbc.CardBody(id=id, children=[
            html.H3(str(value), className="card-title"),
            html.P(subtitle, className="card-text") if subtitle else None,
            trend_element
        ])
    ], className="h-100 shadow-sm") 