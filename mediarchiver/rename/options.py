from dataclasses import dataclass


@dataclass(frozen=True)
class RenameOptions:
    loose: bool = False
    rename: bool = False
    include_formatted: bool = False
    dry_run: bool = False

    @property
    def should_apply_changes(self):
        return self.rename and not self.dry_run
