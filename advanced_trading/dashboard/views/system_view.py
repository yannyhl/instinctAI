"""
System View

This module provides the system health and status view for the dashboard.
"""

import os
import sys
import logging
import threading
import psutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Import Dash libraries
import dash
from dash import html, dcc, callback, Output, Input, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import core modules
from core import config_manager, metrics, logging as log_manager

# Import dashboard modules
from ..components import status_card, control_panel
from ..services import system_service

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.system_view"})


def layout():
    """
    Create the system view layout.
    
    Returns:
        Dash layout
    """
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.H1("System Health & Status"),
                html.P("Monitor system resources, component status, and performance metrics."),
            ], width=8),
            dbc.Col([
                control_panel.create_control_panel("system")
            ], width=4),
        ], className="mb-4"),
        
        dbc.Row([
            # System status cards
            dbc.Col([
                status_card.create_status_card(
                    "CPU Usage", 
                    id="cpu-usage-card",
                    icon="cpu"
                ),
            ], width=3),
            dbc.Col([
                status_card.create_status_card(
                    "Memory Usage", 
                    id="memory-usage-card",
                    icon="memory"
                ),
            ], width=3),
            dbc.Col([
                status_card.create_status_card(
                    "Disk Usage", 
                    id="disk-usage-card",
                    icon="hdd"
                ),
            ], width=3),
            dbc.Col([
                status_card.create_status_card(
                    "Network Activity", 
                    id="network-card",
                    icon="wifi"
                ),
            ], width=3),
        ], className="mb-4"),
        
        dbc.Row([
            # Component status
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Component Status"),
                    dbc.CardBody([
                        html.Div(id="component-status-content")
                    ])
                ])
            ], width=6),
            
            # System logs
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent System Events"),
                    dbc.CardBody([
                        html.Div(id="system-logs-content", style={"maxHeight": "300px", "overflow": "auto"})
                    ])
                ])
            ], width=6),
        ], className="mb-4"),
        
        dbc.Row([
            # CPU usage graph
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("CPU Usage Over Time"),
                    dbc.CardBody([
                        dcc.Graph(id="cpu-usage-graph")
                    ])
                ])
            ], width=6),
            
            # Memory usage graph
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Memory Usage Over Time"),
                    dbc.CardBody([
                        dcc.Graph(id="memory-usage-graph")
                    ])
                ])
            ], width=6),
        ], className="mb-4"),
        
        dbc.Row([
            # Process Table
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("System Processes"),
                    dbc.CardBody([
                        html.Div(id="process-table-content")
                    ])
                ])
            ], width=12),
        ])
    ])


