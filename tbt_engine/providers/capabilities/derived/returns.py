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

RETURNS_CAPABILITY = CapabilityId("derived.returns")


class ReturnMethod(str, Enum):
    SIMPLE = "simple"
    LOG = "log"
    CUMULATIVE = "cumulative"


@dataclass(frozen=True, slots=True)
class ReturnsQuery:
    input: InputSeriesRef
    horizon: int
    start: datetime
    end: datetime
    method: ReturnMethod = ReturnMethod.SIMPLE
    distribution_treatment: str = "as_input"

    def __post_init__(self) -> None:
        if (
            self.horizon <= 0
            or self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start >= self.end
            or type(self.method) is not ReturnMethod
        ):
            raise InvalidCapabilityQueryError("Returns query parameters are invalid")
        if not self.distribution_treatment.strip():
            raise InvalidCapabilityQueryError("Returns distribution treatment is required")


@dataclass(frozen=True, slots=True)
class ReturnsRecord:
    metadata: DerivedRecordMetadata
    value: float


@dataclass(frozen=True, slots=True)
class ReturnsResult:
    query: ReturnsQuery
    data: DerivedDataResult[ReturnsRecord]

    @property
    def records(self) -> tuple[ReturnsRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> DerivedDataAvailability:
        return self.data.availability


class ReturnsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return RETURNS_CAPABILITY

    @abstractmethod
    def get_returns(self, query: ReturnsQuery) -> ReturnsResult:
        raise NotImplementedError


__all__ = [
    "RETURNS_CAPABILITY",
    "ReturnMethod",
    "ReturnsCapability",
    "ReturnsQuery",
    "ReturnsRecord",
    "ReturnsResult",
]
