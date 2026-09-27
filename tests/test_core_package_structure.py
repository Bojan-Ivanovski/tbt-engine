import unittest

from tbt_engine import (
    BeforeOpenMarketState,
    ClosedMarketState,
    ClosePriceValuationModel,
    DailyBarExecutionModel,
    InMemoryResultCollector,
    OpenMarketState,
    StandardTransactionCostModel,
    ZeroTransactionCostModel,
)
from tbt_engine.core.collection.in_memory_result_collector import (
    InMemoryResultCollector as ConcreteInMemoryResultCollector,
)
from tbt_engine.core.costs.standard_transaction_cost_model import (
    StandardTransactionCostModel as ConcreteStandardTransactionCostModel,
)
from tbt_engine.core.costs.zero_transaction_cost_model import (
    ZeroTransactionCostModel as ConcreteZeroTransactionCostModel,
)
from tbt_engine.core.execution.daily_bar_execution_model import (
    DailyBarExecutionModel as ConcreteDailyBarExecutionModel,
)
from tbt_engine.core.market.before_open_market_state import (
    BeforeOpenMarketState as ConcreteBeforeOpenMarketState,
)
from tbt_engine.core.market.closed_market_state import (
    ClosedMarketState as ConcreteClosedMarketState,
)
from tbt_engine.core.market.open_market_state import OpenMarketState as ConcreteOpenMarketState
from tbt_engine.core.valuation.close_price_valuation_model import (
    ClosePriceValuationModel as ConcreteClosePriceValuationModel,
)


class CorePackageStructureTests(unittest.TestCase):
    def test_top_level_exports_reference_split_implementations(self) -> None:
        self.assertIs(InMemoryResultCollector, ConcreteInMemoryResultCollector)
        self.assertIs(DailyBarExecutionModel, ConcreteDailyBarExecutionModel)
        self.assertIs(
            StandardTransactionCostModel,
            ConcreteStandardTransactionCostModel,
        )
        self.assertIs(ZeroTransactionCostModel, ConcreteZeroTransactionCostModel)
        self.assertIs(ClosePriceValuationModel, ConcreteClosePriceValuationModel)
        self.assertIs(BeforeOpenMarketState, ConcreteBeforeOpenMarketState)
        self.assertIs(OpenMarketState, ConcreteOpenMarketState)
        self.assertIs(ClosedMarketState, ConcreteClosedMarketState)


if __name__ == "__main__":
    unittest.main()
