"""Registry of bounded Qwen invocation contracts.

Adapters ask this pure module for mode-specific limits, capability markers,
authority and argv.  It never executes Qwen and never stores credentials.
"""

from __future__ import annotations

import argparse
import copy
import json
import re


_COMMON_ASSIST_MARKERS = [
    "--prompt",
    "--output-format",
    "--json-schema",
    "--worktree",
    "--approval-mode",
    "--max-session-turns",
    "--max-wall-time",
    "--max-tool-calls",
    "--max-subagent-depth",
    "--exclude-tools",
    "--bare",
]
_COMMON_AUTHORITY = {
    "read_only": True,
    "role_dispatch": False,
    "subagent_dispatch": False,
    "acceptance": False,
}


def _contract(
    *,
    limits: dict[str, int | str],
    markers: list[str],
    authority: dict[str, bool],
    exclude_tools: str | None = None,
    disabled_slash_commands: str | None = None,
    approval_mode: str | None = None,
    mcp_config: str | None = None,
) -> dict[str, object]:
    return {
        "limits": limits,
        "required_markers": markers,
        "authority": authority,
        "exclude_tools": exclude_tools,
        "disabled_slash_commands": disabled_slash_commands,
        "approval_mode": approval_mode,
        "mcp_config": mcp_config,
    }


INVOCATION_CONTRACTS: dict[str, dict[str, object]] = {
    "assist": _contract(
        limits={"max_session_turns": 12, "max_tool_calls": 20, "max_wall_time": "10m", "max_subagent_depth": 1},
        markers=_COMMON_ASSIST_MARKERS,
        authority=dict(_COMMON_AUTHORITY),
        approval_mode="plan",
        exclude_tools="Agent,edit,notebook_edit,run_shell_command",
        disabled_slash_commands="review,loop",
    ),
    "assist_yolo": _contract(
        limits={"max_session_turns": 12, "max_tool_calls": 20, "max_wall_time": "10m", "max_subagent_depth": 1},
        markers=_COMMON_ASSIST_MARKERS,
        authority={"read_only": False, "role_dispatch": False, "subagent_dispatch": False, "acceptance": False},
        approval_mode="yolo",
        exclude_tools="Agent,run_shell_command",
        disabled_slash_commands="review,loop",
    ),
    "seal": _contract(
        limits={"max_session_turns": 12, "max_tool_calls": 1, "max_wall_time": "300s", "max_subagent_depth": 1},
        markers=[*_COMMON_ASSIST_MARKERS, "--mcp-config"],
        authority=dict(_COMMON_AUTHORITY),
        approval_mode="plan",
        exclude_tools="Agent,edit,notebook_edit,run_shell_command",
        disabled_slash_commands="review,loop",
        mcp_config='{"mcpServers":{}}',
    ),
    "native_recon": _contract(
        limits={"max_session_turns": 3, "max_tool_calls": 6, "max_wall_time": "5m", "max_subagent_depth": 1},
        markers=[
            "--prompt", "--bare", "--approval-mode", "--output-format", "--json-schema",
            "--max-session-turns", "--max-tool-calls", "--max-wall-time", "--max-subagent-depth",
            "--exclude-tools", "--disabled-slash-commands", "plan",
        ],
        authority=dict(_COMMON_AUTHORITY),
        approval_mode="plan",
        exclude_tools="Agent,edit,notebook_edit,run_shell_command",
        disabled_slash_commands="review,loop",
    ),
    "protocol": _contract(
        limits={"max_session_turns": 20, "max_tool_calls": 20, "max_wall_time": "30m", "max_subagent_depth": 1},
        markers=["--prompt", "--max-session-turns", "--max-tool-calls", "--max-wall-time", "--max-subagent-depth"],
        authority={"read_only": False, "role_dispatch": True, "subagent_dispatch": True, "acceptance": False},
    ),
    "capability_smoke": _contract(
        limits={"max_session_turns": 0, "max_tool_calls": 0, "max_wall_time": "0s", "max_subagent_depth": 0},
        markers=["--prompt", "--max-session-turns", "--max-tool-calls", "--max-wall-time", "--max-subagent-depth"],
        authority=dict(_COMMON_AUTHORITY),
    ),
}


def get_contract(mode: str) -> dict[str, object]:
    """Return an isolated copy of one registry entry."""
    try:
        return copy.deepcopy(INVOCATION_CONTRACTS[mode])
    except KeyError as error:
        raise ValueError(f"unknown invocation mode: {mode}") from error


def _require(values: dict[str, object], *names: str) -> None:
    if any(not isinstance(values.get(name), str) or not str(values[name]).strip() for name in names):
        raise ValueError("missing invocation rendering input")


