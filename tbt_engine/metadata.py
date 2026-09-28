from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Provenance shared by normalized records returned through capabilities."""

    provider: str
    source: str
    retrieved_at: datetime
    source_record_id: str | None = None

    def __post_init__(self) -> None:
        provider = self.provider.strip()
        source = self.source.strip()
        source_record_id = (
            self.source_record_id.strip() if self.source_record_id is not None else None
        )
        if not provider:
            raise ValueError("Metadata provider must not be empty")
        if not source:
            raise ValueError("Metadata source must not be empty")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("Metadata retrieval time must be timezone-aware")
        if source_record_id == "":
            raise ValueError("Metadata source record identifier must not be empty")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "source_record_id", source_record_id)


__all__ = ["SourceMetadata"]
