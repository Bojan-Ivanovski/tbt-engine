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

The starting state is supplied as one immutable portfolio definition:

```python
from tbt_engine import Engine, InitialPortfolio, InitialPosition

engine = Engine(
    initial_portfolio=InitialPortfolio(
        cash=10_000,
        currency="USD",
        positions=(InitialPosition("AAPL", quantity=10),),
    )
)
```

The Market registers the union of `Strategy.define_assets()` and initial-position symbols. Strategy snapshots, order validation, and execution are restricted to the strategy-defined subset, while complete registered data remains available for portfolio valuation. Initial quantities enter the ledger as opening state rather than simulated trades, and their first available opening prices establish starting equity before any strategy command or execution event.

The public `Engine` setup facade lives at `tbt_engine.engine`, while simulation-domain implementation lives under `tbt_engine.core`. Extensible families are organized as packages: `collection`, `costs`, `execution`, `market`, and `valuation` each separate their shared contract from concrete implementations. Consumers should normally use the top-level `tbt_engine` exports; the family packages provide stable domain-level imports when more specific composition is needed. Providers and reusable strategy implementations remain organized in their existing domain packages.

## Simulation pipeline

`Engine` is the setup facade: it loads and aligns provider data, creates the portfolio, validates the selected models, and delegates the run to `SimulationPipeline`. The pipeline owns the deterministic session sequence, strategy callbacks, order processing, execution, accounting, valuation, result delivery, and end-of-data expiry.

`SimulationPipeline` is also exported from `tbt_engine` for tests and integrations that already have a prepared `Market` and `Portfolio`. A direct run follows exactly the same lifecycle and produces the same `BacktestResult` as `Engine`; it does not load data or introduce a separate configuration path.

## Strategy lifecycle

Each synchronized market session has three strategy hooks:

1. `before_open()` sees completed bars through the previous session. Its next-open orders and cancellations are processed before the opening execution event.
2. `execute()` sees every current opening price but cannot see the active session's high, low, or close. It can submit an explicit session-close order or an order for a later open.
3. `after_close()` sees the newly completed bars. Its next-open orders remain pending overnight and can be cancelled by the following `before_open()` hook.

Hooks return `SubmitOrder` and `CancelOrder` commands. Strategies receive an immutable `OrderState` containing stable order IDs and current statuses. A cancellation never removes history: acceptance, fills, cancellations, rejections, and end-of-data expiry are retained in `BacktestResult.order_events`.

Orders based on a completed close cannot fill at that same close. `ExecutionTime.NEXT_OPEN` uses the next eligible opening event, while `ExecutionTime.SESSION_CLOSE` is available only to orders submitted before the close is revealed.

## Execution and fills

An order records what a strategy requested; an immutable `Fill` records what an execution model produced. `Engine` accepts a replaceable `ExecutionModel` and provides `DailyBarExecutionModel` by default. The default model creates one complete fill at the eligible daily-bar open or close and does not infer an intraday price path, liquidity, spread, or slippage from OHLCV data.

Execution models receive an eligible order and an immutable `ExecutionMarketState` containing only prices available during that execution phase. They return an `ExecutionOutcome` with zero, one, or multiple fills and never mutate portfolio state directly. Outcomes can fill, partially fill, leave an order pending without a fill, or reject it. The engine validates order-to-fill identity and quantities before applying successful fills.

Custom models can be passed to `Engine(execution_model=...)`. Pending partial quantities remain eligible at later matching execution events, and all fills are available through `BacktestResult.fills`.

## Transaction costs

The engine uses `ZeroTransactionCostModel` by default, preserving the fill prices and accounting behavior of a backtest with no transaction costs. A deterministic standard model can be injected directly:

```python
from tbt_engine import Engine, StandardTransactionCostModel

engine = Engine(
    transaction_cost_model=StandardTransactionCostModel(
        commission_per_order=1.00,
        commission_per_unit=0.005,
        fee_rate=0.0001,
        spread_bps=2.0,
        slippage_bps=1.0,
    )
)
```

Spread and slippage adjust the execution price upward for buys and downward for sells. Commissions and fees are direct cash charges. Each accepted fill has a stable ID and preserves its pre-cost `reference_price`; its immutable `ExecutionCost` breakdown, currency, model identity, and parameters are available in `BacktestResult.execution_costs`. A model's JSON-serializable description is exposed through `TransactionCostModel.configuration` for future run-manifest integration.

Custom `TransactionCostModel` implementations can declare additional `MarketDataCapability` requirements. The engine rejects a model before simulation when its requirements are unavailable instead of silently estimating missing quote, trade, volatility, volume, or order-book data. Model construction is programmatic; project-wide configuration integration is intentionally separate.

## Portfolio accounting

Portfolio cash and long-only positions are derived from an append-only `PortfolioLedger`. The ledger begins with opening-cash and opening-position entries, then atomically posts each accepted execution as a trade entry plus separate commission and fee entries. Every execution entry links back to its order and fill. Spread and slippage are already reflected in the fill price and are not posted again as cash charges.

The ledger validates the complete execution batch before committing it, so insufficient cash, insufficient positions, duplicate fills, inconsistent references, or unsupported currencies cannot leave a partially updated portfolio. Its cached current state can be reconstructed with `PortfolioLedger.replay()`, and all immutable entries are returned through `BacktestResult.ledger_entries`.

`InitialPortfolio(currency=...)` selects the single portfolio base currency and defaults to `USD`. Transaction costs in another currency are rejected explicitly; foreign-exchange conversion is not inferred by the engine.

## Portfolio valuation

`Engine` uses `ClosePriceValuationModel` by default and accepts another implementation through `valuation_model=...`. After each close, the model receives immutable ledger-derived cash and positions plus a `ValuationMarketState` containing only the completed session's closing prices. It cannot access future candles or mutate accounting state.

Each immutable `PortfolioValuation` records its time, phase, model, currency, cash, position quantities, prices, market values, and reconciled total equity. These records are returned through `BacktestResult.valuations`; the existing equity history and ending equity retain their previous values under the default model.

## Result collection

Simulation output is observed through a replaceable `ResultCollector` supplied with `Engine(result_collector=...)`. The collector receives immutable order snapshots and lifecycle events, fills, execution costs, ledger entries, and valuations in deterministic simulation order. It cannot change the records or participate in strategy, execution, accounting, or valuation decisions.

The default `InMemoryResultCollector` produces the existing `BacktestResult`. Compatibility trades are derived from authoritative fills, while equity history and ending equity are derived from authoritative valuation records instead of being maintained as separate engine state. A collector is reset at the beginning of every run and finalized once after all end-of-data order events have been observed.

## Run the example

```bash
python examples/sma_crossover.py
```

The included example applies a 5-day/20-day moving-average crossover to AAPL, NVDA, and MSFT. `Engine.start()` returns a `BacktestResult` with:

- starting and ending equity
- total return percentage
- accepted trades
- orders and their lifecycle events
- explicit fills linked to their originating orders
- transaction-cost breakdowns linked to their fills
- immutable cash and position ledger entries
- auditable portfolio valuations
- equity history
