from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SMOKE = REPOSITORY_ROOT / "scripts" / "smoke_qwen_capabilities.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


class QwenCapabilitySmokeTest(unittest.TestCase):
    def test_smoke_accepts_qwen_024_by_capability_and_never_dispatches_a_role(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the Qwen smoke contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            fake_qwen = temporary_root / "fake-qwen.ps1"
            calls_path = temporary_root / "calls.txt"
            evidence_path = temporary_root / "smoke.json"
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "Add-Content -LiteralPath $env:QWEN_SMOKE_CALLS -Value ($Arguments -join ' ')\n"
                "if ($Arguments.Count -eq 1 -and $Arguments[0] -eq '--version') { Write-Output '0.24.0'; exit 0 }\n"
                "if ($Arguments.Count -eq 1 -and $Arguments[0] -eq '--help') { Write-Output '--prompt --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth'; exit 0 }\n"
                "exit 9\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_SMOKE_CALLS"] = str(calls_path)

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(SMOKE),
                    "-QwenCommand",
                    str(fake_qwen),
                    "-EvidencePath",
                    str(evidence_path),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
            )

            self.assertEqual(result.returncode, 0)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_CLI_CAPABILITY_READY")
            self.assertEqual(projection["version"], "0.24.0")
            self.assertFalse(projection["role_dispatch"])
            self.assertFalse(projection["acceptance"])
            self.assertEqual(calls_path.read_text(encoding="utf-8").splitlines(), ["--version", "--help"])
            self.assertEqual(json.loads(evidence_path.read_text(encoding="utf-8")), projection)
            self.assertNotIn(str(temporary_root), result.stdout)
            self.assertNotIn("SECRET", evidence_path.read_text(encoding="utf-8").upper())

            smoke_source = SMOKE.read_text(encoding="utf-8")
            self.assertNotIn("/finish-ticket", smoke_source)
            self.assertNotIn("implementer", smoke_source.lower())
            self.assertIn("'--version'", smoke_source)
            self.assertIn("'--help'", smoke_source)


if __name__ == "__main__":
    unittest.main()
