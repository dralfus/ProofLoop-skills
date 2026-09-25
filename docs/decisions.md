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

## D028 — Условно проверять минимальное решение ordinary non-Qwen ticket

Статус: принято 2026-09-20.

Наблюдаемый failure: ordinary ticket может получить новый код, abstraction или dependency вместо уже доступного reuse/platform/installed dependency. Постоянный prompt для всех ролей не доказал экономию reasoning-моделей и может увеличить input/reasoning usage.

Решение: только для eligible ordinary non-Qwen Codex ticket Controller может добавить в существующий `IMPLEMENTATION_PACKET` необязательный пятистрочный `MINIMAL_SOLUTION_CHECK`, сформированный из preflight. Он не создаёт agent, tool-call или audit. Reviewer после `SPEC` и `CODE_QUALITY` задаёт один вопрос о доказанной простой альтернативе; finding остаётся `QUALITY_BLOCKER`. Qwen, critical/resumed/partial, security, concurrency, native/UI, design-gap и unproven-seam ticket исключены.

Критерий успеха: после десяти применимых ticket хотя бы один наблюдаемый дорогой показатель уменьшается без роста scope drift, repair или acceptance failures. LOC сам по себе не является доказательством; при отсутствии выгоды check удаляется отдельным решением.

## D029 — Guarded native Qwen session до dispatch `$finish-ticket`

Статус: принято 2026-09-20; реализация запланирована tickets 16--18.

Наблюдаемый failure: server-side sampling defaults устраняют языковые
артефакты, но Qwen может начать работу без required skill либо повторять
одинаковые tool calls до встроенного watchdog. Текстовое обещание модели не
является доказательством фактических runtime limits.

Решение: добавить отдельный ProofLoop-owned launcher для native Qwen Code.
Он не меняет `qwen.cmd`, пользовательские настройки, endpoint или API key;
до запуска проверяет loop detection, depth, extension и создаёт raw-free
`QWEN_SESSION_GUARD` receipt. Native Qwen Controller до role dispatch требует
fresh receipt. Исчерпание turn/tool/wall budget, streaming-loop detection или
повтор инструментального fingerprint создают `QWEN_RUNTIME_GUARD_STOP` и
требуют fresh session с новым evidence. `QWEN_ASSIST` не изменяется.

Критерий успеха: в серии из трёх guarded native Qwen sessions нет dispatch без
receipt и нет continuation после budget/fingerprint stop; измеряются только
raw-free guard outcome, terminal reason, mode, duration и доступные counters.

## D030 — Capability-based compatibility для guarded launcher

Статус: принято и реализовано 2026-09-20.

Наблюдаемый failure: launcher Ticket 16 и операторский путь были связаны с
точной версией Qwen, хотя установленный Qwen 0.24.0 предоставляет требуемые
CLI capabilities. Номер версии сам по себе не доказывает совместимость
canonical argv и необоснованно блокирует bounded запуск.

Решение: только launcher capability path проверяет наблюдаемые required CLI
markers и строгий canonical argv contract; version string сохраняется лишь в
raw-free smoke evidence. Security gates Ticket 16, включая safe-mode,
loop detection, max depth, extension, receipt и запрет mutations, сохраняются.
Smoke ограничен `qwen --version` и `qwen --help`, не dispatch'ит role и не
выполняет acceptance. Qwen role-agent profile и tickets 17--18 не изменяются.

Критерий успеха: установленный Qwen 0.24.0 проходит capability smoke без
Implementer/acceptance, а launcher блокирует missing capability до ticket work.

## D031 — Lifecycle gate и terminal stop для guarded Qwen session

Статус: принято и реализовано 2026-09-20.

Наблюдаемый failure: raw-free `QWEN_SESSION_GUARD` receipt доказывал стартовые
limits, но Controller ещё мог продолжить работу после stale/mismatched receipt,
исчерпания runtime budget, loop или повторного tool fingerprint.

Решение: pure policy gate принимает только fresh compatible receipt и raw-free
runtime observation. Missing/stale/mismatched evidence возвращает
`BLOCKED_CAPABILITY` до role dispatch. Budget/loop/fingerprint stop добавляет
append-only terminal event `QWEN_RUNTIME_GUARD_STOP` без нового role launch.
Continuation требует нового receipt/launch identity и нового reproducible
evidence; immutable `ledger_anchor` и `prev_hash`/`event_hash` chain блокируют
удаление или замену prefix. Gate не запускает Qwen, Implementer или acceptance
и не меняет acceptance authority.

Критерий успеха: fixtures доказывают fail-closed receipt gate, terminal stop по
каждому runtime predicate и разрешают только fresh continuation с новым
evidence; Qwen-owned profile и Ticket 18 не изменяются.

## D032 — Owner-authorized identity для Ticket 18 fixture revalidation

Статус: принято 2026-09-21.

Runtime drift: администратор заменил Qwen model. Для bounded Ticket 18 fixture
допущена declared identity `qwen38-flash-next` с source
`USER_AUTHORIZED_CONFIGURATION`; это не является version allow-list и не меняет
Qwen role profile, settings, provider или sampling.

