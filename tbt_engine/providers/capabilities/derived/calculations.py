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
class CalculationParameter:
    """One value-affecting parameter in a canonical string representation."""

    name: str
    value: str

    def __post_init__(self) -> None:
        name = _normalized_label(self.name, "Calculation parameter name")
        value = self.value.strip()
        if not value:
            raise ValueError("Calculation parameter value must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, order=True, slots=True, init=False)
class CalculationIdentity:
    """Reproducible identity for a normalized calculation and its convention."""

    name: str
    version: str
    observation_time_rule: str
    parameters: tuple[CalculationParameter, ...]

    def __init__(
        self,
        name: str,
        version: str,
        parameters: Iterable[CalculationParameter] = (),
        observation_time_rule: str = "latest_input",
    ) -> None:
        normalized_parameters = tuple(sorted(parameters))
        parameter_names = tuple(parameter.name for parameter in normalized_parameters)
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("Calculation parameter names must be unique")

        object.__setattr__(self, "name", _normalized_label(name, "Calculation name"))
        object.__setattr__(self, "version", _normalized_label(version, "Calculation version"))
        object.__setattr__(
            self,
            "observation_time_rule",
            _normalized_label(observation_time_rule, "Observation-time rule"),
        )
        object.__setattr__(self, "parameters", normalized_parameters)


__all__ = ["CalculationIdentity", "CalculationParameter"]
