from typing import Mapping

from tbt_engine.core.costs.transaction_cost_model import (
    CostedFill,
    ExecutionCost,
    TransactionCostModel,
)
from tbt_engine.core.execution.execution_model import ExecutionMarketState, Fill


class ZeroTransactionCostModel(TransactionCostModel):
    def __init__(self, *, currency: str = "USD"):
        normalized_currency = currency.strip().upper()
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        self._currency = normalized_currency

    @property
    def name(self) -> str:
        return "zero"

    @property
    def parameters(self) -> Mapping[str, float]:
        return {}

    @property
    def currency(self) -> str:
        return self._currency

    def apply(
        self,
        fill: Fill,
        market: ExecutionMarketState,
        *,
        is_first_fill_for_order: bool,
    ) -> CostedFill:
        if fill.id is None:
            raise ValueError("A fill must have an ID before costs are applied")
        return CostedFill(
            fill=fill,
            cost=ExecutionCost(
                fill_id=fill.id,
                model=self.name,
                currency=self.currency,
            ),
        )
