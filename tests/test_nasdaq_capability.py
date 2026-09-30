import unittest
from datetime import datetime, timezone

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier
from tbt_engine.providers.capabilities.market.nasdaq import (
    NasdaqObservation,
    NasdaqObservationKind,
    NasdaqQuery,
    NasdaqRecordType,
    NasdaqResult,
)


class NasdaqTests(unittest.TestCase):
    def test_observation(self) -> None:
        market = MarketIdentifier("index", "NASDAQ-100")
        source = SourceMetadata("memory", "nasdaq", datetime(2026, 1, 2, tzinfo=timezone.utc))
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record = NasdaqObservation(
            MarketDataMetadata(market, source, stamp, stamp), NasdaqObservationKind.LEVEL, 100.0
        )
        result = NasdaqResult(
            NasdaqQuery(
                market,
                NasdaqRecordType.OBSERVATION,
                stamp,
                datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
            MarketDataResult(market, source, MarketDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
