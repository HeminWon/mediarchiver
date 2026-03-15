from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RenameOptions:
    loose: bool = False
    include_formatted: bool = False
    time_offset_minutes: Optional[int] = None
