#!/usr/bin/env python3
"""
Adaptive Meta-Strategy Example
--------------------------
This script demonstrates how to use the AdaptiveMetaStrategy to combine 
multiple trading strategies with regime-based adaptation.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
from typing import Dict, List, Any, Optional

# Add parent directory to path to allow imports
script_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(script_dir))

# Import from our modules
from strategies.adaptive_meta_strategy import AdaptiveMetaStrategy, create_adaptive_meta_strategy
from strategies.ml_strategy import MLEnsembleStrategy
from strategies.advanced_crypto_strategy import AdvancedCryptoStrategy
from strategies.funding_arbitrage import FundingRateArbitrage
from strategies.statistical_arbitrage import StatisticalArbitrageStrategy
from data.data_loader import DataLoader
from data.data_manager import DataManager
from utils.bayesian_changepoint import BayesianChangepointDetector
from utils.portfolio_allocation import PortfolioAllocator
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(script_dir / 'logs' / f'adaptive_strategy_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run Adaptive Meta-Strategy example')
    
    parser.add_argument('--symbols', type=str, nargs='+',
                      default=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT'],
                      help='Trading pairs to analyze')
    
    parser.add_argument('--start_date', type=str, 
                      default=(datetime.now().replace(year=datetime.now().year-1)).strftime('%Y-%m-%d'),
                      help='Start date for data (YYYY-MM-DD)')
    
    parser.add_argument('--end_date', type=str, 
                      default=datetime.now().strftime('%Y-%m-%d'),
                      help='End date for data (YYYY-MM-DD)')
    
    parser.add_argument('--timeframe', type=str, default='1d',
                      help='Timeframe for data')
    
    parser.add_argument('--allocation_method', type=str, default='hrp',
                      choices=['hrp', 'risk_parity', 'min_variance', 'equal', 'sharpe_maximizing'],
                      help='Portfolio allocation method')
    
    parser.add_argument('--target_volatility', type=float, default=0.15,
                      help='Target annualized volatility')
    
    parser.add_argument('--output_dir', type=str, 
                      default=str(script_dir / 'results' / f'adaptive_strategy_{datetime.now().strftime("%Y%m%d_%H%M%S")}'),
                      help='Directory to save results')
    
    parser.add_argument('--save_state', action='store_true',
                      help='Whether to save strategy state')
    
    return parser.parse_args()

def load_market_data(symbols: List[str], timeframe: str, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
    """
    Load market data for the specified symbols and timeframe.
    
    Parameters:
    -----------
    symbols : List[str]
        List of trading pairs
    timeframe : str
        Timeframe for data
    start_date : str
        Start date for data
    end_date : str
        End date for data
        
    Returns:
    --------
    Dict[str, pd.DataFrame]
        Dictionary of market data frames by symbol
    """
    logger.info(f"Loading market data for {len(symbols)} symbols from {start_date} to {end_date}")
    
    # Initialize data loader
    data_loader = DataLoader(
        cache_dir=config.DATA_DIR / "cache",
        primary_source="binance"
    )
    
    # Load data for each symbol
    market_data = {}
    for symbol in symbols:
        try:
            df = data_loader.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and not df.empty:
                # Add returns column for regime detection
                df['returns'] = df['close'].pct_change()
                market_data[symbol] = df
                logger.info(f"Loaded {len(df)} data points for {symbol}")
            else:
                logger.warning(f"No data loaded for {symbol}")
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {str(e)}")
    
    return market_data

def initialize_strategies(symbols: List[str], market_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Initialize different strategy types for testing.
    
    Parameters:
    -----------
    symbols : List[str]
        List of trading pairs
    market_data : Dict[str, pd.DataFrame]
        Dictionary of market data frames by symbol
        
    Returns:
    --------
    Dict[str, Any]
        Dictionary of strategy instances keyed by strategy name
    """
    logger.info("Initializing trading strategies")
    
    strategies = {}
    
    # 1. ML Ensemble Strategy - uses ML models to predict price movements
    try:
        ml_config = config.STRATEGY_CONFIGS["ml_ensemble"].copy()
        ml_config["symbols"] = symbols
        
        ml_strategy = MLEnsembleStrategy(
            config=ml_config,
            model_dir=str(config.MODELS_DIR / "ml_ensemble")
        )
        
        # Prepare the ML strategy with initial data
        for symbol in symbols:
            if symbol in market_data:
                # Train the model if needed
                if ml_strategy.needs_retraining(symbol):
                    logger.info(f"Training ML model for {symbol}")
                    features = ml_strategy.prepare_features(market_data[symbol], symbol)
                    ml_strategy.train_models(features, symbol)
        
        strategies["ml_ensemble"] = ml_strategy
        logger.info("ML Ensemble Strategy initialized")
    except Exception as e:
        logger.error(f"Error initializing ML Ensemble Strategy: {str(e)}")
    
    # 2. Advanced Crypto Strategy - multi-factor strategy with trend/momentum signals
    try:
        # Create mock context for initialization
        context = {
            "symbols": symbols,
            "timeframe": "1d",
            "lookback_window": 100,
            "indicators": ["rsi", "macd", "bbands", "atr", "stoch", "obv"]
        }
        
        adv_strategy = AdvancedCryptoStrategy(context)
        strategies["advanced_crypto"] = adv_strategy
        logger.info("Advanced Crypto Strategy initialized")
    except Exception as e:
        logger.error(f"Error initializing Advanced Crypto Strategy: {str(e)}")
    
    # 3. Statistical Arbitrage Strategy - pairs trading
    if len(symbols) >= 2:
        try:
            # Configure pairs based on top correlations
            pairs = [(symbols[0], symbols[1])]
            if len(symbols) > 2:
                pairs.append((symbols[0], symbols[2]))
            
            stat_arb_strategy = StatisticalArbitrageStrategy(
                pairs=pairs,
                lookback_window=20,
                entry_threshold=2.0,
                exit_threshold=0.0,
                stop_loss_threshold=4.0
            )
            
            strategies["stat_arb"] = stat_arb_strategy
            logger.info("Statistical Arbitrage Strategy initialized")
        except Exception as e:
            logger.error(f"Error initializing Statistical Arbitrage Strategy: {str(e)}")
    
    # 4. Mean Reversion Strategy - simulated using RSI-based signals
    try:
        class MeanReversionStrategy:
            def __init__(self, oversold_threshold=30, overbought_threshold=70):
                self.oversold = oversold_threshold
                self.overbought = overbought_threshold
                
            def generate_signal(self, market_data):
                # Get the first symbol for simplicity
                symbol = next(iter(market_data))
                data = market_data[symbol]
                
                # Calculate RSI if not already present
                if 'rsi_14' not in data.columns:
                    deltas = data['close'].diff()
                    gain = deltas.where(deltas > 0, 0).rolling(window=14).mean()
                    loss = -deltas.where(deltas < 0, 0).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = data['rsi_14']
                
                # Get the latest RSI value
                latest_rsi = rsi.iloc[-1]
                
                # Generate signal (-1 to 1)
                if latest_rsi < self.oversold:
                    return 1.0  # Oversold - buy signal
                elif latest_rsi > self.overbought:
                    return -1.0  # Overbought - sell signal
                else:
                    # Scale between oversold and overbought
                    normalized = (latest_rsi - self.oversold) / (self.overbought - self.oversold)
                    signal = 1.0 - 2.0 * normalized  # Map to [-1, 1]
                    return signal
        
        mean_reversion = MeanReversionStrategy()
        strategies["mean_reversion"] = mean_reversion
        logger.info("Mean Reversion Strategy initialized")
    except Exception as e:
        logger.error(f"Error initializing Mean Reversion Strategy: {str(e)}")
    
    # 5. Trend Following Strategy - simulated using moving average crossovers
    try:
        class TrendFollowingStrategy:
            def __init__(self, fast_period=10, slow_period=30):
                self.fast_period = fast_period
                self.slow_period = slow_period
                
            def generate_signal(self, market_data):
                # Get the first symbol for simplicity
                symbol = next(iter(market_data))
                data = market_data[symbol]
                
                # Calculate moving averages
                close = data['close']
                fast_ma = close.rolling(window=self.fast_period).mean()
                slow_ma = close.rolling(window=self.slow_period).mean()
                
                # Calculate crossover signal
                crossover = fast_ma - slow_ma
                
                # Normalize the signal between -1 and 1
                # We'll use the ratio of the crossover to the price
                price = close.iloc[-1]
                norm_crossover = (crossover / price).iloc[-1]
                
                # Clip and scale the signal
                signal = max(-1.0, min(1.0, norm_crossover * 10))
                
                return signal
        
        trend_following = TrendFollowingStrategy()
        strategies["trend_following"] = trend_following
        logger.info("Trend Following Strategy initialized")
    except Exception as e:
        logger.error(f"Error initializing Trend Following Strategy: {str(e)}")
    
    logger.info(f"Initialized {len(strategies)} strategies: {list(strategies.keys())}")
    return strategies

