"""
Data Client

This module provides a client for the data API.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List


class DataClient:
    """Data API client."""
    
    def __init__(self, api_client):
        """
        Initialize data client.
        
        Args:
            api_client: API client.
        """
        self.api_client = api_client
    
    def get_data_sources(self) -> List[Dict[str, Any]]:
        """
        Get available data sources.
        
        Returns:
            List of available data sources.
        """
        return self.api_client.get("data/sources")
    
    def get_data_source(self, source_id: str) -> Dict[str, Any]:
        """
        Get information about a specific data source.
        
        Args:
            source_id: Data source ID.
        
        Returns:
            Data source information.
        """
        return self.api_client.get(f"data/sources/{source_id}")
    
    def get_time_series_data(
        self,
        source_id: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        frequency: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get time series data for a specific symbol.
        
        Args:
            source_id: Data source ID.
            symbol: Symbol to get data for.
            start_time: Start time for the data.
            end_time: End time for the data.
            frequency: Data frequency (e.g., 1m, 5m, 1h, 1d).
        
        Returns:
            Time series data.
        """
        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        if frequency:
            params["frequency"] = frequency
        
        return self.api_client.get(f"data/time-series/{source_id}/{symbol}", params=params) 