from dataclasses import dataclass


@dataclass(frozen=True)
class Trade:
    time: str
    symbol: str
    side: str
    quantity: float
    price: float


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

    @property
    def total_return_pct(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return ((self.ending_equity / self.starting_equity) - 1.0) * 100.0
