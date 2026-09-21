from typing import Dict

from engine.asset import Asset


class Portfolio:
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = float(initial_balance)
        self.holdings: Dict[str, Asset] = {}

    def add_asset(self, asset: Asset):
        self.holdings[asset.symbol] = Asset(asset.symbol, asset.quantity)


class PortfolioState:
    def __init__(self, portfolio: Portfolio):
        self._balance = portfolio.balance
        self._holdings = {
            symbol: Asset(asset.symbol, asset.quantity)
            for symbol, asset in portfolio.holdings.items()
        }

    def balance(self) -> float:
        return self._balance

    def holdings(self) -> Dict[str, Asset]:
        return self._holdings

    def __repr__(self):
        return f"({self._balance},{self._holdings})"
