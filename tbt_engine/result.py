from dataclasses import dataclass, field

from tbt_engine.costs import ExecutionCost
from tbt_engine.execution import Fill
from tbt_engine.ledger import LedgerEntry
from tbt_engine.orders import Order, OrderEvent, OrderId
from tbt_engine.valuation import PortfolioValuation


@dataclass(frozen=True)
class Trade:
    time: str
    symbol: str
    side: str
    quantity: float
    price: float
    order_id: OrderId | None = None
    phase: str | None = None


@dataclass(frozen=True)
class EquityPoint:
    time: str
    equity: float


@dataclass
class BacktestResult:
    starting_equity: float
    ending_equity: float
    trades: list[Trade]
    equity_history: list[EquityPoint]
    orders: list[Order] = field(default_factory=lambda: list[Order]())
    order_events: list[OrderEvent] = field(default_factory=lambda: list[OrderEvent]())
    fills: list[Fill] = field(default_factory=lambda: list[Fill]())
    execution_costs: list[ExecutionCost] = field(default_factory=lambda: list[ExecutionCost]())
    ledger_entries: list[LedgerEntry] = field(default_factory=lambda: list[LedgerEntry]())
    valuations: list[PortfolioValuation] = field(default_factory=lambda: list[PortfolioValuation]())

    @property
    def total_return_pct(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return ((self.ending_equity / self.starting_equity) - 1.0) * 100.0
