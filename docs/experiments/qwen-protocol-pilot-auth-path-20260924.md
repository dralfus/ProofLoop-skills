# Native Qwen protocol preflight and auth-path repair, 2026-09-24

## Bounded attempt

- Mode: native `protocol`.
- Budget: `20 turns / 20 tool calls / 30m / depth 1`.
- Task: the disposable one-method regression pilot in
  `.scratch/qwen-protocol-pilot-20260924/qwen-protocol-pilot-ticket.md`.
- `--safe-mode`: not enabled.
- No Qwen model request, role dispatch, test, worktree edit, product acceptance,
  transfer, commit, or push occurred.

Raw-free launcher result: `BLOCKED_CAPABILITY /
LOCAL_SETTINGS_UNAVAILABLE`, `0 turns`, `0 tool calls`, `duration_ms=265`,
`model_request_started=false`. Per the stop-on-first-failure rule there was no
retry.

Read-only diagnosis found a profile-path mismatch: the operator's `USERPROFILE`
contains a readable, valid `.qwen/settings.json` with a `model` object, while
`.NET Environment.SpecialFolder.UserProfile` resolves to a different profile
with no settings file. The launcher default used the latter. No settings file
or Qwen configuration was edited.

## Local fixes and evidence

1. The native protocol compatibility layer did not read Windows Credential
   Manager, and the parent launcher did not forward a non-default
   `CredentialTarget`. OpenAI-compatible Qwen auth requires a process API key.
   A production-shaped fake Credential Manager test first failed because the
   child did not observe the fixture key; after the fix it passed. The protocol
   path now injects the key only for a native Qwen CLI child and restores the
   prior process environment immediately after Qwen returns, before Python
   projection; `finally` is the exception-path fallback. A regression test
   records only whether the fixture credential is present: it first failed
   because the projector inherited the key, then passed after early restore.
   The key is never projected.
2. The settings default now uses `$env:USERPROFILE`, matching the operator's
   actual Qwen configuration location instead of the mismatched .NET special
   folder.
3. No user Qwen settings, provider, sampling, reasoning, role profile,
   credentials, or external Qwen/Stepler files were changed.

At this point the protocol pilot was still `NOT_RUN`: correcting preflight did
not automatically retry after the terminal guard failure. A later distinct
bounded launch is recorded below. The current protocol terminal-evidence
limitation for Ticket 24 is independent and remains open.

## Separate bounded launch and collector diagnosis

A later distinct bounded native `protocol` launch used the same ceilings
(`20 turns / 20 tool calls / 30m / depth 1`) and the disposable Ticket 18
test-only scope. It returned only raw-free
`QWEN_COMMAND_FAILED` (`terminal_reason=QWEN_COMMAND_FAILED`) after
`33,279 ms`. `turn_count` and `tool_call_count` were `NOT_AVAILABLE`,
`session_ended=false`, `loop_status=UNOBSERVED`, `budget_stop=false`, and the
guard receipt had `terminal_stop=null`. No retry followed. The actual Qwen-side
failure cause is unknown: the old collector discarded the adapter projection
and no durable raw event data is retained.

Local RED→GREEN regression tests then identified the collector defect without
another model request. The runtime adapter returns exit code `3` with valid
raw-free JSON for a fail-closed error result; the CLI bridge accepted only exit
`0` and replaced the useful projection with `QWEN_RUNTIME_EVIDENCE_UNSUPPORTED`.
The parent also omitted Qwen/projector exit codes and available failure
counters. D050 changes that contract and tests the complete synthetic
adapter→CLI→parent path. It classifies only allowlisted `is_error`, `subtype`
and `error.message` category, session hash, counters, wall time and tool
fingerprint. Raw message, URL, token, transcript and session ID are never
published. The test's synthetic `403` classification is not evidence that the
live failure was an auth/403 failure.

The actual bounded pilot remains failed and does not prove a successful native
protocol E2E run. No Qwen settings, provider, sampling, reasoning, role profile
or external Qwen/Stepler files were changed. Another live attempt requires
separate owner authorization.
