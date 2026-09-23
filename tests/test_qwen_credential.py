from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPOSITORY_ROOT / "scripts" / "qwen_credential.ps1"
CAPTURE_RUNNER = REPOSITORY_ROOT / "scripts" / "start_qwen_assist_capture.ps1"
CAPTURE_READER = REPOSITORY_ROOT / "scripts" / "get_qwen_assist_capture.ps1"
FINISH_TICKET = REPOSITORY_ROOT / "scripts" / "invoke_qwen_finish_ticket.ps1"
PATCH_SCHEMA = REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist-patch.schema.json"
CANONICAL_LIFECYCLE = REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "task-lifecycle.md"
QWEN_REFERENCE = REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist.md"
HUMAN_LIFECYCLE = REPOSITORY_ROOT / "docs" / "codex-task-lifecycle.md"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


class QwenCredentialTest(unittest.TestCase):
    def test_helper_reads_generic_credential_without_command_line_secret(self) -> None:
        self.assertTrue(HELPER.is_file())
        helper = HELPER.read_text(encoding="utf-8")

        self.assertIn("CredReadW", helper)
        self.assertIn("CredFree", helper)
        self.assertIn("CRED_TYPE_GENERIC", helper)
        self.assertNotIn("Write-Output", helper)
        self.assertNotIn("Write-Host", helper)

    def test_capture_runner_redirects_output_without_putting_secret_in_command(self) -> None:
        self.assertTrue(CAPTURE_RUNNER.is_file())
        runner = CAPTURE_RUNNER.read_text(encoding="utf-8")

        self.assertIn("Start-Process", runner)
        self.assertIn("RedirectStandardOutput", runner)
        self.assertIn("RedirectStandardError", runner)
        self.assertIn("-EncodedCommand", runner)
        self.assertIn("CredentialTarget", runner)
        self.assertNotIn("Get-ProofLoopQwenGenericSecret", runner)

    def test_capture_runner_forwards_explicit_approval_mode(self) -> None:
        runner = CAPTURE_RUNNER.read_text(encoding="utf-8")

        self.assertIn("ValidateSet('plan', 'yolo', 'seal')", runner)
        self.assertIn("[string]$ApprovalMode = 'plan'", runner)
        self.assertIn("-ApprovalMode $(Quote-PowerShellLiteral $ApprovalMode)", runner)
        self.assertIn("[switch]$SuccessfulRecon", runner)
        self.assertIn("Candidate modes require -SuccessfulRecon", runner)

    def test_capture_runner_forwards_patch_seal_receipt(self) -> None:
        runner = CAPTURE_RUNNER.read_text(encoding="utf-8")

        self.assertIn("ValidateSet('plan', 'yolo', 'seal')", runner)
        self.assertIn("[string]$PatchSealReceiptPath", runner)
        self.assertIn("Quote-PowerShellLiteral", runner)
        self.assertIn("-PatchSealReceiptPath", runner)
        self.assertIn("[string]$TicketId", runner)
        self.assertIn("[string]$SealLedgerDirectory", runner)

    def test_capture_reader_reports_running_or_terminal_file_output(self) -> None:
        self.assertTrue(CAPTURE_READER.is_file())
        reader = CAPTURE_READER.read_text(encoding="utf-8")

        self.assertIn("Get-Process", reader)
        self.assertIn("RUNNING", reader)
        self.assertIn("stdout.json", reader)
        self.assertIn("stderr.txt", reader)
        self.assertIn("ConvertFrom-Json", reader)
        self.assertIn("[string]$RunId", reader)
        self.assertIn("ValidatePattern", reader)
        self.assertIn("Join-Path $CaptureDirectory $RunId", reader)
        self.assertIn("[string]$PatchSealReceiptPath", reader)
        self.assertIn("--validate-patch-seal-manifest", reader)
        self.assertIn("SEALED_CANDIDATE", reader)

    def test_finish_ticket_collector_delegates_recon_contract_to_shared_validator(self) -> None:
        collector = FINISH_TICKET.read_text(encoding="utf-8")
        self.assertIn("recon_report_contract.py", collector)
        self.assertIn("'--input-file'", collector)
        self.assertNotIn("$fact.PSObject.Properties.Name.Count", collector)

    def test_capture_reader_accepts_single_terminal_result_without_scalar_count_failure(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the capture-reader contract")

        receipt = {
            "baseline": "abc123",
            "files": ["tests/test_qwen_assist.py"],
            "changed_lines": 17,
            "targeted_tests": [
                "python -m unittest tests.test_qwen_assist.QwenAssistTest.test_patch_candidate_rejects_zero_changed_lines"
            ],
            "targeted_exit_code": 0,
            "git_operations": [],
            "full_suite": False,
            "yolo_reason": "STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT",
        }
        manifest = {
            "successful_recon": True,
            "files": receipt["files"],
            "changed_lines": receipt["changed_lines"],
            "targeted_tests": receipt["targeted_tests"],
            "git_operations": [],
            "full_suite": False,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_id = "a" * 32
            capture_path = temporary_root / run_id
            capture_path.mkdir()
            (capture_path / "stdout.json").write_text(
                json.dumps(
                    {
                        "type": "result",
                        "is_error": False,
                        "subtype": "success",
                        "structured_result": manifest,
                    }
                ),
                encoding="utf-8",
            )
            (capture_path / "stderr.txt").write_text("", encoding="utf-8")
            receipt_path = temporary_root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(CAPTURE_READER),
                    "-RunId",
                    run_id,
                    "-ProcessId",
                    "2147483647",
                    "-PatchSealReceiptPath",
                    str(receipt_path),
                    "-CaptureDirectory",
                    str(temporary_root),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        projection = json.loads(result.stdout)
        self.assertEqual(projection, {"status": "SEALED_CANDIDATE", "pid": 2147483647})
        self.assertNotIn("structured_result", result.stdout)

    def test_capture_reader_accepts_terminal_result_without_optional_metadata(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the capture-reader contract")

        receipt = {
            "baseline": "abc123",
            "files": ["tests/test_qwen_assist.py"],
            "changed_lines": 17,
            "targeted_tests": ["python -m unittest tests.test_qwen_assist"],
            "targeted_exit_code": 0,
            "git_operations": [],
            "full_suite": False,
            "yolo_reason": "STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT",
        }
        manifest = {
            "successful_recon": True,
            "files": receipt["files"],
            "changed_lines": receipt["changed_lines"],
            "targeted_tests": receipt["targeted_tests"],
            "git_operations": [],
            "full_suite": False,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_id = "d" * 32
            capture_path = temporary_root / run_id
            capture_path.mkdir()
            (capture_path / "stdout.json").write_text(
                json.dumps({"type": "result", "structured_result": manifest}),
                encoding="utf-8",
            )
            (capture_path / "stderr.txt").write_text("", encoding="utf-8")
            receipt_path = temporary_root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(CAPTURE_READER),
                    "-RunId", run_id, "-ProcessId", "2147483647",
                    "-PatchSealReceiptPath", str(receipt_path),
                    "-CaptureDirectory", str(temporary_root),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"status": "SEALED_CANDIDATE", "pid": 2147483647})

    def test_capture_reader_requires_final_result_event_for_array_output(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the capture-reader contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_id = "b" * 32
            capture_path = temporary_root / run_id
            capture_path.mkdir()
            (capture_path / "stdout.json").write_text(
                json.dumps([{"type": "assistant", "content": "not terminal"}]),
                encoding="utf-8",
            )
            (capture_path / "stderr.txt").write_text("", encoding="utf-8")
            receipt_path = temporary_root / "receipt.json"
            receipt_path.write_text("{}", encoding="utf-8")

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(CAPTURE_READER),
                    "-RunId",
                    run_id,
                    "-ProcessId",
                    "2147483647",
                    "-PatchSealReceiptPath",
                    str(receipt_path),
                    "-CaptureDirectory",
                    str(temporary_root),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        projection = json.loads(result.stdout)
        self.assertEqual(
            projection,
            {"status": "QWEN_UNUSABLE", "reason": "MISSING_TERMINAL_PATCH_MANIFEST", "pid": 2147483647},
        )
        self.assertNotIn("not terminal", result.stdout)

    def test_capture_reader_classifies_empty_stdout_as_missing_manifest(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the capture-reader contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_id = "c" * 32
            capture_path = temporary_root / run_id
            capture_path.mkdir()
            (capture_path / "stdout.json").write_text("", encoding="utf-8")
            (capture_path / "stderr.txt").write_text("diagnostic only", encoding="utf-8")

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(CAPTURE_READER),
                    "-RunId",
                    run_id,
                    "-ProcessId",
                    "2147483647",
                    "-PatchSealReceiptPath",
                    str(temporary_root / "receipt.json"),
                    "-CaptureDirectory",
                    str(temporary_root),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"status": "QWEN_UNUSABLE", "reason": "MISSING_TERMINAL_PATCH_MANIFEST", "pid": 2147483647},
        )


    def test_patch_candidate_schema_uses_provider_friendly_shape(self) -> None:
        self.assertTrue(PATCH_SCHEMA.is_file())
        schema = json.loads(PATCH_SCHEMA.read_text(encoding="utf-8"))

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["required"]),
            {
                "successful_recon",
                "files",
                "changed_lines",
                "targeted_tests",
                "git_operations",
                "full_suite",
            },
        )
        self.assertEqual(
            {name: schema["properties"][name]["type"] for name in schema["required"]},
            {
                "successful_recon": "boolean",
                "files": "array",
                "changed_lines": "integer",
                "targeted_tests": "array",
                "git_operations": "array",
                "full_suite": "boolean",
            },
        )
        for property_schema in schema["properties"].values():
            self.assertNotIn("const", property_schema)
            self.assertNotIn("minItems", property_schema)
            self.assertNotIn("maxItems", property_schema)
            self.assertNotIn("minLength", property_schema)
            self.assertFalse(isinstance(property_schema.get("type"), list))

    def test_patch_seal_documentation_contract(self) -> None:
        for document in (CANONICAL_LIFECYCLE, QWEN_REFERENCE, HUMAN_LIFECYCLE):
            self.assertTrue(document.is_file())
            content = document.read_text(encoding="utf-8")
            self.assertIn("QWEN_PATCH_SEAL", content)
            self.assertIn("PATCH_SEAL_RECEIPT", content)
            self.assertIn("SEALED_CANDIDATE", content)
            self.assertIn("plan", content)

        canonical = CANONICAL_LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn("one", canonical.lower())
        self.assertIn("no transfer", canonical.lower())
        self.assertIn("no retry", canonical.lower())

if __name__ == "__main__":
    unittest.main()
