"""
Strategies Client

This module provides a client for the strategies API.
"""

from typing import Dict, Any, Optional, List


class StrategiesClient:
    """Strategies API client."""
    
    def __init__(self, api_client):
        """
        Initialize strategies client.
        
        Args:
            api_client: API client.
        """
        self.api_client = api_client
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """
        Get available strategy definitions.
        
        Returns:
            List of available strategy definitions.
        """
        return self.api_client.get("strategies/available")
    
    def create_strategy(
        self,
        name: str,
        type: str,
        symbols: List[str],
        timeframe: str,
        parameters: Optional[Dict[str, Any]] = None,
        risk_limits: Optional[Dict[str, Any]] = None,
        warmup_bars: int = 50,
        auto_start: bool = False,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new strategy.
        
        Args:
            name: Strategy name.
            type: Strategy type.
            symbols: Symbols to trade.
            timeframe: Timeframe for data.
            parameters: Strategy parameters.
            risk_limits: Risk limits.
            warmup_bars: Number of bars for warmup.
            auto_start: Whether to start automatically after initialization.
            description: Strategy description.
            tags: Strategy tags.
        
        Returns:
            Created strategy information.
        """
        data = {
            "name": name,
            "type": type,
            "symbols": symbols,
            "timeframe": timeframe,
            "parameters": parameters or {},
            "risk_limits": risk_limits or {},
            "warmup_bars": warmup_bars,
            "auto_start": auto_start
        }
        
        if description:
            data["description"] = description
            
        if tags:
            data["tags"] = tags
        
        return self.api_client.post("strategies", data=data)
    
    def get_strategies(
        self,
        type: Optional[str] = None,
        state: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get a list of strategies.
        
        Args:
            type: Filter by strategy type.
            state: Filter by strategy state.
            tag: Filter by tag.
            limit: Maximum number of strategies to return.
            offset: Number of strategies to skip.
        
        Returns:
            List of strategies and total count.
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if type:
            params["type"] = type
            
        if state:
            params["state"] = state
            
        if tag:
            params["tag"] = tag
        
        return self.api_client.get("strategies", params=params)
    
    def get_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Get a specific strategy by ID.
        
        Args:
            strategy_id: Strategy ID.
        
        Returns:
            Strategy information.
        """
        return self.api_client.get(f"strategies/{strategy_id}")
    
    def perform_action(self, strategy_id: str, action: str) -> Dict[str, Any]:
        """
        Perform an action on a strategy.
        
        Args:
            strategy_id: Strategy ID.
            action: Action to perform (start, stop, pause, resume).
        
        Returns:
            Action result.
        """
        data = {"action": action}
        
        return self.api_client.post(f"strategies/{strategy_id}/action", data=data)
    
    def start_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Start a strategy.
        
        Args:
            strategy_id: Strategy ID.
        
        Returns:
            Action result.
        """
        return self.perform_action(strategy_id, "start")
    
    def stop_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Stop a strategy.
        
        Args:
            strategy_id: Strategy ID.
        
        Returns:
            Action result.
        """
        return self.perform_action(strategy_id, "stop")
    
    def pause_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Pause a strategy.
        
        Args:
            strategy_id: Strategy ID.
        
        Returns:
            Action result.
        """
        return self.perform_action(strategy_id, "pause")
    
    def resume_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Resume a strategy.
        
        Args:
            strategy_id: Strategy ID.
        
        Returns:
            Action result.
        """
        return self.perform_action(strategy_id, "resume")
    
    def delete_strategy(self, strategy_id: str) -> None:
        """
        Delete a strategy.
        
        Args:
            strategy_id: Strategy ID.
        """
        self.api_client.delete(f"strategies/{strategy_id}") 