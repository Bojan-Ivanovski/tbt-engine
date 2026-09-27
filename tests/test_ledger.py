import unittest

from tbt_engine import (
    CostedFill,
    Engine,
    ExecutionCost,
    ExecutionPhase,
    Fill,
    FillId,
    InitialPortfolio,
    LedgerEntryId,
    LedgerEntryType,
    Market,
    OrderId,
    OrderStatus,
    PortfolioLedger,
    Side,
    StandardTransactionCostModel,
)
from tests.test_execution import MultipleFillExecutionModel
from tests.test_simulation_pipeline import InMemoryProvider, NextOpenStrategy


def make_costed_fill(
    *,
    fill_id: int = 1,
    side: Side = Side.BUY,
    quantity: float = 2,
    price: float = 20,
    currency: str = "USD",
    commission: float = 0,
    fees: float = 0,
    spread: float = 0,
    slippage: float = 0,
) -> CostedFill:
    typed_fill_id = FillId(fill_id)
    fill = Fill(
        id=typed_fill_id,
        order_id=OrderId(fill_id),
        symbol="TEST",
        side=side,
        quantity=quantity,
        price=price,
        time="2026-01-06T00:00:00Z",
        phase=ExecutionPhase.OPEN,
    )
    return CostedFill(
        fill=fill,
        cost=ExecutionCost(
            fill_id=typed_fill_id,
            model="test",
            currency=currency,
            commission=commission,
            fees=fees,
            spread=spread,
            slippage=slippage,
        ),
    )


class PortfolioLedgerTests(unittest.TestCase):
    def test_opening_cash_is_the_first_immutable_entry(self) -> None:
        ledger = PortfolioLedger(100, base_currency="usd", opened_at="2026-01-01")

        self.assertEqual(ledger.base_currency, "USD")
        self.assertEqual(ledger.state.cash, 100)
        self.assertEqual(ledger.state.positions, ())
        self.assertEqual(len(ledger.entries), 1)
        self.assertEqual(ledger.entries[0].id, LedgerEntryId(1))
        self.assertEqual(ledger.entries[0].type, LedgerEntryType.OPENING_CASH)

    def test_fill_posts_trade_commission_and_fee_entries(self) -> None:
        ledger = PortfolioLedger(100)
        costed_fill = make_costed_fill(
            price=20.2,
            commission=1,
            fees=0.5,
            spread=0.4,
            slippage=0.2,
        )

        posting = ledger.post((costed_fill,))

        self.assertTrue(posting.accepted)
        self.assertEqual(
            [entry.type for entry in posting.entries],
            [LedgerEntryType.TRADE, LedgerEntryType.COMMISSION, LedgerEntryType.FEE],
        )
        self.assertEqual([entry.id for entry in posting.entries], [2, 3, 4])
        self.assertAlmostEqual(ledger.state.cash, 58.1)
        self.assertEqual(ledger.state.quantity("TEST"), 2)
        self.assertAlmostEqual(sum(entry.cash_delta for entry in ledger.entries), 58.1)

    def test_spread_and_slippage_are_not_posted_as_direct_charges(self) -> None:
        ledger = PortfolioLedger(100)

        posting = ledger.post((make_costed_fill(price=20.2, spread=0.4, slippage=0.2),))

        self.assertEqual([entry.type for entry in posting.entries], [LedgerEntryType.TRADE])
        self.assertAlmostEqual(posting.entries[0].cash_delta, -40.4)

    def test_sell_increases_cash_and_reduces_the_position(self) -> None:
        ledger = PortfolioLedger(100)
        ledger.post((make_costed_fill(),))

        posting = ledger.post(
            (
                make_costed_fill(
                    fill_id=2,
                    side=Side.SELL,
                    quantity=1,
                    price=30,
                    commission=1,
                ),
            )
        )

        self.assertTrue(posting.accepted)
        self.assertEqual(ledger.state.cash, 89)
        self.assertEqual(ledger.state.quantity("TEST"), 1)

    def test_insufficient_cash_rejects_the_complete_batch_atomically(self) -> None:
        ledger = PortfolioLedger(40)

        rejected = ledger.post((make_costed_fill(commission=1),))

        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "Insufficient cash at execution")
        self.assertEqual(len(ledger.entries), 1)
        self.assertEqual(ledger.state.cash, 40)
        self.assertEqual(ledger.state.positions, ())

        accepted = ledger.post((make_costed_fill(quantity=1),))
        self.assertEqual(accepted.entries[0].id, LedgerEntryId(2))

    def test_insufficient_position_rejects_the_complete_batch(self) -> None:
        ledger = PortfolioLedger(100)

        posting = ledger.post((make_costed_fill(side=Side.SELL, quantity=1, price=30),))

        self.assertFalse(posting.accepted)
        self.assertEqual(posting.reason, "Insufficient position at execution")
        self.assertEqual(len(ledger.entries), 1)

    def test_duplicate_fill_cannot_be_posted_twice(self) -> None:
        ledger = PortfolioLedger(100)
        costed_fill = make_costed_fill(quantity=1)
        ledger.post((costed_fill,))

        posting = ledger.post((costed_fill,))

        self.assertFalse(posting.accepted)
        self.assertEqual(posting.reason, "Fill 1 has already been posted")
        self.assertEqual(len(ledger.entries), 2)

    def test_mismatched_currency_rejects_without_mutation(self) -> None:
        ledger = PortfolioLedger(100, base_currency="USD")

        posting = ledger.post((make_costed_fill(currency="EUR"),))

        self.assertFalse(posting.accepted)
        self.assertIn("portfolio base currency is USD", posting.reason or "")
        self.assertEqual(len(ledger.entries), 1)

    def test_replay_reconstructs_the_cached_state(self) -> None:
        ledger = PortfolioLedger(100)
        ledger.post((make_costed_fill(commission=1, fees=0.5),))
        ledger.post(
            (
                make_costed_fill(
                    fill_id=2,
                    side=Side.SELL,
                    quantity=0.5,
                    price=30,
                ),
            )
        )

        self.assertEqual(ledger.replay(), ledger.state)


