import json
from datetime import datetime, timezone
from pathlib import Path


class OperationLogger:
    def __init__(self, report_dir, operation_name):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.operation_file = self.report_dir / f"{operation_name}_operations.jsonl"
        self.conflict_file = self.report_dir / f"{operation_name}_conflicts.jsonl"

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
        self._append_json_line(self.operation_file, payload)
        if status == "conflict":
            self._append_json_line(self.conflict_file, payload)

    def _append_json_line(self, path, payload):
        with path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            file_obj.write("\n")
