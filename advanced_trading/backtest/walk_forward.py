"""
Walk-Forward Testing Framework
-----------------------------
This module provides functionality for performing walk-forward optimization and testing
of trading strategies, ensuring proper temporal validation and mitigating overfitting.

The walk-forward testing methodology divides historical data into multiple testing periods,
each preceded by a training period. For each testing period, the strategy is optimized on
the corresponding training data and then tested on the out-of-sample testing data.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Callable, Union, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import json
import pickle
from tqdm import tqdm

# Configure logging
logger = logging.getLogger(__name__)

class WalkForwardTest:
    """
    Walk-Forward Testing Framework for systematic evaluation of trading strategies.
    
    This class implements walk-forward testing with multiple methods of data segmentation,
    optimization procedures, and performance evaluation. It helps to rigorously evaluate 
    trading strategies while mitigating overfitting risks.
    
    Parameters:
    -----------
    market_data : Dict[str, pd.DataFrame] or pd.DataFrame
        Dictionary of DataFrames with historical market data, keyed by symbol, or a single DataFrame
    train_size : int or float
        Size of training window (periods if int, fraction if float)
    test_size : int or float
        Size of testing window (periods if int, fraction if float)
    step_size : int
        Number of periods to advance between walk-forward iterations
    optimization_func : Callable
        Function to optimize strategy parameters on training data
    initial_capital : float, optional
        Initial capital for backtesting, default 10000
    commission : float, optional
        Commission rate as a fraction, default 0.001 (0.1%)
    slippage : float, optional
        Slippage as a fraction, default 0.0005 (0.05%)
    leverage : float, optional
        Maximum leverage allowed, default 1.0 (no leverage)
    """
    
    def __init__(
        self,
        market_data: Union[Dict[str, pd.DataFrame], pd.DataFrame],
        train_size: Union[int, float],
        test_size: Union[int, float],
        step_size: int,
        optimization_func: Callable,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
        leverage: float = 1.0,
        output_dir: str = 'results',
    ):
        # Store market data and convert single DataFrame to dict if needed
        if isinstance(market_data, pd.DataFrame):
            self.market_data = {'default': market_data.copy()}
        else:
            self.market_data = market_data.copy()
            
        # Validate that all DataFrames have the same index
        self._validate_data_indices()
        
        # Store parameters
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
        self.optimization_func = optimization_func
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.leverage = leverage
        
        # Internal state
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = {}
        self.periods = []
        self.optimized_params = []
        self.equity_curves = []
        self.metrics_by_period = []
        
    def _validate_data_indices(self):
        """Validate that all market data DataFrames have the same index."""
        if len(self.market_data) <= 1:
            return
            
        first_key = list(self.market_data.keys())[0]
        first_index = self.market_data[first_key].index
        
        for symbol, df in self.market_data.items():
            if not df.index.equals(first_index):
                raise ValueError(f"DataFrame for {symbol} has a different index than {first_key}")
    
    def _compute_walk_forward_periods(self) -> List[Tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
        """
        Compute walk-forward periods based on data and configuration.
        
        Returns:
        --------
        List[Tuple[pd.DatetimeIndex, pd.DatetimeIndex]]
            List of (train_idx, test_idx) tuples for each walk-forward period
        """
        # Get reference DataFrame for index calculations
        ref_symbol = list(self.market_data.keys())[0]
        ref_df = self.market_data[ref_symbol]
        
        # Calculate train and test sizes in terms of index positions
        total_periods = len(ref_df)
        
        if isinstance(self.train_size, float):
            train_periods = int(total_periods * self.train_size)
        else:
            train_periods = self.train_size
            
        if isinstance(self.test_size, float):
            test_periods = int(total_periods * self.test_size)
        else:
            test_periods = self.test_size
        
        # Calculate the number of walk-forward iterations
        max_start_idx = total_periods - train_periods - test_periods
        iterations = max(1, 1 + (max_start_idx // self.step_size))
        
        # Generate periods
        periods = []
        for i in range(iterations):
            start_idx = i * self.step_size
            train_end_idx = start_idx + train_periods
            test_end_idx = min(train_end_idx + test_periods, total_periods)
            
            # Get indices for train and test periods
            train_idx = ref_df.index[start_idx:train_end_idx]
            test_idx = ref_df.index[train_end_idx:test_end_idx]
            
            # Only add if we have valid train and test periods
            if len(train_idx) > 0 and len(test_idx) > 0:
                periods.append((train_idx, test_idx))
        
        return periods
    
    def _train_test_split(self, period: Tuple[pd.DatetimeIndex, pd.DatetimeIndex]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """
        Split market data into training and testing sets for a specific period.
        
        Parameters:
        -----------
        period : Tuple[pd.DatetimeIndex, pd.DatetimeIndex]
            Tuple of (train_idx, test_idx) for the current period
            
        Returns:
        --------
        Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]
            Train and test market data dictionaries
        """
        train_idx, test_idx = period
        
        train_data = {}
        test_data = {}
        
        for symbol, df in self.market_data.items():
            train_data[symbol] = df.loc[train_idx].copy()
            test_data[symbol] = df.loc[test_idx].copy()
        
        return train_data, test_data
    
    def run(self, strategy_factory: Callable, verbose: bool = True) -> Dict:
        """
        Run walk-forward testing.
        
        Parameters:
        -----------
        strategy_factory : Callable
            Function that creates a strategy instance given parameters
        verbose : bool, optional
            Whether to display progress information, default True
            
        Returns:
        --------
        Dict
            Walk-forward testing results
        """
        # Compute walk-forward periods
        self.periods = self._compute_walk_forward_periods()
        if verbose:
            logger.info(f"Generated {len(self.periods)} walk-forward periods")
        
        # Initialize result containers
        self.optimized_params = []
        self.equity_curves = []
        self.metrics_by_period = []
        
        # Iterate through periods
        iterator = tqdm(self.periods) if verbose else self.periods
        for i, period in enumerate(iterator):
            if verbose:
                train_start = period[0][0]
                train_end = period[0][-1]
                test_start = period[1][0]
                test_end = period[1][-1]
                logger.info(f"Period {i+1}: Train {train_start} to {train_end}, Test {test_start} to {test_end}")
            
            # Split data for the current period
            train_data, test_data = self._train_test_split(period)
            
            # Optimize strategy on training data
            if verbose:
                logger.info(f"Optimizing strategy for period {i+1}...")
            
            optimal_params = self.optimization_func(train_data, self.initial_capital, self.commission)
            self.optimized_params.append(optimal_params)
            
            # Create strategy with optimal parameters
            strategy = strategy_factory(**optimal_params)
            
            # Run backtest on test data
            if verbose:
                logger.info(f"Backtesting strategy on test period {i+1}...")
            
            from advanced_trading.backtest.engine import run_backtest
            
            # Run backtest on test data
            backtest_results = run_backtest(
                strategy=strategy,
                market_data=test_data,
                initial_capital=self.initial_capital,
                commission=self.commission,
                slippage=self.slippage,
                leverage=self.leverage
            )
            
            # Store results
            self.equity_curves.append(backtest_results['equity_curve'])
            self.metrics_by_period.append(backtest_results['metrics'])
        
        # Combine results across all periods
        self._combine_results()
        
        return self.results
    
    def _combine_results(self):
        """Combine results from all walk-forward periods into a single results dictionary."""
        # Combine equity curves
        combined_equity = pd.concat(self.equity_curves)
        
        # Calculate overall performance metrics
        from advanced_trading.backtest.performance import calculate_performance_metrics
        
        overall_metrics = calculate_performance_metrics(combined_equity)
        
        # Store results
        self.results = {
            'equity_curve': combined_equity,
            'overall_metrics': overall_metrics,
            'metrics_by_period': self.metrics_by_period,
            'optimized_params': self.optimized_params,
            'periods': [(p[0][0], p[0][-1], p[1][0], p[1][-1]) for p in self.periods]
        }
        
    def plot_results(self, title: str = 'Walk-Forward Test Results', save_path: Optional[str] = None):
        """
        Plot walk-forward test results.
        
        Parameters:
        -----------
        title : str, optional
            Plot title, default 'Walk-Forward Test Results'
        save_path : str, optional
            Path to save the plot, if None then plot is displayed, default None
        """
        if not self.results:
            logger.warning("No results to plot. Run the walk-forward test first.")
            return
        
        # Create figure and axes
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot equity curve on top subplot
        self.results['equity_curve'].plot(ax=ax1)
        ax1.set_title(title)
        ax1.set_ylabel('Equity')
        ax1.grid(True)
        
        # Plot drawdowns on bottom subplot
        drawdowns = (self.results['equity_curve'] / self.results['equity_curve'].cummax() - 1) * 100
        drawdowns.plot(ax=ax2, color='red')
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_xlabel('Date')
        ax2.grid(True)
        
        # Add period markers
        for i, period in enumerate(self.periods):
            # Extract test period
            test_start = period[1][0]
            test_end = period[1][-1]
            
            # Add vertical lines for period boundaries
            ax1.axvline(test_start, color='green', linestyle='--', alpha=0.6)
            ax1.axvline(test_end, color='red', linestyle='--', alpha=0.6)
            
            # Add period number text
            mid_point = test_start + (test_end - test_start) / 2
            ax1.text(mid_point, ax1.get_ylim()[1] * 0.95, f"P{i+1}", 
                    horizontalalignment='center', verticalalignment='top')
        
        # Add overall metrics as text box
        metrics = self.results['overall_metrics']
        metrics_text = (
            f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}\n"
            f"Sortino Ratio: {metrics['sortino_ratio']:.2f}\n"
            f"CAGR: {metrics['cagr']:.2%}\n"
            f"Max Drawdown: {metrics['max_drawdown']:.2%}\n"
            f"Win Rate: {metrics['win_rate']:.2%}\n"
            f"Profit Factor: {metrics['profit_factor']:.2f}"
        )
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax1.text(0.02, 0.98, metrics_text, transform=ax1.transAxes, fontsize=10,
                verticalalignment='top', bbox=props)
        
        plt.tight_layout()
        
        # Save or display plot
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()
    
    def save_results(self, filename: str):
        """
        Save walk-forward test results to file.
        
        Parameters:
        -----------
        filename : str
            Filename to save results to (without extension)
        """
        if not self.results:
            logger.warning("No results to save. Run the walk-forward test first.")
            return
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save results as JSON
        json_path = self.output_dir / f"{filename}.json"
        
        # Convert DataFrame and other complex types to serializable format
        serializable_results = {
            'overall_metrics': self.results['overall_metrics'],
            'metrics_by_period': self.results['metrics_by_period'],
            'optimized_params': self.results['optimized_params'],
            'periods': [(str(p[0]), str(p[1]), str(p[2]), str(p[3])) for p in self.results['periods']]
        }
        
        with open(json_path, 'w') as f:
            json.dump(serializable_results, f, indent=4)
        
        # Save equity curve as CSV
        csv_path = self.output_dir / f"{filename}_equity.csv"
        self.results['equity_curve'].to_csv(csv_path)
        
        # Save complete results (including DataFrames) as pickle
        pickle_path = self.output_dir / f"{filename}.pkl"
        with open(pickle_path, 'wb') as f:
            pickle.dump(self.results, f)
        
        logger.info(f"Results saved to {json_path}, {csv_path} and {pickle_path}")
    
    def load_results(self, filename: str):
        """
        Load walk-forward test results from file.
        
        Parameters:
        -----------
        filename : str
            Filename to load results from (without extension)
        """
        pickle_path = self.output_dir / f"{filename}.pkl"
        
        if not pickle_path.exists():
            raise FileNotFoundError(f"Results file not found: {pickle_path}")
        
        with open(pickle_path, 'rb') as f:
            self.results = pickle.load(f)
        
        logger.info(f"Results loaded from {pickle_path}")
        
        return self.results


class MLWalkForwardAnalysis(WalkForwardTest):
    """
    Walk-Forward Analysis specialized for ML-based trading strategies.
    
    This class extends WalkForwardTest with specialized functionality for 
    ML model training, feature importance analysis, and model performance
    evaluation across different market regimes.
    
    Parameters:
    -----------
    Same as WalkForwardTest, plus:
    feature_engineer : object, optional
        Feature engineering object with fit_transform and transform methods
    feature_importance_func : Callable, optional
        Function to calculate feature importance from trained models
    regime_detection_func : Callable, optional
        Function to detect market regimes in time series data
    """
    
    def __init__(
        self,
        market_data: Union[Dict[str, pd.DataFrame], pd.DataFrame],
        train_size: Union[int, float],
        test_size: Union[int, float],
        step_size: int,
        optimization_func: Callable,
        feature_engineer=None,
        feature_importance_func: Optional[Callable]=None,
        regime_detection_func: Optional[Callable]=None,
        **kwargs
    ):
        super().__init__(
            market_data=market_data,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            optimization_func=optimization_func,
            **kwargs
        )
        
        self.feature_engineer = feature_engineer
        self.feature_importance_func = feature_importance_func
        self.regime_detection_func = regime_detection_func
        
        # Additional result storage
        self.feature_importances = []
        self.regime_distributions = []
        self.model_performances = []
    
    def run(self, strategy_factory: Callable, verbose: bool = True) -> Dict:
        """
        Run ML walk-forward analysis.
        
        Parameters:
        -----------
        strategy_factory : Callable
            Function that creates a strategy instance given parameters
        verbose : bool, optional
            Whether to display progress information, default True
            
        Returns:
        --------
        Dict
            Walk-forward analysis results
        """
        # Reset result containers
        self.feature_importances = []
        self.regime_distributions = []
        self.model_performances = []
        
        # Run standard walk-forward test
        results = super().run(strategy_factory, verbose)
        
        # Analyze feature importance if function provided
        if self.feature_importance_func and hasattr(self.optimized_params[0], 'model'):
            for i, params in enumerate(self.optimized_params):
                if hasattr(params, 'model'):
                    importance = self.feature_importance_func(params.model)
                    self.feature_importances.append(importance)
        
        # Analyze regimes if function provided
        if self.regime_detection_func:
            ref_symbol = list(self.market_data.keys())[0]
            for i, period in enumerate(self.periods):
                _, test_idx = period
                test_data = self.market_data[ref_symbol].loc[test_idx]
                
                # Detect regimes in test period
                regimes = self.regime_detection_func(test_data['close'])
                regime_dist = pd.Series(regimes).value_counts(normalize=True).to_dict()
                self.regime_distributions.append(regime_dist)
                
                # Analyze model performance by regime
                if i < len(self.equity_curves):
                    equity = self.equity_curves[i]
                    performance_by_regime = {}
                    
                    # Calculate returns
                    returns = equity.pct_change().dropna()
                    
                    # Group by regime and calculate performance
                    for regime in set(regimes):
                        regime_returns = returns[regimes == regime]
                        if len(regime_returns) > 0:
                            from advanced_trading.backtest.performance import calculate_performance_metrics
                            metrics = calculate_performance_metrics(regime_returns.cumsum())
                            performance_by_regime[regime] = metrics
                    
                    self.model_performances.append(performance_by_regime)
        
        # Add additional analysis to results
        results['feature_importances'] = self.feature_importances
        results['regime_distributions'] = self.regime_distributions
        results['model_performances_by_regime'] = self.model_performances
        
        return results
    
    def plot_feature_importance(self, top_n: int = 20, save_path: Optional[str] = None):
        """
        Plot feature importance across walk-forward periods.
        
        Parameters:
        -----------
        top_n : int, optional
            Number of top features to plot, default 20
        save_path : str, optional
            Path to save the plot, if None then plot is displayed, default None
        """
        if not self.feature_importances:
            logger.warning("No feature importance data available.")
            return
        
        # Combine feature importances across periods
        all_importances = pd.concat(self.feature_importances, axis=1)
        
        # Calculate mean importance across periods
        mean_importance = all_importances.mean(axis=1).sort_values(ascending=False)
        
        # Select top N features
        top_features = mean_importance.head(top_n)
        
        # Create figure
        plt.figure(figsize=(12, 8))
        top_features.plot(kind='barh')
        plt.title(f'Top {top_n} Feature Importance (Mean Across Periods)')
        plt.xlabel('Importance')
        plt.ylabel('Feature')
        plt.grid(True, axis='x')
        plt.tight_layout()
        
        # Save or display plot
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()
    
    def plot_regime_performance(self, save_path: Optional[str] = None):
        """
        Plot model performance by market regime.
        
        Parameters:
        -----------
        save_path : str, optional
            Path to save the plot, if None then plot is displayed, default None
        """
        if not self.model_performances:
            logger.warning("No regime performance data available.")
            return
        
        # Collect metrics by regime
        regimes = set()
        for perf in self.model_performances:
            regimes.update(perf.keys())
        
        metrics = ['sharpe_ratio', 'sortino_ratio', 'cagr', 'max_drawdown', 'win_rate']
        data = {regime: {metric: [] for metric in metrics} for regime in regimes}
        
        for perf in self.model_performances:
            for regime in regimes:
                if regime in perf:
                    for metric in metrics:
                        if metric in perf[regime]:
                            data[regime][metric].append(perf[regime][metric])
        
        # Calculate mean metrics by regime
        mean_data = {regime: {metric: np.mean(values) for metric, values in regime_data.items() if values}
                    for regime, regime_data in data.items()}
        
        # Create DataFrame for plotting
        df = pd.DataFrame(mean_data).T
        
        # Create figure
        fig, axes = plt.subplots(len(metrics), 1, figsize=(12, 4 * len(metrics)))
        
        for i, metric in enumerate(metrics):
            df[metric].plot(kind='bar', ax=axes[i])
            axes[i].set_title(f'{metric.replace("_", " ").title()} by Market Regime')
            axes[i].set_ylabel(metric.replace('_', ' ').title())
            axes[i].grid(True, axis='y')
        
        plt.tight_layout()
        
        # Save or display plot
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()


# Utility function to create walk-forward optimization for AdaptiveMetaStrategy with ML
def create_ml_adaptive_optimizer(
    ensemble_trainer_class,
    ensemble_trainer_params,
    target_symbol: str,
    strategy_params: Dict = None,
    n_trials: int = 20
) -> Callable:
    """
    Create optimization function for ML-based AdaptiveMetaStrategy.
    
    Parameters:
    -----------
    ensemble_trainer_class : class
        Class for ensemble model trainer
    ensemble_trainer_params : Dict
        Parameters for ensemble trainer
    target_symbol : str
        Target trading symbol
    strategy_params : Dict, optional
        Additional strategy parameters
    n_trials : int, optional
        Number of optimization trials
        
    Returns:
    --------
    Callable
        Optimization function that takes (train_data, initial_capital, commission)
    """
    from advanced_trading.models.ml_ensemble.adaptive_integration import AdaptiveMLStrategy
    import tempfile
    
    def optimizer(train_data, initial_capital, commission):
        # Create temporary directory for model storage
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize ensemble trainer
            trainer_params = ensemble_trainer_params.copy()
            trainer_params['data_dir'] = temp_dir
            trainer_params['output_dir'] = temp_dir
            
            trainer = ensemble_trainer_class(**trainer_params)
            
            # Get symbol data
            df = train_data[target_symbol]
            
            # Train ML ensemble
            ensemble = trainer.prepare_data(df, symbol=target_symbol)
            trainer.train_ensemble(use_predefined_models=True)
            
            # Save ensemble
            model_name = f"{target_symbol}_ensemble.joblib"
            model_path = Path(temp_dir) / model_name
            trainer.save_ensemble(model_name)
            
            # Initialize base strategy parameters
            base_params = {
                'symbol': target_symbol,
                'ensemble_path': str(model_path),
                'prediction_threshold': 0.55,  # Default threshold
                'confidence_scaling': True
            }
            
            # Add additional strategy parameters if provided
            if strategy_params:
                base_params.update(strategy_params)
            
            # Optimize key parameters
            import optuna
            
            def objective(trial):
                # Define parameters to optimize
                params = base_params.copy()
                
                # Adjust prediction threshold
                params['prediction_threshold'] = trial.suggest_float('prediction_threshold', 0.5, 0.7)
                
                # Create strategy
                ml_strategy = AdaptiveMLStrategy(**params)
                
                # Create meta-strategy
                from advanced_trading.strategies.adaptive_meta_strategy import AdaptiveMetaStrategy
                
                meta_strategy = AdaptiveMetaStrategy(
                    strategies={'ml_ensemble': ml_strategy},
                    base_allocations={'ml_ensemble': 1.0},
                    lookback_window=trial.suggest_int('lookback_window', 20, 120),
                    regime_memory=trial.suggest_int('regime_memory', 100, 500),
                    allocation_method='hrp',
                    max_allocation=1.0,
                    min_allocation=0.0
                )
                
                # Run backtest
                from advanced_trading.backtest.engine import run_backtest
                
                results = run_backtest(
                    strategy=meta_strategy,
                    market_data=train_data,
                    initial_capital=initial_capital,
                    commission=commission
                )
                
                # Optimization metric: risk-adjusted return (Sharpe ratio)
                return results['metrics']['sharpe_ratio']
            
            # Run optimization
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials)
            
            # Get best parameters
            best_params = study.best_params
            
            # Update base parameters with optimized values
            optimized_params = base_params.copy()
            optimized_params['prediction_threshold'] = best_params['prediction_threshold']
            
            # Create final strategy instance
            ml_strategy_final = AdaptiveMLStrategy(**optimized_params)
            
            # Return optimized parameters for final strategy creation
            return {
                'strategies': {'ml_ensemble': ml_strategy_final},
                'base_allocations': {'ml_ensemble': 1.0},
                'lookback_window': best_params['lookback_window'],
                'regime_memory': best_params['regime_memory'],
                'allocation_method': 'hrp',
                'max_allocation': 1.0,
                'min_allocation': 0.0
            }
    
    return optimizer


# Example usage:
"""
# Import necessary modules
from advanced_trading.models.ml_ensemble.ensemble_trainer import EnsembleTrainer
from advanced_trading.models.ml_ensemble.feature_engineering import FeatureEngineer
from advanced_trading.strategies.adaptive_meta_strategy import AdaptiveMetaStrategy

