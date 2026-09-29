import unittest
from datetime import datetime, timezone

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef
from tbt_engine.providers.capabilities.derived.macd import MACDQuery


class MACDTests(unittest.TestCase):
    def test_query(self) -> None:
        self.assertEqual(
            MACDQuery(
                InputSeriesRef("company.ohlcv", "T", "close"),
                12,
                26,
                9,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 2, 1, tzinfo=timezone.utc),
            ).signal_period,
            9,
        )

    def test_invalid(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            MACDQuery(
                InputSeriesRef("x", "y", "z"),
                26,
                12,
                9,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 2, 1, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
