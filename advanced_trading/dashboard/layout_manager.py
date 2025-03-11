"""
Dashboard Layout Manager
-----------------------
Provides standardized layout components and theming for the Instinct AI Trading Dashboard.
"""

import dash
from dash import html, dcc
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Any, Optional, Union
import pandas as pd
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Color themes
THEMES = {
    "default": {
        "primary": "#2C3E50",
        "secondary": "#18BC9C",
        "success": "#28a745",
        "danger": "#dc3545",
        "warning": "#ffc107",
        "info": "#17a2b8",
        "light": "#f8f9fa",
        "dark": "#343a40",
        "background": "#ffffff",
        "panel_bg": "#f8f9fa",
        "text": "#212529",
        "text_light": "#6c757d",
        "border": "#dee2e6"
    },
    "dark": {
        "primary": "#375a7f",
        "secondary": "#444444",
        "success": "#00bc8c",
        "danger": "#e74c3c",
        "warning": "#f39c12",
        "info": "#3498db",
        "light": "#adb5bd",
        "dark": "#303030",
        "background": "#222222",
        "panel_bg": "#303030",
        "text": "#fff",
        "text_light": "#999",
        "border": "#444"
    },
    "crypto": {
        "primary": "#1D2330",
        "secondary": "#3861FB",
        "success": "#16C784",
        "danger": "#EA3943",
        "warning": "#FF9332",
        "info": "#8C8CFF",
        "light": "#F8FAFD",
        "dark": "#0D1421",
        "background": "#FFFFFF",
        "panel_bg": "#F8FAFD",
        "text": "#222531",
        "text_light": "#616E85",
        "border": "#EFF2F5"
    }
}

# Current theme
CURRENT_THEME = "default"

def set_theme(theme_name: str):
    """
    Set the current theme.
    
    Args:
        theme_name: Theme name from THEMES dict
    """
    global CURRENT_THEME
    if theme_name in THEMES:
        CURRENT_THEME = theme_name
        logger.info(f"Theme set to {theme_name}")
    else:
        logger.warning(f"Theme {theme_name} not found, using default")
        CURRENT_THEME = "default"

def get_theme_colors():
    """Get current theme colors."""
    return THEMES[CURRENT_THEME]

def create_header(title: str, subtitle: str = None, last_update_id: str = "last-update-time") -> html.Div:
    """
    Create a standardized header component.
    
    Args:
        title: Main title
        subtitle: Optional subtitle
        last_update_id: ID for the last update time element
        
    Returns:
        Dash header component
    """
    colors = get_theme_colors()
    
    header_style = {
        "padding": "20px",
        "background-color": colors["primary"],
        "color": "white",
        "margin-bottom": "20px",
        "border-radius": "5px",
        "box-shadow": "0 2px 4px rgba(0, 0, 0, 0.1)"
    }
    
    if subtitle:
        header_content = [
            html.H1(title, style={"margin-bottom": "5px"}),
            html.P(subtitle, style={"margin-top": "0px"}),
            html.Div(id=last_update_id, style={"font-style": "italic", "font-size": "0.8em", "opacity": "0.8"})
        ]
    else:
        header_content = [
            html.H1(title, style={"margin-bottom": "5px"}),
            html.Div(id=last_update_id, style={"font-style": "italic", "font-size": "0.8em", "opacity": "0.8"})
        ]
    
    return html.Div(header_content, style=header_style)

