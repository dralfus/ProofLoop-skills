# 04 — Поставка Qwen extension и сквозное evidence workflow

**What to build:** Пользователь получает устанавливаемую Qwen Code оболочку для того же `finish-ticket` workflow и проверяемое сквозное доказательство, что Codex и Qwen profiles соблюдают общие инварианты при разных repair policies.

**Blocked by:** 02 — Qwen Code capability preflight и независимые роли; 03 — Сходящийся Qwen repair-loop и progress ledger.

**Status:** implemented; real Qwen pilot is `NOT_RUN` because the CLI is absent

- [x] Qwen Code получает discoverable skill/agent extension с коротким пользовательским запуском и без копирования канонического lifecycle.
- [x] Канонический protocol, Codex plugin, Qwen delivery adapter и человеческие инструкции согласованно описывают auto-selection, capability gate и profile-specific repair policy.
- [x] Сквозные fixtures подтверждают сохранение Codex numeric policy, Qwen convergence без numeric repair cap, non-progress stop и regression stop.
- [x] Evidence фиксирует runtime/model identity, роль, findings, verdicts, команды и observed usage либо честный `NOT_AVAILABLE`.
- [x] Реальный Qwen ticket или эквивалентный воспроизводимый pilot записывает несколько repair-candidates и итоговый terminal verdict для сравнения с исходным workflow; при отсутствии CLI evidence фиксирует `NOT_RUN`, а synthetic fixtures не выдаются за live run.
