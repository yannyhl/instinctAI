"""
Data Preprocessing Examples
--------------------------
This script demonstrates the practical application of data preprocessing functions
for financial time series data using the advanced_trading.utils.data_preprocessing module.

Examples include:
1. Data cleaning (handling missing values, outliers)
2. Feature transformation (normalization, log transforms)
3. Feature engineering (lag features, rolling statistics, date features)
4. Dimensionality reduction (PCA, feature selection)
5. Data splitting (train/test/validation splits, time series cross-validation)

The examples use synthetic data that mimics financial time series characteristics
for illustrative purposes.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import seaborn as sns

# Import data preprocessing functions
from advanced_trading.utils.data_preprocessing import (
    # Data cleaning
    handle_missing_values,
    handle_outliers,
    detect_outliers,
    remove_duplicates,
    resample_time_series,
    
    # Feature transformation
    normalize_data,
    apply_log_transform,
    apply_box_cox_transform,
    apply_differencing,
    apply_scaler,
    
    # Feature engineering
    create_lag_features,
    create_rolling_features,
    extract_date_features,
    
    # Dimensionality reduction
    apply_pca,
    apply_tsne,
    select_features_by_importance,
    
    # Data splitting
    split_time_series_data,
    time_series_cross_validation,
    time_series_bootstrap
)

# Set up plotting
plt.style.use('ggplot')
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14

# Create sample financial time series data
def create_sample_data(n_days=500, start_date='2022-01-01', random_seed=42):
    """Create synthetic financial data with common characteristics"""
    np.random.seed(random_seed)
    
    # Create date range
    dates = pd.date_range(start=start_date, periods=n_days, freq='D')
    
    # Create price series with trend, seasonality and noise
    trend = np.linspace(0, 20, n_days)
    seasonality = 5 * np.sin(np.linspace(0, 10 * np.pi, n_days))
    noise = np.random.normal(0, 5, n_days)
    
    # Generate price with autocorrelation and mean-reverting properties
    price = 100 + trend + seasonality + np.cumsum(noise) * 0.1
    
    # Add high volatility period
    volatility_period = slice(150, 200)
    price[volatility_period] += np.random.normal(0, 30, 50)
    
    # Generate volume (correlated with absolute returns)
    returns = np.diff(price, prepend=price[0])
    volume = 10000 + 5000 * np.abs(returns) + np.random.normal(0, 3000, n_days)
    volume = np.maximum(volume, 1000)  # Ensure minimum volume
    
    # Create some missing values
    missing_indices = np.random.choice(range(n_days), size=20, replace=False)
    price_with_missing = price.copy()
    price_with_missing[missing_indices] = np.nan
    
    # Introduce outliers
    outlier_indices = np.random.choice(range(n_days), size=10, replace=False)
    price_with_outliers = price.copy()
    price_with_outliers[outlier_indices] += np.random.choice([-1, 1], size=10) * np.random.uniform(30, 50, 10)
    
    # Create DataFrame
    df = pd.DataFrame({
        'price': price,
        'price_missing': price_with_missing,
        'price_outliers': price_with_outliers,
        'volume': volume,
    }, index=dates)
    
    # Add some features
    df['returns'] = df['price'].pct_change() * 100
    df['log_returns'] = np.log(df['price'] / df['price'].shift(1)) * 100
    
    return df

# Generate sample data
print("Generating sample financial time series data...")
financial_data = create_sample_data()
print(f"Data shape: {financial_data.shape}")
print(financial_data.head())
print("\nData summary:")
print(financial_data.describe())

# Plot original data
plt.figure(figsize=(14, 10))

plt.subplot(3, 1, 1)
plt.plot(financial_data.index, financial_data['price'], label='Price')
plt.plot(financial_data.index, financial_data['price_missing'], 'r.', label='Price with Missing Values')
plt.plot(financial_data.index, financial_data['price_outliers'], 'g.', label='Price with Outliers')
plt.title('Price Data')
plt.legend()

plt.subplot(3, 1, 2)
plt.plot(financial_data.index, financial_data['returns'], label='Returns (%)')
plt.title('Returns')
plt.legend()

plt.subplot(3, 1, 3)
plt.plot(financial_data.index, financial_data['volume'], label='Volume')
plt.title('Trading Volume')
plt.legend()

plt.tight_layout()
plt.savefig('original_data.png')
plt.close()

print("\n1. DATA CLEANING EXAMPLES")
print("--------------------------")

# Handle missing values
print("\n1.1 Handling Missing Values")
print("Number of missing values before:", financial_data['price_missing'].isna().sum())
data_clean = handle_missing_values(financial_data['price_missing'], method='interpolate')
print("Number of missing values after:", data_clean.isna().sum())

# Compare original vs cleaned data
plt.figure(figsize=(12, 6))
plt.plot(financial_data.index, financial_data['price'], 'b-', label='Original Price')
plt.plot(financial_data.index, financial_data['price_missing'], 'r.', label='Missing Values')
plt.plot(financial_data.index, data_clean, 'g-', label='Interpolated Data')
plt.title('Handling Missing Values with Interpolation')
plt.legend()
plt.savefig('missing_values_handling.png')
plt.close()

# Handle outliers
print("\n1.2 Handling Outliers")
# Detect outliers first
outliers = detect_outliers(financial_data['price_outliers'], method='zscore', threshold=3.0)
print(f"Number of outliers detected: {outliers.sum()}")

# Handle outliers
data_without_outliers = handle_outliers(financial_data['price_outliers'], method='zscore', treatment='clip')

# Compare original vs cleaned data
plt.figure(figsize=(12, 6))
plt.plot(financial_data.index, financial_data['price'], 'b-', label='Original Price')
plt.plot(financial_data.index, financial_data['price_outliers'], 'r.', label='Outliers')
plt.plot(financial_data.index, data_without_outliers, 'g-', label='Cleaned Data')
plt.title('Handling Outliers with Z-Score Clipping')
plt.legend()
plt.savefig('outlier_handling.png')
plt.close()

# Resample time series
print("\n1.3 Time Series Resampling")
daily_data = financial_data[['price', 'volume']].copy()
weekly_data = resample_time_series(daily_data, rule='W', agg_func={'price': 'mean', 'volume': 'sum'})
monthly_data = resample_time_series(daily_data, rule='M', agg_func={'price': 'mean', 'volume': 'sum'})

print(f"Original daily data shape: {daily_data.shape}")
print(f"Resampled weekly data shape: {weekly_data.shape}")
print(f"Resampled monthly data shape: {monthly_data.shape}")

# Plot resampled data
plt.figure(figsize=(12, 8))
plt.subplot(2, 1, 1)
plt.plot(daily_data.index, daily_data['price'], 'b-', label='Daily')
plt.plot(weekly_data.index, weekly_data['price'], 'r-', marker='o', label='Weekly')
plt.plot(monthly_data.index, monthly_data['price'], 'g-', marker='s', label='Monthly')
plt.title('Price Resampling')
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(daily_data.index, daily_data['volume'], 'b-', label='Daily')
plt.plot(weekly_data.index, weekly_data['volume'], 'r-', marker='o', label='Weekly')
plt.plot(monthly_data.index, monthly_data['volume'], 'g-', marker='s', label='Monthly')
plt.title('Volume Resampling')
plt.legend()

plt.tight_layout()
plt.savefig('time_series_resampling.png')
plt.close()

print("\n2. FEATURE TRANSFORMATION EXAMPLES")
print("----------------------------------")

# Normalize data
print("\n2.1 Data Normalization")
normalized_data, scalers = normalize_data(financial_data[['price', 'volume']], return_scaler=True)
print("Original data ranges:")
print(f"Price: [{financial_data['price'].min():.2f}, {financial_data['price'].max():.2f}]")
print(f"Volume: [{financial_data['volume'].min():.2f}, {financial_data['volume'].max():.2f}]")
print("Normalized data ranges:")
print(f"Price: [{normalized_data['price'].min():.2f}, {normalized_data['price'].max():.2f}]")
print(f"Volume: [{normalized_data['volume'].min():.2f}, {normalized_data['volume'].max():.2f}]")

# Plot normalized data
plt.figure(figsize=(12, 6))
plt.plot(financial_data.index, normalized_data['price'], 'b-', label='Normalized Price')
plt.plot(financial_data.index, normalized_data['volume'], 'r-', label='Normalized Volume')
plt.title('Min-Max Normalized Data')
plt.legend()
plt.savefig('normalized_data.png')
plt.close()

# Apply log transform
print("\n2.2 Log Transformation")
# Use price and volume since they're positive
log_transformed = apply_log_transform(financial_data[['price', 'volume']])
print("Log-transformed data summary:")
print(log_transformed.describe())

# Plot log transformed data
plt.figure(figsize=(12, 6))
plt.plot(financial_data.index, financial_data['price'], 'b-', label='Original Price')
plt.plot(financial_data.index, log_transformed['price'], 'r-', label='Log-transformed Price')
plt.title('Log Transformation of Price')
plt.legend()
plt.savefig('log_transform.png')
plt.close()

# Apply differencing
print("\n2.3 Differencing")
differenced_data = apply_differencing(financial_data['price'], periods=1, order=1)
print("First-order differenced data summary:")
print(differenced_data.describe())

# Plot differenced data
plt.figure(figsize=(12, 6))
plt.plot(financial_data.index[1:], differenced_data[1:], 'b-', label='Differenced Price')
plt.axhline(y=0, color='r', linestyle='-')
plt.title('First-Order Differencing of Price')
plt.legend()
plt.savefig('differenced_data.png')
plt.close()

print("\n3. FEATURE ENGINEERING EXAMPLES")
print("-------------------------------")

# Create lag features
print("\n3.1 Lag Features")
lagged_data = create_lag_features(financial_data[['price', 'returns']], lags=[1, 2, 3, 5, 10], drop_na=True)
print(f"Original data shape: {financial_data.shape}")
print(f"Lagged data shape: {lagged_data.shape}")
print("Lagged data columns:")
print(lagged_data.columns.tolist())

# Calculate correlation between original and lagged features
correlation = lagged_data.corr()
plt.figure(figsize=(10, 8))
sns.heatmap(correlation, annot=True, cmap='coolwarm', fmt='.2f')
plt.title('Correlation Between Original and Lagged Features')
plt.tight_layout()
plt.savefig('lag_features_correlation.png')
plt.close()

# Create rolling window features
print("\n3.2 Rolling Window Features")
rolling_data = create_rolling_features(
    financial_data['price'], 
    windows=[5, 10, 20], 
    functions={'mean': np.mean, 'std': np.std}, 
    drop_na=True
)
print(f"Original data shape: {financial_data.shape}")
print(f"Rolling window data shape: {rolling_data.shape}")
print("Rolling window data columns:")
print(rolling_data.columns.tolist())

# Plot original price vs rolling means
plt.figure(figsize=(12, 6))
plt.plot(rolling_data.index, rolling_data['price'], 'k-', label='Price')
plt.plot(rolling_data.index, rolling_data['price_rolling_5_mean'], 'r-', label='5-day MA')
plt.plot(rolling_data.index, rolling_data['price_rolling_10_mean'], 'g-', label='10-day MA')
plt.plot(rolling_data.index, rolling_data['price_rolling_20_mean'], 'b-', label='20-day MA')
plt.title('Price and Moving Averages')
plt.legend()
plt.savefig('rolling_means.png')
plt.close()

# Extract date features
print("\n3.3 Date Features")
date_features = extract_date_features(financial_data)
print(f"Original data shape: {financial_data.shape}")
print(f"Data with date features shape: {date_features.shape}")
print("Date features columns:")
date_cols = [col for col in date_features.columns if col not in financial_data.columns]
print(date_cols)

# Analyze price by day of week
plt.figure(figsize=(10, 6))
sns.boxplot(x='dayofweek', y='price', data=date_features)
plt.title('Price Distribution by Day of Week')
plt.xlabel('Day of Week (0=Monday, 6=Sunday)')
plt.ylabel('Price')
plt.savefig('price_by_day_of_week.png')
plt.close()

print("\n4. DIMENSIONALITY REDUCTION EXAMPLES")
print("-----------------------------------")

# Create a dataset with multiple features for dimensionality reduction
feature_data = pd.DataFrame({
    'price': financial_data['price'],
    'volume': financial_data['volume'],
    'returns': financial_data['returns'],
    'log_returns': financial_data['log_returns'],
})

# Add lag features
feature_data = create_lag_features(feature_data, lags=[1, 2, 3], drop_na=True)

# Add rolling features
for col in ['price', 'volume', 'returns']:
    rolling_features = create_rolling_features(
        feature_data[col], 
        windows=[5, 10], 
        functions={'mean': np.mean, 'std': np.std},
        drop_na=False
    )
    # Get only the rolling features, not the original column
    rolling_cols = [c for c in rolling_features.columns if c != col]
    feature_data[rolling_cols] = rolling_features[rolling_cols]

# Drop any remaining missing values
feature_data = feature_data.dropna()
print(f"Feature data shape: {feature_data.shape}")
print("Feature data columns:")
print(feature_data.columns.tolist())

# Apply PCA
print("\n4.1 Principal Component Analysis")
pca_data, pca_obj, components = apply_pca(
    feature_data, 
    n_components=5, 
    return_components=True, 
    return_explained_variance=True
)
print(f"PCA data shape: {pca_data.shape}")
print("Explained variance ratio:", pca_obj.explained_variance_ratio_)
print("Cumulative explained variance:", np.cumsum(pca_obj.explained_variance_ratio_))

# Plot explained variance
plt.figure(figsize=(10, 5))
plt.bar(range(1, len(pca_obj.explained_variance_ratio_) + 1), pca_obj.explained_variance_ratio_)
plt.plot(range(1, len(pca_obj.explained_variance_ratio_) + 1), 
         np.cumsum(pca_obj.explained_variance_ratio_), 'r-o')
plt.axhline(y=0.9, color='k', linestyle='--')
plt.xticks(range(1, len(pca_obj.explained_variance_ratio_) + 1))
plt.xlabel('Principal Component')
plt.ylabel('Explained Variance Ratio')
plt.title('PCA Explained Variance')
plt.savefig('pca_explained_variance.png')
plt.close()

# Feature importance
print("\n4.2 Feature Selection by Importance")
# Create a target variable (next day's returns)
target = feature_data['returns'].shift(-1).dropna()
feature_data_with_target = feature_data.iloc[:-1].copy()
feature_data_with_target['next_returns'] = target.values

# Select features
selected_features, scores = select_features_by_importance(
    feature_data_with_target, 
    target_column='next_returns',
    method='f_regression', 
    k=10, 
    return_scores=True
)
print("Top 10 features by importance:")
print(scores.head(10))

# Plot feature importance
plt.figure(figsize=(12, 6))
scores.sort_values('score').tail(10).plot(kind='barh')
plt.title('Top 10 Features by Importance (F-regression)')
plt.xlabel('Score')
plt.tight_layout()
plt.savefig('feature_importance.png')
plt.close()

print("\n5. DATA SPLITTING EXAMPLES")
print("-------------------------")

# Basic train/test/validation split
print("\n5.1 Train/Test/Validation Split")
splits = split_time_series_data(
    financial_data['price'], 
    train_size=0.7, 
    val_size=0.15, 
    test_size=0.15
)
print(f"Train set: {splits['train'].shape} ({splits['train'].index[0]} to {splits['train'].index[-1]})")
print(f"Validation set: {splits['val'].shape} ({splits['val'].index[0]} to {splits['val'].index[-1]})")
print(f"Test set: {splits['test'].shape} ({splits['test'].index[0]} to {splits['test'].index[-1]})")

# Plot the splits
plt.figure(figsize=(12, 6))
plt.plot(splits['train'].index, splits['train'], 'b-', label='Train')
plt.plot(splits['val'].index, splits['val'], 'g-', label='Validation')
plt.plot(splits['test'].index, splits['test'], 'r-', label='Test')
plt.title('Train/Validation/Test Split for Time Series Data')
plt.legend()
plt.savefig('train_val_test_split.png')
plt.close()

# Time series cross-validation
print("\n5.2 Time Series Cross-Validation")
cv_splits = time_series_cross_validation(
    financial_data['price'],
    n_splits=5,
    test_size=30,
    expanding_window=True
)
print(f"Number of CV splits: {len(cv_splits)}")
for i, split in enumerate(cv_splits):
    print(f"Split {i+1}:")
    print(f"  Train: {split['train'].shape[0]} samples ({split['train'].index[0]} to {split['train'].index[-1]})")
    print(f"  Test: {split['test'].shape[0]} samples ({split['test'].index[0]} to {split['test'].index[-1]})")

# Plot cross-validation splits
plt.figure(figsize=(12, 10))
for i, split in enumerate(cv_splits):
    plt.subplot(len(cv_splits), 1, i+1)
    plt.plot(financial_data.index, financial_data['price'], 'lightgray')
    plt.plot(split['train'].index, split['train'], 'b-', label=f'Train {i+1}')
    plt.plot(split['test'].index, split['test'], 'r-', label=f'Test {i+1}')
    plt.title(f'CV Split {i+1}')
    plt.legend()
plt.tight_layout()
plt.savefig('time_series_cv_splits.png')
plt.close()

print("\n6. PUTTING IT ALL TOGETHER")
print("-------------------------")

# Example financial prediction pipeline
print("\n6.1 Complete Financial Data Preprocessing Pipeline")

# Step 1: Load and clean data
clean_data = financial_data.copy()
clean_data['price_clean'] = handle_missing_values(
    handle_outliers(financial_data['price_outliers'], method='zscore', treatment='clip'),
    method='interpolate'
)

# Step 2: Feature engineering
# - Create lag features
clean_data = create_lag_features(clean_data[['price_clean', 'returns']], lags=[1, 2, 3, 5], drop_na=False)

# - Create rolling features
for col in ['price_clean']:
    rolling_features = create_rolling_features(
        clean_data[col], 
        windows=[5, 10, 20], 
        functions={'mean': np.mean, 'std': np.std, 'min': np.min, 'max': np.max},
        drop_na=False
    )
    # Get only the rolling features, not the original column
    rolling_cols = [c for c in rolling_features.columns if c != col]
    clean_data[rolling_cols] = rolling_features[rolling_cols]

# - Add date features
clean_data = extract_date_features(clean_data, features=['dayofweek', 'month', 'quarter', 'is_month_end'])

# - Create target variable (next day's return)
clean_data['target_return'] = clean_data['price_clean'].pct_change(periods=1).shift(-1) * 100

# Step 3: Transform features
# - Apply differencing to price
clean_data['price_diff'] = apply_differencing(clean_data['price_clean'], periods=1, order=1)

# - Normalize numeric features
numeric_cols = clean_data.select_dtypes(include=np.number).columns.tolist()
exclude_cols = ['target_return']  # Don't normalize the target
normalize_cols = [col for col in numeric_cols if col not in exclude_cols]
normalized_features, scalers = normalize_data(clean_data[normalize_cols], return_scaler=True)
clean_data[normalize_cols] = normalized_features

# Step 4: Handle missing values from feature creation
clean_data = clean_data.dropna()
print(f"Data shape after preprocessing: {clean_data.shape}")

# Step 5: Feature selection
important_features, scores = select_features_by_importance(
    clean_data.drop(['price', 'price_missing', 'price_outliers', 'price_clean'], axis=1),
    target_column='target_return',
    method='f_regression',
    k=10,
    return_scores=True
)
print("Top 10 features for predicting returns:")
print(scores.head(10))

# Step 6: Split data for modeling
final_data = clean_data[important_features + ['target_return']]
splits = split_time_series_data(final_data, train_size=0.7, val_size=0.15, test_size=0.15)

print(f"Training data shape: {splits['train'].shape}")
print(f"Validation data shape: {splits['val'].shape}")
print(f"Testing data shape: {splits['test'].shape}")

print("\nData preprocessing pipeline complete. The preprocessed data is ready for modeling.")

# Plot a summary of the pipeline results
plt.figure(figsize=(15, 10))

plt.subplot(3, 1, 1)
plt.plot(financial_data.index, financial_data['price'], 'b-', alpha=0.5, label='Original')
plt.plot(financial_data.index, financial_data['price_outliers'], 'r.', label='Outliers')
plt.plot(clean_data.index, clean_data['price_clean'], 'g-', label='Cleaned')
plt.title('Data Cleaning: Original vs Cleaned Price')
plt.legend()

plt.subplot(3, 1, 2)
for feature in important_features[:5]:  # Plot top 5 features
    plt.plot(clean_data.index, clean_data[feature], label=feature)
plt.title('Top 5 Important Features')
plt.legend()

plt.subplot(3, 1, 3)
plt.plot(splits['train'].index, splits['train']['target_return'], 'b-', label='Train')
plt.plot(splits['val'].index, splits['val']['target_return'], 'g-', label='Validation')
plt.plot(splits['test'].index, splits['test']['target_return'], 'r-', label='Test')
plt.title('Target Variable (Next Day Return) for Train/Val/Test Sets')
plt.legend()

plt.tight_layout()
plt.savefig('complete_pipeline_summary.png')
plt.close()

print("\nPlots generated to visualize the data preprocessing pipeline results.")
print("Check the images for visual understanding of each preprocessing step.") 