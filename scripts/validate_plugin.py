"""Validate the installed finish-ticket runtime contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_PROTOCOL_VERSION = "1.11"
REQUIRED_CAPABILITIES = (
    "model_identity",
    "role_dispatch_and_continuation",
    "tool_policy",
    "observed_usage",
)
CAPABILITY_TIERS = ("efficient", "standard", "frontier")
TRUSTED_CODEX_PROVENANCE = {"provider": "openai", "source": "codex-runtime"}
TRUSTED_QWEN_RUNTIME = {"provider": "qwen", "product": "qwen-code", "version": "0.22.2"}
QWEN_BOOLEAN_CAPABILITIES = (
    "role_model_identity_lock",
    "fresh_named_subagent",
    "implementer_continuation",
)
QWEN_REVIEWER_TOOL_CLASSES = frozenset({"read", "verify"})
QWEN_FINDING_TYPES = frozenset(
    {"SPEC_VIOLATION", "REGRESSION", "QUALITY_BLOCKER", "NEW_REQUIREMENT", "DESIGN_GAP"}
)
CODEX_ROUTE_REQUIREMENTS = {
    "controller": {"tier": "standard", "effort": "medium"},
    "implementer": {"tier": "efficient", "effort": "high"},
    "reviewer": {"tier": "standard", "effort": "medium"},
    "verifier": {"tier": "efficient", "effort": "medium"},
}
CODEX_BUDGET = {
    "ordinary": {"role_agents": 3, "frontier": 0, "full_suite": 1, "compaction": 0},
    "critical": {"role_agents": 4, "frontier": 1, "full_suite": 1, "compaction": 1},
}
REQUIRED_CONTRACT_TERMS = (
    "## Runtime adapter contract",
    "capability preflight",
    "BLOCKED_CAPABILITY",
    "model identity",
    "role dispatch and continuation",
    "tool policy",
    "observed usage",
    "Codex adaptive profile",
    "Qwen Code v0.22.2",
    "Qwen single-model profile",
    "fresh named subagent",
    "read-only Reviewer",
    "verification command",
    "QWEN_CONVERGENT",
    "append-only ledger",
    "fixed point",
    "sequence: 1",
    "local_attempt",
    "repair_candidate",
    "attempt_sequences",
    "review_verdict",
    "terminal",
    "REPEATED_ROOT_CAUSE_WITHOUT_NEW_RED",
    "capability tier",
    "requested/selected tier",
    "model-name guessing",
    "codex-runtime",
    "role-agent 3/4",
    "full suite 1",
    "compaction 0/1",
)

QWEN_EXTENSION_MANIFEST = "qwen-extension.json"
QWEN_EXTENSION_SKILLS = "plugins/agentic-development-workflow/skills"
QWEN_EXTENSION_AGENTS = "qwen-code/agents"
QWEN_CONTROLLER_AGENT = "finish-ticket-controller.md"
QWEN_PILOT_EVIDENCE = "docs/experiments/qwen-code-v0222-pilot.md"


def resolve_model_route(
    models: list[dict[str, object]], *, requested_tier: str, effort: str
) -> dict[str, object] | None:
    """Resolve a verified inventory without inferring model families from IDs."""
    requested_index = CAPABILITY_TIERS.index(requested_tier)
    for tier in reversed(CAPABILITY_TIERS[: requested_index + 1]):
        compatible = sorted(
            (
                model
                for model in models
                if model["tier"] == tier and effort in model["efforts"]
            ),
            key=lambda model: model["id"],
        )
        if compatible:
            selected = compatible[0]
            degraded = tier != requested_tier
            return {
                "id": selected["id"],
                "effort": effort,
                "requested_tier": requested_tier,
                "selected_tier": tier,
                "degraded": degraded,
                "degradation_reason": "requested_tier_unavailable" if degraded else None,
            }
    return None


def select_codex_profile(capabilities: object) -> dict[str, object]:
    if not isinstance(capabilities, dict):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["declaration"]}

    missing = [
        capability
        for capability in REQUIRED_CAPABILITIES
        if capability not in capabilities or capabilities[capability] in (False, None)
    ]
    if missing:
        return {"status": "BLOCKED_CAPABILITY", "missing_capabilities": missing}

    available_models = capabilities["model_identity"]
    if not isinstance(available_models, dict):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["model_identity"]}
    if any(
        available_models.get(field) != value
        for field, value in TRUSTED_CODEX_PROVENANCE.items()
    ):
        return {"status": "BLOCKED_CAPABILITY", "untrusted_capabilities": ["model_identity"]}
    models = available_models.get("models", [])
    if (
        not isinstance(available_models.get("provider"), str)
        or not isinstance(models, list)
        or any(
            not isinstance(model, dict)
            or not isinstance(model.get("id"), str)
            or not isinstance(model.get("tier"), str)
            or model.get("tier") not in CAPABILITY_TIERS
            or not isinstance(model.get("efforts"), list)
            or any(not isinstance(effort, str) for effort in model["efforts"])
            for model in models
        )
    ):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["model_identity"]}
    malformed = [
        capability
        for capability in REQUIRED_CAPABILITIES[1:]
        if capabilities[capability] is not True
    ]
    if malformed:
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": malformed}
    selections = {}
    for role, requested in CODEX_ROUTE_REQUIREMENTS.items():
        selection = resolve_model_route(
            models,
            requested_tier=requested["tier"],
            effort=requested["effort"],
        )
        if selection is None:
            return {
                "status": "BLOCKED_CAPABILITY",
                "missing_capabilities": ["model_identity"],
                "routing_failure": {
                    "role": role,
                    "requested_tier": requested["tier"],
                    "effort": requested["effort"],
                    "reason": "no_compatible_model_effort",
                },
            }
        selections[role] = selection

    return {"status": "CODEX_PROFILE", "models": selections, "budget": CODEX_BUDGET}


def select_qwen_profile(capabilities: dict[str, object]) -> dict[str, object]:
    """Validate the documented Qwen Code v0.22.2 preflight fixture schema."""
    runtime = capabilities.get("runtime")
    if not isinstance(runtime, dict) or any(
        runtime.get(field) != value for field, value in TRUSTED_QWEN_RUNTIME.items()
    ):
        return {"status": "BLOCKED_CAPABILITY", "untrusted_capabilities": ["runtime"]}

    missing = [
        capability
        for capability in QWEN_BOOLEAN_CAPABILITIES
        if capability not in capabilities or capabilities[capability] is False
    ]
    if missing:
        return {"status": "BLOCKED_CAPABILITY", "missing_capabilities": missing}
    malformed = [
        capability
        for capability in QWEN_BOOLEAN_CAPABILITIES
        if capabilities[capability] is not True
    ]
    if malformed:
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": malformed}

    verification_command = capabilities.get("verification_command")
    if not is_verification_command(verification_command):
        return {
            "status": "BLOCKED_CAPABILITY",
            "malformed_capabilities": ["verification_command"],
        }

    configured_model = capabilities.get("configured_model")
    active_model = capabilities.get("active_model")
    if (
        not isinstance(configured_model, dict)
        or not isinstance(active_model, dict)
        or not isinstance(configured_model.get("id"), str)
        or not configured_model["id"]
        or active_model.get("id") != configured_model["id"]
    ):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["model_identity"]}

    reviewer_policy = capabilities.get("reviewer_policy")
    if (
        not isinstance(reviewer_policy, dict)
        or reviewer_policy.get("fresh_named") is not True
        or reviewer_policy.get("fork") is not False
        or reviewer_policy.get("write") is not False
        or not isinstance(reviewer_policy.get("tool_classes"), list)
        or frozenset(reviewer_policy["tool_classes"]) != QWEN_REVIEWER_TOOL_CLASSES
    ):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["reviewer_policy"]}

    model = {"id": configured_model["id"]}
    return {
        "status": "QWEN_PROFILE",
        "configuration": {
            "runtime": TRUSTED_QWEN_RUNTIME,
            "model": model,
            "roles": {role: model.copy() for role in CODEX_ROUTE_REQUIREMENTS},
        },
        "usage": "AVAILABLE" if capabilities.get("observed_usage") is True else "NOT_AVAILABLE",
        "repair_policy": "QWEN_CONVERGENT",
    }


def is_verification_command(command: object) -> bool:
    """Accept a non-empty shell string or the documented argv command object."""
    if isinstance(command, str):
        return bool(command.strip())
    if not isinstance(command, dict) or set(command) != {"argv"}:
        return False
    argv = command["argv"]
    return (
        isinstance(argv, list)
        and bool(argv)
        and all(isinstance(argument, str) and argument.strip() for argument in argv)
    )


def is_reproducible_red(evidence: object) -> bool:
    return (
        isinstance(evidence, dict)
        and isinstance(evidence.get("command"), str)
        and bool(evidence["command"].strip())
        and evidence.get("result") == "RED"
    )


def has_red_evidence(evidence: object) -> bool:
    return (
        isinstance(evidence, dict)
        and isinstance(evidence.get("command"), str)
        and bool(evidence["command"].strip())
        and isinstance(evidence.get("result"), str)
        and bool(evidence["result"].strip())
    )


def is_green_evidence(evidence: object) -> bool:
    return (
        isinstance(evidence, list)
        and bool(evidence)
        and all(
            isinstance(item, dict)
            and isinstance(item.get("command"), str)
            and bool(item["command"].strip())
            and item.get("result") == "GREEN"
            for item in evidence
        )
    )


def has_fresh_read_only_reviewer(verdict: object) -> bool:
    return (
        isinstance(verdict, dict)
        and verdict.get("fresh_named") is True
        and verdict.get("fork") is False
        and verdict.get("write") is False
        and isinstance(verdict.get("tool_classes"), list)
        and frozenset(verdict["tool_classes"]) == QWEN_REVIEWER_TOOL_CLASSES
    )


def normalize_root_cause(root_cause: str) -> str:
    """Make equivalent wording comparable without guessing a new cause."""
    return re.sub(r"[-_\s]+", "-", root_cause.strip().casefold())


def is_valid_finding(finding: object) -> bool:
    return (
        isinstance(finding, dict)
        and isinstance(finding.get("fingerprint"), str)
        and bool(finding["fingerprint"].strip())
        and finding.get("type") in QWEN_FINDING_TYPES
        and isinstance(finding.get("root_cause"), str)
        and bool(normalize_root_cause(finding["root_cause"]))
    )


def is_local_attempt(entry: object, open_findings: set[str]) -> bool:
    return (
        isinstance(entry, dict)
        and entry.get("event") == "local_attempt"
        and is_valid_finding(entry.get("finding"))
        and entry["finding"]["fingerprint"] in open_findings
        and is_reproducible_red(entry.get("red_evidence"))
        and isinstance(entry.get("hypothesis"), str)
        and bool(entry["hypothesis"].strip())
        and is_green_evidence(entry.get("green_evidence"))
    )


def has_complete_candidate_trace(entry: dict[str, object]) -> bool:
    model = entry.get("model")
    return (
        isinstance(entry.get("normalized_root_cause"), str)
        and bool(entry["normalized_root_cause"].strip())
        and entry.get("runtime") == TRUSTED_QWEN_RUNTIME
        and isinstance(model, dict)
        and set(model) == {"id"}
        and isinstance(model.get("id"), str)
        and bool(model["id"].strip())
        and entry.get("usage") in {"AVAILABLE", "NOT_AVAILABLE"}
    )


def is_repair_candidate(entry: object, attempts: list[dict[str, object]]) -> bool:
    attempt_sequences = [attempt["sequence"] for attempt in attempts]
    normalized_attempt_roots = {
        normalize_root_cause(attempt["finding"]["root_cause"])
        for attempt in attempts
    }
    return (
        isinstance(entry, dict)
        and entry.get("event") == "repair_candidate"
        and isinstance(entry.get("attempt_sequences"), list)
        and entry["attempt_sequences"] == attempt_sequences
        and isinstance(entry.get("diff"), dict)
        and isinstance(entry["diff"].get("scope_delta"), list)
        and all(isinstance(path, str) and path.strip() for path in entry["diff"]["scope_delta"])
        and has_complete_candidate_trace(entry)
        and len(normalized_attempt_roots) == 1
        and entry["normalized_root_cause"] == next(iter(normalized_attempt_roots))
    )


def has_complete_review_evidence(entry: dict[str, object]) -> bool:
    return (
        entry.get("spec") in {"PASS", "FAIL"}
        and entry.get("code_quality") in {"PASS", "FAIL"}
        and isinstance(entry.get("accepted_criteria_regression"), bool)
        and isinstance(entry.get("unapproved_scope_expansion"), bool)
    )


def is_terminal(entry: object, decision: str) -> bool:
    return (
        isinstance(entry, dict)
        and entry.get("event") == "terminal"
        and decision in {"BLOCKED", "BLOCKED_FOR_DESIGN"}
        and entry.get("status") == decision
        and isinstance(entry.get("reason"), str)
        and bool(entry["reason"].strip())
    )


def append_qwen_terminal(
    ledger: list[object], status: str, reason: str
) -> dict[str, object]:
    """Record every policy stop as an append-only terminal evidence event."""
    return {
        "repair_policy": "QWEN_CONVERGENT",
        "ledger": [
            *ledger,
            {
                "event": "terminal",
                "sequence": len(ledger) + 1,
                "status": status,
                "reason": reason,
            },
        ],
        "status": status,
        "stop_reason": reason,
    }


def existing_qwen_terminal_result(ledger: list[object]) -> dict[str, object] | None:
    """Return a validated historical terminal without appending a second event."""
    if not ledger or not isinstance(ledger[-1], dict) or ledger[-1].get("event") != "terminal":
        return None
    terminal = ledger[-1]
    return {
        "repair_policy": "QWEN_CONVERGENT",
        "ledger": ledger,
        "status": terminal["status"],
        "stop_reason": terminal["reason"],
    }


def validate_qwen_ledger(
    ledger: list[object], configured_model_id: str
) -> tuple[str | None, set[str], bool]:
    """Validate every append-only event and return open findings plus readiness."""
    if not ledger:
        return "MISSING_BASELINE", set(), False
    baseline = ledger[0]
    if (
        not isinstance(baseline, dict)
        or baseline.get("event") != "baseline"
        or baseline.get("sequence") != 1
        or not isinstance(baseline.get("fixed_point"), str)
        or not baseline["fixed_point"].strip()
        or not isinstance(baseline.get("open_findings"), list)
        or not all(is_valid_finding(finding) for finding in baseline["open_findings"])
    ):
        return "INCOMPLETE_BASELINE", set(), False

    open_findings = {
        finding["fingerprint"]
        for finding in baseline["open_findings"]
    }
    if len(open_findings) != len(baseline["open_findings"]):
        return "INCOMPLETE_BASELINE", set(), False

    state = "READY"
    pending_attempts: list[dict[str, object]] = []
    pending_candidate: dict[str, object] | None = None
    for sequence, entry in enumerate(ledger[1:], start=2):
        if not isinstance(entry, dict) or entry.get("sequence") != sequence:
            return "INVALID_LEDGER_SEQUENCE", set(), False
        if state == "TERMINAL":
            return "LEDGER_AFTER_TERMINAL", set(), False
        event = entry.get("event")
        if event == "terminal":
            if state == "AWAITING_TERMINAL" and is_terminal(entry, pending_candidate["decision"]):
                state = "TERMINAL"
                continue
            if state in {"READY", "ATTEMPTING"} and is_terminal(entry, entry.get("status")):
                state = "TERMINAL"
                continue
            return "INVALID_LEDGER_SEQUENCE", set(), False
        if state == "AWAITING_TERMINAL":
            return "TERMINAL_LEDGER_EVIDENCE_MISSING", set(), False
        if event == "local_attempt":
            if state not in {"READY", "ATTEMPTING"}:
                return "INVALID_LEDGER_SEQUENCE", set(), False
            if not is_local_attempt(entry, open_findings):
                return "INCOMPLETE_CONTINUE_EVIDENCE", set(), False
            pending_attempts.append(entry)
            state = "ATTEMPTING"
            continue
        if event == "repair_candidate":
            expected_attempts = [attempt["sequence"] for attempt in pending_attempts]
            if state != "ATTEMPTING" or entry.get("attempt_sequences") != expected_attempts:
                return "INVALID_LEDGER_SEQUENCE", set(), False
            if (
                isinstance(entry.get("model"), dict)
                and entry["model"].get("id") != configured_model_id
            ):
                return "MODEL_IDENTITY_MISMATCH", set(), False
            if not is_repair_candidate(entry, pending_attempts):
                return "INCOMPLETE_CONTINUE_EVIDENCE", set(), False
            pending_candidate = entry
            state = "AWAITING_REVIEW"
            continue
        if event != "review_verdict" or state != "AWAITING_REVIEW" or pending_candidate is None:
            return "INVALID_LEDGER_SEQUENCE", set(), False
        if (
            entry.get("repair_candidate_sequence") != pending_candidate["sequence"]
            or not has_fresh_read_only_reviewer(entry)
            or entry.get("decision") not in {"CONTINUE", "BLOCKED", "BLOCKED_FOR_DESIGN"}
            or not isinstance(entry.get("closed_finding_fingerprints"), list)
            or any(not isinstance(item, str) or not item.strip() for item in entry["closed_finding_fingerprints"])
        ):
            return "INVALID_LEDGER_SEQUENCE", set(), False
        if not has_complete_review_evidence(entry):
            return "INCOMPLETE_REVIEW_EVIDENCE", set(), False
        closed = entry["closed_finding_fingerprints"]
        if len(set(closed)) != len(closed):
            return "INVALID_FINDING_CLOSURE", set(), False
        attempted_findings = {attempt["finding"]["fingerprint"] for attempt in pending_attempts}
        if not set(closed).issubset(open_findings) or not set(closed).issubset(attempted_findings):
            return "INVALID_FINDING_CLOSURE", set(), False
        if entry["decision"] == "CONTINUE":
            if (
                not closed
                or entry.get("spec") != "PASS"
                or entry.get("code_quality") != "PASS"
                or entry.get("accepted_criteria_regression") is not False
                or entry.get("unapproved_scope_expansion") is not False
                or any(attempt["finding"]["type"] in {"REGRESSION", "NEW_REQUIREMENT", "DESIGN_GAP"} for attempt in pending_attempts)
            ):
                return "INCOMPLETE_CONTINUE_EVIDENCE", set(), False
            open_findings.difference_update(closed)
            pending_attempts = []
            pending_candidate = None
            state = "READY"
            continue
        pending_candidate = {"decision": entry["decision"]}
        state = "AWAITING_TERMINAL"
    if state == "AWAITING_TERMINAL":
        return "TERMINAL_LEDGER_EVIDENCE_MISSING", set(), False
    return None, open_findings, state == "READY"


def qwen_repair_decision(payload: object) -> dict[str, object]:
    """Evaluate a Qwen repair candidate and append its evidence to the ledger.

    The function is intentionally a pure policy seam: fixtures supply the
    capability declaration, previous append-only ledger and Reviewer verdict.
    It never dispatches agents or interprets a model name.
    """
    if not isinstance(payload, dict):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["repair_payload"]}
    if payload.get("operation") == "local_attempt":
        ledger = payload.get("ledger", [])
        if not isinstance(ledger, list):
            return {"status": "BLOCKED", "stop_reason": "MALFORMED_LEDGER"}
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, dict):
            return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["capabilities"]}
        profile = select_qwen_profile(capabilities)
        if profile["status"] != "QWEN_PROFILE":
            return profile
        configured_model_id = profile["configuration"]["model"]["id"]
        ledger_problem, _, _ = validate_qwen_ledger(ledger, configured_model_id)
        if ledger_problem is None:
            existing_terminal = existing_qwen_terminal_result(ledger)
            if existing_terminal is not None:
                return existing_terminal
        attempt = payload.get("attempt")
        if not isinstance(attempt, dict):
            ledger_problem, _, _ = validate_qwen_ledger(ledger, configured_model_id)
            if ledger_problem is not None:
                return append_qwen_terminal(ledger, "BLOCKED", ledger_problem)
            return append_qwen_terminal(ledger, "BLOCKED", "INSUFFICIENT_LOCAL_ATTEMPT_EVIDENCE")
        entry = {"event": "local_attempt", "sequence": len(ledger) + 1, **attempt}
        ledger_problem, _, _ = validate_qwen_ledger([*ledger, entry], configured_model_id)
        if ledger_problem is not None:
            return append_qwen_terminal(ledger, "BLOCKED", ledger_problem)
        return {
            "status": payload.get("ticket_status", "IMPLEMENTING"),
            "action": "LOCAL_ATTEMPT",
            "ledger": [*ledger, entry],
        }

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["capabilities"]}
    profile = select_qwen_profile(capabilities)
    if profile["status"] != "QWEN_PROFILE":
        return profile
    ledger = payload.get("ledger")
    candidate = payload.get("candidate")
    if not isinstance(ledger, list):
        return {"status": "BLOCKED", "stop_reason": "MALFORMED_LEDGER"}
    configured_model_id = profile["configuration"]["model"]["id"]
    ledger_problem, known_open_findings, ledger_ready = validate_qwen_ledger(
        ledger, configured_model_id
    )
    if ledger_problem is not None:
        return append_qwen_terminal(ledger, "BLOCKED", ledger_problem)
    existing_terminal = existing_qwen_terminal_result(ledger)
    if existing_terminal is not None:
        return existing_terminal

    if not isinstance(candidate, dict):
        return append_qwen_terminal(ledger, "BLOCKED", "MALFORMED_REPAIR_CANDIDATE")

    verdict = candidate.get("reviewer_verdict")
    existing_attempts: list[dict[str, object]] = []
    for entry in reversed(ledger):
        if isinstance(entry, dict) and entry.get("event") == "local_attempt":
            existing_attempts.append(entry)
            continue
        break
    existing_attempts.reverse()
    uses_existing_attempts = "attempt_sequences" in candidate
    if uses_existing_attempts:
        if (
            not existing_attempts
            or candidate.get("attempt_sequences") != [attempt["sequence"] for attempt in existing_attempts]
        ):
            return append_qwen_terminal(ledger, "BLOCKED", "INVALID_ATTEMPT_REFERENCES")
        finding = existing_attempts[0]["finding"]
        if any(attempt["finding"] != finding for attempt in existing_attempts):
            return append_qwen_terminal(ledger, "BLOCKED", "MIXED_FINDING_ATTEMPTS")
    else:
        if not ledger_ready:
            return append_qwen_terminal(ledger, "BLOCKED", "PENDING_REPAIR_EVIDENCE")
        finding = candidate.get("finding")
        if not is_valid_finding(finding):
            return append_qwen_terminal(ledger, "BLOCKED", "MALFORMED_FINDING")

    fingerprint = finding["fingerprint"]
    finding_type = finding["type"]
    root_cause = finding["root_cause"]
    normalized_root_cause = normalize_root_cause(root_cause)
    history_before_attempts = ledger[: -len(existing_attempts)] if uses_existing_attempts else ledger
    prior_findings = [
        entry.get("finding")
        for entry in history_before_attempts
        if isinstance(entry, dict) and entry.get("event") == "local_attempt" and isinstance(entry.get("finding"), dict)
    ]
    repeated_root_cause = any(
        prior.get("type") == finding_type
        and isinstance(prior.get("root_cause"), str)
        and normalize_root_cause(prior["root_cause"]) == normalized_root_cause
        for prior in prior_findings
    )

    if (
        repeated_root_cause
        and not uses_existing_attempts
        and not is_reproducible_red(candidate.get("red_evidence"))
    ):
        return append_qwen_terminal(ledger, "BLOCKED", "REPEATED_ROOT_CAUSE_WITHOUT_NEW_RED")

    required_candidate_fields = (
        isinstance(candidate.get("diff"), dict)
        and isinstance(candidate["diff"].get("scope_delta"), list)
        and all(isinstance(path, str) and path.strip() for path in candidate["diff"]["scope_delta"]),
        has_fresh_read_only_reviewer(verdict),
    )
    if not uses_existing_attempts:
        required_candidate_fields += (
            isinstance(candidate.get("hypothesis"), str) and bool(candidate["hypothesis"].strip()),
            is_reproducible_red(candidate.get("red_evidence")),
            is_green_evidence(candidate.get("green_evidence")),
        )
    if not all(required_candidate_fields):
        return append_qwen_terminal(ledger, "BLOCKED", "INSUFFICIENT_REPAIR_EVIDENCE")

    closed = verdict.get("closed_finding_fingerprints")
    if (
        not isinstance(closed, list)
        or any(not isinstance(item, str) or not item.strip() for item in closed)
        or len(set(closed)) != len(closed)
        or not set(closed).issubset(known_open_findings)
        or not set(closed).issubset({attempt["finding"]["fingerprint"] for attempt in existing_attempts} if uses_existing_attempts else {fingerprint})
    ):
        return append_qwen_terminal(ledger, "BLOCKED", "INVALID_FINDING_CLOSURE")
    if uses_existing_attempts:
        local_attempts: list[dict[str, object]] = []
        attempt_sequences = candidate["attempt_sequences"]
        candidate_sequence = len(ledger) + 1
    else:
        local_attempts = [{
            "event": "local_attempt",
            "sequence": len(ledger) + 1,
            "finding": finding,
            "red_evidence": candidate["red_evidence"],
            "hypothesis": candidate["hypothesis"],
            "green_evidence": candidate["green_evidence"],
        }]
        attempt_sequences = [local_attempts[0]["sequence"]]
        candidate_sequence = len(ledger) + 2
    repair_candidate = {
        "event": "repair_candidate",
        "sequence": candidate_sequence,
        "attempt_sequences": attempt_sequences,
        "diff": candidate["diff"],
        "normalized_root_cause": normalized_root_cause,
        "runtime": profile["configuration"]["runtime"],
        "model": profile["configuration"]["model"],
        "usage": profile["usage"],
    }
    review_verdict = {
        "event": "review_verdict",
        "sequence": candidate_sequence + 1,
        "repair_candidate_sequence": repair_candidate["sequence"],
        **verdict,
    }
    output_ledger = [*ledger, *local_attempts, repair_candidate, review_verdict]
    result: dict[str, object] = {
        "repair_policy": "QWEN_CONVERGENT",
        "ledger": output_ledger,
    }
    if finding_type in {"NEW_REQUIREMENT", "DESIGN_GAP"}:
        status, reason = "BLOCKED_FOR_DESIGN", finding_type
    elif verdict.get("unapproved_scope_expansion") is True:
        status, reason = "BLOCKED_FOR_DESIGN", "UNAPPROVED_SCOPE_EXPANSION"
    elif verdict.get("accepted_criteria_regression") is True or finding_type == "REGRESSION":
        status, reason = "BLOCKED", "REGRESSION"
    elif verdict.get("spec") != "PASS" or verdict.get("code_quality") != "PASS":
        status, reason = "BLOCKED", "REVIEWER_REJECTED"
    elif fingerprint not in known_open_findings or fingerprint not in verdict.get("closed_finding_fingerprints", []):
        status, reason = "BLOCKED", "NO_OPEN_FINDING_CLOSED"
    else:
        status, reason = "CONTINUE", None
    review_verdict["decision"] = status
    if reason is not None:
        output_ledger.append(
            {
                "event": "terminal",
                "sequence": candidate_sequence + 2,
                "status": status,
                "reason": reason,
            }
        )
    return {**result, "status": status, **({"stop_reason": reason} if reason is not None else {})}


def select_runtime_profile(capabilities: object) -> dict[str, object]:
    """Select a trusted runtime profile from a declaration, never model names."""
    if not isinstance(capabilities, dict):
        return {"status": "BLOCKED_CAPABILITY", "malformed_capabilities": ["declaration"]}
    runtime = capabilities.get("runtime")
    if runtime is not None:
        if not isinstance(runtime, dict) or runtime.get("provider") != "qwen":
            return {"status": "BLOCKED_CAPABILITY", "untrusted_capabilities": ["runtime"]}
        return select_qwen_profile(capabilities)
    return select_codex_profile(capabilities)


def validate_qwen_delivery_extension(repository_root: Path) -> None:
    """Validate the Qwen wrapper without copying the canonical lifecycle."""
    manifest_path = repository_root / QWEN_EXTENSION_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "proofloop-skills"
    assert manifest["version"].startswith(f"{REQUIRED_PROTOCOL_VERSION}.")
    assert manifest["skills"] == QWEN_EXTENSION_SKILLS
    assert manifest["agents"] == QWEN_EXTENSION_AGENTS

    canonical_protocol = repository_root / "plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md"
    qwen_skill = repository_root / QWEN_EXTENSION_SKILLS / "finish-ticket/SKILL.md"
    controller_agent = repository_root / QWEN_EXTENSION_AGENTS / QWEN_CONTROLLER_AGENT
    pilot = repository_root / QWEN_PILOT_EVIDENCE

    assert canonical_protocol.is_file()
    assert qwen_skill.is_file()
    assert controller_agent.is_file()
    assert pilot.is_file()
    qwen_owned_files = [
        manifest_path,
        repository_root / "QWEN.md",
        *(
            path
            for path in (repository_root / "qwen-code").rglob("*")
            if path.is_file()
        ),
    ]
    canonical_text = canonical_protocol.read_text(encoding="utf-8")
    for qwen_owned_file in qwen_owned_files:
        assert_qwen_owned_file_does_not_embed_lifecycle(qwen_owned_file, canonical_text)

    agent_text = controller_agent.read_text(encoding="utf-8")
    assert "name: finish-ticket-controller" in agent_text
    assert "model: inherit" in agent_text
    assert "plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md" in agent_text
    assert "QWEN_CONVERGENT" in agent_text
    assert "Qwen Code v0.22.2" in agent_text

    pilot_text = pilot.read_text(encoding="utf-8")
    assert "QWEN_CLI=ABSENT" in pilot_text
    assert "NOT_RUN" in pilot_text
    assert "qwen --version" in pilot_text


def assert_qwen_owned_file_does_not_embed_lifecycle(
    qwen_owned_file: Path, canonical_lifecycle: str
) -> None:
    """Reject the exact protocol-copy signature while allowing concise references."""
    content = qwen_owned_file.read_text(encoding="utf-8")
    protocol_copy_signature = "\n\n".join(canonical_lifecycle.split("\n\n")[:3]).strip()
    assert protocol_copy_signature not in content, (
        f"Qwen extension file embeds canonical lifecycle content: {qwen_owned_file}"
    )


def validate(plugin_root: Path) -> None:
    manifest = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "agentic-development-workflow"
    assert manifest["version"].startswith(f"{REQUIRED_PROTOCOL_VERSION}.")
    assert manifest["skills"] == "./skills/"

    runtime = plugin_root / "skills/finish-ticket"
    assert (runtime / "SKILL.md").is_file()
    protocol = runtime / "references/task-lifecycle.md"
    assert protocol.is_file()

    protocol_text = protocol.read_text(encoding="utf-8")
    assert f"Версия workflow: `{REQUIRED_PROTOCOL_VERSION}`" in protocol_text
    missing = [term for term in REQUIRED_CONTRACT_TERMS if term not in protocol_text]
    assert not missing, f"runtime adapter contract is missing: {missing}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_root", type=Path, nargs="?")
    parser.add_argument("--capabilities", type=json.loads)
    parser.add_argument("--qwen-repair", type=json.loads)
    parser.add_argument("--qwen-extension-root", type=Path)
    args = parser.parse_args()
    if args.qwen_repair is not None:
        print(json.dumps(qwen_repair_decision(args.qwen_repair), sort_keys=True))
        return
    if args.capabilities is not None:
        print(json.dumps(select_runtime_profile(args.capabilities), sort_keys=True))
        return
    if args.qwen_extension_root is not None:
        validate_qwen_delivery_extension(args.qwen_extension_root)
        return
    if args.plugin_root is None:
        parser.error("plugin_root or --capabilities is required")
    validate(args.plugin_root)


if __name__ == "__main__":
    main()
