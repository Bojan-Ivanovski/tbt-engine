import logging
from datetime import date

from tbt_engine.collection import InMemoryResultCollector, ResultCollector
from tbt_engine.costs import TransactionCostModel, ZeroTransactionCostModel
from tbt_engine.execution import DailyBarExecutionModel, ExecutionModel
from tbt_engine.market import Market
from tbt_engine.pipeline import SimulationPhase, SimulationPipeline
from tbt_engine.portfolio import Portfolio
from tbt_engine.providers.provider import Provider
from tbt_engine.result import BacktestResult
from tbt_engine.strategy import Strategy
from tbt_engine.valuation import ClosePriceValuationModel, ValuationModel

logger = logging.getLogger(__name__)


class Engine:
    def __init__(
        self,
        provider: Provider | None = None,
        start_date: date = date(2000, 1, 1),
        end_date: date | None = None,
        interval: str = "1d",
        initial_balance: float = 1000.0,
        execution_model: ExecutionModel | None = None,
        transaction_cost_model: TransactionCostModel | None = None,
        portfolio_currency: str = "USD",
        valuation_model: ValuationModel | None = None,
        result_collector: ResultCollector | None = None,
    ):
        if provider is None:
            from tbt_engine.providers.yahoo_provider import YahooProvider

            provider = YahooProvider()

        self.provider = provider
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.initial_balance = float(initial_balance)
        self.portfolio_currency = portfolio_currency.strip().upper()
        if len(self.portfolio_currency) != 3 or not self.portfolio_currency.isalpha():
            raise ValueError("Portfolio currency must be a three-letter code")
        self.execution_model = (
            DailyBarExecutionModel() if execution_model is None else execution_model
        )
        self.transaction_cost_model = (
            ZeroTransactionCostModel(currency=self.portfolio_currency)
            if transaction_cost_model is None
            else transaction_cost_model
        )
        self.valuation_model = (
            ClosePriceValuationModel() if valuation_model is None else valuation_model
        )
        self.result_collector = (
            InMemoryResultCollector() if result_collector is None else result_collector
        )

    def start(self, strategy: Strategy) -> BacktestResult:
        logger.info("Running strategy: %s", strategy.name)
        self._validate_cost_model_capabilities()
        portfolio = Portfolio(
            self.initial_balance,
            currency=self.portfolio_currency,
            opened_at=self.start_date.isoformat(),
        )
        market = Market(
            provider=self.provider,
            start=self.start_date,
            end=self.end_date,
            interval=self.interval,
        )
        market.set_assets(strategy.define_market())
        pipeline = SimulationPipeline(
            execution_model=self.execution_model,
            transaction_cost_model=self.transaction_cost_model,
            valuation_model=self.valuation_model,
            result_collector=self.result_collector,
        )

        result = pipeline.run(strategy, market, portfolio)
        logger.info(
            "Finished %s: equity=%.2f return=%.2f%% trades=%d",
            strategy.name,
            result.ending_equity,
            result.total_return_pct,
            len(result.trades),
        )
        return result

    def _validate_cost_model_capabilities(self) -> None:
        required = self.transaction_cost_model.required_capabilities
        if required:
            names = ", ".join(sorted(capability.value for capability in required))
            raise ValueError(
                "Transaction cost model requires unavailable market data capabilities: " f"{names}"
            )


__all__ = ["Engine", "SimulationPhase"]
