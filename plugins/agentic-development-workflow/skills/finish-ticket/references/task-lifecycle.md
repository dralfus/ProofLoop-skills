# Протокол выполнения одного ticket

Версия workflow: `1.11`

Это единственный обязательный runtime-протокол skill `finish-ticket`.
Копии этого файла в проекте не требуются.

## Содержание

- Роли и полномочия
- PREFLIGHT_REPORT
- Design gate
- Выбор модели и effort
- Budget и context gate
- Основной цикл
- Findings и repair-loop
- Возобновление
- Контракты отчётов
- Token usage report
- Финальное evidence

## Runtime adapter contract

Runtime adapter предоставляет Controller только фактические возможности
текущего host. До preflight он выполняет capability preflight и сообщает
доступность всех обязательных возможностей: model identity, role dispatch and
continuation, tool policy и observed usage. `model identity` включает точный
provider/model ID, capability tier (`efficient`, `standard` или `frontier`) и
поддерживаемый effort. Для Codex inventory имеет exact provenance
`provider: openai` и `source: codex-runtime`; любой другой или отсутствующий
marker считается недоверенным. `observed usage` — только counters,
которые adapter реально получил от provider или execution trace.

Если хотя бы одна обязательная возможность недоступна, Controller возвращает
`BLOCKED_CAPABILITY` до первого role-agent launch. Нельзя заменять её fallback,
самопроверкой Controller или новым role behavior. В report перечисляются
отсутствующая capability и provider evidence.

`role dispatch and continuation` означает, что Controller может создать
разрешённую роль и отправить scoped follow-up исходному Implementer. `tool
policy` перечисляет доступные каждой роли tool classes и запрещает adapter
выдавать недоступный tool как доступный.

### Codex adaptive profile

Для Codex adapter сначала проверяет фактический inventory, затем выбирает
минимально достаточные tier и effort по risk policy ниже. Для запроса
`frontier` он детерминированно пробует `frontier`, затем `standard`, затем
`efficient`; для `standard` — `standard`, затем `efficient`; для `efficient`
только `efficient`. Каждый кандидат обязан поддерживать требуемый effort; при
нескольких совместимых IDs выбирается лексикографически первый. В routing
adapter записывает requested/selected tier, `degraded` и reason. Его numeric
policy не меняется: ordinary ticket использует `role-agent 3/4` как лимиты
ordinary/critical, `full suite 1` и `compaction 0/1`; frontier остаётся `0/1`
без нового разрешения. Adapter передаёт выбранную model identity в preflight и
observed usage в closure report.

Внешняя policy fixture принимает declaration с четырьмя capabilities и
проверяемым inventory model IDs/tiers/efforts. При полном Codex declaration
она возвращает `CODEX_PROFILE` с Controller/Implementer/Reviewer/Verifier
routing и этими budget. При неизвестном/недоверенном inventory (включая
отсутствующий exact marker `codex-runtime`), `false` либо отсутствующей
capability или отсутствии совместимой пары tier+effort результат — только
`BLOCKED_CAPABILITY`; model-name guessing, fallback и self-review не
допускаются.

### Qwen Code v0.22.2 single-model profile (Qwen single-model profile)

Qwen выбирается не по имени модели, а только из trusted runtime declaration:
`runtime.provider: qwen`, `runtime.product: qwen-code` и
`runtime.version: 0.22.2`. Документированная fixture schema дополнительно
содержит `configured_model.id`, равный `active_model.id`,
`role_model_identity_lock`, `fresh_named_subagent`,
`implementer_continuation`, `reviewer_policy` и `verification_command`.
Неполная или недоверенная декларация возвращает
`BLOCKED_CAPABILITY` до dispatch.

Boolean capabilities `role_model_identity_lock`, `fresh_named_subagent` и
`implementer_continuation` принимают только literal `true`; строка, число или
другое truthy value является malformed capability. `verification_command`
должна быть непустой строкой команды либо object ровно вида
`{"argv": ["<non-empty argument>", "..."]}`. Boolean, пустая строка, пустой
`argv`, нестроковый аргумент или дополнительные поля не являются executable
verification command и дают `BLOCKED_CAPABILITY`.

