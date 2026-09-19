# Решения по workflow

## D001 — Отделить реализацию от приёмки

Статус: принято.

Implementer не определяет, что его работа `DONE`. Требуется независимое review
и исполняемое evidence.

## D002 — Сохранить mattpocock/skills

Статус: принято.

Matt skills остаются механизмом уточнения требований, спецификации и
декомпозиции. Нет evidence, что их полная замена решит наблюдаемые failures.

## D003 — Использовать Superpowers до оценки OpenSpec

Статус: принято.

Superpowers используется для целевого TDD, диагностики и проверки. OpenSpec
отложен до стабилизации implementation-to-acceptance цикла.

## D004 — Ограничить исправительный цикл пятью раундами

Статус: принято и уточнено D005.

Пятый неуспешный fix завершает ticket как `BLOCKED`; автоматического принятия
не происходит.

## D005 — Добавить health gates и единоличную spawn authority

Статус: принято 2026-08-28.

Основание: ранний критичный pilot сохранил безопасность благодаря независимой проверке, но
потребовал нескольких повторных реализаций, вложенных reviewers, повторных
full-suite запусков и архитектурных решений внутри fix-loop.

Решение:

1. Только Controller создаёт subagents.
2. Reviewer выполняет `SPEC` и `CODE_QUALITY` без дочерних agents.
3. Verifier и full suite запускаются только после статического PASS.
4. Повтор одной пары «тип finding + корневая причина» во втором fix переводит
   ticket в `BLOCKED_FOR_DESIGN`.
5. После двух неуспешных fix требуется разрешение пользователя; пять раундов —
   абсолютный предел.
6. `NEW_REQUIREMENT` и `DESIGN_GAP` проходят adjudication до production-кода.
7. Критичные security/concurrency/OS tickets сразу маршрутизируются на Sol
   `high`.
8. Рост file scope более чем вдвое относительно preflight останавливает цикл.

Критерий успеха: на реальном ticket сохраняется независимое acceptance evidence,
но уменьшаются число agent-запусков, повторных findings и full-suite прогонов.

## D006 — Поставлять workflow одним глобальным skill, затем Codex plugin

Статус: принято 2026-08-30.

Наблюдаемый failure: переносимый комплект требовал копировать несколько файлов
в каждый проект, а стартовый Controller prompt повторял большую часть
протокола. Это увеличивало контекст, создавало несколько источников истины и
делало обновление проектов ручным.

Решение:

1. Исполняемый протокол версии `1.2` первоначально хранился в глобально
   устанавливаемом skill `finish-ticket`; с версии `1.3` он поставляется
   внутри Codex plugin `agentic-development-workflow`.
2. Workflow-файлы не копируются в проекты разработки.
3. Skill читает project-specific правила из уже существующего `AGENTS.md`,
   ticket, спецификации и checkpoint.
4. Пользователь запускает Controller коротким prompt с именем skill и ticket.
5. До первого spawn Controller выдаёт `PREFLIGHT_REPORT`; подтверждение нужно
   для critical/resumed/design/unknown-scope cases.
6. Plugin marketplace устанавливает plugin без ZIP, PowerShell installer и
   копирования workflow-файлов в проект.

Критерий успеха: новый ПК требует одной установки skill, новый проект — ноль
workflow-файлов, а старт ticket — одной короткой команды без дублирования
протокола.

## D007 — Ввести бюджетные и контекстные gates

Статус: принято 2026-08-30.

Наблюдаемый failure: ранний критичный pilot завершился локально, но потребовал нескольких запусков
role-agent, 2 context compaction и значительного повторного чтения контекста.
Существующие health gates защищали корректность, но не делали расход до первого
дорогого запуска наблюдаемым и ограниченным.

Решение:

1. `PREFLIGHT_REPORT` содержит численный бюджет запускаемых ролей, Sol,
   full-suite и compaction.
