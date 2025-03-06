#!/usr/bin/env python

"""
Strategy Runner
-------------
Unified script to run trading strategies with comprehensive testing and deployment support.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
import time
import importlib
import subprocess

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

# Import project modules
from data.data_loader import DataLoader
from utils.monte_carlo import run_monte_carlo_analysis
from utils.risk_stress_testing import perform_stress_testing, default_stress_scenarios
from utils.benchmark_analysis import compare_to_benchmarks
from utils.event_detection import MarketEventDetector
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'logs', f'strategy_runner_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

# Strategy mapping
STRATEGY_CLASSES = {
    'funding_arbitrage': 'strategies.funding_arbitrage.FundingRateArbitrage',
    'statistical_arbitrage': 'strategies.statistical_arbitrage.StatisticalArbitrageStrategy',
    'volume_profile': 'strategies.volume_profile_strategy.VolumeProfileStrategy',
    'lstm': 'strategies.lstm_strategy.LSTMStrategy',
    'ml_ensemble': 'strategies.ml_strategy.MLEnsembleStrategy'
}

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Instinct AI Strategy Runner')
    
    # Strategy selection
    parser.add_argument('--strategy', type=str, required=True,
                      choices=list(STRATEGY_CLASSES.keys()) + ['all'],
                      help='Strategy to run or "all" for all strategies')
    
    # Data parameters
    parser.add_argument('--symbols', type=str, nargs='+',
                      default=config.TRADING_CONFIG['symbols'],
                      help='Symbols to use (e.g., BTC/USDT ETH/USDT)')
    
    parser.add_argument('--start_date', type=str, default=config.BACKTEST_CONFIG['start_date'],
                      help='Start date for backtesting (YYYY-MM-DD)')
    
    parser.add_argument('--end_date', type=str, default=config.BACKTEST_CONFIG['end_date'],
                      help='End date for backtesting (YYYY-MM-DD)')
    
    parser.add_argument('--timeframe', type=str, default=config.BACKTEST_CONFIG['data_frequency'],
                      help='Data timeframe (e.g., 1h, 1d)')
    
    # Capital allocation
    parser.add_argument('--capital', type=float, default=config.TRADING_CONFIG['initial_capital'],
                      help='Initial capital')
    
    # Testing options
    parser.add_argument('--backtest', action='store_true', default=True,
                      help='Run backtest')
    
    parser.add_argument('--optimize', action='store_true',
                      help='Run parameter optimization')
    
    parser.add_argument('--monte_carlo', action='store_true',
                      help='Run Monte Carlo simulation')
    
    parser.add_argument('--stress_test', action='store_true',
                      help='Run stress tests')
    
    parser.add_argument('--event_analysis', action='store_true',
                      help='Run market event analysis')
    
    parser.add_argument('--benchmark', action='store_true',
                      help='Compare to benchmarks')
    
    # Parallel processing
    parser.add_argument('--parallel', action='store_true', default=config.BACKTEST_CONFIG['parallel'],
                      help='Use parallel processing')
    
    parser.add_argument('--workers', type=int, default=config.BACKTEST_CONFIG['num_workers'],
                      help='Number of worker processes for parallel processing')
    
    # Output options
    parser.add_argument('--output_dir', type=str, default=None,
                      help='Directory to save results (default: auto-generated)')
    
    parser.add_argument('--save_model', action='store_true',
                      help='Save trained model')
    
    parser.add_argument('--load_model', action='store_true',
                      help='Load existing model instead of training')
    
    # Live trading options
    parser.add_argument('--paper_trading', action='store_true',
                      help='Run in paper trading mode')
    
    parser.add_argument('--live_trading', action='store_true',
                      help='Run in live trading mode (use with caution)')
    
    parser.add_argument('--dashboard', action='store_true',
                      help='Launch monitoring dashboard')
    
    return parser.parse_args()

def load_data(symbols, timeframe, start_date, end_date):
    """Load market data for backtest."""
    logger.info(f"Loading data for {len(symbols)} symbols from {start_date} to {end_date}")
    
    data_loader = DataLoader()
    data = {}
    
    for symbol in symbols:
        try:
            # Load data
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
    
    if not data:
        logger.error("No market data loaded. Exiting.")
        return None
    
    return data

def import_strategy_class(strategy_name):
    """Dynamically import strategy class."""
    if strategy_name not in STRATEGY_CLASSES:
        logger.error(f"Strategy {strategy_name} not found in available strategies")
        return None
    
    class_path = STRATEGY_CLASSES[strategy_name]
    module_path, class_name = class_path.rsplit('.', 1)
    
    try:
        module = importlib.import_module(module_path)
        strategy_class = getattr(module, class_name)
        logger.info(f"Imported strategy: {class_name} from {module_path}")
        return strategy_class
    except (ImportError, AttributeError) as e:
        logger.error(f"Error importing strategy {strategy_name}: {e}")
        return None

def create_output_dir(strategy_name, output_dir=None):
    """Create output directory for results."""
    if output_dir:
        directory = Path(output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = script_dir / 'results' / f"{strategy_name}_{timestamp}"
    
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Created output directory: {directory}")
    
    return directory

def save_config(args, output_dir):
    """Save configuration to output directory."""
    config_path = output_dir / 'run_config.json'
    
    # Convert args to dictionary
    config_dict = vars(args)
    
    # Convert non-serializable objects to strings
    for key, value in config_dict.items():
        if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
            config_dict[key] = str(value)
    
    with open(config_path, 'w') as f:
        json.dump(config_dict, f, indent=4)
    
    logger.info(f"Saved configuration to {config_path}")

def run_backtest(strategy_class, data, args, output_dir):
    """Run backtest with the specified strategy."""
    logger.info(f"Running backtest with {strategy_class.__name__}")
    
    try:
        # Initialize strategy
        strategy_params = {}
        
        # Different initialization based on strategy type
        if strategy_class.__name__ == 'LSTMStrategy':
            # LSTM requires a specific symbol
            symbol = args.symbols[0] if args.symbols else 'BTC/USDT'
            strategy = strategy_class(
                symbol=symbol,
                sequence_length=60,
                prediction_horizon=5,
                threshold_pct=1.0
            )
        elif strategy_class.__name__ == 'FundingRateArbitrage':
            # Funding arbitrage uses all symbols
            strategy = strategy_class(
                symbols=args.symbols,
                min_funding_rate=0.01,
                max_position_size=0.2
            )
        elif strategy_class.__name__ == 'StatisticalArbitrageStrategy':
            # Statistical arbitrage needs symbol pairs
            strategy = strategy_class(
                symbols=args.symbols,
                lookback_period=20,
                z_threshold=2.0
            )
        else:
            # Default initialization
            strategy = strategy_class(**strategy_params)
        
        # Train strategy (if applicable)
        if hasattr(strategy, 'train') and not args.load_model:
            # For strategies that need training
            logger.info("Training strategy")
            
            # Split data for training
            train_split = 0.7  # Default 70% training
            
            # Find first symbol's data for splitting
            symbol = args.symbols[0] if args.symbols else list(data.keys())[0]
            data_length = len(data[symbol])
            train_size = int(data_length * train_split)
            
            train_data = {}
            for sym, sym_data in data.items():
                train_data[sym] = sym_data.iloc[:train_size]
            
            # Train the strategy
            strategy.train(train_data)
            
            if args.save_model and hasattr(strategy, 'save'):
                model_dir = output_dir / 'model'
                os.makedirs(model_dir, exist_ok=True)
                strategy.save(model_dir)
                logger.info(f"Saved model to {model_dir}")
        
        elif args.load_model and hasattr(strategy, 'load'):
            # Load existing model
            model_dir = script_dir / 'models' / args.strategy
            if model_dir.exists():
                strategy.load(model_dir)
                logger.info(f"Loaded model from {model_dir}")
            else:
                logger.warning(f"Model directory not found: {model_dir}")
        
        # Run backtest
        logger.info("Running backtest")
        results = strategy.backtest(data, initial_capital=args.capital)
        
        # Save results
        results_path = output_dir / 'backtest_results.json'
        with open(results_path, 'w') as f:
            # Convert pandas objects and numpy arrays to JSON serializable format
            json_results = {}
            
            for key, value in results.items():
                if isinstance(value, pd.DataFrame):
                    json_results[key] = value.to_json(orient='split')
                elif isinstance(value, np.ndarray):
                    json_results[key] = value.tolist()
                elif isinstance(value, (int, float, str, bool, list, dict)):
                    json_results[key] = value
                else:
                    json_results[key] = str(value)
            
            json.dump(json_results, f, indent=4)
        
        logger.info(f"Saved backtest results to {results_path}")
        
        # Generate performance visualizations
        if 'equity_curve' in results:
            try:
                import matplotlib.pyplot as plt
                
                # Plot equity curve
                plt.figure(figsize=(12, 6))
                plt.plot(results['equity_curve'])
                plt.title(f"{strategy_class.__name__} - Equity Curve")
                plt.xlabel('Date')
                plt.ylabel('Portfolio Value')
                plt.grid(True)
                plt.savefig(output_dir / 'equity_curve.png')
                plt.close()
                
                logger.info(f"Saved equity curve visualization to {output_dir}")
            except Exception as e:
                logger.warning(f"Error generating visualizations: {e}")
        
        return results
    
    except Exception as e:
        logger.error(f"Error in backtest: {e}", exc_info=True)
        return None

def run_parameter_optimization(strategy_class, data, args, output_dir):
    """Run parameter optimization for the strategy."""
    logger.info(f"Running parameter optimization for {strategy_class.__name__}")
    
    try:
        # Import optimization module
        sys.path.append(str(script_dir))
        from utils.optimization import perform_walk_forward_optimization
        
        # Set up parameter grid based on strategy type
        param_grid = {}
        
        if strategy_class.__name__ == 'LSTMStrategy':
            param_grid = {
                'sequence_length': [20, 40, 60],
                'prediction_horizon': [1, 3, 5],
                'threshold_pct': [0.5, 1.0, 1.5]
            }
        elif strategy_class.__name__ == 'FundingRateArbitrage':
            param_grid = {
                'min_funding_rate': [0.005, 0.01, 0.02],
                'max_position_size': [0.1, 0.2, 0.3]
            }
        elif strategy_class.__name__ == 'StatisticalArbitrageStrategy':
            param_grid = {
                'lookback_period': [10, 20, 30],
                'z_threshold': [1.5, 2.0, 2.5]
            }
        else:
            logger.warning(f"No default parameter grid defined for {strategy_class.__name__}")
            param_grid = {
                'param1': [1, 2, 3],
                'param2': [0.1, 0.2, 0.3]
            }
        
        # Define evaluation function
        def evaluate_performance(results):
            if isinstance(results, dict) and 'performance_metrics' in results:
                metrics = results['performance_metrics']
                # Combine Sharpe ratio and total return
                if 'sharpe_ratio' in metrics and 'total_return' in metrics:
                    return 0.7 * metrics['sharpe_ratio'] + 0.3 * metrics['total_return']
                # Fallback to just return if Sharpe not available
                elif 'total_return' in metrics:
                    return metrics['total_return']
            return -999  # Return large negative value if metrics not available
        
        # Run optimization
        optimization_results = perform_walk_forward_optimization(
            strategy_class=strategy_class,
            data=data,
            param_grid=param_grid,
            train_size=int(len(next(iter(data.values()))) * 0.6),  # 60% training window
            test_size=int(len(next(iter(data.values()))) * 0.2),   # 20% testing window
            step_size=int(len(next(iter(data.values()))) * 0.1),   # 10% step size
            objective_function=evaluate_performance,
            n_jobs=args.workers if args.parallel else 1
        )
        
        # Save optimization results
        results_path = output_dir / 'optimization_results.json'
        
        # Create a serializable version of the results
        serializable_results = {
            'overall_optimal': optimization_results['overall_optimal'],
            'param_stability': {
                param: {
                    k: (v.tolist() if isinstance(v, np.ndarray) else v)
                    for k, v in details.items()
                }
                for param, details in optimization_results['param_stability'].items()
            },
            'windows': []
        }
        
        # Process window results
        for window in optimization_results['windows']:
            serializable_window = {
                'window_idx': window['window_idx'],
                'window': window['window'],
                'optimal_params': window['optimal_params'],
                'performance': window['performance']
            }
            serializable_results['windows'].append(serializable_window)
        
        with open(results_path, 'w') as f:
            json.dump(serializable_results, f, indent=4)
        
        logger.info(f"Saved optimization results to {results_path}")
        
        # Generate optimization visualization
        try:
            from utils.optimization import plot_walk_forward_results
            fig = plot_walk_forward_results(optimization_results)
            fig.savefig(output_dir / 'optimization_results.png')
            plt.close(fig)
            logger.info(f"Saved optimization visualization to {output_dir}")
        except Exception as e:
            logger.warning(f"Error generating optimization visualization: {e}")
        
        return optimization_results
    
    except Exception as e:
        logger.error(f"Error in parameter optimization: {e}", exc_info=True)
        return None

def run_monte_carlo_simulation(strategy_class, data, backtest_results, args, output_dir):
    """Run Monte Carlo simulation for the strategy."""
    logger.info(f"Running Monte Carlo simulation for {strategy_class.__name__}")
    
    try:
        # Get equity curve or returns from backtest results
        if isinstance(backtest_results, dict):
            if 'equity_curve' in backtest_results:
                equity_series = backtest_results['equity_curve']
                returns = equity_series.pct_change().dropna()
            elif 'returns' in backtest_results:
                returns = backtest_results['returns']
            else:
                logger.error("Backtest results don't contain equity curve or returns data")
                return None
        else:
            logger.error("Invalid backtest results format")
            return None
        
        # Extract performance metrics
        performance_metrics = backtest_results.get('performance_metrics', {})
        if not performance_metrics:
            # Calculate basic metrics if not available
            performance_metrics = {
                'total_return': (returns + 1).prod() - 1,
                'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0,
                'max_drawdown': ((returns + 1).cumprod().cummax() - (returns + 1).cumprod()) / (returns + 1).cumprod().cummax()
            }
        
        # Run Monte Carlo analysis
        mc_results = run_monte_carlo_analysis(
            strategy=strategy_class.__name__,
            data=next(iter(data.values())),  # Use first symbol's data
            original_performance=performance_metrics,
            num_simulations=1000,
            output_dir=output_dir
        )
        
        logger.info(f"Completed Monte Carlo simulation with {mc_results.get('num_simulations', 0)} iterations")
        
        return mc_results
    
    except Exception as e:
        logger.error(f"Error in Monte Carlo simulation: {e}", exc_info=True)
        return None

def run_stress_tests(strategy_class, data, args, output_dir):
    """Run stress tests for the strategy."""
    logger.info(f"Running stress tests for {strategy_class.__name__}")
    
    try:
        # Get default stress scenarios
        scenarios = default_stress_scenarios()
        
        # Initialize strategy
        strategy_params = {}
        strategy = strategy_class(**strategy_params)
        
        # Run stress testing
        stress_results = perform_stress_testing(
            strategy=strategy,
            data_dict=data,
            scenarios=scenarios
        )
        
        # Save stress test results
        results_path = output_dir / 'stress_test_results.json'
        
        with open(results_path, 'w') as f:
            json.dump(stress_results, f, indent=4)
        
        logger.info(f"Saved stress test results to {results_path}")
        
        # Generate stress test visualization
        try:
            import matplotlib.pyplot as plt
            
            # Plot results for each scenario
            plt.figure(figsize=(12, 8))
            
            # Extract scenario names and total returns
            scenario_names = list(stress_results.keys())
            returns = [stress_results[s]['performance'].get('total_return', 0) for s in scenario_names]
            
            # Plot bar chart
            plt.bar(range(len(scenario_names)), returns)
            plt.xticks(range(len(scenario_names)), scenario_names, rotation=45)
            plt.title(f"{strategy_class.__name__} - Stress Test Results")
            plt.xlabel('Scenario')
            plt.ylabel('Total Return (%)')
            plt.tight_layout()
            plt.savefig(output_dir / 'stress_test_results.png')
            plt.close()
            
            logger.info(f"Saved stress test visualization to {output_dir}")
        except Exception as e:
            logger.warning(f"Error generating stress test visualization: {e}")
        
        return stress_results
    
    except Exception as e:
        logger.error(f"Error in stress testing: {e}", exc_info=True)
        return None

def run_market_event_analysis(data, args, output_dir):
    """Run market event analysis."""
    logger.info("Running market event analysis")
    
    try:
        # Initialize event detector
        event_detector = MarketEventDetector()
        
        # Detect events for each symbol
        all_events = []
        
        for symbol, symbol_data in data.items():
            symbol_base = symbol.split('/')[0]
            events = event_detector.detect_events(
                market_data=symbol_data,
                start_date=args.start_date,
                end_date=args.end_date,
                symbols=[symbol_base]
            )
            all_events.extend(events)
        
        # Save events to file
        events_path = output_dir / 'market_events.json'
        
        # Convert events to serializable format
        serializable_events = []
        for event in all_events:
            event_dict = {k: v for k, v in event.items()}
            # Convert datetime objects to strings
            if 'date' in event_dict and isinstance(event_dict['date'], datetime):
                event_dict['date'] = event_dict['date'].strftime('%Y-%m-%d %H:%M:%S')
            serializable_events.append(event_dict)
        
        with open(events_path, 'w') as f:
            json.dump(serializable_events, f, indent=4)
        
        logger.info(f"Saved {len(serializable_events)} market events to {events_path}")
        
        # Generate event visualization
        try:
            import matplotlib.pyplot as plt
            from matplotlib.dates import date2num
            
            # Get sentiment timeline
            sentiment_df = event_detector.get_sentiment_timeline()
            
            plt.figure(figsize=(12, 6))
            
            # Plot sentiment over time
            plt.plot(sentiment_df.index, sentiment_df['weighted_sentiment'], label='Sentiment')
            
            # Highlight high-impact events
            high_impact_events = [e for e in all_events if e.get('impact_score', 0) > 7]
            
            for event in high_impact_events:
                event_date = event['date']
                sentiment = event.get('sentiment', 0)
                plt.scatter([event_date], [sentiment], 
                          color='red' if sentiment < 0 else 'green',
                          s=100, zorder=5)
                plt.text(event_date, sentiment, event.get('type', ''), 
                        rotation=45, ha='right', fontsize=8)
            
            plt.title('Market Event Sentiment Timeline')
            plt.xlabel('Date')
            plt.ylabel('Sentiment')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_dir / 'event_sentiment.png')
            plt.close()
            
            logger.info(f"Saved event visualization to {output_dir}")
        except Exception as e:
            logger.warning(f"Error generating event visualization: {e}")
        
        return serializable_events
    
    except Exception as e:
        logger.error(f"Error in market event analysis: {e}", exc_info=True)
        return None

def run_benchmark_comparison(data, backtest_results, args, output_dir):
    """Compare strategy performance to benchmarks."""
    logger.info("Running benchmark comparison")
    
    try:
        # Get strategy equity curve
        if isinstance(backtest_results, dict) and 'equity_curve' in backtest_results:
            strategy_data = pd.DataFrame({'close': backtest_results['equity_curve']})
        else:
            logger.error("Backtest results don't contain equity curve data")
            return None
        
        # Use market data as benchmarks
        benchmarks = {}
        
        # Use first symbol as primary benchmark
        primary_symbol = args.symbols[0] if args.symbols else list(data.keys())[0]
        benchmarks[primary_symbol] = data[primary_symbol]
        
        # Add ETH as additional benchmark if available
        eth_symbol = 'ETH/USDT'
        if eth_symbol in data:
            benchmarks['ETH'] = data[eth_symbol]
        
        # Run comparison
        comparison_results = compare_to_benchmarks(
            strategy_data=strategy_data,
            benchmarks=benchmarks
        )
        
        # Save comparison results
        results_path = output_dir / 'benchmark_comparison.json'
        
        # Convert to serializable format
        serializable_results = {}
        for benchmark, result in comparison_results.items():
            serializable_results[benchmark] = {
                'metrics': result['metrics'],
                'strategy_cum_returns': result['strategy_cum_returns'].to_json(),
                'benchmark_cum_returns': result['benchmark_cum_returns'].to_json(),
                'strategy_drawdown': result['strategy_drawdown'].to_json(),
                'benchmark_drawdown': result['benchmark_drawdown'].to_json()
            }
        
        with open(results_path, 'w') as f:
            json.dump(serializable_results, f, indent=4)
        
        logger.info(f"Saved benchmark comparison to {results_path}")
        
        # Generate comparison visualization
        try:
            from utils.benchmark_analysis import plot_benchmark_comparison
            fig = plot_benchmark_comparison(comparison_results)
            fig.savefig(output_dir / 'benchmark_comparison.png')
            plt.close(fig)
            logger.info(f"Saved benchmark visualization to {output_dir}")
        except Exception as e:
            logger.warning(f"Error generating benchmark visualization: {e}")
        
        return comparison_results
    
    except Exception as e:
        logger.error(f"Error in benchmark comparison: {e}", exc_info=True)
        return None

def launch_dashboard():
    """Launch the monitoring dashboard."""
    logger.info("Launching monitoring dashboard")
    
    try:
        # Dashboard launcher script path
        dashboard_launcher = script_dir / 'run_dashboard.py'
        
        if not dashboard_launcher.exists():
            logger.error(f"Dashboard launcher not found: {dashboard_launcher}")
            return False
        
        # Launch dashboard in a subprocess
        subprocess.Popen([sys.executable, str(dashboard_launcher)])
        
        logger.info("Dashboard launched successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error launching dashboard: {e}")
        return False

def main():
    """Main function."""
    # Parse arguments
    args = parse_args()
    
    # Determine strategies to run
    strategies_to_run = []
    if args.strategy == 'all':
        strategies_to_run = list(STRATEGY_CLASSES.keys())
    else:
        strategies_to_run = [args.strategy]
    
    logger.info(f"Running strategies: {strategies_to_run}")
    
    # Load market data
    data = load_data(args.symbols, args.timeframe, args.start_date, args.end_date)
    
    if data is None:
        return 1
    
    # Run strategies
    for strategy_name in strategies_to_run:
        logger.info(f"Processing strategy: {strategy_name}")
        
        # Create output directory
        output_dir = create_output_dir(strategy_name, args.output_dir)
        
        # Save run configuration
        save_config(args, output_dir)
        
        # Import strategy class
        strategy_class = import_strategy_class(strategy_name)
        
        if strategy_class is None:
            continue
        
        # Run backtest
        backtest_results = None
        if args.backtest:
            backtest_results = run_backtest(strategy_class, data, args, output_dir)
        
        # Run parameter optimization
        if args.optimize:
            optimization_results = run_parameter_optimization(strategy_class, data, args, output_dir)
        
        # Run Monte Carlo simulation
        if args.monte_carlo and backtest_results is not None:
            mc_results = run_monte_carlo_simulation(strategy_class, data, backtest_results, args, output_dir)
        
        # Run stress tests
        if args.stress_test:
            stress_results = run_stress_tests(strategy_class, data, args, output_dir)
        
        # Run market event analysis
        if args.event_analysis:
            event_results = run_market_event_analysis(data, args, output_dir)
        
        # Run benchmark comparison
        if args.benchmark and backtest_results is not None:
            benchmark_results = run_benchmark_comparison(data, backtest_results, args, output_dir)
    
    # Launch dashboard if requested
    if args.dashboard:
        launch_dashboard()
    
    logger.info("Strategy runner completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 