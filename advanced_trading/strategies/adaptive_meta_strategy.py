"""
Adaptive Meta-Strategy
-------------------
An advanced strategy that dynamically allocates capital across multiple sub-strategies
based on detected market regimes, historical performance, and risk management constraints.

This meta-strategy leverages Bayesian changepoint detection for regime identification
and hierarchical risk parity for balanced risk allocation across strategies.
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import matplotlib.pyplot as plt
import json
from pathlib import Path

# Import internal modules using the correct module paths
from advanced_trading.utils.bayesian_changepoint import BayesianChangepointDetector, detect_market_regimes
from advanced_trading.utils.portfolio_allocation import PortfolioAllocator
from advanced_trading.utils.metrics.performance_metrics import calculate_returns_metrics, calculate_regime_performance
from advanced_trading.utils.risk_management import calculate_kelly_fraction, dynamic_risk_adjustment

# Set up logging
logger = logging.getLogger(__name__)

class AdaptiveMetaStrategy:
    """
    A meta-strategy that allocates across multiple sub-strategies
    based on regime detection and performance characteristics.
    
    This strategy combines:
    1. Market regime detection using Bayesian changepoint detection
    2. Strategy performance tracking by regime
    3. Dynamic allocation using historical and recent performance
    4. Risk-balanced portfolio construction using HRP
    5. Adaptive risk management based on market conditions
    
    Parameters:
    -----------
    strategies : Dict[str, Any]
        Dictionary of strategy instances keyed by strategy name
    regime_detector : Optional[BayesianChangepointDetector]
        Pre-configured regime detector (or None to create a new one)
    allocator : Optional[PortfolioAllocator]
        Pre-configured portfolio allocator (or None to create a new one)
    base_allocations : Optional[Dict[str, float]]
        Base allocation weights for each strategy (sums to 1.0)
    lookback_window : int
        Window for tracking strategy performance
    regime_memory : int
        Number of days to remember regime-specific performance
    allocation_method : str
        Method for portfolio allocation ('hrp', 'risk_parity', etc.)
    max_allocation : float
        Maximum allocation to any single strategy
    min_allocation : float
        Minimum allocation to any strategy
    target_volatility : Optional[float]
        Target volatility for the combined strategy
    adaptation_speed : float
        How quickly to adapt to new performance (0-1)
    """
    
    def __init__(
        self,
        strategies: Dict[str, Any],
        regime_detector: Optional[BayesianChangepointDetector] = None,
        allocator: Optional[PortfolioAllocator] = None,
        base_allocations: Optional[Dict[str, float]] = None,
        lookback_window: int = 60,
        regime_memory: int = 252,
        allocation_method: str = 'hrp',
        max_allocation: float = 0.5,
        min_allocation: float = 0.0,
        target_volatility: Optional[float] = 0.15,
        adaptation_speed: float = 0.1
    ):
        # Store strategies
        self.strategies = strategies
        self.strategy_names = list(strategies.keys())
        
        # Initialize regime detector if not provided
        if regime_detector is None:
            self.regime_detector = BayesianChangepointDetector(hazard_function=0.01)
        else:
            self.regime_detector = regime_detector
            
        # Initialize portfolio allocator if not provided
        if allocator is None:
            self.allocator = PortfolioAllocator(
                method=allocation_method,
                target_volatility=target_volatility
            )
        else:
            self.allocator = allocator
            
        # Store parameters
        self.lookback_window = lookback_window
        self.regime_memory = regime_memory
        self.max_allocation = max_allocation
        self.min_allocation = min_allocation
        self.target_volatility = target_volatility
        self.adaptation_speed = adaptation_speed
        
        # Set up base allocations (equal weight if not provided)
        if base_allocations is None:
            self.base_allocations = {name: 1.0 / len(strategies) for name in self.strategy_names}
        else:
            # Normalize to ensure sum is 1.0
            total = sum(base_allocations.values())
            self.base_allocations = {name: weight / total for name, weight in base_allocations.items()}
            
        # Initialize performance tracking
        self.current_regime = None
        self.regime_history = []
        self.performance_by_regime = {}  # Dict[regime_type, Dict[strategy_name, metrics]]
        self.performance_history = pd.DataFrame()  # Track daily performance
        self.current_allocations = self.base_allocations.copy()
        self.signals_history = pd.DataFrame()  # Track strategy signals
        
        # Risk management parameters
        self.risk_params = {
            "max_drawdown": 0.25,  # Maximum allowed drawdown
            "risk_scaling": True,  # Whether to scale by risk
            "use_kelly": True,     # Whether to use Kelly criterion
            "kelly_fraction": 0.5  # Conservative Kelly (half-Kelly)
        }
        
        # State tracking
        self.is_initialized = False
        self.current_positions = {}
        self.current_data_date = None
        
        logger.info(f"AdaptiveMetaStrategy initialized with {len(strategies)} strategies") 

    def update(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        Update the strategy with new market data and return current positions.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
            
        Returns:
        --------
        Dict[str, float]
            Current position allocations by symbol
        """
        # Extract the date from the market data
        first_symbol = next(iter(market_data))
        current_date = market_data[first_symbol].index[-1]
        self.current_data_date = current_date
        
        # 1. Update regime detection
        self._update_regime_detection(market_data)
        
        # 2. Generate signals from all strategies
        signals = self._generate_strategy_signals(market_data)
        
        # 3. Update performance tracking
        self._update_performance_tracking(signals, market_data)
        
        # 4. Calculate strategy allocations based on regime and performance
        self._update_strategy_allocations()
        
        # 5. Calculate final positions
        positions = self._calculate_positions(signals, market_data)
        
        # Store current positions
        self.current_positions = positions
        
        return positions
        
    def _update_regime_detection(self, market_data: Dict[str, pd.DataFrame]) -> None:
        """
        Update the market regime detection based on new data.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
        """
        # Use the first symbol as the benchmark for regime detection
        # In a production system, this could be more sophisticated (e.g., index or basket)
        benchmark_symbol = next(iter(market_data))
        benchmark_data = market_data[benchmark_symbol]
        
        # Calculate returns if not present
        if 'returns' not in benchmark_data.columns:
            benchmark_data['returns'] = benchmark_data['close'].pct_change()
        
        # Get the latest return
        latest_return = benchmark_data['returns'].iloc[-1]
        
        # Update the regime detector
        self.regime_detector.update(latest_return)
        
        # Every 20 days or when significant change is detected, recalculate regimes
        recalculate = False
        if len(self.regime_history) % 20 == 0:
            recalculate = True
        
        if recalculate:
            # Use the full history to detect regimes
            regimes = detect_market_regimes(benchmark_data['returns'].iloc[-self.regime_memory:])
            if regimes['segments']:
                # Get the most recent regime
                latest_segment = regimes['segments'][-1]
                self.current_regime = latest_segment['regime']
            else:
                # Default regime if none detected
                self.current_regime = "Neutral"
        
        # Record regime history
        self.regime_history.append({
            'date': self.current_data_date,
            'regime': self.current_regime
        })
        
        logger.debug(f"Current regime: {self.current_regime}")
    
    def _generate_strategy_signals(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        Generate signals from all sub-strategies.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
            
        Returns:
        --------
        Dict[str, float]
            Dictionary of signals by strategy name
        """
        signals = {}
        
        # Get signals from each strategy
        for name, strategy in self.strategies.items():
            try:
                # Assuming each strategy has a generate_signal method
                if hasattr(strategy, 'generate_signal'):
                    signals[name] = strategy.generate_signal(market_data)
                elif hasattr(strategy, 'generate_signals'):  # Alternative naming
                    # Some strategies may return signals for multiple symbols
                    # In this case, we'll take the average signal
                    strategy_signals = strategy.generate_signals(market_data)
                    if isinstance(strategy_signals, dict):
                        signals[name] = np.mean(list(strategy_signals.values()))
                    else:
                        signals[name] = strategy_signals
                else:
                    logger.warning(f"Strategy {name} doesn't have a signal generation method")
                    signals[name] = 0.0
            except Exception as e:
                logger.error(f"Error generating signal for strategy {name}: {str(e)}")
                signals[name] = 0.0
        
        # Record signals in history
        signal_row = {'date': self.current_data_date}
        signal_row.update(signals)
        
        # Append to signals history - using concat instead of append (deprecated)
        new_row_df = pd.DataFrame([signal_row])
        if not isinstance(self.signals_history, pd.DataFrame) or len(self.signals_history) == 0:
            self.signals_history = new_row_df
        else:
            self.signals_history = pd.concat([self.signals_history, new_row_df], ignore_index=True)
            
        if len(self.signals_history) > self.lookback_window * 2:
            # Trim history to avoid memory growth
            self.signals_history = self.signals_history.iloc[-self.lookback_window*2:]
        
        return signals
    
    def _update_performance_tracking(self, signals: Dict[str, float], 
                                   market_data: Dict[str, pd.DataFrame]) -> None:
        """
        Update performance tracking for each strategy.
        
        Parameters:
        -----------
        signals : Dict[str, float]
            Dictionary of signals by strategy name
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
        """
        if not self.is_initialized:
            self.is_initialized = True
            return  # Skip first update as we need at least one day of history
        
        # Get the previous date for calculating returns
        if len(self.performance_history) > 0:
            prev_date = self.performance_history.iloc[-1]['date']
        else:
            # Create first entry
            perf_row = {
                'date': self.current_data_date,
                'regime': self.current_regime,
                'meta_strategy_return': 0.0
            }
            for name in self.strategy_names:
                perf_row[f'{name}_return'] = 0.0
                perf_row[f'{name}_allocation'] = self.current_allocations[name]
                
            self.performance_history = pd.DataFrame([perf_row])
            return
        
        # Calculate returns for each strategy
        returns = {}
        
        # Use the first symbol as benchmark for simplicity
        benchmark_symbol = next(iter(market_data))
        benchmark_data = market_data[benchmark_symbol]
        
        # For simplicity, we'll calculate returns based on the benchmark
        # In a real system, each strategy would report its own returns
        market_return = benchmark_data['close'].pct_change().iloc[-1]
        
        # Calculate strategy returns based on previous signals
        # This is a simplified approach - in reality each strategy would have its own return calculation
        prev_signals = self.signals_history.iloc[-2] if len(self.signals_history) > 1 else None
        
        if prev_signals is not None:
            for name in self.strategy_names:
                if name in prev_signals:
                    # Scale market return by the signal
                    signal_strength = prev_signals[name]
                    strategy_return = market_return * signal_strength
                    returns[name] = strategy_return
                else:
                    returns[name] = 0.0
        else:
            # If no previous signals, assume flat returns
            returns = {name: 0.0 for name in self.strategy_names}
        
        # Calculate meta-strategy return based on weighted average of strategy returns
        meta_return = sum(returns[name] * self.current_allocations[name] 
                          for name in self.strategy_names)
        
        # Create performance row
        perf_row = {
            'date': self.current_data_date,
            'regime': self.current_regime,
            'meta_strategy_return': meta_return
        }
        
        # Add individual strategy returns and allocations
        for name in self.strategy_names:
            perf_row[f'{name}_return'] = returns[name]
            perf_row[f'{name}_allocation'] = self.current_allocations[name]
        
        # Append to performance history - using concat instead of append (deprecated)
        new_row_df = pd.DataFrame([perf_row])
        self.performance_history = pd.concat([self.performance_history, new_row_df], ignore_index=True)
        
        # Trim history if needed
        if len(self.performance_history) > self.regime_memory:
            self.performance_history = self.performance_history.iloc[-self.regime_memory:]
        
        # Update regime-specific performance
        self._update_regime_performance()
    
    def _update_regime_performance(self) -> None:
        """
        Update performance metrics for each strategy by regime.
        """
        # Group performance history by regime
        grouped = self.performance_history.groupby('regime')
        
        # Update performance by regime
        for regime, group in grouped:
            if regime not in self.performance_by_regime:
                self.performance_by_regime[regime] = {}
            
            # Calculate metrics for each strategy in this regime
            for name in self.strategy_names:
                returns_col = f'{name}_return'
                if returns_col in group.columns:
                    returns = group[returns_col]
                    
                    # Skip if not enough data
                    if len(returns) < 5:
                        continue
                    
                    # Calculate metrics
                    metrics = calculate_returns_metrics(pd.Series(returns.values, index=group['date']))
                    
                    # Store metrics
                    self.performance_by_regime[regime][name] = metrics
    
    def _update_strategy_allocations(self) -> None:
        """
        Update strategy allocations based on regime and performance.
        """
        # Get the current regime
        if self.current_regime is None:
            # If no regime detected yet, use base allocations
            self.current_allocations = self.base_allocations.copy()
            return
        
        # Check if we have performance data for the current regime
        if self.current_regime in self.performance_by_regime:
            regime_performance = self.performance_by_regime[self.current_regime]
            
            # If we have performance data for at least one strategy
            if regime_performance:
                # Calculate allocation scores based on Sharpe ratio
                scores = {}
                for name in self.strategy_names:
                    if name in regime_performance:
                        # Use Sharpe ratio as the score, with a minimum value of 0
                        sharpe = regime_performance[name].get('sharpe_ratio', 0)
                        scores[name] = max(0, sharpe)
                    else:
                        # No data for this strategy in this regime, use a neutral score
                        scores[name] = 0.5
                
                # Normalize scores if any are positive
                total_score = sum(scores.values())
                if total_score > 0:
                    normalized_scores = {name: score / total_score for name, score in scores.items()}
                else:
                    # If all scores are zero, use base allocations
                    normalized_scores = self.base_allocations.copy()
                
                # Apply minimum and maximum allocation constraints
                constrained_allocations = {}
                for name, score in normalized_scores.items():
                    # Apply constraints
                    allocation = max(self.min_allocation, min(self.max_allocation, score))
                    constrained_allocations[name] = allocation
                
                # Normalize constrained allocations to sum to 1.0
                total_allocation = sum(constrained_allocations.values())
                if total_allocation > 0:
                    normalized_allocations = {name: alloc / total_allocation 
                                            for name, alloc in constrained_allocations.items()}
                else:
                    # Fallback to base allocations
                    normalized_allocations = self.base_allocations.copy()
                
                # Smooth allocation changes using adaptation speed
                new_allocations = {}
                for name in self.strategy_names:
                    current = self.current_allocations.get(name, 0)
                    target = normalized_allocations.get(name, 0)
                    new_allocations[name] = current + self.adaptation_speed * (target - current)
                
                # Ensure new allocations sum to 1.0
                total = sum(new_allocations.values())
                if total > 0:
                    self.current_allocations = {name: weight / total 
                                               for name, weight in new_allocations.items()}
                else:
                    self.current_allocations = self.base_allocations.copy()
            else:
                # No performance data for this regime, use base allocations
                self.current_allocations = self.base_allocations.copy()
        else:
            # No data for this regime, use base allocations
            self.current_allocations = self.base_allocations.copy()
        
        logger.debug(f"Updated allocations: {self.current_allocations}")
    
    def _calculate_positions(self, signals: Dict[str, float], 
                           market_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        Calculate final positions based on signals and allocations.
        
        Parameters:
        -----------
        signals : Dict[str, float]
            Dictionary of signals by strategy name
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
            
        Returns:
        --------
        Dict[str, float]
            Dictionary of position sizes by symbol
        """
        # Get all symbols from market data
        symbols = list(market_data.keys())
        
        # Initialize positions
        positions = {symbol: 0.0 for symbol in symbols}
        
        # Calculate positions from each strategy based on allocations
        for name, strategy in self.strategies.items():
            allocation = self.current_allocations.get(name, 0.0)
            
            # Skip if allocation is zero
            if allocation <= 0.0:
                continue
            
            # Get strategy-specific positions
            try:
                if hasattr(strategy, 'get_positions'):
                    strategy_positions = strategy.get_positions(market_data)
                elif hasattr(strategy, 'calculate_positions'):
                    strategy_positions = strategy.calculate_positions(market_data)
                else:
                    # Fallback: use signal to create a simple position
                    signal = signals.get(name, 0.0)
                    strategy_positions = {symbol: signal for symbol in symbols}
            except Exception as e:
                logger.error(f"Error getting positions for strategy {name}: {str(e)}")
                strategy_positions = {symbol: 0.0 for symbol in symbols}
            
            # Add weighted positions
            for symbol, position in strategy_positions.items():
                if symbol in positions:
                    positions[symbol] += position * allocation
        
        # Apply risk adjustment based on current market regime
        positions = self._adjust_positions_for_risk(positions, market_data)
        
        return positions
    
    def _adjust_positions_for_risk(self, positions: Dict[str, float], 
                                 market_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        Adjust positions based on risk parameters and current market regime.
        
        Parameters:
        -----------
        positions : Dict[str, float]
            Dictionary of unadjusted positions by symbol
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
            
        Returns:
        --------
        Dict[str, float]
            Dictionary of risk-adjusted positions by symbol
        """
        # Calculate portfolio volatility
        portfolio_vol = self._estimate_portfolio_volatility(positions, market_data)
        
        # Determine risk adjustment factor based on regime
        adjustment_factor = 1.0
        
        # Adjust based on regime type
        if self.current_regime is not None:
            if "Bear" in self.current_regime:
                # Reduce exposure in bear markets
                adjustment_factor = 0.7
                if "Volatile" in self.current_regime:
                    adjustment_factor = 0.5  # Further reduce in volatile bear markets
            elif "Volatile" in self.current_regime:
                # Reduce exposure in volatile markets
                adjustment_factor = 0.8
            elif "Bull" in self.current_regime:
                # Maintain or slightly increase exposure in bull markets
                adjustment_factor = 1.0
                if "Stable" in self.current_regime:
                    adjustment_factor = 1.1  # Slightly increase in stable bull markets
        
        # Apply Kelly criterion if enabled
        if self.risk_params["use_kelly"]:
            # Get recent performance for win rate and win/loss ratio
            if len(self.performance_history) > 10:
                recent_perf = self.performance_history.iloc[-20:]
                meta_returns = recent_perf['meta_strategy_return'].values
                
                # Calculate win rate and ratio
                wins = (meta_returns > 0).sum()
                losses = (meta_returns < 0).sum()
                
                if losses > 0:
                    win_rate = wins / (wins + losses)
                    
                    # Average win and loss
                    avg_win = meta_returns[meta_returns > 0].mean() if wins > 0 else 0
                    avg_loss = abs(meta_returns[meta_returns < 0].mean()) if losses > 0 else 1
                    
                    # Avoid division by zero
                    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1
                    
                    # Calculate Kelly fraction
                    kelly = calculate_kelly_fraction(win_rate, win_loss_ratio, 
                                                   self.risk_params["kelly_fraction"])
                    
                    # Apply Kelly adjustment
                    adjustment_factor *= kelly
        
        # Apply volatility scaling if enabled
        if self.risk_params["risk_scaling"] and self.target_volatility is not None and portfolio_vol > 0:
            vol_adjustment = self.target_volatility / portfolio_vol
            adjustment_factor *= min(2.0, vol_adjustment)  # Cap at 2x leverage
        
        # Apply drawdown control
        if len(self.performance_history) > 0:
            # Calculate drawdown
            equity_curve = (1 + self.performance_history['meta_strategy_return']).cumprod()
            peak = equity_curve.cummax()
            drawdown = (equity_curve / peak - 1).min()
            
            # Reduce exposure in drawdowns
            if abs(drawdown) > self.risk_params["max_drawdown"] * 0.5:
                # Linearly reduce exposure as drawdown approaches max
                dd_factor = 1.0 - abs(drawdown) / self.risk_params["max_drawdown"]
                adjustment_factor *= max(0.2, dd_factor)  # Minimum 20% exposure
        
        # Apply the adjustment factor to all positions
        adjusted_positions = {symbol: pos * adjustment_factor for symbol, pos in positions.items()}
        
        return adjusted_positions
    
    def _estimate_portfolio_volatility(self, positions: Dict[str, float], 
                                     market_data: Dict[str, pd.DataFrame]) -> float:
        """
        Estimate the volatility of the current portfolio.
        
        Parameters:
        -----------
        positions : Dict[str, float]
            Dictionary of positions by symbol
        market_data : Dict[str, pd.DataFrame]
            Dictionary of market data frames by symbol
            
        Returns:
        --------
        float
            Estimated annualized portfolio volatility
        """
        # Get returns for each symbol
        returns_dict = {}
        for symbol, df in market_data.items():
            if 'returns' not in df.columns:
                if 'close' in df.columns:
                    returns_dict[symbol] = df['close'].pct_change().dropna()
            else:
                returns_dict[symbol] = df['returns'].dropna()
        
        # Convert to DataFrame
        returns_df = pd.DataFrame(returns_dict)
        
        # Remove rows with NaN values
        returns_df = returns_df.dropna()
        
        # If not enough data, return default volatility
        if len(returns_df) < 10:
            return 0.2  # Default 20% volatility
        
        # Calculate covariance matrix
        cov_matrix = returns_df.cov() * 252  # Annualize
        
        # Extract position weights for symbols in the covariance matrix
        symbols = returns_df.columns
        weights = np.array([positions.get(symbol, 0.0) for symbol in symbols])
        
        # Calculate portfolio variance
        portfolio_variance = weights.T @ cov_matrix.values @ weights
        
        # Return portfolio volatility
        return np.sqrt(max(0, portfolio_variance))
    
    def visualize_allocations(self, figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Visualize strategy allocations over time.
        
        Parameters:
        -----------
        figsize : Tuple[int, int]
            Figure size (width, height)
            
        Returns:
        --------
        matplotlib.figure.Figure
            The created figure
        """
        if len(self.performance_history) < 2:
            # Not enough data to visualize
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, "Not enough data to visualize allocations", 
                   ha='center', va='center', fontsize=14)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            return fig
        
        # Extract allocation data
        allocation_data = {}
        for name in self.strategy_names:
            column = f"{name}_allocation"
            if column in self.performance_history.columns:
                allocation_data[name] = self.performance_history[column]
        
        # Create DataFrame for plotting
        allocation_df = pd.DataFrame(allocation_data, index=self.performance_history['date'])
        
        # Create stacked area chart
        fig, ax = plt.subplots(figsize=figsize)
        allocation_df.plot.area(ax=ax, stacked=True, alpha=0.7)
        
        # Add regime information
        regime_df = pd.DataFrame({
            'regime': [r['regime'] for r in self.regime_history]
        }, index=[r['date'] for r in self.regime_history])
        
        # Create regime background
        self._add_regime_background(ax, regime_df)
        
        # Set labels and title
        ax.set_xlabel('Date')
        ax.set_ylabel('Allocation')
        ax.set_title('Strategy Allocations Over Time by Market Regime')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # Adjust y-axis to show full range
        ax.set_ylim(0, 1)
        
        plt.tight_layout()
        return fig
    
    def visualize_performance(self, figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Visualize strategy performance over time.
        
        Parameters:
        -----------
        figsize : Tuple[int, int]
            Figure size (width, height)
            
        Returns:
        --------
        matplotlib.figure.Figure
            The created figure
        """
        if len(self.performance_history) < 2:
            # Not enough data to visualize
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, "Not enough data to visualize performance", 
                   ha='center', va='center', fontsize=14)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            return fig
        
        # Calculate cumulative returns
        perf_data = self.performance_history.copy()
        meta_returns = perf_data['meta_strategy_return']
        meta_cumulative = (1 + meta_returns).cumprod()
        
        # Calculate strategy cumulative returns
        strategy_data = {}
        for name in self.strategy_names:
            column = f"{name}_return"
            if column in perf_data.columns:
                strategy_returns = perf_data[column]
                strategy_data[name] = (1 + strategy_returns).cumprod()
        
        # Create DataFrame for plotting
        perf_df = pd.DataFrame(strategy_data, index=perf_data['date'])
        perf_df['Meta-Strategy'] = meta_cumulative.values
        
        # Create performance chart
        fig, ax = plt.subplots(figsize=figsize)
        perf_df.plot(ax=ax, linewidth=2)
        
        # Add regime information
        regime_df = pd.DataFrame({
            'regime': [r['regime'] for r in self.regime_history]
        }, index=[r['date'] for r in self.regime_history])
        
        # Create regime background
        self._add_regime_background(ax, regime_df)
        
        # Set labels and title
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Returns')
        ax.set_title('Strategy Performance Over Time by Market Regime')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # Add annotations for final values
        for col in perf_df.columns:
            final_value = perf_df[col].iloc[-1]
            ax.annotate(f'{col}: {final_value:.2f}', 
                       xy=(perf_df.index[-1], final_value),
                       xytext=(10, 0), textcoords='offset points',
                       va='center')
        
        plt.tight_layout()
        return fig
    
    def visualize_regime_performance(self, figsize: Tuple[int, int] = (15, 10)) -> plt.Figure:
        """
        Visualize performance by regime for each strategy.
        
        Parameters:
        -----------
        figsize : Tuple[int, int]
            Figure size (width, height)
            
        Returns:
        --------
        matplotlib.figure.Figure
            The created figure
        """
        if not self.performance_by_regime:
            # Not enough data to visualize
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, "Not enough data to visualize regime performance", 
                   ha='center', va='center', fontsize=14)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            return fig
        
        # Set up the figure with multiple subplots
        n_regimes = len(self.performance_by_regime)
        n_cols = min(3, n_regimes)
        n_rows = (n_regimes + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        
        # Flatten axes array for easy iteration
        if n_rows > 1 and n_cols > 1:
            axes_flat = axes.flatten()
        elif n_rows == 1 and n_cols > 1:
            axes_flat = axes
        else:
            axes_flat = [axes]
        
        # Hide unused axes
        for i in range(n_regimes, len(axes_flat)):
            axes_flat[i].axis('off')
        
        # Plot data for each regime
        for i, (regime, perf_data) in enumerate(self.performance_by_regime.items()):
            ax = axes_flat[i]
            
            # Extract sharpe ratios
            sharpe_data = {name: data.get('sharpe_ratio', 0) for name, data in perf_data.items()}
            
            # Sort by Sharpe ratio
            sorted_sharpe = sorted(sharpe_data.items(), key=lambda x: x[1], reverse=True)
            names = [item[0] for item in sorted_sharpe]
            sharpe_values = [item[1] for item in sorted_sharpe]
            
            # Create bar chart
            colors = plt.cm.viridis(np.linspace(0, 0.9, len(names)))
            bars = ax.bar(names, sharpe_values, color=colors)
            
            # Add value labels
            for bar, value in zip(bars, sharpe_values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                       f'{value:.2f}', ha='center', va='bottom', rotation=0)
            
            # Customize plot
            ax.set_title(f'Regime: {regime}')
            ax.set_ylabel('Sharpe Ratio')
            ax.set_ylim(bottom=min(-0.5, min(sharpe_values) - 0.5))
            ax.grid(axis='y', linestyle='--', alpha=0.7)
            
            # Rotate x-axis labels if needed
            if len(names) > 3:
                ax.set_xticklabels(names, rotation=45, ha='right')
        
        plt.suptitle('Strategy Performance by Market Regime (Sharpe Ratio)', fontsize=16)
        plt.tight_layout()
        fig.subplots_adjust(top=0.92)
        
        return fig
    
    def _add_regime_background(self, ax: plt.Axes, regime_df: pd.DataFrame) -> None:
        """
        Add colored background to represent different regimes.
        
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes to draw on
        regime_df : pd.DataFrame
            DataFrame with regime information, indexed by date
        """
        # Get unique regimes
        unique_regimes = regime_df['regime'].unique()
        
        # Create color map
        n_regimes = len(unique_regimes)
        colors = plt.cm.tab20(np.linspace(0, 1, n_regimes))
        regime_colors = {regime: colors[i] for i, regime in enumerate(unique_regimes)}
        
        # Get y-axis limits
        y_min, y_max = ax.get_ylim()
        
        # Find regime transition points
        regime_df['regime_change'] = regime_df['regime'] != regime_df['regime'].shift(1)
        change_points = regime_df.index[regime_df['regime_change']].tolist()
        
        # Add start and end points
        change_points = [regime_df.index[0]] + change_points + [regime_df.index[-1]]
        
        # Draw colored background for each regime segment
        for i in range(len(change_points) - 1):
            start = change_points[i]
            end = change_points[i+1]
            
            # Get the regime for this segment
            if i < len(regime_df):
                regime = regime_df.loc[start:end, 'regime'].iloc[0]
            else:
                continue
                
            # Draw background
            color = regime_colors[regime]
            ax.axvspan(start, end, alpha=0.2, color=color)
            
            # Add regime label in the middle of the segment
            mid_point = start + (end - start) / 2
            ax.text(mid_point, 0.98 * y_max, regime, 
                   ha='center', va='top', fontsize=9, 
                   bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7))
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of performance metrics.
        
        Returns:
        --------
        Dict[str, Any]
            Dictionary with performance metrics
        """
        if len(self.performance_history) < 5:
            return {"error": "Not enough data for performance summary"}
        
        # Calculate meta-strategy metrics
        meta_returns = self.performance_history['meta_strategy_return']
        
        # Calculate metrics
        metrics = calculate_returns_metrics(meta_returns)
        
        # Add regime breakdown
        metrics['regime_breakdown'] = {}
        for regime, data in self.performance_by_regime.items():
            if 'Meta-Strategy' in data:
                metrics['regime_breakdown'][regime] = {
                    'sharpe_ratio': data['Meta-Strategy'].get('sharpe_ratio', 0),
                    'annualized_return': data['Meta-Strategy'].get('annual_return', 0),
                    'max_drawdown': data['Meta-Strategy'].get('max_drawdown', 0),
                    'win_rate': data['Meta-Strategy'].get('win_rate', 0)
                }
        
        # Add strategy allocation information
        metrics['current_allocations'] = self.current_allocations
        
        # Add current regime
        metrics['current_regime'] = self.current_regime
        
        return metrics
    
    def save(self, filepath: str) -> bool:
        """
        Save the strategy state to disk.
        
        Parameters:
        -----------
        filepath : str
            File path to save the state
            
        Returns:
        --------
        bool
            Success status
        """
        try:
            # Create save directory if it doesn't exist
            save_dir = os.path.dirname(filepath)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
            
            # Prepare data to save
            save_data = {
                'current_regime': self.current_regime,
                'regime_history': self.regime_history,
                'base_allocations': self.base_allocations,
                'current_allocations': self.current_allocations,
                'risk_params': self.risk_params,
                'is_initialized': self.is_initialized,
                'current_data_date': self.current_data_date,
                'lookback_window': self.lookback_window,
                'regime_memory': self.regime_memory,
                'max_allocation': self.max_allocation,
                'min_allocation': self.min_allocation,
                'target_volatility': self.target_volatility,
                'adaptation_speed': self.adaptation_speed
            }
            
            # Convert DataFrame to dict for saving
            if len(self.performance_history) > 0:
                save_data['performance_history'] = self.performance_history.to_dict(orient='records')
            
            if len(self.signals_history) > 0:
                save_data['signals_history'] = self.signals_history.to_dict(orient='records')
            
            # Save performance by regime (complex nested dict with custom objects)
            regime_perf_save = {}
            for regime, data in self.performance_by_regime.items():
                regime_perf_save[regime] = {}
                for name, metrics in data.items():
                    regime_perf_save[regime][name] = {k: float(v) for k, v in metrics.items()}
            
            save_data['performance_by_regime'] = regime_perf_save
            
            # Save to file (using json for readability)
            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2, default=str)
            
            logger.info(f"Strategy state saved to {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving strategy state: {str(e)}")
            return False
    
    def load(self, filepath: str) -> bool:
        """
        Load the strategy state from disk.
        
        Parameters:
        -----------
        filepath : str
            File path to load the state from
            
        Returns:
        --------
        bool
            Success status
        """
        try:
            if not os.path.exists(filepath):
                logger.error(f"File not found: {filepath}")
                return False
            
            # Load from file
            with open(filepath, 'r') as f:
                load_data = json.load(f)
            
            # Restore basic attributes
            self.current_regime = load_data.get('current_regime')
            self.regime_history = load_data.get('regime_history', [])
            self.base_allocations = load_data.get('base_allocations', self.base_allocations)
            self.current_allocations = load_data.get('current_allocations', self.current_allocations)
            self.risk_params = load_data.get('risk_params', self.risk_params)
            self.is_initialized = load_data.get('is_initialized', False)
            self.current_data_date = load_data.get('current_data_date')
            self.lookback_window = load_data.get('lookback_window', self.lookback_window)
            self.regime_memory = load_data.get('regime_memory', self.regime_memory)
            self.max_allocation = load_data.get('max_allocation', self.max_allocation)
            self.min_allocation = load_data.get('min_allocation', self.min_allocation)
            self.target_volatility = load_data.get('target_volatility', self.target_volatility)
            self.adaptation_speed = load_data.get('adaptation_speed', self.adaptation_speed)
            
            # Restore DataFrames
            if 'performance_history' in load_data:
                self.performance_history = pd.DataFrame(load_data['performance_history'])
            
            if 'signals_history' in load_data:
                self.signals_history = pd.DataFrame(load_data['signals_history'])
            
            # Restore performance by regime
            if 'performance_by_regime' in load_data:
                self.performance_by_regime = load_data['performance_by_regime']
            
            logger.info(f"Strategy state loaded from {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading strategy state: {str(e)}")
            return False


# Utility function to create an AdaptiveMetaStrategy from existing strategies
def create_adaptive_meta_strategy(
    strategies: Dict[str, Any],
    base_allocations: Optional[Dict[str, float]] = None,
    target_volatility: float = 0.15,
    allocation_method: str = 'hrp',
    max_allocation: float = 0.5,
    save_dir: Optional[str] = None
) -> AdaptiveMetaStrategy:
    """
    Create an AdaptiveMetaStrategy from existing strategies.
    
    Parameters:
    -----------
    strategies : Dict[str, Any]
        Dictionary of strategy instances keyed by strategy name
    base_allocations : Optional[Dict[str, float]]
        Base allocation weights for each strategy (sums to 1.0)
    target_volatility : float
        Target volatility for the combined strategy
    allocation_method : str
        Method for portfolio allocation ('hrp', 'risk_parity', etc.)
    max_allocation : float
        Maximum allocation to any single strategy
    save_dir : Optional[str]
        Directory to save strategy state
        
    Returns:
    --------
    AdaptiveMetaStrategy
        Initialized meta-strategy
    """
    # Create meta-strategy
    meta_strategy = AdaptiveMetaStrategy(
        strategies=strategies,
        base_allocations=base_allocations,
        target_volatility=target_volatility,
        allocation_method=allocation_method,
        max_allocation=max_allocation
    )
    
    # Set up save directory
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        
        # Try to load existing state
        save_path = os.path.join(save_dir, "adaptive_meta_strategy.json")
        if os.path.exists(save_path):
            meta_strategy.load(save_path)
    
    return meta_strategy 