`reviewer_policy` валидна только при `fresh_named: true`, `fork: false`,
`write: false` и read-only tool classes `read`/`verify`. Поэтому Reviewer
всегда создаётся как fresh named subagent, является read-only Reviewer,
не наследует context fork и не получает write-capable tools. Controller и все
role-agents сохраняют одну
проверенную configured model identity. Успешная fixture возвращает observed
configuration и `usage: AVAILABLE|NOT_AVAILABLE`; отсутствие provider usage
не заменяется оценкой токенов.

До dispatch adapter также подтверждает executable verification command.

Этот профиль использует `repair_policy: QWEN_CONVERGENT`. Qwen delivery
поставляется нативным extension из корня repository: `qwen-extension.json`
публикует тот же `finish-ticket` skill и `finish-ticket-controller` agent.
Extension ссылается на этот единственный файл lifecycle, не дублирует его;
короткий запуск — `/finish-ticket ticket <ID или путь>`. Codex adaptive profile
и его numeric budget остаются без изменений.

### Qwen convergent repair policy

У Qwen нет числового лимита repair-раундов. Его заменяет append-only ledger с
фиксированной схемой событий и непрерывным `sequence`:

- `baseline` начинается с `sequence: 1` и содержит `fixed_point` и полный
  список `open_findings`;
- `local_attempt` содержит один открытый finding, воспроизводимый `RED`,
  hypothesis и `GREEN`; он не меняет ticket status и не закрывает finding;
- `repair_candidate` содержит `diff` с `scope_delta`, точные
  `attempt_sequences` уже записанных local attempts, `normalized_root_cause`
  и exact runtime/model/usage trace; `normalized_root_cause` должен точно
  совпадать с нормализацией root cause всех referenced attempts, а `model.id`
  каждого historical candidate — с configured identity текущего Qwen profile;
- `review_verdict` ссылается на repair candidate, содержит fresh named
  read-only Reviewer без fork/write, `SPEC`, `CODE_QUALITY`, regression/scope
  flags и список closed finding fingerprints;
- `terminal` содержит terminal `status` и непустой `reason`.

Запись никогда не перезаписывает предыдущую. Допустимы только переходы
`baseline|review_verdict(CONTINUE) -> local_attempt+ -> repair_candidate ->
review_verdict`; non-`CONTINUE` verdict должен сразу завершаться `terminal`, а
запись после terminal невалидна. Controller проверяет *всю* историю перед
новым кандидатом: каждый прежний `CONTINUE` обязан иметь complete
attempt/candidate/review evidence на любом outcome path, включая terminal.
Каждый policy stop `BLOCKED` или `BLOCKED_FOR_DESIGN` после valid baseline
append-only добавляет `terminal` с непустой reason, в том числе при неполном
repair evidence.
Closed findings должны быть уникальным
подмножеством current open findings и findings referenced attempts; повторное
или дополнительное закрытие без repair evidence не является progress.

Fresh Reviewer возвращает `SPEC`, `CODE_QUALITY`, closed finding fingerprints,
regression accepted criteria и unapproved scope expansion. Controller разрешает
`CONTINUE` только при `SPEC: PASS`, `CODE_QUALITY: PASS`, отсутствии
регрессии/неутверждённого scope и closure известного open finding. Сравнение
root cause нормализует register, пробелы, `_` и `-`; это не даёт повторной
причине пройти как новой из-за spelling. В этом случае Verifier по общему
lifecycle запускается только после static PASS.

Автоматический loop немедленно останавливается: `NEW_REQUIREMENT`,
`DESIGN_GAP` и unapproved scope expansion дают `BLOCKED_FOR_DESIGN`;
regression — `BLOCKED`; повтор пары finding type + normalized root cause без
нового reproducible RED даёт `BLOCKED` с
`REPEATED_ROOT_CAUSE_WITHOUT_NEW_RED`. Отсутствующий RED, fresh review или
закрытый finding также не является progress и не разрешает continuation.

