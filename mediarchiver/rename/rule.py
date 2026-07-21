import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.plan import RenamePlanItem

PLAN_ITEM_STATUSES = {"ready", "skipped", "invalid", "conflict"}
MEDIA_REQUIRED_FIELDS = (
    "date",
    "date_source",
    "device_unit",
    "device_unit_source",
    "original_id",
    "original_id_source",
)
SIDECAR_REQUIRED_FIELDS = ("sidecar_rule", "sidecar_type")
DATE_PATTERN = re.compile(r"^\d{8}-\d{6}$")
ORIGINAL_ID_PATTERN = re.compile(r"^\d{4}$")


@dataclass(frozen=True)
class RuleFileSet:
    source_dir: str
    media_paths: list[str]
    sidecar_paths: list[str]


@dataclass(frozen=True)
class RuleMatch:
    matched: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuiltName:
    file_name: str
    details: dict[str, Any]


class RuleOutputContractError(ValueError):
    pass


class RenameRule(Protocol):
    id: str
    label: str
    description: str
    priority: int
    required_tools: tuple[str, ...]

    def collect_files(self, source_dir: str, include_formatted: bool = False) -> RuleFileSet:
        ...

    def build_plan_items(
        self,
        source_dir: str,
        contexts: dict[str, FileMetadataContext],
        file_set: RuleFileSet,
    ) -> list[RenamePlanItem]:
        ...


def normalize_rule_plan_item(item: RenamePlanItem, rule: RenameRule) -> RenamePlanItem:
    details = normalize_rule_details(item.details, rule)
    validate_rule_plan_item(item, details, rule)
    return RenamePlanItem(
        source=item.source,
        destination=item.destination,
        action=item.action,
        status=item.status,
        reason=item.reason,
        details=details,
    )


def normalize_rule_details(details, rule: RenameRule):
    normalized = dict(details or {})
    normalized["rule"] = rule.id
    normalized["rule_brand"] = rule_brand(rule)
    normalized["rule_label"] = rule.label
    normalized["rule_priority"] = rule_priority(rule)
    if "rule_match" in normalized:
        normalized["rule_match"] = list(normalized["rule_match"] or [])

    required = normalized.get("required")
    if isinstance(required, dict):
        normalized["required"] = dict(required)
    return normalized


def rule_brand(rule: RenameRule):
    return rule.id.split(":", 1)[0]


def rule_priority(rule: RenameRule):
    return int(getattr(rule, "priority", 0))


def validate_rule_plan_item(
    item: RenamePlanItem,
    details: dict[str, Any],
    rule: RenameRule,
) -> None:
    if item.action != "rename":
        raise_rule_contract_error(rule, item, "action must be 'rename'")
    if item.status not in PLAN_ITEM_STATUSES:
        raise_rule_contract_error(rule, item, f"unsupported status: {item.status}")
    if item.status == "ready" and item.destination is None:
        raise_rule_contract_error(rule, item, "ready item must have destination")
    if item.status != "ready" and item.reason is None:
        raise_rule_contract_error(rule, item, "non-ready item must have reason")
    if item.destination is not None:
        validate_destination_file_name(item, rule)

    if "rule_match" in details and not all(
        isinstance(reason, str) for reason in details["rule_match"]
    ):
        raise_rule_contract_error(rule, item, "rule_match must be a list of strings")

    has_media_details = "required" in details or "optional" in details
    has_sidecar_details = "sidecar_rule" in details or "sidecar_type" in details
    if has_media_details:
        validate_media_details(item, details, rule)
    if has_sidecar_details:
        validate_sidecar_details(item, details, rule)
    if item.status == "ready" and not (has_media_details or has_sidecar_details):
        raise_rule_contract_error(
            rule,
            item,
            "ready item must include media required/optional details or sidecar details",
        )


def validate_destination_file_name(item: RenamePlanItem, rule: RenameRule) -> None:
    file_name = os.path.basename(item.destination or "")
    if " " in file_name:
        raise_rule_contract_error(rule, item, "destination file name must not contain spaces")



def validate_media_details(
    item: RenamePlanItem,
    details: dict[str, Any],
    rule: RenameRule,
) -> None:
    required = details.get("required")
    optional = details.get("optional")
    if not isinstance(required, dict):
        raise_rule_contract_error(rule, item, "media details.required must be a dict")
    missing_required = [field for field in MEDIA_REQUIRED_FIELDS if not required.get(field)]
    if missing_required:
        raise_rule_contract_error(
            rule,
            item,
            f"media details.required missing: {', '.join(missing_required)}",
        )
    if DATE_PATTERN.fullmatch(str(required["date"])) is None:
        raise_rule_contract_error(
            rule,
            item,
            "media details.required.date must match YYYYMMDD-HHMMSS",
        )
    if ORIGINAL_ID_PATTERN.fullmatch(str(required["original_id"])) is None:
        raise_rule_contract_error(
            rule,
            item,
            "media details.required.original_id must be four digits",
        )
    if required["device_unit_source"] != "rule" and not str(
        required["device_unit_source"]
    ).startswith("metadata:"):
        raise_rule_contract_error(
            rule,
            item,
            "media details.required.device_unit_source must be 'rule' or metadata:<field>",
        )
    if not isinstance(optional, dict):
        raise_rule_contract_error(rule, item, "media details.optional must be a dict")
    missing_optional = optional.get("missing")
    if not isinstance(missing_optional, list):
        raise_rule_contract_error(
            rule,
            item,
            "media details.optional.missing must be a list",
        )


def validate_sidecar_details(
    item: RenamePlanItem,
    details: dict[str, Any],
    rule: RenameRule,
) -> None:
    missing = [field for field in SIDECAR_REQUIRED_FIELDS if not details.get(field)]
    if missing:
        raise_rule_contract_error(
            rule,
            item,
            f"sidecar details missing: {', '.join(missing)}",
        )
    if item.reason not in {"missing_primary_media", "primary_not_ready"} and not details.get(
        "paired_with"
    ):
        raise_rule_contract_error(rule, item, "sidecar details.paired_with is required")


def raise_rule_contract_error(rule, item, message):
    raise RuleOutputContractError(
        f"{rule.id} returned invalid plan item for {item.source}: {message}"
    )
