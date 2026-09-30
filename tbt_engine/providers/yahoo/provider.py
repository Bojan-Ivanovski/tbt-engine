"""Yahoo Finance provider composition."""

import logging
from datetime import date
from typing import Optional, cast

import pandas as pd

from tbt_engine.providers.provider import Provider

from .common import (
    Clock,
    SearchFactory,
    TickerFactory,
    default_search_factory,
    default_ticker_factory,
    utc_now,
)
from .company import yahoo_company_capabilities
from .macro import yahoo_macro_capabilities
from .market import yahoo_market_capabilities
from .textual import yahoo_textual_capabilities

logger = logging.getLogger(__name__)


class YahooProvider(Provider):
    """Yahoo Finance provider backed by normalized, discoverable capabilities."""

    def __init__(
        self,
        *,
        ticker_factory: TickerFactory = default_ticker_factory,
        search_factory: SearchFactory = default_search_factory,
        clock: Clock = utc_now,
    ) -> None:
        self._ticker_factory = ticker_factory
        self._search_factory = search_factory
        self._clock = clock
        self.company = yahoo_company_capabilities(ticker_factory, clock)
        self.market = yahoo_market_capabilities(ticker_factory, clock)
        self.macro = yahoo_macro_capabilities(ticker_factory, clock)
        self.textual = yahoo_textual_capabilities(ticker_factory, search_factory, clock)
        super().__init__((self.company, self.market, self.macro, self.textual))

    def get_history(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        logger.info("Fetching %s history at interval %s", symbol, interval)
        ticker = self._ticker_factory(symbol)
        return cast(
            pd.DataFrame,
            ticker.history(interval=interval, start=start, end=end),
        )


__all__ = ["YahooProvider"]
