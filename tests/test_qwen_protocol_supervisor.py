from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_qwen_runtime_adapter import ADAPTER


ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "scripts" / "qwen_protocol_supervisor.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(os.name == "nt" and PWSH, "Windows PowerShell process-group contract")
class QwenProtocolSupervisorTest(unittest.TestCase):
    def run_supervisor(
        self, *, scenario: str, max_tools: int = 20, wall_seconds: int = 10,
        extra_arguments: tuple[str, ...] = (),
        command_kind: str = "ps1",
    ) -> tuple[dict[str, object], str, str, list[str], dict[str, bool]]:
        with tempfile.TemporaryDirectory(prefix="proofloop qwen supervisor ") as directory:
            root = Path(directory)
            event_path = root / "qwen events.jsonl"
            worker_path = root / "fake qwen.ps1"
            command_path = root / "qwen.cmd"
            runner_path = root / "run supervisor.ps1"
            arguments_path = root / "observed arguments.json"
            console_path = root / "observed console.json"
            unsupported_marker = root / "unsupported wrapper was executed.txt"
            worker_path.write_text(self.fake_worker(scenario), encoding="utf-8")
            if command_kind == "ps1":
                command = worker_path
            elif command_kind == "recognized_node_shim":
                entry_path = root / "node_modules" / "@qwen-code" / "qwen-code" / "cli-entry.js"
                entry_path.parent.mkdir(parents=True)
                entry_path.write_text(self.fake_node_worker(), encoding="utf-8")
                command_path.write_text(self.node_shim(), encoding="utf-8")
                command = command_path
            elif command_kind == "unsupported_cmd":
                command_path.write_text(
                    f'@echo off\r\necho executed>{unsupported_marker}\r\n',
                    encoding="utf-8",
                )
                command = command_path
            else:
                raise ValueError("unknown command kind")
            runner_path.write_text(
                "param()\n"
                f". '{SUPERVISOR}'\n"
                "$qwenArguments = @('--json-file', $env:QWEN_TEST_EVENT_FILE)\n"
                "if ($env:QWEN_TEST_EXTRA_ARGUMENTS) { $qwenArguments += @(ConvertFrom-Json -InputObject $env:QWEN_TEST_EXTRA_ARGUMENTS) }\n"
                "$result = Invoke-QwenProtocolChild `\n"
                "  -QwenCommand $env:QWEN_TEST_COMMAND `\n"
                "  -QwenArguments $qwenArguments `\n"
                "  -EventFilePath $env:QWEN_TEST_EVENT_FILE `\n"
                "  -LaunchId ('a' * 32) `\n"
                f"  -MaxToolCalls {max_tools} `\n"
                f"  -MaxWallTimeSeconds {wall_seconds}\n"
                "$result.process_observation | ConvertTo-Json -Compress -Depth 5\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_TEST_COMMAND"] = str(command)
            environment["QWEN_TEST_EVENT_FILE"] = str(event_path)
            environment["QWEN_FAKE_WORKER"] = scenario
            environment["QWEN_TEST_EXTRA_ARGUMENTS"] = json.dumps(extra_arguments)
            environment["QWEN_FAKE_ARGS_OUTPUT"] = str(arguments_path)
            environment["QWEN_FAKE_CONSOLE_OUTPUT"] = str(console_path)
            environment["QWEN_FAKE_UNSUPPORTED_MARKER"] = str(unsupported_marker)
            completed = subprocess.run(
                [PWSH, "-NoProfile", "-File", str(runner_path)],
                capture_output=True,
                text=True,
                timeout=20,
                env=environment,
                check=False,
            )
            if completed.returncode != 0:
                self.fail(f"supervisor failed closed: exit={completed.returncode}; stderr={completed.stderr!r}")
            event_text = event_path.read_bytes().decode("utf-8") if event_path.exists() else ""
            observed_arguments = json.loads(arguments_path.read_text(encoding="utf-8")) if arguments_path.exists() else []
            console_observation = json.loads(console_path.read_text(encoding="utf-8")) if console_path.exists() else {}
            return (
                json.loads(completed.stdout.strip().splitlines()[-1]),
                completed.stdout + completed.stderr,
                event_text,
                observed_arguments,
                console_observation,
            )

    @staticmethod
    def fake_worker(scenario: str) -> str:
        common = (
            "param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments)\n"
            "$jsonIndex = [Array]::IndexOf($Arguments, '--json-file')\n"
            "$eventPath = $Arguments[$jsonIndex + 1]\n"
            "$encoding = [Text.UTF8Encoding]::new($false)\n"
            "if ($env:QWEN_FAKE_ARGS_OUTPUT) { [IO.File]::WriteAllText($env:QWEN_FAKE_ARGS_OUTPUT, (ConvertTo-Json -InputObject @($Arguments) -Compress)) }\n"
            "if ($env:QWEN_FAKE_CONSOLE_OUTPUT) { [IO.File]::WriteAllText($env:QWEN_FAKE_CONSOLE_OUTPUT, (ConvertTo-Json -InputObject @{ input=[Console]::IsInputRedirected; output=[Console]::IsOutputRedirected; error=[Console]::IsErrorRedirected } -Compress)) }\n"
            "[IO.File]::WriteAllText($eventPath, '{\"type\":\"system\",\"subtype\":\"session_start\",\"session_id\":\"private-session\"}' + [char]10, $encoding)\n"
        )
        if scenario == "graceful":
            return common + QwenProtocolSupervisorTest.console_handler(write_end=True)
        if scenario == "tool_wait":
            tool_events = (
                "[IO.File]::AppendAllText($eventPath, '{\"type\":\"assistant\",\"message\":{\"id\":\"fake-turn\",\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"Inspect file\"},{\"type\":\"tool_use\",\"id\":\"fake-tool-1\",\"name\":\"read_file\",\"input\":{\"path\":\"C:/private/file.txt\"}}]}}' + [char]10, $encoding)\n"
                "Start-Sleep -Milliseconds 250\n"
                "[IO.File]::AppendAllText($eventPath, '{\"type\":\"user\",\"message\":{\"role\":\"user\",\"content\":[{\"type\":\"tool_result\",\"tool_use_id\":\"fake-tool-1\",\"content\":\"private result\",\"is_error\":false}]}}' + [char]10, $encoding)\n"
            )
            return (
                common
                + QwenProtocolSupervisorTest.console_handler(write_end=True, wait=False)
                + tool_events
                + "[FakeQwenStop]::Wait()\n"
            )
        if scenario == "ignore_graceful":
            return common + QwenProtocolSupervisorTest.console_handler(write_end=False) + "Start-Sleep -Seconds 15\n"
        if scenario == "loop_only":
            events = [
                {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "private request"}]}}
            ]
            for index in range(3):
                tool_id = f"fake-loop-tool-{index}"
                events.extend([
                    {"type": "assistant", "message": {"id": f"fake-loop-turn-{index}", "role": "assistant", "content": [
                        {"type": "text", "text": "Check the same file again."},
                        {"type": "tool_use", "id": tool_id, "name": "read_file", "input": {"path": "C:/private/file.txt"}},
                    ]}},
                    {"type": "user", "message": {"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": tool_id, "content": "same private result", "is_error": False}
                    ]}},
                ])
            events.append({"type": "system", "subtype": "session_end"})
            encoded_events = "\n".join(json.dumps(event) for event in events)
            return common + f"[IO.File]::AppendAllText($eventPath, '{encoded_events}' + [char]10, $encoding)\n"
        if scenario == "normal":
            return common + (
                "Write-Output 'private-raw-stdout'\n"
                "Write-Error 'private-raw-stderr'\n"
                "[IO.File]::AppendAllText($eventPath, '{\"type\":\"system\",\"subtype\":\"session_end\"}' + [char]10, $encoding)\n"
            )
        if scenario == "partial":
            return common + "[IO.File]::AppendAllText($eventPath, '{\"type\":\"system\",\"subtype\":\"session_end\"}', $encoding)\n"
        raise ValueError("unknown fake scenario")

    @staticmethod
    def fake_node_worker() -> str:
        return (
            'const fs = require("node:fs");\n'
            'const args = process.argv.slice(2);\n'
            'const eventPath = args[args.indexOf("--json-file") + 1];\n'
            'fs.writeFileSync(process.env.QWEN_FAKE_ARGS_OUTPUT, JSON.stringify(args));\n'
            'fs.writeFileSync(process.env.QWEN_FAKE_CONSOLE_OUTPUT, JSON.stringify({input:!process.stdin.isTTY,output:!process.stdout.isTTY,error:!process.stderr.isTTY}));\n'
            'const start = {type:"system", subtype:"session_start", session_id:"private-session"};\n'
            'const end = {type:"system", subtype:"session_end"};\n'
            'fs.writeFileSync(eventPath, JSON.stringify(start) + "\\n" + JSON.stringify(end) + "\\n");\n'
        )

    @staticmethod
    def node_shim() -> str:
        lines = [
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
        return "\r\n".join(lines) + "\r\n"

    @staticmethod
    def console_handler(*, write_end: bool, wait: bool = True) -> str:
        append_end = (
            'File.AppendAllText(path, "{\\"type\\":\\"system\\",\\"subtype\\":\\"session_end\\"}\\n"); '
            if write_end else ""
        )
        return (
            "Add-Type -TypeDefinition @'\n"
            "using System; using System.IO; using System.Threading;\n"
            "public static class FakeQwenStop {\n"
            "  static string path; static ManualResetEventSlim done = new ManualResetEventSlim(false);\n"
            f"  static void OnCancel(object sender, ConsoleCancelEventArgs e) {{ e.Cancel = true; {append_end} done.Set(); }}\n"
            "  static ConsoleCancelEventHandler handler = OnCancel;\n"
            "  public static void Install(string value) { path = value; Console.CancelKeyPress += handler; }\n"
            "  public static void Wait() { done.Wait(TimeSpan.FromSeconds(15)); }\n"
            "}\n"
            "'@\n"
            "[FakeQwenStop]::Install($eventPath)\n"
            + ("[FakeQwenStop]::Wait()\n" if wait else "")
        )

    def run_legacy_console_probe(self) -> dict[str, bool]:
        with tempfile.TemporaryDirectory(prefix="proofloop qwen legacy ") as directory:
            root = Path(directory)
            event_path = root / "qwen events.jsonl"
            worker_path = root / "fake qwen.ps1"
            command_path = root / "qwen.cmd"
            runner_path = root / "run legacy.ps1"
            console_path = root / "observed console.json"
            worker_path.write_text(self.fake_worker("normal"), encoding="utf-8")
            command_path.write_text(
                f'@echo off\r\n"{PWSH}" -NoProfile -File "{worker_path}" %*\r\nexit /b %errorlevel%\r\n',
                encoding="utf-8",
            )
            runner_path.write_text(
                "$arguments = @('--json-file', $env:QWEN_TEST_EVENT_FILE)\n"
                "& $env:QWEN_TEST_COMMAND @arguments *> $null\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["QWEN_TEST_COMMAND"] = str(command_path)
            environment["QWEN_TEST_EVENT_FILE"] = str(event_path)
            environment["QWEN_FAKE_ARGS_OUTPUT"] = str(root / "unused.json")
            environment["QWEN_FAKE_CONSOLE_OUTPUT"] = str(console_path)
            completed = subprocess.run(
                [PWSH, "-NoProfile", "-File", str(runner_path)],
                capture_output=True,
                text=True,
                timeout=15,
                env=environment,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(console_path.read_text(encoding="utf-8"))

    def test_wall_stop_requires_graceful_post_stop_session_end_and_closed_tree(self) -> None:
        observation, output, event_text, _, _ = self.run_supervisor(scenario="graceful", wall_seconds=1)

        self.assertEqual(set(observation), {
            "launch_id", "child_started", "process_exited", "process_exit_code", "host_stop_reason",
            "host_stop_requested", "host_interrupt_sent", "stop_observed_while_running", "session_end_seen_before_stop",
            "event_file_bytes_at_stop", "event_file_closed", "elapsed_ms",
        }, observation)
        self.assertEqual(observation["host_stop_reason"], "HOST_WALL_LIMIT")
        self.assertTrue(observation["stop_observed_while_running"])
        self.assertTrue(observation["host_interrupt_sent"])
        self.assertTrue(observation["process_exited"])
        self.assertTrue(observation["event_file_closed"])
        self.assertIsInstance(observation["event_file_bytes_at_stop"], int)
        self.assertNotIn("private-session", output)
        session_end_start = 0
        for line in event_text.splitlines(keepends=True):
            if '"subtype":"session_end"' in line.replace(" ", ""):
                break
            session_end_start += len(line.encode("utf-8"))
        self.assertGreaterEqual(session_end_start, observation["event_file_bytes_at_stop"])
        projection = ADAPTER.project_terminal_receipt(
            event_text, observation, expected_launch_id="a" * 32
        )
        self.assertEqual(projection["terminal_reason"], "HOST_WALL_LIMIT", projection)
        self.assertTrue(projection["budget_stop"])

    def test_host_stop_cutoff_is_sampled_after_final_liveness_check(self) -> None:
        source = SUPERVISOR.read_text(encoding="utf-8")
        stop_start = source.index("if ($null -ne $observation.host_stop_reason)")
        interrupt_start = source.index("$observation.host_interrupt_sent =", stop_start)
        stop_block = source[stop_start:interrupt_start]

        final_liveness_check = stop_block.rindex(
            "if (-not [ProofLoop.QwenNativeProcess]::IsRunning($child))"
        )
        cutoff_sample = stop_block.index(
            "$observation.event_file_bytes_at_stop = (Get-Item"
        )

        self.assertLess(final_liveness_check, cutoff_sample)

    def test_normal_exit_before_threshold_is_never_attributed_to_host(self) -> None:
        observation, output, _, _, _ = self.run_supervisor(scenario="normal")

        self.assertIsNone(observation["host_stop_reason"])
        self.assertFalse(observation["host_stop_requested"])
        self.assertTrue(observation["process_exited"])
        self.assertNotIn("private-raw-stdout", output)
        self.assertNotIn("private-raw-stderr", output)

    def test_cmd_argument_quoting_preserves_paths_and_prompt_metacharacters(self) -> None:
        prompt = 'Check "quoted text" & do not expand %PATH%; preserve ^ and | literally!\nContinue on the next line.'
        observation, _, _, arguments, _ = self.run_supervisor(
            scenario="normal", extra_arguments=("--prompt", prompt)
        )

        self.assertTrue(observation["process_exited"])
        self.assertEqual(arguments[-2:], ["--prompt", prompt])

    @unittest.skipUnless(shutil.which("node.exe") or shutil.which("node"), "Node.js required for recognized-shim transport test")
    def test_recognized_qwen_cmd_direct_node_preserves_prompt_without_cmd_expansion(self) -> None:
        prompt = 'Check "quoted text" & keep %PATH%, ^, |, ! and this newline:\nsecond line.'
        observation, output, _, arguments, supervised_console = self.run_supervisor(
            scenario="normal",
            extra_arguments=("--prompt", prompt),
            command_kind="recognized_node_shim",
        )

        self.assertTrue(observation["child_started"], output)
        self.assertTrue(observation["process_exited"], output)
        self.assertEqual(arguments[-2:], ["--prompt", prompt])
        self.assertEqual(supervised_console, self.run_legacy_console_probe())
        self.assertNotIn("private-session", output)

    def test_unrecognized_cmd_wrapper_is_blocked_without_execution(self) -> None:
        observation, output, _, _, _ = self.run_supervisor(
            scenario="normal", command_kind="unsupported_cmd"
        )

        self.assertFalse(observation["child_started"], observation)
        self.assertFalse(observation["process_exited"], observation)
        self.assertNotIn("unsupported wrapper was executed", output)

    def test_supervisor_preserves_legacy_redirected_console_flags(self) -> None:
        _, _, _, _, supervised_console = self.run_supervisor(scenario="normal")
        legacy_console = self.run_legacy_console_probe()

        self.assertEqual(supervised_console, legacy_console)

    def test_partial_final_line_marks_event_writer_incomplete(self) -> None:
        observation, _, event_text, _, _ = self.run_supervisor(scenario="partial")

        self.assertIsNone(observation["host_stop_reason"])
        self.assertTrue(observation["process_exited"])
        self.assertTrue(observation["event_file_closed"])
        projection = ADAPTER.project_terminal_receipt(
            event_text, observation, expected_launch_id="a" * 32
        )
        self.assertEqual(projection["event_coverage"], "INCOMPLETE")

    def test_tool_ceiling_fires_only_after_matching_result(self) -> None:
        observation, _, event_text, _, _ = self.run_supervisor(
            scenario="tool_wait", max_tools=1, wall_seconds=10
        )
        complete_pair_end = 0
        for line in event_text.splitlines(keepends=True):
            complete_pair_end += len(line.encode("utf-8"))
            if '"type":"user"' in line.replace(" ", ""):
                break

        self.assertEqual(observation["host_stop_reason"], "HOST_TOOL_LIMIT")
        self.assertGreaterEqual(observation["event_file_bytes_at_stop"], complete_pair_end)
        projection = ADAPTER.project_terminal_receipt(
            event_text, observation, expected_launch_id="a" * 32
        )
        self.assertEqual(projection["tool_calls"], 1)
        self.assertTrue(projection["budget_stop"])

    def test_incremental_event_tail_counts_only_id_matched_completed_pairs(self) -> None:
        _, _, event_text, _, _ = self.run_supervisor(
            scenario="tool_wait", max_tools=20, wall_seconds=1
        )
        with tempfile.TemporaryDirectory(prefix="proofloop qwen tail ") as directory:
            event_path = Path(directory) / "events.jsonl"
            script_path = Path(directory) / "tail.ps1"
            event_path.write_bytes(event_text.encode("utf-8"))
            script_path.write_text(
                f". '{SUPERVISOR}'\n"
                "$state = @{ offset=0L; line_start=0L; line=[Collections.Generic.List[byte]]::new(); "
                "pending=[Collections.Generic.Dictionary[string,bool]]::new([StringComparer]::Ordinal); "
                "seen_tool_ids=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal); "
                "completed_tool_ids=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal); "
                "tool_calls=0; session_end_offset=$null; session_started=$false; valid=$true }\n"
                f"Update-QwenEventTail -Path '{event_path}' -State $state -MaximumBytes (16 * 1024 * 1024)\n"
                "@{valid=$state.valid; tool_calls=$state.tool_calls; pending=$state.pending.Count} | ConvertTo-Json -Compress\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [PWSH, "-NoProfile", "-File", str(script_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        tail = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(tail, {"valid": True, "tool_calls": 1, "pending": 0})

    def test_loop_detector_alone_does_not_stop_live_child(self) -> None:
        observation, _, event_text, _, _ = self.run_supervisor(
            scenario="loop_only", max_tools=20, wall_seconds=10
        )

        self.assertIsNone(observation["host_stop_reason"])
        projection = ADAPTER.project_terminal_receipt(
            event_text, observation, expected_launch_id="a" * 32
        )
        self.assertEqual(projection["loop_status"], "DETECTED")
        self.assertFalse(projection["budget_stop"])

    def test_missing_graceful_ack_is_incomplete_after_force_kill(self) -> None:
        observation, _, event_text, _, _ = self.run_supervisor(
            scenario="ignore_graceful", wall_seconds=1
        )

        self.assertTrue(observation["host_interrupt_sent"])
        self.assertTrue(observation["process_exited"])
        projection = ADAPTER.project_terminal_receipt(
            event_text, observation, expected_launch_id="a" * 32
        )
        self.assertEqual(projection["event_coverage"], "INCOMPLETE")
        self.assertFalse(projection["budget_stop"])


if __name__ == "__main__":
    unittest.main()
