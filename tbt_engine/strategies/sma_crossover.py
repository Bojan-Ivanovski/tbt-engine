from tbt_engine.market import ClosedMarketState
from tbt_engine.orders import (
    ExecutionTime,
    OrderIntent,
    OrderState,
    Side,
    StrategyCommand,
    SubmitOrder,
)
from tbt_engine.portfolio import PortfolioState
from tbt_engine.strategy import Strategy


class SmaCrossoverStrategy(Strategy):
    """Long-only SMA crossover strategy using 10% of available cash per entry."""

    def __init__(
        self,
        symbols: list[str],
        short_window: int = 5,
        long_window: int = 20,
        allocation: float = 0.1,
        name: str = "SMA Crossover",
    ):
        super().__init__(name=name)
        self.symbols = symbols
        self.short_window = short_window
        self.long_window = long_window
        self.allocation = allocation

    def define_market(self) -> list[str]:
        return self.symbols

    def after_close(
        self,
        market: ClosedMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        holdings = portfolio.holdings()
        commands: list[StrategyCommand] = []

        for symbol in market.get_all_symbols():
            candles = market.get_past_data(symbol)
            if len(candles) < self.long_window + 1:
                continue

            closes = candles["Close"].to_numpy()
            short_previous = float(closes[-self.short_window - 1 : -1].mean())
            long_previous = float(closes[-self.long_window - 1 : -1].mean())
            short_current = float(closes[-self.short_window :].mean())
            long_current = float(closes[-self.long_window :].mean())

            held_quantity = float(getattr(holdings.get(symbol), "quantity", 0.0))
            crossed_up = short_previous <= long_previous and short_current > long_current
            crossed_down = short_previous >= long_previous and short_current < long_current

            if crossed_up and held_quantity == 0:
                price = market.get_latest_closed(symbol)
                quantity = (portfolio.balance() * self.allocation) / price
                commands.append(
                    SubmitOrder(
                        OrderIntent(
                            symbol=symbol,
                            side=Side.BUY,
                            quantity=quantity,
                            execution_time=ExecutionTime.NEXT_OPEN,
                        )
                    )
                )
            elif crossed_down and held_quantity > 0:
                commands.append(
                    SubmitOrder(
                        OrderIntent(
                            symbol=symbol,
                            side=Side.SELL,
                            quantity=held_quantity,
                            execution_time=ExecutionTime.NEXT_OPEN,
                        )
                    )
                )

        return commands
