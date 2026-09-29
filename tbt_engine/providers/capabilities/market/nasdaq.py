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

NASDAQ_CAPABILITY = CapabilityId("market.nasdaq")


class NasdaqRecordType(str, Enum):
    OBSERVATION = "observation"
    MEMBERSHIP = "membership"


class NasdaqObservationKind(str, Enum):
    LEVEL = "level"
    RETURN = "return"


class NasdaqMembershipScope(str, Enum):
    HISTORICAL = "historical"
    CURRENT_ONLY = "current_only"


@dataclass(frozen=True, slots=True)
class NasdaqQuery:
    market: MarketIdentifier
    record_type: NasdaqRecordType = NasdaqRecordType.OBSERVATION
    start: datetime | date | None = None
    end: datetime | date | None = None
    membership_scope: NasdaqMembershipScope | None = None

    def __post_init__(self) -> None:
        if (
            type(self.market) is not MarketIdentifier
            or type(self.record_type) is not NasdaqRecordType
        ):
            raise InvalidCapabilityQueryError("Nasdaq query identity is invalid")
        for value in (self.start, self.end):
            if value is not None and (
                isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None)
            ):
                raise InvalidCapabilityQueryError("Nasdaq query bounds are invalid")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Nasdaq query start must precede end")
        if self.record_type is NasdaqRecordType.MEMBERSHIP and self.membership_scope is None:
            raise InvalidCapabilityQueryError("Nasdaq membership scope is required")
        if self.record_type is NasdaqRecordType.OBSERVATION and self.membership_scope is not None:
            raise InvalidCapabilityQueryError("Observation query cannot specify membership scope")


@dataclass(frozen=True, slots=True)
class NasdaqObservation:
    metadata: MarketDataMetadata
    kind: NasdaqObservationKind
    value: float
    unit: str = "index_points"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.metadata.effective_at, datetime)
            or self.metadata.effective_at.tzinfo is None
        ):
            raise ValueError("Nasdaq observation requires aware timestamp")
        if not math.isfinite(float(self.value)):
            raise ValueError("Nasdaq value must be finite")
        if not self.unit.strip():
            raise ValueError("Nasdaq unit is required")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "unit", self.unit.strip())


@dataclass(frozen=True, slots=True)
class NasdaqMembership:
    metadata: MarketDataMetadata
    constituent: MarketIdentifier
    scope: NasdaqMembershipScope
    effective_end: date | datetime | None = None

    def __post_init__(self) -> None:
        if (
            type(self.constituent) is not MarketIdentifier
            or type(self.scope) is not NasdaqMembershipScope
        ):
            raise ValueError("Nasdaq membership identity is invalid")
        if self.effective_end is not None and self.metadata.effective_at >= self.effective_end:
            raise ValueError("Nasdaq membership end must follow start")
        if self.scope is NasdaqMembershipScope.CURRENT_ONLY and self.effective_end is not None:
            raise ValueError("Current-only membership cannot have an end")


NasdaqRecord = NasdaqObservation | NasdaqMembership


@dataclass(frozen=True, slots=True)
class NasdaqResult:
    query: NasdaqQuery
    data: MarketDataResult[NasdaqRecord]

    def __post_init__(self) -> None:
        if self.data.market != self.query.market:
            raise ValueError("Nasdaq market must match query")
        previous: object = None
        for record in self.data.records:
            if record.metadata.market != self.query.market:
                raise ValueError("Nasdaq record market must match query")
            if self.query.record_type is NasdaqRecordType.OBSERVATION and not isinstance(
                record, NasdaqObservation
            ):
                raise ValueError("Nasdaq result record type mismatch")
            if self.query.record_type is NasdaqRecordType.MEMBERSHIP and not isinstance(
                record, NasdaqMembership
            ):
                raise ValueError("Nasdaq result record type mismatch")
            timestamp = record.metadata.effective_at
            if self.query.start is not None and timestamp < self.query.start:
                raise ValueError("Nasdaq record precedes query start")
            if self.query.end is not None and timestamp >= self.query.end:
                raise ValueError("Nasdaq record is not before exclusive query end")
            if previous is not None and timestamp <= previous:
                raise ValueError("Nasdaq records must be ascending and unique")
            previous = timestamp

    @property
    def records(self) -> tuple[NasdaqRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MarketDataAvailability:
        return self.data.availability


class NasdaqCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return NASDAQ_CAPABILITY

    @abstractmethod
    def get_nasdaq(self, query: NasdaqQuery) -> NasdaqResult:
        raise NotImplementedError


__all__ = [
    "NASDAQ_CAPABILITY",
    "NasdaqCapability",
    "NasdaqMembership",
    "NasdaqMembershipScope",
    "NasdaqObservation",
    "NasdaqObservationKind",
    "NasdaqQuery",
    "NasdaqRecord",
    "NasdaqRecordType",
    "NasdaqResult",
]
