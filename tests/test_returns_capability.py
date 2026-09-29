import unittest
from datetime import datetime, timezone

from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef
from tbt_engine.providers.capabilities.derived.returns import ReturnMethod, ReturnsQuery


class ReturnsTests(unittest.TestCase):
    def test_query(self) -> None:
        q = ReturnsQuery(
            InputSeriesRef("company.ohlcv", "T", "close"),
            5,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(q.method, ReturnMethod.SIMPLE)


if __name__ == "__main__":
    unittest.main()
