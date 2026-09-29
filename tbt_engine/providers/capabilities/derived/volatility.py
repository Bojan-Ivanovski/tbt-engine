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

VOLATILITY_CAPABILITY = CapabilityId("derived.volatility")


class VolatilityReturnMethod(str, Enum):
    SIMPLE = "simple"
    LOG = "log"


@dataclass(frozen=True, slots=True)
class VolatilityQuery:
    input: InputSeriesRef
    lookback: int
    start: datetime
    end: datetime
    return_method: VolatilityReturnMethod = VolatilityReturnMethod.LOG
    sampling_interval: str = "1d"
    annualization: float | None = None

    def __post_init__(self) -> None:
        if (
            self.lookback <= 0
            or self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start >= self.end
            or type(self.return_method) is not VolatilityReturnMethod
        ):
            raise InvalidCapabilityQueryError("Volatility query parameters are invalid")
        if self.annualization is not None and self.annualization <= 0:
            raise InvalidCapabilityQueryError("Volatility annualization must be positive")


@dataclass(frozen=True, slots=True)
class VolatilityRecord:
    metadata: DerivedRecordMetadata
    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Volatility must be non-negative")


@dataclass(frozen=True, slots=True)
class VolatilityResult:
    query: VolatilityQuery
    data: DerivedDataResult[VolatilityRecord]

    @property
    def records(self) -> tuple[VolatilityRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> DerivedDataAvailability:
        return self.data.availability


class VolatilityCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return VOLATILITY_CAPABILITY

    @abstractmethod
    def get_volatility(self, query: VolatilityQuery) -> VolatilityResult:
        raise NotImplementedError


__all__ = [
    "VOLATILITY_CAPABILITY",
    "VolatilityCapability",
    "VolatilityQuery",
    "VolatilityRecord",
    "VolatilityResult",
    "VolatilityReturnMethod",
]
