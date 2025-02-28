# advanced_trading/utils/optimization.py

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
import logging
import matplotlib.pyplot as plt
from datetime import datetime
import os
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

def perform_walk_forward_optimization(
    strategy_class: Any,
    data: Dict[str, pd.DataFrame],
    param_grid: Dict[str, List[Any]],
    train_size: int,
    test_size: int,
    step_size: int,
    objective_function: Callable[[Dict[str, Any]], float],
    n_jobs: int = 1
) -> Dict[str, Any]:
    """
    Perform walk-forward optimization of strategy parameters.
    
    Args:
        strategy_class: Class of the strategy to optimize
        data: Dictionary of market data by symbol
        param_grid: Dictionary of parameters to optimize
        train_size: Size of training window
        test_size: Size of testing window
        step_size: Size of steps between windows
        objective_function: Function to evaluate performance (higher is better)
        n_jobs: Number of parallel jobs
        
    Returns:
        Dictionary of optimization results
    """
    logger.info("Starting walk-forward optimization")
    
    # Generate all parameter combinations
    param_keys = list(param_grid.keys())
    param_values = list(param_grid.values())
    param_combinations = list(itertools.product(*param_values))
    
    logger.info(f"Evaluating {len(param_combinations)} parameter combinations")
    
    # Get total data length
    # Assuming all data has same length and index
    first_symbol = list(data.keys())[0]
    total_length = len(data[first_symbol])
    
    # Create windows for walk-forward optimization
    windows = []
    for start_idx in range(0, total_length - (train_size + test_size) + 1, step_size):
        train_end = start_idx + train_size
        test_end = train_end + test_size
        
        windows.append({
            'train_start': start_idx,
            'train_end': train_end,
            'test_start': train_end,
            'test_end': test_end
        })
    
    logger.info(f"Created {len(windows)} walk-forward windows")
    
    # Store results for each window
    window_results = []
    
    # Process each window
    for window_idx, window in enumerate(windows):
        logger.info(f"Processing window {window_idx+1}/{len(windows)}")
        
        # Extract train/test data
        train_data = {}
        test_data = {}
        
        for symbol, symbol_data in data.items():
            train_data[symbol] = symbol_data.iloc[window['train_start']:window['train_end']]
            test_data[symbol] = symbol_data.iloc[window['test_start']:window['test_end']]
        
        # Find optimal parameters for this window
        optimal_params, all_results = _optimize_window(
            strategy_class=strategy_class,
            train_data=train_data,
            test_data=test_data,
            param_combinations=param_combinations,
            param_keys=param_keys,
            objective_function=objective_function,
            n_jobs=n_jobs
        )
        
        # Store results
        window_results.append({
            'window_idx': window_idx,
            'window': window,
            'optimal_params': optimal_params,
            'performance': all_results[0]['performance'],  # Best performance
            'all_results': all_results
        })
    
    # Analyze stability of optimal parameters
    param_stability = _analyze_parameter_stability(window_results, param_keys)
    
    # Determine overall optimal parameters
    overall_optimal = _determine_overall_optimal(window_results, param_keys)
    
    # Create final results
    results = {
        'windows': window_results,
        'param_stability': param_stability,
        'overall_optimal': overall_optimal
    }
    
    logger.info("Walk-forward optimization completed")
    return results

