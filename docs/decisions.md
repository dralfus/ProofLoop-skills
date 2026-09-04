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
