import logging
from datetime import date
from typing import Any, Optional, cast

import pandas as pd
import yfinance as yf

from tbt_engine.providers.provider import Provider

logger = logging.getLogger(__name__)


class YahooProvider(Provider):
    """Yahoo Finance price history provider."""

    def get_history(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        logger.info(
            "Fetching %s history at interval %s",
            symbol,
            interval,
        )
        ticker: Any = yf.Ticker(symbol)
        return cast(
            pd.DataFrame,
            ticker.history(
                interval=interval,
                start=start,
                end=end,
            ),
        )
