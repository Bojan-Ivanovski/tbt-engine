from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Generic, Protocol, TypeVar

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.derived.calculations import CalculationIdentity
from tbt_engine.providers.capabilities.derived.inputs import DerivedInput, normalize_inputs


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def require_finite(value: float, label: str = "Derived value") -> None:
    """Reject a non-finite numeric output unless a leaf models absence explicitly."""

    if not isfinite(value):
        raise ValueError(f"{label} must be finite")


class EarlyOutputHandling(str, Enum):
    """How a leaf represents outputs before its warm-up requirement is met."""

    OMITTED = "omitted"
    UNAVAILABLE = "unavailable"


class InsufficientWarmUpHandling(str, Enum):
    """Result state used when requested outputs lack required input coverage."""

    UNAVAILABLE = "unavailable"
    PARTIAL_WHEN_RECORDS_EXIST = "partial_when_records_exist"


@dataclass(frozen=True, slots=True)
class WarmUpRequirement:
    """Normalized warm-up behavior derived from a leaf query's parameters."""

    minimum_observations: int
    consumes_preceding: bool
    early_outputs: EarlyOutputHandling
    insufficient_coverage: InsufficientWarmUpHandling

    def __post_init__(self) -> None:
        if self.minimum_observations <= 0:
            raise ValueError("Minimum warm-up observations must be positive")


@dataclass(frozen=True, slots=True)
class WarmUpMetadata:
    """Evidence that an emitted output met its declared warm-up requirement."""

    requirement: WarmUpRequirement
    observations_used: int
    preceding_observations_used: int

    def __post_init__(self) -> None:
        if self.observations_used < self.requirement.minimum_observations:
            raise ValueError("Output used fewer observations than its warm-up requirement")
        if self.preceding_observations_used < 0:
            raise ValueError("Preceding warm-up observations must not be negative")
        if self.preceding_observations_used > self.observations_used:
            raise ValueError("Preceding observations cannot exceed all observations used")
        if not self.requirement.consumes_preceding and self.preceding_observations_used:
            raise ValueError("Warm-up metadata conflicts with preceding-input behavior")


@dataclass(frozen=True, order=True, slots=True)
class InputProvenance:
    """Latest input timestamps incorporated for one calculation role."""

    input: DerivedInput
    observation_time: datetime
    availability_time: datetime

    def __post_init__(self) -> None:
        _require_aware(self.observation_time, "Input observation time")
        _require_aware(self.availability_time, "Input availability time")


@dataclass(frozen=True, order=True, slots=True)
class DerivedOutputIdentity:
    """Stable identity used to order and de-duplicate derived records."""

    observation_time: datetime
    calculation: CalculationIdentity
    inputs: tuple[DerivedInput, ...]


@dataclass(frozen=True, slots=True, init=False)
class DerivedRecordMetadata:
    """Shared timestamps, provenance, identity, and warm-up evidence for an output."""

    source: SourceMetadata
    inputs: tuple[InputProvenance, ...]
    calculation: CalculationIdentity
    observation_time: datetime
    availability_time: datetime
    warm_up: WarmUpMetadata

    def __init__(
        self,
        source: SourceMetadata,
        inputs: Iterable[InputProvenance],
        calculation: CalculationIdentity,
        observation_time: datetime,
        availability_time: datetime,
        warm_up: WarmUpMetadata,
    ) -> None:
        normalized_inputs = tuple(sorted(inputs, key=lambda item: item.input))
        input_roles = tuple(item.input.role for item in normalized_inputs)
        if not normalized_inputs:
            raise ValueError("Derived record metadata must preserve at least one input")
        if len(input_roles) != len(set(input_roles)):
            raise ValueError("Derived record input roles must be unique")
        _require_aware(observation_time, "Output observation time")
        _require_aware(availability_time, "Output availability time")
        if any(item.observation_time > observation_time for item in normalized_inputs):
            raise ValueError("Future input cannot contribute to an earlier output")
        if (
            calculation.observation_time_rule == "latest_input"
            and max(item.observation_time for item in normalized_inputs) != observation_time
        ):
            raise ValueError("Output observation time must equal the latest input observation")
        if any(item.availability_time > availability_time for item in normalized_inputs):
            raise ValueError("Output cannot be available before all inputs are available")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "inputs", normalized_inputs)
        object.__setattr__(self, "calculation", calculation)
        object.__setattr__(self, "observation_time", observation_time)
        object.__setattr__(self, "availability_time", availability_time)
        object.__setattr__(self, "warm_up", warm_up)

    @property
    def identity(self) -> DerivedOutputIdentity:
        return DerivedOutputIdentity(
            observation_time=self.observation_time,
            calculation=self.calculation,
            inputs=tuple(item.input for item in self.inputs),
        )


