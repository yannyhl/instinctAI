# Migration Guide

This guide provides instructions for migrating useful components from previous implementations to the new `advanced_trading` structure.

## Overview

The new `advanced_trading` directory is a complete, self-contained trading system with improved backtesting, risk management, and strategy implementations. However, if you have custom components in previous implementations that you want to preserve, this guide will help you migrate them properly.

## Migration Process

### 1. Identify Components to Migrate

Review the old implementation and identify valuable components that aren't already in the new system:

- Custom strategies
- Utility functions
- Data connectors
- Visualization tools
- Configuration settings

### 2. Migrating Strategies

**Step 1**: Review strategy files in the old implementation

**Step 2**: Create a new strategy file in `advanced_trading/strategies/`

**Step 3**: Import the necessary modules from the new structure:

```python
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Import new utility modules
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils import technical_indicators as ti
from utils import signal_processing as sp
from utils import risk_management as rm
import config
```

**Step 4**: Refactor the strategy to match the new style:
- Update the class to use the new utility functions
- Make sure it supports proper risk management and position sizing
- Ensure compatibility with the backtest framework

### 3. Migrating Utility Functions

**Step 1**: Identify unique utility functions in the old implementation

**Step 2**: Determine the appropriate module in the new structure:
- `technical_indicators.py`: For indicator calculations
- `signal_processing.py`: For signal transformation and filtering
- `risk_management.py`: For position sizing and risk calculations

**Step 3**: Add the function to the appropriate module, ensuring compatibility with the new framework:
- Use proper typing hints
- Add documentation
- Consider GPU acceleration if applicable

Example:

```python
def custom_indicator(series: Union[pd.Series, np.ndarray], param1: float = 2.0) -> np.ndarray:
    """
    Calculate a custom indicator.
    
    Args:
        series: Time series data
        param1: Parameter for calculation
        
    Returns:
        Array with indicator values
    """
    # Implementation here
    return result
```

### 4. Migrating Data Connectors

**Step 1**: Identify custom data connectors in the old implementation

**Step 2**: Add them to `data_loader.py` as additional methods:

```python
def load_from_custom_source(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Load data from a custom source.
    
    Args:
        symbol: Symbol to load
        start_date: Start date
        end_date: End date
        
    Returns:
        DataFrame with market data
    """
    # Implementation here
    return data
```

### 5. Migrating Configuration Settings

**Step 1**: Identify custom configuration settings in the old implementation

**Step 2**: Add them to `config.py` in the appropriate section:

```python
# Custom strategy configurations
CUSTOM_STRATEGY_CONFIG = {
    "param1": 1.0,
    "param2": 2.0,
    "enabled": True
}
```

## Testing the Migration

After migrating components, test them thoroughly:

1. Run the `quick_test.py` script with your migrated components
2. Perform backtests using `run_simple_backtest.py`
3. Compare results with the old implementation to ensure consistency

## Common Migration Issues

### 1. Import Errors

**Problem**: `ModuleNotFoundError` or `ImportError` when running migrated code

**Solution**: Ensure all necessary modules are properly imported with the correct paths:

```python
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
```

### 2. Function Signature Mismatches

**Problem**: Errors due to different function parameters between old and new implementation

**Solution**: Update function calls to match the new signatures, using keyword arguments for clarity:

```python
# Old:
result = calculate_indicator(data, 10)

# New:
result = ti.calculate_indicator(data, window=10, method='standard')
```

### 3. Data Structure Differences

**Problem**: Errors due to different data structures or column names

**Solution**: Ensure your migrated code handles the data structures used in the new implementation:

```python
# Add compatibility layer if needed
def convert_data_format(old_format_data):
    # Convert to new format
    return new_format_data
```

## Final Checklist

Before finalizing the migration:

1. Ensure all necessary components are migrated
2. Verify that all migrated components work correctly
3. Update documentation to reflect the migrated components
4. Remove redundant code and files
5. Run a full backtest to verify the complete system works as expected 