Ограничение evidence: server-side active identity не получает независимой
attestation в read-only `--version`/`--help` probe. Controlled pilot обязан
публиковать это raw-free limitation и не расширяет authority. Provider metadata
probe или signed attestation остаются отдельным будущим prerequisite.

## D033 — Explicit native read-only recon contract

Статус: принято и реализовано 2026-09-21.

Наблюдаемый failure: guarded launcher принимал только `protocol`, поэтому
read-only recon нельзя было выразить через проверяемый command/authority
contract. Снятие `ValidateSet` без новых ограничителей сделало бы fixed
`/finish-ticket` entry point неявно универсальным и не доказало бы отсутствие
write, subagent или acceptance действий.

Решение: добавить отдельный `recon` mode с `qwen.cmd`, clean fixed-point
worktree, `--bare`, `--approval-mode plan`, JSON/schema output, исключёнными
write/shell/Agent tools, disabled `review,loop` commands и bounded
`3 turns / 6 tools / 5m / depth 1` (Qwen CLI depth is 1-based; Agent remains
excluded). Launcher сохраняет raw-free
`QWEN_RECON_GUARD`; pure lifecycle policy возвращает только
`QWEN_RECON_READY`, `BLOCKED_CAPABILITY`, `QWEN_UNUSABLE` или
`QWEN_RUNTIME_GUARD_STOP`, всегда с `role_dispatch=false`,
`subagent_dispatch=false` и `acceptance=false`. Terminal recon ledger закрыт
навсегда с `RECON_TERMINAL_LEDGER_CLOSED`; fresh independent recon session
начинается только с пустого genesis ledger/anchor, новыми launch/session/ledger
identity и registry-проверенным evidence identity. Active non-empty ledger
принимает только exact same receipt; новый launch получает
`RECON_ACTIVE_LEDGER_LAUNCH_MISMATCH`.

Exact protocol argv/receipt contract и Ticket 16 security gates не меняются.
Recon report является read-only analysis evidence, не role-agent и не
acceptance evidence. Live Qwen/protocol запуск в Ticket 20 не требуется.

Ticket 21 status: implementation accepted locally with `SPEC: SCOPED_PASS`,
но не `DONE`; F1 follow-up получил PASS. Полный blocked-contract regression
для `session_id`/`ledger_id` mismatch и устранение дублированных active
`launch_id`/`session_id` checks с сохранением reason order закрыты локально.
Live Ticket 18 pilot не запускается автоматически и требует отдельного
разрешения; live evidence и acceptance остаются NOT_RUN.

Критерий успеха: focused fixtures доказывают clean-worktree gate,
capability/schema/read-only enforcement, budget/loop/fingerprint terminal stops
и byte-equivalent existing protocol command contract; документация и plugin
lifecycle синхронизированы.

## D034 — Передача validated recon worktree через process cwd

Статус: принято и реализовано локально 2026-09-22; live revalidation закрыта
D036.

Наблюдаемый failure: live Qwen recon завершался до structured-output terminal
event с `stdout_present=false`, `stderr_present=true`. Static inspection Qwen
0.24.3 показала, что `--worktree` принимает slug и создаёт или переиспользует
только `.qwen/worktrees/<slug>`; launcher передавал путь уже подготовленной
ProofLoop worktree (`.worktrees\\...`) как slug.

Решение: сохранить отдельную clean fixed-point gate, но запускать Qwen из неё
через process current directory и убрать `--worktree` из recon argv. Qwen CLI
требует 1-based `--max-subagent-depth`, поэтому recon передаёт `1`, а запрет
subagent остаётся enforced через `--exclude-tools Agent`. Capability gate
проверяет только реально используемые флаги. Это не меняет provider,
model, settings, sampling, auth или protocol mode.

Измеримый критерий: regression fixture фиксирует cwd равным validated worktree,
отсутствие `--worktree` в argv и schema-valid read-only terminal report; live
bounded recon должен перейти из прежнего `QWEN_COMMAND_FAILED` в
`QWEN_RECON_READY` либо дать новый raw-free terminal reason.

## D035 — Raw-free классификация Qwen JSON error envelope

Статус: принято и реализовано локально 2026-09-22.

Наблюдаемый failure: Qwen возвращал валидный JSON на stdout/stderr и ненулевой
exit, но launcher видел только общий `QWEN_COMMAND_FAILED`; envelope мог быть
как терминальным `result`, так и top-level object с `is_error`, `subtype` и
вложенным `error.message`.

Решение: child bridge извлекает только структурные признаки и allowlist-
категории (`structured_output_missing`, `auth_or_forbidden`, `transport`,
`other`), parent сохраняет их в raw-free diagnostic. Текст ошибки, endpoint,
токен и transcript не публикуются. JSON error-result получает отдельный
`QWEN_JSON_ERROR_RESULT`, а structured-output marker сохраняет приоритет.

Критерий: fixtures покрывают Qwen-shaped terminal и top-level error envelope,
а также HTTP 403-подобный случай без утечки raw message; 127 тестов и
PowerShell parser проходят.

## D036 — Bounded recon: native exit, prompt budget и baseline identity

Статус: принято и реализовано локально 2026-09-22; live recon доказан.

Наблюдаемые failures после D034/D035:

