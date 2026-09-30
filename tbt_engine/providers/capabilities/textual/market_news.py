from abc import abstractmethod
from dataclasses import dataclass

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.textual.textual_data import (
    DocumentContent,
    TextualDataAvailability,
    TextualDataResult,
    TextualDocumentMetadata,
    TextualRequestContext,
)

MARKET_NEWS_CAPABILITY = CapabilityId("textual.market_news")


@dataclass(frozen=True, slots=True)
class MarketNewsQuery:
    request: TextualRequestContext
    market: str | None = None
    sector: str | None = None
    topic: str | None = None

    def __post_init__(self) -> None:
        if all(value is None for value in (self.market, self.sector, self.topic)):
            raise InvalidCapabilityQueryError("Market-news query requires a scope")


@dataclass(frozen=True, slots=True)
class MarketNewsRecord:
    metadata: TextualDocumentMetadata
    content: DocumentContent
    headline: str

    def __post_init__(self) -> None:
        if not self.headline.strip():
            raise ValueError("Market-news headline is required")


@dataclass(frozen=True, slots=True)
class MarketNewsResult:
    query: MarketNewsQuery
    data: TextualDataResult[MarketNewsRecord]

    @property
    def records(self) -> tuple[MarketNewsRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> TextualDataAvailability:
        return self.data.availability


class MarketNewsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return MARKET_NEWS_CAPABILITY

    @abstractmethod
    def get_market_news(self, query: MarketNewsQuery) -> MarketNewsResult:
        raise NotImplementedError


__all__ = [
    "MARKET_NEWS_CAPABILITY",
    "MarketNewsCapability",
    "MarketNewsQuery",
    "MarketNewsRecord",
    "MarketNewsResult",
]
