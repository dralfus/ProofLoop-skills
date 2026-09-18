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
    def test_runtime_contract_includes_opaque_reject_diagnostic_gate(self) -> None:
        """Published runtime must retain the bounded raw-free diagnostic rule."""
        VALIDATE_PLUGIN.validate(PLUGIN_ROOT)

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

    def test_diagnostic_cycle_continues_when_localization_changes_under_same_symptom(self) -> None:
        result = self.run_diagnostic_cycle_fixture("continues-through-new-localization")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "DIAGNOSTIC_CYCLE_ACTIVE")
        self.assertEqual(decision["action"], "CONTINUE_DIAGNOSTICS")
        self.assertEqual(decision["consumed_experiments"], 2)
        self.assertEqual(decision["remaining_experiments"], 1)

    def test_diagnostic_cycle_stops_after_two_consecutive_equal_fingerprints(self) -> None:
        result = self.run_diagnostic_cycle_fixture("repeated-fingerprint-control-point")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "DIAGNOSTIC_CONTROL_POINT")
        self.assertEqual(decision["reason"], "REPEATED_DIAGNOSTIC_FINGERPRINT")
        self.assertEqual(decision["consumed_experiments"], 2)
        self.assertEqual(decision["remaining_experiments"], 1)

    def test_diagnostic_cycle_does_not_charge_pre_command_infrastructure_failure(self) -> None:
        result = self.run_diagnostic_cycle_fixture("pre-command-infrastructure")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "INFRASTRUCTURE_BLOCKER")
        self.assertEqual(decision["reason"], "PRE_COMMAND_INFRASTRUCTURE_FAILURE")
        self.assertEqual(decision["consumed_experiments"], 0)
        self.assertEqual(decision["remaining_experiments"], 3)

    def test_diagnostic_cycle_requires_resume_identity_to_match_permit(self) -> None:
        result = self.run_diagnostic_cycle_fixture("resume-identity-mismatch")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "DIAGNOSTIC_CONTROL_POINT")
        self.assertEqual(decision["reason"], "PERMIT_IDENTITY_MISMATCH")
        self.assertEqual(decision["consumed_experiments"], 0)
        self.assertEqual(decision["remaining_experiments"], 3)

    def test_diagnostic_cycle_blocks_incomplete_required_comparison(self) -> None:
        result = self.run_diagnostic_cycle_fixture("incomplete-comparison")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "DIAGNOSTIC_CONTROL_POINT")
        self.assertEqual(decision["reason"], "MALFORMED_SEAM_EVIDENCE")
        self.assertEqual(decision["consumed_experiments"], 0)
        self.assertEqual(decision["remaining_experiments"], 3)

    def test_diagnostic_cycle_blocks_non_append_only_hypothesis_ledger(self) -> None:
        result = self.run_diagnostic_cycle_fixture("invalid-ledger-sequence")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "DIAGNOSTIC_CONTROL_POINT")
        self.assertEqual(decision["reason"], "MALFORMED_HYPOTHESIS_LEDGER")
        self.assertEqual(decision["consumed_experiments"], 0)
        self.assertEqual(decision["remaining_experiments"], 3)

    def test_prepared_candidate_accepts_diagnostic_red_green_before_static_review(self) -> None:
        result = self.run_prepared_candidate_fixture("ready-with-diagnostic-evidence")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "PREPARED_CANDIDATE_READY")
        self.assertEqual(decision["action"], "REQUEST_VERIFIER")

    def test_prepared_candidate_requires_fresh_read_only_review(self) -> None:
        result = self.run_prepared_candidate_fixture("missing-review")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "REVIEW_REQUIRED")
        self.assertEqual(decision["reason"], "FRESH_REVIEW_MISSING")

    def test_prepared_candidate_marks_receipt_stale_after_candidate_identity_changes(self) -> None:
        result = self.run_prepared_candidate_fixture("stale-candidate")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "EVIDENCE_STALE")
        self.assertEqual(decision["reason"], "CANDIDATE_IDENTITY_CHANGED")

    def test_prepared_candidate_marks_receipt_stale_after_build_configuration_changes(self) -> None:
        result = self.run_prepared_candidate_fixture("stale-build-configuration")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "EVIDENCE_STALE")
        self.assertEqual(decision["reason"], "BUILD_CONFIGURATION_CHANGED")
    def test_execution_receipt_accepts_isolated_channel_with_observed_noninteractive_behavior(self) -> None:
        result = self.run_execution_receipt_fixture("isolated-ready")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "EXECUTION_CHANNEL_READY")

    def test_execution_receipt_rejects_side_effectful_behavior_in_isolated_channel(self) -> None:
        result = self.run_execution_receipt_fixture("isolated-side-effect")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "CHANNEL_POLICY_VIOLATION")
        self.assertEqual(decision["reason"], "OBSERVED_BEHAVIOR_MISMATCH")

    def test_execution_receipt_rejects_transitive_interactive_call_from_isolated_suite(self) -> None:
        result = self.run_execution_receipt_fixture("isolated-transitive-interactive")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "CHANNEL_POLICY_VIOLATION")
        self.assertEqual(decision["reason"], "TRANSITIVE_CHANNEL_MISMATCH")

    def test_execution_receipt_marks_pre_command_environment_failure_as_infrastructure(self) -> None:
        result = self.run_execution_receipt_fixture("pre-command-environment-failure")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "INFRASTRUCTURE_BLOCKER")
        self.assertEqual(decision["reason"], "PRE_COMMAND_ENVIRONMENT_FAILURE")
    def test_test_receipts_accept_complete_parameterized_execution(self) -> None:
        result = self.run_test_receipts_fixture("parameterized-complete")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "TEST_EVIDENCE_READY")

    def test_test_receipts_report_incomplete_evidence_when_discovered_case_did_not_execute(self) -> None:
        result = self.run_test_receipts_fixture("discovered-case-not-executed")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(decision["reason"], "DISCOVERY_EXECUTION_MISMATCH")

    def test_test_receipts_mark_pre_command_failure_as_infrastructure(self) -> None:
        result = self.run_test_receipts_fixture("pre-command-environment-failure")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "INFRASTRUCTURE_BLOCKER")
        self.assertEqual(decision["reason"], "PRE_COMMAND_ENVIRONMENT_FAILURE")
    def test_semantic_diff_accepts_complete_production_contract(self) -> None:
        result = self.run_semantic_diff_fixture("complete-production-contract")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "SEMANTIC_DIFF_READY")

    def test_semantic_diff_blocks_production_delta_labeled_test_only(self) -> None:
        result = self.run_semantic_diff_fixture("production-delta-labeled-test-only")

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "SEMANTIC_DIFF_BLOCKED")
        self.assertEqual(decision["reason"], "PRODUCTION_DELTA_LABELED_TEST_ONLY")

    def test_semantic_diff_blocks_missing_production_consumer_evidence(self) -> None:
        result = self.run_semantic_diff_fixture("missing-consumer-evidence")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason"], "MISSING_CONSUMER_EVIDENCE")

    def test_semantic_diff_blocks_missing_regression_evidence(self) -> None:
        result = self.run_semantic_diff_fixture("missing-regression-evidence")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason"], "MISSING_REGRESSION_EVIDENCE")
    def test_pass_projection_accepts_complete_raw_free_evidence(self) -> None:
        result = self.run_pass_projection_fixture("complete-pass")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS_PROJECTION_READY")

    def test_pass_projection_blocks_missing_candidate_identity(self) -> None:
        result = self.run_pass_projection_fixture("missing-identity")
        self.assertEqual(json.loads(result.stdout)["reason"], "MISSING_IDENTITY")

    def test_pass_projection_blocks_missing_artifact_reference(self) -> None:
        result = self.run_pass_projection_fixture("missing-artifact")
        self.assertEqual(json.loads(result.stdout)["reason"], "MISSING_ARTIFACT_REFERENCE")

    def test_pass_projection_blocks_sensitive_field(self) -> None:
        result = self.run_pass_projection_fixture("sensitive-field")
        self.assertEqual(json.loads(result.stdout)["reason"], "RAW_FIELD_FORBIDDEN")
    def test_scenario_fixtures_keep_terminal_state_honest(self) -> None:
        expected = {"next-defect":"NEXT_DEFECT", "infrastructure":"INFRASTRUCTURE_BLOCKER", "repeated":"DIAGNOSTIC_CONTROL_POINT", "resume":"DIAGNOSTIC_CONTROL_POINT", "document-only":"DOCUMENT_ONLY_READY", "security":"BLOCKED_FOR_DESIGN"}
        for name, status in expected.items():
            with self.subTest(name=name):
                fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "scenario" / f"{name}.json"
                result = subprocess.run([sys.executable, str(VALIDATOR), "--scenario-fixture", fixture.read_text(encoding="utf-8")], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], status)
    def test_pass_projection_rejects_nested_sensitive_field(self) -> None:
        result = self.run_pass_projection_payload({"candidate_identity":"c","execution_channel":"isolated","artifact_reference":"a","criteria":{"total":1,"passed":1,"exception_text":"secret"},"required_controls":{"cleanup":True},"evidence_status":"verified"})
        self.assertEqual(json.loads(result.stdout)["reason"], "RAW_FIELD_FORBIDDEN")

    def test_execution_receipt_accepts_project_defined_channel_with_matching_policy(self) -> None:
        result = self.run_execution_receipt_payload({"channel":{"channel_id":"external","side_effect_policy":"controlled","timeout_seconds":1,"identity_required":True,"allowed_scope":["x"]},"environment_ready":True,"target_command_started":True,"observed_behavior":{"side_effectful":True,"interactive":False},"transitive_invocations":[]})
        self.assertEqual(json.loads(result.stdout)["status"], "EXECUTION_CHANNEL_READY")

    def test_semantic_diff_requires_input_and_output_states(self) -> None:
        result = self.run_semantic_diff_payload({"contracts":[{"name":"x","classification":"production","production_semantic_delta":True,"owner":"o","allowed_transitions":["a-b"],"forbidden_transitions":["b-a"],"consumer_evidence":"c","regression_evidence":"r"}]})
        self.assertEqual(json.loads(result.stdout)["reason"], "MISSING_STATE_EVIDENCE")

    def test_scenario_fixture_composes_pass_projection_gate(self) -> None:
        result = subprocess.run([sys.executable,str(VALIDATOR),"--scenario-fixture",json.dumps({"event":"pass_projection","projection":{"execution_channel":"isolated","artifact_reference":"a","criteria":{"total":1,"passed":1},"required_controls":{"cleanup":True},"evidence_status":"verified"}})],capture_output=True,text=True,check=False)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS_PROJECTION_BLOCKED")
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

    def run_diagnostic_cycle_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "diagnostic-cycle" / f"{name}.json"
        return self.run_diagnostic_cycle_payload(json.loads(fixture.read_text(encoding="utf-8")))

    def run_diagnostic_cycle_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--diagnostic-cycle", json.dumps(payload)],
            capture_output=True,
            text=True,
            check=False,
        )

    def run_prepared_candidate_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "prepared-candidate" / f"{name}.json"
        return self.run_prepared_candidate_payload(json.loads(fixture.read_text(encoding="utf-8")))

    def run_prepared_candidate_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--prepared-candidate", json.dumps(payload)],
            capture_output=True,
            text=True,
            check=False,
        )
    def run_execution_receipt_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "execution-channel" / f"{name}.json"
        return self.run_execution_receipt_payload(json.loads(fixture.read_text(encoding="utf-8")))

    def run_execution_receipt_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--execution-receipt", json.dumps(payload)],
            capture_output=True,
            text=True,
            check=False,
        )
    def run_test_receipts_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "test-receipts" / f"{name}.json"
        return self.run_test_receipts_payload(json.loads(fixture.read_text(encoding="utf-8")))

    def run_test_receipts_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--test-receipts", json.dumps(payload)],
            capture_output=True,
            text=True,
            check=False,
        )
    def run_semantic_diff_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "semantic-diff" / f"{name}.json"
        return self.run_semantic_diff_payload(json.loads(fixture.read_text(encoding="utf-8")))

    def run_semantic_diff_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--semantic-diff", json.dumps(payload)],
            capture_output=True,
            text=True,
            check=False,
        )
    def run_pass_projection_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "pass-projection" / f"{name}.json"
        return subprocess.run([sys.executable, str(VALIDATOR), "--pass-projection", json.dumps(json.loads(fixture.read_text(encoding="utf-8")))], capture_output=True, text=True, check=False)
    def run_pass_projection_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(VALIDATOR), "--pass-projection", json.dumps(payload)], capture_output=True, text=True, check=False)

    def run_semantic_diff_payload(self, payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(VALIDATOR), "--semantic-diff", json.dumps(payload)], capture_output=True, text=True, check=False)
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
