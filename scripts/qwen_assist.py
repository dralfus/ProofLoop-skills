"""Bounded, schema-first handoff from Codex Controller to Qwen CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


MAX_ATTEMPTS = 7
MAX_RECON_TURNS = 12
MAX_RECON_TOOL_CALLS = 20
MAX_RECON_WALL_TIME = "10m"
PATCH_SEAL_ELIGIBLE_REASONS = {
    "STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT",
    "COLLECTOR_PROJECTION_FAILED",
}
REQUIRED_CAPABILITY_MARKERS = {
    "non_interactive_prompt": "--prompt",
    "bare_mode": "--bare",
    "json_output": "--output-format",
    "json_schema": "--json-schema",
    "worktree": "--worktree",
    "read_only_mode": "--approval-mode",
    "max_session_turns": "--max-session-turns",
    "max_wall_time": "--max-wall-time",
    "max_tool_calls": "--max-tool-calls",
    "exclude_tools": "--exclude-tools",
}
METRIC_FIELDS = (
    "task_type",
    "outcome",
    "attempts",
    "duration_seconds",
    "tool_calls",
    "stop_reason",
)


def probe_qwen_capabilities(help_text: object) -> dict[str, object]:
    """Accept any Qwen version exposing the bounded bridge capabilities."""
    if not isinstance(help_text, str):
        return {"status": "BLOCKED_CAPABILITY", "missing_capabilities": ["help_text"]}
    missing = [
        capability
        for capability, marker in REQUIRED_CAPABILITY_MARKERS.items()
        if marker not in help_text
    ]
    if "plan" not in help_text and "read_only_mode" not in missing:
        missing.append("read_only_plan")
    return {
        "status": "QWEN_ASSIST_READY" if not missing else "BLOCKED_CAPABILITY",
        "missing_capabilities": missing,
    }


def build_recon_command(
    *, qwen_command: str, prompt: str, schema_path: str, worktree: str
) -> list[str]:
    """Build one read-only Qwen invocation without a model fallback."""
    return [
        qwen_command,
        "--bare",
        "--approval-mode",
        "plan",
        "--output-format",
        "json",
        "--json-schema",
        f"@{schema_path}",
        "--worktree",
        worktree,
        "--max-session-turns",
        str(MAX_RECON_TURNS),
        "--max-wall-time",
        MAX_RECON_WALL_TIME,
        "--max-tool-calls",
        str(MAX_RECON_TOOL_CALLS),
        "--max-subagent-depth",
        "1",
        "--exclude-tools",
        "Agent,edit,notebook_edit,run_shell_command",
        "--disabled-slash-commands",
        "review,loop",
        "--prompt",
        prompt,
    ]


def run_recon(
    *,
    help_text: str,
    qwen_command: str,
    prompt: str,
    schema_path: str,
    worktree: str,
    runner: object | None = None,
) -> dict[str, object]:
    """Run one bounded recon only after the CLI contract has been proven."""
    probe = probe_qwen_capabilities(help_text)
    if probe["status"] != "QWEN_ASSIST_READY":
        return probe
    command = build_recon_command(
        qwen_command=qwen_command,
        prompt=prompt,
        schema_path=schema_path,
        worktree=worktree,
    )
    if runner is None:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        exit_code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    else:
        exit_code, stdout, stderr = runner(command)
    if exit_code != 0:
        terminal_error = f"{stdout}\n{stderr}".lower()
        if exit_code == 53 and "structured_output" in terminal_error and "max session turns" in terminal_error:
            return {"status": "QWEN_UNUSABLE", "reason": "STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT"}
        return {"status": "QWEN_UNUSABLE", "reason": "QWEN_COMMAND_FAILED"}
    report = parse_terminal_json(stdout)
    if report is None:
        return {"status": "QWEN_UNUSABLE", "reason": "INVALID_JSON_OUTPUT"}
    return validate_recon_report(report)


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_recon_report(report: object) -> dict[str, object]:
    """Validate Qwen evidence before it can enter the Controller packet."""
    if not isinstance(report, dict):
        return {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_REPORT"}
    status = report.get("status")
    if status not in {"EVIDENCE_FOUND", "BLOCKED", "QWEN_UNUSABLE"}:
        return {"status": "QWEN_UNUSABLE", "reason": "INVALID_STATUS"}
    if report.get("writes"):
        return {"status": "QWEN_UNUSABLE", "reason": "READ_ONLY_VIOLATION"}
    if status != "EVIDENCE_FOUND":
        return {"status": status, "reason": report.get("stop_reason") or "NO_EVIDENCE"}
    if not _non_empty_string(report.get("baseline")):
        return {"status": "QWEN_UNUSABLE", "reason": "MISSING_BASELINE"}
    facts = report.get("facts")
    if not isinstance(facts, list) or len(facts) < 3:
        return {"status": "QWEN_UNUSABLE", "reason": "INSUFFICIENT_FACTS"}
    for fact in facts:
        if (
            not isinstance(fact, dict)
            or not _non_empty_string(fact.get("file"))
            or not isinstance(fact.get("line"), int)
            or fact["line"] < 1
            or not _non_empty_string(fact.get("fact"))
        ):
            return {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_FACT"}
    required_fields = ("state_owner", "callback_boundary", "acceptance_risk")
    if any(not _non_empty_string(report.get(field)) for field in required_fields):
        return {"status": "QWEN_UNUSABLE", "reason": "INCOMPLETE_RECON"}
    return {"status": "EVIDENCE_FOUND"}


def _normalize_root_cause(value: object) -> str:
    if not _non_empty_string(value):
        return ""
    return re.sub(r"[-_\s]+", "-", value.strip().lower())


def parse_terminal_json(stdout: str) -> object:
    """Accept only one terminal JSON object; transcripts are not evidence."""
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    if not isinstance(parsed, list) or not parsed:
        return None
    terminal_event = parsed[-1]
    if not isinstance(terminal_event, dict) or terminal_event.get("type") != "result":
        return None
    structured_result = terminal_event.get("structured_result")

    return structured_result if isinstance(structured_result, dict) else None

def next_qwen_attempt(
    ledger: object, candidate: object
) -> dict[str, object]:
    """Decide whether a new Qwen call adds evidence instead of repeating a loop."""
    if not isinstance(ledger, list) or not isinstance(candidate, dict):
        return {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_LEDGER"}
    if len(ledger) >= MAX_ATTEMPTS:
        return {"status": "QWEN_UNUSABLE", "reason": "QWEN_BUDGET_EXHAUSTED"}
    root_cause = _normalize_root_cause(candidate.get("root_cause"))
    required_change_fields = ("scope", "criterion", "red_command", "hypothesis")
    if not root_cause or not _non_empty_string(candidate.get("hypothesis")):
        return {"status": "QWEN_UNUSABLE", "reason": "INCOMPLETE_ATTEMPT"}
    previous = ledger[-1] if ledger else None
    if isinstance(previous, dict):
        changed_packet = any(
            _non_empty_string(candidate.get(field))
            and candidate.get(field) != previous.get(field)
            for field in required_change_fields
        )
        if not changed_packet:
            return {"status": "QWEN_UNUSABLE", "reason": "RETRY_WITHOUT_CHANGED_PACKET"}
        previous_root = _normalize_root_cause(previous.get("root_cause"))
        if previous_root == root_cause and not candidate.get("progress"):
            return {"status": "QWEN_UNUSABLE", "reason": "REPEATED_ROOT_CAUSE"}
        if previous.get("progress") is False and candidate.get("progress") is False:
            return {"status": "QWEN_UNUSABLE", "reason": "TWO_NON_PROGRESS_ATTEMPTS"}
    return {"status": "QWEN_ATTEMPT_ALLOWED"}


def validate_patch_candidate(candidate: object) -> dict[str, object]:
    """Keep a Qwen patch a reviewable candidate, never an integration action."""
    if not isinstance(candidate, dict) or candidate.get("successful_recon") is not True:
        return {"status": "QWEN_UNUSABLE", "reason": "RECON_NOT_CONFIRMED"}
    files = candidate.get("files")
    if not isinstance(files, list) or not files or len(files) > 2 or not all(
        _non_empty_string(path) for path in files
    ):
        return {"status": "QWEN_UNUSABLE", "reason": "PATCH_SCOPE_EXCEEDED"}
    if (
        not isinstance(candidate.get("changed_lines"), int)
        or isinstance(candidate["changed_lines"], bool)
        or candidate["changed_lines"] < 1
        or candidate["changed_lines"] > 200
    ):
        return {"status": "QWEN_UNUSABLE", "reason": "PATCH_SCOPE_EXCEEDED"}
    tests = candidate.get("targeted_tests")
    if not isinstance(tests, list) or len(tests) != 1 or not _non_empty_string(tests[0]):
        return {"status": "QWEN_UNUSABLE", "reason": "TARGETED_TEST_REQUIRED"}
    if candidate.get("git_operations") != [] or candidate.get("full_suite") is not False:
        return {"status": "QWEN_UNUSABLE", "reason": "GIT_INTEGRATION_FORBIDDEN"}
    return {"status": "CANDIDATE_PATCH"}


def validate_patch_seal_receipt(
    receipt: object, expected_baseline: str | None = None
) -> dict[str, object]:
    """Accept only an independently observed, bounded unsealed candidate."""
    required_fields = {
        "baseline", "files", "changed_lines", "targeted_tests", "targeted_exit_code",
        "git_operations", "full_suite", "yolo_reason",
    }
    if not isinstance(receipt, dict) or set(receipt) != required_fields:
        return {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_PATCH_SEAL_RECEIPT"}
    if not _non_empty_string(receipt.get("baseline")):
        return {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_PATCH_SEAL_RECEIPT"}
    if expected_baseline is not None and receipt["baseline"] != expected_baseline:
        return {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_BASELINE_MISMATCH"}
    targeted_exit_code = receipt.get("targeted_exit_code")
    if not isinstance(targeted_exit_code, int) or isinstance(targeted_exit_code, bool):
        return {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_PATCH_SEAL_RECEIPT"}
    if targeted_exit_code != 0:
        return {"status": "QWEN_UNUSABLE", "reason": "TARGETED_TEST_NOT_GREEN"}
    if receipt.get("yolo_reason") not in PATCH_SEAL_ELIGIBLE_REASONS:
        return {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_NOT_ELIGIBLE"}
    candidate = {
        "successful_recon": True,
        "files": receipt["files"],
        "changed_lines": receipt["changed_lines"],
        "targeted_tests": receipt["targeted_tests"],
        "git_operations": receipt["git_operations"],
        "full_suite": receipt["full_suite"],
    }
    candidate_validation = validate_patch_candidate(candidate)
    if candidate_validation["status"] != "CANDIDATE_PATCH":
        return candidate_validation
    return {"status": "PATCH_SEAL_RECEIPT_READY"}


def reserve_patch_seal(ticket_id: object, receipt: object, seal_store: Path) -> dict[str, object]:
    """Atomically reserve the single permitted seal call for one ticket."""
    if not _non_empty_string(ticket_id) or not re.fullmatch(r"[A-Za-z0-9._-]+", ticket_id):
        return {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_TICKET_ID"}
    receipt_validation = validate_patch_seal_receipt(receipt)
    if receipt_validation["status"] != "PATCH_SEAL_RECEIPT_READY":
        return receipt_validation
    seal_store.mkdir(parents=True, exist_ok=True)
    reservation = seal_store / f"{ticket_id}.patch-seal-used"
    try:
        with reservation.open("x", encoding="utf-8") as marker:
            marker.write("reserved\n")
    except FileExistsError:
        return {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_ALREADY_USED"}
    return {"status": "PATCH_SEAL_RESERVED"}

def validate_patch_seal_manifest(receipt: object, manifest: object) -> dict[str, object]:
    """Seal only a Qwen manifest that exactly matches observed candidate facts."""
    receipt_validation = validate_patch_seal_receipt(receipt)
    if receipt_validation["status"] != "PATCH_SEAL_RECEIPT_READY":
        return receipt_validation
    manifest_validation = validate_patch_candidate(manifest)
    if manifest_validation["status"] != "CANDIDATE_PATCH":
        return manifest_validation
    assert isinstance(receipt, dict)
    assert isinstance(manifest, dict)
    observed_fields = ("files", "changed_lines", "targeted_tests", "git_operations", "full_suite")
    if any(manifest[field] != receipt[field] for field in observed_fields):
        return {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_MANIFEST_MISMATCH"}
    return {"status": "SEALED_CANDIDATE"}


def anonymize_metric(metric: object) -> dict[str, object]:
    """Keep only approved aggregate fields in the cross-project local store."""
    if not isinstance(metric, dict):
        raise ValueError("metric must be an object")
    missing = [field for field in METRIC_FIELDS if field not in metric]
    if missing:
        raise ValueError(f"metric is missing fields: {', '.join(missing)}")
    return {field: metric[field] for field in METRIC_FIELDS}


def append_metric(store_path: Path, metric: dict[str, object]) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with store_path.open("a", encoding="utf-8") as store:
        store.write(json.dumps(metric, ensure_ascii=False, sort_keys=True) + "\n")


def default_metrics_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is required for the Qwen metrics store")
    return Path(local_app_data) / "ProofLoop Skills" / "qwen-metrics.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-help", type=Path)
    parser.add_argument("--validate-recon", type=json.loads)
    parser.add_argument("--ledger", type=json.loads)
    parser.add_argument("--candidate", type=json.loads)
    parser.add_argument("--validate-patch", type=json.loads)
    parser.add_argument("--validate-patch-seal-receipt", type=json.loads)
    parser.add_argument("--validate-patch-seal-manifest", type=json.loads)
    parser.add_argument("--patch-seal-receipt", type=json.loads)
    parser.add_argument("--expected-baseline")
    parser.add_argument("--reserve-patch-seal", action="store_true")
    parser.add_argument("--ticket-id")
    parser.add_argument("--seal-store", type=Path)
    parser.add_argument("--append-metric", type=json.loads)
    parser.add_argument("--metrics-path", type=Path)
    parser.add_argument("--build-recon-command", action="store_true")
    parser.add_argument("--qwen-command", default="qwen")
    parser.add_argument("--prompt")
    parser.add_argument("--schema-path")
    parser.add_argument("--worktree")
    args = parser.parse_args()
    if args.build_recon_command:
        if not all((args.prompt, args.schema_path, args.worktree)):
            parser.error("--build-recon-command requires --prompt, --schema-path and --worktree")
        print(
            json.dumps(
                build_recon_command(
                    qwen_command=args.qwen_command,
                    prompt=args.prompt,
                    schema_path=args.schema_path,
                    worktree=args.worktree,
                )
            )
        )
    elif args.probe_help is not None:
        print(json.dumps(probe_qwen_capabilities(args.probe_help.read_text(encoding="utf-8")), sort_keys=True))
    elif args.validate_recon is not None:
        print(json.dumps(validate_recon_report(args.validate_recon), sort_keys=True))
    elif args.ledger is not None and args.candidate is not None:
        print(json.dumps(next_qwen_attempt(args.ledger, args.candidate), sort_keys=True))
    elif args.validate_patch is not None:
        print(json.dumps(validate_patch_candidate(args.validate_patch), sort_keys=True))
    elif args.reserve_patch_seal:
        if args.patch_seal_receipt is None or args.ticket_id is None or args.seal_store is None:
            parser.error("--reserve-patch-seal requires --patch-seal-receipt, --ticket-id and --seal-store")
        print(json.dumps(reserve_patch_seal(args.ticket_id, args.patch_seal_receipt, args.seal_store), sort_keys=True))
    elif args.validate_patch_seal_manifest is not None and args.patch_seal_receipt is not None:
        print(json.dumps(validate_patch_seal_manifest(args.patch_seal_receipt, args.validate_patch_seal_manifest), sort_keys=True))
    elif args.validate_patch_seal_receipt is not None:
        print(json.dumps(validate_patch_seal_receipt(args.validate_patch_seal_receipt, args.expected_baseline), sort_keys=True))
    elif args.append_metric is not None and args.metrics_path is not None:
        metric = anonymize_metric(args.append_metric)
        append_metric(args.metrics_path, metric)
        print(json.dumps(metric, sort_keys=True))
    else:
        parser.error("provide one supported action and required arguments")


if __name__ == "__main__":
    main()
