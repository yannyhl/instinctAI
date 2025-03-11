"""
Risk Monitoring Dashboard View

This module provides a comprehensive view for monitoring and analyzing risk metrics
across portfolio, positions, and market levels. It includes real-time risk monitoring,
alerts, and interactive visualizations for various risk dimensions.

The dashboard includes:
- Portfolio risk metrics (VaR, CVaR, drawdowns, concentration)
- Position risk analysis (exposure, correlation, stop levels)
- Market risk indicators (volatility, correlations, regime detection)
- Risk alerts and notifications for breaches of predefined limits
"""

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Union

# Import core components
from advanced_trading.core.observability import get_logger
from advanced_trading.dashboard.core import DashboardState, DashboardController

# Import risk components
from advanced_trading.risk.portfolio import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_var,
    calculate_cvar
)
from advanced_trading.risk.market import (
    calculate_market_volatility,
    calculate_correlation_matrix,
    identify_market_regime
)

# Initialize logger
logger = get_logger(__name__)


def create_risk_monitoring_view(state: DashboardState, controller: DashboardController) -> html.Div:
    """
    Create the risk monitoring dashboard view.
    
    Args:
        state: Current dashboard state
        controller: Dashboard controller for actions
        
    Returns:
        html.Div: The risk monitoring dashboard view
    """
    view_id = "risk-monitoring-view"
    
    # Header with date range selection and risk level indicators
    header = dbc.Row([
        dbc.Col([
            html.H3("Risk Monitoring Dashboard", className="mb-3")
        ], width=6),
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    html.Label("Date Range"),
                    dcc.DatePickerRange(
                        id="risk-date-range",
                        start_date=datetime.now() - timedelta(days=30),
                        end_date=datetime.now(),
                        display_format="YYYY-MM-DD",
                        className="w-100"
                    )
                ], width=8),
                dbc.Col([
                    html.Label("Presets"),
                    dbc.Select(
                        id="risk-date-range-preset",
                        options=[
                            {"label": "Last 7 Days", "value": "7d"},
                            {"label": "Last 30 Days", "value": "30d"},
                            {"label": "Last 90 Days", "value": "90d"},
                            {"label": "Year to Date", "value": "ytd"},
                            {"label": "Max", "value": "max"}
                        ],
                        value="30d",
                        className="w-100"
                    )
                ], width=4)
            ]),
        ], width=6),
    ], className="mb-4")
    
    # Risk summary cards - key metrics at a glance
    risk_summary_cards = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Portfolio VaR (95%)", className="card-subtitle mb-2 text-muted"),
                    html.H4(id="portfolio-var-value", children="--"),
                    html.P(id="portfolio-var-change", children="--", className="text-muted")
                ])
            ], className="h-100")
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Current Drawdown", className="card-subtitle mb-2 text-muted"),
                    html.H4(id="current-drawdown-value", children="--"),
                    html.P(id="max-drawdown-value", children="--", className="text-muted")
                ])
            ], className="h-100")
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Risk Concentration", className="card-subtitle mb-2 text-muted"),
                    html.H4(id="risk-concentration-value", children="--"),
                    html.P(id="risk-concentration-top", children="--", className="text-muted")
                ])
            ], className="h-100")
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Market Regime", className="card-subtitle mb-2 text-muted"),
                    html.H4(id="market-regime-value", children="--"),
                    html.P(id="market-volatility-value", children="--", className="text-muted")
                ])
            ], className="h-100")
        ], width=3)
    ], className="mb-4")
    
    # Active risk alerts
    risk_alerts = dbc.Card([
        dbc.CardHeader(html.H5("Active Risk Alerts")),
        dbc.CardBody([
            html.Div(id="risk-alerts-content", className="risk-alerts-container")
        ])
    ], className="mb-4")
    
    # Portfolio risk section
    portfolio_risk_section = dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H5("Portfolio Risk Analysis"), width=8),
                dbc.Col(
                    dbc.Select(
                        id="portfolio-risk-view-selector",
                        options=[
                            {"label": "Risk Metrics", "value": "metrics"},
                            {"label": "Risk Allocation", "value": "allocation"},
                            {"label": "Drawdown Analysis", "value": "drawdown"},
                            {"label": "Correlation", "value": "correlation"}
                        ],
                        value="metrics",
                        className="w-100"
                    ),
                    width=4
                )
            ])
        ]),
        dbc.CardBody([
            html.Div(id="portfolio-risk-content")
        ])
    ], className="mb-4")
    
    # Position risk section
    position_risk_section = dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H5("Position Risk Analysis"), width=8),
                dbc.Col(
                    dbc.Select(
                        id="position-risk-view-selector",
                        options=[
                            {"label": "Risk Exposure", "value": "exposure"},
                            {"label": "Stop Levels", "value": "stops"},
                            {"label": "Position Sizing", "value": "sizing"}
                        ],
                        value="exposure",
                        className="w-100"
                    ),
                    width=4
                )
            ])
        ]),
        dbc.CardBody([
            html.Div(id="position-risk-content")
        ])
    ], className="mb-4")
    
    # Market risk section
    market_risk_section = dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H5("Market Risk Analysis"), width=8),
                dbc.Col(
                    dbc.Select(
                        id="market-risk-view-selector",
                        options=[
                            {"label": "Volatility Analysis", "value": "volatility"},
                            {"label": "Correlation Analysis", "value": "correlation"},
                            {"label": "Regime Detection", "value": "regime"}
                        ],
                        value="volatility",
                        className="w-100"
                    ),
                    width=4
                )
            ])
        ]),
        dbc.CardBody([
            html.Div(id="market-risk-content")
        ])
    ], className="mb-4")
    
    # Risk settings and configuration
    risk_settings = dbc.Card([
        dbc.CardHeader(html.H5("Risk Configuration")),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("VaR Confidence Level"),
                    dbc.Select(
                        id="var-confidence-level",
                        options=[
                            {"label": "90%", "value": "0.9"},
                            {"label": "95%", "value": "0.95"},
                            {"label": "99%", "value": "0.99"}
                        ],
                        value="0.95",
                        className="w-100 mb-3"
                    )
                ], width=3),
                dbc.Col([
                    html.Label("VaR Calculation Method"),
                    dbc.Select(
                        id="var-calculation-method",
                        options=[
                            {"label": "Historical", "value": "historical"},
                            {"label": "Parametric", "value": "parametric"},
                            {"label": "Monte Carlo", "value": "monte_carlo"}
                        ],
                        value="historical",
                        className="w-100 mb-3"
                    )
                ], width=3),
                dbc.Col([
                    html.Label("Risk Thresholds"),
                    dbc.Button("Configure Risk Limits", id="configure-risk-limits-btn", color="primary")
                ], width=3),
                dbc.Col([
                    html.Label("Alert Configuration"),
                    dbc.Button("Configure Alerts", id="configure-alerts-btn", color="primary")
                ], width=3)
            ])
        ])
    ], className="mb-4")
    
    # Main dashboard content
    main_content = html.Div([
        risk_summary_cards,
        risk_alerts,
        portfolio_risk_section,
        position_risk_section,
        market_risk_section,
        risk_settings
    ], id="risk-dashboard-content")
    
    # Store for data
    stores = [
        dcc.Store(id="risk-data-store"),
        dcc.Store(id="risk-alerts-store"),
        dcc.Store(id="portfolio-risk-data-store"),
        dcc.Store(id="position-risk-data-store"),
        dcc.Store(id="market-risk-data-store")
    ]
    
    # Assemble the view
    view = html.Div([
        html.Div(stores),
        header,
        main_content
    ], id=view_id)
    
    return view


