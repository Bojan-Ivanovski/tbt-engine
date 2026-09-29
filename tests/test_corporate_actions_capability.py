import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier
from tbt_engine.providers.capabilities.company.corporate_actions import *


class CorporateActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = CompanyIdentifier("ticker", "TEST", market="XNAS")
        source = SourceMetadata("memory", "actions", datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.source = source

    def metadata(self, effective_at: date) -> CompanyDataMetadata:
        return CompanyDataMetadata(self.company, self.source, effective_at)

    def test_query_and_records(self) -> None:
        query = CorporateActionsQuery(self.company, start=date(2025, 1, 1), end=date(2027, 1, 1))
        dividend = DividendRecord(
            self.metadata(date(2025, 6, 1)),
            Decimal("0.25"),
            "usd",
            ex_dividend_date=date(2025, 6, 1),
        )
        split = SplitRecord(self.metadata(date(2026, 1, 1)), 2, 1)
        result = CorporateActionsResult(
            query,
            CompanyDataResult(
                self.company,
                self.metadata(date(2025, 1, 1)).source,
                CompanyDataAvailability.AVAILABLE,
                (dividend, split),
            ),
        )
        self.assertEqual(result.records, (dividend, split))

    def test_invalid_query_and_ratio(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            CorporateActionsQuery(self.company, start=date(2026, 1, 1), end=date(2026, 1, 1))
        with self.assertRaises(ValueError):
            SplitRecord(self.metadata(date(2026, 1, 1)), 0, 1)


if __name__ == "__main__":
    unittest.main()
