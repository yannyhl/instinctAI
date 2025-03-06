"""
Walk-Forward Testing Example
---------------------------
This script demonstrates how to use the walk-forward testing framework
for evaluating trading strategies with proper temporal validation.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any, List
import logging
from pathlib import Path
import yfinance as yf

# Import the walk-forward testing framework
from advanced_trading.backtesting.engine.walk_forward import WalkForwardTest, optimize_parameters

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define a simple trading strategy for demonstration
class SimpleMovingAverageStrategy:
    """
    Simple Moving Average (SMA) Crossover Strategy.
    
    This strategy generates buy signals when a fast moving average crosses above
    a slow moving average, and sell signals when it crosses below.
    """
    
    def __init__(self, fast_window: int = 20, slow_window: int = 50, stop_loss: float = 0.05):
        """
        Initialize the strategy with moving average parameters.
        
        Parameters:
        -----------
        fast_window : int
            Window size for the fast moving average
        slow_window : int
            Window size for the slow moving average
        stop_loss : float
            Stop loss percentage (e.g., 0.05 for 5%)
        """
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.stop_loss = stop_loss
        self.positions = {}
        
    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Generate trading signals based on moving average crossovers.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Market data for each symbol
            
        Returns:
        --------
        Dict[str, pd.DataFrame] with signals for each symbol
        """
        signals = {}
        
        for symbol, data in market_data.items():
            # Calculate moving averages
            df = data.copy()
            df['fast_ma'] = df['close'].rolling(self.fast_window).mean()
            df['slow_ma'] = df['close'].rolling(self.slow_window).mean()
            
            # Generate signals
            df['signal'] = 0.0
            
            # Buy signal (fast MA crosses above slow MA)
            df.loc[(df['fast_ma'] > df['slow_ma']) & 
                  (df['fast_ma'].shift(1) <= df['slow_ma'].shift(1)), 'signal'] = 1.0
                  
            # Sell signal (fast MA crosses below slow MA)
            df.loc[(df['fast_ma'] < df['slow_ma']) & 
                  (df['fast_ma'].shift(1) >= df['slow_ma'].shift(1)), 'signal'] = -1.0
                  
            # Store signals
            signals[symbol] = df
            
        return signals
        
    def run_backtest(self, market_data: Dict[str, pd.DataFrame], 
                    initial_capital: float = 10000, 
                    commission: float = 0.001,
                    slippage: float = 0.001) -> Dict[str, Any]:
        """
        Run a backtest of the strategy.
        
        Parameters:
        -----------
        market_data : Dict[str, pd.DataFrame]
            Market data for each symbol
        initial_capital : float
            Initial capital for the backtest
        commission : float
            Commission rate as a fraction
        slippage : float
            Slippage cost as a fraction
            
        Returns:
        --------
        Dict[str, Any] with backtest results
        """
        # Generate signals
        signals = self.generate_signals(market_data)
        
        # Run backtest for each symbol
        results = {}
        trades = []
        portfolio_values = []
        dates = []
        
        # Use the first symbol for portfolio tracking
        primary_symbol = next(iter(signals))
        
        # Initialize portfolio
        capital = initial_capital
        position = 0
        entry_price = 0
        
        # Process signals
        for date, row in signals[primary_symbol].iterrows():
            if np.isnan(row['fast_ma']) or np.isnan(row['slow_ma']):
                # Skip dates with NaN values
                continue
                
            # Check for stop loss
            if position != 0 and entry_price > 0:
                if position > 0 and row['close'] < entry_price * (1 - self.stop_loss):
                    # Stop loss hit for long position
                    sell_value = position * row['close'] * (1 - slippage)
                    commission_cost = sell_value * commission
                    capital = capital + sell_value - commission_cost
                    
                    # Record trade
                    trade = {
                        'entry_date': entry_date,
                        'exit_date': date,
                        'symbol': primary_symbol,
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'position': position,
                        'pnl': sell_value - (position * entry_price) - commission_cost,
                        'exit_reason': 'stop_loss'
                    }
                    trades.append(trade)
                    
                    # Reset position
                    position = 0
                    entry_price = 0
                    
                elif position < 0 and row['close'] > entry_price * (1 + self.stop_loss):
                    # Stop loss hit for short position
                    buy_value = abs(position) * row['close'] * (1 + slippage)
                    commission_cost = buy_value * commission
                    capital = capital - buy_value - commission_cost
                    
                    # Record trade
                    trade = {
                        'entry_date': entry_date,
                        'exit_date': date,
                        'symbol': primary_symbol,
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'position': position,
                        'pnl': (abs(position) * entry_price) - buy_value - commission_cost,
                        'exit_reason': 'stop_loss'
                    }
                    trades.append(trade)
                    
                    # Reset position
                    position = 0
                    entry_price = 0
            
            # Process signals
            if row['signal'] == 1.0 and position <= 0:
                # Buy signal
                if position < 0:
                    # Close short position
                    buy_value = abs(position) * row['close'] * (1 + slippage)
                    commission_cost = buy_value * commission
                    capital = capital - buy_value - commission_cost
                    
                    # Record trade
                    trade = {
                        'entry_date': entry_date,
                        'exit_date': date,
                        'symbol': primary_symbol,
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'position': position,
                        'pnl': (abs(position) * entry_price) - buy_value - commission_cost,
                        'exit_reason': 'signal'
                    }
                    trades.append(trade)
                
                # Open long position
                position = capital / row['close']
                entry_price = row['close']
                entry_date = date
                
            elif row['signal'] == -1.0 and position >= 0:
                # Sell signal
                if position > 0:
                    # Close long position
                    sell_value = position * row['close'] * (1 - slippage)
                    commission_cost = sell_value * commission
                    capital = capital + sell_value - commission_cost
                    
                    # Record trade
                    trade = {
                        'entry_date': entry_date,
                        'exit_date': date,
                        'symbol': primary_symbol,
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'position': position,
                        'pnl': sell_value - (position * entry_price) - commission_cost,
                        'exit_reason': 'signal'
                    }
                    trades.append(trade)
                
                # Open short position
                position = -capital / row['close']
                entry_price = row['close']
                entry_date = date
            
            # Calculate portfolio value
            if position > 0:
                port_value = capital + (position * row['close'])
            elif position < 0:
                port_value = capital + (position * row['close'])
            else:
                port_value = capital
                
            # Store portfolio value
            portfolio_values.append(port_value)
            dates.append(date)
            
        # Create equity curve
        equity_curve = pd.Series(portfolio_values, index=dates)
        
        # Calculate returns
        returns = equity_curve.pct_change().fillna(0)
        
        # Calculate basic metrics
        total_return = (equity_curve.iloc[-1] / initial_capital) - 1
        
        # Annualized return (assuming 252 trading days per year)
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        years = days / 365
        annualized_return = (1 + total_return) ** (1 / max(years, 1e-10)) - 1
        
        # Volatility
        volatility = returns.std() * np.sqrt(252)
        
        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # Max drawdown
        cumulative_returns = (1 + returns).cumprod()
        drawdowns = 1 - cumulative_returns / cumulative_returns.cummax()
        max_drawdown = drawdowns.max()
        
        # Create metrics dictionary
        metrics = {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'num_trades': len(trades)
        }
        
        # Create results dictionary
        results = {
            'equity_curve': equity_curve,
            'returns': returns,
            'trades': trades,
            'metrics': metrics
        }
        
        return results


