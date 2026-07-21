from dataclasses import dataclass
from typing import Protocol

from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.plan import RenamePlanItem


@dataclass(frozen=True)
class ProfileFileSet:
    source_dir: str
    media_paths: list[str]
    sidecar_paths: list[str]


class RenameProfile(Protocol):
    id: str
    label: str
    description: str
    required_tools: tuple[str, ...]

    def collect_files(self, source_dir: str, include_formatted: bool = False) -> ProfileFileSet:
        ...

    def build_plan_items(
        self,
        source_dir: str,
        contexts: dict[str, FileMetadataContext],
        file_set: ProfileFileSet,
    ) -> list[RenamePlanItem]:
        ...
