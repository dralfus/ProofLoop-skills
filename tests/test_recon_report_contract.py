from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "scripts" / "recon_report_contract.py"
SPEC = importlib.util.spec_from_file_location("recon_report_contract", MODULE_PATH)
assert SPEC and SPEC.loader
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


class ReconReportContractTest(unittest.TestCase):
    def report(self) -> dict[str, object]:
        return {
            "status": "EVIDENCE_FOUND",
            "baseline": "abc123",
            "facts": [
                {"file": "README.md", "line": 1, "fact": "one"},
                {"file": "README.md", "line": 2, "fact": "two"},
                {"file": "README.md", "line": 3, "fact": "three"},
            ],
            "state_owner": "owner",
            "callback_boundary": "boundary",
            "acceptance_risk": "risk",
            "stop_reason": None,
            "writes": [],
        }

    def test_valid_report_is_accepted_and_preserves_report(self) -> None:
        report = self.report()

        result = CONTRACT.validate_recon_report(report, expected_baseline="abc123")

        self.assertEqual(result, {"valid": True, "report": report})

    def test_contract_rejects_missing_terminal_fields_and_extra_fields(self) -> None:
        for field in ("stop_reason", "writes"):
            with self.subTest(field=field):
                report = self.report()
                del report[field]
                self.assertEqual(CONTRACT.validate_recon_report(report)["reason"], "MALFORMED_REPORT")

        report = self.report()
        report["unexpected"] = "drift"
        self.assertEqual(CONTRACT.validate_recon_report(report)["reason"], "MALFORMED_REPORT")

        report = self.report()
        report["facts"][0]["source"] = "drift"
        self.assertEqual(CONTRACT.validate_recon_report(report)["reason"], "MALFORMED_FACT")

    def test_contract_rejects_write_and_baseline_mismatch_without_raw_fields(self) -> None:
        report = self.report()
        report["writes"] = ["src/a.cs"]
        self.assertEqual(
            CONTRACT.validate_recon_report(report),
            {"valid": False, "reason": "READ_ONLY_VIOLATION"},
        )

        report = self.report()
        self.assertEqual(
            CONTRACT.validate_recon_report(report, expected_baseline="different"),
            {"valid": False, "reason": "BASELINE_MISMATCH"},
        )

    def test_cli_reads_report_from_file_and_returns_raw_free_result(self) -> None:
        report = self.report()
        report_path = REPOSITORY_ROOT / "tests" / "fixtures" / "recon-contract-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        self.addCleanup(report_path.unlink)

        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--input-file", str(report_path), "--expected-baseline", "abc123"],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"valid": True, "report": report})
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
