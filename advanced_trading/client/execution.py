"""
Execution Client

This module provides a client for the execution API.
"""

from typing import Dict, Any, Optional, List


class ExecutionClient:
    """Execution API client."""
    
    def __init__(self, api_client):
        """
        Initialize execution client.
        
        Args:
            api_client: API client.
        """
        self.api_client = api_client
    
    def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "gtc",
        client_order_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new order.
        
        Args:
            symbol: Symbol to trade.
            side: Order side (buy, sell).
            type: Order type (market, limit, stop, stop_limit, trailing_stop).
            quantity: Order quantity.
            price: Order price (required for limit and stop_limit orders).
            stop_price: Stop price (required for stop and stop_limit orders).
            time_in_force: Time in force (gtc, ioc, fok, day, gtd).
            client_order_id: Client order ID.
            strategy_id: Strategy ID.
            
        Returns:
            Created order information.
        """
        data = {
            "symbol": symbol,
            "side": side,
            "type": type,
            "quantity": quantity,
            "time_in_force": time_in_force
        }
        
        if price is not None:
            data["price"] = price
            
        if stop_price is not None:
            data["stop_price"] = stop_price
            
        if client_order_id:
            data["client_order_id"] = client_order_id
            
        if strategy_id:
            data["strategy_id"] = strategy_id
        
        return self.api_client.post("execution/orders", data=data)
    
    def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        side: Optional[str] = None,
        strategy_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get a list of orders.
        
        Args:
            symbol: Filter by symbol.
            status: Filter by status.
            side: Filter by side.
            strategy_id: Filter by strategy ID.
            limit: Maximum number of orders to return.
            offset: Number of orders to skip.
            
        Returns:
            List of orders.
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if symbol:
            params["symbol"] = symbol
            
        if status:
            params["status"] = status
            
        if side:
            params["side"] = side
            
        if strategy_id:
            params["strategy_id"] = strategy_id
        
        return self.api_client.get("execution/orders", params=params)
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get a specific order by ID.
        
        Args:
            order_id: Order ID.
            
        Returns:
            Order information.
        """
        return self.api_client.get(f"execution/orders/{order_id}")
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID.
            
        Returns:
            Canceled order information.
        """
        return self.api_client.delete(f"execution/orders/{order_id}")
    
    def get_order_fills(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get fills for a specific order.
        
        Args:
            order_id: Order ID.
            
        Returns:
            List of fills.
        """
        return self.api_client.get(f"execution/orders/{order_id}/fills")
    
    # Convenience methods for common order types
    
    def market_buy(
        self,
        symbol: str,
        quantity: float,
        client_order_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a market buy order.
        
        Args:
            symbol: Symbol to trade.
            quantity: Order quantity.
            client_order_id: Client order ID.
            strategy_id: Strategy ID.
            
        Returns:
            Created order information.
        """
        return self.create_order(
            symbol=symbol,
            side="buy",
            type="market",
            quantity=quantity,
            client_order_id=client_order_id,
            strategy_id=strategy_id
        )
    
    def market_sell(
        self,
        symbol: str,
        quantity: float,
        client_order_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a market sell order.
        
        Args:
            symbol: Symbol to trade.
            quantity: Order quantity.
            client_order_id: Client order ID.
            strategy_id: Strategy ID.
            
        Returns:
            Created order information.
        """
        return self.create_order(
            symbol=symbol,
            side="sell",
            type="market",
            quantity=quantity,
            client_order_id=client_order_id,
            strategy_id=strategy_id
        )
    
    def limit_buy(
        self,
        symbol: str,
        quantity: float,
        price: float,
        time_in_force: str = "gtc",
        client_order_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a limit buy order.
        
        Args:
            symbol: Symbol to trade.
            quantity: Order quantity.
            price: Order price.
            time_in_force: Time in force (gtc, ioc, fok, day, gtd).
            client_order_id: Client order ID.
            strategy_id: Strategy ID.
            
        Returns:
            Created order information.
        """
        return self.create_order(
            symbol=symbol,
            side="buy",
            type="limit",
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            strategy_id=strategy_id
        )
    
    def limit_sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        time_in_force: str = "gtc",
        client_order_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a limit sell order.
        
        Args:
            symbol: Symbol to trade.
            quantity: Order quantity.
            price: Order price.
            time_in_force: Time in force (gtc, ioc, fok, day, gtd).
            client_order_id: Client order ID.
            strategy_id: Strategy ID.
            
        Returns:
            Created order information.
        """
        return self.create_order(
            symbol=symbol,
            side="sell",
            type="limit",
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            strategy_id=strategy_id
        ) 