import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.macro.cpi import CPIQuery, CPIRecord, CPIResult, CPIValueKind
from tbt_engine.providers.capabilities.macro.macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
    MacroUnitMetadata,
    ObservationPeriod,
    SeasonalAdjustmentStatus,
)
from tbt_engine.providers.capabilities.macro.macro_identifier import MacroSeriesIdentifier


class CPITests(unittest.TestCase):
    def test_cpi(self) -> None:
        series = MacroSeriesIdentifier("fred", "CPI")
        source = SourceMetadata("memory", "cpi", datetime(2026, 1, 2, tzinfo=timezone.utc))
        period = ObservationPeriod(date(2025, 1, 1), date(2025, 2, 1))
        metadata = MacroDataMetadata(
            series,
            source,
            period,
            datetime(2025, 2, 10, tzinfo=timezone.utc),
            MacroUnitMetadata("index"),
            SeasonalAdjustmentStatus.ADJUSTED,
        )
        record = CPIRecord(metadata, Decimal("100"), CPIValueKind.INDEX)
        result = CPIResult(
            CPIQuery(series, date(2025, 1, 1), date(2026, 1, 1)),
            MacroDataResult(series, source, MacroDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
