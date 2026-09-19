# QWEN_PATCH_SEAL runtime smoke, 2026-09-19

## Scope

This isolated smoke tested the new `QWEN_PATCH_SEAL` path, not Ticket 314
implementation or acceptance. Baseline was `75cfd8d7d32c9e4525601c67501ff2d6b70ae9e9`.
Captures and receipts remain only in local AppData.

## Evidence

A fresh read-only recon returned schema-valid `EVIDENCE_FOUND`. The bounded
yolo candidate changed one test file by nine lines and its declared targeted
test passed, but ended with `FatalTurnLimitedError` without a terminal patch
manifest. Controller produced a schema-valid raw-free `PATCH_SEAL_RECEIPT` and
made one read-only seal call in effective Qwen `plan` mode. That call also ended
with `FatalTurnLimitedError`, without stdout or terminal structured result.

## Outcome

The Python and PowerShell gates correctly prevented transfer: no
`SEALED_CANDIDATE` was created. This is terminal `QWEN_UNUSABLE` for the
patch-seal output contract; no retry was made. Disposable Qwen worktrees and
branches were removed. The main feature worktree received no Qwen candidate
diff.
