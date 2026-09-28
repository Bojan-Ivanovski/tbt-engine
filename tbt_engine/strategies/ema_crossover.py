from tbt_engine.core.market import ClosedMarketState
from tbt_engine.core.orders import OrderState, StrategyCommand
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


class EmaCrossoverStrategy(Strategy):
    """Trade crossings between fast and slow exponential moving averages."""

    def __init__(
        self,
        symbols: list[str],
        fast_window: int = 12,
        slow_window: int = 26,
        allocation: float = 0.1,
        name: str = "EMA Crossover",
    ) -> None:
        super().__init__(name=name)
        self.symbols = normalize_symbols(symbols)
        self.fast_window = require_positive_integer(fast_window, "Fast window")
        self.slow_window = require_positive_integer(slow_window, "Slow window")
        if self.fast_window >= self.slow_window:
            raise ValueError("Fast window must be shorter than slow window")
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
            closes = market.get_past_data(symbol)["Close"]
            if len(closes) < self.slow_window + 1:
                continue
            fast = closes.ewm(span=self.fast_window, adjust=False).mean()
            slow = closes.ewm(span=self.slow_window, adjust=False).mean()
            crossed_up = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
            crossed_down = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]
            held_quantity = holdings.get(symbol, 0.0)
            command = None
            if crossed_up and held_quantity == 0:
                command = buy_at_next_open(
                    symbol,
                    portfolio,
                    market.get_latest_closed(symbol),
                    self.allocation,
                )
            elif crossed_down and held_quantity > 0:
                command = sell_at_next_open(symbol, held_quantity)
            if command is not None:
                commands.append(command)
        return commands
