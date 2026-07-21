from importlib import import_module
from pkgutil import iter_modules

import mediarchiver.rename.rules as rules_package
from mediarchiver.rename.rule import RenameRule


def discover_rules() -> tuple[RenameRule, ...]:
    discovered = []
    package_prefix = rules_package.__name__ + "."
    for module_info in iter_modules(rules_package.__path__, package_prefix):
        if not module_info.ispkg:
            continue
        adapter_module_name = f"{module_info.name}.adapter"
        try:
            adapter_module = import_module(adapter_module_name)
        except ModuleNotFoundError as exc:
            if exc.name == adapter_module_name:
                continue
            raise
        discovered.extend(_rules_from_adapter(adapter_module))
    return tuple(sorted(_validate_rules(discovered), key=lambda rule: rule.id))


def _rules_from_adapter(adapter_module):
    rules = getattr(adapter_module, "RULES", None)
    if rules is not None:
        return tuple(rules)
    rule = getattr(adapter_module, "RULE", None)
    return () if rule is None else (rule,)


def _validate_rules(rules):
    rules_by_id = {}
    for rule in rules:
        rule_id = getattr(rule, "id", None)
        if not rule_id:
            raise ValueError(f"rename rule missing id: {rule!r}")
        if rule_id in rules_by_id:
            raise ValueError(f"duplicate rename rule id: {rule_id}")
        rules_by_id[rule_id] = rule
    return tuple(rules_by_id.values())


RULES: tuple[RenameRule, ...] = discover_rules()
RULES_BY_ID = {rule.id: rule for rule in RULES}


def get_rule(rule_id: str) -> RenameRule:
    try:
        return RULES_BY_ID[rule_id]
    except KeyError as exc:
        supported = ", ".join(sorted(RULES_BY_ID))
        raise ValueError(
            f"unsupported rename rule: {rule_id}. supported: {supported}"
        ) from exc


def list_rules() -> tuple[RenameRule, ...]:
    return RULES
