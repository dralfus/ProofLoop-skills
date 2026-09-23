# 04 — Поставка Qwen extension и сквозное evidence workflow

**What to build:** Пользователь получает устанавливаемую Qwen Code оболочку для того же `finish-ticket` workflow и проверяемое сквозное доказательство, что Codex и Qwen profiles соблюдают общие инварианты при разных repair policies.

**Blocked by:** 02 — Qwen Code capability preflight и независимые роли; 03 — Сходящийся Qwen repair-loop и progress ledger.

**Status:** extension and fixture implementation complete; full native Qwen
`$finish-ticket` repair pilot is `NOT_RUN`.

- [x] Qwen Code получает discoverable skill/agent extension с коротким пользовательским запуском и без копирования канонического lifecycle.
- [x] Канонический protocol, Codex plugin, Qwen delivery adapter и человеческие инструкции согласованно описывают auto-selection, capability gate и profile-specific repair policy.
- [x] Сквозные fixtures подтверждают сохранение Codex numeric policy, Qwen convergence без numeric repair cap, non-progress stop и regression stop.
- [x] Evidence фиксирует runtime/model identity, роль, findings, verdicts, команды и observed usage либо честный `NOT_AVAILABLE`.
- [ ] Реальный Qwen ticket или эквивалентный воспроизводимый pilot записывает несколько repair-candidates и итоговый terminal verdict для сравнения с исходным workflow; synthetic fixtures не выдаются за live run.

Clarification: the owner has confirmed that Qwen CLI is installed and answers.
`NOT_RUN` describes this full native role-lifecycle pilot, not CLI availability.
The separate `QWEN_ASSIST` bounded recon and manifest-only seal evidence do not
exercise Implementer continuation, fresh Reviewer, Verifier or final acceptance.
