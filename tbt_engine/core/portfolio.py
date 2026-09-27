import math
from dataclasses import dataclass, field
from typing import Dict

from tbt_engine.core.asset import Asset
from tbt_engine.core.costs import CostedFill
from tbt_engine.core.ledger import LedgerPosting, PortfolioLedger


@dataclass(frozen=True)
class InitialPosition:
    symbol: str
    quantity: float

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        quantity = float(self.quantity)
        if not symbol:
            raise ValueError("Initial position symbol must not be empty")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Initial position quantity must be finite and positive")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "quantity", quantity)


@dataclass(frozen=True)
class InitialPortfolio:
    cash: float = 1000.0
    currency: str = "USD"
    positions: tuple[InitialPosition, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        cash = float(self.cash)
        currency = self.currency.strip().upper()
        positions = tuple(sorted(self.positions, key=lambda position: position.symbol))
        if not math.isfinite(cash) or cash < 0:
            raise ValueError("Initial portfolio cash must be finite and non-negative")
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("Initial portfolio currency must be a three-letter code")
        symbols = [position.symbol for position in positions]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Initial portfolio cannot contain duplicate positions")
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "positions", positions)


class Portfolio:
    def __init__(
        self,
        initial_portfolio: InitialPortfolio | None = None,
        *,
        opened_at: str = "initial",
    ):
        initial_portfolio = InitialPortfolio() if initial_portfolio is None else initial_portfolio
        self._ledger = PortfolioLedger(
            initial_portfolio.cash,
            base_currency=initial_portfolio.currency,
            opened_at=opened_at,
            opening_positions=(
                (position.symbol, position.quantity) for position in initial_portfolio.positions
            ),
        )

    @property
    def balance(self) -> float:
        return self._ledger.state.cash

    @property
    def ledger(self) -> PortfolioLedger:
        return self._ledger

    @property
    def currency(self) -> str:
        return self._ledger.base_currency

    @property
    def holdings(self) -> Dict[str, Asset]:
        return {
            symbol: Asset(symbol, quantity) for symbol, quantity in self._ledger.state.positions
        }

    def post(self, costed_fills: tuple[CostedFill, ...]) -> LedgerPosting:
        return self._ledger.post(costed_fills)


class PortfolioState:
    def __init__(self, portfolio: Portfolio):
        self._balance = portfolio.balance
        self._currency = portfolio.currency
        self._holdings = {
            symbol: Asset(asset.symbol, asset.quantity)
            for symbol, asset in portfolio.holdings.items()
        }

    def balance(self) -> float:
        return self._balance

    def currency(self) -> str:
        return self._currency

    def holdings(self) -> Dict[str, Asset]:
        return {
            symbol: Asset(asset.symbol, asset.quantity) for symbol, asset in self._holdings.items()
        }

    def __repr__(self):
        return f"({self._balance},{self._holdings})"