2. Обычный ticket допускает три role-agent запуска (Implementer, Reviewer,
   Verifier), критичный — четыре. Дополнительный запуск требует checkpoint и
   отдельного разрешения пользователя.
3. Terra `high` — default для критичной реализации. Sol `high` допускается
   только при документированном недостатке Terra или design-adjudication; более
   одного Sol на ticket — только с явным разрешением пользователя.
4. Проверяющие роли не получают автоматически Sol: deterministic Verifier
   получает Luna `medium`, интерпретирующий — Terra `medium`; critical review
   — Terra `high`.
5. Full suite запускается не более одного раза и сохраняет команду, время,
   exit code и counts в evidence. Если production diff после него не менялся,
   повтор перед commit не нужен.
6. При compaction перед дорогим spawn Controller фиксирует checkpoint; новый
   Controller заново сверяет бюджет и не наследует неявные предположения.

Критерий успеха: следующий критичный ticket сохраняет независимые review и
verification, но не превышает preflight-бюджет без явного решения пользователя;
в отчёте объяснён каждый дорогой запуск.

## D008 — Проверять feasibility production/test seam до Implementer

Статус: принято 2026-08-31.

Наблюдаемый failure: критичный ticket требовал полного snapshot/restore
external state и детерминированной injected matrix. Доступный production code
сохранял состояние только частично и очищал неподдерживаемые форматы;
при этом исходный preflight не требовал показать owner и test seam для каждого
acceptance criterion. Агент мог потратить implementation-раунд на выяснение
архитектуры вместо ранней остановки.

Решение:

1. В `PREFLIGHT_REPORT` добавить обязательный `SEAM_FEASIBILITY` для каждого
   критерия: production entry point, test seam, red-capable command и owner.
2. Отсутствие любого поля или external state без owner/injected boundary даёт
   `BLOCKED_FOR_DESIGN` до Implementer.
3. Implementer получает один компактный `IMPLEMENTATION_PACKET`, а не
   transcript Controller и полную spec; дополнительное чтение ограничено
   прямыми dependencies указанного entry point.
4. Уточнить accounting critical budget после review failure: re-review и
   Verifier занимают два последних launches, так как до статического PASS
   Verifier не запускался.

Критерий успеха: на следующем critical ticket до первого role-agent для 100%
acceptance criteria есть четыре поля feasibility; если хотя бы одного нет,
зафиксирован `BLOCKED_FOR_DESIGN` с нулём implementation launches. При scoped
fix фактические launches не превышают 4 без явного разрешения.

## D009 — Публиковать observed token usage при closure

Статус: принято 2026-08-31.

Наблюдаемый failure: budget задаёт максимальное число запусков, но после
успешного либо неуспешного ticket пользователь не получает сопоставимой
фактической стоимости реализации. Это не позволяет сравнить experiment с
baseline 353 или заметить, где расходуются tokens.

Решение: Controller после `DONE`, `REJECTED`, `BLOCKED_FOR_DESIGN`, `BLOCKED`
и `BUDGET_GATE` выводит стандартный `TOKEN_USAGE`. Он отделяет Implementer и
его follow-ups от acceptance/control ролей и total ticket, использует только
наблюдаемые provider counters или execution trace и явно маркирует пробелы
как `PARTIAL`/`NOT_AVAILABLE`.

Критерий успеха: каждый следующий закрытый или отклонённый ticket имеет один
отчёт с observed implementation tokens и total ticket либо честный
`NOT_AVAILABLE`; в отчёте нет оценочных чисел.

## D010 — Представлять preflight как компактные таблицы

Статус: принято 2026-08-31.

Наблюдаемый failure: линейный `PREFLIGHT_REPORT` содержит все нужные поля, но
смешивает baseline, acceptance, feasibility и budget в один длинный абзац.
Пользователь не может быстро проверить scope и stop gates до дорогого spawn.

