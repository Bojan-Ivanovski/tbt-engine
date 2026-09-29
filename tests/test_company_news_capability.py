import unittest
from datetime import datetime, timedelta, timezone

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier
from tbt_engine.providers.capabilities.company.company_news import (
    CompanyNewsQuery,
    CompanyNewsRecord,
    CompanyNewsResult,
    NewsDocumentId,
)


class CompanyNewsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = CompanyIdentifier("ticker", "TEST", market="XNAS")
        self.source = SourceMetadata("memory", "news", datetime(2026, 1, 2, tzinfo=timezone.utc))

    def record(self, hour: int, value: str) -> CompanyNewsRecord:
        published = datetime(2026, 1, 1, hour, tzinfo=timezone.utc)
        return CompanyNewsRecord(
            CompanyDataMetadata(self.company, self.source, published, published),
            NewsDocumentId("publisher", value),
            published,
            "Publisher",
            "Headline",
            reference="https://example.test/" + value,
        )

    def test_result_and_identity(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        query = CompanyNewsQuery(self.company, start, end)
        result = CompanyNewsResult(
            query,
            CompanyDataResult(
                self.company, self.source, CompanyDataAvailability.AVAILABLE, (self.record(1, "a"),)
            ),
        )
        self.assertEqual(result.records[0].document.value, "a")

    def test_invalid_query(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            CompanyNewsQuery(self.company, datetime(2026, 1, 1), datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
