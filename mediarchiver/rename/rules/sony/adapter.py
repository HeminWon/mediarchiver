from mediarchiver.rename.inventory import SourceInventory
from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule import RuleFileSet
from mediarchiver.rename.rules.sony.detectors.a7m4 import SonyA7M4Detector
from mediarchiver.rename.rules.sony.presets.a7m4 import PRESET as A7M4_PRESET


class SonyA7M4Rule:
    id = "sony:a7m4"
    label = "Sony A7M4"
    description = "Sony A7M4 media rename rule"
    priority = 50
    required_tools = ("exiftool", "ffprobe")

    def __init__(self):
        self.detector = SonyA7M4Detector()
        self.preset = A7M4_PRESET

    def collect_files(self, inventory: SourceInventory) -> RuleFileSet:
        sidecar_paths = [
            file_path
            for file_path in inventory.all_paths
            if self.detector.candidate_sidecar_path(file_path)
        ]
        return RuleFileSet(
            source_dir=inventory.source_dir,
            media_paths=list(inventory.media_paths),
            sidecar_paths=sidecar_paths,
        )

    def build_plan_items(
        self,
        source_dir: str,
        contexts: dict[str, FileMetadataContext],
        file_set: RuleFileSet,
    ) -> list[RenamePlanItem]:
        items = []
        primary_items_by_key = {}
        for media_path in file_set.media_paths:
            context = contexts[media_path]
            match_reasons = self.detector.match_media(context)
            if not match_reasons:
                items.append(
                    RenamePlanItem(
                        source=media_path,
                        destination=None,
                        action="rename",
                        status="skipped",
                        reason="rule_not_matched",
                        details={"rule": self.id},
                    )
                )
                continue
            item = self.preset.build_media_item(source_dir, context, match_reasons)
            items.append(item)
            primary_key = self.preset.primary_key_from_name(context.file_name)
            if primary_key is not None and primary_key not in primary_items_by_key:
                primary_items_by_key[primary_key] = item

        for sidecar_path in file_set.sidecar_paths:
            items.append(
                self.preset.build_sidecar_item(sidecar_path, primary_items_by_key)
            )
        return items


RULE = SonyA7M4Rule()