## Роли и полномочия

- **Controller** определяет baseline, риск, scope, модели, health gates,
  budget/context gates, adjudication и итоговый статус.
- **Implementer** изменяет код и targeted-тесты; возвращает `IMPLEMENTED`,
  `BLOCKED` или `NEEDS_CLARIFICATION`.
- **Reviewer** не изменяет файлы и независимо возвращает `SPEC` и
  `CODE_QUALITY`.
- **Verifier** после статического PASS выполняет acceptance-проверки и
  возвращает `ACCEPTED` или `REJECTED`.

Только Controller создаёт subagents и присваивает `DONE`,
`BLOCKED_FOR_DESIGN` или `BLOCKED`. Role-agents не создают agents. В каждый
момент работает не более одного writer.

## PREFLIGHT_REPORT

До первого spawn Controller обязан:

1. Прочитать проектные инструкции, ticket, спецификацию и checkpoint.
2. Самостоятельно определить корень проекта, тип репозитория, ветку, commit и
   fixed point. Если Git отсутствует, показать bounded snapshot manifest
   `относительный путь -> SHA256` только для ticket/spec и файлов ожидаемого
   scope. Выводить полные 64 hex-символа каждого SHA256. Не сканировать
   vendor/generated/cache каталоги; предел — 200 файлов.
   Если scope ещё неизвестен или превышает предел, зафиксировать hashes входных
   документов и `BASELINE_INCOMPLETE`, затем остановиться до уточнения scope.
3. Связать каждый acceptance criterion с наблюдаемым evidence.
4. Для каждого критерия заполнить `SEAM_FEASIBILITY`: production entry point,
   существующий или явно утверждённый test seam, red-capable команда и граница
   ownership. Если критерий добавляет или меняет injectable boundary, также
   перечислить production-shaped consumer и его compatibility command.
   Критерий без применимых полей не готов к implementation.
5. Отделить implementation requirement от `NEW_REQUIREMENT` и `DESIGN_GAP`.
6. Объявить planned-модели/effort следующих допустимых ролей и причины выбора,
   даже если design gate пока запрещает их spawn.
7. Объявить ожидаемые компоненты, верхнюю границу изменяемых файлов и
   запрещённые соседние подсистемы.
8. Объявить targeted RED/GREEN loop, команды review/verification и stop gates.
9. Зафиксировать budget: тип ticket, максимум и текущий счётчик role-agent
   запусков, frontier, full suite и compaction; также правило эскалации модели.
10. При возобновлении сопоставить checkpoint с текущим partial diff и отметить
   устаревшее evidence.

## User-facing PREFLIGHT_REPORT

Controller сначала выполняет все десять preflight-проверок, но пользователю
выводит только decision receipt. Детали baseline, acceptance mapping, scope,
`SEAM_FEASIBILITY` и targeted commands сохраняются в рабочем preflight record,
`IMPLEMENTATION_PACKET` и final evidence; не печатать их в обычном отчёте.

Формат: заголовок `PREFLIGHT_REPORT`, затем одна Markdown-таблица. В ячейках —
короткие фразы, без повторения ticket/spec и без многострочных
escape-последовательностей.

| Блок | Значение |
|---|---|
| Ticket / spec | `<пути или идентификаторы>` |
| Risk | `<сложность; факторы>` |
| Routing | `<следующая роль; requested/selected tier; effort; причина>` |
| Budget | `<class; role-agent N/M; frontier N/M; suite N/1; compaction N/M>` |
| Stop gates / design gaps | `<условия; нет или список>` |
| Next action | `<spawn, confirmation или BLOCKED_FOR_DESIGN>` |

Если есть `DESIGN_GAP`, `BASELINE_INCOMPLETE` или другой stop gate, после
таблицы вывести только одну строку `Blocking detail: <criterion/condition; что
нужно для продолжения>`. Не выводить полную criterion table, если она не
блокирует решение пользователя.