1. Qwen 0.24.3 возвращал schema-valid `type=result` с `is_error=false`,
   но завершался Windows native exit `-1073740791`; child bridge терял уже
   полученный report, потому что трактовал любой non-zero как failure.
2. Длинный запретительный recon prompt провоцировал Qwen исчерпать
   `max-session-turns`/tool budget (raw-free exit 53/55), хотя capability,
   schema и API smoke проходили.
3. Короткий prompt давал `EVIDENCE_FOUND`, но без переданного fixed point
   модель вернула несовпадающий baseline.

Решение: child принимает native exit только для allowlisted Windows code и
только при наличии terminal `success` с object `structured_result`; обычные
non-zero и error envelopes остаются fail-closed. Recon prompt сокращён до
одной read-only инспекции `README.md` и одного `structured_output`; write,
shell, Agent и slash-команды по-прежнему блокируются CLI/guard gates. Parent
передаёт уже проверенный `reconFixedPoint` в child, prompt требует установить
его без изменения, а parent повторно сверяет baseline.

Измеримый результат: focused runtime-guard suite `15/15`, PowerShell parser
`ok`; live launch `814298d37ba7487c83c3313b72b1f936` завершился
`QWEN_RECON_READY` с `EVIDENCE_FOUND`, `structured_output_valid=true`,
`writes=false`, `role_dispatch=false`, `subagent_dispatch=false`,
`acceptance=false`, budget `3/6/5m/depth1`, clean fixed point
`335ba1dc0364e7bb9ac0413925e1a1e8440cb760`. Это recon evidence, не
Implementer и не acceptance authority.

## D037 — Manifest-only seal после сбоя host-side collector

Статус: принято и реализовано локально 2026-09-22.

Наблюдаемый failure: bounded Qwen implementation изменил только disposable
test-файл и прошёл targeted test, но post-run collector завершился ошибкой
нормализации optional/singleton JSON-свойства `.Count`. Из-за этого terminal
manifest нельзя честно классифицировать как Qwen turn-limit failure, хотя
independent diff/test evidence сохранилось.

Решение: исправить collector так, чтобы он нормализовал terminal event через
явный `[object[]]` и принимал только финальный `result` с
`is_error=false`, `subtype=success` и object `structured_result`. Для одного
изолированного manifest-only запуска добавить отдельную allowlist-причину
`COLLECTOR_PROJECTION_FAILED`; она доступна только при independently observed
bounded diff и green targeted test и не утверждает причину завершения Qwen.
После live error выяснилось, что Qwen CLI считает structured output tool call;
поэтому seal использует ровно `--max-tool-calls 1`, а все write/shell/Agent
tools остаются исключёнными. Seal не получает transfer или acceptance authority.

Критерий: regression tests покрывают singleton/array terminal JSON и
singleton property collection; новый launch выдаёт только raw-free
`SEALED_CANDIDATE` или terminal `QWEN_UNUSABLE`.

## D038 — Один structured-output вызов в manifest-only seal

Статус: принято и реализовано локально 2026-09-22.

Наблюдаемый failure: при `2 turns / 0 tools` Qwen завершился
`FatalTurnLimitedError`, а при `4 turns / 0 tools` вернул JSON envelope
`structured_output_missing`. Это не transport/auth failure: нулевой tool budget
запрещал самому Qwen вызвать требуемый structured-output канал.

Решение: manifest-only seal получает `4 turns / 180s / depth1` и ровно один
tool call, который может быть только structured output; Agent/edit/shell и
network/MCP остаются недоступны. Любой другой tool call не разрешается
exclusion/guard contract. Новый packet получает отдельную reservation identity;
повтор внутри одной seal identity запрещён.

Критерий: live launch должен вернуть terminal schema-valid manifest, после
чего capture reader и независимый validator выдают `SEALED_CANDIDATE`.

## D039 — Provider-friendly schema для manifest-only seal

Статус: принято и реализовано локально 2026-09-23; bounded E2E доказан.

Наблюдаемый failure: smoke-schema давала terminal `structured_result`, но
patch-schema с `const`, min/max constraints и union type неоднократно доходила
до `FatalTurnLimitedError` без structured call. Явный `qwen.cmd` воспроизводил
тот же результат, поэтому entrypoint, auth/transport и collector не были
primary cause. Дополнительно штатный slug `qwen-patch-ticket-314` мог быть
заблокирован уже существующей Qwen-managed веткой.

Решение: provider-facing schema содержит только required поля, basic JSON types
и `additionalProperties=false`; строгие ограничения остаются в
`qwen_assist.py` и independently observed `PATCH_SEAL_RECEIPT`. Повторное
использование Qwen worktree slug не удаляет существующие ветки: Controller
выбирает новый bounded slug после raw-free preflight failure.

Измеримый результат: regression test фиксирует provider-friendly shape; fresh
launch `cbffea5e84ed421cb1566e61b7cd4485` (`12/1/300s/depth1`) вернул через
capture reader `SEALED_CANDIDATE`. Transfer, acceptance и product
implementation не выполнялись.

## D040 — Единый QwenTerminalProjection для terminal transport

Статус: принято и реализовано локально 2026-09-23.

