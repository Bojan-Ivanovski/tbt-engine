import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.company.company_capabilities import (
    CompanyCapabilities,
)
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier
from tbt_engine.providers.capabilities.company.earnings import (
    EARNINGS_CAPABILITY,
    EarningsActual,
    EarningsCapability,
    EarningsEstimate,
    EarningsEvent,
    EarningsMetricId,
    EarningsQuery,
    EarningsReportingPeriod,
    EarningsResult,
    EarningsSurprise,
    EarningsTimingStatus,
)


class InMemoryEarningsCapability(EarningsCapability):
    def __init__(self, result: EarningsResult) -> None:
        self.result = result
        self.queries: list[EarningsQuery] = []

    def get_earnings(self, query: EarningsQuery) -> EarningsResult:
        self.queries.append(query)
        return self.result


class EarningsCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = CompanyIdentifier("ticker", "TEST", market="XNAS")
        self.source = SourceMetadata(
            provider="memory",
            source="fixed-earnings",
            retrieved_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        self.announcement_at = datetime(2026, 4, 20, 20, tzinfo=timezone.utc)
        self.published_at = self.announcement_at + timedelta(minutes=1)
        self.available_at = self.published_at + timedelta(seconds=30)
        self.period = EarningsReportingPeriod(
            start=date(2026, 1, 1),
            end=date(2026, 3, 31),
            label="Q1 2026",
        )
        self.eps = EarningsMetricId("earnings_per_share")

    def metadata(
        self,
        announcement_at: datetime | None = None,
        available_at: datetime | None = None,
    ) -> CompanyDataMetadata:
        effective_at = announcement_at or self.announcement_at
        return CompanyDataMetadata(
            company=self.company,
            source=self.source,
            effective_at=effective_at,
            available_at=available_at or self.available_at,
        )

    def estimate(self, value: Decimal | None = Decimal("1.20")) -> EarningsEstimate:
        return EarningsEstimate(
            metric=self.eps,
            value=value,
            unit="per_share",
            currency="usd",
            analyst_count=12,
        )

    def actual(self, value: Decimal | None = Decimal("1.25")) -> EarningsActual:
        return EarningsActual(
            metric=self.eps,
            value=value,
            unit="per_share",
            currency="USD",
        )

    def event(
        self,
        *,
        announcement_at: datetime | None = None,
        timing_status: EarningsTimingStatus = EarningsTimingStatus.CONFIRMED,
        estimates: tuple[EarningsEstimate, ...] = (),
        actuals: tuple[EarningsActual, ...] = (),
        surprises: tuple[EarningsSurprise, ...] = (),
        published_at: datetime | None = None,
    ) -> EarningsEvent:
        effective_at = announcement_at or self.announcement_at
        publication = published_at if published_at is not None else self.published_at
        availability = max(publication, effective_at) + timedelta(seconds=30)
        return EarningsEvent(
            metadata=self.metadata(effective_at, availability),
            reporting_period=self.period,
            announcement_at=effective_at,
            timing_status=timing_status,
            published_at=publication,
            estimates=estimates,
            actuals=actuals,
            surprises=surprises,
        )

    def query(self) -> EarningsQuery:
        return EarningsQuery(
            company=self.company,
            start=self.announcement_at - timedelta(days=1),
            end=self.announcement_at + timedelta(days=1),
        )

    def result(self, *events: EarningsEvent) -> EarningsResult:
        query = self.query()
        return EarningsResult(
            query=query,
            data=CompanyDataResult(
                company=self.company,
                source=self.source,
                availability=CompanyDataAvailability.AVAILABLE,
                records=events,
            ),
        )

    def test_capability_has_stable_identity_and_composes_with_company_domain(self) -> None:
        result = self.result()
        capability = InMemoryEarningsCapability(result)
        company_capabilities = CompanyCapabilities("memory", (capability,))

        self.assertEqual(capability.id, EARNINGS_CAPABILITY)
        self.assertIs(company_capabilities.require(EarningsCapability), capability)
        self.assertIs(capability.get_earnings(result.query), result)

    def test_query_normalizes_filters_and_uses_shared_query_errors(self) -> None:
        statuses = {EarningsTimingStatus.CONFIRMED}
        query = EarningsQuery(
            company=self.company,
            timing_statuses=statuses,  # pyright: ignore[reportArgumentType]
        )
        statuses.clear()

        self.assertEqual(query.timing_statuses, frozenset((EarningsTimingStatus.CONFIRMED,)))
        invalid_queries = (
            lambda: EarningsQuery(company=self.company, timing_statuses=frozenset()),
            lambda: EarningsQuery(
                company=self.company,
                start=datetime(2026, 1, 1),
            ),
            lambda: EarningsQuery(
                company=self.company,
                start=self.announcement_at,
                end=self.announcement_at,
            ),
        )
        for invalid_query in invalid_queries:
            with self.subTest(invalid_query=invalid_query):
                with self.assertRaises(InvalidCapabilityQueryError):
                    invalid_query()

    def test_reporting_period_and_event_times_are_explicit_and_validated(self) -> None:
        self.assertEqual(self.period.end, date(2026, 3, 31))
        self.assertEqual(self.period.label, "Q1 2026")
        with self.assertRaises(ValueError):
            EarningsReportingPeriod(date(2026, 4, 1), date(2026, 3, 31))
        with self.assertRaises(ValueError):
            EarningsEvent(
                metadata=self.metadata(),
                reporting_period=self.period,
                announcement_at=datetime(2026, 4, 20, 20),
                timing_status=EarningsTimingStatus.CONFIRMED,
            )

    def test_estimates_and_actuals_preserve_missing_zero_and_currency(self) -> None:
        zero_estimate = self.estimate(Decimal(0))
        missing_actual = self.actual(None)

        self.assertEqual(zero_estimate.value, Decimal(0))
        self.assertEqual(zero_estimate.currency, "USD")
        self.assertEqual(zero_estimate.analyst_count, 12)
        self.assertIsNone(missing_actual.value)
        self.assertEqual(missing_actual.metric, zero_estimate.metric)

    def test_estimated_timing_cannot_conflate_reported_facts(self) -> None:
        estimate = self.estimate()
        estimated_event = self.event(
            timing_status=EarningsTimingStatus.ESTIMATED,
            estimates=(estimate,),
            published_at=self.announcement_at - timedelta(days=7),
        )

        self.assertEqual(estimated_event.estimates, (estimate,))
        self.assertEqual(estimated_event.actuals, ())
        with self.assertRaisesRegex(ValueError, "cannot contain reported facts"):
            self.event(
                timing_status=EarningsTimingStatus.ESTIMATED,
                actuals=(self.actual(),),
            )

    def test_confirmed_event_keeps_estimate_actual_and_surprise_distinct(self) -> None:
        estimate = self.estimate()
        actual = self.actual()
        surprise = EarningsSurprise(
            metric=self.eps,
            value=Decimal("0.05"),
            percent=Decimal("4.1667"),
            unit="per_share",
            currency="USD",
        )

        event = self.event(
            estimates=(estimate,),
            actuals=(actual,),
            surprises=(surprise,),
        )

        self.assertEqual(event.estimates, (estimate,))
        self.assertEqual(event.actuals, (actual,))
        self.assertEqual(event.surprises, (surprise,))

    def test_event_validates_fact_uniqueness_and_order(self) -> None:
        revenue = EarningsEstimate(
            metric=EarningsMetricId("revenue"),
            value=Decimal("100"),
            unit="currency",
            currency="USD",
        )
        eps = self.estimate()

        event = self.event(estimates=(eps, revenue))
        self.assertEqual(event.estimates, (eps, revenue))
        with self.assertRaisesRegex(ValueError, "unique ascending"):
            self.event(estimates=(revenue, eps))
        with self.assertRaisesRegex(ValueError, "unique ascending"):
            self.event(estimates=(eps, eps))

    def test_event_preserves_publication_availability_and_source_metadata(self) -> None:
        event = self.event(actuals=(self.actual(),))

        self.assertEqual(event.published_at, self.published_at)
        self.assertEqual(event.metadata.available_at, self.available_at)
        self.assertEqual(event.metadata.source, self.source)
        with self.assertRaisesRegex(ValueError, "precede publication"):
            EarningsEvent(
                metadata=self.metadata(available_at=self.published_at - timedelta(seconds=1)),
                reporting_period=self.period,
                announcement_at=self.announcement_at,
                timing_status=EarningsTimingStatus.CONFIRMED,
                published_at=self.published_at,
            )

    def test_result_enforces_identity_status_and_half_open_bounds(self) -> None:
        different_company = CompanyIdentifier("ticker", "OTHER", market="XNAS")
        with self.assertRaisesRegex(ValueError, "result company"):
            EarningsResult(
                query=self.query(),
                data=CompanyDataResult(
                    company=different_company,
                    source=self.source,
                    availability=CompanyDataAvailability.AVAILABLE,
                ),
            )

        confirmed_only = EarningsQuery(
            company=self.company,
            timing_statuses=frozenset((EarningsTimingStatus.CONFIRMED,)),
        )
        estimated = self.event(
            timing_status=EarningsTimingStatus.ESTIMATED,
            published_at=self.announcement_at - timedelta(days=1),
        )
        with self.assertRaisesRegex(ValueError, "not requested"):
            EarningsResult(
                query=confirmed_only,
                data=CompanyDataResult(
                    company=self.company,
                    source=self.source,
                    availability=CompanyDataAvailability.AVAILABLE,
                    records=(estimated,),
                ),
            )

        end_event = self.event(announcement_at=self.query().end)
        with self.assertRaisesRegex(ValueError, "exclusive query end"):
            self.result(end_event)

    def test_result_enforces_unique_deterministic_order(self) -> None:
        first = self.event(
            announcement_at=self.announcement_at - timedelta(hours=1),
            published_at=self.announcement_at - timedelta(minutes=59),
        )
        second = self.event()

        result = self.result(first, second)
        self.assertEqual(result.events, (first, second))
        with self.assertRaisesRegex(ValueError, "ascending order"):
            self.result(second, first)
        with self.assertRaisesRegex(ValueError, "unique"):
            self.result(second, second)

    def test_available_empty_result_remains_distinct_from_unavailable(self) -> None:
        result = self.result()

        self.assertEqual(result.availability, CompanyDataAvailability.AVAILABLE)
        self.assertEqual(result.events, ())


if __name__ == "__main__":
    unittest.main()
