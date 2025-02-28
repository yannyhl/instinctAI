# InstinctAI

A quantitative cryptocurrency trading system with AI-powered market analysis and strategy development.

## Overview

InstinctAI is a complete framework for developing, testing, and deploying quantitative trading strategies for cryptocurrency markets. It leverages the power of Claude to provide insights, analyze market conditions, and help optimize trading strategies.

Key features:

- 📈 **Funding Rate Momentum Strategy**: Combine funding rate analysis with technical indicators for edge
- 🧠 **Claude Integration**: Advanced market analysis and insights
- 📊 **Backtesting Engine**: Robust framework for testing strategies against historical data
- 🔄 **Modular Architecture**: Clear separation of concerns for easy extension
- 🌐 **Web API**: Access the AI assistant over HTTP
- 📱 **GPU Acceleration**: Built for performance on modern hardware

## System Requirements

- Python 3.9+
- CUDA-compatible GPU (for optimal performance)
- 8GB+ RAM
- Stable internet connection

## Installation

### Option 1: Automated Setup

Run the setup script to create the project structure and install dependencies:

```bash
git clone https://github.com/yourusername/instinct_ai.git
cd instinct_ai
python setup.py
```

### Option 2: Manual Setup

1. Create the project structure:

```bash
mkdir -p instinct_ai/{trading,assistant,backtesting,models,utils,data,logs,results}
```

2. Create a `.env` file with your API keys:

```bash
HYPERLIQUID_API_KEY=your_hyperliquid_api_key
HYPERLIQUID_SECRET_KEY=your_hyperliquid_secret_key
HYPERLIQUID_WALLET_ADDRESS=your_hyperliquid_wallet_address
ANTHROPIC_API_KEY=your_anthropic_api_key
# Add other API keys as needed
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Running a Backtest

Test a strategy against historical data:

```bash
cd instinct_ai
python -m trading.main --mode backtest --symbol BTC --timeframe 1h --strategy funding_momentum --analyze-results
```

Options:
- `--symbol`: Trading symbol (e.g., BTC, ETH)
- `--timeframe`: Data timeframe (e.g., 1h, 4h, 1d)
- `--strategy`: Strategy to use (funding_momentum, liquidity_scalping, volume_breakout)
- `--initial-cash`: Initial capital for the backtest
- `--refresh-data`: Force refresh of market data
- `--analyze-results`: Get AI analysis of backtest results

### Starting the Assistant API

Run the AI assistant service:

```bash
cd instinct_ai
python -m trading.main --mode assistant
```

The API will be available at `http://localhost:8000`

### Paper Trading Mode

Run the system in paper trading mode (simulated trading):

```bash
cd instinct_ai
python -m trading.main --mode paper --symbol BTC --timeframe 1h --use-assistant
```

Options:
- `--use-assistant`: Enable AI market analysis
- `--analysis-interval`: Seconds between market analyses (default: 300)

### Live Trading Mode (Use with caution!)

**Warning**: This mode trades with real funds.

```bash
cd instinct_ai
python -m trading.main --mode live --symbol BTC --timeframe 1h
```

## Strategies

### Funding Rate Momentum Strategy

This strategy combines funding rate analysis with momentum indicators for cryptocurrency trading:

- Seeks opportunities where funding rates provide additional edge
- Confirms direction with technical indicators (RSI, moving averages)
- Implements dynamic position sizing based on volatility
- Uses trailing stops and take profit targets for risk management

Key parameters:
- `funding_threshold`: Minimum funding rate to consider (default: 0.01)
- `rsi_overbought`: RSI overbought threshold (default: 70)
- `rsi_oversold`: RSI oversold threshold (default: 30)
- `risk_pct`: Maximum risk per trade (default: 0.02)

### Liquidity-Aware Scalping Strategy

A short-term trading strategy that utilizes order book liquidity analysis:

- Identifies significant liquidity imbalances
- Takes advantage of short-term price movements
- Implements tight risk controls with specific exit criteria
- Limits holding periods to reduce overnight risk

### Volume Breakout Strategy

A strategy that identifies and trades significant volume breakouts:

- Looks for volume spikes combined with price breakouts
- Uses ATR-based position sizing for risk management
- Implements trailing stops to lock in profits
- Monitors multiple positions simultaneously

## AI Assistant API

The assistant service provides the following endpoints:

- `POST /query`: General query to the assistant
- `POST /analyze/market`: Analyze current market conditions
- `POST /evaluate/trade`: Evaluate a trade setup
- `POST /backtest/run`: Run a backtest with specific parameters
- `POST /strategy/improve`: Get suggestions for improving a strategy

Example query:

```bash
curl -X POST "http://localhost:8000/analyze/market?symbol=BTC&timeframe=1h"
```

## Configuration

Main configuration options are in `config.py`. Key sections:

- `TRADING_CONFIG`: Default trading parameters
- `ASSISTANT_CONFIG`: AI assistant settings
- `BACKTEST_CONFIG`: Backtesting configuration
- `STRATEGY_PARAMS`: Default strategy parameters

## Project Structure

```
instinct_ai/
├── .env                       # Environment variables and API keys
├── config.py                  # Configuration settings
├── trading/
│   ├── main.py                # Main entry point
│   ├── strategies.py          # Strategy implementations
│   ├── data_manager.py        # Data collection and processing
│   └── exchange.py            # Exchange API interactions
├── assistant/
│   ├── service.py             # AI assistant service
│   ├── api.py                 # REST API interface
│   └── prompts.py             # Specialized prompts
├── backtesting/
│   ├── engine.py              # Backtesting engine
│   └── performance.py         # Performance metrics
├── models/                    # ML model implementations
├── utils/                     # Utility functions
├── data/                      # Market data storage
├── logs/                      # System logs
└── results/                   # Backtest results and plots
```

## Development

### Adding a New Strategy

1. Implement your strategy in `trading/strategies.py` by extending `bt.Strategy`
2. Add your strategy to the mapping in `backtesting/engine.py`
3. Add default parameters in `config.py`

### Extending the Assistant

1. Add new prompt templates in `assistant/prompts.py`
2. Implement new methods in `assistant/service.py`
3. Add new endpoints in `assistant/api.py`

## Troubleshooting

- **API Key Issues**: Ensure all API keys in the `.env` file are valid
- **Data Download Errors**: Check internet connection and API limits
- **GPU Memory Errors**: Reduce batch sizes in `config.py`
- **Import Errors**: Verify all dependencies are installed correctly

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Backtrader](https://www.backtrader.com/)
- AI powered by [Claude](https://www.anthropic.com/claude)
- Technical indicators from [TA-Lib](https://ta-lib.org/)

---

## Disclaimer

Trading cryptocurrency involves significant risk and may not be suitable for everyone. This software is for educational purposes only and is not financial advice. Always conduct your own research and consider your financial situation before trading with real funds.