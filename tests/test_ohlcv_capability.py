import unittest
from datetime import datetime, timedelta, timezone

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
from tbt_engine.providers.capabilities.company.ohlcv import (
    OHLCV_CAPABILITY,
    BarInterval,
    BarIntervalUnit,
    OHLCVAdjustment,
    OHLCVBar,
    OHLCVCapability,
    OHLCVQuery,
    OHLCVResult,
)


class InMemoryOHLCVCapability(OHLCVCapability):
    def __init__(self, result: OHLCVResult) -> None:
        self.result = result
        self.queries: list[OHLCVQuery] = []

    def get_ohlcv(self, query: OHLCVQuery) -> OHLCVResult:
        self.queries.append(query)
        return self.result


class OHLCVCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = CompanyIdentifier("ticker", "TEST", market="XNAS")
        self.interval = BarInterval(1, BarIntervalUnit.DAY)
        self.start = datetime(2026, 1, 5, tzinfo=timezone.utc)
        self.source = SourceMetadata(
            provider="memory",
            source="fixed-bars",
            retrieved_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

    def make_bar(self, day: int, *, close: float = 12.0) -> OHLCVBar:
        timestamp = self.start + timedelta(days=day)
        return OHLCVBar(
            metadata=CompanyDataMetadata(
                company=self.company,
                source=self.source,
                effective_at=timestamp,
                available_at=timestamp + timedelta(days=1),
            ),
            interval=self.interval,
            open=10,
            high=max(13, close),
            low=9,
            close=close,
            volume=1_000,
            adjustment=OHLCVAdjustment.UNADJUSTED,
        )

    def make_query(self) -> OHLCVQuery:
        return OHLCVQuery(
            company=self.company,
            interval=self.interval,
            adjustment=OHLCVAdjustment.UNADJUSTED,
            start=self.start,
            end=self.start + timedelta(days=3),
        )

    def make_result(self, *bars: OHLCVBar) -> OHLCVResult:
        query = self.make_query()
        return OHLCVResult(
            query=query,
            data=CompanyDataResult(
                company=self.company,
                source=self.source,
                availability=CompanyDataAvailability.AVAILABLE,
                records=bars,
            ),
        )

    def test_capability_has_stable_identity_and_composes_with_company_domain(self) -> None:
        result = self.make_result()
        capability = InMemoryOHLCVCapability(result)
        company_capabilities = CompanyCapabilities("memory", (capability,))

        self.assertEqual(capability.id, OHLCV_CAPABILITY)
        self.assertIs(company_capabilities.require(OHLCVCapability), capability)
        self.assertIs(capability.get_ohlcv(result.query), result)

    def test_interval_and_query_are_provider_independent_and_time_bounded(self) -> None:
        query = self.make_query()

        self.assertEqual(str(query.interval), "1d")

    def test_invalid_interval_and_query_dimensions_use_shared_query_error(self) -> None:
        invalid_intervals = (
            lambda: BarInterval(0, BarIntervalUnit.DAY),
            lambda: BarInterval(True, BarIntervalUnit.DAY),
            lambda: BarInterval(1.5, BarIntervalUnit.DAY),  # pyright: ignore[reportArgumentType]
            lambda: BarInterval(1, "day"),  # pyright: ignore[reportArgumentType]
        )
        for invalid_interval in invalid_intervals:
            with self.subTest(invalid_interval=invalid_interval):
                with self.assertRaises(InvalidCapabilityQueryError):
                    invalid_interval()

        invalid_queries = (
            lambda: OHLCVQuery(
                company="TEST",  # pyright: ignore[reportArgumentType]
                interval=self.interval,
            ),
            lambda: OHLCVQuery(
                company=self.company,
                interval="1d",  # pyright: ignore[reportArgumentType]
            ),
            lambda: OHLCVQuery(
                company=self.company,
                interval=self.interval,
                adjustment="unadjusted",  # pyright: ignore[reportArgumentType]
            ),
            lambda: OHLCVQuery(
                company=self.company,
                interval=self.interval,
                start=datetime(2026, 1, 5),
            ),
            lambda: OHLCVQuery(
                company=self.company,
                interval=self.interval,
                start=self.start,
                end=self.start,
            ),
            lambda: OHLCVQuery(
                company=self.company,
                interval=self.interval,
                adjustment=OHLCVAdjustment.UNKNOWN,
            ),
        )
        for invalid_query in invalid_queries:
            with self.subTest(invalid_query=invalid_query):
                with self.assertRaises(InvalidCapabilityQueryError):
                    invalid_query()

    def test_daily_interval_preserves_provider_session_alignment(self) -> None:
        session_open = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        query = OHLCVQuery(
            company=self.company,
            interval=self.interval,
            start=session_open,
            end=session_open + timedelta(days=1),
        )
        bar = OHLCVBar(
            metadata=CompanyDataMetadata(
                company=self.company,
                source=self.source,
                effective_at=session_open,
                available_at=session_open + timedelta(hours=7),
            ),
            interval=self.interval,
            open=10,
            high=13,
            low=9,
            close=12,
            volume=1_000,
            adjustment=OHLCVAdjustment.UNADJUSTED,
        )

        result = OHLCVResult(
            query=query,
            data=CompanyDataResult(
                company=self.company,
                source=self.source,
                availability=CompanyDataAvailability.AVAILABLE,
                records=(bar,),
            ),
        )

        self.assertEqual(result.bars[0].timestamp, session_open)

    def test_query_rejects_naive_end_time(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            OHLCVQuery(
                company=self.company,
                interval=self.interval,
                end=datetime(2026, 1, 6),
            )

    def test_bar_preserves_prices_volume_adjustment_and_source_metadata(self) -> None:
        bar = self.make_bar(0)

        self.assertEqual(bar.timestamp, self.start)
        self.assertEqual(bar.open, 10.0)
        self.assertEqual(bar.volume, 1_000.0)
        self.assertEqual(bar.adjustment, OHLCVAdjustment.UNADJUSTED)
        self.assertEqual(bar.metadata.source, self.source)

    def test_bar_rejects_invalid_price_ranges_and_availability_time(self) -> None:
        with self.assertRaises(ValueError):
            OHLCVBar(
                metadata=CompanyDataMetadata(
                    company=self.company,
                    source=self.source,
                    effective_at=self.start,
                ),
                interval=self.interval,
                open=10,
                high=9,
                low=8,
                close=10,
                volume=1_000,
                adjustment=OHLCVAdjustment.UNADJUSTED,
            )
        with self.assertRaises(ValueError):
            OHLCVBar(
                metadata=CompanyDataMetadata(
                    company=self.company,
                    source=self.source,
                    effective_at=self.start,
                    available_at=self.start - timedelta(seconds=1),
                ),
                interval=self.interval,
                open=10,
                high=11,
                low=9,
                close=10,
                volume=1_000,
                adjustment=OHLCVAdjustment.UNADJUSTED,
            )

    def test_result_enforces_unique_ascending_time_alignment(self) -> None:
        first = self.make_bar(0)
        second = self.make_bar(1)

        result = self.make_result(first, second)
        self.assertEqual(result.bars, (first, second))
        with self.assertRaisesRegex(ValueError, "unique, ascending"):
            self.make_result(second, first)
        with self.assertRaisesRegex(ValueError, "unique, ascending"):
            self.make_result(first, first)

    def test_result_enforces_query_identity_interval_adjustment_and_bounds(self) -> None:
        different_company = CompanyIdentifier("ticker", "OTHER", market="XNAS")
        with self.assertRaisesRegex(ValueError, "company must match"):
            OHLCVResult(
                query=self.make_query(),
                data=CompanyDataResult(
                    company=different_company,
                    source=self.source,
                    availability=CompanyDataAvailability.AVAILABLE,
                ),
            )

        with self.assertRaisesRegex(ValueError, "exclusive query end"):
            self.make_result(self.make_bar(3))

        adjusted_bar = OHLCVBar(
            metadata=self.make_bar(0).metadata,
            interval=self.interval,
            open=10,
            high=13,
            low=9,
            close=12,
            volume=1_000,
            adjustment=OHLCVAdjustment.SPLIT_ADJUSTED,
        )
        with self.assertRaisesRegex(ValueError, "adjustment must match"):
            self.make_result(adjusted_bar)

    def test_available_empty_result_is_a_valid_deterministic_response(self) -> None:
        result = self.make_result()

        self.assertEqual(result.availability, CompanyDataAvailability.AVAILABLE)
        self.assertEqual(result.bars, ())


if __name__ == "__main__":
    unittest.main()
