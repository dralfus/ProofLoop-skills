# QWEN_PATCH_SEAL design

## Intent

`QWEN_PATCH_SEAL` separates Qwen's ability to make a bounded candidate edit
from its unreliable `yolo` terminal structured-output completion. It preserves
Qwen as the issuer of the patch manifest and keeps Controller as the only
authority able to verify or transfer a candidate.

## Observed failure

The 2026-09-19 manifest smoke established that `plan` can return a
schema-valid final `structured_result`, while `yolo` can make a one-file edit
and pass its targeted test but exhausts 12 turns before calling
`structured_output`. Retrying that `yolo` packet is prohibited by the existing
health gate. Increasing its turn budget would spend more budget without making
completion deterministic.

## Decision

Introduce one optional, terminal stage after an unsealed `yolo` candidate:

```text
confirmed recon
  -> yolo candidate worktree
  -> missing yolo manifest + bounded observed diff
  -> Controller scope and targeted-test receipt
  -> one read-only QWEN_PATCH_SEAL call in plan mode
  -> Qwen patch manifest matched to observed receipt
  -> independent review and optional transfer
```

The seal is not a retry of the `yolo` worker. It is a distinct, single-use
read-only completion stage with its own normalized root cause and consumes one
of the ticket's seven Qwen calls. It is available only when all of these facts
are already independently observed:

- the candidate worktree has an uncommitted diff with one or two files and at
  most 200 changed lines;
- no Git integration operation occurred;
- exactly one declared targeted command passed in that worktree;
- the candidate baseline matches the recon baseline;
- the original `yolo` failure is specifically missing terminal structured
  output at its turn limit.

## Packet and result contract

The Controller constructs a raw-free `PATCH_SEAL_RECEIPT` from observed facts:
baseline, changed file names, changed-line count, targeted command and result,
and the terminal yolo reason. It does not generate a manifest.

Qwen receives this receipt and a read-only `plan` packet. It cannot edit,
execute shell commands, use Git, network/MCP or subagents. Its only useful
completion is the existing `qwen-assist-patch.schema.json` manifest. The
manifest is accepted only when every declared file, changed-line count,
targeted test, empty `git_operations`, and `full_suite: false` exactly matches
the observed receipt. Any mismatch, missing terminal result or schema failure
is `QWEN_UNUSABLE` for `patch-seal` and no fallback or transfer occurs.

## Authority and safety

`QWEN_PATCH_SEAL` does not make an unsealed candidate acceptable. Controller
still validates the actual diff and test receipt, then runs independent review
before it can transfer anything. Qwen never receives commit, merge,
cherry-pick, push, full-suite or acceptance authority. The seal receipt stores
no token, prompt, source text or raw terminal transcript in Git or metrics.

## Implementation boundaries

- `scripts/qwen_assist.py`: validate the observed receipt and compare it with a
  Qwen-produced manifest.
- `scripts/invoke_qwen_assist.ps1` and capture wrapper: add an explicit
  `seal` mode that always uses `plan`, patch schema and read-only exclusions.
- tests: RED/GREEN coverage for receipt shape, exact matching, mode/tool
  restrictions and no-transfer failures.
- canonical lifecycle, QWEN_ASSIST reference, plugin skill, human lifecycle
  docs and `docs/decisions.md`: describe the new stage and its stop gates.

## Acceptance criteria

1. A seal cannot start without a bounded observed candidate receipt and the
   specific missing-yolo-manifest reason.
2. Seal mode cannot write, run shell/Git/network/subagent/full-suite actions.
3. Only an exact Qwen-produced patch manifest can turn an unsealed candidate
   into `SEALED_CANDIDATE`; Controller cannot synthesize it.
4. Mismatch or missing output remains terminal `QWEN_UNUSABLE` with no
   automatic retry.
5. A new isolated smoke demonstrates the complete yolo-edit -> Controller
   receipt -> Qwen plan-seal manifest path; it remains non-acceptance evidence.
