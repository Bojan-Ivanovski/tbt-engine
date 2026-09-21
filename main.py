import logging
import sys
from typing import List

from engine import Engine
from engine.asset import Asset
from engine.market import MarketState
from engine.portfolio import PortfolioState
from engine.signals.buy import Buy
from engine.signals.sell import Sell
from engine.signals.signal import Signal
from engine.strategy import Strategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("trader")


class ExampleStrategy(Strategy):
    """Long-only SMA crossover strategy using 10% of available cash per entry."""

    def __init__(self, name: str = "ExampleSMA"):
        super().__init__(name=name)

    def define_market(self) -> List[str]:
        return ["AAPL", "NVDA", "MSFT"]

    def execute(self, market: MarketState, portfolio: PortfolioState) -> List[Signal]:
        holdings = portfolio.holdings()
        signals: List[Signal] = []

        for symbol in market.get_all_symbols():
            candles = market.get_past_data(symbol)
            if len(candles) < 21:
                continue

            closes = candles["Close"].to_numpy()
            sma5_prev = float(closes[-6:-1].mean())
            sma20_prev = float(closes[-21:-1].mean())
            sma5_now = float(closes[-5:].mean())
            sma20_now = float(closes[-20:].mean())

            held_quantity = float(getattr(holdings.get(symbol), "quantity", 0.0))
            crossed_up = sma5_prev <= sma20_prev and sma5_now > sma20_now
            crossed_down = sma5_prev >= sma20_prev and sma5_now < sma20_now

            if crossed_up and held_quantity == 0:
                price = market.get_latest_closed(symbol)
                quantity = (portfolio.balance() * 0.1) / price
                signals.append(Buy(Asset(symbol, quantity)))
            elif crossed_down and held_quantity > 0:
                signals.append(Sell(Asset(symbol, held_quantity)))

        return signals


def main() -> None:
    result = Engine().start(ExampleStrategy())
    logger.info(
        "Result: start=%.2f end=%.2f return=%.2f%% trades=%d",
        result.starting_equity,
        result.ending_equity,
        result.total_return_pct,
        len(result.trades),
    )


if __name__ == "__main__":
    main()
