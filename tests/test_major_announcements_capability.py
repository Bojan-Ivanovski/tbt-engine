import unittest

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.textual.major_announcements import (
    AnnouncementCategory,
    MajorAnnouncementQuery,
)
from tbt_engine.providers.capabilities.textual.textual_data import (
    TextualRequestContext,
    TextualTimeBasis,
)


class AnnouncementTests(unittest.TestCase):
    def test_query(self) -> None:
        q = MajorAnnouncementQuery(
            TextualRequestContext(TextualTimeBasis.PUBLISHED_AT),
            category=AnnouncementCategory.FILING,
        )
        self.assertEqual(q.category, AnnouncementCategory.FILING)

    def test_scope_required(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            MajorAnnouncementQuery(TextualRequestContext(TextualTimeBasis.PUBLISHED_AT))


if __name__ == "__main__":
    unittest.main()
