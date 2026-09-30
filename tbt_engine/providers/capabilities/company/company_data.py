from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Generic, TypeVar

from tbt_engine.instruments import TradingSessionIdentifier
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier

T = TypeVar("T")


class CompanyDataAvailability(str, Enum):
    """Coverage status for a successful company-capability request."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CompanyDataMetadata:
    """Company identity, provenance, and point-in-time semantics for one record."""

    company: CompanyIdentifier
    source: SourceMetadata
    effective_at: date | datetime
    available_at: datetime | None = None
    session: TradingSessionIdentifier | None = None

    def __post_init__(self) -> None:
        if isinstance(self.effective_at, datetime) and (
            self.effective_at.tzinfo is None or self.effective_at.utcoffset() is None
        ):
            raise ValueError("Company data effective time must be timezone-aware")
        if self.available_at is not None and (
            self.available_at.tzinfo is None or self.available_at.utcoffset() is None
        ):
            raise ValueError("Company data availability time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CompanyDataResult(Generic[T]):
    """Normalized result distinguishing confirmed empty data from unavailable data."""

    company: CompanyIdentifier
    source: SourceMetadata
    availability: CompanyDataAvailability
    records: tuple[T, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        records = tuple(self.records)
        reason = self.reason.strip() if self.reason is not None else None
        if reason == "":
            raise ValueError("Company data availability reason must not be empty")

        if self.availability is CompanyDataAvailability.AVAILABLE:
            if reason is not None:
                raise ValueError("Available company data must not include a failure reason")
        elif self.availability is CompanyDataAvailability.PARTIAL:
            if not records or reason is None:
                raise ValueError("Partial company data requires records and a reason")
        elif not reason or records:
            raise ValueError("Unavailable company data requires a reason and no records")

        object.__setattr__(self, "records", records)
        object.__setattr__(self, "reason", reason)


__all__ = ["CompanyDataAvailability", "CompanyDataMetadata", "CompanyDataResult"]
