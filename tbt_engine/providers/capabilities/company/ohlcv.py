import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier

OHLCV_CAPABILITY = CapabilityId("company.ohlcv")


def _is_runtime_instance(value: object, expected_type: type[object]) -> bool:
    return isinstance(value, expected_type)


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


class BarIntervalUnit(str, Enum):
    SECOND = "s"
    MINUTE = "m"
    HOUR = "h"
    DAY = "d"
    WEEK = "wk"
    MONTH = "mo"


@dataclass(frozen=True, order=True, slots=True)
class BarInterval:
    """Provider-independent bar size without a prescribed session anchor.

    Providers align intervals to the trading sessions or calendars of their
    source. The interval describes aggregation size, not a universal elapsed
    duration or exchange-calendar rule.
    """

    count: int
    unit: BarIntervalUnit

    def __post_init__(self) -> None:
        if (
            not _is_runtime_instance(self.count, int)
            or _is_runtime_instance(self.count, bool)
            or self.count <= 0
        ):
            raise InvalidCapabilityQueryError("Bar interval count must be a positive integer")
        if not _is_runtime_instance(self.unit, BarIntervalUnit):
            raise InvalidCapabilityQueryError("Bar interval unit must be a supported unit")

    def __str__(self) -> str:
        return f"{self.count}{self.unit.value}"


class OHLCVAdjustment(str, Enum):
    UNADJUSTED = "unadjusted"
    SPLIT_ADJUSTED = "split_adjusted"
    SPLIT_AND_DIVIDEND_ADJUSTED = "split_and_dividend_adjusted"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OHLCVQuery:
    """Normalized OHLCV request with an inclusive start and exclusive end.

    Bounds filter the bar-start timestamp stored in
    ``CompanyDataMetadata.effective_at``. Providers retain their source's
    session or calendar alignment; this contract does not shift bars to a
    universal boundary.
    """

    company: CompanyIdentifier
    interval: BarInterval
    adjustment: OHLCVAdjustment | None = None
    start: datetime | None = None
    end: datetime | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.company, CompanyIdentifier):
            raise InvalidCapabilityQueryError("OHLCV query company is invalid")
        if not _is_runtime_instance(self.interval, BarInterval):
            raise InvalidCapabilityQueryError("OHLCV query interval is invalid")
        if self.adjustment is not None and not _is_runtime_instance(
            self.adjustment, OHLCVAdjustment
        ):
            raise InvalidCapabilityQueryError("OHLCV query adjustment is invalid")
        for name, value in (("start", self.start), ("end", self.end)):
            if value is not None and not _is_aware_datetime(value):
                raise InvalidCapabilityQueryError(
                    f"OHLCV query {name} must be a timezone-aware datetime"
                )
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("OHLCV query start must be before end")
        if self.adjustment is OHLCVAdjustment.UNKNOWN:
            raise InvalidCapabilityQueryError(
                "OHLCV query cannot request an unknown adjustment state"
            )


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """One normalized bar timestamped at its provider-aligned interval start."""

    metadata: CompanyDataMetadata
    interval: BarInterval
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjustment: OHLCVAdjustment

    def __post_init__(self) -> None:
        if not isinstance(self.metadata.effective_at, datetime):
            raise ValueError("OHLCV bar timestamp must be a timezone-aware datetime")

        values = {
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
        }
        for name, value in values.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"OHLCV {name} must be finite and non-negative")

        if values["high"] < max(values["open"], values["low"], values["close"]):
            raise ValueError("OHLCV high must not be below another price")
        if values["low"] > min(values["open"], values["high"], values["close"]):
            raise ValueError("OHLCV low must not be above another price")
        if (
            self.metadata.available_at is not None
            and self.metadata.available_at < self.metadata.effective_at
        ):
            raise ValueError("OHLCV availability time must not precede its timestamp")

        for name, value in values.items():
            object.__setattr__(self, name, value)

    @property
    def timestamp(self) -> datetime:
        effective_at = self.metadata.effective_at
        if not isinstance(effective_at, datetime):
            raise RuntimeError("OHLCV bar has invalid timestamp metadata")
        return effective_at


@dataclass(frozen=True, slots=True)
class OHLCVResult:
    """Validated, deterministically ordered OHLCV response."""

    query: OHLCVQuery
    data: CompanyDataResult[OHLCVBar]

    def __post_init__(self) -> None:
        if self.data.company != self.query.company:
            raise ValueError("OHLCV result company must match its query")

        previous_timestamp: datetime | None = None
        for bar in self.data.records:
            if bar.metadata.company != self.query.company:
                raise ValueError("OHLCV bar company must match its query")
            if bar.interval != self.query.interval:
                raise ValueError("OHLCV bar interval must match its query")
            if self.query.adjustment is not None and bar.adjustment is not self.query.adjustment:
                raise ValueError("OHLCV bar adjustment must match its query")
            if self.query.start is not None and bar.timestamp < self.query.start:
                raise ValueError("OHLCV bar precedes the query start")
            if self.query.end is not None and bar.timestamp >= self.query.end:
                raise ValueError("OHLCV bar is not before the exclusive query end")
            if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
                raise ValueError("OHLCV bars must have unique, ascending timestamps")
            previous_timestamp = bar.timestamp

    @property
    def bars(self) -> tuple[OHLCVBar, ...]:
        return self.data.records

    @property
    def availability(self) -> CompanyDataAvailability:
        return self.data.availability


class OHLCVCapability(Capability):
    """Provider-independent contract for normalized historical price bars."""

    @property
    def id(self) -> CapabilityId:
        return OHLCV_CAPABILITY

    @abstractmethod
    def get_ohlcv(self, query: OHLCVQuery) -> OHLCVResult:
        raise NotImplementedError


__all__ = [
    "BarInterval",
    "BarIntervalUnit",
    "OHLCVAdjustment",
    "OHLCVBar",
    "OHLCVCapability",
    "OHLCVQuery",
    "OHLCVResult",
    "OHLCV_CAPABILITY",
]
