import unittest
from datetime import datetime, timezone

from tbt_engine.providers.capabilities.derived.inputs import InputSeriesRef
from tbt_engine.providers.capabilities.derived.volatility import (
    VolatilityQuery,
    VolatilityReturnMethod,
)


class VolatilityTests(unittest.TestCase):
    def test_query(self) -> None:
        q = VolatilityQuery(
            InputSeriesRef("company.ohlcv", "T", "close"),
            20,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(q.return_method, VolatilityReturnMethod.LOG)


if __name__ == "__main__":
    unittest.main()
