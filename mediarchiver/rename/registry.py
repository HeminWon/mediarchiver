from importlib import import_module
from pkgutil import iter_modules

from mediarchiver.rename import profiles as profiles_package
from mediarchiver.rename.profile import RenameProfile


def discover_profiles() -> tuple[RenameProfile, ...]:
    discovered = []
    package_prefix = profiles_package.__name__ + "."
    for module_info in iter_modules(profiles_package.__path__, package_prefix):
        if not module_info.ispkg:
            continue
        adapter_module_name = f"{module_info.name}.adapter"
        try:
            adapter_module = import_module(adapter_module_name)
        except ModuleNotFoundError as exc:
            if exc.name == adapter_module_name:
                continue
            raise
        discovered.extend(_profiles_from_adapter(adapter_module))
    return tuple(sorted(_validate_profiles(discovered), key=lambda profile: profile.id))


def _profiles_from_adapter(adapter_module):
    profiles = getattr(adapter_module, "PROFILES", None)
    if profiles is not None:
        return tuple(profiles)
    profile = getattr(adapter_module, "PROFILE", None)
    return () if profile is None else (profile,)


def _validate_profiles(profiles):
    profiles_by_id = {}
    for profile in profiles:
        profile_id = getattr(profile, "id", None)
        if not profile_id:
            raise ValueError(f"rename profile missing id: {profile!r}")
        if profile_id in profiles_by_id:
            raise ValueError(f"duplicate rename profile id: {profile_id}")
        profiles_by_id[profile_id] = profile
    return tuple(profiles_by_id.values())


PROFILES: tuple[RenameProfile, ...] = discover_profiles()
PROFILES_BY_ID = {profile.id: profile for profile in PROFILES}


def get_profile(profile_id: str) -> RenameProfile:
    try:
        return PROFILES_BY_ID[profile_id]
    except KeyError as exc:
        supported = ", ".join(sorted(PROFILES_BY_ID))
        raise ValueError(
            f"unsupported rename profile: {profile_id}. supported: {supported}"
        ) from exc


def list_profiles() -> tuple[RenameProfile, ...]:
    return PROFILES
