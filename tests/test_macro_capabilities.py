import unittest
from dataclasses import FrozenInstanceError, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from tbt_engine import SourceMetadata, UnsupportedCapabilityError
from tbt_engine.providers.capabilities import Capability, CapabilityId
from tbt_engine.providers.capabilities.macro.macro_capabilities import MacroCapabilities
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

INTEREST_RATES = CapabilityId("macro.interest_rates")


class InterestRateCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return INTEREST_RATES


class CompanyCapability(Capability):
    @property
    def id(self) -> CapabilityId:
        return CapabilityId("company.dividends")


@dataclass(frozen=True, slots=True)
class ExampleMacroRecord:
    metadata: MacroDataMetadata
    value: Decimal


class MacroCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.series = MacroSeriesIdentifier(" fred ", " GDP ", variant=" nominal ")
        self.source = SourceMetadata(
            provider="test-provider",
            source="test-dataset",
            retrieved_at=datetime(2026, 9, 28, tzinfo=timezone.utc),
        )
        self.period = ObservationPeriod(date(2025, 1, 1), date(2025, 4, 1))
        self.unit = MacroUnitMetadata(" USD ", multiplier=Decimal("1000000000"), currency="usd")

    def metadata(
        self,
        *,
        series: MacroSeriesIdentifier | None = None,
        source: SourceMetadata | None = None,
        period: ObservationPeriod | None = None,
        available_at: datetime | None = None,
        vintage_at: datetime | None = None,
        release_sequence: int | None = None,
    ) -> MacroDataMetadata:
        published_at = datetime(2025, 4, 30, 12, 30, tzinfo=timezone.utc)
        return MacroDataMetadata(
            series=series or self.series,
            source=source or self.source,
            observation_period=period or self.period,
            published_at=published_at,
            available_at=available_at or published_at,
            revision=MacroRevisionMetadata(
                vintage_at=vintage_at,
                release_sequence=release_sequence,
                status=" advance ",
            ),
            unit=self.unit,
            geography=GeographyIdentifier(" iso-3166-1-alpha-2 ", " US "),
            seasonal_adjustment=SeasonalAdjustmentStatus.ADJUSTED,
        )

    def test_macro_capabilities_accept_only_macro_namespace(self) -> None:
        capability = InterestRateCapability()
        capabilities = MacroCapabilities("provider", (capability,))

        self.assertIs(capabilities.require(InterestRateCapability), capability)
        self.assertFalse(capabilities.supports(CapabilityId("macro.gdp")))
        with self.assertRaises(UnsupportedCapabilityError):
            capabilities.require(CapabilityId("macro.gdp"))
        with self.assertRaisesRegex(ValueError, "'macro.' namespace"):
            MacroCapabilities("provider", (CompanyCapability(),))

    def test_macro_and_geography_identifiers_are_explicit_and_normalized(self) -> None:
        self.assertEqual(self.series.namespace, "fred")
        self.assertEqual(self.series.value, "GDP")
        self.assertEqual(self.series.variant, "nominal")
        self.assertEqual(
            GeographyIdentifier(" ISO-3166-1-ALPHA-2 ", " US "),
            GeographyIdentifier("iso-3166-1-alpha-2", "US"),
        )

    def test_identifiers_reject_missing_or_invalid_components(self) -> None:
        invalid_series = (
            ("", "GDP", None),
            ("not a scheme", "GDP", None),
            ("fred", "", None),
            ("fred", "GDP", " "),
        )
        for namespace, value, variant in invalid_series:
            with self.subTest(namespace=namespace, value=value, variant=variant):
                with self.assertRaises(ValueError):
                    MacroSeriesIdentifier(namespace, value, variant)

        with self.assertRaises(ValueError):
            GeographyIdentifier("", "US")
        with self.assertRaises(ValueError):
            GeographyIdentifier("iso", "")

    def test_observation_period_uses_inclusive_start_exclusive_end_dates(self) -> None:
        self.assertEqual(self.period.start, date(2025, 1, 1))
        self.assertEqual(self.period.end, date(2025, 4, 1))
        with self.assertRaises(ValueError):
            ObservationPeriod(date(2025, 1, 1), date(2025, 1, 1))
        with self.assertRaises(TypeError):
            ObservationPeriod(datetime(2025, 1, 1), date(2025, 2, 1))

    def test_revision_and_unit_metadata_validate_and_normalize_values(self) -> None:
        revision = MacroRevisionMetadata(
            vintage_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
            release_sequence=0,
            status=" preliminary ",
            superseded_record_id=" old-record ",
        )

        self.assertEqual(revision.status, "preliminary")
        self.assertEqual(revision.superseded_record_id, "old-record")
        self.assertEqual(self.unit.unit, "USD")
        self.assertEqual(self.unit.currency, "USD")
        with self.assertRaises(ValueError):
            MacroRevisionMetadata(vintage_at=datetime(2025, 5, 1))
        with self.assertRaises(ValueError):
            MacroRevisionMetadata(release_sequence=-1)
        with self.assertRaises(ValueError):
            MacroRevisionMetadata(status=" ")
        with self.assertRaises(ValueError):
            MacroUnitMetadata(" ")
        with self.assertRaises(ValueError):
            MacroUnitMetadata("USD", multiplier=Decimal("0"))
        with self.assertRaises(FrozenInstanceError):
            revision.status = "final"  # type: ignore[misc]

    def test_macro_metadata_enforces_point_in_time_semantics(self) -> None:
        metadata = self.metadata()

        self.assertEqual(metadata.seasonal_adjustment, SeasonalAdjustmentStatus.ADJUSTED)
        with self.assertRaises(ValueError):
            self.metadata(available_at=datetime(2025, 4, 30, 12, 29, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            MacroDataMetadata(
                series=self.series,
                source=self.source,
                observation_period=self.period,
                published_at=datetime(2025, 4, 30, 12, 30),
                available_at=datetime(2025, 4, 30, 12, 30, tzinfo=timezone.utc),
                unit=self.unit,
                seasonal_adjustment=SeasonalAdjustmentStatus.UNKNOWN,
            )
        with self.assertRaises(ValueError):
            MacroDataMetadata(
                series=self.series,
                source=self.source,
                observation_period=self.period,
                available_at=datetime(2025, 4, 30, 12, 30),
                unit=self.unit,
                seasonal_adjustment=SeasonalAdjustmentStatus.UNKNOWN,
            )

    def test_result_distinguishes_available_partial_and_unavailable_data(self) -> None:
        record = ExampleMacroRecord(self.metadata(), Decimal("100"))
        available = MacroDataResult[ExampleMacroRecord](
            series=self.series,
            source=self.source,
            availability=MacroDataAvailability.AVAILABLE,
        )
        partial = MacroDataResult(
            series=self.series,
            source=self.source,
            availability=MacroDataAvailability.PARTIAL,
            records=(record,),
            reason="Some periods are unavailable",
        )
        unavailable = MacroDataResult[ExampleMacroRecord](
            series=self.series,
            source=self.source,
            availability=MacroDataAvailability.UNAVAILABLE,
            reason="Series is outside provider coverage",
        )

        self.assertEqual(available.records, ())
        self.assertEqual(partial.records, (record,))
        self.assertEqual(unavailable.reason, "Series is outside provider coverage")
        with self.assertRaises(ValueError):
            MacroDataResult[ExampleMacroRecord](
                self.series,
                self.source,
                MacroDataAvailability.PARTIAL,
                reason="No records",
            )
        with self.assertRaises(ValueError):
            MacroDataResult(
                self.series,
                self.source,
                MacroDataAvailability.UNAVAILABLE,
                records=(record,),
                reason="Contradictory result",
            )

    def test_result_validates_identity_source_duplicates_and_ordering(self) -> None:
        first_period = ObservationPeriod(date(2024, 10, 1), date(2025, 1, 1))
        first = ExampleMacroRecord(
            self.metadata(period=first_period, release_sequence=0), Decimal("99")
        )
        revised = ExampleMacroRecord(
            self.metadata(
                vintage_at=datetime(2025, 5, 30, tzinfo=timezone.utc),
                release_sequence=1,
            ),
            Decimal("101"),
        )
        advance = ExampleMacroRecord(
            self.metadata(
                vintage_at=datetime(2025, 4, 30, tzinfo=timezone.utc),
                release_sequence=0,
            ),
            Decimal("100"),
        )

        result = MacroDataResult(
            self.series,
            self.source,
            MacroDataAvailability.AVAILABLE,
            records=(revised, advance, first),
        )
        self.assertEqual(result.records, (first, advance, revised))

        caller_records = [advance]
        snapshot = MacroDataResult[ExampleMacroRecord](
            self.series,
            self.source,
            MacroDataAvailability.AVAILABLE,
            records=caller_records,  # type: ignore[arg-type]
        )
        caller_records.clear()
        self.assertEqual(snapshot.records, (advance,))

        with self.assertRaisesRegex(ValueError, "duplicate observations"):
            MacroDataResult(
                self.series,
                self.source,
                MacroDataAvailability.AVAILABLE,
                records=(advance, advance),
            )
        with self.assertRaisesRegex(ValueError, "duplicate observations"):
            MacroDataResult(
                self.series,
                self.source,
                MacroDataAvailability.AVAILABLE,
                records=(
                    advance,
                    ExampleMacroRecord(
                        self.metadata(
                            vintage_at=datetime(2025, 4, 30, tzinfo=timezone.utc),
                            release_sequence=2,
                        ),
                        Decimal("100.5"),
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "requested series"):
            MacroDataResult(
                self.series,
                self.source,
                MacroDataAvailability.AVAILABLE,
                records=(
                    ExampleMacroRecord(
                        self.metadata(series=MacroSeriesIdentifier("fred", "CPI")),
                        Decimal("1"),
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "result source"):
            MacroDataResult(
                self.series,
                self.source,
                MacroDataAvailability.AVAILABLE,
                records=(
                    ExampleMacroRecord(
                        self.metadata(
                            source=SourceMetadata(
                                provider="test-provider",
                                source="test-dataset",
                                retrieved_at=self.source.retrieved_at + timedelta(seconds=1),
                            )
                        ),
                        Decimal("1"),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
