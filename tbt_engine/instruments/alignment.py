from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tbt_engine.instruments.calendar import (
    TradingCalendar,
    TradingCalendarIdentifier,
    TradingSession,
)


class SessionPhase(str, Enum):
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"


class SessionAnchor(str, Enum):
    EXTENDED_OPEN = "extended_open"
    REGULAR_OPEN = "regular_open"
    REGULAR_CLOSE = "regular_close"
    EXTENDED_CLOSE = "extended_close"


@dataclass(frozen=True, slots=True)
class TimestampAlignment:
    """One absolute timestamp classified against an exchange calendar."""

    timestamp_utc: datetime
    timestamp_local: datetime
    calendar: TradingCalendarIdentifier
    phase: SessionPhase
    session: TradingSession | None

    def __post_init__(self) -> None:
        if self.timestamp_utc.tzinfo is None or self.timestamp_utc.utcoffset() is None:
            raise ValueError("Aligned UTC timestamp must be timezone-aware")
        if self.timestamp_utc.utcoffset() != timezone.utc.utcoffset(self.timestamp_utc):
            raise ValueError("Aligned UTC timestamp must use UTC")
        if self.timestamp_local.tzinfo is None or self.timestamp_local.utcoffset() is None:
            raise ValueError("Aligned local timestamp must be timezone-aware")
        if (self.phase is SessionPhase.CLOSED) != (self.session is None):
            raise ValueError("Closed timestamps must not identify a containing session")
        if self.session is not None and self.session.calendar != self.calendar:
            raise ValueError("Aligned session must belong to the selected calendar")


def normalize_timestamp(timestamp: datetime, source_timezone: str | None = None) -> datetime:
    """Return one absolute UTC instant.

    A naive provider timestamp is accepted only when its source timezone is
    supplied explicitly. The datetime ``fold`` value is preserved for ambiguous
    daylight-saving transitions.
    """

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        if source_timezone is None:
            raise ValueError("Naive timestamp requires an explicit source timezone")
        try:
            zone = ZoneInfo(source_timezone.strip())
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unknown source timezone {source_timezone!r}") from error
        local_timestamp = timestamp.replace(tzinfo=zone)
        round_trip = local_timestamp.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if round_trip != timestamp:
            raise ValueError("Naive timestamp does not exist in its source timezone")
        timestamp = local_timestamp
    elif source_timezone is not None:
        raise ValueError("Source timezone must not be supplied for an aware timestamp")
    return timestamp.astimezone(timezone.utc)


def align_timestamp(timestamp: datetime, calendar: TradingCalendar) -> TimestampAlignment:
    timestamp_utc = normalize_timestamp(timestamp)
    zone = ZoneInfo(calendar.timezone)
    timestamp_local = timestamp_utc.astimezone(zone)
    session = calendar.session_containing(timestamp_utc, include_extended=True)
    if session is None:
        phase = SessionPhase.CLOSED
    elif session.contains(timestamp_utc):
        phase = SessionPhase.REGULAR
    elif timestamp_utc < session.regular_open:
        phase = SessionPhase.PRE_MARKET
    else:
        phase = SessionPhase.POST_MARKET
    return TimestampAlignment(
        timestamp_utc=timestamp_utc,
        timestamp_local=timestamp_local,
        calendar=calendar.identifier,
        phase=phase,
        session=session,
    )


def next_regular_session(timestamp: datetime, calendar: TradingCalendar) -> TradingSession:
    """Return the first session whose regular open is not before ``timestamp``."""

    timestamp_utc = normalize_timestamp(timestamp)
    local_date = timestamp_utc.astimezone(ZoneInfo(calendar.timezone)).date()
    candidate = calendar.session_on(local_date)
    if candidate is not None and candidate.regular_open >= timestamp_utc:
        return candidate
    return calendar.next_session(local_date)


def previous_regular_session(timestamp: datetime, calendar: TradingCalendar) -> TradingSession:
    """Return the last session whose regular close is not after ``timestamp``."""

    timestamp_utc = normalize_timestamp(timestamp)
    local_date = timestamp_utc.astimezone(ZoneInfo(calendar.timezone)).date()
    candidate = calendar.session_on(local_date)
    if candidate is not None and candidate.regular_close <= timestamp_utc:
        return candidate
    return calendar.previous_session(local_date)


def session_timestamp(session: TradingSession, anchor: SessionAnchor) -> datetime:
    if anchor is SessionAnchor.REGULAR_OPEN:
        return session.regular_open.astimezone(timezone.utc)
    if anchor is SessionAnchor.REGULAR_CLOSE:
        return session.regular_close.astimezone(timezone.utc)
    if anchor is SessionAnchor.EXTENDED_OPEN:
        if session.extended_open is None:
            raise ValueError("Session does not define an extended open")
        return session.extended_open.astimezone(timezone.utc)
    if session.extended_close is None:
        raise ValueError("Session does not define an extended close")
    return session.extended_close.astimezone(timezone.utc)


__all__ = [
    "SessionAnchor",
    "SessionPhase",
    "TimestampAlignment",
    "align_timestamp",
    "next_regular_session",
    "normalize_timestamp",
    "previous_regular_session",
    "session_timestamp",
]
