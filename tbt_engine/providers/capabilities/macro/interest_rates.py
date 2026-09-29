from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from tbt_engine.core.errors import InvalidCapabilityQueryError, ProviderResponseError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.macro.macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
    MacroUnitMetadata,
    ObservationPeriod,
)
from tbt_engine.providers.capabilities.macro.macro_identifier import (
    GeographyIdentifier,
    MacroSeriesIdentifier,
)

INTEREST_RATES_CAPABILITY_ID = CapabilityId("macro.interest_rates")


class InterestRateInstrumentType(str, Enum):
    """Economic instrument represented by an interest-rate series."""

    POLICY_TARGET = "policy_target"
    EFFECTIVE_RATE = "effective_rate"
    GOVERNMENT_YIELD = "government_yield"


class TenorUnit(str, Enum):
    """Calendar unit used to state an interest-rate tenor."""

    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


@dataclass(frozen=True, order=True, slots=True)
class InterestRateTenor:
    """Exact maturity or tenor associated with an interest-rate observation."""

    length: int
    unit: TenorUnit

    def __post_init__(self) -> None:
        if isinstance(self.length, bool) or self.length <= 0:
            raise ValueError("Interest-rate tenor length must be positive")


class InterestRateQuotation(str, Enum):
    """Value-affecting quotation convention for an interest-rate series."""

    POLICY_TARGET = "policy_target"
    EFFECTIVE_RATE = "effective_rate"
    PAR_YIELD = "par_yield"
    ZERO_COUPON_YIELD = "zero_coupon_yield"
    DISCOUNT_YIELD = "discount_yield"
    YIELD_TO_MATURITY = "yield_to_maturity"


class CompoundingMethod(str, Enum):
    """Method used to compound or annualize a quoted interest rate."""

    NOT_APPLICABLE = "not_applicable"
    SIMPLE = "simple"
    DISCRETE = "discrete"
    CONTINUOUS = "continuous"


@dataclass(frozen=True, slots=True)
class InterestRateCompounding:
    """Exact compounding method, including frequency when it is discrete."""

    method: CompoundingMethod
    periods_per_year: int | None = None

    def __post_init__(self) -> None:
        if self.method is CompoundingMethod.DISCRETE:
            if (
                isinstance(self.periods_per_year, bool)
                or self.periods_per_year is None
                or self.periods_per_year <= 0
            ):
                raise ValueError("Discrete compounding requires positive periods per year")
        elif self.periods_per_year is not None:
            raise ValueError("Only discrete compounding accepts periods per year")


