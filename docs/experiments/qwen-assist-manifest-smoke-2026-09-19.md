# QWEN_ASSIST: minimal patch-manifest smoke, 2026-09-19

## Purpose

This is a transport experiment, not Ticket 314 implementation or acceptance.
It distinguishes whether the missing `QWEN_PATCH_CANDIDATE` manifest depends
on the original packet's complexity or on the `yolo` structured-output path.

## Preconditions

- fixed point: `732dfc77bd6d374651227f949c13c44ab8c2f8f1`;
- Qwen Code capability probe exposed `--bare`, JSON output/schema, worktree,
  approval mode, turn/wall/tool limits and tool exclusions;
- Generic Credential `ProofLoop/Qwen/OpenAI` was injected only into the child
  process;
- a fresh `plan` recon over `tests/test_qwen_assist.py` returned a schema-valid
  `EVIDENCE_FOUND` terminal result in two turns, with three independently
  confirmed facts and an empty `writes` array;
- both calls used disposable worktrees and `--bare`, without `--safe-mode`.

## Write packet

The separate `yolo` worktree received one bounded task: add one focused unit
test to `tests/test_qwen_assist.py`, change no other file, do not run commands,
Git, network/MCP, subagents or acceptance, then return the patch schema. The
declared targeted command was the new test method only. The patch schema still
required no Git operations and `full_suite: false`.

## Observed result

The child ended with `FatalTurnLimitedError` at the 12-turn limit and produced
no stdout event array or terminal `structured_result`. It therefore produced no
schema-valid patch manifest. Independent inspection of the disposable worktree
found exactly one changed file and 11 added lines; the declared targeted test
passed. The main checkout received no code changes.

## Conclusion

The configured Qwen endpoint, Credential Manager path, capture transport and
read-only terminal schema are working. The remaining blocker is specifically
the `yolo` completion path: Qwen can apply the minimal edit but does not invoke
`structured_output` before the fixed turn budget. This is `QWEN_UNUSABLE` for
the patch-output contract, not evidence that Ticket 314 is implemented or
accepted. The two disposable worktrees and branches were removed; terminal
captures and the schema-valid recon receipt remain only under local AppData.

The health gate prohibits another same-root write retry. Raising the turn limit
or changing the write-mode contract would be a new design decision, not an
automatic continuation.
