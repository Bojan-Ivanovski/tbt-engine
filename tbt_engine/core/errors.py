"""Shared exception hierarchy for TBT Engine."""


class TbtEngineError(Exception):
    """Base class for engine-defined errors."""


class CapabilityError(TbtEngineError):
    """Base class for capability contract errors."""


class UnsupportedCapabilityError(CapabilityError):
    """Raised when a provider does not implement a requested capability."""

    def __init__(self, provider: str, capability: str) -> None:
        self.provider = provider
        self.capability = capability
        super().__init__(f"Provider {provider!r} does not support capability {capability!r}")


class UnsupportedCapabilityGroupError(CapabilityError):
    """Raised when a provider does not expose a requested domain collection."""

    def __init__(self, provider: str, group: str) -> None:
        self.provider = provider
        self.group = group
        super().__init__(f"Provider {provider!r} does not support capability group {group!r}")


class CapabilityDataUnavailableError(CapabilityError):
    """Raised when a supported capability has no data for a valid request."""


class InvalidCapabilityQueryError(CapabilityError):
    """Raised when a capability query violates its contract."""


class ProviderError(TbtEngineError):
    """Base class for failures reported by an external data provider."""


class ProviderAuthenticationError(ProviderError):
    """Raised when a provider rejects or requires credentials."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider refuses a request because of a usage limit."""


class ProviderRequestError(ProviderError):
    """Raised when a provider rejects an otherwise valid engine request."""


class ProviderResponseError(ProviderError):
    """Raised when a provider response cannot satisfy its declared contract."""


__all__ = [
    "CapabilityDataUnavailableError",
    "CapabilityError",
    "InvalidCapabilityQueryError",
    "ProviderAuthenticationError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderRequestError",
    "ProviderResponseError",
    "TbtEngineError",
    "UnsupportedCapabilityError",
    "UnsupportedCapabilityGroupError",
]
