# Qwen Progress-Gated Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement a pure runtime-policy contract for allowing fresh Qwen protocol continuation after a per-session budget stop only when a Controller-attested checkpoint binds progress, unchanged task scope, and a concrete next closure.

**Architecture:** Keep the current per-session `20 turns / 20 tool calls / 30m / depth 1` ceiling. Extend the pure Qwen runtime lifecycle policy with a raw-free, hash-bound checkpoint event and strict stop-reason gate. Update the canonical and human workflow instructions so only the Controller can create a checkpoint after verifying observed diff, Qwen progress ledger, and test/review receipts; the policy validates this trusted Controller input but does not independently read those external artifacts. Native launcher integration and a live continuation remain a follow-up ticket.

**Tech Stack:** Python `unittest`, existing `scripts/validate_plugin.py` pure policy CLI, PowerShell native-Qwen launcher contract, Markdown lifecycle docs and plugin validators.

**Spec:** `docs/superpowers/specs/2026-09-24-qwen-progress-gated-continuation-design.md`

## Global Constraints

- Preserve the per-session protocol ceiling `20 turns / 20 tool calls / 30m / depth 1`.
- Preserve the configured Qwen reasoning and do not change user settings, provider, credentials, sampling, or external Qwen/Stepler files.
- A fresh session requires a new receipt/launch identity and a valid progress checkpoint; identical prompt replay without checkpoint evidence is blocked.
- Only budget-exhaustion terminal reasons may be continued; loop, repeated fingerprint, regression, design gap, scope expansion, malformed evidence, or invalid ledger remain terminal.
- Checkpoint and runtime evidence are raw-free: no prompt, secret, file path, diff text, command text, or raw output.
- Do not change recon, QWEN_ASSIST, seal, Codex routing, acceptance authority, or subagent depth.
- This implementation does not connect the policy to the production native launcher, run live Qwen, or transfer or commit any disposable pilot patch.

## Files and Responsibilities

- `scripts/validate_plugin.py`: canonical pure runtime-ledger and checkpoint decision contract.
- `tests/test_qwen_runtime_lifecycle.py`: RED/GREEN behavior of budget stop, checkpoint creation, continuation, and terminal no-progress cases.
- `plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`: canonical Controller procedure for checkpoint evidence and fresh-session continuation.
- `docs/specs/qwen-runtime-guard-profile.md`: runtime guard contract and safety rationale.
- `docs/codex-task-lifecycle.md`: operator-facing procedure.
- `docs/decisions.md`, `docs/current-state.md`, and `tickets.md`: decision, status, and backlog evidence.

## Review Focus

- A valid `fresh_evidence_id` alone must not turn a loop or repeated tool fingerprint into a resumable session.
- A checkpoint whose ticket, scope, or baseline differs from the prior session must not authorize continuation.
- A budget stop without controller-verified progress and a red-capable next closure must stay terminal.
- A repeated or altered checkpoint must not erase earlier counters or bypass the append-only runtime-ledger anchor.
- Checkpoint projection must remain raw-free even when the worktree diff or test output contains sensitive text.

---

### Task 1: Specify the checkpoint at the executable runtime-policy seam

**Files:**
- Modify: `tests/test_qwen_runtime_lifecycle.py`
- Modify: `scripts/validate_plugin.py`

**Interfaces:**
- Consumes: existing `qwen_runtime_guard_decision(payload: object) -> dict[str, object]`, `QWEN_RUNTIME_LIMITS`, and append-only runtime ledger.
- Produces: accepted checkpoint fields `checkpoint_id`, `prior_launch_id`, `task_fingerprint`, `scope_fingerprint`, `baseline_commit`, `diff_fingerprint`, `progress_ledger_fingerprint`, `progress_sequence`, `progress_evidence_id`, `progress_kind`, and `next_closure_fingerprint`.
- Fingerprints and `checkpoint_id` use 64-character lowercase SHA-256; `baseline_commit` is the repository's 40-character lowercase Git object ID; `prior_launch_id` and `progress_evidence_id` are 32-character lowercase hexadecimal identities. `progress_kind` is exactly `LOCAL_GREEN` or `REVIEW_CONTINUE`.
- `checkpoint_id` is SHA-256 over the canonical JSON encoding (UTF-8, sorted keys, compact separators) of all checkpoint fields except `checkpoint_id` itself.

