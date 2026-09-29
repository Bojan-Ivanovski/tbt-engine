import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier

SECTOR_ETF_CAPABILITY = CapabilityId("market.sector_etf")


class SectorETFRecordType(str, Enum):
    OBSERVATION = "observation"
    MAPPING = "mapping"


class SectorETFObservationKind(str, Enum):
    LEVEL = "level"
    RETURN = "return"


@dataclass(frozen=True, slots=True)
class SectorETFQuery:
    market: MarketIdentifier
    record_type: SectorETFRecordType = SectorETFRecordType.OBSERVATION
    start: datetime | None = None
    end: datetime | None = None
    classification_scheme: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self.market) is not MarketIdentifier
            or type(self.record_type) is not SectorETFRecordType
        ):
            raise InvalidCapabilityQueryError("Sector ETF query identity is invalid")
        for value in (self.start, self.end):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise InvalidCapabilityQueryError("Sector ETF bounds must be timezone-aware")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Sector ETF start must precede end")
        if self.classification_scheme is not None and not self.classification_scheme.strip():
            raise InvalidCapabilityQueryError("Sector classification scheme must not be empty")


@dataclass(frozen=True, slots=True)
class SectorETFObservation:
    metadata: MarketDataMetadata
    kind: SectorETFObservationKind
    value: float
    interval: str
    adjustment: str = "unadjusted"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.metadata.effective_at, datetime)
            or self.metadata.effective_at.tzinfo is None
        ):
            raise ValueError("Sector ETF observation requires aware timestamp")
        if (
            not math.isfinite(float(self.value))
            or not self.interval.strip()
            or not self.adjustment.strip()
        ):
            raise ValueError("Sector ETF observation fields are invalid")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "interval", self.interval.strip())
        object.__setattr__(self, "adjustment", self.adjustment.strip())


@dataclass(frozen=True, slots=True)
class SectorETFMapping:
    metadata: MarketDataMetadata
    company: MarketIdentifier
    sector: str
    classification_scheme: str
    effective_end: date | datetime | None = None

    def __post_init__(self) -> None:
        if (
            type(self.company) is not MarketIdentifier
            or not self.sector.strip()
            or not self.classification_scheme.strip()
        ):
            raise ValueError("Sector mapping identity is invalid")
        if self.effective_end is not None and self.metadata.effective_at >= self.effective_end:
            raise ValueError("Sector mapping end must follow start")


SectorETFRecord = SectorETFObservation | SectorETFMapping


@dataclass(frozen=True, slots=True)
class SectorETFResult:
    query: SectorETFQuery
    data: MarketDataResult[SectorETFRecord]

    def __post_init__(self) -> None:
        if self.data.market != self.query.market:
            raise ValueError("Sector ETF market must match query")
        previous: datetime | date | None = None
        for record in self.data.records:
            if record.metadata.market != self.query.market:
                raise ValueError("Sector ETF record market must match query")
            if self.query.record_type is SectorETFRecordType.OBSERVATION and not isinstance(
                record, SectorETFObservation
            ):
                raise ValueError("Sector ETF record type mismatch")
            if self.query.record_type is SectorETFRecordType.MAPPING and not isinstance(
                record, SectorETFMapping
            ):
                raise ValueError("Sector ETF record type mismatch")
            stamp = record.metadata.effective_at
            if self.query.start is not None and stamp < self.query.start:
                raise ValueError("Sector ETF record precedes query start")
            if self.query.end is not None and stamp >= self.query.end:
                raise ValueError("Sector ETF record is not before exclusive query end")
            if previous is not None and stamp <= previous:
                raise ValueError("Sector ETF records must be ascending and unique")
            previous = stamp

    @property
    def records(self) -> tuple[SectorETFRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MarketDataAvailability:
        return self.data.availability


class SectorETFCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return SECTOR_ETF_CAPABILITY

    @abstractmethod
    def get_sector_etf(self, query: SectorETFQuery) -> SectorETFResult:
        raise NotImplementedError


__all__ = [
    "SECTOR_ETF_CAPABILITY",
    "SectorETFCapability",
    "SectorETFMapping",
    "SectorETFObservation",
    "SectorETFObservationKind",
    "SectorETFQuery",
    "SectorETFRecord",
    "SectorETFRecordType",
    "SectorETFResult",
]
