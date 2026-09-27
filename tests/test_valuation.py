import unittest

from tbt_engine import (
    ClosePriceValuationModel,
    Engine,
    LedgerState,
    PortfolioValuation,
    PositionValuation,
    ValuationMarketState,
    ValuationModel,
    ValuationPhase,
)
from tests.test_simulation_pipeline import InMemoryProvider, NextOpenStrategy


def make_market(*, price: float = 25) -> ValuationMarketState:
    return ValuationMarketState(
        time="2026-01-06T00:00:00Z",
        phase=ValuationPhase.CLOSE,
        prices={"TEST": price},
    )


class DoublePriceValuationModel(ValuationModel):
    @property
    def name(self) -> str:
        return "double_price"

    def value(
        self,
        portfolio: LedgerState,
        market: ValuationMarketState,
    ) -> PortfolioValuation:
        positions = tuple(
            PositionValuation(
                symbol=symbol,
                quantity=quantity,
                price=self._price(market, symbol) * 2,
                market_value=quantity * self._price(market, symbol) * 2,
            )
            for symbol, quantity in portfolio.positions
        )
        return PortfolioValuation(
            time=market.time,
            phase=market.phase,
            model=self.name,
            currency=portfolio.currency,
            cash=portfolio.cash,
            positions=positions,
            total_equity=portfolio.cash + sum(position.market_value for position in positions),
        )

    @staticmethod
    def _price(market: ValuationMarketState, symbol: str) -> float:
        price = market.get_price(symbol)
        if price is None:
            raise ValueError(f"Missing price for {symbol}")
        return price


class CapturingValuationModel(ClosePriceValuationModel):
    def __init__(self) -> None:
        self.snapshots: list[ValuationMarketState] = []

    def value(
        self,
        portfolio: LedgerState,
        market: ValuationMarketState,
    ) -> PortfolioValuation:
        self.snapshots.append(market)
        return super().value(portfolio, market)


class InvalidPositionValuationModel(ClosePriceValuationModel):
    def value(
        self,
        portfolio: LedgerState,
        market: ValuationMarketState,
    ) -> PortfolioValuation:
        valuation = super().value(portfolio, market)
        if not valuation.positions:
            return valuation
        position = valuation.positions[0]
        invalid_position = PositionValuation(
            symbol=position.symbol,
            quantity=position.quantity + 1,
            price=position.price,
            market_value=(position.quantity + 1) * position.price,
        )
        return PortfolioValuation(
            time=valuation.time,
            phase=valuation.phase,
            model=valuation.model,
            currency=valuation.currency,
            cash=valuation.cash,
            positions=(invalid_position,),
            total_equity=valuation.cash + invalid_position.market_value,
        )


class ValuationModelTests(unittest.TestCase):
    def test_close_price_model_produces_reconciled_breakdown(self) -> None:
        portfolio = LedgerState(currency="USD", cash=50, positions=(("TEST", 2.0),))

        valuation = ClosePriceValuationModel().value(portfolio, make_market())

        self.assertEqual(valuation.cash, 50)
        self.assertEqual(valuation.currency, "USD")
        self.assertEqual(valuation.positions[0].price, 25)
        self.assertEqual(valuation.positions[0].market_value, 50)
        self.assertEqual(valuation.total_equity, 100)

    def test_close_price_model_requires_a_price_for_every_position(self) -> None:
        portfolio = LedgerState(currency="USD", cash=50, positions=(("OTHER", 2.0),))

        with self.assertRaisesRegex(ValueError, "No valuation price available"):
            ClosePriceValuationModel().value(portfolio, make_market())

    def test_valuation_market_state_is_immutable_and_validated(self) -> None:
        prices = {"test": 25.0}
        market = ValuationMarketState(
            time="2026-01-06T00:00:00Z",
            phase=ValuationPhase.CLOSE,
            prices=prices,
        )
        prices["test"] = 100

        self.assertEqual(market.get_price("TEST"), 25)
        with self.assertRaisesRegex(ValueError, "Invalid valuation price"):
            make_market(price=float("nan"))


class EngineValuationTests(unittest.TestCase):
    def test_default_valuations_preserve_equity_history(self) -> None:
        result = Engine(provider=InMemoryProvider(), initial_balance=100).start(NextOpenStrategy())

        self.assertEqual(len(result.valuations), 3)
        self.assertEqual(
            [valuation.total_equity for valuation in result.valuations],
            [point.equity for point in result.equity_history],
        )
        self.assertEqual(result.valuations[-1].positions[0].price, 29)
        self.assertEqual(result.ending_equity, 118)

    def test_custom_valuation_model_is_injected(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_balance=100,
            valuation_model=DoublePriceValuationModel(),
        ).start(NextOpenStrategy())

        self.assertEqual(result.valuations[-1].model, "double_price")
        self.assertEqual(result.valuations[-1].positions[0].price, 58)
        self.assertEqual(result.ending_equity, 176)

    def test_engine_supplies_only_close_phase_prices(self) -> None:
        model = CapturingValuationModel()

        Engine(
            provider=InMemoryProvider(),
            initial_balance=100,
            valuation_model=model,
        ).start(NextOpenStrategy())

        self.assertEqual(
            [snapshot.phase for snapshot in model.snapshots],
            [ValuationPhase.CLOSE, ValuationPhase.CLOSE, ValuationPhase.CLOSE],
        )
        self.assertEqual(
            [snapshot.get_price("TEST") for snapshot in model.snapshots],
            [12, 21, 29],
        )

    def test_engine_rejects_a_valuation_with_wrong_positions(self) -> None:
        engine = Engine(
            provider=InMemoryProvider(),
            initial_balance=100,
            valuation_model=InvalidPositionValuationModel(),
        )

        with self.assertRaisesRegex(ValueError, "positions do not match"):
            engine.start(NextOpenStrategy())


if __name__ == "__main__":
    unittest.main()