def _limits_argv(contract: dict[str, object]) -> list[str]:
    limits = contract["limits"]
    assert isinstance(limits, dict)
    return [
        "--max-session-turns", str(limits["max_session_turns"]),
        "--max-wall-time", str(limits["max_wall_time"]),
        "--max-tool-calls", str(limits["max_tool_calls"]),
        "--max-subagent-depth", str(limits["max_subagent_depth"]),
    ]


def render_argv(mode: str, **values: object) -> list[str]:
    """Render canonical argv for one mode without the executable name."""
    contract = get_contract(mode)
    if mode == "capability_smoke":
        probe = values.get("probe")
        if probe not in ("help", "version"):
            raise ValueError("capability smoke requires help or version probe")
        return [f"--{probe}"]
    if mode == "protocol":
        _require(values, "ticket")
        ticket = str(values["ticket"])
        if re.fullmatch(r"[A-Za-z0-9._/-]+", ticket) is None:
            raise ValueError("invalid ticket")
        limits = contract["limits"]
        assert isinstance(limits, dict)
        return [
            "--max-session-turns", str(limits["max_session_turns"]),
            "--max-tool-calls", str(limits["max_tool_calls"]),
            "--max-wall-time", str(limits["max_wall_time"]),
            "--max-subagent-depth", str(limits["max_subagent_depth"]),
            "--prompt", f"/finish-ticket ticket {ticket}",
        ]
    if mode == "native_recon":
        _require(values, "schema_path", "baseline")
        prompt = (
            "Inspect only README.md in the current clean worktree using read-only file inspection. "
            f"The baseline is {values['baseline']}. Then call structured_output exactly once with a schema-valid "
            f"EVIDENCE_FOUND report containing at least three concrete facts. Set baseline exactly to {values['baseline']}. "
            "Do not edit files, run commands, or use network."
        )
        return [
            "--bare", "--approval-mode", "plan", "--output-format", "json",
            "--json-schema", f"@{values['schema_path']}", *_limits_argv(contract),
            "--exclude-tools", str(contract["exclude_tools"]),
            "--disabled-slash-commands", str(contract["disabled_slash_commands"]),
            "--prompt", prompt,
        ]
    if mode in {"assist", "assist_yolo"}:
        _require(values, "prompt", "schema_path", "worktree")
        return [
            "--bare", "--approval-mode", str(contract["approval_mode"]), "--output-format", "json",
            "--json-schema", f"@{values['schema_path']}", "--worktree", str(values["worktree"]),
            *_limits_argv(contract), "--exclude-tools", str(contract["exclude_tools"]),
            "--disabled-slash-commands", str(contract["disabled_slash_commands"]),
            "--prompt", str(values["prompt"]),
        ]
    if mode == "seal":
        _require(values, "prompt", "schema_path", "worktree", "patch_seal_receipt")
        prompt = (
            f"{values['prompt']}\nPATCH_SEAL_RECEIPT:\n{values['patch_seal_receipt']}\n"
            "Call structured_output exactly once with the manifest matching the patch schema. "
            "Do not inspect or edit code, use shell/network, or create subagents."
        )
        return [
            "--bare", "--approval-mode", "plan", "--output-format", "json",
            "--json-schema", f"@{values['schema_path']}", "--worktree", str(values["worktree"]),
            *_limits_argv(contract), "--exclude-tools", str(contract["exclude_tools"]),
            "--disabled-slash-commands", str(contract["disabled_slash_commands"]),
            "--mcp-config", str(contract["mcp_config"]), "--prompt", prompt,
        ]
    raise ValueError(f"unsupported invocation mode: {mode}")


def render_command(mode: str, *, qwen_command: str, **values: object) -> list[str]:
    _require({"qwen_command": qwen_command}, "qwen_command")
    return [qwen_command, *render_argv(mode, **values)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a bounded Qwen invocation contract")
    parser.add_argument("--mode", required=True, choices=sorted(INVOCATION_CONTRACTS))
    parser.add_argument("--contract", action="store_true")
    parser.add_argument("--probe", choices=("help", "version"))
    parser.add_argument("--ticket")
    parser.add_argument("--prompt")
    parser.add_argument("--schema-path")
    parser.add_argument("--worktree")
    parser.add_argument("--baseline")
    parser.add_argument("--patch-seal-receipt")
    args = parser.parse_args(argv)
    if args.contract:
        print(json.dumps(get_contract(args.mode), sort_keys=True, separators=(",", ":")))
    else:
        values = vars(args).copy()
        values.pop("mode", None)
        values.pop("contract", None)
        print(json.dumps(render_argv(args.mode, **values), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
