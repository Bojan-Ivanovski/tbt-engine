import unittest
from datetime import datetime, timezone

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier
from tbt_engine.providers.capabilities.market.vix import VIXQuery, VIXRecord, VIXResult


class VIXTests(unittest.TestCase):
    def test_vix(self) -> None:
        market = MarketIdentifier("index", "VIX")
        source = SourceMetadata("memory", "vix", datetime(2026, 1, 2, tzinfo=timezone.utc))
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record = VIXRecord(MarketDataMetadata(market, source, stamp, stamp), 18.2, "1d")
        result = VIXResult(
            VIXQuery(market, stamp, datetime(2026, 1, 2, tzinfo=timezone.utc)),
            MarketDataResult(market, source, MarketDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
