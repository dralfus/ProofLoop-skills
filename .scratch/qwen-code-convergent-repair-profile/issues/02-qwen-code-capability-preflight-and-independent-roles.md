# 02 — Qwen Code capability preflight и независимые роли

**What to build:** Пользователь Qwen Code запускает `$finish-ticket` той же короткой командой и получает Qwen-specific preflight только тогда, когда runtime реально способен создать независимые роли и выполнить evidence-проверки.

**Blocked by:** 01 — Runtime adapter contract и совместимость Codex-профиля.

**Status:** ready-for-agent

- [ ] Qwen profile проверяет runtime version, configured single-model identity, fresh named subagent, continuation Implementer, read-only Reviewer policy и executable verification command.
- [ ] Все роли Qwen используют одну подтверждённую model identity; неявная смена provider или модели блокируется.
- [ ] Reviewer создаётся как fresh named read-only role с отдельным контекстом; fork и write-capable review не дают independent acceptance evidence.
- [ ] Отсутствующая capability приводит к `BLOCKED_CAPABILITY`; успешный preflight содержит наблюдаемую конфигурацию runtime и доступное usage-evidence.
