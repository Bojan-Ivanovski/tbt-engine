import unittest
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

from tbt_engine import SourceMetadata
from tbt_engine.providers.capabilities import Capability, CapabilityId
from tbt_engine.providers.capabilities.market.market_capabilities import MarketCapabilities
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier
from tbt_engine.providers.provider import Provider

BREADTH = CapabilityId("market.breadth")


class BreadthCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return BREADTH


class CompanyCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return CapabilityId("company.ohlcv")


class MarketProvider(Provider):
    def __init__(self) -> None:
        self.breadth = BreadthCapability()
        super().__init__(capability_groups=(MarketCapabilities(self.name, (self.breadth,)),))


class MarketCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.market = MarketIdentifier("ticker", "^GSPC", market="xnas")
        self.source = SourceMetadata(
            provider="test-provider",
            source="test-dataset",
            retrieved_at=datetime(2026, 9, 28, tzinfo=timezone.utc),
        )

    def test_market_capabilities_accept_only_market_namespace(self) -> None:
        capabilities = MarketCapabilities("provider", (BreadthCapability(),))

        self.assertTrue(capabilities.supports(BreadthCapability))
        with self.assertRaisesRegex(ValueError, "'market.' namespace"):
            MarketCapabilities("provider", (CompanyCapability(),))

    def test_provider_composes_market_capabilities(self) -> None:
        provider = MarketProvider()

        market = provider.require_capability_group(MarketCapabilities)
        self.assertIs(market.require(BreadthCapability), provider.breadth)

    def test_market_identifier_normalizes_scheme_value_and_market(self) -> None:
        self.assertEqual(self.market.scheme, "ticker")
        self.assertEqual(self.market.value, "^GSPC")
        self.assertEqual(self.market.market, "XNAS")

        figi = MarketIdentifier(" FIGI ", " BBG000BDTBL9 ")
        self.assertEqual(figi, MarketIdentifier("figi", "BBG000BDTBL9"))

    def test_market_identifier_is_frozen_and_ordered(self) -> None:
        identifiers = [
            MarketIdentifier("ticker", "^VIX"),
            MarketIdentifier("ticker", "^GSPC"),
        ]

        self.assertEqual(sorted(identifiers), list(reversed(identifiers)))
        with self.assertRaises(FrozenInstanceError):
            self.market.value = "^IXIC"  # type: ignore[misc]

    def test_market_identifier_rejects_invalid_components(self) -> None:
        for scheme in ("", "1ticker", "ticker symbol", "ticker/"):
            with self.subTest(scheme=scheme), self.assertRaises(ValueError):
                MarketIdentifier(scheme, "^GSPC")
        with self.assertRaises(ValueError):
            MarketIdentifier("ticker", "")
        with self.assertRaises(ValueError):
            MarketIdentifier("ticker", "^GSPC", market=" ")

    def test_market_metadata_accepts_date_and_aware_datetime_effective_times(self) -> None:
        dated = MarketDataMetadata(
            market=self.market,
            source=self.source,
            effective_at=date(2026, 9, 28),
            available_at=datetime(2026, 9, 28, 20, tzinfo=timezone.utc),
        )
        timed = MarketDataMetadata(
            market=self.market,
            source=self.source,
            effective_at=datetime(2026, 9, 28, 20, tzinfo=timezone.utc),
        )

        self.assertEqual(dated.effective_at, date(2026, 9, 28))
        self.assertIsNone(timed.available_at)

    def test_market_metadata_rejects_naive_datetimes(self) -> None:
        with self.assertRaisesRegex(ValueError, "effective time"):
            MarketDataMetadata(
                market=self.market,
                source=self.source,
                effective_at=datetime(2026, 9, 28),
            )
        with self.assertRaisesRegex(ValueError, "availability time"):
            MarketDataMetadata(
                market=self.market,
                source=self.source,
                effective_at=date(2026, 9, 28),
                available_at=datetime(2026, 9, 29),
            )

    def test_available_empty_result_is_distinct_from_unavailable_data(self) -> None:
        available = MarketDataResult[str](
            market=self.market,
            source=self.source,
            availability=MarketDataAvailability.AVAILABLE,
        )
        unavailable = MarketDataResult[str](
            market=self.market,
            source=self.source,
            availability=MarketDataAvailability.UNAVAILABLE,
            reason="Provider has no coverage for this market",
        )

        self.assertEqual(available.records, ())
        self.assertIsNone(available.reason)
        self.assertEqual(unavailable.availability, MarketDataAvailability.UNAVAILABLE)

    def test_available_result_rejects_any_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not include"):
            MarketDataResult[str](
                market=self.market,
                source=self.source,
                availability=MarketDataAvailability.AVAILABLE,
                reason="Unexpected reason",
            )
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            MarketDataResult[str](
                market=self.market,
                source=self.source,
                availability=MarketDataAvailability.AVAILABLE,
                reason=" ",
            )

    def test_result_snapshots_mutable_record_inputs(self) -> None:
        records = ["first"]
        result = MarketDataResult[str](
            market=self.market,
            source=self.source,
            availability=MarketDataAvailability.PARTIAL,
            records=records,  # type: ignore[arg-type]
            reason="Later coverage is unavailable",
        )

        records.append("second")

        self.assertEqual(result.records, ("first",))
        self.assertIsInstance(result.records, tuple)

    def test_partial_result_requires_records_and_a_reason(self) -> None:
        partial = MarketDataResult(
            market=self.market,
            source=self.source,
            availability=MarketDataAvailability.PARTIAL,
            records=("record",),
            reason=" Some sessions are unavailable ",
        )

        self.assertEqual(partial.records, ("record",))
        self.assertEqual(partial.reason, "Some sessions are unavailable")
        with self.assertRaisesRegex(ValueError, "requires records and a reason"):
            MarketDataResult[str](
                market=self.market,
                source=self.source,
                availability=MarketDataAvailability.PARTIAL,
                reason="No records",
            )
        with self.assertRaisesRegex(ValueError, "requires records and a reason"):
            MarketDataResult(
                market=self.market,
                source=self.source,
                availability=MarketDataAvailability.PARTIAL,
                records=("record",),
            )

    def test_unavailable_result_requires_no_records_and_a_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a reason and no records"):
            MarketDataResult(
                market=self.market,
                source=self.source,
                availability=MarketDataAvailability.UNAVAILABLE,
                records=("record",),
                reason="Contradictory result",
            )
        with self.assertRaisesRegex(ValueError, "requires a reason and no records"):
            MarketDataResult[str](
                market=self.market,
                source=self.source,
                availability=MarketDataAvailability.UNAVAILABLE,
            )


if __name__ == "__main__":
    unittest.main()
