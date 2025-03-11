"""
Strategy Risk Adapter

This module provides a bridge between trading strategies and the risk management system.
It adapts the strategy execution workflow to incorporate risk validation and management
at various stages of the trading process.

The StrategyRiskAdapter wraps around strategies to ensure:

1. Pre-trade validation of all orders against risk parameters
2. Position-level risk monitoring for strategy positions
3. Portfolio-level risk constraint enforcement
4. Post-trade analysis of execution results
5. Adaptive position sizing based on risk parameters

This module is a key part of the risk integration layer, ensuring that all strategies
adhere to the system's risk management rules regardless of their implementation details.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union, Type
from datetime import datetime

from advanced_trading.strategies.base import BaseStrategy
from advanced_trading.execution.risk_integration.risk_manager import (
    ExecutionRiskManager,
    ExecutionRiskConfig,
    RiskCheckResult,
    RiskValidationStatus
)
from advanced_trading.execution.risk_integration.position_risk import (
    PositionRiskValidator,
    PositionRiskMetrics,
    PositionRiskStatus
)
from advanced_trading.execution.risk_integration.portfolio_risk import (
    PortfolioRiskIntegration, 
    PortfolioRiskMetrics,
    PortfolioRiskLevel
)
from advanced_trading.execution.risk_integration.correlation_risk import (
    CorrelationRiskManager,
    CorrelationRegime
)

logger = logging.getLogger(__name__)


class StrategyRiskAdapter:
    """
    Adapter that connects trading strategies with the risk management system.
    
    This class wraps around a strategy to enforce risk rules during the trading
    process. It intercepts strategy signals and execution requests, validates them
    against risk parameters, and can modify or reject actions that violate risk
    constraints.
    """
    
    def __init__(
        self,
        strategy: BaseStrategy,
        risk_config: Optional[ExecutionRiskConfig] = None,
        enable_position_validation: bool = True,
        enable_portfolio_validation: bool = True,
        enable_adaptive_sizing: bool = True,
        enable_correlation_management: bool = True,
        max_position_size_pct: float = 0.1,
        max_position_loss_pct: float = 0.05,
        max_portfolio_drawdown: float = 0.15,
        correlations_limit: float = 0.7
    ):
        """
        Initialize the strategy risk adapter.
        
        Args:
            strategy: The strategy instance to adapt
            risk_config: Configuration for the execution risk manager
            enable_position_validation: Whether to validate position-level risks
            enable_portfolio_validation: Whether to validate portfolio-level risks
            enable_adaptive_sizing: Whether to enable risk-based position sizing
            enable_correlation_management: Whether to manage correlation risk
            max_position_size_pct: Maximum position size as percentage of portfolio
            max_position_loss_pct: Maximum allowed loss for a position
            max_portfolio_drawdown: Maximum portfolio drawdown allowed
            correlations_limit: Maximum correlation between strategies
        """
        self.strategy = strategy
        self.strategy_name = strategy.__class__.__name__
        
        # Initialize risk components
        self.risk_config = risk_config or ExecutionRiskConfig(
            max_position_size_percent=max_position_size_pct,
            max_daily_loss=max_position_loss_pct,
            max_portfolio_drawdown=max_portfolio_drawdown
        )
        
        self.risk_manager = ExecutionRiskManager(self.risk_config)
        
        self.position_validator = PositionRiskValidator(
            max_position_size_pct=max_position_size_pct,
            max_position_loss_pct=max_position_loss_pct,
            correlation_limit=correlations_limit,
            enable_auto_stops=True,
            enable_size_scaling=enable_adaptive_sizing
        )
        
        self.portfolio_risk = PortfolioRiskIntegration(
            max_gross_exposure=self.risk_config.max_gross_exposure,
            max_net_exposure=self.risk_config.max_portfolio_drawdown,
            max_drawdown=max_portfolio_drawdown,
            max_correlation=correlations_limit
        )
        
        # Add correlation risk manager
        self.correlation_manager = CorrelationRiskManager(
            max_correlation_threshold=correlations_limit,
            lookback_periods=60,
            crisis_detection_threshold=0.85
        ) if enable_correlation_management else None
        
        # Configuration flags
        self.enable_position_validation = enable_position_validation
        self.enable_portfolio_validation = enable_portfolio_validation
        self.enable_adaptive_sizing = enable_adaptive_sizing
        self.enable_correlation_management = enable_correlation_management
        
        # Risk tracking
        self.risk_check_results = []
        self.position_metrics = {}
        self.portfolio_metrics = None
        self.correlation_assessment = None
        self._active_positions = {}
        self._trade_returns = {}  # Track returns for correlation analysis
        
        logger.info(f"Initialized risk adapter for strategy {self.strategy_name}")
    
    def generate_signal(self, data: Dict[str, Any], symbol: str) -> Tuple[int, Dict]:
        """
        Generate a risk-aware trading signal by wrapping the strategy's signal generator.
        
        Args:
            data: Market data for generating the signal
            symbol: Trading symbol
            
        Returns:
            Tuple of signal direction and details
        """
        # Generate the signal using the strategy
        signal, signal_details = self.strategy.generate_signal(data, symbol)
        
        # If no signal, return as is
        if signal == 0:
            return signal, signal_details
        
        # Validate the signal against position risk if enabled
        if self.enable_position_validation and symbol in data:
            # Calculate or update position metrics
            position_data = self._extract_position_data(symbol, data)
            
            # Determine portfolio contribution for risk calculation
            portfolio_data = self._extract_portfolio_data(data)
            
            # Calculate position metrics
            metrics = self.position_validator.calculate_position_metrics(
                symbol=symbol,
                position_data=position_data,
                market_data={"ohlcv": data},
                portfolio_data=portfolio_data
            )
            
            # Store metrics
            self.position_metrics[symbol] = metrics
            
            # Check risk status
            risk_status = metrics.risk_status
            
            # Modify signal based on risk status
            if risk_status in (PositionRiskStatus.AT_RISK, PositionRiskStatus.VIOLATED):
                logger.warning(f"Risk validation: {symbol} position {risk_status.value}, " 
                             f"risk-adjusted signal from {signal} to 0")
                signal_details["risk_adjusted"] = True
                signal_details["original_signal"] = signal
                signal_details["risk_status"] = risk_status.value
                
                # Cancel the signal due to risk violation
                return 0, signal_details
            
            # If signal is valid but we have adaptive sizing enabled, adjust size
            if self.enable_adaptive_sizing and "suggested_size" in signal_details:
                original_size = signal_details["suggested_size"]
                
                # Calculate risk-adjusted position size
                adjusted_size = self.position_validator.adjust_position_size(
                    symbol=symbol,
                    base_position_size=original_size,
                    market_data={"ohlcv": data},
                    portfolio_data=portfolio_data
                )
                
                # Update the signal details with adjusted size
                signal_details["suggested_size"] = adjusted_size
                signal_details["risk_adjusted"] = True
                signal_details["original_size"] = original_size
                
                logger.info(f"Risk-adjusted position size for {symbol}: {original_size:.4f} → {adjusted_size:.4f}")
        
        return signal, signal_details
    
    def execute_trades(self, data_dict: Dict[str, Dict[str, Any]], capital: float) -> List[Dict]:
        """
        Execute trades with risk validation and management.
        
        Args:
            data_dict: Dictionary of market data for each symbol
            capital: Available capital for trading
            
        Returns:
            List of executed trade dictionaries
        """
        # First, update portfolio metrics
        portfolio_data = self._extract_portfolio_data(data_dict)
        self.portfolio_metrics = self.portfolio_risk.update_portfolio_metrics(portfolio_data)
        
        # Update correlation data if enabled
        if self.enable_correlation_management and self.correlation_manager:
            self._update_correlation_data(portfolio_data)
            self.correlation_assessment = self.correlation_manager.get_risk_assessment()
            
            # Log correlation information
            if self.correlation_assessment.get('status') == 'ok':
                regime = self.correlation_assessment.get('regime', 'unknown')
                avg_corr = self.correlation_assessment.get('avg_correlation', 0.0)
                risk_level = self.correlation_assessment.get('risk_level', 'unknown')
                
                logger.info(f"Correlation regime: {regime}, Avg: {avg_corr:.2f}, Risk: {risk_level}")
                
                # Log highly correlated pairs
                high_corr_pairs = self.correlation_assessment.get('high_correlation_pairs', [])
                if high_corr_pairs:
                    logger.warning(f"Found {len(high_corr_pairs)} highly correlated pairs:")
                    for asset1, asset2, corr in high_corr_pairs[:3]:  # Show top 3
                        logger.warning(f"  {asset1}/{asset2}: {corr:.2f}")
        
        # Check if trading should be restricted based on portfolio risk or correlation crisis
        portfolio_high_risk = (
            self.enable_portfolio_validation and 
            self.portfolio_metrics and
            self.portfolio_metrics.portfolio_risk_level in (PortfolioRiskLevel.HIGH, PortfolioRiskLevel.CRITICAL)
        )
        
        correlation_high_risk = (
            self.enable_correlation_management and 
            self.correlation_assessment and
            self.correlation_assessment.get('risk_level') in ('elevated', 'critical') and
            self.correlation_assessment.get('regime') in ('high', 'crisis')
        )
        
        if portfolio_high_risk or correlation_high_risk:
            risk_source = "portfolio" if portfolio_high_risk else "correlation"
            risk_level = (
                self.portfolio_metrics.portfolio_risk_level.value if portfolio_high_risk
                else self.correlation_assessment.get('risk_level')
            )
            
            logger.warning(f"{risk_source.capitalize()} risk level {risk_level}, "
                          f"restricting new trades")
            
            # Only allow risk-reducing trades (exits) at high risk levels
            executed_trades = self._execute_risk_reducing_trades(data_dict, capital)
            
            # Add risk annotation to trades
            for trade in executed_trades:
                trade["risk_restricted"] = True
                trade["risk_source"] = risk_source
                trade["risk_level"] = risk_level
            
            return executed_trades
        
        # For normal risk levels, execute trades with pre and post validation
        proposed_trades = self.strategy.execute_trades(data_dict, capital)
        validated_trades = []
        
        # Validate each proposed trade
        for trade in proposed_trades:
            # Skip if not an entry trade (we always allow exits for risk management)
            if trade["action"] != "entry":
                validated_trades.append(trade)
                continue
            
            # Apply correlation-based position sizing if enabled
            if (self.enable_correlation_management and 
                self.correlation_manager and 
                "value" in trade and 
                trade.get("position_sizing", True)):  # Allow opting out
                
                # Get original size and adjust based on correlation
                symbol = trade["symbol"]
                original_value = trade["value"]
                original_quantity = trade["quantity"]
                
                # Calculate adjusted value based on correlation
                adjusted_value = self._apply_correlation_adjustment(symbol, original_value, capital)
                
                if adjusted_value != original_value:
                    # Adjust quantity proportionally
                    trade["quantity"] = original_quantity * (adjusted_value / original_value)
                    trade["value"] = adjusted_value
                    trade["correlation_adjusted"] = True
                    trade["original_value"] = original_value
                    
                    logger.info(f"Correlation-adjusted position: {symbol} from ${original_value:.2f} "
                               f"to ${adjusted_value:.2f}")
            
            # Create order structure for validation
            order = {
                "symbol": trade["symbol"],
                "side": trade["direction"],
                "type": "market",
                "quantity": trade["quantity"],
                "price": trade["price"],
                "notional_value": trade["value"],
                "timestamp": trade.get("timestamp", datetime.now())
            }
            
            # Pre-trade validation
            is_valid, results = self.risk_manager.is_order_valid(
                order=order,
                portfolio_state=portfolio_data,
                market_data=data_dict
            )
            
            # Store validation results
            self.risk_check_results.extend(results)
            
            if is_valid:
                # Trade passed validation
                validated_trades.append(trade)
            else:
                # Log the rejection
                failure_reasons = [r.message for r in results if r.status in (
                    RiskValidationStatus.FAILED, RiskValidationStatus.ERROR)]
                
                logger.warning(f"Rejected trade for {trade['symbol']} due to risk validation: {', '.join(failure_reasons)}")
                
                # Add rejection info to the trade
                trade["rejected"] = True
                trade["rejection_reasons"] = failure_reasons
        
        # If we have executed trades, update position tracking
        if validated_trades:
            self._update_position_tracking(validated_trades)
            
            # Perform post-trade analysis for entries
            entry_trades = [t for t in validated_trades if t["action"] == "entry"]
            for trade in entry_trades:
                # Create sample execution details
                execution_details = {
                    "executed_price": trade["price"],
                    "executed_quantity": trade["quantity"],
                    "executed_notional": trade["value"],
                    "execution_time": trade.get("timestamp", datetime.now()),
                    "market_price": trade["price"]  # Assume filled at market for now
                }
                
                # Create corresponding order
                order = {
                    "symbol": trade["symbol"],
                    "side": trade["direction"],
                    "type": "market",
                    "quantity": trade["quantity"],
                    "price": trade["price"],
                    "notional_value": trade["value"]
                }
                
                # Post-trade analysis
                analysis_results = self.risk_manager.analyze_execution(
                    order=order,
                    execution_details=execution_details,
                    portfolio_state=portfolio_data,
                    market_data=data_dict
                )
                
                # Store analysis results
                self.risk_check_results.extend(analysis_results)
        
        # Apply stop-loss and take-profit recommendations from risk system
        validated_trades = self._apply_risk_adjustments(validated_trades, data_dict)
        
        return validated_trades
    
    def _execute_risk_reducing_trades(self, data_dict: Dict[str, Dict[str, Any]], 
                                    capital: float) -> List[Dict]:
        """
        Execute only risk-reducing trades (exits) when portfolio risk is high.
        
        Args:
            data_dict: Dictionary of market data for each symbol
            capital: Available capital for trading
            
        Returns:
            List of executed risk-reducing trades
        """
        executed_trades = []
        
        # Identify at-risk positions
        at_risk_symbols = self.position_validator.get_at_risk_positions()
        
        # Execute exit trades for high-risk positions
        for symbol in at_risk_symbols:
            if symbol not in data_dict or symbol not in self._active_positions:
                continue
                
            position = self._active_positions[symbol]
            current_price = data_dict[symbol]["ohlcv"].iloc[-1]["close"]
            
            # Create exit trade
            exit_trade = {
                "symbol": symbol,
                "timestamp": datetime.now(),
                "action": "exit",
                "direction": "sell" if position["direction"] == "buy" else "buy",
                "price": current_price,
                "quantity": position["quantity"],
                "value": current_price * position["quantity"],
                "reason": "risk_reduction",
                "risk_adjustment": True
            }
            
            executed_trades.append(exit_trade)
            
            # Update position tracking
            del self._active_positions[symbol]
            
            logger.info(f"Executed risk-reducing exit for {symbol} at {current_price}")
        
        return executed_trades
    
    def _apply_risk_adjustments(self, trades: List[Dict], 
                              data_dict: Dict[str, Dict[str, Any]]) -> List[Dict]:
        """
        Apply stop-loss and take-profit recommendations from the risk system.
        
        Args:
            trades: List of executed trades
            data_dict: Dictionary of market data for each symbol
            
        Returns:
            Updated list of trades with risk adjustments
        """
        # Process only entry trades
        entry_trades = [t for t in trades if t["action"] == "entry"]
        
        for trade in entry_trades:
            symbol = trade["symbol"]
            
            # Skip if no data for this symbol
            if symbol not in data_dict:
                continue
                
            # Calculate stop levels from risk system
            position_data = {
                "size": trade["quantity"],
                "entry_price": trade["price"],
                "current_price": trade["price"],
                "direction": trade["direction"],
                "notional_value": trade["value"]
            }
            
            # Get stop recommendations
            stop_levels = self.position_validator.calculate_stop_levels(
                symbol=symbol,
                position_data=position_data,
                market_data={"ohlcv": data_dict[symbol]},
                risk_percent=0.01  # 1% risk per trade
            )
            
            # Add stop recommendations to trade
            trade["risk_stops"] = stop_levels
            
            # Add recommended take profit (if not already present)
            if "target_price" not in trade and "stop_loss" in stop_levels:
                stop_distance = abs(trade["price"] - stop_levels["stop_loss"])
                
                # Set take profit at 2:1 reward:risk ratio
                if trade["direction"] == "buy":
                    take_profit = trade["price"] + (2 * stop_distance)
                else:
                    take_profit = trade["price"] - (2 * stop_distance)
                    
                trade["target_price"] = take_profit
                trade["risk_adjusted"] = True
        
        return trades
    
    def _apply_correlation_adjustment(self, symbol: str, original_value: float, capital: float) -> float:
        """Apply correlation-based adjustment to position size."""
        if not self.correlation_manager or not self.correlation_assessment:
            return original_value
            
        # Get base position sizes (all positions should sum to 1.0)
        base_sizes = {symbol: original_value / capital}
        
        # Get adjusted sizes based on correlation
        adjusted_sizes = self.correlation_manager.calculate_optimal_position_sizes(base_sizes)
        
        # Get adjusted value
        adjusted_value = adjusted_sizes.get(symbol, original_value / capital) * capital
        
        return adjusted_value
    
    def _update_correlation_data(self, portfolio_data: Dict[str, Any]) -> None:
        """Update correlation data with latest returns."""
        if not self.correlation_manager:
            return
            
        # Extract returns for active positions
        returns = {}
        
        for symbol, position in portfolio_data.get('positions', {}).items():
            if symbol in self._trade_returns:
                prev_price = self._trade_returns[symbol]
                curr_price = position.get('current_price', 0)
                
                if prev_price > 0 and curr_price > 0:
                    # Calculate return
                    ret = (curr_price - prev_price) / prev_price
                    
                    # Adjust for direction
                    if position.get('direction', 'buy') == 'sell':
                        ret = -ret
                        
                    returns[symbol] = ret
            
            # Update stored price
            self._trade_returns[symbol] = position.get('current_price', 0)
        
        # Update correlation manager if we have returns
        if returns:
            self.correlation_manager.update_returns(returns)
            self.correlation_manager.analyze_correlation()
    
    def _extract_position_data(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract position data from market data and strategy state."""
        # Get latest price
        latest_price = None
        if "ohlcv" in data and not data["ohlcv"].empty:
            latest_price = data["ohlcv"].iloc[-1]["close"]
        
        # If we have an active position for this symbol
        if symbol in self._active_positions:
            position = self._active_positions[symbol]
            
            return {
                "symbol": symbol,
                "size": position["quantity"],
                "direction": position["direction"],
                "entry_price": position["entry_price"],
                "current_price": latest_price or position["current_price"],
                "entry_time": position["entry_time"],
                "notional_value": position["value"]
            }
        
        # Default to empty position
        return {
            "symbol": symbol,
            "size": 0,
            "direction": "flat",
            "entry_price": latest_price if latest_price else 0,
            "current_price": latest_price if latest_price else 0,
            "entry_time": datetime.now(),
            "notional_value": 0
        }
    
    def _extract_portfolio_data(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract portfolio data from market data and strategy state."""
        # Calculate total portfolio value from positions
        position_value = 0
        for symbol, position in self._active_positions.items():
            # Get current price for the symbol
            current_price = position.get("current_price", 0)
            
            # Update with latest price if available
            if symbol in data_dict and "ohlcv" in data_dict[symbol] and not data_dict[symbol]["ohlcv"].empty:
                current_price = data_dict[symbol]["ohlcv"].iloc[-1]["close"]
                
            # Calculate position value
            position_value += position.get("quantity", 0) * current_price
        
        # Sample portfolio data
        portfolio_data = {
            "total_value": position_value + self.strategy.capital if hasattr(self.strategy, "capital") else position_value,
            "position_value": position_value,
            "cash_balance": self.strategy.capital if hasattr(self.strategy, "capital") else 0,
            "positions": {
                symbol: {
                    "size": pos["quantity"],
                    "direction": pos["direction"],
                    "entry_price": pos["entry_price"],
                    "current_price": pos.get("current_price", 0),
                    "notional_value": pos["value"],
                    "entry_time": pos["entry_time"]
                }
                for symbol, pos in self._active_positions.items()
            }
        }
        
        return portfolio_data
    
    def _update_position_tracking(self, trades: List[Dict]) -> None:
        """Update position tracking based on executed trades."""
        # Process each trade
        for trade in trades:
            symbol = trade["symbol"]
            
            if trade["action"] == "entry":
                # New position or add to existing
                if symbol not in self._active_positions:
                    self._active_positions[symbol] = {
                        "symbol": symbol,
                        "quantity": trade["quantity"],
                        "direction": trade["direction"],
                        "entry_price": trade["price"],
                        "current_price": trade["price"],
                        "value": trade["value"],
                        "entry_time": trade.get("timestamp", datetime.now())
                    }
                else:
                    # Update existing position
                    existing = self._active_positions[symbol]
                    
                    # If same direction, average down/up
                    if existing["direction"] == trade["direction"]:
                        total_qty = existing["quantity"] + trade["quantity"]
                        total_value = existing["value"] + trade["value"]
                        
                        existing["quantity"] = total_qty
                        existing["value"] = total_value
                        existing["entry_price"] = total_value / total_qty if total_qty != 0 else existing["entry_price"]
                    else:
                        # If opposite direction, reduce position
                        if existing["quantity"] > trade["quantity"]:
                            # Partial reduction
                            existing["quantity"] -= trade["quantity"]
                            existing["value"] = existing["quantity"] * existing["entry_price"]
                        else:
                            # Position flips or closes
                            new_qty = trade["quantity"] - existing["quantity"]
                            
                            if new_qty > 0:
                                # Position flips direction
                                existing["quantity"] = new_qty
                                existing["direction"] = trade["direction"]
                                existing["entry_price"] = trade["price"]
                                existing["value"] = new_qty * trade["price"]
                                existing["entry_time"] = trade.get("timestamp", datetime.now())
                            else:
                                # Position closes exactly
                                del self._active_positions[symbol]
            
            elif trade["action"] == "exit":
                # Exit position
                if symbol in self._active_positions:
                    existing = self._active_positions[symbol]
                    
                    # If exit quantity equals position quantity, remove position
                    if abs(existing["quantity"] - trade["quantity"]) < 1e-8:
                        del self._active_positions[symbol]
                    else:
                        # Partial exit
                        existing["quantity"] -= trade["quantity"]
                        existing["value"] = existing["quantity"] * existing["entry_price"]
    
    def analyze_performance(self, trades: List[Dict]) -> Dict[str, Any]:
        """
        Analyze performance with risk insights.
        
        Args:
            trades: List of executed trade dictionaries
            
        Returns:
            Dictionary with performance metrics and risk insights
        """
        # Get the base performance analysis from the strategy
        performance = self.strategy.analyze_performance(trades)
        
        # Add risk metrics
        risk_insights = {
            "risk_level": self.portfolio_metrics.portfolio_risk_level.value if self.portfolio_metrics else "unknown",
            "max_drawdown": self.portfolio_metrics.max_drawdown if self.portfolio_metrics else 0.0,
            "var_95": self.portfolio_metrics.var_95 if self.portfolio_metrics else 0.0,
            "expected_shortfall": self.portfolio_metrics.expected_shortfall if self.portfolio_metrics else 0.0,
            "current_exposure": {
                "gross": self.portfolio_metrics.gross_exposure if self.portfolio_metrics else 0.0,
                "net": self.portfolio_metrics.net_exposure if self.portfolio_metrics else 0.0
            },
            "position_metrics": {
                symbol: {
                    "risk_status": metrics.risk_status.value,
                    "size_vs_limit": metrics.portfolio_contribution_percent / self.position_validator.max_position_size_pct,
                    "unrealized_pnl_percent": metrics.unrealized_pnl_percent,
                    "risk_reward_ratio": metrics.risk_reward_ratio,
                    "var_95_percent": metrics.var_95
                }
                for symbol, metrics in self.position_metrics.items()
            },
            "risk_validations": {
                "total_checks": len(self.risk_check_results),
                "passed": sum(1 for r in self.risk_check_results if r.status == RiskValidationStatus.PASSED),
                "warnings": sum(1 for r in self.risk_check_results if r.status == RiskValidationStatus.WARNING),
                "failures": sum(1 for r in self.risk_check_results if r.status == RiskValidationStatus.FAILED),
                "errors": sum(1 for r in self.risk_check_results if r.status == RiskValidationStatus.ERROR)
            }
        }
        
        # Add correlation insights if available
        if self.enable_correlation_management and self.correlation_assessment:
            corr_assessment = self.correlation_assessment
            
            if corr_assessment.get('status') == 'ok':
                risk_insights["correlation"] = {
                    "regime": corr_assessment.get('regime', 'unknown'),
                    "risk_level": corr_assessment.get('risk_level', 'unknown'),
                    "avg_correlation": corr_assessment.get('avg_correlation', 0.0),
                    "max_correlation": corr_assessment.get('max_correlation', 0.0),
                    "effective_positions": corr_assessment.get('effective_positions', 1.0),
                    "diversification_score": corr_assessment.get('diversification_score', 1.0),
                    "crisis_probability": corr_assessment.get('crisis_probability', 0.0),
                    "high_correlation_pairs_count": len(corr_assessment.get('high_correlation_pairs', []))
                }
        
        # Add risk insights to performance metrics
        performance["risk_insights"] = risk_insights
        
        return performance 