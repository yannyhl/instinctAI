"""
Backtest Client

This module provides a client for the backtest API.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List


class BacktestClient:
    """Backtest API client."""
    
    def __init__(self, api_client):
        """
        Initialize backtest client.
        
        Args:
            api_client: API client.
        """
        self.api_client = api_client
    
    def create_backtest(
        self,
        strategy_id: str,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        initial_capital: float,
        parameters: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new backtest.
        
        Args:
            strategy_id: Strategy ID to backtest.
            start_date: Start date for the backtest.
            end_date: End date for the backtest.
            symbols: Symbols to include in the backtest.
            initial_capital: Initial capital for the backtest.
            parameters: Override strategy parameters for the backtest.
            description: Backtest description.
            tags: Backtest tags.
            
        Returns:
            Created backtest information.
        """
        data = {
            "strategy_id": strategy_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": symbols,
            "initial_capital": initial_capital,
            "parameters": parameters or {}
        }
        
        if description:
            data["description"] = description
            
        if tags:
            data["tags"] = tags
        
        return self.api_client.post("backtest", data=data)
    
    def get_backtests(
        self,
        strategy_id: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get a list of backtests.
        
        Args:
            strategy_id: Filter by strategy ID.
            status: Filter by status.
            tag: Filter by tag.
            limit: Maximum number of backtests to return.
            offset: Number of backtests to skip.
            
        Returns:
            List of backtests.
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if strategy_id:
            params["strategy_id"] = strategy_id
            
        if status:
            params["status"] = status
            
        if tag:
            params["tag"] = tag
        
        return self.api_client.get("backtest", params=params)
    
    def get_backtest(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get a specific backtest by ID.
        
        Args:
            backtest_id: Backtest ID.
            
        Returns:
            Backtest information.
        """
        return self.api_client.get(f"backtest/{backtest_id}")
    
    def cancel_backtest(self, backtest_id: str) -> None:
        """
        Cancel a backtest.
        
        Args:
            backtest_id: Backtest ID.
        """
        self.api_client.delete(f"backtest/{backtest_id}") 