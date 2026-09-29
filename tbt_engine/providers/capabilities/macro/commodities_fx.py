import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.macro.macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
)
from tbt_engine.providers.capabilities.macro.macro_identifier import MacroSeriesIdentifier

COMMODITIES_FX_CAPABILITY = CapabilityId("macro.commodities_fx")


class InstrumentKind(str, Enum):
    COMMODITY = "commodity"
    FX = "fx"


@dataclass(frozen=True, slots=True)
class CommoditiesFXQuery:
    series: MacroSeriesIdentifier
    start: datetime | None = None
    end: datetime | None = None
    interval: str = "1d"

    def __post_init__(self) -> None:
        if not self.interval.strip():
            raise InvalidCapabilityQueryError("Commodity/FX interval is required")
        for value in (self.start, self.end):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise InvalidCapabilityQueryError("Commodity/FX bounds must be timezone-aware")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Commodity/FX start must precede end")
        object.__setattr__(self, "interval", self.interval.strip())


@dataclass(frozen=True, slots=True)
class CommoditiesFXRecord:
    metadata: MacroDataMetadata
    instrument_kind: InstrumentKind
    value: float
    quote_unit: str
    quote_currency: str | None = None
    base_currency: str | None = None
    adjustment: str = "unadjusted"

    def __post_init__(self) -> None:
        if (
            type(self.instrument_kind) is not InstrumentKind
            or not math.isfinite(float(self.value))
            or not self.quote_unit.strip()
        ):
            raise ValueError("Commodity/FX record fields are invalid")
        if self.instrument_kind is InstrumentKind.FX and (
            not self.base_currency or not self.quote_currency
        ):
            raise ValueError("FX records require base and quote currencies")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "quote_unit", self.quote_unit.strip())


@dataclass(frozen=True, slots=True)
class CommoditiesFXResult:
    query: CommoditiesFXQuery
    data: MacroDataResult[CommoditiesFXRecord]

    def __post_init__(self) -> None:
        if self.data.series != self.query.series:
            raise ValueError("Commodity/FX series must match query")
        previous: datetime | None = None
        for record in self.data.records:
            stamp = record.metadata.available_at
            if self.query.start is not None and stamp < self.query.start:
                raise ValueError("Commodity/FX record precedes query start")
            if self.query.end is not None and stamp >= self.query.end:
                raise ValueError("Commodity/FX record is not before exclusive query end")
            if previous is not None and stamp <= previous:
                raise ValueError("Commodity/FX records must be ascending and unique")
            previous = stamp

    @property
    def records(self) -> tuple[CommoditiesFXRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> MacroDataAvailability:
        return self.data.availability


class CommoditiesFXCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return COMMODITIES_FX_CAPABILITY

    @abstractmethod
    def get_commodities_fx(self, query: CommoditiesFXQuery) -> CommoditiesFXResult:
        raise NotImplementedError


__all__ = [
    "COMMODITIES_FX_CAPABILITY",
    "CommoditiesFXCapability",
    "CommoditiesFXQuery",
    "CommoditiesFXRecord",
    "CommoditiesFXResult",
    "InstrumentKind",
]
