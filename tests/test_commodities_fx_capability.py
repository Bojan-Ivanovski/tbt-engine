import unittest
from datetime import datetime, timezone

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.macro.commodities_fx import (
    CommoditiesFXQuery,
    CommoditiesFXRecord,
    CommoditiesFXResult,
    InstrumentKind,
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


class CommoditiesFXTests(unittest.TestCase):
    def test_fx(self) -> None:
        series = MacroSeriesIdentifier("instrument", "EURUSD")
        source = SourceMetadata("memory", "fx", datetime(2026, 1, 2, tzinfo=timezone.utc))
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        metadata = MacroDataMetadata(
            series,
            source,
            ObservationPeriod(stamp.date(), datetime(2026, 1, 2).date()),
            stamp,
            MacroUnitMetadata("USD/EUR"),
            SeasonalAdjustmentStatus.NOT_APPLICABLE,
        )
        record = CommoditiesFXRecord(metadata, InstrumentKind.FX, 1.1, "quote", "USD", "EUR")
        result = CommoditiesFXResult(
            CommoditiesFXQuery(series, stamp, datetime(2026, 1, 2, tzinfo=timezone.utc)),
            MacroDataResult(series, source, MacroDataAvailability.AVAILABLE, (record,)),
        )
        self.assertEqual(result.records, (record,))


if __name__ == "__main__":
    unittest.main()
