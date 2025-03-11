"""
Strategy-to-Execution Bridge

This module provides the bridge between the strategy framework and the execution engine.
It translates strategy signals into executable orders, routes them to the appropriate
exchange, and provides execution feedback to strategies.

Key features:
- Signal translation: Convert strategy signals to executable orders
- Order routing: Direct orders to appropriate exchanges
- Execution feedback: Provide execution results back to strategies
- Order state tracking: Track pending, filled, and failed orders
- Risk validation: Validate orders against risk parameters before execution
"""

import logging
import time
import threading
import queue
from typing import Dict, List, Optional, Union, Any, Callable, Set
from enum import Enum
import pandas as pd
from datetime import datetime, timedelta

from advanced_trading.strategies.base import Strategy, StrategyResult
from advanced_trading.execution.exchange.order import (
    Order, OrderParams, OrderType, OrderSide, OrderStatus, TimeInForce,
    create_order, submit_order, cancel_order, get_order_status
)
from advanced_trading.execution.exchange.client import ExchangeClient, ExchangeType, connect_exchange
from advanced_trading.execution.analysis.execution_analyzer import (
    ExecutionAnalyzer, BenchmarkType, ExecutionMetrics
)
from advanced_trading.execution.risk_integration.strategy_risk_adapter import StrategyRiskAdapter
from advanced_trading.execution.risk_integration.risk_manager import ExecutionRiskManager

