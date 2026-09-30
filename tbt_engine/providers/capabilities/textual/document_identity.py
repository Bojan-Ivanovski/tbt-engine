import re
from dataclasses import dataclass

_NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


def _normalize_namespace(namespace: str, label: str) -> str:
    normalized = namespace.strip().lower()
    if not _NAMESPACE_PATTERN.fullmatch(normalized):
        raise ValueError(f"{label} namespace is invalid")
    return normalized


@dataclass(frozen=True, order=True, slots=True)
class DocumentIdentifier:
    """Stable source-document identity within an explicit authority namespace."""

    namespace: str
    value: str

    def __post_init__(self) -> None:
        namespace = _normalize_namespace(self.namespace, "Document identifier")
        value = self.value.strip()
        if not value:
            raise ValueError("Document identifier value must not be empty")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, order=True, slots=True)
class DocumentRevisionIdentifier:
    """Stable revision identity kept distinct from its source document identity."""

    namespace: str
    value: str

    def __post_init__(self) -> None:
        namespace = _normalize_namespace(self.namespace, "Document revision identifier")
        value = self.value.strip()
        if not value:
            raise ValueError("Document revision identifier value must not be empty")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)


__all__ = ["DocumentIdentifier", "DocumentRevisionIdentifier"]
