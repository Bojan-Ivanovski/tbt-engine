import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, NewType

from tbt_engine.costs import CostedFill
from tbt_engine.execution import FillId
from tbt_engine.orders import OrderId, Side

LedgerEntryId = NewType("LedgerEntryId", int)


class LedgerEntryType(str, Enum):
    OPENING_CASH = "opening_cash"
    TRADE = "trade"
    COMMISSION = "commission"
    FEE = "fee"


@dataclass(frozen=True)
class LedgerEntry:
    id: LedgerEntryId
    type: LedgerEntryType
    time: str
    phase: str
    currency: str
    cash_delta: float
    order_id: OrderId | None = None
    fill_id: FillId | None = None
    symbol: str | None = None
    quantity_delta: float = 0.0
    unit_price: float | None = None

    def __post_init__(self) -> None:
        currency = self.currency.strip().upper()
        symbol = None if self.symbol is None else self.symbol.strip().upper()
        cash_delta = float(self.cash_delta)
        quantity_delta = float(self.quantity_delta)
        unit_price = None if self.unit_price is None else float(self.unit_price)
        if int(self.id) <= 0:
            raise ValueError("Ledger entry ID must be positive")
        if not self.time or not self.phase:
            raise ValueError("Ledger entry time and phase must not be empty")
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("Ledger entry currency must be a three-letter code")
        if not math.isfinite(cash_delta) or not math.isfinite(quantity_delta):
            raise ValueError("Ledger entry deltas must be finite")
        if unit_price is not None and (not math.isfinite(unit_price) or unit_price <= 0):
            raise ValueError("Ledger entry unit price must be finite and positive")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "cash_delta", cash_delta)
        object.__setattr__(self, "quantity_delta", quantity_delta)
        object.__setattr__(self, "unit_price", unit_price)
        self._validate_shape()

    def _validate_shape(self) -> None:
        if self.type is LedgerEntryType.OPENING_CASH:
            if (
                self.cash_delta < 0
                or self.order_id is not None
                or self.fill_id is not None
                or self.symbol is not None
                or self.quantity_delta != 0
                or self.unit_price is not None
            ):
                raise ValueError("Opening cash entry has inconsistent fields")
            return

        if self.order_id is None or self.fill_id is None or self.symbol is None:
            raise ValueError("Execution ledger entry must reference an order, fill, and symbol")
        if self.type is LedgerEntryType.TRADE:
            if self.quantity_delta == 0 or self.cash_delta == 0 or self.unit_price is None:
                raise ValueError("Trade entry must contain quantity, cash, and unit price")
            expected_cash = -(self.quantity_delta * self.unit_price)
            if not math.isclose(self.cash_delta, expected_cash, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Trade entry cash and position movements do not reconcile")
            return

        if self.quantity_delta != 0 or self.unit_price is not None or self.cash_delta >= 0:
            raise ValueError("Direct-cost entry must contain only a negative cash movement")


@dataclass(frozen=True)
class LedgerState:
    currency: str
    cash: float
    positions: tuple[tuple[str, float], ...]

    def quantity(self, symbol: str) -> float:
        normalized_symbol = symbol.upper()
        return next(
            (
                quantity
                for current_symbol, quantity in self.positions
                if current_symbol == normalized_symbol
            ),
            0.0,
        )

    def as_positions(self) -> dict[str, float]:
        return dict(self.positions)


@dataclass(frozen=True)
class LedgerPosting:
    accepted: bool
    entries: tuple[LedgerEntry, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        if self.accepted == (self.reason is not None):
            raise ValueError(
                "Accepted postings cannot have a reason; rejected postings require one"
            )
        if not self.accepted and self.entries:
            raise ValueError("Rejected postings cannot contain committed entries")


class PortfolioLedger:
    def __init__(
        self,
        initial_cash: float,
        *,
        base_currency: str = "USD",
        opened_at: str = "initial",
    ):
        initial_cash = float(initial_cash)
        currency = base_currency.strip().upper()
        if not math.isfinite(initial_cash) or initial_cash < 0:
            raise ValueError("Initial cash must be finite and non-negative")
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("Portfolio base currency must be a three-letter code")
        opening_entry = LedgerEntry(
            id=LedgerEntryId(1),
            type=LedgerEntryType.OPENING_CASH,
            time=opened_at,
            phase="initialization",
            currency=currency,
            cash_delta=initial_cash,
        )
        self._base_currency = currency
        self._entries: list[LedgerEntry] = [opening_entry]
        self._cash = initial_cash
        self._positions: dict[str, float] = {}
        self._posted_fill_ids: set[FillId] = set()
        self._next_entry_id = 2

    @property
    def base_currency(self) -> str:
        return self._base_currency

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    @property
    def state(self) -> LedgerState:
        return self._make_state(self._cash, self._positions)

    def post(self, costed_fills: tuple[CostedFill, ...]) -> LedgerPosting:
        reason = self._validate_fills(costed_fills)
        if reason is not None:
            return LedgerPosting(accepted=False, reason=reason)

        candidate_entries = self._create_entries(costed_fills)
        projected_cash, projected_positions = self._apply_entries(
            candidate_entries,
            starting_cash=self._cash,
            starting_positions=self._positions,
        )
        if any(quantity < -1e-12 for quantity in projected_positions.values()):
            return LedgerPosting(accepted=False, reason="Insufficient position at execution")
        if projected_cash < -1e-12:
            return LedgerPosting(accepted=False, reason="Insufficient cash at execution")

        self._entries.extend(candidate_entries)
        self._cash = self._normalize_zero(projected_cash)
        self._positions = {
            symbol: self._normalize_zero(quantity)
            for symbol, quantity in projected_positions.items()
            if not math.isclose(quantity, 0.0, rel_tol=0.0, abs_tol=1e-12)
        }
        self._posted_fill_ids.update(
            costed_fill.fill.id for costed_fill in costed_fills if costed_fill.fill.id is not None
        )
        self._next_entry_id += len(candidate_entries)
        return LedgerPosting(accepted=True, entries=candidate_entries)

    def replay(self) -> LedgerState:
        cash, positions = self._apply_entries(
            self._entries,
            starting_cash=0.0,
            starting_positions={},
        )
        return self._make_state(cash, positions)

    def _validate_fills(self, costed_fills: tuple[CostedFill, ...]) -> str | None:
        batch_ids: set[FillId] = set()
        for costed_fill in costed_fills:
            fill = costed_fill.fill
            cost = costed_fill.cost
            if fill.id is None or cost.fill_id != fill.id:
                return "Execution cost does not reference its fill"
            if fill.id in self._posted_fill_ids or fill.id in batch_ids:
                return f"Fill {int(fill.id)} has already been posted"
            batch_ids.add(fill.id)
            if cost.currency != self._base_currency:
                return (
                    f"Unsupported execution cost currency {cost.currency}; "
                    f"portfolio base currency is {self._base_currency}"
                )
        return None

    def _create_entries(self, costed_fills: tuple[CostedFill, ...]) -> tuple[LedgerEntry, ...]:
        entries: list[LedgerEntry] = []
        next_entry_id = self._next_entry_id
        for costed_fill in costed_fills:
            fill = costed_fill.fill
            cost = costed_fill.cost
            if fill.id is None:
                raise RuntimeError("Validated fill has no ID")
            direction = 1.0 if fill.side is Side.BUY else -1.0
            entries.append(
                LedgerEntry(
                    id=LedgerEntryId(next_entry_id),
                    type=LedgerEntryType.TRADE,
                    time=fill.time,
                    phase=fill.phase.value,
                    currency=self._base_currency,
                    cash_delta=-(direction * fill.quantity * fill.price),
                    order_id=fill.order_id,
                    fill_id=fill.id,
                    symbol=fill.symbol,
                    quantity_delta=direction * fill.quantity,
                    unit_price=fill.price,
                )
            )
            next_entry_id += 1
            for entry_type, amount in (
                (LedgerEntryType.COMMISSION, cost.commission),
                (LedgerEntryType.FEE, cost.fees),
            ):
                if amount == 0:
                    continue
                entries.append(
                    LedgerEntry(
                        id=LedgerEntryId(next_entry_id),
                        type=entry_type,
                        time=fill.time,
                        phase=fill.phase.value,
                        currency=self._base_currency,
                        cash_delta=-amount,
                        order_id=fill.order_id,
                        fill_id=fill.id,
                        symbol=fill.symbol,
                    )
                )
                next_entry_id += 1
        return tuple(entries)

    @staticmethod
    def _apply_entries(
        entries: Iterable[LedgerEntry],
        *,
        starting_cash: float,
        starting_positions: dict[str, float],
    ) -> tuple[float, dict[str, float]]:
        cash = starting_cash
        positions = dict(starting_positions)
        for entry in entries:
            cash += entry.cash_delta
            if entry.symbol is not None and entry.quantity_delta != 0:
                positions[entry.symbol] = positions.get(entry.symbol, 0.0) + entry.quantity_delta
        return cash, positions

    def _make_state(self, cash: float, positions: dict[str, float]) -> LedgerState:
        return LedgerState(
            currency=self._base_currency,
            cash=PortfolioLedger._normalize_zero(cash),
            positions=tuple(
                sorted(
                    (symbol, PortfolioLedger._normalize_zero(quantity))
                    for symbol, quantity in positions.items()
                    if not math.isclose(quantity, 0.0, rel_tol=0.0, abs_tol=1e-12)
                )
            ),
        )

    @staticmethod
    def _normalize_zero(value: float) -> float:
        return 0.0 if math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1e-12) else value
