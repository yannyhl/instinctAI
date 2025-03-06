"""
Assistant API Module
-----------------
Provides a REST API for accessing the InstinctAI Assistant
"""

import logging
import json
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd
import uvicorn

import config
from assistant.service import AssistantService
from trading.data_manager import DataManager
from backtesting.engine import run_strategy_backtest

# Configure logging
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="InstinctAI Assistant API",
    description="API for the InstinctAI trading assistant powered by Claude",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify the exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
assistant_service = AssistantService()
data_manager = DataManager()

# ------------------------
# Pydantic Models
# ------------------------

class QueryRequest(BaseModel):
    """Request for querying the assistant"""
    prompt: str = Field(..., description="The prompt to send to the assistant")
    include_history: bool = Field(True, description="Whether to include conversation history")
    include_market_data: bool = Field(False, description="Whether to include recent market data")
    symbol: Optional[str] = Field(None, description="Symbol for market data")
    timeframe: Optional[str] = Field(None, description="Timeframe for market data")

class TradeSetupRequest(BaseModel):
    """Request for evaluating a trade setup"""
    symbol: str = Field(..., description="Trading symbol (e.g., 'BTC')")
    direction: str = Field(..., description="Trade direction ('long' or 'short')")
    entry_price: float = Field(..., description="Entry price")
    stop_loss: float = Field(..., description="Stop loss price")
    take_profit: float = Field(..., description="Take profit price")
    additional_info: Optional[str] = Field("", description="Additional information about the trade")

class BacktestRequest(BaseModel):
    """Request for running a backtest"""
    strategy_name: str = Field(..., description="Name of the strategy to test")
    symbol: str = Field(..., description="Trading symbol (e.g., 'BTC')")
    timeframe: str = Field("1h", description="Data timeframe")
    params: Optional[Dict[str, Any]] = Field(None, description="Strategy parameters")
    initial_cash: float = Field(2000.0, description="Initial cash for backtest")

class StrategyImprovementRequest(BaseModel):
    """Request for strategy improvement suggestions"""
    strategy_name: str = Field(..., description="Name of the strategy")
    backtest_results: Dict[str, Any] = Field(..., description="Results from backtest")

# ------------------------
# Helper Functions
# ------------------------

async def get_market_data(symbol: str = "BTC", timeframe: str = "1h", 
                         refresh: bool = False) -> pd.DataFrame:
    """Get market data with indicators"""
    try:
        data = data_manager.get_data_with_indicators(symbol, timeframe, refresh)
        if data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol} {timeframe}")
        return data
    except Exception as e:
        logger.error(f"Error getting market data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting market data: {str(e)}")

# ------------------------
# API Routes
# ------------------------

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "InstinctAI Assistant API",
        "version": "1.0.0",
        "status": "active"
    }

@app.post("/query")
async def query_assistant(request: QueryRequest):
    """Query the assistant with a prompt"""
    try:
        # Get market data if requested
        market_data = None
        if request.include_market_data and request.symbol:
            symbol = request.symbol
            timeframe = request.timeframe or "1h"
            market_data = await get_market_data(symbol, timeframe)
        
        # Query assistant
        response = await assistant_service.query(
            prompt=request.prompt,
            market_data=market_data,
            include_history=request.include_history
        )
        
        return {
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error querying assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying assistant: {str(e)}")

@app.post("/analyze/market")
async def analyze_market(symbol: str = Query("BTC"), timeframe: str = Query("1h"), refresh: bool = Query(False)):
    """Analyze current market conditions"""
    try:
        # Get market data
        market_data = await get_market_data(symbol, timeframe, refresh)
        
        # Get analysis
        analysis = assistant_service.analyze_market_conditions(market_data)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error analyzing market: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing market: {str(e)}")

@app.post("/evaluate/trade")
async def evaluate_trade(request: TradeSetupRequest):
    """Evaluate a trade setup"""
    try:
        # Calculate risk-reward ratio
        risk = abs(request.entry_price - request.stop_loss)
        reward = abs(request.entry_price - request.take_profit)
        risk_reward = reward / risk if risk > 0 else 0
        
        # Create setup data
        setup_data = {
            "symbol": request.symbol,
            "direction": request.direction,
            "entry_price": request.entry_price,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit,
            "risk_reward": risk_reward,
            "additional_info": request.additional_info
        }
        
        # Get evaluation
        evaluation = assistant_service.evaluate_trade_setup(setup_data)
        
        return {
            "evaluation": evaluation,
            "setup": setup_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error evaluating trade: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error evaluating trade: {str(e)}")

@app.post("/backtest/run")
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """Run a backtest with the specified strategy"""
    try:
        # Get market data
        market_data = await get_market_data(request.symbol, request.timeframe)
        
        # Run backtest
        results = run_strategy_backtest(
            data=market_data,
            strategy_name=request.strategy_name,
            params=request.params,
            initial_cash=request.initial_cash,
            plot=True
        )
        
        # Generate insights in the background
        background_tasks.add_task(
            assistant_service.generate_backtest_insights,
            results
        )
        
        return {
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running backtest: {str(e)}")

@app.post("/strategy/improve")
async def improve_strategy(request: StrategyImprovementRequest):
    """Get suggestions for improving a strategy"""
    try:
        # Get suggestions
        suggestions = assistant_service.suggest_strategy_improvements(
            request.strategy_name,
            request.backtest_results
        )
        
        return {
            "strategy_name": request.strategy_name,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error improving strategy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error improving strategy: {str(e)}")

@app.get("/conversations")
async def get_conversations(limit: int = Query(10)):
    """Get list of recent conversations"""
    try:
        conversations = assistant_service.get_recent_conversations(limit)
        return {
            "conversations": conversations,
            "count": len(conversations)
        }
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting conversations: {str(e)}")

@app.post("/conversations/{conversation_id}/load")
async def load_conversation(conversation_id: str):
    """Load a specific conversation"""
    try:
        success = assistant_service.load_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}")
        
        return {
            "status": "success",
            "conversation_id": conversation_id,
            "message_count": len(assistant_service.conversation_history)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading conversation: {str(e)}")

@app.post("/conversations/save")
async def save_conversation(conversation_id: Optional[str] = None):
    """Save the current conversation"""
    try:
        filepath = assistant_service.save_conversation(conversation_id)
        if not filepath:
            raise HTTPException(status_code=500, detail="Failed to save conversation")
        
        return {
            "status": "success",
            "filepath": filepath,
            "message_count": len(assistant_service.conversation_history)
        }
    except Exception as e:
        logger.error(f"Error saving conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving conversation: {str(e)}")

# ------------------------
# Server Function
# ------------------------

def start_assistant_api():
    """Start the assistant API server"""
    host = config.ASSISTANT_CONFIG.get('host', '0.0.0.0')
    port = config.ASSISTANT_CONFIG.get('port', 8000)
    
    logger.info(f"Starting InstinctAI Assistant API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_assistant_api()