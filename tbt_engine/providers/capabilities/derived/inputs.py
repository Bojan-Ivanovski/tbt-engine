from collections.abc import Iterable
from dataclasses import dataclass


def _normalized_label(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    if any(character.isspace() for character in normalized):
        raise ValueError(f"{label} must not contain whitespace")
    return normalized


@dataclass(frozen=True, order=True, slots=True)
class SeriesQualifier:
    """One normalized value-affecting convention in an input-series identity."""

    name: str
    value: str

    def __post_init__(self) -> None:
        name = _normalized_label(self.name, "Series qualifier name")
        value = self.value.strip()
        if not value:
            raise ValueError("Series qualifier value must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, order=True, slots=True, init=False)
class InputSeriesRef:
    """Stable identity for a selected component of an upstream data series."""

    namespace: str
    series: str
    field: str
    qualifiers: tuple[SeriesQualifier, ...]

    def __init__(
        self,
        namespace: str,
        series: str,
        field: str,
        qualifiers: Iterable[SeriesQualifier] = (),
    ) -> None:
        normalized_qualifiers = tuple(sorted(qualifiers))
        qualifier_names = tuple(qualifier.name for qualifier in normalized_qualifiers)
        if len(qualifier_names) != len(set(qualifier_names)):
            raise ValueError("Input-series qualifier names must be unique")

        object.__setattr__(self, "namespace", _normalized_label(namespace, "Input namespace"))
        object.__setattr__(self, "series", _normalized_label(series, "Input series identifier"))
        object.__setattr__(self, "field", _normalized_label(field, "Input field"))
        object.__setattr__(self, "qualifiers", normalized_qualifiers)


@dataclass(frozen=True, order=True, slots=True)
class DerivedInput:
    """An input series assigned to its semantic role in a calculation."""

    role: str
    series: InputSeriesRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _normalized_label(self.role, "Derived input role"))


def normalize_inputs(inputs: Iterable[DerivedInput]) -> tuple[DerivedInput, ...]:
    """Snapshot inputs into deterministic role order and reject ambiguous roles."""

    normalized = tuple(sorted(inputs))
    roles = tuple(item.role for item in normalized)
    if not normalized:
        raise ValueError("A derived calculation must have at least one input")
    if len(roles) != len(set(roles)):
        raise ValueError("Derived input roles must be unique")
    return normalized


__all__ = ["DerivedInput", "InputSeriesRef", "SeriesQualifier", "normalize_inputs"]
