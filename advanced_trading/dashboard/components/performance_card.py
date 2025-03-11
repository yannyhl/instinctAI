"""
Performance Card Component

This module provides a card component for displaying performance metrics.
"""

import dash
from dash import html
import dash_bootstrap_components as dbc


def create_performance_card(title, id=None, icon=None):
    """
    Create a performance card.
    
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


def create_value_card(title, value, subtitle=None, change=None, change_pct=None, id=None, icon=None):
    """
    Create a card with a value and optional change indicator.
    
    Args:
        title: Card title
        value: Main value to display
        subtitle: Optional subtitle
        change: Optional numeric change (raw value)
        change_pct: Optional percentage change
        id: Component ID
        icon: Optional Bootstrap icon name
        
    Returns:
        Card component
    """
    # Get icon element if provided
    icon_element = html.I(className=f"bi bi-{icon} me-2") if icon else None
    
    # Create change element if provided
    change_element = None
    if change is not None or change_pct is not None:
        is_positive = (change or 0) >= 0
        
        # Format change text
        if change is not None and change_pct is not None:
            change_text = f"{'↑' if is_positive else '↓'} {abs(change):.2f} ({abs(change_pct):.2f}%)"
        elif change is not None:
            change_text = f"{'↑' if is_positive else '↓'} {abs(change):.2f}"
        else:
            change_text = f"{'↑' if is_positive else '↓'} {abs(change_pct):.2f}%"
        
        # Create span with appropriate color
        change_element = html.Span(
            change_text,
            className=f"text-{'success' if is_positive else 'danger'}"
        )
    
    header = [icon_element, title] if icon_element else title
    
    return dbc.Card([
        dbc.CardHeader(header),
        dbc.CardBody(id=id, children=[
            html.H3(str(value), className="card-title"),
            html.P(subtitle, className="card-text") if subtitle else None,
            change_element
        ])
    ], className="h-100 shadow-sm") 