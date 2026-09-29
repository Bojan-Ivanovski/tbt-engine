import unittest
from datetime import date

from tbt_engine.providers.capabilities.textual.earnings_transcripts import (
    EarningsTranscriptQuery,
    TranscriptSection,
)
from tbt_engine.providers.capabilities.textual.textual_data import (
    RelatedEntity,
    TextualRequestContext,
    TextualTimeBasis,
)


class TranscriptTests(unittest.TestCase):
    def test_query_and_sections(self) -> None:
        query = EarningsTranscriptQuery(
            TextualRequestContext(TextualTimeBasis.PUBLISHED_AT),
            RelatedEntity("company", "lei", "x"),
            date(2025, 1, 1),
            date(2025, 3, 31),
        )
        self.assertEqual(query.company.kind, "company")
        self.assertEqual(TranscriptSection("Q&A", "Text", 0).order, 0)


if __name__ == "__main__":
    unittest.main()
