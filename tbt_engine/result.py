from dataclasses import dataclass, field

from tbt_engine.orders import Order, OrderEvent, OrderId


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

    @property
    def total_return_pct(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return ((self.ending_equity / self.starting_equity) - 1.0) * 100.0
