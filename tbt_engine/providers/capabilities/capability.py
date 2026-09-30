from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class CapabilityId:
    """Stable identifier advertised by providers for an optional capability."""

    value: str

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("Capability identifier must not be empty")
        if any(character.isspace() for character in value):
            raise ValueError("Capability identifier must not contain whitespace")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


class Capability(ABC):
    """Base contract for one optional unit of provider behavior."""

    @property
    @abstractmethod
    def id(self) -> CapabilityId:
        """Return the stable identifier used for discovery and diagnostics."""
        raise NotImplementedError
