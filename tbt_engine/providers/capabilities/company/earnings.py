import re
from abc import abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TypeVar

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier

EARNINGS_CAPABILITY = CapabilityId("company.earnings")

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def _is_runtime_instance(value: object, expected_type: type[object]) -> bool:
    return isinstance(value, expected_type)


def _is_date_only(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _normalize_fact_fields(
    value: Decimal | None,
    unit: str,
    currency: str | None,
) -> tuple[str, str | None]:
    if value is not None and not _is_runtime_instance(value, Decimal):
        raise ValueError("Earnings fact value must be Decimal or None")
    if value is not None and not value.is_finite():
        raise ValueError("Earnings fact value must be finite")
    if not _is_runtime_instance(unit, str):
        raise ValueError("Earnings fact unit must be text")
    if currency is not None and not _is_runtime_instance(currency, str):
        raise ValueError("Earnings fact currency must be text or None")

    normalized_unit = unit.strip()
    normalized_currency = currency.strip().upper() if currency is not None else None
    if not normalized_unit:
        raise ValueError("Earnings fact unit must not be empty")
    if normalized_currency is not None and not _CURRENCY_PATTERN.fullmatch(normalized_currency):
        raise ValueError("Earnings fact currency must use a three-letter code")
    return normalized_unit, normalized_currency


class EarningsTimingStatus(str, Enum):
    ESTIMATED = "estimated"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, order=True, slots=True)
class EarningsMetricId:
    """Stable provider-neutral identity for one earnings metric."""

    value: str

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.value, str):
            raise ValueError("Earnings metric identifier must be text")
        value = self.value.strip().lower()
        if not _IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("Earnings metric identifier is invalid")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class EarningsReportingPeriod:
    """Calendar reporting period with inclusive start and end dates."""

    start: date
    end: date
    label: str | None = None

    def __post_init__(self) -> None:
        if not _is_date_only(self.start) or not _is_date_only(self.end):
            raise ValueError("Earnings reporting period bounds must be calendar dates")
        if self.start > self.end:
            raise ValueError("Earnings reporting period start must not follow its end")
        if self.label is not None and not _is_runtime_instance(self.label, str):
            raise ValueError("Earnings reporting period label must be text or None")
        label = self.label.strip() if self.label is not None else None
        if label == "":
            raise ValueError("Earnings reporting period label must not be empty")
        object.__setattr__(self, "label", label)


@dataclass(frozen=True, slots=True)
class EarningsEstimate:
    """Provider estimate kept distinct from a reported actual value."""

    metric: EarningsMetricId
    value: Decimal | None
    unit: str
    currency: str | None = None
    analyst_count: int | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.metric, EarningsMetricId):
            raise ValueError("Earnings estimate metric identity is invalid")
        unit, currency = _normalize_fact_fields(self.value, self.unit, self.currency)
        if self.analyst_count is not None and (
            not _is_runtime_instance(self.analyst_count, int)
            or isinstance(self.analyst_count, bool)
            or self.analyst_count < 0
        ):
            raise ValueError("Earnings estimate analyst count must be non-negative")
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True, slots=True)
class EarningsActual:
    """Reported earnings value kept distinct from provider estimates."""

    metric: EarningsMetricId
    value: Decimal | None
    unit: str
    currency: str | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.metric, EarningsMetricId):
            raise ValueError("Earnings actual metric identity is invalid")
        unit, currency = _normalize_fact_fields(self.value, self.unit, self.currency)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True, slots=True)
class EarningsSurprise:
    """Provider-reported surprise value and/or percentage."""

    metric: EarningsMetricId
    value: Decimal | None = None
    percent: Decimal | None = None
    unit: str = "absolute"
    currency: str | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.metric, EarningsMetricId):
            raise ValueError("Earnings surprise metric identity is invalid")
        if self.value is None and self.percent is None:
            raise ValueError("Earnings surprise requires a value or percentage")
        unit, currency = _normalize_fact_fields(self.value, self.unit, self.currency)
        if self.percent is not None and not _is_runtime_instance(self.percent, Decimal):
            raise ValueError("Earnings surprise percentage must be Decimal or None")
        if self.percent is not None and not self.percent.is_finite():
            raise ValueError("Earnings surprise percentage must be finite")
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True, slots=True)
class EarningsQuery:
    """Earnings request filtered by announcement time.

    ``start`` is inclusive and ``end`` is exclusive. The bounds apply to the
    timezone-aware announcement timestamp, whether its timing is estimated or
    confirmed; reporting periods remain calendar-date intervals.
    """

    company: CompanyIdentifier
    timing_statuses: frozenset[EarningsTimingStatus] = frozenset(EarningsTimingStatus)
    start: datetime | None = None
    end: datetime | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.company, CompanyIdentifier):
            raise InvalidCapabilityQueryError("Earnings query company is invalid")
        try:
            timing_statuses = frozenset(self.timing_statuses)
        except TypeError as error:
            raise InvalidCapabilityQueryError(
                "Earnings query timing statuses must be a collection"
            ) from error
        if not timing_statuses or any(
            not _is_runtime_instance(value, EarningsTimingStatus) for value in timing_statuses
        ):
            raise InvalidCapabilityQueryError("Earnings query timing statuses are invalid")
        for name, value in (("start", self.start), ("end", self.end)):
            if value is not None and not _is_aware_datetime(value):
                raise InvalidCapabilityQueryError(
                    f"Earnings query {name} must be a timezone-aware datetime"
                )
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Earnings query start must be before end")
        object.__setattr__(self, "timing_statuses", timing_statuses)


