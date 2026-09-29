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
)
from tbt_engine.providers.capabilities.macro.macro_identifier import (
    GeographyIdentifier,
    MacroSeriesIdentifier,
)

GDP_CAPABILITY = CapabilityId("macro.gdp")


class GDPPriceBasis(str, Enum):
    NOMINAL = "nominal"
    REAL = "real"


class GDPMeasure(str, Enum):
    TOTAL = "total"
    PER_CAPITA = "per_capita"


@dataclass(frozen=True, slots=True)
class GDPQuery:
    series: MacroSeriesIdentifier
    observation_start: date
    observation_end: date
    geography: GeographyIdentifier | None = None
    price_basis: GDPPriceBasis | None = None
    measure: GDPMeasure | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if self.observation_end <= self.observation_start:
            raise InvalidCapabilityQueryError("GDP bounds are invalid")
        if self.as_of is not None and (self.as_of.tzinfo is None or self.as_of.utcoffset() is None):
            raise InvalidCapabilityQueryError("GDP as-of must be timezone-aware")


@dataclass(frozen=True, slots=True)
class GDPRecord:
    metadata: MacroDataMetadata
    value: Decimal
    price_basis: GDPPriceBasis
    measure: GDPMeasure
    annualized: bool

    def __post_init__(self) -> None:
        if (
            not self.value.is_finite()
            or type(self.price_basis) is not GDPPriceBasis
            or type(self.measure) is not GDPMeasure
        ):
            raise ValueError("GDP record fields are invalid")


@dataclass(frozen=True, slots=True)
class GDPResult:
    query: GDPQuery
    data: MacroDataResult[GDPRecord]

    def __post_init__(self) -> None:
        if self.data.series != self.query.series:
            raise ValueError("GDP series must match query")
        previous = None
        for record in self.data.records:
            period = record.metadata.observation_period
            if (
                period.start < self.query.observation_start
                or period.start >= self.query.observation_end
            ):
                raise ValueError("GDP record is outside query bounds")
            if (
                self.query.geography is not None
                and record.metadata.geography != self.query.geography
            ):
                raise ValueError("GDP geography mismatch")
            if (
                self.query.price_basis is not None
                and record.price_basis is not self.query.price_basis
            ):
                raise ValueError("GDP price basis mismatch")
            if self.query.measure is not None and record.measure is not self.query.measure:
                raise ValueError("GDP measure mismatch")
            if previous is not None and period <= previous:
                raise ValueError("GDP records must be ordered and unique")
            previous = period

    @property
    def records(self) -> tuple[GDPRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MacroDataAvailability:
        return self.data.availability


class GDPCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return GDP_CAPABILITY

    @abstractmethod
    def get_gdp(self, query: GDPQuery) -> GDPResult:
        raise NotImplementedError


__all__ = [
    "GDP_CAPABILITY",
    "GDPCapability",
    "GDPMeasure",
    "GDPPriceBasis",
    "GDPQuery",
    "GDPRecord",
    "GDPResult",
]
