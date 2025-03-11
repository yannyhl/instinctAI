# Time Series Cross-Validation Module

This module provides advanced cross-validation techniques specifically designed for time series data, with a focus on financial applications.

## Key Features

- **Multiple window types**: Sliding, expanding, and anchored windows for time series cross-validation
- **Purged cross-validation**: Prevent data leakage between train and test sets by removing samples with temporal overlap
- **Embargo periods**: Simulate implementation delays by excluding samples after the test set
- **Visualization utilities**: Plot cross-validation schemes to better understand the temporal data splits
- **Scikit-learn compatibility**: Follows scikit-learn's cross-validation interface for easy integration

## Classes and Functions

### TimeSeriesCV

The main class for time series cross-validation:

```python
cv = TimeSeriesCV(
    cv_method='sliding',  # 'sliding', 'expanding', or 'anchored'
    n_splits=5,           # Number of splits to generate
    train_size=0.6,       # Size of training set (float for fraction, int for absolute)
    test_size=0.2,        # Size of test set
    step_size=0.1,        # Step size between folds
    purge_size=0.05,      # Size of purge window between train and test
    embargo_size=0.05     # Size of embargo window after test
)
```

### Utility Functions

- `purged_cross_val_score`: Evaluate a model using purged cross-validation
- `plot_purged_cv_results`: Visualize cross-validation results

## Usage Examples

### Basic Usage

```python
from advanced_trading.utils.cross_validation import TimeSeriesCV

# Create the cross-validation splitter
cv = TimeSeriesCV(
    cv_method='sliding',
    n_splits=5,
    train_size=0.7,
    test_size=0.3,
    step_size=0.1
)

# Generate and iterate over splits
for train_idx, test_idx in cv.split(X, y):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    # Train and evaluate your model
    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)
```

### Model Evaluation

```python
from advanced_trading.utils.cross_validation import purged_cross_val_score
from sklearn.linear_model import Ridge

# Create model and evaluate
model = Ridge(alpha=1.0)
scores = purged_cross_val_score(
    model, X, y, 
    cv=cv, 
    scoring='r2'
)

print(f"R² scores: {scores}")
print(f"Mean R²: {np.mean(scores):.4f}, Std: {np.std(scores):.4f}")
```

### Visualization

```python
# Visualize the CV splits
fig = cv.plot_cv_indices(X)
plt.title("Sliding Window Cross-Validation")
plt.show()

# For time series with dates
fig = cv.plot_cv_dates(X)
plt.title("Cross-Validation Dates")
plt.show()
```

## Best Practices

1. **Always use purged cross-validation** for financial time series to prevent data leakage
2. **Consider embargo periods** to simulate real-world implementation delays
3. **Visualize your CV scheme** to ensure it aligns with your expectations
4. **Compare model performance** across different CV schemes to ensure robustness

## References

- Lopez de Prado, M. (2018). Advances in Financial Machine Learning. Wiley.
- Bergmeir, C., & Benítez, J. M. (2012). On the use of cross-validation for time series predictor evaluation. Information Sciences, 191, 192-213. 