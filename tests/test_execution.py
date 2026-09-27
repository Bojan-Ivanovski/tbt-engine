import unittest

from tbt_engine import (
    CancelOrder,
    DailyBarExecutionModel,
    Engine,
    ExecutionMarketState,
    ExecutionModel,
    ExecutionOutcome,
    ExecutionOutcomeStatus,
    ExecutionPhase,
    Fill,
    InitialPortfolio,
    Order,
    OrderEventType,
    OrderId,
    OrderIntent,
    OrderState,
    OrderStatus,
    Side,
    StrategyCommand,
)
from tbt_engine.core.market import BeforeOpenMarketState
from tbt_engine.core.portfolio import Portfolio, PortfolioState
from tests.test_simulation_pipeline import InMemoryProvider, NextOpenStrategy


class PartialExecutionModel(ExecutionModel):
    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        price = market.get_price(order.intent.symbol)
        if price is None:
            return ExecutionOutcome(
                status=ExecutionOutcomeStatus.REJECTED,
                remaining_quantity=order.remaining_quantity,
                reason="Missing price",
            )
        quantity = 1.0 if order.filled_quantity == 0 else order.remaining_quantity
        remaining = order.remaining_quantity - quantity
        return ExecutionOutcome(
            status=(
                ExecutionOutcomeStatus.FILLED
                if remaining == 0
                else ExecutionOutcomeStatus.PARTIALLY_FILLED
            ),
            remaining_quantity=remaining,
            fills=(
                Fill(
                    order_id=order.id,
                    symbol=order.intent.symbol,
                    side=order.intent.side,
                    quantity=quantity,
                    price=price,
                    time=market.time,
                    phase=market.phase,
                ),
            ),
        )


class MultipleFillExecutionModel(ExecutionModel):
    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        price = market.get_price(order.intent.symbol)
        if price is None:
            return ExecutionOutcome(
                status=ExecutionOutcomeStatus.REJECTED,
                remaining_quantity=order.remaining_quantity,
                reason="Missing price",
            )
        quantities = (0.5, order.remaining_quantity - 0.5)
        return ExecutionOutcome(
            status=ExecutionOutcomeStatus.FILLED,
            remaining_quantity=0,
            fills=tuple(
                Fill(
                    order_id=order.id,
                    symbol=order.intent.symbol,
                    side=order.intent.side,
                    quantity=quantity,
                    price=price,
                    time=market.time,
                    phase=market.phase,
                )
                for quantity in quantities
            ),
        )


class NoFillExecutionModel(ExecutionModel):
    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        return ExecutionOutcome(
            status=ExecutionOutcomeStatus.NO_FILL,
            remaining_quantity=order.remaining_quantity,
            reason="No liquidity",
        )


class RejectedExecutionModel(ExecutionModel):
    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        return ExecutionOutcome(
            status=ExecutionOutcomeStatus.REJECTED,
            remaining_quantity=order.remaining_quantity,
            reason="Unsupported order",
        )


class OverfillExecutionModel(ExecutionModel):
    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        price = market.get_price(order.intent.symbol)
        if price is None:
            raise AssertionError("Expected an execution price")
        return ExecutionOutcome(
            status=ExecutionOutcomeStatus.FILLED,
            remaining_quantity=0,
            fills=(
                Fill(
                    order_id=order.id,
                    symbol=order.intent.symbol,
                    side=order.intent.side,
                    quantity=order.remaining_quantity + 1,
                    price=price,
                    time=market.time,
                    phase=market.phase,
                ),
            ),
        )


