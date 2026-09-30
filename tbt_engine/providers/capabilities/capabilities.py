from collections.abc import Iterable
from typing import TypeVar, overload

from tbt_engine.core.errors import UnsupportedCapabilityError
from tbt_engine.providers.capabilities.capability import Capability, CapabilityId

C = TypeVar("C", bound=Capability)


class Capabilities:
    """Provider-owned collection of capabilities for one data domain."""

    def __init__(self, provider: str, capabilities: Iterable[Capability] = ()) -> None:
        provider = provider.strip()
        if not provider:
            raise ValueError("Capabilities provider must not be empty")

        indexed: dict[CapabilityId, Capability] = {}
        for capability in capabilities:
            if capability.id in indexed:
                raise ValueError(f"Duplicate capability identifier {capability.id!s}")
            indexed[capability.id] = capability

        self._provider = provider
        self._capabilities = indexed

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return tuple(self._capabilities.values())

    @property
    def supported_capabilities(self) -> frozenset[CapabilityId]:
        return frozenset(self._capabilities)

    def supports(self, capability: CapabilityId | type[Capability]) -> bool:
        if isinstance(capability, CapabilityId):
            return capability in self._capabilities
        return any(isinstance(candidate, capability) for candidate in self._capabilities.values())

    @overload
    def require(self, capability: CapabilityId) -> Capability: ...

    @overload
    def require(self, capability: type[C]) -> C: ...

    def require(self, capability: CapabilityId | type[C]) -> Capability:
        if isinstance(capability, CapabilityId):
            implementation = self._capabilities.get(capability)
            label = str(capability)
        else:
            implementation = next(
                (
                    candidate
                    for candidate in self._capabilities.values()
                    if isinstance(candidate, capability)
                ),
                None,
            )
            label = capability.__name__

        if implementation is None:
            raise UnsupportedCapabilityError(self.provider, label)
        return implementation


__all__ = ["Capabilities"]
