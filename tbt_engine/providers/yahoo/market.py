"""Yahoo Finance implementations of market-context capabilities."""

# pyright: reportUnknownArgumentType=false

from datetime import date, datetime
from typing import Any, cast

import pandas as pd

from tbt_engine.providers.capabilities.market import (
    MarketCapabilities,
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
    NasdaqCapability,
    NasdaqObservation,
    NasdaqObservationKind,
    NasdaqQuery,
    NasdaqResult,
    SectorETFCapability,
    SectorETFObservation,
    SectorETFObservationKind,
    SectorETFQuery,
    SectorETFResult,
    SP500Capability,
    SP500Interval,
    SP500IntervalUnit,
    SP500Observation,
    SP500ObservationType,
    SP500Query,
    SP500Result,
    SP500ValueUnit,
    VIXCapability,
    VIXQuery,
    VIXRecord,
    VIXResult,
)
from tbt_engine.providers.capabilities.market.nasdaq import NasdaqRecord, NasdaqRecordType
from tbt_engine.providers.capabilities.market.sector_etf import (
    SectorETFRecord,
    SectorETFRecordType,
)
from tbt_engine.providers.capabilities.market.sp500 import (
    SP500Calculation,
    SP500Record,
    SP500RecordType,
)

from .common import (
    Clock,
    TickerFactory,
    aware_datetime,
    call_yahoo,
    dataframe,
    in_datetime_range,
    source_metadata,
    symbol_text,
    yahoo_symbol,
)

_SP500_INTERVALS = {
    (1, SP500IntervalUnit.MINUTE): "1m",
    (2, SP500IntervalUnit.MINUTE): "2m",
    (5, SP500IntervalUnit.MINUTE): "5m",
    (15, SP500IntervalUnit.MINUTE): "15m",
    (30, SP500IntervalUnit.MINUTE): "30m",
    (60, SP500IntervalUnit.MINUTE): "60m",
    (90, SP500IntervalUnit.MINUTE): "90m",
    (1, SP500IntervalUnit.HOUR): "1h",
    (1, SP500IntervalUnit.DAY): "1d",
    (5, SP500IntervalUnit.DAY): "5d",
    (1, SP500IntervalUnit.WEEK): "1wk",
    (1, SP500IntervalUnit.MONTH): "1mo",
    (3, SP500IntervalUnit.MONTH): "3mo",
}
YAHOO_INTERVALS = frozenset(_SP500_INTERVALS.values())


def _market_symbol(market: object) -> str | tuple[str, str] | None:
    scheme = getattr(market, "scheme", "")
    value = getattr(market, "value", "")
    venue = getattr(market, "market", None)
    return yahoo_symbol(scheme, value, venue)


def _unavailable_market(query_market: object, clock: Clock, reason: str) -> MarketDataResult[Any]:
    return MarketDataResult(
        market=cast(Any, query_market),
        source=source_metadata(clock),
        availability=MarketDataAvailability.UNAVAILABLE,
        reason=reason,
    )


def _history(
    ticker_factory: TickerFactory,
    symbol: str | tuple[str, str],
    interval: str,
    start: datetime | None,
    end: datetime | None,
) -> pd.DataFrame:
    ticker = ticker_factory(symbol)
    return dataframe(
        call_yahoo(
            lambda: ticker.history(
                interval=interval,
                start=start,
                end=end,
                auto_adjust=False,
                actions=False,
            )
        ),
        "history",
    )


