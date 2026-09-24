# TBT Engine

A standalone historical backtesting engine for long-only strategies. It downloads daily prices from Yahoo Finance, replays synchronized market sessions, processes explicit orders, and returns trades, order history, and portfolio equity in memory.

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

Market-data providers, phase-specific market snapshots, orders, portfolio snapshots, result types, and assets are also available from the top-level package. To use another market data source, implement `Provider.get_history()` and pass the provider to `Engine`. Price history must contain `Open` and `Close` columns.

## Strategy lifecycle

Each synchronized market session has three strategy hooks:

1. `before_open()` sees completed bars through the previous session. Its next-open orders and cancellations are processed before the opening execution event.
2. `execute()` sees every current opening price but cannot see the active session's high, low, or close. It can submit an explicit session-close order or an order for a later open.
3. `after_close()` sees the newly completed bars. Its next-open orders remain pending overnight and can be cancelled by the following `before_open()` hook.

Hooks return `SubmitOrder` and `CancelOrder` commands. Strategies receive an immutable `OrderState` containing stable order IDs and current statuses. A cancellation never removes history: acceptance, fills, cancellations, rejections, and end-of-data expiry are retained in `BacktestResult.order_events`.

Orders based on a completed close cannot fill at that same close. `ExecutionTime.NEXT_OPEN` uses the next eligible opening event, while `ExecutionTime.SESSION_CLOSE` is available only to orders submitted before the close is revealed.

## Run the example

```bash
python examples/sma_crossover.py
```

The included example applies a 5-day/20-day moving-average crossover to AAPL, NVDA, and MSFT. `Engine.start()` returns a `BacktestResult` with:

- starting and ending equity
- total return percentage
- accepted trades
- orders and their lifecycle events
- equity history