Для `critical`, resumed/partial, design gap или `BASELINE_INCOMPLETE` Controller
останавливается и запрашивает подтверждение до первого agent spawn. Для
ordinary ticket отчёт является объявленным планом: Controller продолжает в
указанном бюджете. До первого Implementer production-код и тесты не изменяются.

## Design gate

До implementation присвоить `BLOCKED_FOR_DESIGN`, если требуется определить:

- нового state owner или новую подсистему;
- отсутствующую cancellation/timeout semantics;
- поведение уже начатого необратимого side effect;
- неизвестную security boundary;
- новый production seam без доказуемого test seam.
- критерий требует захватить, изменить или восстановить external state, но
  operation owner либо injectable boundary не определены.
- ticket предполагает существующий компонент, но он отсутствует, а создание и
  структура нового компонента не утверждены спецификацией.

Сначала зафиксировать отдельное design-решение. Не проектировать эти решения
внутри repair-loop.

## Выбор модели и effort

Сначала проверить фактический verified inventory текущего multi-agent
инструмента. Policy зависит только от capability tier, не от family name:
Luna, Terra и Sol — лишь примеры значений текущего registry. Неизвестный или
недоверенный inventory блокирует lifecycle, а не разрешает planned model ID.

| Работа | Requested tier | Effort |
|---|---|---:|
| Механическая реализация 1–2 файлов | efficient | high |
| Обычная реализация или Controller | standard | medium |
| Сложная или критичная реализация | standard | high |
| Обычный Reviewer | standard | medium |
| Критичный Reviewer | standard | high |
| Deterministic Verifier | efficient | medium |
| Интерпретирующий Verifier | standard | medium |
| Design-adjudication или доказанный недостаток standard tier | frontier | high |

Ticket критичен при сочетании минимум двух факторов: security/privacy;
concurrency/cancellation; OS/native/UIA/COM/driver/installer; необратимый side
effect; новый architecture seam/state owner; труднообратимое изменение данных
или Git history.

Frontier `high` не является default для critical ticket. Перед его выбором Controller
записывает конкретный недостаток standard tier: неразрешённый finding, невозможность
обосновать design или подтверждённый failure targeted loop. Больше одного frontier
на ticket требует явного разрешения пользователя. `xhigh` разрешён только
после измеримого недостатка `high`; `max` и `ultra` не входят в стандартный
процесс.

Перед каждым spawn Controller публикует:

```text
Раунд: <номер>
Роль: <роль>
Budget: <role-agent N/M; frontier N/M; full suite N/1; compaction N/M>
Сложность: <простая | обычная | сложная | критичная>
Риск: <низкий | средний | высокий | критичный>
Tier, model ID и effort: <значения из verified inventory>
Причина: <почему это минимально достаточная конфигурация>
Эскалация: <нет или предыдущая -> новая с причиной>
```

## Budget и context gate

| Класс ticket | Role-agent запуска | Frontier без нового разрешения | Full suite | Compaction |
|---|---:|---:|---:|---:|
| Ordinary | 3 | 0 | 1 | 0 |
| Critical | 4 | 1 | 1 | 1 |

Запуск означает создание нового role-agent, а не follow-up уже созданному
Implementer. Для первого прохода critical ticket использует Implementer,
Reviewer и Verifier. Если Reviewer вернул FAIL, Verifier ещё не запускался:
допустимая последовательность одного scoped fix — Implementer (follow-up),
scoped re-review, затем Verifier. Так total остаётся равен четырём launches;
Controller не резервирует одновременно отдельные места и для re-review, и для
повторного Verifier.

Перед каждым spawn Controller показывает текущий счётчик. При достижении
лимита он сохраняет checkpoint и возвращает `BUDGET_GATE`; новый spawn возможен
только после отдельного разрешения пользователя с обновлённым budget. Fix rounds
3–5 также требуют отдельного разрешения каждый; пять остаётся абсолютным
terminal limit.

Controller ждёт role-agent event-driven и не опрашивает статус периодически.
Допустим один follow-up для уточнения отчёта; затем используется verdict либо
stop gate. Compaction перед дорогой ролью требует компактного checkpoint и
свежего Controller, который заново сверяет baseline, diff и counters.

