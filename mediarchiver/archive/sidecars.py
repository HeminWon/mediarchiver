import os
import re

SIDECAR_EXTENSIONS = {"aae", "lrf", "lrv", "log", "srt", "thm", "xmp", "xml"}


def is_sidecar_file(file_path):
    if not os.path.isfile(file_path):
        return False
    ext = os.path.splitext(file_path)[1][1:].lower()
    return ext in SIDECAR_EXTENSIONS


def find_sidecar_primary(sidecar_name, primary_by_stem):
    matches = []
    for candidate_stem in get_sidecar_primary_stem_candidates(sidecar_name):
        primary = primary_by_stem.get(candidate_stem.lower())
        if primary is not None and primary not in matches:
            matches.append(primary)
    if len(matches) == 1:
        return matches[0]
    return None


def get_sidecar_primary_stem_candidates(sidecar_name):
    stem = os.path.splitext(sidecar_name)[0]
    candidates = [stem]

    sony_match = re.fullmatch(r"(C\d{4})M\d{2}", stem, flags=re.IGNORECASE)
    if sony_match:
        candidates.append(sony_match.group(1))

    return candidates
