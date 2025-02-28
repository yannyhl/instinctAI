# advanced_trading/utils/monte_carlo.py

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional, Union
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def bootstrap_returns(returns: np.ndarray, block_size: int = 20, 
                    num_samples: int = 252) -> np.ndarray:
    """
    Generate synthetic returns using block bootstrap.
    
    Args:
        returns: Original returns series
        block_size: Size of blocks for bootstrap
        num_samples: Number of samples to generate
        
    Returns:
        Synthetic returns series
    """
    # Create blocks
    num_blocks = len(returns) - block_size + 1
    blocks = [returns[i:i+block_size] for i in range(num_blocks)]
    
    # Generate synthetic series by sampling blocks with replacement
    num_blocks_needed = int(np.ceil(num_samples / block_size))
    sampled_blocks_indices = np.random.choice(len(blocks), size=num_blocks_needed)
    
    # Concatenate blocks
    synthetic_returns = np.concatenate([blocks[i] for i in sampled_blocks_indices])
    
    # Trim to requested length
    return synthetic_returns[:num_samples]

def monte_carlo_simulation(original_returns: np.ndarray, 
                         original_performance: Dict[str, float],
                         num_simulations: int = 1000,
                         block_size: int = 20,
                         confidence_level: float = 0.95) -> Dict[str, Any]:
    """
    Perform Monte Carlo simulation to assess strategy robustness.
    
    Args:
        original_returns: Original returns series
        original_performance: Dictionary of original performance metrics
        num_simulations: Number of Monte Carlo simulations
        block_size: Block size for bootstrap
        confidence_level: Confidence level for intervals
        
    Returns:
        Dictionary of simulation results
    """
    # Store simulation results
    simulation_results = {
        'total_returns': [],
        'sharpe_ratios': [],
        'max_drawdowns': [],
        'win_rates': []
    }
    
    # Run simulations
    for i in range(num_simulations):
        # Generate synthetic returns
        synthetic_returns = bootstrap_returns(original_returns, block_size)
        
        # Calculate performance metrics
        total_return = np.sum(synthetic_returns)
        sharpe_ratio = np.mean(synthetic_returns) / np.std(synthetic_returns) if np.std(synthetic_returns) > 0 else 0
        
        # Calculate drawdown
        cumulative_returns = np.cumsum(synthetic_returns)
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - peak
        max_drawdown = np.min(drawdown)
        
        # Calculate win rate
        win_rate = np.sum(synthetic_returns > 0) / len(synthetic_returns)
        
        # Store results
        simulation_results['total_returns'].append(total_return)
        simulation_results['sharpe_ratios'].append(sharpe_ratio)
        simulation_results['max_drawdowns'].append(max_drawdown)
        simulation_results['win_rates'].append(win_rate)
    
    # Calculate confidence intervals
    lower_percentile = (1 - confidence_level) / 2 * 100
    upper_percentile = (1 + confidence_level) / 2 * 100
    
    metrics = {}
    for metric_name, values in simulation_results.items():
        metrics[metric_name] = {
            'mean': np.mean(values),
            'median': np.median(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values),
            'lower_ci': np.percentile(values, lower_percentile),
            'upper_ci': np.percentile(values, upper_percentile)
        }
    
    return {
        'original_performance': original_performance,
        'metrics': metrics,
        'raw_simulations': simulation_results
    }

