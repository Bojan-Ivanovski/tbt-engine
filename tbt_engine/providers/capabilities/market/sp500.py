import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier

SP500_CAPABILITY = CapabilityId("market.sp500")

_TimePoint = date | datetime


def _is_runtime_instance(value: object, expected_type: type[object]) -> bool:
    return isinstance(value, expected_type)


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _is_date_only(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _same_time_granularity(left: _TimePoint, right: _TimePoint) -> bool:
    return (_is_date_only(left) and _is_date_only(right)) or (
        isinstance(left, datetime) and isinstance(right, datetime)
    )


class SP500RecordType(str, Enum):
    OBSERVATION = "observation"
    MEMBERSHIP = "membership"


class SP500IntervalUnit(str, Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class SP500IntervalAlignment(str, Enum):
    """Boundary used by a provider to aggregate an observation interval."""

    TRADING_SESSION = "trading_session"
    CALENDAR = "calendar"


@dataclass(frozen=True, order=True, slots=True)
class SP500Interval:
    """Provider-neutral interval with explicit session or calendar alignment."""

    count: int
    unit: SP500IntervalUnit
    alignment: SP500IntervalAlignment

    def __post_init__(self) -> None:
        if (
            not _is_runtime_instance(self.count, int)
            or _is_runtime_instance(self.count, bool)
            or self.count <= 0
        ):
            raise InvalidCapabilityQueryError("S&P 500 interval count must be a positive integer")
        if not _is_runtime_instance(self.unit, SP500IntervalUnit):
            raise InvalidCapabilityQueryError("S&P 500 interval unit is invalid")
        if not _is_runtime_instance(self.alignment, SP500IntervalAlignment):
            raise InvalidCapabilityQueryError("S&P 500 interval alignment is invalid")


class SP500ObservationType(str, Enum):
    LEVEL = "level"
    RETURN = "return"


class SP500ValueUnit(str, Enum):
    INDEX_POINTS = "index_points"
    DECIMAL = "decimal"
    PERCENT = "percent"


class SP500Calculation(str, Enum):
    CLOSING_LEVEL = "closing_level"
    SIMPLE_PRICE_RETURN = "simple_price_return"
    LOG_PRICE_RETURN = "log_price_return"
    SIMPLE_TOTAL_RETURN = "simple_total_return"
    LOG_TOTAL_RETURN = "log_total_return"


class SP500MembershipScope(str, Enum):
    """Validity represented by a constituent-membership record."""

    HISTORICAL = "historical"
    CURRENT_ONLY = "current_only"


@dataclass(frozen=True, slots=True)
class SP500Query:
    """S&P 500 request using inclusive-start and exclusive-end filtering.

    Observation bounds filter ``MarketDataMetadata.effective_at``, the
    provider-aligned interval-end timestamp. Membership bounds filter the
    membership effective start. Membership requests explicitly choose whether
    the source must establish historical intervals or only a current snapshot.
    """

    market: MarketIdentifier
    record_type: SP500RecordType
    start: _TimePoint | None = None
    end: _TimePoint | None = None
    interval: SP500Interval | None = None
    membership_scope: SP500MembershipScope | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.market, MarketIdentifier):
            raise InvalidCapabilityQueryError("S&P 500 query market identity is invalid")
        if not _is_runtime_instance(self.record_type, SP500RecordType):
            raise InvalidCapabilityQueryError("S&P 500 query record type is invalid")

        for name, value in (("start", self.start), ("end", self.end)):
            if value is not None and not (_is_date_only(value) or _is_aware_datetime(value)):
                raise InvalidCapabilityQueryError(
                    f"S&P 500 query {name} must be a date or timezone-aware datetime"
                )
        if self.start is not None and self.end is not None:
            if not _same_time_granularity(self.start, self.end):
                raise InvalidCapabilityQueryError(
                    "S&P 500 query bounds must use the same time granularity"
                )
            if self.start >= self.end:
                raise InvalidCapabilityQueryError("S&P 500 query start must be before end")

        if self.record_type is SP500RecordType.OBSERVATION:
            if not _is_runtime_instance(self.interval, SP500Interval):
                raise InvalidCapabilityQueryError("S&P 500 observation query requires an interval")
            if self.membership_scope is not None:
                raise InvalidCapabilityQueryError(
                    "S&P 500 observation query must not specify membership scope"
                )
            if _is_date_only(self.start) or _is_date_only(self.end):
                raise InvalidCapabilityQueryError(
                    "S&P 500 observation bounds must be timezone-aware datetimes"
                )
        else:
            if self.interval is not None:
                raise InvalidCapabilityQueryError(
                    "S&P 500 membership query must not specify an observation interval"
                )
            if not _is_runtime_instance(self.membership_scope, SP500MembershipScope):
                raise InvalidCapabilityQueryError(
                    "S&P 500 membership query requires a membership scope"
                )


@dataclass(frozen=True, slots=True)
class SP500Observation:
    """One index level or return at a provider-aligned interval end."""

    metadata: MarketDataMetadata
    interval: SP500Interval
    observation_type: SP500ObservationType
    value: float
    unit: SP500ValueUnit
    calculation: SP500Calculation

    def __post_init__(self) -> None:
        if not isinstance(self.metadata.effective_at, datetime):
            raise ValueError("S&P 500 observation timestamp must be a timezone-aware datetime")
        if not _is_runtime_instance(self.interval, SP500Interval):
            raise ValueError("S&P 500 observation interval is invalid")
        if not _is_runtime_instance(self.observation_type, SP500ObservationType):
            raise ValueError("S&P 500 observation type is invalid")
        if not _is_runtime_instance(self.unit, SP500ValueUnit):
            raise ValueError("S&P 500 observation unit is invalid")
        if not _is_runtime_instance(self.calculation, SP500Calculation):
            raise ValueError("S&P 500 observation calculation is invalid")

        value = float(self.value)
        if not math.isfinite(value):
            raise ValueError("S&P 500 observation value must be finite")

        if self.observation_type is SP500ObservationType.LEVEL:
            if value < 0:
                raise ValueError("S&P 500 index level must be non-negative")
            if self.unit is not SP500ValueUnit.INDEX_POINTS:
                raise ValueError("S&P 500 index level must use index-point units")
            if self.calculation is not SP500Calculation.CLOSING_LEVEL:
                raise ValueError("S&P 500 index level must use closing-level calculation")
        else:
            if self.unit is SP500ValueUnit.INDEX_POINTS:
                raise ValueError("S&P 500 return must use decimal or percent units")
            if self.calculation is SP500Calculation.CLOSING_LEVEL:
                raise ValueError("S&P 500 return must use an explicit return calculation")

        object.__setattr__(self, "value", value)

    @property
    def timestamp(self) -> datetime:
        effective_at = self.metadata.effective_at
        if not isinstance(effective_at, datetime):
            raise RuntimeError("S&P 500 observation has invalid timestamp metadata")
        return effective_at


@dataclass(frozen=True, slots=True)
class SP500ConstituentMembership:
    """Constituent membership with an explicit historical or snapshot scope.

    For ``HISTORICAL``, ``metadata.effective_at`` is the inclusive effective
    start and ``effective_end`` is exclusive or ``None`` for an open interval.
    For ``CURRENT_ONLY``, ``metadata.effective_at`` is the source snapshot time;
    it does not assert membership before that snapshot.
    """

    metadata: MarketDataMetadata
    constituent: MarketIdentifier
    scope: SP500MembershipScope
    effective_end: _TimePoint | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.constituent, MarketIdentifier):
            raise ValueError("S&P 500 constituent identity is invalid")
        if not _is_runtime_instance(self.scope, SP500MembershipScope):
            raise ValueError("S&P 500 membership scope is invalid")

        effective_start = self.metadata.effective_at
        if self.effective_end is not None:
            if not (_is_date_only(self.effective_end) or _is_aware_datetime(self.effective_end)):
                raise ValueError("S&P 500 membership end must be a date or timezone-aware datetime")
            if not _same_time_granularity(effective_start, self.effective_end):
                raise ValueError("S&P 500 membership interval must use one time granularity")
            if effective_start >= self.effective_end:
                raise ValueError("S&P 500 membership effective end must follow its start")
        if self.scope is SP500MembershipScope.CURRENT_ONLY and self.effective_end is not None:
            raise ValueError("Current-only S&P 500 membership cannot define a historical end")

    @property
    def effective_start(self) -> _TimePoint:
        return self.metadata.effective_at


