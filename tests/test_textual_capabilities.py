import unittest
from dataclasses import FrozenInstanceError, dataclass
from datetime import datetime, timedelta, timezone

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities import Capability, CapabilityId
from tbt_engine.providers.capabilities.textual.document_identity import (
    DocumentIdentifier,
    DocumentRevisionIdentifier,
)
from tbt_engine.providers.capabilities.textual.textual_capabilities import TextualCapabilities
from tbt_engine.providers.capabilities.textual.textual_data import (
    DocumentContent,
    DocumentReference,
    DocumentSummary,
    OriginalDocumentText,
    OriginalTextCompleteness,
    RelatedEntity,
    TextualDataAvailability,
    TextualDataResult,
    TextualDocumentMetadata,
    TextualRequestContext,
    TextualTimeBasis,
    TextualTopic,
)

MARKET_NEWS = CapabilityId("textual.market_news")


class MarketNewsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return MARKET_NEWS


class CompanyNewsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return CapabilityId("company.news")


@dataclass(frozen=True, slots=True)
class ExampleDocument:
    metadata: TextualDocumentMetadata
    content: DocumentContent


class TextualCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.published_at = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)
        self.available_at = self.published_at + timedelta(minutes=2)
        self.source = SourceMetadata(
            provider="test-provider",
            source="publisher-feed",
            retrieved_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
            source_record_id="provider-record-1",
        )

    def metadata(
        self,
        value: str,
        *,
        published_at: datetime | None = None,
        revision: DocumentRevisionIdentifier | None = None,
        event_at: datetime | None = None,
    ) -> TextualDocumentMetadata:
        publication = published_at or self.published_at
        return TextualDocumentMetadata(
            document=DocumentIdentifier("publisher", value),
            revision=revision,
            source=self.source,
            event_at=event_at,
            published_at=publication,
            available_at=publication + timedelta(minutes=2),
        )

    def record(
        self,
        value: str,
        *,
        published_at: datetime | None = None,
        revision: DocumentRevisionIdentifier | None = None,
        event_at: datetime | None = None,
    ) -> ExampleDocument:
        return ExampleDocument(
            metadata=self.metadata(
                value,
                published_at=published_at,
                revision=revision,
                event_at=event_at,
            ),
            content=DocumentContent(original_text=OriginalDocumentText("Original text")),
        )

    def test_textual_capabilities_accept_only_textual_namespace(self) -> None:
        capabilities = TextualCapabilities("provider", (MarketNewsCapability(),))

        self.assertTrue(capabilities.supports(MARKET_NEWS))
        with self.assertRaisesRegex(ValueError, "'textual.' namespace"):
            TextualCapabilities("provider", (CompanyNewsCapability(),))

    def test_document_and_revision_identity_are_explicit_and_stable(self) -> None:
        document = DocumentIdentifier(" Publisher.Archive ", " story-42 ")
        revision = DocumentRevisionIdentifier("Publisher.Archive", " revision-2 ")

        self.assertEqual(document, DocumentIdentifier("publisher.archive", "story-42"))
        self.assertEqual(revision.namespace, document.namespace)
        self.assertNotEqual(document, revision)
        for identity_type in (DocumentIdentifier, DocumentRevisionIdentifier):
            with self.assertRaises(ValueError):
                identity_type("", "value")
            with self.assertRaises(ValueError):
                identity_type("publisher", " ")

    def test_related_entities_require_qualified_identity_and_normalize_fields(self) -> None:
        entity = RelatedEntity(
            kind=" Company ",
            namespace=" LEI ",
            value=" 5493001KJTIIGC8Y1R12 ",
            display_name=" Example Corp ",
            symbol=" EXM ",
            role=" Issuer ",
        )

        self.assertEqual(entity.kind, "company")
        self.assertEqual(entity.namespace, "lei")
        self.assertEqual(entity.role, "issuer")
        with self.assertRaisesRegex(ValueError, "supplied together"):
            RelatedEntity(kind="company", namespace="lei")
        with self.assertRaisesRegex(ValueError, "requires a namespace/value pair or a symbol"):
            RelatedEntity(kind="person", display_name="Unqualified Name")

    def test_topics_preserve_original_taxonomy_label(self) -> None:
        topic = TextualTopic(
            label=" Monetary   Policy ",
            namespace=" Publisher.Topics ",
            original_label="MON_POL",
        )

        self.assertEqual(topic.label, "monetary policy")
        self.assertEqual(topic.namespace, "publisher.topics")
        self.assertEqual(topic.original_label, "MON_POL")
        with self.assertRaises(ValueError):
            TextualTopic(" ")

    def test_metadata_snapshots_and_orders_entities_and_topics(self) -> None:
        entities = [
            RelatedEntity("security", symbol="ZZZ"),
            RelatedEntity("security", symbol="AAA"),
        ]
        topics = [TextualTopic("rates"), TextualTopic("economy")]

        metadata = TextualDocumentMetadata(
            document=DocumentIdentifier("publisher", "story-1"),
            source=self.source,
            published_at=self.published_at,
            available_at=self.available_at,
            related_entities=entities,  # pyright: ignore[reportArgumentType]
            topics=topics,  # pyright: ignore[reportArgumentType]
        )
        entities.append(RelatedEntity("security", symbol="LATER"))
        topics.append(TextualTopic("later"))

        self.assertEqual([entity.symbol for entity in metadata.related_entities], ["AAA", "ZZZ"])
        self.assertEqual([topic.label for topic in metadata.topics], ["economy", "rates"])
        self.assertIsInstance(metadata.related_entities, tuple)
        self.assertIsInstance(metadata.topics, tuple)

    def test_metadata_rejects_duplicate_entity_and_topic_identities(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate identities"):
            TextualDocumentMetadata(
                document=DocumentIdentifier("publisher", "story-1"),
                source=self.source,
                published_at=self.published_at,
                available_at=self.available_at,
                related_entities=(
                    RelatedEntity("company", "lei", "id", display_name="First"),
                    RelatedEntity("company", "lei", "id", display_name="Renamed"),
                ),
            )
        with self.assertRaisesRegex(ValueError, "duplicate identities"):
            TextualDocumentMetadata(
                document=DocumentIdentifier("publisher", "story-1"),
                source=self.source,
                published_at=self.published_at,
                available_at=self.available_at,
                topics=(
                    TextualTopic("economy", original_label="ECON"),
                    TextualTopic("Economy", original_label="economy"),
                ),
            )

    def test_document_times_are_distinct_and_timezone_aware(self) -> None:
        event_at = self.published_at + timedelta(days=1)
        metadata = TextualDocumentMetadata(
            document=DocumentIdentifier("publisher", "story-1"),
            source=self.source,
            event_at=event_at,
            published_at=self.published_at,
            available_at=self.available_at,
        )

        self.assertEqual(metadata.event_at, event_at)
        self.assertNotEqual(metadata.available_at, metadata.source.retrieved_at)
        with self.assertRaisesRegex(ValueError, "publication time"):
            TextualDocumentMetadata(
                document=metadata.document,
                source=self.source,
                published_at=datetime(2026, 9, 28),
                available_at=self.available_at,
            )
        with self.assertRaisesRegex(ValueError, "must not precede"):
            TextualDocumentMetadata(
                document=metadata.document,
                source=self.source,
                published_at=self.published_at,
                available_at=self.published_at - timedelta(seconds=1),
            )
        with self.assertRaisesRegex(ValueError, "event time"):
            TextualDocumentMetadata(
                document=metadata.document,
                source=self.source,
                event_at=datetime(2026, 9, 28),
                published_at=self.published_at,
                available_at=self.available_at,
            )

    def test_content_keeps_original_summary_and_reference_surfaces_distinct(self) -> None:
        references = [
            DocumentReference("url", "https://example.test/story"),
            DocumentReference("content_endpoint", "urn:content:story-1"),
        ]
        content = DocumentContent(
            original_text=OriginalDocumentText(
                "  Original publisher text\n",
                language="en",
                format="text/plain",
            ),
            summary=DocumentSummary("Publisher abstract", self.source),
            references=references,  # pyright: ignore[reportArgumentType]
        )
        references.append(DocumentReference("url", "https://example.test/later"))

        original_text = content.original_text
        summary = content.summary
        self.assertIsNotNone(original_text)
        self.assertIsNotNone(summary)
        assert original_text is not None
        assert summary is not None
        self.assertEqual(original_text.text, "  Original publisher text\n")
        self.assertEqual(summary.text, "Publisher abstract")
        self.assertEqual(len(content.references), 2)
        self.assertIsInstance(content.references, tuple)
        with self.assertRaisesRegex(ValueError, "at least one usable surface"):
            DocumentContent()
        with self.assertRaisesRegex(ValueError, "must not contain duplicates"):
            DocumentContent(
                references=(
                    DocumentReference("url", "https://example.test/story"),
                    DocumentReference("url", "https://example.test/story"),
                )
            )

    def test_partial_original_text_is_explicit(self) -> None:
        partial = OriginalDocumentText(
            "Excerpt",
            completeness=OriginalTextCompleteness.PARTIAL,
            incomplete_reason="Provider truncates long documents",
        )

        self.assertEqual(partial.completeness, OriginalTextCompleteness.PARTIAL)
        with self.assertRaisesRegex(ValueError, "requires an incomplete reason"):
            OriginalDocumentText("Excerpt", completeness=OriginalTextCompleteness.PARTIAL)
        with self.assertRaisesRegex(ValueError, "must not include"):
            OriginalDocumentText("Complete", incomplete_reason="Contradiction")
        with self.assertRaises(ValueError):
            DocumentSummary(" ", self.source)

    def test_request_context_is_frozen_and_requires_aware_ordered_bounds(self) -> None:
        request = TextualRequestContext(
            TextualTimeBasis.PUBLISHED_AT,
            start=self.published_at,
            end=self.published_at + timedelta(days=1),
        )

        with self.assertRaises(FrozenInstanceError):
            request.start = None  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(ValueError):
            TextualRequestContext(TextualTimeBasis.PUBLISHED_AT, datetime(2026, 9, 28))
        with self.assertRaises(ValueError):
            TextualRequestContext(
                TextualTimeBasis.PUBLISHED_AT,
                self.published_at,
                self.published_at,
            )

    def test_result_snapshots_orders_and_validates_document_identity_revisions(self) -> None:
        later = self.published_at + timedelta(hours=2)
        records: list[ExampleDocument] = [
            self.record("b", published_at=later),
            self.record("a"),
        ]
        result = TextualDataResult[ExampleDocument](
            request=TextualRequestContext(TextualTimeBasis.PUBLISHED_AT),
            source=self.source,
            availability=TextualDataAvailability.AVAILABLE,
            records=records,  # pyright: ignore[reportArgumentType]
        )
        records.append(self.record("later-mutation"))

        self.assertEqual([record.metadata.document.value for record in result.records], ["a", "b"])
        self.assertIsInstance(result.records, tuple)

        first_revision = DocumentRevisionIdentifier("publisher", "r1")
        second_revision = DocumentRevisionIdentifier("publisher", "r2")
        revised = TextualDataResult(
            request=TextualRequestContext(TextualTimeBasis.PUBLISHED_AT),
            source=self.source,
            availability=TextualDataAvailability.AVAILABLE,
            records=(
                self.record("same", revision=second_revision),
                self.record("same", revision=first_revision),
            ),
        )
        self.assertEqual(
            [record.metadata.revision for record in revised.records],
            [first_revision, second_revision],
        )

        with self.assertRaisesRegex(ValueError, "duplicate document identity and revision"):
            TextualDataResult(
                request=TextualRequestContext(TextualTimeBasis.PUBLISHED_AT),
                source=self.source,
                availability=TextualDataAvailability.AVAILABLE,
                records=(self.record("duplicate"), self.record("duplicate")),
            )

    def test_result_enforces_request_time_basis_and_bounds(self) -> None:
        request = TextualRequestContext(
            TextualTimeBasis.EVENT_AT,
            start=self.published_at,
            end=self.published_at + timedelta(days=1),
        )

        in_scope = self.record("event", event_at=self.published_at + timedelta(hours=1))
        result = TextualDataResult(
            request=request,
            source=self.source,
            availability=TextualDataAvailability.AVAILABLE,
            records=(in_scope,),
        )
        self.assertEqual(result.records, (in_scope,))
        with self.assertRaisesRegex(ValueError, "require an event time"):
            TextualDataResult(
                request=request,
                source=self.source,
                availability=TextualDataAvailability.AVAILABLE,
                records=(self.record("missing-event"),),
            )
        with self.assertRaisesRegex(ValueError, "outside the requested time range"):
            TextualDataResult(
                request=request,
                source=self.source,
                availability=TextualDataAvailability.AVAILABLE,
                records=(
                    self.record("at-exclusive-end", event_at=self.published_at + timedelta(days=1)),
                ),
            )

    def test_result_availability_states_are_exact(self) -> None:
        request = TextualRequestContext(TextualTimeBasis.AVAILABLE_AT)
        available = TextualDataResult[ExampleDocument](
            request=request,
            source=self.source,
            availability=TextualDataAvailability.AVAILABLE,
        )
        partial = TextualDataResult(
            request=request,
            source=self.source,
            availability=TextualDataAvailability.PARTIAL,
            records=(self.record("partial"),),
            reason="Only summaries are available",
        )
        unavailable = TextualDataResult[ExampleDocument](
            request=request,
            source=self.source,
            availability=TextualDataAvailability.UNAVAILABLE,
            reason="Provider has no coverage",
        )

        self.assertEqual(available.records, ())
        self.assertEqual(partial.reason, "Only summaries are available")
        self.assertEqual(unavailable.records, ())
        with self.assertRaises(ValueError):
            TextualDataResult[ExampleDocument](
                request=request,
                source=self.source,
                availability=TextualDataAvailability.PARTIAL,
                reason="No usable records",
            )
        with self.assertRaises(ValueError):
            TextualDataResult(
                request=request,
                source=self.source,
                availability=TextualDataAvailability.UNAVAILABLE,
                records=(self.record("contradiction"),),
                reason="Contradictory result",
            )


if __name__ == "__main__":
    unittest.main()