def create_card(title: str, content: Union[dash.development.base_component.Component, List[dash.development.base_component.Component]], 
              footer: Optional[dash.development.base_component.Component] = None,
              color: Optional[str] = None) -> html.Div:
    """
    Create a card component with title and content.
    
    Args:
        title: Card title
        content: Card content (Dash component or list of components)
        footer: Optional footer component
        color: Optional background color override
        
    Returns:
        Dash card component
    """
    colors = get_theme_colors()
    
    card_style = {
        "background-color": color if color else colors["panel_bg"],
        "border-radius": "5px",
        "border": f"1px solid {colors['border']}",
        "padding": "15px",
        "margin-bottom": "20px",
        "box-shadow": "0 2px 4px rgba(0, 0, 0, 0.05)"
    }
    
    header_style = {
        "border-bottom": f"1px solid {colors['border']}",
        "padding-bottom": "10px",
        "margin-bottom": "15px",
        "font-weight": "bold",
        "color": colors["text"]
    }
    
    footer_style = {
        "border-top": f"1px solid {colors['border']}",
        "padding-top": "10px",
        "margin-top": "15px",
        "font-size": "0.9em",
        "color": colors["text_light"]
    }
    
    card_components = [
        html.Div(title, style=header_style),
        html.Div(content, style={"padding": "5px 0"})
    ]
    
    if footer:
        card_components.append(html.Div(footer, style=footer_style))
    
    return html.Div(card_components, style=card_style)

def create_metric_row(metrics: List[Dict[str, Any]]) -> html.Div:
    """
    Create a row of metric cards.
    
    Args:
        metrics: List of metric dictionaries with keys:
                - title: Metric title
                - value: Metric value
                - unit: Optional unit (%, $, etc.)
                - change: Optional change value
                - color: Optional color override
        
    Returns:
        Dash component with metric cards in a row
    """
    colors = get_theme_colors()
    
    metric_cards = []
    
    for metric in metrics:
        # Determine color based on value or change if applicable
        metric_color = metric.get("color")
        if not metric_color and "change" in metric:
            change = metric["change"]
            if isinstance(change, (int, float)):
                metric_color = colors["success"] if change > 0 else colors["danger"] if change < 0 else colors["text"]
        
        if not metric_color:
            metric_color = colors["text"]
        
        # Format value
        value = metric["value"]
        unit = metric.get("unit", "")
        
        if isinstance(value, (int, float)):
            if value >= 10000 and "format" not in metric:
                formatted_value = f"{value:,.0f}{unit}"
            elif "format" in metric:
                formatted_value = metric["format"].format(value) + unit
            else:
                formatted_value = f"{value:.2f}{unit}"
        else:
            formatted_value = f"{value}{unit}"
        
        # Create metric card
        card_content = [
            html.Div(metric["title"], style={"font-size": "0.9em", "color": colors["text_light"]}),
            html.Div(formatted_value, style={
                "font-size": "1.8em", 
                "font-weight": "bold",
                "color": metric_color,
                "margin": "5px 0"
            })
        ]
        
        # Add change indicator if available
        if "change" in metric:
            change = metric["change"]
            if isinstance(change, (int, float)):
                change_color = colors["success"] if change > 0 else colors["danger"] if change < 0 else colors["text_light"]
                change_icon = "▲" if change > 0 else "▼" if change < 0 else "•"
                
                card_content.append(html.Div([
                    f"{change_icon} {abs(change):.2f}%"
                ], style={"color": change_color, "font-size": "0.9em"}))
        
        metric_card = html.Div(card_content, style={
            "background-color": colors["panel_bg"],
            "border-radius": "5px",
            "border": f"1px solid {colors['border']}",
            "padding": "15px",
            "text-align": "center",
            "width": f"calc({100 / len(metrics)}% - 20px)",
            "margin": "0 10px",
            "display": "inline-block"
        })
        
        metric_cards.append(metric_card)
    
    return html.Div(metric_cards, style={"display": "flex", "margin": "0 -10px 20px -10px"})

