from typing import Protocol

from mediarchiver.rename.metadata import FileMetadataContext


class BaseDetector(Protocol):
    """Base protocol for all metadata-driven detectors."""

    def match_media(self, context: FileMetadataContext) -> tuple[str, ...]:
        """Return tuple of match reasons (empty if no match)."""
        ...
