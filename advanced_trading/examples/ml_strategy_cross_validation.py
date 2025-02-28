#!/usr/bin/env python
"""
ML Strategy Cross-Validation Example

This script demonstrates how to use the cross-validation framework
with machine learning trading strategies in the Instinct AI system.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import logging
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# Import Instinct AI modules
from advanced_trading.utils.cross_validation import (
    TimeSeriesCrossValidator, 
    cross_validate_strategy,
    evaluate_predictions,
    feature_importance_cv,
    plot_feature_importance,
    plot_cv_predictions
)
from advanced_trading.utils.metrics.performance_metrics import (
    calculate_returns_metrics,
    calculate_drawdown_metrics,
    calculate_trade_metrics
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_sample_data():
    """
    Load sample data for demonstration.
    In a real scenario, you would use the data_loader module.
    """
    # For demonstration, we'll create synthetic data
    # In a real scenario, you would load actual market data
    np.random.seed(42)
    
    # Create date range
    dates = pd.date_range(start='2020-01-01', end='2022-12-31', freq='D')
    
    # Create features
    n_samples = len(dates)
    
    # Price series with trend and noise
    price = 100 + np.cumsum(np.random.normal(0.05, 1, n_samples))
    
    # Create features
    df = pd.DataFrame({
        'price': price,
        'returns': np.random.normal(0, 1, n_samples),
        'volume': np.random.exponential(1, n_samples) * 1000,
        'volatility': np.random.gamma(2, 2, n_samples),
        'rsi': np.random.uniform(0, 100, n_samples),
        'macd': np.random.normal(0, 1, n_samples),
        'bb_upper': price + np.random.uniform(1, 5, n_samples),
        'bb_lower': price - np.random.uniform(1, 5, n_samples),
        'atr': np.random.exponential(1, n_samples),
        'adx': np.random.uniform(0, 100, n_samples),
    }, index=dates)
    
    # Add some autocorrelation to make it more realistic
    for col in df.columns:
        if col != 'price':
            df[col] = df[col].rolling(5).mean().fillna(df[col])
    
    # Create target: 1 if price goes up in next 5 days, 0 otherwise
    df['target'] = (df['price'].shift(-5) > df['price']).astype(int)
    
    # Add market regime column for regime-based CV
    df['regime'] = np.where(df['volatility'] > df['volatility'].median(), 'high_vol', 'low_vol')
    
    # Drop NaN values
    df = df.dropna()
    
    return df

def create_ml_strategy(X_train, y_train, model_type='classifier', **params):
    """
    Create and train a machine learning strategy.
    
    Args:
        X_train: Training features
        y_train: Training target
        model_type: 'classifier' or 'regressor'
        **params: Additional parameters for the model
        
    Returns:
        Trained model
    """
    if model_type == 'classifier':
        model = Pipeline([
            ('scaler', StandardScaler()),
            ('model', RandomForestClassifier(
                n_estimators=params.get('n_estimators', 100),
                max_depth=params.get('max_depth', 5),
                random_state=42
            ))
        ])
    else:  # regressor
        model = Pipeline([
            ('scaler', StandardScaler()),
            ('model', GradientBoostingRegressor(
                n_estimators=params.get('n_estimators', 100),
                max_depth=params.get('max_depth', 3),
                learning_rate=params.get('learning_rate', 0.1),
                random_state=42
            ))
        ])
    
    model.fit(X_train, y_train)
    return model

def custom_scoring_function(y_true, y_pred):
    """
    Custom scoring function for trading strategies.
    
    This function calculates a custom score based on precision and recall,
    with a higher weight on precision to minimize false positives.
    
    Args:
        y_true: True values
        y_pred: Predicted values
        
    Returns:
        Custom score
    """
    from sklearn.metrics import precision_score, recall_score
    
    # For classification models
    if set(np.unique(y_true)) == {0, 1}:
        # Convert probabilities to binary predictions
        if y_pred.max() <= 1 and y_pred.min() >= 0 and not np.array_equal(y_pred, y_pred.astype(bool)):
            y_pred_binary = (y_pred > 0.5).astype(int)
        else:
            y_pred_binary = y_pred
            
        precision = precision_score(y_true, y_pred_binary, zero_division=0)
        recall = recall_score(y_true, y_pred_binary, zero_division=0)
        
        # Custom score with higher weight on precision
        return 0.7 * precision + 0.3 * recall
    
    # For regression models
    else:
        # Calculate directional accuracy
        direction_true = np.sign(y_true)
        direction_pred = np.sign(y_pred)
        directional_accuracy = np.mean(direction_true == direction_pred)
        
        # Calculate mean absolute error
        mae = np.mean(np.abs(y_true - y_pred))
        
        # Normalize MAE
        max_abs_true = np.max(np.abs(y_true))
        normalized_mae = mae / max_abs_true if max_abs_true > 0 else mae
        
        # Custom score
        return directional_accuracy - normalized_mae

def generate_trading_signals(predictions, threshold=0.5):
    """
    Generate trading signals from model predictions.
    
    Args:
        predictions: Model predictions
        threshold: Threshold for classification models
        
    Returns:
        DataFrame with trading signals
    """
    signals = pd.Series(index=predictions.index)
    
    # For classification models (probabilities)
    if predictions.max() <= 1 and predictions.min() >= 0:
        signals = pd.Series(0, index=predictions.index)
        signals[predictions > threshold] = 1
        signals[predictions < (1 - threshold)] = -1
    # For regression models
    else:
        signals = np.sign(predictions)
    
    return signals

def calculate_strategy_returns(signals, price_series, transaction_cost=0.001):
    """
    Calculate strategy returns based on signals.
    
    Args:
        signals: Trading signals (-1, 0, 1)
        price_series: Price series
        transaction_cost: Transaction cost as a fraction of price
        
    Returns:
        DataFrame with strategy performance
    """
    # Calculate price returns
    price_returns = price_series.pct_change().fillna(0)
    
    # Shift signals to avoid lookahead bias
    strategy_signals = signals.shift(1).fillna(0)
    
    # Calculate strategy returns
    strategy_returns = strategy_signals * price_returns
    
    # Calculate transaction costs
    signal_changes = strategy_signals.diff().fillna(0).abs()
    transaction_costs = signal_changes * transaction_cost
    
    # Subtract transaction costs
    strategy_returns = strategy_returns - transaction_costs
    
    # Calculate cumulative returns
    cumulative_returns = (1 + strategy_returns).cumprod()
    
    return pd.DataFrame({
        'signals': strategy_signals,
        'price_returns': price_returns,
        'strategy_returns': strategy_returns,
        'cumulative_returns': cumulative_returns
    })

def main():
    """Main function to demonstrate cross-validation of ML strategies."""
    logger.info("Loading sample data...")
    df = load_sample_data()
    
    # Prepare features and target
    X = df.drop(['price', 'target', 'regime'], axis=1)
    y = df['target']
    price = df['price']
    
    # Create output directory for results
    output_dir = os.path.join('results', f'ml_cv_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info("Demonstrating different cross-validation methods...")
    
    # 1. Purged K-Fold Cross-Validation
    logger.info("\n1. Purged K-Fold Cross-Validation")
    cv_purged = TimeSeriesCrossValidator(
        cv_method="purged_kfold",
        n_splits=5,
        gap_size=5,  # 5-day gap between train and test
        embargo_size=2  # 2-day embargo after test
    )
    
    # Visualize the splits
    fig_purged = cv_purged.plot_splits(X)
    fig_purged.suptitle("Purged K-Fold Cross-Validation Splits")
    fig_purged.savefig(os.path.join(output_dir, 'purged_kfold_splits.png'))
    
    # Cross-validate the strategy
    results_purged = cross_validate_strategy(
        strategy_fn=create_ml_strategy,
        X=X,
        y=y,
        cv=cv_purged,
        strategy_params={'n_estimators': 100, 'max_depth': 4},
        scoring_fn=custom_scoring_function,
        return_models=True,
        return_predictions=True,
        verbose=True,
        save_dir=os.path.join(output_dir, 'purged_kfold')
    )
    
    logger.info(f"Purged K-Fold CV Results: Mean Score = {results_purged['mean_score']:.4f}, Std = {results_purged['std_score']:.4f}")
    
    # 2. Walk-Forward Cross-Validation
    logger.info("\n2. Walk-Forward Cross-Validation")
    cv_walk_forward = TimeSeriesCrossValidator(
        cv_method="walk_forward",
        n_splits=5,
        min_train_size=100,
        test_size=50,
        gap_size=5
    )
    
    # Visualize the splits
    fig_walk_forward = cv_walk_forward.plot_splits(X)
    fig_walk_forward.suptitle("Walk-Forward Cross-Validation Splits")
    fig_walk_forward.savefig(os.path.join(output_dir, 'walk_forward_splits.png'))
    
    # Cross-validate the strategy
    results_walk_forward = cross_validate_strategy(
        strategy_fn=create_ml_strategy,
        X=X,
        y=y,
        cv=cv_walk_forward,
        strategy_params={'model_type': 'regressor', 'n_estimators': 100},
        scoring_fn=custom_scoring_function,
        return_models=True,
        return_predictions=True,
        verbose=True,
        save_dir=os.path.join(output_dir, 'walk_forward')
    )
    
    logger.info(f"Walk-Forward CV Results: Mean Score = {results_walk_forward['mean_score']:.4f}, Std = {results_walk_forward['std_score']:.4f}")
    
    # 3. Regime-Based Cross-Validation
    logger.info("\n3. Regime-Based Cross-Validation")
    cv_regime = TimeSeriesCrossValidator(
        cv_method="regime_based",
        n_splits=3,
        regime_column="regime"
    )
    
    # Add regime column back to X for regime-based CV
    X_with_regime = X.copy()
    X_with_regime['regime'] = df['regime']
    
    # Visualize the splits
    fig_regime = cv_regime.plot_splits(X_with_regime)
    fig_regime.suptitle("Regime-Based Cross-Validation Splits")
    fig_regime.savefig(os.path.join(output_dir, 'regime_based_splits.png'))
    
    # Cross-validate the strategy
    results_regime = cross_validate_strategy(
        strategy_fn=create_ml_strategy,
        X=X_with_regime,
        y=y,
        cv=cv_regime,
        strategy_params={'n_estimators': 100, 'max_depth': 4},
        scoring_fn=custom_scoring_function,
        return_models=True,
        return_predictions=True,
        verbose=True,
        save_dir=os.path.join(output_dir, 'regime_based')
    )
    
    logger.info(f"Regime-Based CV Results: Mean Score = {results_regime['mean_score']:.4f}, Std = {results_regime['std_score']:.4f}")
    
    # 4. Feature Importance Analysis
    logger.info("\n4. Feature Importance Analysis")
    importance_df = feature_importance_cv(
        strategy_fn=create_ml_strategy,
        X=X,
        y=y,
        cv=cv_purged,
        strategy_params={'n_estimators': 100, 'max_depth': 4},
        importance_method="permutation",
        n_repeats=5,
        random_state=42
    )
    
    # Save feature importance
    importance_df.to_csv(os.path.join(output_dir, 'feature_importance.csv'))
    
    # Plot feature importance
    fig_importance = plot_feature_importance(importance_df)
    fig_importance.savefig(os.path.join(output_dir, 'feature_importance.png'))
    
    # 5. Trading Strategy Evaluation
    logger.info("\n5. Trading Strategy Evaluation")
    
    # Generate trading signals from the best model's predictions
    predictions = results_purged['predictions']
    signals = generate_trading_signals(predictions, threshold=0.6)
    
    # Calculate strategy returns
    strategy_performance = calculate_strategy_returns(signals, price)
    
    # Save strategy performance
    strategy_performance.to_csv(os.path.join(output_dir, 'strategy_performance.csv'))
    
    # Plot strategy performance
    fig, ax = plt.subplots(3, 1, figsize=(15, 12), sharex=True)
    
    # Plot price
    ax[0].plot(price.index, price)
    ax[0].set_title('Price')
    ax[0].set_ylabel('Price')
    
    # Plot signals
    ax[1].plot(strategy_performance.index, strategy_performance['signals'])
    ax[1].set_title('Trading Signals')
    ax[1].set_ylabel('Signal')
    
    # Plot cumulative returns
    ax[2].plot(strategy_performance.index, strategy_performance['cumulative_returns'])
    ax[2].set_title('Cumulative Returns')
    ax[2].set_ylabel('Returns')
    ax[2].set_xlabel('Date')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'strategy_performance.png'))
    
    # Calculate performance metrics
    returns_metrics = calculate_returns_metrics(strategy_performance['strategy_returns'])
    drawdown_metrics = calculate_drawdown_metrics(strategy_performance['strategy_returns'])
    
    # Create trades from signals
    trades = pd.DataFrame({
        'entry_date': strategy_performance.index[strategy_performance['signals'].diff() != 0],
        'exit_date': strategy_performance.index[strategy_performance['signals'].diff().shift(-1) != 0],
        'direction': strategy_performance['signals'][strategy_performance['signals'].diff() != 0],
        'entry_price': price[strategy_performance['signals'].diff() != 0],
        'exit_price': price[strategy_performance['signals'].diff().shift(-1) != 0]
    })
    
    # Calculate trade metrics
    trade_metrics = calculate_trade_metrics(trades)
    
    # Combine all metrics
    all_metrics = {**returns_metrics, **drawdown_metrics, **trade_metrics}
    
    # Save metrics
    pd.Series(all_metrics).to_csv(os.path.join(output_dir, 'performance_metrics.csv'))
    
    # Print summary
    logger.info("\nStrategy Performance Summary:")
    logger.info(f"Annual Return: {returns_metrics['annual_return']:.2%}")
    logger.info(f"Sharpe Ratio: {returns_metrics['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {drawdown_metrics['max_drawdown']:.2%}")
    logger.info(f"Calmar Ratio: {drawdown_metrics['calmar_ratio']:.2f}")
    logger.info(f"Win Rate: {trade_metrics['win_rate']:.2%}")
    logger.info(f"Profit Factor: {trade_metrics['profit_factor']:.2f}")
    
    logger.info(f"\nResults saved to {output_dir}")

if __name__ == "__main__":
    main() 