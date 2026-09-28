import math

from pandas import Series

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


class RsiMeanReversionStrategy(Strategy):
    """Buy oversold RSI readings and exit positions at overbought readings."""

    def __init__(
        self,
        symbols: list[str],
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        allocation: float = 0.1,
        name: str = "RSI Mean Reversion",
    ) -> None:
        super().__init__(name=name)
        self.symbols = normalize_symbols(symbols)
        self.period = require_positive_integer(period, "RSI period")
        self.oversold = float(oversold)
        self.overbought = float(overbought)
        if (
            not math.isfinite(self.oversold)
            or not math.isfinite(self.overbought)
            or self.oversold < 0
            or self.overbought > 100
            or self.oversold >= self.overbought
        ):
            raise ValueError("RSI thresholds must satisfy 0 <= oversold < overbought <= 100")
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
            rsi = self._latest_rsi(closes)
            if rsi is None:
                continue
            held_quantity = holdings.get(symbol, 0.0)
            command = None
            if rsi <= self.oversold and held_quantity == 0:
                command = buy_at_next_open(
                    symbol,
                    portfolio,
                    market.get_latest_closed(symbol),
                    self.allocation,
                )
            elif rsi >= self.overbought and held_quantity > 0:
                command = sell_at_next_open(symbol, held_quantity)
            if command is not None:
                commands.append(command)
        return commands

    def _latest_rsi(self, closes: Series[float]) -> float | None:
        if len(closes) < self.period + 1:
            return None
        deltas = closes.astype(float).diff().dropna()
        gains = deltas.clip(lower=0.0)
        losses = -deltas.clip(upper=0.0)
        average_gain = float(gains.iloc[: self.period].mean())
        average_loss = float(losses.iloc[: self.period].mean())
        for index in range(self.period, len(deltas)):
            average_gain = (
                (average_gain * (self.period - 1)) + float(gains.iloc[index])
            ) / self.period
            average_loss = (
                (average_loss * (self.period - 1)) + float(losses.iloc[index])
            ) / self.period
        if average_loss == 0:
            return 100.0 if average_gain > 0 else 50.0
        relative_strength = average_gain / average_loss
        return 100.0 - (100.0 / (1.0 + relative_strength))