def run_meta_strategy_backtest(
    strategies: Dict[str, Any], 
    market_data: Dict[str, pd.DataFrame],
    args: Any
) -> AdaptiveMetaStrategy:
    """
    Run backtest for the Adaptive Meta-Strategy.
    
    Parameters:
    -----------
    strategies : Dict[str, Any]
        Dictionary of strategy instances keyed by strategy name
    market_data : Dict[str, pd.DataFrame]
        Dictionary of market data frames by symbol
    args : argparse.Namespace
        Command line arguments
        
    Returns:
    --------
    AdaptiveMetaStrategy
        The meta-strategy instance after backtesting
    """
    logger.info("Initializing Adaptive Meta-Strategy")
    
    # Create regime detector
    regime_detector = BayesianChangepointDetector(hazard_function=0.01)
    
    # Create portfolio allocator
    allocator = PortfolioAllocator(
        method=args.allocation_method,
        target_volatility=args.target_volatility
    )
    
    # Create base allocations (equal weights initially)
    base_allocations = {name: 1.0 / len(strategies) for name in strategies.keys()}
    
    # Create meta-strategy
    meta_strategy = AdaptiveMetaStrategy(
        strategies=strategies,
        regime_detector=regime_detector,
        allocator=allocator,
        base_allocations=base_allocations,
        lookback_window=60,
        regime_memory=252,
        allocation_method=args.allocation_method,
        max_allocation=0.5,
        min_allocation=0.0,
        target_volatility=args.target_volatility,
        adaptation_speed=0.1
    )
    
    # Set up results directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Find all valid dates in the data (dates where all symbols have data)
    all_dates = set()
    for symbol, df in market_data.items():
        if all_dates:
            all_dates &= set(df.index)
        else:
            all_dates = set(df.index)
    
    all_dates = sorted(list(all_dates))
    
    # Run backtest for each date in chronological order
    logger.info(f"Running backtest with {len(all_dates)} data points")
    
    # Track portfolio value over time
    portfolio_value = 10000.0  # Starting capital
    portfolio_history = []
    allocation_history = []
    regime_history = []
    
    for date in all_dates:
        # Create a subset of market data up to this date for each symbol
        current_data = {}
        for symbol, df in market_data.items():
            if date in df.index:
                # Include all data up to and including this date
                current_data[symbol] = df.loc[:date].copy()
        
        # Skip if we don't have data for all symbols
        if len(current_data) != len(market_data):
            continue
        
        # Update the meta-strategy
        positions = meta_strategy.update(current_data)
        
        # Calculate portfolio return based on positions and market returns
        daily_return = 0
        for symbol, position in positions.items():
            # Get the market return for this symbol
            if len(current_data[symbol]) > 1:
                market_return = current_data[symbol]['returns'].iloc[-1]
                # Scale by position size
                daily_return += position * market_return
        
        # Update portfolio value
        portfolio_value *= (1 + daily_return)
        
        # Record portfolio value and other metrics
        portfolio_history.append({
            'date': date,
            'portfolio_value': portfolio_value,
            'daily_return': daily_return
        })
        
        # Record allocations
        allocation_history.append({
            'date': date,
            **meta_strategy.current_allocations
        })
        
        # Record regime
        regime_history.append({
            'date': date,
            'regime': meta_strategy.current_regime
        })
    
    # Convert to DataFrames
    portfolio_df = pd.DataFrame(portfolio_history)
    allocation_df = pd.DataFrame(allocation_history)
    regime_df = pd.DataFrame(regime_history)
    
    # Save results
    portfolio_df.to_csv(os.path.join(args.output_dir, 'portfolio_history.csv'), index=False)
    allocation_df.to_csv(os.path.join(args.output_dir, 'allocation_history.csv'), index=False)
    regime_df.to_csv(os.path.join(args.output_dir, 'regime_history.csv'), index=False)
    
    # Generate visualizations
    visualize_results(meta_strategy, portfolio_df, allocation_df, regime_df, args.output_dir)
    
    # Save strategy state if requested
    if args.save_state:
        save_path = os.path.join(args.output_dir, 'adaptive_meta_strategy.json')
        if meta_strategy.save(save_path):
            logger.info(f"Strategy state saved to {save_path}")
    
    return meta_strategy

