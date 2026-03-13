from dataclasses import dataclass


@dataclass(frozen=True)
class RenameOptions:
    loose: bool = False
    include_formatted: bool = False
