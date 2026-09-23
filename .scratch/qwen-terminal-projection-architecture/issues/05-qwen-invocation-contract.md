# 05 — QwenInvocationContract: registry bounded argv

**What to build:** Assist, recon, protocol и capability-smoke paths получают mode-specific invocation contracts из единой registry, сохраняя различия budgets, exclusions и authority.

**Blocked by:** 01 — QwenTerminalProjection; 02 — ReconReportContract

**Status:** implemented locally; awaiting review/commit

- [x] Маркеры capabilities, authority flags и argv rendering согласованы между adapters.
- [x] Protocol, recon и seal не объединяются в один неразличимый режим.
- [x] Contract matrix доказывает отсутствие drift без запуска Qwen.

Implementation: `scripts/qwen_invocation_contract.py` is the registry. Assist,
native recon, protocol, seal and capability-smoke adapters consume its mode
contracts or renderers; tests compare limits, markers, exclusions, authority
and argv without starting Qwen.
