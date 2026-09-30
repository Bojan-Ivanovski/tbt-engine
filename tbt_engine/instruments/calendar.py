import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tbt_engine.instruments.identity import ExchangeIdentifier

_CALENDAR_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


def _require_date(value: date, label: str) -> date:
    if isinstance(value, datetime):
        raise TypeError(f"{label} must be a calendar date")
    return value


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


@dataclass(frozen=True, order=True, slots=True)
class TradingCalendarIdentifier:
    value: str

    def __post_init__(self) -> None:
        value = self.value.strip().lower()
        if not _CALENDAR_ID_PATTERN.fullmatch(value):
            raise ValueError("Trading calendar identifier is invalid")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class TradingSessionIdentifier:
    """Stable identity of one labeled session in a trading calendar."""

    calendar: TradingCalendarIdentifier
    trading_date: date

    def __post_init__(self) -> None:
        _require_date(self.trading_date, "Session trading date")


@dataclass(frozen=True, order=True, slots=True)
class SessionBoundary:
    """Local wall-clock boundary relative to the labeled trading date."""

    local_time: time
    day_offset: int = 0

    def __post_init__(self) -> None:
        if self.local_time.tzinfo is not None:
            raise ValueError("Session boundary time must not contain timezone information")
        if isinstance(self.day_offset, bool) or self.day_offset < -1 or self.day_offset > 2:
            raise ValueError("Session boundary day offset must be between -1 and 2")


@dataclass(frozen=True, slots=True)
class SessionTemplate:
    opens: SessionBoundary
    closes: SessionBoundary

    def __post_init__(self) -> None:
        anchor = date(2000, 1, 3)
        if self._at(anchor, self.opens) >= self._at(anchor, self.closes):
            raise ValueError("Session close must follow session open")

    @staticmethod
    def _at(trading_date: date, boundary: SessionBoundary) -> datetime:
        return datetime.combine(
            trading_date + timedelta(days=boundary.day_offset),
            boundary.local_time,
        )

    def local_bounds(self, trading_date: date) -> tuple[datetime, datetime]:
        trading_date = _require_date(trading_date, "Trading date")
        return (self._at(trading_date, self.opens), self._at(trading_date, self.closes))


@dataclass(frozen=True, slots=True)
class WeekdaySchedule:
    weekday: int
    regular: SessionTemplate
    extended: SessionTemplate | None = None

    def __post_init__(self) -> None:
        if isinstance(self.weekday, bool) or not 0 <= self.weekday <= 6:
            raise ValueError("Schedule weekday must be between Monday (0) and Sunday (6)")
        if self.extended is not None:
            _validate_extended_session(self.regular, self.extended)


def _validate_extended_session(regular: SessionTemplate, extended: SessionTemplate) -> None:
    anchor = date(2000, 1, 3)
    regular_open, regular_close = regular.local_bounds(anchor)
    extended_open, extended_close = extended.local_bounds(anchor)
    if extended_open > regular_open or extended_close < regular_close:
        raise ValueError("Extended session must contain the regular session")


@dataclass(frozen=True, order=True, slots=True)
class CalendarClosure:
    trading_date: date
    reason: str

    def __post_init__(self) -> None:
        _require_date(self.trading_date, "Calendar closure date")
        reason = self.reason.strip()
        if not reason:
            raise ValueError("Calendar closure reason must not be empty")
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True, slots=True)
class SessionOverride:
    """Replacement schedule for a shortened or otherwise exceptional session."""

    trading_date: date
    regular: SessionTemplate
    reason: str
    extended: SessionTemplate | None = None

    def __post_init__(self) -> None:
        _require_date(self.trading_date, "Session override date")
        reason = self.reason.strip()
        if not reason:
            raise ValueError("Session override reason must not be empty")
        if self.extended is not None:
            _validate_extended_session(self.regular, self.extended)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True, slots=True)
class TradingSession:
    calendar: TradingCalendarIdentifier
    exchange: ExchangeIdentifier
    trading_date: date
    regular_open: datetime
    regular_close: datetime
    extended_open: datetime | None = None
    extended_close: datetime | None = None
    override_reason: str | None = None

    def __post_init__(self) -> None:
        _require_date(self.trading_date, "Session trading date")
        for label, value in (
            ("Regular open", self.regular_open),
            ("Regular close", self.regular_close),
        ):
            _require_aware(value, label)
        if self.regular_open >= self.regular_close:
            raise ValueError("Regular session close must follow its open")
        if (self.extended_open is None) != (self.extended_close is None):
            raise ValueError("Extended session requires both open and close")
        if self.extended_open is not None and self.extended_close is not None:
            _require_aware(self.extended_open, "Extended open")
            _require_aware(self.extended_close, "Extended close")
            if self.extended_open > self.regular_open or self.extended_close < self.regular_close:
                raise ValueError("Extended session must contain the regular session")

    @property
    def id(self) -> TradingSessionIdentifier:
        return TradingSessionIdentifier(self.calendar, self.trading_date)

    def contains(self, timestamp: datetime, include_extended: bool = False) -> bool:
        _require_aware(timestamp, "Timestamp")
        opens = (
            self.extended_open
            if include_extended and self.extended_open is not None
            else self.regular_open
        )
        closes = (
            self.extended_close
            if include_extended and self.extended_close is not None
            else self.regular_close
        )
        return opens <= timestamp < closes


