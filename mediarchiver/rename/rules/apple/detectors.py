def has_screenshot_marker(metadata: dict):
    for field in ("UserComment", "ImageDescription", "Description"):
        value = str(metadata.get(field, "")).strip().lower()
        if "screenshot" in value:
            return True
    return False


def has_apple_marker(metadata: dict):
    for field in (
        "Make",
        "DeviceManufacturer",
        "ProfileCMMType",
        "PrimaryPlatform",
        "ProfileCreator",
        "ProfileCopyright",
    ):
        value = str(metadata.get(field, "")).strip().lower()
        if "apple" in value:
            return True
    return False
