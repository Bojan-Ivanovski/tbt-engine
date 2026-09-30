import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_SCHEME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_MIC_PATTERN = re.compile(r"^[A-Z0-9]{4}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def _calendar_date(value: date, label: str) -> date:
    if isinstance(value, datetime):
        raise TypeError(f"{label} must be a calendar date")
    return value


@dataclass(frozen=True, order=True, slots=True)
class InstrumentIdentifier:
    """Stable instrument identity under an explicit authority namespace."""

    scheme: str
    value: str

    def __post_init__(self) -> None:
        scheme = self.scheme.strip().lower()
        value = self.value.strip()
        if not _SCHEME_PATTERN.fullmatch(scheme):
            raise ValueError("Instrument identifier scheme is invalid")
        if not value:
            raise ValueError("Instrument identifier value must not be empty")
        object.__setattr__(self, "scheme", scheme)
        object.__setattr__(self, "value", value)

    @property
    def canonical(self) -> "InstrumentIdentifier":
        """Return the base identity value, discarding capability-specific subtype fields."""

        return InstrumentIdentifier(self.scheme, self.value)


class AssetType(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    FUTURE = "future"
    OPTION = "option"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    FIXED_INCOME = "fixed_income"
    RATE = "rate"
    UNKNOWN = "unknown"


@dataclass(frozen=True, order=True, slots=True)
class ExchangeIdentifier:
    """ISO 10383 market identifier code (MIC)."""

    mic: str

    def __post_init__(self) -> None:
        mic = self.mic.strip().upper()
        if not _MIC_PATTERN.fullmatch(mic):
            raise ValueError("Exchange MIC must contain four letters or digits")
        object.__setattr__(self, "mic", mic)

    def __str__(self) -> str:
        return self.mic


@dataclass(frozen=True, order=True, slots=True)
class CurrencyCode:
    """Normalized three-letter currency code."""

    value: str

    def __post_init__(self) -> None:
        value = self.value.strip().upper()
        if not _CURRENCY_PATTERN.fullmatch(value):
            raise ValueError("Currency must be a three-letter code")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Exchange:
    id: ExchangeIdentifier
    name: str
    timezone: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        timezone_name = self.timezone.strip()
        if not name:
            raise ValueError("Exchange name must not be empty")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unknown exchange timezone {timezone_name!r}") from error
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "timezone", timezone_name)


@dataclass(frozen=True, slots=True)
class Instrument:
    id: InstrumentIdentifier
    asset_type: AssetType
    exchange: ExchangeIdentifier | None = None
    currency: CurrencyCode | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", self.id.canonical)
        name = self.name.strip() if self.name is not None else None
        if name == "":
            raise ValueError("Instrument name must not be empty")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True, slots=True)
class ProviderSymbolMapping:
    """Provider symbol valid on an inclusive-start, exclusive-end date range."""

    instrument: InstrumentIdentifier
    provider: str
    symbol: str
    valid_from: date | None = None
    valid_to: date | None = None
    exchange: ExchangeIdentifier | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument", self.instrument.canonical)
        provider = self.provider.strip().lower()
        symbol = self.symbol.strip()
        if not provider:
            raise ValueError("Symbol provider must not be empty")
        if not symbol:
            raise ValueError("Provider symbol must not be empty")
        if self.valid_from is not None:
            _calendar_date(self.valid_from, "Symbol validity start")
        if self.valid_to is not None:
            _calendar_date(self.valid_to, "Symbol validity end")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from >= self.valid_to
        ):
            raise ValueError("Symbol validity start must precede its exclusive end")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "symbol", symbol)

    def is_valid_on(self, trading_date: date) -> bool:
        trading_date = _calendar_date(trading_date, "Symbol lookup date")
        return (self.valid_from is None or self.valid_from <= trading_date) and (
            self.valid_to is None or trading_date < self.valid_to
        )


class SymbolMappingError(LookupError):
    """Base error for failed or ambiguous symbol resolution."""