# ---------- Callback Functions ---------- #

@callback(
    Output("risk-date-range", "start_date"),
    Output("risk-date-range", "end_date"),
    Input("risk-date-range-preset", "value")
)
def update_date_range(preset: str) -> Tuple[datetime, datetime]:
    """
    Update the date range based on the selected preset.
    
    Args:
        preset: The selected date range preset
        
    Returns:
        Tuple containing start_date and end_date
    """
    end_date = datetime.now()
    
    if preset == "7d":
        start_date = end_date - timedelta(days=7)
    elif preset == "30d":
        start_date = end_date - timedelta(days=30)
    elif preset == "90d":
        start_date = end_date - timedelta(days=90)
    elif preset == "ytd":
        start_date = datetime(end_date.year, 1, 1)
    elif preset == "max":
        # Use a reasonable default for max history
        start_date = end_date - timedelta(days=365 * 3)  # 3 years
    else:
        # Default to 30 days
        start_date = end_date - timedelta(days=30)
    
    logger.info(f"Updating risk date range: {start_date.date()} to {end_date.date()}")
    return start_date, end_date


@callback(
    Output("risk-data-store", "data"),
    Input("risk-date-range", "start_date"),
    Input("risk-date-range", "end_date")
)
def update_risk_data(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Update risk data based on selected date range.
    
    Args:
        start_date: Start date for risk data
        end_date: End date for risk data
        
    Returns:
        Dictionary containing risk data
    """
    if start_date is None or end_date is None:
        logger.warning("Missing start or end date for risk data")
        return {}
    
    # Convert string dates to datetime objects
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.split('T')[0])
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date.split('T')[0])
    
    logger.info(f"Fetching risk data from {start_date.date()} to {end_date.date()}")
    
    # TODO: Replace with actual data fetch from the risk service
    # For now, generate sample data for demonstration
    return generate_sample_risk_data(start_date, end_date)


@callback(
    Output("risk-alerts-store", "data"),
    Input("risk-data-store", "data")
)
def update_risk_alerts(risk_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update risk alerts based on current risk data and thresholds.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        Dictionary containing risk alerts
    """
    if not risk_data:
        logger.warning("No risk data available for alert generation")
        return {"alerts": []}
    
    # TODO: Replace with actual alert generation using defined thresholds
    # For now, generate sample alerts
    return generate_sample_risk_alerts(risk_data)


@callback(
    Output("portfolio-var-value", "children"),
    Output("portfolio-var-change", "children"),
    Output("portfolio-var-change", "className"),
    Input("risk-data-store", "data"),
    Input("var-confidence-level", "value"),
    Input("var-calculation-method", "value")
)
def update_var_display(
    risk_data: Dict[str, Any],
    confidence_level: str,
    calculation_method: str
) -> Tuple[str, str, str]:
    """
    Update the Value at Risk (VaR) display with current risk data.
    
    Args:
        risk_data: Current risk data
        confidence_level: VaR confidence level
        calculation_method: VaR calculation method
        
    Returns:
        Tuple containing VaR value, change text, and change class
    """
    if not risk_data or "var" not in risk_data:
        return "N/A", "No data available", "text-muted"
    
    # Get VaR value based on confidence level and method
    confidence_level = float(confidence_level)
    var_key = f"var_{int(confidence_level * 100)}_{calculation_method}"
    
    if var_key not in risk_data["var"]:
        var_value = risk_data["var"].get("var_95_historical", 0.0)
    else:
        var_value = risk_data["var"][var_key]
    
    # Format VaR as percentage of portfolio value
    var_pct = var_value * 100
    var_display = f"{var_pct:.2f}%"
    
    # Calculate change from previous period
    if "previous_var" in risk_data and var_key in risk_data["previous_var"]:
        prev_var = risk_data["previous_var"][var_key]
        var_change = var_value - prev_var
        var_change_pct = (var_change / prev_var) * 100 if prev_var != 0 else 0
        
        # Higher VaR is worse (more risk)
        if var_change > 0:
            change_text = f"↑ {var_change_pct:.1f}% from previous"
            change_class = "text-danger"
        elif var_change < 0:
            change_text = f"↓ {abs(var_change_pct):.1f}% from previous"
            change_class = "text-success"
        else:
            change_text = "No change from previous"
            change_class = "text-muted"
    else:
        change_text = "No previous data available"
        change_class = "text-muted"
    
    return var_display, change_text, change_class


@callback(
    Output("current-drawdown-value", "children"),
    Output("max-drawdown-value", "children"),
    Input("risk-data-store", "data")
)
def update_drawdown_display(risk_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Update the current and maximum drawdown display.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        Tuple containing current drawdown and max drawdown text
    """
    if not risk_data or "drawdown" not in risk_data:
        return "N/A", "Max: N/A"
    
    current_dd = risk_data["drawdown"].get("current", 0.0)
    max_dd = risk_data["drawdown"].get("max", 0.0)
    
    current_dd_pct = current_dd * 100
    max_dd_pct = max_dd * 100
    
    current_dd_display = f"{current_dd_pct:.2f}%"
    max_dd_display = f"Max: {max_dd_pct:.2f}%"
    
    return current_dd_display, max_dd_display


@callback(
    Output("risk-concentration-value", "children"),
    Output("risk-concentration-top", "children"),
    Input("risk-data-store", "data")
)
def update_concentration_display(risk_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Update the risk concentration display.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        Tuple containing concentration value and top concentration text
    """
    if not risk_data or "concentration" not in risk_data:
        return "N/A", "No data available"
    
    concentration = risk_data["concentration"].get("value", 0.0)
    top_exposure = risk_data["concentration"].get("top_exposure", None)
    
    concentration_display = f"{concentration:.2f}"
    
    if top_exposure:
        top_name = top_exposure.get("name", "Unknown")
        top_pct = top_exposure.get("percentage", 0.0) * 100
        top_text = f"Top: {top_name} ({top_pct:.1f}%)"
    else:
        top_text = "No significant concentration"
    
    return concentration_display, top_text


@callback(
    Output("market-regime-value", "children"),
    Output("market-volatility-value", "children"),
    Input("risk-data-store", "data")
)
def update_market_regime_display(risk_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Update the market regime and volatility display.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        Tuple containing market regime and volatility text
    """
    if not risk_data or "market" not in risk_data:
        return "Unknown", "Vol: N/A"
    
    regime = risk_data["market"].get("regime", "Normal")
    volatility = risk_data["market"].get("volatility", 0.0)
    
    volatility_pct = volatility * 100
    volatility_display = f"Vol: {volatility_pct:.2f}%"
    
    return regime, volatility_display


@callback(
    Output("portfolio-risk-content", "children"),
    Input("portfolio-risk-view-selector", "value"),
    Input("risk-data-store", "data")
)
def update_portfolio_risk_content(view_type: str, risk_data: Dict[str, Any]) -> html.Div:
    """
    Update the portfolio risk content based on the selected view type.
    
    Args:
        view_type: Selected view type (metrics, allocation, drawdown, correlation)
        risk_data: Current risk data
        
    Returns:
        html.Div: The updated portfolio risk content
    """
    if not risk_data:
        return html.Div("No risk data available", className="text-center p-5")
    
    if view_type == "metrics":
        return create_portfolio_risk_metrics(risk_data)
    elif view_type == "allocation":
        return create_portfolio_risk_allocation(risk_data)
    elif view_type == "drawdown":
        return create_portfolio_drawdown_analysis(risk_data)
    elif view_type == "correlation":
        return create_portfolio_correlation_analysis(risk_data)
    else:
        return html.Div(f"Unknown view type: {view_type}", className="text-center p-5")


def create_portfolio_risk_metrics(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the portfolio risk metrics view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The portfolio risk metrics view
    """
    # Create sample data for risk metrics table
    metrics_data = [
        {"Metric": "Value at Risk (95%)", "Value": f"{risk_data['var']['var_95_historical']*100:.2f}%", "Description": "Maximum expected loss at 95% confidence level"},
        {"Metric": "Conditional VaR (95%)", "Value": f"{risk_data['var']['var_95_historical']*1.2*100:.2f}%", "Description": "Expected loss if VaR threshold is exceeded"},
        {"Metric": "Current Drawdown", "Value": f"{risk_data['drawdown']['current']*100:.2f}%", "Description": "Current drawdown from peak portfolio value"},
        {"Metric": "Maximum Drawdown", "Value": f"{risk_data['drawdown']['max']*100:.2f}%", "Description": "Largest historical drawdown"},
        {"Metric": "Concentration Ratio", "Value": f"{risk_data['concentration']['value']:.2f}", "Description": "Measure of portfolio concentration risk"},
        {"Metric": "Beta", "Value": f"{np.random.uniform(0.8, 1.2):.2f}", "Description": "Portfolio beta relative to market"}
    ]
    
    # Create risk metrics table
    metrics_table = html.Div([
        dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Risk Metric"), 
                    html.Th("Value"), 
                    html.Th("Description")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(metric["Metric"]),
                    html.Td(metric["Value"]),
                    html.Td(metric["Description"])
                ]) for metric in metrics_data
            ])
        ], bordered=True, hover=True, responsive=True, striped=True)
    ])
    
    # Create risk limits chart comparing current values to limits
    limits_data = {
        "metrics": ["VaR", "CVaR", "Drawdown", "Concentration", "Single Position"],
        "current": [
            risk_data["var"]["var_95_historical"],
            risk_data["var"]["var_95_historical"] * 1.2,
            risk_data["drawdown"]["current"],
            risk_data["concentration"]["value"] / 10,  # Scaled for visualization
            risk_data["concentration"]["top_exposure"]["percentage"]
        ],
        "limits": [0.025, 0.03, 0.15, 0.3, 0.35]  # Sample risk limits
    }
    
    # Calculate utilization percentages
    utilization = [min(100 * (c / l), 100) for c, l in zip(limits_data["current"], limits_data["limits"])]
    
    # Create limit utilization chart
    limits_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                x=limits_data["metrics"],
                y=utilization,
                text=[f"{u:.1f}%" for u in utilization],
                textposition="auto",
                marker_color=[
                    "green" if u < 50 else ("orange" if u < 80 else "red") 
                    for u in utilization
                ]
            )
        ]).update_layout(
            title="Risk Limit Utilization",
            yaxis_title="Utilization (%)",
            yaxis_range=[0, 100],
            showlegend=False
        )
    )
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(metrics_table, width=12, className="mb-4"),
            dbc.Col(limits_chart, width=12)
        ])
    ])


