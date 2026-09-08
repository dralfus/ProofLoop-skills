# Tickets: QWEN_ASSIST bridge

Источник: `docs/specs/qwen-assist-bridge.md`.

## 1. Capability-driven Qwen runner

**Что реализовать:** Codex может вызвать Qwen как синхронный внешний worker и
получить schema-valid terminal JSON либо `BLOCKED_CAPABILITY`. Принимаются
обновлённые версии CLI, если в их help доступны обязательные возможности:
non-interactive prompt, JSON schema/output, worktree, limits и read-only mode.
Default-модель используется без fallback.

**Blocked by:** None — can start immediately.

**Status:** done

- [ ] Capability probe не зависит от version string Qwen.
- [ ] Missing capability возвращает `BLOCKED_CAPABILITY` до worker execution.
- [ ] Runner создаёт один bounded non-interactive invocation и валидирует
  terminal JSON.

## 2. Read-only `QWEN_RECON_REPORT`

**Что реализовать:** Controller может передать Qwen read-only packet в clean
fixed-point worktree и получить report с минимум тремя проверяемыми фактами,
state owner, callback boundary и одним acceptance risk. Worker не имеет права
писать файлы, выполнять shell-команды, тесты или создавать subagents.

**Blocked by:** 1. Capability-driven Qwen runner.

**Status:** done

- [ ] Schema принимает только `EVIDENCE_FOUND`, `BLOCKED` или `QWEN_UNUSABLE`.
- [ ] Успех требует полного набора проверяемых полей и отсутствия writes.
- [ ] Невалидный report не становится evidence для Controller.

## 3. Health ledger и обезличенные Qwen-метрики

**Что реализовать:** На ticket ведётся общий bounded ledger Qwen. Он разрешает
до семи вызовов, требует нового evidence для retry и останавливает Qwen после
двух непрогрессивных попыток или повторной root cause. Полный report остаётся
локальным; central JSONL содержит только обезличенные метрики.

**Blocked by:** 2. Read-only `QWEN_RECON_REPORT`.

**Status:** done

- [ ] Лимит в семь распространяется на все режимы Qwen одного ticket.
- [ ] Повтор требует изменённого scope, criterion, RED-command или hypothesis.
- [ ] Central store не получает исходный код, пути или raw findings.

## 4. Read-only live-pilot на ticket 314

**Что реализовать:** Оператор может выполнить один ограниченный read-only
`QWEN_RECON` на ticket 314 из isolated fixed point, исключающего текущий diff
ticket 355. Codex может подтвердить report и сохранить pilot evidence, не
изменяя и не принимая ticket 314.

**Blocked by:** 1. Capability-driven Qwen runner; 2. Read-only
`QWEN_RECON_REPORT`; 3. Health ledger и обезличенные Qwen-метрики.

**Status:** blocked-by-evidence — pilot завершился `QWEN_UNUSABLE`:
`STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT`; см.
`docs/experiments/qwen-assist-ticket-314-pilot.md`.

- [ ] Процедура явно отделяет успешный bridge-pilot от acceptance ticket 314.
- [ ] Pilot фиксирует baseline, limits, terminal outcome и anonymized metrics.
- [ ] Нет diff ticket 355, записей Qwen или тестовых side effects.

## 5. `QWEN_PATCH_CANDIDATE` с независимым переносом

**Что реализовать:** После подтверждённого recon Qwen может создать небольшой
candidate diff в своей worktree. Codex independently проверяет candidate и сам
переносит только одобренное изменение; Qwen не выполняет Git-интеграцию.

**Blocked by:** 4. Read-only live-pilot на ticket 314.

**Status:** implemented, activation blocked by ticket 4.

- [ ] Candidate ограничен двумя файлами, 200 изменёнными строками и одним
  targeted test.
- [ ] Qwen не может commit, merge, cherry-pick, push, full suite или acceptance.
- [ ] Transfer требует independent Codex review и executable evidence.
