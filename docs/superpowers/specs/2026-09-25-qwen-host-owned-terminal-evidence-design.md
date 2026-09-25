# Draft: terminal evidence для native Qwen continuation

> **Статус:** целевая evidence semantics одобрена владельцем 2026-09-25; runtime-реализация не выполнена. `HOST_CLEAR` принят только как отдельный host detector outcome при полном event stream, не как синоним `NATIVE_CLEAR`. Обычный `NORMAL_EXIT` не является budget stop. D048 и live Ticket 24 gate остаются fail-closed до реализации и доказательства source.

## Цель

Определить, может ли ProofLoop доказать terminal outcome native Qwen-сессии собственным host evidence и каким отдельным evidence можно оценить loop state. Цель — не называть host-наблюдение сигналом Qwen и не открывать Ticket 24 по отсутствию ошибок или событий.

## Термины

- **Terminal receipt** — raw-free host record одного запуска: связывает launch/session/task identities, terminal reason, наблюдаемый process outcome, полноту event stream, counters и источник loop assessment. Это не встроенный Qwen artifact и не самоутверждение модели.
- **Terminal reason** — ответ на вопрос, *почему процесс/сессия завершились*.
- **Loop status** — отдельный ответ на вопрос, *какое loop evidence доступно*. Причина остановки и loop status не выводятся друг из друга.
- **Host-owned evidence** — факт, непосредственно наблюдённый ProofLoop launcher/supervisor, например его monotonic deadline и отправленный им stop request для связанного child process. Проекция одних только Qwen JSON events не становится host-owned stop evidence.
- **`NATIVE_CLEAR`** — явное документированное положительное состояние от Qwen runtime. В текущем опубликованном Dual Output contract такого поля не найдено.
- **`HOST_CLEAR`** — отдельное утверждение будущего host detector: обработан полный, привязанный к сессии event stream и по явно утверждённому алгоритму detector не обнаружил loop. Это не эквивалент `NATIVE_CLEAR` и не характеристика внутреннего состояния Qwen.

## Наблюдаемый текущий seam и ограничение

Protocol launcher добавляет временный `--json-file`, синхронно вызывает Qwen, а после возврата процесса передаёт файл проектору и удаляет его в `finally`. Он измеряет elapsed time, но не наблюдает wall-limit во время запуска и не управляет остановкой дочернего процесса. Поэтому текущий post-process projection не может сам доказать, что host остановил процесс по wall/tool limit. Перед проектированием такой способности нужно отдельно установить, возможно ли отслеживать события и управлять процессом, сохраняя native TUI execution mode.

Текущий adapter выдаёт session digest, завершённые assistant turns, число tool-use IDs, elapsed seconds, `session_ended`, `terminal_reason: null`, `budget_stop: false` и `loop_status: UNOBSERVED`. Его `tool_fingerprint` — digest отсортированного списка tool-use IDs, а не доказательство повторения семантически одинаковых действий и не loop detector.

Проверенная заметка по Qwen Code v0.24.5 указывает: native TUI `--json-file` документирует `session_end` как clean shutdown, но не typed budget-stop reason и не явный loop status; headless exit 55 относится к иному режиму и не разделяет причины run-level budget; `StopFailure` hook может дать positive loop failure, но не clear confirmation, и требует hook configuration. Источник: `docs/research/qwen-v0245-terminal-evidence-refresh-20260925.md` и первичные ссылки в нём.

## Контракт полноты event stream

| Значение | Условия | Разрешённое использование |
|---|---|---|
| `COMPLETE` | Источник привязан к одному launch/session; процесс и все его descendants завершены, event writer закрыт; весь поток прочитан без пропусков, повреждений, неподдерживаемой схемы и незакрытых tool-use/result пар; есть ровно один финальный matching `session_end`. При host stop `session_end` начинается с byte offset не меньше `event_file_bytes_at_stop`, снятого после фиксации stop intent и последней проверки живого процесса, но до graceful interrupt; offset обязан совпадать с границей полной JSONL-строки. | Только после этого разрешено вычислять counters и host detector result по всему потоку. Само `COMPLETE` не означает budget stop или `CLEAR`. |
| `INCOMPLETE` | Есть конкретный признак усечения, ошибки чтения/парсинга, отсутствующего требуемого конца потока, mismatch session identity или collector gap. | Terminal block; continuation запрещён. |
| `UNKNOWN` | Нельзя подтвердить ни полноту, ни конкретный дефект — например, контракт источника не описывает final flush либо race между закрытием процесса и последним event. | Terminal block; continuation запрещён. |

