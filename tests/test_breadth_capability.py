import unittest
from datetime import datetime, timezone

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.market.breadth import (
    BreadthQuery,
    BreadthRecord,
    BreadthResult,
)
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier


class BreadthTests(unittest.TestCase):
    def test_breadth(self) -> None:
        market = MarketIdentifier("universe", "NYSE")
        source = SourceMetadata("memory", "breadth", datetime(2026, 1, 2, tzinfo=timezone.utc))
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record = BreadthRecord(
            MarketDataMetadata(market, source, stamp, stamp),
            "1d",
            "exchange_close",
            advancing_issues=10,
            declining_issues=5,
        )
        result = BreadthResult(
            BreadthQuery(
                market,
                stamp,
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                methodology="exchange_close",
            ),
            MarketDataResult(market, source, MarketDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
