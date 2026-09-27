import logging

from tbt_engine.core.collection import InMemoryResultCollector, ResultCollector
from tbt_engine.core.costs import TransactionCostModel, ZeroTransactionCostModel
from tbt_engine.core.execution import DailyBarExecutionModel, ExecutionModel
from tbt_engine.core.market import Market
from tbt_engine.core.pipeline import SimulationPipeline
from tbt_engine.core.portfolio import InitialPortfolio, Portfolio
from tbt_engine.core.result import BacktestResult
from tbt_engine.core.strategy import Strategy
from tbt_engine.core.valuation import ClosePriceValuationModel, ValuationModel
from tbt_engine.providers.provider import Provider

logger = logging.getLogger(__name__)


class Engine:
    def __init__(
        self,
        market: Market | None = None,
        provider: Provider | None = None,
        initial_portfolio: InitialPortfolio | None = None,
        execution_model: ExecutionModel | None = None,
        transaction_cost_model: TransactionCostModel | None = None,
        valuation_model: ValuationModel | None = None,
        result_collector: ResultCollector | None = None,
    ):
        if provider is None:
            from tbt_engine.providers.yahoo_provider import YahooProvider

            provider = YahooProvider()

        self.provider = provider
        self.market = Market() if market is None else market
        self.market.set_provider(provider)
        self.initial_portfolio = (
            InitialPortfolio() if initial_portfolio is None else initial_portfolio
        )
        self.execution_model = (
            DailyBarExecutionModel() if execution_model is None else execution_model
        )
        self.transaction_cost_model = (
            ZeroTransactionCostModel(currency=self.initial_portfolio.currency)
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
            self.initial_portfolio,
            opened_at=self.market.start.isoformat(),
        )
        strategy_assets = strategy.define_assets()
        self.market.set_assets(
            [
                *strategy_assets,
                *(position.symbol for position in self.initial_portfolio.positions),
            ]
        )
        pipeline = SimulationPipeline(
            execution_model=self.execution_model,
            transaction_cost_model=self.transaction_cost_model,
            valuation_model=self.valuation_model,
            result_collector=self.result_collector,
        )

        result = pipeline.run(
            strategy,
            self.market,
            portfolio,
            strategy_assets=strategy_assets,
        )
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


__all__ = ["Engine"]
