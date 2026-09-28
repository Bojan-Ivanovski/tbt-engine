from abc import ABC
from collections.abc import Iterable
from datetime import date
from typing import Optional, TypeVar, overload

import pandas as pd

from tbt_engine.core.errors import UnsupportedCapabilityError, UnsupportedCapabilityGroupError
from tbt_engine.providers.capabilities import Capabilities, Capability, CapabilityId

C = TypeVar("C", bound=Capability)
G = TypeVar("G", bound=Capabilities)


class Provider(ABC):
    def __init__(self, capability_groups: Iterable[Capabilities] = ()) -> None:
        groups = tuple(capability_groups)
        group_types: set[type[Capabilities]] = set()
        for group in groups:
            group_type = type(group)
            if group_type in group_types:
                raise ValueError(f"Duplicate capability group {group_type.__name__}")
            group_types.add(group_type)
        self._capability_groups = groups

    @property
    def name(self) -> str:
        """Stable provider name used in discovery and diagnostics."""
        return type(self).__name__

    @property
    def capability_groups(self) -> tuple[Capabilities, ...]:
        """Domain collections composed into this provider."""
        return getattr(self, "_capability_groups", ())

    @property
    def supported_capabilities(self) -> frozenset[CapabilityId]:
        """Capabilities implemented through normalized provider contracts."""
        return frozenset(
            capability
            for group in self.capability_groups
            for capability in group.supported_capabilities
        )

    def supports(self, capability: CapabilityId | type[Capability]) -> bool:
        return any(group.supports(capability) for group in self.capability_groups)

    @overload
    def require_capability(self, capability: CapabilityId) -> Capability: ...

    @overload
    def require_capability(self, capability: type[C]) -> C: ...

    def require_capability(self, capability: CapabilityId | type[C]) -> Capability:
        for group in self.capability_groups:
            if group.supports(capability):
                if isinstance(capability, CapabilityId):
                    return group.require(capability)
                return group.require(capability)

        label = str(capability) if isinstance(capability, CapabilityId) else capability.__name__
        raise UnsupportedCapabilityError(self.name, label)

    def has_capability_group(self, group: type[G]) -> bool:
        return any(isinstance(candidate, group) for candidate in self.capability_groups)

    def require_capability_group(self, group: type[G]) -> G:
        implementation = next(
            (candidate for candidate in self.capability_groups if isinstance(candidate, group)),
            None,
        )
        if implementation is None:
            raise UnsupportedCapabilityGroupError(self.name, group.__name__)
        return implementation

    def get_history(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        """Compatibility API retained until the normalized OHLCV capability exists."""
        raise UnsupportedCapabilityError(self.name, "legacy.history")
