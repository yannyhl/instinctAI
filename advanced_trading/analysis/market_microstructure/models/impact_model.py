"""
Market Impact Models

This module provides models for estimating and predicting the market impact of orders.
Market impact is the effect that a market participant has when buying or selling an asset.
It is the extent to which the buying or selling moves the price against the buyer or seller.

The module includes:
- Base ImpactModel class defining the interface
- LinearImpactModel implementing the classic square-root law
- NonlinearImpactModel for more complex impact functions
- MLImpactModel using machine learning for impact prediction
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Tuple, Any, Callable
from abc import ABC, abstractmethod
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os
import logging

# Setup logging
logger = logging.getLogger(__name__)

class ImpactModel(ABC):
    """
    Abstract base class for market impact models.
    
    Market impact models predict how a trade of a given size will affect the market price.
    This is crucial for optimizing execution strategies and estimating transaction costs.
    """
    
    def __init__(self, name: str, market_type: str = "limit_order_book"):
        """
        Initialize the impact model.
        
        Args:
            name: Name of the model
            market_type: Type of market (e.g., "limit_order_book", "dealer", "continuous_auction")
        """
        self.name = name
        self.market_type = market_type
        self.is_trained = False
        self.metadata = {}
        
    @abstractmethod
    def predict_impact(self, order_size: float, market_state: Dict[str, Any], side: str) -> float:
        """
        Predict the market impact for a given order size and market state.
        
        Args:
            order_size: Size of the order (normalized or absolute)
            market_state: Dictionary containing market state variables
            side: Trade direction ("buy" or "sell")
            
        Returns:
            Predicted price impact as a fraction of the mid price
        """
        pass
    
    @abstractmethod
    def train(self, trade_data: pd.DataFrame, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Train the impact model using historical trade and market data.
        
        Args:
            trade_data: DataFrame containing trade data (size, time, etc.)
            market_data: DataFrame containing market state before each trade
            
        Returns:
            Dictionary with training results and metrics
        """
        pass
    
    def save(self, filepath: str) -> None:
        """
        Save the model to disk.
        
        Args:
            filepath: Path where to save the model
        """
        try:
            model_data = {
                "name": self.name,
                "market_type": self.market_type,
                "is_trained": self.is_trained,
                "metadata": self.metadata,
                "model_params": self._get_model_params()
            }
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            joblib.dump(model_data, filepath)
            logger.info(f"Impact model saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save model: {str(e)}")
            raise
    
    def load(self, filepath: str) -> None:
        """
        Load the model from disk.
        
        Args:
            filepath: Path from where to load the model
        """
        try:
            model_data = joblib.load(filepath)
            
            self.name = model_data["name"]
            self.market_type = model_data["market_type"]
            self.is_trained = model_data["is_trained"]
            self.metadata = model_data["metadata"]
            self._set_model_params(model_data["model_params"])
            
            logger.info(f"Impact model loaded from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise
    
    @abstractmethod
    def _get_model_params(self) -> Dict[str, Any]:
        """Get model parameters for serialization"""
        pass
    
    @abstractmethod
    def _set_model_params(self, params: Dict[str, Any]) -> None:
        """Set model parameters after deserialization"""
        pass


class LinearImpactModel(ImpactModel):
    """
    Linear impact model implementing the classic square-root law.
    
    The price impact is modeled as:
    Impact = Y * sigma * (order_size / ADV)^alpha
    
    Where:
    - Y is a market-specific constant
    - sigma is the asset volatility
    - ADV is the average daily volume
    - alpha is typically 0.5 (square root)
    """
    
    def __init__(self, name: str = "Square-Root Impact Model", alpha: float = 0.5, Y: float = 1.0):
        """
        Initialize the linear impact model.
        
        Args:
            name: Name of the model
            alpha: Exponent in the impact formula, typically 0.5
            Y: Market-specific constant
        """
        super().__init__(name, "limit_order_book")
        self.alpha = alpha
        self.Y = Y
        self.is_trained = True  # Linear models don't require explicit training
        
    def predict_impact(self, order_size: float, market_state: Dict[str, Any], side: str) -> float:
        """
        Predict market impact using the square-root law.
        
        Args:
            order_size: Size of the order
            market_state: Dictionary with keys:
                - 'volatility': Asset volatility (daily)
                - 'adv': Average daily volume
                - Other market state variables (not used in this model)
            side: Trade direction ("buy" or "sell")
            
        Returns:
            Predicted price impact as a fraction of the mid price
        """
        try:
            volatility = market_state.get('volatility', 0.02)  # Default to 2% daily volatility
            adv = market_state.get('adv', order_size * 100)    # Default to order being 1% of ADV
            
            # Calculate relative order size
            relative_size = order_size / adv
            
            # Apply square-root law
            impact = self.Y * volatility * np.power(relative_size, self.alpha)
            
            # Adjust sign based on trade direction
            if side.lower() == "sell":
                impact = -impact
                
            return impact
        except Exception as e:
            logger.error(f"Error predicting impact: {str(e)}")
            # Return a conservative impact estimate on error
            return 0.001 * (1 if side.lower() == "buy" else -1)
    
    def train(self, trade_data: pd.DataFrame, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calibrate the model parameters using historical data.
        
        Args:
            trade_data: DataFrame with columns:
                - 'size': Order size
                - 'impact': Observed price impact
                - 'side': Trade direction
            market_data: DataFrame with columns:
                - 'volatility': Asset volatility
                - 'adv': Average daily volume
                
        Returns:
            Dictionary with training results
        """
        try:
            # Merge data
            data = pd.concat([trade_data, market_data], axis=1)
            
            # Calculate relative order size
            data['relative_size'] = data['size'] / data['adv']
            
            # Convert side to sign
            data['impact_sign'] = data['side'].apply(lambda x: 1 if x.lower() == "buy" else -1)
            data['signed_impact'] = data['impact'] * data['impact_sign']
            
            # Fit model to find optimal Y (keeping alpha fixed)
            def objective_function(Y_value):
                predicted = Y_value * data['volatility'] * np.power(data['relative_size'], self.alpha)
                return mean_squared_error(data['signed_impact'], predicted)
            
            # Simple grid search for Y
            best_Y = 1.0
            best_mse = objective_function(best_Y)
            
            for Y_candidate in np.linspace(0.1, 5.0, 50):
                mse = objective_function(Y_candidate)
                if mse < best_mse:
                    best_mse = mse
                    best_Y = Y_candidate
            
            self.Y = best_Y
            self.is_trained = True
            
            # Calculate metrics
            predicted_impact = self.Y * data['volatility'] * np.power(data['relative_size'], self.alpha)
            r2 = r2_score(data['signed_impact'], predicted_impact)
            rmse = np.sqrt(best_mse)
            
            results = {
                "Y": self.Y,
                "alpha": self.alpha,
                "rmse": rmse,
                "r2": r2,
                "mean_impact": data['impact'].mean()
            }
            
            self.metadata = {
                "training_data_size": len(data),
                "training_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "metrics": results
            }
            
            logger.info(f"Linear impact model calibrated with Y={self.Y}, R²={r2:.4f}")
            return results
            
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            raise
    
    def _get_model_params(self) -> Dict[str, Any]:
        """Get model parameters for serialization"""
        return {
            "alpha": self.alpha,
            "Y": self.Y
        }
    
    def _set_model_params(self, params: Dict[str, Any]) -> None:
        """Set model parameters after deserialization"""
        self.alpha = params.get("alpha", 0.5)
        self.Y = params.get("Y", 1.0)


class NonlinearImpactModel(ImpactModel):
    """
    Nonlinear impact model with transient and permanent components.
    
    This model separates market impact into:
    - Permanent impact: Long-term price change after the trade
    - Temporary impact: Short-term price change that decays over time
    
    The model accounts for market resilience and nonlinear scaling with order size.
    """
    
    def __init__(self, name: str = "Nonlinear Impact Model"):
        """
        Initialize the nonlinear impact model.
        
        Args:
            name: Name of the model
        """
        super().__init__(name, "limit_order_book")
        
        # Permanent impact parameters
        self.perm_factor = 1.0
        self.perm_exponent = 0.6
        
        # Temporary impact parameters
        self.temp_factor = 1.5
        self.temp_exponent = 0.85
        
        # Decay parameters
        self.decay_factor = 0.5
        self.decay_exponent = 1.0
        
        # Market characteristics
        self.market_factors = {
            "resilience": 0.1,  # Market resilience (recovery speed)
            "depth_factor": 1.0  # Scaling factor for market depth
        }
        
    def predict_impact(self, order_size: float, market_state: Dict[str, Any], side: str) -> float:
        """
        Predict market impact using the nonlinear model.
        
        Args:
            order_size: Size of the order
            market_state: Dictionary with market state variables:
                - 'volatility': Asset volatility (daily)
                - 'adv': Average daily volume
                - 'spread': Current bid-ask spread
                - 'depth': Market depth at best levels
                - 'order_book_imbalance': Imbalance between buy/sell sides
            side: Trade direction ("buy" or "sell")
            
        Returns:
            Predicted price impact as a fraction of the mid price
        """
        try:
            # Extract market state variables with defaults
            volatility = market_state.get('volatility', 0.02)
            adv = market_state.get('adv', order_size * 100)
            spread = market_state.get('spread', 0.0001)
            depth = market_state.get('depth', order_size * 10)
            imbalance = market_state.get('order_book_imbalance', 0.0)
            
            # Calculate relative order size
            relative_size = order_size / adv
            
            # Account for order book imbalance (can reduce or increase impact)
            # Positive imbalance means more bids than asks (buying pressure)
            side_factor = 1 if side.lower() == "buy" else -1
            imbalance_adjustment = 1.0 - (imbalance * side_factor * 0.5)
            
            # Calculate permanent impact component
            perm_impact = self.perm_factor * volatility * np.power(relative_size, self.perm_exponent)
            
            # Calculate temporary impact component, considering market depth
            depth_ratio = order_size / (depth * self.market_factors["depth_factor"])
            temp_impact = self.temp_factor * spread * np.power(depth_ratio, self.temp_exponent)
            
            # Apply imbalance adjustment
            total_impact = (perm_impact + temp_impact) * imbalance_adjustment
            
            # Apply side direction
            if side.lower() == "sell":
                total_impact = -total_impact
                
            return total_impact
            
        except Exception as e:
            logger.error(f"Error predicting impact: {str(e)}")
            # Return a conservative impact estimate on error
            return 0.002 * (1 if side.lower() == "buy" else -1)
            
    def train(self, trade_data: pd.DataFrame, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Train the nonlinear impact model using historical data.
        
        Args:
            trade_data: DataFrame with columns:
                - 'size': Order size
                - 'immediate_impact': Observed immediate price impact
                - 'permanent_impact': Observed permanent price impact
                - 'side': Trade direction
            market_data: DataFrame with columns:
                - 'volatility': Asset volatility
                - 'adv': Average daily volume
                - 'spread': Bid-ask spread
                - 'depth': Market depth
                - 'order_book_imbalance': Order book imbalance
                
        Returns:
            Dictionary with training results
        """
        try:
            # Merge data
            data = pd.concat([trade_data, market_data], axis=1)
            
            # Calculate relative order size and depth ratio
            data['relative_size'] = data['size'] / data['adv']
            data['depth_ratio'] = data['size'] / data['depth']
            
            # Convert side to sign
            data['impact_sign'] = data['side'].apply(lambda x: 1 if x.lower() == "buy" else -1)
            data['signed_immediate_impact'] = data['immediate_impact'] * data['impact_sign']
            data['signed_permanent_impact'] = data['permanent_impact'] * data['impact_sign']
            
            # Define objective function for optimization
            def objective_function(params):
                perm_factor, perm_exp, temp_factor, temp_exp = params
                
                # Calculate permanent impact component
                perm_impact = perm_factor * data['volatility'] * np.power(data['relative_size'], perm_exp)
                
                # Calculate temporary impact component
                temp_impact = temp_factor * data['spread'] * np.power(data['depth_ratio'], temp_exp)
                
                # Apply imbalance adjustment
                imbalance_adjustment = 1.0 - (data['order_book_imbalance'] * data['impact_sign'] * 0.5)
                predicted_impact = (perm_impact + temp_impact) * imbalance_adjustment
                
                # Calculate MSE for both immediate and permanent impact
                immediate_mse = mean_squared_error(data['signed_immediate_impact'], 
                                                 predicted_impact)
                permanent_mse = mean_squared_error(data['signed_permanent_impact'], 
                                                 perm_impact)
                
                # Weighted combination
                return 0.7 * immediate_mse + 0.3 * permanent_mse
            
            # Simple grid search for parameters
            best_params = [self.perm_factor, self.perm_exponent, 
                          self.temp_factor, self.temp_exponent]
            best_mse = objective_function(best_params)
            
            # Define parameter ranges
            param_ranges = [
                np.linspace(0.5, 2.0, 4),   # perm_factor
                np.linspace(0.3, 0.9, 4),   # perm_exponent
                np.linspace(0.5, 3.0, 4),   # temp_factor
                np.linspace(0.5, 1.2, 4)    # temp_exponent
            ]
            
            # Grid search (simplified for brevity)
            from itertools import product
            for params in product(*param_ranges):
                mse = objective_function(params)
                if mse < best_mse:
                    best_mse = mse
                    best_params = params
            
            # Update model parameters
            self.perm_factor, self.perm_exponent, self.temp_factor, self.temp_exponent = best_params
            self.is_trained = True
            
            # Calculate final predictions and metrics
            perm_impact = self.perm_factor * data['volatility'] * np.power(data['relative_size'], self.perm_exponent)
            temp_impact = self.temp_factor * data['spread'] * np.power(data['depth_ratio'], self.temp_exponent)
            imbalance_adjustment = 1.0 - (data['order_book_imbalance'] * data['impact_sign'] * 0.5)
            predicted_impact = (perm_impact + temp_impact) * imbalance_adjustment
            
            r2_immediate = r2_score(data['signed_immediate_impact'], predicted_impact)
            r2_permanent = r2_score(data['signed_permanent_impact'], perm_impact)
            rmse = np.sqrt(best_mse)
            
            results = {
                "perm_factor": self.perm_factor,
                "perm_exponent": self.perm_exponent,
                "temp_factor": self.temp_factor,
                "temp_exponent": self.temp_exponent,
                "rmse": rmse,
                "r2_immediate": r2_immediate,
                "r2_permanent": r2_permanent
            }
            
            self.metadata = {
                "training_data_size": len(data),
                "training_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "metrics": results
            }
            
            logger.info(f"Nonlinear impact model trained with R²={r2_immediate:.4f} (immediate)")
            return results
            
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            raise
    
    def _get_model_params(self) -> Dict[str, Any]:
        """Get model parameters for serialization"""
        return {
            "perm_factor": self.perm_factor,
            "perm_exponent": self.perm_exponent,
            "temp_factor": self.temp_factor,
            "temp_exponent": self.temp_exponent,
            "decay_factor": self.decay_factor,
            "decay_exponent": self.decay_exponent,
            "market_factors": self.market_factors
        }
    
    def _set_model_params(self, params: Dict[str, Any]) -> None:
        """Set model parameters after deserialization"""
        self.perm_factor = params.get("perm_factor", 1.0)
        self.perm_exponent = params.get("perm_exponent", 0.6)
        self.temp_factor = params.get("temp_factor", 1.5)
        self.temp_exponent = params.get("temp_exponent", 0.85)
        self.decay_factor = params.get("decay_factor", 0.5)
        self.decay_exponent = params.get("decay_exponent", 1.0)
        self.market_factors = params.get("market_factors", {
            "resilience": 0.1,
            "depth_factor": 1.0
        })


class MLImpactModel(ImpactModel):
    """
    Machine learning-based market impact model.
    
    This model uses gradient boosting or random forest to predict market impact
    based on a wide range of features from market state and order characteristics.
    """
    
    def __init__(self, name: str = "ML Impact Model", model_type: str = "gradient_boosting"):
        """
        Initialize the ML impact model.
        
        Args:
            name: Name of the model
            model_type: Type of ML model to use ("gradient_boosting" or "random_forest")
        """
        super().__init__(name, "limit_order_book")
        self.model_type = model_type
        self.model = None
        self.feature_scaler = StandardScaler()
        self.required_features = [
            'volatility', 'adv', 'spread', 'depth', 'order_book_imbalance',
            'relative_size', 'market_volume', 'time_of_day'
        ]
        self.feature_importance = {}
    
    def predict_impact(self, order_size: float, market_state: Dict[str, Any], side: str) -> float:
        """
        Predict market impact using the trained ML model.
        
        Args:
            order_size: Size of the order
            market_state: Dictionary with market state variables
            side: Trade direction ("buy" or "sell")
            
        Returns:
            Predicted price impact as a fraction of the mid price
        """
        if not self.is_trained or self.model is None:
            logger.warning("Model not trained yet, using fallback linear model")
            # Fallback to a simple linear model
            fallback = LinearImpactModel()
            return fallback.predict_impact(order_size, market_state, side)
        
        try:
            # Prepare features
            features = {}
            
            # Add basic features
            features['volatility'] = market_state.get('volatility', 0.02)
            features['adv'] = market_state.get('adv', order_size * 100)
            features['spread'] = market_state.get('spread', 0.0001)
            features['depth'] = market_state.get('depth', order_size * 10)
            features['order_book_imbalance'] = market_state.get('order_book_imbalance', 0.0)
            features['relative_size'] = order_size / features['adv']
            features['market_volume'] = market_state.get('market_volume', features['adv'] * 0.1)
            features['time_of_day'] = market_state.get('time_of_day', 0.5)  # Normalized time (0-1)
            
            # Add additional features if available
            for key, value in market_state.items():
                if key not in features and key in self.feature_importance:
                    features[key] = value
            
            # Convert to DataFrame
            df = pd.DataFrame([features])
            
            # Ensure all required features are present
            for feature in self.required_features:
                if feature not in df.columns:
                    df[feature] = 0.0
            
            # Apply scaling
            features_scaled = self.feature_scaler.transform(df)
            
            # Predict impact
            impact = self.model.predict(features_scaled)[0]
            
            # Apply side direction
            if side.lower() == "sell":
                impact = -impact
                
            return impact
            
        except Exception as e:
            logger.error(f"Error predicting impact with ML model: {str(e)}")
            # Fallback to a simple model on error
            fallback = LinearImpactModel()
            return fallback.predict_impact(order_size, market_state, side)
    
    def train(self, trade_data: pd.DataFrame, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Train the ML impact model using historical data.
        
        Args:
            trade_data: DataFrame with columns:
                - 'size': Order size
                - 'impact': Observed price impact
                - 'side': Trade direction
            market_data: DataFrame with market state variables
                
        Returns:
            Dictionary with training results
        """
        try:
            # Merge data
            data = pd.concat([trade_data, market_data], axis=1)
            
            # Add derived features
            if 'adv' in data.columns and 'size' in data.columns:
                data['relative_size'] = data['size'] / data['adv']
            
            # Convert side to sign
            data['impact_sign'] = data['side'].apply(lambda x: 1 if x.lower() == "buy" else -1)
            data['signed_impact'] = data['impact'] * data['impact_sign']
            
            # Select features and target
            features = [col for col in data.columns if col not in 
                       ['impact', 'side', 'impact_sign', 'signed_impact']]
            X = data[features]
            y = data['signed_impact']
            
            # Save required features
            self.required_features = features
            
            # Scale features
            X_scaled = self.feature_scaler.fit_transform(X)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42)
            
            # Create and train model
            if self.model_type == "gradient_boosting":
                self.model = GradientBoostingRegressor(
                    n_estimators=100,
                    learning_rate=0.1,
                    max_depth=3,
                    random_state=42
                )
            else:  # random_forest
                self.model = RandomForestRegressor(
                    n_estimators=100,
                    max_depth=5,
                    random_state=42
                )
            
            self.model.fit(X_train, y_train)
            self.is_trained = True
            
            # Calculate predictions and metrics
            y_pred = self.model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)
            
            # Get feature importance
            if hasattr(self.model, 'feature_importances_'):
                importance = self.model.feature_importances_
                self.feature_importance = {feat: imp for feat, imp in zip(features, importance)}
            
            results = {
                "rmse": rmse,
                "r2": r2,
                "mse": mse,
                "feature_importance": self.feature_importance
            }
            
            self.metadata = {
                "training_data_size": len(data),
                "testing_data_size": len(y_test),
                "training_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "metrics": results,
                "model_type": self.model_type
            }
            
            logger.info(f"ML impact model trained with R²={r2:.4f}")
            return results
            
        except Exception as e:
            logger.error(f"Error training ML model: {str(e)}")
            raise
    
    def _get_model_params(self) -> Dict[str, Any]:
        """Get model parameters for serialization"""
        if not self.is_trained:
            return {
                "model_type": self.model_type,
                "is_trained": False
            }
        
        return {
            "model_type": self.model_type,
            "model": self.model,
            "feature_scaler": self.feature_scaler,
            "required_features": self.required_features,
            "feature_importance": self.feature_importance
        }
    
    def _set_model_params(self, params: Dict[str, Any]) -> None:
        """Set model parameters after deserialization"""
        self.model_type = params.get("model_type", "gradient_boosting")
        
        if "model" in params:
            self.model = params["model"]
            self.feature_scaler = params.get("feature_scaler", StandardScaler())
            self.required_features = params.get("required_features", [])
            self.feature_importance = params.get("feature_importance", {}) 