from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "scripts" / "qwen_assist.py"
SPEC = importlib.util.spec_from_file_location("qwen_assist", MODULE_PATH)
POWERSHELL_WRAPPER = REPOSITORY_ROOT / "scripts" / "invoke_qwen_assist.ps1"
assert SPEC and SPEC.loader
QWEN_ASSIST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QWEN_ASSIST)


QWEN_HELP = """
  -p, --prompt                          Prompt.
      --bare                            Skip implicit workspace customizations.
  -o, --output-format                   The format of the CLI output.
      --json-schema                     JSON Schema that the model's final output must conform to.
      --worktree                        Start the session inside a git worktree.
      --approval-mode                   Set the approval mode: plan.
      --max-session-turns               Maximum number of session turns.
      --max-wall-time                   Run-level wall-clock budget.
      --max-tool-calls                  Maximum cumulative tool calls.
      --exclude-tools                   Tools to exclude.
      --fallback-model                  Fallback model(s).
"""


class QwenAssistTest(unittest.TestCase):
    def recon_report(self) -> dict[str, object]:
        return {
            "status": "EVIDENCE_FOUND",
            "baseline": "abc123",
            "facts": [
                {"file": "src/a.cs", "line": 10, "fact": "Callback enters resident lookup."},
                {"file": "src/b.cs", "line": 20, "fact": "Owner publishes the snapshot."},
                {"file": "tests/c.cs", "line": 30, "fact": "Fixture covers stale evidence."},
            ],
            "state_owner": "Resident evidence owner",
            "callback_boundary": "Low-level pointer callback",
            "acceptance_risk": "Stale evidence must fail closed.",
            "stop_reason": None,
        }

    def test_capability_probe_accepts_new_version_without_version_field(self) -> None:
        result = QWEN_ASSIST.probe_qwen_capabilities(QWEN_HELP)

        self.assertEqual(result, {"status": "QWEN_ASSIST_READY", "missing_capabilities": []})

    def test_capability_probe_blocks_missing_limit(self) -> None:
        result = QWEN_ASSIST.probe_qwen_capabilities(QWEN_HELP.replace("--max-tool-calls", ""))

        self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
        self.assertEqual(result["missing_capabilities"], ["max_tool_calls"])

    def test_capability_probe_blocks_missing_bare_mode(self) -> None:
        result = QWEN_ASSIST.probe_qwen_capabilities(QWEN_HELP.replace("--bare", ""))

        self.assertEqual(result["status"], "BLOCKED_CAPABILITY")
        self.assertEqual(result["missing_capabilities"], ["bare_mode"])

    def test_powershell_wrapper_requires_and_passes_bare_mode(self) -> None:
        wrapper = POWERSHELL_WRAPPER.read_text(encoding="utf-8")
        required_markers = wrapper.split("$requiredMarkers = @(", 1)[1].split(")", 1)[0]

        self.assertIn("'--bare'", required_markers)
        self.assertIn("    '--bare' `", wrapper)

        self.assertIn("$effectiveApprovalMode = if ($ApprovalMode -eq 'seal') { 'plan' } else { $ApprovalMode }", wrapper)
        self.assertIn("$excludedTools = if ($effectiveApprovalMode -eq 'plan')", wrapper)
        self.assertIn("'Agent,edit,notebook_edit,run_shell_command'", wrapper)
        self.assertIn("else { 'Agent,run_shell_command' }", wrapper)


        self.assertIn("[string]$AuthType", wrapper)
        self.assertIn("'--auth-type'", wrapper)
        self.assertIn("[string]$CredentialTarget", wrapper)
        self.assertIn("Get-ProofLoopQwenGenericSecret", wrapper)
        self.assertIn("Remove-Item Env:OPENAI_API_KEY", wrapper)
        self.assertIn("OPENAI_BASE_URL", wrapper)
        self.assertIn("https://llm-dev.gs-labs.ru/api/v1", wrapper)
        self.assertIn("OPENAI_MODEL", wrapper)
        self.assertIn("qwen38-flash-next", wrapper)
        self.assertIn("Remove-Item Env:OPENAI_BASE_URL", wrapper)
        self.assertIn("Remove-Item Env:OPENAI_MODEL", wrapper)

    def test_powershell_wrapper_seal_is_read_only(self) -> None:
        wrapper = POWERSHELL_WRAPPER.read_text(encoding="utf-8")

        self.assertIn("ValidateSet('plan', 'yolo', 'seal')", wrapper)
        self.assertIn("[string]$PatchSealReceiptPath", wrapper)
        self.assertIn("$effectiveApprovalMode = if ($ApprovalMode -eq 'seal') { 'plan' } else { $ApprovalMode }", wrapper)
        self.assertIn("--validate-patch-seal-receipt", wrapper)
        self.assertIn("'Agent,edit,notebook_edit,run_shell_command'", wrapper)
        self.assertIn("$maxToolCalls = if ($ApprovalMode -eq 'seal') { '1' } else { '20' }", wrapper)
        self.assertIn("$maxSessionTurns = if ($ApprovalMode -eq 'seal') { '12' } else { '12' }", wrapper)
        self.assertIn("$maxWallTime = if ($ApprovalMode -eq 'seal') { '300s' } else { '10m' }", wrapper)
        self.assertIn("Call structured_output exactly once", wrapper)
        self.assertIn("Do not inspect or edit code, use shell/network, or create subagents.", wrapper)

    def test_recon_runner_builds_read_only_bounded_command_and_rejects_bad_output(self) -> None:
        runner = Mock(return_value=(0, json.dumps(self.recon_report()), ""))
        result = QWEN_ASSIST.run_recon(
            help_text=QWEN_HELP,
            qwen_command="qwen",
            prompt="Map one callback.",
            schema_path="schema.json",
            worktree="pilot-314",
            runner=runner,
        )

        self.assertEqual(result, {"status": "EVIDENCE_FOUND"})
        command = runner.call_args.args[0]
        self.assertIn("--prompt", command)
        self.assertIn("plan", command)
        self.assertIn("--exclude-tools", command)
        self.assertIn("--bare", command)
        self.assertNotIn("--fallback-model", command)
        excluded_tool_index = command.index("--exclude-tools")
        self.assertEqual(
            command[excluded_tool_index + 1],
            "Agent,edit,notebook_edit,run_shell_command",
        )

        invalid = QWEN_ASSIST.run_recon(
            help_text=QWEN_HELP,
            qwen_command="qwen",
            prompt="Map one callback.",
            schema_path="schema.json",
            worktree="pilot-314",
            runner=Mock(return_value=(0, "not-json", "")),
        )
        self.assertEqual(invalid, {"status": "QWEN_UNUSABLE", "reason": "INVALID_JSON_OUTPUT"})

    def test_recon_classifies_structured_output_missing_at_turn_limit(self) -> None:
        result = QWEN_ASSIST.run_recon(
            help_text=QWEN_HELP,
            qwen_command="qwen",
            prompt="Map one callback.",
            schema_path="schema.json",
            worktree="pilot-314",
            runner=Mock(return_value=(53, "Reached max session turns. structured_output was not called.", "")),
        )
        self.assertEqual(
            result,
            {"status": "QWEN_UNUSABLE", "reason": "STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT"},
        )

    def test_recon_runner_accepts_current_json_event_array_structured_result(self) -> None:
        runner = Mock(
            return_value=(
                0,
                json.dumps(
                    [
                        {"type": "message", "role": "assistant", "content": "Inspecting scope."},
                        {"type": "result", "structured_result": self.recon_report()},
                    ]
                ),
                "",
            )
        )

        result = QWEN_ASSIST.run_recon(
            help_text=QWEN_HELP,
            qwen_command="qwen",
            prompt="Map one callback.",
            schema_path="schema.json",
            worktree="pilot-314",
            runner=runner,
        )

        self.assertEqual(result, {"status": "EVIDENCE_FOUND"})

    def test_recon_report_requires_three_locatable_facts_and_read_only_fields(self) -> None:

        self.assertEqual(QWEN_ASSIST.validate_recon_report(self.recon_report()), {"status": "EVIDENCE_FOUND"})

        incomplete = self.recon_report()
        incomplete["facts"] = incomplete["facts"][:2]
        self.assertEqual(
            QWEN_ASSIST.validate_recon_report(incomplete),
            {"status": "QWEN_UNUSABLE", "reason": "INSUFFICIENT_FACTS"},
        )

    def test_recon_report_rejects_reported_writes(self) -> None:
        report = self.recon_report()
        report["writes"] = ["src/a.cs"]

        self.assertEqual(
            QWEN_ASSIST.validate_recon_report(report),
            {"status": "QWEN_UNUSABLE", "reason": "READ_ONLY_VIOLATION"},
        )

    def test_ledger_stops_repeated_root_cause_and_two_non_progress_attempts(self) -> None:
        repeated = [
            {
                "root_cause": "missing resident evidence",
                "progress": False,
                "hypothesis": "old",
                "scope": "first",
            },
        ]
        self.assertEqual(
            QWEN_ASSIST.next_qwen_attempt(
                repeated,
                {
                    "root_cause": "missing-resident-evidence",
                    "progress": False,
                    "hypothesis": "retry",
                    "scope": "second",
                },
            ),
            {"status": "QWEN_UNUSABLE", "reason": "REPEATED_ROOT_CAUSE"},
        )

        non_progress = [
            {"root_cause": "first", "progress": False, "hypothesis": "old", "scope": "first"},
        ]
        self.assertEqual(
            QWEN_ASSIST.next_qwen_attempt(
                non_progress,
                {"root_cause": "second", "progress": False, "hypothesis": "new scope", "scope": "second"},
            ),
            {"status": "QWEN_UNUSABLE", "reason": "TWO_NON_PROGRESS_ATTEMPTS"},
        )

    def test_ledger_allows_at_most_seven_attempts(self) -> None:
        ledger = [
            {"root_cause": f"cause-{index}", "progress": True, "hypothesis": "old", "scope": "old"}
            for index in range(7)
        ]

        self.assertEqual(
            QWEN_ASSIST.next_qwen_attempt(
                ledger,
                {"root_cause": "cause-8", "progress": True, "hypothesis": "new evidence", "scope": "new"},
            ),
            {"status": "QWEN_UNUSABLE", "reason": "QWEN_BUDGET_EXHAUSTED"},
        )

    def test_ledger_requires_a_changed_retry_packet(self) -> None:
        previous = {"root_cause": "first", "progress": True, "hypothesis": "same", "scope": "same"}
        self.assertEqual(
            QWEN_ASSIST.next_qwen_attempt(
                [previous],
                {"root_cause": "second", "progress": True, "hypothesis": "same", "scope": "same"},
            ),
            {"status": "QWEN_UNUSABLE", "reason": "RETRY_WITHOUT_CHANGED_PACKET"},
        )

    def patch_seal_receipt(self) -> dict[str, object]:
        return {
            "baseline": "abc123",
            "files": ["scripts/qwen_assist.py"],
            "changed_lines": 12,
            "targeted_tests": [
                "python -m unittest tests.test_qwen_assist.QwenAssistTest.test_patch_seal_accepts_exact_observed_manifest"
            ],
            "targeted_exit_code": 0,
            "git_operations": [],
            "full_suite": False,
            "yolo_reason": "STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT",
        }

    def test_patch_seal_accepts_exact_observed_manifest(self) -> None:
        receipt = self.patch_seal_receipt()
        manifest = {
            "successful_recon": True,
            "files": receipt["files"],
            "changed_lines": receipt["changed_lines"],
            "targeted_tests": receipt["targeted_tests"],
            "git_operations": [],
            "full_suite": False,
        }

        self.assertEqual(
            QWEN_ASSIST.validate_patch_seal_receipt(receipt),
            {"status": "PATCH_SEAL_RECEIPT_READY"},
        )
        self.assertEqual(
            QWEN_ASSIST.validate_patch_seal_manifest(receipt, manifest),
            {"status": "SEALED_CANDIDATE"},
        )

    def test_patch_seal_rejects_non_integer_targeted_exit_code(self) -> None:
        receipt = self.patch_seal_receipt()
        receipt["targeted_exit_code"] = False

        self.assertEqual(
            QWEN_ASSIST.validate_patch_seal_receipt(receipt),
            {"status": "QWEN_UNUSABLE", "reason": "MALFORMED_PATCH_SEAL_RECEIPT"},
        )

    def test_patch_seal_rejects_boolean_changed_lines_and_wrong_baseline(self) -> None:
        receipt = self.patch_seal_receipt()
        receipt["changed_lines"] = True
        self.assertEqual(
            QWEN_ASSIST.validate_patch_seal_receipt(receipt),
            {"status": "QWEN_UNUSABLE", "reason": "PATCH_SCOPE_EXCEEDED"},
        )

        receipt = self.patch_seal_receipt()
        self.assertEqual(
            QWEN_ASSIST.validate_patch_seal_receipt(receipt, expected_baseline="def456"),
            {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_BASELINE_MISMATCH"},
        )

    def test_patch_seal_reservation_allows_one_call_per_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            seal_store = Path(temporary_directory)
            self.assertEqual(
                QWEN_ASSIST.reserve_patch_seal("314", self.patch_seal_receipt(), seal_store),
                {"status": "PATCH_SEAL_RESERVED"},
            )
            self.assertEqual(
                QWEN_ASSIST.reserve_patch_seal("314", self.patch_seal_receipt(), seal_store),
                {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_ALREADY_USED"},
            )
    def test_patch_seal_rejects_ineligible_or_out_of_scope_receipt(self) -> None:
        receipt = self.patch_seal_receipt()
        receipt["yolo_reason"] = "QWEN_COMMAND_FAILED"
        self.assertEqual(
            QWEN_ASSIST.validate_patch_seal_receipt(receipt),
            {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_NOT_ELIGIBLE"},
        )

        for field, value, reason in (
            ("files", ["a.py", "b.py", "c.py"], "PATCH_SCOPE_EXCEEDED"),
            ("changed_lines", 201, "PATCH_SCOPE_EXCEEDED"),
            ("git_operations", ["commit"], "GIT_INTEGRATION_FORBIDDEN"),
            ("full_suite", True, "GIT_INTEGRATION_FORBIDDEN"),
        ):
            receipt = self.patch_seal_receipt()
            receipt[field] = value
            self.assertEqual(
                QWEN_ASSIST.validate_patch_seal_receipt(receipt),
                {"status": "QWEN_UNUSABLE", "reason": reason},
            )

    def test_patch_seal_accepts_controller_collector_failure_reason(self) -> None:
        receipt = self.patch_seal_receipt()
        receipt["yolo_reason"] = "COLLECTOR_PROJECTION_FAILED"

        self.assertEqual(
            QWEN_ASSIST.validate_patch_seal_receipt(receipt),
            {"status": "PATCH_SEAL_RECEIPT_READY"},
        )

    def test_patch_seal_rejects_manifest_that_differs_from_observed_receipt(self) -> None:
        receipt = self.patch_seal_receipt()
        manifest = {
            "successful_recon": True,
            "files": receipt["files"],
            "changed_lines": receipt["changed_lines"],
            "targeted_tests": receipt["targeted_tests"],
            "git_operations": [],
            "full_suite": False,
        }

        for field, value in (
            ("files", ["tests/test_qwen_assist.py"]),
            ("changed_lines", 13),
            ("targeted_tests", ["python -m unittest another.test"]),
        ):
            changed_manifest = dict(manifest)
            changed_manifest[field] = value
            self.assertEqual(
                QWEN_ASSIST.validate_patch_seal_manifest(receipt, changed_manifest),
                {"status": "QWEN_UNUSABLE", "reason": "PATCH_SEAL_MANIFEST_MISMATCH"},
            )

    def test_cli_validates_patch_seal_receipt(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--validate-patch-seal-receipt", json.dumps(self.patch_seal_receipt())],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"status": "PATCH_SEAL_RECEIPT_READY"})

    def test_cli_validates_terminal_patch_seal_manifest(self) -> None:
        receipt = self.patch_seal_receipt()
        manifest = {
            "successful_recon": True,
            "files": receipt["files"],
            "changed_lines": receipt["changed_lines"],
            "targeted_tests": receipt["targeted_tests"],
            "git_operations": [],
            "full_suite": False,
        }
        completed = subprocess.run(
            [
                sys.executable, str(MODULE_PATH), "--validate-patch-seal-manifest", json.dumps(manifest),
                "--patch-seal-receipt", json.dumps(receipt),
            ], check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"status": "SEALED_CANDIDATE"})
    def test_patch_candidate_enforces_small_diff_and_no_git_integration(self) -> None:
        candidate = {
            "successful_recon": True,
            "files": ["src/a.cs", "tests/a.cs"],
            "changed_lines": 200,
            "targeted_tests": ["dotnet test --filter A"],
            "git_operations": [],
            "full_suite": False,
        }
        self.assertEqual(QWEN_ASSIST.validate_patch_candidate(candidate), {"status": "CANDIDATE_PATCH"})

        candidate["git_operations"] = ["commit"]
        self.assertEqual(
            QWEN_ASSIST.validate_patch_candidate(candidate),
            {"status": "QWEN_UNUSABLE", "reason": "GIT_INTEGRATION_FORBIDDEN"},
        )
        candidate["git_operations"] = False
        self.assertEqual(
            QWEN_ASSIST.validate_patch_candidate(candidate),
            {"status": "QWEN_UNUSABLE", "reason": "GIT_INTEGRATION_FORBIDDEN"},
        )


    def test_metrics_store_only_anonymized_fields(self) -> None:
        metric = QWEN_ASSIST.anonymize_metric(
            {
                "task_type": "recon",
                "outcome": "EVIDENCE_FOUND",
                "attempts": 1,
                "duration_seconds": 34,
                "tool_calls": 6,
                "stop_reason": None,
                "file": "S:/secret/project/src/a.cs",
                "raw_finding": "secret text",
            }
        )
        self.assertEqual(
            metric,
            {
                "task_type": "recon",
                "outcome": "EVIDENCE_FOUND",
                "attempts": 1,
                "duration_seconds": 34,
                "tool_calls": 6,
                "stop_reason": None,
            },
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "qwen-metrics.jsonl"
            QWEN_ASSIST.append_metric(store, metric)
            self.assertEqual(json.loads(store.read_text(encoding="utf-8")), metric)

    def test_default_metrics_path_uses_local_app_data_not_project_path(self) -> None:
        previous = os.environ.get("LOCALAPPDATA")
        self.addCleanup(
            lambda: os.environ.__setitem__("LOCALAPPDATA", previous)
            if previous is not None
            else os.environ.pop("LOCALAPPDATA", None)
        )
        os.environ["LOCALAPPDATA"] = "C:/Users/test/AppData/Local"

        self.assertEqual(
            QWEN_ASSIST.default_metrics_path(),
            Path("C:/Users/test/AppData/Local/ProofLoop Skills/qwen-metrics.jsonl"),
        )


if __name__ == "__main__":
    unittest.main()
