from typing import Dict

from tbt_engine.core.asset import Asset
from tbt_engine.core.costs import CostedFill
from tbt_engine.core.ledger import LedgerPosting, PortfolioLedger


class Portfolio:
    def __init__(
        self,
        initial_balance: float = 1000.0,
        *,
        currency: str = "USD",
        opened_at: str = "initial",
    ):
        self._ledger = PortfolioLedger(
            initial_balance,
            base_currency=currency,
            opened_at=opened_at,
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
