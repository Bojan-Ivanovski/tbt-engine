import logging

from tbt_engine.market import MarketState
from tbt_engine.portfolio import Portfolio
from tbt_engine.signals.signal import Signal

logger = logging.getLogger(__name__)


class Buy(Signal):
    side = "buy"

    def execute(self, portfolio: Portfolio, market: MarketState) -> bool:
        price = market.get_latest_closed(self.asset.symbol)
        cost = self.asset * price
        if self.asset.quantity <= 0 or price <= 0:
            return False
        if portfolio.balance < cost:
            logger.warning("Not enough balance in portfolio to buy")
            return False
        if not portfolio.holdings.get(self.asset.symbol):
            portfolio.add_asset(self.asset)
        else:
            portfolio.holdings[self.asset.symbol] += self.asset
        portfolio.balance -= cost
        return True
