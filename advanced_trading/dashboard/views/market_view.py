"""
Market View

This module provides the market view for the dashboard.
"""

import os
import sys
import logging
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

# Import services
from dashboard.services import market_service

# Import components
from dashboard.components.status_card import create_status_card, create_metric_card

# Configure logging
logger = log_manager.get_logger(__name__, {"component": "dashboard.views.market_view"})


def create_market_view():
    """
    Create the market view.
    
    Returns:
        Market view layout
    """
    # Get supported symbols
    symbols = market_service.get_supported_symbols()
    default_symbol = symbols[0] if symbols else "BTC/USD"
    
    # Create layout
    layout = html.Div([
        # Title and description
        html.H2("Market View"),
        html.P("Monitor real-time market data and price movements."),
        
        # Market summary section
        html.Div([
            html.H4("Market Summary", className="mb-3"),
            dbc.Row([
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H5("Market Cap", className="card-title"),
                            html.Div(id="market-cap", className="display-4"),
                            html.Div(id="market-cap-change", className="text-muted"),
                        ]),
                        className="shadow-sm"
                    ),
                    width=3
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H5("24h Volume", className="card-title"),
                            html.Div(id="market-volume", className="display-4"),
                            html.Div(id="market-volume-change", className="text-muted"),
                        ]),
                        className="shadow-sm"
                    ),
                    width=3
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H5("BTC Dominance", className="card-title"),
                            html.Div(id="btc-dominance", className="display-4"),
                            html.Div(id="btc-dominance-change", className="text-muted"),
                        ]),
                        className="shadow-sm"
                    ),
                    width=3
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H5("Fear & Greed", className="card-title"),
                            html.Div(id="fear-greed", className="display-4"),
                            html.Div(id="fear-greed-label", className="text-muted"),
                        ]),
                        className="shadow-sm"
                    ),
                    width=3
                ),
            ], className="mb-4"),
        ]),
        
        # Symbol selection and chart section
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.H4("Price Charts", className="mb-3"),
                    # Symbol selector
                    dbc.FormGroup([
                        dbc.Label("Symbol"),
                        dcc.Dropdown(
                            id="symbol-selector",
                            options=[{"label": s, "value": s} for s in symbols],
                            value=default_symbol,
                            clearable=False
                        )
                    ]),
                    # Timeframe selector
                    dbc.FormGroup([
                        dbc.Label("Timeframe"),
                        dbc.ButtonGroup([
                            dbc.Button("1m", id="btn-timeframe-1m", color="outline-primary", size="sm", n_clicks=0),
                            dbc.Button("5m", id="btn-timeframe-5m", color="outline-primary", size="sm", n_clicks=0),
                            dbc.Button("15m", id="btn-timeframe-15m", color="outline-primary", size="sm", n_clicks=0),
                            dbc.Button("1h", id="btn-timeframe-1h", color="primary", size="sm", n_clicks=1),
                            dbc.Button("4h", id="btn-timeframe-4h", color="outline-primary", size="sm", n_clicks=0),
                            dbc.Button("1d", id="btn-timeframe-1d", color="outline-primary", size="sm", n_clicks=0),
                        ]),
                        dcc.Store(id="current-timeframe", data="1h")
                    ]),
                ]),
            ]),
            
            # Main chart
            dbc.Row([
                dbc.Col([
                    dcc.Graph(
                        id="price-chart",
                        style={"height": "500px"},
                        figure={"layout": {"title": "Loading..."}}
                    )
                ]),
            ], className="mb-4"),
        ]),
        
        # Market info sections
        dbc.Row([
            # Left column
            dbc.Col([
                html.H4("Symbol Information"),
                html.Div(id="symbol-info", className="mb-4"),
                
                html.H4("Recent Trades"),
                html.Div(id="recent-trades", className="mb-4")
            ], width=6),
            
            # Right column
            dbc.Col([
                html.H4("Order Book"),
                html.Div(id="order-book", className="mb-4"),
                
                html.H4("Technical Indicators"),
                html.Div(id="technical-indicators", className="mb-4")
            ], width=6)
        ]),
        
        # Refresh interval
        dcc.Interval(
            id="market-refresh-interval",
            interval=5000,  # 5 seconds
            n_intervals=0
        )
    ])
    
    return layout


