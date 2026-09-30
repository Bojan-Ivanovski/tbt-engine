import unittest
from datetime import date, datetime

from tbt_engine import (
    AmbiguousSymbolMappingError,
    AssetType,
    CurrencyCode,
    Exchange,
    ExchangeIdentifier,
    Instrument,
    InstrumentIdentifier,
    ProviderSymbolMapping,
    SymbolMap,
    SymbolMappingNotFoundError,
)
from tbt_engine.providers.capabilities.company import CompanyIdentifier
from tbt_engine.providers.capabilities.market import MarketIdentifier


class InstrumentIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = ExchangeIdentifier("xnas")
        self.instrument = InstrumentIdentifier("figi", "BBG000MM2P62")

    def test_normalizes_stable_identity_and_reference_data(self) -> None:
        exchange = Exchange(self.exchange, " Nasdaq ", "America/New_York")
        instrument = Instrument(
            id=self.instrument,
            asset_type=AssetType.EQUITY,
            exchange=self.exchange,
            currency=CurrencyCode("usd"),
            name=" Meta Platforms ",
        )

        self.assertEqual(self.instrument.scheme, "figi")
        self.assertEqual(exchange.name, "Nasdaq")
        self.assertEqual(instrument.currency, CurrencyCode("USD"))
        self.assertEqual(instrument.name, "Meta Platforms")

    def test_existing_capability_identifiers_are_instrument_identifiers(self) -> None:
        company = CompanyIdentifier("figi", "BBG000MM2P62", market="xnas")
        market = MarketIdentifier("figi", "BBG000BDTBL9", market="xnas")

        self.assertIsInstance(company, InstrumentIdentifier)
        self.assertIsInstance(market, InstrumentIdentifier)
        self.assertEqual(company.canonical, InstrumentIdentifier("figi", "BBG000MM2P62"))
        self.assertEqual(market.canonical, InstrumentIdentifier("figi", "BBG000BDTBL9"))
        self.assertEqual(company.market, "XNAS")
        self.assertEqual(market.market, "XNAS")

    def test_resolves_symbol_changes_by_effective_date(self) -> None:
        symbols = SymbolMap(
            (
                ProviderSymbolMapping(
                    instrument=self.instrument,
                    provider="example",
                    symbol="FB",
                    valid_to=date(2022, 6, 9),
                    exchange=self.exchange,
                ),
                ProviderSymbolMapping(
                    instrument=self.instrument,
                    provider="example",
                    symbol="META",
                    valid_from=date(2022, 6, 9),
                    exchange=self.exchange,
                ),
            )
        )

        self.assertEqual(symbols.resolve("EXAMPLE", "FB", date(2022, 6, 8)), self.instrument)
        self.assertEqual(symbols.resolve("example", "META", date(2022, 6, 9)), self.instrument)
        self.assertEqual(
            symbols.symbol_for("example", self.instrument, date(2022, 6, 8)),
            "FB",
        )
        self.assertEqual(
            symbols.symbol_for("example", self.instrument, date(2022, 6, 9)),
            "META",
        )
        with self.assertRaises(SymbolMappingNotFoundError):
            symbols.resolve("example", "FB", date(2022, 6, 9))

    def test_rejects_overlapping_symbol_history(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            SymbolMap(
                (
                    ProviderSymbolMapping(
                        self.instrument,
                        "example",
                        "META",
                        valid_from=date(2022, 1, 1),
                        exchange=self.exchange,
                    ),
                    ProviderSymbolMapping(
                        InstrumentIdentifier("figi", "OTHER"),
                        "example",
                        "META",
                        valid_from=date(2023, 1, 1),
                        exchange=self.exchange,
                    ),
                )
            )

    def test_requires_exchange_to_disambiguate_reused_symbols(self) -> None:
        other_exchange = ExchangeIdentifier("XNYS")
        other_instrument = InstrumentIdentifier("figi", "OTHER")
        symbols = SymbolMap(
            (
                ProviderSymbolMapping(
                    self.instrument,
                    "example",
                    "ABC",
                    exchange=self.exchange,
                ),
                ProviderSymbolMapping(
                    other_instrument,
                    "example",
                    "ABC",
                    exchange=other_exchange,
                ),
            )
        )

        with self.assertRaises(AmbiguousSymbolMappingError):
            symbols.resolve("example", "ABC", date(2025, 1, 1))
        self.assertEqual(
            symbols.resolve("example", "ABC", date(2025, 1, 1), other_exchange),
            other_instrument,
        )

    def test_rejects_invalid_reference_values_and_datetime_validity(self) -> None:
        with self.assertRaises(ValueError):
            ExchangeIdentifier("NASDAQ")
        with self.assertRaises(ValueError):
            CurrencyCode("US")
        with self.assertRaises(ValueError):
            Exchange(self.exchange, "Nasdaq", "Not/A_Zone")
        with self.assertRaises(TypeError):
            ProviderSymbolMapping(
                self.instrument,
                "example",
                "META",
                valid_from=datetime(2025, 1, 1),
            )


if __name__ == "__main__":
    unittest.main()
