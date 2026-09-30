from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Generic, Protocol, TypeVar

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.macro.macro_identifier import (
    GeographyIdentifier,
    MacroSeriesIdentifier,
)


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True, order=True, slots=True)
class ObservationPeriod:
    """Inclusive-start, exclusive-end period measured by a macro observation."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if isinstance(self.start, datetime) or isinstance(self.end, datetime):
            raise TypeError("Macro observation period boundaries must be dates")
        if self.end <= self.start:
            raise ValueError("Macro observation period end must be later than its start")


@dataclass(frozen=True, slots=True)
class MacroRevisionMetadata:
    """Descriptive revision and vintage identity for a macro observation."""

    vintage_at: datetime | None = None
    release_sequence: int | None = None
    status: str | None = None
    superseded_record_id: str | None = None

    def __post_init__(self) -> None:
        status = self.status.strip() if self.status is not None else None
        superseded_record_id = (
            self.superseded_record_id.strip() if self.superseded_record_id is not None else None
        )

        if self.vintage_at is not None and not _is_aware(self.vintage_at):
            raise ValueError("Macro revision vintage time must be timezone-aware")
        if isinstance(self.release_sequence, bool) or (
            self.release_sequence is not None and self.release_sequence < 0
        ):
            raise ValueError("Macro revision release sequence must be non-negative")
        if status == "":
            raise ValueError("Macro revision status must not be empty")
        if superseded_record_id == "":
            raise ValueError("Superseded source record identifier must not be empty")

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "superseded_record_id", superseded_record_id)


@dataclass(frozen=True, slots=True)
class MacroUnitMetadata:
    """Exact unit and scaling convention of a stored macro value."""

    unit: str
    multiplier: Decimal | None = None
    currency: str | None = None

    def __post_init__(self) -> None:
        unit = self.unit.strip()
        currency = self.currency.strip().upper() if self.currency is not None else None

        if not unit:
            raise ValueError("Macro unit identifier must not be empty")
        if self.multiplier is not None and (
            not self.multiplier.is_finite() or self.multiplier <= 0
        ):
            raise ValueError("Macro unit multiplier must be finite and positive")
        if currency == "":
            raise ValueError("Macro unit currency must not be empty")

        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "currency", currency)


class SeasonalAdjustmentStatus(str, Enum):
    """Seasonal-adjustment convention applied to a macro observation."""

    ADJUSTED = "adjusted"
    UNADJUSTED = "unadjusted"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MacroDataMetadata:
    """Shared identity, timing, measurement, and provenance for one release record."""

    series: MacroSeriesIdentifier
    source: SourceMetadata
    observation_period: ObservationPeriod
    available_at: datetime
    unit: MacroUnitMetadata
    seasonal_adjustment: SeasonalAdjustmentStatus
    published_at: datetime | None = None
    revision: MacroRevisionMetadata | None = None
    geography: GeographyIdentifier | None = None

    def __post_init__(self) -> None:
        if not _is_aware(self.available_at):
            raise ValueError("Macro data availability time must be timezone-aware")
        if self.published_at is not None:
            if not _is_aware(self.published_at):
                raise ValueError("Macro data publication time must be timezone-aware")
            if self.available_at < self.published_at:
                raise ValueError(
                    "Macro data availability time must not precede its publication time"
                )


class MacroDataRecord(Protocol):
    """Structural contract implemented by every release-based macro record."""

    @property
    def metadata(self) -> MacroDataMetadata:
        """Return the record's shared macro metadata."""
        ...


T = TypeVar("T", bound=MacroDataRecord)


class MacroDataAvailability(str, Enum):
    """Coverage status for a successful macro-capability request."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


def _source_matches(record_source: SourceMetadata, result_source: SourceMetadata) -> bool:
    return (
        record_source.provider == result_source.provider
        and record_source.source == result_source.source
        and record_source.retrieved_at == result_source.retrieved_at
        and (
            result_source.source_record_id is None
            or record_source.source_record_id == result_source.source_record_id
        )
    )


def _vintage_key(metadata: MacroDataMetadata) -> tuple[datetime, int, str]:
    revision = metadata.revision
    vintage_at = revision.vintage_at if revision is not None else None
    release_sequence = revision.release_sequence if revision is not None else None
    source_record_id = metadata.source.source_record_id
    return (
        vintage_at or datetime.min.replace(tzinfo=timezone.utc),
        release_sequence if release_sequence is not None else -1,
        source_record_id or "",
    )


def _record_sort_key(record: MacroDataRecord) -> tuple[date, date, datetime, int, str]:
    period = record.metadata.observation_period
    return (period.start, period.end, *_vintage_key(record.metadata))


def _duplicate_key(
    metadata: MacroDataMetadata,
) -> tuple[MacroSeriesIdentifier, ObservationPeriod, datetime | int | None]:
    revision = metadata.revision
    vintage_identity: datetime | int | None = None
    if revision is not None:
        vintage_identity = (
            revision.vintage_at if revision.vintage_at is not None else revision.release_sequence
        )
    return (
        metadata.series,
        metadata.observation_period,
        vintage_identity,
    )


@dataclass(frozen=True, slots=True)
class MacroDataResult(Generic[T]):
    """Normalized macro result with explicit coverage and immutable records."""

    series: MacroSeriesIdentifier
    source: SourceMetadata
    availability: MacroDataAvailability
    records: tuple[T, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        reason = self.reason.strip() if self.reason is not None else None
        records = tuple(sorted(self.records, key=_record_sort_key))

        if reason == "":
            raise ValueError("Macro data availability reason must not be empty")
        if self.availability is MacroDataAvailability.AVAILABLE:
            if reason is not None:
                raise ValueError("Available macro data must not include a reason")
        elif self.availability is MacroDataAvailability.PARTIAL:
            if not records or reason is None:
                raise ValueError("Partial macro data requires records and a reason")
        elif reason is None or records:
            raise ValueError("Unavailable macro data requires a reason and no records")

        seen: set[tuple[MacroSeriesIdentifier, ObservationPeriod, datetime | int | None]] = set()
        for record in records:
            metadata = record.metadata
            if metadata.series != self.series:
                raise ValueError("Macro result records must match the requested series")
            if not _source_matches(metadata.source, self.source):
                raise ValueError("Macro result records must match the result source")

            duplicate_key = _duplicate_key(metadata)
            if duplicate_key in seen:
                raise ValueError(
                    "Macro result contains duplicate observations for a series, period, and vintage"
                )
            seen.add(duplicate_key)

        object.__setattr__(self, "records", records)
        object.__setattr__(self, "reason", reason)


__all__ = [
    "MacroDataAvailability",
    "MacroDataMetadata",
    "MacroDataRecord",
    "MacroDataResult",
    "MacroRevisionMetadata",
    "MacroUnitMetadata",
    "ObservationPeriod",
    "SeasonalAdjustmentStatus",
]
