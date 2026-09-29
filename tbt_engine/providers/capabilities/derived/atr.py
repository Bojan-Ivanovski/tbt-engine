from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef
from tbt_engine.providers.capabilities.derived.results import (
    DerivedDataAvailability,
    DerivedDataResult,
    DerivedRecordMetadata,
)

ATR_CAPABILITY = CapabilityId("derived.atr")


class ATRSmoothing(str, Enum):
    WILDER = "wilder"
    SMA = "sma"
    EMA = "ema"


@dataclass(frozen=True, slots=True)
class ATRQuery:
    high: InputSeriesRef
    low: InputSeriesRef
    close: InputSeriesRef
    period: int
    start: datetime
    end: datetime
    smoothing: ATRSmoothing = ATRSmoothing.WILDER

    def __post_init__(self) -> None:
        if (
            self.period <= 0
            or self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start >= self.end
            or type(self.smoothing) is not ATRSmoothing
        ):
            raise InvalidCapabilityQueryError("ATR query parameters are invalid")


@dataclass(frozen=True, slots=True)
class ATRRecord:
    metadata: DerivedRecordMetadata
    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("ATR value must be non-negative")


@dataclass(frozen=True, slots=True)
class ATRResult:
    query: ATRQuery
    data: DerivedDataResult[ATRRecord]

    @property
    def records(self) -> tuple[ATRRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> DerivedDataAvailability:
        return self.data.availability


class ATRCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return ATR_CAPABILITY

    @abstractmethod
    def get_atr(self, query: ATRQuery) -> ATRResult:
        raise NotImplementedError


__all__ = ["ATR_CAPABILITY", "ATRCapability", "ATRQuery", "ATRRecord", "ATRResult", "ATRSmoothing"]
