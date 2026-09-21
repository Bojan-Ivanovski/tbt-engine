# TBT Engine

A minimal historical backtesting engine for long-only strategies. It downloads daily prices from Yahoo Finance, replays synchronized candles, executes buy and sell signals, and returns trades and portfolio equity in memory.

## Setup

```bash
python -m pip install .
```

For development, activate the project's pyenv environment and install the formatting and type-checking tools:

```bash
pyenv activate tbt-engine
python -m pip install -e ".[dev]"
```

Run the checks with:

```bash
isort --check-only .
black --check .
pyright
```

## Run the example

```bash
python main.py
```

The included example applies a 5-day/20-day moving-average crossover to AAPL, NVDA, and MSFT. `Engine.start()` returns a `BacktestResult` with:

- starting and ending equity
- total return percentage
- accepted trades
- equity history

To use another market data source, implement `Provider.get_history()` and pass the provider to `Engine`.
