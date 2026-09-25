from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from qwen_terminal_evidence import project_terminal_receipt


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


def event_stream(*cycles: list[dict[str, object]], session_end: bool = True) -> list[dict[str, object]]:
    events: list[dict[str, object]] = [
        {"type": "system", "subtype": "session_start", "session_id": "private-session-id"},
        {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": "private prompt marker"}]},
        },
    ]
    for cycle in cycles:
        events.extend(cycle)
    if session_end:
        events.append({"type": "system", "subtype": "session_end", "data": {"reason": "clean"}})
    return events


def event_jsonl(events: list[dict[str, object]]) -> str:
    return "".join(
        json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n"
        for event in events
    )


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
