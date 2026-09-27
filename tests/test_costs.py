import json
import unittest

from tbt_engine import (
    Engine,
    ExecutionMarketState,
    ExecutionPhase,
    Fill,
    FillId,
    InitialPortfolio,
    MarketDataCapability,
    OrderId,
    Side,
    StandardTransactionCostModel,
    ZeroTransactionCostModel,
)
from tests.test_execution import PartialExecutionModel
from tests.test_simulation_pipeline import InMemoryProvider, NextOpenStrategy


def make_fill(*, side: Side = Side.BUY) -> Fill:
    return Fill(
        id=FillId(1),
        order_id=OrderId(1),
        symbol="TEST",
        side=side,
        quantity=10,
        price=100,
        time="2026-01-06T00:00:00Z",
        phase=ExecutionPhase.OPEN,
    )


def make_market() -> ExecutionMarketState:
    return ExecutionMarketState(
        time="2026-01-06T00:00:00Z",
        phase=ExecutionPhase.OPEN,
        prices={"TEST": 100},
    )


class QuoteRequiredCostModel(ZeroTransactionCostModel):
    @property
    def required_capabilities(self) -> frozenset[MarketDataCapability]:
        return frozenset({MarketDataCapability.HISTORICAL_QUOTES})


class TransactionCostModelTests(unittest.TestCase):
    def test_zero_cost_model_preserves_fill_and_records_zero_costs(self) -> None:
        fill = make_fill()

        result = ZeroTransactionCostModel().apply(fill, make_market(), is_first_fill_for_order=True)

        self.assertEqual(result.fill, fill)
        self.assertEqual(result.cost.fill_id, FillId(1))
        self.assertEqual(result.cost.total_cost, 0)

    def test_standard_model_applies_buy_costs_and_breakdown(self) -> None:
        model = StandardTransactionCostModel(
            commission_per_order=1,
            commission_per_unit=0.01,
            fee_rate=0.001,
            spread_bps=5,
            slippage_bps=3,
        )

        result = model.apply(make_fill(), make_market(), is_first_fill_for_order=True)

        self.assertAlmostEqual(result.fill.price, 100.08)
        self.assertEqual(result.fill.reference_price, 100)
        self.assertAlmostEqual(result.cost.commission, 1.1)
        self.assertAlmostEqual(result.cost.fees, 1.0008)
        self.assertAlmostEqual(result.cost.spread, 0.5)
        self.assertAlmostEqual(result.cost.slippage, 0.3)
        self.assertAlmostEqual(result.cost.total_cost, 2.9008)
        self.assertEqual(result.cost.currency, "USD")
        self.assertEqual(dict(result.cost.parameters), dict(model.parameters))

    def test_standard_model_adjusts_sell_price_downward(self) -> None:
        model = StandardTransactionCostModel(spread_bps=5, slippage_bps=3)

        result = model.apply(
            make_fill(side=Side.SELL),
            make_market(),
            is_first_fill_for_order=True,
        )

        self.assertAlmostEqual(result.fill.price, 99.92)

    def test_per_order_commission_is_only_charged_on_first_fill(self) -> None:
        model = StandardTransactionCostModel(commission_per_order=2)

        result = model.apply(make_fill(), make_market(), is_first_fill_for_order=False)

        self.assertEqual(result.cost.commission, 0)

    def test_standard_model_rejects_invalid_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "spread_bps"):
            StandardTransactionCostModel(spread_bps=-1)
        with self.assertRaisesRegex(ValueError, "less than 10,000"):
            StandardTransactionCostModel(spread_bps=5_000, slippage_bps=5_000)
        with self.assertRaisesRegex(ValueError, "currency"):
            StandardTransactionCostModel(currency="US")

    def test_model_configuration_is_serializable(self) -> None:
        model = StandardTransactionCostModel(
            commission_per_order=1,
            fee_rate=0.001,
            currency="eur",
        )

        serialized = json.loads(json.dumps(model.configuration))

        self.assertEqual(serialized["name"], "standard")
        self.assertEqual(serialized["currency"], "EUR")
        self.assertEqual(serialized["parameters"]["commission_per_order"], 1)


class EngineTransactionCostTests(unittest.TestCase):
    def test_engine_applies_costs_and_exposes_linked_records(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            transaction_cost_model=StandardTransactionCostModel(
                commission_per_order=1,
                spread_bps=100,
            ),
        ).start(NextOpenStrategy())

        self.assertEqual(result.fills[0].id, FillId(1))
        self.assertEqual(result.fills[0].reference_price, 20)
        self.assertAlmostEqual(result.fills[0].price, 20.2)
        self.assertEqual(result.execution_costs[0].fill_id, result.fills[0].id)
        self.assertEqual(result.execution_costs[0].commission, 1)
        self.assertAlmostEqual(result.execution_costs[0].spread, 0.4)
        self.assertAlmostEqual(result.ending_equity, 116.6)

    def test_default_engine_behavior_has_explicit_zero_costs(self) -> None:
        result = Engine(
            provider=InMemoryProvider(), initial_portfolio=InitialPortfolio(cash=100)
        ).start(NextOpenStrategy())

        self.assertEqual(len(result.execution_costs), 1)
        self.assertEqual(result.execution_costs[0].total_cost, 0)
        self.assertEqual(result.fills[0].price, 20)

    def test_identical_inputs_produce_identical_fills_and_costs(self) -> None:
        model = StandardTransactionCostModel(
            commission_per_unit=0.01,
            fee_rate=0.001,
            spread_bps=5,
            slippage_bps=3,
        )

        first = Engine(provider=InMemoryProvider(), transaction_cost_model=model).start(
            NextOpenStrategy()
        )
        second = Engine(provider=InMemoryProvider(), transaction_cost_model=model).start(
            NextOpenStrategy()
        )

        self.assertEqual(first.fills, second.fills)
        self.assertEqual(first.execution_costs, second.execution_costs)
        self.assertEqual(first.ending_equity, second.ending_equity)

    def test_direct_costs_are_included_in_buy_affordability(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=40),
            transaction_cost_model=StandardTransactionCostModel(commission_per_order=1),
        ).start(NextOpenStrategy())

        self.assertEqual(result.fills, [])
        self.assertEqual(result.execution_costs, [])
        self.assertEqual(result.order_events[-1].reason, "Insufficient cash at execution")

    def test_partial_fills_only_charge_per_order_commission_once(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            execution_model=PartialExecutionModel(),
            transaction_cost_model=StandardTransactionCostModel(commission_per_order=1),
        ).start(NextOpenStrategy())

        self.assertEqual([cost.commission for cost in result.execution_costs], [1, 0])
        self.assertEqual([fill.id for fill in result.fills], [FillId(1), FillId(2)])

    def test_engine_rejects_unavailable_market_data_capabilities(self) -> None:
        engine = Engine(
            provider=InMemoryProvider(),
            transaction_cost_model=QuoteRequiredCostModel(),
        )

        with self.assertRaisesRegex(ValueError, "historical_quotes"):
            engine.start(NextOpenStrategy())


if __name__ == "__main__":
    unittest.main()
