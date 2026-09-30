from dataclasses import dataclass

from tbt_engine.instruments import InstrumentIdentifier


@dataclass(frozen=True, order=True, slots=True)
class MarketIdentifier(InstrumentIdentifier):
    """Provider-neutral market instrument or universe identifier."""

    scheme: str
    value: str
    market: str | None = None

    def __post_init__(self) -> None:
        super(MarketIdentifier, self).__post_init__()
        market = self.market.strip().upper() if self.market is not None else None
        if market == "":
            raise ValueError("Market identifier market must not be empty")
        object.__setattr__(self, "market", market)


__all__ = ["MarketIdentifier"]
