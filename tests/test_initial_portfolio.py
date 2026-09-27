import unittest

from tbt_engine import (
    Engine,
    ExecutionTime,
    InitialPortfolio,
    InitialPosition,
    LedgerEntryType,
    OrderIntent,
    OrderState,
    OrderStatus,
    PortfolioState,
    Side,
    Strategy,
    StrategyCommand,
    SubmitOrder,
)
from tbt_engine.core.ledger import PortfolioLedger
from tbt_engine.core.market import BeforeOpenMarketState, OpenMarketState
from tests.test_simulation_pipeline import InMemoryProvider


class ObserveInitialPortfolioStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__("observe-initial-portfolio")
        self.symbols: tuple[str, ...] = ()
        self.cash = 0.0
        self.quantity = 0.0

    def define_assets(self) -> list[str]:
        return ["CONTROL"]

    def before_open(
        self,
        market: BeforeOpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        if not self.symbols:
            self.symbols = tuple(market.get_all_symbols())
            self.cash = portfolio.balance()
            self.quantity = portfolio.holdings()["TEST"].quantity
        return []


class AttemptUnmanagedPositionTradeStrategy(ObserveInitialPortfolioStrategy):
    def __init__(self) -> None:
        super().__init__()
        self.submitted = False

    def execute(
        self,
        market: OpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        if self.submitted:
            return []
        self.submitted = True
        return [
            SubmitOrder(
                OrderIntent(
                    symbol="TEST",
                    side=Side.SELL,
                    quantity=1,
                    execution_time=ExecutionTime.SESSION_CLOSE,
                )
            )
        ]


class InitialPortfolioTests(unittest.TestCase):
    def test_initial_state_is_normalized_and_immutable(self) -> None:
        initial = InitialPortfolio(
            cash=100,
            currency="eur",
            positions=(
                InitialPosition("msft", 2),
                InitialPosition("aapl", 1),
            ),
        )

        self.assertEqual(initial.cash, 100.0)
        self.assertEqual(initial.currency, "EUR")
        self.assertEqual(
            [(position.symbol, position.quantity) for position in initial.positions],
            [("AAPL", 1.0), ("MSFT", 2.0)],
        )
        with self.assertRaisesRegex(AttributeError, "cannot assign"):
            initial.cash = 200  # type: ignore[misc]

    def test_initial_state_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "cash"):
            InitialPortfolio(cash=-1)
        with self.assertRaisesRegex(ValueError, "currency"):
            InitialPortfolio(currency="US")
        with self.assertRaisesRegex(ValueError, "quantity"):
            InitialPosition("TEST", 0)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            InitialPortfolio(
                positions=(
                    InitialPosition("test", 1),
                    InitialPosition("TEST", 2),
                )
            )

    def test_opening_positions_are_replayable_ledger_state(self) -> None:
        ledger = PortfolioLedger(
            100,
            opening_positions=(("msft", 2), ("aapl", 1)),
        )

        self.assertEqual(
            [entry.type for entry in ledger.entries],
            [
                LedgerEntryType.OPENING_CASH,
                LedgerEntryType.OPENING_POSITION,
                LedgerEntryType.OPENING_POSITION,
            ],
        )
        self.assertEqual(
            [(entry.symbol, entry.quantity_delta) for entry in ledger.entries[1:]],
            [("AAPL", 1), ("MSFT", 2)],
        )
        self.assertEqual(ledger.replay(), ledger.state)

    def test_engine_values_initial_positions_at_first_open(self) -> None:
        initial = InitialPortfolio(
            cash=100,
            positions=(InitialPosition("TEST", 2),),
        )
        strategy = ObserveInitialPortfolioStrategy()

        provider = InMemoryProvider()
        result = Engine(
            provider=provider,
            initial_portfolio=initial,
        ).start(strategy)

        self.assertEqual(provider.requested_symbols, ["CONTROL", "TEST"])
        self.assertEqual(strategy.symbols, ("CONTROL",))
        self.assertEqual(strategy.cash, 100)
        self.assertEqual(strategy.quantity, 2)
        self.assertEqual(result.starting_equity, 120)
        self.assertEqual(result.ending_equity, 158)
        self.assertAlmostEqual(result.total_return_pct, 31.66666666666666)
        self.assertEqual(result.trades, [])
        self.assertEqual(
            [entry.type for entry in result.ledger_entries],
            [LedgerEntryType.OPENING_CASH, LedgerEntryType.OPENING_POSITION],
        )

    def test_strategy_cannot_trade_an_unselected_portfolio_asset(self) -> None:
        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(
                cash=100,
                positions=(InitialPosition("TEST", 2),),
            ),
        ).start(AttemptUnmanagedPositionTradeStrategy())

        self.assertEqual(result.orders[0].status, OrderStatus.REJECTED)
        self.assertIn("outside the strategy asset set", result.order_events[0].reason or "")
        self.assertEqual(result.fills, [])
        self.assertEqual(result.valuations[-1].positions[0].quantity, 2)

    def test_engine_recreates_initial_state_for_each_run(self) -> None:
        engine = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(
                cash=100,
                positions=(InitialPosition("TEST", 2),),
            ),
        )

        first = engine.start(ObserveInitialPortfolioStrategy())
        second = engine.start(ObserveInitialPortfolioStrategy())

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
