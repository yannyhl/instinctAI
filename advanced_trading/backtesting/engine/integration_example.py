"""
Integration Example: TimeSeriesCV and WalkForwardTest
---------------------------------------------------
This example demonstrates how the TimeSeriesCV class integrates with the 
WalkForwardTest framework for proper temporal validation of trading strategies.

The example shows:
1. How to load market data
2. How to create a simple trading strategy
3. How to optimize strategy parameters with cross-validation
4. How to run walk-forward testing
5. How to visualize and analyze results
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Any
import logging
import yfinance as yf
from datetime import datetime, timedelta

# Import our modules
from advanced_trading.utils.cross_validation import TimeSeriesCV
from advanced_trading.backtesting.engine.walk_forward import WalkForwardTest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_example_data(ticker: str = 'SPY', period: str = '5y') -> pd.DataFrame:
    """
    Download financial data for example using yfinance.
    
    Parameters:
    -----------
    ticker : str
        Ticker symbol to download
    period : str
        Period to download (e.g. '1y', '2y', '5y')
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with OHLCV data
    """
    logger.info(f"Downloading {ticker} data for {period}")
    data = yf.download(ticker, period=period)
    
    # Add some basic features
    data['returns'] = data['Close'].pct_change()
    data['ma_10'] = data['Close'].rolling(10).mean()
    data['ma_30'] = data['Close'].rolling(30).mean()
    data['ma_50'] = data['Close'].rolling(50).mean()
    data['rsi'] = compute_rsi(data['Close'])
    
    # Rename columns to lowercase for consistency
    data.columns = [col.lower() for col in data.columns]
    
    # Drop NaN values
    data.dropna(inplace=True)
    
    logger.info(f"Downloaded {len(data)} rows of data")
    return data

def compute_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """
    Compute the Relative Strength Index (RSI).
    
    Parameters:
    -----------
    prices : pd.Series
        Price series
    window : int
        RSI window period
        
    Returns:
    --------
    pd.Series
        RSI values
    """
    # Calculate price changes
    delta = prices.diff()
    
    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Calculate average gain and loss
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

class MACrossoverStrategy:
    """
    Simple Moving Average Crossover Strategy.
    
    This strategy generates buy signals when the fast MA crosses above the slow MA,
    and sell signals when the fast MA crosses below the slow MA.
    
    Parameters:
    -----------
    fast_period : int
        Fast moving average period
    slow_period : int
        Slow moving average period
    rsi_period : int
        RSI period for filter
    rsi_oversold : float
        RSI oversold threshold for entry filter
    rsi_overbought : float
        RSI overbought threshold for exit filter
    """
    
    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 30,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0
    ):
        """Initialize strategy parameters."""
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
    def generate_signals(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals.
        
        Parameters:
        -----------
        market_data : pd.DataFrame
            Market data with price and indicator columns
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with added signal columns
        """
        data = market_data.copy()
        
        # Calculate moving averages if not already present
        if f'ma_{self.fast_period}' not in data.columns:
            data[f'ma_{self.fast_period}'] = data['close'].rolling(self.fast_period).mean()
            
        if f'ma_{self.slow_period}' not in data.columns:
            data[f'ma_{self.slow_period}'] = data['close'].rolling(self.slow_period).mean()
            
        # Calculate RSI if not already present
        if 'rsi' not in data.columns or self.rsi_period != 14:  # 14 is default in our download function
            data['rsi'] = compute_rsi(data['close'], self.rsi_period)
            
        # Get fast and slow MA columns
        fast_ma = f'ma_{self.fast_period}'
        slow_ma = f'ma_{self.slow_period}'
        
        # Create crossover signals
        data['ma_diff'] = data[fast_ma] - data[slow_ma]
        data['signal'] = 0
        
        # Previous MA diff for crossover detection
        data['prev_ma_diff'] = data['ma_diff'].shift(1)
        
        # Buy signals: Fast MA crosses above Slow MA and RSI is oversold
        buy_signals = (
            (data['ma_diff'] > 0) & 
            (data['prev_ma_diff'] <= 0) & 
            (data['rsi'] < self.rsi_oversold)
        )
        
        # Sell signals: Fast MA crosses below Slow MA or RSI is overbought
        sell_signals = (
            (data['ma_diff'] < 0) & 
            (data['prev_ma_diff'] >= 0)
        ) | (data['rsi'] > self.rsi_overbought)
        
        # Apply signals
        data.loc[buy_signals, 'signal'] = 1  # Buy
        data.loc[sell_signals, 'signal'] = -1  # Sell
        
        # Generate position column (cumulative sum of signals)
        data['position'] = data['signal'].cumsum().clip(0, 1)
        
        return data