Наблюдаемый failure: CLI bridge, recon launcher и capture reader независимо
классифицировали terminal JSON, structured-output failure и error envelope.
Расхождение правил могло дать разные raw-free reasons для одного Qwen
transport outcome.

Решение: выделить pure Python module `QwenTerminalProjection`. Его interface
принимает stdout/stderr и возвращает только allowlisted projection; отдельный
extractor принимает только финальный `type=result` со schema-valid
`structured_result`. PowerShell adapters отвечают лишь за I/O и exit mapping;
протокол сохраняет намеренно silent output contract.

Измеримый результат: recon, capture и assist paths используют общий parser;
fixtures покрывают terminal success, structured-output missing, auth/forbidden,
malformed и trailing-transcript cases; полный suite `138/138`, PowerShell
parser `ok`. Raw message, transcript и secrets в projection не попадают.

## D041 — Единый executable contract для QWEN_RECON_REPORT

Статус: принято и реализовано локально 2026-09-23.

Наблюдаемый failure: Python `qwen_assist.py` и PowerShell recon launcher
валидаировали один `QWEN_RECON_REPORT` разными правилами. Python принимал
отсутствующие terminal fields и лишние fact properties, а PowerShell выполнял
собственную копию проверок. Это создавало риск разных raw-free причин для
одного malformed, read-only или baseline-mismatch output.

Решение: `scripts/recon_report_contract.py` владеет executable semantic
contract: allowlisted fields, terminal `stop_reason`/`writes`, exact locatable
facts, read-only violation и optional fixed-point comparison. JSON Schema
остаётся декларативным wire contract; Python и PowerShell adapters делегируют
ему semantic verdict, не передавая raw output через аргументы.

Измеримый результат: production-shaped valid/malformed/write/baseline fixtures
покрыты Python contract tests и PowerShell launcher regressions; полный suite
`142/142`, PowerShell parser `ok`. Qwen settings, provider, credentials и
внешний MCP-конфиг не изменялись.

## D042 — Общая QwenGuardPolicy до native dispatch

Статус: принято и реализовано локально 2026-09-23.

Наблюдаемый failure: guarded PowerShell launcher имел inline-проверки
settings/capabilities/worktree, а protocol и recon различались только по
разрозненным ветвям. Не было одного проверяемого решения, которое связывает
budget, authority flags, receipt freshness и fixed point до вызова Qwen.

Решение: выделить pure `scripts/qwen_guard_policy.py`. Он принимает только
raw-free projected settings, worktree facts, capability markers и receipt
facts; возвращает `QWEN_GUARD_READY`, `BLOCKED_CAPABILITY` или terminal
`QWEN_RUNTIME_GUARD_STOP` с явными authority flags. Protocol сохраняет
`20/20/30m` и role/subagent authority, recon — `3/6/5m`, read-only и все
authority flags false. PowerShell adapter вызывает policy через временный
JSON-файл и не dispatch'ит child Qwen до `QWEN_GUARD_READY`.

Измеримый результат: unit matrix покрывает budgets, settings, capabilities,
stale receipt, dirty worktree, fixed-point drift, loop/terminal stop и raw-free
output; launcher recon/protocol regressions проходят, PowerShell parser `ok`.
Qwen settings, provider, credentials и внешний MCP-конфиг не изменялись.

## D043 — Production-shaped behavioral fixtures для Qwen adapters

Статус: принято и реализовано локально 2026-09-23.

Наблюдаемый failure: часть Qwen regression tests подтверждала поведение через
поиск строк в PowerShell source. Такой тест мог остаться зелёным после
поломки runtime helper и не покрывал совместную семантику terminal,
recon-report и credential boundary.

Решение: добавить fixture matrix
`tests/fixtures/qwen-adapters/production-shaped.json` и runner, который
вызывает публичные `QwenTerminalProjection`/`ReconReportContract` interfaces.
Отдельный PowerShell fixture запускает public wrapper с fake Qwen и stub
Credential Manager, наблюдая фактический restore `OPENAI_*` после failure.
Source assertions остаются только минимальным adapter smoke coverage.

Измеримый результат: matrix покрывает terminal success, malformed JSON,
baseline mismatch, read-only write violation и credential restore; fixture
runner `2/2` зелёный. Fixture-only GREEN не является acceptance evidence.

## D044 — Единый QwenInvocationContract registry

Статус: принято и реализовано локально 2026-09-23.

Наблюдаемый failure: assist, native recon, protocol, seal и capability smoke
держали budgets, capability markers, exclusions и argv в разных PowerShell/
Python ветвях. Это позволяло тихо дрейфовать mode-specific contract и смешать
read-only recon с protocol или seal.

Решение: `scripts/qwen_invocation_contract.py` стал pure registry и renderer.
Он хранит отдельные mode entries для assist, assist-yolo, seal, native recon,
protocol и capability smoke с authority flags; adapters получают из registry
limits/markers и canonical argv, а provider/auth values остаются внешними
inputs. Registry не запускает Qwen и не содержит credentials.

Измеримый результат: contract matrix проверяет distinct budgets, authority,
required markers, exclusions и rendered argv для всех режимов без Qwen launch;
assist, guarded recon/protocol и capability-smoke adapters используют registry.
Protocol compatibility child сверяет входной argv с тем же renderer, поэтому
в нём нет отдельной копии protocol limits. Protocol, recon и seal остаются
разными contracts. Полный suite после этого изменения `154/154`, PowerShell
parser и plugin validator проходят.

