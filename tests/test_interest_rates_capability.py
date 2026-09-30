import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from tbt_engine import SourceMetadata
from tbt_engine.core.errors import InvalidCapabilityQueryError, ProviderResponseError
from tbt_engine.providers.capabilities.macro.interest_rates import (
    INTEREST_RATES_CAPABILITY_ID,
    CompoundingMethod,
    InterestRateCompounding,
    InterestRateInstrumentType,
    InterestRateOrdering,
    InterestRateQuery,
    InterestRateQuotation,
    InterestRateRecord,
    InterestRatesCapability,
    InterestRateTenor,
    TenorUnit,
)
from tbt_engine.providers.capabilities.macro.macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataResult,
    MacroRevisionMetadata,
    MacroUnitMetadata,
    ObservationPeriod,
    SeasonalAdjustmentStatus,
)
from tbt_engine.providers.capabilities.macro.macro_identifier import (
    GeographyIdentifier,
    MacroSeriesIdentifier,
)


class FixedInterestRatesCapability(InterestRatesCapability):
    def __init__(self, result: MacroDataResult[InterestRateRecord]) -> None:
        self.result = result
        self.queries: list[InterestRateQuery] = []

    def _get_interest_rates(self, query: InterestRateQuery) -> MacroDataResult[InterestRateRecord]:
        self.queries.append(query)
        return self.result


class InterestRatesCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.series = MacroSeriesIdentifier("fred", "DGS10")
        self.geography = GeographyIdentifier("iso-3166-1-alpha-2", "US")
        self.source = SourceMetadata(
            provider="test-provider",
            source="test-rates",
            retrieved_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
        )
        self.unit = MacroUnitMetadata("percent")
        self.tenor = InterestRateTenor(10, TenorUnit.YEARS)
        self.compounding = InterestRateCompounding(CompoundingMethod.SIMPLE)

    def metadata(
        self,
        *,
        period: ObservationPeriod | None = None,
        available_at: datetime | None = None,
        vintage_at: datetime | None = None,
        release_sequence: int | None = None,
        series: MacroSeriesIdentifier | None = None,
        geography: GeographyIdentifier | None = None,
        unit: MacroUnitMetadata | None = None,
        source_record_id: str | None = None,
    ) -> MacroDataMetadata:
        available_at = available_at or datetime(2025, 1, 3, 21, tzinfo=timezone.utc)
        return MacroDataMetadata(
            series=series or self.series,
            source=SourceMetadata(
                provider=self.source.provider,
                source=self.source.source,
                retrieved_at=self.source.retrieved_at,
                source_record_id=source_record_id,
            ),
            observation_period=period or ObservationPeriod(date(2025, 1, 2), date(2025, 1, 3)),
            published_at=available_at,
            available_at=available_at,
            revision=MacroRevisionMetadata(
                vintage_at=vintage_at,
                release_sequence=release_sequence,
            ),
            unit=unit or self.unit,
            geography=geography or self.geography,
            seasonal_adjustment=SeasonalAdjustmentStatus.NOT_APPLICABLE,
        )

    def yield_record(
        self,
        *,
        value: str = "4.25",
        **metadata_overrides: object,
    ) -> InterestRateRecord:
        return InterestRateRecord(
            metadata=self.metadata(**metadata_overrides),  # type: ignore[arg-type]
            value=Decimal(value),
            instrument_type=InterestRateInstrumentType.GOVERNMENT_YIELD,
            tenor=self.tenor,
            quotation=InterestRateQuotation.PAR_YIELD,
            compounding=self.compounding,
        )

    def result(
        self,
        records: tuple[InterestRateRecord, ...],
        *,
        availability: MacroDataAvailability = MacroDataAvailability.AVAILABLE,
        reason: str | None = None,
        series: MacroSeriesIdentifier | None = None,
    ) -> MacroDataResult[InterestRateRecord]:
        return MacroDataResult(
            series=series or self.series,
            source=self.source,
            availability=availability,
            records=records,
            reason=reason,
        )

    def query(self, **overrides: object) -> InterestRateQuery:
        values: dict[str, object] = {
            "series": self.series,
            "observation_start": date(2025, 1, 1),
            "observation_end": date(2025, 2, 1),
            "geography": self.geography,
            "instrument_type": InterestRateInstrumentType.GOVERNMENT_YIELD,
            "tenor": self.tenor,
            "unit": self.unit,
            "quotation": InterestRateQuotation.PAR_YIELD,
            "compounding": self.compounding,
        }
        values.update(overrides)
        return InterestRateQuery(**values)  # type: ignore[arg-type]

    def test_capability_has_stable_identifier_and_one_provider_method(self) -> None:
        capability = FixedInterestRatesCapability(self.result(()))

        query = self.query()
        self.assertEqual(capability.id, INTEREST_RATES_CAPABILITY_ID)
        self.assertEqual(capability.get_interest_rates(query).records, ())
        self.assertEqual(capability.queries, [query])
        self.assertEqual(
            InterestRatesCapability.__abstractmethods__, frozenset({"_get_interest_rates"})
        )

    def test_query_validates_half_open_bounds_and_aware_as_of(self) -> None:
        as_of = datetime(2025, 1, 15, tzinfo=timezone.utc)
        query = self.query(as_of=as_of, ordering=InterestRateOrdering.DESCENDING)

        self.assertEqual(query.as_of, as_of)
        with self.assertRaises(InvalidCapabilityQueryError):
            self.query(observation_end=date(2025, 1, 1))
        with self.assertRaises(InvalidCapabilityQueryError):
            self.query(observation_start=datetime(2025, 1, 1))
        with self.assertRaises(InvalidCapabilityQueryError):
            self.query(as_of=datetime(2025, 1, 15))

    def test_query_rejects_incompatible_policy_and_yield_variants(self) -> None:
        with self.assertRaises(InvalidCapabilityQueryError):
            self.query(
                instrument_type=InterestRateInstrumentType.POLICY_TARGET,
                tenor=self.tenor,
                quotation=InterestRateQuotation.POLICY_TARGET,
            )
        with self.assertRaises(InvalidCapabilityQueryError):
            self.query(
                instrument_type=InterestRateInstrumentType.EFFECTIVE_RATE,
                tenor=None,
                quotation=InterestRateQuotation.PAR_YIELD,
            )
        with self.assertRaises(InvalidCapabilityQueryError):
            self.query(quotation=InterestRateQuotation.POLICY_TARGET)

    def test_tenor_and_compounding_conventions_are_exact_and_validated(self) -> None:
        discrete = InterestRateCompounding(CompoundingMethod.DISCRETE, periods_per_year=2)

        self.assertEqual(discrete.periods_per_year, 2)
        with self.assertRaises(ValueError):
            InterestRateTenor(0, TenorUnit.MONTHS)
        with self.assertRaises(ValueError):
            InterestRateCompounding(CompoundingMethod.DISCRETE)
        with self.assertRaises(ValueError):
            InterestRateCompounding(CompoundingMethod.CONTINUOUS, periods_per_year=1)

    def test_records_keep_policy_effective_and_government_rates_distinct(self) -> None:
        metadata = self.metadata()
        policy = InterestRateRecord(
            metadata=metadata,
            value=Decimal("5.25"),
            instrument_type=InterestRateInstrumentType.POLICY_TARGET,
            tenor=None,
            quotation=InterestRateQuotation.POLICY_TARGET,
            compounding=InterestRateCompounding(CompoundingMethod.NOT_APPLICABLE),
        )
        effective = InterestRateRecord(
            metadata=metadata,
            value=Decimal("5.33"),
            instrument_type=InterestRateInstrumentType.EFFECTIVE_RATE,
            tenor=InterestRateTenor(1, TenorUnit.DAYS),
            quotation=InterestRateQuotation.EFFECTIVE_RATE,
            compounding=self.compounding,
        )

        self.assertNotEqual(policy.instrument_type, effective.instrument_type)
        with self.assertRaises(ValueError):
            InterestRateRecord(
                metadata=metadata,
                value=Decimal("4.25"),
                instrument_type=InterestRateInstrumentType.GOVERNMENT_YIELD,
                tenor=None,
                quotation=InterestRateQuotation.PAR_YIELD,
                compounding=self.compounding,
            )
        with self.assertRaises(ValueError):
            InterestRateRecord(
                metadata=metadata,
                value=Decimal("NaN"),
                instrument_type=InterestRateInstrumentType.POLICY_TARGET,
                tenor=None,
                quotation=InterestRateQuotation.POLICY_TARGET,
                compounding=self.compounding,
            )

    def test_record_rejects_revision_known_after_availability(self) -> None:
        with self.assertRaisesRegex(ValueError, "vintage"):
            self.yield_record(
                available_at=datetime(2025, 1, 3, 21, tzinfo=timezone.utc),
                vintage_at=datetime(2025, 1, 4, tzinfo=timezone.utc),
            )

    def test_as_of_selects_latest_eligible_vintage_without_lookahead(self) -> None:
        period = ObservationPeriod(date(2025, 1, 2), date(2025, 1, 3))
        advance = self.yield_record(
            value="4.20",
            period=period,
            available_at=datetime(2025, 1, 3, 21, tzinfo=timezone.utc),
            vintage_at=datetime(2025, 1, 3, 20, tzinfo=timezone.utc),
            release_sequence=0,
            source_record_id="advance",
        )
        revision = self.yield_record(
            value="4.25",
            period=period,
            available_at=datetime(2025, 1, 10, 21, tzinfo=timezone.utc),
            vintage_at=datetime(2025, 1, 10, 20, tzinfo=timezone.utc),
            release_sequence=1,
            source_record_id="revision",
        )
        future = self.yield_record(
            value="4.30",
            period=period,
            available_at=datetime(2025, 1, 20, 21, tzinfo=timezone.utc),
            vintage_at=datetime(2025, 1, 20, 20, tzinfo=timezone.utc),
            release_sequence=2,
            source_record_id="future",
        )
        capability = FixedInterestRatesCapability(self.result((future, advance, revision)))

        result = capability.get_interest_rates(
            self.query(as_of=datetime(2025, 1, 15, tzinfo=timezone.utc))
        )

        self.assertEqual(result.records, (revision,))

    def test_query_ordering_is_deterministic(self) -> None:
        january = self.yield_record()
        february = self.yield_record(
            period=ObservationPeriod(date(2025, 1, 3), date(2025, 1, 4)),
            available_at=datetime(2025, 1, 4, 21, tzinfo=timezone.utc),
        )
        capability = FixedInterestRatesCapability(self.result((february, january)))

        ascending = capability.get_interest_rates(self.query())
        descending = capability.get_interest_rates(
            self.query(ordering=InterestRateOrdering.DESCENDING)
        )

        self.assertEqual(ascending.records, (january, february))
        self.assertEqual(descending.records, (february, january))

    def test_result_boundary_rejects_mismatched_series_bounds_and_variants(self) -> None:
        other_series = MacroSeriesIdentifier("fred", "DGS2")
        with self.assertRaisesRegex(ProviderResponseError, "series"):
            FixedInterestRatesCapability(self.result((), series=other_series)).get_interest_rates(
                self.query()
            )

        outside = self.yield_record(period=ObservationPeriod(date(2024, 12, 1), date(2025, 1, 1)))
        with self.assertRaisesRegex(ProviderResponseError, "bounds"):
            FixedInterestRatesCapability(self.result((outside,))).get_interest_rates(self.query())

        wrong_tenor = InterestRateRecord(
            metadata=self.metadata(),
            value=Decimal("4.25"),
            instrument_type=InterestRateInstrumentType.GOVERNMENT_YIELD,
            tenor=InterestRateTenor(2, TenorUnit.YEARS),
            quotation=InterestRateQuotation.PAR_YIELD,
            compounding=self.compounding,
        )
        with self.assertRaisesRegex(ProviderResponseError, "tenor"):
            FixedInterestRatesCapability(self.result((wrong_tenor,))).get_interest_rates(
                self.query()
            )

    def test_partial_result_without_as_of_eligible_records_becomes_unavailable(self) -> None:
        future = self.yield_record(available_at=datetime(2025, 1, 20, 21, tzinfo=timezone.utc))
        capability = FixedInterestRatesCapability(
            self.result(
                (future,),
                availability=MacroDataAvailability.PARTIAL,
                reason="Some provider vintages are unavailable",
            )
        )

        result = capability.get_interest_rates(
            self.query(as_of=datetime(2025, 1, 15, tzinfo=timezone.utc))
        )

        self.assertEqual(result.availability, MacroDataAvailability.UNAVAILABLE)
        self.assertEqual(result.records, ())


if __name__ == "__main__":
    unittest.main()