class YahooSP500Capability(SP500Capability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_sp500(self, query: SP500Query) -> SP500Result:
        symbol = _market_symbol(query.market)
        if symbol is None or symbol_text(symbol).upper() != "^GSPC":
            data = _unavailable_market(
                query.market, self._clock, "Yahoo identifies the S&P 500 index as ^GSPC"
            )
            return SP500Result(query, data)  # type: ignore[arg-type]
        if query.record_type is SP500RecordType.MEMBERSHIP:
            data = _unavailable_market(
                query.market,
                self._clock,
                "Yahoo Finance does not expose normalized S&P 500 constituent history",
            )
            return SP500Result(query, data)  # type: ignore[arg-type]
        assert isinstance(query.interval, SP500Interval)
        interval = _SP500_INTERVALS.get((query.interval.count, query.interval.unit))
        if interval is None:
            data = _unavailable_market(
                query.market, self._clock, "Yahoo does not support the requested S&P 500 interval"
            )
            return SP500Result(query, data)  # type: ignore[arg-type]
        assert query.start is None or isinstance(query.start, datetime)
        assert query.end is None or isinstance(query.end, datetime)
        retrieved = self._clock()
        frame = _history(self._ticker_factory, symbol, interval, query.start, query.end)
        records: list[SP500Observation] = []
        for index, row in frame.sort_index().iterrows():
            stamp = aware_datetime(index)
            if not in_datetime_range(stamp, query.start, query.end):
                continue
            close = row.get("Close")
            if close is None or bool(pd.isna(close)):
                continue
            records.append(
                SP500Observation(
                    metadata=MarketDataMetadata(
                        query.market,
                        source_metadata(lambda: retrieved, f"^GSPC:{stamp.isoformat()}"),
                        stamp,
                    ),
                    interval=query.interval,
                    observation_type=SP500ObservationType.LEVEL,
                    value=float(close),
                    unit=SP500ValueUnit.INDEX_POINTS,
                    calculation=SP500Calculation.CLOSING_LEVEL,
                )
            )
        data: MarketDataResult[SP500Record] = MarketDataResult(
            query.market,
            source_metadata(lambda: retrieved),
            MarketDataAvailability.AVAILABLE,
            tuple(records),
        )
        return SP500Result(query, data)


class YahooNasdaqCapability(NasdaqCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_nasdaq(self, query: NasdaqQuery) -> NasdaqResult:
        symbol = _market_symbol(query.market)
        if symbol is None or symbol_text(symbol).upper() not in {"^IXIC", "^NDX"}:
            data = _unavailable_market(
                query.market,
                self._clock,
                "Yahoo supports explicit Nasdaq index tickers ^IXIC and ^NDX",
            )
            return NasdaqResult(query, data)  # type: ignore[arg-type]
        if query.record_type is NasdaqRecordType.MEMBERSHIP:
            data = _unavailable_market(
                query.market,
                self._clock,
                "Yahoo Finance does not expose normalized Nasdaq constituent history",
            )
            return NasdaqResult(query, data)  # type: ignore[arg-type]
        if (
            isinstance(query.start, date)
            and not isinstance(query.start, datetime)
            or isinstance(query.end, date)
            and not isinstance(query.end, datetime)
        ):
            data = _unavailable_market(
                query.market,
                self._clock,
                "Yahoo Nasdaq observations require datetime query bounds",
            )
            return NasdaqResult(query, data)  # type: ignore[arg-type]
        if isinstance(query.start, datetime) or query.start is None:
            start = query.start
        else:
            start = datetime.combine(query.start, datetime.min.time()).astimezone()
        if isinstance(query.end, datetime) or query.end is None:
            end = query.end
        else:
            end = datetime.combine(query.end, datetime.min.time()).astimezone()
        retrieved = self._clock()
        frame = _history(self._ticker_factory, symbol, "1d", start, end)
        records: list[NasdaqObservation] = []
        for index, row in frame.sort_index().iterrows():
            stamp = aware_datetime(index)
            close = row.get("Close")
            if close is None or bool(pd.isna(close)):
                continue
            records.append(
                NasdaqObservation(
                    MarketDataMetadata(
                        query.market,
                        source_metadata(
                            lambda: retrieved,
                            f"{symbol_text(symbol)}:{stamp.isoformat()}",
                        ),
                        stamp,
                    ),
                    NasdaqObservationKind.LEVEL,
                    float(close),
                )
            )
        data: MarketDataResult[NasdaqRecord] = MarketDataResult(
            query.market,
            source_metadata(lambda: retrieved),
            MarketDataAvailability.AVAILABLE,
            tuple(records),
        )
        return NasdaqResult(query, data)


class YahooSectorETFCapability(SectorETFCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_sector_etf(self, query: SectorETFQuery) -> SectorETFResult:
        symbol = _market_symbol(query.market)
        if symbol is None:
            data = _unavailable_market(
                query.market, self._clock, "Yahoo requires a ticker identity"
            )
            return SectorETFResult(query, data)  # type: ignore[arg-type]
        if query.record_type is SectorETFRecordType.MAPPING:
            data = _unavailable_market(
                query.market,
                self._clock,
                "Yahoo Finance does not expose effective-dated sector mappings",
            )
            return SectorETFResult(query, data)  # type: ignore[arg-type]
        retrieved = self._clock()
        frame = _history(self._ticker_factory, symbol, "1d", query.start, query.end)
        records: list[SectorETFObservation] = []
        for index, row in frame.sort_index().iterrows():
            stamp = aware_datetime(index)
            if not in_datetime_range(stamp, query.start, query.end):
                continue
            close = row.get("Close")
            if close is None or bool(pd.isna(close)):
                continue
            records.append(
                SectorETFObservation(
                    MarketDataMetadata(
                        query.market,
                        source_metadata(
                            lambda: retrieved,
                            f"{symbol_text(symbol)}:{stamp.isoformat()}",
                        ),
                        stamp,
                    ),
                    SectorETFObservationKind.LEVEL,
                    float(close),
                    "1d",
                    "unadjusted",
                )
            )
        data: MarketDataResult[SectorETFRecord] = MarketDataResult(
            query.market,
            source_metadata(lambda: retrieved),
            MarketDataAvailability.AVAILABLE,
            tuple(records),
        )
        return SectorETFResult(query, data)


class YahooVIXCapability(VIXCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_vix(self, query: VIXQuery) -> VIXResult:
        symbol = _market_symbol(query.market)
        if symbol is None or symbol_text(symbol).upper() != "^VIX":
            data = _unavailable_market(
                query.market, self._clock, "Yahoo identifies the VIX index as ^VIX"
            )
            return VIXResult(query, data)  # type: ignore[arg-type]
        if query.interval not in YAHOO_INTERVALS:
            data = _unavailable_market(
                query.market, self._clock, f"Yahoo does not support interval {query.interval}"
            )
            return VIXResult(query, data)  # type: ignore[arg-type]
        retrieved = self._clock()
        frame = _history(self._ticker_factory, symbol, query.interval, query.start, query.end)
        records: list[VIXRecord] = []
        for index, row in frame.sort_index().iterrows():
            stamp = aware_datetime(index)
            if not in_datetime_range(stamp, query.start, query.end):
                continue
            close = row.get("Close")
            if close is None or bool(pd.isna(close)):
                continue
            records.append(
                VIXRecord(
                    MarketDataMetadata(
                        query.market,
                        source_metadata(lambda: retrieved, f"^VIX:{stamp.isoformat()}"),
                        stamp,
                    ),
                    float(close),
                    query.interval,
                )
            )
        data = MarketDataResult(
            query.market,
            source_metadata(lambda: retrieved),
            MarketDataAvailability.AVAILABLE,
            tuple(records),
        )
        return VIXResult(query, data)


def yahoo_market_capabilities(ticker_factory: TickerFactory, clock: Clock) -> MarketCapabilities:
    return MarketCapabilities(
        "YahooProvider",
        (
            YahooSP500Capability(ticker_factory, clock),
            YahooNasdaqCapability(ticker_factory, clock),
            YahooSectorETFCapability(ticker_factory, clock),
            YahooVIXCapability(ticker_factory, clock),
        ),
    )


__all__ = [
    "YahooNasdaqCapability",
    "YahooSP500Capability",
    "YahooSectorETFCapability",
    "YahooVIXCapability",
    "yahoo_market_capabilities",
]
