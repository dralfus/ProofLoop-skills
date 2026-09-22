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

**Current local status (2026-09-18):** benign schema-smoke is schema-valid with
the configured `qwen38-flash-next` OpenAI-compatible route. The captured
read-only recon returned exit `53` / `FatalTurnLimitedError` without terminal
`structured_output`; see
`docs/experiments/qwen-assist-ticket-314-captured-recon-2026-09-18.md`.
The repeated root cause is `QWEN_UNUSABLE`, not Ticket 314 acceptance evidence.
- [ ] Процедура явно отделяет успешный bridge-pilot от acceptance ticket 314.
- [ ] Pilot фиксирует baseline, limits, terminal outcome и anonymized metrics.
- [ ] Нет diff ticket 355, записей Qwen или тестовых side effects.

## 5. `QWEN_PATCH_CANDIDATE` с независимым переносом
**Update (2026-09-18, supersedes status above):** Ticket 4 is done. A narrowed
one-file packet returned schema-valid `EVIDENCE_FOUND` in three turns from a
clean isolated worktree at baseline `c7ad67ce9bcfa21526d56b9a7eca5f3b82ca673a`.
Codex independently confirmed three locatable facts, empty `writes` and no
worktree diff; the local metric contains only approved aggregate fields. This
is bridge evidence, not Ticket 314 acceptance evidence.

**Update for Ticket 5:** partial. Qwen produced an independently verified
2-file/8-line candidate, but both write runs ended exit `53` without terminal
patch manifest; the write-output branch remains `QWEN_UNUSABLE` and stops same-root retries.

**Update (2026-09-19):** A new minimal, isolated manifest smoke narrowed the
failure: schema-valid `plan` recon completed in two turns, while `yolo` applied
exactly one file/11-line test-only change and its targeted test passed, but
again ended at the 12-turn limit with no terminal manifest. Thus the remaining
blocker is the Qwen `yolo` structured-output completion path, not Ticket 314
scope, authentication, capture transport, or an inability to write the patch.
See `docs/experiments/qwen-assist-manifest-smoke-2026-09-19.md`.

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

**Review finding:** channel taxonomy должна принимать `noninteractive`, `privileged`, `external` и project-defined values; side-effect policy обязана согласовываться с наблюдаемым поведением.

**Blocked by:** 6. Разрешённый диагностический цикл.

**Status:** corrected after review, local validation complete

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

**Review finding:** production contract должен фиксировать input/output states, а не только строковые transitions.

**Blocked by:** 6. Разрешённый диагностический цикл.

**Status:** corrected after review, local validation complete

- [x] Production semantic delta не может быть описан как test-only patch.
- [x] Для каждого изменённого контракта фиксируются owner, transitions и consumer evidence.
- [x] Отсутствие regression или consumer evidence блокирует full/release verification.
- [x] Gate не расширяет acceptance surface без явного решения и доказательства.

## 12. Raw-free PASS projection и identity evidence

**Что реализовать:** Aggregate acceptance публикует безопасный машиночитаемый projection не только при REJECTED, но и при PASS, связывая результат с текущим кандидатом и execution channel.

**Review finding:** raw-free проверка должна рекурсивно запрещать sensitive fields во всех вложенных объектах.

**Blocked by:** 9. Execution channels и классификация тестов; 10. Receipts выбора и исполнения тестов.

**Status:** corrected after review, local validation complete

- [x] PASS projection содержит criterion/scenario counts, required controls, cleanup/evidence status, identity и artifact reference.
- [x] REJECTED сохраняет совместимый raw-free failure projection.
- [x] Projection не содержит prompt, secret, customer data, raw command output или exception text.
- [x] Verifier может установить достаточность PASS без ручного чтения assertion source.

## 13. Модульный protocol и сценарийные fixtures

**Что реализовать:** finish-ticket поставляет короткий основной lifecycle и условно загружаемые runtime, diagnostic и resume ветви; behaviour fixtures подтверждают совместную работу новых gates и отсутствие ложного DONE.

**Review finding:** scenario fixtures должны композиционно запускать gates и доказывать отсутствие ложного `DONE`, а не отображать имя события в status.