- [x] **Step 1: Add RED cases for budget-only continuation and checkpoint validation.**

Add focused tests to `QwenRuntimeLifecycleTest` using existing `base_payload`, `make_receipt`, and `make_observation` helpers:

1. A terminal `MAX_SESSION_TURNS_EXHAUSTED` observation with a complete checkpoint appends a `checkpoint` event before `terminal`; a fresh receipt, new launch id, and matching checkpoint then return `QWEN_RUNTIME_GUARD_READY` and append `session_start` without removing prior events.
2. The same continuation with prior `LOOP_DETECTED` or `REPEATED_TOOL_FINGERPRINT` returns `BLOCKED_CAPABILITY` and does not append a session event, even with a new receipt and evidence id.
3. Missing checkpoint, missing next closure, invalid hash, reused evidence/checkpoint identity, non-increasing progress sequence, changed ticket/scope/baseline, forbidden raw fields, or invalid checkpoint hash returns `BLOCKED_CAPABILITY` with no role dispatch.
4. A valid checkpoint with progress kind outside `LOCAL_GREEN` and `REVIEW_CONTINUE` is rejected.
5. Existing first-session success and non-continuation terminal tests remain unchanged in meaning.

- [x] **Step 2: Run the focused tests and observe RED.**

Run: `python -m unittest tests.test_qwen_runtime_lifecycle.QwenRuntimeLifecycleTest`

Expected: new checkpoint tests fail because the current runtime ledger does not recognize checkpoint events and currently permits a fresh receipt after loop terminal evidence.

- [x] **Step 3: Implement checkpoint hashing, validation, and terminal transition.**

In `scripts/validate_plugin.py`:

1. Add a canonical checkpoint hash helper and validate the exact field set, lowercase hash formats, positive sequence, allowed progress kind, distinct evidence id, and matching `checkpoint_id`.
2. Extend runtime observations with raw-free `task_fingerprint`, `scope_fingerprint`, and `baseline_commit`; record them in the hashed runtime observation event.
3. When a session stops for one of `MAX_SESSION_TURNS_EXHAUSTED`, `MAX_TOOL_CALLS_EXHAUSTED`, or `MAX_WALL_TIME_EXHAUSTED`, append a validated `checkpoint` event only if one is present. Always append the terminal stop event; without a valid checkpoint, do not make that stop resumable. Checkpoint evidence stores hashes/identities only; the fresh model prompt may include the verified current task context needed to act, but secrets and raw output are never copied into the receipt or ledger.
4. Permit `session_start` only after one of those three budget terminal reasons and only when the checkpoint is valid, linked to the previous launch, and matches task/scope/baseline. Require a fresh launch id and unused progress evidence id. Preserve all earlier observations and counters.
5. Reject continuation after `LOOP_DETECTED` and `REPEATED_TOOL_FINGERPRINT` regardless of new launch/evidence. Preserve existing rejection of malformed, stale, mismatched, or tampered ledgers.

- [x] **Step 4: Run the focused tests and observe GREEN.**

Run: `python -m unittest tests.test_qwen_runtime_lifecycle.QwenRuntimeLifecycleTest`

Expected: all checkpoint tests and prior lifecycle tests pass; loop and repeated-fingerprint terminals cannot resume.

### Task 2: Connect checkpoint evidence to Controller workflow instructions