SP500Record = SP500Observation | SP500ConstituentMembership


def _record_time(record: SP500Record) -> _TimePoint:
    return record.metadata.effective_at


@dataclass(frozen=True, slots=True)
class SP500Result:
    """Validated, deterministically ordered S&P 500 response."""

    query: SP500Query
    data: MarketDataResult[SP500Record]

    def __post_init__(self) -> None:
        if self.data.market != self.query.market:
            raise ValueError("S&P 500 result market identity must match its query")

        previous_time: _TimePoint | None = None
        previous_key: tuple[str, ...] | None = None
        uses_datetime: bool | None = None

        for record in self.data.records:
            if record.metadata.market != self.query.market:
                raise ValueError("S&P 500 record market identity must match its query")

            if self.query.record_type is SP500RecordType.OBSERVATION:
                if not isinstance(record, SP500Observation):
                    raise ValueError("S&P 500 observation result contains membership data")
                if record.interval != self.query.interval:
                    raise ValueError("S&P 500 observation interval must match its query")
                record_key = (record.observation_type.value, record.calculation.value)
            else:
                if not isinstance(record, SP500ConstituentMembership):
                    raise ValueError("S&P 500 membership result contains observation data")
                if record.scope is not self.query.membership_scope:
                    raise ValueError("S&P 500 membership scope must match its query")
                record_key = (
                    record.constituent.scheme,
                    record.constituent.value,
                    record.constituent.market or "",
                )

            record_time = _record_time(record)
            record_uses_datetime = isinstance(record_time, datetime)
            if uses_datetime is None:
                uses_datetime = record_uses_datetime
            elif uses_datetime is not record_uses_datetime:
                raise ValueError("S&P 500 records must use one time granularity")

            if self.query.start is not None:
                if not _same_time_granularity(record_time, self.query.start):
                    raise ValueError("S&P 500 record time granularity must match its query")
                if record_time < self.query.start:
                    raise ValueError("S&P 500 record precedes the query start")
            if self.query.end is not None:
                if not _same_time_granularity(record_time, self.query.end):
                    raise ValueError("S&P 500 record time granularity must match its query")
                if record_time >= self.query.end:
                    raise ValueError("S&P 500 record is not before the exclusive query end")

            if previous_time is not None:
                if record_time < previous_time or (
                    record_time == previous_time
                    and previous_key is not None
                    and record_key <= previous_key
                ):
                    raise ValueError("S&P 500 records must be unique and deterministically ordered")
            previous_time = record_time
            previous_key = record_key

    @property
    def records(self) -> tuple[SP500Record, ...]:
        return self.data.records

    @property
    def observations(self) -> tuple[SP500Observation, ...]:
        return tuple(record for record in self.data.records if isinstance(record, SP500Observation))

    @property
    def memberships(self) -> tuple[SP500ConstituentMembership, ...]:
        return tuple(
            record for record in self.data.records if isinstance(record, SP500ConstituentMembership)
        )

    @property
    def availability(self) -> MarketDataAvailability:
        return self.data.availability


class SP500Capability(Capability):
    """Provider-independent contract for normalized S&P 500 context."""

    @property
    def id(self) -> CapabilityId:
        return SP500_CAPABILITY

    @abstractmethod
    def get_sp500(self, query: SP500Query) -> SP500Result:
        raise NotImplementedError


__all__ = [
    "SP500Calculation",
    "SP500Capability",
    "SP500ConstituentMembership",
    "SP500Interval",
    "SP500IntervalAlignment",
    "SP500IntervalUnit",
    "SP500MembershipScope",
    "SP500Observation",
    "SP500ObservationType",
    "SP500Query",
    "SP500Record",
    "SP500RecordType",
    "SP500Result",
    "SP500ValueUnit",
    "SP500_CAPABILITY",
]
