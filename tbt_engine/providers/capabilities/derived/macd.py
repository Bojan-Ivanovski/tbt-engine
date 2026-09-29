from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef
from tbt_engine.providers.capabilities.derived.results import (
    DerivedDataAvailability,
    DerivedDataResult,
    DerivedRecordMetadata,
)

MACD_CAPABILITY = CapabilityId("derived.macd")


@dataclass(frozen=True, slots=True)
class MACDQuery:
    input: InputSeriesRef
    fast_period: int
    slow_period: int
    signal_period: int
    start: datetime
    end: datetime
    convention: str = "ema"

    def __post_init__(self) -> None:
        if (
            min(self.fast_period, self.slow_period, self.signal_period) <= 0
            or self.fast_period >= self.slow_period
            or self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start >= self.end
        ):
            raise InvalidCapabilityQueryError("MACD query parameters are invalid")


@dataclass(frozen=True, slots=True)
class MACDRecord:
    metadata: DerivedRecordMetadata
    macd: float
    signal: float | None
    histogram: float | None


@dataclass(frozen=True, slots=True)
class MACDResult:
    query: MACDQuery
    data: DerivedDataResult[MACDRecord]

    @property
    def records(self) -> tuple[MACDRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> DerivedDataAvailability:
        return self.data.availability


class MACDCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return MACD_CAPABILITY

    @abstractmethod
    def get_macd(self, query: MACDQuery) -> MACDResult:
        raise NotImplementedError


__all__ = ["MACD_CAPABILITY", "MACDCapability", "MACDQuery", "MACDRecord", "MACDResult"]
