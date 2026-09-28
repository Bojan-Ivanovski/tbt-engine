from tbt_engine.core.market import ClosedMarketState
from tbt_engine.core.orders import (
    OrderState,
    StrategyCommand,
)
from tbt_engine.core.portfolio import PortfolioState
from tbt_engine.core.strategy import Strategy
from tbt_engine.strategies._common import (
    buy_at_next_open,
    has_active_order,
    normalize_symbols,
    require_allocation,
    require_positive_integer,
    sell_at_next_open,
)


class SmaCrossoverStrategy(Strategy):
    """Long-only SMA crossover strategy using 10% of available cash per entry."""

    def __init__(
        self,
        symbols: list[str],
        short_window: int = 5,
        long_window: int = 20,
        allocation: float = 0.1,
        name: str = "SMA Crossover",
    ) -> None:
        super().__init__(name=name)
        self.symbols = normalize_symbols(symbols)
        self.short_window = require_positive_integer(short_window, "Short window")
        self.long_window = require_positive_integer(long_window, "Long window")
        if self.short_window >= self.long_window:
            raise ValueError("Short window must be shorter than long window")
        self.allocation = require_allocation(allocation)

    def define_assets(self) -> list[str]:
        return list(self.symbols)

    def after_close(
        self,
        market: ClosedMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        holdings = portfolio.holdings()
        commands: list[StrategyCommand] = []

        for symbol in self.symbols:
            if has_active_order(orders, symbol):
                continue
            candles = market.get_past_data(symbol)
            if len(candles) < self.long_window + 1:
                continue

            closes = candles["Close"].to_numpy()
            short_previous = float(closes[-self.short_window - 1 : -1].mean())
            long_previous = float(closes[-self.long_window - 1 : -1].mean())
            short_current = float(closes[-self.short_window :].mean())
            long_current = float(closes[-self.long_window :].mean())

            held_quantity = holdings.get(symbol, 0.0)
            crossed_up = short_previous <= long_previous and short_current > long_current
            crossed_down = short_previous >= long_previous and short_current < long_current

            if crossed_up and held_quantity == 0:
                price = market.get_latest_closed(symbol)
                command = buy_at_next_open(symbol, portfolio, price, self.allocation)
                if command is not None:
                    commands.append(command)
            elif crossed_down and held_quantity > 0:
                command = sell_at_next_open(symbol, held_quantity)
                if command is not None:
                    commands.append(command)

        return commands
