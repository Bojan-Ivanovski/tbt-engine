from collections.abc import Iterable

from tbt_engine.providers.capabilities.capabilities import Capabilities
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId

DERIVED_CAPABILITY_IDS = frozenset(
    CapabilityId(identifier)
    for identifier in (
        "derived.atr",
        "derived.ema",
        "derived.macd",
        "derived.returns",
        "derived.rsi",
        "derived.sma",
        "derived.volatility",
    )
)


class DerivedCapabilities(Capabilities):
    """Provider-owned collection of supported derived-data implementations."""

    def __init__(self, provider: str, capabilities: Iterable[Capability] = ()) -> None:
        normalized = tuple(sorted(capabilities, key=lambda capability: capability.id))
        invalid = tuple(
            capability.id
            for capability in normalized
            if capability.id not in DERIVED_CAPABILITY_IDS
        )
        if invalid:
            identifiers = ", ".join(str(identifier) for identifier in invalid)
            raise ValueError(f"Unsupported derived capability identifier(s): {identifiers}")
        super().__init__(provider, normalized)


__all__ = ["DERIVED_CAPABILITY_IDS", "DerivedCapabilities"]
