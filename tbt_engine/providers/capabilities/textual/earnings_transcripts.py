from abc import abstractmethod
from dataclasses import dataclass
from datetime import date

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.textual.textual_data import (
    DocumentContent,
    RelatedEntity,
    TextualDataAvailability,
    TextualDataResult,
    TextualDocumentMetadata,
    TextualRequestContext,
)

EARNINGS_TRANSCRIPTS_CAPABILITY = CapabilityId("textual.earnings_transcripts")


@dataclass(frozen=True, slots=True)
class EarningsTranscriptQuery:
    request: TextualRequestContext
    company: RelatedEntity
    period_start: date | None = None
    period_end: date | None = None

    def __post_init__(self) -> None:
        if self.company.kind != "company":
            raise InvalidCapabilityQueryError("Transcript company entity is required")
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_start > self.period_end
        ):
            raise InvalidCapabilityQueryError("Transcript period bounds are invalid")


@dataclass(frozen=True, slots=True)
class TranscriptSection:
    heading: str
    content: str
    order: int

    def __post_init__(self) -> None:
        if not self.heading.strip() or not self.content.strip() or self.order < 0:
            raise ValueError("Transcript section is invalid")


@dataclass(frozen=True, slots=True)
class EarningsTranscriptRecord:
    metadata: TextualDocumentMetadata
    content: DocumentContent
    reporting_start: date
    reporting_end: date
    sections: tuple[TranscriptSection, ...] = ()

    def __post_init__(self) -> None:
        if self.reporting_start > self.reporting_end:
            raise ValueError("Transcript reporting period is invalid")
        if tuple(section.order for section in self.sections) != tuple(
            sorted(section.order for section in self.sections)
        ):
            raise ValueError("Transcript sections must be ordered")


@dataclass(frozen=True, slots=True)
class EarningsTranscriptResult:
    query: EarningsTranscriptQuery
    data: TextualDataResult[EarningsTranscriptRecord]

    @property
    def records(self) -> tuple[EarningsTranscriptRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> TextualDataAvailability:
        return self.data.availability


class EarningsTranscriptsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return EARNINGS_TRANSCRIPTS_CAPABILITY

    @abstractmethod
    def get_earnings_transcripts(self, query: EarningsTranscriptQuery) -> EarningsTranscriptResult:
        raise NotImplementedError


__all__ = [
    "EARNINGS_TRANSCRIPTS_CAPABILITY",
    "EarningsTranscriptQuery",
    "EarningsTranscriptRecord",
    "EarningsTranscriptResult",
    "EarningsTranscriptsCapability",
    "TranscriptSection",
]
