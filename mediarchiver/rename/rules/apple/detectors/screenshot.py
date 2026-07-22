from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.rules.detectors.base import BaseDetector


class AppleScreenshotDetector(BaseDetector):
    def match_media(self, context: FileMetadataContext) -> tuple[str, ...]:
        metadata = context.exif_metadata or {}
        if context.extension.lower() != ".png":
            return ()

        screenshot_reasons = screenshot_marker_reasons(metadata)
        if not screenshot_reasons:
            return ()

        apple_reasons = apple_source_reasons(metadata)
        if not apple_reasons:
            return ()

        return ("extension=png", *screenshot_reasons, *apple_reasons)


def has_screenshot_marker(metadata: dict) -> bool:
    return bool(screenshot_marker_reasons(metadata))


def screenshot_marker_reasons(metadata: dict) -> tuple[str, ...]:
    reasons = []
    for field in ("UserComment", "ImageDescription", "Description"):
        value = str(metadata.get(field, "")).strip().lower()
        if "screenshot" in value:
            reasons.append(f"metadata:{field}=screenshot")
    return tuple(reasons)


def apple_source_reasons(metadata: dict) -> tuple[str, ...]:
    reasons = []
    if is_apple_company_value(metadata, "Make"):
        reasons.append("metadata:Make=apple")
    if is_apple_company_value(metadata, "DeviceManufacturer"):
        reasons.append("metadata:DeviceManufacturer=apple")
    if is_apple_company_value(metadata, "PrimaryPlatform"):
        reasons.append("metadata:PrimaryPlatform=apple")
    if is_apple_company_value(metadata, "ProfileCreator"):
        reasons.append("metadata:ProfileCreator=apple")

    device_fields = ("Model", "DeviceModelName", "HostComputer")
    for field in device_fields:
        value = normalized_metadata_value(metadata, field)
        if any(marker in value for marker in ("iphone", "ipad", "macbook", "imac")):
            reasons.append(f"metadata:{field}=apple_device")

    software_fields = ("Software", "CreatorTool")
    for field in software_fields:
        value = normalized_metadata_value(metadata, field)
        if any(marker in value for marker in ("ios", "ipados", "macos", "iphone os")):
            reasons.append(f"metadata:{field}=apple_platform")

    return tuple(reasons)


def normalized_metadata_value(metadata: dict, field: str):
    return str(metadata.get(field, "")).strip().lower()


def is_apple_company_value(metadata: dict, field: str):
    value = normalized_metadata_value(metadata, field)
    return value == "apple" or value.startswith("apple ")