def run_backtest(
    strategy: MACrossoverStrategy,
    market_data: pd.DataFrame,
    initial_capital: float = 100000.0,
    commission: float = 0.001,
    slippage: float = 0.001
) -> Dict[str, Any]:
    """
    Run a backtest on the strategy.
    
    Parameters:
    -----------
    strategy : MACrossoverStrategy
        Strategy to backtest
    market_data : pd.DataFrame
        Market data with OHLCV
    initial_capital : float
        Initial capital
    commission : float
        Commission rate per trade
    slippage : float
        Slippage rate per trade
        
    Returns:
    --------
    Dict[str, Any]
        Backtest results
    """
    # Generate signals
    data = strategy.generate_signals(market_data)
    
    # Ensure we have a position column
    if 'position' not in data.columns:
        raise ValueError("Strategy did not generate position column")
        
    # Calculate position changes (trades)
    data['position_change'] = data['position'].diff()
    
    # Calculate trade sizes and costs
    data['trade_price'] = data['close'] * (1 + slippage * data['position_change'].apply(np.sign))
    data['trade_size'] = abs(data['position_change']) * initial_capital
    data['trade_cost'] = data['trade_size'] * commission
    data['trade_value'] = data['position_change'] * data['trade_price'] * initial_capital
    
    # Calculate equity and returns
    data['equity'] = initial_capital - data['trade_value'].cumsum() - data['trade_cost'].cumsum()
    data['equity'] = data['equity'] + data['position'] * data['close'] * initial_capital
    data['returns'] = data['equity'].pct_change()
    
    # Extract trades
    trades = []
    for i, row in data[data['position_change'] != 0].iterrows():
        trade = {
            'date': i,
            'type': 'buy' if row['position_change'] > 0 else 'sell',
            'price': row['trade_price'],
            'size': row['trade_size'],
            'cost': row['trade_cost'],
            'value': abs(row['trade_value']),
            'pnl': 0  # Will calculate this later
        }
        trades.append(trade)
        
    # Calculate trade P&L
    for i in range(1, len(trades)):
        if trades[i]['type'] == 'sell' and trades[i-1]['type'] == 'buy':
            pnl = trades[i]['price'] - trades[i-1]['price']
            pnl = pnl * initial_capital - trades[i]['cost'] - trades[i-1]['cost']
            trades[i]['pnl'] = pnl
    
    # Calculate performance metrics
    total_return = (data['equity'].iloc[-1] / initial_capital) - 1 if len(data) > 0 else 0
    annual_return = (1 + total_return) ** (252 / len(data)) - 1 if len(data) > 0 else 0
    volatility = data['returns'].std() * np.sqrt(252) if len(data) > 0 else 0
    sharpe_ratio = annual_return / volatility if volatility > 0 else 0
    max_drawdown = (data['equity'] / data['equity'].cummax() - 1).min() if len(data) > 0 else 0
    
    # Compile results
    results = {
        'equity_curve': data['equity'],
        'returns': data['returns'],
        'trades': trades,
        'signals': data[['close', 'position', 'position_change']],
        'metrics': {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': sum(1 for t in trades if t['pnl'] > 0) / len(trades) if trades else 0
        }
    }
    
    return results

