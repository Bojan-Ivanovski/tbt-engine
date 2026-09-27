import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, NewType, TypeAlias

OrderId = NewType("OrderId", int)


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class ExecutionTime(str, Enum):
    NEXT_OPEN = "next_open"
    SESSION_CLOSE = "session_close"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderEventType(str, Enum):
    ACCEPTED = "accepted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    NO_FILL = "no_fill"
    CANCELLED = "cancelled"
    CANCELLATION_REJECTED = "cancellation_rejected"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: Side
    quantity: float
    execution_time: ExecutionTime = ExecutionTime.NEXT_OPEN

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "quantity", float(self.quantity))


@dataclass(frozen=True)
class SubmitOrder:
    intent: OrderIntent


@dataclass(frozen=True)
class CancelOrder:
    order_id: OrderId


StrategyCommand: TypeAlias = SubmitOrder | CancelOrder


@dataclass(frozen=True)
class Order:
    id: OrderId
    intent: OrderIntent
    status: OrderStatus
    submitted_at: str
    submitted_phase: str
    eligible_candle: int
    filled_quantity: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "filled_quantity", float(self.filled_quantity))
        if (
            not math.isfinite(self.filled_quantity)
            or self.filled_quantity < 0
            or self.filled_quantity > self.intent.quantity
        ):
            raise ValueError("Filled quantity must be between zero and the order quantity")

    @property
    def remaining_quantity(self) -> float:
        return self.intent.quantity - self.filled_quantity


@dataclass(frozen=True)
class OrderEvent:
    order_id: OrderId
    time: str
    phase: str
    type: OrderEventType
    reason: str | None = None


class OrderState:
    """Immutable order snapshot exposed to a strategy callback."""

    def __init__(self, orders: Mapping[OrderId, Order]):
        self._orders = MappingProxyType(dict(orders))

    def all(self) -> tuple[Order, ...]:
        return tuple(self._orders.values())

    def active(self) -> tuple[Order, ...]:
        return tuple(
            order
            for order in self._orders.values()
            if order.status in {OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED}
        )

    def get(self, order_id: OrderId) -> Order | None:
        return self._orders.get(order_id)