class TradingCalendar:
    """Immutable exchange schedule with explicit closures and overrides."""

    def __init__(
        self,
        identifier: TradingCalendarIdentifier,
        exchange: ExchangeIdentifier,
        timezone: str,
        schedules: Iterable[WeekdaySchedule],
        closures: Iterable[CalendarClosure] = (),
        overrides: Iterable[SessionOverride] = (),
    ) -> None:
        timezone_name = timezone.strip()
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unknown calendar timezone {timezone_name!r}") from error

        schedule_items = tuple(sorted(schedules, key=lambda item: item.weekday))
        schedule_days = tuple(item.weekday for item in schedule_items)
        if not schedule_items:
            raise ValueError("Trading calendar requires at least one weekday schedule")
        if len(schedule_days) != len(set(schedule_days)):
            raise ValueError("Trading calendar weekdays must be unique")

        closure_items = tuple(sorted(closures, key=lambda item: item.trading_date))
        closure_dates = tuple(item.trading_date for item in closure_items)
        if len(closure_dates) != len(set(closure_dates)):
            raise ValueError("Trading calendar closures must use unique dates")

        override_items = tuple(sorted(overrides, key=lambda item: item.trading_date))
        override_dates = tuple(item.trading_date for item in override_items)
        if len(override_dates) != len(set(override_dates)):
            raise ValueError("Trading calendar overrides must use unique dates")
        if set(closure_dates).intersection(override_dates):
            raise ValueError("A date cannot be both closed and overridden")

        self._identifier = identifier
        self._exchange = exchange
        self._timezone_name = timezone_name
        self._zone = zone
        self._schedules = schedule_items
        self._closures = closure_items
        self._overrides = override_items

    @property
    def identifier(self) -> TradingCalendarIdentifier:
        return self._identifier

    @property
    def exchange(self) -> ExchangeIdentifier:
        return self._exchange

    @property
    def timezone(self) -> str:
        return self._timezone_name

    @property
    def schedules(self) -> tuple[WeekdaySchedule, ...]:
        return self._schedules

    @property
    def closures(self) -> tuple[CalendarClosure, ...]:
        return self._closures

    @property
    def overrides(self) -> tuple[SessionOverride, ...]:
        return self._overrides

    def _aware_bounds(
        self, trading_date: date, template: SessionTemplate
    ) -> tuple[datetime, datetime]:
        local_open, local_close = template.local_bounds(trading_date)
        return (
            local_open.replace(tzinfo=self._zone),
            local_close.replace(tzinfo=self._zone),
        )

    def session_on(self, trading_date: date) -> TradingSession | None:
        trading_date = _require_date(trading_date, "Trading date")
        if any(item.trading_date == trading_date for item in self._closures):
            return None

        override = next(
            (item for item in self._overrides if item.trading_date == trading_date),
            None,
        )
        if override is not None:
            regular = override.regular
            extended = override.extended
            reason = override.reason
        else:
            schedule = next(
                (item for item in self._schedules if item.weekday == trading_date.weekday()),
                None,
            )
            if schedule is None:
                return None
            regular = schedule.regular
            extended = schedule.extended
            reason = None

        regular_open, regular_close = self._aware_bounds(trading_date, regular)
        extended_bounds = (
            self._aware_bounds(trading_date, extended) if extended is not None else (None, None)
        )
        return TradingSession(
            calendar=self._identifier,
            exchange=self._exchange,
            trading_date=trading_date,
            regular_open=regular_open,
            regular_close=regular_close,
            extended_open=extended_bounds[0],
            extended_close=extended_bounds[1],
            override_reason=reason,
        )

    def session_containing(
        self, timestamp: datetime, include_extended: bool = False
    ) -> TradingSession | None:
        _require_aware(timestamp, "Timestamp")
        local_date = timestamp.astimezone(self._zone).date()
        for offset in (-2, -1, 0, 1, 2):
            session = self.session_on(local_date + timedelta(days=offset))
            if session is not None and session.contains(timestamp, include_extended):
                return session
        return None

    def next_session(self, after: date, maximum_days: int = 3660) -> TradingSession:
        after = _require_date(after, "Session search date")
        if isinstance(maximum_days, bool) or maximum_days <= 0:
            raise ValueError("Session search limit must be positive")
        for offset in range(1, maximum_days + 1):
            session = self.session_on(after + timedelta(days=offset))
            if session is not None:
                return session
        raise LookupError("No future trading session found within the search limit")

    def previous_session(self, before: date, maximum_days: int = 3660) -> TradingSession:
        before = _require_date(before, "Session search date")
        if isinstance(maximum_days, bool) or maximum_days <= 0:
            raise ValueError("Session search limit must be positive")
        for offset in range(1, maximum_days + 1):
            session = self.session_on(before - timedelta(days=offset))
            if session is not None:
                return session
        raise LookupError("No previous trading session found within the search limit")


__all__ = [
    "CalendarClosure",
    "SessionBoundary",
    "SessionOverride",
    "SessionTemplate",
    "TradingCalendar",
    "TradingCalendarIdentifier",
    "TradingSession",
    "TradingSessionIdentifier",
    "WeekdaySchedule",
]
