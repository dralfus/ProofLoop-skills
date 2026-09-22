# Текущее состояние

## Существующий workflow

1. Требования уточняются с mattpocock/skills.
2. Создаются спецификация и tickets.
3. Implementer реализует один ticket и пишет тесты.
4. Независимые роли проверяют спецификацию, код и исполняемое evidence.
5. Только Controller присваивает итоговый статус.

## Наблюдаемый failure mode 1: ложное завершение

Implementation-агенты сообщали о завершении при:

- пропущенных требованиях;
- преждевременно закрытых checkbox;
- placeholders и stubs;
- реализации только части поведения;
- зелёных тестах, не доказывающих полную спецификацию.

Разделение реализации и приёмки предотвращает такое `DONE`.

## Наблюдаемый failure mode 2: нездоровый repair-loop

Реальный критичный pilot показал другой отказ:

- сложная security/concurrency/OS задача была первоначально маршрутизирована на
  Terra, а Sol подключён только после нескольких исправлений;
- один production-seam finding повторялся в нескольких раундах;
- Reviewer создавал собственных review-subagents;
- полный test suite запускался до окончательного статического PASS;
- новые timeout/cancellation semantics формировались внутри implementation-
  цикла, хотя должны были быть отдельным design-решением;
- partial diff после usage limit требовал повторного чтения и анализа.

Независимая проверка сохранила безопасность и не допустила ложного `DONE`, но
процесс оказался неэффективным по токенам и времени.

## Уточнённая гипотеза

Надёжный workflow требует одновременно:

- независимой acceptance authority;
- единоличной spawn authority у Controller;
- risk-first выбора модели;
- статического review до Verifier/full suite;
- adjudication новых требований;
- ранней остановки повторяющейся корневой причины;
- отдельного статуса `BLOCKED_FOR_DESIGN`.

Пилот, завершённый после нескольких дорогих итераций, добавил новый наблюдаемый
failure: формально безопасные health gates не ограничивали
число role-agent запусков, повторное чтение контекста и эскалацию на Sol.
Значительная часть расхода пришлась на контекст Controller и повторные
проверки, поэтому дорогая модель сама по себе не является объяснением.

Пять fix-раундов остаются абсолютным пределом, но не являются штатной целью.

## Наблюдаемый failure mode 3: реализация до доказуемого seam

Критичный ticket не должен начинать implementation, пока для каждого acceptance
criterion не определены production owner, test seam и red-capable команда.
Иначе работа превращается в архитектурное исследование уже после дорогого
запуска. Gate должен возвращать `BLOCKED_FOR_DESIGN` до Implementer.

## Наблюдаемый failure mode 4: fake seam без production consumer evidence

Зелёная матрица через test double не доказывает совместимость изменённой
boundary с production-shaped consumer. Для такой boundary до implementation
нужны consumer и compatibility command; при `REJECTED` Controller группирует
подтверждённую primary cause и её cascade failures.

## Наблюдаемый failure mode 5: частичная приёмка и непроверенный runner

`SCOPED_PASS` частичного repair не является приёмкой ticket. Незакрытый
acceptance ledger запрещает Verifier и full suite. Внешний runner без
технического enforcement может создавать лишние jobs, поэтому не получает
доступ к очереди и его результат всегда перепроверяется Controller.

## Наблюдаемый failure mode 6: дорогой и многословный control loop

Полный preflight необходим Controller, но его подробная печать и повторное
чтение старого контекста расходуют tokens без нового решения. Пользователь
получает короткий decision receipt, а resume идёт через компактный checkpoint
и fresh Controller.

## Наблюдаемый failure mode 7: неподтверждённая переносимость runtime

Нельзя переносить профиль ролей, модели и tools между runtimes по имени модели.
Без точной capability declaration, независимого Reviewer и executable
verification workflow возвращает `BLOCKED_CAPABILITY` до первого spawn.

## Наблюдаемый failure mode 8: repair без доказуемой сходимости

Если runtime допускает несколько локальных исправлений одной model identity,
прогресс должен подтверждаться append-only ledger, воспроизводимым `RED` и
fresh review. Повтор root cause, regression, `NEW_REQUIREMENT`, `DESIGN_GAP`
или неутверждённое расширение scope останавливают automatic continuation.