# Load data
data = load_data('BTC', '1h', '2022-01-01', '2023-01-01', 'data')

# Create optimizer
optimizer = create_ml_adaptive_optimizer(
    ensemble_trainer_class=EnsembleTrainer,
    ensemble_trainer_params={
        'prediction_type': 'classification',
        'target_horizon': 5,
        'cv_folds': 3,
        'ensemble_method': 'weighted_avg',
        'regime_aware': True
    },
    target_symbol='BTC',
    n_trials=10
)

# Create walk-forward tester
wf = MLWalkForwardAnalysis(
    market_data=data,
    train_size=3000,  # 3000 periods (hours)
    test_size=720,    # 720 periods (1 month)
    step_size=720,    # Step 1 month at a time
    optimization_func=optimizer,
    feature_engineer=FeatureEngineer(),
    regime_detection_func=lambda x: detect_market_regimes(x, n_regimes=3),
    initial_capital=10000,
    commission=0.001
)

# Run walk-forward test
results = wf.run(
    strategy_factory=lambda **kwargs: AdaptiveMetaStrategy(**kwargs),
    verbose=True
)

# Plot results
wf.plot_results(title='Adaptive ML Strategy Walk-Forward Test', 
                save_path='results/walk_forward_test.png')

# Save results
wf.save_results('ml_adaptive_wf_test')
""" 