def create_tab_layout(tabs: List[Dict[str, Any]]) -> html.Div:
    """
    Create a tabbed layout.
    
    Args:
        tabs: List of tab dictionaries with keys:
              - label: Tab label
              - content: Tab content
              - value: Optional tab value (defaults to label)
        
    Returns:
        Dash tabs component
    """
    colors = get_theme_colors()
    
    # Process tabs
    tab_items = []
    tab_content = []
    
    for i, tab in enumerate(tabs):
        tab_value = tab.get("value", str(i))
        tab_items.append(dcc.Tab(
            label=tab["label"],
            value=tab_value,
            style={
                "padding": "10px 15px",
                "border-bottom": f"1px solid {colors['border']}",
                "backgroundColor": colors["panel_bg"],
                "color": colors["text"]
            },
            selected_style={
                "padding": "10px 15px",
                "borderTop": f"3px solid {colors['primary']}",
                "borderBottom": f"0px solid {colors['panel_bg']}",
                "backgroundColor": colors["panel_bg"],
                "color": colors["primary"],
                "fontWeight": "bold"
            }
        ))
        
        tab_content.append(html.Div(
            tab["content"],
            id=f"tab-content-{tab_value}",
            style={"display": "none"}
        ))
    
    # Create tabs component
    tabs_component = html.Div([
        dcc.Tabs(
            id="tabs",
            value="0",
            children=tab_items,
            style={
                "borderBottom": f"1px solid {colors['border']}",
                "marginBottom": "20px"
            }
        ),
        html.Div(
            tab_content,
            id="tabs-content"
        )
    ])
    
    return tabs_component

def create_alert(message: str, type: str = "info", is_dismissible: bool = True, id: Optional[str] = None) -> html.Div:
    """
    Create an alert component.
    
    Args:
        message: Alert message
        type: Alert type (info, success, warning, danger)
        is_dismissible: Whether the alert can be dismissed
        id: Optional ID for the alert
        
    Returns:
        Dash alert component
    """
    colors = get_theme_colors()
    
    # Map alert type to color
    alert_colors = {
        "info": colors["info"],
        "success": colors["success"],
        "warning": colors["warning"],
        "danger": colors["danger"],
    }
    
    bg_color = alert_colors.get(type, colors["info"])
    
    alert_style = {
        "backgroundColor": _adjust_color_opacity(bg_color, 0.2),
        "color": bg_color,
        "padding": "15px",
        "borderRadius": "5px",
        "border": f"1px solid {_adjust_color_opacity(bg_color, 0.5)}",
        "marginBottom": "20px",
        "position": "relative",
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center"
    }
    
    # Create close button if dismissible
    if is_dismissible:
        close_button = html.Button(
            "×",
            style={
                "backgroundColor": "transparent",
                "border": "none",
                "color": bg_color,
                "fontSize": "20px",
                "fontWeight": "bold",
                "cursor": "pointer",
                "padding": "0",
                "lineHeight": "1",
                "marginLeft": "15px"
            },
            n_clicks=0,
            className="alert-close"
        )
        alert_content = [html.Div(message), close_button]
    else:
        alert_content = message
    
    # Add ID if provided
    if id:
        return html.Div(alert_content, style=alert_style, id=id)
    else:
        return html.Div(alert_content, style=alert_style)

def create_table(
    columns: List[Dict[str, str]], 
    data: List[Dict[str, Any]], 
    striped: bool = True, 
    bordered: bool = True,
    hover: bool = True
) -> html.Table:
    """
    Create a styled table component.
    
    Args:
        columns: List of column dictionaries with keys 'id' and 'name'
        data: List of data dictionaries with column ids as keys
        striped: Whether to stripe alternate rows
        bordered: Whether to add borders
        hover: Whether to add hover effect
        
    Returns:
        Dash table component
    """
    colors = get_theme_colors()
    
    # Create table header
    header_cells = [html.Th(col["name"], style={
        "textAlign": "left",
        "padding": "12px 15px",
        "backgroundColor": colors["primary"],
        "color": "white",
        "fontWeight": "bold"
    }) for col in columns]
    
    header = html.Thead(html.Tr(header_cells))
    
    # Create table rows
    rows = []
    for i, row_data in enumerate(data):
        row_style = {
            "backgroundColor": colors["panel_bg"] if not striped or i % 2 == 0 else _adjust_color_opacity(colors["light"], 0.5)
        }
        
        cells = []
        for col in columns:
            # Get cell value
            value = row_data.get(col["id"], "")
            
            # Apply cell formatting if specified
            if "format" in col and callable(col["format"]):
                formatted_value = col["format"](value)
            else:
                formatted_value = value
            
            cells.append(html.Td(formatted_value, style={
                "padding": "8px 15px",
                "borderBottom": f"1px solid {colors['border']}" if bordered else "none"
            }))
        
        rows.append(html.Tr(cells, style=row_style))
    
    # Create table body
    body = html.Tbody(rows)
    
    # Create table
    table_style = {
        "width": "100%",
        "borderCollapse": "collapse",
        "marginBottom": "20px",
        "border": f"1px solid {colors['border']}" if bordered else "none"
    }
    
    return html.Table([header, body], style=table_style)

