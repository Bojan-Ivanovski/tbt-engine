import unittest
from collections.abc import Sequence

import pandas as pd

from tbt_engine.core.market import ClosedMarketState, Market
from tbt_engine.core.market.market import MarketAsset
from tbt_engine.core.orders import (
    ExecutionTime,
    Order,
    OrderId,
    OrderIntent,
    OrderState,
    OrderStatus,
    Side,
    SubmitOrder,
)
from tbt_engine.core.portfolio import InitialPortfolio, InitialPosition, Portfolio, PortfolioState
from tbt_engine.strategies import (
    BuyAndHoldStrategy,
    EmaCrossoverStrategy,
    MacdCrossoverStrategy,
    RsiMeanReversionStrategy,
    SmaCrossoverStrategy,
)


def closed_market_state(
    closes: Sequence[float],
    *,
    symbol: str = "TEST",
) -> ClosedMarketState:
    history = pd.DataFrame(
        {"Open": closes, "Close": closes},
        index=pd.date_range("2026-01-01", periods=len(closes), freq="D"),
    )
    market = Market()
    market.assets = {symbol: MarketAsset(symbol, history)}
    market.current_candle = len(history) - 1
    market.final_candle = len(history)
    return ClosedMarketState(market, [symbol])


def portfolio_state(*, cash: float = 1_000.0, held: float = 0.0) -> PortfolioState:
    positions = () if held == 0 else (InitialPosition("TEST", held),)
    return PortfolioState(Portfolio(InitialPortfolio(cash=cash, positions=positions)))


def submitted_order(command: object) -> OrderIntent:
    if not isinstance(command, SubmitOrder):
        raise AssertionError("Expected a submitted order")
    return command.intent


