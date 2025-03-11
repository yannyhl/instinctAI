"""
Strategy Risk Integration Example

This example demonstrates how to integrate the risk management system with trading strategies
using the StrategyRiskAdapter. It shows:

1. How to wrap a strategy with the risk adapter
2. How the adapter validates signals and trades against risk parameters
3. How risk-adjusted position sizing works
4. How portfolio-level risk constraints affect trading
5. How correlation risk management adjusts allocations

This serves as a practical implementation guide for incorporating risk management
into any trading strategy.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Import trading strategy components
from advanced_trading.strategies.statistical.statistical_arbitrage import StatisticalArbitrageStrategy
from advanced_trading.strategies.hybrid.advanced_crypto_strategy import AdvancedCryptoStrategy
from advanced_trading.strategies.meta.adaptive_meta_strategy import AdaptiveMetaStrategy

# Import risk management components
from advanced_trading.execution.risk_integration.strategy_risk_adapter import StrategyRiskAdapter
from advanced_trading.execution.risk_integration.risk_manager import ExecutionRiskConfig
from advanced_trading.execution.risk_integration.correlation_risk import CorrelationRiskManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("strategy_risk_example")


def generate_sample_data() -> Dict[str, Dict[str, pd.DataFrame]]:
    """Generate sample market data for demonstration purposes."""
    # Date range for sample data
    dates = pd.date_range(start=datetime.now() - timedelta(days=60),
                         end=datetime.now(),
                         freq='1H')
    
    # Generate sample data for BTC and ETH
    symbols = ['BTC', 'ETH', 'SOL', 'BNB']
    data_dict = {}
    
    for symbol in symbols:
        # Start with a base price
        base_price = 50000 if symbol == 'BTC' else 3000 if symbol == 'ETH' else 100 if symbol == 'SOL' else 400
        
        # Generate price series with some randomness and trend
        noise = np.random.normal(0, 1, len(dates))
        trend = np.linspace(0, 20, len(dates))
        prices = base_price + trend + noise * (base_price * 0.01)  # 1% price volatility
        
        # Generate OHLCV data
        ohlcv_data = pd.DataFrame({
            'open': prices,
            'high': prices * (1 + np.random.uniform(0, 0.01, len(dates))),  # 0-1% higher
            'low': prices * (1 - np.random.uniform(0, 0.01, len(dates))),   # 0-1% lower
            'close': prices * (1 + np.random.normal(0, 0.005, len(dates))),  # Closing price with some noise
            'volume': np.random.uniform(1000, 5000, len(dates)) * (base_price / 1000)  # Volume scaled by price
        }, index=dates)
        
        # Create orderbook data (simplified)
        orderbook_data = pd.DataFrame({
            'bid_price': prices * 0.999,  # 0.1% below price
            'bid_size': np.random.uniform(1, 10, len(dates)),
            'ask_price': prices * 1.001,  # 0.1% above price
            'ask_size': np.random.uniform(1, 10, len(dates))
        }, index=dates)
        
        # Optional funding rate data for funding arbitrage
        funding_data = pd.DataFrame({
            'rate': np.random.normal(0.0001, 0.0005, len(dates)),  # ~0.01% average
            'predicted_rate': np.random.normal(0.0001, 0.0003, len(dates))
        }, index=dates)
        
        # Store in data dictionary
        data_dict[symbol] = {
            'ohlcv': ohlcv_data,
            'orderbook': orderbook_data,
            'funding_rates': funding_data
        }
    
    return data_dict


def example_statistical_arbitrage_with_risk():
    """Demonstrate statistical arbitrage with risk management."""
    logger.info("===== Starting Statistical Arbitrage with Risk Management Example =====")
    
    # Generate sample market data
    data_dict = generate_sample_data()
    symbols = list(data_dict.keys())
    
    # Create a statistical arbitrage strategy
    strategy = StatisticalArbitrageStrategy(
        symbols=symbols,
        lookback_period=30,
        entry_threshold=2.0,
        exit_threshold=0.5,
        stop_loss_threshold=3.0,
        max_positions=2
    )
    
    # Create custom risk configuration
    risk_config = ExecutionRiskConfig(
        max_position_size_percent=0.05,  # 5% maximum position size
        max_daily_loss=0.02,             # 2% maximum daily loss
        max_portfolio_drawdown=0.10,     # 10% maximum drawdown
        max_slippage_percent=0.01,       # 1% maximum slippage
        enforce_pre_trade_checks=True
    )
    
    # Create risk adapter with the strategy
    risk_adapted_strategy = StrategyRiskAdapter(
        strategy=strategy,
        risk_config=risk_config,
        enable_position_validation=True,
        enable_portfolio_validation=True,
        enable_adaptive_sizing=True,
        enable_correlation_management=True,  # Enable correlation management
        max_position_size_pct=0.05,
        max_position_loss_pct=0.02,
        correlations_limit=0.7  # Maximum allowed correlation
    )
    
    # Trading simulation with initial capital
    initial_capital = 100000  # $100,000 initial capital
    
    # Execute trades with risk management
    trades = risk_adapted_strategy.execute_trades(data_dict, initial_capital)
    
    # Display results
    logger.info(f"Executed {len(trades)} trades with risk management")
    
    # Analyze performance with risk insights
    if trades:
        performance = risk_adapted_strategy.analyze_performance(trades)
        
        logger.info(f"Strategy Performance:")
        logger.info(f"Total Trades: {performance.get('total_trades', 0)}")
        logger.info(f"Win Rate: {performance.get('win_rate', 0):.2%}")
        logger.info(f"Profit Factor: {performance.get('profit_factor', 0):.2f}")
        
        # Display risk insights
        risk_insights = performance.get('risk_insights', {})
        logger.info(f"Risk Level: {risk_insights.get('risk_level', 'unknown')}")
        logger.info(f"Max Drawdown: {risk_insights.get('max_drawdown', 0):.2%}")
        logger.info(f"Value at Risk (95%): {risk_insights.get('var_95', 0):.2%}")
        
        # Display correlation insights if available
        correlation = risk_insights.get('correlation', {})
        if correlation:
            logger.info(f"Correlation Regime: {correlation.get('regime', 'unknown')}")
            logger.info(f"Correlation Risk Level: {correlation.get('risk_level', 'unknown')}")
            logger.info(f"Average Correlation: {correlation.get('avg_correlation', 0):.2f}")
            logger.info(f"Diversification Score: {correlation.get('diversification_score', 0):.2f}")
        
        # Risk validation statistics
        validations = risk_insights.get('risk_validations', {})
        logger.info(f"Risk Validations: {validations.get('total_checks', 0)} total checks")
        logger.info(f"  Passed: {validations.get('passed', 0)}")
        logger.info(f"  Warnings: {validations.get('warnings', 0)}")
        logger.info(f"  Failures: {validations.get('failures', 0)}")


def example_hybrid_strategy_with_risk():
    """Demonstrate advanced crypto strategy with risk management."""
    logger.info("===== Starting Advanced Crypto Strategy with Risk Management Example =====")
    
    # Generate sample market data
    data_dict = generate_sample_data()
    symbols = list(data_dict.keys())
    
    # Create advanced crypto strategy
    strategy = AdvancedCryptoStrategy(
        symbols=symbols,
        short_window=20,
        long_window=50,
        max_position_size=0.1,
        base_risk_per_trade=0.01,
        dynamic_stop_loss=True
    )
    
    # Create risk adapter with more conservative settings
    risk_adapted_strategy = StrategyRiskAdapter(
        strategy=strategy,
        enable_position_validation=True,
        enable_portfolio_validation=True,
        enable_adaptive_sizing=True,
        enable_correlation_management=True,
        max_position_size_pct=0.03,  # More conservative than strategy's default
        max_position_loss_pct=0.015,  # More conservative than strategy's default
        max_portfolio_drawdown=0.10,
        correlations_limit=0.65
    )
    
    # Trading simulation
    initial_capital = 100000  # $100,000 initial capital
    executed_trades = []
    
    # Simulate multiple trading periods
    logger.info("Simulating multiple trading periods...")
    
    for i in range(5):
        # Update data slightly to simulate market changes
        for symbol in symbols:
            # Shift data by a small random amount
            shift_pct = np.random.normal(0, 0.005)  # 0.5% standard deviation
            data_dict[symbol]['ohlcv']['close'] *= (1 + shift_pct)
            data_dict[symbol]['ohlcv']['open'] *= (1 + shift_pct)
            data_dict[symbol]['ohlcv']['high'] *= (1 + shift_pct)
            data_dict[symbol]['ohlcv']['low'] *= (1 + shift_pct)
        
        # Execute trades with risk management
        period_trades = risk_adapted_strategy.execute_trades(data_dict, initial_capital)
        executed_trades.extend(period_trades)
        
        logger.info(f"Period {i+1}: Executed {len(period_trades)} trades")
    
    # Analyze performance
    if executed_trades:
        performance = risk_adapted_strategy.analyze_performance(executed_trades)
        
        logger.info(f"Strategy Performance after {len(executed_trades)} total trades:")
        logger.info(f"Win Rate: {performance.get('win_rate', 0):.2%}")
        logger.info(f"Average Profit: {performance.get('average_profit_pct', 0):.2%}")
        
        # Risk metrics
        risk_insights = performance.get('risk_insights', {})
        logger.info(f"Portfolio Risk Level: {risk_insights.get('risk_level', 'unknown')}")
        
        # Correlation metrics
        correlation = risk_insights.get('correlation', {})
        if correlation:
            logger.info(f"Correlation Regime: {correlation.get('regime', 'unknown')}")
            logger.info(f"Highly Correlated Pairs: {correlation.get('high_correlation_pairs_count', 0)}")
        
        # Position risk metrics
        position_metrics = risk_insights.get('position_metrics', {})
        for symbol, metrics in position_metrics.items():
            logger.info(f"{symbol} Risk Status: {metrics.get('risk_status', 'unknown')}")


def example_correlation_crisis_response():
    """Demonstrate how the system responds to a correlation crisis."""
    logger.info("===== Starting Correlation Crisis Response Example =====")
    
    # Generate normal sample data
    data_dict = generate_sample_data()
    symbols = list(data_dict.keys())
    
    # Create a strategy
    strategy = AdvancedCryptoStrategy(
        symbols=symbols,
        short_window=20,
        long_window=50
    )
    
    # Create risk adapter with correlation management
    risk_adapted_strategy = StrategyRiskAdapter(
        strategy=strategy,
        enable_correlation_management=True,
        correlations_limit=0.7,
        max_position_size_pct=0.1
    )
    
    # Initial capital
    initial_capital = 100000
    
    # Execute trades with normal correlation
    normal_trades = risk_adapted_strategy.execute_trades(data_dict, initial_capital)
    logger.info(f"Normal market conditions: Executed {len(normal_trades)} trades")
    
    # Get current correlation assessment
    if hasattr(risk_adapted_strategy, 'correlation_assessment'):
        corr_assessment = risk_adapted_strategy.correlation_assessment or {}
        logger.info(f"Normal correlation regime: {corr_assessment.get('regime', 'unknown')}")
        logger.info(f"Normal average correlation: {corr_assessment.get('avg_correlation', 0):.3f}")
    
    # Now simulate a correlation crisis by making all assets move together
    logger.info("Simulating a correlation crisis...")
    
    # Make all assets highly correlated
    base_move = np.random.normal(0, 0.02)  # 2% random move
    for symbol in symbols:
        # Apply same directional move to all assets with small variations
        move = base_move + np.random.normal(0, 0.002)  # Small variation
        data_dict[symbol]['ohlcv']['close'] *= (1 + move)
        data_dict[symbol]['ohlcv']['open'] *= (1 + move)
        data_dict[symbol]['ohlcv']['high'] *= (1 + move * 1.1)  # Slightly higher high
        data_dict[symbol]['ohlcv']['low'] *= (1 + move * 0.9)   # Slightly lower low
    
    # Manually inject correlation data to simulate crisis
    if hasattr(risk_adapted_strategy, 'correlation_manager') and risk_adapted_strategy.correlation_manager:
        # Create a fake return history with high correlation
        high_corr_returns = {}
        for symbol in symbols:
            # All assets have almost the same return (high correlation)
            high_corr_returns[symbol] = base_move + np.random.normal(0, 0.001)  # Very small variation
        
        # Update returns in the correlation manager
        risk_adapted_strategy.correlation_manager.update_returns(high_corr_returns)
        
        # Force correlation analysis
        risk_adapted_strategy.correlation_manager.analyze_correlation()
    
    # Execute trades during correlation crisis
    crisis_trades = risk_adapted_strategy.execute_trades(data_dict, initial_capital)
    logger.info(f"Crisis conditions: Executed {len(crisis_trades)} trades")
    
    # Get crisis correlation assessment
    if hasattr(risk_adapted_strategy, 'correlation_assessment'):
        corr_assessment = risk_adapted_strategy.correlation_assessment or {}
        logger.info(f"Crisis correlation regime: {corr_assessment.get('regime', 'unknown')}")
        logger.info(f"Crisis average correlation: {corr_assessment.get('avg_correlation', 0):.3f}")
        logger.info(f"Crisis risk level: {corr_assessment.get('risk_level', 'unknown')}")
        logger.info(f"Recommendation: {corr_assessment.get('recommendation', 'None')}")
    
    # Check for position adjustments
    adjusted_trades = [t for t in crisis_trades if t.get('correlation_adjusted', False)]
    logger.info(f"Correlation-adjusted trades: {len(adjusted_trades)}")
    
    # Check for risk-reducing trades
    risk_trades = [t for t in crisis_trades if t.get('risk_restricted', False)]
    logger.info(f"Risk-restricted trades: {len(risk_trades)}")
    
    if risk_trades:
        logger.info(f"Risk restriction source: {risk_trades[0].get('risk_source', 'unknown')}")
        logger.info(f"Risk level: {risk_trades[0].get('risk_level', 'unknown')}")


def example_meta_strategy_with_risk():
    """Demonstrate meta-strategy with risk management."""
    logger.info("===== Starting Meta-Strategy with Risk Management Example =====")
    
    # Generate sample market data
    data_dict = generate_sample_data()
    symbols = list(data_dict.keys())
    
    # Create individual strategies that will be managed by the meta-strategy
    stat_arb_strategy = StatisticalArbitrageStrategy(
        symbols=symbols,
        lookback_period=30,
        entry_threshold=2.0,
        exit_threshold=0.5
    )
    
    advanced_strategy = AdvancedCryptoStrategy(
        symbols=symbols,
        short_window=20,
        long_window=50
    )
    
    # Create meta-strategy that manages both strategies
    meta_strategy = AdaptiveMetaStrategy(
        symbols=symbols,
        strategies=[stat_arb_strategy, advanced_strategy],
        lookback_window=30,
        adaptation_speed=0.2
    )
    
    # Wrap meta-strategy with risk adapter
    risk_adapted_meta = StrategyRiskAdapter(
        strategy=meta_strategy,
        enable_position_validation=True,
        enable_portfolio_validation=True,
        enable_correlation_management=True,
        max_position_size_pct=0.04,
        max_position_loss_pct=0.02,
        max_portfolio_drawdown=0.12,
        correlations_limit=0.6
    )
    
    # Execute trades
    initial_capital = 100000
    trades = risk_adapted_meta.execute_trades(data_dict, initial_capital)
    
    logger.info(f"Meta-strategy executed {len(trades)} trades with risk management")
    
    # Analyze performance
    if trades:
        performance = risk_adapted_meta.analyze_performance(trades)
        
        logger.info(f"Meta-Strategy Performance:")
        logger.info(f"Total Trades: {performance.get('total_trades', 0)}")
        logger.info(f"Win Rate: {performance.get('win_rate', 0):.2%}")
        
        # Display risk insights
        risk_insights = performance.get('risk_insights', {})
        logger.info(f"Risk Level: {risk_insights.get('risk_level', 'unknown')}")
        logger.info(f"Max Drawdown: {risk_insights.get('max_drawdown', 0):.2%}")
        
        # Display correlation insights
        correlation = risk_insights.get('correlation', {})
        if correlation:
            logger.info(f"Correlation Regime: {correlation.get('regime', 'unknown')}")
            logger.info(f"Diversification Score: {correlation.get('diversification_score', 0):.2f}")


if __name__ == "__main__":
    try:
        logger.info("Starting strategy risk integration examples")
        
        # Run examples
        example_statistical_arbitrage_with_risk()
        example_hybrid_strategy_with_risk()
        example_correlation_crisis_response()  # Added correlation crisis example
        example_meta_strategy_with_risk()
        
        logger.info("All examples completed successfully")
    except Exception as e:
        logger.error(f"Error in examples: {str(e)}", exc_info=True) 