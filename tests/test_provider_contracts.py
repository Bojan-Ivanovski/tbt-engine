import unittest
from datetime import datetime, timezone

from tbt_engine import (
    Capabilities,
    Capability,
    CapabilityId,
    SourceMetadata,
    UnsupportedCapabilityError,
    UnsupportedCapabilityGroupError,
)
from tbt_engine.providers import Provider

DIVIDENDS = CapabilityId("company.dividends")


class DividendCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return DIVIDENDS


class CompanyCapabilities(Capabilities):
    pass


class EmptyProvider(Provider):
    pass


class CompanyProvider(Provider):
    def __init__(self) -> None:
        self.dividends = DividendCapability()
        super().__init__(
            capability_groups=(CompanyCapabilities(self.name, capabilities=(self.dividends,)),)
        )


class ProviderContractTests(unittest.TestCase):
    def test_capability_identifier_is_normalized_and_hashable(self) -> None:
        capability = CapabilityId(" company.ohlcv ")

        self.assertEqual(str(capability), "company.ohlcv")
        self.assertEqual(frozenset({capability}), frozenset({CapabilityId("company.ohlcv")}))

    def test_capability_identifier_rejects_empty_or_whitespace_values(self) -> None:
        with self.assertRaises(ValueError):
            CapabilityId(" ")
        with self.assertRaises(ValueError):
            CapabilityId("company ohlcv")

    def test_capabilities_resolve_by_identifier_and_contract(self) -> None:
        provider = CompanyProvider()
        company = provider.require_capability_group(CompanyCapabilities)

        self.assertIs(company.require(DIVIDENDS), provider.dividends)
        self.assertIs(company.require(DividendCapability), provider.dividends)
        self.assertTrue(company.supports(DIVIDENDS))
        self.assertTrue(company.supports(DividendCapability))

    def test_provider_composes_domain_capability_collections(self) -> None:
        provider = CompanyProvider()

        self.assertEqual(provider.supported_capabilities, frozenset({DIVIDENDS}))
        self.assertTrue(provider.has_capability_group(CompanyCapabilities))
        self.assertTrue(provider.supports(DividendCapability))
        self.assertIs(provider.require_capability(DividendCapability), provider.dividends)

    def test_provider_makes_unsupported_contracts_explicit(self) -> None:
        provider = EmptyProvider()
        capability = CapabilityId("company.ohlcv")

        self.assertFalse(provider.supports(capability))
        with self.assertRaisesRegex(
            UnsupportedCapabilityError,
            "EmptyProvider.*company.ohlcv",
        ):
            provider.require_capability(capability)
        with self.assertRaisesRegex(
            UnsupportedCapabilityGroupError,
            "EmptyProvider.*CompanyCapabilities",
        ):
            provider.require_capability_group(CompanyCapabilities)

    def test_capabilities_reject_duplicate_identifiers(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate capability identifier"):
            CompanyCapabilities(
                "provider",
                capabilities=(DividendCapability(), DividendCapability()),
            )

    def test_source_metadata_requires_an_aware_retrieval_time(self) -> None:
        metadata = SourceMetadata(
            provider=" yahoo ",
            source=" Yahoo Finance ",
            retrieved_at=datetime(2026, 9, 28, tzinfo=timezone.utc),
            source_record_id=" quote-1 ",
        )

        self.assertEqual(metadata.provider, "yahoo")
        self.assertEqual(metadata.source_record_id, "quote-1")
        with self.assertRaises(ValueError):
            SourceMetadata(
                provider="yahoo",
                source="Yahoo Finance",
                retrieved_at=datetime(2026, 9, 28),
            )


if __name__ == "__main__":
    unittest.main()
