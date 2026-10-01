from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from qwen_role_progress_checkpoint import (
    READ_CHECKPOINT_THRESHOLD,
    ROLE_PROGRESS_CHECKPOINT_VERSION,
    classify_tool_class,
    evaluate_progress_checkpoint,
    project_role_progress,
)

LAUNCH_ID = "b" * 32


def read_call(index: int, name: str = "read_file") -> list[dict[str, object]]:
    use_id = f"private-tool-use-{index}"
    return [
        {
            "type": "assistant",
            "message": {
                "id": f"private-message-{index}",
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": use_id, "name": name, "input": {"path": "private/file.txt"}}
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": use_id, "content": "private result", "is_error": False}],
            },
        },
    ]


def agent_dispatch(
    role: str,
    index: int,
    *,
    completed: bool = True,
    is_error: bool = False,
    tool_name: str = "Agent",
    extra_input: dict[str, object] | None = None,
) -> tuple[list[dict[str, object]], str]:
    use_id = f"private-agent-tool-{index}"
    call_input: dict[str, object] = {"subagent_type": role, "prompt": "private role prompt"}
    if extra_input:
        call_input.update(extra_input)
    events: list[dict[str, object]] = [
        {
            "type": "assistant",
            "message": {
                "id": f"private-agent-message-{index}",
                "role": "assistant",
                "content": [{"type": "tool_use", "id": use_id, "name": tool_name, "input": call_input}],
            },
        },
    ]
    if completed:
        events.append(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": use_id, "content": "private role report", "is_error": is_error}
                    ],
                },
            }
        )
    return events, use_id


def stream(*cycles: list[dict[str, object]]) -> str:
    events: list[dict[str, object]] = [
        {"type": "system", "subtype": "session_start", "session_id": "private-session-id"},
    ]
    for cycle in cycles:
        events.extend(cycle)
    events.append({"type": "system", "subtype": "session_end", "data": {"reason": "clean"}})
    return "".join(json.dumps(e, ensure_ascii=True, separators=(",", ":")) + "\n" for e in events)


def payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "checkpoint_version": ROLE_PROGRESS_CHECKPOINT_VERSION,
        "role": "finish-ticket-implementer",
        "role_completed": False,
        "read_only_tool_calls": 0,
        "mutating_tool_calls": 0,
        "unclassified_tool_calls": 0,
        "new_verified_facts": False,
        "next_step_declared": False,
        "task_scope_unchanged": True,
    }
    base.update(overrides)
    return base


class ToolClassTest(unittest.TestCase):
    def test_known_classes(self) -> None:
        self.assertEqual(classify_tool_class("read_file"), "read")
        self.assertEqual(classify_tool_class("Grep_Search"), "read")
        self.assertEqual(classify_tool_class("edit"), "mutating")
        self.assertEqual(classify_tool_class("run_shell_command"), "mutating")

    def test_unknown_or_empty_name_is_unclassified(self) -> None:
        self.assertEqual(classify_tool_class("mystery_tool"), "unclassified")
        self.assertEqual(classify_tool_class(""), "unclassified")
        self.assertEqual(classify_tool_class(None), "unclassified")


