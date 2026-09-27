import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from tbt_engine.core.execution.execution_model import ExecutionMarketState, Fill, FillId


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
