"""
Dashboard Components
------------------
Specialized components and widgets for the Instinct AI Trading Dashboard.
"""

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import html, dcc

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import project modules
from dashboard.layout_manager import create_card, get_theme_colors

def create_price_chart(
    price_data: Dict[str, Any],
    show_volume: bool = True,
    show_indicators: bool = True,
    height: int = 500
) -> dcc.Graph:
    """
    Create a price chart with optional volume and indicators.
    
    Args:
        price_data: Price data dictionary from market_data_handler
        show_volume: Whether to show volume
        show_indicators: Whether to show technical indicators
        height: Chart height in pixels
        
    Returns:
        Dash Graph component with the price chart
    """
    colors = get_theme_colors()
    
    # Create figure with secondary y-axis if showing volume
    fig = make_subplots(specs=[[{"secondary_y": show_volume}]])
    
    # Extract data
    timestamps = price_data['data']['timestamps']
    opens = price_data['data']['open']
    highs = price_data['data']['high']
    lows = price_data['data']['low']
    closes = price_data['data']['close']
    volumes = price_data['data']['volume'] if 'volume' in price_data['data'] else []
    
    # Add price candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=timestamps,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name="Price",
            increasing=dict(line=dict(color=colors["success"])),
            decreasing=dict(line=dict(color=colors["danger"]))
        ),
        secondary_y=False
    )
    
    # Add volume if requested
    if show_volume and volumes:
        color_vol = [colors["success"] if closes[i] >= opens[i] else colors["danger"] 
                    for i in range(len(closes))]
        
        fig.add_trace(
            go.Bar(
                x=timestamps,
                y=volumes,
                name="Volume",
                marker=dict(
                    color=[f"rgba({int(c[1:3], 16)}, {int(c[3:5], 16)}, {int(c[5:7], 16)}, 0.5)" 
                          for c in color_vol]
                )
            ),
            secondary_y=True
        )
    
    # Add indicators if requested and available
    if show_indicators and 'indicators' in price_data:
        indicators = price_data['indicators']
        
        # Add Moving Averages
        if 'sma20' in indicators:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=indicators['sma20'],
                    name="SMA(20)",
                    line=dict(color=colors["info"], width=1.5)
                ),
                secondary_y=False
            )
        
        if 'sma50' in indicators:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=indicators['sma50'],
                    name="SMA(50)",
                    line=dict(color=colors["secondary"], width=1.5)
                ),
                secondary_y=False
            )
        
        # Add Bollinger Bands
        if all(k in indicators for k in ['bb_upper', 'bb_middle', 'bb_lower']):
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=indicators['bb_upper'],
                    name="BB Upper",
                    line=dict(color=colors["primary"], width=1, dash='dash'),
                    opacity=0.7
                ),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=indicators['bb_middle'],
                    name="BB Middle",
                    line=dict(color=colors["primary"], width=1),
                    opacity=0.7
                ),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=indicators['bb_lower'],
                    name="BB Lower",
                    line=dict(color=colors["primary"], width=1, dash='dash'),
                    opacity=0.7,
                    fill='tonexty',
                    fillcolor=f"rgba({int(colors['primary'][1:3], 16)}, {int(colors['primary'][3:5], 16)}, {int(colors['primary'][5:7], 16)}, 0.1)"
                ),
                secondary_y=False
            )
    
    # Add current regime annotation if available
    if 'regime' in price_data:
        regime = price_data['regime']
        
        regime_colors = {
            "Bull Market": colors["success"],
            "Sideways/Neutral": colors["warning"],
            "Bear Market": colors["danger"],
            "High Volatility": colors["info"],
            "Low Volatility": colors["secondary"]
        }
        
        regime_color = regime_colors.get(regime, colors["primary"])
        
        fig.add_annotation(
            x=0.02,
            y=0.98,
            xref="paper",
            yref="paper",
            text=f"Regime: {regime}",
            showarrow=False,
            font=dict(
                size=12,
                color=regime_color
            ),
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor=regime_color,
            borderwidth=1,
            borderpad=4
        )
    
    # Update layout
    fig.update_layout(
        title=f"{price_data['symbol']} Price Chart ({price_data['timeframe']})",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=height,
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["panel_bg"],
        font=dict(color=colors["text"])
    )
    
    # Update y-axis labels
    fig.update_yaxes(title_text="Price", secondary_y=False)
    
    if show_volume:
        fig.update_yaxes(title_text="Volume", secondary_y=True)
    
    # Update grid lines
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=f"rgba({int(colors['border'][1:3], 16)}, {int(colors['border'][3:5], 16)}, {int(colors['border'][5:7], 16)}, 0.1)"
    )
    
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=f"rgba({int(colors['border'][1:3], 16)}, {int(colors['border'][3:5], 16)}, {int(colors['border'][5:7], 16)}, 0.1)"
    )
    
    return dcc.Graph(figure=fig)

