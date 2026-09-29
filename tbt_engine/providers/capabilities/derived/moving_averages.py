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


class MovingAverageKind(str, Enum):
    SMA = "sma"
    EMA = "ema"


SMA_CAPABILITY = CapabilityId("derived.sma")
EMA_CAPABILITY = CapabilityId("derived.ema")


@dataclass(frozen=True, slots=True)
class MovingAverageQuery:
    input: InputSeriesRef
    window: int
    start: datetime
    end: datetime
    kind: MovingAverageKind
    initialization: str = "standard"

    def __post_init__(self) -> None:
        if (
            self.window <= 0
            or self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start >= self.end
            or type(self.kind) is not MovingAverageKind
        ):
            raise InvalidCapabilityQueryError("Moving-average query parameters are invalid")


@dataclass(frozen=True, slots=True)
class MovingAverageRecord:
    metadata: DerivedRecordMetadata
    value: float


@dataclass(frozen=True, slots=True)
class MovingAverageResult:
    query: MovingAverageQuery
    data: DerivedDataResult[MovingAverageRecord]

    @property
    def records(self) -> tuple[MovingAverageRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> DerivedDataAvailability:
        return self.data.availability


class SMACapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return SMA_CAPABILITY

    @abstractmethod
    def get_sma(self, query: MovingAverageQuery) -> MovingAverageResult:
        raise NotImplementedError


class EMACapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return EMA_CAPABILITY

    @abstractmethod
    def get_ema(self, query: MovingAverageQuery) -> MovingAverageResult:
        raise NotImplementedError


__all__ = [
    "EMA_CAPABILITY",
    "EMACapability",
    "MovingAverageKind",
    "MovingAverageQuery",
    "MovingAverageRecord",
    "MovingAverageResult",
    "SMA_CAPABILITY",
    "SMACapability",
]
