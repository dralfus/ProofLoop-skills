from __future__ import annotations

import importlib.util
import json
import os
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

        self.assertIn("$excludedTools = if ($ApprovalMode -eq 'plan')", wrapper)
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
