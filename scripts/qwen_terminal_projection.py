"""Pure, raw-free projection of Qwen terminal JSON and error envelopes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


_STRUCTURED_OUTPUT_PATTERN = re.compile(
    r"(?i)model did not produce structured output|"
    r"plain text instead of calling.*structured_output|"
    r"structured[ _-]?output.*missing"
)
_AUTH_PATTERN = re.compile(
    r"(?i)\b(401|403)\b|unauthori[sz]ed|forbidden|api[\s_-]*key|"
    r"authentication|bearer|token"
)
_TRANSPORT_PATTERN = re.compile(
    r"(?i)\b5\d\d\b|websocket|https?://|fetch failed|timed? ?out|"
    r"network|connection|econn|dns|proxy|gateway"
)


def _parse_output(output: object) -> tuple[bool, bool, str, object | None]:
    present = isinstance(output, str) and bool(output.strip())
    if not present:
        return False, False, "none", None
    try:
        parsed = json.loads(output)
    except (TypeError, json.JSONDecodeError):
        return True, False, "none", None
    if isinstance(parsed, list):
        return True, True, "array", parsed
    if isinstance(parsed, dict):
        return True, True, "object", parsed
    return True, True, "other", parsed


def _terminal(parsed: object, *, require_final: bool = False) -> tuple[dict[str, object] | None, bool]:
    if isinstance(parsed, list):
        if require_final:
            terminal = parsed[-1] if parsed and isinstance(parsed[-1], dict) else None
            return (terminal, False) if isinstance(terminal, dict) and terminal.get("type") == "result" else (None, False)
        events = [event for event in parsed if isinstance(event, dict) and event.get("type") == "result"]
        return (events[-1], False) if events else (None, False)
    if not isinstance(parsed, dict):
        return None, False
    if parsed.get("type") == "result":
        return parsed, False
    if any(field in parsed for field in ("is_error", "subtype", "error")):
        return parsed, True
    return None, False


def _error_message(terminal: dict[str, object]) -> tuple[str, str, bool]:
    message = ""
    error = terminal.get("error")
    if isinstance(error, dict) and error.get("message") is not None:
        message = str(error["message"])
    legacy_message = terminal.get("errorMessage")
    if not message and legacy_message is not None:
        message = str(legacy_message)
    error_type = str(terminal.get("errorType", ""))
    present = bool(message.strip())
    if _STRUCTURED_OUTPUT_PATTERN.search(message) or error_type in {
        "structured_output_missing",
        "structured-output-missing",
    } or _STRUCTURED_OUTPUT_PATTERN.search(str(legacy_message or "")):
        return message, "structured_output_missing", True
    if _AUTH_PATTERN.search(message):
        return message, "auth_or_forbidden", False
    if _TRANSPORT_PATTERN.search(message):
        return message, "transport", False
    return message, "other" if present else "none", False


def inspect_output(output: object) -> dict[str, object]:
    present, is_json, shape, parsed = _parse_output(output)
    terminal, is_envelope = _terminal(parsed)
    inspection: dict[str, object] = {
        "present": present,
        "json": is_json,
        "structured_output_marker": False,
        "json_shape": shape,
        "terminal_result": False,
        "terminal_is_error": False,
        "terminal_subtype": "none",
        "error_message_present": False,
        "error_message_category": "none",
        "envelope_is_error": False,
        "envelope_subtype": "none",
        "envelope_error_message_present": False,
        "envelope_error_message_category": "none",
    }
    if terminal is not None:
        is_error = terminal.get("is_error") if isinstance(terminal.get("is_error"), bool) else False
        subtype_value = terminal.get("subtype")
        subtype = subtype_value if subtype_value in {"success", "error_during_execution"} else (
            "other" if subtype_value not in (None, "") else "none"
        )
        message, category, structured_marker = _error_message(terminal)
        message_present = bool(message.strip())
        inspection["structured_output_marker"] = structured_marker
        inspection["error_message_present"] = message_present
        inspection["error_message_category"] = category
        if is_envelope:
            inspection["envelope_is_error"] = is_error
            inspection["envelope_subtype"] = subtype
            inspection["envelope_error_message_present"] = message_present
            inspection["envelope_error_message_category"] = category
        else:
            inspection["terminal_result"] = True
            inspection["terminal_is_error"] = is_error
            inspection["terminal_subtype"] = subtype
    if not inspection["structured_output_marker"] and present and isinstance(output, str):
        if _STRUCTURED_OUTPUT_PATTERN.search(output):
            inspection["structured_output_marker"] = True
            inspection["error_message_category"] = "structured_output_missing"
    return inspection


def project_failure(stdout: object, stderr: object) -> dict[str, object]:
    """Return only allowlisted terminal facts; never return raw output."""
    stdout_inspection = inspect_output(stdout)
    stderr_inspection = inspect_output(stderr)
    stdout_structured = bool(stdout_inspection["structured_output_marker"])
    stderr_structured = bool(stderr_inspection["structured_output_marker"])
    json_error = any(
        bool(inspection[field])
        for inspection in (stdout_inspection, stderr_inspection)
        for field in ("terminal_is_error", "envelope_is_error")
    )
    reason = (
        "STRUCTURED_OUTPUT_MISSING"
        if stdout_structured or stderr_structured
        else "QWEN_JSON_ERROR_RESULT"
        if json_error
        else "QWEN_COMMAND_FAILED"
    )
    structured_channel = (
        "stdout+stderr"
        if stdout_structured and stderr_structured
        else "stdout"
        if stdout_structured
        else "stderr"
        if stderr_structured
        else "none"
    )

    def first(inspection_key: str, default: object) -> object:
        value = stdout_inspection[inspection_key]
        return value if value not in (False, "none") else stderr_inspection[inspection_key] or default

    diagnostic = {
        "stdout_present": bool(stdout_inspection["present"]),
        "stderr_present": bool(stderr_inspection["present"]),
        "stdout_json": bool(stdout_inspection["json"]),
        "stderr_json": bool(stderr_inspection["json"]),
        "structured_output_channel": structured_channel,
        "json_shape": first("json_shape", "none"),
        "terminal_result": bool(stdout_inspection["terminal_result"] or stderr_inspection["terminal_result"]),
        "terminal_is_error": json_error,
        "terminal_subtype": first("terminal_subtype", "none"),
        "error_message_present": bool(stdout_inspection["error_message_present"] or stderr_inspection["error_message_present"]),
        "error_message_category": first("error_message_category", "none"),
        "envelope_is_error": bool(stdout_inspection["envelope_is_error"] or stderr_inspection["envelope_is_error"]),
        "envelope_subtype": first("envelope_subtype", "none"),
        "envelope_error_message_present": bool(stdout_inspection["envelope_error_message_present"] or stderr_inspection["envelope_error_message_present"]),
        "envelope_error_message_category": first("envelope_error_message_category", "none"),
    }
    return {"reason": reason, "diagnostic": diagnostic}


def extract_structured_result(output: object) -> dict[str, object] | None:
    """Extract only a successful terminal structured result."""
    _, is_json, _, parsed = _parse_output(output)
    if not is_json:
        return None
    terminal, is_envelope = _terminal(parsed, require_final=True)
    if is_envelope or terminal is None:
        return None
    is_error = terminal.get("is_error")
    if is_error is not None and (not isinstance(is_error, bool) or is_error):
        return None
    subtype = terminal.get("subtype")
    if subtype is not None and subtype != "success":
        return None
    result = terminal.get("structured_result")
    return result if isinstance(result, dict) else None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", action="store_true")
    parser.add_argument("--stdout-file", type=Path)
    parser.add_argument("--stderr-file", type=Path)
    parser.add_argument("--extract-structured-result", action="store_true")
    parser.add_argument("--input-file", type=Path)
    args = parser.parse_args()
    if args.project:
        print(json.dumps(project_failure(_read(args.stdout_file), _read(args.stderr_file)), sort_keys=True))
        return
    if args.extract_structured_result:
        result = extract_structured_result(_read(args.input_file))
        if result is None:
            print(json.dumps({"status": "MISSING_TERMINAL_STRUCTURED_RESULT"}, sort_keys=True))
        else:
            print(json.dumps({"status": "TERMINAL_STRUCTURED_RESULT", "structured_result": result}, sort_keys=True))
        return
    parser.error("one projection operation is required")


if __name__ == "__main__":
    main()
