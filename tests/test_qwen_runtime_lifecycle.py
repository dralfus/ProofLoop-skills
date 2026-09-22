from __future__ import annotations

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
        "session_id": "session-1",
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
        cases = (
            (make_observation(turns=20), "MAX_SESSION_TURNS_EXHAUSTED"),
            (make_observation(wall_time_seconds=1800), "MAX_WALL_TIME_EXHAUSTED"),
            (make_observation(loop_detected=True), "LOOP_DETECTED"),
        )
        for observation, reason in cases:
            with self.subTest(reason=reason):
                result = self.decide(self.base_payload(observation=observation))
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

    def test_continuation_requires_new_receipt_and_reproducible_evidence(self) -> None:
        stopped = self.decide(self.base_payload(observation=make_observation(loop_detected=True)))
        terminal_ledger = stopped["ledger"]
        reused = self.decide(
            self.base_payload(
                ledger=terminal_ledger,
                ledger_anchor=stopped["ledger_anchor"],
                observation=make_observation(continuation=True, fresh_evidence_id="evidence-2"),
            )
        )
        self.assertEqual(reused, {"status": "BLOCKED_CAPABILITY", "reason": "FRESH_SESSION_REQUIRED", "role_dispatch": False})

        fresh = self.decide(
            self.base_payload(
                receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                ledger=terminal_ledger,
                ledger_anchor=stopped["ledger_anchor"],
                observation=make_observation(continuation=True, fresh_evidence_id="evidence-2"),
            )
        )
        self.assertEqual(fresh["status"], "QWEN_RUNTIME_GUARD_READY")
        self.assertTrue(fresh["role_dispatch"])
        self.assertEqual(fresh["ledger"][-1]["event"], "runtime_observation")

        next_observation = self.decide(
            self.base_payload(
                receipt=make_receipt(launch_id="b" * 32, issued_at_utc="2026-09-20T12:00:30.000Z"),
                ledger=fresh["ledger"],
                ledger_anchor=fresh["ledger_anchor"],
                observation=make_observation(session_id="session-2"),
            )
        )
        self.assertEqual(next_observation["status"], "QWEN_RUNTIME_GUARD_READY")

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
