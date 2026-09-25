"""Validate the installed finish-ticket runtime contract."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path


REQUIRED_PROTOCOL_VERSION = "1.14"
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
    "controller": {"tier": "efficient", "effort": "medium"},
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
    "QWEN_SESSION_GUARD",
    "QWEN_RUNTIME_GUARD_STOP",
    "QWEN_RECON_GUARD",
    "QWEN_RECON_READY",
    "native read-only recon",
    "clean fixed-point worktree",
    "fresh compatible",
    "runtime observation",
    "terminal event",
    "ledger_anchor",
    "prev_hash",
    "event_hash",
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
    "acceptance ledger",
    "SCOPED_PASS",
    "ACCEPTANCE_INCOMPLETE",
    "TEST_PERMIT",
    "JOB_REJECTED",
    "NEXT_CLOSURE",
    "FAILURE_PROJECTION",
    "DIAGNOSTIC_CYCLE_PERMIT",
    "DIAGNOSTIC_PROGRESS",
    "REPAIR_FAILURE",
    "NEXT_DEFECT",
    "INFRASTRUCTURE_BLOCKER",
    "REPEATED_DIAGNOSTIC_FINGERPRINT",
    "HYPOTHESIS_LEDGER",
    "diagnostic_seam",
    "reason_code",
    "references/diagnostic-cycle.md",
    "PREPARED_CANDIDATE_READY",
    "EVIDENCE_STALE",
    "references/prepared-candidate-review.md",
    "EXECUTION_CHANNEL_READY",
    "CHANNEL_POLICY_VIOLATION",
    "references/execution-channels.md",
    "TEST_EVIDENCE_READY",
    "EVIDENCE_INCOMPLETE",
    "references/test-receipts.md",
    "SEMANTIC_DIFF_READY",
    "SEMANTIC_DIFF_BLOCKED",
    "references/semantic-diff.md",
    "PASS_PROJECTION_READY",
    "Luna-first escalation",
    "EFFICIENT_TIER_DEFICIENCY",
    "PASS_PROJECTION_BLOCKED",
    "references/pass-projection.md",
    "QWEN_ASSIST bridge",
    "references/qwen-assist.md",
    "семь вызовов на ticket",
)

QWEN_EXTENSION_MANIFEST = "qwen-extension.json"
QWEN_EXTENSION_SKILLS = "plugins/agentic-development-workflow/skills"
QWEN_EXTENSION_AGENTS = "qwen-code/agents"
QWEN_CONTROLLER_AGENT = "finish-ticket-controller.md"
QWEN_PILOT_EVIDENCE = "docs/experiments/qwen-code-v0222-pilot.md"
QWEN_RUNTIME_RECEIPT_VERSION = 1
QWEN_RUNTIME_LIMITS = {
    "max_session_turns": 20,
    "max_tool_calls": 20,
    "max_wall_time": "30m",
    "max_subagent_depth": 1,
}
QWEN_RECON_LIMITS = {
    "max_session_turns": 3,
    "max_tool_calls": 6,
    "max_wall_time": "5m",
    "max_subagent_depth": 1,
}


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


DIAGNOSTIC_CLASSIFICATIONS = frozenset(
    {"DIAGNOSTIC_PROGRESS", "REPAIR_FAILURE", "NEXT_DEFECT", "INFRASTRUCTURE_BLOCKER"}
)
DIAGNOSTIC_OBSERVATION_FIELDS = frozenset(
    {"first_failed_operation", "reason_code", "observed_result"}
)
HYPOTHESIS_LEDGER_FIELDS = (
    "symptom",
    "production_boundary",
    "hypothesis",
    "command",
    "outcome",
    "next_action",
)
PERMIT_IDENTITY_FIELDS = (
    "baseline",
    "scope",
    "channel",
    "max_experiments",
    "immutable_guarantees",
    "stop_conditions",
    "issued_at",
    "expires_at",
    "allowed_changes",
    "semantic_identity",
    "diagnostic_seam",
)


def is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_nonempty_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(is_nonempty_string(item) for item in value)


def is_valid_semantic_identity(value: object) -> bool:
    return isinstance(value, dict) and all(
        is_nonempty_string(value.get(field))
        for field in ("security_boundary", "ownership", "side_effect_semantics")
    )


def is_valid_permit_interval(issued_at: object, expires_at: object) -> bool:
    if not is_nonempty_string(issued_at) or not is_nonempty_string(expires_at):
        return False
    try:
        issued = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return issued.tzinfo is not None and expires.tzinfo is not None and issued < expires


def is_valid_diagnostic_seam(value: object) -> bool:
    if not isinstance(value, dict) or not is_nonempty_string(value.get("criterion")):
        return False
    causes = value.get("competing_causes")
    observations = value.get("required_observations")
    sides = value.get("comparison_sides")
    return (
        is_nonempty_string_list(causes)
        and len(causes) >= 2
        and len(set(causes)) == len(causes)
        and is_nonempty_string_list(observations)
        and set(observations).issubset(DIAGNOSTIC_OBSERVATION_FIELDS)
        and {"first_failed_operation", "reason_code"}.issubset(observations)
        and isinstance(sides, list)
        and all(is_nonempty_string(side) for side in sides)
        and len(set(sides)) == len(sides)
        and len(sides) in {0, 2}
    )


def diagnostic_cycle_result(
    status: str,
    reason: str | None,
    consumed_experiments: int,
    max_experiments: int,
    action: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "consumed_experiments": consumed_experiments,
        "remaining_experiments": max_experiments - consumed_experiments,
    }
    if reason is not None:
        result["reason"] = reason
    if action is not None:
        result["action"] = action
    return result


def has_required_comparison(entry: dict[str, object], seam: dict[str, object]) -> bool:
    sides = seam["comparison_sides"]
    if not sides:
        return True
    comparison = entry.get("comparison")
    if not isinstance(comparison, dict) or set(comparison) != set(sides):
        return False
    return all(
        isinstance(observation, dict)
        and all(is_nonempty_string(observation.get(field)) for field in seam["required_observations"])
        for observation in comparison.values()
    )


def has_valid_ledger_context(entry: object, sequence: int) -> bool:
    return (
        isinstance(entry, dict)
        and entry.get("sequence") == sequence
        and entry.get("classification") in DIAGNOSTIC_CLASSIFICATIONS
        and all(is_nonempty_string(entry.get(field)) for field in HYPOTHESIS_LEDGER_FIELDS)
    )


def diagnostic_cycle_decision(payload: object) -> dict[str, object]:
    """Evaluate one bounded diagnostic permit without executing any command."""
    if not isinstance(payload, dict):
        return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_DIAGNOSTIC_CYCLE", 0, 0)

    permit = payload.get("permit")
    if not isinstance(permit, dict):
        return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_DIAGNOSTIC_CYCLE", 0, 0)

    baseline = permit.get("baseline")
    scope = permit.get("scope")
    channel = permit.get("channel")
    max_experiments = permit.get("max_experiments")
    issued_at = permit.get("issued_at")
    expires_at = permit.get("expires_at")
    seam = permit.get("diagnostic_seam")
    if (
        not is_nonempty_string(baseline)
        or not is_nonempty_string_list(scope)
        or not is_nonempty_string(channel)
        or not isinstance(max_experiments, int)
        or isinstance(max_experiments, bool)
        or not 1 <= max_experiments <= 3
        or not is_nonempty_string_list(permit.get("immutable_guarantees"))
        or not is_nonempty_string_list(permit.get("stop_conditions"))
        or not is_nonempty_string_list(permit.get("allowed_changes"))
        or not is_valid_semantic_identity(permit.get("semantic_identity"))
        or not is_valid_permit_interval(issued_at, expires_at)
        or not is_valid_diagnostic_seam(seam)
    ):
        return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_DIAGNOSTIC_CYCLE", 0, 0)

    permit_identity = {field: permit[field] for field in PERMIT_IDENTITY_FIELDS}
    prior_consumed = 0
    resume = payload.get("resume")
    if resume is not None:
        if not isinstance(resume, dict) or resume.get("permit_identity") != permit_identity:
            return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "PERMIT_IDENTITY_MISMATCH", 0, max_experiments)
        prior_consumed = resume.get("consumed_experiments", 0)
        if (
            not isinstance(prior_consumed, int)
            or isinstance(prior_consumed, bool)
            or not 0 <= prior_consumed <= max_experiments
        ):
            return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_DIAGNOSTIC_CYCLE", 0, max_experiments)

    ledger = payload.get("hypothesis_ledger")
    if not isinstance(ledger, list):
        return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_HYPOTHESIS_LEDGER", prior_consumed, max_experiments)

    consumed = prior_consumed
    previous_fingerprint: tuple[str, ...] | None = None
    for sequence, entry in enumerate(ledger, start=1):
        if not has_valid_ledger_context(entry, sequence):
            return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_HYPOTHESIS_LEDGER", consumed, max_experiments)
        classification = entry["classification"]
        if classification == "INFRASTRUCTURE_BLOCKER":
            if entry.get("target_command_started") is not False:
                return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_INFRASTRUCTURE_BLOCKER", consumed, max_experiments)
            return diagnostic_cycle_result(
                "INFRASTRUCTURE_BLOCKER",
                "PRE_COMMAND_INFRASTRUCTURE_FAILURE",
                consumed,
                max_experiments,
                "REPAIR_INFRASTRUCTURE",
            )

        observations = tuple(entry.get(field) for field in seam["required_observations"])
        if not all(is_nonempty_string(value) for value in observations) or not has_required_comparison(entry, seam):
            return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "MALFORMED_SEAM_EVIDENCE", consumed, max_experiments)
        if consumed >= max_experiments:
            return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "EXPERIMENT_BUDGET_EXCEEDED", consumed, max_experiments)

        consumed += 1
        fingerprint = tuple(value.strip() for value in observations)
        if fingerprint == previous_fingerprint:
            return diagnostic_cycle_result(
                "DIAGNOSTIC_CONTROL_POINT",
                "REPEATED_DIAGNOSTIC_FINGERPRINT",
                consumed,
                max_experiments,
            )
        previous_fingerprint = fingerprint

    if consumed == max_experiments:
        return diagnostic_cycle_result("DIAGNOSTIC_CONTROL_POINT", "EXPERIMENT_BUDGET_EXHAUSTED", consumed, max_experiments)
    return diagnostic_cycle_result("DIAGNOSTIC_CYCLE_ACTIVE", None, consumed, max_experiments, "CONTINUE_DIAGNOSTICS")
PREPARED_CANDIDATE_CONTEXT_FIELDS = (
    "build_configuration",
    "execution_configuration",
    "required_environment",
)


def prepared_candidate_result(status: str, reason: str | None = None, action: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {"status": status}
    if reason is not None:
        result["reason"] = reason
    if action is not None:
        result["action"] = action
    return result


def is_valid_prepared_context(value: object) -> bool:
    return (
        isinstance(value, dict)
        and is_nonempty_string(value.get("build_configuration"))
        and is_nonempty_string(value.get("execution_configuration"))
        and is_nonempty_string_list(value.get("required_environment"))
    )


def is_valid_prepared_candidate(candidate: object) -> bool:
    if not isinstance(candidate, dict):
        return False
    evidence = candidate.get("diagnostic_evidence")
    return (
        is_nonempty_string(candidate.get("identity"))
        and is_nonempty_string_list(candidate.get("scope_delta"))
        and is_nonempty_string_list(candidate.get("criteria"))
        and is_nonempty_string_list(candidate.get("invariants"))
        and isinstance(evidence, dict)
        and is_reproducible_red(evidence.get("red"))
        and is_green_evidence(evidence.get("green"))
        and is_valid_prepared_context(candidate.get("evidence_context"))
    )


def has_matching_fresh_review(verdict: object, candidate_identity: str) -> bool:
    return (
        has_fresh_read_only_reviewer(verdict)
        and isinstance(verdict, dict)
        and verdict.get("candidate_identity") == candidate_identity
        and verdict.get("spec") == "PASS"
        and verdict.get("code_quality") == "PASS"
    )


def receipt_staleness_reason(receipt: object, candidate: dict[str, object]) -> str | None:
    if not isinstance(receipt, dict):
        return "MALFORMED_EVIDENCE_RECEIPT"
    context = candidate["evidence_context"]
    required = ("candidate_identity", "test_id", "command", "executed_set", "result", *PREPARED_CANDIDATE_CONTEXT_FIELDS)
    if (
        not all(field in receipt for field in required)
        or not is_nonempty_string(receipt.get("test_id"))
        or not is_verification_command(receipt.get("command"))
        or not is_nonempty_string_list(receipt.get("executed_set"))
        or receipt.get("result") != "GREEN"
        or not is_nonempty_string_list(receipt.get("required_environment"))
    ):
        return "MALFORMED_EVIDENCE_RECEIPT"
    if receipt["candidate_identity"] != candidate["identity"]:
        return "CANDIDATE_IDENTITY_CHANGED"
    if receipt["build_configuration"] != context["build_configuration"]:
        return "BUILD_CONFIGURATION_CHANGED"
    if receipt["execution_configuration"] != context["execution_configuration"]:
        return "EXECUTION_CONFIGURATION_CHANGED"
    if receipt["required_environment"] != context["required_environment"]:
        return "REQUIRED_ENVIRONMENT_CHANGED"
    return None


def prepared_candidate_decision(payload: object) -> dict[str, object]:
    """Validate reusable evidence for one candidate; never execute or reuse it automatically."""
    if not isinstance(payload, dict) or not is_valid_prepared_candidate(payload.get("candidate")):
        return prepared_candidate_result("REVIEW_REQUIRED", "MALFORMED_PREPARED_CANDIDATE")

    candidate = payload["candidate"]
    candidate_identity = candidate["identity"]
    if not has_matching_fresh_review(payload.get("reviewer_verdict"), candidate_identity):
        return prepared_candidate_result("REVIEW_REQUIRED", "FRESH_REVIEW_MISSING")

    receipts = payload.get("evidence_receipts")
    if not isinstance(receipts, list) or not receipts:
        return prepared_candidate_result("EVIDENCE_STALE", "MISSING_EVIDENCE_RECEIPT")
    for receipt in receipts:
        reason = receipt_staleness_reason(receipt, candidate)
        if reason is not None:
            return prepared_candidate_result("EVIDENCE_STALE", reason)
    return prepared_candidate_result("PREPARED_CANDIDATE_READY", action="REQUEST_VERIFIER")

EXECUTION_CHANNEL_IDS = frozenset({"isolated", "side-effectful", "interactive"})
EXECUTION_SIDE_EFFECT_POLICIES = frozenset({"none", "controlled", "interactive"})


def execution_channel_result(status: str, reason: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {"status": status}
    if reason is not None:
        result["reason"] = reason
    return result


def behavior_channel(behavior: object) -> str | None:
    if (
        not isinstance(behavior, dict)
        or set(behavior) != {"side_effectful", "interactive"}
        or not isinstance(behavior["side_effectful"], bool)
        or not isinstance(behavior["interactive"], bool)
    ):
        return None
    if behavior["interactive"]:
        return "interactive"
    if behavior["side_effectful"]:
        return "side-effectful"
    return "isolated"


def is_valid_execution_channel(channel: object) -> bool:
    return (
        isinstance(channel, dict)
        and is_nonempty_string(channel.get("channel_id"))
        and channel.get("side_effect_policy") in EXECUTION_SIDE_EFFECT_POLICIES
        and isinstance(channel.get("timeout_seconds"), int)
        and not isinstance(channel.get("timeout_seconds"), bool)
        and channel["timeout_seconds"] > 0
        and isinstance(channel.get("identity_required"), bool)
        and is_nonempty_string_list(channel.get("allowed_scope"))
    )


def execution_receipt_decision(payload: object) -> dict[str, object]:
    """Classify one declared execution channel without executing its command."""
    if not isinstance(payload, dict) or not is_valid_execution_channel(payload.get("channel")):
        return execution_channel_result("CHANNEL_POLICY_VIOLATION", "MALFORMED_EXECUTION_RECEIPT")
    if payload.get("environment_ready") is False and payload.get("target_command_started") is False:
        return execution_channel_result("INFRASTRUCTURE_BLOCKER", "PRE_COMMAND_ENVIRONMENT_FAILURE")
    if payload.get("environment_ready") is not True or payload.get("target_command_started") is not True:
        return execution_channel_result("CHANNEL_POLICY_VIOLATION", "MALFORMED_EXECUTION_RECEIPT")

    channel = payload["channel"]
    observed = behavior_channel(payload.get("observed_behavior"))
    expected_policy = {"isolated": "none", "side-effectful": "controlled", "interactive": "interactive"}.get(observed)
    if expected_policy is None or channel["side_effect_policy"] != expected_policy:
        return execution_channel_result("CHANNEL_POLICY_VIOLATION", "OBSERVED_BEHAVIOR_MISMATCH")
    invocations = payload.get("transitive_invocations")
    if not isinstance(invocations, list):
        return execution_channel_result("CHANNEL_POLICY_VIOLATION", "MALFORMED_EXECUTION_RECEIPT")
    if channel["side_effect_policy"] == "none" and any(behavior_channel(item) != "isolated" for item in invocations):
        return execution_channel_result("CHANNEL_POLICY_VIOLATION", "TRANSITIVE_CHANNEL_MISMATCH")
    return execution_channel_result("EXECUTION_CHANNEL_READY")


def test_receipts_result(status: str, reason: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {"status": status}
    if reason is not None:
        result["reason"] = reason
    return result


def is_valid_test_case_list(value: object, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(is_nonempty_string(case) for case in value)
        and len(set(value)) == len(value)
    )


def test_receipts_decision(payload: object) -> dict[str, object]:
    """Compare discovery and execution receipts without retrying or inferring a product verdict."""
    if not isinstance(payload, dict):
        return test_receipts_result("EVIDENCE_INCOMPLETE", "MALFORMED_TEST_RECEIPTS")
    discovery = payload.get("discovery_receipt")
    execution = payload.get("execution_receipt")
    if not isinstance(discovery, dict) or not isinstance(execution, dict):
        return test_receipts_result("EVIDENCE_INCOMPLETE", "MALFORMED_TEST_RECEIPTS")
    if execution.get("environment_ready") is False and execution.get("target_command_started") is False:
        return test_receipts_result("INFRASTRUCTURE_BLOCKER", "PRE_COMMAND_ENVIRONMENT_FAILURE")
    if (
        not is_nonempty_string(discovery.get("selector"))
        or not is_valid_test_case_list(discovery.get("discovered_cases"))
        or execution.get("environment_ready") is not True
        or execution.get("target_command_started") is not True
        or not is_verification_command(execution.get("command"))
        or not is_valid_test_case_list(execution.get("executed_cases"), allow_empty=True)
        or not isinstance(execution.get("counts"), dict)
        or set(execution["counts"]) != {"passed", "failed", "skipped"}
        or not all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in execution["counts"].values())
        or not is_nonempty_string(execution.get("result"))
    ):
        return test_receipts_result("EVIDENCE_INCOMPLETE", "MALFORMED_TEST_RECEIPTS")
    if set(discovery["discovered_cases"]) != set(execution["executed_cases"]) or sum(execution["counts"].values()) != len(execution["executed_cases"]):
        return test_receipts_result("EVIDENCE_INCOMPLETE", "DISCOVERY_EXECUTION_MISMATCH")
    return test_receipts_result("TEST_EVIDENCE_READY")


SEMANTIC_CONTRACT_FIELDS = (
    "name",
    "classification",
    "production_semantic_delta",
    "owner",
    "allowed_transitions",
    "forbidden_transitions",
    "consumer_evidence",
    "regression_evidence",
)


def semantic_diff_result(status: str, reason: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {"status": status}
    if reason is not None:
        result["reason"] = reason
    return result


def semantic_diff_decision(payload: object) -> dict[str, object]:
    """Gate expensive verification on declared production-contract evidence."""
    if not isinstance(payload, dict) or not isinstance(payload.get("contracts"), list) or not payload["contracts"]:
        return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "MALFORMED_SEMANTIC_DIFF")
    for contract in payload["contracts"]:
        if not isinstance(contract, dict) or not is_nonempty_string(contract.get("name")):
            return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "MALFORMED_SEMANTIC_DIFF")
        if contract.get("production_semantic_delta") is not True:
            continue
        if contract.get("classification") == "test-only":
            return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "PRODUCTION_DELTA_LABELED_TEST_ONLY")
        if contract.get("classification") != "production" or not is_nonempty_string(contract.get("owner")):
            return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "MALFORMED_SEMANTIC_DIFF")
        if not is_nonempty_string_list(contract.get("input_states")) or not is_nonempty_string_list(contract.get("output_states")):
            return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "MISSING_STATE_EVIDENCE")
        if not is_nonempty_string_list(contract.get("allowed_transitions")) or not is_nonempty_string_list(contract.get("forbidden_transitions")):
            return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "MISSING_TRANSITION_EVIDENCE")
        if not is_nonempty_string(contract.get("consumer_evidence")):
            return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "MISSING_CONSUMER_EVIDENCE")
        if not is_nonempty_string(contract.get("regression_evidence")):
            return semantic_diff_result("SEMANTIC_DIFF_BLOCKED", "MISSING_REGRESSION_EVIDENCE")
    return semantic_diff_result("SEMANTIC_DIFF_READY")


FORBIDDEN_PROJECTION_FIELDS = frozenset({"prompt", "secret", "path", "raw_command_output", "exception_text", "customer_data"})

def contains_forbidden_projection_field(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_PROJECTION_FIELDS or contains_forbidden_projection_field(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_projection_field(item) for item in value)
    return False


def _parse_runtime_utc(value: object) -> datetime | None:
    if not is_nonempty_string(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _runtime_receipt_reason(
    receipt: object, now_utc: datetime, max_age_seconds: int
) -> str | None:
    if receipt is None:
        return "RECEIPT_MISSING"
    if not isinstance(receipt, dict) or contains_forbidden_projection_field(receipt):
        return "RECEIPT_MISMATCHED"
    if (
        receipt.get("receipt_type") != "QWEN_SESSION_GUARD"
        or receipt.get("receipt_version") != QWEN_RUNTIME_RECEIPT_VERSION
        or not isinstance(receipt.get("launch_id"), str)
        or re.fullmatch(r"[0-9a-f]{32}", receipt["launch_id"]) is None
        or receipt.get("mode") != "protocol"
        or receipt.get("limits") != QWEN_RUNTIME_LIMITS
        or receipt.get("loop_detection") is not True
        or receipt.get("extension_available") is not True
    ):
        return "RECEIPT_MISMATCHED"
    issued_at = _parse_runtime_utc(receipt.get("issued_at_utc"))
    if issued_at is None:
        return "RECEIPT_MISMATCHED"
    age_seconds = (now_utc - issued_at).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_seconds:
        return "RECEIPT_STALE"
    return None


_QWEN_TERMINAL_RECEIPT_FIELDS = frozenset({
    "schema_version", "status", "reason", "launch_id", "session_id_hash",
    "terminal_reason", "terminal_source", "process_exit_code", "event_coverage",
    "turns", "tool_calls", "wall_time_seconds", "loop_status",
    "loop_detector_version", "budget_stop",
})
_QWEN_TERMINAL_RECEIPT_VERSION = "proofloop.qwen-terminal-receipt.v1"
_QWEN_LOOP_DETECTOR_VERSION = "exact_tool_interaction_cycle_v1"
_QWEN_HOST_BUDGET_STOPS = frozenset({"HOST_WALL_LIMIT", "HOST_TOOL_LIMIT"})


def _runtime_terminal_evidence_reason(
    evidence: object, launch_id: str, observation: dict[str, object]
) -> str | None:
    if not isinstance(evidence, dict) or frozenset(evidence) != _QWEN_TERMINAL_RECEIPT_FIELDS:
        return "TERMINAL_EVIDENCE_MALFORMED"
    if contains_forbidden_projection_field(evidence):
        return "RAW_FIELD_FORBIDDEN"
    if (
        evidence.get("schema_version") != _QWEN_TERMINAL_RECEIPT_VERSION
        or evidence.get("status") != "COMPLETE"
        or evidence.get("reason") not in {"COMPLETE", "NORMAL_EXIT_NOT_RESUMABLE"}
        or evidence.get("launch_id") != launch_id
        or re.fullmatch(r"[0-9a-f]{32}", str(evidence.get("launch_id"))) is None
        or evidence.get("session_id_hash") != observation.get("session_id")
        or re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("session_id_hash"))) is None
        or evidence.get("event_coverage") != "COMPLETE"
        or evidence.get("loop_status") != "HOST_CLEAR"
        or evidence.get("loop_detector_version") != _QWEN_LOOP_DETECTOR_VERSION
        or type(evidence.get("budget_stop")) is not bool
        or any(
            type(evidence.get(field)) is not int or evidence[field] < 0
            for field in ("turns", "tool_calls", "wall_time_seconds")
        )
        or any(
            evidence.get(field) != observation.get(field)
            for field in ("turns", "tool_calls", "wall_time_seconds")
        )
        or (evidence.get("loop_status") == "DETECTED") != observation.get("loop_detected")
    ):
        return "TERMINAL_EVIDENCE_MISMATCH"
    terminal_reason = evidence.get("terminal_reason")
    terminal_source = evidence.get("terminal_source")
    if evidence.get("budget_stop") is True:
        if (
            evidence.get("reason") != "COMPLETE"
            or terminal_source != "HOST"
            or terminal_reason not in _QWEN_HOST_BUDGET_STOPS
            or evidence.get("process_exit_code") is None
            or type(evidence.get("process_exit_code")) is not int
            or not -1 <= evidence["process_exit_code"] <= 255
            or (terminal_reason == "HOST_TOOL_LIMIT" and evidence["tool_calls"] < QWEN_RUNTIME_LIMITS["max_tool_calls"])
            or (terminal_reason == "HOST_WALL_LIMIT" and evidence["wall_time_seconds"] < 1800)
        ):
            return "TERMINAL_EVIDENCE_MISMATCH"
    elif (
        terminal_source != "PROCESS"
        or terminal_reason not in {"NORMAL_EXIT", "PROCESS_FAILURE"}
        or evidence.get("budget_stop") is not False
        or evidence.get("process_exit_code") is None
        or type(evidence.get("process_exit_code")) is not int
        or not -1 <= evidence["process_exit_code"] <= 255
    ):
        return "TERMINAL_EVIDENCE_MISMATCH"
    return None


def _runtime_event_hash(entry: dict[str, object]) -> str:
    unsigned = {key: value for key, value in entry.items() if key != "event_hash"}
    canonical = json.dumps(unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _runtime_append_event(
    ledger: list[dict[str, object]], event: dict[str, object], ledger_id: str
) -> dict[str, object]:
    entry = {
        "ledger_id": ledger_id,
        "sequence": len(ledger) + 1,
        "prev_hash": ledger[-1]["event_hash"] if ledger else "GENESIS",
        **event,
    }
    entry["event_hash"] = _runtime_event_hash(entry)
    return entry


def _runtime_observation_is_valid(entry: dict[str, object]) -> bool:
    observation_fields = {
        "ledger_id", "sequence", "prev_hash", "event_hash", "event", "launch_id",
        "session_id", "turns", "tool_calls", "wall_time_seconds", "loop_detected",
        "tool_fingerprint", "reproducible_evidence", "continuation",
    }
    context_present = any(field in entry for field in _RUNTIME_CONTEXT_FIELDS)
    if context_present:
        observation_fields.update(_RUNTIME_CONTEXT_FIELDS)
    if entry.get("continuation") is True:
        observation_fields.update({"fresh_evidence_id", "checkpoint_id"})
    if "terminal_evidence_hash" in entry:
        observation_fields.add("terminal_evidence_hash")
    return (
        frozenset(entry) == observation_fields
        and all(
            is_nonempty_string(entry.get(field))
            for field in ("launch_id", "session_id", "tool_fingerprint")
        )
        and re.fullmatch(r"[0-9a-f]{32}", entry["launch_id"]) is not None
        and isinstance(entry.get("turns"), int)
        and not isinstance(entry["turns"], bool)
        and entry["turns"] >= 0
        and isinstance(entry.get("tool_calls"), int)
        and not isinstance(entry["tool_calls"], bool)
        and entry["tool_calls"] >= 0
        and isinstance(entry.get("wall_time_seconds"), int)
        and not isinstance(entry["wall_time_seconds"], bool)
        and entry["wall_time_seconds"] >= 0
        and isinstance(entry.get("loop_detected"), bool)
        and entry.get("reproducible_evidence") is True
        and (
            "terminal_evidence_hash" not in entry
            or re.fullmatch(r"[0-9a-f]{64}", str(entry.get("terminal_evidence_hash"))) is not None
        )
        and isinstance(entry.get("continuation"), bool)
        and _runtime_context_fields_valid(entry, required=entry.get("continuation") is True)
        and (
            entry["continuation"] is not True
            or (
                re.fullmatch(r"[0-9a-f]{32}", str(entry.get("fresh_evidence_id"))) is not None
                and re.fullmatch(r"[0-9a-f]{64}", str(entry.get("checkpoint_id"))) is not None
            )
        )
    )


_RUNTIME_CONTEXT_FIELDS = ("task_fingerprint", "scope_fingerprint", "baseline_commit")
_RUNTIME_CHECKPOINT_FIELDS = frozenset({
    "checkpoint_id", "prior_launch_id", "task_fingerprint", "scope_fingerprint",
    "baseline_commit", "diff_fingerprint", "progress_ledger_fingerprint",
    "progress_sequence", "progress_evidence_id", "progress_kind",
    "next_closure_fingerprint",
})
_RUNTIME_BUDGET_STOPS = frozenset({
    "HOST_WALL_LIMIT", "HOST_TOOL_LIMIT",
})


def _runtime_context_fields_valid(value: dict[str, object], *, required: bool) -> bool:
    present = [field in value for field in _RUNTIME_CONTEXT_FIELDS]
    if not any(present) and not required:
        return True
    if not all(present):
        return False
    return (
        re.fullmatch(r"[0-9a-f]{64}", str(value.get("task_fingerprint"))) is not None
        and re.fullmatch(r"[0-9a-f]{64}", str(value.get("scope_fingerprint"))) is not None
        and re.fullmatch(r"[0-9a-f]{40}", str(value.get("baseline_commit"))) is not None
    )


def _runtime_checkpoint_hash(checkpoint: dict[str, object]) -> str:
    unsigned = {key: value for key, value in checkpoint.items() if key != "checkpoint_id"}
    canonical = json.dumps(unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _runtime_checkpoint_is_valid(checkpoint: object, launch_id: str, observation: dict[str, object]) -> bool:
    if not isinstance(checkpoint, dict) or frozenset(checkpoint) != _RUNTIME_CHECKPOINT_FIELDS:
        return False
    if contains_forbidden_projection_field(checkpoint):
        return False
    if (
        re.fullmatch(r"[0-9a-f]{64}", str(checkpoint.get("checkpoint_id"))) is None
        or checkpoint.get("checkpoint_id") != _runtime_checkpoint_hash(checkpoint)
        or checkpoint.get("prior_launch_id") != launch_id
        or re.fullmatch(r"[0-9a-f]{32}", str(checkpoint.get("prior_launch_id"))) is None
        or not _runtime_context_fields_valid(checkpoint, required=True)
        or not _runtime_context_fields_valid(observation, required=True)
        or any(checkpoint.get(field) != observation.get(field) for field in _RUNTIME_CONTEXT_FIELDS)
        or re.fullmatch(r"[0-9a-f]{64}", str(checkpoint.get("diff_fingerprint"))) is None
        or re.fullmatch(r"[0-9a-f]{64}", str(checkpoint.get("progress_ledger_fingerprint"))) is None
        or not isinstance(checkpoint.get("progress_sequence"), int)
        or isinstance(checkpoint.get("progress_sequence"), bool)
        or checkpoint["progress_sequence"] <= 0
        or re.fullmatch(r"[0-9a-f]{32}", str(checkpoint.get("progress_evidence_id"))) is None
        or not isinstance(checkpoint.get("progress_kind"), str)
        or checkpoint["progress_kind"] not in {"LOCAL_GREEN", "REVIEW_CONTINUE"}
        or re.fullmatch(r"[0-9a-f]{64}", str(checkpoint.get("next_closure_fingerprint"))) is None
    ):
        return False
    return True


def _runtime_ledger_reason(ledger: object, anchor: object) -> str | None:
    if not isinstance(ledger, list) or not isinstance(anchor, dict):
        return "RUNTIME_LEDGER_INVALID"
    if (
        not is_nonempty_string(anchor.get("ledger_id"))
        or not isinstance(anchor.get("sequence"), int)
        or isinstance(anchor["sequence"], bool)
        or anchor["sequence"] < 0
        or not is_nonempty_string(anchor.get("head_hash"))
    ):
        return "RUNTIME_LEDGER_INVALID"
    if len(ledger) != anchor["sequence"]:
        return "RUNTIME_LEDGER_ANCHOR_MISMATCH"
    if not ledger:
        return "RUNTIME_LEDGER_ANCHOR_MISMATCH" if anchor["head_hash"] != "GENESIS" else None
    state = "ACTIVE"
    active_launch_id: str | None = None
    terminal_reason: str | None = None
    current_checkpoint: dict[str, object] | None = None
    last_observation: dict[str, object] | None = None
    session_fresh_evidence: str | None = None
    previous_event: str | None = None
    last_progress_sequence = 0
    checkpoint_ids: set[str] = set()
    evidence_ids: set[str] = set()
    previous_hash = "GENESIS"
    for sequence, entry in enumerate(ledger, start=1):
        if not isinstance(entry, dict) or entry.get("sequence") != sequence:
            return "RUNTIME_LEDGER_INVALID"
        if (
            entry.get("ledger_id") != anchor["ledger_id"]
            or entry.get("prev_hash") != previous_hash
            or not is_nonempty_string(entry.get("event_hash"))
            or entry["event_hash"] != _runtime_event_hash(entry)
        ):
            return "RUNTIME_LEDGER_INVALID"
        previous_hash = entry["event_hash"]
        event = entry.get("event")
        if event == "runtime_observation":
            if state != "ACTIVE" or not _runtime_observation_is_valid(entry):
                return "RUNTIME_LEDGER_INVALID"
            active_launch_id = entry["launch_id"]
            last_observation = entry
            current_checkpoint = None
            if entry.get("continuation") is True:
                if entry.get("fresh_evidence_id") != session_fresh_evidence:
                    return "RUNTIME_LEDGER_INVALID"
        elif event == "terminal":
            if (
                state != "ACTIVE"
                or frozenset(entry) != {
                    "ledger_id", "sequence", "prev_hash", "event_hash", "event",
                    "launch_id", "status", "reason",
                }
                or entry.get("status") != "QWEN_RUNTIME_GUARD_STOP"
                or not is_nonempty_string(entry.get("reason"))
                or re.fullmatch(r"[0-9a-f]{32}", str(entry.get("launch_id"))) is None
                or entry.get("launch_id") != active_launch_id
            ):
                return "RUNTIME_LEDGER_INVALID"
            terminal_reason = str(entry["reason"])
            state = "TERMINAL"
        elif event == "checkpoint":
            checkpoint = {field: entry.get(field) for field in _RUNTIME_CHECKPOINT_FIELDS}
            checkpoint_event_fields = _RUNTIME_CHECKPOINT_FIELDS | {
                "ledger_id", "sequence", "prev_hash", "event_hash", "event", "launch_id",
            }
            if (
                state != "ACTIVE"
                or previous_event != "runtime_observation"
                or frozenset(entry) != checkpoint_event_fields
                or entry.get("launch_id") != active_launch_id
                or not isinstance(last_observation, dict)
                or not _runtime_checkpoint_is_valid(checkpoint, str(active_launch_id), last_observation)
                or entry.get("checkpoint_id") in checkpoint_ids
                or entry.get("progress_evidence_id") in evidence_ids
                or entry.get("progress_sequence", 0) <= last_progress_sequence
            ):
                return "RUNTIME_LEDGER_INVALID"
            current_checkpoint = checkpoint
            checkpoint_ids.add(str(entry["checkpoint_id"]))
            evidence_ids.add(str(entry["progress_evidence_id"]))
            last_progress_sequence = int(entry["progress_sequence"])
        elif event == "session_start":
            if (
                state != "TERMINAL"
                or frozenset(entry) != {
                    "ledger_id", "sequence", "prev_hash", "event_hash", "event",
                    "launch_id", "fresh_evidence_id", "checkpoint_id",
                }
                or terminal_reason not in _RUNTIME_BUDGET_STOPS
                or current_checkpoint is None
                or re.fullmatch(r"[0-9a-f]{32}", str(entry.get("launch_id"))) is None
                or re.fullmatch(r"[0-9a-f]{32}", str(entry.get("fresh_evidence_id"))) is None
                or entry.get("launch_id") == active_launch_id
                or entry.get("checkpoint_id") != current_checkpoint["checkpoint_id"]
                or entry.get("fresh_evidence_id") in evidence_ids
            ):
                return "RUNTIME_LEDGER_INVALID"
            evidence_ids.add(str(entry["fresh_evidence_id"]))
            active_launch_id = entry["launch_id"]
            session_fresh_evidence = str(entry["fresh_evidence_id"])
            state = "ACTIVE"
            terminal_reason = None
            current_checkpoint = None
            last_observation = None
        else:
            return "RUNTIME_LEDGER_INVALID"
        if event == "terminal":
            # A checkpoint is resumable only when it immediately precedes this stop.
            if entry["reason"] not in _RUNTIME_BUDGET_STOPS:
                current_checkpoint = None
        previous_event = str(event)
    if anchor["head_hash"] != previous_hash:
        return "RUNTIME_LEDGER_ANCHOR_MISMATCH"
    return None


def _runtime_observation_projection(
    launch_id: str, observation: dict[str, object], terminal_evidence_hash: str | None = None
) -> dict[str, object]:
    projection = {
        "event": "runtime_observation",
        "launch_id": launch_id,
        "session_id": observation["session_id"],
        "turns": observation["turns"],
        "tool_calls": observation["tool_calls"],
        "wall_time_seconds": observation["wall_time_seconds"],
        "loop_detected": observation["loop_detected"],
        "tool_fingerprint": observation["tool_fingerprint"],
        "reproducible_evidence": observation["reproducible_evidence"],
        "continuation": observation["continuation"],
    }
    for field in _RUNTIME_CONTEXT_FIELDS:
        if field in observation:
            projection[field] = observation[field]
    if observation.get("continuation") is True:
        projection["continuation"] = True
        projection["fresh_evidence_id"] = observation["fresh_evidence_id"]
        projection["checkpoint_id"] = observation["checkpoint_id"]
    if terminal_evidence_hash is not None:
        projection["terminal_evidence_hash"] = terminal_evidence_hash
    return projection


def _runtime_ledger_anchor(ledger: list[dict[str, object]]) -> dict[str, object]:
    return {
        "ledger_id": ledger[0]["ledger_id"],
        "sequence": len(ledger),
        "head_hash": ledger[-1]["event_hash"],
    }


def qwen_runtime_guard_decision(payload: object) -> dict[str, object]:
    """Evaluate one raw-free guarded-session observation without dispatching anything."""
    if not isinstance(payload, dict) or payload.get("operation") != "runtime_observation":
        return {"status": "BLOCKED_CAPABILITY", "reason": "MALFORMED_RUNTIME_EVIDENCE", "role_dispatch": False}
    if contains_forbidden_projection_field(payload):
        return {"status": "BLOCKED_CAPABILITY", "reason": "RAW_FIELD_FORBIDDEN", "role_dispatch": False}
    now_utc = _parse_runtime_utc(payload.get("now_utc"))
    max_age_seconds = payload.get("max_receipt_age_seconds", 300)
    if now_utc is None or isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int) or not 0 < max_age_seconds <= 3600:
        return {"status": "BLOCKED_CAPABILITY", "reason": "MALFORMED_RUNTIME_EVIDENCE", "role_dispatch": False}
    receipt = payload.get("receipt")
    receipt_reason = _runtime_receipt_reason(receipt, now_utc, max_age_seconds)
    if receipt_reason is not None:
        return {"status": "BLOCKED_CAPABILITY", "reason": receipt_reason, "role_dispatch": False}
    ledger = payload.get("ledger")
    ledger_anchor = payload.get("ledger_anchor")
    ledger_reason = _runtime_ledger_reason(ledger, ledger_anchor)
    if ledger_reason is not None:
        return {"status": "BLOCKED_CAPABILITY", "reason": ledger_reason, "role_dispatch": False}
    if not isinstance(ledger, list) or not isinstance(ledger_anchor, dict):
        return {"status": "BLOCKED_CAPABILITY", "reason": "RUNTIME_LEDGER_INVALID", "role_dispatch": False}
    if not ledger and ledger_anchor["ledger_id"] != receipt["launch_id"]:
        return {"status": "BLOCKED_CAPABILITY", "reason": "RUNTIME_LEDGER_ANCHOR_MISMATCH", "role_dispatch": False}
    observation = payload.get("observation")
    if not isinstance(observation, dict) or contains_forbidden_projection_field(observation):
        return {"status": "BLOCKED_CAPABILITY", "reason": "RUNTIME_EVIDENCE_MALFORMED", "role_dispatch": False}
    required_observation_types = (
        isinstance(observation.get("session_id"), str) and bool(observation["session_id"].strip()),
        isinstance(observation.get("turns"), int) and not isinstance(observation["turns"], bool) and observation["turns"] >= 0,
        isinstance(observation.get("tool_calls"), int) and not isinstance(observation["tool_calls"], bool) and observation["tool_calls"] >= 0,
        isinstance(observation.get("wall_time_seconds"), int) and not isinstance(observation["wall_time_seconds"], bool) and observation["wall_time_seconds"] >= 0,
        isinstance(observation.get("loop_detected"), bool),
        isinstance(observation.get("tool_fingerprint"), str) and bool(observation["tool_fingerprint"].strip()),
        observation.get("reproducible_evidence") is True,
        isinstance(observation.get("continuation"), bool),
    )
    if not all(required_observation_types):
        return {"status": "BLOCKED_CAPABILITY", "reason": "RUNTIME_EVIDENCE_MALFORMED", "role_dispatch": False}
    terminal_evidence = payload.get("terminal_evidence")
    terminal_evidence_hash = None
    if "terminal_evidence" in payload:
        terminal_evidence_reason = _runtime_terminal_evidence_reason(
            terminal_evidence, str(receipt["launch_id"]), observation
        )
        if terminal_evidence_reason is not None:
            return {"status": "BLOCKED_CAPABILITY", "reason": terminal_evidence_reason, "role_dispatch": False}
        terminal_evidence_hash = hashlib.sha256(
            json.dumps(terminal_evidence, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    if observation["continuation"] is True and (
        re.fullmatch(r"[0-9a-f]{32}", str(observation.get("fresh_evidence_id"))) is None
        or re.fullmatch(r"[0-9a-f]{64}", str(observation.get("checkpoint_id"))) is None
        or not _runtime_context_fields_valid(observation, required=True)
    ):
        return {"status": "BLOCKED_CAPABILITY", "reason": "CONTINUATION_EVIDENCE_MISSING", "role_dispatch": False}

    output_ledger: list[dict[str, object]] = list(ledger)
    ledger_id = ledger_anchor["ledger_id"]
    terminal_launches = {
        entry["launch_id"]
        for entry in output_ledger
        if isinstance(entry, dict) and entry.get("event") == "terminal" and isinstance(entry.get("launch_id"), str)
    }
    last_event = output_ledger[-1] if output_ledger else None
    if observation["continuation"] is True and not (isinstance(last_event, dict) and last_event.get("event") == "terminal"):
        return {"status": "BLOCKED_CAPABILITY", "reason": "FRESH_SESSION_REQUIRED", "role_dispatch": False}
    if isinstance(last_event, dict) and last_event.get("event") == "terminal":
        if receipt["launch_id"] in terminal_launches:
            return {"status": "BLOCKED_CAPABILITY", "reason": "FRESH_SESSION_REQUIRED", "role_dispatch": False}
        if observation["continuation"] is not True:
            return {"status": "BLOCKED_CAPABILITY", "reason": "FRESH_SESSION_REQUIRED", "role_dispatch": False}
        checkpoint_entry = output_ledger[-2] if len(output_ledger) >= 2 else None
        if (
            last_event.get("reason") not in _RUNTIME_BUDGET_STOPS
            or not isinstance(checkpoint_entry, dict)
            or checkpoint_entry.get("event") != "checkpoint"
            or checkpoint_entry.get("checkpoint_id") != observation.get("checkpoint_id")
            or any(checkpoint_entry.get(field) != observation.get(field) for field in _RUNTIME_CONTEXT_FIELDS)
            or observation.get("fresh_evidence_id") in {
                entry.get("progress_evidence_id") for entry in output_ledger if isinstance(entry, dict)
            }
        ):
            return {"status": "BLOCKED_CAPABILITY", "reason": "CHECKPOINT_REQUIRED", "role_dispatch": False}
        output_ledger.append(
            _runtime_append_event(
                output_ledger,
                {
                    "event": "session_start",
                    "launch_id": receipt["launch_id"],
                    "fresh_evidence_id": observation["fresh_evidence_id"],
                    "checkpoint_id": observation["checkpoint_id"],
                },
                ledger_id,
            )
        )

    prior_observation = next(
        (
            entry
            for entry in reversed(output_ledger)
            if isinstance(entry, dict) and entry.get("event") == "runtime_observation"
        ),
        None,
    )
    repeated_fingerprint = (
        isinstance(prior_observation, dict)
        and prior_observation.get("launch_id") == receipt["launch_id"]
        and prior_observation.get("session_id") == observation["session_id"]
        and prior_observation.get("tool_fingerprint") == observation["tool_fingerprint"]
    )
    stop_reason = None
    if observation["loop_detected"] is True:
        stop_reason = "LOOP_DETECTED"
    elif terminal_evidence is not None and terminal_evidence.get("budget_stop") is True:
        stop_reason = str(terminal_evidence["terminal_reason"])
    elif terminal_evidence is not None and terminal_evidence.get("terminal_reason") == "PROCESS_FAILURE":
        return {"status": "BLOCKED_CAPABILITY", "reason": "PROCESS_FAILURE_NOT_RESUMABLE", "role_dispatch": False}
    elif terminal_evidence is not None and terminal_evidence.get("terminal_reason") == "NORMAL_EXIT":
        stop_reason = "NORMAL_EXIT"
    elif repeated_fingerprint:
        stop_reason = "REPEATED_TOOL_FINGERPRINT"
    checkpoint = observation.get("checkpoint")
    if checkpoint is not None and (
        stop_reason not in _RUNTIME_BUDGET_STOPS
        or not _runtime_checkpoint_is_valid(checkpoint, str(receipt["launch_id"]), observation)
    ):
        return {"status": "BLOCKED_CAPABILITY", "reason": "CHECKPOINT_INVALID", "role_dispatch": False}
    if checkpoint is not None:
        previous_checkpoints = [entry for entry in ledger if isinstance(entry, dict) and entry.get("event") == "checkpoint"]
        if previous_checkpoints:
            latest_checkpoint = previous_checkpoints[-1]
            if (
                checkpoint["checkpoint_id"] in {entry.get("checkpoint_id") for entry in previous_checkpoints}
                or checkpoint["progress_evidence_id"] in {entry.get("progress_evidence_id") for entry in previous_checkpoints}
                or checkpoint["progress_evidence_id"] in {
                    entry.get("fresh_evidence_id") for entry in ledger if isinstance(entry, dict)
                }
                or checkpoint["progress_sequence"] <= latest_checkpoint.get("progress_sequence", 0)
                or any(checkpoint.get(field) != latest_checkpoint.get(field) for field in _RUNTIME_CONTEXT_FIELDS)
            ):
                return {"status": "BLOCKED_CAPABILITY", "reason": "CHECKPOINT_INVALID", "role_dispatch": False}
    output_ledger.append(
        _runtime_append_event(
            output_ledger,
            _runtime_observation_projection(receipt["launch_id"], observation, terminal_evidence_hash),
            ledger_id,
        )
    )
    if stop_reason is not None:
        if checkpoint is not None:
            checkpoint_event = {
                "event": "checkpoint",
                "launch_id": receipt["launch_id"],
                **checkpoint,
            }
            output_ledger.append(_runtime_append_event(output_ledger, checkpoint_event, ledger_id))
        output_ledger.append(
            _runtime_append_event(
                output_ledger,
                {
                    "event": "terminal",
                    "launch_id": receipt["launch_id"],
                    "status": "QWEN_RUNTIME_GUARD_STOP",
                    "reason": stop_reason,
                },
                ledger_id,
            )
        )
        return {
            "status": "QWEN_RUNTIME_GUARD_STOP",
            "reason": stop_reason,
            "launch_id": receipt["launch_id"],
            "session_id": observation["session_id"],
            "role_dispatch": False,
            "ledger": output_ledger,
            "ledger_anchor": _runtime_ledger_anchor(output_ledger),
        }
    return {
        "status": "QWEN_RUNTIME_GUARD_READY",
        "launch_id": receipt["launch_id"],
        "session_id": observation["session_id"],
        "role_dispatch": True,
        "ledger": output_ledger,
        "ledger_anchor": _runtime_ledger_anchor(output_ledger),
    }


def _recon_receipt_reason(
    receipt: object, now_utc: datetime, max_age_seconds: int
) -> str | None:
    if receipt is None:
        return "RECEIPT_MISSING"
    if not isinstance(receipt, dict) or contains_forbidden_projection_field(receipt):
        return "RECEIPT_MISMATCHED"
    if (
        receipt.get("receipt_type") != "QWEN_RECON_GUARD"
        or receipt.get("receipt_version") != QWEN_RUNTIME_RECEIPT_VERSION
        or not isinstance(receipt.get("launch_id"), str)
        or re.fullmatch(r"[0-9a-f]{32}", receipt["launch_id"]) is None
        or not isinstance(receipt.get("session_id"), str)
        or re.fullmatch(r"[0-9a-f]{32}", receipt["session_id"]) is None
        or not isinstance(receipt.get("ledger_id"), str)
        or re.fullmatch(r"[0-9a-f]{32}", receipt["ledger_id"]) is None
        or not isinstance(receipt.get("fresh_evidence_id"), str)
        or re.fullmatch(r"[0-9a-f]{32}", receipt["fresh_evidence_id"]) is None
        or receipt.get("mode") != "recon"
        or receipt.get("limits") != QWEN_RECON_LIMITS
        or receipt.get("loop_detection") is not True
        or receipt.get("extension_available") is not True
        or receipt.get("read_only") is not True
        or receipt.get("role_dispatch") is not False
        or receipt.get("subagent_dispatch") is not False
        or receipt.get("acceptance") is not False
        or receipt.get("structured_output") is not True
        or receipt.get("worktree_clean") is not True
        or not isinstance(receipt.get("fixed_point"), str)
        or re.fullmatch(r"[0-9a-f]{40,64}", receipt["fixed_point"]) is None
    ):
        return "RECEIPT_MISMATCHED"
    issued_at = _parse_runtime_utc(receipt.get("issued_at_utc"))
    if issued_at is None:
        return "RECEIPT_MISMATCHED"
    age_seconds = (now_utc - issued_at).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_seconds:
        return "RECEIPT_STALE"
    return None


def _recon_ledger_reason(ledger: object, anchor: object) -> str | None:
    if not isinstance(ledger, list) or not isinstance(anchor, dict):
        return "RUNTIME_LEDGER_INVALID"
    if (
        not is_nonempty_string(anchor.get("ledger_id"))
        or not isinstance(anchor.get("sequence"), int)
        or isinstance(anchor["sequence"], bool)
        or anchor["sequence"] < 0
        or not is_nonempty_string(anchor.get("head_hash"))
    ):
        return "RUNTIME_LEDGER_INVALID"
    if len(ledger) != anchor["sequence"]:
        return "RUNTIME_LEDGER_ANCHOR_MISMATCH"
    if not ledger:
        return "RUNTIME_LEDGER_ANCHOR_MISMATCH" if anchor["head_hash"] != "GENESIS" else None
    state = "ACTIVE"
    identity: tuple[str, str, str, str] | None = None
    previous_hash = "GENESIS"
    for sequence, entry in enumerate(ledger, start=1):
        if not isinstance(entry, dict) or entry.get("sequence") != sequence:
            return "RUNTIME_LEDGER_INVALID"
        if (
            entry.get("ledger_id") != anchor["ledger_id"]
            or entry.get("prev_hash") != previous_hash
            or not is_nonempty_string(entry.get("event_hash"))
            or entry["event_hash"] != _runtime_event_hash(entry)
        ):
            return "RUNTIME_LEDGER_INVALID"
        previous_hash = entry["event_hash"]
        event = entry.get("event")
        if event == "recon_observation":
            if state != "ACTIVE" or not _recon_observation_is_valid(entry):
                return "RUNTIME_LEDGER_INVALID"
            event_identity = (
                entry["launch_id"], entry["session_id"], entry["ledger_id"], entry["fresh_evidence_id"]
            )
            if identity is None:
                identity = event_identity
            elif event_identity != identity:
                return "RUNTIME_LEDGER_INVALID"
        elif event == "terminal":
            if (
                state != "ACTIVE"
                or entry.get("status") != "QWEN_RUNTIME_GUARD_STOP"
                or not is_nonempty_string(entry.get("reason"))
                or re.fullmatch(r"[0-9a-f]{32}", str(entry.get("launch_id"))) is None
                or identity is None
                or entry.get("launch_id") != identity[0]
            ):
                return "RUNTIME_LEDGER_INVALID"
            state = "TERMINAL"
        else:
            return "RUNTIME_LEDGER_INVALID"
    if anchor["head_hash"] != previous_hash:
        return "RUNTIME_LEDGER_ANCHOR_MISMATCH"
    return None


def _recon_observation_is_valid(entry: dict[str, object]) -> bool:
    return (
        set(entry) == {
            "event", "launch_id", "session_id", "ledger_id", "fresh_evidence_id", "turns",
            "tool_calls", "wall_time_seconds", "loop_detected", "tool_fingerprint",
            "reproducible_evidence", "structured_output_valid", "writes", "implementation",
            "role_dispatch", "subagent_dispatch", "acceptance", "sequence", "prev_hash", "event_hash",
        }
        and all(is_nonempty_string(entry.get(field)) for field in ("launch_id", "session_id", "ledger_id", "fresh_evidence_id", "tool_fingerprint"))
        and re.fullmatch(r"[0-9a-f]{32}", entry["launch_id"]) is not None
        and re.fullmatch(r"[0-9a-f]{32}", entry["session_id"]) is not None
        and re.fullmatch(r"[0-9a-f]{32}", entry["ledger_id"]) is not None
        and re.fullmatch(r"[0-9a-f]{32}", entry["fresh_evidence_id"]) is not None
        and isinstance(entry.get("turns"), int)
        and not isinstance(entry["turns"], bool)
        and entry["turns"] >= 0
        and isinstance(entry.get("tool_calls"), int)
        and not isinstance(entry["tool_calls"], bool)
        and entry["tool_calls"] >= 0
        and isinstance(entry.get("wall_time_seconds"), int)
        and not isinstance(entry["wall_time_seconds"], bool)
        and entry["wall_time_seconds"] >= 0
        and isinstance(entry.get("loop_detected"), bool)
        and entry.get("reproducible_evidence") is True
        and entry.get("structured_output_valid") is True
        and entry.get("writes") is False
        and entry.get("implementation") is False
        and entry.get("role_dispatch") is False
        and entry.get("subagent_dispatch") is False
        and entry.get("acceptance") is False
    )


def _recon_observation_projection(
    receipt: dict[str, object], observation: dict[str, object]
) -> dict[str, object]:
    projection: dict[str, object] = {
        "event": "recon_observation",
        "launch_id": receipt["launch_id"],
        "session_id": observation["session_id"],
        "ledger_id": receipt["ledger_id"],
        "fresh_evidence_id": receipt["fresh_evidence_id"],
        "turns": observation["turns"],
        "tool_calls": observation["tool_calls"],
        "wall_time_seconds": observation["wall_time_seconds"],
        "loop_detected": observation["loop_detected"],
        "tool_fingerprint": observation["tool_fingerprint"],
        "reproducible_evidence": observation["reproducible_evidence"],
        "structured_output_valid": observation["structured_output_valid"],
        "writes": observation["writes"],
        "implementation": observation["implementation"],
        "role_dispatch": observation["role_dispatch"],
        "subagent_dispatch": observation["subagent_dispatch"],
        "acceptance": observation["acceptance"],
    }

    return projection


def _recon_decision(status: str, reason: str, **extra: object) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "reason": reason,
        "role_dispatch": False,
        "subagent_dispatch": False,
        "acceptance": False,
    }
    result.update(extra)
    return result


def qwen_recon_guard_decision(payload: object) -> dict[str, object]:
    """Evaluate a bounded native read-only recon without dispatching anything."""
    if not isinstance(payload, dict) or payload.get("operation") != "recon_observation":
        return _recon_decision("BLOCKED_CAPABILITY", "MALFORMED_RECON_EVIDENCE")
    if contains_forbidden_projection_field(payload):
        return _recon_decision("BLOCKED_CAPABILITY", "RAW_FIELD_FORBIDDEN")
    now_utc = _parse_runtime_utc(payload.get("now_utc"))
    max_age_seconds = payload.get("max_receipt_age_seconds", 300)
    if now_utc is None or isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int) or not 0 < max_age_seconds <= 3600:
        return _recon_decision("BLOCKED_CAPABILITY", "MALFORMED_RECON_EVIDENCE")
    receipt = payload.get("receipt")
    receipt_reason = _recon_receipt_reason(receipt, now_utc, max_age_seconds)
    if receipt_reason is not None:
        return _recon_decision("BLOCKED_CAPABILITY", receipt_reason)
    ledger = payload.get("ledger")
    ledger_anchor = payload.get("ledger_anchor")
    ledger_reason = _recon_ledger_reason(ledger, ledger_anchor)
    if ledger_reason is not None:
        return _recon_decision("BLOCKED_CAPABILITY", ledger_reason)
    if not isinstance(ledger, list) or not isinstance(ledger_anchor, dict):
        return _recon_decision("BLOCKED_CAPABILITY", "RUNTIME_LEDGER_INVALID")
    observation = payload.get("observation")
    if not isinstance(observation, dict) or contains_forbidden_projection_field(observation):
        return _recon_decision("BLOCKED_CAPABILITY", "RUNTIME_EVIDENCE_MALFORMED")
    output_ledger: list[dict[str, object]] = list(ledger)
    ledger_id = ledger_anchor["ledger_id"]
    last_event = output_ledger[-1] if output_ledger else None
    if isinstance(last_event, dict) and last_event.get("event") == "terminal":
        return _recon_decision("BLOCKED_CAPABILITY", "RECON_TERMINAL_LEDGER_CLOSED")
    prior_observation = next(
        (entry for entry in reversed(output_ledger) if isinstance(entry, dict) and entry.get("event") == "recon_observation"),
        None,
    )
    if isinstance(prior_observation, dict):
        if prior_observation.get("launch_id") != receipt["launch_id"]:
            return _recon_decision("BLOCKED_CAPABILITY", "RECON_ACTIVE_LEDGER_LAUNCH_MISMATCH")
        if prior_observation.get("session_id") != receipt["session_id"]:
            return _recon_decision("BLOCKED_CAPABILITY", "RECON_ACTIVE_LEDGER_SESSION_MISMATCH")
    if ledger_id != receipt["ledger_id"]:
        return _recon_decision(
            "BLOCKED_CAPABILITY",
            "RECON_RECEIPT_LEDGER_MISMATCH" if output_ledger else "RECON_ANCHOR_MISMATCH",
        )
    required_observation_fields = {
        "session_id", "turns", "tool_calls", "wall_time_seconds", "loop_detected", "tool_fingerprint",
        "reproducible_evidence", "structured_output_valid", "writes", "implementation", "role_dispatch",
        "subagent_dispatch", "acceptance",
    }
    if set(observation) != required_observation_fields or observation.get("session_id") != receipt["session_id"]:
        return _recon_decision("BLOCKED_CAPABILITY", "RUNTIME_EVIDENCE_MALFORMED")
    if not _recon_observation_is_valid({
        **observation,
        "event": "recon_observation",
        "launch_id": receipt["launch_id"],
        "ledger_id": receipt["ledger_id"],
        "fresh_evidence_id": receipt["fresh_evidence_id"],
        "sequence": 1,
        "prev_hash": "GENESIS",
        "event_hash": "placeholder",
    }):
        for field, reason in (
            ("writes", "RECON_WRITE_VIOLATION"),
            ("implementation", "RECON_IMPLEMENTATION_VIOLATION"),
            ("subagent_dispatch", "RECON_SUBAGENT_VIOLATION"),
            ("acceptance", "RECON_ACCEPTANCE_VIOLATION"),
            ("structured_output_valid", "STRUCTURED_OUTPUT_INVALID"),
        ):
            invalid = (
                observation.get(field) is not True
                if field == "structured_output_valid"
                else observation.get(field) is not False
            )
            if invalid:
                return _recon_decision("QWEN_UNUSABLE", reason)
        return _recon_decision("BLOCKED_CAPABILITY", "RUNTIME_EVIDENCE_MALFORMED")

    used_fresh_evidence_ids = payload.get("used_fresh_evidence_ids")
    if not output_ledger:
        if (
            not isinstance(used_fresh_evidence_ids, list)
            or any(not isinstance(identity, str) or re.fullmatch(r"[0-9a-f]{32}", identity) is None for identity in used_fresh_evidence_ids)
        ):
            return _recon_decision("BLOCKED_CAPABILITY", "RECON_EVIDENCE_REGISTRY_UNAVAILABLE")
        if receipt["fresh_evidence_id"] in used_fresh_evidence_ids:
            return _recon_decision("BLOCKED_CAPABILITY", "RECON_FRESH_EVIDENCE_REUSED")
    elif isinstance(prior_observation, dict):
        if (
            prior_observation.get("ledger_id") != receipt["ledger_id"]
            or prior_observation.get("fresh_evidence_id") != receipt["fresh_evidence_id"]
        ):
            return _recon_decision("BLOCKED_CAPABILITY", "RECON_RECEIPT_LEDGER_MISMATCH")
    repeated_fingerprint = (
        isinstance(prior_observation, dict)
        and prior_observation.get("launch_id") == receipt["launch_id"]
        and prior_observation.get("session_id") == observation["session_id"]
        and prior_observation.get("tool_fingerprint") == observation["tool_fingerprint"]
    )
    output_ledger.append(_runtime_append_event(output_ledger, _recon_observation_projection(receipt, observation), ledger_id))
    stop_reason = None
    if observation["loop_detected"] is True:
        stop_reason = "LOOP_DETECTED"
    elif observation["turns"] >= QWEN_RECON_LIMITS["max_session_turns"]:
        stop_reason = "MAX_SESSION_TURNS_EXHAUSTED"
    elif observation["tool_calls"] >= QWEN_RECON_LIMITS["max_tool_calls"]:
        stop_reason = "MAX_TOOL_CALLS_EXHAUSTED"
    elif observation["wall_time_seconds"] >= 300:
        stop_reason = "MAX_WALL_TIME_EXHAUSTED"
    elif repeated_fingerprint:
        stop_reason = "REPEATED_TOOL_FINGERPRINT"
    if stop_reason is not None:
        output_ledger.append(_runtime_append_event(output_ledger, {"event": "terminal", "launch_id": receipt["launch_id"], "status": "QWEN_RUNTIME_GUARD_STOP", "reason": stop_reason}, ledger_id))
        return _recon_decision("QWEN_RUNTIME_GUARD_STOP", stop_reason, launch_id=receipt["launch_id"], session_id=observation["session_id"], ledger=output_ledger, ledger_anchor=_runtime_ledger_anchor(output_ledger))
    return {"status": "QWEN_RECON_READY", "launch_id": receipt["launch_id"], "session_id": observation["session_id"], "role_dispatch": False, "subagent_dispatch": False, "acceptance": False, "ledger": output_ledger, "ledger_anchor": _runtime_ledger_anchor(output_ledger)}

def pass_projection_decision(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict): return {"status":"PASS_PROJECTION_BLOCKED","reason":"MALFORMED_PASS_PROJECTION"}
    if contains_forbidden_projection_field(payload): return {"status":"PASS_PROJECTION_BLOCKED","reason":"RAW_FIELD_FORBIDDEN"}
    if not is_nonempty_string(payload.get("candidate_identity")): return {"status":"PASS_PROJECTION_BLOCKED","reason":"MISSING_IDENTITY"}
    if not is_nonempty_string(payload.get("artifact_reference")): return {"status":"PASS_PROJECTION_BLOCKED","reason":"MISSING_ARTIFACT_REFERENCE"}
    criteria=payload.get("criteria")
    if (not is_nonempty_string(payload.get("execution_channel")) or not isinstance(criteria,dict) or not isinstance(criteria.get("total"),int) or not isinstance(criteria.get("passed"),int) or criteria["total"] < 1 or criteria["passed"] != criteria["total"] or not isinstance(payload.get("required_controls"),dict) or not payload["required_controls"] or not is_nonempty_string(payload.get("evidence_status"))): return {"status":"PASS_PROJECTION_BLOCKED","reason":"MALFORMED_PASS_PROJECTION"}
    return {"status":"PASS_PROJECTION_READY"}


def scenario_fixture_decision(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict): return {"status":"SCENARIO_MALFORMED"}
    if payload.get("event") == "pass_projection": return pass_projection_decision(payload.get("projection"))
    statuses = {"next_defect":"NEXT_DEFECT", "infrastructure":"INFRASTRUCTURE_BLOCKER", "repeated":"DIAGNOSTIC_CONTROL_POINT", "resume_mismatch":"DIAGNOSTIC_CONTROL_POINT", "document_only":"DOCUMENT_ONLY_READY", "new_security_requirement":"BLOCKED_FOR_DESIGN"}
    return {"status": statuses.get(payload.get("event"), "SCENARIO_MALFORMED")}

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
    model_escalation = runtime / "references/model-escalation.md"
    minimal_solution_check = runtime / "references/minimal-solution-check.md"
    assert protocol.is_file()
    assert model_escalation.is_file()
    assert minimal_solution_check.is_file()

    protocol_text = protocol.read_text(encoding="utf-8")
    assert f"Версия workflow: `{REQUIRED_PROTOCOL_VERSION}`" in protocol_text
    missing = [term for term in REQUIRED_CONTRACT_TERMS if term not in protocol_text]
    assert not missing, f"runtime adapter contract is missing: {missing}"
    escalation_text = model_escalation.read_text(encoding="utf-8")
    minimal_solution_text = minimal_solution_check.read_text(encoding="utf-8")
    assert "ordinary non-Qwen" in minimal_solution_text
    assert "ровно пять строк" in minimal_solution_text
    for term in ("Luna-first", "EFFICIENT_TIER_DEFICIENCY", "TOKEN_USAGE"):
        assert term in escalation_text, f"model escalation reference is missing: {term}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_root", type=Path, nargs="?")
    parser.add_argument("--capabilities", type=json.loads)
    parser.add_argument("--qwen-repair", type=json.loads)
    parser.add_argument("--diagnostic-cycle", type=json.loads)
    parser.add_argument("--prepared-candidate", type=json.loads)
    parser.add_argument("--execution-receipt", type=json.loads)
    parser.add_argument("--test-receipts", type=json.loads)
    parser.add_argument("--semantic-diff", type=json.loads)
    parser.add_argument("--pass-projection", type=json.loads)
    parser.add_argument("--scenario-fixture", type=json.loads)
    parser.add_argument("--qwen-runtime-guard", type=json.loads)
    parser.add_argument("--qwen-recon-guard", type=json.loads)
    parser.add_argument("--qwen-extension-root", type=Path)
    args = parser.parse_args()
    if args.diagnostic_cycle is not None:
        print(json.dumps(diagnostic_cycle_decision(args.diagnostic_cycle), sort_keys=True))
        return
    if args.scenario_fixture is not None:
        print(json.dumps(scenario_fixture_decision(args.scenario_fixture), sort_keys=True))
        return
    if args.qwen_runtime_guard is not None:
        print(json.dumps(qwen_runtime_guard_decision(args.qwen_runtime_guard), sort_keys=True))
        return
    if args.qwen_recon_guard is not None:
        print(json.dumps(qwen_recon_guard_decision(args.qwen_recon_guard), sort_keys=True))
        return
    if args.pass_projection is not None:
        print(json.dumps(pass_projection_decision(args.pass_projection), sort_keys=True))
        return
    if args.semantic_diff is not None:
        print(json.dumps(semantic_diff_decision(args.semantic_diff), sort_keys=True))
        return
    if args.test_receipts is not None:
        print(json.dumps(test_receipts_decision(args.test_receipts), sort_keys=True))
        return
    if args.execution_receipt is not None:
        print(json.dumps(execution_receipt_decision(args.execution_receipt), sort_keys=True))
        return
    if args.prepared_candidate is not None:
        print(json.dumps(prepared_candidate_decision(args.prepared_candidate), sort_keys=True))
        return
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
