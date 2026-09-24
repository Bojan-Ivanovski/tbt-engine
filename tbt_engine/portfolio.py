from typing import Dict

from tbt_engine.asset import Asset


class Portfolio:
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = float(initial_balance)
        self.holdings: Dict[str, Asset] = {}

    def add_asset(self, asset: Asset):
        self.holdings[asset.symbol] = Asset(asset.symbol, asset.quantity)

    def buy(self, symbol: str, quantity: float, price: float) -> bool:
        cost = quantity * price
        if quantity <= 0 or price <= 0 or self.balance < cost:
            return False
        holding = self.holdings.get(symbol)
        if holding is None:
            self.add_asset(Asset(symbol, quantity))
        else:
            holding += Asset(symbol, quantity)
        self.balance -= cost
        return True

    def sell(self, symbol: str, quantity: float, price: float) -> bool:
        holding = self.holdings.get(symbol)
        if holding is None or quantity <= 0 or price <= 0 or quantity > holding.quantity:
            return False
        holding -= Asset(symbol, quantity)
        self.balance += quantity * price
        if holding.quantity == 0:
            del self.holdings[symbol]
        return True


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
