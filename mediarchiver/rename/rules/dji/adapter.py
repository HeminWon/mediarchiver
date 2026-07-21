import os
from pathlib import Path

from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule import RuleFileSet
from mediarchiver.rename.rules import is_formatted_file_name
from mediarchiver.rename.rules.dji.detectors.pocket import PocketDetector
from mediarchiver.rename.rules.dji.presets.pocket4p import PRESET as POCKET4P_PRESET
from mediarchiver.rename.rules.dji.presets.pocket4p import mark_destination_conflicts


class DjiPocket4PRule:
    id = "dji:pocket4p"
    label = "DJI Pocket 4P"
    description = "Strict DJI Pocket 4P media rename rule"
    required_tools = ("exiftool", "ffprobe")

    def __init__(self):
        self.detector = PocketDetector()
        self.preset = POCKET4P_PRESET

    def collect_files(self, source_dir: str, include_formatted: bool = False) -> RuleFileSet:
        media_paths = []
        sidecar_paths = []
        for name in sorted(os.listdir(source_dir)):
            file_path = os.path.join(source_dir, name)
            if not os.path.isfile(file_path):
                continue
            if not include_formatted and is_formatted_file_name(name):
                continue
            if self.detector.candidate_sidecar_path(file_path):
                sidecar_paths.append(file_path)
                continue
            if self.detector.candidate_media_path(file_path):
                media_paths.append(file_path)
        return RuleFileSet(
            source_dir=source_dir,
            media_paths=media_paths,
            sidecar_paths=sidecar_paths,
        )

    def build_plan_items(
        self,
        source_dir: str,
        contexts: dict[str, FileMetadataContext],
        file_set: RuleFileSet,
    ) -> list[RenamePlanItem]:
        items = []
        primary_items_by_stem = {}
        for media_path in file_set.media_paths:
            context = contexts[media_path]
            match = self.detector.match_media(context)
            if not match.matched:
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
            item = self.preset.build_media_item(source_dir, context, match.reasons)
            items.append(item)
            if context.is_video:
                primary_items_by_stem[Path(media_path).stem] = item

        for sidecar_path in file_set.sidecar_paths:
            items.append(self.preset.build_lrf_item(sidecar_path, primary_items_by_stem))

        return mark_destination_conflicts(items)


RULE = DjiPocket4PRule()