## D045 — Fail-closed Qwen session modes без изменения user settings

Статус: принято и реализовано локально 2026-09-23.

Наблюдаемый failure: launcher не различал mode-level thinking policy и output
budget. `recon` мог унаследовать configured high reasoning, а `protocol` не
гарантировал достаточный output budget; изменение persistent settings или
sampling ради режима нарушило бы user-owned configuration boundary.

Решение: pure `scripts/qwen_mode_contract.py` требует от `recon` явный CLI
`--no-thinking` и блокирует его до model request, если установленный CLI такой
capability не показывает. `protocol` требует настроенный reasoning effort и
передаёт `QWEN_CODE_MAX_OUTPUT_TOKENS=8000` только в дочерний process scope,
восстанавливая прежнее значение. Sampling, provider, model и settings не
меняются. Raw-free launcher status включает mode, terminal reason, elapsed
milliseconds и доступные counters; protocol сохраняет canonical argv.

Измеримый критерий: production-shaped fixture проверяет mode policy,
process-scoped output cap/restore и отсутствие dispatch при недоступном
thinking control; установленный Qwen 0.24.4 не публикует `--no-thinking`,
поэтому live recon завершает `BLOCKED_CAPABILITY`, а следующий protocol pilot
не запускается. Это не live role-lifecycle evidence.

## D046 — Recon inherits configured Qwen thinking

Статус: принято владельцем 2026-09-24; supersedes the `recon` thinking gate in D045.

Наблюдаемый failure: D045 превратил экономический режимный выбор в capability
gate. Qwen CLI не имеет отдельного `--no-thinking` флага; при этом thinking
может быть задан через configured `model.reasoningEffort`, и его наличие само
по себе не нарушает read-only authority. Поэтому recon блокировался до запроса
модели, хотя его turn/tool/wall budgets уже ограничивают запуск.

Решение: `recon` сохраняет thinking/reasoning из операторской конфигурации и
свой малый budget `3/6/5m/depth1`. Launcher не должен требовать отключения
thinking или редактировать settings/provider/sampling. `protocol` сохраняет
configured reasoning и process-scoped output cap не ниже 8000.

Следующий шаг: узкий implementation follow-up к Ticket 18 — удалить obsolete
`--no-thinking` gate из recon launcher/contract, обновить fixtures, затем один
новый bounded recon pilot. Protocol запускается только после корректного
terminal outcome recon; при первом guard/evidence/protocol failure — stop без
retry. Это решение не ослабляет read-only restrictions, authority flags или
outer runtime budgets.

Результат follow-up: mode policy, canonical argv и launcher больше не требуют
`--no-thinking`; recon наследует configured reasoning. Qwen 0.24.4 прошёл
capability smoke (11/11 markers), а bounded recon вернул
`QWEN_RECON_READY` на clean baseline с валидным structured output и нулевыми
write/dispatch/acceptance flags. Protocol pilot не является read-only и
документированная процедура включает Implementer/acceptance; до отдельного
согласования этой границы он остаётся NOT_RUN.

## D047 — Progress-gated continuation after Qwen session budget stop

Статус: принято владельцем 2026-09-24.

Наблюдаемый failure mode: один фиксированный protocol-session budget может
остановить сложную задачу при доказуемом progress; простой reset counters и
повтор неизменного входа, напротив, не отличает продуктивное продолжение от
loop. Текущий runtime guard требует fresh receipt после terminal, но ранее
принимал его после `LOOP_DETECTED` и не связывал continuation с проверенным
progress/task scope.

Решение: оставить per-session ceiling `20 turns / 20 tool calls / 30m /
depth 1`; разрешать новую session только после `MAX_SESSION_TURNS_EXHAUSTED`,
`MAX_TOOL_CALLS_EXHAUSTED` или `MAX_WALL_TIME_EXHAUSTED` и Controller-verified
raw-free checkpoint. Checkpoint связывает launch, неизменные task/scope/baseline,
diff, append-only progress ledger/sequence, новый evidence id, допустимый
`LOCAL_GREEN`/`REVIEW_CONTINUE` и один следующий closure. `LOOP_DETECTED` и
`REPEATED_TOOL_FINGERPRINT` остаются terminal. Новый receipt не сбрасывает
историю и counters. Пользовательские Qwen settings, provider, reasoning,
sampling, role profile и внешние Qwen/Stepler files не меняются.

Измеримый критерий policy slice: валидный checkpoint открывает только новую
session с неизменным task/scope/baseline; отсутствующий, replayed, tampered,
regression, non-progress или loop evidence блокирует dispatch. Append-only
ledger сохраняет все прежние observations и terminal причины. Runtime policy
принимает только Controller-attested evidence и не перепроверяет внешний
progress ledger/worktree/review receipt; native launcher пока не подключён.
Local fixtures доказывают policy contract, но не native continuation и не
improvement в живой работе. Следующая задача — native adapter integration,
после неё отдельный live multi-repair Qwen pilot.

## D048 — Native Qwen checkpoint integration is host-verified and fail-closed

