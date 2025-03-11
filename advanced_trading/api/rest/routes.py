"""
API Routes

This module provides route definitions and versioning for the API.
"""

from fastapi import APIRouter

from .routers import auth, strategies, data, execution, backtest

# Create the main API router
api_router = APIRouter()

# Version 1 router
v1_router = APIRouter(prefix="/v1")

# Add routers to v1
v1_router.include_router(auth.router)
v1_router.include_router(strategies.router)
v1_router.include_router(data.router)
v1_router.include_router(execution.router)
v1_router.include_router(backtest.router)

# Add v1 router to main api router
api_router.include_router(v1_router)

# Latest version router (points to the latest version)
api_router.include_router(auth.router)
api_router.include_router(strategies.router)
api_router.include_router(data.router)
api_router.include_router(execution.router)
api_router.include_router(backtest.router) 