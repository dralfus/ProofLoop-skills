# Qwen Host-Owned Terminal Evidence Design Plan

> **Для исполнителей:** это план только design-stage. Реализация, изменение пользовательской конфигурации Qwen и live-запуск запрещены до отдельного согласования.

**Цель:** определить, может ли ProofLoop сам надёжно подтвердить причину остановки Qwen и отсутствие host-detected loop, не выдавая это за native Qwen `CLEAR`.

**Архитектура:** сохранить текущий fail-closed контракт D048. Исследовать supervision процесса и полноту event stream; затем представить владельцу отдельный raw-free receipt contract и вариант решения. Возможный статус `HOST_CLEAR` — только предложение о независимой host-проверке, не синоним `NATIVE_CLEAR`.

**Технологии:** Qwen CLI native protocol и `--json-file`; существующие PowerShell launchers; Python evidence adapter; `unittest` и fake-process fixtures.

**Основание:** `docs/superpowers/specs/2026-09-24-qwen-native-checkpoint-adapter-design.md`, D048 в `docs/decisions.md`, критерии Ticket 24 в `tickets.md`.

## Ограничения

- Не менять внешние пользовательские Qwen settings, provider, credentials, sampling, reasoning, role profile или настройки loop detection; не редактировать установку/кэш CLI и посторонние проекты.
- Пока выполняется этот design-stage, не делать model request и не запускать live pilot: это временная граница текущего этапа, а не общий запрет использовать Qwen. Любой будущий live pilot остаётся отдельным gate и не может стартовать, пока terminal evidence source не подтверждён.
- Не считать `session_end`, отсутствие loop-события, текстовый итог Qwen или exit code `55` доказательством budget-stop либо `CLEAR`.
- Не сохранять prompt, transcript, tool arguments/results, абсолютные пути, секреты или raw exception в постоянный receipt.
- Не ослаблять и не переписывать D048/Ticket 24 до отдельного решения владельца.
- Не переносить patch, не выполнять acceptance и не создавать commit.

## Фокус проверки

1. **Неполный event stream:** частичный файл, неизвестная запись или потерянный хвост дают `UNKNOWN` и запрещают continuation.
2. **Гонка host-stop:** достижение wall/tool ceiling около штатного завершения не должно ошибочно приписываться Qwen или наоборот.
3. **Неполное наблюдение loop:** `HOST_CLEAR` допустим только при доказанной полноте входных событий и завершённом host-анализе; иначе `UNKNOWN`.
4. **Различие источников:** native stop, host-issued stop, normal exit, crash и user interrupt остаются разными причинами.
5. **Raw leakage:** ни один отказ projection/collector не должен печатать или сохранять сырой event payload.

---

### Task 1: Зафиксировать происхождение и пределы terminal evidence

**Файлы:**
- Read: `docs/research/qwen-v0245-terminal-evidence-refresh-20260925.md`
- Read: `scripts/invoke_qwen_finish_ticket_cli.ps1`
- Read: `scripts/qwen_runtime_adapter.py`
- Read: `tickets.md` (Ticket 23 и Ticket 24), `docs/decisions.md` (D048)
- Create: `docs/superpowers/specs/2026-09-25-qwen-host-owned-terminal-evidence-design.md`

**Результат:** design draft с таблицей terminal reasons, источником каждого факта, producer/observer, требуемой полнотой и fail-closed исходом. Для `HOST_WALL_LIMIT` и `HOST_TOOL_LIMIT` draft обязан показать, что launcher сам наблюдал предел, запросил остановку дочернего процесса и получил его terminal process status. Если такая причинная цепочка не может быть доказана текущим способом запуска, исход — `UNSUPPORTED`, не предположение.

- [x] Сопоставить в таблице `NATIVE_BUDGET_STOP`, `HOST_WALL_LIMIT`, `HOST_TOOL_LIMIT`, `NORMAL_EXIT`, `USER_INTERRUPT`, `PROCESS_FAILURE` и `UNKNOWN` с наблюдаемым источником и достаточным доказательством.
- [x] Отдельно отметить, что `--json-file` counters не доказывают причину остановки, а опубликованный Qwen contract не гарантирует loop-clear signal.
- [x] Записать открытый технический вопрос: можно ли безопасно и полно tail/monitor native event file во время работы процесса, не меняя CLI mode или Qwen config.
- [x] Проверить черновик против текущего D048 и Ticket 24: пока нет принятого владельцем альтернативного решения, статус остаётся `BLOCKED_EVIDENCE_SOURCE`.

**Gate:** design draft не содержит вывода `CLEAR` из отсутствия события, счётчика или текста модели; все недоказуемые источники классифицированы как `UNKNOWN`.

### Task 2: Определить raw-free receipt и два независимых loop-status источника

**Файл:** `docs/superpowers/specs/2026-09-25-qwen-host-owned-terminal-evidence-design.md`