class CancelAfterPartialStrategy(NextOpenStrategy):
    def before_open(
        self,
        market: BeforeOpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        partially_filled = tuple(
            order for order in orders.active() if order.status is OrderStatus.PARTIALLY_FILLED
        )
        if partially_filled:
            return [CancelOrder(partially_filled[0].id)]
        return []


class ExecutionModelTests(unittest.TestCase):
    def test_daily_bar_model_returns_fill_without_mutating_portfolio(self) -> None:
        portfolio = Portfolio(initial_portfolio=InitialPortfolio(cash=100))
        order = Order(
            id=OrderId(1),
            intent=OrderIntent(symbol="TEST", side=Side.BUY, quantity=2),
            status=OrderStatus.PENDING,
            submitted_at="2026-01-05T00:00:00Z",
            submitted_phase="after_close",
            eligible_candle=1,
        )
        market = ExecutionMarketState(
            time="2026-01-06T00:00:00Z",
            phase=ExecutionPhase.OPEN,
            prices={"TEST": 20},
        )

        outcome = DailyBarExecutionModel().execute(order, market)

        self.assertEqual(outcome.status, ExecutionOutcomeStatus.FILLED)
        self.assertEqual(outcome.fills[0].quantity, 2)
        self.assertEqual(outcome.fills[0].price, 20)
        self.assertEqual(portfolio.balance, 100)
        self.assertEqual(portfolio.holdings, {})

    def test_partial_fills_are_applied_across_eligible_events(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            execution_model=PartialExecutionModel(),
        ).start(NextOpenStrategy())

        self.assertEqual([fill.quantity for fill in result.fills], [1, 1])
        self.assertEqual([fill.price for fill in result.fills], [20, 30])
        self.assertEqual(result.orders[0].status, OrderStatus.FILLED)
        self.assertEqual(result.orders[0].filled_quantity, 2)
        self.assertEqual(
            [event.type for event in result.order_events],
            [
                OrderEventType.ACCEPTED,
                OrderEventType.PARTIALLY_FILLED,
                OrderEventType.FILLED,
            ],
        )

    def test_one_execution_outcome_can_contain_multiple_fills(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            execution_model=MultipleFillExecutionModel(),
        ).start(NextOpenStrategy())

        self.assertEqual([fill.quantity for fill in result.fills], [0.5, 1.5])
        self.assertEqual(len(result.trades), 2)
        self.assertTrue(all(fill.order_id == result.orders[0].id for fill in result.fills))

    def test_partially_filled_order_can_be_cancelled_before_next_attempt(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            execution_model=PartialExecutionModel(),
        ).start(CancelAfterPartialStrategy())

        self.assertEqual([fill.quantity for fill in result.fills], [1])
        self.assertEqual(result.orders[0].filled_quantity, 1)
        self.assertEqual(result.orders[0].status, OrderStatus.CANCELLED)
        self.assertEqual(
            [event.type for event in result.order_events],
            [
                OrderEventType.ACCEPTED,
                OrderEventType.PARTIALLY_FILLED,
                OrderEventType.CANCELLED,
            ],
        )

    def test_no_fill_outcome_leaves_order_active_until_expiry(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            execution_model=NoFillExecutionModel(),
        ).start(NextOpenStrategy())

        self.assertEqual(result.fills, [])
        self.assertEqual(result.orders[0].status, OrderStatus.EXPIRED)
        self.assertEqual(
            [event.type for event in result.order_events],
            [
                OrderEventType.ACCEPTED,
                OrderEventType.NO_FILL,
                OrderEventType.NO_FILL,
                OrderEventType.EXPIRED,
            ],
        )

    def test_rejected_outcome_terminates_order_without_a_fill(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            execution_model=RejectedExecutionModel(),
        ).start(NextOpenStrategy())

        self.assertEqual(result.fills, [])
        self.assertEqual(result.orders[0].status, OrderStatus.REJECTED)
        self.assertEqual(result.order_events[-1].reason, "Unsupported order")

    def test_engine_rejects_an_execution_model_that_overfills(self) -> None:
        engine = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            execution_model=OverfillExecutionModel(),
        )

        with self.assertRaisesRegex(ValueError, "overfilled order"):
            engine.start(NextOpenStrategy())

    def test_daily_bar_model_rejects_missing_symbol_price(self) -> None:
        order = Order(
            id=OrderId(1),
            intent=OrderIntent(symbol="TEST", side=Side.BUY, quantity=2),
            status=OrderStatus.PENDING,
            submitted_at="2026-01-05T00:00:00Z",
            submitted_phase="after_close",
            eligible_candle=1,
        )
        market = ExecutionMarketState(
            time="2026-01-06T00:00:00Z",
            phase=ExecutionPhase.OPEN,
            prices={},
        )

        outcome = DailyBarExecutionModel().execute(order, market)

        self.assertEqual(outcome.status, ExecutionOutcomeStatus.REJECTED)
        self.assertEqual(outcome.reason, "No execution price available for TEST")

    def test_execution_market_state_rejects_invalid_prices(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid execution price"):
            ExecutionMarketState(
                time="2026-01-06T00:00:00Z",
                phase=ExecutionPhase.OPEN,
                prices={"TEST": float("nan")},
            )


if __name__ == "__main__":
    unittest.main()
