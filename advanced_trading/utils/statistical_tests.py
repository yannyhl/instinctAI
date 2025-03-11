"""
Statistical tests for financial time series analysis.

This module provides a comprehensive set of statistical tests commonly used in financial
time series analysis. It includes tests for stationarity, normality, cointegration, 
causality, and other statistical properties that are important for developing robust
trading strategies.

Features:
    - Stationarity tests (ADF, KPSS, Phillips-Perron)
    - Normality tests (Jarque-Bera, Shapiro-Wilk, D'Agostino-Pearson)
    - Descriptive statistics (skewness, kurtosis, etc.)
    - Cointegration tests (Engle-Granger, Johansen)
    - Causality tests (Granger causality)
    - Correlation tests (Pearson, Spearman, Kendall)
    - Autocorrelation tests (Ljung-Box, Durbin-Watson)
    - White noise tests (Bartlett, Portmanteau)
    - Break point detection (Chow test, CUSUM)
    
All functions support both pandas Series/DataFrame and numpy arrays.
"""

import numpy as np
import pandas as pd
import logging
from typing import Union, Dict, Tuple, Optional, List
import scipy.stats as stats
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, kpss, coint, grangercausalitytests
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from arch.unitroot import PhillipsPerron, KPSS, ADF
import warnings

# Setup logging
logger = logging.getLogger(__name__)