Решение: обязательный preflight рендерится двумя Markdown-таблицами: summary и
одна строка feasibility на criterion. В ячейках используются короткие фразы;
все прежние обязательные поля сохраняются.

Критерий успеха: каждый новый preflight имеет две таблицы, а пользователь может
найти baseline, budget, next action и status каждого criterion без чтения
свободного текста.

## D011 — Проверять production consumer изменённой injectable boundary

Статус: принято 2026-08-31.

Наблюдаемый failure: deterministic matrix прошла через fake boundary, но
production-shaped consumer с реальной boundary завершался ошибкой. Full suite
показал каскад failures, которые являлись следствием
одной primary причины; scoped evidence и Reviewer PASS не доказали consumer
compatibility.

Решение:

1. Если acceptance criterion добавляет или меняет injectable boundary,
   `SEAM_FEASIBILITY` называет production-shaped consumer и запускаемую
   compatibility command.
2. `IMPLEMENTATION_PACKET` передаёт этот consumer Implementer, а Reviewer
   возвращает `FAIL`, если evidence ограничено fake/injected seam.
3. После Verifier `REJECTED` Controller публикует `FAILURE_SUMMARY` с одной
   нормализованной primary cause, только подтверждёнными cascade failures,
   in-scope verdict и одним focused next loop.

Критерий успеха: на следующем ticket с изменённой injectable boundary до
Implementer есть consumer command, а любой full-suite failure отчётно отделяет
одну установленную root cause от каскада и не запускает широкий diagnostic loop.

## D012 — Измерять test suite до его оптимизации

Статус: принято 2026-08-31.

Наблюдаемый риск: большое количество тестов само по себе может ошибочно
восприниматься как дефект. Удаление или quarantine по счётчику способно убрать
security или production-consumer evidence; при этом без duration, flaky history
и карты `test -> risk -> seam` нельзя доказать реальную стоимость или дубли.

Решение: plugin поставляет отдельный manual-only `$audit-test-suite`. Он делает
read-only audit с ограниченным числом запусков, строит evidence map и выдаёт
только proposals с replacement proof. Skill не меняет тесты, CI или quarantine;
изменения выполняются отдельным ticket либо отдельной явно одобренной правкой.

Критерий успеха: audit любого проекта завершается baseline и evidence map, а
каждый `CONSOLIDATE_CANDIDATE` имеет сохранённый риск/seam и проверяемую
replacement command; при отсутствии этого evidence выводится
`NO_CHANGE_RECOMMENDED` или `MEASUREMENT_INCOMPLETE`.

## D013 — Выводить пользователю только preflight decision receipt

Статус: принято 2026-08-31.

Наблюдаемый failure: Controller обязан собирать baseline, scope, acceptance и
feasibility, но печать всех этих данных в каждом первом сообщении создаёт
длинный отчёт, который труднее прочитать и который расходует context/output
tokens без изменения пользовательского решения.

Решение: `PREFLIGHT_REPORT` показывает шесть полей: Ticket/spec, Risk,
Routing, Budget, Stop gates/design gaps и Next action. Полный preflight record,
`SEAM_FEASIBILITY`, targeted commands и scope остаются обязательными внутренними
данными `IMPLEMENTATION_PACKET` и final evidence. При stop gate Controller
добавляет только один blocking detail.

Критерий успеха: следующий preflight даёт пользователю одно короткое решение
без потери обязательных feasibility данных для Implementer, Reviewer и Verifier.

## D014 — Блокировать lifecycle при отсутствии runtime capability

Статус: принято 2026-09-01.

Наблюдаемый failure: lifecycle предполагал возможности Codex неявно. Runtime
без role dispatch, корректной identity модели, tool policy или observed usage
мог перейти к self-review либо silent fallback и выдать evidence, которое не
соответствует фактическому host.

