"""Pure fail-closed policy seam for ProofLoop-owned Qwen launches.

The adapters perform I/O and process control.  This module receives only
already-projected settings, worktree facts, CLI capabilities and receipt facts;
it never starts Qwen and returns no raw paths, prompts, secrets or output.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
from pathlib import Path


PROTOCOL_LIMITS = {
    "max_session_turns": 20,
    "max_tool_calls": 20,
    "max_wall_time": "30m",
    "max_subagent_depth": 1,
}
RECON_LIMITS = {
    "max_session_turns": 3,
    "max_tool_calls": 6,
    "max_wall_time": "5m",
    "max_subagent_depth": 1,
}
CAPABILITY_MARKERS = {
    "protocol": frozenset(
        {
            "--prompt",
            "--max-session-turns",
            "--max-tool-calls",
            "--max-wall-time",
            "--max-subagent-depth",
            "--json-file",
        }
    ),
    "recon": frozenset(
        {
            "--prompt",
            "--bare",
            "--approval-mode",
            "--output-format",
            "--json-schema",
            "--max-session-turns",
            "--max-tool-calls",
            "--max-wall-time",
            "--max-subagent-depth",
            "--exclude-tools",
            "--disabled-slash-commands",
            "plan",
        }
    ),
}
_FORBIDDEN_FIELDS = frozenset(
    {"prompt", "secret", "path", "raw_command_output", "exception_text", "customer_data"}
)
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_FIXED_POINT = re.compile(r"^[0-9a-f]{40,64}$")
_ALLOWED_INPUT_FIELDS = {
    "operation",
    "mode",
    "now_utc",
    "max_receipt_age_seconds",
    "settings",
    "worktree",
    "capabilities",
    "receipt",
    "terminal_stop",
}


def blocked(reason: str) -> dict[str, object]:
    return {
        "status": "BLOCKED_CAPABILITY",
        "reason": reason,
        "role_dispatch": False,
        "subagent_dispatch": False,
        "acceptance": False,
    }


def terminal_stop(reason: str) -> dict[str, object]:
    return {
        "status": "QWEN_RUNTIME_GUARD_STOP",
        "reason": reason,
        "role_dispatch": False,
        "subagent_dispatch": False,
        "acceptance": False,
    }


def _contains_forbidden_field(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            key in _FORBIDDEN_FIELDS or _contains_forbidden_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _valid_identity(value: object) -> bool:
    return isinstance(value, str) and _HEX32.fullmatch(value) is not None


def _valid_settings(settings: object) -> str | None:
    if not isinstance(settings, dict):
        return "MALFORMED_GUARD_INPUT"
    skip_loop = settings.get("skipLoopDetection")
    max_tools = settings.get("maxToolCallsPerTurn")
    max_depth = settings.get("maxSubagentDepth")
    if skip_loop is not False:
        return "LOOP_DETECTION_DISABLED"
    if isinstance(max_tools, bool) or not isinstance(max_tools, int) or not 1 <= max_tools <= 20:
        return "MAX_TOOL_CALLS_INVALID"
    if isinstance(max_depth, bool) or not isinstance(max_depth, int):
        return "MAX_SUBAGENT_DEPTH_INVALID"
    if max_depth > 1:
        return "MAX_SUBAGENT_DEPTH_EXCEEDED"
    if max_depth != 1:
        return "MAX_SUBAGENT_DEPTH_INVALID"
    return None


def _valid_capabilities(mode: str, capabilities: object) -> str | None:
    if not isinstance(capabilities, dict) or not isinstance(capabilities.get("markers"), list):
        return "MALFORMED_GUARD_INPUT"
    markers = capabilities["markers"]
    if any(not isinstance(marker, str) for marker in markers):
        return "MALFORMED_GUARD_INPUT"
    if not CAPABILITY_MARKERS[mode].issubset(markers):
        return "QWEN_CLI_CAPABILITY_MISSING"
    return None


def _valid_worktree(mode: str, worktree: object) -> str | None:
    if not isinstance(worktree, dict) or worktree.get("available") is not True:
        return "WORKTREE_UNAVAILABLE"
    if mode == "recon":
        if worktree.get("clean") is not True:
            return "WORKTREE_NOT_CLEAN"
        if not isinstance(worktree.get("fixed_point"), str) or _FIXED_POINT.fullmatch(worktree["fixed_point"]) is None:
            return "FIXED_POINT_UNAVAILABLE"
    return None


def _valid_receipt(
    mode: str,
    receipt: object,
    now: datetime,
    max_age_seconds: int,
    worktree: dict[str, object],
) -> str | None:
    if not isinstance(receipt, dict):
        return "RECEIPT_MISSING" if receipt is None else "RECEIPT_MISMATCHED"
    expected_type = "QWEN_SESSION_GUARD" if mode == "protocol" else "QWEN_RECON_GUARD"
    expected_limits = PROTOCOL_LIMITS if mode == "protocol" else RECON_LIMITS
    if (
        receipt.get("receipt_type") != expected_type
        or receipt.get("receipt_version") != 1
        or receipt.get("mode") != mode
        or not _valid_identity(receipt.get("launch_id"))
        or receipt.get("limits") != expected_limits
        or receipt.get("loop_detection") is not True
        or receipt.get("extension_available") is not True
    ):
        return "RECEIPT_MISMATCHED"
    issued_at = _parse_utc(receipt.get("issued_at_utc"))
    if issued_at is None:
        return "RECEIPT_MISMATCHED"
    age_seconds = (now - issued_at).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_seconds:
        return "RECEIPT_STALE"
    if mode == "recon":
        if (
            isinstance(receipt.get("fixed_point"), str)
            and isinstance(worktree.get("fixed_point"), str)
            and receipt["fixed_point"] != worktree["fixed_point"]
        ):
            return "FIXED_POINT_MISMATCH"
        if (
            not _valid_identity(receipt.get("session_id"))
            or not _valid_identity(receipt.get("ledger_id"))
            or not _valid_identity(receipt.get("fresh_evidence_id"))
            or receipt.get("read_only") is not True
            or receipt.get("role_dispatch") is not False
            or receipt.get("subagent_dispatch") is not False
            or receipt.get("acceptance") is not False
            or receipt.get("structured_output") is not True
            or receipt.get("worktree_clean") is not True
            or not isinstance(receipt.get("fixed_point"), str)
            or _FIXED_POINT.fullmatch(receipt["fixed_point"]) is None
            or receipt["fixed_point"] != worktree.get("fixed_point")
        ):
            return "RECEIPT_MISMATCHED"
    return None


def evaluate_guard_policy(payload: object) -> dict[str, object]:
    """Evaluate pre-dispatch facts without invoking any process."""
    if not isinstance(payload, dict):
        return blocked("MALFORMED_GUARD_INPUT")
    if _contains_forbidden_field(payload):
        return blocked("RAW_FIELD_FORBIDDEN")
    if set(payload) - _ALLOWED_INPUT_FIELDS:
        return blocked("MALFORMED_GUARD_INPUT")
    if payload.get("operation") != "guard_preflight":
        return blocked("MALFORMED_GUARD_INPUT")
    mode = payload.get("mode")
    if mode not in ("protocol", "recon"):
        return blocked("MALFORMED_GUARD_INPUT")
    terminal = payload.get("terminal_stop")
    if not isinstance(terminal, bool):
        return blocked("MALFORMED_GUARD_INPUT")
    now = _parse_utc(payload.get("now_utc"))
    max_age = payload.get("max_receipt_age_seconds", 300)
    if now is None or isinstance(max_age, bool) or not isinstance(max_age, int) or not 0 < max_age <= 3600:
        return blocked("MALFORMED_GUARD_INPUT")
    settings_reason = _valid_settings(payload.get("settings"))
    if settings_reason is not None:
        return blocked(settings_reason)
    capability_reason = _valid_capabilities(mode, payload.get("capabilities"))
    if capability_reason is not None:
        return blocked(capability_reason)
    worktree_reason = _valid_worktree(mode, payload.get("worktree"))
    if worktree_reason is not None:
        return blocked(worktree_reason)
    worktree = payload["worktree"]
    receipt_reason = _valid_receipt(mode, payload.get("receipt"), now, max_age, worktree)
    if receipt_reason is not None:
        return blocked(receipt_reason)
    if terminal:
        return terminal_stop("TERMINAL_STOP_ACTIVE")

    limits = dict(PROTOCOL_LIMITS if mode == "protocol" else RECON_LIMITS)
    recon = mode == "recon"
    return {
        "status": "QWEN_GUARD_READY",
        "mode": mode,
        "limits": limits,
        "loop_detection": True,
        "read_only": recon,
        "implementation": not recon,
        "role_dispatch": not recon,
        "subagent_dispatch": not recon,
        "acceptance": False,
    }


def _load_input(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Qwen pre-dispatch guard policy")
    parser.add_argument("--input-file", required=True, type=Path)
    args = parser.parse_args(argv)
    result = evaluate_guard_policy(_load_input(args.input_file))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
