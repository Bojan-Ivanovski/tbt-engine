import unittest
from datetime import date, datetime, timezone

from tbt_engine import (
    SourceMetadata,
)
from tbt_engine.providers.capabilities import Capability, CapabilityId
from tbt_engine.providers.capabilities.company.company_capabilities import (
    CompanyCapabilities,
)
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier
from tbt_engine.providers.provider import Provider

DIVIDENDS = CapabilityId("company.dividends")


class DividendCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return DIVIDENDS


class MarketCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return CapabilityId("market.breadth")


class CompanyProvider(Provider):
    def __init__(self) -> None:
        self.dividends = DividendCapability()
        super().__init__(capability_groups=(CompanyCapabilities(self.name, (self.dividends,)),))


class CompanyCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = CompanyIdentifier("ticker", "AAPL", market="xnas")
        self.source = SourceMetadata(
            provider="test-provider",
            source="test-dataset",
            retrieved_at=datetime(2026, 9, 28, tzinfo=timezone.utc),
        )

    def test_company_capabilities_accept_only_company_namespace(self) -> None:
        capabilities = CompanyCapabilities("provider", (DividendCapability(),))

        self.assertTrue(capabilities.supports(DividendCapability))
        with self.assertRaisesRegex(ValueError, "'company.' namespace"):
            CompanyCapabilities("provider", (MarketCapability(),))

    def test_provider_composes_company_capabilities(self) -> None:
        provider = CompanyProvider()

        company = provider.require_capability_group(CompanyCapabilities)
        self.assertIs(company.require(DividendCapability), provider.dividends)

    def test_company_identifier_preserves_scheme_and_market_qualification(self) -> None:
        self.assertEqual(self.company.scheme, "ticker")
        self.assertEqual(self.company.value, "AAPL")
        self.assertEqual(self.company.market, "XNAS")

        cik = CompanyIdentifier(" CIK ", " 0000320193 ")
        self.assertEqual(cik, CompanyIdentifier("cik", "0000320193"))

    def test_company_identifier_rejects_ambiguous_empty_components(self) -> None:
        with self.assertRaises(ValueError):
            CompanyIdentifier("", "AAPL")
        with self.assertRaises(ValueError):
            CompanyIdentifier("ticker", "")
        with self.assertRaises(ValueError):
            CompanyIdentifier("ticker", "AAPL", market=" ")

    def test_company_metadata_requires_aware_datetimes(self) -> None:
        metadata = CompanyDataMetadata(
            company=self.company,
            source=self.source,
            effective_at=date(2026, 9, 28),
            available_at=datetime(2026, 9, 28, 20, tzinfo=timezone.utc),
        )

        self.assertEqual(metadata.effective_at, date(2026, 9, 28))
        with self.assertRaises(ValueError):
            CompanyDataMetadata(
                company=self.company,
                source=self.source,
                effective_at=datetime(2026, 9, 28),
            )
        with self.assertRaises(ValueError):
            CompanyDataMetadata(
                company=self.company,
                source=self.source,
                effective_at=date(2026, 9, 28),
                available_at=datetime(2026, 9, 29),
            )

    def test_available_empty_result_is_distinct_from_unavailable_data(self) -> None:
        available = CompanyDataResult[str](
            company=self.company,
            source=self.source,
            availability=CompanyDataAvailability.AVAILABLE,
        )
        unavailable = CompanyDataResult[str](
            company=self.company,
            source=self.source,
            availability=CompanyDataAvailability.UNAVAILABLE,
            reason="Provider has no coverage for this company",
        )

        self.assertEqual(available.records, ())
        self.assertIsNone(available.reason)
        self.assertEqual(unavailable.availability, CompanyDataAvailability.UNAVAILABLE)

    def test_result_records_are_normalized_to_an_immutable_tuple(self) -> None:
        records = ["record"]

        result = CompanyDataResult[str](
            company=self.company,
            source=self.source,
            availability=CompanyDataAvailability.AVAILABLE,
            records=records,  # pyright: ignore[reportArgumentType]
        )
        records.append("later mutation")

        self.assertEqual(result.records, ("record",))
        self.assertIsInstance(result.records, tuple)

    def test_partial_and_unavailable_results_enforce_their_invariants(self) -> None:
        partial = CompanyDataResult(
            company=self.company,
            source=self.source,
            availability=CompanyDataAvailability.PARTIAL,
            records=("record",),
            reason="Some reporting periods are unavailable",
        )

        self.assertEqual(partial.records, ("record",))
        with self.assertRaises(ValueError):
            CompanyDataResult[str](
                company=self.company,
                source=self.source,
                availability=CompanyDataAvailability.PARTIAL,
                reason="No records",
            )
        with self.assertRaises(ValueError):
            CompanyDataResult(
                company=self.company,
                source=self.source,
                availability=CompanyDataAvailability.UNAVAILABLE,
                records=("record",),
                reason="Contradictory result",
            )


if __name__ == "__main__":
    unittest.main()
