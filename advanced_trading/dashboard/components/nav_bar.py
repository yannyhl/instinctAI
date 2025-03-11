"""
Navigation Bar Component

This module provides the navigation bar component for the dashboard.
"""

import dash
from dash import html
import dash_bootstrap_components as dbc

# Import dashboard modules
from dashboard.config import get_dashboard_config


def create_navbar() -> dbc.Navbar:
    """
    Create the navigation bar for the dashboard.
    
    Returns:
        dbc.Navbar: The navigation bar component.
    """
    brand = dbc.NavbarBrand(
        [
            html.I(className="fas fa-chart-line me-2"),
            "Instinct AI"
        ],
        href="#",
        className="ms-2"
    )
    
    # System nav item
    system_nav = dbc.NavItem(
        dbc.NavLink(
            [
                html.I(className="fas fa-server me-2"),
                "System"
            ],
            href="#",
            id="nav-system"
        )
    )
    
    # Portfolio nav item
    portfolio_nav = dbc.NavItem(
        dbc.NavLink(
            [
                html.I(className="fas fa-briefcase me-2"),
                "Portfolio"
            ],
            href="#",
            id="nav-portfolio"
        )
    )
    
    # Market nav item
    market_nav = dbc.NavItem(
        dbc.NavLink(
            [
                html.I(className="fas fa-chart-bar me-2"),
                "Market"
            ],
            href="#",
            id="nav-market"
        )
    )
    
    # Strategy nav item
    strategy_nav = dbc.NavItem(
        dbc.NavLink(
            [
                html.I(className="fas fa-chess me-2"),
                "Strategies"
            ],
            href="#",
            id="nav-strategy"
        )
    )
    
    # Strategy Monitoring nav item
    strategy_monitoring_nav = dbc.NavItem(
        dbc.NavLink(
            [
                html.I(className="fas fa-tachometer-alt me-2"),
                "Strategy Monitoring"
            ],
            href="#",
            id="nav-strategy-monitoring"
        )
    )
    
    # Performance Dashboard nav item
    performance_dashboard_nav = dbc.NavItem(
        dbc.NavLink(
            [
                html.I(className="fas fa-chart-area me-2"),
                "Performance"
            ],
            href="#",
            id="nav-performance-dashboard"
        )
    )
    
    # Nav items
    nav_items = dbc.Nav(
        [
            system_nav,
            portfolio_nav,
            market_nav,
            strategy_nav,
            strategy_monitoring_nav,
            performance_dashboard_nav
        ],
        navbar=True,
        className="me-auto"
    )
    
    # User menu dropdown
    user_menu = dbc.DropdownMenu(
        [
            dbc.DropdownMenuItem("Settings", href="#"),
            dbc.DropdownMenuItem("Profile", href="#"),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem("Logout", href="#")
        ],
        label=html.Span([
            html.I(className="fas fa-user me-2"),
            "User"
        ]),
        nav=True,
        align_end=True
    )
    
    # System status indicator
    system_status = html.Div(
        [
            html.Span("System: ", className="me-1"),
            html.Span(
                "ONLINE",
                className="badge bg-success"
            )
        ],
        className="d-flex align-items-center me-3"
    )
    
    # Right side items
    right_nav = dbc.Nav(
        [
            system_status,
            user_menu
        ],
        navbar=True,
        className="ms-auto"
    )
    
    # Assemble navbar
    navbar = dbc.Navbar(
        dbc.Container(
            [
                brand,
                dbc.NavbarToggler(id="navbar-toggler"),
                dbc.Collapse(
                    [nav_items, right_nav],
                    id="navbar-collapse",
                    navbar=True
                )
            ],
            fluid=True
        ),
        color="dark",
        dark=True,
        sticky="top"
    )
    
    return navbar 