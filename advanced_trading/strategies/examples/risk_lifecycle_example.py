"""
Risk-Aware Strategy Lifecycle Management Example

This example demonstrates how to use the Risk-Aware Strategy Lifecycle Management system to:
1. Create and register strategies with risk limits
2. Initialize and warm up strategies with risk validation
3. Execute strategies with real-time risk monitoring
4. Respond to risk violations automatically
5. Track and analyze risk metrics during strategy execution

This serves as a comprehensive example of how the Strategy Lifecycle Management system 
integrates with the Risk Management system in the Instinct AI trading platform.
"""

import os
import time
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

from advanced_trading.strategies.base import Strategy, StrategyConfig, StrategyType, StrategyResult
from advanced_trading.strategies.risk_integration import RiskAwareStrategyLifecycleManager, RiskViolationError
from advanced_trading.strategies.examples.lifecycle_example import ExampleStrategy, generate_sample_data
from advanced_trading.execution.risk_integration.risk_manager import ExecutionRiskConfig
from advanced_trading.risk.portfolio.controller import PortfolioRiskController

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HighVolatilityStrategy(Strategy):
    """
    A strategy that intentionally takes high volatility positions for demonstration purposes.
    
    This strategy will generate signals with high position sizes that should trigger
    risk violations, demonstrating how the risk management system reacts.
    """
    
    # Strategy metadata
    STRATEGY_TYPE = StrategyType.TECHNICAL
    PARAMETERS = {
        "volatility_threshold": {"type": "float", "default": 0.02, "description": "Volatility threshold"},
        "position_size_multiplier": {"type": "float", "default": 5.0, "description": "Position size multiplier"}
    }
    REQUIRED_DATA = ["close"]
    
    def __init__(self, config: StrategyConfig):
        """Initialize the strategy."""
        super().__init__(config)
        self.volatility_threshold = 0.02
        self.position_size_multiplier = 5.0
        self.version = "1.0.0"
        self.author = "Instinct AI Team"
        self.tags = ["high_volatility", "risk_example"]
        
        # Internal state
        self._volatility = {}
        self._position = {}
        self._last_signal = {}
    
    def initialize(self, parameters: Optional[Dict[str, Any]] = None, 
                 dependencies: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the strategy."""
        logger.info(f"Initializing {self.name} strategy")
        
        # Set parameters
        if parameters:
            if "volatility_threshold" in parameters:
                self.volatility_threshold = parameters["volatility_threshold"]
            if "position_size_multiplier" in parameters:
                self.position_size_multiplier = parameters["position_size_multiplier"]
        
        # Initialize state
        for symbol in self.config.symbols:
            self._volatility[symbol] = None
            self._position[symbol] = 0.0
            self._last_signal[symbol] = None
        
        logger.info(f"Strategy {self.name} initialized with volatility_threshold={self.volatility_threshold}, " 
                   f"position_size_multiplier={self.position_size_multiplier}")
    
    def process_warmup_data(self, data: pd.DataFrame) -> None:
        """Process warm-up data."""
        logger.info(f"Processing warm-up data with {len(data)} rows")
        
        # Convert data to dict format expected by process_data
        symbols = self.config.symbols
        if len(symbols) == 1:
            data_dict = {symbols[0]: data}
        else:
            # Assume data has a 'symbol' column
            data_dict = {}
            for symbol in symbols:
                symbol_data = data[data['symbol'] == symbol] if 'symbol' in data.columns else data
                data_dict[symbol] = symbol_data
        
        # Process data
        self.process_data(data_dict)
        
        logger.info("Warm-up data processed")
    
    def process_data(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Process market data and calculate volatility."""
        result = {}
        
        for symbol, df in data.items():
            # Skip if symbol not in config
            if symbol not in self.config.symbols:
                continue
                
            # Calculate volatility
            if 'close' not in df.columns:
                logger.warning(f"Close price column not found in data for {symbol}")
                continue
                
            processed = df.copy()
            
            # Calculate 20-day rolling volatility
            processed['returns'] = processed['close'].pct_change()
            processed['volatility'] = processed['returns'].rolling(window=20).std() * np.sqrt(252)
            
            # Calculate signal based on volatility
            # If volatility is high, generate a buy signal with a large position size
            processed['signal'] = np.where(
                processed['volatility'] > self.volatility_threshold, 
                self.position_size_multiplier,  # Intentionally large position size
                0
            )
            
            # Update internal state
            if not processed.empty:
                self._volatility[symbol] = processed['volatility'].iloc[-1]
                self._last_signal[symbol] = processed['signal'].iloc[-1]
            
            result[symbol] = processed
            
        return result
    
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Generate trading signals."""
        signals = {}
        
        for symbol, df in data.items():
            signals_df = pd.DataFrame()
            signals_df['timestamp'] = df.index
            signals_df['signal'] = df['signal']
            signals_df['price'] = df['close']
            signals_df['volatility'] = df['volatility']
            
            # Only include rows with non-zero signals
            signals_df = signals_df[signals_df['signal'] != 0]
            
            signals[symbol] = signals_df
            
            # Update state with signals
            for _, row in signals_df.iterrows():
                self.state.add_signal(symbol, {
                    'timestamp': row['timestamp'],
                    'signal': row['signal'],
                    'price': row['price'],
                    'volatility': row['volatility']
                })
        
        return signals
    
    def execute(self, signals: Dict[str, pd.DataFrame]) -> StrategyResult:
        """Execute trading signals."""
        pnl = 0.0
        positions = {}
        trades = []
        
        for symbol, df in signals.items():
            if df.empty:
                continue
                
            for _, row in df.iterrows():
                old_position = self._position.get(symbol, 0.0)
                
                # Set new position based on signal
                # This will intentionally set a very large position size
                new_position = row['signal']
                
                # Record position change if any
                if new_position != old_position:
                    trades.append({
                        'timestamp': row['timestamp'],
                        'symbol': symbol,
                        'action': 'buy' if new_position > 0 else 'sell',
                        'price': row['price'],
                        'quantity': abs(new_position),
                        'position': new_position
                    })
                    
                    # Update position
                    self._position[symbol] = new_position
                    
                    # Update state with position
                    self.state.update_position(symbol, {
                        'timestamp': row['timestamp'],
                        'position': new_position,
                        'price': row['price'],
                        'volatility': row['volatility']
                    })
            
            positions[symbol] = self._position[symbol]
        
        # Create result
        result = StrategyResult(
            strategy_name=self.name,
            signals={s: df for s, df in signals.items() if not df.empty},
            positions=pd.DataFrame([
                {'symbol': s, 'position': p, 'timestamp': pd.Timestamp.now()}
                for s, p in positions.items()
            ]) if positions else None,
            pnl=pnl,
            trades=pd.DataFrame(trades) if trades else None,
            timestamp=pd.Timestamp.now()
        )
        
        return result


def generate_risk_limits(max_position_size=0.1, max_volatility=0.02):
    """Generate standard risk limits for a strategy."""
    return {
        "position": {
            "max_position_size": max_position_size,
            "max_drawdown": 0.05,
            "max_loss_per_trade": 0.02
        },
        "portfolio": {
            "max_exposure": 0.5,
            "max_correlation": 0.7,
            "max_concentration": 0.3
        },
        "market": {
            "max_volatility": max_volatility,
            "max_spread": 0.01,
            "max_slippage": 0.005
        }
    }


def main():
    """Run the risk-aware lifecycle management example."""
    # Create risk configuration
    risk_config = ExecutionRiskConfig(
        enabled=True,
        enforce_pre_trade_checks=True,
        max_position_size_percent=0.1,
        max_position_loss_pct=0.05,
        max_portfolio_drawdown=0.15,
        max_correlation_allowed=0.7
    )
    
    # Create portfolio risk controller
    portfolio_risk_controller = PortfolioRiskController(
        max_portfolio_exposure=1.0,
        max_correlation_exposure=0.4,
        drawdown_control_threshold=0.1,
        target_portfolio_volatility=0.15
    )
    
    # Create risk-aware strategy lifecycle manager
    lifecycle_manager = RiskAwareStrategyLifecycleManager(
        risk_config=risk_config,
        portfolio_risk_controller=portfolio_risk_controller,
        enforce_risk_limits=True,
        auto_adjust_position_sizes=True,
        emergency_stop_on_violation=True
    )
    
    # Create strategy configuration for a "normal" strategy
    symbols = ["BTC/USD", "ETH/USD"]
    normal_config = StrategyConfig(
        name="Normal Strategy",
        symbols=symbols,
        timeframe="1h",
        parameters={
            "fast_ma_period": 5,
            "slow_ma_period": 20,
            "signal_threshold": 0.001
        },
        risk_limits={
            "max_position": 1.0,
            "max_drawdown": 0.05
        }
    )
    
    # Create strategy configuration for a "risky" strategy
    risky_config = StrategyConfig(
        name="Risky Strategy",
        symbols=symbols,
        timeframe="1h",
        parameters={
            "volatility_threshold": 0.01,
            "position_size_multiplier": 5.0
        },
        risk_limits={
            "max_position": 1.0,
            "max_drawdown": 0.05
        }
    )
    
    # Create strategy instances
    normal_strategy = ExampleStrategy(normal_config)
    risky_strategy = HighVolatilityStrategy(risky_config)
    
    # Register strategies with lifecycle manager and risk limits
    normal_strategy_id = lifecycle_manager.register_strategy(
        strategy=normal_strategy,
        strategy_id="normal_strategy",
        parameters=normal_config.parameters,
        dependencies={},
        warmup_bars=50,
        auto_initialize=True,
        risk_limits=generate_risk_limits(max_position_size=0.1, max_volatility=0.02)
    )
    
    risky_strategy_id = lifecycle_manager.register_strategy(
        strategy=risky_strategy,
        strategy_id="risky_strategy",
        parameters=risky_config.parameters,
        dependencies={},
        warmup_bars=50,
        auto_initialize=True,
        risk_limits=generate_risk_limits(max_position_size=0.1, max_volatility=0.02)
    )
    
    logger.info(f"Registered strategies with IDs: {normal_strategy_id}, {risky_strategy_id}")
    
    # Generate sample data with a volatility spike for testing risk controls
    sample_data = generate_sample_data(symbols, periods=200)
    
    # Add a volatility spike to the data
    for symbol in symbols:
        # Add a volatility spike around period 120
        spike_start = 120
        spike_end = 140
        spike_factor = 3.0
        
        # Create a spike multiplier array
        multiplier = np.ones(200)
        multiplier[spike_start:spike_end] = np.linspace(1.0, spike_factor, spike_end - spike_start)
        
        # Apply the multiplier to the price moves
        base_prices = sample_data[symbol]['close'].values
        
        for i in range(1, len(base_prices)):
            if i >= spike_start and i < spike_end:
                # Exaggerate price moves during the spike
                move = (base_prices[i] - base_prices[i-1]) * multiplier[i]
                base_prices[i] = base_prices[i-1] + move
        
        # Update the dataframe
        sample_data[symbol]['close'] = base_prices
        sample_data[symbol]['high'] = base_prices * np.random.uniform(1.001, 1.005, 200)
        sample_data[symbol]['low'] = base_prices * np.random.uniform(0.995, 0.999, 200)
    
    # Warm up the strategies
    logger.info("Warming up strategies...")
    for strategy_id in [normal_strategy_id, risky_strategy_id]:
        for i in range(5):
            # Create a batch of 10 bars
            batch_data = pd.concat([
                sample_data[symbol].iloc[i*10:(i+1)*10] 
                for symbol in symbols
            ], keys=symbols, names=['symbol'])
            
            # Process batch
            try:
                warm_up_complete = lifecycle_manager.warmup_strategy(strategy_id, batch_data)
                
                # Check status
                status = lifecycle_manager.get_strategy_status(strategy_id)
                logger.info(f"Strategy {strategy_id} warm-up progress: {status['warmup_progress']}, Status: {status['state']}")
                
                if warm_up_complete:
                    logger.info(f"Strategy {strategy_id} warm-up complete!")
                    break
            except RiskViolationError as e:
                logger.error(f"Risk violation during warmup: {str(e)}")
    
    # Start the strategies
    logger.info("Starting strategies...")
    for strategy_id in [normal_strategy_id, risky_strategy_id]:
        try:
            lifecycle_manager.start_strategy(strategy_id)
            logger.info(f"Strategy {strategy_id} started successfully")
        except RiskViolationError as e:
            logger.error(f"Risk violation when starting strategy {strategy_id}: {str(e)}")
    
    # Process live data (including the volatility spike)
    logger.info("Processing live data...")
    for i in range(5, 15):
        # Create a batch of data
        batch_data = {
            symbol: sample_data[symbol].iloc[i*10:(i+1)*10]
            for symbol in symbols
        }
        
        # Process normal strategy first
        try:
            normal_results = lifecycle_manager.process_data(normal_strategy_id, batch_data)
            logger.info(f"Normal strategy processing complete for batch {i}")
            
            # Check risk metrics
            risk_metrics = lifecycle_manager.get_strategy_risk_metrics(normal_strategy_id)
            logger.info(f"Normal strategy risk metrics: violations={risk_metrics['violations_count']}, warnings={risk_metrics['warnings_count']}")
        except RiskViolationError as e:
            logger.error(f"Risk violation in normal strategy: {str(e)}")
            
        # Then process risky strategy (which should eventually violate risk limits)
        try:
            risky_results = lifecycle_manager.process_data(risky_strategy_id, batch_data)
            logger.info(f"Risky strategy processing complete for batch {i}")
            
            # Check risk metrics
            risk_metrics = lifecycle_manager.get_strategy_risk_metrics(risky_strategy_id)
            logger.info(f"Risky strategy risk metrics: violations={risk_metrics['violations_count']}, warnings={risk_metrics['warnings_count']}")
        except RiskViolationError as e:
            logger.error(f"Risk violation in risky strategy: {str(e)}")
        
        # Get portfolio risk metrics
        portfolio_metrics = lifecycle_manager.get_portfolio_risk_metrics()
        logger.info(f"Portfolio risk metrics: strategies={portfolio_metrics['strategy_count']}, active={portfolio_metrics.get('active_strategy_count', 0)}, violations={portfolio_metrics.get('violation_count', 0)}")
        
        # Check for risk violations
        violations = lifecycle_manager.get_risk_violations(limit=5)
        if violations:
            logger.warning(f"Recent risk violations: {len(violations)}")
            for v in violations[:3]:  # Show top 3
                logger.warning(f"Violation: {v['message']} ({v['strategy_id']})")
    
    # Get final statuses
    all_statuses = lifecycle_manager.get_all_strategies_status()
    logger.info(f"Final strategy statuses: {all_statuses}")
    
    # Stop all strategies
    for strategy_id in [normal_strategy_id, risky_strategy_id]:
        try:
            lifecycle_manager.stop_strategy(strategy_id)
            logger.info(f"Strategy {strategy_id} stopped")
        except Exception as e:
            logger.error(f"Error stopping strategy {strategy_id}: {str(e)}")
    
    logger.info("Risk-aware lifecycle management example completed")


if __name__ == "__main__":
    main() 