def plot_monte_carlo_results(results: Dict[str, Any], 
                           save_path: Optional[str] = None) -> plt.Figure:
    """
    Create visualization of Monte Carlo simulation results.
    
    Args:
        results: Monte Carlo simulation results
        save_path: Path to save the visualization
        
    Returns:
        Matplotlib figure
    """
    fig, axs = plt.subplots(2, 2, figsize=(15, 12))
    
    # Plot total returns distribution
    axs[0, 0].hist(results['raw_simulations']['total_returns'], bins=50, alpha=0.7)
    axs[0, 0].axvline(results['original_performance']['total_return'], 
                     color='r', linestyle='--', label='Original')
    axs[0, 0].axvline(results['metrics']['total_returns']['lower_ci'], 
                     color='g', linestyle=':', label='95% CI')
    axs[0, 0].axvline(results['metrics']['total_returns']['upper_ci'], 
                     color='g', linestyle=':')
    axs[0, 0].set_title('Distribution of Total Returns')
    axs[0, 0].set_xlabel('Total Return')
    axs[0, 0].set_ylabel('Frequency')
    axs[0, 0].legend()
    
    # Plot Sharpe ratio distribution
    axs[0, 1].hist(results['raw_simulations']['sharpe_ratios'], bins=50, alpha=0.7)
    axs[0, 1].axvline(results['original_performance']['sharpe_ratio'], 
                     color='r', linestyle='--', label='Original')
    axs[0, 1].axvline(results['metrics']['sharpe_ratios']['lower_ci'], 
                     color='g', linestyle=':', label='95% CI')
    axs[0, 1].axvline(results['metrics']['sharpe_ratios']['upper_ci'], 
                     color='g', linestyle=':')
    axs[0, 1].set_title('Distribution of Sharpe Ratios')
    axs[0, 1].set_xlabel('Sharpe Ratio')
    axs[0, 1].set_ylabel('Frequency')
    axs[0, 1].legend()
    
    # Plot max drawdown distribution
    axs[1, 0].hist(results['raw_simulations']['max_drawdowns'], bins=50, alpha=0.7)
    axs[1, 0].axvline(results['original_performance']['max_drawdown'], 
                     color='r', linestyle='--', label='Original')
    axs[1, 0].axvline(results['metrics']['max_drawdowns']['lower_ci'], 
                     color='g', linestyle=':', label='95% CI')
    axs[1, 0].axvline(results['metrics']['max_drawdowns']['upper_ci'], 
                     color='g', linestyle=':')
    axs[1, 0].set_title('Distribution of Max Drawdowns')
    axs[1, 0].set_xlabel('Max Drawdown')
    axs[1, 0].set_ylabel('Frequency')
    axs[1, 0].legend()
    
     # Plot win rate distribution
    axs[1, 1].hist(results['raw_simulations']['win_rates'], bins=50, alpha=0.7)
    axs[1, 1].axvline(results['original_performance']['win_rate'], 
                     color='r', linestyle='--', label='Original')
    axs[1, 1].axvline(results['metrics']['win_rates']['lower_ci'], 
                     color='g', linestyle=':', label='95% CI')
    axs[1, 1].axvline(results['metrics']['win_rates']['upper_ci'], 
                     color='g', linestyle=':')
    axs[1, 1].set_title('Distribution of Win Rates')
    axs[1, 1].set_xlabel('Win Rate')
    axs[1, 1].set_ylabel('Frequency')
    axs[1, 1].legend()
    
    # Add overall title
    fig.suptitle('Monte Carlo Simulation Results', fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.96])  # Adjust for suptitle
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Monte Carlo visualization saved to {save_path}")
    
    return fig