def optimize_parameters(
    strategy_class: Any,
    market_data: pd.DataFrame,
    default_params: Dict[str, Any],
    backtest_func: Any,
    initial_capital: float = 100000.0,
    commission: float = 0.001,
    slippage: float = 0.001
) -> Dict[str, Any]:
    """
    Optimize strategy parameters using TimeSeriesCV.
    
    Parameters:
    -----------
    strategy_class : Any
        Strategy class to optimize
    market_data : pd.DataFrame
        Market data
    default_params : Dict[str, Any]
        Default parameters
    backtest_func : Any
        Backtest function
    initial_capital : float
        Initial capital
    commission : float
        Commission rate
    slippage : float
        Slippage rate
        
    Returns:
    --------
    Dict[str, Any]
        Optimized parameters
    """
    # Parameter grid
    param_grid = {
        'fast_period': [5, 10, 15, 20],
        'slow_period': [20, 30, 40, 50],
        'rsi_oversold': [20, 25, 30, 35],
        'rsi_overbought': [65, 70, 75, 80]
    }
    
    # Create TimeSeriesCV
    cv = TimeSeriesCV(
        cv_method='sliding',
        n_splits=3,
        train_size=0.6,
        test_size=0.2,
        purge_size=0.05
    )
    
    # Generate CV splits
    splits = list(cv.split(market_data))
    
    # Track best parameters
    best_params = default_params.copy()
    best_score = -float('inf')
    
    # Simple grid search (for demo purposes)
    # In a real application, you would use a more sophisticated approach
    for fast_period in param_grid['fast_period']:
        for slow_period in param_grid['slow_period']:
            # Skip invalid combinations
            if fast_period >= slow_period:
                continue
                
            for rsi_oversold in param_grid['rsi_oversold']:
                for rsi_overbought in param_grid['rsi_overbought']:
                    # Skip invalid combinations
                    if rsi_oversold >= rsi_overbought:
                        continue
                        
                    current_params = {
                        'fast_period': fast_period,
                        'slow_period': slow_period,
                        'rsi_oversold': rsi_oversold,
                        'rsi_overbought': rsi_overbought
                    }
                    
                    # Evaluate with CV
                    cv_scores = []
                    for train_idx, test_idx in splits:
                        train_data = market_data.iloc[train_idx]
                        test_data = market_data.iloc[test_idx]
                        
                        strategy = strategy_class(**current_params)
                        result = backtest_func(
                            strategy=strategy,
                            market_data=test_data,
                            initial_capital=initial_capital,
                            commission=commission,
                            slippage=slippage
                        )
                        
                        cv_scores.append(result['metrics']['sharpe_ratio'])
                    
                    # Calculate mean score
                    mean_score = np.mean(cv_scores)
                    
                    # Update best params if better
                    if mean_score > best_score:
                        best_score = mean_score
                        best_params = current_params.copy()
                        logger.info(f"New best parameters: {best_params} with CV Sharpe: {best_score:.4f}")
    
    logger.info(f"Optimized parameters: {best_params} with CV Sharpe: {best_score:.4f}")
    return best_params

def main():
    """Execute the integration example."""
    try:
        logger.info("Starting TimeSeriesCV and WalkForwardTest integration example")
        
        # 1. Download market data
        market_data = download_example_data()
        
        # 2. Define default strategy parameters
        default_params = {
            'fast_period': 10,
            'slow_period': 30,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70
        }
        
        # 3. Create and run a simple backtest
        logger.info("Running simple backtest with default parameters")
        strategy = MACrossoverStrategy(**default_params)
        backtest_result = run_backtest(strategy, market_data)
        
        logger.info(f"Default parameters backtest metrics: "
                   f"Sharpe={backtest_result['metrics']['sharpe_ratio']:.2f}, "
                   f"Return={backtest_result['metrics']['total_return']:.2%}")
        
        # 4. Optimize parameters
        logger.info("Optimizing strategy parameters")
        optimized_params = optimize_parameters(
            strategy_class=MACrossoverStrategy,
            market_data=market_data,
            default_params=default_params,
            backtest_func=run_backtest
        )
        
        # 5. Run walk-forward test
        logger.info("Running walk-forward test")
        wf_test = WalkForwardTest(
            market_data=market_data,
            train_size=0.5,
            test_size=0.2,
            step_size=0.1,
            window_type='sliding',
            purge_window=0.05,
            optimization_func=optimize_parameters
        )
        
        wf_results = wf_test.run(
            strategy_class=MACrossoverStrategy,
            default_params=default_params,
            backtest_func=run_backtest,
            show_progress=True
        )
        
        # 6. Plot results
        wf_test.plot_equity_curves()
        plt.title("Walk-Forward Test - Equity Curves")
        plt.tight_layout()
        plt.show()
        
        wf_test.plot_parameter_stability()
        plt.suptitle("Walk-Forward Test - Parameter Stability")
        plt.tight_layout()
        plt.show()
        
        wf_test.plot_performance_by_period()
        plt.title("Walk-Forward Test - Performance by Period")
        plt.tight_layout()
        plt.show()
        
        wf_test.plot_train_test_windows()
        plt.title("Walk-Forward Test - Train/Test Windows")
        plt.tight_layout()
        plt.show()
        
        # 7. Analyze robustness
        robustness = wf_test.compute_robustness_metrics()
        logger.info(f"Robustness metrics: {robustness}")
        
        # 8. Save results
        wf_test.save_results("walk_forward_results.json")
        
        logger.info("TimeSeriesCV and WalkForwardTest integration example completed successfully")
        
    except Exception as e:
        logger.error(f"Error in integration example: {e}", exc_info=True)

if __name__ == "__main__":
    main() 