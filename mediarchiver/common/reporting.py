import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class OperationSummary:
    total: int = 0
    by_status: Counter = field(default_factory=Counter)
    by_reason: Counter = field(default_factory=Counter)

    def add(self, status, reason=None):
        self.total += 1
        self.by_status[status] += 1
        if reason:
            self.by_reason[reason] += 1

    def as_dict(self):
        return {
            "total": self.total,
            "success": self.by_status.get("success", 0),
            "preview": self.by_status.get("preview", 0),
            "skipped": self.by_status.get("skipped", 0),
            "conflict": self.by_status.get("conflict", 0),
            "reasons": dict(self.by_reason),
        }


class OperationLogger:
    def __init__(self, report_dir, operation_name):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.operation_file = self.report_dir / f"{operation_name}_operations.jsonl"
        self.conflict_file = self.report_dir / f"{operation_name}_conflicts.jsonl"
        self.summary = OperationSummary()
        self._operation_fh = self.operation_file.open("a", encoding="utf-8")
        self._conflict_fh = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self._operation_fh is not None:
            self._operation_fh.close()
            self._operation_fh = None
        if self._conflict_fh is not None:
            self._conflict_fh.close()
            self._conflict_fh = None

    def record(
        self,
        action,
        source,
        destination=None,
        status="success",
        reason=None,
        details=None,
    ):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "source": str(source),
            "destination": str(destination) if destination is not None else None,
            "status": status,
            "reason": reason,
            "details": details or {},
        }
        self._write_json_line(self._operation_fh, payload)
        self.summary.add(status, reason)
        if status == "conflict":
            if self._conflict_fh is None:
                self._conflict_fh = self.conflict_file.open("a", encoding="utf-8")
            self._write_json_line(self._conflict_fh, payload)

    @staticmethod
    def _write_json_line(fh, payload):
        fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        fh.write("\n")
        fh.flush()
