"""
Assistant Service Module
----------------------
Provides integration with Claude AI for trading analysis and insights
"""

import os
import logging
import json
from typing import Dict, List, Optional, Union, Any
import asyncio
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import anthropic

import config
from assistant.prompts import get_prompt_template

logger = logging.getLogger(__name__)

class AssistantService:
    """
    Service for interacting with Claude AI to provide trading insights and analysis
    """
    
    def __init__(self):
        """Initialize the Assistant Service"""
        self.api_key = config.ANTHROPIC_API_KEY
        self.model = config.ASSISTANT_CONFIG['model']
        self.max_tokens = config.ASSISTANT_CONFIG['max_tokens']
        self.conversation_history = []
        self.max_history_length = config.ASSISTANT_CONFIG['conversation_history_length']
        
        # Initialize client
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info(f"Assistant service initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Error initializing Claude client: {str(e)}")
            self.client = None
        
        # Create conversation history directory
        self.history_dir = config.BASE_DIR / 'assistant' / 'history'
        self.history_dir.mkdir(exist_ok=True, parents=True)
    
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        self.conversation_history.append({"role": role, "content": content})
        
        # Trim history if it gets too long
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def save_conversation(self, conversation_id: str = None) -> str:
        """
        Save the current conversation history to disk
        
        Args:
            conversation_id: Identifier for the conversation
            
        Returns:
            Path to the saved file
        """
        try:
            # Generate conversation ID if not provided
            if conversation_id is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                conversation_id = f"conversation_{timestamp}"
            
            # Create path
            filepath = self.history_dir / f"{conversation_id}.json"
            
            # Save conversation
            with open(filepath, 'w') as f:
                json.dump({
                    'id': conversation_id,
                    'timestamp': datetime.now().isoformat(),
                    'messages': self.conversation_history
                }, f, indent=2)
                
            logger.info(f"Conversation saved to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving conversation: {str(e)}")
            return ""
    
    def load_conversation(self, conversation_id: str) -> bool:
        """
        Load a saved conversation
        
        Args:
            conversation_id: Identifier for the conversation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build filepath
            filepath = self.history_dir / f"{conversation_id}.json"
            
            # Check if file exists
            if not filepath.exists():
                logger.error(f"Conversation file not found: {filepath}")
                return False
            
            # Load conversation
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            # Update conversation history
            self.conversation_history = data.get('messages', [])
            
            logger.info(f"Loaded conversation with {len(self.conversation_history)} messages")
            return True
            
        except Exception as e:
            logger.error(f"Error loading conversation: {str(e)}")
            return False
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """
        Get a list of recent conversations
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation metadata
        """
        try:
            # List all conversation files
            files = list(self.history_dir.glob("conversation_*.json"))
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # Limit results
            files = files[:limit]
            
            # Extract metadata
            conversations = []
            for file in files:
                try:
                    with open(file, 'r') as f:
                        data = json.load(f)
                        
                    conversations.append({
                        'id': data.get('id', file.stem),
                        'timestamp': data.get('timestamp', ''),
                        'message_count': len(data.get('messages', [])),
                        'filename': file.name
                    })
                except Exception as e:
                    logger.error(f"Error reading conversation file {file}: {str(e)}")
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting recent conversations: {str(e)}")
            return []
    
    async def query(self, prompt: str, market_data: Optional[pd.DataFrame] = None, 
                  include_history: bool = True) -> str:
        """
        Query Claude with a prompt, optionally including market data
        and conversation history
        
        Args:
            prompt: The query to send to Claude
            market_data: Optional market data to include
            include_history: Whether to include conversation history
            
        Returns:
            Claude's response
        """
        if self.client is None:
            logger.error("Claude client not initialized, cannot process query")
            return "Error: Claude client not initialized"
        
        try:
            # Prepare full prompt with optional market data
            full_prompt = prompt
            if market_data is not None and not market_data.empty:
                # Add market data context
                data_summary = "\nRecent market data summary:\n"
                data_summary += f"- Timeframe: {market_data.index[0]} to {market_data.index[-1]}\n"
                data_summary += f"- Current price: {market_data['close'].iloc[-1]}\n"
                data_summary += f"- 24h Change: {(market_data['close'].iloc[-1] / market_data['close'].iloc[-min(24, len(market_data)-1)] - 1) * 100:.2f}%\n"
                
                # Add technical indicators if available
                if 'rsi' in market_data.columns:
                    data_summary += f"- RSI: {market_data['rsi'].iloc[-1]:.2f}\n"
                if 'sma20' in market_data.columns and 'sma50' in market_data.columns:
                    data_summary += f"- SMA20/SMA50: {market_data['sma20'].iloc[-1]:.2f}/{market_data['sma50'].iloc[-1]:.2f}\n"
                if 'atr' in market_data.columns:
                    data_summary += f"- ATR: {market_data['atr'].iloc[-1]:.2f}\n"
                
                full_prompt += data_summary
            
            # Build messages with history if requested
            messages = []
            if include_history and self.conversation_history:
                messages = self.conversation_history.copy()
            
            # Add the current prompt
            messages.append({"role": "user", "content": full_prompt})
            
            # Query Claude
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=self.max_tokens,
                messages=messages
            )
            
            # Extract response text
            response_text = response.content[0].text
            
            # Add to conversation history
            self.add_message("user", full_prompt)
            self.add_message("assistant", response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error querying Claude: {str(e)}")
            return f"Error querying Claude: {str(e)}"
    
    def analyze_market_conditions(self, market_data: pd.DataFrame) -> str:
        """
        Analyze current market conditions using Claude
        
        Args:
            market_data: DataFrame with market data
            
        Returns:
            Analysis of market conditions
        """
        # Get prompt template
        prompt = get_prompt_template('market_analysis').format(
            symbol=market_data.index.name or "Unknown",
            timeframe="1h"  # This should be dynamically determined
        )
        
        # Run query synchronously by creating an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.query(prompt, market_data))
        finally:
            loop.close()
        
        return response
    
    def evaluate_trade_setup(self, setup_data: Dict) -> str:
        """
        Evaluate a potential trade setup
        
        Args:
            setup_data: Dictionary with trade setup details
            
        Returns:
            Evaluation of the trade setup
        """
        # Get prompt template
        prompt = get_prompt_template('trade_evaluation').format(
            symbol=setup_data.get('symbol', 'Unknown'),
            direction=setup_data.get('direction', 'long'),
            entry_price=setup_data.get('entry_price', 0),
            stop_loss=setup_data.get('stop_loss', 0),
            take_profit=setup_data.get('take_profit', 0),
            risk_reward=setup_data.get('risk_reward', 0),
            additional_info=setup_data.get('additional_info', '')
        )
        
        # Run query synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.query(prompt))
        finally:
            loop.close()
        
        return response
    
    def generate_backtest_insights(self, backtest_results: Dict) -> str:
        """
        Generate insights from backtest results
        
        Args:
            backtest_results: Dictionary with backtest results
            
        Returns:
            Insights from backtest results
        """
        # Get prompt template
        prompt = get_prompt_template('backtest_analysis').format(
            strategy_name=backtest_results.get('strategy_name', 'Unknown'),
            return_pct=backtest_results.get('return_pct', 0),
            sharpe_ratio=backtest_results.get('sharpe_ratio', 0),
            max_drawdown=backtest_results.get('max_drawdown_pct', 0),
            win_rate=backtest_results.get('win_rate', 0),
            total_trades=backtest_results.get('total_trades', 0)
        )
        
        # Run query synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.query(prompt))
        finally:
            loop.close()
        
        return response
    
    def suggest_strategy_improvements(self, strategy_name: str, 
                                    backtest_results: Dict) -> str:
        """
        Suggest improvements to a trading strategy
        
        Args:
            strategy_name: Name of the strategy
            backtest_results: Dictionary with backtest results
            
        Returns:
            Suggestions for strategy improvements
        """
        # Get prompt template
        prompt = get_prompt_template('strategy_improvement').format(
            strategy_name=strategy_name,
            return_pct=backtest_results.get('return_pct', 0),
            sharpe_ratio=backtest_results.get('sharpe_ratio', 0),
            max_drawdown=backtest_results.get('max_drawdown_pct', 0),
            win_rate=backtest_results.get('win_rate', 0),
            total_trades=backtest_results.get('total_trades', 0),
            params=json.dumps(backtest_results.get('strategy_params', {}), indent=2)
        )
        
        # Run query synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.query(prompt))
        finally:
            loop.close()
        
        return response
    
    def compare_strategy_performance(self, comparison_results: Dict) -> str:
        """
        Compare performance of multiple strategies
        
        Args:
            comparison_results: Dictionary with comparison results
            
        Returns:
            Analysis of strategy comparison
        """
        # Extract results for each strategy
        strategies = []
        for result in comparison_results.get('results', []):
            strategies.append({
                'name': result.get('strategy_name', 'Unknown'),
                'return_pct': result.get('return_pct', 0),
                'sharpe_ratio': result.get('sharpe_ratio', 0),
                'max_drawdown': result.get('max_drawdown_pct', 0),
                'win_rate': result.get('win_rate', 0)
            })
        
        # Get prompt template
        prompt = get_prompt_template('strategy_comparison').format(
            strategies_json=json.dumps(strategies, indent=2),
            best_strategy=comparison_results.get('best_strategy', {}).get('name', 'Unknown')
        )
        
        # Run query synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.query(prompt))
        finally:
            loop.close()
        
        return response