class BuiltInStrategyTests(unittest.TestCase):
    def test_buy_and_hold_invests_equally_across_symbols(self) -> None:
        history = pd.DataFrame(
            {"Open": [10.0], "Close": [10.0]},
            index=pd.date_range("2026-01-01", periods=1, freq="D"),
        )
        market = Market()
        market.assets = {
            "AAA": MarketAsset("AAA", history.copy()),
            "BBB": MarketAsset("BBB", history.copy()),
        }
        market.current_candle = 0
        market.final_candle = 1
        state = ClosedMarketState(market, ["AAA", "BBB"])

        commands = BuyAndHoldStrategy(["bbb", "AAA"]).after_close(
            state,
            portfolio_state(cash=1_000),
            OrderState({}),
        )

        self.assertEqual([submitted_order(command).symbol for command in commands], ["AAA", "BBB"])
        self.assertEqual([submitted_order(command).quantity for command in commands], [50.0, 50.0])
        self.assertTrue(
            all(
                submitted_order(command).execution_time is ExecutionTime.NEXT_OPEN
                for command in commands
            )
        )

    def test_sma_crossover_buys_on_upward_cross(self) -> None:
        strategy = SmaCrossoverStrategy(["TEST"], short_window=2, long_window=3)

        commands = strategy.after_close(
            closed_market_state([3.0, 2.0, 1.0, 1.0, 2.0]),
            portfolio_state(),
            OrderState({}),
        )

        self.assertEqual(len(commands), 1)
        self.assertEqual(submitted_order(commands[0]).side, Side.BUY)

    def test_ema_crossover_buys_on_upward_cross(self) -> None:
        strategy = EmaCrossoverStrategy(["TEST"], fast_window=2, slow_window=3)

        commands = strategy.after_close(
            closed_market_state([1.0, 1.0, 1.0, 2.0]),
            portfolio_state(),
            OrderState({}),
        )

        self.assertEqual(len(commands), 1)
        self.assertEqual(submitted_order(commands[0]).side, Side.BUY)

    def test_rsi_buys_oversold_and_sells_overbought(self) -> None:
        strategy = RsiMeanReversionStrategy(["TEST"], period=2)

        buy_commands = strategy.after_close(
            closed_market_state([3.0, 2.0, 1.0]),
            portfolio_state(),
            OrderState({}),
        )
        sell_commands = strategy.after_close(
            closed_market_state([1.0, 2.0, 3.0]),
            portfolio_state(held=4.0),
            OrderState({}),
        )

        self.assertEqual(submitted_order(buy_commands[0]).side, Side.BUY)
        self.assertEqual(submitted_order(sell_commands[0]).side, Side.SELL)
        self.assertEqual(submitted_order(sell_commands[0]).quantity, 4.0)

    def test_macd_crossover_buys_on_upward_signal_cross(self) -> None:
        strategy = MacdCrossoverStrategy(
            ["TEST"],
            fast_window=2,
            slow_window=3,
            signal_window=2,
        )

        commands = strategy.after_close(
            closed_market_state([3.0, 3.0, 3.0, 2.0, 3.0]),
            portfolio_state(),
            OrderState({}),
        )

        self.assertEqual(len(commands), 1)
        self.assertEqual(submitted_order(commands[0]).side, Side.BUY)

    def test_crossover_strategies_exit_on_downward_cross(self) -> None:
        cases = (
            (
                SmaCrossoverStrategy(["TEST"], short_window=2, long_window=3),
                [1.0, 2.0, 3.0, 3.0, 2.0],
            ),
            (
                EmaCrossoverStrategy(["TEST"], fast_window=2, slow_window=3),
                [2.0, 2.0, 2.0, 1.0],
            ),
            (
                MacdCrossoverStrategy(
                    ["TEST"],
                    fast_window=2,
                    slow_window=3,
                    signal_window=2,
                ),
                [1.0, 1.0, 1.0, 2.0, 1.0],
            ),
        )
        for strategy, closes in cases:
            with self.subTest(strategy=strategy.name):
                commands = strategy.after_close(
                    closed_market_state(closes),
                    portfolio_state(held=4.0),
                    OrderState({}),
                )

                self.assertEqual(len(commands), 1)
                self.assertEqual(submitted_order(commands[0]).side, Side.SELL)
                self.assertEqual(submitted_order(commands[0]).quantity, 4.0)

    def test_indicator_strategy_waits_for_warmup(self) -> None:
        strategy = MacdCrossoverStrategy(
            ["TEST"],
            fast_window=2,
            slow_window=3,
            signal_window=2,
        )

        commands = strategy.after_close(
            closed_market_state([1.0, 2.0, 3.0, 4.0]),
            portfolio_state(),
            OrderState({}),
        )

        self.assertEqual(commands, [])

    def test_active_order_suppresses_duplicate_signal(self) -> None:
        active_order = Order(
            id=OrderId(1),
            intent=OrderIntent("TEST", Side.BUY, 1.0),
            status=OrderStatus.PENDING,
            submitted_at="2026-01-01T00:00:00Z",
            submitted_phase="after_close",
            eligible_candle=1,
        )
        strategy = SmaCrossoverStrategy(["TEST"], short_window=2, long_window=3)

        commands = strategy.after_close(
            closed_market_state([3.0, 2.0, 1.0, 1.0, 2.0]),
            portfolio_state(),
            OrderState({active_order.id: active_order}),
        )

        self.assertEqual(commands, [])

    def test_strategy_parameters_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "symbols"):
            BuyAndHoldStrategy([])
        with self.assertRaisesRegex(ValueError, "shorter"):
            SmaCrossoverStrategy(["TEST"], short_window=20, long_window=20)
        with self.assertRaisesRegex(ValueError, "Allocation"):
            EmaCrossoverStrategy(["TEST"], allocation=0)
        with self.assertRaisesRegex(ValueError, "thresholds"):
            RsiMeanReversionStrategy(["TEST"], oversold=80, overbought=20)
        with self.assertRaisesRegex(ValueError, "Signal window"):
            MacdCrossoverStrategy(["TEST"], signal_window=0)


if __name__ == "__main__":
    unittest.main()
