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

Статус: exact-version gate superseded решением D056; capability gates сохранены.

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

Критерий исходного решения: fixture для Qwen v0.22.2 выбирает single-model profile и
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
Qwen extension initially used `/proofloop-skills:finish-ticket ticket <ID или путь>`;
D055 later set the protocol route to the owner's personal `/finish-ticket`. Exact capability
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
contract. Снятие `ValidateSet` без новых ограничителей сделало бы then-current
fixed `/proofloop-skills:finish-ticket` entry point (route later corrected by D055)
неявно универсальным и не доказало бы отсутствие
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

## D052 — Диагностируемый visible-output protocol pilot

**Observed failure:** bounded native protocol launch 2026-09-25 завершился
`QWEN_COMMAND_FAILED`; raw-free terminal receipt не показывал, разрешилась ли
команда, был ли создан child, завершился ли процесс и в каком состоянии остался
event file. Скрытые stdout/stderr child не позволяли оператору увидеть
терминальный ответ Qwen. Причина конкретного запуска осталась неизвестна.

**Почему текущий workflow не обработал failure:** существующий receipt сохранял
runtime summary/counters, но не launch-stage evidence; supervisor подавлял child
stdout/stderr без отдельного диагностического режима.

**Решение:** добавить allowlisted raw-free launch stages и состояние event file
в `QWEN_TERMINAL_OUTCOME` v2. Добавить opt-in `-ShowOutput` для protocol
launcher: стандартное подавление остаётся поведением по умолчанию; видимый вывод
идёт оператору, но не попадает в JSON projection/receipt. Это не меняет
настройки, provider, credentials, sampling, reasoning, role profile, budget,
authority gates, acceptance или continuation policy.

**Измеримый критерий:** synthetic tests покрывают видимый stdout/stderr,
неизменное подавление по умолчанию, неподдерживаемый command type,
`process_state`/exit code и `MISSING`/`EMPTY` event file; raw markers и текст
исключения отсутствуют в receipt. После полного локального gate разрешён один
новый clean disposable test-only protocol pilot с объявленными mode/budget.
Любой gate/protocol failure терминален и не повторяется. Pilot не является
Ticket 314 product acceptance и не снимает Ticket 24 `BLOCKED_EVIDENCE_SOURCE`.

**Результат bounded attempt, 2026-09-25:** capability smoke прошёл на Qwen CLI
`0.24.5` со всеми пятью capability markers. Один visible-output protocol
attempt завершился за `1441 ms` с `QWEN_COMMAND_FAILED`; raw-free receipt v2
зафиксировал `outer_stage=RUNTIME_EVIDENCE_PARSED`,
`supervisor_stage=NOT_REACHED`, `process_state=NOT_STARTED`,
`event_file_state=NOT_OBSERVED`, counters `NOT_AVAILABLE`,
`session_ended=false`, `budget_stop=false`, `loop_status=UNOBSERVED` и
`console_output_mode=VISIBLE`. Qwen child и model request не стартовали, target
worktree остался чистым. Это указывает на failure до supervisor dispatch, но не
различает Credential Manager lookup и другие CLI pre-launch steps. Retry не
выполнялся. Рекомендация: отдельная raw-free локальная диагностика pre-launch
stages; новый live launch — только после отдельного разрешения.

## D053 — Интерактивный initial prompt для native protocol

**Observed failure:** локальный `protocol` renderer, capability allow-list,
guard policy и CLI bridge были согласованы вокруг `--prompt`. Qwen Code
документирует `--prompt` как non-interactive запуск, тогда как
`--prompt-interactive` передаёт initial prompt в интерактивную сессию.
Следовательно, contract противоречил native TUI design. Это не устанавливает
причину live попыток 2026-09-25: они остановились до child dispatch, поэтому
Qwen TUI/model request не наблюдались.

**Почему workflow пропустил mismatch:** локальные проверки утверждали только
точное совпадение argv внутри ProofLoop; capability preflight и guard policy
проверяли устаревший marker, не различая interactive и headless режимы CLI.

**Решение:** protocol передаёт initial skill command через `--prompt-interactive`;
конкретный route позже исправлен решением D055.
Invocation registry, launcher preflight, raw-free guard policy и CLI bridge
согласованы; legacy `--prompt` отклоняется. Остальные protocol limits и
authority gates, `--json-file`, Qwen settings, provider/auth, sampling и role
profile сохраняются. Headless fallback запрещён. Общий `capability_smoke`
требует оба prompt-флага (`--prompt` для остальных режимов и
`--prompt-interactive` для native protocol), чтобы наличие только headless
режима не давало ложный readiness.

**Измеримый критерий:** contract test требует `--prompt-interactive` и
исключает `--prompt` в protocol; общий capability smoke требует оба флага и
блокируется, если отсутствует interactive marker; policy принимает только
interactive marker; PowerShell
bridge принимает точный interactive argv и отклоняет legacy headless argv до
child dispatch; protocol runtime fixtures сообщают interactive capability.
Focused invocation, policy и runtime suites проходят. Эти локальные проверки
не подтверждают, что live TUI/approval UI видим или что Qwen ответил.

