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
evidence; он не запускает role-agent или acceptance. Ticket 18 локально
реализует режимные contracts и raw-free pilot fields. По пересмотренному
решению D046 `recon` сохраняет configured thinking, ограничиваясь малым
runtime budget; implementation follow-up удалил obsolete `--no-thinking` gate
из mode/argv/launcher contract и усилил инструкции Qwen по обязательному
следованию установленному `/finish-ticket` skill. Capability smoke прошёл на
Qwen 0.24.4; bounded pilot `3/6/5m/depth1` завершился `QWEN_RECON_READY` на
clean baseline `335ba1dc0364e7bb9ac0413925e1a1e8440cb760`, с валидным
structured output, `writes=false` и всеми dispatch/acceptance flags `false`.
Последующий bounded native protocol attempt Ticket 18 завершился
`QWEN_COMMAND_FAILED` после `33,279 ms`; counters не были доступны,
`session_ended=false`, `loop_status=UNOBSERVED`, `budget_stop=false`. Попытка не
доказала успешный protocol E2E; повторного Qwen запуска не выполнялось.
Role/acceptance evidence остаются отдельными незавершёнными gates.
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

## Ticket 22: progress-gated Qwen continuation policy

Ticket 22 runtime policy и Ticket 23 native checkpoint adapter локально
реализованы. Host adapter пересчитывает task/scope/baseline/diff, проверяет
append-only progress ledger и typed test/review receipt binding, затем вызывает
runtime policy до dispatch. Fake launcher доказывает fail-closed dispatch gate;
checkpoint/progress identities блокируют replay. Session ceilings
`20/20/30m/depth1`, configured reasoning, Qwen settings/provider/sampling и
внешние файлы не меняются.

Прежняя native-only projection не могла доказать host budget stop или loop-clear.
После принятия D051 protocol launcher использует host-owned terminal receipt:
supervisor владеет child process tree, обрабатывает только полные записи
`--json-file` sidecar и удаляет transcript после raw-free projection.
Continuation требует `HOST_WALL_LIMIT` или `HOST_TOOL_LIMIT`,
`event_coverage=COMPLETE`, post-stop `session_end`, закрытый process tree,
checkpoint и `HOST_CLEAR` от `exact_tool_interaction_cycle_v1`. Локальные fake
fixtures не являются live Qwen proof; Ticket 24 остаётся `BLOCKED_EVIDENCE_SOURCE` /
`NOT_RUN` до отдельной проверки native process/event совместимости.

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
read-only recon path, но не Implementer и не acceptance evidence. На момент
записи этот результат ещё находился в незакоммиченном рабочем diff; позднее
изменения Qwen seal были зафиксированы в `b767ec3`.

2026-09-22 manifest-only seal после bounded test-only candidate также получил
terminal outcome без retry. Collector исправлен для singleton/array terminal
JSON, singleton `.Count` и пустого stdout; launch
`7dd8ce112bcc4b909393af741c49e8ad` имел budget `2/0/90s/depth1`, но вернул
`exit_code=53`, `stdout_present=false`, `stderr_present=true`,
`structured_result=false`. Исправленный collector классифицировал это как
`QWEN_UNUSABLE / MISSING_TERMINAL_PATCH_MANIFEST`; `SEALED_CANDIDATE` не
создан. Изменённая allowlist-причина `COLLECTOR_PROJECTION_FAILED` не
подменяет фактический terminal outcome Qwen и не даёт transfer или acceptance.

После этой серии диагностика разделила две причины. При простом smoke-schema
Qwen возвращал terminal structured result, а patch-schema исчерпывал turns до
его вызова. Provider-facing patch-schema упрощена до обязательных полей и
базовых JSON-типов; строгие scope/test/Git ограничения по-прежнему проверяет
host-side `qwen_assist.py`. Отдельный launch со старым Qwen worktree slug был
остановлен до model execution из-за уже существующей ветки; существующий
worktree сохранён, для доказательства выбран fresh slug.

Fresh bounded seal `cbffea5e84ed421cb1566e61b7cd4485` (`12/1/300s/depth1`)
вернул через capture reader `SEALED_CANDIDATE`. Это доказывает E2E
manifest-only Qwen seal path; transfer, acceptance и product implementation
не выполнялись. Collector и локальные gates проверены.

2026-09-23 реализован первый архитектурный slice `QwenTerminalProjection`.
Recon CLI, capture reader и assist parser используют общий pure raw-free
projection; terminal extraction принимает только финальный `result`, а
protocol сохраняет silent output contract. Regression/full suite: `138/138`.

