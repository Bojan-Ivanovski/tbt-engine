from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier

COMPANY_NEWS_CAPABILITY = CapabilityId("company.news")


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


@dataclass(frozen=True, order=True, slots=True)
class NewsDocumentId:
    namespace: str
    value: str

    def __post_init__(self) -> None:
        namespace = self.namespace.strip().lower()
        value = self.value.strip()
        if not namespace or not value:
            raise ValueError("News document identity must not be empty")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)


class SentimentScale(str, Enum):
    UNKNOWN = "unknown"
    NEGATIVE_TO_POSITIVE = "negative_to_positive"
    SCORE = "score"


@dataclass(frozen=True, slots=True)
class NewsSentiment:
    value: float
    scale: SentimentScale
    model: str | None = None

    def __post_init__(self) -> None:
        if self.value != self.value:
            raise ValueError("News sentiment must be numeric")
        if self.model is not None and not self.model.strip():
            raise ValueError("News sentiment model must not be empty")


@dataclass(frozen=True, slots=True)
class CompanyNewsQuery:
    company: CompanyIdentifier
    start: datetime | None = None
    end: datetime | None = None
    topics: frozenset[str] = frozenset()
    limit: int | None = None

    def __post_init__(self) -> None:
        if type(self.company) is not CompanyIdentifier:
            raise InvalidCapabilityQueryError("Company-news company is invalid")
        if any(value is not None and not _aware(value) for value in (self.start, self.end)):
            raise InvalidCapabilityQueryError("Company-news bounds must be timezone-aware")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Company-news start must precede end")
        if self.limit is not None and (isinstance(self.limit, bool) or self.limit <= 0):
            raise InvalidCapabilityQueryError("Company-news limit must be positive")
        normalized = frozenset(topic.strip().lower() for topic in self.topics)
        if any(not topic for topic in normalized):
            raise InvalidCapabilityQueryError("Company-news topics must not be empty")
        object.__setattr__(self, "topics", normalized)


@dataclass(frozen=True, slots=True)
class CompanyNewsRecord:
    metadata: CompanyDataMetadata
    document: NewsDocumentId
    published_at: datetime
    publisher: str
    headline: str
    summary: str | None = None
    text: str | None = None
    reference: str | None = None
    related_companies: tuple[CompanyIdentifier, ...] = ()
    topics: tuple[str, ...] = ()
    sentiment: NewsSentiment | None = None

    def __post_init__(self) -> None:
        if not _aware(self.published_at):
            raise ValueError("Company-news publication time must be timezone-aware")
        if not self.publisher.strip() or not self.headline.strip():
            raise ValueError("Company-news publisher and headline are required")
        if all(
            value is None or not value.strip()
            for value in (self.text, self.summary, self.reference)
        ):
            raise ValueError("Company-news requires text, summary, or reference")
        topics = tuple(sorted({topic.strip().lower() for topic in self.topics}))
        if any(not topic for topic in topics):
            raise ValueError("Company-news topics must not be empty")
        companies = tuple(sorted(set(self.related_companies)))
        object.__setattr__(self, "topics", topics)
        object.__setattr__(self, "related_companies", companies)


@dataclass(frozen=True, slots=True)
class CompanyNewsResult:
    query: CompanyNewsQuery
    data: CompanyDataResult[CompanyNewsRecord]

    def __post_init__(self) -> None:
        if self.data.company != self.query.company:
            raise ValueError("Company-news company must match query")
        seen: set[tuple[NewsDocumentId, object]] = set()
        previous: datetime | None = None
        for record in self.data.records:
            if record.metadata.company != self.query.company:
                raise ValueError("Company-news record company must match query")
            if self.query.start is not None and record.published_at < self.query.start:
                raise ValueError("Company-news record precedes query start")
            if self.query.end is not None and record.published_at >= self.query.end:
                raise ValueError("Company-news record is not before exclusive query end")
            key = (record.document, record.metadata.source.source_record_id)
            if key in seen:
                raise ValueError("Company-news documents must be unique")
            seen.add(key)
            if previous is not None and (record.published_at, record.document) <= (
                previous,
                record.document,
            ):
                raise ValueError("Company-news records must be ascending and unique")
            previous = record.published_at

    @property
    def records(self) -> tuple[CompanyNewsRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> CompanyDataAvailability:
        return self.data.availability


class CompanyNewsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return COMPANY_NEWS_CAPABILITY

    @abstractmethod
    def get_company_news(self, query: CompanyNewsQuery) -> CompanyNewsResult:
        raise NotImplementedError


__all__ = [
    "COMPANY_NEWS_CAPABILITY",
    "CompanyNewsCapability",
    "CompanyNewsQuery",
    "CompanyNewsRecord",
    "CompanyNewsResult",
    "NewsDocumentId",
    "NewsSentiment",
    "SentimentScale",
]
