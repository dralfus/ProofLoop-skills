from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_plugin.py"
FORBIDDEN_RECON_FIELD = "continuation"


def make_receipt(
    *,
    launch_id: str = "a" * 32,
    issued_at_utc: str = "2026-09-20T12:00:00.000Z",
    limits: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "receipt_type": "QWEN_SESSION_GUARD",
        "receipt_version": 1,
        "launch_id": launch_id,
        "issued_at_utc": issued_at_utc,
        "mode": "protocol",
        "limits": limits
        or {
            "max_session_turns": 20,
            "max_tool_calls": 20,
            "max_wall_time": "30m",
            "max_subagent_depth": 1,
        },
        "loop_detection": True,
        "extension_available": True,
    }


def make_observation(**overrides: object) -> dict[str, object]:
    observation: dict[str, object] = {
        "session_id": hashlib.sha256(b"session-1").hexdigest(),
        "turns": 1,
        "tool_calls": 1,
        "wall_time_seconds": 1,
        "loop_detected": False,
        "tool_fingerprint": "fingerprint-a",
        "reproducible_evidence": True,
        "continuation": False,
    }
    observation.update(overrides)
    return observation


def make_terminal_evidence(
    observation: dict[str, object], *, launch_id: str = "a" * 32,
    terminal_reason: str = "HOST_TOOL_LIMIT",
) -> dict[str, object]:
    session_hash = str(observation["session_id"])
    return {
        "schema_version": "proofloop.qwen-terminal-receipt.v1",
        "status": "COMPLETE",
        "reason": "COMPLETE",
        "launch_id": launch_id,
        "session_id_hash": session_hash,
        "terminal_reason": terminal_reason,
        "terminal_source": "HOST",
        "process_exit_code": 0,
        "event_coverage": "COMPLETE",
        "turns": observation["turns"],
        "tool_calls": observation["tool_calls"],
        "wall_time_seconds": observation["wall_time_seconds"],
        "loop_status": "HOST_CLEAR",
        "loop_detector_version": "exact_tool_interaction_cycle_v1",
        "budget_stop": True,
    }


def make_recon_receipt(
    *,
    launch_id: str = "b" * 32,
    ledger_id: str = "d" * 32,
    session_id: str = "c" * 32,
    fresh_evidence_id: str = "e" * 32,
    issued_at_utc: str = "2026-09-20T12:00:00.000Z",
) -> dict[str, object]:
    return {
        "receipt_type": "QWEN_RECON_GUARD",
        "receipt_version": 1,
        "launch_id": launch_id,
        "ledger_id": ledger_id,
        "session_id": session_id,
        "fresh_evidence_id": fresh_evidence_id,
        "issued_at_utc": issued_at_utc,
        "mode": "recon",
        "limits": {
            "max_session_turns": 3,
            "max_tool_calls": 6,
            "max_wall_time": "5m",
            "max_subagent_depth": 1,
        },
        "loop_detection": True,
        "extension_available": True,
        "read_only": True,
        "role_dispatch": False,
        "subagent_dispatch": False,
        "acceptance": False,
        "structured_output": True,
        "worktree_clean": True,
        "fixed_point": "a" * 40,
    }


def make_recon_observation(**overrides: object) -> dict[str, object]:
    observation: dict[str, object] = {
        "session_id": "c" * 32,
        "turns": 1,
        "tool_calls": 1,
        "wall_time_seconds": 1,
        "loop_detected": False,
        "tool_fingerprint": "recon-fingerprint-a",
        "reproducible_evidence": True,
        "structured_output_valid": True,
        "writes": False,
        "implementation": False,
        "role_dispatch": False,
        "subagent_dispatch": False,
        "acceptance": False,
    }
    observation.update(overrides)
    return observation


