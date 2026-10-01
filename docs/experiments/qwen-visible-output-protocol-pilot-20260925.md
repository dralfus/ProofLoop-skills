# Bounded Qwen visible-output protocol pilot — 2026-09-25

## Purpose and scope

Exercise one clean disposable native Qwen protocol launch after adding raw-free
launch-stage diagnostics and opt-in visible child output. The first proposed
test (`changed_lines=0`) was already present in clean HEAD `eeb1813`; after owner
approval, the test-only scope was changed to a direct regression for
`validate_patch_candidate(changed_lines=201)`. No product Ticket 314
implementation/acceptance or transfer was authorized.

The disposable task required one method in `tests/test_qwen_assist.py`, at most
20 added lines, only its exact targeted unittest, independent review/verifier,
and no production/docs/config changes, full suite, commit or push. The ticket
was kept outside the disposable checkout. Its target HEAD was
`eeb181364ad54c3b39bb2733de9213613831d554`; the checkout was clean immediately
before launch.

## Budget and gates

- Capability smoke: `0 turns / 0 tool calls / 0s / depth 0`; `qwen --version`
  and `qwen --help` only. Result: Qwen CLI `0.24.5`; all five required markers
  present; no model request.
- One protocol attempt: `20 turns / 20 tool calls / 30m / depth 1`,
  `qwen.cmd`, `-ShowOutput`, receipt directory under the workspace `.scratch`.
- No retry was permitted after a gate, evidence or protocol failure.

Capability receipt:
`.scratch/qwen-visible-protocol-pilot-20260925/capability-smoke.json`.

## Terminal outcome

The single protocol invocation ended after `1441 ms` with
`QWEN_COMMAND_FAILED`. The raw-free `QWEN_TERMINAL_OUTCOME` v2 is:

- `outer_stage=RUNTIME_EVIDENCE_PARSED`
- `supervisor_stage=NOT_REACHED`
- `process_state=NOT_STARTED`, no process exit code
- `event_file_state=NOT_OBSERVED`, no event byte count
- `turn_count=NOT_AVAILABLE`, `tool_call_count=NOT_AVAILABLE`
- `session_ended=false`, `budget_stop=false`, `loop_status=UNOBSERVED`
- `console_output_mode=VISIBLE`; no Qwen child output was emitted
- `terminal_receipt_written=true`

Receipt:
`.scratch/qwen-visible-protocol-pilot-20260925/receipts/QWEN_TERMINAL_OUTCOME-2768b56dc45049c2ab115d45c2ddabe0.json`.

The parent parsed a fail-closed CLI projection, but the native supervisor was
never reached and no Qwen child/model request started. The evidence localizes
the failure to before child dispatch; it does not distinguish Credential
Manager lookup from another CLI pre-launch failure. It is not evidence of an
API/provider/transport failure and does not prove Qwen implementation E2E.
The disposable checkout remained clean; no test patch was created. No retry was
performed.

## Recommendation

Keep Ticket 24 `BLOCKED_EVIDENCE_SOURCE` and the implementation pilot unproven.
Next, add or use a bounded raw-free local diagnostic for CLI pre-launch stages
to distinguish credential acquisition from supervisor dispatch without
printing or inspecting a secret. Any new live Qwen attempt requires separate
authorization; do not retry this launch unchanged.