class SymbolMappingNotFoundError(SymbolMappingError):
    pass


class AmbiguousSymbolMappingError(SymbolMappingError):
    pass


def _mapping_sort_key(
    mapping: ProviderSymbolMapping,
) -> tuple[str, str, str, date, date, InstrumentIdentifier]:
    return (
        mapping.provider,
        mapping.symbol,
        mapping.exchange.mic if mapping.exchange is not None else "",
        mapping.valid_from or date.min,
        mapping.valid_to or date.max,
        mapping.instrument,
    )


def _ranges_overlap(left: ProviderSymbolMapping, right: ProviderSymbolMapping) -> bool:
    left_start = left.valid_from or date.min
    left_end = left.valid_to or date.max
    right_start = right.valid_from or date.min
    right_end = right.valid_to or date.max
    return left_start < right_end and right_start < left_end


class SymbolMap:
    """Immutable provider-symbol history with point-in-time resolution."""

    def __init__(self, mappings: Iterable[ProviderSymbolMapping] = ()) -> None:
        normalized = tuple(sorted(mappings, key=_mapping_sort_key))
        for index, mapping in enumerate(normalized):
            for other in normalized[index + 1 :]:
                same_symbol = (
                    mapping.provider,
                    mapping.symbol,
                    mapping.exchange,
                ) == (other.provider, other.symbol, other.exchange)
                if same_symbol and _ranges_overlap(mapping, other):
                    raise ValueError(
                        "Provider symbol mappings must not overlap for one provider and exchange"
                    )
        self._mappings = normalized

    @property
    def mappings(self) -> tuple[ProviderSymbolMapping, ...]:
        return self._mappings

    def resolve(
        self,
        provider: str,
        symbol: str,
        trading_date: date,
        exchange: ExchangeIdentifier | None = None,
    ) -> InstrumentIdentifier:
        provider = provider.strip().lower()
        symbol = symbol.strip()
        candidates = tuple(
            mapping
            for mapping in self._mappings
            if mapping.provider == provider
            and mapping.symbol == symbol
            and mapping.is_valid_on(trading_date)
            and (exchange is None or mapping.exchange == exchange)
        )
        if not candidates:
            raise SymbolMappingNotFoundError(
                f"No mapping for {provider}:{symbol} on {trading_date.isoformat()}"
            )
        instruments = frozenset(mapping.instrument for mapping in candidates)
        if len(instruments) != 1:
            raise AmbiguousSymbolMappingError(
                f"Ambiguous mapping for {provider}:{symbol} on {trading_date.isoformat()}"
            )
        return next(iter(instruments))

    def symbol_for(
        self,
        provider: str,
        instrument: InstrumentIdentifier,
        trading_date: date,
        exchange: ExchangeIdentifier | None = None,
    ) -> str:
        provider = provider.strip().lower()
        instrument = instrument.canonical
        candidates = tuple(
            mapping
            for mapping in self._mappings
            if mapping.provider == provider
            and mapping.instrument == instrument
            and mapping.is_valid_on(trading_date)
            and (exchange is None or mapping.exchange == exchange)
        )
        symbols = frozenset(mapping.symbol for mapping in candidates)
        if not symbols:
            raise SymbolMappingNotFoundError(
                f"No {provider} symbol for {instrument.scheme}:{instrument.value} "
                f"on {trading_date.isoformat()}"
            )
        if len(symbols) != 1:
            raise AmbiguousSymbolMappingError(
                f"Multiple {provider} symbols for {instrument.scheme}:{instrument.value} "
                f"on {trading_date.isoformat()}"
            )
        return next(iter(symbols))


__all__ = [
    "AmbiguousSymbolMappingError",
    "AssetType",
    "CurrencyCode",
    "Exchange",
    "ExchangeIdentifier",
    "Instrument",
    "InstrumentIdentifier",
    "ProviderSymbolMapping",
    "SymbolMap",
    "SymbolMappingError",
    "SymbolMappingNotFoundError",
]
