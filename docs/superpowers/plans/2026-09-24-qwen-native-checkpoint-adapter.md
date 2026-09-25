# Native Qwen checkpoint adapter implementation plan

> **Execution mode:** Native, inline in the current workspace. Preserve existing dirty and untracked user files; do not commit or push.

**Goal:** Connect Ticket 22's progress-gated runtime policy to the native Qwen protocol launcher through independent host evidence checks and a raw-free Qwen event projection.

**Architecture:** Add a pure Python adapter for JSONL projection and checkpoint host verification, invoke the existing `qwen_runtime_guard_decision` only after host checks pass, then connect the adapter to an explicit continuation path in PowerShell. The event sidecar is treated as sensitive and ephemeral. Add contract tests with fake Qwen and fixture evidence; no live model request.

**Spec:** `docs/superpowers/specs/2026-09-24-qwen-native-checkpoint-adapter-design.md`

## Global constraints

- Do not edit Qwen/Stepler settings, caches, credentials, provider, sampling or role profiles.
- Preserve Qwen `20 / 20 / 30m / 1`, configured reasoning and loop detection.
- Do not perform a live Qwen task, implementation, acceptance, patch transfer, commit or push.
- Never persist or print raw JSONL event contents. Always remove temporary event files.
- Only call Qwen after all host evidence checks and the runtime policy return READY.
- A recognized loop/repeated fingerprint, evidence mismatch, unknown status, or projection failure is terminal and never retried.

## Task 1: Build host evidence and raw-free event adapter

**Files:** add `scripts/qwen_runtime_adapter.py`, add `tests/test_qwen_runtime_adapter.py`.

- [x] Add fixture tests for valid/invalid JSONL event projection, raw field exclusion, incomplete event stream, session lifecycle, counter extraction, and prove `session_end` is not inferred as budget stop.
- [x] Add host adapter tests using disposable temporary Git repos for matching baseline/task/scope/diff/progress receipts, and mismatches for each input.
- [x] Implement a stable `QWEN_RUNTIME_EVIDENCE_UNSUPPORTED` block for event schemas/statuses not explicitly supported.
- [x] Implement task/scope/baseline/diff/progress/test/review receipt validation and call Ticket 22 runtime policy only after every check passes.
- [x] Run focused tests; initial import-red before adapter implementation, then focused green.

## Task 2: Connect explicit continuation to native launcher

**Files:** modify `scripts/qwen_invocation_contract.py`, `scripts/invoke_qwen_finish_ticket.ps1`, `scripts/invoke_qwen_finish_ticket_cli.ps1`, and `tests/test_qwen_runtime_guard.py` (plus focused argv tests as required).

- [x] Add the required `--json-file` capability marker without changing mode ceilings.
- [x] Create an ephemeral JSONL event file for protocol runs; include its path in exact argv contract; project to a raw-free summary; delete it from `finally` on success, failure and launch exception.
- [x] Add an explicit continuation request parameter. Run the evidence adapter and policy before the child process; reject malformed path/JSON/receipt and blocked results without launching fake or real Qwen.
- [x] Generate fresh receipt/launch/evidence identities and pass the unchanged ticket plus verified continuation packet only on READY.
- [x] Keep regular protocol argv unchanged except the documented sidecar flag; preserve nonzero terminal exit and projected counters.
- [x] Add PowerShell fake-child tests proving one dispatch on READY, zero dispatch on block, no leaked event contents, event-file cleanup, unchanged limits, and argument-contract enforcement.

## Task 3: Synchronize canonical/human docs and backlog

**Files:** modify canonical plugin lifecycle, runtime guard profile, operator lifecycle, decisions, current-state and `tickets.md`; add/update documentation tests.

- [x] Record concrete failure mode, the launcher/policy gap, minimal adapter change, and measurable criteria in `docs/decisions.md`.
- [x] Document the raw-event file as sensitive, ephemeral data; describe the explicit continuation gate and fail-closed unknown terminal evidence.
- [x] Keep Ticket 23 local implementation status separate from live pilot status; define the live pilot as an independent gated ticket.
- [x] Add contract assertions that settings/provider/sampling/reasoning/limits are unchanged and live Qwen remains NOT_RUN.

## Task 4: Validate and review

- [x] Run focused adapter/runtime/launcher/argv/doc tests.
- [x] Run `python scripts/validate_plugin.py plugins/agentic-development-workflow`.
- [x] Run full discovered tests sequentially after targeted tests.
- [x] Review this implementation against the approved design and dirty-file boundary; correct findings and rerun affected tests.
- [x] Report exact final test counts, validator status, remaining live pilot gate, and no commit/push.

## Execution result

- Focused adapter/runtime/launcher/argv/doc suite: 112 tests passed.
- Full discovered suite: 181 tests passed.
- `scripts/validate_plugin.py plugins/agentic-development-workflow`: PASS.
- PowerShell parser: both production launcher scripts parse without errors.
- `git diff --check`: PASS.
- Live Qwen multi-repair continuation: NOT_RUN; the current sidecar projection
  cannot prove budget-stop reason or loop-clear. Ticket 24 remains a separate
  gate; no Qwen model request, settings change, commit or push was made.
