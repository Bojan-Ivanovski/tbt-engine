import re
from dataclasses import dataclass

_IDENTIFIER_NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_GEOGRAPHY_SCHEME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


@dataclass(frozen=True, order=True, slots=True)
class MacroSeriesIdentifier:
    """Identity of an economic series under an explicit namespace."""

    namespace: str
    value: str
    variant: str | None = None

    def __post_init__(self) -> None:
        namespace = self.namespace.strip().lower()
        value = self.value.strip()
        variant = self.variant.strip() if self.variant is not None else None

        if not _IDENTIFIER_NAMESPACE_PATTERN.fullmatch(namespace):
            raise ValueError("Macro series namespace is invalid")
        if not value:
            raise ValueError("Macro series identifier value must not be empty")
        if variant == "":
            raise ValueError("Macro series identifier variant must not be empty")

        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "variant", variant)


@dataclass(frozen=True, order=True, slots=True)
class GeographyIdentifier:
    """Identity of a geography under an explicit scheme."""

    scheme: str
    value: str

    def __post_init__(self) -> None:
        scheme = self.scheme.strip().lower()
        value = self.value.strip()

        if not _GEOGRAPHY_SCHEME_PATTERN.fullmatch(scheme):
            raise ValueError("Geography identifier scheme is invalid")
        if not value:
            raise ValueError("Geography identifier value must not be empty")

        object.__setattr__(self, "scheme", scheme)
        object.__setattr__(self, "value", value)


__all__ = ["GeographyIdentifier", "MacroSeriesIdentifier"]
