"""Yahoo Finance implementations of company-scoped capabilities."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

import re
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, cast

import pandas as pd

from tbt_engine.core.errors import ProviderError
from tbt_engine.providers.capabilities.company import (
    AccountingBasis,
    CompanyCapabilities,
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
    CompanyIdentifier,
    CompanyNewsCapability,
    CompanyNewsQuery,
    CompanyNewsRecord,
    CompanyNewsResult,
    CompanyProfileRecord,
    CorporateActionsCapability,
    CorporateActionsQuery,
    CorporateActionsResult,
    CorporateActionType,
    DividendRecord,
    EarningsActual,
    EarningsCapability,
    EarningsEstimate,
    EarningsEvent,
    EarningsMetricId,
    EarningsQuery,
    EarningsReportingPeriod,
    EarningsResult,
    EarningsSurprise,
    EarningsTimingStatus,
    FinancialStatementRecord,
    FinancialStatementType,
    FiscalPeriod,
    FiscalPeriodLabel,
    FundamentalMetricId,
    FundamentalRecordType,
    FundamentalsCapability,
    FundamentalsQuery,
    FundamentalsResult,
    OHLCVAdjustment,
    OHLCVBar,
    OHLCVCapability,
    OHLCVQuery,
    OHLCVResult,
    ReportingPeriod,
    ReportingPeriodType,
    SplitRecord,
)
from tbt_engine.providers.capabilities.company.company_news import NewsDocumentId

from .common import (
    Clock,
    TickerFactory,
    aware_datetime,
    call_yahoo,
    dataframe,
    date_only,
    decimal_value,
    in_date_range,
    in_datetime_range,
    optional_text,
    response_mapping,
    source_metadata,
    symbol_text,
    yahoo_symbol,
)

_INTERVALS = {
    "1m",
    "2m",
    "5m",
    "15m",
    "30m",
    "60m",
    "90m",
    "1h",
    "1d",
    "5d",
    "1wk",
    "1mo",
    "3mo",
}
_METRIC_PARTS = re.compile(r"(?<!^)(?=[A-Z])|[^A-Za-z0-9]+")


def _company_symbol(company: CompanyIdentifier) -> str | tuple[str, str] | None:
    return yahoo_symbol(company.scheme, company.value, company.market)


def _metric_id(value: object) -> FundamentalMetricId:
    parts = [part.lower() for part in _METRIC_PARTS.split(str(value)) if part]
    normalized = "_".join(parts) or "unknown"
    if not normalized[0].isalpha():
        normalized = f"metric_{normalized}"
    return FundamentalMetricId(normalized)


def _unavailable_company(
    company: CompanyIdentifier, clock: Clock, reason: str
) -> CompanyDataResult[Any]:
    return CompanyDataResult(
        company=company,
        source=source_metadata(clock),
        availability=CompanyDataAvailability.UNAVAILABLE,
        reason=reason,
    )


class YahooOHLCVCapability(OHLCVCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_ohlcv(self, query: OHLCVQuery) -> OHLCVResult:
        symbol = _company_symbol(query.company)
        interval = str(query.interval)
        if symbol is None:
            data = _unavailable_company(
                query.company, self._clock, "Yahoo requires a ticker identity"
            )
            return OHLCVResult(query, data)
        if interval not in _INTERVALS:
            data = _unavailable_company(
                query.company, self._clock, f"Yahoo does not support interval {interval}"
            )
            return OHLCVResult(query, data)
        adjustment = query.adjustment or OHLCVAdjustment.UNADJUSTED
        if adjustment is OHLCVAdjustment.SPLIT_ADJUSTED:
            data = _unavailable_company(
                query.company,
                self._clock,
                "Yahoo does not expose split-only adjusted bars",
            )
            return OHLCVResult(query, data)

        retrieved = self._clock()
        ticker = self._ticker_factory(symbol)
        frame = dataframe(
            call_yahoo(
                lambda: ticker.history(
                    interval=interval,
                    start=query.start,
                    end=query.end,
                    auto_adjust=adjustment is OHLCVAdjustment.SPLIT_AND_DIVIDEND_ADJUSTED,
                    actions=False,
                )
            ),
            "history",
        )
        source = source_metadata(lambda: retrieved)
        bars: list[OHLCVBar] = []
        for index, row in frame.sort_index().iterrows():
            timestamp = aware_datetime(index)
            if not in_datetime_range(timestamp, query.start, query.end):
                continue
            values = [row.get(name) for name in ("Open", "High", "Low", "Close", "Volume")]
            if any(value is None or bool(pd.isna(value)) for value in values):
                continue
            record_source = source_metadata(
                lambda: retrieved, f"{symbol_text(symbol)}:{timestamp.isoformat()}"
            )
            bars.append(
                OHLCVBar(
                    metadata=CompanyDataMetadata(
                        company=query.company,
                        source=record_source,
                        effective_at=timestamp,
                    ),
                    interval=query.interval,
                    open=float(cast(Any, values[0])),
                    high=float(cast(Any, values[1])),
                    low=float(cast(Any, values[2])),
                    close=float(cast(Any, values[3])),
                    volume=float(cast(Any, values[4])),
                    adjustment=adjustment,
                )
            )
        data = CompanyDataResult(
            company=query.company,
            source=source,
            availability=CompanyDataAvailability.AVAILABLE,
            records=tuple(bars),
        )
        return OHLCVResult(query, data)


class YahooCorporateActionsCapability(CorporateActionsCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_corporate_actions(self, query: CorporateActionsQuery) -> CorporateActionsResult:
        symbol = _company_symbol(query.company)
        if symbol is None:
            return CorporateActionsResult(
                query,
                _unavailable_company(
                    query.company, self._clock, "Yahoo requires a ticker identity"
                ),
            )
        retrieved = self._clock()
        ticker = self._ticker_factory(symbol)
        frame = dataframe(call_yahoo(lambda: ticker.get_actions(period="max")), "actions")
        records: list[DividendRecord | SplitRecord] = []
        for index, row in frame.sort_index().iterrows():
            effective = date_only(index)
            if not in_date_range(effective, query.start, query.end):
                continue
            metadata = CompanyDataMetadata(
                company=query.company,
                source=source_metadata(
                    lambda: retrieved, f"{symbol_text(symbol)}:{effective.isoformat()}"
                ),
                effective_at=effective,
            )
            dividend = decimal_value(row.get("Dividends"))
            if CorporateActionType.DIVIDEND in query.action_types and dividend not in (None, 0):
                records.append(DividendRecord(metadata=metadata, amount=dividend))
            split = decimal_value(row.get("Stock Splits"))
            if CorporateActionType.SPLIT in query.action_types and split not in (None, 0):
                ratio = Fraction(split).limit_denominator(10_000)
                records.append(
                    SplitRecord(
                        metadata=metadata,
                        numerator=ratio.numerator,
                        denominator=ratio.denominator,
                    )
                )
        records.sort(key=lambda record: record.metadata.effective_at)
        data = CompanyDataResult(
            query.company,
            source_metadata(lambda: retrieved),
            CompanyDataAvailability.AVAILABLE,
            tuple(records),
        )
        return CorporateActionsResult(query, data)


class YahooFundamentalsCapability(FundamentalsCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_fundamentals(self, query: FundamentalsQuery) -> FundamentalsResult:
        symbol = _company_symbol(query.company)
        if symbol is None:
            return FundamentalsResult(
                query,
                _unavailable_company(
                    query.company, self._clock, "Yahoo requires a ticker identity"
                ),
            )
        retrieved = self._clock()
        ticker = self._ticker_factory(symbol)
        records: list[CompanyProfileRecord | FinancialStatementRecord] = []
        failures: list[str] = []

        if FundamentalRecordType.PROFILE in query.record_types:
            try:
                info = response_mapping(call_yahoo(ticker.get_info))
                profile_date = retrieved.date()
                fields = {
                    "legal_name": optional_text(info.get("longName") or info.get("shortName")),
                    "description": optional_text(info.get("longBusinessSummary")),
                    "sector": optional_text(info.get("sector")),
                    "industry": optional_text(info.get("industry")),
                    "country": optional_text(info.get("country")),
                    "website": optional_text(info.get("website")),
                }
                if in_date_range(profile_date, query.start, query.end) and any(fields.values()):
                    records.append(
                        CompanyProfileRecord(
                            metadata=CompanyDataMetadata(
                                query.company,
                                source_metadata(lambda: retrieved, symbol_text(symbol)),
                                profile_date,
                                retrieved,
                            ),
                            legal_name=fields["legal_name"],
                            description=fields["description"],
                            sector=fields["sector"],
                            industry=fields["industry"],
                            country=fields["country"],
                            website=fields["website"],
                        )
                    )
            except Exception as error:
                if isinstance(error, ProviderError):
                    raise
                failures.append(f"profile: {error}")

        if FundamentalRecordType.FINANCIAL_STATEMENT in query.record_types:
            requested = query.statement_types or frozenset(
                {
                    FinancialStatementType.BALANCE_SHEET,
                    FinancialStatementType.INCOME_STATEMENT,
                    FinancialStatementType.CASH_FLOW,
                }
            )
            methods: dict[FinancialStatementType, str] = {
                FinancialStatementType.BALANCE_SHEET: "get_balance_sheet",
                FinancialStatementType.INCOME_STATEMENT: "get_income_stmt",
                FinancialStatementType.CASH_FLOW: "get_cash_flow",
            }
            unsupported = requested.difference(methods)
            if unsupported:
                failures.append(
                    "unsupported statement types: "
                    + ", ".join(sorted(value.value for value in unsupported))
                )
            for statement_type in sorted(
                requested.intersection(methods), key=lambda value: value.value
            ):
                for frequency in ("yearly", "quarterly"):
                    try:
                        method = getattr(ticker, methods[statement_type])
                        frame = dataframe(
                            call_yahoo(
                                lambda method=method, frequency=frequency: method(freq=frequency)
                            ),
                            f"{statement_type.value} {frequency}",
                        )
                        records.extend(
                            self._statement_records(
                                query,
                                frame,
                                statement_type,
                                frequency,
                                retrieved,
                                symbol_text(symbol),
                            )
                        )
                    except Exception as error:
                        if isinstance(error, ProviderError):
                            raise
                        failures.append(f"{statement_type.value}/{frequency}: {error}")

        records.sort(key=_fundamental_sort_key)
        if records and failures:
            availability = CompanyDataAvailability.PARTIAL
            reason = "; ".join(failures)
        elif records or not failures:
            availability = CompanyDataAvailability.AVAILABLE
            reason = None
        else:
            availability = CompanyDataAvailability.UNAVAILABLE
            reason = "; ".join(failures)
        data = CompanyDataResult(
            query.company,
            source_metadata(lambda: retrieved),
            availability,
            tuple(records),
            reason,
        )
        return FundamentalsResult(query, data)

    def _statement_records(
        self,
        query: FundamentalsQuery,
        frame: pd.DataFrame,
        statement_type: FinancialStatementType,
        frequency: str,
        retrieved: datetime,
        symbol: str,
    ) -> list[FinancialStatementRecord]:
        records: list[FinancialStatementRecord] = []
        for column in frame.columns:
            period_end = date_only(column)
            if not in_date_range(period_end, query.start, query.end):
                continue
            is_instant = statement_type is FinancialStatementType.BALANCE_SHEET
            reporting_period = ReportingPeriod(
                ReportingPeriodType.INSTANT if is_instant else ReportingPeriodType.DURATION,
                end=period_end,
                start=(
                    None
                    if is_instant
                    else period_end - timedelta(days=364 if frequency == "yearly" else 89)
                ),
            )
            label = (
                FiscalPeriodLabel.FY
                if frequency == "yearly"
                else (
                    FiscalPeriodLabel.Q1,
                    FiscalPeriodLabel.Q2,
                    FiscalPeriodLabel.Q3,
                    FiscalPeriodLabel.Q4,
                )[(period_end.month - 1) // 3]
            )
            for metric_name, value in frame[column].items():
                records.append(
                    FinancialStatementRecord(
                        metadata=CompanyDataMetadata(
                            query.company,
                            source_metadata(
                                lambda: retrieved,
                                f"{symbol}:{statement_type.value}:{period_end}:{metric_name}",
                            ),
                            period_end,
                        ),
                        statement_type=statement_type,
                        metric=_metric_id(metric_name),
                        reporting_period=reporting_period,
                        fiscal_period=FiscalPeriod(period_end.year, label),
                        accounting_basis=AccountingBasis("unknown"),
                        value=decimal_value(value),
                        unit="reported",
                    )
                )
        return records


def _fundamental_sort_key(
    record: CompanyProfileRecord | FinancialStatementRecord,
) -> tuple[str, ...]:
    effective = record.metadata.effective_at.isoformat()
    if isinstance(record, CompanyProfileRecord):
        return (effective, "0")
    return (
        effective,
        "1",
        record.statement_type.value,
        record.reporting_period.start.isoformat() if record.reporting_period.start else "",
        f"{record.fiscal_period.year:020d}",
        record.fiscal_period.label.value,
        record.metric.value,
        record.accounting_basis.value,
        "",
    )


class YahooEarningsCapability(EarningsCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_earnings(self, query: EarningsQuery) -> EarningsResult:
        symbol = _company_symbol(query.company)
        if symbol is None:
            return EarningsResult(
                query,
                _unavailable_company(
                    query.company, self._clock, "Yahoo requires a ticker identity"
                ),
            )
        retrieved = self._clock()
        ticker = self._ticker_factory(symbol)
        value = call_yahoo(lambda: ticker.get_earnings_dates(limit=100))
        if value is None:
            data = _unavailable_company(
                query.company, lambda: retrieved, "Yahoo returned no earnings calendar"
            )
            return EarningsResult(query, data)
        frame = dataframe(value, "earnings dates")
        events: list[EarningsEvent] = []
        eps = EarningsMetricId("eps")
        for index, row in frame.sort_index().iterrows():
            announcement = aware_datetime(index)
            if not in_datetime_range(announcement, query.start, query.end):
                continue
            actual = decimal_value(row.get("Reported EPS"))
            status = (
                EarningsTimingStatus.CONFIRMED
                if actual is not None
                else EarningsTimingStatus.ESTIMATED
            )
            if status not in query.timing_statuses:
                continue
            estimate = decimal_value(row.get("EPS Estimate"))
            surprise = decimal_value(row.get("Surprise(%)"))
            period_end = announcement.date().replace(day=1) - timedelta(days=1)
            period_start = period_end - timedelta(days=89)
            actuals = (EarningsActual(eps, actual, "per_share"),) if actual is not None else ()
            estimates = (
                (EarningsEstimate(eps, estimate, "per_share"),) if estimate is not None else ()
            )
            surprises = (
                (EarningsSurprise(eps, percent=surprise, unit="per_share"),)
                if surprise is not None
                else ()
            )
            events.append(
                EarningsEvent(
                    metadata=CompanyDataMetadata(
                        query.company,
                        source_metadata(
                            lambda: retrieved, f"{symbol_text(symbol)}:{announcement.isoformat()}"
                        ),
                        announcement,
                        announcement if actual is not None else None,
                    ),
                    reporting_period=EarningsReportingPeriod(period_start, period_end),
                    announcement_at=announcement,
                    timing_status=status,
                    published_at=announcement if actual is not None else None,
                    estimates=estimates,
                    actuals=actuals,
                    surprises=surprises,
                )
            )
        events.sort(key=lambda event: event.announcement_at)
        data = CompanyDataResult(
            query.company,
            source_metadata(lambda: retrieved),
            CompanyDataAvailability.AVAILABLE,
            tuple(events),
        )
        return EarningsResult(query, data)


class YahooCompanyNewsCapability(CompanyNewsCapability):
    def __init__(self, ticker_factory: TickerFactory, clock: Clock) -> None:
        self._ticker_factory = ticker_factory
        self._clock = clock

    def get_company_news(self, query: CompanyNewsQuery) -> CompanyNewsResult:
        symbol = _company_symbol(query.company)
        if symbol is None:
            return CompanyNewsResult(
                query,
                _unavailable_company(
                    query.company, self._clock, "Yahoo requires a ticker identity"
                ),
            )
        retrieved = self._clock()
        count = query.limit or 10
        raw = call_yahoo(lambda: self._ticker_factory(symbol).get_news(count=count, tab="news"))
        if not isinstance(raw, list):
            return CompanyNewsResult(
                query,
                _unavailable_company(
                    query.company, lambda: retrieved, "Yahoo returned invalid news"
                ),
            )
        records: list[CompanyNewsRecord] = []
        for raw_item in raw:
            item = cast(dict[str, Any], raw_item) if isinstance(raw_item, dict) else None
            if item is None:
                continue
            content = item.get("content") if isinstance(item.get("content"), dict) else item
            assert isinstance(content, dict)
            published_raw = content.get("pubDate") or content.get("providerPublishTime")
            if published_raw is None:
                continue
            published = (
                datetime.fromtimestamp(float(published_raw), tz=retrieved.tzinfo)
                if isinstance(published_raw, (int, float))
                else aware_datetime(published_raw)
            )
            if not in_datetime_range(published, query.start, query.end):
                continue
            title = optional_text(content.get("title"))
            publisher_value = content.get("provider")
            publisher = (
                optional_text(publisher_value.get("displayName"))
                if isinstance(publisher_value, dict)
                else optional_text(publisher_value)
            )
            url_value = (
                content.get("canonicalUrl") or content.get("clickThroughUrl") or content.get("link")
            )
            if isinstance(url_value, dict):
                url_value = url_value.get("url")
            reference = optional_text(url_value)
            summary = optional_text(content.get("summary") or content.get("description"))
            raw_topics = content.get("topics")
            topics = (
                tuple(
                    sorted(
                        {str(topic).strip().lower() for topic in raw_topics if str(topic).strip()}
                    )
                )
                if isinstance(raw_topics, (list, tuple, set))
                else ()
            )
            if query.topics and query.topics.isdisjoint(topics):
                continue
            if title is None or publisher is None or (reference is None and summary is None):
                continue
            identifier = optional_text(content.get("id") or content.get("uuid")) or reference
            assert identifier is not None
            records.append(
                CompanyNewsRecord(
                    metadata=CompanyDataMetadata(
                        query.company,
                        source_metadata(lambda: retrieved, identifier),
                        published,
                        published,
                    ),
                    document=NewsDocumentId("yahoo", identifier),
                    published_at=published,
                    publisher=publisher,
                    headline=title,
                    summary=summary,
                    reference=reference,
                    related_companies=(query.company,),
                    topics=topics,
                )
            )
        records.sort(key=lambda record: record.published_at)
        if query.limit is not None:
            records = records[: query.limit]
        data = CompanyDataResult(
            query.company,
            source_metadata(lambda: retrieved),
            CompanyDataAvailability.AVAILABLE,
            tuple(records),
        )
        return CompanyNewsResult(query, data)


def yahoo_company_capabilities(ticker_factory: TickerFactory, clock: Clock) -> CompanyCapabilities:
    capabilities = (
        YahooOHLCVCapability(ticker_factory, clock),
        YahooFundamentalsCapability(ticker_factory, clock),
        YahooEarningsCapability(ticker_factory, clock),
        YahooCorporateActionsCapability(ticker_factory, clock),
        YahooCompanyNewsCapability(ticker_factory, clock),
    )
    return CompanyCapabilities("YahooProvider", capabilities)


__all__ = [
    "YahooCompanyNewsCapability",
    "YahooCorporateActionsCapability",
    "YahooEarningsCapability",
    "YahooFundamentalsCapability",
    "YahooOHLCVCapability",
    "yahoo_company_capabilities",
]