def create_portfolio_risk_allocation(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the portfolio risk allocation view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The portfolio risk allocation view
    """
    # Generate sample data for risk allocation
    assets = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD", "DOT-USD"]
    
    # Value allocation
    value_allocation = {
        "Asset": assets,
        "Allocation": [
            np.random.uniform(0.15, 0.4),
            np.random.uniform(0.1, 0.3),
            np.random.uniform(0.05, 0.15),
            np.random.uniform(0.05, 0.15),
            np.random.uniform(0.03, 0.1),
            np.random.uniform(0.03, 0.1)
        ]
    }
    
    # Normalize to 100%
    total = sum(value_allocation["Allocation"])
    value_allocation["Allocation"] = [a / total for a in value_allocation["Allocation"]]
    
    # Risk allocation (might be different from value allocation)
    risk_contribution = {
        "Asset": assets,
        "Contribution": [
            np.random.uniform(0.2, 0.5),
            np.random.uniform(0.15, 0.3),
            np.random.uniform(0.05, 0.2),
            np.random.uniform(0.05, 0.15),
            np.random.uniform(0.03, 0.1),
            np.random.uniform(0.03, 0.1)
        ]
    }
    
    # Normalize to 100%
    total = sum(risk_contribution["Contribution"])
    risk_contribution["Contribution"] = [c / total for c in risk_contribution["Contribution"]]
    
    # Create value allocation pie chart
    value_pie = dcc.Graph(
        figure=go.Figure(data=[
            go.Pie(
                labels=value_allocation["Asset"],
                values=value_allocation["Allocation"],
                textinfo="label+percent",
                hole=0.3
            )
        ]).update_layout(
            title="Portfolio Value Allocation",
            showlegend=True
        )
    )
    
    # Create risk contribution pie chart
    risk_pie = dcc.Graph(
        figure=go.Figure(data=[
            go.Pie(
                labels=risk_contribution["Asset"],
                values=risk_contribution["Contribution"],
                textinfo="label+percent",
                hole=0.3
            )
        ]).update_layout(
            title="Risk Contribution",
            showlegend=True
        )
    )
    
    # Create comparison bar chart
    comparison_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                name="Value Allocation",
                x=value_allocation["Asset"],
                y=[a * 100 for a in value_allocation["Allocation"]],
                offsetgroup=0
            ),
            go.Bar(
                name="Risk Contribution",
                x=risk_contribution["Asset"],
                y=[c * 100 for c in risk_contribution["Contribution"]],
                offsetgroup=1
            )
        ]).update_layout(
            title="Value vs. Risk Allocation",
            xaxis_title="Asset",
            yaxis_title="Percentage (%)",
            barmode="group",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )
    )
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(value_pie, md=6),
            dbc.Col(risk_pie, md=6)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(comparison_chart, width=12)
        ])
    ])


def create_portfolio_drawdown_analysis(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the portfolio drawdown analysis view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The portfolio drawdown analysis view
    """
    # Generate sample data for drawdown analysis
    # In a real implementation, this would come from the risk_data
    
    # Generate dates for the last 90 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    
    # Sample portfolio values
    np.random.seed(42)  # For reproducibility
    base_value = 1000000
    daily_returns = np.random.normal(0.0005, 0.015, len(dates))
    portfolio_values = [base_value]
    
    for ret in daily_returns:
        portfolio_values.append(portfolio_values[-1] * (1 + ret))
    
    portfolio_values = portfolio_values[1:]  # Remove the initial value
    
    # Calculate drawdowns
    cumulative_max = np.maximum.accumulate(portfolio_values)
    drawdowns = (portfolio_values - cumulative_max) / cumulative_max
    
    # Create portfolio value chart with drawdown overlay
    portfolio_chart = dcc.Graph(
        figure=go.Figure().add_trace(
            go.Scatter(
                x=dates,
                y=portfolio_values,
                name="Portfolio Value",
                line=dict(color="blue")
            )
        ).add_trace(
            go.Scatter(
                x=dates,
                y=cumulative_max,
                name="High Water Mark",
                line=dict(color="green", dash="dash")
            )
        ).update_layout(
            title="Portfolio Value and High Water Mark",
            xaxis_title="Date",
            yaxis_title="Value ($)",
            legend=dict(orientation="h")
        )
    )
    
    # Create drawdown chart
    drawdown_chart = dcc.Graph(
        figure=go.Figure().add_trace(
            go.Scatter(
                x=dates,
                y=drawdowns,
                name="Drawdown",
                fill="tozeroy",
                line=dict(color="red")
            )
        ).add_trace(
            go.Scatter(
                x=dates,
                y=[0] * len(dates),
                line=dict(color="gray", width=1),
                showlegend=False
            )
        ).update_layout(
            title="Portfolio Drawdown",
            xaxis_title="Date",
            yaxis_title="Drawdown (%)",
            yaxis_tickformat=".1%",
            yaxis_range=[min(drawdowns) * 1.1, 0.01],  # Add some padding
            showlegend=False
        )
    )
    
    # Generate data for drawdown table
    # Find drawdown periods (consecutive negative drawdowns)
    drawdown_periods = []
    current_period = {"start": None, "end": None, "max_drawdown": 0, "recovery": None}
    in_drawdown = False
    
    for i, (date, dd) in enumerate(zip(dates, drawdowns)):
        if not in_drawdown and dd < 0:
            # Start of new drawdown period
            in_drawdown = True
            current_period = {
                "start": date,
                "end": None,
                "max_drawdown": dd,
                "recovery": None
            }
        elif in_drawdown:
            if dd < current_period["max_drawdown"]:
                # New max drawdown in current period
                current_period["max_drawdown"] = dd
                current_period["end"] = date
            
            if dd >= 0:
                # Recovered from drawdown
                in_drawdown = False
                current_period["recovery"] = date
                if current_period["end"] is None:
                    current_period["end"] = current_period["start"]
                drawdown_periods.append(current_period)
    
    # If still in drawdown at the end
    if in_drawdown:
        if current_period["end"] is None:
            current_period["end"] = dates[-1]
        current_period["recovery"] = None
        drawdown_periods.append(current_period)
    
    # Sort drawdown periods by max drawdown
    drawdown_periods.sort(key=lambda x: x["max_drawdown"])
    
    # Create drawdown table
    drawdown_table = html.Div([
        html.H5("Top Drawdown Periods", className="mb-3"),
        dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Start Date"),
                    html.Th("End Date"),
                    html.Th("Max Drawdown"),
                    html.Th("Duration"),
                    html.Th("Recovery Date"),
                    html.Th("Recovery Time")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(period["start"].strftime("%Y-%m-%d")),
                    html.Td(period["end"].strftime("%Y-%m-%d")),
                    html.Td(f"{period['max_drawdown']:.2%}"),
                    html.Td(f"{(period['end'] - period['start']).days} days"),
                    html.Td(period["recovery"].strftime("%Y-%m-%d") if period["recovery"] else "Not recovered"),
                    html.Td(f"{(period['recovery'] - period['end']).days} days" if period["recovery"] else "N/A")
                ]) for period in drawdown_periods[:5]  # Show top 5 drawdowns
            ])
        ], bordered=True, hover=True, responsive=True, striped=True)
    ])
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(portfolio_chart, width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(drawdown_chart, width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(drawdown_table, width=12)
        ])
    ])


