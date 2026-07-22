
from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.rules.detectors.base import BaseDetector


class AppleIPhoneDetector(BaseDetector):
    def match_media(self, context: FileMetadataContext) -> tuple[str, ...]:
        metadata = context.exif_metadata or {}
        reasons = []
        make = str(metadata.get("Make", "")).strip().lower()
        model = str(metadata.get("Model", "")).strip().lower()
        host = str(metadata.get("HostComputer", "")).strip().lower()

        if make == "apple":
            reasons.append("metadata=make_apple")
        if model.startswith("iphone"):
            reasons.append("metadata=model_iphone")
        if host.startswith("iphone"):
            reasons.append("metadata=host_iphone")

        return tuple(reasons)
