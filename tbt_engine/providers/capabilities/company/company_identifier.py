import re
from dataclasses import dataclass

_SCHEME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


@dataclass(frozen=True, order=True, slots=True)
class CompanyIdentifier:
    """Provider-neutral company identifier with an explicit identity scheme."""

    scheme: str
    value: str
    market: str | None = None

    def __post_init__(self) -> None:
        scheme = self.scheme.strip().lower()
        value = self.value.strip()
        market = self.market.strip().upper() if self.market is not None else None

        if not _SCHEME_PATTERN.fullmatch(scheme):
            raise ValueError("Company identifier scheme is invalid")
        if not value:
            raise ValueError("Company identifier value must not be empty")
        if market == "":
            raise ValueError("Company identifier market must not be empty")

        object.__setattr__(self, "scheme", scheme)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "market", market)


__all__ = ["CompanyIdentifier"]
