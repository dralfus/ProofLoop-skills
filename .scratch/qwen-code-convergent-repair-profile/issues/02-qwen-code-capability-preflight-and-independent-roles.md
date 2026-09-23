# 02 — Qwen Code capability preflight и независимые роли

**What to build:** Пользователь Qwen Code запускает `$finish-ticket` той же короткой командой и получает Qwen-specific preflight только тогда, когда runtime реально способен создать независимые роли и выполнить evidence-проверки.

**Blocked by:** 01 — Runtime adapter contract и совместимость Codex-профиля.

**Status:** implemented locally; live role capability attestation pending.

- [x] Qwen profile проверяет runtime version, configured single-model identity, fresh named subagent, continuation Implementer, read-only Reviewer policy и executable verification command.
- [x] Все роли Qwen должны использовать одну declared model identity; неявная смена provider или модели блокируется.
- [x] Reviewer policy требует fresh named read-only role; fork и write-capable review не дают independent acceptance evidence.
- [x] Отсутствующая capability приводит к `BLOCKED_CAPABILITY`; preflight сохраняет доступное usage-evidence и честный `NOT_AVAILABLE`.

Evidence: profile validator and missing/malformed-capability fixtures cover the
fail-closed contract. Whether the installed Qwen runtime actually satisfies
these role capabilities remains unverified until the full live pilot.
