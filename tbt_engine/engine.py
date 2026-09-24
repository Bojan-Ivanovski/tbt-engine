import logging
from datetime import date

from tbt_engine.market import Market, MarketState
from tbt_engine.portfolio import Portfolio, PortfolioState
from tbt_engine.providers.provider import Provider
from tbt_engine.result import BacktestResult, EquityPoint, Trade
from tbt_engine.strategy import Strategy

logger = logging.getLogger(__name__)


class Engine:
    def __init__(
        self,
        provider: Provider | None = None,
        start_date: date = date(2000, 1, 1),
        end_date: date | None = None,
        interval: str = "1d",
        initial_balance: float = 1000.0,
    ):
        if provider is None:
            from tbt_engine.providers.yahoo_provider import YahooProvider

            provider = YahooProvider()

        self.provider = provider
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.initial_balance = float(initial_balance)

    def start(self, strategy: Strategy) -> BacktestResult:
        logger.info("Running strategy: %s", strategy.name)
        portfolio = Portfolio(self.initial_balance)
        market = Market(
            provider=self.provider,
            start=self.start_date,
            end=self.end_date,
            interval=self.interval,
        )
        market.set_assets(strategy.define_market())

        trades: list[Trade] = []
        equity_history: list[EquityPoint] = []

        while market.next_candle() < market.final_candle:
            market_state = MarketState(market)
            candle_time = market_state.get_market_time_iso()
            signals = strategy.execute(
                market=market_state,
                portfolio=PortfolioState(portfolio),
            )

            for signal in signals:
                price = market_state.get_latest_closed(signal.asset.symbol)
                if signal.execute(portfolio, market_state):
                    trades.append(
                        Trade(
                            time=candle_time,
                            symbol=signal.asset.symbol,
                            side=signal.side,
                            quantity=signal.asset.quantity,
                            price=price,
                        )
                    )

            equity = portfolio.balance + sum(
                asset.quantity * market_state.get_latest_closed(symbol)
                for symbol, asset in portfolio.holdings.items()
            )
            equity_history.append(EquityPoint(candle_time, equity))

        ending_equity = equity_history[-1].equity
        result = BacktestResult(
            starting_equity=self.initial_balance,
            ending_equity=ending_equity,
            trades=trades,
            equity_history=equity_history,
        )
        logger.info(
            "Finished %s: equity=%.2f return=%.2f%% trades=%d",
            strategy.name,
            result.ending_equity,
            result.total_return_pct,
            len(result.trades),
        )
        return result
