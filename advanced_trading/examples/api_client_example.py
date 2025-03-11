#!/usr/bin/env python
"""
API Client Example

This script demonstrates how to use the Instinct AI client SDK.
"""

import logging
import asyncio
import time
from datetime import datetime, timedelta

from advanced_trading.client import ApiClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_client_example")


async def main():
    """Run API client example."""
    # Create API client
    client = ApiClient(
        base_url="http://localhost:8000",
        api_version="v1"
    )
    
    # Initialize all clients
    client._initialize_clients()
    
    # 1. Authentication Example
    logger.info("1. Authentication Example")
    
    try:
        # Log in
        login_response = client.auth.login(
            username="test",
            password="password"
        )
        logger.info(f"Logged in as: {login_response['username']}")
        logger.info(f"Token expires in: {login_response['expires_in']} seconds")
        
        # Get current user
        user = client.auth.get_current_user()
        logger.info(f"Current user: {user['username']}")
        
        # Create API key
        # Note: This requires admin permissions in a real system
        api_key_response = client.auth.create_api_key(user["id"])
        logger.info(f"Created API key: {api_key_response['api_key']}")
        
        # Revoke API key
        client.auth.revoke_api_key(api_key_response["api_key"])
        logger.info("Revoked API key")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
    
    # 2. Strategies Example
    logger.info("\n2. Strategies Example")
    
    try:
        # Get available strategies
        strategies = client.strategies.get_available_strategies()
        logger.info(f"Available strategies: {len(strategies)}")
        for strategy in strategies:
            logger.info(f"  - {strategy['name']}: {strategy['description']}")
        
        # Create a strategy
        strategy = client.strategies.create_strategy(
            name="Test Strategy",
            type="trend_following",
            symbols=["BTC/USD"],
            timeframe="1h",
            parameters={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            },
            risk_limits={
                "max_position_size": 0.1,
                "max_drawdown": 0.1
            },
            description="Test strategy for API client example"
        )
        logger.info(f"Created strategy: {strategy['id']}")
        
        # Get strategy details
        strategy_details = client.strategies.get_strategy(strategy["id"])
        logger.info(f"Strategy state: {strategy_details['state']}")
        
        # Start strategy
        start_result = client.strategies.start_strategy(strategy["id"])
        logger.info(f"Started strategy: {start_result['success']}")
        
        # Stop strategy
        stop_result = client.strategies.stop_strategy(strategy["id"])
        logger.info(f"Stopped strategy: {stop_result['success']}")
        
        # Delete strategy
        client.strategies.delete_strategy(strategy["id"])
        logger.info("Deleted strategy")
    except Exception as e:
        logger.error(f"Strategies error: {e}")
    
    # 3. Data Example
    logger.info("\n3. Data Example")
    
    try:
        # Get data sources
        sources = client.data.get_data_sources()
        logger.info(f"Available data sources: {len(sources)}")
        for source in sources:
            logger.info(f"  - {source['name']}: {source['description']}")
        
        # Get data source details
        source = client.data.get_data_source(sources[0]["id"])
        logger.info(f"Data source: {source['name']}")
        logger.info(f"Available symbols: {', '.join(source['symbols'])}")
        
        # Get time series data
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        
        data = client.data.get_time_series_data(
            source_id=source["id"],
            symbol=source["symbols"][0],
            start_time=start_time,
            end_time=end_time,
            frequency="1h"
        )
        logger.info(f"Retrieved {len(data)} data points")
        if data:
            logger.info(f"First data point: {data[0]['timestamp']}, Close: {data[0]['close']}")
            logger.info(f"Last data point: {data[-1]['timestamp']}, Close: {data[-1]['close']}")
    except Exception as e:
        logger.error(f"Data error: {e}")
    
    # 4. Execution Example
    logger.info("\n4. Execution Example")
    
    try:
        # Create a market order
        order = client.execution.market_buy(
            symbol="BTC/USD",
            quantity=0.1
        )
        logger.info(f"Created order: {order['id']}")
        logger.info(f"Order status: {order['status']}")
        
        # Get order details
        order_details = client.execution.get_order(order["id"])
        logger.info(f"Order details: {order_details['status']}")
        
        # Cancel order if not filled
        if order_details["status"] not in ["filled", "canceled"]:
            canceled_order = client.execution.cancel_order(order["id"])
            logger.info(f"Canceled order: {canceled_order['status']}")
        
        # Get order fills
        fills = client.execution.get_order_fills(order["id"])
        logger.info(f"Order fills: {len(fills)}")
    except Exception as e:
        logger.error(f"Execution error: {e}")
    
    # 5. Backtest Example
    logger.info("\n5. Backtest Example")
    
    try:
        # Create a new backtest
        backtest = client.backtest.create_backtest(
            strategy_id="test-strategy",  # This would be a real strategy ID in production
            start_date=datetime(2022, 1, 1),
            end_date=datetime(2022, 12, 31),
            symbols=["BTC/USD"],
            initial_capital=100000.0,
            parameters={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            },
            description="Test backtest for API client example"
        )
        logger.info(f"Created backtest: {backtest['id']}")
        
        # Get backtest details
        backtest_details = client.backtest.get_backtest(backtest["id"])
        logger.info(f"Backtest status: {backtest_details['status']}")
        
        # Wait for backtest to complete (in a real scenario)
        logger.info("Waiting for backtest to complete...")
        for _ in range(5):  # Poll a few times
            time.sleep(1)  # Wait a bit
            backtest_details = client.backtest.get_backtest(backtest["id"])
            logger.info(f"Backtest status: {backtest_details['status']}")
            if backtest_details["status"] in ["completed", "failed", "cancelled"]:
                break
        
        # Cancel backtest if still running
        if backtest_details["status"] not in ["completed", "failed", "cancelled"]:
            client.backtest.cancel_backtest(backtest["id"])
            logger.info("Cancelled backtest")
    except Exception as e:
        logger.error(f"Backtest error: {e}")
    
    # 6. WebSocket Example
    logger.info("\n6. WebSocket Example")
    
    try:
        # Create WebSocket connection
        ws = client.create_websocket_connection(authenticated=True)
        
        # Define custom message handler
        def on_message(ws, message):
            logger.info(f"WebSocket message: {message}")
        
        # Override message handler
        ws.on_message = on_message
        
        # Start connection in a separate thread
        import threading
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        logger.info("WebSocket connection started")
        
        # Wait a bit for the connection to establish
        time.sleep(2)
        
        # Close WebSocket connection
        ws.close()
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 