class EvaluateProgressCheckpointTest(unittest.TestCase):
    def test_reads_below_threshold_do_not_require_checkpoint(self) -> None:
        for reads in range(0, READ_CHECKPOINT_THRESHOLD):
            decision = evaluate_progress_checkpoint(payload(read_only_tool_calls=reads))
            self.assertEqual(decision["status"], "ALLOW", reads)
            self.assertEqual(decision["reason"], "BELOW_CHECKPOINT_THRESHOLD", reads)

    def test_sixth_read_of_unfinished_role_requires_checkpoint(self) -> None:
        decision = evaluate_progress_checkpoint(payload(read_only_tool_calls=READ_CHECKPOINT_THRESHOLD))
        self.assertEqual(decision["status"], "BLOCK")
        self.assertEqual(decision["reason"], "PROGRESS_CHECKPOINT_REQUIRED")

    def test_valid_checkpoint_allows_continuation_without_counter_reset(self) -> None:
        decision = evaluate_progress_checkpoint(
            payload(
                read_only_tool_calls=READ_CHECKPOINT_THRESHOLD,
                new_verified_facts=True,
                next_step_declared=True,
            )
        )
        self.assertEqual(decision["status"], "ALLOW")
        self.assertEqual(decision["reason"], "CHECKPOINT_ACCEPTED")
        self.assertEqual(decision["read_only_tool_calls"], READ_CHECKPOINT_THRESHOLD)

    def test_checkpoint_without_progress_blocks_next_action(self) -> None:
        for facts, step in ((True, False), (False, True)):
            decision = evaluate_progress_checkpoint(
                payload(read_only_tool_calls=8, new_verified_facts=facts, next_step_declared=step)
            )
            self.assertEqual(decision["status"], "BLOCK", (facts, step))
            self.assertEqual(decision["reason"], "PROGRESS_CHECKPOINT_REQUIRED", (facts, step))

    def test_scope_drift_blocks_even_with_declared_progress(self) -> None:
        decision = evaluate_progress_checkpoint(
            payload(
                read_only_tool_calls=READ_CHECKPOINT_THRESHOLD,
                new_verified_facts=True,
                next_step_declared=True,
                task_scope_unchanged=False,
            )
        )
        self.assertEqual(decision["status"], "BLOCK")
        self.assertEqual(decision["reason"], "TASK_SCOPE_CHANGED")

    def test_completed_role_below_threshold_is_not_retroactively_blocked(self) -> None:
        decision = evaluate_progress_checkpoint(
            payload(role_completed=True, read_only_tool_calls=READ_CHECKPOINT_THRESHOLD)
        )
        self.assertEqual(decision["status"], "ALLOW")
        self.assertEqual(decision["reason"], "ROLE_COMPLETED_BEFORE_THRESHOLD")

    def test_mixed_tool_pattern_gets_no_read_threshold_exception(self) -> None:
        decision = evaluate_progress_checkpoint(
            payload(read_only_tool_calls=READ_CHECKPOINT_THRESHOLD, mutating_tool_calls=7)
        )
        self.assertEqual(decision["status"], "BLOCK")
        self.assertEqual(decision["reason"], "PROGRESS_CHECKPOINT_REQUIRED")

    def test_malformed_or_non_allowlisted_input_blocks(self) -> None:
        bad_version = evaluate_progress_checkpoint(
            {**payload(), "checkpoint_version": "role_progress_checkpoint_v0"}
        )
        self.assertEqual(bad_version["reason"], "CHECKPOINT_VERSION_UNSUPPORTED")
        bad_role = evaluate_progress_checkpoint({**payload(), "role": "finish-ticket-anything"})
        self.assertEqual(bad_role["reason"], "ROLE_NOT_ALLOWLISTED")
        missing = payload()
        del missing["next_step_declared"]
        self.assertEqual(evaluate_progress_checkpoint(missing)["reason"], "CHECKPOINT_INPUT_INVALID")
        self.assertEqual(evaluate_progress_checkpoint("not-an-object")["reason"], "CHECKPOINT_INPUT_INVALID")
        string_count = evaluate_progress_checkpoint({**payload(), "read_only_tool_calls": "6"})
        self.assertEqual(string_count["reason"], "CHECKPOINT_INPUT_INVALID")

    def test_decision_id_is_deterministic_and_raw_free(self) -> None:
        first = evaluate_progress_checkpoint(payload(read_only_tool_calls=6))
        second = evaluate_progress_checkpoint(payload(read_only_tool_calls=6))
        self.assertEqual(first["decision_id"], second["decision_id"])
        serialized = json.dumps(first, sort_keys=True)
        for marker in ("private", "prompt", "S:\\", "C:\\"):
            self.assertNotIn(marker, serialized)


