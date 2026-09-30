import unittest

import tbt_engine
from tbt_engine.providers import (
    Capability,
    CapabilityId,
    CompanyCapabilities,
    DerivedCapabilities,
    MacroCapabilities,
    MarketCapabilities,
    Provider,
    TextualCapabilities,
)
from tbt_engine.providers.capabilities.company import OHLCV_CAPABILITY, OHLCVCapability
from tbt_engine.providers.capabilities.derived import RSI_CAPABILITY, RSICapability
from tbt_engine.providers.capabilities.macro import CPI_CAPABILITY, CPICapability
from tbt_engine.providers.capabilities.market import SP500_CAPABILITY, SP500Capability
from tbt_engine.providers.capabilities.textual import MARKET_NEWS_CAPABILITY, MarketNewsCapability


class CapabilityExportTests(unittest.TestCase):
    def test_domain_collections_and_leaf_contracts_are_public(self) -> None:
        self.assertIs(tbt_engine.CompanyCapabilities, CompanyCapabilities)
        self.assertIs(tbt_engine.DerivedCapabilities, DerivedCapabilities)
        self.assertIs(tbt_engine.MacroCapabilities, MacroCapabilities)
        self.assertIs(tbt_engine.MarketCapabilities, MarketCapabilities)
        self.assertIs(tbt_engine.TextualCapabilities, TextualCapabilities)
        identifiers = {
            OHLCV_CAPABILITY: OHLCVCapability,
            RSI_CAPABILITY: RSICapability,
            CPI_CAPABILITY: CPICapability,
            SP500_CAPABILITY: SP500Capability,
            MARKET_NEWS_CAPABILITY: MarketNewsCapability,
        }
        self.assertEqual(
            {identifier.value.split(".")[0] for identifier in identifiers},
            {"company", "derived", "macro", "market", "textual"},
        )

    def test_provider_discovers_every_domain_collection(self) -> None:
        class StubCapability(Capability):
            def __init__(self, identifier: CapabilityId) -> None:
                self._id = identifier

            @property
            def id(self) -> CapabilityId:
                return self._id

        groups = (
            CompanyCapabilities("test", (StubCapability(OHLCV_CAPABILITY),)),
            DerivedCapabilities("test", (StubCapability(RSI_CAPABILITY),)),
            MacroCapabilities("test", (StubCapability(CPI_CAPABILITY),)),
            MarketCapabilities("test", (StubCapability(SP500_CAPABILITY),)),
            TextualCapabilities("test", (StubCapability(MARKET_NEWS_CAPABILITY),)),
        )
        provider = Provider(groups)

        self.assertEqual(provider.capability_groups, groups)
        expected = frozenset(
            identifier for group in groups for identifier in group.supported_capabilities
        )
        self.assertEqual(provider.supported_capabilities, expected)
        for group in groups:
            self.assertTrue(provider.has_capability_group(type(group)))
            self.assertTrue(provider.supports(next(iter(group.supported_capabilities))))


if __name__ == "__main__":
    unittest.main()