def create_volume_profile_chart(
    volume_profile_data: Dict[str, Any],
    height: int = 400
) -> dcc.Graph:
    """
    Create a volume profile chart.
    
    Args:
        volume_profile_data: Volume profile data from market_data_handler
        height: Chart height in pixels
        
    Returns:
        Dash Graph component with the volume profile
    """
    colors = get_theme_colors()
    
    # Extract data
    price_levels = volume_profile_data.get('price_levels', [])
    volumes = volume_profile_data.get('volumes', [])
    poc = volume_profile_data.get('poc')
    value_area = volume_profile_data.get('value_area', [])
    
    if not price_levels or not volumes:
        # Empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="No volume profile data available",
            showarrow=False,
            font=dict(
                size=14,
                color=colors["text_light"]
            )
        )
        
        fig.update_layout(
            height=height,
            paper_bgcolor=colors["background"],
            plot_bgcolor=colors["panel_bg"],
            font=dict(color=colors["text"])
        )
        
        return dcc.Graph(figure=fig)
    
    # Create figure
    fig = go.Figure()
    
    # Add horizontal volume bars
    fig.add_trace(
        go.Bar(
            y=price_levels,
            x=volumes,
            orientation='h',
            name="Volume",
            marker=dict(
                color=colors["secondary"],
                opacity=0.7,
                line=dict(
                    color=colors["secondary"],
                    width=1
                )
            )
        )
    )
    
    # Add POC line
    if poc is not None:
        fig.add_shape(
            type="line",
            x0=0,
            y0=poc,
            x1=max(volumes) if volumes else 1,
            y1=poc,
            line=dict(
                color=colors["danger"],
                width=2,
                dash="dash",
            )
        )
        
        fig.add_annotation(
            x=max(volumes) * 0.95 if volumes else 0.95,
            y=poc,
            text="POC",
            showarrow=False,
            font=dict(
                size=10,
                color=colors["danger"]
            )
        )
    
    # Add Value Area
    if value_area and len(value_area) == 2:
        # Value Area Low
        fig.add_shape(
            type="line",
            x0=0,
            y0=value_area[0],
            x1=max(volumes) if volumes else 1,
            y1=value_area[0],
            line=dict(
                color=colors["success"],
                width=1,
                dash="dot",
            )
        )
        
        fig.add_annotation(
            x=max(volumes) * 0.95 if volumes else 0.95,
            y=value_area[0],
            text="VAL",
            showarrow=False,
            font=dict(
                size=8,
                color=colors["success"]
            )
        )
        
        # Value Area High
        fig.add_shape(
            type="line",
            x0=0,
            y0=value_area[1],
            x1=max(volumes) if volumes else 1,
            y1=value_area[1],
            line=dict(
                color=colors["success"],
                width=1,
                dash="dot",
            )
        )
        
        fig.add_annotation(
            x=max(volumes) * 0.95 if volumes else 0.95,
            y=value_area[1],
            text="VAH",
            showarrow=False,
            font=dict(
                size=8,
                color=colors["success"]
            )
        )
    
    # Update layout
    fig.update_layout(
        title=f"{volume_profile_data['symbol']} Volume Profile ({volume_profile_data['timeframe']})",
        xaxis_title="Volume",
        yaxis_title="Price",
        height=height,
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="closest",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["panel_bg"],
        font=dict(color=colors["text"])
    )
    
    # Update axes
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=f"rgba({int(colors['border'][1:3], 16)}, {int(colors['border'][3:5], 16)}, {int(colors['border'][5:7], 16)}, 0.1)"
    )
    
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=f"rgba({int(colors['border'][1:3], 16)}, {int(colors['border'][3:5], 16)}, {int(colors['border'][5:7], 16)}, 0.1)"
    )
    
    return dcc.Graph(figure=fig)

