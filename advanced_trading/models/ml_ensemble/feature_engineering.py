"""
Feature Engineering
------------------
Comprehensive feature engineering for financial time series data.
This module provides functions to create and transform features for ML models,
including technical indicators, statistical features, and time-based features.

Features are grouped by categories to help with feature selection and importance analysis.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
import talib
from scipy import stats
import logging
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif, f_regression, mutual_info_regression

# Get the logger
logger = logging.getLogger(__name__)

class FeatureEngineer:
    """
    Comprehensive feature engineering for financial time series data.
    
    This class creates features useful for predicting market movements,
    including technical indicators, statistical features, and derivatives
    of price action, volume, and other market data.
    
    It handles missing values, scaling, and feature selection to create
    clean datasets ready for ML model training.
    """
    
    def __init__(
        self,
        handle_missing: str = 'fill',
        scaling: Optional[str] = 'standard',
        feature_selection: Optional[str] = None,
        n_features: int = 20,
        random_state: int = 42
    ):
        """
        Initialize the feature engineer.
        
        Parameters:
        -----------
        handle_missing : str
            Method for handling missing values ('drop', 'fill')
        scaling : Optional[str]
            Method for scaling features ('standard', 'minmax', or None)
        feature_selection : Optional[str]
            Method for feature selection ('kbest', 'mutual_info', or None)
        n_features : int
            Number of features to select if using feature selection
        random_state : int
            Random state for reproducibility
        """
        self.handle_missing = handle_missing
        self.scaling = scaling
        self.feature_selection = feature_selection
        self.n_features = n_features
        self.random_state = random_state
        self.selected_features = None
        self.scaler = None
        self.imputer = None
        self.feature_selector = None
    
    def fit_transform(
        self, 
        df: pd.DataFrame, 
        target: Optional[pd.Series] = None,
        prediction_type: str = 'classification'
    ) -> pd.DataFrame:
        """
        Fit preprocessing steps and transform the data.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw financial data (must contain OHLCV columns)
        target : Optional[pd.Series]
            Target variable (required for supervised feature selection)
        prediction_type : str
            Type of prediction task ('classification' or 'regression')
            
        Returns:
        --------
        pd.DataFrame
            Transformed features ready for model training
        """
        # Create features
        df_features = self.create_features(df)
        
        # Handle missing values
        if self.handle_missing == 'drop':
            df_features = df_features.dropna()
        elif self.handle_missing == 'fill':
            self.imputer = SimpleImputer(strategy='median')
            df_features = pd.DataFrame(
                self.imputer.fit_transform(df_features),
                columns=df_features.columns,
                index=df_features.index
            )
        
        # Scale features
        if self.scaling:
            if self.scaling == 'standard':
                self.scaler = StandardScaler()
            elif self.scaling == 'minmax':
                self.scaler = MinMaxScaler()
                
            scaled_features = self.scaler.fit_transform(df_features)
            df_features = pd.DataFrame(
                scaled_features,
                columns=df_features.columns,
                index=df_features.index
            )
        
        # Perform feature selection if specified and target is provided
        if self.feature_selection and target is not None:
            # Align target with features (handle any index mismatches)
            aligned_target = target.loc[df_features.index]
            
            if self.feature_selection == 'kbest':
                if prediction_type == 'classification':
                    self.feature_selector = SelectKBest(f_classif, k=min(self.n_features, df_features.shape[1]))
                else:
                    self.feature_selector = SelectKBest(f_regression, k=min(self.n_features, df_features.shape[1]))
            elif self.feature_selection == 'mutual_info':
                if prediction_type == 'classification':
                    self.feature_selector = SelectKBest(
                        mutual_info_classif, 
                        k=min(self.n_features, df_features.shape[1])
                    )
                else:
                    self.feature_selector = SelectKBest(
                        mutual_info_regression, 
                        k=min(self.n_features, df_features.shape[1])
                    )
            
            # Fit and transform
            selected_features = self.feature_selector.fit_transform(df_features, aligned_target)
            
            # Get selected feature names
            selected_indices = self.feature_selector.get_support(indices=True)
            self.selected_features = [df_features.columns[i] for i in selected_indices]
            
            # Convert back to DataFrame with selected features only
            df_features = pd.DataFrame(
                selected_features,
                columns=self.selected_features,
                index=df_features.index
            )
        
        return df_features
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform new data using fitted preprocessing steps.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw financial data (must contain OHLCV columns)
            
        Returns:
        --------
        pd.DataFrame
            Transformed features ready for prediction
        """
        # Create features
        df_features = self.create_features(df)
        
        # Handle missing values
        if self.handle_missing == 'fill' and self.imputer is not None:
            df_features = pd.DataFrame(
                self.imputer.transform(df_features),
                columns=df_features.columns,
                index=df_features.index
            )
        
        # Scale features
        if self.scaling and self.scaler is not None:
            scaled_features = self.scaler.transform(df_features)
            df_features = pd.DataFrame(
                scaled_features,
                columns=df_features.columns,
                index=df_features.index
            )
        
        # Select features if needed
        if self.feature_selection and self.selected_features is not None:
            # Ensure all selected features are in the dataframe
            for feature in self.selected_features:
                if feature not in df_features.columns:
                    logger.warning(f"Feature {feature} not found in input data.")
            
            # Only keep selected features
            df_features = df_features[self.selected_features]
        
        return df_features
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create comprehensive features from raw financial data.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw financial data (must contain OHLCV columns)
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with engineered features
        """
        # Ensure OHLCV columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Required column {col} not found in dataframe")
        
        # Create copy to avoid modifying original
        ohlcv = df.copy()
        
        # Dictionary to store all features
        features = {}
        
        # Price and returns features
        features.update(self._create_price_features(ohlcv))
        
        # Technical indicator features
        features.update(self._create_technical_indicators(ohlcv))
        
        # Volatility features
        features.update(self._create_volatility_features(ohlcv))
        
        # Volume features
        features.update(self._create_volume_features(ohlcv))
        
        # Statistical features
        features.update(self._create_statistical_features(ohlcv))
        
        # Time-based features (if datetime index)
        if isinstance(ohlcv.index, pd.DatetimeIndex):
            features.update(self._create_time_features(ohlcv))
        
        # Convert to DataFrame
        feature_df = pd.DataFrame(features, index=ohlcv.index)
        
        # Drop features with too many missing values (>30%)
        missing_pct = feature_df.isnull().mean()
        cols_to_drop = missing_pct[missing_pct > 0.3].index
        feature_df = feature_df.drop(columns=cols_to_drop)
        
        # Drop features with zero variance
        variance = feature_df.var()
        zero_var_cols = variance[variance == 0].index
        feature_df = feature_df.drop(columns=zero_var_cols)
        
        if len(cols_to_drop) > 0:
            logger.info(f"Dropped {len(cols_to_drop)} features with >30% missing values")
        if len(zero_var_cols) > 0:
            logger.info(f"Dropped {len(zero_var_cols)} features with zero variance")
        
        return feature_df
    
    def _create_price_features(self, ohlcv: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Create features based on price action"""
        features = {}
        
        # Simple price relationships
        features['hlc3'] = (ohlcv['high'] + ohlcv['low'] + ohlcv['close']) / 3
        features['oc2'] = (ohlcv['open'] + ohlcv['close']) / 2
        features['hl2'] = (ohlcv['high'] + ohlcv['low']) / 2
        features['ohlc4'] = (ohlcv['open'] + ohlcv['high'] + ohlcv['low'] + ohlcv['close']) / 4
        
        # Price ratios
        features['close_to_high'] = ohlcv['close'] / ohlcv['high']
        features['close_to_low'] = ohlcv['close'] / ohlcv['low']
        features['close_to_open'] = ohlcv['close'] / ohlcv['open']
        
        # Candle features
        features['candle_body'] = np.abs(ohlcv['close'] - ohlcv['open'])
        features['candle_shadow_upper'] = ohlcv['high'] - np.maximum(ohlcv['close'], ohlcv['open'])
        features['candle_shadow_lower'] = np.minimum(ohlcv['close'], ohlcv['open']) - ohlcv['low']
        features['candle_range'] = ohlcv['high'] - ohlcv['low']
        
        # Returns
        for period in [1, 2, 3, 5, 10, 20]:
            # Price momentum (returns)
            features[f'returns_{period}d'] = ohlcv['close'].pct_change(period)
            
            # Log returns
            features[f'log_returns_{period}d'] = np.log(ohlcv['close'] / ohlcv['close'].shift(period))
            
            # High/low returns
            features[f'high_returns_{period}d'] = ohlcv['high'].pct_change(period)
            features[f'low_returns_{period}d'] = ohlcv['low'].pct_change(period)
        
        return features
    
    def _create_technical_indicators(self, ohlcv: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Create standard technical indicators"""
        features = {}
        
        # Moving averages
        for period in [5, 10, 20, 50, 100, 200]:
            # Simple moving average (SMA)
            features[f'sma_{period}'] = talib.SMA(ohlcv['close'].values, timeperiod=period)
            
            # Exponential moving average (EMA)
            features[f'ema_{period}'] = talib.EMA(ohlcv['close'].values, timeperiod=period)
            
            # MA ratios
            features[f'close_to_sma_{period}'] = ohlcv['close'] / features[f'sma_{period}']
            features[f'close_to_ema_{period}'] = ohlcv['close'] / features[f'ema_{period}']
        
        # MACD
        macd, macd_signal, macd_hist = talib.MACD(
            ohlcv['close'].values, 
            fastperiod=12, 
            slowperiod=26, 
            signalperiod=9
        )
        features['macd'] = macd
        features['macd_signal'] = macd_signal
        features['macd_hist'] = macd_hist
        features['macd_diff'] = macd - macd_signal
        
        # RSI
        for period in [7, 14, 21]:
            features[f'rsi_{period}'] = talib.RSI(ohlcv['close'].values, timeperiod=period)
        
        # Stochastic oscillator
        slowk, slowd = talib.STOCH(
            ohlcv['high'].values,
            ohlcv['low'].values,
            ohlcv['close'].values,
            fastk_period=14,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0
        )
        features['stoch_k'] = slowk
        features['stoch_d'] = slowd
        features['stoch_diff'] = slowk - slowd
        
        # Bollinger Bands
        upperband, middleband, lowerband = talib.BBANDS(
            ohlcv['close'].values,
            timeperiod=20,
            nbdevup=2,
            nbdevdn=2,
            matype=0
        )
        features['bb_upper'] = upperband
        features['bb_middle'] = middleband
        features['bb_lower'] = lowerband
        features['bb_width'] = (upperband - lowerband) / middleband
        features['bb_position'] = (ohlcv['close'] - lowerband) / (upperband - lowerband)
        
        # Momentum
        for period in [5, 10, 14, 20, 30]:
            features[f'mom_{period}'] = talib.MOM(ohlcv['close'].values, timeperiod=period)
        
        # ADX (Average Directional Index)
        features['adx_14'] = talib.ADX(
            ohlcv['high'].values,
            ohlcv['low'].values,
            ohlcv['close'].values,
            timeperiod=14
        )
        
        # CCI (Commodity Channel Index)
        features['cci_14'] = talib.CCI(
            ohlcv['high'].values,
            ohlcv['low'].values,
            ohlcv['close'].values,
            timeperiod=14
        )
        
        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            features[f'roc_{period}'] = talib.ROC(ohlcv['close'].values, timeperiod=period)
        
        # Williams %R
        for period in [7, 14, 21]:
            features[f'willr_{period}'] = talib.WILLR(
                ohlcv['high'].values,
                ohlcv['low'].values,
                ohlcv['close'].values,
                timeperiod=period
            )
        
        # OBV (On Balance Volume)
        features['obv'] = talib.OBV(ohlcv['close'].values, ohlcv['volume'].values)
        
        return features
    
    def _create_volatility_features(self, ohlcv: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Create volatility indicators"""
        features = {}
        
        # ATR (Average True Range)
        for period in [7, 14, 21]:
            features[f'atr_{period}'] = talib.ATR(
                ohlcv['high'].values,
                ohlcv['low'].values,
                ohlcv['close'].values,
                timeperiod=period
            )
            
            # Normalized ATR (ATR / Close)
            features[f'natr_{period}'] = features[f'atr_{period}'] / ohlcv['close']
        
        # Historical volatility (standard deviation of returns)
        for period in [5, 10, 20, 30]:
            features[f'volatility_{period}d'] = ohlcv['close'].pct_change().rolling(period).std()
        
        # Garman-Klass volatility
        log_hl = np.log(ohlcv['high'] / ohlcv['low'])
        log_co = np.log(ohlcv['close'] / ohlcv['open'])
        
        gk_vol = 0.5 * log_hl**2 - (2*np.log(2) - 1) * log_co**2
        
        for period in [5, 10, 20]:
            features[f'gk_vol_{period}d'] = np.sqrt(gk_vol.rolling(period).mean())
        
        # High-Low range relative to close
        for period in [5, 10, 20]:
            high_max = ohlcv['high'].rolling(period).max()
            low_min = ohlcv['low'].rolling(period).min()
            features[f'range_ratio_{period}d'] = (high_max - low_min) / ohlcv['close']
        
        return features
    
    def _create_volume_features(self, ohlcv: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Create volume-based indicators"""
        features = {}
        
        # Volume changes
        for period in [1, 3, 5, 10]:
            features[f'volume_change_{period}d'] = ohlcv['volume'].pct_change(period)
        
        # Normalized volume (by moving average)
        for period in [5, 10, 20, 50]:
            vol_ma = ohlcv['volume'].rolling(period).mean()
            features[f'volume_ratio_{period}d'] = ohlcv['volume'] / vol_ma
        
        # Volume momentum
        for period in [5, 10, 20]:
            features[f'volume_mom_{period}d'] = ohlcv['volume'] - ohlcv['volume'].shift(period)
        
        # Price-volume relationships
        # Positive volume (close > open)
        pos_volume = ohlcv['volume'].copy()
        pos_volume[ohlcv['close'] < ohlcv['open']] = 0
        
        # Negative volume (close < open)
        neg_volume = ohlcv['volume'].copy()
        neg_volume[ohlcv['close'] > ohlcv['open']] = 0
        
        for period in [5, 10, 20]:
            # Positive volume momentum
            features[f'pos_volume_mom_{period}d'] = pos_volume.rolling(period).sum() / ohlcv['volume'].rolling(period).sum()
            
            # Negative volume momentum
            features[f'neg_volume_mom_{period}d'] = neg_volume.rolling(period).sum() / ohlcv['volume'].rolling(period).sum()
        
        # Money Flow Index
        for period in [7, 14, 21]:
            features[f'mfi_{period}'] = talib.MFI(
                ohlcv['high'].values,
                ohlcv['low'].values,
                ohlcv['close'].values,
                ohlcv['volume'].values,
                timeperiod=period
            )
        
        # Chaikin Money Flow
        for period in [20]:
            ad = ((ohlcv['close'] - ohlcv['low']) - (ohlcv['high'] - ohlcv['close'])) / (ohlcv['high'] - ohlcv['low']) * ohlcv['volume']
            features[f'cmf_{period}'] = ad.rolling(period).sum() / ohlcv['volume'].rolling(period).sum()
        
        # Force Index
        for period in [2, 13]:
            features[f'force_idx_{period}'] = ohlcv['close'].diff(1) * ohlcv['volume']
            features[f'force_idx_{period}'] = talib.EMA(features[f'force_idx_{period}'].values, timeperiod=period)
        
        return features
    
    def _create_statistical_features(self, ohlcv: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Create statistical indicators"""
        features = {}
        
        # Z-scores of returns
        for period in [10, 20, 50]:
            returns = ohlcv['close'].pct_change(1)
            rolling_mean = returns.rolling(period).mean()
            rolling_std = returns.rolling(period).std()
            features[f'returns_zscore_{period}d'] = (returns - rolling_mean) / rolling_std
        
        # Z-scores of price
        for period in [10, 20, 50]:
            rolling_mean = ohlcv['close'].rolling(period).mean()
            rolling_std = ohlcv['close'].rolling(period).std()
            features[f'price_zscore_{period}d'] = (ohlcv['close'] - rolling_mean) / rolling_std
        
        # Autocorrelation
        returns = ohlcv['close'].pct_change(1).fillna(0)
        for lag in [1, 2, 3, 5]:
            autocorr = returns.rolling(20).apply(lambda x: x.autocorr(lag=lag), raw=False)
            features[f'autocorr_lag{lag}'] = autocorr
        
        # Skewness and kurtosis of returns
        for period in [10, 20, 30]:
            features[f'returns_skew_{period}d'] = returns.rolling(period).skew()
            features[f'returns_kurt_{period}d'] = returns.rolling(period).kurt()
        
        # Linear regression slope of price
        def slope(y):
            x = np.arange(len(y))
            slope, _, _, _, _ = stats.linregress(x, y)
            return slope
        
        for period in [5, 10, 20]:
            features[f'price_slope_{period}d'] = ohlcv['close'].rolling(period).apply(slope, raw=True)
        
        # R-squared of price trend (goodness of fit)
        def rsquared(y):
            x = np.arange(len(y))
            _, _, r_value, _, _ = stats.linregress(x, y)
            return r_value**2
        
        for period in [10, 20]:
            features[f'price_rsquared_{period}d'] = ohlcv['close'].rolling(period).apply(rsquared, raw=True)
        
        # Hurst exponent (simplified calculation)
        def hurst(prices):
            if len(prices) < 10:
                return np.nan
            
            lags = range(2, min(10, len(prices) // 2))
            tau = [np.std(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]
            
            if not all(tau):
                return np.nan
                
            reg = np.polyfit(np.log(lags), np.log(tau), 1)
            return reg[0]
        
        features['hurst_exponent'] = ohlcv['close'].rolling(50).apply(hurst, raw=True)
        
        return features
    
    def _create_time_features(self, ohlcv: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Create time-based features"""
        features = {}
        
        # Day of week
        features['day_of_week'] = ohlcv.index.dayofweek
        
        # Hour of day (if intraday data)
        if hasattr(ohlcv.index, 'hour'):
            features['hour_of_day'] = ohlcv.index.hour
        
        # Month
        features['month'] = ohlcv.index.month
        
        # Quarter
        features['quarter'] = ohlcv.index.quarter
        
        # Is month end/start
        features['is_month_end'] = ohlcv.index.is_month_end.astype(int)
        features['is_month_start'] = ohlcv.index.is_month_start.astype(int)
        
        # Is quarter end/start
        features['is_quarter_end'] = ohlcv.index.is_quarter_end.astype(int)
        features['is_quarter_start'] = ohlcv.index.is_quarter_start.astype(int)
        
        # Year
        features['year'] = ohlcv.index.year
        
        return features
    
    def get_feature_categories(self) -> Dict[str, List[str]]:
        """
        Get feature categories for analysis.
        
        Returns:
        --------
        Dict[str, List[str]]
            Dictionary mapping category names to lists of feature names
        """
        # Define feature categories by prefix
        categories = {
            'price': ['hlc3', 'oc2', 'hl2', 'ohlc4', 'close_to_high', 'close_to_low', 'close_to_open',
                     'candle_body', 'candle_shadow_upper', 'candle_shadow_lower', 'candle_range',
                     'returns_', 'log_returns_', 'high_returns_', 'low_returns_'],
            'moving_average': ['sma_', 'ema_', 'close_to_sma_', 'close_to_ema_'],
            'momentum': ['macd', 'rsi_', 'stoch_', 'mom_', 'roc_', 'willr_'],
            'volatility': ['bb_', 'atr_', 'natr_', 'volatility_', 'gk_vol_', 'range_ratio_'],
            'volume': ['volume_', 'pos_volume_', 'neg_volume_', 'mfi_', 'cmf_', 'force_idx_', 'obv'],
            'trend': ['adx_', 'price_slope_', 'price_rsquared_'],
            'statistical': ['returns_zscore_', 'price_zscore_', 'autocorr_', 'returns_skew_', 
                           'returns_kurt_', 'hurst_'],
            'time': ['day_of_week', 'hour_of_day', 'month', 'quarter', 'is_month_',
                    'is_quarter_', 'year']
        }
        
        return categories
    
    def select_features_by_category(
        self, 
        df: pd.DataFrame, 
        categories: List[str]
    ) -> pd.DataFrame:
        """
        Select features by category.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with all features
        categories : List[str]
            List of categories to select
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with selected features
        """
        # Get category mapping
        category_map = self.get_feature_categories()
        
        # Get columns to select
        cols_to_select = []
        
        for category in categories:
            if category in category_map:
                # For each pattern in this category
                for pattern in category_map[category]:
                    # Find all columns that match this pattern
                    matching_cols = [col for col in df.columns if col.startswith(pattern) or col == pattern]
                    cols_to_select.extend(matching_cols)
        
        # Remove duplicates
        cols_to_select = list(set(cols_to_select))
        
        # Select only columns that exist in the dataframe
        existing_cols = [col for col in cols_to_select if col in df.columns]
        
        if len(existing_cols) == 0:
            logger.warning("No matching features found in the dataframe")
            return pd.DataFrame()
        
        return df[existing_cols]
    
    def create_target_variable(
        self, 
        df: pd.DataFrame, 
        method: str = 'binary_direction',
        horizon: int = 5,
        threshold: float = 0.0
    ) -> pd.Series:
        """
        Create target variable for supervised learning.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw price data
        method : str
            Method to create target ('binary_direction', 'multi_direction', 'regression_return')
        horizon : int
            Forecast horizon (in periods)
        threshold : float
            Threshold for significant movement (used in 'binary_direction')
            
        Returns:
        --------
        pd.Series
            Target variable
        """
        # Ensure 'close' column exists
        if 'close' not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")
        
        # Calculate future returns
        future_returns = df['close'].pct_change(horizon).shift(-horizon)
        
        if method == 'binary_direction':
            # 1 if return > threshold, 0 if return < -threshold, NaN otherwise
            target = pd.Series(index=df.index, dtype=float)
            target[future_returns > threshold] = 1
            target[future_returns < -threshold] = 0
            
        elif method == 'multi_direction':
            # 1 for up, 0 for flat, -1 for down
            target = pd.Series(index=df.index, dtype=float)
            target[future_returns > threshold] = 1
            target[(future_returns >= -threshold) & (future_returns <= threshold)] = 0
            target[future_returns < -threshold] = -1
            
        elif method == 'regression_return':
            # Use raw future return as target
            target = future_returns
            
        else:
            raise ValueError(f"Unknown target method: {method}")
        
        return target
    
    def feature_importance_analysis(
        self, 
        X: pd.DataFrame, 
        model: Any,
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        Analyze feature importance from a trained model.
        
        Parameters:
        -----------
        X : pd.DataFrame
            Feature dataframe
        model : Any
            Trained model with feature_importances_ or coef_ attribute
        top_n : int
            Number of top features to include
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with feature importances
        """
        # Extract model from pipeline if needed
        if hasattr(model, 'named_steps') and 'model' in model.named_steps:
            model = model.named_steps['model']
        
        # Extract feature importance
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        elif hasattr(model, 'coef_'):
            importances = np.abs(model.coef_)
            if importances.ndim > 1:
                importances = importances.mean(axis=0)
        else:
            raise ValueError("Model does not have feature_importances_ or coef_ attribute")
        
        # Create DataFrame with feature importances
        importance_df = pd.DataFrame({
            'feature': X.columns,
            'importance': importances
        })
        
        # Sort by importance
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        # Get top N features
        if top_n > 0:
            importance_df = importance_df.head(top_n)
        
        return importance_df 