**Предлагаемая форма контракта (подлежит рассмотрению, не принята):**

- `terminal_reason`: одно значение из Task 1; причина содержит source class `NATIVE` или `HOST`.
- `process_exit`: только числовой exit code и факт завершения процесса; без вывода причины из одного кода.
- `event_coverage`: `COMPLETE`, `INCOMPLETE` или `UNKNOWN`, связанный с session identity и проверяемым концом потока.
- `counters`: только завершённые turns/tool calls и elapsed time; без raw payload.
- `loop_status`: `NATIVE_CLEAR`, `HOST_CLEAR`, `DETECTED` или `UNKNOWN`.
- `HOST_CLEAR`: может выдаваться лишь отдельным версионируемым host detector при полном покрытии событий и отсутствии срабатывания; точный fingerprint/threshold contract должен быть явно описан и проверяем. Иначе `UNKNOWN`.
- `NATIVE_CLEAR`: допустим только если Qwen выдаёт явный документированный позитивный signal и adapter проверяет его известную схему. Его нельзя синтезировать host-кодом.
- Любой невалидный, неполный, устаревший или несвязанный receipt блокирует continuation.

- [x] Зафиксировать обязательные связи receipt: opaque session/run identity, ticket/scope identity, launch identity и event coverage; исключить пути и содержимое задачи.
- [x] Описать state table для `NATIVE_CLEAR` и `HOST_CLEAR`: это разные утверждения, и ни одно не получается из другого.
- [x] Включить сценарии false-clear: процесс завершился до flush, collector пропустил event, неизвестный event, detector не получил весь поток.
- [x] Не выбирать конкретный loop fingerprint/threshold без обоснования по event schema и отдельного владельческого решения.

**Gate:** другой исполнитель может по таблице классифицировать native signal, host-owned stop, неполноту и неизвестность, не прибегая к эвристике или тексту Qwen.

### Task 3: Подготовить исполнимую матрицу для будущей локальной проверки

**Файл:** `docs/superpowers/specs/2026-09-25-qwen-host-owned-terminal-evidence-design.md`

- [x] Указать fake-process случаи: launcher-issued wall stop, launcher-issued tool stop, штатный exit до лимита, crash, interrupt и неответивший процесс.
- [x] Указать event-stream случаи: пустой, корректный полный, частичный, неизвестная schema, отсутствующий terminal event и race между последней записью и process exit.
- [x] Для каждого случая задать ожидаемые `terminal_reason`, `event_coverage`, `loop_status` и факт dispatch continuation (только `READY` открывает ровно одну fresh session; прочее — ноль).
- [x] Добавить raw-leak assertions на synthetic secret, prompt marker, tool argument и абсолютный путь.
- [x] Явно отделить эти локальные fixtures от live Qwen proof: fixtures подтверждают host contract, но не native CLI поведение.

**Gate:** матрица задаёт наблюдаемый PASS/FAIL для каждого receipt-класса, включая неполные и состязательные события.

### Task 4: Получить решение владельца и только затем планировать реализацию

**Файлы на этом design-stage:** только новая design spec. `D048`, канонический протокол, launcher, plugin, tests и Ticket 24 остаются неизменными.

- [x] Представить владельцу design draft с двумя явно разделёнными вариантами: продолжать ждать native terminal signals; либо отдельно рассмотреть host-owned stop + host detector contract.
- [x] До решения не заменять текущий native-clear gate на `HOST_CLEAR` и не менять Ticket 24 статус.
- [x] После выбора host-owned варианта зафиксировать отдельное решение в `docs/decisions.md` и согласовать целевую evidence semantics и scope.
- [x] После одобрения design spec составить отдельный implementation plan с точными интерфейсами и тестами для launcher, adapter, lifecycle policy, canonical protocol, plugin и пользовательских документов: `docs/superpowers/plans/2026-09-25-qwen-host-owned-terminal-evidence.md`.
- [x] Получено отдельное разрешение владельца перейти к реализации после подготовки плана; live pilot остаётся самостоятельным последующим gate.

**Gate:** design-stage завершён: spec reviewed, D051 принят, implementation plan подготовлен, общее разрешение на реализацию получено. Код начинается после review конкретного implementation plan и подтверждения предложенного метода исполнения; live pilot остаётся самостоятельным последующим gate.

---

## Критерии завершения этого плана

- Design draft не смешивает native Qwen signal с host-owned evidence.
- Каждая terminal reason имеет источник и явные условия `UNKNOWN`.
- Receipt не содержит raw transcript или секретные/путевые данные.
- D048 и Ticket 24 остаются fail-closed до отдельного решения владельца.
- D051 фиксирует принятое целевое host-owned semantics; runtime implementation и live proof остаются невыполненными.
- Ни код, ни Qwen CLI, ни Qwen settings не изменялись/запускались в design-stage.
