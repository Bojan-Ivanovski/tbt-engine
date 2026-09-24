from tbt_engine.market import MarketState
from tbt_engine.portfolio import Portfolio
from tbt_engine.signals.signal import Signal


class Sell(Signal):
    side = "sell"

    def execute(self, portfolio: Portfolio, market: MarketState) -> bool:
        price = market.get_latest_closed(self.asset.symbol)
        holding = portfolio.holdings.get(self.asset.symbol)
        if (
            not holding
            or self.asset.quantity <= 0
            or self.asset.quantity > holding.quantity
            or price <= 0
        ):
            return False

        holding -= self.asset
        portfolio.balance += self.asset * price
        if holding.quantity == 0:
            del portfolio.holdings[self.asset.symbol]
        return True
