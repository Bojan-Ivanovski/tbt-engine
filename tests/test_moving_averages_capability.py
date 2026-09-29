import unittest
from datetime import datetime, timezone

from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef
from tbt_engine.providers.capabilities.derived.moving_averages import (
    MovingAverageKind,
    MovingAverageQuery,
)


class MovingAverageTests(unittest.TestCase):
    def test_kinds(self) -> None:
        query = MovingAverageQuery(
            InputSeriesRef("company.ohlcv", "T", "close"),
            20,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            MovingAverageKind.EMA,
        )
        self.assertEqual(query.kind, MovingAverageKind.EMA)


if __name__ == "__main__":
    unittest.main()
