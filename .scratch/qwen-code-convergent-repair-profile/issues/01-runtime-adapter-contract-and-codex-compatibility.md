# 01 — Runtime adapter contract и совместимость Codex-профиля

**What to build:** Controller определяет совместимый runtime по проверяемым capabilities и выбирает его policy без изменения поведения существующего Codex workflow. Несовместимое окружение получает понятный `BLOCKED_CAPABILITY`, а не неявный fallback.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Controller использует явный runtime adapter contract для capability preflight, model identity, role dispatch/continuation, tool policy и observed usage.
- [ ] Auto-selection сохраняет действующий adaptive Codex profile и его model/budget policy.
- [ ] Runtime без обязательных capabilities завершается `BLOCKED_CAPABILITY` без self-review или предполагаемого provider fallback.
- [ ] Контракт и profile selection проверены внешними lifecycle fixtures; текущий Codex сценарий остаётся совместимым.