Статус: принято владельцем 2026-09-24.

Наблюдаемый failure mode: Ticket 22 runtime policy проверяет hashes и
append-only runtime ledger, но не читает текущий worktree, canonical progress
ledger или test/review receipts. Production protocol launcher не вызывал эту
policy и подавлял весь Qwen output. Opaque Controller hashes сами по себе не
доказывают ни текущий diff, ни прогресс.

Решение: добавить host-side continuation adapter, который пересчитывает
task/scope/baseline/diff fingerprints, проверяет progress-ledger chain и typed
fresh receipt bindings и только затем вызывает Ticket 22 policy. Native
launcher разрешает dispatch только при `QWEN_RUNTIME_GUARD_READY`; checkpoint и
progress-evidence identities помечаются как consumed. Для наблюдения session
используется Qwen `--json-file`, но sidecar является полным чувствительным
transcript: он временен, обрабатывается raw-free и удаляется. Continuation
context передаётся отдельно только в prompt, не попадая в receipt/ledger.

Ограничение доказательства: текущий projection фиксирует session/counters, но
не устанавливает terminal budget reason или loop-clear. `session_end` не
считается budget stop. Неизвестный, неполный либо не связанный с runtime ledger
terminal projection блокирует continuation. Поэтому локальный READY fixture
доказывает adapter→policy композицию, но live Qwen multi-repair продолжает
оставаться отдельным NOT_RUN gate до подтверждённого источника terminal
evidence.

Актуализация evidence 2026-09-24: официальный Qwen Code `v0.24.4` native
`--json-file` sidecar не содержит typed budget-stop reason или явного loop
state. Headless `-p` output не эквивалентен native path, а exit `55` не
различает wall-time и tool-call budgets. Отсутствие события не доказывает
`CLEAR`; Ticket 24 остаётся `BLOCKED_EVIDENCE_SOURCE` до availability либо
отдельно одобренного совместимого terminal source. См.
`docs/research/qwen-v0244-dual-output-terminal-evidence.md`.

Измеримые критерии: каждый task/scope/baseline/diff/progress/test/review
mismatch блокирует dispatch; valid fixture создаёт fresh decision и сохраняет
предыдущие counters/events; loop/repeated fingerprint и replay остаются
terminal; fake launcher доказывает нулевой Qwen dispatch при блокировке; ни raw
event, ни continuation packet не попадают в постоянные receipts.

## D049 — Native protocol получает API key только из Windows Credential Manager

Статус: локально исправлено и regression tests RED→GREEN; bounded protocol
pilot остановился до model dispatch.

Наблюдаемый failure mode: native `protocol` launcher вызывал Qwen CLI, но не
читал Windows Credential Manager. В `recon` такой read уже существовал. В
результате успешная ручная аутентификация и recon не доказывали, что protocol
child получает API key; верхний launcher также терял настроенный
`CredentialTarget`. Официальный Qwen Code auth contract для OpenAI-compatible
provider разрешает API key из `OPENAI_API_KEY`, а не из Windows Credential
Manager напрямую. Единственный bounded protocol attempt дополнительно
остановился до Qwen request: `.NET SpecialFolder.UserProfile` не совпал с
`USERPROFILE`, где расположен пользовательский Qwen config.

Решение: перед native Qwen `protocol` dispatch прочитать Generic Credential
для настроенного target, передать его как `OPENAI_API_KEY` дочернему процессу
Qwen, а сразу после его возврата восстановить или удалить прежнее process
значение до projection/любых других subprocess; `finally` страхует исключения.
Передать `CredentialTarget` через оба launcher слоя; default `SettingsPath`
строить от `USERPROFILE`. Не записывать ключ в environment пользователя,
settings, receipts или logs; protocol не меняет endpoint/model и sampling. Для
`recon` сохраняется его существующий process-scoped endpoint/model contract.

Почему прежние gates это пропустили: protocol fixtures проверяли argv, budget,
sidecar и raw-free projection, но не наблюдали credential resolution и
конфайнмент секрета на границах child processes; credential fixture покрывал
другой adapter. Launcher tests передавали `SettingsPath` явно и не проверяли
Windows profile default.

Измеримый критерий: fake native launcher с изолированным fake Credential
Manager проходит `BLOCKED/RED → QWEN_SESSION_GUARD_READY/GREEN`, Qwen child
видит fixture secret, а следующий Python projector — нет; исходное process
environment восстановлено, custom target доходит без drift, stdout/stderr и
permanent evidence не содержат fixture key. Default-path regression фиксирует
`USERPROFILE`. Реальный протокол запускается отдельно только после этого
локального gate; запуск после terminal guard failure не повторяется
автоматически.

## D050 — Сохранять raw-free terminal evidence protocol при fail-closed projection

Статус: реализовано локально, regression-tested 2026-09-24.

Наблюдаемый failure mode: runtime adapter намеренно завершает процесс кодом
`3`, когда выдаёт валидную raw-free projection со статусом
`BLOCKED_CAPABILITY`. CLI compatibility layer считала любой ненулевой code
ошибкой самого projector и заменяла его JSON на общий
`QWEN_RUNTIME_EVIDENCE_UNSUPPORTED`. В результате верхний launcher терял
причину, доступные counters и exit code Qwen. Дополнительный regression также
выявил strict-mode access к необязательному `reason` у обычной успешной
projection.

