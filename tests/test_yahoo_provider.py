import unittest
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from tbt_engine.core.errors import ProviderRateLimitError
from tbt_engine.providers import YahooProvider
from tbt_engine.providers.capabilities import CapabilityId
from tbt_engine.providers.capabilities.company import (
    BarInterval,
    BarIntervalUnit,
    CompanyIdentifier,
    CompanyNewsCapability,
    CompanyNewsQuery,
    CorporateActionsCapability,
    CorporateActionsQuery,
    EarningsCapability,
    EarningsQuery,
    FundamentalRecordType,
    FundamentalsCapability,
    FundamentalsQuery,
    OHLCVAdjustment,
    OHLCVCapability,
    OHLCVQuery,
)
from tbt_engine.providers.capabilities.macro import (
    CommoditiesFXCapability,
    CommoditiesFXQuery,
    MacroSeriesIdentifier,
)
from tbt_engine.providers.capabilities.market import (
    MarketIdentifier,
    NasdaqCapability,
    NasdaqQuery,
    SectorETFCapability,
    SectorETFQuery,
    SP500Capability,
    SP500Interval,
    SP500IntervalAlignment,
    SP500IntervalUnit,
    SP500Query,
    VIXCapability,
    VIXQuery,
)
from tbt_engine.providers.capabilities.market.sp500 import SP500RecordType
from tbt_engine.providers.capabilities.textual import (
    AnnouncementCategory,
    MajorAnnouncementQuery,
    MajorAnnouncementsCapability,
    MarketNewsCapability,
    MarketNewsQuery,
    RelatedEntity,
    TextualRequestContext,
    TextualTimeBasis,
)

NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
INDEX = pd.DatetimeIndex(
    [datetime(2026, 1, 5, tzinfo=timezone.utc), datetime(2026, 1, 6, tzinfo=timezone.utc)]
)


