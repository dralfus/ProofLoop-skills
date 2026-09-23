from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "qwen-adapters" / "production-shaped.json"
WRAPPER = REPOSITORY_ROOT / "scripts" / "invoke_qwen_assist.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TERMINAL = load_module("qwen_terminal_projection_fixture", REPOSITORY_ROOT / "scripts" / "qwen_terminal_projection.py")
RECON = load_module("recon_report_contract_fixture", REPOSITORY_ROOT / "scripts" / "recon_report_contract.py")


class QwenProductionFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def test_terminal_and_recon_matrix_uses_public_interfaces(self) -> None:
        terminal_case = self.fixtures["terminal_success"]
        structured = TERMINAL.extract_structured_result(json.dumps(terminal_case["stdout"]))
        self.assertIsNotNone(structured)
        self.assertEqual(structured["status"], terminal_case["expected"])

        malformed_case = self.fixtures["malformed_json"]
        failure = TERMINAL.project_failure(malformed_case["stdout"], malformed_case["stderr"])
        self.assertEqual(failure["reason"], malformed_case["expected"])
        self.assertNotIn("not-json", json.dumps(failure))

        baseline_case = self.fixtures["baseline_mismatch"]
        baseline_result = RECON.validate_recon_report(
            baseline_case["report"], expected_baseline=baseline_case["expected_baseline"]
        )
        self.assertEqual(baseline_result["reason"], baseline_case["expected"])

        write_case = self.fixtures["no_write"]
        write_result = RECON.validate_recon_report(write_case["report"])
        self.assertEqual(write_result["reason"], write_case["expected"])

    @unittest.skipUnless(PWSH, "PowerShell is required for credential restore behavior")
    def test_credential_restore_is_observed_through_real_wrapper_boundary(self) -> None:
        case = self.fixtures["credential_restore"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            wrapper = root / "invoke_qwen_assist.ps1"
            helper = root / "qwen_credential.ps1"
            registry = root / "qwen_invocation_contract.py"
            fake_qwen = root / "qwen.cmd"
            observed = root / "qwen-env.txt"
            wrapper.write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
            registry.write_text(
                (REPOSITORY_ROOT / "scripts" / "qwen_invocation_contract.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            helper.write_text(
                "function Get-ProofLoopQwenGenericSecret { param([string]$Target) return 'fixture-secret' }\n",
                encoding="utf-8",
            )
            fake_qwen.write_text(
                "@echo off\n"
                "if \"%1\"==\"--help\" (echo --prompt --output-format --json-schema --worktree --approval-mode --max-session-turns --max-wall-time --max-tool-calls --max-subagent-depth --exclude-tools --bare plan & exit /b 0)\n"
                f">\"{observed}\" echo %OPENAI_API_KEY%^|%OPENAI_BASE_URL%^|%OPENAI_MODEL%\n"
                "exit /b 7\n",
                encoding="utf-8",
            )
            command = (
                "$ErrorActionPreference='Stop'; "
                f"$env:PATH={json.dumps(str(root) + os.pathsep + os.environ.get('PATH', ''))}; "
                f"$env:OPENAI_API_KEY={json.dumps(case['old']['OPENAI_API_KEY'])}; "
                f"$env:OPENAI_BASE_URL={json.dumps(case['old']['OPENAI_BASE_URL'])}; "
                f"$env:OPENAI_MODEL={json.dumps(case['old']['OPENAI_MODEL'])}; "
                "try { "
                f". {json.dumps(str(wrapper))} -Prompt 'fixture' -SchemaPath 'schema.json' "
                f"-Worktree 'fixture' -AuthType 'openai' -ApprovalMode 'plan' -CredentialTarget 'Fixture/Target' "
                "} catch {}; "
                "[ordered]@{key=$env:OPENAI_API_KEY;base=$env:OPENAI_BASE_URL;model=$env:OPENAI_MODEL} | ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                [PWSH, "-NoProfile", "-Command", command],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )
            self.assertTrue(observed.is_file(), result.stderr + result.stdout)
            self.assertIn("fixture-secret", observed.read_text(encoding="utf-8"))
            restored = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(
                restored,
                {
                    "key": case["old"]["OPENAI_API_KEY"],
                    "base": case["old"]["OPENAI_BASE_URL"],
                    "model": case["old"]["OPENAI_MODEL"],
                },
            )


if __name__ == "__main__":
    unittest.main()
