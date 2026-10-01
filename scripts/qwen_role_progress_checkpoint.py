"""Project raw-free role-agent progress facts and evaluate the checkpoint gate.

Ticket 26: when an unfinished allowlisted role-agent has accumulated six
read-only tool calls, the Controller requires a short progress checkpoint
before the next action. Six is a checkpoint threshold, not a hard cap, not a
count of consecutive calls, and not a reason to end useful work. Loop
detection, budget ceilings, and Qwen settings are owned by other gates and
are not changed here.

SEAM LIMITATION (Ticket 26): the parent stream-json events carry only the
Controller's own Agent dispatch tool_use/tool_result pairs. Nested role-agent
internal tool calls are not visible in the parent stream, so the projector
cannot attribute them to a role identity. It therefore counts only calls that
are observable and unambiguously attributable to one role dispatch window; a
role with no observed internal calls keeps zero counters and never gains
checkpoint authority from absence of evidence. Unknown or unclassified tool
names never count as read-only.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from qwen_terminal_evidence import (
    _ROLE_LIFECYCLE_ALLOWLIST,
    _decode_event_lines,
    _ProjectionError,
)

ROLE_PROGRESS_SCHEMA = "proofloop.qwen-role-progress.v1"
ROLE_PROGRESS_CHECKPOINT_VERSION = "role_progress_checkpoint_v1"
READ_CHECKPOINT_THRESHOLD = 6

READ_ONLY_TOOL_CLASSES = frozenset(
    {
        "read_file",
        "glob",
        "grep_search",
        "list_directory",
        "tool_search",
        "read_mcp_resource",
        "zoom_image",
    }
)
MUTATING_TOOL_CLASSES = frozenset(
    {
        "edit",
        "write_file",
        "notebook_edit",
        "run_shell_command",
        "agent",
        "task_stop",
        "send_message",
    }
)

_INPUT_FIELDS = frozenset(
    {
        "checkpoint_version",
        "role",
        "role_completed",
        "read_only_tool_calls",
        "mutating_tool_calls",
        "unclassified_tool_calls",
        "new_verified_facts",
        "next_step_declared",
        "task_scope_unchanged",
    }
)


def classify_tool_class(name: object) -> str:
    if not isinstance(name, str) or not name:
        return "unclassified"
    lowered = name.casefold()
    if lowered in READ_ONLY_TOOL_CLASSES:
        return "read"
    if lowered in MUTATING_TOOL_CLASSES:
        return "mutating"
    return "unclassified"


def project_role_progress(event_jsonl: str, *, expected_launch_id: str) -> dict[str, Any]:
    """Project per-role tool-class counters; unknown forms fail closed without raw echo."""
    safe_launch_id = (
        expected_launch_id
        if isinstance(expected_launch_id, str)
        and re.fullmatch(r"[0-9a-f]{32}", expected_launch_id) is not None
        else "0" * 32
    )

    def result(status: str, reason: str, roles: list[dict[str, object]] | None = None) -> dict[str, Any]:
        return {
            "schema_version": ROLE_PROGRESS_SCHEMA,
            "status": status,
            "reason": reason,
            "launch_id": safe_launch_id,
            "read_checkpoint_threshold": READ_CHECKPOINT_THRESHOLD,
            "roles": roles or [],
        }

    if safe_launch_id == "0" * 32:
        return result("BLOCKED", "LAUNCH_ID_INVALID")
    try:
        decoded = _decode_event_lines(event_jsonl)
    except _ProjectionError as error:
        return result("BLOCKED", error.reason)
    except Exception:
        return result("BLOCKED", "PROJECTION_FAILURE")

    roles: list[dict[str, object]] = []
    pending: dict[str, dict[str, object]] = {}
    unattributed = {"read": 0, "mutating": 0, "unclassified": 0}
    try:
        for _, event in decoded:
            event_type = event.get("type")
            if event_type == "assistant":
                message = event.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    identity = block.get("id")
                    name = block.get("name")
                    if not isinstance(identity, str) or not isinstance(name, str) or not name:
                        continue
                    if name.casefold() == "agent":
                        call_input = block.get("input")
                        role_name = call_input.get("subagent_type") if isinstance(call_input, dict) else None
                        fresh_named = bool(
                            isinstance(call_input, dict)
                            and call_input.get("resume_agent_id") in (None, "")
                            and call_input.get("fork") is not True
                            and not any(
                                call_input.get(field) not in (None, "", False, [])
                                for field in ("fork_turns", "fork_tools", "fork_profile")
                            )
                        )
                        if role_name in _ROLE_LIFECYCLE_ALLOWLIST and fresh_named:
                            role_entry: dict[str, object] = {
                                "role": role_name,
                                "completion": "PENDING",
                                "read_only_tool_calls": 0,
                                "mutating_tool_calls": 0,
                                "unclassified_tool_calls": 0,
                                "checkpoint_required": False,
                            }
                            roles.append(role_entry)
                            pending[identity] = {"kind": "role", "entry": role_entry}
                        else:
                            unattributed["unclassified"] += 1
                            pending[identity] = {"kind": "unclassified"}
                        continue
                    # Only the Controller dispatches roles in this stream, so a
                    # non-Agent tool call here is Controller-level activity and
                    # is never attributed to a role. Role-internal calls are not
                    # observable in the parent stream (see module docstring);
                    # they can only ever land in the conservative unattributed
                    # tally, which never grants checkpoint authority.
                    unattributed[classify_tool_class(name)] += 1
            elif event_type == "user":
                message = event.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    state = pending.get(block.get("tool_use_id"))
                    if state is not None and state["kind"] == "role":
                        state["entry"]["completion"] = (
                            "ERROR" if block.get("is_error", False) else "COMPLETED"
                        )
    except Exception:
        return result("BLOCKED", "PROJECTION_FAILURE")

    for role_entry in roles:
        role_entry["checkpoint_required"] = bool(
            role_entry["completion"] == "PENDING"
            and int(role_entry["read_only_tool_calls"]) >= READ_CHECKPOINT_THRESHOLD
        )
    projection = result("COMPLETE", "ROLE_PROGRESS_PROJECTED", roles)
    projection["unattributed_tool_calls"] = dict(unattributed)
    return projection


def evaluate_progress_checkpoint(payload: object) -> dict[str, object]:
    """Pure Controller gate: below threshold ALLOW, at threshold require checkpoint evidence."""
    base = {"schema_version": ROLE_PROGRESS_SCHEMA + ".decision"}
    if not isinstance(payload, dict) or frozenset(payload) != _INPUT_FIELDS:
        return {**base, "status": "BLOCK", "reason": "CHECKPOINT_INPUT_INVALID", "role": None}
    if payload["checkpoint_version"] != ROLE_PROGRESS_CHECKPOINT_VERSION:
        return {**base, "status": "BLOCK", "reason": "CHECKPOINT_VERSION_UNSUPPORTED", "role": None}
    role = payload["role"]
    if role not in _ROLE_LIFECYCLE_ALLOWLIST:
        return {**base, "status": "BLOCK", "reason": "ROLE_NOT_ALLOWLISTED", "role": None}
    for field in ("role_completed", "new_verified_facts", "next_step_declared", "task_scope_unchanged"):
        if type(payload[field]) is not bool:
            return {**base, "status": "BLOCK", "reason": "CHECKPOINT_INPUT_INVALID", "role": role}
    for field in ("read_only_tool_calls", "mutating_tool_calls", "unclassified_tool_calls"):
        value = payload[field]
        if type(value) is not int or value < 0:
            return {**base, "status": "BLOCK", "reason": "CHECKPOINT_INPUT_INVALID", "role": role}

    decision_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()

    def decide(status: str, reason: str) -> dict[str, object]:
        return {
            "schema_version": ROLE_PROGRESS_SCHEMA + ".decision",
            "decision_id": decision_id,
            "status": status,
            "reason": reason,
            "role": role,
            "read_only_tool_calls": payload["read_only_tool_calls"],
            "checkpoint_threshold": READ_CHECKPOINT_THRESHOLD,
        }

    if payload["role_completed"]:
        return decide("ALLOW", "ROLE_COMPLETED_BEFORE_THRESHOLD")
    if payload["read_only_tool_calls"] < READ_CHECKPOINT_THRESHOLD:
        return decide("ALLOW", "BELOW_CHECKPOINT_THRESHOLD")
    if not payload["task_scope_unchanged"]:
        return decide("BLOCK", "TASK_SCOPE_CHANGED")
    if not payload["new_verified_facts"] or not payload["next_step_declared"]:
        return decide("BLOCK", "PROGRESS_CHECKPOINT_REQUIRED")
    return decide("ALLOW", "CHECKPOINT_ACCEPTED")