Решение: канонический protocol вводит декларативный runtime adapter contract с
capability preflight. Отсутствующая обязательная capability возвращает
`BLOCKED_CAPABILITY` до первого role-agent launch, без fallback. Codex profile
принимает проверяемый inventory `id/tier/efforts`: resolver выбирает requested
tier и effort, затем при необходимости строго понижает `frontier -> standard
-> efficient` только к совместимому effort. Он сохраняет requested/selected
tier, degraded flag и reason. Неизвестный inventory либо отсутствие совместимой
пары тоже возвращает `BLOCKED_CAPABILITY`; Luna, Terra и Sol остаются примерами
registry, не workflow logic. Численные лимиты сохраняются: role-agent 3/4,
frontier 0/1, full suite 1 и compaction 0/1. CI запускает внешний validator и
executable fixture, которые подтверждают contract установленного plugin.

Для Codex trusted provenance является минимальным exact contract:
`provider: openai` и `source: codex-runtime`. Структурно валидный inventory с
другим или отсутствующим provenance возвращает `BLOCKED_CAPABILITY` до routing.

Критерий успеха: fixture с отсутствующим role dispatch, недоверенным inventory
или несовместимым effort возвращает `BLOCKED_CAPABILITY`; arbitrary inventory
выбирается по tier, а frontier request деградирует к standard с записанной
причиной. Valid plugin подтверждает protocol 1.10; ни один runtime без
обязательной capability не начинает role-agent dispatch.

## D015 — Ввести Qwen Code preflight как contract fixture

Статус: принято 2026-09-01.

Наблюдаемый failure: Codex adaptive profile предполагает inventory, dispatch
и tool policy, которых Qwen Code нельзя считать доступными по имени модели.
Без проверки exact runtime version, одной configured identity и независимого
read-only Reviewer Controller мог бы начать недоказуемый lifecycle или
подменить независимую приёмку self-review.

Решение: protocol и executable validator выбирают Qwen только по trusted
declaration `provider: qwen`, `product: qwen-code`, `version: 0.22.2`.
Preflight требует совпадения configured/active model ID, fresh named subagent,
`role_model_identity_lock` для всех ролей, continuation исходного Implementer,
fresh named Reviewer с `fork: false`,
`write: false` и read-only tools, а также executable verification command.
Отсутствие или нарушение возвращает `BLOCKED_CAPABILITY`. Успех сохраняет
одну identity для всех ролей и `usage: AVAILABLE|NOT_AVAILABLE`.

Boolean capability принимает только literal `true`. Verification command
принимается только как непустая строка либо object
`{"argv": ["<non-empty argument>", "..."]}`; truthy surrogate, пустая
строка, пустой `argv` и лишние fields блокируются как malformed capability.

Минимальное изменение не добавляет Qwen packaging и unlimited convergence
repair-loop: fixture возвращает `repair_policy: NOT_IMPLEMENTED`; эти policy
и delivery остаются отдельными tickets.

Критерий успеха: fixture для Qwen v0.22.2 выбирает single-model profile и
возвращает configuration/usage; fixture с fork/write Reviewer, изменённой
active identity либо отсутствующими dispatch/continuation/verification
capabilities возвращает `BLOCKED_CAPABILITY`. Codex fixture и его numeric
budget остаются без изменений.

## D016 — Сходящийся Qwen repair-loop через append-only ledger

Статус: принято 2026-09-01.

Наблюдаемый failure: D015 доказывает лишь preflight. Если после него снять
numeric fix cap Qwen без external evidence, одна model identity способна
повторять self-repair и принять неподтверждённый progress. Если сохранить
Codex numeric cap, полезный локальный Qwen repair обрывается по счётчику, а не
по состоянию finding.

