import unittest

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.textual.market_news import MarketNewsQuery
from tbt_engine.providers.capabilities.textual.textual_data import (
    TextualRequestContext,
    TextualTimeBasis,
)


class MarketNewsTests(unittest.TestCase):
    def test_scope(self) -> None:
        self.assertEqual(
            MarketNewsQuery(
                TextualRequestContext(TextualTimeBasis.PUBLISHED_AT), market="global"
            ).market,
            "global",
        )

    def test_scope_required(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            MarketNewsQuery(TextualRequestContext(TextualTimeBasis.PUBLISHED_AT))


if __name__ == "__main__":
    unittest.main()