def create_regime_distribution_chart(
    regime_data: Dict[str, Any],
    height: int = 300
) -> dcc.Graph:
    """
    Create a chart showing the distribution of market regimes.
    
    Args:
        regime_data: Regime distribution data from market_data_handler
        height: Chart height in pixels
        
    Returns:
        Dash Graph component with regime distribution
    """
    colors = get_theme_colors()
    
    # Extract data
    regimes = regime_data.get('regimes', [])
    counts = regime_data.get('counts', [])
    current_regime = regime_data.get('current_regime')
    
    if not regimes or not counts:
        # Empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="No regime data available",
            showarrow=False,
            font=dict(
                size=14,
                color=colors["text_light"]
            )
        )
        
        fig.update_layout(
            height=height,
            paper_bgcolor=colors["background"],
            plot_bgcolor=colors["panel_bg"],
            font=dict(color=colors["text"])
        )
        
        return dcc.Graph(figure=fig)
    
    # Create regime colors
    regime_colors = [
        colors["danger"],     # Bear Market
        colors["secondary"],  # Sideways/Neutral
        colors["success"],    # Bull Market
        colors["info"],       # High Volatility
        colors["warning"]     # Low Volatility
    ]
    
    # Ensure we have enough colors
    while len(regime_colors) < len(regimes):
        regime_colors.append(colors["primary"])
    
    # Trim to match number of regimes
    bar_colors = regime_colors[:len(regimes)]
    
    # Create figure
    fig = go.Figure()
    
    # Add distribution bars
    fig.add_trace(
        go.Bar(
            x=regimes,
            y=counts,
            marker_color=bar_colors,
            text=[f"{count:.0f}" for count in counts],
            textposition='auto'
        )
    )
    
    # Add marker for current regime
    if current_regime and current_regime in regimes:
        try:
            current_index = regimes.index(current_regime)
            
            # Add a marker to highlight the current regime
            fig.add_shape(
                type="rect",
                x0=current_index - 0.4,
                x1=current_index + 0.4,
                y0=0,
                y1=counts[current_index],
                line=dict(
                    color="white",
                    width=2,
                ),
                fillcolor="rgba(0, 0, 0, 0)",
            )
            
            fig.add_annotation(
                x=regimes[current_index],
                y=counts[current_index] + max(counts) * 0.1 if counts else 1,
                text="Current",
                showarrow=True,
                arrowhead=2,
                arrowcolor="white",
                arrowsize=1,
                arrowwidth=2
            )
        except (ValueError, IndexError) as e:
            pass
    
    # Update layout
    fig.update_layout(
        title=f"{regime_data['symbol']} Market Regime Distribution",
        xaxis_title="Regime",
        yaxis_title="Days",
        height=height,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["panel_bg"],
        font=dict(color=colors["text"])
    )
    
    # Update axes
    fig.update_xaxes(
        showgrid=False,
        categoryorder='array',
        categoryarray=regimes
    )
    
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=f"rgba({int(colors['border'][1:3], 16)}, {int(colors['border'][3:5], 16)}, {int(colors['border'][5:7], 16)}, 0.1)"
    )
    
    return dcc.Graph(figure=fig)

def create_correlation_matrix_chart(
    correlation_data: Dict[str, Any],
    height: int = 400
) -> dcc.Graph:
    """
    Create a correlation matrix heatmap.
    
    Args:
        correlation_data: Correlation matrix data from market_data_handler
        height: Chart height in pixels
        
    Returns:
        Dash Graph component with correlation matrix
    """
    colors = get_theme_colors()
    
    # Extract data
    symbols = correlation_data.get('symbols', [])
    matrix = correlation_data.get('matrix', [])
    
    if not symbols or not matrix:
        # Empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="No correlation data available",
            showarrow=False,
            font=dict(
                size=14,
                color=colors["text_light"]
            )
        )
        
        fig.update_layout(
            height=height,
            paper_bgcolor=colors["background"],
            plot_bgcolor=colors["panel_bg"],
            font=dict(color=colors["text"])
        )
        
        return dcc.Graph(figure=fig)
    
    # Create figure
    fig = go.Figure()
    
    # Add heatmap
    fig.add_trace(go.Heatmap(
        z=matrix,
        x=symbols,
        y=symbols,
        colorscale='RdBu',
        zmid=0,
        zmin=-1,
        zmax=1,
        colorbar=dict(
            title="Correlation",
            titleside="right"
        ),
        hovertemplate='%{x} - %{y}<br>Correlation: %{z:.2f}<extra></extra>'
    ))
    
    # Update layout
    fig.update_layout(
        title="Asset Correlation Matrix",
        height=height,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["panel_bg"],
        font=dict(color=colors["text"])
    )
    
    return dcc.Graph(figure=fig)