Решение: Qwen использует `QWEN_CONVERGENT` без числового лимита repair-раундов.
Ledger имеет формальную append-only event-схему: `baseline` содержит fixed point
и open findings; `local_attempt` — finding, reproducible RED, hypothesis и
GREEN; `repair_candidate` — diff/scope, sequence references, normalized root
cause, точно соответствующую referenced attempts, и runtime/model/usage trace;
`review_verdict` — fresh read-only Reviewer,
static verdicts, regression/scope flags и closed findings; `terminal` — status
и reason. Controller валидирует всю историю, а не последнюю запись:
каждый historical `CONTINUE` обязан иметь полный attempt/candidate/review
chain. Closed findings должны быть уникальным подмножеством current open
findings и findings referenced attempts; extra, invented или повторное closure
блокирует progression. Non-`CONTINUE` verdict требует terminal event, а после
terminal события запрещены. Controller продолжает только после закрытия
известного open finding при `SPEC: PASS`, `CODE_QUALITY: PASS`, отсутствии
regression accepted criteria и unapproved scope. Repeated normalized type/root
cause без нового reproducible RED даёт
`BLOCKED`; `NEW_REQUIREMENT`, `DESIGN_GAP` и unapproved scope дают
`BLOCKED_FOR_DESIGN`; regression также запрещает automatic continuation.
Codex budget policy не меняется; Qwen packaging был намеренно отложен до
отдельного delivery решения D017.

Критерий успеха: внешний JSON fixture доказывает `CONTINUE` для независимого
progress, append-only `local_attempt` без изменения ticket status, точные
attempt references candidate и terminal reason. Validator отклоняет
empty/incomplete/invalid-sequence ledger, invented/extra/repeated closure и
historical `CONTINUE` без полного evidence, а также repeated normalized root
cause без RED, regression, новое требование, design gap и scope expansion. В
profile нет numeric repair cap.

## D017 — Поставлять Qwen как native extension без второй lifecycle-копии

Статус: принято 2026-09-02.

Наблюдаемый failure: D015/D016 задавали безопасную Qwen policy, но без
discoverable delivery wrapper Qwen пользователь не мог коротко вызвать тот же
workflow. Копирование protocol в Qwen skill создало бы drift и расходящиеся
acceptance rules.