def create_donut_chart(
    labels: List[str],
    values: List[Union[int, float]],
    title: Optional[str] = None,
    colors: Optional[List[str]] = None,
    hole: float = 0.6
) -> dcc.Graph:
    """
    Create a donut chart.
    
    Args:
        labels: Slice labels
        values: Slice values
        title: Optional chart title
        colors: Optional custom colors
        hole: Hole size (0-1)
        
    Returns:
        Dash Graph component with donut chart
    """
    theme_colors = get_theme_colors()
    
    # Use theme colors if not provided
    if not colors:
        colors = [
            theme_colors["primary"],
            theme_colors["secondary"],
            theme_colors["success"],
            theme_colors["info"],
            theme_colors["warning"],
            theme_colors["danger"]
        ]
        
        # Extend colors if needed
        while len(colors) < len(labels):
            colors.extend(colors)
    
    # Create donut chart
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=hole,
        marker=dict(colors=colors[:len(labels)]),
        textinfo='label+percent',
        insidetextorientation='radial'
    )])
    
    # Set layout
    layout = {
        "margin": dict(l=20, r=20, t=30, b=20),
        "paper_bgcolor": theme_colors["panel_bg"],
        "plot_bgcolor": theme_colors["panel_bg"],
        "font": dict(color=theme_colors["text"])
    }
    
    if title:
        layout["title"] = title
    
    fig.update_layout(**layout)
    
    return dcc.Graph(figure=fig)

def _adjust_color_opacity(color: str, opacity: float) -> str:
    """
    Adjust color opacity.
    
    Args:
        color: Color in hex format (#RRGGBB)
        opacity: Opacity value (0-1)
        
    Returns:
        RGBA color string
    """
    # Handle shorthand hex
    if color.startswith('#') and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return f"rgba({r}, {g}, {b}, {opacity})"
    
    # Already rgba
    elif color.startswith('rgba'):
        return color
    
    # Other formats - return as is
    return color

def create_separator(margin: str = "20px 0") -> html.Hr:
    """
    Create a horizontal separator.
    
    Args:
        margin: CSS margin value
        
    Returns:
        Dash Hr component
    """
    colors = get_theme_colors()
    
    return html.Hr(style={
        "border": 0,
        "borderTop": f"1px solid {colors['border']}",
        "margin": margin
    })

def create_button(
    text: str,
    id: Optional[str] = None,
    type: str = "primary",
    size: str = "md",
    icon: Optional[str] = None,
    style: Optional[Dict[str, str]] = None
) -> html.Button:
    """
    Create a styled button component.
    
    Args:
        text: Button text
        id: Optional button ID
        type: Button type (primary, secondary, success, danger, warning, info)
        size: Button size (sm, md, lg)
        icon: Optional icon class (FontAwesome) to display
        style: Optional additional styles
        
    Returns:
        Dash Button component
    """
    colors = get_theme_colors()
    
    # Map button type to color
    button_colors = {
        "primary": colors["primary"],
        "secondary": colors["secondary"],
        "success": colors["success"],
        "danger": colors["danger"],
        "warning": colors["warning"],
        "info": colors["info"]
    }
    
    bg_color = button_colors.get(type, colors["primary"])
    
    # Map size to padding and font size
    size_map = {
        "sm": {"padding": "6px 12px", "font-size": "0.875rem"},
        "md": {"padding": "8px 16px", "font-size": "1rem"},
        "lg": {"padding": "10px 20px", "font-size": "1.25rem"}
    }
    
    size_style = size_map.get(size, size_map["md"])
    
    # Base button style
    button_style = {
        "background-color": bg_color,
        "color": "white",
        "border": "none",
        "border-radius": "4px",
        "cursor": "pointer",
        "font-weight": "500",
        "text-align": "center",
        "transition": "background-color 0.15s ease-in-out",
        **size_style
    }
    
    # Add custom styles if provided
    if style:
        button_style.update(style)
    
    # Create button content
    if icon:
        button_content = [html.I(className=icon, style={"margin-right": "6px"}), text]
    else:
        button_content = text
    
    # Add ID if provided
    if id:
        return html.Button(button_content, style=button_style, id=id)
    else:
        return html.Button(button_content, style=button_style)

