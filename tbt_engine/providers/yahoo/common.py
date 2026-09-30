"""Shared Yahoo Finance adapter helpers."""

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, TypeAlias, cast

import pandas as pd
import yfinance as yf

from tbt_engine.core.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
)
from tbt_engine.metadata import SourceMetadata

YahooTicker: TypeAlias = Any
TickerFactory: TypeAlias = Callable[[str | tuple[str, str]], YahooTicker]
SearchFactory: TypeAlias = Callable[..., Any]
Clock: TypeAlias = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_ticker_factory(symbol: str | tuple[str, str]) -> YahooTicker:
    return yf.Ticker(symbol)


def default_search_factory(*args: object, **kwargs: object) -> Any:
    search: Any = yf.Search
    return search(*args, **kwargs)


def source_metadata(clock: Clock, source_record_id: str | None = None) -> SourceMetadata:
    return SourceMetadata(
        provider="yahoo",
        source="Yahoo Finance",
        retrieved_at=clock(),
        source_record_id=source_record_id,
    )


def yahoo_symbol(scheme: str, value: str, market: str | None) -> str | tuple[str, str] | None:
    if scheme not in {"ticker", "yahoo"}:
        return None
    return (value, market) if market is not None else value


def symbol_text(symbol: str | tuple[str, str]) -> str:
    return symbol[0] if isinstance(symbol, tuple) else symbol


def aware_datetime(value: object) -> datetime:
    timestamp = pd.Timestamp(cast(Any, value))
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    return timestamp.to_pydatetime()


def date_only(value: object) -> date:
    return pd.Timestamp(cast(Any, value)).date()


def decimal_value(value: object) -> Decimal | None:
    if value is None or cast(bool, pd.isna(cast(Any, value))):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ProviderResponseError(
            f"Yahoo Finance returned a non-numeric value: {value!r}"
        ) from error
    if not result.is_finite():
        return None
    return result


def optional_text(value: object) -> str | None:
    if value is None or cast(bool, pd.isna(cast(Any, value))):
        return None
    result = str(value).strip()
    return result or None


def response_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderResponseError("Yahoo Finance returned an unexpected response shape")
    return cast(Mapping[str, Any], value)


def translate_error(error: Exception) -> Exception:
    name = type(error).__name__.lower()
    message = str(error) or type(error).__name__
    if "ratelimit" in name or "too many requests" in message.lower():
        return ProviderRateLimitError(message)
    if "auth" in name or "unauthorized" in message.lower() or "forbidden" in message.lower():
        return ProviderAuthenticationError(message)
    if "json" in name or "decode" in name or "response" in name:
        return ProviderResponseError(message)
    return ProviderRequestError(message)


def call_yahoo(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except (ProviderRequestError, ProviderResponseError):
        raise
    except Exception as error:
        raise translate_error(error) from error


def dataframe(value: object, label: str) -> pd.DataFrame:
    if not isinstance(value, pd.DataFrame):
        raise ProviderResponseError(f"Yahoo Finance {label} response is not tabular")
    return value


def in_datetime_range(value: datetime, start: datetime | None, end: datetime | None) -> bool:
    return (start is None or value >= start) and (end is None or value < end)


def in_date_range(value: date, start: date | None, end: date | None) -> bool:
    return (start is None or value >= start) and (end is None or value < end)
