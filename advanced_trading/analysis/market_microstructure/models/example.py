"""
Market Microstructure Models Example

This script demonstrates the usage of market impact models for estimating
the price impact of orders in different market conditions.

Examples include:
1. Linear impact model (square-root law)
2. Nonlinear impact model with permanent and temporary components
3. ML-based impact model
4. Order book prediction with VAR and LSTM models
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import impact models
from advanced_trading.analysis.market_microstructure.models import (
    LinearImpactModel, NonlinearImpactModel, MLImpactModel,
    VAR_OrderBookPredictor, LSTM_OrderBookPredictor
)

# Import visualization tools
from advanced_trading.analysis.market_microstructure.visualization import (
    ImpactVisualizer, OrderBookVisualizer
)

def generate_synthetic_data(n_samples=100):
    """Generate synthetic data for model demonstration."""
    
    # Generate order sizes (exponentially distributed to have more small orders)
    sizes = np.random.exponential(scale=1.0, size=n_samples)
    sizes = np.sort(sizes)  # Sort for better visualization
    
    # Normalize to percentage of ADV (Average Daily Volume)
    sizes = sizes / np.max(sizes) * 0.5  # Max size is 50% of ADV
    
    # Generate market states
    volatilities = 0.01 + 0.02 * np.random.rand(n_samples)  # 1% to 3% volatility
    spreads = 0.0005 + 0.0015 * np.random.rand(n_samples)  # 0.5 to 2 bps spread
    depths = np.random.uniform(low=10, high=100, size=n_samples)  # Market depth
    
    # Create synthetic impact data with noise
    # Use square-root law with random noise
    true_impacts = 0.1 * volatilities * np.sqrt(sizes)
    noise = 0.2 * true_impacts * np.random.randn(n_samples)
    observed_impacts = true_impacts + noise
    
    # Ensure impacts are positive
    observed_impacts = np.maximum(observed_impacts, 0)
    
    # Generate synthetic order book data for prediction examples
    timestamps = [datetime.now() + timedelta(minutes=i) for i in range(n_samples)]
    
    # Create order book metrics like bid-ask imbalance, depth, etc.
    order_book_metrics = pd.DataFrame({
        'timestamp': timestamps,
        'mid_price': 100 + np.cumsum(0.01 * np.random.randn(n_samples)),
        'spread': spreads,
        'depth': depths,
        'order_book_imbalance': 0.3 * np.random.randn(n_samples),  # -1 to 1 range
        'volatility': volatilities,
        'volume': 1000 + 500 * np.random.rand(n_samples)
    })
    
    # Add lag features for time series modeling
    for lag in range(1, 4):
        for col in ['mid_price', 'spread', 'order_book_imbalance', 'volume']:
            order_book_metrics[f'{col}_lag_{lag}'] = order_book_metrics[col].shift(lag)
    
    # Drop rows with NaN values from lagging
    order_book_metrics = order_book_metrics.dropna()
    
    # Add information about whether price went up or down in next period
    order_book_metrics['price_direction'] = np.sign(order_book_metrics['mid_price'].diff().shift(-1))
    
    # Create separate trade-level data for ML model training
    trade_data = pd.DataFrame({
        'timestamp': timestamps,
        'size': sizes,
        'impact': observed_impacts,
        'side': np.random.choice(['buy', 'sell'], size=n_samples),
        'pre_trade_price': 100 + np.cumsum(0.01 * np.random.randn(n_samples)),
        'execution_price': 100 + np.cumsum(0.01 * np.random.randn(n_samples))
    })
    
    # Match with market state
    trade_data['volatility'] = volatilities
    trade_data['spread'] = spreads
    trade_data['depth'] = depths
    
    # Separate permanent and temporary impacts for nonlinear model
    alpha = 0.6  # Permanent impact exponent
    beta = 0.8   # Temporary impact exponent
    trade_data['permanent_impact'] = 0.05 * volatilities * np.power(sizes, alpha)
    trade_data['temporary_impact'] = 0.08 * spreads * np.power(sizes / depths, beta)
    trade_data['immediate_impact'] = trade_data['permanent_impact'] + trade_data['temporary_impact']
    
    # Return all generated data
    return {
        'sizes': sizes,
        'observed_impacts': observed_impacts,
        'order_book_metrics': order_book_metrics,
        'trade_data': trade_data,
        'volatilities': volatilities,
        'spreads': spreads,
        'depths': depths
    }

def demo_linear_impact_model(data):
    """Demonstrate the linear impact model."""
    
    logger.info("Demonstrating Linear Impact Model")
    
    # Extract relevant data
    sizes = data['sizes']
    observed_impacts = data['observed_impacts']
    trade_data = data['trade_data']
    
    # Create and train linear impact model
    model = LinearImpactModel(name="Square-Root Impact Model", alpha=0.5)
    
    # Create synthetic market state for prediction
    market_state = {
        'volatility': 0.02,  # 2% volatility
        'adv': 1000          # Average daily volume
    }
    
    # Predict impact for a range of order sizes
    test_sizes = np.linspace(0.01, 0.5, 50)  # 1% to 50% of ADV
    predicted_impacts = [model.predict_impact(size, market_state, 'buy') for size in test_sizes]
    
    # Train the model on the trade data
    training_data = trade_data[['size', 'impact', 'side']].copy()
    market_data = trade_data[['volatility', 'adv']].copy()
    
    # Add ADV column if not present
    if 'adv' not in market_data.columns:
        market_data['adv'] = 1000  # Placeholder value
    
    result = model.train(training_data, market_data)
    
    # Print training results
    logger.info(f"Model training results: Y={result['Y']:.4f}, alpha={result['alpha']:.4f}")
    logger.info(f"Training metrics: R²={result['r2']:.4f}, RMSE={result['rmse']:.6f}")
    
    # Use the visualization module to plot results
    impact_viz = ImpactVisualizer()
    
    # Plot impact curve
    fig, ax = impact_viz.plot_impact_curve(
        sizes, 
        observed_impacts, 
        model_name="Square-Root Impact Model",
        fit_curve=True,
        model_formula=f"Impact = {result['Y']:.4f} * Volatility * (Size/ADV)^{model.alpha:.2f}"
    )
    
    # Save plot
    plt.savefig("linear_impact_model.png")
    plt.close(fig)
    
    # Calculate predicted impacts after training
    predicted_impacts_after = [model.predict_impact(size, market_state, 'buy') for size in test_sizes]
    
    # Plot comparison before and after training
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(sizes, observed_impacts, color='black', alpha=0.7, label='Observed Impact')
    ax.plot(test_sizes, predicted_impacts, color='red', linewidth=2, 
           linestyle='--', label='Before Training')
    ax.plot(test_sizes, predicted_impacts_after, color='blue', linewidth=2, 
           label='After Training')
    
    ax.set_xlabel('Order Size (Fraction of ADV)')
    ax.set_ylabel('Price Impact')
    ax.set_title('Linear Impact Model - Before vs After Training')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("linear_impact_before_after.png")
    plt.close(fig)
    
    logger.info("Linear Impact Model demonstration completed")
    
    return model

def demo_nonlinear_impact_model(data):
    """Demonstrate the nonlinear impact model with permanent and temporary components."""
    
    logger.info("Demonstrating Nonlinear Impact Model")
    
    # Extract relevant data
    trade_data = data['trade_data']
    
    # Create nonlinear impact model
    model = NonlinearImpactModel(name="Nonlinear Impact Model")
    
    # Extract permanent and temporary impact components for training
    training_data = trade_data[['size', 'immediate_impact', 'permanent_impact', 'side']].copy()
    market_data = trade_data[['volatility', 'spread', 'depth', 'adv', 'order_book_imbalance']].copy()
    
    # Add required columns if not present
    if 'adv' not in market_data.columns:
        market_data['adv'] = 1000  # Placeholder value
    
    if 'order_book_imbalance' not in market_data.columns:
        market_data['order_book_imbalance'] = 0.0  # Neutral
    
    # Train the model
    result = model.train(training_data, market_data)
    
    # Print training results
    logger.info(f"Nonlinear Model Training Results:")
    logger.info(f"  Permanent Impact: factor={result['perm_factor']:.4f}, exponent={result['perm_exponent']:.4f}")
    logger.info(f"  Temporary Impact: factor={result['temp_factor']:.4f}, exponent={result['temp_exponent']:.4f}")
    logger.info(f"  R² (immediate): {result['r2_immediate']:.4f}, R² (permanent): {result['r2_permanent']:.4f}")
    
    # Create sample market state for predictions
    market_state = {
        'volatility': 0.02,    # 2% volatility
        'adv': 1000,           # Average daily volume
        'spread': 0.001,       # 10 bps spread
        'depth': 50,           # Market depth
        'order_book_imbalance': 0.0  # Neutral
    }
    
    # Generate predictions for a range of order sizes
    test_sizes = np.linspace(0.01, 0.5, 50)  # 1% to 50% of ADV
    
    # Calculate impact components
    permanent_impacts = []
    temporary_impacts = []
    total_impacts = []
    
    for size in test_sizes:
        # Get permanent impact component
        permanent_impact = model.perm_factor * market_state['volatility'] * np.power(size / market_state['adv'], model.perm_exponent)
        
        # Get temporary impact component
        depth_ratio = size / (market_state['depth'] * model.market_factors["depth_factor"])
        temporary_impact = model.temp_factor * market_state['spread'] * np.power(depth_ratio, model.temp_exponent)
        
        # Calculate total impact
        total_impact = model.predict_impact(size, market_state, 'buy')
        
        permanent_impacts.append(permanent_impact)
        temporary_impacts.append(temporary_impact)
        total_impacts.append(total_impact)
    
    # Use visualization
    impact_viz = ImpactVisualizer()
    
    # Plot permanent vs temporary impact
    fig, ax = impact_viz.plot_permanent_temporary_impact(
        test_sizes,
        np.array(permanent_impacts),
        np.array(temporary_impacts),
        model_name="Nonlinear Impact Model"
    )
    
    plt.savefig("nonlinear_impact_components.png")
    plt.close(fig)
    
    # Plot impact under different market conditions
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Different volatilities
    volatilities = [0.01, 0.02, 0.03, 0.05]  # 1% to 5%
    ax = axes[0, 0]
    for vol in volatilities:
        market_state['volatility'] = vol
        impacts = [model.predict_impact(size, market_state, 'buy') for size in test_sizes]
        ax.plot(test_sizes, impacts, label=f'Vol: {vol:.1%}')
    
    ax.set_title('Impact vs. Volatility')
    ax.set_xlabel('Order Size (Fraction of ADV)')
    ax.set_ylabel('Price Impact')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Different spreads
    spreads = [0.0005, 0.001, 0.002, 0.004]  # 5 to 40 bps
    ax = axes[0, 1]
    market_state['volatility'] = 0.02  # Reset volatility
    for spread in spreads:
        market_state['spread'] = spread
        impacts = [model.predict_impact(size, market_state, 'buy') for size in test_sizes]
        ax.plot(test_sizes, impacts, label=f'Spread: {spread*10000:.0f} bps')
    
    ax.set_title('Impact vs. Spread')
    ax.set_xlabel('Order Size (Fraction of ADV)')
    ax.set_ylabel('Price Impact')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Different depths
    depths = [20, 50, 100, 200]
    ax = axes[1, 0]
    market_state['spread'] = 0.001  # Reset spread
    for depth in depths:
        market_state['depth'] = depth
        impacts = [model.predict_impact(size, market_state, 'buy') for size in test_sizes]
        ax.plot(test_sizes, impacts, label=f'Depth: {depth}')
    
    ax.set_title('Impact vs. Market Depth')
    ax.set_xlabel('Order Size (Fraction of ADV)')
    ax.set_ylabel('Price Impact')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Different order book imbalances
    imbalances = [-0.5, -0.2, 0, 0.2, 0.5]  # -0.5 (sell) to 0.5 (buy)
    ax = axes[1, 1]
    market_state['depth'] = 50  # Reset depth
    for imbalance in imbalances:
        market_state['order_book_imbalance'] = imbalance
        impacts = [model.predict_impact(size, market_state, 'buy') for size in test_sizes]
        ax.plot(test_sizes, impacts, label=f'Imbalance: {imbalance:.1f}')
    
    ax.set_title('Impact vs. Order Book Imbalance')
    ax.set_xlabel('Order Size (Fraction of ADV)')
    ax.set_ylabel('Price Impact')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("nonlinear_impact_conditions.png")
    plt.close(fig)
    
    logger.info("Nonlinear Impact Model demonstration completed")
    
    return model

def demo_ml_impact_model(data):
    """Demonstrate the ML-based impact model."""
    
    logger.info("Demonstrating ML-based Impact Model")
    
    # Extract relevant data
    trade_data = data['trade_data']
    
    # Create ML impact model
    model = MLImpactModel(name="ML Impact Model", model_type="gradient_boosting")
    
    # Extract features for training
    training_data = trade_data[['size', 'impact', 'side']].copy()
    
    # Create market state features
    market_features = ['volatility', 'spread', 'depth']
    # Add any additional features from the data
    for feature in ['order_book_imbalance', 'market_volume', 'time_of_day']:
        if feature in trade_data.columns:
            market_features.append(feature)
    
    market_data = trade_data[market_features].copy()
    
    # Train the model
    try:
        result = model.train(training_data, market_data)
        
        # Print training results
        logger.info(f"ML Model Training Results:")
        logger.info(f"  R²: {result['r2']:.4f}, RMSE: {result['rmse']:.6f}")
        
        # Print feature importances
        logger.info("Feature Importances:")
        for feature, importance in sorted(
            result['feature_importance'].items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            logger.info(f"  {feature}: {importance:.4f}")
        
        # Create sample market state for predictions
        market_state = {
            'volatility': 0.02,
            'spread': 0.001,
            'depth': 50,
            'order_book_imbalance': 0.0,
            'market_volume': 500,
            'time_of_day': 0.5
        }
        
        # Generate predictions for a range of order sizes
        test_sizes = np.linspace(0.01, 0.5, 50)  # 1% to 50% of ADV
        ml_impacts = [model.predict_impact(size, market_state, 'buy') for size in test_sizes]
        
        # Compare with linear model
        linear_model = LinearImpactModel(name="Square-Root Impact Model")
        linear_impacts = [linear_model.predict_impact(size, market_state, 'buy') for size in test_sizes]
        
        # Compare with nonlinear model
        nonlinear_model = NonlinearImpactModel(name="Nonlinear Impact Model")
        nonlinear_impacts = [nonlinear_model.predict_impact(size, market_state, 'buy') for size in test_sizes]
        
        # Use visualization for comparison
        impact_viz = ImpactVisualizer()
        
        # Create a dictionary of model results
        model_results = {
            'ML Model (Gradient Boosting)': np.array(ml_impacts),
            'Linear Model (Square-Root)': np.array(linear_impacts),
            'Nonlinear Model': np.array(nonlinear_impacts)
        }
        
        # Get random sample of actual impacts for comparison
        sample_indices = np.random.choice(len(data['sizes']), size=20, replace=False)
        sample_sizes = data['sizes'][sample_indices]
        sample_impacts = data['observed_impacts'][sample_indices]
        
        # Plot model comparison
        fig, axes = impact_viz.plot_model_comparison(
            test_sizes,
            model_results,
            actual_impacts=None,  # No actual impacts for this range
            reference_model='Linear Model (Square-Root)'
        )
        
        plt.savefig("ml_impact_model_comparison.png")
        plt.close(fig)
        
        # Plot feature importance
        if hasattr(model, 'feature_importance') and model.feature_importance:
            # Sort features by importance
            sorted_features = dict(sorted(
                model.feature_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            ))
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(list(sorted_features.keys()), list(sorted_features.values()))
            ax.set_title('ML Impact Model - Feature Importance')
            ax.set_xlabel('Importance')
            plt.tight_layout()
            plt.savefig("ml_impact_feature_importance.png")
            plt.close(fig)
        
        logger.info("ML Impact Model demonstration completed")
        return model
        
    except Exception as e:
        logger.error(f"Error in ML model demonstration: {str(e)}")
        return None

def demo_order_book_predictor(data):
    """Demonstrate the order book prediction models."""
    
    logger.info("Demonstrating Order Book Prediction Models")
    
    # Extract order book data
    order_book_data = data['order_book_metrics']
    
    # Try VAR model first
    try:
        # Set up target columns to predict
        target_cols = ['mid_price', 'spread', 'order_book_imbalance']
        
        # Create VAR predictor
        var_model = VAR_OrderBookPredictor(
            name="VAR Order Book Predictor",
            prediction_horizon=5,  # Predict 5 steps ahead
            lag_order=3            # Use 3 lags
        )
        
        # Prepare data for training
        train_data = order_book_data[target_cols].copy()
        
        # Train the model
        result = var_model.train(train_data)
        
        # Print training results
        logger.info(f"VAR Model Training Results:")
        logger.info(f"  Overall R²: {result['overall_r2']:.4f}, RMSE: {result['overall_rmse']:.6f}")
        
        # Print R² for each variable
        for var, r2 in result['r2_by_variable'].items():
            logger.info(f"  {var} R²: {r2:.4f}")
        
        # Make predictions using the last 10 data points
        last_data = train_data.tail(10)
        predictions = var_model.predict(last_data)
        
        # Plot actual vs predicted
        fig, axes = plt.subplots(len(target_cols), 1, figsize=(12, 4*len(target_cols)), sharex=True)
        
        # Create x-axis for actual data
        actual_times = order_book_data.index[-20:]
        
        # Create x-axis for predicted data
        if isinstance(order_book_data.index, pd.DatetimeIndex):
            last_time = order_book_data.index[-1]
            time_diff = order_book_data.index[-1] - order_book_data.index[-2]
            pred_times = [last_time + (i+1)*time_diff for i in range(len(predictions))]
        else:
            # If not datetime index, just use sequential numbers
            last_idx = len(order_book_data) - 1
            pred_times = range(last_idx + 1, last_idx + 1 + len(predictions))
        
        for i, col in enumerate(target_cols):
            ax = axes[i] if len(target_cols) > 1 else axes
            
            # Plot actual data (last 20 points)
            ax.plot(actual_times, order_book_data[col].values[-20:], 
                   color='blue', label='Actual')
            
            # Plot predicted data
            ax.plot(pred_times, predictions[col].values, 
                   color='red', marker='o', linestyle='--', label='Predicted')
            
            ax.set_title(f'VAR Prediction: {col}')
            ax.set_ylabel(col)
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        axes[-1].set_xlabel('Time')
        plt.tight_layout()
        plt.savefig("var_prediction.png")
        plt.close(fig)
        
        logger.info("VAR Order Book Predictor demonstration completed")
        
    except Exception as e:
        logger.error(f"Error in VAR model demonstration: {str(e)}")
    
    # Try LSTM model if TensorFlow is available
    try:
        from tensorflow.keras.models import Sequential
        
        logger.info("TensorFlow is available, demonstrating LSTM Order Book Predictor")
        
        # Set up features and target
        feature_cols = ['mid_price', 'spread', 'order_book_imbalance', 'volume',
                      'mid_price_lag_1', 'spread_lag_1', 'order_book_imbalance_lag_1']
        target_cols = ['mid_price']
        
        # Create LSTM predictor
        lstm_model = LSTM_OrderBookPredictor(
            name="LSTM Order Book Predictor",
            prediction_horizon=5,   # Predict 5 steps ahead
            lookback_window=10,     # Use 10 time steps of history
            lstm_units=[64, 32]     # Two LSTM layers with 64 and 32 units
        )
        
        # Prepare data for training
        train_data = order_book_data[feature_cols + target_cols].copy()
        
        # Split data for testing later
        train_size = int(len(train_data) * 0.8)
        train_set = train_data[:train_size]
        test_set = train_data[train_size:]
        
        # Train the model with reduced epochs for example
        result = lstm_model.train(
            train_set, 
            target_columns=target_cols,
            epochs=10,            # Use fewer epochs for example
            batch_size=32,
            validation_split=0.2
        )
        
        # Print training results
        logger.info(f"LSTM Model Training Results:")
        logger.info(f"  Overall R²: {result['overall_r2']:.4f}, RMSE: {result['overall_rmse']:.6f}")
        logger.info(f"  Training epochs: {result['epochs']}")
        logger.info(f"  Final loss: {result['final_loss']:.6f}, Val loss: {result['final_val_loss']:.6f}")
        
        # Make predictions using the last part of the data
        last_data = test_set.iloc[-20:]
        predictions = lstm_model.predict(last_data)
        
        # Plot actual vs predicted
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Create x-axis for actual data
        actual_times = order_book_data.index[-20:]
        
        # Create x-axis for predicted data
        if isinstance(order_book_data.index, pd.DatetimeIndex):
            last_time = order_book_data.index[-1]
            time_diff = order_book_data.index[-1] - order_book_data.index[-2]
            pred_times = [last_time + (i+1)*time_diff for i in range(len(predictions))]
        else:
            # If not datetime index, just use sequential numbers
            last_idx = len(order_book_data) - 1
            pred_times = range(last_idx + 1, last_idx + 1 + len(predictions))
        
        # Plot actual data (last 20 points)
        ax.plot(actual_times, order_book_data['mid_price'].values[-20:], 
               color='blue', label='Actual')
        
        # Plot predicted data
        ax.plot(pred_times, predictions['mid_price'].values, 
               color='red', marker='o', linestyle='--', label='LSTM Prediction')
        
        ax.set_title('LSTM Price Prediction')
        ax.set_ylabel('Mid Price')
        ax.set_xlabel('Time')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig("lstm_prediction.png")
        plt.close(fig)
        
        logger.info("LSTM Order Book Predictor demonstration completed")
        
    except ImportError:
        logger.info("TensorFlow not available, skipping LSTM model demonstration")
    except Exception as e:
        logger.error(f"Error in LSTM model demonstration: {str(e)}")

def main():
    """Main function to demonstrate market microstructure models."""
    
    logger.info("Starting Market Microstructure Models demonstration")
    
    # Generate synthetic data
    data = generate_synthetic_data(n_samples=200)
    
    # Demonstrate linear impact model
    linear_model = demo_linear_impact_model(data)
    
    # Demonstrate nonlinear impact model
    nonlinear_model = demo_nonlinear_impact_model(data)
    
    # Demonstrate ML impact model
    ml_model = demo_ml_impact_model(data)
    
    # Demonstrate order book predictor
    demo_order_book_predictor(data)
    
    logger.info("Market Microstructure Models demonstration completed")

if __name__ == "__main__":
    main() 