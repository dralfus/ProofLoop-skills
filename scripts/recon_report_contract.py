"""Executable, raw-free contract for Qwen read-only recon reports.

The JSON Schema describes the wire shape.  This module owns the semantic
checks shared by the Python and PowerShell adapters so that both paths fail
closed with the same reason.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_TOP_LEVEL_FIELDS = {
    "status",
    "baseline",
    "facts",
    "state_owner",
    "callback_boundary",
    "acceptance_risk",
    "stop_reason",
    "writes",
}
_STATUSES = {"EVIDENCE_FOUND", "BLOCKED", "QWEN_UNUSABLE"}
_FACT_FIELDS = {"file", "line", "fact"}


def _failure(reason: str) -> dict[str, object]:
    return {"valid": False, "reason": reason}


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_line_number(value: object) -> bool:
    # bool is an int subclass, but is not a JSON Schema integer line number.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def validate_recon_report(
    report: object, *, expected_baseline: str | None = None
) -> dict[str, object]:
    """Return a small raw-free verdict for one decoded recon report."""
    if not isinstance(report, dict):
        return _failure("MALFORMED_REPORT")
    if set(report) - _TOP_LEVEL_FIELDS:
        return _failure("MALFORMED_REPORT")

    status = report.get("status")
    if status not in _STATUSES:
        return _failure("INVALID_STATUS")

    if "writes" not in report or not isinstance(report["writes"], list):
        return _failure("MALFORMED_REPORT")
    if any(not isinstance(write, str) for write in report["writes"]):
        return _failure("MALFORMED_REPORT")
    if report["writes"]:
        return _failure("READ_ONLY_VIOLATION")

    if "stop_reason" not in report:
        return _failure("MALFORMED_REPORT")
    stop_reason = report["stop_reason"]
    if stop_reason is not None and not isinstance(stop_reason, str):
        return _failure("MALFORMED_REPORT")
    if status == "EVIDENCE_FOUND" and stop_reason is not None:
        return _failure("MALFORMED_REPORT")
    if status != "EVIDENCE_FOUND":
        return _failure("RECON_REPORT_BLOCKED")

    if not _non_empty_string(report.get("baseline")):
        return _failure("MISSING_BASELINE")
    if expected_baseline is not None and report["baseline"] != expected_baseline:
        return _failure("BASELINE_MISMATCH")

    facts = report.get("facts")
    if not isinstance(facts, list) or len(facts) < 3:
        return _failure("INSUFFICIENT_FACTS")
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != _FACT_FIELDS:
            return _failure("MALFORMED_FACT")
        if (
            not _non_empty_string(fact.get("file"))
            or not _is_line_number(fact.get("line"))
            or not _non_empty_string(fact.get("fact"))
        ):
            return _failure("MALFORMED_FACT")

    for field in ("state_owner", "callback_boundary", "acceptance_risk"):
        if not _non_empty_string(report.get(field)):
            return _failure("INCOMPLETE_RECON")

    return {"valid": True, "report": report}


def _parse_input(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Qwen recon report")
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--expected-baseline")
    args = parser.parse_args(argv)
    report = _parse_input(args.input_file)
    result = validate_recon_report(report, expected_baseline=args.expected_baseline)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