# Initialize logger
logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of strategy signals."""
    ENTRY = "entry"  # Enter a new position
    EXIT = "exit"  # Exit an existing position
    MODIFY = "modify"  # Modify an existing position
    CANCEL = "cancel"  # Cancel an existing order


class ExecutionMode(Enum):
    """Execution modes for the bridge."""
    SYNC = "synchronous"  # Synchronous execution (blocking)
    ASYNC = "asynchronous"  # Asynchronous execution (non-blocking)
    SIMULATION = "simulation"  # Simulated execution (no real orders)


class OrderStatus(Enum):
    """Status of an order in the bridge."""
    PENDING = "pending"  # Order is pending execution
    SUBMITTED = "submitted"  # Order has been submitted to exchange
    FILLED = "filled"  # Order has been completely filled
    PARTIALLY_FILLED = "partially_filled"  # Order has been partially filled
    FAILED = "failed"  # Order execution failed
    CANCELED = "canceled"  # Order was canceled


class StrategyExecutionBridge:
    """
    Bridge between the strategy framework and the execution engine.
    
    This class translates strategy signals into executable orders,
    routes them to the appropriate exchange, and provides execution
    feedback to the strategies.
    """
    
    def __init__(
        self,
        execution_mode: ExecutionMode = ExecutionMode.SYNC,
        risk_manager: Optional[ExecutionRiskManager] = None,
        analyze_executions: bool = True,
        max_parallel_orders: int = 10,
        order_update_interval_ms: int = 1000
    ):
        """
        Initialize the strategy execution bridge.
        
        Args:
            execution_mode: Mode of execution (sync, async, simulation)
            risk_manager: Risk manager for validating orders
            analyze_executions: Whether to analyze executions
            max_parallel_orders: Maximum number of parallel orders in async mode
            order_update_interval_ms: Interval for order status updates in ms
        """
        self.execution_mode = execution_mode
        self.risk_manager = risk_manager
        self.analyze_executions = analyze_executions
        self.max_parallel_orders = max_parallel_orders
        self.order_update_interval_ms = order_update_interval_ms
        
        # Initialize state
        self.exchanges: Dict[str, ExchangeClient] = {}
        self.orders: Dict[str, Order] = {}  # All orders by order ID
        self.strategy_orders: Dict[str, Set[str]] = {}  # Orders by strategy ID
        self.pending_orders: Dict[str, Order] = {}  # Orders pending execution
        self.active_orders: Dict[str, Order] = {}  # Orders submitted but not filled/canceled
        
        # Initialize execution analyzer if enabled
        self.execution_analyzer = ExecutionAnalyzer() if analyze_executions else None
        
        # Initialize async execution if needed
        if execution_mode == ExecutionMode.ASYNC:
            self.order_queue = queue.Queue()
            self.stop_event = threading.Event()
            self.worker_threads = []
            self._start_worker_threads()
        
        logger.info(f"Strategy execution bridge initialized with mode: {execution_mode.value}")
    
    def connect_exchange(
        self,
        exchange_name: str,
        credentials: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Connect to an exchange.
        
        Args:
            exchange_name: Name of the exchange
            credentials: Exchange credentials
            **kwargs: Additional connection parameters
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            client = connect_exchange(exchange_name, credentials, **kwargs)
            if client and client.is_connected():
                self.exchanges[exchange_name] = client
                logger.info(f"Connected to exchange: {exchange_name}")
                return True
            else:
                logger.error(f"Failed to connect to exchange: {exchange_name}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to exchange {exchange_name}: {str(e)}")
            return False
    
    def disconnect_exchange(self, exchange_name: str) -> bool:
        """
        Disconnect from an exchange.
        
        Args:
            exchange_name: Name of the exchange
            
        Returns:
            True if disconnection successful, False otherwise
        """
        if exchange_name not in self.exchanges:
            logger.warning(f"Exchange {exchange_name} not connected")
            return False
        
        try:
            client = self.exchanges[exchange_name]
            success = client.disconnect()
            if success:
                del self.exchanges[exchange_name]
                logger.info(f"Disconnected from exchange: {exchange_name}")
            else:
                logger.error(f"Failed to disconnect from exchange: {exchange_name}")
            return success
        except Exception as e:
            logger.error(f"Error disconnecting from exchange {exchange_name}: {str(e)}")
            return False
    
    def process_strategy_result(
        self,
        strategy_id: str,
        result: StrategyResult,
        exchange_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a strategy result and execute any signals.
        
        Args:
            strategy_id: ID of the strategy
            result: The strategy result containing signals
            exchange_name: Optional exchange to use
            
        Returns:
            Dictionary with execution results
        """
        if not result or not result.signals or not result.signals:
            logger.info(f"No signals in strategy result for {strategy_id}")
            return {"status": "no_signals"}
        
        # Initialize results
        execution_results = {
            "strategy_id": strategy_id,
            "timestamp": datetime.now(),
            "orders": [],
            "status": "success"
        }
        
        # Get target exchange
        target_exchange = self._get_target_exchange(exchange_name)
        if not target_exchange:
            logger.error(f"No exchange available for execution")
            execution_results["status"] = "no_exchange"
            return execution_results
        
        # Initialize orders set for this strategy if not exists
        if strategy_id not in self.strategy_orders:
            self.strategy_orders[strategy_id] = set()
        
        # Process signals by symbol
        for symbol, signals_df in result.signals.items():
            if signals_df.empty:
                continue
                
            # Process each signal
            for _, signal in signals_df.iterrows():
                # Create order from signal
                try:
                    order_params = self._create_order_params_from_signal(symbol, signal)
                    order = create_order(order_params)
                    
                    # Generate unique client order ID if not provided
                    if not order.params.client_order_id:
                        order.params.client_order_id = f"{strategy_id}_{time.time()}"
                    
                    # Validate order with risk manager if available
                    if self.risk_manager:
                        is_valid, reason = self.risk_manager.validate_order(order)
                        if not is_valid:
                            logger.warning(f"Order failed risk validation: {reason}")
                            execution_results["orders"].append({
                                "symbol": symbol,
                                "status": "rejected",
                                "reason": reason
                            })
                            continue
                    
                    # Execute or queue order based on execution mode
                    if self.execution_mode == ExecutionMode.SYNC:
                        executed_order = self._execute_order(target_exchange, order)
                        self._track_order(strategy_id, executed_order)
                        execution_results["orders"].append({
                            "symbol": symbol,
                            "order_id": executed_order.exchange_order_id,
                            "status": executed_order.status.value
                        })
                    elif self.execution_mode == ExecutionMode.ASYNC:
                        # Queue order for async execution
                        self.order_queue.put((strategy_id, target_exchange, order))
                        self._track_order(strategy_id, order)
                        execution_results["orders"].append({
                            "symbol": symbol,
                            "order_id": order.params.client_order_id,
                            "status": "queued"
                        })
                    else:  # Simulation mode
                        simulated_order = self._simulate_order(order)
                        self._track_order(strategy_id, simulated_order)
                        execution_results["orders"].append({
                            "symbol": symbol,
                            "order_id": simulated_order.params.client_order_id,
                            "status": simulated_order.status.value
                        })
                except Exception as e:
                    logger.error(f"Error processing signal for {symbol}: {str(e)}")
                    execution_results["orders"].append({
                        "symbol": symbol,
                        "status": "error",
                        "reason": str(e)
                    })
        
        return execution_results
    
    def cancel_all_orders(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all active orders.
        
        Args:
            strategy_id: Optional strategy ID to cancel orders for
            
        Returns:
            Dictionary with cancellation results
        """
        results = {
            "timestamp": datetime.now(),
            "canceled": [],
            "failed": []
        }
        
        # Determine which orders to cancel
        order_ids_to_cancel = set()
        if strategy_id:
            # Cancel orders for specific strategy
            if strategy_id in self.strategy_orders:
                order_ids_to_cancel = self.strategy_orders[strategy_id]
        else:
            # Cancel all active orders
            order_ids_to_cancel = set(self.active_orders.keys())
        
        # Cancel each order
        for order_id in order_ids_to_cancel:
            order = self.active_orders.get(order_id)
            if not order:
                continue
                
            # Get exchange for this order
            exchange = self._get_exchange_for_order(order)
            if not exchange:
                results["failed"].append({
                    "order_id": order_id,
                    "reason": "exchange_not_found"
                })
                continue
            
            try:
                canceled_order = cancel_order(exchange, order)
                if canceled_order.status == OrderStatus.CANCELED:
                    # Update order in our tracking
                    self.orders[order_id] = canceled_order
                    if order_id in self.active_orders:
                        del self.active_orders[order_id]
                    
                    results["canceled"].append({
                        "order_id": order_id,
                        "symbol": order.params.symbol
                    })
                else:
                    results["failed"].append({
                        "order_id": order_id,
                        "reason": "cancellation_failed",
                        "status": canceled_order.status.value
                    })
            except Exception as e:
                logger.error(f"Error canceling order {order_id}: {str(e)}")
                results["failed"].append({
                    "order_id": order_id,
                    "reason": str(e)
                })
        
        return results
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of an order.
        
        Args:
            order_id: The order ID
            
        Returns:
            Order status information or None if not found
        """
        # First check our local tracking
        order = self.orders.get(order_id)
        if not order:
            logger.warning(f"Order {order_id} not found in local tracking")
            return None
        
        # For active orders, get latest status from exchange
        if order_id in self.active_orders:
            try:
                exchange = self._get_exchange_for_order(order)
                if exchange:
                    updated_order = get_order_status(exchange, order_id)
                    self.orders[order_id] = updated_order
                    if updated_order.status == OrderStatus.FILLED:
                        # Move from active to filled
                        del self.active_orders[order_id]
                    order = updated_order
            except Exception as e:
                logger.error(f"Error getting order status for {order_id}: {str(e)}")
        
        # Create status dictionary
        status = {
            "order_id": order_id,
            "exchange_order_id": order.exchange_order_id,
            "symbol": order.params.symbol,
            "side": order.params.side.value,
            "type": order.params.order_type.value,
            "quantity": order.params.quantity,
            "price": order.params.price,
            "status": order.status.value,
            "filled_quantity": order.filled_quantity,
            "average_price": order.average_price,
            "fee": order.fee,
            "created_at": order.created_at,
            "updated_at": order.updated_at
        }
        
        return status
    
    def get_all_orders(self, strategy_id: Optional[str] = None, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all orders.
        
        Args:
            strategy_id: Optional strategy ID to filter orders
            active_only: Whether to return only active orders
            
        Returns:
            List of order status dictionaries
        """
        # Determine which orders to include
        order_ids = set()
        if strategy_id:
            # Get orders for specific strategy
            if strategy_id in self.strategy_orders:
                order_ids = self.strategy_orders[strategy_id]
        else:
            # Get all orders
            order_ids = set(self.orders.keys())
        
        # Filter by active status if requested
        if active_only:
            order_ids = order_ids.intersection(set(self.active_orders.keys()))
        
        # Get status for each order
        return [self.get_order_status(order_id) for order_id in order_ids if self.get_order_status(order_id)]
    
    def get_execution_analytics(self, 
                              strategy_id: Optional[str] = None,
                              period: timedelta = timedelta(days=1)) -> Optional[Dict[str, Any]]:
        """
        Get execution analytics.
        
        Args:
            strategy_id: Optional strategy ID to filter executions
            period: Time period to analyze
            
        Returns:
            Execution analytics or None if analyzer not enabled
        """
        if not self.execution_analyzer:
            logger.warning("Execution analyzer not enabled")
            return None
        
        # Get execution summary
        try:
            summary = self.execution_analyzer.get_execution_summary()
            
            # Filter by strategy if requested
            if strategy_id and 'strategy_id' in summary.columns:
                summary = summary[summary['strategy_id'] == strategy_id]
            
            # Filter by time period
            cutoff = datetime.now() - period
            if 'timestamp' in summary.columns:
                summary = summary[summary['timestamp'] >= cutoff]
            
            # Calculate aggregated metrics
            if not summary.empty:
                analytics = {
                    "orders_count": len(summary),
                    "symbols": summary['symbol'].nunique(),
                    "fill_rate_avg": summary['fill_rate'].mean(),
                    "slippage_avg_bps": summary['slippage'].mean() * 10000,  # Convert to basis points
                    "implementation_shortfall_avg_bps": summary['implementation_shortfall'].mean() * 10000,
                    "time_to_fill_avg_seconds": summary['time_to_fill'].mean(),
                    "by_symbol": {}
                }
                
                # Calculate metrics by symbol
                for symbol in summary['symbol'].unique():
                    symbol_data = summary[summary['symbol'] == symbol]
                    analytics["by_symbol"][symbol] = {
                        "orders_count": len(symbol_data),
                        "fill_rate_avg": symbol_data['fill_rate'].mean(),
                        "slippage_avg_bps": symbol_data['slippage'].mean() * 10000,
                        "implementation_shortfall_avg_bps": symbol_data['implementation_shortfall'].mean() * 10000,
                        "time_to_fill_avg_seconds": symbol_data['time_to_fill'].mean()
                    }
                
                return analytics
            else:
                return {"orders_count": 0, "message": "No executions found for the specified criteria"}
        except Exception as e:
            logger.error(f"Error generating execution analytics: {str(e)}")
            return {"error": str(e)}
    
    def shutdown(self) -> bool:
        """
        Shut down the execution bridge.
        
        Returns:
            True if shutdown successful
        """
        logger.info("Shutting down strategy execution bridge")
        
        # Cancel all active orders
        self.cancel_all_orders()
        
        # Stop async workers if running
        if self.execution_mode == ExecutionMode.ASYNC:
            self.stop_event.set()
            for thread in self.worker_threads:
                thread.join(timeout=5.0)  # Wait up to 5 seconds for each thread
            self.worker_threads = []
        
        # Disconnect from all exchanges
        for exchange_name in list(self.exchanges.keys()):
            self.disconnect_exchange(exchange_name)
        
        logger.info("Strategy execution bridge shut down successfully")
        return True
    
    def _create_order_params_from_signal(self, symbol: str, signal: pd.Series) -> OrderParams:
        """
        Create order parameters from a strategy signal.
        
        Args:
            symbol: Trading symbol
            signal: Signal data
            
        Returns:
            Order parameters
            
        Raises:
            ValueError: If signal data is invalid
        """
        # Extract signal data
        side = None
        if 'side' in signal:
            if isinstance(signal['side'], str):
                side = OrderSide.BUY if signal['side'].lower() == 'buy' else OrderSide.SELL
            elif 'signal' in signal and signal['signal'] > 0:
                side = OrderSide.BUY
            elif 'signal' in signal and signal['signal'] < 0:
                side = OrderSide.SELL
        elif 'signal' in signal:
            side = OrderSide.BUY if signal['signal'] > 0 else OrderSide.SELL
        
        if side is None:
            raise ValueError(f"Could not determine order side from signal: {signal}")
        
        # Get price
        price = None
        if 'price' in signal:
            price = float(signal['price'])
        elif 'limit_price' in signal:
            price = float(signal['limit_price'])
        
        # Get quantity
        quantity = None
        if 'quantity' in signal:
            quantity = float(signal['quantity'])
        elif 'size' in signal:
            quantity = float(signal['size'])
        elif 'amount' in signal:
            quantity = float(signal['amount'])
        elif 'signal' in signal and abs(signal['signal']) > 0:
            quantity = abs(float(signal['signal']))
        
        if quantity is None or quantity <= 0:
            raise ValueError(f"Could not determine order quantity from signal: {signal}")
        
        # Determine order type
        order_type = OrderType.MARKET
        if price is not None:
            order_type = OrderType.LIMIT
        
        # Create order parameters
        params = OrderParams(
            symbol=symbol,
            order_type=order_type,
            side=side,
            quantity=quantity,
            price=price,
            time_in_force=TimeInForce.GTC
        )
        
        # Add additional parameters from signal
        if 'stop_price' in signal and not pd.isna(signal['stop_price']):
            params.stop_price = float(signal['stop_price'])
            if order_type == OrderType.LIMIT:
                params.order_type = OrderType.STOP_LIMIT
            else:
                params.order_type = OrderType.STOP_LOSS
        
        if 'client_order_id' in signal and not pd.isna(signal['client_order_id']):
            params.client_order_id = str(signal['client_order_id'])
        
        if 'reduce_only' in signal and not pd.isna(signal['reduce_only']):
            params.reduce_only = bool(signal['reduce_only'])
        
        if 'post_only' in signal and not pd.isna(signal['post_only']):
            params.post_only = bool(signal['post_only'])
        
        return params
    
    def _get_target_exchange(self, exchange_name: Optional[str] = None) -> Optional[ExchangeClient]:
        """
        Get the target exchange for order execution.
        
        Args:
            exchange_name: Optional name of the exchange to use
            
        Returns:
            Exchange client or None if not available
        """
        if exchange_name and exchange_name in self.exchanges:
            return self.exchanges[exchange_name]
        
        # If no specific exchange requested, use the first available
        if self.exchanges:
            return next(iter(self.exchanges.values()))
        
        # For simulation mode, return None (will be handled by simulation)
        if self.execution_mode == ExecutionMode.SIMULATION:
            return None
            
        logger.error("No exchange available for execution")
        return None
    
    def _execute_order(self, exchange: ExchangeClient, order: Order) -> Order:
        """
        Execute an order on an exchange.
        
        Args:
            exchange: Exchange client
            order: Order to execute
            
        Returns:
            Executed order
        """
        try:
            # Submit order to exchange
            executed_order = submit_order(exchange, order)
            
            # Store market data for analysis
            market_data = {}
            
            # Track order
            self.orders[executed_order.exchange_order_id] = executed_order
            
            # Add to active orders if not filled
            if executed_order.status != OrderStatus.FILLED:
                self.active_orders[executed_order.exchange_order_id] = executed_order
            
            # Analyze execution if enabled
            if self.execution_analyzer and executed_order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                self.execution_analyzer.add_execution(executed_order, market_data)
            
            return executed_order
        except Exception as e:
            logger.error(f"Error executing order: {str(e)}")
            # Update order status to failed
            order.status = OrderStatus.FAILED
            return order
    
    def _simulate_order(self, order: Order) -> Order:
        """
        Simulate order execution.
        
        Args:
            order: Order to simulate
            
        Returns:
            Simulated order
        """
        # Assign a simulated exchange order ID
        order.exchange_order_id = f"sim_{order.params.client_order_id or int(time.time())}"
        
        # Simulate a filled order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.params.quantity
        order.average_price = order.params.price or 0.0  # Use provided price or simulate market price
        order.created_at = datetime.now()
        order.updated_at = datetime.now()
        
        # Add simulated fee (5 bps)
        order.fee = order.filled_quantity * order.average_price * 0.0005
        order.fee_currency = order.params.symbol.split('/')[1] if '/' in order.params.symbol else 'USD'
        
        return order
    
    def _track_order(self, strategy_id: str, order: Order) -> None:
        """
        Track an order in the system.
        
        Args:
            strategy_id: Strategy ID
            order: Order to track
        """
        # Generate order ID if not available
        order_id = order.exchange_order_id or order.params.client_order_id
        if not order_id:
            order_id = f"{strategy_id}_{int(time.time())}"
            order.params.client_order_id = order_id
        
        # Add to orders dict
        self.orders[order_id] = order
        
        # Add to strategy orders
        if strategy_id not in self.strategy_orders:
            self.strategy_orders[strategy_id] = set()
        self.strategy_orders[strategy_id].add(order_id)
        
        # Add to active orders if applicable
        if order.status not in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
            self.active_orders[order_id] = order
    
    def _get_exchange_for_order(self, order: Order) -> Optional[ExchangeClient]:
        """
        Get the exchange client for an order.
        
        Args:
            order: The order
            
        Returns:
            Exchange client or None if not found
        """
        # If only one exchange, use it
        if len(self.exchanges) == 1:
            return next(iter(self.exchanges.values()))
        
        # TODO: Implement logic to determine which exchange to use based on order properties
        # For now, just use the first exchange
        if self.exchanges:
            return next(iter(self.exchanges.values()))
        
        return None
    
    def _start_worker_threads(self) -> None:
        """Start worker threads for async order execution."""
        for i in range(self.max_parallel_orders):
            thread = threading.Thread(
                target=self._order_worker,
                name=f"order-worker-{i}",
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)
    
    def _order_worker(self) -> None:
        """Worker thread function for async order execution."""
        while not self.stop_event.is_set():
            try:
                # Get an order from the queue with timeout
                try:
                    strategy_id, exchange, order = self.order_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Execute the order
                try:
                    executed_order = self._execute_order(exchange, order)
                    # Update tracking
                    self._track_order(strategy_id, executed_order)
                except Exception as e:
                    logger.error(f"Error in order worker: {str(e)}")
                finally:
                    # Mark task as done
                    self.order_queue.task_done()
            except Exception as e:
                logger.error(f"Unexpected error in order worker: {str(e)}")
                # Small sleep to avoid tight loop in case of repeated errors
                time.sleep(0.1) 