@dataclass(frozen=True, slots=True, init=False)
class DerivedDataRequestContext:
    """Immutable normalized context shared by every derived leaf request."""

    inputs: tuple[DerivedInput, ...]
    calculation: CalculationIdentity
    output_start: datetime
    output_end: datetime
    warm_up: WarmUpRequirement

    def __init__(
        self,
        inputs: Iterable[DerivedInput],
        calculation: CalculationIdentity,
        output_start: datetime,
        output_end: datetime,
        warm_up: WarmUpRequirement,
    ) -> None:
        _require_aware(output_start, "Output start")
        _require_aware(output_end, "Output end")
        if output_start >= output_end:
            raise ValueError("Output start must be earlier than output end")
        object.__setattr__(self, "inputs", normalize_inputs(inputs))
        object.__setattr__(self, "calculation", calculation)
        object.__setattr__(self, "output_start", output_start)
        object.__setattr__(self, "output_end", output_end)
        object.__setattr__(self, "warm_up", warm_up)


class DerivedDataAvailability(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class DerivedRecord(Protocol):
    @property
    def metadata(self) -> DerivedRecordMetadata:
        """Return shared metadata used to validate and identify this record."""
        ...


RecordT = TypeVar("RecordT", bound=DerivedRecord)


@dataclass(frozen=True, slots=True, init=False)
class DerivedDataResult(Generic[RecordT]):
    """Validated immutable result shape shared by locally and remotely derived data."""

    request: DerivedDataRequestContext
    source: SourceMetadata
    availability: DerivedDataAvailability
    records: tuple[RecordT, ...]
    reason: str | None

    def __init__(
        self,
        request: DerivedDataRequestContext,
        source: SourceMetadata,
        availability: DerivedDataAvailability,
        records: Iterable[RecordT] = (),
        reason: str | None = None,
    ) -> None:
        normalized_records = tuple(records)
        normalized_reason = reason.strip() if reason is not None else None
        if normalized_reason == "":
            raise ValueError("Derived result reason must not be empty")
        if availability is DerivedDataAvailability.AVAILABLE and normalized_reason is not None:
            raise ValueError("Available derived results must not have a reason")
        if availability is DerivedDataAvailability.PARTIAL and (
            not normalized_records or normalized_reason is None
        ):
            raise ValueError("Partial derived results require records and a reason")
        if availability is DerivedDataAvailability.UNAVAILABLE and (
            normalized_records or normalized_reason is None
        ):
            raise ValueError("Unavailable derived results require no records and a reason")

        identities = tuple(record.metadata.identity for record in normalized_records)
        if any(left >= right for left, right in zip(identities, identities[1:])):
            raise ValueError("Derived records must be strictly ordered and unique")
        expected_inputs = request.inputs
        for record in normalized_records:
            metadata = record.metadata
            if metadata.source != source:
                raise ValueError("Derived record source metadata does not match the result")
            if tuple(item.input for item in metadata.inputs) != expected_inputs:
                raise ValueError("Derived record inputs do not match the request")
            if metadata.calculation != request.calculation:
                raise ValueError("Derived record calculation does not match the request")
            if metadata.warm_up.requirement != request.warm_up:
                raise ValueError("Derived record warm-up requirement does not match the request")
            if not request.output_start <= metadata.observation_time < request.output_end:
                raise ValueError("Derived record falls outside the requested output bounds")

        object.__setattr__(self, "request", request)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "availability", availability)
        object.__setattr__(self, "records", normalized_records)
        object.__setattr__(self, "reason", normalized_reason)


__all__ = [
    "DerivedDataAvailability",
    "DerivedDataRequestContext",
    "DerivedDataResult",
    "DerivedOutputIdentity",
    "DerivedRecord",
    "DerivedRecordMetadata",
    "EarlyOutputHandling",
    "InsufficientWarmUpHandling",
    "InputProvenance",
    "WarmUpMetadata",
    "WarmUpRequirement",
    "require_finite",
]