def adf_test(data: Union[pd.Series, np.ndarray], 
             regression: str = 'c', 
             lags: Optional[int] = None) -> Dict:
    """
    Augmented Dickey-Fuller test for stationarity.
    
    The null hypothesis of the test is that the time series has a unit root, meaning it is non-stationary.
    The alternative hypothesis is that the time series is stationary.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
    regression : str, optional
        Type of regression to include in test:
        'c': constant only (default)
        'ct': constant and trend
        'ctt': constant, linear and quadratic trend
        'nc': no constant, no trend
    lags : int, optional
        Number of lags to include in the model. If None, it's automatically selected based on AIC.
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Test statistic
        - 'pvalue': p-value
        - 'critical_values': Dictionary of critical values at 1%, 5%, and 10% significance
        - 'lags': Number of lags used
        - 'nobs': Number of observations
        - 'is_stationary': Boolean indicating whether the series is stationary (p-value < 0.05)
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import adf_test
    >>> 
    >>> # Generate a non-stationary random walk
    >>> np.random.seed(42)
    >>> random_walk = np.cumsum(np.random.normal(0, 1, 1000))
    >>> result = adf_test(random_walk)
    >>> print(f"ADF Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Is stationary: {result['is_stationary']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run ADF test
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result = adfuller(data, regression=regression, maxlag=lags)
    
    # Extract and return results
    output = {
        'statistic': result[0],
        'pvalue': result[1],
        'critical_values': result[4],
        'lags': result[2],
        'nobs': result[3],
        'is_stationary': result[1] < 0.05,
        'method': 'Augmented Dickey-Fuller Test'
    }
    
    return output

def kpss_test(data: Union[pd.Series, np.ndarray],
              regression: str = 'c',
              lags: Optional[int] = None) -> Dict:
    """
    KPSS test for stationarity.
    
    The null hypothesis of the test is that the time series is stationary.
    The alternative hypothesis is that the time series has a unit root, meaning it is non-stationary.
    
    This test complements the ADF test as they have opposite null hypotheses.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
    regression : str, optional
        Type of regression to include in test:
        'c': constant only (default)
        'ct': constant and trend
    lags : int, optional
        Number of lags to include in the model. If None, it's automatically selected.
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Test statistic
        - 'pvalue': p-value
        - 'critical_values': Dictionary of critical values at 1%, 5%, and 10% significance
        - 'lags': Number of lags used
        - 'is_stationary': Boolean indicating whether the series is stationary (p-value > 0.05)
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import kpss_test
    >>> 
    >>> # Generate a non-stationary random walk
    >>> np.random.seed(42)
    >>> random_walk = np.cumsum(np.random.normal(0, 1, 1000))
    >>> result = kpss_test(random_walk)
    >>> print(f"KPSS Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Is stationary: {result['is_stationary']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run KPSS test
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result = kpss(data, regression=regression, nlags=lags)
    
    # Extract and return results
    output = {
        'statistic': result[0],
        'pvalue': result[1],
        'critical_values': result[3],
        'lags': result[2],
        'is_stationary': result[1] > 0.05,
        'method': 'KPSS Test'
    }
    
    return output

def phillips_perron_test(data: Union[pd.Series, np.ndarray],
                        regression: str = 'c',
                        lags: Optional[int] = None) -> Dict:
    """
    Phillips-Perron test for stationarity.
    
    The null hypothesis of the test is that the time series has a unit root, meaning it is non-stationary.
    The alternative hypothesis is that the time series is stationary.
    
    Unlike the ADF test, the Phillips-Perron test is robust to heteroskedasticity.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
    regression : str, optional
        Type of regression to include in test:
        'c': constant only (default)
        'ct': constant and trend
        'n': no constant, no trend
    lags : int, optional
        Number of lags to include in the model. If None, it's automatically selected.
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Test statistic
        - 'pvalue': p-value
        - 'critical_values': Dictionary of critical values at 1%, 5%, and 10% significance
        - 'lags': Number of lags used
        - 'is_stationary': Boolean indicating whether the series is stationary (p-value < 0.05)
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import phillips_perron_test
    >>> 
    >>> # Generate a non-stationary random walk
    >>> np.random.seed(42)
    >>> random_walk = np.cumsum(np.random.normal(0, 1, 1000))
    >>> result = phillips_perron_test(random_walk)
    >>> print(f"Phillips-Perron Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Is stationary: {result['is_stationary']}")
    """
    # Convert to pandas Series if numpy array
    if isinstance(data, np.ndarray):
        data = pd.Series(data)
    
    # Remove NaN values
    data = data.dropna()
    
    # Map regression type to arch package format
    reg_map = {'c': 'c', 'ct': 'ct', 'n': 'n'}
    regression = reg_map.get(regression, 'c')
    
    # Run Phillips-Perron test
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        pp = PhillipsPerron(data, trend=regression, lags=lags)
        result = pp.summary()
    
    # Extract and return results
    critical_values = {
        '1%': pp.critical_values['1%'],
        '5%': pp.critical_values['5%'],
        '10%': pp.critical_values['10%']
    }
    
    output = {
        'statistic': pp.stat,
        'pvalue': pp.pvalue,
        'critical_values': critical_values,
        'lags': pp.lags,
        'is_stationary': pp.pvalue < 0.05,
        'method': 'Phillips-Perron Test'
    }
    
    return output

def stationarity_analysis(data: Union[pd.Series, np.ndarray], 
                          diff_max: int = 2,
                          alpha: float = 0.05,
                          regression: str = 'c') -> Dict:
    """
    Comprehensive stationarity analysis of a time series.
    
    This function runs multiple stationarity tests (ADF, KPSS, Phillips-Perron) on the original series
    and its differenced versions to determine the order of integration I(d) needed for stationarity.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to analyze
    diff_max : int, optional
        Maximum number of differences to check (default: 2)
    alpha : float, optional
        Significance level (default: 0.05)
    regression : str, optional
        Type of regression to include in tests:
        'c': constant only (default)
        'ct': constant and trend
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'order_of_integration': The number of differences needed for stationarity
        - 'tests': Dictionary of test results for each difference level
        - 'is_stationary': Boolean indicating whether the original series is stationary
        - 'recommendation': Text recommendation for handling the series
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import stationarity_analysis
    >>> 
    >>> # Generate a non-stationary random walk
    >>> np.random.seed(42)
    >>> random_walk = np.cumsum(np.random.normal(0, 1, 1000))
    >>> result = stationarity_analysis(random_walk)
    >>> print(f"Order of integration: I({result['order_of_integration']})")
    >>> print(f"Recommendation: {result['recommendation']}")
    """
    # Convert to pandas Series if numpy array
    if isinstance(data, np.ndarray):
        data = pd.Series(data)
    
    # Remove NaN values
    data = data.dropna()
    
    # Initialize results
    results = {
        'order_of_integration': None,
        'tests': {},
        'is_stationary': False,
        'recommendation': ''
    }
    
    # Test original series
    adf_result = adf_test(data, regression=regression)
    kpss_result = kpss_test(data, regression=regression)
    pp_result = phillips_perron_test(data, regression=regression)
    
    # Determine if original series is stationary
    # We require at least 2 tests to agree
    adf_stationary = adf_result['pvalue'] < alpha
    kpss_stationary = kpss_result['pvalue'] > alpha  # KPSS null hypothesis is stationarity
    pp_stationary = pp_result['pvalue'] < alpha
    
    stationarity_votes = sum([adf_stationary, kpss_stationary, pp_stationary])
    original_is_stationary = stationarity_votes >= 2
    
    results['tests'][0] = {
        'adf': adf_result,
        'kpss': kpss_result,
        'phillips_perron': pp_result,
        'is_stationary': original_is_stationary
    }
    
    results['is_stationary'] = original_is_stationary
    
    # If original series is stationary, we're done
    if original_is_stationary:
        results['order_of_integration'] = 0
        results['recommendation'] = "The series is stationary. No differencing is required."
        return results
    
    # Otherwise, test differenced series up to diff_max
    diff_data = data.copy()
    for d in range(1, diff_max + 1):
        diff_data = diff_data.diff().dropna()
        
        adf_result = adf_test(diff_data, regression=regression)
        kpss_result = kpss_test(diff_data, regression=regression)
        pp_result = phillips_perron_test(diff_data, regression=regression)
        
        adf_stationary = adf_result['pvalue'] < alpha
        kpss_stationary = kpss_result['pvalue'] > alpha
        pp_stationary = pp_result['pvalue'] < alpha
        
        stationarity_votes = sum([adf_stationary, kpss_stationary, pp_stationary])
        is_stationary = stationarity_votes >= 2
        
        results['tests'][d] = {
            'adf': adf_result,
            'kpss': kpss_result,
            'phillips_perron': pp_result,
            'is_stationary': is_stationary
        }
        
        if is_stationary:
            results['order_of_integration'] = d
            if d == 1:
                results['recommendation'] = "The series is integrated of order 1. First differencing is recommended."
            else:
                results['recommendation'] = f"The series is integrated of order {d}. {d}th differencing is recommended."
            return results
    
    # If we reach here, the series is not stationary even after diff_max differences
    results['order_of_integration'] = None
    results['recommendation'] = f"The series is not stationary even after {diff_max} differences. Consider alternative transformations or models for non-stationary data."
    
    return results 

def descriptive_stats(data: Union[pd.Series, np.ndarray]) -> Dict:
    """
    Calculate comprehensive descriptive statistics for a time series.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to analyze
        
    Returns
    -------
    Dict
        Dictionary containing various descriptive statistics:
        - 'mean': Mean value
        - 'median': Median value
        - 'std': Standard deviation
        - 'var': Variance
        - 'min': Minimum value
        - 'max': Maximum value
        - 'range': Range (max - min)
        - 'skewness': Skewness
        - 'kurtosis': Excess kurtosis
        - 'iqr': Interquartile range
        - 'mad': Median absolute deviation
        - 'q25': 25th percentile
        - 'q75': 75th percentile
        - 'count': Number of observations
        - 'missing': Number of missing values
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import descriptive_stats
    >>> 
    >>> # Generate random data
    >>> np.random.seed(42)
    >>> data = np.random.normal(0, 1, 1000)
    >>> stats = descriptive_stats(data)
    >>> print(f"Mean: {stats['mean']:.4f}, Std Dev: {stats['std']:.4f}")
    >>> print(f"Skewness: {stats['skewness']:.4f}, Kurtosis: {stats['kurtosis']:.4f}")
    """
    # Convert to pandas Series if numpy array
    if isinstance(data, np.ndarray):
        data = pd.Series(data)
    
    # Calculate statistics
    data_no_na = data.dropna()
    count = len(data)
    missing = count - len(data_no_na)
    
    if len(data_no_na) == 0:
        logger.warning("All values in the data are NaN. Returning empty statistics.")
        return {
            'mean': np.nan,
            'median': np.nan,
            'std': np.nan,
            'var': np.nan,
            'min': np.nan,
            'max': np.nan,
            'range': np.nan,
            'skewness': np.nan,
            'kurtosis': np.nan,
            'iqr': np.nan,
            'mad': np.nan,
            'q25': np.nan,
            'q75': np.nan,
            'count': count,
            'missing': missing
        }
    
    # Calculate statistics using pandas methods
    q25 = data_no_na.quantile(0.25)
    q75 = data_no_na.quantile(0.75)
    
    # Return results
    return {
        'mean': data_no_na.mean(),
        'median': data_no_na.median(),
        'std': data_no_na.std(),
        'var': data_no_na.var(),
        'min': data_no_na.min(),
        'max': data_no_na.max(),
        'range': data_no_na.max() - data_no_na.min(),
        'skewness': data_no_na.skew(),
        'kurtosis': data_no_na.kurtosis(),  # Already excess kurtosis in pandas
        'iqr': q75 - q25,
        'mad': (data_no_na - data_no_na.median()).abs().median(),
        'q25': q25,
        'q75': q75,
        'count': count,
        'missing': missing
    }

def jarque_bera_test(data: Union[pd.Series, np.ndarray]) -> Dict:
    """
    Jarque-Bera test for normality.
    
    The null hypothesis of the test is that the data is normally distributed.
    The alternative hypothesis is that the data does not come from a normal distribution.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Jarque-Bera test statistic
        - 'pvalue': p-value
        - 'skewness': Sample skewness
        - 'kurtosis': Sample excess kurtosis
        - 'is_normal': Boolean indicating whether the data is normally distributed (p-value > 0.05)
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import jarque_bera_test
    >>> 
    >>> # Generate normally distributed data
    >>> np.random.seed(42)
    >>> normal_data = np.random.normal(0, 1, 1000)
    >>> result = jarque_bera_test(normal_data)
    >>> print(f"JB Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Is normal: {result['is_normal']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run Jarque-Bera test
    jb_stat, p_value, skew, kurtosis = jarque_bera(data)
    
    # Extract and return results
    output = {
        'statistic': jb_stat,
        'pvalue': p_value,
        'skewness': skew,
        'kurtosis': kurtosis,
        'is_normal': p_value > 0.05,
        'method': 'Jarque-Bera Test'
    }
    
    return output

def shapiro_wilk_test(data: Union[pd.Series, np.ndarray]) -> Dict:
    """
    Shapiro-Wilk test for normality.
    
    The null hypothesis of the test is that the data is normally distributed.
    The alternative hypothesis is that the data does not come from a normal distribution.
    
    Note: The Shapiro-Wilk test is generally more powerful for small sample sizes.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test. Must have between 3 and 5000 samples.
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Shapiro-Wilk test statistic
        - 'pvalue': p-value
        - 'is_normal': Boolean indicating whether the data is normally distributed (p-value > 0.05)
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import shapiro_wilk_test
    >>> 
    >>> # Generate normally distributed data
    >>> np.random.seed(42)
    >>> normal_data = np.random.normal(0, 1, 1000)
    >>> result = shapiro_wilk_test(normal_data)
    >>> print(f"SW Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Is normal: {result['is_normal']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Check if sample size is within acceptable range for Shapiro-Wilk
    if len(data) < 3 or len(data) > 5000:
        logger.warning(f"Sample size ({len(data)}) is outside the recommended range for "
                     f"Shapiro-Wilk test (3-5000). Results may be unreliable.")
        
        # If too many samples, take a random subset
        if len(data) > 5000:
            np.random.seed(42)  # For reproducibility
            data = np.random.choice(data, size=5000, replace=False)
    
    # Run Shapiro-Wilk test
    stat, p_value = stats.shapiro(data)
    
    # Extract and return results
    output = {
        'statistic': stat,
        'pvalue': p_value,
        'is_normal': p_value > 0.05,
        'method': 'Shapiro-Wilk Test'
    }
    
    return output

def anderson_darling_test(data: Union[pd.Series, np.ndarray]) -> Dict:
    """
    Anderson-Darling test for normality.
    
    The null hypothesis of the test is that the data is normally distributed.
    The alternative hypothesis is that the data does not come from a normal distribution.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Anderson-Darling test statistic
        - 'critical_values': Critical values for different significance levels
        - 'significance_levels': Corresponding significance levels
        - 'is_normal': Boolean indicating whether the data is normally distributed at 5% significance
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import anderson_darling_test
    >>> 
    >>> # Generate normally distributed data
    >>> np.random.seed(42)
    >>> normal_data = np.random.normal(0, 1, 1000)
    >>> result = anderson_darling_test(normal_data)
    >>> print(f"AD Statistic: {result['statistic']:.4f}")
    >>> print(f"Is normal at 5% significance: {result['is_normal']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run Anderson-Darling test
    result = stats.anderson(data, dist='norm')
    
    # Create dictionary of critical values
    significance_levels = result.significance_level
    critical_values = result.critical_values
    
    # Find the 5% significance level index (typically index 2)
    try:
        idx_5pct = np.where(significance_levels == 5)[0][0]
        is_normal = result.statistic < critical_values[idx_5pct]
    except IndexError:
        logger.warning("5% significance level not available in Anderson-Darling test results. Using closest available.")
        # Find the closest to 5%
        idx_5pct = np.abs(significance_levels - 5).argmin()
        is_normal = result.statistic < critical_values[idx_5pct]
    
    # Create dictionary of critical values
    crit_value_dict = {f"{significance_levels[i]}%": critical_values[i] for i in range(len(significance_levels))}
    
    # Extract and return results
    output = {
        'statistic': result.statistic,
        'critical_values': crit_value_dict,
        'significance_levels': significance_levels.tolist(),
        'is_normal': is_normal,
        'method': 'Anderson-Darling Test'
    }
    
    return output

def dagostino_pearson_test(data: Union[pd.Series, np.ndarray]) -> Dict:
    """
    D'Agostino-Pearson test for normality.
    
    The null hypothesis of the test is that the data is normally distributed.
    The alternative hypothesis is that the data does not come from a normal distribution.
    
    This test combines skew and kurtosis tests to form an omnibus test of normality.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': D'Agostino-Pearson test statistic
        - 'pvalue': p-value
        - 'is_normal': Boolean indicating whether the data is normally distributed (p-value > 0.05)
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import dagostino_pearson_test
    >>> 
    >>> # Generate normally distributed data
    >>> np.random.seed(42)
    >>> normal_data = np.random.normal(0, 1, 1000)
    >>> result = dagostino_pearson_test(normal_data)
    >>> print(f"D'Agostino-Pearson Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Is normal: {result['is_normal']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run D'Agostino-Pearson test
    stat, p_value = stats.normaltest(data)
    
    # Extract and return results
    output = {
        'statistic': stat,
        'pvalue': p_value,
        'is_normal': p_value > 0.05,
        'method': "D'Agostino-Pearson Test"
    }
    
    return output

def normality_analysis(data: Union[pd.Series, np.ndarray]) -> Dict:
    """
    Comprehensive normality analysis of a time series.
    
    This function runs multiple normality tests (Jarque-Bera, Shapiro-Wilk, 
    Anderson-Darling, D'Agostino-Pearson) on the data and provides a consensus result.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to analyze
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'tests': Dictionary of individual test results
        - 'consensus': The majority vote on normality
        - 'descriptive_stats': Basic descriptive statistics
        - 'recommendation': Text recommendation based on the analysis
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import normality_analysis
    >>> 
    >>> # Generate data with varying distributions
    >>> np.random.seed(42)
    >>> normal_data = np.random.normal(0, 1, 1000)
    >>> skewed_data = np.random.exponential(scale=1.0, size=1000)
    >>> 
    >>> normal_result = normality_analysis(normal_data)
    >>> skewed_result = normality_analysis(skewed_data)
    >>> 
    >>> print(f"Normal data consensus: {normal_result['consensus']}")
    >>> print(f"Skewed data consensus: {skewed_result['consensus']}")
    """
    # Convert to pandas Series if numpy array
    if isinstance(data, np.ndarray):
        data = pd.Series(data)
    
    # Remove NaN values
    data = data.dropna()
    
    # Calculate descriptive statistics
    desc_stats = descriptive_stats(data)
    
    # Run normality tests
    jb_test = jarque_bera_test(data)
    sw_test = shapiro_wilk_test(data)
    ad_test = anderson_darling_test(data)
    dp_test = dagostino_pearson_test(data)
    
    # Determine consensus (majority vote)
    normality_votes = sum([
        jb_test['is_normal'],
        sw_test['is_normal'],
        ad_test['is_normal'],
        dp_test['is_normal']
    ])
    
    is_normal = normality_votes >= 2  # At least 2 tests agree on normality
    
    # Create recommendation based on results
    if is_normal:
        recommendation = "The data appears to be normally distributed based on the majority of tests. " \
                         "Parametric methods are appropriate."
    else:
        # Check for specific issues
        if abs(desc_stats['skewness']) > 1.0:
            skew_direction = "positively" if desc_stats['skewness'] > 0 else "negatively"
            recommendation = f"The data is {skew_direction} skewed (skewness = {desc_stats['skewness']:.2f}). " \
                             "Consider a transformation like log, square root, or Box-Cox to achieve normality, " \
                             "or use non-parametric methods."
        elif desc_stats['kurtosis'] > 2.0:
            recommendation = f"The data has heavy tails (excess kurtosis = {desc_stats['kurtosis']:.2f}). " \
                             "Consider using robust methods or non-parametric approaches."
        elif desc_stats['kurtosis'] < -1.0:
            recommendation = f"The data has light tails (excess kurtosis = {desc_stats['kurtosis']:.2f}). " \
                             "Consider non-parametric methods."
        else:
            recommendation = "The data deviates from normality according to the majority of tests. " \
                             "Consider using non-parametric methods or transforming the data."
    
    # Create output dictionary
    output = {
        'tests': {
            'jarque_bera': jb_test,
            'shapiro_wilk': sw_test,
            'anderson_darling': ad_test,
            'dagostino_pearson': dp_test
        },
        'consensus': 'Normal' if is_normal else 'Non-normal',
        'descriptive_stats': desc_stats,
        'recommendation': recommendation
    }
    
    return output 

def engle_granger_test(y: Union[pd.Series, np.ndarray], 
                      x: Union[pd.Series, np.ndarray, pd.DataFrame, np.ndarray],
                      regression: str = 'c',
                      lags: Optional[int] = None) -> Dict:
    """
    Engle-Granger test for cointegration between two time series.
    
    The null hypothesis is that there is no cointegration, i.e., the series are not 
    cointegrated. The alternative hypothesis is that the series are cointegrated.
    
    Parameters
    ----------
    y : Union[pd.Series, np.ndarray]
        The dependent variable in the cointegration model
    x : Union[pd.Series, np.ndarray, pd.DataFrame, np.ndarray]
        The independent variable(s) in the cointegration model
    regression : str, optional
        Type of regression included in the test:
        'c': constant only (default)
        'ct': constant and trend
        'ctt': constant, linear and quadratic trend
        'n': no constant, no trend
    lags : int, optional
        Maximum number of lags in the ADF test on the residuals. If None, it's 
        automatically selected based on AIC.
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Test statistic
        - 'pvalue': p-value
        - 'critical_values': Dictionary of critical values at 1%, 5%, and 10% significance
        - 'regression_results': OLS regression results
        - 'residuals': The residuals from the cointegration regression
        - 'lags': Number of lags used
        - 'is_cointegrated': Boolean indicating whether the series are cointegrated
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import engle_granger_test
    >>> 
    >>> # Generate cointegrated series
    >>> np.random.seed(42)
    >>> x = np.cumsum(np.random.normal(0, 1, 1000))
    >>> y = 2 * x + np.random.normal(0, 1, 1000)  # y is cointegrated with x
    >>> 
    >>> result = engle_granger_test(y, x)
    >>> print(f"Test Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Is cointegrated: {result['is_cointegrated']}")
    """
    # Convert to pandas Series/DataFrame
    if isinstance(y, np.ndarray):
        y = pd.Series(y)
    
    if isinstance(x, np.ndarray):
        if x.ndim == 1:
            x = pd.Series(x)
        else:
            x = pd.DataFrame(x)
    
    # Remove NaN values
    if isinstance(x, pd.DataFrame):
        # For DataFrames, get the common index of non-NaN values
        valid_indices = ~y.isna()
        for col in x.columns:
            valid_indices = valid_indices & ~x[col].isna()
        
        y = y[valid_indices]
        x = x[valid_indices]
    else:
        # For Series, simpler approach
        valid_indices = ~y.isna() & ~x.isna()
        y = y[valid_indices]
        x = x[valid_indices]
    
    # Add constant to x if regression type includes it
    if regression in ['c', 'ct', 'ctt']:
        if isinstance(x, pd.Series):
            x = pd.DataFrame(x, columns=['x'])
        x = sm.add_constant(x)
    
    # Run OLS regression
    model = sm.OLS(y, x)
    results = model.fit()
    
    # Get residuals
    residuals = results.resid
    
    # Run ADF test on residuals
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        adf_result = adfuller(residuals, regression='n', maxlag=lags)
    
    # Extract and return results
    output = {
        'statistic': adf_result[0],
        'pvalue': adf_result[1],
        'critical_values': adf_result[4],
        'regression_results': results,
        'residuals': residuals,
        'lags': adf_result[2],
        'is_cointegrated': adf_result[1] < 0.05,
        'method': 'Engle-Granger Test'
    }
    
    return output

def johansen_test(data: Union[pd.DataFrame, np.ndarray],
                 det_order: int = 0,
                 k_ar_diff: int = 1) -> Dict:
    """
    Johansen test for cointegration among multiple time series.
    
    The Johansen test is used to determine the number of cointegrating relationships
    among multiple time series.
    
    Parameters
    ----------
    data : Union[pd.DataFrame, np.ndarray]
        The multivariate time series data. Each column is a separate time series.
    det_order : int, optional
        Deterministic term inclusion:
        -1: no deterministic terms
        0: constant term (default)
        1: constant and trend
    k_ar_diff : int, optional
        Number of lagged difference terms used in the model
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'trace_statistic': Trace test statistic
        - 'trace_critical_values': Critical values for the trace test
        - 'max_eig_statistic': Maximum eigenvalue test statistic
        - 'max_eig_critical_values': Critical values for the max eigenvalue test
        - 'n_cointegration': Number of cointegrating relationships (based on trace test at 5% level)
        - 'eigenvectors': The estimated cointegrating vectors
        - 'eigenvalues': The eigenvalues from the Johansen procedure
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import johansen_test
    >>> 
    >>> # Generate cointegrated series
    >>> np.random.seed(42)
    >>> x1 = np.cumsum(np.random.normal(0, 1, 1000))
    >>> x2 = 2 * x1 + np.random.normal(0, 1, 1000)  # x2 is cointegrated with x1
    >>> x3 = 0.5 * x1 + np.random.normal(0, 1, 1000)  # x3 is also cointegrated with x1
    >>> 
    >>> data = pd.DataFrame({'x1': x1, 'x2': x2, 'x3': x3})
    >>> result = johansen_test(data)
    >>> 
    >>> print(f"Number of cointegrating relationships: {result['n_cointegration']}")
    >>> print("Trace statistic:")
    >>> for i, stat in enumerate(result['trace_statistic']):
    >>>     print(f"H0: r <= {i}, Stat: {stat:.4f}, 5% Critical Value: {result['trace_critical_values'][i][1]:.4f}")
    """
    # Convert to pandas DataFrame
    if isinstance(data, np.ndarray):
        data = pd.DataFrame(data)
    
    # Remove NaN values
    data = data.dropna()
    
    # Run Johansen test
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            result = coint_johansen(data, det_order=det_order, k_ar_diff=k_ar_diff)
    except Exception as e:
        logger.error(f"Error in Johansen test: {str(e)}")
        # Return error dictionary
        return {
            'error': str(e),
            'method': 'Johansen Test',
            'success': False
        }
    
    # Determine number of cointegrating relationships (based on trace test at 5% significance)
    n_cointegration = 0
    for i, (stat, crit) in enumerate(zip(result.lr1, result.cvt)):
        if stat > crit[1]:  # 5% critical value
            n_cointegration += 1
        else:
            break
    
    # Extract and return results
    output = {
        'trace_statistic': result.lr1,
        'trace_critical_values': result.cvt,
        'max_eig_statistic': result.lr2,
        'max_eig_critical_values': result.cvm,
        'n_cointegration': n_cointegration,
        'eigenvectors': result.evec,
        'eigenvalues': result.eig,
        'method': 'Johansen Test',
        'success': True
    }
    
    return output

def cointegration_analysis(data: Union[pd.DataFrame, np.ndarray],
                          method: str = 'both',
                          significance_level: float = 0.05) -> Dict:
    """
    Comprehensive cointegration analysis of multiple time series.
    
    This function runs various cointegration tests on the provided time series
    and provides detailed insights on cointegration relationships.
    
    Parameters
    ----------
    data : Union[pd.DataFrame, np.ndarray]
        The multivariate time series data. Each column is a separate time series.
    method : str, optional
        Which tests to run:
        'engle-granger': Pairwise Engle-Granger tests
        'johansen': Johansen test for the full system
        'both': Both tests (default)
    significance_level : float, optional
        Significance level for determining cointegration (default: 0.05)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'johansen': Results from Johansen test (if method is 'johansen' or 'both')
        - 'engle_granger': Results from pairwise Engle-Granger tests (if method is 'engle-granger' or 'both')
        - 'cointegration_matrix': Matrix showing which pairs are cointegrated
        - 'n_cointegration': Number of cointegrating relationships
        - 'recommendation': Text recommendation based on the analysis
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import cointegration_analysis
    >>> 
    >>> # Generate cointegrated series
    >>> np.random.seed(42)
    >>> x1 = np.cumsum(np.random.normal(0, 1, 1000))
    >>> x2 = 2 * x1 + np.random.normal(0, 1, 1000)  # x2 is cointegrated with x1
    >>> x3 = np.cumsum(np.random.normal(0, 1, 1000))  # x3 is independent
    >>> 
    >>> data = pd.DataFrame({'x1': x1, 'x2': x2, 'x3': x3})
    >>> result = cointegration_analysis(data)
    >>> 
    >>> print(f"Number of cointegrating relationships: {result['n_cointegration']}")
    >>> print(f"Recommendation: {result['recommendation']}")
    """
    # Convert to pandas DataFrame
    if isinstance(data, np.ndarray):
        data = pd.DataFrame(data)
    
    # Remove NaN values
    data = data.dropna()
    
    # Initialize results
    results = {
        'n_cointegration': 0,
        'recommendation': '',
        'success': True
    }
    
    # Run Johansen test if requested
    if method in ['johansen', 'both']:
        johansen_result = johansen_test(data)
        results['johansen'] = johansen_result
        
        if not johansen_result.get('success', True):
            if method == 'johansen':
                results['success'] = False
                results['recommendation'] = f"Johansen test failed: {johansen_result.get('error', 'Unknown error')}"
                return results
            else:
                results['recommendation'] = f"Note: Johansen test failed: {johansen_result.get('error', 'Unknown error')}. Using only Engle-Granger results."
        else:
            results['n_cointegration'] = johansen_result['n_cointegration']
    
    # Run pairwise Engle-Granger tests if requested
    if method in ['engle-granger', 'both']:
        n_series = data.shape[1]
        eg_results = []
        cointegration_matrix = np.zeros((n_series, n_series), dtype=bool)
        
        # Run tests for each pair of series
        for i in range(n_series):
            for j in range(i+1, n_series):
                # Test with i as dependent
                eg_result_i = engle_granger_test(data.iloc[:, i], data.iloc[:, j])
                
                # Test with j as dependent
                eg_result_j = engle_granger_test(data.iloc[:, j], data.iloc[:, i])
                
                # A pair is considered cointegrated if either test shows cointegration
                is_cointegrated = eg_result_i['is_cointegrated'] or eg_result_j['is_cointegrated']
                
                # Update cointegration matrix
                cointegration_matrix[i, j] = is_cointegrated
                cointegration_matrix[j, i] = is_cointegrated
                
                # Store results
                eg_results.append({
                    'series_i': data.columns[i] if isinstance(data, pd.DataFrame) else f"Series {i}",
                    'series_j': data.columns[j] if isinstance(data, pd.DataFrame) else f"Series {j}",
                    'i_as_dependent': eg_result_i,
                    'j_as_dependent': eg_result_j,
                    'is_cointegrated': is_cointegrated
                })
        
        # Count cointegrated pairs
        if method == 'engle-granger':
            results['n_cointegration'] = np.sum(cointegration_matrix) // 2
        
        # Store Engle-Granger results
        results['engle_granger'] = {
            'results': eg_results,
            'n_cointegrated_pairs': np.sum(cointegration_matrix) // 2
        }
        
        # Convert cointegration matrix to DataFrame if input was DataFrame
        if isinstance(data, pd.DataFrame):
            results['cointegration_matrix'] = pd.DataFrame(
                cointegration_matrix,
                index=data.columns,
                columns=data.columns
            )
        else:
            results['cointegration_matrix'] = cointegration_matrix
    
    # Create recommendation
    n_series = data.shape[1]
    max_possible_relationships = n_series - 1
    
    if method == 'both':
        if results['n_cointegration'] == 0 and results['engle_granger']['n_cointegrated_pairs'] == 0:
            results['recommendation'] = "No cointegration detected among the series. These series do not have a long-term equilibrium relationship."
        elif results['n_cointegration'] > 0 and results['engle_granger']['n_cointegrated_pairs'] > 0:
            results['recommendation'] = f"Cointegration detected. Johansen test indicates {results['n_cointegration']} cointegrating relationship(s), and Engle-Granger identified {results['engle_granger']['n_cointegrated_pairs']} cointegrated pair(s). These series have long-term equilibrium relationships suitable for error correction models or pairs trading strategies."
        else:
            results['recommendation'] = f"Mixed evidence of cointegration. Johansen test indicates {results['n_cointegration']} cointegrating relationship(s), while Engle-Granger identified {results['engle_granger']['n_cointegrated_pairs']} cointegrated pair(s). Consider further investigation or using the test most appropriate for your specific application."
    elif method == 'johansen':
        if results['n_cointegration'] == 0:
            results['recommendation'] = "Johansen test detected no cointegration among the series. These series do not have a long-term equilibrium relationship."
        elif results['n_cointegration'] == max_possible_relationships:
            results['recommendation'] = f"Johansen test detected maximum possible cointegration ({max_possible_relationships} relationship(s)). All series are strongly interconnected with long-term equilibrium relationships."
        else:
            results['recommendation'] = f"Johansen test detected {results['n_cointegration']} cointegrating relationship(s) out of a maximum possible {max_possible_relationships}. These series have some long-term equilibrium relationships suitable for error correction models."
    elif method == 'engle-granger':
        max_possible_pairs = (n_series * (n_series - 1)) // 2
        if results['engle_granger']['n_cointegrated_pairs'] == 0:
            results['recommendation'] = "Engle-Granger tests detected no cointegration between any pairs of series. These series do not have pairwise long-term equilibrium relationships."
        elif results['engle_granger']['n_cointegrated_pairs'] == max_possible_pairs:
            results['recommendation'] = f"Engle-Granger tests detected cointegration between all pairs of series ({max_possible_pairs} pairs). All series are interconnected with long-term equilibrium relationships."
        else:
            results['recommendation'] = f"Engle-Granger tests detected cointegration in {results['engle_granger']['n_cointegrated_pairs']} out of {max_possible_pairs} possible pairs. Some series have long-term equilibrium relationships suitable for pairs trading strategies."
    
    return results 

def granger_causality_test(y: Union[pd.Series, np.ndarray],
                          x: Union[pd.Series, np.ndarray],
                          maxlag: int = 5,
                          verbose: bool = False) -> Dict:
    """
    Granger causality test to assess if one time series helps predict another.
    
    The null hypothesis is that x does not Granger-cause y. The alternative
    hypothesis is that x does Granger-cause y.
    
    Parameters
    ----------
    y : Union[pd.Series, np.ndarray]
        The dependent time series to be tested
    x : Union[pd.Series, np.ndarray]
        The independent time series to test for causality
    maxlag : int, optional
        Maximum number of lags to consider (default: 5)
    verbose : bool, optional
        Whether to print detailed test results (default: False)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'results': Dictionary of test results for each lag
        - 'min_pvalue': Minimum p-value across all lags
        - 'optimal_lag': Lag with the minimum p-value
        - 'has_causality': Boolean indicating whether x Granger-causes y (min_pvalue < 0.05)
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import granger_causality_test
    >>> 
    >>> # Generate causally related series
    >>> np.random.seed(42)
    >>> x = np.random.normal(0, 1, 1000)
    >>> y = np.zeros(1000)
    >>> for i in range(5, 1000):
    >>>     y[i] = 0.5 * x[i-1] + 0.3 * x[i-2] + 0.1 * x[i-3] + np.random.normal(0, 0.5)
    >>> 
    >>> result = granger_causality_test(y, x, maxlag=10)
    >>> print(f"Minimum p-value: {result['min_pvalue']:.4f} at lag {result['optimal_lag']}")
    >>> print(f"x Granger-causes y: {result['has_causality']}")
    """
    # Convert to pandas Series
    if isinstance(y, np.ndarray):
        y = pd.Series(y)
    
    if isinstance(x, np.ndarray):
        x = pd.Series(x)
    
    # Ensure series have the same length
    min_len = min(len(y), len(x))
    y = y.iloc[:min_len] if len(y) > min_len else y
    x = x.iloc[:min_len] if len(x) > min_len else x
    
    # Create DataFrame with both series
    data = pd.DataFrame({'y': y, 'x': x})
    data = data.dropna()
    
    # Run Granger causality test
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            result = grangercausalitytests(data, maxlag=maxlag, verbose=verbose)
    except Exception as e:
        logger.error(f"Error in Granger causality test: {str(e)}")
        # Return error dictionary
        return {
            'error': str(e),
            'method': 'Granger Causality Test',
            'success': False
        }
    
    # Extract and organize results
    lag_results = {}
    min_pvalue = 1.0
    optimal_lag = None
    
    for lag in range(1, maxlag + 1):
        # F-test p-value (Wald test)
        test_stat = result[lag][0]['ssr_ftest']
        p_value = test_stat[1]
        
        lag_results[lag] = {
            'f_statistic': test_stat[0],
            'pvalue': p_value,
            'df': test_stat[2],
            'ssr_chi2test': result[lag][0]['ssr_chi2test'],
            'lrtest': result[lag][0]['lrtest'],
            'params_ftest': result[lag][0]['params_ftest']
        }
        
        if p_value < min_pvalue:
            min_pvalue = p_value
            optimal_lag = lag
    
    # Extract and return results
    output = {
        'results': lag_results,
        'min_pvalue': min_pvalue,
        'optimal_lag': optimal_lag,
        'has_causality': min_pvalue < 0.05,
        'method': 'Granger Causality Test',
        'success': True
    }
    
    return output

def instantaneous_causality_test(y: Union[pd.Series, np.ndarray],
                                x: Union[pd.Series, np.ndarray],
                                lag: int = 1) -> Dict:
    """
    Instantaneous causality test to assess if two time series are contemporaneously related.
    
    The null hypothesis is that there is no instantaneous causality between x and y.
    The alternative hypothesis is that there is instantaneous causality.
    
    Parameters
    ----------
    y : Union[pd.Series, np.ndarray]
        First time series
    x : Union[pd.Series, np.ndarray]
        Second time series
    lag : int, optional
        Number of lags to include in the model (default: 1)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Test statistic
        - 'pvalue': p-value
        - 'df': Degrees of freedom
        - 'has_instantaneous_causality': Boolean indicating whether there is instantaneous causality
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import instantaneous_causality_test
    >>> 
    >>> # Generate contemporaneously related series
    >>> np.random.seed(42)
    >>> z = np.random.normal(0, 1, 1000)  # Common factor
    >>> x = 0.7 * z + np.random.normal(0, 0.5, 1000)
    >>> y = 0.5 * z + np.random.normal(0, 0.5, 1000)
    >>> 
    >>> result = instantaneous_causality_test(y, x)
    >>> print(f"Instantaneous causality p-value: {result['pvalue']:.4f}")
    >>> print(f"Has instantaneous causality: {result['has_instantaneous_causality']}")
    """
    # Convert to pandas Series
    if isinstance(y, np.ndarray):
        y = pd.Series(y)
    
    if isinstance(x, np.ndarray):
        x = pd.Series(x)
    
    # Ensure series have the same length
    min_len = min(len(y), len(x))
    y = y.iloc[:min_len] if len(y) > min_len else y
    x = x.iloc[:min_len] if len(x) > min_len else x
    
    # Create DataFrame with both series
    data = pd.DataFrame({'y': y, 'x': x})
    data = data.dropna()
    
    try:
        # Fit VAR model
        model = sm.tsa.VAR(data)
        results = model.fit(lag)
        
        # Get residuals
        resid = results.resid
        
        # Calculate correlation of residuals
        corr_matrix = np.corrcoef(resid.T)
        corr = corr_matrix[0, 1]
        
        # Calculate the test statistic
        n = len(data)
        statistic = n * np.log(1 - corr**2)
        
        # Calculate the p-value (chi-squared with 1 degree of freedom)
        p_value = 1 - stats.chi2.cdf(statistic, df=1)
        
    except Exception as e:
        logger.error(f"Error in instantaneous causality test: {str(e)}")
        # Return error dictionary
        return {
            'error': str(e),
            'method': 'Instantaneous Causality Test',
            'success': False
        }
    
    # Extract and return results
    output = {
        'statistic': statistic,
        'pvalue': p_value,
        'df': 1,
        'has_instantaneous_causality': p_value < 0.05,
        'method': 'Instantaneous Causality Test',
        'success': True
    }
    
    return output

def correlation_test(x: Union[pd.Series, np.ndarray], 
                    y: Union[pd.Series, np.ndarray],
                    method: str = 'pearson') -> Dict:
    """
    Correlation test to assess the relationship between two time series.
    
    Parameters
    ----------
    x : Union[pd.Series, np.ndarray]
        First time series
    y : Union[pd.Series, np.ndarray]
        Second time series
    method : str, optional
        Correlation method:
        'pearson': Pearson correlation coefficient (default)
        'spearman': Spearman rank correlation
        'kendall': Kendall's tau
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'correlation': Correlation coefficient
        - 'pvalue': p-value for the correlation
        - 'method': The correlation method used
        - 'n': Number of observations
        - 'is_significant': Boolean indicating whether the correlation is statistically significant
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import correlation_test
    >>> 
    >>> # Generate correlated series
    >>> np.random.seed(42)
    >>> x = np.random.normal(0, 1, 1000)
    >>> y = 0.7 * x + np.random.normal(0, 0.5, 1000)  # y is correlated with x
    >>> 
    >>> result_pearson = correlation_test(x, y, method='pearson')
    >>> result_spearman = correlation_test(x, y, method='spearman')
    >>> 
    >>> print(f"Pearson correlation: {result_pearson['correlation']:.4f}, p-value: {result_pearson['pvalue']:.4f}")
    >>> print(f"Spearman correlation: {result_spearman['correlation']:.4f}, p-value: {result_spearman['pvalue']:.4f}")
    """
    # Convert to numpy arrays
    if isinstance(x, pd.Series):
        x = x.values
    
    if isinstance(y, pd.Series):
        y = y.values
    
    # Ensure arrays have the same length
    min_len = min(len(x), len(y))
    x = x[:min_len] if len(x) > min_len else x
    y = y[:min_len] if len(y) > min_len else y
    
    # Remove NaN values (pairwise)
    mask = ~np.isnan(x) & ~np.isnan(y)
    x = x[mask]
    y = y[mask]
    
    # Calculate correlation based on method
    if method.lower() == 'pearson':
        corr, p_value = stats.pearsonr(x, y)
    elif method.lower() == 'spearman':
        corr, p_value = stats.spearmanr(x, y)
    elif method.lower() == 'kendall':
        corr, p_value = stats.kendalltau(x, y)
    else:
        raise ValueError(f"Unknown correlation method: {method}. Use 'pearson', 'spearman', or 'kendall'.")
    
    # Extract and return results
    output = {
        'correlation': corr,
        'pvalue': p_value,
        'method': f"{method.capitalize()} Correlation",
        'n': len(x),
        'is_significant': p_value < 0.05
    }
    
    return output

def rolling_correlation(x: Union[pd.Series, np.ndarray], 
                       y: Union[pd.Series, np.ndarray],
                       window: int = 60,
                       method: str = 'pearson') -> Dict:
    """
    Calculate rolling correlation between two time series.
    
    Parameters
    ----------
    x : Union[pd.Series, np.ndarray]
        First time series
    y : Union[pd.Series, np.ndarray]
        Second time series
    window : int, optional
        Rolling window size (default: 60)
    method : str, optional
        Correlation method:
        'pearson': Pearson correlation coefficient (default)
        'spearman': Spearman rank correlation
        'kendall': Kendall's tau
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'rolling_correlation': Series of rolling correlation values
        - 'mean_correlation': Mean correlation over the entire period
        - 'std_correlation': Standard deviation of correlation over the entire period
        - 'method': The correlation method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> import matplotlib.pyplot as plt
    >>> from advanced_trading.utils.statistical_tests import rolling_correlation
    >>> 
    >>> # Generate series with time-varying correlation
    >>> np.random.seed(42)
    >>> n = 1000
    >>> x = np.random.normal(0, 1, n)
    >>> 
    >>> # Create y with varying correlation to x
    >>> y = np.zeros(n)
    >>> for i in range(n):
    >>>     if i < n/3:
    >>>         y[i] = 0.8 * x[i] + np.random.normal(0, 0.4)  # Strong positive correlation
    >>>     elif i < 2*n/3:
    >>>         y[i] = -0.6 * x[i] + np.random.normal(0, 0.6)  # Moderate negative correlation
    >>>     else:
    >>>         y[i] = 0.1 * x[i] + np.random.normal(0, 0.9)  # Weak correlation
    >>> 
    >>> result = rolling_correlation(x, y, window=100)
    >>> 
    >>> # Plot rolling correlation
    >>> plt.figure(figsize=(12, 6))
    >>> plt.plot(result['rolling_correlation'])
    >>> plt.axhline(y=0, color='r', linestyle='--')
    >>> plt.title('Rolling Correlation')
    >>> plt.xlabel('Time')
    >>> plt.ylabel('Correlation Coefficient')
    >>> plt.show()
    """
    # Convert to pandas Series
    if isinstance(x, np.ndarray):
        x = pd.Series(x)
    
    if isinstance(y, np.ndarray):
        y = pd.Series(y)
    
    # Ensure series have the same length
    min_len = min(len(x), len(y))
    x = x.iloc[:min_len] if len(x) > min_len else x
    y = y.iloc[:min_len] if len(y) > min_len else y
    
    # Create DataFrame with both series
    data = pd.DataFrame({'x': x, 'y': y})
    
    # Calculate rolling correlation
    if method.lower() == 'pearson':
        rolling_corr = data['x'].rolling(window=window).corr(data['y'])
    elif method.lower() == 'spearman':
        rolling_corr = data['x'].rolling(window=window).corr(data['y'], method='spearman')
    elif method.lower() == 'kendall':
        # For Kendall's tau, we need to manually calculate for each window
        rolling_corr = pd.Series(index=data.index)
        for i in range(window - 1, len(data)):
            x_window = data['x'].iloc[i-window+1:i+1]
            y_window = data['y'].iloc[i-window+1:i+1]
            if len(x_window) == window:  # Ensure we have enough data for the window
                corr, _ = stats.kendalltau(x_window, y_window)
                rolling_corr.iloc[i] = corr
    else:
        raise ValueError(f"Unknown correlation method: {method}. Use 'pearson', 'spearman', or 'kendall'.")
    
    # Extract and return results
    output = {
        'rolling_correlation': rolling_corr,
        'mean_correlation': rolling_corr.mean(),
        'std_correlation': rolling_corr.std(),
        'method': f"Rolling {method.capitalize()} Correlation (window={window})"
    }
    
    return output

def causality_analysis(x: Union[pd.Series, np.ndarray], 
                      y: Union[pd.Series, np.ndarray],
                      maxlag: int = 10) -> Dict:
    """
    Comprehensive causality analysis between two time series.
    
    This function runs Granger causality tests in both directions and
    instantaneous causality test to provide insights on the causal relationships.
    
    Parameters
    ----------
    x : Union[pd.Series, np.ndarray]
        First time series
    y : Union[pd.Series, np.ndarray]
        Second time series
    maxlag : int, optional
        Maximum number of lags to consider in Granger causality tests (default: 10)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'x_causes_y': Results from Granger causality test where x may cause y
        - 'y_causes_x': Results from Granger causality test where y may cause x
        - 'instantaneous': Results from instantaneous causality test
        - 'correlation': Correlation between the series
        - 'relationship_type': The identified relationship type
        - 'recommendation': Text recommendation based on the analysis
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import causality_analysis
    >>> 
    >>> # Generate causally related series
    >>> np.random.seed(42)
    >>> x = np.random.normal(0, 1, 1000)
    >>> y = np.zeros(1000)
    >>> for i in range(5, 1000):
    >>>     y[i] = 0.5 * x[i-1] + 0.3 * x[i-2] + 0.1 * x[i-3] + np.random.normal(0, 0.5)
    >>> 
    >>> result = causality_analysis(x, y)
    >>> print(f"Relationship type: {result['relationship_type']}")
    >>> print(f"Recommendation: {result['recommendation']}")
    """
    # Convert to pandas Series
    if isinstance(x, np.ndarray):
        x = pd.Series(x)
    
    if isinstance(y, np.ndarray):
        y = pd.Series(y)
    
    # Run tests
    x_causes_y = granger_causality_test(y, x, maxlag=maxlag)
    y_causes_x = granger_causality_test(x, y, maxlag=maxlag)
    instantaneous = instantaneous_causality_test(x, y)
    correlation_result = correlation_test(x, y)
    
    # Determine the relationship type
    x_causes_y_flag = x_causes_y.get('has_causality', False)
    y_causes_x_flag = y_causes_x.get('has_causality', False)
    instantaneous_flag = instantaneous.get('has_instantaneous_causality', False)
    significant_corr = correlation_result.get('is_significant', False)
    
    if x_causes_y_flag and y_causes_x_flag:
        relationship = "Bidirectional Causality"
    elif x_causes_y_flag:
        relationship = "Unidirectional Causality (X -> Y)"
    elif y_causes_x_flag:
        relationship = "Unidirectional Causality (Y -> X)"
    elif instantaneous_flag:
        relationship = "Instantaneous Causality"
    elif significant_corr:
        relationship = "Correlation without Causality"
    else:
        relationship = "No Significant Relationship"
    
    # Create recommendation
    if relationship == "Bidirectional Causality":
        recommendation = "There is a feedback system between the two series. Consider using Vector Autoregression (VAR) models to capture the bidirectional relationship."
    elif relationship == "Unidirectional Causality (X -> Y)":
        lag = x_causes_y.get('optimal_lag', None)
        recommendation = f"X appears to cause Y with optimal lag {lag}. Consider using X as a leading indicator for Y, with a lag of {lag} periods."
    elif relationship == "Unidirectional Causality (Y -> X)":
        lag = y_causes_x.get('optimal_lag', None)
        recommendation = f"Y appears to cause X with optimal lag {lag}. Consider using Y as a leading indicator for X, with a lag of {lag} periods."
    elif relationship == "Instantaneous Causality":
        recommendation = "The series show contemporaneous causality, suggesting they are affected by common factors or one affects the other within the same time period. Consider using Structural Vector Autoregression (SVAR) models."
    elif relationship == "Correlation without Causality":
        corr = correlation_result.get('correlation', 0)
        if abs(corr) > 0.7:
            strength = "strong"
        elif abs(corr) > 0.4:
            strength = "moderate"
        else:
            strength = "weak"
        direction = "positive" if corr > 0 else "negative"
        recommendation = f"The series show a {strength} {direction} correlation (r={corr:.2f}) but no causal relationship. They may be influenced by a common external factor."
    else:
        recommendation = "No significant relationship detected. The series appear to be independent of each other."
    
    # Create output dictionary
    output = {
        'x_causes_y': x_causes_y,
        'y_causes_x': y_causes_x,
        'instantaneous': instantaneous,
        'correlation': correlation_result,
        'relationship_type': relationship,
        'recommendation': recommendation
    }
    
    return output 

def ljung_box_test(data: Union[pd.Series, np.ndarray], 
                  lags: int = 10,
                  model_df: int = 0) -> Dict:
    """
    Ljung-Box test for autocorrelation in a time series.
    
    The null hypothesis is that the data is independently distributed. The alternative
    hypothesis is that the data exhibits serial correlation.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
    lags : int, optional
        Number of lags to test (default: 10)
    model_df : int, optional
        Degrees of freedom consumed by a model (e.g., df in ARIMA(p,d,q) is p+q)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Ljung-Box Q statistic
        - 'pvalue': p-value
        - 'lags': Number of lags tested
        - 'has_autocorrelation': Boolean indicating whether the series has autocorrelation
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import ljung_box_test
    >>> 
    >>> # Generate autocorrelated series
    >>> np.random.seed(42)
    >>> n = 1000
    >>> ar_series = np.zeros(n)
    >>> for i in range(1, n):
    >>>     ar_series[i] = 0.7 * ar_series[i-1] + np.random.normal(0, 1)
    >>> 
    >>> result = ljung_box_test(ar_series, lags=20)
    >>> print(f"Ljung-Box Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Has autocorrelation: {result['has_autocorrelation']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run Ljung-Box test
    try:
        result = acorr_ljungbox(data, lags=[lags], return_df=False, model_df=model_df)
        statistic = result[0][0]
        p_value = result[1][0]
    except Exception as e:
        logger.error(f"Error in Ljung-Box test: {str(e)}")
        # Return error dictionary
        return {
            'error': str(e),
            'method': 'Ljung-Box Test',
            'success': False
        }
    
    # Extract and return results
    output = {
        'statistic': statistic,
        'pvalue': p_value,
        'lags': lags,
        'has_autocorrelation': p_value < 0.05,
        'method': 'Ljung-Box Test',
        'success': True
    }
    
    return output

def durbin_watson_test(data: Union[pd.Series, np.ndarray]) -> Dict:
    """
    Durbin-Watson test for autocorrelation in residuals.
    
    The test statistic is between 0 and 4:
    - A value of 2 indicates no autocorrelation
    - A value < 2 indicates positive autocorrelation
    - A value > 2 indicates negative autocorrelation
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Residuals to test for autocorrelation
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Durbin-Watson statistic
        - 'interpretation': Interpretation of the result
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import durbin_watson_test
    >>> 
    >>> # Generate autocorrelated residuals
    >>> np.random.seed(42)
    >>> n = 1000
    >>> residuals = np.zeros(n)
    >>> for i in range(1, n):
    >>>     residuals[i] = 0.7 * residuals[i-1] + np.random.normal(0, 1)
    >>> 
    >>> result = durbin_watson_test(residuals)
    >>> print(f"Durbin-Watson Statistic: {result['statistic']:.4f}")
    >>> print(f"Interpretation: {result['interpretation']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run Durbin-Watson test
    dw_stat = durbin_watson(data)
    
    # Interpret result
    if dw_stat < 1.5:
        interpretation = "Strong positive autocorrelation"
    elif dw_stat < 1.8:
        interpretation = "Moderate positive autocorrelation"
    elif dw_stat <= 2.2:
        interpretation = "No significant autocorrelation"
    elif dw_stat < 2.5:
        interpretation = "Moderate negative autocorrelation"
    else:
        interpretation = "Strong negative autocorrelation"
    
    # Extract and return results
    output = {
        'statistic': dw_stat,
        'interpretation': interpretation,
        'method': 'Durbin-Watson Test'
    }
    
    return output

def arch_test(data: Union[pd.Series, np.ndarray], lags: int = 5) -> Dict:
    """
    ARCH test for conditional heteroskedasticity in a time series.
    
    The null hypothesis is that there is no ARCH effect in the residuals.
    The alternative hypothesis is that there is an ARCH effect.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to test
    lags : int, optional
        Number of lags to test (default: 5)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'statistic': Test statistic (Lagrange multiplier)
        - 'pvalue': p-value
        - 'lags': Number of lags tested
        - 'has_arch_effect': Boolean indicating whether there is an ARCH effect
        - 'method': The test method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import arch_test
    >>> 
    >>> # Generate GARCH-like data with volatility clustering
    >>> np.random.seed(42)
    >>> n = 1000
    >>> returns = np.zeros(n)
    >>> volatility = np.zeros(n)
    >>> volatility[0] = 0.1
    >>> 
    >>> for i in range(1, n):
    >>>     volatility[i] = 0.1 + 0.2 * returns[i-1]**2 + 0.7 * volatility[i-1]
    >>>     returns[i] = np.random.normal(0, np.sqrt(volatility[i]))
    >>> 
    >>> result = arch_test(returns)
    >>> print(f"ARCH Test Statistic: {result['statistic']:.4f}")
    >>> print(f"p-value: {result['pvalue']:.4f}")
    >>> print(f"Has ARCH effect: {result['has_arch_effect']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Run ARCH test
    try:
        result = het_arch(data, nlags=lags)
        statistic = result[0]
        p_value = result[1]
    except Exception as e:
        logger.error(f"Error in ARCH test: {str(e)}")
        # Return error dictionary
        return {
            'error': str(e),
            'method': 'ARCH Test',
            'success': False
        }
    
    # Extract and return results
    output = {
        'statistic': statistic,
        'pvalue': p_value,
        'lags': lags,
        'has_arch_effect': p_value < 0.05,
        'method': 'ARCH Test',
        'success': True
    }
    
    return output 

def acf_pacf_analysis(data: Union[pd.Series, np.ndarray], 
                     max_lag: int = 40,
                     alpha: float = 0.05) -> Dict:
    """
    Calculate and analyze the autocorrelation function (ACF) and partial autocorrelation
    function (PACF) of a time series.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to analyze
    max_lag : int, optional
        Maximum number of lags to calculate (default: 40)
    alpha : float, optional
        Significance level for confidence intervals (default: 0.05)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'acf': Autocorrelation function values
        - 'pacf': Partial autocorrelation function values
        - 'acf_ci': Confidence interval bounds for ACF
        - 'pacf_ci': Confidence interval bounds for PACF
        - 'significant_acf': Lags with significant autocorrelation
        - 'significant_pacf': Lags with significant partial autocorrelation
        - 'suggested_ar': Suggested AR order based on PACF
        - 'suggested_ma': Suggested MA order based on ACF
        - 'method': The analysis method used
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> import matplotlib.pyplot as plt
    >>> from advanced_trading.utils.statistical_tests import acf_pacf_analysis
    >>> 
    >>> # Generate ARMA process
    >>> np.random.seed(42)
    >>> n = 1000
    >>> ar = np.zeros(n)
    >>> for i in range(2, n):
    >>>     ar[i] = 0.6 * ar[i-1] - 0.2 * ar[i-2] + np.random.normal(0, 1)
    >>> 
    >>> result = acf_pacf_analysis(ar, max_lag=20)
    >>> 
    >>> # Print suggested orders
    >>> print(f"Suggested AR order: {result['suggested_ar']}")
    >>> print(f"Suggested MA order: {result['suggested_ma']}")
    """
    # Convert to numpy array if pandas Series
    if isinstance(data, pd.Series):
        data = data.values
    
    # Remove NaN values
    data = data[~np.isnan(data)]
    
    # Calculate ACF and PACF
    acf_values = sm.tsa.acf(data, nlags=max_lag, fft=True)
    pacf_values = sm.tsa.pacf(data, nlags=max_lag, method='ols')
    
    # Calculate confidence intervals
    n = len(data)
    ci = stats.norm.ppf(1 - alpha / 2) / np.sqrt(n)
    acf_ci = [-ci, ci]
    pacf_ci = [-ci, ci]
    
    # Find significant lags
    significant_acf = [i for i in range(1, len(acf_values)) if abs(acf_values[i]) > ci]
    significant_pacf = [i for i in range(1, len(pacf_values)) if abs(pacf_values[i]) > ci]
    
    # Suggest ARMA orders
    # AR order: Look for cutoff in PACF
    ar_cutoff = find_acf_cutoff(pacf_values[1:], ci)
    
    # MA order: Look for cutoff in ACF
    ma_cutoff = find_acf_cutoff(acf_values[1:], ci)
    
    # Extract and return results
    output = {
        'acf': acf_values,
        'pacf': pacf_values,
        'acf_ci': acf_ci,
        'pacf_ci': pacf_ci,
        'significant_acf': significant_acf,
        'significant_pacf': significant_pacf,
        'suggested_ar': ar_cutoff,
        'suggested_ma': ma_cutoff,
        'method': 'ACF-PACF Analysis'
    }
    
    return output

def find_acf_cutoff(acf_values: np.ndarray, threshold: float) -> int:
    """
    Helper function to find the lag where ACF/PACF values cut off.
    
    Parameters
    ----------
    acf_values : np.ndarray
        ACF or PACF values (excluding lag 0)
    threshold : float
        Significance threshold
        
    Returns
    -------
    int
        Lag where cutoff occurs
    """
    # Look for the lag where values start staying within the CI
    for i in range(len(acf_values)):
        # Check if i and the next 2 lags are all within the CI
        if (i+2 < len(acf_values) and 
            abs(acf_values[i]) <= threshold and 
            abs(acf_values[i+1]) <= threshold and 
            abs(acf_values[i+2]) <= threshold):
            return i
    
    # If no clear cutoff, return the last significant lag
    for i in range(len(acf_values) - 1, -1, -1):
        if abs(acf_values[i]) > threshold:
            return i + 1
    
    return 0  # No significant lags

def time_series_diagnostics(data: Union[pd.Series, np.ndarray], 
                           max_lag: int = 20,
                           alpha: float = 0.05) -> Dict:
    """
    Comprehensive diagnostic tests for a time series.
    
    This function runs multiple tests to determine stationarity, autocorrelation,
    normality, and conditional heteroskedasticity in a time series.
    
    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Time series data to analyze
    max_lag : int, optional
        Maximum number of lags to test (default: 20)
    alpha : float, optional
        Significance level (default: 0.05)
        
    Returns
    -------
    Dict
        Dictionary containing:
        - 'stationarity': Results from stationarity tests
        - 'autocorrelation': Results from autocorrelation tests
        - 'normality': Results from normality tests
        - 'heteroskedasticity': Results from heteroskedasticity tests
        - 'acf_pacf': ACF and PACF analysis
        - 'summary': Dictionary of key findings
        - 'recommendation': Text recommendation based on the analysis
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> from advanced_trading.utils.statistical_tests import time_series_diagnostics
    >>> 
    >>> # Generate time series data
    >>> np.random.seed(42)
    >>> n = 1000
    >>> ar_series = np.zeros(n)
    >>> for i in range(1, n):
    >>>     ar_series[i] = 0.7 * ar_series[i-1] + np.random.normal(0, 1)
    >>> 
    >>> result = time_series_diagnostics(ar_series)
    >>> 
    >>> print(f"Is stationary: {result['summary']['is_stationary']}")
    >>> print(f"Has autocorrelation: {result['summary']['has_autocorrelation']}")
    >>> print(f"Is normally distributed: {result['summary']['is_normal']}")
    >>> print(f"Has heteroskedasticity: {result['summary']['has_heteroskedasticity']}")
    >>> print(f"Recommendation: {result['recommendation']}")
    """
    # Convert to pandas Series if numpy array
    if isinstance(data, np.ndarray):
        data = pd.Series(data)
    
    # Remove NaN values
    data = data.dropna()
    
    # Run stationarity tests
    stationarity = stationarity_analysis(data)
    
    # Run autocorrelation tests
    ljung_box = ljung_box_test(data, lags=max_lag)
    durbin_watson_result = durbin_watson_test(data)
    acf_pacf = acf_pacf_analysis(data, max_lag=max_lag, alpha=alpha)
    
    # Run normality tests
    normality = normality_analysis(data)
    
    # Run heteroskedasticity tests
    arch_result = arch_test(data, lags=min(max_lag, 10))
    
    # Summarize key findings
    summary = {
        'is_stationary': stationarity['is_stationary'],
        'order_of_integration': stationarity['order_of_integration'],
        'has_autocorrelation': ljung_box.get('has_autocorrelation', False),
        'is_normal': normality['consensus'] == 'Normal',
        'has_heteroskedasticity': arch_result.get('has_arch_effect', False),
        'suggested_ar': acf_pacf['suggested_ar'],
        'suggested_ma': acf_pacf['suggested_ma']
    }
    
    # Create recommendation
    recommendation = ""
    
    # Stationarity recommendations
    if not summary['is_stationary']:
        if summary['order_of_integration'] is not None:
            recommendation += f"The series is non-stationary and requires differencing of order {summary['order_of_integration']} to achieve stationarity. "
        else:
            recommendation += "The series is non-stationary and may require transformation or differencing to achieve stationarity. "
    else:
        recommendation += "The series is stationary. "
    
    # Autocorrelation recommendations
    if summary['has_autocorrelation']:
        ar_order = acf_pacf['suggested_ar']
        ma_order = acf_pacf['suggested_ma']
        
        if ar_order > 0 and ma_order > 0:
            recommendation += f"The series exhibits autocorrelation patterns suggesting an ARMA({ar_order},{ma_order}) structure. "
        elif ar_order > 0:
            recommendation += f"The series exhibits autocorrelation patterns suggesting an AR({ar_order}) structure. "
        elif ma_order > 0:
            recommendation += f"The series exhibits autocorrelation patterns suggesting an MA({ma_order}) structure. "
        else:
            recommendation += "The series exhibits statistically significant autocorrelation. "
    else:
        recommendation += "The series does not exhibit significant autocorrelation. "
    
    # Normality recommendations
    if not summary['is_normal']:
        recommendation += f"The residuals are not normally distributed: {normality['recommendation']} "
    else:
        recommendation += "The residuals appear to be normally distributed. "
    
    # Heteroskedasticity recommendations
    if summary['has_heteroskedasticity']:
        recommendation += "The series exhibits ARCH effects (volatility clustering), suggesting GARCH-type modeling may be appropriate. "
    else:
        recommendation += "The series has constant variance (homoskedasticity). "
    
    # Create output dictionary
    output = {
        'stationarity': stationarity,
        'autocorrelation': {
            'ljung_box': ljung_box,
            'durbin_watson': durbin_watson_result
        },
        'normality': normality,
        'heteroskedasticity': {
            'arch': arch_result
        },
        'acf_pacf': acf_pacf,
        'summary': summary,
        'recommendation': recommendation
    }
    
    return output
