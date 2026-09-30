"""Yahoo Finance implementation of commodity and FX observations."""

# pyright: reportUnknownArgumentType=false

from datetime import datetime, timedelta

import pandas as pd

from tbt_engine.providers.capabilities.macro import (
    CommoditiesFXCapability,
    CommoditiesFXQuery,
    CommoditiesFXRecord,
    CommoditiesFXResult,
    InstrumentKind,
    MacroCapabilities,
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
    MacroUnitMetadata,
    ObservationPeriod,
    SeasonalAdjustmentStatus,
)

from .common import (
    Clock,
    TickerFactory,
    aware_datetime,
    call_yahoo,
    dataframe,
    source_metadata,
)
from .market import YAHOO_INTERVALS


class YahooCommoditiesFXCapability(CommoditiesFXCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_commodities_fx(self, query: CommoditiesFXQuery) -> CommoditiesFXResult:
        if query.series.namespace not in {"ticker", "yahoo"}:
            return self._unavailable(query, "Yahoo requires a ticker or yahoo series namespace")
        if query.interval not in YAHOO_INTERVALS:
            return self._unavailable(query, f"Yahoo does not support interval {query.interval}")
        symbol = query.series.value
        upper_symbol = symbol.upper()
        is_fx = upper_symbol.endswith("=X")
        is_commodity = upper_symbol.endswith("=F")
        if not is_fx and not is_commodity:
            return self._unavailable(
                query,
                "Yahoo commodity/FX series must use an =F futures or =X currency ticker",
            )
        if is_fx:
            pair = upper_symbol.removesuffix("=X").replace("/", "")
            if len(pair) != 6 or not pair.isalpha():
                return self._unavailable(query, "Yahoo FX ticker does not identify a currency pair")
            base_currency, quote_currency = pair[:3], pair[3:]
            quote_unit = "exchange_rate"
            kind = InstrumentKind.FX
        else:
            base_currency = None
            quote_currency = query.series.variant
            quote_unit = query.series.variant or "price"
            kind = InstrumentKind.COMMODITY

        retrieved = self._clock()
        ticker = self._ticker_factory(symbol)
        frame = dataframe(
            call_yahoo(
                lambda: ticker.history(
                    interval=query.interval,
                    start=query.start,
                    end=query.end,
                    auto_adjust=False,
                    actions=False,
                )
            ),
            "commodity/FX history",
        )
        records: list[CommoditiesFXRecord] = []
        for index, row in frame.sort_index().iterrows():
            interval_start = aware_datetime(index)
            available_at = _interval_end(interval_start, query.interval)
            if query.start is not None and available_at < query.start:
                continue
            if query.end is not None and available_at >= query.end:
                continue
            close = row.get("Close")
            if close is None or bool(pd.isna(close)):
                continue
            period_start = interval_start.date()
            period_end = max(available_at.date(), period_start + timedelta(days=1))
            record_source = source_metadata(
                lambda: retrieved, f"{symbol}:{available_at.isoformat()}"
            )
            records.append(
                CommoditiesFXRecord(
                    metadata=MacroDataMetadata(
                        series=query.series,
                        source=record_source,
                        observation_period=ObservationPeriod(period_start, period_end),
                        available_at=available_at,
                        unit=MacroUnitMetadata(
                            quote_unit,
                            currency=quote_currency if kind is InstrumentKind.COMMODITY else None,
                        ),
                        seasonal_adjustment=SeasonalAdjustmentStatus.NOT_APPLICABLE,
                    ),
                    instrument_kind=kind,
                    value=float(close),
                    quote_unit=quote_unit,
                    quote_currency=quote_currency,
                    base_currency=base_currency,
                )
            )
        data = MacroDataResult(
            query.series,
            source_metadata(lambda: retrieved),
            MacroDataAvailability.AVAILABLE,
            tuple(records),
        )
        return CommoditiesFXResult(query, data)

    def _unavailable(self, query: CommoditiesFXQuery, reason: str) -> CommoditiesFXResult:
        data = MacroDataResult[CommoditiesFXRecord](
            query.series,
            source_metadata(self._clock),
            MacroDataAvailability.UNAVAILABLE,
            reason=reason,
        )
        return CommoditiesFXResult(query, data)


def _interval_end(start: datetime, interval: str) -> datetime:
    if interval.endswith("m") and not interval.endswith("mo"):
        return start + timedelta(minutes=int(interval[:-1]))
    if interval.endswith("h"):
        return start + timedelta(hours=int(interval[:-1]))
    if interval.endswith("wk"):
        return start + timedelta(weeks=int(interval[:-2]))
    if interval.endswith("mo"):
        return start + timedelta(days=30 * int(interval[:-2]))
    return start + timedelta(days=int(interval[:-1]))


def yahoo_macro_capabilities(ticker_factory: TickerFactory, clock: Clock) -> MacroCapabilities:
    return MacroCapabilities(
        "YahooProvider", (YahooCommoditiesFXCapability(ticker_factory, clock),)
    )


__all__ = ["YahooCommoditiesFXCapability", "yahoo_macro_capabilities"]