Решение: принимать adapter codes `0` и `3` только при наличии валидного JSON,
при этом `3` остаётся fail-closed outcome и не даёт dispatch authority. Для
terminal `type=result` с `is_error=true` извлекать только raw-free
`subtype`, presence/category `error.message`, hashed session id, counters,
wall time и tool fingerprint; `error.message`, transcript, URL, token и
session id не сохранять. Child и parent передают numeric Qwen/projector exit
codes и parse/output booleans по allowlist. Неизвестный code, malformed JSON
или unsupported schema остаются blocked.

Почему прежние gates это пропустили: tests покрывали pure projection и
успешный adapter subprocess отдельно, но не совместный terminal-failure путь
через exit code `3`, PowerShell CLI bridge и parent status serializer.

Критерий: synthetic native launcher с error envelope (`HTTP 403`, private URL
и fixture token) проходит RED→GREEN на полном adapter→CLI→parent пути; status
остаётся `QWEN_COMMAND_FAILED`, reason становится `QWEN_JSON_ERROR_RESULT`,
доступные counters/exit codes присутствуют, а текст ошибки/URL/token нигде не
публикуются. Этот критерий улучшает локальную диагностику, но не устанавливает
задним числом причину предшествующего live Qwen failure и не отменяет запрет
на автоматический retry.

## D051 — Host-owned terminal evidence как отдельный источник Qwen continuation

Статус: принято владельцем 2026-09-25; runtime-реализация локально выполнена
и прошла local verification; live gate Ticket 24 остаётся отдельным.

Наблюдаемый failure mode: native Qwen `--json-file` contract не предоставляет
проверяемые typed budget-stop reason и positive loop-clear. Текущий launcher
синхронно вызывает Qwen, читает event sidecar после завершения и потому не
может утверждать, что сам остановил процесс по wall/tool ceiling. `session_end`,
обычный exit и отсутствие loop-события не заменяют эти факты.

Решение: для continuation допускается отдельно доказанный host-owned evidence
source как альтернатива native Qwen signal, но не как его эмуляция. Он обязан
связать launch/session, типизированную host stop action, завершение именно
этого child process, полное покрытие event stream и raw-free receipt. `HOST_CLEAR`
может быть eligible loop evidence только как результат явного, версионируемого
host detector, завершившего анализ полного потока. Это утверждение ограничено
правилами detector и не является `NATIVE_CLEAR` или гарантией отсутствия любого
возможного цикла. Неполнота, неизвестность, противоречие либо неупорядоченная
гонка дают `UNKNOWN` и запрещают continuation. `NORMAL_EXIT` не является budget
stop и не открывает budget continuation.

На момент принятия решение фиксировало целевую evidence semantics, но не
доказывало наличие source. До implementation, полного локального
fake-process/evidence suite и отдельного bounded live gate Ticket 24 оставался
`BLOCKED_EVIDENCE_SOURCE` / `NOT_RUN`.
Process supervision обязан сохранить native TUI mode и не менять Qwen settings,
provider, credentials, sampling, reasoning, role profile или loop-detection
configuration. Если supervisor не может доказать process ownership, event
completeness и TUI compatibility, host source считается unsupported; применяется
существующий fail-closed путь.

Дополнительный completeness gate: опубликованный Qwen Dual Output contract
допускает adapter exception, отключающий event bridge без `session_end`. Поэтому
для host-issued stop supervisor обязан зафиксировать stop intent при живом child,
снять `event_file_bytes_at_stop` до graceful interrupt и получить matching
`session_end`, начинающийся не раньше этого offset и завершающийся до полного
process-tree exit. Размер снимается до сигнала: fake-child показал, что при
быстром graceful response `session_end` может начать записываться между сигналом
и post-signal size sample, оставляя cutoff внутри его JSONL-строки. Последняя
проверка child liveness перед сигналом и line-boundary validation закрывают
наблюдаемый race; offset должен совпадать с границей полной JSONL-строки. Отсутствующий
post-stop `session_end`, timeout с force-kill или неоднозначная последовательность
дают `INCOMPLETE`/`UNKNOWN`; закрытия файла недостаточно для continuation.

Проверенные локальные fixtures для `exact_tool_interaction_cycle_v1` обязаны
защищать обычные повторы: одинаковые tool name/input при разных результатах,
одинаковых результатах с разным assistant content и только две идентичные
завершённые interaction cycles не являются `DETECTED`. Три полные идентичные
cycles дают только terminal classification; detector не посылает signal
работающему child. Намеренный workflow с тремя совершенно одинаковыми cycles
остаётся явным риском false positive для continuation, не для живого действия.

Измеримые критерии реализации: (1) fake process покрывает wall/tool stop,
normal exit, interrupt, crash и races; неоднозначные случаи дают `UNKNOWN`;
(2) raw-free receipt связан с launch/session and checkpoint identities и не
содержит prompt, transcript, tool payloads, paths, credentials или raw errors;
(3) host detector выдаёт `HOST_CLEAR` только при `event_coverage=COMPLETE`,
идентичной session и завершённом versioned analysis; missing/unknown/malformed
events блокируют; (4) runtime dispatch остаётся нулевым на любом unsupported
или blocked receipt; (5) fixtures не выдаются за live Qwen proof.

