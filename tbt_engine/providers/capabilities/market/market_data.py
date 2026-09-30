from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Generic, TypeVar

from tbt_engine.instruments import TradingSessionIdentifier
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier

T = TypeVar("T")


class MarketDataAvailability(str, Enum):
    """Coverage status for a successful market-capability request."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MarketDataMetadata:
    """Market identity, provenance, and point-in-time semantics for one record."""

    market: MarketIdentifier
    source: SourceMetadata
    effective_at: date | datetime
    available_at: datetime | None = None
    session: TradingSessionIdentifier | None = None

    def __post_init__(self) -> None:
        if isinstance(self.effective_at, datetime) and (
            self.effective_at.tzinfo is None or self.effective_at.utcoffset() is None
        ):
            raise ValueError("Market data effective time must be timezone-aware")
        if self.available_at is not None and (
            self.available_at.tzinfo is None or self.available_at.utcoffset() is None
        ):
            raise ValueError("Market data availability time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class MarketDataResult(Generic[T]):
    """Normalized result distinguishing confirmed empty data from unavailable data."""

    market: MarketIdentifier
    source: SourceMetadata
    availability: MarketDataAvailability
    records: tuple[T, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        records = tuple(self.records)
        object.__setattr__(self, "records", records)

        reason = self.reason.strip() if self.reason is not None else None
        if reason == "":
            raise ValueError("Market data availability reason must not be empty")

        if self.availability is MarketDataAvailability.AVAILABLE:
            if reason is not None:
                raise ValueError("Available market data must not include a failure reason")
        elif self.availability is MarketDataAvailability.PARTIAL:
            if not records or reason is None:
                raise ValueError("Partial market data requires records and a reason")
        elif not reason or records:
            raise ValueError("Unavailable market data requires a reason and no records")

        object.__setattr__(self, "reason", reason)


__all__ = ["MarketDataAvailability", "MarketDataMetadata", "MarketDataResult"]
