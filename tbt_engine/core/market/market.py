import math
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable

import pandas as pd

from tbt_engine.providers.provider import Provider


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

    def get_open(self, candle: int) -> float:
        open_price = float(self.history["Open"].iloc[candle])
        if not math.isfinite(open_price) or open_price <= 0:
            raise ValueError(f"Invalid opening price for {self.symbol} at candle {candle}")
        return open_price

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
        normalized_symbols = sorted(set(symbol.upper() for symbol in symbols))
        if not normalized_symbols:
            raise ValueError("A market must register at least one symbol")

        self.assets = {symbol: self._load_asset(symbol) for symbol in normalized_symbols}
        self._align_assets()

    def _load_asset(self, symbol: str) -> MarketAsset:
        history = self.provider.get_history(
            symbol=symbol,
            start=self.start,
            end=self.end,
            interval=self.interval,
        )
        if history.empty:
            raise ValueError(f"No price history returned for {symbol}")
        missing_columns = {"Open", "Close"}.difference(history.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Price history for {symbol} is missing columns: {missing}")
        return MarketAsset(symbol, history.sort_index())

    def _align_assets(self) -> None:
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
