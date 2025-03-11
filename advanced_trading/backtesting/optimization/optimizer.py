"""
Strategy Optimization Module
---------------------------
This module provides a comprehensive framework for optimizing trading strategy parameters
using various optimization techniques. It supports grid search, random search, Bayesian
optimization, and genetic algorithms.

The optimization process incorporates time series cross-validation to ensure robust
results and prevent overfitting. Performance metrics are calculated across multiple
validation periods to ensure the parameter sets generalize well.

Key features:
1. Multiple optimization techniques (grid search, random search, Bayesian, genetic)
2. Time series cross-validation integration
3. Parallel execution support for faster optimization
4. Robust performance metrics across market regimes
5. Visualization tools for optimization results
6. Parameter sensitivity analysis
"""

import time
import datetime
import itertools
import json
import os
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple, Callable, Optional, Union, Any, Type, Iterator

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from joblib import Parallel, delayed
from tqdm import tqdm
from skopt import BayesSearchCV
from skopt.space import Real, Integer, Categorical

# Import our modules
from advanced_trading.core.observability import get_logger
from advanced_trading.strategies.base import Strategy, StrategyConfig
from advanced_trading.utils.cross_validation.time_series_cv import TimeSeriesCV
from advanced_trading.backtesting.engine.backtest import Backtest, BacktestConfig, BacktestResult

# Initialize logger
logger = get_logger(__name__)


class OptimizationMetric(Enum):
    """Metrics that can be optimized during strategy parameter tuning."""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    ANNUAL_RETURN = "annual_return"
    MAX_DRAWDOWN = "max_drawdown"
    PROFIT_FACTOR = "profit_factor"
    EXPECTANCY = "expectancy"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"


class OptimizationMethod(Enum):
    """Optimization methods supported by the framework."""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"


@dataclass
class OptimizerConfig:
    """
    Configuration for the strategy optimizer.
    
    Attributes:
        parameter_space: Dictionary defining the parameter space to search
        optimization_metric: Metric to optimize (from OptimizationMetric enum)
        optimization_method: Method to use for optimization (from OptimizationMethod enum)
        cross_validation: Time series cross-validation settings
        maximize: Whether to maximize or minimize the metric
        n_iterations: Number of iterations (for methods that use iterations)
        n_jobs: Number of parallel jobs to run
        random_state: Random state for reproducibility
        additional_constraints: Additional constraints on parameter combinations
    """
    parameter_space: Dict[str, Union[List, Tuple]]
    optimization_metric: OptimizationMetric = OptimizationMetric.SHARPE_RATIO
    optimization_method: OptimizationMethod = OptimizationMethod.GRID_SEARCH
    cross_validation: Optional[Dict[str, Any]] = None
    maximize: bool = True
    n_iterations: int = 10
    n_jobs: int = 1
    random_state: Optional[int] = None
    additional_constraints: Optional[Callable[[Dict[str, Any]], bool]] = None


@dataclass
class OptimizationResult:
    """
    Results of a strategy optimization.
    
    Attributes:
        best_parameters: Best parameter set found during optimization
        all_results: All parameter sets and their performance metrics
        best_score: Best score achieved (according to optimization_metric)
        cv_results: Cross-validation results for each parameter set
        optimization_time: Time taken for optimization (in seconds)
        config: Configuration used for optimization
        parameter_importance: Importance of each parameter in determining performance
        sensitivity_analysis: Sensitivity of performance to parameter changes
    """
    best_parameters: Dict[str, Any]
    all_results: pd.DataFrame
    best_score: float
    cv_results: Dict[str, List[float]]
    optimization_time: float
    config: OptimizerConfig
    parameter_importance: Optional[Dict[str, float]] = None
    sensitivity_analysis: Optional[Dict[str, pd.DataFrame]] = None


class OptimizationCallback(ABC):
    """Base class for optimization callbacks."""
    
    @abstractmethod
    def on_optimization_start(self, config: OptimizerConfig) -> None:
        """Called when optimization starts."""
        pass
    
    @abstractmethod
    def on_iteration_complete(self, iteration: int, parameters: Dict[str, Any], 
                             score: float, best_score: float) -> None:
        """Called when an iteration completes."""
        pass
    
    @abstractmethod
    def on_optimization_end(self, result: OptimizationResult) -> None:
        """Called when optimization ends."""
        pass