def create_portfolio_correlation_analysis(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the portfolio correlation analysis view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The portfolio correlation analysis view
    """
    # Generate sample data for correlation analysis
    assets = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD", "DOT-USD", "Market"]
    
    # Generate a correlation matrix
    np.random.seed(42)  # For reproducibility
    
    # Create a realistic correlation matrix
    # Crypto assets tend to have higher correlations
    corr_matrix = np.array([
        [1.00, 0.75, 0.65, 0.60, 0.55, 0.70, 0.65],  # BTC
        [0.75, 1.00, 0.80, 0.70, 0.75, 0.65, 0.60],  # ETH
        [0.65, 0.80, 1.00, 0.75, 0.70, 0.60, 0.50],  # SOL
        [0.60, 0.70, 0.75, 1.00, 0.80, 0.65, 0.45],  # AVAX
        [0.55, 0.75, 0.70, 0.80, 1.00, 0.70, 0.55],  # MATIC
        [0.70, 0.65, 0.60, 0.65, 0.70, 1.00, 0.60],  # DOT
        [0.65, 0.60, 0.50, 0.45, 0.55, 0.60, 1.00]   # Market
    ])
    
    # Add some random noise to make it less perfect
    noise = np.random.uniform(-0.1, 0.1, corr_matrix.shape)
    # Make sure the noise preserves symmetry and diagonal of 1s
    noise = (noise + noise.T) / 2
    np.fill_diagonal(noise, 0)
    
    corr_matrix = corr_matrix + noise
    # Ensure correlations stay in [-1, 1] range
    corr_matrix = np.clip(corr_matrix, -1, 1)
    # Make sure diagonal is exactly 1
    np.fill_diagonal(corr_matrix, 1)
    
    # Create correlation heatmap
    corr_heatmap = dcc.Graph(
        figure=go.Figure(data=go.Heatmap(
            z=corr_matrix,
            x=assets,
            y=assets,
            colorscale="RdBu_r",
            zmin=-1,
            zmax=1,
            text=[[f"{val:.2f}" for val in row] for row in corr_matrix],
            texttemplate="%{text}",
            textfont={"size": 10}
        )).update_layout(
            title="Asset Correlation Matrix",
            width=700,
            height=600
        )
    )
    
    # Calculate average correlations for each asset
    avg_corrs = [
        {
            "Asset": asset,
            "Avg. Correlation": sum(corr_matrix[i]) / (len(assets) - 1)
        } for i, asset in enumerate(assets)
    ]
    
    # Sort by average correlation
    avg_corrs.sort(key=lambda x: x["Avg. Correlation"], reverse=True)
    
    # Create average correlation chart
    avg_corr_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                x=[x["Asset"] for x in avg_corrs],
                y=[x["Avg. Correlation"] for x in avg_corrs],
                text=[f"{x['Avg. Correlation']:.2f}" for x in avg_corrs],
                textposition="auto",
                marker_color="blue"
            )
        ]).update_layout(
            title="Average Correlation by Asset",
            xaxis_title="Asset",
            yaxis_title="Average Correlation"
        )
    )
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(html.Div([
                html.H5("Correlation Analysis", className="mb-3"),
                html.P("""
                    Asset correlations provide insights into portfolio diversification 
                    and systematic risk exposure. Lower correlations generally indicate 
                    better diversification.
                """),
                html.P("""
                    In the heatmap, values closer to 1 (red) indicate strong positive 
                    correlation, values closer to -1 (blue) indicate strong negative 
                    correlation, and values near 0 (white) indicate little correlation.
                """)
            ]), width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(corr_heatmap, lg=7),
            dbc.Col(avg_corr_chart, lg=5)
        ])
    ])


@callback(
    Output("position-risk-content", "children"),
    Input("position-risk-view-selector", "value"),
    Input("risk-data-store", "data")
)
def update_position_risk_content(view_type: str, risk_data: Dict[str, Any]) -> html.Div:
    """
    Update the position risk content based on the selected view type.
    
    Args:
        view_type: Selected view type (exposure, stops, sizing)
        risk_data: Current risk data
        
    Returns:
        html.Div: The updated position risk content
    """
    if not risk_data:
        return html.Div("No risk data available", className="text-center p-5")
    
    if view_type == "exposure":
        return create_position_risk_exposure(risk_data)
    elif view_type == "stops":
        return create_position_stop_levels(risk_data)
    elif view_type == "sizing":
        return create_position_sizing_analysis(risk_data)
    else:
        return html.Div(f"Unknown view type: {view_type}", className="text-center p-5")


def create_position_risk_exposure(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the position risk exposure view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The position risk exposure view
    """
    # Generate sample position data
    positions = [
        {"asset": "BTC-USD", "size": 2.5, "entry_price": 35000, "current_price": 36500, "pnl": 3750, "risk": 0.35},
        {"asset": "ETH-USD", "size": 15, "entry_price": 2200, "current_price": 2150, "pnl": -750, "risk": 0.25},
        {"asset": "SOL-USD", "size": 150, "entry_price": 95, "current_price": 105, "pnl": 1500, "risk": 0.15},
        {"asset": "AVAX-USD", "size": 200, "entry_price": 28, "current_price": 27.5, "pnl": -100, "risk": 0.10},
        {"asset": "MATIC-USD", "size": 5000, "entry_price": 0.85, "current_price": 0.88, "pnl": 150, "risk": 0.08},
        {"asset": "DOT-USD", "size": 300, "entry_price": 6.5, "current_price": 6.2, "pnl": -90, "risk": 0.07}
    ]
    
    # Calculate position values and risk allocations
    total_value = sum(p["size"] * p["current_price"] for p in positions)
    total_risk = sum(p["risk"] for p in positions)
    
    for p in positions:
        p["value"] = p["size"] * p["current_price"]
        p["value_pct"] = p["value"] / total_value
        p["risk_pct"] = p["risk"] / total_risk
        p["pnl_pct"] = p["pnl"] / (p["size"] * p["entry_price"]) if p["size"] * p["entry_price"] != 0 else 0
    
    # Sort positions by risk allocation
    positions.sort(key=lambda x: x["risk"], reverse=True)
    
    # Create position table
    position_table = html.Div([
        dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Asset"),
                    html.Th("Size"),
                    html.Th("Entry Price"),
                    html.Th("Current Price"),
                    html.Th("Value"),
                    html.Th("P&L"),
                    html.Th("Risk Allocation")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(p["asset"]),
                    html.Td(f"{p['size']:.2f}"),
                    html.Td(f"${p['entry_price']:.2f}"),
                    html.Td(f"${p['current_price']:.2f}"),
                    html.Td(f"${p['value']:.2f}"),
                    html.Td([
                        f"${p['pnl']:.2f}",
                        html.Span(
                            f" ({p['pnl_pct']:.2%})",
                            className="text-success" if p["pnl"] >= 0 else "text-danger"
                        )
                    ]),
                    html.Td(f"{p['risk_pct']:.2%}")
                ]) for p in positions
            ])
        ], bordered=True, hover=True, responsive=True, striped=True)
    ])
    
    # Create risk allocation chart
    risk_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                name="Value Allocation",
                x=[p["asset"] for p in positions],
                y=[p["value_pct"] * 100 for p in positions],
                marker_color="blue",
                opacity=0.7
            ),
            go.Bar(
                name="Risk Allocation",
                x=[p["asset"] for p in positions],
                y=[p["risk_pct"] * 100 for p in positions],
                marker_color="red",
                opacity=0.7
            )
        ]).update_layout(
            title="Position Value vs. Risk Allocation",
            xaxis_title="Asset",
            yaxis_title="Percentage (%)",
            barmode="group",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )
    )
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(position_table, width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(risk_chart, width=12)
        ])
    ])


