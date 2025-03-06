"""
Navigation Bar Component

This module provides the navigation bar component for the dashboard.
"""

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

# Import dashboard modules
from dashboard.config import get_dashboard_config


def create_navbar(title="Instinct AI Trading Platform", theme="light"):
    """
    Create a navigation bar.
    
    Args:
        title: Dashboard title
        theme: UI theme ("light" or "dark")
        
    Returns:
        Navbar component
    """
    # Get views configuration
    config = get_dashboard_config()
    views_config = config.get("views", {})
    
    # Determine text and background color based on theme
    bg_color = "light" if theme == "light" else "dark"
    text_color = "dark" if theme == "light" else "light"
    
    # Create navigation items
    nav_items = []
    
    # System nav item
    if views_config.get("system", {}).get("enabled", True):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="fas fa-server mr-2"),
                        "System"
                    ],
                    id="nav-system",
                    href="#",
                    active=True
                )
            )
        )
    
    # Portfolio nav item
    if views_config.get("portfolio", {}).get("enabled", True):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="fas fa-chart-pie mr-2"),
                        "Portfolio"
                    ],
                    id="nav-portfolio",
                    href="#"
                )
            )
        )
    
    # Market nav item
    if views_config.get("market", {}).get("enabled", True):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="fas fa-chart-line mr-2"),
                        "Market"
                    ],
                    id="nav-market",
                    href="#"
                )
            )
        )
    
    # Strategy nav item
    if views_config.get("strategy", {}).get("enabled", True):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="fas fa-cogs mr-2"),
                        "Strategy"
                    ],
                    id="nav-strategy",
                    href="#"
                )
            )
        )
    
    # Create navbar
    navbar = dbc.Navbar(
        [
            # Brand
            dbc.Row(
                [
                    dbc.Col(
                        html.I(className="fas fa-robot mr-2 ml-2"),
                        width="auto"
                    ),
                    dbc.Col(
                        dbc.NavbarBrand(title, className="ml-2"),
                        width="auto"
                    ),
                ],
                align="center",
                no_gutters=True,
            ),
            
            # Environment indicator
            dbc.NavbarToggler(id="navbar-toggler"),
            
            # Navigation items
            dbc.Collapse(
                dbc.Nav(
                    nav_items,
                    className="ml-auto",
                    navbar=True
                ),
                id="navbar-collapse",
                navbar=True,
            ),
            
            # Right side items
            dbc.Row(
                [
                    dbc.Col(
                        html.Span(
                            [
                                html.I(className="fas fa-circle text-success mr-1"),
                                "Running"
                            ],
                            className=f"text-{text_color} mr-3"
                        ),
                        width="auto"
                    ),
                ],
                align="center",
                no_gutters=True,
                className="ml-auto mr-3"
            )
        ],
        color=bg_color,
        dark=(theme == "dark"),
        className="mb-5",
    )
    
    return navbar 