class FakeTicker:
    def history(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1_000.0, 2_000.0],
            },
            index=INDEX,
        )

    def get_actions(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame(
            {"Dividends": [0.25, 0.0], "Stock Splits": [0.0, 2.0]},
            index=INDEX,
        )

    def get_info(self) -> dict[str, object]:
        return {
            "longName": "Example Corp",
            "sector": "Technology",
            "industry": "Software",
        }

    def get_balance_sheet(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame({pd.Timestamp("2025-12-31"): [1000.0]}, index=["Total Assets"])

    def get_income_stmt(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame({pd.Timestamp("2025-12-31"): [500.0]}, index=["Total Revenue"])

    def get_cash_flow(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame({pd.Timestamp("2025-12-31"): [200.0]}, index=["Free Cash Flow"])

    def get_earnings_dates(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame(
            {"EPS Estimate": [1.1], "Reported EPS": [1.2], "Surprise(%)": [9.09]},
            index=pd.DatetimeIndex([datetime(2026, 1, 20, 21, tzinfo=timezone.utc)]),
        )

    def get_news(self, **kwargs: object) -> list[dict[str, object]]:
        tab = kwargs.get("tab")
        title = "Example press release" if tab == "press releases" else "Example company news"
        return [
            {
                "content": {
                    "id": f"news-{tab or 'company'}",
                    "title": title,
                    "pubDate": "2026-01-10T12:00:00Z",
                    "provider": {"displayName": "Example Wire"},
                    "summary": "A deterministic summary.",
                    "canonicalUrl": {"url": "https://example.test/article"},
                }
            }
        ]

    def get_sec_filings(self) -> dict[str, object]:
        return {
            "filings": [
                {
                    "id": "filing-1",
                    "type": "10-K",
                    "filingDate": "2026-01-12T12:00:00Z",
                    "edgarUrl": "https://example.test/filing",
                }
            ]
        }


class FakeSearch:
    def __init__(self, _query: str, **_kwargs: object) -> None:
        self.news: list[dict[str, object]] = [
            {
                "content": {
                    "id": "market-1",
                    "title": "Markets advance",
                    "pubDate": "2026-01-11T12:00:00Z",
                    "provider": {"displayName": "Example Wire"},
                    "summary": "Broad markets advanced.",
                }
            }
        ]


class YahooProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.symbols: list[str | tuple[str, str]] = []

        def ticker_factory(symbol: str | tuple[str, str]) -> Any:
            self.symbols.append(symbol)
            return FakeTicker()

        self.provider = YahooProvider(
            ticker_factory=ticker_factory,
            search_factory=FakeSearch,
            clock=lambda: NOW,
        )
        self.company = CompanyIdentifier("ticker", "EXM", market="XNAS")

    def test_advertises_the_complete_normalized_yahoo_capability_matrix(self) -> None:
        expected = {
            "company.ohlcv",
            "company.fundamentals",
            "company.earnings",
            "company.corporate_actions",
            "company.news",
            "market.sp500",
            "market.nasdaq",
            "market.sector_etf",
            "market.vix",
            "macro.commodities_fx",
            "textual.market_news",
            "textual.major_announcements",
        }

        self.assertEqual(
            self.provider.supported_capabilities,
            frozenset(CapabilityId(value) for value in expected),
        )
        self.assertEqual(type(self.provider).__module__, "tbt_engine.providers.yahoo.provider")

    def test_normalizes_all_company_capabilities(self) -> None:
        ohlcv = self.provider.require_capability(OHLCVCapability).get_ohlcv(
            OHLCVQuery(
                self.company,
                BarInterval(1, BarIntervalUnit.DAY),
                OHLCVAdjustment.UNADJUSTED,
            )
        )
        fundamentals = self.provider.require_capability(FundamentalsCapability).get_fundamentals(
            FundamentalsQuery(
                self.company,
                record_types=frozenset({FundamentalRecordType.PROFILE}),
            )
        )
        earnings = self.provider.require_capability(EarningsCapability).get_earnings(
            EarningsQuery(self.company)
        )
        actions = self.provider.require_capability(
            CorporateActionsCapability
        ).get_corporate_actions(CorporateActionsQuery(self.company))
        news = self.provider.require_capability(CompanyNewsCapability).get_company_news(
            CompanyNewsQuery(self.company)
        )

        self.assertEqual(len(ohlcv.bars), 2)
        self.assertEqual(len(fundamentals.records), 1)
        self.assertEqual(len(earnings.events), 1)
        self.assertEqual(len(actions.records), 2)
        self.assertEqual(len(news.records), 1)
        self.assertEqual(self.symbols[0], ("EXM", "XNAS"))

    def test_normalizes_all_market_and_macro_capabilities(self) -> None:
        sp500_market = MarketIdentifier("ticker", "^GSPC")
        sp500 = self.provider.require_capability(SP500Capability).get_sp500(
            SP500Query(
                sp500_market,
                SP500RecordType.OBSERVATION,
                interval=SP500Interval(
                    1, SP500IntervalUnit.DAY, SP500IntervalAlignment.TRADING_SESSION
                ),
            )
        )
        nasdaq = self.provider.require_capability(NasdaqCapability).get_nasdaq(
            NasdaqQuery(MarketIdentifier("ticker", "^IXIC"))
        )
        sector = self.provider.require_capability(SectorETFCapability).get_sector_etf(
            SectorETFQuery(MarketIdentifier("ticker", "XLK"))
        )
        vix = self.provider.require_capability(VIXCapability).get_vix(
            VIXQuery(MarketIdentifier("ticker", "^VIX"))
        )
        fx = self.provider.require_capability(CommoditiesFXCapability).get_commodities_fx(
            CommoditiesFXQuery(MacroSeriesIdentifier("yahoo", "EURUSD=X"))
        )

        self.assertEqual(len(sp500.observations), 2)
        self.assertEqual(len(nasdaq.records), 2)
        self.assertEqual(len(sector.records), 2)
        self.assertEqual(len(vix.records), 2)
        self.assertEqual(len(fx.records), 2)

    def test_normalizes_all_textual_capabilities(self) -> None:
        request = TextualRequestContext(TextualTimeBasis.PUBLISHED_AT)
        market_news = self.provider.require_capability(MarketNewsCapability).get_market_news(
            MarketNewsQuery(request, market="US")
        )
        announcements = self.provider.require_capability(
            MajorAnnouncementsCapability
        ).get_major_announcements(
            MajorAnnouncementQuery(
                request,
                category=AnnouncementCategory.PRESS_RELEASE,
                entity=RelatedEntity(kind="company", symbol="EXM"),
            )
        )

        self.assertEqual(len(market_news.records), 1)
        self.assertEqual(len(announcements.records), 1)

    def test_legacy_history_remains_available(self) -> None:
        result = self.provider.get_history("EXM")

        self.assertEqual(list(result["Close"]), [101.0, 102.0])

    def test_maps_yfinance_rate_limits_to_the_shared_provider_error(self) -> None:
        class YFRateLimitError(Exception):
            pass

        class LimitedTicker(FakeTicker):
            def history(self, **_kwargs: object) -> pd.DataFrame:
                raise YFRateLimitError("Too many requests")

        provider = YahooProvider(
            ticker_factory=lambda _symbol: LimitedTicker(),
            search_factory=FakeSearch,
            clock=lambda: NOW,
        )
        capability = provider.require_capability(OHLCVCapability)

        with self.assertRaises(ProviderRateLimitError):
            capability.get_ohlcv(OHLCVQuery(self.company, BarInterval(1, BarIntervalUnit.DAY)))


if __name__ == "__main__":
    unittest.main()
