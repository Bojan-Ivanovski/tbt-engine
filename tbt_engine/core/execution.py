import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, NewType

from tbt_engine.core.orders import Order, OrderId, Side

FillId = NewType("FillId", int)


class ExecutionPhase(str, Enum):
    OPEN = "open"
    CLOSE = "close"


class ExecutionOutcomeStatus(str, Enum):
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    NO_FILL = "no_fill"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Fill:
    order_id: OrderId
    symbol: str
    side: Side
    quantity: float
    price: float
    time: str
    phase: ExecutionPhase
    id: FillId | None = None
    reference_price: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "quantity", float(self.quantity))
        object.__setattr__(self, "price", float(self.price))
        reference_price = (
            self.price if self.reference_price is None else float(self.reference_price)
        )
        object.__setattr__(self, "reference_price", reference_price)
        if not math.isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("Fill quantity must be finite and greater than zero")
        if not math.isfinite(self.price) or self.price <= 0:
            raise ValueError("Fill price must be finite and greater than zero")
        if not math.isfinite(reference_price) or reference_price <= 0:
            raise ValueError("Fill reference price must be finite and greater than zero")


@dataclass(frozen=True)
class ExecutionOutcome:
    status: ExecutionOutcomeStatus
    remaining_quantity: float
    fills: tuple[Fill, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "fills", tuple(self.fills))
        object.__setattr__(self, "remaining_quantity", float(self.remaining_quantity))
        if not math.isfinite(self.remaining_quantity) or self.remaining_quantity < 0:
            raise ValueError("Remaining quantity must be finite and non-negative")
        if self.status in {
            ExecutionOutcomeStatus.FILLED,
            ExecutionOutcomeStatus.PARTIALLY_FILLED,
        }:
            if not self.fills:
                raise ValueError("A filled execution outcome must contain at least one fill")
        elif self.fills:
            raise ValueError("A no-fill or rejected outcome cannot contain fills")
        if self.status is ExecutionOutcomeStatus.FILLED and self.remaining_quantity != 0:
            raise ValueError("A filled execution outcome cannot have remaining quantity")
        if self.status is ExecutionOutcomeStatus.PARTIALLY_FILLED and self.remaining_quantity <= 0:
            raise ValueError("A partial execution outcome must have remaining quantity")
        if self.status is ExecutionOutcomeStatus.REJECTED and not self.reason:
            raise ValueError("A rejected execution outcome must include a reason")


class ExecutionMarketState:
    """Immutable prices available to an execution model at one market phase."""

    def __init__(
        self,
        time: str,
        phase: ExecutionPhase,
        prices: Mapping[str, float],
    ):
        normalized_prices: dict[str, float] = {}
        for symbol, raw_price in prices.items():
            price = float(raw_price)
            if not math.isfinite(price) or price <= 0:
                raise ValueError(f"Invalid execution price for {symbol.upper()}")
            normalized_prices[symbol.upper()] = price
        self._time = time
        self._phase = phase
        self._prices = MappingProxyType(normalized_prices)

    @property
    def time(self) -> str:
        return self._time

    @property
    def phase(self) -> ExecutionPhase:
        return self._phase

    def get_price(self, symbol: str) -> float | None:
        return self._prices.get(symbol.upper())


class ExecutionModel(ABC):
    @abstractmethod
    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        """Return a deterministic outcome without mutating portfolio state."""
        raise NotImplementedError


class DailyBarExecutionModel(ExecutionModel):
    """Fully fill market orders at an eligible daily-bar open or close."""

    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        price = market.get_price(order.intent.symbol)
        if price is None:
            return ExecutionOutcome(
                status=ExecutionOutcomeStatus.REJECTED,
                remaining_quantity=order.remaining_quantity,
                reason=f"No execution price available for {order.intent.symbol}",
            )
        fill = Fill(
            order_id=order.id,
            symbol=order.intent.symbol,
            side=order.intent.side,
            quantity=order.remaining_quantity,
            price=price,
            time=market.time,
            phase=market.phase,
        )
        return ExecutionOutcome(
            status=ExecutionOutcomeStatus.FILLED,
            remaining_quantity=0,
            fills=(fill,),
        )