Неизвестная schema считается fail-closed: adapter сохраняет только фиксированный raw-free reason, не raw event и не exception text. Отсутствие event не является evidence, что event stream полон.

## Таблица причин остановки

| `terminal_reason` | Кто владеет фактом / минимально достаточное доказательство | Полнота и противоречия | Текущее состояние / Ticket 24 |
|---|---|---|---|
| `NATIVE_BUDGET_STOP` | Qwen runtime сообщает документированный typed stop kind, связанный с конкретной session; terminal event согласован с закрытием процесса. Один exit code или счётчики недостаточны. | Нужны известная schema, session binding, полный поток и отсутствие конфликтующего terminal fact. | Не документирован в проверенном native `--json-file` contract; классифицировать как `UNKNOWN`/unsupported, не принимать как terminal proof. |
| `HOST_WALL_LIMIT` | Host supervisor видит monotonic deadline, записывает stop intent для конкретной child-process identity, посылает graceful interrupt в изолированную process group и ждёт matching `session_end`, затем exit того же process tree. | Supervisor должен наблюдать весь интервал. Если `session_end` пришёл до stop, stop не приписывается host; если matching clean end после stop отсутствует или race неупорядочен — `UNKNOWN`, не budget continuation. | Не реализовано: текущий launcher вызывает Qwen синхронно и проецирует sidecar после возврата. Нужен process-supervision seam, graceful console interrupt, сохранение native TUI и полный terminal sidecar. |
| `HOST_TOOL_LIMIT` | Host supervisor считает завершённые tool-use/result пары из потока той же session; после ceiling фиксирует stop intent, посылает graceful interrupt в изолированную process group и ждёт matching `session_end`, затем exit process tree. | Нельзя останавливать между `tool_use` и `tool_result`. Нужны live delivery, однозначное pairing, отсутствие loss/duplicates и race-safe ordering. Без `session_end` после stop continuation запрещён. | Не реализовано: текущий sidecar читается после запуска; live completed-pair counter/stop source не доказан. |
| `NORMAL_EXIT` | Host наблюдает завершение дочернего процесса и его числовой exit; native `session_end`, если присутствует, подтверждает только clean session shutdown. | Нужна согласованность process/session identity. Не превращать в budget stop или `CLEAR`. | Доступны отдельные post-run наблюдения, но это не подходящий budget terminal для Ticket 24 continuation. |
| `USER_INTERRUPT` | Host/console handler действительно наблюдает interrupt для данной child process; процесс после него завершён и exit связан с тем же launch. | Если Ctrl+C оборвал сам launcher до durable receipt либо нельзя отделить interrupt от иных exits — `UNKNOWN`. | Точный raw-free interrupt receipt текущим путём не доказан; не считать exit code alone достаточным. |
| `PROCESS_FAILURE` | Host наблюдает факт запуска и завершения с numeric non-zero exit или классифицированный allowlisted process failure. | Сырой stderr/exception не сохраняется; если конкретная причина не доказуема, остаётся только `PROCESS_FAILURE`/`UNKNOWN`, без budget вывода. | Возможна raw-free классификация отдельных error envelopes, но она не заменяет terminal source для continuation. |
| `UNKNOWN` | Обязателен при отсутствии source, неполноте, неоднозначном race, несовпадении identity, неизвестной schema или противоречивых фактах. | Всегда terminal/fail-closed. | Текущее состояние при отсутствии typed evidence; Ticket 24 остаётся `BLOCKED_EVIDENCE_SOURCE` / `NOT_RUN`. |

`terminal_reason` не устанавливается по финальному тексту Qwen, `session_end` без stop kind, одному exit code, превышению counter после факта или отсутствию loop-события.

## Loop-status contract: раздельные источники