def create_position_stop_levels(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the position stop levels view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The position stop levels view
    """
    # Generate sample position data with stop levels
    positions = [
        {
            "asset": "BTC-USD", 
            "size": 2.5, 
            "entry_price": 35000, 
            "current_price": 36500,
            "stop_price": 33250,
            "stop_type": "Trailing",
            "stop_distance": 0.05,
            "risk_amount": 8125
        },
        {
            "asset": "ETH-USD", 
            "size": 15, 
            "entry_price": 2200, 
            "current_price": 2150,
            "stop_price": 2000,
            "stop_type": "Fixed",
            "stop_distance": 0.07,
            "risk_amount": 2250
        },
        {
            "asset": "SOL-USD", 
            "size": 150, 
            "entry_price": 95, 
            "current_price": 105,
            "stop_price": 90,
            "stop_type": "Trailing",
            "stop_distance": 0.14,
            "risk_amount": 2250
        },
        {
            "asset": "AVAX-USD", 
            "size": 200, 
            "entry_price": 28, 
            "current_price": 27.5,
            "stop_price": 25,
            "stop_type": "Fixed",
            "stop_distance": 0.09,
            "risk_amount": 500
        },
        {
            "asset": "MATIC-USD", 
            "size": 5000, 
            "entry_price": 0.85, 
            "current_price": 0.88,
            "stop_price": 0.75,
            "stop_type": "Fixed",
            "stop_distance": 0.15,
            "risk_amount": 650
        },
        {
            "asset": "DOT-USD", 
            "size": 300, 
            "entry_price": 6.5, 
            "current_price": 6.2,
            "stop_price": 5.8,
            "stop_type": "Trailing",
            "stop_distance": 0.06,
            "risk_amount": 120
        }
    ]
    
    # Calculate additional metrics
    for p in positions:
        p["stop_pct"] = (p["current_price"] - p["stop_price"]) / p["current_price"]
        p["position_value"] = p["size"] * p["current_price"]
        p["risk_pct"] = p["risk_amount"] / p["position_value"] if p["position_value"] != 0 else 0
    
    # Sort positions by risk amount
    positions.sort(key=lambda x: x["risk_amount"], reverse=True)
    
    # Create stop levels table
    stop_table = html.Div([
        dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Asset"),
                    html.Th("Current Price"),
                    html.Th("Stop Price"),
                    html.Th("Stop Type"),
                    html.Th("Stop Distance"),
                    html.Th("Risk Amount"),
                    html.Th("Risk %")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(p["asset"]),
                    html.Td(f"${p['current_price']:.2f}"),
                    html.Td(f"${p['stop_price']:.2f}"),
                    html.Td(p["stop_type"]),
                    html.Td(f"{p['stop_distance']:.2%}"),
                    html.Td(f"${p['risk_amount']:.2f}"),
                    html.Td(f"{p['risk_pct']:.2%}")
                ]) for p in positions
            ])
        ], bordered=True, hover=True, responsive=True, striped=True)
    ])
    
    # Create stop distance chart
    stop_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                x=[p["asset"] for p in positions],
                y=[p["stop_distance"] * 100 for p in positions],
                text=[f"{p['stop_distance']:.2%}" for p in positions],
                textposition="auto",
                marker_color=[
                    "green" if p["stop_distance"] < 0.05 else 
                    ("orange" if p["stop_distance"] < 0.1 else "red")
                    for p in positions
                ]
            )
        ]).update_layout(
            title="Stop Distance by Position",
            xaxis_title="Asset",
            yaxis_title="Stop Distance (%)",
            showlegend=False
        )
    )
    
    # Create risk amount chart
    risk_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Pie(
                labels=[p["asset"] for p in positions],
                values=[p["risk_amount"] for p in positions],
                textinfo="label+percent",
                hole=0.3
            )
        ]).update_layout(
            title="Risk Amount Distribution",
            showlegend=True
        )
    )
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(stop_table, width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(stop_chart, md=6),
            dbc.Col(risk_chart, md=6)
        ])
    ])


def create_position_sizing_analysis(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the position sizing analysis view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The position sizing analysis view
    """
    # Generate sample position sizing data
    assets = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD", "DOT-USD"]
    
    # Current position sizes
    current_sizes = [2.5, 15, 150, 200, 5000, 300]
    
    # Current prices
    prices = [36500, 2150, 105, 27.5, 0.88, 6.2]
    
    # Calculate position values
    position_values = [size * price for size, price in zip(current_sizes, prices)]
    
    # Calculate portfolio value
    portfolio_value = sum(position_values)
    
    # Calculate current allocation percentages
    current_allocations = [value / portfolio_value for value in position_values]
    
    # Sample target allocations
    target_allocations = [0.35, 0.25, 0.15, 0.1, 0.08, 0.07]
    
    # Calculate target position values
    target_values = [portfolio_value * alloc for alloc in target_allocations]
    
    # Calculate target position sizes
    target_sizes = [value / price for value, price in zip(target_values, prices)]
    
    # Calculate size adjustments needed
    adjustments = [target - current for target, current in zip(target_sizes, current_sizes)]
    adjustment_values = [adj * price for adj, price in zip(adjustments, prices)]
    
    # Create position sizing table
    sizing_data = []
    for i, asset in enumerate(assets):
        sizing_data.append({
            "Asset": asset,
            "Current Size": f"{current_sizes[i]:.2f}",
            "Current Value": f"${position_values[i]:.2f}",
            "Current Allocation": f"{current_allocations[i]:.2%}",
            "Target Allocation": f"{target_allocations[i]:.2%}",
            "Target Size": f"{target_sizes[i]:.2f}",
            "Adjustment": f"{adjustments[i]:.2f}",
            "Adjustment Value": f"${adjustment_values[i]:.2f}"
        })
    
    sizing_table = html.Div([
        dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Asset"),
                    html.Th("Current Size"),
                    html.Th("Current Value"),
                    html.Th("Current Allocation"),
                    html.Th("Target Allocation"),
                    html.Th("Target Size"),
                    html.Th("Adjustment"),
                    html.Th("Adjustment Value")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(data["Asset"]),
                    html.Td(data["Current Size"]),
                    html.Td(data["Current Value"]),
                    html.Td(data["Current Allocation"]),
                    html.Td(data["Target Allocation"]),
                    html.Td(data["Target Size"]),
                    html.Td(
                        data["Adjustment"],
                        className="text-success" if float(data["Adjustment"]) >= 0 else "text-danger"
                    ),
                    html.Td(
                        data["Adjustment Value"],
                        className="text-success" if float(data["Adjustment"]) >= 0 else "text-danger"
                    )
                ]) for data in sizing_data
            ])
        ], bordered=True, hover=True, responsive=True, striped=True)
    ])
    
    # Create allocation comparison chart
    allocation_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                name="Current Allocation",
                x=assets,
                y=[alloc * 100 for alloc in current_allocations],
                marker_color="blue",
                opacity=0.7
            ),
            go.Bar(
                name="Target Allocation",
                x=assets,
                y=[alloc * 100 for alloc in target_allocations],
                marker_color="green",
                opacity=0.7
            )
        ]).update_layout(
            title="Current vs. Target Allocation",
            xaxis_title="Asset",
            yaxis_title="Allocation (%)",
            barmode="group",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )
    )
    
    # Create adjustment chart
    adjustment_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                x=assets,
                y=adjustment_values,
                marker_color=["green" if adj >= 0 else "red" for adj in adjustments],
                text=[f"${val:.2f}" for val in adjustment_values],
                textposition="auto"
            )
        ]).update_layout(
            title="Required Position Adjustments",
            xaxis_title="Asset",
            yaxis_title="Adjustment Value ($)",
            showlegend=False
        )
    )
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(sizing_table, width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(allocation_chart, md=6),
            dbc.Col(adjustment_chart, md=6)
        ])
    ])


