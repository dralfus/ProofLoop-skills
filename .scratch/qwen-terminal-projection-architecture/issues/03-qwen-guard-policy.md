# 03 — QwenGuardPolicy: pure guarded-launch policy

**What to build:** До любого Qwen dispatch единый policy module принимает проверенные settings, worktree, capabilities и receipt facts и возвращает raw-free decision с authority flags.

**Blocked by:** 01 — QwenTerminalProjection; 02 — ReconReportContract

**Status:** implemented locally; awaiting review/commit

- [x] Protocol и recon сохраняют разные budgets и authority contracts при общей policy seam.
- [x] Ни один side-effectful Qwen launcher не вызывается до успешного decision.
- [x] Receipt freshness, fixed point, loop detection и terminal stop остаются fail-closed.

Implementation: `scripts/qwen_guard_policy.py` is a pure raw-free pre-dispatch
policy. The guarded PowerShell launcher serializes only projected facts to a
temporary file, requires `QWEN_GUARD_READY`, and invokes the Qwen child only
after that decision. Protocol/recon limits and authority flags remain distinct;
Qwen settings, provider, credentials and external MCP configuration are not
modified.
