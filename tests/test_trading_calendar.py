import unittest
from datetime import date, datetime, time, timezone

from tbt_engine import (
    CalendarClosure,
    ExchangeIdentifier,
    SessionAnchor,
    SessionBoundary,
    SessionOverride,
    SessionPhase,
    SessionTemplate,
    TradingCalendar,
    TradingCalendarIdentifier,
    WeekdaySchedule,
    align_timestamp,
    next_regular_session,
    normalize_timestamp,
    previous_regular_session,
    session_timestamp,
)
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.company import CompanyDataMetadata, CompanyIdentifier


def session_template(open_time: time, close_time: time) -> SessionTemplate:
    return SessionTemplate(SessionBoundary(open_time), SessionBoundary(close_time))


class TradingCalendarTests(unittest.TestCase):
    def setUp(self) -> None:
        regular = session_template(time(9, 30), time(16))
        extended = session_template(time(4), time(20))
        schedules = tuple(WeekdaySchedule(weekday, regular, extended) for weekday in range(5))
        self.calendar = TradingCalendar(
            identifier=TradingCalendarIdentifier("us.xnas"),
            exchange=ExchangeIdentifier("XNAS"),
            timezone="America/New_York",
            schedules=schedules,
            closures=(CalendarClosure(date(2025, 1, 1), "New Year's Day"),),
            overrides=(
                SessionOverride(
                    trading_date=date(2025, 1, 3),
                    regular=session_template(time(9, 30), time(13)),
                    reason="Shortened session",
                    extended=session_template(time(4), time(17)),
                ),
            ),
        )

    def test_builds_regular_session_in_exchange_timezone(self) -> None:
        session = self.calendar.session_on(date(2025, 1, 2))

        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.regular_open.hour, 9)
        self.assertEqual(session.regular_open.minute, 30)
        self.assertEqual(
            session_timestamp(session, SessionAnchor.REGULAR_OPEN),
            datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(
            session_timestamp(session, SessionAnchor.REGULAR_CLOSE),
            datetime(2025, 1, 2, 21, tzinfo=timezone.utc),
        )

        metadata = CompanyDataMetadata(
            company=CompanyIdentifier("figi", "BBG000B9XRY4", market="XNAS"),
            source=SourceMetadata("example", "memory", session.regular_close),
            effective_at=session.regular_open,
            available_at=session.regular_close,
            session=session.id,
        )
        self.assertEqual(metadata.session, session.id)

    def test_applies_closures_and_shortened_session_overrides(self) -> None:
        self.assertIsNone(self.calendar.session_on(date(2025, 1, 1)))
        shortened = self.calendar.session_on(date(2025, 1, 3))

        self.assertIsNotNone(shortened)
        assert shortened is not None
        assert shortened.extended_close is not None
        self.assertEqual(shortened.regular_close.hour, 13)
        self.assertEqual(shortened.extended_close.hour, 17)
        self.assertEqual(shortened.override_reason, "Shortened session")

    def test_classifies_regular_and_extended_hours(self) -> None:
        premarket = align_timestamp(datetime(2025, 1, 2, 13, tzinfo=timezone.utc), self.calendar)
        regular = align_timestamp(datetime(2025, 1, 2, 16, tzinfo=timezone.utc), self.calendar)
        postmarket = align_timestamp(datetime(2025, 1, 3, 0, tzinfo=timezone.utc), self.calendar)
        closed = align_timestamp(datetime(2025, 1, 4, 18, tzinfo=timezone.utc), self.calendar)

        self.assertEqual(premarket.phase, SessionPhase.PRE_MARKET)
        self.assertEqual(regular.phase, SessionPhase.REGULAR)
        self.assertEqual(postmarket.phase, SessionPhase.POST_MARKET)
        self.assertEqual(closed.phase, SessionPhase.CLOSED)
        self.assertIsNone(closed.session)

    def test_finds_previous_and_next_actionable_sessions(self) -> None:
        before_open = datetime(2025, 1, 2, 13, tzinfo=timezone.utc)
        after_close = datetime(2025, 1, 2, 22, tzinfo=timezone.utc)

        self.assertEqual(
            next_regular_session(before_open, self.calendar).trading_date,
            date(2025, 1, 2),
        )
        self.assertEqual(
            next_regular_session(after_close, self.calendar).trading_date,
            date(2025, 1, 3),
        )
        self.assertEqual(
            previous_regular_session(after_close, self.calendar).trading_date,
            date(2025, 1, 2),
        )
        self.assertEqual(
            previous_regular_session(before_open, self.calendar).trading_date,
            date(2024, 12, 31),
        )

    def test_normalizes_aware_and_explicitly_zoned_naive_timestamps(self) -> None:
        aware = normalize_timestamp(datetime(2025, 7, 1, 9, 30), "America/New_York")

        self.assertEqual(aware, datetime(2025, 7, 1, 13, 30, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, "explicit source timezone"):
            normalize_timestamp(datetime(2025, 7, 1, 9, 30))
        with self.assertRaisesRegex(ValueError, "must not be supplied"):
            normalize_timestamp(aware, "UTC")
        with self.assertRaisesRegex(ValueError, "does not exist"):
            normalize_timestamp(datetime(2025, 3, 9, 2, 30), "America/New_York")

    def test_supports_sessions_opening_on_the_previous_calendar_day(self) -> None:
        overnight = TradingCalendar(
            identifier=TradingCalendarIdentifier("example.overnight"),
            exchange=ExchangeIdentifier("XEXM"),
            timezone="UTC",
            schedules=(
                WeekdaySchedule(
                    0,
                    SessionTemplate(
                        SessionBoundary(time(18), day_offset=-1),
                        SessionBoundary(time(17)),
                    ),
                ),
            ),
        )

        alignment = align_timestamp(
            datetime(2025, 1, 5, 23, tzinfo=timezone.utc),
            overnight,
        )

        self.assertEqual(alignment.phase, SessionPhase.REGULAR)
        assert alignment.session is not None
        self.assertEqual(alignment.session.trading_date, date(2025, 1, 6))

    def test_rejects_invalid_and_conflicting_schedules(self) -> None:
        regular = session_template(time(9, 30), time(16))
        with self.assertRaisesRegex(ValueError, "weekdays must be unique"):
            TradingCalendar(
                TradingCalendarIdentifier("duplicate"),
                ExchangeIdentifier("XNAS"),
                "UTC",
                (WeekdaySchedule(0, regular), WeekdaySchedule(0, regular)),
            )
        with self.assertRaisesRegex(ValueError, "both closed and overridden"):
            TradingCalendar(
                TradingCalendarIdentifier("conflict"),
                ExchangeIdentifier("XNAS"),
                "UTC",
                (WeekdaySchedule(0, regular),),
                closures=(CalendarClosure(date(2025, 1, 6), "Closed"),),
                overrides=(SessionOverride(date(2025, 1, 6), regular, "Override"),),
            )


if __name__ == "__main__":
    unittest.main()
