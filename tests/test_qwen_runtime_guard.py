from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_qwen_runtime_adapter import QwenRuntimeAdapterTest as AdapterFixtures
from tests.test_qwen_runtime_adapter import ADAPTER as RUNTIME_ADAPTER
from tests.test_qwen_runtime_adapter import init_repo as init_adapter_repo


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPOSITORY_ROOT / "scripts" / "invoke_qwen_finish_ticket.ps1"
CLI_COMPATIBILITY_CONSUMER = REPOSITORY_ROOT / "scripts" / "invoke_qwen_finish_ticket_cli.ps1"
RECON_SCHEMA = REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist-recon.schema.json"
PWSH = shutil.which("pwsh") or shutil.which("powershell")
GIT = shutil.which("git")


def create_clean_git_worktree(root: Path) -> None:
    if GIT is None:
        raise unittest.SkipTest("Git is required for the clean-worktree contract")
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_NAME": "ProofLoop Test",
            "GIT_AUTHOR_EMAIL": "proofloop@example.invalid",
            "GIT_COMMITTER_NAME": "ProofLoop Test",
            "GIT_COMMITTER_EMAIL": "proofloop@example.invalid",
        }
    )
    subprocess.run([GIT, "init", "--quiet", str(root)], check=True, env=environment)
    (root / "README.md").write_text("clean fixture\n", encoding="utf-8")
    subprocess.run([GIT, "-C", str(root), "add", "README.md"], check=True, env=environment)
    subprocess.run(
        [GIT, "-C", str(root), "commit", "--quiet", "-m", "fixture"],
        check=True,
        env=environment,
    )


def write_qwen_node_shim(root: Path, entrypoint_source: str) -> Path:
    entrypoint = root / "node_modules" / "@qwen-code" / "qwen-code" / "cli-entry.js"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text(entrypoint_source, encoding="utf-8")
    command = root / "qwen.cmd"
    command.write_text(
        "\r\n".join(
            [
                "@ECHO off",
                "GOTO start",
                ":find_dp0",
                "SET dp0=%~dp0",
                "EXIT /b",
                ":start",
                "SETLOCAL",
                "CALL :find_dp0",
                "",
                r'IF EXIST "%dp0%\node.exe" (',
                r'  SET "_prog=%dp0%\node.exe"',
                ") ELSE (",
                '  SET "_prog=node"',
                "  SET PATHEXT=%PATHEXT:;.JS;=;%",
                ")",
                "",
                r'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\node_modules\@qwen-code\qwen-code\cli-entry.js" %*',
            ]
        )
        + "\r\n",
        encoding="utf-8",
    )
    return command