**Blocked by:** 6. Разрешённый диагностический цикл; 7. Информативный диагностический seam; 8. Review подготовленного кандидата и validity evidence; 9. Execution channels и классификация тестов; 10. Receipts выбора и исполнения тестов; 11. Semantic diff gate production-контрактов; 12. Raw-free PASS projection и identity evidence.

**Status:** corrected after review, local validation complete

- [x] Основной lifecycle не требует загрузки runtime-specific и diagnostic деталей до выбора соответствующей ветви.
- [x] NOT_AVAILABLE usage сохраняет честную метрику, но не блокирует работу; недоступная critical model не разрешает молчаливый downgrade.
- [x] Версия protocol синхронизирована между canonical source, plugin, human docs и receipts.
- [x] Scenario fixtures покрывают следующий defect, infrastructure failure, повтор без нового evidence, resume permit, document-only change и новое security requirement.

## 14. Luna-first routing с доказуемой эскалацией

**Что реализовать:** Обычная локальная задача начинает с `efficient/high`; tier
повышается только по raw-free evidence недостаточности efficient-tier. Новый
дешёвый repair не должен превращаться в бесконечный loop или ослаблять
independent acceptance.

**Blocked by:** None.

**Status:** implemented, local validation complete.

- [x] Canonical lifecycle определяет initial Luna-pass, один repair ordinary и
  второй только для mechanical low-risk ticket.
- [x] `EFFICIENT_TIER_DEFICIENCY` фиксирует RED, fingerprint, scope, причину и
  следующий closure до перехода на `standard/high`.
- [x] Critical/resumed/security/native/concurrency ticket исключены из
  дополнительного Luna repair; Reviewer остаётся independent standard tier.
- [x] Plugin manifest, Qwen extension, validator и человеческие документы
  синхронизированы с версией 1.14.
- [x] Review P1 исправлен: ordinary Controller routing выбирает `efficient/medium`
  и защищён executable profile fixture.

## Update: Ticket 5 QWEN_PATCH_SEAL

D027 добавляет одноразовый read-only `plan` seal после наблюдаемого unsealed
`yolo` diff с `STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT`. Только exact manifest
Qwen, совпадающий с `PATCH_SEAL_RECEIPT`, создаёт `SEALED_CANDIDATE`; нет
retry, transfer или acceptance без независимого review.

## Update: Ticket 5 runtime seal evidence (2026-09-19)

The isolated `QWEN_PATCH_SEAL` smoke reached a schema-valid receipt after a
bounded unsealed yolo diff and green targeted test, but its one read-only
`plan` seal call ended at turn limit without a terminal manifest. No
`SEALED_CANDIDATE` or transfer was created; this is terminal `QWEN_UNUSABLE`
for the seal output contract. See
`docs/experiments/qwen-assist-patch-seal-smoke-2026-09-19.md`.

## Update: collector-repaired manifest-only seal (2026-09-22)

Collector normalizes singleton/array terminal JSON, rejects non-success final
events and classifies empty stdout as `MISSING_TERMINAL_PATCH_MANIFEST`.
Disposable candidate `qwen-patch-ticket-314` retained one test-only file with
17 added lines and a green focused test. One changed-scope seal launch
(`2 turns / 0 tools / 90s / depth1`) ended `QWEN_UNUSABLE` with raw-free
`exit_code=53`, `stdout_present=false`, `stderr_present=true` and no terminal
manifest. No retry, transfer or acceptance followed; see
`docs/experiments/qwen-manifest-only-collector-failure-2026-09-22.md`.

Follow-up diagnostics used fresh bounded packets `4/0/180s`, `4/1/180s` with
explicit `structured_output`, and `12/1/300s`; all ended without a terminal
patch manifest (`structured_output_missing` or `FatalTurnLimitedError`). This
is now classified as an external Qwen CLI/provider limitation. E2E
`SEALED_CANDIDATE` remains NOT PROVEN; no further blind retry was made.

## 15. Условный `MINIMAL_SOLUTION_CHECK` для ordinary non-Qwen ticket

**Status:** implemented, local validation pending.

