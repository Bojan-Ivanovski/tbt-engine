import re
from abc import abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TypeAlias

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier

FUNDAMENTALS_CAPABILITY = CapabilityId("company.fundamentals")

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def _is_runtime_instance(value: object, expected_type: type[object]) -> bool:
    return isinstance(value, expected_type)


def _is_date_only(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _normalize_optional_text(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if not _is_runtime_instance(value, str):
        raise ValueError(f"Fundamentals {label} must be text or None")
    return value.strip()


def _validate_record_timing(
    metadata: CompanyDataMetadata,
    published_at: datetime | None,
) -> date:
    effective_at = metadata.effective_at
    if not _is_date_only(effective_at):
        raise ValueError("Fundamentals effective time must be a calendar date")
    if published_at is not None and not _is_aware_datetime(published_at):
        raise ValueError("Fundamentals publication time must be timezone-aware")
    if (
        published_at is not None
        and metadata.available_at is not None
        and metadata.available_at < published_at
    ):
        raise ValueError("Fundamentals availability time must not precede publication")
    return effective_at


class FundamentalRecordType(str, Enum):
    PROFILE = "profile"
    FINANCIAL_STATEMENT = "financial_statement"


class FinancialStatementType(str, Enum):
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW = "cash_flow"
    CHANGES_IN_EQUITY = "changes_in_equity"
    COMPREHENSIVE_INCOME = "comprehensive_income"


class ReportingPeriodType(str, Enum):
    INSTANT = "instant"
    DURATION = "duration"


class FiscalPeriodLabel(str, Enum):
    FY = "FY"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    H1 = "H1"
    H2 = "H2"
    NINE_MONTHS = "9M"


@dataclass(frozen=True, order=True, slots=True)
class FundamentalMetricId:
    """Stable provider-neutral identity for one reported metric."""

    value: str

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.value, str):
            raise ValueError("Fundamental metric identifier must be text")
        value = self.value.strip().lower()
        if not _IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("Fundamental metric identifier is invalid")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class AccountingBasis:
    """Named accounting framework, such as IFRS or US GAAP."""

    value: str

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.value, str):
            raise ValueError("Accounting basis must be text")
        value = self.value.strip().lower()
        if not _IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("Accounting basis is invalid")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class ReportingPeriod:
    """Calendar reporting period with inclusive start and end dates."""

    type: ReportingPeriodType
    end: date
    start: date | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.type, ReportingPeriodType):
            raise ValueError("Reporting period type is invalid")
        if not _is_date_only(self.end):
            raise ValueError("Reporting period end must be a calendar date")
        if self.start is not None and not _is_date_only(self.start):
            raise ValueError("Reporting period start must be a calendar date")
        if self.type is ReportingPeriodType.INSTANT and self.start is not None:
            raise ValueError("Instant reporting periods must not have a start date")
        if self.type is ReportingPeriodType.DURATION and self.start is None:
            raise ValueError("Duration reporting periods require a start date")
        if self.start is not None and self.start > self.end:
            raise ValueError("Reporting period start must not follow its end")


@dataclass(frozen=True, order=True, slots=True)
class FiscalPeriod:
    """Issuer fiscal year and normalized period label."""

    year: int
    label: FiscalPeriodLabel

    def __post_init__(self) -> None:
        if (
            not _is_runtime_instance(self.year, int)
            or isinstance(self.year, bool)
            or self.year <= 0
        ):
            raise ValueError("Fiscal year must be a positive integer")
        if not _is_runtime_instance(self.label, FiscalPeriodLabel):
            raise ValueError("Fiscal period label is invalid")


@dataclass(frozen=True, slots=True)
class FundamentalsQuery:
    """Fundamentals request filtered by effective calendar date.

    ``start`` is inclusive and ``end`` is exclusive. Financial statement
    records align to their reporting-period end; profile records align to the
    date on which the snapshot applies.
    """

    company: CompanyIdentifier
    record_types: frozenset[FundamentalRecordType] = frozenset(FundamentalRecordType)
    statement_types: frozenset[FinancialStatementType] = frozenset()
    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        if not _is_runtime_instance(self.company, CompanyIdentifier):
            raise InvalidCapabilityQueryError("Fundamentals query company is invalid")
        try:
            record_types = frozenset(self.record_types)
            statement_types = frozenset(self.statement_types)
        except TypeError as error:
            raise InvalidCapabilityQueryError(
                "Fundamentals query filters must be collections"
            ) from error
        if not record_types or any(
            not _is_runtime_instance(value, FundamentalRecordType) for value in record_types
        ):
            raise InvalidCapabilityQueryError("Fundamentals query record types are invalid")
        if any(
            not _is_runtime_instance(value, FinancialStatementType) for value in statement_types
        ):
            raise InvalidCapabilityQueryError("Fundamentals query statement types are invalid")
        if statement_types and FundamentalRecordType.FINANCIAL_STATEMENT not in record_types:
            raise InvalidCapabilityQueryError(
                "Fundamentals statement filters require financial statement records"
            )
        for name, value in (("start", self.start), ("end", self.end)):
            if value is not None and not _is_date_only(value):
                raise InvalidCapabilityQueryError(
                    f"Fundamentals query {name} must be a calendar date"
                )
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise InvalidCapabilityQueryError("Fundamentals query start must be before end")
        object.__setattr__(self, "record_types", record_types)
        object.__setattr__(self, "statement_types", statement_types)


