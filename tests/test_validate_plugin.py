from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPOSITORY_ROOT / "scripts/validate_plugin.py"
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins/agentic-development-workflow"
SPEC = importlib.util.spec_from_file_location("validate_plugin", VALIDATOR)
assert SPEC and SPEC.loader
VALIDATE_PLUGIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE_PLUGIN)


class ValidatePluginTest(unittest.TestCase):
    def test_validates_discoverable_qwen_delivery_extension(self) -> None:
        VALIDATE_PLUGIN.validate_qwen_delivery_extension(REPOSITORY_ROOT)

    def test_qwen_extension_validator_rejects_embedded_canonical_lifecycle_fixture(self) -> None:
        canonical = (
            PLUGIN_ROOT / "skills" / "finish-ticket" / "references" / "task-lifecycle.md"
        ).read_text(encoding="utf-8")
        copied_fixture = (
            REPOSITORY_ROOT / "tests" / "fixtures" / "qwen-extension" / "embedded-canonical-lifecycle.md"
        )

        with self.assertRaises(AssertionError):
            VALIDATE_PLUGIN.assert_qwen_owned_file_does_not_embed_lifecycle(
                copied_fixture, canonical
            )

    def test_end_to_end_fixtures_preserve_codex_and_qwen_policies(self) -> None:
        fixtures = REPOSITORY_ROOT / "tests" / "fixtures" / "end-to-end"

        codex = json.loads((fixtures / "codex-policy-preserved.json").read_text(encoding="utf-8"))
        codex_result = self.run_policy(codex["capabilities"])
        self.assertEqual(codex_result.returncode, 0, codex_result.stderr)
        self.assertEqual(json.loads(codex_result.stdout)["status"], codex["expected"]["profile"])
        self.assertEqual(json.loads(codex_result.stdout)["budget"], codex["expected"]["budget"])

        qwen_preflight = json.loads((fixtures / "qwen-preflight.json").read_text(encoding="utf-8"))
        qwen_preflight_result = self.run_policy(qwen_preflight["capabilities"])
        self.assertEqual(qwen_preflight_result.returncode, 0, qwen_preflight_result.stderr)
        self.assertEqual(json.loads(qwen_preflight_result.stdout)["status"], qwen_preflight["expected"]["profile"])
        self.assertNotIn("numeric_repair_cap", json.loads(qwen_preflight_result.stdout))

        for name in ("qwen-converges", "qwen-terminal-non-progress", "qwen-terminal-regression"):
            with self.subTest(name=name):
                fixture = json.loads((fixtures / f"{name}.json").read_text(encoding="utf-8"))
                result = self.run_qwen_repair_payload(fixture["payload"])
                self.assertEqual(result.returncode, 0, result.stderr)
                decision = json.loads(result.stdout)
                self.assertEqual(decision["status"], fixture["expected"]["status"])
                self.assertEqual(decision["ledger"][-1]["event"], fixture["expected"]["last_event"])

        qwen_no_capability = json.loads((fixtures / "qwen-no-capability.json").read_text(encoding="utf-8"))
        qwen_no_capability_result = self.run_policy(qwen_no_capability["capabilities"])
        self.assertEqual(qwen_no_capability_result.returncode, 0, qwen_no_capability_result.stderr)
        self.assertEqual(json.loads(qwen_no_capability_result.stdout)["status"], "BLOCKED_CAPABILITY")

    def test_selects_qwen_profile_from_trusted_v0222_declaration(self) -> None:
        result = self.run_policy(
            {
                "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                "configured_model": {"id": "qwen3-coder-plus"},
                "active_model": {"id": "qwen3-coder-plus"},
                "role_model_identity_lock": True,
                "fresh_named_subagent": True,
                "implementer_continuation": True,
                "reviewer_policy": {
                    "fresh_named": True,
                    "fork": False,
                    "write": False,
                    "tool_classes": ["read", "verify"],
                },
                "verification_command": "python -m unittest",
                "observed_usage": False,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"configuration": {"model": {"id": "qwen3-coder-plus"}, "roles": {"controller": {"id": "qwen3-coder-plus"}, "implementer": {"id": "qwen3-coder-plus"}, "reviewer": {"id": "qwen3-coder-plus"}, "verifier": {"id": "qwen3-coder-plus"}}, "runtime": {"product": "qwen-code", "provider": "qwen", "version": "0.22.2"}}, "repair_policy": "QWEN_CONVERGENT", "status": "QWEN_PROFILE", "usage": "NOT_AVAILABLE"}\n',
        )

    def test_qwen_profile_blocks_a_reviewer_that_can_fork_or_write(self) -> None:
        capabilities = {
            "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
            "configured_model": {"id": "qwen3-coder-plus"},
            "active_model": {"id": "qwen3-coder-plus"},
            "role_model_identity_lock": True,
            "fresh_named_subagent": True,
            "implementer_continuation": True,
            "reviewer_policy": {
                "fresh_named": True,
                "fork": True,
                "write": True,
                "tool_classes": ["read", "verify"],
            },
            "verification_command": "python -m unittest",
            "observed_usage": True,
        }

        result = self.run_policy(capabilities)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"malformed_capabilities": ["reviewer_policy"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_qwen_profile_blocks_a_changed_active_model(self) -> None:
        capabilities = {
            "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
            "configured_model": {"id": "qwen3-coder-plus"},
            "active_model": {"id": "qwen3-coder-next"},
            "role_model_identity_lock": True,
            "fresh_named_subagent": True,
            "implementer_continuation": True,
            "reviewer_policy": {
                "fresh_named": True,
                "fork": False,
                "write": False,
                "tool_classes": ["read", "verify"],
            },
            "verification_command": "python -m unittest",
            "observed_usage": True,
        }

        result = self.run_policy(capabilities)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"malformed_capabilities": ["model_identity"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_qwen_profile_blocks_missing_dispatch_and_continuation(self) -> None:
        result = self.run_policy(
            {
                "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                "configured_model": {"id": "qwen3-coder-plus"},
                "active_model": {"id": "qwen3-coder-plus"},
                "role_model_identity_lock": True,
                "fresh_named_subagent": False,
                "implementer_continuation": False,
                "reviewer_policy": {
                    "fresh_named": True,
                    "fork": False,
                    "write": False,
                    "tool_classes": ["read", "verify"],
                },
                "verification_command": "python -m unittest",
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"missing_capabilities": ["fresh_named_subagent", "implementer_continuation"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_qwen_profile_blocks_without_a_role_identity_lock(self) -> None:
        result = self.run_policy(
            {
                "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                "configured_model": {"id": "qwen3-coder-plus"},
                "active_model": {"id": "qwen3-coder-plus"},
                "fresh_named_subagent": True,
                "implementer_continuation": True,
                "reviewer_policy": {
                    "fresh_named": True,
                    "fork": False,
                    "write": False,
                    "tool_classes": ["read", "verify"],
                },
                "verification_command": "python -m unittest",
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"missing_capabilities": ["role_model_identity_lock"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_qwen_profile_blocks_truthy_strings_for_boolean_capabilities(self) -> None:
        result = self.run_policy(
            {
                "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                "configured_model": {"id": "qwen3-coder-plus"},
                "active_model": {"id": "qwen3-coder-plus"},
                "role_model_identity_lock": "true",
                "fresh_named_subagent": "true",
                "implementer_continuation": "true",
                "reviewer_policy": {
                    "fresh_named": True,
                    "fork": False,
                    "write": False,
                    "tool_classes": ["read", "verify"],
                },
                "verification_command": "python -m unittest",
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"malformed_capabilities": ["role_model_identity_lock", "fresh_named_subagent", "implementer_continuation"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_qwen_profile_blocks_an_empty_structured_verification_command(self) -> None:
        result = self.run_policy(
            {
                "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                "configured_model": {"id": "qwen3-coder-plus"},
                "active_model": {"id": "qwen3-coder-plus"},
                "role_model_identity_lock": True,
                "fresh_named_subagent": True,
                "implementer_continuation": True,
                "reviewer_policy": {
                    "fresh_named": True,
                    "fork": False,
                    "write": False,
                    "tool_classes": ["read", "verify"],
                },
                "verification_command": {"argv": []},
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"malformed_capabilities": ["verification_command"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_qwen_profile_blocks_a_truthy_non_command_verification_value(self) -> None:
        result = self.run_policy(
            {
                "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                "configured_model": {"id": "qwen3-coder-plus"},
                "active_model": {"id": "qwen3-coder-plus"},
                "role_model_identity_lock": True,
                "fresh_named_subagent": True,
                "implementer_continuation": True,
                "reviewer_policy": {
                    "fresh_named": True,
                    "fork": False,
                    "write": False,
                    "tool_classes": ["read", "verify"],
                },
                "verification_command": True,
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"malformed_capabilities": ["verification_command"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_qwen_convergent_repair_continues_only_after_independent_progress(self) -> None:
        result = self.run_qwen_repair_fixture("converges")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "CONTINUE")
        self.assertEqual(decision["repair_policy"], "QWEN_CONVERGENT")
        self.assertNotIn("numeric_repair_cap", decision)
        self.assertEqual([entry["event"] for entry in decision["ledger"]], ["baseline", "local_attempt", "repair_candidate", "review_verdict"])
        self.assertEqual(decision["ledger"][2]["attempt_sequences"], [2])
        self.assertEqual(decision["ledger"][3]["closed_finding_fingerprints"], ["F-01"])

    def test_qwen_local_attempt_preserves_ticket_status_and_ledger(self) -> None:
        result = self.run_qwen_repair_fixture("local-attempt")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "IMPLEMENTING")
        self.assertEqual(decision["action"], "LOCAL_ATTEMPT")
        self.assertEqual([entry["event"] for entry in decision["ledger"]], ["baseline", "local_attempt"])
        self.assertEqual(decision["ledger"][-1]["finding"]["fingerprint"], "F-LOCAL")

    def test_qwen_repair_blocks_repeated_root_cause_without_new_red(self) -> None:
        result = self.run_qwen_repair_fixture("repeated-root-without-red")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "REPEATED_ROOT_CAUSE_WITHOUT_NEW_RED")
        self.assertEqual(decision["ledger"][-1]["event"], "terminal")

    def test_qwen_repair_rejects_a_historical_candidate_with_a_different_model_identity(self) -> None:
        result = self.run_qwen_repair_fixture("historical-model-identity-mismatch")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "MODEL_IDENTITY_MISMATCH")
        self.assertEqual(decision["ledger"][-1]["event"], "terminal")

    def test_qwen_repair_appends_a_terminal_for_insufficient_repair_evidence(self) -> None:
        result = self.run_qwen_repair_fixture("insufficient-repair-evidence")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INSUFFICIENT_REPAIR_EVIDENCE")
        self.assertEqual(decision["ledger"][-1]["event"], "terminal")
        self.assertEqual(decision["ledger"][-1]["reason"], "INSUFFICIENT_REPAIR_EVIDENCE")
        ledger_problem, _, _ = VALIDATE_PLUGIN.validate_qwen_ledger(
            decision["ledger"], "qwen3-coder-plus"
        )
        self.assertIsNone(ledger_problem)

    def test_qwen_repair_preserves_a_valid_historical_terminal_when_given_another_candidate(self) -> None:
        result = self.run_qwen_repair_fixture("candidate-after-terminal")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "REVIEWER_REJECTED")
        self.assertEqual([entry["event"] for entry in decision["ledger"]], ["baseline", "terminal"])
        ledger_problem, _, _ = VALIDATE_PLUGIN.validate_qwen_ledger(
            decision["ledger"], "qwen3-coder-plus"
        )
        self.assertIsNone(ledger_problem)

    def test_qwen_repair_does_not_continue_when_reviewer_closed_no_finding(self) -> None:
        result = self.run_qwen_repair_fixture("no-finding-closed")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "NO_OPEN_FINDING_CLOSED")
        self.assertEqual(decision["ledger"][-1]["reason"], "NO_OPEN_FINDING_CLOSED")

    def test_qwen_repair_blocks_empty_or_incomplete_ledger(self) -> None:
        expected = {
            "empty-ledger": "MISSING_BASELINE",
            "incomplete-baseline": "INCOMPLETE_BASELINE",
        }

        for fixture, stop_reason in expected.items():
            with self.subTest(fixture=fixture):
                result = self.run_qwen_repair_fixture(fixture)

                self.assertEqual(result.returncode, 0, result.stderr)
                decision = json.loads(result.stdout)
                self.assertEqual(decision["status"], "BLOCKED")
                self.assertEqual(decision["stop_reason"], stop_reason)

    def test_qwen_repair_blocks_an_invented_finding_closure(self) -> None:
        result = self.run_qwen_repair_fixture("invented-closure")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INVALID_FINDING_CLOSURE")
        self.assertEqual(decision["ledger"][-1]["reason"], "INVALID_FINDING_CLOSURE")

    def test_qwen_repair_allows_multiple_local_attempts_before_a_candidate(self) -> None:
        result = self.run_qwen_repair_fixture("multiple-local-attempts-then-converges")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "CONTINUE")
        self.assertEqual(len(decision["ledger"]), 6)
        self.assertEqual(decision["ledger"][4]["attempt_sequences"], [2, 3, 4])

    def test_qwen_repair_normalizes_equivalent_root_causes_before_comparison(self) -> None:
        result = self.run_qwen_repair_fixture("normalized-repeated-root")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "REPEATED_ROOT_CAUSE_WITHOUT_NEW_RED")
        self.assertEqual(decision["ledger"][2]["normalized_root_cause"], "missing-null-guard")

    def test_qwen_repair_requires_valid_prior_sequence_and_terminal_evidence(self) -> None:
        expected = {
            "invalid-prior-sequence": "INVALID_LEDGER_SEQUENCE",
            "terminal-evidence-missing": "TERMINAL_LEDGER_EVIDENCE_MISSING",
        }

        for fixture, stop_reason in expected.items():
            with self.subTest(fixture=fixture):
                result = self.run_qwen_repair_fixture(fixture)

                self.assertEqual(result.returncode, 0, result.stderr)
                decision = json.loads(result.stdout)
                self.assertEqual(decision["status"], "BLOCKED")
                self.assertEqual(decision["stop_reason"], stop_reason)

    def test_qwen_repair_rejects_a_historical_review_extra_closure(self) -> None:
        result = self.run_qwen_repair_payload(
            {
                "capabilities": self.qwen_capabilities(),
                "ledger": [
                    {
                        "event": "baseline",
                        "sequence": 1,
                        "fixed_point": "abc123",
                        "open_findings": [
                            {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                            {"fingerprint": "F-02", "type": "QUALITY_BLOCKER", "root_cause": "wrong-order"},
                        ],
                    },
                    {
                        "event": "local_attempt",
                        "sequence": 2,
                        "finding": {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                        "red_evidence": {"command": "python -m unittest tests.test_guard", "result": "RED"},
                        "hypothesis": "Guard input.",
                        "green_evidence": [{"command": "python -m unittest tests.test_guard", "result": "GREEN"}],
                    },
                    {
                        "event": "repair_candidate",
                        "sequence": 3,
                        "attempt_sequences": [2],
                        "diff": {"scope_delta": []},
                        "normalized_root_cause": "missing-guard",
                        "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                        "model": {"id": "qwen3-coder-plus"},
                        "usage": "NOT_AVAILABLE",
                    },
                    {
                        "event": "review_verdict",
                        "sequence": 4,
                        "repair_candidate_sequence": 3,
                        "fresh_named": True,
                        "fork": False,
                        "write": False,
                        "tool_classes": ["read", "verify"],
                        "spec": "PASS",
                        "code_quality": "PASS",
                        "closed_finding_fingerprints": ["F-01", "F-02"],
                        "accepted_criteria_regression": False,
                        "unapproved_scope_expansion": False,
                        "decision": "CONTINUE",
                    },
                ],
                "candidate": self.qwen_candidate("F-02", "QUALITY_BLOCKER", "wrong-order"),
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INVALID_FINDING_CLOSURE")

    def test_qwen_repair_rejects_a_historical_continue_without_attempt_evidence(self) -> None:
        result = self.run_qwen_repair_payload(
            {
                "capabilities": self.qwen_capabilities(),
                "ledger": [
                    {
                        "event": "baseline",
                        "sequence": 1,
                        "fixed_point": "abc123",
                        "open_findings": [
                            {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                            {"fingerprint": "F-02", "type": "QUALITY_BLOCKER", "root_cause": "wrong-order"},
                        ],
                    },
                    {
                        "event": "local_attempt",
                        "sequence": 2,
                        "finding": {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                        "red_evidence": {"command": "python -m unittest tests.test_guard", "result": "RED"},
                        "hypothesis": "Guard input.",
                    },
                    {"event": "repair_candidate", "sequence": 3, "attempt_sequences": [2], "diff": {"scope_delta": []}},
                    {
                        "event": "review_verdict",
                        "sequence": 4,
                        "repair_candidate_sequence": 3,
                        "fresh_named": True,
                        "fork": False,
                        "write": False,
                        "tool_classes": ["read", "verify"],
                        "spec": "PASS",
                        "code_quality": "PASS",
                        "closed_finding_fingerprints": ["F-01"],
                        "accepted_criteria_regression": False,
                        "unapproved_scope_expansion": False,
                        "decision": "CONTINUE",
                    },
                ],
                "candidate": self.qwen_candidate("F-02", "QUALITY_BLOCKER", "wrong-order"),
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INCOMPLETE_CONTINUE_EVIDENCE")

    def test_qwen_repair_rejects_a_historical_continue_without_candidate_trace_evidence(self) -> None:
        result = self.run_qwen_repair_payload(
            {
                "capabilities": self.qwen_capabilities(),
                "ledger": [
                    {
                        "event": "baseline",
                        "sequence": 1,
                        "fixed_point": "abc123",
                        "open_findings": [
                            {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                            {"fingerprint": "F-02", "type": "QUALITY_BLOCKER", "root_cause": "wrong-order"},
                        ],
                    },
                    {
                        "event": "local_attempt",
                        "sequence": 2,
                        "finding": {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                        "red_evidence": {"command": "python -m unittest tests.test_guard", "result": "RED"},
                        "hypothesis": "Guard input.",
                        "green_evidence": [{"command": "python -m unittest tests.test_guard", "result": "GREEN"}],
                    },
                    {"event": "repair_candidate", "sequence": 3, "attempt_sequences": [2], "diff": {"scope_delta": []}},
                    {
                        "event": "review_verdict",
                        "sequence": 4,
                        "repair_candidate_sequence": 3,
                        "fresh_named": True,
                        "fork": False,
                        "write": False,
                        "tool_classes": ["read", "verify"],
                        "spec": "PASS",
                        "code_quality": "PASS",
                        "closed_finding_fingerprints": ["F-01"],
                        "accepted_criteria_regression": False,
                        "unapproved_scope_expansion": False,
                        "decision": "CONTINUE",
                    },
                ],
                "candidate": self.qwen_candidate("F-02", "QUALITY_BLOCKER", "wrong-order"),
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INCOMPLETE_CONTINUE_EVIDENCE")

    def test_qwen_repair_rejects_a_forged_historical_normalized_root_cause(self) -> None:
        result = self.run_qwen_repair_fixture("forged-normalized-root-cause")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INCOMPLETE_CONTINUE_EVIDENCE")

    def test_qwen_repair_rejects_nonexistent_historical_closure(self) -> None:
        result = self.run_qwen_repair_payload(
            {
                "capabilities": self.qwen_capabilities(),
                "ledger": [
                    {
                        "event": "baseline",
                        "sequence": 1,
                        "fixed_point": "abc123",
                        "open_findings": [{"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"}],
                    },
                    {
                        "event": "local_attempt",
                        "sequence": 2,
                        "finding": {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                        "red_evidence": {"command": "python -m unittest tests.test_guard", "result": "RED"},
                        "hypothesis": "Guard input.",
                        "green_evidence": [{"command": "python -m unittest tests.test_guard", "result": "GREEN"}],
                    },
                    {
                        "event": "repair_candidate",
                        "sequence": 3,
                        "attempt_sequences": [2],
                        "diff": {"scope_delta": []},
                        "normalized_root_cause": "missing-guard",
                        "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                        "model": {"id": "qwen3-coder-plus"},
                        "usage": "NOT_AVAILABLE",
                    },
                    {
                        "event": "review_verdict",
                        "sequence": 4,
                        "repair_candidate_sequence": 3,
                        "fresh_named": True,
                        "fork": False,
                        "write": False,
                        "tool_classes": ["read", "verify"],
                        "spec": "PASS",
                        "code_quality": "PASS",
                        "closed_finding_fingerprints": ["F-01", "F-404"],
                        "accepted_criteria_regression": False,
                        "unapproved_scope_expansion": False,
                        "decision": "CONTINUE",
                    },
                ],
                "candidate": self.qwen_candidate("F-01", "SPEC_VIOLATION", "missing-guard"),
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INVALID_FINDING_CLOSURE")

    def test_qwen_repair_rejects_terminal_path_without_full_reviewer_evidence(self) -> None:
        result = self.run_qwen_repair_payload(
            {
                "capabilities": self.qwen_capabilities(),
                "ledger": [
                    {
                        "event": "baseline",
                        "sequence": 1,
                        "fixed_point": "abc123",
                        "open_findings": [{"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"}],
                    },
                    {
                        "event": "local_attempt",
                        "sequence": 2,
                        "finding": {"fingerprint": "F-01", "type": "SPEC_VIOLATION", "root_cause": "missing-guard"},
                        "red_evidence": {"command": "python -m unittest tests.test_guard", "result": "RED"},
                        "hypothesis": "Guard input.",
                        "green_evidence": [{"command": "python -m unittest tests.test_guard", "result": "GREEN"}],
                    },
                    {
                        "event": "repair_candidate",
                        "sequence": 3,
                        "attempt_sequences": [2],
                        "diff": {"scope_delta": []},
                        "normalized_root_cause": "missing-guard",
                        "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
                        "model": {"id": "qwen3-coder-plus"},
                        "usage": "NOT_AVAILABLE",
                    },
                    {
                        "event": "review_verdict",
                        "sequence": 4,
                        "repair_candidate_sequence": 3,
                        "fresh_named": True,
                        "fork": False,
                        "write": False,
                        "tool_classes": ["read", "verify"],
                        "closed_finding_fingerprints": [],
                        "decision": "BLOCKED",
                    },
                    {"event": "terminal", "sequence": 5, "status": "BLOCKED", "reason": "REVIEWER_REJECTED"},
                ],
                "candidate": self.qwen_candidate("F-01", "SPEC_VIOLATION", "missing-guard"),
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["stop_reason"], "INCOMPLETE_REVIEW_EVIDENCE")

    def test_qwen_repair_stops_for_regression_new_requirement_design_gap_and_scope(self) -> None:
        expected = {
            "regression": ("BLOCKED", "REGRESSION"),
            "new-requirement": ("BLOCKED_FOR_DESIGN", "NEW_REQUIREMENT"),
            "design-gap": ("BLOCKED_FOR_DESIGN", "DESIGN_GAP"),
            "scope-expansion": ("BLOCKED_FOR_DESIGN", "UNAPPROVED_SCOPE_EXPANSION"),
        }

        for fixture, (status, stop_reason) in expected.items():
            with self.subTest(fixture=fixture):
                result = self.run_qwen_repair_fixture(fixture)

                self.assertEqual(result.returncode, 0, result.stderr)
                decision = json.loads(result.stdout)
                self.assertEqual(decision["status"], status)
                self.assertEqual(decision["stop_reason"], stop_reason)
                self.assertEqual(len(decision["ledger"]), 5)
                self.assertEqual(decision["ledger"][-1]["reason"], stop_reason)

    def test_blocks_without_role_dispatch_or_continuation(self) -> None:
        result = self.run_policy(
            {
                "model_identity": {
                    "provider": "openai",
                    "source": "codex-runtime",
                    "models": [
                        {"id": "small-current", "tier": "efficient", "efforts": ["medium", "high"]},
                        {"id": "balanced-current", "tier": "standard", "efforts": ["medium", "high"]},
                    ],
                },
                "role_dispatch_and_continuation": False,
                "tool_policy": True,
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"missing_capabilities": ["role_dispatch_and_continuation"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_selects_codex_profile_from_arbitrary_verified_inventory(self) -> None:
        result = self.run_policy(
            {
                "model_identity": {
                    "provider": "openai",
                    "source": "codex-runtime",
                    "models": [
                        {"id": "small-current", "tier": "efficient", "efforts": ["medium", "high"]},
                        {"id": "balanced-current", "tier": "standard", "efforts": ["medium", "high"]},
                    ],
                },
                "role_dispatch_and_continuation": True,
                "tool_policy": True,
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"budget": {"critical": {"compaction": 1, "frontier": 1, "full_suite": 1, "role_agents": 4}, "ordinary": {"compaction": 0, "frontier": 0, "full_suite": 1, "role_agents": 3}}, "models": {"controller": {"degradation_reason": null, "degraded": false, "effort": "medium", "id": "balanced-current", "requested_tier": "standard", "selected_tier": "standard"}, "implementer": {"degradation_reason": null, "degraded": false, "effort": "high", "id": "small-current", "requested_tier": "efficient", "selected_tier": "efficient"}, "reviewer": {"degradation_reason": null, "degraded": false, "effort": "medium", "id": "balanced-current", "requested_tier": "standard", "selected_tier": "standard"}, "verifier": {"degradation_reason": null, "degraded": false, "effort": "medium", "id": "small-current", "requested_tier": "efficient", "selected_tier": "efficient"}}, "status": "CODEX_PROFILE"}\n',
        )

    def test_degrades_frontier_request_to_compatible_lower_tier(self) -> None:
        route = VALIDATE_PLUGIN.resolve_model_route(
            [
                {"id": "standard-v2", "tier": "standard", "efforts": ["high"]},
                {"id": "efficient-v2", "tier": "efficient", "efforts": ["high"]},
            ],
            requested_tier="frontier",
            effort="high",
        )

        self.assertEqual(
            route,
            {
                "id": "standard-v2",
                "effort": "high",
                "requested_tier": "frontier",
                "selected_tier": "standard",
                "degraded": True,
                "degradation_reason": "requested_tier_unavailable",
            },
        )

    def test_blocks_when_inventory_is_untrusted_or_no_route_supports_effort(self) -> None:
        malformed = self.run_policy(
            {
                "model_identity": {
                    "provider": "openai",
                    "source": "codex-runtime",
                    "models": [{"id": "unknown", "tier": "experimental", "efforts": ["high"]}],
                },
                "role_dispatch_and_continuation": True,
                "tool_policy": True,
                "observed_usage": True,
            }
        )
        incompatible = self.run_policy(
            {
                "model_identity": {
                    "provider": "openai",
                    "source": "codex-runtime",
                    "models": [
                        {"id": "small-current", "tier": "efficient", "efforts": ["medium"]},
                        {"id": "balanced-current", "tier": "standard", "efforts": ["medium"]},
                    ],
                },
                "role_dispatch_and_continuation": True,
                "tool_policy": True,
                "observed_usage": True,
            }
        )

        self.assertEqual(malformed.returncode, 0, malformed.stderr)
        self.assertEqual(
            malformed.stdout,
            '{"malformed_capabilities": ["model_identity"], "status": "BLOCKED_CAPABILITY"}\n',
        )
        self.assertEqual(incompatible.returncode, 0, incompatible.stderr)
        self.assertEqual(
            incompatible.stdout,
            '{"missing_capabilities": ["model_identity"], "routing_failure": {"effort": "high", "reason": "no_compatible_model_effort", "requested_tier": "efficient", "role": "implementer"}, "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_blocks_malformed_model_identity_without_traceback(self) -> None:
        result = self.run_policy(
            {
                "model_identity": ["gpt-5.6-luna"],
                "role_dispatch_and_continuation": True,
                "tool_policy": True,
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"malformed_capabilities": ["model_identity"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def test_blocks_structurally_valid_inventory_without_trusted_runtime_provenance(self) -> None:
        result = self.run_policy(
            {
                "model_identity": {
                    "provider": "openai",
                    "source": "manual-input",
                    "models": [
                        {"id": "small-current", "tier": "efficient", "efforts": ["medium", "high"]},
                        {"id": "balanced-current", "tier": "standard", "efforts": ["medium", "high"]},
                    ],
                },
                "role_dispatch_and_continuation": True,
                "tool_policy": True,
                "observed_usage": True,
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"status": "BLOCKED_CAPABILITY", "untrusted_capabilities": ["model_identity"]}\n',
        )

    def test_blocks_malformed_top_level_declaration_without_traceback(self) -> None:
        result = self.run_policy(["not", "a", "declaration"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            '{"malformed_capabilities": ["declaration"], "status": "BLOCKED_CAPABILITY"}\n',
        )

    def run_policy(self, capabilities: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--capabilities", json.dumps(capabilities)],
            capture_output=True,
            text=True,
            check=False,
        )

    def run_qwen_repair_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "qwen-repair" / f"{name}.json"
        return self.run_qwen_repair_payload(json.loads(fixture.read_text(encoding="utf-8")))

    def run_qwen_repair_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--qwen-repair", json.dumps(payload)],
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def qwen_capabilities() -> dict[str, object]:
        return {
            "runtime": {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"},
            "configured_model": {"id": "qwen3-coder-plus"},
            "active_model": {"id": "qwen3-coder-plus"},
            "role_model_identity_lock": True,
            "fresh_named_subagent": True,
            "implementer_continuation": True,
            "reviewer_policy": {"fresh_named": True, "fork": False, "write": False, "tool_classes": ["read", "verify"]},
            "verification_command": "python -m unittest",
            "observed_usage": False,
        }

    @staticmethod
    def qwen_candidate(fingerprint: str, finding_type: str, root_cause: str) -> dict[str, object]:
        return {
            "finding": {"fingerprint": fingerprint, "type": finding_type, "root_cause": root_cause},
            "red_evidence": {"command": "python -m unittest tests.test_order", "result": "RED"},
            "hypothesis": "Use stable order.",
            "diff": {"scope_delta": []},
            "green_evidence": [{"command": "python -m unittest tests.test_order", "result": "GREEN"}],
            "reviewer_verdict": {
                "fresh_named": True,
                "fork": False,
                "write": False,
                "tool_classes": ["read", "verify"],
                "spec": "PASS",
                "code_quality": "PASS",
                "closed_finding_fingerprints": [fingerprint],
                "accepted_criteria_regression": False,
                "unapproved_scope_expansion": False,
            },
        }


if __name__ == "__main__":
    unittest.main()
