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

BREADTH_CAPABILITY = CapabilityId("market.breadth")


@dataclass(frozen=True, slots=True)
class BreadthQuery:
    market: MarketIdentifier
    start: datetime | None = None
    end: datetime | None = None
    interval: str = "1d"
    methodology: str = ""

    def __post_init__(self) -> None:
        if type(self.market) is not MarketIdentifier or not self.interval.strip():
            raise InvalidCapabilityQueryError("Breadth identity and interval are required")
        for value in (self.start, self.end):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise InvalidCapabilityQueryError("Breadth bounds must be timezone-aware")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Breadth start must precede end")
        if not self.methodology.strip():
            raise InvalidCapabilityQueryError("Breadth methodology is required")
        object.__setattr__(self, "interval", self.interval.strip())
        object.__setattr__(self, "methodology", self.methodology.strip())


@dataclass(frozen=True, slots=True)
class BreadthRecord:
    metadata: MarketDataMetadata
    interval: str
    methodology: str
    advancing_issues: int | None = None
    declining_issues: int | None = None
    new_highs: int | None = None
    new_lows: int | None = None
    advancing_volume: float | None = None
    declining_volume: float | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.metadata.effective_at, datetime)
            or self.metadata.effective_at.tzinfo is None
        ):
            raise ValueError("Breadth timestamp must be aware")
        if not self.interval.strip() or not self.methodology.strip():
            raise ValueError("Breadth interval and methodology are required")
        for value in (self.advancing_issues, self.declining_issues, self.new_highs, self.new_lows):
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError("Breadth counts must be non-negative")
        for value in (self.advancing_volume, self.declining_volume):
            if value is not None and (not math.isfinite(float(value)) or value < 0):
                raise ValueError("Breadth volumes must be non-negative and finite")


@dataclass(frozen=True, slots=True)
class BreadthResult:
    query: BreadthQuery
    data: MarketDataResult[BreadthRecord]

    def __post_init__(self) -> None:
        if self.data.market != self.query.market:
            raise ValueError("Breadth market must match query")
        previous: datetime | None = None
        for record in self.data.records:
            if (
                record.interval != self.query.interval
                or record.methodology != self.query.methodology
            ):
                raise ValueError("Breadth dimensions must match query")
            stamp = record.metadata.effective_at
            if not isinstance(stamp, datetime):
                raise ValueError("Breadth timestamp must be datetime")
            if self.query.start is not None and stamp < self.query.start:
                raise ValueError("Breadth record precedes query start")
            if self.query.end is not None and stamp >= self.query.end:
                raise ValueError("Breadth record is not before exclusive query end")
            if previous is not None and stamp <= previous:
                raise ValueError("Breadth records must be ascending and unique")
            previous = stamp

    @property
    def records(self) -> tuple[BreadthRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MarketDataAvailability:
        return self.data.availability


class BreadthCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return BREADTH_CAPABILITY

    @abstractmethod
    def get_breadth(self, query: BreadthQuery) -> BreadthResult:
        raise NotImplementedError


__all__ = [
    "BREADTH_CAPABILITY",
    "BreadthCapability",
    "BreadthQuery",
    "BreadthRecord",
    "BreadthResult",
]