**Files:**
- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`
- Modify: `docs/specs/qwen-runtime-guard-profile.md`
- Modify: `docs/codex-task-lifecycle.md`
- Modify: `docs/decisions.md`
- Modify: `docs/current-state.md`
- Modify: `tickets.md`

**Interfaces:**
- Consumes: Task 1 checkpoint contract and the existing Qwen progress ledger with `local_attempt`, `repair_candidate`, and independent `review_verdict` events.
- Produces: one consistent Controller procedure that verifies the checkpoint from the actual isolated worktree, progress ledger, test receipts, and current review evidence before invoking the existing runtime policy.

- [x] **Step 1: Write failing documentation-contract tests.**

Extend the existing documentation checks in `tests/test_validate_plugin.py` so the canonical lifecycle and human Qwen guide must describe: checkpoint fields, controller-side verification, the three resumable budget reasons, forbidden loop/fingerprint continuation, unchanged ticket/scope/baseline, and preservation of prior counters. Add a check that no Qwen-user settings or sampling controls are introduced.

- [x] **Step 2: Run the documentation-contract tests and observe RED.**

Run: `python -m unittest tests.test_validate_plugin.ValidatePluginTest`

Expected: the new assertions fail because the workflow documents fresh evidence but not the complete checkpoint contract.

- [x] **Step 3: Document the operational checkpoint sequence consistently.**

Update the canonical lifecycle and human guide to instruct the Controller to verify, before continuation: identical task/scope/baseline fingerprints; observed diff fingerprint; canonical progress-ledger fingerprint and strictly increasing sequence; the latest RED/GREEN or independent `CONTINUE` evidence; and one concrete next closure. The Controller then emits only the raw-free checkpoint fields from Task 1 and starts a fresh guarded session. The continuation prompt retains the original requirements and adds the verified current state needed to act; the prompt itself is not copied into the raw-free receipt or ledger. Document that loop/repeated fingerprint and invalid progress remain terminal.

Add a new decision after D046 describing the observed fixed-budget-versus-loop failure mode, the chosen evidence-gated continuation, and measurable stop/continuation criteria. Add a Ticket 22 entry in `tickets.md` with the dependency on Tickets 16/17/18 and status `implemented locally` only after Task 4 completes. Update `docs/current-state.md` without claiming live multi-repair evidence.

- [x] **Step 4: Run the documentation-contract tests and observe GREEN.**

Run: `python -m unittest tests.test_validate_plugin.ValidatePluginTest`

Expected: all documentation policy assertions pass with one consistent procedure and no changes to Qwen settings or mode limits.

### Task 3: Validate the full local contract and record evidence

**Files:**
- Modify: `tests/test_qwen_runtime_lifecycle.py`
- Modify: `tests/test_validate_plugin.py`
- Modify: `scripts/validate_plugin.py`
- Verify: all files listed in Tasks 1 and 2

**Interfaces:**
- Consumes: Task 1 executable contract and Task 2 canonical/human instructions.
- Produces: passing unit tests and plugin validators proving raw-free, append-only, evidence-gated continuation locally. No claim of live Qwen effectiveness.

- [x] **Step 1: Run the targeted runtime and policy suites.**

Run: `python -m unittest tests.test_qwen_runtime_lifecycle tests.test_qwen_runtime_guard tests.test_validate_plugin`

Expected: all targeted suites pass, including existing recon, mode, progress-ledger, and profile tests.

- [x] **Step 2: Run repository and package validators.**

Run: `python scripts/validate_plugin.py plugins/agentic-development-workflow`

Expected: exit 0 and validator reports no protocol, package, or documentation-contract errors.

- [x] **Step 3: Run the complete local unit suite.**

Run: `python -m unittest discover -s tests`

Expected: all discovered tests pass; record the observed test count.

- [x] **Step 4: Review the diff against the approved design.**

Confirm that only checkpoint policy, its tests, canonical/human documentation, decision, backlog, and current-state evidence changed. Confirm no changes to per-session limits, Qwen settings, provider, credentials, sampling, role depth, acceptance authority, or external files. Do not run Qwen as part of this implementation plan.

## Plan self-review

- Spec coverage: progress checkpoint, same-task/scope/baseline binding, fresh-session identity, counter preservation, stop-on-loop, fixed per-session ceilings, and local validation are assigned to Tasks 1–3.
- Review focus coverage: loop/fingerprint, mismatched task context, missing progress/next closure, tampering/replay, and raw-free projection are covered by Task 1 tests and Task 2 documentation checks.
- No placeholder steps remain; test commands and expected outcomes are explicit.
- Scope remains local policy implementation and evidence only; production native-launcher integration is Ticket 23, and a live multi-repair pilot follows that integration as a separate bounded stage.
- Final local evidence: targeted suites `104/104`; plugin validator exit code `0`; complete suite `165/165`; fresh read-only review PASS after raw-free event-schema corrections.
