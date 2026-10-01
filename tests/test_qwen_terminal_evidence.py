from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from qwen_terminal_evidence import project_role_lifecycle, project_terminal_receipt


def interaction_events(
    *,
    action: dict[str, object] | None = None,
    assistant_text: str = "Checking the same file again.",
    result: object = "private tool result",
    index: int = 1,
) -> list[dict[str, object]]:
    use_id = f"private-tool-use-{index}"
    blocks: list[dict[str, object]] = [
        {"type": "text", "text": assistant_text},
        {
            "type": "tool_use",
            "id": use_id,
            "name": "read_file",
            "input": action or {"path": "C:/private/project/file.txt"},
        },
    ]
    result_block: dict[str, object] = {
        "type": "tool_result",
        "tool_use_id": use_id,
        "content": result,
        "is_error": False,
    }
    return [
        {
            "type": "assistant",
            "message": {"id": f"private-message-{index}", "role": "assistant", "content": blocks},
        },
        {"type": "user", "message": {"role": "user", "content": [result_block]}},
    ]


def event_stream(
    *cycles: list[dict[str, object]],
    session_end: bool = True,
    terminal: str = "session_end",
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = [
        {"type": "system", "subtype": "session_start", "session_id": "private-session-id"},
        {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": "private prompt marker"}]},
        },
    ]
    for cycle in cycles:
        events.extend(cycle)
    if session_end and terminal == "result":
        events.append(
            {
                "type": "result",
                "subtype": "success",
                "session_id": "private-session-id",
                "is_error": False,
            }
        )
    elif session_end:
        events.append({"type": "system", "subtype": "session_end", "data": {"reason": "clean"}})
    return events


def event_jsonl(events: list[dict[str, object]]) -> str:
    return "".join(
        json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n"
        for event in events
    )


def role_call(
    role: str,
    prompt: str,
    result: str,
    index: int,
    *,
    is_error: bool = False,
    resume_agent_id: str | None = None,
    fork_turns: str | None = None,
    tool_name: str = "Agent",
) -> list[dict[str, object]]:
    call_input: dict[str, object] = {"subagent_type": role, "prompt": prompt}
    if resume_agent_id is not None:
        call_input["resume_agent_id"] = resume_agent_id
    if fork_turns is not None:
        call_input["fork_turns"] = fork_turns
    tool_id = f"private-agent-tool-{index}"
    return [
        {
            "type": "assistant",
            "message": {
                "id": f"private-agent-message-{index}",
                "role": "assistant",
                "content": [{"type": "tool_use", "id": tool_id, "name": tool_name, "input": call_input}],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": result, "is_error": is_error}],
            },
        },
    ]


def observation(
    *,
    launch_id: str = "a" * 32,
    stop_reason: str | None = None,
    session_end_seen_before_stop: bool = False,
    event_file_bytes_at_stop: int | None = None,
    event_file_closed: bool = True,
) -> dict[str, object]:
    host_stop_requested = stop_reason is not None
    return {
        "launch_id": launch_id,
        "child_started": True,
        "process_exited": True,
        "process_exit_code": 0,
        "host_stop_reason": stop_reason,
        "host_stop_requested": host_stop_requested,
        "host_interrupt_sent": host_stop_requested,
        "stop_observed_while_running": host_stop_requested,
        "session_end_seen_before_stop": session_end_seen_before_stop,
        "event_file_bytes_at_stop": event_file_bytes_at_stop,
        "event_file_closed": event_file_closed,
        "elapsed_ms": 180_000 if stop_reason == "HOST_WALL_LIMIT" else 250,
    }


def serialized(receipt: dict[str, object]) -> str:
    return json.dumps(receipt, ensure_ascii=True, sort_keys=True)


class QwenTerminalEvidenceTest(unittest.TestCase):
    def test_headless_stream_json_result_completes_terminal_and_role_projections(self) -> None:
        events = event_stream(
            role_call("finish-ticket-implementer", "private implementation prompt", "private implementation output", 1),
            role_call("finish-ticket-reviewer", "private review prompt", "private review output", 2),
            role_call("finish-ticket-verifier", "private verification prompt", "private verification output", 3),
            terminal="result",
        )

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)
        roles = project_role_lifecycle(event_jsonl(events), expected_launch_id="a" * 32)

        self.assertEqual(receipt["status"], "COMPLETE")
        self.assertEqual(receipt["event_coverage"], "COMPLETE")
        self.assertEqual(receipt["turns"], 3)
        self.assertEqual(receipt["tool_calls"], 3)
        self.assertEqual(receipt["loop_status"], "HOST_CLEAR")
        self.assertEqual(roles["status"], "COMPLETE")
        self.assertEqual([call["role"] for call in roles["role_calls"]], [
            "finish-ticket-implementer", "finish-ticket-reviewer", "finish-ticket-verifier",
        ])

    def test_headless_init_result_completes_terminal_and_role_projections(self) -> None:
        events = event_stream(
            role_call("finish-ticket-implementer", "private implementation prompt", "private implementation output", 4),
            role_call("finish-ticket-reviewer", "private review prompt", "private review output", 5),
            role_call("finish-ticket-verifier", "private verification prompt", "private verification output", 6),
            terminal="result",
        )
        events[0]["subtype"] = "init"
        for event in events:
            if event.get("type") == "assistant":
                event["message"]["content"].insert(0, {"type": "thinking", "thinking": "private reasoning block"})

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)
        roles = project_role_lifecycle(event_jsonl(events), expected_launch_id="a" * 32)

        self.assertEqual(receipt["status"], "COMPLETE")
        self.assertEqual(receipt["event_coverage"], "COMPLETE")
        self.assertEqual(receipt["turns"], 3)
        self.assertEqual(receipt["tool_calls"], 3)
        self.assertEqual(roles["status"], "COMPLETE")
        self.assertEqual(len(roles["role_calls"]), 3)
        self.assertNotIn("private reasoning block", serialized(receipt))
        self.assertNotIn("private reasoning block", serialized(roles))

    def test_thinking_blocks_do_not_change_repeated_tool_cycle_fingerprints(self) -> None:
        cycles = [interaction_events(index=index) for index in range(1, 4)]
        for index, cycle in enumerate(cycles, start=1):
            cycle[0]["message"]["content"].insert(0, {
                "type": "thinking",
                "thinking": f"private reasoning variation {index}",
            })
        events = event_stream(*cycles)

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        self.assertEqual(receipt["loop_status"], "DETECTED")
        self.assertNotIn("private reasoning variation", serialized(receipt))

    def test_headless_result_must_match_session_and_be_final(self) -> None:
        events = event_stream(terminal="result")
        events[-1]["session_id"] = "other-private-session"

        mismatched = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        events[-1]["session_id"] = "private-session-id"
        events.append({"type": "assistant", "message": {"id": "late-message", "role": "assistant", "content": []}})
        non_final = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        self.assertEqual(mismatched["status"], "BLOCKED")
        self.assertEqual(non_final["status"], "BLOCKED")

    def test_role_lifecycle_requires_completed_fresh_named_roles_in_order(self) -> None:
        events = event_stream(
            role_call("finish-ticket-implementer", "private implementation prompt", "private implementation output", 10),
            role_call("finish-ticket-reviewer", "private review prompt", "private review output", 11, tool_name="agent"),
            role_call("finish-ticket-verifier", "private verification prompt", "private verification output", 12),
        )

        projection = project_role_lifecycle(event_jsonl(events), expected_launch_id="a" * 32)

        self.assertEqual(projection["status"], "COMPLETE")
        self.assertEqual(projection["reason"], "ROLE_LIFECYCLE_COMPLETE")
        self.assertEqual(
            [call["role"] for call in projection["role_calls"]],
            ["finish-ticket-implementer", "finish-ticket-reviewer", "finish-ticket-verifier"],
        )
        self.assertTrue(all(call["fresh_named"] for call in projection["role_calls"]))
        self.assertTrue(all(call["completion"] == "COMPLETED" for call in projection["role_calls"]))
        rendered = json.dumps(projection)
        for forbidden in ("private implementation prompt", "private review output", "private verification prompt"):
            self.assertNotIn(forbidden, rendered)

    def test_role_lifecycle_blocks_unknown_and_resumed_agents_without_leaking_names(self) -> None:
        events = event_stream(
            role_call("secret-unrecognized-agent", "private prompt", "private result", 20),
            role_call("finish-ticket-implementer", "private prompt", "private result", 21),
            role_call("finish-ticket-reviewer", "private prompt", "private result", 22, resume_agent_id="private-agent-id"),
            role_call("finish-ticket-verifier", "private prompt", "private result", 23),
        )

        projection = project_role_lifecycle(event_jsonl(events), expected_launch_id="b" * 32)

        self.assertEqual(projection["status"], "BLOCKED")
        self.assertEqual(projection["reason"], "ROLE_AGENT_UNCLASSIFIED")
        self.assertEqual(projection["unclassified_agent_calls"], 1)
        self.assertFalse(projection["role_calls"][1]["fresh_named"])
        rendered = json.dumps(projection)
        for forbidden in ("secret-unrecognized-agent", "private prompt", "private result", "private-agent-id"):
            self.assertNotIn(forbidden, rendered)

    def test_role_lifecycle_blocks_failed_or_incomplete_dispatch(self) -> None:
        failed = event_stream(
            role_call("finish-ticket-implementer", "private prompt", "private result", 30, is_error=True),
            role_call("finish-ticket-reviewer", "private prompt", "private result", 31),
            role_call("finish-ticket-verifier", "private prompt", "private result", 32),
        )
        missing_verifier = event_stream(
            role_call("finish-ticket-implementer", "private prompt", "private result", 33),
            role_call("finish-ticket-reviewer", "private prompt", "private result", 34),
        )

        failed_projection = project_role_lifecycle(event_jsonl(failed), expected_launch_id="c" * 32)
        missing_projection = project_role_lifecycle(event_jsonl(missing_verifier), expected_launch_id="d" * 32)

        self.assertEqual(failed_projection["status"], "BLOCKED")
        self.assertEqual(failed_projection["reason"], "ROLE_CALL_FAILED")
        self.assertEqual(missing_projection["status"], "BLOCKED")
        self.assertEqual(missing_projection["reason"], "ROLE_CALL_MISSING")

    def test_role_lifecycle_rejects_fork_arguments(self) -> None:
        events = event_stream(
            role_call("finish-ticket-implementer", "private prompt", "private result", 40),
            role_call("finish-ticket-reviewer", "private prompt", "private result", 41, fork_turns="3"),
            role_call("finish-ticket-verifier", "private prompt", "private result", 42),
        )

        projection = project_role_lifecycle(event_jsonl(events), expected_launch_id="e" * 32)

        self.assertEqual(projection["status"], "BLOCKED")
        self.assertEqual(projection["reason"], "ROLE_NOT_FRESH_NAMED")

    def test_complete_stream_without_identical_cycle_is_host_clear(self) -> None:
        events = event_stream(
            interaction_events(assistant_text="Read the source.", result="source v1", index=1),
            interaction_events(assistant_text="Verify the changed file.", result="diff v2", index=2),
        )

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        self.assertEqual(receipt["event_coverage"], "COMPLETE")
        self.assertEqual(receipt["loop_status"], "HOST_CLEAR")
        self.assertEqual(receipt["loop_detector_version"], "exact_tool_interaction_cycle_v1")
        self.assertFalse(receipt["budget_stop"])

    def test_same_action_with_different_results_is_not_a_loop(self) -> None:
        events = event_stream(
            interaction_events(result="first read result", index=1),
            interaction_events(result="second read result", index=2),
            interaction_events(result="third read result", index=3),
        )

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        self.assertEqual(receipt["loop_status"], "HOST_CLEAR")

    def test_same_action_and_result_with_changed_assistant_text_is_not_a_loop(self) -> None:
        events = event_stream(
            interaction_events(assistant_text="Read it to confirm the path.", result="same file", index=1),
            interaction_events(assistant_text="Now verify its unchanged contents.", result="same file", index=2),
            interaction_events(assistant_text="The repeated check is intentional.", result="same file", index=3),
        )

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        self.assertEqual(receipt["loop_status"], "HOST_CLEAR")

    def test_three_identical_complete_interaction_cycles_are_detected(self) -> None:
        events = event_stream(
            interaction_events(index=1),
            interaction_events(index=2),
            interaction_events(index=3),
        )

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        self.assertEqual(receipt["loop_status"], "DETECTED")
        self.assertEqual(receipt["loop_detector_version"], "exact_tool_interaction_cycle_v1")
        self.assertFalse(receipt["budget_stop"])

    def test_two_identical_complete_cycles_are_not_enough_to_mark_a_loop(self) -> None:
        receipt = project_terminal_receipt(
            event_jsonl(event_stream(interaction_events(index=1), interaction_events(index=2))),
            observation(),
            expected_launch_id="a" * 32,
        )

        self.assertEqual(receipt["loop_status"], "HOST_CLEAR")

    def test_loop_detection_never_requests_a_process_stop(self) -> None:
        receipt = project_terminal_receipt(
            event_jsonl(
                event_stream(
                    interaction_events(index=1),
                    interaction_events(index=2),
                    interaction_events(index=3),
                )
            ),
            observation(),
            expected_launch_id="a" * 32,
        )

        self.assertEqual(receipt["loop_status"], "DETECTED")
        self.assertFalse(receipt["budget_stop"])

    def test_changed_action_breaks_identical_interaction_sequence(self) -> None:
        events = event_stream(
            interaction_events(index=1),
            interaction_events(index=2),
            interaction_events(action={"path": "C:/private/project/other.txt"}, index=3),
        )

        receipt = project_terminal_receipt(event_jsonl(events), observation(), expected_launch_id="a" * 32)

        self.assertEqual(receipt["loop_status"], "HOST_CLEAR")

    def test_missing_tool_name_or_input_yields_unknown(self) -> None:
        for missing in ("name", "input"):
            with self.subTest(missing=missing):
                cycle = interaction_events(index=1)
                use = cycle[0]["message"]["content"][1]
                del use[missing]

                receipt = project_terminal_receipt(
                    event_jsonl(event_stream(cycle)), observation(), expected_launch_id="a" * 32
                )

                self.assertEqual(receipt["loop_status"], "UNKNOWN")
                self.assertNotEqual(receipt["event_coverage"], "COMPLETE")

    def test_missing_tool_result_yields_unknown(self) -> None:
        cycle = interaction_events(index=1)[:1]

        receipt = project_terminal_receipt(
            event_jsonl(event_stream(cycle)), observation(), expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["loop_status"], "UNKNOWN")
        self.assertNotEqual(receipt["event_coverage"], "COMPLETE")

    def test_incomplete_terminal_preserves_only_raw_free_observed_counters(self) -> None:
        events = event_stream(
            role_call("finish-ticket-implementer", "private role prompt", "private role result", 1, is_error=True),
            session_end=False,
        )
        process = observation()
        process["process_exit_code"] = 1

        receipt = project_terminal_receipt(
            event_jsonl(events), process, expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertEqual(receipt["terminal_reason"], "UNKNOWN")
        self.assertEqual(
            receipt["partial_observation"],
            {
                "event_lines_observed": 4,
                "assistant_turns_observed": 1,
                "tool_dispatches_observed": 1,
                "tool_results_observed": 1,
                "tool_errors_observed": 1,
                "agent_dispatches_observed": 1,
                "terminal_result_seen": False,
            },
        )
        self.assertNotIn("private role prompt", serialized(receipt))
        self.assertNotIn("private role result", serialized(receipt))

    def test_truncated_or_malformed_jsonl_preserves_only_complete_raw_free_prefix(self) -> None:
        events = event_stream(
            role_call("finish-ticket-implementer", "private role prompt", "private role result", 1, is_error=True),
        )
        valid_stream = event_jsonl(events)
        malformed_tail = event_jsonl(events[:-1]) + '{"type":"result","private":"secret"\n'

        for raw_stream in (valid_stream[:-1], malformed_tail):
            with self.subTest(raw_stream_kind="truncated" if raw_stream == valid_stream[:-1] else "malformed"):
                receipt = project_terminal_receipt(
                    raw_stream, observation(), expected_launch_id="a" * 32
                )

                self.assertEqual(receipt["status"], "BLOCKED")
                self.assertEqual(receipt["event_coverage"], "INCOMPLETE")
                self.assertEqual(receipt["loop_status"], "UNKNOWN")
                self.assertEqual(
                    receipt["partial_observation"],
                    {
                        "event_lines_observed": 4,
                        "assistant_turns_observed": 1,
                        "tool_dispatches_observed": 1,
                        "tool_results_observed": 1,
                        "tool_errors_observed": 1,
                        "agent_dispatches_observed": 1,
                        "terminal_result_seen": False,
                    },
                )
                self.assertNotIn("private role prompt", serialized(receipt))
                self.assertNotIn("private role result", serialized(receipt))
                self.assertNotIn("secret", serialized(receipt))

    def test_duplicate_tool_ids_yield_unknown(self) -> None:
        first = interaction_events(index=1)
        second = interaction_events(index=2)
        second[0]["message"]["content"][1]["id"] = "private-tool-use-1"
        second[1]["message"]["content"][0]["tool_use_id"] = "private-tool-use-1"

        receipt = project_terminal_receipt(
            event_jsonl(event_stream(first, second)), observation(), expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["loop_status"], "UNKNOWN")
        self.assertNotEqual(receipt["event_coverage"], "COMPLETE")

    def test_unknown_block_yields_unknown_without_raw_echo(self) -> None:
        cycle = interaction_events(index=1)
        cycle[0]["message"]["content"].append({"type": "future_private_block", "value": "secret-value"})

        receipt = project_terminal_receipt(
            event_jsonl(event_stream(cycle)), observation(), expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["loop_status"], "UNKNOWN")
        self.assertNotIn("secret-value", serialized(receipt))

    def test_malformed_thinking_block_yields_unknown_without_raw_echo(self) -> None:
        cycle = interaction_events(index=1)
        cycle[0]["message"]["content"].insert(0, {"type": "thinking", "thinking": 17})

        receipt = project_terminal_receipt(
            event_jsonl(event_stream(cycle)), observation(), expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["loop_status"], "UNKNOWN")
        self.assertNotIn("17", serialized(receipt))

    def test_unterminated_final_jsonl_line_is_incomplete(self) -> None:
        raw = event_jsonl(event_stream())[:-1]

        receipt = project_terminal_receipt(raw, observation(), expected_launch_id="a" * 32)

        self.assertEqual(receipt["event_coverage"], "INCOMPLETE")
        self.assertEqual(receipt["loop_status"], "UNKNOWN")

    def test_unhashable_host_reason_fails_closed_without_exception(self) -> None:
        process = observation()
        process["host_stop_reason"] = ["unexpected"]

        receipt = project_terminal_receipt(
            event_jsonl(event_stream()), process, expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["terminal_reason"], "UNKNOWN")
        self.assertEqual(receipt["loop_status"], "UNKNOWN")

    def test_oversized_tool_result_does_not_claim_cycle_equality(self) -> None:
        huge = "x" * 65_536
        cycle = interaction_events(result=huge, index=1)

        receipt = project_terminal_receipt(
            event_jsonl(event_stream(
                cycle,
                interaction_events(result=huge, index=2),
                interaction_events(result=huge, index=3),
            )),
            observation(),
            expected_launch_id="a" * 32,
        )

        self.assertEqual(receipt["loop_status"], "UNKNOWN")

    def test_normal_exit_is_not_a_budget_stop(self) -> None:
        receipt = project_terminal_receipt(
            event_jsonl(event_stream()), observation(), expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["terminal_reason"], "NORMAL_EXIT")
        self.assertFalse(receipt["budget_stop"])

    def test_eligible_host_wall_stop_requires_host_ordering_and_complete_stream(self) -> None:
        events = event_stream()
        stop_offset = len(event_jsonl(events[:-1]).encode("utf-8"))
        receipt = project_terminal_receipt(
            event_jsonl(events),
            observation(stop_reason="HOST_WALL_LIMIT", event_file_bytes_at_stop=stop_offset),
            expected_launch_id="a" * 32,
        )

        self.assertEqual(receipt["terminal_reason"], "HOST_WALL_LIMIT")
        self.assertEqual(receipt["terminal_source"], "HOST")
        self.assertEqual(receipt["event_coverage"], "COMPLETE")
        self.assertTrue(receipt["budget_stop"])

    def test_host_budget_stop_without_post_stop_session_end_is_incomplete(self) -> None:
        receipt = project_terminal_receipt(
            event_jsonl(event_stream(session_end=False)),
            observation(
                stop_reason="HOST_WALL_LIMIT",
                event_file_bytes_at_stop=len(event_jsonl(event_stream(session_end=False)).encode("utf-8")),
            ),
            expected_launch_id="a" * 32,
        )

        self.assertEqual(receipt["event_coverage"], "INCOMPLETE")
        self.assertEqual(receipt["loop_status"], "UNKNOWN")
        self.assertFalse(receipt["budget_stop"])

    def test_session_end_seen_before_stop_is_not_host_budget_evidence(self) -> None:
        events = event_stream()
        process = observation(
            stop_reason="HOST_WALL_LIMIT",
            session_end_seen_before_stop=True,
            event_file_bytes_at_stop=len(event_jsonl(events).encode("utf-8")),
        )

        receipt = project_terminal_receipt(
            event_jsonl(events), process, expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["terminal_reason"], "UNKNOWN")
        self.assertFalse(receipt["budget_stop"])

    def test_unordered_host_stop_is_not_attributed_to_host(self) -> None:
        process = observation(stop_reason="HOST_WALL_LIMIT", event_file_bytes_at_stop=1)
        process["stop_observed_while_running"] = False

        receipt = project_terminal_receipt(
            event_jsonl(event_stream(session_end=False)), process, expected_launch_id="a" * 32
        )

        self.assertEqual(receipt["terminal_reason"], "UNKNOWN")
        self.assertFalse(receipt["budget_stop"])

    def test_host_stop_offset_inside_a_jsonl_line_is_incomplete(self) -> None:
        events = event_stream()
        raw = event_jsonl(events)
        process = observation(stop_reason="HOST_WALL_LIMIT", event_file_bytes_at_stop=3)

        receipt = project_terminal_receipt(raw, process, expected_launch_id="a" * 32)

        self.assertEqual(receipt["event_coverage"], "INCOMPLETE")
        self.assertFalse(receipt["budget_stop"])

    def test_raw_event_values_never_appear_in_receipt(self) -> None:
        events = event_jsonl(event_stream(interaction_events(index=1)))

        receipt = project_terminal_receipt(events, observation(), expected_launch_id="a" * 32)
        rendered = serialized(receipt)

        for forbidden in (
            "private-session-id",
            "private-message-1",
            "private-tool-use-1",
            "private prompt marker",
            "C:/private/project/file.txt",
            "private tool result",
        ):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