def format_price(value, currency="$"):
    """Format price with appropriate decimal places"""
    if value >= 1000:
        return f"{currency}{value:,.2f}"
    elif value >= 100:
        return f"{currency}{value:.2f}"
    elif value >= 10:
        return f"{currency}{value:.3f}"
    elif value >= 1:
        return f"{currency}{value:.4f}"
    else:
        return f"{currency}{value:.6f}"


def create_price_chart(symbol, timeframe="1h"):
    """Create a price chart for the specified symbol"""
    # Get OHLCV data
    ohlcv_data = market_service.get_ohlcv(symbol, timeframe)
    
    if not ohlcv_data:
        return go.Figure().update_layout(title=f"No data available for {symbol}")
    
    # Create DataFrame
    df = pd.DataFrame(ohlcv_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Create candlestick chart
    fig = go.Figure(data=[go.Candlestick(
        x=df["timestamp"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="OHLC"
    )])
    
    # Add volume as a bar chart
    fig.add_trace(go.Bar(
        x=df["timestamp"],
        y=df["volume"],
        name="Volume",
        marker_color="rgba(0, 0, 255, 0.3)",
        opacity=0.5,
        yaxis="y2"
    ))
    
    # Customize layout
    fig.update_layout(
        title=f"{symbol} ({timeframe.upper()})",
        xaxis_title="Time",
        yaxis_title="Price",
        yaxis2=dict(
            title="Volume",
            overlaying="y",
            side="right",
            showgrid=False
        ),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500
    )
    
    return fig


def register_callbacks(app):
    """
    Register callbacks for the market view.
    
    Args:
        app: Dash application
    """
    # Callback to update market summary
    @app.callback(
        [
            Output("market-cap", "children"),
            Output("market-cap-change", "children"),
            Output("market-volume", "children"),
            Output("market-volume-change", "children"),
            Output("btc-dominance", "children"),
            Output("btc-dominance-change", "children"),
            Output("fear-greed", "children"),
            Output("fear-greed-label", "children")
        ],
        Input("market-refresh-interval", "n_intervals")
    )
    def update_market_summary(n_intervals):
        """Update market summary information"""
        # Get market summary
        summary = market_service.get_market_summary()
        
        # Format data
        market_cap = f"${summary['global']['total_market_cap'] / 1e9:.1f}B"
        market_cap_change = "24h Change: +2.5%"  # Placeholder
        
        market_volume = f"${summary['global']['total_volume_24h'] / 1e9:.1f}B"
        market_volume_change = "24h Change: +5.1%"  # Placeholder
        
        btc_dominance = f"{summary['global']['btc_dominance']:.1f}%"
        btc_dominance_change = "24h Change: -0.3%"  # Placeholder
        
        # Get sentiment data
        sentiment = market_service.get_market_sentiment()
        fear_greed = f"{sentiment['fear_greed_index']}"
        fear_greed_label = sentiment['fear_greed_value']
        
        return market_cap, market_cap_change, market_volume, market_volume_change, btc_dominance, btc_dominance_change, fear_greed, fear_greed_label
    
    # Callback to update price chart
    @app.callback(
        Output("price-chart", "figure"),
        [
            Input("symbol-selector", "value"),
            Input("current-timeframe", "data"),
            Input("market-refresh-interval", "n_intervals")
        ]
    )
    def update_price_chart(symbol, timeframe, n_intervals):
        """Update the price chart"""
        return create_price_chart(symbol, timeframe)
    
    # Callback to update symbol information
    @app.callback(
        Output("symbol-info", "children"),
        [
            Input("symbol-selector", "value"),
            Input("market-refresh-interval", "n_intervals")
        ]
    )
    def update_symbol_info(symbol, n_intervals):
        """Update symbol information"""
        # Get market summary
        summary = market_service.get_market_summary()
        
        # Get symbol data
        if symbol in summary["symbols"]:
            symbol_data = summary["symbols"][symbol]
            
            # Create information card
            info_card = dbc.Card(
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H5("Current Price"),
                            html.P(format_price(symbol_data["price"]), className="lead")
                        ], width=4),
                        dbc.Col([
                            html.H5("24h Change"),
                            html.P(
                                f"{symbol_data['change_24h']:+.2f}%", 
                                className=f"lead {'text-success' if symbol_data['change_24h'] >= 0 else 'text-danger'}"
                            )
                        ], width=4),
                        dbc.Col([
                            html.H5("24h Volume"),
                            html.P(f"${symbol_data['volume_24h']:,.2f}", className="lead")
                        ], width=4)
                    ]),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([
                            html.H5("24h High"),
                            html.P(format_price(symbol_data["high_24h"]), className="lead")
                        ], width=4),
                        dbc.Col([
                            html.H5("24h Low"),
                            html.P(format_price(symbol_data["low_24h"]), className="lead")
                        ], width=4),
                        dbc.Col([
                            dbc.Button("Add to Watchlist", color="primary", className="mt-3")
                        ], width=4)
                    ])
                ])
            )
            
            return info_card
        
        return html.Div("Symbol information not available")
    
    # Callback to update order book
    @app.callback(
        Output("order-book", "children"),
        [
            Input("symbol-selector", "value"),
            Input("market-refresh-interval", "n_intervals")
        ]
    )
    def update_order_book(symbol, n_intervals):
        """Update order book"""
        # Get order book
        orderbook = market_service.get_orderbook(symbol)
        
        # Format the order book
        bids = orderbook["bids"][:5]  # Top 5 bids
        asks = orderbook["asks"][:5]  # Top 5 asks
        
        # Create tables
        bid_rows = [
            html.Tr([
                html.Td(format_price(bid[0]), className="text-success"),
                html.Td(f"{bid[1]:.6f}"),
                html.Td(f"{bid[0] * bid[1]:.2f}")
            ]) for bid in bids
        ]
        
        ask_rows = [
            html.Tr([
                html.Td(format_price(ask[0]), className="text-danger"),
                html.Td(f"{ask[1]:.6f}"),
                html.Td(f"{ask[0] * ask[1]:.2f}")
            ]) for ask in asks
        ]
        
        # Create order book card
        orderbook_card = dbc.Card(
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H5("Bids"),
                        dbc.Table(
                            [
                                html.Thead(
                                    html.Tr([
                                        html.Th("Price"),
                                        html.Th("Amount"),
                                        html.Th("Total")
                                    ])
                                ),
                                html.Tbody(bid_rows)
                            ],
                            size="sm",
                            bordered=False
                        )
                    ], width=6),
                    dbc.Col([
                        html.H5("Asks"),
                        dbc.Table(
                            [
                                html.Thead(
                                    html.Tr([
                                        html.Th("Price"),
                                        html.Th("Amount"),
                                        html.Th("Total")
                                    ])
                                ),
                                html.Tbody(ask_rows)
                            ],
                            size="sm",
                            bordered=False
                        )
                    ], width=6)
                ])
            ])
        )
        
        return orderbook_card
    
    # Callback to update recent trades
    @app.callback(
        Output("recent-trades", "children"),
        [
            Input("symbol-selector", "value"),
            Input("market-refresh-interval", "n_intervals")
        ]
    )
    def update_recent_trades(symbol, n_intervals):
        """Update recent trades"""
        # Get recent trades
        trades = market_service.get_recent_trades(symbol, limit=8)
        
        # Format trades
        trade_rows = []
        for trade in trades:
            side_class = "text-success" if trade["side"] == "buy" else "text-danger"
            
            trade_rows.append(
                html.Tr([
                    html.Td(trade["timestamp"].split("T")[1].split(".")[0]),
                    html.Td(format_price(trade["price"]), className=side_class),
                    html.Td(f"{trade['quantity']:.6f}"),
                    html.Td(f"{trade['price'] * trade['quantity']:.2f}")
                ])
            )
        
        # Create trades card
        trades_card = dbc.Card(
            dbc.CardBody([
                dbc.Table(
                    [
                        html.Thead(
                            html.Tr([
                                html.Th("Time"),
                                html.Th("Price"),
                                html.Th("Amount"),
                                html.Th("Total")
                            ])
                        ),
                        html.Tbody(trade_rows)
                    ],
                    size="sm",
                    bordered=False
                )
            ])
        )
        
        return trades_card
    
    # Callback to update technical indicators
    @app.callback(
        Output("technical-indicators", "children"),
        [
            Input("symbol-selector", "value"),
            Input("market-refresh-interval", "n_intervals")
        ]
    )
    def update_technical_indicators(symbol, n_intervals):
        """Update technical indicators"""
        # Get indicators
        indicators = market_service.get_indicators(symbol)
        
        if not indicators:
            return html.Div("Indicators not available")
        
        # Create indicator cards
        indicator_cards = dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("SMA 20", className="card-title"),
                html.P(f"{indicators['sma20']:.2f}", className="lead")
            ]), className="mb-3"), width=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("EMA 20", className="card-title"),
                html.P(f"{indicators['ema20']:.2f}", className="lead")
            ]), className="mb-3"), width=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("RSI", className="card-title"),
                html.P([
                    f"{indicators['rsi']:.1f}",
                    html.Small(
                        " (Oversold)" if indicators['rsi'] < 30 else " (Overbought)" if indicators['rsi'] > 70 else "",
                        className="text-danger" if indicators['rsi'] < 30 or indicators['rsi'] > 70 else ""
                    )
                ], className="lead")
            ]), className="mb-3"), width=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Signal", className="card-title"),
                html.P([
                    html.Span(
                        "BUY" if indicators['rsi'] < 30 else "SELL" if indicators['rsi'] > 70 else "NEUTRAL",
                        className=f"lead {'text-success' if indicators['rsi'] < 30 else 'text-danger' if indicators['rsi'] > 70 else 'text-secondary'}"
                    )
                ])
            ]), className="mb-3"), width=6)
        ])
        
        return indicator_cards
    
    # Callback to update timeframe
    @app.callback(
        [
            Output("current-timeframe", "data"),
            Output("btn-timeframe-1m", "color"),
            Output("btn-timeframe-5m", "color"),
            Output("btn-timeframe-15m", "color"),
            Output("btn-timeframe-1h", "color"),
            Output("btn-timeframe-4h", "color"),
            Output("btn-timeframe-1d", "color"),
        ],
        [
            Input("btn-timeframe-1m", "n_clicks"),
            Input("btn-timeframe-5m", "n_clicks"),
            Input("btn-timeframe-15m", "n_clicks"),
            Input("btn-timeframe-1h", "n_clicks"),
            Input("btn-timeframe-4h", "n_clicks"),
            Input("btn-timeframe-1d", "n_clicks"),
        ]
    )
    def update_timeframe(n_1m, n_5m, n_15m, n_1h, n_4h, n_1d):
        """Update the selected timeframe"""
        ctx = dash.callback_context
        
        if not ctx.triggered:
            # Default timeframe
            return "1h", "outline-primary", "outline-primary", "outline-primary", "primary", "outline-primary", "outline-primary"
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        # Set colors based on selected timeframe
        colors = ["outline-primary"] * 6
        
        if button_id == "btn-timeframe-1m":
            timeframe = "1m"
            colors[0] = "primary"
        elif button_id == "btn-timeframe-5m":
            timeframe = "5m"
            colors[1] = "primary"
        elif button_id == "btn-timeframe-15m":
            timeframe = "15m"
            colors[2] = "primary"
        elif button_id == "btn-timeframe-1h":
            timeframe = "1h"
            colors[3] = "primary"
        elif button_id == "btn-timeframe-4h":
            timeframe = "4h"
            colors[4] = "primary"
        elif button_id == "btn-timeframe-1d":
            timeframe = "1d"
            colors[5] = "primary"
        else:
            timeframe = "1h"
            colors[3] = "primary"
        
        return timeframe, *colors 