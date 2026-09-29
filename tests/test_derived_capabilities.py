import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId
from tbt_engine.providers.capabilities.derived.calculations import (
    CalculationIdentity,
    CalculationParameter,
)
from tbt_engine.providers.capabilities.derived.capabilities import DerivedCapabilities
from tbt_engine.providers.capabilities.derived.inputs import (
    DerivedInput,
    InputSeriesRef,
    SeriesQualifier,
)
from tbt_engine.providers.capabilities.derived.results import (
    DerivedDataAvailability,
    DerivedDataRequestContext,
    DerivedDataResult,
    DerivedRecordMetadata,
    EarlyOutputHandling,
    InputProvenance,
    InsufficientWarmUpHandling,
    WarmUpMetadata,
    WarmUpRequirement,
    require_finite,
)

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 2, 1, tzinfo=UTC)


class StubCapability(Capability):
    def __init__(self, identifier: str) -> None:
        self._id = CapabilityId(identifier)

    @property
    def id(self) -> CapabilityId:
        return self._id


@dataclass(frozen=True, slots=True)
class StubRecord:
    metadata: DerivedRecordMetadata
    value: float

    def __post_init__(self) -> None:
        require_finite(self.value)


class DerivedContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SourceMetadata("local", "fixture", START)
        self.close = InputSeriesRef(
            " market.ohlcv ",
            " AAPL ",
            " CLOSE ",
            qualifiers=(
                SeriesQualifier("interval", "1d"),
                SeriesQualifier("adjustment", "split-adjusted"),
            ),
        )
        self.input = DerivedInput(" source ", self.close)
        self.calculation = CalculationIdentity(
            " SMA ",
            " V1 ",
            parameters=(CalculationParameter("window", "20"),),
        )
        self.requirement = WarmUpRequirement(
            20,
            True,
            EarlyOutputHandling.OMITTED,
            InsufficientWarmUpHandling.PARTIAL_WHEN_RECORDS_EXIST,
        )
        self.request = DerivedDataRequestContext(
            inputs=(self.input,),
            calculation=self.calculation,
            output_start=START,
            output_end=END,
            warm_up=self.requirement,
        )

    def record(self, day: int = 2) -> StubRecord:
        observed = START + timedelta(days=day)
        available = observed + timedelta(hours=1)
        metadata = DerivedRecordMetadata(
            source=self.source,
            inputs=(InputProvenance(self.input, observed, available),),
            calculation=self.calculation,
            observation_time=observed,
            availability_time=available,
            warm_up=WarmUpMetadata(self.requirement, 20, 19),
        )
        return StubRecord(metadata, 101.25)

    def test_input_identity_is_normalized_hashable_and_deterministic(self) -> None:
        reversed_identity = InputSeriesRef(
            "market.ohlcv",
            "aapl",
            "close",
            reversed(self.close.qualifiers),
        )

        self.assertEqual(self.close, reversed_identity)
        self.assertEqual(self.close.series, "aapl")
        self.assertEqual(hash(self.close), hash(reversed_identity))

    def test_input_identity_rejects_duplicate_qualifier_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "qualifier names must be unique"):
            InputSeriesRef(
                "market.ohlcv",
                "aapl",
                "close",
                (
                    SeriesQualifier("interval", "1d"),
                    SeriesQualifier("interval", "1h"),
                ),
            )

    def test_calculation_identity_canonicalizes_parameter_order(self) -> None:
        left = CalculationIdentity(
            "volatility",
            "v1",
            (
                CalculationParameter("window", "20"),
                CalculationParameter("method", "log"),
            ),
        )
        right = CalculationIdentity(
            " VOLATILITY ",
            " V1 ",
            reversed(left.parameters),
        )

        self.assertEqual(left, right)
        with self.assertRaisesRegex(ValueError, "parameter names must be unique"):
            CalculationIdentity(
                "volatility",
                "v1",
                (
                    CalculationParameter("window", "20"),
                    CalculationParameter("window", "30"),
                ),
            )

    def test_request_snapshots_inputs_and_uses_inclusive_exclusive_bounds(self) -> None:
        mutable_inputs = [self.input]
        request = DerivedDataRequestContext(
            mutable_inputs,
            self.calculation,
            START,
            END,
            self.requirement,
        )
        mutable_inputs.clear()

        self.assertEqual(request.inputs, (self.input,))
        end_record = self.record()
        end_input = InputProvenance(self.input, END, END + timedelta(hours=1))
        end_metadata = DerivedRecordMetadata(
            self.source,
            (end_input,),
            self.calculation,
            END,
            END + timedelta(hours=1),
            end_record.metadata.warm_up,
        )
        with self.assertRaisesRegex(ValueError, "outside the requested output bounds"):
            DerivedDataResult(
                request,
                self.source,
                DerivedDataAvailability.AVAILABLE,
                (StubRecord(end_metadata, 1.0),),
            )

    def test_request_requires_aware_ordered_bounds_and_unique_roles(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            DerivedDataRequestContext(
                (self.input,),
                self.calculation,
                datetime(2026, 1, 1),
                END,
                self.requirement,
            )
        with self.assertRaisesRegex(ValueError, "earlier"):
            DerivedDataRequestContext((self.input,), self.calculation, END, START, self.requirement)
        with self.assertRaisesRegex(ValueError, "roles must be unique"):
            DerivedDataRequestContext(
                (self.input, self.input), self.calculation, START, END, self.requirement
            )

    def test_warm_up_metadata_proves_the_declared_requirement(self) -> None:
        with self.assertRaisesRegex(ValueError, "fewer observations"):
            WarmUpMetadata(self.requirement, 19, 19)
        with self.assertRaisesRegex(ValueError, "conflicts"):
            WarmUpMetadata(
                WarmUpRequirement(
                    1,
                    False,
                    EarlyOutputHandling.OMITTED,
                    InsufficientWarmUpHandling.UNAVAILABLE,
                ),
                1,
                1,
            )

    def test_record_enforces_point_in_time_timestamps(self) -> None:
        future = START + timedelta(days=3)
        with self.assertRaisesRegex(ValueError, "Future input"):
            DerivedRecordMetadata(
                self.source,
                (InputProvenance(self.input, future, future),),
                self.calculation,
                START + timedelta(days=2),
                future,
                WarmUpMetadata(self.requirement, 20, 19),
            )
        observed = START + timedelta(days=2)
        with self.assertRaisesRegex(ValueError, "before all inputs"):
            DerivedRecordMetadata(
                self.source,
                (InputProvenance(self.input, observed, observed + timedelta(hours=2)),),
                self.calculation,
                observed,
                observed + timedelta(hours=1),
                WarmUpMetadata(self.requirement, 20, 19),
            )

    def test_alternate_timestamp_rule_is_part_of_calculation_identity(self) -> None:
        alternate = CalculationIdentity(
            "sma",
            "v1",
            (CalculationParameter("window", "20"),),
            observation_time_rule="period_end",
        )
        self.assertNotEqual(alternate, self.calculation)
        observed = START + timedelta(days=2)
        metadata = DerivedRecordMetadata(
            self.source,
            (InputProvenance(self.input, observed, observed),),
            alternate,
            observed + timedelta(hours=4),
            observed + timedelta(hours=4),
            WarmUpMetadata(self.requirement, 20, 19),
        )
        self.assertEqual(metadata.calculation.observation_time_rule, "period_end")

    def test_results_snapshot_records_and_validate_availability_states(self) -> None:
        mutable_records = [self.record()]
        partial = DerivedDataResult(
            self.request,
            self.source,
            DerivedDataAvailability.PARTIAL,
            mutable_records,
            "insufficient coverage for later outputs",
        )
        mutable_records.clear()
        self.assertEqual(len(partial.records), 1)

        empty = DerivedDataResult(self.request, self.source, DerivedDataAvailability.AVAILABLE)
        self.assertEqual(empty.records, ())
        with self.assertRaisesRegex(ValueError, "Available.*must not have a reason"):
            DerivedDataResult(
                self.request,
                self.source,
                DerivedDataAvailability.AVAILABLE,
                reason="unexpected",
            )
        with self.assertRaisesRegex(ValueError, "Partial.*require records"):
            DerivedDataResult(
                self.request,
                self.source,
                DerivedDataAvailability.PARTIAL,
                reason="no records",
            )
        with self.assertRaisesRegex(ValueError, "Unavailable.*require no records"):
            DerivedDataResult(
                self.request,
                self.source,
                DerivedDataAvailability.UNAVAILABLE,
                (self.record(),),
                "not supported upstream",
            )

    def test_results_require_strict_order_and_matching_request_identity(self) -> None:
        later = self.record(3)
        earlier = self.record(2)
        with self.assertRaisesRegex(ValueError, "strictly ordered and unique"):
            DerivedDataResult(
                self.request,
                self.source,
                DerivedDataAvailability.AVAILABLE,
                (later, earlier),
            )
        with self.assertRaisesRegex(ValueError, "strictly ordered and unique"):
            DerivedDataResult(
                self.request,
                self.source,
                DerivedDataAvailability.AVAILABLE,
                (earlier, earlier),
            )

        other_calculation = CalculationIdentity("ema", "v1")
        other_metadata = DerivedRecordMetadata(
            self.source,
            earlier.metadata.inputs,
            other_calculation,
            earlier.metadata.observation_time,
            earlier.metadata.availability_time,
            earlier.metadata.warm_up,
        )
        with self.assertRaisesRegex(ValueError, "calculation does not match"):
            DerivedDataResult(
                self.request,
                self.source,
                DerivedDataAvailability.AVAILABLE,
                (StubRecord(other_metadata, 1.0),),
            )

    def test_numeric_leaf_records_reject_non_finite_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            StubRecord(self.record().metadata, float("nan"))

    def test_derived_collection_accepts_only_known_identifiers_in_stable_order(self) -> None:
        collection = DerivedCapabilities(
            "provider",
            (StubCapability("derived.sma"), StubCapability("derived.rsi")),
        )
        self.assertEqual(
            tuple(str(capability.id) for capability in collection.capabilities),
            ("derived.rsi", "derived.sma"),
        )
        with self.assertRaisesRegex(ValueError, "Unsupported derived capability"):
            DerivedCapabilities("provider", (StubCapability("market.ohlcv"),))
        with self.assertRaisesRegex(ValueError, "Unsupported derived capability"):
            DerivedCapabilities("provider", (StubCapability("derived.unknown"),))


if __name__ == "__main__":
    unittest.main()
