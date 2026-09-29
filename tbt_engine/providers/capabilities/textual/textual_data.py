import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generic, Protocol, TypeVar

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.textual.document_identity import (
    DocumentIdentifier,
    DocumentRevisionIdentifier,
)

_NORMALIZED_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _optional_text(value: str | None, label: str) -> str | None:
    normalized = value.strip() if value is not None else None
    if normalized == "":
        raise ValueError(f"{label} must not be empty")
    return normalized


def _normalized_name(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not _NORMALIZED_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(f"{label} is invalid")
    return normalized


@dataclass(frozen=True, slots=True)
class RelatedEntity:
    """Normalized relationship between a document and a named entity."""

    kind: str
    namespace: str | None = None
    value: str | None = None
    display_name: str | None = None
    symbol: str | None = None
    role: str | None = None

    def __post_init__(self) -> None:
        kind = _normalized_name(self.kind, "Related entity kind")
        namespace = (
            _normalized_name(self.namespace, "Related entity namespace")
            if self.namespace is not None
            else None
        )
        value = _optional_text(self.value, "Related entity identifier value")
        display_name = _optional_text(self.display_name, "Related entity display name")
        symbol = _optional_text(self.symbol, "Related entity symbol")
        role = (
            _normalized_name(self.role, "Related entity relationship role")
            if self.role is not None
            else None
        )

        if (namespace is None) != (value is None):
            raise ValueError("Related entity namespace and value must be supplied together")
        if namespace is None and symbol is None:
            raise ValueError("Related entity identity requires a namespace/value pair or a symbol")

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "role", role)


def _entity_identity(entity: RelatedEntity) -> tuple[str, str, str, str]:
    return (
        entity.kind,
        entity.namespace or "",
        entity.value or entity.symbol or "",
        entity.role or "",
    )


def _entity_sort_key(entity: RelatedEntity) -> tuple[str, ...]:
    return (*_entity_identity(entity), entity.symbol or "", entity.display_name or "")


@dataclass(frozen=True, slots=True)
class TextualTopic:
    """Normalized document topic with optional source-taxonomy provenance."""

    label: str
    namespace: str | None = None
    original_label: str | None = None

    def __post_init__(self) -> None:
        label = " ".join(self.label.split()).lower()
        namespace = (
            _normalized_name(self.namespace, "Topic namespace")
            if self.namespace is not None
            else None
        )
        original_label = _optional_text(self.original_label, "Topic original label or code")
        if not label:
            raise ValueError("Topic normalized label must not be empty")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "original_label", original_label)


def _topic_identity(topic: TextualTopic) -> tuple[str, str]:
    return (topic.namespace or "", topic.label)


def _topic_sort_key(topic: TextualTopic) -> tuple[str, str, str]:
    return (*_topic_identity(topic), topic.original_label or "")


class OriginalTextCompleteness(str, Enum):
    """Whether represented original text contains the complete source document."""

    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class OriginalDocumentText:
    """Original source text, never a provider- or model-generated summary."""

    text: str
    completeness: OriginalTextCompleteness = OriginalTextCompleteness.COMPLETE
    language: str | None = None
    format: str | None = None
    incomplete_reason: str | None = None

    def __post_init__(self) -> None:
        language = _optional_text(self.language, "Original document language")
        format_name = _optional_text(self.format, "Original document format")
        incomplete_reason = _optional_text(
            self.incomplete_reason, "Incomplete original document reason"
        )
        if not self.text.strip():
            raise ValueError("Original document text must not be empty")
        if self.completeness is OriginalTextCompleteness.COMPLETE:
            if incomplete_reason is not None:
                raise ValueError("Complete original text must not include an incomplete reason")
        elif incomplete_reason is None:
            raise ValueError("Partial original text requires an incomplete reason")

        object.__setattr__(self, "language", language)
        object.__setattr__(self, "format", format_name)
        object.__setattr__(self, "incomplete_reason", incomplete_reason)


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    """Provider- or publisher-supplied summary with its own provenance."""

    text: str
    source: SourceMetadata

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Document summary must not be empty")


@dataclass(frozen=True, order=True, slots=True)
class DocumentReference:
    """Non-empty reference expected to locate or retrieve a document."""

    kind: str
    value: str

    def __post_init__(self) -> None:
        kind = _normalized_name(self.kind, "Document reference kind")
        value = self.value.strip()
        if not value:
            raise ValueError("Document reference value must not be empty")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class DocumentContent:
    """Distinct original, summary, and retrievable document surfaces."""

    original_text: OriginalDocumentText | None = None
    summary: DocumentSummary | None = None
    references: tuple[DocumentReference, ...] = ()

    def __post_init__(self) -> None:
        references = tuple(sorted(self.references))
        if len(references) != len(set(references)):
            raise ValueError("Document content references must not contain duplicates")
        if self.original_text is None and self.summary is None and not references:
            raise ValueError("Document content requires at least one usable surface")
        object.__setattr__(self, "references", references)