**Статус:** локальный patch и focused regression проходят; live Qwen не
запускался. Ticket 24 остаётся `BLOCKED_EVIDENCE_SOURCE` / `NOT_RUN` до
отдельного bounded native-compatibility разрешения. Источник CLI semantics:
[Qwen Code v0.24.5 settings/CLI options](https://github.com/QwenLM/qwen-code/blob/v0.24.5/docs/users/configuration/settings.md#L991-L994).

## D054 — Проверять namespace установленного Qwen Skill (заменено D055)

Статус: решение о protocol route superseded 2026-09-26; историческое наблюдение
оставлено, чтобы не скрывать live failure.

**Observed failure:** одна live native protocol попытка передала
`/proofloop-skills:finish-ticket`; Qwen ответил `Unknown command`, model request
не начался. Это подтверждает неуспех namespaced invocation в том процессе;
причина, почему extension command не был доступен там, осталась неизвестной.

**Изначальный вывод:** выбрали extension route, так как protocol был привязан к
пакету. Но владелец использует личный `/finish-ticket`; неудача namespaced
extension route не является свидетельством против личного Skill. D055 выбирает
route установленного владельцем Skill и не утверждает, что причина прежнего
extension-registration failure установлена.

## D055 — Протокол вызывает личный Qwen Skill

Статус: принято 2026-09-26; заменяет protocol-route вывод D054.

**Failure mode:** launcher мог передавать slash-команду не того источника Skill:
личный Skill и Skill из extension имеют разные правила регистрации и имён.
Наблюдавшийся `Unknown command` не определяет причину сам по себе.

**Почему workflow пропустил failure:** registry/bridge жёстко зафиксировали
extension namespace и требовали extension manifest, хотя владелец использует
личный `/finish-ticket` из `~/.qwen/skills/finish-ticket/`. Проверка package
manifest не доказывала доступность выбранного личного Skill.

**Решение:** protocol передаёт `/finish-ticket ticket <ticket>`. Read-only
preflight проверяет только наличие `~/.qwen/skills/finish-ticket/SKILL.md` и
точный frontmatter `name: finish-ticket`. Protocol не требует extension
manifest; `recon` сохраняет свой extension gate. Receipt отмечает
`finish_ticket_skill_available`, а не extension availability. Settings,
provider/auth, sampling, Qwen-файлы и внешний процесс не меняются.

**Измеримый критерий:** registry/bridge принимают bare personal route и
отвергают namespaced route; focused launcher tests доказывают missing/invalid
frontmatter stop до CLI probe и работу протокола при отсутствующем extension
manifest; validators принимают mode-specific receipt. Это локальный contract
proof, не live runtime proof. Live Qwen в рамках решения не запускался.

Источник различия route: [Qwen Code v0.24.5 Agent Skills](https://github.com/QwenLM/qwen-code/blob/v0.24.5/docs/users/features/skills.md#how-skills-are-invoked).

## D056 — Версионно-независимый Qwen role capability preflight

Статус: принято 2026-09-27.

**Observed failure:** локальный Qwen single-model profile разрешал role lifecycle
только при `runtime.version: 0.22.2`; установленный CLI `0.24.6` блокировался до
первой роли, хотя номер версии сам по себе не показывал наличие или отсутствие
обязательных role capabilities.

**Почему текущий workflow не обработал failure:** D015 использовал exact version
как proxy для runtime compatibility. Версии CLI меняются чаще, чем capability
contract, поэтому gate устаревал и не проверял фактическую совместимость.

**Решение:** допуск идентифицирует Qwen по `provider: qwen` и
`product: qwen-code`; любая непустая наблюдаемая версия сохраняется в evidence,
но не является allow-list. Capability declaration требует совпадающие
configured/active model IDs и identity lock; fresh named subagents и
continuation исходного Implementer; read-only Reviewer без fork/write;
executable verification command; observed usage как
`AVAILABLE|NOT_AVAILABLE`. Missing, malformed или несовместимая capability
по-прежнему даёт `BLOCKED_CAPABILITY` до Implementer. Версия остаётся
наблюдаемым runtime trace и не заменяет model identity.

**Измеримый критерий:** новый runtime version проходит тот же capability
validator; missing capability, changed active model и Reviewer write/fork
по-прежнему блокируются; candidate trace сохраняет фактическую версию; live
disposable pilot отдельно показывает Controller, Implementer, независимого
Reviewer и Verifier. Fixture PASS не объявляется live lifecycle proof. Qwen
settings, auth, provider, sampling и внешние файлы не меняются.

Capability model сверяется с официальными возможностями Qwen Code: [named
subagents and continuation](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/sub-agents.md)
и [Agent tool](https://github.com/QwenLM/qwen-code/blob/main/docs/developers/tools/task.md).
Документация upstream не заменяет live evidence установленного CLI.

## D057 — Raw-free evidence фактического Qwen role dispatch

Статус: принято 2026-09-27 для bounded E2E-проверки; без изменения acceptance
authority.

**Failure mode:** host terminal receipt доказывал завершение процесса и общие
счётчики, но не показывал, запускал ли Qwen именованные роли. Отчёт самого
Controller мог ошибочно выглядеть как независимый role lifecycle.

**Почему workflow пропускал failure:** строгая схема terminal receipt намеренно
не сохраняет tool input/result; отдельного raw-free sidecar для именованных
Agent dispatch не было.

**Решение:** рядом с неизменной схемой terminal receipt runtime projection
содержит role_lifecycle_evidence версии proofloop.qwen-role-lifecycle.v1,
спроецированное host adapter из того же полного JSONL session. Оно связано
теми же launch_id и hash session identity и выводит только allowlist
finish-ticket-implementer, finish-ticket-reviewer, finish-ticket-verifier,
состояние парного tool-result, freshness flag и число нераспознанных Agent
calls. Сырые имена, prompts, arguments и results не сохраняются. Успех требует
завершённых fresh named dispatch в порядке Implementer → Reviewer → Verifier;
repair допускает повтор Implementer/Reviewer перед Verifier. Fork/resume,
failure, неизвестная Agent role, отсутствие/нарушение порядка или неполное
событие дают BLOCKED. Событие доказывает только dispatch/completion, но не
ограничения инструментов роли, корректность её вывода, patch quality или
acceptance. Версия Qwen не участвует в allowlist.

**Измеримый критерий:** synthetic projection проходит только для корректного
парного role sequence; missing, reordered, failed, forked/resumed и unknown
dispatch блокируются. Тесты проверяют совпадение launch/session и отсутствие
prompt/result marker в runtime projection. Live E2E считается доказанным лишь
при host receipt COMPLETE и связанном role projection COMPLETE; fixture PASS
сам по себе этого не доказывает.

Upstream описывает agent с subagent_type и отличает named agents от
fork-вызова subagent_type="fork"; конкретный installed CLI обязан пройти live
projection, а не version allow-list:
[Agent tool](https://github.com/QwenLM/qwen-code/blob/main/docs/developers/tools/task.md),
[subagents](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/sub-agents.md).

## D058 — Raw-free диагностика protocol child без JSONL

Статус: принято 2026-09-27 для bounded live-проверок; без изменения role или
acceptance authority.

**Observed failure:** live protocol child завершился с exit code 1 и пустым
JSONL; Qwen debug/latest отсутствовал, поэтому причина и role lifecycle были
UNKNOWN. При SUPPRESSED вывод supervisor отправлял stdout/stderr в NUL.

**Почему workflow пропустил failure:** host terminal collector видел только
event JSONL и process exit; отдельный raw-free канал для child stdout/stderr
не собирался.

**Решение:** protocol supervisor временно перенаправляет stdout/stderr в
уникальные temp-файлы только при скрытом выводе. После завершения host
ограниченно читает каждый stream (до 2 MiB), запускает существующий
raw-free projector, сохраняет только process_output_diagnostic с enum
категориями и удаляет temp-файлы в finally. Oversize/read failure даёт только
capture status; содержимое, paths и provider messages не публикуются.
Visible-output mode не меняется. Эта телеметрия не объявляет run успешным и
не заменяет полный event receipt.

**Измеримый критерий:** fake child с пустым event file, nonzero exit и raw
HTTP 403 в stderr приводит к auth_or_forbidden в terminal outcome; stdout,
stderr, URL и token-marker отсутствуют во всех receipts; supervisor подтверждает
отдельный захват потоков. Реальную причину ранее завершившегося live child это
задним числом не устанавливает; нужен новый отдельно bounded запуск.

## D059 — Headless stream-json для protocol role lifecycle

Статус: принято 2026-09-27 для продолжения bounded Qwen E2E; решение D053 о
`--prompt-interactive` заменено. Решение не закреплено за версией Qwen CLI.

**Наблюдаемый failure mode:** live protocol launcher запускал Qwen с
`--prompt-interactive` при redirected stdin/stdout/stderr. Child завершился с
exit code `1`, event JSONL остался пустым, `Qwen debug/latest` не появился,
счётчики и role lifecycle не были доступны. Raw stderr прежнего запуска не
сохранили, поэтому конкретное сообщение CLI неизвестно.

**Почему workflow пропустил failure:** D053 проверял наличие
`--prompt-interactive` в capability/help contract, но не проверял, что launcher
предоставляет TTY для interactive mode. Capability marker прошёл, хотя реальный
launch работал с redirected streams; terminal collector в результате не получил
events, необходимые для host receipt и role projection.

**Решение:** protocol использует headless invocation
`--output-format stream-json --prompt "/finish-ticket ticket N"`. Capability
preflight, invocation registry, guard policy, bridge и тестовые fixtures
проверяют этот контракт и session ceilings. `type=result` с совпадающим
session_id, валидным subtype/optional `is_error` и без незавершённых tool calls
является допустимым финальным terminal event для обычного headless запуска;
supervisor применяет ту же схему при live tail. Для host-driven continuation
terminal event всё ещё должен наблюдаться после host stop, process tree должен
быть закрыт, event coverage полным, а budget-stop/checkpoint/loop gates остаются
без изменений. Raw stream временный и удаляется после raw-free projection.

Официальные Qwen CLI docs описывают [`--prompt` и `stream-json` как headless
invocation и JSONL event output](https://github.com/QwenLM/qwen-code-docs/blob/main/website/content/en/users/features/headless.md),
[`UserPromptExpansion` для skills/slash commands в headless runs](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/hooks.md)
и [named subagents в headless sessions](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/sub-agents.md).
Эти docs обосновывают выбор invocation shape, но не заменяют live проверку
установленного клиента.

**Минимальное изменение:** перейти с interactive `--prompt-interactive` на
headless `--prompt` + `stream-json` и добавить строгую terminal projection для
`type=result`; не менять auth/provider/model/sampling/reasoning, Qwen settings,
role profiles, session budgets, acceptance authority или внешние Qwen/Stepler
файлы.

**Критерий улучшения:** contract/capability/runtime tests принимают только
headless stream-json shape и завершают COMPLETE только при валидном финальном
result/session terminal event; отсутствующий/mismatched terminal, неизвестная
схема, незавершённый tool call и events после terminal остаются fail-closed.
Capability smoke выполняется без model request. Затем один связанный bounded
live pilot обязан показать host terminal receipt COMPLETE, raw-free role
projection COMPLETE в порядке Controller → Implementer → Reviewer → Verifier,
целевой test-only diff и успешный focused test. До этих live свидетельств E2E
не считается доказанным.

## D060 — Принимать headless `system/init` и уточнить auth-классификацию

Статус: принято 2026-09-27 для bounded E2E; без изменения budgets, acceptance
authority или настроек Qwen.

**Наблюдаемый failure mode:** обычный `qwen.cmd` headless вызов вернул exit `0`
и stream-json с одним assistant turn и финальным `result/success`, но начальный
`system` event имел subtype `init`. Runtime projector, принимавший только
`system/session_start`, вернул `SESSION_START_MISSING`; host evidence оказался
unusable, хотя live CLI вызов успешно завершился.

Связанный диагностический дефект: raw-text classifier трактовал любое
упоминание `token` или `api key` как `auth_or_forbidden`. Поэтому прежний receipt
`auth_or_forbidden` после отдельного exit `1` не доказывал ошибку credentials;
raw child stream не сохранялся, и точный error message восстановить нельзя.

**Почему workflow пропустил failure:** fixtures и collector были построены по
`session_start` примеру из документации и не включали `system/init`. Capability
`--help` подтверждал флаги, но не фактическую schema-форму событий. Ошибка
auth-classifier возникла из слишком широкого substring match.

**Решение:** terminal projector и supervisor принимают `system/init` и
`system/session_start` как bootstrap subtype только при непустом session id;
финальный `result` должен совпасть с распознанным session id, а
unknown/malformed bootstrap и events after terminal остаются fail-closed. Auth
classifier выдаёт `auth_or_forbidden` только для HTTP 401/403,
unauthorized/forbidden и явных phrases о failed/denied auth или
invalid/missing/expired/revoked key/token; обычное упоминание API key/token
классифицируется как `other`.

**Измеримый критерий:** regression tests показывают RED на `system/init` и на
generic token text, GREEN после изменения; legacy `session_start` и явный HTTP
403 продолжают проходить. Следующий bounded live pilot обязан дать COMPLETE
host evidence и role projection. Результат обычного CLI smoke не считается
role-lifecycle proof. Решение не привязано к версии Qwen CLI и не меняет
Credential Manager, settings, provider/auth, sampling, model или role profiles.

## D061 — Protocol наследует модельный output budget Qwen

Статус: принято 2026-09-27 для bounded E2E; не меняет Qwen settings,
provider/auth, model, sampling, reasoning или role profiles.

**Наблюдаемый failure mode:** live protocol pilot завершился с exit `1`,
`QWEN_COMMAND_FAILED`, `0` распознанных ходов и tool calls, без валидного
stream-json terminal; stdout присутствовал, stderr отсутствовал. Raw-free
classifier выдал `STRUCTURED_OUTPUT_MISSING`, но точная причина не доказана:
raw stream был удалён, а `~/.qwen/debug/latest` отсутствовал. Контрольный
короткий запрос через тот же Node shim и отдельная headless expansion личного
`/finish-ticket` без ticket завершились `result/success`; это исключает общий
CLI transport и простую skill-discovery проблему, но не локализует task-specific
сбой Controller/role cycle.

**Почему workflow мог усугубить failure:** protocol mode принудительно задавал
`QWEN_CODE_MAX_OUTPUT_TOKENS=8000`. Qwen документирует, что эта переменная
фиксирует per-response cap вместо model-native лимита и автоматического
повышения лимита при truncation ([официальная справка Qwen settings](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/settings.md)).
Это ограничение не измерялось как средство улучшения соблюдения skill, тогда
как владелец явно выбрал не оптимизировать Qwen по токенам.

**Решение:** protocol mode больше не устанавливает `QWEN_CODE_MAX_OUTPUT_TOKENS`
и не передаёт `OutputTokenLimit`; Qwen наследует output budget модели и
операторской конфигурации. Уже существующее process environment не перезаписывается.
Workflow ceilings `20 turns / 20 tool calls / 30m / depth 1` остаются
отдельными guardrails.

**Измеримый критерий:** mode contract возвращает `output_token_limit=null` и
пустой `process_environment`; production-shaped test подтверждает, что launcher
не переопределяет существующий output-token env. Следующий bounded pilot обязан
дать host terminal evidence и Controller → Implementer → Reviewer → Verifier
projection со статусом `COMPLETE`, а Verifier — пройти ровно focused test.
Это изменение и допуски остаются версионно-независимыми; E2E до этих свидетельств
не доказан.

## D062 — Игнорировать reasoning-блоки в raw-free terminal projection

Статус: принято 2026-09-27 для bounded E2E; без pinning версии Qwen и без
изменения настроек модели.

**Наблюдаемый failure mode:** protocol pilot `dddbe83f200643b7a762e793067689d8`
завершился exit `0`, но host projector выдал
`BLOCKED_CAPABILITY / QWEN_RUNTIME_EVIDENCE_UNSUPPORTED`; распознано `0` turns,
`0` tool calls, terminal receipt и role projection отсутствовали. Stream имел
7,185 bytes и был удалён после raw-free обработки. Причина не может быть
подтверждена содержимым именно этого stream. Однако локальная проверка показала
конкретный contract gap: event projectors отвергали все assistant content block
types кроме `text` и `tool_use`, тогда как Qwen stream-json может представлять
reasoning отдельным `thinking` block.

**Почему workflow пропустил failure:** regression fixtures покрывали обычный
assistant text/tool sequence и lifecycle roles, но не отдельный reasoning block.
Fail-closed обработка правильно остановила недопустимую схему, однако
совместимость формата reasoning content не была выражена в контракте.

**Решение:** terminal evidence, runtime adapter и host supervisor принимают
assistant `thinking` block только при строковом поле `thinking`, затем
отбрасывают его значение. Reasoning не участвует в receipt, role evidence,
public projection или fingerprints повторяющихся tool cycles. Неизвестные
block types и malformed thinking остаются fail-closed. Это форматный контракт,
не зависящий от номера релиза; configured reasoning и модель не меняются.

**Измеримый критерий:** regressions должны показать, что корректный thinking
block не блокирует complete terminal/role projection, его приватный текст не
попадает в evidence, изменяющийся reasoning не скрывает три идентичных tool
cycle fingerprints, а malformed/unknown blocks по-прежнему блокируются. Локально
прошли 55 тестов `test_qwen_terminal_evidence`,
`test_qwen_protocol_supervisor` и `test_qwen_runtime_adapter`. Это исправляет
обнаруженный compatibility gap, но не подтверждает, что предыдущий удалённый
stream содержал именно такой block, и не является live E2E proof. Следующий
разрешённый pilot остаётся единственной попыткой на этот scope и должен
подтвердить полный host receipt, Controller → Implementer → Reviewer → Verifier
projection и focused test.

## D063 — Проецировать raw-free CLI stage в terminal receipt

Статус: принято 2026-09-27 для продолжения bounded E2E; не меняет Qwen
settings/provider/auth/model/reasoning, budgets или version policy.

**Наблюдаемый failure mode:** live launch `8b9b8c9cd1b9445d83476cf882369e3a`
завершился за `1,195 ms` с `QWEN_COMMAND_FAILED`, counters `NOT_AVAILABLE`,
`outer_stage=RUNTIME_EVIDENCE_PARSED`, `supervisor_stage=NOT_REACHED`,
`process_state=NOT_STARTED`, `event_file_state=NOT_OBSERVED`. Версия 2 receipt
не показывала, на какой CLI pre-launch фазе возникла ошибка.

**Локализация:** Credential Manager entry оказался доступен, protocol argv
совпал с registry (`12/12`), текущий Node shim распознался, supervisor
загрузился, а один model-free `--version` через тот же supervisor завершился
exit `0`. Эти независимые проверки сужают место до полного CLI bridge path, но
не устанавливают точную фазу/exception в неуспешном launch; сообщение исключения
не сохранялось и секреты/raw streams не читались.

**Почему workflow пропустил failure:** CLI compatibility consumer сводил любые
pre-launch исключения к `QWEN_COMMAND_UNAVAILABLE`, а terminal receipt
сохранял только outer/supervisor stages. При `NOT_REACHED` эти данные не
различали credential lookup, capture setup и supervisor dispatch.

**Решение:** CLI bridge выставляет конечный enum `cli_stage`/`cli_failure_stage`;
outer writer валидирует его и сохраняет в `QWEN_TERMINAL_OUTCOME` v3 как
`launch_diagnostic.cli_stage` (nested schema version 2). Разрешены только
`ARGUMENT_CONTRACT`, `ARGUMENTS_VALIDATED`, `CAPTURE_SETUP`, `CAPTURE_READY`,
`CREDENTIAL_HELPER_LOAD`, `CREDENTIAL_LOOKUP`, `CREDENTIAL_READY`, `SUPERVISOR_LOAD`, `SUPERVISOR_READY`,
`SUPERVISOR_DISPATCH`, `SUPERVISOR_RETURNED`, `RUNTIME_PROJECTION`,
`RUNTIME_PROJECTED`, `NOT_REACHED`. Exception text, credential identity/value,
paths, URLs, prompts и output не попадают в receipt.

**Измеримый критерий:** model-free regression с заведомо отсутствующим
Credential Manager target выдаёт только `cli_failure_stage=CREDENTIAL_LOOKUP`;
nonzero child regression сохраняет `cli_stage=RUNTIME_PROJECTED`. Ни один путь
не запускает модель. После локального полного gate следующий live protocol pilot
должен показать точную raw-free CLI stage при pre-launch failure либо завершить
полный host/role/test lifecycle. Ticket 314 и E2E до такого evidence остаются
незакрытыми. Решение не pin-ит версию Qwen.

## D064 — Изолировать protocol CLI consumer отдельным PowerShell host

Статус: принято 2026-09-27 как process-boundary mitigation; причина ранних
`CREDENTIAL_LOOKUP` receipts полностью не доказана. Qwen version policy и
настройки не меняются.

**Наблюдаемый failure mode:** live receipts `fa6a16fd15ca4211b8041e0174ec1d2e`,
`18c97522de9c44f0be4732dfcb1228a3` и `e8795a4069634509b20eb5b166ce8dda`
заканчивались на `cli_stage=CREDENTIAL_LOOKUP`, до supervisor/process start.
Ранее отдельный `pwsh -File` с существующим target проходил lookup, тогда как
старый top-level launch — нет. При повторной model-free проверке в свежем
`pwsh` и in-process, и отдельный `-File` consumer достигли ожидаемого
`RUNTIME_PROJECTED / COMMAND_RESOLUTION_FAILED`; значит, общий same-runspace
сбой не воспроизводится детерминированно.

**Почему локализация была неполной:** прежние receipts показывали фазу, но
не exception; direct-consumer probes не включали точный state полного
top-level launcher. Поэтому утверждать, что Credential Manager или конкретный
PowerShell host был исходной причиной, нельзя.

**Решение:** protocol launcher запускает CLI compatibility consumer отдельным
экземпляром текущего PowerShell executable с `-NoLogo -NoProfile -File`. Это
изолирует native Credential Manager read от ambient runspace state и даёт
raw-free JSON boundary; API key остаётся только в process environment
consumer/Qwen и не передаётся аргументом. Null optional packet не передаётся.

**Измеримый критерий:** opt-in integration test
`test_protocol_injects_process_scoped_credential_manager_key` читает уже
существующий Credential Manager target и запускает только fake Node Qwen shim.
Он прошёл: fake child наблюдал только факт непустого key, исходное process
environment восстановлено, projector увидел тестовый sentinel, token отсутствует
в stdout/stderr. Это доказывает текущий local host/credential bridge без model
request, но не доказывает первопричину прежних live receipts и не является E2E
Qwen proof.

## D065 — Ограничить continuation packet платформенным argv бюджетом

Статус: принято 2026-09-27; это предел передачи данных на Windows, не модельный
token/session budget и не Qwen version gate.

**Наблюдаемый failure mode:** red-capable fake-process regression с прежним
максимумом `32,768` символов падал при передаче packet строкой через новый
PowerShell child boundary: `NOT_REACHED / NOT_STARTED`. После перехода на temp-file
transport consumer проходил, но supervisor всё ещё правильно отвергал итоговую
Qwen command line около `32,000` символов до старта процесса.

**Решение:** raw continuation содержимое передаётся CLI consumer только через
короткий путь к UTF-8 temp-файлу; файл удаляется при pre-dispatch failure и после
возврата consumer. Максимум continuation context теперь `14,000 UTF-8 bytes` в
policy adapter, launcher и consumer. Этот запас учитывает escaping prompt argv и
фиксированные CLI arguments; supervisor сохраняет независимую окончательную
проверку длины command line и fail-closed отказ при фактическом превышении.

**Измеримый критерий:** regression принимает и доставляет ровно `14,000` ASCII
байт через полный fake host/continuation path, проверяет exact packet tail и
отсутствие оставшихся `tmp*.tmp`; adapter блокирует `14,001` байт до role
dispatch. Ни один тест не запускает модель. Canonical `/finish-ticket` argv не
меняется, exact-version policy не добавляется.

## D066 — Сохранить безопасное partial Qwen evidence и ограничить pilot budget

Статус: принято 2026-09-27 для одного disposable Ticket 314 pilot; не pin-ит
версию Qwen и не меняет settings, auth/provider, reasoning, sampling, role
profile или acceptance authority.

**Наблюдаемый failure mode:** предыдущий live launch
`f923fa88f3c84434a8d517643467cf33` завершился `QWEN_COMMAND_FAILED`, exit `1`.
Host receipt v3 сохранил `event_file_state=PRESENT`, но `turn_count=0`,
`tool_call_count=0`, `event_coverage=UNKNOWN`, `session_ended=false` и не имел
typed event/role projection. Отдельные Qwen usage metadata показали один вызов
личного `/finish-ticket`, 20 tool calls (19 success, 1 failed) и отсутствие
Agent dispatch; это не host receipt и не доказывает, что именно tool limit
вызвал отказ. Raw Qwen debug/latest и точная terminal cause для этого запуска
недоступны.

**Почему workflow пропустил failure:** terminal projector fail-closed блокировал
неполный/malformed JSONL, но не сохранял безопасный prefix observation.
Controller видел process failure, однако не мог по host evidence оценить,
дошёл ли запуск до role dispatch и сколько typed tool results было завершено.
Обычный budget `20 tool calls` также исчерпался по отдельным usage metadata до
подтверждённого role lifecycle; причинная связь с terminal failure неизвестна.

**Решение:** strict terminal/lifecycle projection остаётся fail-closed. Отдельный
диагностический projection считает только полностью завершённые и валидные
JSONL records перед первым malformed/truncated record; поля ограничены counts
events/assistant turns/tool dispatch/results/errors/Agent dispatches и boolean
`terminal_result_seen`. Raw records, tool names/inputs/results, paths и prompts
не сохраняются. `QWEN_TERMINAL_OUTCOME` повышен до v4. Эти partial counters не
являются terminal proof, не открывают continuation или acceptance.

Для одной свежей bounded попытки standard `20/20/30m/depth1` сохраняется, но
owner-authorized disposable test-only packet получает opt-in `pilot-expanded`
profile с `20 turns / 40 tool calls / 30m / depth 1`. Profile требует
`qwen-protocol-pilot-ticket.md`, `.scratch` checkout с `.git` и точные
test-only markers; scope gate действует независимо в top-level launcher и CLI
consumer до Qwen dispatch. Guard receipt v2 связывает `budget_profile` и
effective limits. User setting `model.maxToolCallsPerTurn=20` не меняется;
обычный protocol остаётся на 20.

**Измеримый критерий:** focused regressions проверяют raw-free diagnostics для
truncated и malformed tails, полную передачу этих counters в host receipt v4,
40-call argv только при точном disposable scope и отказ дочернего CLI consumer
обойти тот же scope gate; standard argv/limits остаются 20. После локального
полного gate разрешён ровно один live Qwen protocol pilot в свежем disposable
checkout. PASS требует COMPLETE host terminal evidence, завершённую цепочку
fresh Implementer → Reviewer → Verifier (Controller остаётся владельцем
оркестрации), test-only patch одного теста не более 20 изменённых строк и
успешный focused test. При любом guard/evidence/protocol failure запуск
останавливается без retry; raw-free receipt и counters фиксируются, E2E остаётся
недоказанным.

**Результат разрешённой попытки 2026-09-27:** capability smoke прошёл (`7/7`
required markers), полный local suite — `265` tests, `1` skipped. Новый pilot
`bdcc0068e37a4eebbe8090a38919a629` не достиг Qwen child: terminal receipt v4
зафиксировал `QWEN_COMMAND_FAILED`, `cli_stage=CREDENTIAL_LOOKUP`,
`supervisor_stage=NOT_REACHED`, `process_state=NOT_STARTED`, duration `1,867 ms`;
turn/tool counters недоступны, event file отсутствовал. Guard receipt v2
подтвердил корректный scoped budget `20/40/30m/depth1`, skill preflight и
loop detection. Disposable test и staged index остались неизменны. Это failure
Credential Manager lookup path, но не evidence об ошибочном/просроченном API
key или HTTP/Qwen response. В рамках D066 повтор не выполняется; E2E proof не
получен. Следующая безопасная рекомендация — отдельная model-free raw-free
диагностика CredRead в том же child host, без печати секрета, и отдельное
разрешение владельца для будущего live pilot.

## D067 — Сохранять точную raw-free причину runtime projection block

Статус: реализовано и проверено локально 2026-09-27; последующий bounded
pilot остановился до запуска Qwen child на `CREDENTIAL_LOOKUP` (см. D068).

**Наблюдаемый failure mode:** terminal projector может вернуть точную raw-free
причину неполного или недопустимого event lifecycle — например,
`TOOL_RESULT_MISSING`. Top-level launcher при любом результате, отличном от
`COMPLETE`, записывал только общий `QWEN_RUNTIME_EVIDENCE_UNSUPPORTED`, из-за
чего расследование не различало причины, уже вычисленные host projector.

**Почему workflow пропустил failure:** tests покрывали отдельные projection
категории и общий parent receipt, но не проводили blocked projector reason через
реальный fake-process → CLI consumer → top-level receipt путь.

**Решение:** сохранить общий status/reason `BLOCKED_CAPABILITY` /
`QWEN_RUNTIME_EVIDENCE_UNSUPPORTED` и добавить отдельное поле
`runtime_projection_reason`. Оно принимает только фиксированные raw-free reason
codes terminal projector; сырые event lines, tool inputs/results, paths,
prompts и exception text не сохраняются. Версия parent receipt повышена с v4 до
v5. Поле диагностическое и не даёт role dispatch, continuation или acceptance
authority.

**Измеримый критерий:** fake Qwen выдаёт валидное начало session и tool dispatch
без соответствующего result; end-to-end fake launcher остаётся blocked, а
parent output и receipt содержат `runtime_projection_reason=TOOL_RESULT_MISSING`
и counters `1 dispatch / 0 results`. Маркеры session/tool/path из JSONL не
появляются в output или receipt. Это подтверждено focused regression;
27.09.2026 также прошли focused runtime-guard suite (`46` tests, `1` skipped),
полный suite (`266` tests, `1` skipped) и обе plugin validation команды.

**Ограничение:** D067 подтверждает потерю классификации на host→receipt seam, но
не восстанавливает удалённый JSONL последнего live запуска и не устанавливает,
почему Qwen не вызвал Implementer. E2E Ticket 314 остаётся недоказанным; raw
capture остаётся выключенным.

## D068 — Проверять Windows identity до Qwen Credential Manager lookup

Статус: причина последнего `CREDENTIAL_LOOKUP` локализована на стороне
исполняющего процесса; owner-context probe прошёл, свежий pilot clone подготовлен
для запуска владельцем.

**Наблюдаемый failure mode:** bounded pilot
`c14a89d7b86e4cf9ae39b3678cb3f209` остановился до запуска Qwen child на
`cli_stage=CREDENTIAL_LOOKUP`; counters были `NOT_AVAILABLE`, event stream не
наблюдался.

**Диагностика:** тот же `qwen_credential.ps1` в отдельном `pwsh 7.5.5 x64`
вернул `Win32Exception` code `1168` (`ERROR_NOT_FOUND`). При этом профиль
указывал на `C:\Users\alexey.andreev`, но Windows identity процесса не
совпадала с `alexey.andreev`; raw-free `cmdkey /list` inventory не показал
ожидаемый Generic Credential target. Вывод списка credentials и secret не
сохранялись.

**Вывод:** текущий agent host не имеет target в Credential Manager своей
security identity, хотя путь `USERPROFILE` указывает на каталог пользователя.
Это объясняет отказ до model request, но не доказывает отсутствие или
невалидность credential в интерактивном профиле владельца.

**Решение и критерий следующего шага:** не обходить границу identity копированием
секрета в environment или другую учётную запись. Владелец подтвердил
`CREDENTIAL_PRESENT` в интерактивном PowerShell без вывода значения. Новый
bounded pilot запускается из этого owner-controlled host в отдельном свежем
clone; запуск из agent host остаётся запрещённым, пока его Windows identity
отличается. Это не меняет provider, настройки Qwen или версию CLI и пока не
является E2E-доказательством.

## D069 — Остановить Ticket 25 как BLOCKED_EVIDENCE_SOURCE без угадывания event-схемы

Статус: принято 2026-09-28; owner подтвердил выбор.

**Наблюдаемый failure mode:** terminal projection live запуска
`46d14fc6e82c47118a3f1d1a96b549de` вернула `EVENT_SCHEMA_UNKNOWN` при
`event_coverage=UNKNOWN`, хотя процесс завершился exit `0` и terminal result
присутствовал. Ticket 25 требовал сначала проверить доступность trace этого
запуска.

**Диагностика:** read-only поиск launch id по `.scratch`, `.tmp`, `.worktrees`,
`%TEMP%`, `AppData\Local\Temp`, `~\.qwen\tmp` и содержимому репозитория не нашёл
event-файла или receipts запуска; сырой JSONL удаляется после raw-free
projection, поэтому trace этого запуска в owner-controlled окружении недоступен.

**Решение:** не угадывать native Qwen JSONL dialect и не повторять native
protocol launch ради получения trace; зафиксировать Ticket 25 как
`BLOCKED_EVIDENCE_SOURCE`. Следующий диагностический шаг (например, отдельный
bounded launch с raw capture или иной evidence source) требует отдельного
решения владельца. Fail-closed `EVENT_SCHEMA_UNKNOWN` не ослаблялся; версии Qwen
allow-list не добавлялся.

**Измеримый критерий:** `tickets.md` Ticket 25 содержит raw-free статус
`BLOCKED_EVIDENCE_SOURCE` с перечнем проверенных локаций и датой; ни один
fixture или тест не содержит угаданную схему; live protocol launch в рамках
тикета не выполнялся.

**Ограничение:** D069 не устанавливает фактическую event-схему запуска
`46d14fc6…` и не открывает Ticket 25 к реализации; Ticket 26 опирается на
независимый SEAM_FEASIBILITY, а не на восстановленный trace.

## D070 — Progress checkpoint для role-agents на шести read-only вызовах

Статус: принято 2026-09-28; локальная реализация Ticket 26.

**Наблюдаемый failure mode:** выборка владельца из 22 role-agent запусков
Ticket 314: 11 `LOOP_DETECTED`, 6 silent failed, 1 отмена, 4 completed (один
completed — fork с нулём tool calls, т.е. продуктивно завершились три). Среди
17 loop/silent failures у 16 было не менее 10 read calls; все completed — не
более шести. Это correlation, не причинность: выборка мала, содержит fork/no-op
и отмену.

**Почему workflow пропустил failure:** существующие gates останавливают
только уже состоявшуюся петлю (`exact_tool_interaction_cycle_v1`) или
исчерпание budget; длинная непродуктивная read-активность незавершённой роли
не имела промежуточной контрольной точки.

**Решение:** при шести cumulative read-only tool calls незавершённой fresh
named роли Controller требует короткий progress checkpoint (новые проверенные
факты + один конкретный следующий шаг, task/scope неизменен) до следующего
действия. Шесть — checkpoint threshold, не hard cap, не consecutive count,
без сброса counters. Реализация: pure `scripts/qwen_role_progress_checkpoint.py`
(classify/projection/decision, raw-free schema
`proofloop.qwen-role-progress.v1`) и adapter flag `--project-role-progress`;
петли остаются немедленным terminal stop без исключений для mixed
read/write/shell; silent failure — отдельный outcome без автоматического
retry; fork с нулём вызовов не продуктивная роль. Обычные ceilings
`20/20/30m/depth 1`, `pilot-expanded`, Qwen settings/role profile не менялись.

**SEAM_FEASIBILITY ограничение:** parent stream-json наблюдает только
dispatch/result пар Controller → роль; вложенные tool calls роли в parent
потоке не видны. Projection атрибутирует counters только наблюдаемым
вызовам, остальные — conservative unattributed tally без checkpoint
authority. Технический gate не заменён prompt-only обещанием: decision
returns BLOCK без валидного checkpoint. Ровный seam вложенной наблюдаемости
— отдельный будущий design gap, если потребуется.

**Измеримый критерий:** `tests/test_qwen_role_progress_checkpoint.py` —
при 0–5 reads ALLOW без checkpoint; шестой read незавершённой роли —
`PROGRESS_CHECKPOINT_REQUIRED`; валидный checkpoint — ALLOW без сброса
counters; отсутствие прогресса/scope drift — BLOCK; fork/resume/unknown —
unclassified; malformed stream — fail-closed без raw echo. Локально:
focused `20/20` и adapter suite `30/30` PASS.

**Ограничение:** live-валидация порога не выполнялась и требует отдельного
разрешения; correlation из выборки Ticket 314 не пересчитывается как общее
качество Qwen.