@dataclass(frozen=True, slots=True)
class CompanyProfileRecord:
    """Normalized company profile snapshot with optional provider coverage."""

    metadata: CompanyDataMetadata
    published_at: datetime | None = None
    legal_name: str | None = None
    description: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None

    def __post_init__(self) -> None:
        _validate_record_timing(self.metadata, self.published_at)
        values = {
            "legal name": _normalize_optional_text(self.legal_name, "legal name"),
            "description": _normalize_optional_text(self.description, "description"),
            "sector": _normalize_optional_text(self.sector, "sector"),
            "industry": _normalize_optional_text(self.industry, "industry"),
            "country": _normalize_optional_text(self.country, "country"),
            "website": _normalize_optional_text(self.website, "website"),
        }
        if all(value is None for value in values.values()):
            raise ValueError("Company profile record requires at least one supplied field")
        object.__setattr__(self, "legal_name", values["legal name"])
        object.__setattr__(self, "description", values["description"])
        object.__setattr__(self, "sector", values["sector"])
        object.__setattr__(self, "industry", values["industry"])
        object.__setattr__(self, "country", values["country"])
        object.__setattr__(self, "website", values["website"])


@dataclass(frozen=True, slots=True)
class FinancialStatementRecord:
    """One normalized financial-statement metric observation."""

    metadata: CompanyDataMetadata
    statement_type: FinancialStatementType
    metric: FundamentalMetricId
    reporting_period: ReportingPeriod
    fiscal_period: FiscalPeriod
    accounting_basis: AccountingBasis
    value: Decimal | None
    unit: str
    scale: Decimal = Decimal(1)
    currency: str | None = None
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        effective_at = _validate_record_timing(self.metadata, self.published_at)
        if not _is_runtime_instance(self.statement_type, FinancialStatementType):
            raise ValueError("Financial statement type is invalid")
        if not _is_runtime_instance(self.metric, FundamentalMetricId):
            raise ValueError("Financial statement metric identity is invalid")
        if not _is_runtime_instance(self.reporting_period, ReportingPeriod):
            raise ValueError("Financial statement reporting period is invalid")
        if not _is_runtime_instance(self.fiscal_period, FiscalPeriod):
            raise ValueError("Financial statement fiscal period is invalid")
        if not _is_runtime_instance(self.accounting_basis, AccountingBasis):
            raise ValueError("Financial statement accounting basis is invalid")
        if effective_at != self.reporting_period.end:
            raise ValueError("Financial statement effective date must equal reporting period end")
        if self.published_at is not None and self.published_at.date() < effective_at:
            raise ValueError("Financial statement publication must not precede its period end")
        if self.value is not None and not _is_runtime_instance(self.value, Decimal):
            raise ValueError("Financial statement value must be Decimal or None")
        if self.value is not None and not self.value.is_finite():
            raise ValueError("Financial statement value must be finite")

        if not _is_runtime_instance(self.unit, str):
            raise ValueError("Financial statement unit must be text")
        if self.currency is not None and not _is_runtime_instance(self.currency, str):
            raise ValueError("Financial statement currency must be text or None")
        unit = self.unit.strip()
        currency = self.currency.strip().upper() if self.currency is not None else None
        if not unit:
            raise ValueError("Financial statement unit must not be empty")
        if not _is_runtime_instance(self.scale, Decimal) or not self.scale.is_finite():
            raise ValueError("Financial statement scale must be a finite Decimal")
        if self.scale <= 0:
            raise ValueError("Financial statement scale must be positive")
        if currency is not None and not _CURRENCY_PATTERN.fullmatch(currency):
            raise ValueError("Financial statement currency must use a three-letter code")

        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "currency", currency)


FundamentalsRecord: TypeAlias = CompanyProfileRecord | FinancialStatementRecord


def _is_fundamentals_record(value: object) -> bool:
    return isinstance(value, (CompanyProfileRecord, FinancialStatementRecord))