def run_monte_carlo_analysis(strategy: Any, data: pd.DataFrame, 
                           original_performance: Dict[str, float],
                           num_simulations: int = 1000,
                           output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a complete Monte Carlo analysis for a trading strategy.
    
    Args:
        strategy: Strategy instance
        data: Market data
        original_performance: Dictionary of original performance metrics
        num_simulations: Number of Monte Carlo simulations
        output_dir: Directory to save results
        
    Returns:
        Dictionary of analysis results
    """
    # Extract returns from original performance
    if 'returns' in data.columns:
        original_returns = data['returns'].dropna().values
    else:
        # Calculate returns if not available
        original_returns = data['close'].pct_change().dropna().values
    
    logger.info(f"Running Monte Carlo simulation with {num_simulations} iterations")
    
    # Run Monte Carlo simulation
    mc_results = monte_carlo_simulation(
        original_returns=original_returns,
        original_performance=original_performance,
        num_simulations=num_simulations
    )
    
    # Create visualization
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(output_dir, f"monte_carlo_{timestamp}.png")
        
        # Generate and save plot
        fig = plot_monte_carlo_results(mc_results, save_path)
        
        # Save results data
        results_path = os.path.join(output_dir, f"monte_carlo_results_{timestamp}.json")
        
        # Convert numpy arrays to lists for JSON serialization
        serializable_results = {
            'original_performance': mc_results['original_performance'],
            'metrics': mc_results['metrics'],
            'raw_simulations': {
                'total_returns': mc_results['raw_simulations']['total_returns'].tolist(),
                'sharpe_ratios': mc_results['raw_simulations']['sharpe_ratios'].tolist(),
                'max_drawdowns': mc_results['raw_simulations']['max_drawdowns'].tolist(),
                'win_rates': mc_results['raw_simulations']['win_rates'].tolist()
            }
        }
        
        import json
        with open(results_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        logger.info(f"Monte Carlo results saved to {results_path}")
    
    # Return results
    return mc_results

def calculate_var_cvar(returns: np.ndarray, confidence_level: float = 0.95) -> Dict[str, float]:
    """
    Calculate Value at Risk (VaR) and Conditional Value at Risk (CVaR).
    
    Args:
        returns: Array of returns
        confidence_level: Confidence level (e.g., 0.95 for 95%)
        
    Returns:
        Dictionary with VaR and CVaR values
    """
    # Sort returns in ascending order
    sorted_returns = np.sort(returns)
    
    # Calculate the index for VaR
    var_index = int(len(returns) * (1 - confidence_level))
    
    # Get VaR (negative of the return at the specified percentile)
    var = -sorted_returns[var_index]
    
    # Calculate CVaR (average of returns beyond VaR)
    cvar_returns = sorted_returns[:var_index+1]
    cvar = -np.mean(cvar_returns)
    
    return {
        'var': var,
        'cvar': cvar
    }

def analyze_strategy_robustness(mc_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze strategy robustness based on Monte Carlo results.
    
    Args:
        mc_results: Monte Carlo simulation results
        
    Returns:
        Dictionary of robustness metrics
    """
    # Calculate probability of positive return
    total_returns = np.array(mc_results['raw_simulations']['total_returns'])
    prob_positive_return = np.mean(total_returns > 0)
    
    # Calculate probability of beating benchmark (if available)
    benchmark_return = mc_results['original_performance'].get('benchmark_return', 0)
    prob_beat_benchmark = np.mean(total_returns > benchmark_return)
    
    # Calculate probability of achieving target return
    target_return = 0.10  # 10% return target
    prob_target_return = np.mean(total_returns >= target_return)
    
    # Calculate VaR and CVaR
    risk_metrics = calculate_var_cvar(total_returns)
    
    # Calculate probability of catastrophic loss
    catastrophic_threshold = -0.20  # -20% return
    prob_catastrophic = np.mean(total_returns <= catastrophic_threshold)
    
    # Calculate robustness score (simple version)
    # Higher score = more robust
    robustness_score = (prob_positive_return * 0.4 + 
                       (1 - prob_catastrophic) * 0.4 + 
                       prob_beat_benchmark * 0.2)
    
    # Interpretation
    if robustness_score >= 0.8:
        robustness_level = "Highly Robust"
    elif robustness_score >= 0.6:
        robustness_level = "Moderately Robust"
    elif robustness_score >= 0.4:
        robustness_level = "Somewhat Robust"
    else:
        robustness_level = "Not Robust"
    
    return {
        'prob_positive_return': prob_positive_return,
        'prob_beat_benchmark': prob_beat_benchmark,
        'prob_target_return': prob_target_return,
        'prob_catastrophic': prob_catastrophic,
        'var': risk_metrics['var'],
        'cvar': risk_metrics['cvar'],
        'robustness_score': robustness_score,
        'robustness_level': robustness_level
    }