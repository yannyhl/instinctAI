"""
API Integration Tests

This module provides integration tests for the API.
"""

import os
import pytest
import requests
from fastapi.testclient import TestClient

# Import the API app
from advanced_trading.api.main import app


@pytest.fixture
def api_client():
    """Provide a test client for the API."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Provide authentication headers for API requests."""
    # This is a simplistic approach - in a real test we would authenticate first
    return {
        "Authorization": "Bearer test-token"
    }


class TestAPIHealth:
    """Test the API health endpoint."""
    
    def test_health_check(self, api_client):
        """Test that the health check endpoint works."""
        response = api_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAuthEndpoints:
    """Test the authentication endpoints."""
    
    def test_login_with_valid_credentials(self, api_client):
        """Test logging in with valid credentials."""
        response = api_client.post(
            "/api/auth/login",
            json={
                "username": "test",
                "password": "password"
            }
        )
        
        # In our mock implementation, these credentials should work
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
    
    def test_login_with_invalid_credentials(self, api_client):
        """Test logging in with invalid credentials."""
        response = api_client.post(
            "/api/auth/login",
            json={
                "username": "invalid",
                "password": "invalid"
            }
        )
        
        assert response.status_code == 401


class TestStrategiesEndpoints:
    """Test the strategies endpoints."""
    
    def test_get_available_strategies(self, api_client, auth_headers):
        """Test getting available strategy definitions."""
        response = api_client.get(
            "/api/strategies/available",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Check structure of strategy definitions
        if data:
            strategy = data[0]
            assert "name" in strategy
            assert "description" in strategy
            assert "type" in strategy
            assert "parameters" in strategy
    
    def test_create_and_delete_strategy(self, api_client, auth_headers):
        """Test creating and deleting a strategy."""
        # Create strategy
        create_response = api_client.post(
            "/api/strategies",
            headers=auth_headers,
            json={
                "name": "Test Strategy",
                "type": "trend_following",
                "symbols": ["BTC/USD"],
                "timeframe": "1h",
                "parameters": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9
                }
            }
        )
        
        assert create_response.status_code == 201
        data = create_response.json()
        assert "id" in data
        strategy_id = data["id"]
        
        # Get strategy
        get_response = api_client.get(
            f"/api/strategies/{strategy_id}",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        assert get_response.json()["id"] == strategy_id
        
        # Delete strategy
        delete_response = api_client.delete(
            f"/api/strategies/{strategy_id}",
            headers=auth_headers
        )
        
        assert delete_response.status_code == 204


class TestDataEndpoints:
    """Test the data endpoints."""
    
    def test_get_data_sources(self, api_client, auth_headers):
        """Test getting data sources."""
        response = api_client.get(
            "/api/data/sources",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Check structure of data sources
        if data:
            source = data[0]
            assert "id" in source
            assert "name" in source
            assert "symbols" in source
    
    def test_get_time_series_data(self, api_client, auth_headers):
        """Test getting time series data."""
        # First get a data source
        sources_response = api_client.get(
            "/api/data/sources",
            headers=auth_headers
        )
        
        assert sources_response.status_code == 200
        sources = sources_response.json()
        
        if not sources:
            pytest.skip("No data sources available")
        
        source = sources[0]
        symbol = source["symbols"][0]
        
        # Now get time series data
        data_response = api_client.get(
            f"/api/data/time-series/{source['id']}/{symbol}",
            headers=auth_headers,
            params={
                "start_time": "2023-01-01T00:00:00Z",
                "end_time": "2023-01-02T00:00:00Z",
                "frequency": "1h"
            }
        )
        
        assert data_response.status_code == 200
        data = data_response.json()
        assert isinstance(data, list)
        
        # Check structure of time series data
        if data:
            point = data[0]
            assert "timestamp" in point
            assert "close" in point


class TestExecutionEndpoints:
    """Test the execution endpoints."""
    
    def test_create_and_cancel_order(self, api_client, auth_headers):
        """Test creating and canceling an order."""
        # Create order
        create_response = api_client.post(
            "/api/execution/orders",
            headers=auth_headers,
            json={
                "symbol": "BTC/USD",
                "side": "buy",
                "type": "market",
                "quantity": 0.1
            }
        )
        
        assert create_response.status_code == 200
        data = create_response.json()
        assert "id" in data
        order_id = data["id"]
        
        # Get order
        get_response = api_client.get(
            f"/api/execution/orders/{order_id}",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        assert get_response.json()["id"] == order_id
        
        # Cancel order
        cancel_response = api_client.delete(
            f"/api/execution/orders/{order_id}",
            headers=auth_headers
        )
        
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "canceled"


class TestBacktestEndpoints:
    """Test the backtest endpoints."""
    
    def test_create_and_cancel_backtest(self, api_client, auth_headers):
        """Test creating and canceling a backtest."""
        # Create backtest
        create_response = api_client.post(
            "/api/backtest",
            headers=auth_headers,
            json={
                "strategy_id": "test-strategy",
                "start_date": "2022-01-01T00:00:00Z",
                "end_date": "2022-12-31T00:00:00Z",
                "symbols": ["BTC/USD"],
                "initial_capital": 100000.0,
                "parameters": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9
                }
            }
        )
        
        assert create_response.status_code == 201
        data = create_response.json()
        assert "id" in data
        backtest_id = data["id"]
        
        # Get backtest
        get_response = api_client.get(
            f"/api/backtest/{backtest_id}",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        assert get_response.json()["id"] == backtest_id
        
        # Cancel backtest
        cancel_response = api_client.delete(
            f"/api/backtest/{backtest_id}",
            headers=auth_headers
        )
        
        assert cancel_response.status_code == 204 