Full suite сохраняется отдельной evidence-записью: command, started/finished,
exit code, pass/fail/skipped counts и commit/diff. Если после успешного suite
production diff не менялся, повтор перед commit не выполняется.

## Основной цикл

1. Создать одного Implementer с `IMPLEMENTATION_PACKET`: baseline, только
   применимые acceptance criteria, `SEAM_FEASIBILITY`, включая production
   consumer/compatibility command для изменённой injectable boundary, разрешённый scope,
   targeted RED/GREEN commands, stop gates и открытые findings. Это единственный
   handoff; transcript Controller, неприменимые части spec и повторное чтение
   неизменённых входных документов не передаются. Дополнительный файл допустим
   лишь как прямая dependency указанного production entry point.
   Для implementation использовать ровно один процессный путь: TDD для новой
   функции либо диагностику для уже наблюдаемого defect; не загружать оба без
   подтверждённой необходимости.
2. Implementer создаёт или уточняет red-capable targeted test, наблюдает RED,
   реализует минимальное изменение и подтверждает GREEN. Full suite не
   запускает без специальной проектной необходимости.
3. Создать одного свежего Reviewer. Он проверяет fixed-point diff по осям
   `SPEC` и `CODE_QUALITY`, включая compatibility evidence каждого
   production-shaped consumer изменённой injectable boundary. Evidence только
   через fake/injected seam без такого consumer даёт `REGRESSION` и `FAIL`.
   Reviewer не изменяет файлы, не создаёт agents и не запускает full suite.
4. При любом `FAIL` не запускать Verifier. Классифицировать findings и провести
   adjudication.
5. Только после `SPEC: PASS` и `CODE_QUALITY: PASS` создать Verifier.
6. Verifier выполняет targeted acceptance, один обычный full suite при
   необходимости и обязательные live-проверки. Отсутствующую проверку отмечает
   `NOT_RUN` с причиной.
7. При `ACCEPTED` Controller сохраняет evidence и присваивает `DONE`.
8. При `REJECTED` Controller публикует `FAILURE_SUMMARY`; разрешён только
   scoped fix подтверждённого требования.

## Findings и repair-loop

Каждый finding получает тип `SPEC_VIOLATION`, `REGRESSION`,
`QUALITY_BLOCKER`, `NEW_REQUIREMENT` или `DESIGN_GAP`, а также нормализованную
корневую причину.

- `NEW_REQUIREMENT` требует решения владельца требований или нового ticket.
- `DESIGN_GAP` немедленно даёт `BLOCKED_FOR_DESIGN`.
- Fix 1 выполняет исходный Implementer одним follow-up в уже созданной роли;
  затем запускается один scoped re-review finding и связанных regressions.
- Второе появление пары «тип finding + корневая причина» немедленно даёт
  `BLOCKED_FOR_DESIGN`.
- После первого scoped fix ordinary ticket исчерпывает default budget и
  требует checkpoint с явным разрешением пользователя. Critical ticket может
  завершить один re-review и Verifier в зарезервированном четвёртом запуске.
- После двух неуспешных fixes Controller запрашивает явное разрешение
  пользователя. Автоматический третий раунд запрещён.
- Каждый разрешённый раунд 3–5 использует свежий Controller, новый budget и
  пересмотренную модель либо утверждённое design-решение.
- После пятого неуспешного раунда присваивается `BLOCKED`; открытые findings и
  следующий диагностический шаг сохраняются.

Немедленно остановить цикл как `BLOCKED_FOR_DESIGN`, если фактический file
scope более чем вдвое превысил preflight, появилась новая подсистема/state
owner, один production-seam bypass повторился, требуется придумать semantics
или partial diff после usage limit не имеет безопасного checkpoint.

## Возобновление

1. Не считать прерванного агента завершившим работу и не откатывать
   пользовательские изменения.
2. Зафиксировать current diff, изменённые файлы, RED/GREEN состояние,
   незавершённые проверки, budget counters, последний `TOKEN_USAGE` и последнее
   достоверное evidence.
