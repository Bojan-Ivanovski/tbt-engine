from tbt_engine.core.market import ClosedMarketState
from tbt_engine.core.orders import OrderState, StrategyCommand
from tbt_engine.core.portfolio import PortfolioState
from tbt_engine.core.strategy import Strategy
from tbt_engine.strategies._common import (
    buy_at_next_open,
    has_active_order,
    normalize_symbols,
    require_allocation,
)


class BuyAndHoldStrategy(Strategy):
    """Invest equally across unowned symbols and retain the positions."""

    def __init__(
        self,
        symbols: list[str],
        allocation: float = 1.0,
        name: str = "Buy and Hold",
    ) -> None:
        super().__init__(name=name)
        self.symbols = normalize_symbols(symbols)
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
        allocation_per_symbol = self.allocation / len(self.symbols)
        commands: list[StrategyCommand] = []
        for symbol in self.symbols:
            if holdings.get(symbol, 0.0) > 0 or has_active_order(orders, symbol):
                continue
            command = buy_at_next_open(
                symbol,
                portfolio,
                market.get_latest_closed(symbol),
                allocation_per_symbol,
            )
            if command is not None:
                commands.append(command)
        return commands
