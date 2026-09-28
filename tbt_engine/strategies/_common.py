import math
from collections.abc import Iterable

from tbt_engine.core.orders import (
    ExecutionTime,
    OrderIntent,
    OrderState,
    Side,
    SubmitOrder,
)
from tbt_engine.core.portfolio import PortfolioState


def normalize_symbols(symbols: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted({symbol.strip().upper() for symbol in symbols}))
    if not normalized or "" in normalized:
        raise ValueError("Strategy symbols must contain at least one non-empty symbol")
    return normalized


def require_positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def require_allocation(value: float) -> float:
    allocation = float(value)
    if not math.isfinite(allocation) or allocation <= 0 or allocation > 1:
        raise ValueError("Allocation must be finite and greater than zero up to one")
    return allocation


def has_active_order(orders: OrderState, symbol: str) -> bool:
    return any(order.intent.symbol == symbol for order in orders.active())


def buy_at_next_open(
    symbol: str,
    portfolio: PortfolioState,
    reference_price: float,
    allocation: float,
) -> SubmitOrder | None:
    if not math.isfinite(reference_price) or reference_price <= 0:
        raise ValueError(f"Reference price for {symbol} must be finite and positive")
    quantity = (portfolio.balance() * allocation) / reference_price
    if not math.isfinite(quantity) or quantity <= 0:
        return None
    return SubmitOrder(
        OrderIntent(
            symbol=symbol,
            side=Side.BUY,
            quantity=quantity,
            execution_time=ExecutionTime.NEXT_OPEN,
        )
    )


def sell_at_next_open(symbol: str, quantity: float) -> SubmitOrder | None:
    if not math.isfinite(quantity) or quantity <= 0:
        return None
    return SubmitOrder(
        OrderIntent(
            symbol=symbol,
            side=Side.SELL,
            quantity=quantity,
            execution_time=ExecutionTime.NEXT_OPEN,
        )
    )
