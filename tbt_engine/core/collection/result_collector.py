from abc import ABC, abstractmethod
from typing import TypeAlias

from tbt_engine.core.costs.transaction_cost_model import ExecutionCost
from tbt_engine.core.execution.execution_model import Fill
from tbt_engine.core.ledger import LedgerEntry
from tbt_engine.core.orders import Order, OrderEvent
from tbt_engine.core.result import BacktestResult
from tbt_engine.core.valuation.valuation_model import PortfolioValuation

SimulationRecord: TypeAlias = (
    Order | OrderEvent | Fill | ExecutionCost | LedgerEntry | PortfolioValuation
)


class ResultCollector(ABC):
    @abstractmethod
    def begin(self, starting_equity: float) -> None:
        """Start a run and reset any state retained from an earlier run."""
        raise NotImplementedError

    @abstractmethod
    def collect(self, record: SimulationRecord) -> None:
        """Observe one immutable record without changing simulation behavior."""
        raise NotImplementedError

    @abstractmethod
    def finalize(self) -> BacktestResult:
        """Finalize and return the collected result."""
        raise NotImplementedError