- [x] Check использует существующий packet и Reviewer без новой роли или команды.
- [x] Qwen и тяжёлые ticket исключены; acceptance authority не ослаблена.
- [x] Pilot измеряет diff, launches, repair/context, usage, scope drift и outcome.

## 16. Guarded launcher native Qwen Code

**Что реализовать:** Оператор запускает native Qwen `$finish-ticket` через
отдельный ProofLoop-owned launcher, который проверяет допустимую local
configuration и extension, передаёт outer runtime limits и создаёт raw-free
receipt без изменения пользовательских настроек или чужих runners.

**Blocked by:** None — can start immediately.

**Status:** implemented, local validation complete.

- [x] Launcher блокирует safe-mode, disabled loop detection, nesting глубже
  одного уровня и отсутствующий ProofLoop extension до ticket work.
- [x] Launcher не выводит secret и не изменяет `qwen.cmd`, user settings,
  endpoint, model или API key.
- [x] Launcher создаёт локальный raw-free `QWEN_SESSION_GUARD` receipt с
  launch identity, mode и effective limits.

## 17. Lifecycle gate и terminal stop guarded Qwen session

**Что реализовать:** Native Qwen Controller запускает role-agent только при
fresh compatible `QWEN_SESSION_GUARD` и останавливает exhausted или повторный
runtime loop без автоматического continuation.

**Blocked by:** 16. Guarded launcher native Qwen Code.

**Status:** implemented, local validation complete.

- [x] Missing, stale или несовместимый receipt возвращает
  `BLOCKED_CAPABILITY` до role dispatch.
- [x] Budget exhaustion, loop detection или повтор tool fingerprint дают
  `QWEN_RUNTIME_GUARD_STOP` без нового role launch.
- [x] Fresh continuation требует нового reproducible evidence и сохраняет
  append-only QWEN ledger с immutable anchor/hash chain; acceptance authority не
  меняется.

## 18. Режимы Qwen и controlled pilot guard

**Что реализовать:** Оператор получает документированные режимы `recon` и
`protocol`, а workflow — fixtures и малый pilot, проверяющие guard без
неподтверждённых заявлений об улучшении Qwen.

**Blocked by:** 16. Guarded launcher native Qwen Code; 17. Lifecycle gate и terminal stop guarded Qwen session.

**Status:** ready-for-agent.

- [ ] `recon` использует малый budget без thinking; `protocol` включает
  thinking и output limit не меньше 8000, не задавая sampling defaults.
- [ ] Packet подаётся по-английски с требованием русского ответа; model name
  не становится version allow-list.
- [ ] Fixtures и pilot публикуют raw-free guard outcome, terminal reason,
  duration, mode и доступные turn/tool counters.

## 19. Capability-based Qwen launcher compatibility

**Что реализовать:** Убрать exact-version gate из launcher capability path
Ticket 16 и принимать установленный Qwen по наблюдаемым обязательным CLI
capabilities и canonical argv compatibility. Добавить bounded read-only smoke
для установленного Qwen 0.24.0 без role dispatch и acceptance.

**Blocked by:** 16. Guarded launcher native Qwen Code.

**Status:** implemented, local validation complete.

- [x] Launcher проверяет required CLI capabilities и compatibility contract,
  не используя version string как allow-list.
- [x] Все security gates Ticket 16 сохранены: safe-mode, loop detection,
  max depth, extension, raw-free receipt и запрет mutations.
- [x] Smoke выполняет только `qwen --version` и `qwen --help`, публикует
  raw-free version/capability evidence и не запускает Implementer или acceptance.

## 20. Native read-only Qwen recon mode

**Что реализовать:** Добавить в guarded native-Qwen launcher отдельный explicit
`recon` mode для ограниченного анализа в clean fixed-point worktree. Режим не
является `protocol`, не запускает role-agent или acceptance и не получает
write-capable tool classes.

**Blocked by:** 16. Guarded launcher native Qwen Code; 17. Lifecycle gate и
terminal stop guarded Qwen session.

