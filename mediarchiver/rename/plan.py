import json
import shlex
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

RENAME_PLAN_VERSION = 1


@dataclass(frozen=True)
class RenamePlanItem:
    source: str
    destination: Optional[str]
    action: str
    status: str
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, payload):
        return cls(
            source=payload["source"],
            destination=payload.get("destination"),
            action=payload.get("action", "rename"),
            status=payload["status"],
            reason=payload.get("reason"),
            details=payload.get("details") or {},
        )


@dataclass(frozen=True)
class RenamePlan:
    version: int
    operation: str
    source_dir: str
    options: Dict[str, Any]
    items: List[RenamePlanItem]

    @property
    def summary(self):
        counters = Counter(item.status for item in self.items)
        return {
            "total": len(self.items),
            "ready": counters.get("ready", 0),
            "skipped": counters.get("skipped", 0),
            "conflict": counters.get("conflict", 0),
            "invalid": counters.get("invalid", 0),
        }

    def to_dict(self):
        return {
            "version": self.version,
            "operation": self.operation,
            "source_dir": self.source_dir,
            "options": self.options,
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(
            version=payload["version"],
            operation=payload["operation"],
            source_dir=payload["source_dir"],
            options=payload.get("options") or {},
            items=[RenamePlanItem.from_dict(item) for item in payload.get("items") or []],
        )


def write_rename_plan(plan, path):
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8"
    )


def load_rename_plan(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    plan = RenamePlan.from_dict(payload)
    validate_rename_plan(plan)
    return plan


def render_rename_plan_shell(plan):
    validate_rename_plan(plan)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"# Generated from rename plan: {plan.source_dir}",
    ]

    ready_items = [item for item in plan.items if item.status == "ready"]
    if not ready_items:
        lines.append("# No ready rename actions in plan")
        return "\n".join(lines) + "\n"

    for item in ready_items:
        if item.destination is None:
            continue
        lines.append(f"mv {shlex.quote(item.source)} {shlex.quote(item.destination)}")
    return "\n".join(lines) + "\n"


def export_rename_plan_shell(plan, path):
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(render_rename_plan_shell(plan), encoding="utf-8")


def validate_rename_plan(plan):
    if plan.version != RENAME_PLAN_VERSION:
        raise ValueError(f"unsupported rename plan version: {plan.version}")
    if plan.operation != "rename":
        raise ValueError(f"unsupported plan operation: {plan.operation}")
    if not Path(plan.source_dir).is_absolute():
        raise ValueError("rename plan source_dir must be an absolute path")
    for item in plan.items:
        if not Path(item.source).is_absolute():
            raise ValueError(f"rename plan source must be an absolute path: {item.source}")
        if item.destination is not None and not Path(item.destination).is_absolute():
            raise ValueError(
                f"rename plan destination must be an absolute path: {item.destination}"
            )