| `loop_status` | Источник и условия | Чего это не доказывает |
|---|---|---|
| `NATIVE_CLEAR` | Позитивный, документированный Qwen field/event с известной schema и session binding. | Не выводится из включённой настройки loop detection, отсутствия `StopFailure`, нормального завершения или текста модели. |
| `HOST_CLEAR` | Host detector получил `event_coverage=COMPLETE`, все completed tool interactions связаны с результатами и анализ `exact_tool_interaction_cycle_v1` завершён без срабатывания. | Не доказывает внутреннее решение Qwen и не утверждает абсолютное отсутствие любого возможного цикла. Не может быть выдан при неполном/неизвестном цикле. Повтор одного `name/input` не считается циклом: detector сравнивает assistant content, упорядоченные tool-use blocks и связанные результаты. |
| `DETECTED` | Явное positive native loop error либо три последовательных идентичных полных host interaction cycles с source/version и связанными event identities. | Само совпадение `{tool name, input}` недостаточно. Изменившийся assistant content или matched result сбрасывает серию; две одинаковые completed cycles ниже порога. Даже полное тройное совпадение не прерывает живой процесс: оно только блокирует continuation. Намеренно повторённый workflow всё ещё может дать false positive, а меняющийся loop — быть пропущен. Положительное обнаружение не доказывает budget reason. Hook `StopFailure` сам по себе не предоставляет clear signal. |
| `UNKNOWN` | Нет positive clear/detection; полнота или источник не подтверждены; схема неизвестна; detector не завершился. | Нельзя трактовать как `CLEAR`; continuation запрещён. |

Проверка алгоритма подтвердила, что три одинаковых `{name, input}` fingerprint недостаточны: они игнорируют assistant continuation и результаты, поэтому одинаковое чтение файла/команда проверки может быть ошибочно принято за цикл. Принятый для реализации узкий detector `exact_tool_interaction_cycle_v1` формирует in-memory fingerprint из нормализованного содержимого одного завершённого assistant tool-use message и связанных `tool_result` blocks (content и `is_error`), исключая уникальные message/tool-use IDs. Три соседних идентичных полных cycle fingerprints дают `DETECTED`; одно повторение вызова без совпадения полного interaction cycle не считается. Изменение input, результата, порядка действий или assistant content сбрасывает серию.

Detector является только классификатором terminal stream и никогда не останавливает живой Qwen process. Wall/tool supervisor останавливает child только по собственным ceilings, причём tool ceiling считается по завершённым `tool_use`/`tool_result` парам. Для `event_coverage=COMPLETE` требуется matching `session_end` после host stop: опубликованный Qwen контракт допускает adapter exception, который отключает bridge без `session_end`, так что один закрытый файл недостаточен. Graceful stop timeout требует force termination и даёт `INCOMPLETE`/`UNKNOWN`, без continuation. Невалидная/непарная схема, возможное усечение result либо неполный поток также дают `UNKNOWN`. Даже exact repeated cycle может быть намеренным в редком workflow: detector ограничен и не является oracle намерения; loops с изменяющимся содержимым он может пропустить. Эти ограничения версия detector делает явными.

## Raw-free terminal receipt (принятая цель; точная схема и реализация ожидают review)

Минимальная проекция должна связывать:

- `schema_version`, opaque `launch_id` и хеш `session_id`;
- ticket/task/scope/baseline/diff/progress identity, уже проверяемые checkpoint adapter;
- `terminal_reason` и отдельный `terminal_source` (`NATIVE`, `HOST`, `PROCESS`, `UNKNOWN`);
- числовой process exit и завершённые counters/elapsed time;
- `event_coverage` и provenance завершения collector;
- `loop_status`, его source (`NATIVE`/`HOST`) и detector/schema version, если применимо;
- фиксированный status/reason и decision о continuation; raw `session_id` в receipt не сохраняется.

Не включаются prompt, сообщения, tool arguments/results, команды, абсолютные пути, credentials и raw exception. Любая неполная, несогласованная, устаревшая или неподписанная identity блокирует continuation. Receipt должен добавляться в существующий append-only evidence chain; он не получает acceptance authority и не переписывает counters прошлой session.

Владелец принял raw-free host-owned evidence как допустимую альтернативную source semantics в D051. Поля и строгая схема ниже являются implementation proposal, а не уже внедрённым runtime contract; точные интерфейсы и алгоритм detector вынесены на review в `docs/superpowers/plans/2026-09-25-qwen-host-owned-terminal-evidence.md`.

## Будущая локальная test matrix (не выполнена в этом design draft)

Fixtures должны управлять fake child process и fake event writer, не вызывая Qwen:

