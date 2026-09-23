# 04 — Production-shaped Qwen contract fixtures

**What to build:** Поведенческие fixtures проверяют runtime semantics Qwen adapters через публичные interfaces, а source-text assertions остаются только минимальным smoke coverage.

**Blocked by:** 01 — QwenTerminalProjection; 02 — ReconReportContract; 03 — QwenGuardPolicy

**Status:** complete; committed in `4751c04` (`feat(qwen): unify bounded runtime contracts`)

- [x] Regression matrix ловит terminal event, malformed JSON, baseline mismatch, no-write и credential-restore failures.
- [x] Удаление production helper приводит к красному поведенческому тесту через публичные interfaces.
- [x] Acceptance evidence остаётся независимой от fixture-only GREEN.

Implementation: `tests/fixtures/qwen-adapters/production-shaped.json` feeds
public terminal/recon interfaces; the credential case executes a copied public
PowerShell wrapper with a fake Qwen process and stub Credential Manager. No
live Qwen, acceptance, transfer or product implementation is performed.
