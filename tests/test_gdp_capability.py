import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.macro.gdp import (
    GDPMeasure,
    GDPPriceBasis,
    GDPQuery,
    GDPRecord,
    GDPResult,
)
from tbt_engine.providers.capabilities.macro.macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
    MacroUnitMetadata,
    ObservationPeriod,
    SeasonalAdjustmentStatus,
)
from tbt_engine.providers.capabilities.macro.macro_identifier import MacroSeriesIdentifier


class GDPTests(unittest.TestCase):
    def test_gdp(self) -> None:
        series = MacroSeriesIdentifier("fred", "GDP")
        source = SourceMetadata("memory", "gdp", datetime(2026, 1, 2, tzinfo=timezone.utc))
        period = ObservationPeriod(date(2025, 1, 1), date(2026, 1, 1))
        metadata = MacroDataMetadata(
            series,
            source,
            period,
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            MacroUnitMetadata("currency", currency="USD"),
            SeasonalAdjustmentStatus.ADJUSTED,
        )
        record = GDPRecord(metadata, Decimal("100"), GDPPriceBasis.REAL, GDPMeasure.TOTAL, True)
        result = GDPResult(
            GDPQuery(series, date(2025, 1, 1), date(2027, 1, 1)),
            MacroDataResult(series, source, MacroDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
