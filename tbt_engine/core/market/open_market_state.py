from typing import Iterable

from tbt_engine.core.market.market import Market
from tbt_engine.core.market.market_state import MarketState


class OpenMarketState(MarketState):
    def __init__(self, market: Market, symbols: Iterable[str]):
        super().__init__(market, symbols, market.current_candle - 1)

    def get_current_open(self, symbol: str) -> float:
        return self._assets[symbol].get_open(self._current_candle)