3. Проверить stop gates до нового spawn.
4. При design gap остановиться; при утверждённом design и прежнем scope
   передать свежему Implementer только компактный handoff.

## Контракты отчётов

Implementer:

```text
Статус: IMPLEMENTED | BLOCKED | NEEDS_CLARIFICATION
Ticket и baseline: <значения>
Изменённые файлы: <список>
Acceptance: <критерий -> изменение>
Тесты агента: <путь/имя, created|modified|deleted, что проверяет, criterion>
RED/GREEN evidence: <команда, exit code, результат>
Использованный process skill: <TDD | диагностика>
Не выполнено: <список>
Риски и допущения: <список>
```

Reviewer:

```text
SPEC: PASS | FAIL
CODE_QUALITY: PASS | FAIL
Fixed point и diff: <значения>
Acceptance: <критерий -> evidence>
Findings: <тип, severity, корневая причина, файл/область, требуемый результат>
Design gaps/new requirements: <список>
Непроверенные риски: <список>
```

Verifier:

```text
EXECUTABLE_VERIFICATION: PASS | FAIL | NOT_RUN
Итог: ACCEPTED | REJECTED
Acceptance: <критерий -> evidence>
Команды: <команда, exit code, результат>
Full suite: <команда, started/finished, exit code, counts или обоснование
отсутствия>
Live evidence: <сценарий и результат либо NOT_RUN>
Непроверенные риски: <список>
```

После `REJECTED` Controller добавляет к Verifier verdict:

```text
FAILURE_SUMMARY
PRIMARY_FAILURE: <одна нормализованная корневая причина или UNKNOWN>
CASCADE_FAILURES: <точное число тестовых падений, вызванных primary failure, или UNKNOWN>
IN_SCOPE: <yes|no|unknown; краткое основание>
NEXT_LOOP: <bounded repair с focused command | BLOCKED_FOR_DESIGN | user decision>
```

`CASCADE_FAILURES` не является числом всех failed tests: в него входят только
падения, для которых Verifier установил одну primary cause. При `UNKNOWN`
Controller не придумывает grouping и не расходует новый implementation budget
до создания red-capable focused loop.

## Token usage report

После каждого `DONE`, `BLOCKED_FOR_DESIGN`, `BLOCKED`, `BUDGET_GATE` и
Verifier verdict `REJECTED` Controller публикует `TOKEN_USAGE`. Он получает
значения только из доступного Codex task/role-agent usage или execution trace;
не оценивает и не выводит вымышленные токены. Отчёт не создаёт новую роль и не
задерживает status.

```text
TOKEN_USAGE
Статус: <DONE|REJECTED|BLOCKED_FOR_DESIGN|BLOCKED|BUDGET_GATE>
Источник: <usage/execution trace|NOT_AVAILABLE>
Implementation: <Implementer и follow-ups: input, cached input, output,
reasoning или NOT_AVAILABLE>
Acceptance/control: <Controller, Reviewer, Verifier по ролям или NOT_AVAILABLE>
Ticket total: <input, cached input, output, reasoning или NOT_AVAILABLE>
Coverage: <COMPLETE|PARTIAL|NOT_AVAILABLE>
Отсутствующие значения: <список|нет>
```

`COMPLETE` означает, что суммарные значения построены из observed counters
каждой запущенной роли и Controller. Если provider не раскрывает часть или все
счётчики, использовать `PARTIAL` либо `NOT_AVAILABLE`; это не повод заменять
цифры оценкой.

## Финальное evidence

Controller сохраняет project/ticket ID, baseline и итоговый diff, acceptance
evidence, команды и exit codes, тесты Implementer, модели/effort, findings и
adjudication, число fix-раундов, сработавшие stop gates, live/NOT_RUN проверки,
budget counters, compaction/checkpoint и итоговый статус.
К каждой закрытой или отклонённой попытке также сохраняется `TOKEN_USAGE`.

`DONE` разрешён только при независимых `SPEC: PASS`, `CODE_QUALITY: PASS` и
достаточном `ACCEPTED` evidence по каждому acceptance criterion.
