import os

from mediarchiver.common.tool import is_img, is_vid
from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.profile import ProfileFileSet
from mediarchiver.rename.profiles.apple.presets.iphone import PRESET as IPHONE_PRESET
from mediarchiver.rename.rules import is_formatted_file_name


class AppleIPhoneProfile:
    id = "apple:iphone"
    label = "Apple iPhone"
    description = "Apple iPhone media rename profile"
    required_tools = ("exiftool", "ffprobe")

    def __init__(self):
        self.preset = IPHONE_PRESET

    def collect_files(self, source_dir: str, include_formatted: bool = False) -> ProfileFileSet:
        media_paths = []
        for name in sorted(os.listdir(source_dir)):
            file_path = os.path.join(source_dir, name)
            if not os.path.isfile(file_path):
                continue
            if not include_formatted and is_formatted_file_name(name):
                continue
            if is_img(file_path) or is_vid(file_path):
                media_paths.append(file_path)
        return ProfileFileSet(
            source_dir=source_dir,
            media_paths=media_paths,
            sidecar_paths=[],
        )

    def build_plan_items(
        self,
        source_dir: str,
        contexts: dict[str, FileMetadataContext],
        file_set: ProfileFileSet,
    ) -> list[RenamePlanItem]:
        items = []
        for media_path in file_set.media_paths:
            context = contexts[media_path]
            match_reasons = match_apple_iphone(context)
            if not match_reasons:
                items.append(
                    RenamePlanItem(
                        source=media_path,
                        destination=None,
                        action="rename",
                        status="skipped",
                        reason="profile_not_matched",
                        details={"profile": self.id},
                    )
                )
                continue
            items.append(self.preset.build_media_item(source_dir, context, match_reasons))
        return items


def match_apple_iphone(context: FileMetadataContext) -> tuple[str, ...]:
    metadata = context.exif_metadata or {}
    reasons = []
    make = str(metadata.get("Make", "")).strip().lower()
    model = str(metadata.get("Model", "")).strip().lower()
    host = str(metadata.get("HostComputer", "")).strip().lower()
    if make == "apple":
        reasons.append("make=apple")
    if model.startswith("iphone"):
        reasons.append("model=iphone")
    if host.startswith("iphone"):
        reasons.append("host=iphone")
    return tuple(reasons)


PROFILE = AppleIPhoneProfile()
