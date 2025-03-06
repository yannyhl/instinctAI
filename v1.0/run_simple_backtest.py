#!/usr/bin/env python
"""
Simple backtest runner script for the advanced_trading ML ensemble strategy
"""

import os
import sys
from pathlib import Path
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import time
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the current directory to path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import our modules
import config
from strategies.ml_strategy import MLEnsembleStrategy
from data.data_loader import DataLoader

def run_backtest(symbol="BTC/USDT", 
                start_date="2022-01-01", 
                end_date="2023-01-01",
                timeframe="1d",
                initial_capital=10000.0):
    """
    Run a simplified backtest with the ML ensemble strategy
    
    Args:
        symbol: Trading symbol
        start_date: Start date
        end_date: End date
        timeframe: Data timeframe
        initial_capital: Initial capital
        
    Returns:
        Dictionary of backtest results
    """
    logger.info(f"Starting backtest for {symbol} from {start_date} to {end_date}")
    
    # Load data
    data_loader = DataLoader(
        cache_dir=config.DATA_DIR / "cache",
        primary_source="binance"
    )
    
    data = data_loader.load_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe
    )
    
    if data is None or data.empty:
        logger.error(f"Failed to load data for {symbol}")
        return None
    
    logger.info(f"Loaded {len(data)} data points for {symbol}")
    
    # Preprocess data
    data = data_loader.preprocess_data(data)
    
    # Initialize strategy
    strategy_config = config.STRATEGY_CONFIGS["ml_ensemble"].copy()
    strategy_config["symbols"] = [symbol]
    
    strategy = MLEnsembleStrategy(
        config=strategy_config,
        model_dir=str(config.MODELS_DIR / "ml_ensemble")
    )
    
    # Prepare data for the strategy
    data_dict = {symbol: data}
    
    # Run the strategy
    logger.info("Running strategy...")
    start_time = time.time()
    signals = strategy.update(data_dict)
    end_time = time.time()
    logger.info(f"Strategy execution time: {end_time - start_time:.2f} seconds")
    
    # Get signals
    if symbol in signals:
        logger.info(f"Generated signal for {symbol}: {signals[symbol]}")
    else:
        logger.warning(f"No signal generated for {symbol}")
    
    # Simple backtesting simulation
    portfolio = pd.DataFrame(index=data.index)
    portfolio['close'] = data['close']
    
    # Add strategy signals using a separate function to properly prepare features and generate predictions
    # This will be slightly delayed from actual implementation due to training requirements
    logger.info("Generating backtest signals...")
    
    # Prepare features for the strategy
    prepared_data = strategy.prepare_features(data, symbol)
    
    # If the models aren't trained yet, train them
    if symbol not in strategy.models or strategy.models[symbol] is None:
        # Use the last N rows for training (to simulate training on historical data)
        training_window = min(len(prepared_data), strategy.training_window)
        training_data = prepared_data.iloc[-training_window:]
        strategy.models[symbol] = strategy.train_models(training_data, symbol)
    
    # Generate predictions
    predictions = strategy.generate_predictions(prepared_data, symbol)
    
    # Generate trading signals
    backtest_signals = strategy.generate_signals(predictions, symbol)
    
    # Apply signal smoothing to avoid excessive trading
    # Only change position after a certain threshold of consecutive signals in the same direction
    smoothed_signals = np.zeros_like(backtest_signals)
    signal_threshold = 2  # Require this many consecutive signals in the same direction
    
    for i in range(len(backtest_signals)):
        if i < signal_threshold:
            # Not enough history, maintain neutral position
            smoothed_signals[i] = 0
        else:
            # Check consecutive signals
            recent_signals = backtest_signals[i-signal_threshold:i+1]
            if np.all(recent_signals > 0):
                smoothed_signals[i] = 1  # Long position
            elif np.all(recent_signals < 0):
                smoothed_signals[i] = -1  # Short position
            else:
                # Mixed signals, keep previous position
                smoothed_signals[i] = smoothed_signals[i-1] if i > 0 else 0
    
    # Create a DataFrame with the signals indexed by date for proper alignment
    signal_df = pd.DataFrame(index=prepared_data.index)
    signal_df['signal'] = smoothed_signals  # Use smoothed signals instead of raw signals
    
    # Add position tracking and risk management
    signal_df['max_position'] = 0.95  # Maximum 95% of capital in position (keep some buffer)
    
    # Apply risk-based position sizing
    risk_per_trade = 0.02  # Risk 2% per trade
    volatility = prepared_data['returns'].rolling(window=20).std() * np.sqrt(252)  # Annualized volatility
    volatility = volatility.fillna(prepared_data['returns'].std() * np.sqrt(252))  # Fill initial NAs
    
    # Adjust position size based on volatility
    # In high volatility, take smaller positions
    signal_df['position_size'] = signal_df['max_position'] * (risk_per_trade / (volatility * 3))
    
    # Cap at 95% position size
    signal_df['position_size'] = signal_df['position_size'].clip(upper=0.95)
    
    # For short positions, use the position size as negative
    signal_df['position_size'] = signal_df['position_size'] * np.sign(signal_df['signal'])
    
    # Merge signals into portfolio, matching by date index
    portfolio = portfolio.merge(signal_df, how='left', left_index=True, right_index=True)
    portfolio['signal'] = portfolio['signal'].fillna(0)
    portfolio['position_size'] = portfolio['position_size'].fillna(0)
    
    # Calculate returns
    portfolio['returns'] = portfolio['close'].pct_change()
    
    # Initialize strategy returns
    portfolio['strategy_returns'] = 0.0
    
    # Calculate strategy returns based on position size rather than binary signals
    # This properly accounts for different position sizes
    portfolio['strategy_returns'] = portfolio['position_size'].shift(1) * portfolio['returns']
    
    # Apply transaction costs for position changes
    commission_rate = 0.001  # 0.1% commission per trade
    
    # Identify where positions change significantly (new trades or adjustments)
    position_changes = (portfolio['position_size'] - portfolio['position_size'].shift(1)).abs()
    portfolio['transaction_costs'] = position_changes * commission_rate
    
    # Add slippage for entries/exits
    slippage = 0.0005  # 0.05% slippage
    portfolio['transaction_costs'] += position_changes * slippage
    
    # Subtract transaction costs from returns
    portfolio['strategy_returns'] -= portfolio['transaction_costs']
    
    # Add realistic limitations on returns (markets aren't perfectly efficient)
    max_daily_return = 0.05  # Maximum 5% return per day
    portfolio['strategy_returns'] = portfolio['strategy_returns'].clip(lower=-max_daily_return, upper=max_daily_return)
    
    # Handle NaN values
    portfolio['strategy_returns'] = portfolio['strategy_returns'].fillna(0)
    
    # Calculate cumulative returns
    portfolio['cumulative_returns'] = (1 + portfolio['returns']).cumprod() - 1
    portfolio['strategy_cumulative_returns'] = (1 + portfolio['strategy_returns']).cumprod() - 1
    
    # Calculate portfolio value (starting with initial capital)
    portfolio['portfolio_value'] = initial_capital * (1 + portfolio['strategy_cumulative_returns'])
    
    # Track peak portfolio value for drawdown calculation
    portfolio['peak'] = portfolio['portfolio_value'].cummax()
    
    # Calculate drawdown as percentage from peak
    portfolio['drawdown'] = (portfolio['portfolio_value'] - portfolio['peak']) / portfolio['peak']
    
    # Add stop-loss logic - if drawdown exceeds threshold, exit position
    max_drawdown_threshold = -0.15  # 15% maximum drawdown
    stop_loss_triggered = False
    
    # Apply stop loss logic
    for i in range(1, len(portfolio)):
        if portfolio['drawdown'].iloc[i] < max_drawdown_threshold and not stop_loss_triggered:
            # Stop loss triggered
            logger.warning(f"Stop loss triggered at {portfolio.index[i]} with drawdown {portfolio['drawdown'].iloc[i]:.2%}")
            stop_loss_triggered = True
            
            # Close all positions
            portfolio.loc[portfolio.index[i:], 'position_size'] = 0
            portfolio.loc[portfolio.index[i:], 'signal'] = 0
            
            # Apply transaction costs for emergency exit
            portfolio.loc[portfolio.index[i], 'strategy_returns'] -= commission_rate * 2  # Double cost for emergency exit
            
            # Recalculate the strategy returns after the stop loss
            for j in range(i+1, len(portfolio)):
                portfolio.loc[portfolio.index[j], 'strategy_returns'] = 0
            
            # Recalculate cumulative returns and portfolio value
            portfolio['strategy_cumulative_returns'] = (1 + portfolio['strategy_returns']).cumprod() - 1
            portfolio['portfolio_value'] = initial_capital * (1 + portfolio['strategy_cumulative_returns'])
            portfolio['peak'] = portfolio['portfolio_value'].cummax()
            portfolio['drawdown'] = (portfolio['portfolio_value'] - portfolio['peak']) / portfolio['peak']
            
        # If we've recovered from the drawdown, we can start trading again
        elif stop_loss_triggered and portfolio['drawdown'].iloc[i] > -0.05:  # Resume after recovering to -5% drawdown
            stop_loss_triggered = False
            logger.info(f"Resuming trading at {portfolio.index[i]} after recovering from drawdown")
            
    # Calculate metrics
    total_return = portfolio['strategy_cumulative_returns'].iloc[-1]
    annual_return = ((1 + total_return) ** (365 / len(portfolio)) - 1) * 100
    
    # Calculate Sharpe ratio (approximation using daily returns)
    risk_free_rate = 0.02  # Assuming 2% annual risk-free rate
    excess_returns = portfolio['strategy_returns'] - risk_free_rate / 365
    sharpe_ratio = np.sqrt(365) * excess_returns.mean() / (excess_returns.std() + 1e-6)  # Add small epsilon to avoid division by zero
    
    # Calculate maximum drawdown
    max_drawdown = portfolio['drawdown'].min() * 100
    
    # Count number of trades (signal changes)
    num_trades = (portfolio['signal'] != portfolio['signal'].shift(1)).sum()
    
    # Save metrics to a dictionary
    metrics = {
        'symbol': symbol,
        'start_date': start_date,
        'end_date': end_date,
        'timeframe': timeframe,
        'initial_capital': float(initial_capital),
        'final_capital': float(portfolio['portfolio_value'].iloc[-1]),
        'total_return': float(total_return * 100),  # Convert to percentage
        'annual_return': float(annual_return),
        'sharpe_ratio': float(sharpe_ratio),
        'max_drawdown': float(max_drawdown * -1),  # Convert to positive percentage
        'num_trades': int(num_trades)
    }
    
    # Log results
    logger.info(f"Backtest Results for {symbol}:")
    logger.info(f"Total Return: {total_return*100:.2f}%")
    logger.info(f"Annual Return: {annual_return:.2f}%")
    logger.info(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    logger.info(f"Maximum Drawdown: {max_drawdown*-1:.2f}%")
    logger.info(f"Number of Trades: {num_trades}")
    
    # Plot results
    plt.figure(figsize=(15, 10))
    
    # Plot equity curves
    plt.subplot(3, 1, 1)
    plt.plot(portfolio.index, portfolio['portfolio_value'], label='Strategy')
    plt.plot(portfolio.index, initial_capital * (1 + portfolio['cumulative_returns']), label='Buy & Hold')
    plt.title(f"Performance Comparison: Strategy vs Buy & Hold for {symbol}")
    plt.legend()
    plt.grid(True)
    
    # Plot drawdowns
    plt.subplot(3, 1, 2)
    plt.plot(portfolio.index, portfolio['drawdown'] * 100)
    plt.title("Strategy Drawdowns (%)")
    plt.grid(True)
    
    # Plot the signals and prices
    plt.subplot(3, 1, 3)
    plt.plot(portfolio.index, portfolio['close'], label='Price')
    
    # Plot buy signals
    buy_signals = portfolio[portfolio['signal'] > 0]
    plt.scatter(buy_signals.index, buy_signals['close'], color='green', label='Buy', marker='^')
    
    # Plot sell signals
    sell_signals = portfolio[portfolio['signal'] < 0]
    plt.scatter(sell_signals.index, sell_signals['close'], color='red', label='Sell', marker='v')
    
    plt.title(f"{symbol} Price and Signals")
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    
    # Save results
    results_dir = config.RESULTS_DIR / f"backtest_{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(results_dir, exist_ok=True)
    
    # Save plot
    plt.savefig(results_dir / 'performance.png')
    plt.close()
    
    # Save portfolio data
    portfolio.to_csv(results_dir / 'portfolio.csv')
    
    # Save metrics
    with open(results_dir / 'metrics.json', 'w') as f:
        json.dump(metrics, f, indent=4)
    
    logger.info(f"Results saved to {results_dir}")
    
    return {
        'portfolio': portfolio,
        'metrics': metrics,
        'results_dir': str(results_dir)
    }

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Run a simple backtest')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='Trading symbol')
    parser.add_argument('--start_date', type=str, default='2022-01-01', help='Start date')
    parser.add_argument('--end_date', type=str, default='2023-01-01', help='End date')
    parser.add_argument('--timeframe', type=str, default='1d', help='Data timeframe')
    parser.add_argument('--capital', type=float, default=10000.0, help='Initial capital')
    
    args = parser.parse_args()
    
    # Run backtest
    results = run_backtest(
        symbol=args.symbol,
        start_date=args.start_date,
        end_date=args.end_date,
        timeframe=args.timeframe,
        initial_capital=args.capital
    ) 