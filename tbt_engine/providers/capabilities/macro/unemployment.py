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

UNEMPLOYMENT_CAPABILITY = CapabilityId("macro.unemployment")


class UnemploymentMeasure(str, Enum):
    RATE = "rate"
    COUNT = "count"
    LABOR_FORCE = "labor_force"


@dataclass(frozen=True, slots=True)
class UnemploymentQuery:
    series: MacroSeriesIdentifier
    observation_start: date
    observation_end: date
    geography: GeographyIdentifier | None = None
    measure: UnemploymentMeasure | None = None
    seasonal_adjustment: SeasonalAdjustmentStatus | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if self.observation_end <= self.observation_start:
            raise InvalidCapabilityQueryError("Unemployment bounds are invalid")
        if self.as_of is not None and (self.as_of.tzinfo is None or self.as_of.utcoffset() is None):
            raise InvalidCapabilityQueryError("Unemployment as-of must be timezone-aware")


@dataclass(frozen=True, slots=True)
class UnemploymentRecord:
    metadata: MacroDataMetadata
    value: Decimal
    measure: UnemploymentMeasure
    methodology: str

    def __post_init__(self) -> None:
        if (
            not self.value.is_finite()
            or type(self.measure) is not UnemploymentMeasure
            or not self.methodology.strip()
        ):
            raise ValueError("Unemployment record fields are invalid")


@dataclass(frozen=True, slots=True)
class UnemploymentResult:
    query: UnemploymentQuery
    data: MacroDataResult[UnemploymentRecord]

    def __post_init__(self) -> None:
        if self.data.series != self.query.series:
            raise ValueError("Unemployment series must match query")
        previous = None
        for record in self.data.records:
            period = record.metadata.observation_period
            if (
                period.start < self.query.observation_start
                or period.start >= self.query.observation_end
            ):
                raise ValueError("Unemployment record is outside query bounds")
            if (
                self.query.geography is not None
                and record.metadata.geography != self.query.geography
            ):
                raise ValueError("Unemployment geography mismatch")
            if self.query.measure is not None and record.measure is not self.query.measure:
                raise ValueError("Unemployment measure mismatch")
            if previous is not None and period <= previous:
                raise ValueError("Unemployment records must be ordered and unique")
            previous = period

    @property
    def records(self) -> tuple[UnemploymentRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MacroDataAvailability:
        return self.data.availability


class UnemploymentCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return UNEMPLOYMENT_CAPABILITY

    @abstractmethod
    def get_unemployment(self, query: UnemploymentQuery) -> UnemploymentResult:
        raise NotImplementedError


__all__ = [
    "UNEMPLOYMENT_CAPABILITY",
    "UnemploymentCapability",
    "UnemploymentMeasure",
    "UnemploymentQuery",
    "UnemploymentRecord",
    "UnemploymentResult",
]
