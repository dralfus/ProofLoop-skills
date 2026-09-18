# QWEN_ASSIST: Ticket 314 captured read-only recon 2026-09-18

## Scope

One QWEN_RECON invocation used clean fixed point
`ccff98153bb5d01d25300f7227a87c2b8d075dba`, `--bare`, plan mode, JSON schema,
the configured OpenAI-compatible route, and the file-backed capture transport.
The packet permitted only `read_file` for five named bridge files and prohibited
writes, shell, tests, network/MCP, subagents, Git, and acceptance.

## Outcome

The capture transport completed and preserved stderr. Qwen terminated with exit
code `53`, `FatalTurnLimitedError`, and no terminal `structured_output` after
the 12-turn limit. No `QWEN_RECON_REPORT` was available for Controller review.

The isolated worktree was clean and removed with its temporary branch. This is
the same normalized root cause as the prior Ticket 314 pilot, so the health gate
prohibits an automatic retry. It is `QWEN_UNUSABLE` for this read-only packet,
not Ticket 314 acceptance evidence or a verdict on the ticket.
