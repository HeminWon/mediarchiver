from dataclasses import dataclass
from typing import Optional, Protocol

from mediarchiver.rename.metadata import FileMetadataContext


@dataclass(frozen=True)
class SidecarRename:
    source: str
    destination: str
    rule_name: Optional[str] = None
    paired_with: Optional[str] = None


class BrandRule(Protocol):
    name: str

    def find_sidecars(
        self,
        source_dir: str,
        context: FileMetadataContext,
        new_file_name: str,
    ) -> list[SidecarRename]:
        ...


SidecarRule = BrandRule