## Наблюдаемый failure mode 9: непрозрачный aggregate reject

Aggregate acceptance может честно вернуть `REJECTED`, но один assertion вида
`report.Passed == false` не позволяет установить primary failure, cascade или
in-scope verdict. Новый repair в этой точке стал бы догадкой и мог бы запустить
дорогой цикл без feedback signal.

Версия `1.14` требует raw-free `FAILURE_PROJECTION` и разрешает ровно один
test-only diagnostic loop без нового role-agent launch. Если projection не
получена повторно, ticket блокируется как `DIAGNOSTIC_EVIDENCE_INCOMPLETE`.

## Наблюдаемый failure mode 10: дешёвый worker повторяет невалидную работу

Qwen полезна как дополнительный compute, но не доказала соблюдение role
protocol: она может расширять scope, запускать лишние jobs и повторять попытки
без новой диагностической информации. Поэтому `QWEN_ASSIST` не получает роль
или acceptance authority. Она ограничена schema-first read-only recon в чистой
worktree, затем малым candidate по отдельному решению Controller; health gate
останавливает повтор root cause, две непрогрессивные попытки или седьмой вызов.

## Наблюдаемый failure mode 11: преждевременная дорогая эскалация

Даже при здоровых acceptance gates ordinary ticket мог начинаться на standard
или быстро переходить на более дорогую модель без доказательства, что
efficient-tier локальный loop исчерпан. Это увеличивает token usage, но не
даёт нового evidence. Ответ — Luna-first routing для ограниченной реализации,
а не ослабление review или увеличение бесконечного repair-loop.

Эскалация на standard допускается только после raw-free
`EFFICIENT_TIER_DEFICIENCY`. Обычный ticket получает initial Luna-pass и один
scoped repair; mechanical low-risk — не более двух repair при новой
локализации. Critical ticket не является частью этого дешёвого маршрута.

## Текущая цель

Проверить глобальный plugin и протокол версии `1.14` на следующих десяти ordinary
ticket без копирования workflow-файлов в проект. До первого spawn подтвердить
runtime capability declaration и `BLOCKED_CAPABILITY` при её отсутствии, затем
измерить:

- число role-agent запусков;
- число fix-раундов;
- повторение корневых причин;
- рост diff относительно preflight;
- число full-suite запусков;
- фактическое число role-agent запусков против preflight-бюджета;
- модель/effort каждого запуска, compaction и повторное использование
  контекста;
- итоговый статус и качество evidence.
- долю reject с установленной primary failure и число diagnostic permits.

Дополнительно проверить, что `SCOPED_PASS` не создаёт Verifier, rejected job
не создаёт новую роль, а внешний runner не может поставить непредусмотренный
Sandbox job.

Версия `1.2` устранила failure mode: ручное распространение
нескольких файлов и большой стартовый prompt создают дублирование, drift и
лишний контекст. Исполняемый протокол теперь поставляется одним глобальным
skill.

## Наблюдаемый failure mode 12: избыточное решение ordinary ticket

У ordinary ticket новый helper, abstraction или dependency могут заменять уже доступное решение. Постоянный minimalism prompt для всех ролей способен увеличить reasoning usage, поэтому применяется только измеряемый `MINIMAL_SOLUTION_CHECK` внутри existing packet.

## Наблюдаемый failure mode 13: native Qwen запускается без внешнего session guard

Server-side sampling defaults устраняют языковые артефакты, но не доказывают,
что native Qwen применит required skill или прекратит повторные tool calls.
Текущий `QWEN_CONVERGENT` ledger останавливает non-progress между
repair-candidates, но не ограничивает сам процесс Qwen до watchdog. Ticket 16
ввёл отдельный ProofLoop-owned guarded launcher, raw-free receipt и технические
limits; Ticket 19 заменил version pin launcher capability path на capability и
CLI compatibility checks. Ticket 17 добавил pure raw-free lifecycle gate для
fresh receipt, terminal budget/loop/fingerprint stop и append-only continuation
evidence; он не запускает role-agent или acceptance. Режимы Ticket 18 остаются
отдельной незапущенной задачей; live role/acceptance evidence нет.
Административная замена Qwen model считается runtime drift и prerequisite для
Ticket 18. Для controlled fixture owner-authorized declaration фиксирует
`configured_model_id: qwen38-flash-next`, source
`USER_AUTHORIZED_CONFIGURATION`; server-side active identity остаётся
неattested limitation. Текущие Ticket 17 gates не ослабляются.

