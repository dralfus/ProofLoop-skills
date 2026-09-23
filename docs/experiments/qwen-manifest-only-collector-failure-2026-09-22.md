# Qwen manifest-only seal after collector repair, 2026-09-22

## Scope

One disposable test-only candidate in the existing `qwen-patch-ticket-314`
worktree. No product implementation, acceptance, transfer, Git operation or
Qwen setting/provider change was allowed. The candidate diff remained one test
file with 17 added lines and its focused test exited `0`.

## Collector repair

The capture reader now normalizes singleton and array JSON through an explicit
`[object[]]` terminal-event projection, accepts only final
`type=result`, `is_error=false`, `subtype=success` with an object
`structured_result`, and classifies empty stdout as
`MISSING_TERMINAL_PATCH_MANIFEST`. The malformed singleton-property `.Count`
path in the guarded collector was also normalized.

## Seal diagnostics

The local raw-free receipt was independently validated and each packet used a
fresh reservation identity under the changed-scope reason
`COLLECTOR_PROJECTION_FAILED`. Agent/edit/shell tools remained excluded and
`review,loop` stayed disabled.

1. `7dd8ce112bcc4b909393af741c49e8ad`: `2 turns / 0 tools / 90s`; empty
   stdout and `FatalTurnLimitedError`.
2. `feef28d628a44547a9ea8baed2c28325`: `4 turns / 0 tools / 180s`; terminal
   JSON error envelope classified `structured_output_missing`.
3. `4d1f3cc76a554fd0a807160a5fbcbe6f`: `4 turns / 1 tool / 180s` with an
   explicit structured-output instruction; same structured-output error.
4. `643d1b35725447ed806b3c3d284b52e6`: `12 turns / 1 tool / 300s` with the
   same instruction; empty stdout and `FatalTurnLimitedError`.

The repaired collector returned raw-free
`QWEN_UNUSABLE / MISSING_TERMINAL_PATCH_MANIFEST` for the empty-output runs;
no `SEALED_CANDIDATE` was created. Auth/forbidden and transport classifiers
were false for the terminal captures. This is a terminal Qwen CLI/provider
structured-output limitation after three changed bounded packets, not a
collector or candidate-scope failure; no further blind retry was made.

## Follow-up diagnosis and E2E seal, 2026-09-23

The red-capable differential loop isolated two independent failures:

1. The same packet through explicit `qwen.cmd` still ended with `exit=53`,
   empty stdout and `FatalTurnLimitedError`; the entrypoint and collector were
   not the cause. A simple smoke schema succeeded, while the patch schema
   repeatedly exhausted turns before a structured call.
2. A normal launch with the old Qwen worktree slug was rejected before model
   execution because `worktree-qwen-patch-ticket-314` already existed. The
   existing branch/worktree was preserved; a fresh slug was used instead.

The provider-facing patch schema was reduced to required fields plus basic JSON
types. Strict bounds (`const`, min/max constraints and union types) remain
enforced by `qwen_assist.py` when comparing the manifest with the independent
`PATCH_SEAL_RECEIPT`; they are no longer sent as model-generation constraints.

Fresh bounded seal launch `cbffea5e84ed421cb1566e61b7cd4485` used
`12 turns / 1 structured_output call / 300s / depth1`, a fresh slug and fresh
reservation identity. The capture reader returned `SEALED_CANDIDATE`. No
transfer, commit, acceptance or product implementation followed. This is the
first end-to-end proof of the Qwen manifest-only seal path.
