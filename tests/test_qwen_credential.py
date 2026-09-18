from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPOSITORY_ROOT / "scripts" / "qwen_credential.ps1"
CAPTURE_RUNNER = REPOSITORY_ROOT / "scripts" / "start_qwen_assist_capture.ps1"


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


if __name__ == "__main__":
    unittest.main()
