import unittest
from datetime import datetime, timezone

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef
from tbt_engine.providers.capabilities.derived.rsi import RSIQuery


class RSITests(unittest.TestCase):
    def test_query(self) -> None:
        q = RSIQuery(
            InputSeriesRef("company.ohlcv", "TEST", "close"),
            14,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(q.lookback, 14)

    def test_invalid(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            RSIQuery(
                InputSeriesRef("x", "y", "z"),
                0,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 2, 1, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