T = TypeVar("T", EarningsEstimate, EarningsActual, EarningsSurprise)


def _normalize_facts(
    facts: tuple[T, ...],
    expected_type: type[T],
    label: str,
) -> tuple[T, ...]:
    normalized = tuple(facts)
    previous_metric: str | None = None
    for fact in normalized:
        if not _is_runtime_instance(fact, expected_type):
            raise ValueError(f"Earnings {label} contains an invalid fact type")
        metric = fact.metric.value
        if previous_metric is not None and metric <= previous_metric:
            raise ValueError(f"Earnings {label} must have unique ascending metric identities")
        previous_metric = metric
    return normalized


@dataclass(frozen=True, slots=True)
class EarningsEvent:
    """One versioned earnings event with distinct estimate and reported facts."""

    metadata: CompanyDataMetadata
    reporting_period: EarningsReportingPeriod
    announcement_at: datetime
    timing_status: EarningsTimingStatus
    published_at: datetime | None = None
    estimates: tuple[EarningsEstimate, ...] = ()
    actuals: tuple[EarningsActual, ...] = ()
    surprises: tuple[EarningsSurprise, ...] = ()

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.reporting_period, EarningsReportingPeriod):
            raise ValueError("Earnings event reporting period is invalid")
        if not _is_aware_datetime(self.announcement_at):
            raise ValueError("Earnings announcement time must be timezone-aware")
        if not _is_runtime_instance(self.timing_status, EarningsTimingStatus):
            raise ValueError("Earnings timing status is invalid")
        if not _is_aware_datetime(self.metadata.effective_at):
            raise ValueError("Earnings effective time must be a timezone-aware datetime")
        if self.metadata.effective_at != self.announcement_at:
            raise ValueError("Earnings effective time must equal its announcement time")
        if self.published_at is not None and not _is_aware_datetime(self.published_at):
            raise ValueError("Earnings publication time must be timezone-aware")
        if (
            self.published_at is not None
            and self.metadata.available_at is not None
            and self.metadata.available_at < self.published_at
        ):
            raise ValueError("Earnings availability time must not precede publication")

        estimates = _normalize_facts(self.estimates, EarningsEstimate, "estimates")
        actuals = _normalize_facts(self.actuals, EarningsActual, "actuals")
        surprises = _normalize_facts(self.surprises, EarningsSurprise, "surprises")
        if self.timing_status is EarningsTimingStatus.ESTIMATED and (actuals or surprises):
            raise ValueError("Estimated-timing earnings events cannot contain reported facts")
        if actuals or surprises:
            if self.published_at is not None and self.published_at < self.announcement_at:
                raise ValueError("Reported earnings publication must not precede announcement")
            if (
                self.metadata.available_at is not None
                and self.metadata.available_at < self.announcement_at
            ):
                raise ValueError("Reported earnings availability must not precede announcement")

        object.__setattr__(self, "estimates", estimates)
        object.__setattr__(self, "actuals", actuals)
        object.__setattr__(self, "surprises", surprises)


def _event_sort_key(event: EarningsEvent) -> tuple[str, ...]:
    published_at = (
        event.published_at.astimezone(timezone.utc).isoformat()
        if event.published_at is not None
        else ""
    )
    return (
        event.announcement_at.astimezone(timezone.utc).isoformat(),
        event.reporting_period.end.isoformat(),
        event.reporting_period.start.isoformat(),
        event.timing_status.value,
        published_at,
    )


@dataclass(frozen=True, slots=True)
class EarningsResult:
    """Validated earnings events in deterministic announcement-time order."""

    query: EarningsQuery
    data: CompanyDataResult[EarningsEvent]

    def __post_init__(self) -> None:
        if self.data.company != self.query.company:
            raise ValueError("Earnings result company must match its query")

        previous_key: tuple[str, ...] | None = None
        identities: set[tuple[str, ...]] = set()
        for event in self.data.records:
            if not _is_runtime_instance(event, EarningsEvent):
                raise ValueError("Earnings result contains an invalid event type")
            if event.metadata.company != self.query.company:
                raise ValueError("Earnings event company must match its query")
            if event.timing_status not in self.query.timing_statuses:
                raise ValueError("Earnings event timing status was not requested")
            if self.query.start is not None and event.announcement_at < self.query.start:
                raise ValueError("Earnings event precedes the query start")
            if self.query.end is not None and event.announcement_at >= self.query.end:
                raise ValueError("Earnings event is not before the exclusive query end")

            identity = _event_sort_key(event)
            if identity in identities:
                raise ValueError("Earnings events must be unique")
            identities.add(identity)
            if previous_key is not None and identity <= previous_key:
                raise ValueError("Earnings events must use deterministic ascending order")
            previous_key = identity

    @property
    def events(self) -> tuple[EarningsEvent, ...]:
        return self.data.records

    @property
    def availability(self) -> CompanyDataAvailability:
        return self.data.availability


class EarningsCapability(Capability):
    """Provider-independent contract for normalized company earnings."""

    @property
    def id(self) -> CapabilityId:
        return EARNINGS_CAPABILITY

    @abstractmethod
    def get_earnings(self, query: EarningsQuery) -> EarningsResult:
        raise NotImplementedError


__all__ = [
    "EARNINGS_CAPABILITY",
    "EarningsActual",
    "EarningsCapability",
    "EarningsEstimate",
    "EarningsEvent",
    "EarningsMetricId",
    "EarningsQuery",
    "EarningsReportingPeriod",
    "EarningsResult",
    "EarningsSurprise",
    "EarningsTimingStatus",
]
