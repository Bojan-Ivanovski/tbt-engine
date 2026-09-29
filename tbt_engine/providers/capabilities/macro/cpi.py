from abc import abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.macro.macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
    SeasonalAdjustmentStatus,
)
from tbt_engine.providers.capabilities.macro.macro_identifier import (
    GeographyIdentifier,
    MacroSeriesIdentifier,
)

CPI_CAPABILITY = CapabilityId("macro.cpi")


class CPIValueKind(str, Enum):
    INDEX = "index"
    PERIOD_CHANGE = "period_change"
    YEAR_CHANGE = "year_change"


@dataclass(frozen=True, slots=True)
class CPIQuery:
    series: MacroSeriesIdentifier
    observation_start: date
    observation_end: date
    geography: GeographyIdentifier | None = None
    as_of: datetime | None = None
    value_kind: CPIValueKind | None = None
    seasonal_adjustment: SeasonalAdjustmentStatus | None = None

    def __post_init__(self) -> None:
        if self.observation_end <= self.observation_start:
            raise InvalidCapabilityQueryError("CPI bounds are invalid")
        if self.as_of is not None and (self.as_of.tzinfo is None or self.as_of.utcoffset() is None):
            raise InvalidCapabilityQueryError("CPI as-of must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CPIRecord:
    metadata: MacroDataMetadata
    value: Decimal
    kind: CPIValueKind

    def __post_init__(self) -> None:
        if not self.value.is_finite() or type(self.kind) is not CPIValueKind:
            raise ValueError("CPI record value or kind is invalid")


@dataclass(frozen=True, slots=True)
class CPIResult:
    query: CPIQuery
    data: MacroDataResult[CPIRecord]

    def __post_init__(self) -> None:
        if self.data.series != self.query.series:
            raise ValueError("CPI series must match query")
        previous: object = None
        for record in self.data.records:
            period = record.metadata.observation_period
            if (
                period.start < self.query.observation_start
                or period.start >= self.query.observation_end
            ):
                raise ValueError("CPI record is outside query bounds")
            if (
                self.query.geography is not None
                and record.metadata.geography != self.query.geography
            ):
                raise ValueError("CPI geography mismatch")
            if self.query.value_kind is not None and record.kind is not self.query.value_kind:
                raise ValueError("CPI value kind mismatch")
            if previous is not None and period <= previous:
                raise ValueError("CPI records must be ordered and unique")
            previous = period

    @property
    def records(self) -> tuple[CPIRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MacroDataAvailability:
        return self.data.availability


class CPICapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return CPI_CAPABILITY

    @abstractmethod
    def get_cpi(self, query: CPIQuery) -> CPIResult:
        raise NotImplementedError


__all__ = ["CPI_CAPABILITY", "CPICapability", "CPIQuery", "CPIRecord", "CPIResult", "CPIValueKind"]