2026-09-23 recon contract углублён вторым slice `ReconReportContract`.
`qwen_assist.py` и PowerShell launcher делегируют одной executable проверке
shape/terminal fields/facts/read-only/baseline; JSON Schema остаётся wire
декларацией. Полный suite: `142/142`; PowerShell parser: `ok`. Изменений
Qwen settings/provider/auth или внешнего MCP-конфига нет.

2026-09-23 реализован третий архитектурный slice `QwenGuardPolicy`.
Pure pre-dispatch policy связывает projected settings, capabilities, worktree и
receipt facts; protocol и recon сохраняют разные budgets/authority contracts.
Guarded PowerShell launcher вызывает child Qwen только после
`QWEN_GUARD_READY`; stale receipt, fixed-point drift, unsafe settings и
terminal stop остаются fail-closed.

2026-09-23 Ticket 04 перевёл ключевые Qwen adapter regressions на
production-shaped behavior fixtures. Matrix публично проверяет terminal event,
malformed JSON, baseline mismatch, no-write и credential restore; fake Qwen
используется только локально и не является live/acceptance evidence.

2026-09-23 Ticket 05 добавил `QwenInvocationContract` registry.
Assist, native recon, protocol, seal и capability-smoke adapters получают
mode-specific limits, capability markers, exclusions, authority и argv из
единого pure renderer; contract matrix не запускает Qwen и фиксирует отсутствие
drift между режимами. Protocol compatibility child также сверяет входной argv
с registry, а не с локальной копией лимитов. Полный suite после этого slice:
`154/154`; PowerShell parser и plugin validator: `ok`.

2026-09-24 capability smoke для установленного Qwen `0.24.4` прошёл без
model request: все пять CLI markers (`prompt`, session/tool/wall limits и
subagent depth) присутствуют; role dispatch и acceptance отсутствуют.
Raw-free receipt сохранён в `.scratch/qwen-ticket24-capability-smoke-20260924.json`.

Диагностика protocol launcher обнаружила, что `CredentialTarget` не доходил до
CLI compatibility layer, а Credential Manager key инжектировался только в
`recon`. В protocol child Qwen для OpenAI-compatible auth требовался
`OPENAI_API_KEY`; прежние fixtures проверяли sidecar/budget, но не credential
resolution. Добавлен process-scoped key injection из Windows Credential
Manager с восстановлением environment сразу после Qwen child и в `finally`
при исключениях, forwarding target через оба слоя. Regression обнаружил, что
первоначально key наследовался Python projector-ом; тест был расширен и прошёл
RED→GREEN после очистки environment до projection. Настройки пользователя,
provider, sampling и постоянное environment не менялись. Единственный
bounded native protocol pilot остановился до model dispatch с
`LOCAL_SETTINGS_UNAVAILABLE` (`0/0`, 265ms): `.NET SpecialFolder.UserProfile`
не совпал с `USERPROFILE`, где settings читается успешно. Default исправлен на
`USERPROFILE`; повторной live попытки не было.

Установленная версия Qwen CLI `v0.24.4` подтверждена локальным capability
smoke; upstream contract проверен по tag `v0.24.4`. Native `--json-file` не
даёт typed budget-stop reason или
explicit loop-clear; headless `-p` — другой invocation path, а exit `55`
смешивает wall-time/tool-call budgets. Поэтому Ticket 24 остаётся
`BLOCKED_EVIDENCE_SOURCE`; детали и первичные ссылки — в
`docs/research/qwen-v0244-dual-output-terminal-evidence.md`.

2026-09-25 перепроверены официальные материалы upstream v0.24.5 и текущий
локальный CLI: `qwen.cmd --version` вернул `0.24.4` (exit `0`, без model
request). Новый release и опубликованный Dual Output contract не дают
документированной гарантии typed budget-stop reason либо positive loop-clear.
Поэтому разрешение владельца на bounded launch не снимает prelaunch evidence
gate; модельный pilot не dispatch'ился. Свежая сверка: `docs/research/qwen-v0245-terminal-evidence-refresh-20260925.md`.

После tightening credential lifetime: `python -m unittest discover -s tests`
прошёл `184/184`; plugin validator завершился с exit `0`, PowerShell parse
обоих launcher scripts и `git diff --check` прошли. Остались только ожидаемые
Git warnings о нормализации CRLF/LF. Последующий bounded protocol attempt
`1ccd10aa3b394d62876d567d8e9b01f7` завершился `QWEN_COMMAND_FAILED` за
`33,279 ms`; turns/tools=`NOT_AVAILABLE`, `session_ended=false`,
`loop_status=UNOBSERVED`, `budget_stop=false`, `terminal_stop=null`. Старый
collector не передал Qwen exit code и envelope classification, поэтому
фактическая причина live failure неизвестна. Synthetic regression выявил
дефект collector: adapter code `3` с валидной blocked JSON projection
отбрасывался как unsupported. D050 исправляет эту цепочку и сохраняет только
allowlisted error classification, counters/identities когда доступны и
numeric exit codes. Новый live запуск после исправления не выполнялся; для
него требуется отдельное решение владельца. Ticket 18 live protocol success
не доказан; Ticket 24 остаётся `BLOCKED_EVIDENCE_SOURCE`.