def create_performance_chart(
    strategies: List[str],
    performance_data: Dict[str, pd.DataFrame],
    benchmark_name: str = "BTC/USDT",
    height: int = 400
) -> dcc.Graph:
    """
    Create a performance comparison chart for multiple strategies.
    
    Args:
        strategies: List of strategy names
        performance_data: Dict of performance DataFrames by strategy
        benchmark_name: Name of the benchmark series
        height: Chart height in pixels
        
    Returns:
        Dash Graph component with performance chart
    """
    colors = get_theme_colors()
    
    # Generate strategy colors
    strategy_colors = [
        colors["primary"],
        colors["success"],
        colors["info"],
        colors["warning"],
        colors["secondary"]
    ]
    
    # Create figure
    fig = go.Figure()
    
    # Add strategy lines
    for i, strategy in enumerate(strategies):
        if strategy not in performance_data:
            continue
            
        df = performance_data[strategy]
        
        if 'portfolio_value' not in df.columns:
            continue
            
        # Normalize to starting value of 1 for comparison
        if len(df) > 0:
            initial_value = df['portfolio_value'].iloc[0]
            equity_curve = df['portfolio_value'] / initial_value
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=equity_curve,
                    name=strategy,
                    line=dict(
                        color=strategy_colors[i % len(strategy_colors)],
                        width=2
                    )
                )
            )
    
    # Add benchmark if available
    if benchmark_name in performance_data:
        df = performance_data[benchmark_name]
        
        if 'close' in df.columns and len(df) > 0:
            initial_value = df['close'].iloc[0]
            benchmark_curve = df['close'] / initial_value
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=benchmark_curve,
                    name=f"{benchmark_name} (Benchmark)",
                    line=dict(
                        color=colors["danger"],
                        width=2,
                        dash='dash'
                    )
                )
            )
    
    # Update layout
    fig.update_layout(
        title="Strategy Performance Comparison",
        xaxis_title="Date",
        yaxis_title="Relative Value (Starting = 1)",
        height=height,
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode="x unified",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["panel_bg"],
        font=dict(color=colors["text"])
    )
    
    # Update axes
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=f"rgba({int(colors['border'][1:3], 16)}, {int(colors['border'][3:5], 16)}, {int(colors['border'][5:7], 16)}, 0.1)"
    )
    
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=f"rgba({int(colors['border'][1:3], 16)}, {int(colors['border'][3:5], 16)}, {int(colors['border'][5:7], 16)}, 0.1)"
    )
    
    return dcc.Graph(figure=fig)

def create_market_summary_cards(
    market_data: List[Dict[str, Any]]
) -> List[html.Div]:
    """
    Create market summary cards for multiple symbols.
    
    Args:
        market_data: List of market data dictionaries
        
    Returns:
        List of Dash card components
    """
    colors = get_theme_colors()
    
    cards = []
    
    for data in market_data:
        symbol = data.get('symbol', 'Unknown')
        price = data.get('price', 0.0)
        daily_change = data.get('daily_change', 0.0)
        regime = data.get('regime', 'unknown')
        
        # Determine color based on price change
        change_color = colors["success"] if daily_change >= 0 else colors["danger"]
        change_icon = "▲" if daily_change >= 0 else "▼"
        
        # Create card element
        card = html.Div([
            html.H4(symbol, style={"margin-bottom": "5px", "color": colors["text"]}),
            html.P(f"${price:,.2f}", style={"font-size": "1.2em", "margin-bottom": "5px", "font-weight": "bold"}),
            html.P([
                f"{change_icon} {abs(daily_change):.2f}%"
            ], style={"color": change_color, "margin-bottom": "5px"}),
            html.P(f"Regime: {regime}", style={"font-size": "0.8em", "margin-bottom": "0px", "color": colors["text_light"]})
        ], style={
            "border": f"1px solid {colors['border']}",
            "border-radius": "5px",
            "padding": "10px",
            "margin": "5px",
            "width": "150px",
            "display": "inline-block",
            "text-align": "center",
            "background-color": colors["panel_bg"]
        })
        
        cards.append(card)
    
    return cards

