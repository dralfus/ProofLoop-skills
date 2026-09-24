"""Mode-specific reasoning and output controls for native Qwen pilots.

This pure module describes only runtime controls supported by the launcher. It
does not set persistent settings, provider configuration, or sampling values.
"""

from __future__ import annotations

import copy
import argparse
import json


MODE_RUNTIME_CONTRACTS: dict[str, dict[str, object]] = {
    "recon": {
        "thinking_policy": "inherit_configured_reasoning",
        "output_token_limit": None,
        "process_environment": {},
    },
    "protocol": {
        "thinking_policy": "require_configured_reasoning",
        "output_token_limit": 8000,
        "process_environment": {"QWEN_CODE_MAX_OUTPUT_TOKENS": "8000"},
        "packet_language": "en",
        "response_language": "ru",
    },
}


def get_mode_runtime_contract(mode: str) -> dict[str, object]:
    try:
        return copy.deepcopy(MODE_RUNTIME_CONTRACTS[mode])
    except KeyError as error:
        raise ValueError("unknown Qwen session mode") from error


def evaluate_mode_preflight(
    mode: str, *, reasoning_effort: object
) -> dict[str, object]:
    """Return a raw-free mode gate before any model request."""
    contract = get_mode_runtime_contract(mode)
    if mode == "recon":
        if not isinstance(reasoning_effort, str) or reasoning_effort.strip().lower() in {
            "",
            "none",
            "off",
            "disabled",
        }:
            return {
                "status": "BLOCKED_CAPABILITY",
                "mode": mode,
                "reason": "RECON_THINKING_NOT_CONFIGURED",
            }
        return {
            "status": "QWEN_MODE_READY",
            "mode": mode,
            "reason": "MODE_CONTROLS_AVAILABLE",
            "thinking_policy": contract["thinking_policy"],
            "output_token_limit": None,
            "process_environment": contract["process_environment"],
        }
    if not isinstance(reasoning_effort, str) or reasoning_effort.strip().lower() in {
        "",
        "none",
        "off",
        "disabled",
    }:
        return {
            "status": "BLOCKED_CAPABILITY",
            "mode": mode,
            "reason": "PROTOCOL_THINKING_NOT_CONFIGURED",
        }
    return {
        "status": "QWEN_MODE_READY",
        "mode": mode,
        "reason": "MODE_CONTROLS_AVAILABLE",
        "thinking_policy": contract["thinking_policy"],
        "output_token_limit": contract["output_token_limit"],
        "process_environment": contract["process_environment"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Qwen mode runtime controls")
    parser.add_argument("--mode", choices=sorted(MODE_RUNTIME_CONTRACTS), required=True)
    parser.add_argument("--reasoning-effort")
    args = parser.parse_args(argv)
    print(json.dumps(evaluate_mode_preflight(args.mode, reasoning_effort=args.reasoning_effort), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
