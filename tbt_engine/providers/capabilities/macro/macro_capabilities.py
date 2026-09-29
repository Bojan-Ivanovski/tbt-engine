from collections.abc import Iterable

from tbt_engine.providers.capabilities.capabilities import Capabilities
from tbt_engine.providers.capabilities.capability import Capability


class MacroCapabilities(Capabilities):
    """Provider-owned collection of normalized macro-data capabilities."""

    def __init__(self, provider: str, capabilities: Iterable[Capability] = ()) -> None:
        capabilities = tuple(capabilities)
        for capability in capabilities:
            if not capability.id.value.startswith("macro."):
                raise ValueError("Macro capability identifier must use the 'macro.' namespace")
        super().__init__(provider, capabilities)


__all__ = ["MacroCapabilities"]
