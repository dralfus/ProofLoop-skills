"""Host verification and raw-free projection for native Qwen continuation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_plugin import (  # noqa: E402
    _QWEN_TERMINAL_RECEIPT_FIELDS,
    _runtime_terminal_evidence_reason,
    qwen_runtime_guard_decision,
)
from qwen_terminal_projection import inspect_output  # noqa: E402
from qwen_terminal_evidence import project_terminal_receipt  # noqa: E402


MAX_EVENT_BYTES = 16 * 1024 * 1024
MAX_EVENT_LINE_BYTES = 1024 * 1024
RAW_FREE_BLOCK = {"status": "BLOCKED_CAPABILITY", "reason": "QWEN_RUNTIME_EVIDENCE_UNSUPPORTED", "role_dispatch": False}
_LEDGER_EVENT_FIELDS = frozenset({
    "sequence", "kind", "evidence_id", "task_fingerprint", "scope_fingerprint",
    "baseline_commit", "diff_fingerprint", "next_closure_fingerprint",
    "test_receipt_id", "review_receipt_id", "prev_hash", "event_hash",
})
_RECEIPT_FIELDS = frozenset({
    "receipt_id", "kind", "status", "evidence_id", "task_fingerprint",
    "scope_fingerprint", "baseline_commit", "diff_fingerprint", "issued_at_utc",
})


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_hash(value: object, length: int = 64) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _safe_relative_file(root: Path, name: object) -> Path | None:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        return None
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise ValueError("host evidence unavailable")
    return result.stdout


def _diff_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(b"tracked-diff\0")
    digest.update(_git(root, "diff", "--binary", "HEAD", "--"))
    names = _git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for name in names:
        if not name:
            continue
        relative = os.fsdecode(name)
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as error:
            raise ValueError("host evidence unavailable") from error
        if path.is_symlink():
            content = os.fsencode(os.readlink(path))
        elif path.is_file():
            content = path.read_bytes()
        else:
            raise ValueError("host evidence unavailable")
        digest.update(b"untracked\0")
        digest.update(name)
        digest.update(b"\0")
        digest.update(content)
    return digest.hexdigest()


def collect_host_facts(
    repo_root: str | Path, *, ticket: str, task_source: str, scope_source: str
) -> dict[str, str]:
    """Recompute task, scope, baseline and diff identities from local host state."""
    root = Path(repo_root).resolve()
    if not root.is_dir() or re.fullmatch(r"[A-Za-z0-9._/-]+", ticket) is None:
        raise ValueError("host evidence unavailable")
    task_path = _safe_relative_file(root, task_source)
    scope_path = _safe_relative_file(root, scope_source)
    if task_path is None or scope_path is None:
        raise ValueError("host evidence unavailable")
    git_root = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    if git_root != root:
        raise ValueError("host evidence unavailable")
    head = _git(root, "rev-parse", "HEAD").decode("ascii", errors="strict").strip()
    if not _is_hash(head, 40):
        raise ValueError("host evidence unavailable")
    task_bytes = task_path.read_bytes()
    scope_bytes = scope_path.read_bytes()
    task_text = task_bytes.decode("utf-8", errors="strict")
    if re.search(rf"(?<![A-Za-z0-9]){re.escape(ticket)}(?![A-Za-z0-9])", task_text) is None:
        raise ValueError("host evidence unavailable")
    return {
        "ticket": ticket,
        "baseline_commit": head,
        "task_fingerprint": _sha256(task_bytes),
        "scope_fingerprint": _sha256(scope_bytes),
        "diff_fingerprint": _diff_fingerprint(root),
    }


def _progress_ledger_valid(ledger: object) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(ledger, dict) or set(ledger) != {"schema", "ledger_id", "events", "head_hash"}:
        return None, "CONTROLLER_PROGRESS_LEDGER_INVALID"
    if ledger.get("schema") != "proofloop.progress-ledger.v1" or not _is_hash(ledger.get("ledger_id"), 32):
        return None, "CONTROLLER_PROGRESS_LEDGER_INVALID"
    events = ledger.get("events")
    if not isinstance(events, list) or not events:
        return None, "CONTROLLER_PROGRESS_LEDGER_INVALID"
    previous_hash = "GENESIS"
    latest: dict[str, Any] | None = None
    evidence_ids: set[str] = set()
    receipt_ids: set[str] = set()
    for sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict) or set(event) != _LEDGER_EVENT_FIELDS:
            return None, "CONTROLLER_PROGRESS_LEDGER_INVALID"
        if (
            event.get("sequence") != sequence
            or event.get("kind") not in {"LOCAL_GREEN", "REVIEW_CONTINUE"}
            or event.get("prev_hash") != previous_hash
            or not _is_hash(event.get("evidence_id"), 32)
            or not _is_hash(event.get("task_fingerprint"))
            or not _is_hash(event.get("scope_fingerprint"))
            or not _is_hash(event.get("baseline_commit"), 40)
            or not _is_hash(event.get("diff_fingerprint"))
            or not _is_hash(event.get("next_closure_fingerprint"))
            or (event.get("test_receipt_id") is not None and not _is_hash(event.get("test_receipt_id"), 32))
            or (event.get("review_receipt_id") is not None and not _is_hash(event.get("review_receipt_id"), 32))
            or event.get("evidence_id") in evidence_ids
            or (event.get("kind") == "LOCAL_GREEN" and (
                not _is_hash(event.get("test_receipt_id"), 32) or event.get("review_receipt_id") is not None
            ))
            or (event.get("kind") == "REVIEW_CONTINUE" and (
                event.get("test_receipt_id") is not None or not _is_hash(event.get("review_receipt_id"), 32)
            ))
            or any(identity in receipt_ids for identity in (event.get("test_receipt_id"), event.get("review_receipt_id")) if identity is not None)
        ):
            return None, "CONTROLLER_PROGRESS_LEDGER_INVALID"
        expected_hash = _sha256(_canonical({key: value for key, value in event.items() if key != "event_hash"}))
        if event.get("event_hash") != expected_hash:
            return None, "CONTROLLER_PROGRESS_LEDGER_INVALID"
        previous_hash = expected_hash
        evidence_ids.add(str(event["evidence_id"]))
        receipt_ids.update(str(identity) for identity in (event.get("test_receipt_id"), event.get("review_receipt_id")) if identity is not None)
        latest = event
    if ledger.get("head_hash") != previous_hash:
        return None, "CONTROLLER_PROGRESS_LEDGER_INVALID"
    return latest, None


def _receipt_matches(receipt: object, expected_id: object, kind: str, status: str, latest: dict[str, Any]) -> bool:
    if not isinstance(receipt, dict):
        return False
    required = set(_RECEIPT_FIELDS)
    if kind == "review":
        required |= {"reviewer_id_hash", "fresh_named", "read_only", "write"}
    if set(receipt) != required:
        return False
    if (
        receipt.get("receipt_id") != expected_id
        or not _is_hash(receipt.get("receipt_id"), 32)
        or receipt.get("kind") != kind
        or receipt.get("status") != status
        or receipt.get("evidence_id") != latest.get("evidence_id")
        or any(receipt.get(field) != latest.get(field) for field in (
            "task_fingerprint", "scope_fingerprint", "baseline_commit", "diff_fingerprint"
        ))
    ):
        return False
    issued_at = receipt.get("issued_at_utc")
    try:
        timestamp = datetime.fromisoformat(str(issued_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
    if timestamp.tzinfo is None or age < 0 or age > 300:
        return False
    if kind == "review" and (
        not _is_hash(receipt.get("reviewer_id_hash"))
        or receipt.get("fresh_named") is not True
        or receipt.get("read_only") is not True
        or receipt.get("write") is not False
    ):
        return False
    return True


def prepare_continuation(
    request: object,
    *,
    launch_id: str | None = None,
    fresh_evidence_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Verify current host evidence, then ask Ticket 22 policy for a decision."""
    if not isinstance(request, dict) or set(request) != {
        "operation", "repo_root", "ticket", "task_source", "scope_source",
        "runtime_payload", "progress_ledger", "test_receipt", "review_receipt",
        "continuation_context", "prior_projection",
    } or request.get("operation") != "prepare_continuation":
        return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MALFORMED"}
    try:
        facts = collect_host_facts(
            request["repo_root"], ticket=request["ticket"],
            task_source=request["task_source"], scope_source=request["scope_source"],
        )
    except (OSError, UnicodeError, ValueError, TypeError, subprocess.SubprocessError):
        return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_HOST_EVIDENCE_UNAVAILABLE"}
    latest, ledger_problem = _progress_ledger_valid(request.get("progress_ledger"))
    if ledger_problem or latest is None:
        return {**RAW_FREE_BLOCK, "reason": ledger_problem or "CONTROLLER_PROGRESS_LEDGER_INVALID"}
    runtime_payload = request.get("runtime_payload")
    if not isinstance(runtime_payload, dict) or request.get("ticket") != runtime_payload.get("ticket"):
        return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MISMATCH"}
    continuation_context = request.get("continuation_context")
    if (
        not isinstance(continuation_context, str)
        or not continuation_context.strip()
        or len(continuation_context.encode("utf-8")) > 32_768
    ):
        return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MALFORMED"}
    checkpoint = None
    if isinstance(runtime_payload, dict):
        observation = runtime_payload.get("observation")
        if isinstance(observation, dict):
            checkpoint = observation.get("checkpoint")
        runtime_ledger = runtime_payload.get("ledger")
        if checkpoint is None and isinstance(runtime_ledger, list) and len(runtime_ledger) >= 2:
            checkpoint_event = runtime_ledger[-2]
            terminal_event = runtime_ledger[-1]
            if (
                isinstance(checkpoint_event, dict)
                and checkpoint_event.get("event") == "checkpoint"
                and isinstance(terminal_event, dict)
                and terminal_event.get("event") == "terminal"
            ):
                checkpoint_fields = {
                    "checkpoint_id", "prior_launch_id", "task_fingerprint", "scope_fingerprint",
                    "baseline_commit", "diff_fingerprint", "progress_ledger_fingerprint",
                    "progress_sequence", "progress_evidence_id", "progress_kind",
                    "next_closure_fingerprint",
                }
                checkpoint = {field: checkpoint_event.get(field) for field in checkpoint_fields}
    prior_projection = request.get("prior_projection")
    prior_runtime_observation = None
    runtime_ledger = runtime_payload.get("ledger")
    if isinstance(runtime_ledger, list):
        prior_runtime_observation = next(
            (entry for entry in reversed(runtime_ledger) if isinstance(entry, dict) and entry.get("event") == "runtime_observation"),
            None,
        )
    terminal_event = runtime_ledger[-1] if isinstance(runtime_ledger, list) and runtime_ledger else None
    projection_matches = False
    if (
        isinstance(prior_projection, dict)
        and frozenset(prior_projection) == _QWEN_TERMINAL_RECEIPT_FIELDS
        and isinstance(prior_runtime_observation, dict)
        and isinstance(terminal_event, dict)
        and terminal_event.get("event") == "terminal"
    ):
        evidence_reason = _runtime_terminal_evidence_reason(
            prior_projection,
            str(prior_runtime_observation.get("launch_id", "")),
            prior_runtime_observation,
        )
        evidence_hash = _sha256(_canonical(prior_projection))
        projection_matches = (
            evidence_reason is None
            and prior_projection.get("budget_stop") is True
            and prior_projection.get("terminal_source") == "HOST"
            and prior_projection.get("event_coverage") == "COMPLETE"
            and prior_projection.get("loop_status") == "HOST_CLEAR"
            and prior_projection.get("terminal_reason") in {"HOST_WALL_LIMIT", "HOST_TOOL_LIMIT"}
            and prior_runtime_observation.get("terminal_evidence_hash") == evidence_hash
            and prior_runtime_observation.get("session_id") == prior_projection.get("session_id_hash")
            and prior_runtime_observation.get("turns") == prior_projection.get("turns")
            and prior_runtime_observation.get("tool_calls") == prior_projection.get("tool_calls")
            and prior_runtime_observation.get("wall_time_seconds") == prior_projection.get("wall_time_seconds")
            and prior_runtime_observation.get("loop_detected") is False
            and terminal_event.get("status") == "QWEN_RUNTIME_GUARD_STOP"
            and terminal_event.get("reason") == prior_projection.get("terminal_reason")
            and terminal_event.get("launch_id") == prior_projection.get("launch_id")
        )
    if not projection_matches:
        return {**RAW_FREE_BLOCK, "reason": "QWEN_RUNTIME_EVIDENCE_UNSUPPORTED"}
    ledger_fingerprint = _sha256(_canonical(request["progress_ledger"]))
    context_matches = (
        isinstance(checkpoint, dict)
        and checkpoint.get("task_fingerprint") == facts["task_fingerprint"] == latest.get("task_fingerprint")
        and checkpoint.get("scope_fingerprint") == facts["scope_fingerprint"] == latest.get("scope_fingerprint")
        and checkpoint.get("baseline_commit") == facts["baseline_commit"] == latest.get("baseline_commit")
        and checkpoint.get("diff_fingerprint") == facts["diff_fingerprint"] == latest.get("diff_fingerprint")
        and checkpoint.get("progress_ledger_fingerprint") == ledger_fingerprint
        and checkpoint.get("progress_sequence") == latest.get("sequence")
        and checkpoint.get("progress_evidence_id") == latest.get("evidence_id")
        and checkpoint.get("progress_kind") == latest.get("kind")
        and checkpoint.get("next_closure_fingerprint") == latest.get("next_closure_fingerprint")
        and _sha256(continuation_context.encode("utf-8")) == latest.get("next_closure_fingerprint")
        and latest.get("sequence") > 0
    )
    if not context_matches:
        return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MISMATCH"}
    if latest["kind"] == "LOCAL_GREEN":
        if latest.get("review_receipt_id") is not None or not _receipt_matches(
            request.get("test_receipt"), latest.get("test_receipt_id"), "test", "GREEN", latest
        ):
            return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MISMATCH"}
    elif latest["kind"] == "REVIEW_CONTINUE":
        if latest.get("test_receipt_id") is not None or not _receipt_matches(
            request.get("review_receipt"), latest.get("review_receipt_id"), "review", "CONTINUE", latest
        ):
            return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MISMATCH"}
    else:
        return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_PROGRESS_LEDGER_INVALID"}
    if not isinstance(checkpoint, dict) or not _is_hash(checkpoint.get("checkpoint_id")):
        return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MISMATCH"}
    runtime_payload = json.loads(json.dumps(runtime_payload))
    runtime_payload.pop("terminal_evidence", None)
    if launch_id is not None or fresh_evidence_id is not None or session_id is not None:
        if not all(_is_hash(value, 32) for value in (launch_id, fresh_evidence_id, session_id)):
            return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MALFORMED"}
        if not isinstance(runtime_payload.get("receipt"), dict) or not isinstance(runtime_payload.get("observation"), dict):
            return {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MALFORMED"}
        runtime_payload["receipt"]["launch_id"] = launch_id
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        runtime_payload["receipt"]["issued_at_utc"] = now
        runtime_payload["now_utc"] = now
        runtime_payload["observation"]["fresh_evidence_id"] = fresh_evidence_id
        runtime_payload["observation"]["session_id"] = session_id
    decision = qwen_runtime_guard_decision(runtime_payload)
    if decision.get("status") != "QWEN_RUNTIME_GUARD_READY":
        return {
            "status": str(decision.get("status", "BLOCKED_CAPABILITY")),
            "reason": str(decision.get("reason", "QWEN_RUNTIME_GUARD_BLOCKED")),
            "role_dispatch": False,
            **({"ledger": decision["ledger"], "ledger_anchor": decision["ledger_anchor"]}
               if isinstance(decision.get("ledger"), list) and isinstance(decision.get("ledger_anchor"), dict)
               else {}),
        }
    return {
        "status": "QWEN_RUNTIME_GUARD_READY",
        "reason": "CHECKPOINT_VERIFIED",
        "role_dispatch": True,
        "launch_id": decision["launch_id"],
        "session_id": decision["session_id"],
        "ledger": decision["ledger"],
        "ledger_anchor": decision["ledger_anchor"],
        "facts": {key: value for key, value in facts.items() if key != "ticket"},
        "progress_sequence": latest["sequence"],
        "progress_evidence_id": latest["evidence_id"],
        "checkpoint_id": checkpoint["checkpoint_id"],
        "continuation_packet": continuation_context,
    }


def project_qwen_events(event_text: str, *, wall_time_seconds: int) -> dict[str, Any]:
    """Reduce dual-output JSONL to raw-free session metadata; never infer budget stop."""
    if not isinstance(event_text, str) or not isinstance(wall_time_seconds, int) or isinstance(wall_time_seconds, bool) or wall_time_seconds < 0:
        return dict(RAW_FREE_BLOCK)
    encoded = event_text.encode("utf-8", errors="replace")
    if len(encoded) > MAX_EVENT_BYTES:
        return dict(RAW_FREE_BLOCK)
    lines = event_text.splitlines()
    if not lines:
        return dict(RAW_FREE_BLOCK)
    session_id = None
    session_ended = False
    assistant_ids: set[str] = set()
    tool_use_ids: set[str] = set()
    allowed_types = {"system", "assistant", "user", "control_request", "control_response", "stream_event", "result"}
    for line_number, line in enumerate(lines):
        if len(line.encode("utf-8", errors="replace")) > MAX_EVENT_LINE_BYTES:
            return dict(RAW_FREE_BLOCK)
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, UnicodeError):
            return dict(RAW_FREE_BLOCK)
        if not isinstance(event, dict) or event.get("type") not in allowed_types:
            return dict(RAW_FREE_BLOCK)
        if session_ended:
            return dict(RAW_FREE_BLOCK)
        event_type = event["type"]
        if event_type == "system":
            subtype = event.get("subtype")
            if subtype == "session_start":
                if line_number != 0:
                    return dict(RAW_FREE_BLOCK)
                value = event.get("session_id") or (event.get("data", {}).get("session_id") if isinstance(event.get("data"), dict) else None)
                if not isinstance(value, str) or not value or session_id is not None:
                    return dict(RAW_FREE_BLOCK)
                session_id = _sha256(value.encode("utf-8"))
            elif subtype == "session_end":
                if session_id is None:
                    return dict(RAW_FREE_BLOCK)
                session_ended = True
            else:
                return dict(RAW_FREE_BLOCK)
        elif event_type == "assistant":
            message = event.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("id"), str) or not isinstance(message.get("content"), list):
                return dict(RAW_FREE_BLOCK)
            message_id = message["id"]
            if message_id in assistant_ids:
                return dict(RAW_FREE_BLOCK)
            assistant_ids.add(message_id)
            for block in message["content"]:
                if not isinstance(block, dict):
                    return dict(RAW_FREE_BLOCK)
                if block.get("type") == "tool_use":
                    identity = block.get("id")
                    if not isinstance(identity, str) or not identity:
                        return dict(RAW_FREE_BLOCK)
                    tool_use_ids.add(identity)
        elif event_type == "stream_event":
            nested = event.get("event")
            if not isinstance(nested, dict) or nested.get("type") not in {
                "message_start", "content_block_start", "content_block_delta", "content_block_stop", "message_stop"
            }:
                return dict(RAW_FREE_BLOCK)
        elif event_type == "result":
            # Result payloads can include raw transcript text. Inspect only
            # the error envelope and emit its raw-free classification.
            if not isinstance(event.get("is_error"), bool):
                return dict(RAW_FREE_BLOCK)
            if event["is_error"]:
                classification = inspect_output(json.dumps(event, ensure_ascii=True))
                return {
                    **RAW_FREE_BLOCK,
                    "reason": "QWEN_JSON_ERROR_RESULT",
                    "turns": len(assistant_ids),
                    "tool_calls": len(tool_use_ids),
                    "wall_time_seconds": wall_time_seconds,
                    "tool_fingerprint": _sha256(_canonical(sorted(tool_use_ids))),
                    "session_ended": False,
                    "terminal_reason": "QWEN_JSON_ERROR_RESULT",
                    "budget_stop": False,
                    "loop_status": "UNOBSERVED",
                    **({"session_id": session_id} if session_id is not None else {}),
                    "diagnostic": {
                        "terminal_result": True,
                        "terminal_is_error": True,
                        "terminal_subtype": classification["terminal_subtype"],
                        "error_message_present": classification["error_message_present"],
                        "error_message_category": classification["error_message_category"],
                    },
                }
    if session_id is None:
        return dict(RAW_FREE_BLOCK)
    fingerprint = _sha256(_canonical(sorted(tool_use_ids)))
    return {
        "status": "QWEN_RUNTIME_EVIDENCE_PROJECTED",
        "session_id": session_id,
        "turns": len(assistant_ids),
        "tool_calls": len(tool_use_ids),
        "wall_time_seconds": wall_time_seconds,
        "tool_fingerprint": fingerprint,
        "session_ended": session_ended,
        "terminal_reason": None,
        "budget_stop": False,
        "loop_status": "UNOBSERVED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Raw-free Qwen runtime evidence adapter")
    parser.add_argument("--project-events", type=Path)
    parser.add_argument("--process-observation-file", type=Path)
    parser.add_argument("--wall-time-seconds", type=int, default=0)
    parser.add_argument("--prepare-continuation", type=Path)
    parser.add_argument("--launch-id")
    parser.add_argument("--fresh-evidence-id")
    parser.add_argument("--session-id")
    parser.add_argument("--continuation-packet-output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.project_events is not None:
            if args.project_events.stat().st_size > MAX_EVENT_BYTES:
                result = dict(RAW_FREE_BLOCK)
            elif args.process_observation_file is not None:
                if args.process_observation_file.stat().st_size > 64 * 1024 or not args.launch_id:
                    result = dict(RAW_FREE_BLOCK)
                else:
                    observation = json.loads(args.process_observation_file.read_text(encoding="utf-8"))
                    result = project_terminal_receipt(
                        args.project_events.read_text(encoding="utf-8"),
                        observation,
                        expected_launch_id=args.launch_id,
                    )
            elif args.launch_id is not None:
                result = dict(RAW_FREE_BLOCK)
            else:
                result = project_qwen_events(args.project_events.read_text(encoding="utf-8"), wall_time_seconds=args.wall_time_seconds)
        elif args.prepare_continuation is not None:
            request = json.loads(args.prepare_continuation.read_text(encoding="utf-8"))
            result = prepare_continuation(
                request, launch_id=args.launch_id, fresh_evidence_id=args.fresh_evidence_id,
                session_id=args.session_id,
            )
            if result.get("status") == "QWEN_RUNTIME_GUARD_READY":
                packet = result.pop("continuation_packet", None)
                if args.continuation_packet_output is None or not isinstance(packet, str):
                    result = {**RAW_FREE_BLOCK, "reason": "CONTROLLER_EVIDENCE_MALFORMED"}
                else:
                    args.continuation_packet_output.write_text(packet, encoding="utf-8")
        else:
            parser.error("one operation is required")
            return 2
    except (OSError, UnicodeError, json.JSONDecodeError):
        result = dict(RAW_FREE_BLOCK)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("status") in {
        "QWEN_RUNTIME_EVIDENCE_PROJECTED", "QWEN_RUNTIME_GUARD_READY", "COMPLETE"
    } else 3


if __name__ == "__main__":
    raise SystemExit(main())
