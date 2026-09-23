from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "qwen_terminal_projection.py"
SPEC = importlib.util.spec_from_file_location("qwen_terminal_projection", MODULE_PATH)
assert SPEC and SPEC.loader
QWEN_TERMINAL_PROJECTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QWEN_TERMINAL_PROJECTION)


class QwenTerminalProjectionTest(unittest.TestCase):
    def test_projects_structured_output_failure_without_raw_message(self) -> None:
        result = QWEN_TERMINAL_PROJECTION.project_failure(
            json.dumps(
                [
                    {
                        "type": "result",
                        "subtype": "error_during_execution",
                        "is_error": True,
                        "error": {"message": "model did not produce structured output"},
                    }
                ]
            ),
            "",
        )

        self.assertEqual(result["reason"], "STRUCTURED_OUTPUT_MISSING")
        self.assertTrue(result["diagnostic"]["terminal_is_error"])
        self.assertEqual(result["diagnostic"]["error_message_category"], "structured_output_missing")
        self.assertNotIn("model did not produce structured output", json.dumps(result))

    def test_projects_top_level_auth_error_without_raw_message(self) -> None:
        result = QWEN_TERMINAL_PROJECTION.project_failure(
            "",
            json.dumps(
                {
                    "is_error": True,
                    "subtype": "error_during_execution",
                    "error": {"message": "HTTP 403 Forbidden"},
                }
            ),
        )

        self.assertEqual(result["reason"], "QWEN_JSON_ERROR_RESULT")
        self.assertTrue(result["diagnostic"]["envelope_is_error"])
        self.assertEqual(result["diagnostic"]["envelope_error_message_category"], "auth_or_forbidden")
        self.assertNotIn("403 Forbidden", json.dumps(result))

    def test_extracts_terminal_structured_result_from_event_array(self) -> None:
        manifest = {"successful_recon": True, "files": ["tests/a.py"]}

        result = QWEN_TERMINAL_PROJECTION.extract_structured_result(
            json.dumps(
                [
                    {"type": "message", "content": "progress"},
                    {
                        "type": "result",
                        "is_error": False,
                        "subtype": "success",
                        "structured_result": manifest,
                    },
                ]
            )
        )

        self.assertEqual(result, manifest)

    def test_extract_structured_result_rejects_error_or_non_terminal_output(self) -> None:
        self.assertIsNone(
            QWEN_TERMINAL_PROJECTION.extract_structured_result(
                json.dumps(
                    {
                        "type": "result",
                        "is_error": True,
                        "subtype": "error_during_execution",
                        "structured_result": {"secret": "must not pass"},
                    }
                )
            )
        )
        self.assertIsNone(
            QWEN_TERMINAL_PROJECTION.extract_structured_result(
                json.dumps([{"type": "assistant", "content": "not terminal"}])
            )
        )
        self.assertIsNone(
            QWEN_TERMINAL_PROJECTION.extract_structured_result(
                json.dumps(
                    [
                        {"type": "result", "is_error": False, "subtype": "success", "structured_result": {"ok": True}},
                        {"type": "message", "content": "trailing transcript"},
                    ]
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