def register_callbacks(app):
    """
    Register callbacks for the system view.
    
    Args:
        app: Dash application
    """
    # CPU usage card update
    @app.callback(
        Output("cpu-usage-card", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_cpu_card(n_intervals):
        """Update the CPU usage card"""
        cpu_percent = psutil.cpu_percent()
        return [
            html.H3(f"{cpu_percent:.1f}%", className="card-title"),
            html.P("Current CPU utilization", className="card-text"),
            get_status_badge(cpu_percent, [30, 70])
        ]
    
    # Memory usage card update
    @app.callback(
        Output("memory-usage-card", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_memory_card(n_intervals):
        """Update the memory usage card"""
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024 ** 3)
        memory_total_gb = memory.total / (1024 ** 3)
        
        return [
            html.H3(f"{memory_percent:.1f}%", className="card-title"),
            html.P(f"{memory_used_gb:.1f} / {memory_total_gb:.1f} GB", className="card-text"),
            get_status_badge(memory_percent, [30, 70])
        ]
    
    # Disk usage card update
    @app.callback(
        Output("disk-usage-card", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_disk_card(n_intervals):
        """Update the disk usage card"""
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024 ** 3)
        disk_total_gb = disk.total / (1024 ** 3)
        
        return [
            html.H3(f"{disk_percent:.1f}%", className="card-title"),
            html.P(f"{disk_used_gb:.1f} / {disk_total_gb:.1f} GB", className="card-text"),
            get_status_badge(disk_percent, [50, 80])
        ]
    
    # Network activity card update
    @app.callback(
        Output("network-card", "children"),
        Input("medium-interval", "n_intervals"),
        State("network-card", "children"),
    )
    def update_network_card(n_intervals, previous_children):
        """Update the network activity card"""
        net_io = psutil.net_io_counters()
        
        # Calculate rates if previous data available
        if previous_children and isinstance(previous_children, list) and len(previous_children) > 2:
            try:
                send_text = previous_children[1].children
                if isinstance(send_text, str) and " KB/s" in send_text:
                    previous_send = float(send_text.split(" KB/s")[0].split(": ")[1])
                    previous_recv = float(send_text.split(" KB/s recv: ")[1].split(" KB/s")[0])
                    
                    # Just placeholder values - in a real system you'd track actual previous values and timestamps
                    send_rate = previous_send + 1.5
                    recv_rate = previous_recv + 2.3
                else:
                    send_rate = 0
                    recv_rate = 0
            except (ValueError, IndexError, AttributeError):
                send_rate = 0
                recv_rate = 0
        else:
            send_rate = 0
            recv_rate = 0
        
        # Check if active
        network_active = send_rate > 0.5 or recv_rate > 0.5
        
        return [
            html.H3("Active" if network_active else "Idle", className="card-title"),
            html.P(f"send: {send_rate:.1f} KB/s recv: {recv_rate:.1f} KB/s", className="card-text"),
            get_status_badge("good" if network_active else "warning")
        ]
    
    # Component status update
    @app.callback(
        Output("component-status-content", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_component_status(n_intervals):
        """Update the component status table"""
        # Get component status from system service
        components = system_service.get_component_status()
        
        # Create status table
        return html.Table([
            html.Thead(
                html.Tr([
                    html.Th("Component"),
                    html.Th("Status"),
                    html.Th("Last Update"),
                    html.Th("Details")
                ])
            ),
            html.Tbody([
                html.Tr([
                    html.Td(component["name"]),
                    html.Td(get_status_badge(component["status"])),
                    html.Td(component["last_update"]),
                    html.Td(component["details"]),
                ]) for component in components
            ])
        ], className="table table-striped table-sm")
    
    # System logs update
    @app.callback(
        Output("system-logs-content", "children"),
        Input("medium-interval", "n_intervals"),
    )
    def update_system_logs(n_intervals):
        """Update the system logs display"""
        # Get recent logs from system service
        logs = system_service.get_recent_logs(20)
        
        # Create log display
        return html.Div([
            html.Div([
                html.Span(log["timestamp"], className="text-muted me-2"),
                html.Span(log["level"], className=f"badge me-2 bg-{get_log_level_color(log['level'])}"),
                html.Span(log["message"])
            ], className="mb-1 border-bottom pb-1") for log in logs
        ])
    
    # CPU usage graph update
    @app.callback(
        Output("cpu-usage-graph", "figure"),
        Input("slow-interval", "n_intervals"),
    )
    def update_cpu_graph(n_intervals):
        """Update the CPU usage graph"""
        # Get CPU history from system service
        cpu_history = system_service.get_cpu_history()
        
        # Create DataFrame for plotting
        if not cpu_history:
            # Create empty plot if no data
            return px.line(title="No CPU data available")
        
        df = pd.DataFrame(cpu_history)
        
        # Create plot
        fig = px.line(df, x="timestamp", y="usage", title="CPU Usage")
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Usage (%)",
            yaxis_range=[0, 100],
            template="plotly_dark" if config_manager.get("dashboard.theme", "dark") == "dark" else "plotly"
        )
        
        return fig
    
    # Memory usage graph update
    @app.callback(
        Output("memory-usage-graph", "figure"),
        Input("slow-interval", "n_intervals"),
    )
    def update_memory_graph(n_intervals):
        """Update the memory usage graph"""
        # Get memory history from system service
        memory_history = system_service.get_memory_history()
        
        # Create DataFrame for plotting
        if not memory_history:
            # Create empty plot if no data
            return px.line(title="No memory data available")
        
        df = pd.DataFrame(memory_history)
        
        # Create plot
        fig = px.line(df, x="timestamp", y="usage", title="Memory Usage")
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Usage (%)",
            yaxis_range=[0, 100],
            template="plotly_dark" if config_manager.get("dashboard.theme", "dark") == "dark" else "plotly"
        )
        
        return fig
    
    # Process table update
    @app.callback(
        Output("process-table-content", "children"),
        Input("slow-interval", "n_intervals"),
    )
    def update_process_table(n_intervals):
        """Update the process table"""
        # Get process table from system service
        processes = system_service.get_processes(10)
        
        # Create process table
        return html.Table([
            html.Thead(
                html.Tr([
                    html.Th("PID"),
                    html.Th("Name"),
                    html.Th("Status"),
                    html.Th("CPU %"),
                    html.Th("Memory %"),
                    html.Th("Created")
                ])
            ),
            html.Tbody([
                html.Tr([
                    html.Td(process["pid"]),
                    html.Td(process["name"]),
                    html.Td(process["status"]),
                    html.Td(f"{process['cpu_percent']:.1f}%"),
                    html.Td(f"{process['memory_percent']:.1f}%"),
                    html.Td(process["created"])
                ]) for process in processes
            ])
        ], className="table table-striped table-sm")


def get_status_badge(status, thresholds=None):
    """
    Create a status badge based on status value.
    
    Args:
        status: Status value (numeric or string)
        thresholds: Optional thresholds for numeric values [warning, critical]
        
    Returns:
        Status badge component
    """
    if isinstance(status, (int, float)):
        # Numeric status
        if thresholds:
            warning, critical = thresholds
            if status >= critical:
                status_class = "danger"
                status_text = "Critical"
            elif status >= warning:
                status_class = "warning"
                status_text = "Warning"
            else:
                status_class = "success"
                status_text = "Good"
        else:
            # Default numeric handling
            if status >= 80:
                status_class = "danger"
                status_text = "Critical"
            elif status >= 50:
                status_class = "warning"
                status_text = "Warning"
            else:
                status_class = "success"
                status_text = "Good"
    else:
        # String status
        status = status.lower()
        if status in ["good", "online", "active", "running", "ok"]:
            status_class = "success"
            status_text = "Good"
        elif status in ["warning", "degraded", "slow"]:
            status_class = "warning"
            status_text = "Warning"
        elif status in ["error", "critical", "down", "offline", "stopped"]:
            status_class = "danger"
            status_text = "Critical"
        else:
            status_class = "secondary"
            status_text = "Unknown"
    
    return html.Span(status_text, className=f"badge bg-{status_class}")


def get_log_level_color(level):
    """
    Get the color for a log level.
    
    Args:
        level: Log level
        
    Returns:
        Color class
    """
    level = level.lower()
    if level in ["debug"]:
        return "secondary"
    elif level in ["info"]:
        return "primary"
    elif level in ["warning"]:
        return "warning"
    elif level in ["error"]:
        return "danger"
    elif level in ["critical"]:
        return "dark"
    else:
        return "light" 