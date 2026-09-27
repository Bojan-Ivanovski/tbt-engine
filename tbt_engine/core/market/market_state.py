from typing import Iterable, KeysView

import pandas as pd

from tbt_engine.core.market.market import Market, MarketAsset


class MarketState:
    def __init__(
        self,
        market: Market,
        symbols: Iterable[str],
        last_closed_candle: int | None = None,
    ):
        normalized_symbols = sorted(set(symbol.upper() for symbol in symbols))
        missing_symbols = set(normalized_symbols).difference(market.assets)
        if missing_symbols:
            missing = ", ".join(sorted(missing_symbols))
            raise ValueError(f"Strategy assets are not registered in the market: {missing}")
        self._assets: dict[str, MarketAsset] = {
            symbol: market.assets[symbol] for symbol in normalized_symbols
        }
        self._time_asset = next(iter(market.assets.values()))
        self._current_candle = market.current_candle
        self._last_closed_candle = (
            market.current_candle if last_closed_candle is None else last_closed_candle
        )

    def get_all_symbols(self) -> KeysView[str]:
        return self._assets.keys()

    def get_past_data(self, symbol: str) -> pd.DataFrame:
        return self._assets[symbol].get_candle_range(self._last_closed_candle).copy()

    def get_market_time_iso(self) -> str:
        return self._time_asset.get_candle_time_iso(self._current_candle)
