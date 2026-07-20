from mediarchiver.rename.brand_rules.base import SidecarRename
from mediarchiver.rename.metadata import FileMetadataContext


class DjiSidecarRule:
    name = "dji"

    def find_sidecars(
        self,
        source_dir: str,
        context: FileMetadataContext,
        new_file_name: str,
    ) -> list[SidecarRename]:
        return []
