# advanced_trading/run_full_backtest.py
#!/usr/bin/env python

"""
Full Backtest Runner
----------------
Comprehensive script to run backtests on multiple strategies with detailed analytics
and comparative analysis.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import matplotlib.pyplot as plt
import concurrent.futures
import itertools
import traceback

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import project modules
import config
from data.data_loader import DataLoader
from utils.performance import calculate_performance_metrics, create_tear_sheet
from utils.monte_carlo import run_monte_carlo_analysis
from utils.risk_stress_testing import perform_stress_testing
from utils.benchmark_analysis import compare_to_benchmarks
from utils.event_detection import MarketEventDetector
from utils.regime_detection import RegimeClassifier

# Import strategies
from strategies.funding_arbitrage import FundingRateArbitrage
from strategies.statistical_arbitrage import StatisticalArbitrageStrategy
from strategies.volume_profile_strategy import VolumeProfileStrategy
from strategies.lstm_strategy import LSTMStrategy
from strategies.ml_strategy import MLEnsembleStrategy

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'logs', f'full_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

# Strategy factory
STRATEGIES = {
    'funding_arbitrage': FundingRateArbitrage,
    'statistical_arbitrage': StatisticalArbitrageStrategy,
    'volume_profile': VolumeProfileStrategy,
    'lstm': LSTMStrategy,
    'ml_ensemble': MLEnsembleStrategy
}

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run comprehensive backtests')
    
    parser.add_argument('--strategies', type=str, nargs='+',
                      choices=list(STRATEGIES.keys()) + ['all'],
                      default=['volume_profile'],
                      help='Strategies to backtest (use "all" for all strategies)')
    
    parser.add_argument('--symbols', type=str, nargs='+',
                      default=['BTC/USDT'],
                      help='Symbols to backtest')
    
    parser.add_argument('--pairs', type=str, nargs='+',
                      help='Specific symbol pairs for paired strategies (format: Symbol1,Symbol2)')
    
    parser.add_argument('--start_date', type=str, default='2020-01-01',
                      help='Start date for backtesting (YYYY-MM-DD)')
    
    parser.add_argument('--end_date', type=str, default='2023-01-01',
                      help='End date for backtesting (YYYY-MM-DD)')
    
    parser.add_argument('--capital', type=float, default=10000.0,
                      help='Initial capital')
    
    parser.add_argument('--timeframe', type=str, default='1d',
                      help='Data timeframe (e.g., 1h, 4h, 1d)')
    
    parser.add_argument('--test_periods', type=int, default=1,
                      help='Number of test periods to evaluate (uses walk-forward)')

    parser.add_argument('--monte_carlo', action='store_true',
                      help='Run Monte Carlo simulations')
    
    parser.add_argument('--stress_test', action='store_true',
                      help='Run stress tests')
    
    parser.add_argument('--compare_benchmarks', action='store_true',
                      help='Compare to benchmarks')
    
    parser.add_argument('--detect_regimes', action='store_true',
                      help='Detect market regimes')
    
    parser.add_argument('--detect_events', action='store_true',
                      help='Detect market events')
    
    parser.add_argument('--parallel', action='store_true',
                      help='Run backtests in parallel')
    
    parser.add_argument('--max_workers', type=int, default=4,
                      help='Maximum number of parallel workers')
    
    parser.add_argument('--output_dir', type=str, default=None,
                      help='Directory to save results')
    
    return parser.parse_args()

def load_data(symbols, timeframe, start_date, end_date):
    """Load data for all symbols."""
    logger.info(f"Loading data for {len(symbols)} symbols from {start_date} to {end_date}")
    
    data_loader = DataLoader()
    data = {}
    
    for symbol in symbols:
        try:
            symbol_data = data_loader.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if symbol_data is not None and not symbol_data.empty:
                data[symbol] = symbol_data
                logger.info(f"Loaded {len(symbol_data)} data points for {symbol}")
            else:
                logger.warning(f"No data loaded for {symbol}")
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
    
    return data

def parse_pairs(pairs_arg):
    """Parse pairs argument into list of symbol pairs."""
    parsed_pairs = []
    
    if pairs_arg:
        for pair_str in pairs_arg:
            # Handle format like "BTC/USDT,ETH/USDT"
            symbols = pair_str.split(',')
            if len(symbols) == 2:
                parsed_pairs.append((symbols[0].strip(), symbols[1].strip()))
    
    return parsed_pairs

def create_strategy(strategy_name, symbols, pairs=None, timeframe='1d'):
    """Create strategy instance based on strategy name."""
    if strategy_name not in STRATEGIES:
        logger.error(f"Unknown strategy: {strategy_name}")
        return None
    
    strategy_class = STRATEGIES[strategy_name]
    
    try:
        if strategy_name == 'funding_arbitrage':
            return strategy_class(symbols=symbols, min_funding_rate=0.01, max_position_size=0.2)
        
        elif strategy_name == 'statistical_arbitrage':
            # Use provided pairs or default to first two symbols
            if not pairs and len(symbols) >= 2:
                pairs = [(symbols[0], symbols[1])]
            
            if not pairs:
                logger.error("Statistical arbitrage requires at least one pair")
                return None
            
            return strategy_class(pairs=pairs, lookback_period=20, z_threshold=2.0)
        
        elif strategy_name == 'volume_profile':
            # Volume profile works on a single symbol
            symbol = symbols[0] if symbols else 'BTC/USDT'
            return strategy_class(symbol=symbol, lookback_period=60, num_bins=50)
        
        elif strategy_name == 'lstm':
            # LSTM works on a single symbol
            symbol = symbols[0] if symbols else 'BTC/USDT'
            return strategy_class(symbol=symbol, sequence_length=60, prediction_horizon=5)
        
        elif strategy_name == 'ml_ensemble':
            # Build configuration for ML ensemble
            return strategy_class(
                config={
                    'symbols': symbols,
                    'lookback_window': 30,
                    'prediction_horizon': 5,
                    'training_window': 252,
                    'threshold_buy': 0.65,
                    'threshold_sell': 0.65
                }
            )
        
        else:
            return strategy_class()
    
    except Exception as e:
        logger.error(f"Error creating strategy {strategy_name}: {e}")
        return None

def run_single_backtest(strategy_name, symbols, pairs, data, args):
    """Run backtest for a single strategy."""
    logger.info(f"Running backtest for {strategy_name} strategy")
    
    # Create strategy instance
    strategy = create_strategy(strategy_name, symbols, pairs, args.timeframe)
    
    if strategy is None:
        logger.error(f"Failed to create {strategy_name} strategy")
        return None
    
    try:
        # Strategy-specific preprocessing
        if strategy_name == 'lstm':
            # LSTM needs training first
            symbol = symbols[0]
            train_size = int(len(data[symbol]) * 0.7)
            train_data = {symbol: data[symbol].iloc[:train_size]}
            
            logger.info(f"Training LSTM model on {train_size} data points")
            strategy.train(train_data[symbol])
        
        elif strategy_name == 'ml_ensemble':
            # ML Ensemble needs training
            train_size = int(len(next(iter(data.values()))) * 0.7)
            train_data = {}
            
            for symbol, symbol_data in data.items():
                train_data[symbol] = symbol_data.iloc[:train_size]
            
            logger.info(f"Training ML Ensemble model")
            strategy.train_models(train_data)
        
        elif strategy_name == 'funding_arbitrage':
            # Generate simulated funding rate data
            funding_data = {}
            
            for symbol in symbols:
                # Create synthetic funding rates for testing
                funding_rates = pd.DataFrame(index=data[symbol].index)
                for exchange in ['binance', 'ftx', 'bybit']:
                    # Random funding rates with some bias
                    rates = np.random.normal(0.0001, 0.0005, size=len(funding_rates))
                    funding_rates[exchange] = rates
                
                funding_data[symbol] = funding_rates
            
            # Run backtest with funding data
            results = strategy.backtest(
                price_data=data,
                funding_data=funding_data,
                initial_capital=args.capital
            )
            
            return results
        
        # Run backtest
        if strategy_name != 'funding_arbitrage':  # Already handled above
            if hasattr(strategy, 'backtest'):
                if strategy_name in ['volume_profile', 'lstm']:
                    # Single symbol strategies
                    symbol = symbols[0]
                    results = strategy.backtest(data[symbol], initial_capital=args.capital)
                else:
                    # Multi-symbol strategies
                    results = strategy.backtest(data, initial_capital=args.capital)
            else:
                logger.error(f"Strategy {strategy_name} does not have a backtest method")
                return None
        
        logger.info(f"Backtest completed for {strategy_name}")
        return results
    
    except Exception as e:
        logger.error(f"Error in backtest for {strategy_name}: {e}")
        traceback.print_exc()
        return None

def analyze_results(results, strategy_name, output_dir):
    """Analyze backtest results and generate reports."""
    if results is None:
        logger.error(f"No results to analyze for {strategy_name}")
        return None
    
    try:
        # Create results DataFrame for analysis
        if 'portfolio_value' in results:
            portfolio_values = results['portfolio_value']
            if isinstance(portfolio_values, list):
                dates = results.get('dates', range(len(portfolio_values)))
                portfolio_df = pd.DataFrame({
                    'portfolio_value': portfolio_values
                }, index=dates)
            else:
                portfolio_df = pd.DataFrame(portfolio_values)
            
            # Calculate returns if not present
            if 'returns' not in portfolio_df.columns:
                portfolio_df['returns'] = portfolio_df['portfolio_value'].pct_change()
        else:
            # Try to extract from nested structure
            for key, value in results.items():
                if isinstance(value, dict) and 'portfolio_value' in value:
                    portfolio_df = pd.DataFrame({
                        'portfolio_value': value['portfolio_value']
                    }, index=value.get('dates', range(len(value['portfolio_value']))))
                    portfolio_df['returns'] = portfolio_df['portfolio_value'].pct_change()
                    break
            else:
                logger.error(f"Could not find portfolio values in results for {strategy_name}")
                return None
        
        # Calculate performance metrics
        metrics = calculate_performance_metrics(portfolio_df)
        
        # Create output directory for this strategy
        strategy_dir = output_dir / strategy_name
        os.makedirs(strategy_dir, exist_ok=True)
        
        # Save portfolio values and metrics
        portfolio_df.to_csv(strategy_dir / 'portfolio_values.csv')
        
        with open(strategy_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=4)
        
        # Save trades if available
        if 'trades' in results:
            trades_df = pd.DataFrame(results['trades'])
            trades_df.to_csv(strategy_dir / 'trades.csv', index=False)
        
        # Create performance visualization
        create_tear_sheet(portfolio_df, save_path=str(strategy_dir / 'performance_tearsheet.png'))
        
        logger.info(f"Analysis completed for {strategy_name}")
        logger.info(f"Total Return: {metrics['total_return']:.2f}%")
        logger.info(f"Annual Return: {metrics['annual_return']:.2f}%")
        logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
        
        return metrics
    
    except Exception as e:
        logger.error(f"Error analyzing results for {strategy_name}: {e}")
        traceback.print_exc()
        return None

def run_monte_carlo_simulation(results, strategy_name, output_dir):
    """Run Monte Carlo simulation on strategy results."""
    if results is None:
        logger.error(f"No results for Monte Carlo simulation for {strategy_name}")
        return None
    
    logger.info(f"Running Monte Carlo simulation for {strategy_name}")
    
    try:
        # Extract returns series
        if 'returns' in results:
            returns = results['returns']
        elif isinstance(results, dict) and 'portfolio_value' in results:
            # Calculate returns from portfolio value
            portfolio_values = results['portfolio_value']
            returns = [0] + [(portfolio_values[i] / portfolio_values[i-1] - 1) 
                           for i in range(1, len(portfolio_values))]
        else:
            # Try to find returns in nested structure
            for key, value in results.items():
                if isinstance(value, dict) and 'returns' in value:
                    returns = value['returns']
                    break
            else:
                logger.error(f"Could not find returns data for Monte Carlo simulation for {strategy_name}")
                return None
        
        # Convert to pandas Series if needed
        if not isinstance(returns, pd.Series):
            returns = pd.Series(returns)
        
        # Create Monte Carlo simulation directory
        mc_dir = output_dir / strategy_name / 'monte_carlo'
        os.makedirs(mc_dir, exist_ok=True)
        
        # Run simulation
        mc_results = run_monte_carlo_analysis(
            strategy=strategy_name,
            returns=returns,
            num_simulations=1000,
            output_dir=mc_dir
        )
        
        # Save results
        with open(mc_dir / 'monte_carlo_results.json', 'w') as f:
            json.dump(mc_results, f, indent=4, default=str)
        
        logger.info(f"Monte Carlo simulation completed for {strategy_name}")
        return mc_results
    
    except Exception as e:
        logger.error(f"Error in Monte Carlo simulation for {strategy_name}: {e}")
        traceback.print_exc()
        return None

def run_stress_tests(strategy, data, strategy_name, output_dir):
    """Run stress tests on the strategy."""
    if strategy is None:
        logger.error(f"No strategy for stress testing {strategy_name}")
        return None
    
    logger.info(f"Running stress tests for {strategy_name}")
    
    try:
        # Create stress test directory
        stress_dir = output_dir / strategy_name / 'stress_tests'
        os.makedirs(stress_dir, exist_ok=True)
        
        # Run stress tests
        stress_results = perform_stress_testing(
            strategy=strategy,
            data_dict=data
        )
        
        # Save results
        with open(stress_dir / 'stress_test_results.json', 'w') as f:
            json.dump(stress_results, f, indent=4, default=str)
        
        # Create visualization showing performance in each scenario
        visualize_stress_tests(stress_results, stress_dir)
        
        logger.info(f"Stress tests completed for {strategy_name}")
        return stress_results
    
    except Exception as e:
        logger.error(f"Error in stress tests for {strategy_name}: {e}")
        traceback.print_exc()
        return None

def visualize_stress_tests(stress_results, output_dir):
    """Create visualization of stress test results."""
    # Extract scenario names and returns
    scenarios = []
    returns = []
    
    for scenario_name, result in stress_results.items():
        if 'performance' in result and 'total_return' in result['performance']:
            scenarios.append(scenario_name)
            returns.append(result['performance']['total_return'])
    
    if not scenarios:
        logger.warning("No valid stress test results to visualize")
        return
    
    # Create bar chart
    plt.figure(figsize=(10, 6))
    colors = ['green' if r >= 0 else 'red' for r in returns]
    plt.bar(scenarios, returns, color=colors)
    plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    plt.title('Strategy Performance in Stress Scenarios')
    plt.xlabel('Scenario')
    plt.ylabel('Total Return (%)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_dir / 'stress_test_results.png', dpi=300)
    plt.close()

def run_benchmark_comparison(results, data, strategy_name, output_dir):
    """Compare strategy to benchmark assets."""
    if results is None:
        logger.error(f"No results for benchmark comparison for {strategy_name}")
        return None
    
    logger.info(f"Running benchmark comparison for {strategy_name}")
    
    try:
        # Extract portfolio values
        if 'portfolio_value' in results:
            portfolio_values = results['portfolio_value']
            if isinstance(portfolio_values, list):
                dates = results.get('dates', range(len(portfolio_values)))
                portfolio_df = pd.DataFrame({
                    'portfolio_value': portfolio_values
                }, index=dates)
            else:
                portfolio_df = pd.DataFrame(portfolio_values)
        else:
            # Try to find portfolio values in nested structure
            for key, value in results.items():
                if isinstance(value, dict) and 'portfolio_value' in value:
                    portfolio_df = pd.DataFrame({
                        'portfolio_value': value['portfolio_value']
                    }, index=value.get('dates', range(len(value['portfolio_value']))))
                    break
            else:
                logger.error(f"Could not find portfolio values for benchmark comparison for {strategy_name}")
                return None
        
        # Create benchmarks directory
        benchmark_dir = output_dir / strategy_name / 'benchmarks'
        os.makedirs(benchmark_dir, exist_ok=True)
        
        # Use market data as benchmarks
        benchmarks = {}
        for symbol, symbol_data in data.items():
            # Convert to format expected by compare_to_benchmarks
            bench_df = pd.DataFrame({
                'close': symbol_data['close']
            })
            benchmarks[symbol] = bench_df
        
        # Run comparison
        comparison_results = compare_to_benchmarks(
            strategy_data=portfolio_df,
            benchmarks=benchmarks
        )
        
        # Save results
        with open(benchmark_dir / 'benchmark_results.json', 'w') as f:
            json.dump(comparison_results, f, indent=4, default=str)
        
        # Create visualization
        visualize_benchmark_comparison(comparison_results, benchmark_dir)
        
        logger.info(f"Benchmark comparison completed for {strategy_name}")
        return comparison_results
    
    except Exception as e:
        logger.error(f"Error in benchmark comparison for {strategy_name}: {e}")
        traceback.print_exc()
        return None

def visualize_benchmark_comparison(comparison_results, output_dir):
    """Create visualization of benchmark comparison."""
    # Extract cumulative returns for strategy and benchmarks
    plt.figure(figsize=(12, 6))
    
    # Plot each benchmark
    for benchmark, result in comparison_results.items():
        if 'strategy_cum_returns' in result and 'benchmark_cum_returns' in result:
            # Convert from json strings if needed
            if isinstance(result['benchmark_cum_returns'], str):
                benchmark_returns = pd.read_json(result['benchmark_cum_returns'])
                strategy_returns = pd.read_json(result['strategy_cum_returns'])
            else:
                benchmark_returns = result['benchmark_cum_returns']
                strategy_returns = result['strategy_cum_returns']
            
            # Plot cumulative returns
            plt.plot(benchmark_returns.index, benchmark_returns * 100, 
                   label=f'Benchmark: {benchmark}')
    
    # Plot strategy returns
    if 'strategy_cum_returns' in comparison_results[next(iter(comparison_results))]:
        strategy_returns = comparison_results[next(iter(comparison_results))]['strategy_cum_returns']
        if isinstance(strategy_returns, str):
            strategy_returns = pd.read_json(strategy_returns)
        
        plt.plot(strategy_returns.index, strategy_returns * 100, 
               label='Strategy', linewidth=2, color='black')
    
    plt.title('Strategy vs. Benchmark Performance')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return (%)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_dir / 'benchmark_comparison.png', dpi=300)
    plt.close()

def detect_market_regimes(data, output_dir):
    """Detect market regimes using multiple methods."""
    logger.info("Detecting market regimes")
    
    try:
        # Create regimes directory
        regimes_dir = output_dir / 'market_regimes'
        os.makedirs(regimes_dir, exist_ok=True)
        
        # Use first symbol for regime detection
        symbol = next(iter(data.keys()))
        price_data = data[symbol]
        
        # Initialize regime classifier
        classifier = RegimeClassifier(method='hmm', n_regimes=3)
        
        # Fit model
        classifier.fit(price_data)
        
        # Predict regimes
        regimes = classifier.predict(price_data)
        
        # Save regime predictions
        regimes_df = pd.DataFrame({
            'regime': regimes,
            'close': price_data['close']
        })
        regimes_df.to_csv(regimes_dir / f'regimes_{symbol.replace("/", "_")}.csv')
        
        # Analyze regimes
        regime_stats = classifier.analyze_regimes(price_data, regimes)
        
        # Save regime statistics
        with open(regimes_dir / f'regime_stats_{symbol.replace("/", "_")}.json', 'w') as f:
            json.dump(regime_stats, f, indent=4, default=str)
        
        # Create visualization
        fig = classifier.plot_regimes(price_data, regimes)
        fig.savefig(regimes_dir / f'regimes_{symbol.replace("/", "_")}.png', dpi=300)
        plt.close(fig)
        
        # Create returns distribution by regime
        fig = classifier.plot_regime_distributions(price_data, regimes)
        fig.savefig(regimes_dir / f'regime_distributions_{symbol.replace("/", "_")}.png', dpi=300)
        plt.close(fig)
        
        logger.info(f"Market regime detection completed for {symbol}")
        return regimes
    
    except Exception as e:
        logger.error(f"Error detecting market regimes: {e}")
        traceback.print_exc()
        return None

def detect_market_events(data, start_date, end_date, output_dir):
    """Detect significant market events."""
    logger.info("Detecting market events")
    
    try:
        # Create events directory
        events_dir = output_dir / 'market_events'
        os.makedirs(events_dir, exist_ok=True)
        
        # Initialize event detector
        detector = MarketEventDetector()
        
        # Process each symbol
        all_events = []
        
        for symbol, price_data in data.items():
            symbol_base = symbol.split('/')[0]
            
            # Detect events
            events = detector.detect_events(
                market_data=price_data,
                start_date=start_date,
                end_date=end_date,
                symbols=[symbol_base]
            )
            
            # Add to combined list
            for event in events:
                event['symbol'] = symbol
                all_events.append(event)
        
        # Convert event dates to strings for json serialization
        for event in all_events:
            if 'date' in event and isinstance(event['date'], (datetime, pd.Timestamp)):
                event['date'] = event['date'].strftime('%Y-%m-%d')
        
        # Save events
        with open(events_dir / 'market_events.json', 'w') as f:
            json.dump(all_events, f, indent=4)
        
        # Create visualization of price with events
        for symbol, price_data in data.items():
            visualize_events_on_price(price_data, all_events, symbol, events_dir)
        
        logger.info(f"Detected {len(all_events)} market events")
        return all_events
    
    except Exception as e:
        logger.error(f"Error detecting market events: {e}")
        traceback.print_exc()
        return None

def visualize_events_on_price(price_data, events, symbol, output_dir):
    """Visualize market events on price chart."""
    # Filter events for this symbol
    symbol_events = [e for e in events if e.get('symbol') == symbol]
    
    if not symbol_events:
        return
    
    # Create visualization
    plt.figure(figsize=(12, 6))
    
    # Plot price
    plt.plot(price_data.index, price_data['close'], color='black')
    
    # Plot events
    for event in symbol_events:
        # Convert date string back to datetime if needed
        if isinstance(event['date'], str):
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
        else:
            event_date = event['date']
        
        # Find closest index in price data
        closest_idx = price_data.index[price_data.index.get_indexer([event_date], method='nearest')[0]]
        
        # Get price at event
        event_price = price_data.loc[closest_idx, 'close']
        
        # Determine color based on sentiment
        color = 'green' if event.get('sentiment', 0) > 0 else 'red'
        
        # Plot marker
        plt.scatter(closest_idx, event_price, color=color, zorder=5, s=100)
        
        # Add text annotation
        plt.annotate(
            event.get('type', 'Event'),
            xy=(closest_idx, event_price),
            xytext=(0, 20),
            textcoords='offset points',
            ha='center',
            va='bottom',
            rotation=45,
            bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0')
        )
    
    plt.title(f'Market Events for {symbol}')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_dir / f'events_{symbol.replace("/", "_")}.png', dpi=300)
    plt.close()

def compare_strategies(all_results, output_dir):
    """Compare performance of all strategies."""
    logger.info("Comparing strategy performance")
    
    if not all_results:
        logger.warning("No results to compare")
        return
    
    try:
        # Extract metrics for all strategies
        strategies = []
        total_returns = []
        annual_returns = []
        sharpe_ratios = []
        max_drawdowns = []
        
        for strategy_name, metrics in all_results.items():
            if metrics:
                strategies.append(strategy_name)
                total_returns.append(metrics.get('total_return', 0))
                annual_returns.append(metrics.get('annual_return', 0))
                sharpe_ratios.append(metrics.get('sharpe_ratio', 0))
                max_drawdowns.append(metrics.get('max_drawdown', 0))
        
        if not strategies:
            logger.warning("No valid results to compare")
            return
        
        # Create comparison table
        comparison_df = pd.DataFrame({
            'Strategy': strategies,
            'Total Return (%)': total_returns,
            'Annual Return (%)': annual_returns,
            'Sharpe Ratio': sharpe_ratios,
            'Max Drawdown (%)': max_drawdowns
        })
        
        # Save comparison table
        comparison_df.to_csv(output_dir / 'strategy_comparison.csv', index=False)
        
        # Create visualizations
        # 1. Total Returns
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 2, 1)
        colors = ['green' if r >= 0 else 'red' for r in total_returns]
        plt.bar(strategies, total_returns, color=colors)
        plt.title('Total Returns (%)')
        plt.ylabel('Return (%)')
        plt.xticks(rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        
        # 2. Annual Returns
        plt.subplot(2, 2, 2)
        colors = ['green' if r >= 0 else 'red' for r in annual_returns]
        plt.bar(strategies, annual_returns, color=colors)
        plt.title('Annual Returns (%)')
        plt.ylabel('Return (%)')
        plt.xticks(rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        
        # 3. Sharpe Ratios
        plt.subplot(2, 2, 3)
        colors = ['green' if r >= 1 else ('yellow' if r >= 0 else 'red') for r in sharpe_ratios]
        plt.bar(strategies, sharpe_ratios, color=colors)
        plt.title('Sharpe Ratios')
        plt.ylabel('Ratio')
        plt.xticks(rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        
        # 4. Max Drawdowns
        plt.subplot(2, 2, 4)
        colors = ['red' for _ in max_drawdowns]
        plt.bar(strategies, max_drawdowns, color=colors)
        plt.title('Maximum Drawdowns (%)')
        plt.ylabel('Drawdown (%)')
        plt.xticks(rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_dir / 'strategy_comparison.png', dpi=300)
        plt.close()
        
        logger.info("Strategy comparison completed")
    
    except Exception as e:
        logger.error(f"Error comparing strategies: {e}")
        traceback.print_exc()

def main():
    """Main entry point for the script."""
    # Parse arguments
    args = parse_args()
    
    # Set up output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(script_dir) / 'results' / f'full_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Determine strategies to test
    strategies_to_test = args.strategies
    if 'all' in strategies_to_test:
        strategies_to_test = list(STRATEGIES.keys())
    
    logger.info(f"Testing strategies: {', '.join(strategies_to_test)}")
    
    # Parse pairs if provided
    pairs = parse_pairs(args.pairs)
    
    # Load market data
    data = load_data(args.symbols, args.timeframe, args.start_date, args.end_date)
    
    if not data:
        logger.error("No market data loaded. Exiting.")
        return 1
    
    # Save configuration
    config_dict = vars(args)
    config_dict['symbols'] = args.symbols
    config_dict['strategies'] = strategies_to_test
    
    with open(output_dir / 'backtest_config.json', 'w') as f:
        json.dump(config_dict, f, indent=4)
    
    # Detect market regimes if requested
    if args.detect_regimes:
        detect_market_regimes(data, output_dir)
    
    # Detect market events if requested
    if args.detect_events:
        detect_market_events(data, args.start_date, args.end_date, output_dir)
    
    # Run backtests
    backtest_results = {}
    strategy_instances = {}
    analysis_results = {}
    
    if args.parallel and len(strategies_to_test) > 1:
        # Run backtests in parallel
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {}
            
            for strategy_name in strategies_to_test:
                future = executor.submit(
                    run_single_backtest,
                    strategy_name,
                    args.symbols,
                    pairs,
                    data,
                    args
                )
                futures[future] = strategy_name
            
            for future in concurrent.futures.as_completed(futures):
                strategy_name = futures[future]
                try:
                    result = future.result()
                    backtest_results[strategy_name] = result
                    logger.info(f"Completed backtest for {strategy_name}")
                except Exception as e:
                    logger.error(f"Error in backtest for {strategy_name}: {e}")
                    traceback.print_exc()
    else:
        # Run backtests sequentially
        for strategy_name in strategies_to_test:
            # Create strategy instance
            strategy = create_strategy(strategy_name, args.symbols, pairs, args.timeframe)
            strategy_instances[strategy_name] = strategy
            
            # Run backtest
            result = run_single_backtest(strategy_name, args.symbols, pairs, data, args)
            backtest_results[strategy_name] = result
    
    # Analyze results
    for strategy_name, result in backtest_results.items():
        if result:
            metrics = analyze_results(result, strategy_name, output_dir)
            analysis_results[strategy_name] = metrics
    
    # Run additional analysis if requested
    for strategy_name, result in backtest_results.items():
        if not result:
            continue
        
        if args.monte_carlo:
            run_monte_carlo_simulation(result, strategy_name, output_dir)
        
        if args.stress_test:
            # Get or create strategy instance
            strategy = strategy_instances.get(strategy_name)
            if strategy is None:
                strategy = create_strategy(strategy_name, args.symbols, pairs, args.timeframe)
            
            if strategy:
                run_stress_tests(strategy, data, strategy_name, output_dir)
        
        if args.compare_benchmarks:
            run_benchmark_comparison(result, data, strategy_name, output_dir)
    
    # Compare strategies
    compare_strategies(analysis_results, output_dir)
    
    logger.info(f"Full backtest completed. Results saved to {output_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(main())