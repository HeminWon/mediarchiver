import glob
import os
from functools import cache

from mediarchiver.common.tool import sony_xml_video_stem
from mediarchiver.rename.brand_rules.base import SidecarRename
from mediarchiver.rename.metadata import FileMetadataContext


@cache
def _sony_xml_lookup_by_video_stem(folder_path):
    """Build a video_stem -> [xml_file_path, ...] lookup for SONY XML pairing."""
    lookup = {}
    for file_name in sorted(glob.glob(os.path.join(folder_path, "*"))):
        base = os.path.basename(file_name)
        result = sony_xml_video_stem(base)
        if result is None:
            continue
        video_stem, _ = result
        lookup.setdefault(video_stem.upper(), []).append(file_name)
    return lookup


def sony_xml_match_xmls(folder_path, video_file):
    """Return list of SONY XML sidecar paths that pair with *video_file*."""
    video_stem = os.path.splitext(os.path.basename(video_file))[0]
    return _sony_xml_lookup_by_video_stem(folder_path).get(video_stem.upper(), [])


class SonyXmlSidecarRule:
    name = "sony_xml"

    def find_sidecars(
        self,
        source_dir: str,
        context: FileMetadataContext,
        new_file_name: str,
    ) -> list[SidecarRename]:
        if not context.is_video:
            return []

        new_file_name_stem = os.path.splitext(new_file_name)[0]
        renames = []
        for xml_path in sony_xml_match_xmls(source_dir, context.file_path):
            result = sony_xml_video_stem(os.path.basename(xml_path))
            if result is None:
                continue
            _, xml_suffix = result
            renames.append(
                SidecarRename(
                    source=xml_path,
                    destination=os.path.join(source_dir, new_file_name_stem + xml_suffix),
                )
            )
        return renames
