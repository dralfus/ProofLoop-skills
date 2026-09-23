# 02 — ReconReportContract: единый executable validator

**What to build:** Python и PowerShell recon paths принимают и отклоняют `QWEN_RECON_REPORT` по одной семантике baseline, facts, writes, stop reason и terminal status.

**Blocked by:** None — can start immediately

**Status:** implemented locally; awaiting review/commit

- [x] Одинаковые malformed, incomplete, read-only violation и baseline mismatch дают одинаковые raw-free reasons.
- [x] JSON Schema остаётся декларативным контрактом, а host-side validator сохраняет fail-closed ограничения.
- [x] Production-shaped reports покрыты общим Python contract suite и PowerShell launcher regressions.

Implementation: `scripts/recon_report_contract.py` is the single semantic
validator. `qwen_assist.py` and `invoke_qwen_finish_ticket.ps1` delegate to it;
PowerShell only handles temporary-file I/O and maps the raw-free verdict. No
Qwen settings, provider, credentials or external MCP configuration changed.