def create_alert_cards(
    alerts: List[Dict[str, Any]]
) -> List[html.Div]:
    """
    Create alert cards for market alerts.
    
    Args:
        alerts: List of alert dictionaries
        
    Returns:
        List of Dash card components
    """
    colors = get_theme_colors()
    
    if not alerts:
        return [html.Div("No active alerts", style={
            "font-style": "italic",
            "color": colors["text_light"],
            "text-align": "center",
            "padding": "20px"
        })]
    
    alert_cards = []
    
    for alert in alerts:
        # Determine severity color
        severity = alert.get('severity', 'medium')
        severity_colors = {
            'high': colors["danger"],
            'medium': colors["warning"],
            'low': colors["info"]
        }
        border_color = severity_colors.get(severity, colors["secondary"])
        
        # Create alert card
        card = html.Div([
            html.Div([
                html.Strong(f"{alert.get('type', 'Alert').replace('_', ' ').title()}: ", style={"color": border_color}),
                html.Span(alert.get('message', 'No details'))
            ]),
            html.Div([
                html.Small(f"Symbol: {alert.get('symbol', 'N/A')} | "),
                html.Small(f"Time: {alert.get('timestamp', datetime.now().isoformat()).split('T')[0]}")
            ], style={"margin-top": "5px", "color": colors["text_light"]})
        ], style={
            "background-color": colors["panel_bg"],
            "border-left": f"4px solid {border_color}",
            "border-radius": "5px",
            "padding": "10px",
            "margin-bottom": "10px",
            "box-shadow": "0 2px 4px rgba(0, 0, 0, 0.05)"
        })
        
        alert_cards.append(card)
    
    return alert_cards

def create_performance_metrics_table(
    strategy_names: List[str],
    metrics_list: List[Dict[str, float]]
) -> html.Table:
    """
    Create a table of performance metrics for multiple strategies.
    
    Args:
        strategy_names: List of strategy names
        metrics_list: List of metric dictionaries
        
    Returns:
        Dash Table component
    """
    colors = get_theme_colors()
    
    if not strategy_names or not metrics_list:
        return html.Div("No strategy performance data available", style={
            "font-style": "italic",
            "color": colors["text_light"],
            "text-align": "center",
            "padding": "20px"
        })
    
    # Define metrics to display
    metric_order = [
        "total_return", "annual_return", "sharpe_ratio", 
        "max_drawdown", "win_rate", "profit_factor"
    ]
    
    metric_labels = {
        "total_return": "Total Return (%)",
        "annual_return": "Annual Return (%)",
        "sharpe_ratio": "Sharpe Ratio",
        "max_drawdown": "Max Drawdown (%)",
        "win_rate": "Win Rate (%)",
        "profit_factor": "Profit Factor",
        "num_trades": "Number of Trades"
    }
    
    # Create table rows
    rows = []
    
    for metric in metric_order:
        # Create cells
        row_cells = [html.Td(metric_labels.get(metric, metric), style={
            "font-weight": "bold",
            "padding": "8px 15px",
            "border-bottom": f"1px solid {colors['border']}"
        })]
        
        # Add metrics for each strategy
        for i, strategy in enumerate(strategy_names):
            if i < len(metrics_list):
                metrics = metrics_list[i]
                value = metrics.get(metric, "N/A")
                
                # Format values
                if isinstance(value, (int, float)):
                    if metric in ["total_return", "annual_return", "max_drawdown", "win_rate"]:
                        formatted_value = f"{value:.2f}%"
                    else:
                        formatted_value = f"{value:.2f}"
                        
                    # Determine color
                    if metric == "max_drawdown":
                        color = colors["danger"] if value > 15 else colors["text"]
                    elif metric in ["total_return", "annual_return", "sharpe_ratio", "win_rate", "profit_factor"]:
                        color = colors["success"] if value > 0 else colors["danger"]
                    else:
                        color = colors["text"]
                else:
                    formatted_value = str(value)
                    color = colors["text"]
                
                # Create cell
                cell = html.Td(formatted_value, style={
                    "padding": "8px 15px",
                    "border-bottom": f"1px solid {colors['border']}",
                    "color": color,
                    "text-align": "right"
                })
            else:
                cell = html.Td("N/A", style={
                    "padding": "8px 15px",
                    "border-bottom": f"1px solid {colors['border']}",
                    "color": colors["text_light"],
                    "text-align": "right"
                })
                
            row_cells.append(cell)
        
        # Create row
        rows.append(html.Tr(row_cells))
    
    # Create table headers
    headers = [html.Th("Metric", style={
        "text-align": "left",
        "padding": "12px 15px",
        "background-color": colors["primary"],
        "color": "white"
    })]
    
    for strategy in strategy_names:
        headers.append(html.Th(strategy, style={
            "text-align": "right",
            "padding": "12px 15px",
            "background-color": colors["primary"],
            "color": "white"
        }))
    
    # Create table
    table = html.Table(
        [
            html.Thead(html.Tr(headers)),
            html.Tbody(rows)
        ],
        style={
            "width": "100%",
            "border-collapse": "collapse",
            "border": f"1px solid {colors['border']}",
            "background-color": colors["panel_bg"]
        }
    )
    
    return table

