import math
from abc import ABC, abstractmethod
from typing import TypeAlias

from tbt_engine.core.costs import ExecutionCost
from tbt_engine.core.execution import Fill
from tbt_engine.core.ledger import LedgerEntry
from tbt_engine.core.orders import Order, OrderEvent, OrderId
from tbt_engine.core.result import BacktestResult, EquityPoint, Trade
from tbt_engine.core.valuation import PortfolioValuation

SimulationRecord: TypeAlias = (
    Order | OrderEvent | Fill | ExecutionCost | LedgerEntry | PortfolioValuation
)


class ResultCollector(ABC):
    @abstractmethod
    def begin(self, starting_equity: float) -> None:
        """Start a run and reset any state retained from an earlier run."""
        raise NotImplementedError

    @abstractmethod
    def collect(self, record: SimulationRecord) -> None:
        """Observe one immutable record without changing simulation behavior."""
        raise NotImplementedError

    @abstractmethod
    def finalize(self) -> BacktestResult:
        """Finalize and return the collected result."""
        raise NotImplementedError


class InMemoryResultCollector(ResultCollector):
    """Default collector that builds the public in-memory backtest result."""

    def __init__(self) -> None:
        self._started = False
        self._finalized = False
        self._starting_equity = 0.0
        self._records: list[SimulationRecord] = []
        self._orders: dict[OrderId, Order] = {}
        self._order_events: list[OrderEvent] = []
        self._fills: list[Fill] = []
        self._execution_costs: list[ExecutionCost] = []
        self._ledger_entries: list[LedgerEntry] = []
        self._valuations: list[PortfolioValuation] = []

    @property
    def records(self) -> tuple[SimulationRecord, ...]:
        return tuple(self._records)

    def begin(self, starting_equity: float) -> None:
        starting_equity = float(starting_equity)
        if not math.isfinite(starting_equity) or starting_equity < 0:
            raise ValueError("Starting equity must be finite and non-negative")
        self._started = True
        self._finalized = False
        self._starting_equity = starting_equity
        self._records = []
        self._orders = {}
        self._order_events = []
        self._fills = []
        self._execution_costs = []
        self._ledger_entries = []
        self._valuations = []

    def collect(self, record: SimulationRecord) -> None:
        self._require_collecting()
        self._records.append(record)
        if isinstance(record, Order):
            self._orders[record.id] = record
        elif isinstance(record, OrderEvent):
            self._order_events.append(record)
        elif isinstance(record, Fill):
            self._fills.append(record)
        elif isinstance(record, ExecutionCost):
            self._execution_costs.append(record)
        elif isinstance(record, LedgerEntry):
            self._ledger_entries.append(record)
        else:
            self._valuations.append(record)

    def finalize(self) -> BacktestResult:
        self._require_collecting()
        if not self._valuations:
            raise ValueError("Cannot finalize a result without valuation records")
        trades = [
            Trade(
                time=fill.time,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                order_id=fill.order_id,
                phase=fill.phase.value,
            )
            for fill in self._fills
        ]
        equity_history = [
            EquityPoint(time=valuation.time, equity=valuation.total_equity)
            for valuation in self._valuations
        ]
        self._finalized = True
        return BacktestResult(
            starting_equity=self._starting_equity,
            ending_equity=self._valuations[-1].total_equity,
            trades=trades,
            equity_history=equity_history,
            orders=list(self._orders.values()),
            order_events=list(self._order_events),
            fills=list(self._fills),
            execution_costs=list(self._execution_costs),
            ledger_entries=list(self._ledger_entries),
            valuations=list(self._valuations),
        )

    def _require_collecting(self) -> None:
        if not self._started:
            raise RuntimeError("Result collection has not started")
        if self._finalized:
            raise RuntimeError("Result collection has already been finalized")
