"""Yahoo Finance implementations of textual capabilities."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from datetime import datetime
from typing import Any, Iterable, Mapping, cast

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.textual import (
    AnnouncementCategory,
    DocumentContent,
    DocumentIdentifier,
    DocumentReference,
    DocumentSummary,
    MajorAnnouncementQuery,
    MajorAnnouncementRecord,
    MajorAnnouncementResult,
    MajorAnnouncementsCapability,
    MarketNewsCapability,
    MarketNewsQuery,
    MarketNewsRecord,
    MarketNewsResult,
    TextualCapabilities,
    TextualDataAvailability,
    TextualDataResult,
    TextualDocumentMetadata,
    TextualRequestContext,
    TextualTimeBasis,
)

from .common import (
    Clock,
    SearchFactory,
    TickerFactory,
    aware_datetime,
    call_yahoo,
    optional_text,
    source_metadata,
)


def _mapping_items(value: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, list):
        return (cast(Mapping[str, Any], item) for item in value if isinstance(item, Mapping))
    if isinstance(value, Mapping):
        for key in ("filings", "news", "items"):
            nested = value.get(key)
            if isinstance(nested, list):
                return (
                    cast(Mapping[str, Any], item) for item in nested if isinstance(item, Mapping)
                )
    return ()


def _article_fields(
    item: Mapping[str, Any], retrieved: datetime
) -> tuple[str, datetime, str, str | None, str | None, str] | None:
    nested = item.get("content")
    content = cast(Mapping[str, Any], nested) if isinstance(nested, Mapping) else item
    published_raw = (
        content.get("pubDate")
        or content.get("providerPublishTime")
        or content.get("date")
        or content.get("filingDate")
    )
    if published_raw is None:
        return None
    published = (
        datetime.fromtimestamp(float(published_raw), tz=retrieved.tzinfo)
        if isinstance(published_raw, (int, float))
        else aware_datetime(published_raw)
    )
    headline = optional_text(content.get("title") or content.get("headline") or content.get("type"))
    provider_value = content.get("provider")
    publisher = (
        optional_text(provider_value.get("displayName"))
        if isinstance(provider_value, Mapping)
        else optional_text(provider_value)
    ) or "Yahoo Finance"
    summary = optional_text(content.get("summary") or content.get("description"))
    url_value = (
        content.get("canonicalUrl")
        or content.get("clickThroughUrl")
        or content.get("link")
        or content.get("edgarUrl")
        or content.get("url")
    )
    if isinstance(url_value, Mapping):
        url_value = url_value.get("url")
    reference = optional_text(url_value)
    identifier = optional_text(content.get("id") or content.get("uuid")) or reference
    if headline is None or identifier is None or (summary is None and reference is None):
        return None
    return headline, published, publisher, summary, reference, identifier


def _content(summary: str | None, reference: str | None, source: SourceMetadata) -> DocumentContent:
    return DocumentContent(
        summary=DocumentSummary(summary, source) if summary is not None else None,
        references=(DocumentReference("url", reference),) if reference is not None else (),
    )


def _record_time(metadata: TextualDocumentMetadata, basis: TextualTimeBasis) -> datetime:
    if basis is TextualTimeBasis.EVENT_AT:
        assert metadata.event_at is not None
        return metadata.event_at
    if basis is TextualTimeBasis.PUBLISHED_AT:
        return metadata.published_at
    return metadata.available_at


def _matches_request(metadata: TextualDocumentMetadata, request: TextualRequestContext) -> bool:
    value = _record_time(metadata, request.time_basis)
    return (request.start is None or value >= request.start) and (
        request.end is None or value < request.end
    )


class YahooMarketNewsCapability(MarketNewsCapability):
    def __init__(self, search_factory: SearchFactory, clock: Clock) -> None:
        self._search_factory = search_factory
        self._clock = clock

    def get_market_news(self, query: MarketNewsQuery) -> MarketNewsResult:
        terms = [value for value in (query.market, query.sector, query.topic) if value]
        search_text = " ".join(terms)
        retrieved = self._clock()
        search = call_yahoo(
            lambda: self._search_factory(
                search_text,
                max_results=0,
                news_count=100,
                lists_count=0,
                recommended=0,
                raise_errors=True,
            )
        )
        raw = getattr(search, "news", None)
        if not isinstance(raw, list):
            return self._unavailable(query, "Yahoo returned an invalid market-news response")
        source = source_metadata(lambda: retrieved)
        records: list[MarketNewsRecord] = []
        for item in _mapping_items(raw):
            fields = _article_fields(item, retrieved)
            if fields is None:
                continue
            headline, published, _publisher, summary, reference, identifier = fields
            record_source = source_metadata(lambda: retrieved, identifier)
            metadata = TextualDocumentMetadata(
                document=DocumentIdentifier("yahoo", identifier),
                source=record_source,
                published_at=published,
                available_at=published,
                event_at=published,
            )
            if not _matches_request(metadata, query.request):
                continue
            records.append(
                MarketNewsRecord(
                    metadata,
                    _content(summary, reference, record_source),
                    headline,
                )
            )
        data = TextualDataResult(
            query.request,
            source,
            TextualDataAvailability.AVAILABLE,
            tuple(records),
        )
        return MarketNewsResult(query, data)

    def _unavailable(self, query: MarketNewsQuery, reason: str) -> MarketNewsResult:
        return MarketNewsResult(
            query,
            TextualDataResult(
                query.request,
                source_metadata(self._clock),
                TextualDataAvailability.UNAVAILABLE,
                reason=reason,
            ),
        )


class YahooMajorAnnouncementsCapability(MajorAnnouncementsCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_major_announcements(self, query: MajorAnnouncementQuery) -> MajorAnnouncementResult:
        if query.entity is None or query.entity.symbol is None:
            return self._unavailable(
                query, "Yahoo major announcements require an entity with a ticker symbol"
            )
        retrieved = self._clock()
        ticker = self._ticker_factory(query.entity.symbol)
        items: list[tuple[Mapping[str, Any], AnnouncementCategory]] = []
        categories = (
            {query.category}
            if query.category is not None
            else {AnnouncementCategory.FILING, AnnouncementCategory.PRESS_RELEASE}
        )
        if (
            AnnouncementCategory.FILING in categories
            or AnnouncementCategory.REGULATORY in categories
        ):
            filings = call_yahoo(ticker.get_sec_filings)
            category = (
                query.category
                if query.category is AnnouncementCategory.REGULATORY
                else AnnouncementCategory.FILING
            )
            items.extend((item, category) for item in _mapping_items(filings))
        if (
            AnnouncementCategory.PRESS_RELEASE in categories
            or AnnouncementCategory.CORPORATE_EVENT in categories
        ):
            news = call_yahoo(lambda: ticker.get_news(count=100, tab="press releases"))
            category = (
                query.category
                if query.category is AnnouncementCategory.CORPORATE_EVENT
                else AnnouncementCategory.PRESS_RELEASE
            )
            items.extend((item, category) for item in _mapping_items(news))

        source = source_metadata(lambda: retrieved)
        records: list[MajorAnnouncementRecord] = []
        for item, category in items:
            fields = _article_fields(item, retrieved)
            if fields is None:
                continue
            headline, published, publisher, summary, reference, identifier = fields
            record_source = source_metadata(lambda: retrieved, identifier)
            metadata = TextualDocumentMetadata(
                document=DocumentIdentifier("yahoo", identifier),
                source=record_source,
                published_at=published,
                available_at=published,
                event_at=published,
                related_entities=(query.entity,),
            )
            if not _matches_request(metadata, query.request):
                continue
            records.append(
                MajorAnnouncementRecord(
                    metadata=metadata,
                    content=_content(summary, reference, record_source),
                    category=category,
                    headline=headline,
                    official_source=publisher,
                    related_entities=(query.entity,),
                )
            )
        data = TextualDataResult(
            query.request,
            source,
            TextualDataAvailability.AVAILABLE,
            tuple(records),
        )
        return MajorAnnouncementResult(query, data)

    def _unavailable(self, query: MajorAnnouncementQuery, reason: str) -> MajorAnnouncementResult:
        return MajorAnnouncementResult(
            query,
            TextualDataResult(
                query.request,
                source_metadata(self._clock),
                TextualDataAvailability.UNAVAILABLE,
                reason=reason,
            ),
        )


def yahoo_textual_capabilities(
    ticker_factory: TickerFactory, search_factory: SearchFactory, clock: Clock
) -> TextualCapabilities:
    return TextualCapabilities(
        "YahooProvider",
        (
            YahooMarketNewsCapability(search_factory, clock),
            YahooMajorAnnouncementsCapability(ticker_factory, clock),
        ),
    )


__all__ = [
    "YahooMajorAnnouncementsCapability",
    "YahooMarketNewsCapability",
    "yahoo_textual_capabilities",
]
