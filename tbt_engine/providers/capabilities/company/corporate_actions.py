from abc import abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier

CORPORATE_ACTIONS_CAPABILITY = CapabilityId("company.corporate_actions")


def _date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


class CorporateActionType(str, Enum):
    DIVIDEND = "dividend"
    SPLIT = "split"


@dataclass(frozen=True, slots=True)
class CorporateActionsQuery:
    company: CompanyIdentifier
    start: date | None = None
    end: date | None = None
    action_types: frozenset[CorporateActionType] = frozenset(CorporateActionType)

    def __post_init__(self) -> None:
        if type(self.company) is not CompanyIdentifier:
            raise InvalidCapabilityQueryError("Corporate-actions company is invalid")
        try:
            kinds = frozenset(self.action_types)
        except TypeError as exc:
            raise InvalidCapabilityQueryError(
                "Corporate-action types must be a collection"
            ) from exc
        if not kinds or any(type(kind) is not CorporateActionType for kind in kinds):
            raise InvalidCapabilityQueryError("Corporate-action types are invalid")
        if any(value is not None and not _date(value) for value in (self.start, self.end)):
            raise InvalidCapabilityQueryError("Corporate-action bounds must be dates")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Corporate-action start must precede end")
        object.__setattr__(self, "action_types", kinds)


@dataclass(frozen=True, slots=True)
class DividendRecord:
    metadata: CompanyDataMetadata
    amount: Decimal | None
    currency: str | None = None
    declaration_date: date | None = None
    ex_dividend_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None

    def __post_init__(self) -> None:
        if not _date(self.metadata.effective_at):
            raise ValueError("Dividend effective time must be a date")
        if self.amount is not None and (
            type(self.amount) is not Decimal or not self.amount.is_finite() or self.amount < 0
        ):
            raise ValueError("Dividend amount must be finite and non-negative")
        if self.currency is not None:
            currency = self.currency.strip().upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("Dividend currency must be a three-letter code")
            object.__setattr__(self, "currency", currency)
        for value in (
            self.declaration_date,
            self.ex_dividend_date,
            self.record_date,
            self.payment_date,
        ):
            if value is not None and not _date(value):
                raise ValueError("Dividend dates must be calendar dates")


@dataclass(frozen=True, slots=True)
class SplitRecord:
    metadata: CompanyDataMetadata
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if not _date(self.metadata.effective_at):
            raise ValueError("Split effective time must be a date")
        if (
            isinstance(self.numerator, bool)
            or isinstance(self.denominator, bool)
            or self.numerator <= 0
            or self.denominator <= 0
        ):
            raise ValueError("Split ratio values must be positive integers")


CorporateActionRecord = DividendRecord | SplitRecord


@dataclass(frozen=True, slots=True)
class CorporateActionsResult:
    query: CorporateActionsQuery
    data: CompanyDataResult[CorporateActionRecord]

    def __post_init__(self) -> None:
        if self.data.company != self.query.company:
            raise ValueError("Corporate-actions company must match query")
        previous: date | None = None
        seen: set[tuple[object, ...]] = set()
        for record in self.data.records:
            if record.metadata.company != self.query.company:
                raise ValueError("Corporate-action record company must match query")
            kind = (
                CorporateActionType.DIVIDEND
                if isinstance(record, DividendRecord)
                else CorporateActionType.SPLIT
            )
            if kind not in self.query.action_types:
                raise ValueError("Corporate-action type was not requested")
            effective = record.metadata.effective_at
            assert isinstance(effective, date) and not isinstance(effective, datetime)
            if self.query.start is not None and effective < self.query.start:
                raise ValueError("Corporate-action precedes query start")
            if self.query.end is not None and effective >= self.query.end:
                raise ValueError("Corporate-action is not before exclusive query end")
            identity = (kind, effective, record.metadata.source.source_record_id)
            if identity in seen:
                raise ValueError("Corporate-action records must be unique")
            seen.add(identity)
            if previous is not None and effective <= previous:
                raise ValueError("Corporate-action records must be ascending and unique")
            previous = effective

    @property
    def records(self) -> tuple[CorporateActionRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> CompanyDataAvailability:
        return self.data.availability


class CorporateActionsCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return CORPORATE_ACTIONS_CAPABILITY

    @abstractmethod
    def get_corporate_actions(self, query: CorporateActionsQuery) -> CorporateActionsResult:
        raise NotImplementedError


__all__ = [
    "CORPORATE_ACTIONS_CAPABILITY",
    "CorporateActionRecord",
    "CorporateActionType",
    "CorporateActionsCapability",
    "CorporateActionsQuery",
    "CorporateActionsResult",
    "DividendRecord",
    "SplitRecord",
]