def download_example_data() -> Dict[str, pd.DataFrame]:
    """
    Download example data for the walk-forward testing example.
    
    Returns:
    --------
    Dict[str, pd.DataFrame] with market data
    """
    # Define symbols to download
    symbols = ['SPY']
    
    # Download data
    market_data = {}
    
    for symbol in symbols:
        # Download data
        data = yf.download(symbol, start='2018-01-01', end='2023-01-01')
        
        # Rename columns to lowercase
        data.columns = [col.lower() for col in data.columns]
        
        # Store data
        market_data[symbol] = data
        
    return market_data


def example_parameter_optimization(market_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Example of parameter optimization for the SMA strategy.
    
    Parameters:
    -----------
    market_data : Dict[str, pd.DataFrame]
        Market data for each symbol
        
    Returns:
    --------
    Dict[str, Any] with optimized parameters
    """
    # Define parameter grid
    param_grid = {
        'fast_window': [5, 10, 15, 20, 25],
        'slow_window': [30, 40, 50, 60, 70],
        'stop_loss': [0.05, 0.1, 0.15]
    }
    
    # Run parameter optimization
    optimized_params = optimize_parameters(
        strategy_class=SimpleMovingAverageStrategy,
        market_data=market_data,
        param_grid=param_grid,
        metric='sharpe_ratio',
        initial_capital=10000,
        commission=0.001,
        slippage=0.001
    )
    
    return optimized_params


def example_walk_forward(market_data: Dict[str, pd.DataFrame],
                       default_params: Dict[str, Any],
                       use_optimization: bool = True) -> Dict[str, Any]:
    """
    Example of walk-forward testing.
    
    Parameters:
    -----------
    market_data : Dict[str, pd.DataFrame]
        Market data for each symbol
    default_params : Dict[str, Any]
        Default parameters for the strategy
    use_optimization : bool
        Whether to use parameter optimization
        
    Returns:
    --------
    Dict[str, Any] with walk-forward results
    """
    # Define optimization function if using optimization
    if use_optimization:
        def optimize_func(strategy_class, market_data, default_params, **kwargs):
            # Define parameter grid based on default parameters
            param_grid = {
                'fast_window': [max(5, default_params['fast_window'] - 5),
                               default_params['fast_window'],
                               min(30, default_params['fast_window'] + 5)],
                'slow_window': [max(20, default_params['slow_window'] - 10),
                               default_params['slow_window'],
                               min(100, default_params['slow_window'] + 10)],
                'stop_loss': [max(0.02, default_params['stop_loss'] - 0.02),
                             default_params['stop_loss'],
                             min(0.2, default_params['stop_loss'] + 0.02)]
            }
            
            # Run parameter optimization
            return optimize_parameters(
                strategy_class=strategy_class,
                market_data=market_data,
                param_grid=param_grid,
                metric='sharpe_ratio',
                **kwargs
            )
    else:
        optimize_func = None
    
    # Initialize walk-forward tester
    wf_test = WalkForwardTest(
        market_data=market_data,
        train_size=252,  # ~ 1 year of data
        test_size=63,    # ~ 3 months of data
        step_size=21,    # ~ 1 month steps
        optimization_func=optimize_func,
        window_type='sliding',
        purge_window=5,  # 5 days purge between train and test
        initial_capital=10000,
        commission=0.001,
        slippage=0.001
    )
    
    # Run walk-forward test
    results = wf_test.run(
        strategy_class=SimpleMovingAverageStrategy,
        default_params=default_params,
        show_progress=True
    )
    
    # Plot results
    print("\nPlotting results...")
    
    # Plot equity curves
    wf_test.plot_equity_curves()
    plt.savefig("equity_curves.png")
    plt.close()
    
    # Plot parameter stability
    wf_test.plot_parameter_stability()
    plt.savefig("parameter_stability.png")
    plt.close()
    
    # Plot performance by period
    wf_test.plot_performance_by_period(metric='sharpe_ratio')
    plt.savefig("sharpe_by_period.png")
    plt.close()
    
    # Plot train/test windows
    wf_test.plot_train_test_windows()
    plt.savefig("train_test_windows.png")
    plt.close()
    
    # Analyze parameter stability
    stability_metrics = wf_test.analyze_parameter_stability()
    print("\nParameter Stability Metrics:")
    for metric_name, metric_values in stability_metrics.items():
        print(f"\n{metric_name.title()}:")
        for param_name, value in metric_values.items():
            print(f"  {param_name}: {value:.4f}")
    
    # Compute robustness metrics
    robustness_metrics = wf_test.compute_robustness_metrics()
    print("\nRobustness Metrics:")
    for metric_name, value in robustness_metrics.items():
        print(f"  {metric_name.replace('_', ' ').title()}: {value:.4f}")
    
    # Save results
    wf_test.save_results("walk_forward_results.pkl")
    
    return results


def main():
    """
    Main function to run the walk-forward testing example.
    """
    print("Walk-Forward Testing Example")
    print("---------------------------")
    
    # Download example data
    print("\nDownloading example data...")
    market_data = download_example_data()
    
    # Run parameter optimization on full dataset
    print("\nRunning initial parameter optimization...")
    default_params = example_parameter_optimization(market_data)
    print(f"Optimized parameters: {default_params}")
    
    # If optimization fails, use default parameters
    if not default_params:
        default_params = {
            'fast_window': 20,
            'slow_window': 50,
            'stop_loss': 0.05
        }
        print(f"Using default parameters: {default_params}")
    
    # Run walk-forward test
    print("\nRunning walk-forward test...")
    results = example_walk_forward(market_data, default_params, use_optimization=True)
    
    # Print overall metrics
    print("\nOverall Performance Metrics:")
    for metric_name, value in results['overall_metrics'].items():
        print(f"  {metric_name.replace('_', ' ').title()}: {value:.4f}")
    
    print("\nWalk-Forward Testing Example completed. Results saved to disk.")


if __name__ == "__main__":
    main() 