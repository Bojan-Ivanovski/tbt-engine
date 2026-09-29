import unittest
from datetime import datetime, timezone

from tbt_engine.providers.capabilities.derived.atr import ATRQuery, ATRSmoothing
from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef


class ATRTests(unittest.TestCase):
    def test_query(self) -> None:
        ref = InputSeriesRef("company.ohlcv", "T", "high")
        query = ATRQuery(
            ref,
            InputSeriesRef("company.ohlcv", "T", "low"),
            InputSeriesRef("company.ohlcv", "T", "close"),
            14,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(query.smoothing, ATRSmoothing.WILDER)


if __name__ == "__main__":
    unittest.main()