def _publication_key(published_at: datetime | None) -> str:
    if published_at is None:
        return ""
    return published_at.astimezone(timezone.utc).isoformat()


def _record_sort_key(record: FundamentalsRecord) -> tuple[str, ...]:
    effective_at = record.metadata.effective_at
    if not _is_date_only(effective_at):
        raise ValueError("Fundamentals effective time must be a calendar date")
    if isinstance(record, CompanyProfileRecord):
        return (effective_at.isoformat(), "0", _publication_key(record.published_at))
    period_start = record.reporting_period.start
    return (
        effective_at.isoformat(),
        "1",
        record.statement_type.value,
        period_start.isoformat() if period_start is not None else "",
        f"{record.fiscal_period.year:020d}",
        record.fiscal_period.label.value,
        record.metric.value,
        record.accounting_basis.value,
        _publication_key(record.published_at),
    )


def _record_identity(record: FundamentalsRecord) -> tuple[str, ...]:
    effective_at = record.metadata.effective_at
    if not _is_date_only(effective_at):
        raise ValueError("Fundamentals effective time must be a calendar date")
    if isinstance(record, CompanyProfileRecord):
        return ("profile", effective_at.isoformat(), _publication_key(record.published_at))
    period_start = record.reporting_period.start
    return (
        "financial_statement",
        record.statement_type.value,
        period_start.isoformat() if period_start is not None else "",
        record.reporting_period.end.isoformat(),
        str(record.fiscal_period.year),
        record.fiscal_period.label.value,
        record.metric.value,
        record.accounting_basis.value,
        _publication_key(record.published_at),
    )


@dataclass(frozen=True, slots=True)
class FundamentalsResult:
    """Validated fundamentals response in deterministic ascending order.

    Records sort by effective date, with profile snapshots before statement
    metrics on the same date. Statement ties sort by statement, period, fiscal
    period, metric, accounting basis, and publication time.
    """

    query: FundamentalsQuery
    data: CompanyDataResult[FundamentalsRecord]

    def __post_init__(self) -> None:
        if self.data.company != self.query.company:
            raise ValueError("Fundamentals result company must match its query")

        previous_key: tuple[str, ...] | None = None
        identities: set[tuple[str, ...]] = set()
        for record in self.data.records:
            if not _is_fundamentals_record(record):
                raise ValueError("Fundamentals result contains an invalid record type")
            if record.metadata.company != self.query.company:
                raise ValueError("Fundamentals record company must match its query")

            effective_at = record.metadata.effective_at
            if not _is_date_only(effective_at):
                raise ValueError("Fundamentals effective time must be a calendar date")
            if self.query.start is not None and effective_at < self.query.start:
                raise ValueError("Fundamentals record precedes the query start")
            if self.query.end is not None and effective_at >= self.query.end:
                raise ValueError("Fundamentals record is not before the exclusive query end")

            if isinstance(record, CompanyProfileRecord):
                if FundamentalRecordType.PROFILE not in self.query.record_types:
                    raise ValueError("Fundamentals result contains an unrequested profile")
            else:
                if FundamentalRecordType.FINANCIAL_STATEMENT not in self.query.record_types:
                    raise ValueError("Fundamentals result contains an unrequested statement")
                if (
                    self.query.statement_types
                    and record.statement_type not in self.query.statement_types
                ):
                    raise ValueError("Fundamentals statement type was not requested")

            identity = _record_identity(record)
            if identity in identities:
                raise ValueError("Fundamentals records must be unique")
            identities.add(identity)

            key = _record_sort_key(record)
            if previous_key is not None and key <= previous_key:
                raise ValueError("Fundamentals records must use deterministic ascending order")
            previous_key = key

    @property
    def records(self) -> tuple[FundamentalsRecord, ...]:
        return self.data.records

    @property
    def availability(self) -> CompanyDataAvailability:
        return self.data.availability


class FundamentalsCapability(Capability):
    """Provider-independent contract for normalized company fundamentals."""

    @property
    def id(self) -> CapabilityId:
        return FUNDAMENTALS_CAPABILITY

    @abstractmethod
    def get_fundamentals(self, query: FundamentalsQuery) -> FundamentalsResult:
        raise NotImplementedError


__all__ = [
    "AccountingBasis",
    "CompanyProfileRecord",
    "FUNDAMENTALS_CAPABILITY",
    "FinancialStatementRecord",
    "FinancialStatementType",
    "FiscalPeriod",
    "FiscalPeriodLabel",
    "FundamentalMetricId",
    "FundamentalRecordType",
    "FundamentalsCapability",
    "FundamentalsQuery",
    "FundamentalsRecord",
    "FundamentalsResult",
    "ReportingPeriod",
    "ReportingPeriodType",
]