class ProgressCallback(OptimizationCallback):
    """Callback that displays optimization progress."""
    
    def __init__(self, display_interval: int = 1):
        """Initialize the callback."""
        self.display_interval = display_interval
        self.start_time = None
    
    def on_optimization_start(self, config: OptimizerConfig) -> None:
        """Called when optimization starts."""
        self.start_time = time.time()
        parameter_space_size = self._calculate_space_size(config)
        logger.info(f"Starting optimization with {parameter_space_size} parameter combinations")
        logger.info(f"Optimization method: {config.optimization_method.value}")
        logger.info(f"Optimization metric: {config.optimization_metric.value}")
        logger.info(f"Using {config.n_jobs} parallel jobs")
    
    def on_iteration_complete(self, iteration: int, parameters: Dict[str, Any], 
                             score: float, best_score: float) -> None:
        """Called when an iteration completes."""
        if iteration % self.display_interval == 0:
            elapsed = time.time() - self.start_time
            logger.info(f"Iteration {iteration} - Score: {score:.4f} - Best: {best_score:.4f} - "
                       f"Time: {elapsed:.1f}s")
    
    def on_optimization_end(self, result: OptimizationResult) -> None:
        """Called when optimization ends."""
        logger.info(f"Optimization complete - Best score: {result.best_score:.4f}")
        logger.info(f"Best parameters: {result.best_parameters}")
        logger.info(f"Total time: {result.optimization_time:.1f}s")
    
    def _calculate_space_size(self, config: OptimizerConfig) -> int:
        """Calculate the size of the parameter space."""
        if config.optimization_method == OptimizationMethod.GRID_SEARCH:
            space_size = 1
            for param_values in config.parameter_space.values():
                space_size *= len(param_values)
            return space_size
        else:
            return config.n_iterations


