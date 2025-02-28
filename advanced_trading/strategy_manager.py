# advanced_trading/strategy_manager.py

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union, Any
from datetime import datetime, timedelta
import os
import json
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

# Import strategies
from strategies.funding_arbitrage import FundingRateArbitrage
from strategies.statistical_arbitrage import StatisticalArbitrageStrategy
from strategies.volume_profile_strategy import VolumeProfileStrategy
from utils.regime_detection import RegimeClassifier
from data.data_loader import DataLoader

logger = logging.getLogger(__name__)

class StrategyManager:
    """
    Manager for multiple trading strategies with dynamic capital allocation
    based on performance and market regime.
    """
    
    def __init__(self, 
                total_capital: float = 100000.0,
                strategies_config: Dict = None,
                data_loader: DataLoader = None,
                results_dir: str = None):
        """
        Initialize the strategy manager.
        
        Args:
            total_capital: Total capital to allocate
            strategies_config: Configuration for strategies
            data_loader: Data loader instance or None to create new
            results_dir: Directory to save results
        """
        self.total_capital = total_capital
        self.strategies_config = strategies_config or {}
        self.data_loader = data_loader or DataLoader()
        
        # Create results directory
        if results_dir:
            self.results_dir = Path(results_dir)
        else:
            self.results_dir = Path(__file__).resolve().parent / 'results' / 'strategy_manager' / datetime.now().strftime('%Y%m%d_%H%M%S')
        
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Initialize regime classifier
        self.regime_classifier = RegimeClassifier()
        
        # Initialize strategies
        self.strategies = {}
        self._initialize_strategies()
        
        # Capital allocation
        self.allocations = {}
        self._initialize_allocations()
        
        # Performance tracking
        self.performance_history = {}
        
        logger.info(f"Initialized Strategy Manager with {self.total_capital} capital")
    
    def _initialize_strategies(self):
        """Initialize all trading strategies."""
        # Set default strategy configuration if not provided
        if not self.strategies_config:
            self.strategies_config = {
                'funding_arbitrage': {
                    'enabled': True,
                    'params': {
                        'min_rate_threshold': 0.0005,  # 0.05% per 8h
                        'max_position_per_pair': 0.2
                    }
                },
                'statistical_arbitrage': {
                    'enabled': True,
                    'params': {
                        'entry_threshold': 2.0,
                        'exit_threshold': 0.5,
                        'max_holding_period': 10,
                        'max_position_per_pair': 0.2
                    }
                },
                'volume_profile': {
                    'enabled': True,
                    'params': {
                        'lookback_periods': 100,
                        'poc_threshold_pct': 0.5,
                        'key_level_threshold_pct': 0.2,
                        'profit_target_pct': 2.0,
                        'stop_loss_pct': 1.0
                    }
                }
            }
        
        # Initialize each strategy if enabled
        if self.strategies_config.get('funding_arbitrage', {}).get('enabled', False):
            params = self.strategies_config['funding_arbitrage'].get('params', {})
            self.strategies['funding_arbitrage'] = FundingRateArbitrage(**params)
            logger.info("Initialized Funding Arbitrage strategy")
        
        if self.strategies_config.get('statistical_arbitrage', {}).get('enabled', False):
            params = self.strategies_config['statistical_arbitrage'].get('params', {})
            self.strategies['statistical_arbitrage'] = StatisticalArbitrageStrategy(**params)
            logger.info("Initialized Statistical Arbitrage strategy")
        
        if self.strategies_config.get('volume_profile', {}).get('enabled', False):
            params = self.strategies_config['volume_profile'].get('params', {})
            self.strategies['volume_profile'] = VolumeProfileStrategy(**params)
            logger.info("Initialized Volume Profile strategy")
    
    def _initialize_allocations(self):
        """Initialize capital allocations for strategies."""
        # Start with equal allocation
        n_strategies = len(self.strategies)
        if n_strategies == 0:
            logger.warning("No strategies initialized")
            return
        
        equal_allocation = 1.0 / n_strategies
        
        for strategy_name in self.strategies:
            self.allocations[strategy_name] = equal_allocation
            
            # Initialize performance history
            self.performance_history[strategy_name] = {
                'returns': [],
                'sharpe_ratio': [],
                'win_rate': [],
                'profit_factor': [],
                'capital': []
            }
        
        logger.info(f"Initialized equal capital allocation: {self.allocations}")
    
    def detect_market_regime(self, data_dict: Dict[str, pd.DataFrame]) -> str:
        """
        Detect current market regime.
        
        Args:
            data_dict: Dictionary of price data
            
        Returns:
            String identifying the current regime
        """
        # Combine data from multiple symbols
        returns_dict = {}
        for symbol, data in data_dict.items():
            if 'close' in data.columns:
                returns = data['close'].pct_change().dropna()
                if not returns.empty:
                    returns_dict[symbol] = returns
        
        if not returns_dict:
            return "unknown"
        
        # Use first symbol as reference or aggregate them
        if len(returns_dict) == 1:
            reference_returns = list(returns_dict.values())[0]
        else:
            # Reindex to common date range and average
            dfs = []
            for returns in returns_dict.values():
                dfs.append(returns.reindex(pd.date_range(returns.index.min(), returns.index.max())))
            
            # Average returns across symbols
            reference_returns = pd.concat(dfs, axis=1).mean(axis=1).dropna()
        
        # Detect regime
        regime = self.regime_classifier.detect_regime(reference_returns)
        
        logger.info(f"Detected market regime: {regime}")
        
        return regime
    
    def adjust_allocations_for_regime(self, regime: str):
        """
        Adjust strategy allocations based on market regime.
        
        Args:
            regime: Current market regime
        """
        # Define strategy weights for different regimes
        regime_weights = {
            "trending_bullish": {
                "funding_arbitrage": 0.2,
                "statistical_arbitrage": 0.3,
                "volume_profile": 0.5
            },
            "trending_bearish": {
                "funding_arbitrage": 0.3,
                "statistical_arbitrage": 0.5,
                "volume_profile": 0.2
            },
            "mean_reverting": {
                "funding_arbitrage": 0.2,
                "statistical_arbitrage": 0.6,
                "volume_profile": 0.2
            },
            "high_volatility": {
                "funding_arbitrage": 0.5,
                "statistical_arbitrage": 0.2,
                "volume_profile": 0.3
            },
            "low_volatility": {
                "funding_arbitrage": 0.6,
                "statistical_arbitrage": 0.3,
                "volume_profile": 0.1
            },
            "unknown": {
                "funding_arbitrage": 0.33,
                "statistical_arbitrage": 0.33,
                "volume_profile": 0.34
            }
        }
        
        # Check if regime is recognized
        if regime not in regime_weights:
            regime = "unknown"
        
        # Get weights for current regime
        weights = regime_weights[regime]
        
        # Adjust allocations based on which strategies are actually enabled
        enabled_strategies = list(self.strategies.keys())
        total_weight = sum(weights.get(s, 0) for s in enabled_strategies)
        
        if total_weight > 0:
            for strategy_name in enabled_strategies:
                self.allocations[strategy_name] = weights.get(strategy_name, 0) / total_weight
        
        logger.info(f"Adjusted allocations for {regime} regime: {self.allocations}")
    
    def adjust_allocations_for_performance(self, lookback_periods: int = 10):
        """
        Adjust strategy allocations based on recent performance.
        
        Args:
            lookback_periods: Number of periods to consider for performance
        """
        if not self.performance_history:
            logger.warning("No performance history available for allocation adjustment")
            return
        
        # Calculate recent performance metrics
        recent_metrics = {}
        
        for strategy_name, history in self.performance_history.items():
            if not history['returns'] or len(history['returns']) < lookback_periods:
                # Not enough history
                recent_metrics[strategy_name] = {
                    'sharpe': 0,
                    'win_rate': 0,
                    'profit_factor': 0
                }
                continue
            
            # Get recent returns
            recent_returns = history['returns'][-lookback_periods:]
            
            # Calculate Sharpe ratio
            sharpe = np.mean(recent_returns) / np.std(recent_returns) if np.std(recent_returns) > 0 else 0
            
            # Get recent win rate
            if 'win_rate' in history and len(history['win_rate']) > 0:
                win_rate = history['win_rate'][-1]
            else:
                win_rate = 0
            
            # Get recent profit factor
            if 'profit_factor' in history and len(history['profit_factor']) > 0:
                profit_factor = history['profit_factor'][-1]
            else:
                profit_factor = 0
            
            recent_metrics[strategy_name] = {
                'sharpe': sharpe,
                'win_rate': win_rate,
                'profit_factor': profit_factor
            }
        
        # Combine metrics into a single score
        strategy_scores = {}
        
        for strategy_name, metrics in recent_metrics.items():
            # Weighted combination of metrics
            score = (
                0.4 * max(0, metrics['sharpe']) + 
                0.3 * metrics['win_rate'] + 
                0.3 * min(3, metrics['profit_factor'])
            )
            
            strategy_scores[strategy_name] = max(0.1, score)  # Minimum score of 0.1
        
        # Calculate new allocations proportional to scores
        total_score = sum(strategy_scores.values())
        
        if total_score > 0:
            for strategy_name, score in strategy_scores.items():
                self.allocations[strategy_name] = score / total_score
        
        logger.info(f"Adjusted allocations based on performance: {self.allocations}")
    
    def get_strategy_capital(self, strategy_name: str) -> float:
        """
        Get allocated capital for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Allocated capital amount
        """
        allocation = self.allocations.get(strategy_name, 0)
        return self.total_capital * allocation
    
    def run_strategies(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        """
        Run all strategies and collect signals.
        
        Args:
            data_dict: Dictionary of price data
            
        Returns:
            Dictionary of strategy signals and trades
        """
        # Detect market regime
        regime = self.detect_market_regime(data_dict)
        
        # Adjust allocations based on regime
        self.adjust_allocations_for_regime(regime)
        
        # Adjust allocations based on performance
        self.adjust_allocations_for_performance()
        
        # Run each strategy
        strategy_results = {}
        
        for strategy_name, strategy in self.strategies.items():
            try:
                # Get allocated capital
                capital = self.get_strategy_capital(strategy_name)
                
                logger.info(f"Running {strategy_name} with {capital:.2f} capital")
                
                # Execute strategy
                if strategy_name == 'funding_arbitrage':
                    opportunities = strategy.find_opportunities()
                    trades = strategy.execute_arbitrage(capital)
                    result = {
                        'opportunities': opportunities,
                        'trades': trades
                    }
                
                elif strategy_name == 'statistical_arbitrage':
                    signals = strategy.generate_signals(data_dict)
                    trades = strategy.execute_trades(signals, data_dict, capital)
                    result = {
                        'signals': signals,
                        'trades': trades
                    }
                
                elif strategy_name == 'volume_profile':
                    trades = strategy.execute_trades(data_dict, capital)
                    result = {
                        'trades': trades
                    }
                
                else:
                    logger.warning(f"Unknown strategy type: {strategy_name}")
                    continue
                
                # Store results
                strategy_results[strategy_name] = result
                
                # Update performance based on trades
                self._update_strategy_performance(strategy_name, result)
                
            except Exception as e:
                logger.error(f"Error running {strategy_name}: {str(e)}", exc_info=True)
        
        return strategy_results
    
    def _update_strategy_performance(self, strategy_name: str, result: Dict):
        """
        Update strategy performance metrics.
        
        Args:
            strategy_name: Name of the strategy
            result: Strategy execution result
        """
        trades = result.get('trades', [])
        
        if not trades:
            return
        
        # Calculate returns from trades
        returns = []
        winning_trades = 0
        losing_trades = 0
        total_profit = 0
        total_loss = 0
        
        for trade in trades:
            if 'pnl_pct' in trade:
                returns.append(trade['pnl_pct'] / 100.0)  # Convert from percentage
                
                if trade['pnl_pct'] > 0:
                    winning_trades += 1
                    total_profit += trade['pnl_pct']
                else:
                    losing_trades += 1
                    total_loss += abs(trade['pnl_pct'])
        
        if returns:
            # Calculate metrics
            avg_return = np.mean(returns)
            win_rate = winning_trades / (winning_trades + losing_trades) if (winning_trades + losing_trades) > 0 else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            
            # Update performance history
            self.performance_history[strategy_name]['returns'].append(avg_return)
            self.performance_history[strategy_name]['win_rate'].append(win_rate)
            self.performance_history[strategy_name]['profit_factor'].append(profit_factor)
            
            # Update allocated capital
            current_capital = self.get_strategy_capital(strategy_name)
            self.performance_history[strategy_name]['capital'].append(current_capital)
            
            # Calculate Sharpe if we have enough returns
            if len(returns) > 1:
                sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
                self.performance_history[strategy_name]['sharpe_ratio'].append(sharpe)
            
            logger.info(f"{strategy_name} performance: Return {avg_return:.2%}, "
                      f"Win rate {win_rate:.2f}, Profit factor {profit_factor:.2f}")
    
        def visualize_performance(self, save_path: Optional[str] = None) -> plt.Figure:
        """
        Visualize performance metrics for all strategies.
        
        Args:
            save_path: Path to save the visualization
            
        Returns:
            Matplotlib figure
        """
        if not self.performance_history:
            logger.warning("No performance history available for visualization")
            return None
        
        # Create figure with subplots
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        
        # Colors for each strategy
        colors = {
            'funding_arbitrage': 'blue',
            'statistical_arbitrage': 'green',
            'volume_profile': 'red'
        }
        
        # Plot returns
        ax = axes[0, 0]
        for strategy_name, history in self.performance_history.items():
            if history['returns']:
                ax.plot(range(len(history['returns'])), history['returns'], 
                       label=strategy_name, color=colors.get(strategy_name, 'gray'))
        ax.set_title('Average Returns per Period')
        ax.set_ylabel('Return')
        ax.grid(True)
        ax.legend()
        
        # Plot win rate
        ax = axes[0, 1]
        for strategy_name, history in self.performance_history.items():
            if history['win_rate']:
                ax.plot(range(len(history['win_rate'])), history['win_rate'], 
                       label=strategy_name, color=colors.get(strategy_name, 'gray'))
        ax.set_title('Win Rate')
        ax.set_ylabel('Win Rate')
        ax.grid(True)
        ax.legend()
        
        # Plot profit factor
        ax = axes[1, 0]
        for strategy_name, history in self.performance_history.items():
            if history['profit_factor']:
                # Cap profit factor for visualization
                capped_pf = [min(pf, 5) for pf in history['profit_factor']]
                ax.plot(range(len(capped_pf)), capped_pf, 
                       label=strategy_name, color=colors.get(strategy_name, 'gray'))
        ax.set_title('Profit Factor (capped at 5)')
        ax.set_ylabel('Profit Factor')
        ax.grid(True)
        ax.legend()
        
        # Plot Sharpe ratio
        ax = axes[1, 1]
        for strategy_name, history in self.performance_history.items():
            if history.get('sharpe_ratio', []):
                ax.plot(range(len(history['sharpe_ratio'])), history['sharpe_ratio'], 
                       label=strategy_name, color=colors.get(strategy_name, 'gray'))
        ax.set_title('Sharpe Ratio')
        ax.set_ylabel('Sharpe')
        ax.grid(True)
        ax.legend()
        
        # Plot capital allocation
        ax = axes[2, 0]
        for strategy_name, history in self.performance_history.items():
            if history['capital']:
                ax.plot(range(len(history['capital'])), history['capital'], 
                       label=strategy_name, color=colors.get(strategy_name, 'gray'))
        ax.set_title('Capital Allocation')
        ax.set_ylabel('Capital')
        ax.grid(True)
        ax.legend()
        
        # Plot current allocation pie chart
        ax = axes[2, 1]
        if self.allocations:
            labels = list(self.allocations.keys())
            sizes = [self.allocations[label] * 100 for label in labels]  # Convert to percentages
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=[colors.get(l, 'gray') for l in labels])
            ax.set_title('Current Capital Allocation')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved performance visualization to {save_path}")
        
        return fig
    
    def save_performance_history(self, file_path: Optional[str] = None) -> str:
        """
        Save performance history to a file.
        
        Args:
            file_path: Path to save the file or None for default
            
        Returns:
            Path where file was saved
        """
        if not file_path:
            file_path = os.path.join(self.results_dir, f"performance_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        # Prepare data for serialization
        data = {
            'allocations': self.allocations,
            'performance': {}
        }
        
        for strategy_name, history in self.performance_history.items():
            data['performance'][strategy_name] = {
                'returns': history['returns'],
                'win_rate': history['win_rate'],
                'profit_factor': history['profit_factor'],
                'sharpe_ratio': history.get('sharpe_ratio', []),
                'capital': history['capital']
            }
        
        # Save to file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved performance history to {file_path}")
        
        return file_path
    
    def load_performance_history(self, file_path: str) -> bool:
        """
        Load performance history from a file.
        
        Args:
            file_path: Path to load from
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"Performance history file not found: {file_path}")
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load allocations
            if 'allocations' in data:
                self.allocations = data['allocations']
            
            # Load performance history
            if 'performance' in data:
                for strategy_name, history in data['performance'].items():
                    # Initialize if strategy doesn't exist
                    if strategy_name not in self.performance_history:
                        self.performance_history[strategy_name] = {
                            'returns': [],
                            'win_rate': [],
                            'profit_factor': [],
                            'sharpe_ratio': [],
                            'capital': []
                        }
                    
                    # Load metrics
                    for metric, values in history.items():
                        if metric in self.performance_history[strategy_name]:
                            self.performance_history[strategy_name][metric] = values
            
            logger.info(f"Loaded performance history from {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading performance history: {str(e)}")
            return False