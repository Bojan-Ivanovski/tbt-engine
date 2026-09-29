import unittest
from datetime import datetime, timezone

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier
from tbt_engine.providers.capabilities.market.sector_etf import (
    SectorETFObservation,
    SectorETFObservationKind,
    SectorETFQuery,
    SectorETFResult,
)


class SectorETFTests(unittest.TestCase):
    def test_observation(self) -> None:
        market = MarketIdentifier("ticker", "XLK", market="ARCX")
        source = SourceMetadata("memory", "sector", datetime(2026, 1, 2, tzinfo=timezone.utc))
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record = SectorETFObservation(
            MarketDataMetadata(market, source, stamp, stamp),
            SectorETFObservationKind.LEVEL,
            100,
            "1d",
        )
        result = SectorETFResult(
            SectorETFQuery(market, start=stamp, end=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            MarketDataResult(market, source, MarketDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
