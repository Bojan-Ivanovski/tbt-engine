# TBT Engine

A standalone historical backtesting engine for long-only strategies. It downloads daily prices from Yahoo Finance, replays synchronized candles, executes buy and sell signals, and returns trades and portfolio equity in memory.

## Setup

```bash
python -m pip install .
```

For development, install the configured Python version with pyenv, then create a project-local virtual environment. The checked-in `.python-version` makes pyenv select the correct interpreter automatically inside the repository.

```bash
pyenv install --skip-existing 3.14.6
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the checks with:

```bash
isort --check-only .
black --check .
pyright
```

Build the wheel and source distribution with:

```bash
python -m build
```

## Library usage

The supported API is exported directly from `tbt_engine`:

```python
from tbt_engine import Engine, Strategy
```

Market-data providers, signals, portfolio snapshots, result types, and assets are also available from the top-level package. To use another market data source, implement `Provider.get_history()` and pass the provider to `Engine`.

## Run the example

```bash
python examples/sma_crossover.py
```

The included example applies a 5-day/20-day moving-average crossover to AAPL, NVDA, and MSFT. `Engine.start()` returns a `BacktestResult` with:

- starting and ending equity
- total return percentage
- accepted trades
- equity history
