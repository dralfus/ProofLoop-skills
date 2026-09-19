from __future__ import annotations

import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPOSITORY_ROOT / "scripts" / "qwen_credential.ps1"
CAPTURE_RUNNER = REPOSITORY_ROOT / "scripts" / "start_qwen_assist_capture.ps1"
CAPTURE_READER = REPOSITORY_ROOT / "scripts" / "get_qwen_assist_capture.ps1"
PATCH_SCHEMA = REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist-patch.schema.json"
CANONICAL_LIFECYCLE = REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "task-lifecycle.md"
QWEN_REFERENCE = REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist.md"
HUMAN_LIFECYCLE = REPOSITORY_ROOT / "docs" / "codex-task-lifecycle.md"


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
        self.assertIn("-ApprovalMode '$ApprovalMode'", runner)
        self.assertIn("[switch]$SuccessfulRecon", runner)
        self.assertIn("Candidate modes require -SuccessfulRecon", runner)

    def test_capture_runner_forwards_patch_seal_receipt(self) -> None:
        runner = CAPTURE_RUNNER.read_text(encoding="utf-8")

        self.assertIn("ValidateSet('plan', 'yolo', 'seal')", runner)
        self.assertIn("[string]$PatchSealReceiptPath", runner)
        self.assertIn("-PatchSealReceiptPath '$PatchSealReceiptPath'", runner)

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


    def test_patch_candidate_schema_matches_the_bounded_candidate_contract(self) -> None:
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
        self.assertEqual(schema["properties"]["files"]["maxItems"], 2)
        self.assertEqual(schema["properties"]["changed_lines"]["maximum"], 200)
        self.assertEqual(schema["properties"]["targeted_tests"]["maxItems"], 1)
        self.assertEqual(schema["properties"]["git_operations"]["type"], "array")
        self.assertEqual(schema["properties"]["git_operations"]["maxItems"], 0)

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