Implementation ruling по запросу владельца 2026-09-25: первоначальный
fingerprint только `{tool name, input}` отклонён как слишком широкий — одинаковые
read/check действия возможны в нормальной работе, а один fingerprint игнорирует
tool result и текст assistant. Для реализации выбран versioned detector
`exact_tool_interaction_cycle_v1`: он сравнивает три соседних завершённых
assistant tool-use/result cycle, связывает каждый result с `tool_use_id` и
включает нормализованный assistant content, ordered tool names/inputs и matched
result content/`is_error`; уникальные IDs исключаются. Несвязанный, неизвестный,
неполный либо потенциально усечённый cycle даёт `UNKNOWN`. Этот детектор только
классифицирует полный terminal stream и никогда не останавливает процесс;
process stop остаётся только за typed wall/tool ceilings, причём tool ceiling
считается по завершённым use/result парам.

Остаточный риск: любой эвристический detector может совпасть с намеренным
повтором полного interaction cycle или пропустить цикл, меняющий содержимое.
Это не oracle намерения; версия и ограниченная семантика должны быть видны в
receipt и тестах. Локальная матрица обязана показать отсутствие срабатывания на
одинаковых действиях с разными результатами и на одинаковых действиях/результатах
с различным assistant content. Основание и таблицы terminal evidence находятся в
`docs/superpowers/specs/2026-09-25-qwen-host-owned-terminal-evidence-design.md`.

Implementation finding, 2026-09-25: первый supervisor запускал `.cmd`
через shell-compatible путь. Fake-child regression показал, что многострочный prompt
и `%PATH%`/кавычки/метасимволы изменяются на пути через `cmd.exe`; тот же путь
мог исполнить произвольный неизвестный batch wrapper. Принятое узкое исправление:
для известного Qwen `qwen.cmd` npm-style Node shim распознаётся точная форма
wrapper и фиксированный `node_modules\@qwen-code\qwen-code\cli-entry.js`,
после чего supervisor вызывает найденный `node.exe` напрямую с entrypoint и
неизменённым argv. Protocol capability `--help` preflight использует тот же
direct-Node adapter до любого исполнения Qwen-команды. `.ps1` и `.exe` также
остаются прямыми дочерними процессами. Неизвестный `.cmd`, изменившаяся форма
или отсутствующий Node/entrypoint блокируются до исполнения, включая ранний
preflight; shell fallback запрещён. Критерий: fake Node
получает исходные argv values, включая newline, кавычки, `%PATH%`, `^`, `|`, `!`;
неизвестный wrapper не исполняется ни на capability preflight, ни при child
launch; установленный shim проходит только read-only recognition. Полный
launcher regression проверяет `QWEN_CLI_UNAVAILABLE` до marker side effect.
Стандартные потоки, process-group/job ownership и native protocol argv
подтверждаются fake-child tests; эти tests не выполняют Qwen CLI или model
request.

Implementation status, 2026-09-25: локальные host-owned receipt, loop detector,
checkpoint binding, supervisor wiring и canonical/operator documentation
прошли full local test suite (`224/224`), documentation/invocation-contract
tests (`74/74`), plugin validation (exit 0), PowerShell AST parsing
(`3/3`) и `git diff --check`. Отдельный direct-Node transport test
прошёл после добавления проверки redirected console flags; дополнительный
full-launcher regression блокирует неизвестную обёртку на capability preflight
до любых side effects. Ни Qwen CLI, ни модель не запускались;
settings/provider/auth не менялись. Ticket 24 остаётся
`BLOCKED_EVIDENCE_SOURCE` / `NOT_RUN`, потому что реальный native Qwen
process/event-stream compatibility pilot не выполнялся.

Live implementation finding, 2026-09-25: после этого был выполнен один
bounded disposable protocol launch. Он завершился `QWEN_COMMAND_FAILED` за
1478 ms; `turn_count` и `tool_call_count` были `NOT_AVAILABLE`,
`session_ended=false`, `loop_status=UNOBSERVED`, `budget_stop=false`, а typed
Qwen/projector exit code, error category и runtime projection отсутствовали.
В receipt directory сохранился только предзапусковой `QWEN_SESSION_GUARD`.
Фактическая причина — child launch, provider/transport failure или event capture
— по имеющимся raw-free данным неразличима.

Минимальная коррекция evidence path: parent сохраняет отдельный versioned
`QWEN_TERMINAL_OUTCOME` при nonzero/unsupported protocol outcome; запись идёт
через временный файл с rename и возвращает `terminal_receipt_written`. Receipt
может содержать parent failure и явные unavailable counters/runtime fields, не
выдавая их за Qwen runtime event projection. Synthetic regression до изменения
был RED, после — GREEN; он проверяет сохранение
`QWEN_JSON_ERROR_RESULT`/`auth_or_forbidden` и отсутствие URL, token и raw
message. Это устраняет потерю доступного failure evidence, но не устанавливает
задним числом первопричину и не разрешает retry.
Ticket 24 остаётся заблокирован до отдельного bounded live gate.