## Наблюдаемый failure mode 14: recon не имел отдельной executable boundary

Design-only разбор Ticket 20 установил, что guarded launcher принимал только
`protocol`: его `ValidateSet`, child CLI contract и fixed `/finish-ticket`
prompt не позволяли безопасно выразить read-only recon. Простое снятие
ограничения расширило бы authority без доказуемых write/subagent/structured
output gates. Ticket 20 добавляет отдельный native `recon` contract с clean
fixed-point worktree, `--bare`, plan-mode tool exclusions, bounded limits,
schema-validated JSON, raw-free `QWEN_RECON_GUARD` и terminal stops; existing
protocol remains exact. Recon result is never role or acceptance evidence.

## Статус Ticket 21

Ticket 21 реализован локально, F1 follow-up получил `PASS`, а fresh review
не нашёл P0–P3 в F1 scope. Ticket сохраняет `SPEC: SCOPED_PASS` и не является
`DONE`: protocol и acceptance live не запускались. F1-1 закрепляет
полный blocked-contract regression для `session_id`/`ledger_id` mismatch:
`status=BLOCKED_CAPABILITY`, три authority markers false и отсутствие ledger
append. F1-2 удаляет дублированные active `launch_id`/`session_id` checks с
сохранением reason order.

2026-09-22 диагностика live recon завершена. Первые bounded прогоны выявили
три отдельные причины: native exit `-1073740791` после валидного terminal
result, перегруженный prompt с исчерпанием Qwen turn/tool budget и отсутствие
явного fixed-point в prompt (`BASELINE_MISMATCH`). Bridge теперь принимает
только allowlisted native exit вместе с schema-valid success result; prompt
сведён к одной read-only инспекции и одному structured output; parent передаёт
и повторно проверяет baseline.

Новый bounded live launch
`814298d37ba7487c83c3313b72b1f936` завершился `QWEN_RECON_READY` с
`EVIDENCE_FOUND`, `structured_output_valid=true`, `writes=false`,
`role_dispatch=false`, `subagent_dispatch=false`, `acceptance=false`; budget
`3/6/5m/depth1`, clean fixed point
`335ba1dc0364e7bb9ac0413925e1a1e8440cb760`. Это доказательство native
read-only recon path, но не Implementer и не acceptance evidence. Текущий
рабочий diff остаётся без commit.

2026-09-22 manifest-only seal после bounded test-only candidate также получил
terminal outcome без retry. Collector исправлен для singleton/array terminal
JSON, singleton `.Count` и пустого stdout; launch
`7dd8ce112bcc4b909393af741c49e8ad` имел budget `2/0/90s/depth1`, но вернул
`exit_code=53`, `stdout_present=false`, `stderr_present=true`,
`structured_result=false`. Исправленный collector классифицировал это как
`QWEN_UNUSABLE / MISSING_TERMINAL_PATCH_MANIFEST`; `SEALED_CANDIDATE` не
создан. Изменённая allowlist-причина `COLLECTOR_PROJECTION_FAILED` не
подменяет фактический terminal outcome Qwen и не даёт transfer или acceptance.

После диагностики выполнены ещё три fresh bounded packet с изменённым scope:
`4/0/180s` дал structured JSON error envelope,
`4/1/180s` с explicit `structured_output` дал тот же structured-output
failure, а `12/1/300s` снова завершился `FatalTurnLimitedError` с пустым
stdout. Auth/transport не были причиной. Поэтому E2E `SEALED_CANDIDATE` не
доказан; дальнейший blind retry остановлен как внешний Qwen CLI/provider
limitation. Collector и локальные gates исправлены и проверены.