def create_settings_panel() -> html.Div:
    """
    Create a settings panel for the dashboard.
    
    Returns:
        Dash Div component with settings
    """
    colors = get_theme_colors()
    
    # Create theme selector
    theme_selector = html.Div([
        html.Label("Dashboard Theme:", style={"font-weight": "bold", "margin-bottom": "5px"}),
        dcc.RadioItems(
            id="theme-selector",
            options=[
                {"label": "Default", "value": "default"},
                {"label": "Dark", "value": "dark"},
                {"label": "Crypto", "value": "crypto"}
            ],
            value="default",
            style={"margin-bottom": "10px"}
        )
    ])
    
    # Create update interval selector
    update_selector = html.Div([
        html.Label("Update Interval:", style={"font-weight": "bold", "margin-bottom": "5px"}),
        dcc.Dropdown(
            id="update-interval-selector",
            options=[
                {"label": "30 seconds", "value": 30},
                {"label": "1 minute", "value": 60},
                {"label": "5 minutes", "value": 300},
                {"label": "15 minutes", "value": 900},
                {"label": "30 minutes", "value": 1800},
                {"label": "1 hour", "value": 3600}
            ],
            value=60,
            style={"margin-bottom": "15px"}
        )
    ])
    
    # Create symbol selector
    symbol_selector = html.Div([
        html.Label("Favorite Symbols:", style={"font-weight": "bold", "margin-bottom": "5px"}),
        dcc.Checklist(
            id="favorite-symbols",
            options=[
                {"label": "BTC/USDT", "value": "BTC/USDT"},
                {"label": "ETH/USDT", "value": "ETH/USDT"},
                {"label": "SOL/USDT", "value": "SOL/USDT"},
                {"label": "DOGE/USDT", "value": "DOGE/USDT"},
                {"label": "BNB/USDT", "value": "BNB/USDT"}
            ],
            value=["BTC/USDT", "ETH/USDT"],
            style={"margin-bottom": "15px"}
        )
    ])
    
    # Create settings panel
    panel = html.Div([
        html.H3("Dashboard Settings", style={"margin-top": "0"}),
        theme_selector,
        html.Hr(style={"margin": "15px 0", "border": "none", "border-top": f"1px solid {colors['border']}"}),
        update_selector,
        html.Hr(style={"margin": "15px 0", "border": "none", "border-top": f"1px solid {colors['border']}"}),
        symbol_selector,
        html.Hr(style={"margin": "15px 0", "border": "none", "border-top": f"1px solid {colors['border']}"}),
        html.Button(
            "Apply Settings",
            id="apply-settings-button",
            style={
                "background-color": colors["primary"],
                "color": "white",
                "border": "none",
                "padding": "10px 15px",
                "border-radius": "5px",
                "cursor": "pointer",
                "width": "100%"
            }
        )
    ], style={
        "padding": "15px",
        "border-radius": "5px",
        "background-color": colors["panel_bg"],
        "border": f"1px solid {colors['border']}",
        "margin-bottom": "20px"
    })
    
    return panel 