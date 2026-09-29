"""Shared contracts for normalized textual provider capabilities."""

# pyright: reportUnusedImport=false, reportUnsupportedDunderAll=false
"""Normalized textual-context provider capability contracts."""

from .document_identity import DocumentIdentifier, DocumentRevisionIdentifier
from .earnings_transcripts import (
    EARNINGS_TRANSCRIPTS_CAPABILITY,
    EarningsTranscriptQuery,
    EarningsTranscriptRecord,
    EarningsTranscriptResult,
    EarningsTranscriptsCapability,
    TranscriptSection,
)
from .major_announcements import (
    MAJOR_ANNOUNCEMENTS_CAPABILITY,
    AnnouncementCategory,
    MajorAnnouncementQuery,
    MajorAnnouncementRecord,
    MajorAnnouncementResult,
    MajorAnnouncementsCapability,
)
from .market_news import (
    MARKET_NEWS_CAPABILITY,
    MarketNewsCapability,
    MarketNewsQuery,
    MarketNewsRecord,
    MarketNewsResult,
)
from .textual_capabilities import TextualCapabilities
from .textual_data import (
    DocumentContent,
    DocumentReference,
    DocumentSummary,
    OriginalDocumentText,
    OriginalTextCompleteness,
    RelatedEntity,
    TextualDataAvailability,
    TextualDataResult,
    TextualDocumentMetadata,
    TextualDocumentRecord,
    TextualRequestContext,
    TextualTimeBasis,
    TextualTopic,
)

__all__ = [name for name in globals() if not name.startswith("_")]
