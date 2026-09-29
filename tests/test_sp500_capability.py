import unittest
from datetime import date, datetime, timedelta, timezone

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.market.market_capabilities import MarketCapabilities
from tbt_engine.providers.capabilities.market.market_data import (
    MarketDataAvailability,
    MarketDataMetadata,
    MarketDataResult,
)
from tbt_engine.providers.capabilities.market.market_identifier import MarketIdentifier
from tbt_engine.providers.capabilities.market.sp500 import (
    SP500_CAPABILITY,
    SP500Calculation,
    SP500Capability,
    SP500ConstituentMembership,
    SP500Interval,
    SP500IntervalAlignment,
    SP500IntervalUnit,
    SP500MembershipScope,
    SP500Observation,
    SP500ObservationType,
    SP500Query,
    SP500RecordType,
    SP500Result,
    SP500ValueUnit,
)


class InMemorySP500Capability(SP500Capability):
    def __init__(self, result: SP500Result) -> None:
        self.result = result
        self.queries: list[SP500Query] = []

    def get_sp500(self, query: SP500Query) -> SP500Result:
        self.queries.append(query)
        return self.result


class SP500CapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = MarketIdentifier("sp-global-index", "SPX")
        self.other_index = MarketIdentifier("sp-global-index", "SPXT")
        self.constituent = MarketIdentifier("ticker", "AAPL", market="XNAS")
        self.start = datetime(2026, 1, 5, 21, tzinfo=timezone.utc)
        self.interval = SP500Interval(
            count=1,
            unit=SP500IntervalUnit.DAY,
            alignment=SP500IntervalAlignment.TRADING_SESSION,
        )
        self.source = SourceMetadata(
            provider="memory",
            source="licensed-sp500-dataset",
            retrieved_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

    def observation_query(self) -> SP500Query:
        return SP500Query(
            market=self.index,
            record_type=SP500RecordType.OBSERVATION,
            start=self.start,
            end=self.start + timedelta(days=3),
            interval=self.interval,
        )

    def membership_query(
        self,
        scope: SP500MembershipScope = SP500MembershipScope.HISTORICAL,
    ) -> SP500Query:
        return SP500Query(
            market=self.index,
            record_type=SP500RecordType.MEMBERSHIP,
            start=date(2026, 1, 1),
            end=date(2026, 2, 1),
            membership_scope=scope,
        )

    def observation(
        self,
        day: int = 0,
        *,
        observation_type: SP500ObservationType = SP500ObservationType.LEVEL,
        calculation: SP500Calculation = SP500Calculation.CLOSING_LEVEL,
        unit: SP500ValueUnit = SP500ValueUnit.INDEX_POINTS,
        value: float = 6_000,
        market: MarketIdentifier | None = None,
    ) -> SP500Observation:
        timestamp = self.start + timedelta(days=day)
        return SP500Observation(
            metadata=MarketDataMetadata(
                market=market or self.index,
                source=self.source,
                effective_at=timestamp,
                available_at=timestamp + timedelta(minutes=1),
            ),
            interval=self.interval,
            observation_type=observation_type,
            value=value,
            unit=unit,
            calculation=calculation,
        )

    def membership(
        self,
        constituent: MarketIdentifier | None = None,
        *,
        start: date = date(2026, 1, 1),
        end: date | None = None,
        scope: SP500MembershipScope = SP500MembershipScope.HISTORICAL,
        market: MarketIdentifier | None = None,
    ) -> SP500ConstituentMembership:
        return SP500ConstituentMembership(
            metadata=MarketDataMetadata(
                market=market or self.index,
                source=self.source,
                effective_at=start,
                available_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
            constituent=constituent or self.constituent,
            scope=scope,
            effective_end=end,
        )

    def result(
        self,
        query: SP500Query,
        *records: SP500Observation | SP500ConstituentMembership,
        market: MarketIdentifier | None = None,
        availability: MarketDataAvailability = MarketDataAvailability.AVAILABLE,
        reason: str | None = None,
    ) -> SP500Result:
        return SP500Result(
            query=query,
            data=MarketDataResult(
                market=market or self.index,
                source=self.source,
                availability=availability,
                records=records,
                reason=reason,
            ),
        )

    def test_capability_has_stable_identity_and_composes_with_market_domain(self) -> None:
        result = self.result(self.observation_query())
        capability = InMemorySP500Capability(result)
        capabilities = MarketCapabilities("memory", (capability,))

        self.assertEqual(capability.id, SP500_CAPABILITY)
        self.assertIs(capabilities.require(SP500Capability), capability)
        self.assertIs(capability.get_sp500(result.query), result)

    def test_query_preserves_exact_index_identity_and_interval_semantics(self) -> None:
        query = self.observation_query()
        interval = query.interval

        self.assertEqual(query.market, self.index)
        self.assertEqual(interval, self.interval)
        self.assertIsNotNone(interval)
        assert interval is not None
        self.assertEqual(interval.alignment, SP500IntervalAlignment.TRADING_SESSION)

    def test_invalid_interval_dimensions_use_shared_query_error(self) -> None:
        invalid_intervals = (
            lambda: SP500Interval(
                0,
                SP500IntervalUnit.DAY,
                SP500IntervalAlignment.TRADING_SESSION,
            ),
            lambda: SP500Interval(
                True,
                SP500IntervalUnit.DAY,
                SP500IntervalAlignment.TRADING_SESSION,
            ),
            lambda: SP500Interval(
                1.5,  # pyright: ignore[reportArgumentType]
                SP500IntervalUnit.DAY,
                SP500IntervalAlignment.TRADING_SESSION,
            ),
            lambda: SP500Interval(
                1,
                "day",  # pyright: ignore[reportArgumentType]
                SP500IntervalAlignment.TRADING_SESSION,
            ),
            lambda: SP500Interval(
                1,
                SP500IntervalUnit.DAY,
                "session",  # pyright: ignore[reportArgumentType]
            ),
        )

        for invalid_interval in invalid_intervals:
            with self.subTest(invalid_interval=invalid_interval):
                with self.assertRaises(InvalidCapabilityQueryError):
                    invalid_interval()

    def test_invalid_query_dimensions_use_shared_query_error(self) -> None:
        invalid_queries = (
            lambda: SP500Query(
                market="SPX",  # pyright: ignore[reportArgumentType]
                record_type=SP500RecordType.OBSERVATION,
                interval=self.interval,
            ),
            lambda: SP500Query(
                market=self.index,
                record_type="observation",  # pyright: ignore[reportArgumentType]
                interval=self.interval,
            ),
            lambda: SP500Query(
                market=self.index,
                record_type=SP500RecordType.OBSERVATION,
            ),
            lambda: SP500Query(
                market=self.index,
                record_type=SP500RecordType.OBSERVATION,
                interval=self.interval,
                membership_scope=SP500MembershipScope.HISTORICAL,
            ),
            lambda: SP500Query(
                market=self.index,
                record_type=SP500RecordType.MEMBERSHIP,
            ),
            lambda: SP500Query(
                market=self.index,
                record_type=SP500RecordType.MEMBERSHIP,
                interval=self.interval,
                membership_scope=SP500MembershipScope.HISTORICAL,
            ),
            lambda: SP500Query(
                market=self.index,
                record_type=SP500RecordType.OBSERVATION,
                interval=self.interval,
                start=datetime(2026, 1, 1),
            ),
            lambda: SP500Query(
                market=self.index,
                record_type=SP500RecordType.OBSERVATION,
                interval=self.interval,
                start=self.start,
                end=self.start,
            ),
            lambda: SP500Query(
                market=self.index,
                record_type=SP500RecordType.MEMBERSHIP,
                start=date(2026, 1, 1),
                end=datetime(2026, 2, 1, tzinfo=timezone.utc),
                membership_scope=SP500MembershipScope.HISTORICAL,
            ),
        )

        for invalid_query in invalid_queries:
            with self.subTest(invalid_query=invalid_query):
                with self.assertRaises(InvalidCapabilityQueryError):
                    invalid_query()

    def test_observation_preserves_level_return_and_provenance_semantics(self) -> None:
        level = self.observation()
        price_return = self.observation(
            observation_type=SP500ObservationType.RETURN,
            calculation=SP500Calculation.SIMPLE_PRICE_RETURN,
            unit=SP500ValueUnit.DECIMAL,
            value=-0.01,
        )

        self.assertEqual(level.timestamp, self.start)
        self.assertEqual(level.value, 6_000.0)
        self.assertEqual(level.unit, SP500ValueUnit.INDEX_POINTS)
        self.assertEqual(price_return.calculation, SP500Calculation.SIMPLE_PRICE_RETURN)
        self.assertEqual(price_return.metadata.source, self.source)

    def test_observation_rejects_invalid_values_and_semantic_combinations(self) -> None:
        invalid_observations = (
            lambda: self.observation(value=float("nan")),
            lambda: self.observation(value=-1),
            lambda: self.observation(unit=SP500ValueUnit.PERCENT),
            lambda: self.observation(calculation=SP500Calculation.SIMPLE_PRICE_RETURN),
            lambda: self.observation(
                observation_type=SP500ObservationType.RETURN,
                calculation=SP500Calculation.SIMPLE_PRICE_RETURN,
                unit=SP500ValueUnit.INDEX_POINTS,
                value=1,
            ),
            lambda: self.observation(
                observation_type=SP500ObservationType.RETURN,
                calculation=SP500Calculation.CLOSING_LEVEL,
                unit=SP500ValueUnit.DECIMAL,
                value=0.01,
            ),
            lambda: SP500Observation(
                metadata=MarketDataMetadata(
                    market=self.index,
                    source=self.source,
                    effective_at=date(2026, 1, 5),
                ),
                interval=self.interval,
                observation_type=SP500ObservationType.LEVEL,
                value=6_000,
                unit=SP500ValueUnit.INDEX_POINTS,
                calculation=SP500Calculation.CLOSING_LEVEL,
            ),
        )

        for invalid_observation in invalid_observations:
            with self.subTest(invalid_observation=invalid_observation):
                with self.assertRaises(ValueError):
                    invalid_observation()

    def test_historical_membership_uses_inclusive_start_and_exclusive_end(self) -> None:
        membership = self.membership(end=date(2026, 2, 1))

        self.assertEqual(membership.effective_start, date(2026, 1, 1))
        self.assertEqual(membership.effective_end, date(2026, 2, 1))
        self.assertEqual(membership.scope, SP500MembershipScope.HISTORICAL)
        self.assertEqual(membership.metadata.source, self.source)

    def test_membership_distinguishes_current_snapshot_from_history(self) -> None:
        snapshot = self.membership(scope=SP500MembershipScope.CURRENT_ONLY)

        self.assertEqual(snapshot.scope, SP500MembershipScope.CURRENT_ONLY)
        self.assertIsNone(snapshot.effective_end)
        with self.assertRaisesRegex(ValueError, "cannot define a historical end"):
            self.membership(
                scope=SP500MembershipScope.CURRENT_ONLY,
                end=date(2026, 2, 1),
            )

    def test_membership_rejects_invalid_effective_intervals(self) -> None:
        with self.assertRaisesRegex(ValueError, "must follow"):
            self.membership(end=date(2026, 1, 1))

        with self.assertRaisesRegex(ValueError, "one time granularity"):
            SP500ConstituentMembership(
                metadata=MarketDataMetadata(
                    market=self.index,
                    source=self.source,
                    effective_at=date(2026, 1, 1),
                ),
                constituent=self.constituent,
                scope=SP500MembershipScope.HISTORICAL,
                effective_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
            )

    def test_observation_result_enforces_identity_interval_bounds_and_type(self) -> None:
        query = self.observation_query()

        self.assertEqual(self.result(query, self.observation()).observations, (self.observation(),))
        with self.assertRaisesRegex(ValueError, "result market identity"):
            self.result(query, market=self.other_index)
        with self.assertRaisesRegex(ValueError, "record market identity"):
            self.result(query, self.observation(market=self.other_index))
        with self.assertRaisesRegex(ValueError, "exclusive query end"):
            self.result(query, self.observation(day=3))
        with self.assertRaisesRegex(ValueError, "contains membership"):
            self.result(query, self.membership())

        other_interval = SP500Interval(
            1,
            SP500IntervalUnit.WEEK,
            SP500IntervalAlignment.CALENDAR,
        )
        mismatched = SP500Observation(
            metadata=self.observation().metadata,
            interval=other_interval,
            observation_type=SP500ObservationType.LEVEL,
            value=6_000,
            unit=SP500ValueUnit.INDEX_POINTS,
            calculation=SP500Calculation.CLOSING_LEVEL,
        )
        with self.assertRaisesRegex(ValueError, "interval must match"):
            self.result(query, mismatched)

    def test_observation_result_requires_unique_deterministic_order(self) -> None:
        query = self.observation_query()
        level = self.observation()
        price_return = self.observation(
            observation_type=SP500ObservationType.RETURN,
            calculation=SP500Calculation.SIMPLE_PRICE_RETURN,
            unit=SP500ValueUnit.DECIMAL,
            value=0.01,
        )
        next_level = self.observation(day=1)

        result = self.result(query, level, price_return, next_level)
        self.assertEqual(result.records, (level, price_return, next_level))
        with self.assertRaisesRegex(ValueError, "unique and deterministically ordered"):
            self.result(query, price_return, level)
        with self.assertRaisesRegex(ValueError, "unique and deterministically ordered"):
            self.result(query, level, level)

    def test_membership_result_enforces_scope_bounds_and_order(self) -> None:
        query = self.membership_query()
        first = self.membership()
        second = self.membership(MarketIdentifier("ticker", "MSFT", market="XNAS"))

        result = self.result(query, first, second)
        self.assertEqual(result.memberships, (first, second))
        with self.assertRaisesRegex(ValueError, "unique and deterministically ordered"):
            self.result(query, second, first)
        with self.assertRaisesRegex(ValueError, "scope must match"):
            self.result(query, self.membership(scope=SP500MembershipScope.CURRENT_ONLY))
        with self.assertRaisesRegex(ValueError, "exclusive query end"):
            self.result(query, self.membership(start=date(2026, 2, 1)))

    def test_supported_capability_can_return_unavailable_for_valid_request(self) -> None:
        query = self.membership_query()
        result = self.result(
            query,
            availability=MarketDataAvailability.UNAVAILABLE,
            reason="Provider does not establish historical constituent validity",
        )

        self.assertEqual(result.availability, MarketDataAvailability.UNAVAILABLE)
        self.assertEqual(result.records, ())


if __name__ == "__main__":
    unittest.main()
