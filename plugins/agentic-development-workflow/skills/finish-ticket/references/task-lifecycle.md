# Протокол выполнения одного ticket

Версия workflow: `1.7`

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
   запусков, Sol, full suite и compaction; также правило эскалации модели.
10. При возобновлении сопоставить checkpoint с текущим partial diff и отметить
   устаревшее evidence.

Формат: Controller выводит заголовок `PREFLIGHT_REPORT`, затем две Markdown
таблицы. В ячейках — короткие фразы, без повторения ticket/spec и без
многострочных escape-последовательностей.

| Блок | Значение |
|---|---|
| Ticket / spec | `<пути или идентификаторы>` |
| Project / baseline | `<root; ветка и commit или manifest>` |
| Acceptance | `<краткие criteria -> evidence>` |
| Risk | `<сложность; факторы>` |
| Scope | `<компоненты; лимит файлов; исключения>` |
| Feedback loop | `<targeted RED/GREEN command>` |
| Routing | `<следующая роль; model/effort; причина>` |
| Budget | `<class; role-agent N/M; Sol N/M; suite N/1; compaction N/M>` |
| Stop gates / design gaps | `<условия; нет или список>` |
| Next action | `<spawn, confirmation или BLOCKED_FOR_DESIGN>` |

| Criterion | Production seam | Test seam / RED command | Production consumer / compatibility command | Owner | Status |
|---|---|---|---|---|---|
| `<criterion>` | `<entry point>` | `<injected seam; command>` | `<consumer; command>` или `N/A — boundary unchanged` | `<owner>` | `READY` или `DESIGN_GAP` |

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

Сначала проверить фактический allowlist текущего multi-agent инструмента.
Названия Luna, Terra и Sol ниже означают доступные семейства соответствующего
уровня; при отсутствии семейства выбрать ближайшую доступную модель и явно
записать соответствие.

Если allowlist пока недоступен, всё равно выбрать planned capability tier из
таблицы, например `Luna high`, и пометить только точный model ID как
`UNRESOLVED_UNTIL_SPAWN`. Значение «определить позже» без tier и effort не
заполняет `PREFLIGHT_REPORT`.

| Работа | Модель | Effort |
|---|---|---:|
| Механическая реализация 1–2 файлов | Luna | high |
| Обычная реализация или Controller | Terra | medium |
| Сложная или критичная реализация | Terra | high |
| Обычный Reviewer | Terra | medium |
| Критичный Reviewer | Terra | high |
| Deterministic Verifier | Luna | medium |
| Интерпретирующий Verifier | Terra | medium |
| Design-adjudication или доказанный недостаток Terra | Sol | high |

Ticket критичен при сочетании минимум двух факторов: security/privacy;
concurrency/cancellation; OS/native/UIA/COM/driver/installer; необратимый side
effect; новый architecture seam/state owner; труднообратимое изменение данных
или Git history.

Sol `high` не является default для critical ticket. Перед его выбором Controller
записывает конкретный недостаток Terra: неразрешённый finding, невозможность
обосновать design или подтверждённый failure targeted loop. Больше одного Sol
на ticket требует явного разрешения пользователя. `xhigh` разрешён только
после измеримого недостатка `high`; `max` и `ultra` не входят в стандартный
процесс.

Перед каждым spawn Controller публикует:

```text
Раунд: <номер>
Роль: <роль>
Budget: <role-agent N/M; Sol N/M; full suite N/1; compaction N/M>
Сложность: <простая | обычная | сложная | критичная>
Риск: <низкий | средний | высокий | критичный>
Модель и effort: <точные значения из allowlist>
Причина: <почему это минимально достаточная конфигурация>
Эскалация: <нет или предыдущая -> новая с причиной>
```

## Budget и context gate

| Класс ticket | Role-agent запуска | Sol без нового разрешения | Full suite | Compaction |
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