class StrategyOptimizer:
    """
    Optimizer for trading strategies.
    
    This class provides methods for optimizing trading strategy parameters using
    various optimization techniques. It integrates with time series cross-validation
    to ensure robust results.
    
    Attributes:
        config: Configuration for the optimizer
        strategy_class: Strategy class to optimize
        base_config: Base configuration for the strategy
        callbacks: Callbacks for the optimization process
    """
    
    def __init__(self, 
                config: OptimizerConfig,
                strategy_class: Type[Strategy],
                base_config: StrategyConfig,
                market_data: Dict[str, pd.DataFrame],
                callbacks: Optional[List[OptimizationCallback]] = None):
        """
        Initialize the strategy optimizer.
        
        Args:
            config: Configuration for the optimizer
            strategy_class: Strategy class to optimize
            base_config: Base configuration for the strategy
            market_data: Market data for backtesting (dict of DataFrames by symbol)
            callbacks: Optional callbacks for the optimization process
        """
        self.config = config
        self.strategy_class = strategy_class
        self.base_config = base_config
        self.market_data = market_data
        self.callbacks = callbacks or [ProgressCallback()]
        
        self._optimization_start_time = None
        self._best_score = float('-inf') if config.maximize else float('inf')
        self._best_parameters = None
        self._all_results = []
        self._cv_results = {}
        
        # Initialize cross-validation if needed
        self._initialize_cv()
    
    def _initialize_cv(self) -> None:
        """Initialize cross-validation."""
        if self.config.cross_validation is None:
            # Default cross-validation settings
            self.config.cross_validation = {
                'cv_method': 'sliding',
                'n_splits': 5,
                'train_size': 0.7,
                'test_size': 0.2,
                'step_size': 0.05,
                'purge_size': 0.05,
                'embargo_size': 0.05
            }
        
        # Create TimeSeriesCV instance
        self.cv = TimeSeriesCV(**self.config.cross_validation)
    
    def optimize(self) -> OptimizationResult:
        """
        Optimize strategy parameters.
        
        Returns:
            OptimizationResult: The results of the optimization.
        """
        self._optimization_start_time = time.time()
        
        # Notify callbacks
        for callback in self.callbacks:
            callback.on_optimization_start(self.config)
        
        # Run optimization based on method
        if self.config.optimization_method == OptimizationMethod.GRID_SEARCH:
            self._run_grid_search()
        elif self.config.optimization_method == OptimizationMethod.RANDOM_SEARCH:
            self._run_random_search()
        elif self.config.optimization_method == OptimizationMethod.BAYESIAN:
            self._run_bayesian_optimization()
        elif self.config.optimization_method == OptimizationMethod.GENETIC:
            self._run_genetic_algorithm()
        else:
            raise ValueError(f"Unsupported optimization method: {self.config.optimization_method}")
        
        # Calculate optimization time
        optimization_time = time.time() - self._optimization_start_time
        
        # Create result DataFrame
        all_results = pd.DataFrame(self._all_results)
        
        # Sort by score
        sort_ascending = not self.config.maximize
        if not all_results.empty:
            all_results = all_results.sort_values('score', ascending=sort_ascending)
        
        # Calculate parameter importance and sensitivity if enough data points
        parameter_importance = None
        sensitivity_analysis = None
        if len(all_results) >= 10:
            parameter_importance = self._calculate_parameter_importance(all_results)
            sensitivity_analysis = self._perform_sensitivity_analysis(all_results)
        
        # Create result object
        result = OptimizationResult(
            best_parameters=self._best_parameters,
            all_results=all_results,
            best_score=self._best_score,
            cv_results=self._cv_results,
            optimization_time=optimization_time,
            config=self.config,
            parameter_importance=parameter_importance,
            sensitivity_analysis=sensitivity_analysis
        )
        
        # Notify callbacks
        for callback in self.callbacks:
            callback.on_optimization_end(result)
        
        return result
    
    def _run_grid_search(self) -> None:
        """Run grid search optimization."""
        # Create parameter grid
        param_keys = list(self.config.parameter_space.keys())
        param_values = list(self.config.parameter_space.values())
        param_grid = list(itertools.product(*param_values))
        
        # Run evaluations in parallel
        results = Parallel(n_jobs=self.config.n_jobs)(
            delayed(self._evaluate_parameters)(dict(zip(param_keys, params)), i)
            for i, params in enumerate(param_grid)
        )
        
        # Process results
        for i, (params, score, cv_scores) in enumerate(results):
            self._update_best_result(params, score, cv_scores)
    
    def _run_random_search(self) -> None:
        """Run random search optimization."""
        # Set random seed
        if self.config.random_state is not None:
            np.random.seed(self.config.random_state)
        
        # Run iterations
        for i in range(self.config.n_iterations):
            # Sample random parameters
            params = self._sample_random_parameters()
            
            # Skip invalid parameter combinations
            if not self._is_valid_parameters(params):
                continue
            
            # Evaluate parameters
            score, cv_scores = self._evaluate_parameters_single(params, i)
            
            # Update best result
            self._update_best_result(params, score, cv_scores)
    
    def _run_bayesian_optimization(self) -> None:
        """Run Bayesian optimization."""
        # Convert parameter space to scikit-optimize format
        space = []
        for param_name, param_range in self.config.parameter_space.items():
            if isinstance(param_range[0], int):
                space.append(Integer(min(param_range), max(param_range), name=param_name))
            elif isinstance(param_range[0], float):
                space.append(Real(min(param_range), max(param_range), name=param_name))
            else:
                space.append(Categorical(param_range, name=param_name))
        
        # Define objective function
        def objective_func(params):
            param_dict = {p.name: params[i] for i, p in enumerate(space)}
            
            # Skip invalid parameter combinations
            if not self._is_valid_parameters(param_dict):
                return float('-inf') if self.config.maximize else float('inf')
            
            # Evaluate parameters
            iteration = len(self._all_results)
            score, cv_scores = self._evaluate_parameters_single(param_dict, iteration)
            
            # Update best result (this is just for tracking; skopt keeps its own best)
            self._update_best_result(param_dict, score, cv_scores)
            
            # Return negative score if maximizing (skopt minimizes)
            return -score if self.config.maximize else score
        
        # Run optimization
        from skopt import gp_minimize
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = gp_minimize(
                objective_func,
                space,
                n_calls=self.config.n_iterations,
                random_state=self.config.random_state,
                verbose=False,
                n_jobs=self.config.n_jobs
            )
        
        # Convert result back to parameter dictionary
        best_params = {p.name: result.x[i] for i, p in enumerate(space)}
        best_score = -result.fun if self.config.maximize else result.fun
        
        # Update best result (in case it wasn't caught during iterations)
        if ((self.config.maximize and best_score > self._best_score) or
            (not self.config.maximize and best_score < self._best_score)):
            self._best_score = best_score
            self._best_parameters = best_params
    
    def _run_genetic_algorithm(self) -> None:
        """Run genetic algorithm optimization."""
        try:
            from deap import base, creator, tools, algorithms
        except ImportError:
            logger.error("Genetic algorithm requires the DEAP package. Install with: pip install deap")
            raise ImportError("DEAP package is required for genetic algorithms")
        
        # Set random seed
        if self.config.random_state is not None:
            np.random.seed(self.config.random_state)
            random.seed(self.config.random_state)
        
        # Define fitness class (maximization or minimization)
        if hasattr(creator, "FitnessMax"):
            del creator.FitnessMax
        if hasattr(creator, "FitnessMin"):
            del creator.FitnessMin
        if hasattr(creator, "Individual"):
            del creator.Individual
        
        if self.config.maximize:
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
            creator.create("Individual", list, fitness=creator.FitnessMax)
        else:
            creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
            creator.create("Individual", list, fitness=creator.FitnessMin)
        
        # Create toolbox
        toolbox = base.Toolbox()
        
        # Register parameter generators
        param_keys = list(self.config.parameter_space.keys())
        
        # Define attribute generators based on parameter types
        for i, (param_name, param_range) in enumerate(self.config.parameter_space.items()):
            if isinstance(param_range[0], int):
                toolbox.register(f"attr_{i}", np.random.randint, 
                               low=min(param_range), high=max(param_range) + 1)
            elif isinstance(param_range[0], float):
                toolbox.register(f"attr_{i}", np.random.uniform, 
                               low=min(param_range), high=max(param_range))
            else:
                toolbox.register(f"attr_{i}", np.random.choice, a=param_range)
        
        # Register individual and population creation
        toolbox.register("individual", tools.initCycle, creator.Individual,
                       (getattr(toolbox, f"attr_{i}") for i in range(len(param_keys))), n=1)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        
        # Define evaluation function
        def evaluate_individual(individual):
            params = dict(zip(param_keys, individual))
            
            # Skip invalid parameter combinations
            if not self._is_valid_parameters(params):
                return (-float('inf'),) if self.config.maximize else (float('inf'),)
            
            # Evaluate parameters
            iteration = len(self._all_results)
            score, cv_scores = self._evaluate_parameters_single(params, iteration)
            
            # Update best result
            self._update_best_result(params, score, cv_scores)
            
            return (score,)
        
        # Register genetic operators
        toolbox.register("evaluate", evaluate_individual)
        toolbox.register("mate", tools.cxBlend, alpha=0.5)
        toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1, indpb=0.2)
        toolbox.register("select", tools.selTournament, tournsize=3)
        
        # Create initial population
        population = toolbox.population(n=min(50, self.config.n_iterations))
        
        # Define statistics
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("min", np.min)
        stats.register("max", np.max)
        
        # Run genetic algorithm
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            population, logbook = algorithms.eaSimple(
                population, toolbox, cxpb=0.5, mutpb=0.2,
                ngen=max(10, self.config.n_iterations // 5),
                stats=stats, verbose=False
            )
        
        # Get best individual
        best_ind = tools.selBest(population, 1)[0]
        best_params = dict(zip(param_keys, best_ind))
        
        # Ensure best parameters are recorded
        if self._best_parameters is None:
            self._best_parameters = best_params
    
    def _sample_random_parameters(self) -> Dict[str, Any]:
        """Sample random parameters from the parameter space."""
        params = {}
        for param_name, param_range in self.config.parameter_space.items():
            if isinstance(param_range[0], int):
                params[param_name] = np.random.randint(min(param_range), max(param_range) + 1)
            elif isinstance(param_range[0], float):
                params[param_name] = np.random.uniform(min(param_range), max(param_range))
            else:
                params[param_name] = np.random.choice(param_range)
        return params
    
    def _is_valid_parameters(self, params: Dict[str, Any]) -> bool:
        """Check if parameter combination is valid."""
        if self.config.additional_constraints is None:
            return True
        return self.config.additional_constraints(params)
    
    def _evaluate_parameters(self, params: Dict[str, Any], iteration: int) -> Tuple[Dict[str, Any], float, List[float]]:
        """Evaluate parameters using cross-validation."""
        score, cv_scores = self._evaluate_parameters_single(params, iteration)
        return params, score, cv_scores
    
    def _evaluate_parameters_single(self, params: Dict[str, Any], iteration: int) -> Tuple[float, List[float]]:
        """Evaluate a single parameter set."""
        # Get time series splits for cross-validation
        cv_scores = []
        
        first_key = next(iter(self.market_data.keys()))
        data = self.market_data[first_key]
        
        # Create a dummy array for time series CV (just need the length)
        dummy_array = np.arange(len(data))
        
        # Run cross-validation
        for train_idx, test_idx in self.cv.split(dummy_array):
            # Get train/test data for all symbols
            train_data = {}
            test_data = {}
            for symbol, df in self.market_data.items():
                train_data[symbol] = df.iloc[train_idx].copy()
                test_data[symbol] = df.iloc[test_idx].copy()
            
            # Create strategy with parameters
            strategy_config = self._create_strategy_config(params)
            
            # Create backtest config
            backtest_config = self._create_backtest_config(strategy_config, test_data)
            
            # Run backtest
            backtest = Backtest(backtest_config)
            backtest.setup()
            result = backtest.run()
            
            # Get score from result
            metric_name = self.config.optimization_metric.value
            score = result.performance_metrics.get(metric_name, float('-inf') if self.config.maximize else float('inf'))
            cv_scores.append(score)
        
        # Calculate final score as mean of CV scores
        if cv_scores:
            final_score = np.mean(cv_scores)
        else:
            final_score = float('-inf') if self.config.maximize else float('inf')
        
        # Add to all results
        result_entry = {**params, 'score': final_score, 'iteration': iteration}
        self._all_results.append(result_entry)
        
        # Save CV scores
        param_key = self._get_param_key(params)
        self._cv_results[param_key] = cv_scores
        
        # Notify callbacks
        for callback in self.callbacks:
            callback.on_iteration_complete(iteration, params, final_score, self._best_score)
        
        return final_score, cv_scores
    
    def _update_best_result(self, params: Dict[str, Any], score: float, cv_scores: List[float]) -> None:
        """Update best result if this score is better."""
        if (self.config.maximize and score > self._best_score) or (not self.config.maximize and score < self._best_score):
            self._best_score = score
            self._best_parameters = params.copy()
    
    def _create_strategy_config(self, params: Dict[str, Any]) -> StrategyConfig:
        """Create strategy config with parameters."""
        # Create a copy of base config
        config_dict = vars(self.base_config).copy()
        
        # Update with parameters
        # Note: This assumes that all parameters are direct attributes of StrategyConfig
        # If parameters are nested, this will need to be more complex
        for param_name, param_value in params.items():
            config_dict[param_name] = param_value
        
        # Create new config
        return StrategyConfig(**config_dict)
    
    def _create_backtest_config(self, strategy_config: StrategyConfig, 
                              test_data: Dict[str, pd.DataFrame]) -> BacktestConfig:
        """Create backtest config for evaluation."""
        # Get dates from test data
        first_symbol = next(iter(test_data.keys()))
        start_date = test_data[first_symbol].index[0]
        end_date = test_data[first_symbol].index[-1]
        
        # Create backtest config
        return BacktestConfig(
            name=f"optimization_{strategy_config.name}",
            strategy_config=strategy_config,
            start_date=start_date,
            end_date=end_date,
            symbols=list(test_data.keys()),
            initial_capital=100000.0,
            mode=BacktestMode.EVENT_DRIVEN,
            data_frequency="1d"  # This should be dynamic based on data
        )
    
    def _get_param_key(self, params: Dict[str, Any]) -> str:
        """Get unique key for parameter set."""
        return json.dumps(params, sort_keys=True)
    
    def _calculate_parameter_importance(self, results: pd.DataFrame) -> Dict[str, float]:
        """Calculate parameter importance by correlation with score."""
        importance = {}
        param_columns = [col for col in results.columns if col not in ['score', 'iteration']]
        
        for param in param_columns:
            # Skip if parameter has only one unique value
            if results[param].nunique() <= 1:
                importance[param] = 0.0
                continue
            
            # Calculate correlation with score
            if results[param].dtype in [np.int64, np.float64]:
                corr = np.abs(results[param].corr(results['score']))
                if np.isnan(corr):
                    corr = 0.0
            else:
                # For categorical parameters, use ANOVA
                from scipy import stats
                groups = []
                for val in results[param].unique():
                    groups.append(results[results[param] == val]['score'].values)
                
                if len(groups) <= 1 or any(len(g) <= 1 for g in groups):
                    corr = 0.0
                else:
                    try:
                        f_val, p_val = stats.f_oneway(*groups)
                        corr = 1.0 - p_val  # Higher importance for lower p-values
                    except:
                        corr = 0.0
            
            importance[param] = corr
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}
        
        return importance
    
    def _perform_sensitivity_analysis(self, results: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Perform sensitivity analysis for each parameter."""
        sensitivity = {}
        param_columns = [col for col in results.columns if col not in ['score', 'iteration']]
        
        for param in param_columns:
            # Skip if parameter has only one unique value
            if results[param].nunique() <= 1:
                continue
            
            # Group by parameter value and calculate score statistics
            if results[param].dtype in [np.int64, np.float64]:
                # For numerical parameters, create bins
                try:
                    bins = min(10, results[param].nunique())
                    grouped = results.groupby(pd.cut(results[param], bins=bins))
                except:
                    # Fallback to exact values if binning fails
                    grouped = results.groupby(param)
            else:
                # For categorical parameters, group by exact values
                grouped = results.groupby(param)
            
            # Calculate statistics
            stats = grouped['score'].agg(['mean', 'std', 'count', 'min', 'max'])
            sensitivity[param] = stats
        
        return sensitivity
    
    def plot_optimization_results(self, result: OptimizationResult = None,
                                figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Plot optimization results.
        
        Args:
            result: OptimizationResult to plot (uses last result if None)
            figsize: Figure size
            
        Returns:
            Figure with optimization results
        """
        if result is None:
            if self._all_results:
                all_results = pd.DataFrame(self._all_results)
            else:
                logger.warning("No optimization results to plot")
                return None
        else:
            all_results = result.all_results
        
        if all_results.empty:
            logger.warning("Empty results DataFrame")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # Plot 1: Score over iterations
        ax1 = axes[0, 0]
        if 'iteration' in all_results.columns:
            all_results.plot(x='iteration', y='score', kind='scatter', ax=ax1)
            ax1.set_title('Score Over Iterations')
            ax1.set_xlabel('Iteration')
            ax1.set_ylabel('Score')
        
        # Plot 2: Parameter importance
        ax2 = axes[0, 1]
        if result and result.parameter_importance:
            importance_df = pd.Series(result.parameter_importance).sort_values(ascending=False)
            importance_df.plot(kind='bar', ax=ax2)
            ax2.set_title('Parameter Importance')
            ax2.set_xlabel('Parameter')
            ax2.set_ylabel('Importance')
            plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
        
        # Plot 3: Distribution of scores
        ax3 = axes[1, 0]
        all_results['score'].plot(kind='hist', bins=20, ax=ax3)
        ax3.set_title('Distribution of Scores')
        ax3.set_xlabel('Score')
        ax3.set_ylabel('Count')
        
        # Plot 4: Top parameters vs. score
        ax4 = axes[1, 1]
        if result and result.parameter_importance:
            top_param = max(result.parameter_importance.items(), key=lambda x: x[1])[0]
            if all_results[top_param].dtype in [np.int64, np.float64]:
                all_results.plot(x=top_param, y='score', kind='scatter', ax=ax4)
                ax4.set_title(f'Score vs. {top_param}')
                ax4.set_xlabel(top_param)
                ax4.set_ylabel('Score')
        
        plt.tight_layout()
        return fig
    
    def plot_parameter_surface(self, result: OptimizationResult = None,
                             param1: str = None, param2: str = None,
                             figsize: Tuple[int, int] = (10, 8)) -> plt.Figure:
        """
        Plot parameter surface for two parameters.
        
        Args:
            result: OptimizationResult to plot (uses last result if None)
            param1: First parameter to plot (x-axis)
            param2: Second parameter to plot (y-axis)
            figsize: Figure size
            
        Returns:
            Figure with parameter surface plot
        """
        if result is None:
            if self._all_results:
                all_results = pd.DataFrame(self._all_results)
            else:
                logger.warning("No optimization results to plot")
                return None
        else:
            all_results = result.all_results
        
        if all_results.empty:
            logger.warning("Empty results DataFrame")
            return None
        
        # If params not specified, use top two important parameters
        if param1 is None or param2 is None:
            if result and result.parameter_importance:
                importance = list(result.parameter_importance.items())
                importance.sort(key=lambda x: x[1], reverse=True)
                
                if len(importance) >= 2:
                    if param1 is None:
                        param1 = importance[0][0]
                    if param2 is None:
                        param2 = importance[1][0]
                else:
                    logger.warning("Not enough parameters with importance data")
                    return None
            else:
                # Just use first two numeric parameters
                numeric_params = [col for col in all_results.columns 
                                if col not in ['score', 'iteration'] 
                                and all_results[col].dtype in [np.int64, np.float64]]
                
                if len(numeric_params) >= 2:
                    param1 = numeric_params[0]
                    param2 = numeric_params[1]
                else:
                    logger.warning("Not enough numeric parameters to plot")
                    return None
        
        # Check if parameters are numeric
        if all_results[param1].dtype not in [np.int64, np.float64] or all_results[param2].dtype not in [np.int64, np.float64]:
            logger.warning("Both parameters must be numeric for surface plot")
            return None
        
        # Create 3D plot
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot scatter points
        sc = ax.scatter(all_results[param1], all_results[param2], all_results['score'],
                      c=all_results['score'], cmap='viridis', alpha=0.8)
        
        # Add colorbar
        plt.colorbar(sc, ax=ax, label='Score')
        
        # Set labels
        ax.set_xlabel(param1)
        ax.set_ylabel(param2)
        ax.set_zlabel('Score')
        ax.set_title(f'Parameter Surface: {param1} vs {param2}')
        
        return fig
    
    def save_results(self, result: OptimizationResult, path: str) -> None:
        """
        Save optimization results to disk.
        
        Args:
            result: OptimizationResult to save
            path: Path to save to
        """
        # Create directory if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Serialize results
        serialized = {
            'best_parameters': result.best_parameters,
            'best_score': result.best_score,
            'optimization_time': result.optimization_time,
            'config': {
                'parameter_space': result.config.parameter_space,
                'optimization_metric': result.config.optimization_metric.value,
                'optimization_method': result.config.optimization_method.value,
                'cross_validation': result.config.cross_validation,
                'maximize': result.config.maximize,
                'n_iterations': result.config.n_iterations,
                'n_jobs': result.config.n_jobs,
                'random_state': result.config.random_state
            },
            'parameter_importance': result.parameter_importance,
            # Can't easily serialize sensitivity analysis DataFrames
            'all_results': result.all_results.to_dict(orient='records'),
            'cv_results': result.cv_results
        }
        
        # Save to file
        with open(path, 'w') as f:
            json.dump(serialized, f, indent=2)
        
        logger.info(f"Optimization results saved to {path}")
    
    @classmethod
    def load_results(cls, path: str) -> OptimizationResult:
        """
        Load optimization results from disk.
        
        Args:
            path: Path to load from
            
        Returns:
            OptimizationResult: Loaded results
        """
        # Load from file
        with open(path, 'r') as f:
            serialized = json.load(f)
        
        # Recreate config
        config = OptimizerConfig(
            parameter_space=serialized['config']['parameter_space'],
            optimization_metric=OptimizationMetric(serialized['config']['optimization_metric']),
            optimization_method=OptimizationMethod(serialized['config']['optimization_method']),
            cross_validation=serialized['config']['cross_validation'],
            maximize=serialized['config']['maximize'],
            n_iterations=serialized['config']['n_iterations'],
            n_jobs=serialized['config']['n_jobs'],
            random_state=serialized['config']['random_state']
        )
        
        # Recreate result
        return OptimizationResult(
            best_parameters=serialized['best_parameters'],
            all_results=pd.DataFrame(serialized['all_results']),
            best_score=serialized['best_score'],
            cv_results=serialized['cv_results'],
            optimization_time=serialized['optimization_time'],
            config=config,
            parameter_importance=serialized['parameter_importance'],
            sensitivity_analysis=None  # Can't easily deserialize DataFrames
        ) 