def _optimize_window(
    strategy_class: Any,
    train_data: Dict[str, pd.DataFrame],
    test_data: Dict[str, pd.DataFrame],
    param_combinations: List[Tuple],
    param_keys: List[str],
    objective_function: Callable[[Dict[str, Any]], float],
    n_jobs: int = 1
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Optimize parameters for a single window.
    
    Args:
        strategy_class: Class of the strategy to optimize
        train_data: Training data
        test_data: Test data
        param_combinations: List of parameter combinations
        param_keys: List of parameter keys
        objective_function: Function to evaluate performance
        n_jobs: Number of parallel jobs
        
    Returns:
        Tuple of (optimal parameters, all results)
    """
    # Function to evaluate a parameter combination
    def evaluate_params(params_tuple):
        # Convert tuple to dictionary
        params = {key: value for key, value in zip(param_keys, params_tuple)}
        
        try:
            # Initialize strategy with parameters
            strategy = strategy_class(**params)
            
            # Train strategy
            strategy.train(train_data)
            
            # Test strategy
            performance = strategy.backtest(test_data)
            
            # Calculate objective score
            score = objective_function(performance)
            
            return {
                'params': params,
                'score': score,
                'performance': performance
            }
        except Exception as e:
            logger.warning(f"Error evaluating parameters {params}: {e}")
            return {
                'params': params,
                'score': float('-inf'),
                'performance': None
            }
    
    # Evaluate all parameter combinations
    results = []
    
    if n_jobs > 1:
        # Parallel execution
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {executor.submit(evaluate_params, params): params for params in param_combinations}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
    else:
        # Sequential execution
        for params in param_combinations:
            result = evaluate_params(params)
            if result:
                results.append(result)
    
    # Sort results by score (descending)
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # Get optimal parameters
    optimal_params = results[0]['params'] if results else {}
    
    return optimal_params, results

def _analyze_parameter_stability(window_results: List[Dict[str, Any]], 
                              param_keys: List[str]) -> Dict[str, Any]:
    """
    Analyze the stability of optimal parameters across windows.
    
    Args:
        window_results: Results for each window
        param_keys: List of parameter keys
        
    Returns:
        Dictionary of parameter stability metrics
    """
    stability = {}
    
    for param in param_keys:
        # Extract optimal values for this parameter across all windows
        values = [window['optimal_params'].get(param) for window in window_results]
        
        # Count frequency of each value
        value_counts = {}
        for value in values:
            if value not in value_counts:
                value_counts[value] = 0
            value_counts[value] += 1
        
        # Calculate stability metrics
        most_common_value = max(value_counts.items(), key=lambda x: x[1])[0]
        most_common_frequency = value_counts[most_common_value] / len(values)
        
        # Calculate variance for numeric parameters
        variance = None
        if all(isinstance(v, (int, float)) for v in values):
            variance = np.var(values)
        
        stability[param] = {
            'values': values,
            'most_common': most_common_value,
            'frequency': most_common_frequency,
            'variance': variance
        }
    
    return stability

def _determine_overall_optimal(window_results: List[Dict[str, Any]], 
                            param_keys: List[str]) -> Dict[str, Any]:
    """
    Determine overall optimal parameters based on window results.
    
    Args:
        window_results: Results for each window
        param_keys: List of parameter keys
        
    Returns:
        Dictionary of overall optimal parameters
    """
    # Start with the most frequent value for each parameter
    stability = _analyze_parameter_stability(window_results, param_keys)
    optimal = {param: stability[param]['most_common'] for param in param_keys}
    
    # Average performance metrics
    performances = [window['performance'] for window in window_results if window['performance']]
    avg_performance = {}
    
    if performances:
        # Find common keys across all performances
        common_keys = set(performances[0].keys())
        for perf in performances[1:]:
            common_keys &= set(perf.keys())
        
        # Calculate average for each metric
        for key in common_keys:
            if all(isinstance(perf[key], (int, float)) for perf in performances):
                avg_performance[key] = np.mean([perf[key] for perf in performances])
    
    return {
        'params': optimal,
        'avg_performance': avg_performance
    }

def plot_walk_forward_results(results: Dict[str, Any], 
                           save_path: Optional[str] = None) -> plt.Figure:
    """
    Plot results of walk-forward optimization.
    
    Args:
        results: Walk-forward optimization results
        save_path: Path to save the visualization
        
    Returns:
        Matplotlib figure
    """
    # Extract data
    window_results = results['windows']
    param_stability = results['param_stability']
    
    # Create figure
    fig = plt.figure(figsize=(15, 10))
    
    # Plot performance across windows
    ax1 = plt.subplot(2, 1, 1)
    
    window_indices = [window['window_idx'] for window in window_results]
    performances = []
    
    # Check for common performance metrics
    if window_results and 'performance' in window_results[0]:
        first_perf = window_results[0]['performance']
        if isinstance(first_perf, dict) and 'total_return' in first_perf:
            # Plot total return
            performances = [window['performance'].get('total_return', 0) for window in window_results]
            ax1.plot(window_indices, performances, marker='o')
            ax1.set_title('Total Return by Window')
            ax1.set_xlabel('Window Index')
            ax1.set_ylabel('Total Return')
            ax1.grid(True, alpha=0.3)
    
    # Plot parameter stability for numeric parameters
    ax2 = plt.subplot(2, 1, 2)
    
    # Filter for numeric parameters
    numeric_params = []
    for param, stability in param_stability.items():
        if all(isinstance(v, (int, float)) for v in stability['values']):
            numeric_params.append(param)
    
    # Plot up to 5 parameters
    for i, param in enumerate(numeric_params[:5]):
        values = param_stability[param]['values']
        ax2.plot(window_indices, values, marker='o', label=param)
    
    ax2.set_title('Parameter Values by Window')
    ax2.set_xlabel('Window Index')
    ax2.set_ylabel('Parameter Value')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Walk-forward optimization plot saved to {save_path}")
    
    return fig

class ParameterOptimizer:
    """
    Strategy parameter optimization framework supporting multiple optimization methods.
    """
    
    def __init__(self, 
                objective_function: Callable, 
                param_space: Dict[str, Union[List, Tuple]],
                optimization_method: str = 'bayesian',
                maximize: bool = True,
                n_trials: int = 100,
                n_jobs: int = -1,
                random_seed: int = 42,
                save_dir: Optional[str] = None):
        """
        Initialize the parameter optimizer.
        
        Args:
            objective_function: Function that takes parameters dict and returns score
            param_space: Dictionary mapping parameter names to their possible values
            optimization_method: One of 'bayesian', 'grid', 'random'
            maximize: Whether to maximize (True) or minimize (False) the objective
            n_trials: Number of trials for random and bayesian methods
            n_jobs: Number of parallel jobs (-1 for all available cores)
            random_seed: Random seed for reproducibility
            save_dir: Directory to save optimization results (optional)
        """
        self.objective_function = objective_function
        self.param_space = param_space
        self.optimization_method = optimization_method.lower()
        self.maximize = maximize
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.random_seed = random_seed
        
        # Validate optimization method
        valid_methods = ['bayesian', 'grid', 'random']
        if self.optimization_method not in valid_methods:
            raise ValueError(f"Optimization method must be one of {valid_methods}")
        
        # Results storage
        self.results = []
        self.best_params = None
        self.best_score = -float('inf') if maximize else float('inf')
        
        # Set up save directory
        if save_dir is not None:
            self.save_dir = Path(save_dir)
            os.makedirs(self.save_dir, exist_ok=True)
        else:
            self.save_dir = None
        
        # Set random seed
        np.random.seed(self.random_seed)
        
        logger.info(f"Initialized {self.optimization_method} optimizer with {len(param_space)} parameters")
    
    def optimize(self) -> Dict[str, Any]:
        """
        Run the optimization process.
        
        Returns:
            Dictionary with best parameters and optimization results
        """
        logger.info(f"Starting {self.optimization_method} optimization...")
        start_time = time.time()
        
        if self.optimization_method == 'grid':
            self._grid_search()
        elif self.optimization_method == 'random':
            self._random_search()
        elif self.optimization_method == 'bayesian':
            self._bayesian_optimization()
        
        elapsed_time = time.time() - start_time
        logger.info(f"Optimization completed in {elapsed_time:.2f} seconds")
        logger.info(f"Best score: {self.best_score}")
        logger.info(f"Best parameters: {self.best_params}")
        
        # Save results if directory is provided
        if self.save_dir is not None:
            self.save_results()
        
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'all_results': self.results,
            'elapsed_time': elapsed_time
        }
    
    def _grid_search(self):
        """Perform exhaustive grid search over the parameter space."""
        # Get all parameter combinations
        param_names = list(self.param_space.keys())
        param_values = list(self.param_space.values())
        
        # Calculate total combinations for progress tracking
        total_combinations = np.prod([len(values) for values in param_values])
        logger.info(f"Grid search with {total_combinations} parameter combinations")
        
        # Create all combinations
        for i, combination in enumerate(itertools.product(*param_values)):
            # Create parameter dictionary
            params = dict(zip(param_names, combination))
            
            # Evaluate parameters
            score = self._evaluate_params(params)
            
            # Log progress
            if (i + 1) % max(1, total_combinations // 10) == 0:
                progress = (i + 1) / total_combinations * 100
                logger.info(f"Progress: {progress:.1f}% ({i + 1}/{total_combinations})")
    
    def _random_search(self):
        """Perform random search over the parameter space."""
        logger.info(f"Random search with {self.n_trials} trials")
        
        for i in range(self.n_trials):
            # Sample random parameters
            params = self._sample_random_params()
            
            # Evaluate parameters
            score = self._evaluate_params(params)
            
            # Log progress
            if (i + 1) % max(1, self.n_trials // 10) == 0:
                progress = (i + 1) / self.n_trials * 100
                logger.info(f"Progress: {progress:.1f}% ({i + 1}/{self.n_trials})")
    
    def _bayesian_optimization(self):
        """Perform Bayesian optimization using scikit-optimize."""
        try:
            from skopt import gp_minimize, Optimizer
            from skopt.space import Real, Integer, Categorical
            from skopt.utils import use_named_args
            from skopt.plots import plot_convergence
        except ImportError:
            logger.error("scikit-optimize not installed. Please install with 'pip install scikit-optimize'")
            logger.info("Falling back to random search")
            return self._random_search()
        
        logger.info(f"Bayesian optimization with {self.n_trials} trials")
        
        # Define the search space for skopt
        space = []
        dimensions_names = []
        
        for name, values in self.param_space.items():
            dimensions_names.append(name)
            
            if isinstance(values, (list, tuple)):
                # Check if all values are numeric
                if all(isinstance(v, (int, float)) for v in values):
                    if all(isinstance(v, int) for v in values):
                        # Integer values
                        space.append(Integer(min(values), max(values), name=name))
                    else:
                        # Float values
                        space.append(Real(min(values), max(values), name=name))
                else:
                    # Categorical values
                    space.append(Categorical(values, name=name))
            elif isinstance(values, dict) and 'min' in values and 'max' in values:
                # Range specification
                if values.get('type') == 'int':
                    space.append(Integer(values['min'], values['max'], name=name))
                else:
                    space.append(Real(values['min'], values['max'], name=name))
        
        # Define the objective function for skopt
        @use_named_args(space)
        def objective(**params):
            # Convert params to correct types
            processed_params = {}
            for name, value in params.items():
                param_def = self.param_space.get(name)
                if isinstance(param_def, dict) and param_def.get('type') == 'int':
                    processed_params[name] = int(value)
                else:
                    processed_params[name] = value
            
            score = self._evaluate_params(processed_params)
            return -score if self.maximize else score
        
        # Run the optimization
        result = gp_minimize(
            objective,
            space,
            n_calls=self.n_trials,
            random_state=self.random_seed,
            n_jobs=self.n_jobs,
            verbose=True
        )
        
        # Process the results
        best_params_values = result.x
        self.best_params = dict(zip(dimensions_names, best_params_values))
        self.best_score = -result.fun if self.maximize else result.fun
        
        # Create plot if save_dir is provided
        if self.save_dir is not None:
            plt.figure(figsize=(10, 6))
            plot_convergence(result)
            plt.savefig(self.save_dir / 'convergence_plot.png', dpi=100)
            plt.close()
    
    def _sample_random_params(self) -> Dict[str, Any]:
        """Sample random parameters from the parameter space."""
        params = {}
        
        for name, values in self.param_space.items():
            if isinstance(values, (list, tuple)):
                # Sample from list of values
                params[name] = np.random.choice(values)
            elif isinstance(values, dict) and 'min' in values and 'max' in values:
                # Sample from range
                if values.get('type') == 'int':
                    params[name] = np.random.randint(values['min'], values['max'] + 1)
                else:
                    params[name] = np.random.uniform(values['min'], values['max'])
        
        return params
    
    def _evaluate_params(self, params: Dict[str, Any]) -> float:
        """
        Evaluate a set of parameters using the objective function.
        
        Args:
            params: Dictionary of parameter values
            
        Returns:
            Score from the objective function
        """
        try:
            score = self.objective_function(params)
            
            # Handle invalid scores
            if score is None or np.isnan(score):
                logger.warning(f"Invalid score for parameters {params}")
                score = FAILED_STRATEGY_SCORE
            
            # Update best score and parameters
            if self.maximize and score > self.best_score:
                self.best_score = score
                self.best_params = params.copy()
                logger.info(f"New best score: {score} with parameters {params}")
            elif not self.maximize and score < self.best_score:
                self.best_score = score
                self.best_params = params.copy()
                logger.info(f"New best score: {score} with parameters {params}")
            
            # Store result
            self.results.append({
                'params': params.copy(),
                'score': score,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            return score
        
        except Exception as e:
            logger.error(f"Error evaluating parameters {params}: {str(e)}")
            # Store the failed result
            self.results.append({
                'params': params.copy(),
                'score': FAILED_STRATEGY_SCORE,
                'error': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            return FAILED_STRATEGY_SCORE
    
    def save_results(self):
        """Save optimization results to disk."""
        if self.save_dir is None:
            logger.warning("No save directory specified, skipping result saving")
            return
        
        # Create timestamp for the files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save results to CSV
        results_df = pd.DataFrame(self.results)
        results_df.to_csv(self.save_dir / f'optimization_results_{timestamp}.csv', index=False)
        
        # Save best parameters
        best_params_file = self.save_dir / f'best_params_{timestamp}.pkl'
        with open(best_params_file, 'wb') as f:
            pickle.dump(self.best_params, f)
        
        # Create visualization of parameter importance
        self._plot_parameter_importance()
        
        logger.info(f"Optimization results saved to {self.save_dir}")
    
    def _plot_parameter_importance(self):
        """Create plot showing the importance of each parameter."""
        if not self.results:
            return
        
        # Convert results to DataFrame
        results_df = pd.DataFrame(self.results)
        
        # Filter out failed runs
        results_df = results_df[results_df['score'] != FAILED_STRATEGY_SCORE]
        
        if len(results_df) < 5:  # Need enough data for meaningful analysis
            return
        
        # Create figure
        fig, axes = plt.subplots(len(self.param_space), 1, figsize=(10, 3 * len(self.param_space)))
        
        # Ensure axes is always a list
        if len(self.param_space) == 1:
            axes = [axes]
        
        # Plot parameter vs score for each parameter
        for i, (param_name, param_values) in enumerate(self.param_space.items()):
            ax = axes[i]
            
            # Extract parameter values and scores
            if param_name in results_df['params'].iloc[0]:
                # Parameter values are directly in the params dictionary
                param_data = [result['params'][param_name] for result in self.results 
                             if result['score'] != FAILED_STRATEGY_SCORE]
            else:
                logger.warning(f"Parameter {param_name} not found in results")
                continue
            
            scores = results_df['score'].values
            
            # Plot parameter vs score
            ax.scatter(param_data, scores, alpha=0.6)
            ax.set_xlabel(param_name)
            ax.set_ylabel('Score')
            ax.set_title(f'Parameter Importance: {param_name}')
            ax.grid(True, alpha=0.3)
            
            # Add best parameter marker
            if self.best_params is not None and param_name in self.best_params:
                best_value = self.best_params[param_name]
                ax.axvline(x=best_value, color='red', linestyle='--', 
                          label=f'Best: {best_value}')
                ax.legend()
        
        plt.tight_layout()
        plt.savefig(self.save_dir / 'parameter_importance.png', dpi=100)
        plt.close()


def walk_forward_optimization(strategy_constructor: Callable,
                             data: Dict[str, pd.DataFrame],
                             param_space: Dict[str, Union[List, Tuple]],
                             train_size: int,
                             test_size: int,
                             step_size: int,
                             optimization_method: str = 'bayesian',
                             n_trials: int = 50,
                             maximize_metric: str = 'sharpe_ratio',
                             n_jobs: int = -1) -> Dict[str, Any]:
    """
    Perform walk-forward optimization with proper training/testing separation.
    
    Args:
        strategy_constructor: Function that creates a strategy instance with given parameters
        data: Dictionary of DataFrames (e.g., by symbol)
        param_space: Dictionary mapping parameter names to their possible values
        train_size: Number of bars in the training window
        test_size: Number of bars in the test window
        step_size: Number of bars to step forward
        optimization_method: One of 'bayesian', 'grid', 'random'
        n_trials: Number of trials for random and bayesian methods
        maximize_metric: Metric to maximize in the objective function
        n_jobs: Number of parallel jobs
        
    Returns:
        Dictionary with optimization results for each fold
    """
    logger.info(f"Starting walk-forward optimization with {len(data)} symbols")
    
    # Validate inputs
    if not data:
        raise ValueError("No data provided")
    
    # Get total data length (assume all DataFrames have same length)
    first_symbol = next(iter(data.values()))
    total_bars = len(first_symbol)
    
    if total_bars < train_size + test_size:
        raise ValueError(f"Insufficient data: {total_bars} bars available, "
                        f"but {train_size + test_size} required")
    
    # Calculate number of folds
    n_folds = (total_bars - train_size - test_size) // step_size + 1
    logger.info(f"Performing {n_folds} optimization folds")
    
    # Results storage
    fold_results = []
    all_test_results = []
    combined_equity_curve = pd.Series(dtype=float)
    
    # Create directory for results
    results_dir = Path(f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(results_dir, exist_ok=True)
    
    # For each fold
    for fold in range(n_folds):
        logger.info(f"Starting fold {fold + 1}/{n_folds}")
        
        # Calculate indices
        train_start = fold * step_size
        train_end = train_start + train_size
        test_start = train_end
        test_end = test_start + test_size
        
        # Skip if we've reached the end of data
        if test_end > total_bars:
            logger.info(f"Skipping fold {fold + 1} as it exceeds available data")
            continue
        
        # Create training and test datasets
        train_data = {symbol: df.iloc[train_start:train_end].copy() 
                     for symbol, df in data.items()}
        
        test_data = {symbol: df.iloc[test_start:test_end].copy() 
                    for symbol, df in data.items()}
        
        # Define the objective function for this fold
        def objective_function(params):
            try:
                # Create strategy with these parameters
                strategy = strategy_constructor(**params)
                
                # Train on training data
                strategy_metrics = strategy.backtest(train_data)
                
                # Return the metric we want to maximize
                if maximize_metric in strategy_metrics:
                    return strategy_metrics[maximize_metric]
                else:
                    logger.warning(f"Metric {maximize_metric} not found in strategy results")
                    return FAILED_STRATEGY_SCORE
            except Exception as e:
                logger.error(f"Error in objective function: {str(e)}")
                return FAILED_STRATEGY_SCORE
        
        # Create optimizer for this fold
        fold_optimizer = ParameterOptimizer(
            objective_function=objective_function,
            param_space=param_space,
            optimization_method=optimization_method,
            maximize=True,
            n_trials=n_trials,
            n_jobs=n_jobs,
            save_dir=results_dir / f"fold_{fold + 1}"
        )
        
        # Run optimization
        fold_opt_results = fold_optimizer.optimize()
        
        # Get best parameters
        best_params = fold_opt_results['best_params']
        
        # Test the best parameters on the test set
        try:
            # Create strategy with best parameters
            best_strategy = strategy_constructor(**best_params)
            
            # Run strategy on test data
            test_results = best_strategy.backtest(test_data)
            
            # Store test results
            test_metrics = {
                'fold': fold + 1,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'best_params': best_params,
                'train_score': fold_opt_results['best_score'],
                'test_metrics': test_results
            }
            
            all_test_results.append(test_metrics)
            
            # Add test equity curve to combined equity curve
            if 'equity_curve' in test_results:
                test_equity = test_results['equity_curve']
                
                if combined_equity_curve.empty:
                    combined_equity_curve = test_equity
                else:
                    # Scale to connect with previous equity curve
                    scaling_factor = combined_equity_curve.iloc[-1] / test_equity.iloc[0]
                    adjusted_equity = test_equity * scaling_factor
                    combined_equity_curve = pd.concat([combined_equity_curve, adjusted_equity.iloc[1:]])
            
            logger.info(f"Fold {fold + 1} test {maximize_metric}: {test_results.get(maximize_metric, 'N/A')}")
        
        except Exception as e:
            logger.error(f"Error testing fold {fold + 1}: {str(e)}")
            test_metrics = {
                'fold': fold + 1,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'best_params': best_params,
                'train_score': fold_opt_results['best_score'],
                'test_metrics': {'error': str(e)}
            }
            all_test_results.append(test_metrics)
        
        # Store fold results
        fold_results.append({
            'fold': fold + 1,
            'optimization_results': fold_opt_results,
            'test_results': test_metrics
        })
    
    # Calculate aggregate statistics
    test_scores = [r['test_metrics'].get(maximize_metric) for r in all_test_results 
                  if isinstance(r['test_metrics'], dict) and maximize_metric in r['test_metrics']]
    
    if test_scores:
        avg_test_score = np.mean(test_scores)
        std_test_score = np.std(test_scores)
        min_test_score = np.min(test_scores)
        max_test_score = np.max(test_scores)
        
        logger.info(f"Walk-forward optimization complete.")
        logger.info(f"Average test {maximize_metric}: {avg_test_score:.4f} ± {std_test_score:.4f}")
        logger.info(f"Range: [{min_test_score:.4f}, {max_test_score:.4f}]")
    else:
        logger.warning("No valid test scores available")
    
    # Create visualization
    plt.figure(figsize=(12, 6))
    
    if not combined_equity_curve.empty:
        plt.plot(combined_equity_curve)
        plt.title('Walk-Forward Optimization: Combined Equity Curve')
        plt.xlabel('Bar')
        plt.ylabel('Equity')
        plt.grid(True, alpha=0.3)
        plt.savefig(results_dir / 'combined_equity_curve.png', dpi=100)
    
    # Save aggregate results
    summary = {
        'n_folds': n_folds,
        'param_space': param_space,
        'train_size': train_size,
        'test_size': test_size,
        'step_size': step_size,
        'optimization_method': optimization_method,
        'maximize_metric': maximize_metric,
        'avg_test_score': avg_test_score if test_scores else None,
        'std_test_score': std_test_score if test_scores else None,
        'min_test_score': min_test_score if test_scores else None,
        'max_test_score': max_test_score if test_scores else None,
    }
    
    # Save summary to file
    with open(results_dir / 'summary.pkl', 'wb') as f:
        pickle.dump(summary, f)
    
    # Save test results to CSV
    test_results_df = pd.DataFrame([
        {
            'fold': r['fold'],
            'train_start': r['train_start'],
            'train_end': r['train_end'],
            'test_start': r['test_start'],
            'test_end': r['test_end'],
            'train_score': r['train_score'],
            **{f"test_{k}": v for k, v in r['test_metrics'].items() 
               if k != 'equity_curve' and not isinstance(v, dict)}
        }
        for r in all_test_results
        if isinstance(r['test_metrics'], dict)
    ])
    
    if not test_results_df.empty:
        test_results_df.to_csv(results_dir / 'test_results.csv', index=False)
    
    return {
        'fold_results': fold_results,
        'all_test_results': all_test_results,
        'combined_equity_curve': combined_equity_curve,
        'summary': summary,
        'results_dir': results_dir
    }


def monte_carlo_simulation(returns: pd.Series, 
                          n_simulations: int = 1000, 
                          block_size: int = 0,
                          random_seed: int = 42) -> Dict[str, Any]:
    """
    Perform Monte Carlo simulation to assess strategy robustness.
    
    Args:
        returns: Series of strategy returns
        n_simulations: Number of simulations to run
        block_size: Block size for block bootstrap (0 for regular bootstrap)
        random_seed: Random seed for reproducibility
        
    Returns:
        Dictionary with simulation results
    """
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    # Set random seed
    np.random.seed(random_seed)
    
    # Store original equity curve for reference
    original_equity = (1 + returns).cumprod()
    
    # Store simulation paths
    equity_paths = np.zeros((n_simulations, len(returns)))
    
    # Block bootstrap
    if block_size > 0:
        # Create blocks of returns
        n_blocks = len(returns) // block_size
        if n_blocks < 10:  # Need enough blocks for meaningful simulation
            logger.warning(f"Too few blocks ({n_blocks}) for block size {block_size}. Using simple bootstrap.")
            block_size = 0
        else:
            blocks = []
            for i in range(n_blocks):
                start_idx = i * block_size
                end_idx = start_idx + block_size
                if end_idx <= len(returns):
                    blocks.append(returns.iloc[start_idx:end_idx].values)
    
    # Run simulations
    for i in range(n_simulations):
        if block_size > 0:
            # Block bootstrap
            block_indices = np.random.choice(len(blocks), n_blocks, replace=True)
            sim_returns = np.concatenate([blocks[idx] for idx in block_indices])
            # Truncate to original length
            sim_returns = sim_returns[:len(returns)]
        else:
            # Simple bootstrap
            sim_returns = np.random.choice(returns, len(returns), replace=True)
        
        # Calculate equity curve
        equity_paths[i, :] = (1 + sim_returns).cumprod()
    
    # Calculate percentiles
    percentiles = {
        'lower_5': np.percentile(equity_paths, 5, axis=0),
        'lower_25': np.percentile(equity_paths, 25, axis=0),
        'median': np.percentile(equity_paths, 50, axis=0),
        'upper_75': np.percentile(equity_paths, 75, axis=0),
        'upper_95': np.percentile(equity_paths, 95, axis=0)
    }
    
    # Calculate final equity statistics
    final_values = equity_paths[:, -1]
    final_stats = {
        'mean': np.mean(final_values),
        'median': np.median(final_values),
        'std': np.std(final_values),
        'min': np.min(final_values),
        'max': np.max(final_values),
        'percentile_5': np.percentile(final_values, 5),
        'percentile_95': np.percentile(final_values, 95)
    }
    
    # Calculate probability of profit
    prob_profit = np.mean(final_values > 1.0) * 100
    
    # Calculate maximum drawdown distribution
    max_drawdowns = []
    for path in equity_paths:
        peak = np.maximum.accumulate(path)
        drawdown = (path / peak) - 1
        max_drawdowns.append(np.min(drawdown) * 100)  # Convert to percentage
    
    drawdown_stats = {
        'mean': np.mean(max_drawdowns),
        'median': np.median(max_drawdowns),
        'std': np.std(max_drawdowns),
        'min': np.min(max_drawdowns),
        'max': np.max(max_drawdowns),
        'percentile_5': np.percentile(max_drawdowns, 5),
        'percentile_95': np.percentile(max_drawdowns, 95)
    }
    
    # Final results dictionary
    results = {
        'original_equity': original_equity,
        'equity_paths': equity_paths,
        'percentiles': percentiles,
        'final_stats': final_stats,
        'probability_of_profit': prob_profit,
        'drawdown_stats': drawdown_stats,
        'max_drawdowns': max_drawdowns,
        'simulation_params': {
            'n_simulations': n_simulations,
            'block_size': block_size,
            'random_seed': random_seed
        }
    }
    
    return results


def plot_monte_carlo_results(mc_results: Dict[str, Any], 
                            title: str = 'Monte Carlo Simulation',
                            save_path: Optional[str] = None) -> plt.Figure:
    """
    Plot Monte Carlo simulation results.
    
    Args:
        mc_results: Results dictionary from monte_carlo_simulation
        title: Plot title
        save_path: Path to save the plot (optional)
        
    Returns:
        Matplotlib figure with plots
    """
    # Create figure
    fig = plt.figure(figsize=(15, 10))
    fig.suptitle(title, fontsize=16)
    
    # Grid specification
    gs = fig.add_gridspec(2, 2)
    
    # 1. Equity curves with percentiles
    ax1 = fig.add_subplot(gs[0, :])
    
    # Get data
    original_equity = mc_results['original_equity']
    percentiles = mc_results['percentiles']
    
    # Create x-axis (bar numbers)
    x = np.arange(len(original_equity))
    
    # Plot percentiles
    ax1.fill_between(x, percentiles['lower_5'], percentiles['upper_95'], 
                    alpha=0.1, color='blue', label='5-95% Range')
    ax1.fill_between(x, percentiles['lower_25'], percentiles['upper_75'], 
                    alpha=0.2, color='blue', label='25-75% Range')
    ax1.plot(x, percentiles['median'], 'b', label='Median')
    ax1.plot(x, original_equity, 'r', label='Original')
    
    ax1.set_title('Equity Curve Distribution')
    ax1.set_xlabel('Bar')
    ax1.set_ylabel('Equity')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Final equity distribution
    ax2 = fig.add_subplot(gs[1, 0])
    
    # Get data
    final_values = mc_results['equity_paths'][:, -1]
    
    # Plot histogram
    ax2.hist(final_values, bins=50, alpha=0.7, color='blue')
    ax2.axvline(x=mc_results['final_stats']['mean'], color='r', linestyle='-', 
               label=f"Mean: {mc_results['final_stats']['mean']:.2f}")
    ax2.axvline(x=mc_results['final_stats']['median'], color='g', linestyle='--', 
               label=f"Median: {mc_results['final_stats']['median']:.2f}")
    ax2.axvline(x=1.0, color='k', linestyle=':', label="Break-even")
    
    ax2.set_title('Final Equity Distribution')
    ax2.set_xlabel('Final Equity')
    ax2.set_ylabel('Frequency')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Drawdown distribution
    ax3 = fig.add_subplot(gs[1, 1])
    
    # Get data
    max_drawdowns = mc_results['max_drawdowns']
    
    # Plot histogram
    ax3.hist(max_drawdowns, bins=50, alpha=0.7, color='red')
    ax3.axvline(x=mc_results['drawdown_stats']['mean'], color='b', linestyle='-', 
               label=f"Mean: {mc_results['drawdown_stats']['mean']:.2f}%")
    ax3.axvline(x=mc_results['drawdown_stats']['percentile_5'], color='g', linestyle='--', 
               label=f"5%: {mc_results['drawdown_stats']['percentile_5']:.2f}%")
    
    ax3.set_title('Maximum Drawdown Distribution')
    ax3.set_xlabel('Maximum Drawdown (%)')
    ax3.set_ylabel('Frequency')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Add text with key statistics
    fig.text(0.02, 0.02, 
            f"Probability of Profit: {mc_results['probability_of_profit']:.1f}%\n"
            f"Expected Final Equity: {mc_results['final_stats']['mean']:.2f} ± {mc_results['final_stats']['std']:.2f}\n"
            f"Expected Max Drawdown: {mc_results['drawdown_stats']['mean']:.2f}% ± {mc_results['drawdown_stats']['std']:.2f}%",
            fontsize=10, bbox=dict(facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    fig.subplots_adjust(top=0.92)
    
    # Save plot if path provided
    if save_path:
        plt.savefig(save_path, dpi=100, bbox_inches='tight')
    
    return fig