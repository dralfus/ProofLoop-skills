# 01 — Runtime adapter contract и совместимость Codex-профиля

**What to build:** Controller определяет совместимый runtime по проверяемым capabilities и выбирает его policy без изменения поведения существующего Codex workflow. Несовместимое окружение получает понятный `BLOCKED_CAPABILITY`, а не неявный fallback.

**Blocked by:** None — can start immediately.

**Status:** implemented locally; full live Qwen `$finish-ticket` pilot pending.

- [x] Controller использует явный runtime adapter contract для capability preflight, model identity, role dispatch/continuation, tool policy и observed usage.
- [x] Auto-selection сохраняет действующий adaptive Codex profile и его model/budget policy.
- [x] Runtime без обязательных capabilities завершается `BLOCKED_CAPABILITY` без self-review или предполагаемого provider fallback.
- [x] Контракт и profile selection проверены lifecycle fixtures; текущий Codex сценарий остаётся совместимым.

Evidence: canonical lifecycle, `scripts/validate_plugin.py`, profile fixtures
and end-to-end policy fixtures. Fixture coverage is local contract evidence;
it does not claim a live Qwen role run.