def visualize_results(
    meta_strategy: AdaptiveMetaStrategy, 
    portfolio_df: pd.DataFrame, 
    allocation_df: pd.DataFrame, 
    regime_df: pd.DataFrame, 
    output_dir: str
) -> None:
    """
    Generate and save visualizations of the meta-strategy results.
    
    Parameters:
    -----------
    meta_strategy : AdaptiveMetaStrategy
        The meta-strategy instance
    portfolio_df : pd.DataFrame
        DataFrame with portfolio history
    allocation_df : pd.DataFrame
        DataFrame with allocation history
    regime_df : pd.DataFrame
        DataFrame with regime history
    output_dir : str
        Directory to save results
    """
    logger.info("Generating visualizations")
    
    # 1. Portfolio Value Over Time with Regime Background
    fig, ax = plt.subplots(figsize=(12, 6))
    portfolio_df.set_index('date')['portfolio_value'].plot(ax=ax, linewidth=2)
    
    # Add regime background
    meta_strategy._add_regime_background(ax, regime_df.set_index('date'))
    
    ax.set_title('Adaptive Meta-Strategy: Portfolio Value Over Time')
    ax.set_xlabel('Date')
    ax.set_ylabel('Portfolio Value')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, 'portfolio_value.png'))
    
    # 2. Strategy Allocations Over Time
    fig = meta_strategy.visualize_allocations()
    fig.savefig(os.path.join(output_dir, 'strategy_allocations.png'))
    
    # 3. Performance by Regime
    fig = meta_strategy.visualize_regime_performance()
    fig.savefig(os.path.join(output_dir, 'regime_performance.png'))
    
    # 4. Cumulative Returns Comparison
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Calculate cumulative returns for portfolio
    portfolio_df['cumulative_return'] = (1 + portfolio_df['daily_return']).cumprod() - 1
    portfolio_df.set_index('date')['cumulative_return'].plot(ax=ax, linewidth=2, label='Adaptive Meta-Strategy')
    
    # Calculate benchmark returns (using first symbol as benchmark)
    benchmark_symbol = next(iter(portfolio_df.keys()))
    
    ax.set_title('Adaptive Meta-Strategy vs Benchmark: Cumulative Returns')
    ax.set_xlabel('Date')
    ax.set_ylabel('Cumulative Return')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, 'cumulative_returns.png'))
    
    # 5. Summary Performance Metrics
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Calculate performance metrics
    returns = portfolio_df['daily_return']
    
    total_return = portfolio_df['portfolio_value'].iloc[-1] / portfolio_df['portfolio_value'].iloc[0] - 1
    annualized_return = (1 + total_return) ** (252 / len(returns)) - 1
    volatility = returns.std() * np.sqrt(252)
    sharpe_ratio = annualized_return / volatility if volatility != 0 else 0
    
    # Calculate max drawdown
    portfolio_value = portfolio_df['portfolio_value']
    peak = portfolio_value.cummax()
    drawdown = (portfolio_value / peak - 1)
    max_drawdown = drawdown.min()
    
    # Calculate win rate
    win_rate = (returns > 0).mean()
    
    # Display metrics
    ax.axis('off')
    plt.text(0.5, 0.9, 'Adaptive Meta-Strategy Performance Metrics', 
           fontsize=16, ha='center', weight='bold')
    
    metrics_text = [
        f"Total Return: {total_return:.2%}",
        f"Annualized Return: {annualized_return:.2%}",
        f"Annualized Volatility: {volatility:.2%}",
        f"Sharpe Ratio: {sharpe_ratio:.2f}",
        f"Maximum Drawdown: {max_drawdown:.2%}",
        f"Win Rate: {win_rate:.2%}",
        f"Number of Days: {len(returns)}",
        f"Current Regime: {meta_strategy.current_regime}"
    ]
    
    for i, text in enumerate(metrics_text):
        plt.text(0.5, 0.8 - i * 0.07, text, fontsize=12, ha='center')
    
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, 'performance_metrics.png'))
    
    logger.info(f"Visualizations saved to {output_dir}")

def main():
    """Main function to run the Adaptive Meta-Strategy example."""
    # Parse command line arguments
    args = parse_args()
    
    # Load market data
    market_data = load_market_data(args.symbols, args.timeframe, args.start_date, args.end_date)
    
    if not market_data:
        logger.error("No market data loaded. Exiting.")
        return 1
    
    # Initialize strategies
    strategies = initialize_strategies(args.symbols, market_data)
    
    if not strategies:
        logger.error("No strategies initialized. Exiting.")
        return 1
    
    # Run meta-strategy backtest
    meta_strategy = run_meta_strategy_backtest(strategies, market_data, args)
    
    logger.info("Adaptive Meta-Strategy example completed")
    logger.info(f"Results saved to {args.output_dir}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 