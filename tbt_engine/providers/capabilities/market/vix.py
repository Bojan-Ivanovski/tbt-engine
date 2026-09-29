import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier

VIX_CAPABILITY = CapabilityId("market.vix")


@dataclass(frozen=True, slots=True)
class VIXQuery:
    market: MarketIdentifier
    start: datetime | None = None
    end: datetime | None = None
    interval: str = "1d"

    def __post_init__(self) -> None:
        if type(self.market) is not MarketIdentifier or not self.interval.strip():
            raise InvalidCapabilityQueryError("VIX query identity or interval is invalid")
        for value in (self.start, self.end):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise InvalidCapabilityQueryError("VIX bounds must be timezone-aware")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("VIX start must precede end")
        object.__setattr__(self, "interval", self.interval.strip())


@dataclass(frozen=True, slots=True)
class VIXRecord:
    metadata: MarketDataMetadata
    level: float
    interval: str
    settlement: str = "close"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.metadata.effective_at, datetime)
            or self.metadata.effective_at.tzinfo is None
        ):
            raise ValueError("VIX timestamp must be aware")
        if not math.isfinite(float(self.level)) or self.level < 0:
            raise ValueError("VIX level must be finite and non-negative")
        if not self.interval.strip() or not self.settlement.strip():
            raise ValueError("VIX interval and settlement are required")
        object.__setattr__(self, "level", float(self.level))
        object.__setattr__(self, "interval", self.interval.strip())
        object.__setattr__(self, "settlement", self.settlement.strip())


@dataclass(frozen=True, slots=True)
class VIXResult:
    query: VIXQuery
    data: MarketDataResult[VIXRecord]

    def __post_init__(self) -> None:
        if self.data.market != self.query.market:
            raise ValueError("VIX market must match query")
        previous: datetime | None = None
        for record in self.data.records:
            if record.interval != self.query.interval:
                raise ValueError("VIX interval must match query")
            stamp = record.metadata.effective_at
            if not isinstance(stamp, datetime):
                raise ValueError("VIX timestamp must be datetime")
            if self.query.start is not None and stamp < self.query.start:
                raise ValueError("VIX record precedes query start")
            if self.query.end is not None and stamp >= self.query.end:
                raise ValueError("VIX record is not before exclusive query end")
            if previous is not None and stamp <= previous:
                raise ValueError("VIX records must be ascending and unique")
            previous = stamp

    @property
    def records(self) -> tuple[VIXRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MarketDataAvailability:
        return self.data.availability


class VIXCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return VIX_CAPABILITY

    @abstractmethod
    def get_vix(self, query: VIXQuery) -> VIXResult:
        raise NotImplementedError


__all__ = ["VIX_CAPABILITY", "VIXCapability", "VIXQuery", "VIXRecord", "VIXResult"]