Локальная проверка D050: focused Qwen runtime suites `60/60`, full
`python -m unittest discover -s tests` — `187/187`, plugin validator — exit
`0`, PowerShell AST parser обоих launcher scripts — `PARSE_OK`,
`git diff --check` — без ошибок (только ожидаемые CRLF/LF warnings). Эти
результаты относятся к локальному collector patch; live Qwen не запускался.

2026-09-25 D051 implementation завершена локально. Fake supervisor проверяет
host wall/tool stop, completion race, event cutoff, закрытие process tree,
direct Node запуск распознанного Qwen shim, сохранение argv с кавычками/
метасимволами/newline, неизменность redirected console flags и блокировку
неизвестного .cmd без исполнения. Triple-cycle detector не считает обычные
повторные действия loop: разные result/assistant content и два одинаковых
цикла не дают DETECTED; три соседних одинаковых полных цикла дают только
terminal classification и не останавливают живой процесс.

Дополнительный regression выявил, что внешний launcher выполнял capability
`--help` через неизвестный `.cmd` до supervisor gate. Protocol preflight теперь
использует тот же direct-Node adapter и отклоняет неизвестную обёртку до
исполнения; full-launcher test проверяет `QWEN_CLI_UNAVAILABLE` и отсутствие
marker side effect. Targeted protocol preflight, recognized-shim и
documentation-sync tests прошли 3/3.

Итоговая локальная verification на тот момент: полный test suite 224/224;
focused supervisor rerun 2/2; plugin validator/invocation-contract tests 74/74;
plugin validator exit 0; PowerShell AST parse 3/3; `git diff --check` без
whitespace errors. Тогда Qwen CLI или модель не запускались;
settings/provider/auth не менялись, commit/push не выполнялись.

2026-09-25: один bounded disposable protocol launch Ticket 24 был выполнен и
завершился за 1478 ms со статусом `QWEN_COMMAND_FAILED`; `turn_count` и
`tool_call_count` — `NOT_AVAILABLE`, `session_ended=false`,
`loop_status=UNOBSERVED`, `budget_stop=false`. Typed Qwen/projector exit code,
terminal JSON classification и runtime projection отсутствовали; сохранился
только preflight `QWEN_SESSION_GUARD`. Причина не установлена — данные не
различают child launch, transport/provider failure и отсутствие валидного event
stream. Повторного запуска не было. Collector исправлен так, чтобы сохранять
отдельный versioned raw-free `QWEN_TERMINAL_OUTCOME` даже при недоступном Qwen
runtime projection; synthetic regression подтвердил envelope persistence и
секрет-free классификацию. Ticket 24 остаётся
`BLOCKED_EVIDENCE_SOURCE`; multi-repair continuation остаётся `NOT_RUN` до
отдельного разрешения на новый bounded live gate. Qwen settings/provider/auth и
внешние файлы не менялись.

2026-09-25: после отдельного capability smoke (`0.24.5`, все пять обязательных
маркеров присутствуют) выполнен один bounded disposable protocol pilot на узкой
test-only задаче, связанной с Ticket 314. Terminal outcome: `QWEN_COMMAND_FAILED`
за `1490 ms`; `turn_count` и `tool_call_count` — `NOT_AVAILABLE`,
`session_ended=false`, `budget_stop=false`, `loop_status=UNOBSERVED`. Raw-free
`QWEN_TERMINAL_OUTCOME` сохранён, но typed runtime projection отсутствует;
tracked-файлы disposable checkout не изменены. Причина этого запуска не
установлена; повтор запрещён без нового разрешения. Это не Ticket 314
implementation/acceptance и не evidence для Ticket 24. Рекомендация — сначала
разобрать доступные raw-free child/transport receipts, затем запросить отдельный
bounded запуск только после появления диагностического основания. Qwen settings,
provider, credentials и внешние файлы со стороны Controller не менялись; сами
пользовательские настройки намеренно не инспектировались.

Post-fix local verification: focused Qwen runtime suites `94 passed` plus
`79 subtests`; validator suite `69 passed` plus `19 subtests`; full
`python -m unittest discover -s tests` — `227/227`; plugin validator with
`plugins/agentic-development-workflow` — exit `0`; PowerShell AST parse `3/3`;
`git diff --check` — exit `0` (only line-ending conversion warnings).