class InterestRateOrdering(str, Enum):
    """Requested deterministic ordering of interest-rate observations."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


@dataclass(frozen=True, slots=True)
class InterestRateQuery:
    """Typed query for a half-open range of interest-rate observation periods."""

    series: MacroSeriesIdentifier
    observation_start: date
    observation_end: date
    as_of: datetime | None = None
    geography: GeographyIdentifier | None = None
    instrument_type: InterestRateInstrumentType | None = None
    tenor: InterestRateTenor | None = None
    unit: MacroUnitMetadata | None = None
    quotation: InterestRateQuotation | None = None
    compounding: InterestRateCompounding | None = None
    ordering: InterestRateOrdering = InterestRateOrdering.ASCENDING

    def __post_init__(self) -> None:
        if isinstance(self.observation_start, datetime) or isinstance(
            self.observation_end, datetime
        ):
            raise InvalidCapabilityQueryError("Interest-rate observation bounds must be dates")
        if self.observation_end <= self.observation_start:
            raise InvalidCapabilityQueryError(
                "Interest-rate observation end must be later than its start"
            )
        if self.as_of is not None and (self.as_of.tzinfo is None or self.as_of.utcoffset() is None):
            raise InvalidCapabilityQueryError("Interest-rate as-of time must be timezone-aware")
        if (
            self.instrument_type is InterestRateInstrumentType.POLICY_TARGET
            and self.tenor is not None
        ):
            raise InvalidCapabilityQueryError("Policy-target queries must not specify a tenor")
        if (
            self.instrument_type is InterestRateInstrumentType.POLICY_TARGET
            and self.quotation not in (None, InterestRateQuotation.POLICY_TARGET)
        ):
            raise InvalidCapabilityQueryError(
                "Policy-target queries require the policy-target quotation"
            )
        if (
            self.instrument_type is InterestRateInstrumentType.EFFECTIVE_RATE
            and self.quotation not in (None, InterestRateQuotation.EFFECTIVE_RATE)
        ):
            raise InvalidCapabilityQueryError(
                "Effective-rate queries require the effective-rate quotation"
            )
        if (
            self.instrument_type is InterestRateInstrumentType.GOVERNMENT_YIELD
            and self.quotation
            in (
                InterestRateQuotation.POLICY_TARGET,
                InterestRateQuotation.EFFECTIVE_RATE,
            )
        ):
            raise InvalidCapabilityQueryError("Government-yield queries require a yield quotation")


@dataclass(frozen=True, slots=True)
class InterestRateRecord:
    """One normalized interest-rate observation with exact measurement conventions."""

    metadata: MacroDataMetadata
    value: Decimal
    instrument_type: InterestRateInstrumentType
    tenor: InterestRateTenor | None
    quotation: InterestRateQuotation
    compounding: InterestRateCompounding

    def __post_init__(self) -> None:
        if not self.value.is_finite():
            raise ValueError("Interest-rate value must be finite")
        if self.instrument_type is InterestRateInstrumentType.POLICY_TARGET:
            if self.tenor is not None:
                raise ValueError("Policy-target observations must not specify a tenor")
            if self.quotation is not InterestRateQuotation.POLICY_TARGET:
                raise ValueError("Policy-target observations require the policy-target quotation")
        elif self.instrument_type is InterestRateInstrumentType.EFFECTIVE_RATE:
            if self.quotation is not InterestRateQuotation.EFFECTIVE_RATE:
                raise ValueError("Effective-rate observations require the effective-rate quotation")
        else:
            if self.tenor is None:
                raise ValueError("Government-yield observations require a tenor")
            if self.quotation in (
                InterestRateQuotation.POLICY_TARGET,
                InterestRateQuotation.EFFECTIVE_RATE,
            ):
                raise ValueError("Government-yield observations require a yield quotation")

        revision = self.metadata.revision
        if (
            revision is not None
            and revision.vintage_at is not None
            and revision.vintage_at > self.metadata.available_at
        ):
            raise ValueError("Interest-rate revision vintage must not follow its availability time")


def _record_matches_query(record: InterestRateRecord, query: InterestRateQuery) -> None:
    metadata = record.metadata
    period = metadata.observation_period
    if period.start < query.observation_start or period.end > query.observation_end:
        raise ProviderResponseError(
            "Interest-rate result contains an observation outside the requested bounds"
        )
    if query.geography is not None and metadata.geography != query.geography:
        raise ProviderResponseError(
            "Interest-rate result contains a record for an unrequested geography"
        )
    if query.instrument_type is not None and record.instrument_type is not query.instrument_type:
        raise ProviderResponseError("Interest-rate result contains an unrequested instrument type")
    if query.tenor is not None and record.tenor != query.tenor:
        raise ProviderResponseError("Interest-rate result contains an unrequested tenor")
    if query.unit is not None and metadata.unit != query.unit:
        raise ProviderResponseError("Interest-rate result contains an unrequested unit")
    if query.quotation is not None and record.quotation is not query.quotation:
        raise ProviderResponseError("Interest-rate result contains an unrequested quotation")
    if query.compounding is not None and record.compounding != query.compounding:
        raise ProviderResponseError(
            "Interest-rate result contains an unrequested compounding convention"
        )


def _latest_vintage_key(record: InterestRateRecord) -> tuple[datetime, datetime, int, str]:
    metadata = record.metadata
    revision = metadata.revision
    vintage_at = revision.vintage_at if revision is not None else None
    release_sequence = revision.release_sequence if revision is not None else None
    return (
        metadata.available_at,
        vintage_at or datetime.min.replace(tzinfo=timezone.utc),
        release_sequence if release_sequence is not None else -1,
        metadata.source.source_record_id or "",
    )


def _apply_query_to_result(
    query: InterestRateQuery,
    result: MacroDataResult[InterestRateRecord],
) -> MacroDataResult[InterestRateRecord]:
    if result.series != query.series:
        raise ProviderResponseError(
            "Interest-rate result series does not match the requested series"
        )

    records = tuple(result.records)
    for record in records:
        _record_matches_query(record, query)

    if query.as_of is not None:
        eligible = (record for record in records if record.metadata.available_at <= query.as_of)
        latest_by_period: dict[ObservationPeriod, InterestRateRecord] = {}
        for record in eligible:
            period = record.metadata.observation_period
            current = latest_by_period.get(period)
            if current is None or _latest_vintage_key(record) > _latest_vintage_key(current):
                latest_by_period[period] = record
        records = tuple(latest_by_period.values())

    availability = result.availability
    reason = result.reason
    if availability is MacroDataAvailability.PARTIAL and not records:
        availability = MacroDataAvailability.UNAVAILABLE

    normalized = MacroDataResult(
        series=result.series,
        source=result.source,
        availability=availability,
        records=records,
        reason=reason,
    )
    if query.ordering is InterestRateOrdering.DESCENDING:
        object.__setattr__(normalized, "records", tuple(reversed(normalized.records)))
    return normalized


class InterestRatesCapability(Capability, ABC):
    """Provider contract for normalized policy-rate and government-yield series."""

    @property
    def id(self) -> CapabilityId:
        return INTEREST_RATES_CAPABILITY_ID

    def get_interest_rates(self, query: InterestRateQuery) -> MacroDataResult[InterestRateRecord]:
        """Return validated records honoring bounds, variants, order, and as-of time."""
        return _apply_query_to_result(query, self._get_interest_rates(query))

    @abstractmethod
    def _get_interest_rates(self, query: InterestRateQuery) -> MacroDataResult[InterestRateRecord]:
        """Fetch normalized provider records before common query enforcement."""
        raise NotImplementedError


__all__ = [
    "CompoundingMethod",
    "INTEREST_RATES_CAPABILITY_ID",
    "InterestRateCompounding",
    "InterestRateInstrumentType",
    "InterestRateOrdering",
    "InterestRateQuery",
    "InterestRateQuotation",
    "InterestRateRecord",
    "InterestRateTenor",
    "InterestRatesCapability",
    "TenorUnit",
]
