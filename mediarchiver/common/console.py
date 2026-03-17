def _print_lines(lines):
    for line in lines:
        print(line)


def confirm_proceed(prompt):
    """Prompt for y/n confirmation. Returns True if user confirms, False otherwise."""
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def print_run_header(operation, values):
    lines = [f"[{operation}] start"]
    for key, value in values.items():
        lines.append(f"- {key}: {value}")
    _print_lines(lines)


def print_run_summary(operation, summary):
    lines = [
        f"[{operation}] done",
        f"- total: {summary.get('total', 0)}",
        f"- success: {summary.get('success', 0)}",
        f"- preview: {summary.get('preview', 0)}",
        f"- skipped: {summary.get('skipped', 0)}",
        f"- conflict: {summary.get('conflict', 0)}",
    ]
    reasons = summary.get("reasons", {})
    if reasons:
        top_reasons = ", ".join(
            f"{reason}={count}"
            for reason, count in sorted(
                reasons.items(), key=lambda item: (-item[1], item[0])
            )[:5]
        )
        lines.append(f"- reasons: {top_reasons}")
    _print_lines(lines)


def print_plan_summary(operation, summary):
    lines = [
        f"[{operation}] plan",
        f"- total: {summary.get('total', 0)}",
        f"- ready: {summary.get('ready', 0)}",
        f"- skipped: {summary.get('skipped', 0)}",
        f"- conflict: {summary.get('conflict', 0)}",
        f"- invalid: {summary.get('invalid', 0)}",
    ]
    _print_lines(lines)
