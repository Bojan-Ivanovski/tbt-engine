from typing import Iterable

from tbt_engine.core.market.market import Market
from tbt_engine.core.market.market_state import MarketState


class ClosedMarketState(MarketState):
    def __init__(self, market: Market, symbols: Iterable[str]):
        super().__init__(market, symbols, market.current_candle)

    def get_latest_closed(self, symbol: str) -> float:
        return self._assets[symbol].get_close(self._last_closed_candle)