@dataclass(frozen=True, slots=True)
class TextualDocumentMetadata:
    """Shared identity, timing, provenance, and classification for a document."""

    document: DocumentIdentifier
    source: SourceMetadata
    published_at: datetime
    available_at: datetime
    revision: DocumentRevisionIdentifier | None = None
    event_at: datetime | None = None
    related_entities: tuple[RelatedEntity, ...] = ()
    topics: tuple[TextualTopic, ...] = ()

    def __post_init__(self) -> None:
        if not _is_aware(self.published_at):
            raise ValueError("Document publication time must be timezone-aware")
        if not _is_aware(self.available_at):
            raise ValueError("Document availability time must be timezone-aware")
        if self.available_at < self.published_at:
            raise ValueError("Document availability time must not precede publication time")
        if self.event_at is not None and not _is_aware(self.event_at):
            raise ValueError("Document event time must be timezone-aware")

        entities = tuple(sorted(self.related_entities, key=_entity_sort_key))
        entity_identities = [_entity_identity(entity) for entity in entities]
        if len(entity_identities) != len(set(entity_identities)):
            raise ValueError("Document related entities must not contain duplicate identities")

        topics = tuple(sorted(self.topics, key=_topic_sort_key))
        topic_identities = [_topic_identity(topic) for topic in topics]
        if len(topic_identities) != len(set(topic_identities)):
            raise ValueError("Document topics must not contain duplicate identities")

        object.__setattr__(self, "related_entities", entities)
        object.__setattr__(self, "topics", topics)


class TextualTimeBasis(str, Enum):
    """Document timestamp controlling a textual query's filtering and ordering."""

    EVENT_AT = "event_at"
    PUBLISHED_AT = "published_at"
    AVAILABLE_AT = "available_at"


@dataclass(frozen=True, slots=True)
class TextualRequestContext:
    """Immutable shared filtering context extended by frozen leaf query types."""

    time_basis: TextualTimeBasis
    start: datetime | None = None
    end: datetime | None = None

    def __post_init__(self) -> None:
        if self.start is not None and not _is_aware(self.start):
            raise ValueError("Textual request start time must be timezone-aware")
        if self.end is not None and not _is_aware(self.end):
            raise ValueError("Textual request end time must be timezone-aware")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("Textual request end must be later than its start")


class TextualDocumentRecord(Protocol):
    """Structural contract implemented by every normalized textual record."""

    @property
    def metadata(self) -> TextualDocumentMetadata:
        """Return the record's shared textual metadata."""
        ...


T = TypeVar("T", bound=TextualDocumentRecord)


class TextualDataAvailability(str, Enum):
    """Coverage status for a successful textual-capability request."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


def _record_time(record: TextualDocumentRecord, basis: TextualTimeBasis) -> datetime:
    metadata = record.metadata
    if basis is TextualTimeBasis.EVENT_AT:
        if metadata.event_at is None:
            raise ValueError("Event-time textual results require an event time on every record")
        return metadata.event_at
    if basis is TextualTimeBasis.PUBLISHED_AT:
        return metadata.published_at
    return metadata.available_at


def _record_identity(
    record: TextualDocumentRecord,
) -> tuple[DocumentIdentifier, DocumentRevisionIdentifier | None]:
    return (record.metadata.document, record.metadata.revision)


def _record_sort_key(
    record: TextualDocumentRecord, basis: TextualTimeBasis
) -> tuple[datetime, str, str, str, str]:
    document = record.metadata.document
    revision = record.metadata.revision
    return (
        _record_time(record, basis),
        document.namespace,
        document.value,
        revision.namespace if revision is not None else "",
        revision.value if revision is not None else "",
    )


@dataclass(frozen=True, slots=True)
class TextualDataResult(Generic[T]):
    """Normalized textual result with explicit coverage and stable ordering."""

    request: TextualRequestContext
    source: SourceMetadata
    availability: TextualDataAvailability
    records: tuple[T, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        reason = self.reason.strip() if self.reason is not None else None
        records = tuple(
            sorted(
                self.records, key=lambda record: _record_sort_key(record, self.request.time_basis)
            )
        )

        if reason == "":
            raise ValueError("Textual data availability reason must not be empty")
        if self.availability is TextualDataAvailability.AVAILABLE:
            if reason is not None:
                raise ValueError("Available textual data must not include a reason")
        elif self.availability is TextualDataAvailability.PARTIAL:
            if not records or reason is None:
                raise ValueError("Partial textual data requires records and a reason")
        elif reason is None or records:
            raise ValueError("Unavailable textual data requires a reason and no records")

        seen: set[tuple[DocumentIdentifier, DocumentRevisionIdentifier | None]] = set()
        for record in records:
            record_time = _record_time(record, self.request.time_basis)
            if self.request.start is not None and record_time < self.request.start:
                raise ValueError("Textual result record precedes the requested time range")
            if self.request.end is not None and record_time >= self.request.end:
                raise ValueError("Textual result record falls outside the requested time range")

            identity = _record_identity(record)
            if identity in seen:
                raise ValueError(
                    "Textual result contains a duplicate document identity and revision"
                )
            seen.add(identity)

        object.__setattr__(self, "records", records)
        object.__setattr__(self, "reason", reason)


__all__ = [
    "DocumentContent",
    "DocumentReference",
    "DocumentSummary",
    "OriginalDocumentText",
    "OriginalTextCompleteness",
    "RelatedEntity",
    "TextualDataAvailability",
    "TextualDataResult",
    "TextualDocumentMetadata",
    "TextualDocumentRecord",
    "TextualRequestContext",
    "TextualTimeBasis",
    "TextualTopic",
]
