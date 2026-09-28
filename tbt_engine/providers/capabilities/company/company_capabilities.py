from collections.abc import Iterable

from tbt_engine.providers.capabilities.capabilities import Capabilities
from tbt_engine.providers.capabilities.capability import Capability


class CompanyCapabilities(Capabilities):
    """Provider-owned collection of normalized company-data capabilities."""

    def __init__(self, provider: str, capabilities: Iterable[Capability] = ()) -> None:
        capabilities = tuple(capabilities)
        for capability in capabilities:
            if not capability.id.value.startswith("company."):
                raise ValueError("Company capability identifier must use the 'company.' namespace")
        super().__init__(provider, capabilities)


__all__ = ["CompanyCapabilities"]
