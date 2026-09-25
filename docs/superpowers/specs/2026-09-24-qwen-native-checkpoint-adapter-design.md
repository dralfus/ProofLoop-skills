# Дизайн: native Qwen checkpoint adapter

## Цель

Подключить локальный progress-gated runtime policy Ticket 22 к native protocol
launcher так, чтобы новая Qwen session могла стартовать только после проверки
текущего состояния проекта и Controller-attested checkpoint. Изменения не
затрагивают Qwen settings, provider, sampling, credentials, reasoning или
внешние файлы.

## Failure mode

Ticket 22 проверяет schema, hashes и переходы runtime ledger, но policy получает
Controller-provided evidence и самостоятельно не проверяет worktree, task,
progress ledger и test/review receipts. Native protocol launcher вызывает только
prelaunch guard, затем запускает Qwen и отбрасывает его stdout/stderr. Поэтому
checkpoint contract пока не является доказательством актуального состояния и
не защищает новую session от stale или поддельного host evidence.

## Решение

Добавить host evidence adapter и явный guarded continuation path:

1. Native Qwen protocol invocation использует `--json-file` как sidecar рядом с
обычным CLI output. Эта опция сохраняет обычный режим работы; event-файл
считается чувствительным transcript, создаётся как временный файл и удаляется в
`finally` после raw-free projection. Сырые события никогда не выводятся в
launcher status или постоянный receipt.
2. Проектор извлекает только allowlisted lifecycle/metrics: session identity в
виде digest, завершённые assistant turns, уникальные tool-use calls, session
start/end и известные terminal enum. Неизвестное/неполное event shape означает
`QWEN_RUNTIME_EVIDENCE_UNSUPPORTED`; значения сообщений, tool input/results,
cwd, command и file paths не сохраняются. Само наличие `session_end` не
доказывает budget stop.
3. Явный continuation request несёт checkpoint, append-only runtime ledger,
   canonical progress ledger, prior raw-free terminal projection и typed
   test/review receipts. Adapter сам сверяет ticket/task/scope/baseline,
   актуальный Git diff fingerprint, projection с предыдущим runtime observation,
   budget terminal, loop status и progress/receipts, а затем вызывает
   `qwen_runtime_guard_decision`. Поля checkpoint не заменяют проверку исходных
   источников.
4. Launcher разрешает dispatch только для `QWEN_RUNTIME_GUARD_READY`. Отсутствие
evidence, любой mismatch, loop/repeated fingerprint, неизвестный terminal
reason или ошибка raw-free projection дают fail-closed результат без вызова
Qwen. Продолжение создаёт свежие launch/evidence identities; предыдущие
counters и ledger events не удаляются.
5. Continuation prompt использует тот же canonical `/finish-ticket ticket <id>`
и добавляет Controller-verified progress context как текст prompt, не как часть
raw-free runtime receipt. Ticket requirements и scope не меняются.

Qwen Dual Output документирует JSONL sidecar как полный session event log, то
есть он может содержать prompt и tool content. Поэтому его нельзя считать
безопасным долговременным audit log. Документация описывает session lifecycle и
metrics, но не гарантирует отдельный budget-stop reason для всех protocol
ceilings. Проектор не выводит этот reason из эвристик; если launcher/CLI не
предоставляет проверяемый terminal enum или точный budget evidence, continuation
блокируется. Runtime hooks и settings не используются.

Текущий raw-free sidecar projection достоверно извлекает session hash, завершённые
assistant turns и уникальные tool-use ids, но не классифицирует budget reason и
не может доказать loop-clear. Поэтому launcher-generated projection сам по себе
не разрешает continuation; до отдельного подтверждённого terminal source
production request останется fail-closed. Fixture READY доказывает композицию
host adapter и Ticket 22 policy, но не наличие terminal signal в Qwen CLI.

## Контракт host evidence adapter

- Вход: пути к worktree и JSON evidence bundle; входные пути не попадают в
  результат/receipt.
- Проверяется: baseline `HEAD`, task id и hash исходных task/spec, scope hash,
  raw-free progress ledger schema/sequence/hash, актуальный diff hash и свежие
  test/review receipt identities, статусы и diff binding; prior projection
  должен совпасть с предыдущим runtime observation и разрешённым terminal event.
- Результат: только фиксированный status/reason, launch/session identities,
  числовые counters, decision и append-only runtime ledger. Никаких raw
  сообщений, имён файлов, команд, diff или exception текста.
- Policy остаётся единственной authority для разрешения continuation и не
  получает role dispatch/acceptance authority из host adapter.

## Альтернативы

1. Передавать hashes напрямую в Ticket 22 policy — отклонено: это не проверяет
   фактические файлы и receipts.
2. Установить Qwen hooks — отклонено: hooks задаются через Qwen user/workspace
   settings и могут получать полный prompt/transcript; settings владельца вне
   scope.
3. Перейти на headless `stream-json` — отклонено для native path: это меняет
   protocol/UI mode. Dual-output sidecar сохраняет основной CLI output.

## Измеримые критерии

- Fixture end-to-end доказывает `adapter -> policy -> QWEN_RUNTIME_GUARD_READY`
  при текущих, согласованных evidence и ровно одну разрешённую fresh session.
- Изменение любого из task/scope/baseline/diff/progress/test/review receipt
  блокирует dispatch до вызова Qwen.
- Budget stop с валидным checkpoint сохраняет все прежние ledger events и
  counters; loop/repeated fingerprint остаются terminal.
- Повреждённый/неизвестный raw event stream блокирует continuation и нигде не
  печатает тестовые secrets, команды, пути или содержимое сообщений.
- Fake-Qwen launcher test подтверждает отсутствие child dispatch на любом
  blocked результате и точный сохранённый protocol budget.
- Локальные tests и validators проходят. Живой Qwen continuation, disposable
  patch transfer, acceptance и commit остаются отдельными gates.

## Границы

Не меняются существующие per-session ceilings (`20 turns / 20 tool calls / 30m
/ depth 1`), пользовательский Qwen config, provider, credentials, sampling,
reasoning, loop-detection configuration, skill role, acceptance authority,
recon, QWEN_ASSIST, seal и Codex routing. Никакая сессия модели не запускается в
рамках локальной реализации и проверки этого ticket.
