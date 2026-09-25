from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "scripts" / "qwen_runtime_adapter.py"
SPEC = importlib.util.spec_from_file_location("qwen_runtime_adapter", MODULE_PATH)
assert SPEC and SPEC.loader
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
GIT = os.environ.get("GIT", "git")


def canonical_hash(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def init_repo(root: Path) -> str:
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "ProofLoop Test",
        "GIT_AUTHOR_EMAIL": "proofloop@example.invalid",
        "GIT_COMMITTER_NAME": "ProofLoop Test",
        "GIT_COMMITTER_EMAIL": "proofloop@example.invalid",
    })
    subprocess.run([GIT, "init", "--quiet", str(root)], check=True, env=env)
    (root / "tickets.md").write_text("## 314. Fixture ticket\nDo the fixture task.\n", encoding="utf-8")
    (root / "scope.md").write_text("Allowed: change fixture.py only.\n", encoding="utf-8")
    (root / "fixture.py").write_text("before = True\n", encoding="utf-8")
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True, env=env)
    subprocess.run([GIT, "-C", str(root), "commit", "--quiet", "-m", "fixture"], check=True, env=env)
    return subprocess.run([GIT, "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


class QwenRuntimeAdapterTest(unittest.TestCase):
    def test_cli_requires_host_observation_before_emitting_terminal_receipt(self) -> None:
        events = [
            {"type": "system", "subtype": "session_start", "session_id": "private-session"},
            {"type": "system", "subtype": "session_end", "data": {"reason": "clean"}},
        ]
        observation = {
            "launch_id": "a" * 32,
            "child_started": True,
            "process_exited": True,
            "process_exit_code": 0,
            "host_stop_reason": None,
            "host_stop_requested": False,
            "host_interrupt_sent": False,
            "stop_observed_while_running": False,
            "session_end_seen_before_stop": False,
            "event_file_bytes_at_stop": None,
            "event_file_closed": True,
            "elapsed_ms": 1200,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            event_path = Path(temp_dir) / "events.jsonl"
            observation_path = Path(temp_dir) / "observation.json"
            event_path.write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
            observation_path.write_text(json.dumps(observation), encoding="utf-8")
            output = StringIO()

            with redirect_stdout(output):
                exit_code = ADAPTER.main([
                    "--project-events", str(event_path),
                    "--process-observation-file", str(observation_path),
                    "--launch-id", "a" * 32,
                ])

        projection = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(projection["terminal_reason"], "NORMAL_EXIT")
        self.assertEqual(projection["loop_status"], "HOST_CLEAR")
        self.assertEqual(projection["session_id_hash"], hashlib.sha256(b"private-session").hexdigest())
        self.assertNotIn("private-session", output.getvalue())

    def test_event_projection_is_raw_free_and_counts_only_allowlisted_metadata(self) -> None:
        events = [
            {"type": "system", "subtype": "session_start", "session_id": "private-session-id", "data": {"cwd": "C:/private"}},
            {"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": "secret prompt echo"}, {"type": "tool_use", "id": "tool-1", "name": "run_shell_command", "input": {"command": "private command"}}]}},
            {"type": "assistant", "message": {"id": "m2", "content": [{"type": "text", "text": "private result"}]}},
            {"type": "system", "subtype": "session_end", "data": {"reason": "prompt_input_exit"}},
        ]

        result = ADAPTER.project_qwen_events("\n".join(json.dumps(item) for item in events) + "\n", wall_time_seconds=9)

        self.assertEqual(result["status"], "QWEN_RUNTIME_EVIDENCE_PROJECTED")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["turns"], 2)
        self.assertEqual(result["wall_time_seconds"], 9)
        self.assertTrue(result["session_ended"])
        self.assertIsNone(result["terminal_reason"])
        self.assertRegex(result["session_id"], r"^[0-9a-f]{64}$")
        rendered = json.dumps(result)
        for forbidden in ("private-session-id", "private command", "private result", "secret prompt echo", "C:/private"):
            self.assertNotIn(forbidden, rendered)

    def test_unknown_or_truncated_event_stream_fails_closed_without_raw_echo(self) -> None:
        for stream in (
            '{"type":"system","subtype":"future_terminal","message":"secret"}\n',
            '{"type":"assistant","message":{"content":[{"type":"tool_use","input":{"command":"secret"}}]}',
            'not-json secret\n',
        ):
            with self.subTest(stream=stream):
                result = ADAPTER.project_qwen_events(stream, wall_time_seconds=1)
                self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
                self.assertEqual(result["reason"], "QWEN_RUNTIME_EVIDENCE_UNSUPPORTED")
                self.assertNotIn("secret", json.dumps(result))

    def test_session_end_never_counts_as_budget_stop(self) -> None:
        stream = json.dumps({"type": "system", "subtype": "session_start", "session_id": "s"}) + "\n"
        stream += json.dumps({"type": "system", "subtype": "session_end", "data": {"reason": "prompt_input_exit"}}) + "\n"

        result = ADAPTER.project_qwen_events(stream, wall_time_seconds=2)

        self.assertEqual(result["status"], "QWEN_RUNTIME_EVIDENCE_PROJECTED")
        self.assertIsNone(result["terminal_reason"])
        self.assertFalse(result["budget_stop"])

    def test_error_result_has_raw_free_terminal_classification(self) -> None:
        private_message = "HTTP 403 Forbidden for https://private.example/v1 using secret-token"
        events = [
            {"type": "system", "subtype": "session_start", "session_id": "private-session"},
            {
                "type": "result",
                "is_error": True,
                "subtype": "error_during_execution",
                "error": {"message": private_message},
            },
        ]

        result = ADAPTER.project_qwen_events("\n".join(json.dumps(item) for item in events), wall_time_seconds=3)

        self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
        self.assertEqual(result["reason"], "QWEN_JSON_ERROR_RESULT")
        self.assertEqual(result["turns"], 0)
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(result["wall_time_seconds"], 3)
        self.assertEqual(result["terminal_reason"], "QWEN_JSON_ERROR_RESULT")
        self.assertFalse(result["budget_stop"])
        self.assertEqual(result["loop_status"], "UNOBSERVED")
        self.assertRegex(result["session_id"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            result["diagnostic"],
            {
                "terminal_result": True,
                "terminal_is_error": True,
                "terminal_subtype": "error_during_execution",
                "error_message_present": True,
                "error_message_category": "auth_or_forbidden",
            },
        )
        serialized = json.dumps(result)
        for forbidden in (private_message, "private.example", "secret-token"):
            self.assertNotIn(forbidden, serialized)

    def test_valid_host_evidence_flows_through_runtime_policy_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = init_repo(root)
            (root / "fixture.py").write_text("after = True\n", encoding="utf-8")
            facts = ADAPTER.collect_host_facts(root, ticket="314", task_source="tickets.md", scope_source="scope.md")
            ledger = self.make_progress_ledger(facts)
            test_receipt = self.make_receipt(facts, ledger["events"][0], kind="test", status="GREEN")
            checkpoint = self.make_checkpoint(facts, ledger, test_receipt)
            prior = self.prior_runtime_payload(baseline, facts, checkpoint)

            request = {
                "operation": "prepare_continuation",
                "repo_root": str(root),
                "ticket": "314",
                "task_source": "tickets.md",
                "scope_source": "scope.md",
                "runtime_payload": prior,
                "progress_ledger": ledger,
                "test_receipt": test_receipt,
                "review_receipt": None,
                "continuation_context": "Complete the next measurable closure in the existing scope.",
                "prior_projection": self.prior_terminal_receipt(),
            }
            result = ADAPTER.prepare_continuation(request)

            self.assertEqual(result["status"], "QWEN_RUNTIME_GUARD_READY")
            self.assertTrue(result["role_dispatch"])
            self.assertEqual(result["ledger"][-2]["event"], "session_start")
            self.assertEqual(result["ledger"][-2]["checkpoint_id"], checkpoint["checkpoint_id"])
            self.assertEqual(result["ledger"][-1]["event"], "runtime_observation")
            self.assertEqual(len(result["ledger"]), len(prior["ledger"]) + 2)
            self.assertEqual(result["ledger"][0]["turns"], 2)
            self.assertEqual(result["ledger"][-2]["fresh_evidence_id"], "8" * 32)

            invalid_updates = (
                {"schema_version": "proofloop.qwen-terminal-receipt.v2"},
                {"launch_id": "b" * 32},
                {"terminal_source": "PROCESS"},
                {"event_coverage": "INCOMPLETE"},
                {"turns": 3},
                {"loop_status": "DETECTED"},
            )
            for update in invalid_updates:
                with self.subTest(update=update):
                    invalid_request = json.loads(json.dumps(request))
                    invalid_request["prior_projection"].update(update)
                    rejected = ADAPTER.prepare_continuation(invalid_request)
                    self.assertEqual(rejected["status"], "BLOCKED_CAPABILITY")
                    self.assertFalse(rejected["role_dispatch"])

            unbound_request = json.loads(json.dumps(request))
            unbound_request["runtime_payload"]["ledger"][-3].pop("terminal_evidence_hash")
            unbound_request["runtime_payload"]["ledger_anchor"] = self.rehash_runtime_ledger(
                unbound_request["runtime_payload"]["ledger"]
            )
            unbound = ADAPTER.prepare_continuation(unbound_request)
            self.assertEqual(unbound["status"], "BLOCKED_CAPABILITY")
            self.assertFalse(unbound["role_dispatch"])

    def test_diff_or_receipt_mismatch_blocks_before_policy_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            (root / "fixture.py").write_text("after = True\n", encoding="utf-8")
            facts = ADAPTER.collect_host_facts(root, ticket="314", task_source="tickets.md", scope_source="scope.md")
            ledger = self.make_progress_ledger(facts)
            test_receipt = self.make_receipt(facts, ledger["events"][0], kind="test", status="GREEN")
            checkpoint = self.make_checkpoint(facts, ledger, test_receipt)
            request = {
                "operation": "prepare_continuation", "repo_root": str(root), "ticket": "314",
                "task_source": "tickets.md", "scope_source": "scope.md",
                "runtime_payload": self.prior_runtime_payload(facts["baseline_commit"], facts, checkpoint),
                "progress_ledger": ledger, "test_receipt": test_receipt, "review_receipt": None,
                "continuation_context": "Complete the next measurable closure in the existing scope.",
                "prior_projection": self.prior_terminal_receipt(),
            }
            request["test_receipt"] = {**test_receipt, "diff_fingerprint": "f" * 64}

            result = ADAPTER.prepare_continuation(request)

            self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
            self.assertEqual(result["reason"], "CONTROLLER_EVIDENCE_MISMATCH")
            self.assertFalse(result["role_dispatch"])

    def test_loop_terminal_projection_cannot_reach_runtime_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = init_repo(root)
            (root / "fixture.py").write_text("after = True\n", encoding="utf-8")
            facts = ADAPTER.collect_host_facts(root, ticket="314", task_source="tickets.md", scope_source="scope.md")
            ledger = self.make_progress_ledger(facts)
            test_receipt = self.make_receipt(facts, ledger["events"][0], kind="test", status="GREEN")
            checkpoint = self.make_checkpoint(facts, ledger, test_receipt)
            runtime_payload = self.prior_runtime_payload(baseline, facts, checkpoint)
            runtime_payload["ledger"][-1]["reason"] = "LOOP_DETECTED"
            runtime_payload["ledger_anchor"] = self.rehash_runtime_ledger(runtime_payload["ledger"])
            projection = self.prior_terminal_receipt()
            projection["terminal_reason"] = "LOOP_DETECTED"
            projection["budget_stop"] = False
            projection["loop_status"] = "DETECTED"
            request = {
                "operation": "prepare_continuation", "repo_root": str(root), "ticket": "314",
                "task_source": "tickets.md", "scope_source": "scope.md", "runtime_payload": runtime_payload,
                "progress_ledger": ledger, "test_receipt": test_receipt, "review_receipt": None,
                "continuation_context": "Complete the next measurable closure in the existing scope.",
                "prior_projection": projection,
            }

            result = ADAPTER.prepare_continuation(request)

            self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
            self.assertEqual(result["reason"], "QWEN_RUNTIME_EVIDENCE_UNSUPPORTED")
            self.assertFalse(result["role_dispatch"])
            self.assertNotIn("continuation_packet", result)

    @staticmethod
    def make_progress_ledger(facts: dict[str, str]) -> dict[str, object]:
        continuation_context = "Complete the next measurable closure in the existing scope."
        event: dict[str, object] = {
            "sequence": 1,
            "kind": "LOCAL_GREEN",
            "evidence_id": "6" * 32,
            "task_fingerprint": facts["task_fingerprint"],
            "scope_fingerprint": facts["scope_fingerprint"],
            "baseline_commit": facts["baseline_commit"],
            "diff_fingerprint": facts["diff_fingerprint"],
            "next_closure_fingerprint": hashlib.sha256(continuation_context.encode("utf-8")).hexdigest(),
            "test_receipt_id": "b" * 32,
            "review_receipt_id": None,
            "prev_hash": "GENESIS",
        }
        event["event_hash"] = canonical_hash(event)
        ledger: dict[str, object] = {"schema": "proofloop.progress-ledger.v1", "ledger_id": "d" * 32, "events": [event]}
        ledger["head_hash"] = event["event_hash"]
        return ledger

    @staticmethod
    def make_receipt(facts: dict[str, str], event: dict[str, object], *, kind: str, status: str) -> dict[str, object]:
        return {
            "receipt_id": "b" * 32,
            "kind": kind,
            "status": status,
            "evidence_id": event["evidence_id"],
            "task_fingerprint": facts["task_fingerprint"],
            "scope_fingerprint": facts["scope_fingerprint"],
            "baseline_commit": facts["baseline_commit"],
            "diff_fingerprint": facts["diff_fingerprint"],
            "issued_at_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }

    @staticmethod
    def make_checkpoint(facts: dict[str, str], ledger: dict[str, object], receipt: dict[str, object]) -> dict[str, object]:
        unsigned: dict[str, object] = {
            "prior_launch_id": "a" * 32,
            "task_fingerprint": facts["task_fingerprint"],
            "scope_fingerprint": facts["scope_fingerprint"],
            "baseline_commit": facts["baseline_commit"],
            "diff_fingerprint": facts["diff_fingerprint"],
            "progress_ledger_fingerprint": canonical_hash(ledger),
            "progress_sequence": 1,
            "progress_evidence_id": "6" * 32,
            "progress_kind": "LOCAL_GREEN",
            "next_closure_fingerprint": ledger["events"][0]["next_closure_fingerprint"],
        }
        return {"checkpoint_id": canonical_hash(unsigned), **unsigned}

    @staticmethod
    def prior_runtime_payload(baseline: str, facts: dict[str, str], checkpoint: dict[str, object]) -> dict[str, object]:
        observation = {
            "session_id": "3" * 64, "turns": 2, "tool_calls": 2, "wall_time_seconds": 1800,
            "loop_detected": False, "tool_fingerprint": "c" * 64, "reproducible_evidence": True,
            "continuation": False, "task_fingerprint": facts["task_fingerprint"],
            "scope_fingerprint": facts["scope_fingerprint"], "baseline_commit": baseline,
            "checkpoint": checkpoint,
        }
        stop_payload = {
            "ticket": "314",
            "operation": "runtime_observation", "now_utc": "2026-09-24T12:01:00.000Z",
            "max_receipt_age_seconds": 300,
            "receipt": {
                "receipt_type": "QWEN_SESSION_GUARD", "receipt_version": 1, "launch_id": "a" * 32,
                "issued_at_utc": "2026-09-24T12:00:00.000Z", "mode": "protocol",
                "limits": {"max_session_turns": 20, "max_tool_calls": 20, "max_wall_time": "30m", "max_subagent_depth": 1},
                "loop_detection": True, "extension_available": True,
            },
            "ledger": [], "ledger_anchor": {"ledger_id": "a" * 32, "sequence": 0, "head_hash": "GENESIS"},
            "observation": observation,
            "terminal_evidence": QwenRuntimeAdapterTest.prior_terminal_receipt(),
        }
        stopped = ADAPTER.qwen_runtime_guard_decision(stop_payload)
        if stopped.get("status") != "QWEN_RUNTIME_GUARD_STOP":
            raise AssertionError("fixture must produce a valid budget stop")
        continuation_observation = {
            "session_id": "9" * 32, "turns": 0, "tool_calls": 0, "wall_time_seconds": 0,
            "loop_detected": False, "tool_fingerprint": "d" * 64, "reproducible_evidence": True,
            "continuation": True, "fresh_evidence_id": "8" * 32,
            "checkpoint_id": checkpoint["checkpoint_id"],
            "task_fingerprint": facts["task_fingerprint"],
            "scope_fingerprint": facts["scope_fingerprint"],
            "baseline_commit": baseline,
        }
        continuation = dict(stop_payload)
        continuation.pop("terminal_evidence")
        continuation["receipt"] = {**stop_payload["receipt"], "launch_id": "9" * 32}
        continuation["ledger"] = stopped["ledger"]
        continuation["ledger_anchor"] = stopped["ledger_anchor"]
        continuation["observation"] = continuation_observation
        return continuation

    @staticmethod
    def prior_terminal_receipt() -> dict[str, object]:
        return {
            "schema_version": "proofloop.qwen-terminal-receipt.v1",
            "status": "COMPLETE",
            "reason": "COMPLETE",
            "launch_id": "a" * 32,
            "session_id_hash": "3" * 64,
            "terminal_reason": "HOST_WALL_LIMIT",
            "terminal_source": "HOST",
            "process_exit_code": 0,
            "event_coverage": "COMPLETE",
            "turns": 2,
            "tool_calls": 2,
            "wall_time_seconds": 1800,
            "loop_status": "HOST_CLEAR",
            "loop_detector_version": "exact_tool_interaction_cycle_v1",
            "budget_stop": True,
        }

    @staticmethod
    def rehash_runtime_ledger(ledger: list[dict[str, object]]) -> dict[str, object]:
        previous_hash = "GENESIS"
        for entry in ledger:
            entry["prev_hash"] = previous_hash
            entry["event_hash"] = canonical_hash({key: value for key, value in entry.items() if key != "event_hash"})
            previous_hash = str(entry["event_hash"])
        return {"ledger_id": ledger[0]["ledger_id"], "sequence": len(ledger), "head_hash": previous_hash}


if __name__ == "__main__":
    unittest.main()
