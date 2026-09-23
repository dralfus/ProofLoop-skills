from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "scripts" / "qwen_guard_policy.py"
LAUNCHER_PATH = REPOSITORY_ROOT / "scripts" / "invoke_qwen_finish_ticket.ps1"
SPEC = importlib.util.spec_from_file_location("qwen_guard_policy", MODULE_PATH)
assert SPEC and SPEC.loader
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class QwenGuardPolicyTest(unittest.TestCase):
    def payload(self, mode: str = "protocol", **overrides: object) -> dict[str, object]:
        limits = POLICY.PROTOCOL_LIMITS if mode == "protocol" else POLICY.RECON_LIMITS
        receipt: dict[str, object] = {
            "receipt_type": "QWEN_SESSION_GUARD" if mode == "protocol" else "QWEN_RECON_GUARD",
            "receipt_version": 1,
            "launch_id": "a" * 32,
            "issued_at_utc": "2026-09-23T12:00:00.000Z",
            "mode": mode,
            "limits": dict(limits),
            "loop_detection": True,
            "extension_available": True,
        }
        worktree: dict[str, object] = {"available": True}
        if mode == "recon":
            receipt.update(
                {
                    "session_id": "b" * 32,
                    "ledger_id": "c" * 32,
                    "fresh_evidence_id": "d" * 32,
                    "read_only": True,
                    "role_dispatch": False,
                    "subagent_dispatch": False,
                    "acceptance": False,
                    "structured_output": True,
                    "worktree_clean": True,
                    "fixed_point": "e" * 40,
                }
            )
            worktree.update({"clean": True, "fixed_point": "e" * 40})
        payload: dict[str, object] = {
            "operation": "guard_preflight",
            "mode": mode,
            "now_utc": "2026-09-23T12:01:00.000Z",
            "max_receipt_age_seconds": 300,
            "settings": {
                "skipLoopDetection": False,
                "maxToolCallsPerTurn": 20,
                "maxSubagentDepth": 1,
            },
            "worktree": worktree,
            "capabilities": {"markers": list(POLICY.CAPABILITY_MARKERS[mode])},
            "receipt": receipt,
            "terminal_stop": False,
        }
        payload.update(overrides)
        return payload

    def test_protocol_and_recon_keep_distinct_budget_and_authority_contracts(self) -> None:
        protocol = POLICY.evaluate_guard_policy(self.payload("protocol"))
        recon = POLICY.evaluate_guard_policy(self.payload("recon"))

        self.assertEqual(protocol["status"], "QWEN_GUARD_READY")
        self.assertEqual(protocol["limits"], POLICY.PROTOCOL_LIMITS)
        self.assertTrue(protocol["role_dispatch"])
        self.assertTrue(protocol["subagent_dispatch"])
        self.assertFalse(protocol["read_only"])
        self.assertEqual(recon["status"], "QWEN_GUARD_READY")
        self.assertEqual(recon["limits"], POLICY.RECON_LIMITS)
        self.assertFalse(recon["role_dispatch"])
        self.assertFalse(recon["subagent_dispatch"])
        self.assertFalse(recon["acceptance"])
        self.assertTrue(recon["read_only"])

    def test_policy_blocks_unsafe_settings_and_missing_capabilities(self) -> None:
        for field, value, reason in (
            ("skipLoopDetection", True, "LOOP_DETECTION_DISABLED"),
            ("maxToolCallsPerTurn", 0, "MAX_TOOL_CALLS_INVALID"),
            ("maxSubagentDepth", 2, "MAX_SUBAGENT_DEPTH_EXCEEDED"),
        ):
            with self.subTest(field=field):
                settings = dict(self.payload()["settings"])
                settings[field] = value
                result = POLICY.evaluate_guard_policy(self.payload(settings=settings))
                self.assertEqual(result, POLICY.blocked(reason))

        markers = list(POLICY.CAPABILITY_MARKERS["recon"])
        markers.pop()
        result = POLICY.evaluate_guard_policy(
            self.payload("recon", capabilities={"markers": markers})
        )
        self.assertEqual(result, POLICY.blocked("QWEN_CLI_CAPABILITY_MISSING"))

    def test_policy_blocks_stale_receipt_dirty_worktree_and_fixed_point_drift(self) -> None:
        stale = self.payload(now_utc="2026-09-23T12:06:00.000Z")
        self.assertEqual(
            POLICY.evaluate_guard_policy(stale), POLICY.blocked("RECEIPT_STALE")
        )

        dirty = self.payload("recon", worktree={"available": True, "clean": False, "fixed_point": "e" * 40})
        self.assertEqual(
            POLICY.evaluate_guard_policy(dirty), POLICY.blocked("WORKTREE_NOT_CLEAN")
        )

        drift = self.payload("recon", worktree={"available": True, "clean": True, "fixed_point": "f" * 40})
        self.assertEqual(
            POLICY.evaluate_guard_policy(drift), POLICY.blocked("FIXED_POINT_MISMATCH")
        )

    def test_policy_stops_before_dispatch_when_terminal_stop_is_active(self) -> None:
        result = POLICY.evaluate_guard_policy(self.payload(terminal_stop=True))

        self.assertEqual(result, POLICY.terminal_stop("TERMINAL_STOP_ACTIVE"))

    def test_policy_is_raw_free_and_rejects_malformed_input(self) -> None:
        result = POLICY.evaluate_guard_policy({"operation": "guard_preflight"})

        self.assertEqual(result, POLICY.blocked("MALFORMED_GUARD_INPUT"))
        self.assertNotIn("raw", result)
        self.assertNotIn("path", result)
        self.assertNotIn("secret", result)

    def test_guarded_adapter_dispatches_only_after_ready_decision(self) -> None:
        source = LAUNCHER_PATH.read_text(encoding="utf-8")

        policy_call = source.index("$guardDecision = Invoke-QwenGuardPolicy")
        child_dispatch = source.index("& $cliCompatibilityConsumer", policy_call)
        decision_gate = source.index("if ($guardDecision.status -ne 'QWEN_GUARD_READY')", policy_call)
        self.assertLess(policy_call, decision_gate)
        self.assertLess(decision_gate, child_dispatch)


if __name__ == "__main__":
    unittest.main()
