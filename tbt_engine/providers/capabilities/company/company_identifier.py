from dataclasses import dataclass

from tbt_engine.instruments import InstrumentIdentifier


@dataclass(frozen=True, order=True, slots=True)
class CompanyIdentifier(InstrumentIdentifier):
    """Provider-neutral company identifier with an explicit identity scheme."""

    scheme: str
    value: str
    market: str | None = None

    def __post_init__(self) -> None:
        super(CompanyIdentifier, self).__post_init__()
        market = self.market.strip().upper() if self.market is not None else None
        if market == "":
            raise ValueError("Company identifier market must not be empty")
        object.__setattr__(self, "market", market)


__all__ = ["CompanyIdentifier"]