class ProjectRoleProgressTest(unittest.TestCase):
    def test_pending_role_counters_and_checkpoint_flag(self) -> None:
        cycles = [read_call(i) for i in range(READ_CHECKPOINT_THRESHOLD)]
        projection = project_role_progress(
            stream(*[agent_dispatch("finish-ticket-implementer", 90, completed=False)[0]], *cycles),
            expected_launch_id=LAUNCH_ID,
        )
        self.assertEqual(projection["status"], "COMPLETE")
        self.assertEqual(len(projection["roles"]), 1)
        role = projection["roles"][0]
        self.assertEqual(role["completion"], "PENDING")
        self.assertEqual(role["read_only_tool_calls"], 0)
        self.assertFalse(role["checkpoint_required"])
        self.assertEqual(projection["unattributed_tool_calls"]["read"], READ_CHECKPOINT_THRESHOLD)

    def test_completed_role_is_not_marked_checkpoint_required(self) -> None:
        events, _ = agent_dispatch("finish-ticket-reviewer", 1)
        projection = project_role_progress(stream(events), expected_launch_id=LAUNCH_ID)
        role = projection["roles"][0]
        self.assertEqual(role["completion"], "COMPLETED")
        self.assertFalse(role["checkpoint_required"])

    def test_error_completion_is_recorded(self) -> None:
        events, _ = agent_dispatch("finish-ticket-verifier", 1, is_error=True)
        projection = project_role_progress(stream(events), expected_launch_id=LAUNCH_ID)
        self.assertEqual(projection["roles"][0]["completion"], "ERROR")

    def test_fork_or_resume_dispatch_is_unclassified_not_a_role(self) -> None:
        events, _ = agent_dispatch(
            "finish-ticket-implementer", 1, extra_input={"resume_agent_id": "private-agent-id"}
        )
        projection = project_role_progress(stream(events), expected_launch_id=LAUNCH_ID)
        self.assertEqual(projection["roles"], [])
        self.assertEqual(projection["unattributed_tool_calls"]["unclassified"], 1)

    def test_unknown_agent_type_is_unclassified(self) -> None:
        events, _ = agent_dispatch("mystery-role", 1)
        projection = project_role_progress(stream(events), expected_launch_id=LAUNCH_ID)
        self.assertEqual(projection["roles"], [])
        self.assertEqual(projection["unattributed_tool_calls"]["unclassified"], 1)

    def test_malformed_stream_fails_closed_without_raw_echo(self) -> None:
        raw = stream(read_call(1)) + '{"type":"assistant","broken\n'
        projection = project_role_progress(raw, expected_launch_id=LAUNCH_ID)
        self.assertEqual(projection["status"], "BLOCKED")
        serialized = json.dumps(projection, sort_keys=True)
        for marker in ("private", "broken", "assistant"):
            self.assertNotIn(marker, serialized)

    def test_invalid_launch_id_blocks(self) -> None:
        projection = project_role_progress(stream(read_call(1)), expected_launch_id="nope")
        self.assertEqual(projection["status"], "BLOCKED")
        self.assertEqual(projection["reason"], "LAUNCH_ID_INVALID")

    def test_threshold_is_six_and_not_a_cap(self) -> None:
        self.assertEqual(READ_CHECKPOINT_THRESHOLD, 6)


class AdapterCliTest(unittest.TestCase):
    def test_project_role_progress_flag_returns_raw_free_projection(self) -> None:
        import io
        import tempfile
        from contextlib import redirect_stdout

        from qwen_runtime_adapter import main as adapter_main

        events = stream(*[agent_dispatch("finish-ticket-implementer", 90, completed=False)[0]])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(events, encoding="utf-8")
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = adapter_main(["--project-role-progress", str(path), "--launch-id", LAUNCH_ID])
        self.assertEqual(exit_code, 0)
        output = captured.getvalue()
        self.assertIn("proofloop.qwen-role-progress.v1", output)
        self.assertNotIn("private", output)


if __name__ == "__main__":
    unittest.main()
