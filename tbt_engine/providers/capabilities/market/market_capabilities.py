from collections.abc import Iterable

from tbt_engine.providers.capabilities.capabilities import Capabilities
from tbt_engine.providers.capabilities.capability import Capability


class MarketCapabilities(Capabilities):
    """Provider-owned collection of normalized market-data capabilities."""

    def __init__(self, provider: str, capabilities: Iterable[Capability] = ()) -> None:
        capabilities = tuple(capabilities)
        for capability in capabilities:
            if not capability.id.value.startswith("market."):
                raise ValueError("Market capability identifier must use the 'market.' namespace")
        super().__init__(provider, capabilities)


__all__ = ["MarketCapabilities"]