| Сценарий | Ожидаемые terminal/evidence поля | Continuation dispatch |
|---|---|---|
| Fake child жив после host wall deadline; supervisor фиксирует stop и получает process exit; stream полон | `HOST_WALL_LIMIT`, `COMPLETE`; loop — только результат отдельного детектора, иначе `UNKNOWN` | `0` при текущей политике; только после принятия host semantics и `READY` — ровно `1` |
| Fake tool event достигает порога во время живого stream; supervisor фиксирует stop и child exit | `HOST_TOOL_LIMIT`, `COMPLETE` только если доказаны доставка/flush/order; иначе `UNKNOWN` | То же: до принятого policy — `0`; согласованный `READY` — ровно `1` |
| Штатное завершение до любого host ceiling | `NORMAL_EXIT`; `COMPLETE` если выполнены end-of-stream условия | `0` для budget continuation |
| Child crash / non-zero exit | `PROCESS_FAILURE`, только наблюдённый exit; coverage может быть `INCOMPLETE` | `0` |
| User interrupt без durable host observation либо с неустановленным process identity | `UNKNOWN`; не приписывать причину по одному коду | `0` |
| Sidecar пустой, усечён, имеет unknown schema, missing end/flush либо session mismatch | `UNKNOWN` или `INCOMPLETE`; raw-free reason | `0` |
| Host detector не получил последнюю запись / не завершился / встретил unknown event | `loop_status=UNKNOWN`; никогда не `HOST_CLEAR` | `0` |
| Три вызова имеют одинаковые `{name,input}`, но возвращают разные результаты | `HOST_CLEAR`, если stream полон и остальные cycles валидны | eligible только при отдельном `READY` |
| Три вызова имеют одинаковые `{name,input}` и результаты, но assistant content различается | `HOST_CLEAR`, если stream полон и остальные cycles валидны | eligible только при отдельном `READY` |
| Три полных assistant/tool-result interaction cycles полностью одинаковы | `DETECTED`; loop classifier не прерывает процесс | `0` |
| В raw input есть secret, prompt marker, tool argument и абсолютный путь | Ни одно значение не выходит в stdout/stderr/permanent receipt | `0` при block; projection не утечёт raw |

Эти fixtures докажут только host adapter/process-control контракт. Они не докажут Qwen native behavior, live TUI compatibility или успешный Ticket 24.

## Варианты решения

1. **Сохранить native-only evidence gate.** Ждать документированного Qwen terminal budget reason и explicit `NATIVE_CLEAR`. Максимально сохраняет смысл текущего native gate; Ticket 24 остаётся заблокированным.
2. **Отдельно принять host-owned evidence.** Спроектировать process supervisor и независимый detector, предварительно доказать feasibility на fake process, затем проверить влияние на native TUI и event completeness. Это settings-neutral по замыслу, но меняет semantics: host stop/`HOST_CLEAR` становится допустимым только если владелец явно принимает его как альтернативу native evidence. Потребуются отдельное решение и синхронизация канонического протокола/plugin/docs/tests до исполнения.
3. **Использовать headless exit codes или StopFailure hook.** Не рекомендуется: headless меняет execution mode и не разделяет все причины; hook даёт возможный positive failure, но не clear, и требует настройки вне текущего scope.

**Решение владельца 2026-09-25:** выбран вариант 2 как допустимая целевая evidence semantics. Host supervisor обязан доказать, что сохраняет native TUI и получает полный event stream. `HOST_CLEAR` допустим как отдельный versioned host detector result, но не подменяет внутренний сигнал Qwen. Если process-control или event completeness не доказуемы, source считается unsupported и Ticket 24 остаётся blocked.

## Согласованные условия и открытый implementation detail

1. Владелец подтвердил, что `HOST_CLEAR` может быть альтернативным host evidence только при полном stream и явном detector; оно не равняется `NATIVE_CLEAR`.
2. Владелец подтвердил, что `NORMAL_EXIT` не открывает budget continuation.
3. Точный host loop fingerprint/threshold остаётся implementation detail для отдельного reviewed plan. Он должен показать алгоритм, false-positive/false-negative cases и тесты до начала реализации.

До реализации и проверки evidence source Ticket 24 остаётся `BLOCKED_EVIDENCE_SOURCE` / `NOT_RUN`. Implementation plan готовится отдельно; он не означает, что runtime source уже доступен.
