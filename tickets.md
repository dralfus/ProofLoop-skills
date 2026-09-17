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
# Tickets: сходимость finish-ticket по урокам Ticket 355

Источник: docs/specs/finish-ticket-ticket-355-convergence.md.

## 6. Разрешённый диагностический цикл

**Что реализовать:** Controller выдаёт ограниченный DIAGNOSTIC_CYCLE_PERMIT, в рамках которого Implementer автономно выполняет несколько информативных экспериментов в утверждённых scope, execution channel и budget.

**Blocked by:** None — can start immediately.

**Status:** implemented, local validation complete.

- [x] Permit фиксирует baseline, scope, channel, budget, время, допустимые изменения, неизменяемые гарантии, semantic identity и stop conditions.
- [x] Результат классифицируется как DIAGNOSTIC_PROGRESS, REPAIR_FAILURE, NEXT_DEFECT или INFRASTRUCTURE_BLOCKER.
- [x] Resume требует полного совпадения permit identity; изменение security, ownership, side-effect semantics, channel, budget, scope, allowed changes или времени требует нового permit.
- [x] Pre-command infrastructure failure не расходует budget; повтор fingerprint и исчерпание budget возвращают DIAGNOSTIC_CONTROL_POINT.
## 7. Информативный диагностический seam

**Что реализовать:** Для каждого диагностируемого acceptance criterion Controller заранее фиксирует, какие конкурирующие причины различает результат целевой команды, и использует append-only hypothesis ledger только при появлении новой информации.

**Blocked by:** 6. Разрешённый диагностический цикл.

**Status:** implemented, local validation complete.

- [x] SEAM_FEASIBILITY содержит минимальный raw-free контракт различения причин отказа.
- [x] Для многостадийной операции evidence сохраняет первую failed stage и закрытый reason code; для comparison — обе стороны до assertion.
- [x] Две попытки без нового различающего evidence требуют control point.
- [x] Новая локализация того же symptom не ошибочно становится DESIGN_GAP или повторной root cause.
## 8. Review подготовленного кандидата и validity evidence

**Что реализовать:** Implementer собирает диагностические RED/GREEN внутри разрешённого цикла, затем независимый Reviewer оценивает подготовленный candidate и затронутые инварианты. Надёжное evidence повторно используется только при неизменных значимых зависимостях.

**Blocked by:** 6. Разрешённый диагностический цикл; 7. Информативный диагностический seam.

**Status:** implemented, local validation complete

- [x] Диагностический evidence не требует предварительного static PASS.
- [x] Reviewer получает candidate delta, связанные criteria и изменённые инварианты, не повторяя неизменившиеся проверки автоматически.
- [x] Receipt хранит candidate, тест, build/execution configuration, required environment, команду, executed set и результат.
- [x] Изменение значимой зависимости делает receipt непригодным для переиспользования.

## 9. Execution channels и классификация тестов

**Что реализовать:** Каждый execution path ticket получает универсальную характеристику channel, а tests, запускающие side-effectful или interactive path, явно классифицируются по наблюдаемому поведению.

**Blocked by:** 6. Разрешённый диагностический цикл.

**Status:** implemented, local validation complete

- [x] Execution receipt объявляет один channel для каждого вида evidence.
- [x] Channel определяет policy side effects, timeout, identity receipt и допустимый scope без платформенных специальных случаев.
- [x] Static contract обнаруживает транзитивный вызов неподходящего channel в изолированном suite.
- [x] Environment failure до целевой команды получает INFRASTRUCTURE_BLOCKER, а не product verdict.

## 10. Receipts выбора и исполнения тестов

**Что реализовать:** Controller получает отдельные доказательства discovery и фактического execution test cases, поэтому parameterization и ограничения adapter не маскируются под успешную или неуспешную проверку.

**Blocked by:** 9. Execution channels и классификация тестов.

**Status:** implemented, local validation complete

- [x] DISCOVERY_RECEIPT хранит найденные cases и критерий выбора.
- [x] EXECUTION_RECEIPT хранит реально executed cases, counts, command и result.
- [x] Расхождение receipts формирует честный status неполноты evidence.
- [x] Controller выбирает другой evidence seam либо блокирует ticket, не создавая retry loop на основании одного exit code.

## 11. Semantic diff gate production-контрактов

**Что реализовать:** Перед дорогой verification Controller выявляет каждый изменённый production contract и требует доказать его owner, допустимые и запрещённые transitions, production consumer и regression.

**Blocked by:** 6. Разрешённый диагностический цикл.

**Status:** implemented, local validation complete

- [x] Production semantic delta не может быть описан как test-only patch.
- [x] Для каждого изменённого контракта фиксируются owner, transitions и consumer evidence.
- [x] Отсутствие regression или consumer evidence блокирует full/release verification.
- [x] Gate не расширяет acceptance surface без явного решения и доказательства.

## 12. Raw-free PASS projection и identity evidence

**Что реализовать:** Aggregate acceptance публикует безопасный машиночитаемый projection не только при REJECTED, но и при PASS, связывая результат с текущим кандидатом и execution channel.

**Blocked by:** 9. Execution channels и классификация тестов; 10. Receipts выбора и исполнения тестов.

**Status:** ready-for-agent

- [ ] PASS projection содержит criterion/scenario counts, required controls, cleanup/evidence status, identity и artifact reference.
- [ ] REJECTED сохраняет совместимый raw-free failure projection.
- [ ] Projection не содержит prompt, secret, customer data, raw command output или exception text.
- [ ] Verifier может установить достаточность PASS без ручного чтения assertion source.

## 13. Модульный protocol и сценарийные fixtures

**Что реализовать:** finish-ticket поставляет короткий основной lifecycle и условно загружаемые runtime, diagnostic и resume ветви; behaviour fixtures подтверждают совместную работу новых gates и отсутствие ложного DONE.

**Blocked by:** 6. Разрешённый диагностический цикл; 7. Информативный диагностический seam; 8. Review подготовленного кандидата и validity evidence; 9. Execution channels и классификация тестов; 10. Receipts выбора и исполнения тестов; 11. Semantic diff gate production-контрактов; 12. Raw-free PASS projection и identity evidence.

**Status:** ready-for-agent

- [ ] Основной lifecycle не требует загрузки runtime-specific и diagnostic деталей до выбора соответствующей ветви.
- [ ] NOT_AVAILABLE usage сохраняет честную метрику, но не блокирует работу; недоступная critical model не разрешает молчаливый downgrade.
- [ ] Версия protocol синхронизирована между canonical source, plugin, human docs и receipts.
- [ ] Scenario fixtures покрывают следующий defect, infrastructure failure, повтор без нового evidence, resume permit, document-only change и новое security requirement.