class QwenRuntimeGuardTest(unittest.TestCase):
    def test_launcher_default_settings_path_uses_userprofile_environment(self) -> None:
        source = LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("Join-Path $env:USERPROFILE '.qwen\\settings.json'", source)
        self.assertNotIn("GetFolderPath([Environment+SpecialFolder]::UserProfile)", source)

    def test_protocol_preflight_blocks_unrecognized_qwen_cmd_before_execution(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            extension_root = root / "proofloop-skills"
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1,
                            "reasoningEffort": "xhigh",
                        }
                    }
                ),
                encoding="utf-8",
            )
            marker = root / "unknown wrapper executed.txt"
            fake_qwen = root / "qwen.cmd"
            fake_qwen.write_text(
                '@echo off\r\nif defined QWEN_TEST_UNSUPPORTED_MARKER echo executed>"%QWEN_TEST_UNSUPPORTED_MARKER%"\r\nexit /b 0\r\n',
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(LAUNCHER),
                    "-Ticket", "314", "-Mode", "protocol",
                    "-SettingsPath", str(settings_path),
                    "-ExtensionRoot", str(extension_root),
                    "-ReceiptDirectory", str(root / "receipts"),
                    "-QwenCommand", str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env={**os.environ, "QWEN_TEST_UNSUPPORTED_MARKER": str(marker)},
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("QWEN_CLI_UNAVAILABLE", result.stdout + result.stderr)
            self.assertFalse(marker.exists(), "unknown batch wrapper ran during capability preflight")

    def test_protocol_injects_process_scoped_credential_manager_key(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")
        if not (shutil.which("node.exe") or shutil.which("node")):
            self.skipTest("Node.js is required to exercise the recognized Qwen cmd shim")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            extension_root = root / "proofloop-skills"
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1,
                            "reasoningEffort": "xhigh",
                        }
                    }
                ),
                encoding="utf-8",
            )
            observed_path = root / "credential-observed.txt"
            python_auth_observed_path = root / "python-auth-observed.txt"
            parent_restore_observed_path = root / "parent-restore-observed.txt"
            python_shim_directory = root / "python-shim"
            python_shim_directory.mkdir()
            python_shim = python_shim_directory / "python.cmd"
            python_shim.write_text(
                '@echo off\r\n'
                'if "%OPENAI_API_KEY%"=="fixture-only-secret" (>>"%QWEN_FAKE_PYTHON_AUTH%" echo leaked) else (>>"%QWEN_FAKE_PYTHON_AUTH%" echo safe)\r\n'
                '"%QWEN_REAL_PYTHON%" %*\r\n'
                'exit /b %errorlevel%\r\n',
                encoding="utf-8",
            )
            fake_qwen = write_qwen_node_shim(
                root,
                'const fs = require("node:fs");\n'
                'const args = process.argv.slice(2);\n'
                'if (args.length === 1 && args[0] === "--help") { console.log("--prompt --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --json-file"); process.exit(0); }\n'
                'fs.writeFileSync(process.env.QWEN_FAKE_AUTH_OBSERVED, String(process.env.OPENAI_API_KEY === "fixture-only-secret"));\n'
                'const eventPath = args[args.indexOf("--json-file") + 1];\n'
                'const events = [{type:"system",subtype:"session_start",session_id:"fixture-session"},{type:"assistant",message:{id:"turn-1",role:"assistant",content:[]}},{type:"system",subtype:"session_end",data:{reason:"prompt_input_exit"}}];\n'
                'fs.writeFileSync(eventPath, events.map(event => JSON.stringify(event)).join("\\n") + "\\n");\n',
            )
            wrapper = root / "launch.ps1"
            wrapper.write_text(
                "Add-Type -TypeDefinition @'\n"
                "namespace ProofLoop { public static class QwenCredentialNative {\n"
                "  public static string ReadGenericSecret(string target) {\n"
                "    if (target != \"ProofLoop/TestCredential\") throw new System.InvalidOperationException(\"fixture target mismatch\");\n"
                "    return \"fixture-only-secret\";\n"
                "  }\n"
                "} }\n"
                "'@\n"
                "& $env:QWEN_TEST_LAUNCHER -Ticket 'qwen-protocol-pilot-ticket.md' -Mode protocol `\n"
                "  -SettingsPath $env:QWEN_TEST_SETTINGS -ExtensionRoot $env:QWEN_TEST_EXTENSION `\n"
                "  -ReceiptDirectory $env:QWEN_TEST_RECEIPTS -QwenCommand $env:QWEN_TEST_COMMAND `\n"
                "  -CredentialTarget 'ProofLoop/TestCredential'\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_PARENT_RESTORE, [string]([Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'Process') -ceq 'existing-process-value'))\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "QWEN_FAKE_AUTH_OBSERVED": str(observed_path),
                    "QWEN_FAKE_PYTHON_AUTH": str(python_auth_observed_path),
                    "QWEN_FAKE_PARENT_RESTORE": str(parent_restore_observed_path),
                    "QWEN_REAL_PYTHON": sys.executable,
                    "QWEN_TEST_LAUNCHER": str(LAUNCHER),
                    "QWEN_TEST_SETTINGS": str(settings_path),
                    "QWEN_TEST_EXTENSION": str(extension_root),
                    "QWEN_TEST_RECEIPTS": str(root / "receipts"),
                    "QWEN_TEST_COMMAND": str(fake_qwen),
                    "OPENAI_API_KEY": "existing-process-value",
                    "PATH": str(python_shim_directory) + os.pathsep + os.environ.get("PATH", ""),
                }
            )
            result = subprocess.run(
                [PWSH, "-NoProfile", "-File", str(wrapper)],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_SESSION_GUARD_READY")
            self.assertEqual(observed_path.read_text(encoding="utf-8").lower(), "true")
            self.assertIn("safe", python_auth_observed_path.read_text(encoding="utf-8").splitlines())
            self.assertNotIn("leaked", python_auth_observed_path.read_text(encoding="utf-8").splitlines())
            self.assertEqual(parent_restore_observed_path.read_text(encoding="utf-8").lower(), "true")
            self.assertNotIn("fixture-only-secret", result.stdout + result.stderr)

    def test_protocol_launcher_preserves_raw_free_jsonl_error_classification(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            extension_root = root / "proofloop-skills"
            receipt_directory = root / "receipts"
            fake_qwen = root / "fake-qwen.ps1"
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            settings_path.write_text(
                json.dumps({"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}),
                encoding="utf-8",
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --json-file'; exit 0 }\n"
                "$jsonIndex = [Array]::IndexOf($Arguments, '--json-file')\n"
                "[IO.File]::WriteAllLines($Arguments[$jsonIndex + 1], [string[]]@('{\"type\":\"system\",\"subtype\":\"session_start\",\"session_id\":\"private-session\"}', '{\"type\":\"result\",\"is_error\":true,\"subtype\":\"error_during_execution\",\"error\":{\"message\":\"HTTP 403 Forbidden https://private.example/v1 secret-token\"}}', '{\"type\":\"system\",\"subtype\":\"session_end\"}'), [Text.UTF8Encoding]::new($false))\n"
                "cmd.exe /c 'exit 7'\n"
                "exit 7\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "18",
                    "-Mode",
                    "protocol",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env={**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")},
            )

            self.assertEqual(result.returncode, 7, result.stderr + result.stdout)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_COMMAND_FAILED")
            self.assertEqual(projection["reason"], "QWEN_JSON_ERROR_RESULT", projection)
            self.assertEqual(projection["qwen_exit_code"], 7)
            self.assertEqual(projection["runtime_projection_exit_code"], 3)
            self.assertTrue(projection["runtime_projection_output_present"])
            self.assertTrue(projection["runtime_projection_parse_valid"])
            self.assertEqual(projection["runtime_evidence_status"], "QWEN_COMMAND_FAILED")
            self.assertEqual(projection["turn_count"], 0)
            self.assertEqual(projection["tool_call_count"], 0)
            self.assertRegex(projection["session_id"], r"^[0-9a-f]{64}$")
            self.assertGreaterEqual(projection["wall_time_seconds"], 0)
            self.assertRegex(projection["tool_fingerprint"], r"^[0-9a-f]{64}$")
            self.assertEqual(projection["diagnostic"]["terminal_subtype"], "error_during_execution")
            self.assertEqual(projection["diagnostic"]["error_message_category"], "auth_or_forbidden")
            terminal_receipts = list(receipt_directory.glob("QWEN_TERMINAL_OUTCOME-*.json"))
            self.assertEqual(len(terminal_receipts), 1)
            terminal_receipt_text = terminal_receipts[0].read_text(encoding="utf-8")
            terminal_receipt = json.loads(terminal_receipt_text)
            self.assertEqual(terminal_receipt["receipt_type"], "QWEN_TERMINAL_OUTCOME")
            self.assertEqual(terminal_receipt["receipt_version"], 1)
            self.assertEqual(terminal_receipt["status"], "QWEN_COMMAND_FAILED")
            self.assertEqual(terminal_receipt["reason"], "QWEN_JSON_ERROR_RESULT")
            self.assertEqual(terminal_receipt["diagnostic"]["error_message_category"], "auth_or_forbidden")
            self.assertTrue(terminal_receipt["terminal_receipt_written"])
            for forbidden in ("private-session", "private.example", "secret-token", "403 Forbidden"):
                self.assertNotIn(forbidden, result.stdout + result.stderr)
                self.assertNotIn(forbidden, terminal_receipt_text)

    def test_protocol_launcher_persists_terminal_outcome_when_qwen_events_are_missing(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            extension_root = root / "proofloop-skills"
            receipt_directory = root / "receipts"
            fake_qwen = root / "fake-qwen.ps1"
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            settings_path.write_text(
                json.dumps({"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}),
                encoding="utf-8",
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --json-file'; exit 0 }\n"
                "$jsonIndex = [Array]::IndexOf($Arguments, '--json-file')\n"
                "[IO.File]::WriteAllText($Arguments[$jsonIndex + 1], '', [Text.UTF8Encoding]::new($false))\n"
                "exit 7\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(LAUNCHER),
                    "-Ticket", "18", "-Mode", "protocol",
                    "-SettingsPath", str(settings_path),
                    "-ExtensionRoot", str(extension_root),
                    "-ReceiptDirectory", str(receipt_directory),
                    "-QwenCommand", str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env={**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")},
            )

            self.assertEqual(result.returncode, 7, result.stderr + result.stdout)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_COMMAND_FAILED")
            self.assertEqual(projection["runtime_evidence_status"], "QWEN_COMMAND_FAILED")
            self.assertEqual(projection["qwen_exit_code"], 7)
            self.assertEqual(projection["turn_count"], 0)
            self.assertEqual(projection["tool_call_count"], 0)
            self.assertFalse(projection["session_ended"])
            self.assertFalse(projection["budget_stop"])
            self.assertEqual(projection["event_coverage"], "INCOMPLETE")
            terminal_receipts = list(receipt_directory.glob("QWEN_TERMINAL_OUTCOME-*.json"))
            self.assertEqual(len(terminal_receipts), 1)
            terminal_receipt = json.loads(terminal_receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(terminal_receipt["receipt_type"], "QWEN_TERMINAL_OUTCOME")
            self.assertTrue(terminal_receipt["terminal_receipt_written"])
            self.assertEqual(terminal_receipt["runtime_evidence_status"], "QWEN_COMMAND_FAILED")

    def test_protocol_applies_process_scoped_output_limit_and_restores_prior_value(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for process environment behavior")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fake_qwen = root / "fake-qwen.ps1"
            observed = root / "observed.txt"
            fake_qwen.write_text(
                "[IO.File]::WriteAllText($env:QWEN_FAKE_OBSERVED, $env:QWEN_CODE_MAX_OUTPUT_TOKENS)\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "QWEN_FAKE_OBSERVED": str(observed),
                    "QWEN_CODE_MAX_OUTPUT_TOKENS": "prior-value",
                    "QWEN_CLI_WRAPPER": str(CLI_COMPATIBILITY_CONSUMER),
                    "QWEN_FAKE_CLI": str(fake_qwen),
                    "QWEN_PROTOCOL_ARGS": json.dumps(
                        [
                            "--max-session-turns", "20", "--max-tool-calls", "20",
                            "--max-wall-time", "30m", "--max-subagent-depth", "1",
                            "--prompt", "/finish-ticket ticket 18",
                        ]
                    ),
                }
            )
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-Command",
                    ". $env:QWEN_CLI_WRAPPER -Mode protocol -QwenCommand $env:QWEN_FAKE_CLI -QwenArgumentsJson $env:QWEN_PROTOCOL_ARGS; Write-Output ('restored=' + $env:QWEN_CODE_MAX_OUTPUT_TOKENS)",
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(observed.read_text(encoding="utf-8"), "8000")
            self.assertIn("restored=prior-value", result.stdout)

    def test_protocol_event_sidecar_is_removed_when_qwen_throws(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fake_qwen = root / "fake-qwen.ps1"
            event_path_observation = root / "event-path.txt"
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "$jsonIndex = [Array]::IndexOf($Arguments, '--json-file')\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_EVENT_PATH, $Arguments[$jsonIndex + 1])\n"
                "throw 'private event content'\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update({
                "QWEN_FAKE_EVENT_PATH": str(event_path_observation),
                "QWEN_CLI_WRAPPER": str(CLI_COMPATIBILITY_CONSUMER),
                "QWEN_FAKE_CLI": str(fake_qwen),
                "QWEN_PROTOCOL_ARGS": json.dumps([
                    "--max-session-turns", "20", "--max-tool-calls", "20",
                    "--max-wall-time", "30m", "--max-subagent-depth", "1",
                    "--prompt", "/finish-ticket ticket 18",
                ]),
            })
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-Command",
                    ". $env:QWEN_CLI_WRAPPER -Mode protocol -QwenCommand $env:QWEN_FAKE_CLI -QwenArgumentsJson $env:QWEN_PROTOCOL_ARGS",
                ],
                check=False, capture_output=True, encoding="utf-8", env=environment,
            )

            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["reason"], "QWEN_COMMAND_FAILED")
            self.assertNotIn("private event content", result.stdout + result.stderr)
            event_path = Path(event_path_observation.read_text(encoding="utf-8"))
            self.assertFalse(event_path.exists())

    def test_protocol_preserves_projected_counters_when_qwen_exits_nonzero(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fake_qwen = root / "fake-qwen.ps1"
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "$jsonIndex = [Array]::IndexOf($Arguments, '--json-file')\n"
                "$eventPath = $Arguments[$jsonIndex + 1]\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_EVENT_PATH, $eventPath)\n"
                "[IO.File]::WriteAllLines($eventPath, [string[]]@('{\"type\":\"system\",\"subtype\":\"session_start\",\"session_id\":\"fixture-session\"}', '{\"type\":\"assistant\",\"message\":{\"id\":\"turn-1\",\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"PRIVATE\"}]}}', '{\"type\":\"system\",\"subtype\":\"session_end\",\"data\":{\"reason\":\"prompt_input_exit\"}}'), [Text.UTF8Encoding]::new($false))\n"
                "exit 7\n",
                encoding="utf-8",
            )
            event_path_observation = root / "event-path.txt"
            arguments = [
                "--max-session-turns", "20", "--max-tool-calls", "20",
                "--max-wall-time", "30m", "--max-subagent-depth", "1",
                "--prompt", "/finish-ticket ticket 18",
            ]
            environment = os.environ.copy()
            environment["QWEN_FAKE_EVENT_PATH"] = str(event_path_observation)
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-Command",
                    ". $env:QWEN_CLI_WRAPPER -Mode protocol -QwenCommand $env:QWEN_FAKE_CLI -QwenArgumentsJson $env:QWEN_PROTOCOL_ARGS",
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env={
                    **environment,
                    "QWEN_CLI_WRAPPER": str(CLI_COMPATIBILITY_CONSUMER),
                    "QWEN_FAKE_CLI": str(fake_qwen),
                    "QWEN_TEST_PYTHON": os.environ.get("PYTHON", "python"),
                    "QWEN_PROTOCOL_ARGS": json.dumps(arguments),
                },
            )

            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_COMMAND_FAILED")
            self.assertEqual(projection["runtime_evidence_status"], "COMPLETE")
            self.assertEqual(projection["turns"], 1)
            self.assertEqual(projection["tool_calls"], 0)
            self.assertNotIn("PRIVATE", result.stdout + result.stderr)
            # The Qwen sidecar is deleted even when the child returns a failure exit.
            event_path = Path(event_path_observation.read_text(encoding="utf-8"))
            self.assertFalse(event_path.exists())

    def test_recon_schema_requires_terminal_outcome_fields(self) -> None:
        schema = json.loads(RECON_SCHEMA.read_text(encoding="utf-8"))
        self.assertIn("stop_reason", schema["required"])
        self.assertIn("writes", schema["required"])
        evidence_found = next(
            constraint for constraint in schema["allOf"]
            if constraint.get("if", {}).get("properties", {}).get("status", {}).get("const") == "EVIDENCE_FOUND"
        )
        self.assertEqual(evidence_found["then"]["properties"]["stop_reason"], {"const": None})
        self.assertEqual(evidence_found["then"]["properties"]["writes"], {"maxItems": 0})

    def test_launcher_rejects_malformed_recon_terminal_outcome_fields(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1, "reasoningEffort": "xhigh",
                        },
                        "skipLoopDetection": True,
                        "maxToolCallsPerTurn": 1,
                        "maxSubagentDepth": 2,
                    }
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(json.dumps({"name": "proofloop-skills"}), encoding="utf-8")
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --worktree --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands plan'; exit 0 }\n"
                "Write-Output $env:QWEN_FAKE_REPORT\n",
                encoding="utf-8",
            )
            baseline = subprocess.run([GIT, "-C", str(recon_worktree), "rev-parse", "HEAD"], check=True, capture_output=True, encoding="utf-8").stdout.strip()
            valid = {
                "status": "EVIDENCE_FOUND", "baseline": baseline,
                "facts": [{"file": "README.md", "line": 1, "fact": "a"}, {"file": "README.md", "line": 1, "fact": "b"}, {"file": "README.md", "line": 1, "fact": "c"}],
                "state_owner": "owner", "callback_boundary": "none", "acceptance_risk": "none",
                "stop_reason": None, "writes": [],
            }
            malformed_reports = []
            for field, value in (("stop_reason", None), ("writes", None)):
                report = dict(valid)
                del report[field]
                malformed_reports.append(report)
            for field, value in (("writes", None), ("writes", [1]), ("stop_reason", []), ("stop_reason", "not-null")):
                report = dict(valid)
                report[field] = value
                malformed_reports.append(report)

            for report in malformed_reports:
                with self.subTest(report=report):
                    environment = os.environ.copy()
                    environment["QWEN_FAKE_REPORT"] = json.dumps(report)
                    result = subprocess.run(
                        [PWSH, "-NoProfile", "-File", str(LAUNCHER), "-Ticket", "20", "-Mode", "recon", "-SettingsPath", str(settings_path), "-ExtensionRoot", str(extension_root), "-ReceiptDirectory", str(receipt_directory), "-ReconWorktree", str(recon_worktree), "-QwenCommand", str(fake_qwen)],
                        check=False, capture_output=True, encoding="utf-8", env=environment,
                    )
                    self.assertEqual(result.returncode, 4, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["status"], "QWEN_UNUSABLE")
                    self.assertEqual(json.loads(result.stdout)["reason"], "MALFORMED_REPORT")

    def test_launcher_maps_structured_output_failure_to_raw_free_reason(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1, "reasoningEffort": "xhigh",
                        },
                        "skipLoopDetection": True,
                        "maxToolCallsPerTurn": 1,
                        "maxSubagentDepth": 99,
                    }
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --worktree --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "Write-Output '[{\"type\":\"result\",\"is_error\":true,\"errorType\":\"structured_output_missing\",\"errorMessage\":\"model did not produce structured output\"}]'\n"
                "exit 1\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_UNUSABLE")
            self.assertEqual(projection["reason"], "STRUCTURED_OUTPUT_MISSING")
            self.assertFalse(projection["role_dispatch"])
            self.assertFalse(projection["subagent_dispatch"])
            self.assertFalse(projection["acceptance"])
            self.assertNotIn("model did not produce structured output", result.stdout.lower())
            self.assertNotIn(str(temporary_root), result.stdout)

    def test_launcher_maps_qwen_json_error_result_to_structured_output_reason(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "Write-Output '[{\"type\":\"assistant\",\"message\":{\"content\":[]}}, {\"type\":\"result\",\"subtype\":\"error_during_execution\",\"is_error\":true,\"error\":{\"message\":\"model did not produce structured output\"}}]'\n"
                "exit 1\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 4, result.stderr)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_UNUSABLE")
            self.assertEqual(projection["reason"], "STRUCTURED_OUTPUT_MISSING")
            self.assertEqual(projection["diagnostic"]["stdout_json"], True)
            self.assertEqual(projection["diagnostic"]["structured_output_channel"], "stdout")
            self.assertEqual(projection["diagnostic"]["json_shape"], "array")
            self.assertTrue(projection["diagnostic"]["terminal_result"])
            self.assertTrue(projection["diagnostic"]["terminal_is_error"])
            self.assertEqual(projection["diagnostic"]["terminal_subtype"], "error_during_execution")
            self.assertTrue(projection["diagnostic"]["error_message_present"])
            self.assertEqual(projection["diagnostic"]["error_message_category"], "structured_output_missing")
            self.assertNotIn("model did not produce structured output", result.stdout.lower())

    def test_launcher_classifies_qwen_json_auth_error_without_raw_message(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "Write-Output '[{\"type\":\"result\",\"subtype\":\"error_during_execution\",\"is_error\":true,\"error\":{\"message\":\"HTTP 403 Forbidden\"}}]'\n"
                "exit 1\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 4, result.stderr)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_UNUSABLE")
            self.assertEqual(projection["reason"], "QWEN_JSON_ERROR_RESULT")
            self.assertEqual(projection["diagnostic"]["error_message_category"], "auth_or_forbidden")
            self.assertNotIn("403 Forbidden", result.stdout)

    def test_launcher_classifies_top_level_qwen_json_error_envelope_without_raw_message(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "cmd.exe /c 'echo {\"is_error\":true,\"subtype\":\"error_during_execution\",\"error\":{\"message\":\"HTTP 403 Forbidden\"}} 1>&2'\n"
                "exit 1\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_UNUSABLE")
            self.assertEqual(projection["reason"], "QWEN_JSON_ERROR_RESULT")
            diagnostic = projection["diagnostic"]
            self.assertTrue(diagnostic["stderr_json"])
            self.assertEqual(diagnostic["json_shape"], "object")
            self.assertFalse(diagnostic["terminal_result"])
            self.assertTrue(diagnostic["envelope_is_error"])
            self.assertEqual(diagnostic["envelope_subtype"], "error_during_execution")
            self.assertTrue(diagnostic["envelope_error_message_present"])
            self.assertEqual(diagnostic["envelope_error_message_category"], "auth_or_forbidden")
            self.assertNotIn("403 Forbidden", result.stdout)

    def test_launcher_accepts_schema_valid_terminal_after_windows_native_abort(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            baseline = subprocess.run(
                [GIT, "-C", str(recon_worktree), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                encoding="utf-8",
            ).stdout.strip()
            report = {
                "status": "EVIDENCE_FOUND",
                "baseline": baseline,
                "facts": [
                    {"file": "README.md", "line": 1, "fact": "clean fixture"},
                    {"file": "README.md", "line": 1, "fact": "fixed point"},
                    {"file": "README.md", "line": 1, "fact": "read only"},
                ],
                "state_owner": "owner",
                "callback_boundary": "none",
                "acceptance_risk": "none",
                "stop_reason": None,
                "writes": [],
            }
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "Write-Output $env:QWEN_FAKE_OUTPUT\n"
                "exit -1073740791\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_FAKE_OUTPUT"] = json.dumps(
                [
                    {"type": "assistant", "message": {"content": []}},
                    {"type": "result", "subtype": "success", "is_error": False, "structured_result": report},
                ]
            )

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_RECON_READY")
            self.assertEqual(projection["report"], report)

    def test_launcher_diagnoses_structured_output_failure_from_stderr(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --worktree --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "Write-Error 'Model produced plain text instead of calling the structured_output tool.' -ErrorAction Continue\n"
                "exit 1\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 4, result.stderr)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_UNUSABLE")
            self.assertEqual(projection["reason"], "STRUCTURED_OUTPUT_MISSING")
            self.assertEqual(
                projection["diagnostic"],
                {
                    "stdout_present": False,
                    "stderr_present": True,
                    "stdout_json": False,
                    "stderr_json": False,
                    "structured_output_channel": "stderr",
                    "json_shape": "none",
                    "terminal_result": False,
                    "terminal_is_error": False,
                    "terminal_subtype": "none",
                    "error_message_present": False,
                    "error_message_category": "structured_output_missing",
                    "envelope_is_error": False,
                    "envelope_subtype": "none",
                    "envelope_error_message_present": False,
                    "envelope_error_message_category": "none",
                },
            )
            self.assertNotIn("Model produced plain text", result.stdout)
            self.assertNotIn(str(temporary_root), result.stdout)

    def test_launcher_blocks_unsafe_inputs_and_writes_raw_free_receipt_for_guarded_session(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            reached_path = temporary_root / "fake-qwen-reached.txt"
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1, "reasoningEffort": "xhigh",
                        }
                    }
                ),
                encoding="utf-8",
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --json-file'; exit 0 }\n"
                "$jsonIndex = [Array]::IndexOf($Arguments, '--json-file')\n"
                "if ($jsonIndex -ge 0) { [IO.File]::WriteAllLines($Arguments[$jsonIndex + 1], [string[]]@('{\"type\":\"system\",\"subtype\":\"session_start\",\"session_id\":\"fixture-session\"}', '{\"type\":\"assistant\",\"message\":{\"id\":\"m1\",\"role\":\"assistant\",\"content\":[]}}', '{\"type\":\"system\",\"subtype\":\"session_end\",\"data\":{\"reason\":\"prompt_input_exit\"}}'), [Text.UTF8Encoding]::new($false)) }\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_REACHED, ($Arguments -join [Environment]::NewLine))\n",
                encoding="utf-8",
            )

            def launch(*extra_arguments: str) -> subprocess.CompletedProcess[str]:
                environment = os.environ.copy()
                environment["QWEN_FAKE_REACHED"] = str(reached_path)
                return subprocess.run(
                    [
                        PWSH,
                        "-NoProfile",
                        "-File",
                        str(LAUNCHER),
                        "-Ticket",
                        "16",
                        "-Mode",
                        "protocol",
                        "-SettingsPath",
                        str(settings_path),
                        "-ExtensionRoot",
                        str(extension_root),
                        "-ReceiptDirectory",
                        str(receipt_directory),
                        "-QwenCommand",
                        str(fake_qwen),
                        *extra_arguments,
                    ],
                    check=False,
                    capture_output=True,
                    encoding="utf-8",
                    env=environment,
                )

            blocked_cases = (
                ("safe-mode", ("-SafeMode",), "SAFE_MODE_REQUESTED"),
                ("loop-detection", (), "LOOP_DETECTION_DISABLED"),
                ("nesting", (), "MAX_SUBAGENT_DEPTH_EXCEEDED"),
                ("extension", (), "PROOFLOOP_EXTENSION_MISSING"),
            )
            for case, extra_arguments, expected_reason in blocked_cases:
                if case == "loop-detection":
                    settings_path.write_text(
                        json.dumps({"model": {"skipLoopDetection": True, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}),
                        encoding="utf-8",
                    )
                elif case == "nesting":
                    settings_path.write_text(
                        json.dumps({"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 2}}),
                        encoding="utf-8",
                    )
                else:
                    settings_path.write_text(
                        json.dumps({"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}),
                        encoding="utf-8",
                    )
                with self.subTest(case=case):
                    result = launch(*extra_arguments)
                    self.assertEqual(result.returncode, 3)
                    projection = json.loads(result.stdout)
                    self.assertEqual(projection["status"], "BLOCKED_CAPABILITY")
                    self.assertEqual(projection["reason"], expected_reason)
                    self.assertEqual(projection["mode"], "protocol")
                    self.assertEqual(projection["terminal_reason"], expected_reason)
                    self.assertEqual(projection["turn_count"], 0)
                    self.assertEqual(projection["tool_call_count"], 0)
                    self.assertGreaterEqual(projection["duration_ms"], 0)
                    self.assertFalse(reached_path.exists())

            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            result = launch()

            self.assertEqual(
                result.returncode,
                0,
                f"{result.stderr}{result.stdout}; fake_child_reached={reached_path.exists()}",
            )
            status = json.loads(result.stdout)
            self.assertEqual(status["status"], "QWEN_SESSION_GUARD_READY")
            self.assertEqual(status["mode"], "protocol")
            self.assertEqual(status["terminal_reason"], "QWEN_SESSION_GUARD_READY")
            self.assertEqual(status["runtime_evidence_status"], "COMPLETE")
            self.assertEqual(status["turn_count"], 1)
            self.assertEqual(status["tool_call_count"], 0)
            self.assertFalse(status["budget_stop"])
            self.assertEqual(status["loop_status"], "HOST_CLEAR")
            self.assertGreaterEqual(status["duration_ms"], 0)
            self.assertNotIn(str(temporary_root), result.stdout)
            self.assertNotIn("SECRET", result.stdout.upper())
            self.assertTrue(reached_path.is_file())
            recorded_arguments = reached_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                recorded_arguments[:10],
                [
                    "--max-session-turns",
                    "20",
                    "--max-tool-calls",
                    "20",
                    "--max-wall-time",
                    "30m",
                    "--max-subagent-depth",
                    "1",
                    "--prompt",
                    "/finish-ticket ticket 16",
                ],
            )
            self.assertEqual(recorded_arguments[10], "--json-file")
            self.assertFalse(Path(recorded_arguments[11]).exists())
            receipts = list(receipt_directory.glob("QWEN_SESSION_GUARD-*.json"))
            self.assertEqual(len(receipts), 1)
            receipt_text = receipts[0].read_text(encoding="utf-8")
            receipt = json.loads(receipt_text)
            self.assertEqual(receipt["receipt_type"], "QWEN_SESSION_GUARD")
            self.assertEqual(receipt["launch_id"], status["launch_id"])
            self.assertEqual(receipt["mode"], "protocol")
            self.assertEqual(receipt["receipt_version"], 1)
            self.assertRegex(receipt["issued_at_utc"], r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")
            self.assertEqual(
                receipt["limits"],
                {"max_session_turns": 20, "max_tool_calls": 20, "max_wall_time": "30m", "max_subagent_depth": 1},
            )
            self.assertTrue(receipt["loop_detection"])
            self.assertTrue(receipt["extension_available"])
            self.assertNotIn(str(temporary_root), receipt_text)
            self.assertNotIn("SECRET", receipt_text.upper())

    def test_launcher_dispatches_once_after_valid_checkpoint_adapter_gate(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            host_repo = temporary_root / "checkpoint-host"
            host_repo.mkdir()
            baseline = init_adapter_repo(host_repo)
            (host_repo / "fixture.py").write_text("after = True\n", encoding="utf-8")
            facts = RUNTIME_ADAPTER.collect_host_facts(
                host_repo, ticket="314", task_source="tickets.md", scope_source="scope.md"
            )
            ledger = AdapterFixtures.make_progress_ledger(facts)
            test_receipt = AdapterFixtures.make_receipt(facts, ledger["events"][0], kind="test", status="GREEN")
            checkpoint = AdapterFixtures.make_checkpoint(facts, ledger, test_receipt)
            evidence = {
                "operation": "prepare_continuation",
                "repo_root": str(host_repo),
                "ticket": "314",
                "task_source": "tickets.md",
                "scope_source": "scope.md",
                "runtime_payload": AdapterFixtures.prior_runtime_payload(baseline, facts, checkpoint),
                "progress_ledger": ledger,
                "test_receipt": test_receipt,
                "review_receipt": None,
                "continuation_context": "Complete the next measurable closure in the existing scope.",
                "prior_projection": AdapterFixtures.prior_terminal_receipt(),
            }
            evidence_path = temporary_root / "controller-evidence.json"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

            settings_path = temporary_root / "settings.json"
            settings_path.write_text(json.dumps({"model": {
                "skipLoopDetection": False,
                "maxToolCallsPerTurn": 20,
                "maxSubagentDepth": 1,
                "reasoningEffort": "xhigh",
            }}), encoding="utf-8")
            extension_root = temporary_root / "proofloop-skills"
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(json.dumps({"name": "proofloop-skills"}), encoding="utf-8")
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            reached_path = temporary_root / "reached.json"
            argument_summary_path = temporary_root / "argument-summary.json"
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --json-file'; exit 0 }\n"
                "$promptIndex = [Array]::IndexOf($Arguments, '--prompt')\n"
                "$jsonIndex = [Array]::IndexOf($Arguments, '--json-file')\n"
                "$promptHasMarker = $promptIndex -ge 0 -and $Arguments[$promptIndex + 1] -match 'PROOFLOOP_VERIFIED_CONTINUATION'\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_ARGUMENT_SUMMARY, (@{ count=$Arguments.Count; prompt_index=$promptIndex; prompt_has_marker=$promptHasMarker; json_index=$jsonIndex } | ConvertTo-Json -Compress))\n"
                "if ($Arguments[$promptIndex + 1] -notmatch 'PROOFLOOP_VERIFIED_CONTINUATION' -or $jsonIndex -lt 0) { exit 9 }\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_REACHED, ($Arguments | ConvertTo-Json -Compress))\n"
                "[IO.File]::WriteAllLines($Arguments[$jsonIndex + 1], [string[]]@('{\"type\":\"system\",\"subtype\":\"session_start\",\"session_id\":\"fixture-session\"}', '{\"type\":\"system\",\"subtype\":\"session_end\",\"data\":{\"reason\":\"prompt_input_exit\"}}'), [Text.UTF8Encoding]::new($false))\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_FAKE_REACHED"] = str(reached_path)
            environment["QWEN_FAKE_ARGUMENT_SUMMARY"] = str(argument_summary_path)
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(LAUNCHER),
                    "-Ticket", "314", "-Mode", "protocol",
                    "-SettingsPath", str(settings_path),
                    "-ExtensionRoot", str(extension_root),
                    "-ReceiptDirectory", str(receipt_directory),
                    "-QwenCommand", str(fake_qwen),
                    "-ContinuationEvidencePath", str(evidence_path),
                ],
                check=False, capture_output=True, encoding="utf-8", env=environment,
            )

            argument_summary = argument_summary_path.read_text(encoding="utf-8") if argument_summary_path.exists() else "not-started"
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout + argument_summary)
            status = json.loads(result.stdout)
            self.assertEqual(status["status"], "QWEN_SESSION_GUARD_READY")
            executed = json.loads(reached_path.read_text(encoding="utf-8"))
            self.assertEqual(executed.count("--prompt"), 1)
            self.assertEqual(executed.count("--json-file"), 1)
            self.assertTrue(any("PROOFLOOP_VERIFIED_CONTINUATION" in arg for arg in executed))
            self.assertEqual(len(list(receipt_directory.glob("QWEN_CHECKPOINT-CONSUMED-*.json"))), 1)
            self.assertEqual(len(list(receipt_directory.glob("QWEN_PROGRESS-CONSUMED-*.json"))), 1)
            self.assertEqual(len(list(receipt_directory.glob("QWEN_RUNTIME_LEDGER-*.json"))), 1)

    def test_launcher_blocks_missing_cli_capability_before_ticket_work(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            reached_path = temporary_root / "fake-qwen-reached.txt"
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1, "reasoningEffort": "xhigh",
                        }
                    }
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --max-session-turns --max-wall-time --max-subagent-depth'; exit 0 }\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_REACHED, ($Arguments -join [Environment]::NewLine))\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["QWEN_FAKE_REACHED"] = str(reached_path)
            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "19",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
            )

            self.assertEqual(result.returncode, 3)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "BLOCKED_CAPABILITY")
            self.assertEqual(projection["reason"], "QWEN_CLI_CAPABILITY_MISSING")
            self.assertEqual(projection["mode"], "protocol")
            self.assertEqual(projection["terminal_reason"], "QWEN_CLI_CAPABILITY_MISSING")
            self.assertEqual(projection["turn_count"], 0)
            self.assertEqual(projection["tool_call_count"], 0)
            self.assertGreaterEqual(projection["duration_ms"], 0)
            self.assertFalse(reached_path.exists())

    def test_launcher_blocks_invalid_continuation_evidence_before_model_dispatch(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            extension_root = root / "proofloop-skills"
            receipt_directory = root / "receipts"
            fake_qwen = root / "fake-qwen.ps1"
            reached_path = root / "reached.txt"
            evidence_path = root / "invalid-evidence.json"
            settings_path.write_text(
                json.dumps({"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(json.dumps({"name": "proofloop-skills"}), encoding="utf-8")
            evidence_path.write_text("{}", encoding="utf-8")
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --json-file'; exit 0 }\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_REACHED, 'reached')\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_FAKE_REACHED"] = str(reached_path)
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(LAUNCHER), "-Ticket", "314",
                    "-SettingsPath", str(settings_path), "-ExtensionRoot", str(extension_root),
                    "-ReceiptDirectory", str(receipt_directory), "-QwenCommand", str(fake_qwen),
                    "-ContinuationEvidencePath", str(evidence_path),
                ],
                check=False, capture_output=True, encoding="utf-8", env=environment,
            )

            self.assertEqual(result.returncode, 3)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "BLOCKED_CAPABILITY")
            self.assertEqual(projection["reason"], "CONTROLLER_EVIDENCE_INVALID")
            self.assertFalse(reached_path.exists())
            self.assertNotIn(str(root), result.stdout)

    def test_qwen_cli_compatibility_consumer_allows_only_the_operator_argv_contract(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        expected_arguments = [
            "--max-session-turns",
            "20",
            "--max-tool-calls",
            "20",
            "--max-wall-time",
            "30m",
            "--max-subagent-depth",
            "1",
            "--prompt",
            "/finish-ticket ticket 16",
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            fake_qwen = temporary_root / "strict-fake-qwen.ps1"
            reached_path = temporary_root / "strict-fake-qwen-reached.json"
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "$expected = @('--max-session-turns', '20', '--max-tool-calls', '20', '--max-wall-time', '30m', '--max-subagent-depth', '1', '--prompt', '/finish-ticket ticket 16')\n"
                "if ($Arguments.Count -ne ($expected.Count + 2) -or @(0..($expected.Count - 1) | Where-Object { $Arguments[$_] -ne $expected[$_] }).Count -ne 0 -or $Arguments[$expected.Count] -ne '--json-file') { exit 9 }\n"
                "[IO.File]::WriteAllLines($Arguments[$expected.Count + 1], [string[]]@('{\"type\":\"system\",\"subtype\":\"session_start\",\"session_id\":\"fixture-session\"}', '{\"type\":\"system\",\"subtype\":\"session_end\",\"data\":{\"reason\":\"prompt_input_exit\"}}'), [Text.UTF8Encoding]::new($false))\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_REACHED, ($Arguments | ConvertTo-Json -Compress))\n",
                encoding="utf-8",
            )

            def consume(arguments: list[str]) -> subprocess.CompletedProcess[str]:
                environment = os.environ.copy()
                environment["QWEN_FAKE_REACHED"] = str(reached_path)
                return subprocess.run(
                    [
                        PWSH,
                        "-NoProfile",
                        "-File",
                        str(CLI_COMPATIBILITY_CONSUMER),
                        "-QwenCommand",
                        str(fake_qwen),
                        "-QwenArgumentsJson",
                        json.dumps(arguments),
                    ],
                    check=False,
                    capture_output=True,
                    encoding="utf-8",
                    env=environment,
                )

            accepted = consume(expected_arguments)
            self.assertEqual(accepted.returncode, 0)
            executed = json.loads(reached_path.read_text(encoding="utf-8"))
            self.assertEqual(executed[: len(expected_arguments)], expected_arguments)
            self.assertEqual(executed[len(expected_arguments)], "--json-file")
            self.assertFalse(Path(executed[len(expected_arguments) + 1]).exists())

            for rejected_arguments in (
                expected_arguments[:-1],
                [*expected_arguments, "--safe-mode"],
                ["--safe-mode", *expected_arguments],
            ):
                if reached_path.exists():
                    reached_path.unlink()
                with self.subTest(arguments=rejected_arguments):
                    rejected = consume(rejected_arguments)
                    self.assertEqual(rejected.returncode, 5)
                    self.assertEqual(
                        json.loads(rejected.stdout),
                        {"status": "QWEN_COMMAND_REJECTED", "reason": "QWEN_ARGUMENT_CONTRACT_INVALID"},
                    )
                    self.assertFalse(reached_path.exists())

    def test_launcher_recon_is_read_only_bounded_and_returns_structured_report(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            arguments_path = temporary_root / "recon-arguments.json"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1, "reasoningEffort": "xhigh",
                        }
                    }
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --worktree --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands plan'; exit 0 }\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_ARGUMENTS, ($Arguments | ConvertTo-Json -Compress))\n"
                "@{ status = 'EVIDENCE_FOUND'; baseline = $env:QWEN_FAKE_BASELINE; facts = @(@{ file = 'README.md'; line = 1; fact = 'Fixture is clean.' }, @{ file = 'README.md'; line = 1; fact = 'No write capability is granted.' }, @{ file = 'README.md'; line = 1; fact = 'No acceptance path is present.' }); state_owner = 'fixture owner'; callback_boundary = 'none'; acceptance_risk = 'recon is not acceptance'; stop_reason = $null; writes = @() } | ConvertTo-Json -Compress\n"
                "exit 0\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["QWEN_FAKE_ARGUMENTS"] = str(arguments_path)
            environment["QWEN_FAKE_BASELINE"] = subprocess.run(
                [GIT, "-C", str(recon_worktree), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                encoding="utf-8",
            ).stdout.strip()
            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-ReconSchemaPath",
                    str(REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist-recon.schema.json"),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "QWEN_RECON_READY")
            self.assertFalse(projection["role_dispatch"])
            self.assertFalse(projection["subagent_dispatch"])
            self.assertFalse(projection["acceptance"])
            self.assertEqual(projection["report"]["status"], "EVIDENCE_FOUND")
            arguments = json.loads(arguments_path.read_text(encoding="utf-8"))
            self.assertEqual(arguments[0:7], ["--bare", "--approval-mode", "plan", "--output-format", "json", "--json-schema", "@" + str(REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist-recon.schema.json")])
            self.assertNotIn("--worktree", arguments)
            self.assertEqual(arguments[arguments.index("--max-session-turns") + 1], "3")
            self.assertEqual(arguments[arguments.index("--max-tool-calls") + 1], "6")
            self.assertEqual(arguments[arguments.index("--max-wall-time") + 1], "5m")
            self.assertEqual(arguments[arguments.index("--max-subagent-depth") + 1], "1")
            self.assertEqual(arguments[arguments.index("--exclude-tools") + 1], "Agent,edit,notebook_edit,run_shell_command")
            self.assertEqual(arguments[arguments.index("--disabled-slash-commands") + 1], "review,loop")
            prompt = arguments[arguments.index("--prompt") + 1]
            self.assertEqual(
                prompt,
                "Inspect only README.md in the current clean worktree using read-only file inspection. "
                "The baseline is " + environment["QWEN_FAKE_BASELINE"] + ". "
                "Then call structured_output exactly once with a schema-valid EVIDENCE_FOUND report containing "
                "at least three concrete facts. Set baseline exactly to " + environment["QWEN_FAKE_BASELINE"] + ". "
                "Do not edit files, run commands, or use network.",
            )
            self.assertNotIn("/finish-ticket", arguments)
            receipt_path = next(receipt_directory.glob("*.json"))
            self.assertTrue(receipt_path.name.startswith("QWEN_RECON_GUARD-"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["receipt_type"], "QWEN_RECON_GUARD")
            identity_fields = ("launch_id", "session_id", "ledger_id", "fresh_evidence_id")
            self.assertTrue(all(field in receipt for field in identity_fields))
            for field in identity_fields:
                self.assertRegex(receipt[field], r"^[0-9a-f]{32}$")
            self.assertTrue(receipt["read_only"])
            self.assertFalse(receipt["role_dispatch"])
            self.assertFalse(receipt["subagent_dispatch"])
            self.assertFalse(receipt["acceptance"])
            self.assertTrue(receipt["structured_output"])
            self.assertTrue(receipt["worktree_clean"])
            self.assertNotIn(str(temporary_root), result.stdout)
            receipt_text = json.dumps(receipt)
            self.assertNotIn(str(temporary_root), receipt_text)
            self.assertNotIn("SECRET", receipt_text.upper())

            second = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(LAUNCHER), "-Ticket", "20", "-Mode", "recon",
                    "-SettingsPath", str(settings_path), "-ExtensionRoot", str(extension_root),
                    "-ReceiptDirectory", str(receipt_directory), "-ReconWorktree", str(recon_worktree),
                    "-ReconSchemaPath", str(REPOSITORY_ROOT / "plugins" / "agentic-development-workflow" / "skills" / "finish-ticket" / "references" / "qwen-assist-recon.schema.json"),
                    "-QwenCommand", str(fake_qwen),
                ],
                check=False, capture_output=True, encoding="utf-8", env=environment,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            receipts = [json.loads(path.read_text(encoding="utf-8")) for path in receipt_directory.glob("*.json")]
            self.assertEqual(len(receipts), 2)
            for field in identity_fields:
                self.assertNotEqual(receipts[0][field], receipts[1][field], field)
            self.assertNotEqual(receipts[0]["fresh_evidence_id"], receipts[1]["fresh_evidence_id"])

            launcher_text = LAUNCHER.read_text(encoding="utf-8")
            self.assertIn("$used.Contains($candidate)", launcher_text)
            self.assertIn("do {", launcher_text)

    def test_launcher_recon_runs_qwen_from_validated_worktree_without_worktree_flag(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            arguments_path = temporary_root / "recon-runtime.json"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps(
                    {
                        "model": {
                            "skipLoopDetection": False,
                            "maxToolCallsPerTurn": 20,
                            "maxSubagentDepth": 1, "reasoningEffort": "xhigh",
                        }
                    }
                ),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "@{ cwd = (Get-Location).Path; arguments = $Arguments } | ConvertTo-Json -Compress | Set-Content -LiteralPath $env:QWEN_FAKE_RUNTIME -Encoding utf8\n"
                "@{ status = 'EVIDENCE_FOUND'; baseline = $env:QWEN_FAKE_BASELINE; facts = @(@{ file = 'README.md'; line = 1; fact = 'Fixture is clean.' }, @{ file = 'README.md'; line = 1; fact = 'No write capability is granted.' }, @{ file = 'README.md'; line = 1; fact = 'No acceptance path is present.' }); state_owner = 'fixture owner'; callback_boundary = 'none'; acceptance_risk = 'recon is not acceptance'; stop_reason = $null; writes = @() } | ConvertTo-Json -Compress\n"
                "exit 0\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["QWEN_FAKE_RUNTIME"] = str(arguments_path)
            environment["QWEN_FAKE_BASELINE"] = subprocess.run(
                [GIT, "-C", str(recon_worktree), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                encoding="utf-8",
            ).stdout.strip()
            result = subprocess.run(
                [
                    PWSH,
                    "-NoProfile",
                    "-File",
                    str(LAUNCHER),
                    "-Ticket",
                    "20",
                    "-Mode",
                    "recon",
                    "-SettingsPath",
                    str(settings_path),
                    "-ExtensionRoot",
                    str(extension_root),
                    "-ReceiptDirectory",
                    str(receipt_directory),
                    "-ReconWorktree",
                    str(recon_worktree),
                    "-ReconSchemaPath",
                    str(RECON_SCHEMA),
                    "-QwenCommand",
                    str(fake_qwen),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            runtime = json.loads(arguments_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(
                Path(runtime["cwd"]).resolve(),
                recon_worktree.resolve(),
            )
            self.assertNotIn("--worktree", runtime["arguments"])

    def test_launcher_recon_blocks_dirty_worktree_before_qwen_execution(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "dirty-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            reached_path = temporary_root / "reached.txt"
            create_clean_git_worktree(recon_worktree)
            (recon_worktree / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
            settings_path.write_text(
                json.dumps({"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_REACHED, 'reached')\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --json-schema --worktree --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_FAKE_REACHED"] = str(reached_path)
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(LAUNCHER), "-Ticket", "20", "-Mode", "recon",
                    "-SettingsPath", str(settings_path), "-ExtensionRoot", str(extension_root),
                    "-ReceiptDirectory", str(receipt_directory), "-ReconWorktree", str(recon_worktree),
                    "-QwenCommand", str(fake_qwen),
                ],
                check=False, capture_output=True, encoding="utf-8", env=environment,
            )

            self.assertEqual(result.returncode, 3)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "BLOCKED_CAPABILITY")
            self.assertEqual(projection["reason"], "WORKTREE_NOT_CLEAN")
            self.assertFalse(projection["role_dispatch"])
            self.assertFalse(projection["subagent_dispatch"])
            self.assertFalse(projection["acceptance"])
            self.assertEqual(projection["mode"], "recon")
            self.assertEqual(projection["terminal_reason"], "WORKTREE_NOT_CLEAN")
            self.assertEqual(projection["turn_count"], 0)
            self.assertEqual(projection["tool_call_count"], 0)
            self.assertGreaterEqual(projection["duration_ms"], 0)
            self.assertFalse(reached_path.exists())
            self.assertFalse(receipt_directory.exists())

    def test_launcher_recon_blocks_missing_structured_output_capability(self) -> None:
        self.assertIsNotNone(PWSH, "PowerShell is required for the launcher contract")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            settings_path = temporary_root / "settings.json"
            extension_root = temporary_root / "proofloop-skills"
            recon_worktree = temporary_root / "clean-worktree"
            receipt_directory = temporary_root / "receipts"
            fake_qwen = temporary_root / "fake-qwen.ps1"
            reached_path = temporary_root / "reached.txt"
            create_clean_git_worktree(recon_worktree)
            settings_path.write_text(
                json.dumps({"model": {"skipLoopDetection": False, "maxToolCallsPerTurn": 20, "maxSubagentDepth": 1, "reasoningEffort": "xhigh"}}),
                encoding="utf-8",
            )
            extension_root.mkdir()
            (extension_root / "qwen-extension.json").write_text(
                json.dumps({"name": "proofloop-skills"}), encoding="utf-8"
            )
            fake_qwen.write_text(
                "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
                "if ($Arguments -contains '--help') { Write-Output '--prompt --bare --approval-mode --output-format --worktree --max-session-turns --max-tool-calls --max-wall-time --max-subagent-depth --exclude-tools --disabled-slash-commands --no-thinking plan'; exit 0 }\n"
                "[IO.File]::WriteAllText($env:QWEN_FAKE_REACHED, 'reached')\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_FAKE_REACHED"] = str(reached_path)
            result = subprocess.run(
                [
                    PWSH, "-NoProfile", "-File", str(LAUNCHER), "-Ticket", "20", "-Mode", "recon",
                    "-SettingsPath", str(settings_path), "-ExtensionRoot", str(extension_root),
                    "-ReceiptDirectory", str(receipt_directory), "-ReconWorktree", str(recon_worktree),
                    "-QwenCommand", str(fake_qwen),
                ],
                check=False, capture_output=True, encoding="utf-8", env=environment,
            )

            self.assertEqual(result.returncode, 3)
            projection = json.loads(result.stdout)
            self.assertEqual(projection["status"], "BLOCKED_CAPABILITY")
            self.assertEqual(projection["reason"], "QWEN_CLI_CAPABILITY_MISSING")
            self.assertFalse(projection["role_dispatch"])
            self.assertFalse(reached_path.exists())
            self.assertFalse(receipt_directory.exists())


if __name__ == "__main__":
    unittest.main()
