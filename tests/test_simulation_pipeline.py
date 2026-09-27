import unittest
from datetime import date

import pandas as pd

from tbt_engine import (
    CancelOrder,
    ClosePriceValuationModel,
    DailyBarExecutionModel,
    Engine,
    ExecutionTime,
    InitialPortfolio,
    InMemoryResultCollector,
    OrderEventType,
    OrderIntent,
    OrderState,
    OrderStatus,
    PortfolioState,
    Provider,
    Side,
    SimulationPipeline,
    Strategy,
    StrategyCommand,
    SubmitOrder,
    ZeroTransactionCostModel,
)
from tbt_engine.core.market import (
    BeforeOpenMarketState,
    ClosedMarketState,
    Market,
    OpenMarketState,
)
from tbt_engine.core.pipeline import SimulationPipeline as CoreSimulationPipeline
from tbt_engine.core.portfolio import Portfolio
from tbt_engine.engine import Engine as RootEngine


class InMemoryProvider(Provider):
    def __init__(self, rows: int = 3) -> None:
        self.requested_symbols: list[str] = []
        self.requests: list[tuple[str, str, date | None, date | None]] = []
        self._history = pd.DataFrame(
            {"Open": [10.0, 20.0, 30.0], "Close": [12.0, 21.0, 29.0]},
            index=pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"]),
        ).iloc[:rows]

    def get_history(
        self,
        symbol: str,
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        self.requested_symbols.append(symbol)
        self.requests.append((symbol, interval, start, end))
        return self._history.copy()


class NextOpenStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__("next-open")
        self.submitted = False
        self.observations: list[tuple[str, int]] = []

    def define_assets(self) -> list[str]:
        return ["TEST"]

    def before_open(
        self,
        market: BeforeOpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        self.observations.append(("before_open", len(market.get_past_data("TEST"))))
        return []

    def execute(
        self,
        market: OpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        self.observations.append(("execute", len(market.get_past_data("TEST"))))
        return []

    def after_close(
        self,
        market: ClosedMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        self.observations.append(("after_close", len(market.get_past_data("TEST"))))
        if self.submitted:
            return []
        self.submitted = True
        return [
            SubmitOrder(
                OrderIntent(
                    symbol="TEST",
                    side=Side.BUY,
                    quantity=2,
                    execution_time=ExecutionTime.NEXT_OPEN,
                )
            )
        ]


class CancelBeforeOpenStrategy(NextOpenStrategy):
    def before_open(
        self,
        market: BeforeOpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        active = orders.active()
        if active:
            return [CancelOrder(active[0].id)]
        return []


class SessionCloseStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__("session-close")
        self.submitted = False
        self.first_open: float | None = None
        self.closed_bars_during_execute: int | None = None

    def define_assets(self) -> list[str]:
        return ["TEST"]

    def execute(
        self,
        market: OpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        if self.submitted:
            return []
        self.submitted = True
        self.first_open = market.get_current_open("TEST")
        self.closed_bars_during_execute = len(market.get_past_data("TEST"))
        return [
            SubmitOrder(
                OrderIntent(
                    symbol="TEST",
                    side=Side.BUY,
                    quantity=1,
                    execution_time=ExecutionTime.SESSION_CLOSE,
                )
            )
        ]


class SimulationPipelineTests(unittest.TestCase):
    def test_public_imports_share_root_and_core_implementations(self) -> None:
        self.assertIs(Engine, RootEngine)
        self.assertIs(SimulationPipeline, CoreSimulationPipeline)

    def test_engine_injects_provider_into_configured_market(self) -> None:
        provider = InMemoryProvider()
        market = Market(
            start=date(2026, 1, 1),
            end=date(2026, 2, 1),
            interval="1wk",
        )

        Engine(
            market=market,
            provider=provider,
            initial_portfolio=InitialPortfolio(cash=100),
        ).start(NextOpenStrategy())

        self.assertEqual(
            provider.requests,
            [("TEST", "1wk", date(2026, 1, 1), date(2026, 2, 1))],
        )

    def test_engine_creates_default_market_when_none_is_supplied(self) -> None:
        engine = Engine(provider=InMemoryProvider())

        self.assertIsInstance(engine.market, Market)
        self.assertEqual(engine.market.start, date(2000, 1, 1))
        self.assertIsNone(engine.market.end)
        self.assertEqual(engine.market.interval, "1d")

    def test_market_requires_provider_before_loading_assets(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "provider"):
            Market().set_assets(["TEST"])

    def test_direct_pipeline_run_matches_engine_result(self) -> None:
        engine_strategy = NextOpenStrategy()
        pipeline_strategy = NextOpenStrategy()
        expected = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
        ).start(engine_strategy)
        market = Market(start=date(2000, 1, 1))
        market.set_provider(InMemoryProvider())
        market.set_assets(pipeline_strategy.define_assets())
        portfolio = Portfolio(
            InitialPortfolio(cash=100),
            opened_at=date(2000, 1, 1).isoformat(),
        )
        pipeline = SimulationPipeline(
            execution_model=DailyBarExecutionModel(),
            transaction_cost_model=ZeroTransactionCostModel(),
            valuation_model=ClosePriceValuationModel(),
            result_collector=InMemoryResultCollector(),
        )

        actual = pipeline.run(
            pipeline_strategy,
            market,
            portfolio,
            strategy_assets=pipeline_strategy.define_assets(),
        )

        self.assertEqual(actual, expected)
        self.assertEqual(pipeline_strategy.observations, engine_strategy.observations)

    def test_after_close_order_fills_at_next_open(self) -> None:
        strategy = NextOpenStrategy()

        result = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
        ).start(strategy)

        self.assertEqual(result.trades[0].time, "2026-01-06T00:00:00Z")
        self.assertEqual(result.trades[0].price, 20)
        self.assertEqual(result.trades[0].quantity, 2)
        self.assertEqual(result.fills[0].order_id, result.orders[0].id)
        self.assertEqual(result.fills[0].price, 20)
        self.assertEqual(result.orders[0].status, OrderStatus.FILLED)
        self.assertEqual(
            strategy.observations[:4],
            [
                ("before_open", 0),
                ("execute", 0),
                ("after_close", 1),
                ("before_open", 1),
            ],
        )

    def test_before_open_can_cancel_order_before_opening_fill(self) -> None:
        result = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
        ).start(CancelBeforeOpenStrategy())

        self.assertEqual(result.trades, [])
        self.assertEqual(result.orders[0].status, OrderStatus.CANCELLED)
        self.assertEqual(
            [event.type for event in result.order_events],
            [OrderEventType.ACCEPTED, OrderEventType.CANCELLED],
        )

    def test_execute_can_submit_order_for_current_close(self) -> None:
        strategy = SessionCloseStrategy()

        result = Engine(
            market=Market(),
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
        ).start(strategy)

        self.assertEqual(strategy.first_open, 10)
        self.assertEqual(strategy.closed_bars_during_execute, 0)
        self.assertEqual(result.trades[0].time, "2026-01-05T00:00:00Z")
        self.assertEqual(result.trades[0].price, 12)

    def test_order_without_later_open_expires(self) -> None:
        result = Engine(
            market=Market(),
            provider=InMemoryProvider(rows=1),
            initial_portfolio=InitialPortfolio(cash=100),
        ).start(NextOpenStrategy())

        self.assertEqual(result.trades, [])
        self.assertEqual(result.orders[0].status, OrderStatus.EXPIRED)
        self.assertEqual(result.order_events[-1].type, OrderEventType.EXPIRED)


if __name__ == "__main__":
    unittest.main()
