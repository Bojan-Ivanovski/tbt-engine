import math
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, KeysView

import pandas as pd

from engine.providers.provider import Provider


class MarketAsset:
    def __init__(self, symbol: str, history: pd.DataFrame):
        self.symbol = symbol
        self.history = history

    def align_to(self, index: pd.Index[Any]) -> None:
        self.history = self.history.loc[index]

    def get_candle_range(self, candle: int) -> pd.DataFrame:
        return self.history.iloc[: candle + 1]

    def get_close(self, candle: int) -> float:
        close = float(self.history["Close"].iloc[candle])
        if not math.isfinite(close) or close <= 0:
            raise ValueError(f"Invalid closing price for {self.symbol} at candle {candle}")
        return close

    def get_candle_time_iso(self, candle: int) -> str:
        raw_timestamp = self.history.index[candle]
        if isinstance(raw_timestamp, date) and not isinstance(raw_timestamp, datetime):
            return raw_timestamp.isoformat()

        timestamp = pd.Timestamp(raw_timestamp).to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return (
            timestamp.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )


class Market:
    def __init__(
        self,
        provider: Provider,
        start: date,
        end: date | None = None,
        interval: str = "1d",
    ):
        self.provider = provider
        self.start = start
        self.end = end
        self.interval = interval
        self.assets: Dict[str, MarketAsset] = {}
        self.current_candle = -1
        self.final_candle = 0

    def set_assets(self, symbols: Iterable[str]) -> None:
        normalized_symbols = list(dict.fromkeys(symbol.upper() for symbol in symbols))
        if not normalized_symbols:
            raise ValueError("A strategy must define at least one symbol")

        for symbol in normalized_symbols:
            history = self.provider.get_history(
                symbol=symbol,
                start=self.start,
                end=self.end,
                interval=self.interval,
            )
            if history.empty:
                raise ValueError(f"No price history returned for {symbol}")
            if "Close" not in history.columns:
                raise ValueError(f"Price history for {symbol} has no Close column")
            self.assets[symbol] = MarketAsset(symbol, history.sort_index())

        common_index: pd.Index[Any] | None = None
        for asset in self.assets.values():
            common_index = (
                asset.history.index
                if common_index is None
                else common_index.intersection(asset.history.index)
            )

        if common_index is None or common_index.empty:
            raise ValueError("The selected symbols have no overlapping price history")

        common_index = common_index.sort_values()
        for asset in self.assets.values():
            asset.align_to(common_index)
        self.final_candle = len(common_index)

    def next_candle(self) -> int:
        self.current_candle += 1
        return self.current_candle


class MarketState:
    def __init__(self, market: Market):
        self.assets = market.assets
        self.current_candle = market.current_candle

    def get_all_symbols(self) -> KeysView[str]:
        return self.assets.keys()

    def get_past_data(self, symbol: str) -> pd.DataFrame:
        return self.assets[symbol].get_candle_range(self.current_candle)

    def get_latest_closed(self, symbol: str) -> float:
        return self.assets[symbol].get_close(self.current_candle)

    def get_market_time_iso(self) -> str:
        first_asset = next(iter(self.assets.values()))
        return first_asset.get_candle_time_iso(self.current_candle)