class EngineLedgerTests(unittest.TestCase):
    def test_engine_exposes_reconcilable_ledger_entries(self) -> None:
        result = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            transaction_cost_model=StandardTransactionCostModel(
                commission_per_order=1,
                fee_rate=0.001,
                spread_bps=100,
            ),
        ).start(NextOpenStrategy())

        self.assertEqual(
            [entry.type for entry in result.ledger_entries],
            [
                LedgerEntryType.OPENING_CASH,
                LedgerEntryType.TRADE,
                LedgerEntryType.COMMISSION,
                LedgerEntryType.FEE,
            ],
        )
        self.assertAlmostEqual(sum(entry.cash_delta for entry in result.ledger_entries), 58.5596)
        self.assertAlmostEqual(result.ending_equity, 116.5596)

    def test_engine_rejects_mismatched_cost_currency(self) -> None:
        result = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            transaction_cost_model=StandardTransactionCostModel(currency="EUR"),
        ).start(NextOpenStrategy())

        self.assertEqual(result.fills, [])
        self.assertEqual(result.execution_costs, [])
        self.assertEqual(result.orders[0].status, OrderStatus.REJECTED)
        self.assertIn("portfolio base currency is USD", result.order_events[-1].reason or "")
        self.assertEqual(len(result.ledger_entries), 1)

    def test_default_zero_cost_model_uses_initial_portfolio_currency(self) -> None:
        result = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100, currency="EUR"),
        ).start(NextOpenStrategy())

        self.assertEqual(result.execution_costs[0].currency, "EUR")
        self.assertEqual(result.ledger_entries[0].currency, "EUR")

    def test_multi_fill_outcome_is_rejected_without_partial_posting(self) -> None:
        result = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=30),
            execution_model=MultipleFillExecutionModel(),
        ).start(NextOpenStrategy())

        self.assertEqual(result.fills, [])
        self.assertEqual(len(result.ledger_entries), 1)
        self.assertEqual(result.order_events[-1].reason, "Insufficient cash at execution")


if __name__ == "__main__":
    unittest.main()