**Status:** implementation and local validation complete; bounded live recon
proof passed 2026-09-22 after separately diagnosed bridge, prompt-budget and
baseline-identity failures. No protocol/Implementer/acceptance run was made.

- [x] `recon` использует `qwen.cmd`, `--bare`, fixed read-only prompt,
  `--approval-mode plan`, clean worktree и bounded turns/tool-calls/wall-time.
- [x] JSON/schema output валидируется до `QWEN_RECON_READY`; malformed,
  write/implementation/subagent/acceptance output становится terminal
  `QWEN_UNUSABLE`.
- [x] `protocol` exact argv contract не изменён; safe-mode, loop detection,
  extension, max-depth и raw-free receipt gates сохранены.
- [x] Recon receipt и append-only lifecycle policy fail closed на budget,
  loop/fingerprint и continuation; role dispatch и acceptance всегда false.
- [x] Focused tests покрывают clean/dirty worktree, command contract,
   structured output, forbidden actions и terminal stops.
- [x] Raw-free evidence captured for the initial worktree/depth failures and
  the later native-abort/prompt-budget/baseline failures; no raw error text or
  secret was published.
- [x] Final live launch `814298d37ba7487c83c3313b72b1f936` reached
  `QWEN_RECON_READY` with `EVIDENCE_FOUND`, exact baseline, schema-valid
  structured output, `writes=false` and all authority markers false.

## 21. Replacement recon lifecycle: fresh-ledger sessions

**Что реализовать:** Заменить recon-specific lifecycle Ticket 20 на модель,
где terminal ledger необратимо закрыт, каждая новая recon session создаёт новый
receipt и пустой genesis ledger, а active старый ledger не может присоединиться
к новому launch. В recon contract не должно быть поля или semantics
`continuation`; protocol contract не меняется.

**Design:**

- `docs/superpowers/specs/2026-09-21-qwen-recon-lifecycle-replacement-design.md`
- `docs/superpowers/plans/2026-09-21-qwen-recon-lifecycle-replacement.md`

**Blocked by:** separate authorization for any live Ticket 18 pilot; no automatic launch.

**Status:** implemented locally; F1 `PASS`; `SPEC: SCOPED_PASS`; NOT DONE; live Qwen/recon/protocol and acceptance NOT_RUN.

- [x] Terminal recon ledger необратимо закрыт и никогда не принимается снова.
- [x] New session требует нового `receipt`, `launch_id`, `session_id`,
  `ledger_id`, genesis `ledger_anchor` и неповторяемый `fresh_evidence_id`.
- [x] Active old ledger не принимается с новым `launch_id`; same-session append
  использует exact receipt identity.
- [x] Recon не содержит `continuation`; protocol continuation остаётся
  неизменным.
- [x] `stop_reason` и `writes` обязательны и schema-equivalent в launcher и
  canonical report schema.
- [x] RED matrix, полный suite, validators, PowerShell parse и independent
  review выполнены; live Qwen/recon/protocol и acceptance не запускались.

F1 closed the two deferred P3 findings: mismatch regressions now assert the
complete blocked decision (`status=BLOCKED_CAPABILITY`, all three authority
markers false, and no ledger append), and duplicate active `launch_id`/
`session_id` checks were removed while preserving reason order.

## 21-F1. Deferred Ticket 21 P3 closure

**Что реализовать:** закрыть только два deferred quality findings Ticket 21;
не начинать live Ticket 18 и не менять recon design.

**Blocked by:** отдельное разрешение на follow-up implementation.

**Status:** PASS; implementation complete; live Qwen/recon/protocol and acceptance NOT_RUN.

- [x] P3-1: для `session_id` и `ledger_id` mismatch regression paths прямо
  проверяются `status=BLOCKED_CAPABILITY`, `role_dispatch=false`,
  `subagent_dispatch=false`, `acceptance=false` и отсутствие нового ledger
  event.
- [x] P3-2: дублированные active `launch_id`/`session_id` checks удалены при
  сохранении reason order, либо добавлены explicit rationale и regression
  evidence, объясняющие их сохранение.
- [x] После закрытия обоих критериев получен fresh independent review; Ticket 18
  live pilot не запускается автоматически.
