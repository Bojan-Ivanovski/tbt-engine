import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from tbt_engine.ledger import LedgerState


class ValuationPhase(str, Enum):
    CLOSE = "close"


class ValuationMarketState:
    """Immutable point-in-time prices available to a valuation model."""

    def __init__(
        self,
        *,
        time: str,
        phase: ValuationPhase,
        prices: Mapping[str, float],
    ):
        if not time:
            raise ValueError("Valuation market time must not be empty")
        normalized_prices: dict[str, float] = {}
        for symbol, raw_price in prices.items():
            price = float(raw_price)
            if not math.isfinite(price) or price <= 0:
                raise ValueError(f"Invalid valuation price for {symbol.upper()}")
            normalized_prices[symbol.upper()] = price
        self._time = time
        self._phase = phase
        self._prices = MappingProxyType(normalized_prices)

    @property
    def time(self) -> str:
        return self._time

    @property
    def phase(self) -> ValuationPhase:
        return self._phase

    @property
    def prices(self) -> Mapping[str, float]:
        return self._prices

    def get_price(self, symbol: str) -> float | None:
        return self._prices.get(symbol.upper())


@dataclass(frozen=True)
class PositionValuation:
    symbol: str
    quantity: float
    price: float
    market_value: float

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        quantity = float(self.quantity)
        price = float(self.price)
        market_value = float(self.market_value)
        if not symbol:
            raise ValueError("Valued position symbol must not be empty")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Valued position quantity must be finite and positive")
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Valuation price must be finite and positive")
        if not math.isfinite(market_value) or not math.isclose(
            market_value,
            quantity * price,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Position market value does not reconcile")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "market_value", market_value)


@dataclass(frozen=True)
class PortfolioValuation:
    time: str
    phase: ValuationPhase
    model: str
    currency: str
    cash: float
    positions: tuple[PositionValuation, ...]
    total_equity: float

    def __post_init__(self) -> None:
        model = self.model.strip()
        currency = self.currency.strip().upper()
        cash = float(self.cash)
        positions = tuple(self.positions)
        total_equity = float(self.total_equity)
        if not self.time or not model:
            raise ValueError("Valuation time and model must not be empty")
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("Valuation currency must be a three-letter code")
        if not math.isfinite(cash):
            raise ValueError("Valuation cash must be finite")
        symbols = [position.symbol for position in positions]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Valuation cannot contain duplicate positions")
        expected_equity = cash + sum(position.market_value for position in positions)
        if not math.isfinite(total_equity) or not math.isclose(
            total_equity,
            expected_equity,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Portfolio valuation does not reconcile")
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "total_equity", total_equity)


class ValuationModel(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def value(
        self,
        portfolio: LedgerState,
        market: ValuationMarketState,
    ) -> PortfolioValuation:
        """Value immutable portfolio state using only the supplied market snapshot."""
        raise NotImplementedError


class ClosePriceValuationModel(ValuationModel):
    @property
    def name(self) -> str:
        return "close_price"

    def value(
        self,
        portfolio: LedgerState,
        market: ValuationMarketState,
    ) -> PortfolioValuation:
        positions: list[PositionValuation] = []
        for symbol, quantity in portfolio.positions:
            price = market.get_price(symbol)
            if price is None:
                raise ValueError(f"No valuation price available for {symbol}")
            positions.append(
                PositionValuation(
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    market_value=quantity * price,
                )
            )
        total_equity = portfolio.cash + sum(position.market_value for position in positions)
        return PortfolioValuation(
            time=market.time,
            phase=market.phase,
            model=self.name,
            currency=portfolio.currency,
            cash=portfolio.cash,
            positions=tuple(positions),
            total_equity=total_equity,
        )
