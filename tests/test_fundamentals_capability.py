import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from tbt_engine.core.errors import InvalidCapabilityQueryError
from tbt_engine.metadata import SourceMetadata
from tbt_engine.providers.capabilities.company.company_capabilities import (
    CompanyCapabilities,
)
from tbt_engine.providers.capabilities.company.company_data import (
    CompanyDataAvailability,
    CompanyDataMetadata,
    CompanyDataResult,
)
from tbt_engine.providers.capabilities.company.company_identifier import CompanyIdentifier
from tbt_engine.providers.capabilities.company.fundamentals import (
    FUNDAMENTALS_CAPABILITY,
    AccountingBasis,
    CompanyProfileRecord,
    FinancialStatementRecord,
    FinancialStatementType,
    FiscalPeriod,
    FiscalPeriodLabel,
    FundamentalMetricId,
    FundamentalRecordType,
    FundamentalsCapability,
    FundamentalsQuery,
    FundamentalsResult,
    ReportingPeriod,
    ReportingPeriodType,
)


class InMemoryFundamentalsCapability(FundamentalsCapability):
    def __init__(self, result: FundamentalsResult) -> None:
        self.result = result
        self.queries: list[FundamentalsQuery] = []

    def get_fundamentals(self, query: FundamentalsQuery) -> FundamentalsResult:
        self.queries.append(query)
        return self.result


class FundamentalsCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = CompanyIdentifier("ticker", "TEST", market="XNAS")
        self.source = SourceMetadata(
            provider="memory",
            source="fixed-fundamentals",
            retrieved_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        self.period_end = date(2025, 12, 31)
        self.published_at = datetime(2026, 2, 1, 14, tzinfo=timezone.utc)
        self.available_at = self.published_at + timedelta(minutes=5)

    def metadata(self, effective_at: date) -> CompanyDataMetadata:
        return CompanyDataMetadata(
            company=self.company,
            source=self.source,
            effective_at=effective_at,
            available_at=self.available_at,
        )

    def query(self) -> FundamentalsQuery:
        return FundamentalsQuery(
            company=self.company,
            start=date(2025, 1, 1),
            end=date(2026, 1, 1),
        )

    def statement(
        self,
        metric: str = "revenue",
        value: Decimal | None = Decimal("125.5"),
    ) -> FinancialStatementRecord:
        return FinancialStatementRecord(
            metadata=self.metadata(self.period_end),
            statement_type=FinancialStatementType.INCOME_STATEMENT,
            metric=FundamentalMetricId(metric),
            reporting_period=ReportingPeriod(
                ReportingPeriodType.DURATION,
                end=self.period_end,
                start=date(2025, 1, 1),
            ),
            fiscal_period=FiscalPeriod(2025, FiscalPeriodLabel.FY),
            accounting_basis=AccountingBasis("us-gaap"),
            value=value,
            unit="currency",
            scale=Decimal("1000000"),
            currency="usd",
            published_at=self.published_at,
        )

    def result(
        self, *records: CompanyProfileRecord | FinancialStatementRecord
    ) -> FundamentalsResult:
        query = self.query()
        return FundamentalsResult(
            query=query,
            data=CompanyDataResult(
                company=self.company,
                source=self.source,
                availability=CompanyDataAvailability.AVAILABLE,
                records=records,
            ),
        )

    def test_capability_has_stable_identity_and_composes_with_company_domain(self) -> None:
        result = self.result()
        capability = InMemoryFundamentalsCapability(result)
        company_capabilities = CompanyCapabilities("memory", (capability,))

        self.assertEqual(capability.id, FUNDAMENTALS_CAPABILITY)
        self.assertIs(company_capabilities.require(FundamentalsCapability), capability)
        self.assertIs(capability.get_fundamentals(result.query), result)

    def test_query_normalizes_filters_and_uses_shared_query_errors(self) -> None:
        record_types = {FundamentalRecordType.FINANCIAL_STATEMENT}
        query = FundamentalsQuery(
            company=self.company,
            record_types=record_types,  # pyright: ignore[reportArgumentType]
            statement_types={
                FinancialStatementType.CASH_FLOW
            },  # pyright: ignore[reportArgumentType]
        )
        record_types.clear()

        self.assertEqual(
            query.record_types,
            frozenset((FundamentalRecordType.FINANCIAL_STATEMENT,)),
        )
        invalid_queries = (
            lambda: FundamentalsQuery(
                company=self.company,
                record_types=frozenset(),
            ),
            lambda: FundamentalsQuery(
                company=self.company,
                record_types=frozenset((FundamentalRecordType.PROFILE,)),
                statement_types=frozenset((FinancialStatementType.BALANCE_SHEET,)),
            ),
            lambda: FundamentalsQuery(
                company=self.company,
                start=datetime(
                    2025, 1, 1, tzinfo=timezone.utc
                ),  # pyright: ignore[reportArgumentType]
            ),
            lambda: FundamentalsQuery(
                company=self.company,
                start=date(2026, 1, 1),
                end=date(2026, 1, 1),
            ),
        )
        for invalid_query in invalid_queries:
            with self.subTest(invalid_query=invalid_query):
                with self.assertRaises(InvalidCapabilityQueryError):
                    invalid_query()

    def test_profile_preserves_empty_text_separately_from_missing_text(self) -> None:
        profile = CompanyProfileRecord(
            metadata=self.metadata(self.period_end),
            legal_name=" Test Company ",
            description="",
            sector=None,
            published_at=self.published_at,
        )

        self.assertEqual(profile.legal_name, "Test Company")
        self.assertEqual(profile.description, "")
        self.assertIsNone(profile.sector)
        with self.assertRaises(ValueError):
            CompanyProfileRecord(metadata=self.metadata(self.period_end))

    def test_statement_preserves_zero_separately_from_missing_value(self) -> None:
        zero = self.statement(value=Decimal(0))
        missing = self.statement(metric="operating_income", value=None)

        self.assertEqual(zero.value, Decimal(0))
        self.assertIsNone(missing.value)
        self.assertEqual(zero.currency, "USD")
        self.assertEqual(zero.unit, "currency")
        self.assertEqual(zero.scale, Decimal("1000000"))
        self.assertEqual(zero.accounting_basis, AccountingBasis("us-gaap"))

    def test_reporting_and_fiscal_periods_are_explicit_and_validated(self) -> None:
        instant = ReportingPeriod(ReportingPeriodType.INSTANT, self.period_end)

        self.assertIsNone(instant.start)
        self.assertEqual(FiscalPeriod(2025, FiscalPeriodLabel.Q4).label, FiscalPeriodLabel.Q4)
        with self.assertRaises(ValueError):
            ReportingPeriod(
                ReportingPeriodType.DURATION,
                end=self.period_end,
            )
        with self.assertRaises(ValueError):
            ReportingPeriod(
                ReportingPeriodType.INSTANT,
                end=self.period_end,
                start=date(2025, 1, 1),
            )
        with self.assertRaises(ValueError):
            FiscalPeriod(0, FiscalPeriodLabel.FY)
        with self.assertRaises(ValueError):
            FiscalPeriod(2025.5, FiscalPeriodLabel.FY)  # pyright: ignore[reportArgumentType]

    def test_records_preserve_publication_and_point_in_time_availability(self) -> None:
        statement = self.statement()

        self.assertEqual(statement.published_at, self.published_at)
        self.assertEqual(statement.metadata.available_at, self.available_at)
        with self.assertRaisesRegex(ValueError, "precede publication"):
            FinancialStatementRecord(
                metadata=CompanyDataMetadata(
                    company=self.company,
                    source=self.source,
                    effective_at=self.period_end,
                    available_at=self.published_at - timedelta(seconds=1),
                ),
                statement_type=statement.statement_type,
                metric=statement.metric,
                reporting_period=statement.reporting_period,
                fiscal_period=statement.fiscal_period,
                accounting_basis=statement.accounting_basis,
                value=statement.value,
                unit=statement.unit,
                published_at=self.published_at,
            )
        with self.assertRaisesRegex(ValueError, "period end"):
            FinancialStatementRecord(
                metadata=self.metadata(self.period_end),
                statement_type=statement.statement_type,
                metric=statement.metric,
                reporting_period=statement.reporting_period,
                fiscal_period=statement.fiscal_period,
                accounting_basis=statement.accounting_basis,
                value=statement.value,
                unit=statement.unit,
                published_at=datetime(2025, 12, 30, tzinfo=timezone.utc),
            )

    def test_statement_validates_period_currency_unit_scale_and_numeric_value(self) -> None:
        statement = self.statement()
        invalid_arguments = (
            {"metadata": self.metadata(date(2025, 9, 30))},
            {"currency": "US"},
            {"unit": " "},
            {"scale": Decimal(0)},
            {"value": Decimal("NaN")},
        )
        base = {
            "metadata": statement.metadata,
            "statement_type": statement.statement_type,
            "metric": statement.metric,
            "reporting_period": statement.reporting_period,
            "fiscal_period": statement.fiscal_period,
            "accounting_basis": statement.accounting_basis,
            "value": statement.value,
            "unit": statement.unit,
            "scale": statement.scale,
            "currency": statement.currency,
            "published_at": statement.published_at,
        }
        for changes in invalid_arguments:
            arguments = base | changes
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    FinancialStatementRecord(**arguments)  # pyright: ignore[reportArgumentType]

    def test_result_enforces_query_identity_filters_bounds_and_record_company(self) -> None:
        different_company = CompanyIdentifier("ticker", "OTHER", market="XNAS")
        with self.assertRaisesRegex(ValueError, "result company"):
            FundamentalsResult(
                query=self.query(),
                data=CompanyDataResult(
                    company=different_company,
                    source=self.source,
                    availability=CompanyDataAvailability.AVAILABLE,
                ),
            )

        profile_only = FundamentalsQuery(
            company=self.company,
            record_types=frozenset((FundamentalRecordType.PROFILE,)),
        )
        with self.assertRaisesRegex(ValueError, "unrequested statement"):
            FundamentalsResult(
                query=profile_only,
                data=CompanyDataResult(
                    company=self.company,
                    source=self.source,
                    availability=CompanyDataAvailability.AVAILABLE,
                    records=(self.statement(),),
                ),
            )

        out_of_range = FinancialStatementRecord(
            metadata=self.metadata(date(2026, 1, 1)),
            statement_type=FinancialStatementType.BALANCE_SHEET,
            metric=FundamentalMetricId("assets"),
            reporting_period=ReportingPeriod(ReportingPeriodType.INSTANT, date(2026, 1, 1)),
            fiscal_period=FiscalPeriod(2025, FiscalPeriodLabel.FY),
            accounting_basis=AccountingBasis("us-gaap"),
            value=Decimal(1),
            unit="currency",
            currency="USD",
            published_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        with self.assertRaisesRegex(ValueError, "exclusive query end"):
            self.result(out_of_range)

    def test_result_enforces_unique_deterministic_order(self) -> None:
        profile = CompanyProfileRecord(
            metadata=self.metadata(date(2025, 6, 30)),
            legal_name="Test Company",
            published_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
        )
        statement = self.statement()

        result = self.result(profile, statement)
        self.assertEqual(result.records, (profile, statement))
        with self.assertRaisesRegex(ValueError, "ascending order"):
            self.result(statement, profile)
        with self.assertRaisesRegex(ValueError, "unique"):
            self.result(statement, statement)

    def test_available_empty_result_remains_distinct_from_unavailable(self) -> None:
        result = self.result()

        self.assertEqual(result.availability, CompanyDataAvailability.AVAILABLE)
        self.assertEqual(result.records, ())


if __name__ == "__main__":
    unittest.main()
