from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum

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

MAJOR_ANNOUNCEMENTS_CAPABILITY = CapabilityId("textual.major_announcements")


class AnnouncementCategory(str, Enum):
    FILING = "filing"
    PRESS_RELEASE = "press_release"
    REGULATORY = "regulatory"
    CORPORATE_EVENT = "corporate_event"


@dataclass(frozen=True, slots=True)
class MajorAnnouncementQuery:
    request: TextualRequestContext
    category: AnnouncementCategory | None = None
    entity: RelatedEntity | None = None

    def __post_init__(self) -> None:
        if self.category is None and self.entity is None:
            raise InvalidCapabilityQueryError("Announcement query requires category or entity")


@dataclass(frozen=True, slots=True)
class MajorAnnouncementRecord:
    metadata: TextualDocumentMetadata
    content: DocumentContent
    category: AnnouncementCategory
    headline: str
    official_source: str
    related_entities: tuple[RelatedEntity, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.headline.strip()
            or not self.official_source.strip()
            or type(self.category) is not AnnouncementCategory
        ):
            raise ValueError("Announcement fields are invalid")


@dataclass(frozen=True, slots=True)
class MajorAnnouncementResult:
    query: MajorAnnouncementQuery
    data: TextualDataResult[MajorAnnouncementRecord]

    @property
    def records(self) -> tuple[MajorAnnouncementRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> TextualDataAvailability:
        return self.data.availability


class MajorAnnouncementsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return MAJOR_ANNOUNCEMENTS_CAPABILITY

    @abstractmethod
    def get_major_announcements(self, query: MajorAnnouncementQuery) -> MajorAnnouncementResult:
        raise NotImplementedError


__all__ = [
    "AnnouncementCategory",
    "MAJOR_ANNOUNCEMENTS_CAPABILITY",
    "MajorAnnouncementQuery",
    "MajorAnnouncementRecord",
    "MajorAnnouncementResult",
    "MajorAnnouncementsCapability",
]
