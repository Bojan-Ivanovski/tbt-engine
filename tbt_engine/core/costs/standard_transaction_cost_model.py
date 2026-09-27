import math
from dataclasses import replace
from typing import Mapping

from tbt_engine.core.costs.transaction_cost_model import (
    CostedFill,
    ExecutionCost,
    TransactionCostModel,
)
from tbt_engine.core.execution.execution_model import ExecutionMarketState, Fill
from tbt_engine.core.orders import Side


class StandardTransactionCostModel(TransactionCostModel):
    """Deterministic costs supplied directly as programmatic model parameters."""

    def __init__(
        self,
        *,
        commission_per_order: float = 0.0,
        commission_per_unit: float = 0.0,
        fee_rate: float = 0.0,
        spread_bps: float = 0.0,
        slippage_bps: float = 0.0,
        currency: str = "USD",
    ):
        values = {
            "commission_per_order": float(commission_per_order),
            "commission_per_unit": float(commission_per_unit),
            "fee_rate": float(fee_rate),
            "spread_bps": float(spread_bps),
            "slippage_bps": float(slippage_bps),
        }
        for name, value in values.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if values["spread_bps"] + values["slippage_bps"] >= 10_000:
            raise ValueError("Combined spread and slippage must be less than 10,000 bps")
        normalized_currency = currency.strip().upper()
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        self._parameters = values
        self._currency = normalized_currency

    @property
    def name(self) -> str:
        return "standard"

    @property
    def parameters(self) -> Mapping[str, float]:
        return dict(self._parameters)

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

        reference_price = fill.reference_price
        if reference_price is None:
            raise ValueError("A fill must have a reference price before costs are applied")
        spread_per_unit = reference_price * self._parameters["spread_bps"] / 10_000
        slippage_per_unit = reference_price * self._parameters["slippage_bps"] / 10_000
        price_adjustment = spread_per_unit + slippage_per_unit
        execution_price = (
            reference_price + price_adjustment
            if fill.side is Side.BUY
            else reference_price - price_adjustment
        )
        adjusted_fill = replace(fill, price=execution_price)

        commission = self._parameters["commission_per_unit"] * fill.quantity
        if is_first_fill_for_order:
            commission += self._parameters["commission_per_order"]
        fees = execution_price * fill.quantity * self._parameters["fee_rate"]
        cost = ExecutionCost(
            fill_id=fill.id,
            model=self.name,
            currency=self.currency,
            parameters=tuple(self.parameters.items()),
            commission=commission,
            fees=fees,
            spread=spread_per_unit * fill.quantity,
            slippage=slippage_per_unit * fill.quantity,
        )
        return CostedFill(fill=adjusted_fill, cost=cost)
