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
    WarmUpRequirement,
)

RSI_CAPABILITY = CapabilityId("derived.rsi")


@dataclass(frozen=True, slots=True)
class RSIQuery:
    input: InputSeriesRef
    lookback: int
    start: datetime
    end: datetime
    convention: str = "wilder"
    warm_up: WarmUpRequirement | None = None

    def __post_init__(self) -> None:
        if (
            self.lookback <= 0
            or self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start >= self.end
        ):
            raise InvalidCapabilityQueryError("RSI query parameters are invalid")
        if not self.convention.strip():
            raise InvalidCapabilityQueryError("RSI convention is required")


@dataclass(frozen=True, slots=True)
class RSIRecord:
    metadata: DerivedRecordMetadata
    value: float

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 100:
            raise ValueError("RSI value must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class RSIResult:
    query: RSIQuery
    data: DerivedDataResult[RSIRecord]

    @property
    def records(self) -> tuple[RSIRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> DerivedDataAvailability:
        return self.data.availability


class RSICapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return RSI_CAPABILITY

    @abstractmethod
    def get_rsi(self, query: RSIQuery) -> RSIResult:
        raise NotImplementedError


__all__ = ["RSI_CAPABILITY", "RSICapability", "RSIQuery", "RSIRecord", "RSIResult"]
