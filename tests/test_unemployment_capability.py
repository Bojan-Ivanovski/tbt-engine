import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.macro.macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
    MacroUnitMetadata,
    ObservationPeriod,
    SeasonalAdjustmentStatus,
)
from tbt_engine.providers.capabilities.macro.macro_identifier import MacroSeriesIdentifier
from tbt_engine.providers.capabilities.macro.unemployment import (
    UnemploymentMeasure,
    UnemploymentQuery,
    UnemploymentRecord,
    UnemploymentResult,
)


class UnemploymentTests(unittest.TestCase):
    def test_unemployment(self) -> None:
        series = MacroSeriesIdentifier("fred", "UNRATE")
        source = SourceMetadata("memory", "unemployment", datetime(2026, 1, 2, tzinfo=timezone.utc))
        period = ObservationPeriod(date(2025, 1, 1), date(2025, 2, 1))
        metadata = MacroDataMetadata(
            series,
            source,
            period,
            datetime(2025, 2, 10, tzinfo=timezone.utc),
            MacroUnitMetadata("percent"),
            SeasonalAdjustmentStatus.ADJUSTED,
        )
        record = UnemploymentRecord(
            metadata, Decimal("4.1"), UnemploymentMeasure.RATE, "civilian labor force"
        )
        result = UnemploymentResult(
            UnemploymentQuery(series, date(2025, 1, 1), date(2026, 1, 1)),
            MacroDataResult(series, source, MacroDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
