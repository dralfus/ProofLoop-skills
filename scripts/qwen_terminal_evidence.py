"""Project complete Qwen Dual Output JSONL and host observations to raw-free evidence."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


MAX_EVENT_BYTES = 16 * 1024 * 1024
MAX_EVENT_LINE_BYTES = 1024 * 1024
MAX_TEXT_RESULT_BYTES = 65_536
MAX_ELAPSED_MS = 24 * 60 * 60 * 1000
LOOP_DETECTOR_VERSION = "exact_tool_interaction_cycle_v1"
RECEIPT_SCHEMA = "proofloop.qwen-terminal-receipt.v1"
_OBSERVATION_FIELDS = frozenset(
    {
        "launch_id",
        "child_started",
        "process_exited",
        "process_exit_code",
        "host_stop_reason",
        "host_stop_requested",
        "host_interrupt_sent",
        "stop_observed_while_running",
        "session_end_seen_before_stop",
        "event_file_bytes_at_stop",
        "event_file_closed",
        "elapsed_ms",
    }
)
_EVENT_TYPES = {
    "system",
    "assistant",
    "user",
    "control_request",
    "control_response",
    "stream_event",
    "result",
}
_BLOCK_TYPES = {"text", "tool_use", "tool_result"}
_STOP_REASONS = {"HOST_WALL_LIMIT", "HOST_TOOL_LIMIT"}


class _ProjectionError(ValueError):
    def __init__(self, reason: str, *, incomplete: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.incomplete = incomplete


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise _ProjectionError("EVENT_SCHEMA_UNKNOWN") from error


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_free(
    *,
    launch_id: str,
    status: str,
    reason: str,
    terminal_reason: str,
    terminal_source: str,
    process_exit_code: int | None,
    event_coverage: str,
    turns: int,
    tool_calls: int,
    elapsed_ms: int,
    loop_status: str,
    budget_stop: bool,
    session_id: str | None = None,
) -> dict[str, Any]:
    session_digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest() if session_id else None
    return {
        "schema_version": RECEIPT_SCHEMA,
        "status": status,
        "reason": reason,
        "launch_id": launch_id,
        "session_id_hash": session_digest,
        "terminal_reason": terminal_reason,
        "terminal_source": terminal_source,
        "process_exit_code": process_exit_code,
        "event_coverage": event_coverage,
        "turns": turns,
        "tool_calls": tool_calls,
        "wall_time_seconds": elapsed_ms // 1000,
        "loop_status": loop_status,
        "loop_detector_version": LOOP_DETECTOR_VERSION,
        "budget_stop": budget_stop,
    }


def _validate_observation(observation: object, expected_launch_id: str) -> dict[str, Any]:
    if not isinstance(observation, dict) or set(observation) != _OBSERVATION_FIELDS:
        raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    launch_id = observation.get("launch_id")
    if (
        not isinstance(launch_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", launch_id) is None
        or launch_id != expected_launch_id
    ):
        raise _ProjectionError("LAUNCH_ID_MISMATCH")
    for key in (
        "child_started",
        "process_exited",
        "host_stop_requested",
        "host_interrupt_sent",
        "stop_observed_while_running",
        "session_end_seen_before_stop",
        "event_file_closed",
    ):
        if type(observation.get(key)) is not bool:
            raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    exit_code = observation.get("process_exit_code")
    if exit_code is not None and (type(exit_code) is not int or not -1 <= exit_code <= 255):
        raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    elapsed_ms = observation.get("elapsed_ms")
    if type(elapsed_ms) is not int or not 0 <= elapsed_ms <= MAX_ELAPSED_MS:
        raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    stop_reason = observation.get("host_stop_reason")
    if stop_reason is not None and (
        not isinstance(stop_reason, str) or stop_reason not in _STOP_REASONS
    ):
        raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    stop_offset = observation.get("event_file_bytes_at_stop")
    if stop_reason is None:
        if observation.get("host_stop_requested") or observation.get("host_interrupt_sent") or stop_offset is not None:
            raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    elif (
        not observation.get("host_stop_requested")
        or not observation.get("host_interrupt_sent")
        or type(stop_offset) is not int
        or not 0 <= stop_offset <= MAX_EVENT_BYTES
    ):
        raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    if observation.get("process_exited") and exit_code is None:
        raise _ProjectionError("PROCESS_OBSERVATION_INVALID")
    return observation


def _decode_event_lines(event_jsonl: str) -> list[tuple[int, dict[str, Any]]]:
    if not isinstance(event_jsonl, str):
        raise _ProjectionError("EVENT_STREAM_INVALID")
    try:
        encoded = event_jsonl.encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise _ProjectionError("EVENT_STREAM_INVALID", incomplete=True) from error
    if not encoded or len(encoded) > MAX_EVENT_BYTES:
        raise _ProjectionError("EVENT_STREAM_INCOMPLETE", incomplete=True)
    if not encoded.endswith(b"\n"):
        raise _ProjectionError("EVENT_STREAM_INCOMPLETE", incomplete=True)

    def reject_constant(_: str) -> None:
        raise ValueError("non-finite number")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = item
        return value

    decoded: list[tuple[int, dict[str, Any]]] = []
    offset = 0
    for raw_line in encoded.splitlines(keepends=True):
        start = offset
        offset += len(raw_line)
        line = raw_line[:-1]
        if line.endswith(b"\r"):
            line = line[:-1]
        if not line or len(line) > MAX_EVENT_LINE_BYTES:
            raise _ProjectionError("EVENT_STREAM_INCOMPLETE", incomplete=True)
        try:
            event = json.loads(
                line.decode("utf-8", errors="strict"),
                parse_constant=reject_constant,
                object_pairs_hook=unique_object,
            )
        except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as error:
            raise _ProjectionError("EVENT_STREAM_INCOMPLETE", incomplete=True) from error
        if not isinstance(event, dict):
            raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
        decoded.append((start, event))
    if offset != len(encoded):
        raise _ProjectionError("EVENT_STREAM_INCOMPLETE", incomplete=True)
    return decoded


def _text_result_size(value: object) -> int:
    try:
        if isinstance(value, str):
            return len(value.encode("utf-8", errors="strict"))
        if isinstance(value, list):
            total = 0
            for block in value:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    total += len(block["text"].encode("utf-8", errors="strict"))
            return total
        return len(_canonical(value))
    except UnicodeError as error:
        raise _ProjectionError("EVENT_SCHEMA_UNKNOWN") from error


def _interaction_cycles(
    events: list[tuple[int, dict[str, Any]]],
) -> tuple[str | None, int, int, int, bool, list[str]]:
    """Return session id, counters, terminal offset, uncertainty, and adjacent fingerprints."""
    session_id: str | None = None
    session_end_offsets: list[int] = []
    message_ids: set[str] = set()
    tool_ids: set[str] = set()
    pending: dict[str, dict[str, Any]] = {}
    assistant_content: list[object] | None = None
    assistant_tools: list[str] = []
    matched: dict[str, dict[str, Any]] = {}
    cycles: list[str] = []
    turns = 0
    tool_calls = 0
    loop_unknown = False

    def finalize_cycle() -> None:
        nonlocal assistant_content, assistant_tools, matched, pending, loop_unknown
        if assistant_content is None:
            return
        if len(matched) != len(assistant_tools):
            raise _ProjectionError("TOOL_RESULT_MISSING", incomplete=True)
        ordered_results = [matched[identity] for identity in assistant_tools]
        if any(result["oversized"] for result in ordered_results):
            loop_unknown = True
            assistant_content = None
            assistant_tools = []
            matched = {}
            pending = {}
            return
        cycles.append(
            _digest(
                {
                    "assistant_content": assistant_content,
                    "results": [
                        {"content": result["content"], "is_error": result["is_error"]}
                        for result in ordered_results
                    ],
                }
            )
        )
        assistant_content = None
        assistant_tools = []
        matched = {}
        pending = {}

    for offset, event in events:
        event_type = event.get("type")
        if not isinstance(event_type, str) or event_type not in _EVENT_TYPES:
            raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
        if event_type == "system":
            subtype = event.get("subtype")
            if subtype == "session_start":
                if session_id is not None or not isinstance(event.get("session_id"), str) or not event["session_id"]:
                    raise _ProjectionError("SESSION_ID_INVALID")
                try:
                    event["session_id"].encode("utf-8", errors="strict")
                except UnicodeError as error:
                    raise _ProjectionError("SESSION_ID_INVALID") from error
                session_id = event["session_id"]
            elif subtype == "session_end":
                if session_id is None or pending or assistant_content is not None:
                    raise _ProjectionError("SESSION_END_INVALID", incomplete=True)
                session_end_offsets.append(offset)
            elif subtype is None:
                raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
            continue

        if session_id is None:
            raise _ProjectionError("SESSION_START_MISSING", incomplete=True)

        if event_type == "assistant":
            message = event.get("message")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
            message_id = message.get("id")
            content = message.get("content")
            if not isinstance(message_id, str) or not message_id or message_id in message_ids or not isinstance(content, list):
                raise _ProjectionError("MESSAGE_ID_INVALID")
            message_ids.add(message_id)
            turns += 1
            if assistant_content is not None:
                if pending:
                    raise _ProjectionError("TOOL_RESULT_MISSING", incomplete=True)
                finalize_cycle()
            if pending:
                raise _ProjectionError("TOOL_RESULT_MISSING", incomplete=True)
            normalized: list[object] = []
            tools: list[str] = []
            for block in content:
                if (
                    not isinstance(block, dict)
                    or not isinstance(block.get("type"), str)
                    or block.get("type") not in _BLOCK_TYPES
                ):
                    raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
                block_type = block["type"]
                if block_type == "text":
                    text = block.get("text")
                    if not isinstance(text, str):
                        raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
                    normalized.append({"type": "text", "text": text})
                elif block_type == "tool_use":
                    identity = block.get("id")
                    name = block.get("name")
                    if (
                        not isinstance(identity, str)
                        or not identity
                        or identity in tool_ids
                        or not isinstance(name, str)
                        or not name
                        or not isinstance(block.get("input"), dict)
                    ):
                        raise _ProjectionError("TOOL_USE_INVALID")
                    tool_ids.add(identity)
                    input_value = block["input"]
                    _canonical(input_value)
                    normalized.append({"type": "tool_use", "name": name, "input": input_value})
                    tools.append(identity)
                    pending[identity] = {"name": name, "input": input_value}
                else:
                    raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
            if tools:
                assistant_content = normalized
                assistant_tools = tools
                matched = {}
            else:
                # A completed assistant response without a tool call breaks a tool-cycle run.
                cycles = []
            continue

        if event_type == "user":
            message = event.get("message")
            if not isinstance(message, dict) or message.get("role") != "user" or not isinstance(message.get("content"), list):
                raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
            results_here = False
            text_here = False
            for block in message["content"]:
                if (
                    not isinstance(block, dict)
                    or not isinstance(block.get("type"), str)
                    or block.get("type") not in _BLOCK_TYPES
                ):
                    raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
                if block["type"] == "tool_result":
                    identity = block.get("tool_use_id")
                    if (
                        not isinstance(identity, str)
                        or identity not in pending
                        or identity in matched
                        or "content" not in block
                    ):
                        raise _ProjectionError("TOOL_RESULT_UNPAIRED", incomplete=True)
                    content_value = block.get("content")
                    is_error = block.get("is_error", False)
                    if type(is_error) is not bool:
                        raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
                    result_size = _text_result_size(content_value)
                    matched[identity] = {
                        "content": content_value,
                        "is_error": is_error,
                        "oversized": result_size >= MAX_TEXT_RESULT_BYTES,
                    }
                    tool_calls += 1
                    results_here = True
                elif block["type"] == "text":
                    if not isinstance(block.get("text"), str):
                        raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
                    text_here = True
                else:
                    raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
            if results_here:
                if text_here:
                    loop_unknown = True
                if len(matched) == len(assistant_tools):
                    finalize_cycle()
            elif text_here:
                if assistant_content is not None:
                    raise _ProjectionError("TOOL_RESULT_MISSING", incomplete=True)
                # A human/model prompt between actions means they are not adjacent cycles.
                cycles = []
            continue

        # Other documented event classes do not alter the tool stream, but unknown shapes
        # cannot establish that a repeated interaction was adjacent and complete.
        if event_type in {"control_request", "control_response", "stream_event", "result"}:
            payload = event.get("request") or event.get("response") or event.get("data") or event.get("result")
            if payload is None:
                raise _ProjectionError("EVENT_SCHEMA_UNKNOWN")
            if event_type in {"control_request", "control_response", "stream_event"}:
                loop_unknown = True
            else:
                cycles = []

    if session_id is None:
        raise _ProjectionError("SESSION_START_MISSING", incomplete=True)
    if pending or assistant_content is not None:
        raise _ProjectionError("TOOL_RESULT_MISSING", incomplete=True)
    if len(session_end_offsets) != 1:
        raise _ProjectionError("SESSION_END_MISSING", incomplete=True)
    if events[-1][1].get("type") != "system" or events[-1][1].get("subtype") != "session_end":
        raise _ProjectionError("SESSION_END_NOT_FINAL", incomplete=True)
    return session_id, turns, tool_calls, session_end_offsets[0], loop_unknown, cycles[-3:]


def _project_terminal_receipt(
    event_jsonl: str,
    process_observation: object,
    *,
    expected_launch_id: str,
) -> dict[str, object]:
    """Return a fixed raw-free receipt; incomplete or ambiguous evidence fails closed."""
    if not isinstance(expected_launch_id, str) or re.fullmatch(r"[0-9a-f]{32}", expected_launch_id) is None:
        return _raw_free(
            launch_id="0" * 32,
            status="BLOCKED",
            reason="LAUNCH_ID_INVALID",
            terminal_reason="UNKNOWN",
            terminal_source="UNKNOWN",
            process_exit_code=None,
            event_coverage="UNKNOWN",
            turns=0,
            tool_calls=0,
            elapsed_ms=0,
            loop_status="UNKNOWN",
            budget_stop=False,
        )
    try:
        observation = _validate_observation(process_observation, expected_launch_id)
        decoded = _decode_event_lines(event_jsonl)
        session_id, turns, tool_calls, session_end_offset, loop_unknown, cycle_hashes = _interaction_cycles(decoded)
    except _ProjectionError as error:
        observation = process_observation if isinstance(process_observation, dict) else {}
        elapsed_ms = observation.get("elapsed_ms", 0)
        exit_code = observation.get("process_exit_code")
        return _raw_free(
            launch_id=expected_launch_id,
            status="BLOCKED",
            reason=error.reason,
            terminal_reason="UNKNOWN",
            terminal_source="UNKNOWN",
            process_exit_code=exit_code if type(exit_code) is int and -1 <= exit_code <= 255 else None,
            event_coverage="INCOMPLETE" if error.incomplete else "UNKNOWN",
            turns=0,
            tool_calls=0,
            elapsed_ms=elapsed_ms if type(elapsed_ms) is int and 0 <= elapsed_ms <= MAX_ELAPSED_MS else 0,
            loop_status="UNKNOWN",
            budget_stop=False,
        )

    elapsed_ms = observation["elapsed_ms"]
    exit_code = observation["process_exit_code"]
    host_stop_reason = observation["host_stop_reason"]
    stop_offset = observation["event_file_bytes_at_stop"]
    if host_stop_reason is not None:
        event_bytes = event_jsonl.encode("utf-8")
        if stop_offset > len(event_bytes) or (
            stop_offset > 0 and not event_bytes[:stop_offset].endswith(b"\n")
        ):
            return _raw_free(
                launch_id=expected_launch_id,
                status="BLOCKED",
                reason="HOST_STOP_OFFSET_NOT_LINE_BOUNDARY",
                terminal_reason="UNKNOWN",
                terminal_source="UNKNOWN",
                process_exit_code=observation["process_exit_code"],
                event_coverage="INCOMPLETE",
                turns=turns,
                tool_calls=tool_calls,
                elapsed_ms=observation["elapsed_ms"],
                loop_status="UNKNOWN",
                budget_stop=False,
                session_id=session_id,
            )
    complete = (
        observation["child_started"]
        and observation["process_exited"]
        and observation["event_file_closed"]
        and exit_code is not None
    )
    if host_stop_reason is not None:
        if session_end_offset < stop_offset:
            return _raw_free(
                launch_id=expected_launch_id,
                status="BLOCKED",
                reason="SESSION_END_PRECEDES_HOST_STOP",
                terminal_reason="UNKNOWN",
                terminal_source="UNKNOWN",
                process_exit_code=exit_code,
                event_coverage="UNKNOWN",
                turns=turns,
                tool_calls=tool_calls,
                elapsed_ms=elapsed_ms,
                loop_status="UNKNOWN",
                budget_stop=False,
                session_id=session_id,
            )
        if observation["session_end_seen_before_stop"]:
            return _raw_free(
                launch_id=expected_launch_id,
                status="BLOCKED",
                reason="SESSION_END_PRECEDES_HOST_STOP",
                terminal_reason="UNKNOWN",
                terminal_source="UNKNOWN",
                process_exit_code=exit_code,
                event_coverage="UNKNOWN",
                turns=turns,
                tool_calls=tool_calls,
                elapsed_ms=elapsed_ms,
                loop_status="UNKNOWN",
                budget_stop=False,
                session_id=session_id,
            )
        complete = complete and observation["host_stop_requested"] and observation["stop_observed_while_running"]
        if not complete:
            return _raw_free(
                launch_id=expected_launch_id,
                status="BLOCKED",
                reason="HOST_STOP_NOT_PROVEN",
                terminal_reason="UNKNOWN",
                terminal_source="UNKNOWN",
                process_exit_code=exit_code,
                event_coverage="INCOMPLETE",
                turns=turns,
                tool_calls=tool_calls,
                elapsed_ms=elapsed_ms,
                loop_status="UNKNOWN",
                budget_stop=False,
                session_id=session_id,
            )
        terminal_reason = host_stop_reason
        terminal_source = "HOST"
        budget_stop = True
    else:
        if not complete:
            return _raw_free(
                launch_id=expected_launch_id,
                status="BLOCKED",
                reason="PROCESS_TERMINAL_UNPROVEN",
                terminal_reason="UNKNOWN",
                terminal_source="UNKNOWN",
                process_exit_code=exit_code,
                event_coverage="INCOMPLETE",
                turns=turns,
                tool_calls=tool_calls,
                elapsed_ms=elapsed_ms,
                loop_status="UNKNOWN",
                budget_stop=False,
                session_id=session_id,
            )
        terminal_reason = "NORMAL_EXIT" if exit_code == 0 else "PROCESS_FAILURE"
        terminal_source = "PROCESS"
        budget_stop = False

    if loop_unknown:
        loop_status = "UNKNOWN"
    else:
        loop_status = "DETECTED" if len(cycle_hashes) == 3 and len(set(cycle_hashes)) == 1 else "HOST_CLEAR"
    status = "BLOCKED" if loop_status in {"UNKNOWN", "DETECTED"} else "COMPLETE"
    reason = "LOOP_PATTERN_DETECTED" if loop_status == "DETECTED" else "COMPLETE" if status == "COMPLETE" else "LOOP_EVIDENCE_UNKNOWN"
    if not budget_stop and terminal_reason == "NORMAL_EXIT" and loop_status == "HOST_CLEAR":
        reason = "NORMAL_EXIT_NOT_RESUMABLE"
    return _raw_free(
        launch_id=expected_launch_id,
        status=status,
        reason=reason,
        terminal_reason=terminal_reason,
        terminal_source=terminal_source,
        process_exit_code=exit_code,
        event_coverage="COMPLETE",
        turns=turns,
        tool_calls=tool_calls,
        elapsed_ms=elapsed_ms,
        loop_status=loop_status,
        budget_stop=budget_stop,
        session_id=session_id,
    )


def project_terminal_receipt(
    event_jsonl: str,
    process_observation: object,
    *,
    expected_launch_id: str,
) -> dict[str, object]:
    """Public no-raw boundary: even unexpected malformed inputs return fixed evidence."""
    safe_launch_id = (
        expected_launch_id
        if isinstance(expected_launch_id, str)
        and re.fullmatch(r"[0-9a-f]{32}", expected_launch_id) is not None
        else "0" * 32
    )
    try:
        return _project_terminal_receipt(
            event_jsonl,
            process_observation,
            expected_launch_id=expected_launch_id,
        )
    except Exception:
        return _raw_free(
            launch_id=safe_launch_id,
            status="BLOCKED",
            reason="PROJECTION_FAILURE",
            terminal_reason="UNKNOWN",
            terminal_source="UNKNOWN",
            process_exit_code=None,
            event_coverage="UNKNOWN",
            turns=0,
            tool_calls=0,
            elapsed_ms=0,
            loop_status="UNKNOWN",
            budget_stop=False,
        )
