from collections.abc import Iterable

from tbt_engine.providers.capabilities.capabilities import Capabilities
from tbt_engine.providers.capabilities.capability import Capability


class TextualCapabilities(Capabilities):
    """Provider-owned collection of normalized textual capabilities."""

    def __init__(self, provider: str, capabilities: Iterable[Capability] = ()) -> None:
        capabilities = tuple(capabilities)
        for capability in capabilities:
            if not capability.id.value.startswith("textual."):
                raise ValueError("Textual capability identifier must use the 'textual.' namespace")
        super().__init__(provider, capabilities)


__all__ = ["TextualCapabilities"]
