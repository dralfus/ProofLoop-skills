from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "scripts" / "qwen_invocation_contract.py"
SPEC = importlib.util.spec_from_file_location("qwen_invocation_contract", MODULE_PATH)
assert SPEC and SPEC.loader
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


class QwenInvocationContractTest(unittest.TestCase):
    def test_registry_has_distinct_mode_contracts(self) -> None:
        modes = {"assist", "assist_yolo", "seal", "native_recon", "protocol", "capability_smoke"}
        self.assertEqual(set(CONTRACT.INVOCATION_CONTRACTS), modes)
        self.assertNotEqual(
            CONTRACT.get_contract("protocol")["limits"],
            CONTRACT.get_contract("native_recon")["limits"],
        )
        self.assertNotEqual(
            CONTRACT.get_contract("native_recon")["authority"],
            CONTRACT.get_contract("protocol")["authority"],
        )
        self.assertNotEqual(
            CONTRACT.get_contract("seal")["limits"],
            CONTRACT.get_contract("assist")["limits"],
        )

    def test_registry_contract_matrix_exposes_markers_and_authority(self) -> None:
        for mode, expected_read_only in (
            ("assist", True),
            ("assist_yolo", False),
            ("seal", True),
            ("native_recon", True),
            ("protocol", False),
            ("capability_smoke", True),
        ):
            with self.subTest(mode=mode):
                contract = CONTRACT.get_contract(mode)
                self.assertTrue(contract["required_markers"])
                self.assertEqual(contract["authority"]["read_only"], expected_read_only)
                self.assertFalse(contract["authority"]["acceptance"])

    def test_rendering_preserves_mode_specific_argv(self) -> None:
        assist = CONTRACT.render_command(
            "assist",
            qwen_command="qwen",
            prompt="Map scope.",
            schema_path="schema.json",
            worktree="pilot-314",
        )
        self.assertEqual(assist[0], "qwen")
        self.assertIn("--bare", assist)
        self.assertIn("--worktree", assist)
        self.assertEqual(assist[assist.index("--max-session-turns") + 1], "12")
        self.assertEqual(assist[assist.index("--max-tool-calls") + 1], "20")

        native_recon = CONTRACT.render_argv(
            "native_recon",
            schema_path="qwen-assist-recon.schema.json",
            baseline="a" * 40,
        )
        self.assertNotIn("--worktree", native_recon)
        self.assertEqual(native_recon[native_recon.index("--max-session-turns") + 1], "3")
        self.assertEqual(native_recon[native_recon.index("--max-tool-calls") + 1], "6")
        self.assertIn("Agent,edit,notebook_edit,run_shell_command", native_recon)

        protocol = CONTRACT.render_argv("protocol", ticket="16")
        self.assertEqual(
            protocol,
            [
                "--max-session-turns", "20",
                "--max-tool-calls", "20",
                "--max-wall-time", "30m",
                "--max-subagent-depth", "1",
                "--prompt", "/finish-ticket ticket 16",
            ],
        )

        seal = CONTRACT.render_argv(
            "seal",
            prompt="Seal candidate.",
            schema_path="qwen-assist-patch.schema.json",
            worktree="qwen-patch-314",
            patch_seal_receipt="{\"baseline\":\"abc\"}",
        )
        self.assertIn("--mcp-config", seal)
        self.assertIn("--max-tool-calls", seal)
        self.assertEqual(seal[seal.index("--max-tool-calls") + 1], "1")
        self.assertIn("PATCH_SEAL_RECEIPT", seal[-1])

        self.assertEqual(CONTRACT.render_argv("capability_smoke", probe="version"), ["--version"])
        self.assertEqual(CONTRACT.render_argv("capability_smoke", probe="help"), ["--help"])

    def test_registry_returns_copies_and_rejects_ambiguous_rendering(self) -> None:
        first = CONTRACT.get_contract("assist")
        first["limits"]["max_tool_calls"] = 0
        self.assertEqual(CONTRACT.get_contract("assist")["limits"]["max_tool_calls"], 20)
        with self.assertRaises(ValueError):
            CONTRACT.render_argv("native_recon")


if __name__ == "__main__":
    unittest.main()
