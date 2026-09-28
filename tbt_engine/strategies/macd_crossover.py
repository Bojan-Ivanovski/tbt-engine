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


class MacdCrossoverStrategy(Strategy):
    """Trade crossings between MACD and its exponential signal line."""

    def __init__(
        self,
        symbols: list[str],
        fast_window: int = 12,
        slow_window: int = 26,
        signal_window: int = 9,
        allocation: float = 0.1,
        name: str = "MACD Crossover",
    ) -> None:
        super().__init__(name=name)
        self.symbols = normalize_symbols(symbols)
        self.fast_window = require_positive_integer(fast_window, "Fast window")
        self.slow_window = require_positive_integer(slow_window, "Slow window")
        self.signal_window = require_positive_integer(signal_window, "Signal window")
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
            if len(closes) < self.slow_window + self.signal_window:
                continue
            fast = closes.ewm(span=self.fast_window, adjust=False).mean()
            slow = closes.ewm(span=self.slow_window, adjust=False).mean()
            macd = fast - slow
            signal = macd.ewm(span=self.signal_window, adjust=False).mean()
            crossed_up = macd.iloc[-2] <= signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]
            crossed_down = macd.iloc[-2] >= signal.iloc[-2] and macd.iloc[-1] < signal.iloc[-1]
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
