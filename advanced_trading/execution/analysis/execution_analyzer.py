"""
Execution Analysis Module

This module provides tools for analyzing the quality and performance of order execution.
It includes functions for:

1. Transaction Cost Analysis (TCA): Measuring the costs of execution vs. benchmarks
2. Market Impact Analysis: Measuring the price impact of orders
3. Execution Quality Metrics: Slippage, fill rates, timing, etc.
4. Performance Reporting: Generating reports on execution performance

These tools help traders and algorithms evaluate and improve execution strategies.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import logging

from advanced_trading.execution.exchange.order import Order, OrderStatus, OrderType, OrderSide, TimeInForce

# Initialize logger
logger = logging.getLogger(__name__)


class BenchmarkType:
    """Benchmark types for transaction cost analysis."""
    ARRIVAL = "arrival_price"  # Price at order arrival time
    VWAP = "vwap"  # Volume-weighted average price
    TWAP = "twap"  # Time-weighted average price
    CLOSE = "close_price"  # Close price
    MID = "mid_price"  # Mid price (average of bid and ask)
    CUSTOM = "custom"  # Custom benchmark


class ExecutionMetrics:
    """Container for execution quality metrics."""
    
    def __init__(self):
        """Initialize execution metrics."""
        # Transaction cost metrics
        self.implementation_shortfall = 0.0  # Difference between expected and realized cost
        self.slippage = 0.0  # Difference between expected and actual execution price
        self.market_impact = 0.0  # Price movement caused by the order
        self.timing_cost = 0.0  # Cost due to timing of trades
        self.fee_cost = 0.0  # Exchange fees and other explicit costs
        self.total_cost = 0.0  # Total execution cost
        
        # Execution quality metrics
        self.fill_rate = 0.0  # Percentage of order filled
        self.time_to_fill = 0.0  # Time from order submission to fill
        self.price_improvement = 0.0  # Better price than expected
        self.partial_fills = 0  # Number of partial fills
        self.rejection_rate = 0.0  # Percentage of orders rejected
        self.cancellation_rate = 0.0  # Percentage of orders cancelled
        
        # Market condition metrics
        self.spread_at_execution = 0.0  # Bid-ask spread at execution time
        self.market_volatility = 0.0  # Market volatility during execution
        self.liquidity_consumed = 0.0  # Amount of liquidity consumed
        self.executed_during_adverse_move = False  # Whether execution happened during adverse price move
        
        # Performance vs benchmarks
        self.vwap_performance = 0.0  # Performance vs VWAP
        self.arrival_performance = 0.0  # Performance vs arrival price
        self.benchmark_performances = {}  # Performance vs other benchmarks
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {k: v for k, v in self.__dict__.items()}
    
    def from_dict(self, metrics_dict: Dict[str, Any]) -> None:
        """Load metrics from dictionary."""
        for k, v in metrics_dict.items():
            if hasattr(self, k):
                setattr(self, k, v)


class ExecutionAnalyzer:
    """
    Analyzer for execution quality and transaction costs.
    
    This class provides tools for analyzing execution performance,
    calculating transaction costs, and measuring market impact.
    """
    
    def __init__(self):
        """Initialize execution analyzer."""
        # Store historical executions for analysis
        self.executions: List[Dict[str, Any]] = []
        # Store metrics for each execution
        self.metrics: Dict[str, ExecutionMetrics] = {}
    
    def add_execution(self, 
                     order: Order, 
                     market_data: Dict[str, Any],
                     benchmark_prices: Optional[Dict[str, float]] = None) -> str:
        """
        Add an execution for analysis.
        
        Args:
            order: The executed order
            market_data: Market data during execution (e.g., bid, ask, etc.)
            benchmark_prices: Optional benchmark prices for comparison
            
        Returns:
            Execution ID (matches order ID)
        """
        execution_id = order.exchange_order_id or str(hash(order))
        
        execution = {
            "execution_id": execution_id,
            "order": order,
            "market_data": market_data,
            "benchmark_prices": benchmark_prices or {},
            "timestamp": datetime.now(),
            "analyzed": False
        }
        
        self.executions.append(execution)
        self.metrics[execution_id] = ExecutionMetrics()
        
        logger.info(f"Added execution {execution_id} for analysis")
        return execution_id
    
    def analyze_execution(self, execution_id: str) -> ExecutionMetrics:
        """
        Analyze an execution and calculate metrics.
        
        Args:
            execution_id: ID of the execution to analyze
            
        Returns:
            Execution metrics
            
        Raises:
            ValueError: If execution ID is not found
        """
        # Find the execution
        execution = next((e for e in self.executions if e["execution_id"] == execution_id), None)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        # Create metrics instance
        metrics = ExecutionMetrics()
        
        # Extract order and market data
        order = execution["order"]
        market_data = execution["market_data"]
        benchmark_prices = execution["benchmark_prices"]
        
        # Skip if order was not filled
        if order.status != OrderStatus.FILLED and order.status != OrderStatus.PARTIALLY_FILLED:
            logger.warning(f"Order {execution_id} not filled, skipping analysis")
            self.metrics[execution_id] = metrics
            return metrics
        
        # Calculate basic metrics
        metrics.fill_rate = order.filled_quantity / order.params.quantity if order.params.quantity > 0 else 0.0
        metrics.partial_fills = 1 if order.status == OrderStatus.PARTIALLY_FILLED else 0
        
        # Calculate timing metrics if timestamps available
        if order.created_at and order.updated_at:
            metrics.time_to_fill = (order.updated_at - order.created_at).total_seconds()
        
        # Calculate spread if bid/ask available
        if 'bid' in market_data and 'ask' in market_data:
            metrics.spread_at_execution = market_data['ask'] - market_data['bid']
        
        # Calculate slippage
        expected_price = order.params.price if order.params.price else market_data.get('mid', market_data.get('last', 0))
        if order.average_price:
            # For buy orders, slippage is positive if executed price is higher than expected
            # For sell orders, slippage is positive if executed price is lower than expected
            if order.params.side == OrderSide.BUY:
                metrics.slippage = (order.average_price - expected_price) / expected_price if expected_price > 0 else 0
            else:
                metrics.slippage = (expected_price - order.average_price) / expected_price if expected_price > 0 else 0
        
        # Calculate fee cost
        metrics.fee_cost = order.fee if order.fee else 0.0
        
        # Calculate market impact if we have price before and after
        if 'price_before' in market_data and 'price_after' in market_data:
            price_before = market_data['price_before']
            price_after = market_data['price_after']
            
            # For buy orders, positive impact means price increased
            # For sell orders, positive impact means price decreased
            if order.params.side == OrderSide.BUY:
                metrics.market_impact = (price_after - price_before) / price_before if price_before > 0 else 0
            else:
                metrics.market_impact = (price_before - price_after) / price_before if price_before > 0 else 0
        
        # Calculate implementation shortfall
        arrival_price = benchmark_prices.get(BenchmarkType.ARRIVAL, expected_price)
        if order.average_price and arrival_price > 0:
            if order.params.side == OrderSide.BUY:
                metrics.implementation_shortfall = (order.average_price - arrival_price) / arrival_price
            else:
                metrics.implementation_shortfall = (arrival_price - order.average_price) / arrival_price
        
        # Calculate performance vs benchmarks
        for benchmark_type, benchmark_price in benchmark_prices.items():
            if order.average_price and benchmark_price > 0:
                if order.params.side == OrderSide.BUY:
                    performance = (benchmark_price - order.average_price) / benchmark_price
                else:
                    performance = (order.average_price - benchmark_price) / benchmark_price
                
                metrics.benchmark_performances[benchmark_type] = performance
                
                # Set specific benchmark performances
                if benchmark_type == BenchmarkType.VWAP:
                    metrics.vwap_performance = performance
                elif benchmark_type == BenchmarkType.ARRIVAL:
                    metrics.arrival_performance = performance
        
        # Calculate total cost
        metrics.total_cost = metrics.implementation_shortfall + metrics.fee_cost
        
        # Store the metrics
        self.metrics[execution_id] = metrics
        
        # Mark execution as analyzed
        execution["analyzed"] = True
        
        return metrics
    
    def get_metrics(self, execution_id: str) -> ExecutionMetrics:
        """
        Get metrics for an execution.
        
        Args:
            execution_id: ID of the execution
            
        Returns:
            Execution metrics
            
        Raises:
            ValueError: If execution ID is not found
        """
        if execution_id not in self.metrics:
            raise ValueError(f"Execution {execution_id} not found")
        
        # If execution hasn't been analyzed, analyze it first
        execution = next((e for e in self.executions if e["execution_id"] == execution_id), None)
        if execution and not execution["analyzed"]:
            return self.analyze_execution(execution_id)
        
        return self.metrics[execution_id]
    
    def analyze_all_executions(self) -> Dict[str, ExecutionMetrics]:
        """
        Analyze all executions and return metrics.
        
        Returns:
            Dictionary mapping execution IDs to metrics
        """
        for execution in self.executions:
            if not execution["analyzed"]:
                self.analyze_execution(execution["execution_id"])
        
        return self.metrics
    
    def get_execution_summary(self) -> pd.DataFrame:
        """
        Generate a summary of all executions.
        
        Returns:
            DataFrame with execution summaries
        """
        # Ensure all executions are analyzed
        self.analyze_all_executions()
        
        # Create summary dataframe
        summary_data = []
        
        for execution in self.executions:
            execution_id = execution["execution_id"]
            order = execution["order"]
            metrics = self.metrics[execution_id]
            
            summary_data.append({
                "execution_id": execution_id,
                "symbol": order.params.symbol,
                "side": order.params.side.value,
                "order_type": order.params.order_type.value,
                "quantity": order.params.quantity,
                "filled_quantity": order.filled_quantity,
                "fill_rate": metrics.fill_rate,
                "expected_price": order.params.price,
                "execution_price": order.average_price,
                "slippage": metrics.slippage,
                "market_impact": metrics.market_impact,
                "implementation_shortfall": metrics.implementation_shortfall,
                "total_cost": metrics.total_cost,
                "time_to_fill": metrics.time_to_fill,
                "timestamp": execution["timestamp"]
            })
        
        return pd.DataFrame(summary_data)
    
    def plot_execution_costs(self, 
                           execution_ids: Optional[List[str]] = None, 
                           aggregate: bool = False) -> Tuple[Figure, Axes]:
        """
        Plot execution costs.
        
        Args:
            execution_ids: List of execution IDs to plot, or None for all
            aggregate: Whether to aggregate costs or show individually
            
        Returns:
            Figure and Axes for the plot
        """
        # Ensure all executions are analyzed
        self.analyze_all_executions()
        
        # Get executions to plot
        if execution_ids is None:
            execution_ids = [e["execution_id"] for e in self.executions]
        
        # Collect data for plotting
        data = []
        for execution_id in execution_ids:
            metrics = self.metrics.get(execution_id)
            if metrics:
                execution = next((e for e in self.executions if e["execution_id"] == execution_id), None)
                if execution:
                    data.append({
                        "execution_id": execution_id,
                        "symbol": execution["order"].params.symbol,
                        "implementation_shortfall": metrics.implementation_shortfall,
                        "fee_cost": metrics.fee_cost,
                        "market_impact": metrics.market_impact,
                        "timing_cost": metrics.timing_cost,
                        "side": execution["order"].params.side.value
                    })
        
        if not data:
            raise ValueError("No execution data available for plotting")
            
        # Create dataframe
        df = pd.DataFrame(data)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if aggregate:
            # Aggregate costs
            costs = {
                "Implementation Shortfall": df["implementation_shortfall"].mean(),
                "Fee Cost": df["fee_cost"].mean(),
                "Market Impact": df["market_impact"].mean(),
                "Timing Cost": df["timing_cost"].mean()
            }
            
            # Plot stacked bar
            ax.bar(list(costs.keys()), list(costs.values()), color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'])
            ax.set_title("Average Execution Costs")
            ax.set_ylabel("Cost (bps)")
            
            # Add total
            total = sum(costs.values())
            ax.text(len(costs) - 0.5, total + 0.0005, f"Total: {total:.4f}", 
                   ha='center', va='bottom', fontweight='bold')
        else:
            # Plot individual executions
            symbols = df["symbol"].unique()
            x = range(len(symbols))
            
            # Calculate costs by symbol
            symbol_costs = {symbol: {} for symbol in symbols}
            for symbol in symbols:
                symbol_df = df[df["symbol"] == symbol]
                symbol_costs[symbol] = {
                    "Implementation Shortfall": symbol_df["implementation_shortfall"].mean(),
                    "Fee Cost": symbol_df["fee_cost"].mean(),
                    "Market Impact": symbol_df["market_impact"].mean(),
                    "Timing Cost": symbol_df["timing_cost"].mean()
                }
            
            # Plot stacked bars for each symbol
            width = 0.5
            bottom = np.zeros(len(symbols))
            
            for cost_type, color in zip(
                ["Implementation Shortfall", "Fee Cost", "Market Impact", "Timing Cost"],
                ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
            ):
                values = [symbol_costs[symbol][cost_type] for symbol in symbols]
                ax.bar(x, values, width, bottom=bottom, label=cost_type, color=color)
                bottom += values
            
            ax.set_title("Execution Costs by Symbol")
            ax.set_ylabel("Cost (bps)")
            ax.set_xticks(x)
            ax.set_xticklabels(symbols, rotation=45)
            ax.legend()
            
            # Add totals
            for i, symbol in enumerate(symbols):
                total = sum(symbol_costs[symbol].values())
                ax.text(i, total + 0.0005, f"{total:.4f}", 
                       ha='center', va='bottom', fontweight='bold')
        
        # Formatting
        plt.tight_layout()
        return fig, ax
    
    def plot_benchmark_comparison(self, 
                                execution_ids: Optional[List[str]] = None) -> Tuple[Figure, Axes]:
        """
        Plot execution performance vs benchmarks.
        
        Args:
            execution_ids: List of execution IDs to plot, or None for all
            
        Returns:
            Figure and Axes for the plot
        """
        # Ensure all executions are analyzed
        self.analyze_all_executions()
        
        # Get executions to plot
        if execution_ids is None:
            execution_ids = [e["execution_id"] for e in self.executions]
        
        # Collect data for plotting
        data = []
        for execution_id in execution_ids:
            metrics = self.metrics.get(execution_id)
            if metrics and metrics.benchmark_performances:
                execution = next((e for e in self.executions if e["execution_id"] == execution_id), None)
                if execution:
                    for benchmark_type, performance in metrics.benchmark_performances.items():
                        data.append({
                            "execution_id": execution_id,
                            "symbol": execution["order"].params.symbol,
                            "benchmark": benchmark_type,
                            "performance": performance,
                            "side": execution["order"].params.side.value
                        })
        
        if not data:
            raise ValueError("No benchmark data available for plotting")
            
        # Create dataframe
        df = pd.DataFrame(data)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Group by benchmark and calculate average performance
        benchmark_performance = df.groupby("benchmark")["performance"].mean().reset_index()
        
        # Sort by performance
        benchmark_performance = benchmark_performance.sort_values("performance", ascending=False)
        
        # Plot bars
        colors = ['#1f77b4' if p > 0 else '#d62728' for p in benchmark_performance["performance"]]
        ax.bar(benchmark_performance["benchmark"], benchmark_performance["performance"], color=colors)
        
        # Add horizontal line at zero
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        # Add labels and title
        ax.set_title("Execution Performance vs Benchmarks")
        ax.set_ylabel("Performance (bps)")
        ax.set_xlabel("Benchmark")
        
        # Formatting
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        return fig, ax


class ExecutionQualityMonitor:
    """
    Monitor for tracking execution quality over time.
    
    This class provides tools for monitoring execution quality metrics
    over time and generating alerts when metrics fall outside acceptable ranges.
    """
    
    def __init__(self):
        """Initialize execution quality monitor."""
        # Store execution metrics over time
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Alert thresholds
        self.thresholds: Dict[str, Dict[str, float]] = {
            "slippage": {"warning": 0.001, "critical": 0.002},  # 10/20 bps
            "implementation_shortfall": {"warning": 0.002, "critical": 0.004},  # 20/40 bps
            "fill_rate": {"warning": 0.9, "critical": 0.8},  # 90%/80%
            "market_impact": {"warning": 0.001, "critical": 0.002},  # 10/20 bps
            "rejection_rate": {"warning": 0.05, "critical": 0.1}  # 5%/10%
        }
        
        # Store alerts
        self.alerts: List[Dict[str, Any]] = []
    
    def add_metrics(self, 
                  symbol: str, 
                  metrics: ExecutionMetrics, 
                  timestamp: Optional[datetime] = None) -> None:
        """
        Add metrics to history.
        
        Args:
            symbol: Trading symbol
            metrics: Execution metrics
            timestamp: Optional timestamp, defaults to now
        """
        if symbol not in self.metrics_history:
            self.metrics_history[symbol] = []
            
        self.metrics_history[symbol].append({
            "metrics": metrics.to_dict(),
            "timestamp": timestamp or datetime.now()
        })
        
        # Check for alerts
        self._check_alerts(symbol, metrics)
    
    def _check_alerts(self, symbol: str, metrics: ExecutionMetrics) -> None:
        """
        Check metrics against thresholds and generate alerts.
        
        Args:
            symbol: Trading symbol
            metrics: Execution metrics
        """
        for metric_name, thresholds in self.thresholds.items():
            metric_value = getattr(metrics, metric_name, 0)
            
            # Special handling for fill_rate (higher is better)
            if metric_name == "fill_rate":
                if metric_value < thresholds["critical"]:
                    self._add_alert(symbol, metric_name, metric_value, "critical")
                elif metric_value < thresholds["warning"]:
                    self._add_alert(symbol, metric_name, metric_value, "warning")
            else:
                # For other metrics, lower is better
                if metric_value > thresholds["critical"]:
                    self._add_alert(symbol, metric_name, metric_value, "critical")
                elif metric_value > thresholds["warning"]:
                    self._add_alert(symbol, metric_name, metric_value, "warning")
    
    def _add_alert(self, 
                 symbol: str, 
                 metric_name: str, 
                 metric_value: float, 
                 severity: str) -> None:
        """
        Add an alert.
        
        Args:
            symbol: Trading symbol
            metric_name: Name of the metric
            metric_value: Value of the metric
            severity: Alert severity
        """
        alert = {
            "symbol": symbol,
            "metric": metric_name,
            "value": metric_value,
            "severity": severity,
            "threshold": self.thresholds[metric_name][severity],
            "timestamp": datetime.now()
        }
        
        self.alerts.append(alert)
        
        # Log the alert
        logger.warning(f"Execution quality alert: {severity} {metric_name} for {symbol}: {metric_value:.6f}")
    
    def get_recent_metrics(self, 
                         symbol: str, 
                         lookback: timedelta = timedelta(days=1)) -> pd.DataFrame:
        """
        Get recent metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            lookback: Lookback period
            
        Returns:
            DataFrame with metrics
        """
        if symbol not in self.metrics_history:
            return pd.DataFrame()
            
        # Get metrics within lookback period
        cutoff = datetime.now() - lookback
        recent_metrics = [
            {**entry["metrics"], "timestamp": entry["timestamp"]}
            for entry in self.metrics_history[symbol]
            if entry["timestamp"] >= cutoff
        ]
        
        return pd.DataFrame(recent_metrics)
    
    def get_alerts(self, 
                 severity: Optional[str] = None, 
                 lookback: timedelta = timedelta(days=1)) -> pd.DataFrame:
        """
        Get recent alerts.
        
        Args:
            severity: Optional severity filter
            lookback: Lookback period
            
        Returns:
            DataFrame with alerts
        """
        # Filter alerts by severity and time
        cutoff = datetime.now() - lookback
        filtered_alerts = [
            alert for alert in self.alerts
            if alert["timestamp"] >= cutoff and
               (severity is None or alert["severity"] == severity)
        ]
        
        return pd.DataFrame(filtered_alerts)
    
    def plot_metrics_trend(self, 
                         symbol: str, 
                         metric_name: str,
                         lookback: timedelta = timedelta(days=7)) -> Tuple[Figure, Axes]:
        """
        Plot metrics trend over time.
        
        Args:
            symbol: Trading symbol
            metric_name: Metric to plot
            lookback: Lookback period
            
        Returns:
            Figure and Axes for the plot
        """
        # Get recent metrics
        metrics_df = self.get_recent_metrics(symbol, lookback)
        
        if metrics_df.empty or metric_name not in metrics_df.columns:
            raise ValueError(f"No data available for {metric_name} on {symbol}")
            
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot metric trend
        ax.plot(metrics_df["timestamp"], metrics_df[metric_name], 
               marker='o', linestyle='-', color='#1f77b4')
        
        # Add thresholds if available
        if metric_name in self.thresholds:
            if metric_name == "fill_rate":
                # For fill_rate, thresholds are lower bounds
                ax.axhline(y=self.thresholds[metric_name]["warning"], 
                          color='#ff7f0e', linestyle='--', alpha=0.7,
                          label=f"Warning ({self.thresholds[metric_name]['warning']:.4f})")
                ax.axhline(y=self.thresholds[metric_name]["critical"], 
                          color='#d62728', linestyle='--', alpha=0.7,
                          label=f"Critical ({self.thresholds[metric_name]['critical']:.4f})")
            else:
                # For other metrics, thresholds are upper bounds
                ax.axhline(y=self.thresholds[metric_name]["warning"], 
                          color='#ff7f0e', linestyle='--', alpha=0.7,
                          label=f"Warning ({self.thresholds[metric_name]['warning']:.4f})")
                ax.axhline(y=self.thresholds[metric_name]["critical"], 
                          color='#d62728', linestyle='--', alpha=0.7,
                          label=f"Critical ({self.thresholds[metric_name]['critical']:.4f})")
        
        # Add labels and title
        metric_label = metric_name.replace('_', ' ').title()
        ax.set_title(f"{metric_label} Trend for {symbol}")
        ax.set_ylabel(metric_label)
        ax.set_xlabel("Time")
        
        # Add legend
        ax.legend()
        
        # Formatting
        plt.tight_layout()
        
        return fig, ax 