class QwenRuntimeLifecycleTest(unittest.TestCase):
    def decide(self, payload: dict[str, object]) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--qwen-runtime-guard", json.dumps(payload)],
            check=False,
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def base_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "operation": "runtime_observation",
            "now_utc": "2026-09-20T12:01:00.000Z",
            "max_receipt_age_seconds": 300,
            "receipt": make_receipt(),
            "ledger": [],
            "ledger_anchor": {"ledger_id": "a" * 32, "sequence": 0, "head_hash": "GENESIS"},
            "observation": make_observation(),
        }
        payload.update(overrides)
        return payload

    def checkpoint(self, **overrides: object) -> dict[str, object]:
        fields: dict[str, object] = {
            "prior_launch_id": "a" * 32,
            "task_fingerprint": "1" * 64,
            "scope_fingerprint": "2" * 64,
            "baseline_commit": "3" * 40,
            "diff_fingerprint": "4" * 64,
            "progress_ledger_fingerprint": "5" * 64,
            "progress_sequence": 1,
            "progress_evidence_id": "6" * 32,
            "progress_kind": "LOCAL_GREEN",
            "next_closure_fingerprint": "7" * 64,
        }
        fields.update(overrides)
        canonical = json.dumps(fields, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return {"checkpoint_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest(), **fields}

    def rehash_ledger(self, ledger: list[dict[str, object]]) -> dict[str, object]:
        previous_hash = "GENESIS"
        for entry in ledger:
            entry["prev_hash"] = previous_hash
            unsigned = {key: value for key, value in entry.items() if key != "event_hash"}
            canonical = json.dumps(unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            entry["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            previous_hash = entry["event_hash"]
        return {"ledger_id": ledger[0]["ledger_id"], "sequence": len(ledger), "head_hash": previous_hash}

    def budget_stop(self, reason: str = "HOST_TOOL_LIMIT") -> dict[str, object]:
        observation = make_observation(
            turns=1,
            tool_calls=20 if reason == "HOST_TOOL_LIMIT" else 1,
            wall_time_seconds=1800 if reason == "HOST_WALL_LIMIT" else 1,
            task_fingerprint="1" * 64,
            scope_fingerprint="2" * 64,
            baseline_commit="3" * 40,
            checkpoint=self.checkpoint(),
        )
        return self.decide(self.base_payload(
            observation=observation,
            terminal_evidence=make_terminal_evidence(observation, terminal_reason=reason),
        ))

    def continue_from(self, stopped: dict[str, object], **overrides: object) -> dict[str, object]:
        checkpoint_entry = stopped["ledger"][-2]
        observation = make_observation(
            session_id="session-2",
            continuation=True,
            fresh_evidence_id="8" * 32,
            task_fingerprint=checkpoint_entry.get("task_fingerprint", "1" * 64),
            scope_fingerprint=checkpoint_entry.get("scope_fingerprint", "2" * 64),
            baseline_commit=checkpoint_entry.get("baseline_commit", "3" * 40),
            checkpoint_id=checkpoint_entry.get("checkpoint_id", self.checkpoint()["checkpoint_id"]),
        )
        observation.update(overrides)
        return self.decide(
            self.base_payload(
                receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                ledger=stopped["ledger"],
                ledger_anchor=stopped["ledger_anchor"],
                observation=observation,
            )
        )

    def test_gate_blocks_missing_stale_and_mismatched_receipts_before_dispatch(self) -> None:
        cases = (
            (None, "RECEIPT_MISSING"),
            (make_receipt(issued_at_utc="2026-09-20T11:54:00.000Z"), "RECEIPT_STALE"),
            (
                make_receipt(limits={"max_session_turns": 20, "max_tool_calls": 19, "max_wall_time": "30m", "max_subagent_depth": 1}),
                "RECEIPT_MISMATCHED",
            ),
        )
        for receipt, reason in cases:
            with self.subTest(reason=reason):
                result = self.decide(self.base_payload(receipt=receipt))
                self.assertEqual(result, {"status": "BLOCKED_CAPABILITY", "reason": reason, "role_dispatch": False})

    def test_gate_stops_budget_loop_and_repeated_fingerprint_without_new_role_launch(self) -> None:
        host_cases = (
            (make_observation(tool_calls=20), "HOST_TOOL_LIMIT"),
            (make_observation(wall_time_seconds=1800), "HOST_WALL_LIMIT"),
        )
        cases = [(observation, reason, make_terminal_evidence(observation, terminal_reason=reason))
                 for observation, reason in host_cases]
        loop_observation = make_observation(loop_detected=True)
        cases.append((loop_observation, "LOOP_DETECTED", None))
        for observation, reason, terminal_evidence in cases:
            with self.subTest(reason=reason):
                payload = {"observation": observation}
                if terminal_evidence is not None:
                    payload["terminal_evidence"] = terminal_evidence
                result = self.decide(self.base_payload(**payload))
                self.assertEqual(result["status"], "QWEN_RUNTIME_GUARD_STOP")
                self.assertEqual(result["reason"], reason)
                self.assertFalse(result["role_dispatch"])
                self.assertEqual(result["ledger"][-1]["event"], "terminal")

        prior = self.decide(self.base_payload())
        repeated = self.decide(
            self.base_payload(
                ledger=prior["ledger"],
                ledger_anchor=prior["ledger_anchor"],
                observation=make_observation(),
            )
        )
        self.assertEqual(repeated["status"], "QWEN_RUNTIME_GUARD_STOP")
        self.assertEqual(repeated["reason"], "REPEATED_TOOL_FINGERPRINT")
        self.assertFalse(repeated["role_dispatch"])

    def test_counters_alone_never_infer_host_owned_budget_stop(self) -> None:
        for observation in (
            make_observation(turns=20),
            make_observation(tool_calls=20),
            make_observation(wall_time_seconds=1800),
        ):
            with self.subTest(observation=observation):
                result = self.decide(self.base_payload(observation=observation))
                self.assertEqual(result["status"], "QWEN_RUNTIME_GUARD_READY")
                self.assertTrue(result["role_dispatch"])
                self.assertNotEqual(result["ledger"][-1].get("event"), "terminal")

    def test_host_budget_terminal_requires_complete_matching_receipt(self) -> None:
        observation = make_observation(tool_calls=20)
        valid = make_terminal_evidence(observation)
        invalid_receipts = (
            {**valid, "status": "BLOCKED"},
            {**valid, "launch_id": "b" * 32},
            {**valid, "session_id_hash": "f" * 64},
            {**valid, "terminal_source": "PROCESS"},
            {**valid, "event_coverage": "INCOMPLETE"},
            {**valid, "tool_calls": 19},
            {**valid, "loop_detector_version": "unknown"},
            {**valid, "budget_stop": False},
        )
        for terminal_evidence in invalid_receipts:
            with self.subTest(terminal_evidence=terminal_evidence):
                result = self.decide(self.base_payload(
                    observation=observation,
                    terminal_evidence=terminal_evidence,
                ))
                self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
                self.assertFalse(result["role_dispatch"])

    def test_normal_exit_terminal_evidence_never_authorizes_role_dispatch(self) -> None:
        observation = make_observation()
        terminal_evidence = make_terminal_evidence(observation, terminal_reason="NORMAL_EXIT")
        terminal_evidence.update(
            terminal_source="PROCESS",
            process_exit_code=0,
            budget_stop=False,
        )

        result = self.decide(self.base_payload(
            observation=observation,
            terminal_evidence=terminal_evidence,
        ))

        self.assertEqual(result["status"], "QWEN_RUNTIME_GUARD_STOP")
        self.assertEqual(result["reason"], "NORMAL_EXIT")
        self.assertFalse(result["role_dispatch"])
        self.assertEqual(result["ledger"][-1]["event"], "terminal")

    def test_loop_and_repeated_fingerprint_cannot_resume_with_fresh_evidence(self) -> None:
        stopped = self.decide(self.base_payload(observation=make_observation(loop_detected=True)))
        reused = self.continue_from(stopped)
        self.assertEqual(reused["status"], "BLOCKED_CAPABILITY")
        self.assertFalse(reused["role_dispatch"])

        first = self.decide(self.base_payload())
        repeated = self.decide(self.base_payload(ledger=first["ledger"], ledger_anchor=first["ledger_anchor"]))
        self.assertEqual(repeated["reason"], "REPEATED_TOOL_FINGERPRINT")
        blocked = self.continue_from(repeated)
        self.assertEqual(blocked["status"], "BLOCKED_CAPABILITY")
        self.assertFalse(blocked["role_dispatch"])

    def test_budget_stop_requires_valid_checkpoint_for_fresh_session(self) -> None:
        stopped = self.budget_stop()
        self.assertEqual(stopped["reason"], "HOST_TOOL_LIMIT")
        self.assertEqual([event["event"] for event in stopped["ledger"]], ["runtime_observation", "checkpoint", "terminal"])
        fresh = self.continue_from(stopped)
        self.assertEqual(fresh["status"], "QWEN_RUNTIME_GUARD_READY")
        self.assertTrue(fresh["role_dispatch"])
        self.assertEqual(fresh["ledger"][-2]["event"], "session_start")
        self.assertEqual(len(fresh["ledger"]), len(stopped["ledger"]) + 2)
        next_observation = self.decide(
            self.base_payload(
                receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                ledger=fresh["ledger"],
                ledger_anchor=fresh["ledger_anchor"],
                observation=make_observation(session_id="session-2", tool_fingerprint="fingerprint-b"),
            )
        )
        self.assertEqual(next_observation["status"], "QWEN_RUNTIME_GUARD_READY", next_observation)

    def test_budget_stop_checkpoint_validation_is_fail_closed(self) -> None:
        invalid_cases = (
            (self.checkpoint(next_closure_fingerprint=""), "missing closure"),
            (self.checkpoint(diff_fingerprint="bad"), "invalid hash"),
            (self.checkpoint(progress_sequence=0), "invalid sequence"),
            (self.checkpoint(progress_kind="IMPLEMENTED"), "invalid progress kind"),
            (self.checkpoint(progress_kind=[]), "malformed progress kind"),
            ({**self.checkpoint(), "checkpoint_id": "0" * 64}, "tampered checkpoint id"),
            (self.checkpoint(path="secret"), "raw field"),
        )
        for checkpoint, label in invalid_cases:
            with self.subTest(label=label):
                observation = make_observation(
                    turns=20,
                    task_fingerprint="1" * 64,
                    scope_fingerprint="2" * 64,
                    baseline_commit="3" * 40,
                    checkpoint=checkpoint,
                )
                result = self.decide(self.base_payload(observation=observation))
                self.assertEqual(result["status"], "BLOCKED_CAPABILITY")

    def test_continuation_requires_checkpoint_and_unchanged_task_scope_baseline(self) -> None:
        stopped = self.budget_stop()
        for overrides in (
            {"checkpoint_id": "0" * 64},
            {"task_fingerprint": "9" * 64},
            {"scope_fingerprint": "9" * 64},
            {"baseline_commit": "9" * 40},
            {"fresh_evidence_id": "6" * 32},
        ):
            with self.subTest(overrides=overrides):
                result = self.continue_from(stopped, **overrides)
                self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
                self.assertFalse(result["role_dispatch"])

    def test_budget_stop_without_checkpoint_is_not_resumable(self) -> None:
        observation = make_observation(tool_calls=20)
        stopped = self.decide(self.base_payload(
            observation=observation,
            terminal_evidence=make_terminal_evidence(observation),
        ))
        self.assertEqual(stopped["status"], "QWEN_RUNTIME_GUARD_STOP")
        blocked = self.continue_from(stopped)
        self.assertEqual(blocked["status"], "BLOCKED_CAPABILITY")
        self.assertFalse(blocked["role_dispatch"])

    def test_checkpoint_progress_identity_and_context_cannot_be_reused(self) -> None:
        first_observation = make_observation(
            tool_calls=20,
            task_fingerprint="1" * 64,
            scope_fingerprint="2" * 64,
            baseline_commit="3" * 40,
            checkpoint=self.checkpoint(progress_sequence=5),
        )
        first = self.decide(self.base_payload(
            observation=first_observation,
            terminal_evidence=make_terminal_evidence(first_observation),
        ))
        resumed = self.continue_from(first)
        cases = (
            (self.checkpoint(prior_launch_id="b" * 32, progress_sequence=5), "sequence reuse"),
            (self.checkpoint(prior_launch_id="b" * 32, progress_sequence=6), "evidence reuse"),
            (self.checkpoint(prior_launch_id="b" * 32, progress_sequence=6, task_fingerprint="9" * 64), "task drift"),
        )
        for checkpoint, label in cases:
            with self.subTest(label=label):
                observation = make_observation(
                    turns=20,
                    tool_fingerprint=f"next-{label}",
                    task_fingerprint="1" * 64,
                    scope_fingerprint="2" * 64,
                    baseline_commit="3" * 40,
                    checkpoint=checkpoint,
                )
                result = self.decide(
                    self.base_payload(
                        receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                        ledger=resumed["ledger"],
                        ledger_anchor=resumed["ledger_anchor"],
                        observation=observation,
                    )
                )
                self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
                self.assertFalse(result["role_dispatch"])

    def test_checkpoint_ledger_rejects_unknown_raw_fields_even_with_valid_hash_chain(self) -> None:
        stopped = self.budget_stop()
        ledger = json.loads(json.dumps(stopped["ledger"]))
        ledger[1]["diff_text"] = "raw diff content"
        anchor = self.rehash_ledger(ledger)
        result = self.decide(
            self.base_payload(
                receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                ledger=ledger,
                ledger_anchor=anchor,
                observation=make_observation(
                    continuation=True,
                    fresh_evidence_id="8" * 32,
                    task_fingerprint="1" * 64,
                    scope_fingerprint="2" * 64,
                    baseline_commit="3" * 40,
                    checkpoint_id=ledger[1]["checkpoint_id"],
                ),
            )
        )
        self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
        self.assertEqual(result["reason"], "RUNTIME_LEDGER_INVALID")
        self.assertFalse(result["role_dispatch"])

    def test_runtime_ledger_event_types_reject_unknown_fields_even_with_valid_hash_chain(self) -> None:
        first = self.decide(self.base_payload())
        budget_stopped = self.budget_stop()
        resumed = self.continue_from(budget_stopped)
        cases = (
            (first, 0, self.base_payload),
            (
                budget_stopped,
                len(budget_stopped["ledger"]) - 1,
                lambda **kwargs: self.base_payload(
                    receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                    observation=make_observation(
                        continuation=True,
                        fresh_evidence_id="8" * 32,
                        task_fingerprint="1" * 64,
                        scope_fingerprint="2" * 64,
                        baseline_commit="3" * 40,
                        checkpoint_id=budget_stopped["ledger"][1]["checkpoint_id"],
                    ),
                    **kwargs,
                ),
            ),
            (
                resumed,
                3,
                lambda **kwargs: self.base_payload(
                    receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                    observation=make_observation(tool_fingerprint="new-work"),
                    **kwargs,
                ),
            ),
        )
        for decision, index, payload_factory in cases:
            with self.subTest(event=decision["ledger"][index]["event"]):
                ledger = json.loads(json.dumps(decision["ledger"]))
                ledger[index]["diff_text"] = "raw content"
                anchor = self.rehash_ledger(ledger)
                result = self.decide(payload_factory(ledger=ledger, ledger_anchor=anchor))
                self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
                self.assertEqual(result["reason"], "RUNTIME_LEDGER_INVALID")

    def test_gate_rejects_tampered_terminal_and_ledger_prefix(self) -> None:
        stopped = self.decide(self.base_payload(observation=make_observation(loop_detected=True)))
        missing_terminal_identity = [dict(entry) for entry in stopped["ledger"]]
        del missing_terminal_identity[-1]["launch_id"]
        result = self.decide(
            self.base_payload(
                ledger=missing_terminal_identity,
                ledger_anchor=stopped["ledger_anchor"],
            )
        )
        self.assertEqual(result, {"status": "BLOCKED_CAPABILITY", "reason": "RUNTIME_LEDGER_INVALID", "role_dispatch": False})

        deleted_prefix = stopped["ledger"][:-1]
        result = self.decide(
            self.base_payload(
                ledger=deleted_prefix,
                ledger_anchor=stopped["ledger_anchor"],
            )
        )
        self.assertEqual(result, {"status": "BLOCKED_CAPABILITY", "reason": "RUNTIME_LEDGER_ANCHOR_MISMATCH", "role_dispatch": False})

        replaced_prefix = [dict(entry) for entry in stopped["ledger"]]
        replaced_prefix[0]["tool_fingerprint"] = "replacement"
        result = self.decide(
            self.base_payload(
                ledger=replaced_prefix,
                ledger_anchor=stopped["ledger_anchor"],
            )
        )
        self.assertEqual(result, {"status": "BLOCKED_CAPABILITY", "reason": "RUNTIME_LEDGER_INVALID", "role_dispatch": False})

    def recon_decide(self, payload: dict[str, object]) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--qwen-recon-guard", json.dumps(payload)],
            check=False,
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def recon_payload(self, **overrides: object) -> dict[str, object]:
        receipt = make_recon_receipt()
        payload: dict[str, object] = {
            "operation": "recon_observation",
            "now_utc": "2026-09-20T12:01:00.000Z",
            "max_receipt_age_seconds": 300,
            "receipt": receipt,
            "ledger": [],
            "ledger_anchor": {"ledger_id": receipt["ledger_id"], "sequence": 0, "head_hash": "GENESIS"},
            "observation": make_recon_observation(),
            "used_fresh_evidence_ids": [],
        }
        payload.update(overrides)
        return payload

    def assert_recon_blocked_without_ledger_append(
        self, result: dict[str, object], reason: str
    ) -> None:
        self.assertEqual(
            result,
            {
                "status": "BLOCKED_CAPABILITY",
                "reason": reason,
                "role_dispatch": False,
                "subagent_dispatch": False,
                "acceptance": False,
            },
        )
        self.assertNotIn("ledger", result)

    def test_recon_active_identity_checks_have_one_source_copy_each(self) -> None:
        source = VALIDATOR.read_text(encoding="utf-8")
        self.assertEqual(
            source.count(
                'if prior_observation.get("launch_id") != receipt["launch_id"]:'
            ),
            1,
        )
        self.assertEqual(
            source.count(
                'if prior_observation.get("session_id") != receipt["session_id"]:'
            ),
            1,
        )

    def test_recon_guard_ready_never_dispatches_role_and_requires_structured_read_only_output(self) -> None:
        result = self.recon_decide(self.recon_payload())
        self.assertEqual(result["status"], "QWEN_RECON_READY")
        self.assertFalse(result["role_dispatch"])
        self.assertEqual(result["ledger"][-1]["event"], "recon_observation")

        for field, value, reason in (
            ("writes", True, "RECON_WRITE_VIOLATION"),
            ("implementation", True, "RECON_IMPLEMENTATION_VIOLATION"),
            ("subagent_dispatch", True, "RECON_SUBAGENT_VIOLATION"),
            ("acceptance", True, "RECON_ACCEPTANCE_VIOLATION"),
            ("structured_output_valid", False, "STRUCTURED_OUTPUT_INVALID"),
        ):
            with self.subTest(field=field):
                result = self.recon_decide(self.recon_payload(observation=make_recon_observation(**{field: value})))
                self.assertEqual(
                    result,
                    {
                        "status": "QWEN_UNUSABLE",
                        "reason": reason,
                        "role_dispatch": False,
                        "subagent_dispatch": False,
                        "acceptance": False,
                    },
                )

    def test_recon_guard_stops_budget_loop_and_fingerprint(self) -> None:
        cases = (
            (make_recon_observation(turns=3), "MAX_SESSION_TURNS_EXHAUSTED"),
            (make_recon_observation(tool_calls=6), "MAX_TOOL_CALLS_EXHAUSTED"),
            (make_recon_observation(wall_time_seconds=300), "MAX_WALL_TIME_EXHAUSTED"),
            (make_recon_observation(loop_detected=True), "LOOP_DETECTED"),
        )
        for observation, reason in cases:
            with self.subTest(reason=reason):
                result = self.recon_decide(self.recon_payload(observation=observation))
                self.assertEqual(result["status"], "QWEN_RUNTIME_GUARD_STOP")
                self.assertEqual(result["reason"], reason)
                self.assertFalse(result["role_dispatch"])
                self.assertEqual(result["ledger"][-1]["event"], "terminal")

        first = self.recon_decide(self.recon_payload())
        repeated = self.recon_decide(
            self.recon_payload(
                ledger=first["ledger"],
                ledger_anchor=first["ledger_anchor"],
            )
        )
        self.assertEqual(repeated["status"], "QWEN_RUNTIME_GUARD_STOP")
        self.assertEqual(repeated["reason"], "REPEATED_TOOL_FINGERPRINT")
        self.assertFalse(repeated["role_dispatch"])

    def test_recon_new_launch_cannot_attach_active_ledger(self) -> None:
        first = self.recon_decide(self.recon_payload())
        self.assertEqual(first["status"], "QWEN_RECON_READY")
        result = self.recon_decide(
            self.recon_payload(
                receipt=make_recon_receipt(
                    launch_id="f" * 32,
                    session_id="a" * 32,
                    ledger_id="9" * 32,
                    fresh_evidence_id="9" * 32,
                ),
                ledger=first["ledger"],
                ledger_anchor=first["ledger_anchor"],
                observation=make_recon_observation(session_id="a" * 32),
            )
        )
        self.assert_recon_blocked_without_ledger_append(
            result, "RECON_ACTIVE_LEDGER_LAUNCH_MISMATCH"
        )

    def test_recon_active_session_rejects_session_and_ledger_identity_mismatch(self) -> None:
        first = self.recon_decide(self.recon_payload())

        session_mismatch = self.recon_decide(
            self.recon_payload(
                receipt=make_recon_receipt(session_id="f" * 32),
                ledger=first["ledger"],
                ledger_anchor=first["ledger_anchor"],
                observation=make_recon_observation(session_id="f" * 32),
            )
        )
        self.assert_recon_blocked_without_ledger_append(
            session_mismatch, "RECON_ACTIVE_LEDGER_SESSION_MISMATCH"
        )

        ledger_mismatch = self.recon_decide(
            self.recon_payload(
                receipt=make_recon_receipt(ledger_id="f" * 32),
                ledger=first["ledger"],
                ledger_anchor=first["ledger_anchor"],
                observation=make_recon_observation(),
            )
        )
        self.assert_recon_blocked_without_ledger_append(
            ledger_mismatch, "RECON_RECEIPT_LEDGER_MISMATCH"
        )

    def test_recon_terminal_ledger_is_closed(self) -> None:
        stopped = self.recon_decide(
            self.recon_payload(observation=make_recon_observation(loop_detected=True))
        )
        self.assertEqual(stopped["status"], "QWEN_RUNTIME_GUARD_STOP")
        for receipt in (
            make_recon_receipt(),
            make_recon_receipt(
                launch_id="f" * 32,
                session_id="a" * 32,
                ledger_id="9" * 32,
                fresh_evidence_id="8" * 32,
            ),
        ):
            with self.subTest(launch_id=receipt["launch_id"]):
                result = self.recon_decide(
                    self.recon_payload(
                        receipt=receipt,
                        ledger=stopped["ledger"],
                        ledger_anchor=stopped["ledger_anchor"],
                        observation=make_recon_observation(session_id=receipt["session_id"]),
                    )
                )
                self.assertEqual(result["reason"], "RECON_TERMINAL_LEDGER_CLOSED")
                self.assertFalse(result["role_dispatch"])

    def test_recon_fresh_session_requires_genesis_and_evidence_identity(self) -> None:
        receipt = make_recon_receipt(
            launch_id="f" * 32,
            session_id="a" * 32,
            ledger_id="9" * 32,
            fresh_evidence_id="8" * 32,
        )
        result = self.recon_decide(
            self.recon_payload(
                receipt=receipt,
                ledger=[],
                ledger_anchor={
                    "ledger_id": "9" * 32,
                    "sequence": 0,
                    "head_hash": "GENESIS",
                },
                observation=make_recon_observation(session_id="a" * 32),
            )
        )
        self.assertEqual(result["status"], "QWEN_RECON_READY")

        missing = dict(receipt)
        missing["fresh_evidence_id"] = ""
        blocked = self.recon_decide(self.recon_payload(receipt=missing))
        self.assertEqual(blocked["status"], "BLOCKED_CAPABILITY")

        with_forbidden_field = make_recon_observation()
        with_forbidden_field[FORBIDDEN_RECON_FIELD] = False
        blocked = self.recon_decide(self.recon_payload(observation=with_forbidden_field))
        self.assertEqual(blocked["status"], "BLOCKED_CAPABILITY")

        reused = self.recon_decide(
            self.recon_payload(
                receipt=receipt,
                ledger_anchor={"ledger_id": receipt["ledger_id"], "sequence": 0, "head_hash": "GENESIS"},
                observation=make_recon_observation(session_id=receipt["session_id"]),
                used_fresh_evidence_ids=[receipt["fresh_evidence_id"]],
            )
        )
        self.assertEqual(reused["reason"], "RECON_FRESH_EVIDENCE_REUSED")

        unavailable = self.recon_payload()
        del unavailable["used_fresh_evidence_ids"]
        blocked = self.recon_decide(unavailable)
        self.assertEqual(blocked["reason"], "RECON_EVIDENCE_REGISTRY_UNAVAILABLE")

    def test_recon_same_session_append_requires_exact_receipt_identity(self) -> None:
        first = self.recon_decide(self.recon_payload())
        appended = self.recon_decide(
            self.recon_payload(
                ledger=first["ledger"],
                ledger_anchor=first["ledger_anchor"],
                used_fresh_evidence_ids=["e" * 32],
                observation=make_recon_observation(tool_fingerprint="recon-fingerprint-b"),
            )
        )
        self.assertEqual(appended["status"], "QWEN_RECON_READY")

        receipt = make_recon_receipt(fresh_evidence_id="8" * 32)
        blocked = self.recon_decide(
            self.recon_payload(
                receipt=receipt,
                ledger=first["ledger"],
                ledger_anchor=first["ledger_anchor"],
                used_fresh_evidence_ids=["e" * 32, "8" * 32],
            )
        )
        self.assertEqual(blocked["reason"], "RECON_RECEIPT_LEDGER_MISMATCH")

if __name__ == "__main__":
    unittest.main()