def create_input_group(
    label: str,
    input_component: dash.development.base_component.Component,
    help_text: Optional[str] = None,
    required: bool = False
) -> html.Div:
    """
    Create an input group with label and optional help text.
    
    Args:
        label: Input label
        input_component: Dash input component (dcc.Input, dcc.Dropdown, etc.)
        help_text: Optional help text
        required: Whether the input is required
        
    Returns:
        Dash Div component containing the input group
    """
    colors = get_theme_colors()
    
    label_style = {
        "display": "block",
        "margin-bottom": "6px",
        "font-weight": "500",
        "color": colors["text"]
    }
    
    help_style = {
        "font-size": "0.875em",
        "color": colors["text_light"],
        "margin-top": "6px"
    }
    
    # Create label element
    if required:
        label_element = html.Label([
            label, 
            html.Span(" *", style={"color": colors["danger"]})
        ], style=label_style)
    else:
        label_element = html.Label(label, style=label_style)
    
    # Create input group
    group_elements = [label_element, input_component]
    
    # Add help text if provided
    if help_text:
        group_elements.append(html.Small(help_text, style=help_style))
    
    return html.Div(group_elements, style={"margin-bottom": "20px"})

def create_main_layout(
    title: str,
    subtitle: Optional[str] = None,
    content: List[dash.development.base_component.Component] = None,
    sidebar: Optional[dash.development.base_component.Component] = None,
    sidebar_width: str = "25%",
    last_update_id: str = "last-update-time"
) -> html.Div:
    """
    Create a main layout with optional sidebar.
    
    Args:
        title: Page title
        subtitle: Optional subtitle
        content: Main content components
        sidebar: Optional sidebar component
        sidebar_width: Width of sidebar (if present)
        last_update_id: ID for the last update time element
        
    Returns:
        Dash Div component with the main layout
    """
    colors = get_theme_colors()
    
    # Create header
    header = create_header(title, subtitle, last_update_id)
    
    # Create content area
    if sidebar:
        # Layout with sidebar
        content_area = html.Div([
            # Sidebar
            html.Div(sidebar, style={
                "width": sidebar_width,
                "padding-right": "20px"
            }),
            
            # Main content
            html.Div(content or [], style={
                "width": f"calc(100% - {sidebar_width})"
            })
        ], style={
            "display": "flex",
            "flex-wrap": "wrap"
        })
    else:
        # Full width content
        content_area = html.Div(content or [])
    
    # Create footer
    footer = html.Footer([
        html.Hr(style={"margin": "20px 0"}),
        html.P([
            "Instinct AI Trading Dashboard ",
            html.Span("© " + str(datetime.now().year), style={"opacity": "0.8"})
        ], style={
            "text-align": "center",
            "color": colors["text_light"],
            "font-size": "0.9em"
        })
    ])
    
    # Return complete layout
    return html.Div([
        header,
        content_area,
        footer
    ], style={
        "max-width": "1400px",
        "margin": "0 auto",
        "padding": "20px",
        "background-color": colors["background"],
        "color": colors["text"]
    }) 