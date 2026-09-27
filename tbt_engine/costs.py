import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import Enum
from typing import Mapping

from tbt_engine.execution import ExecutionMarketState, Fill, FillId
from tbt_engine.orders import Side


class MarketDataCapability(str, Enum):
    HISTORICAL_QUOTES = "historical_quotes"
    TRADES = "trades"
    VOLUME_HISTORY = "volume_history"
    VOLATILITY_HISTORY = "volatility_history"
    ORDER_BOOK = "order_book"


@dataclass(frozen=True)
class ExecutionCost:
    fill_id: FillId
    model: str
    currency: str = "USD"
    parameters: tuple[tuple[str, float], ...] = ()
    commission: float = 0.0
    fees: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0

    def __post_init__(self) -> None:
        model = self.model.strip()
        currency = self.currency.strip().upper()
        if not model:
            raise ValueError("Execution cost model must not be empty")
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("Execution cost currency must be a three-letter code")
        parameters = tuple(sorted(self.parameters))
        for name, value in parameters:
            if not name or not math.isfinite(value):
                raise ValueError("Execution cost parameters must have finite named values")
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "parameters", parameters)
        for name in ("commission", "fees", "spread", "slippage"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name.capitalize()} cost must be finite and non-negative")
            object.__setattr__(self, name, value)

    @property
    def direct_cost(self) -> float:
        return self.commission + self.fees

    @property
    def price_adjustment_cost(self) -> float:
        return self.spread + self.slippage

    @property
    def total_cost(self) -> float:
        return self.direct_cost + self.price_adjustment_cost


@dataclass(frozen=True)
class CostedFill:
    fill: Fill
    cost: ExecutionCost

    def __post_init__(self) -> None:
        if self.fill.id is None or self.cost.fill_id != self.fill.id:
            raise ValueError("Execution cost must reference its fill")


class TransactionCostModel(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def parameters(self) -> Mapping[str, float]:
        raise NotImplementedError

    @property
    def currency(self) -> str:
        return "USD"

    @property
    def required_capabilities(self) -> frozenset[MarketDataCapability]:
        return frozenset()

    @property
    def configuration(self) -> dict[str, object]:
        return {
            "name": self.name,
            "currency": self.currency,
            "parameters": dict(self.parameters),
            "required_capabilities": sorted(
                capability.value for capability in self.required_capabilities
            ),
        }

    @abstractmethod
    def apply(
        self,
        fill: Fill,
        market: ExecutionMarketState,
        *,
        is_first_fill_for_order: bool,
    ) -> CostedFill:
        """Return an adjusted fill and explicit costs without mutating accounting state."""
        raise NotImplementedError


class ZeroTransactionCostModel(TransactionCostModel):
    @property
    def name(self) -> str:
        return "zero"

    @property
    def parameters(self) -> Mapping[str, float]:
        return {}

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