@callback(
    Output("market-risk-content", "children"),
    Input("market-risk-view-selector", "value"),
    Input("risk-data-store", "data")
)
def update_market_risk_content(view_type: str, risk_data: Dict[str, Any]) -> html.Div:
    """
    Update the market risk content based on the selected view type.
    
    Args:
        view_type: Selected view type (volatility, correlation, regime)
        risk_data: Current risk data
        
    Returns:
        html.Div: The updated market risk content
    """
    if not risk_data:
        return html.Div("No risk data available", className="text-center p-5")
    
    if view_type == "volatility":
        return create_market_volatility_analysis(risk_data)
    elif view_type == "correlation":
        return create_market_correlation_analysis(risk_data)
    elif view_type == "regime":
        return create_market_regime_analysis(risk_data)
    else:
        return html.Div(f"Unknown view type: {view_type}", className="text-center p-5")


def create_market_volatility_analysis(risk_data: Dict[str, Any]) -> html.Div:
    """
    Create the market volatility analysis view.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        html.Div: The market volatility analysis view
    """
    # Generate sample data for volatility analysis
    assets = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD", "DOT-USD", "Market"]
    
    # Generate dates for the last 90 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    
    # Generate volatility data
    np.random.seed(42)  # For reproducibility
    
    # Base volatility levels for each asset
    base_vols = {
        "BTC-USD": 0.03,
        "ETH-USD": 0.04,
        "SOL-USD": 0.06,
        "AVAX-USD": 0.055,
        "MATIC-USD": 0.05,
        "DOT-USD": 0.045,
        "Market": 0.025
    }
    
    # Generate volatility time series with some common patterns
    market_vol = []
    for i in range(len(dates)):
        # Create a market volatility pattern with some spikes
        if i < 30:
            # Normal period
            vol = base_vols["Market"] * (1 + 0.2 * np.sin(i / 10) + 0.1 * np.random.randn())
        elif 30 <= i < 45:
            # Volatility spike
            vol = base_vols["Market"] * (1.5 + 0.5 * np.sin((i - 30) / 5) + 0.15 * np.random.randn())
        elif 45 <= i < 60:
            # Declining volatility
            vol = base_vols["Market"] * (1.5 - 0.03 * (i - 45) + 0.1 * np.random.randn())
        else:
            # Back to normal with slight uptrend
            vol = base_vols["Market"] * (1 + 0.01 * (i - 60) + 0.2 * np.sin((i - 60) / 15) + 0.1 * np.random.randn())
        
        market_vol.append(max(0.01, vol))  # Ensure positive volatility
    
    # Generate asset-specific volatility with correlation to market
    asset_vols = {}
    for asset in assets:
        if asset == "Market":
            asset_vols[asset] = market_vol
        else:
            # Create correlated volatility series
            beta = np.random.uniform(0.8, 1.2)  # Volatility beta to market
            asset_specific = []
            for i, market_v in enumerate(market_vol):
                # Correlated with market but with asset-specific patterns
                vol = base_vols[asset] * (1 + beta * (market_v / base_vols["Market"] - 1) + 0.15 * np.random.randn())
                asset_specific.append(max(0.01, vol))  # Ensure positive volatility
            asset_vols[asset] = asset_specific
    
    # Create volatility time series chart
    vol_series_data = []
    for asset in assets:
        vol_series_data.append(
            go.Scatter(
                x=dates,
                y=[v * 100 for v in asset_vols[asset]],  # Convert to percentage
                name=asset,
                visible="legendonly" if asset != "Market" else True
            )
        )
    
    vol_series_chart = dcc.Graph(
        figure=go.Figure(data=vol_series_data).update_layout(
            title="Volatility Time Series",
            xaxis_title="Date",
            yaxis_title="Volatility (%)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )
    )
    
    # Calculate current volatility for each asset
    current_vols = {asset: asset_vols[asset][-1] for asset in assets}
    
    # Calculate historical average volatility
    avg_vols = {asset: np.mean(asset_vols[asset]) for asset in assets}
    
    # Calculate volatility ratio (current / average)
    vol_ratios = {asset: current_vols[asset] / avg_vols[asset] for asset in assets}
    
    # Create current volatility comparison chart
    vol_comparison_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                x=list(assets),
                y=[current_vols[asset] * 100 for asset in assets],
                name="Current Volatility",
                marker_color="blue"
            ),
            go.Bar(
                x=list(assets),
                y=[avg_vols[asset] * 100 for asset in assets],
                name="Historical Average",
                marker_color="gray"
            )
        ]).update_layout(
            title="Current vs. Historical Average Volatility",
            xaxis_title="Asset",
            yaxis_title="Volatility (%)",
            barmode="group",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )
    )
    
    # Create volatility ratio chart
    vol_ratio_chart = dcc.Graph(
        figure=go.Figure(data=[
            go.Bar(
                x=list(assets),
                y=[vol_ratios[asset] for asset in assets],
                text=[f"{vol_ratios[asset]:.2f}x" for asset in assets],
                textposition="auto",
                marker_color=[
                    "green" if vol_ratios[asset] < 0.9 else 
                    ("orange" if vol_ratios[asset] < 1.1 else "red")
                    for asset in assets
                ]
            )
        ]).update_layout(
            title="Volatility Ratio (Current / Historical Average)",
            xaxis_title="Asset",
            yaxis_title="Ratio",
            showlegend=False
        )
    )
    
    # Create volatility table
    vol_table_data = []
    for asset in assets:
        vol_table_data.append({
            "Asset": asset,
            "Current Volatility": f"{current_vols[asset]:.2%}",
            "Historical Average": f"{avg_vols[asset]:.2%}",
            "Ratio": f"{vol_ratios[asset]:.2f}x",
            "Status": (
                "Below Average" if vol_ratios[asset] < 0.9 else
                ("Average" if vol_ratios[asset] < 1.1 else "Above Average")
            )
        })
    
    vol_table = html.Div([
        dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Asset"),
                    html.Th("Current Volatility"),
                    html.Th("Historical Average"),
                    html.Th("Ratio"),
                    html.Th("Status")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(data["Asset"]),
                    html.Td(data["Current Volatility"]),
                    html.Td(data["Historical Average"]),
                    html.Td(data["Ratio"]),
                    html.Td(
                        data["Status"],
                        className=(
                            "text-success" if data["Status"] == "Below Average" else
                            ("text-warning" if data["Status"] == "Average" else "text-danger")
                        )
                    )
                ]) for data in vol_table_data
            ])
        ], bordered=True, hover=True, responsive=True, striped=True)
    ])
    
    # Assemble view
    return html.Div([
        dbc.Row([
            dbc.Col(vol_series_chart, width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(vol_table, width=12, className="mb-4")
        ]),
        dbc.Row([
            dbc.Col(vol_comparison_chart, md=6),
            dbc.Col(vol_ratio_chart, md=6)
        ])
    ])


# ---------- Helper Functions ---------- #

def generate_sample_risk_data(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Generate sample risk data for demonstration purposes.
    
    Args:
        start_date: Start date for the data
        end_date: End date for the data
        
    Returns:
        Dictionary containing sample risk data
    """
    # Generate sample VaR data
    var_95_hist = np.random.uniform(0.015, 0.025)
    var_99_hist = var_95_hist * 1.3
    var_90_hist = var_95_hist * 0.8
    
    var_95_param = var_95_hist * np.random.uniform(0.9, 1.1)
    var_99_param = var_99_hist * np.random.uniform(0.9, 1.1)
    var_90_param = var_90_hist * np.random.uniform(0.9, 1.1)
    
    var_95_mc = var_95_hist * np.random.uniform(0.9, 1.1)
    var_99_mc = var_99_hist * np.random.uniform(0.9, 1.1)
    var_90_mc = var_90_hist * np.random.uniform(0.9, 1.1)
    
    # Previous period VaR
    prev_var_95_hist = var_95_hist * np.random.uniform(0.8, 1.2)
    prev_var_99_hist = var_99_hist * np.random.uniform(0.8, 1.2)
    prev_var_90_hist = var_90_hist * np.random.uniform(0.8, 1.2)
    
    # Drawdown data
    current_dd = np.random.uniform(0.005, 0.02)
    max_dd = max(current_dd, np.random.uniform(0.02, 0.04))
    
    # Concentration data
    concentration_value = np.random.uniform(1.2, 2.5)
    
    # Market data
    regimes = ["Normal", "High Volatility", "Risk-On", "Risk-Off", "Trending"]
    market_regime = np.random.choice(regimes)
    market_vol = np.random.uniform(0.01, 0.03)
    
    return {
        "var": {
            "var_95_historical": var_95_hist,
            "var_99_historical": var_99_hist,
            "var_90_historical": var_90_hist,
            "var_95_parametric": var_95_param,
            "var_99_parametric": var_99_param,
            "var_90_parametric": var_90_param,
            "var_95_monte_carlo": var_95_mc,
            "var_99_monte_carlo": var_99_mc,
            "var_90_monte_carlo": var_90_mc
        },
        "previous_var": {
            "var_95_historical": prev_var_95_hist,
            "var_99_historical": prev_var_99_hist,
            "var_90_historical": prev_var_90_hist
        },
        "drawdown": {
            "current": current_dd,
            "max": max_dd
        },
        "concentration": {
            "value": concentration_value,
            "top_exposure": {
                "name": "BTC-USD",
                "percentage": np.random.uniform(0.2, 0.4)
            }
        },
        "market": {
            "regime": market_regime,
            "volatility": market_vol
        },
        "time_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }


def generate_sample_risk_alerts(risk_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate sample risk alerts for demonstration purposes.
    
    Args:
        risk_data: Current risk data
        
    Returns:
        Dictionary containing sample risk alerts
    """
    # Sample alert types and severities
    alert_types = [
        {"type": "var_breach", "message": "Portfolio VaR exceeds threshold", "severity": "high"},
        {"type": "drawdown_breach", "message": "Current drawdown exceeds alert level", "severity": "medium"},
        {"type": "concentration_breach", "message": "Position concentration too high", "severity": "medium"},
        {"type": "volatility_spike", "message": "Market volatility spike detected", "severity": "high"},
        {"type": "liquidity_warning", "message": "Reduced market liquidity detected", "severity": "low"},
        {"type": "margin_warning", "message": "Account approaching margin limit", "severity": "high"},
        {"type": "correlation_shift", "message": "Unusual correlation pattern detected", "severity": "low"}
    ]
    
    # Randomly select 0-3 alerts
    num_alerts = np.random.randint(0, 4)
    selected_alerts = []
    
    if num_alerts > 0:
        # Select random alerts without replacement
        selected_indices = np.random.choice(len(alert_types), size=num_alerts, replace=False)
        
        for idx in selected_indices:
            alert = alert_types[idx].copy()
            
            # Add timestamp and details
            alert["timestamp"] = datetime.now().isoformat()
            
            if alert["type"] == "var_breach":
                threshold = np.random.uniform(0.015, 0.02)
                current = risk_data["var"]["var_95_historical"]
                alert["details"] = f"Current: {current:.2%}, Threshold: {threshold:.2%}"
                
            elif alert["type"] == "drawdown_breach":
                threshold = np.random.uniform(0.01, 0.015)
                current = risk_data["drawdown"]["current"]
                alert["details"] = f"Current: {current:.2%}, Threshold: {threshold:.2%}"
                
            elif alert["type"] == "concentration_breach":
                asset = risk_data["concentration"]["top_exposure"]["name"]
                pct = risk_data["concentration"]["top_exposure"]["percentage"]
                alert["details"] = f"{asset}: {pct:.2%} of portfolio"
                
            selected_alerts.append(alert)
    
    return {"alerts": selected_alerts} 