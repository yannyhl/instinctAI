"""
Instinct AI Trading Dashboard
----------------------------
A comprehensive dashboard for monitoring cryptocurrency markets and trading strategies.
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
from dash import html, dcc, callback, Input, Output, dash_table, ctx
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import traceback
import logging

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import project modules
import config
from dashboard.market_data_handler import get_market_data_handler
from utils.market_monitor import get_market_monitor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the data handler
data_handler = get_market_data_handler()

# Initialize the app
app = dash.Dash(
    __name__,
    title="Instinct AI Trading Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True
)

# Define layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("Instinct AI Trading Dashboard", style={"margin-bottom": "0px"}),
        html.P("Real-time market monitor and trading strategy insights", style={"margin-top": "0px"}),
        html.Div(id="last-update-time", style={"font-style": "italic", "font-size": "0.8em"}),
    ], style={"text-align": "center", "margin-bottom": "20px"}),
    
    # Market Overview Section
    html.Div([
        html.H2("Market Overview"),
        
        # Symbol selector
        html.Div([
            html.Label("Symbol:"),
            dcc.Dropdown(
                id="symbol-selector",
                options=[
                    {"label": symbol, "value": symbol}
                    for symbol in config.TRADING_CONFIG['symbols']
                ],
                value=config.TRADING_CONFIG['symbols'][0] if config.TRADING_CONFIG['symbols'] else None,
                clearable=False,
                style={"width": "200px"}
            ),
        ], style={"margin-bottom": "15px"}),
        
        # Timeframe selector
        html.Div([
            html.Label("Timeframe:"),
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
        ], style={"margin-bottom": "15px"}),
        
        # Price chart
        html.Div([
            dcc.Graph(id="price-chart", style={"height": "500px"})
        ], style={"margin-bottom": "20px"}),
        
        # Market summary cards
        html.Div([
            html.Div(id="market-summary-cards", className="row"),
        ], style={"margin-bottom": "20px"})
    ], style={"margin-bottom": "30px"}),
    
    # Volume Profile and Regime Analysis
    html.Div([
        html.Div([
            html.H3("Volume Profile"),
            dcc.Graph(id="volume-profile-chart", style={"height": "300px"})
        ], className="six columns", style={"width": "48%", "display": "inline-block"}),
        
        html.Div([
            html.H3("Regime Distribution"),
            dcc.Graph(id="regime-distribution-chart", style={"height": "300px"})
        ], className="six columns", style={"width": "48%", "display": "inline-block", "float": "right"})
    ], className="row", style={"margin-bottom": "20px"}),
    
    # Strategy Performance Section
    html.Div([
        html.H2("Strategy Performance"),
        
        # Performance metrics table
        html.Div([
            html.H3("Performance Metrics"),
            html.Div(id="performance-metrics-table")
        ], style={"margin-bottom": "20px"}),
        
        # Performance chart
        html.Div([
            dcc.Graph(id="performance-chart", style={"height": "400px"})
        ], style={"margin-bottom": "20px"}),
    ], style={"margin-bottom": "30px"}),
    
    # Market Analysis Section
    html.Div([
        html.H2("Market Analysis"),
        
        # Correlation matrix
        html.Div([
            html.H3("Asset Correlation"),
            dcc.Graph(id="correlation-matrix", style={"height": "400px"})
        ], style={"margin-bottom": "20px"}),
        
        # Alerts and events
        html.Div([
            html.H3("Alerts & Events"),
            html.Div(id="alerts-section")
        ], style={"margin-bottom": "20px"}),
    ]),
    
    # Auto-update interval
    dcc.Interval(
        id="interval-component",
        interval=60*1000,  # in milliseconds (1 minute)
        n_intervals=0
    ),
    
    # Manual refresh button
    html.Div([
        html.Button(
            "Refresh Data", 
            id="refresh-button", 
            style={
                "margin-top": "20px",
                "margin-bottom": "20px",
                "background-color": "#007BFF",
                "color": "white",
                "border": "none",
                "padding": "10px 20px",
                "cursor": "pointer"
            }
        ),
        html.Div(id="refresh-status")
    ], style={"text-align": "center"})
], style={"max-width": "1200px", "margin": "0 auto", "padding": "20px"})

# Callbacks
@callback(
    Output("price-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("symbol-selector", "value"),
     Input("timeframe-selector", "value"),
     Input("refresh-button", "n_clicks")]
)
def update_price_chart(n_intervals, symbol, timeframe, n_clicks):
    if not symbol or not timeframe:
        return go.Figure()
    
    # Get chart data
    chart_data = data_handler.get_price_chart_data(
        symbol=symbol,
        timeframe=timeframe,
        n_periods=100
    )
    
    # Create figure with secondary y-axis for volume
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add price candlestick chart on primary axis
    fig.add_trace(
        go.Candlestick(
            x=chart_data['data']['timestamps'],
            open=chart_data['data']['open'],
            high=chart_data['data']['high'],
            low=chart_data['data']['low'],
            close=chart_data['data']['close'],
            name="Price"
        ),
        secondary_y=False
    )
    
    # Add volume chart on secondary axis
    fig.add_trace(
        go.Bar(
            x=chart_data['data']['timestamps'],
            y=chart_data['data']['volume'],
            name="Volume",
            marker_color='rgba(55, 83, 109, 0.7)'
        ),
        secondary_y=True
    )
    
    # Add indicators if available
    if 'indicators' in chart_data:
        indicators = chart_data['indicators']
        
        if 'sma20' in indicators:
            fig.add_trace(
                go.Scatter(
                    x=chart_data['data']['timestamps'],
                    y=indicators['sma20'],
                    name="SMA(20)",
                    line=dict(color='blue', width=1)
                ),
                secondary_y=False
            )
        
        if 'sma50' in indicators:
            fig.add_trace(
                go.Scatter(
                    x=chart_data['data']['timestamps'],
                    y=indicators['sma50'],
                    name="SMA(50)",
                    line=dict(color='orange', width=1)
                ),
                secondary_y=False
            )
        
        if all(k in indicators for k in ['bb_upper', 'bb_middle', 'bb_lower']):
            fig.add_trace(
                go.Scatter(
                    x=chart_data['data']['timestamps'],
                    y=indicators['bb_upper'],
                    name="BB Upper",
                    line=dict(color='rgba(0, 128, 0, 0.3)', width=1),
                    showlegend=True
                ),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(
                    x=chart_data['data']['timestamps'],
                    y=indicators['bb_lower'],
                    name="BB Lower",
                    line=dict(color='rgba(0, 128, 0, 0.3)', width=1),
                    fill='tonexty',
                    fillcolor='rgba(0, 128, 0, 0.1)',
                    showlegend=True
                ),
                secondary_y=False
            )
    
    # Add current regime annotation if available
    if 'regime' in chart_data:
        regime = chart_data['regime']
        fig.add_annotation(
            x=0.02,
            y=0.98,
            xref="paper",
            yref="paper",
            text=f"Regime: {regime}",
            showarrow=False,
            font=dict(
                size=12,
                color="black"
            ),
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="gray",
            borderwidth=1,
            borderpad=4
        )
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} Price Chart ({timeframe})",
        xaxis_title="Time",
        xaxis_rangeslider_visible=False,
        height=500,
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Update y-axis labels
    fig.update_yaxes(title_text="Price", secondary_y=False)
    fig.update_yaxes(title_text="Volume", secondary_y=True)
    
    return fig

@callback(
    Output("market-summary-cards", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_market_summary_cards(n_intervals, n_clicks):
    # Get market overview data
    overview = data_handler.get_market_overview()
    
    # Create summary cards
    cards = []
    
    for symbol_data in overview['market_data']:
        symbol = symbol_data['symbol']
        price = symbol_data.get('price', 0.0)
        daily_change = symbol_data.get('daily_change', 0.0)
        regime = symbol_data.get('regime', 'unknown')
        
        # Determine color based on price change
        change_color = "green" if daily_change >= 0 else "red"
        change_icon = "▲" if daily_change >= 0 else "▼"
        
        # Create card element
        card = html.Div([
            html.H4(symbol, style={"margin-bottom": "5px"}),
            html.P(f"${price:,.2f}", style={"font-size": "1.2em", "margin-bottom": "5px"}),
            html.P([
                f"{change_icon} {abs(daily_change):.2f}%"
            ], style={"color": change_color, "margin-bottom": "5px"}),
            html.P(f"Regime: {regime}", style={"font-size": "0.8em", "margin-bottom": "0px"})
        ], style={
            "border": "1px solid #ddd",
            "border-radius": "5px",
            "padding": "10px",
            "margin": "5px",
            "width": "150px",
            "display": "inline-block",
            "text-align": "center"
        })
        
        cards.append(card)
    
    return cards

@callback(
    Output("volume-profile-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("symbol-selector", "value"),
     Input("timeframe-selector", "value"),
     Input("refresh-button", "n_clicks")]
)
def update_volume_profile_chart(n_intervals, symbol, timeframe, n_clicks):
    if not symbol or not timeframe:
        return go.Figure()
    
    # Get volume profile data
    profile_data = data_handler.get_volume_profile(
        symbol=symbol,
        timeframe=timeframe,
        n_periods=100,
        n_bins=20
    )
    
    # Create figure
    fig = go.Figure()
    
    # Add horizontal volume bars
    fig.add_trace(
        go.Bar(
            y=profile_data['price_levels'],
            x=profile_data['volumes'],
            orientation='h',
            name="Volume",
            marker=dict(
                color='rgba(55, 83, 109, 0.7)',
                line=dict(
                    color='rgba(55, 83, 109, 1.0)',
                    width=1
                )
            )
        )
    )
    
    # Add POC line
    if profile_data['poc'] is not None:
        fig.add_shape(
            type="line",
            x0=0,
            y0=profile_data['poc'],
            x1=max(profile_data['volumes']) if profile_data['volumes'] else 1,
            y1=profile_data['poc'],
            line=dict(
                color="red",
                width=2,
                dash="dash",
            )
        )
        
        fig.add_annotation(
            x=max(profile_data['volumes']) * 0.95 if profile_data['volumes'] else 0.95,
            y=profile_data['poc'],
            text="POC",
            showarrow=False,
            font=dict(
                size=10,
                color="red"
            )
        )
    
    # Add Value Area
    if profile_data['value_area'] and len(profile_data['value_area']) == 2:
        # Value Area Low
        fig.add_shape(
            type="line",
            x0=0,
            y0=profile_data['value_area'][0],
            x1=max(profile_data['volumes']) if profile_data['volumes'] else 1,
            y1=profile_data['value_area'][0],
            line=dict(
                color="green",
                width=1,
                dash="dot",
            )
        )
        
        fig.add_annotation(
            x=max(profile_data['volumes']) * 0.95 if profile_data['volumes'] else 0.95,
            y=profile_data['value_area'][0],
            text="VAL",
            showarrow=False,
            font=dict(
                size=8,
                color="green"
            )
        )
        
        # Value Area High
        fig.add_shape(
            type="line",
            x0=0,
            y0=profile_data['value_area'][1],
            x1=max(profile_data['volumes']) if profile_data['volumes'] else 1,
            y1=profile_data['value_area'][1],
            line=dict(
                color="green",
                width=1,
                dash="dot",
            )
        )
        
        fig.add_annotation(
            x=max(profile_data['volumes']) * 0.95 if profile_data['volumes'] else 0.95,
            y=profile_data['value_area'][1],
            text="VAH",
            showarrow=False,
            font=dict(
                size=8,
                color="green"
            )
        )
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} Volume Profile ({timeframe})",
        xaxis_title="Volume",
        yaxis_title="Price",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="closest"
    )
    
    return fig

@callback(
    Output("regime-distribution-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("symbol-selector", "value"),
     Input("refresh-button", "n_clicks")]
)
def update_regime_distribution_chart(n_intervals, symbol, n_clicks):
    if not symbol:
        return go.Figure()
    
    # Get regime distribution data
    regime_data = data_handler.get_regime_distribution(symbol)
    
    # Create colors for regimes
    colors = ['#2E86C1', '#28B463', '#D4AC0D', '#CB4335', '#884EA0']
    bar_colors = colors[:len(regime_data['regimes'])]
    
    # Create figure
    fig = go.Figure()
    
    # Add regime distribution bars
    fig.add_trace(
        go.Bar(
            x=regime_data['regimes'],
            y=regime_data['counts'],
            marker_color=bar_colors,
            text=regime_data['counts'],
            textposition='auto'
        )
    )
    
    # Add marker for current regime
    if regime_data['current_regime'] is not None:
        try:
            current_index = regime_data['regimes'].index(regime_data['current_regime'])
            
            fig.add_annotation(
                x=regime_data['regimes'][current_index],
                y=regime_data['counts'][current_index] + max(regime_data['counts']) * 0.1 if regime_data['counts'] else 1,
                text="Current",
                showarrow=True,
                arrowhead=1,
                arrowcolor='red',
                arrowsize=1,
                arrowwidth=2
            )
        except (ValueError, IndexError) as e:
            logger.warning(f"Error adding current regime annotation: {e}")
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} Market Regime Distribution",
        xaxis_title="Regime",
        yaxis_title="Days",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig

@callback(
    Output("performance-metrics-table", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_performance_metrics_table(n_intervals, n_clicks):
    # Get strategy performance data
    performance_data = data_handler.get_strategy_performance()
    
    if not performance_data['strategies']:
        return html.P("No strategy performance data available")
    
    # Create table rows
    rows = []
    
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
    
    for metric in metric_order:
        row_cells = [html.Td(metric_labels.get(metric, metric))]
        
        for i, strategy in enumerate(performance_data['strategies']):
            metrics = performance_data['metrics'][i]
            value = metrics.get(metric, "N/A")
            
            # Format percentages
            if isinstance(value, (int, float)) and ("return" in metric or "drawdown" in metric or "rate" in metric):
                formatted_value = f"{value:.2f}%" if value != "N/A" else "N/A"
            else:
                formatted_value = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            
            # Determine color based on metric
            if metric == "max_drawdown":
                color = "red" if isinstance(value, (int, float)) and value > 15 else "black"
            elif "return" in metric or "ratio" in metric or "factor" in metric or "rate" in metric:
                color = "green" if isinstance(value, (int, float)) and value > 0 else "red"
            else:
                color = "black"
            
            row_cells.append(html.Td(formatted_value, style={"color": color}))
        
        rows.append(html.Tr(row_cells))
    
    # Create table headers
    headers = [html.Th("Metric")] + [html.Th(strategy) for strategy in performance_data['strategies']]
    
    # Create table
    table = html.Table(
        [
            html.Thead(html.Tr(headers)),
            html.Tbody(rows)
        ],
        style={
            "width": "100%", 
            "border-collapse": "collapse", 
            "border": "1px solid #ddd"
        }
    )
    
    return table

@callback(
    Output("performance-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_performance_chart(n_intervals, n_clicks):
    # This is a placeholder - in production we would get actual strategy performance data
    # For now, simulate performance data for two strategies
    
    # Create date range
    dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
    
    # Create random cumulative performance for two strategies
    np.random.seed(42)  # For reproducibility
    strat1_returns = np.random.normal(0.001, 0.01, len(dates)).cumsum() + 1
    strat2_returns = np.random.normal(0.0015, 0.015, len(dates)).cumsum() + 1
    benchmark_returns = np.random.normal(0.0005, 0.008, len(dates)).cumsum() + 1
    
    # Create figure
    fig = go.Figure()
    
    # Add strategy performance lines
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=strat1_returns,
            name="LSTM Strategy",
            line=dict(color='blue', width=2)
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=strat2_returns,
            name="Volume Profile Strategy",
            line=dict(color='green', width=2)
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=benchmark_returns,
            name="Benchmark (BTC/USDT)",
            line=dict(color='gray', width=2, dash='dash')
        )
    )
    
    # Update layout
    fig.update_layout(
        title="Strategy Performance Comparison",
        xaxis_title="Date",
        yaxis_title="Cumulative Return",
        height=400,
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig

@callback(
    Output("correlation-matrix", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_correlation_matrix(n_intervals, n_clicks):
    # Get correlation matrix data
    matrix_data = data_handler.get_correlation_matrix()
    
    if not matrix_data.get('matrix'):
        return go.Figure()
    
    # Create figure
    fig = go.Figure()
    
    # Add heatmap
    fig.add_trace(go.Heatmap(
        z=matrix_data['matrix'],
        x=matrix_data['symbols'],
        y=matrix_data['symbols'],
        colorscale='RdBu',
        zmin=-1,
        zmax=1,
        colorbar=dict(title="Correlation")
    ))
    
    # Update layout
    fig.update_layout(
        title="Asset Correlation Matrix",
        height=400,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_showgrid=False,
        yaxis_showgrid=False,
        xaxis_zeroline=False,
        yaxis_zeroline=False
    )
    
    return fig

@callback(
    Output("alerts-section", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_alerts_section(n_intervals, n_clicks):
    # Get alerts
    alerts = data_handler.get_alerts()
    
    if not alerts:
        return html.P("No active alerts", style={"font-style": "italic"})
    
    # Create alert cards
    alert_cards = []
    
    for alert in alerts:
        # Determine severity color
        severity = alert.get('severity', 'medium')
        severity_color = {
            'high': '#F8D7DA',  # light red
            'medium': '#FFF3CD',  # light yellow
            'low': '#D1ECF1'  # light blue
        }.get(severity, '#FFF3CD')
        
        # Create alert card
        card = html.Div([
            html.Div([
                html.Strong(f"{alert.get('type', 'Alert').replace('_', ' ').title()}: "),
                html.Span(alert.get('message', 'No details'))
            ]),
            html.Div([
                html.Small(f"Symbol: {alert.get('symbol', 'N/A')} | "),
                html.Small(f"Time: {alert.get('timestamp', datetime.now().isoformat()).split('T')[0]}")
            ], style={"margin-top": "5px", "color": "#666"})
        ], style={
            "background-color": severity_color,
            "border": f"1px solid {severity_color}",
            "border-radius": "5px",
            "padding": "10px",
            "margin-bottom": "10px"
        })
        
        alert_cards.append(card)
    
    return html.Div(alert_cards)

@callback(
    Output("last-update-time", "children"),
    [Input("interval-component", "n_intervals"),
     Input("refresh-button", "n_clicks")]
)
def update_last_update_time(n_intervals, n_clicks):
    # Get the market monitor's last update time
    market_monitor = get_market_monitor()
    last_update = market_monitor.last_update_time
    
    if last_update:
        return f"Last updated: {last_update.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        return "Data not yet loaded"

@callback(
    Output("refresh-status", "children"),
    Input("refresh-button", "n_clicks")
)
def refresh_data(n_clicks):
    if not n_clicks:
        return ""
    
    try:
        # Trigger a manual data update
        success = data_handler.update_data()
        
        if success:
            return html.Div("Data refreshed successfully!", 
                         style={"color": "green", "margin-top": "10px"})
        else:
            return html.Div("Error refreshing data", 
                         style={"color": "red", "margin-top": "10px"})
                         
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return html.Div(f"Error: {str(e)}", 
                     style={"color": "red", "margin-top": "10px"})

# Run the app
if __name__ == "__main__":
    try:
        # Parse command line arguments for port and debug mode
        import argparse
        parser = argparse.ArgumentParser(description="Run the Instinct AI Trading Dashboard")
        parser.add_argument("--port", type=int, default=8050, help="Port to run the dashboard on")
        parser.add_argument("--debug", action="store_true", help="Run in debug mode")
        args = parser.parse_args()
        
        # Start the dashboard
        logger.info(f"Starting dashboard on port {args.port} (debug={args.debug})")
        app.run_server(debug=args.debug, port=args.port)
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}")
        traceback.print_exc()
    finally:
        # Make sure to stop the market monitor when the app exits
        market_monitor = get_market_monitor()
        market_monitor.stop()
    # Add strategy returns if available
    for strategy_name, metrics in data_refresher.performance.items():
        # Create a synthetic equity curve based on reported returns
        # This is just for visualization purposes
        if 'annual_return' in metrics:
            annual_return = metrics['annual_return'] / 100  # Convert from percentage
            days = (benchmark_data.index[-1] - benchmark_data.index[0]).days
            daily_return = (1 + annual_return) ** (1/365) - 1
            
            # Generate synthetic equity curve
            equity_curve = []
            for i in range(len(benchmark_data)):
                # Adjust daily return by benchmark volatility for more realistic curve
                bench_vol = abs(benchmark_returns[i]) / benchmark_returns.std() if benchmark_returns.std() > 0 else 1
                adjusted_return = daily_return * (0.5 + 0.5 * bench_vol)
                
                if i == 0:
                    equity_curve.append(1 + adjusted_return)
                else:
                    equity_curve.append(equity_curve[i-1] * (1 + adjusted_return))
            
            strategy_cum_returns = [ec - 1 for ec in equity_curve]
            
            fig.add_trace(
                go.Scatter(
                    x=benchmark_data.index,
                    y=np.array(strategy_cum_returns) * 100,  # Convert to percentage
                    name=strategy_name,
                    line=dict(width=2)
                )
            )
    
    # Update layout
    fig.update_layout(
        title="Cumulative Returns Comparison",
        xaxis_title="Date",
        yaxis_title="Cumulative Return (%)",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        legend_title="Strategy",
        hovermode="closest"
    )
    
    return fig

@callback(
    Output("drawdown-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_drawdown_chart(n):
    if not data_refresher.data:
        return go.Figure()
    
    # Create drawdown chart for the first symbol
    symbols = list(data_refresher.data.keys())
    
    if not symbols:
        return go.Figure()
    
    symbol = symbols[0]
    df = data_refresher.data[symbol]
    
    # Calculate drawdown
    returns = df['close'].pct_change().fillna(0)
    cum_returns = (1 + returns).cumprod()
    running_max = np.maximum.accumulate(cum_returns)
    drawdown = (cum_returns / running_max - 1) * 100  # Convert to percentage
    
    # Create figure
    fig = go.Figure()
    
    # Add drawdown area chart
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=drawdown,
            fill='tozeroy',
            name=f"{symbol} Drawdown",
            line=dict(color='red'),
            fillcolor='rgba(255, 0, 0, 0.3)'
        )
    )
    
    # Update layout
    fig.update_layout(
        title="Market Drawdown",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        legend_title="Symbol",
        hovermode="closest"
    )
    
    return fig

@callback(
    Output("rolling-metrics-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_rolling_metrics_chart(n):
    if not data_refresher.data:
        return go.Figure()
    
    # Create rolling metrics chart for the first symbol
    symbols = list(data_refresher.data.keys())
    
    if not symbols:
        return go.Figure()
    
    symbol = symbols[0]
    df = data_refresher.data[symbol]
    
    # Calculate rolling metrics
    window = min(30, len(df) // 2)  # 30-day window or half the data
    returns = df['close'].pct_change().fillna(0)
    
    rolling_return = returns.rolling(window=window).mean() * window * 100  # Scaled to percentage
    rolling_vol = returns.rolling(window=window).std() * np.sqrt(window) * 100  # Scaled to percentage
    rolling_sharpe = rolling_return / rolling_vol if not rolling_vol.empty and rolling_vol.mean() > 0 else pd.Series(0, index=returns.index)
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add rolling return
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=rolling_return,
            name="Rolling Return",
            line=dict(color='green', width=2)
        ),
        secondary_y=False,
    )
    
    # Add rolling volatility
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=rolling_vol,
            name="Rolling Volatility",
            line=dict(color='red', width=2)
        ),
        secondary_y=False,
    )
    
    # Add rolling Sharpe ratio
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=rolling_sharpe,
            name="Rolling Sharpe",
            line=dict(color='blue', width=2)
        ),
        secondary_y=True,
    )
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} Rolling Metrics ({window}-day window)",
        xaxis_title="Date",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        legend_title="Metric",
        hovermode="closest"
    )
    
    # Update y-axis labels
    fig.update_yaxes(title_text="Return/Volatility (%)", secondary_y=False)
    fig.update_yaxes(title_text="Sharpe Ratio", secondary_y=True)
    
    return fig

@callback(
    Output("risk-metrics-table", "children"),
    Input("interval-component", "n_intervals")
)
def update_risk_metrics_table(n):
    if not data_refresher.data:
        return html.P("No data available")
    
    # Calculate risk metrics for each symbol
    risk_metrics = {}
    
    for symbol, df in data_refresher.data.items():
        returns = df['close'].pct_change().dropna()
        
        if len(returns) < 10:
            continue
        
        # Calculate basic risk metrics
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized, in percentage
        
        # Calculate drawdown
        cum_returns = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (cum_returns / running_max - 1) * 100  # In percentage
        max_drawdown = drawdown.min()
        
        # Calculate VaR and CVaR (95%)
        var_95 = np.percentile(returns, 5) * 100  # Daily VaR at 95% confidence, in percentage
        cvar_95 = returns[returns <= var_95 / 100].mean() * 100  # Daily CVaR, in percentage
        
        # Store metrics
        risk_metrics[symbol] = {
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "worst_day": returns.min() * 100,  # In percentage
            "best_day": returns.max() * 100    # In percentage
        }
    
    if not risk_metrics:
        return html.P("Not enough data to calculate risk metrics")
    
    # Create table rows
    rows = []
    
    metric_labels = {
        "volatility": "Volatility (Annual %)",
        "max_drawdown": "Maximum Drawdown (%)",
        "var_95": "Daily VaR (95%)",
        "cvar_95": "Daily CVaR (95%)",
        "worst_day": "Worst Daily Return (%)",
        "best_day": "Best Daily Return (%)"
    }
    
    for metric, label in metric_labels.items():
        row_cells = [html.Td(label)]
        
        for symbol in risk_metrics.keys():
            value = risk_metrics[symbol].get(metric, "N/A")
            
            # Format value
            if isinstance(value, (int, float)):
                formatted_value = f"{value:.2f}%"
                
                # Determine color based on metric
                if metric in ["max_drawdown", "var_95", "cvar_95", "worst_day"]:
                    color = "red"
                elif metric in ["best_day"]:
                    color = "green"
                else:
                    color = "black"
            else:
                formatted_value = str(value)
                color = "black"
            
            row_cells.append(html.Td(formatted_value, style={"color": color}))
        
        rows.append(html.Tr(row_cells))
    
    # Create table headers
    headers = [html.Th("Metric")] + [html.Th(symbol) for symbol in risk_metrics.keys()]
    
    # Create table
    table = html.Table(
        [
            html.Thead(html.Tr(headers)),
            html.Tbody(rows)
        ],
        style={"width": "100%", "border-collapse": "collapse"}
    )
    
    return table

@callback(
    Output("var-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_var_chart(n):
    if not data_refresher.data:
        return go.Figure()
    
    # Create VaR chart for the first symbol
    symbols = list(data_refresher.data.keys())
    
    if not symbols:
        return go.Figure()
    
    symbol = symbols[0]
    df = data_refresher.data[symbol]
    
    # Calculate returns
    returns = df['close'].pct_change().dropna() * 100  # In percentage
    
    # Create histogram for returns distribution
    fig = go.Figure()
    
    # Add histogram
    fig.add_trace(
        go.Histogram(
            x=returns,
            nbinsx=30,
            name="Returns Distribution",
            marker_color='rgba(55, 83, 109, 0.7)'
        )
    )
    
    # Calculate VaR at different confidence levels
    var_95 = np.percentile(returns, 5)
    var_99 = np.percentile(returns, 1)
    
    # Add VaR lines
    fig.add_vline(
        x=var_95,
        line_dash="dash",
        line_color="red",
        annotation_text="95% VaR",
        annotation_position="top right"
    )
    
    fig.add_vline(
        x=var_99,
        line_dash="dash",
        line_color="darkred",
        annotation_text="99% VaR",
        annotation_position="top right"
    )
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} Returns Distribution and VaR",
        xaxis_title="Daily Return (%)",
        yaxis_title="Frequency",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        legend_title="Legend",
        hovermode="closest"
    )
    
    return fig

@callback(
    Output("correlation-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_correlation_chart(n):
    if not data_refresher.data or len(data_refresher.data) < 2:
        return go.Figure()
    
    # Calculate returns for all symbols
    returns_data = {}
    
    for symbol, df in data_refresher.data.items():
        returns = df['close'].pct_change().dropna()
        returns_data[symbol] = returns
    
    # Create returns DataFrame
    returns_df = pd.DataFrame(returns_data)
    
    # Calculate correlation matrix
    corr_matrix = returns_df.corr()
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.index,
        colorscale='RdBu',
        zmin=-1,
        zmax=1,
        colorbar=dict(title="Correlation")
    ))
    
    # Update layout
    fig.update_layout(
        title="Asset Correlation Matrix",
        height=400,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_showgrid=False,
        yaxis_showgrid=False,
        xaxis_zeroline=False,
        yaxis_zeroline=False
    )
    
    return fig

@callback(
    Output("last-update-time", "children"),
    Input("interval-component", "n_intervals")
)
def update_last_update_time(n):
    if data_refresher.last_update:
        return f"Last updated: {data_refresher.last_update.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        return "Data not yet loaded"

# Run the app
if __name__ == "__main__":
    try:
        app.run_server(debug=True, port=8050)
    finally:
        # Make sure to stop the data refresher thread when the app exits
        data_refresher.stop() 