Решение: корневой `qwen-extension.json` публикует существующий каталог skills
Codex plugin и Qwen-compatible named agent `finish-ticket-controller`. Agent
с `model: inherit` читает единственный canonical lifecycle по пути
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`.
Qwen запускается `/finish-ticket ticket <ID или путь>`; exact capability
preflight и `QWEN_CONVERGENT` сохраняются. Validator проверяет manifest,
skill/agent discovery path, reference на canonical lifecycle и отсутствие
Qwen-копии protocol. Сквозные fixtures отдельно подтверждают неизменный Codex
budget, Qwen preflight, convergence без numeric cap, `BLOCKED_CAPABILITY` и
terminal regression evidence.

Реальный pilot не подменяется fixture: пока `qwen` CLI отсутствует, evidence
artifact содержит `QWEN_CLI=ABSENT` и `NOT_RUN`, а документация описывает
воспроизводимую процедуру будущего запуска.

Критерий успеха: `python scripts/validate_plugin.py --qwen-extension-root .`
и bundled tests проходят; installed extension показывает `finish-ticket` и
`finish-ticket-controller`, а canonical lifecycle существует в одном месте.
## D018 — Закрывать acceptance ledger до verification и изолировать внешние runners

Статус: принято 2026-09-04.

Основание: реальный pilot показал, что `SCOPED_PASS` частичного repair позволил
запустить Verifier при заранее известном незакрытом criterion. Отдельно
неуправляемый внешний runner создал десятки Sandbox jobs и повторные full suite;
текстовые инструкции не являются техническим ограничением side effects.

Решение:

1. Controller ведёт acceptance ledger для каждого criterion: implementation,
   independent review, executable evidence и статус.
2. `SCOPED_PASS` не равен `SPEC: PASS` ticket; при незакрытом ledger Controller
   возвращает `ACCEPTANCE_INCOMPLETE` и не запускает Verifier/full suite.
3. UI/Sandbox job создаёт только Controller через schema-valid `TEST_PERMIT`.
   Отклонение job до целевой команды даёт `JOB_REJECTED` и исправляется одним
   follow-up того же Verifier.
4. Внешний runner без enforcement работает в изолированной worktree без queue
   и full-suite capability; его результат повторно исполняет Controller.
5. Расширение budget требует `NEXT_CLOSURE`; resume после checkpoint или смены
   execution environment создаёт fresh Controller с компактным handoff.

Критерий успеха: на следующем похожем ticket ноль Verifier/full-suite запусков
при незакрытом criterion, ноль новых role-agent после rejected job и ноль
неразрешённых Sandbox jobs от внешнего runner.

## D019 — Диагностировать непрозрачный aggregate reject до repair

Статус: принято 2026-09-08.

Наблюдаемый failure: independent Reviewer мог подтвердить статический diff, а
targeted executable acceptance вернуть только aggregate boolean `false`.
`FAILURE_SUMMARY` тогда честно содержит `UNKNOWN`, но следующий implementation
round не имеет установленной primary cause и превращается в дорогую догадку.

Решение:

1. Aggregate acceptance-test при failure обязан отдавать raw-free
   `FAILURE_PROJECTION`: стабильные scenario/criterion ID, status, terminal
   status, raw-free flag, cleanup, evidence level, build ID и другие уже
   разрешённые поля.
2. Если failure summary остаётся unknown только из-за отсутствующей projection,
   Controller фиксирует `FAILURE_EVIDENCE: INCOMPLETE`.
3. Разрешён один test-only diagnostic loop: follow-up существующего Implementer
   меняет только diagnostic test, а Controller создаёт один schema-valid
   targeted `TEST_PERMIT`. Это не новый role-agent launch и не repair round.
4. До projection не запускаются repair, Verifier, full suite или live evidence.
   Повторная непрозрачность завершается `BLOCKED` с причиной
   `DIAGNOSTIC_EVIDENCE_INCOMPLETE`.

Критерий успеха: на следующем aggregate reject в evidence есть raw-free first
failure projection; до неё не появляется новый role-agent или full-suite job.
Если one diagnostic loop не даёт usable projection, ticket завершён `BLOCKED`,
а не продолжается новой догадкой.

## D020 — Использовать Qwen только как ограниченный внешний assist worker

Статус: принято 2026-09-08.

Наблюдаемый failure: Qwen дешевле Codex, но на реальных задачах нарушала
протокол, запускала лишние jobs и продолжала бесплодные циклы. Полный Qwen
lifecycle с `QWEN_CONVERGENT` не является достаточным основанием передавать
ей роль Implementer или acceptance authority.

Решение: ввести отдельный `QWEN_ASSIST`, запускаемый Controller Codex как
синхронный внешний worker. Каждый вызов проходит capability probe фактического
CLI без version pin; отсутствие non-interactive JSON/schema, worktree,
read-only mode или limits даёт `BLOCKED_CAPABILITY`. Первая операция —
read-only `QWEN_RECON_REPORT` с тремя locatable facts, state owner, callback
boundary и acceptance risk. Patch candidate допустим только после проверки
Codex, в отдельной worktree, максимум два файла/200 строк/один targeted test.
Qwen не выполняет Git-интеграцию, full suite или acceptance.

На ticket действует общий cap семь вызовов. Новый retry обязан менять packet и
добавлять evidence; повтор root cause или две непрогрессивные попытки дают
`QWEN_UNUSABLE`. Полные отчёты остаются локальными вне Git; global JSONL
содержит только обезличенные агрегаты.

Критерий успеха: live read-only pilot возвращает schema-valid report без diff,
shell/test side effects и без загрязнения worktree другого ticket; метрика не
содержит код, пути или raw findings. Только после этого измеряется полезность
малых patch candidates, а не их acceptance.


## D021 — Усилить gates Tickets 9–13 после review

Статус: принято 2026-09-18.

Наблюдаемый failure: первые реализации gates проверяли часть формы receipt, но не все semantics: закрытая taxonomy channel, нерекурсивная raw-free проверка, неполная state evidence и scenario fixtures без композиции gates.

Решение: re-open Tickets 9, 11, 12 и 13. Channel taxonomy становится extensible и согласованной с observed behavior; semantic contracts содержат input/output states; PASS projection рекурсивно исключает запрещённые поля; scenario fixtures проходят реальные policy gates и не могут вернуть DONE. Критерий успеха: каждый прежний bypass имеет RED/Green fixture.

## D022 — Luna-first routing с доказуемой эскалацией

Статус: принято 2026-09-18.

Наблюдаемый failure: ordinary задачи могли получать standard/frontier tier до
того, как ограниченный efficient-tier loop дал доказательство своей
недостаточности. Вместе с повторным чтением context это повышало расход
лимитов, не улучшая acceptance evidence.

Решение: для ordinary локальной реализации Controller запрашивает
`efficient/high` и допускает один scoped Luna repair; у mechanical low-risk
ticket — максимум два repair при новом RED или новой локализации. Переход на
`standard/high` требует `EFFICIENT_TIER_DEFICIENCY` с model identity, RED,
fingerprint, scope, причиной и следующим closure. Reviewer остаётся
independent `standard/medium`; critical/resumed/security/native/concurrency
ticket не используют дополнительный Luna repair. Числовые budget, full suite,
acceptance authority и stop gates не ослабляются.

Критерий успеха: pilot из десяти ordinary ticket показывает меньше
`standard`/`frontier` запусков без роста `REJECTED`, reopen или времени до
первого подтверждённого GREEN. Critical ticket, включая Ticket 355, не входят
в сравнение.

## D023 — Проверять current structured-output contract Qwen до ticket recon

Статус: принято 2026-09-18.

Наблюдаемый failure: Ticket 314 завершился на turn limit без
`structured_output`, а current Qwen Code v0.24.0 документирует
`--output-format json` как event array с terminal `structured_result`. Старый
parser принимал только один JSON object и отверг бы успешный current run как
`INVALID_JSON_OUTPUT`.

Решение: bridge извлекает object только из final `result.structured_result`
event либо legacy single object. До следующего ticket recon Controller запускает
отдельный benign schema-smoke в clean worktree без ticket code; только
schema-valid terminal output разрешает уменьшенный read-only recon. Smoke не
является evidence или acceptance ticket. Критерий успеха: fixture current event
array проходит parser, а live smoke подтверждает terminal schema-valid result
до первого Ticket 314 recon. Launch использует capability-gated `--bare`, но
не `--safe-mode`, чтобы исключить неявные workspace customizations.

## D024 — Хранить Qwen OpenAI-compatible token в Windows Credential Manager

Статус: принято 2026-09-18.

Наблюдаемый failure: headless `--bare` smoke Qwen v0.24.0 не выбрал auth type,
а явный `--auth-type openai` остановился до первого turn, потому что token не
был доступен процессу. Хранение token в project settings, metrics или постоянной
user environment variable расширяет поверхность раскрытия.

Решение: для `--auth-type openai` wrapper читает Generic Credential текущего
Windows-пользователя с target `ProofLoop/Qwen/OpenAI`, передаёт secret только
в `OPENAI_API_KEY` дочернего процесса и в `finally` восстанавливает прежнее
значение или удаляет variable. Критерий успеха: wrapper и native credential
helper проходят static tests и PowerShell parse; следующий live smoke не
получает token в packet, report или metrics.

## D025 — Preserve Qwen terminal output across host transport boundaries

Status: accepted 2026-09-18.

Observed failure: Qwen completed a bounded recon and left a clean worktree,
but the host transport did not retain stdout. Without terminal JSON, Controller
cannot accept a report or retry the ticket pilot by inertia.

Decision: a capture runner starts a hidden child process and writes stdout and
stderr only in `%LOCALAPPDATA%\ProofLoop Skills\qwen-captures`. Its reader
reports `RUNNING`, `COMPLETE`, or `COMPLETE_INVALID_OUTPUT`. Only `COMPLETE`
with a schema-valid final structured result can enter the bridge parser.
Success criterion: an end-to-end benign smoke completes through start/poll/read
without a token in command line, repository, or central metrics.

## D025 — Preserve Qwen terminal output across host transport boundaries

Status: accepted 2026-09-18.

Observed failure: Qwen completed a bounded recon and left a clean worktree,
but the host transport did not retain stdout. Without terminal JSON, Controller
cannot accept a report or retry the ticket pilot by inertia.

Decision: a capture runner starts a hidden child process and writes stdout and
stderr only in `%LOCALAPPDATA%\ProofLoop Skills\qwen-captures`. Its reader
reports `RUNNING`, `COMPLETE`, or `COMPLETE_INVALID_OUTPUT`. Only `COMPLETE`
with a schema-valid final structured result can enter the bridge parser.
Success criterion: an end-to-end benign smoke completes through start/poll/read
without a token in command line, repository, or central metrics.

## D026 — Явно отделить write-candidate Qwen от read-only recon

Статус: принято 2026-09-18.

Наблюдаемый failure: read-only `plan` packet показывает модели edit и shell
tools, хотя policy их отклоняет; для patch candidate отдельный write-mode
нуждается в явном, а не неявном, переходе. Live Ticket 314 также показал, что
Qwen может завершить маленький diff, но исчерпать 12 turns до terminal
`structured_output`; отсутствие manifest не даёт права считать output contract
успешным или повторять тот же packet.

Решение: capture-wrapper получает explicit `ApprovalMode` со значением `plan`
по умолчанию и `yolo` только для already-confirmed recon в isolated worktree.
Read-only invocation явно исключает `Agent`, `edit`, `notebook_edit` и
`run_shell_command`. Write candidate обязан следовать
`qwen-assist-patch.schema.json` (2 files, 200 lines, one targeted test, no Git
or full suite), но Controller independently сверяет настоящий diff и выполняет
test перед переносом. Повторный отсутствующий terminal manifest останавливает
write-output branch как `QWEN_UNUSABLE`.

Критерий успеха: focused tests подтверждают distinct plan/yolo tool lists,
`-SuccessfulRecon` обязателен для `yolo`, schema и validator принимают только
пустой список Git operations; candidate pilot либо возвращает schema-valid

## D027 — Seal Qwen manifest after an unsealed bounded candidate

Статус: принято 2026-09-19.

Наблюдаемый failure: `yolo` может внести ограниченный diff, но завершиться на
turn limit без `structured_output`; повтор того же write packet запрещён health
gate. Увеличение лимита не делает terminal manifest детерминированным.

Решение: после exact `STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT` Controller может
один раз создать raw-free `PATCH_SEAL_RECEIPT` из observed scope и green
targeted test и вызвать Qwen в read-only `plan` как `QWEN_PATCH_SEAL`. Только
точно совпадающий Qwen manifest даёт `SEALED_CANDIDATE`; mismatch/absence —
terminal `QWEN_UNUSABLE`, no retry and no transfer. Seal расходует один вызов
общего лимита семь и не получает acceptance authority.

Критерий: isolated smoke проходит `yolo` unsealed diff -> receipt -> Qwen
plan-seal manifest, после чего candidate всё ещё требует independent review.

D027 runtime enforcement: atomically reserve the ticket's sole seal call, include PATCH_SEAL_RECEIPT in Qwen's packet, and emit SEALED_CANDIDATE only after capture-reader exact terminal-manifest comparison.
