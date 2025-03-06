# Trading Assistant Guide

The Trading Assistant is an interactive command-line tool that helps you navigate, use, and optimize the Advanced Trading System. This guide explains its key features and commands.

## Getting Started

To launch the Trading Assistant, navigate to the project directory and run:

```bash
./assistant_cli.py
```

You will see a welcome message and a command prompt (`>`). Type `help` to see all available commands.

## Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `help` | Display a list of available commands | `help` or `help backtest` |
| `backtest` | Run a backtest with specified parameters | `backtest BTC/USDT 2022-01-01 2023-01-01 1d 10000` |
| `analyze` | Analyze backtest results | `analyze` or `analyze /path/to/results` |
| `list_symbols` | List available trading symbols | `list_symbols binance` |
| `show_symbols` | Show popular cryptocurrency pairs | `show_symbols 10` |
| `show_features` | Show feature importance for a symbol's ML model | `show_features BTC/USDT` |
| `optimize` | Optimize a strategy parameter | `optimize BTC/USDT signal_threshold 0.3 0.7 5` |
| `explain` | Explain a trading concept | `explain risk_management` |
| `version` | Show system version and components | `version` |
| `clean` | Clean cached data or temp files | `clean cache` or `clean all` |
| `exit` | Exit the assistant | `exit` |

## Command Details

### Backtesting

The `backtest` command runs a backtest with the ML Ensemble strategy:

```
> backtest BTC/USDT 2022-01-01 2023-01-01 1d 10000
```

Arguments:
- Symbol (required): Trading pair like BTC/USDT
- Start date: Beginning date (YYYY-MM-DD format)
- End date: Ending date (YYYY-MM-DD format)
- Timeframe: Data frequency (default: 1d)
- Capital: Initial capital (default: 10000)

After running, the system will display performance metrics and save detailed results.

### Analyzing Results

The `analyze` command examines backtest results:

```
> analyze
```

Without arguments, it analyzes the most recent backtest. You can also specify a path:

```
> analyze /path/to/results/directory
```

The analysis includes metrics like returns, drawdowns, and trade statistics.

### Understanding Feature Importance

The `show_features` command reveals which indicators are most influential:

```
> show_features BTC/USDT
```

This helps you understand what drives the model's predictions.

### Learning About the System

The `explain` command provides detailed explanations of key concepts:

```
> explain backtest
> explain ml_strategy
> explain risk_management
> explain feature_engineering
> explain performance_metrics
> explain gpu_acceleration
```

Use this command to learn about different aspects of the system.

### Parameter Optimization

The `optimize` command helps you find optimal parameter values:

```
> optimize BTC/USDT signal_threshold 0.3 0.7 5
```

This tests a parameter across a range of values to find the best performance.

### Finding Trading Symbols

Two commands help with symbols:

```
> list_symbols binance
```
Lists all available pairs from the specified exchange.

```
> show_symbols 10
```
Shows the top N popular cryptocurrency pairs.

### System Maintenance

Keep your system clean with:

```
> clean cache    # Remove cached data
> clean logs     # Clear log files
> clean results  # Remove result directories
> clean all      # Clean everything
```

### Checking System Information

Use the `version` command to see:
- Current system version
- Installed packages
- GPU availability
- Configuration directories
- Available documentation

## Example Workflow

1. **Check system version**:
   ```
   > version
   ```

2. **View available symbols**:
   ```
   > show_symbols
   ```

3. **Run a backtest**:
   ```
   > backtest BTC/USDT 2022-01-01 2022-12-31 1d 10000
   ```

4. **Analyze the results**:
   ```
   > analyze
   ```

5. **Check which features are most important**:
   ```
   > show_features BTC/USDT
   ```

6. **Learn more about the strategy**:
   ```
   > explain ml_strategy
   ```

7. **Try optimizing a parameter**:
   ```
   > optimize BTC/USDT threshold_buy 0.6 0.8 5
   ```

8. **Clean up temporary files**:
   ```
   > clean cache
   ```

## Tips and Best Practices

1. **Start small**: Begin with short date ranges for faster backtests
2. **Analyze thoroughly**: Always check the results and feature importance
3. **Learn the concepts**: Use `explain` to understand the system components
4. **Regular cleanup**: Use `clean` periodically to save disk space
5. **Document findings**: Keep notes on what parameters work best
6. **Incremental optimization**: Change one parameter at a time
7. **Cross-validation**: Test on different time periods for robustness

## Troubleshooting

If you encounter issues:

1. Check logs in the `logs` directory
2. Use `version` to verify system components
3. Try `clean all` to reset cached data
4. Ensure you have the required data for the selected date range
5. For GPU issues, check if GPU libraries are properly installed 